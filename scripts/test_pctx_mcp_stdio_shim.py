import importlib.util
import io
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHIM = ROOT / "ai/bin/pctx-mcp-stdio-shim.py"


def load_shim():
    spec = importlib.util.spec_from_file_location("pctx_mcp_stdio_shim", SHIM)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CaptureStderr:
    def __init__(self):
        self.buffer = io.BytesIO()

    def flush(self):
        pass


class PctxMcpStdioShimTests(unittest.TestCase):
    def test_stderr_to_stderr_drains_binary_pipe_without_buffer_attribute(self):
        shim = load_shim()
        capture = CaptureStderr()
        original_stderr = shim.sys.stderr
        shim.sys.stderr = capture
        try:
            child = types.SimpleNamespace(stderr=io.BytesIO(b"serena startup noise"))

            shim.stderr_to_stderr(child)
        finally:
            shim.sys.stderr = original_stderr

        self.assertEqual(capture.buffer.getvalue(), b"serena startup noise")


if __name__ == "__main__":
    unittest.main()
