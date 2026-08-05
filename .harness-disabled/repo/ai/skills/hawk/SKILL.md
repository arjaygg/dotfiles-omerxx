---
name: hawk
description: >
  Hawk — legacy shim. Multi-language Go/Python/TypeScript reviewer covering Architecture,
  Quality, Resilience, and Security. Superseded by lensed-review; this shim forwards there and
  pins Hawk's severity-ranked findings table so existing callers keep working.
triggers:
  - hawk review
  - /hawk
version: 4.0.0
model: sonnet
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
disable_model_invocation: false
---

# Hawk (shim → `lensed-review`)

This skill holds **no review logic**. Hawk's four dimensions are now lenses in
`ai/skills/lensed-review/lenses.toml`. Retirement record: `ai/skills/REMOVALS.md`.

## Forward

Invoke `lensed-review` with lenses `correctness`, `style`, `resilience`, `security`; add `doubt`
when the caller passes `--adversarial`. `--deep`, `--effort`, and `--post-pr` pass through
unchanged. Do not re-implement any dimension here.

## Legacy output contract (pinned)

Callers expect this shape. Render `lensed-review` findings into it. Severity is assigned at this
rendering step (Coordinator triage) — lenses emit no `severity` field of their own.

- Dedupe on `(file + line ± 3)` OR `(file + lens + first 20 chars of trigger_condition,
  lowercased)`; keep the highest-severity instance.
- Sort CRITICAL → HIGH → MEDIUM → LOW.
- Verdict: any CRITICAL → *Request changes*; HIGH ≥ 2 → *Request changes*; HIGH = 1 → *Needs work*;
  MEDIUM only → *Approve with minor suggestions*; LOW only → *Approve with minor notes*; none →
  *LGTM*.
- Executive summary blockquote, then the table:

```
> **Hawk review** · X critical · Y high · Z medium · W low
>
> [what changed]. [primary concern]. **Verdict: [VERDICT]**

| Severity | Category | File:Line | Description | Fix |
|----------|----------|-----------|-------------|-----|
```

- `--post-pr`: summary as a block comment; CRITICAL/HIGH inside diff hunks as inline comments via
  `gh api repos/<owner>/<repo>/pulls/<N>/comments`; everything else as one block comment.
  `--post-pr=block` posts summary + full table as a single block comment.
