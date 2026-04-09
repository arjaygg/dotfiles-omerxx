This server provides tools to explore SDK functions and execute SDK scripts for the following services: Serena, Exa, Qmd, Ref, Markitdown, LeanCtx
General:
    - BATCH MULTIPLE TOOL CALLS INTO ONE `execute_typescript` CALL.
    - These tools exists to reduce round-trips. When a task requires multiple tool calls:
        - WRONG: Multiple `execute_typescript` calls, each with one tool
        - RIGHT: One `execute_typescript` call with a script that calls all needed tools
    - Only `return` and `console.log` data you need, tools could have very large responses.
    - IMPORTANT: All tool calls are ASYNC. Use await for each call.
WORKFLOW:
    1. Use the `list_functions` and `get_function_details` tools to discover tools signatures and input/output types.
    2. Write ONE script that calls ALL tools needed for the task and execute that script with `execute_typescript`, no need to import anything, all the namespaces returned by `list_functions` and `get_function_details` will be available globally.