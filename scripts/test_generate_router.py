"""Tests for the generated skill router and the manifest coverage checks."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_router as gr  # noqa: E402
from lib.manifest_lint import check_manifest  # noqa: E402

HEADER = "skill,phase,preceded-by,followed-by,output-location,outputs\n"


class RouterGenerationTests(unittest.TestCase):
    def test_regeneration_is_idempotent(self):
        rows = gr.read_manifest()
        self.assertEqual(gr.render(rows), gr.render(rows))

    def test_committed_router_is_not_stale(self):
        self.assertEqual(
            gr.ROUTER.read_text(encoding="utf-8"),
            gr.render(gr.read_manifest()),
            "router is stale — run: python3 scripts/generate_router.py",
        )

    def test_generated_router_carries_the_do_not_edit_banner(self):
        text = gr.ROUTER.read_text(encoding="utf-8")
        self.assertIn("GENERATED FILE — DO NOT EDIT", text)
        self.assertIn("ai/skills/manifest.csv", text)

    def test_every_manifest_skill_appears_in_the_router(self):
        text = gr.ROUTER.read_text(encoding="utf-8")
        for row in gr.read_manifest():
            self.assertIn(f"`{row['skill']}`", text)

    def test_all_six_core_behaviors_are_stated(self):
        text = gr.ROUTER.read_text(encoding="utf-8")
        for phrase in (
            "Surface assumptions",
            "Manage confusion actively",
            "Push back when warranted",
            "Enforce simplicity",
            "Maintain scope discipline",
            "Verify, don't assume",
        ):
            self.assertIn(phrase, text)
        self.assertIn("non-negotiable", text)

    def test_unknown_phase_is_rejected(self):
        rows = [
            {
                "skill": "explore",
                "phase": "teleport",
                "preceded-by": "",
                "followed-by": "",
                "output-location": "inline",
                "outputs": "x",
            }
        ]
        with self.assertRaises(SystemExit):
            gr.render(rows)


class ManifestLintTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "ai/skills/real-skill").mkdir(parents=True)
        (self.root / "ai/skills/real-skill/SKILL.md").write_text("x", encoding="utf-8")
        (self.root / ".claude").mkdir(parents=True)
        (self.root / ".claude/settings.json").write_text("{}", encoding="utf-8")
        self.manifest = self.root / "ai/skills/manifest.csv"
        self.addCleanup(self.tmp.cleanup)

    def rules(self):
        return {rule for rule, _ in check_manifest(self.root)}

    def test_clean_manifest_has_no_issues(self):
        self.manifest.write_text(
            HEADER + "real-skill,orient,,,inline,stuff\n", encoding="utf-8"
        )
        self.assertEqual(check_manifest(self.root), [])

    def test_row_naming_a_nonexistent_skill_fails(self):
        self.manifest.write_text(
            HEADER + "real-skill,orient,,,inline,stuff\nghost,orient,,,inline,stuff\n",
            encoding="utf-8",
        )
        self.assertIn("manifest-unknown-skill", self.rules())

    def test_neighbour_naming_a_nonexistent_skill_fails(self):
        self.manifest.write_text(
            HEADER + "real-skill,orient,ghost,,inline,stuff\n", encoding="utf-8"
        )
        self.assertIn("manifest-unknown-skill", self.rules())

    def test_enabled_skill_absent_from_the_manifest_fails(self):
        self.manifest.write_text(HEADER, encoding="utf-8")
        self.assertIn("manifest-missing-skill", self.rules())

    def test_disabled_skill_absent_from_the_manifest_is_fine(self):
        (self.root / ".claude/settings.json").write_text(
            '{"skillOverrides": {"real-skill": "off"}}', encoding="utf-8"
        )
        self.manifest.write_text(HEADER, encoding="utf-8")
        self.assertEqual(check_manifest(self.root), [])

    def test_wrong_columns_are_reported(self):
        self.manifest.write_text("skill,phase\nreal-skill,orient\n", encoding="utf-8")
        self.assertIn("manifest-malformed", self.rules())


if __name__ == "__main__":
    unittest.main()
