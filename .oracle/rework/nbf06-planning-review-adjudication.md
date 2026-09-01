# NBF-06 planning review adjudication

Date: 2026-08-31  
Reviewer: manager/oracle adjudication of the three Luna rework reviews  
Scope: planning packet and current source only; no brief, matrix, tasklist,
status, or production files were changed.

## Bound inputs

| Artifact | SHA-256 |
|---|---|
| `.oracle/briefs/nbf06-provider-resilience-implementation.md` | `0d7836904dff516d2e7d410f3ce3363d38d512e4bc2dcaff990d883da4bfdabd` |
| `.oracle/research/nbf06-acceptance-test-matrix.md` | `8b9c55f47c52e5dfe71e44f635eab00c3e40578164f317f2b4ccc03121da3758` |
| `.oracle/tasklist.md` | `a4f574ce02421226a0f4610ffc503918e54cd8b5f8ee28ca8e7805afaf1e3959` |
| live source checkout | `887c25cf8fddcd14fde24fce49697b9c8b3188b0` |

The packet is directionally correct, but the findings are not all merely
wording issues. The current source is a pre-NBF-06 baseline: it has typed
primitives, but no integrated T8 producer/observation/route policy. NBF-06
should not pass its planning gate until the accepted and modified items below
are made executable and tested.

## Adjudicated findings

Verdicts mean **accepted** (the finding is true as stated), **modified** (the
risk is real but its scope or exact remedy needs tightening), or **rejected**
(the claimed defect is not supported by the frozen packet/source).

There are no rejected findings in this adjudication. The two modified findings
are genuine risks, but the remedy must preserve the frozen no-second-store and
NBF-04/NBF-05 shell-authority boundaries.

### 1. Cache contradiction / “no provider cache” — MODIFIED (real ambiguity)

Evidence:

* SD-002 and the non-goals prohibit a provider store, projection, journal, or
  cache authority.
* The tasklist and brief nevertheless require cache-loss/mismatch repair and
  list a “cache update” crash cutpoint.
* `IncidentLedger._project_records()` (`incident/ledger.py:518-670`) rebuilds
  provider state from the one journal; there is no provider cache file or
  provider-cache owner in the current source.

Adjudication: this is not permission to add a cache. “Cache” must be defined as
a disposable materialized/in-memory projection (or test double), rebuilt from
the IncidentLedger. A lost or mismatched materialization is repaired by replay;
it must never become a second authority. If the intended requirement is a
persistent cache, the settled decision and ownership boundary must be changed
before implementation. Keep the current no-second-store decision.

### 2. Canonical test-node drift — ACCEPTED

Evidence: the implementation brief’s stable hooks use names such as
`test_accepted_exhaustion_is_single_observation`, while the matrix proposes
`test_accepted_exhaustion_emits_one_terminal_and_observation`. The same drift
exists for A32 (the matrix’s aggregate node versus the brief’s batch and
fanout nodes) and A38. The tasklist fixes the test file and command family but
does not resolve these node names.

Adjudication: accepted. A reviewer cannot tell whether a green result proves
the same MUST criterion when the names differ. The implementation must create
one canonical A01–A38 manifest, with one node and one command per criterion;
the brief, matrix, test module, and final evidence must use that manifest.
Aliases may be retained only as explicit compatibility aliases, not as
separate evidence.

### 3. Uncovered selectors: `memory_headroom`, `auto`, and normalizers — ACCEPTED

Evidence:

* `handlers/shared.py:389-407` calls `select_memory_safe_spec()` and then
  constructs a new `AgentMode`, selecting a configured alternate outside
  `_advance_configured_spec_fallback`.
* `fallback_chains.py:256-270` silently skips malformed entries and returns
  the first duplicate phase entry.
* `auto.py:5613-5625` filters malformed phase-model entries, and
  `workers/_impl.py:7240-7246` does likewise for explicitness checks.
* `worker_fanout.py:451-463` constructs an `AgentMode` from a fallback spec;
  its independent `_next_fallback_index()` is at `:466-490`.
* `workers/_impl.py:8664-8699` (via the worker path) can still select
  `_runtime_fallback_candidates()` after configured fallback declines.

Adjudication: accepted, with a boundary modification. Memory headroom remains
a pre-admission safety/scheduling gate, not a T8 provider rotator, but any
configured-spec choice it makes must be represented by the canonical chain
decision and must not run after an accepted provider outcome. Auto’s phase-model
propagation, every normalizer, fanout, execute, and loop caller must preserve
the same normalized bytes, chain identity, selected index, and suppression
marker. Malformed/duplicate/conflicting input must fail closed rather than be
skipped. Add direct tests for each call site; do not solve this by adding a
second selector.

### 4. Wrapper ambiguity — MODIFIED (scope boundary is required)

Evidence: NBF-05 owns `cloud/wrappers/arnold-watchdog` and
`arnold-heartbeat` (`tasklist.md:521-636`), while the NBF-06 brief explicitly
forbids changing shell wrappers and NBF-04/05 authority. The managed door at
`cloud/babysitter/launch.py:554-643` does use the shared dispatch seam and maps
typed outcomes to the legacy integer API.

Adjudication: the finding is valid only if “wrapper” means the managed/cloud
compatibility boundary. NBF-06 must not put provider policy in watchdog,
heartbeat, or signal wrappers. It must test that the typed terminal and T8
decision are durable before managed integer conversion, and add an ownership
assertion that wrapper edits are outside NBF-06. Treat “managed” and “shell
signal wrapper” as distinct surfaces in the evidence.

### 5. Scalar-chain suppression in fanout/loop — ACCEPTED

Evidence: fanout has its own `_next_fallback_index()` and
`_agent_mode_for_fallback_spec()` (`_core/worker_fanout.py:451-490`) and loops
through alternate specs at `:535-590`. The execute batch also iterates
`configured_specs` directly (`execute/batch.py:1360-1450`). A scalar chain is
currently represented as a one-element tuple by the normalizer, but there is
no universal suppression contract; worker code can still reach the ambient
`_runtime_fallback_candidates` path.

Adjudication: accepted. Scalar presence must mean “configured chain present,”
not “chain has more than one entry.” Fanout, batch execute, and loop-execute
must delegate classification/selection to the one typed door. Execute and
loop-execute must produce the typed no-transition refusal before resolving a
second target or patching metadata. The ambient path must be suppressed for
every configured chain, including a scalar chain, and cannot run after an
accepted worker outcome.

### 6. Distinguish internal same-spec retries — ACCEPTED

Evidence: OMP has an internal retry loop at `workers/omp.py:1710-1779`,
including retry delays and per-attempt failure reasons. Those attempts retain
the same route but are not currently linked to an accepted terminal or a T8
observation. Conversely, the dispatch adapter only constructs
`provider_exhausted` from explicit structured evidence
(`cloud/worker_dispatch.py:312-350`).

Adjudication: accepted. Internal attempts are bounded evidence under one
logical dispatch/receipt; they cannot append terminals or observations. The
final accepted outcome may carry an attempt count and a canonical terminal
provider-evidence ID. Raw stderr/message classification may help an adapter
produce typed evidence, but it must not itself call T8 or create an observation.
Add duplicate-callback, same-spec retry, and accepted-launch gating tests.

### 7. A32 lacks path-specific production commands — ACCEPTED

Evidence: the matrix gives one aggregate A32 command, but the source has
separate paths: `execute/batch.py:1360-1450`, fanout
`_run_worker_unit_with_ordered_fallback()` (`_core/worker_fanout.py:492-590`),
and direct `loop.engine.run_loop_worker()` (`loop/engine.py:541-590`). Existing
tests already separate the surfaces: `test_tiered_execute_provider_fallback.py`
and `test_worker_fanout_fallback.py`.

Adjudication: accepted. A32 evidence must include path-specific commands and
spies proving zero second target resolution, metadata patch, client/WBC/RPC,
or worker launch for each path, plus a direct loop-engine fixture. The
aggregate node may summarize these results but cannot replace them.

Required command shape (using the final canonical node names) is:

```text
pytest -q tests/arnold_pipelines/megaplan/test_tiered_execute_provider_fallback.py::<batch-refusal-node>
pytest -q tests/arnold_pipelines/megaplan/test_worker_fanout_fallback.py::<fanout-refusal-node>
pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::<direct-loop-engine-refusal-node>
```

The final manifest must replace the placeholders with exact nodes and retain
the full focused tasklist command.

### 8. A23/A38 `rg` scans are inadequate — ACCEPTED (modified evidence method)

Evidence: the matrix recommends an `rg` search over broad source/test trees.
That search is useful for discovery, but it cannot distinguish comments,
strings, imports, test fixtures, dynamic calls, or legitimate generic seam
uses. Current source demonstrably contains multiple fallback-related call
sites, so a textual “one owner” result would be unsafe.

Adjudication: accepted. Keep `rg` as a human-readable supplemental trace, but
make the gate an AST/import/call-site checker over an explicit production-file
allowlist. It must identify definitions, calls, imports, and forbidden writes;
allow only the shared seam, the one configured-selection authority, and the
generic ledger/schema extensions. Add negative fixtures for a second selector,
provider policy in NBF-02/03, NBF-04/05 signal edits, and NBF-08 storage.

### 9. Managed/cloud parity — ACCEPTED (with wrapper boundary)

Evidence: native and OMP workers converge on `dispatch_with_admission`; the
managed door calls it at `cloud/babysitter/launch.py:611-643` but converts
`DispatchOutcome` to an integer. The current seam appends the terminal before
returning (`cloud/worker_dispatch.py:1366-1390`), yet does not invoke an
integrated T8 policy. Therefore parity is not established by the current
shared call alone.

Adjudication: accepted. Run equivalent typed-outcome, terminal/observation,
unresolved, and no-side-effect tests for native, OMP, managed, and cloud
callers. Assert that managed integer conversion occurs only after durable
typed evidence and that a compatibility caller cannot relaunch after losing
in-memory metadata. Do not interpret this as permission to alter NBF-05 shell
wrappers.

### 10. Race/crash cutpoint oracle — ACCEPTED

Evidence: existing tests cover generic ledger torn lines and some reservation
contention (`test_incident_ledger_transactions.py:33-184`), but the provider
helpers are not integrated. `append_provider_observation()` at
`incident/ledger.py:1326-1327` is a standalone append, and the current probe
and child operations are separate ledger calls.

Adjudication: accepted and blocking. The NBF-06 gate needs deterministic fault
injection after terminal append, linked observation append, projection update,
probe lease, probe result, recovery creation/consumption, composite child
append, post-commit receipt derivation, materialized-cache update, and child
admission entry. For every cutpoint, reopen the ledger and prove no duplicate
terminal/observation/lease/authorization/child and a stable receipt. Run
two-process races for observation, lease, recovery consumption, and child
reservation. Unknown durability must remain unresolved and must not launch.

### 11. `recovery_policy` / disposition classification — ACCEPTED

Evidence: `phase_result.py:39-99` defines provider scheduling reasons, and
`phase_result_classify.py:191-217` preserves typed outcome kinds. However,
`RecoveryPolicy.classify()` (`orchestration/recovery_policy.py:704-830`) only
special-cases scheduling/no-launch and otherwise treats an accepted
`provider_exhausted` outcome as an unclassified or external error. Worker
disposition is explicitly distinct in both `DispatchOutcome` and the ledger.

Adjudication: accepted. T8 must emit a typed scheduling condition before the
generic breaker/recovery policy, and consumers must bypass blocked/failure
accounting for provider hold/degraded/probe states. Genuine internal errors
must continue through the existing breaker. Disposition must stay a separate
terminal path, break provider consecutiveness as specified, and never become
provider degradation. Add positive and negative consumer tests rather than
changing generic recovery semantics broadly.

### 12. A05 quota/auth versus `provider_exhausted` semantics — ACCEPTED (real
contract ambiguity; resolve conservatively)

Evidence:

* Tasklist A05 says auth, quota, rate-limit, unsupported-model,
  context-window, malformed, schema, and internal errors remain ordinary
  failures.
* The brief’s policy table allows quota to be cross-family configured fallback
  eligible, while saying T8 observation requires explicit typed exhaustion.
* `workers/omp.py:667-730` classifies quota/auth from provider error text, but
  `_OMP_RETRYABLE_CODES` (`:238-255`) excludes quota/auth. `_impl.py:7780-7815`
  nevertheless includes quota/auth in configured fallback classes.

Adjudication: the distinction can be made coherent, but the packet currently
states it too absolutely. Until a settled decision says otherwise, use the
conservative rule: auth/quota are ordinary typed failures for T8 observation;
an explicitly configured, pre-tool cross-family fallback may consume the
ordinary classification, but never creates provider observation/degradation.
`provider_exhausted` requires contract-approved structured evidence and must
not be inferred from quota/auth prose. If quota exhaustion is intended to be a
T8 observation class, amend the tasklist/settled decisions before coding and
update A05/A22; do not silently choose that interpretation.

### 13. Epoch/chain identity source, fencing, and migration — ACCEPTED

Evidence: `ProviderFailureKey` (`incident/schema.py:275-304`) hashes a supplied
epoch string, but the current tree has no canonical provider-epoch producer or
fencing source. `WorkerAdmissionRequest` carries a caller-supplied
`configured_fallback_chain_identity` (`cloud/worker_dispatch.py:137-181`),
while the receipt does not independently carry the normalized chain bytes or
epoch. Child reservation schema (`incident/schema.py:1076-1078`) likewise has
no target epoch/key fields.

Adjudication: accepted. Define the source of truth before implementation:
epoch must come from the authoritative route/admission proof, not wall-clock,
membership refresh, or a worker-supplied arbitrary string; stale epochs must
fail closed under the ledger lock. Chain identity must be derived from phase,
normalized ordered specs, source/profile identity, and schema/parser version,
then be bound to admission, terminal/provider evidence, lease/recovery, child,
and receipt. Old records remain immutable; missing identity means ordinary or
held/unresolved, never inferred provider state. Add stale/reordered/duplicate/
cross-phase chain and wrong-epoch replay vectors.

### 14. Observation canonical ID/atomicity/repair — ACCEPTED

Evidence: `IncidentLedger.append_provider_observation()` accepts an arbitrary
caller-provided `observation_id` and only key/spec/phase/class/epoch
(`incident/ledger.py:1326-1327`). It neither requires a reservation or terminal
ID nor participates in `_project_records()`’s terminal-derived streak. The
schema’s observation shape (`incident/schema.py:1083-1084`) has the same gap.

Adjudication: accepted and blocking. Derive observation identity
deterministically from the accepted terminal/logical dispatch and canonical
key; require reservation, terminal, receipt, selected spec, epoch, chain
identity, and evidence digest. Enforce one-to-one linkage under the existing
ledger lock/CAS (an additive combined terminal/observation transaction is
acceptable); reject orphan, mismatched, and conflicting duplicates. Replay and
cache/materialization repair must return the committed identity, never append
or launch again.

### 15. Probe lease expiry/failure lifecycle — ACCEPTED

Evidence: `create_probe_lease()` rejects any prior same-key
`provider_probe_started` record (`incident/ledger.py:1365-1368`), so a failed or
expired lease can permanently deny future probes. `append_probe_result()` uses
wall-clock `datetime.now()` and only checks lease key/context (`:1329-1359`);
there is no explicit failure/expiry transition in the provider projection.

Adjudication: accepted. Permit at most one active lease, not one lease ever.
Give lease creation/result/failure/expiry deterministic identities and a
test-injectable clock; bind parent reservation, terminal, phase, route, epoch,
and key. Expiry or failed probe must launch nothing and preserve the streak,
while allowing a bounded subsequent lease according to policy. Passed results
are single-use recovery evidence and cannot authorize another parent/key/epoch/
route. Add restart and two-process lease races.

### 16. Canonical single door — ACCEPTED (current source disproves compliance)

Evidence: `_advance_configured_spec_fallback()` is the intended helper
(`workers/_impl.py:7777-7850`), but the live source also contains direct execute
iteration, fanout index/AgentMode construction, memory-headroom selection, and
ambient `_runtime_fallback_candidates()` selection. No production call
currently connects `append_provider_observation`, probe creation/result, and
route-child reservation into one T8 policy at `dispatch_with_admission`.

Adjudication: accepted and a release gate. Implement exactly one T8 policy at
the shared dispatch seam and exactly one configured alternate-selection
authority. Callers are adapters that pass typed decisions through; they may
not select, construct a fallback target, append a terminal/observation, or
launch on an unbound decision. The AST ownership test must enumerate all
current call sites and prove no policy copy remains.

## Concrete revision checklist

The next revision must carry these items into the execution-ready plan and
final evidence (without adding a store or changing NBF-04/05/NBF-08 authority):

1. Resolve the A05 semantic wording conservatively: ordinary auth/quota versus
   explicitly evidenced `provider_exhausted`; state exactly which classes can
   produce T8 observation and which can only trigger pre-tool configured
   fallback.
2. Publish one A01–A38 canonical test-node/command manifest and use it in the
   brief, matrix, implementation, and evidence. Include path-specific A32
   batch, fanout, and direct loop-engine commands.
3. Add a strict full-list phase-model parser: reject malformed, duplicate,
   conflicting, reordered, and cross-phase entries; derive and persist chain
   identity from normalized bytes plus source/profile/parser identity.
4. Audit and route every selector/caller: `handlers/shared.py` memory gate,
   `auto.py` propagation, `resolve_agent_mode`, `_impl.py` fallback and ambient
   path, `execute/batch.py`, `_core/worker_fanout.py`, and `loop/engine.py`.
   A scalar one-element chain must suppress ambient fallback exactly like a
   multi-entry chain.
5. Make execute/loop-execute refusal typed and pre-side-effect, including
   before second target resolution, metadata patch, client/WBC/RPC, or worker
   launch; preserve existing workspace-fingerprint evidence as a safety check,
   not as authorization.
6. Keep OMP/internal same-spec retries as per-attempt evidence under one
   logical dispatch. Only accepted structured adapter evidence may produce one
   terminal and one linked observation; stderr alone never does.
7. Extend the existing IncidentLedger/schema/CAS only: canonical observation
   ID, terminal/reservation linkage, chain/epoch/key binding, one-to-one
   idempotency, combined transition atomicity, and immutable legacy migration.
8. Define provider epoch authority and fencing. Reject stale/wrong epoch and
   forged chain/key/receipt identity before any route or launch side effect.
9. Replace the permanent same-key probe denial with active-lease lifecycle:
   deterministic fake clock, expiry, failure, restart, retry, single-use pass,
   and parent/key/route/epoch binding.
10. Treat cache as disposable materialization only. Add cache-loss and
    mismatched-cache replay tests that rebuild from the ledger and never write
    a second provider authority.
11. Thread provider hold/degraded/probe conditions through phase result,
    handlers, `auto`, and recovery consumers; bypass generic breaker/blocked
    accounting for scheduling while retaining internal-error breaker behavior
    and distinct worker-disposition classification.
12. Add provider-specific deterministic fault injection after every required
    cutpoint and multiprocessing races for observation, lease, recovery,
    composite child, and admission. Assert unresolved on unknown durability and
    at-most-one event/child/side effect on replay.
13. Add an AST/import/call-site ownership checker with explicit allowlists;
    retain `rg` only as supplemental discovery. Check no second scheduler,
    selector, terminal writer, provider projection, journal/store, or NBF-04/05
    signal/NBF-08 chain-control authority.
14. Run native, OMP, managed, and cloud parity fixtures; verify typed evidence
    is committed before managed integer conversion and compatibility replay
    cannot relaunch.
15. Keep shell wrappers outside NBF-06 changes and make that boundary
    mechanically visible in the ownership evidence.

## Oracle disposition

No finding in this review justifies adding a provider store, second journal,
second scheduler, family lease, shell signal authority, or NBF-08 chain ledger.
The packet may proceed to implementation only after the modified semantics and
the checklist above are reflected in the execution plan and the missing T8
integration tests are treated as hard evidence, not as optional follow-up.

## Round-2 adjudication (planning-packet gate)

This round was checked against the exact frozen inputs:

- brief `.oracle/briefs/nbf06-provider-resilience-implementation.md`, SHA-256
  `227fbd5233569932d89ebd34ae2030c904d786e942aa3698dc67f0b444c7e154`;
- matrix `.oracle/research/nbf06-acceptance-test-matrix.md`, SHA-256
  `932b8cd05aa0eee3e497aa8a341be9eed635d27de830a6b538f13d266dbf41de`;
- relevant tasklist `.oracle/tasklist.md`, SHA-256
  `a4f574ce02421226a0f4610ffc503918e54cd8b5f8ee28ca8e7805afaf1e3959`
  (Batch 4/NBF-06 lines 673–818);
- live source at the review baseline, with NBF-06 implementation intentionally
  not started.

Verdicts below distinguish a defect in the packet’s determinism or live-source
assumption from the expected absence of future implementation and tests.

### Verdicts

1. **A32 semicolon and aggregate-node mismatch — MODIFIED (command defect
   accepted).** Matrix A32 (line 97) uses three pytest commands joined by
   semicolons, then says the aggregate node must report all three. A shell
   command of that form can return the status of only the final command and is
   not evidence that all subchecks passed. The brief already preserves the
   three path-specific invocations (lines 424–430), so this is a registry/
   command mismatch, not a reason to reject the underlying requirement. Make
   the aggregate node a real test whose result includes all three named paths,
   and give it one command; retain the three standalone path commands as
   independently required subchecks. The aggregate must fail if any subcheck
   fails and must not hide a skipped/missing path.

2. **Epoch producer, field, proof, fencing, and migration — MODIFIED.** The
   packet correctly rejects wall clock, membership refresh, and worker-supplied
   epoch values (brief lines 172–177; matrix lines 149–157), and correctly
   requires stale/replaced epochs to hold before route/launch. It does not yet
   name the concrete producer, receipt/outcome fields, proof object, or the
   lock-time fence operation. The current source’s admission request has
   `configured_fallback_chain_identity` but no completed NBF-06 epoch contract;
   that absence is expected, not evidence against the plan. Specify one
   authoritative route/admission producer, the exact epoch field on request,
   receipt, terminal/evidence, and child reservation, the proof carried to the
   ledger lock, the compare-and-fence rule, and the typed result for stale,
   replaced, missing, or forged epochs. State that legacy records remain
   immutable and ordinary/held; no migration may infer an epoch.

3. **Canonical chain serialization, version, and source identity — MODIFIED.**
   The brief (lines 152–170) and matrix (lines 149–157) establish the right
   identity ingredients, including normalized ordered specs, phase, source/
   profile identity, and parser/schema version. They do not freeze the byte
   serialization or define what constitutes source identity. Specify the exact
   canonical encoding (including UTF-8, field order, separators, scalar
   one-element chains, and normalization), a named parser/schema version
   constant, and the source/profile/config provenance digest. Replay must use
   the stored bytes/identity rather than current configuration; altered,
   reordered, duplicate, cross-phase, or version-mismatched data fails closed.

4. **Explicit A23/A38 allowlist, profiles, policy overrides, and
   `control_binding` — MODIFIED, with a rejected live-source premise.** The
   packet requires an AST/import/call-site allowlist and names `auto.py`,
   memory, batch, fanout, loop, and the shared selector (brief lines 75–117;
   matrix lines 105–145), but it does not enumerate the production files,
   permitted symbols, profile-resolution/override paths, or the exact binding
   invariant. A targeted live-source search finds no `control_binding` symbol
   or established policy-override field. Therefore a claim that an existing
   live `control_binding` implementation was overlooked is rejected; it would
   import an undefined surface. The plan must either define that term and its
   owner as a genuinely new contract, or explicitly state that no such control
   exists and add a negative fixture preventing an invented override. In
   either case enumerate the actual profile/config and `auto.py` paths in the
   allowlist, with definitions/imports/calls/ledger writes and allowed versus
   forbidden ownership. `rg` remains supplemental only.

5. **A08 “may” versus mandatory probe — ACCEPTED (real packet ambiguity).**
   Matrix A08 (line 73) says first exhaustion “holds, and probe,” while the
   brief says it “may create one bounded probe lease” (SD-006 and lines
   276–277). The relevant tasklist also says “holds, and probes” (line 727),
   so the settled gate intent is mandatory, not optional. That difference
   changes observable state and makes the gate nondeterministic. Settle one
   rule: after the first accepted matching
   exhaustion, the policy must hold and attempt exactly one bounded probe lease
   under the active-key/parent/epoch/route guard. If an active lease already
   exists, or the ledger cannot establish the lease, return the specified
   held/unresolved result with no launch; after a closed lease, only the
   explicitly bounded retry rule may create a subsequent lease. A passed probe
   never resets the streak or authorizes itself as a worker observation.

6. **Canonical selector API and the two timing boundaries — MODIFIED.** The
   packet identifies `_advance_configured_spec_fallback` and the shared
   dispatch seam as the sole authority, but does not freeze a typed API or
   explicitly separate pre-tool selection from post-accepted-outcome policy.
   Define the canonical request/result: phase, normalized chain bytes and
   identity, selected index/spec, structured failure class, provider family,
   `pre_tool`/accepted-launch state, admission receipt/proof, and suppression
   marker in; either a typed next-target decision or `ExecuteFallbackUnsafe`
   with the complete refusal metadata out. The timing rule must be explicit:
   pre-tool, cross-family, contract-approved ordinary failures may consume a
   configured chain; after accepted launch, only the T8 terminal/observation
   seam may act, and execute/loop-execute must refuse before second-target
   resolution. Adapters may transport the decision but never select.

7. **`ExecuteFallbackUnsafe` through broad exceptions — MODIFIED.** The
   packet says not to turn the execute prohibition into an ordinary failure
   (brief lines 297–300), but does not specify transport through broad catches.
   Freeze the exception/result contract and require every adapter to re-raise
   this exact typed refusal unchanged (or wrap only with a preserved cause and
   all fields). A broad `except Exception` must not swallow, classify, patch
   metadata for, or convert it. Tests must assert phase, configured specs,
   selected index, failure class, receipt/chain identity, and zero model
   resolution, metadata mutation, client/WBC/RPC, or worker-launch effects.
   Existing broad catches in the unimplemented paths are not adjudicated as a
   source failure; this is a required implementation invariant.

8. **Observation repair state machine — MODIFIED.** The packet correctly
   requires terminal linkage, deterministic IDs, replay idempotency, and a
   pending-link/reconcile record where one transaction is unavailable (brief
   lines 225–237; matrix lines 159–165). It does not enumerate repair states or
   allowed transitions. Add a finite state table covering terminal committed
   without observation, observation link pending, observation committed with
   projection unknown, repaired/idempotent replay, conflicting duplicate, and
   unknown durability. Replay may reconcile only from the exact terminal,
   reservation, receipt, key/epoch, chain identity, and evidence digest;
   conflict/unknown stays held/unresolved and cannot advance a route. The
   terminal-derived projection remains the sole streak authority.

9. **Probe events, APIs, and closure — MODIFIED.** Active-lease semantics are
   present (brief lines 239–245; matrix lines 167–172), but event names,
   payloads, API return states, and idempotent closure are not frozen. Specify
   `provider_probe_started` plus result/failed/expired closure events (or one
   explicitly typed result schema), each carrying lease ID, parent terminal/
   reservation, key, epoch, phase, route/context, chain identity, and
   deterministic clock/evidence data. Freeze `active -> passed|failed|expired`
   transitions, one active lease, bounded post-close retry, single-use passed
   evidence, and replay behavior. Failure/expiry closes the lease atomically,
   launches nothing, and preserves streak; unknown durability is unresolved.

10. **Typed pre-tool auth/quota evidence producer and binding — MODIFIED.**
    The A05 policy is now semantically coherent: auth/quota may consume an
    explicitly configured pre-tool cross-family fallback but cannot produce a
    T8 observation/degradation from prose (brief lines 259–268; matrix line
    70). The packet does not identify the producer or bind that decision to an
    admission/chain identity. Require a structured pre-tool adapter record
    with `accepted_launch=false`, typed class, source adapter, phase, selected
    index/spec, chain identity, and admission/config provenance; the canonical
    selector alone may consume it. Missing or prose-only auth/quota evidence
    is ordinary failure/no fallback. It must never be relabeled
    `provider_exhausted`, create a terminal/observation, or enter streak/
    degradation state.

    The tasklist’s broad “remain ordinary failures” wording (line 724) is
    compatible only if “ordinary” is explicitly defined as “not a T8
    observation/degradation”; its pre-tool configured-fallback exception must
    be stated alongside that wording in the execution-ready interpretation.

11. **Memory/auto/fanout/batch/loop source absence — REJECTED as stated.**
    The live baseline does contain the pre-admission explicitness helper and
    ambient candidate path (`workers/_impl.py:7237–7250`), the configured
    selector (`:7777–7828`), batch fallback helper (`execute/batch.py:1343`),
    fanout helper (`_core/worker_fanout.py:451–470`), and loop worker
    (`loop/engine.py:541–556`). Their not yet delegating to the future policy
    is expected because implementation has not begun. The brief and matrix
    already enumerate these as adapters/gates and require delegation and
    suppression. No packet revision is warranted for a finding that merely
    reports absent implementation; preserve the allowlist and add the named
    tests during execution.

