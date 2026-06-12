Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Audit `.megaplan/` at a classification level. It is large on disk, but only a
small subset is tracked. Do not propose deleting active local state unless you
can distinguish it from committed artifacts.

Use `git ls-files .megaplan` and ignored status. Return:

1. Tracked `.megaplan` surfaces by category.
2. Ignored/local `.megaplan` surfaces by category.
3. What can be documented as local runtime state.
4. What, if anything, should move to `docs/` or another committed surface.

Keep the answer under 600 words.
