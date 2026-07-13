import json
import unittest
from pathlib import Path

from scripts.config_generate import build_proposal
from scripts.public_hygiene_check import scan_text


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = ROOT / "ai" / "config"
TEMPLATES = (
    TEMPLATE_ROOT / "gemini" / "mcp.base.json",
    TEMPLATE_ROOT / "cursor" / "mcp.base.json",
    TEMPLATE_ROOT / "windsurf" / "mcp_config.base.json",
    TEMPLATE_ROOT / "pctx" / "pctx.base.json",
)
VARIABLES = {"PCTX_CONFIG": "/tmp/pctx.json", "USER_NAME": "portable-user"}


class PortableConfigTemplateTests(unittest.TestCase):
    def test_all_client_templates_are_portable_json_objects(self):
        for path in TEMPLATES:
            with self.subTest(path=path):
                self.assertTrue(path.is_file())
                text = path.read_text(encoding="utf-8")
                self.assertEqual(scan_text(path.as_posix(), text), [])
                self.assertIsInstance(json.loads(text), dict)

    def test_all_client_templates_generate_without_mutating_inputs(self):
        for path in TEMPLATES:
            with self.subTest(path=path):
                before = path.read_bytes()
                proposal = build_proposal(path, variables=VARIABLES)
                self.assertIsInstance(json.loads(proposal), dict)
                self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
