# T1.4 Stage-A implementation delta — deterministic v3 finalizer rejection

Date: 2026-08-02  
Posture: read-only design/preparation except for this requested report  
Status: scoped implementation delta only; **not an implementation or completion claim**

## Decision

Implement only the exercised v3 `plan -> critique -> gate -> finalize` route.
At the finalizer graph-admission boundary, a deterministic rejection has one
stable owner identity and is terminal by default. The only nonterminal outcome
is one owner-authorized, exact-pointer repair against the same run, plan,
iteration, owner-minted object revision, contract bundle, fingerprint, and
occurrence. Consume that authority before dispatch, re-admit the entire repaired
candidate, and never issue a second repair. No execute, publish, or notification
effect may occur before an accepted finalizer transition.

This is the finite Stage-A slice described by the independent Sol report. It is
not the older T1.4 brief's platform-wide owner-store, recovery, wrapper, and
effect migration.

## Preconditions and integration cut

Build on one clean descendant of recovery ancestor
`6787d6363e8fc0603092913ae877db14f3b9fff8`, after these interfaces are frozen:

1. Integrate accepted Run Authority containment candidate
   `48e13e1bcbc6769aff753270331d52ac1c148125`.
2. Repair and independently accept T1.1 candidate
   `3ed353f8aa3d0df450c563c3cb8d76c87349e32d`. Its active repair worktree is
   still clean at that failing commit; the four ordinary-path defects remain:
   caller-mintable hermetic authority, root-policy bypass, direct-init target
   identity loss, and missing-marker/rename fail-open. T1.4 must consume the
   repaired owner-installed admission context and must not add a second local
   admission authority.
3. Consume T1.2's terminal critic-attempt reducer and T1.3's authenticated
   immutable transport/bundle identity. A finalizer semantic candidate is
   admissible only after the selected critic set is terminal `SUCCEEDED` and its
   exact bundle digest is fixed.
4. Consume T1.5's canonical occurrence/Custody port and T1.6's WBC effect port.
   If either port is absent, unreadable, stale, corrupt, or ambiguous, stop;
   never substitute plan-local JSON.

The T1.1 candidate ports being repaired are
`arnold_pipelines/run_authority_store.py:41-59,88-153` and
`arnold_pipelines/megaplan/chain/prerequisite_admission.py:619-845,866-912` in
`3ed353f...`. Their accepted replacements must be injected by owner composition,
not caller arguments. Run Authority's reusable record vocabulary is
`arnold_pipelines/run_authority/contracts.py:197-337,377-402` in `48e13e1...`
(`CoordinatorFence`, `CapabilityGrant`, `SubjectAttempt`, `Claim`, `Decision`,
`CASExpectation`). T1.4 adds an adapter over the accepted owner; it does not add
a generic Run Authority store.

## Current exercised seam and exact defects

The current checkout is `36a10988717f9dfb0ab31d49baf05cc89bcfa989`
(tree `c3f401de2f2e0bf621c7eb88339aaf9483e8bad0`) with substantial unrelated user
changes. Line references below describe the current working files and should be
re-resolved after the clean integration merge.

1. `arnold_pipelines/megaplan/handlers/finalize.py:326-359` validates schema but
   throws only the first diagnostic as prose. The underlying validator already
   provides stable `code`, `payload_pointer`, and `schema_pointer` at
   `arnold/pipeline/contract_validation.py:19-37,84-95,218-273,300-313`.
2. Finalize semantic rules at `handlers/finalize.py:362-479` emit free-form
   messages without stable rule IDs or pointers. They cannot support a semantic
   fingerprint or a safely bounded patch.
3. `FinalizeBaselineSelectionError` is explicitly converted into a broad
   `finalize -> revise -> critique/gate -> finalize` loop at
   `handlers/finalize.py:1453-1581`. It rewrites gate projections and makes the
   plan look critiqued again. This is the exact route T1.4 must replace for v3.
4. `_write_finalize_artifacts` performs normalization, baseline-command
   selection/execution, capability writes, and publication at
   `handlers/finalize.py:1584-1657`. `handle_finalize` invokes it before any
   owner-accepted `gate -> finalize` decision, then sets `finalized` and exposes
   `execute` at `:1705-1775`.
5. `handlers/execute.py:304-319,348-389` checks only the projected state and
   approval flags. It does not require a current accepted finalizer-transition
   record, so direct execute is a bypass.
6. `orchestration/phase_result.py:23-38,303-375` has no typed deterministic
   rejection. Its guard maps ordinary finalizer validation exceptions to
   `internal_error` at `:652-716`.
