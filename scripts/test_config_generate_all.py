import json
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from scripts.config_generate_all import TemplateValidationError, build_proposals


ROOT = Path(__file__).resolve().parents[1]
CLIENTS = {"claude", "codex", "gemini", "cursor", "windsurf", "pctx"}


class ConfigGenerateAllTests(unittest.TestCase):
    def _manifest_root(self, clients):
        directory = tempfile.TemporaryDirectory()
        root = Path(directory.name)
        config_dir = root / "ai/config"
        config_dir.mkdir(parents=True)
        (config_dir / "base.json").write_text("{}\n", encoding="utf-8")
        (config_dir / "manifest.json").write_text(
            json.dumps({"version": 1, "clients": clients}), encoding="utf-8"
        )
        return directory, root

    def test_builds_all_manifest_clients_with_explicit_variables(self):
        proposals = build_proposals(
            ROOT,
            variables={
                "PCTX_CONFIG": "~/.config/pctx/pctx.json",
                "USER_NAME": "portable-user",
            },
        )

        self.assertEqual(set(proposals), CLIENTS)
        for proposal in proposals.values():
            if proposal["format"] == "json":
                self.assertIsInstance(json.loads(proposal["content"]), dict)
            else:
                self.assertIsInstance(tomllib.loads(proposal["content"]), dict)

    def test_rejects_unresolved_placeholders(self):
        with self.assertRaises(TemplateValidationError):
            build_proposals(ROOT, clients={"pctx"})

    def test_rejects_duplicate_client_names(self):
        directory, root = self._manifest_root(
            [
                {"name": "one", "format": "json", "base": "ai/config/base.json", "runtime": "~/.one.json"},
                {"name": "one", "format": "json", "base": "ai/config/base.json", "runtime": "~/.two.json"},
            ]
        )
        with directory:
            with self.assertRaisesRegex(TemplateValidationError, "duplicate client name"):
                build_proposals(root)

    def test_rejects_unsafe_client_names(self):
        directory, root = self._manifest_root(
            [
                {"name": "../escape", "format": "json", "base": "ai/config/base.json", "runtime": "~/.one.json"},
            ]
        )
        with directory:
            with self.assertRaisesRegex(TemplateValidationError, "unsafe name"):
                build_proposals(root)

    def test_rejects_runtime_escape_and_duplicate_targets(self):
        directory, root = self._manifest_root(
            [
                {"name": "one", "format": "json", "base": "ai/config/base.json", "runtime": "~/../escape.json"},
            ]
        )
        with directory:
            with self.assertRaisesRegex(TemplateValidationError, "runtime escapes"):
                build_proposals(root)

        directory, root = self._manifest_root(
            [
                {"name": "one", "format": "json", "base": "ai/config/base.json", "runtime": "~/.same.json"},
                {"name": "two", "format": "json", "base": "ai/config/base.json", "runtime": "~/.same.json"},
            ]
        )
        with directory:
            with self.assertRaisesRegex(TemplateValidationError, "duplicate runtime target"):
                build_proposals(root)

    def test_merges_toml_overlay_without_mutating_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            overlay_dir = Path(directory)
            overlay = overlay_dir / "codex.overlay.toml"
            overlay.write_text(
                "[features]\nunified_exec = false\nnew_flag = true\n",
                encoding="utf-8",
            )
            before = overlay.read_bytes()

            proposals = build_proposals(ROOT, clients={"codex"}, overlay_dir=overlay_dir)

        rendered = tomllib.loads(proposals["codex"]["content"])
        self.assertFalse(rendered["features"]["unified_exec"])
        self.assertTrue(rendered["features"]["new_flag"])
        self.assertEqual(before, b"[features]\nunified_exec = false\nnew_flag = true\n")

    def test_cli_emits_deterministic_proposal_bundle(self):
        command = [
            sys.executable,
            str(ROOT / "scripts/config_generate_all.py"),
            "--root",
            str(ROOT),
            "--client",
            "codex",
        ]
        first = subprocess.run(command, capture_output=True, text=True, check=False)
        second = subprocess.run(command, capture_output=True, text=True, check=False)

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(set(json.loads(first.stdout)["proposals"]), {"codex"})


if __name__ == "__main__":
    unittest.main()
