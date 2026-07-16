import json
import tempfile
import unittest
from pathlib import Path

from scripts.config_inventory import build_inventory, summarize_inventory


class ConfigInventoryTests(unittest.TestCase):
    def test_build_inventory_classifies_manifest_entries_without_runtime_reads(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            base = root / "ai/config/demo/base.json"
            base.parent.mkdir(parents=True)
            base.write_text("{}\n", encoding="utf-8")
            manifest = root / "ai/config/manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "clients": [
                            {
                                "name": "demo",
                                "format": "json",
                                "base": "ai/config/demo/base.json",
                                "runtime": "~/.demo/config.json",
                                "overlay": "~/.config/dotfiles-ai/demo.overlay.json",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            rows = build_inventory(root, manifest)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].name, "demo")
        self.assertEqual(rows[0].base_scope, "tracked-portable-base")
        self.assertEqual(rows[0].source_status, "present")
        self.assertEqual(rows[0].format_status, "format-ok")
        self.assertEqual(rows[0].runtime_scope, "user-runtime")
        self.assertEqual(rows[0].overlay_scope, "ignored-local-overlay")

    def test_summary_counts_statuses(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "clients": [
                            {
                                "name": "missing",
                                "format": "json",
                                "base": "missing.json",
                                "runtime": ".tracked/runtime.json",
                                "overlay": "~/.config/dotfiles-ai/missing.overlay.json",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            summary = summarize_inventory(build_inventory(root, manifest))

        self.assertEqual(
            summary,
            {
                "total": 1,
                "by_base_scope": {"tracked-non-config-base": 1},
                "by_source_status": {"missing": 1},
                "by_format_status": {"format-ok": 1},
                "by_runtime_scope": {"tracked-runtime-path": 1},
                "by_overlay_scope": {"ignored-local-overlay": 1},
            },
        )

    def test_summary_counts_unsafe_base_and_format_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "clients": [
                            {
                                "name": "bad",
                                "format": "toml",
                                "base": "../config/base.json",
                                "runtime": "~/.bad/config.json",
                                "overlay": "~/.config/dotfiles-ai/bad.overlay.toml",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            summary = summarize_inventory(build_inventory(root, manifest))

        self.assertEqual(summary["by_base_scope"], {"unsafe-base-path": 1})
        self.assertEqual(summary["by_format_status"], {"format-mismatch": 1})


if __name__ == "__main__":
    unittest.main()
