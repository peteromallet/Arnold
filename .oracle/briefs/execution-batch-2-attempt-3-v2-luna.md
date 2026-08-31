# Batch-2 rework attempt-3 v2 — Luna leaf-continuation execution brief

## Execution boundary

This is a fresh **LEAF CONTINUATION** after the attempt-3 wrapper timeout. It
is executor evidence work only, not an Oracle review or verdict. One GPT-5.6
Luna/high executor may work directly in the existing dirty repository. Do not
invoke Megaplan, Megado, `launch_hermes_agent.py`, OMP, another launcher, any
subagent, delegation, reviewer, or model from inside this execution. The
operator may launch this brief once with the command shown below; the child
must perform all implementation and validation itself with local tools.

Use `apply_patch` for source/test edits. Do not commit, stage, push, merge,
rewrite history, start Batch 3, or mutate `.oracle/tasklist.md`,
`.oracle/northstar.md`, `.oracle/plan.md`, `.oracle/agent_goal.md`,
`.oracle/custody.md`, `.oracle/status.md`, or prior artifacts. Preserve valid
prior work, but audit the partial tree before relying on it. Do not self-review
or issue an Oracle acceptance token.

Operator launch recipe (the executor itself must not run this or any nested
launcher):

```bash
PYENV_VERSION=3.11.11 python /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py --model="codex:gpt-5.6-luna:high" --query-file=/Users/peteromalley/Documents/Arnold-oracle-nbf/.oracle/briefs/execution-batch-2-attempt-3-v2-luna.md --project-dir=/Users/peteromalley/Documents/Arnold-oracle-nbf --timeout=7200
```

The prior wrapper launch is invalid executor evidence because it delegated to
OMP and timed out. Its append-only receipt is
`.oracle/receipts/execution-batch-2-attempt-3-timeout.md`, SHA
`678e86f3a1f18e304507249b8175195374375da4ebd46610de30761b421ba3df`.

## Immutable bindings and current dirty-tree checkpoint

| Binding | Identity |
|---|---|
| Repository / branch | `/Users/peteromalley/Documents/Arnold-oracle-nbf` / `megado-nbf-guard-0826` |
| Current HEAD | `2297fb330cdb375b4e5bd048f0d5c37d0e06db30` |
| Source/base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` |
| Candidate implementation / parent / tree | `5da26ec5be4d13559948fe4256a114ad7626482b` / `19deab5bb407273e7e82d40a66fc06d17af93ad4` / `e3d0376482154c4f95d2ec5809d630c4a0c32e69` |
| Candidate canonical production+focused diff | `5586c1861dce44334c3991e997bdc8b90b82d25d2ed8f28bb558b42aae499fd0` |
| Current partial all source/test diff vs candidate | `acb8ca400c1b0874cea1f030630ba2f186f16cd22ceedfc2a33fe7ab592a19ec` |
| Current partial production-only diff | `f636e53dfdf83ab7bac8eeff80243822ce8b4bef43fbb445ce6713555c122549` |
| Attempt-3 timeout receipt | `678e86f3a1f18e304507249b8175195374375da4ebd46610de30761b421ba3df` |
| Attempt-3 packet / triage receipt / prior execution brief | `ff19d01688124ef3b77dba28ab24c28da71b395838c645a3a34f7b580c24c1e2` / `5d08b2b2f31a8a85f602c449311bd05a775711f298db963a8bc611f81abfab38` / `7ef4af5b06937e5f32e3a09aeb96084f2f79864dbc9926166799d7b7cf90c516` |
| Attempt-2 packet / triage receipt / execution brief | `cba6d2236a7bae5bd12f38f38ad775ca800ed19dc3ba79c14ac6e00d3d78ff83` / `4d1d9bde6740897e84e99ac34d050055eb7f7c12a4823f65fe2cb7e04e007ed3` / `7d7a807309dac3d2704ee05f66f6f597feff7d63a1b1e46d2b7b4d8898da0c87` |
| Attempt-2 finding / receipt | `f1e3b9521bd15e932a87be921325af901c78e9dde06fd2729d7bf502c722e7d4` / `ea9723a96c8e6d7e9cb7b68a3352d6dc34b03b81dfd47011d0599db6a7844425` |
| Attempt-1 packet / triage receipt / finding / receipt | `4ac1c007cdef27f223841ea4e4cb16aca5d4c23a4d3292983cfb4e8ba8469615` / `caaffc753a899b23c773a8551c67dadbf15edb2f88934dbb22595901390e41aa` / `0bbd43a08d1e25d583ed7267ebe2da140b950d4ade46cbc3185e22242d4048d4` / `b0ebecd1395c5f93015834e70629159f686969d5aef13eb2e0aecb7b5026a224` |
| Policy override | `.oracle/receipts/model-policy-override-batch2-sol.md` / `6ab820892edaca0bd1b60bbd8a4934904b2f0d3a7704aaa77477779c6218085b` |
| Frozen tasklist | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| Frozen North Star | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| Frozen plan | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| Frozen agent goal | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` |
| Frozen custody | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |

