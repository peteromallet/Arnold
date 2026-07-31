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
last_edited_at: '2026-07-31T03:20:20.230680+00:00'
epics: []
---

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
