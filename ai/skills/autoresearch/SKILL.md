---
name: autoresearch
description: >
  Implements the Karpathy autoresearch pattern: an autonomous modify → verify → keep/discard
  loop that iteratively improves any artifact with a measurable metric. Use this skill
  whenever the user wants to improve something repeatedly until a goal is hit — test
  coverage, build time, bundle size, failing tests, security findings, latency, prompt
  eval pass rates. Invoke proactively when the user says "fix all failing tests", "optimize
  until X", "run overnight", "keep improving", "make all tests pass", "reduce build time",
  "run experiments", or whenever a bounded loop of modify→verify→keep/discard would help.
  Offers five modes: /autoresearch (metric optimization), /autoresearch:fix (drive a count
  to zero), /autoresearch:security (read-only STRIDE+OWASP audit), /autoresearch:learn
  (doc generation loop), /autoresearch:scenario (edge case discovery). Worktree-isolated,
  ADO-integrated, pctx/Serena-aware, Axos-safe.
---

# Autoresearch Skill

Implements the Karpathy autoresearch pattern: an autonomous modify → verify → keep/discard
loop that iteratively improves any artifact with a parseable metric. Each kept improvement
becomes the new baseline so gains compound. Experiments run in git-isolated worktrees.

---

## Subcommand Routing

| Invocation | Mode | Description |
|---|---|---|
| `/autoresearch` | **optimize** | Iterative metric optimization (main loop) |
| `/autoresearch:fix` | **fix** | Drive failing count to zero (tests, lint, build) |
| `/autoresearch:security` | **security** | Read-only STRIDE + OWASP threat analysis |
| `/autoresearch:learn` | **learn** | Documentation / artifact generation loop |
| `/autoresearch:scenario` | **scenario** | Edge case discovery across 12 scenario dimensions |

Route to the appropriate section below based on invocation.

---

## SAFETY RULES (apply to ALL modes)

These constraints exist to make the loop predictable and reversible. Follow them even when
a hypothesis looks very promising — the whole value of the pattern is that each experiment
is independently verifiable and cleanly undoable.

1. **Scope is the contract**: Only modify files matching the declared `Scope` pattern.
   Any hypothesis that requires touching out-of-scope files is a sign the scope was
   defined too narrowly — surface this to the user rather than silently expanding it.
2. **Sensitive files are off-limits**: Do not touch `.env`, `*.secret`, `*credential*`,
   `*password*`, `*.pem`, `*.key`, `*.pfx`, `*.p12`, `appsettings.Production.*`,
   `appsettings.Staging.*`. The `pre-tool-gate.sh` hook enforces this at the tool level,
   but the skill should refuse these hypotheses before even reaching a tool call.
3. **Bounded by default**: Default `Iterations: 10`. Do not run unbounded without explicit
   `Iterations: unlimited` from the user. Unbounded loops can run for hours; the user
   should make that choice deliberately.
4. **Worktree isolation**: Run all experiments in `.trees/<goal-slug>/` unless the user
   explicitly opts out with `Worktree: false`. This keeps the main branch clean and makes
   it easy to abandon a failed run without cleanup.
5. **Guard is a hard gate**: A result that improves the metric but fails the guard is
   discarded — the guard exists to prevent regressions that look like wins. Do not propose
   relaxing the guard; if it keeps blocking, surface the pattern to the user.
6. **Immutable eval**: If a Verify or Guard command is a script or file, do not modify it.
   The eval harness is the trust anchor — if it changes, you can't compare iterations.
7. **Commit before verify**: Commit the change before running the verify command. This is
   what makes `git reset --hard HEAD~1` a clean undo — without the commit, a failed verify
   leaves the worktree in a dirty state that's harder to recover from.

---

## MODE: optimize (main `/autoresearch`)

### Setup Gate

Before starting the loop, collect all required fields. If the user's invocation includes
them inline, skip prompting. Otherwise, interactively ask for missing ones.

**Required fields:**

| Field | Description | Example |
|---|---|---|
| `Goal` | What to achieve | "Increase test coverage to 90%" |
| `Scope` | File patterns agent may modify | `tests/**/*.cs` |
| `Metric` | Name of the number being tracked | "Line coverage percentage" |
| `Direction` | `higher` or `lower` | `higher` |
| `Verify` | Shell command that outputs the metric as a bare number on stdout | `dotnet test ... \| grep "Line" \| awk '...'` |

