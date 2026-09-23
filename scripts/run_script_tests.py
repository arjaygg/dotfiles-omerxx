#!/usr/bin/env python3
"""Run all script tests, explicitly skipping quarantined integrations only when disabled."""

from __future__ import annotations

import argparse
import json
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

try:
    from scripts.harness_state_check import check_harness_state
except ModuleNotFoundError:  # Direct execution adds scripts/ rather than the repo root.
    from harness_state_check import check_harness_state


EXCLUSIONS_FILE = Path("scripts/fixtures/disabled-harness-exclusions.json")


@dataclass(frozen=True)
class TestExclusion:
    test_id: str
    dependency: str
    reason: str
    expected_error: str | None = None

    @property
    def skip_reason(self) -> str:
        return f"quarantined dependency: {self.dependency}; {self.reason}"


def load_exclusions(path: Path) -> tuple[TestExclusion, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("excluded_tests")
    if not isinstance(entries, list):
        raise ValueError("excluded_tests must be a list")

    exclusions: list[TestExclusion] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("every exclusion must be an object")
        test_ids = entry.get("ids")
        dependency = entry.get("dependency")
        reason = entry.get("reason")
        expected_error = entry.get("expected_error")
        if not isinstance(test_ids, list) or not test_ids:
            raise ValueError("every exclusion group needs a non-empty ids list")
        if not all(isinstance(test_id, str) and test_id.strip() for test_id in test_ids):
            raise ValueError("every excluded test ID must be non-empty text")
        if not all(isinstance(value, str) and value.strip() for value in (dependency, reason)):
            raise ValueError("every exclusion group needs dependency and reason")
        if expected_error is not None and (not isinstance(expected_error, str) or not expected_error):
            raise ValueError("expected_error must be non-empty text when provided")
        exclusions.extend(
            TestExclusion(test_id, dependency, reason, expected_error) for test_id in test_ids
        )

    ids = [exclusion.test_id for exclusion in exclusions]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate test IDs in disabled-harness exclusions")
    return tuple(exclusions)


def flatten_tests(suite: unittest.TestSuite) -> Iterable[unittest.TestCase]:
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from flatten_tests(test)
        else:
            yield test


def select_tests(
    suite: unittest.TestSuite,
    exclusions: Sequence[TestExclusion],
    *,
    state: str,
) -> unittest.TestSuite:
    tests = list(flatten_tests(suite))
    if state != "disabled":
        return suite

    by_id = {exclusion.test_id: exclusion for exclusion in exclusions}
    discovered = {test.id() for test in tests}
    stale = sorted(set(by_id) - discovered)
    if stale:
        raise ValueError(f"disabled-harness exclusions reference unknown tests: {', '.join(stale)}")

    for test in tests:
        exclusion = by_id.get(test.id())
        if not exclusion or not test.id().startswith("unittest.loader._FailedTest."):
            continue
        error = getattr(test, "_exception", None)
        final_line = next(
            (line.strip() for line in reversed(str(error).splitlines()) if line.strip()), ""
        )
        if (
            not isinstance(error, ImportError)
            or not exclusion.expected_error
            or final_line != exclusion.expected_error
        ):
            raise ValueError(f"unexpected import failure for excluded test: {test.id()}")

    tests_by_class: dict[type[unittest.TestCase], list[unittest.TestCase]] = {}
    for test in tests:
        tests_by_class.setdefault(type(test), []).append(test)

    for test_class, class_tests in tests_by_class.items():
        class_exclusions = [by_id.get(test.id()) for test in class_tests]
        if all(class_exclusions) and "setUpClass" in test_class.__dict__:
            setattr(test_class, "__unittest_skip__", True)
            setattr(test_class, "__unittest_skip_why__", class_exclusions[0].skip_reason)
            continue
        for test, exclusion in zip(class_tests, class_exclusions):
            if exclusion:
                def skipped() -> None:
                    return None

                setattr(skipped, "__unittest_skip__", True)
                setattr(skipped, "__unittest_skip_why__", exclusion.skip_reason)
                setattr(test, test._testMethodName, skipped)
    return suite


def discover_tests(root: Path) -> unittest.TestSuite:
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return unittest.defaultTestLoader.discover(
        start_dir=str(root / "scripts"), pattern="test_*.py"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    root = args.root.resolve()

    state, results = check_harness_state(root)
    if state not in {"enabled", "disabled"}:
        failures = [f"{result.path}: {result.message}" for result in results if result.status == "fail"]
        print("invalid harness state: " + "; ".join(failures), file=sys.stderr)
        return 2

    try:
        exclusions = load_exclusions(root / EXCLUSIONS_FILE)
        suite = select_tests(discover_tests(root), exclusions, state=state)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"script-test selection failed: {error}", file=sys.stderr)
        return 2

    active_exclusions = exclusions if state == "disabled" else ()
    print(
        json.dumps(
            {
                "harness_state": state,
                "quarantined_test_count": len(active_exclusions),
                "quarantined_test_manifest": str(EXCLUSIONS_FILE) if active_exclusions else None,
            }
        )
    )
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
