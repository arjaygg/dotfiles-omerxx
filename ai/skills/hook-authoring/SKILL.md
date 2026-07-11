---
name: hook-authoring
description: Conventions for writing, editing, or fixing Claude Code hooks (PreToolUse/PostToolUse/SessionStart/SessionEnd shell scripts wired into .claude/settings.json) in this dotfiles repo. Covers the standalone-hook-vs-fold-into-pre-tool-gate-v2.sh decision, the stdin JSON parsing pattern, the deny-JSON schema that actually blocks a tool call, the HARD-BLOCK reason-prefix convention, per-session state file naming, and the critical exec-form-vs-shell-form path portability gotcha. USE THIS SKILL whenever the user asks to add a new hook, debug why a hook isn't firing/blocking, fix a hardcoded path in a hook entry, or edit `.claude/hooks/*.sh` or the `hooks` section of `.claude/settings.json` — even if they don't say the word "hook" explicitly (e.g. "block this tool call", "why didn't my PreToolUse rule fire", "make this path work on another machine").
triggers:
  - write a hook
  - add a PreToolUse hook
  - fix hook path
  - hook not blocking
  - settings.json hooks
  - portable hook path
  - exec-form vs shell-form
---

# Hook Authoring

Reference for editing `.claude/hooks/*.sh` and the `hooks` section of `.claude/settings.json` in this repo. This file is the **global** user settings (symlinked `~/.dotfiles/.claude/settings.json` → `~/.claude/settings.json`) — it runs for every project on the machine, not just this one. Keep that scope in mind for every decision below.

## 1. Standalone hook vs. folding into `pre-tool-gate-v2.sh`

`pre-tool-gate-v2.sh` is the large consolidated `PreToolUse` gate covering cross-cutting security/policy concerns: git safety, PR conventions, plan scope, session-init gating, tool-priority enforcement. Its own header comment already establishes the precedent for *not* folding everything into it — `rtk-rewrite.sh` and the lean-ctx hook redirect both live as separate entries.

Use this rule: a narrow, orthogonal bookkeeping concern (e.g. "track whether X happened once this session") gets its **own standalone hook file** with its own `PreToolUse` entry and a narrow `matcher`. A concern that's genuinely cross-cutting security/policy — the kind of thing that should short-circuit many different tools for the same underlying reason — belongs in the consolidated gate. When unsure, default to standalone: it's easier to fold a proven standalone hook into the gate later than to untangle one concern from an already-large file.

## 2. Reading the hook's stdin payload

Every hook receives one JSON object on stdin. The established pattern in this repo is a single `jq -r` call with `@sh` escaping, so the values are already shell-safe after `eval`:

```bash
INPUT=$(cat)

eval "$(echo "$INPUT" | jq -r '
  @sh "TOOL_NAME=\(.tool_name // "")",
  @sh "FILE_PATH=\(.tool_input.file_path // .tool_input.path // "")",
  @sh "SESSION_ID=\(.session_id // "")"
' 2>/dev/null)" 2>/dev/null || exit 0
```

Fall through (`exit 0`) on any parse failure — a hook that crashes on malformed input is worse than a hook that silently no-ops. Pull whichever fields the hook actually needs; common ones are `tool_name`, `tool_input.file_path`/`tool_input.path`/`tool_input.command`, and `session_id`.

## 3. The deny schema that actually blocks a tool call

A plain `exit 1` from a `PreToolUse` hook does **not** block the tool call — only this exact JSON on stdout (with `exit 0`) does:

```bash
jq -cn --arg r "$REASON" \
  '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
exit 0
```

If the hook has nothing to say, just `exit 0` with no output — don't emit an allow payload, silence is the pass-through.

## 4. The `[HARD-BLOCK — DO NOT RETRY]` prefix

`pre-tool-gate-v2.sh`'s `_deny()` helper prefixes every denial reason with `[HARD-BLOCK — DO NOT RETRY]`. New hooks should match this convention in `$REASON` so the model reading the denial treats it consistently: the block is final for that exact call, retrying (even reworded) will hit the same wall, and the model should switch approaches instead of looping. Follow the prefix with a one-line reason and, where useful, the correct alternative tool/action.

## 5. Per-session state files

For "has X already happened this session" bookkeeping, use a flag/log file keyed on the effective session id and the calling user, not a global path:

