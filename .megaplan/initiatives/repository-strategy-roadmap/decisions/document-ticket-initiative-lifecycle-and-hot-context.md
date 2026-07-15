---
type: decision
slug: document-ticket-initiative-lifecycle-and-hot-context
title: Document, Ticket, and Initiative Lifecycle with Resident Hot Context
created_at: '2026-07-15T11:35:09Z'
---

# Document, Ticket, and Initiative Lifecycle with Resident Hot Context

## Decision

Arnold/Megaplan uses three deliberately different durable categories:

- A **document** is speculative, exploratory, or durable knowledge. It can
  capture evidence, research, a decision, notes, or a handoff, but its
  existence never implies execution approval.
- A **ticket** is a specific problem, opportunity, or idea that probably should
  be addressed but is not yet a coordinated actionable plan.
- An **initiative** is a committed coherent outcome with explicit boundaries
  and success criteria, likely spanning workstreams. Detailed planning and
  chain execution can come later.

Agents search rough slug/title/description and related content first, reuse the
closest canonical artifact, and build on it. A document becomes a ticket when
it identifies a specific addressable item. A ticket is promoted to an
initiative when the outcome is committed and coordination is warranted; the
ticket identity and promotion relationship are preserved. Initiative creation
alone never creates execution authority or starts a chain.

## Placement and initiative structure

Planning assets follow `megaplan-initiatives-v1` at
`.megaplan/initiatives/<slug>/`. `README.md` is the required front door,
current truth, and canonical index. The standard locations are:

- `briefs/`: curated planning inputs and milestone briefs.
- `research/`: evidence, investigations, alternatives, and syntheses.
- `decisions/`: accepted decisions, rationale, and consequences.
- `notes/`: useful working notes not yet promoted to current truth.
- `handoff/`: curated handoffs and canonical syntheses.
- `assets/`: supporting non-prose files.

`NORTHSTAR.md` is optional until the outcome needs a separate durable end-state
anchor. `chain.yaml` is optional until coordinated execution is ready. Planning
documents are never created directly under `.megaplan/briefs`.

Agent and subagent run logs/results remain raw evidence in their managed run
stores. Durable conclusions are curated into the appropriate canonical
document, cite the source run/artifacts, resolve contradictions, and are linked
from the initiative README; raw output is not copied wholesale into current
truth.

Repository-wide durable product/operator documentation can remain in the
repository's established `docs/` or root front-door location. Initiative-owned
knowledge belongs in the matching initiative directories above.

## Resident hot-context contract

The resident injects concise lifecycle instructions plus three separately
labeled rolling-hour categories:

- tickets added or edited;
- initiatives added or edited;
- durable non-state documents added or edited.

The lower one-hour boundary is inclusive and future timestamps are excluded.
The hot summary emits names only, sorted by newest authoritative UTC activity
then normalized name/identity. Added and edited evidence for one identity is
deduplicated; because the output is name-only, duplicate case-folded display
names are also collapsed with newest evidence winning. Each category is capped
and reports an omitted count.

Ticket activity uses canonical `created_at` and `last_edited_at` values and
fails closed on malformed records. Document activity uses explicit
timezone-aware frontmatter timestamps, recent Git add/modify evidence, and
mtime only for untracked/dirty or non-Git documents. State, runtime, cache,
generated plan/epic data, `chain.yaml`, cloud configuration, exact churn names
such as `status.md`/`state.md`/`progress.md`/`wait-log.md`, logs, and raw
subagent output are excluded. A recent admitted document under an initiative
also makes that initiative recent; state-only churn does not.

The hot context is orientation, not a database. Agents use the typed
`tickets`, `initiatives`, `documents`, and `policies` context routes or scoped
search (including their `python -P -m arnold_pipelines.megaplan resident`
CLI twins) for deeper records and authoritative UTC timestamps.

## Compatibility and failure behavior

Existing ticket Markdown and timestamps, initiative search/metadata, and
resident routes remain authoritative. The new routes are additive. The
initiative CLI and resident creation tool now generate an explicit README
front door while leaving `NORTHSTAR.md` and `chain.yaml` optional unless the
caller requests them. Malformed timestamp/frontmatter data is omitted from
recent activity rather than guessed.
