import unittest

from scripts.context_routing_report import summarize_metrics


class ContextRoutingReportTests(unittest.TestCase):
    def test_report_summarizes_required_observability_fields(self):
        metrics = [
            {
                "decision": "allow",
                "reason_code": "small-read",
                "size_class": "small",
                "requested_mode": "task",
                "returned_tokens": 120,
                "cache_hit": False,
            },
            {
                "decision": "warn",
                "reason_code": "medium-unscoped-read",
                "size_class": "medium",
                "requested_mode": None,
                "returned_tokens": 800,
                "cache_hit": False,
            },
            {
                "decision": "allow",
                "reason_code": "exactness-escape",
                "size_class": "large",
                "requested_mode": "raw",
                "returned_tokens": 4_100,
                "cache_hit": True,
            },
            {
                "decision": "allow",
                "reason_code": "bounded-output",
                "returned_tokens": 50,
            },
            {
                "decision": "allow",
                "reason_code": "unrelated-tool",
            },
            {
                "decision": "deny",
                "reason_code": "false-positive",
            },
            {
                "decision": "deny",
                "reason_code": "dead-end",
            },
        ]

        report = summarize_metrics(metrics)

        self.assertEqual(report["reads"]["full"], 2)
        self.assertEqual(report["reads"]["focused"], 1)
        self.assertEqual(report["decisions"], {"allow": 4, "deny": 2, "warn": 1})
        self.assertEqual(report["escape_hatches"], 1)
        self.assertEqual(report["cache"]["hits"], 1)
        self.assertEqual(report["cache"]["misses"], 2)
        self.assertEqual(report["returned_tokens"]["p95"], 4_100)
        self.assertEqual(report["false_positive_blocks"], 1)
        self.assertEqual(report["false_positive_rate"], 0.5)
        self.assertEqual(report["dead_ends"], 1)
        self.assertEqual(report["dead_end_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