7. Auto can fresh-retry external errors for `finalize` at
   `auto.py:4628-4705`, and a generic failed phase receives a resumable
   `rerun_phase` cursor at `:4860-4904`. The shared classifier also lists
   `finalize` as externally retryable and retries quality blocks at
   `orchestration/recovery_policy.py:50-59,189-245`.
8. Worker execution has same-model fresh retries at
   `workers/_impl.py:4714-4798`, configured-spec/model fallback at
   `:4870-4940`, and ambient agent fallback at `:4941-4995`. Model capture can
   call an arbitrary envelope repair callback at
   `arnold/pipeline/model_seam.py:964-1004,1107-1120`. Generic JSON repair is
   separate at `workers/_impl.py:2599-2730`; Hermes invokes it at
   `workers/hermes.py:1569-1655`. None of these is semantic graph-repair
   authority.
9. The authored graph exposes `gate:force_proceed` and `finalize:revise` at
   `workflows/workflow.pypeline:100-129,207-217`; the executable policy mirrors
   the revise fallback at `workflows/components.py:1405-1489`. The override
   registry exposes `force-proceed` at `handlers/override.py:1910-1944` and
   `workflows/override_matrix.py:82-89`.
10. Boundary contracts include `plan_to_critique`, `critique_to_gate`, and
    authority-required `gate_to_revise` at
    `workflows/boundary_contracts.py:79-123`, but no `gate_to_finalize` owner
    boundary. `finalize_artifacts` and `finalize_fallback` explicitly set
    `authority_required=False` at `:530-584`.
11. Supervisor control may expose force-advance/reroute from critiqued or gated
    projections at `planning/control_binding.py:397-454`. A copied state or
    prose/reset path therefore remains capable of reaching finalize without the
    intended occurrence/budget join.

Gate's blocking-flag reprompt at `handlers/gate.py:993-1098` occurs before a
finalizer candidate exists. It is not T1.4 graph repair and is not charged to
the finalizer repair budget. The v3 profile nevertheless has one physical model
route and no model fallback, as required by the Stage-A envelope.

## Exact contract

### 1. Typed rejection and semantic fingerprint

Add `arnold_pipelines/megaplan/orchestration/finalizer_repair.py` with closed,
versioned immutable records:

- `FinalizerDiagnostic(rule_id, code, payload_pointer, schema_pointer,
  semantic_subjects)`;
- `FinalizerObjectRef(run_id, project_id, plan_id, iteration, object_kind,
  object_revision, contract_bundle_digest, schema_digest, policy_id,
  policy_version)`;
- `PlannerRepairRequired(object_ref, fingerprint, occurrence_id,
  candidate_digest, diagnostics, invalid_pointers, producer_evidence_ref)`;
- `FinalizerRepairPatch(fingerprint, occurrence_id, object_revision,
  contract_bundle_digest, operations)`;
- `FinalizerAdmission(status, admitted_revision, transition_decision_id,
  repair_ordinal, evidence_refs)`.

The owner mints `object_revision` before finalizer generation. A model output or
copied projection cannot mint a new revision. `candidate_digest` and producer,
model, session, process, runtime, raw-capture, and workspace identities are
bound as occurrence evidence but excluded from the fingerprint.

Compute:

```text
fingerprint = sha256(canonical_json({
  "contract": "megaplan.finalizer-rejection.v1",
  "route": "v3.plan-critique-gate-finalize",
  "run_id": run_id,
  "project_id": project_id,
  "plan_id": plan_id,
  "iteration": iteration,
  "object_kind": "finalize_graph",
  "object_revision": owner_object_revision,
  "contract_bundle_digest": contract_bundle_digest,
  "schema_digest": schema_digest,
  "policy_id": policy_id,
  "policy_version": policy_version,
  "diagnostics": sorted([
    {"rule_id", "code", "payload_pointer", "schema_pointer",
     "semantic_subjects"}
  ])
}))
```

`semantic_subjects` may contain canonical task/action IDs or graph node/edge
IDs required to identify an invariant. It must not contain human error prose,
formatting, raw invalid values, timestamps, retry counts, provider/model/session
identity, process identity, paths, workspace identity, or projection bytes.
Diagnostic ordering and duplicate messages are normalized. Thus rewording the
same failure under the same owner object revision cannot reset the budget.

