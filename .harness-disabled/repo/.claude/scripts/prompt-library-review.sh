#!/usr/bin/env bash
# prompt-library-review.sh — Review, star, and promote prompts from the library.
#
# Usage:
#   prompt-library-review.sh top [N]        — Show top N prompts by score (default: 20)
#   prompt-library-review.sh recent [N]     — Show N most recent prompts (default: 20)
#   prompt-library-review.sh star <id>      — Toggle starred flag
#   prompt-library-review.sh promote <id>   — Promote to ai/prompts/<slug>.md
#   prompt-library-review.sh stats          — Show library statistics
#   prompt-library-review.sh browse         — Interactive fzf browser (star/promote/delete)

set -euo pipefail

DB_FILE="$HOME/.local/share/prompt-library/prompts.db"
DOTFILES="${DOTFILES_ROOT:-$HOME/.dotfiles}"
PROMPTS_DIR="$DOTFILES/ai/prompts"

[[ -f "$DB_FILE" ]] || { echo "Database not found: $DB_FILE" >&2; echo "Run prompt-library-import.sh first." >&2; exit 1; }

cmd="${1:-top}"
shift || true

case "$cmd" in
    top)
        limit="${1:-20}"
        echo "═══ Top $limit Prompts by Score ═══"
        sqlite3 -column -header "$DB_FILE" "
            SELECT id, score,
                   CASE WHEN starred THEN '★' ELSE ' ' END AS star,
                   CASE WHEN promoted THEN '✓' ELSE ' ' END AS promo,
                   substr(prompt, 1, 70) || CASE WHEN length(prompt) > 70 THEN '...' ELSE '' END AS prompt,
                   project, word_count AS wc
            FROM prompts
            WHERE deleted = 0
            ORDER BY starred DESC, score DESC, reuse_count DESC
            LIMIT $limit;"
        ;;

    recent)
        limit="${1:-20}"
        echo "═══ $limit Most Recent Prompts ═══"
        sqlite3 -column -header "$DB_FILE" "
            SELECT id, score,
                   CASE WHEN starred THEN '★' ELSE ' ' END AS star,
                   substr(prompt, 1, 70) || CASE WHEN length(prompt) > 70 THEN '...' ELSE '' END AS prompt,
                   project, date(timestamp) AS date
            FROM prompts
            WHERE deleted = 0
            ORDER BY timestamp DESC
            LIMIT $limit;"
        ;;

    star)
        id="${1:?Usage: prompt-library-review.sh star <id>}"
        current=$(sqlite3 "$DB_FILE" "SELECT starred FROM prompts WHERE id = '$id';")
        [[ -z "$current" ]] && { echo "Prompt $id not found" >&2; exit 1; }
        new_val=$((1 - current))
        sqlite3 "$DB_FILE" "UPDATE prompts SET starred = $new_val WHERE id = '$id';"
        if [[ "$new_val" -eq 1 ]]; then
            echo "★ Starred prompt $id"
        else
            echo "  Unstarred prompt $id"
        fi
        ;;

    promote)
        id="${1:?Usage: prompt-library-review.sh promote <id>}"
        row=$(sqlite3 -json "$DB_FILE" "SELECT * FROM prompts WHERE id = '$id' AND deleted = 0;" 2>/dev/null)
        [[ "$row" == "[]" || -z "$row" ]] && { echo "Prompt $id not found or deleted" >&2; exit 1; }

        prompt=$(echo "$row" | python3 -c "import sys,json; print(json.loads(sys.stdin.read())[0]['prompt'].strip())")
        project=$(echo "$row" | python3 -c "import sys,json; print(json.loads(sys.stdin.read())[0].get('project','').strip())")
        score=$(echo "$row" | python3 -c "import sys,json; print(json.loads(sys.stdin.read())[0].get('score',0))")

        # Generate slug from first 5 words of prompt
        slug=$(echo "$prompt" | tr '[:upper:]' '[:lower:]' | tr -cs '[:alnum:]' '-' | cut -c1-50 | sed 's/-$//')

        # Check if already promoted
        already=$(sqlite3 "$DB_FILE" "SELECT promoted FROM prompts WHERE id = '$id';")
        [[ "$already" -eq 1 ]] && { echo "Prompt $id already promoted" >&2; exit 1; }

        mkdir -p "$PROMPTS_DIR"

        # Write the prompt file with frontmatter
        cat > "$PROMPTS_DIR/$slug.md" <<EOF
