# Luna execution brief — NBF-01 Batch 1 rework 6

## Leaf execution and authority

You are GPT-5.6 Luna at high reasoning, the sole Normal executor for the
sealed attempt-6 packet. This is a **LEAF execution inside an already-running
frozen Megado pipeline**. Do not invoke Megaplan, Megado, a nested harness, or
any other orchestrator. Do not create plans, dispatch a reviewer, self-review,
issue a verdict, commit, stage, push, merge, rebase, reset, clean, or start
Batch 2. Historical/frozen/status/goal/custody artifacts must remain untouched.

Execute exactly one task, RW6-01, with one writer:

```text
RW6-01 — C02/C13 complete six-kind/four-door payload and typed-identity matrix
```

Use `apply_patch` for edits. The default and expected change is test-only.
Change production only if a correctly shaped behavioral case concretely proves
a real validator defect; document the exact proof and keep any production fix
minimal and within the owned seams. Do not expand scope merely because a
production file is nearby.

Create exactly these executor artifacts after implementation and validation:

- `.oracle/findings/execution-nbf01-rework6-luna.md`
- `.oracle/receipts/execution-nbf01-rework6-luna.md`

These are executor evidence, not an Oracle review. Do not place
`PASS_BATCH_1`/`ACCEPTED_ISSUES` in them.

## Immutable bindings

Candidate repository:
`/Users/peteromalley/Documents/Arnold-oracle-nbf`

