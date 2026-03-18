---
name: Context Optimization & Token Management Plan
overview: Implement a comprehensive token management strategy across all IDEs (Claude Code, Cursor, Windsurf, Gemini, Codex) to reduce context rot and waste. This involves creating strict ignore files, modularizing heavy documentation into referenceable standards, and configuring tool-specific optimization settings.
todos:
  - id: create-ignore-files
    content: Create .cursorignore, .claudeignore, .windsurfignore, .codexignore with strict exclusion patterns
    status: pending
  - id: create-standards-docs
    content: Create docs/standards/ directory and populate with extracted standards (testing, solid, security, oop)
    status: pending
  - id: update-cursor-rules
    content: Update .cursor/rules/*.mdc to reference new standards docs instead of embedding content
    status: pending
  - id: update-agents-md
    content: Update AGENTS.md with Context Hygiene protocols and references to standards
    status: pending
  - id: update-gitignore
    content: Update .gitignore to include strict patterns as a baseline
    status: pending
isProject: false
---

# Context Optimization & Token Management Plan

## 1. Standardize Ignore Files (Immediate Token Savings)

Create consistent, strict ignore files for all IDEs to prevent accidental ingestion of high-token, low-value files (lock files, build artifacts, assets).

- **Files to Create/Update:**
  - `.cursorignore` (Cursor)
  - `.claudeignore` (Claude Code)
  - `.windsurfignore` (Windsurf)
  - `.codexignore` (Codex)
  - Update `.geminiignore` (Gemini)
  - Update `.gitignore` (as baseline)
- **Content Strategy:**
  - Exclude `Cargo.lock`, `package-lock.json`, `yarn.lock` (unless explicitly needed)
  - Exclude `target/`, `dist/`, `build/`, `node_modules/`
  - Exclude large assets: `*.svg`, `*.png`, `*.jpg`, `*.pdf`, `*.db`, `*.sqlite`, `*.log`
  - Exclude generated docs/coverage: `docs/coverage/`, `lcov-report/`

## 2. Modularize "Always-On" Context (Reduce Context Rot)

Move heavy "Always Applied" rules (Testing Standards, SOLID, Security, OOP) out of the global prompt context and into referenceable documentation. This shifts from "Always in Context" to "Reference on Demand".

- **Action:**
  - Create `docs/standards/` directory.
  - Create `docs/standards/testing.md` (Testing Standards)
  - Create `docs/standards/solid.md` (SOLID Principles)
  - Create `docs/standards/security.md` (Security Essentials)
  - Create `docs/standards/oop.md` (OOP Best Practices)
  - Create `docs/standards/rust.md` (Rust Standards - refactor from `rust-standards.mdc` if applicable)
- **Update Rules:**
  - Modify `.cursor/rules/` to *reference* these files instead of embedding them.
  - Update `AGENTS.md` to point to these standards.

## 3. Tool-Specific Optimization

Configure each IDE to maximize its native token management capabilities.

- **Claude Code:**
  - Verify `MAX_THINKING_TOKENS` (currently 8k) - consider bumping to 16k for complex tasks if budget allows, or keep lean.
  - Ensure `context-mode` hooks are active and filtering output.
- **Cursor:**
  - Refine `.cursorrules` to be lean and pointer-based.
  - Enforce `rtk` usage for shell commands (already in place, but reinforce in `AGENTS.md`).
- **Gemini:**
  - Sync `.geminiignore` with the new standard.
  - Utilize `thinkingBudget` (32k) for deep analysis tasks.
- **Windsurf/Codex:**
  - Apply ignore files.
  - Ensure they use the `docs/standards/` references.

## 4. Establish "Context Hygiene" Protocols

Add a section to `AGENTS.md` defining protocols for maintaining a clean context.

- **Protocol:**
  - **"Compact Context":** explicitly ask the agent to "compact context" or "summarize state" every ~10 turns or when switching tasks.
  - **"Reference, Don't Read":** Use `@docs/standards/testing.md` instead of asking "what are the testing rules?".
  - **"Reset on Drift":** If the conversation drifts, start a new session.

## 5. Verification

- Verify that ignore files are respected by each tool (e.g., trying to read a locked file should fail or warn).
- Check context window usage in a sample session.

