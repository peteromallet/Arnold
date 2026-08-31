# Batch-2 rework attempt-3 — Sol triage packet

## Triage status and boundary

This append-only packet is Oracle triage evidence only. It is not
implementation, a fresh review, a Batch-2 gate, or an Oracle verdict. It does
not authorize implementation, review launch, staging, commit, push, merge,
history rewrite, Batch 3, or mutation of source, tests, status, frozen inputs,
custody, agent goal, or any prior artifact.

No model, subagent, Luna worker, reviewer, fallback, fanout, or nested harness
was launched during this triage. Megaplan was not invoked because it would
create outputs beyond the two paths authorized for this leaf.

Exactly four remaining must-level roots are accepted and deduplicated, in this
strict execution order:

1. `R3-NATIVE-001` — native proof authenticity and recomputation;
2. `R3-TERM-002` — production-door typed terminal transport;
3. `R3-LIFE-003` — stale-marker lifecycle reconciliation;
4. `R3-AUTH-004` — checker adversarial category completeness.

The later executor must be exactly one serial writer using GPT-5.6 Luna. Every
item is `Normal`; none satisfies the exceptional `[XHARD]` threshold, and Sol
is forbidden for implementation absent complete irreducible-judgment evidence.

The prior direct passes `B2-RTB-001`, `B2-CHILD-005`, `B2-OMP-006`, and
`B2-SCHED-008` remain preserved. No new direct evidence disproves them. The
four babysitter failures remain unchanged baseline evidence and are not rework.

## Immutable binding