---
name: $slug
description: Promoted from prompt library (score: $score, source: $project)
source_id: $id
promoted_at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
---

$prompt
EOF

        sqlite3 "$DB_FILE" "UPDATE prompts SET promoted = 1 WHERE id = '$id';"
        echo "✓ Promoted to: $PROMPTS_DIR/$slug.md"
        echo "  Available in Ctrl+A / picker"
        ;;

    stats)
        echo "═══ Prompt Library Statistics ═══"
        sqlite3 "$DB_FILE" "
            SELECT
                count(*) AS total_prompts,
                count(CASE WHEN deleted = 0 THEN 1 END) AS active,
                count(CASE WHEN starred = 1 THEN 1 END) AS starred,
                count(CASE WHEN promoted = 1 THEN 1 END) AS promoted,
                count(CASE WHEN score > 0 THEN 1 END) AS positive_score,
                count(CASE WHEN score < 0 THEN 1 END) AS negative_score,
                round(avg(score), 1) AS avg_score,
                max(score) AS max_score,
                count(DISTINCT project) AS projects
            FROM prompts;" | while IFS='|' read -r total active starred promoted pos neg avg max projects; do
            echo "  Total prompts:    $total"
            echo "  Active:           $active"
            echo "  Starred:          $starred"
            echo "  Promoted:         $promoted"
            echo "  Positive score:   $pos"
            echo "  Negative score:   $neg"
            echo "  Average score:    $avg"
            echo "  Max score:        $max"
            echo "  Projects:         $projects"
        done
        echo ""
        echo "═══ Top Projects ═══"
        sqlite3 -column -header "$DB_FILE" "
            SELECT project, count(*) AS prompts, round(avg(score),1) AS avg_score
            FROM prompts WHERE deleted = 0
            GROUP BY project ORDER BY count(*) DESC LIMIT 10;"
        ;;

    browse)
        # Interactive fzf browser
        tmpfile=$(mktemp)
        trap 'rm -f "$tmpfile"' EXIT

        reload_cmd="sqlite3 '$DB_FILE' \"SELECT id || '\t' || CASE WHEN starred THEN '★' ELSE ' ' END || ' [' || printf('%+d', score) || '] ' || substr(prompt, 1, 80) || '\t' || project || '\t' || date(timestamp) FROM prompts WHERE deleted = 0 ORDER BY starred DESC, score DESC, timestamp DESC;\""

        eval "$reload_cmd" | fzf \
            --delimiter='\t' \
            --with-nth=2,3,4 \
            --prompt="  prompt library: " \
            --header="Enter: view · Alt-S: star · Alt-P: promote · Alt-D: delete · Esc: close" \
            --border \
            --height=80% \
            --ansi \
            --preview="id=\$(echo {} | cut -f1); sqlite3 '$DB_FILE' \"SELECT '═══ Prompt ═══' || char(10) || prompt || char(10) || char(10) || '═══ Metadata ═══' || char(10) || 'ID: ' || id || char(10) || 'Score: ' || score || char(10) || 'Starred: ' || CASE WHEN starred THEN 'Yes' ELSE 'No' END || char(10) || 'Promoted: ' || CASE WHEN promoted THEN 'Yes' ELSE 'No' END || char(10) || 'Project: ' || project || char(10) || 'Branch: ' || branch || char(10) || 'Date: ' || timestamp || char(10) || 'Words: ' || word_count FROM prompts WHERE id = '\$id';\"" \
            --preview-window='right:50%:wrap' \
            --bind="alt-s:execute-silent(id=\$(echo {} | cut -f1); $0 star \$id)+reload($reload_cmd)" \
            --bind="alt-p:execute(id=\$(echo {} | cut -f1); $0 promote \$id; read -p 'Press Enter...')+reload($reload_cmd)" \
            --bind="alt-d:execute-silent(id=\$(echo {} | cut -f1); sqlite3 '$DB_FILE' \"UPDATE prompts SET deleted=1 WHERE id='\$id';\")+reload($reload_cmd)" \
            2>/dev/null || true
        ;;

    *)
        echo "Usage: prompt-library-review.sh {top|recent|star|promote|stats|browse} [args]" >&2
        exit 1
        ;;
esac
