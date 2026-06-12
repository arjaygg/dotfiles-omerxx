#!/usr/bin/env python3
"""
CI/CD Webhook Server — cicd-monitor Agent
Receives GitHub workflow_run completion webhooks and routes to remediation agents.
"""

import http.server
import socketserver
import json
import logging
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

PORT = 5000
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("cicd-monitor")


def classify_failure(payload):
    """Classify failure severity based on webhook payload."""
    workflow_run = payload.get("workflow_run", {})
    failed_jobs = payload.get("failed_jobs", [])
    cve_count = payload.get("cve_count", 0)

    conclusion = workflow_run.get("conclusion")

    # SUCCESS: No failures
    if conclusion == "success":
        return "SUCCESS"

    # CRITICAL: Secrets detected
    if any("secrets" in j.get("name", "").lower() for j in failed_jobs):
        return "CRITICAL"

    # CRITICAL: HIGH/CRITICAL CVEs from Trivy
    if cve_count > 0:
        return "CRITICAL"

    # HIGH/MEDIUM: Apply RFM logic for other failures
    if failed_jobs:
        rfm_score = calculate_rfm_score(failed_jobs, payload)
        if rfm_score >= 4:
            return "HIGH_ESCALATE"  # Skip retry, go directly to review
        else:
            return "HIGH_RETRY"  # Safe to retry

    return "MEDIUM"  # Unknown failure pattern


def calculate_rfm_score(failed_jobs, payload):
    """Calculate RFM = Recency × Frequency × Magnitude.

    Simplified scoring (full implementation reads cicd-events.md from Serena):
    - R=1 (default, no recent failures tracked)
    - F=1 (default, assume first failure)
    - M=1 (dev), M=2 (dev+qa), M=3 (all envs)
    """
    recency = 1
    frequency = 1

    # Magnitude: How many environments are blocked?
    job_names = [j.get("name", "").lower() for j in failed_jobs]
    magnitude = 1
    if any("qa" in name for name in job_names):
        magnitude = 2
    if any("uat" in name or "prod" in name for name in job_names):
        magnitude = 3

    score = recency * frequency * magnitude
    logger.info(f"RFM Score: {score} (R={recency}, F={frequency}, M={magnitude})")
    return score


class WebhookHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for webhook events."""

    def do_POST(self):
        """Handle POST requests to /dispatch endpoint."""
        if self.path != "/dispatch":
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        try:
            payload = json.loads(body)
            workflow_run = payload.get("workflow_run", {})
            run_id = workflow_run.get("id")
            ref = workflow_run.get("head_branch")
            conclusion = workflow_run.get("conclusion")
            failed_jobs = payload.get("failed_jobs", [])
            cve_count = payload.get("cve_count", 0)

            logger.info(f"✓ Webhook received: run_id={run_id}, ref={ref}, conclusion={conclusion}")
            logger.info(f"  Failed jobs: {len(failed_jobs)}, CVEs: {cve_count}")

            # Classify failure
            severity = classify_failure(payload)
            logger.info(f"  Severity: {severity}")

            # Respond immediately to GitHub (don't block on agent dispatch)
            response = {
                "status": "processed",
                "run_id": run_id,
                "severity": severity,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

            # Route based on severity (non-blocking)
            route_by_severity(run_id, ref, severity, payload)

        except json.JSONDecodeError as e:
            logger.error(f"✗ Invalid JSON: {e}")
            self.send_response(400)
            self.end_headers()
        except Exception as e:
            logger.error(f"✗ Error: {e}")
            self.send_response(500)
            self.end_headers()

    def do_GET(self):
        """Handle GET requests for health check."""
        if self.path == "/health":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "healthy",
                "service": "cicd-monitor-webhook"
            }).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        pass


def route_by_severity(run_id, ref, severity, payload):
    """Route webhook to appropriate agent based on severity.

    In production, this would call SendMessage() to notify other agents.
    For now, log the routing decision.
    """
    failed_jobs = payload.get("failed_jobs", [])
    job_names = [j.get("name") for j in failed_jobs]

    if severity == "SUCCESS":
        logger.info(f"  Route: cicd-audit (deployment_success)")
    elif severity == "CRITICAL":
        logger.info(f"  Route: cicd-audit + cicd-review (critical severity)")
    elif severity == "HIGH_RETRY":
        logger.info(f"  Route: cicd-audit + cicd-auto-retry (RFM < 4, safe to retry)")
    elif severity == "HIGH_ESCALATE":
        logger.info(f"  Route: cicd-audit + cicd-review (RFM ≥ 4, systemic)")
    else:
        logger.info(f"  Route: cicd-audit (build warning, no retry)")


def main():
    """Start webhook server."""
    logger.info(f"🚀 Starting CI/CD monitor webhook server on http://0.0.0.0:{PORT}")

    with socketserver.TCPServer(("0.0.0.0", PORT), WebhookHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info("✓ Server stopped")
            sys.exit(0)
        except Exception as e:
            logger.error(f"✗ Server error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
