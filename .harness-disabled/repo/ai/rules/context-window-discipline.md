# Context Window Discipline

These rules optimize agent behavior for large context windows (1M tokens).

## Context Anxiety

You have a 1M token context window. Do not take shortcuts, leave tasks incomplete, or reduce output quality due to context concerns. Complete tasks fully.

## Large File Reads

Follow `context-and-compaction.md`: progressively disclose with `ctx_compose`, then focused `task`, `reference`, or `lines` reads; never read every chunk merely because a file is large.

## File Size Awareness

When working on files over 500 lines, consider whether they should be modularized into smaller, focused units. Large files degrade agent edit accuracy.
