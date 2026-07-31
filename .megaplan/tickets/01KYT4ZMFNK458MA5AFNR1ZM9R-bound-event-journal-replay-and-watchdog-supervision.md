---
id: 01KYT4ZMFNK458MA5AFNR1ZM9R
title: Bound event-journal replay and watchdog supervision
status: open
source: human
tags:
- bug
- performance
- reliability
- observability
- pre-native-blocker
codebase_id: null
created_at: '2026-07-30T18:35:57.813554+00:00'
last_edited_at: '2026-07-30T19:00:16.686390+00:00'
epics:
- epic_id: megaplan-native-parity-corrective
  resolves_on_complete: false
  kind: associated
  provenance: null
  linked_at: 2026-07-30 19:00:16.686313+00:00
---

## Classification

MUST LAND BEFORE THE NATIVE PARITY EPIC STARTS: a bounded compatibility implementation sufficient for status, resume, authority reconstruction, and watchdog supervision to operate safely on the existing M11-scale history. The full durable database/backend productization may wait for Platformization, but the next epic must not run with the current unbounded scans or a disabled watchdog.

## Observed failure

M11 had at least 60,137 events and a roughly 710 MB journal. Canonical resume spent minutes replaying it and read more than 10 GB logically. Watchdog scanning reached roughly 5.4 GiB RSS, creating OOM risk, so watchdog supervision is currently disabled. Repeated restart is not recovery.

## Immediate pre-epic repair

Implement a content-addressed checkpoint/cursor/index path for current authority projection plus bounded reverse-tail/status/watchdog queries. Checkpoints and indexes only accelerate the append-only canonical journal; they never become authority. Bind them to store incarnation, restore generation, schema/fold version, source cursor, and canonical prefix hash. Publish atomically and reject stale, partial, corrupt, or cross-incarnation acceleration state. Re-enable supervision only after bounded-query canaries pass.

Set explicit fixture-relative ceilings before implementation based on a clean baseline, then gate cold restart, warm restart, status, and watchdog on those ceilings for wall time, peak RSS, bytes read, and fold count. The acceptance artifact must record the chosen ceilings and measurements; vague bounded claims do not pass.

## Acceptance

- Golden fixture contains at least 60,137 events and 710 MB of canonical history.
- Full-fold and accelerated projection are semantically identical.
- Warm reads perform no full-journal fold; cold recovery is bounded and publishes one atomic checkpoint.
- Concurrent append, crash during checkpoint publication, truncation, corrupt checkpoint, restore/new incarnation, and schema/fold upgrade fail safely and rebuild when permitted.
- Status and watchdog use bounded cursor/tail APIs rather than independently scanning the journal.
- Emit UTC timing, peak RSS, bytes-read, fold-count, cursor, and checkpoint provenance receipts.
- Watchdog is safely re-enabled and a killed runner is detected without OOM or duplicate repair.

## Successor-epic handoff

Native S1 must consume the exact checkpoint/query contract and 60k-event proof before dispatch. Native S5A/S5B/S7 prove no handler fallback performs an unbounded rescan. Platformization may replace the compatibility implementation with the neutral durable substrate, but must preserve the fixture, non-authority rule, incarnation invalidation, and performance receipts. Deduplicate supervisor behavior with the canonical fixer-containment and timeline-projection tickets rather than creating another watcher.