| Binding | Independently verified identity |
|---|---|
| Repository / branch | `/Users/peteromalley/Documents/Arnold-oracle-nbf` / `megado-nbf-guard-0826` |
| Current HEAD | `2297fb330cdb375b4e5bd048f0d5c37d0e06db30` |
| Source/base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` |
| Candidate implementation | `5da26ec5be4d13559948fe4256a114ad7626482b` |
| Candidate parent / tree | `19deab5bb407273e7e82d40a66fc06d17af93ad4` / `e3d0376482154c4f95d2ec5809d630c4a0c32e69` |
| Candidate canonical production+focused diff | 392,090 bytes / `5586c1861dce44334c3991e997bdc8b90b82d25d2ed8f28bb558b42aae499fd0` |
| Attempt-2 source/test diff | 72,757 bytes / `a3465991e84b88b3b9177002db630ba32f8d02fdc7726a61b510cc85eb392697` |
| Frozen tasklist | `.oracle/tasklist.md` / `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| Frozen North Star | `.oracle/northstar.md` / `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| Frozen plan | `.oracle/plan.md` / `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| Frozen agent goal | `.oracle/agent_goal.md` / `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` |
| Frozen custody | `.oracle/custody.md` / `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| Policy override | `.oracle/receipts/model-policy-override-batch2-sol.md` / `6ab820892edaca0bd1b60bbd8a4934904b2f0d3a7704aaa77477779c6218085b` |
| Attempt-2 packet / triage brief / receipt | `cba6d2236a7bae5bd12f38f38ad775ca800ed19dc3ba79c14ac6e00d3d78ff83` / `95971b60f1cfb0453a180f9f17e5243c00b8b811dd1d90c6fd9ff01bbe425730` / `4d1d9bde6740897e84e99ac34d050055eb7f7c12a4823f65fe2cb7e04e007ed3` |
| Attempt-2 execution brief / finding / receipt | `7d7a807309dac3d2704ee05f66f6f597feff7d63a1b1e46d2b7b4d8898da0c87` / `f1e3b9521bd15e932a87be921325af901c78e9dde06fd2729d7bf502c722e7d4` / `ea9723a96c8e6d7e9cb7b68a3352d6dc34b03b81dfd47011d0599db6a7844425` |
| Attempt-2 Luna gate check-in / receipt | `aaccbc2b21360f01bc9e0ecc876544ab6a77240b7397da308b3973f5d7b8ab41` / `b463af00062bf30f0c19d5e37b20c4abb3d3db53d8283b8883a45096ff3a84eb` |
| Attempt-2 Sol gate check-in / receipt | `4b33d0106f6dc5cb8f32ce53220671e07d7d0c50b45488d8123e77acdb01d6e4` / `ca044383cb39fc9e3c3c0c713413485f0d51a23c43115e96efb6eb5b160f505c` |
| Rework-1 Luna check-in / receipt | `78ab46f94529728cfbfdbb72828949e323dfe3177dd7231c37a1a27bbea38f45` / `e758d5d1928019ad0356f23b0992147714bd00280da8e8adbdef06616b8fd1d3` |
| Rework-1 Sol check-in / receipt | `4230d985d68e88a7660db189d963e0c028d072efbb95474bc11e28dee9344245` / `a4e8a005920465a5a8e4441924738bae3d44562779add42863601736a1128462` |
| Original Luna check-in / receipt | `0b9e339ae594039e44be5328ea26a5f210e0347d779a0c7c4309a2e21d7d9613` / `2f092fd5ac5c1dd6e254d45241e80bab265beefc9f132d8b2a59e9b31bb89a5e` |
| Original Sol check-in / receipt | `3c222d8ab50f591b5b9ac9688d2cb1a056a65a84bf9dcdd89b76694cb5c52653` / `55888e85bbce6a9bae7daef7754e7a799a9c74dad31b04da58d5e84a885c8c74` |
| Historical nested / invalid incidents | `b9f52bd8c7368f9604140d6021c30a72673992eee0e802bd8430f55b94122b4d` / `1ed5777d62d40d821c37b246cd4c99d4c166f96f77c9a4e13c79aa37b9ca2b43` |

All invalid fallback, aborted, nested, premature Batch-3, and invalid-review
artifacts remain quarantined provenance. They supply no acceptance evidence.

## Canonical North Star — byte-verbatim

The bytes between the markers, excluding the marker lines, are the complete
`.oracle/northstar.md`, including its original final newline.

<!-- NORTH_STAR_SHA256_BEGIN -->
# North Star — Arnold self-healing supervision

**End state:** An agent harness where no worker can be launched onto a spec that
isn't live, a box that won't survive it, or a seed bound to the wrong interpreter —
and where every worker death carries its killer's identity in a typed record that
the recovery loop consumes before it ever retries the same fingerprint.

**Enduring principles**
- One door per invariant: admission, dispatch, and death are each enforced at
  exactly one place; duplicate preflights are deleted, not patched around.
- Deaths speak: SIGKILL, timeout, terminate, restack — every termination emits
  `{killer, signal, elapsed_s}` into the failure ledger. Silent death is a bug.
- Models are admitted, not assumed: a model id must resolve against catalog,
  prefix map, family classifier, and live provider membership at dispatch time,
  typedly rejecting expired or unknown ids.
- Fixes ship on main through the fixer contract; hotfixes that live only as
  deployed-but-uncommitted files do not exist.

**Anti-patterns to avoid**
- Single-scan verdicts treated as sustained truth (wedge kills, restacks).
- Anonymous integer exit codes where a disposition belongs.
- Judgment-based "healthy" claims without positive proof (live pid + advancing seq).
- Redispatch of an identical failure fingerprint without a changed precondition.

**Aligned progress feels like:** fewer incident classes over time, each new stall
arriving with evidence attached and leaving with a root fix on main.
<!-- NORTH_STAR_SHA256_END -->

Extracted-block SHA-256 requirement:
`d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`.

## 1. `R3-NATIVE-001` — Native proof authenticity and recomputation

### Concrete evidence and frozen criterion

- Attempt-2 Sol gate probe `C01` supplied a current-seed native request whose
  request-local resolver returned stale `observed_at=1900`, arbitrary identity,
  capability registry, proof text, and 64-byte digest. Admission created one
  reservation and copied the arbitrary digest into the receipt.
- Current `WorkerAdmissionRequest` still transports
  `route_liveness_resolver`; `_impl.py::_production_worker_dispatch` copies it
  from `worker_options`; and `require_production_worker_dispatch_runtime`
  invokes it for native routes before `_validate_native_liveness`.
- `_validate_native_liveness` checks field presence and exact backend/provider/
  model/route strings, but does not recompute capability content, registry
  generation, observation freshness, proof identity, or digest. The current
  default only refuses; repository search finds no authoritative production
  native proof producer bound to the client-construction seam.
- Exact frozen NBF-02 criteria: “Production rejects before WBC/client/process/
  RPC construction when ... route liveness ... is absent or invalid”; “Native
  routes require positive proof from the actual native backend/runtime/model
  seam without being forced into OMP or adding speculative network checks”;
  and canonical admission jointly validates translation, catalog where
  applicable, family, positive route liveness, source/runtime, seed/interpreter,
  timeout, memory, fingerprint, and reservation.
- Exact frozen agent-goal criterion 5: **Joint model admission — and expired-ID
  proof**.

North Star principle: “Models are admitted, not assumed.” Anti-pattern:
judgment/nonempty caller assertions treated as positive live capability proof.

### Narrow outcome, owned paths, non-goals, order, and model

The selected native construction seam must produce the proof that admission
consumes. Admission must independently recompute and compare exact backend,
provider, normalized model, selected route, capability content, registry/runtime
generation, observation/freshness identity, and canonical digest before any
reservation, WBC attempt, client, process, or RPC construction. A request-local
resolver may be removed from production or retained only as a test attestor
whose output cannot replace authoritative recomputation. One proof from the
actual selected seam admits once; stale, forged, arbitrary, ambiguous, missing,
or mismatched proof refuses typedly with zero construction cardinality.

Owned paths only:

- `arnold_pipelines/megaplan/cloud/worker_dispatch.py`
- `arnold_pipelines/megaplan/workers/_impl.py`
- `tests/cloud/dispatch_test_helpers.py`
- `tests/cloud/test_worker_dispatch_admission.py`
- `tests/cloud/test_worker_dispatch_context.py`
- `tests/cloud/test_worker_dispatch_spy.py`

Non-goals: no speculative network probe; no OMP rewrite; no forcing native
routes through OMP; no T8/provider policy; no scheduler, journal, family lease,
or generic provider authority; no reopening `B2-RTB-001`, `B2-OMP-006`, or
static `ox-alpha` behavior. Dependency: frozen NBF-01 primitives and preserved
`B2-RTB-001`. Strict order: item 1 of 4.

Threshold analysis: `Normal`. Authenticity is decided by exact identity,
generation, digest, refusal-order, and cardinality assertions. `[XHARD]` would
require an unresolved product-policy or architecture choice not reducible to
the frozen oracle; none exists. Selected model: GPT-5.6 Luna. Sol execution is
forbidden.

### Deterministic acceptance oracle

- Add and retain these exact focused tests:
  `test_native_proof_recomputes_authoritative_content_generation_and_digest`,
  `test_native_proof_rejects_stale_or_forged_proof_before_reservation`,
  `test_native_proof_rejects_backend_provider_model_and_route_mismatch`, and
  `test_native_selected_construction_seam_admits_exactly_once`.
- The stale/forged matrix varies identity, backend, provider, normalized model,
  selected route, capability content, registry generation, observation,
  proof, and digest independently. Every negative row returns typed refusal and
  records zero reservations, WBC starts, clients, processes, and RPCs.
- Positive proof is generated at the actual native seam and its content,
  generation, and digest recompute byte-for-byte into the receipt.
- Exact OMP membership and static-catalog-accepts/live-rejects
  `openrouter/stealth/ox-alpha` remain green as preservation, not new scope.

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/cloud/test_worker_dispatch_admission.py::test_native_proof_recomputes_authoritative_content_generation_and_digest \
  tests/cloud/test_worker_dispatch_admission.py::test_native_proof_rejects_stale_or_forged_proof_before_reservation \
  tests/cloud/test_worker_dispatch_admission.py::test_native_proof_rejects_backend_provider_model_and_route_mismatch \
  tests/cloud/test_worker_dispatch_spy.py::test_native_selected_construction_seam_admits_exactly_once
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/cloud/test_worker_dispatch_admission.py \
  tests/cloud/test_runtime_attestation.py \
  tests/cloud/test_worker_dispatch_context.py \
  tests/cloud/test_worker_dispatch_spy.py \
  tests/workers/test_omp_adapter.py
```

