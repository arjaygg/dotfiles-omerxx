#!/usr/bin/env python3
"""Run hook fixtures and assert structured allow/deny behavior."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


VALID_OUTPUT_MODES = frozenset({"empty", "decision"})


@dataclass(frozen=True)
class HookResult:
    returncode: int
    stdout: str
    stderr: str


def load_manifest(path: Path) -> list[dict[str, object]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("fixture manifest must be an array")
    for case in value:
        if not isinstance(case, dict) or not isinstance(case.get("name"), str):
            raise ValueError("each fixture must be an object with a name")
        if case.get("expect") not in {"allow", "ask", "deny"}:
            raise ValueError(f"{case['name']}: expect must be allow, ask, or deny")
        event = case.get("event", "PreToolUse")
        if not isinstance(event, str) or not event:
            raise ValueError(f"{case['name']}: event must be a non-empty string")
        expected_exit = case.get("expected_exit", 0)
        if isinstance(expected_exit, bool) or not isinstance(expected_exit, int) or expected_exit < 0:
            raise ValueError(f"{case['name']}: expected_exit must be a non-negative integer")
        output_mode = case.get("output")
        if output_mode is not None and output_mode not in VALID_OUTPUT_MODES:
            raise ValueError(f"{case['name']}: output must be empty or decision")
        if not isinstance(case.get("input"), dict):
            raise ValueError(f"{case['name']}: input must be an object")
        if "expected_updated_input" in case:
            expected = case["expected_updated_input"]
            if not isinstance(expected, dict):
                raise ValueError(f"{case['name']}: expected_updated_input must be an object")
            tool_input = case["input"].get("tool_input")
            if isinstance(tool_input, dict):
                missing = sorted(set(tool_input) - set(expected))
                if missing:
                    names = ", ".join(missing)
                    raise ValueError(f"{case['name']}: expected_updated_input must preserve keys: {names}")
        if "expected_input" in case and not isinstance(case["expected_input"], dict):
            raise ValueError(f"{case['name']}: expected_input must be an object")
    return value


def run_case(hook: Path, case: dict[str, object]) -> HookResult:
    completed = subprocess.run(
        ["bash", str(hook)],
        input=json.dumps(case["input"]),
        capture_output=True,
        text=True,
        check=False,
    )
    return HookResult(completed.returncode, completed.stdout, completed.stderr)


def check_result(case: dict[str, object], returncode: int, stdout: str, stderr: str) -> list[str]:
    expect = case["expect"]
    failures: list[str] = []
    expected_exit = case.get("expected_exit", 0)
    if returncode != expected_exit:
        failures.append(f"expected exit {expected_exit}, got {returncode}")
    expects_rewrite = "expected_updated_input" in case or "expected_input" in case
    output_mode = case.get(
        "output",
        "empty" if expect == "allow" and not expects_rewrite else "decision",
    )
    if output_mode == "empty":
        if stdout.strip():
            failures.append("empty-output fixture must produce no stdout")
        return failures

    try:
        decision = json.loads(stdout)
    except json.JSONDecodeError:
        failures.append("structured fixture must emit exactly one JSON decision on stdout")
        return failures
    if "expected_input" in case:
        if decision != case["expected_input"]:
            failures.append("fixture raw input does not match expected rewrite")
        return failures
    output = decision.get("hookSpecificOutput") if isinstance(decision, dict) else None
    if not isinstance(output, dict):
        failures.append("structured fixture is missing hookSpecificOutput")
        return failures
    expected_event = case.get("event", "PreToolUse")
    if output.get("hookEventName") != expected_event:
        failures.append(f"structured fixture must identify {expected_event}")
    if output.get("permissionDecision") != expect:
        failures.append(f"{expect} fixture must set permissionDecision={expect}")
    if not isinstance(output.get("permissionDecisionReason"), str) or not output["permissionDecisionReason"]:
        failures.append(f"{expect} fixture must include a reason")
    if "updatedInput" in output and not isinstance(output["updatedInput"], dict):
        failures.append("updatedInput must be an object when present")
    if expects_rewrite and output.get("updatedInput") != case["expected_updated_input"]:
        failures.append("fixture updatedInput does not match expected rewrite")
    return failures


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hook", type=Path)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args(argv)
    failures = 0
    for case in load_manifest(args.manifest):
        result = run_case(args.hook, case)
        errors = check_result(case, result.returncode, result.stdout, result.stderr)
        if errors:
            failures += 1
            print(f"FAIL {case['name']}: {'; '.join(errors)}")
        else:
            print(f"PASS {case['name']}")
    print(f"results: {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
