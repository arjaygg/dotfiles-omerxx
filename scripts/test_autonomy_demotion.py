"""Tests for the autonomy demotion writer in .claude/hooks/git-pipeline-gate.sh.

Part VIII of plans/2026-07-27-native-agent-orchestration.md requires demotion to be
mechanical rather than remembered. These tests pin the three properties that keep it
from doing more harm than good:

* ``test_stageless_blocked_entry_does_not_demote`` — orchestrate.js's halt payload has no
  stage field and most of its ``blocked`` emitters are orchestrator infrastructure, so
  inferring a leg would demote one the failure never touched.
* ``test_refusal_does_not_demote`` — a leg that stopped for lack of authorization is not a
  defect. Demoting on it makes an unattended run ratchet its own tier down every time it
  correctly stops to ask, healable only by a human-committed eval report.
* ``test_healed_marker_is_not_recreated`` — pipeline-log.jsonl is append-only, so without a
  watermark a marker removed after committing evidence reappears on the next Stop.
"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GATE = REPO_ROOT / ".claude" / "hooks" / "git-pipeline-gate.sh"
EXPECTED_HOOKS_PATH = str(Path.home() / ".dotfiles" / "git" / "hooks")

PIPELINE_BLOCK = """\
pipeline:
  auto_commit: A2
  auto_push: A2
  auto_pr: A2
  auto_ship: A2
  auto_clean: A2
