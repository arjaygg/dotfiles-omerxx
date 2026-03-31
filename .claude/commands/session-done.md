# Session Done — Mark Current Session as Complete

Mark the current session as complete so `/session-picker` knows to skip it.

## Instructions

1. Check if `plans/` directory exists. If not, inform user there's nothing to mark.

2. Update or create `plans/session-handoff.md` with `status: complete`:
   - If the file exists, add or update the `status:` field to `complete`
   - If the file doesn't exist, create a minimal one:
     ```
     # Session Handoff — <current date and time>
     status: complete

     **Branch:** <current branch>
     **Last commit:** <latest commit oneline>

     ---
     *Marked complete by /session-done.*
     ```

3. Check for uncommitted changes:
   - If dirty files exist, warn the user: "There are uncommitted changes. Commit or stash before closing?"
   - List the dirty files
   - Ask if they want to proceed anyway

4. Check if a PR exists for the current branch:
   - If yes and merged: confirm session is done
   - If yes and open: note "PR still open — marking session done but PR remains active"
   - If no PR: note "No PR found — branch work may need a PR before it's truly done"

5. Confirm: "Session marked as complete. `/session-picker` will now skip this session."

## Arguments

- `$ARGUMENTS` — optional:
  - `abandon` — mark as `status: abandoned` instead of `complete`
  - `force` — skip the uncommitted changes warning
