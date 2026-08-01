#!/usr/bin/env python3
"""Tests for .codex/hooks/user-prompt-submit.sh output aggregation.

The script sources $HOME/.dotfiles/.codex/hooks/lib.sh and runs three
downstream hooks from $HOME/.dotfiles/.claude/hooks/, so tests build a
fake HOME with stub scripts and drive the aggregator via subprocess.
"""

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".codex" / "hooks" / "user-prompt-submit.sh"

HOOK_NAMES = (
    "session-init-enforcer",
    "plans-healthcheck",
    "plan-todowrite-reminder",
)

LIB_STUB = """#!/usr/bin/env bash
codex_hook_log() { printf '[codex-hook] %s\\n' "$*" >&2; }
"""


def _hook_script(body: str) -> str:
    return "#!/usr/bin/env bash\ncat >/dev/null || true\n" + body


def _json_ctx(ctx: str) -> str:
    return json.dumps({"hookSpecificOutput": {"additionalContext": ctx}})


def _json_block(reason: str, ctx: str = "") -> str:
    out = {"decision": "block", "reason": reason}
    if ctx:
        out["hookSpecificOutput"] = {"additionalContext": ctx}
    return json.dumps(out)


class CodexUserPromptSubmitTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        lib_dir = self.home / ".dotfiles" / ".codex" / "hooks"
        lib_dir.mkdir(parents=True)
        (lib_dir / "lib.sh").write_text(LIB_STUB, encoding="utf-8")
        self.hooks_dir = self.home / ".dotfiles" / ".claude" / "hooks"
        self.hooks_dir.mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _write_hook(self, name: str, body: str | None):
        if body is None:
            return
        path = self.hooks_dir / f"{name}.sh"
        path.write_text(_hook_script(body), encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)

    def _run(self, hooks: dict, env_extra: dict | None = None):
        for name in HOOK_NAMES:
            self._write_hook(name, hooks.get(name))
        env = os.environ.copy()
        env["HOME"] = str(self.home)
        env.pop("CODEX_HOOKS_DISABLED", None)
        env.pop("CODEX_HOOKS_STRICT", None)
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            ["bash", str(SCRIPT)],
            input="{}",
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

    def test_merges_context_in_hook_order(self):
        proc = self._run({
            "session-init-enforcer": f"printf '%s' '{_json_ctx('first')}'",
            "plans-healthcheck": f"printf '%s' '{_json_ctx('second')}'",
            "plan-todowrite-reminder": f"printf '%s' '{_json_ctx('third')}'",
        })
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(ctx, "first\nsecond\nthird")
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")

    def test_first_block_reason_wins(self):
        proc = self._run({
            "session-init-enforcer": f"printf '%s' '{_json_block('reason-one', 'ctx-a')}'",
            "plans-healthcheck": f"printf '%s' '{_json_block('reason-two', 'ctx-b')}'",
        })
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["decision"], "block")
        self.assertEqual(out["reason"], "reason-one")
        self.assertEqual(out["hookSpecificOutput"]["additionalContext"], "ctx-a\nctx-b")

    def test_plaintext_output_becomes_context(self):
        proc = self._run({
            "session-init-enforcer": "printf 'plain advisory text'",
        })
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(
            out["hookSpecificOutput"]["additionalContext"], "plain advisory text"
        )

    def test_malformed_json_becomes_context(self):
        proc = self._run({
            "plans-healthcheck": "printf '{not valid json'",
        })
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(
            out["hookSpecificOutput"]["additionalContext"], "{not valid json"
        )

    def test_downstream_failure_ignored_when_not_strict(self):
        proc = self._run({
            "session-init-enforcer": "exit 3",
            "plans-healthcheck": f"printf '%s' '{_json_ctx('still-runs')}'",
        })
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(
            out["hookSpecificOutput"]["additionalContext"], "still-runs"
        )

    def test_downstream_failure_aborts_when_strict(self):
        proc = self._run(
            {"session-init-enforcer": "exit 3"},
            env_extra={"CODEX_HOOKS_STRICT": "1"},
        )
        self.assertEqual(proc.returncode, 3)

    def test_missing_script_aborts_when_strict(self):
        proc = self._run(
            {"session-init-enforcer": "true"},
            env_extra={"CODEX_HOOKS_STRICT": "1"},
        )
        self.assertNotEqual(proc.returncode, 0)

    def test_missing_script_skipped_when_not_strict(self):
        proc = self._run({
            "session-init-enforcer": f"printf '%s' '{_json_ctx('only-output')}'",
        })
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(
            out["hookSpecificOutput"]["additionalContext"], "only-output"
        )

    def test_disabled_hooks_produce_no_output(self):
        proc = self._run(
            {
                "session-init-enforcer": f"printf '%s' '{_json_ctx('x')}'",
                "plans-healthcheck": f"printf '%s' '{_json_block('r')}'",
            },
            env_extra={"CODEX_HOOKS_DISABLED": "1"},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_silent_hooks_produce_no_output(self):
        proc = self._run({
            "session-init-enforcer": "true",
            "plans-healthcheck": "true",
            "plan-todowrite-reminder": "true",
        })
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")


if __name__ == "__main__":
    unittest.main()
