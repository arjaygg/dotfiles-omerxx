#!/usr/bin/env python3
"""Contract tests for the read-before-overwrite gate (pre-tool-gate-v2.sh §3a).

The gate used to cover Edit/MultiEdit as well, backed by a uid-lifetime flat file
at /tmp/.claude-read-log-$(id -u) that only native Read ever wrote to. In lean-ctx
replace-mode sessions native Read has no schema, and neither ctx_read nor
Serena.getSymbolsOverview populated the log, so no compliant action could clear the
block. The Edit arm was removed (the harness's own Edit contract plus `old_string`
matching already cover it) and the Write arm was rebuilt: session-scoped,
realpath-canonicalized, exact-line matched, with ctx_read literal-path parity.

These tests pin all of that so pre-tool-gate-v2.sh and post-tool-analytics.sh
cannot drift apart again.
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS = REPO_ROOT / ".claude" / "hooks"
PRE_GATE = HOOKS / "pre-tool-gate-v2.sh"
POST_ANALYTICS = HOOKS / "post-tool-analytics.sh"


def read_log_for(session_id: str) -> Path:
    return Path(f"/tmp/.claude-read-log-{os.getuid()}-{session_id}")


def run_hook(script: Path, payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


class ReadBeforeOverwriteGateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.sandbox = Path(self._tmp.name)
        self.session_id = f"test-{os.getpid()}-{self.id().rsplit('.', 1)[-1]}"
        self.log = read_log_for(self.session_id)
        self.log.unlink(missing_ok=True)
        self.addCleanup(self.log.unlink, True)
        self.addCleanup(self._tmp.cleanup)

    # --- helpers -------------------------------------------------------

    def gate(self, tool_name: str, file_path: Path) -> subprocess.CompletedProcess:
        return run_hook(
            PRE_GATE,
            {
                "session_id": self.session_id,
                "tool_name": tool_name,
                "tool_input": {"file_path": str(file_path)},
            },
        )

    def observe_read(self, file_path: Path) -> None:
        run_hook(
            POST_ANALYTICS,
            {
                "session_id": self.session_id,
                "tool_name": "Read",
                "tool_input": {"file_path": str(file_path)},
            },
        )

    def observe_ctx_read(
        self, file_path: Path, tool_name: str = "mcp__lean-ctx__ctx_read"
    ) -> subprocess.CompletedProcess:
        return run_hook(
            POST_ANALYTICS,
            {
                "session_id": self.session_id,
                "tool_name": tool_name,
                "tool_input": {"path": str(file_path)},
            },
        )

    def assertDenied(self, result: subprocess.CompletedProcess) -> str:
        self.assertEqual(result.returncode, 0, result.stderr)
        decisions = [
            json.loads(line)["hookSpecificOutput"]
            for line in result.stdout.splitlines()
            if line.startswith("{") and "hookSpecificOutput" in line
        ]
        self.assertTrue(decisions, f"expected a deny decision, got: {result.stdout!r}")
        self.assertEqual(decisions[-1]["permissionDecision"], "deny")
        return decisions[-1]["permissionDecisionReason"]

    def assertAllowed(self, result: subprocess.CompletedProcess) -> None:
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("BLOCKED", result.stdout + result.stderr)

    def make_file(self, name: str, body: str = "content\n") -> Path:
        path = self.sandbox / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
        return path

    # --- the Edit arm is gone ------------------------------------------

    def test_edit_of_unread_file_is_allowed(self):
        """The removed arm: Edit no longer consults the read log at all."""
        target = self.make_file("unread.md")
        for tool in ("Edit", "MultiEdit"):
            with self.subTest(tool=tool):
                self.assertAllowed(self.gate(tool, target))

    # --- the Write arm still gates -------------------------------------

    def test_write_over_unread_existing_file_is_denied(self):
        target = self.make_file("unread.md")
        reason = self.assertDenied(self.gate("Write", target))
        self.assertIn("without reading it in this session", reason)

    def test_write_to_new_file_is_allowed(self):
        self.assertAllowed(self.gate("Write", self.sandbox / "brand-new.md"))

    def test_read_clears_the_write_gate(self):
        target = self.make_file("read-me.md")
        self.observe_read(target)
        self.assertAllowed(self.gate("Write", target))

    def test_deny_message_names_ctx_read_and_disclaims_serena(self):
        """The old message advertised Serena.getSymbolsOverview, which never
        wrote the log, and omitted ctx_read, which is the mandated reader."""
        reason = self.assertDenied(self.gate("Write", self.make_file("msg.md")))
        self.assertIn("LeanCtx.ctxRead", reason)
        self.assertIn("Serena.getSymbolsOverview does NOT satisfy this gate", reason)

    # --- F2/F3/F4: session scope, exact match, canonicalization ---------

    def test_read_log_is_session_scoped(self):
        target = self.make_file("scoped.md")
        self.observe_read(target)
        other = run_hook(
            PRE_GATE,
            {
                "session_id": self.session_id + "-other",
                "tool_name": "Write",
                "tool_input": {"file_path": str(target)},
            },
        )
        self.assertDenied(other)

    def test_substring_path_does_not_inherit_an_exemption(self):
        """`grep -qF` passed /a/b once /a/b.md was logged; -qxF does not."""
        longer = self.make_file("b.md")
        shorter = self.make_file("b")
        self.observe_read(longer)
        self.assertDenied(self.gate("Write", shorter))

    def test_symlink_alias_shares_one_read_log_entry(self):
        """This is a symlink farm: ~/.claude/hooks/x and
        ~/.dotfiles/.claude/hooks/x are the same file."""
        real = self.make_file("real/target.txt")
        link = self.sandbox / "link"
        link.symlink_to(self.sandbox / "real")
        self.observe_read(link / "target.txt")
        self.assertAllowed(self.gate("Write", real))

    # --- F1: ctx_read parity -------------------------------------------

    def test_ctx_read_clears_the_gate(self):
        target = self.make_file("via-ctx.txt")
        self.assertDenied(self.gate("Write", target))
        self.observe_ctx_read(target)
        self.assertAllowed(self.gate("Write", target))

    def test_ctx_read_alias_tool_names_all_clear_the_gate(self):
        for tool_name in ("ctx_read", "mcp__lean-ctx__ctx_read", "mcp__lean_ctx__ctx_read"):
            with self.subTest(tool_name=tool_name):
                target = self.make_file(f"alias-{tool_name}.txt")
                self.assertDenied(self.gate("Write", target))
                self.observe_ctx_read(target, tool_name=tool_name)
                self.assertAllowed(self.gate("Write", target))

    def test_only_regular_files_are_registered(self):
        self.observe_ctx_read(Path(self.sandbox))
        entries = self.log.read_text().splitlines() if self.log.exists() else []
        self.assertNotIn(str(Path(self.sandbox).resolve()), entries)

    def test_ctx_read_without_a_path_does_not_crash_the_hook(self):
        result = run_hook(
            POST_ANALYTICS,
            {
                "session_id": self.session_id,
                "tool_name": "mcp__lean-ctx__ctx_read",
                "tool_input": {},
            },
        )
        self.assertNotIn("HOOK CRASH", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
