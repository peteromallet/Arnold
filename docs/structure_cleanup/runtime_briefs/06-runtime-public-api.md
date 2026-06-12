Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: Identify runtime public API constraints.

Context:
- `vibecomfy.__init__` lazily exposes runtime `run`, `run_sync`,
  `run_embedded`, and `run_embedded_sync`.
- Cleanup should not break documented public imports, but internal clutter should not survive as fake API.

Focus:
- Inspect docs, recipes, tests, and `runtime/__init__.py`.
- Which runtime modules/classes/functions are public?
- Which flat module imports are accidental/internal and can be migrated?

Do not edit. Return keep/move/delete constraints under 900 words.
