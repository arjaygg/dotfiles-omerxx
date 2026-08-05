Review this PR/diff critically. Check for:
- Logic errors or off-by-one mistakes
- Missing error handling or edge cases that could cause silent failures
- Security issues (injection, auth bypass, data exposure, input validation)
- Performance regressions (N+1 queries, missing indexes, large memory allocations)
- Breaking changes to public interfaces or contracts
- Tests that don't actually cover the changed code paths
- Code that's harder to understand than necessary

Flag each issue with: BLOCKER, WARNING, or NIT. Summarize the overall risk level at the end.