## 2. `R3-TERM-002` — Production-door typed terminal transport

### Concrete evidence and frozen criterion

- Attempt-2 Sol probe `C01` showed a failure-shaped bare `WorkerResult`
  projecting as `DispatchOutcome(kind="success")`; a provider-exhaustion
  exception became identity-poor `unresolved_launch`; unknown integer `7`
  remained safely unresolved.
- Current `_impl.py` returns
  `LaunchResult(True, wbc_dispatch.run(...).worker_result)` and OMP returns the
  recursive `wbc_dispatch.run(...).worker_result`. Neither physical closure
  constructs the explicit operation-specific `DispatchOutcome` envelope used
  by the green generic transport tests.
- Current `_normalize_outcome` maps bare `WorkerResult` and its four-tuple
  wrapper unconditionally to success. The outer `except Exception` collapses
  provider exhaustion and other post-admission exceptions to an unresolved
  result that omits receipt, fingerprint, worker, timing, and failure context.
- Exact frozen NBF-02 criteria: “Accepted success, ordinary failure, provider
  exhaustion, and worker disposition each record one canonical terminal event
  before consumer projection”; disposition retains its ID, receipt,
  fingerprint, phase/spec, worker, timing, and accepted context end to end;
  append/link failure retains an unresolved reservation.
- Exact frozen NBF-03 criterion: accepted worker-disposition traces preserve
  the disposition ID and show one terminal projection after record-before-signal.
- Exact frozen agent-goal criterion 3: **Typed death dispositions — every real
  signal branch**, limited here to lossless Batch-2 transport of already-typed
  results through the real production doors.

