"""Unit tests for the skill customization resolver.

One test per merge rule (scalars, tables, keyed arrays of tables by both `code` and `id`,
plain arrays), plus resolution order and the `file:` partial-failure contract.
"""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import resolve_customization as rc  # noqa: E402


class MergeRuleTests(unittest.TestCase):
    def test_scalars_override(self):
        merged = rc.merge({"model": "sonnet", "depth": 2}, {"model": "opus"})
        self.assertEqual(merged, {"model": "opus", "depth": 2})

    def test_tables_deep_merge(self):
        base = {"output": {"format": "table", "path": "reports/a.md", "nested": {"x": 1}}}
        incoming = {"output": {"format": "json", "nested": {"y": 2}}}
        self.assertEqual(
            rc.merge(base, incoming),
            {
                "output": {
                    "format": "json",
                    "path": "reports/a.md",
                    "nested": {"x": 1, "y": 2},
                }
            },
        )

    def test_code_keyed_table_arrays_replace_on_match_append_on_new(self):
        base = {"lens": [{"code": "security", "on": True}, {"code": "style", "on": True}]}
        incoming = {"lens": [{"code": "style", "on": False}, {"code": "perf", "on": True}]}
        self.assertEqual(
            rc.merge(base, incoming)["lens"],
            [
                {"code": "security", "on": True},
                {"code": "style", "on": False},
                {"code": "perf", "on": True},
            ],
        )

    def test_id_keyed_table_arrays_replace_on_match_append_on_new(self):
        base = {"step": [{"id": 1, "name": "scope"}, {"id": 2, "name": "review"}]}
        incoming = {"step": [{"id": 2, "name": "triage"}, {"id": 3, "name": "report"}]}
        self.assertEqual(
            rc.merge(base, incoming)["step"],
            [
                {"id": 1, "name": "scope"},
                {"id": 2, "name": "triage"},
                {"id": 3, "name": "report"},
            ],
        )

    def test_unkeyed_table_arrays_append(self):
        base = {"hook": [{"cmd": "a"}]}
        incoming = {"hook": [{"cmd": "b"}]}
        self.assertEqual(rc.merge(base, incoming)["hook"], [{"cmd": "a"}, {"cmd": "b"}])

    def test_plain_arrays_append(self):
        base = {"activation_steps_append": ["one"]}
        incoming = {"activation_steps_append": ["two"]}
        self.assertEqual(
            rc.merge(base, incoming)["activation_steps_append"], ["one", "two"]
        )


class ResolutionOrderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.skills = root / "skills"
        self.custom = root / "custom"
        (self.skills / "demo").mkdir(parents=True)
        self.custom.mkdir(parents=True)
        self.addCleanup(self.tmp.cleanup)

    def write(self, path: Path, text: str):
        path.write_text(text, encoding="utf-8")

    def test_user_layer_wins_over_team_wins_over_base(self):
        self.write(self.skills / "demo/customize.toml", 'tier = "base"\nkept = "yes"\n')
        self.write(self.custom / "demo.toml", 'tier = "team"\n')
        self.write(self.custom / "demo.user.toml", 'tier = "user"\n')
        res = rc.resolve("demo", self.skills, self.custom)
        self.assertEqual(res.config["tier"], "user")
        self.assertEqual(res.config["kept"], "yes")
        self.assertEqual(len(res.layers), 3)

    def test_missing_optional_layers_are_skipped(self):
        self.write(self.skills / "demo/customize.toml", 'tier = "base"\n')
        res = rc.resolve("demo", self.skills, self.custom)
        self.assertEqual(res.config, {"tier": "base"})
        self.assertEqual(len(res.layers), 1)
        self.assertEqual(res.missing_files, [])

    def test_file_value_loads_referenced_contents(self):
        self.write(self.skills / "demo/guidance.md", "be careful\n")
        self.write(self.skills / "demo/customize.toml", 'review_guidance = "file:guidance.md"\n')
        res = rc.resolve("demo", self.skills, self.custom)
        self.assertEqual(res.config["review_guidance"], "be careful\n")
        self.assertEqual(res.missing_files, [])

    def test_missing_file_value_is_named_and_skipped(self):
        self.write(self.skills / "demo/customize.toml", 'review_guidance = "file:absent.md"\n')
        res = rc.resolve("demo", self.skills, self.custom)
        self.assertEqual(res.missing_files, ["absent.md"])
        self.assertIn("absent.md", res.header())
        # resolution continues: the layer still applied, the value is left verbatim
        self.assertEqual(res.config["review_guidance"], "file:absent.md")
        self.assertEqual(len(res.layers), 1)


if __name__ == "__main__":
    unittest.main()