12. **Parity/race tests absent — REJECTED as stated.** The matrix explicitly
    names native/OMP/managed/cloud parity, crash cutpoints, two-process races,
    replay, and cache-repair evidence (lines 182–196 and A33–A37), while the
    brief makes them hard acceptance requirements (lines 358–376 and
    432–464). Their absence in the preimplementation tree is not a planning
    ambiguity and cannot lower the gate. Implement the already-frozen tests;
    do not add a waiver or claim that current source absence disproves the
    packet.

### Round-2 exact revision checklist

1. Correct matrix A32: replace the semicolon-only aggregate command with one
   aggregate test command whose result covers all three path-specific refusal
   tests; retain and run each of the three standalone commands, with any
   missing/skipped subcheck failing the node.
2. Freeze the epoch contract: producer, request/receipt/outcome fields, proof
   contents, ledger-lock compare/fence, stale/replaced/forged handling, and
   immutable legacy migration behavior.
3. Freeze canonical chain bytes and identity: normalization, ordered encoding,
   scalar representation, UTF-8/field order, source/profile/config provenance,
   parser/schema version, and replay-from-stored-identity behavior.
4. Publish the A23/A38 production-file/symbol allowlist, including profile
   resolution and `auto.py` propagation/override paths, definition/import/call
   restrictions, ledger-write ownership, and negative fixtures. Resolve
   `control_binding` by defining an owner or explicitly declaring it absent;
   do not assume a nonexistent live symbol.
5. Resolve A08 to a deterministic first-observation probe rule: mandatory
   bounded lease attempt, explicit already-active/ledger-unavailable held or
   unresolved result, and bounded post-close retry.
6. Write the canonical selector API and timing table, including typed inputs,
   typed next-target/refusal outputs, pre-tool eligibility, accepted-launch
   prohibition, chain suppression, and adapter-only callers.
7. Specify `ExecuteFallbackUnsafe` propagation across all broad exception
   boundaries and add field-preserving, zero-side-effect tests for batch,
   ordered fanout, and direct loop-engine paths.
8. Add the observation repair state machine and deterministic transition/error
   table; require exact terminal/reservation linkage and unresolved handling
   for conflict or unknown durability.
9. Specify probe event/API schemas and atomic closure/idempotency, including
   active lease uniqueness, fake-clock expiry/failure, bounded retry, and
   single-use passed evidence.
10. Specify the typed pre-tool auth/quota evidence producer and its
    `accepted_launch=false`/receipt/chain binding; prohibit prose-to-T8
    conversion and observation/degradation side effects.
11. Keep findings 11–12 rejected at the planning gate: source and test
    absence is preimplementation, not a packet defect. Treat the existing
    A01–A38 parity/race/allowlist nodes as hard implementation acceptance.
12. Rehash the brief and matrix before implementation and record these
    decisions in the execution-ready plan; do not edit either frozen input,
    the live source, tasklist, or status as part of adjudication.
13. Reconcile the execution-ready interpretation with tasklist Batch 4: keep
    the mandatory first probe (line 727), the sole selector (line 742), the
    execute prohibition (line 751), and the parity/race/cache gate (lines
    752–756); clarify that the tasklist’s ordinary auth/quota wording does not
    permit prose-driven T8 observation while allowing the typed pre-tool
    exception frozen in the brief/matrix.

### Round-2 disposition

The aggregate is **1 accepted, 9 modified, and 2 rejected**. The packet is
not rubber-stamped: A32’s command, probe cardinality, identity serialization,
epoch proof, selector timing/API, exception transport, repair lifecycle,
probe lifecycle, allowlist ownership, and typed pre-tool evidence require the
revisions above. The two source/test-absence findings are explicitly rejected
because they contradict the stated planning gate rather than expose packet
non-determinism. No revision authorizes a provider cache/store, second
selector, second scheduler, second journal, shell signal authority, or
NBF-08 chain ledger.

## Round-3 adjudication (planning-packet gate)

This round was reproduced against the supplied exact inputs:

- brief `.oracle/briefs/nbf06-provider-resilience-implementation.md`, SHA-256
  `6fe4b2c1b4d6db24aff56364d58b5dbe60b6b47a0fd2b8ee5084ee328a132b0c`;
- matrix `.oracle/research/nbf06-acceptance-test-matrix.md`, SHA-256
  `58a68a1f597c95cba93aa8ba96c39b7fe4cca2bece403fc7d0dac543500f6d4d`;
- frozen `.oracle/plan.md`, SHA-256
  `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`;
- frozen `.oracle/tasklist.md`, SHA-256
  `a4f574ce02421226a0f4610ffc503918e54cd8b5f8ee28ca8e7805afaf1e3959`;
- live source baseline `887c25cf8fddcd14fde24fce49697b9c8b3188b0`.

The plan/tasklist are the higher-order frozen contract. Current source and
existing-test gaps are not implementation evidence against a planning packet;
they are relevant only where a packet makes a false live-source claim or
leaves a required contract nondeterministic.

### Round-3 verdicts

1. **Stale manager-adjudication SHA — ACCEPTED.** The current brief line 20
   and matrix line 22 still bind to the earlier Round-1 artifact SHA
   `608bd61f...`, while the Round-2 artifact is
   `ec697d1d146792ea4c207a28e332babb63c0fe798b2e775b24426cb74e095944`.
   That makes review provenance stale. After this Round-3 artifact is
   finalized, the next packet revision must bind both headers to this
   artifact’s final SHA, then rehash the packet and matrix without creating a
   circular self-reference.

2. **A08 mandatory/may/at-most-one and retry timing — MODIFIED.** The packet
   now says “must attempt exactly one” in SD-006/S3 and matrix A08, “at most
   one active lease” in the lifecycle, but still says “may lease one probe” at
   brief lines 411–412 and leaves the timing split between immediate API
   language and the plan’s `retry_not_before` rule. Freeze the sequence as:
   accepted terminal commits hold/streak one; before `retry_not_before` no
   lease is attempted; at the deadline exactly one caller attempts a bounded
   lease; an existing active lease returns held; failure/expiry closes it; only
   the explicit bounded post-close rule permits another lease. “At most one”
   applies to concurrent active leases, not all leases over the lifecycle.

3. **Unsupported/infrastructure exhaustion versus typed availability/
   idle-timeout — ACCEPTED as a classification defect.** The frozen plan
   defines the T8 `provider_failure_class` as typed availability or idle-timeout
   (plan lines 1171–1181 and 1288), while the brief table (line 396) groups
   generic `infrastructure` with availability and does not name idle-timeout.
   The existing classifier’s broad `infrastructure` and `timeout` values
   cannot silently become T8 exhaustion. Freeze the T8 exhaustion enum to
   `availability` and `idle_timeout`, with an adapter mapping only when
   structured evidence proves idle timeout. Generic infrastructure/internal
   errors may follow the frozen pre-tool fallback rule, but never emit
   `provider_exhausted` merely from infrastructure, timeout, unsupported-model,
   or worker-timeout labels. Unsupported-model remains ordinary and excluded.

4. **Auth/quota pre-tool exception versus frozen blocked-fallback rules —
   ACCEPTED.** The brief and matrix introduce a “sole exception” allowing a
   `PreToolProviderAttestation` for an auth/quota cross-family fallback. The
   frozen v1 rules explicitly block fallback for auth errors and quota
   exhaustion (`arnold_pipelines/megaplan/data/instructions.md:180–184`), and
   the plan/tasklist require auth/quota to remain ordinary failures. Calling
   the exception compatible with that wording does not cure the behavioral
   conflict. Remove the exception from the NBF-06 packet and A05, or obtain a
   separately frozen plan/tasklist decision before implementation. Under the
   current gate, auth/quota evidence may be ordinary typed diagnostics but
   cannot consume configured fallback, create a T8 observation, or authorize a
   child. No prose-to-T8 inference is allowed.

5. **Epoch proof timing, fields, and fencing — ACCEPTED as a circularity
   defect.** The brief’s `ProviderEpochProof` (lines 221–243) is produced
   before reservation commit but includes `reservation_event_id` and
   `admission_receipt_id`; the packet also requires receipt derivation after
   commit (lines 360–364). A proof cannot bind IDs that do not yet exist
   without a circular or mutable proof. Split it into a pre-commit immutable
   epoch claim containing route/admission generation, route-liveness and
   membership evidence, family, normalized spec, and claim digest,
   atomically stored with the reservation; then derive post-commit binding/
   proof and receipt from the committed reservation event. Define which digest
   is compared under the ledger lock, how stale/replaced epochs fence, and
   ensure workers/callers never originate or replace the claim. Legacy records
   remain immutable and cannot be inferred.

6. **Selector authority and pure/stateful split — MODIFIED.** The packet has
   a useful sole API, but `PostTerminalHoldProbe` is described as linking,
   projecting, and starting a lease (brief lines 141–145), making the
   supposedly canonical selector stateful. The plan assigns scheduling-loop
   ownership to `dispatch_with_admission` and limits policy to a decision plus
   ledger operations through the existing authority (plan lines 1094–1138).
   Specify two layers under one owner: a pure
   `select_provider_route(request, ledger_view)` with no writes or launches,
   and one lock/CAS decision-applier invoked only by the shared seam for
   terminal/observation/probe/child effects. Adapters transport tagged results
   and never select or write independently. This is an effect split, not a
   second selector or scheduler.

7. **Persisted canonical chain/provenance bytes — MODIFIED.** The packet
   freezes a byte format and says stored identity wins on replay (brief lines
   245–255), but does not explicitly require the canonical chain bytes and
   provenance-origin bytes to be persisted in the authoritative reservation/
   receipt record. A digest alone cannot diagnose tampered or incompatible
   bytes after configuration changes. Persist exact canonical bytes (or an
   immutable ledger payload containing them) and provenance source bytes/digest
   at reservation/receipt creation; later events bind the digest. Keep this
   inside IncidentLedger, never a provider cache. Replay verifies stored bytes
   and never reserializes current profile/configuration.

8. **Observation pending/committed states and cycle-free ID — MODIFIED.** The
   packet lists repair states and APIs, but the observation ID recipe includes
   reservation/receipt identity while receipt identities are also derived
   after commit. Freeze dependency order and exclude any ID derived from the
   event currently being constructed. Derive the observation ID from already
   durable parent terminal, reservation identity, logical dispatch, selected
   spec, chain/key/epoch, and evidence digest; then bind observation event and
   any post-commit child receipt to it. Define transitions for terminal-
   committed, link-pending, observation-committed/projection-unknown,
   repaired, conflict, and durability-unknown. Conflict/unknown remains held
   and cannot route.

9. **`ExecuteFallbackUnsafe` fields, transport, and A32 assertions —
   MODIFIED.** The selector prose requires preserving all request/refusal
   fields, but the refusal rule and A32 row do not enumerate the full
   assertion set. The current exception class carries phase, chain, attempted
   index, total, and selected spec, while the packet additionally requires
   failure class, receipt identity, chain identity, and selected-attempt
   metadata. Freeze one schema and assert in batch, ordered-fanout, and direct
   loop-engine paths: exact typed code/class, phase, configured ordered specs,
   selected/attempted index and spec, failure class, receipt/logical
   dispatch/chain identity, preserved cause, and zero model resolution,
   metadata mutation, client/WBC/RPC, or launch. Broad catches must re-raise
   unchanged. A32’s aggregate and three standalone commands are now
   distinct; aggregate reporting must include every path and fail on missing/
   skipped paths.

10. **Concrete A38 symbol allowlist — MODIFIED.** The packet has a file list,
    but “profile resolution,” “policy override,” `resolve_agent_mode`, and
    ledger/forbidden calls remain categories rather than an exact
    definition/import/call allowlist. Freeze literal production paths and
    symbols, including `workers/_impl.py:resolve_agent_mode` and
    `_advance_configured_spec_fallback`, profile loaders/resolvers, phase-model
    propagation, `auto.py`, `fallback_chains.py`, the shared dispatch seam,
    `incident/{ledger,schema}.py`, and adapter consumers. Enumerate allowed and
    forbidden calls/writes (second selector/scheduler, direct launch/client/
    WBC/RPC, terminal/observation writer, provider projection/store,
    NBF-04/05 signal/confirmation/shell, NBF-08 journal). Distinguish
    definitions, imports, calls, comments, strings, fixtures, and generic
    ledger use; broad `rg` cannot pass A38.

11. **Real `PlanningControlBinding` existence and classification — ACCEPTED
    as an incorrect live-source assumption.** The matrix says no live
    `control_binding` symbol exists (lines 169–177), but the baseline contains
    `arnold_pipelines/megaplan/planning/control_binding.py`, class
    `PlanningControlBinding` (line 906), factory `planning_control_binding`
    (line 1954), and consumers in `planning/operations.py` and
    `control_interface.py`. The source-owner matrix classifies it as the
    maintenance-owned Control Binding decision surface, with repair/execute
    compatibility readers; its module header says non-authoritative in M9 and
    expiry-gated by M10. It is not an NBF-06 T8 owner, but A38 must include it
    as a forbidden/propagation boundary: NBF-06 may not mutate, bypass, or
    reinterpret planning bindings, and profile/override calls must retain
    chain provenance. Correct the packet’s “no live symbol” claim and negative
    fixture accordingly.

12. **Concrete probe executor/result/lease/bounds — MODIFIED.** The packet
    names ledger APIs and event fields but does not identify the injected probe
    executor, result type, lease TTL/deadline, maximum subsequent attempts, or
    the no-tool/no-client guarantee. Freeze an injected `ProbeExecutor` (or
    exact callable contract) receiving parent route/epoch/key/context and
    returning a typed result with lease ID, passed/failed outcome, evidence
    digest, executor identity, start/finish clock samples, and no launch
    acceptance. Freeze lease expiry and `retry_not_before` calculation,
    bounded retry count/window, active-lease CAS, and terminal closure events.
    Failure/expiry/unknown launches nothing; a passed result is single-use and
    only the canonical recovery producer may consume it.

13. **Wrong A06 existing evidence node — ACCEPTED.** Matrix A06 (line 71)
    cites `test_worker_disposition.py::test_disposition_breaks_consecutiveness_without_degradation`
    as existing evidence. The live function is actually
    `tests/arnold_pipelines/megaplan/test_provider_route_projection.py:264`;
    there is no matching function at the cited `test_worker_disposition.py`
    path. Keep the proposed new A06 node, correct the reusable-evidence path,
    and do not treat the future provider-suite node’s absence as a defect.

14. **Reports that the planned provider suite/parity/race implementation is
    absent — REJECTED as planning findings.** The matrix marks the provider
    suite and full crash/race cases as `M`/implementation deliverables (lines
    50–55 and 317–324), and the plan/tasklist make them hard Batch-4 evidence.
    Their absence before NBF-06 starts is expected. Only the oracle details
    above may be revised; no waiver, source backfill, or status/tasklist edit
    is justified by these reports.

### Round-3 exact final revision checklist

1. Rebind the next packet/matrix manager-adjudication header to this Round-3
   artifact’s final SHA after append; preserve prior hashes only as provenance.
2. Resolve A08 timing and cardinality: hold first, wait through
   `retry_not_before`, one guarded active-lease CAS winner, explicit close
   states, and bounded post-close retry.
3. Restrict T8 exhaustion to `availability`/`idle_timeout`; keep generic
   infrastructure/internal/unsupported/worker-timeout semantics out of T8.
4. Remove the auth/quota pre-tool fallback exception under frozen v1 blocked
   rules, or stop for a fresh plan/tasklist freeze before changing scope.
5. Replace circular epoch proof with pre-commit claim plus post-commit binding/
   receipt derivation, exact fields, lock comparison, fencing, and migration.
6. Split pure selector from the single stateful lock/CAS applier without
   creating another selector or scheduler.
7. Persist canonical chain and provenance bytes in authoritative ledger
   reservation/receipt payloads; verify stored identity on replay.
8. Freeze cycle-free observation IDs and all repair-state transitions, with
   conflict/unknown held and unresolved.
9. Freeze complete `ExecuteFallbackUnsafe` schema/cause transport and A32
   field/zero-effect assertions for all three paths and aggregate reporting.
10. Expand A38 to a literal symbol/import/call/write allowlist, including
    profile/override/`resolve_agent_mode`, actual ledger calls, forbidden
    calls, and the real `PlanningControlBinding` boundary.
11. Freeze probe executor/result/lease APIs, no-tool semantics, clock/deadline
    bounds, active-lease CAS, closure/replay, and single-use pass consumption.
12. Correct A06 reusable evidence to
    `test_provider_route_projection.py::test_disposition_breaks_consecutiveness_without_degradation`.
    Keep future suite/parity/race cases as hard `M` acceptance.
13. Rehash all frozen inputs after packet corrections and record the final
    adjudication SHA; do not edit source, tasklist, status, or the packet as
    part of this artifact append.

### Round-3 disposition

The manager disposition is **6 accepted, 7 modified, and 1 rejected**. The
accepted defects are stale adjudication binding, broad infrastructure T8
classification, auth/quota exception against frozen blocked rules, circular
epoch proof, false `control_binding` absence, and wrong A06 evidence path.
The sole rejected category is absence of intentionally future implementation
and tests. No finding authorizes a provider cache/store, second selector,
second scheduler, second journal, shell signal authority, or NBF-08 chain
ledger.

## Round-4 adjudication

### Inputs and method

This round adjudicates the three Round-2/3 Luna REWORK sets against the
planning-packet gate, not against an implementation-complete gate. The exact
inputs were:

| Input | SHA-256 |
| --- | --- |
| `.oracle/briefs/nbf06-provider-resilience-implementation.md` | `ce9d867c6507acb2f18c65ec16a173a68e5ab795a707e5f82cffcc65a638acd2` |
| `.oracle/research/nbf06-acceptance-test-matrix.md` | `816d0801b674113769d701a0e58f15f0e2f84df1cdfbf5f8322626e5ed2076e8` |
| `.oracle/rework/nbf06-planning-review-adjudication.md` (prior) | `aca6cf4b75786a3a0d96569b3f06f372e7aede0a7fc30e11b493a1469ad5b600` |
| `.oracle/plan.md` | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| `.oracle/tasklist.md` | `a4f574ce02421226a0f4610ffc503918e54cd8b5f8ee28ca8e7805afaf1e3959` |
| live-source baseline | `887c25cf8fddcd14fde24fce49697b9c8b3188b0` |

The frozen plan/tasklist and their authority boundaries control where they
conflict with exploratory research. A missing future symbol, test, or
implementation is not a planning defect unless the packet makes its contract
ambiguous or contradicts a frozen higher-level rule. The source confirms that
`classify_retryability` has a broad operational taxonomy and that the current
`ExecuteFallbackUnsafe`/fallback paths are not yet the proposed packet seam;
those facts are implementation work, not evidence that the packet is wrong.

### Finding-by-finding verdicts

1. **`retryability_class` versus `provider_failure_class` — MODIFIED.**

   This is a reproducible packet ambiguity, but not a reason to reject the
   typed T8 contract. The brief's failure table (lines 413–427) and matrix's
   auth/quota rule (lines 292–299) restrict T8 `provider_failure_class` to
   accepted structured `availability` or `idle_timeout` evidence. The live
   `fallback_chains.py:422–506` taxonomy instead exposes broad
   `retryability_class` values, including infrastructure, quota, auth, and
   unsupported model, and even treats quota as cross-family-retryable in one
   helper. Freeze that these are distinct fields and policies: a raw or
   generic retryability label is never cast into T8 exhaustion. Add a literal
   mapping table: structured availability → T8 availability; structured idle
   timeout → T8 idle_timeout; infrastructure/internal/worker timeout,
   quota/auth/rate-limit/unsupported/context/bad-request/unknown/conflict →
   no `provider_exhausted`. Pre-tool fallback eligibility must separately use
   the frozen v1 retryability rules and remain blocked for auth/quota/rate
   limit. Require adapter-produced evidence and fail closed on conflicting
   fields.

2. **Observation committed states/transitions — MODIFIED.**

   The finding is not wholly reproducible: the brief now supplies a finite
   repair table (lines 354–374), and the matrix names
   `terminal_committed`, `observation_link_pending`,
   `observation_committed_projection_unknown`, `repaired`,
   `observation_conflict`, and `durability_unknown` (lines 265–269).
   However, the table says `observation_link_pending` may enter
   `observation_committed`, while the named state is
   `observation_committed_projection_unknown`; this leaves the durable-event
   versus projection-certainty boundary underspecified. Add an explicit
   transition/event table: append link → committed event, then projection
   certainty → repaired or projection-unknown; define whether
   `observation_committed` is an actual state or only an event. State that no
   route, child, or launch is permitted from pending, conflict, or either
   unknown state, and that only exact ledger evidence repairs them. Preserve
   the existing cycle-free ID and terminal-derived streak authority.

3. **Probe `unknown` state — MODIFIED.**

   The packet correctly exposes `ProviderProbeResult.result` as
   `passed|failed|unknown` and separately says lifecycle is
   `active -> passed|failed|expired` (brief lines 376–392; matrix lines
   271–284). It does not say what the result `unknown` does to the lease,
   event, streak, or retry clock. Freeze `unknown` as an unresolved
   durability/result outcome, not a pass and not an ordinary failure: record
   the exact result bytes and typed unknown event/state, do not mutate the
   streak or authorize a child, and do not immediately create another lease.
   Specify whether the active lease closes to `durability_unknown` or remains
   an explicit closed-unknown result, and permit only exact reconciliation to
   `passed`, `failed`, or `expired`. Make replay and idempotent closure rules
   explicit; unknown must never authorize launch.

4. **Crash after epoch claim, before binding/receipt — MODIFIED.**

   The epoch split is now materially correct: the matrix (lines 229–239)
   defines a lock-captured pre-commit `ProviderEpochClaim` without
   reservation/receipt IDs and a post-commit `ProviderEpochBinding` with
   those IDs. The missing case is the crash between those durable operations.
   Add a named `epoch_binding_pending` (or equivalent reservation binding
   pending) repair state and event, with deterministic replay/reconciliation.
   Until binding and authoritative epoch comparison are proven, the
   reservation is held: no client/WBC/RPC/worker launch, terminal progression,
   child, probe authorization, or target rotation. A missing binding is not
   proof of no launch; an explicit pre-launch cut point and exact ledger
   evidence are required. Define how a post-append crash repairs the binding
   without inventing reservation or receipt IDs in the pre-commit claim.

5. **Literal identity bytes and receipt serialization — MODIFIED.**

   The matrix now fixes the chain domain tag, UTF-8, big-endian 64-bit
   length-prefixed fields, field order, scalar count, provenance digest, and
   persistence of chain/provenance bytes (lines 241–252). That is sufficient
   to reject the earlier “identity is only a digest” finding, but not yet a
   byte-level conformance contract. Freeze a normative vector and exact
   encoding for the domain-tag bytes, parser/schema version, `spec_count`,
   source/profile/config origin bytes, normalized strings, raw digest bytes,
   NUL/invalid-UTF-8 rejection, and digest representation. Separately freeze
   field order/version/omission/null rules for the canonical admission and
   post-commit receipt serialization, and state which bytes are persisted and
   hashed. Keep receipt derivation after append so receipt IDs cannot enter a
   pre-commit or observation-ID hash; replay must compare stored bytes rather
   than current configuration. Do not expand this into an unrelated demand
   that every legacy ledger event acquire a new serializer.

6. **Canonical `ExecuteFallbackUnsafe` module, transport, and broad catches — MODIFIED.**

   The packet does require a complete payload and unchanged propagation (brief
   lines 460–469; matrix lines 199–225), and correctly prohibits an execute or
   loop-execute second dispatch. It still does not freeze one unambiguous
   owner/transport: the allowlist calls out
   `orchestration/provider_resilience.py`, while the live canonical class is
   currently in `fallback_chains.py:521–550`; “return/raise” also permits
   callers to disagree about whether the value is a decision or an exception.
   Specify one defining module (or one defining module plus a documented
   identity-preserving import alias), one exact `ProviderRouteDecision`
   prohibition variant, and the boundary that converts it to/raises the
   exact `ExecuteFallbackUnsafe` object. Freeze all listed fields and
   serialization, with no wrapper or metadata patch. Every broad boundary
   must catch/re-raise `ExecuteFallbackUnsafe` before `Exception`; it may not
   wrap, downgrade, select a model, or launch. This is a packet seam defect,
   not a demand that the current source already implement the class there.

7. **A38 literal paths, symbols, calls, and writes — MODIFIED.**

   The revised matrix has a useful production inventory and the real
   `PlanningControlBinding` at `planning/control_binding.py:906` (factory near
   1954), but A38 still uses category-level wording such as
   “normalization/encoding/family/classification helpers” and “adapter/consumer
   plumbing only.” That is not mechanically auditable. Expand A38 to a
   literal allow/deny manifest covering exact files, symbols, imports/call
   edges, and permitted ledger writes, including
   `cloud/worker_dispatch.py:dispatch_with_admission` and terminal-exception
   normalization; the pure selector and locked applier in
   `orchestration/provider_resilience.py`; `_advance_configured_spec_fallback`,
   `run_step_with_worker`, and `resolve_agent_mode`; profiles/override
   loaders; `handlers/shared.py`, `auto.py`, memory, batch, fanout, and loop
   adapters; and the existing ledger/schema append primitives. Mark
   `PlanningControlBinding` as an outside, maintenance-owned boundary that
   NBF-06 may consume but not mutate or bypass. List forbidden direct client,
   WBC/RPC/worker launch, second selector/scheduler/terminal writer/projection,
   provider cache/store, NBF-04/05 signal, and NBF-08 calls/writes. Include
   imported aliases and negative fixtures; `rg` may supplement but cannot be
   the sole proof. This is a packet auditability gap, not a claim that every
   listed symbol must already exist.

8. **Numeric probe TTL/deadline/retry bounds and clock — ACCEPTED.**

   The brief and matrix name TTL, deadline, `retry_not_before`, maximum
   attempts, total retry window, and an injected executor/clock, but provide
   no numeric constants, formulas, or boundary semantics (brief lines
   376–392; matrix lines 271–284). This is a direct determinism defect in a
   planning packet. Freeze finite versioned values/formulas (for example,
   lease TTL, execution deadline no greater than TTL, maximum attempts, and
   total retry window), the exact `retry_not_before` calculation, inclusive or
   exclusive expiry, and the injected monotonic/UTC clock contract. Specify
   cancellation, clock rollback/jump handling, and deterministic vectors at
   each boundary. Values must be justified by the plan; the adjudication does
   not invent them. A future implementation or test absence is not itself the
   finding.

9. **Stale architecture research, quota, and source precedence — MODIFIED.**

   The two cited research files are not stale in this revision: their bytes
   match the brief's recorded SHAs (`0f00ca46…f168d` and `6903b3b4…7740f9f`),
   and the seam research explicitly names `.oracle/tasklist.md:673–784` as
   authoritative. The adversarial research usefully records that current
   code's retry taxonomy may include quota, while the frozen packet and plan
   prohibit auth/quota fallback and T8 exhaustion. The review is therefore
   overbroad if it treats research prose or current source as a conflicting
   authority. Modify the packet's provenance section to state precedence:
   frozen tasklist/plan and settled packet/matrix contracts first (with the
   matrix authoritative for A01–A38), cited research read-only/contextual,
   and live source descriptive only until implementation. Rehash referenced
   research whenever it changes and explicitly say no stale research can
   override the frozen v1 auth/quota rule. Do not add quota fallback merely
   because the source helper currently labels it retryable.

10. **Post-terminal target proposal versus the higher plan — MODIFIED.**

   The concern identifies a terminology hazard, not an outright higher-plan
   violation. The frozen plan (lines 1125 and 1314–1326) permits T8 policy to
   propose a configured fallback target through
   `_advance_configured_spec_fallback`; the shared seam then constructs the
   linked child and canonical admission validates it. The packet (brief lines
   448–458) correctly says there is one configured selection door and no
   post-terminal second selector. Freeze that “proposal” is a pure data
   candidate from the already persisted, normalized chain—not a new selection,
   authorization, scheduler, or launch—and that only the locked shared seam
   can authorize the child. State whether the policy may call the helper only
   to form that candidate, require source receipt/key/epoch/observation and
   target identity in the locked validation, and define the zero-effect result
   for rejection/race/unknown. Do not remove the higher-plan proposal step;
   remove only the ambiguity that could turn it into a second selector.

11. **Claims that missing future APIs/tests are packet failures — REJECTED as
    stated.**

   The current source does not yet contain the proposed provider-resilience
   module, full probe API, expanded exception payload, parity fixtures, or
   race/crash tests. That is expected because the task is explicitly a
   planning packet and the plan/tasklist assign those to future slices. The
   source's `fallback_chains.py:521–550`, `workers/_impl.py:7777–7828`,
   `execute/batch.py:1360–1455`, and fanout path are evidence for the
   implementation delta, not grounds to reject this packet. Such review
   comments are rejected unless they identify one of the contract ambiguities
   above or an actual contradiction with the frozen plan. The implementation
   must still satisfy the revised A38, crash, parity, and race acceptance
   contracts when executed.

### Round-4 exact revision checklist