**Optional fields:**

| Field | Default | Description |
|---|---|---|
| `Guard` | none | Must-exit-0 command; failure reverts the experiment |
| `Iterations` | 10 | Max loop iterations; use `unlimited` for unbounded |
| `Worktree` | true | Run in `.trees/<goal-slug>/`; `false` to use current branch |
| `TimeoutPerIter` | none | Max seconds per verify run (kills runaway experiments) |

**Setup validation:**
1. Run the Verify command once to establish the **baseline metric**. If it fails, stop and
   help the user fix it before starting.
2. If `Worktree: true` (default), create the isolated worktree now:
   ```bash
   $HOME/.dotfiles/.claude/scripts/stack create feat/autoresearch-<goal-slug> main
   ```
   All subsequent work happens in `.trees/<goal-slug>/`.
3. Confirm: "Baseline: `<metric>`. Starting optimization loop. Goal: `<goal>`."
4. Create `autoresearch-results.tsv` in the worktree root with header:
   ```
   iteration	status	metric_before	metric_after	delta	description	commit_sha	timestamp
   ```

### The 9-Step Loop

Execute this loop up to `Iterations` times (or until `Goal` metric is reached):

#### Step 1 — READ STATE

Using pctx/Serena (batch via `mcp__pctx__execute_typescript`):
- Read `autoresearch-results.tsv` for history of what worked and what failed
- Identify scope files and their current state via `Serena.listDir`
- Look for patterns: what hypotheses were tried? What was untried?

Batching these reads matters here — forming a hypothesis without full scope context leads
to low-quality changes that are likely to be reverted.

```typescript
async function run() {
  const [scopeFiles, overview] = await Promise.all([
    Serena.searchForPattern({ pattern: ".", relative_path: "<scope-dir>" }),
    Serena.getSymbolsOverview({ relative_path: "<scope-dir>" }),
  ]);
  return { scopeFiles, overview };
}
```

Avoid reading results.tsv with the Read tool — it can grow large and pollute the context
window with raw data you only need a slice of. Query specific rows with grep/awk instead.

#### Step 2 — IDEATE

Form one focused hypothesis based on:
- What's the most impactful untested/unoptimized area?
- What failed before? (avoid repeating failed approaches)
- What worked? (build on successful patterns)

The hypothesis must be:
- **Focused**: one change at a time
- **Reversible**: expressible as a git diff
- **Within scope**: only touches declared Scope files
- **Testable**: the Verify command will measure its effect

Write out the hypothesis explicitly before modifying anything:
> "Hypothesis #N: Adding tests for `<method>` will increase coverage from `<before>` to
> approximately `<estimate>` because `<reasoning>`."

#### Step 3 — MODIFY

Make exactly the changes dictated by the hypothesis. Use:
- `Serena.replaceSymbolBody` / `Serena.insertAfterSymbol` for symbol-aware edits
- `Edit` tool for line-based changes when symbol bounds are unclear

Keep changes minimal and focused on the hypothesis. Do not refactor surrounding code.

#### Step 4 — GIT COMMIT (before verification)

```bash
git add <scope-files>
git commit -m "autoresearch(iter-N): <hypothesis description>"
```

Committing before verification is what makes the loop safe to interrupt at any point —
each experiment is an atomic unit in git. The commit message should describe the hypothesis
so the results log is human-readable without needing to diff each commit.

#### Step 5 — RUN VERIFY

Execute the Verify command. If `TimeoutPerIter` is set, kill after that many seconds.

Capture:
- Exit code
- Full stdout/stderr (for crash diagnosis)
- The metric value on stdout's last non-empty line (or parse per the Verify spec)

If the command outputs multiple lines, parse the metric from the expected format. If
parsing fails, treat as crash (go to Step 7).

#### Step 6 — EXTRACT METRIC

Parse the metric value as a float. Compare against `metric_before` (the value before
this iteration's modify step — from the previous iteration's `metric_after`, or baseline).

Calculate `delta = metric_after - metric_before`.

#### Step 7 — CRASH DETECTION

If the verify command crashed (non-zero exit AND metric extraction failed):

1. Read the error output. Try to fix the issue (e.g., syntax error in modified file).
2. If fixable in ≤3 attempts: fix → re-run Verify → continue to Step 8.
3. If not fixable after 3 attempts:
   - `git reset --hard HEAD~1` (revert the change)
   - Log: `status=crash`, `metric_after=—`
   - Increment crash counter. If >3 crashes in a row, stop and report to user.
   - Go to Step 9.

