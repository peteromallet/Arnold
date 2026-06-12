Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Find deletion candidates in the agent/agentic layer only:
`agentic/`, `agents/`, `.agents/`, `.claude/`, `.megaplan/`.

Classify each candidate as:
- safe delete now
- delete only after user approval
- keep

Pay special attention to `__pycache__`, generated evidence, local scheduler
state, and megaplan logs/plans.

Return a concise table with exact paths and rationale. Under 600 words.
