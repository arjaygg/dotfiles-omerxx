"""Verify proposal-only setup from a clean tracked clone."""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Any


class CleanCloneError(RuntimeError):
    """Raised when a clean-clone proposal check cannot be completed."""


def _archive_clone(root: Path, destination: Path, ref: str) -> int:
    result = subprocess.run(
        ["git", "-C", str(root), "archive", "--format=tar", ref],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode(errors="replace").strip()
        raise CleanCloneError(f"git archive failed: {detail}")

    try:
        with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r:") as archive:
            members = archive.getmembers()
            regular_members = [member for member in members if not member.issym() and not member.islnk()]
            archive.extractall(destination, members=regular_members)
            return len(members) - len(regular_members)
    except (OSError, tarfile.TarError) as error:
        raise CleanCloneError(f"cannot extract clean clone: {error}") from error


def _manifest_clients(clone: Path) -> list[str]:
    manifest_path = clone / "ai/config/manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        clients = manifest["clients"]
        names = [client["name"] for client in clients]
    except (KeyError, OSError, TypeError, json.JSONDecodeError) as error:
        raise CleanCloneError(f"invalid configuration manifest: {error}") from error
    if not names or len(names) != len(set(names)):
        raise CleanCloneError("configuration manifest must contain unique clients")
    return sorted(names)


def run_check(root: Path, ref: str = "HEAD") -> dict[str, Any]:
    """Archive ``ref`` and prove its setup dry-run is proposal-only."""

    root = root.resolve()
    with tempfile.TemporaryDirectory(prefix="dotfiles-clean-clone-") as directory:
        workspace = Path(directory)
        clone = workspace / "clone"
        fake_home = workspace / "home"
        clone.mkdir()
        fake_home.mkdir()
        skipped_symlink_count = _archive_clone(root, clone, ref)

        setup = clone / "setup.sh"
        if not setup.is_file():
            raise CleanCloneError("clean clone does not contain setup.sh")

        environment = os.environ.copy()
        environment["HOME"] = str(fake_home)
        result = subprocess.run(
            ["bash", str(setup), "--dry-run"],
            cwd=clone,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise CleanCloneError(f"clean-clone setup dry-run failed: {detail}")
        if "Setup complete" in result.stdout:
            raise CleanCloneError("setup dry-run reached the install path")

        try:
            payload = json.loads(result.stdout)
            proposals = payload["proposals"]
            clients = sorted(proposals)
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise CleanCloneError(f"setup dry-run did not emit proposals: {error}") from error

        expected_clients = _manifest_clients(clone)
        if clients != expected_clients:
            raise CleanCloneError(
                f"setup dry-run clients {clients!r} do not match manifest {expected_clients!r}"
            )

        runtime_writes = any(fake_home.iterdir())
        if runtime_writes:
            raise CleanCloneError("setup dry-run wrote below the isolated home")

        return {
            "client_count": len(clients),
            "clients": clients,
            "runtime_writes": False,
            "skipped_symlink_count": skipped_symlink_count,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--ref", default="HEAD")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(run_check(args.root, args.ref), sort_keys=True))
    except CleanCloneError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