Before another planning-packet gate, the packet author must:

1. Add the explicit `retryability_class` → (or not →) T8
   `provider_failure_class` mapping, with adapter evidence and fail-closed
   conflicting/unknown rules; keep auth/quota/rate-limit blocked.
2. Replace the observation prose/table with one exact event/state transition
   table that distinguishes committed event, projection-unknown,
   durability-unknown, conflict, repair, and route/launch eligibility.
3. Define probe `unknown` result closure, durability state, retry/streak
   effects, replay, and reconciliation; prohibit child authorization.
4. Add crash-safe epoch-binding-pending state/event, repair proof, and the
   positive no-launch rule after a claim/reservation crash.
5. Publish canonical chain and receipt byte vectors, field encodings, digest
   representation, provenance bytes, version/omission rules, and replay byte
   comparison without circular IDs.
6. Name the one `ExecuteFallbackUnsafe` defining module, decision/exception
   conversion boundary, exact payload transport, and broad-exception
   re-raise ordering.
7. Turn A38 into a literal path/symbol/import/call/write allowlist and
   forbidden manifest, including profiles/overrides, `resolve_agent_mode`,
   the real planning-control boundary, and negative fixtures.
8. Freeze versioned numeric probe TTL/deadline/max-attempt/retry-window
   values or formulas, `retry_not_before`, expiry boundaries, injected clock,
   cancellation, and clock-jump test vectors.
9. Record source/research SHA provenance and precedence explicitly; mark
   architecture research read-only and non-authoritative to the frozen
   plan/tasklist/matrix, especially for quota/auth semantics.
10. Rewrite post-terminal “target proposal” as a pure configured-chain
    candidate and document the single locked admission/authorization door,
    including rejected/raced/unresolved zero-effect outcomes.
11. Rebind the next brief and matrix to this appended adjudication SHA after
    all packet corrections. Do not edit source, tasklist, status, or this
    artifact's prior rounds while performing packet revision.

### Round-4 disposition

The manager disposition is **1 accepted, 9 modified, and 1 rejected**. The
accepted defect is the absence of numeric probe bounds and deterministic clock
semantics. The modified findings are the retryability/T8 mapping, observation
repair vocabulary, probe unknown outcome, epoch binding-pending crash gap,
literal identity/receipt bytes, canonical `ExecuteFallbackUnsafe` transport,
A38's mechanical manifest, research precedence, and post-terminal proposal
semantics. The rejected finding is implementation/test absence treated as a
planning failure. No Round-4 finding authorizes a provider cache/store,
second selector, second scheduler, second journal, shell signal authority, or
NBF-08 chain ledger.

## Round-5 adjudication

### Inputs, authority, and reproduction standard

This round was checked against the exact packet inputs below:

| Input | SHA-256 |
| --- | --- |
| `.oracle/briefs/nbf06-provider-resilience-implementation.md` | `6ee00bf6bd9e3b534c0e584f0638341be4ab192e6edf7d860372bb0436305115` |
| `.oracle/research/nbf06-acceptance-test-matrix.md` | `582d1973ae368a0398945ef49fd051058b7ffec9670a48d71f22ffe484407c59` |
| `.oracle/rework/nbf06-planning-review-adjudication.md` (prior) | `57d64c3625d69c9612bfdd98b408f82d5626cf545bc1c3f95609139f4819c755` |
| `.oracle/plan.md` | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| `.oracle/tasklist.md` | `a4f574ce02421226a0f4610ffc503918e54cd8b5f8ee28ca8e7805afaf1e3959` |
| live-source baseline | `887c25cf8fddcd14fde24fce49697b9c8b3188b0` |

The frozen plan/tasklist remain the higher authority; the matrix is authoritative
for A01–A38; the brief supplies the settled NBF-06 detail; research is
read-only context; and the current source is evidence of the implementation
delta. A future test or symbol being absent is not itself a packet failure.

### Finding-by-finding verdicts

1. **Probe unknown/durability state, event, and replay — REJECTED as stale.**

   The alleged omission is no longer reproducible. The brief explicitly makes
   `unknown` close to `durability_unknown`, records exact result bytes, leaves
   streak and authorization unchanged, prohibits immediate retry, and permits
   only exact reconciliation to `passed`, `failed`, or `expired` (lines
   496–505). The matrix says the same and defines matching replay/closure as
   idempotent (lines 384–399). This is sufficient planning semantics. The
   implementation must later prove it, but source/test absence does not reopen
   this finding.

2. **Numeric boundary vectors and post-close attempt timing — MODIFIED.**

   The packet now freezes `NBF06-PROBE-V1` values and formulas—30-second lease
   TTL, 20-second executor deadline, 5-second delay, two attempts, and
   90-second window—and defines inclusive expiry and injected-clock behavior
   (brief lines 507–520; matrix lines 401–411). The remaining ambiguity is the
   post-close schedule: “permits a bounded subsequent lease” does not say
   whether the 5-second delay applies after each failed/expired closure, how a
   second lease's attempt number relates to the per-parent “1 or 2” rule, or
   what happens when closure and retry-window boundaries coincide. Add exact
   vectors for just-before/at/after `retry_not_before`, lease deadline, window
   end, failed closure, expired closure, second-attempt admission, and backward
   clock samples. Define `next_retry_not_before` after each closure, attempt
   counting scope, and the zero-effect result at every boundary. Do not alter
   the constants merely because a reviewer prefers different values.

3. **Canonical `WorkerAdmissionReceipt` versus a provider receipt — ACCEPTED.**

   This is a real cross-artifact naming and identity conflict. The frozen plan
   makes `WorkerAdmissionReceipt` the canonical admission result, owned by the
   admission/ledger authority, with a required field set and a versioned ID
   derived from the committed reservation event and canonical logical-child
   identity (plan §4.4, lines 341–398; composite rule §4.7, lines 580–611).
   The revised brief/matrix instead introduce `NBF06-RECEIPT-V1`, call its
   SHA-256 a “Receipt ID,” and use `admission_receipt_id` while omitting
   canonical fields such as physical door, admission attempt, route-liveness,
   source/runtime/manifest identities, projection version, and admitted-at.
   Freeze that NBF-06 cannot create a competing admission receipt or redefine
   `admission_receipt_id`. Either make its bytes an explicitly additive
   provider-evidence envelope that references the existing canonical receipt,
   with a distinct `provider_evidence_receipt_id`, or specify an approved
   additive extension through the NBF-01 receipt serializer. Preserve the
   existing WorkerAdmissionReceipt derivation and fields, distinguish the two
   byte vectors/IDs, and state which one is carried by terminal, observation,
   probe, and child events. A provider payload must never replace or silently
   truncate the canonical admission receipt.

4. **`ExecuteFallbackUnsafe` serialization and exact-object versus wrapper — MODIFIED.**

   The packet now names one defining class at
   `arnold_pipelines/megaplan/fallback_chains.py:521`, makes the selector return
   a tagged refusal carrying the object, has the adapter raise once, and
   requires broad catches to re-raise the same object (matrix lines 250–281).
   That resolves duplicate-class and wrapper ambiguity. It does not define the
   canonical serialized transport for a process/CLI/phase boundary: the
   complete field list is present, but field encoding, version, omission/null
   rules, and round-trip identity are not. Name the existing exception/error
   transport owner (or freeze one additive versioned envelope), serialize all
   fields deterministically, and require deserialization to preserve the exact
   refusal code and payload without constructing a new routing decision. Keep
   `except ExecuteFallbackUnsafe: raise` before broad `Exception`; a wrapper may
   carry display text only if the canonical typed object remains the transported
   cause and no metadata is patched. This is a contract refinement, not a
   requirement that the current source already have the future fields.

5. **Remaining nonliteral A38 entries and stale line/symbol names — ACCEPTED.**

   A38 is improved but still not mechanically reproducible as written. The
   matrix manifest gives category-only entries such as
   `handlers/shared.py:389 configured-chain adapter`,
   `orchestration/phase_result.py, phase_result_classify.py, recovery_policy.py`,
   `workers/omp.py:1708 internal retry`, and `cloud/babysitter/launch.py:554
   managed conversion`, without exact symbols or allowed call/write edges.
   More concretely, it names `workers/_impl.py:7887 run_step_with_worker`,
   while the live baseline defines that symbol at line 8085; the brief repeats
   the stale 7887 reference (brief lines 137–151; matrix lines 183–205).
   Replace line-number authority with a symbol-qualified manifest (line
   numbers may be generated diagnostics), resolve every definition/import/call/
   write by AST, and list exact allowed and forbidden edges for all named
   adapters, profiles/overrides, ledger methods, and the maintenance-owned
   `PlanningControlBinding`. Include negative fixtures for each forbidden edge.
   Do not treat the future `provider_resilience.py` symbols' current absence as
   failure; the defect is that the acceptance manifest itself currently cannot
   be run deterministically.

6. **Provider evidence must carry `retryability_class` and
   `provider_failure_class` — ACCEPTED.**

   The frozen plan's `provider_exhausted` schema explicitly requires
   `retryability_class` (plan lines 1050–1061). The brief's provider-evidence
   object (lines 376–390) contains only `provider_failure_class`, even though it
   later supplies a mapping table. That is a direct packet-to-plan mismatch,
   not merely a preferred duplicate field. Add both fields to the typed
   evidence (or an explicitly versioned adapter record that losslessly carries
   both), with `retryability_class` retaining the broad adapter taxonomy and
   `provider_failure_class` restricted to T8 `availability|idle_timeout`.
   Validate the exact mapping before terminal writing: infrastructure/internal/
   worker-timeout, quota/auth/rate-limit/unsupported/context/bad-request, and
   unknown/conflict map to no T8 class and no `provider_exhausted`. Conflicting
   fields fail closed. Raw stderr/prose still cannot supply either field.

7. **Terminal/observation one-writer sequence and observation-ID ordering — ACCEPTED.**

   The packet correctly says the terminal is the semantic observation source and
   shows a single terminal writer followed by one linked observation (brief
   lines 419–447). But its typed outcome requires `provider_evidence.observation_id`
   before that terminal exists (lines 383–389), while the same packet says the
   observation ID is derived from the already durable accepted terminal (lines
   441–444). That is a circular ordering unless the atomic primitive's ID
   allocation is specified. Freeze one sequence: the canonical terminal writer
   appends the accepted terminal without a caller-supplied observation ID; then
   derive the deterministic observation ID from the committed terminal/event
   identity and append/link exactly one observation, or define an atomic ledger
   primitive that allocates the terminal identity before computing the
   observation ID and proves no circular payload. Update the typed schema to
   mark the observation ID as derived/post-terminal (or a clearly non-input
   placeholder), keep exactly one terminal writer and one observation-link
   writer, and require replay/cardinality tests for crash before/after each
   append. The terminal-derived projection remains the streak authority.

8. **Positive quota tests require inversion or explicit scope — ACCEPTED.**

   Frozen v1 rules prohibit fallback advancement for quota exhaustion
   (`arnold_pipelines/megaplan/data/instructions.md:180–186`), and the packet
   repeats that auth/quota are ordinary failures with no fallback or T8
   exhaustion (brief lines 529–537; matrix lines 419–424). The live suite still
   contains positive quota-advance expectations, including
   `test_fallback_chains.py::test_cross_family_advance_membership`,
   `test_worker_fanout_fallback.py::test_cross_family_quota_advances`, and
   `test_gpt56_execution_policy.py::test_launch_time_quota_advances_non_read_only_plan`.
   The brief only directs inversion of positive execute/loop-execute tests, so
   the packet does not establish how these contradictory tests are scoped.
   Add an exact disposition: invert/update every v1-reachable positive quota
   expectation to assert no advance, or label it pre-v1 legacy characterization
   and exclude it from NBF-06/A01–A38 and all gate evidence. The same scope must
   apply to auth and rate-limit cases. Do not broaden NBF-06 to quota fallback
   merely to preserve the current helper behavior.

9. **Authority and justification for 30/20/5/2/90 probe constants — MODIFIED.**

   The packet does now provide concrete values and formulas, so the original
   “no numeric policy” objection is no longer accepted. It does not identify
   why those values are authoritative or how a later policy revision is
   versioned. State that `NBF06-PROBE-V1` is an NBF-06 policy owned by the
   settled plan/packet and is not inherited from generic NBF-01 TTL or a
   provider SDK; record the operational rationale and safety relationships
   (`executor_deadline <= lease_ttl`, finite retry budget, and window cap).
   Specify that changes require a new policy version, updated vectors and
   replay compatibility rules, not an ambient configuration override. Keep
   injected monotonic time authoritative for decisions and UTC evidence-only.
   This does not require inventing a different number or sourcing a number from
   stale architecture research.

### Round-5 exact revision checklist

Before the next packet gate, the author must:

1. Add boundary vectors and a precise post-close retry schedule, including
   attempt-number scope, delay application, closure races, and retry-window
   cutoffs.
2. Reconcile `NBF06-RECEIPT-V1` with canonical `WorkerAdmissionReceipt`:
   preserve the existing admission ID/fields/derivation, or rename and bind a
   distinct provider-evidence receipt through the approved serializer.
3. Freeze the serialized `ExecuteFallbackUnsafe` transport/version and exact
   object-preserving conversion/re-raise path; retain broad-catch ordering.
4. Replace A38's line/category manifest with exact symbol-qualified
   definitions/imports/calls/writes, correct `run_step_with_worker`'s stale
   reference, and include all negative fixtures and ownership boundaries.
5. Add `retryability_class` to provider evidence alongside T8
   `provider_failure_class`, with the fail-closed mapping and conflict rules
   required by the plan.
6. Remove the pre-terminal observation-ID input and document the one-writer
   terminal → derived-ID → observation sequence, including atomic and crash
   replay variants.
7. Invert or explicitly exclude the identified positive quota/auth/rate-limit
   tests so frozen v1 gate evidence cannot pass contradictory behavior.
8. Record `NBF06-PROBE-V1` ownership, rationale, safety relationships, version
   migration rule, and deterministic numeric vectors without changing the
   selected values by fiat.
9. Rebind the next brief and matrix to this appended adjudication SHA after
   packet corrections; do not edit source, tasklist, status, or prior rounds in
   this artifact.

### Round-5 disposition

The manager disposition is **5 accepted, 3 modified, and 1 rejected**:
accepted are findings 3, 5, 6, 7, and 8; modified are 2, 4, and 9; rejected is
1. No finding authorizes quota fallback, a provider cache/store, a second
receipt authority, selector, scheduler, terminal writer, projection, journal,
signal door, or NBF-08 chain ledger.

## Round-6 adjudication

### Inputs and authority

The exact Round-6 inputs were verified as follows:

| Input | SHA-256 |
| --- | --- |
| `.oracle/briefs/nbf06-provider-resilience-implementation.md` | `0a85456518d44c0c3551391ac054a7bc7028db2da8d57fa93d471ee84439ce3c` |
| `.oracle/research/nbf06-acceptance-test-matrix.md` | `9a1f12b8eb158d53acd2151b7ccb1630f9a22faef86238d4a19efb73ea16b17d` |
| `.oracle/rework/nbf06-planning-review-adjudication.md` (prior) | `8275b63452cd8a53c73f5f640bceb9848c2483854bd98de8b1063ebbdae01527` |
| `.oracle/plan.md` | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| `.oracle/tasklist.md` | `a4f574ce02421226a0f4610ffc503918e54cd8b5f8ee28ca8e7805afaf1e3959` |
| live-source baseline | `887c25cf8fddcd14fde24fce49697b9c8b3188b0` |

Judgment follows the frozen plan/tasklist first, the matrix for A01–A38, the
settled packet, read-only research, and descriptive live source. A source or
test that is intentionally future work is not a packet defect. A contradiction
between a packet vector and its own schema, or between the packet and a frozen
plan field/order, is a packet defect.

### Finding-by-finding verdicts

1. **Deterministic attempt-2, expiry-boundary, and race probe schedule — REJECTED
   as fixed.**

   The alleged omission is no longer reproducible. The brief now fixes
   `NBF06-PROBE-V1` and gives vectors for pre-deadline hold, the exact deadline
   CAS, replay, executor deadline, inclusive lease expiry, retry-window end,
   attempt-1 closure, `next_retry_not_before`, attempt-2 eligibility, competing
   CAS, unknown durability, and the no-attempt-3 rule (lines 553–584). The
   matrix repeats those boundary rules (lines 458–484). This is sufficient
   planning determinism; implementation of the race fixture is future work.

2. **Truly literal A38 manifest, including new APIs/types/serializers/consumers,
   boundaries, and exact edges — ACCEPTED.**

   The matrix is now symbol-qualified for many existing adapters, but its
   manifest still omits required new surfaces from the packet contract:
   `ProviderEpochClaim`/`ProviderEpochBinding`, `ProbeExecutor`,
   `ProviderProbeResult`, `start_provider_probe_locked`,
   `record_provider_probe_result_locked`, `close_provider_probe_locked`, the
   observation/epoch reconciliation APIs, provider-evidence serializer/vector,
   `serialize_execute_fallback_unsafe` and
   `deserialize_execute_fallback_unsafe`, and the exact
   `WorkerAdmissionReceipt`/provider-evidence boundary. It also describes the
   permitted edges mostly as “only locked ledger/CAS calls” rather than listing
   each definition, import, call, and write edge. The packet's A38 claim cannot
   be mechanically reproduced from that manifest. Extend the allowlist with
   every required new type/function/serializer and each named consumer and
   maintenance-owned boundary; state the exact allowed call graph and ledger
   write primitives, forbidden edges, alias/import rules, and negative fixtures.
   Keep missing future symbols an implementation gap, not the reason for this
   verdict; the accepted defect is manifest incompleteness.

3. **Provider-evidence vector missing required fields — ACCEPTED.**

   The typed evidence schema now correctly requires both broad
   `retryability_class` and narrow `provider_failure_class` (brief lines
   409–463; matrix lines 111–132). However, the normative
   `NBF06-PROVIDER-EVIDENCE-V1` envelope and its 324-byte vector (brief lines
   372–412; matrix lines 385–412) list neither field. The vector therefore
   cannot serialize the very fields used to validate T8 eligibility and cannot
   be replay-equivalent to the accepted evidence. Add both fields in fixed
   order, with explicit raw values and a revised length/hash vector, and test
   conflicting/missing mappings. Do not replace the broad field with the T8
   class or infer either from stderr/prose.

4. **Versioned `provider_failure_key` formula — ACCEPTED.**

   The frozen plan requires
   `digest(provider_failure_key_version, phase, normalized selected spec,
   provider_failure_class, provider_epoch_identity)` (plan lines 1168–1181).
   The brief and matrix currently say only that the key is derived from phase,
   normalized spec, typed class, and epoch; neither freezes the version field,
   canonical key-byte framing, normalization/vector, or exact exclusions in
   the packet. Add a versioned key contract (for example an explicitly named
   NBF06 key version), fixed field order/encoding and normalization, a
   normative vector/hash, and the exclusion list: probe/result/timestamps,
   retry counts, live-membership digests, and ephemeral health observations.
   State that changed-precondition rekey/reset compares these exact bytes under
   the authoritative producer and that caller-forged keys, missing versions,
   and legacy records remain held/ordinary rather than inferred.

5. **Post-terminal observation ID versus pre-terminal outcome and receipt/evidence
   ordering — MODIFIED.**

   The packet now fixes the principal cycle: the terminal writer receives no
   caller-supplied observation ID, the committed terminal identity derives the
   observation ID, and the observation-link writer appends exactly once (brief
   lines 441–448). It also marks the typed outcome's observation ID as derived
   after terminal commit. The remaining ordering is ambiguous because the
   provider-evidence envelope contains terminal ID and derived observation ID,
   while its provider-evidence receipt ID is described only as assigned “after
   the canonical reservation append” (lines 372–398). Define the complete
   order explicitly: adapter evidence digest and terminal evidence first;
   reservation/terminal append; observation-ID derivation from durable terminal
   identity plus evidence digest; observation link; then provider-evidence
   envelope/ID linkage (or an atomic primitive with the equivalent dependency
   proof). No digest may include its own receipt ID or derived observation ID;
   no terminal payload may require an ID not yet derivable. Preserve one
   terminal writer, one observation-link writer, matching replay, and the
   terminal-derived streak projection. This is a refinement of an otherwise
   repaired contract, not a request for a second writer.

6. **Epoch seam timing, receipt fields, derivation/exclusions, and fencing — MODIFIED.**

   The “epoch is produced after reservation” portion is not reproducible: the
   revised packet places the lock-captured `ProviderEpochClaim` in the existing
   admission authority after liveness/membership validation and atomically with
   the reservation (brief lines 272–305), with explicit binding-pending crash
   handling (lines 307–319). But the canonical `WorkerAdmissionReceipt` field
   list (lines 351–370) does not include `provider_epoch_identity`, while the
   packet separately says the post-commit admission receipt contains it (lines
   292–297). It also names claim/binding fields without a versioned derivation
   formula or a complete exclusion/fence contract. Resolve this inconsistency by
   stating whether epoch binding is an additive field of the existing canonical
   receipt or a separately named, receipt-linked binding envelope owned through
   the NBF-01 serializer. Freeze its exact producer call point, claim/binding
   bytes and digests, derivation inputs/exclusions (no wall clock, caller string,
   inferred current configuration, or unbound membership refresh), and locked
   stale/replaced/wrong-family/spec/forged fence result. Do not let NBF-06
   redefine the existing receipt authority.

7. **Missing post-terminal configured-fallback decision versus pre-tool-only
   cross-family/same-route child — ACCEPTED.**

   The packet has `PreToolNextTarget`, `PostTerminalRecoveryChild`, and
   `PostTerminalReturnPrimary`, and says only the pre-tool variant may select a
   target (brief lines 172–207). Yet the frozen plan requires, after the second
   matching observation, `_advance_configured_spec_fallback` to propose the
   configured alternate and the policy to return that target plus its
   authorizing observation (plan lines 1314–1326). No tagged decision variant
   currently carries that post-terminal cross-family candidate; the recovery
   variant is expressly same-route and the return variant is primary. Add an
   explicit `PostTerminalConfiguredFallbackChild` (or document a precisely
   equivalent variant) carrying the pure persisted-chain candidate, second
   observation authorization, source/target key and epoch, and composite-door
   proof. State that proposal is not selection/authorization/launch, that only
   the locked applier authorizes it, and that rejection/race/unknown state is
   zero-effect. Keep `PreToolNextTarget` as the only pre-tool target-selection
   variant and keep same-route recovery distinct from cross-family fallback.

8. **`durability_unknown` probe enum contradiction — ACCEPTED.**

   The packet simultaneously declares probe lifecycle exactly
   `active -> passed|failed|expired` and says an `unknown` result closes to
   `durability_unknown` (brief lines 530–551; matrix lines 441–456). It names
   `durability_state` but does not give its enum, and the same unqualified
   `durability_unknown` token is used in observation repair and epoch-binding
   domains. This is an internally contradictory state contract. Separate the
   dimensions and enumerate them: e.g. `ProviderProbeResult.result =
   passed|failed|unknown`; `ProbeLeaseState =
   active|passed|failed|expired|durability_unknown` (or an explicitly
   orthogonal closed-unknown state); and `ProbeDurabilityState` with exact
   values. Name the event for unknown, define replay/closure and reconciliation,
   and distinguish probe unknown from observation/epoch durability unknown in
   schemas and route eligibility. Unknown must remain held, non-retrying,
   non-streak-mutating, and unable to authorize a child.

### Round-6 exact revision checklist

1. Expand A38 to enumerate every required new API/type/serializer, consumer,
   boundary, import/call/write edge, alias rule, forbidden edge, and negative
   fixture; keep it symbol-qualified and mechanically resolvable.
2. Add `retryability_class` and `provider_failure_class` to the normative
   provider-evidence serialization and publish a corrected vector/hash.
3. Freeze the versioned provider-failure-key bytes/formula, normalization,
   exclusions, vector, and authoritative rekey/fence behavior.
4. Publish one non-circular terminal → observation-ID → observation-link →
   provider-evidence receipt ordering, including the atomic-ledger alternative
   and crash/replay cardinality proof.
5. Resolve epoch binding's receipt ownership/field placement and freeze its
   producer, versioned derivation, exclusions, stored bytes, and stale/forged
   fence outcomes.
6. Add or precisely define the post-terminal configured-fallback decision
   variant, with cross-family candidate versus same-route recovery distinction,
   locked composite authorization, and zero-effect rejection/race behavior.
7. Separate probe result, lease lifecycle, and durability enums; name unknown
   events and exact reconciliation/replay transitions.
8. Rebind the next brief and matrix to this appended adjudication SHA after
   corrections. Do not edit source, tasklist, status, or prior rounds in this
   artifact.

### Round-6 disposition

The manager disposition is **5 accepted, 2 modified, and 1 rejected**. Accepted
are findings 2, 3, 4, 7, and 8; modified are 5 and 6; rejected is 1. The
accepted findings are packet-level reproducibility/authority defects, not
implementation-absence claims. No finding authorizes a provider cache/store,
second selector, scheduler, terminal writer, projection, journal, signal door,
quota fallback, or NBF-08 chain ledger.

## Round-7 adjudication

### Inputs and authority

The exact Round-7 inputs were verified:

| Input | SHA-256 |
| --- | --- |
| `.oracle/briefs/nbf06-provider-resilience-implementation.md` | `361e4a028033c232e94d164912860023a396ce2c7c228f77ee93309af7365fdd` |
| `.oracle/research/nbf06-acceptance-test-matrix.md` | `369751d353432993278f9dbaaa9e0014f5b8cee7b3f04316acab5ab373ceb4a5` |
| `.oracle/rework/nbf06-planning-review-adjudication.md` (prior) | `d375f9fea87df049a12e1375c6f467bc48c38b0f46520c9124ce445e6f8457af` |
| `.oracle/plan.md` | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| `.oracle/tasklist.md` | `a4f574ce02421226a0f4610ffc503918e54cd8b5f8ee28ca8e7805afaf1e3959` |
| live-source baseline | `887c25cf8fddcd14fde24fce49697b9c8b3188b0` |

The frozen plan/tasklist control ownership and existing receipt/terminal
contracts. The matrix controls A01–A38. The brief/matrix Round-6 amendments
are considered when deciding whether a Round-7 finding remains reproducible.
Current absence of the proposed provider-resilience module or tests is an
implementation gap, not a planning defect.

### Finding-by-finding verdicts

1. **Observation/evidence ID circularity and pre-terminal `DispatchOutcome` —
   REJECTED as fixed.**

   The Round-6 amendments now state the dependency explicitly: accepted adapter
   evidence, reservation/terminal commit, terminal-ID-plus-evidence observation
   ID derivation, one observation link, then provider-evidence receipt linkage
   (brief lines 975–982; matrix lines 725–732). The typed outcome marks
   `observation_id` derived after terminal commit and not an input (brief lines
   419–427; matrix lines 125–132). The provider-evidence vector includes the
   derived field only in its post-terminal envelope. This addresses the alleged
   cycle. Future implementation must preserve it, but the prior finding is not
   still a packet blocker.

2. **Canonical receipt owner/path and missing epoch/chain fields/additive
   serializer — MODIFIED.**

   Ownership is now clear: `WorkerAdmissionReceipt` remains the NBF-01/NBF-02
   canonical result and NBF-06 cannot create a receipt authority (brief lines
   351–370 and 986–988). The packet also says the existing serializer gains
   `provider_epoch_identity` (brief lines 986–997; matrix lines 741–743).
   However, the enumerated canonical receipt fields do not list either
   `configured_fallback_chain_identity` or `provider_epoch_identity`, despite
   earlier text saying chain identity is carried on the admission receipt and
   the amendment saying epoch is added through that serializer. Freeze one
   exact owner/path and additive schema version: list both fields (or define a
   separately named, receipt-linked binding extension owned by NBF-01), their
   null/required rules, serializer and replay behavior, and the precise fields
   carried by terminal/observation/probe/child events. Preserve the existing
   admission receipt ID derivation; the provider-evidence envelope must remain
   distinct. This is a consistency gap, not permission for NBF-06 to redefine
   the canonical receipt.

3. **Cross-family pre-tool-only versus post-terminal configured fallback —
   REJECTED as fixed.**

   The packet now adds `PostTerminalConfiguredFallbackChild` as a tagged pure
   persisted-chain cross-family candidate with second-observation
   authorization, source/target key and epoch, index/spec, and composite-door
   proof; it is distinct from same-route recovery and is authorized only by
   the locked applier (brief lines 1002–1007; matrix lines 748–754). The
   `PreToolNextTarget` restriction remains intact. The higher plan's proposal
   step is therefore represented without making post-terminal proposal a
   second selector. Missing implementation of the new variant is future work.

