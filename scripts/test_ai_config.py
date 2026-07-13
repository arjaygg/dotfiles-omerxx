import json
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from scripts.ai_config import compare_proposals
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


if __name__ == "__main__":
    unittest.main()
