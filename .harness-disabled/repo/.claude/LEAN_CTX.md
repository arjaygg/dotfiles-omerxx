# lean-ctx — Context Runtime

**Integration mode:** primary file, tree, text-search, and shell-output runtime. LeanCtx is registered as a direct MCP server in every client.

## Authoritative Routing

- **Serena:** semantic code navigation, symbols, references, impact analysis, and symbol-aware edits.
- **LeanCtx:** focused `ctx_compose`, `ctx_read`, `ctx_search`, `ctx_tree`, and `ctx_expand` operations.
- **Two or more independent operations:** issue them as parallel tool calls in a single message.
- **Native tools:** editing or specialized capabilities Serena/LeanCtx do not provide.
- **Fallback:** if LeanCtx is unavailable, use the client’s native dedicated tool rather than installing a second output compressor.

## Core LeanCtx Tools

- `ctx_compose` — task-scoped source selection before focused reads.
- `ctx_read` — cached file reads with intent-specific modes.
- `ctx_tree` — compact directory maps.
- `ctx_search` — text and regex search.
- `ctx_expand` — lossless expansion of LeanCtx references.

Shell hooks route noisy command output through LeanCtx without adding another direct MCP schema. `ctx_patch`, session, and graph functions are reached through the same direct server.

## Shell and Exact Evidence

Use `ctx_shell` for commands by default. When exact output, quotes, counts, or line-level evidence is required, pass `raw: true` or run:

~~~bash
lean-ctx raw "<exact command>"
~~~

Never wrap a LeanCtx shell call in another output compressor or enable parallel command rewriters.

## Headroom boundary

Headroom receives `HEADROOM_CONTEXT_TOOL=lean-ctx`, `HEADROOM_EXCLUDE_TOOLS` for every direct LeanCtx tool, and `HEADROOM_DISABLE_KOMPRESS=1`. It runs only as the persistent provider proxy; never register `headroom mcp serve` in a client.

## Fallbacks

If LeanCtx is unavailable, use the client’s native dedicated tool. Do not install or invoke a second output-compression runtime as a fallback.
