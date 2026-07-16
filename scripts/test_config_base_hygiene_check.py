import json
import tempfile
import unittest
from pathlib import Path

from scripts.config_base_hygiene_check import base_hygiene_findings
from scripts.public_hygiene_check import summarize_findings


class ConfigBaseHygieneCheckTests(unittest.TestCase):
    def test_reports_hygiene_findings_only_in_manifest_bases(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            base = root / "ai/config/codex/config.base.toml"
            base.parent.mkdir(parents=True)
            example_home = "/" + "Users/example"
            base.write_text(f'path = "{example_home}/.config/pctx/pctx.json"\n', encoding="utf-8")
            ignored = root / "ai/config/codex/README.md"
            ignored.write_text(f"{example_home}/not-a-base\n", encoding="utf-8")
            manifest = root / "ai/config/manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "clients": [
                            {
                                "name": "codex",
                                "format": "toml",
                                "base": "ai/config/codex/config.base.toml",
                                "runtime": "~/.codex/config.toml",
                                "overlay": "~/.config/dotfiles-ai/codex.overlay.toml",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            findings = base_hygiene_findings(root)

        self.assertEqual(summarize_findings(findings)["total"], 1)
        self.assertEqual(findings[0].path, "ai/config/codex/config.base.toml")

    def test_current_manifest_bases_are_hygiene_clean(self):
        root = Path(__file__).resolve().parents[1]
        findings = base_hygiene_findings(root)

        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
