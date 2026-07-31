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
last_edited_at: '2026-07-31T03:21:43.170899+00:00'
epics: []
---

The cloud watchdog treated durable human-required states (`awaiting_human`, `awaiting_human_verify`) and an open auto-policy PR boundary as failed execution. That allowed L1/L2 repair or relaunch to run before notification, and a stale repair exhaustion sidecar could hide the current gate.

Release-blocker correction:
- classify human/open-PR waits as explicit non-repair dispositions;
- launch exactly one stable, read-only notification agent per gate fingerprint;
- allow machine repair only through a separately admitted canonical machine-repair disposition;
- clear a needs-human sidecar deterministically when its recorded plan is superseded;
- keep resolver-vs-legacy comparison output diagnostic-only;
- preserve matching sidecars as evidence without allowing them to suppress the current typed gate.

Acceptance is the focused watchdog cases for plan, prep verify, chain verify, open PR, stable notification payload identity, stale sidecar clearing, and comparison diagnostics, plus adjacent human-blocker/diagnostic/watchdog suites.
