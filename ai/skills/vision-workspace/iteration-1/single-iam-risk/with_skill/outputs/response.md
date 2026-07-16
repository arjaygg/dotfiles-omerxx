**Conclusion:** This statement permits privilege escalation: `iam:PassRole` with `Resource = "*"` lets the calling principal pass *any* role in the account to an ECS task, not just the intended task role. Fix: scope `Resource` to the specific task/execution role ARN(s).

**Scope and approach:** Handled inline as a single security-lens review, per the request to stay narrow. No build, deploy, or observability workstream was launched — none of that context bears on a PassRole resource-scoping question.

**Evidence-backed finding:** `iam:PassedToService = "ecs-tasks.amazonaws.com"` constrains *which service* may assume the passed role, but it does not constrain *which role* can be passed — that control lives entirely in `Resource`. With `Resource = "*"`, any principal holding this policy (directly or via an assumed CI/CD execution role) can pass a role far more privileged than an ECS task role was ever meant to have — for example, an administrative role — to a new ECS task, then have that task assume it. This is the standard PassRole-based privilege-escalation pattern, and it is real regardless of how tightly `ecs:RunTask` itself is scoped elsewhere.

**Prioritized action:**
- Replace `Resource = "*"` with the explicit ARN(s) of the intended ECS task/execution role(s), e.g. `arn:aws:iam::<account-id>:role/<ecs-task-execution-role-name>`.
- If multiple environments/roles are legitimately needed, use a scoped wildcard on a naming convention (e.g. `arn:aws:iam::<account-id>:role/ecs-task-*`) rather than a bare `*`, and confirm that pattern cannot match unrelated privileged roles.

**Assumptions / unresolved questions:** Assumes no additional `Condition` block narrows `Resource` elsewhere in the policy (none was supplied); if one exists, re-evaluate against it. This finding stands as read-only analysis — no Terraform change was applied. No other workstream (build, deploy, observability) is warranted for this request.