Refactor `handlers/finalize.py:_validate_finalize_payload` and
`_finalize_semantic_postcheck` into a pure collector
`collect_finalizer_diagnostics(...) -> tuple[FinalizerDiagnostic, ...]`.
Assign a stable rule ID and RFC 6901 pointer to every current schema, semantic,
topology, coverage, and policy invariant. Keep the old raising wrapper only for
non-v3 compatibility. Baseline selection that cannot name a repairable candidate
pointer is a deterministic terminal diagnostic; it must not silently route to
`revise`.

### 2. One owner-CAS repair, consumed before effect

Add `arnold_pipelines/megaplan/orchestration/finalizer_repair_owner.py` containing
protocols/adapters only:

```text
observe_rejection(required) -> occurrence/current budget
claim_repair_once(expected owner cursor, fingerprint, occurrence_id,
                  object_revision, bundle_digest) -> claimed|exhausted|indeterminate
record_dispatch_intent(claim, gle_key) -> exact replay|conflict
resolve_repair(claim, outcome, candidate_digest) -> current owner record
read_current(fingerprint, occurrence_id) -> fail-closed owner view
```

The production adapter is fixed by owner composition. Test doubles live under
tests and cannot be selected through a shipped boolean/backend/key/root/callback.
The owner transaction creates/replays the occurrence and CASes budget
`available -> claimed` exactly once. The budget is consumed when the WBC dispatch
intent becomes durable, not when a response arrives. Two initializers or callers
for the same key produce one claim and at most one effect.

Use T1.6's WBC port for the repair model effect. The GLEK binds:

```text
(run_id, plan_id, iteration, object_revision, contract_bundle_digest,
 fingerprint, occurrence_id, repair_ordinal=1, physical_route_id,
 credential_set_id, tool_mode, runtime_generation)
```

Provider-applied/ACK-lost or local response loss is reconciled against that key;
it is never resent. Unknown provider truth is sticky indeterminate and terminal
for this Stage-A route. No configured-spec fallback, ambient agent fallback,
fresh session, model/provider swap, restart, copied-workspace reset, prose
reprompt, or ordinary phase retry may dispatch another repair.

### 3. Exact pointer/field bounding

Implement `apply_bounded_finalizer_patch(base, patch, required)` in
`finalizer_repair.py`:

- accept only `add` for an exactly missing rejected field and `replace` for an
  exactly existing rejected field;
- every operation pointer must equal an independently derived
  `invalid_pointer`; reject parent, child, sibling, wildcard, alias, duplicate,
  overlapping, or escaped-token ambiguity;
- reject `remove`, `move`, `copy`, array insertion/deletion/reordering/resize,
  task/action ID change, and any operation on owner identity, bundle, policy,
  schema, provenance, route, or revision fields;
- canonicalize before comparison and prove every unlisted leaf and container
  membership is unchanged;
- reject any repair record whose fingerprint, occurrence, base revision, bundle,
  run/plan/iteration, or ordinal differs from the claim.

The repair producer returns only the patch, never a replacement whole payload.
If a rule cannot produce exact independently proven pointers, repair is
ineligible and the rejection is terminal.

### 4. Full re-admission and accepted transition

Add `admit_or_repair_finalizer_candidate(...)` in `finalizer_repair.py`:

1. Collect all pure diagnostics for the original candidate.
2. If none, request Run Authority acceptance for `gate_to_finalize` bound to the
   owner object revision, bundle, candidate digest, current owner cursor/fence,
   critic-attempt proof, and gate decision.
3. If rejected, persist/reconcile the canonical occurrence. Stop unless the
   exact one-repair claim is accepted by the domain owner, Custody, WBC, and Run
   Authority.
4. Dispatch one patch effect, apply the bounded patch locally, then rerun the
   entire current schema + semantic + topology + coverage + policy admission
   set. Do not validate only the named fields.
5. If any diagnostic remains or any owner join is unavailable/ambiguous, mark
   the occurrence terminal/exhausted and stop. There is no second repair.
6. If clean, ask Run Authority to accept `gate_to_finalize` for the repaired
   candidate and same occurrence/revision/bundle. Only that current accepted
   decision makes the finalizer candidate publishable.

Add authority-required boundary contract `gate_to_finalize` in
`workflows/boundary_contracts.py` and include it in exports, semantic-health
checks, fixtures, and boundary tests. Change the v3 `finalize_artifacts` boundary
to reference that accepted decision. Do not treat a receipt, `state.json`,
`gate.json`, `phase_result.json`, or `finalize.json` as the decision.

### 5. Handler ordering and zero downstream effects

Modify `handlers/finalize.py:1705-1775` to order the v3 path:

```text
T1.1 current plan admission
-> T1.2/T1.3 terminal-success candidate evidence
-> pure finalizer admission
-> optional one owner/WBC repair and full re-admission
-> current Run Authority gate_to_finalize acceptance
-> finalize artifact/baseline publication
-> state/history/receipt/phase-result projection
-> expose execute
```

Before acceptance, do not call `_write_finalize_artifacts`, baseline test
commands, `_finish_step`, execute dispatch, Git/PR/product publication, or any
notification sender. Local rejection diagnostics may be projected only after
the owner occurrence commit and remain non-authoritative.

Modify `handlers/execute.py:_enforce_entry_route` to require the exact current
accepted `gate_to_finalize` owner decision in addition to projected
`STATE_FINALIZED`. Missing, stale, superseded, wrong revision/bundle/occurrence,
or unreadable authority rejects before approval-state writes or worker launch.
T1.6's execute/publish/notify effect boundary must consume the same admission
reference. For this T1.4 route, notification remains zero even on terminal
rejection; the separate controlled T1.5/T1.10 failure canary is not permission
to notify from this path.

### 6. Terminal result and bypass denial

Extend `orchestration/phase_result.py` with a versioned
`deterministic_rejection` exit kind and a closed rejection payload containing
only stable IDs/digests/status. Make older phase-result readers explicitly
compatible or fail closed; do not silently coerce the new record to
`internal_error`.

Modify `orchestration/recovery_policy.py` and `auto.py` so this exit kind always
halts with zero retry delta, `STATE_FAILED`, no `resume_cursor`, and no
`recoverable_via` action. Re-observation replays the owner terminal record and
does nothing.

For plans bearing the exact v3 Stage-A admission identity, hard-deny these
alternate paths unless they present the same current accepted owner transition:

- `FinalizeBaselineSelectionError -> revise`;
- `finalize:revise`, `gate:force_proceed`, override force-proceed/replan,
  tiebreaker/override finalize, and direct finalize/execute;
- `model_seam` envelope repair callbacks, generic worker JSON repair used as a
  semantic repair, configured/ambient model fallback, and phase fresh retry;
- supervisor/watchdog/repair-loop restart or copied-state recovery.

Implement the denial through the owner-backed route guard, not by trusting a
v3-looking state field or marker. Unrelated non-v3 workflows keep their existing
behavior; wholesale legacy-route deletion is deferred.

## Exact implementation file set

New production files:

- `arnold_pipelines/megaplan/orchestration/finalizer_repair.py`
- `arnold_pipelines/megaplan/orchestration/finalizer_repair_owner.py`

Required edits:

- `arnold_pipelines/megaplan/handlers/finalize.py`
- `arnold_pipelines/megaplan/handlers/execute.py`
- `arnold_pipelines/megaplan/orchestration/phase_result.py`
- `arnold_pipelines/megaplan/orchestration/recovery_policy.py`
- `arnold_pipelines/megaplan/auto.py`
- `arnold_pipelines/megaplan/workers/_impl.py`
- `arnold_pipelines/megaplan/workers/hermes.py`
- `arnold/pipeline/model_seam.py`
- `arnold_pipelines/megaplan/workflows/boundary_contracts.py`
- `arnold_pipelines/megaplan/workflows/components.py`
- `arnold_pipelines/megaplan/workflows/workflow.pypeline`
- `arnold_pipelines/megaplan/planning/control_binding.py`
- `arnold_pipelines/megaplan/handlers/override.py`
- `arnold_pipelines/megaplan/workflows/override_matrix.py`
- the accepted T1.1/T1.2/T1.3/T1.5/T1.6 owner-composition module after those
  ports freeze; do not guess that filename/API in this lane.

The worker/model-seam edits are narrow mode plumbing: `semantic_repair_once`
must suppress every generic repair/retry/fallback and delegate the effect to
WBC. They are not a rewrite of ordinary transport policy.

## Finite test delta

Add:

- `tests/orchestration/test_finalizer_repair.py` — canonical diagnostics and
  fingerprint, pointer patching, full re-admission, owner CAS, crash/response
  loss, corruption, concurrency, and terminal replay;
- `tests/arnold_pipelines/megaplan/test_v3_finalizer_route.py` — handler ordering,
  gate/finalize/execute authority, alternate-route denial, and zero-effect
  spies;
- `tests/installed_wheel/test_v3_finalizer_repair.py` — clean wheel/module-CLI
  and installed owner-composition behavior;
- focused cloud-wrapper tests beside existing
  `tests/cloud/test_watchdog_wrappers.py` and repair-loop tests, proving the
  installed v3 terminal result is non-restartable/non-redispatchable.

