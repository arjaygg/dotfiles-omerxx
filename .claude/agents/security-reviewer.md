108 lines → 81 unique
1 errors:
  3. **Fail Securely** — Errors should not expose data
last 15 unique lines:
4. Verify remediation works
5. Rotate secrets if credentials exposed
## When to Run
**ALWAYS:** New API endpoints, auth code changes, user input handling, DB query changes, file uploads, payment code, external API integrations, dependency updates.
**IMMEDIATELY:** Production incidents, dependency CVEs, user security reports, before major releases.
## Success Metrics
- No CRITICAL issues found
- All HIGH issues addressed
- No secrets in code
- Dependencies up to date
- Security checklist complete
## Reference
For detailed vulnerability patterns, code examples, report templates, and PR review templates, see skill: `security-review`.
---
**Remember**: Security is not optional. One vulnerability can cost users real financial losses. Be thorough, be paranoid, be proactive.
[lean-ctx: 995→194 tok, -81%]
