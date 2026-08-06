# Immediate Fix and Category Hardening — R7 cl2 finalize blocker

- incident/occurrence: occ_critique_r7_superfixer_retry_20260806_v1_70c522f651d6859e134250ee
  (target occurrence digest sha256:f3b952beb7881acc80f5efc98b1f21b64a911cc6d17dd87b220e1d336b4e55c5)
- target: session critique-ledger-accountability-v3-r7-launch-20260805; plan cl2-wbc-backed-ledger-20260805-2140
  (milestone 0 `cl2-ledger-replay`); chain spec sha256 da4b317822a3d2e9c4c5944dd832edbff0f4c01c413a8d32a6b2b5098d21f0d1
- evidence pack: .megaplan/incident-evidence/critique-r7-superfixer-20260806-104038-ca591908/evidence-pack-delta.md
- Sol stage 1: .megaplan/incident-evidence/critique-r7-superfixer-20260806-093148-0d3c3bc5/sol-stage1.md
- Flash swarm (10/10): .../critique-r7-superfixer-20260806-093148-0d3c3bc5/swarm/ + swarm-index.json
- Sol stage 2 (this fire): .../critique-r7-superfixer-20260806-104038-ca591908/sol-stage2.md
- handoff envelope: .../critique-r7-superfixer-20260806-104038-ca591908/recovery-handoff.json
  (handoff_id sha256:96fdcee6e5b9e88df587c43283afcebcf9f9afa346c9c86ce52d73ed80070dd4)
- follow-up ticket: 01KZBC4GX4C8SN38Z53RSWZJEG
  (.megaplan/tickets/01KZBC4GX4C8SN38Z53RSWZJEG-...md, sha256 5fd6cdb1f5d1e047d0e6a8727df3f1299814e4e57760431688049d3cdde33376)
- authoritative fingerprint (before == after): sha256:f606c1a81311e3d4109e3343dcb43d230d9a0fe411560e08605fd1c83a3e25e9

Adjudicated root cause (Sol stage 2, this fire): gate-to-finalize critique-resolution compatibility was not
versioned or validated against the exact bound finalize policy before PROCEED; runtime A (d5848010) fails
closed on finding CF-0B506E1EDCD92E90C192 (`accepted_tradeoff` without verified/gate_resolution/v5 carry).
Missed backstops: no compatibility validator before PROCEED, and the lifecycle coordinator did not leave a
canonical finalize-attempt/repair-identity record, so the canonical repair producer returned
`zero_authority_rejected`. The empty attempt is not retrospectively repairable by an ordinary fixer.

## HORIZON A — `agent_actionable: true` (shortest safe occurrence-preserving action)

- Disposition: quarantine checkpoint inside an active external-gate route
  (route: `external_run_authority_gate_then_authorized_rebind_or_migrated_child_then_one_canonical_repair`).
- Immediate actions completed this fire (notification-silent, zero recovery effects):
  1. Re-observed canonical state (blocked; runner dead; no in-flight recovery; fingerprint unchanged).
  2. Sol stage-2 adjudication persisted; validated content-addressed recovery_handoff.v1 envelope materialized.
  3. Exactly one canonical follow-up ticket created (01KZBC4GX4C8SN38Z53RSWZJEG) for the Run Authority/operator.
  4. Complete blocked receipt written at the managed occurrence directory; schedule left active.
- Next owner: Run Authority/operator for this session's execution binding and recovery admission.
- External gate: explicit approval required for EITHER an atomic CAS-protected A→B runtime rebind (marker +
  chain binding, naming A prior identity and B content identity) OR an authority-approved migrated child,
  PLUS a canonical recovery-dispatch attempt via an authority-owned seam (no backfill from labels/events/
  liveness/PID), an effect-barrier receipt for the interrupted 3rd finalize attempt, and a new fence rule.
- After the gate: exactly one producer run → one blocker-specific request → Run Authority decision → one
  Custody claim/epoch/lease → one WBC attempt/effect key → one ordinary-fixer finalize invocation under the
  authorized runtime → real validator + after-proof (cursor/milestone advancement, terminal Custody/WBC
  receipts, matching runtime identity, zero Horizon A notifications).
- Return condition: resume only when the external authority receipt, runtime transition or migrated-child
  receipt, effect-barrier receipt, new fence rule, and canonical recovery-dispatch attempt all validate.
  Scheduled next attempt = first configured active schedule fire after that condition.
- Stop gates: fingerprint mismatch; envelope/handoff hash failure; state or occurrence identity change;
  live runner/claim/WBC appears; approval absent/ambiguous/unsigned; runtime B content identity absent or
  unauthorized; marker/chain bindings disagree without CAS; missing effect-barrier receipt; selector/output
  policy unresolved; category-risk decision unresolved; producer non-delegated outcome; duplicate
  request/claim/attempt/notification identity; validator rejection or missing phase_end; notification ambiguity.

## HORIZON B — `epic_update_required: true`, `agent_actionable: false` (category closure)

- Epic: .megaplan/initiatives/critique-ledger-accountability-v3-r7-20260805/ (update existing; no duplicate authority).
- First broken contract: unversioned gate-to-finalize resolution envelope; missed backstop: no
  compatibility validation of the accepted artifact set against the exact bound finalize policy, and no
  canonical phase-attempt persistence on failure.
- Canonical owner: Megaplan critique-custody contract (orchestration/critique_custody.py) with attempt
  ownership in auto.py / store/plan_repository.py.
- Machine-readable contract: append-only content-addressed `arnold.megaplan.recovery_admission.v1` envelope
  linking finding resolution + gate carry, canonical phase dispatch/attempt + failure CAS, runtime
  identity/rebind history, request/decision/claim/WBC records, validator envelopes, and notification
  intent/effect identity; every referenced record must hash back to the envelope.
- Required changes: critique/gate/finalize policy enforcement (critique_custody.py, handlers/gate.py,
  handlers/finalize.py, orchestration/finalize_authority.py); attempt persistence before subprocess dispatch
  (auto.py, plan_repository.py); Run Authority/Custody/WBC exact occurrence/runtime/fence/epoch/CAS
  bindings; atomic runtime cutover across chain/execution_binding.py, cloud/runtime_cutover.py,
  cloud/runtime_provenance.py, marker, chain state, authority journal; fail-closed repair_delegation.py with
  typed recovery-admission gate; notification intent after terminal authority decision with at-most-once
  effect; work_ledger duplicate-transition fix and missing-carry/metrics observability.
- Epic crosswalk: CL2 resolution envelope + phase-attempt persistence + WBC replay; CL3 observer/fixer
  consumption and evidence-set briefing identity; CL4 gate/finalize compatibility validation and carry
  completeness; CL5 atomic runtime cutover, recovery admission, notification custody, legacy retirement.
- Dependencies: schema freeze → attempt/runtime authority transaction → gate/finalize enforcement →
  migration/replay → CL5 cutover. Parallel: schema/migration, critique validation, authority transaction,
  observer/fixer, notification work after schema freeze.
- INDETERMINATE (very-hard decisions): fixed-tradeoff equivalence; exact-finding vs family identity;
  same-occurrence rebind vs migrated child; mandatory selector/output declarations; legacy CAS backfill
  eligibility; terminal notification conduit ownership.
- Category-closure proof: retroactive R7 + bigbang replay with crash injection at every boundary yielding
  exactly one repair occurrence, one claim, one attempt, at most one notification effect, real validator
  success, preserved runtime/authority lineage, cursor advancement, and no orphaned request/grant/lease/
  claim/reservation/intent/effect. Closure may be claimed only after the ordinary fixer advances the
  accepted cursor under the authorized runtime.
