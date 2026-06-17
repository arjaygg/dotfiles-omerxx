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

    num_failed = test_data.get("numFailedTests", 0)
    num_total = test_data.get("numTotalTests", 0)

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
    # Allow if a test file was recently modified (guards against stale test.json —
    # the agent wrote a failing test but the suite hasn't re-run yet).
    if _recent_test_modification(modifications or [], config):
        return StateMachineResult(allowed=True)

    return StateMachineResult(
        allowed=False,
        message=(
            "TDD: All tests pass. Write a failing test first, then implement. "
            "(If you just wrote a test, run the test suite so test.json reflects current state.)"
        ),
    )


def _recent_test_modification(modifications: list, config) -> bool:
    window = modifications[-config.recent_modification_window:]
    for mod in window:
        path = mod.get("path", "") if isinstance(mod, dict) else str(mod)
        if config.is_test_file(path):
            return True
    return False
