#!/usr/bin/env bash
# UserPromptSubmit hook — suggest optimal model/effort primitives per task type.
# Advisory only — never blocks. Exit 0 always.
# Modeled on prompt-parallelism-hint.sh

input=$(cat)
prompt=$(echo "$input" | jq -r '.prompt // ""' 2>/dev/null)

# Trivial: quick lookups, Q&A, explain — Haiku is faster and cheaper
if echo "$prompt" | grep -qiE \
  '^(what|where|which|who|when|how|does|is|are|list|show me|tell me|explain|define) .{0,80}$'; then
  echo "💡 TRIVIAL TASK: consider /model haiku for speed + cost savings"
  exit 0
fi

# Complex: architecture, design, root cause, evaluate — use max effort (deepest thinking)
if echo "$prompt" | grep -qiE \
  'architect|design pattern|decompose|root cause|tradeoff|evaluate|compare approaches|refactor (the|entire|whole)|why (is|does|would|did)'; then
  echo "🔥 COMPLEX TASK: consider /effort max — enables deepest thinking mode"
  exit 0
fi

# Rapid iteration: live debugging, tight loop — fast mode adds 2.5x speed, same quality
if echo "$prompt" | grep -qiE \
  'try (again|this|another)|tweak|adjust|one more|still (failing|broken|not working)|iterate'; then
  echo "⚡ ITERATION TASK: consider /fast on — 2.5x speed, same quality, same thinking depth"
  exit 0
fi

# Background/bulk: autonomous tasks where fast mode adds cost without perceived benefit
if echo "$prompt" | grep -qiE \
  'all files|every file|bulk|entire codebase|large.scale|batch process|mass (update|replace|rename)'; then
  echo "🐢 BULK TASK: keep /fast off — background tasks do not benefit from speed"
  exit 0
fi

# Event watching: monitoring/polling/tailing intent → suggest Monitor over /loop
if echo "$prompt" | grep -qiE \
  'watch (the|for|ci|build|log|pod|deploy)|monitor (the|ci|build|log)|tail -f|follow.*log|poll (for|until|every)|notify.*when|alert.*when|detect.*change|wait.*until.*complet|loop.*check|check.*every [0-9]|every (30|60|120|[0-9]+) (sec|min)|ci.*(status|check|watch)|build.*(status|watch|fail)'; then
  echo "📡 MONITORING TASK: consider the Monitor tool — event-driven, zero tokens when silent (vs /loop which charges a full prompt per tick). See ai/rules/monitor-patterns.md for recipes."
  exit 0
fi

# Ambiguous semantic routing across tool ecosystems (Qmd/Graphify/repomix/Serena).
# Unlike the categories above, these don't exit early on their own — a prompt
# can legitimately match more than one, and matching 2+ means the tool choice
# is genuinely ambiguous, not obvious. Advisory only; never blocks (exit 0 always).
_routing_classes=()

if echo "$prompt" | grep -qiE \
  'docs?|documentation|readme|changelog|release notes|knowledge base|runbook|wiki'; then
  echo "📚 DOCS/KNOWLEDGE SEARCH: consider Qmd over ad-hoc grep — see tool-routing skill's Qmd table"
  _routing_classes+=("qmd")
fi

if echo "$prompt" | grep -qiE \
  'depend(s|ency|encies) (on|of|graph)|call graph|who calls|callers of|impact of changing|blast radius|reference graph'; then
  echo "🕸️  DEPENDENCY/GRAPH QUESTION: consider Graphify — see tool-routing skill's Graphify breakdown"
  _routing_classes+=("graphify")
fi

if echo "$prompt" | grep -qiE \
  '[0-9]+\+? files|across (the )?(codebase|repo|project)|many files|multiple files'; then
  echo "📦 MULTI-FILE CONTEXT: consider the repomix skill (5+ files) — see ai/skills/repomix/SKILL.md"
  _routing_classes+=("repomix")
fi

if echo "$prompt" | grep -qiE \
  'find (the )?symbol|rename (the )?(symbol|function|method|class)|where is .* defined|symbol lookup|find (all )?(usages|references) of'; then
  echo "🔎 SYMBOL LOOKUP/RENAME: consider Serena.findSymbol / Serena.renameSymbol — see tool-priority.md §1"
  _routing_classes+=("serena")
fi

if [[ "${#_routing_classes[@]}" -ge 2 ]]; then
  echo "[ESCALATE] 2+ routing classes matched (${_routing_classes[*]}) — invoke Skill(tool-routing) before picking a tool."
fi

exit 0
