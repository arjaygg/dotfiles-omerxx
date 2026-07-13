import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CommandReferenceTests(unittest.TestCase):
    def test_evolve_command_has_no_dead_cli_path(self):
        text = (ROOT / "ai/commands/evolve.md").read_text(encoding="utf-8")

        self.assertNotIn("continuous-learning-v2", text)
        self.assertNotIn('python3 "${CLAUDE_PLUGIN_ROOT}', text)
        self.assertNotIn("python3 ~/.claude/skills", text)
        self.assertIn("scripts/policy_proposal.py validate", text)


if __name__ == "__main__":
    unittest.main()
