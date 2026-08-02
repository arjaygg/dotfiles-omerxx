#!/usr/bin/env python3
"""Contract tests for the stop.sh <-> lifecycle-hook.sh Stop handoff.

Regression coverage for the deadlock introduced in 440c8ae: lifecycle-hook.sh
swallowed the unbound Stop envelope, so stop.sh saw empty output, could not
resolve a binding, and blocked Stop unconditionally. Every unbound session in
an opted-in repo became unable to end.

stop.sh's contract (stop.sh, "Only an exact rc=0 unbound envelope may fall back
to the legacy gate") requires the bridge to *emit* that envelope. These tests
pin both halves so the two scripts cannot drift apart again.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS = REPO_ROOT / ".claude" / "hooks"
BRIDGE = HOOKS / "lifecycle-hook.sh"
STOP = HOOKS / "stop.sh"
VALIDATOR = HOOKS / "lifecycle-envelope.py"

UNBOUND_STOP_ENVELOPE = {
    "lifecycle_hook": {
        "schema_version": 1,
        "processed": True,
        "event": "Stop",
        "binding": "unbound",
    }
}

FAIL_CLOSED_REASON = (
    "Lifecycle Stop bridge output was unavailable or invalid; failed closed."
)


def run(script: Path, payload: dict, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(script), *args],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def stop_payload(session_id: str = "test-unbound-session") -> dict:
    return {"session_id": session_id, "cwd": str(REPO_ROOT)}


class UnboundStopBridgeTest(unittest.TestCase):
    """The bridge must emit the unbound Stop envelope, not swallow it."""

    def test_bridge_emits_unbound_stop_envelope(self):
        result = run(BRIDGE, stop_payload(), "Stop")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(
            result.stdout.strip(),
            "bridge emitted no stdout for an unbound Stop; stop.sh cannot "
            "distinguish this from a broken bridge and will fail closed",
        )
        self.assertEqual(json.loads(result.stdout), UNBOUND_STOP_ENVELOPE)

    def test_validator_resolves_the_emitted_envelope_as_unbound(self):
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), "Stop"],
            input=json.dumps(UNBOUND_STOP_ENVELOPE),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "unbound")


class UnboundStopDispatcherTest(unittest.TestCase):
    """stop.sh must fall through to the legacy gate rather than fail closed."""

    def test_stop_does_not_emit_the_fail_closed_block(self):
        result = run(STOP, stop_payload())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(
            FAIL_CLOSED_REASON,
            result.stdout,
            "unbound Stop was rejected as a broken bridge — the session can "
            "never end (regression of 440c8ae)",
        )

    def test_stop_output_is_either_empty_or_a_legacy_gate_decision(self):
        result = run(STOP, stop_payload())
        for line in filter(None, (ln.strip() for ln in result.stdout.splitlines())):
            payload = json.loads(line)
            reason = payload.get("reason", "")
            self.assertNotEqual(reason, FAIL_CLOSED_REASON)


if __name__ == "__main__":
    unittest.main()
