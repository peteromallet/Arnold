# Corrected Luna execution brief — NBF-02 → NBF-03 / Batch 2 v3 continuation

## Mission and immutable bindings

You are GPT-5.6 Luna at high reasoning, the sole Normal executor for this fresh
leaf continuation. This is implementation and validation, not review, Oracle
judgment, or a verdict. Execute the frozen Batch-2 tasks strictly serially:
finish NBF-02 completely before starting NBF-03. Work in
`/Users/peteromalley/Documents/Arnold-oracle-nbf` on branch
`megado-nbf-guard-0826`, beginning from current HEAD
`19deab5bb407273e7e82d40a66fc06d17af93ad4` and source/base
`origin/main@798c50619204010ed3f4297fbb57988fe9381924`.

The frozen tasklist SHA-256 is
`9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`.
The Batch-1 PASS checkpoint is
`878a9b2980f0eab6642ed51c30e687903a7213b9`.

The canonical North Star SHA-256 is
`d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`.
The full canonical text is embedded below byte-for-byte. Verify the extracted
block independently before editing.

## Prior attempts and provenance defects

Preserve all prior artifacts immutably. Bind and inspect these identities:

| artifact | full SHA-256 | provenance note |
|---|---|---|
| first brief `.oracle/briefs/execution-nbf02-nbf03-luna.md` | `938f61b1ccaa06ea9cd7e428b184d02143f9e87accf96eeb95ec8b0e70797003` | Its North Star heading was lowered from the original `#` to `##`; not byte-for-byte verbatim. |
| first finding `.oracle/findings/execution-nbf02-nbf03-luna.md` | `9c8e6b7db2a104056c9843ffad59b04234e2dc904a8898858d049fdaf0ed1ff0` | The v2 brief’s historical binding `77831c...` was abbreviated/incorrect; retain that defect explicitly. |
| first receipt `.oracle/receipts/execution-nbf02-nbf03-luna.md` | `b957f16fab1aa5502440434b1c51931b584b2321fc7be1c88af0ce7797367b07` | Stable prior evidence. |
| corrected v2 brief `.oracle/briefs/execution-nbf02-nbf03-luna-v2.md` | `f6daf95f6b7ff91c0840170a98e3d8263e56faf28c64a4d3acd0535cdb1f2e6e` | It bound the first finding and diff with ellipses and launched without explicit `:high`. |
| v2 timeout receipt `.oracle/receipts/execution-nbf02-nbf03-luna-v2-timeout.md` | `e8c4f572ed34bda80fdebf9307c856bb336037de54ef32e26b33ec202a5c66e4` | Session `88209`, PIDs `74894/74917`, exit `124` after default 1800s; no v2 finding/receipt. |
| timeout-audit worktree diff | `e945526a223f4c03f866d892d4ab5be70c189d7fbcfb9c70552f06bf68b3f6fd` | Full SHA, not the v2 brief’s abbreviated `499c98...` binding. |
| `.oracle/plan.md` | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` | Stable prerequisite. |
| `.oracle/agent_goal.md` | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` | Stable prerequisite. |
| `.oracle/custody.md` | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` | Stable prerequisite. |

The timeout audit’s final observed diff is the complete current tracked
production/worktree diff identity at this continuation boundary; independently
rehash the current production and complete tracked worktree diff before and
after work. Do not confuse the v2 timeout’s outer launcher return `0` with its
emitted wrapper status `124`; v2 did not complete and produced no finding or
receipt.

## Exact launcher authorization

The previous v2 invocation used `--model="codex:gpt-5.6-luna"` without explicit
`:high` and omitted `--timeout`, thereby using the launcher default 1800s. This
v3 invocation must use the explicit high selector and at least 3600 seconds:

```text
PYENV_VERSION=3.11.11 python /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py --model="codex:gpt-5.6-luna:high" --query-file=/Users/peteromalley/Documents/Arnold-oracle-nbf/.oracle/briefs/execution-nbf02-nbf03-luna-v3.md --project-dir=/Users/peteromalley/Documents/Arnold-oracle-nbf --timeout=3600
```

The launcher help was inspected: `--model` accepts a string and `--timeout`
accepts a float with a 1800.0 default. Record the actual command, resolved
model, PID/session, cwd, UTC start/end, exit status, and complete stream
transcripts/digests. Do not invoke a nested harness or any reviewer.

## North Star — canonical byte-for-byte block

Do not alter any byte in this block. It is the exact content of
`.oracle/northstar.md`, including the original level-one heading:

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

Run and record:

```bash
sha256sum .oracle/northstar.md
```

Extract only the bytes between the `text` fences in this brief and compare them
with `.oracle/northstar.md`; the extracted SHA must equal
`d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`.

## Leaf restrictions and dirty-tree audit

Read `.oracle/agent_goal.md`, `.oracle/plan.md`, the complete frozen NBF-02 and
NBF-03 sections, all current source/tests, and the v2 timeout receipt before
editing. Inspect the v2 diff in full, especially large changes/deletions in
`tests/arnold_pipelines/megaplan/test_phase_result_classify.py`,
`tests/arnold_pipelines/megaplan/test_plan_circuit.py`, and all newly added
Batch-2 tests. For every deletion or broad alteration, determine whether it is
necessary for the frozen contract; restore accidental losses and remove
speculative or unrelated changes. Preserve legitimate existing Batch-1 and
user changes. Use `apply_patch` for edits.

No commit, stage, push, merge, rebase, reset, clean, Batch 3, history rewrite,
status/goal/custody/frozen-file edit, or protected live-box/chain mutation. Do
not edit the first brief, first finding, first receipt, v2 brief, or timeout
receipt. Do not self-review or issue a verdict. Produce only fresh v3 executor
evidence at the two paths named below.

## Serial implementation contract

### RW/NBF-02 first

Implement canonical typed admission request/receipt/refusal/context using the
NBF-01 reservation primitives; OMP exact bounded `omp models --json` membership;
native positive backend proof without forcing native through OMP; static
`openrouter/stealth/ox-alpha` acceptance with typed live joint rejection;
semantic-fingerprint reservation and changed-precondition authorization;
generic `dispatch_with_admission` as the sole scheduling loop; T7 cooldown retry
and expiry without launches/WBC/failure/breaker/block effects; controlled
`not_started -> entered -> accepted` launch sequencing and truthful
no-entry/no-acceptance reconciliation; typed outcomes including worker
disposition; one canonical terminal writer with no duplicate disposition append;
lossless handler/auto scheduling/no-launch/disposition transport; unresolved
reservation reconciliation; and authorized linked-child construction.

Production must fail closed before WBC/client/process/RPC construction for absent
or invalid source, runtime, manifest, seed, interpreter, timeout, memory, route
liveness, or ledger proof. Worker dispositions remain typed and never become
ordinary failure or provider degradation. No T8 policy, signal-site wiring,
provider threshold/probe/fallback/scalar/return policy, second scheduler,
second admission authority, second journal/store, family lease, or speculative
network check.

### RW/NBF-03 only after NBF-02

Wire exactly one physical admission owner for native, direct/nested OMP,
babysitter, and chain origins. Nested OMP has one hit in `run_omp_step` and no
outer `_impl.py` hit. Every production `run_step_with_worker` enters
`dispatch_with_admission`. `wbc_dispatch=None` constructs the canonical adapter
or rejects before legacy launch. WBC intent precedes admission; WBC start follows
reservation, derived receipt, and `not_started`. Scheduling/no-launch has no WBC
start/failure/completion. Accepted dispositions preserve ID and show
record-before-signal then one terminal projection. Authorized children use new
linked IDs. Door removal, duplicate outer admission, chain/no-WBC bypass,
WBC-before-admission, raw launch access, or a second launch must fail.

The AST authority checker must detect raw authority calls and aliases,
chain-local preflight/direct spawn, no-WBC delegation, WBC-before-admission,
nested double gating, and raw launch access. All three door files must be free of
raw refresh/require calls; no `MEGAPLAN_MOCK_WORKERS=1`; no `/workspace/.cloud-hot-env`
mutation; no T8 policy beyond the frozen generic interface/traces.

## Exact validation requirements

Use a fresh evidence directory such as
`/tmp/oracle-nbf02-nbf03-luna-v3-0830/`. Every command below is mandatory;
capture literal command, cwd, UTC start/end, exit, complete stdout/stderr, and
SHA-256 for both streams. Collection failure due absent modules is not an
acceptable v3 blocker: create all missing tasklist-required tests and exercise
real behavior. Run the exact frozen commands in serial task order:

### Exact frozen NBF-02 command

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

### Exact frozen NBF-03 command

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

Run the complete frozen Batch-2 checkpoint matrix: all NBF-02/NBF-03 focused
modules; all 42 existing runtime-attestation tests; native, direct/nested OMP,
babysitter, chain, no-WBC, authorized-child, WBC ordering, logical-ID
cardinality, typed disposition, scheduling/no-launch, reconciliation, and
`ox-alpha`/native-liveness probes. Run every required missing test file, not a
partial source probe. Run `python -m py_compile` over every changed Python file
and `git diff --check`. Do not run an unrelated broad suite unless the frozen
contract explicitly requires it.

The four babysitter/WBC failures previously observed must be investigated. If
candidate-caused, fix them. If genuinely baseline/pre-existing, prove that with
the source checkpoint and isolated exact evidence while still satisfying every
frozen acceptance criterion; do not silently waive them.

## Evidence deliverables

After implementation and validation, write exactly:

- `.oracle/findings/execution-nbf02-nbf03-luna-v3.md`
- `.oracle/receipts/execution-nbf02-nbf03-luna-v3.md`

Bind every owned path and full SHA-256, current final HEAD and source/base,
frozen tasklist/North Star and prerequisite hashes, Batch-1 checkpoint, all
prior artifact identities and provenance defects, the exact explicit-high
launcher invocation, complete command/transcript manifests and stream digests,
test counts and failures, checker/raw scan, compile/diff-check, final tracked
production/worktree diff, and the two artifact hashes. Classify pre-existing
blockers honestly. Do not claim an Oracle verdict or self-review. No other file
or history mutation is permitted.
