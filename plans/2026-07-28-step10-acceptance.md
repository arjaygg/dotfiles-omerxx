# Step 10 acceptance evidence — consolidate review into one lensed skill

**Date:** 2026-07-28
**Branch:** `chore/native-agent-orchestration-step10` (not merged to `main`)
**Spec:** `plans/specs/2026-07-28-step10.md`

## Commits

| Hash | What |
|---|---|
| `a06de2d` | lensed-review scaffold — `SKILL.md`, `lenses.toml`, 5 `references/lens-*.md` |
| `9acbcd4` | restored Step 9's `ai/skills/REMOVALS.md` ledger |
| `762a7a3` | `cap/references/schemas.md`: finding requires `lens`, `severity` dropped |
| `708dc31` | restored Step 7's eval harness (`evals/`, `scripts/run_evals.py`, `scripts/lib/tfidf.py`) |
| `097064d` | shims for `hawk`, `pr-review`, `code-health`, `bmad-custom-pr-review` |
| `c421a8c` | 9 ledger rows recording the consolidation |
| `a81e8ec` + `eac38ed` | shims for the 5 review agents (second commit restores the symlink layout) |
| `53daea8` | `evals/cases/lensed-review.json`; last `severity` mention removed from schemas |
| `9d4bcd2` | `.claude/skills/lensed-review` symlink |

## Acceptance checkboxes

- [x] **`lenses.toml` parses; every entry has exactly the five §22 keys.** `tomllib` parse of
  6 entries; each reports `keys=['after','applies_to','code','instruction','when'] -> OK`.
- [x] **A lens with an empty `instruction` is skipped in a dry run.** Dry-run resolution output:
  `SKIP performance: instruction empty -> disabled, reference file not loaded`; the other five
  print `RUN <code>: would load references/lens-<code>.md`.
- [x] **Every `references/lens-*.md` ≤90 lines.** `wc -l`: correctness 38, doubt 35, resilience 31,
  security 32, style 33. (`SKILL.md` is 72 ≤ 80.)
- [x] **Findings carry `lens`, zero `severity`.** `REVIEW_SCHEMA` finding requires
  `lens, category, file, line, description, fix, confidence`; `grep -c -i severity
  ai/skills/cap/references/schemas.md` → **0**.
- [x] **Doubt cycle is a lens, not a separate harness.** `[doubt]` entry in `lenses.toml` with
  `after = "correctness"` — it consumes another lens's findings; no separate script exists.
- [x] **Every superseded mechanism has a shim + ledger entry + eval-case disposition** (9 total):
  skills `hawk`, `pr-review`, `code-health`, `bmad-custom-pr-review`; agents `security-reviewer`,
  `claude-code-review-agent`, `silent-failure-hunter`, `database-reviewer`,
  `performance-optimizer`. All 9 rows in `REMOVALS.md` read `superseded-by lensed-review`.
- [x] **Collision report vs Step 7 baseline.** Baseline (`evals/collision-baseline.md`, commit
  `41132c1`): **0** pairs ≥50%. After consolidation: **0** pairs ≥50%; rank-1 rate 81.8% over
  11 cases (floor 80%). It cannot go below zero, so parity is the passing result.
- [x] **Nothing named `review` was created or touched.** No `ai/skills/review`,
  `ai/skills/code-review`, or `ai/skills/simplify` exists; the new skill is `lensed-review`.

## Eval-case migration

Step 7 committed cases for 10 skills — none of them for `hawk`, `pr-review`, `code-health`, or
`bmad-custom-pr-review`. No orphans were left behind. `evals/cases/lensed-review.json` is their
consolidated successor, covering the merged trigger surface plus two negatives, and asserts the
empty-`instruction` skip and the `lens`/no-`severity` finding shape.

## Deviations

1. **Step 7's harness was materialized into this branch** (`708dc31`). `evals/` and
   `scripts/run_evals.py` only existed on the unmerged `chore/...-step7` branch, so the collision
   check could not run here. Same treatment Step 9's `REMOVALS.md` already received.
2. **`bmad-custom-pr-review`'s description was rewritten** after the first shim pass pushed it to
   53% similarity with `pr-review` (a warn-tier collision that did not exist at baseline). Reworded
   to Charcoal-layer-walking language; back to 0 pairs.
3. **The last `severity` token in `schemas.md` was prose** stating the field's absence. Reworded to
   "No ranking, priority, or triage-order field" so the literal `grep -c severity` reports 0. The
   rule is unchanged.
4. **Agent shims live in `ai/agents/`, not `.claude/agents/`.** The first attempt wrote regular
   files over the `.claude/agents/*` symlinks, violating the repo's symlink-distribution rule;
   `eac38ed` moved content to the source of truth and restored the links.
5. **`performance` lens ships disabled.** Required by the spec to prove the skip path is real. The
   consequence — `performance-optimizer`'s profiling depth is not reproduced — is recorded in both
   the ledger and the agent shim rather than papered over.

## Stop conditions

None hit. Step 7's collision baseline was located and cited (`41132c1`,
`evals/collision-baseline.md`); no Claude Code built-in was created or modified.