4. **A38 exact symbols, serializers, consumers, boundaries, and edges —
   ACCEPTED.**

   The amendment materially expands A38, but it still does not form a truly
   closed mechanical manifest. It names `ProviderProbeResult` and the lease/
   durability enums but omits the required `ProbeExecutor` type/owner and its
   evidence-producing adapter; it does not name provider-evidence, epoch-claim,
   epoch-binding, or canonical admission-receipt serializer functions; and it
   gives no exact `ProviderLedgerView` fields/constructor/producer. It lists
   both `append_provider_observation` and `append_provider_observation_link`
   alongside the atomic terminal/observation API without specifying whether
   they are legacy compatibility writers, repair-only writers, or forbidden
   direct NBF-06 edges. “Adapter -> selector -> applier -> named methods” is
   still too coarse to prove the exact imports/callers and terminal-writer
   edges. Complete A38 with every required type/function/serializer and exact
   producer/consumer path, including `ProbeExecutor`, `ProviderLedgerView`,
   epoch/evidence/receipt serializers, `DispatchOutcome` adapters, and all
   observation/terminal APIs. For each, enumerate allowed definitions,
   imports, calls, and writes; explicitly forbid direct legacy observation
   writes except a named repair path; and include negative fixtures for
   generic `append_event`, unlocked ledger calls, duplicate writers, and
   unlisted aliases. The current source not having these future APIs remains
   implementation absence, not the accepted reason.

5. **Epoch claim/binding domain, order, digest, exclusions, vectors, and fence —
   MODIFIED.**

   The amendment fixes the producer location and order (locked liveness/
   membership validation, pre-commit claim, reservation, post-commit binding)
   and gives claim fields/exclusions and stale/forged fence outcomes (brief
   lines 984–1000; matrix lines 734–746). It still supplies no normative claim
   or binding domain tags, exact U64BE field order, digest formulas, or byte
   vectors/hashes comparable to the chain, provider-evidence, and failure-key
   vectors. Freeze versioned `ProviderEpochClaim` and `ProviderEpochBinding`
   serializations, including the exact `provider_epoch_identity` derivation,
   claim/binding digest inputs, reservation/receipt linkage, and explicit
   exclusions. Require vectors and replay byte comparison. Keep the lock fence
   fail-closed for stale/replaced/wrong-family/spec/forged/mismatched values,
   with `epoch_binding_pending`/durability-unknown held and no launch/probe/
   child. Do not move the producer after reservation or derive epoch from
   current configuration, wall clock, caller strings, or unbound refresh.

6. **`ProbeExecutor` owner/evidence source and `ProviderLedgerView` schema —
   ACCEPTED.**

   The packet defines the call shape `ProbeExecutor.run(request, deadline,
   cancellation_token)` and names `ProviderLedgerView` in the selector request,
   but it does not identify who constructs either value, which typed evidence
   source is authoritative, or the complete view fields used by the pure
   selector. The plan requires policy decisions to consume authoritative
   ledger projection/CAS state, and no provider client/tool/worker launch may
   occur in a probe. Freeze: the sole probe-executor interface and owning
   adapter; the typed provider-evidence producer and binding to the accepted
   terminal/lease; the complete immutable `ProviderLedgerView` fields and
   version; and the rule that it is a read snapshot supplied to the pure
   selector, never a caller-created route authority. Unknown/missing/conflicting
   view or evidence yields `Unresolved` with no write/launch. This is a packet
   schema/authority gap, not a demand that the source already contain the new
   types.

7. **Pending/committed/reconciled states versus canonical
   `provider_observation` projection/count — MODIFIED.**

   The state machine now distinguishes pending, committed-projection-unknown,
   repaired, conflict, and durability-unknown and says the terminal-derived
   projection is authoritative (brief lines 503–528; matrix lines 425–439).
   It still does not give a literal projection rule tying each event/state to
   the canonical `provider_observation` record and streak count. In
   particular, “append `provider_observation_committed`” could be read as a
   second count unless the ledger mapping is explicit, and the role of
   `provider_observation_reconciled` in count materialization is not stated.
   Add a cardinality table: one accepted terminal produces one canonical
   observation/count input; pending/committed/reconciled records are linkage or
   repair events and never additional count inputs; projection-unknown and
   durability-unknown count as held/unresolved; conflict is permanent hold;
   only exact replay of the terminal/evidence/link can materialize the one
   observation. State which single ledger primitive/writer performs each
   transition, how legacy `append_provider_observation` is scoped, and assert
   one observation and one streak increment across crash/replay/CAS races.

### Round-7 exact revision checklist

1. Add `configured_fallback_chain_identity` and `provider_epoch_identity` to
   the canonical receipt field/serializer contract, or define an explicit
   NBF-01-owned linked extension; preserve canonical receipt ID derivation.
2. Make A38 a closed AST manifest: add `ProbeExecutor`, `ProviderLedgerView`,
   all evidence/epoch/receipt serializers, exact producers/consumers, legacy
   observation-writer scope, generic `append_event` rules, and every allowed/
   forbidden import/call/write edge with negative fixtures.
3. Publish versioned epoch claim/binding domain/field order/digest formulas,
   exclusions, normative vectors, replay comparison, and lock-fence outcomes.
4. Freeze the sole probe executor/evidence producer and complete immutable
   `ProviderLedgerView` schema/version; fail closed on caller-created or stale
   snapshots.
5. Map pending/committed/reconciled/unknown/conflict events to the canonical
   provider-observation projection and count, with one-writer/cardinality and
   crash/replay/CAS assertions.
6. Rebind the next brief and matrix to this appended adjudication SHA after
   corrections. Do not edit source, tasklist, status, or prior rounds in this
   artifact.

### Round-7 disposition

The manager disposition is **2 accepted, 3 modified, and 2 rejected**.
Accepted are findings 4 and 6; modified are 2, 5, and 7; rejected as fixed are
1 and 3. The accepted findings are packet-level reproducibility/authority
 defects; they do not convert future implementation absence into a gate
 failure. No finding authorizes a provider cache/store, second selector,
 scheduler, terminal writer, projection, journal, signal door, quota fallback,
 or NBF-08 chain ledger.

## Round-8 manager adjudication

### Inputs and authority

This round was adjudicated against the exact packet inputs below. The brief
and matrix are the authority for the planned NBF-06 contract; the frozen plan
and tasklist remain scope controls; live source is descriptive until the
planned implementation begins. A PASS review is not accepted as proof by
itself, and a REWORK review is not accepted merely because planned symbols or
tests are absent from the current source.

| Artifact | SHA-256 |
| --- | --- |
| Brief `.oracle/briefs/nbf06-provider-resilience-implementation.md` | `9159a670d8b0df3e794d3404bb27bfdba7ecc8b8d749805f0c0665c76fc05e4a` |
| Matrix `.oracle/research/nbf06-acceptance-test-matrix.md` | `41306c0c3c4eaf5c92035327176577f5790a02f9498c56e8f7ab74f7a55e68cb` |
| Prior adjudication before this append | `3e3417be8afa3e3dbfd20dcaacf061489ad8a6cc4c51973450d7af5fbfd27d8b` |
| Frozen plan | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| Frozen tasklist | `a4f574ce02421226a0f4610ffc503918e54cd8b5f8ee28ca8e7805afaf1e3959` |

The live-source check confirms that the current ledger still exposes generic
`append_provider_observation`, `append_probe_result`, `create_probe_lease`,
and `append_event` paths (`incident/ledger.py:1326-1379`), and the current
`WorkerAdmissionReceipt` dataclass has no NBF-06 epoch/chain extension fields
(`cloud/worker_dispatch.py:196-229`). Those are implementation facts, not
reasons to reject a planning deliverable. The findings below are limited to
packet ambiguity or missing acceptance authority.

### Finding-by-finding verdicts

1. **Precommit adapter evidence versus postcommit envelope/
   `DispatchOutcome` — MODIFIED.**

   The packet correctly separates the NBF06 provider-evidence envelope from
   `WorkerAdmissionReceipt` and fixes its post-reservation fields
   (brief:373-387; matrix:387-401). It also says that accepted adapter evidence
   is serialized before reservation/terminal commit and that observation and
   provider-evidence IDs are derived later (brief:911-920; matrix:789-795).
   However, the contract still uses “accepted adapter evidence,”
   `DispatchOutcome.provider_evidence`, `terminal_provider_evidence_id`, and
   `provider_evidence_receipt_id` without defining the staged types and their
   owner. The `DispatchOutcome` field list includes a post-terminal
   `observation_id` and an unexplained `terminal_provider_evidence_id`
   (brief:415-429), while the envelope requires terminal and observation IDs.
   A worker cannot be required to supply values that only exist after the
   terminal commit, and the two evidence IDs must not silently become aliases.

   Preserve the fixed dependency order, but add a literal schema table: a
   precommit adapter-evidence type containing only accepted-launch, typed
   failure, receipt/chain/epoch/key, and raw evidence-digest inputs; the
   terminal writer's accepted input; the postcommit
   `ProviderEvidenceEnvelope`; `terminal_provider_evidence_id` assignment;
   `provider_evidence_receipt_id` assignment; and the exact link events. State
   whether `DispatchOutcome` is the precommit object, the postcommit returned
   view, or two explicitly named representations. No precommit object or
   terminal digest may require `observation_id` or either postcommit receipt
   ID; replay must compare each staged object with its own serializer.

2. **Canonical decision union, current amendment, and cross-family timing —
   MODIFIED.**

   The primary selector declaration enumerates variants at brief:176-196 but
   omits `PostTerminalConfiguredFallbackChild`. The later Round-7 text adds
   that child and distinguishes it from `PostTerminalRecoveryChild`
   (brief:1139-1144; matrix:749-755), so the finding that the concept is wholly
   absent is rejected. The reproducible defect is precedence: the packet's
   “exactly these variants” declaration and the later amendment are not one
   consolidated current union, and the amendment remains bound to the prior
   adjudication rather than this Round-8 correction. The text also leaves the
   timing boundary between a pre-tool cross-family `PreToolNextTarget` and a
   post-terminal configured child implicit: the child carries “second matching
   observation” but does not state the complete parent state and proof that
   must precede it.

   Add a Round-8-bound authoritative union replacing the earlier declaration,
   including `PostTerminalConfiguredFallbackChild`, and state that only
   `PreToolNextTarget` can select before a tool/launch. Define the configured
   child as a post-terminal composite-door proposal whose source terminal,
   observation/probe or second-observation authorization, chain index, source
   and target key/epoch, and lock snapshot are already proven; it must not be
   reached by pre-tool selection or by a provider-class shortcut. Record the
   exact cross-family timing and zero-effect outcomes for stale, rejected, and
   competing proposals.

3. **Text versus raw digest validation and binding equality — MODIFIED.**

   The packet now gives the right direction: chain framing uses raw
   `SHA256(origin_bytes)` and exact 32-byte fields (brief:321-333), epoch
   identity/claim/binding use versioned U64BE framing and vectors
   (brief:969-997), and the lock compares claim and binding against
   authoritative state (brief:292-305). Thus a review alleging that no raw
   digest contract exists is overbroad. It is still not mechanically explicit
   at every boundary which values are raw bytes, which are textual hex
   renderings, and what equality is checked before a child or evidence link.
   “Compare the binding” does not enumerate equality of family, normalized
   spec, route liveness identity/digest, membership snapshot, generation,
   epoch identity, claim digest, reservation ID, and receipt ID.

   Add a shared validation table for all serializers: UTF-8/NFC text fields,
   raw 32-byte digest fields, display-only hex, and rejection of hex text where
   raw bytes are required. Define binding equality as field-by-field equality
   to the stored claim/reservation/receipt plus recomputed claim and binding
   digests, under the ledger lock. Add tamper vectors for text/bytes
   substitution, field omission, wrong family/spec, and mismatched receipt or
   reservation; do not create a second identity scheme.

4. **Durable `provider_hold`/`provider_success` events, schemas, writers, and
   projection — ACCEPTED.**

   The matrix requires success reset and keyed projection behavior (matrix
   NBF06-A16 and T2, lines 87 and 552-553), and the brief says probe/wait and
   recovery events must not increment the streak (brief:1001-1010). Neither
   current contract, however, defines durable `provider_hold` or
   `provider_success` event kinds, their required payloads, a sole writer, or
   how they project into the canonical observation/streak state. The A38
   manifest names observation and probe methods but no hold/success schema or
   explicit projection edge. This is a packet-level omission, not a complaint
   that the source has not implemented future events.

   Add versioned schemas and a state/event table for both events: required
   terminal/observation/receipt/chain/epoch/key/evidence fields, deterministic
   IDs, producer, sole locked writer, replay/conflict behavior, and projection
   effect. State explicitly that hold is zero-count/held and success resets
   only the matching canonical key, never creates an observation, and never
   authorizes a child by itself. Add both symbols and their producer ->
   serializer -> locked applier -> projection edges to A38, while forbidding
   direct generic append and duplicate writers.

5. **Target epoch/key fields, derivation, locked check, and child vector —
   ACCEPTED.**

   The packet requires `reserve_provider_route_child` to validate a target
   epoch/key (brief:590-595), and the post-terminal child prose says it carries
   source/target key and epoch (brief:1139-1143). Matrix A28 only states the
   behavioral outcome that the target supplies its own epoch/key (matrix:98-99).
   Neither authority gives the child event's literal target field names and
   types, the derivation from the target admission claim, the exact locked
   comparisons, or a normative child-path byte vector. Without those details,
   “target has its own epoch/key” can be implemented as inherited source
   identity or an unchecked caller string.

   Add target fields to the canonical `PostTerminalConfiguredFallbackChild`
   and `provider_route_child_reserved` contract (target family, normalized
   spec/index, target provider-failure key, epoch claim/binding identity and
   digests, chain identity, and target admission/receipt proof as applicable),
   with exact derivation and U64BE serializer/vector. Under the existing lock,
   compare the proposal to the persisted target admission record and reject
   source inheritance, stale/replaced/forged target proofs, and CAS races with
   no child, receipt, launch, or projection effect.

6. **Canonical receipt storage of chain/origin/epoch bytes and digests —
   MODIFIED.**

   The packet says that canonical chain and provenance-origin bytes, not only
   digests, are persisted in reservation and receipt payloads (brief:321-334),
   and that exact epoch claim/binding payloads are persisted
   (brief:1111-1117; matrix:327-329). It also gives the receipt's identity
   fields and says the existing receipt ID derivation is preserved
   (brief:365-385). What remains ambiguous is the literal storage contract:
   the receipt field list names identities but not raw chain/origin/claim/
   binding byte fields or an NBF-01-owned linked extension, and no omission,
   null, serializer-version, or replay rule says where those bytes are read.

   Keep `WorkerAdmissionReceipt` as the sole owner and preserve its ID
   derivation, but specify an additive serializer extension (or a named
   immutable NBF-01-linked payload) containing canonical chain bytes, origin
   bytes, origin digest, epoch claim bytes/digest, epoch binding bytes/digest,
   and their versions. Define legacy nullability, accepted-provider required
   values, exact byte comparison on replay, and the prohibition on deriving
   bytes from current configuration. The provider-evidence envelope remains a
   distinct payload and must link rather than replace this receipt.

7. **A38 per-symbol producer -> serializer -> applier -> ledger edges and
   generic `append_event` conflict — ACCEPTED.**

   The Round-7 manifest materially improves symbol coverage, naming
   `ProbeExecutor`, `ProviderLedgerView`, evidence/epoch serializers, receipt
   serializers, and legacy observation methods (brief:924-965; matrix:797-836).
   It still describes the allowed graph at a category level (“adapter -> pure
   selector -> locked applier -> named methods”) and does not give a row for
   each new symbol's exact producer, serializer, consumer, and ledger write.
   It also lists generic `append_event` in the inherited manifest while
   forbidding direct provider-policy use, without specifying how the checker
   distinguishes unrelated generic callers from a forbidden NBF-06 edge. The
   same gap remains for the hold/success events and the target epoch/receipt
   serializers above. This is a reproducibility defect in the planned A38
   checker, not a demand that the live source already contain these symbols.

   Replace category prose with a closed table containing every allowed
   definition/import/call/write edge: adapter evidence producer; each
   serializer and inverse; epoch claim/binding producer; `ProbeExecutor` and
   evidence producer; `ProviderLedgerView` producer; pure selector; locked
   applier; terminal/observation/hold/success/probe/child writers; and
   receipt storage. Mark `append_event` as forbidden to NBF-06 policy while
   allowing only explicitly listed unrelated generic consumers. Include
   negative fixtures for direct append, unlocked calls, duplicate writers,
   caller-created views, missing serializers, and unlisted aliases. Require
   separate definition/import/call/write diagnostics and the exact A38 pass
   line.

### Round-8 exact revision checklist

1. Add the staged precommit-adapter versus postcommit-provider-evidence schema,
   including the owner and assignment point for both evidence IDs and a
   `DispatchOutcome` representation that cannot require postcommit IDs early.
2. Publish a Round-8-bound authoritative `ProviderRouteDecision` union with
   `PostTerminalConfiguredFallbackChild`, and freeze its cross-family timing,
   parent proof, and zero-effect races.
3. Add one raw-bytes/text validation and binding-equality table, with tamper
   vectors proving field-by-field claim, binding, reservation, receipt, and
   target equality under the lock.
4. Define durable `provider_hold` and `provider_success` schemas, event IDs,
   sole writers, projection/count effects, replay/conflict rules, and A38
   edges; hold is held/zero-count and success resets only its matching key.
5. Add exact target child epoch/key fields, derivation, lock comparisons,
   serializer and normative vector; prohibit inherited source identity.
6. Specify the NBF-01-owned additive receipt storage for canonical chain,
   origin, epoch claim/binding bytes and digests, including version/null/
   migration/replay rules and stable receipt-ID derivation.
7. Replace A38 category prose with a literal per-symbol producer ->
   serializer -> consumer/applier -> ledger edge manifest, explicitly
   classifying generic `append_event` and all legacy observation writers.
8. Rebind the corrected brief and matrix to this Round-8 adjudication SHA;
   do not edit source, frozen plan/tasklist, status, or prior adjudication
   rounds.

### Round-8 disposition

The manager disposition is **2 accepted, 5 modified, and 0 rejected**.
Accepted blockers are findings 4 and 5. Findings 1, 2, 3, and 6 are real
contract ambiguities requiring exact amendments; finding 7 is a reproducible
A38-manifest defect. The later Round-7 prose fixes the existence of the
configured post-terminal child and the existence of raw digest vectors, so
those narrower “wholly absent” claims are not accepted. No disposition
authorizes a provider cache/store, second selector, scheduler, terminal
writer, projection authority, journal, signal door, quota fallback, or NBF-08
chain ledger.

## Round-9 manager adjudication

### Inputs and authority

This definitive pass uses the exact current packet and the prior adjudication
as follows. The frozen plan/tasklist still control scope; the brief and matrix
control the planned NBF-06 contract and A01-A38 registry; live source is
descriptive until implementation. “One PASS/four REWORK” is not a vote: each
REWORK claim was checked against the current text, and implementation absence
was not counted as a defect.

| Artifact | SHA-256 |
| --- | --- |
| Brief `.oracle/briefs/nbf06-provider-resilience-implementation.md` | `3cb6deeb11a76145dd780686a83adaa149c4df44e1503e828e6df8ab5a379d4b` |
| Matrix `.oracle/research/nbf06-acceptance-test-matrix.md` | `d78a13e2dbba1b89dbd05c7be214cb84938cb637d285f9ca91cbb779ea387be3` |
| Prior adjudication | `48e64b618cb1a8bccb40744b2d6d46416d7f77c2eedab11328f4b175494f80a7` |
| Frozen plan | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| Frozen tasklist | `a4f574ce02421226a0f4610ffc503918e54cd8b5f8ee28ca8e7805afaf1e3959` |

The live-source observation is unchanged and intentionally non-blocking: the
current `WorkerAdmissionReceipt` is defined in `cloud/worker_dispatch.py`
and generic ledger methods remain in `incident/ledger.py`. That is expected
preimplementation drift, not evidence that the plan must edit those files in
this adjudication.

### Finding-by-finding verdicts

1. **Grouped or missing A38 symbols and producer/serializer/applier/ledger
   edges — ACCEPTED.**

   Round-8 added useful rows for the precommit evidence, receipt, epoch,
   envelope, view, probe, hold/success, observation, configured child, and
   refusal. It still groups symbols that the gate must resolve literally
   (`ProbeExecutor/Result`, `ProviderEpochClaim/Binding`, `provider_hold/success`)
   and omits a row for `DispatchOutcomeCommitted`, its inverse/bridge, the
   exact hold/success serializers, target-child serializer, and the concrete
   terminal/evidence-link writer edges (brief:1267-1287; matrix:982-1002).
   “Adapter -> serializer -> applier” is not enough for an AST checker to
   identify definitions, imports, calls, and writes or to distinguish a
   proposal from a writer. Generic `append_event` is named as forbidden, but
   the allowlisted unrelated callers and the exact exclusion rule remain
   nonliteral.

   Close A38 with one row per type, function, inverse, producer, consumer,
   applier, and write. Include `DispatchOutcome`/`DispatchOutcomeCommitted`,
   precommit/terminal/postcommit serializers, provider evidence and epoch
   serializers, `ProbeExecutor` and result producer, hold/success event
   serializers and writers, target-child serializer, canonical receipt
   extension, and every terminal/observation/link/reconciliation method. Give
   exact file-qualified symbols and allowed edges, classify generic
   `append_event` per caller, and retain negative fixtures for direct or
   unlocked writes. This is a planning reproducibility blocker, not a demand
   that the current source already define future symbols.

2. **Probe versus second-observation authorization — MODIFIED.**

   The packet correctly distinguishes same-route recovery from the configured
   cross-family child and requires a matching probe or second-observation
   authorization (brief:1189-1198; matrix:911-919). The “or” is still
   under-specified: it does not identify which parent state, event sequence,
   and key/epoch proof authorizes each branch, nor does it say whether a
   passed probe is necessary, sufficient only with a recovery event, or
   irrelevant to the second-observation path. A probe result must not itself
   authorize an identical retry, while a second accepted matching observation
   must not be confused with a probe lease.

   Add a disjoint transition table: first observation -> hold/probe -> one
   same-route recovery child; accepted matching child exhaustion -> observation
   two; and only the explicitly configured post-terminal cross-family child
   path, with its own authorization proof. Name the required event IDs and
   source/target key/epoch checks for each branch, and assert that a probe
   success alone, volatile liveness/membership changes, or an observation
   count alone cannot authorize either child.

3. **`provider_success` linkage and reset authority — ACCEPTED.**

   The new success schema has `admission_receipt_id`, chain, epoch, key,
   evidence digest, reason, and state, and says it resets the matching key
   (brief:1231-1238; matrix:948-953). Unlike `provider_hold`, it has no
   `terminal_event_id` or `observation_id` (or an explicitly named parent
   success proof), and the packet does not state which accepted terminal or
   canonical observation it closes. A receipt/key/evidence tuple by itself
   can be replayed against the wrong parent and reset unrelated projection
   state. The sole writer name is not a linkage contract.

   Add the authoritative parent terminal/observation linkage (or an explicit
   immutable success-proof type), exact required fields and digest, and the
   locked projection rule that only the matching canonical key/parent may be
   reset. Define replay/conflict and crash behavior and add A38 edges and
   positive/negative vectors. Success must remain zero-observation and
   zero-child by itself.

4. **Versioned precommit/terminal/postcommit schema bridge and migration —
   MODIFIED.**

   Round-8 now names `ProviderAdapterEvidencePrecommit`, `DispatchOutcome` as
   that representation, and `DispatchOutcomeCommitted` as a postcommit view
   (brief:1166-1187; matrix:896-909). This resolves the earlier type-stage
   ambiguity, but it does not specify schema versions for the bridge, how the
   existing serialized `DispatchOutcome`/terminal records decode, or how old
   records migrate without inventing postcommit IDs. The current terminal
   schema also has legacy compatibility fields (live
   `incident/schema.py:1101-1118`), so “additive” needs a precise boundary.

   Freeze versioned codecs and a migration matrix: old adapter/terminal
   payload -> precommit-compatible input, new terminal payload -> committed
   view, postcommit evidence envelope/link, and legacy ordinary/provider
   records. Require explicit null/omission rules, no generated observation or
   evidence ID for legacy records, byte-identical replay, and held/unresolved
   treatment for records that cannot be upgraded by proof. Keep one terminal
   writer and one evidence-link writer.

5. **Epoch one-append, binding-pending, liveness/membership rekey, and actual
   reservation owner seam — MODIFIED.**

   The packet says the claim is captured after liveness/membership validation,
   atomically stored with the reservation, and then receives a postcommit
   binding; a crash enters `epoch_binding_pending` and is repaired under the
   same lock (brief:279-319, 1107-1121; matrix:735-747). This is directionally
   coherent, but it does not state the physical invariant that there is one
   reservation append containing the claim and no standalone prepare/claim
   event, while the pending/reconciled events are repair metadata only. It
   also does not identify the exact reservation-owner function at the shared
   seam or define whether a changed liveness/membership snapshot creates a
   new epoch/rekey or merely makes the old claim stale.

   State the owner as the existing locked admission/reservation operation
   (with its file-qualified symbol), and state the one-append rule: claim and
   reservation are one durable reservation operation; binding/receipt repair
   is the only later append; no prepare record, second reservation writer, or
   inferred claim. Define rekey semantics for changed route liveness,
   membership, family, and spec: new admission claim only, old claim fenced,
   no mutation of an accepted claim, and unresolved on missing/stale proof.
   Add crash vectors for before reservation, after reservation-before-binding,
   and concurrent replacement under the existing lock.

6. **Child proposal versus postcommit IDs and one reservation writer —
   ACCEPTED.**

   The configured-child contract now lists both `target_admission_receipt_id`
   and `target_reservation_event_id` as fields of the pure proposal and says
   the locked door appends the child reservation (brief:1242-1253; matrix:
   963-973). The proposal therefore appears to require the reservation/receipt
   that the same child-door operation is supposed to create. If these are an
   already admitted target route, that ownership is not stated; if they are
   the new child reservation IDs, the proposal is circular. The packet also
   does not explicitly say which single writer assigns the child reservation
   and postcommit child receipt.

   Split the fields into precommit target-admission proof (existing target
   receipt/reservation, if that is intended) and postcommit child IDs assigned
   by `reserve_provider_route_child`. A pure proposal must never contain an ID
   produced by its own append. Define one locked child-reservation writer,
   postcommit receipt derivation, replay/CAS equality, and exact source/target
   linkage. Reject inherited source identity and any second child or receipt
   writer with zero effects.

7. **Probe executor outside the ledger lock, lease fencing, and result CAS —
   ACCEPTED.**

   The packet defines `ProbeExecutor.run(request, deadline, cancellation_token)`
   and says the locked applier owns effects, while the executor consumes a
   locked view/lease identity (brief:944-949; matrix:817-822). It never says
   whether `run` executes after releasing the ledger lock. Holding the lock
   across an executor call would block all reconciliation and make lease
   expiry/fencing non-deterministic; releasing it without a revalidation rule
   permits a late result from an expired, replaced, or concurrently consumed
   lease to mutate state.

   Specify: acquire/validate lease under lock; snapshot immutable request and
   fencing token; release lock for the bounded executor call; reacquire lock;
   CAS the result only when lease ID, parent terminal/reservation, key, epoch,
   route, attempt, deadline, and fencing token still match. A late/unknown/
   duplicate result records a typed held/durability outcome with no streak,
   child, retry, or launch effect. Add this ownership and edge to A38 and
   deterministic lock-release/reacquire race vectors.

8. **Receipt authority between cloud adapters and `incident/schema.py`, and
   additive fields/serializer — MODIFIED.**

   The packet consistently names NBF-01/NBF-02 and
   `incident/schema.py:serialize_worker_admission_receipt` as the receipt
   authority and calls cloud dispatch an adapter (brief:900-909; matrix:
   365-385). The live source still defines the dataclass in
   `cloud/worker_dispatch.py:196-229`, which is non-blocking before
   implementation, but the packet does not explicitly require cloud to
   consume/transport the canonical incident-schema object rather than define
   a parallel class. It also does not give the exact bridge for additive
   chain/epoch extension fields across cloud serialization.

   Add an authority statement and edge: incident/schema (NBF-01/02) defines
   the one class/codecs; cloud/worker_dispatch only adapts/round-trips it and
   may not derive, mutate, or redefine receipt IDs. Specify the additive
   extension's version/null rules, cloud transport representation, inverse
   decode, and byte/replay equality. Preserve the existing receipt-ID
   derivation and do not introduce a provider receipt authority.

9. **Child ownership — MODIFIED.**

   The packet correctly assigns proposal formation to the pure selector and
   says only the locked composite door may authorize it, with
   `reserve_provider_route_child` named as the door (brief:590-595,
   1242-1253; matrix:994). It does not explicitly assign ownership of the
   composite reservation schema/write to the existing generic ledger/admission
   owner versus the NBF-06 policy module, leaving room for a second child
   writer or for policy code to append directly.

   State the split literally: NBF-06 owns the pure decision and proof;
   the existing locked ledger/admission seam owns the sole
   `provider_route_child_reserved` append, child receipt assignment, and CAS;
   all callers are adapters. Add the file-qualified owner and forbid direct
   policy append, alternate child reservation, provider cache, or new journal.

