import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ai-policy-validation.yml"


class AiPolicyWorkflowTests(unittest.TestCase):
    def test_workflow_runs_maintained_policy_checks(self):
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("name: ai-policy-validation", text)
        self.assertIn("python3 -m unittest discover -s scripts -p 'test_*.py'", text)
        self.assertIn("scripts/hook_fixture_runner.py", text)
        self.assertIn(".claude/hooks/pre-tool-gate-v2.sh", text)
        self.assertIn("scripts/fixtures/pretool-gate-v2.json", text)
        self.assertIn("scripts/hook_config_check.py", text)
        self.assertIn("scripts/fixtures/hook-config-baseline.json", text)
        self.assertIn("scripts/shell_syntax_check.py", text)
        self.assertIn("PyYAML==6.0.2", text)
        self.assertIn("yaml.safe_load", text)
        self.assertIn("scripts/instruction_budget.py", text)
        self.assertIn("scripts/permission_hook_conflicts.py", text)

    def test_workflow_is_read_only_and_scoped_to_main_prs(self):
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("pull_request:", text)
        self.assertNotIn("branches: [main]", text)
        self.assertIn("contents: read", text)
        self.assertNotIn("scripts/ai_config.py diff", text)
        self.assertNotIn("setup.sh", text)


if __name__ == "__main__":
    unittest.main()
