---
status: frozen
---

# Lifecycle CI portability repair

## Intent

Make PR validation use tracked canonical configuration in clean checkouts while
preserving validation of installed runtime settings when they exist.

## Acceptance

1. Workflow and setup hook checks use `ai/config/claude/settings.base.json`.
2. Hook-target and Headroom tests do not require ignored `.claude/settings.json`.
3. Installed runtime settings remain validated when present.
4. Secret-detection fixtures construct token-shaped values at runtime.
5. The complete discovered script suite and focused portability tests pass.
6. Changes remain confined to the base lifecycle stack branch and are not pushed.
