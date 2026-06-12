Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: Audit tests/docs contracts that constrain cleanup of root `vibecomfy/*.py` files.

Context:
- We want aggressive deletion/moves but need to know real contracts versus stale references.
- Do not edit files.

Focus:
- For likely root cleanup candidates, identify tests/docs/examples that must be updated.
- Distinguish live tests from historical docs and cleanup evidence.
- Identify any `known_failures.txt` entries tied to root paths.
- Identify public import examples in docs/recipes that should remain stable.

Output:
- Contract map: root path, live contract refs, stale/historical refs, recommended cleanup strategy.
- Keep under 900 words.
