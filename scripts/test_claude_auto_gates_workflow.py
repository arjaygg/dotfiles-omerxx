from pathlib import Path
import unittest


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/claude-auto-gates.yml"
SETUP = Path(__file__).resolve().parents[1] / "setup.sh"
SHARED_AUDIT_SUMMARY_COMMANDS = [
    "python3 scripts/shell_syntax_check.py --summary",
    "python3 scripts/syntax_check.py --summary",
    "python3 scripts/guidance_adapter_check.py --summary",
    "python3 scripts/autonomous_skill_check.py --summary",
    "python3 scripts/mcp_gateway_check.py --summary",
    "python3 scripts/hook_fixture_runner.py .claude/hooks/pre-tool-gate-v2.sh scripts/fixtures/pretool-gate-v2.json --summary",
    "python3 scripts/hook_target_check.py .claude/settings.json --summary",
    "python3 scripts/hook_output_schema_check.py .claude/hooks --summary || true",
    "python3 scripts/self_modification_check.py --summary || true",
    "python3 scripts/config_inventory.py --summary",
    "python3 scripts/config_base_hygiene_check.py --summary",
    "python3 scripts/public_hygiene_check.py --summary || true",
    "python3 scripts/config_doctor.py --summary || true",
    "python3 scripts/hook_config_check.py .claude/settings.json --summary || true",
    "python3 scripts/instruction_budget_check.py --summary",
    "python3 scripts/skill_reference_check.py --summary || true",
]


class ClaudeAutoGatesWorkflowTests(unittest.TestCase):
    def test_config_audit_summary_job_is_non_blocking_for_known_baselines(self):
        text = WORKFLOW.read_text()

        self.assertIn("claude-auto-config-audit-summary:", text)
        self.assertIn("python3 scripts/config_inventory.py --summary", text)
        self.assertIn("python3 scripts/guidance_adapter_check.py --summary", text)
        self.assertIn("python3 scripts/autonomous_skill_check.py --summary", text)
        self.assertIn("python3 scripts/mcp_gateway_check.py --summary", text)
        self.assertIn("python3 scripts/hook_target_check.py .claude/settings.json --summary", text)
        self.assertIn("python3 scripts/hook_output_schema_check.py .claude/hooks --summary || true", text)
        self.assertIn("python3 scripts/self_modification_check.py --summary || true", text)
        self.assertIn("python3 scripts/config_base_hygiene_check.py --summary", text)
        self.assertIn("python3 scripts/public_hygiene_check.py --summary || true", text)
        self.assertIn("python3 scripts/config_doctor.py --summary || true", text)
        self.assertIn(
            "python3 scripts/hook_config_check.py .claude/settings.json --summary || true",
            text,
        )
        self.assertIn("python3 scripts/instruction_budget_check.py --summary", text)
        self.assertIn("python3 scripts/skill_reference_check.py --summary || true", text)

    def test_setup_check_and_pr_audit_share_summary_commands(self):
        workflow = WORKFLOW.read_text()
        setup = SETUP.read_text()

        for command in SHARED_AUDIT_SUMMARY_COMMANDS:
            with self.subTest(command=command):
                self.assertIn(command, workflow)
                self.assertIn(command, setup)


if __name__ == "__main__":
    unittest.main()
