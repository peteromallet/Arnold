---
id: 01KYPT8PS81GTFC4CE2PFGVETM
title: Nonterminal runner exit must immediately retrigger verified recovery
status: open
source: human
tags:
- bug
- recovery
- liveness
- observability
- managed-recovery-custody
- immediate-residual
codebase_id: null
created_at: '2026-07-29T11:30:57.448947+00:00'
last_edited_at: '2026-07-31T03:17:11+00:00'
epics:
- epic_id: megaplan-native-parity-corrective
  resolves_on_complete: false
  kind: associated
  provenance: post-m11-ticket-reconciliation-20260731
  linked_at: '2026-07-31T03:17:11+00:00'
---

The fixer declared recovery after transient cursor movement, and a retained M11 runner later exited nonterminal without a new occurrence. Fix commit b74157f1c9a1f3de3605c7f30447db18e5615f10 adds delayed live-heartbeat verification, a managed runner boundary, and immediate predecessor-linked runner_exit_nonterminal requests. The 13:28Z recurrence exposed a remaining deployment boundary: attempt 37 was an already-running noncanonical tmux session, so the managed exit sentinel never owned it and its death again produced no sidecar or queue request. Require the fixer to classify every live target as canonically managed, adopt it under an exit monitor when safe or replace it once, and never report healthy from a raw tmux PID alone. Acceptance: replay a pre-existing noncanonical runner that later dies and prove exactly one fresh global occurrence, one singleton recovery, and a canonical managed successor. Current recovery is now running under operator_control run-runner with supervisor PID 3490468 and child PID 3490470.

## 2026-07-31 reconciliation

The consolidated tree now rejects dead worker PIDs as live active steps
(`373e09dace`) and preserves bounded phase-handoff evidence (`003ae66712`).
Those fixes remove two prerequisites for the recurrence but do not adopt or
replace a pre-existing noncanonical runner. Keep the ticket open as an
immediate live-proof residual. Native Parity S6 is an associated consumer, not
an auto-resolver.
