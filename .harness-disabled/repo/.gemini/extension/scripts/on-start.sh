#!/usr/bin/env bash
# SessionStart hook: advisory message that dotfiles-guards are active.
# Intentionally minimal — guards are enforced via policies/bash-guards.toml.
echo "[dotfiles-guards] Policy rules active: bash guards, secrets protection, commit safety." >&2
