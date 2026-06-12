Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: audit root index/manifest files associated with templates and corpus.

Focus files:
- `template_index.json`
- `workflow_index.json`
- `external_workflow_index.json`
- `node_index.json`
- `asset_manifest.json`
- `version_matrix.json`
- `custom_nodes.lock`

Use `rg -n` for each filename in code/docs/tests.

Do not edit files.

Questions:
1. Which files are generated but intentionally committed?
2. Which must stay at repo root because code/tests assume paths?
3. Is documentation adequate?
4. Are any safe .gitignore or README clarifications needed?

Return a table and safe-first recommendation.
