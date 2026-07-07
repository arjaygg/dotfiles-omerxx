# pctx Functions — 2026-07-07 (DRIFT DETECTED vs 2026-06-12 snapshot)

Namespaces: Serena, Qmd, LeanCtx, Repomix, **Graphify (new)**

## Serena (unchanged)
listDir, findFile, searchForPattern, getSymbolsOverview, findSymbol, findReferencingSymbols,
replaceSymbolBody, insertAfterSymbol, insertBeforeSymbol, renameSymbol,
writeMemory, readMemory, listMemories, deleteMemory, renameMemory, editMemory,
checkOnboardingPerformed, onboarding, initialInstructions

## Qmd — CHANGED
Now: query, get, multiGet, status
Was: search, vectorSearch, deepSearch, get, multiGet, status
`query` replaces search/vectorSearch/deepSearch with a single typed sub-query document (lex/vec/hyde).
**Action needed:** `ai/rules/tool-priority.md` §10 still references `Qmd.deepSearch`/`Qmd.search` — stale, should be updated to `Qmd.query` with typed sub-queries.

## LeanCtx — CHANGED
Now: ctxCall, ctxEdit, ctxGraph, ctxKnowledge, ctxOverview, ctxProvider, ctxRead, ctxSearch, ctxSession, ctxShell, ctxTree
Was: ctxRead, ctxMultiRead, ctxTree, ctxShell, ctxSearch, ctxCompress, ctxBenchmark, ctxMetrics, ctxAnalyze,
ctxCache, ctxDiscover, ctxSmartRead, ctxDelta, ctxDedup, ctxFill, ctxIntent, ctxResponse, ctxContext,
ctxGraph, ctxSession, ctxKnowledge, ctxAgent, ctxOverview, ctxWrapped
Consolidated to 11 core functions; most former standalone tools (ctxIntent, ctxSmartRead, ctxMultiRead,
ctxCompress, etc.) now appear to be reachable only via `ctxCall(name, args)` dispatch, not as top-level fns.
**Action needed:** session-init hook step 5 calls `LeanCtx.ctxCall({ name: "ctx_intent", ... })` — this
matches the new dispatch shape, but `ai/rules/tool-priority.md` §10 references `LeanCtx.ctxSmartRead` /
`ctxMultiRead` as direct calls — stale, should route through `ctxCall`.

## Repomix (unchanged)
packCodebase, packRemoteRepository, generateSkill, attachPackedOutput,
readRepomixOutput, grepRepomixOutput, fileSystemReadFile, fileSystemReadDirectory

## Graphify (new namespace, not documented anywhere in ai/rules/)
queryGraph, getNode, getNeighbors, getCommunity, godNodes, graphStats, shortestPath,
listPrs, getPrImpact, triagePrs
PR-graph-impact tooling (listPrs/getPrImpact/triagePrs) is directly relevant to the
"Git Workflow & PR Management" and CI/CD areas — currently undocumented in tool-priority.md.
