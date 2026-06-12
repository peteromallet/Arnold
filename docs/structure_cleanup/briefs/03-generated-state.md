Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

You are a DeepSeek audit subagent reviewing generated state and cache placement.

Top-level generated/local-looking entries include:
.DS_Store, .hypothesis, .import_linter_cache, .pytest_cache, .ruff_cache, .venv,
.desloppify, .megaplan, artifacts, out, input, install.log, finalize.json,
asset_manifest.json, external_workflow_index.json, node_index.json,
template_index.json, version_matrix.json, workflow_index.json, custom_nodes.lock.

Task:
- Classify which are durable tracked source/contracts, which are generated but
  intentionally committed, which are local output/cache and should be ignored or
  moved, and which need more evidence.
- Look at git tracking where helpful.

Return under 400 words:
1. Durable root generated artifacts that probably stay.
2. Generated artifacts that should move under a clear directory.
3. Local/ignored artifacts that should be deleted from this checkout or added to
   .gitignore.
4. Checks needed before acting.
