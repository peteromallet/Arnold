# Porting Deep Audit 10 — Safe Action Batch

Work from repo root `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Goal: synthesize the safest next cleanup batch for `vibecomfy/porting` after the previous shim deletions.

Assume already deleted:
- old `vibecomfy.porting.edit_*` shims
- old `uid/scope/slot_codec/widget_aliases/widget_schema/wrapper_*` root duplicates
- `vibecomfy/router_rules.py`

Find the next batch that is actually safe.

Questions:
1. What is the highest-confidence next deletion/move batch?
2. What should explicitly not be touched yet?
3. What commands prove the batch did not break behavior?
4. What status docs should be updated?

Return a short prioritized action plan.

Do not edit files.
