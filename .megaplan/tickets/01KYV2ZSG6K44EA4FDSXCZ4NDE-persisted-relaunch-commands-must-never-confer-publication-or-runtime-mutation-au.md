---
id: 01KYV2ZSG6K44EA4FDSXCZ4NDE
title: Persisted relaunch commands must never confer publication or runtime-mutation
  authority
status: open
source: human
tags:
- bug
- recovery
- authority
- publication
- runtime-provenance
codebase_id: null
created_at: '2026-07-31T03:20:20.230680+00:00'
last_edited_at: '2026-07-31T06:27:01+00:00'
epics:
- epic_id: megaplan-native-parity-corrective
  resolves_on_complete: false
  kind: associated
  provenance: post-m11-ticket-gap-audit-20260731
  linked_at: '2026-07-31T06:27:01+00:00'
- epic_id: native-workflow-platformization
  resolves_on_complete: false
  kind: associated
  provenance: post-m11-ticket-gap-audit-20260731
  linked_at: '2026-07-31T06:27:01+00:00'
---

## Classification

The default-off compatibility containment is an immediate post-M11 release
requirement. The complete typed-intent migration is follow-up architecture and
must not delay a release whose live wrappers demonstrably cannot publish,
install, or replace a runtime without current explicit authority.

Native Parity S5A/S5B/S7 owns the Megaplan product integration: migrate every
surviving relaunch producer to a typed intent and route it through the existing
action/effect admission path. Platformization may extract and certify the
neutral intent/effect primitive and second-consumer contract. Both epic links
are association-only: neither epic may auto-close this ticket without proving
that the product command-text authority path is gone.

## Problem

Cloud recovery markers persist relaunch command text. Historical commands can outlive the policy and runtime generation that produced them, so executing them as authority can silently push a branch, install an unbound checkout, or otherwise mutate delivery state. The immediate post-M11 repair makes publication default-off and deterministically regenerates known push/install-capable marker commands from the current wrapper.

## Remaining durable design

Treat every persisted command as evidence/data. A write-capable relaunch may execute only through the canonical action/effect gate with an explicit target-scoped grant, current fence, and durable terminal receipt. Prefer persisting a typed relaunch intent (run kind, subject, pinned runtime identity, target) and materializing command text only after current admission. Remove heuristic shell-text classification once all producers write typed intents.

## Acceptance

- Push, install, checkout replacement, destructive filesystem, and shell-redirection fixtures cannot gain authority from marker text.
- An expired, mismatched-target, mismatched-runtime, or missing grant fails closed with typed evidence and no effect.
- An admitted publication effect produces a target-bound idempotent receipt and replays without duplicate publication.
- Old markers migrate or regenerate safely; no persisted command becomes an authority source.
- Focused recovery proves local repair can relaunch without remote publication.

## 2026-07-31 implementation evidence and residual

Commit `f1e79699e4` landed the immediate containment. Repair runtime selection is
bound to the current envelope, publication is default-off, and known
push/install-capable historical marker commands are regenerated from the
current wrapper rather than trusted as authority.

Keep this ticket open. Release closure still requires the exact final cloud
runtime canary to prove that the deployed watchdog and repair loop inherit the
same selector and cannot publish or mutate the runtime without the explicit
release grant. After release, the typed-intent migration and removal of
heuristic shell-text classification remain the product/platform follow-up
described above.
