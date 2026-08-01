# 0015 — Headroom runs per-session via wrapper; Codex connects direct

**Status:** Accepted
**Date:** 2026-08-01
**Supersedes:** `0013-context-routing-ownership.md` §2 (persistent provider proxy) for Codex; acceptance item "Codex retains the Headroom provider proxy" in `plans/specs/codex-context-hardening.md`

## Context

- Headroom was upgraded 0.24.0 → 0.33.0 (see `plans/decisions.md` 2026-08-01). The running proxy
  serves Claude on port 8788, launched per-session via the `hclaude` zsh alias
  (`headroom wrap claude`) — it is not a persistent daemon.
- The persistent-proxy model is unachievable on this host: Docker is unavailable and the
  Python-service installer requires a missing `~/.bashrc` (noted in `plans/decisions.md`
  2026-07-17).
- No `hcodex` alias exists; nothing launches Codex through Headroom. The Codex
  `[model_providers.headroom]` block pointed at port 8787, which nothing serves.
- 0013 §2 assumed "one persistent provider proxy" shared by all clients. That premise no longer
  holds.

## Decision

1. Codex connects directly to OpenAI — `model_provider` and `[model_providers.headroom]` are
   removed from the tracked `.codex/config.toml` and `ai/config/codex/config.base.toml`, and the
   startup/hardening tests assert their absence.
2. Claude keeps proxying through Headroom (`ANTHROPIC_BASE_URL=http://127.0.0.1:8788` +
   `hclaude` wrapper). Headroom 0.33.0 auto-detects `lean-ctx` as the context tool, so no alias or
   env changes were required for the upgrade.
3. If Codex proxying is wanted later, implement it via `~/.config/dotfiles-ai/codex.overlay.toml`
   plus a `config_generate` live-write step — which decision 0012 currently scopes out — rather
   than re-adding machine-specific provider state to tracked config.

## Consequences

- 0013 §1 and §3–§5 are unaffected: LeanCtx still exclusively owns content compression, and the
  shared classifier/gate contract is unchanged.
- `scripts/test_codex_pctx_startup.py` and `scripts/test_headroom_hardening.py` now pin the
  absence of project-local provider settings instead of their presence.
- Codex traffic is no longer compressed/metered by Headroom; only Claude sessions are.
