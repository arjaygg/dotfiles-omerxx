import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.config_doctor import compare_runtime_file, run_doctor


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

    def test_identical_source_and_runtime_settings_have_no_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.json"
            runtime = root / "runtime.json"
            source.write_text('{"safe": true}\n', encoding="utf-8")
            runtime.write_bytes(source.read_bytes())

            self.assertEqual(compare_runtime_file(source, runtime), [])

    def test_runtime_drift_is_reported_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.json"
            runtime = root / "runtime.json"
            source.write_text('{"safe": true}\n', encoding="utf-8")
            runtime.write_text('{"safe": false}\n', encoding="utf-8")
            before_source = source.read_bytes()
            before_runtime = runtime.read_bytes()

            issues = compare_runtime_file(source, runtime)
            after_source = source.read_bytes()
            after_runtime = runtime.read_bytes()

        self.assertEqual([issue.rule for issue in issues], ["runtime-drift"])
        self.assertTrue(issues[0].remediation)
        self.assertEqual(after_source, before_source)
        self.assertEqual(after_runtime, before_runtime)

    def test_tracked_local_overlay_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_config_tree(root)
            local_settings = root / ".claude/settings.local.json"
            local_settings.parent.mkdir(parents=True, exist_ok=True)
            local_settings.write_text('{"local": true}\n', encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(
                ["git", "-C", str(root), "add", "-f", ".claude/settings.local.json"], check=True
            )

            issues = run_doctor(root)

        self.assertEqual(
            [issue.rule for issue in issues],
            ["tracked-local-overlay"],
        )

    def test_blanket_permission_allow_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_config_tree(root)
            (root / ".claude/settings.json").write_text(
                json.dumps({"permissions": {"allow": ["Bash(*)", "Read(*)"]}}),
                encoding="utf-8",
            )

            issues = run_doctor(root)

        self.assertEqual(
            [issue.rule for issue in issues],
            ["blanket-permission-allow", "blanket-permission-allow"],
        )


if __name__ == "__main__":
    unittest.main()
