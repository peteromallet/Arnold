# Package Layer Audit 03: Porting Subsystem

Audit `vibecomfy/porting/` and its subpackages.

Questions:
- Which subdirs are source, generated cache, layout/edit/widget helpers, or fixtures?
- Are there stale caches or snapshots that should move/ignore?
- Are package-level docs/READMEs missing for a complex subsystem?
- What imports/tests prevent moving modules?

Do not suggest behavior refactors as safe structure cleanup.
