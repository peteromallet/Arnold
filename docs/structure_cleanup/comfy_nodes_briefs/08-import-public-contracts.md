# Comfy Nodes Audit 08: Import Public Contracts

Working directory: `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Audit only. Do not edit files.

Scope: imports of `vibecomfy.comfy_nodes`.

Question: Which import paths are public ComfyUI contracts and which are internal accidental paths?

Return:
- import graph summary with live importers
- public paths that must be preserved
- private paths that can be moved/deleted after caller migration
- proposed stale-import guard searches/tests

