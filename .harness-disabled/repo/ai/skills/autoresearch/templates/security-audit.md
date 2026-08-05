# Security Audit Template (Financial Services)

Pre-filled configuration for comprehensive security audit with financial services context.

## Fields

```
Goal: Comprehensive security audit with financial services context
Scope: {auto-detect: src/api/**, src/middleware/**, src/auth/**, src/services/**}
Depth: standard
Focus: Authentication, authorization, data handling, PCI-DSS sensitive flows
Iterations: 15
Role: Architect
```

## Financial Services Context

These areas deserve extra scrutiny in Axos repos:

- **PCI-DSS**: Cardholder data handling, encryption at rest and in transit, tokenization
- **SOC2**: Audit trail completeness, access control verification, change management
- **Regulatory**: Data residency, retention policies, right to erasure compliance
- **Auth flows**: Token handling, session management, privilege escalation paths
- **Data exposure**: Logging of sensitive fields, error messages leaking internals
- **API boundaries**: Rate limiting, input validation, CORS configuration

## Strategy Notes

- Every finding requires code evidence (file:line + attack scenario) — no theoretical fluff
- Classify by severity: CRITICAL > HIGH > MEDIUM > LOW
- Map to OWASP Top 10 and STRIDE categories
- For financial data paths, check both encryption and access control
- Flag any hardcoded credentials, API keys, or connection strings