The current partial source/test diff has exactly these 18 paths and no
untracked source/test paths. Audit each path for necessity before editing;
restore accidental expansion and do not erase legitimate earlier fixes:

```text
arnold_pipelines/megaplan/auto.py
arnold_pipelines/megaplan/cloud/babysitter/launch.py
arnold_pipelines/megaplan/cloud/controlled_final_launch.py
arnold_pipelines/megaplan/cloud/worker_dispatch.py
arnold_pipelines/megaplan/incident/ledger.py
arnold_pipelines/megaplan/incident/schema.py
arnold_pipelines/megaplan/workers/_impl.py
arnold_pipelines/megaplan/workers/omp.py
scripts/check_worker_admission_authority.py
tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py
tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py
tests/cloud/dispatch_test_helpers.py
tests/cloud/test_controlled_final_launch.py
tests/cloud/test_dispatch_reconciliation.py
tests/cloud/test_dispatch_with_admission.py
tests/cloud/test_worker_admission_authority.py
tests/cloud/test_worker_dispatch_admission.py
tests/cloud/test_worker_dispatch_spy.py
```

## North Star — canonical byte-for-byte block

The bytes between the markers, excluding marker lines and the Markdown fence,
are the complete `.oracle/northstar.md`, including its original final newline.
Extract and verify SHA-256 equals
`d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` before
continuing.

<!-- NORTH_STAR_SHA256_BEGIN -->
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
<!-- NORTH_STAR_SHA256_END -->

## Strict serial execution

Execute exactly this order, one writer only:

1. `R3-NATIVE-001` — native proof authenticity and recomputation.
2. `R3-TERM-002` — production-door typed terminal transport.
3. `R3-LIFE-003` — stale-marker lifecycle reconciliation.
4. `R3-AUTH-004` — checker adversarial authority completeness.

All four are Normal/Luna. Do not escalate to Sol or `[XHARD]`; do not reopen
passed `B2-RTB-001`, `B2-CHILD-005`, `B2-OMP-006`, or `B2-SCHED-008`. Keep
changes minimal/KISS and do not implement T8/provider policy.

### R3-NATIVE-001

Use the actual native construction seam and authoritative route membership.
Recompute and bind proof content, generation, identity, registry, observation,
and digest. Wrong, stale, forged, missing, or ambiguous proof must refuse before
reservation/client construction with zero construction cardinality. A
request-local resolver cannot replace authoritative recomputation.

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

### R3-TERM-002

Every physical native, OMP, and managed door must transport typed success,
ordinary failure, provider exhaustion, and worker disposition with complete
context. Record exactly once before projection. Bare failure-shaped results
never project as success; exceptions remain typed or context-rich unresolved.

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

### R3-LIFE-003

Reject selective earlier-ID reconciliation when accepted/entered markers exist.
Require receipt-bound physical evidence, global contradiction checks,
commit-before-projection, explicit state handling, at-most-once closure, and no
identical blind relaunch.

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

### R3-AUTH-004

The static checker must diagnose qualified/import/module/assignment/call aliases,
process construction, reversed multiline absent-WBC delegation, aliased raw
launch, and nested/double admission with contextual category diagnostics.

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

## Preservation and frozen validation commands

