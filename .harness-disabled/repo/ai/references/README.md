# References

Standing, project-wide reference material that skills and agents point to instead of restating
inline. Distinct from `ai/rules/` (behavioral defaults) and `ai/skills/` (triggered procedures):
files here are facts and bars to apply, not instructions to follow on their own.

- `definition-of-done.md` — the standing Correctness/Quality/Integration/Documentation/
  Ship-readiness bar applied to every worker return, on top of that task's own acceptance criteria.

Symlinked into `.claude/references` by `setup.sh` so Claude Code sessions can resolve it at a
stable path regardless of which repo directory (or worktree) they were started from.
