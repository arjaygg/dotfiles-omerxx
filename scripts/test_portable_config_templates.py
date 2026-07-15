import json
import tomllib
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
CODEX_TEMPLATE = TEMPLATE_ROOT / "codex" / "config.base.toml"
CODEX_OVERLAY = TEMPLATE_ROOT / "codex" / "codex.overlay.example.toml"
VARIABLES = {
    "MARKETPLACE_CACHE": "/tmp/marketplace-cache",
    "PCTX_CONFIG": "/tmp/pctx.json",
    "PROJECT_ROOT": "/tmp/example-project",
    "USER_NAME": "portable-user",
}


class PortableConfigTemplateTests(unittest.TestCase):
    def test_all_client_templates_are_portable_json_objects(self):
        for path in TEMPLATES:
            with self.subTest(path=path):
                self.assertTrue(path.is_file())
                text = path.read_text(encoding="utf-8")
                self.assertEqual(scan_text(path.as_posix(), text), [])
                self.assertIsInstance(json.loads(text), dict)

    def test_codex_template_is_portable_and_valid_toml(self):
        self.assertTrue(CODEX_TEMPLATE.is_file())
        text = CODEX_TEMPLATE.read_text(encoding="utf-8")
        self.assertEqual(scan_text(CODEX_TEMPLATE.as_posix(), text), [])
        config = tomllib.loads(text)
        self.assertEqual(config["mcp_servers"]["pctx"]["command"], "pctx")
        self.assertEqual(config["project_doc_fallback_filenames"], ["AGENTS.md"])
        self.assertIn("status_line", config["tui"])
        self.assertNotIn("status_line", config)

    def test_all_client_templates_generate_without_mutating_inputs(self):
        for path in TEMPLATES:
            with self.subTest(path=path):
                before = path.read_bytes()
                proposal = build_proposal(path, variables=VARIABLES)
                self.assertIsInstance(json.loads(proposal), dict)
                self.assertEqual(path.read_bytes(), before)

    def test_codex_template_generates_without_mutating_inputs(self):
        before = CODEX_TEMPLATE.read_bytes()
        proposal_text = build_proposal(CODEX_TEMPLATE, variables=VARIABLES)
        proposal = tomllib.loads(proposal_text)
        self.assertIsInstance(proposal, dict)
        self.assertEqual(proposal["mcp_servers"]["pctx"]["args"][4], "/tmp/pctx.json")
        self.assertEqual(CODEX_TEMPLATE.read_bytes(), before)

    def test_codex_example_overlay_parses_and_generates_without_mutation(self):
        base_before = CODEX_TEMPLATE.read_bytes()
        overlay_before = CODEX_OVERLAY.read_bytes()
        overlay_text = overlay_before.decode("utf-8")
        self.assertEqual(scan_text(CODEX_OVERLAY.as_posix(), overlay_text), [])
        overlay = tomllib.loads(overlay_text)
        self.assertEqual(
            overlay["projects"]["${PROJECT_ROOT}"]["trust_level"],
            "trusted",
        )
        self.assertTrue(overlay["skills"]["config"][0]["enabled"])
        self.assertEqual(
            overlay["skills"]["config"][0]["path"],
            "${PROJECT_ROOT}/.agents/skills/example-skill",
        )
        self.assertEqual(
            overlay["mcp_servers"]["marketplace"]["command"],
            "mcp-marketplace",
        )

        proposal_text = build_proposal(
            CODEX_TEMPLATE,
            CODEX_OVERLAY,
            variables=VARIABLES,
        )
        proposal = tomllib.loads(proposal_text)
        self.assertEqual(
            proposal["projects"]["/tmp/example-project"]["trust_level"],
            "trusted",
        )
        self.assertEqual(
            proposal["skills"]["config"][0]["path"],
            "/tmp/example-project/.agents/skills/example-skill",
        )
        self.assertEqual(
            proposal["mcp_servers"]["marketplace"]["args"],
            ["start", "--cache-dir", "/tmp/marketplace-cache"],
        )
        self.assertEqual(CODEX_TEMPLATE.read_bytes(), base_before)
        self.assertEqual(CODEX_OVERLAY.read_bytes(), overlay_before)



if __name__ == "__main__":
    unittest.main()
