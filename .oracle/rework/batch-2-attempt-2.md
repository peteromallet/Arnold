# Batch-2 rework attempt-2 — Sol triage packet

## Triage status and boundary

This packet records Oracle triage evidence only. It is not implementation, a
fresh review, a Batch-2 gate, or a Batch-2 verdict. It does not authorize a
model launch, executor, reviewer, source/test edit, commit, stage, push, merge,
history rewrite, Batch 3, or mutation of the frozen tasklist, North Star, plan,
agent goal, custody, status, or any prior artifact. A later, separately
authorized execution leaf may consume this packet in the strict serial order
below.

Exactly five surviving roots are accepted and deduplicated:

1. `R2-RTB-001` — runtime binding/custom-validator authority boundary;
2. `R2-NATIVE-001` — native proof authority and exact route identity;
3. `R2-TERM-003` — production typed terminal transport;
4. `R2-LIFE-004` — dispatch-wired truthful pre-entry reconciliation;
5. `R2-AUTH-005` — adversarial authority-checker coverage.

All five are `Normal`, selected model GPT-5.6 Luna. None meets the exceptional
`[XHARD]` threshold: each is governed by a frozen typed, identity, cardinality,
state-machine, or static-checker oracle and contains no irreducible judgment
kernel. No model was launched during this triage.

`B2-CHILD-005`, `B2-OMP-006`, and `B2-SCHED-008` remain accepted passes and
must not be reopened absent new direct evidence. The four NBF-03 babysitter
failures remain unchanged-baseline evidence, not an attempt-2 work item.

## Immutable binding

