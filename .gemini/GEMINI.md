# Gemini User Instructions

This file is the user-global Gemini entrypoint for this machine.

@../ai/rules/agent-user-global.md

## Gemini-Specific Notes

- Project-specific guidance should come from each repository via `AGENTS.md` and related project docs.
- Gemini configuration is split across `~/.gemini/mcp.json` and `~/.gemini/settings.json`; both must stay aligned.
- Keep durable policy out of the "Gemini Added Memories" section below.

---

## Gemini Added Memories
- basictex is installed
- The files ghostty/config, hammerspoon/init.lua, nvim/after/queries/go/injections.scm, nvim/after/queries/go/locals.scm, nvim/lua/lsp_autocommands.lua, nvim/lua/plugins/lsp.lua, nvim/lua/plugins/syntax.lua, nvim/lua/plugins/telescope.lua, ssh/rc, and tmux/tmux.conf were restored from the upstream (caarlos0/dotfiles) repository, not the user's fork origin.
