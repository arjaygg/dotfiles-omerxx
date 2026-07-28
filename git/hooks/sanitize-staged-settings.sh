#!/usr/bin/env bash
# pre-commit step: sanitise staged .claude/settings.json.
#
# Two kinds of drift arrive in that file, both from tools doing the right thing
# locally, and ~/.claude/settings.json is a symlink into this repo so both reach a
# tracked, published file:
#
#   1. lean-ctx rewrites three hook entries with the absolute path of its own
#      binary on every `doctor --fix` / `setup` / `wrap`. Verified that it
#      re-absolutises from `$HOME/...` and from a bare invocation alike, so the
#      entry cannot be written in a form that survives.
#   2. Claude Code writes `skipDangerousModePermissionPrompt`, which is a
#      deliberate machine-local default here. It belongs in
#      .claude/settings.local.json — gitignored, and higher precedence — so
#      dropping it from the commit does not change local behaviour.
#
# Both are fixed in the INDEX, never the working tree: the live file keeps what the
# tools wrote and keeps working, while the commit stays portable and clean. The
# developer's working copy is never silently altered.

set -euo pipefail

TARGET=".claude/settings.json"

# Resolve helpers relative to this script rather than hardcoding $HOME/.dotfiles:
# core.hooksPath makes $0 stable, but a script-relative path is correct by
# construction in a worktree or an alternate checkout, and lets the test point at
# the copy under test. DOTFILES_ROOT overrides for that purpose.
_hook_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
DOTFILES_ROOT="${DOTFILES_ROOT:-$(cd "$_hook_dir/../.." && pwd)}"
NORMALIZER="$DOTFILES_ROOT/scripts/normalize_home_paths.py"
STRIPPER="$DOTFILES_ROOT/scripts/strip_local_only_settings.py"

# Nothing staged for that path -> nothing to do.
if ! git diff --cached --name-only --diff-filter=ACM -- "$TARGET" | grep -q .; then
    exit 0
fi

for helper in "$NORMALIZER" "$STRIPPER"; do
    [ -f "$helper" ] || { echo "sanitize-staged-settings: missing $helper" >&2; exit 1; }
done

staged=$(git show ":$TARGET")

# Pass 1 — this machine's home directory -> $HOME.
if normalized=$(printf '%s' "$staged" | python3 "$NORMALIZER" --label "$TARGET"); then
    :
else
    status=$?
    if [ "$status" -eq 2 ]; then
        # An absolute home path outside $HOME; substituting $HOME would be wrong.
        echo "sanitize-staged-settings: $TARGET has an absolute home path outside \$HOME." >&2
        echo "  Fix it by hand — \$HOME is not a safe substitution there." >&2
    else
        echo "sanitize-staged-settings: path normaliser failed (exit $status)" >&2
    fi
    exit 1
fi

# Pass 2 — machine-local-only keys.
if cleaned=$(printf '%s' "$normalized" | python3 "$STRIPPER" --label "$TARGET"); then
    :
else
    status=$?
    if [ "$status" -eq 2 ]; then
        echo "sanitize-staged-settings: $TARGET is not valid JSON; refusing to strip keys." >&2
    else
        echo "sanitize-staged-settings: local-only key stripper failed (exit $status)" >&2
    fi
    exit 1
fi

if [ "$cleaned" = "$staged" ]; then
    exit 0
fi

# Rewrite just the index entry, leaving the working tree alone.
blob=$(printf '%s' "$cleaned" | git hash-object -w --stdin)
mode=$(git ls-files --stage -- "$TARGET" | awk '{print $1}')
git update-index --cacheinfo "${mode:-100644}","$blob","$TARGET"

echo "sanitize-staged-settings: cleaned staged $TARGET (working copy untouched)"
