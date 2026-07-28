import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

from scripts.context_retrieval_benchmark import (
    MARKDOWN_REQUIREMENTS,
    RECALL_TERMS,
    TASK_QUERY,
    benchmark,
    score_output,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "scripts" / "fixtures" / "context-routing" / "complex.md"


class ContextRetrievalBenchmarkTests(unittest.TestCase):
    def test_exact_output_has_full_fidelity_and_recall(self):
        source = ("\n".join(RECALL_TERMS) + "\n").encode()
        score = score_output(source, source)
        self.assertTrue(score["byte_fidelity"])
        self.assertEqual(score["recall_at_5"], 1.0)
        self.assertEqual(score["output_ratio"], 1.0)

    def test_focused_output_scores_recall_and_reduction(self):
        source = (("\n".join(RECALL_TERMS) + "\n") * 100).encode()
        focused = ("\n".join(RECALL_TERMS) + "\n").encode()
        score = score_output(source, focused)
        self.assertEqual(score["recall_at_5"], 1.0)
        self.assertLessEqual(score["output_ratio"], 0.25)

    def test_markdown_fidelity_requires_complete_contiguous_structures(self):
        source = FIXTURE.read_bytes()
        disordered = "\n".join(RECALL_TERMS).encode()
        exact_score = score_output(source, source)
        disordered_score = score_output(source, disordered)
        self.assertEqual(exact_score["markdown_fidelity"], 1.0)
        self.assertEqual(disordered_score["recall_at_5"], 1.0)
        self.assertEqual(disordered_score["markdown_fidelity"], 0.0)

    def test_portable_wrapper_preserves_exact_mode_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "exact.md"
            source = bytes(range(256)) + b"\x00no trailing newline"
            path.write_bytes(source)
            for mode in ("raw", "full"):
                invocations = (
                    ("read", str(path), "-m", mode),
                    ("read", "--mode", mode, str(path)),
                    ("read", f"--mode={mode}", str(path)),
                )
                for arguments in invocations:
                    with self.subTest(mode=mode, arguments=arguments):
                        result = subprocess.run(
                            [
                                str(ROOT / ".local/bin/lean_ctx_wrapper.sh"),
                                *arguments,
                            ],
                            env=os.environ,
                            check=False,
                            capture_output=True,
                        )
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(result.stdout, source)

    def test_benchmark_runs_real_task_setup_and_measures_cache_reread(self):
        with tempfile.TemporaryDirectory() as td:
            binary = Path(td) / "fake-lean-ctx"
            focused = "\n\n".join(MARKDOWN_REQUIREMENTS.values()).encode()
            binary.write_text(
                textwrap.dedent(
                    f"""\
                    #!/usr/bin/env python3
                    import os
                    import sys
                    from pathlib import Path

                    arguments = sys.argv[1:]
                    data_dir = Path(os.environ["LEAN_CTX_DATA_DIR"])
                    data_dir.mkdir(parents=True, exist_ok=True)
                    if arguments[:2] == ["session", "task"]:
                        (data_dir / "task.txt").write_text(" ".join(arguments[2:]))
                    elif arguments and arguments[0] == "read":
                        path = Path(next(value for value in arguments[1:] if not value.startswith("-") and value not in ("raw", "full", "task")))
                        mode_index = arguments.index("-m") + 1
                        mode = arguments[mode_index]
                        if mode in ("raw", "full"):
                            sys.stdout.buffer.write(path.read_bytes())
                        elif (data_dir / "task-read").exists():
                            sys.stdout.buffer.write(b"[Archived:task-cache]\\n")
                        else:
                            (data_dir / "task-read").touch()
                            sys.stdout.buffer.write({focused!r})
                    else:
                        raise SystemExit(2)
                    """
                ),
                encoding="utf-8",
            )
            binary.chmod(0o755)

            report = benchmark(binary, FIXTURE, repetitions=600, timeout=5)

        self.assertEqual(report["task_query"], TASK_QUERY)
        self.assertTrue(report["ok"], report)
        self.assertLessEqual(
            report["modes"]["task_reread"]["estimated_tokens"],
            32,
        )

    def test_benchmark_does_not_claim_cache_success_for_repeated_full_output(self):
        with tempfile.TemporaryDirectory() as td:
            binary = Path(td) / "fake-lean-ctx"
            binary.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env python3
                    import sys
                    from pathlib import Path

                    arguments = sys.argv[1:]
                    if arguments[:2] == ["session", "task"]:
                        raise SystemExit(0)
                    if arguments and arguments[0] == "read":
                        path = Path(next(value for value in arguments[1:] if not value.startswith("-") and value not in ("raw", "full", "task")))
                        sys.stdout.buffer.write(path.read_bytes())
                        raise SystemExit(0)
                    raise SystemExit(2)
                    """
                ),
                encoding="utf-8",
            )
            binary.chmod(0o755)

            report = benchmark(binary, FIXTURE, repetitions=100, timeout=5)

        self.assertFalse(report["targets"]["focused_ratio"])
        self.assertFalse(report["targets"]["cache_reread"])
        self.assertFalse(report["ok"])
        self.assertTrue(
            any("task reread returned" in defect for defect in report["defects"])
        )


if __name__ == "__main__":
    unittest.main()
