---
name: release-prep
description: >
  Release Prep — parallel 4-agent release readiness audit.
  Spawns Manifest, CHANGELOG, Migrations, and Rollback agents concurrently,
  then synthesizes a unified go/no-go report.
  Use before cutting a release, tagging a version, or merging a release branch.
triggers:
  - /release-prep
  - release prep
  - release readiness
  - pre-release audit
  - release check
  - ready to release
version: 1.0.0
model: sonnet
allowed-tools:
  - Read
  - Glob
  - Bash
  - Agent
  - advisor
---

# Release Prep — 4-Agent Parallel Release Readiness Audit

Dispatches four parallel subagents to audit release readiness signals, then synthesizes a
unified go/no-go report. When any agent reports WARN or FAIL, performs RCA before concluding.

## When to Use

- Before tagging a release (`git tag vX.Y.Z`)
- Before merging a release branch to main
- Before deploying to production after a long feature window
- When asked "are we ready to release?" or "release check"

---

## Instructions

### Step 1 — Gather Release Context

Before dispatching agents, collect baseline info:

```bash
# Current version in repo (check go.mod, package.json, Chart.yaml, or VERSION file)
cat VERSION 2>/dev/null || cat package.json 2>/dev/null | jq -r '.version' || grep "^module" go.mod 2>/dev/null

# Most recent tag
git describe --tags --abbrev=0 2>/dev/null || git log --oneline -5

# Commits since last tag (unreleased changes)
git log $(git describe --tags --abbrev=0 2>/dev/null)..HEAD --oneline 2>/dev/null | head -30

# Pending/uncommitted changes
git status --short
```

If `$ARGUMENTS` specifies a version (e.g. `/release-prep v1.2.0`), use it as the target version.

---

### Step 2 — Dispatch 4 Parallel Agents

Launch all four simultaneously. Each must return a **single structured block**.

---

**Agent 1 — Manifest Agent**

```
Audit deployment manifests and release configuration for release readiness.

Check:
1. K8s manifests (if present): image tags are not `:latest`, resource limits/requests are set,
   replica counts are appropriate for production
2. Helm charts (if present): appVersion matches intended release version, Chart.yaml version bumped
3. Docker Compose / docker-bake.hcl (if present): no dev-only overrides leaking to prod target
4. CI release pipeline (e.g. .github/workflows/release.yml): triggers on correct branch/tag pattern
5. Environment-specific configs: no debug flags, no test data seeds in prod config

Output as single structured block:
MANIFEST_STATUS=OK|WARN|FAIL
IMAGE_TAGS=<pinned|latest_detected|N/A>
RESOURCE_LIMITS=<set|missing|N/A>
PIPELINE_READY=<yes|no|N/A>
NOTES=<one-line summary or "none">
```

---

**Agent 2 — CHANGELOG Agent**

```
Audit CHANGELOG and release notes for release readiness.

Check:
1. CHANGELOG.md (or RELEASES.md, NEWS.md) exists and has an entry for the upcoming version
2. The upcoming version entry is not marked [Unreleased] or [WIP]
3. The entry covers all significant commits since the last tag
   (compare: git log <last-tag>..HEAD --oneline to CHANGELOG entries)
4. Version number follows semver (vMAJOR.MINOR.PATCH)
5. If this is a MAJOR or MINOR bump: migration notes or breaking changes section is present
6. PR/issue links in CHANGELOG are well-formed (not placeholder text)

Output as single structured block:
CHANGELOG_STATUS=OK|WARN|FAIL
VERSION_IN_CHANGELOG=<version found or "missing">
BREAKING_CHANGES_NOTED=<yes|no|N/A>
UNRELEASED_ENTRIES=<count>
NOTES=<one-line summary or "none">
```

---

**Agent 3 — Migrations Agent**

```
Audit database migrations for release readiness.

Check:
1. Any new migration files present since last tag
   (look in db/migrations/, migrations/, flyway/, liquibase/ — or equivalent)
2. Migrations are numbered/timestamped sequentially (no gaps, no duplicates)
3. Each migration has a corresponding down/rollback migration (or is documented as irreversible)
4. No migration modifies a column in a way that breaks the previous release's models
   (e.g. NOT NULL without DEFAULT on an active table)
5. Migration was run in staging/preprod (check migration state table if accessible)
6. If no migrations directory exists: output N/A with a note

Output as single structured block:
MIGRATION_STATUS=OK|WARN|FAIL
NEW_MIGRATIONS=<count or 0>
REVERSIBLE=<all|partial|none|N/A>
BACKWARD_COMPATIBLE=<yes|no|unknown>
STAGED=<yes|no|unknown|N/A>
NOTES=<one-line summary or "none">
```

---

**Agent 4 — Rollback Agent**

```
Audit rollback readiness for the upcoming release.

Check:
1. Rollback procedure is documented (RUNBOOK.md, docs/runbooks/, or inline in CHANGELOG)
2. The previous release artifact is still available (previous Docker image tag, previous binary)
   - For GitHub releases: check that previous tag exists and has assets
   - For container registries: verify previous image tag is not overwritten
3. No irreversible operations in this release (schema drops, data transforms without backups)
4. Feature flags: are new features behind a flag that can be turned off without a redeploy?
5. Minimum downtime rollback: is there a one-command or one-click rollback path?

Output as single structured block:
ROLLBACK_STATUS=OK|WARN|FAIL
PROCEDURE_DOCUMENTED=<yes|no>
PREVIOUS_ARTIFACT=<available|unavailable|unknown>
IRREVERSIBLE_OPS=<none|list>
FEATURE_FLAGGED=<yes|partial|no>
NOTES=<one-line summary or "none">
```

---

### Step 3 — Synthesize Go/No-Go Report

After all four agents complete, produce this report:

```
## Release Prep Report — <timestamp>

**Target version:** <version>
**Overall verdict:** ✅ GO | ⚠️ CONDITIONAL GO | ❌ NO-GO

### Signal Summary
| Agent      | Status | Key Finding |
|------------|--------|-------------|
| Manifest   | OK/WARN/FAIL | <one line> |
| CHANGELOG  | OK/WARN/FAIL | <one line> |
| Migrations | OK/WARN/FAIL | <one line> |
| Rollback   | OK/WARN/FAIL | <one line> |

### Verdict Criteria
- ✅ GO: all four agents OK
- ⚠️ CONDITIONAL GO: at most one WARN, zero FAIL — list blocking actions before release
- ❌ NO-GO: any FAIL, or two or more WARNs

### Blocking Actions (if any)
<list of required fixes before release — empty if GO>

### Details
<expand WARN or FAIL rows with full agent output>

### Checked
- [x] Deployment manifests + pipeline config
- [x] CHANGELOG / release notes
- [x] Database migrations + reversibility
- [x] Rollback procedure + previous artifact

### Not Checked
- [ ] <anything inaccessible or not applicable — be explicit>

### Recommendation
<lead with: "Release is GO", "Fix X before releasing", or "Do not release until Y is resolved">
```

---

### Step 4 — RCA for WARN/FAIL

If any agent reports WARN or FAIL:

1. Do NOT conclude from a single signal — cross-reference agents.
2. State hypothesis explicitly: "Hypothesis: X blocks release because Y, evidenced by [Migration agent: no down migration] + [Rollback agent: irreversible ops]"
3. List what additional checks would confirm or refute the hypothesis.
4. Call `advisor` before labeling anything NO-GO — confirm the finding is real and not a false positive (e.g. migration table confirms staging run but agent couldn't query it).
