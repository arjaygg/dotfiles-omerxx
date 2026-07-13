import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.config_generate import (
    TemplateValidationError,
    build_proposal,
    compare_proposal,
    deep_merge,
    expand_placeholders,
)


ROOT = Path(__file__).resolve().parents[1]


class ConfigGenerateTests(unittest.TestCase):
    def test_expand_placeholders_replaces_nested_values(self):
        value = {
            "command": "${PCTX_COMMAND}",
            "args": ["--config", "${PCTX_CONFIG}"],
        }

        self.assertEqual(
            expand_placeholders(
                value,
                {"PCTX_COMMAND": "pctx", "PCTX_CONFIG": "/tmp/pctx.json"},
            ),
            {"command": "pctx", "args": ["--config", "/tmp/pctx.json"]},
        )

    def test_expand_placeholders_rejects_unresolved_variables(self):
        with self.assertRaises(TemplateValidationError):
            expand_placeholders({"path": "${MISSING}"}, {})

    def test_build_proposal_expands_explicit_variables_without_environment_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.json"
            base.write_text('{"path": "${CONFIG_PATH}"}\n', encoding="utf-8")

            original = os.environ.get("CONFIG_PATH")
            os.environ["CONFIG_PATH"] = "/tmp/should-not-be-used"
            try:
                proposal = build_proposal(
                    base,
                    variables={"CONFIG_PATH": "/tmp/pctx.json"},
                )
            finally:
                if original is None:
                    os.environ.pop("CONFIG_PATH", None)
                else:
                    os.environ["CONFIG_PATH"] = original

        self.assertEqual(json.loads(proposal), {"path": "/tmp/pctx.json"})

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

    def test_script_entrypoint_accepts_explicit_variables(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "base.json"
            base.write_text('{"path": "${CONFIG_PATH}"}\n', encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/config_generate.py"),
                    str(base),
                    "--set",
                    "CONFIG_PATH=/tmp/pctx.json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"path": "/tmp/pctx.json"})

    def test_compare_proposal_reports_paths_and_hashes_without_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.json"
            overlay = root / "overlay.json"
            target = root / "target.json"
            base.write_text('{"model": "portable", "nested": {"a": 1}}\n', encoding="utf-8")
            overlay.write_text('{"nested": {"b": 2}}\n', encoding="utf-8")
            target.write_text('{"model": "portable", "nested": {"a": 1, "b": 3}}\n', encoding="utf-8")
            target_before = target.read_bytes()

            comparison = compare_proposal(base, overlay, target)

            self.assertEqual(comparison.changed_paths, ["nested.b"])
            self.assertEqual(len(comparison.proposal_sha256), 64)
            self.assertEqual(len(comparison.target_sha256), 64)
            self.assertEqual(target.read_bytes(), target_before)


if __name__ == "__main__":
    unittest.main()
