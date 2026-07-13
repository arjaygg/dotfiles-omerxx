import json
import tempfile
import unittest
from pathlib import Path

from scripts.config_doctor import run_doctor


CONFIG_FILES = (
    (".claude/settings.json", "json"),
    (".codex/config.toml", "toml"),
    (".gemini/settings.json", "json"),
    (".gemini/mcp.json", "json"),
    (".cursor/cli-config.json", "json"),
    (".windsurf/mcp_config.json", "json"),
    ("mcp.json", "json"),
)


def make_config_tree(root: Path) -> None:
    for relative_path, kind in CONFIG_FILES:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n" if kind == "json" else "model = 'portable'\n", encoding="utf-8")


class ConfigDoctorTests(unittest.TestCase):
    def test_valid_tree_has_no_issues(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_config_tree(root)

            self.assertEqual(run_doctor(root), [])

    def test_reports_invalid_config_and_unsafe_bypass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_config_tree(root)
            settings = root / ".claude/settings.json"
            settings.write_text(
                json.dumps({"skipDangerousModePermissionPrompt": True}), encoding="utf-8"
            )
            (root / ".gemini/settings.json").write_text("{broken", encoding="utf-8")

            issues = run_doctor(root)

        self.assertEqual(
            {(issue.rule, issue.path) for issue in issues},
            {
                ("unsafe-bypass", ".claude/settings.json"),
                ("invalid-config", ".gemini/settings.json"),
            },
        )

    def test_reports_absolute_paths_and_copyback_behavior(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_config_tree(root)
            (root / ".codex/config.toml").write_text(
                "path = '/Users/alice/.config/pctx.json'\n", encoding="utf-8"
            )
            guard = root / ".claude/hooks/settings-symlink-guard.sh"
            guard.parent.mkdir(parents=True, exist_ok=True)
            guard.write_text('cp "$LIVE" "$SRC"\n', encoding="utf-8")
            before = guard.read_bytes()

            issues = run_doctor(root)

        self.assertEqual(
            {(issue.rule, issue.path) for issue in issues},
            {
                ("absolute-home-path", ".codex/config.toml"),
                ("runtime-copyback", ".claude/hooks/settings-symlink-guard.sh"),
            },
        )
        self.assertEqual(before, b'cp "$LIVE" "$SRC"\n')


if __name__ == "__main__":
    unittest.main()
