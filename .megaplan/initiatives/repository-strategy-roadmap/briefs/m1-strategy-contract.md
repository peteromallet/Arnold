---
type: brief
slug: m1-strategy-contract
title: Typed Strategy Contract and Validator
epic: repository-strategy-roadmap
created_at: '2026-07-13T21:35:51.654281+00:00'
---

# Typed Strategy Contract and Validator

## Outcome

Define and implement the authoritative `.megaplan/STRATEGY.md` contract,
parser, validator, and deterministic machine projection. A human can edit the
strategy as ordinary Markdown, and automation can recover a typed repository
direction plus a Now / Next / Later portfolio without consulting an
independently editable data file.

## Scope

### In scope

- Specify one versioned Markdown grammar for stable direction (mission,
  principles, architecture direction, constraints, non-goals) and living
  `Now`, `Next`, and `Later` roadmap sections.
- Model each roadmap entry with `type`, `ref`, and mutable display `title`.
  Permit only `ticket` and `epic`; derive horizon from section placement.
- Define identity as `(type, ref)`, reject duplicate identity across horizons,
  validate ticket ULIDs and canonical epic/initiative identifiers, and resolve
  referenced artifacts without copying their bodies or lifecycle statuses.
- Add typed in-memory contracts, source-location-aware diagnostics, parser and
  serializer behavior, and a versioned deterministic JSON projection that is
  explicitly rebuildable from Markdown plus artifact lookup.
- Establish missing-reference, stale-title, malformed-Markdown, duplicate-item,
  and unsupported-version behavior with focused unit and golden tests.
- Provide an example/template that remains readable without tooling.

### Out of scope

- Ticket/epic promotion mutations, broad CLI ergonomics, legacy migration, or
  adopting a real Arnold strategy file; later milestones own those concerns.
- Cross-repository portfolio aggregation, scheduling, estimation, or arbitrary
  roadmap item types.

## Locked Decisions

- `.megaplan/STRATEGY.md` typed Markdown is the sole strategy authority.
- JSON is generated/rebuildable and never independently editable.
- Executable roadmap types are exactly `ticket` and `epic`.
- `Now` / `Next` / `Later` is orthogonal to type.
- Identity is `type + ref`; ticket refs are immutable ULIDs, epic refs are
  canonical initiative/epic identifiers (normally initiative slugs), and title
  is display-only.
- Entries reference artifacts and must not duplicate artifact bodies or status.

## Open Questions for This Sprint

- Choose the narrowest Markdown block grammar that supports lossless,
  unsurprising human edits and precise diagnostics.
- Decide the projection path/schema version and whether stale display titles
  warn or normalize, without making titles identity.
- Decide which broken references are hard validation errors versus explicitly
  permitted transitional warnings; automation must fail closed on ambiguity.

## Constraints

- Preserve existing generic Markdown artifact helpers and canonical
  `megaplan-initiatives-v1` layout rather than introducing another parser stack
  without evidence.
- Parser and validation must be deterministic, side-effect free at the core,
  UTF-8 safe, and testable without a database or network.
- Never infer artifact state from copied roadmap fields.
- This sprint is sized to at most two weeks of skilled engineering work.

## Done Criteria

- A versioned strategy contract and typed model exist with explicit authority
  documentation.
- Valid typed Markdown round-trips without semantic loss; malformed and
  duplicate entries produce stable source-located diagnostics.
- Ticket ULID and epic identifier validation and repository resolution are
  covered by positive and negative tests.
- A projection can be deleted and reproduced byte-for-byte (or canonically
  equivalently) from authoritative inputs; editing only the projection cannot
  alter parsed strategy meaning.
- Tests prove horizon/type independence and reject a third executable type.
- No strategy entry schema includes a second copy of ticket/epic body or status.

## Touchpoints

- `.megaplan/STRATEGY.md` convention and documentation.
- `arnold_pipelines/megaplan/artifacts.py`, `layout.py`, and a focused strategy
  package/module.
- Initiative/ticket lookup helpers and new strategy parser/validator/projection
  tests under `tests/arnold_pipelines/megaplan/`.

## Anti-Scope

- Do not replace tickets, initiatives, or their storage backends.
- Do not add document/investigation/idea/action as executable item types.
- Do not make JSON, filename, title, or ordering a hidden identity source.
- Do not refactor unrelated status or run-state projections.