- branch: `megado-nbf-guard-0826`
- bound planning HEAD: `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- source/merge-base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- frozen tasklist SHA-256:
  `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- North Star SHA-256:
  `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- attempt-5 production baseline SHA-256:
  `7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411`

Sealed attempt-6 inputs:

- `.oracle/rework/batch-1-attempt-6.md` SHA-256
  `b776d6cc5b090fb4cbb278ec5fff265cb5cf92896c22c0fe0fed066713609b83`
- `.oracle/receipts/rework-triage-batch-1-attempt-6-grok.md` SHA-256
  `88a0c2b76663cf63a32129296a74a610d01a4bedf66aef04dbaec570979bbcc8`

Attempt-5 accepted-issues gate artifacts, all historical and immutable:

- Luna check-in SHA-256
  `670dbde42ab483ac36e08f2d1222d83b80a42248c6036d47cbeb77459649a8a6`
- Luna receipt SHA-256
  `4d96b1922cb6dca3b79c5d414092cb0407f49c32c95236e54fb08530994cc143`
- Grok check-in SHA-256
  `49c7bb1e94f828536be0800372d06aca55388667730870e1d5ee7e0efdf42aa6`
- Grok receipt SHA-256
  `537225951f608611b290c413a8e133a1a897f911c3ee49be9f13ea3bd03670ef`

Also read `.oracle/agent_goal.md`, `.oracle/custody.md`, settled plan v8,
attempt-5 packet/triage/execution/finding/receipt, and all prior evidence. Do
not rewrite them. Before editing, capture actual HEAD, branch, merge-base,
worktree status, input hash matches, and the attempt-5 production diff match.
At completion, capture the new candidate HEAD and post-fix production diff;
the baseline is not the target.

## Scope and preserved behavior

Own only RW6-01's existing seams:

- `arnold_pipelines/megaplan/orchestration/phase_result.py`: `DispatchOutcome`
  construction, `from_dict`, and six-kind decode paths;
- `arnold_pipelines/megaplan/incident/schema.py`: worker disposition,
  observed process death, non-worker lifecycle disposition,
  `_typed_worker_identity`, and `validate_nbf_event` payload/identity branches;
- `arnold_pipelines/megaplan/incident/ledger.py`: public
  `append_terminal_outcome`, public `append_disposition`, and only the locked
  append validation door needed by these records;
- existing named tests in `test_scheduling_conditions.py`,
  `test_worker_disposition.py`, and `test_terminal_outcomes.py`.

Default to test-only changes. Do not edit the unchanged legacy
`test_incident_ledger.py` unless a frozen must-criterion cannot live in the
eight owned NBF modules. Do not add a ninth test module.

Preserve all prior-MET behavior, especially RW5-01/C19–C21 coherent forgery
rejection at decode/validate/private append/projection/reserve and legitimate
reader replay/consume-once, RW5-03/C39 confirmation evidence equality, one
incident journal and sequence-sidecar lock, typed worker dispositions,
no-launch/unresolved distinction, legal OOM/unknown-death/non-worker paths,
keyed provider/recovery behavior, race/crash/replay proofs, C41 CLI statuses
0/2/3/4/5, and all C03–C08/C12/C14 semantics.

Prohibited: C19–C21 or C39 reopeners; C36–C38; C01 overweight
`PhaseResult.from_dict`; C40 cache matrix; T8 policy; admission/scheduler/
physical doors/launch/signal/fallback/family leases/rotators; second journal,
store, projection, policy owner, or prepare/commit framework; broad missing
module repair; custody/status/goal/tasklist/plan/North Star edits; historical
rewrite; commit/merge/Batch 2; and any Oracle or review verdict.

## RW6-01 exact behavioral outcome

The surviving defect is proof quality, not an observed source validator bypass.
The current validators reject correctly shaped illegal records, but prior named
tests feed incomplete dictionaries and merely assert `ValueError`, so they
fail before the intended payload-family or identity boundary. Replace that
ceremony with correctly shaped records and exact error-family assertions.

### Six-kind payload matrix

Use `legal.to_dict()` with every `DispatchOutcome._FIELDS` key populated and
unused exclusive payloads explicitly `None`; mutate exactly one incompatible
payload family. Exercise all six cases through all four doors:

1. direct `DispatchOutcome` construction;
2. `DispatchOutcome.from_dict` decode;
3. `validate_nbf_event` using a complete terminal event where applicable; and
4. real public locked `append_terminal_outcome` and public
   `append_disposition` (private `_append_nbf` is not a substitute).

Required illegal combinations and intended error families:

```text
no_launch                 + success_payload
unresolved_launch         + complete structured provider_evidence
success                   + terminal_failure
ordinary_terminal_failure + success_payload
provider_exhausted        + disposition_id, retaining complete provider_evidence
worker_disposition        + success_payload
```

Assert payload-family messages such as `no_launch cannot carry`,
`success cannot carry`, `ordinary failure cannot carry`, `provider exhaustion
cannot carry`, or `worker disposition cannot carry`; do not accept generic
`missing DispatchOutcome fields`, unknown-field, or unrelated malformed-record
errors. For scheduling kinds at terminal validation, assert the intended
`invalid terminal outcome kind`; for legal scheduling records at public
terminal append, retain `scheduling outcomes have no worker terminal event`.

### Typed identity matrix

At each applicable door, cover missing (`None`), fabricated non-mapping/wrong
types, bare strings, wrong schema version, incomplete mapping, non-positive PID,
and mismatched typed worker identity (`host`/`pid`/`boot_id`) for worker
identity. Cover observed-death missing/fabricated subject, cause, killer,
victim identity evidence, and wrong version; preserve only legal
`worker|external_process` subjects and `observed_dead_unknown|cgroup_oom`
causes. Cover non-worker missing/fabricated/empty lifecycle identity, wrong
subject, worker causes, and wrong version. Every negative must reach the
identity validator, not incidental missing `DispatchOutcome` fields.

Keep legal positives: worker disposition, observed unknown death, non-worker
lifecycle shutdown, matching success/ordinary/provider terminals, positive
cgroup OOM, and unknown death.

Strengthen existing named tests in place, including:

- `test_dispatch_outcome_incompatible_payload_matrix`;
- `test_incompatible_matrix_rejects_at_public_terminal_append`;
- `test_typed_identity_matrix_rejects_missing_and_fabricated_worker_at_all_doors`;
- `test_worker_disposition_rejects_success_payload_at_append`; and
- the existing observed/non-worker identity and terminal append tests.

Tests must fail against the attempt-5 candidate for the named gap, be
deterministic, and assert intended rejection categories. Change production only
if a complete case demonstrates a real validator defect; do not “improve”
validators speculatively.

## Exact validation commands and evidence

Use a fresh isolated evidence/transcript directory, e.g.
`/tmp/oracle-nbf01-rework6-luna/`; do not reuse prior attempt roots. Every
command must record literal argv, cwd, UTC start/end, exit status, complete
stdout/stderr or immutable transcript path, and full SHA-256 digests for each
stream and structured transcript. Empty streams must use the full digest
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

Run from `/Users/peteromalley/Documents/Arnold-oracle-nbf`:

```bash
python -m pytest -q tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py
python -m pytest -q tests/arnold_pipelines/megaplan/test_worker_disposition.py -k "incompatible_matrix or observed_and_non_worker"
python -m pytest -q tests/arnold_pipelines/megaplan/test_terminal_outcomes.py -k "append or disposition or worker"
python -m pytest -q tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py tests/arnold_pipelines/megaplan/test_provider_route_projection.py tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_supervision_confirmation.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_incident_ledger.py
python -m pytest -q tests/arnold_pipelines/megaplan/test_incident_ledger.py
python -m pytest -q tests/arnold_pipelines/megaplan/test_incident_projection.py tests/arnold_pipelines/megaplan/test_incident_summaries.py tests/arnold_pipelines/megaplan/test_incident_bridge.py tests/arnold_pipelines/megaplan/test_phase_result_classify.py
python -m py_compile arnold_pipelines/megaplan/incident/__init__.py arnold_pipelines/megaplan/incident/ledger.py arnold_pipelines/megaplan/incident/schema.py arnold_pipelines/megaplan/incident/disposition.py arnold_pipelines/megaplan/orchestration/phase_result.py arnold_pipelines/megaplan/orchestration/phase_result_classify.py
git diff --check
```

Do **not** rerun `python -m pytest -q tests/arnold_pipelines/megaplan`; the
attempt-6 packet deliberately excludes the broad suite and already has an
authoritative pre-existing collection-blocker result. Do not repair or reclassify
its missing modules. Do not rerun C41 CLI unless specifically needed as a
regression; if rerun, use the existing real subprocess command and record all
0/2/3/4/5 cases without redesign.

After tests, record final identity and production diff exactly against source
for the five tracked production paths plus `incident/disposition.py`:

```bash
git rev-parse HEAD
git rev-parse --abbrev-ref HEAD
git merge-base HEAD origin/main
git diff origin/main -- arnold_pipelines/megaplan/incident/__init__.py arnold_pipelines/megaplan/incident/ledger.py arnold_pipelines/megaplan/incident/schema.py arnold_pipelines/megaplan/incident/disposition.py arnold_pipelines/megaplan/orchestration/phase_result.py arnold_pipelines/megaplan/orchestration/phase_result_classify.py
```

Inventory every modified tracked file and every owned untracked production/test
file with `git hash-object` and full SHA-256. Explicitly prove the unchanged
legacy ledger test identity and that no later-batch file entered the diff.

## Finding and receipt contract

The finding must state RW6-01 outcome, whether production remained unchanged or
why a concrete defect required a minimal production patch, exact files/symbols,
preserved behavior, candidate HEAD/source/tasklist/North Star identities,
attempt-6 packet/triage hashes, baseline and final production diff, all exact
commands/results, and honest failures. It is executor evidence, not a verdict.

The receipt must include model `codex:gpt-5.6-luna`, high reasoning, invocation
metadata, UTC timestamps, cwd, exact argv, exits, complete transcript paths,
stdout/stderr/transcript SHA-256s, per-file hash/object inventory, and final
production diff digest. State explicitly that no self-review, reviewer,
commit, nested harness, broad rerun, Batch 2, or frozen/history mutation
occurred.

## North Star — Arnold self-healing supervision (verbatim)

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

## Megado delegation mandate (verbatim)

> DELEGATION MANDATE — You are a manager and validator of the normal execution pool, NOT a worker. Delegate as much as possible to the task's selected normal model: DeepSeek V4 Flash or GPT-5.6 Luna. Flash invocation: `omp -p @<brief>.md --model deepseek-v4-flash --cwd <worktree> --no-session --auto-approve --max-time=1800`; Luna invocation: `launch_hermes_agent.py --model="codex:gpt-5.6-luna" --query-file=<brief> --project-dir=<worktree>` (research-only briefs use read/search tools). Dispatch research, execution, and critique briefs to the selected model — critique passes optimize for elegance: KISS, YAGNI, cut scope that isn't pulling its weight; flag overengineering, not just bugs. Your job is to direct, then validate: read delegated output against the acceptance criteria; do work yourself only when delegation is impossible — the selected normal model already failed at it, or the piece is too small / too tightly coupled to your own reasoning to hand off. If you catch yourself implementing or researching directly, stop and ask whether a normal-pool brief would cover it. It almost always would.
