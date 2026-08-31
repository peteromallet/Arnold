# Batch-2 rework attempt-4 — bounded Luna execution packet

## Packet boundary and provenance

This is an append-only implementation packet derived from the authoritative
GPT-5.6 Sol/high Oracle adjudication for Batch-2 attempt-3. The adjudication
returned `ACCEPTED_ISSUES`; it is bound below by the complete check-in and
receipt hashes. This packet is executor guidance, not an Oracle verdict.

The executor is one Normal GPT-5.6 Luna writer operating directly in the
existing candidate tree. Work is strictly serial in the order below. Use
`apply_patch` for all source and test edits. Do not edit the frozen tasklist,
North Star, plan, goal, custody, status, history, or prior artifacts. Do not
commit, stage, push, merge, start Batch 3, invoke a nested model/delegation
harness, or issue a verdict. Preserve valid existing work and the four passed
roots. Do not widen this packet into T8/provider policy, scheduler, signal-site,
family-lease, or generic six-kind/every-door scope.

## Immutable bindings

| Binding | SHA / identity |
|---|---|
| Repository / branch | `/Users/peteromalley/Documents/Arnold-oracle-nbf` / `megado-nbf-guard-0826` |
| Current HEAD | `2297fb330cdb375b4e5bd048f0d5c37d0e06db30` |
| Immutable source/base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` |
| Candidate implementation commit | `5da26ec5be4d13559948fe4256a114ad7626482b` |
| Candidate parent / tree | `19deab5bb407273e7e82d40a66fc06d17af93ad4` / `e3d0376482154c4f95d2ec5809d630c4a0c32e69` |
| Candidate canonical diff | `5586c1861dce44334c3991e997bdc8b90b82d25d2ed8f28bb558b42aae499fd0` |
| Current source/test diff | `acb8ca400c1b0874cea1f030630ba2f186f16cd22ceedfc2a33fe7ab592a19ec` |
| Frozen tasklist `.oracle/tasklist.md` | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| Frozen North Star `.oracle/northstar.md` | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| Frozen plan `.oracle/plan.md` | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| Frozen agent goal `.oracle/agent_goal.md` | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` |
| Frozen custody `.oracle/custody.md` | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| Attempt-3 packet | `.oracle/rework/batch-2-attempt-3.md` — `ff19d01688124ef3b77dba28ab24c28da71b395838c645a3a34f7b580c24c1e2` |
| Attempt-3 triage brief / receipt | `.oracle/briefs/rework-triage-batch-2-attempt-3-sol.md` — `bf23bd246b3ac1a60e16af74415274032641359a2677df5f5c19c763ce523cfc`; `.oracle/receipts/rework-triage-batch-2-attempt-3-sol.md` — `5d08b2b2f31a8a85f602c449311bd05a775711f298db963a8bc611f81abfab38` |
| Authoritative Sol check-in | `.oracle/checkins/batch-2-attempt-3-sol.md` — `f48bffe73211a01ec8a95acb1a1cde99fc9ce6276165d64fac32b302609a27ad` |
| Authoritative Sol receipt | `.oracle/receipts/oracle-batch-2-attempt-3-sol.md` — `4dad76f10aaf0a3407ecaff7948ec09d1f07457bf2d04afb683a076cef719759` |
| Clean sealed manifest | `.oracle/evidence/batch-2-attempt-3-sealed.md` — `2c60512f34311883849d1530af4c5b719cab7bb29434087985905c36b2573cbf` |
| Attempt-3 v3 finding / receipt | `.oracle/findings/execution-batch-2-attempt-3-v3-luna.md` — `c216fc39fcdec21cf81f8a3bb43656b7dca5ef949a050a85ac1a81b0523569ee`; `.oracle/receipts/execution-batch-2-attempt-3-v3-luna.md` — `cca7987c9f23eab5ec6c2a4cf80ceb1af84fd1d5e2503bc20421ef2685cb0bcf` |
| Review-policy override | `.oracle/receipts/review-policy-override-multi-luna-single-sol.md` — `1e22ec54c1c1afb33e3d1faf81d2e49b8b540f6f62dbd7e0b264249716c4bccc` |
| Prior Luna review pairs | evidence `f4bc8d6d9f4c5eb3e3986d96e895d14e91d350cbb08c4e9fc58b9fa8fe097ed6` / `f920f6aaf739e27734fb099702d3f7d84bf511199b9f2fc54e46eeec08238f3f`; runtime `a3eb381fff36416cb3fec6f71b9fdca8ff10f4577db6d14d8bb115e57f4eaebe` / `cc5d499e45bcb1af3e354353907d3ad30308891ff732bc2767bf1c2b2aa257bb`; authority `5d3a2b2392d36980f73e68092ab5700665012fac19791c51df3ea1b9d01712df` / `7aa91b304533a0879502120252629442b8e43bfb8c3e914b0f155fce58318cba` |

