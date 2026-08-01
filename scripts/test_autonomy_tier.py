"""Fixture-based tests for scripts/ai/autonomy-tier.sh.

Builds throwaway git repos (no network I/O) and asserts the resolver's authorization
properties per plans/2026-07-27-native-agent-orchestration.md Part VIII and Step 18.

Each test names the property it pins. The two that matter most:

* ``test_staged_but_uncommitted_report_grants_nothing`` — `git ls-files --error-unmatch`
  succeeds on a merely *staged* file, so using it as the "committed" check would let
  `git add` alone buy a promotion. Asserts the resolver uses `git cat-file -e HEAD:`.
* ``test_declared_above_hard_cap_is_refused_not_clamped`` — an irreversible leg declaring
  above A2 is a config error that fails closed, not something silently corrected.
"""
import json
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

RESOLVER = Path(__file__).resolve().parent / "ai" / "autonomy-tier.sh"

BASE_PIPELINE = """\
  auto_stack: A2
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


def init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "autonomy-test@example.com")
    git(path, "config", "user.name", "Autonomy Test")
    (path / "README.md").write_text("init\n")
    git(path, "add", "README.md")
    git(path, "commit", "-q", "-m", "chore: init")
    return path


def write_config(repo: Path, pipeline: str = BASE_PIPELINE, override: str | None = None):
    body = f"pipeline:\n{pipeline}"
    if override is not None:
        # Normalise to exactly two spaces of indent. The resolver scopes keys to their
        # top-level block, so a fully-dedented body would (correctly) parse as
        # top-level keys and be ignored.
        lines = textwrap.dedent(override).strip("\n").splitlines()
        if not any(line.strip().startswith("decision:") for line in lines):
            lines.append("decision: hermetic test approval")
        block = "".join(f"  {line.strip()}\n" for line in lines if line.strip())
        body += f"autonomy_override:\n{block}"
    (repo / ".claude-atomic.yaml").write_text(body)


def resolve(repo: Path, stage: str):
    """Returns (exit_code, parsed_json_or_None, stderr)."""
    proc = subprocess.run(
        [str(RESOLVER), "--stage", stage, "--json"],
        cwd=str(repo), capture_output=True, text=True,
    )
    payload = None
    if proc.returncode == 0 and proc.stdout.strip():
        payload = json.loads(proc.stdout.strip())
    return proc.returncode, payload, proc.stderr


class AutonomyTierTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.repo = init_repo(Path(self._td.name) / "repo")

    def tearDown(self):
        self._td.cleanup()

    # --- C1: tier vocabulary, and refusing the pre-Step-18 boolean form -----------
    def test_legacy_boolean_is_refused(self):
        write_config(self.repo, pipeline="  auto_commit: true\n" + BASE_PIPELINE[BASE_PIPELINE.index("  auto_push"):])
        code, _, err = resolve(self.repo, "auto_commit")
        self.assertEqual(code, 3, f"expected config error, got {code}: {err}")
        self.assertIn("legacy boolean", err)

    def test_unparseable_tier_is_refused(self):
        write_config(self.repo, pipeline="  auto_commit: A9\n" + BASE_PIPELINE[BASE_PIPELINE.index("  auto_push"):])
        code, _, err = resolve(self.repo, "auto_commit")
        self.assertEqual(code, 3)
        self.assertIn("unparseable tier", err)

    def test_absent_key_defaults_to_a0(self):
        write_config(self.repo, pipeline="  auto_push: A2\n  auto_pr: A2\n  auto_ship: A2\n  auto_clean: A2\n")
        code, out, err = resolve(self.repo, "auto_commit")
        self.assertEqual(code, 0, err)
        self.assertEqual(out["declared"], "A0")

    def test_keys_are_scoped_to_the_pipeline_block(self):
        """An auto_* key under another block must not be picked up as a declaration."""
        cfg = (
            "subsystems:\n  ai-config:\n    - \"ai/\"\n"
            "validation:\n  auto_commit: A4\n"      # decoy in the wrong block
            f"pipeline:\n{BASE_PIPELINE}"
        )
        (self.repo / ".claude-atomic.yaml").write_text(cfg)
        code, out, err = resolve(self.repo, "auto_commit")
        self.assertEqual(code, 0, err)
        self.assertEqual(out["declared"], "A2", "decoy key in validation: block leaked through")

    # --- C5: the hard cap fails closed rather than clamping ----------------------
    def test_declared_above_hard_cap_is_refused_not_clamped(self):
        write_config(self.repo, pipeline=BASE_PIPELINE.replace("auto_ship: A2", "auto_ship: A3"))
        code, _, err = resolve(self.repo, "auto_ship")
        self.assertEqual(code, 3, "an irreversible leg above A2 must fail closed")
        self.assertIn("capped at A2", err)

    def test_reversible_leg_may_exceed_a2(self):
        write_config(self.repo, pipeline=BASE_PIPELINE.replace("auto_push: A2", "auto_push: A4"))
        code, out, err = resolve(self.repo, "auto_push")
        self.assertEqual(code, 0, err)
        self.assertEqual(out["hard_cap"], "A4")

    def test_auto_stack_is_a_first_class_reversible_stage(self):
        write_config(self.repo, override="""\
              tier: A2
              basis: risk-accepted
              stages: auto_stack
              expires: 2099-01-01
              signed_off_by: test
            """)
        code, out, err = resolve(self.repo, "auto_stack")
        self.assertEqual(code, 0, err)
        self.assertEqual(out["hard_cap"], "A4")
        self.assertEqual(out["effective"], "A2")

    # --- C3: promotion requires a COMMITTED green eval run -----------------------
    def test_staged_but_uncommitted_report_grants_nothing(self):
        write_config(self.repo)
        reports = self.repo / "evals" / "reports"
        reports.mkdir(parents=True)
        (reports / "auto_commit.json").write_text('{"green": true, "tier": "A4"}\n')
        git(self.repo, "add", "evals/reports/auto_commit.json")

        # Precondition: the naive check would pass here, which is the whole point.
        naive = git(self.repo, "ls-files", "--error-unmatch",
                    "evals/reports/auto_commit.json", check=False)
        self.assertEqual(naive.returncode, 0, "fixture invalid: file should be staged/tracked")

        code, out, err = resolve(self.repo, "auto_commit")
        self.assertEqual(code, 0, err)
        self.assertEqual(out["evidence_tier"], "A0",
                         "a staged-but-uncommitted report must not buy a promotion")

    def test_committed_green_report_grants_evidence(self):
        write_config(self.repo)
        reports = self.repo / "evals" / "reports"
        reports.mkdir(parents=True)
        (reports / "auto_commit.json").write_text('{"green": true, "tier": "A4"}\n')
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "test: add green report")
        code, out, err = resolve(self.repo, "auto_commit")
        self.assertEqual(code, 0, err)
        self.assertEqual(out["evidence_tier"], "A4")
        # declared is a ceiling: evidence above it does not raise the effective tier.
        self.assertEqual(out["effective"], "A2")

    def test_committed_report_that_is_not_green_grants_nothing(self):
        write_config(self.repo)
        reports = self.repo / "evals" / "reports"
        reports.mkdir(parents=True)
        (reports / "auto_commit.json").write_text('{"green": false, "tier": "A4"}\n')
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "test: add red report")
        code, out, err = resolve(self.repo, "auto_commit")
        self.assertEqual(code, 0, err)
        self.assertEqual(out["evidence_tier"], "A0")

    # --- C6: the risk-acceptance override is separate, capped, and enforced ------
    def test_override_is_not_evidence(self):
        write_config(self.repo, override="""\
              tier: A2
              basis: risk-accepted
              stages: auto_commit
              expires: 2099-01-01
              signed_off_by: test
            """)
        code, out, err = resolve(self.repo, "auto_commit")
        self.assertEqual(code, 0, err)
        self.assertEqual(out["override_tier"], "A2")
        self.assertEqual(out["evidence_tier"], "A0",
                         "risk-acceptance must never be reported as evidence")
        self.assertEqual(out["effective"], "A2")

    def test_expired_override_grants_nothing(self):
        write_config(self.repo, override="""\
              tier: A2
              basis: risk-accepted
              stages: auto_commit
              expires: 2020-01-01
              signed_off_by: test
            """)
        code, out, err = resolve(self.repo, "auto_commit")
        self.assertEqual(code, 3)
        self.assertIsNone(out)
        self.assertIn("expired", err.lower())

    def test_override_refused_for_irreversible_leg(self):
        write_config(self.repo, override="""\
              tier: A2
              basis: risk-accepted
              stages: auto_commit auto_ship
              expires: 2099-01-01
              signed_off_by: test
            """)
        code, out, err = resolve(self.repo, "auto_ship")
        self.assertEqual(code, 0, err)
        self.assertEqual(out["override_tier"], "A0")
        self.assertIn("irreversible", out["override_basis"])

    # --- C4: demotion lowers exactly one tier, from the SHARED git dir -----------
    def test_demotion_marker_drops_exactly_one_tier(self):
        write_config(self.repo, override="""\
              tier: A2
              basis: risk-accepted
              stages: auto_commit
              expires: 2099-01-01
              signed_off_by: test
            """)
        code, out, _ = resolve(self.repo, "auto_commit")
        self.assertEqual(out["effective"], "A2")

        Path(out["marker"]).touch()
        code, out, err = resolve(self.repo, "auto_commit")
        self.assertEqual(code, 0, err)
        self.assertTrue(out["demoted"])
        self.assertEqual(out["effective"], "A1")

    def test_demotion_marker_is_shared_across_worktrees(self):
        """--git-dir would make markers per-worktree, so `stack create` would launder
        every demotion. The marker must live in the shared --git-common-dir."""
        write_config(self.repo)
        _, main_out, _ = resolve(self.repo, "auto_ship")

        wt = Path(self._td.name) / "linked"
        git(self.repo, "worktree", "add", "-q", "-b", "feature/x", str(wt))
        write_config(wt)
        _, wt_out, err = resolve(wt, "auto_ship")
        self.assertIsNotNone(wt_out, err)
        self.assertEqual(main_out["marker"], wt_out["marker"],
                         "demotion marker must be shared, not per-worktree")

    def test_demotion_cannot_go_below_a0(self):
        write_config(self.repo, pipeline=BASE_PIPELINE.replace("auto_commit: A2", "auto_commit: A0"))
        code, out, _ = resolve(self.repo, "auto_commit")
        Path(out["marker"]).touch()
        code, out, err = resolve(self.repo, "auto_commit")
        self.assertEqual(code, 0, err)
        self.assertEqual(out["effective"], "A0")

    # --- usage / environment ------------------------------------------------------
    def test_malformed_duplicate_unsigned_and_invalid_basis_overrides_are_rejected(self):
        valid_override = """autonomy_override:
  tier: A2
  basis: risk-accepted
  stages: auto_commit
  expires: 2099-01-01
  signed_off_by: reviewer
  decision: approved risk basis
