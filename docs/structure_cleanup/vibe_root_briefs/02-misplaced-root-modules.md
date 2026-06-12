Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: Audit top-level `vibecomfy/*.py` files that earn a place in the package but not at the package root.

Context:
- Goal is a self-organizing structure where root files are broad public boundaries; implementation details should live under subsystem packages.
- User accepts moving files and updating imports.
- Do not edit files. Return recommendations only.

Focus:
- Which root modules belong under `_compile/`, `runtime/`, `registry/`, `loader/`, `nodes/`, `porting/`, `schema/`, `testing/`, `comfy_nodes/`, or another existing package?
- For each candidate move, inspect current imports and likely public API impact.
- Avoid cosmetic moves with high test/doc churn unless the current placement is clearly misleading.

Output:
- Move-candidate table: old path, proposed path, why, importing files, risk, tests to run.
- Keep under 900 words.