#### Step 8 — DECIDE

**Case A: Metric improved** (`direction=higher`: delta > 0; `direction=lower`: delta < 0)

- If `Guard` is defined: run the Guard command.
  - Guard passes (exit 0): **KEEP**. The commit stays.
    - If guard failed on fix attempt: try to fix (≤2 rework attempts), then discard.
  - Guard fails: **DISCARD**. `git reset --hard HEAD~1`. Log `status=discard-guard`.
- If no `Guard`: **KEEP**. The commit stays.

**Case B: Metric same or worse**

- `git reset --hard HEAD~1`
- Log `status=discard`

**KEEP path**: Update `metric_before` to `metric_after` for next iteration.

**Check goal**: If `Goal` is a target metric (e.g., "90%") and it's been reached → stop
the loop early, print summary, and exit.

#### Step 9 — LOG & REPEAT

Append to `autoresearch-results.tsv`:
```
<N>	<status>	<metric_before>	<metric_after>	<delta>	<hypothesis_short>	<sha_or_dash>	<ISO8601_timestamp>
```

Status values: `keep`, `discard`, `discard-guard`, `crash`

Print one-line status: `[iter N] <status>: <metric_before> → <metric_after> (<+/- delta>)`

Increment iteration counter. If `N < Iterations` and goal not met → go to Step 1.

### Post-Loop Summary

After the loop ends (iterations exhausted, goal met, or user interrupt):

1. Print final summary table from results.tsv
2. Report: X kept, Y discarded, Z crashes. Net improvement: `<baseline>` → `<final>`.
3. If `Worktree: true`: remind user that all kept changes are committed in
   `.trees/<goal-slug>/`. To merge: `$HOME/.dotfiles/.claude/scripts/stack-pr` or
   review with `git log` in the worktree.
4. Offer to post the summary as an ADO PR comment if the user is working on a PR:
   ```bash
   az repos pr update --id <PR_ID> \
     --description "$(cat autoresearch-results.tsv | column -t)" \
     --organization "https://dev.azure.com/bofaz"
   ```

---

## MODE: fix (`/autoresearch:fix`)

**Purpose**: Drive a count-based metric (failing tests, lint errors, build errors) to zero.

**Simplified Setup Gate:**

Required fields:
- `Target`: What to make pass (e.g., "Make all tests pass", "Fix all lint errors")
- `Scope`: Files the agent may modify (source files AND/OR test files)
- `Iterations`: Default 10

The skill auto-derives:
- `Metric`: Failing count (parsed from verify output)
- `Direction`: lower (target: 0)
- `Verify`: auto-suggested based on file extensions in scope:
  - `.cs` files → `dotnet test --no-build 2>&1 | grep -c "Failed\|Error" || echo 0`
  - `.go` files → `go test ./... 2>&1 | grep -c "FAIL" || echo 0`
  - `.ts/.js` files → `npx jest 2>&1 | grep -c "FAIL" || echo 0`
  - Custom: ask user

**Loop behavior**: Same 9-step loop as optimize mode, but:
- Step 2 (Ideate): Focus on reading error messages from the last verify run to form the fix hypothesis
- Step 8: Success = `metric_after == 0`. Stop immediately when all failures cleared.
- Crash recovery is more aggressive (3→5 fix attempts before giving up on a crash)

**Format**:
```
/autoresearch:fix
Target: <what to make pass>
Scope: <files>
[Verify: <custom command>]
[Iterations: N]
```

---

## MODE: security (`/autoresearch:security`)

**Purpose**: Read-only comprehensive security analysis. No file modifications. No commits.

**Dimensions** (iterate through each, producing findings):

1. **STRIDE Threat Model**: For each component in scope, identify:
   - Spoofing (identity verification)
   - Tampering (data integrity)
   - Repudiation (audit trails)
   - Information Disclosure (data exposure)
   - Denial of Service (availability)
   - Elevation of Privilege (authorization bypass)

2. **OWASP Top 10** scan against scope files:
   A01 Broken Access Control, A02 Cryptographic Failures, A03 Injection,
   A04 Insecure Design, A05 Security Misconfiguration, A06 Vulnerable Components,
   A07 Identification and Authentication Failures, A08 Software and Data Integrity Failures,
   A09 Security Logging and Monitoring Failures, A10 Server-Side Request Forgery

