# GPT-5.6 Luna/high execution brief — NBF-01 Batch 1 rework attempt 4

## Role and objective

You are the sole Normal executor for the fourth NBF-01 rework pass. Run as
**GPT-5.6 Luna with high reasoning effort** in:

`/Users/peteromalley/Documents/Arnold-oracle-nbf`

Implement the frozen supplemental packet `.oracle/rework/batch-1-attempt-4.md`
exactly, building on the existing dirty candidate and preserving all user,
orchestrator, and earlier accepted changes. Execute as one writer in strict
serial order:

```text
RW4-01 → RW4-02 → RW4-03 → RW4-04 → RW4-05 → RW4-06
```

RW4-01 is a hard blocker. Do not begin RW4-02 or any later work until the
coherent recomputed changed-precondition forgery rejects at decode, append, and
consume while a valid reason-specific authoritative-reader event appends and
consumes exactly once. Do not parallelize repository writers or allow another
agent to edit these files concurrently.

This is implementation and executor validation only. You are not the Oracle and
must not issue `PASS_BATCH_1` or `ACCEPTED_ISSUES`.

## Leaf-execution boundary — do not start another harness

This task is already a leaf execution step inside the active, frozen
Megado/Oracle run. Do **not** initialize, invoke, nest, or diagnose another
Megaplan or Megado harness, and do not rerun preparation, planning, critique,
gate, revision, or tasklist generation. The repository `AGENTS.md` Megaplan
front-door applies when starting a new Megaplan run; that requirement is already
satisfied and superseded for this delegated leaf by the frozen tasklist, the
attempt-4 supplemental packet, and the orchestrator's explicit delegation.
Start directly with identity verification, full packet/source/test reading, and
then the serial implementation below.

## Immutable inputs

- Source / merge-base:
  `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Current branch: `megado-nbf-guard-0826`
- Current HEAD: `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- Frozen tasklist `.oracle/tasklist.md` SHA-256:
  `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- North Star `.oracle/northstar.md` SHA-256:
  `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Attempt-4 packet `.oracle/rework/batch-1-attempt-4.md` SHA-256:
  `4df7024a285e3d0c373278dbd72aed98a0d5af26b05f1f880cf64e9f20a2d534`
- Attempt-4 triage receipt
  `.oracle/receipts/rework-triage-batch-1-attempt-4-grok.md` SHA-256:
  `3d20f7bc585e5b5495a38b7a2a26caf1050c90f6dc14f719a95d3203516cfa2c`
- Attempt-3 starting tracked-production diff SHA-256:
  `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8`
- Prior Grok verdict `.oracle/checkins/batch-1-rework3-grok.md` SHA-256:
  `4bd93c1d24e55c1860add92abbce5c44c979c2d0b83dd63b1ceb798db783af02`
- Prior Grok receipt `.oracle/receipts/oracle-nbf01-rework3-grok.md`
  SHA-256:
  `95ec60c0f981217500b9922ac86ffb95d6c60036d39ea32d07761731716c3a30`

Before editing, verify every identity above, resolve branch/HEAD/merge-base, and
reproduce the starting production digest with the packet's exact command. If an
identity differs, stop with a concrete blocker; do not normalize or rewrite an
artifact. The starting digest is historical input, not the post-fix target.

## Mandatory reading and inspection before editing

Read completely:

- `.oracle/northstar.md`, `.oracle/agent_goal.md`, frozen
  `.oracle/tasklist.md`, and settled `.oracle/plan.md`;
- `.oracle/rework/batch-1-attempt-4.md` and its triage receipt;
- the bound attempt-3 Grok verdict and receipt;
- attempt-3 Luna executor finding/receipt and Luna review check-in/receipt;
- prior rework packets/check-ins needed to identify preserved behavior.

Then inspect the actual current source and every owned test body before making
changes:

- `arnold_pipelines/megaplan/incident/{__init__,schema,ledger,disposition}.py`
- `arnold_pipelines/megaplan/orchestration/phase_result.py`
- `arnold_pipelines/megaplan/orchestration/phase_result_classify.py`
- the eight new NBF test modules;
- unchanged legacy `tests/arnold_pipelines/megaplan/test_incident_ledger.py`.

Treat the packet as canonical when this brief summarizes it. Implement the
smallest solution that satisfies its exact named criteria. Use `apply_patch`
for every repository file edit. Do not use shell redirection, `cat >`, Python
file-writing scripts, or wholesale generated rewrites. Preserve unrelated dirty
tree changes and never stash, reset, clean, or overwrite them.

## Global scope and preservation

Preserve every prior-MET behavior listed in the packet, including:

- one `_IncidentEventJournal`, one sequence-sidecar `fcntl.flock`, and one
  `_locked` / `_append_nbf_locked` mutation door;
- persisted receipt-bound accepted-launch markers with no terminal
  self-authorization;
- C03–C08, C10, C12, C14–C18, C22, C25, C26 shape, C27, C29 order,
  C30/C31 matching/rekey-at-one, C35–C38, C41, CP04, CP05, CP09, CP10;