The Sol check-in and receipt above are the authoritative source for all four
accepted roots and their evidence. The abbreviated historical review hashes
are labels only; the executor must rehash every file it consumes and record
full values in its finding and receipt. No invalid nested, fallback, aborted,
premature-Batch-3, or stale-marker artifact is acceptance evidence.

## North Star — canonical byte-for-byte block

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

The bytes between the North Star markers, including the final newline, must
hash exactly to `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`.

## Preserved dispositions and explicit exclusions

Keep the already-passed `B2-RTB-001` canonical admission/retry-boundary,
`B2-CHILD-005` child authorization, `B2-OMP-006` no-WBC OMP delegation, and
`B2-SCHED-008` scheduler/wait ownership findings unless new direct evidence
proves a regression. The four babysitter failures are unchanged baseline
failures and are not rework. Do not generalize this packet into six payload
kinds through every door, Batch-3 crash semantics, a digest-construction change,
T8 provider policy, a second scheduler, a second journal, signal-site wiring,
or a family-wide launch lease.

## Strict serial work order

All four items are `Normal`, selected model `GPT-5.6 Luna`, one writer only, and
must remain below the exceptional `[XHARD]` threshold. The next review gate is
the recorded user policy: default to three fresh independent Luna/high passes
for this new segment, expanding only for concrete disagreement or inconclusive
evidence; then at most one Sol/high Oracle judgment. Executor evidence never
counts as a review. No Sol/XHARD classification is justified by the current
source-based findings.

### 1. R3-NATIVE-001 — authoritative native proof

**Evidence and affected contract.** The Sol check-in cites
`worker_dispatch.py:524-589`, `:643-682`, and `workers/_impl.py:7347-7390`:
`_validate_native_liveness` accepts only a literal false check, resolver-only
proof can bypass a construction seam, and `_native_construction_proof` treats a
callable as constructable. Direct evidence accepted an unknown model and a
self-consistent negative/stale proof. This fails frozen goal criterion 1/5,
Batch-2 canonical admission, and the North Star principle “Models are admitted,
not assumed.”

**Required outcome and owned scope.** Native admission must obtain a positive
proof from the selected backend/runtime/model construction seam. Recompute and
bind exact content, generation, model identity, registry/family, route/provider,
observation age, and digest; require `proof.constructable is True`. Unknown or
expired model, stale observation, missing/ambiguous seam, negative or forged
proof, and any mismatch must refuse typedly before reservation, WBC, client,
process, RPC, or launch construction. A valid proof admits exactly once.
Reuse the existing admission and native seam in `cloud/worker_dispatch.py`,
`workers/_impl.py`, native model/runtime seam, and their focused tests. Do not
add speculative network probes, rewrite native through OMP, or implement T8.

**Dependency and exact acceptance.** First item; later terminal transport must
consume its authoritative receipt. Add or strengthen tests proving authoritative
recomputation, unknown/stale/forged rejection, route mismatch rejection, zero
construction before refusal, and exactly-once valid construction. Preserve all
existing admission/retry-boundary passes.

### 2. R3-TERM-002 — physical-door typed terminal transport

**Evidence and affected contract.** The Sol check-in cites
`worker_dispatch.py:754-766`, `:293-341`, `:1043-1046`, `workers/_impl.py:7466-7492,
:6972-7013`, `workers/omp.py:1237-1269`, `handlers/shared.py:1059-1069`,
`handlers/execute.py:1196-1240`, and `test_worker_dispatch_spy.py:94-125`.
Identity fields are overwritten, bare failure-shaped values can project as
success, typed exceptions collapse to identity-poor unresolved state, physical
doors return raw values, and the alleged physical matrix uses a generic lambda.
This fails frozen criteria 5/7 and “Deaths speak” / “one door per invariant.”

