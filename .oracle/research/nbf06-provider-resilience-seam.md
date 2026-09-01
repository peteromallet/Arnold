# NBF-06 provider-resilience seam research

Status: read-only repository investigation; no production, tasklist, or status
files were changed for this note.

## Contract binding

The authoritative NBF-06 task is `.oracle/tasklist.md:673-784` (especially
ownership at `683-700`, files at `701-716`, and acceptance at `718-757`).
The same contract is repeated in `.oracle/plan.md:2612-2779`; the detailed T8
transition rules are at `.oracle/plan.md:1284-1312`.  The North Star is
`.oracle/northstar.md:3-15`, and the provider-degraded evolution criterion is
`.oracle/agent_goal.md:115-128`.

The contract is additive to the already-frozen NBF-01 ledger/CAS and NBF-02
admission/scheduling doors.  NBF-06 must not add a scheduler, admission
authority, terminal writer, changed-precondition bypass, rotator, projection,
journal, or independent provider store.

## Single shared seam

The one implementation seam is:

`arnold_pipelines/megaplan/cloud/worker_dispatch.py:1304`
`dispatch_with_admission(request, launch, ...)`.

It is the only common post-admission lifecycle in the current production
doors.  It receives a typed `WorkerAdmissionRequest`, asks the canonical gate,
waits/retries typed `SchedulingCondition` values, constructs
`ControlledFinalLaunch`, runs the launch closure, normalizes the result into a
typed `DispatchOutcome`, appends one canonical terminal at lines 1366-1379,
then closes the controlled adapter at lines 1380-1387.  T8 policy should be
called at this seam around the existing terminal/projection boundary, using
the terminal outcome and `IncidentLedger` projection as its sole input/output
authority.  A provider policy added separately to each door would permit
double observations and divergent retry/fallback decisions.

### Direct consumers of the seam

| Consumer | Current symbol/door | Current path |
| --- | --- | --- |
| Native non-OMP worker | `workers/_impl.py:7887-8015`, `_production_worker_dispatch` | Builds `WorkerAdmissionRequest`, supplies the WBC-backed launch closure, and calls `dispatch_with_admission`; maps `SchedulingCondition`/`DispatchOutcome` back to the legacy worker API. |
| OMP worker | `workers/omp.py:1173-1290`, `_run_omp_with_admission` | Builds the same request, calls the same seam, and preserves typed outcomes in the transport metadata; the physical OMP worker still has its own internal retry loop at `1708-1779`. |
| Managed babysitter | `cloud/babysitter/launch.py:554-643`, `_admit_managed_launch` | Uses the same seam and translates the typed result back to the established integer API while retaining `ctx["dispatch_outcome"]`. |
| Phase handler boundary | `handlers/shared.py:354-565`, `_run_worker` | Is the common caller for plan/gate/review/finalize/feedback flows; it consumes scheduling conditions and typed outcomes and emits a `PhaseResult`. |
| Phase result/execute consumers | `handlers/execute.py:897-925,1232-1245`; `orchestration/phase_result.py:599-704`; `auto.py` driver | Preserve scheduling-vs-failure routing and feed recovery/circuit decisions. Scheduling results must bypass ordinary breaker/failure accounting. |
| Direct legacy worker callers | `workers/_impl.py:8085-8225`, `run_step_with_worker`; `execute/batch.py:1401`; loop/prompt/tiebreaker helpers | Reach `_production_worker_dispatch` or the legacy compatibility path. They must not gain independent provider policy. |

The seam's admission request already carries the relevant route and identity
fields (`WorkerAdmissionRequest` at `worker_dispatch.py:137-181`), and its
receipt carries provider/model/family, route-liveness proof, fingerprint,
reservation event, and execution context (`:200-231`).

## Existing typed and persistence primitives

* `orchestration/phase_result.py:42-99` already defines lossless
  `SchedulingCondition`, including `provider_observation_wait`,
  `provider_degraded`, `provider_probe_wait`, `provider_probe_failed`, and
  `unresolved_launch`.  `DispatchOutcome` at `:102-246` already separates
  `provider_exhausted`, `ordinary_terminal_failure`, `worker_disposition`,
  `success`, `no_launch`, and `unresolved_launch`; provider exhaustion requires
  structured evidence including observation ID, retryability class, attempt
  count, terminal evidence ID, precondition identity, provider epoch identity,
  provider-failure key, and observation time.
