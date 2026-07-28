# lean-ctx — Context Runtime

**Integration mode:** primary file, tree, text-search, and shell-output runtime. LeanCtx is available both as a native MCP server and through pctx.

## Authoritative Routing

- **Serena through pctx:** semantic code navigation, symbols, references, impact analysis, and symbol-aware edits.
- **LeanCtx directly:** focused `ctx_compose`, `ctx_read`, `ctx_search`, `ctx_tree`, and `ctx_expand` operations.
- **pctx `execute_typescript`:** two or more operations, mixed Serena/LeanCtx/Qmd calls, or filtering before results enter context.
- **Native tools:** editing or specialized capabilities Serena/LeanCtx do not provide.
- **Fallback:** if LeanCtx is unavailable, use the client’s native dedicated tool rather than installing a second output compressor.

## Core LeanCtx Tools

- `ctx_compose` / `LeanCtx.ctxCompose` — task-scoped source selection before focused reads.
- `ctx_read` / `LeanCtx.ctxRead` — cached file reads with intent-specific modes.
- `ctx_tree` / `LeanCtx.ctxTree` — compact directory maps.
- `ctx_search` / `LeanCtx.ctxSearch` — text and regex search.
- `ctx_expand` / `LeanCtx.ctxExpand` — lossless expansion of LeanCtx references.

Shell hooks route noisy command output through LeanCtx without adding another direct MCP schema. Use pctx for deferred `ctx_patch`, session, graph, and batch functions.

## Shell and Exact Evidence

Use `ctx_shell` for commands by default. When exact output, quotes, counts, or line-level evidence is required, pass `raw: true` or run:

~~~bash
lean-ctx raw "<exact command>"
~~~

Never wrap a LeanCtx shell call in another output compressor or enable parallel command rewriters.

## Headroom boundary

Headroom receives `HEADROOM_CONTEXT_TOOL=lean-ctx`, `HEADROOM_EXCLUDE_TOOLS` for every direct LeanCtx/pctx tool, and `HEADROOM_DISABLE_KOMPRESS=1`. It runs only as the persistent provider proxy; never register `headroom mcp serve` in a client.

## Fallbacks

If LeanCtx is unavailable, use the client’s native dedicated tool. Do not install or invoke a second output-compression runtime as a fallback.
