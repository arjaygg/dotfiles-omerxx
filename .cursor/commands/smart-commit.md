# Smart Commit and Push

Analyze the current git changes and intelligently split them into **atomic commits**, then push them to the remote repository.

## Instructions

1. Run `git status` and `git diff` to see all current changes
2. Analyze the changes and identify candidate groups based on:
   - Files in the same directory or subdirectory
   - Related functionality (e.g., all documentation changes, all configuration changes)
   - Dependency relationships (e.g., tests that go with implementation files)
   - Similar types of changes (additions, modifications, deletions)

3. Ensure groups are **atomic**:
   - Each commit must represent **one logical change** (smallest sensible unit)
   - If a group contains multiple independent changes, split it further until each commit is atomic
   - Avoid mixing refactors with behavior changes unless inseparable

4. For each atomic group:
   - Stage the relevant files using `git add`
   - Create a descriptive commit message that:
     - Follows **Conventional Commits**: https://www.conventionalcommits.org/en/v1.0.0/
       - Format: `type(scope): summary`
       - Common `type`: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`, `build`, `perf`, `style`, `revert`
       - Use **!** or **BREAKING CHANGE:** (or both) in the body when applicable
     - Follows the repository's commit message style (check recent commits with `git log`)
     - Focuses on the "why" rather than just the "what"
   - Include an **intelligent footer** (trailers at the end of the commit message):
     - If running in **Cursor**, include:
       ```
       🤖 Generated with Cursor
       ```
     - If running in **Claude Code**, include:
       ```
       🤖 Generated with [Claude Code](https://claude.com/claude-code)

       Co-Authored-By: Claude <noreply@anthropic.com>
       ```
     - If unclear which tool is being used, **omit the footer** rather than guessing.
   - Commit the changes using a HEREDOC format

5. After all commits are created:
   - Run `git status` to verify all changes have been committed
   - Push to the remote repository using `git push`
   - Display the results to the user

## Important Notes

- DO NOT commit files that likely contain secrets (.env, credentials.json, etc.)
- If unclear about how to group changes, ask the user for guidance
- Show the user your grouping plan before making commits
- Use HEREDOC format for commit messages to ensure proper formatting
- Follow safe git practices (never force push to main/master, never skip hooks, etc.)
