# Corrected Luna execution brief — NBF-02 → NBF-03 / Batch 2 continuation

## Execution identity and boundary

You are GPT-5.6 Luna at high reasoning, the sole Normal executor for this fresh
leaf continuation. This is implementation and validation work, not review,
Oracle work, or a verdict. Execute the frozen Batch-2 tasks serially:
NBF-02 completely, then NBF-03 completely. Work in
`/Users/peteromalley/Documents/Arnold-oracle-nbf` on branch
`megado-nbf-guard-0826`, inspecting the current dirty tree before editing.

This continuation starts from current HEAD
`19deab5bb407273e7e82d40a66fc06d17af93ad4`, whose parent Batch-1 PASS
checkpoint is `878a9b2980f0eab6642ed51c30e687903a7213b9`. The immutable source
base is `origin/main@798c50619204010ed3f4297fbb57988fe9381924`. The frozen
tasklist SHA-256 is
`9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`.

The first Batch-2 execution brief is preserved at
`.oracle/briefs/execution-nbf02-nbf03-luna.md`, SHA-256
`938f61b1ccaa06ea9cd7e428b184d02143f9e87accf96eeb95ec8b0e70797003`. Record
its heading-level propagation defect: its North Star section changed the
original `# North Star — Arnold self-healing supervision` heading to a lower
`##` heading and therefore did not embed the North Star byte sequence
verbatim. Do not edit or rewrite that brief.

The first execution evidence bindings are retained as historical inputs:

- finding `.oracle/findings/execution-nbf02-nbf03-luna.md`, supplied SHA-256
  `77831c...`;
- receipt `.oracle/receipts/execution-nbf02-nbf03-luna.md`, supplied SHA-256
  `b957f16fab1aa5502440434b1c51931b584b2321fc7be1c88af0ce7797367b07`;
- first execution current production-diff identity, supplied as `499c98...`.

The current dirty Batch-2 work is in scope. Preserve unrelated user changes
and all historical artifacts. Use `apply_patch` for every edit. Do not invoke
Megaplan, Megado, a nested harness, another agent, a reviewer, or an Oracle.
Do not commit, stage, push, merge, rebase, reset, clean, start Batch 3, or edit
`.oracle/tasklist.md`, `.oracle/northstar.md`, `.oracle/agent_goal.md`,
`.oracle/status.md`, `.oracle/custody.md`, or historical findings/receipts.

## North Star — verbatim byte block

The following block is copied byte-for-byte from `.oracle/northstar.md`,
including its original level-one heading. Do not alter any character:

```text
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
```

Independently verify before implementation that the extracted canonical file
hash is exactly:
`d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`.
The evidence receipt must include the literal `sha256sum .oracle/northstar.md`
command and its matching result.

## Frozen implementation scope

Read `.oracle/agent_goal.md`, `.oracle/plan.md`, the complete NBF-02 and NBF-03
sections of the frozen tasklist, and the current source/tests before editing.
Implement the contracts fully, not a scaffold or source-only probe.

### NBF-02 — canonical admission and generic scheduling

Own the canonical typed admission request, receipt, refusal, and execution
context; NBF-01 reservation primitives; OMP and native route-applicable positive
liveness; generic `dispatch_with_admission`; controlled final-launch sequencing;
T7 memory-cooldown scheduling; typed `DispatchOutcome` including
`worker_disposition`; truthful `no_launch`; final-launch exception normalization;
canonical terminal-writer integration; disposition-to-terminal linkage without a
duplicate disposition append; unresolved-reservation reconciliation; lossless
scheduling/no-launch/worker-disposition transport through handlers and `auto.py`;
early breaker bypass for scheduling/no-launch only; and generic authorized
linked-child construction.

Production must reject before WBC/client/process/RPC construction when any
required source, runtime, manifest, seed, interpreter, timeout, memory, route
liveness, or ledger proof is absent or invalid. OMP must require bounded valid
exact `omp models --json` membership. Native routes need positive proof from the
actual native backend/runtime/model seam without being forced through OMP or
gaining speculative network checks. Static catalog acceptance of
`openrouter/stealth/ox-alpha` remains, while joint live admission rejects it
typedly before client construction. Same-fingerprint different logical IDs must
share one reservation; liveness-only changes cannot bypass refusal; only a
canonical evidence-bound single-use changed precondition can authorize
redispatch.

`dispatch_with_admission` is the sole scheduling loop. T7 cooldown may retry
with idempotent retry-wait evidence and injected sleep, but produces zero launch,
WBC attempt, or failure before admission. Scheduling expiry reaches
`PhaseResult` without failure accounting, breaker mutation, or `blocked`.
`ControlledFinalLaunch` must persist `not_started -> entered -> accepted` in
order, allow at most one final-launch closure per logical dispatch, and support
truthful no-entry/no-acceptance reconciliation. Missing, contradictory,
post-entry, or post-acceptance evidence remains unresolved until canonical
evidence exists. Accepted success, ordinary failure, provider exhaustion, and
worker disposition each record one canonical terminal event first. Worker
disposition retains its ID, receipt, fingerprint, phase/spec, worker, timing,
and accepted-launch context end-to-end and is never coerced into ordinary
failure/provider degradation. Outcome/link failure retains an unresolved
reservation. Linked children require a canonical terminal parent and durable
authorization; no-launch/unresolved parents are insufficient.

