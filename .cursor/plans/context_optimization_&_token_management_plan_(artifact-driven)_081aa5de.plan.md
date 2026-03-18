---
name: Context Optimization & Token Management Plan (Artifact-Driven)
overview: Implement a "Kernel + Modules" architecture for context management, enforced by native tool capabilities and an "Artifact-Driven" compaction strategy. Refactor core files (`AGENTS.md`, etc.) to be lean "Kernels", move standards to `docs/standards/`, and enforce that state is persisted in artifacts (plans, ADRs) rather than chat history.
todos:
  - id: create-standards-modules
    content: Create docs/standards/ directory and populate with extracted standards (rust.md, testing.md, solid.md, security.md, oop.md, git.md, context.md, routing.md)
    status: pending
  - id: refactor-kernels
    content: Refactor AGENTS.md, CLAUDE.md, GEMINI.md to be lean Kernels with links to standards
    status: pending
  - id: update-pre-compact-hook
    content: Update .claude/hooks/pre-compact.sh to prioritize plans/ and docs/adr/ during compaction
    status: pending
  - id: create-ignore-files
    content: Create .cursorignore, .claudeignore, .windsurfignore, .codexignore, .geminiignore with strict patterns
    status: pending
  - id: implement-git-hooks
    content: Create scripts/git-hooks/check-kernel-size.sh and add to .pre-commit-config.yaml
    status: pending
  - id: update-claude-hooks
    content: Verify/Update .claude/hooks/pre-tool-gate.sh to enforce read restrictions
    status: pending
isProject: false
---

# Context Optimization & Token Management Plan (Artifact-Driven)

## 1. Implement "Kernel + Modules" Architecture
Refactor the core agent files to be lean "Kernels" containing only critical identity, safety, and routing information. Move detailed standards to referenceable "Modules".

### The Modules (`docs/standards/`)
Create a centralized `docs/standards/` directory to house detailed rules.
- **`docs/standards/rust.md`**: Detailed Rust coding standards (from `AGENTS.md` & `rust-standards.mdc`).
- **`docs/standards/testing.md`**: Testing standards, patterns, and examples.
- **`docs/standards/solid.md`**: SOLID principles and architectural guidelines.
- **`docs/standards/security.md`**: Security requirements, masking, and authorization rules.
- **`docs/standards/oop.md`**: OOP best practices.
- **`docs/standards/git.md`**: Git workflow and commit conventions.
- **`docs/standards/context.md`**: Context management, compaction strategies, and artifact-driven workflows.
- **`docs/standards/routing.md`**: **(NEW)** Task routing tables, tool usage (RTK, MCP), and subagent delegation rules.

### The Kernels (Protected Files)
Refactor these files to act as **Routers** and **Identity Definitions**.
- **`AGENTS.md` (The Constitution):**
  - **Content:** Project Overview, High-Level Role, Critical Constraints, Escalation Protocol, Links to Standards.
  - **Constraint:** Max 100 lines.
- **`CLAUDE.md` (The Orchestrator):**
  - **Content:** High-level Orchestration identity, MCP hooks config, `context-mode` settings.
  - **Refactor:** Move detailed routing tables and workflows to `docs/standards/routing.md`.
  - **Constraint:** Max 100 lines.
- **`GEMINI.md` (The Researcher):**
  - **Content:** Research role, read-only analysis workflows.
  - **Constraint:** Max 50 lines.

## 2. Implement "Artifact-Driven Context" Strategy
Shift the "Source of Truth" from chat history (ephemeral) to persistent artifacts (files). This makes compaction lossless.

- **Define in `docs/standards/context.md`:**
  - **Rule:** "If it's not in a file (Plan, ADR, Todo), it doesn't exist."
  - **Protocol:**
    - **Start of Task:** Create/Update `plans/<task-name>.md`.
    - **During Task:** Update the plan with decisions/progress.
    - **End of Session:** Ensure `plans/` is up-to-date.
    - **Compaction:** When compacting, the model only needs to read the *current plan* to restore state, ignoring the chat history.
  - **Session Partitioning:** "One task, one session. Clear context after git commit."

## 3. Enforcement & Automation (The "Muscle")

### A. Git Pre-Commit Hooks
- **Script:** Create `scripts/git-hooks/check-kernel-size.sh`
  - Logic: Fails if `AGENTS.md` > 100 lines, `CLAUDE.md` > 100 lines, or `GEMINI.md` > 50 lines.
- **Config:** Add to `.pre-commit-config.yaml`.

### B. Claude Code Hooks
- **`context-monitor.sh`:** Ensure this script checks token usage and suggests creating a **Checkpoint (Artifact Update)** at 30% usage.
- **`pre-compact.sh`:** Update to explicitly prioritize `plans/*.md` and `docs/adr/*.md` during compaction.

### C. Standardize Ignore Files
- **Files:** `.cursorignore`, `.claudeignore`, `.windsurfignore`, `.codexignore`, `.geminiignore`
- **Content:** Exclude lock files, build artifacts (`target/`), large assets (`*.db`, `*.log`), and generated docs.

## 4. Execution Steps
1.  **Modules:** Create `docs/standards/` and populate (including `context.md`, `routing.md`).
2.  **Kernels:** Truncate `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` to reference modules.
3.  **Ignores:** Create `.*ignore` files.
4.  **Hooks:** Create `check-kernel-size.sh`, update `.pre-commit-config.yaml`, update `pre-compact.sh`.
5.  **Docs:** Update `AGENTS.md` with the "Context Hygiene" protocol pointing to `docs/standards/context.md`.

## 5. Verification
- **Test Hook:** Try to commit a bloated `AGENTS.md` -> Expect failure.
- **Test Artifacts:** Verify that `pre-compact.sh` output includes instructions to retain `plans/`.
- **Test References:** Verify agents can find standards via links.