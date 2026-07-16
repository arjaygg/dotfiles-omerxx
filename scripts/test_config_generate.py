import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from scripts.config_generate import (
    TemplateValidationError,
    build_proposal,
    compare_proposal,
    deep_merge,
    expand_placeholders,
)


ROOT = Path(__file__).resolve().parents[1]


class ConfigGenerateTests(unittest.TestCase):
    def test_expand_placeholders_replaces_nested_values(self):
        value = {
            "command": "${PCTX_COMMAND}",
            "args": ["--config", "${PCTX_CONFIG}"],
        }

        self.assertEqual(
            expand_placeholders(
                value,
                {"PCTX_COMMAND": "pctx", "PCTX_CONFIG": "/tmp/pctx.json"},
            ),
            {"command": "pctx", "args": ["--config", "/tmp/pctx.json"]},
        )

    def test_expand_placeholders_replaces_nested_keys_and_values(self):
        value = {
            "${ROOT_KEY}": {
                "${CHILD_KEY}": "${VALUE}",
                "items": [{"${ITEM_KEY}": "${ITEM_VALUE}"}],
            },
            "unchanged": {"enabled": True},
        }

        expanded = expand_placeholders(
            value,
            {
                "ROOT_KEY": "projects",
                "CHILD_KEY": "example",
                "VALUE": "configured",
                "ITEM_KEY": "path",
                "ITEM_VALUE": "/tmp/example",
            },
        )

        self.assertEqual(
            expanded,
            {
                "projects": {
                    "example": "configured",
                    "items": [{"path": "/tmp/example"}],
                },
                "unchanged": {"enabled": True},
            },
        )
        self.assertEqual(list(expanded), ["projects", "unchanged"])
        self.assertIsNot(expanded["unchanged"], value["unchanged"])

    def test_expand_placeholders_rejects_unresolved_variables(self):
        with self.assertRaises(TemplateValidationError):
            expand_placeholders({"path": "${MISSING}"}, {})

    def test_expand_placeholders_rejects_unresolved_key_variables(self):
        with self.assertRaisesRegex(
            TemplateValidationError,
            "unresolved template variable: MISSING",
        ):
            expand_placeholders({"${MISSING}": "value"}, {})

    def test_expand_placeholders_rejects_expanded_key_collisions(self):
        with self.assertRaisesRegex(
            TemplateValidationError,
            "mapping key collision after placeholder expansion",
        ):
            expand_placeholders(
                {"${FIRST}": 1, "${SECOND}": 2},
                {"FIRST": "same", "SECOND": "same"},
            )

    def test_expand_placeholders_requires_string_mapping_keys(self):
        with self.assertRaisesRegex(
            TemplateValidationError,
            "template mapping keys must be strings",
        ):
            expand_placeholders({1: "value"}, {})

    def test_build_proposal_expands_explicit_variables_without_environment_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.json"
            base.write_text('{"path": "${CONFIG_PATH}"}\n', encoding="utf-8")

            original = os.environ.get("CONFIG_PATH")
            os.environ["CONFIG_PATH"] = "/tmp/should-not-be-used"
            try:
                proposal = build_proposal(
                    base,
                    variables={"CONFIG_PATH": "/tmp/pctx.json"},
                )
            finally:
                if original is None:
                    os.environ.pop("CONFIG_PATH", None)
                else:
                    os.environ["CONFIG_PATH"] = original

        self.assertEqual(json.loads(proposal), {"path": "/tmp/pctx.json"})

    def test_deep_merge_recurses_and_replaces_lists(self):
        base = {"model": "portable", "nested": {"keep": True, "replace": 1}, "list": [1]}
        overlay = {"nested": {"replace": 2}, "list": [2], "local": True}

        self.assertEqual(
            deep_merge(base, overlay),
            {
                "model": "portable",
                "nested": {"keep": True, "replace": 2},
                "list": [2],
                "local": True,
            },
        )
        self.assertEqual(base["nested"]["replace"], 1)

    def test_build_proposal_merges_without_mutating_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.json"
            overlay = root / "overlay.json"
            base.write_text('{"model": "portable", "nested": {"a": 1}}\n', encoding="utf-8")
            overlay.write_text('{"nested": {"b": 2}}\n', encoding="utf-8")
            base_before = base.read_bytes()
            overlay_before = overlay.read_bytes()

            proposal = build_proposal(base, overlay)

            self.assertEqual(json.loads(proposal), {"model": "portable", "nested": {"a": 1, "b": 2}})
            self.assertEqual(base.read_bytes(), base_before)
            self.assertEqual(overlay.read_bytes(), overlay_before)

    def test_build_proposal_rejects_private_or_secret_input(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "base.json"
            private_home = "/" + "Users/alice"
            base.write_text(
                f'{{"path": "{private_home}/.config/tool", "token": "secret-value"}}\n',
                encoding="utf-8",
            )

            with self.assertRaises(TemplateValidationError):
                build_proposal(base)

    def test_build_proposal_rejects_private_or_secret_input_for_toml(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "base.toml"
            private_path = "/" + "Users/alice/.config/tool"
            base.write_text(
                f'path = "{private_path}"\ntoken = "secret-value"\n',
                encoding="utf-8",
            )

            with self.assertRaises(TemplateValidationError):
                build_proposal(base)

    def test_script_entrypoint_emits_proposal(self):
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/config_generate.py"),
                str(ROOT / "ai/config/claude/settings.base.json"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsInstance(json.loads(result.stdout), dict)

    def test_script_entrypoint_accepts_explicit_variables(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "base.json"
            base.write_text('{"path": "${CONFIG_PATH}"}\n', encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/config_generate.py"),
                    str(base),
                    "--set",
                    "CONFIG_PATH=/tmp/pctx.json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"path": "/tmp/pctx.json"})

    def test_compare_proposal_reports_paths_and_hashes_without_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.json"
            overlay = root / "overlay.json"
            target = root / "target.json"
            base.write_text('{"model": "portable", "nested": {"a": 1}}\n', encoding="utf-8")
            overlay.write_text('{"nested": {"b": 2}}\n', encoding="utf-8")
            target.write_text('{"model": "portable", "nested": {"a": 1, "b": 3}}\n', encoding="utf-8")
            target_before = target.read_bytes()

            comparison = compare_proposal(base, overlay, target)

            self.assertEqual(comparison.changed_paths, ["nested.b"])
            self.assertEqual(len(comparison.proposal_sha256), 64)
            self.assertEqual(len(comparison.target_sha256), 64)
            self.assertEqual(target.read_bytes(), target_before)

    def test_build_proposal_parses_and_emits_toml(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.toml"
            overlay = root / "overlay.toml"
            base.write_text('model = "portable"\n\n[nested]\na = 1\n', encoding="utf-8")
            overlay.write_text('[nested]\nb = 2\n', encoding="utf-8")

            proposal_text = build_proposal(base, overlay)
            proposal = tomllib.loads(proposal_text)

            self.assertEqual(proposal, {"model": "portable", "nested": {"a": 1, "b": 2}})

    def test_build_proposal_round_trips_codex_toml_shapes(self):
        source = """
[notice.model_migrations]
"gpt-5.2" = "gpt-5.3-codex"

[[skills.config]]
path = "skills/first"
enabled = true

[[skills.config]]
path = "skills/second"
enabled = false
""".lstrip()
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "base.toml"
            base.write_text(source, encoding="utf-8")

            proposal = build_proposal(base)

        self.assertEqual(tomllib.loads(proposal), tomllib.loads(source))

    def test_build_proposal_round_trips_tomllib_value_types(self):
        source = r"""
string = "line\nbreak"
quoted = '"value"'
enabled = true
integer = 42
float = 1.25
not_a_number = nan
negative_not_a_number = -nan
positive_infinity = inf
negative_infinity = -inf
date = 2026-07-15
time = 12:34:56.789
local_datetime = 2026-07-15T12:34:56
offset_datetime = 2026-07-15T12:34:56Z
values = [1, 2, 3]
matrix = [[1, 2], [3, 4]]
mixed = [{ "special.key" = "value" }, "tail"]
inline = { plain = "value", nested = { enabled = false } }
""".lstrip()
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "base.toml"
            base.write_text(source, encoding="utf-8")

            proposal_text = build_proposal(base)
            actual = tomllib.loads(proposal_text)

        expected = tomllib.loads(source)
        positive_actual = actual.pop("not_a_number")
        positive_expected = expected.pop("not_a_number")
        negative_actual = actual.pop("negative_not_a_number")
        negative_expected = expected.pop("negative_not_a_number")
        self.assertTrue(math.isnan(positive_actual))
        self.assertTrue(math.isnan(negative_actual))
        self.assertEqual(math.copysign(1.0, positive_actual), 1.0)
        self.assertEqual(math.copysign(1.0, positive_expected), 1.0)
        self.assertEqual(math.copysign(1.0, negative_actual), -1.0)
        self.assertEqual(math.copysign(1.0, negative_expected), -1.0)
        self.assertIn("negative_not_a_number = -nan", proposal_text)
        self.assertEqual(actual, expected)

    def test_compare_proposal_works_with_toml(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.toml"
            overlay = root / "overlay.toml"
            target = root / "target.toml"
            base.write_text('model = "portable"\n\n[nested]\na = 1\n', encoding="utf-8")
            overlay.write_text('[nested]\nb = 2\n', encoding="utf-8")
            target.write_text('model = "portable"\n\n[nested]\na = 1\nb = 3\n', encoding="utf-8")

            comparison = compare_proposal(base, overlay, target)

            self.assertEqual(comparison.changed_paths, ["nested.b"])

    def test_build_proposal_rejects_credential_shaped_key_suffixes(self):
        cases = (
            ("db_password", "opaque database material!"),
            ("clientSecret", "opaque client material!"),
            ("apiKey", "opaque API key material!"),
            ("passphrase", "opaque phrase with spaces!"),
            (
                "aws_credentials",
                {"access_id": "opaque credential material!"},
            ),
            ("service_credential", "opaque credential material!"),
            ("credentials", "opaque credential collection!"),
            ("private_key", "opaque non-PEM key material!"),
            ("password_hash", "opaque hash material!"),
            ("password_salt", "opaque salt material!"),
            ("secret_value", "opaque secret material!"),
            ("token_value", "opaque token material!"),
        )

        with tempfile.TemporaryDirectory() as directory:
            for index, (key, value) in enumerate(cases):
                with self.subTest(key=key):
                    base = Path(directory) / f"case-{index}.json"
                    base.write_text(json.dumps({key: value}), encoding="utf-8")

                    with self.assertRaises(TemplateValidationError) as caught:
                        build_proposal(base)

                    message = str(caught.exception)
                    self.assertIn("secret-assignment", message)
                    self.assertNotIn(key, message)
                    self.assertNotIn("opaque", message)

    def test_compare_proposal_rejects_new_structured_secret_shapes(self):
        overlay_key = "service_" + "passphrase"
        target_key = "aws_" + "credentials"
        sensitive_value = "opaque value with spaces!"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.json"
            overlay = root / "overlay.json"
            target = root / "target.json"
            base_content = {"model": "portable"}
            base.write_text(json.dumps(base_content), encoding="utf-8")
            target.write_text(json.dumps(base_content), encoding="utf-8")
            overlay.write_text(
                json.dumps({overlay_key: sensitive_value}),
                encoding="utf-8",
            )

            with self.assertRaises(TemplateValidationError) as overlay_caught:
                compare_proposal(base, overlay, target)

            overlay_message = str(overlay_caught.exception)
            self.assertIn("secret-assignment", overlay_message)
            self.assertNotIn(overlay_key, overlay_message)
            self.assertNotIn(sensitive_value, overlay_message)

            target.write_text(
                json.dumps({**base_content, target_key: {"id": sensitive_value}}),
                encoding="utf-8",
            )
            with self.assertRaises(TemplateValidationError) as target_caught:
                compare_proposal(base, None, target)

        target_message = str(target_caught.exception)
        self.assertIn("secret-assignment", target_message)
        self.assertNotIn(target_key, target_message)
        self.assertNotIn(sensitive_value, target_message)

    def test_build_proposal_rejects_structured_secret_assignments(self):
        escaped_password_key = "pass" + "\\u0077" + "ord"
        github_token_key = "github_" + "token"
        auth_token_key = "auth" + "Token"
        api_key = "api" + "_key"
        cases = (
            (
                "json",
                '{"' + escaped_password_key + '": "phrase with spaces!"}\n',
                "password",
                "phrase with spaces!",
            ),
            (
                "toml",
                f'{github_token_key} = """line one with spaces!\n'
                'line two, punctuation.\n"""\n',
                github_token_key,
                "line one with spaces!",
            ),
            (
                "json",
                json.dumps({auth_token_key: "punctuation ! ?"}) + "\n",
                auth_token_key,
                "punctuation ! ?",
            ),
            (
                "json",
                json.dumps({api_key: "not a credential!"}) + "\n",
                api_key,
                "not a credential!",
            ),
        )

        with tempfile.TemporaryDirectory() as directory:
            for index, (suffix, content, key, sensitive_value) in enumerate(cases):
                with self.subTest(index=index, suffix=suffix):
                    base = Path(directory) / f"case-{index}.{suffix}"
                    base.write_text(content, encoding="utf-8")

                    with self.assertRaises(TemplateValidationError) as caught:
                        build_proposal(base)

                    message = str(caught.exception)
                    self.assertIn("secret-assignment", message)
                    self.assertNotIn(key, message)
                    self.assertNotIn(sensitive_value, message)

    def test_build_proposal_allows_safe_secret_placeholders(self):
        config = {
            "token": "",
            "password": None,
            "api_key": "[REDACTED local]",
            "github_token": "<set-locally>",
            "authToken": "YOUR_AUTH_TOKEN",
            "clientSecret": "CHANGE_ME",
            "access_token": "REPLACE_ME",
            "client_secret": [],
            "tokenizer": "configured value",
            "secretary": "configured person",
            "token_budget": 4096,
            "token_endpoint": "https://example.invalid/oauth",
            "token_count": 12,
            "max_tokens": 1024,
            "password_min_length": 12,
            "password_policy": "strong",
            "secret_scanning_enabled": True,
            "credentials_provider": "local-process",
            "credential_process": "helper --safe",
            "private_key_path": "/tmp/example-key",
            "private_key_id": "example-key-id",
        }
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "base.json"
            base.write_text(json.dumps(config), encoding="utf-8")

            proposal = json.loads(build_proposal(base))

        self.assertEqual(proposal, config)

    def test_build_proposal_allows_unresolved_secret_placeholder_in_template(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "base.json"
            base.write_text('{"token": "${TOKEN}"}\n', encoding="utf-8")

            with self.assertRaises(TemplateValidationError) as caught:
                build_proposal(base)

        message = str(caught.exception)
        self.assertIn("unresolved template variable: TOKEN", message)
        self.assertNotIn("secret-assignment", message)

    def test_build_proposal_rejects_expanded_secret_values(self):
        sensitive_value = "phrase with spaces and punctuation!"
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "base.json"
            base.write_text(
                '{"password": "${PASSWORD}"}\n',
                encoding="utf-8",
            )

            with self.assertRaises(TemplateValidationError) as caught:
                build_proposal(base, variables={"PASSWORD": sensitive_value})

        message = str(caught.exception)
        self.assertIn("secret-assignment", message)
        self.assertNotIn("password", message)
        self.assertNotIn(sensitive_value, message)

    def test_build_proposal_rejects_unescaped_private_key_values(self):
        escaped_marker = "\\u002d" * 5 + "BEGIN " + "PRIVATE " + "KEY-----"
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "base.json"
            base.write_text(
                '{"notes": "' + escaped_marker + '"}\n',
                encoding="utf-8",
            )

            with self.assertRaises(TemplateValidationError) as caught:
                build_proposal(base)

        message = str(caught.exception)
        self.assertIn("private-key", message)
        self.assertNotIn("BEGIN", message)

    def test_compare_proposal_rejects_structured_target_secrets(self):
        escaped_password_key = "pass" + "\\u0077" + "ord"
        sensitive_value = "phrase with spaces and punctuation!"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.json"
            target = root / "target.json"
            base.write_text('{"model": "portable"}\n', encoding="utf-8")
            target.write_text(
                '{"model": "portable", "'
                + escaped_password_key
                + '": "'
                + sensitive_value
                + '"}\n',
                encoding="utf-8",
            )

            with self.assertRaises(TemplateValidationError) as caught:
                compare_proposal(base, None, target)

        message = str(caught.exception)
        self.assertIn("secret-assignment", message)
        self.assertNotIn("password", message)
        self.assertNotIn(sensitive_value, message)

    def test_build_proposal_rejects_generic_keys_and_windows_local_paths(self):
        separator = "\\"
        drive_path = separator.join(
            ("C:", "users", "Alice Smith", "config")
        )
        unc_path = separator * 2 + separator.join(
            ("work station", "team share", "config")
        )
        private_key_marker = "-----BEGIN " + "PRIVATE KEY-----"
        pgp_private_key_marker = (
            "-----BEGIN " + "PGP PRIVATE " + "KEY BLOCK-----"
        )
        cases = (
            (
                "private-key",
                f'key = "{private_key_marker}"\n',
                private_key_marker,
                None,
            ),
            (
                "private-key",
                f'key = "{pgp_private_key_marker}"\n',
                pgp_private_key_marker,
                None,
            ),
            (
                "absolute-home-path",
                "path = '${LOCAL_PATH}'\n",
                drive_path,
                {"LOCAL_PATH": drive_path},
            ),
            (
                "absolute-home-path",
                "path = '${LOCAL_PATH}'\n",
                unc_path,
                {"LOCAL_PATH": unc_path},
            ),
        )

        with tempfile.TemporaryDirectory() as directory:
            for index, (rule, content, sensitive_value, variables) in enumerate(cases):
                with self.subTest(rule=rule, index=index):
                    base = Path(directory) / f"case-{index}.toml"
                    base.write_text(content, encoding="utf-8")

                    with self.assertRaises(TemplateValidationError) as caught:
                        build_proposal(base, variables=variables)

                    message = str(caught.exception)
                    self.assertIn(f"{rule}@1", message)
                    self.assertNotIn(sensitive_value, message)

    def test_compare_proposal_accepts_windows_and_unc_overlay_paths(self):
        separator = "\\"
        drive_path = separator.join(
            ("C:", "users", "Alice Smith", "config")
        )
        unc_path = separator * 2 + separator.join(
            ("work station", "team share", "config")
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.toml"
            overlay = root / "overlay.toml"
            target = root / "target.toml"
            base.write_text('model = "portable"\n', encoding="utf-8")
            overlay.write_text(
                f"drive_path = '{drive_path}'\nunc_path = '{unc_path}'\n",
                encoding="utf-8",
            )
            target.write_text('model = "portable"\n', encoding="utf-8")
            before = {
                path: path.read_bytes() for path in (base, overlay, target)
            }

            comparison = compare_proposal(base, overlay, target)

            self.assertEqual(comparison.changed_paths, ["drive_path", "unc_path"])
            changed_text = "\n".join(comparison.changed_paths)
            self.assertNotIn(drive_path, changed_text)
            self.assertNotIn(unc_path, changed_text)
            self.assertEqual(
                {path: path.read_bytes() for path in (base, overlay, target)},
                before,
            )

    def test_compare_proposal_rejects_sensitive_target_findings_before_parsing(self):
        secret_value = "a" * 16
        private_key_marker = "-----BEGIN " + "PRIVATE KEY-----"
        cases = (
            (
                "secret-assignment",
                f'token = "{secret_value}"\n[invalid\n',
                secret_value,
            ),
            (
                "private-key",
                f'key = "{private_key_marker}"\n',
                private_key_marker,
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.toml"
            target = root / "target.toml"
            base.write_text('model = "portable"\n', encoding="utf-8")

            for rule, content, sensitive_value in cases:
                with self.subTest(rule=rule):
                    target.write_text(
                        'model = "portable"\n' + content,
                        encoding="utf-8",
                    )
                    target_before = target.read_bytes()

                    with self.assertRaises(TemplateValidationError) as caught:
                        compare_proposal(base, None, target)

                    message = str(caught.exception)
                    self.assertIn(f"{rule}@2", message)
                    self.assertNotIn(sensitive_value, message)
                    self.assertNotIn("invalid TOML target", message)
                    self.assertEqual(target.read_bytes(), target_before)

    def test_compare_proposal_rejects_json_target_secret_assignments(self):
        secret_value = "a" * 16
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.json"
            target = root / "target.json"
            base.write_text('{"model": "portable"}\n', encoding="utf-8")
            target.write_text(
                json.dumps({"model": "portable", "token": secret_value}),
                encoding="utf-8",
            )

            with self.assertRaises(TemplateValidationError) as caught:
                compare_proposal(base, None, target)

        message = str(caught.exception)
        self.assertIn("secret-assignment@1", message)
        self.assertNotIn(secret_value, message)

    def test_compare_proposal_detects_missing_null_and_type_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.json"
            target = root / "target.json"
            base.write_text(
                '{"bool_value": true, "int_value": 1}\n',
                encoding="utf-8",
            )
            target.write_text(
                '{"bool_value": 1, "int_value": 1.0, '
                '"missing_vs_null": null}\n',
                encoding="utf-8",
            )

            comparison = compare_proposal(base, None, target)

        self.assertEqual(
            comparison.changed_paths,
            ["bool_value", "int_value", "missing_vs_null"],
        )

    def test_compare_proposal_treats_nan_with_matching_sign_as_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.toml"
            target = root / "target.toml"
            base.write_text(
                "same_nan = nan\nnan_sign = nan\n",
                encoding="utf-8",
            )
            target.write_text(
                "same_nan = nan\nnan_sign = -nan\n",
                encoding="utf-8",
            )

            comparison = compare_proposal(base, None, target)

        self.assertEqual(comparison.changed_paths, ["nan_sign"])

    def test_compare_proposal_distinguishes_dotted_and_nested_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.json"
            target = root / "target.json"
            base.write_text(
                '{"root": {"a": {"b": 0}, "a.b": 0}}\n',
                encoding="utf-8",
            )
            target.write_text(
                '{"root": {"a": {"b": 1}, "a.b": 1}}\n',
                encoding="utf-8",
            )

            comparison = compare_proposal(base, None, target)

        self.assertEqual(
            comparison.changed_paths,
            ["root.a.b", 'root["a.b"]'],
        )

    def test_compare_proposal_distinguishes_literal_redaction_label(self):
        private_key = "/" + "Users/alice/private-repo"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.json"
            target = root / "target.json"
            base.write_text(
                '{"root": {"<redacted-key-1>": {"value": 0}}}\n',
                encoding="utf-8",
            )
            target.write_text(
                json.dumps(
                    {
                        "root": {
                            private_key: {"value": 1},
                            "<redacted-key-1>": {"value": 1},
                        }
                    }
                ),
                encoding="utf-8",
            )

            comparison = compare_proposal(base, None, target)

        changed_text = "\n".join(comparison.changed_paths)
        self.assertNotIn(private_key, changed_text)
        self.assertNotIn("alice", changed_text)
        self.assertEqual(
            comparison.changed_paths,
            [
                "root.<redacted-key-1>.value",
                'root["<redacted-key-1>"].value',
            ],
        )

    def test_build_proposal_rejects_absolute_home_path_in_overlay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.toml"
            overlay = root / "overlay.toml"
            private_path = "/" + "Users/alice/private-repo"
            base.write_text('model = "portable"\n', encoding="utf-8")
            overlay.write_text(
                f'project_path = "{private_path}"\n',
                encoding="utf-8",
            )

            with self.assertRaises(TemplateValidationError) as caught:
                build_proposal(base, overlay)

        message = str(caught.exception)
        self.assertIn("absolute-home-path@1", message)
        self.assertNotIn(private_path, message)

    def test_compare_proposal_accepts_absolute_home_path_in_overlay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.toml"
            overlay = root / "overlay.toml"
            target = root / "target.toml"
            private_username = "A" + "xos"
            private_project_key = (
                "/" + "Users/" + private_username + "/private-repo"
            )
            private_org_url = "https://dev.azure.com/" + "bofaz"
            base.write_text('model = "portable"\n', encoding="utf-8")
            overlay.write_text(
                f'[projects."{private_project_key}"]\n'
                f'project_path = "{private_project_key}"\n'
                f'organization_url = "{private_org_url}"\n'
                'trust_level = "trusted"\n',
                encoding="utf-8",
            )
            target.write_text('model = "portable"\n', encoding="utf-8")
            before = {
                path: path.read_bytes() for path in (base, overlay, target)
            }

            comparison = compare_proposal(base, overlay, target)

            self.assertEqual(
                comparison.changed_paths,
                [
                    "projects.<redacted-key-1>.organization_url",
                    "projects.<redacted-key-1>.project_path",
                    "projects.<redacted-key-1>.trust_level",
                ],
            )
            changed_text = "\n".join(comparison.changed_paths)
            self.assertNotIn(private_project_key, changed_text)
            self.assertNotIn(private_username, changed_text)
            self.assertNotIn(private_org_url, changed_text)
            self.assertEqual(len(comparison.proposal_sha256), 64)
            self.assertEqual(len(comparison.target_sha256), 64)
            self.assertEqual(
                {path: path.read_bytes() for path in (base, overlay, target)},
                before,
            )

    def test_compare_proposal_rejects_non_path_overlay_findings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.toml"
            overlay = root / "overlay.toml"
            target = root / "target.toml"
            secret_value = "a" * 16
            private_key_marker = "-----BEGIN " + "RSA PRIVATE KEY-----"
            pgp_private_key_marker = (
                "-----BEGIN " + "PGP PRIVATE " + "KEY BLOCK-----"
            )
            base.write_text('model = "portable"\n', encoding="utf-8")
            target.write_text('model = "portable"\n', encoding="utf-8")
            cases = (
                (
                    "secret-assignment",
                    f'token = "{secret_value}"\n',
                    secret_value,
                ),
                (
                    "private-key",
                    f'key = "{private_key_marker}"\n',
                    private_key_marker,
                ),
                (
                    "private-key",
                    f'key = "{pgp_private_key_marker}"\n',
                    pgp_private_key_marker,
                ),
            )

            for rule, content, sensitive_value in cases:
                with self.subTest(rule=rule):
                    overlay.write_text(content, encoding="utf-8")

                    with self.assertRaises(TemplateValidationError) as caught:
                        compare_proposal(base, overlay, target)

                    message = str(caught.exception)
                    self.assertIn(f"{rule}@1", message)
                    self.assertNotIn(sensitive_value, message)

    def test_compare_proposal_redacts_sensitive_mapping_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.toml"
            target = root / "target.toml"
            private_project_key = "/" + "Users/alice/private-repo"
            base.write_text(
                """
[projects.safe]
trust_level = "untrusted"

[[skills.config]]
path = "skills/old"
""".lstrip(),
                encoding="utf-8",
            )
            target.write_text(
                f"""
[projects.safe]
trust_level = "trusted"

[projects."{private_project_key}"]
trust_level = "trusted"
sandbox_mode = "read-only"

[projects."~/git/private-repo"]
trust_level = "trusted"
sandbox_mode = "read-only"

[[skills.config]]
path = "skills/new"
""".lstrip(),
                encoding="utf-8",
            )

            comparison = compare_proposal(base, None, target)

        changed_text = "\n".join(comparison.changed_paths)
        self.assertNotIn("/Users/", changed_text)
        self.assertNotIn("alice", changed_text)
        self.assertNotIn("~/git/", changed_text)
        self.assertEqual(
            comparison.changed_paths,
            [
                "projects.<redacted-key-1>.sandbox_mode",
                "projects.<redacted-key-1>.trust_level",
                "projects.<redacted-key-2>.sandbox_mode",
                "projects.<redacted-key-2>.trust_level",
                "projects.safe.trust_level",
                "skills.config[0].path",
            ],
        )

    def test_compare_proposal_redacts_windows_and_scanner_flagged_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.json"
            target = root / "target.json"
            scanner_flagged_key = "A" + "xos Clearing"
            separator = "\\"
            windows_path_key = separator.join(
                ("C:", "Users", "alice", "private-repo")
            )
            base.write_text(
                json.dumps({"projects": {"safe": {"enabled": False}}}),
                encoding="utf-8",
            )
            target.write_text(
                json.dumps(
                    {
                        "projects": {
                            "safe": {"enabled": True},
                            windows_path_key: {"enabled": True},
                            scanner_flagged_key: {"enabled": True},
                        }
                    }
                ),
                encoding="utf-8",
            )

            comparison = compare_proposal(base, None, target)

        changed_text = "\n".join(comparison.changed_paths)
        self.assertNotIn(windows_path_key, changed_text)
        self.assertNotIn("alice", changed_text)
        self.assertNotIn(scanner_flagged_key, changed_text)
        self.assertEqual(
            comparison.changed_paths,
            [
                "projects.<redacted-key-1>.enabled",
                "projects.<redacted-key-2>.enabled",
                "projects.safe.enabled",
            ],
        )

    def test_compare_proposal_preserves_json_bom_target_support(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.json"
            target = root / "target.json"
            base.write_text('{"nested": {"value": 1}}\n', encoding="utf-8")
            target_bytes = b'\xef\xbb\xbf{"nested": {"value": 2}}\n'
            target.write_bytes(target_bytes)

            comparison = compare_proposal(base, None, target)

            self.assertEqual(comparison.changed_paths, ["nested.value"])
            self.assertEqual(
                comparison.target_sha256,
                hashlib.sha256(target_bytes).hexdigest(),
            )

    def test_build_proposal_rejects_unsupported_and_mismatched_formats(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unsupported = root / "base.yaml"
            json_base = root / "base.json"
            toml_overlay = root / "overlay.toml"
            unsupported.write_text("value: 1\n", encoding="utf-8")
            json_base.write_text("{}\n", encoding="utf-8")
            toml_overlay.write_text("value = 1\n", encoding="utf-8")

            with self.assertRaisesRegex(
                TemplateValidationError, "unsupported template format"
            ):
                build_proposal(unsupported)
            with self.assertRaisesRegex(
                TemplateValidationError, "overlay format does not match"
            ):
                build_proposal(json_base, toml_overlay)

    def test_script_entrypoint_rejects_invalid_toml_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "base.toml"
            base.write_text("[invalid\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).with_name("config_generate.py")),
                    str(base),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("config proposal rejected", result.stderr)
        self.assertIn("invalid TOML template", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_codex_proposal_generation_is_idempotent(self):
        base = ROOT / "ai/config/codex/config.base.toml"
        overlay = ROOT / "ai/config/codex/codex.overlay.example.toml"
        variables = {
            "MARKETPLACE_CACHE": "/tmp/marketplace-cache",
            "PCTX_CONFIG": "/tmp/pctx.json",
            "PROJECT_ROOT": "/tmp/example-project",
        }
        base_before = base.read_bytes()
        overlay_before = overlay.read_bytes()

        first = build_proposal(base, overlay, variables)
        second = build_proposal(base, overlay, variables)

        self.assertEqual(first, second)
        proposal = tomllib.loads(first)
        self.assertEqual(
            proposal["projects"]["/tmp/example-project"]["trust_level"],
            "trusted",
        )
        self.assertEqual(
            proposal["skills"]["config"][0]["path"],
            "/tmp/example-project/.agents/skills/example-skill",
        )
        self.assertEqual(base.read_bytes(), base_before)
        self.assertEqual(overlay.read_bytes(), overlay_before)

if __name__ == "__main__":
    unittest.main()