Do not implement provider thresholds/probing/degradation/fallback/scalar/
return-to-primary policy, signal-site wiring, two-scan policy calls, or T8 route
races.

### NBF-03 — three physical doors and authority proof

Own native non-OMP, direct/nested OMP, babysitter, and chain-originated physical
door bindings; nested/direct OMP ownership; chain delegation; production no-WBC
closure; WBC intent/admission/start ordering; controlled-adapter placement;
admission-attempt/final-launch traces; generic scheduling/no-launch/
worker-disposition traces; receipt-context propagation; and the admission
authority bypass checker.

Every production `run_step_with_worker` call enters `dispatch_with_admission`.
Nested OMP has exactly one admission hit in `run_omp_step`, with no outer
`_impl.py` hit. `wbc_dispatch=None` constructs the canonical adapter or rejects
before legacy launch. WBC intent precedes admission, but WBC start follows
reservation, derived receipt, and `not_started`. Scheduling and truthful
no-launch produce no WBC start/failure/completion. Accepted worker disposition
traces preserve the ID and show record-before-signal followed by one terminal
projection. Authorized children use new linked logical IDs.

Door removal, duplicate outer admission, chain bypass, no-WBC bypass,
WBC-before-admission, direct raw launch access, and second launch must fail.
Structural tests replace only final spawn/RPC/WBC/managed-command seams and do
not use `MEGAPLAN_MOCK_WORKERS=1`. Different-fingerprint dispatches remain
concurrent; add no family lease. The checker must detect raw authority calls,
aliases, chain-local preflight/direct spawn, no-WBC legacy delegation,
WBC-before-admission, nested double admission, and raw launch access; it must
pass across all doors and chain origins. The three door files contain no raw
refresh/require calls. Do not mutate `/workspace/.cloud-hot-env`. No T8 policy
may appear beyond the frozen extension/tracing interface.

## Required validation — execute every command

Run every exact frozen command below with cwd
`/Users/peteromalley/Documents/Arnold-oracle-nbf`; do not skip collection-blocked
commands or treat absent modules as acceptable blockers. If a task-required test
file is absent, create it with the strongest obvious behavioral coverage and
exercise the real semantics. Preserve full literal commands, UTC start/end,
exit codes, complete stdout/stderr files, and SHA-256 digests under a fresh
evidence directory (for example `/tmp/oracle-nbf02-nbf03-luna-v2-0830/`).

### Exact NBF-02 focused command

```bash
pytest -q \
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

### Exact NBF-03 focused command

```bash
pytest -q \
  tests/cloud/test_worker_dispatch_spy.py \
  tests/cloud/test_worker_admission_authority.py \
  tests/cloud/test_chain_admission.py \
  tests/cloud/test_babysitter_routing.py \
  tests/cloud/test_babysitter_goal.py \
  tests/arnold_pipelines/megaplan/test_common_worker_dispatch_wbc.py
```

### Exact checker and raw-symbol scan

```bash
python scripts/check_worker_admission_authority.py --check
```

```bash
if rg -n \
  'refresh_runtime_launch_seed_for_worker_dispatch|require_configured_runtime_launch' \
  arnold_pipelines/megaplan/workers/_impl.py \
  arnold_pipelines/megaplan/workers/omp.py \
  arnold_pipelines/megaplan/cloud/babysitter/launch.py
then
  exit 1
fi
```

Also run the full frozen Batch-2 checkpoint matrix: every NBF-02/NBF-03 test
module and acceptance seam, all 42 existing runtime-attestation tests, native,
direct/nested OMP, babysitter, chain, no-WBC, authorized-child, WBC ordering,
logical-ID cardinality, typed disposition, scheduling/no-launch, reconciliation,
and `ox-alpha`/native-liveness probes. Run `py_compile` for every changed Python
file and `git diff --check`. Investigate and resolve the four babysitter/WBC
failures seen by the first executor if they are candidate-caused. If and only if
they are proven baseline/pre-existing, retain the frozen acceptance proof and
record the source checkpoint and exact evidence; they are not a reason to skip
the required semantics. Do not use broad missing-module results as a silent
waiver.

## Evidence and deliverables

Write only these fresh executor artifacts after implementation and validation:

- `.oracle/findings/execution-nbf02-nbf03-luna-v2.md`
- `.oracle/receipts/execution-nbf02-nbf03-luna-v2.md`

Bind the current HEAD/base, frozen tasklist and North Star hashes, Batch-1 PASS
checkpoint, first brief SHA and heading defect, first finding/receipt/diff
identities, every owned path, exact commands/results, UTC timestamps, complete
stream paths/digests, test counts, py_compile/diff-check results, and final
production diff digest. State any pre-existing failure precisely, but do not
declare an Oracle verdict or self-review. Do not edit the first execution
artifacts. No commit, stage, push, Batch 3, historical rewrite, frozen-file
mutation, status/goal/custody edit, or nested harness action is permitted.
