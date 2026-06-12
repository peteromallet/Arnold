Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: Audit runtime import coupling and cycles.

Focus:
- Runtime imports from package root modules and other subsystems.
- Other subsystems importing runtime internals.
- Any import paths still pointing to deleted root shims.

Questions:
- Which runtime modules are coupling hotspots?
- Which moves/deletions reduce coupling without behavior changes?
- Any circular import hazards?

Do not edit. Output ranked hotspots under 900 words.
