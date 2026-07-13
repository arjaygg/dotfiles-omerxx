import json
import tomllib
import unittest
from pathlib import Path

from scripts.public_hygiene_check import scan_text


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "ai" / "config" / "manifest.json"


class ConfigManifestTests(unittest.TestCase):
    def test_manifest_is_portable_and_references_valid_bases(self):
        text = MANIFEST.read_text(encoding="utf-8")
        self.assertEqual(scan_text(MANIFEST.as_posix(), text), [])
        manifest = json.loads(text)

        self.assertEqual(manifest["version"], 1)
        clients = manifest["clients"]
        self.assertEqual(
            {client["name"] for client in clients},
            {"claude", "codex", "gemini", "cursor", "windsurf", "pctx"},
        )

        for client in clients:
            with self.subTest(client=client["name"]):
                base = ROOT / client["base"]
                self.assertTrue(base.is_file())
                self.assertTrue(client["runtime"].startswith("~/"))
                self.assertTrue(client["overlay"].startswith("~/.config/dotfiles-ai/"))
                base_text = base.read_text(encoding="utf-8")
                self.assertEqual(scan_text(base.as_posix(), base_text), [])
                if client["format"] == "json":
                    self.assertIsInstance(json.loads(base_text), dict)
                elif client["format"] == "toml":
                    self.assertIsInstance(tomllib.loads(base_text), dict)
                else:
                    self.fail(f"unsupported manifest format: {client['format']}")


if __name__ == "__main__":
    unittest.main()
