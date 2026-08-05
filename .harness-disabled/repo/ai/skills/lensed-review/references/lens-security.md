# Security Lens

Derived from `hawk`'s Security dimension, the `security-reviewer` agent, and `pr-review`'s
Security dimension. Runs when the change touches auth, input handling, secrets, network calls, or
dependency versions (see `lenses.toml`'s `when` for this lens).

## What to check (OWASP-oriented)

- **Injection**: SQL/command/template injection from unsanitized input reaching a query, shell
  call, or template renderer.
- **Auth/authz**: missing or bypassable authentication checks; authorization checks that trust
  client-supplied identifiers instead of the authenticated session.
- **Secrets handling**: hardcoded credentials, API keys, or tokens; secrets logged in plaintext;
  secrets committed to the repo.
- **Input validation**: unvalidated/unsanitized user input crossing a trust boundary (API request
  body, file upload, URL parameter, environment variable from an untrusted source).
- **Dependency CVEs**: newly introduced or upgraded dependencies with known vulnerabilities —
  check version pins against known advisories if tooling is available.
- **XSS/CSRF**: unescaped user content rendered into HTML/JS contexts; state-changing endpoints
  missing CSRF protection where the framework doesn't handle it automatically.

## Process

1. Identify every trust boundary the change crosses (network input, file input, environment,
   third-party API response).
2. For each, confirm whether validation/sanitization actually happens on the path taken by
   untrusted data — trace the code, don't assume a validator exists because one exists elsewhere.
3. Emit one finding per confirmed issue: `lens: "security"`, `location`, `trigger_condition`,
   `guard_snippet` (the concrete fix — e.g. a parameterized query, an allowlist, an escape call),
   `potential_consequence` (what an attacker gains). No `severity` field — the Coordinator triages.
4. Do not flag theoretical issues with no reachable trigger condition; this lens reports exploitable
   gaps, not general security best-practice reminders.
