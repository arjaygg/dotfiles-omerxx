# Progress: Hook Correctness Fixes

## Done
- [x] Validate all 26 hooks via autoresearch (6 bugs found)
- [x] Web research on hook output channel semantics + JSON block pattern
- [x] Create implementation plan (`plans/tranquil-floating-scone.md`)
- [x] Step 1: Fix hook_exit_code() inversion + add hook_block() in hook-metrics.sh
- [x] Step 2: Migrate PreToolUse blocking hooks to JSON structured output
  - [x] pre-tool-gate.sh
  - [x] check-agent-parallelism.sh
  - [x] plan-scope-gate.sh
  - [x] edit-without-read.sh
- [x] Step 3: Fix PostToolUse hooks — stderr → stdout, exit 2 → exit 0
  - [x] bash-output-guard.sh
  - [x] pctx-batch-tracker.sh
  - [x] post-task-fence.sh
  - [x] post-tool-handler.sh (+ remove dead BATCH CHECK block)
- [x] Step 4: Fix plans-healthcheck.sh HOOKS HEALTH gate + instructions-loaded.sh server list + serena-tool-priority.sh regex
- [x] Step 5: Smoke-test all key paths, commit (84e771d), push branch
- [x] hook-config.yaml: update comments to corrected semantics

## In Progress
- [ ] Step 7: Open validation session in a fresh Claude Code instance to exercise hooks end-to-end
