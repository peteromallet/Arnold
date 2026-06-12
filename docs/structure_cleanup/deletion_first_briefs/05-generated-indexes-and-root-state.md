You are auditing root-level generated indexes and state files.

Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task:
- Evaluate root files: `template_index.json`, `workflow_index.json`, `external_workflow_index.json`, `node_index.json`, `version_matrix.json`, `asset_manifest.json`, `custom_nodes.lock`, `.env.example`, `this.env`.
- Decide which belong at root, which should move, which are generated junk that can be deleted, and which must be kept despite being generated.

Constraints:
- Do not edit files.
- Do not read/print secret values from `this.env`; classify by path only.
- Output delete/move/keep with evidence from code/tests/docs references.
