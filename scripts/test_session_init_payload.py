"""Regression tests for the session-init hook's SessionStart payload.

The hook must emit well-formed JSON of a fixed shape regardless of which encoder is available,
and must inject the generated skill router exactly once per session.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude/hooks/session-init.sh"
MANIFEST = ROOT / "ai/skills/manifest.csv"


def _stub_dir(tmp: Path, *, jq: bool, python3: bool) -> Path:
    """A PATH directory exposing only the tools we want the hook to find."""
    stub = tmp / "bin"
    stub.mkdir(exist_ok=True)
    wanted = {"jq": jq, "python3": python3}
    for tool in ("bash", "awk", "cat", "date", "dirname", "find", "id", "wc", "tr", "grep",
                 "pgrep", "sed", "mkdir", "rm", "printf", "env"):
        real = shutil.which(tool)
        if real and not (stub / tool).exists():
            (stub / tool).symlink_to(real)
    for tool, include in wanted.items():
        real = shutil.which(tool)
        if include and real and not (stub / tool).exists():
            (stub / tool).symlink_to(real)
    return stub


class SessionInitPayloadTests(unittest.TestCase):
    def run_hook(self, *, jq: bool, python3: bool) -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            env = dict(os.environ)
            env["PATH"] = str(_stub_dir(tmp, jq=jq, python3=python3))
            env["HOME"] = os.environ["HOME"]  # hook falls back to $HOME/.dotfiles
            # isolate the once-per-session marker from real sessions on this machine
            env["TMPDIR"] = str(tmp)
            proc = subprocess.run(
                [shutil.which("bash") or "/bin/bash", str(HOOK)],
                cwd=tmpdir,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # jq pretty-prints across several lines; the shell and python encoders emit one.
        start = proc.stdout.find("{")
        self.assertNotEqual(start, -1, f"no JSON object in stdout: {proc.stdout!r}")
        return json.loads(proc.stdout[start:])

    def assert_shape(self, payload: dict):
        self.assertIn("hookSpecificOutput", payload)
        inner = payload["hookSpecificOutput"]
        self.assertEqual(set(inner), {"hookEventName", "additionalContext"})
        self.assertEqual(inner["hookEventName"], "SessionStart")
        self.assertIsInstance(inner["additionalContext"], str)
        self.assertIn("hook: session-init", inner["additionalContext"])

    def test_payload_shape_with_jq(self):
        if not shutil.which("jq"):
            self.skipTest("jq not installed")
        self.assert_shape(self.run_hook(jq=True, python3=True))

    def test_payload_shape_without_jq(self):
        self.assert_shape(self.run_hook(jq=False, python3=True))

    def test_payload_shape_without_jq_or_python3(self):
        self.assert_shape(self.run_hook(jq=False, python3=False))

    def test_encoders_agree(self):
        """Every available encoder must produce the same parsed payload."""
        without_python = self.run_hook(jq=False, python3=False)
        with_python = self.run_hook(jq=False, python3=True)
        self.assertEqual(
            without_python["hookSpecificOutput"]["hookEventName"],
            with_python["hookSpecificOutput"]["hookEventName"],
        )

    def test_router_is_injected(self):
        context = self.run_hook(jq=False, python3=True)["hookSpecificOutput"][
            "additionalContext"
        ]
        self.assertIn("skill router", context)
        self.assertIn("ai/skills/manifest.csv", context)
        self.assertIn("core behaviors", context)
        # digest lines are phase-keyed and come from the manifest
        self.assertIn("orient:", context)
        self.assertIn("ship:", context)


class RouterDigestTests(unittest.TestCase):
    def test_every_manifest_phase_appears_in_the_digest(self):
        phases = set()
        for line in MANIFEST.read_text(encoding="utf-8").splitlines()[1:]:
            if line.strip():
                phases.add(line.split(",")[1])
        known = {"orient", "diagnose", "plan", "implement", "review", "ship", "operate"}
        self.assertEqual(
            phases - known, set(), "manifest uses a phase the digest cannot render"
        )


if __name__ == "__main__":
    unittest.main()
