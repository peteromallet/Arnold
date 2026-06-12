Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: Audit root modules related to models, assets, node packs, registries, fetch, and metadata.

Context:
- Root has `model_assets.py`, `fetch.py`, `metadata.py`, `custom_node_refs.py`, `node_packs*.py`, `index_types.py`, `source_map.py`, etc.
- There are packages `registry/`, `node_packs/`, `nodes/`, and `schema/`.
- Do not edit files.

Focus:
- Which root modules are real public boundaries?
- Which should move under `registry/`, `node_packs/`, `nodes/`, or `schema/`?
- Which are dead or duplicate?
- Identify low-risk delete/move candidates.

Output:
- Ranked action list with import evidence and verification commands.
- Keep under 900 words.
