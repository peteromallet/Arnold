Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: Audit `vibecomfy/runtime/` for deletion-first cleanup.

Context:
- User preference: delete shims/compat files unless there is an extreme reason to keep them.
- Do not edit files. Return findings only.
- Inspect current filesystem state, not assumptions from older docs.

Focus:
- Find runtime files that are dead, duplicate, shadowed by packages, or re-export shims.
- Pay special attention to `eval.py`, `eval_plan.py`, `eval_prompt.py`, and `preview_types.py` versus `runtime/eval/`.
- For each deletion candidate, prove it with import/reference searches.

Output:
- Table: path, delete/migrate/keep, evidence, risk, verification command.
- Keep under 900 words.