North Star principle: “Deaths speak.” Anti-pattern: anonymous or failure-shaped
legacy values projected as success, or typed identity collapsed at a door.

### Narrow outcome, owned paths, non-goals, order, and model

Each physical native, OMP, and managed-command operation door must map its
actual operation result into an operation-specific typed success, ordinary
failure, provider exhaustion, or worker disposition before returning to the
shared dispatch seam. The canonical terminal writer commits exactly once before
consumer projection. Every kind preserves receipt, fingerprint, phase/spec,
logical/door/worker identity, timing, accepted-launch context, and applicable
failure/disposition context. Append or disposition-link failure returns a
context-rich unresolved outcome and holds the reservation. Unknown legacy
integers, strings, tuples, objects, malformed mappings, and unclassified bare
failure-shaped `WorkerResult` values remain rejected/unresolved, never success.

Owned paths only:

- `arnold_pipelines/megaplan/cloud/worker_dispatch.py`
- `arnold_pipelines/megaplan/cloud/controlled_final_launch.py`
- `arnold_pipelines/megaplan/cloud/babysitter/launch.py`
- `arnold_pipelines/megaplan/workers/_impl.py`
- `arnold_pipelines/megaplan/workers/omp.py`
- `tests/cloud/test_controlled_final_launch.py`
- `tests/cloud/test_dispatch_with_admission.py`
- `tests/cloud/test_worker_dispatch_spy.py`
- `tests/arnold_pipelines/megaplan/test_terminal_outcomes.py`
- `tests/arnold_pipelines/megaplan/test_worker_disposition.py`
- `tests/arnold_pipelines/megaplan/test_common_worker_dispatch_wbc.py`

Non-goals: no generic schema or incident-ledger rewrite; no signal-site work;
no six-kind × every-door generalization; no T8/provider degradation policy; no
loosening of unknown legacy rejection; no reopening passed OMP ownership,
child authorization, scheduling, or breaker semantics. Dependencies:
`R3-NATIVE-001` and existing NBF-01 terminal/disposition primitives. Strict
order: item 2 of 4.

Threshold analysis: `Normal`. The four allowed operation terminal categories,
field preservation, append cardinality, and ordering are frozen and mechanically
testable. `[XHARD]` would require choosing new terminal semantics or adjudicating
irreducibly ambiguous operation state; this item instead preserves unresolved
for ambiguity. Selected model: GPT-5.6 Luna. Sol execution is forbidden.

### Deterministic acceptance oracle

- Add and retain exact tests
  `test_native_physical_door_transports_typed_terminal_categories`,
  `test_omp_physical_door_transports_typed_terminal_categories`,
  `test_managed_door_transports_typed_terminal_categories`,
  `test_failure_shaped_worker_result_never_projects_as_success`, and
  `test_terminal_append_or_link_failure_holds_full_context_unresolved`.
- For each real door, parameterize exactly success, ordinary failure, provider
  exhaustion, and worker disposition; assert one accepted marker, one terminal
  append, record-before-projection, and complete identity/context equality.
- Assert disposition is recorded before projection, is not appended twice,
  does not become ordinary failure/provider degradation, and preserves breaker
  semantics.
- Assert provider exhaustion is typed, not exception-collapsed; other ambiguous
  exceptions remain unresolved without invented success.

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/cloud/test_worker_dispatch_spy.py::test_native_physical_door_transports_typed_terminal_categories \
  tests/cloud/test_worker_dispatch_spy.py::test_omp_physical_door_transports_typed_terminal_categories \
  tests/cloud/test_worker_dispatch_spy.py::test_managed_door_transports_typed_terminal_categories \
  tests/cloud/test_dispatch_with_admission.py::test_failure_shaped_worker_result_never_projects_as_success \
  tests/cloud/test_dispatch_with_admission.py::test_terminal_append_or_link_failure_holds_full_context_unresolved
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/cloud/test_dispatch_with_admission.py \
  tests/cloud/test_controlled_final_launch.py \
  tests/cloud/test_worker_dispatch_spy.py \
  tests/arnold_pipelines/megaplan/test_terminal_outcomes.py \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_common_worker_dispatch_wbc.py
