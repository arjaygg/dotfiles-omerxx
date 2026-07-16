import tempfile
import unittest
from pathlib import Path

from scripts.autonomous_skill_check import check_autonomous_skills, summarize_results


def write_skill(root: Path, name: str, body: str) -> None:
    path = root / "ai/skills" / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


class AutonomousSkillCheckTests(unittest.TestCase):
    def test_valid_core_skill_contracts_pass(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name, role in {
                "cap": "orchestrator",
                "stark": "plan",
                "fury": "test",
                "ironman": "implement",
                "hawk": "review",
                "strange": "debug",
            }.items():
                write_skill(
                    root,
                    name,
                    "\n".join(
                        [
                            "---",
                            f"name: {name}",
                            "description: core autonomous primitive",
                            "triggers:",
                            f"  - /{name}",
                            "version: 1.0.0",
                            "model: sonnet",
                            "---",
                            f"# {name}",
                            role,
                            "portable workflow architect not for: writing code writing tests",
                            "failing test tdd test-first tests pass minimal findings architecture security",
                            "reproduce hypothesize verify fix",
                            "persistence directive",
                            "TodoWrite",
                            "TaskUpdate",
                            "stark fury ironman hawk" if name == "cap" else "",
                        ]
                    ),
                )

            results = check_autonomous_skills(root)

        self.assertFalse([result for result in results if result.status == "fail"])
        summary = summarize_results(results)
        self.assertEqual(summary["by_status"], {"ok": summary["total"]})

    def test_missing_orchestration_phase_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_skill(
                root,
                "cap",
                "\n".join(
                    [
                        "---",
                        "name: cap",
                        "description: core autonomous primitive",
                        "triggers:",
                        "  - /cap",
                        "version: 1.0.0",
                        "model: sonnet",
                        "---",
                        "# cap",
                        "orchestrator",
                        "persistence directive",
                        "TodoWrite",
                        "TaskUpdate",
                        "stark fury ironman",
                    ]
                ),
            )

            results = check_autonomous_skills(root, required_skills=("cap",))

        self.assertIn(
            ("cap-orchestrates-hawk", "ai/skills/cap/SKILL.md", "fail"),
            [(result.rule, result.path, result.status) for result in results],
        )

    def test_current_repo_autonomous_skills_pass(self):
        root = Path(__file__).resolve().parents[1]
        results = check_autonomous_skills(root)

        self.assertFalse([result for result in results if result.status == "fail"])


if __name__ == "__main__":
    unittest.main()