"""
        cases = {
            "duplicate-block": f"pipeline:\n{BASE_PIPELINE}pipeline:\n{BASE_PIPELINE}",
            "duplicate-key": f"pipeline:\n{BASE_PIPELINE}  auto_commit: A2\n",
            "incomplete": f"pipeline:\n{BASE_PIPELINE}autonomy_override:\n  tier: A2\n",
            "malformed-expiry": f"pipeline:\n{BASE_PIPELINE}" + valid_override.replace("2099-01-01", "not-a-date"),
            "unsigned": f"pipeline:\n{BASE_PIPELINE}" + valid_override.replace("reviewer", "!unsigned"),
            "unknown-stage": f"pipeline:\n{BASE_PIPELINE}" + valid_override.replace("auto_commit", "auto_unknown"),
            "invalid-basis": f"pipeline:\n{BASE_PIPELINE}" + valid_override.replace("risk-accepted", "self-approved"),
            "invalid-decision": f"pipeline:\n{BASE_PIPELINE}" + valid_override.replace("approved risk basis", "x"),
        }
        for name, config in cases.items():
            with self.subTest(name=name):
                (self.repo / ".claude-atomic.yaml").write_text(config)
                code, output, error = resolve(self.repo, "auto_commit")
                self.assertEqual(code, 3, f"{name} unexpectedly passed: {error}")
                self.assertIsNone(output)

    def test_unknown_stage_is_rejected(self):
        write_config(self.repo)
        code, _, err = resolve(self.repo, "auto_nope")
        self.assertEqual(code, 2)
        self.assertIn("unknown stage", err)

    def test_missing_config_is_an_error_not_a_default(self):
        code, _, err = resolve(self.repo, "auto_commit")
        self.assertEqual(code, 4, "absent config must fail, never silently permit")

    def test_all_stages_emit_valid_json(self):
        write_config(self.repo)
        proc = subprocess.run([str(RESOLVER), "--all", "--json"],
                              cwd=str(self.repo), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rows = json.loads(proc.stdout)
        self.assertEqual(len(rows), 6)
        self.assertEqual({r["stage"] for r in rows},
                         {"auto_stack", "auto_commit", "auto_push", "auto_pr", "auto_ship", "auto_clean"})


if __name__ == "__main__":
    unittest.main()
