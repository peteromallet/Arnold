Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: Audit only top-level files directly under `vibecomfy/` for deletion-first cleanup.

Context:
- The project is doing a layer-by-layer file-structure cleanup.
- User preference: delete shims/compatibility files unless there is an extreme reason to keep them.
- Do not edit files. Return findings only.
- Ignore already-deleted files in git status; inspect current filesystem state.

Focus:
- Which root `vibecomfy/*.py` files are dead, duplicate, shadowed by packages, generated artifacts, stale compatibility shims, or only referenced by stale docs?
- For every deletion candidate, prove it with live import/reference searches.
- Explicitly separate "safe delete now" from "delete after migration" and "keep".

Output:
- Ranked deletion table: path, evidence, risk, exact follow-up verification command.
- Keep under 900 words.
