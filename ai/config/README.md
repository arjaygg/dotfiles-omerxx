# Portable configuration proposals

This directory contains tracked, portable configuration bases and examples. It is
not a live runtime directory. `scripts/config_generate.py` merges a base JSON file
with an optional ignored overlay and prints a proposal to stdout; it never writes a
runtime file or adopts runtime drift.

## Claude

- `claude/settings.base.json` is the sanitized, portable snapshot for the current
  tracked Claude settings.
- `claude/settings.overlay.example.json` shows the shape of a local overlay without
  organization names, user paths, or secrets.

## Other clients

- `codex/config.base.toml` is a portable Codex base; it is parser-validated but
  is not wired into runtime generation yet.
- `gemini/mcp.base.json`, `cursor/mcp.base.json`, and
  `windsurf/mcp_config.base.json` contain portable PCTX client definitions.
- `pctx/pctx.base.json` uses executable names resolved by the local `PATH`, rather
  than machine-specific installation paths.

The current `.claude/settings.json` distribution path remains unchanged until a
separate review approves runtime wiring. This keeps the migration reversible while
the generated proposal is validated.

The top-level installer also exposes read-only migration checkpoints:

```sh
./setup.sh --dry-run  # emit all client proposals; no directories or links are changed
./setup.sh --check    # emit the read-only doctor report; exit 1 means findings exist
```

Both modes return before GNU Stow, package installation, directory creation, or
symlink mutation. Running `./setup.sh` without either flag retains the existing install
path and remains a separate, review-gated operation.

Example:

```sh
python3 scripts/config_generate.py \
  ai/config/claude/settings.base.json \
  --overlay ai/config/claude/settings.overlay.example.json
```

Review the JSON output; do not redirect it to a live configuration path.

To build a deterministic, proposal-only bundle for every manifest client (including
Codex TOML), use:

```sh
python3 scripts/config_generate_all.py \\
  --set PCTX_CONFIG=~/.config/pctx/pctx.json \\
  --set USER_NAME=portable-user
```

The command emits a JSON envelope containing each client's format, runtime destination,
and rendered proposal. It never writes the bases, overlays, or runtime files. Pass
`--overlay-dir` explicitly to merge ignored local overlays, or `--client NAME` to limit
the bundle to selected manifest clients.

The unified read-only interface exposes equivalent subcommands:

```sh
python3 scripts/ai_config.py generate --set PCTX_CONFIG=~/.config/pctx/pctx.json --set USER_NAME=portable-user
python3 scripts/ai_config.py diff --runtime-root "$HOME" --client codex
python3 scripts/ai_config.py doctor --root .
```

`diff` reports `match`, `drift`, `missing`, or `invalid-target` with hashes and changed
paths only; it never prints target configuration content or modifies files. Runtime
application, atomic replacement, and backups remain separate review-gated work.

To measure the effective always-loaded guidance chains for repository guidance, Claude,
Codex, and Gemini without changing any files, run:

```sh
python3 scripts/effective_context.py \
  --max-lines 400 \
  --max-words 3000 \
  --max-bytes 20000
```

The JSON report follows line-oriented Markdown imports, resolves the canonical Codex
base and Gemini context settings, deduplicates aggregate files, and reports missing or
out-of-root references. Budget violations return exit status 1; the command is
read-only and does not rewrite the instruction hierarchy.

For a local proposal tree, create an explicit marker and use `stage`:

```sh
mkdir -p /tmp/dotfiles-ai-stage
touch /tmp/dotfiles-ai-stage/.ai-config-staging
python3 scripts/ai_config.py stage \\
  --output-root /tmp/dotfiles-ai-stage \\
  --client codex
```

Staging writes atomically below the marked directory. Existing files are refused by
default; `--replace` creates a sibling `.bak` before replacement. Do not point this
command at a live home-directory configuration tree.

Portable client bases use explicit `${NAME}` markers. Supply replacements with
`--set`; the generator never reads process environment variables implicitly:

```sh
python3 scripts/config_generate.py \
  ai/config/gemini/mcp.base.json \
  --set PCTX_CONFIG=/tmp/pctx.json
```

For a content-safe review against an existing JSON target, use
`--compare-against`; it reports only changed JSON paths and SHA-256 values:

```sh
python3 scripts/config_generate.py \
  ai/config/claude/settings.base.json \
  --overlay ai/config/claude/settings.overlay.example.json \
  --compare-against "$HOME/.claude/settings.json"
```
