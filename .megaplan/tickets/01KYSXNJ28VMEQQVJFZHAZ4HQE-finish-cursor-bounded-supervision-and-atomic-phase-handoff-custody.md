---
id: 01KYSXNJ28VMEQQVJFZHAZ4HQE
title: Finish cursor-bounded supervision and atomic phase-handoff custody
status: open
source: human
tags:
- bug
- reliability
- performance
- observability
- custody
- superfixer
codebase_id: null
created_at: '2026-07-30T16:28:07.625016+00:00'
last_edited_at: '2026-07-30T16:28:07.625016+00:00'
epics: []
---

The 2026-07-30 M11 incident proved that the remaining failure is structural, not a test-selection problem. Focused review correctly ran only the affected pause/resume tests, but execute completed without an atomic handoff to review; the chain runner stopped, and the three-hour fixer attempted O(total-history) status/recovery projection over a 676 MB / 58k-event journal. Python object expansion drove the container toward OOM before recovery could run.

Immediate bleeding-stop fixes have landed on `editible-install` (`1703509fd8`, `5f0f9f1d6d`, `228a40175f`, `228628b117`): bounded 16 MiB/5,000-event audit tails; liveness/heartbeat no longer counts as durable recovery; default-off global watchdog sweep and unbounded snapshot; exact session/plan targeting; and a live proof auditing one plan in ~25 seconds at stable memory. These mitigations must remain, but they are not the whole architectural fix.

## Required durable follow-up

1. Make every supervision consumer cursor-bounded/incremental: status, introspect, watchdog, progress-auditor snapshots/gather, recurrence evidence, chain driver, resident status, and canonical timeline projection. No full `events.ndjson` read or whole-history Python materialization on the normal recovery path.
2. Make phase completion and next-phase custody one durable transition. A successful `execute` receipt must either atomically admit/start `review` or leave an explicit recoverable handoff receipt owned by a live canonical runner; it must never strand `executed` behind a dead PID.
3. Define recovery success as evidence beyond the recovered boundary (for execute: reviewed/done, not merely executed, heartbeat growth, or a fresh PID). Retain/reacquire custody until that proof or an explicit terminal escalation.
4. Replace permanent manual allowlists with deterministic target selection from the current attention/failure receipt while preserving exact session/plan scoping and preventing fan-out across historical plans.
5. Attest installed wrapper, selected source root, pinned runtime, and editable-install commit as one coherent deployment; wrapper/source drift must fail closed and produce a repairable receipt.
6. Add a 58k-event/~700 MB fixture with wall-time and peak-RSS ceilings, cursor-resume parity against a one-time full rebuild, phase-handoff crash/restart cases, and a regression proving only affected tests run while the full-suite backstop remains shadow/advisory unless policy explicitly promotes it.
7. Feed the bounded-projection receipt and phase-handoff proof into the Custody → Native Parity handoff. This is Custody/Arnold supervision ownership, not Completion-kernel or Platformization ownership.

## Done criteria

- Ordinary status/recovery of the large fixture stays within an explicit small memory budget and time bound independent of total history after the cursor checkpoint.
- Killing the runner after execute success deterministically resumes review without manual state edits or repeated stop/start cycles.
- The three-hour fixer targets one live failure owner, spawns no duplicate repair owner, and cannot declare success from liveness alone.
- All attempts, transitions, failures, recoveries, and acceptance receipts remain reconstructable in the canonical timeline with UTC timestamps and source links.
- Deployed wrapper/source/runtime attestation matches the `editible-install` commit used by the session.

