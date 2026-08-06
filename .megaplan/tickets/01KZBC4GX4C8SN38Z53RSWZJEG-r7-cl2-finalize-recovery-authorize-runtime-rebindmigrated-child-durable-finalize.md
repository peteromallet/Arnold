---
id: 01KZBC4GX4C8SN38Z53RSWZJEG
title: 'R7 cl2 finalize recovery: authorize runtime rebind/migrated child + durable
  finalize-attempt authority'
status: open
source: human
tags:
- follow-up
- superfixer
- r7
- authority
- recovery
codebase_id: null
created_at: '2026-08-06T11:08:03.365114+00:00'
last_edited_at: '2026-08-06T12:00:03.535464+00:00'
epics: []
---

Follow-up from the occurrence-bound Superfixer backstop (repeated poll 2026-08-06T10:40Z). Target: session critique-ledger-accountability-v3-r7-launch-20260805; plan cl2-wbc-backed-ledger-20260805-2140 (milestone 0 cl2-ledger-replay); occurrence sha256:f3b952beb7881acc80f5efc98b1f21b64a911cc6d17dd87b220e1d336b4e55c5. Blocker: finalize critique_finding_unresolved CF-0B506E1EDCD92E90C192; runtime A fails closed, runtime B unauthorized. Horizon A: Run Authority/operator authorizes A->B rebind or migrated child + canonical recovery-dispatch attempt + effect-barrier receipt + fence rule; then one producer/request/decision/claim/WBC/finalize/validator. Horizon B: recovery_admission.v1 contract, phase-attempt persistence, atomic runtime cutover, gate-finalize compatibility. Evidence: .megaplan/incident-evidence/critique-r7-superfixer-20260806-104038-ca591908/ (handoff_id sha256:96fdcee6e5b9e88df587c43283afcebcf9f9afa346c9c86ce52d73ed80070dd4).
## Retry occurrence 2026-08-06T11:31Z (occ_critique_r7_superfixer_retry_20260806_v3_86e40e1e0058ad7934f251c0, managed run subagent-20260806-113119-171252f9)

Sol stage-2 re-adjudication (codex:gpt-5.6-sol, high reasoning) under restored pinned-runtime evidence:
- Runtime A identity verified (provenance ok:true, content e8b12504130bd283333891ffd5e14f126bb5cd6558892153b4b533a2417fe5e6; chain execution/runtime binding match).
- Operator excludes runtime B; A->B rebind route obsolete.
- Root cause re-reproduced: write_critique_clearance raises critique_finding_unresolved for CF-0B506E1EDCD92E90C192 and CF-B67C1E37D72114DDCF70 (accepted_tradeoff without gate_resolution) under runtime A finalize policy.
- Registry repair via supported seams is NOT available; the only viable recovery is an operator/Run Authority-approved A-lineage source repair of orchestration/critique_custody.py `_resolution_for_finding` (admit accepted_tradeoff && gate_expected && fixed_claim -> verified_plan_mutation) plus prospective recovery admission, deployed via supported runtime-rebind + update_marker_runtime seams, then one override recover-blocked (failure fingerprint 4a772446d29148efccc408bc04eaf07ce5fca741a7e2b1288df78218e4a8bc32), one finalize, then chain start.
- New validated handoff: sha256:d5e9aa809be2f7018ece44d891ed0575e82ad1cfdb1df6acd2574a45b7d5bc2c (envelope .megaplan/incident-evidence/critique-r7-superfixer-20260806-113119-171252f9/recovery-handoff.json).
- Status remains OPEN, assigned to Run Authority/operator. Fingerprint before/after sha256:a8c4416eb4e87db1d2bf52c2ee18c4f39c050206803f73bcac27867729c0e68b.
