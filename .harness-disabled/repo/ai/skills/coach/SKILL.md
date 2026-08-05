---
name: coach
description: >
  On-demand AI engineering coaching powered by the Microsoft AI Engineering Coach rule catalog
  (synced from microsoft/AI-Engineering-Coach). Reads your Claude Code session logs
  (~/.claude/projects/**/*.jsonl) and surfaces personalized anti-pattern feedback based on
  your actual usage data. No VS Code required. Use for periodic usage reviews, identifying
  blind spots, and improving agentic workflow habits.
version: 1.0.0
triggers:
  - coach me
  - how am I using AI
  - review my AI usage
  - AI coaching session
  - show my anti-patterns
  - am I using AI well
  - what bad habits do I have
  - coach sync
---

# AI Engineering Coach

Surfaces personalized coaching insights from the [Microsoft AI Engineering Coach](https://github.com/microsoft/AI-Engineering-Coach) rule catalog, applied to your real Claude Code session data.

## Modes

| Invocation | Behavior |
|-----------|---------|
| `/coach` | Analyze last 7 days of sessions (default) |
| `/coach sync` | Re-sync rules from upstream Microsoft repo |
| `/coach check <rule-id>` | Explain one rule and assess whether it applies to you |

## Execution Steps

### 0. Sync check

Verify `ai/skills/coach/rules/` exists and contains `.md` files:

```bash
ls ~/.dotfiles/ai/skills/coach/rules/*.md 2>/dev/null | wc -l | tr -d ' '
```

If the count is 0, run sync first:

```bash
bash ~/.dotfiles/ai/skills/coach/sync.sh
```

For `/coach sync`, always run `sync.sh` and report the updated rule count.

### 1. Load coaching persona

Read the `PERSONA` constant from `~/.dotfiles/ai/skills/coach/coach-persona.ts` — adopt it
as your coaching voice for this session (warm but professional, data-driven, celebrate
strengths before weaknesses, suggest 1–2 changes at a time).

### 2. Load the rule catalog

Read every `.md` file in `~/.dotfiles/ai/skills/coach/rules/`. Each rule has:

```yaml
id: <rule-id>
name: <human name>
group: <prompt-quality|session-hygiene|tool-mastery|context-management|code-review|...>
severity: high|medium|low
```

And plain-English sections: **Description**, **When Triggered**, **How to Improve**, **Examples**.

### 3. Gather session data

Use `jq` to extract coaching signals from `~/.claude/projects/**/*.jsonl`.

**JSONL format** (from parser-claude.ts):
- `type: "user"` lines → `message.content[].text`, `timestamp`, `cwd`, `sessionId`
- `type: "assistant"` lines → `message.content[]` (incl. `type: "tool_use"` blocks with `name`), `message.model`

Run these in parallel:

```bash
# Session sizes (message count per file)
find ~/.claude/projects -name "*.jsonl" -newer /tmp/._coach_cutoff 2>/dev/null \
  | xargs -I{} sh -c 'echo "$(jq -r "select(.type==\"user\") | .sessionId" "$1" | sort -u | head -1) $(jq "select(.type==\"user\") | 1" "$1" | wc -l | tr -d " ")" -- {}' \
  | sort -k2 -rn | head -20
```

```bash
# Touch a cutoff file for --days scoping (default: 7 days)
touch -t "$(date -v-7d +%Y%m%d%H%M)" /tmp/._coach_cutoff 2>/dev/null || \
  touch -d "7 days ago" /tmp/._coach_cutoff 2>/dev/null
```

```bash
# User message lengths (for lazy-prompting)
find ~/.claude/projects -name "*.jsonl" -newer /tmp/._coach_cutoff 2>/dev/null \
  | xargs jq -r 'select(.type=="user") | .message.content[]? | select(.type=="text") | .text | length' 2>/dev/null \
  | awk '{sum+=$1; count++; if($1<30) short++} END {printf "total=%d short=%d ratio=%.2f\n", count, short, (count>0 ? short/count : 0)}'
```

```bash
# Models used (for model-overreliance)
find ~/.claude/projects -name "*.jsonl" -newer /tmp/._coach_cutoff 2>/dev/null \
  | xargs jq -r 'select(.type=="assistant" and .message.model != null) | .message.model' 2>/dev/null \
  | sort | uniq -c | sort -rn
```

```bash
# Tool names used (for yolo-mode, agentic-no-tools)
find ~/.claude/projects -name "*.jsonl" -newer /tmp/._coach_cutoff 2>/dev/null \
  | xargs jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="tool_use") | .name' 2>/dev/null \
  | sort | uniq -c | sort -rn | head -15
```

```bash
# Slash commands in user messages (for no-plan-mode, no-slash-commands)
find ~/.claude/projects -name "*.jsonl" -newer /tmp/._coach_cutoff 2>/dev/null \
  | xargs jq -r 'select(.type=="user") | .message.content[]? | select(.type=="text") | .text' 2>/dev/null \
  | grep -o '/[a-z][a-z-]*' | sort | uniq -c | sort -rn | head -10
```

### 4. Apply rules

For each rule in the catalog, assess whether the detection condition described in
**When Triggered** matches the gathered data. Use the severity and thresholds described
in each rule's frontmatter as guidance.

Focus especially on rules where your data clearly crosses the threshold described —
avoid flagging borderline cases.

### 5. Output

**Format:**

```
## AI Engineering Coach — [Quick Review | 7-Day Summary | Check: <rule-id>]

### Top findings

**1. [Rule Name]** · severity: high|medium|low · `rule-id`
> [What I observed in your data]
> 
> **How to improve:** [verbatim from the rule's "How to Improve" section]

**2. ...** (max 3 findings)

---

### What's working ✓

**[Rule Name]** — [one sentence on why this rule is NOT triggered for you]

---

*Rules sourced from [microsoft/AI-Engineering-Coach](https://github.com/microsoft/AI-Engineering-Coach).
Run `/coach sync` to pull updates.*
```

**Tone:** Follow the coaching persona — warm, data-specific, 1–2 changes at a time.
Cite actual numbers from the data ("Your avg session has 61 messages — aim for under 50").

## Notes

- Rules directory: `~/.dotfiles/ai/skills/coach/rules/` (gitignored — synced from upstream)
- Sync script: `~/.dotfiles/ai/skills/coach/sync.sh`
- Source repo: https://github.com/microsoft/AI-Engineering-Coach
