# Cap Step 1 — Parse Arguments & Select Runtime

If a step says read fully and follow step-XX, you read and follow step-XX. No exceptions.

## Parse Arguments

From `$ARGUMENTS`, extract:

| Parameter | How to extract | Default |
|---|---|---|
| `feature` | Everything after stripping flags (--mode, --autonomous, --resume) | required |
| `mode` | `--mode <value>` | `feature` |
| `autonomous` | Presence of `--autonomous` flag | `false` |
| `resumeRunId` | `--resume <wf_xxx_id>` | none |

If `feature` is empty: ask the user for the feature description before proceeding.

## Select Runtime

Choose exactly one runtime before doing implementation work:

1. **Workflow runtime:** use only when the current agent exposes a callable `Workflow` tool or
   primitive in its available tool list.
2. **Portable runtime:** use when `Workflow` is absent, unknown, unsupported, or unavailable.

Do **not** probe by calling `Workflow` speculatively. If the tool is not clearly available,
assume the portable runtime.

Claude Code usually supports the Workflow runtime. Codex, Gemini, Cursor, and generic skill
hosts should be treated as portable unless their tool list explicitly includes Workflow.

## Common Rationalizations

| Excuse | Rebuttal |
|---|---|
| "I'll just call Workflow to see if it's there" | Probing by calling `Workflow` speculatively can trigger a real run/side effect — check the tool list instead of invoking it. |
| "The feature description is thin, I'll assume the obvious scope" | An empty or thin `feature` value should stop the flow and ask the user, not guess scope for an autonomous multi-phase run. |
| "This host usually has Workflow, skip the check" | "Usually" is not "always" — Codex/Gemini/Cursor/generic hosts must be treated as portable unless Workflow is explicitly in the tool list. |
| "--resume was passed, I'll just start a fresh run instead" | A resume request implies the user expects the prior run's state; silently starting fresh discards that intent — honor `resumeRunId` per the selected runtime's resume path. |

## Next

Read fully and follow **step-02.md** (Workflow Runtime) if Workflow is available, otherwise **step-03.md** (Portable Runtime).
