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
last_edited_at: '2026-07-31T09:25:00+00:00'
epics:
- epic_id: megaplan-native-parity-corrective
  resolves_on_complete: false
  kind: associated
  provenance: post-m11-ticket-reconciliation-20260731
  linked_at: '2026-07-31T03:17:11+00:00'
---

The fixer declared recovery after transient cursor movement, and a retained M11
runner later exited nonterminal without a new occurrence. Historical run notes
cite `b74157f1c9a1f3de3605c7f30447db18e5615f10` for delayed live-heartbeat
verification and a managed runner boundary, but that object is unavailable in
the candidate repository and must not be represented as landed candidate
evidence. The 13:28Z recurrence exposed a remaining deployment boundary:
attempt 37 was an already-running noncanonical tmux session, so the managed
exit sentinel never owned it and its death again produced no sidecar or queue
request. Require the fixer to classify every live target as canonically
managed, adopt it under an exit monitor when safe or replace it once, and never
report healthy from a raw tmux PID alone. Acceptance: replay a pre-existing
noncanonical runner that later dies and prove exactly one fresh global
occurrence, one singleton recovery, and a canonical managed successor.

## 2026-07-31 reconciliation

The consolidated tree now rejects dead worker PIDs as live active steps
(`373e09dace`) and preserves bounded phase-handoff evidence (`003ae66712`).
Those fixes remove two prerequisites for the recurrence but do not adopt or
replace a pre-existing noncanonical runner. Keep the ticket open as an
immediate live-proof residual. Native Parity S6 is an associated consumer, not
an auto-resolver.

## 2026-08-27 third recurrence — hub-owned chain drive torn down with owning session (occurrence a1555447f922)

Shape: chain `native-build-forward`, plan `p2-milestone-gate-bootstrap-20260827-1501`
(robustness full) driven by a hub process launched `persist=false, detached=false, PTY,
restart=on-failure` by the prior babysitter's omp session. The drive completed the plan
phase cleanly (events seq 12-15, 15:14:54, `phase_result exit_kind=success`) and was
SIGKILLed by hub last-omp teardown at ~15:15:03 when that session ended — zero log output
(wrapper redirects all driver output to `.megaplan/cloud-chain.log`; untouched since drive
start), no failure record, `restart=on-failure` never fired (restarts=0), critique never
dispatched. Third recurrence of silent nonterminal custody loss in this epic
(a1555447f922 gen1 04:23Z, 944dd380108d 15:01Z, this).

Dispositions this occurrence:
- Immediate: relaunch under the attested custody contract `persist=true, detached=true,
  pty=false, restart=no`, no ready matcher (hub record nbf-drive-a1555447f922-g2,
  pid 2744069); continuous drive; critique phase_start proven at seq 18, 15:58:54Z.
- Source fix shipped: commit `b91a81c1836303db1490d162cdf3dc242cfd0e10` —
  `arnold_pipelines/megaplan/skills/babysitter/scripts/render_babysitter_goal.py` STEP 4 now
  pins the DRIVE CUSTODY CONTRACT (four hub fields, no ready matcher, attestation, forbids
  persist=false/detached=false and restart=on-failure) + regression
  `test_renderer_drive_custody_contract_pins_persistent_detached_launch` (red->green);
  manifest advanced to generation 10 (expected_head b91a81c183) BEFORE relaunch so every
  worker dispatch binds the fixed generation.
- Codex rank-2 backstop (defense-in-depth, not yet implemented): chain-driver singleton
  lease (`chain/driver_lease.py`, acquired in run_chain, exposed via chain/status.py) +
  local-chain watchdog redrive in `cloud/supervise.py` gated on live lease AND no live phase
  worker. Regression must prove: kill driver between planned-write and critique-dispatch ->
  exactly one successor, resume at critique without re-init, terminal chains do not redrive,
  exits 24/65 do not loop, live lease prevents overlap.

Acceptance addition: a hub-launched chain drive whose owning omp session exits MUST
survive (attested persist+detached), and the goal renderer regression must pin the
contract so the launch contract cannot regress silently.
