# Document Pipeline and Harness Plan

**Date:** 2026-07-30

**Status:** Proposed

**Scope:** Reusable user-scoped document-ingestion infrastructure plus the `PerfMngmt_cc` performance-review adapter

## Ownership

This plan lives in the dotfiles project because the reusable `docpipe` harness is user-scoped infrastructure. `PerfMngmt_cc` remains the first project adapter and consumer.

## Objective

Create a repeatable, efficient, and auditable workflow for processing PDFs, Markdown, spreadsheets, and related documents across projects while keeping performance-management policies project-specific.

## Architecture Decision

Use a two-layer design:

1. **User-scoped generic harness:** content hashing, extraction adapters, cache, provenance registry, diagnostics, and search-index integration.
2. **Project-scoped adapter:** input discovery, schemas, roster/entity matching, cycle rules, evidence packets, validation gates, and output linters.

The generic harness must never contain employee-rating policy or project-specific templates. The project must not depend on unversioned absolute paths or personal caches.

## Trigger and Routing Rules

### Explicit triggers

- `docpipe ingest <file>` for one document.
- `docpipe run --cycle <Cycle>` for a configured project run.
- User requests to read, summarize, analyze, or index a binary document.
- Manager-evaluation workflow requests a source scan or employee evidence packet.

### Change triggers

- New or replaced files under configured input globs.
- Content-hash, extractor-profile, schema, OCR-model, or embedding-model changes.
- Late uploads or source-lock discrepancies.

### CI and scheduled triggers

- Validate changed inputs and outputs in pre-commit/CI.
- Optionally run a periodic scan for stale indexes, replacements, and missing artifacts.

### Routing

- PDF/DOCX/image → complexity check, extraction, quality validation, JSON plus Markdown view.
- XLSX/CSV → structured spreadsheet parsing; do not flatten analytical inputs through PDF conversion.
- Markdown/text → hash, normalize, and index directly; no conversion.
- Source code → normal code-search workflow, not document ingestion.
- Repository with `.docpipe.yml` → project adapter; without it → generic personal-document mode.

## Target Pipeline

```text
discover → hash → classify → extract → normalize → validate
         → freeze source-lock → index → build evidence packet
         → human gate → LLM synthesis → deterministic lint
```

### Content-addressed cache

Cache identity must include source bytes, extractor name/version, normalized options, OCR language/model, and schema version. Use SQLite for operational status and a filesystem cache for artifacts. Store timestamps in run metadata, not deterministic artifacts.

### Canonical artifacts

- Original binary is the primary source.
- Structured JSON is the canonical intermediate representation.
- Markdown is a human/search view generated from JSON.
- Every segment/fact/quote must resolve to source hash plus page, row, or block reference.

### Quality gates

Block or flag encrypted, corrupt, empty, garbled, low-confidence, wrong-cycle, duplicate, or unmapped documents. Require visual review for flagged pages. Do not draft while material validation questions remain unresolved.

## Project Deliverables

Proposed project files:

```text
.docpipe.yml
pyproject.toml
uv.lock
tools/document_pipeline/
schemas/document-record.schema.json
tests/document_pipeline/
justfile
```

The project should also create a tracked per-cycle source lock, for example:

```text
Output_Validation_<Cycle>/source-lock.json
```

The source lock records relative path, logical entity, source hash, extraction artifact hash, tool/profile versions, and quality status.

Project-specific components include employee/manager matching, tenure and calibration rules, required evaluation sections, evidence-packet construction, validation-question gates, and manager/conversation-guide linters.

## User Harness Deliverables

Proposed user-scoped components:

```text
~/.local/bin/docpipe
~/.config/docpipe/config.toml
~/.local/share/docpipe/registry.sqlite
~/.cache/docpipe/<security-scope>/<cache-key>/
```

Capabilities: `doctor`, version checks, generic PDF/Office/image adapters, content-addressed cache, dry-run garbage collection, project-aware namespaces, local-only defaults, and one batched search-index refresh per run.

Restricted documents must use project-scoped indexes/cache permissions. Do not place all projects into one unscoped global collection.

## Immediate Remediation

1. Replace the `convert_to_markdown` / `liteparse` / `lit` ambiguity with one `docpipe` contract.
2. Replace filename/mtime extraction tracking with SHA-256 source manifests.
3. Upgrade the global ingest wrapper from slug-overwrite/text-only behavior to namespaced JSON-plus-Markdown artifacts.
4. Run index update/embed once per batch, not once per source file.
5. Change the existing agent-per-PDF extraction pattern to deterministic extraction first and agent fallback only for difficult pages.
6. Add explicit project Python allowlisting to `.gitignore` before adding pipeline code.

## Phased Implementation

## Step 1 — Foundation
**Files:** `.docpipe.yml`, `pyproject.toml`, `uv.lock`, `tools/document_pipeline/`, `.gitignore`

**Accepts:** The project can scan configured inputs, calculate hashes, detect additions/replacements, verify tool versions, and report a machine-readable plan without drafting evaluations.

## Step 2 — Extraction and provenance
**Files:** `tools/document_pipeline/`, `schemas/document-record.schema.json`, `tests/document_pipeline/`, `Output_Validation_<Cycle>/source-lock.json`

**Accepts:** PDF, Markdown, and spreadsheet fixtures produce deterministic artifacts with source/page/row provenance and quality statuses; unchanged inputs reuse the cache.

## Step 3 — Indexing and evidence packets
**Files:** `.qmd/` configuration or project index wiring, `tools/document_pipeline/`, manager-evaluation skill integration

**Accepts:** Search is project-scoped; one changed source updates only affected artifacts; employee packets contain required sources, citations, gaps, and contradictions.

## Step 4 — Workflow and CI integration
**Files:** `prompt.md`, `AGENTS.md`, relevant `.claude/skills/*`, `justfile`, CI configuration

**Accepts:** The documented workflow invokes the same command contract, unresolved validation questions block drafting, and deterministic output linters remain green.

## Step 5 — Security and operations
**Files:** user-scoped `docpipe` configuration and diagnostics; project security tests

**Accepts:** Raw source text is absent from logs, untrusted document instructions are treated as data, restricted indexes are isolated, and deletion/garbage-collection behavior is testable.

## Non-Goals for Initial Version

- Do not introduce DVC, Snakemake, Dagster, or Git LFS yet; the current corpus is small enough for a Python CLI, SQLite manifest, and local cache.
- Do not make an LLM the default PDF extractor.
- Do not store operational caches, embeddings, credentials, or absolute user paths in Git.
- Do not couple this manual file workflow to Compass.

## Acceptance Metrics

- Second unchanged run performs zero extraction work and zero new embeddings.
- One changed source rebuilds only that source and dependent packets.
- Silent replacement under the same filename is detected.
- Identical inputs, tool versions, profiles, and schemas produce byte-identical normalized artifacts.
- Every evidence item resolves to a source hash and location.
- Cross-project searches cannot return restricted documents by default.
- Final evaluation and conversation-guide linters remain deterministic and green.
