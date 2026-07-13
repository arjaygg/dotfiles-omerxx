import json
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from scripts.ai_config import compare_proposals, stage_proposals
from scripts.config_generate import TemplateValidationError
from scripts.config_generate_all import build_proposals


ROOT = Path(__file__).resolve().parents[1]


class AiConfigCliTests(unittest.TestCase):
    def test_diff_reports_match_and_drift_without_target_content(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime_root = Path(directory)
            proposal = build_proposals(ROOT, clients={"codex"})["codex"]
            target = runtime_root / ".codex/config.toml"
            target.parent.mkdir(parents=True)
            target.write_text(proposal["content"], encoding="utf-8")

            matching = compare_proposals(ROOT, runtime_root, clients={"codex"})
            target.write_text(proposal["content"].replace('model = "gpt-5.5"', 'model = "gpt-5.4"'), encoding="utf-8")
            drifted = compare_proposals(ROOT, runtime_root, clients={"codex"})

        self.assertEqual(matching["codex"]["status"], "match")
        self.assertEqual(drifted["codex"]["status"], "drift")
        self.assertIn("model", drifted["codex"]["changed_paths"])
        self.assertNotIn("target_content", drifted["codex"])

    def test_diff_reports_missing_target(self):
        with tempfile.TemporaryDirectory() as directory:
            result = compare_proposals(ROOT, Path(directory), clients={"codex"})

        self.assertEqual(result["codex"]["status"], "missing")
        self.assertEqual(result["codex"]["changed_paths"], [])

    def test_generate_command_emits_proposals(self):
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/ai_config.py"),
                "generate",
                "--root",
                str(ROOT),
                "--client",
                "codex",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(set(payload["proposals"]), {"codex"})
        self.assertIsInstance(tomllib.loads(payload["proposals"]["codex"]["content"]), dict)

    def test_doctor_command_emits_read_only_issue_report(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/ai_config.py"), "doctor", "--root", str(ROOT)],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIsInstance(json.loads(result.stdout), list)

    def test_stage_requires_explicit_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(TemplateValidationError):
                stage_proposals(ROOT, Path(directory), clients={"codex"})

    def test_stage_writes_atomic_proposal_under_marked_root(self):
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            (output_root / ".ai-config-staging").touch()

            result = stage_proposals(ROOT, output_root, clients={"codex"})
            target = (output_root / ".codex/config.toml").resolve()
            content = target.read_text(encoding="utf-8")

        self.assertEqual(result["backups"], [])
        self.assertEqual(result["written"], [str(target)])
        self.assertIn('model = "gpt-5.5"', content)

    def test_stage_refuses_existing_target_without_replace(self):
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            (output_root / ".ai-config-staging").touch()
            target = (output_root / ".codex/config.toml").resolve()
            target.parent.mkdir(parents=True)
            target.write_text("old = true\n", encoding="utf-8")

            with self.assertRaises(TemplateValidationError):
                stage_proposals(ROOT, output_root, clients={"codex"})

            self.assertEqual(target.read_text(encoding="utf-8"), "old = true\n")

    def test_stage_replace_creates_backup_before_replacing(self):
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            (output_root / ".ai-config-staging").touch()
            target = (output_root / ".codex/config.toml").resolve()
            target.parent.mkdir(parents=True)
            target.write_text("old = true\n", encoding="utf-8")

            result = stage_proposals(ROOT, output_root, clients={"codex"}, replace=True)

            backup = target.with_name(target.name + ".bak")
            self.assertEqual(backup.read_text(encoding="utf-8"), "old = true\n")
            self.assertEqual(result["backups"], [str(backup)])
            self.assertNotEqual(target.read_text(encoding="utf-8"), "old = true\n")


if __name__ == "__main__":
    unittest.main()
