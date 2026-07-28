"""Static gates for .claude/workflows/orchestrate.js (Goal 05 Steps 14 and 15).

The live check is `Workflow({scriptPath, args:{dryRun:true, ...}})`, which cannot run from
Python — the acceptance fixtures are driven entirely through `args` and their results are
recorded in the PR body. These tests pin the invariants that make those runs safe and
repeatable: the pre-tool-gate SECTION 8 fan-out cap, the meta literal, schema+label on every
subagent call, null guards, reviewer input isolation, logged caps, the absence of any
backgrounding construct, and — for Step 15 — the finding contract, the triage taxonomy with its
scope-authority rule, the three persisted loop bounds, and the HALT paths.
"""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".claude/workflows/orchestrate.js"
SCHEMAS = ROOT / "ai/skills/cap/references/schemas.md"
AUTO_SHIP = ROOT / "ai/skills/auto-ship/SKILL.md"
GATE = ROOT / ".claude/hooks/pre-tool-gate-v2.sh"

# Same regex pre-tool-gate-v2.sh SECTION 8 uses to count literal subagent call sites.
AGENT_CALL_RE = re.compile(r"(^|[^A-Za-z0-9_])agent\s*\(")
MAX_AGENT_CALL_SITES = 3

# The plan's §20 finding contract. These names are shared by orchestrate.js's FINDING_SCHEMA
# and schemas.md's REVIEW_SCHEMA; the two must not drift apart.
FINDING_FIELDS = ("lens", "location", "trigger_condition", "guard_snippet", "potential_consequence")

# §23 taxonomy and §24 bounds.
CATEGORIES = ("intent_gap", "bad_spec", "patch", "defer", "reject")
BOUNDS = {"retry_count": 3, "doubt_cycle_iteration": 3, "review_loop_iteration": 5}


class OrchestrateWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SCRIPT.read_text(encoding="utf-8")
        cls.code = "\n".join(
            line for line in cls.text.splitlines() if not line.lstrip().startswith("//")
        )

    # ----------------------------------------------------------- Step 14 invariants

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
        self.assertEqual(declared, sorted(set(called), key=called.index))

    def test_every_subagent_call_passes_schema_and_label(self):
        for line in self.text.splitlines():
            if AGENT_CALL_RE.search(line):
                self.assertIn("schema:", line, f"no schema on: {line.strip()}")
                self.assertIn("label:", line, f"no label on: {line.strip()}")

    def test_every_stage_result_is_null_guarded(self):
        for name in ("impl", "review", "triage", "accept"):
            self.assertIn(f"if (!{name})", self.text, f"{name} result is not null-guarded")

    def test_reviewer_gets_artifact_and_contract_only(self):
        block = self.text.split("phase('Review')", 1)[1].split("phase('Triage')", 1)[0]
        self.assertIn("ARTIFACT", block)
        self.assertIn("CONTRACT", block)
        self.assertIn("lensed-review", block)
        # The worker's claim of validity must never reach the reviewer (plan §21).
        self.assertNotIn("impl.summary", block)
        self.assertNotIn("impl.valid", block)
        self.assertNotIn("impl.issues", block)

    def test_review_logic_is_delegated_not_embedded(self):
        self.assertIn("Do not embed your own", self.text)

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
        for stage in ("implement", "review", "triage", "halt"):
            self.assertIn(f"stage === '{stage}'", self.text)
        # Fixture keys must cover each schema's required list.
        for required in re.findall(r"required: \[([^\]]+)\]", self.text):
            for key in re.findall(r"'([^']+)'", required):
                self.assertIn(f"{key}:", self.text, f"no fixture field for required key {key}")

    def test_no_backgrounding_constructs(self):
        # The acceptance criterion greps the whole file, so these tokens must not appear even
        # in a comment that disclaims them.
        for forbidden in ("run_in_background", "detached", "ScheduleWakeup", "CronCreate"):
            self.assertNotIn(forbidden, self.text, f"{forbidden} is forbidden on unattended paths")

    # ----------------------------------------------------- §20 the finding contract

    def test_finding_schema_uses_the_plan_field_names(self):
        block = self.text.split("const FINDING_SCHEMA", 1)[1].split("const REVIEW_SCHEMA", 1)[0]
        for field in FINDING_FIELDS:
            self.assertIn(field, block, f"FINDING_SCHEMA is missing §20 field {field}")
        # The pre-Step-15 shape must be gone, or schemas.md and this file have drifted.
        for stale in ("description:", "fix:"):
            self.assertNotIn(stale, block, f"stale pre-§20 field {stale} still in FINDING_SCHEMA")

    def test_schemas_md_matches_the_same_contract(self):
        text = SCHEMAS.read_text(encoding="utf-8")
        block = text.split("## REVIEW_SCHEMA", 1)[1].split("## VERDICT_SCHEMA", 1)[0]
        for field in FINDING_FIELDS:
            self.assertIn(field, block, f"schemas.md REVIEW_SCHEMA is missing §20 field {field}")

    def test_no_finding_level_severity_anywhere(self):
        # Already true before Step 15 (Step 10 removed it) — this pins it so it stays true.
        block = (
            SCHEMAS.read_text(encoding="utf-8")
            .split("## REVIEW_SCHEMA", 1)[1]
            .split("## VERDICT_SCHEMA", 1)[0]
        )
        self.assertNotIn('"severity"', block)
        finding_block = self.text.split("const FINDING_SCHEMA", 1)[1].split(
            "const REVIEW_SCHEMA", 1
        )[0]
        self.assertNotIn("severity", finding_block)

    def test_dedupe_requires_same_claim_and_same_action(self):
        block = self.text.split("function dedupe", 1)[1].split("\n}", 1)[0]
        self.assertIn("trigger_condition", block)
        self.assertIn("guard_snippet", block)

    # ---------------------------------------------------------- §23 triage taxonomy

    def test_all_five_categories_present(self):
        for category in CATEGORIES:
            self.assertIn(f"'{category}'", self.text, f"category {category} missing")

    def test_scope_authority_rule_rejects_inadmissible_authorities(self):
        block = self.text.split("function enforceScopeAuthority", 1)[1].split("\n}", 1)[0]
        # Only the intent itself may justify an out-of-scope defer/reject.
        self.assertIn("authority === 'intent'", block)
        # Anything else is rerouted, and a silent intent escalates to intent_gap.
        self.assertIn("intent_gap", block)
        self.assertIn("bad_spec", block)
        self.assertRegex(block, r"log\(")

    def test_tie_breakers_prefer_bad_spec_and_reject(self):
        block = self.text.split("function applyTieBreakers", 1)[1].split("\nfunction ", 1)[0]
        self.assertIn("preferring bad_spec", block)
        self.assertIn("preferring reject", block)

    def test_cascade_moots_lower_categories(self):
        block = self.text.split("function applyCascade", 1)[1].split("\nfunction ", 1)[0]
        self.assertIn("intent_gap", block)
        self.assertIn("bad_spec", block)
        self.assertIn("moot", block)

    # ------------------------------------------------------------- §24 loop bounds

    def test_all_three_bounds_declared_at_the_plan_values(self):
        block = self.text.split("const BOUNDS =", 1)[1].split("\n", 1)[0]
        for counter, bound in BOUNDS.items():
            self.assertRegex(
                block,
                rf"{counter}:\s*{bound}\b",
                f"{counter} must be bounded at {bound} — raising a bound is the §24 failure mode",
            )

    def test_counters_are_read_from_frontmatter_not_initialised(self):
        block = self.text.split("const counters =", 1)[1].split("\n}", 1)[0]
        for counter in BOUNDS:
            self.assertIn(f"fm.{counter}", block, f"{counter} must come from spec frontmatter")

    def test_non_convergence_condition_is_worded_for_the_fixture(self):
        self.assertIn("(non-convergence)", self.text)
        self.assertIn("review repair loop exceeded", self.text)

    def test_worker_outcome_states_increment_retry_count(self):
        # A null or empty return is a failure, not a success.
        self.assertGreaterEqual(self.code.count("counters.retry_count += 1"), 3)

    def test_triage_log_records_counts_and_addressed_findings(self):
        block = self.text.split("ctx.triageLog = {", 1)[1].split("\n  }", 1)[0]
        for key in ("counts:", "by_severity:", "addressed_findings:"):
            self.assertIn(key, block)
        # A pass that fixed nothing must be visibly a pass that fixed nothing.
        self.assertIn("'none'", self.text)

    # --------------------------------------------------------------- §25 follow-up

    def test_followup_signal_is_computed_from_patch_findings_only(self):
        block = self.text.split("function followupSignal", 1)[1].split("\n}", 1)[0]
        self.assertIn("r.category === 'patch'", block)
        self.assertIn("3 * counts.medium + counts.low", block)
        self.assertIn(">= 5", block)
        for excluded in ("defer", "reject"):
            self.assertNotIn(excluded, block, f"{excluded} findings must not feed the signal")

    # -------------------------------------------------------------------- §15 HALT

    def test_halt_paths_are_deterministic_per_degenerate_case(self):
        block = self.text.split("function haltPathFor", 1)[1].split("\n}", 1)[0]
        self.assertIn("-unresolved.md", block)
        self.assertIn("-ambiguous.md", block)

    def test_terminal_status_carries_the_minimum_payload(self):
        block = self.text.split("async function halt(", 1)[1].split("\n}", 1)[0]
        for key in ("status,", "condition,", "artifact:"):
            self.assertIn(key, block, f"HALT payload is missing {key}")

    def test_unpersisted_done_is_not_reported_as_ok(self):
        block = self.text.split("async function halt(", 1)[1].split("\n}", 1)[0]
        self.assertIn("status === 'done' && terminal.written", block)

    def test_every_exit_path_goes_through_halt(self):
        # Only `main()`'s own returns and the top-level dispatch may return; each must halt.
        body = self.code.split("async function main()", 1)[1]
        for match in re.finditer(r"^\s*return (?!halt\()(?!\{$)", body, re.MULTILINE):
            line = body[match.start() : body.index("\n", match.start())].strip()
            self.assertIn("halt(", line, f"exit path bypasses HALT: {line}")

    def test_a_thrown_stage_actually_writes_a_terminal_status(self):
        """Regression: the previous version of this test asserted only that `} finally {` and
        the NO-TERMINAL-STATUS log line existed. Both were present while the `finally` block
        merely *logged* — so a thrown stage left no artifact at all, and the source comment
        claiming try/finally guaranteed the write was false. Assert the write, not the shape.
        """
        self.assertIn("} catch (err) {", self.code, "no catch block: a throw cannot be handled")

        start = self.code.index("} catch (err) {")
        end = self.code.index("} finally {", start)
        catch_body = self.code[start:end]

        self.assertIn("halt(", catch_body,
                      "catch block must WRITE a terminal status, not just log about its absence")
        self.assertIn("throw err", catch_body,
                      "the original failure must still propagate — never swallowed by recovery")
        # The recovery write must not be able to mask the original error.
        self.assertIn("HALT WRITE THREW", catch_body)
        # `finally` stays as the last-resort log.
        self.assertIn("NO TERMINAL STATUS WRITTEN", self.text)

    def test_the_false_try_finally_guarantee_is_not_reinstated(self):
        self.assertNotIn(
            "try/finally guarantees a terminal write",
            self.text,
            "this claim was false: the finally block only logged. Do not restore it.",
        )

    def test_the_sigkill_detector_has_a_producer(self):
        """§15 documents killed runs being detected by a spec still marked `running` with no
        terminal status. Nothing ever wrote `running` — TEMPLATE.md ships `status: draft` — so
        the detector had no producer and an in-flight run looked like a never-started one.
        """
        self.assertIn("async function markRunning(", self.code)
        self.assertIn("status: running", self.text,
                      "markRunning must actually set `status: running`")
        # Called on the healthy path only: the bound-exceeded / bad-spec branches halt without
        # ever starting, so marking those `running` would invent an in-flight run.
        main_start = self.code.index("async function main() {")
        self.assertIn("await markRunning(specPath, ctx)", self.code[main_start:])
        # Dry runs must not spawn a subagent for it.
        self.assertIn("stage === 'mark_running'", self.code,
                      "mark_running needs a dry-run fixture branch")

    # ------------------------------------------------------------------- auto-ship

    def test_auto_ship_reuses_the_halt_definition_without_restating_it(self):
        text = AUTO_SHIP.read_text(encoding="utf-8")
        self.assertIn("## Terminal Status (HALT)", text)
        self.assertIn("§15", text)
        # One log, not a second one.
        self.assertIn(".claude/pipeline-log.jsonl", text)
        self.assertIn("Do not create a second", text)
        self.assertIn("-unresolved.md", text)
        self.assertIn("-ambiguous.md", text)


if __name__ == "__main__":
    unittest.main()
