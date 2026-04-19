# Test Plan: session-init-enforcer.sh

## Scope
Verify the UserPromptSubmit hook correctly injects init preamble when flags are
missing, and is silent once both flags are set.

## Scenarios

### A — enforcer hook
| ID  | Condition                          | Expected output                          |
|-----|------------------------------------|------------------------------------------|
| A1  | No CLAUDE_SESSION_ID               | Silent (exit 0, no output)               |
| A2  | Both flags missing                 | Full preamble (serena + ctxIntent steps) |
| A3  | Serena flag set, ctx missing       | Partial preamble (ctxIntent only)        |
| A4  | Ctx flag set, serena missing       | Partial preamble (serena steps only)     |
| A5  | Both flags set                     | Silent (exit 0, no output)               |

### B — pre-tool-gate-v2.sh Grep paths (regression)
| ID  | Condition                          | Expected                                  |
|-----|------------------------------------|-------------------------------------------|
| B1  | No serena-init flag                | Section 0 block                           |
| B2  | Serena-init set, no ctx flag       | Section 0B block                          |
| B3  | All flags, `func NewWorker`        | Section 6 block + findSymbol hint         |
| B4  | All flags, `WorkerPool` (Pascal)   | Section 6 block + findSymbol + name       |
| B5  | All flags, `mempalace` (general)   | Section 6 block + ctxSearch + query       |

### C — session-init.sh output (regression)
| ID  | Condition                          | Expected                                  |
|-----|------------------------------------|--------------------------------------------|
| C1  | .serena/ present                   | Step 5 = "REQUIRED to unlock Grep"        |
| C2  | No .serena/ dir                    | Step 4 = "REQUIRED to unlock Grep"        |