10. **A09 volatile-change boundary — REJECTED as already covered.**

   Matrix A09 explicitly says time/sleep/membership/liveness changes and probe
   success alone cannot authorize an identical retry or reset/rekey
   (matrix:80). The packet separately requires persisted matching evidence,
   locked key/epoch checks, and a single-use recovery proof before a child
   (brief:590-595, 1146-1153). A demand for a new authority or a complaint
   that the live source does not yet implement this test is overreach. The
   transition-table clarification in finding 2 should make the existing A09
   boundary executable, but A09 itself is not an additional blocker.

### Round-9 exact closure checklist

1. Replace A38 grouping with a file-qualified row for every type, codec,
   producer, consumer, applier, writer, and edge, including committed outcome,
   hold/success, target child, probe, receipt extension, and generic-append
   exclusions.
2. Publish disjoint probe/recovery versus second-observation/configured-child
   transition tables with event IDs, key/epoch proofs, and “probe success alone
   is insufficient” vectors.
3. Link `provider_success` to its authoritative terminal/observation parent,
   define matching-key reset/count effects, and add replay/conflict writers.
4. Freeze versioned precommit -> terminal -> postcommit codecs and legacy
   migration/null rules with no inferred IDs or duplicate writers.
5. State the actual reservation owner and one-append epoch-claim invariant;
   prohibit prepare records and define liveness/membership rekey/fencing
   semantics and crash vectors.
6. Remove postcommit child reservation/receipt IDs from the pure proposal unless
   they are explicitly identified as an already-existing target-admission
   proof; assign new child IDs only in the sole locked child writer.
7. Specify executor lock release/reacquire, lease fencing token, result CAS,
   late-result handling, and the corresponding A38/race evidence.
8. Make `incident/schema.py` the sole receipt class/codec authority and cloud
   dispatch a transport adapter with additive extension/replay rules.
9. Name the existing generic ledger/admission owner of the sole child-reservation
   append and prohibit policy-side duplicate writes.
10. Rebind corrected brief/matrix to this Round-9 adjudication SHA. Do not edit
    live source, frozen plan/tasklist, status, or prior adjudication rounds.

### Round-9 disposition

The manager disposition is **4 accepted, 5 modified, and 1 rejected**.
Accepted blockers are findings 1, 3, 6, and 7. Findings 2, 4, 5, 8, and 9
are real contract/ownership ambiguities requiring exact closure amendments.
Finding 10 is rejected as already explicit in A09 and supported by the packet
boundary rules. No finding authorizes a provider cache/store, second selector,
new scheduler, second terminal/child writer, external journal, signal door,
quota/auth fallback, or NBF-08 chain-control surface.


## Round-10 manager adjudication

### Inputs and authority

This pass uses the exact Round-10 brief and matrix below, with the prior
adjudication as the amendment chain. The frozen plan/tasklist remain scope
controls. The packet is judged for a deterministic implementation contract;
absence of future code/tests in the live source is not a finding.

| Artifact | SHA-256 |
| --- | --- |
| Brief `.oracle/briefs/nbf06-provider-resilience-implementation.md` | `202dcf9e4177b243595b15b8b6e404631e7daa439d0ae73c5e18d2286e90473f` |
| Matrix `.oracle/research/nbf06-acceptance-test-matrix.md` | `fd0febf7caf1eeda17ce6c075324331a5bee4b25bf2e0f6112ee358aa45ff8a1` |
| Prior adjudication | `df920d301d81e03d9507e5720c081837218beaa5477b4a8505b1e7e1dd5fd39b` |
| Frozen plan | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| Frozen tasklist | `a4f574ce02421226a0f4610ffc503918e54cd8b5f8ee28ca8e7805afaf1e3959` |

### Finding-by-finding verdicts

1. **A38 final table remains grouped and non-file-qualified — ACCEPTED.**

   Round-9 adds a more complete table, but rows still group independent
   definitions and codecs (`DispatchOutcome`/`DispatchOutcomeCommitted`,
   `ProbeExecutor`/`ProviderProbeResult`) and use abstract labels such as
   “adapter,” “bridge,” “terminal,” “projection,” and “probe codec” rather
   than file-qualified symbols and inverse names (brief:1371-1395;
   matrix:1083-1105). It does not enumerate every writer edge for the
   precommit, accepted-terminal, postcommit envelope, hold/success, target
   child, receipt extension, or branch transition events. The statement that
   unrelated `append_event` callers must be listed is a requirement, not the
   list itself. This is a reproducibility blocker for A38, not a demand that
   the source already have the planned module.

   Replace the table with one row per file-qualified definition, codec and
   inverse, producer, consumer, applier, and write. Include exact terminal,
   observation, hold/success, probe, epoch, receipt, child, and transition
   symbols. Enumerate the permitted unrelated `append_event` callers and
   exclude all NBF-06 callers mechanically; report definitions/imports/calls/
   writes separately with negative fixtures and the exact A38 pass line.

2. **Stale 452-byte child vector versus the current committed field set —
   ACCEPTED.**

   The current Round-9 contract correctly removes IDs produced by the child
   append from the pure proposal and has the locked writer assign
   `child_reservation_event_id` and `child_admission_receipt_id`
   (brief:1349-1358; matrix:1064-1072). The only displayed 452-byte vector is
   inherited from Round-8 and encodes the older proposal fields, including
   target reservation/receipt IDs (brief:1255-1264; matrix:975-980). Round-9
   supplies no replacement bytes, length, or hash. A checker cannot know
   whether to validate the stale vector or the new proposal.

   Mark the old vector superseded and publish a new vector whose exact field
   order contains only the current pure proposal fields, with target admission
   proof and no IDs assigned by its own append. Separately publish the
   committed `provider_route_child_reserved` field vector, including newly
   assigned child IDs, and bind both to the current amendment. Add replacement,
   replay, and source-inheritance negative vectors.

3. **`provider_success` serialization and event identity — ACCEPTED.**

   The packet now provides the success field set and sole writer and links it
   to an exact terminal/observation parent (brief:1339-1347; matrix:1054-1062),
   but “deterministic ID is the hash of canonical fields” from Round-8 remains
   without a versioned byte domain, field order, raw/text rules, vector, or
   hash (brief:1225-1238; matrix:942-953). The same gap affects the
   hold-event identity. A stable event ID cannot be reproduced from a prose
   field set when serializer order or textual rendering is unspecified.

   Define `NBF06-PROVIDER-HOLD-V1` and `NBF06-PROVIDER-SUCCESS-V1` U64BE
   field order, digest coverage, required parent/receipt/key/epoch/evidence
   fields, ID formula, exact sample bytes and SHA-256, replay comparison, and
   conflict behavior. Keep hold zero-count and success matching-key reset;
   neither event may create an observation or child.

4. **Branch transition event/identity fields and vectors — ACCEPTED.**

   The transition table names the intended branch effects, and says recovery
   and configured fallback use disjoint IDs/proofs (brief:1322-1335;
   matrix:1038-1050). It does not define the durable event schemas or exact
   identity vectors for `provider_recovery_verified`, probe-to-recovery
   consumption, configured-child proposal, target admission, or the
   post-terminal return/hold branches. Nor does it specify which fields bind
   branch identity to parent terminal, observation, lease, chain, key, epoch,
   and receipt. Branch names alone permit event-ID collisions or cross-branch
   replay.

   Add a branch matrix with versioned event kind, required fields, deterministic
   ID formula, producer, sole writer, parent/child linkage, allowed effect,
   and exact bytes/hash vectors for each transition. Require distinct branch
   domains and proof fields, locked equality, idempotent replay, and zero
   effect on stale, wrong-branch, or competing events. Do not add a new store
   or scheduler to hold these events.

5. **Migration matrix, codec paths, and authority of the frozen
   `DispatchOutcome` — MODIFIED.**

   The Round-9 text now names V1 precommit, terminal, and provider-evidence
   codecs, says `DispatchOutcome` is precommit, gives a postcommit view, and
   requires explicit nulls for legacy records (brief:1295-1312;
   matrix:1020-1036). That resolves the prior broad bridge ambiguity. It still
   lacks a row-by-row migration matrix for existing `DispatchOutcome` dicts,
   terminal records, ordinary failures, provider terminals, and cloud
   transport, including which inverse codec is called and when an old record
   remains ordinary/held. It also does not explicitly state that this is an
   additive bridge satisfying the frozen typed `DispatchOutcome` decision,
   not a replacement that makes postcommit IDs mandatory at precommit.

   Add the migration matrix and file-qualified codec paths, with old/new
   schema versions, explicit null/omission/unknown handling, canonical byte
   comparison, and no inferred IDs. State that the frozen precommit
   `DispatchOutcome` contract remains fail-closed and the committed view is a
   separate additive result; legacy records cannot be upgraded without proof.

6. **Harmless liveness/membership refresh versus epoch replacement and A09 —
   ACCEPTED.**

   A09 says time/sleep/membership/liveness changes and probe success alone
   cannot authorize identical retry or reset/rekey (matrix:80). Round-9 says
   changed liveness or membership creates a new admission claim and fences the
   old one (brief:1362-1369; matrix:1074-1081), but does not distinguish a
   harmless refresh of a probe/ledger view from an authoritative route or
   membership generation change at the reservation seam. As written, a
   volatile membership refresh could appear to force a rekey, contradicting
   A09, or could be treated as harmless while changing the epoch inputs.

   Define the authoritative replacement predicate: only the locked route /
   membership generation or validated admission snapshot that changes the
   epoch claim replaces and fences it. Probe-time health, wall-clock, sleep,
   retry timing, and non-authoritative refreshes are harmless and cannot reset,
   rekey, or authorize a child. Add paired A09 vectors for harmless refresh
   and true generation replacement, including stale old-epoch rejection and
   no duplicate claim/reservation.

7. **Deterministic hold/success/observation IDs — ACCEPTED.**

   Observation identity is described as terminal/reservation/chain/key/epoch/
   evidence-derived and cycle-free (brief:444-496; matrix:418-427), while
   hold/success are named events with only prose hash requirements. None of
   the three has a complete common statement of domain tag, U64BE order,
   digest coverage, raw digest representation, and normative vectors in the
   current Round-9 authority. The old observation event IDs and the new
   hold/success IDs can therefore be generated differently by independent
   implementations, and replay/cardinality proofs cannot be byte-checked.

   Publish one deterministic-ID registry for `provider_observation`,
   `provider_hold`, and `provider_success`: version/domain, exact ordered
   fields, excluded postcommit IDs, raw/text encoding, digest formula, sample
   bytes and SHA-256, and collision/replay/conflict behavior. Bind each event
   to the authoritative terminal/receipt/key/epoch/evidence records and assert
   one observation/count input despite crash, repair, and CAS races.

### Round-10 exact closure checklist

1. Replace A38 prose/grouped rows with file-qualified per-symbol definitions,
   inverse codecs, producers, consumers, appliers, writers, and explicit
   unrelated `append_event` allowlist/exclusions.
2. Supersede the stale 452-byte proposal vector and publish separate current
   pure-proposal and committed-child field vectors with lengths/hashes.
3. Freeze versioned U64BE serializers, ID formulas, and vectors for hold and
   success events, preserving zero-count/reset semantics.
4. Add branch transition schemas/identity fields/vectors and disjoint replay,
   lock, and zero-effect rules for recovery/configured-child/return paths.
5. Add the complete legacy-to-V1 migration matrix and state the additive
   precommit `DispatchOutcome` / postcommit view authority explicitly.
6. Define the locked epoch replacement predicate versus harmless refresh and
   add paired A09 vectors; no volatile refresh may rekey or authorize.
7. Publish the common deterministic-ID registry and vectors for observation,
   hold, and success, including terminal/receipt/key/epoch/evidence binding.
8. Rebind the corrected brief and matrix to this Round-10 adjudication SHA;
   do not edit live source, frozen plan/tasklist, status, or prior rounds.

### Round-10 disposition

The manager disposition is **6 accepted, 1 modified, and 0 rejected**.
Accepted blockers are findings 1, 2, 3, 4, 6, and 7. Finding 5 is modified:
the staged codec concept is now present, but its migration/authority matrix
is not closed. Requirements that merely demand implementation, tests, or
global changes outside NBF-06 are rejected as overreach and are not included
above. No finding authorizes a provider cache/store, second selector,
scheduler, duplicate terminal/child writer, external journal, signal door,
quota/auth fallback, or NBF-08 chain-control surface.
## Round-11 manager adjudication

### Inputs and authority

This pass uses the exact current brief and matrix below and the immediately
prior adjudication. The frozen plan/tasklist remain the scope authority. A
brief or matrix that still names the preceding adjudication is not inherently
stale: revisions naturally precede the adjudication that reviews them. The
post-adjudication rebind is nevertheless required before the next freeze.

| Artifact | SHA-256 |
| --- | --- |
| Brief `.oracle/briefs/nbf06-provider-resilience-implementation.md` | `5f4cd42c334256effdaada27bee8b83284efe55334b21f436db5120494d78aba` |
| Matrix `.oracle/research/nbf06-acceptance-test-matrix.md` | `078ce1e683abbff1625058d34d7d75664be6c953f04a18dbc0228b5adc9bf9c3` |
| Prior adjudication | `95714c959d9ac0946330d4bfc701c26281ab86fe3e68e859d33dd228ebb9f363` |
| Frozen plan | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| Frozen tasklist | `a4f574ce02421226a0f4610ffc503918e54cd8b5f8ee28ca8e7805afaf1e3959` |

### Finding-by-finding verdicts

1. **Header/provenance binding and natural revision order — MODIFIED.**

   Both packet headers identify the preceding adjudication SHA
   `df920d...` (brief:18-20; matrix:20-22), while their Round-10 sections are
   explicitly bound to `95714c...` (brief:161-165; matrix:1107-1111). The
   current packet SHA therefore represents a revision made after the prior
   review, not proof of a stale-input failure. The reproducible issue is only
   that the packet's current “manager adjudication bound” line has not yet
   been advanced to the adjudication produced by this round.

   Preserve the chronology and update the brief/matrix binding only after this
   artifact is final; record the exact new SHA and do not rewrite historical
   round sections. The final rebind is a custody step, not a reason to reject
   the current review inputs.

2. **New vector lengths/hashes without literal ordered bytes and sample fields
   — ACCEPTED.**

   Round-10 supplies lengths and SHA-256 values for the current child,
   hold/success, and branch vectors but no literal byte payload or complete
   sample field tuple (brief:212-251; matrix:1149-1174). A digest cannot
   independently reproduce a serializer, and “U64BE-framed” does not identify
   field order, null encoding, or sample values. This is a planning contract
   blocker, not a demand that implementation tests already exist.

   Publish literal ordered bytes (or a named checked-in machine-readable
   vector fixture with its own hash) and the sample field values for each
   current vector. Include pure proposal and committed-child vectors, hold,
   success, recovery/configured-child/return branches, and observation IDs;
   state raw/text/null rules and mark every superseded vector explicitly.

3. **Hold/success field names and serializer agreement — ACCEPTED.**

   The brief uses `hold_event_id` and `success_event_id` in its ordered fields
   (brief:225-234), while the matrix's corresponding registry says generic
   `event_id` and generic `epoch`/`key` names (matrix:1161-1166). Earlier prose
   also uses a different shorthand for the same records. Since these fields
   participate in event IDs and replay, the discrepancy is semantic, not
   cosmetic: two implementations could produce different bytes while both
   claiming the stated SHA.

   Choose one canonical field vocabulary and repeat it identically in brief,
   matrix, schemas, inverse codecs, ID formulas, and vectors. Define whether
   the event-ID field is excluded from the hash input, how `chain_digest`,
   epoch, key, evidence, and parent IDs are encoded, and reject aliases as
   acceptance evidence.

4. **Transition/observation ID registry — ACCEPTED.**

   Round-10 gives branch names and hashes and says parent fields are lock-equal
   (brief:241-251), but it does not provide literal branch payloads or a
   deterministic ID registry for observation, recovery consumption,
   configured-child proposal, return-primary, and repair transitions. The
   observation prose still describes its inputs without a versioned domain and
   exact ordered bytes (brief:444-496). Event names and hash labels alone do
   not prevent cross-branch replay or ID collision.

   Add a registry row per transition and `provider_observation` with domain,
   version, ordered fields, parent/receipt/key/epoch/evidence binding,
   excluded postcommit IDs, ID formula, literal bytes/hash, producer, sole
   writer, and replay/conflict result. Require distinct branch domains and
   one observation/count input through repair and CAS races.

5. **Migration codec paths, mappings, and null rules — ACCEPTED.**

   The migration table names categories such as “legacy inverse,” “terminal
   inverse,” and “canonical receipt inverse/transport” but does not identify
   each file-qualified codec, input-to-output field mapping, schema version,
   or which explicit nulls are legal for legacy ordinary versus accepted
   provider records (brief:253-268; matrix:1176-1190). The statement that
   inverses are version-checked is not a migration matrix.

   Add a complete matrix for legacy `DispatchOutcome`, legacy ordinary and
   provider terminal events, V1 precommit/terminal/envelope, receipt transport,
   child records, and torn/unknown payloads. Name every codec and inverse,
   field mapping, omitted/null/unknown behavior, upgrade prohibition, and
   replay byte check. State that the frozen fail-closed precommit
   `DispatchOutcome` is not replaced by the postcommit view.

6. **Pure selector policy versus adapter door — REJECTED as already explicit.**

   The packet defines `select_provider_route(request, ledger_view)` as the
   pure policy API, assigns effects to
   `apply_provider_route_decision_locked`, and labels dispatch, memory, auto,
   batch, fanout, and loop paths as adapters (brief:280-326; matrix:144-175).
   The single configured selection authority and no-second-selector rule are
   also frozen in SD-001/SD-008 and A23. A demand that implementation absence
   prove this distinction now is out of scope; no new checklist item is
   warranted.

7. **`incident/schema.py` ownership versus NBF-01/NBF-06 task scope —
   MODIFIED.**

   The tasklist assigns typed schemas/strict serialization to NBF-01 and says
   NBF-06 must use NBF-01 ledger/projection/CAS (tasklist:75-113, 699), while
   the brief assigns the canonical receipt class/codecs to NBF-01/NBF-02 and
   cloud only transports them (brief:471-482, 1314-1320). Thus a finding that
   the packet may create a new NBF-06 receipt authority is rejected. The
   remaining ambiguity is execution ownership: additive receipt/epoch codecs
   are described in the NBF-06 contract but the synchronization handoff to
   the NBF-01 schema task is not stated.

   Record the split explicitly: NBF-01 owns implementation of the shared
   `incident/schema.py` class/codecs and generic ledger serialization; NBF-06
   owns provider policy and supplies only the frozen additive contract and
   integration tests. Cloud dispatch is a transport adapter and may not
   define or derive receipt IDs. No NBF-06 task may bypass the NBF-01 gate.

8. **Epoch/key exclusion of liveness and membership — REJECTED in the broad
   form; retain the settled boundary.**

   The frozen provider-failure key excludes volatile liveness, timing, probe,
   retry, and membership refresh fields (SD-005; tasklist:741 and 728-740),
   while an authoritative route/membership generation is intentionally an
   input to the epoch claim. The current packet now distinguishes harmless
   refresh from locked authoritative replacement and provides paired A09
   vectors (brief:270-278; matrix:1192-1198). Therefore “epoch/key must
   exclude all liveness/membership data” would contradict the settled fencing
   contract. Only non-authoritative refresh must be excluded; a validated
   generation change may create and fence a new epoch claim. No further
   scope is added.

9. **Child ledger event must omit receipt and derived postcommit view —
   ACCEPTED.**

   Round-10 correctly removes child IDs from the pure proposal, but its
   “committed” vector explicitly adds assigned child reservation and receipt
   IDs (brief:214-223; matrix:1151-1159), while the frozen tasklist says the
   composite event contains no child receipt-ID input and receipt identity is
   derived after append (tasklist:149-150). The current contract does not
   distinguish an event payload from a postcommit view, so this is a direct
   contradiction that can reintroduce circularity.

   Make `provider_route_child_reserved` contain only pre-append source/target
   proof and its event/reservation identity; omit `child_admission_receipt_id`
   and any derived postcommit view fields. Derive the child receipt after the
   append in the existing locked owner, expose it only in a separate committed
   view/link, and publish replacement pure/committed vectors and replay/CAS
   rules. Keep one child reservation writer.

10. **A05 auth/quota pre-tool conflict — REJECTED as already settled.**

   Matrix A05 explicitly keeps auth, quota, rate-limit, unsupported-model,
   context, malformed, schema, internal, and worker-timeout errors ordinary
   and forbids an auth/quota pre-tool fallback exception (matrix:76). The
   brief repeats the same frozen v1 rule and directs contradictory positive
   fixtures to be inverted or excluded (brief:716-733). A stale source test or
   implementation behavior cannot override that packet contract, and asking
   NBF-06 to preserve quota fallback would exceed frozen scope.

### Round-11 exact closure checklist

1. Rebind the corrected packet to this adjudication only after completion;
   preserve prior provenance sections as history.
2. Publish literal bytes/sample fields and hashes for every current child,
   hold/success, branch, and observation vector; mark Round-8/old vectors
   superseded.
3. Normalize hold/success field names and serializer/ID formulas identically
   across brief, matrix, codecs, and inverse paths.
4. Add a versioned transition/observation ID registry with branch-specific
   domains, parent bindings, sole writers, replay/CAS rules, and vectors.
5. Add file-qualified legacy/V1 migration codec paths, field mappings, nulls,
   and no-inference behavior while preserving frozen precommit DispatchOutcome.
6. Record NBF-01 schema ownership and NBF-06 integration handoff; cloud remains
   transport-only and no parallel receipt authority is permitted.
7. Remove child receipt/postcommit-view fields from the ledger event and derive
   them only after append; publish replacement proposal/committed vectors.
8. Preserve A09's harmless-refresh versus authoritative-replacement rule and
   A05's no-auth/quota-fallback rule; do not broaden scope.

### Round-11 disposition

The manager disposition is **5 accepted, 2 modified, and 3 rejected**.
Accepted blockers are findings 2, 3, 4, 5, and 9; modified findings are 1 and
7; rejected findings are 6, 8, and 10. Requirements for implementation that
are not packet-contract corrections are excluded. No finding authorizes a provider
cache/store, second selector, scheduler, duplicate terminal/child writer,
external journal, signal door, quota/auth fallback, or NBF-08 chain ledger.

## Round-12 manager adjudication

### Inputs and authority

This round reviews the exact current packet revision below. The frozen
plan/tasklist remain the scope and ownership authority; the matrix is the
A01–A38 node authority; the brief is the implementation-contract authority
where it does not contradict those frozen controls. Live source absence is
preimplementation evidence and is not, by itself, a defect.

| Artifact | SHA-256 |
| --- | --- |
| Brief `.oracle/briefs/nbf06-provider-resilience-implementation.md` | `bd1e09d591cdd278a8c1a1e8c0bc639a7cfc13441a298a917b42fc8b37f6b84e` |
| Matrix `.oracle/research/nbf06-acceptance-test-matrix.md` | `ca8c92ff3fd049925c48017e3d79e9a0ad3fb07ad2a1a1abb99830e5c4eaad54` |
| Prior adjudication | `559d2a1bd466e4f2f02a53b0de752c3f559ad54dd51f97f7fa09fa083ed7ce0b` |
| Frozen plan | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| Frozen tasklist | `a4f574ce02421226a0f4610ffc503918e54cd8b5f8ee28ca8e7805afaf1e3959` |

### Consolidation decision

A clean consolidated rewrite of the brief and matrix is **REQUIRED** before
the next planning freeze. This is not a request for more narrative or for
implementation to begin. The accumulated amendment sections contain multiple
normative-looking “current” descriptions, some of which are superseded and
some of which still disagree. An implementer must not have to choose between
them. The rewrite must retain a short provenance note and mark old vectors and
schemas superseded, but must expose one current union, one codec/migration
table, one ID/byte registry, and one A38 manifest. It must not change the
frozen task boundaries, add a provider store/scheduler, or turn this into an
implementation task.

### Finding-by-finding verdicts

1. **Unpublished current child/branch literal bytes and fields — ACCEPTED.**

   The revision names the current 401/431/465-byte child vectors and gives
   hashes, but does not publish the current payload bytes or complete sample
   field tuples in the same authoritative section. The branch entries give
   domains, a prose field summary, lengths, and hashes, but not an ordered
   byte fixture. Earlier literal bytes belong to superseded vectors. A digest
   without ordered input bytes cannot independently reproduce the serializer.

   The consolidated packet must publish one machine-readable or literal
   fixture for the pure proposal, committed event, committed view, hold,
   success, observation, and each recovery/configured-child/return branch,
   with sample fields, field order, null/raw-text rules, length, and SHA. A
   checked-in fixture with an explicitly named path and hash is sufficient;
   repeating long hex in both documents is not required.

2. **Missing transition ID registry — ACCEPTED.**

   “Branch registry” prose and three branch hashes are not a registry that
   fixes ID domains, ordered fields, parent bindings, producer/sole writer,
   replay/CAS result, and the literal vector. Observation, recovery,
   configured-child, return-primary, and repair transitions can therefore be
   implemented with different IDs while appearing compliant.

   Add one authoritative versioned registry row per transition and per
   observation/hold/success event. Each row must identify domain, exact field
   order, ID preimage/exclusions, parent receipt/key/epoch/evidence binding,
   producer, sole writer, replay/conflict behavior, and fixture/hash. This is
   the minimum reproducibility contract, not implementation test demand.

3. **Incomplete migration rows/codecs, including legacy provider terminals —
   ACCEPTED.**

   The current migration table has legacy `DispatchOutcome`, legacy ordinary
   terminal, V1 terminal/envelope, receipt transport, child, and torn/unknown
   rows, but no explicit legacy provider-terminal input row. “Legacy terminal
   inverse” is not enough to say whether provider fields are ordinary,
   accepted, held, or rejected, nor which nulls and IDs are legal. The brief
   and matrix also name slightly different codec paths.

   Add file-qualified rows for legacy ordinary terminal, legacy provider
   terminal, legacy observation/hold/success if encountered, V1 precommit,
   V1 accepted terminal, envelope/link, receipt transport, child event/view,
   and torn/unknown payloads. For every row specify codec and inverse,
   version, field mapping, explicit null/omission behavior, no-inference rule,
   upgrade prohibition, and replay byte check. Keep the frozen fail-closed
   precommit `DispatchOutcome` and postcommit view distinction.

4. **Decision union omits `PostTerminalConfiguredFallbackChild` in one
   current definition — ACCEPTED.**

   The canonical selector prose at the earlier brief section lists
   `PreToolNextTarget`, hold/probe, recovery child, return primary,
   `ExecuteFallbackUnsafe`, `NoTransition`, and `Unresolved`, while later
   “authoritative” sections include `PostTerminalConfiguredFallbackChild`.
   The packet simultaneously describes and omits the configured-child tag.
   This is a direct union contradiction, not a source-implementation issue.

   The consolidated union must contain exactly one configured-child variant,
   explicitly post-terminal and cross-family, with target proof fields but no
   side effect. Only the locked composite reservation door may apply it; the
   pre-tool variant remains the only pre-tool target selector.

5. **Inherited A38 allow versus later forbid, and duplicate exception owner —
   ACCEPTED.**

   Earlier A38 manifests list broad `incident/ledger.py` methods including
   `append_event` under additive writes, while later text says `append_event`
   is forbidden to NBF-06 policy and permits only file-qualified unrelated
   callers. The packet also alternates between a sole
   `fallback_chains.py:ExecuteFallbackUnsafe` owner and abbreviated “sole
   exception owner” wording without a single literal row for the codec,
   inverse, and transport edges. A checker cannot reliably distinguish a
   generic ledger allow from a provider-policy write or reject a duplicate
   exception class.

   The consolidated A38 manifest must be one literal, file-qualified table:
   `append_event` is forbidden to NBF-06 policy, and every unrelated generic
   caller is named separately with its permitted reason. It must name the one
   `fallback_chains.py:ExecuteFallbackUnsafe` class, its serializer/inverse,
   the exact adapter consumers, and identity-preserving raise/re-raise edges.
   Definitions, imports, calls, and writes remain separate checker outputs.

6. **`chain_digest` versus `configured_fallback_chain_identity` vocabulary —
   ACCEPTED.**

   The current packet uses the explicit receipt/evidence field
   `configured_fallback_chain_identity` but the current hold/success and
   observation registries use `chain_digest`. It does not state whether these
   are the same raw 32-byte digest, distinct values, or an alias permitted
   only in display text. Since the value participates in IDs, receipt binding,
   and replay, this is a reproducible contract ambiguity.

   Choose one canonical field name and define any display alias explicitly.
   State the canonical chain bytes, origin/source bytes, digest formula,
   raw-versus-hex representation, and exact field name in every event,
   receipt extension, codec, inverse, ID formula, and fixture. Do not require
   a second chain identity or a provider cache.

