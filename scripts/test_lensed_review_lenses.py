"""Data-contract tests for ai/skills/lensed-review/lenses.toml (Goal 05 Step 10).

Step 10's Accepts requires the five-keys-per-lens schema and that a lens with an empty
`instruction` is skipped. Nothing executable parsed this file — `grep -rn 'lenses.toml'` over
*.py/*.js/*.sh returned zero hits — so both were prose plus an LLM-graded Tier-3 expectation, and
the data contract could drift silently. These tests make the contract deterministic. They do not
invent a runtime: skipping is still performed by the skill's prompt, but the *shape* it relies on
is now pinned.
"""
import tomllib
import unittest
from pathlib import Path

LENSES = Path(__file__).resolve().parents[1] / "ai/skills/lensed-review/lenses.toml"

# §22's per-lens schema.
REQUIRED_KEYS = {"code", "applies_to", "when", "after", "instruction"}


def enabled(lenses):
    """The skill's own rule: an entry with an empty `instruction` is disabled."""
    return {name for name, body in lenses.items() if str(body.get("instruction", "")).strip()}


class LensesContractTests(unittest.TestCase):
    def setUp(self):
        with LENSES.open("rb") as fh:
            self.doc = tomllib.load(fh)
        self.lenses = {k: v for k, v in self.doc.items() if isinstance(v, dict)}

    def test_parses_and_declares_at_least_one_lens(self):
        self.assertTrue(self.lenses, "no lens tables found")

    def test_every_lens_has_exactly_the_five_keys(self):
        for name, body in self.lenses.items():
            with self.subTest(lens=name):
                self.assertEqual(
                    set(body) & REQUIRED_KEYS, REQUIRED_KEYS,
                    f"{name} is missing {REQUIRED_KEYS - set(body)}",
                )
                self.assertFalse(
                    set(body) - REQUIRED_KEYS,
                    f"{name} has unexpected keys {set(body) - REQUIRED_KEYS}",
                )

    def test_empty_instruction_lens_is_excluded_from_the_enabled_set(self):
        on = enabled(self.lenses)
        empties = {n for n, b in self.lenses.items()
                   if not str(b.get("instruction", "")).strip()}
        self.assertTrue(
            empties,
            "fixture assumption gone: no lens has an empty instruction, so this test no longer "
            "proves the skip rule. Point it at whichever lens is disabled, or delete it.",
        )
        for n in empties:
            self.assertNotIn(n, on, f"{n} has an empty instruction but is still enabled")

    def test_a_lens_with_a_real_instruction_is_enabled(self):
        self.assertIn("correctness", self.lenses, "the correctness lens is expected to exist")
        self.assertIn("correctness", enabled(self.lenses))

    def test_not_every_lens_is_skipped(self):
        """A config where everything is disabled is a bug, not a valid state — the skill would
        run and produce nothing while reporting success."""
        self.assertTrue(enabled(self.lenses), "every lens is disabled")


if __name__ == "__main__":
    unittest.main()
