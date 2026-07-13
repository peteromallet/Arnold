---
type: brief
slug: m4-migration-compatibility
title: Migration and Backward Compatibility
epic: repository-strategy-roadmap
created_at: '2026-07-13T21:35:51.655142+00:00'
---

# Migration and Backward Compatibility

## Outcome

Make the strategy feature safe for repositories with existing tickets,
initiatives, store mirrors, and mixed versions. Migration is inspectable,
idempotent, and non-destructive; invalid legacy identity is surfaced rather
than silently guessed, while generated projections can always be discarded and
rebuilt from current authoritative artifacts.

## Scope

### In scope

- Inventory and classify existing ticket files, including historical filenames
  without ULID prefixes, current `epics` relationship frontmatter, store rows,
  initiative slugs, and absent strategy files.
- Define version negotiation for `.megaplan/STRATEGY.md` and generated
  projections, including upgrade, refusal, rollback, and mixed-version behavior.
- Add dry-run migration/doctor output that reports invalid IDs, ambiguous epic
  refs, duplicate identities, orphan links, stale titles, and projection drift.
- Implement idempotent safe migration for supported legacy cases with backups
  or transactional writes and proof that artifact identity/history is retained.
- Ensure an absent strategy remains valid (feature not adopted) and no command
  forces all existing tickets into a roadmap.
- Add compatibility fixtures spanning file-only and store-backed modes.

### Out of scope

- Inventing ULIDs for ambiguous legacy tickets without an explicit mapping,
  bulk reprioritizing existing work, or migrating every repository on disk.
- Rewriting unrelated initiative layouts or run-state JSON.

## Locked Decisions

- Typed Markdown and artifact identities remain authority after migration;
  generated JSON may be deleted at any time.
- Existing tickets/initiatives are preserved; migration cannot collapse ticket
  and epic identity or delete promotion history.
- Repositories may opt in incrementally, and tickets need not enter the roadmap.
- Ambiguity fails closed with actionable evidence rather than title/filename
  guessing.

## Open Questions for This Sprint

- Determine which legacy non-ULID ticket artifacts are supported as read-only,
  explicitly mapped, or excluded from roadmap eligibility.
- Choose the strategy schema upgrade mechanism and minimum rollback evidence.
- Define store/file reconciliation precedence without elevating generated or
  stale mirrored data into a new authority.

## Constraints

- Migration must be repeatable and safe in dirty worktrees.
- No network dependency for local validation/dry-run.
- File and store backends must preserve their existing public contracts until a
  versioned replacement is proven.
- This sprint is sized to at most two weeks.

## Done Criteria

- A dry run inventories all relevant legacy states and makes no mutations.
- Supported migrations are idempotent, preserve IDs/history, and can be rolled
  back or reconstructed from recorded mappings/backups.
- Unsupported/ambiguous identities block strategic referencing with precise
  diagnostics and no guessed identity.
- Old projections are ignored/rebuilt; changing one cannot change authoritative
  strategy meaning.
- Compatibility tests cover absent strategy, old/new strategy versions,
  non-ULID legacy filenames, orphan relationships, mixed store/file state, and
  repeated migration.

## Touchpoints

- Ticket files/store adapters, strategy schema/projection, initiative resolver,
  CLI doctor/migration surfaces, and fixtures under `tests/`.
- Existing `.megaplan/tickets/` corpus as read-only characterization input.

## Anti-Scope

- Do not bulk-edit the repository's real ticket corpus during test development.
- Do not infer identity from mutable titles or filename slugs.
- Do not turn generated projection timestamps or status copies into authority.
- Do not couple this migration to unrelated `.megaplan/plans` layout changes.
