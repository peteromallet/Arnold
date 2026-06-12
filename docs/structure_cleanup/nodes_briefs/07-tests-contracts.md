# Nodes Layer Audit 07: Tests and Contracts

Working directory: `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Goal: identify which tests encode the current node shim contract and how they should change under deletion-first policy.

Inspect:
- `tests/test_node_shims.py`
- `tests/test_generated_node_wrappers.py`
- `tests/test_api_surface.py`
- `tests/test_templates_module.py`
- generated wrapper tests and characterization goldens.

Return:
1. Tests that currently require keeping `vibecomfy.nodes.<pack>`.
2. Tests that would need to change if shims are deleted.
3. Whether tests are protecting intentional public API or accidental compatibility.
4. Minimal focused test command for this layer.
Keep the answer under 500 words.
