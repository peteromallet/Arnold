---
id: 01KYV32AG2Y6VQAS8ZDJPG8JJ3
title: Keep human and open-PR waits outside automatic repair custody
status: open
source: human
tags:
- bug
- watchdog
- custody
- notifications
codebase_id: null
created_at: '2026-07-31T03:21:43.170899+00:00'
last_edited_at: '2026-07-31T06:27:01+00:00'
epics: []
---

## Classification

IMMEDIATE POST-M11 RELEASE RESIDUAL. This is a product watchdog/custody
correction, not work to defer to Native Parity or Platformization. A successor
epic may consume its fixtures, but no successor is its resolver.

The cloud watchdog treated durable human-required states (`awaiting_human`, `awaiting_human_verify`) and an open auto-policy PR boundary as failed execution. That allowed L1/L2 repair or relaunch to run before notification, and a stale repair exhaustion sidecar could hide the current gate.

Release-blocker correction:
- classify human/open-PR waits as explicit non-repair dispositions;
- launch exactly one stable, read-only notification agent per gate fingerprint;
- allow machine repair only through a separately admitted canonical machine-repair disposition;
- clear a needs-human sidecar deterministically when its recorded plan is superseded;
- keep resolver-vs-legacy comparison output diagnostic-only;
- preserve matching sidecars as evidence without allowing them to suppress the current typed gate.

Acceptance is the focused watchdog cases for plan, prep verify, chain verify, open PR, stable notification payload identity, stale sidecar clearing, and comparison diagnostics, plus adjacent human-blocker/diagnostic/watchdog suites.

## 2026-07-31 implementation evidence and residual

Commit `62e54c30dd` landed explicit human/open-PR non-repair routing, stable
notification handling, stale needs-human reconciliation, and diagnostic-only
resolver comparison in the watchdog wrapper. Focused cases are present in
`tests/cloud/test_watchdog_wrappers.py` alongside the existing human-blocker
and finalized-open-PR suites.

Keep this ticket open until the exact final frozen inventory passes and the
deployed watchdog canary observes representative `awaiting_human`,
`awaiting_human_verify`, and open-PR states without an L1/L2 launch. At that
point the ticket is narrowly addressable; it has no remaining
Platformization/Native-Parity architecture dependency.
