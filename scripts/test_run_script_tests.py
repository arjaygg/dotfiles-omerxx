import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_script_tests import TestExclusion, load_exclusions, select_tests


def make_case(name: str, *, passes: bool) -> unittest.TestCase:
    def test_case(self):
        if not passes:
            self.fail("unrelated failure must propagate")

    case = type(name, (unittest.TestCase,), {"test_case": test_case, "__module__": __name__})
    return case("test_case")


def make_setup_failure_case(name: str) -> unittest.TestCase:
    @classmethod
    def set_up_class(cls):
        raise AssertionError("fixture setup must not run for an exact excluded class")

    def test_case(self):
        self.fail("unreachable")

    case = type(
        name,
        (unittest.TestCase,),
        {"setUpClass": set_up_class, "test_case": test_case, "__module__": __name__},
    )
    return case("test_case")


def run(suite: unittest.TestSuite) -> unittest.TestResult:
    return unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)


class RunScriptTestsTests(unittest.TestCase):
    def test_exclusion_group_expands_each_exact_test_id(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "exclusions.json"
            path.write_text(
                json.dumps(
                    {
                        "excluded_tests": [
                            {
                                "ids": ["one.Test.test_case", "two.Test.test_case"],
                                "dependency": "archived hook",
                                "reason": "fixture needs the active hook",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            exclusions = load_exclusions(path)

        self.assertEqual([exclusion.test_id for exclusion in exclusions], ["one.Test.test_case", "two.Test.test_case"])

    def test_disabled_mode_skips_only_the_exact_quarantined_test(self):
        passing = make_case("PassingCase", passes=True)
        failing = make_case("FailingCase", passes=False)
        exclusion = TestExclusion(failing.id(), "archived hook", "test fixture reads active hook")

        result = run(select_tests(unittest.TestSuite([passing, failing]), [exclusion], state="disabled"))

        self.assertTrue(result.wasSuccessful())
        self.assertEqual(result.testsRun, 2)
        self.assertEqual(len(result.skipped), 1)
        self.assertIn("archived hook", result.skipped[0][1])

    def test_enabled_mode_runs_a_quarantined_test_normally(self):
        failing = make_case("FailingCase", passes=False)
        exclusion = TestExclusion(failing.id(), "archived hook", "test fixture reads active hook")

        result = run(select_tests(unittest.TestSuite([failing]), [exclusion], state="enabled"))

        self.assertFalse(result.wasSuccessful())
        self.assertEqual(len(result.failures), 1)
        self.assertEqual(result.skipped, [])

    def test_unknown_exclusion_fails_selection(self):
        exclusion = TestExclusion("missing.Test.test_case", "archived hook", "stale record")

        with self.assertRaisesRegex(ValueError, "unknown tests"):
            select_tests(
                unittest.TestSuite([make_case("PassingCase", passes=True)]),
                [exclusion],
                state="disabled",
            )

    def test_enabled_mode_ignores_disabled_only_stale_exclusions(self):
        exclusion = TestExclusion("missing.Test.test_case", "archived hook", "stale disabled record")

        result = run(
            select_tests(
                unittest.TestSuite([make_case("PassingCase", passes=True)]),
                [exclusion],
                state="enabled",
            )
        )

        self.assertTrue(result.wasSuccessful())

    def test_failed_import_must_match_its_recorded_quarantined_dependency(self):
        failed = unittest.loader._FailedTest(
            "test_context_gate",
            ImportError("failed import\nModuleNotFoundError: No module named 'ai.context'"),
        )
        exclusion = TestExclusion(
            failed.id(),
            "archived ai.context module",
            "test imports the retired subject",
            "ModuleNotFoundError: No module named 'ai.context'",
        )
        result = run(select_tests(unittest.TestSuite([failed]), [exclusion], state="disabled"))
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(len(result.skipped), 1)

        unrelated = unittest.loader._FailedTest(
            "test_context_gate",
            ImportError(
                "failed import\nModuleNotFoundError: No module named 'ai.context'\n"
                "ModuleNotFoundError: No module named 'new_unrelated_dependency'"
            ),
        )
        with self.assertRaisesRegex(ValueError, "unexpected import failure"):
            select_tests(unittest.TestSuite([unrelated]), [exclusion], state="disabled")

    def test_fully_excluded_class_does_not_run_its_fixture_setup(self):
        test = make_setup_failure_case("ArchivedFixtureCase")
        exclusion = TestExclusion(test.id(), "archived hook", "fixture requires active hook")

        result = run(select_tests(unittest.TestSuite([test]), [exclusion], state="disabled"))

        self.assertTrue(result.wasSuccessful())
        self.assertEqual(len(result.skipped), 1)

    def test_unlisted_new_test_runs_by_default(self):
        passing = make_case("PassingCase", passes=True)
        failing = make_case("FailingCase", passes=False)
        exclusion = TestExclusion(passing.id(), "archived hook", "known integration")

        result = run(select_tests(unittest.TestSuite([passing, failing]), [exclusion], state="disabled"))

        self.assertEqual(result.testsRun, 2)
        self.assertEqual(len(result.skipped), 1)
        self.assertEqual(len(result.failures), 1)


if __name__ == "__main__":
    unittest.main()
