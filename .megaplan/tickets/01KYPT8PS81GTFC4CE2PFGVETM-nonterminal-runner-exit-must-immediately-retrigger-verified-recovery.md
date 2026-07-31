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
codebase_id: null
created_at: '2026-07-29T11:30:57.448947+00:00'
last_edited_at: '2026-07-30T12:58:53.130269+00:00'
epics: []
---

The fixer declared recovery after transient cursor movement, and a retained M11 runner later exited nonterminal without a new occurrence. Fix commit b74157f1c9a1f3de3605c7f30447db18e5615f10 adds delayed live-heartbeat verification, a managed runner boundary, and immediate predecessor-linked runner_exit_nonterminal requests. The 13:28Z recurrence exposed a remaining deployment boundary: attempt 37 was an already-running noncanonical tmux session, so the managed exit sentinel never owned it and its death again produced no sidecar or queue request. Require the fixer to classify every live target as canonically managed, adopt it under an exit monitor when safe or replace it once, and never report healthy from a raw tmux PID alone. Acceptance: replay a pre-existing noncanonical runner that later dies and prove exactly one fresh global occurrence, one singleton recovery, and a canonical managed successor. Current recovery is now running under operator_control run-runner with supervisor PID 3490468 and child PID 3490470.
