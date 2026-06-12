# Comfy Nodes Audit 03: Agent Module Shape

Working directory: `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Audit only. Do not edit files.

Scope: `vibecomfy/comfy_nodes/agent/`.

Question: Is the agent backend package split into the right abstractions?

Inspect large and boundary files:
- `edit.py`
- `session.py`
- `contracts.py`
- `provider.py`
- `routes.py`
- `runtime.py`
- `runtime_code.py`
- `diagnostics.py`
- `audit.py`
- `fixture_provider.py`
- `gates.py`
- `worker.py`

Return:
- files that should be deleted, moved, split, or kept
- whether any modules are compatibility shims or duplicate functionality
- concrete smallest safe cleanup batch
- tests likely to cover it

