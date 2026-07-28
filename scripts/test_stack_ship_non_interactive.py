"""Tests for stack-ship.sh's confirmation handling.

The confirmation was a bare `read -p`, which blocks forever without a TTY. Every
non-interactive caller therefore hung: `auto-ship`, cron, and any agent run. It printed the merge
plan and then sat there with no indication why — found by hanging on it
(plans/2026-07-28-harness-end-to-end-proof.md).

The fix is deliberately *not* "always skip the prompt". That prompt is the **A2 checkpoint** for an
irreversible action, and Part VIII caps `auto_ship`/`auto_clean` at A2, so bypassing it unattended
would put the leg above its own cap. `--yes` is for a run a human already authorised out-of-band,
which is why it demands `--reason` and records it in the audit log.
"""
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".claude/scripts/stack-ship.sh"
AUTO_SHIP = ROOT / "ai/skills/auto-ship/SKILL.md"


class StackShipConfirmationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code = SCRIPT.read_text(encoding="utf-8")

    def test_script_parses(self):
        r = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_yes_flag_exists_and_is_opt_in(self):
        self.assertIn("--yes|-y)", self.code)
        self.assertIn("ASSUME_YES=0", self.code, "must default to requiring confirmation")

    def test_yes_requires_a_reason(self):
        """A bypass of an irreversible-action checkpoint must be attributable.

        Anchored on the confirmation block specifically — `ASSUME_YES` also appears later in the
        audit-logging block, and matching the first occurrence tests the wrong code.
        """
        idx = self.code.index("This will execute the merge plan above")
        window = self.code[idx:idx + 1400]
        self.assertIn('-z "$YES_REASON"', window,
                      "the confirmation block must require --reason when --yes is given")
        self.assertIn("exit 1", window, "missing --reason must fail, not proceed")

    def test_no_tty_fails_loudly_instead_of_hanging(self):
        """The original defect: a read with no TTY blocks forever."""
        idx = self.code.index('elif [[ ! -t 0 ]]')
        window = self.code[idx:idx + 700]
        self.assertIn("No TTY", window)
        self.assertIn("exit 1", window)

    def test_the_interactive_prompt_is_still_the_default_path(self):
        self.assertIn('read -p "Continue? (y/n) "', self.code,
                      "the prompt must remain for interactive runs — it is the A2 checkpoint")

    def test_a_bypass_is_recorded_in_the_audit_log(self):
        self.assertIn("confirmed_by", self.code)
        self.assertIn("bypass_reason", self.code)
        idx = self.code.index("confirmed_by=")
        self.assertIn('"prompt"', self.code[idx:idx + 200],
                      "a normal confirmed merge must be distinguishable from a bypass")

    def test_auto_ship_is_told_never_to_pass_yes(self):
        """auto_ship is capped at A2; --yes would take it above its own cap."""
        text = AUTO_SHIP.read_text(encoding="utf-8")
        self.assertIn("--yes", text, "auto-ship must explicitly address the flag")
        self.assertRegex(
            text,
            r"(?i)(never|must\s+not)\s+pass\s+`?--yes`?",
            "auto-ship needs an explicit prohibition, not just a mention",
        )
        # And it must say WHY, so the rule survives someone deciding it looks inconvenient.
        self.assertIn("A2 checkpoint", text)

    def test_no_admin_merge_anywhere(self):
        self.assertNotIn("--admin", self.code)


class ParentBranchLabelTests(unittest.TestCase):
    """The dry-run merge plan printed `→ origin` instead of `→ main`.

    Cosmetic — the real merge takes its base from the PR, so nothing merged to the wrong place —
    but a dry-run whose entire purpose is to show the plan before an irreversible action must not
    mislabel the target.
    """

    @classmethod
    def setUpClass(cls):
        cls.code = SCRIPT.read_text(encoding="utf-8")

    def test_parent_comes_from_the_pr_base_not_a_ref_scan(self):
        self.assertIn("baseRefName", self.code,
                      "the merge target must be read from the PR, which is what gh pr merge uses")
        # The old implementation guessed by matching a merge-base SHA against every remote ref,
        # which is how "origin" ended up printed as the target.
        self.assertNotIn("git branch -r --format='%(refname:short)'", self.code,
                         "remote-ref scanning is what produced the mislabelled target")

    def test_the_printed_plan_uses_the_resolved_parent(self):
        self.assertIn('echo "  1. Merge $TARGET_BRANCH → $parent"', self.code)


if __name__ == "__main__":
    unittest.main()
