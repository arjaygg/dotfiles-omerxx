---
name: ollama
description: Delegates self-contained tasks to a local Ollama model (llama3.2). Use for code explanation, summarization, boilerplate generation, Q&A, and brainstorming without external API cost or privacy exposure. Invoked via /ollama or explicit user request.
triggers:
  - use ollama
  - run ollama
  - local model
  - ask ollama
  - ollama explain
  - ollama generate
  - ollama summarize
  - local llm
  - offline model
  - private model
  - no external api
---

# Ollama Local Subagent

Runs a task against a local Ollama model. No external API calls — fully private, zero cost.

## When to Use

**TRIGGER** when the user's request contains:
- "use ollama" / "ask ollama" / "run ollama"
- "local model" / "local LLM" / "offline"
- "private model" / "no external API" / "cost-conscious"
- Explicit `/ollama` invocation

Good tasks for Ollama:
- Explain or summarize a function, file, or snippet
- General Q&A or brainstorming (no tool access needed)
- Generate boilerplate when the pattern is clear and self-contained
- Quick documentation drafts for a single symbol

**Do NOT use Ollama for:**
- Multi-file architectural changes (use Claude Code)
- Tasks needing MCP tools, ADO, browser, or git (use Claude Code)
- Complex multi-step debugging across the codebase (use Claude Code)

## Default Model

**`llama3.2`** — fast, balanced, good for general + code tasks.

For code-heavy tasks, the user can specify: `qwen2.5-coder:7b`

## Instructions

### 1. Check Ollama is available

```bash
if ! command -v ollama &>/dev/null; then
    echo "Error: ollama is not installed. Install from https://ollama.com"
    exit 1
fi
```

If Ollama is missing, inform the user and stop.

### 2. Collect context

Read the relevant file(s) or code snippets using Read/Glob as needed. Include only what is necessary — avoid dumping entire large files.

### 3. Determine the model

- Default: `llama3.2`
- If the user specifies a model (e.g., "use qwen2.5-coder"), substitute it directly.

### 4. Construct the prompt

Write the prompt to `/tmp/ollama-prompt.txt` to safely handle multiline code and special characters:

```bash
cat > /tmp/ollama-prompt.txt << 'PROMPT_EOF'
You are a helpful coding assistant. Answer concisely and directly.

Task: <user_task>

<code_context_if_any>
PROMPT_EOF
```

Substitute `<user_task>` with the user's request and `<code_context_if_any>` with relevant file content or code snippets (omit the placeholder if there is no context).

### 5. Run Ollama

```bash
ollama run llama3.2 < /tmp/ollama-prompt.txt
```

Replace `llama3.2` with the user-specified model if provided.

### 6. Return output

Display the model's response to the user. If the output is long, summarize or highlight the key points.

## Examples

**User:** "Ollama, explain what this function does: [paste]"
```bash
cat > /tmp/ollama-prompt.txt << 'PROMPT_EOF'
You are a helpful coding assistant. Answer concisely and directly.

Task: Explain what the following function does.

```python
def retry(fn, max_attempts=3):
    for i in range(max_attempts):
        try:
            return fn()
        except Exception as e:
            if i == max_attempts - 1:
                raise
```
PROMPT_EOF
ollama run llama3.2 < /tmp/ollama-prompt.txt
```

**User:** "Ask ollama to generate a Go HTTP handler boilerplate"
```bash
cat > /tmp/ollama-prompt.txt << 'PROMPT_EOF'
You are a helpful coding assistant. Answer concisely and directly.

Task: Generate a minimal Go HTTP handler boilerplate for a JSON REST endpoint.
PROMPT_EOF
ollama run llama3.2 < /tmp/ollama-prompt.txt
```

**User:** "Use qwen2.5-coder to explain this file"
```bash
# Same flow, model overridden:
ollama run qwen2.5-coder:7b < /tmp/ollama-prompt.txt
```

## Model Reference

| Model | Best for |
|-------|----------|
| `llama3.2` | General Q&A, explanation, boilerplate (default) |
| `qwen2.5-coder:7b` | Code-heavy tasks, refactoring suggestions |

Pull a model if not yet downloaded:
```bash
ollama pull llama3.2
ollama pull qwen2.5-coder:7b
```
