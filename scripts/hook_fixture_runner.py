#!/usr/bin/env python3
"""Run hook fixtures and assert structured hook output behavior."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


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
        if case.get("expect") not in {"allow", "deny", "ask", "rewrite", "context"}:
            raise ValueError(f"{case['name']}: expect must be allow, deny, ask, rewrite, or context")
        if not isinstance(case.get("input"), dict):
            raise ValueError(f"{case['name']}: input must be an object")
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
    expected_event = str(case.get("event", "PreToolUse"))
    failures: list[str] = []
    if returncode != 0:
        failures.append(f"expected exit 0, got {returncode}")
    if expect == "allow":
        if stdout.strip():
            failures.append("allow fixture must produce no stdout")
        return failures

    decision = _parse_stdout_json(stdout)
    if decision is None:
        failures.append(f"{expect} fixture must emit JSON on stdout")
        return failures
    output = decision.get("hookSpecificOutput") if isinstance(decision, dict) else None
    if not isinstance(output, dict):
        failures.append(f"{expect} fixture is missing hookSpecificOutput")
        return failures
    if output.get("hookEventName") != expected_event:
        failures.append(f"{expect} fixture must identify {expected_event}")
    if expect in {"deny", "ask", "rewrite"}:
        expected_decision = "allow" if expect == "rewrite" else expect
        if output.get("permissionDecision") != expected_decision:
            failures.append(f"{expect} fixture must set permissionDecision={expected_decision}")
        if not isinstance(output.get("permissionDecisionReason"), str) or not output["permissionDecisionReason"]:
            failures.append(f"{expect} fixture must include a reason")
    if expect == "rewrite":
        updated = output.get("updatedInput")
        if not isinstance(updated, dict):
            failures.append("rewrite fixture must include object updatedInput")
        else:
            original = case.get("input", {}).get("tool_input") if isinstance(case.get("input"), dict) else None
            if isinstance(original, dict):
                missing = sorted(key for key in original if key not in updated)
                if missing:
                    failures.append(f"rewrite fixture updatedInput dropped original keys: {', '.join(missing)}")
            for key, value in case.get("expected_updated_input", {}).items():
                if updated.get(key) != value:
                    failures.append(f"rewrite fixture updatedInput.{key} mismatch")
    if expect == "context":
        context = output.get("additionalContext")
        if not isinstance(context, str) or not context:
            failures.append("context fixture must include additionalContext")
    return failures


def _parse_stdout_json(stdout: str) -> dict[str, object] | None:
    try:
        decision = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    return decision if isinstance(decision, dict) else None


def summarize_run(
    cases: Sequence[dict[str, object]], failures_by_case: dict[str, list[str]]
) -> dict[str, object]:
    failed_cases = sorted(failures_by_case)
    return {
        "total": len(cases),
        "passed": len(cases) - len(failed_cases),
        "failed": len(failed_cases),
        "failed_cases": failed_cases,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hook", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)
    cases = load_manifest(args.manifest)
    failures_by_case: dict[str, list[str]] = {}
    for case in cases:
        result = run_case(args.hook, case)
        errors = check_result(case, result.returncode, result.stdout, result.stderr)
        if errors:
            failures_by_case[str(case["name"])] = errors
            if not args.summary:
                print(f"FAIL {case['name']}: {'; '.join(errors)}")
        elif not args.summary:
            print(f"PASS {case['name']}")
    if args.summary:
        print(json.dumps(summarize_run(cases, failures_by_case), indent=2))
    else:
        print(f"results: {len(failures_by_case)} failed")
    return 1 if failures_by_case else 0


if __name__ == "__main__":
    sys.exit(main())
