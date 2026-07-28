# Context & Compaction (User-Scope)

## Context ownership

- **LeanCtx exclusively owns file, search, and shell-output compression.**
- **Headroom owns provider-history optimization only.** It must pass LeanCtx and pctx tool results through unchanged and must never store nested or self-referential CCR content.
- Recover a local provider-history CCR with `python3 "$HOME/.dotfiles/scripts/headroom_hardening.py" recover-ccr "$HOME/.headroom/ccr_store.db" <hash>`; invalid or recursive entries are refused.
- Use pctx for batched/deferred SDK calls; expose only LeanCtx's focused compose/read/search/tree/expand tools directly.

## Progressive file disclosure

Route reads as `ctx_compose → task/reference/lines → full/raw only when necessary`.

| Class | Threshold | Route |
|---|---|---|
| Small | ≤16 KB and ≤200 lines | Full read allowed |
| Medium | >16 KB or >200 lines | Warn; use `task`, `reference`, or selected lines |
| Large | >128 KB or >1,500 lines | `ctx_compose`, then focused `ctx_read`; warn during rollout and block after promotion |
| Huge/generated | >512 KB, lockfile, generated artifact, or log dump | Deny native full reads; targeted search/read only |

- `ctx_read(mode="task")` for understanding, `reference` for quotations, and `lines:N-M` for bounded inspection.
- `full`, `raw`, or `anchored` are exactness escape hatches for governing policy, acceptance criteria, verification, and editing.
- Markdown retrieval must retain heading ancestry, front matter, tables, lists, cross-section qualifications, and complete fenced code blocks; do not use Markdown `map` or `signatures` until their zero-token benchmark defect is fixed.
- Code: Serena symbols first, focused LeanCtx reads second. JSON/YAML/TOML: key paths or structural reads. Logs: errors plus bounded context. CSV: schema, samples, aggregates. Lockfiles/generated files: targeted search only. Binary documents: ingestion skills.
- Post-compression output over 4,000 tokens must return an expandable reference. Cached rereads should return `reference`/cache stubs (≤32 tokens), not retransmit content.

## Session discipline

- Keep current task and decisions in `plans/`; chat history is ephemeral.
- Prefer concrete request scope, one task per session, and no more than 1–2 compactions before checkpointing and starting fresh.
- Do not reread imported instruction files after compaction; clients reload them automatically.
- Treat scratchpads as write-mostly and prefer file-path references to pasted screenshots.
- `LeanCtx.ctxSession(action: "status"/"load"/"finding")` is the continuity layer; no global shell bootstrap is required.

The executable thresholds and rollout contract live in `ai/context/context-routing.json`; client hooks call the standard-library gate in `ai/context/context_gate.py`.