7. **Precommit labeled pre-reservation despite receipt, and old/current
   `DispatchOutcome` contradiction — ACCEPTED.**

   `ProviderAdapterEvidencePrecommit` is described as “pre-reservation” while
   carrying an admission receipt and being produced at the terminal-exception
   adapter after accepted launch. Elsewhere `DispatchOutcome` is the
   precommit bridge, the terminal payload is accepted only after reservation,
   and `DispatchOutcomeCommitted` is postcommit. “Precommit” can mean before
   terminal append, but “pre-reservation” means before the receipt-bearing
   admission; the current wording does not choose one lifecycle.

   Consolidate the stages explicitly: admission/reservation creates the
   receipt and epoch claim; adapter precommit evidence is before terminal and
   observation append but after the accepted admission it references;
   `DispatchOutcome` is that bridge; terminal/evidence/observation IDs and
   `DispatchOutcomeCommitted` are postcommit. Preserve legacy decode with
   explicit nulls and no inferred IDs. No new receipt authority is implied.

8. **Selector authority naming — MODIFIED.**

   There is no need for a second selector: the packet consistently intends a
   pure `select_provider_route` decision function, with
   `_advance_configured_spec_fallback` as the configured-chain normalization/
   candidate authority and adapters as non-selecting callers. However, the
   phrase “sole configured alternate-selection authority” is attached to
   different layers in different sections, making ownership hard to audit.

   Consolidate the names and roles: `_advance_configured_spec_fallback` may
   normalize a persisted configured chain and form the candidate;
   `select_provider_route(request, ledger_view)` is the sole pure policy
   decision API; the locked applier is the only effect door. Memory, auto,
   profiles, overrides, batch, fanout, loop, and ambient compatibility paths
   delegate or propagate only. This does not reopen the settled selector
   scope.

9. **Conflicting `provider_success` schemas and physical order — MODIFIED.**

   The latest Round-11 text supplies a canonical 10-field order and current
   bytes/hash, but retained Round-8/9 sections show both a success schema with
   and without `terminal_event_id`/`observation_id`. Because several sections
   are presented as authoritative, a reader can still choose incompatible
   physical payloads. The latest current choice need not be redesigned; the
   contradiction must be removed or explicitly marked historical.

   The consolidated registry must select one `provider_success` field set and
   physical order, one ID preimage/exclusion rule, one sole writer, and one
   fixture/hash. Apply the same treatment to hold and observation. Mark all
   older vectors/schema descriptions superseded; do not add a second success
   event or projection owner.

10. **NBF-01 prerequisite versus NBF-06 reassignment, with source absence —
    MODIFIED.**

   Source absence is not evidence that the plan is wrong: implementation is
   intentionally not begun. The frozen tasklist assigns shared typed schemas,
   strict serialization, and generic ledger/projection/CAS to NBF-01, while
   NBF-06 owns provider policy and integration. The brief mostly says this,
   but “NBF-06 owns policy/integration tests only” can be read as removing the
   NBF-06 provider module and its policy work, while other lines describe
   NBF-06 implementation hooks.

   Preserve NBF-01 as a prerequisite/owner of `incident/schema.py`, shared
   receipt codecs, and generic ledger primitives. State that NBF-06 owns the
   provider policy module, adapter integration, provider-specific contract
   fixtures, and tests, but cannot reassign or duplicate NBF-01 schema/ledger
   authority. Record the dependency and handoff in the consolidated packet;
   do not classify missing source files as a planning failure.

### Round-12 exact consolidation checklist

1. Rewrite the brief and matrix into one current normative section each;
   retain only a short supersession/provenance note for prior rounds and mark
   old vectors, field sets, and manifests explicitly historical.
2. Publish a single fixture registry with literal or named machine-readable
   ordered bytes, sample fields, raw/text/null rules, length, and SHA for
   child proposal/event/view, observation, hold, success, and all three branch
   transitions.
3. Publish the versioned transition/observation/hold/success ID registry with
   domains, exact preimages/exclusions, parent bindings, producers, sole
   writers, replay/CAS outcomes, and fixture references.
4. Add file-qualified migration rows/codecs/inverses for legacy provider
   terminals and all in-scope legacy/V1/torn payload classes, including field
   mappings, explicit nulls, and no-inference/upgrade rules.
5. Freeze one `ProviderRouteDecision` union containing
   `PostTerminalConfiguredFallbackChild`, and write the admission → precommit
   → terminal/evidence/observation → postcommit lifecycle without the
   “pre-reservation with receipt” ambiguity.
6. Replace all grouped/inherited A38 prose with one literal per-symbol table;
   classify `append_event` generic exceptions, the sole
   `ExecuteFallbackUnsafe` owner/codec/inverse, and every producer→consumer→
   applier→write edge separately.
7. Normalize `configured_fallback_chain_identity` versus `chain_digest` into
   one canonical vocabulary and formula across receipt, event, codec, inverse,
   and vector sections.
8. State the selector layering and NBF-01/NBF-06 handoff exactly as in
   findings 8 and 10. Do not add a provider cache, scheduler, second selector,
   second receipt/terminal/projection/child writer, NBF-04/05 door, quota/auth
   fallback, or NBF-08 journal/store.
9. Rebind the consolidated brief and matrix to the final adjudication SHA
   after the rewrite; do not edit live source, frozen plan/tasklist, or status
   as part of this adjudication.

### Round-12 disposition

The manager disposition is **7 accepted, 3 modified, and 0 rejected**.
Accepted blockers are findings 1, 2, 3, 4, 5, 6, and 7. Findings 8, 9, and
10 are modified because their intended scope is settled but the accumulated
wording still needs consolidation. No finding is accepted merely because a
future source file or test is absent. The consolidation is required for
deterministic planning closure, not as implementation-level documentation
maximalism.

## Round-13 manager adjudication (clean-packet review)

### Inputs and authority

This pass reviews the clean-packet revision below. The frozen plan/tasklist
remain scope and ownership authority; the matrix is the A01–A38 node
authority; the brief is the provider-contract authority subject to those
controls. Live source is descriptive preimplementation evidence. A missing
future module or test is not a defect unless the packet itself claims a
reproducible command or contract that is internally inconsistent.

| Artifact | SHA-256 |
| --- | --- |
| Brief `.oracle/briefs/nbf06-provider-resilience-implementation.md` | `a58ad3965d1c7dab3ab40ded8096ca37eed0f04949dc64feadc6f75bd7dbb20c` |
| Matrix `.oracle/research/nbf06-acceptance-test-matrix.md` | `ed6d092a371cad9d9a8547cb8e646b92f391c5c520d6f9935a497625af1a8239` |
| Prior adjudication | `5fa4198b96d571e37281bc5b1c25554869ce8a3b6bc51f5d4a16bee1330c0dd5` |
| Frozen plan | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| Frozen tasklist | `a4f574ce02421226a0f4610ffc503918e54cd8b5f8ee28ca8e7805afaf1e3959` |

### Reproduction and verdicts

1. **REFUSAL vector is invalid — ACCEPTED.**

   The matrix labels a textual `REFUSAL(369)` and hash as a U64BE-framed
   payload, but the shown `||null||` form is not literal framed bytes. Applying
   the stated rule to its 16 fields gives 326 bytes and SHA-256
   `9e44ee0a5ba17a44e45c9fb5ee16986d5b327a803562e0bd00303768658dc804`, not
   the claimed 369 bytes or `617da68ac9b25f1175a259c544ed678c28f61bfc3f7f3e586302e868abd90e06`.
   This is a direct reproducibility failure, independent of implementation.

   Replace it with an actual hex payload (or a named checked-in fixture),
   exact field tuple/count, explicit zero-length null encoding, length, and a
   hash computed over exactly those bytes. Do not preserve the incorrect
   digest as an alias or acceptance vector.

2. **Child/branch literal fixtures are unpublished — ACCEPTED.**

   The clean packet claims that the matrix contains full literal vectors, but
   it publishes literal bytes only for chain/evidence/failure-key/epoch and
   observation/hold/success. The current child proposal/event/view and the
   recovery/configured/return branches have descriptions, lengths, and hashes
   only. The brief repeats that gap. A future implementation cannot reproduce
   those codecs from a digest and prose field grouping.

   Publish exact current bytes or named fixture paths for every child and
   branch, with ordered fields, sample values, null/raw-text rules, length, and
   SHA. A fixture file referenced by both packet artifacts is sufficient; this
   does not require duplicating long hex in prose.

3. **Transition registry is incomplete — ACCEPTED.**

   The transition table names states and broad preconditions/effects, but it
   does not give a deterministic ID domain/preimage, field order, parent
   bindings, producer, sole writer, replay/conflict result, or fixture for
   each transition. The branch hashes elsewhere do not close those omissions.
   In particular, `provider_recovery_verified`, configured child, return, and
   observation repair can still be encoded differently by two conforming
   readers.

   Add one versioned registry row for every transition and observation,
   hold, and success event. Include exact ID inputs/exclusions, parent
   terminal/receipt/key/epoch/evidence bindings, writer, CAS/replay result,
   and fixture reference. Keep transition IDs distinct across branches and
   do not create a second ledger or event writer.

4. **Migration rows contain placeholders, including recovery_verified —
   ACCEPTED.**

   The row `legacy provider terminal/observation/hold/success | file-qualified
   legacy inverse` is not a file-qualified codec path, and the transition
   registry's `provider_recovery_verified` row has no legacy/V1 codec, field
   mapping, null behavior, or replay rule. “Preserve class” does not specify
   how an old record is classified or rejected.

   Name each codec and inverse by file and symbol for legacy provider terminal,
   observation, hold/success, and recovery evidence as applicable, plus all V1
   records. Specify input/output mappings, versions, explicit nulls versus
   omissions, unknown/torn behavior, no-inference upgrade prohibition, and
   byte-identical replay. Keep legacy ordinary records ordinary and preserve
   the fail-closed precommit bridge.

5. **`chain_digest` versus canonical chain identity remains ambiguous —
   MODIFIED.**

   The clean packet declares `configured_fallback_chain_identity` canonical
   and `chain_digest` display-only, which is the correct direction. However,
   fixture and ordered-field tables still use `chain_digest` as a field name,
   including provider evidence and hold/success/observation rows, without
   stating that the encoded field is the exact same raw digest. This leaves
   the physical codec vocabulary ambiguous even though the policy intent is
   settled.

   Retain one canonical encoded name and formula everywhere. If
   `chain_digest` remains a display alias, label it non-serializable and show
   `configured_fallback_chain_identity` in every ordered tuple, schema,
   inverse, and fixture. Define canonical chain/origin bytes, digest inputs,
   and raw-versus-hex representation once.

6. **A38 edges are still incomplete despite a file-qualified table —
   ACCEPTED.**

   The matrix table is materially improved, but it still groups some roles,
   gives shortened paths such as `fallback_chains.py`, and describes “all
   other generic append_event callers” without naming them. It lists
   serializer edges without a complete inverse edge for each codec and does
   not provide an exact invocation/path for the checker. The brief's earlier
   manifest also contains broader ledger method allowances, so the claimed
   closed graph is not actually one literal production allowlist.

   Replace inherited prose with one file-qualified per-symbol manifest. For
   every definition/import/call/write state producer, serializer, inverse,
   consumer, applier, and permitted write. Name each unrelated generic
   `append_event` caller or explicitly allow none; forbid it to NBF-06 policy.
   Name the sole `fallback_chains.py:ExecuteFallbackUnsafe` class, codec,
   inverse, and identity-preserving transport edges. Give A38 an exact
   checker command and retain separate negative fixtures for definitions,
   imports, calls, and writes.

7. **Lifecycle staging and circularity are inconsistent — ACCEPTED.**

   The clean packet says adapter evidence leads to reservation and terminal
   commit, while its reservation boundary creates the admission receipt and
   epoch claim that the evidence already carries. It also says the child
   `provider_route_child_reserved` result is an event/view with “receipt in
   ledger event,” contradicting the stated postcommit-only child receipt and
   the frozen one-append/no-derived-ID rule. The phrase “precommit” is not
   enough to resolve whether it is before reservation, terminal append, or
   postcommit evidence.

   State one acyclic order: canonical admission/reservation creates the
   receipt and epoch claim; accepted-launch adapter evidence references that
   receipt before terminal append; terminal/event and observation linkage then
   commit; postcommit evidence/view and derived child receipt follow. The
   child ledger event must omit the derived receipt, and only the existing
   locked owner may derive it after append. Provide crash/replay outcomes for
   each seam and remove all contrary wording.

8. **Failure-key fixture does not match NBF-01's canonical class — ACCEPTED.**

   The matrix claims a U64BE `NBF06-PROVIDER-FAILURE-KEY-V1` vector with
   fields `domain, run, spec, availability, epoch-1`, length 117, and SHA
   `023bb004...`. The live NBF-01 class at
   `arnold_pipelines/megaplan/incident/schema.py:ProviderFailureKey.derive`
   canonically hashes JSON material containing `version`, `phase`,
   `selected_spec`, `provider_failure_class`, and `provider_epoch_identity`
   through `_digest(canonical_json(...))`. For the matrix's stated tuple, that
   canonical source derivation is
   `003c3779c6450703a19c42a69e644ec1b5601a18843c7f0017a18601c29d9db5`, not
   the matrix value. The packet cannot call both encodings canonical.

   Make the fixture use the existing NBF-01 `ProviderFailureKey` class and
   its exact version/phase/spec/provider-failure-class/epoch formula, or
   explicitly amend that owner through the frozen NBF-01 task (not NBF-06).
   Recompute length/hash and all dependent evidence/observation vectors;
   never silently introduce a second U64 key codec.

9. **A32/A38 semicolon and prose commands — ACCEPTED.**

   The matrix says commands are independent and fail-fast and says no
   semicolon may mask failure, but A32 is presented as one aggregate command
   in the acceptance row while the three required path checks are not all
   independently enumerated there. A38 supplies expected output but no exact
   checker invocation/path. This makes claimed acceptance evidence
   non-reproducible even before tests exist.

   List the aggregate only as an optional convenience. Record three literal,
   independently executed A32 commands (batch, ordered fanout, and direct
   loop engine), with fail-fast status for each. Add the exact A38 checker
   command, working directory, production allowlist input, and required output
   line. Do not use shell semicolon chains or prose placeholders as evidence.

10. **Reservation lifecycle wording — ACCEPTED.**

   “At the locked reservation boundary NBF-01/02 writes the epoch claim” is
   compatible with one reservation append, but the surrounding clean packet
   simultaneously presents accepted evidence as preceding reservation and
   calls the child event a view containing its receipt. Those statements leave
   the admission/claim/binding/terminal sequence and the crash cut point
   under-specified and can recreate receipt/claim circularity.

   Use explicit stage names and owners: pre-tool admission and one locked
   reservation append (receipt plus claim), post-append binding repair only
   when needed, accepted-launch terminal precommit, terminal/observation
   commit, then postcommit receipt/evidence/view derivation. Define pending
   and durability-unknown at the binding seam, prohibit launch/child/probe
   while unresolved, and state that no derived receipt or observation ID is an
   input to the append that creates its source record.

### Round-13 exact repair checklist

1. Replace the invalid REFUSAL pseudo-vector with checked literal/framed bytes,
   exact fields including null encoding, length, and recomputed SHA.
2. Add a shared current-fixture registry for child proposal/event/view and all
   branch transitions with literal or named bytes, field tuples, raw/text/null
   rules, lengths, and hashes.
3. Expand the transition registry to exact versioned IDs, preimages,
   exclusions, parent bindings, producers, sole writers, replay/CAS outcomes,
   and fixture references for every transition/event.
4. Replace migration placeholders with file-qualified codec/inverse rows for
   legacy provider terminal/observation/hold/success and recovery_verified,
   including mappings, versions, nulls, unknown/torn/no-upgrade rules.
5. Normalize all encoded chain fields to `configured_fallback_chain_identity`
   (or explicitly define a byte-identical non-encoded display alias), and
   update every dependent vector and digest.
6. Publish one literal A38 manifest with full paths, one row per symbol and
   inverse, producer→serializer→consumer/applier→write edges, named generic
   append_event exceptions, the sole refusal owner, and an exact checker
   invocation plus negative fixtures.
7. Rewrite the lifecycle as admission/reservation → accepted-launch
   precommit → terminal/observation commit → postcommit evidence/view,
   explicitly removing receipt/ID circularity and child receipt from the
   ledger event.
8. Rebase the failure-key vector on the NBF-01 `ProviderFailureKey` canonical
   serializer/class and recompute dependent vectors; do not create a second
   key codec or reassign NBF-01 ownership.
9. Enumerate three standalone A32 commands and one exact A38 command; keep
   aggregate/prose commands supplemental only and prohibit semicolon masking.
10. Rebind the corrected clean brief and matrix to the final adjudication SHA
    after these repairs. Do not edit live source, frozen plan/tasklist, or
    status as part of this adjudication.

### Round-13 disposition

The manager disposition is **9 accepted and 1 modified**. Accepted blockers
are findings 1, 2, 3, 4, 6, 7, 8, 9, and 10. Finding 5 is modified because the
canonical identity decision is already made, but the encoded field vocabulary
still needs normalization. These are packet reproducibility and lifecycle
corrections, not demands to implement the plan or to document every source
detail. No finding authorizes a provider cache, second selector/scheduler,
second receipt/terminal/projection/child writer, NBF-04/05 door, quota/auth
fallback, or NBF-08 journal/store.

## Round-14 manager adjudication (final clean-packet review)

### Inputs and authority

This pass reviews the exact final-clean-packet candidates below. Frozen
plan/tasklist ownership and scope remain controlling; the matrix owns A01–A38
commands/registry, and the brief owns the provider contract subject to those
controls. Live source is not required to contain the not-yet-implemented NBF-06
module, but any claim about an existing canonical class or serializer must
match the live source.

| Artifact | SHA-256 |
| --- | --- |
| Brief `.oracle/briefs/nbf06-provider-resilience-implementation.md` | `ef3ba50a506c596ae27b7b55c9128908fc8c7105c9284d67254cb7d69a53f0bf` |
| Matrix `.oracle/research/nbf06-acceptance-test-matrix.md` | `035ce3dc8eb119181580ad0bc0da0d6e6af62004819915720b8a4e426dac8b0a` |
| Prior adjudication | `f7b942230671ebffd0aec4bc1e45c638db38cbe231d2fb6b59097f1531ad6313` |
| Frozen plan | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| Frozen tasklist | `a4f574ce02421226a0f4610ffc503918e54cd8b5f8ee28ca8e7805afaf1e3959` |

### Finding-by-finding verdicts

1. **Raw 32-byte versus ASCII-hex digest encoding — ACCEPTED.**

   The packet declares raw 32-byte digests, but the current EVIDENCE vector
   frames the failure-key digest with length `0x40` and ASCII hex, and the
   OBSERVATION/HOLD/SUCCESS vectors likewise frame the key/evidence values as
   64-character text. The refusal field `configured_fallback_chain_identity`
   is also encoded as text while other sections call the identity raw32. The
   vectors can hash consistently with their own bytes and still violate the
   declared wire contract.

   Freeze representation by field: IDs and ordinary text are U64BE-framed
   UTF-8/NFC; digest fields are exactly 32 raw bytes; absent chain identity is
   an explicit null or a separately defined sentinel, never accidental ASCII
   hex. The NBF-01 failure-key value may remain a displayed hex string, but
   event serializers must state whether they decode it to raw32. Recompute all
   dependent vectors and reject text-for-bytes substitution.

2. **Transition fixture coverage/mapping for probe, pending, reconciled, and
   durability states — ACCEPTED.**

   The transition table names these states and points at broad fixtures, but
   it does not publish a literal payload/field mapping for probe-start,
   probe-result, probe-close, observation-link-pending, observation-reconciled,
   or `provider_durability_unknown`. A named transition and a shared
   observation hash do not establish replay, CAS, or unknown-state bytes.

   Add versioned fixtures and registry rows for each transition, with exact
   ordered fields, ID preimage/exclusions, parent/lease/fence bindings,
   producer/sole writer, unknown/expiry/repair result, null rules, and length/
   SHA. Keep pending and reconciled linkage from counting a second observation;
   durability unknown must remain no-route/no-launch until exact repair.

3. **Child-view domain — ACCEPTED.**

   `CHILD_VIEW` is labeled `NBF06-PROVIDER-ROUTE-CHILD-COMMITTED-VIEW-V1`,
   but its literal payload begins with the child-event domain
   `NBF06-PROVIDER-ROUTE-CHILD-EVENT-V1`. The table and vector therefore
   disagree about the domain and cannot be independently replay-validated.

   Choose one explicit view domain and encode it in the view fixture, or state
   that the view deliberately reuses event-domain bytes and make that reuse a
   normative exception. In either case the view is postcommit only, carries
   the derived receipt, and is never the ledger-event payload.

4. **A38 exact inverse rows and transport edges — ACCEPTED.**

   The matrix now names many file-qualified symbols, but several rows still
   say “serializer/inverse” or group a view/codec pair without naming the
   inverse symbol, and the producer→consumer→applier→write edge is not closed
   for every probe/epoch/recovery/refusal type. The exact checker command does
   not cure a manifest whose rows are incomplete.

   Make one literal row per definition, import, call, serializer, inverse,
   producer, consumer, applier, and allowed write. Include probe start/result/
   close/reconcile, epoch claim/binding, recovery, child event/view, refusal,
   and all transport adapters. `append_event` remains forbidden to NBF-06;
   name every unrelated exception and forbid NBF06 domains. Preserve separate
   AST definitions/imports/calls/writes and negative fixtures.

5. **Immutable legacy recovery migration — ACCEPTED.**

   The migration row maps legacy recovery evidence to the V1 serializer and
   says absent proof is null, but does not state that the legacy bytes remain
   immutable or that a legacy record cannot be rewritten as a V1
   `provider_recovery_verified` event. That omission can manufacture a
   single-use child authorization during repair.

   Require byte-preserving legacy decode/re-encode, explicit legacy class and
   version, null/omission mapping, and no V1 upgrade or inferred proof. Only
   an independently durable V1 proof with exact passed lease/parent binding
   can authorize recovery; legacy reconciliation is read/repair evidence only.

6. **Target key mismatch: source key reused for codex/epoch-2 target —
   ACCEPTED.**

   The current child fixture repeats source key digest
   `003c3779c6450703a19c42a69e644ec1b5601a18843c7f0017a18601c29d9db5` in the
   target-key slot, although the target is `codex:gpt-5.6` at `epoch-2`. The
   live canonical `ProviderFailureKey.derive` formula produces
   `a297d0150fcb774fb747519d24d682f223a73462b7291185647814a3389b73d1` for
   `(phase=run, selected_spec=codex:gpt-5.6, provider_failure_class=availability,
   provider_epoch_identity=epoch-2)`. The vector is self-hashed but semantically
   forged by source-key inheritance.

   Replace target key fields and dependent child/branch vectors with the
   target-derived key, and require the locked child door to recompute and
   compare target phase/spec/class/epoch. Source key/epoch may authorize the
   parent but can never be copied into the target.

7. **Zero chain-identity sentinel — ACCEPTED.**

   The event fixtures encode an all-zero 32-byte chain field for a no-chain
   sample while the contract says `null` differs from omission and calls the
   configured identity a digest. It does not reserve all-zero as a valid
   no-chain sentinel or distinguish it from a real digest value.

   Define one representation for absent chain identity—prefer explicit null
   where the schema permits it—or reserve an explicit versioned all-zero
   sentinel with a normative meaning and validation rule. Apply it uniformly
   to receipt, evidence, observation, hold/success, child, branch, refusal,
   migration, and replay vectors; do not infer identity from current config.

8. **Auth/quota typed pre-tool exception versus T8 — MODIFIED.**

   The settled T8 rule correctly excludes auth, quota, rate-limit, unsupported,
   context, internal, and timeout classes from `provider_exhausted`. The clean
   packet does not, however, state with equal precision that auth/quota may
   not produce a typed pre-tool alternate-target exception; “only pre-tool
   target choice” and “never T8 exhaustion” could be read as permitting that
   separate path.

   Add one explicit rule: auth/quota (and the other ordinary classes) produce
   no `PreToolNextTarget`, no configured-chain advancement, and no typed
   exception that authorizes a target under frozen v1. Only the frozen eligible
   operational classes may reach a pre-tool decision, and accepted-launch
   T8 exhaustion remains a separate post-tool rule. Do not broaden NBF-06 or
   create positive quota-fallback tests.

9. **EPOCH-ID literal fixture — ACCEPTED.**

   The epoch-identity registry row supplies a field summary and digest but a
   blank byte length and no literal payload. The claim and binding fixtures
   cannot substitute for the identity preimage: the claim embeds its digest,
   so an implementation could choose different identity bytes while matching
   the displayed claim hash.

   Publish the exact `NBF06-PROVIDER-EPOCH-ID-V1` ordered fields, raw/text/
   numeric encodings, literal bytes or named fixture, length, and SHA. Verify
   claim construction consumes that exact identity digest and retain the
   volatile-field exclusion/fencing rule.

10. **Inverted child-receipt forbidden wording — ACCEPTED.**

   The transition row currently describes an event without receipt but lists
   “derived receipt in ledger event” as the forbidden consequence, while the
   A38 child row says “receipt never in event.” The sentence is intended as a
   prohibition but is easy to read as an allowed edge and conflicts with the
   current child-view rule.

   Rewrite the row positively and unambiguously: `CHILD_EVENT` contains no
   derived child receipt; `CHILD_VIEW` contains it only after the locked append
   and derivation; one locked owner performs both steps. Add tamper/replay
   vectors proving event/view separation and reject any receipt-bearing event.

### Round-14 exact repair checklist

1. Correct all digest-bearing vectors to the selected raw32/explicit-null
   representation and recompute lengths, hashes, and dependent payloads.
2. Add literal or named fixtures and complete mappings for probe start/result/
   close, pending/reconciled linkage, and durability-unknown transitions.
3. Give the child committed view its own declared domain (or explicitly freeze
   domain reuse) and align every label, codec, inverse, and vector.
4. Complete A38 with one file-qualified row per symbol/codec/inverse and full
   producer→transport→consumer→applier→write edges, exact checker command,
   named generic append exceptions, and negative fixtures.
5. Freeze immutable legacy recovery migration: byte-preserving decode/re-encode,
   explicit nulls, no inferred proof, and no silent V1 authorization upgrade.
6. Replace inherited source key in the codex/epoch-2 target fixture with the
   canonical target-derived key `a297d015…3389b73d1`; recompute child/branch
   vectors and enforce locked target recomputation.
7. Define and apply one no-chain identity representation; distinguish null,
   all-zero sentinel, and a real digest in every schema and fixture.
8. State the explicit no-auth/no-quota pre-tool target/exception rule while
   preserving the frozen T8 exhaustion classification.
9. Publish literal `NBF06-PROVIDER-EPOCH-ID-V1` bytes/fields/length/SHA and
   bind the claim fixture to that exact identity digest.
10. Correct the child-event forbidden wording and prove receipt-free event /
    postcommit receipt-bearing view separation.
11. Rebind the corrected brief and matrix to this adjudication SHA after all
    repairs. Do not edit live source, frozen plan/tasklist, or status as part
    of adjudication.

### Round-14 disposition

The manager disposition is **9 accepted and 1 modified**. Accepted blockers
are findings 1–7, 9, and 10. Finding 8 is modified because the frozen
auth/quota/T8 boundary is settled, but the pre-tool prohibition must be stated
explicitly. These are reproducible packet-contract defects; no source absence
is treated as implementation failure, and no requirement adds a provider
cache, scheduler, selector, receipt/terminal/projection writer, physical
signal door, or NBF-08 store/journal.

## Round-15 manager adjudication (final clean-packet evidence review)

Inputs checked:

| artifact | SHA-256 |
|---|---|
| brief | `528000e4e7a8da26af6a8ae5dc54ead17b84422c3fb8df2172fd874602fea31f` |
| acceptance matrix | `125c39a72b631bf58692de585c3b8ad2484963379b74c17d8c00d3af196f594e` |
| preceding adjudication | `9fe26d064627676b3937d37d3072c66a0dc335a67fa3ac20139676f6ebbd6b0a` |

The three Round-15 reviews are unanimous REWORK, but unanimity is not
dispositive. I reproduced each finding against the frozen packet and separated
contract defects from implementation work that is intentionally absent.

### Finding-by-finding verdicts

1. **Transition fixture references: ACCEPTED.** The transition table names
   `PENDING`, `RECONCILED`, `PROBE_START`, `PROBE_RESULT`, `PROBE_CLOSED`, and
   `UNKNOWN` (and gives partial field labels), but does not publish a literal or
   named fixture payload, complete ordered fields, or a complete transition
   mapping. A reader cannot independently recompute the referenced digest,
   binding, lease, parent/fence, result/null, and replay constraints. Add the
   exact fixture bytes or stable fixture names plus those fields, producer,
   writer, preimage exclusions, lengths, and hashes. This is a planning
   reproducibility defect, not a demand for implemented tests.

2. **Primary A38 standalone inverse rows/edges: ACCEPTED.** The packet now
   contains a substantially improved file-qualified graph and checker command,
   but the primary contract still permits grouped rows and implicit inverses;
   not every declared codec/type has a standalone inverse and complete
   producer→transport→consumer/applier→write edge. Make the primary A38 table
   literal and one-row-per-symbol, including every serializer and inverse, with
   exact file/module ownership, edge, and negative fixture. Keep generic
   `append_event` callers outside the NBF06 allowlist explicitly named and
   rejected. This is not a finding that current source lacks those APIs.

