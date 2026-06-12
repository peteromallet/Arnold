# Dead Module Audit 07: Object Info JSON Snapshots

Audit stale-looking JSON snapshots under `vibecomfy/porting/object_info/` versus
`vibecomfy/porting/cache/object_info/`.

Check consumers, tests, docs, and generation pipeline.

Return whether any JSON files can be deleted safely, or defer with reason.
