You are auditing tracked docs for deletion, not just relocation.

Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task:
- Identify docs that are stale duplicates, superseded by newer docs, broken stubs, old generated evidence, or low-value remnants that should be deleted rather than moved.
- Distinguish historical records worth keeping from junk.
- Exclude docs/structure_cleanup/* from deletion unless it is transient scratch within that directory.

Constraints:
- Do not edit files.
- Do not recommend deleting authored history just because it is old; recommend deletion only for duplicate/stale/junk.
- Output exact delete candidates with safer alternative if move/keep is better.
