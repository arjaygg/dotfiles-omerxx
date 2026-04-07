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

exit 0
