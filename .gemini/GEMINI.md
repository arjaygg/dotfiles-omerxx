# Gemini User Instructions

This file is the user-global Gemini entrypoint for this machine.

@../ai/rules/agent-user-global.md
@../ai/rules/tool-priority.md
@../ai/rules/context-and-compaction.md

## Gemini-Specific Notes

- Project-specific guidance should come from each repository via `AGENTS.md` and related project docs.
- Gemini configuration is split across `~/.gemini/mcp.json` and `~/.gemini/settings.json`; both must stay aligned.
- Keep durable policy out of the "Gemini Added Memories" section below.

---

## Gemini Added Memories
- basictex is installed
- The files ghostty/config, hammerspoon/init.lua, nvim/after/queries/go/injections.scm, nvim/after/queries/go/locals.scm, nvim/lua/lsp_autocommands.lua, nvim/lua/plugins/lsp.lua, nvim/lua/plugins/syntax.lua, nvim/lua/plugins/telescope.lua, ssh/rc, and tmux/tmux.conf were restored from the upstream (caarlos0/dotfiles) repository, not the user's fork origin.

<!-- lean-ctx-rules -->
<!-- version: 8 -->

lean-ctx shadow mode: native file/search/shell calls auto-route to ctx_* — no tool-mapping needed.
Exclusive tools (no native trigger): ctx_compose (understand code, call first), ctx_search(action=symbol) (exact symbol), ctx_search(action=semantic) (by meaning), ctx_callgraph (callers), ctx_knowledge / ctx_session (memory).
<!-- lean-ctx-compression -->
OUTPUT STYLE: concise
- Bullet points over paragraphs
- Skip filler words and hedging ("I think", "probably", "it seems")
- 1-sentence explanations max, then code/action
- No repeating what the user said
<!-- /lean-ctx-compression -->
<!-- /lean-ctx-rules -->