3. **Receipt ownership across NBF01/NBF02/cloud transport: REJECTED as a
   blocker.** The packet already assigns generic schema/event codecs and
   `WorkerAdmissionReceipt` to NBF01, makes NBF06 the policy/integration
   consumer, and says cloud transport carries canonical receipt bytes without
   deriving IDs. That is an adequate ownership boundary. Preserve this exact
   distinction in the consolidated wording, but do not add another receipt
   owner or require implementation evidence at the planning gate.

4. **Distinct precommit evidence versus postcommit envelope/DispatchOutcome:
   ACCEPTED.** The lifecycle distinguishes adapter evidence before terminal
   commit from the postcommit envelope/observation/child view, yet the published
   `EVIDENCE` fixture carries `terminal-1` and `observation-1` while being used by
   a preterminal/terminal-commit row whose IDs are supposed to be excluded.
   Publish separate fixtures and schemas: a precommit adapter
   evidence/`DispatchOutcome` fixture with no terminal, observation, or derived
   postcommit receipt IDs; and a postcommit `ProviderEvidenceEnvelope` fixture
   with those links populated. State the bridge and ordering explicitly so no
   postcommit ID is an input to its own precommit evidence digest.

5. **Return-primary target proof/source-target key/epoch: ACCEPTED.** The
   return-primary proposal lists a return proof and provider identity but does
   not make source and target admission proof, key, and epoch claims distinct.
   That leaves an authorization path in which a source claim can be reused for
   the target. Require source receipt/observation/key/epoch and independently
   derived target primary spec/family/key/epoch claim/binding plus target
   admission proof and return proof. The locked composite door must validate both
   domains; no source identity may be inherited as a target claim.

6. **Child event identity (`event_id` versus `child_reservation_event_id`):
   ACCEPTED.** The packet names `child_reservation_event_id` and separately
   relies on a ledger event identity, but never states whether they are equal,
   whether either is in the hash preimage, or when either is assigned. That is a
   genuine circularity/replay ambiguity. Freeze one rule: either omit the event
   ID from the canonical payload preimage and assign it at append, or define a
   distinct deterministic child-reservation ID whose preimage excludes the
   generated ledger event ID. Publish fields, formula, append order, CAS/replay
   behavior, and the event/view boundary; child events remain receipt-free.

7. **Non-null chain identity encoding (raw32 versus text): ACCEPTED.** The
   brief says no-chain is explicit null (`U64BE(0)`) and that all-zero raw32 is
   not the sentinel, but matrix rows still say `null-or-text`, and the refusal
   representation does not consistently type the non-null value. Freeze one
   physical encoding everywhere: a non-null chain identity is exactly the raw32
   digest of canonical chain bytes, never text or hex; absent is exactly the
   explicit null sentinel. Update every transition/refusal/receipt fixture and
   recompute dependent vectors. Keep `chain_digest` as display-only vocabulary.

### Round-15 exact repair checklist

1. Publish literal or stable named `PENDING`, `RECONCILED`, `PROBE_START`,
   `PROBE_RESULT`, `PROBE_CLOSED`, and `UNKNOWN` fixtures with ordered fields,
   preimage exclusions, binding/lease/parent/fence, producer/writer, result and
   null rules, byte length, and SHA; add the complete transition mapping.
2. Replace the primary A38 grouped/implicit registry with one literal row per
   symbol and codec, its exact inverse, file-qualified producer, transport,
   consumer/applier, and write edge. Include the exact checker command,
   allowlist, negative fixtures, and named non-NBF06 `append_event` exceptions.
3. Preserve the NBF01 receipt/schema owner, NBF02 admission consumer/seam, and
   cloud byte-transport boundary in one authoritative ownership row; do not
   create a second receipt writer or ID derivation path.
4. Add separate precommit adapter-evidence/`DispatchOutcome` fixtures and
   postcommit `ProviderEvidenceEnvelope` fixtures, with an explicit
   precommit→terminal→observation/postcommit bridge and no circular IDs.
5. Expand return-primary proposal and vectors with independently derived source
   and target receipt/proof/key/epoch/binding fields; require the locked
   source-target composite validation and reject inherited source claims.
6. Define `event_id` and `child_reservation_event_id` ownership, preimage,
   assignment order, append/CAS/replay behavior, and receipt-free child event
   versus postcommit child view. Add a non-circular identity vector.
7. Replace every `null-or-text` chain identity declaration with the single
   raw32-or-explicit-null encoding and recompute all affected refusal,
   transition, receipt, and chain vectors; retain display-only `chain_digest`.
8. Rebind the repaired brief and matrix to this adjudication SHA. Do not edit
   live source, frozen plan/tasklist, or status as part of this adjudication.

### Round-15 disposition

The manager disposition is **6 accepted and 1 rejected**. Accepted blockers are
findings 1, 2, and 4–7. Finding 3 is rejected as already settled by the packet’s
explicit ownership boundary. The accepted items are reproducible contract or
serialization ambiguities; they do not require implementation, tests, or new
architecture beyond the frozen NBF06 planning scope.

## Round-16 manager adjudication (finite repair checklist)

Inputs: brief `dfbb8ff729cfa824d0773035d4b4d399cfddbcba5d2e77c204ced66b76f11e60`,
matrix `47fbee64b4e40136da5284f54b2288dba03d175005e19b50bf34b7c702f0ae3f`,
and prior adjudication `f58fe5f3a2a37c4359879640713f06f53d3f6021a5307dc5d4fbbc17b95b3118`.

1. **Precommit bridge — ACCEPTED.** The matrix says the typed
   `DispatchOutcome` bridge carries precommit bytes unchanged, but its
   `PRECOMMIT_EVIDENCE` and `DISPATCH_OUTCOME` fixtures have different domains,
   lengths, and hashes. The live `phase_result.py:DispatchOutcome` also uses
   fields such as `kind`, `launch_state`, `semantic_dispatch_fingerprint`,
   nullable postcommit IDs, and nested `provider_evidence`, rather than the
   matrix's wire-field names. This is a real conversion/serialization
   ambiguity. The packet must choose byte-identical transport (same domain and
   bytes) or an explicit typed retag/re-encode; it cannot claim both. It must
   publish the live-field→wire-field map and nullable/staged rules, including
   which terminal/observation/event/derived-receipt fields are null before
   commit and populated only after commit.

2. **CHILD_EVENT ID wording — ACCEPTED.** The tuple includes source
   reservation, admission, and observation link IDs, while the prose says
   “decision_kind and all IDs are excluded.” It does not define whether
   `child_reservation_event_id` is an alias for canonical `event_id` or a
   distinct identity. That contradiction affects the bytes and replay rule.
   State exactly which source link IDs are in the preimage; state whether
   `child_reservation_event_id == event_id` or is separately derived; exclude
   every self/derived ID and the child receipt from the event preimage; then
   update the ordered tuple, literal bytes/hash, child view, and A38 row.

3. **Primary A38 codec/edge registry — ACCEPTED.** The allow/deny graph names
   route, probe, phase/dispatch, fallback, and some legacy symbols, but the
   primary inverse/edge registry does not give every one a standalone
   serializer↔inverse and complete producer→transport→consumer/applier→write
   edge. Several endpoints remain role prose rather than file-qualified
   symbols. Add one literal primary row for each route request/decision,
   probe request/result, live `DispatchOutcome` bridge, fallback chain
   encode/decode/persistence codec, and legacy provider codec. Every producer,
   transport, consumer, applier, and durable writer must be repository-relative
   and file-qualified; preserve the explicit generic-`append_event` denylist.

4. **Migration shorthand — ACCEPTED.** A few migration rows use “↔ precommit
   adapter codec,” “child event/view,” or “/ inverse” shorthand, so the
   version/domain, exact field mapping, null-versus-omission behavior, unknown
   handling, no-upgrade rule, and replay comparison are not independently
   reproducible. Expand each legacy `DispatchOutcome`, ordinary/provider
   terminal, observation, hold/success, recovery, receipt, child event/view,
   and V1 row to an exact file-qualified codec and inverse with those rules.
   This is a packet contract repair, not a demand that the absent
   implementation already exist.

5. **A38 script/fixture files and task ownership — MODIFIED.** The named
   `scripts/check_nbf06_a38.py` and `tests/.../fixtures/nbf06_a38` do not exist
   in the current live tree. Their absence is expected before NBF-06
   implementation and is not, by itself, a planning-gate failure. However,
   the packet must assign the planned deliverables: NBF-01 owns shared schema
   codecs/inverses; NBF-06 owns provider fixture vectors, the A38 checker and
   NBF06 negative fixtures, with NBF-07 only invoking the checker during final
   validation. Name those paths and the handoff in the packet; do not alter the
   frozen tasklist merely to manufacture present-day files.

### Round-16 exact repair checklist

1. Select and document one bridge mode: either identical precommit bytes, or
   explicit typed retag/re-encode. Reconcile the two current vectors, hashes,
   domains, and lengths, and publish the complete live `DispatchOutcome` field
   mapping plus null/stage conversion table.
2. Replace “all IDs excluded” with an explicit CHILD_EVENT preimage list:
   source link IDs included; self event/child-reservation identity and derived
   child receipt excluded (or a separately defined non-circular identity);
   decision inclusion/exclusion stated. Recompute CHILD_EVENT, CHILD_ID, and
   CHILD_VIEW fixtures and hashes.
3. Make the A38 primary table one row per route, probe, phase/dispatch,
   fallback, legacy, receipt, epoch, observation, child, return, and refusal
   codec. Add exact inverse and file-qualified producer→transport→consumer→
   applier→writer for every row; remove role-only endpoints.
4. Expand every migration row with version/domain, field mapping, codec and
   inverse paths, explicit null/omission/unknown rules, no-upgrade behavior,
   and byte-identical replay/CAS behavior.
5. Add a packet ownership row naming NBF-01 shared codec work, NBF-06
   `scripts/check_nbf06_a38.py` plus
   `tests/arnold_pipelines/megaplan/fixtures/nbf06_a38` negative fixtures, and
   NBF-07 final invocation. Keep the exact standalone checker command and
   expected output.
6. Rebind the repaired brief and matrix to the resulting adjudication SHA.
   Do not edit live source, frozen plan/tasklist, or status as part of this
   adjudication.

**Round-16 disposition: 4 accepted, 1 modified.** Findings 1–4 are
reproducible packet ambiguities. Finding 5 is accepted only for missing
planned ownership and modified to reject current-file absence as an
implementation failure.

## Round-17 manager adjudication (current-byte custody review)

Current authoritative inputs are brief
`b042c2d9491d283702c72ac462c6b72ab1fbe2e0911f742ba063eb92edd35ee4`, matrix
`ebe0fac2f6266561192c54467181b0a7757677b54b385855a9fc2f75933ff84e`, frozen
plan `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`, and
tasklist `a4f574ce02421226a0f4610ffc503918e54cd8b5f8ee28ca8e7805afaf1e3959`.
Earlier reported adjudication bytes were not recoverable and their actor is
unknown; those reports are historical context, not custody evidence.

1. **A38 route proposal, competing writers, probe/legacy/planning denylist —
   ACCEPTED.** The primary A38 table has route request/decision and child
   entries, but no unambiguous standalone route-proposal codec/ inverse. Its
   request and decision edges name `reserve_provider_route_locked` and
   `append_provider_route_decision`, while the composite child edge names
   `reserve_provider_route_child`; the packet does not say which is the sole
   durable route transition. Probe, legacy, and `PlanningControlBinding`
   boundaries are not all represented as exact deny edges in that primary
   registry. This is a real one-writer/allowlist ambiguity, not a claim that
   the planned checker must already exist.

2. **Liveness/membership in epoch and then failure key — ACCEPTED.** The
   current `EPOCH_ID` includes `route_liveness_digest` and
   `provider_membership_snapshot_digest`, while the failure key includes the
   resulting `provider_epoch_identity`. That permits a liveness or membership
   refresh to change the failure key, conflicting with the frozen rule that
   such refreshes cannot reset/rekey the streak or authorize an identical
   retry. Separate stable key identity from fencing evidence: volatile
   liveness/membership may validate a claim or fence a reservation, but must
   not silently become a new provider-failure key.

3. **Epoch label versus epoch digest — ACCEPTED.** Wire examples use the text
   label `epoch-1` in precommit/failure-key fields, while `EPOCH_ID` and claim
   fixtures use a digest identity (`db1e…`). The packet never freezes whether
   `provider_epoch_identity` is a label, raw32 digest, or a display alias in
   each codec. Declare one typed wire representation, distinguish display
   labels from canonical identity bytes, and make claim, evidence, key, and
   replay equality use the same representation.

4. **CHILD_EVENT decision/proposal provenance — ACCEPTED.** Source linkage
   IDs are included, but `decision_kind` is explicitly excluded and no
   `proposal_digest` is included. Distinct route decisions can therefore
   collide on the same event payload unless the domain or another frozen field
   carries that distinction. Include either the canonical decision field or a
   non-circular digest of the complete proposal, state its exact preimage, and
   recompute child event/identity/view vectors.

5. **Raw-byte `DispatchOutcome` bridge/live field map — ACCEPTED.** The packet
   now gives a useful live-field mapping, but a live `DispatchOutcome` is a
   typed dataclass whose `to_dict`/`from_dict` fields and nested evidence do not
   themselves equal the framed NBF06 payload. “Byte-for-byte unchanged” is
   true only after an adapter has serialized the mapped value; it is false if
   it means the live object crosses without conversion. Freeze the adapter
   conversion and stage/null rules, then reserve “unchanged” for the bytes
   after that conversion.

6. **Second terminal name/writer — ACCEPTED.** NBF-01 owns
   `IncidentLedger.append_terminal_outcome`, while the NBF06 registry calls
   `record_provider_terminal_with_observation_locked` the sole terminal/
   observation writer. The packet does not state whether the latter delegates
   to the former or creates a second physical terminal path. Designate one
   physical terminal writer and identify the NBF06 method as policy adapter or
   transaction wrapper only; preserve one terminal and one observation
   cardinality under the existing lock/CAS.

7. **Migration and role-only A38 endpoints — ACCEPTED.** Migration rows are
   improved but still contain shorthand and role prose in the primary edge
   registry (for example “cloud worker dispatch,” “terminal adapter,” “legacy
   reader,” and an unqualified inverse). A machine-facing A38 contract needs
   exact repository-relative symbols for every serializer, inverse, producer,
   transport, consumer/applier, and writer, including probe, route proposal,
   legacy codecs, and the planning-binding deny boundary.

### Round-17 exact repair checklist

1. Rebind custody to the current brief and matrix bytes above. Treat all prior
   adjudication hashes as historical unless a current file reproduces them; do
   not infer or assert the unknown prior actor. Record the new adjudication SHA
   only after this append, then rebind the repaired brief/matrix to it.
2. Define one route-proposal domain/codec/inverse and one locked durable writer.
   Remove or relabel `reserve_provider_route_locked` and
   `append_provider_route_decision` if they are not the same composite route
   transition as `reserve_provider_route_child`; publish the exact producer,
   applier, append/CAS, replay, and forbidden competing edges.
3. Split stable provider epoch identity from volatile fencing evidence. State
   whether liveness/membership are excluded from the failure-key preimage and
   prove that refresh alone cannot rekey, reset, or authorize an identical
   retry; add the replacement/fence vector.
4. Freeze epoch wire typing: canonical raw identity/digest versus display
   label, field by field. Align `EPOCH_ID`, claim, binding, precommit evidence,
   provider failure key, and replay equality; recompute affected lengths,
   bytes, and hashes.
5. Replace the CHILD_EVENT “decision excluded” ambiguity with an explicit
   decision or proposal-digest field and ordered preimage. Keep source link IDs
   included, self/derived IDs and child receipt excluded, and prove a
   non-circular event/child-reservation identity.
6. Publish the live `DispatchOutcome` adapter schema: exact field map,
   accepted/staged/null states, conversion codec, and the point after which
   precommit bytes are transported unchanged. Update both bridge rows and
   hashes so no live-object/raw-wire contradiction remains.
7. Name `IncidentLedger.append_terminal_outcome` as the sole physical terminal
   writer; make `record_provider_terminal_with_observation_locked` an explicit
   delegating locked adapter (or remove it), and document the single observation
   writer and cardinality/CAS path.
8. Make the A38 primary registry fully file-qualified and standalone for route
   proposal, probe, phase/dispatch, fallback, legacy migration, and planning
   binding deny edges. Replace role prose with symbols and keep generic
   `append_event` forbidden to NBF06.
9. Recompute every changed fixture/vector and publish exact checker/negative-
   fixture ownership and standalone command; do not treat absent preimplementation
   files as current test failures. Do not edit live source, frozen plan,
   tasklist, or status in this adjudication.

## Round-18 manager adjudication (sealed-packet contract review)

Current inputs are brief `fc357a58c1c881b88bd32970526ba910da6a0d45e5247eee4f8f2dceecd91d2d`,
matrix `7aef0fe9a3085d97702f604cf9d8ba3e22d51c46145f089b3496a35b5bfbc92c`,
frozen plan `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`,
and tasklist `a4f574ce02421226a0f4610ffc503918e54cd8b5f8ee28ca8e7805afaf1e3959`.

1. **A38 role prose and competing probe endpoints — ACCEPTED.** The primary
   registry is improved, but probe request/result appear both as orchestration
   transport codecs and incident wire codecs, while rows still use role prose
   such as “probe selector,” “cloud worker dispatch,” “terminal adapter,” and
   “expiry/result owner.” Without an explicit adapter boundary, the two probe
   codec families can become competing producers or writers. Keep the typed
   transport pair and durable incident pair distinct, give each exact inverse
   and file-qualified producer/consumer/writer, and make the planning-binding
   and legacy deny edges explicit in the primary A38 contract.

2. **Live `DispatchOutcome` field map, reservation ID, retryability alias, and
   bypass — ACCEPTED.** The live dataclass has no top-level
   `reservation_event_id`; it has nullable staged IDs, `provider_failure_key`,
   `semantic_dispatch_fingerprint`, and nested provider evidence. The wire
   precommit fixture requires a reservation ID and names `retryability`, while
   the live evidence uses `retryability_class`. The packet maps many fields but
   does not identify the authoritative reservation-context producer, alias
   normalization/precedence, or rejection of ignored live fields. Freeze those
   mappings and prove that non-accepted/no-launch/ambiguous outcomes cannot
   bypass typed refusal or create a T8 precommit/target.

3. **A32 aggregate fail-closed semantics — ACCEPTED.** A32 is labeled a
   supplemental aggregate while its row names one aggregate test and the
   contract separately lists three standalone commands. It does not state the
   required result when one command is missing, skipped, xfailed, or passes
   without proving pre-resolution/no-side-effect refusal. Define aggregate PASS
   as the conjunction of all three named doors, with collection/skip/xfail or
   any nonzero result failing closed; preserve independent execution and do
   not mask failure with shell composition. This is a test-contract rule, not a
   demand for present implementation tests.

4. **Epoch producer/fence, typed result, and generation semantics — ACCEPTED.**
   The packet gives an epoch fixture and says NBF-01/02 writes the claim, but
   does not name the exact locked producer/result contract or fully distinguish
   stable epoch `generation` from admission `admission_generation`. A stale or
   replaced claim therefore lacks a deterministic typed outcome and could
   accidentally alter the stable identity. Name the reservation owner and
   locked claim/binding methods, enumerate bound/replaced/stale/pending/
   `durability_unknown` results, and state that stable generation belongs to
   epoch identity while admission generation is reservation metadata excluded
   from identity/failure-key derivation.

5. **Fixture domain/version mismatches — ACCEPTED.** The same current packet
   labels fixtures and transition rows inconsistently: e.g. observation,
   hold, success, recovery, and durability-unknown literal domains are V2 while
   corresponding registry/migration rows still say V1; return and child rows
   also mix V2/V3 labels. A hash cannot repair a domain/version label mismatch.
   Choose the authoritative domain/version for every fixture, transition,
   migration row, codec, inverse, and vector, then recompute dependent bytes,
   lengths, and hashes.

6. **Probe states, timing constants, clock, and unknown reconciliation —
   MODIFIED.** The packet adds `active|passed|failed|expired|durability_unknown`,
   `provider_probe_closed`, and fixed `t0+4.999/t0+5.000/t0+5.001` boundaries,
   while the frozen plan exposes `probe_status=none|leased|passed|failed`,
   `retry_not_before`, and one bounded lease, without those numeric constants
   or a new probe state machine. The missing clock injection and unknown/expiry
   reconciliation rule are valid blockers; requiring new states or constants
   beyond the frozen plan would be overreach. Map unknown/expiry to the frozen
   unresolved/held semantics (or obtain an explicit in-scope amendment), use
   an injected clock and symbolic `retry_not_before` boundary, and define
   single-use close/reconcile/no-launch behavior.

7. **Closed decision union missing `PreToolNextTarget` — ACCEPTED.** The packet
   calls `PreToolNextTarget` the only pre-tool target choice but omits it from
   the declared closed `ProviderRouteDecision` union. That leaves the type
   contract unable to represent its own pre-tool result and permits an implicit
   selector. Add it explicitly with its pre-tool-only fields and ensure the
   post-terminal configured child remains a separate composite door.

8. **Explicit-null versus omission in precommit — ACCEPTED.** The packet says
   postcommit IDs are nullable staging values and also says the precommit wire
   has no terminal/observation/event/derived-receipt IDs. Those are distinct
   object and wire rules, but the packet does not freeze the conversion. Choose
   one exact contract; the least-surprising current vector choice is nullable
   `None` on the typed object and omission of those fields from the precommit
   wire payload. State that explicit U64BE(0) null is used only where a schema
   declares a field, and update field lists/fixtures/replay assertions.

### Round-18 exact repair checklist

1. Make A38 primary rows file-qualified end to end. Separate orchestration
   probe request/result transport codecs from incident durable codecs; name
   every inverse, producer, consumer, locked writer, and planning/legacy deny
   edge. Remove role-only endpoint prose and retain generic `append_event`
   prohibition.
2. Publish a complete live `DispatchOutcome` conversion table, including every
   live field, ignored-field rule, nullable/staged state, reservation ID source
   from admission context, `retryability_class`→wire `retryability` alias and
   mismatch rejection, provider-key precedence, and no-launch/refusal bypass
   prohibition. Recompute bridge vectors.
3. Define the A32 aggregate as a fail-closed conjunction of its three exact
   standalone commands: missing, no-collection, skip, xfail, or nonzero is not
   PASS; commands run independently with no shell masking.
4. Name the exact locked epoch claim producer and typed fence outcomes. Keep
   stable epoch `generation` in the identity; keep admission generation
   separate reservation metadata; exclude liveness/membership and admission
   generation from failure-key derivation; add stale/replaced/pending/
   durability-unknown replay vectors.
5. Create one domain/version registry and align every literal fixture,
   transition row, migration row, serializer/inverse, length, and SHA. Do not
   retain mixed V1/V2/V3 labels for identical current payloads.
6. Resolve probe semantics within frozen scope: use injected clock and
   `retry_not_before`, one bounded lease and one close/reconcile path; map
   failed, expired, and unknown to held/unresolved no-launch behavior. If a new
   enum/event is retained, document its explicit in-scope amendment and exact
   projection mapping before using it.
7. Add `PreToolNextTarget` to the closed decision union with exact pre-tool
   fields, and keep configured post-terminal child/return decisions behind the
   locked composite door.
8. Freeze typed-null versus wire-omission rules for all precommit IDs, update
   field lists and replay/length/SHA fixtures, and reject inferred postcommit
   IDs.
9. Rebind the repaired brief and matrix to the resulting adjudication SHA;
   do not edit live source, frozen plan, tasklist, or status in this
   adjudication.

**Round-18 disposition: 7 accepted, 1 modified.** The modified probe finding
accepts the missing clock/reconciliation contract but rejects unapproved
expansion of frozen probe states or numeric policy constants. All other
accepted findings are reproducible packet non-determinism or cross-artifact
contract mismatches, not implementation-absence findings.

## Round-19 manager adjudication (sealed current packet)

Inputs were rebound to the exact current bytes: brief
`e73972d638cac5850087e10e9dc2f06c6a72936c538d7105f6f75df7d37ddf4e`, matrix
`a288e155b92749eb98d8bae3683418cbdd6b62b77813e1d7d4831163f2d9acdc`, frozen
plan `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e`, and
tasklist `a4f574ce02421226a0f4610ffc503918e54cd8b5f8ee28ca8e7805afaf1e3959`.
The live source was checked in the same working tree; no implementation
absence is treated as a planning defect.

### Reproduced findings and verdicts

1. **Separate precommit schema/owner versus live `DispatchOutcome` map —
   ACCEPTED.** The packet correctly insists on a separate precommit domain and
   a one-way adapter, but its advertised staged fields are not the live
   object: `phase_result.py:DispatchOutcome` has `terminal_outcome_event_id`
   and `reconciliation_event_id`, but no `reservation_event_id`,
   `observation_id`, `event_id`, or `derived_receipt_id`. The matrix's
   `DISPATCH_OUTCOME_STAGE` nevertheless describes those latter names as
   nullable fields on the typed object. That is a reproducible source/packet
   mismatch. The map must enumerate the actual `_FIELDS` set, each mapped,
   ignored, or externally supplied value, and distinguish object-to-wire
   re-encoding from a lossless `to_dict`/`from_dict` round trip. “Unchanged”
   may describe transport after conversion only.

2. **Wrong A38 `_advance_configured_spec_fallback` path — REJECTED.** The
   asserted defect is not present in the sealed packet. Matrix A38 names
   `arnold_pipelines/megaplan/workers/_impl.py:_advance_configured_spec_fallback`,
   and the live definition and call sites are there (the codec/refusal owner
   is separately in `fallback_chains.py`). A reviewer confusing the codec
   module with the actual advance door has not reproduced a blocker. Preserve
   the file-qualified `workers/_impl.py` path and the separate
   `fallback_chains.py:ExecuteFallbackUnsafe` owner.

3. **Receipt authority cloud/NBF-02 versus NBF-01 — REJECTED.** The current
   brief and matrix explicitly make NBF-01 the `WorkerAdmissionReceipt` byte/ID
   owner, make NBF-02 the consumer at the dispatch seam, and constrain cloud
   transport to bytes-only. NBF-06 stores/links but does not mint, rewrite, or
   reinterpret the receipt. This finding is already settled; adding a second
   receipt authority would contradict the packet.

4. **Explicit NBF-02 dispatch-seam handoff and order — ACCEPTED.** “One typed
   policy call after accepted terminal normalization” is not an executable
   handoff contract. The packet must name `cloud/worker_dispatch.py:
   dispatch_with_admission` as the NBF-02 seam and publish one ordered chain:
   pre-tool admission and reservation/receipt, epoch binding, accepted-launch
   adapter evidence, terminal normalization, one provider-policy call,
   locked terminal/observation commit, and only then postcommit envelope or
   child/return application. It must state which typed value crosses every
   edge and prohibit policy selection before admission, a second call through
   compatibility entrances, or a bypass around the seam. This is packet
   non-determinism, not a claim that the current source already implements
   NBF-06.

5. **`select_provider_probe` as adapter, not a second selector — ACCEPTED.**
   The matrix currently shows a transport path into `select_provider_probe`,
   but does not bind its input to the same parent admission receipt,
   reservation, configured-chain identity, failure key, epoch claim/binding,
   route, and lease fence used by the route selector. The revision must define
   it as a pure/adaptor request constructor over the locked immutable
   `ProviderLedgerView`; it returns a typed probe request and cannot choose a
   route, create a target, launch a client, or append durable state. The
   absence of this planned function in live source is expected before
   implementation and is not itself evidence.

6. **Ordinary legacy terminal domain — ACCEPTED.** The migration table labels
   “ordinary legacy terminal V1” with `NBF06-PROVIDER-TERMINAL-V1` while also
   saying it is ordinary and never provider-upgraded. Those assertions cannot
   both define a domain-safe decoder. Ordinary legacy records must retain the
   existing NBF-01 ordinary `worker_terminal_outcome` domain/version and its
   codec; the provider-terminal codec must be a distinct NBF-06 domain/version.
   The row must name the real legacy domain from NBF-01, preserve null versus
   omission, and reject inference or upgrade. This is a migration-contract
   ambiguity, not a demand for already-existing NBF-06 serializers.

7. **Complete A38 alternate entrances and aliases — ACCEPTED.** The primary
   rows cover the core route and several execute/fanout/loop refusals, but the
   alternate integration surface remains partly owner prose. A38 must have
   literal file-qualified rows for `resolve_agent_mode`/AgentMode propagation,
   `run_step_with_worker`, execute batch, worker fanout, loop/runtime,
   `handlers/shared.py`, `auto.py`, managed cloud launch, and `workers/omp.py`,
   each with producer → transport → consumer → policy/effect or refusal edge.
   It must also list aliases (including the chain identity display alias,
   retryability/provider-class aliases, and the configured-chain advance
   symbol) and identify which canonical symbol they resolve to. No grouped
   role prose, competing selector, hidden launch path, or alternate writer is
   allowed. Missing future implementation files are not a failure; missing
   literal planned edges and alias rules are.

