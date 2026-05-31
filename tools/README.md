# Tools

`tools/` holds repo-maintenance utilities that inspect the codebase but are not
part of the installed megaplan CLI.

Current tool:

- `silent_failure_census.py` scans `megaplan/**/*.py` for silent exception
  handlers and direct `stderr` writes, then classifies them for the M3a cleanup
  policy.

Run tools from the repository root so relative paths and policy allowlists line
up with the checked-out tree:

```bash
python tools/silent_failure_census.py
```