```

## 3. `R3-LIFE-003` — Stale-marker lifecycle reconciliation

### Concrete evidence and frozen criterion

- Attempt-2 Sol probe `C10` persisted `not_started → entered → accepted`, then
  passed only the earlier `not_started` event ID to `reconcile_no_launch`. The
  helper returned `no_launch` and the ledger committed `released_no_launch`
  while the accepted marker remained persisted.
- Current `reconcile_no_launch` reads the whole ledger but filters to the
  caller-selected IDs before checking contradiction. Current
  `IncidentLedger.reconcile_reservation` repeats the same selected-evidence
  pattern under lock, so neither authority rejects a later receipt-bound
  entered/accepted/terminal/disposition contradiction globally.
- Current `dispatch_with_admission` trusts a callable `launch.pre_entry` and
  lets its caller-selected evidence IDs cite the adapter's own `not_started`
  marker. Attempt-2 Sol `C01b` showed this releases a reservation without a
  persisted physical-door operation proof; no production door defines that
  hook.
- Exact frozen NBF-02 criteria: positive no-entry/no-acceptance evidence
  reconciles before `no_launch`; missing, contradictory, post-entry, or
  post-acceptance evidence stays unresolved; sequencing covers pre-entry,
  pre-acceptance, accepted, ambiguous, append-failure, restart, and identical
  retry after truthful no-launch; only canonical evidence-bound change may
  authorize redispatch.
- Exact frozen agent-goal criterion 4: **Fingerprint redispatch block —
  pre-launch**.

North Star principle: “One door per invariant.” Anti-pattern: redispatch of an
identical fingerprint after selective or caller-manufactured no-launch proof.

### Narrow outcome, owned paths, non-goals, order, and model

The canonical ledger transaction must inspect all persisted evidence bound to
the reservation, receipt, logical dispatch, and physical door while holding the
append lock. `released_no_launch` is legal only from receipt-bound positive
physical-operation evidence proving no entry and no acceptance, with no global
entered, accepted, terminal, disposition, or conflicting reconciliation
marker. The release commits before `no_launch` projection. Caller-attached
function attributes and adapter markers alone are insufficient. Missing,
selective, stale, contradictory, post-entry, post-acceptance, append-failed, or
restart-ambiguous evidence holds unresolved; identical retry cannot blindly
launch. Encode and test the explicit state matrix:

| Persisted operation state | Release result |
|---|---|
| bound operation `not_started` + positive no-entry/no-acceptance, no contradiction | commit one `released_no_launch`, then project `no_launch` |
| adapter `not_started` only | unresolved hold |
| `entered` without terminal | unresolved hold |
| `accepted` without terminal | unresolved hold |
| terminal/disposition exists | terminal recovery or existing closure, never no-launch |
| missing/selective/stale/foreign evidence | unresolved hold |
| reconciliation append failure | unresolved hold |
| replay of identical valid release | idempotent same release; no launch |

Owned paths only:

- `arnold_pipelines/megaplan/cloud/worker_dispatch.py`
- `arnold_pipelines/megaplan/cloud/controlled_final_launch.py`
- `arnold_pipelines/megaplan/incident/ledger.py`
- `tests/cloud/test_controlled_final_launch.py`
- `tests/cloud/test_dispatch_reconciliation.py`
- `tests/cloud/test_dispatch_with_admission.py`
- `tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py`

Non-goals: no PID-absence, exception-text, elapsed-time, or single-scan
inference; no second reconciliation authority or journal; no terminal schema
rewrite; no change to safe unresolved behavior; no scheduler/provider policy;
no identical blind relaunch. Dependency: `R3-TERM-002` finalizes terminal and
accepted-state shapes. Strict order: item 3 of 4.

Threshold analysis: `Normal`. The legal state matrix, global contradiction
predicate, transaction boundary, idempotency, and zero/one launch cardinality
are deterministic. `[XHARD]` would require guessing whether an ambiguous
operation launched; the frozen rule forbids guessing and mandates unresolved.
Selected model: GPT-5.6 Luna. Sol execution is forbidden.

### Deterministic acceptance oracle

- Add and retain exact tests
  `test_reconcile_no_launch_rejects_selective_not_started_when_accepted_exists`,
  `test_pre_entry_release_requires_receipt_bound_physical_operation_evidence`,
  `test_reconciliation_explicit_persisted_state_matrix`,
  `test_no_launch_commits_before_projection_and_replays_idempotently`, and
  `test_identical_retry_never_relaunches_unresolved_or_accepted_state`.
- The selective-evidence test must reproduce the exact
  `not_started → entered → accepted` history, supply only the first ID, and
  assert no `released_no_launch` append and an unresolved/closed-safe result.
- The physical-operation test must prove adapter-only and foreign-door evidence
  cannot release, while fully bound operation evidence can release once.
- The state-matrix test must restart from a fresh ledger for every row and
  assert reservation, terminal, fingerprint, breaker, and launch cardinalities.

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/cloud/test_dispatch_reconciliation.py::test_reconcile_no_launch_rejects_selective_not_started_when_accepted_exists \
  tests/cloud/test_dispatch_with_admission.py::test_pre_entry_release_requires_receipt_bound_physical_operation_evidence \
  tests/cloud/test_dispatch_reconciliation.py::test_reconciliation_explicit_persisted_state_matrix \
  tests/cloud/test_dispatch_reconciliation.py::test_no_launch_commits_before_projection_and_replays_idempotently \
  tests/cloud/test_dispatch_with_admission.py::test_identical_retry_never_relaunches_unresolved_or_accepted_state
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/cloud/test_controlled_final_launch.py \
  tests/cloud/test_dispatch_reconciliation.py \
  tests/cloud/test_dispatch_with_admission.py \
  tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py
```