**Required outcome and owned scope.** After item 1, native, OMP, and managed
physical doors must construct and transport operation-specific typed success,
ordinary failure, provider exhaustion, and worker disposition outcomes. Compare
all admission, dispatch, worker, timing, receipt, fingerprint, phase, spec,
route, and worker identities; mismatch rejects and never overwrites. Record one
canonical terminal event before consumer projection. Typed death exceptions must
terminalize with complete context; append/link failure returns context-complete
unresolved and holds the reservation; `PhaseResult.dispatch_outcome` reaches
its consumer. The canonical disposition is not appended twice, never coerced to
ordinary failure/provider exhaustion, and never enters provider degradation.
Own only `workers/_impl.py::run_step_with_worker` and its native closure,
`workers/omp.py::run_omp_step` / `_run_omp_with_admission`, the managed
`cloud/babysitter/launch.py::_admit_managed_launch` door, the shared
`cloud/worker_dispatch.py::_normalize_outcome`/`dispatch_with_admission` path,
`handlers/shared.py` and `handlers/execute.py` phase transport, and the real-door
spy fixtures. Keep unknown legacy values rejected; do not reopen generic schema
or signal-site scope.

**Dependency and exact acceptance.** Depends on R3-NATIVE-001. Add real native,
OMP, and managed-door tests for all four typed categories, forged identity
rejection, failure-shaped-result non-success, typed death, append/link failure,
single terminal/disposition append, and end-to-end phase transport. Preserve
RTB/CHILD/OMP/SCHED passes.

### 3. R3-LIFE-003 — global persisted transition reconciliation

**Evidence and affected contract.** The Sol check-in cites
`incident/ledger.py:657-683`, `incident/schema.py:1186-1202`, and
`controlled_final_launch.py:42-64`. The append door binds receipts but not the
persisted predecessor, and reopen selects a strongest marker without validating
history. Direct evidence reopened contradictory
`not_started → entered → accepted → not_started` as accepted, and selective
earlier-ID reconciliation released a reservation while an accepted marker
remained. This fails frozen criteria 3/7 and the North Star anti-pattern against
unsubstantiated launch/death state.

**Required outcome and owned scope.** The canonical locked ledger door must
enforce legal `not_started → entered → accepted → closed` transitions and
idempotent replay globally, not per selected marker. Reject closed-first,
accepted-before-entered, entered-after-accepted, stale not-started,
conflicting-duplicate, and mixed-door histories. Reopen must validate the
complete persisted history and receipt-bound physical evidence rather than pick
the strongest marker. Preserve commit-before-projection, no-launch, replay,
at-most-once, and reservation semantics. Own only predecessor validation,
reconciliation, reopen, and their tests; do not add a journal or scheduler.

**Dependency and exact acceptance.** Depends on R3-TERM-002. Add explicit
persisted-state matrix tests, selective-earlier-ID rejection, physical evidence
requirements, no-launch commit-before-projection replay, and identical retry
non-relaunch. Preserve valid recovered-terminal and durable-ambiguous-hold
behavior.

### 4. R3-AUTH-004 — physical WBC closure and contextual checker

**Evidence and affected contract.** The Sol check-in cites
`scripts/check_worker_admission_authority.py:183-194,256-299`,
`workers/_impl.py:6972-7013,7882-7902`, and `workers/omp.py:1237-1252`.
Checker coverage depends on function-name regexes, misses qualified/call aliases,
reversed or multiline absent-WBC forms, process construction and raw launch
aliases, and nested/double admission. Flag-on OMP loses WBC context. Direct
probes found no diagnostic for `subprocess.Popen` in `execute()` and only a raw
final-launch category for `if not wbc_dispatch`. This fails frozen criterion 4
and “one door per invariant.”

**Required outcome and owned scope.** The flag-on OMP path forwards the canonical
WBC adapter. `wbc_dispatch=None` constructs it or refuses before controlled
entry/reservation and never reaches raw launch. The checker must scan every call
in configured door files regardless of enclosing-symbol spelling and
deterministically classify qualified/import/module/assignment/call aliases,
truthy/reversed/multiline absent-WBC forms, aliased process/raw launch,
nested/double admission, WBC ordering, and chain preflight/launch with contextual
diagnostics. Add one negative fixture per frozen category and an independent raw
symbol scan. Do not turn the checker into runtime authority or a general linter.

**Dependency and exact acceptance.** Depends on R3-LIFE-003. Full authority
fixtures must complete, not time out; focused checker tests must cover each
category and alias, and the raw-symbol scan must be empty. Preserve CHILD, OMP,
and SCHED behavior.

