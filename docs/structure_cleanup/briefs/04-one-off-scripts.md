Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

You are a DeepSeek audit subagent reviewing one-off root scripts and plans.

Root candidates:
_debug_json.py, _debug_normalize.py, _debug_resolver.py, _fix_t6.py,
_regen_templates.py, plan_v2.md, revised_plan.md, finalize.json,
CUSTOM_NODES_AUDIT.md, SECURITY_AUDIT_NOTES.md.

Task:
- Determine whether these are active project surfaces, historical notes,
  development utilities, or disposable scratch files.
- Suggest destinations using existing conventions if possible: scripts/, tools/,
  docs/, artifacts/, out/.
- Be conservative about deletion; prefer move/archive when history may matter.

Return under 400 words:
1. File-by-file recommended action.
2. Destination names if moved.
3. Any references/imports that must be updated.
4. What can be deleted immediately if untracked/ignored.
