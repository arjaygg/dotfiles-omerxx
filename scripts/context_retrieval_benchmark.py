#!/usr/bin/env python3
"""Reproduce LeanCtx Markdown fidelity, recall, and compression measurements."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
RECALL_TERMS = (
    "ALPHA_INVARIANT",
    "BETA_REFERENCE",
    "GAMMA_LIST_ITEM",
    "DELTA_FENCE",
    "OMEGA_QUALIFICATION",
)
TASK_QUERY = (
    "Explain the shared routing contract, including its table reference, "
    "nested procedure, complete code example, and cross-section exception."
)
MARKDOWN_REQUIREMENTS = {
    "front_matter": (
        "---\n"
        "title: Context routing fidelity fixture\n"
        "owner: context-platform\n"
        "---"
    ),
    "heading_ancestry": (
        "# Shared Contract\n\n"
        "The `ALPHA_INVARIANT` applies to every client."
    ),
    "table": (
        "| Class | Required route |\n"
        "|---|---|\n"
        "| Medium | `BETA_REFERENCE` |\n"
        "| Large | compose then focused read |"
    ),
    "nested_list": (
        "- Preserve `GAMMA_LIST_ITEM`.\n"
        "  - Preserve nested list ancestry."
    ),
    "complete_fence": (
        "```python\n"
        "def routing_fixture() -> str:\n"
        '    return "DELTA_FENCE"\n'
        "```"
    ),
    "cross_section_qualification": (
        "# Cross-Section Qualifications\n\n"
        "`OMEGA_QUALIFICATION` overrides `ALPHA_INVARIANT` only for archived log dumps."
    ),
}
CACHE_REREAD_MAX_TOKENS = 32


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def score_output(source: bytes, output: bytes) -> dict[str, object]:
    text = output.decode("utf-8", errors="replace")
    recalled = [term for term in RECALL_TERMS if term in text]
    preserved = [
        name for name, snippet in MARKDOWN_REQUIREMENTS.items() if snippet in text
    ]
    return {
        "source_sha256": sha256(source),
        "output_sha256": sha256(output),
        "byte_fidelity": output == source,
        "recall_at_5": len(recalled) / len(RECALL_TERMS),
        "recalled": recalled,
        "markdown_fidelity": len(preserved) / len(MARKDOWN_REQUIREMENTS),
        "preserved_markdown": preserved,
        "output_ratio": len(output) / len(source) if source else 0.0,
        "estimated_tokens": (len(output) + 3) // 4,
    }


def run_command(
    binary: Path,
    arguments: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: float,
) -> bytes:
    try:
        result = subprocess.run(
            [str(binary), *arguments],
            cwd=cwd,
            env=env,
            check=False,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            f"lean-ctx {' '.join(arguments)} timed out after {timeout:g}s"
        ) from error
    if result.returncode != 0:
        raise RuntimeError(
            f"lean-ctx {' '.join(arguments)} failed ({result.returncode}): "
            f"{result.stderr.decode(errors='replace')}"
        )
    return result.stdout


def run_mode(
    binary: Path,
    path: Path,
    mode: str,
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: float,
) -> bytes:
    return run_command(
        binary,
        ("read", str(path), "-m", mode),
        cwd=cwd,
        env=env,
        timeout=timeout,
    )


def benchmark(
    binary: Path,
    fixture: Path,
    *,
    repetitions: int = 600,
    timeout: float = 60,
) -> dict[str, object]:
    binary = binary.expanduser().resolve()
    base = fixture.read_text(encoding="utf-8")
    filler = "\n".join(
        f"Routine explanatory filler line {index}." for index in range(repetitions)
    )
    source = (base + "\n" + filler + "\n").encode()
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir)
        path = workspace / "complex-large.md"
        path.write_bytes(source)
        env = {
            **os.environ,
            "LEAN_CTX_DATA_DIR": str(workspace / "lean-ctx-data"),
            "XDG_CACHE_HOME": str(workspace / "cache"),
            "XDG_CONFIG_HOME": str(workspace / "config"),
            "XDG_STATE_HOME": str(workspace / "state"),
        }
        try:
            lean_ctx_version = run_command(
                binary,
                ("--version",),
                cwd=workspace,
                env=env,
                timeout=timeout,
            ).decode("utf-8", errors="replace").strip()
        except RuntimeError:
            lean_ctx_version = "unknown"
        outputs = {
            mode: run_mode(
                binary,
                path,
                mode,
                cwd=workspace,
                env=env,
                timeout=timeout,
            )
            for mode in ("raw", "full")
        }
        task_error = ""
        try:
            run_command(
                binary,
                ("session", "task", TASK_QUERY),
                cwd=workspace,
                env=env,
                timeout=timeout,
            )
            outputs["task"] = run_mode(
                binary,
                path,
                "task",
                cwd=workspace,
                env=env,
                timeout=timeout,
            )
            outputs["task_reread"] = run_mode(
                binary,
                path,
                "task",
                cwd=workspace,
                env=env,
                timeout=timeout,
            )
        except RuntimeError as error:
            task_error = str(error)
            outputs["task"] = b""
            outputs["task_reread"] = b""

    scored = {mode: score_output(source, output) for mode, output in outputs.items()}
    targets = {
        "exact_fidelity": all(scored[mode]["byte_fidelity"] for mode in ("raw", "full")),
        "recall_at_5": scored["task"]["recall_at_5"] >= 0.95,
        "focused_ratio": (
            not task_error
            and bool(outputs["task"])
            and scored["task"]["output_ratio"] <= 0.25
        ),
        "markdown_fidelity": scored["task"]["markdown_fidelity"] == 1.0,
        "cache_reread": (
            not task_error
            and scored["task_reread"]["estimated_tokens"] <= CACHE_REREAD_MAX_TOKENS
            and len(outputs["task_reread"]) < len(outputs["task"])
        ),
    }
    defects: list[str] = []
    if task_error:
        defects.append(task_error)
    if not targets["markdown_fidelity"] and not task_error:
        missing = sorted(
            set(MARKDOWN_REQUIREMENTS) - set(scored["task"]["preserved_markdown"])
        )
        defects.append(
            "LeanCtx task mode did not preserve Markdown structures: "
            + ", ".join(missing)
        )
    if not targets["cache_reread"] and not task_error:
        defects.append(
            "LeanCtx task reread returned "
            f"{scored['task_reread']['estimated_tokens']} estimated tokens; "
            f"target is <= {CACHE_REREAD_MAX_TOKENS} and smaller than the first read"
        )
    return {
        "binary": str(binary),
        "lean_ctx_version": lean_ctx_version,
        "task_query": TASK_QUERY,
        "modes": scored,
        "targets": targets,
        "defects": defects,
        "ok": all(targets.values()),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--binary",
        type=Path,
        default=ROOT / ".local" / "bin" / "lean_ctx_wrapper.sh",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path(__file__).parent
        / "fixtures"
        / "context-routing"
        / "complex.md",
    )
    parser.add_argument("--repetitions", type=int, default=600)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    report = benchmark(
        args.binary,
        args.fixture,
        repetitions=args.repetitions,
        timeout=args.timeout,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and not report["ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
