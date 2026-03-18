---
name: Context Optimization & Token Management Plan (Refined)
overview: Implement a "Kernel + Modules" architecture for context management. Refactor `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md` to be lean "Kernel" files that reference modular standards in `docs/standards/`. Create strict ignore files to reduce context rot. establish protocols for maintaining this structure.
todos:
  - id: create-standards-modules
    content: Create docs/standards/ directory and populate with extracted standards (rust.md, testing.md, solid.md, security.md, oop.md, git.md)
    status: pending
  - id: refactor-agents-kernel
    content: Refactor AGENTS.md to be a lean Kernel with links to standards and protection header
    status: pending
  - id: refactor-claude-kernel
    content: Refactor CLAUDE.md to focus on orchestration and reference AGENTS.md
    status: pending
  - id: refactor-gemini-kernel
    content: Refactor GEMINI.md to focus on research and reference AGENTS.md
    status: pending
  - id: update-cursor-rules
    content: Update .cursor/rules/*.mdc to reference new standards docs
    status: pending
  - id: create-ignore-files
    content: Create .cursorignore, .claudeignore, .windsurfignore, .codexignore, .geminiignore with strict patterns
    status: pending
isProject: false
---

# Context Optimization & Token Management Plan (Refined)

## 1. Implement "Kernel + Modules" Architecture

Refactor the core agent files to be lean "Kernels" containing only critical identity, safety, and routing information. Move detailed standards to referenceable "Modules".

### The Modules (`docs/standards/`)

Create a centralized `docs/standards/` directory to house detailed rules.

- `**docs/standards/rust.md**`: Detailed Rust coding standards (from `AGENTS.md` & `rust-standards.mdc`).
- `**docs/standards/testing.md**`: Testing standards, patterns, and examples.
- `**docs/standards/solid.md**`: SOLID principles and architectural guidelines.
- `**docs/standards/security.md**`: Security requirements, masking, and authorization rules.
- `**docs/standards/oop.md**`: OOP best practices for applicable languages.
- `**docs/standards/git.md**`: Git workflow, commit conventions, and branching strategy.

### The Kernels (Protected Files)

Refactor these files to act as **Routers** and **Identity Definitions**.

- `**AGENTS.md` (The Constitution):**
  - **Content:** Project Overview, High-Level Role, Critical Constraints (Safety/Security), Escalation Protocol, and **Links** to `docs/standards/`*.
  - **Protection:** Add header: `<!-- DO NOT EDIT WITHOUT APPROVAL. KEEP UNDER 100 LINES. -->`
- `**CLAUDE.md` (The Orchestrator):**
  - **Content:** Orchestration specific rules, MCP hooks, `context-mode` config, Subagent definitions.
  - **Refactor:** Remove duplicate general rules; reference `AGENTS.md` for shared rules.
  - **Protection:** Add header: `<!-- DO NOT EDIT WITHOUT APPROVAL. KEEP UNDER 100 LINES. -->`
- `**GEMINI.md` (The Researcher):**
  - **Content:** Research role specific rules, read-only analysis workflows.
  - **Refactor:** Remove duplicate general rules; reference `AGENTS.md`.
  - **Protection:** Add header: `<!-- DO NOT EDIT WITHOUT APPROVAL. KEEP UNDER 50 LINES. -->`

## 2. Standardize Ignore Files (Immediate Token Savings)

Create consistent, strict ignore files for all IDEs to prevent accidental ingestion of high-token, low-value files.

- **Files to Create/Update:**
  - `.cursorignore`, `.claudeignore`, `.windsurfignore`, `.codexignore`, `.geminiignore`
- **Content Strategy:**
  - Exclude lock files (`Cargo.lock`, etc.) unless explicitly needed.
  - Exclude build artifacts (`target/`, `dist/`, `build/`).
  - Exclude large assets (`*.db`, `*.log`, `*.pdf`, images).
  - Exclude generated docs/coverage.

## 3. Tool-Specific Optimization

- **Cursor:**
  - Update `.cursor/rules/*.mdc` to be lean wrappers that *reference* `docs/standards/`* instead of embedding content.
  - Verify `rtk` usage for shell commands.
- **Claude Code / Gemini:**
  - Ensure `context-mode` hooks are active.
  - Verify `thinkingBudget` / `MAX_THINKING_TOKENS`.

## 4. Maintenance Protocol (How to Ensure)

Add a "Maintenance Protocol" section to `AGENTS.md` (or a dedicated `docs/maintenance.md` if preferred, but `AGENTS.md` is better for visibility).

- **Protocol Rules:**
  - **"Reference, Don't Duplicate":** When adding a new rule, add it to a `docs/standards/` file, then reference it. Never add bulk text to `AGENTS.md`.
  - **"Context Hygiene":** Agents must explicitly "compact context" or "summarize state" every ~10 turns.
  - **"Periodic Audit":** User/Agent should review `AGENTS.md` size periodically.

## 5. Verification

- Verify that ignore files are respected (e.g., try reading a locked file).
- Verify that agents can successfully find standards by following the links in `AGENTS.md`.