Run each command exactly, in this order, with a fresh external evidence root,
literal argv, UTC start/end, exit code, separate stdout/stderr byte counts and
SHA-256, pre/post porcelain, and changed-path hashes. Record failures rather
than erasing them.

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/cloud/test_runtime_attestation.py tests/cloud/test_worker_dispatch_admission.py tests/cloud/test_worker_dispatch_context.py
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/cloud/test_chain_admission.py tests/cloud/test_dispatch_with_admission.py tests/arnold_pipelines/megaplan/test_provider_route_projection.py tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/cloud/test_worker_dispatch_spy.py tests/cloud/test_chain_admission.py tests/cloud/test_dispatch_with_admission.py tests/arnold_pipelines/megaplan/test_common_worker_dispatch_wbc.py tests/workers/test_omp_adapter.py
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/cloud/test_dispatch_with_admission.py tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_phase_result_classify.py tests/arnold_pipelines/megaplan/test_plan_circuit.py
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/cloud/test_runtime_attestation.py tests/cloud/test_worker_dispatch_admission.py tests/cloud/test_dispatch_with_admission.py tests/cloud/test_chain_admission.py tests/cloud/test_worker_dispatch_context.py tests/cloud/test_dispatch_reconciliation.py tests/cloud/test_controlled_final_launch.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py tests/arnold_pipelines/megaplan/test_memory_headroom.py tests/arnold_pipelines/megaplan/test_worker_memory_gate.py tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_phase_result_classify.py tests/arnold_pipelines/megaplan/test_plan_circuit.py tests/workers/test_omp_adapter.py
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/cloud/test_worker_dispatch_spy.py tests/cloud/test_worker_admission_authority.py tests/cloud/test_chain_admission.py tests/cloud/test_babysitter_routing.py tests/cloud/test_babysitter_goal.py tests/arnold_pipelines/megaplan/test_common_worker_dispatch_wbc.py
git diff --quiet 19deab5bb407273e7e82d40a66fc06d17af93ad4 -- arnold_pipelines/megaplan/cloud/babysitter/routing.py skills/babysitter/scripts/render_babysitter_goal.py tests/cloud/test_babysitter_routing.py tests/cloud/test_babysitter_goal.py
shasum -a 256 arnold_pipelines/megaplan/cloud/babysitter/routing.py tests/cloud/test_babysitter_routing.py tests/cloud/test_babysitter_goal.py
PYTHONDONTWRITEBYTECODE=1 python -B scripts/check_worker_admission_authority.py --check
if rg -n 'refresh_runtime_launch_seed_for_worker_dispatch|require_configured_runtime_launch' arnold_pipelines/megaplan/workers/_impl.py arnold_pipelines/megaplan/workers/omp.py arnold_pipelines/megaplan/cloud/babysitter/launch.py; then exit 1; fi
PYTHONDONTWRITEBYTECODE=1 python -m compileall -q arnold_pipelines scripts tests
git diff --check
```

Also capture and bind:

```bash
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git rev-parse origin/main
git show -s --format='%H%n%P%n%T' 5da26ec5be4d13559948fe4256a114ad7626482b
git diff --binary --full-index 5da26ec5be4d13559948fe4256a114ad7626482b -- arnold_pipelines scripts tests | shasum -a 256
git diff --name-status 5da26ec5be4d13559948fe4256a114ad7626482b -- arnold_pipelines scripts tests
git ls-files --others --exclude-standard -- arnold_pipelines scripts tests
shasum -a 256 .oracle/tasklist.md .oracle/northstar.md .oracle/plan.md .oracle/agent_goal.md .oracle/custody.md
```

## Required outputs

After direct implementation and validation, create only these versioned
executor artifacts (not a verdict):

* `.oracle/findings/execution-batch-2-attempt-3-v2-luna.md`
* `.oracle/receipts/execution-batch-2-attempt-3-v2-luna.md`

Bind every changed path and hash, every command/result/transcript digest,
candidate/source/frozen identities, preservation and baseline evidence, and
the final production/source-test diff. Explicitly disclose any baseline or
environment blocker. Do not claim Oracle acceptance, do not review another
agent, and do not mutate frozen/history/status/goal/custody artifacts.