| Binding | Verified identity |
|---|---|
| Repository / branch | `/Users/peteromalley/Documents/Arnold-oracle-nbf` / `megado-nbf-guard-0826` |
| Current HEAD | `2297fb330cdb375b4e5bd048f0d5c37d0e06db30` |
| Source/base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` |
| Candidate implementation | `5da26ec5be4d13559948fe4256a114ad7626482b` |
| Candidate parent / tree | `19deab5bb407273e7e82d40a66fc06d17af93ad4` / `e3d0376482154c4f95d2ec5809d630c4a0c32e69` |
| Candidate canonical production+focused diff | 392,090 bytes / `5586c1861dce44334c3991e997bdc8b90b82d25d2ed8f28bb558b42aae499fd0` |
| Rework-1 production+test diff | 56,801 bytes / `b1c37f2168165047fe976156625fde217b29cd7928757ac5d9e4fa02b88b4bf2` |
| Rework-1 production-only diff | 50,324 bytes / `e4efc78fb00ac60bbb8ed939ba0653d06307d566fc9e6656235fa4a293bc1991` |
| Frozen tasklist | `.oracle/tasklist.md` / `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| Frozen North Star | `.oracle/northstar.md` / `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| Frozen plan | `.oracle/plan.md` / `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| Frozen agent goal | `.oracle/agent_goal.md` / `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` |
| Frozen custody | `.oracle/custody.md` / `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| Policy override | `.oracle/receipts/model-policy-override-batch2-sol.md` / `6ab820892edaca0bd1b60bbd8a4934904b2f0d3a7704aaa77477779c6218085b` |
| Rework-1 gate brief | `.oracle/briefs/oracle-batch-2-rework1-sol.md` / `c8c0267c01e1f6110b0b9f341382cfccaae2f727f8b86f349e09c5790c6a8af9` |
| Rework-1 Luna check-in / receipt | `78ab46f94529728cfbfdbb72828949e323dfe3177dd7231c37a1a27bbea38f45` / `e758d5d1928019ad0356f23b0992147714bd00280da8e8adbdef06616b8fd1d3` |
| Rework-1 Sol check-in / receipt | `4230d985d68e88a7660db189d963e0c028d072efbb95474bc11e28dee9344245` / `a4e8a005920465a5a8e4441924738bae3d44562779add42863601736a1128462` |
| Original accepted Luna check-in / receipt | `0b9e339ae594039e44be5328ea26a5f210e0347d779a0c7c4309a2e21d7d9613` / `2f092fd5ac5c1dd6e254d45241e80bab265beefc9f132d8b2a59e9b31bb89a5e` |
| Original accepted Sol check-in / receipt | `3c222d8ab50f591b5b9ac9688d2cb1a056a65a84bf9dcdd89b76694cb5c52653` / `55888e85bbce6a9bae7daef7754e7a799a9c74dad31b04da58d5e84a885c8c74` |
| Attempt-1 packet / triage receipt | `4ac1c007cdef27f223841ea4e4cb16aca5d4c23a4d3292983cfb4e8ba8469615` / `caaffc753a899b23c773a8551c67dadbf15edb2f88934dbb22595901390e41aa` |
| Attempt-1 execution brief | `77fdfb2ce75cf149aea4744f68678ee6e22cfdb8b7b4b4b47d3fabf997d6db00` |
| Attempt-1 sealed finding / receipt | `0bbd43a08d1e25d583ed7267ebe2da140b950d4ade46cbc3185e22242d4048d4` / `b0ebecd1395c5f93015834e70629159f686969d5aef13eb2e0aecb7b5026a224` |
| Nested-launch / invalid-provenance incidents | `b9f52bd8c7368f9604140d6021c30a72673992eee0e802bd8430f55b94122b4d` / `1ed5777d62d40d821c37b246cd4c99d4c166f96f77c9a4e13c79aa37b9ca2b43` |

All historical aborted, fallback, nested, invalid-provenance, and premature
Batch-3 material is quarantine context only. It supplies no replacement gate,
review, implementation, or verdict authority.

## Canonical North Star — byte-verbatim

The bytes between the two markers, excluding the marker lines themselves, are
the complete `.oracle/northstar.md`, including its original final newline.

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

## 1. `R2-RTB-001` — Runtime binding/custom-validator authority boundary

### Concrete evidence and frozen criterion

- Rework-1 Luna check-in lines 17–20 and Sol check-in criterion table record a
  production-shaped admission using arbitrary caller-supplied source, runtime,
  manifest, seed, and interpreter values; Sol probe `C01` created one
  reservation from that forged proof.
- Current `worker_dispatch.py:358-369` returns any positive mapping from
  `request.source_runtime_validator`; `:401-436` then treats the same mapping
  as authoritative if its values agree with the request. This proves agreement
  between two caller-shaped objects, not agreement with current runtime truth.
- Exact affected frozen NBF-02 criteria:
  “`require_production_worker_dispatch_runtime` is the only admission authority
  and returns one receipt proving every settled invariant” and “Production
  rejects before WBC/client/process/RPC construction when source, runtime,
  manifest, seed, interpreter, timeout, memory, route liveness, or ledger proof
  is absent or invalid.”
- Exact affected frozen agent-goal criterion: criterion 1, **Unique admission
  gate**, including seed/interpreter binding and fail-closed admission before a
  worker exists.

North Star connection: “Models are admitted, not assumed” and “One door per
invariant.” Anti-pattern connection: judgment-based healthy claims without
positive proof.

### Narrow outcome, ownership, non-goals, order, and model

Use one canonical authoritative runtime-binding path before reservation. A
custom validator may remain as a legitimate injected test seam only when its
typed proof is cryptographically/identity-bound to the current authoritative
source revision, runtime vector, manifest, seed, and interpreter evidence; it
may not replace or manufacture that evidence. Reject missing, stale, forged,
or mismatched proof typedly before reservation and before WBC/client/process/RPC
construction.

Owned paths only:

- `arnold_pipelines/megaplan/cloud/worker_dispatch.py`
- `arnold_pipelines/megaplan/cloud/runtime_attestation.py`
- `tests/cloud/dispatch_test_helpers.py`
- `tests/cloud/test_runtime_attestation.py`
- `tests/cloud/test_worker_dispatch_admission.py`
- `tests/cloud/test_worker_dispatch_context.py`

Non-goals: no new authority, journal, provider policy, network probe, route
fallback, signal-site work, or change to passed child/OMP/scheduler behavior.
Dependency: existing NBF-01 ledger/CAS and runtime-attestation primitives.
Strict order: item 1 of 5. Classification: `Normal`. Selected model: GPT-5.6
Luna.

### Acceptance oracle

- Forged positive callback values for each of source, runtime vector, manifest,
  seed, and interpreter return a typed refusal; reservations, WBC attempts,
  clients, processes, and RPCs remain cardinality zero.
- A callback proof copied from a prior source/runtime/seed generation refuses.
- A legitimate injected seam bound to the current authoritative evidence admits
  exactly once and the receipt/fingerprint contains those authoritative
  identities.
- Omitting the callback cannot omit authoritative validation.

Focused command:

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/cloud/test_runtime_attestation.py tests/cloud/test_worker_dispatch_admission.py tests/cloud/test_worker_dispatch_context.py
```

