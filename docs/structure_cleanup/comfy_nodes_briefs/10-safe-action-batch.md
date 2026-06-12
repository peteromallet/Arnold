# Comfy Nodes Audit 10: Safe Action Batch

Working directory: `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Audit only. Do not edit files.

Synthesize a deletion-first action batch for `vibecomfy/comfy_nodes/` based on current evidence.

Bias:
- delete obvious backups, generated junk, stale shims, dead examples
- move files only if importers can be migrated cleanly
- keep a compatibility path only for a hard public ComfyUI contract

Return:
- exact ordered file operations
- exact import updates
- deferrals and why
- focused verification commands

