# Nodes Layer Audit 03: Ready Template Blast Radius

Working directory: `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Goal: assess whether migrating ready templates from `vibecomfy.nodes.<pack>` to `vibecomfy.nodes._generated.<pack>` is reasonable in this cleanup.

Inspect:
- `ready_templates/**/*.py`
- `template_index.json`
- `tests/characterization/goldens/emitter/*.golden`
- template/emitter code that writes node imports
- any tests that assert import text.

Questions:
- How many ready templates import public node shims?
- Would changing imports alter intended public authoring API?
- Would regenerating templates be required?
- Is the blast radius acceptable for a deletion-first cleanup pass?

Return:
1. Recommended action: migrate now, defer, or keep as public contract.
2. Evidence count or examples for blast radius.
3. Tests/goldens likely to fail.
4. Smallest safe action batch.
Keep the answer under 500 words.