## 2. `R2-NATIVE-001` — Native proof authority and exact route identity

### Concrete evidence and frozen criterion

- Current `worker_dispatch.py:521-522` accepts a route-liveness resolver from
  the request/worker options; `_validate_native_liveness` at `:439-453` checks
  nonempty fields and provider/model but does not authenticate the proof to the
  seam that will construct the selected backend/client. Its required `backend`
  field is not compared to the selected backend.
- Rework-1 Luna admitted `backend=not-codex`; the Sol gate retained this
  failure and also confirmed that an injected OMP resolver can supply a
  mismatched nonempty identity/digest. `R2-ROUTE-002` is therefore a duplicate
  exact-route aspect and is folded into this single item.
- Exact affected frozen NBF-02 criteria: “OMP requires bounded, valid, exact
  `omp models --json` membership”; “Native routes require positive proof from
  the actual native backend/runtime/model seam without being forced into OMP or
  adding speculative network checks”; and static `ox-alpha` acceptance must
  still be jointly rejected live before client construction.
- Exact affected frozen agent-goal criterion: criterion 5, **Joint model
  admission — and expired-ID proof**.

North Star connection: “Models are admitted, not assumed.” Anti-pattern
connection: executable/nonempty identity presence or caller assertion treated
as capability and live membership proof.

### Narrow outcome, ownership, non-goals, order, and model

Bind positive proof to the actual seam constructing the selected native
backend/provider/model. Require exact normalized provider/model membership,
backend identity, route identity, capability/runtime registry generation, and
proof digest/content binding before reservation or client construction. For
OMP, validate the injected seam's identity/digest against the exact requested
normalized membership rather than accepting arbitrary nonempty strings.

Owned paths only:

- `arnold_pipelines/megaplan/cloud/worker_dispatch.py`
- `arnold_pipelines/megaplan/workers/_impl.py`
- `arnold_pipelines/megaplan/workers/omp.py`
- `tests/cloud/dispatch_test_helpers.py`
- `tests/cloud/test_runtime_attestation.py`
- `tests/cloud/test_worker_dispatch_admission.py`
- `tests/workers/test_omp_adapter.py`

Non-goals: no T8 policy; no speculative network probe; no forcing native models
through OMP; no new provider authority; no reopening absent-WBC OMP, child, or
scheduler passes. Dependency: `R2-RTB-001`. Strict order: item 2 of 5.
Classification: `Normal`. Selected model: GPT-5.6 Luna.

### Acceptance oracle

- Executable-only, caller-forged, wrong-backend, wrong-provider, wrong-model,
  wrong-route, stale-generation, ambiguous, missing, or digest-mismatched proof
  typedly refuses before reservation/client/process/RPC construction.
- An injected OMP proof must match the exact normalized provider/model member
  and authoritative membership digest; arbitrary nonempty identity/digest does
  not admit.
- A proof generated by the actual selected native construction seam admits
  exactly once; a matching OMP member still admits through OMP only.
- Static catalog acceptance plus live rejection of
  `openrouter/stealth/ox-alpha` remains green.