- positive OOM and legal unknown-death append paths;
- `worker_disposition` + `success_payload` source rejection;
- keyed replay with no `latest_stream_key` mutation fallback;
- real composite fresh replay and existing `_emit_locked` pre-append failure;
- CLI 0/2/3/4/5 including expired and already-consumed replay;
- expiry-after-consume rejection;
- deleted `reserve_provider_route_child_with_receipt` convenience surface;
- real two-process reservation contention and corrected custody/history.

Do not reopen or implement any excluded work: C36–C38, C01 through overweight
`PhaseResult.from_dict`, C40 cache-mismatch expansion, T8 policy, admission or
scheduler callers, physical doors, launch adapters, signal wiring, fallback
policy, family leases, rotators, a second journal/store/projection, prepare/
commit, the two missing broad-suite modules, custody, historical evidence,
status/agent-goal changes, main merge, or Batch 2.

## Serial execution contract

### RW4-01 — authoritative producer and coherent-forgery closure

Own only the packet-listed producer/handle seams in `incident/schema.py`,
`append_changed_precondition` / `consume_changed_precondition` in
`incident/ledger.py`, and the relevant producer/one-consume tests.

Replace the caller-dictionary authority path with the smallest typed source
handle and closed reason-specific reader for each of the seven allowlisted
reasons. The reader—not caller-supplied serialized content—must bind producer
kind/version, reason, subject, source version, persisted evidence and digest,
canonical before/after values and content IDs, and provider-key transition.
Keep generic `ChangedPrecondition.produce` and `produce_changed_precondition`
closed. Do not add a signature service, registry framework, second authority
store, or generic escape hatch.

Validate independently at:

1. `ChangedPrecondition.from_dict` / decode;
2. locked `append_changed_precondition`; and
3. locked `consume_changed_precondition`.

Retarget `test_coherent_forged_provider_transition_with_recomputed_ids_rejects`
to rebuild every serializable hash and ID. It must fail at all three doors.
Prove the valid reason-specific reader path appends and consumes once, then
rejects a second consume. Run the packet's RW4-01 exact test command. Do not
advance until all RW4-01 acceptance criteria and C22 preservation pass.

### RW4-02 — C02/C13 four-door payload and identity matrix

Only after RW4-01 passes, strengthen the packet-owned `DispatchOutcome`, typed
disposition/death identity, validation, append, and existing named test seams.
Exercise the complete illegal payload/identity matrix through direct
construction, `from_dict`, `validate_nbf_event`, and the real locked public
append door. Include `worker_disposition` + `success_payload` in the existing
named matrix. Reject bare/arbitrary worker identity and missing/fabricated
worker, observed-death, and non-worker identities; retain all legal positives.
Do not route C01 through `PhaseResult.from_dict` and do not reopen C14.

Run the exact RW4-02 test command and prove the strengthened named tests would
fail on the unmodified attempt-3 hole.

### RW4-03 — non-latest keyed proof and canonical probe-lease binding

After RW4-02 passes, own the packet-listed keyed reducer, probe lease/result,
recovery consume, child reservation, and provider projection tests. Retarget the
required existing names to a **non-latest** applicable stream and assert numeric
state for all affected and unaffected keys. Prove success resets only its key;
ordinary failure/disposition break only their key without degradation; missing
key mutates none; restart/replay preserves isolation.

Require every accepted probe result to match an existing unexpired lease and
parent/phase/route/provider context. Cover passed, failed, absent, expired,
mismatched, replayed, and consumed probe/recovery paths. Valid recovery consumes
once inside the single composite child append and preserves the keyed streak.
Do not restore latest-stream fallback or implement T8.

Run the exact full provider projection test command and all packet-required
non-latest/recovery named tests before advancing.

### RW4-04 — distinct terminal race and post-append crash/reopen proof

After RW4-03 passes, retarget
`test_two_process_terminal_linkage_is_atomic` to two real OS processes using
distinct terminal IDs and conflicting kinds; exactly one wins and fresh replay
is valid. Preserve same-ID idempotency under a separate non-required test.

Retain the real `_emit_locked` pre-append failure proof. Add the smallest test
injection after the composite is durably appended but before receipt return/
derivation. After reopening a fresh ledger, prove the committed composite
projects exactly once and derives a byte-identical receipt; pre-append failure
still exposes neither transition nor receipt. Do not add prepare/commit or any
second persistence surface.

Run both exact RW4-04 transaction and provider replay/receipt commands.

### RW4-05 — complete durable confirmation equality matrix

After RW4-04 passes, require and compare every frozen confirmation identity,
timing, and evidence field at the existing schema/ledger doors: victim PID,
process-start identity, progress identity, supervisor incarnation, cause,
evidence digest, TTL/expiry, scan interval/separation, and required policy/
schema version. Strengthen the existing named test with every single-field
mismatch and omission. Preserve restart, replacement, expiration, original
expiry, expiry-after-consume rejection, and the locked one-consumer race.