### Finite Round-19 repair checklist

1. Replace `DISPATCH_OUTCOME_FIELDS/STAGE` with the exact live
   `DispatchOutcome._FIELDS` list from `phase_result.py`; for every field mark
   `mapped`, `ignored`, `staged-after-commit`, or `supplied by the accepted
   admission context`. Remove invented typed fields and explicitly document
   the one-way precommit conversion versus lossless live-object serialization.
2. Keep `reservation_event_id` external to `DispatchOutcome`: require the
   accepted `dispatch_with_admission` context, reject missing/mismatched
   context, and include that rule in the bridge fixture and inverse contract.
3. Add a file-qualified NBF-02 handoff/order table centered on
   `cloud/worker_dispatch.py:dispatch_with_admission`, with exactly one policy
   invocation and explicit pre-tool, terminal, observation, and postcommit
   boundaries; show every compatibility entrance as a delegating path.
4. Define `select_provider_probe` as a pure adapter over the immutable parent
   view and list all parent bindings (admission/reservation/chain/key/epoch/
   route/lease). Its transport inverse ends before the locked probe-result
   writer; it never selects a second route or writes the ledger.
5. Split the ordinary NBF-01 legacy terminal migration row from
   `NBF06-PROVIDER-TERMINAL-V1`; use the actual ordinary domain/version and
   retain no-upgrade, null/omission, unknown-field, and replay rules.
6. Expand the A38 registry with standalone, file-qualified rows for every
   AgentMode, runtime, shared, auto, managed, OMP, batch, fanout, and loop
   entrance, plus canonical alias → owner mappings and forbidden bypasses.
   Keep `_advance_configured_spec_fallback` at
   `workers/_impl.py`; keep `ExecuteFallbackUnsafe` at
   `fallback_chains.py`; retain the explicit NBF-01 receipt owner row.
7. Recompute any changed bridge/migration/allowlist fixtures and hashes, then
   rebind the repaired packet custody to the resulting adjudication SHA. Do
   not modify live source, frozen plan, tasklist, or status in this repair.

**Round-19 disposition: 5 accepted, 2 rejected.** Accepted findings identify
remaining reproducible schema, ordering, domain, probe-binding, and A38
coverage ambiguity. The path and receipt findings are rejected because the
sealed bytes and live source directly contradict those alleged defects.

## Round-20 manager adjudication (sealed current packet)

Inputs were checked at the requested custody boundary: brief
`baadedc70fcfa1399e4e5c1f97af55bf431d5e13f6e631e1e5758fb696d91466`, matrix
`ee6cb294d7e23eddc8a92a67c9f7fe73583efc2984c9884ffd527e667677dd83`, frozen
plan `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e`,
tasklist `a4f574ce02421226a0f4610ffc503918e54cd8b5f8ee28ca8e7805afaf1e3959`,
and prior adjudication `ff7f561bcc47eadbfd2a386045d981ba4c2f1cef01ce0078487e9f5fdb3e1f33`.
The source tree is intentionally preimplementation; source inspection below
is used to identify frozen seams and existing compatibility behavior, not to
require NBF-06 symbols to exist already.

### Reproduced findings and verdicts

1. **Existing terminal append versus planned T8 policy order — MODIFIED,
   accepted as a planning blocker.** The live NBF-02 seam normalizes an
   accepted `DispatchOutcome` and immediately calls the existing sole writer
   `IncidentLedger.append_terminal_outcome` (`cloud/worker_dispatch.py:1363-1369`);
   no T8 policy call exists in the current implementation. The packet instead
   specifies `select_provider_route` followed by
   `apply_provider_route_decision_locked`, whose terminal/observation commit
   is described as occurring after the policy decision. That source fact is not
   an implementation failure, but the packet must not silently present the two
   orders as the same protocol. It must state whether the planned T8 applier
   invokes the frozen writer in one atomic terminal+observation operation
   before any route effect, or whether an append-first legacy cutpoint is
   retained and reconciled before policy effects. In either design, crashes at
   pre-append, terminal-only, terminal-plus-observation, and post-policy
   cutpoints must replay idempotently with no duplicate terminal/observation or
   child. Ownership of the physical terminal writer remains NBF-01; this
   finding does not authorize a second writer or require a source edit now.

2. **Passed probe must close before recovery/child — ACCEPTED.** The packet
   says that only an explicitly closed lease permits the post-close retry, and
   it has separate `PROBE_RESULT`, `PROBE_CLOSED`, and
   `provider_recovery_verified` rows, but the recovery row still lists only
   “passed single-use evidence” as its precondition. A passed executor result
   must not itself authorize recovery or a child while the lease is still
   open. Closure must first CAS the exact lease/result to `closed` (and only a
   passed closure may proceed); then `provider_recovery_verified` consumes that
   closed, single-use proof; only then may the locked child reservation door
   run. Failed, expired, unknown, duplicate, late, or unclosed results remain
   held/unresolved and cannot route or launch.

3. **Positive auth/quota/rate-limit tests and replacements — ACCEPTED with a
   precise compatibility distinction.** The current source tests contain
   behavior that conflicts with the current NBF-06 v1 contract: fallback-chain
   quota classification/advance assertions (`test_cross_family_advance_membership`,
   `test_codex_auth_error_surface_classifies_as_auth`,
   `test_codex_no_credits_surface_classifies_as_quota`), direct fanout
   advancement (`test_cross_family_quota_advances`), and the GPT-5.6 launch-time
   quota advancement (`test_launch_time_quota_advances_non_read_only_plan`).
   The packet expressly says auth, quota, rate-limit, unsupported, context,
   internal, and timeout classes do not create T8 exhaustion or a v1
   `PreToolNextTarget`/configured-chain advance. Those positive tests cannot
   be silently treated as NBF-06 evidence. Low-level classifier tests may be
   retained only as clearly labelled pre-existing generic compatibility
   characterization; their prose and gate status must not claim T8 authority.
   The fanout and GPT-5.6 positive quota advances require negative replacements
   proving no second resolution/worker effect. The parameterized GPT-5.6
   cases must similarly remove or reclassify rate-limit/unsupported advances;
   availability/infrastructure positive behavior may remain only where it is
   explicitly the eligible operational class and is outside the execute
   prohibition. The matrix must name the replacement tests and their exact
   paths. Existing auth/rate-limit negative fanout coverage is compatible but
   is not a substitute for the missing cross-path disposition table.

4. **Recovery/breaker ownership and bypass boundaries — ACCEPTED.** The
   packet says T8 bypasses generic failure/breaker accounting while genuine
   internal errors retain existing behavior, but neither the ownership table
   nor A38 gives a complete boundary for the live generic paths. In source,
   `orchestration/phase_result_classify.py` classifies external payloads and
   dispatch outcomes, `orchestration/recovery_policy.py:RecoveryPolicy` owns
   generic retry/escalation, and `incident/disposition.py` owns disposition
   persistence/signal projection. The plan must state that typed T8
   `provider_exhausted` is intercepted at the NBF-02/T8 seam before generic
   breaker/blocker accounting; `phase_result_classify` is only the typed
   adapter; `RecoveryPolicy` remains the generic owner for non-T8 cases,
   including repeated `internal_error`; and `incident/disposition.py` remains
   signal/disposition authority, never a T8 terminal, observation, or route
   writer. Any compatibility call from these modules must be a named
   delegate/deny edge, with no T8 bypass and no blanket exemption that changes
   internal-error behavior.

### Finite Round-20 repair checklist

1. Add one authoritative terminal/policy transaction diagram to the brief and
   matrix. Identify the frozen `IncidentLedger.append_terminal_outcome` call,
   the exact point at which T8 sees structured evidence, and whether the
   terminal+observation CAS is performed before or inside the T8 applier. Add
   four crash/replay vectors (before append, terminal-only, terminal plus
   observation, post-policy) and require one terminal/observation cardinality.
2. Add `provider_probe_closed` as an explicit precondition and parent binding
   of `provider_recovery_verified`; require passed result → exact close CAS →
   recovery proof → child reservation. Add rejection vectors for passed-but-
   open, duplicate close, late result, and unknown/expired closure.
3. Create a disposition table for the named existing tests: retain classifier
   cases only as non-T8 characterization, replace direct fanout/GPT-5.6
   quota advances with no-advance/no-side-effect assertions, and explicitly
   classify rate-limit/auth/unsupported cases. Add exact replacement test
   paths to the A01–A38 registry; do not claim a generic positive quota test
   proves NBF-06 v1 behavior.
4. Add file-qualified A38 rows for
   `orchestration/phase_result_classify.py:classify_dispatch_outcome` and
   `classify_external_error_payload`,
   `orchestration/recovery_policy.py:RecoveryPolicy.classify` (and its
   circuit wrapper), and `incident/disposition.py:record_disposition` plus
   its terminal projection helpers. Show T8-before-generic ordering, the
   internal-error path, the signal/disposition deny boundary, and all
   compatibility delegates; prohibit duplicate breaker, terminal,
   observation, or route writers.
5. Recompute only changed packet/matrix fixture references and rebind their
   custody to the resulting adjudication SHA. Do not edit live source, tests,
   frozen plan, tasklist, or status in this adjudication.

**Round-20 disposition: 3 accepted, 1 modified.** The accepted findings are
reproducible lifecycle, test-contract, and ownership gaps. The terminal-order
finding is modified because the current append-first source behavior is a
pre-existing seam, not an NBF-06 implementation failure; the packet must
nevertheless choose and make crash-safe one integration order.

## Round-21 manager adjudication (sealed current packet)

The custody inputs for this round are brief
`a53b13aba3f2442d1fa2b3847db28383bc5f88bb5463b7c34c904c40090bceb1`, matrix
`f36f99e71e65dbb6e2f2dbf3fffe70b171559c0151afe5c71107d57f13165d9f`, frozen
plan `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e`,
tasklist `a4f574ce02421226a0f4610ffc503918e54cd8b5f8ee28ca8e7805afaf1e3959`,
and prior adjudication `a38e8aa17c2fb9141d81d0b0367bb89eba0c1b567838da4cc791497b67d21466`.
The tree remains deliberately preimplementation; absence of planned NBF-06
symbols is not itself a defect. The following findings were checked against
the sealed packet and the live source.

### Reproduced findings and verdicts

1. **Stale `phase_result_classify` path — MODIFIED (narrow correction
   accepted).** The broad claim that the orchestration path is stale is false:
   the live file is
   `arnold_pipelines/megaplan/orchestration/phase_result_classify.py`, and it
   contains both `classify_external_error_payload` and
   `classify_dispatch_outcome`. The packet correctly uses that path for the
   typed classification adapter and correctly uses
   `orchestration/phase_result.py:DispatchOutcome` for the live outcome. It
   does, however, contain one real stale compatibility entry at brief line 91:
   `arnold_pipelines/megaplan/phase_result_classify.py` (without
   `orchestration`), a path absent from the source tree. This is a literal
   packet error limited to that row; it does not justify relocating the
   classifier or treating the `DispatchOutcome` path as a classifier owner.

2. **Wrong primary A38 `_advance` path despite alias — REJECTED.** The sealed
   matrix's primary row names
   `arnold_pipelines/megaplan/workers/_impl.py:_advance_configured_spec_fallback`
   (line 478), and the brief names the same owner. The live source defines it
   in `_impl.py` and its call sites are there; `fallback_chains.py` owns the
   chain codec/classifiers and `ExecuteFallbackUnsafe`, not the advancement
   operation. The alias-resolution concern is already answered by the packet's
   separate alias rule. No primary-owner change is warranted; retain the
   distinct refusal owner and do not create a second `_advance` row.

3. **V2 recovery proof versus canonical `ChangedPrecondition` bridge —
   ACCEPTED.** The packet establishes a separate wire domain,
   `NBF06-PROVIDER-RECOVERY-VERIFIED-V2`, and correctly requires a passed,
   closed probe before a child. It does not make the relation to the existing
   NBF-01 canonical event operationally explicit. The live source has
   `incident/schema.py:ChangedPrecondition`, the fixed reason-specific producer
   `produce_provider_recovery_verified`, and ledger append/consume paths. The
   plan must say that the V2 recovery payload is evidence/protocol transport,
   while the authoritative changed-precondition event is produced by the
   reason-specific NBF-01 producer, appended once, consumed once, and linked
   by the recovery proof/child authorization. It must define the exact field
   mapping, including the before/after key equality rule, proof/evidence
   digest, parent admission/observation/epoch bindings, and the
   `authorizing_event_id`/consumption field used by the child. A V2 decoder
   must not silently manufacture a `ChangedPrecondition`; a child must not
   treat an uncommitted V2 record or an unconsumed canonical event as proof.
   This bridge must remain cycle-free and preserve the existing NBF-01
   authoritative-source validation.

4. **Incomplete nested `provider_evidence` precommit staging and
   reconstruction — ACCEPTED.** The matrix names the nested epoch, key,
   retryability, and provider-class mappings, and correctly omits staged
   postcommit IDs. That is not a complete nested contract: the live
   `DispatchOutcome.provider_evidence` is an open `Any` payload, while the
   precommit fixture only proves the flattened outer fields. Add one closed
   nested schema/table naming every required field, type, raw32/null/omission
   rule, version, and authoritative producer. Define the forward conversion
   from accepted live `DispatchOutcome` and the inverse reconstruction back to
   the typed staged object, including accepted-admission context and nested
   `provider_failure_key` authority. Missing, unknown, conflicting, or
   top-level-alias-mismatched nested evidence must reject; postcommit terminal,
   observation, reconciliation, and derived-receipt IDs must remain staged or
   omitted exactly as specified and never be inferred. Add a fixture for a
   complete nested payload and negative fixtures for missing/conflicting
   members. This is a packet determinism requirement, not a demand that the
   implementation already exist.

5. **Canonical provider-family vocabulary/mapping and dependent epoch
   vectors — ACCEPTED.** The live classifier is concrete: `fallback_chains.py:
   provider_family` derives the upstream family for `omp` routes and aliases
   `openai-codex→codex` and `grok→xai`; the existing test maps
   `omp:deepseek/deepseek-v4-pro→deepseek` and
   `omp:fireworks/kimi-k2.6→fireworks`. The sealed epoch fixture uses
   `family=fireworks` with normalized spec
   `omp:deepseek/deepseek-chat`, without publishing a mapping that could make
   that value canonical. This is a reproducible identity/vector defect, not a
   request for a new provider cache. Publish one canonical vocabulary and a
   total normalization/alias table for every configured spec form, state
   whether family means upstream provider rather than transport `omp`, and
   apply it consistently to epoch identity, epoch claim/binding, failure-key
   inputs, target/return proofs, child/branch vectors, probe bindings, and
   family-crossing decisions. Recompute all affected literal bytes and hashes;
   liveness/membership evidence remains fencing-only and must not enter stable
   family identity.

6. **Exact `select_provider_route` signature and authority — ACCEPTED.** The
   brief contradicts itself: the NBF-02 sequence says
   `select_provider_route(view)`, while the route section says
   `select_provider_route(request, ledger_view)`; the matrix gives only the
   symbol and role. This is a real planning ambiguity even though the planned
   module is not yet implemented. The canonical contract should use the
   section's two typed immutable inputs,
   `arnold_pipelines/megaplan/orchestration/provider_resilience.py:
   select_provider_route(request, ledger_view)`, with the request and
   `ProviderLedgerView` schemas named, or deliberately fold request into the
   view and change every occurrence to the one-argument form. The packet must
   choose one; this adjudication does not permit both. In either form it is a
   pure function: no append, launch, cache, lock mutation, observation, or
   child effect. `dispatch_with_admission` is the sole NBF-02 caller and the
   locked applier is the sole effect door; aliases and compatibility entrances
   delegate to that authority rather than select independently.

### Finite Round-21 repair checklist

1. Correct the brief's compatibility row from the nonexistent
   `arnold_pipelines/megaplan/phase_result_classify.py` to the actual
   `.../orchestration/phase_result_classify.py`; retain
   `phase_result.py:DispatchOutcome` only for the live outcome codec/bridge.
2. Add the explicit V2-recovery → NBF-01 `ChangedPrecondition` bridge:
   producer, append writer, consume CAS, exact field mapping and proof/child
   authorization linkage; reject open, uncommitted, duplicate, or mismatched
   proof and preserve the no-cycle identity rule.
3. Publish the complete nested `provider_evidence` precommit schema and
   live-object forward/inverse staging table, with required fields,
   nullability/omission, aliases, context equality, unknown/conflict rejection,
   and complete/negative fixtures.
4. Publish the canonical provider-family map and aliases, correct the
   deepseek/fireworks epoch-family fixture, and recompute epoch claim/binding,
   failure-key, child/branch/return, probe, and any dependent hashes.
5. Choose and use exactly one selector signature; make
   `select_provider_route(request, ledger_view)` the file-qualified pure
   authority (or consistently document the folded one-argument alternative),
   then update the NBF-02 sequence, A38 rows, caller edge, and fixture schema.
6. Rebind the repaired brief/matrix custody to their new hashes and this
   adjudication SHA. Do not edit live source, frozen plan, tasklist, tests,
   status, or any artifact other than the packet owners' subsequent revision.

**Round-21 disposition: 4 accepted, 1 modified, 1 rejected.** The accepted
items are the recovery-identity bridge, nested evidence closure, family/vector
identity mismatch, and selector signature ambiguity. The path finding is
accepted only as a one-row correction; the alleged `_advance` primary-owner
defect is rejected by the sealed matrix and live source.

## Round-22 manager adjudication (stopped sequential Luna gate)

This is a manager adjudication of the stopped sequential Luna gate. No further
review was commissioned. Custody is bound to the exact candidate packet:

| Artifact | SHA-256 |
|---|---|
| brief | `32b9a2cffba2c87fcf28553ef3293d33c88063d4ce9c1f474b166e11ed37926b` |
| authoritative matrix | `799e8319f5efa220597b66d361436797e461a655f7ae372f4a12a01211829c0f` |
| frozen plan | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| frozen tasklist | `a4f574ce02421226a0f4610ffc503918e54cd8b5f8ee28ca8e7805afaf1e3959` |
| prior adjudication input | `b7fdcbd50ef19437273aa62049a6c4c2f87e2ad7942114f9ff6336649da6a67b` |
| live source checkout | `887c25cf8fddcd14fde24fce49697b9c8b3188b0` |

### Reproduced findings and verdicts

Verdicts distinguish a packet defect that prevents deterministic
implementation/acceptance from a source absence expected in this
preimplementation tree. Accepted findings are blocking for packet readiness;
the repair checklist below is finite and does not authorize source, tasklist,
status, or review changes.

1. **Stale A38 `_advance_configured_spec_fallback` owner path — REJECTED.**
   The alleged stale path is not stale: the live source defines
   `arnold_pipelines/megaplan/workers/_impl.py:_advance_configured_spec_fallback`
   at `workers/_impl.py:7777` and calls it at `:8576` and `:8632`. The matrix
   separately assigns `fallback_chains.py:ExecuteFallbackUnsafe` as the typed
   execute-refusal owner and `fallback_chains.py:encode_fallback_specs` as the
   codec. Those are distinct responsibilities, and the A38 rows and aliases
   preserve that distinction. No owner relocation or duplicate A38 row is
   warranted. The source's pre-NBF-06 silent `None` behavior remains an
   implementation obligation already covered by the frozen contract, not a
   stale-path defect.

2. **Complete nested evidence fixture is a placeholder — ACCEPTED.** The
   packet names `NBF06-PROVIDER-EVIDENCE-NESTED-V1`, its required fields, and
   five negative fixture labels, but provides neither a literal nested payload
   nor literal bytes/hash nor actual negative fixture content. It even says
   those fixtures are expected to be absent until implementation. That is
   insufficient for the packet's exact-SHA/deterministic precommit contract:
   a future implementation cannot prove the complete nested shape or reject
   each named failure from the packet alone. This is a packet blocker, not a
   demand that the current source already contain NBF-06 tests.

3. **Nested precommit evidence loses fields and cannot invert — ACCEPTED.**
   The packet requires `observation_id`, `exhausted_attempt_count`,
   `terminal_provider_evidence_id`, `precondition_identity`, and `observed_at`
   in the live nested record, but the published `PRECOMMIT_EVIDENCE` and
   `DISPATCH_OUTCOME` vectors carry only flattened epoch/key/retryability/
   provider-class values. The claimed inverse therefore cannot reconstruct the
   same nested object; the current `DispatchOutcome.provider_evidence` is also
   an open `Any` mapping in live source (`phase_result.py:135`). This is a
   deterministic schema/losslessness blocker. The packet must choose one
   closed wire representation that preserves those fields (or explicitly
   scope the inverse to a retained typed sidecar), specify its exact mapping,
   and rebind every affected vector; postcommit IDs must remain omitted and
   must never be inferred.

4. **No deterministic canonical CHAIN codec owner versus legacy
   `encode_fallback_specs` — ACCEPTED.** The packet defines canonical
   `NBF06-CHAIN-ID-V1` framed bytes and a `CHAIN(175)` digest, yet its A38
   primary registry names
   `fallback_chains.py:encode_fallback_specs`/`decode_fallback_specs` as the
   chain serializer. Live `encode_fallback_specs` (`fallback_chains.py:213-218`)
   emits the reserved `__fallback_json__:` JSON string, not the framed CHAIN
   bytes. Calling the legacy codec the canonical A38 serializer leaves chain
   identity authority and replay bytes ambiguous. This is a blocking owner /
   identity defect. The packet must designate one file-qualified canonical
   CHAIN serializer/inverse, demote the JSON codec to a named compatibility
   persistence adapter (or consistently replace it and recompute the fixture),
   and state the sole identity producer and all alias/negative rules.

5. **Probe timing formulas, clock, and reconciliation underspecified —
   ACCEPTED (bounded to frozen scope).** The packet freezes the symbolic
   boundary `now >= retry_not_before`, an injected clock, one bounded lease,
   and one close/reconcile CAS, but does not define how `retry_not_before` is
   derived, the clock units/monotonic contract, the bounded-lease expiration
   comparison, or the exact reconciliation precedence for unknown, expired,
   duplicate, and late results. The existing fields and four-state projection
   are enough to close this without adding state or constants. The ambiguity
   nevertheless blocks deterministic implementation and A08/A10/A33 evidence.
   Treat this as a formula/clock/reconciliation contract repair only: do not
   add a new state, timer field, scheduler, lease store, or policy constant.

6. **Epoch identity wording/version/generation contradiction — MODIFIED.**
   The current packet has mostly separated the concepts: `NBF06-PROVIDER-
   EPOCH-ID-V2` is the protocol/domain version, stable identity includes
   `family, normalized_spec, generation`, and `admission_generation` plus
   liveness/membership are excluded metadata/fencing fields. Thus a claim that
   the bytes are intrinsically contradictory is overstated. A real naming
   ambiguity remains because the frozen plan also uses “proof generation” for
   native liveness evidence while the NBF-06 fixture uses bare `generation`,
   and the claim table repeats both `version` and `generation` without naming
   their authority/type. This is a narrow packet repair, not permission to
   expand state. Use explicit names such as protocol `version`, stable
   `provider_epoch_generation`, and reservation `admission_generation`, name
   their authoritative producer and types, state that native proof generation
   is separate fencing evidence, and recompute only vectors whose ordered
   field labels/values actually change.

7. **Selector signature/authority — REJECTED for the current packet.** The
   alleged one-argument/two-argument conflict is gone: every current brief and
   matrix occurrence uses the exact two-input
   `arnold_pipelines/megaplan/orchestration/provider_resilience.py:select_provider_route(request, ledger_view)`
   form. The packet names typed immutable request and `ProviderLedgerView`,
   makes the selector pure, restricts its caller to
   `dispatch_with_admission`, and assigns effects to
   `apply_provider_route_decision_locked`. The planned module's absence in
   the preimplementation source is expected. No selector redesign or second
   authority is justified; implementation must simply honor the already
   settled contract.

### Finite Round-22 repair checklist

1. Add one literal complete `NBF06-PROVIDER-EVIDENCE-NESTED-V1` fixture with
   ordered fields, byte length, SHA, and the five named negative fixtures;
   bind the fixture to the A01–A38 registry.
2. Close the precommit nested-evidence wire contract: preserve and invert all
   required nested fields, define the exact field placement and raw32/null /
   omission rules, reject missing/unknown/conflicting members, retain accepted
   admission-context equality, and recompute affected precommit/bridge hashes
   without introducing postcommit IDs.
3. Resolve CHAIN ownership: name the one canonical framed serializer/inverse
   and identity producer, mark legacy `encode_fallback_specs` as compatibility
   only (or revise the whole contract consistently), and add a negative test
   that legacy JSON bytes cannot stand in for `NBF06-CHAIN-ID-V1`.
4. Specify probe timing using the existing fields only: injected monotonic
   clock and units, exact `retry_not_before` derivation, lease-boundary
   comparison, close/reconcile CAS precedence for passed/failed/unknown /
   expired/late/duplicate results, and replay outcomes. Update A08/A10/A33
   command/evidence text and any changed literal hashes.
5. Rename/document epoch concepts without expanding state: protocol version,
   stable provider-epoch generation, reservation admission generation, and
   native liveness proof generation must each have one type, producer, and
   inclusion/exclusion rule; recompute only dependent vectors.
6. Rebind the revised brief and matrix custody to their resulting SHAs and
   record this adjudication artifact SHA. Do not edit live source, frozen plan,
   tasklist, status, or any other artifact in this adjudication.

**Round-22 disposition: 4 accepted, 1 modified, 2 rejected.** The accepted
blockers are nested fixture closure, nested-wire losslessness, canonical CHAIN
ownership, and probe timing/reconciliation. Epoch terminology needs a bounded
repair. The alleged `_advance` stale path and selector conflict are not
reproducible against the sealed packet/live source.

## Round 23 — Sol oracle adjudication

**Candidate custody.** Source HEAD
`887c25cf8fddcd14fde24fce49697b9c8b3188b0`, plan SHA
`0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`,
tasklist SHA
`a4f574ce02421226a0f4610ffc503918e54cd8b5f8ee28ca8e7805afaf1e3959`,
brief SHA `c70672637b67463a8a5868b4aea90b39119baa5ca9ba00888e4f697f2307850a`,
matrix SHA `589f5bb884aedbecacd6cd72f4da64994b61780b34506aa785d7d28512def9b2`,
and prior-adjudication SHA
`467366deaef4d7056fce9b70a596b26282789d4ae56ad1564e9c2c47d10cc4ca`
all matched before this append.

1. **Canonical authorization IDs allegedly missing from `RECOVERY(284)` and
   `CHILD_EVENT(475)` — REJECTED.** This conflates NBF-06 transport preimages
   with the canonical NBF-01 ledger event. The plan already requires
   `authorizing_event_id` and
   `consumed_changed_precondition_event_id` on the atomic composite child
   record (`.oracle/plan.md:566-607`). The repaired brief explicitly makes V2
   recovery evidence-only, assigns one producer-derived
   `ChangedPrecondition` append, and records both IDs at single-use child
   consumption (`.oracle/briefs/nbf06-provider-resilience-implementation.md:316-333`).
   The matrix repeats that exact bridge and rejects decoder minting, foreign or
   open leases, conflicts, replay cycles, and duplicate consumption
   (`.oracle/research/nbf06-acceptance-test-matrix.md:63-76,388-395,426-438`).
   Live `reserve_provider_route_child` derives and writes both fields and
   replay marks that canonical change consumed
   (`arnold_pipelines/megaplan/incident/ledger.py:568-597,1072-1127`). Adding
   canonical consumption IDs to the transport fixtures would duplicate the
   existing authority and is not needed to choose an implementation.

2. **Probe replay allegedly requires a new persisted clock/state authority —
   REJECTED as stale-baseline.** The Round-22 repair is present: the brief and
   matrix freeze injected `MonotonicClock.now_ns()`, unsigned nanoseconds,
   `retry_not_before_ns=max(parent_retry_not_before_ns,terminal_observed_ns)`,
   persisted retry/deadline boundaries, inclusive eligibility/expiry,
   rollback fail-closed behavior, one close/reconcile CAS, duplicate replay,
   and exact result-versus-expiry precedence
   (`.oracle/briefs/nbf06-provider-resilience-implementation.md:428-476`;
   `.oracle/research/nbf06-acceptance-test-matrix.md:345-375,433-435`). The
   canonical persisted replay boundary is the derived `retry_not_before` plus
   the lease deadline/closure record; its derivation operands need not become
   independent authorities. The live ISO/float helpers at
   `arnold_pipelines/megaplan/incident/ledger.py:1329-1371` are the
   preimplementation baseline assigned to NBF-06, not a packet contradiction.

**Exact finite repair checklist:** none. Both findings are rejected; no packet,
plan, tasklist, source, state, schema, clock, store, scheduler, or acceptance
change is authorized.

**North Star alignment.** This preserves the one canonical
`ChangedPrecondition` consumption door, prevents redispatch of an unchanged
fingerprint, and refuses both duplicate authorization fields in transport
fixtures and a second clock/store authority.

**Round-23 disposition: 0 accepted, 0 modified, 2 rejected.**
