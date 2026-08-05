"""
TDD state machine — Option 1 enforcement.

Rules:
  - No tests at all → block (no test file exists for this code)
  - Tests failing (RED phase) → allow (implementing to fix them)
  - All tests pass, recent test edit → allow (stale test.json, new test written)
  - All tests pass, no recent test edit → block (write a failing test first)
"""
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class StateMachineResult:
    allowed: bool
    message: str = ""


def check(file_path: str, test_data: Optional[dict], modifications: Optional[list], config) -> StateMachineResult:
    if test_data is None:
        # No test.json — cannot enforce; fail open
        return StateMachineResult(allowed=True)

    num_failed, num_total = _count_tests(test_data)

    if num_total == 0:
        return StateMachineResult(
            allowed=False,
            message=(
                f"TDD: No tests found (test.json shows 0 tests). "
                f"Write a test for {Path(file_path).name} before implementing."
            ),
        )

    # RED phase: failing tests → allow implementation
    if num_failed > 0:
        return StateMachineResult(allowed=True)

    # GREEN phase: all passing.
    # Allow if a test file was recently modified — guards against stale test.json
    # (agent wrote a failing test but suite hasn't re-run yet).
    if _recent_test_modification(modifications, config):
        return StateMachineResult(allowed=True)

    return StateMachineResult(
        allowed=False,
        message=(
            "TDD: All tests pass. Write a failing test first, then implement. "
            "(If you just wrote a test, run the test suite so test.json reflects current state.)"
        ),
    )


def _recent_test_modification(modifications, config) -> bool:
    """Check whether a test file was recently touched via multiple signals."""
    # Signal 1: modifications.json is a list of prior hook events (tdd-guard history format)
    if isinstance(modifications, list):
        window = modifications[-config.recent_modification_window:]
        for mod in window:
            path = mod.get("path", "") if isinstance(mod, dict) else str(mod)
            if config.is_test_file(path):
                return True

    # Signal 2: modifications.json is the current hook event (single dict)
    # — not useful for history, skip

    # Signal 3: git status — any test file with unstaged/staged changes
    return _git_has_modified_test_file(config)


def _git_has_modified_test_file(config) -> bool:
    import subprocess
    try:
        result = subprocess.run(
            ["git", "status", "--short", "--porcelain"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            # format: "XY path" or "XY old -> new"
            parts = line.strip().split()
            if not parts:
                continue
            file_path = parts[-1]
            if config.is_test_file(file_path):
                return True
    except Exception:
        pass
    return False


def _count_tests(test_data: dict):
    """Return (num_failed, num_total) — handles both tdd-guard schema variants.

    tdd-guard-vitest schema: {reason, testModules: [{moduleId, tests: [{state}]}]}
    Legacy schema:           {numFailedTests, numTotalTests}
    """
    # tdd-guard-vitest format
    if "testModules" in test_data:
        total = failed = 0
        for module in test_data.get("testModules", []):
            for test in module.get("tests", []):
                total += 1
                if test.get("state") != "passed":
                    failed += 1
        # Fast path: use top-level reason when counts come out ambiguous
        if total == 0 and test_data.get("reason") == "failed":
            return 1, 1  # Something failed, treat as RED
        return failed, total

    # Legacy / custom reporter format
    return (
        test_data.get("numFailedTests", 0),
        test_data.get("numTotalTests", 0),
    )