3. **Red-team (4 personas)**:
   - External attacker (unauthenticated, internet-facing)
   - Insider threat (authenticated employee, misuse of legitimate access)
   - Compliance auditor (PCI-DSS, SOC2, GDPR angle — financial data context)
   - Pentester (automated scanning, common exploit patterns)

4. **Dependency review**: Flag any dependencies in scope files that are known-vulnerable
   or have suspicious patterns (evaluate, don't confirm — no internet access)

**Output format**:

```markdown
# Security Audit Report — <scope> — <date>

## Summary
- Critical: N | High: N | Medium: N | Low: N | Info: N

## Findings

### [CRITICAL] <Finding Title>
**Category**: <STRIDE / OWASP ID> | **Persona**: <persona>
**Location**: `<file>:<line>`
**Description**: <what the vulnerability is>
**Impact**: <what an attacker can do>
**Recommendation**: <specific fix>

[... repeat for each finding ...]

## Methodology
[Brief note on what was analyzed and how]
```

Save the report to `security-audit-<date>.md` in the current directory.

**Format**:
```
/autoresearch:security
Scope: <files or glob>
[Depth: quick|standard|thorough]   # default: standard
```

---

## MODE: learn (`/autoresearch:learn`)

**Purpose**: Generate and validate documentation, XML doc comments, or other artifacts
in an iterative keep/discard loop with validation as the metric.

**Loop variation**:
- `Verify` = validation script (e.g., XML well-formed check, doc coverage count)
- `Metric` = artifact count passing validation
- `Direction` = higher
- No Guard by default (output-only, no regression risk)
- Each iteration: generate one artifact unit → validate → keep if valid → log → next

**Format**:
```
/autoresearch:learn
Scope: <source files to document>
Output: <output directory>
[Format: xml-doc|markdown|openapi]   # default: inferred from scope
[Iterations: N]
```

**Iteration behavior**:
- Step 2 (Ideate): Pick the next undocumented public symbol (use Serena.getSymbolsOverview)
- Step 3 (Modify): Write the documentation to the Output directory
- Step 5 (Verify): Validate the generated file (well-formed, complete, references valid)
- Step 8 (Decide): Keep if valid, discard and try different format if invalid

---

## MODE: scenario (`/autoresearch:scenario`)

**Purpose**: Systematically discover edge cases, failure modes, and test scenarios for a
feature or flow by iterating through 12 scenario dimensions.

**No file modifications** — produces a scenario report file only.

**12 Scenario Dimensions** (iterate through each):

1. **Happy path**: Normal successful execution
2. **Error path**: Common failure conditions with graceful handling
3. **Edge case**: Boundary values, empty inputs, max/min, exact limits
4. **Abuse**: Malicious or unexpected user behavior, attempted exploits
5. **Scale**: High volume, many records, concurrent users, rate limits
6. **Concurrent**: Simultaneous operations, race conditions, double-submission
7. **Temporal**: Timing edge cases, timezone boundaries, DST, year boundaries, deadlines
8. **Data variation**: Unusual characters, encoding, NULL/empty/whitespace, very long values
9. **Permission**: Insufficient permissions, cross-tenant access, role boundaries
10. **Integration**: External service failure, partial failure, timeout, retry storms
11. **Recovery**: Crash mid-operation, partial write, idempotency, retry after failure
12. **State transition**: Invalid state machine transitions, stale state, eventual consistency

For each dimension, generate N scenarios (default 2 per dimension = 24 total). Each
scenario entry in the results file includes:

```
dimension    scenario_id    title    severity    affected_file    description    test_hint
```

**Severity levels**: Critical / High / Medium / Low / Info

**Output file**: `scenario/<YYMMDD-HHMM>-<slug>/scenario-results.tsv`

**Format**:
```
/autoresearch:scenario
Scenario: <feature or flow to analyze>
Scope: <relevant source files>
[Dimensions: comma-separated list]   # default: all 12
[Iterations: N]                      # scenarios per dimension; default: 2
```

---

## Integration Points

### pctx/Serena (code understanding before modifying)

Always use `mcp__pctx__execute_typescript` to batch-read the scope before forming
hypotheses. This prevents low-quality hypotheses based on partial context.

Example batch read for Go files:
```typescript
async function run() {
  const [structure, patterns] = await Promise.all([
    Serena.getSymbolsOverview({ relative_path: "pkg/app/worker" }),
    Serena.searchForPattern({
      pattern: "func Test",
      relative_path: "pkg/app/worker",
    }),
  ]);
  return { structure, existingTests: patterns };
}
```

### Worktree Isolation (via stack-create skill)

Default: create an isolated worktree before the loop starts.
```bash
$HOME/.dotfiles/.claude/scripts/stack create feat/autoresearch-<goal-slug> main
```

All experiments, commits, and reverts happen inside `.trees/<goal-slug>/`. The main
branch is never touched. If the user Ctrl+C's mid-loop:
1. The current uncommitted changes are in the worktree
2. The worktree itself is safe to inspect or resume
3. Committed-but-discarded experiments were already reverted via `git reset`
4. `autoresearch-results.tsv` has the full audit trail

### ADO Integration

After the loop, if the user provides a PR ID:
```bash
# Post summary as PR comment
az repos pr update \
  --id <PR_ID> \
  --description "Autoresearch summary: <N> improvements kept, <baseline> → <final>" \
  --organization "https://dev.azure.com/bofaz"
```

For detailed reporting, write to a wiki page or PR thread comment using:
```bash
az devops wiki page create \
  --path "autoresearch/<date>-<goal>" \
  --content "$(cat autoresearch-results.tsv)" \
  --organization "https://dev.azure.com/bofaz" \
  --project "Axos-Universal-Core"
```

### Context Window Management

Long loops produce large output. Route verify command output to the sandbox:
- Use `mcp__plugin_context-mode_context-mode__ctx_execute` to run verify commands
  when output is expected to be large (build logs, test runs)
- Use `rtk` prefix for all Bash commands (hook handles this automatically)
- Never dump full build logs into chat — extract only the metric line

---

## Quick Reference Examples

### Example 1: Increase .NET test coverage overnight
```
/autoresearch
Goal: Increase line coverage to 90%
Scope: tests/**/*.cs
Metric: Line coverage percentage
Direction: higher
Verify: dotnet test --collect:"XPlat Code Coverage" --results-directory ./coverage && reportgenerator -reports:./coverage/**/coverage.cobertura.xml -targetdir:./coverage/report -reporttypes:TextSummary && grep "Line coverage" ./coverage/report/Summary.txt | awk -F'[:%]' '{print $2}' | tr -d ' '
Guard: dotnet build --no-restore && dotnet test --no-build --filter "Category!=Integration"
Iterations: 20
```

### Example 2: Fix all failing Go tests
```
/autoresearch:fix
Target: Make all tests pass
Scope: pkg/app/worker/worker.go, pkg/app/worker/worker_test.go
Iterations: 10
```

### Example 3: Security audit before merging auth PR
```
/autoresearch:security
Scope: src/Auth/**/*.cs, src/Middleware/AuthMiddleware.cs
Depth: thorough
```

### Example 4: Reduce build time
```
/autoresearch
Goal: Reduce build time below 180 seconds
Scope: *.csproj, Directory.Build.props
Metric: Build time in seconds
Direction: lower
Verify: time dotnet build --no-restore 2>&1 | grep real | awk '{print $2}' | sed 's/m/*60+/;s/s//' | bc
Guard: dotnet test --no-build
Iterations: 15
```

### Example 5: Edge case discovery for transfer feature
```
/autoresearch:scenario
Scenario: User initiates a wire transfer between two Axos accounts
Scope: src/Services/TransferService.cs, src/Models/Transfer.cs
Iterations: 2
```

---

## Error Handling Reference

| Condition | Action |
|---|---|
| Verify command not found | Stop. Help user fix the command. |
| Baseline metric parse fails | Stop. Show raw output. Help user fix parsing. |
| Crash 1-3 in a row | Try to fix. Log crash. Continue. |
| Crash 4+ consecutive | Stop. Report. Suggest user inspect scope files. |
| Guard fails on keep | Try rework ≤2 times. Then discard. |
| Scope violation detected | Refuse hypothesis. Ideate new one without mentioning the skipped file. |
| Worktree creation fails | Warn user. Offer to run without worktree isolation (risk: experiments on current branch). |
| User Ctrl+C mid-loop | Commit is already in worktree (Step 4 ran before verify). Print current state. |
