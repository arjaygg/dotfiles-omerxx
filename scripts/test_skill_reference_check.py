import tempfile
import unittest
from pathlib import Path

from scripts.skill_reference_check import check_references, summarize_issues


class SkillReferenceCheckTests(unittest.TestCase):
    def test_reports_missing_skill_path_and_slash_reference(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "ai/skills/existing").mkdir(parents=True)
            (root / "ai/skills/existing/SKILL.md").write_text("---\nname: existing\n---\n", encoding="utf-8")
            (root / "ai/commands/existing-command.md").parent.mkdir(parents=True)
            (root / "ai/commands/existing-command.md").write_text("# command\n", encoding="utf-8")
            doc = root / "plans/demo.md"
            doc.parent.mkdir()
            doc.write_text(
                "\n".join(
                    [
                        "Keep `ai/skills/existing/SKILL.md`.",
                        "Missing path: `ai/skills/missing-skill/SKILL.md`.",
                        "Existing command `/existing-command` is ok.",
                        "Missing slash `/missing-command` is not ok.",
                    ]
                ),
                encoding="utf-8",
            )

            issues = check_references(root)

        self.assertEqual(
            [(issue.kind, issue.name, issue.line, issue.scope) for issue in issues],
            [
                ("skill-path", "missing-skill", 2, "historical-plans"),
                ("slash-ref", "missing-command", 4, "historical-plans"),
            ],
        )
        self.assertEqual(
            summarize_issues(issues),
            {
                "total": 2,
                "by_scope": {"historical-plans": 2},
                "by_kind": {"skill-path": 1, "slash-ref": 1},
                "by_name": {"missing-command": 1, "missing-skill": 1},
                "by_path": {"plans/demo.md": 2},
            },
        )


if __name__ == "__main__":
    unittest.main()
