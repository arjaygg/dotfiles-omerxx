import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.public_hygiene_check import scan_text


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude/hooks/settings-symlink-guard.sh"
SETTINGS = ROOT / ".claude/settings.json"
BASE_TEMPLATE = ROOT / "ai/config/claude/settings.base.json"

class Phase0BoundaryTests(unittest.TestCase):
    def test_tracked_settings_do_not_enable_dangerous_mode_bypass(self):
        # The guarantee is scoped to the distributable base template: fresh
        # machines must not inherit a bypass default. The live tracked file is
        # runtime-managed state — Claude Code re-persists
        # skipDangerousModePermissionPrompt there whenever the user consents in
        # the UI (also mirrored in the gitignored settings.local.json), so
        # asserting it on the live file produced a red/green treadmill.
        settings = json.loads(BASE_TEMPLATE.read_text(encoding="utf-8"))

        self.assertIsNot(settings.get("skipDangerousModePermissionPrompt"), True)

    def test_runtime_settings_file_is_untracked_and_ignored(self):
        # decisions/0016: .claude/settings.json is a runtime-managed projection
        # (lean-ctx daemon + Claude Code rewrite it), generated from the base
        # template on fresh machines — it must never be committed.
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", ".claude/settings.json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        ignored = subprocess.run(
            ["git", "check-ignore", ".claude/settings.json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(tracked.returncode, 0)
        self.assertEqual(ignored.returncode, 0)

    @unittest.skipUnless(SETTINGS.exists(), "runtime settings not generated on this host")
    def test_runtime_settings_is_valid_json(self):
        # Post-0016 the live file is runtime-owned: divergence from the base
        # template (model choice, skipDangerousModePermissionPrompt, absolute
        # lean-ctx hook paths) is legitimate state, not drift. The only durable
        # guarantee is that the file stays parseable.
        json.loads(SETTINGS.read_text(encoding="utf-8"))

    def test_claude_base_template_is_hygienic(self):
        self.assertEqual(
            scan_text("ai/config/claude/settings.base.json", BASE_TEMPLATE.read_text(encoding="utf-8")),
            [],
        )

    def test_guard_source_has_no_copyback_or_auto_relink_commands(self):
        source = HOOK.read_text(encoding="utf-8")

        self.assertNotIn('cp "$LIVE" "$SRC"', source)
        self.assertNotIn('ln -sf "$SRC" "$LIVE"', source)

    def test_machine_local_settings_overlay_is_not_tracked(self):
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", ".claude/settings.local.json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        ignored = subprocess.run(
            ["git", "check-ignore", ".claude/settings.local.json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(tracked.returncode, 0)
        self.assertEqual(ignored.returncode, 0)

    def test_severed_valid_runtime_file_is_reported_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            source = home / ".dotfiles/.claude/settings.json"
            live = home / ".claude/settings.json"
            source.parent.mkdir(parents=True)
            live.parent.mkdir(parents=True)
            source.write_text('{"portable": true}\n', encoding="utf-8")
            live.write_text('{"portable": false}\n', encoding="utf-8")
            source_before = source.read_bytes()
            live_before = live.read_bytes()

            result = self._run_guard(home)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(source.read_bytes(), source_before)
            self.assertEqual(live.read_bytes(), live_before)
            self.assertFalse(live.is_symlink())
            self.assertIn("not auto-syncing", result.stdout)

    def test_invalid_runtime_file_is_reported_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            source = home / ".dotfiles/.claude/settings.json"
            live = home / ".claude/settings.json"
            source.parent.mkdir(parents=True)
            live.parent.mkdir(parents=True)
            source.write_text('{"portable": true}\n', encoding="utf-8")
            live.write_text("{broken\n", encoding="utf-8")

            result = self._run_guard(home)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(source.read_text(encoding="utf-8"), '{"portable": true}\n')
            self.assertEqual(live.read_text(encoding="utf-8"), "{broken\n")
            self.assertIn("invalid JSON", result.stdout)

    def test_intact_symlink_is_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            source = home / ".dotfiles/.claude/settings.json"
            live = home / ".claude/settings.json"
            source.parent.mkdir(parents=True)
            live.parent.mkdir(parents=True)
            source.write_text('{"portable": true}\n', encoding="utf-8")
            live.symlink_to(source)

            result = self._run_guard(home)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertTrue(live.is_symlink())
            self.assertEqual(live.read_text(encoding="utf-8"), '{"portable": true}\n')

    @staticmethod
    def _run_guard(home: Path) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["HOME"] = str(home)
        return subprocess.run(
            ["bash", str(HOOK)],
            input="{}\n",
            capture_output=True,
            text=True,
            check=False,
            env=environment,
        )


if __name__ == "__main__":
    unittest.main()
