Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: Audit import graph coupling caused by top-level `vibecomfy/*.py` modules.

Context:
- File organization should reflect abstraction boundaries.
- Root modules that create circular imports or cross-layer coupling are high-priority cleanup candidates.
- Do not edit files.

Focus:
- Find root modules imported by many subsystems.
- Identify cycles or suspicious cross-boundary imports.
- Recommend the smallest structure changes that reduce coupling.
- Deletion preferred over shims where feasible.

Output:
- Coupling hotspots table: root module, importers, problem, recommended action, risk.
- Keep under 900 words.
