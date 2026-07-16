import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.public_hygiene_check import scan_repo, scan_text, summarize_findings


ROOT = Path(__file__).resolve().parents[1]


class PublicHygieneCheckTests(unittest.TestCase):
    def test_clean_portable_text_has_no_findings(self):
        findings = scan_text(
            "template.json",
            '{"home": "$HOME/.dotfiles", "user_home": "/Users/${user}", '
            '"windows_home": "C:\\Users\\${user}\\config"}\n',
        )

        self.assertEqual(findings, [])

    def test_detects_private_paths_org_urls_and_secret_assignments(self):
        private_home = "/" + "Users/alice"
        private_url = "https://dev.azure.com/" + "bofaz/project"
        findings = scan_text(
            "runtime.md",
            f"path={private_home}/.config\n"
            f"ado={private_url}\n"
            'tok' + 'en = "sk-live-12345678901234567890"\n',
        )

        self.assertEqual(
            [finding.rule for finding in findings],
            ["absolute-home-path", "private-org-url", "secret-assignment"],
        )
        self.assertEqual([finding.line for finding in findings], [1, 2, 3])
        self.assertTrue(all(finding.path == "runtime.md" for finding in findings))

    def test_detects_json_secret_assignments(self):
        secret_value = "a" * 16
        findings = scan_text(
            "target.json",
            '{"token": "' + secret_value + '"}\n',
        )

        self.assertEqual([finding.rule for finding in findings], ["secret-assignment"])
        self.assertEqual([finding.line for finding in findings], [1])

    def test_redacted_and_placeholder_values_are_not_secrets(self):
        findings = scan_text(
            "docs.md",
            'api_key: "[REDACTED]"\n'
            'token: "YOUR_TOKEN_HERE"\n'
            "secret: <set-in-local-overlay>\n",
        )

        self.assertEqual(findings, [])

    def test_detects_windows_drive_and_unc_local_paths(self):
        separator = "\\"
        drive_path = separator.join(
            ("C:", "users", "Alice Smith", "config")
        )
        unc_path = separator * 2 + separator.join(
            ("work station", "team share", "config")
        )

        findings = scan_text(
            "runtime.txt",
            f"drive={drive_path}\nunc={unc_path}\n"
            "asset=//cdn.example.com/assets/\n",
        )

        self.assertEqual(
            [finding.rule for finding in findings],
            ["absolute-home-path", "absolute-home-path"],
        )
        self.assertEqual([finding.line for finding in findings], [1, 2])

    def test_detects_generic_and_prefixed_private_key_material(self):
        marker_end = "PRIVATE " + "KEY-----"
        prefixes = ("", "RSA ", "EC ", "OPENSSH ")
        markers = [
            "-----BEGIN " + prefix + marker_end for prefix in prefixes
        ]
        markers.append("-----BEGIN " + "PGP PRIVATE " + "KEY BLOCK-----")

        findings = scan_text("key.txt", "\n".join(markers))

        self.assertEqual(
            [finding.rule for finding in findings],
            ["private-key"] * len(markers),
        )
        self.assertEqual([finding.line for finding in findings], [1, 2, 3, 4, 5])

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

    def test_summary_groups_counts_without_excerpts(self):
        private_name = "A" + "xos Financial"
        private_home = "/" + "Users/alice"
        other_home = "/" + "Users/bob"
        findings = scan_text(
            "runtime.md",
            f"owner: {private_name}\npath={private_home}/.config\n",
        ) + scan_text("other.md", f"path={other_home}/.cache\n")

        summary = summarize_findings(findings)

        self.assertEqual(
            summary,
            {
                "total": 3,
                "by_rule": {"absolute-home-path": 2, "private-org-name": 1},
                "by_path": {"runtime.md": 2, "other.md": 1},
            },
        )
        self.assertNotIn("owner", repr(summary))
        self.assertNotIn("alice", repr(summary))

    def test_scripts_tree_has_no_hygiene_findings(self):
        findings = []
        for path in sorted((ROOT / "scripts").glob("*.py")):
            findings.extend(scan_text(path.relative_to(ROOT).as_posix(), path.read_text(encoding="utf-8")))

        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
