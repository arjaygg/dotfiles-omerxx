import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.config_doctor import CONFIG_SPECS, Issue, compare_runtime_file, run_doctor, summarize_issues


CONFIG_FILES = (
    (".claude/settings.json", "json"),
    (".codex/config.toml", "toml"),
    (".config/pctx/pctx.json", "json"),
    (".gemini/settings.json", "json"),
    (".gemini/mcp.json", "json"),
    (".gemini/config/mcp_config.json", "json"),
    (".cursor/cli-config.json", "json"),
    (".cursor/mcp.json", "json"),
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

    def test_cli_runs_directly_from_repo_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_config_tree(root)

            result = subprocess.run(
                ["python3", str(Path(__file__).resolve().parent / "config_doctor.py"), str(root), "--json"],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])

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
            private_home = "/" + "Users/alice"
            (root / ".codex/config.toml").write_text(
                f"path = '{private_home}/.config/pctx.json'\n", encoding="utf-8"
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

    def test_summary_groups_issues_without_messages(self):
        private_home = "/" + "Users/alice"
        issues = [
            Issue(".codex/config.toml", "absolute-home-path", "warning", f"line 1: {private_home}/.config"),
            Issue(".codex/config.toml", "absolute-home-path", "warning", f"line 2: {private_home}/bin"),
            Issue(".claude/settings.json", "blanket-permission-allow", "error", "Bash(*)"),
        ]

        summary = summarize_issues(issues)

        self.assertEqual(
            summary,
            {
                "total": 3,
                "by_rule": {"absolute-home-path": 2, "blanket-permission-allow": 1},
                "by_severity": {"error": 1, "warning": 2},
                "by_path": {".codex/config.toml": 2, ".claude/settings.json": 1},
            },
        )
        self.assertNotIn("alice", repr(summary))
        self.assertNotIn("Bash(*)", repr(summary))

    def test_doctor_covers_tracked_client_config_paths(self):
        tracked_config_paths = {
            ".codex/config.toml",
            ".config/pctx/pctx.json",
            ".gemini/settings.json",
            ".gemini/mcp.json",
            ".gemini/config/mcp_config.json",
            ".cursor/mcp.json",
            ".windsurf/mcp_config.json",
        }

        self.assertTrue(tracked_config_paths.issubset({path for path, _kind in CONFIG_SPECS}))

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
