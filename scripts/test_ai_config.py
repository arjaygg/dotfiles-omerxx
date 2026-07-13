import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

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

    def test_stage_rolls_back_prior_replacements_when_a_later_target_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            (output_root / ".ai-config-staging").touch()
            codex_target = output_root / ".codex/config.toml"
            gemini_target = output_root / ".gemini/mcp.json"
            codex_target.parent.mkdir(parents=True)
            gemini_target.parent.mkdir(parents=True)
            codex_target.write_text("codex = 'old'\n", encoding="utf-8")
            gemini_target.write_text('{"gemini": "old"}\n', encoding="utf-8")
            real_replace = os.replace

            def replace_or_fail(source, target):
                if str(target).endswith(".gemini/mcp.json"):
                    raise OSError("simulated second-target failure")
                real_replace(source, target)

            with mock.patch("scripts.ai_config.os.replace", side_effect=replace_or_fail):
                with self.assertRaisesRegex(OSError, "second-target"):
                    stage_proposals(
                        ROOT,
                        output_root,
                        clients={"codex", "gemini"},
                        variables={"PCTX_CONFIG": "/tmp/pctx.json"},
                        replace=True,
                    )

            self.assertEqual(codex_target.read_text(encoding="utf-8"), "codex = 'old'\n")
            self.assertEqual(gemini_target.read_text(encoding="utf-8"), '{"gemini": "old"}\n')
            self.assertEqual(list(output_root.rglob("*.bak")), [])

    def test_stage_preserves_unmanaged_client_cache_files(self):
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            (output_root / ".ai-config-staging").touch()
            caches = {
                output_root / ".codex/cache/session.db": b"codex-cache-v1",
                output_root / ".gemini/cache/index.sqlite": b"gemini-cache-v1",
            }
            for path, content in caches.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)

            stage_proposals(
                ROOT,
                output_root,
                clients={"codex", "gemini"},
                variables={"PCTX_CONFIG": "/tmp/pctx.json"},
            )

            for path, content in caches.items():
                self.assertEqual(path.read_bytes(), content)

    def test_stage_rejects_symlinked_parent_that_escapes_staging_root(self):
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory) / "staging"
            outside = Path(directory) / "outside"
            output_root.mkdir()
            outside.mkdir()
            (output_root / ".ai-config-staging").touch()
            (output_root / ".codex").symlink_to(outside, target_is_directory=True)

            with self.assertRaisesRegex(TemplateValidationError, "symlink"):
                stage_proposals(ROOT, output_root, clients={"codex"})

            self.assertFalse((outside / "config.toml").exists())


if __name__ == "__main__":
    unittest.main()
