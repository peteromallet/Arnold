# M1 Maintenance Boundary Handoff

Status: finalized containment bridge (M1) → M2 handoff
Scope: mutation, receipt, queue, and environment boundaries shipped by M1
Ownership note: this document names boundaries only. It does not grant M2 new
authority. M2 must wrap the named contract nodes with coherent observations and
must not change custody or introduce competing stores (see
[Forbidden changes](#forbidden-changes-for-m2)).

## Purpose

M1 is a default-off containment release, not a contradiction of the Maintenance
Control Plane North Star. It narrows the sprint to shipped safety boundaries
around the existing L1/L2/L3 maintenance paths while preserving the North Star
ownership split:

- **Run Authority** remains authoritative for grants and fences.
- **Custody** remains authoritative for repair custody.
- **WBC** remains authoritative for boundary evidence.
- The lifecycle `write_plan_state` path remains the canonical plan-state writer;
  `TransitionWriter` is not a substitute for it, and `RuntimeTransitionWriter`
  may be used only for maintenance incident/deviation receipts.

M1 contains the existing paths; it does not recreate the M7 authority validator,
lease store, WBC ledger, or `TransitionWriter` enforcement.

## The four boundaries

### 1. Mutation boundary

- Central predicate: `arnold_pipelines/megaplan/cloud/feature_flags.py`
  `mutation_authorized(path)`. Mutation is authorized only when
  `master_enabled AND path_enabled`; the master gate is
  `ARNOLD_AUTONOMY` (default **off**), and each mutation-capable path has its
  own path gate (`ARNOLD_REPAIR_TRIGGER_ENABLED` for L1,
  `ARNOLD_META_REPAIR_ENABLED` for L2, `ARNOLD_AUDIT_AUTOFIX_ENABLED` for L3).
- Unknown paths fail closed: `mutation_authorized` rejects any path outside the
  stable `l1` / `l2` / `l3` identifiers rather than guessing.
- Every shipped wrapper checks the centralized predicate at its effect boundary
  before any plan/state/source/commit/push/subprocess mutation:
  - L1: `arnold-supervise`, `arnold-repair-trigger`, `arnold-repair-loop`
  - L2: `arnold-meta-repair-loop`, `arnold-watchdog`
  - L3: `arnold-progress-auditor`
- Observation, evidence capture, redaction, queue inspection, and reporting
  remain active with `ARNOLD_AUTONOMY=0`; only mutation is blocked.
- The acceptance map pins this boundary at
  `tests/cloud/test_m1_containment_acceptance.py` via the
  no-conftest-hook and explicit-mutation-boundary nodes.

### 2. Receipt boundary

- Durable dispatch receipts live in
  `arnold_pipelines/megaplan/receipts/schema.py` and
  `arnold_pipelines/megaplan/receipts/writer.py`.
- A maintenance dispatch has a durable identity (`dispatch_id`) and an
  initialized snapshot **before** launch; initialization failure blocks launch.
- After any started action, `report_only` is permanently falsified, even if
  finalization fails; every started action stays factual in the durable receipt,
  and a finalization failure surfaces an explicit indeterminate receipt state
  rather than letting the action vanish from receipt truth.
- Automatic maintenance dispatch proves `resolved_runtime_model ==
  "gpt-5.6-sol"` from the dispatch receipt; configured profile names or intent
  strings are not proof, and conflicting pins fail visibly.
- Mutation facts (`state`, `source`, `commit`, `push`) are recorded factually and
  are never inferred from local test success, agent prose, or subprocess exit
  alone.

### 3. Queue boundary

- One central repair queue root: absolute
  `<workspace>/.megaplan/repair-queue` (see
  `arnold_pipelines/megaplan/cloud/repair_requests.py`
  `validate_queue_root`).
- Relative roots are rejected; any root inside `.megaplan/plans` is rejected
  even if a nested directory is named `repair-queue`.
- One lifecycle failure produces one request and one accepted decision/claim;
  repeated identical detection coalesces without duplicate active custody.
- Stranded plan-local requests migrate into the central root as non-authoritative
  lineage; legacy records never become claimable authority.
- No second queue is introduced.

### 4. Environment boundary

- Maintenance custody always names an explicit environment namespace via
  `arnold_pipelines/megaplan/cloud/maintenance_environment.py`
  (`resolve_maintenance_environment`, env `ARNOLD_MAINTENANCE_ENVIRONMENT`).
- The only accepted identities are `production`, `staging`, `test`, and
  `fixture`; anything missing or unrecognized fails closed (raises) rather than
  guessing, and no alias (`prod` → `production`) is accepted.
- Records feeding aggregates, queue decisions, incident bridge writes, and
  conformance fixtures carry their namespace; test/staging/fixture records cannot
  alias production aggregates or the production incident store
  (`arnold_pipelines/megaplan/cloud/incident_bridge.py`).

## Contract nodes M2 may wrap

M2 may attach coherent observations to the following shipped contract nodes.
Each node is the finalized M1 surface; M2 wraps, it does not replace:

- `feature_flags.mutation_authorized(path)` for L1/L2/L3 gating.
- Shipped wrapper effect boundaries:
  `arnold-repair-trigger`, `arnold-repair-loop`, `arnold-supervise` (L1);
  `arnold-meta-repair-loop`, `arnold-watchdog` (L2);
  `arnold-progress-auditor` (L3).
- `current_target.resolve_current_target` — typed `UNKNOWN`/`INCOHERENT`
  evidence with `green=false` and `authorizes_mutation=false` for missing,
  stale, partial, contradictory, cross-environment, or present-but-invalid
  inputs; the production adapter signature is drift-protected.
- `current_target_liveness` — PID/tmux/heartbeat/lease/subprocess-success
  observations are diagnostic and provisional only; they never verify recovery.
- `repair_contract` — closed repair-outcome validation; unexpected outcome
  strings fail validation rather than falling through as success.
- `repair_requests` — central queue root, request/claim coalescing, and
  stranded-request migration lineage.
- `maintenance_environment` — namespace normalization and fail-closed identity.
- `incident_bridge.IncidentStoreWriter` — namespace-bound incident writes.
- `receipts.writer` — dispatch receipt preparation, initialization, and
  finalization (durable identity, resolved-model proof, mutation facts).
- `six_hour_auditor` — six-hour auditor: automatic maintenance launch is
  fail-closed (preinitialized receipt, resolved model exactly `gpt-5.6-sol`,
  non-conflicting pins); when the launch guards refuse, it remains read-only,
  reporting and enqueuing repair requests only; `report_only` is falsified after
  any started action.
- `progress_auditor_controller` — initializes dispatch receipts before
  maintenance subprocesses and derives report mode from factual action markers.

M2 wrapping means observing these nodes (typed observations, coherent evidence,
delayed verification if later approved) without altering their effect semantics.

## Forbidden changes for M2

- **No custody changes.** M2 must not change who holds repair custody, must not
  move grants/fences away from Run Authority, and must not make maintenance
  custody a second execution authority.
- **No competing stores.** M2 must not introduce a second repair queue, lease
  store, WBC ledger, `TransitionWriter` replacement, authority validator, or
  plan-state writer. `write_plan_state` remains the canonical plan-state writer;
  `RuntimeTransitionWriter` stays limited to maintenance incident/deviation
  receipts.
- M2 must wrap the existing custody/receipt/queue boundaries, not replace them.

## Disclosures

### Provisional July 10 audit mapping

The authoritative rank 1–7 audit backlog artifact for 2026-07-10 is unavailable.
Until it is recovered, `tests/cloud/test_m1_containment_acceptance.py` carries
the mechanical provisional mapping as the implementation bridge:

- ranks 1–3 → master-plus-path authorization for L1/L2/L3 mutation;
- rank 4 → one explicit central repair queue and no inferred custody;
- rank 5 → production current-target evidence stays typed and never green;
- rank 6 → liveness/process success remains provisional recovery evidence;
- rank 7 → test incident stores cannot alias production custody;
- addition 1 → dispatch identity and receipt initialization precede launch;
- addition 2 → automatic dispatch proves the exact resolved runtime model;
- addition 3 → the six-hour auditor is read-only and only queues repairs;
- addition 4 → every attempted launch permanently falsifies report-only;
- addition 10 → missing/stale/partial/contradictory evidence fails closed.

This mapping is a reconciliation bridge, not an exact reconciliation to the
missing July audit artifact; it must be re-checked against the original audit
when that artifact is recovered.

### Deferred seven-invariant installed-runtime question

The plan's installed-runtime conformance criterion names seven maintenance
safety invariants: UNKNOWN/INCOHERENT evidence, stale fence/lease, duplicate
occurrence, self-verification, replay correction, default-off action, and
rollback/default-off preservation. Whether installed-runtime conformance over
all seven invariants is proven remains an **open/deferred question** for M1:
M1's shipped-wrapper installed-runtime proof is narrower than that full set (see
next section), so the seven-invariant installed-runtime claim is **not** made by
M1 and must be resolved before M1 can be declared complete against that
criterion.

### What T7 actually proves

Task T7 (installed-runtime proof) proves **only shipped-wrapper syntax and
gating**, exactly through its three nodes:

- `tests/cloud/test_progress_auditor.py::test_audit_effect_authority_requires_mutation_and_commit_gate`
- `tests/cloud/test_watchdog_wrappers.py::test_arnold_meta_repair_loop_wrapper_bash_n_syntax`
- `tests/cloud/test_watchdog_wrappers.py::test_meta_repair_wrapper_has_feature_flag_gating`

Concretely, T7 proves that the shipped `arnold-meta-repair-loop` wrapper bytes
(1) pass `bash -n` syntax and (2) fail closed on the L2 master-plus-path
feature-flag gate. T7 does **not** prove the seven deferred installed-runtime
invariants listed above, and it must not be described as doing so.
