You are auditing file names in docs/plans/ and docs/historical/.

Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task:
- Identify files whose names are too generic for a historical archive, e.g. plan_v2.md, revised_plan.md, finalize.json.
- Recommend clearer target names only where the rename materially improves navigation.
- Include any reference repairs needed for renamed files.

Constraints:
- Do not edit files.
- Prefer no rename if the old name is referenced by active code and the benefit is minor.
- Output a ranked list of rename candidates with exact old/new paths.
