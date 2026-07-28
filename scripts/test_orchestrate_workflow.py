"""Static gates for .claude/workflows/orchestrate.js (Goal 05 Step 14).

The live check is `Workflow({scriptPath, args:{dryRun:true}})`, which cannot run from
Python. These tests pin the invariants that make that run safe and repeatable: the
pre-tool-gate SECTION 8 fan-out cap, the meta literal, schema+label on every subagent
call, null guards, reviewer input isolation, logged caps, and the absence of any
unattended-mode construct (Step 15's scope).
"""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".claude/workflows/orchestrate.js"
GATE = ROOT / ".claude/hooks/pre-tool-gate-v2.sh"

# Same regex pre-tool-gate-v2.sh SECTION 8 uses to count literal subagent call sites.
AGENT_CALL_RE = re.compile(r"(^|[^A-Za-z0-9_])agent\s*\(")
MAX_AGENT_CALL_SITES = 3


class OrchestrateWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SCRIPT.read_text(encoding="utf-8")

    def test_script_exists(self):
        self.assertTrue(SCRIPT.is_file(), f"missing {SCRIPT}")

    def test_agent_call_sites_within_hard_cap(self):
        count = len(AGENT_CALL_RE.findall(self.text))
        self.assertLessEqual(
            count,
            MAX_AGENT_CALL_SITES,
            f"{count} literal agent call sites; SECTION 8 hard-denies more than "
            f"{MAX_AGENT_CALL_SITES} (its regex counts comments too)",
        )

    def test_hard_cap_matches_the_gate_script(self):
        # Guard against the hook's threshold drifting away from this test's constant.
        self.assertIn("literal agent( count > 3", GATE.read_text(encoding="utf-8"))

    def test_meta_is_a_pure_literal_with_required_keys(self):
        head = self.text.split("\n// Goal 05", 1)[0]
        self.assertTrue(head.startswith("export const meta = {"))
        for key in ("name:", "description:", "phases:"):
            self.assertIn(key, head)
        # No variables, calls, spreads, or interpolation inside the literal.
        self.assertNotIn("...", head)
        self.assertNotIn("${", head)
        self.assertNotIn("`", head)
        self.assertIsNone(
            re.search(r"[A-Za-z_][A-Za-z0-9_]*\s*\(", head),
            "meta must be a pure literal — no function calls",
        )

    def test_meta_phases_match_phase_calls(self):
        declared = re.findall(r"title:\s*'([^']+)'", self.text)
        called = re.findall(r"phase\('([^']+)'\)", self.text)
        self.assertEqual(declared, called)

    def test_every_subagent_call_passes_schema_and_label(self):
        for line in self.text.splitlines():
            if AGENT_CALL_RE.search(line):
                self.assertIn("schema:", line, f"no schema on: {line.strip()}")
                self.assertIn("label:", line, f"no label on: {line.strip()}")

    def test_every_stage_result_is_null_guarded(self):
        for name in ("impl", "review", "accept"):
            self.assertIn(f"if (!{name})", self.text, f"{name} result is not null-guarded")

    def test_reviewer_gets_artifact_and_contract_only(self):
        review_block = self.text.split("phase('Review')", 1)[1].split("phase('Accept')", 1)[0]
        self.assertIn("ARTIFACT", review_block)
        self.assertIn("CONTRACT", review_block)
        self.assertIn("lensed-review", review_block)
        # The worker's claim of validity must never reach the reviewer (plan §21).
        self.assertNotIn("impl.summary", review_block)
        self.assertNotIn("impl.valid", review_block)
        self.assertNotIn("impl.issues", review_block)

    def test_review_logic_is_delegated_not_embedded(self):
        self.assertIn("Do not embed your own review", self.text)

    def test_definition_of_done_path_is_read_and_absence_is_logged(self):
        self.assertIn("ai/references/definition-of-done.md", self.text)
        self.assertTrue((ROOT / "ai/references/definition-of-done.md").is_file())
        self.assertIn("if (!accept.dodFound)", self.text)
        self.assertRegex(self.text, r"log\(`Definition of Done not found")

    def test_every_truncation_is_logged(self):
        for match in re.finditer(r"\.slice\(", self.text):
            window = self.text[max(0, match.start() - 600) : match.start()]
            self.assertIn("CAP APPLIED", window, "a slice() cap is applied without a log()")

    def test_dry_run_stubs_every_stage_with_schema_shaped_fixtures(self):
        self.assertIn("args.dryRun", self.text)
        self.assertIn("if (opts.dryRun)", self.text)
        for stage in ("implement", "review"):
            self.assertIn(f"stage === '{stage}'", self.text)
        # Fixture keys must cover each schema's required list.
        for required in re.findall(r"required: \[([^\]]+)\]", self.text):
            for key in re.findall(r"'([^']+)'", required):
                self.assertIn(f"{key}:", self.text, f"no fixture field for required key {key}")

    def test_no_unattended_mode_code(self):
        # Comments are stripped: the header names Step 15's constructs in order to
        # disclaim them, which is the opposite of implementing them.
        code = "\n".join(
            line for line in self.text.splitlines() if not line.lstrip().startswith("//")
        )
        for forbidden in ("run_in_background", "HALT", "detached", "ScheduleWakeup", "CronCreate"):
            self.assertNotIn(forbidden, code, f"{forbidden} is Step 15's scope")


if __name__ == "__main__":
    unittest.main()
