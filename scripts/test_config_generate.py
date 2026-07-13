import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.config_generate import TemplateValidationError, build_proposal, deep_merge


ROOT = Path(__file__).resolve().parents[1]


class ConfigGenerateTests(unittest.TestCase):
    def test_deep_merge_recurses_and_replaces_lists(self):
        base = {"model": "portable", "nested": {"keep": True, "replace": 1}, "list": [1]}
        overlay = {"nested": {"replace": 2}, "list": [2], "local": True}

        self.assertEqual(
            deep_merge(base, overlay),
            {
                "model": "portable",
                "nested": {"keep": True, "replace": 2},
                "list": [2],
                "local": True,
            },
        )
        self.assertEqual(base["nested"]["replace"], 1)

    def test_build_proposal_merges_without_mutating_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.json"
            overlay = root / "overlay.json"
            base.write_text('{"model": "portable", "nested": {"a": 1}}\n', encoding="utf-8")
            overlay.write_text('{"nested": {"b": 2}}\n', encoding="utf-8")
            base_before = base.read_bytes()
            overlay_before = overlay.read_bytes()

            proposal = build_proposal(base, overlay)

            self.assertEqual(json.loads(proposal), {"model": "portable", "nested": {"a": 1, "b": 2}})
            self.assertEqual(base.read_bytes(), base_before)
            self.assertEqual(overlay.read_bytes(), overlay_before)

    def test_build_proposal_rejects_private_or_secret_input(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "base.json"
            base.write_text(
                '{"path": "/Users/alice/.config/tool", "token": "secret-value"}\n',
                encoding="utf-8",
            )

            with self.assertRaises(TemplateValidationError):
                build_proposal(base)

    def test_script_entrypoint_emits_proposal(self):
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/config_generate.py"),
                str(ROOT / "ai/config/claude/settings.base.json"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsInstance(json.loads(result.stdout), dict)


if __name__ == "__main__":
    unittest.main()
