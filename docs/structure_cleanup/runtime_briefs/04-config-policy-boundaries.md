Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: Audit runtime config/model-policy/local-library boundaries.

Focus files:
- `config.py`, `model_policy.py`, `policy.py`, `metadata.py`,
  `_local_library_yaml.py`, plus root `local_library.py` if needed for context.

Questions:
- Are these files correctly placed?
- Are any duplicates of root or registry modules?
- Are any old compatibility names still kept only for tests?
- What move/delete batch is safe?

Do not edit. Output decisions, evidence, and tests under 900 words.
