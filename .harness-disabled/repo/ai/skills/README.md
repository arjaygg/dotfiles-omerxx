# `ai/skills/` — skill sources and the customization layer

Every skill lives here as the single source of truth and is symlinked into each consumer
(`.claude/skills/<name>`, and the equivalent for other clients) by `setup.sh`. Retirement and
disablement are tracked in [`REMOVALS.md`](REMOVALS.md).

## Why customization needs a layer

Because skills are symlinked rather than copied, a per-project or personal tweak would
otherwise mean editing the shared source — every consumer inherits the change, and the shared
file drifts from what the repo intends. That failure mode is already visible elsewhere:
`settings-symlink-guard` reports `~/.claude/settings.json` has become a regular file diverging
from its tracked original.

The customization layer keeps the shipped file read-only and puts overrides beside it.

## The three layers

Resolved in order, later layers winning:

| # | Path | Purpose | Commit it? |
|---|---|---|---|
| 1 | `ai/skills/<skill>/customize.toml` | shipped defaults — **DO NOT EDIT** | yes, by the skill author |
| 2 | `.claude/custom/<skill>.toml` | team-wide overrides | yes |
| 3 | `.claude/custom/<skill>.user.toml` | personal overrides | no |

Layers 2 and 3 are optional; a missing layer is skipped, not an error. Every shipped
`customize.toml` carries a DO-NOT-EDIT banner, because it is replaced wholesale on update and
any edit made there is lost.

Resolve the merged result:

```bash
python3 scripts/resolve_customization.py <skill>          # header + merged JSON
python3 scripts/resolve_customization.py <skill> --json   # merged JSON only
```

## Merge rules

Four rules, applied when a later layer meets an earlier one:

| Shape | Behaviour |
|---|---|
| scalars | override |
| tables | deep-merge |
| arrays of tables keyed by `code` or `id` | replace the element with the matching key, append new ones |
| all other arrays | append |

The keyed-array rule is what lets an override change one lens, one step, or one hook without
restating the whole list. Keying requires *every* element in both arrays to carry the same
field (`code` or `id`); otherwise the arrays simply append.

## `file:` values

A string value prefixed `file:` is a path or glob, resolved relative to the layer file's own
directory, whose contents load in its place:

```toml
review_guidance = "file:guidance/house-style.md"
```

**Partial failure is reported, never silent.** If a `file:` value cannot be read, the resolver
names the failed path in its output header and continues — the rest of the configuration still
applies, and the unreadable value is left verbatim so the problem is visible downstream.

## When the resolver is unavailable

Skills must not fall back to "read the base file and use defaults" — that silently discards
every override and produces confidently wrong behaviour. The required fallback is the
**three-file** one: read all three layer paths directly, in order, and apply the four merge
rules by hand, so overrides survive. If a layer is missing, skip it. Say in the output which
layers were applied and which `file:` values failed, exactly as the resolver would.

## Pilot

`lensed-review` is the first skill to ship a `customize.toml`. Its shipped defaults cover
output format, per-lens enablement (keyed by `code`), and the declarative extension points
(`activation_steps_prepend`, `activation_steps_append`, `persistent_facts`).
