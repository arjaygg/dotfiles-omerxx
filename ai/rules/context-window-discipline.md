# Context Window Discipline

These rules optimize agent behavior for large context windows (1M tokens).

## Context Anxiety

You have a 1M token context window. Do not take shortcuts, leave tasks incomplete, or reduce output quality due to context concerns. Complete tasks fully.

## Large File Reads

The Read tool has a 2,000-line hard limit per call. When reading large files, first check the line count. If the file exceeds 2,000 lines, use `offset` and `limit` parameters to read the entire file in chunks.

## Subagent Delegation

Aggressively offload online research, documentation lookups, codebase exploration, and log analysis to subagents. This prevents large tool outputs from spiking main context usage. When about to read logs or large outputs, defer to a subagent.

When spawning a subagent, include a specific "why" in the prompt — not just what to search, but why that information is needed. This produces targeted, non-overlapping results.

## File Size Awareness

When working on files over 500 lines, consider whether they should be modularized into smaller, focused units. Large files degrade agent edit accuracy.
