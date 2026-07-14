---
type: anchor
anchor_type: north_star
slug: repository-strategy-roadmap
title: 'North Star: Repository Strategy Roadmap'
created_at: '2026-07-13T21:35:51.653719+00:00'
---

# North Star: Repository Strategy Roadmap

## End State

Every repository can carry a durable `.megaplan/STRATEGY.md` that is both a
pleasant human strategy document and the authoritative source for a typed
Now / Next / Later portfolio. Stable direction and the living roadmap coexist
without becoming competing authorities: roadmap entries point to real ticket
or epic artifacts, while machine consumers rebuild any JSON view from the
Markdown and the referenced artifacts.

Operators can capture a ticket, give it strategic visibility at any horizon,
promote sufficiently planned work into a distinct epic, and follow both
artifacts through completion with identity and relationship history intact.
Validation and CLI workflows make broken references, duplicate identities,
invalid horizons, and authority drift obvious before automation acts.

## Non-Negotiables

- Typed Markdown is authoritative. JSON and other indexes are deterministic,
  disposable projections and are never independently editable.
- The executable roadmap vocabulary is exactly `ticket` and `epic`.
- Horizon (`Now`, `Next`, `Later`) is independent of artifact type.
- Roadmap identity is `type + ref`. Ticket refs are immutable ticket ULIDs;
  epic refs are canonical initiative/epic identifiers, currently normally the
  initiative slug. Titles are mutable display text, never identity.
- Strategy entries reference artifacts and do not duplicate their full bodies,
  lifecycle status, plans, or completion evidence.
- Ticket-to-epic promotion retains both artifacts, creates a new epic identity,
  and records an explicit supersedes/resolves relationship. A ticket ID is
  never reused as an epic ID.
- Roadmap membership means strategic visibility, not existence: ordinary small
  tickets may remain outside the strategy.
- Existing ticket and initiative artifacts remain readable throughout rollout.

## Explicit Non-Goals

- Replacing tickets or initiatives with embedded strategy entries.
- Building a general project-management suite, arbitrary workflow-item type
  registry, scheduling engine, effort estimator, or cross-repository portfolio.
- Making generated JSON, cached search indexes, display titles, or strategy
  copies of artifact status authoritative.
- Automatically promoting tickets based on size, age, or model judgment.
- Replanning or restructuring unrelated existing initiatives.

## Allowed Temporary Bridges

- Existing ticket `epics` links and store-backed `TicketEpicLink` records may be
  adapted behind one canonical relationship API while the richer promotion
  vocabulary is introduced.
- Legacy ticket filenames without a valid ULID may remain discoverable with
  explicit validation diagnostics; new roadmap references must use valid
  immutable artifact identity.
- A generated projection may be absent or stale during rollout, provided every
  consumer can rebuild it and refuses to treat it as source authority.

## Drift Signals

- A third executable roadmap item type appears.
- A horizon is inferred from whether an item is a ticket or epic.
- Editing JSON changes strategy meaning, or Markdown and JSON require manual
  reconciliation.
- A roadmap entry carries its own actionable body or lifecycle status.
- Promotion deletes a ticket, mutates its ULID, or assigns that ULID to an epic.
- Titles or filenames are used as identity.
- Every ticket is forced into the strategy, turning it into a duplicate backlog.
- CLI convenience becomes the only way to make a valid human-readable edit.
