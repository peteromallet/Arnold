# Comfy Nodes Audit 04: Stages Package

Working directory: `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Audit only. Do not edit files.

Scope: `vibecomfy/comfy_nodes/stages/`.

Question: Does `stages/` contain coherent stage implementations, or are there files that belong under `agent/`, `web/`, or elsewhere?

Inspect all files in `stages/` and their importers.

Return:
- role of each stage module
- live importers and public contracts
- deletion/move opportunities
- whether `stages/` should remain a first-class package
- focused tests/commands