Focused command:

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/cloud/test_worker_dispatch_admission.py tests/cloud/test_runtime_attestation.py tests/workers/test_omp_adapter.py
```

## 3. `R2-TERM-003` — Production typed terminal transport

### Concrete evidence and frozen criterion

- Current `worker_dispatch.py:607-613` converts every native `WorkerResult` and
  four-tuple wrapper into `DispatchOutcome(kind="success")`.
- Current `dispatch_with_admission` catches every exception at `:792-795` and
  returns an identity-poor unresolved outcome. The rework-1 Sol gate therefore
  found no lossless ordinary-failure, provider-exhaustion, or
  worker-disposition transport through the real native/OMP closures even though
  generic six-kind schema/ledger tests pass.
- `ControlledFinalLaunch.run` at `controlled_final_launch.py:97-122` records
  `accepted` for a typed worker value before operation-specific terminal
  mapping; this makes record-before-projection ordering and exact typed mapping
  load-bearing.
- Exact affected frozen NBF-02 criteria: “Accepted success, ordinary failure,
  provider exhaustion, and worker disposition each record one canonical
  terminal event before consumer projection”; disposition retains all identity
  and is never coerced into ordinary failure/provider degradation; append/link
  failure retains an unresolved reservation.
- Exact affected frozen agent-goal criterion: criterion 3, **Typed death
  dispositions — every real signal branch**, specifically the typed identity
  that Batch 2 must transport without loss after acceptance.

North Star connection: “Deaths speak.” Anti-pattern connection: anonymous
integer/undifferentiated success where a typed failure or disposition belongs.

### Narrow outcome, ownership, non-goals, order, and model

Give each physical operation door an explicit typed terminal mapping. Preserve
success, ordinary failure, provider exhaustion, and worker disposition with
receipt, fingerprint, selected route, worker/disposition identity, timing, and
accepted-launch context. Append the canonical terminal exactly once before
consumer projection. Preserve existing breaker semantics. Keep arbitrary
legacy integers, strings, tuples, objects, and malformed mappings rejected;
do not revive permissive legacy coercion.

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

Non-goals: no provider policy/T8, no signal-site implementation, no ledger or
schema rewrite, no loosening of unknown-value rejection, and no reopening
passed OMP/child/scheduler ownership. Dependencies: `R2-RTB-001`,
`R2-NATIVE-001`, and the existing NBF-01 terminal writer. Strict order: item 3
of 5. Classification: `Normal`. Selected model: GPT-5.6 Luna.

### Acceptance oracle

- Each physical door maps typed success, ordinary failure, provider exhaustion,
  and worker disposition without kind or identity loss; one accepted logical
  dispatch appends exactly one terminal event before return/projection.
- Worker disposition retains disposition ID, receipt, fingerprint, phase/spec,
  worker, timing, and accepted state; it never enters provider degradation and
  keeps its breaker semantics.
- Terminal append/link failure returns unresolved and leaves the reservation
  held; replay does not double append.
- Arbitrary integers, strings, tuples, objects, malformed mappings, and
  non-operation-specific `WorkerResult` failure encodings cannot become
  terminal success.

Focused command:

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/cloud/test_dispatch_with_admission.py tests/cloud/test_controlled_final_launch.py tests/cloud/test_worker_dispatch_spy.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_common_worker_dispatch_wbc.py
```

## 4. `R2-LIFE-004` — Dispatch-wired truthful pre-entry reconciliation

### Concrete evidence and frozen criterion

- `reconcile_no_launch` at `worker_dispatch.py:666-732` correctly requires a
  persisted receipt-bound `not_started` marker and rejects entered/accepted
  contradiction.
- `dispatch_with_admission` at `:768-795` always constructs the adapter, calls
  `controlled.run`, and therefore persists `entered` before the operation.
  It has no operation-derived positive pre-entry/no-acceptance branch that can
  call the strict helper and commit `released_no_launch` before projection.
- Rework-1 Sol accepted the existing safe unresolved hold but found the
  positive release half of the frozen state matrix unwired.
