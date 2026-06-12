# Comfy Nodes Audit 02: Web Assets Delete-First

Working directory: `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Audit only. Do not edit files.

Scope: `vibecomfy/comfy_nodes/web/`.

Focus on obvious source-tree debris and asset ownership:
- `.bak` files
- generated contract files
- `.gitkeep`
- `package.json`
- large bundled JS files
- `astrid_logo.png`

Return:
- which files are generated, backups, live source, or static assets
- which can be deleted immediately
- whether any generated files should move to `out/`, `docs/`, or a generator output path
- exact import/reference evidence
- verification commands

