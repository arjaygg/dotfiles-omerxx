## 2026-07-01 — Use SQLite for fixture cache
**Decision:** Use SQLite for the fixture cache.
**Why:** Simplicity, no extra service dependency.
**Alternatives rejected:** Redis — overkill for single-process cache.
**Assumptions:** Cache stays under 1GB.
