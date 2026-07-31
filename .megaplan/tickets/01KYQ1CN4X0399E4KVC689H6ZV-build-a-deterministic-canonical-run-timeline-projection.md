---
id: 01KYQ1CN4X0399E4KVC689H6ZV
title: Contain misleading run views and adopt the platform timeline substrate
status: open
source: human
tags:
- observability
- audit
- timeline
- replay
- post-m11
- projection
- native-platform-consumer
- containment
- do-not-wait-for-platform
- immediate-residual
codebase_id: null
created_at: '2026-07-29T13:35:26.878096+00:00'
last_edited_at: '2026-07-31T03:17:11+00:00'
epics:
- epic_id: megaplan-native-parity-corrective
  resolves_on_complete: false
  kind: associated
  provenance: post-m11-ticket-reconciliation-20260731
  linked_at: '2026-07-31T03:17:11+00:00'
---

## Scope: safe current views and platform-consumer adapter

This ticket contains misleading status now and later wires Megaplan rendering
to the platform projection substrate. It must not implement a second journal or
projection engine.

## Immediate work after the custody epic

- Render unknown/stale/stopped when process, custody, heartbeat, and fresh-event
  evidence do not correlate.
- Never render complete/100% while accepted execution has an unresolved subject
  or a current repairable failure receipt remains.
- Surface marker/PID/tmux/sidecar/authority contradictions explicitly.
- Keep status, `/whats-cooking`, auditors, and timeline views read-only and
  non-authoritative.
- Preserve and bound access to the M10/M11 event history; current multi-hundred
  megabyte journals must not make chain startup or status appear frozen.

## Platform handoff

Native platform M4 owns append-only durable storage, per-domain cursors,
bounded incremental projection, checkpoint/rebuild mechanics, and deterministic
projection utilities. M6 owns installed-package conformance. Megaplan supplies
only the product join schema, canonical state vocabulary, source selection, and
concise operator rendering over that substrate.

## Acceptance

1. The M10/M11 incident chronology rebuilds deterministically with UTC
   timestamps, durations, causal links, failures, repair attempts, and source
   artifact references.
2. Large-history incremental status/startup reads are bounded and measured.
3. Dead-worker/live-tmux, reused PID, late evidence, and false-100% fixtures
   produce explicit contradiction/gap rows.
4. Deleting the projection and rebuilding yields the same digest.
5. Forged or stale projections cannot authorize action.

## Non-goals

- A new authority, state machine, retry queue, event journal, or persistence
  backend.
- Implementing platform M4/M6 inside Megaplan.
- Hiding contradictory evidence to create a cleaner narrative.

## 2026-07-31 reconciliation

`003ae66712` supplies a bounded, rebuildable event-checkpoint substrate and
starts migrating status/watchdog consumers. The concise canonical timeline,
complete consumer inventory, production canary, and contradiction rendering
remain open. Native Parity S6 is the associated Megaplan product consumer. The
finalized Platformization epic may extract qualified projection components, but
does not automatically resolve this product view and is deliberately not
linked with auto-address semantics.
