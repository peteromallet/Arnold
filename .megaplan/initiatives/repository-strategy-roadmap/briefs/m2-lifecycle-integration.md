---
type: brief
slug: m2-lifecycle-integration
title: Ticket and Epic Lifecycle Integration
epic: repository-strategy-roadmap
created_at: '2026-07-13T21:35:51.654610+00:00'
---

# Ticket and Epic Lifecycle Integration

## Outcome

Integrate strategy references with the real ticket and initiative lifecycle so
tickets can enter or leave strategic visibility, and a ticket can be promoted
to a separately identified epic while both artifacts and their durable
supersedes/resolves relationship remain intact across file and store backends.

## Scope

### In scope

- Build on M1's typed strategy and artifact resolver contract.
- Define one canonical relationship vocabulary/API for ticket-to-epic links,
  including ordinary association, `resolves_on_complete`, and promotion's
  supersedes/resolves semantics.
- Implement promotion as creation/reuse of a genuinely matching initiative with
  a new canonical epic identifier, never a ticket ULID reused as epic identity.
- Retain the source ticket, record relationship provenance, and define whether
  a strategically visible roadmap entry changes from ticket to epic while the
  relationship preserves discoverability of the original ticket.
- Reconcile file frontmatter (`epics`) with store-backed `TicketEpicLink` and
  epic-completion auto-address behavior behind a consistent contract.
- Define lifecycle validation for missing, dismissed, addressed, completed,
  superseded, duplicate, and conflicting references without copying status into
  the strategy.
- Add end-to-end tests for tickets outside the roadmap, tickets added to any
  horizon, promotion, relationship replay, and epic completion.

### Out of scope

- Automated/model-triggered promotion, arbitrary hierarchy, cross-repo links,
  or deleting/merging historical ticket artifacts.
- Full CLI authoring UX and legacy corpus migration; later milestones own them.

## Locked Decisions

- Roadmap inclusion is optional strategic visibility; small tickets may remain
  outside `.megaplan/STRATEGY.md`.
- Promotion retains both artifacts and records supersedes/resolves; it never
  mutates or reuses the ticket ULID as the epic identifier.
- The epic ref is the canonical initiative/epic identifier, normally the
  initiative slug; title is not identity.
- Strategy never becomes the status authority for either artifact.

## Open Questions for This Sprint

- Select the canonical on-disk relationship representation and compatibility
  adapter for current `epics` frontmatter and `TicketEpicLink` rows.
- Define idempotency and collision behavior when promotion is retried or a
  matching initiative already exists.
- Decide roadmap transition behavior on promotion (replace, retain with an
  explicit relationship view, or require operator choice) while preventing two
  executable entries from accidentally representing the same intended work.

## Constraints

- Preserve existing open/addressed/dismissed ticket semantics and automatic
  addressing for resolving epic links.
- File-only and configured-store modes must agree on identity and relationship
  meaning, with rollback-safe writes or explicit reconciliation diagnostics.
- Reuse initiative search before creation; no duplicate initiatives.
- This sprint is sized to at most two weeks.

## Done Criteria

- Promotion always yields distinct ticket and epic IDs and retains the ticket.
- Relationship data is queryable from both artifacts' supported read surfaces
  and remains stable after reload/rebuild.
- Retried promotion is idempotent or fails with a precise actionable conflict;
  it never creates silent duplicate initiatives.
- Epic completion addresses only tickets explicitly marked resolves-on-complete.
- Strategy validation resolves current artifact state dynamically and never
  relies on copied roadmap status.
- File/store contract and end-to-end lifecycle tests cover success, retry,
  partial failure/reconciliation, missing refs, and tickets not on the roadmap.

## Touchpoints

- `arnold_pipelines/megaplan/tickets/core.py`, `tickets/files.py`, ticket schemas,
  store protocols/adapters, and contract tests.
- Initiative search/layout helpers and epic completion linkage.
- M1 strategy resolver/validator and relationship-focused tests.

## Anti-Scope

- Do not delete or rewrite ticket history during promotion.
- Do not use ticket title, filename slug, or epic title as relationship identity.
- Do not put mutable artifact status into `.megaplan/STRATEGY.md`.
- Do not introduce a second promotion store independent of ticket/epic artifacts.