## 4. `R3-AUTH-004` — Checker adversarial category completeness

### Concrete evidence and frozen criterion

- Attempt-2 Sol fixture `C03` supplied qualified `getattr` call aliases,
  reversed multiline absent-WBC delegation, aliased process/raw launch, and
  aliased double admission. The checker emitted only one
  `raw_final_launch_access` diagnostic and missed the other required categories.
- Current `_aliases` resolves only import and assignment values that are
  `Name`/`Attribute`; `_qualified_name` returns empty for call aliases such as
  `getattr(module, "symbol")`.
- Current process detection depends on a resolved short name and door-like
  enclosing symbol. Current absent-WBC detection recognizes only a direct
  `wbc_dispatch is/== None` comparison and an unaliased `final_launch` name;
  it misses reversed comparisons and aliased/multiline delegation. Admission
  counting inherits the same incomplete call resolution.
- Exact frozen NBF-03 criterion: the checker detects raw authority calls,
  resolvable aliases, chain-local preflight, direct chain spawn, no-WBC legacy
  delegation, WBC-before-admission, nested double admission, and raw launch
  access; diagnostics must pass across all doors and chain origins.
- Exact frozen agent-goal criteria 2 and 6: **Wire all three launch doors —
  exactly once each** and **Structural spy test — three doors,
  gate-before-spawn**.

North Star principle: “One door per invariant.” Anti-pattern: a green narrow
static scan treated as proof despite deterministic alias/category evasions.

### Narrow outcome, owned paths, non-goals, order, and model

Complete deterministic AST/text resolution for qualified, imported, module,
assignment, and call aliases, including literal-string `getattr` where the
target is statically knowable. Normalize both orientations and multiline forms
of absent-WBC tests. Every frozen category must have one isolated negative
fixture and emit a contextual diagnostic with path, line, enclosing symbol,
category/code, and reason. The repository-positive check remains zero
diagnostics only after all category fixtures pass. Retain an independent empty
raw-symbol scan over the three physical doors.

Owned paths only:

- `scripts/check_worker_admission_authority.py`
- `tests/cloud/test_worker_admission_authority.py`

Non-goals: the checker is not runtime authority; no general linter framework;
no broad production rewrite unless the completed checker reports a repository
violation; no replacement of structural spies or the independent raw-symbol
scan. Dependency: final door shapes after `R3-NATIVE-001`, `R3-TERM-002`, and
`R3-LIFE-003`. Strict order: item 4 of 4.

Threshold analysis: `Normal`. The finite frozen category list, alias forms,
diagnostic fields, deterministic ordering, and positive/negative fixtures are
mechanically decidable. `[XHARD]` would require open-ended whole-program alias
analysis or general lint design; both are expressly excluded. Selected model:
GPT-5.6 Luna. Sol execution is forbidden.

### Deterministic acceptance oracle

- Add one isolated parameterized negative fixture per exact frozen category:
  `raw_authority_call`, `chain_local_preflight`, `direct_chain_launch`,
  `absent_wbc_legacy_delegation`, `wbc_before_admission`,
  `nested_double_admission`, and `raw_final_launch_access`; preserve process,
  client, RPC, and WBC construction subcategory coverage used to enforce raw
  launch access.
- Add exact adversarial tests
  `test_checker_detects_qualified_getattr_call_alias`,
  `test_checker_detects_reversed_multiline_absent_wbc_delegation`,
  `test_checker_detects_aliased_process_and_raw_launch`, and
  `test_checker_detects_aliased_double_admission`.
