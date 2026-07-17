---
name: chrome-mcp-efficiency
description: Minimal-token Chrome MCP browser automation patterns — text extraction over screenshots, filtered console/network reads, tool-discovery batching, tab hygiene. Use when writing or reviewing Chrome MCP tool calls.
version: 1.0.0
disable-model-invocation: true
triggers:
  - chrome-mcp-efficiency
  - efficient chrome mcp
  - minimize chrome mcp output
---

# Skill: chrome-mcp-efficiency

These rules apply whenever an agent primitive (skill, command, rule) writes or recommends
`mcp__claude-in-chrome__*` tool calls. The goal is to avoid context bloat from browser automation —
DOM dumps, screenshots, and console/network logs can each consume tens of thousands of tokens if
pulled indiscriminately.

## Decision Tree

Before calling a Chrome tool, choose the least-verbose path:

```
Need page content/text?     → get_page_text or read_page (never computer screenshot for this)
Need to verify a UI state?  → computer (screenshot) only when text extraction can't answer it
Need an element to click?   → find (selector/description) over a full read_page dump
Need console output?        → read_console_messages with a `pattern` filter, not unfiltered
Need network activity?      → read_network_requests scoped to the relevant request, not all traffic
Multi-step task?            → plan steps first; avoid re-reading full page state after each click
```

## Required Patterns

**Prefer text extraction over screenshots:**
```
# Good — structured, minimal tokens
get_page_text(tab_id)
read_page(tab_id, selector: ".results")

# Bad — screenshot for something text extraction already answers
computer(action: "screenshot")
```

**Filter console/network reads:**
```
# Good — pattern-scoped
read_console_messages(pattern: "\\[MyApp\\]")
read_network_requests(url_pattern: "/api/checkout")

# Bad — unfiltered full log dump
read_console_messages()
```

**Batch tool discovery:** load every Chrome tool you expect to need in one `ToolSearch` call
(see MCP server instructions) rather than one call per tool.

**Checkpoint multi-step workflows:** for tasks spanning several navigations/clicks, state the plan
once, then act — don't re-fetch full page state after every micro-action if the prior read
already confirmed the needed element exists.

**Tab hygiene:** close tabs opened for a sub-task once it's done (`tabs_close_mcp`) rather than
letting them accumulate across a long session.

## Forbidden Anti-Patterns

- `computer(action: "screenshot")` as the default way to read page content — use `get_page_text`/`read_page` first
- Unfiltered `read_console_messages()` / `read_network_requests()` on a noisy page
- Re-reading full page state after every single click/keystroke in a multi-step flow
- Leaving many tabs open across a long session "just in case"
- Loading Chrome MCP tools one `ToolSearch` call at a time instead of batching

## Allowed Exceptions

- A screenshot is warranted when visual layout/rendering itself is the thing being verified (not text content)
- Full unfiltered log reads are fine for short, one-off debugging sessions on a page with little log volume
- Keeping a tab open is fine when the user is actively going back to it later in the same session

## Reference

Precedent research: Chrome MCP context-efficiency best practices (deep-research pass, 2026-07).
See also `ai/rules/tool-priority.md` §0/§1 for the general dedicated-tool-over-shell priority this mirrors.
Enforcement backstop: `.claude/hooks/chrome-mcp-guard.sh` (PreToolUse hook on `mcp__claude-in-chrome__.*`).
