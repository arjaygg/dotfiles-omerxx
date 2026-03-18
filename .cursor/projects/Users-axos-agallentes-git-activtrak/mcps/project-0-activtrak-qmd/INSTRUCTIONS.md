QMD is your local search engine over 79 markdown documents.

Collections (scope with `collection` parameter):
  - "activtrak" (24 docs)
  - "team-okrs" (36 docs)
  - "claude-pdf-context" (19 docs)

Search:
  - `search` (~30ms) — keyword and exact phrase matching.
  - `vector_search` (~2s) — meaning-based, finds adjacent concepts even when vocabulary differs.
  - `deep_search` (~10s) — auto-expands the query into variations, searches each by keyword and meaning, reranks for top hits.

Retrieval:
  - `get` — single document by path or docid (#abc123). Supports line offset (`file.md:100`).
  - `multi_get` — batch retrieve by glob (`journals/2025-05*.md`) or comma-separated list.

Tips:
  - File paths in results are relative to their collection.
  - Use `minScore: 0.5` to filter low-confidence results.
  - Results include a `context` field describing the content type.