* `orchestration/phase_result_classify.py:191-217` preserves those outcome
  kinds and rejects unknown kinds.  It does not yet implement T8 streak,
  hold/probe, or route decisions.
* `incident/schema.py:274-304` defines canonical `ProviderFailureKey`; its
  material is exactly phase, normalized selected spec, typed provider failure
  class, and authoritative provider epoch identity.  `:868-869` exports the
  derivation helper.
* `incident/schema.py:1076-1086` and `:1262-1269` define/validate the existing
  NBF event shapes for worker terminals, route-child reservations, provider
  observations, probe leases/results, and provider recovery.
* `incident/ledger.py:600-638` projects provider-keyed streams from accepted
  worker terminal events.  It increments matching `provider_exhausted`, resets
  on matching success, marks an applicable stream broken on ordinary failure or
  worker disposition, and rekeys only on a changed-precondition key change.
  `:1326-1371` supplies append/create methods for provider observations and
  probe leases/results.  `:1064-1127` validates passed-probe recovery evidence,
  single-use authorization, parent linkage, and the composite
  `provider_route_child_reserved` event.
* `incident/ledger.py:809-935` is the existing canonical terminal writer.
  `cloud/worker_dispatch.py:1366-1379` already keeps the reservation open on
  terminal-append failure and returns a typed unresolved outcome.
* `fallback_chains.py:256-269` reads configured chains;
  `:322-337` derives provider-family boundaries; `:422-518` classifies typed
  retryability; and `workers/_impl.py:7777-7815` is the only configured
  alternate-selection door, `_advance_configured_spec_fallback`.
* `orchestration/recovery_policy.py:694-821` is a pure generic recovery
  classifier, and `:823-860` bridges to the existing circuit.  `auto.py` has
  caller-owned repeated-failure/circuit state at `:5468-5494` and external
  retry handling at `:7150-7205`.  These are consumers/compatibility surfaces,
  not a second T8 owner.

## Existing gaps against T8

The baseline plan explicitly records provider degradation as missing
(`.oracle/plan.md:123-128`): there is no post-launch typed provider policy,
worker-outcome-keyed observation/hold/probe loop, atomic transition-child
decision, or restart-safe same-route return path.  The current code confirms
that gap:

1. `dispatch_with_admission` handles typed admission scheduling and terminal
   persistence, but has no provider observation, probe lease, degradation, or
   configured fallback decision.
2. The ledger projection derives a streak from `worker_terminal_outcome` when
   `provider_failure_key` is present, but does not itself enforce the T8 rule
   that only a canonical accepted `provider_exhausted` terminal creates one
   observation.  The standalone `append_provider_observation` method is not
   linked to a terminal or reservation by its signature, and the projection
   does not consume `provider_observation` records as a policy transition.
3. `workers/omp.py` maps RPC/error text to typed OMP error codes and retries
   internally.  That is useful producer evidence, but it is not a canonical
   accepted `provider_exhausted` outcome and must not directly drive T8 or
   duplicate observations.  Raw stderr must remain outside policy.
4. `_advance_configured_spec_fallback` supports pre-tool, non-execute/read-only
   fallback under explicit safety conditions.  It does not perform the T8
   first-observation hold, probe authorization, linked child admission, scalar
   pin, or return-to-primary transition.
5. `RecoveryPolicy`/`auto.py` classify external errors and ordinary breakers;
   they do not recognize provider-degraded scheduling as a distinct typed
   condition.  Their existing scheduling-condition bypass must be preserved,
   while T8 state must not be folded into the generic repeated-error breaker.
6. `test_provider_scheduling_conditions.py` named by the contract is not yet
   present.  Existing tests cover the pieces but not the end-to-end T8 policy.

## Existing tests and missing coverage

Current useful coverage is split across:

* `tests/arnold_pipelines/megaplan/test_provider_route_projection.py` —
  17 tests for key derivation, keyed/replayed streaks, success/ordinary/
  disposition behavior, probe lease/recovery authorization, composite route
  reservation, and receipt replay.  This is projection/ledger coverage, not
  the shared dispatch policy.
* `test_scheduling_conditions.py` — only lossless phase round-trip and invalid
  reason rejection (2 tests).
* `test_terminal_outcomes.py` and `test_worker_disposition.py` — typed outcome
  invariants and disposition separation.
* `test_fallback_chains.py` — normalization, provider-family boundaries,
  retryability classes, same/cross-family selection, and execute prohibition.
* `test_provider_contract_failure_routing.py` — typed external contract errors,
  bounded repair, and ordinary recovery policy.
* `test_incident_ledger_transactions.py` — reservation/terminal CAS, torn
  writes, replay, changed-precondition consumption, and atomic route-child
  linkage.
* `tests/cloud/test_dispatch_reconciliation.py` — positive no-launch and
  unresolved/replay behavior at the dispatch seam.

The new T8 test module should add deterministic fake clocks, fake probes,
ledger reopen/replay, crash cutpoints, and two-process/CAS races for: one
accepted exhaustion => one observation/streak one/hold; failed probe; passed
probe and recovery authorization preserving streak; exactly one linked child;
matching child exhaustion => degradation; success reset; different-key rekey;
ordinary/disposition break; no-launch/unresolved refusal; scalar pin; fallback
and return composite events; and execute/loop-execute prohibition.  It should
also assert no stderr-only policy, no duplicate internal-retry observations,
one probe lease, one child maximum, and restart-stable receipt/stream state.

## Minimal implementation slices (proposal)

1. **Typed producer adapter.** Extend only the existing worker result/error
   adapters so OMP and non-OMP accepted failures produce one valid
   `DispatchOutcome(provider_exhausted)` with the required evidence.  Keep
   ordinary auth/quota/rate-limit/unsupported/schema/internal errors and
   `worker_disposition` on their existing typed paths.  Have the shared seam
   normalize this once and call the existing terminal writer.
2. **Pure T8 policy at the seam.** Add one small policy module consumed by
   `dispatch_with_admission`.  Given the canonical terminal outcome plus the
   ledger projection, derive the provider-failure key, enforce worker-outcome
   streak semantics, append one observation/hold, and return typed scheduling
   conditions.  Probes use the existing ledger lease/result APIs and injectable
   bounded clocks; probes/waits/recovery events never mutate the streak.
3. **Evidence-bound same-route child.** Invoke the existing provider-recovery
   producer and `reserve_provider_route_child` only after a passed probe and
   consumed single-use authorization.  Use the existing canonical joint
   admission and composite event; derive receipt after commit.  No parent
   unresolved/no-launch child, no time-only retry, and no duplicate route
   reservation.
4. **Configured route and scalar policy.** Ask
   `_advance_configured_spec_fallback` only for an allowed configured target;
   pass the target through the same admission seam.  Preserve scalar pins as
   bounded hold/probe and implement return-to-primary through the same
   composite event.  Explicitly reject execute/loop-execute fallback.
5. **Consumers and recovery.** Teach phase-result/handler/auto consumers to
   preserve `scheduling_condition` and `provider_degraded` without generic
   failure/breaker increments.  Keep generic `RecoveryPolicy` and genuine
   internal-error circuits unchanged.
6. **Replay/race proof.** Add the named focused module and extend existing
   ledger/terminal/fallback tests only where needed.  Reopen the ledger at each
   cutpoint; prove idempotent observation/probe/transition/receipt behavior and
   at-most-one authorized child.  Do not add a scheduler, journal, store,
   admission authority, terminal writer, or alternate fallback door.

## Acceptance boundary

The implementation is complete only when every path above reaches the one
shared `dispatch_with_admission` policy boundary, the exact T8 acceptance list
at `.oracle/tasklist.md:718-757` is covered, and no provider policy remains in
NBF-02/NBF-03 beyond generic scheduling/trace contracts.  This research note
does not claim implementation or test passage.
