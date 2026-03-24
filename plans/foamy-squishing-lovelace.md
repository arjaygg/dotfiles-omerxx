# Plan: Show exact backend model in statusline

## Context
- When launching via .claude/scripts/claude-launch.sh, the statusline currently shows a generic "Claude" model label.
- We want the statusline to display the exact backend model actually in use (e.g., "claude-sonnet-4-6", "claude-3-7-sonnet-20250219", "gemini-3.1-pro-preview", "gemini-3-flash", "gemini-3.1-pro").
- The launcher already determines backend and sets environment, but it sometimes sets CLAUDE_CODE_MODEL to a spoofed Claude ID (for CLI compatibility), especially for Gemini/Cursor paths. We cannot change that argument because it drives the CLI behavior.
- Therefore, we will introduce a dedicated env var for the statusline to read that reflects the "real" backend model, independent of what the CLI needs.

## Approach (recommended)
1) Augment launcher to export CLAUDE_STATUSLINE_MODEL with the real backend model string for each backend.
2) Update statusline to prefer CLAUDE_STATUSLINE_MODEL (then fall back to CLAUDE_CODE_MODEL), and when provided, display the exact string verbatim (no normalization to generic names).
3) Keep existing transcript-based detection as a fallback only when neither env var is present.

## Files and precise changes

1. .claude/scripts/claude-launch.sh
- After arguments are parsed and possible --model overrides applied (around lines 226-251), set CLAUDE_STATUSLINE_MODEL based on BACKEND and available overrides.
- Proposed insertion after line 251 (right after finalizing CLAUDE_CODE_MODEL), before exec:

  ```bash
  # Expose exact backend model for statusline display
  case "$BACKEND" in
      gemini)
          export CLAUDE_STATUSLINE_MODEL="${GEMINI_MODEL_OVERRIDE:-${GEMINI_MODEL:-gemini-3.1-pro-preview}}"
          ;;
      cursor)
          export CLAUDE_STATUSLINE_MODEL="${CURSOR_MODEL_OVERRIDE:-${CURSOR_AGENT_MODEL:-gemini-3.1-pro}}"
          ;;
      router|codex)
          # Here CLAUDE_CODE_MODEL is the true Claude model we intend to use
          export CLAUDE_STATUSLINE_MODEL="${CLAUDE_CODE_MODEL}"
          ;;
      native|*)
          unset CLAUDE_STATUSLINE_MODEL
          ;;
  esac
  ```

- Rationale:
  - Gemini backend: uses the actual Gemini model env we already compute (GEMINI_MODEL[_OVERRIDE]).
  - Cursor backend: uses the actual Cursor agent model env we already compute (CURSOR_AGENT_MODEL[_OVERRIDE]).
  - Router/Codex: CLAUDE_CODE_MODEL is already the real Claude model we route to; surface it directly.

2. .claude/claude-statusline/statusline.sh
- Prefer env-provided exact model over transcript heuristics and avoid normalizing to generic labels.
- Proposed minimal additions:

  a) Right before the transcript-based detection block (around lines ~840-846), insert a new env check:

  ```bash
  # Prefer explicit model from launcher if available
  if [[ -z "$model_name" || "$model_name" == "Claude" ]]; then
      if [[ -n "$CLAUDE_STATUSLINE_MODEL" ]]; then
          model_name="$CLAUDE_STATUSLINE_MODEL"
          exact_model=1
      elif [[ -n "$CLAUDE_CODE_MODEL" ]]; then
          model_name="$CLAUDE_CODE_MODEL"
          exact_model=1
      fi
  fi
  ```

  b) Where model_display is derived from model_name (around lines ~851-904), bypass the generic mapping if we have an exact model:

  ```bash
  model_display="$model_name"
  if [[ "${exact_model:-0}" != "1" ]]; then
      case "$model_name" in
          # existing mapping to Opus/Sonnet/Haiku/GPT/Grok/etc.
          # (leave the current case/esac block unchanged)
      esac
  fi
  ```

  - Leave the existing color/context-limit logic as-is; it will still work. If desired later, we can add a small case for "gemini-*" to choose a distinct color, but not required for correctness.

## Verification
- Manual dry run of statusline script:
  - Router path (Claude):
    - Expected: model shows "claude-sonnet-4-6" (or the override passed via --model).
    - Command: `CLAUDE_STATUSLINE_MODEL=claude-sonnet-4-6 bash ~/.claude/claude-statusline/statusline.sh`
  - Gemini path:
    - Expected: model shows "gemini-3.1-pro-preview" (or override).
    - Command: `CLAUDE_STATUSLINE_MODEL=gemini-3.1-pro-preview bash ~/.claude/claude-statusline/statusline.sh`
  - Cursor path:
    - Expected: model shows "gemini-3.1-pro" or chosen override.
    - Command: `CLAUDE_STATUSLINE_MODEL=gemini-3.1-pro bash ~/.claude/claude-statusline/statusline.sh`

- End-to-end:
  - Launch: `.claude/scripts/claude-launch.sh router claude` → statusline should show claude-sonnet-4-6.
  - Launch: `.claude/scripts/claude-launch.sh gemini claude` → statusline should show gemini-3.1-pro-preview (or your override via `--model`).
  - Launch: `.claude/scripts/claude-launch.sh cursor claude` → statusline should show gemini-3.1-pro (or your override).

## Notes
- We intentionally do not alter `--model` passed to the `claude` CLI. The new env var only affects display.
- The transcript-based fallback remains intact if the env variables are absent.
- After implementation, remove the stale session handoff file at plans/session-handoff.md.

## Rollback
- Remove the CLAUDE_STATUSLINE_MODEL export block from the launcher and the two small statusline.sh insertions. Statusline will revert to transcript heuristics showing a generic model name.
