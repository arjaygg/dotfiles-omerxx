import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.public_hygiene_check import _fingerprint, compare_baseline, scan_repo, scan_text


class PublicHygieneCheckTests(unittest.TestCase):
    def test_clean_portable_text_has_no_findings(self):
        findings = scan_text(
            "template.json",
            '{"home": "$HOME/.dotfiles", "user_home": "/Users/${user}"}\n',
        )

        self.assertEqual(findings, [])

    def test_detects_private_paths_org_urls_and_secret_assignments(self):
        findings = scan_text(
            "runtime.md",
            "path=/Users/alice/.config\n"
            "ado=https://dev.azure.com/bofaz/project\n"
            'tok' + 'en = "sk-live-12345678901234567890"\n',
        )

        self.assertEqual(
            [finding.rule for finding in findings],
            ["absolute-home-path", "private-org-url", "secret-assignment"],
        )
        self.assertEqual([finding.line for finding in findings], [1, 2, 3])
        self.assertTrue(all(finding.path == "runtime.md" for finding in findings))

    def test_redacted_and_placeholder_values_are_not_secrets(self):
        findings = scan_text(
            "docs.md",
            'api_key: "[REDACTED]"\n'
            'token: "YOUR_TOKEN_HERE"\n'
            "secret: <set-in-local-overlay>\n",
        )

        self.assertEqual(findings, [])

    def test_detects_private_key_material(self):
        findings = scan_text(
            "key.txt",
            "-----BEGIN " + "RSA PRIVATE KEY-----\nmaterial\n",
        )

        self.assertEqual([finding.rule for finding in findings], ["private-key"])

    def test_repo_scan_only_reports_tracked_utf8_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private_name = "A" + "xos Financial"
            (root / "tracked.md").write_text(f"owner: {private_name}\n", encoding="utf-8")
            (root / "untracked.md").write_text(f"owner: {private_name}\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "add", "tracked.md"], check=True)

            findings = scan_repo(root)

        self.assertEqual([(finding.path, finding.rule) for finding in findings], [("tracked.md", "private-org-name")])

    def test_baseline_reports_added_and_removed_findings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tracked.md").write_text("path=/Users/alice/.config\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "add", "tracked.md"], check=True)
            baseline = root / "baseline.json"
            baseline.write_text('{"schema": 1, "finding_count": 0, "fingerprint": "' + "0" * 64 + '"}', encoding="utf-8")
            report = compare_baseline(root, baseline)

        self.assertEqual(report["finding_count"], 1)
        self.assertFalse(report["baseline_match"])

    def test_baseline_matches_finding_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tracked.md").write_text("path=/Users/alice/.config\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "add", "tracked.md"], check=True)
            fingerprint = _fingerprint({("tracked.md", 1, "absolute-home-path")})
            baseline = root / "baseline.json"
            baseline.write_text(
                f'{{"schema": 1, "finding_count": 1, "fingerprint": "{fingerprint}"}}',
                encoding="utf-8",
            )
            report = compare_baseline(root, baseline)
        self.assertTrue(report["baseline_match"])


if __name__ == "__main__":
    unittest.main()