## Required validation and evidence

The executor must capture each command with literal argv, UTC start/end,
separate stdout/stderr byte counts and SHA-256, exit code, pre/post porcelain,
and changed-path hashes under a fresh evidence directory. Run the four focused
groups below strictly in order, then the exact frozen NBF-02/NBF-03 suites and
preservation commands from the frozen contract. Record failures honestly and
classify unchanged babysitter baseline failures with parent/clean reproduction.

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/cloud/test_worker_dispatch_admission.py::test_native_proof_recomputes_authoritative_content_generation_and_digest \
  tests/cloud/test_worker_dispatch_admission.py::test_native_proof_rejects_stale_or_forged_proof_before_reservation \
  tests/cloud/test_worker_dispatch_admission.py::test_native_proof_rejects_backend_provider_model_and_route_mismatch \
  tests/cloud/test_worker_dispatch_spy.py::test_native_selected_construction_seam_admits_exactly_once
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/cloud/test_worker_dispatch_spy.py::test_native_physical_door_transports_typed_terminal_categories \
  tests/cloud/test_worker_dispatch_spy.py::test_omp_physical_door_transports_typed_terminal_categories \
  tests/cloud/test_worker_dispatch_spy.py::test_managed_door_transports_typed_terminal_categories \
  tests/cloud/test_dispatch_with_admission.py::test_failure_shaped_worker_result_never_projects_as_success \
  tests/cloud/test_dispatch_with_admission.py::test_terminal_append_or_link_failure_holds_full_context_unresolved
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/cloud/test_dispatch_reconciliation.py::test_reconcile_no_launch_rejects_selective_not_started_when_accepted_exists \
  tests/cloud/test_dispatch_with_admission.py::test_pre_entry_release_requires_receipt_bound_physical_operation_evidence \
  tests/cloud/test_dispatch_reconciliation.py::test_reconciliation_explicit_persisted_state_matrix \
  tests/cloud/test_dispatch_reconciliation.py::test_no_launch_commits_before_projection_and_replays_idempotently \
  tests/cloud/test_dispatch_with_admission.py::test_identical_retry_never_relaunches_unresolved_or_accepted_state
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/cloud/test_worker_admission_authority.py::test_checker_emits_each_frozen_category_with_context \
  tests/cloud/test_worker_admission_authority.py::test_checker_detects_qualified_getattr_call_alias \
  tests/cloud/test_worker_admission_authority.py::test_checker_detects_reversed_multiline_absent_wbc_delegation \
  tests/cloud/test_worker_admission_authority.py::test_checker_detects_aliased_process_and_raw_launch \
  tests/cloud/test_worker_admission_authority.py::test_checker_detects_aliased_double_admission
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/cloud/test_worker_admission_authority.py
PYTHONDONTWRITEBYTECODE=1 python -B scripts/check_worker_admission_authority.py --check
if rg -n \
  'refresh_runtime_launch_seed_for_worker_dispatch|require_configured_runtime_launch' \
  arnold_pipelines/megaplan/workers/_impl.py \
  arnold_pipelines/megaplan/workers/omp.py \
  arnold_pipelines/megaplan/cloud/babysitter/launch.py
then
  exit 1
fi
```

Then run every exact frozen NBF-02/NBF-03 command and preservation command in
`.oracle/tasklist.md` / `.oracle/rework/batch-2-attempt-3.md`, including the
full focused suites, clean-baseline proof, static checker/raw-symbol scan,
compile, `git diff --check`, and final source/test/production diff digest. Do
not skip a command because a focused group is green. Do not rerun an expensive
suite only if an authoritative fresh result covers the identical command; state
the reused receipt and its digest.

## Executor deliverables

Create only these new versioned executor artifacts after implementation and
validation:

- `.oracle/findings/execution-batch-2-attempt-4-luna.md`
- `.oracle/receipts/execution-batch-2-attempt-4-luna.md`

Bind all changed paths, source/base/current/candidate identities, frozen hashes,
packet and Sol evidence hashes, review-policy hash, every command and result,
stream/error digests, baseline classification, final production and full
source/test diff digests, and the North Star exact-match result. The finding is
executor evidence, not a self-review or Oracle verdict. The receipt must state
that no commit, stage, push, merge, Batch 3, frozen/history/status mutation, or
nested model occurred.
