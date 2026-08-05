# Cap Step 2 — Workflow Runtime

If a step says read fully and follow step-XX, you read and follow step-XX. No exceptions.

Read the workflow script:

```
Read('ai/skills/cap/cap-workflow.js')
```

Pass it inline to the Workflow tool (inline `script:` is the safe first-invocation pattern):

```
Workflow({
  script: <content of cap-workflow.js>,
  args: {
    feature: "<parsed feature>",
    mode: "<feature|uplift>",
    autonomous: <true|false>,
  }
})
```

**For resume:** Use the `scriptPath` and run ID printed by a prior invocation:

```
Workflow({
  scriptPath: "<scriptPath from prior run>",
  resumeFromRunId: "<wf_xxx_id>",
  args: { feature: "...", mode: "...", autonomous: false }
})
```

Note: the Workflow tool prints `scriptPath` in its result — save it for the user so they can
use `--resume <runId>` in a future invocation without re-reading the script file.

## Next

Read fully and follow **step-04.md** (Post-Run Review).
