# Environment gotchas

This analysis touches ~1 GB of JSONL and needs long-running shell pipelines, which is
exactly the combination that trips the guardrails on this machine. Every failure below is
deterministic, so recognise it and switch rather than retrying.

## Shell command routing

`ctx_shell` enforces an allowlist. Ordinary analysis commands get blocked by it —
observed: `du`, `[`, and anything where `xargs` delegates to `sh`. The block message is
final; a reworded retry hits the same wall.

| Need | Use |
|---|---|
| Multi-line script, loops, conditionals, any pipeline of substance | `ctx_execute(language="shell")` — the sanctioned path, no allowlist |
| A single long-running command that needs more than 30 s | `ctx_shell(command=..., timeout_ms=...)` |
| Anything else | `ctx_execute` |

**The timeout split is the important part:** `ctx_execute` caps at **30 seconds** and will
kill the sweep mid-flight. `ctx_shell` accepts `timeout_ms` up to an hour but is
allowlist-gated. So:

- Run `collect-cost-data.sh` through **`ctx_shell` with `timeout_ms: 600000`**. It is a
  single `bash <script>` invocation, so the allowlist is satisfied, and it gets the runway
  it needs.
- Use `ctx_execute` for the small ad-hoc `jq` queries against `summary.json` afterwards.

If the sweep still times out, the fix is to narrow the file set (fewer projects, or a
shorter window), not to raise the timeout again.

## Performance

Spawning one `jq` per transcript file takes minutes and often blows the timeout; passing
the whole file list to a single `jq` takes seconds. The collector does the latter via
`xargs jq ... < filelist`. Preserve that shape if you modify it.

## Writing files

Two blocks apply to output:

1. **Overwriting an existing file is hook-blocked** unless native `Read` ran on it first —
   and native `Read` is denied by policy here, so an overwrite cannot be unblocked.
   Consequence: **get the numbers right before writing the report.** Verify every derived
   figure against `summary.json` first. If a rewrite becomes unavoidable, write to a new
   filename rather than fighting the hook, then delete the superseded draft.
2. **Artifact publishing may be disabled** (it reads file contents). When it is, the
   dashboard stays a local HTML file — write it into the output directory and `open` it.
   Do not treat this as a failure; a local file is a perfectly good deliverable.

## Editing the skill itself

The dotfiles repo blocks edits on `main` — a hook demands a stacked branch. Use the
`stack-create` skill (`stack create feature/<name> main`) and edit under
`.trees/<name>/`. The `stack` script must be invoked with the repo as the working
directory, so pass `cwd` rather than prefixing a `cd`.

## `ccusage` specifics

- `ccusage claude <cmd>` scopes to Claude Code; bare `ccusage <cmd>` includes every agent
  it detects (Codex, Gemini, …). Always be explicit, and confirm the intended scope with
  the user when more than one agent shows up.
- `--since` / `--until` want compact `YYYYMMDD`.
- `ccusage session --since ...` (without the `claude` scope) has returned zero sessions in
  practice; `ccusage claude session` populates `projectPath` and `sessionId` correctly.
  Prefer the scoped form for anything session- or project-level.
- The `period` field carries the date/month label. Some versions leave `month` null on the
  `monthly` command, so read `period`.

## Raw transcript caveats

- Transcripts under `subagents/` are subagent runs; the parent session lives one level up.
  Split on the path to get the main-vs-subagent breakdown.
- Filtering files by mtime `>= window start` is sound — appending updates mtime, so a file
  untouched since before the window cannot hold records inside it. Still filter individual
  records by `.timestamp`, because a file touched during the window may also hold older
  records.
- Raw counts run roughly **2× ccusage's deduplicated totals** because resumed and forked
  sessions replay history. Never source a dollar figure from raw counts. Ratios are fine —
  uniform duplication cancels.
- A session with no assistant turns yields no `usage` records at all. Guard against empty
  results rather than assuming every transcript contributes.
