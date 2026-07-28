#!/usr/bin/env bash
# pre-commit step: keep this machine's home directory out of staged
# .claude/settings.json.
#
# lean-ctx owns three hook entries in that file and rewrites them with the
# absolute path of its own binary on every `doctor --fix` / `setup` / `wrap`.
# Since ~/.claude/settings.json symlinks here, the machine-specific path reaches
# a tracked, published file. Rewriting the entry by hand does not survive —
# verified that `doctor --fix` re-absolutises from `$HOME/...` and from a bare
# invocation alike.
#
# So the index is normalised rather than the working tree: the live file keeps
# whatever lean-ctx wrote (it works), and the commit stays portable. Only the
# staged blob is touched, so the developer's working copy is never surprised.

set -euo pipefail

TARGET=".claude/settings.json"

# Resolve the normaliser relative to this script rather than hardcoding
# $HOME/.dotfiles: core.hooksPath makes $0 stable, but a script-relative path is
# correct by construction in a worktree or an alternate checkout, and lets the
# test point at the copy under test. DOTFILES_ROOT overrides for that purpose.
_hook_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
DOTFILES_ROOT="${DOTFILES_ROOT:-$(cd "$_hook_dir/../.." && pwd)}"
NORMALIZER="$DOTFILES_ROOT/scripts/normalize_home_paths.py"

# Nothing staged for that path -> nothing to do.
if ! git diff --cached --name-only --diff-filter=ACM -- "$TARGET" | grep -q .; then
    exit 0
fi

[ -f "$NORMALIZER" ] || { echo "normalize-settings-paths: missing $NORMALIZER" >&2; exit 1; }

staged=$(git show ":$TARGET")

if normalized=$(printf '%s' "$staged" | python3 "$NORMALIZER" --label "$TARGET"); then
    :
else
    status=$?
    # 2 = an absolute home path we must not rewrite automatically.
    if [ "$status" -eq 2 ]; then
        echo "normalize-settings-paths: $TARGET has an absolute home path outside \$HOME." >&2
        echo "  Fix it by hand — \$HOME is not a safe substitution there." >&2
    else
        echo "normalize-settings-paths: normaliser failed (exit $status)" >&2
    fi
    exit 1
fi

if [ "$normalized" = "$staged" ]; then
    exit 0
fi

# Rewrite just the index entry, leaving the working tree alone.
blob=$(printf '%s' "$normalized" | git hash-object -w --stdin)
mode=$(git ls-files --stage -- "$TARGET" | awk '{print $1}')
git update-index --cacheinfo "${mode:-100644}","$blob","$TARGET"

echo "normalize-settings-paths: rewrote \$HOME in staged $TARGET (working copy untouched)"