- Assert deterministic diagnostics are stable under fixture ordering and every
  diagnostic contains path, line, enclosing symbol, category/code, and reason.

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/cloud/test_worker_admission_authority.py::test_checker_emits_each_frozen_category_with_context \
  tests/cloud/test_worker_admission_authority.py::test_checker_detects_qualified_getattr_call_alias \
  tests/cloud/test_worker_admission_authority.py::test_checker_detects_reversed_multiline_absent_wbc_delegation \
  tests/cloud/test_worker_admission_authority.py::test_checker_detects_aliased_process_and_raw_launch \
  tests/cloud/test_worker_admission_authority.py::test_checker_detects_aliased_double_admission
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/cloud/test_worker_admission_authority.py
PYTHONDONTWRITEBYTECODE=1 python -B scripts/check_worker_admission_authority.py --check
```

## Preserved passes and rejected dispositions

- `B2-RTB-001` — preserve as PASS. Attempt-2 Sol replaced source revision,
  runtime vector, manifest, seed, and interpreter callback fields one at a time;
  each returned typed `runtime_binding_mismatch` with zero reservations.
- `B2-CHILD-005` — preserve as PASS. Composite route transition and child
  reservation remain one locked append with canonical terminal parent,
  authorization, context, single-use, and post-commit derived receipt.
- `B2-OMP-006` — preserve as PASS. Production absent-WBC OMP typedly refuses
  before raw launch; direct/nested OMP retains exactly one admission owner;
  production exact OMP membership remains canonical.
- `B2-SCHED-008` — preserve as PASS. `dispatch_with_admission` remains the sole
  injected scheduling loop and preservation tests remain green.
- The four baseline failures
  `test_babysitter_routing_defaults_to_legacy_deepseek`,
  `test_legacy_managed_spec_keeps_hermes_controller`,
  `test_renderer_requires_single_flash_orchestrator_contract`, and
  `test_renderer_cli_mentions_single_flash_contract` are rejected as rework.
  Attempt-2 recorded 47 passes plus exactly these failures; the three existing
  routing/goal paths retain hashes
  `285af9a1ac4f2db640d4ca781f426e4c52f2af47203a5deff0f0db805a62f9eb`,
  `ba75ceca1f1316864aef83d6f92a81fae2cd4e88c2da0168dac1391d817eb7fa`,
  and `4e85a83fa889640abaea70046d73498a2ed407bccffc3434750c764df2c87153`;
  the renderer path is absent from both candidate parent and HEAD.
- Broad six-kind × every-door generalizations are rejected. `R3-TERM-002`
  requires only operation-specific success, ordinary failure, provider
  exhaustion, and worker disposition through the real physical doors.
- The aggregate digest-construction issue is rejected as a nonissue. The
  historical construction independently reproduces 392,090 bytes and
  `5586c1861dce44334c3991e997bdc8b90b82d25d2ed8f28bb558b42aae499fd0`.
- T8 thresholds/probes/degradation/fallback/return/races, provider policy,
  scheduler changes, a second journal, family-wide lease, signal-site work,
  and general schema expansion remain excluded.

After the four serial items, run the preserved-pass commands exactly:

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/cloud/test_runtime_attestation.py tests/cloud/test_worker_dispatch_admission.py tests/cloud/test_worker_dispatch_context.py
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/cloud/test_chain_admission.py tests/cloud/test_dispatch_with_admission.py tests/arnold_pipelines/megaplan/test_provider_route_projection.py tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/cloud/test_worker_dispatch_spy.py tests/cloud/test_chain_admission.py tests/cloud/test_dispatch_with_admission.py tests/arnold_pipelines/megaplan/test_common_worker_dispatch_wbc.py tests/workers/test_omp_adapter.py
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/cloud/test_dispatch_with_admission.py tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_phase_result_classify.py tests/arnold_pipelines/megaplan/test_plan_circuit.py
```

## Frozen Batch-2 validation contract for the later executor

Implementation must be one GPT-5.6 Luna writer, strictly serial in the four-item
order above. Complete and externally capture each item's focused probes and
full focused module command before starting the next item. No parallel writer,
review launch, fallback, fanout, nested model launch, or Batch-3 work is
authorized by this packet.

Run the full frozen NBF-02 gate exactly:

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/cloud/test_runtime_attestation.py \
  tests/cloud/test_worker_dispatch_admission.py \
  tests/cloud/test_dispatch_with_admission.py \
  tests/cloud/test_chain_admission.py \
  tests/cloud/test_worker_dispatch_context.py \
  tests/cloud/test_dispatch_reconciliation.py \
  tests/cloud/test_controlled_final_launch.py \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py \
  tests/arnold_pipelines/megaplan/test_terminal_outcomes.py \
  tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py \
  tests/arnold_pipelines/megaplan/test_memory_headroom.py \
  tests/arnold_pipelines/megaplan/test_worker_memory_gate.py \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_phase_result_classify.py \
  tests/arnold_pipelines/megaplan/test_plan_circuit.py \
  tests/workers/test_omp_adapter.py