- Exact affected frozen NBF-02 criteria: “Positive no-entry/no-acceptance
  evidence reconciles before returning `no_launch`”; missing, contradictory,
  post-entry, or post-acceptance evidence stays unresolved; each final-launch
  closure is at most once; outcome-append failure holds the reservation.
- Exact affected frozen agent-goal criterion: criterion 4, **Fingerprint
  redispatch block — pre-launch**, because truthful release versus unresolved
  hold controls whether identical redispatch can occur.

North Star connection: one door per invariant. Anti-pattern connection: blind
redispatch from inferred no-launch or missing process evidence.

### Narrow outcome, ownership, non-goals, order, and model

Wire operation-derived evidence into `dispatch_with_admission` so only proven
pre-entry/no-acceptance reaches exactly one committed `released_no_launch`
before `no_launch` projection. Represent pre-entry, entered, accepted,
ambiguous, append-failure, and restart states explicitly. Contradictory,
post-entry, post-acceptance, missing, or append-failed evidence remains
unresolved and cannot trigger blind retry.

Owned paths only:

- `arnold_pipelines/megaplan/cloud/worker_dispatch.py`
- `arnold_pipelines/megaplan/cloud/controlled_final_launch.py`
- `tests/cloud/test_controlled_final_launch.py`
- `tests/cloud/test_dispatch_reconciliation.py`
- `tests/cloud/test_dispatch_with_admission.py`

Non-goals: no inference from PID absence, exception text, elapsed time, or
restart; no terminal-kind rewrite; no new reconciliation authority; no change
to passed scheduling behavior. Dependency: `R2-TERM-003`. Strict order: item 4
of 5. Classification: `Normal`. Selected model: GPT-5.6 Luna.

### Acceptance oracle

- Positive receipt-bound pre-entry/no-acceptance evidence appends exactly one
  `released_no_launch`, commits it before returned projection, clears no
  unrelated reservation, and creates zero terminal/fingerprint/breaker input.
- Entered, accepted, contradictory, missing, or append-failed evidence returns
  typed unresolved, retains the reservation, and never relaunches on identical
  retry or restart.
- Reconciliation replay is idempotent and restart restores the strongest
  persisted state.

