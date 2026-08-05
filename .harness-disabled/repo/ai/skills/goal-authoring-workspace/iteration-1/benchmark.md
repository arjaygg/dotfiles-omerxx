# Skill Benchmark: goal-authoring

**Model**: <model-name>
**Date**: 2026-07-16T14:38:46Z
**Evals**: 0, 1, 2 (1 runs each per configuration)

## Summary

| Metric | With Skill | Without Skill | Delta |
|--------|------------|---------------|-------|
| Pass Rate | 93% ± 12% | 67% ± 58% | +0.27 |
| Time | 0.0s ± 0.0s | 0.0s ± 0.0s | +0.0s |
| Tokens | 0 ± 0 | 0 ± 0 | +0 |

## Notes

- eval-bootstrap-new-project is the only eval where the two configurations diverge sharply (with_skill 0.8 vs without_skill 0.0). Without the skill, the agent invented its own conventions entirely: YAML front-matter instead of the required heading list, a 'Context' heading not in the spec, no goals/00-index.md, no plans/ directory at all, and a self-authored goals/validate.sh instead of scripts/validate_goals.py. This is the eval that most directly demonstrates the skill's value — the other two evals (add-goal-to-existing-index, fix-malformed-goal) both scored 1.0 in both configurations, meaning they don't discriminate between with/without skill for this run and mainly validate that the skill doesn't regress already-good behavior.
- The without_skill pass_rate stddev (0.5774) looks like high variance but is actually a bimodal artifact of only 3 evals: two runs scored 1.0 and one scored 0.0. It should not be read as 'inconsistent performance' in the statistical sense — it reflects one categorically different eval (bootstrap-new-project), not noisy grading.
- with_skill's only failure this iteration was eval-bootstrap-new-project's active_context_points_at_goal expectation: plans/active-context.md was created from the skeleton template but the goal:/status:/focus: pointer block was never filled in. This is a real gap worth addressing in the skill (e.g. an explicit reminder to populate the pointer block immediately after creating a new active goal), not a grading artifact.
- eval-add-goal-to-existing-index's with_skill validator expectation was initially graded from the agent's own reconstructed report rather than direct re-execution; this was resolved during this grading pass by directly re-running scripts/validate_goals.py against the copied output project and confirming exit 0. Both add-goal and fix-malformed-goal validator expectations across both configurations are now backed by direct re-execution, not just self-reported transcript evidence.
- runs_per_configuration in metadata was corrected from the aggregation script's default value of 3 to the actual value of 1 — only a single run was executed per (eval, configuration) pair in this iteration. Timing and token metrics (time_seconds, tokens, tool_calls) are all 0 for every run because no timing.json was captured: the with/without-skill subagents communicated their results via teammate chat rather than a tracked spawned-task mechanism, so no total_tokens/duration_ms notification was ever received. This is a known gap, not a silent omission — a future iteration should capture timing via a task-tracked spawn mechanism if time/token comparisons are wanted.