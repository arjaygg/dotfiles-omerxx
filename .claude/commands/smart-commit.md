# Smart Commit and Push

Analyze the current git changes and intelligently group related modifications into separate commits, then push them to the remote repository.

## Instructions

1. Run `git status` and `git diff` to see all current changes
2. Analyze the changes and identify logical groups based on:
   - Files in the same directory or subdirectory
   - Related functionality (e.g., all documentation changes, all configuration changes)
   - Dependency relationships (e.g., tests that go with implementation files)
   - Similar types of changes (additions, modifications, deletions)

3. For each logical group:
   - Stage the relevant files using `git add`
   - Create a descriptive commit message that:
     - Summarizes the nature of the changes
     - Follows the repository's commit message style (check recent commits with `git log`)
     - Focuses on the "why" rather than just the "what"
   - Include the standard footer:
     ```
     🤖 Generated with [Claude Code](https://claude.com/claude-code)

     Co-Authored-By: Claude <noreply@anthropic.com>
     ```
   - Commit the changes using a HEREDOC format

4. After all commits are created:
   - Run `git status` to verify all changes have been committed
   - Push to the remote repository using `git push`
   - Display the results to the user

## Important Notes

- DO NOT commit files that likely contain secrets (.env, credentials.json, etc.)
- If unclear about how to group changes, ask the user for guidance
- Show the user your grouping plan before making commits
- Use HEREDOC format for commit messages to ensure proper formatting
- Follow the Git Safety Protocol (never force push to main/master, never skip hooks, etc.)
