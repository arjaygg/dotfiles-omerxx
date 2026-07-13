import json
import subprocess
import sys
import unittest
from pathlib import Path

from scripts.bootstrap_check import DEFAULT_VARIABLES, verify_bootstrap


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CLIENTS = {"claude", "codex", "gemini", "cursor", "windsurf", "pctx"}


class BootstrapCheckTests(unittest.TestCase):
    def test_verifies_all_clients_twice_without_writing_runtime_files(self):
        before = {
            path: path.read_bytes()
            for path in (
                ROOT / "ai/config/manifest.json",
                ROOT / "ai/config/codex/config.base.toml",
            )
        }

        report = verify_bootstrap(ROOT, variables=DEFAULT_VARIABLES)

        after = {path: path.read_bytes() for path in before}
        self.assertEqual(set(report["clients"]), EXPECTED_CLIENTS)
        self.assertTrue(report["idempotent"])
        self.assertEqual(report["staged_client_count"], 6)
        self.assertTrue(report["staged_idempotent"])
        self.assertTrue(report["staged_cache_preserved"])
        self.assertTrue(report["temporary_stage_writes"])
        self.assertFalse(report["writes_performed"])
        self.assertFalse(report["runtime_writes"])
        self.assertEqual(before, after)
        for client in report["clients"].values():
            self.assertEqual(len(client["proposal_sha256"]), 64)

    def test_cli_emits_machine_readable_clean_machine_proof(self):
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/bootstrap_check.py"),
                "--root",
                str(ROOT),
                "--set",
                "PCTX_CONFIG=~/.config/pctx/pctx.json",
                "--set",
                "USER_NAME=portable-user",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema"], 1)
        self.assertTrue(payload["idempotent"])
        self.assertEqual(payload["client_count"], 6)
        self.assertEqual(payload["staged_client_count"], 6)
        self.assertTrue(payload["staged_idempotent"])
        self.assertTrue(payload["staged_cache_preserved"])
        self.assertFalse(payload["writes_performed"])

    def test_cli_rejects_malformed_variable_assignments(self):
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/bootstrap_check.py"),
                "--root",
                str(ROOT),
                "--set",
                "not-an-assignment",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid --set", result.stderr)


if __name__ == "__main__":
    unittest.main()
