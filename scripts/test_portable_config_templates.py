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
    TEMPLATE_ROOT / "gemini" / "settings.base.json",
    TEMPLATE_ROOT / "cursor" / "mcp.base.json",
    TEMPLATE_ROOT / "windsurf" / "mcp_config.base.json",
    TEMPLATE_ROOT / "pctx" / "pctx.base.json",
)
CODEX_TEMPLATE = TEMPLATE_ROOT / "codex" / "config.base.toml"
CODEX_OVERLAY = TEMPLATE_ROOT / "codex" / "codex.overlay.example.toml"
GEMINI_SETTINGS_TEMPLATE = TEMPLATE_ROOT / "gemini" / "settings.base.json"
GEMINI_SETTINGS_OVERLAY = TEMPLATE_ROOT / "gemini" / "gemini-settings.overlay.example.json"
CURSOR_TEMPLATE = TEMPLATE_ROOT / "cursor" / "mcp.base.json"
CURSOR_OVERLAY = TEMPLATE_ROOT / "cursor" / "cursor.overlay.example.json"
WINDSURF_TEMPLATE = TEMPLATE_ROOT / "windsurf" / "mcp_config.base.json"
WINDSURF_OVERLAY = TEMPLATE_ROOT / "windsurf" / "windsurf.overlay.example.json"
VARIABLES = {
    "MARKETPLACE_CACHE": "/tmp/marketplace-cache",
    "PCTX_CONFIG": "/tmp/pctx.json",
    "PROJECT_ROOT": "/tmp/example-project",
    "USER_NAME": "portable-user",
    "LEAN_CTX_DATA_DIR": "/tmp/lean-ctx-data",
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

    def test_gemini_settings_template_has_expected_keys_and_excludes_preferences(self):
        config = json.loads(GEMINI_SETTINGS_TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(config["selectedAuthType"], "oauth-personal")
        self.assertEqual(config["mcpServers"]["pctx"]["command"], "pctx")
        self.assertEqual(config["security"]["auth"]["selectedType"], "oauth-personal")
        self.assertEqual(config["context"]["fileName"], ["AGENTS.md", "GEMINI.md"])
        self.assertTrue(config["experimental"]["enableAgents"])
        self.assertIn("statusLine", config)
        self.assertNotIn("model", config)
        self.assertNotIn("trustedWorkspaces", config)

    def test_cursor_template_includes_notebooklm_and_chrome_devtools(self):
        config = json.loads(CURSOR_TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(config["mcpServers"]["notebooklm"]["command"], "notebooklm-mcp")
        self.assertEqual(config["mcpServers"]["notebooklm"]["args"], [])
        self.assertEqual(
            config["mcpServers"]["chrome-devtools"]["command"],
            "chrome-devtools-mcp-wrapper.sh",
        )
        self.assertEqual(config["mcpServers"]["chrome-devtools"]["args"], [])

    def test_windsurf_template_includes_lean_ctx(self):
        config = json.loads(WINDSURF_TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(config["mcpServers"]["lean-ctx"]["command"], "lean-ctx")
        self.assertEqual(
            config["mcpServers"]["lean-ctx"]["env"]["LEAN_CTX_FULL_TOOLS"],
            "1",
        )

        proposal = json.loads(build_proposal(WINDSURF_TEMPLATE, variables=VARIABLES))
        self.assertEqual(
            proposal["mcpServers"]["lean-ctx"]["env"]["LEAN_CTX_DATA_DIR"],
            "/tmp/lean-ctx-data",
        )

    def test_gemini_settings_example_overlay_parses_and_generates_without_mutation(self):
        base_before = GEMINI_SETTINGS_TEMPLATE.read_bytes()
        overlay_before = GEMINI_SETTINGS_OVERLAY.read_bytes()
        overlay_text = overlay_before.decode("utf-8")
        self.assertEqual(scan_text(GEMINI_SETTINGS_OVERLAY.as_posix(), overlay_text), [])
        overlay = json.loads(overlay_text)
        self.assertEqual(overlay["trustedWorkspaces"], ["/tmp/example-project"])

        proposal = json.loads(
            build_proposal(
                GEMINI_SETTINGS_TEMPLATE,
                GEMINI_SETTINGS_OVERLAY,
                variables=VARIABLES,
            )
        )
        self.assertEqual(proposal["model"], "auto")
        self.assertEqual(proposal["trustedWorkspaces"], ["/tmp/example-project"])
        self.assertEqual(GEMINI_SETTINGS_TEMPLATE.read_bytes(), base_before)
        self.assertEqual(GEMINI_SETTINGS_OVERLAY.read_bytes(), overlay_before)

    def test_cursor_example_overlay_parses_and_generates_without_mutation(self):
        base_before = CURSOR_TEMPLATE.read_bytes()
        overlay_before = CURSOR_OVERLAY.read_bytes()
        overlay_text = overlay_before.decode("utf-8")
        self.assertEqual(scan_text(CURSOR_OVERLAY.as_posix(), overlay_text), [])
        overlay = json.loads(overlay_text)
        self.assertEqual(overlay["mcpServers"]["pctx"]["command"], "/tmp/example-bin/pctx")

        proposal = json.loads(
            build_proposal(CURSOR_TEMPLATE, CURSOR_OVERLAY, variables=VARIABLES)
        )
        self.assertEqual(
            proposal["mcpServers"]["notebooklm"]["command"],
            "/tmp/example-bin/notebooklm-mcp",
        )
        self.assertEqual(
            proposal["mcpServers"]["chrome-devtools"]["command"],
            "/tmp/example-bin/chrome-devtools-mcp-wrapper.sh",
        )
        self.assertEqual(CURSOR_TEMPLATE.read_bytes(), base_before)
        self.assertEqual(CURSOR_OVERLAY.read_bytes(), overlay_before)

    def test_windsurf_example_overlay_parses_and_generates_without_mutation(self):
        base_before = WINDSURF_TEMPLATE.read_bytes()
        overlay_before = WINDSURF_OVERLAY.read_bytes()
        overlay_text = overlay_before.decode("utf-8")
        self.assertEqual(scan_text(WINDSURF_OVERLAY.as_posix(), overlay_text), [])
        overlay = json.loads(overlay_text)
        self.assertEqual(
            overlay["mcpServers"]["lean-ctx"]["env"]["LEAN_CTX_DATA_DIR"],
            "/tmp/example-lean-ctx",
        )

        proposal = json.loads(
            build_proposal(WINDSURF_TEMPLATE, WINDSURF_OVERLAY, variables=VARIABLES)
        )
        self.assertEqual(
            proposal["mcpServers"]["lean-ctx"]["env"]["LEAN_CTX_DATA_DIR"],
            "/tmp/example-lean-ctx",
        )
        self.assertEqual(WINDSURF_TEMPLATE.read_bytes(), base_before)
        self.assertEqual(WINDSURF_OVERLAY.read_bytes(), overlay_before)


if __name__ == "__main__":
    unittest.main()