```

Run the full frozen NBF-03 gate exactly:

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/cloud/test_worker_dispatch_spy.py \
  tests/cloud/test_worker_admission_authority.py \
  tests/cloud/test_chain_admission.py \
  tests/cloud/test_babysitter_routing.py \
  tests/cloud/test_babysitter_goal.py \
  tests/arnold_pipelines/megaplan/test_common_worker_dispatch_wbc.py
```

Only the same four named babysitter baseline failures may be nonzero, and only
if the following baseline proof remains exact:

```bash
git diff --quiet 19deab5bb407273e7e82d40a66fc06d17af93ad4 -- \
  arnold_pipelines/megaplan/cloud/babysitter/routing.py \
  skills/babysitter/scripts/render_babysitter_goal.py \
  tests/cloud/test_babysitter_routing.py \
  tests/cloud/test_babysitter_goal.py
shasum -a 256 \
  arnold_pipelines/megaplan/cloud/babysitter/routing.py \
  tests/cloud/test_babysitter_routing.py \
  tests/cloud/test_babysitter_goal.py
test -z "$(git ls-tree -r --name-only 19deab5bb407273e7e82d40a66fc06d17af93ad4 -- skills/babysitter/scripts/render_babysitter_goal.py)"
test -z "$(git ls-tree -r --name-only HEAD -- skills/babysitter/scripts/render_babysitter_goal.py)"
```

Run checker, independent raw-symbol scan, compile, and diff check exactly in
this order:

```bash
PYTHONDONTWRITEBYTECODE=1 python -B scripts/check_worker_admission_authority.py --check
if rg -n \
  'refresh_runtime_launch_seed_for_worker_dispatch|require_configured_runtime_launch' \
  arnold_pipelines/megaplan/workers/_impl.py \
  arnold_pipelines/megaplan/workers/omp.py \
  arnold_pipelines/megaplan/cloud/babysitter/launch.py
then
  exit 1
fi
PYTHONDONTWRITEBYTECODE=1 python -m compileall -q arnold_pipelines scripts tests
git diff --check
```

The later executor must also prove:

```bash
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git rev-parse origin/main
git show -s --format='%H%n%P%n%T' 5da26ec5be4d13559948fe4256a114ad7626482b
git diff --binary --full-index 5da26ec5be4d13559948fe4256a114ad7626482b -- arnold_pipelines scripts tests | shasum -a 256
git diff --name-status 5da26ec5be4d13559948fe4256a114ad7626482b -- arnold_pipelines scripts tests
git ls-files --others --exclude-standard -- arnold_pipelines scripts tests
```

For every command, use a fresh evidence root outside the repository and capture
literal argv, working directory, UTC start/end, exit status, separate stdout and
stderr byte counts and SHA-256, and pre/post
`git status --porcelain=v1 -uall`. Capture per-item and final changed-path lists,
source/test diff bytes/SHA, owned-path hashes, candidate/source/base/frozen
bindings, and proof that no untracked production/test path escaped inventory.
A zero exit is insufficient: the finding/receipt must state the typed refusal,
identity equality, construction cardinality, terminal category/order,
reconciliation state-matrix result, or checker category/context observed.
Intermediate failures remain in the command ledger; corrected reruns do not
erase them. No transcript may be written into frozen or prior artifacts.

## Delegation mandate for later separately authorized execution

DELEGATION MANDATE — You are a manager and validator of the normal execution pool, NOT a worker. Delegate as much as possible to the task's selected normal model: DeepSeek V4 Flash or GPT-5.6 Luna. Flash invocation: `omp -p @<brief>.md --model deepseek-v4-flash --cwd <worktree> --no-session --auto-approve --max-time=1800`; Luna invocation: `launch_hermes_agent.py --model="codex:gpt-5.6-luna" --query-file=<brief> --project-dir=<worktree>` (research-only briefs use read/search tools). Dispatch research, execution, and critique briefs to the selected model — critique passes optimize for elegance: KISS, YAGNI, cut scope that isn't pulling its weight; flag overengineering, not just bugs. Your job is to direct, then validate: read delegated output against the acceptance criteria; do work yourself only when delegation is impossible — the selected normal model already failed at it, or the piece is too small / too tightly coupled to your own reasoning to hand off. If you catch yourself implementing or researching directly, stop and ask whether a normal-pool brief would cover it. It almost always would.

This mandate applies only after separate execution authorization. It did not
authorize a model launch during this triage, and no model was launched.

## Final packet boundary

This packet performs none of the four accepted items and issues no Oracle gate
token or verdict. It changes no source, test, frozen input, custody, agent goal,
status file, history, prior artifact, or Batch-3 material. It authorizes no
implementation, review, verdict, commit, stage, push, merge, reset, clean,
history rewrite, or Batch 3. Only this packet and its paired attempt-3 triage
receipt are authorized outputs of this leaf.
