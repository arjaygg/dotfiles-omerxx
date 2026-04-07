50 lines → 34 unique
6 errors:
  description: Review code for silent failures, swallowed errors, bad fallbacks, and missing error propagation.
  - `catch {}` or ignored exceptions
  - errors converted to `null` / empty arrays with no context
  ### 4. Error Propagation Issues
  ### 5. Missing Error Handling
  ... +1 more errors
last 15 unique lines:
- graceful-looking paths that make downstream bugs harder to diagnose
### 4. Error Propagation Issues
- lost stack traces
- generic rethrows
- missing async handling
### 5. Missing Error Handling
- no timeout or error handling around network/file/db paths
- no rollback around transactional work
## Output Format
For each finding:
- location
- severity
- issue
- impact
- fix recommendation
[lean-ctx: 233→174 tok, -25%]
