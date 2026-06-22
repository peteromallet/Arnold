# State Authority Migration

The M3 runtime replaces overwrite-only state authorities with a journal-first,
manifest-coordinate model.  This document explains the new coordinate system,
legacy-alias quarantine, authority-gated resume, and the migration path for old
state authorities.

## Manifest-coordinate cursors

Runtime identity is `(alias, manifest_hash)`:

```python
from arnold.manifest import manifest_coordinate, NodeRef

coord = manifest_coordinate("my-workflow", "sha256:...")
cursor = coord.cursor(node=NodeRef("gate"), reentry_id="resume")
```

`ManifestCursor` (in `arnold.manifest.refs`) is the only cursor accepted by
`arnold.execution.run`.  It pairs a human alias with a cryptographic manifest
hash, so old aliases cannot accidentally resume against a changed workflow
definition.

The kernel's `ReplayCursor` (`arnold.kernel.replay`) is bridged to a
`ManifestCursor` by `arnold.execution.resume.build_resume_manifest_cursor` and
`prepare_resume`.

## Legacy alias quarantine

`prepare_resume` resolves cursors with native-first semantics:

1. If the cursor's `manifest_hash` matches the loaded manifest, use it.
2. Otherwise, consult `legacy_aliases` (a mapping from old hash to
   `LegacyAliasRecord`).
3. If neither resolves cleanly, the outcome is quarantined with a reason such
   as `manifest_hash mismatch`.

Quarantine produces `ResumeOutcome(ok=False, replay_resolution=..., quarantine_reason=...)`
rather than mutating state.  This prevents stale aliases from resuming against
the wrong topology.

## Authority-gated resume

A manifest may declare `AuthorityRequirement` items in its `WorkflowPolicy`:

```python
WorkflowPolicy(
    authority=(
        AuthorityRequirement(authority_id="resume-auth", action="resume"),
    ),
)
```

Before accepting a resume cursor, `LocalJournalBackend._check_authority` asks
`ExecutionRegistries.authorities` to verify the action.  Denied authority
short-circuits to `ExecutionState.QUARANTINED` and emits a `resume_rejected`
event with code `authority_denied`.

Authority is checked before any node executes, so a denied resume cannot mutate
the journal beyond the rejection event.

## Migration path for old state authorities

Old authorities live in modules such as `arnold.pipeline.state`,
`arnold.runtime.state_persistence`, and product-specific resume stores.  The
migration path is:

1. **Read-only reconciliation**: continue writing old state, but do not use it
   as the source of truth.  Reconstruct runnable state from `events.ndjson`.
2. **Cursor conversion**: convert old resume tokens to `ReplayCursor` or
   `ManifestCursor` using `build_resume_manifest_cursor`.
3. **Alias registration**: map old manifest hashes to current hashes via
   `legacy_aliases` in `prepare_resume`.
4. **Authority registration**: port old auth checks to
   `ExecutionRegistries.authorities` handlers.
5. **Deletion**: once all in-flight runs have converted, remove old state
   writes.  See `runtime-salvage-deletion-map.md` for the disposal schedule.

## Files involved

- `arnold/manifest/refs.py` — `ManifestCoordinate`, `ManifestCursor`, `NodeRef`.
- `arnold/kernel/replay.py` — `ReplayCursor`, `resolve_cursor`.
- `arnold/execution/resume.py` — `prepare_resume`, `build_resume_manifest_cursor`.
- `arnold/execution/backend.py` — `_check_authority`, `run_manifest`.
- `arnold/execution/registries.py` — `AuthorityRegistry`, `ExecutionRegistries`.