Focused command:

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/cloud/test_controlled_final_launch.py tests/cloud/test_dispatch_reconciliation.py tests/cloud/test_dispatch_with_admission.py
```

## 5. `R2-AUTH-005` — Adversarial authority-checker coverage

### Concrete evidence and frozen criterion

- Current checker recognizes process starts only for `Popen`, asyncio process
  constructors, `system`, and `call` at
  `scripts/check_worker_admission_authority.py:108-117`; aliased
  `subprocess.run` is absent.
- Its absent-WBC text rule at `:152-158` requires the condition and
  `final_launch(` on the same physical line, so multiline delegation evades it.
- Raw final-launch detection at `:121-122` accepts only unaliased `Name` calls;
  nested admission counting at `:127-149` is scope/line based. Existing focused
  tests contain only the repository-positive case and one import-alias raw
  preflight fixture (`tests/cloud/test_worker_admission_authority.py:6-19`).
- Sol fixture `C03` combined aliased `subprocess.run`, nested admissions,
  multiline absent-WBC delegation, and aliased raw final-launch access; the
  checker returned `ok: true` with zero diagnostics.
- Exact affected frozen NBF-03 criterion: the checker detects raw authority
  calls, resolvable aliases, chain-local preflight/spawn, no-WBC legacy
  delegation, WBC-before-admission, nested double admission, and raw launch
  access, and passes across all doors/chain origins.
- Exact affected frozen agent-goal criteria: criterion 2, **Wire all three
  launch doors — exactly once each**, and criterion 6, **Structural spy test —
  three doors, gate-before-spawn**.

North Star connection: one door per invariant. Anti-pattern connection: a
green narrow/grep-like scan treated as proof of authority ownership.

### Narrow outcome, ownership, non-goals, order, and model

Implement deterministic AST/text categories with qualified/import alias
resolution and contextual diagnostics containing path, line, enclosing symbol,
category, and reason. Add one adversarial negative fixture for every frozen
category, including the four demonstrated evasions. Retain the independent
raw-symbol scan.

Owned paths only:

- `scripts/check_worker_admission_authority.py`
- `tests/cloud/test_worker_admission_authority.py`
- `tests/cloud/test_worker_dispatch_spy.py`
- `tests/cloud/test_chain_admission.py`

Non-goals: the checker does not become runtime authority; no production-door
rewrite without a new repository diagnostic; no broad linter framework; no
replacement of the readable raw-symbol scan. Dependency: final door shapes
after `R2-TERM-003` and `R2-LIFE-004`. Strict order: item 5 of 5.
Classification: `Normal`. Selected model: GPT-5.6 Luna.

### Acceptance oracle

- One isolated negative fixture per frozen category produces the exact category
  and contextual diagnostic; qualified, imported, module, assignment, and call
  aliases cannot evade resolution.
- Dedicated fixtures catch aliased `subprocess.run`, multiline absent-WBC
  delegation, nested/double admission across nested scopes, and aliased raw
  final-launch access.
- Repository doors and chain origins produce zero diagnostics only after all
  categories have executed; the checker remains deterministic across ordering.
- The secondary raw-symbol scan remains empty and independent.

Focused commands:

```bash
PYTHONDONTWRITEBYTECODE=1 python -B scripts/check_worker_admission_authority.py --check
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/cloud/test_worker_admission_authority.py tests/cloud/test_worker_dispatch_spy.py tests/cloud/test_chain_admission.py
```

## Preserved passes and rejected/duplicate dispositions

- `B2-CHILD-005` — preserve as PASS. Composite ledger reservation already
  validates terminal parent, authorizer, context, route, projection, evidence,
  single use, and derived receipt under lock. No attempt-2 item owns that
  implementation.
- `B2-OMP-006` — preserve as PASS. Production absent-WBC OMP typedly refuses
  before raw/legacy launch, and direct/nested ownership remains one OMP
  admission. Exact-route proof mismatch is not an absent-WBC reopening; it is
  deduplicated into `R2-NATIVE-001`.
- `B2-SCHED-008` — preserve as PASS. Sol rejected Luna's second-wait-owner
  finding after tracing typed scheduling propagation; no scheduler rework is
  accepted.
- Luna `R2-ROUTE-002` — rejected as a duplicate item; its concrete exact
  provider/model membership and digest gap is retained inside
  `R2-NATIVE-001`.
- Broad six-kind × every-door defect claims — rejected; only the source-proven
  production typed-transport root remains as `R2-TERM-003`.
- Historical aggregate-digest issue — rejected as a reproducible construction
  nonissue.
- Four NBF-03 babysitter failures — unchanged baseline only. The failing tests
  and routing/renderer sources retain parent hashes
  `ba75ceca1f1316864aef83d6f92a81fae2cd4e88c2da0168dac1391d817eb7fa`,
  `4e85a83fa889640abaea70046d73498a2ed407bccffc3434750c764df2c87153`,
  `285af9a1ac4f2db640d4ca781f426e4c52f2af47203a5deff0f0db805a62f9eb`,
  and `8e781247c8e8de436bb78dba3e55e799b6e2300c6f72f623866477c01e26aa3d`.
- T8 thresholds/probes/degradation/fallback/return/races — rejected as deferred
  NBF-06 scope. Second journal, provider rotator, family lease, and generalized
  ownership claims — rejected as unsupported.

Preservation regression commands, run after the five serial items:

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/cloud/test_chain_admission.py tests/cloud/test_dispatch_with_admission.py tests/arnold_pipelines/megaplan/test_provider_route_projection.py tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/cloud/test_worker_dispatch_spy.py tests/cloud/test_chain_admission.py tests/cloud/test_dispatch_with_admission.py tests/arnold_pipelines/megaplan/test_common_worker_dispatch_wbc.py tests/workers/test_omp_adapter.py
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/cloud/test_dispatch_with_admission.py tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_phase_result_classify.py tests/arnold_pipelines/megaplan/test_plan_circuit.py
```

## Frozen Batch-2 validation contract for a future executor

Implementation, if separately authorized, must be one serial writer in the
item order above. No parallel writer, expanded reviewer operation, nested
launch, or concurrent item validation is permitted. Each item must be complete
and its focused command captured before the next item starts. After all five
items and the three preservation commands, run the following gates.

Frozen NBF-02 focused suite:

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

Frozen NBF-03 focused suite:

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/cloud/test_worker_dispatch_spy.py \
  tests/cloud/test_worker_admission_authority.py \
  tests/cloud/test_chain_admission.py \
  tests/cloud/test_babysitter_routing.py \
  tests/cloud/test_babysitter_goal.py \
  tests/arnold_pipelines/megaplan/test_common_worker_dispatch_wbc.py
```

The expected NBF-03 result remains exactly 41 passed and the same four
unchanged-baseline failures unless new direct evidence proves otherwise. Prove
the baseline identities with:

```bash
git diff --quiet 19deab5bb407273e7e82d40a66fc06d17af93ad4 -- \
  arnold_pipelines/megaplan/cloud/babysitter/routing.py \
  skills/babysitter/scripts/render_babysitter_goal.py \
  tests/cloud/test_babysitter_routing.py \
  tests/cloud/test_babysitter_goal.py
sha256sum \
  arnold_pipelines/megaplan/cloud/babysitter/routing.py \
  skills/babysitter/scripts/render_babysitter_goal.py \
  tests/cloud/test_babysitter_routing.py \
  tests/cloud/test_babysitter_goal.py
```

Exact checker, secondary raw-symbol scan, compile, and diff checks:

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

No broad Batch-3/T8 suite is demanded merely for attempt-2 triage. A future
execution brief and executor finding/receipt must bind every command above,
the frozen NBF-02/NBF-03 path lists, checker, raw scan, compile, diff-check,
baseline classification, and final source/test diff.

For every future command, use a fresh external evidence root outside the
repository and capture: literal argv; UTC start and end; exit status; separate
stdout and stderr byte counts and SHA-256; pre/post
`git status --porcelain=v1 -uall`; changed-path list and SHA-256 before and
after; and the exact candidate/source/base bindings. A zero exit is not enough:
the finding/receipt must state the typed, refusal, cardinality, state, or checker
oracle observed. No transcript may be written into frozen or prior artifacts.

## Delegation mandate for later separately authorized execution

DELEGATION MANDATE — You are a manager and validator of the normal execution pool, NOT a worker. Delegate as much as possible to the task's selected normal model: DeepSeek V4 Flash or GPT-5.6 Luna. Flash invocation: `omp -p @<brief>.md --model deepseek-v4-flash --cwd <worktree> --no-session --auto-approve --max-time=1800`; Luna invocation: `launch_hermes_agent.py --model="codex:gpt-5.6-luna" --query-file=<brief> --project-dir=<worktree>` (research-only briefs use read/search tools). Dispatch research, execution, and critique briefs to the selected model — critique passes optimize for elegance: KISS, YAGNI, cut scope that isn't pulling its weight; flag overengineering, not just bugs. Your job is to direct, then validate: read delegated output against the acceptance criteria; do work yourself only when delegation is impossible — the selected normal model already failed at it, or the piece is too small / too tightly coupled to your own reasoning to hand off. If you catch yourself implementing or researching directly, stop and ask whether a normal-pool brief would cover it. It almost always would.

This mandate applies only after a separate execution authorization. It did not
authorize a model launch during this triage, and no model was launched.

## Final packet boundary

This packet performs none of the five accepted items and issues no Oracle gate
token or verdict. It changes no source, test, frozen input, status, history,
agent goal, custody, prior artifact, or Batch-3 material. It authorizes no
implementation, review, verdict, commit, stage, push, merge, reset, clean,
history rewrite, or Batch 3. Only this packet and its paired attempt-2 triage
receipt are authorized outputs of this leaf.
