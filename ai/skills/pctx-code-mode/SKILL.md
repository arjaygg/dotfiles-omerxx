---
name: pctx-code-mode
description: Instructs the agent to use pctx Code Mode to execute a TypeScript script within a secure Deno sandbox for complex workflows, rather than making multiple sequential tool calls.
triggers:
  - process data
  - batch process
  - run a script
  - complex extraction
  - bulk data
  - use pctx
---

# pctx Code Mode

You have access to the `pctx` MCP gateway. Instead of making sequential tool calls (like reading 20 files one by one, or paginating through an API), you must write a Deno-compatible TypeScript script and execute it via `pctx`.

## When to Use
- You need to loop over multiple files or API endpoints.
- You need to perform complex data extraction or transformation.
- You are hitting context limits by dumping raw data into the chat.

## Instructions
1. **Understand the Goal:** Determine what data needs to be fetched or processed.
2. **Write the Script:** Create a TypeScript file (e.g., `script.ts`). Use the `pctx` provided MCP tools within the script.
3. **Execute via pctx:** Use the `pctx` MCP server to run the script. `pctx` will execute it in a secure sandbox and return only the final results.

### Example Script (`task.ts`)
```typescript
import { mcp } from "pctx";

async function main() {
  // Example of calling an upstream MCP tool through pctx
  const files = await mcp.callTool("filesystem", "list_directory", { path: "./docs" });
  
  let summary = "";
  for (const file of files.entries) {
     if (file.name.endsWith(".md")) {
        const content = await mcp.callTool("filesystem", "read_file", { path: `./docs/${file.name}` });
        // Process content...
        summary += `\nProcessed ${file.name}`;
     }
  }
  
  console.log("Final Summary:", summary);
}

main();
```

4. **Review Output:** The output of the script will be returned to your context. Use it to answer the user's request.
