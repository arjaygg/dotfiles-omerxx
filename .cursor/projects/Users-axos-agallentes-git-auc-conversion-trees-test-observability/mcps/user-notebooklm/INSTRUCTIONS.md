NotebookLM MCP - Access NotebookLM (notebooklm.google.com).

**Auth:** If you get authentication errors, run `nlm login` via your Bash/terminal tool. This is the automated authentication method that handles everything. Only use save_auth_tokens as a fallback if the CLI fails.
**Account Switching:** To switch Google Accounts for the MCP server, run `nlm login switch <profile>` in Bash. The MCP server instantly uses the active default profile.
**Confirmation:** Tools with confirm param require user approval before setting confirm=True.
**Studio:** After creating audio/video/infographic/slides, poll studio_status for completion.

Consolidated tools:
- source_add(source_type=url|text|drive|file, url=..., document_id=..., text=..., file_path=...): Add any source type
- studio_create(artifact_type=audio|video|...): Create any artifact type
- studio_revise: Revise individual slides in an existing slide deck
- download_artifact(artifact_type=audio|video|...): Download any artifact type
- note_create/note_list/note_update/note_delete: Manage notes in notebooks