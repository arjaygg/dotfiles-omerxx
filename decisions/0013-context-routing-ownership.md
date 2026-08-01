# 0013 — LeanCtx owns content compression; Headroom owns provider history

**Status:** Accepted — §2 partially superseded by `0015-headroom-per-session-wrapper.md` for Codex (2026-08-01)  
**Date:** 2026-07-29

## Context

LeanCtx and Headroom both transformed tool results. Headroom 0.27.0 stored recursive `<<ccr:...>>` references, six per-session MCP containers accumulated, and client guidance disagreed about whether large files should be focused or read completely in chunks.

## Decision

1. LeanCtx exclusively owns file, search, and shell-output compression.
2. Headroom runs as one persistent provider proxy. LeanCtx/pctx tool names are listed in `HEADROOM_EXCLUDE_TOOLS`; Kompress is disabled until deliberately benchmarked.
3. `ai/context/context-routing.json` and `ai/context/context_gate.py` define one warn-to-block classifier used by thin Claude, Codex, Cursor, and AGY/Antigravity hook adapters.
4. Large files use `ctx_compose → task/reference/lines → full/raw/anchored only for exactness`.
5. Metrics record classifications, timing, and hashed paths under the XDG state directory; contents, prompts, outputs, commands, secrets, and absolute paths are forbidden.

## Consequences

- Medium reads remain warnings. Large reads warn during the seven-day rollout and block only after promotion evidence; huge/generated native full reads block immediately.
- A machine-local override may demote a denial to warning but cannot disable telemetry.
- Normal clients must not register `headroom mcp serve`; setup audits recursive CCR rows and removes the Codex Headroom MCP block while preserving the provider proxy.
- LeanCtx 3.9.12 Markdown task/reference behavior remains benchmarked as an upstream constraint. The portable LeanCtx launcher removes the version's extra CLI newline for explicit `raw`/`full` reads, and reproducible fixtures stay until a verified release meets the focused-retrieval targets.