```bash
EFFECTIVE_SESSION_ID="${SESSION_ID:-${CLAUDE_SESSION_ID:-default}}"
LOG_FILE="/tmp/.claude-<purpose>-$(id -u)-${EFFECTIVE_SESSION_ID}"
```

`$(id -u)` keeps multiple users on a shared machine from colliding in `/tmp`; falling back through `SESSION_ID` → `CLAUDE_SESSION_ID` → `"default"` keeps the hook functional even if the session id isn't populated in some invocation context. This is the same pattern `pre-tool-gate-v2.sh` uses for its own init-gating and repeat-block tracking — reuse it rather than inventing a new naming scheme per hook.

## 6. Portable paths: exec-form vs. shell-form (read this before touching any hook path)

This is the one that will silently break hook enforcement machine-wide if you get it wrong.

`.claude/settings.json` hook entries come in two shapes:

- **Exec-form** — `{"type":"command","command":"bash","args":["/abs/path/to/script.sh"]}`. This spawns via `execve()` directly, with **no shell parsing of `args`**. Only Claude Code's own built-in tokens (`$CLAUDE_PROJECT_DIR`, `$CLAUDE_PLUGIN_ROOT`) get substituted inline by Claude Code itself before exec. Any other `$VAR` reference (e.g. `$HOME`) is passed through **completely literally** — bash will try to open a file literally named `$HOME/...` and fail. Most hook entries in this repo's `settings.json` use this exec-form, including `pre-tool-gate-v2.sh` itself.
- **Shell-form** — a single `"command"` string, e.g. `"bash -lc '$HOME/.dotfiles/.claude/hooks/foo.sh'"`. This goes through a real shell, so `$HOME` and other env vars expand normally. The lean-ctx hook redirect entry already uses this form.

**Why `$CLAUDE_PROJECT_DIR` is the wrong fix here specifically:** it resolves to whatever project is currently open, which is correct for a hook that ships *inside* a project. But this repo's `.claude/settings.json` is the **global** user settings file, symlinked into `~/.claude/settings.json` and applied across every project on the machine — a hook script living in `~/.dotfiles/.claude/hooks/` needs to resolve to that fixed location regardless of which project triggered it. `$CLAUDE_PROJECT_DIR` would point at the wrong repo entirely as soon as you're working anywhere else.

**The correct portable form:** `$HOME/.dotfiles/...`, matching `setup.sh`'s own hardcoded `~/.dotfiles` clone-location convention, applied via **shell-form**, not by editing the `args` array of an exec-form entry in place. Editing `args: ["$HOME/..."]` under exec-form looks like a fix and is not — it will pass the literal string through unexpanded.

### Converting an existing exec-form entry safely

1. Convert one entry at a time from `{"command":"bash","args":["/abs/path"]}` to `{"command":"bash -lc '$HOME/.dotfiles/relative/path/to/script.sh'"}` (or the equivalent single-string shell-form for that hook's matcher).
2. Trigger the guarded tool call in a live session and confirm the hook still fires with the expected deny/allow behavior — don't assume `exit 0` on the settings load means the entry works.
3. Only move to the next entry once the converted one is confirmed live. A bad conversion silently disables that hook's enforcement with no error at settings-load time — there's no linting step that catches a broken exec→shell conversion, so live verification is the only real check.

## 7. Quick checklist for a new hook

- [ ] Decide standalone file vs. fold into `pre-tool-gate-v2.sh` (§1)
- [ ] Narrow `matcher` in the `PreToolUse`/`PostToolUse` entry — don't match more tools than the hook actually cares about
- [ ] Parse stdin with the `jq -r`/`@sh`/`eval` pattern (§2), fall through safely on parse failure
- [ ] Use the exact deny JSON schema (§3) with `exit 0`, `[HARD-BLOCK — DO NOT RETRY]` prefix (§4)
- [ ] If tracking session state, use the `EFFECTIVE_SESSION_ID` + `/tmp/.claude-<purpose>-$(id -u)-${id}` pattern (§5)
- [ ] Use `$HOME/.dotfiles/...` shell-form for any path reference in this repo's global `settings.json`, never a bare exec-form `args` path with an env var in it (§6)
- [ ] Live-test the actual tool call the hook guards, not just that `settings.json` parses as valid JSON
