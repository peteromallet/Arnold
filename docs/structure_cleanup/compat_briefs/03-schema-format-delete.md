# Compatibility Layer Audit 03: Schema Format Delete

Working directory: `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Goal: decide whether `vibecomfy/schema/format.py` should be deleted and `format_issue` moved into `schema/validate.py`.

Inspect:
- `vibecomfy/schema/format.py`
- `vibecomfy/schema/validate.py`
- importers in commands/runtime/tests/docs.

Return under 450 words:
1. Keep/move/delete verdict.
2. Required import migrations.
3. Whether `schema.format` is public API or internal helper.
4. Focused tests/commands.
