# Compatibility Layer Audit 05: Schema Package Shape

Working directory: `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Goal: assess remaining schema-package files that look like old shims or outdated plan assumptions.

Inspect:
- `vibecomfy/schema/`
- `docs/plans/revised_plan.md` Unit 11
- tests importing schema modules.

Questions:
- Are `factory.py` and `registry.py` real live modules or obsolete leftovers?
- Are there small modules that should be moved/deleted in the same safe pass?
- Should this pass limit itself to `format.py` and diagnostics?

Return under 500 words:
1. Safe actions now.
2. Explicit deferrals and why.
3. Verification commands.
