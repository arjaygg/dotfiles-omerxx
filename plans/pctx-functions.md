# pctx Functions — 2026-07-10 (refreshed; no drift vs 2026-07-08 snapshot)

Namespaces: Serena, Qmd, LeanCtx, Repomix, Graphify

Refresh method (M11, constitution-hooks audit): full function list re-confirmed via
`mcp__pctx__list_functions`; every parameter shape quoted below was confirmed this session via
`mcp__pctx__get_function_details` against the live SDK — not copied from the prior snapshot or from
`ai/rules/tool-priority.md`.

## Serena (unchanged)
listDir, findFile, searchForPattern, getSymbolsOverview, findSymbol, findReferencingSymbols,
replaceSymbolBody, insertAfterSymbol, insertBeforeSymbol, renameSymbol,
writeMemory, readMemory, listMemories, deleteMemory, renameMemory, editMemory,
checkOnboardingPerformed, onboarding, initialInstructions

Spot-checked full signatures for `findSymbol` and `searchForPattern` via `get_function_details` —
match documented usage in `ai/rules/tool-priority.md` §1/§6/§9. No drift.

## Qmd — CHANGED (confirmed live); one field-name bug found in the rules doc
Now: `query`, `get`, `multiGet`, `status`. `search`/`vectorSearch`/`deepSearch` are gone — confirmed
absent from the live function list, fully consolidated into `query`.

Real `QueryInput` shape (confirmed via `get_function_details`, not inferred):
```ts
Qmd.query({
  searches: [{ type: "lex" | "vec" | "hyde", query: string }],  // required
  limit?: number,          // default 10
  minScore?: number,       // default 0
  candidateLimit?: number, // default 40
  collections?: string[],
  intent?: string,         // disambiguation context only, does not search on its own
  rerank?: boolean,        // default true
})
```

**Bug found (feeds M1):** `ai/rules/tool-priority.md` §10 documents this call as
`Qmd.query({ subqueries: [{type: "lex"|"vec"|"hyde", text}] })`. Both names are wrong against the
live schema — the array field is `searches` (not `subqueries`) and each entry's text key is `query`
(not `text`). A parallel PR (branch `fix/tool-priority-qmd-query-fields`) is correcting this in
`tool-priority.md`; the shape above is the live ground truth to copy from once that lands.

**Action needed:** none for this file — the shape above is accurate as of this session. The
previously-flagged "`tool-priority.md` §10 still references `Qmd.deepSearch`/`Qmd.search`" callout is
now stale/resolved: those names are gone from `tool-priority.md` §10, which already calls `Qmd.query`
exclusively. Only the `searches`/`query` field-name bug above remains open, tracked under M1.

## LeanCtx — CHANGED (confirmed live); prior action item resolved, one new bug found
Now: `ctxCall`, `ctxEdit`, `ctxGraph`, `ctxKnowledge`, `ctxOverview`, `ctxProvider`, `ctxRead`,
`ctxSearch`, `ctxSession`, `ctxShell`, `ctxTree` — 11 core functions, count and names unchanged from
the 2026-07-07 snapshot (re-confirmed via `list_functions`).

Parameter shapes confirmed via `get_function_details` this session:
- `ctxCall({ name: string, arguments?: object })` — dispatch for the 50+ non-core tools (e.g.
  `ctx_intent`, `ctx_smart_read`, `ctx_multi_read`, `ctx_architecture`, `ctx_impact`, `ctx_callgraph`,
  `ctx_refactor`, `ctx_symbol`, `ctx_routes`, `ctx_smells`, `ctx_index`, ...). **The payload field is
  `arguments`, not `args`.**
- `ctxRead({ path, mode?, fresh?, start_line? })` — modes: full\|map\|signatures\|diff\|aggressive\|entropy\|task\|ref\|lines:N-M.
- `ctxSearch({ pattern, path?, ext?, max_results?, ignore_gitignore? })`.
- `ctxShell({ command, cwd?, env?, raw? })`.
- `ctxTree({ path?, depth?, show_hidden? })`.
- `ctxSession({ action, session_id?, value? })` — actions: status\|load\|save\|task\|finding\|decision\|reset\|list\|cleanup\|snapshot\|restore\|resume\|profile\|role\|budget\|slo\|diff\|verify\|episodes\|procedures.
- `ctxGraph({ action, path?, project_root?, depth?, kind? })` — actions: build\|related\|symbol\|impact\|status\|enrich\|context\|diagram.
- `ctxKnowledge({ action, key?, value?, query?, mode?, category?, confidence?, ... })` — large action
  set (policy, remember, recall, pattern, feedback, relate, unrelate, relations, consolidate, status,
  health, remove, export, timeline, rooms, search, wakeup, embeddings_*).
- `ctxOverview({ path?, task? })`.
- `ctxProvider({ action, provider?, resource?, mode?, state?, status?, labels?, iid?, limit? })` —
  GitHub/GitLab/MCP-bridge resource access.
- `ctxEdit({ path, new_string, old_string?, create?, replace_all? })`.

**Prior action item — resolved:** the 2026-07-07 callout ("session-init hook's
`ctxCall({name: "ctx_intent", ...})` matches the dispatch shape, but `tool-priority.md` §10 still
references `ctxSmartRead`/`ctxMultiRead` as direct top-level calls") is itself stale. Reading the live
rule file this session shows §10's "File Reading" table already routes both through
`ctxCall({name: "ctx_multi_read"|"ctx_smart_read", ...})` — no remaining direct top-level call
references.

**New bug found (not yet tracked anywhere):** `ai/rules/tool-priority.md` §10 "File Reading" table and
its prose both write the `ctxCall` dispatch payload as `LeanCtx.ctxCall({name: "...", args: {...}})`.
Per the live `CtxCallInput` schema confirmed above, the field is `arguments`, not `args` — `args` is
silently the wrong key. This is a real, current bug (found by comparing the doc to the live schema
this session), separate from the M1 `Qmd.query` finding above. Not fixed here — out of scope for this
file and `tool-priority.md` has a concurrent PR in flight touching the same section; flagging for a
follow-up fix.

## Repomix (unchanged)
packCodebase, packRemoteRepository, generateSkill, attachPackedOutput,
readRepomixOutput, grepRepomixOutput, fileSystemReadFile, fileSystemReadDirectory

## Graphify (documented — no longer "new/undocumented")
queryGraph, getNode, getNeighbors, getCommunity, godNodes, graphStats, shortestPath,
listPrs, getPrImpact, triagePrs

Spot-checked `listPrs({ base?, repo? })` and `getPrImpact({ pr_number, repo? })` via
`get_function_details` — signatures match the 2026-07-07 snapshot, no drift.

**Action needed:** none — `ai/rules/tool-priority.md` §10 now has a full "PR / Git Graph Tooling"
section documenting this namespace (listPrs/getPrImpact/triagePrs/queryGraph/getNeighbors/
godNodes/graphStats/shortestPath). The 2026-07-07 snapshot's "not documented anywhere" callout is
stale/resolved.

---
Next refresh due: 2026-07-09 (24h TTL per `ai/rules/tool-priority.md` §7).
