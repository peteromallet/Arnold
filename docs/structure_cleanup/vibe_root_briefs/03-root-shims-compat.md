Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: Audit compatibility/shim-looking top-level modules under `vibecomfy/`.

Context:
- User specifically says shims should be deleted wherever possible and kept only in extreme cases.
- Do not edit files.

Focus paths likely worth inspecting:
- `vibecomfy/_workflow_helpers.py`
- `vibecomfy/_helper_resolve.py`
- `vibecomfy/_widget_aliases.py`
- `vibecomfy/_graph_utils.py`
- `vibecomfy/cli_loader.py`
- `vibecomfy/scratchpad_loader.py`
- any root module that mostly re-exports or delegates.

For each:
- Is it a true shim, a public compatibility surface, or an active implementation?
- What imports/tests/docs require it?
- Can callers be migrated to canonical modules now?
- Would deletion break public API or only tests/docs?

Output:
- Delete/migrate/keep decision list with exact import rewrites needed.
- Keep under 900 words.