"""


def git(cwd, *args, check=True):
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise AssertionError(f"git {args} failed: {proc.stderr}")
    return proc


class DemotionWriterTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.repo = Path(self._td.name) / "repo"
        self.repo.mkdir(parents=True)
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "demote-test@example.com")
        git(self.repo, "config", "user.name", "Demote Test")
        (self.repo / "README.md").write_text("init\n")
        git(self.repo, "add", "README.md")
        git(self.repo, "commit", "-q", "-m", "chore: init")
        # Set this AFTER the fixture's own commit: it points at the real dotfiles
        # pre-commit chain (conventional-body check, skill lint, evals), which would
        # otherwise reject the fixture commit above. The gate no-ops unless the repo
        # has opted into this hooks path, so it must be set before running the gate.
        git(self.repo, "config", "core.hooksPath", EXPECTED_HOOKS_PATH)
        (self.repo / ".claude-atomic.yaml").write_text(PIPELINE_BLOCK)
        (self.repo / ".claude").mkdir(exist_ok=True)
        self.log = self.repo / ".claude" / "pipeline-log.jsonl"

    def tearDown(self):
        self._td.cleanup()

    # --- helpers ------------------------------------------------------------------
    def git_common(self) -> Path:
        out = git(self.repo, "rev-parse", "--git-common-dir").stdout.strip()
        p = Path(out)
        return p if p.is_absolute() else (self.repo / p).resolve()

    def marker(self, stage: str) -> Path:
        return self.git_common() / f"autonomy-demoted-{stage}"

    def append_log(self, **entry):
        with self.log.open("a") as fh:
            fh.write(json.dumps(entry) + "\n")

    def run_gate(self):
        proc = subprocess.run(
            ["bash", str(GATE)],
            cwd=str(self.repo),
            input=json.dumps({"stop_hook_active": False}),
            capture_output=True, text=True,
        )
        # The gate must never fail a session, whatever it decides.
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc

    # --- the writer fires on a real per-leg defect --------------------------------
    def test_blocked_leg_with_stage_is_demoted(self):
        self.append_log(ts="2026-07-28T10:00:00Z", status="blocked",
                        stage="auto_ship", condition="stack-ship exited 1")
        self.run_gate()
        m = self.marker("auto_ship")
        self.assertTrue(m.exists(), "a stage-tagged blocked leg must write a marker")
        payload = json.loads(m.read_text())
        self.assertEqual(payload["stage"], "auto_ship")
        self.assertIn("rm this file", payload["heal"])

    def test_marker_lands_in_shared_git_dir_not_per_worktree(self):
        self.append_log(ts="2026-07-28T10:00:00Z", status="blocked",
                        stage="auto_ship", condition="stack-ship exited 1")
        self.run_gate()
        per_worktree = self.repo / ".git" / "worktrees"
        self.assertTrue(self.marker("auto_ship").exists())
        self.assertFalse(per_worktree.exists(),
                         "marker must not be written under a per-worktree gitdir")

    # --- attribution is explicit, never inferred ---------------------------------
    def test_stageless_blocked_entry_does_not_demote(self):
        self.append_log(ts="2026-07-28T10:00:00Z", status="blocked",
                        label="some-spec-label",
                        condition="implement worker returned null (died or was skipped)")
        self.run_gate()
        for stage in ("auto_commit", "auto_push", "auto_pr", "auto_ship", "auto_clean"):
            self.assertFalse(self.marker(stage).exists(),
                             f"{stage} demoted from a stage-less halt")

    def test_unknown_stage_name_does_not_demote(self):
        self.append_log(ts="2026-07-28T10:00:00Z", status="blocked",
                        stage="auto_deploy", condition="whatever")
        self.run_gate()
        self.assertFalse((self.git_common() / "autonomy-demoted-auto_deploy").exists())

    def test_gate_own_block_decision_does_not_demote(self):
        """The gate logs {decision: block} nudges. Those are not leg defects."""
        self.append_log(ts="2026-07-28T10:00:00Z", signal="merge_due",
                        decision="block", reason="CI green -- merge via stack-ship")
        self.run_gate()
        self.assertFalse(self.marker("auto_ship").exists())

    # --- refusals are absent authorization, not defects --------------------------
    def test_refusal_does_not_demote(self):
        for cond in ("needs_confirmation: user must approve the merge",
                     "leg refused: identity assertion unavailable",
                     "degrade-to-confirm on merge_due"):
            with self.subTest(cond=cond):
                self.log.write_text("")
                for stage in ("auto_ship", "auto_clean"):
                    self.marker(stage).unlink(missing_ok=True)
                (self.git_common() / "autonomy-demote-watermark").unlink(missing_ok=True)
                self.append_log(ts="2026-07-28T10:00:00Z", status="blocked",
                                stage="auto_ship", condition=cond)
                self.run_gate()
                self.assertFalse(self.marker("auto_ship").exists(),
                                 f"demoted on an authorization stop: {cond}")

    # --- the watermark makes healing permanent -----------------------------------
    def test_healed_marker_is_not_recreated(self):
        self.append_log(ts="2026-07-28T10:00:00Z", status="blocked",
                        stage="auto_ship", condition="stack-ship exited 1")
        self.run_gate()
        m = self.marker("auto_ship")
        self.assertTrue(m.exists())

        # Human commits evidence and clears the marker. The log entry remains forever.
        m.unlink()
        self.run_gate()
        self.assertFalse(m.exists(),
                         "append-only log re-created a healed marker (watermark not honoured)")

    def test_new_defect_after_healing_demotes_again(self):
        self.append_log(ts="2026-07-28T10:00:00Z", status="blocked",
                        stage="auto_ship", condition="stack-ship exited 1")
        self.run_gate()
        self.marker("auto_ship").unlink()

        self.append_log(ts="2026-07-28T11:00:00Z", status="blocked",
                        stage="auto_ship", condition="stack-ship exited 1 again")
        self.run_gate()
        self.assertTrue(self.marker("auto_ship").exists(),
                        "a genuinely new defect after healing must demote again")

    # --- robustness ---------------------------------------------------------------
    def test_malformed_log_lines_are_skipped(self):
        with self.log.open("a") as fh:
            fh.write("not json at all\n")
            fh.write('{"truncated": \n')
        self.append_log(ts="2026-07-28T10:00:00Z", status="blocked",
                        stage="auto_ship", condition="stack-ship exited 1")
        self.run_gate()
        self.assertTrue(self.marker("auto_ship").exists(),
                        "a malformed line must not stop later entries being processed")

    def test_absent_log_is_not_an_error(self):
        self.assertFalse(self.log.exists())
        self.run_gate()

    def test_done_status_never_demotes(self):
        self.append_log(ts="2026-07-28T10:00:00Z", status="done", stage="auto_ship",
                        condition="")
        self.run_gate()
        self.assertFalse(self.marker("auto_ship").exists())


if __name__ == "__main__":
    unittest.main()