Required hostile cases:

1. Same rule/pointers/revision/bundle under changed error prose, diagnostic
   order, model, provider, session, process, runtime path, workspace copy, and
   restart yields the same fingerprint and occurrence.
2. Changed owner revision, bundle, policy/schema version, semantic subject, or
   actual invariant set does not alias the old authorization.
3. Missing/corrupt/stale/substituted domain owner, Custody, WBC, Run Authority,
   critic-attempt, raw bundle, or gate record rejects before effects.
4. Two and 200 concurrent claimers produce one claim, one GLEK, and at most one
   repair dispatch.
5. Crashes before/after occurrence commit, repair claim, WBC intent, provider
   application, result receipt, re-admission, RA acceptance, artifact write,
   and state projection reconcile without a second effect.
6. Provider applied/ACK lost is reconciled; unknown truth is sticky terminal;
   neither case resends.
7. Exact missing-field add and invalid-field replace can pass. Parent/child/
   sibling widening, valid-field mutation, array resize/reorder, ID mutation,
   whole-object replacement, duplicate pointers, wrong occurrence/revision/
   bundle/fingerprint, and second repair fail.
8. Repaired candidate undergoes every admission rule. Fixing the named pointer
   while creating a new schema/semantic/topology/coverage/policy defect is
   terminal.
9. Baseline-selection rejection no longer fabricates a gate revise loop for v3.
10. Semantic rejection never invokes generic JSON repair, model fallback,
    `--fresh`, resume, override, tiebreaker, watchdog restart, or simple-fixer
    prose reset.
11. Before current RA acceptance, spies observe zero finalize artifact/baseline,
    execute, publish, Git/PR, deploy, and notify effects. Direct execute also
    fails closed.
12. Source, `python -m arnold_pipelines.megaplan`, built wheel, installed
    canonical `workflow.pypeline`, and materialized wrapper behavior agree.

Run the new suites plus current dependency closure:

- `tests/arnold_pipelines/megaplan/test_handler_behaviors.py:908-1054`
- `tests/arnold_pipelines/megaplan/test_model_seam_recovery.py:17-168`
- `tests/arnold_pipelines/megaplan/test_boundary_contracts.py:223-359,452+`
- `tests/arnold_pipelines/megaplan/test_boundary_receipts.py`
- `tests/arnold_pipelines/megaplan/test_workflows_components.py`
- `tests/arnold_pipelines/megaplan/test_workflows_planning.py`
- `tests/arnold_pipelines/megaplan/test_installed_package_composition_smoke.py`
- `tests/arnold_pipelines/megaplan/test_source_path_reconciliation.py`
- `tests/arnold_pipelines/megaplan/test_wheel_smoke.py`
- `tests/installed_wheel/test_import_workflow_kernel.py`

## Explicitly deferred

- Generic T1.7 owner-store adoption or one universal ledger.
- Non-v3 plans, all model routes, model fallback policy outside this exact
  route, and platform-wide retry/recovery redesign.
- Generic `simple_fixer`/watchdog/meta-repair repair logic; T1.5 owns canonical
  failure occurrence/recovery and must consume this terminal occurrence without
  redispatching graph repair.
- Full T1.10 notification UX, reminders, rotation, chunking, and unrelated
  senders. This route sends no notification before acceptance.
- Git/PR/product execution and publication; those effects are unavailable in
  the finite Stage-A envelope.
- Full legacy-test cleanup, every wrapper retirement, key rotation, archival,
  and platform-wide source/entrypoint migration.
- T1.1's generic root-milestone/ChainState redesign beyond its four reproduced
  blockers; T1.4 only consumes its accepted v3 admission record.

## Stage-A acceptance predicate for T1.4

T1.4's route slice is locally acceptable only when one integrated installed
candidate proves all of the following together:

- one stable rejection identity across the hostile equivalence class;
- zero repair by default and at most one owner/WBC repair when explicitly
  accepted;
- exact-pointer preservation and complete re-admission;
- a current accepted `gate_to_finalize` owner decision before artifact
  publication or downstream effects;
- terminal, non-resumable, non-restartable failure otherwise;
- source/wheel/module-CLI/materialized-wrapper parity.

This evidence does not mark T1.4 complete. Formal acceptance still requires an
independent review, clean-lineage integration, installed owner composition, and
the scoped Release Authority receipt for the exact Stage-A candidate.

Report-body SHA-256 (the 443-line UTF-8 report before this digest paragraph was
appended): `c605ace58b2f2077e4635a97879e8e93cea2bc2b068045f310ec5026023b62e9`