C41 is regression only: rerun real CLI 0/2/3/4/5 behavior without redesign or
signalling. Run the packet's exact RW4-05 test command.

### RW4-06 — immutable stable-tree executor evidence

Only after RW4-01 through RW4-05 are complete and the source/test tree is stable,
run the full validation contract below and create exactly these new artifacts:

- `.oracle/findings/execution-nbf01-rework4-luna.md`
- `.oracle/receipts/execution-nbf01-rework4-luna.md`

Use `apply_patch` for both. Label them executor evidence, not Oracle review.
Bind exact branch, HEAD, source/merge-base, frozen tasklist, North Star, packet,
triage receipt, starting attempt-3 digest, and final attempt-4 production diff.
Inventory every modified tracked and owned untracked production/test file with
both `git hash-object` and full SHA-256—explicitly including
`incident/disposition.py` and all eight new NBF test modules.

For every command record exact argv, cwd, exit status, complete stdout/stderr or
an immutable isolated transcript path, and full 64-hex SHA-256 for both streams.
Record the full megaplan-directory sweep verbatim, including the known
pre-existing missing-module collection blocker if it recurs; do not summarize
or repair it. Record every unresolved issue honestly. Historical evidence must
remain historical and untouched.

## Required validation

Run fresh packet-specific tests after each serial stage, then run all of the
following against the stable candidate. Add the strongest deterministic
in-scope behavioral/adversarial probes needed to prove a criterion; do not rely
on pass-count growth or test names.

### RW4-01 coherent-forgery / authoritative-reader gate

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py \
  -k "precondition or consumed_change or forged or producer or authoritative"
```

### RW4-02 four-door payload/identity matrix

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_terminal_outcomes.py
```

### RW4-03 provider/recovery matrix

```bash
pytest -q tests/arnold_pipelines/megaplan/test_provider_route_projection.py
```

### RW4-04 transaction/concurrency/crash/replay proofs

```bash
pytest -q tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py \
  -k "two_process or torn or crash or contention or post_append or receipt"

pytest -q tests/arnold_pipelines/megaplan/test_provider_route_projection.py \
  -k "replay or receipt"
```

### RW4-05 confirmation and CLI regressions

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_supervision_confirmation.py \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py
```

Also invoke direct independent CLI subprocesses for status 0; malformed and
schema-invalid 2; append/lock 3; invalid ledger 4; and missing, expired, and
distinct already-consumed replay 5. Record exact stdin, ledger roots, argv,
streams, exits, and hashes; status 0 must emit one JSON acknowledgment and never
signal.

### Frozen focused suite

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_provider_route_projection.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py \
  tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py \
  tests/arnold_pipelines/megaplan/test_terminal_outcomes.py \
  tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py \
  tests/arnold_pipelines/megaplan/test_supervision_confirmation.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger.py
```

### Frozen legacy suite

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_incident_projection.py \
  tests/arnold_pipelines/megaplan/test_incident_summaries.py \
  tests/arnold_pipelines/megaplan/test_incident_bridge.py \
  tests/arnold_pipelines/megaplan/test_phase_result_classify.py
```

### Broad evidence sweep

```bash
pytest -q tests/arnold_pipelines/megaplan
```

Capture its complete output even if the pre-existing missing
`arnold.agent.costing.model_resource_capabilities` and
`tools.environments.singularity` modules stop collection. Do not fix or waive
them; classify only as the packet directs.

### Compile and whitespace gates

```bash
python -m py_compile \
  arnold_pipelines/megaplan/orchestration/phase_result.py \
  arnold_pipelines/megaplan/orchestration/phase_result_classify.py \
  arnold_pipelines/megaplan/incident/schema.py \
  arnold_pipelines/megaplan/incident/ledger.py \
  arnold_pipelines/megaplan/incident/disposition.py

git diff --check
```

In addition, explicitly rerun the strongest in-scope adversaries: coherent
recomputed forgery at all three doors, valid source reader one-consume, real
two-process distinct terminal race, pre- and post-append composite failures with
fresh replay, non-latest provider isolation across restart, lease-bound recovery
negative matrix, complete confirmation mismatch/omission matrix, and concurrent
confirmation consumption.

## Completion and stop conditions

If RW4-01 cannot be made behaviorally correct within the frozen seam, stop and
write a concrete blocker; do not proceed to later tasks or widen scope. If a
later test exposes an in-scope regression, diagnose and fix it in the owning
serial task before continuing. If an excluded concern is the only blocker,
record it and stop rather than reopening the exclusion.

On successful execution, publish only the two immutable attempt-4 executor
artifacts plus in-scope source/test edits. Report changed files, exact results,
digests, and unresolved issues. Do not commission any reviewer. Do not write a
Luna review check-in/receipt. Do not issue an Oracle verdict. Do not stage,
commit, push, merge, rebase, reset, clean, start Batch 2, mutate the frozen
tasklist/plan/North Star/custody/status/agent goal, or rewrite any historical
artifact. Stop after the executor finding and receipt are complete and stable.

## Complete immutable North Star (verbatim)

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
