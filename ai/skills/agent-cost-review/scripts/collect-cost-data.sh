#!/usr/bin/env bash
# collect-cost-data.sh — one-pass data collection for an agent cost review.
#
# Usage:
#   bash collect-cost-data.sh <YYYY-MM> [--agent claude|all] [--out DIR] [--repos "path1 path2"]
#
# Writes <out>/summary.json plus intermediate JSON, and prints a human-readable digest.
# Runs for 2-5 minutes on a heavy month; it sweeps every session transcript in the window.
#
# Requires: ccusage, jq. Optional: gh (for PR counts), git (for commit counts).

set -uo pipefail

WINDOW="${1:-}"
[ -z "$WINDOW" ] && { echo "usage: $0 <YYYY-MM> [--agent claude|all] [--out DIR] [--repos \"p1 p2\"]" >&2; exit 2; }
shift

AGENT=claude
OUT=""
REPOS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --agent) AGENT="$2"; shift 2 ;;
    --out)   OUT="$2";   shift 2 ;;
    --repos) REPOS="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

case "$WINDOW" in
  [0-9][0-9][0-9][0-9]-[0-9][0-9]) : ;;
  *) echo "window must be YYYY-MM, got '$WINDOW'" >&2; exit 2 ;;
esac

OUT="${OUT:-$HOME/reports/${WINDOW}-agent-cost}"
mkdir -p "$OUT"

# ---------------------------------------------------------------- date window

YEAR="${WINDOW%-*}"
MONTH="${WINDOW#*-}"
START="${WINDOW}-01"

