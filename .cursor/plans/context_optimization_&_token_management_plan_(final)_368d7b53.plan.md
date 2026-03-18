---
name: Context Optimization & Token Management Plan (Final)
overview: Implement a "Kernel + Modules" architecture for context management, enforced by native tool capabilities. Refactor core files (`AGENTS.md`, etc.) to be lean "Kernels", move standards to `docs/standards/`, and use Git hooks + IDE hooks to prevent regression and context bloat.
todos:
  - id: create-standards-modules
    content: Create docs/standards/ directory and populate with extracted standards (rust.md, testing.md, solid.md, security.md, oop.md, git.md)
    status: pending
  - id: refactor-kernels
    content: Refactor AGENTS.md, CLAUDE.md, GEMINI.md to be lean Kernels with links to standards
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

# Context Optimization & Token Management Plan (Final)

## 1. Implement "Kernel + Modules" Architecture

Refactor the core agent files to be lean "Kernels" containing only critical identity, safety, and routing information. Move detailed standards to referenceable "Modules".

### The Modules (`docs/standards/`)

Create a centralized `docs/standards/` directory to house detailed rules.

- `**docs/standards/rust.md**`: Detailed Rust coding standards.
- `**docs/standards/testing.md**`: Testing standards, patterns, and examples.
- `**docs/standards/solid.md**`: SOLID principles and architectural guidelines.
- `**docs/standards/security.md**`: Security requirements, masking, and authorization rules.
- `**docs/standards/oop.md**`: OOP best practices.
- `**docs/standards/git.md**`: Git workflow and commit conventions.

### The Kernels (Protected Files)

Refactor these files to act as **Routers** and **Identity Definitions**.

- `**AGENTS.md` (The Constitution):**
  - **Content:** Project Overview, High-Level Role, Critical Constraints, Escalation Protocol, Links to Standards.
  - **Constraint:** Max 100 lines.
- `**CLAUDE.md` (The Orchestrator):**
  - **Content:** Orchestration rules, MCP hooks, `context-mode` config.
  - **Constraint:** Max 100 lines.
- `**GEMINI.md` (The Researcher):**
  - **Content:** Research role, read-only analysis workflows.
  - **Constraint:** Max 50 lines.

## 2. Standardize Ignore Files (Immediate Token Savings)

Create consistent, strict ignore files for all IDEs.

- **Files:** `.cursorignore`, `.claudeignore`, `.windsurfignore`, `.codexignore`, `.geminiignore`
- **Content:** Exclude lock files, build artifacts (`target/`), large assets (`*.db`, `*.log`), and generated docs.

## 3. Enforcement & Automation (The "Muscle")

### A. Git Pre-Commit Hooks (The Gatekeeper)

Prevent "Context Rot" by rejecting commits that bloat the Kernels.

- **Script:** Create `scripts/git-hooks/check-kernel-size.sh`
  - Logic: Fails if `AGENTS.md` > 100 lines, `CLAUDE.md` > 100 lines, or `GEMINI.md` > 50 lines.
- **Config:** Add to `.pre-commit-config.yaml`.

### B. Claude Code Hooks (The Active Guard)

Leverage existing `context-mode` hooks in `.claude/settings.json`.

- `**context-monitor.sh`:** Ensure this script (configured in `Notification` hook) checks token usage and warns the user if context usage is high (>50%), suggesting compaction.
- `**pre-tool-gate.sh`:** Verify it prevents reading "Ignored" files (like `Cargo.lock`) even if the model asks for them, returning a "Use grep instead" error message.

### C. Cursor Rules (The Linter)

- **Meta-Rule:** Update `AGENTS.md` (read by Cursor) to include a "Context Hygiene" protocol:
  - "If you have exchanged >10 messages, check if you need to summarize/compact."
  - "Always prefer referencing `docs/standards/` over asking for rules."

## 4. Execution Steps

1. **Modules:** Create `docs/standards/` and extract content.
2. **Kernels:** Truncate `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` to reference modules.
3. **Ignores:** Create `.*ignore` files.
4. **Hooks:** Create `check-kernel-size.sh` and update `.pre-commit-config.yaml`.
5. **Docs:** Update `AGENTS.md` with the "Context Hygiene" protocol.

## 5. Verification

- **Test Hook:** Try to commit a bloated `AGENTS.md` -> Expect failure.
- **Test Ignore:** Try to read `Cargo.lock` in Claude Code -> Expect interception/warning.
- **Test References:** Verify agents can find standards via links.

