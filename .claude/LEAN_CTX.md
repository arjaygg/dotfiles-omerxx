# lean-ctx — Context Runtime

**Integration mode:** primary file, tree, text-search, and shell-output runtime. LeanCtx is available both as a native MCP server and through pctx.

## Authoritative Routing

- **Serena through pctx:** semantic code navigation, symbols, references, impact analysis, and symbol-aware edits.
- **LeanCtx directly:** one file/tree/text/shell operation when no output filtering is needed.
- **pctx `execute_typescript`:** two or more operations, mixed Serena/LeanCtx/Qmd calls, or filtering before results enter context.
- **Native tools:** editing or specialized capabilities Serena/LeanCtx do not provide.
- **Fallback:** if LeanCtx is unavailable, use the client’s native dedicated tool rather than installing a second output compressor.

## Core LeanCtx Tools

- `ctx_read` / `LeanCtx.ctxRead` — cached file reads with intent-specific modes.
- `ctx_tree` / `LeanCtx.ctxTree` — compact directory maps.
- `ctx_search` / `LeanCtx.ctxSearch` — text and regex search.
- `ctx_shell` / `LeanCtx.ctxShell` — compressed command, build, test, and log output.
- `ctx_patch` / `LeanCtx.ctxPatch` — hash-anchored text edits.
- `ctx_session` / `LeanCtx.ctxSession` — cross-session context state.

## Shell and Exact Evidence

Use `ctx_shell` for commands by default. When exact output, quotes, counts, or line-level evidence is required, pass `raw: true` or run:

~~~bash
lean-ctx raw "<exact command>"
~~~

Never wrap a LeanCtx shell call in another output compressor or enable parallel command rewriters.

## Agent Setup

~~~bash
export HEADROOM_CONTEXT_TOOL=lean-ctx
lean-ctx init --agent claude
lean-ctx init --agent codex
~~~

Headroom must receive `HEADROOM_CONTEXT_TOOL=lean-ctx` so its compatibility path cannot select or install another context tool. Persist the selector in each launcher or agent environment, not only an interactive shell.

## Fallbacks

If LeanCtx is unavailable, use the client’s native dedicated tool. Do not install or invoke a second output-compression runtime as a fallback.