next_month() {  # YYYY-MM -> YYYY-MM-01 of the following month
  local y="${1%-*}" m="${1#*-}"
  m=$((10#$m + 1))
  if [ "$m" -gt 12 ]; then m=1; y=$((y + 1)); fi
  printf '%04d-%02d-01' "$y" "$m"
}
prev_month() {
  local y="${1%-*}" m="${1#*-}"
  m=$((10#$m - 1))
  if [ "$m" -lt 1 ]; then m=12; y=$((y - 1)); fi
  printf '%04d-%02d' "$y" "$m"
}

END_EXCL="$(next_month "$WINDOW")"          # first day of next month (exclusive bound)
PREV="$(prev_month "$WINDOW")"
PREV_START="${PREV}-01"
PREV_END_EXCL="$START"
COMPACT_START="${START//-/}"

# ccusage --until is INCLUSIVE. Passing END_EXCL (the 1st of the next month)
# silently pulls one extra day into the window, which inflates the comparison
# baseline and understates growth. Step back one day for every ccusage call.
day_before() {  # YYYY-MM-DD -> YYYYMMDD of the preceding day
  date -v-1d -j -f "%Y-%m-%d" "$1" +%Y%m%d 2>/dev/null \
    || date -d "$1 -1 day" +%Y%m%d 2>/dev/null
}
COMPACT_END_INCL="$(day_before "$END_EXCL")"
PREV_COMPACT_START="${PREV_START//-/}"
PREV_COMPACT_END_INCL="$(day_before "$START")"
[ -n "$COMPACT_END_INCL" ] || { echo "could not compute window end date" >&2; exit 1; }

CC_ROOT="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects"
export CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"

echo "window       : $START .. $END_EXCL (exclusive)"
echo "agent scope  : $AGENT"
echo "output dir   : $OUT"
echo

# ------------------------------------------------------------ ccusage extracts
# `ccusage claude ...` scopes to Claude Code. Bare `ccusage ...` includes every
# coding agent it detects (Codex, Gemini, ...). Mixing them silently makes every
# ratio wrong, so the scope is explicit.

if [ "$AGENT" = "claude" ]; then CCU=(ccusage claude); else CCU=(ccusage); fi

echo "[1/6] ccusage daily + model breakdown ..."
"${CCU[@]}" daily --since "$COMPACT_START" --until "$COMPACT_END_INCL" --breakdown --json \
  > "$OUT/daily.json" 2>/dev/null || { echo "ccusage daily failed" >&2; exit 1; }

echo "[2/6] ccusage sessions (project attribution) ..."
"${CCU[@]}" session --since "$COMPACT_START" --until "$COMPACT_END_INCL" --json \
  > "$OUT/sessions.json" 2>/dev/null || echo '{"sessions":[]}' > "$OUT/sessions.json"

echo "[3/6] previous window for comparison ..."
"${CCU[@]}" daily --since "$PREV_COMPACT_START" --until "$PREV_COMPACT_END_INCL" --breakdown --json \
  > "$OUT/daily_prev.json" 2>/dev/null || echo '{"daily":[]}' > "$OUT/daily_prev.json"

# ------------------------------------------------------- raw transcript sweep
# Dollar figures always come from ccusage (deduplicated by request id).
# The raw sweep supplies STRUCTURAL ratios only: request counts, average context
# size, main-vs-subagent split, and the fixed first-turn preamble. Raw logs
# double-count resumed/forked sessions (~2x), which cancels out of ratios.

echo "[4/6] sweeping raw transcripts for context structure ..."
find "$CC_ROOT" -name '*.jsonl' -newermt "$START" > "$OUT/files.txt" 2>/dev/null || : > "$OUT/files.txt"
grep -v 'subagents/' "$OUT/files.txt" > "$OUT/files_main.txt" || : > "$OUT/files_main.txt"
grep    'subagents/' "$OUT/files.txt" > "$OUT/files_sub.txt"  || : > "$OUT/files_sub.txt"

sweep() {  # $1=file list  $2=tag  -> tsv: tag model in out cW cR
  local list="$1" tag="$2"
  [ -s "$list" ] || return 0
  # One jq process over many files; spawning jq per file is ~50x slower.
  xargs jq -r --arg t "$tag" --arg s "$START" --arg e "$END_EXCL" '
    select(.type == "assistant"
           and .message.usage != null
           and .timestamp >= $s
           and .timestamp <  $e)
    | [ $t,
        (.message.model // "unknown"),
        (.message.usage.input_tokens // 0),
        (.message.usage.output_tokens // 0),
        (.message.usage.cache_creation_input_tokens // 0),
        (.message.usage.cache_read_input_tokens // 0) ]
    | @tsv' < "$list" 2>/dev/null
}

{ sweep "$OUT/files_main.txt" MAIN; sweep "$OUT/files_sub.txt" SUB; } > "$OUT/calls.tsv"

# First-turn context = the fixed preamble: system prompt, standing instructions,
# skill/agent listings, MCP tool catalogues -- everything paid before any project
# file is read. Sampled, because the median is stable well before the full set.
echo "[5/6] measuring per-session context floor ..."
: > "$OUT/floor.txt"
head -400 "$OUT/files_main.txt" | while IFS= read -r f; do
  jq -r 'select(.type == "assistant" and .message.usage != null)
         | ((.message.usage.input_tokens // 0)
            + (.message.usage.cache_creation_input_tokens // 0)
            + (.message.usage.cache_read_input_tokens // 0))' "$f" 2>/dev/null | head -1
done >> "$OUT/floor.txt"

STRUCT="$(awk -F'\t' '
  { n++; o += $4; cw += $5; cr += $6
    if ($1 == "MAIN") { mn++; mcr += $6 } else { sn++; scr += $6; so += $4 } }
  END {
    if (n == 0) { print "{\"requests_raw\":0}"; exit }
    printf "{\"requests_raw\":%d,\"main_requests\":%d,\"sub_requests\":%d,", n, mn, sn
    printf "\"subagent_request_share\":%.4f,", (n ? sn / n : 0)
    printf "\"subagent_cache_read_share\":%.4f,", ((mcr + scr) ? scr / (mcr + scr) : 0)
    printf "\"subagent_output_share\":%.4f,", (o ? so / o : 0)
    printf "\"avg_context_tokens\":%d}", (n ? (cr + cw) / n : 0)
  }' "$OUT/calls.tsv")"

FLOOR="$(sort -n "$OUT/floor.txt" | awk '
  NF { a[++n] = $1 }
  END {
    if (n == 0) { print "{\"floor_sample\":0}"; exit }
    printf "{\"floor_sample\":%d,\"floor_p10\":%d,\"floor_median\":%d,\"floor_p90\":%d}",
      n, a[int(n * 0.1) + 1], a[int((n + 1) / 2)], a[int(n * 0.9) + 1]
  }')"

PER_MODEL_CALLS="$(awk -F'\t' '
  { n[$2]++ ; c[$2] += $5 + $6 }
  END { printf "{"; s = ""
        for (m in n) { printf "%s\"%s\":{\"requests\":%d,\"avg_context\":%d}", s, m, n[m], n[m] ? c[m] / n[m] : 0; s = "," }
        printf "}" }' "$OUT/calls.tsv")"

# ------------------------------------------------------------- delivered work

echo "[6/6] delivered work (PRs, commits) ..."
PRS='{"available":false}'
if command -v gh >/dev/null 2>&1; then
  m_now=$(gh search prs --author=@me --merged-at="${START}..${END_EXCL}"      --limit 1000 --json number 2>/dev/null | jq 'length' 2>/dev/null || echo null)
  o_now=$(gh search prs --author=@me --created="${START}..${END_EXCL}"        --limit 1000 --json number 2>/dev/null | jq 'length' 2>/dev/null || echo null)
  m_prv=$(gh search prs --author=@me --merged-at="${PREV_START}..${PREV_END_EXCL}" --limit 1000 --json number 2>/dev/null | jq 'length' 2>/dev/null || echo null)
  [ -n "$m_now" ] && PRS="{\"available\":true,\"merged\":${m_now:-null},\"opened\":${o_now:-null},\"merged_prev\":${m_prv:-null}}"
fi

# Repos to count commits in: caller-supplied, else inferred from the busiest
# session project paths. Inference is best-effort -- worktrees and renamed dirs
# will not resolve, which is why --repos exists.
if [ -z "$REPOS" ]; then
  # Project dirs encode the absolute path with '/' replaced by '-'. Strip the
  # encoded $HOME rather than a guessed pattern -- a username containing a
  # hyphen (axos-agallentes) defeats any '^-Users-[^-]*-' style match.
  HOME_ENC="$(printf '%s' "$HOME" | tr '/' '-')"
  REPOS="$(jq -r '[.sessions[]?.projectPath] | map(select(. != null))
                  | group_by(.) | map({p: .[0], n: length}) | sort_by(-.n)
                  | .[:12][].p' "$OUT/sessions.json" 2>/dev/null \
           | sed "s|^${HOME_ENC}-||; s|^${HOME_ENC}||; s|--trees.*$||; s|/.*$||" \
           | sed '/^$/d' | sort -u | tr '\n' ' ')"
  RESOLVED=""
  for r in $REPOS; do
    # Claude encodes path separators as '-', so "git-foo-bar" may be
    # "git/foo-bar". Repo dirs also mix '-' and '_' in leaf names.
    slashed="$(printf '%s' "$r" | sed 's|^git-|git/|')"
    leaf="${slashed#git/}"
    leaf_us="$(printf '%s' "$leaf" | tr '-' '_')"
    # A leading '-' is an encoded dotfile dir: "-dotfiles" -> "$HOME/.dotfiles".
    dotted=".${r#-}"
    for cand in "$HOME/$slashed" "$HOME/git/$leaf_us" "$HOME/$dotted" \
                "$HOME/git/$r" "$HOME/$r" "$HOME/.$r"; do
      [ -d "$cand/.git" ] && case " $RESOLVED " in
        *" $cand "*) : ;;
        *) RESOLVED="$RESOLVED $cand"; break ;;
      esac
    done
  done
  REPOS="$RESOLVED"
fi

: > "$OUT/commits.tsv"
for d in $REPOS; do
  [ -d "$d/.git" ] || continue
  n=$(git -C "$d" log --since="$START" --until="$END_EXCL" --oneline 2>/dev/null | wc -l | tr -d ' ')
  st=$(git -C "$d" log --since="$START" --until="$END_EXCL" --shortstat --pretty=tformat: 2>/dev/null \
       | awk '{for(i=1;i<=NF;i++){if($i ~ /^insertion/)a+=$(i-1); if($i ~ /^deletion/)b+=$(i-1); if($i ~ /^file/)f+=$(i-1)}}
              END{printf "%d\t%d\t%d", f, a, b}')
  printf '%s\t%s\t%s\n' "$(basename "$d")" "${n:-0}" "$st" >> "$OUT/commits.tsv"
done

COMMITS="$(awk -F'\t' '
  { n += $2; f += $3; ins += $4; del += $5
    if ($4 > maxins) { maxins = $4; maxrepo = $1 }
    rows = rows sep "{\"repo\":\"" $1 "\",\"commits\":" $2 ",\"files\":" $3 ",\"insertions\":" $4 ",\"deletions\":" $5 "}"; sep = "," }
  END { printf "{\"total_commits\":%d,\"total_files\":%d,\"total_insertions\":%d,", n, f, ins
        printf "\"loc_outlier_repo\":\"%s\",\"loc_outlier_insertions\":%d,", maxrepo, maxins
        printf "\"loc_trustworthy\":%s,", (ins > 0 && maxins / ins > 0.6) ? "false" : "true"
        printf "\"by_repo\":[%s]}", rows }' "$OUT/commits.tsv")"
[ -s "$OUT/commits.tsv" ] || COMMITS='{"total_commits":0,"loc_trustworthy":false,"by_repo":[]}'

# ------------------------------------------------- assemble + decompose in jq
# Component split assumes the published cache multipliers relative to input:
#   output = 5x, cache write = 1.25x, cache read = 0.10x
# Each model's base input rate is then solved from its own MEASURED total cost,
# so the split is internally consistent per model. It is a model, not a
# measurement -- say so in the report. See references/cost-model.md.

jq -n \
  --slurpfile daily "$OUT/daily.json" \
  --slurpfile prev  "$OUT/daily_prev.json" \
  --slurpfile sess  "$OUT/sessions.json" \
  --argjson struct  "$STRUCT" \
  --argjson floor   "$FLOOR" \
  --argjson mcalls  "$PER_MODEL_CALLS" \
  --argjson prs     "$PRS" \
  --argjson commits "$COMMITS" \
  --arg window "$WINDOW" --arg prevw "$PREV" --arg agent "$AGENT" '
  def models($d): [ $d[0].daily[]?.modelBreakdowns[]? ]
    | group_by(.modelName)
    | map({ model: .[0].modelName,
            cost:  (map(.cost)                 | add // 0),
            inp:   (map(.inputTokens)          | add // 0),
            out:   (map(.outputTokens)         | add // 0),
            cW:    (map(.cacheCreationTokens)  | add // 0),
            cR:    (map(.cacheReadTokens)      | add // 0) })
    | map(. + { weight: (.inp + 5 * .out + 1.25 * .cW + 0.1 * .cR) })
    | map(. + { base_rate_per_mtok: (if .weight > 0 then .cost / (.weight / 1000000) else 0 end),
                rate:               (if .weight > 0 then .cost / .weight else 0 end) })
    | map(. + { cost_input:  (.rate * .inp),
                cost_output: (.rate * 5 * .out),
                cost_cwrite: (.rate * 1.25 * .cW),
                cost_cread:  (.rate * 0.1 * .cR),
                tokens:      (.inp + .out + .cW + .cR) })
    | sort_by(-.cost);

  (models($daily))                                     as $m
  | ([ $m[].cost ]   | add // 0)                       as $total
  | ([ $m[].tokens ] | add // 1)                       as $tok
  | ([ $prev[0].daily[]?.modelBreakdowns[]?.cost ] | add // 0) as $prevcost
  | [ $daily[0].daily[]? | { date: .period,
                             cost: (.modelBreakdowns // [] | map(.cost) | add // 0) } ] as $days
  | ([ $sess[0].sessions[]? ] | sort_by(-.totalCost))   as $ss
  | ([ $ss[].totalCost ] | add // 0)                    as $stotal
  | {
    window: $window, previous_window: $prevw, agent_scope: $agent,

    totals: {
      cost: $total,
      cost_previous: $prevcost,
      cost_growth: (if $prevcost > 0 then $total / $prevcost else null end),
      tokens: $tok,
      input:  ([ $m[].inp ] | add // 0),
      output: ([ $m[].out ] | add // 0),
      cache_write: ([ $m[].cW ] | add // 0),
      cache_read:  ([ $m[].cR ] | add // 0),
      annualised: ($total * 12)
    },

    components: (
      { input:  ([ $m[].cost_input  ] | add // 0),
        output: ([ $m[].cost_output ] | add // 0),
        cache_write: ([ $m[].cost_cwrite ] | add // 0),
        cache_read:  ([ $m[].cost_cread  ] | add // 0) }
      | . + { context_total: (.input + .cache_write + .cache_read),
              context_share: (if $total > 0 then (.input + .cache_write + .cache_read) / $total else 0 end),
              generation_share: (if $total > 0 then .output / $total else 0 end),
              basis: "modelled: output 5x input, cache write 1.25x, cache read 0.10x; base rate solved per model from its measured total" }
    ),

    by_model: [ $m[] | {
      model, cost, tokens,
      cost_share:   (if $total > 0 then .cost / $total else 0 end),
      token_share:  (.tokens / $tok),
      base_rate_per_mtok,
      output: .out, cache_read: .cR, cache_write: .cW,
      requests: ($mcalls[.model].requests // null),
      avg_context: ($mcalls[.model].avg_context // null)
    } ],

    rate_ratio_vs_cheapest_major: (
      ([ $m[] | select(.cost > ($total * 0.05)) | .base_rate_per_mtok ] | min) as $lo
      | [ $m[] | select(.cost > ($total * 0.05))
          | { model, ratio: (if $lo > 0 then .base_rate_per_mtok / $lo else null end) } ]
    ),

    daily: $days,
    daily_stats: {
      active_days:      ([ $days[] | select(.cost > 1) ] | length),
      substantive_days: ([ $days[] | select(.cost > ($total / 40)) ] | length),
      peak: ($days | sort_by(-.cost) | .[0] // null),
      last_day: ($days | last // null)
    },

    sessions: {
      count: ($ss | length),
      total_cost: $stotal,
      top10_share: (if $stotal > 0 then ([ $ss[:10][].totalCost ] | add // 0) / $stotal else 0 end),
      top50_share: (if $stotal > 0 then ([ $ss[:50][].totalCost ] | add // 0) / $stotal else 0 end),
      tail_share:  (if $stotal > 0 then 1 - (([ $ss[:50][].totalCost ] | add // 0) / $stotal) else 0 end),
      cost_per_session: (if ($ss | length) > 0 then $stotal / ($ss | length) else 0 end),
      top: [ $ss[:15][] | { cost: .totalCost, project: .projectPath, id: (.sessionId // "")[0:8],
                            started: (.firstActivity // "")[0:10], cache_read: .cacheReadTokens } ]
    },

    by_project: [ $ss[] | { p: .projectPath, c: .totalCost } ]
      | group_by(.p)
      | map({ project: .[0].p,
              cost: (map(.c) | add),
              sessions: length,
              cost_per_session: ((map(.c) | add) / length) })
      | sort_by(-.cost) | .[:20],

    structure: ($struct + $floor + {
      floor_share_of_context: (if ($struct.avg_context_tokens // 0) > 0
                               then ($floor.floor_median // 0) / $struct.avg_context_tokens else null end)
    }),

    delivered: { pull_requests: $prs, commits: $commits },

    unit_economics: (
      ($prs.merged // null) as $mg | ($prs.merged_prev // null) as $mp
      | { cost_per_merged_pr:      (if ($mg // 0) > 0 then $total / $mg else null end),
          cost_per_merged_pr_prev: (if ($mp // 0) > 0 and $prevcost > 0 then $prevcost / $mp else null end),
          cost_per_commit:         (if ($commits.total_commits // 0) > 0 then $total / $commits.total_commits else null end),
          throughput_growth:       (if ($mp // 0) > 0 then ($mg // 0) / $mp else null end) }
      | . + { unit_cost_regression: (if .cost_per_merged_pr != null and .cost_per_merged_pr_prev != null
                                     then .cost_per_merged_pr / .cost_per_merged_pr_prev else null end) }
    )
  }' > "$OUT/summary.json"

# ------------------------------------------------------------------- digest

jq -r '
  "=== \(.window) · scope=\(.agent_scope) ===",
  "cost              $\(.totals.cost | floor)  (prev $\(.totals.cost_previous | floor)\(if .totals.cost_growth then ", \(.totals.cost_growth * 10 | floor / 10)x" else "" end))",
  "annualised        $\(.totals.annualised | floor)",
  "",
  "components        cache-read \(.components.cache_read | floor) · cache-write \(.components.cache_write | floor) · output \(.components.output | floor) · input \(.components.input | floor)",
  "context share     \(.components.context_share * 1000 | floor / 10)%   generation \(.components.generation_share * 1000 | floor / 10)%",
  "",
  "models            " + ([ .by_model[] | "\(.model) $\(.cost | floor) (\(.cost_share * 1000 | floor / 10)% cost / \(.token_share * 1000 | floor / 10)% tok)" ] | join("\n                  ")),
  "",
  "sessions          \(.sessions.count)  ·  $\(.sessions.cost_per_session * 100 | floor / 100)/session  ·  top10 \(.sessions.top10_share * 1000 | floor / 10)% · tail \(.sessions.tail_share * 1000 | floor / 10)%",
  "context floor     median \(.structure.floor_median // 0) tok of avg \(.structure.avg_context_tokens // 0) (\((.structure.floor_share_of_context // 0) * 1000 | floor / 10)%)",
  "subagents         \((.structure.subagent_request_share // 0) * 1000 | floor / 10)% of requests",
  "",
  "delivered         PRs merged \(.delivered.pull_requests.merged // "n/a") (prev \(.delivered.pull_requests.merged_prev // "n/a")) · commits \(.delivered.commits.total_commits // 0)",
  "loc trustworthy   \(.delivered.commits.loc_trustworthy)  \(if .delivered.commits.loc_trustworthy == false then "(outlier: \(.delivered.commits.loc_outlier_repo)) -- do not report LOC" else "" end)",
  "",
  "cost / merged PR  $\((.unit_economics.cost_per_merged_pr // 0) * 100 | floor / 100)  (prev $\((.unit_economics.cost_per_merged_pr_prev // 0) * 100 | floor / 100)\(if .unit_economics.unit_cost_regression then ", \(.unit_economics.unit_cost_regression * 10 | floor / 10)x" else "" end))",
  "throughput growth \(if .unit_economics.throughput_growth then (.unit_economics.throughput_growth * 100 | floor / 100) else "n/a" end)x",
  "",
  "top projects      " + ([ .by_project[:8][] | "$\(.cost | floor)  \(.sessions)s  \(.project)" ] | join("\n                  "))
' "$OUT/summary.json"

echo
echo "summary.json -> $OUT/summary.json"
