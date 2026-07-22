import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHIM = ROOT / ".local/bin/agy-mcp-legacy-shim.py"
LEGACY_BACKEND = """
import json
import sys

print('legacy test backend stderr', file=sys.stderr, flush=True)

for line in sys.stdin:
    message = json.loads(line)
    if message.get('method') == 'server/discover':
        print('server/discover must not reach the legacy backend', file=sys.stderr, flush=True)
        raise SystemExit(91)
    if message.get('method') == 'notifications/roots/list_changed':
        print('pre-initialize roots notification must not reach the legacy backend', file=sys.stderr, flush=True)
        raise SystemExit(92)
    if message.get('method') == 'initialize':
        print(json.dumps({
            'jsonrpc': '2.0',
            'id': message.get('id'),
            'result': {
                'protocolVersion': '2025-06-18',
                'capabilities': {},
                'serverInfo': {'name': 'legacy-test-server', 'version': '1.0.0'},
            },
        }), flush=True)
"""


def send(process: subprocess.Popen[str], message: dict[str, object]) -> None:
    assert process.stdin is not None
    process.stdin.write(json.dumps(message) + "\n")
    process.stdin.flush()


def receive(process: subprocess.Popen[str]) -> dict[str, object]:
    assert process.stdout is not None
    line = process.stdout.readline()
    if not line:
        raise AssertionError("shim closed stdout before returning an MCP response")
    return json.loads(line)


class AgyMcpLegacyShimTests(unittest.TestCase):
    def start_shim(self) -> subprocess.Popen[str]:
        return subprocess.Popen(
            [sys.executable, str(SHIM), "--", sys.executable, "-c", LEGACY_BACKEND],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    def stop(self, process: subprocess.Popen[str]) -> tuple[int, str, str]:
        if process.stdin is not None and not process.stdin.closed:
            process.stdin.close()
        returncode = process.wait(timeout=5)
        stdout = process.stdout.read() if process.stdout is not None else ""
        stderr = process.stderr.read() if process.stderr is not None else ""
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()
        return returncode, stdout, stderr

    def test_discovery_is_rejected_without_starting_legacy_backend(self):
        process = self.start_shim()
        try:
            send(process, {"jsonrpc": "2.0", "id": 0, "method": "server/discover", "params": {}})

            response = receive(process)

            self.assertEqual(response["id"], 0)
            self.assertEqual(response["error"]["code"], -32601)
            self.assertIn("server/discover", response["error"]["message"])
        finally:
            returncode, stdout, stderr = self.stop(process)

        self.assertEqual(returncode, 0, stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertNotIn("legacy test backend stderr", json.dumps(response))

    def test_preinitialize_notifications_are_silent_then_initialize_is_forwarded(self):
        process = self.start_shim()
        try:
            send(process, {"jsonrpc": "2.0", "method": "server/discover", "params": {}})
            send(
                process,
                {
                    "jsonrpc": "2.0",
                    "method": "notifications/roots/list_changed",
                    "params": {},
                },
            )

            send(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "initialize",
                    "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {}},
                },
            )
            response = receive(process)

            self.assertEqual(response["id"], 2)
            self.assertEqual(response["result"]["serverInfo"]["name"], "legacy-test-server")
        finally:
            returncode, stdout, stderr = self.stop(process)

        self.assertEqual(returncode, 0, stderr)
        self.assertEqual(stdout, "")
        self.assertIn("legacy test backend stderr", stderr)
        self.assertNotIn("pre-initialize roots notification", stderr)
        self.assertNotIn("legacy test backend stderr", json.dumps(response))


if __name__ == "__main__":
    unittest.main()
