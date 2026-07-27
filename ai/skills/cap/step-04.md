# Cap Step 4 — Post-Run Review

If a step says read fully and follow step-XX, you read and follow step-XX. No exceptions.

After either runtime completes, if `autonomous` is **false** and `advisor` is available:

Call `advisor()` with the workflow result for final sanity check:
- All 7 phases completed? (check `result.blocked` — false = success)
- No CRITICAL/HIGH findings remaining? (`result.criticalHighRemaining === 0`)
- Tests count reasonable for scope? (`result.testsCount`)
- Plan acceptance criteria met?

Report the advisor's verdict to the user.

If `advisor` is unavailable, perform the same sanity check yourself and report the verdict.

If `autonomous` is **true** and the Workflow runtime was used, the workflow's Finalize agent
already sent a PushNotification. Skip the advisor call and report the result summary directly.

If `autonomous` is **true** in portable runtime, do not attempt PushNotification unless the host
agent explicitly provides it.

## Red Flags

- A run is reported as "done" while `result.blocked` is true or unchecked — *checkable*: was `result.blocked` explicitly read and shown to be `false` before reporting success?
- `criticalHighRemaining` is nonzero but the run is reported clean.
- `advisor()` was skipped for a non-autonomous run even though `advisor` was available.
- `PushNotification` is called from the portable runtime without the host agent explicitly providing it.

## Next

Read fully and follow **step-05.md** (Report to User).
