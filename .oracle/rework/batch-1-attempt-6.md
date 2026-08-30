# Supplemental rework tasklist — NBF-01 / Batch 1, attempt 6

**Status:** supplemental rework only. NBF-01 remains **unaccepted**. Batch 2
is **prohibited** until a later Grok 4.6 Oracle gate returns `PASS_BATCH_1`.

This file does not mutate the frozen NBF tasklist, settled plan v8, North Star,
source base, custody, status, agent goal, or any prior brief, check-in,
finding, receipt, or rework packet. It is the smallest follow-on tasklist
after attempt 5 received `ACCEPTED_ISSUES`. Build on the existing dirty
candidate. Preserve every prior-MET primitive, the attempt-5 closures of
RW5-01/C19–C21 and RW5-03/C39, and the already-corrected custody document.

**Authority:** Grok 4.6 Oracle triage of the surviving attempt-5 issue in
`.oracle/checkins/batch-1-rework5-grok.md`, grounded in Luna review
`.oracle/checkins/batch-1-rework5-luna.md` and independent re-read plus
reproduction of the current candidate symbols and named tests. This turn is
triage only. It does not dispatch implementation or review.

**Identities (verified 2026-08-30T05:12:06Z):**

| Artifact | Identity |
| --- | --- |
| Repository | `/Users/peteromalley/Documents/Arnold-oracle-nbf` |
| Candidate branch | `megado-nbf-guard-0826` |
| Planning HEAD | `922241d0bdb3e993c3b554cc69f19948adef7bc3` |
| Immutable source base / merge-base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` |
| Frozen tasklist SHA-256 | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| Settled plan v8 SHA-256 | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| North Star SHA-256 | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| Custody SHA-256 | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| Agent goal SHA-256 | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` |
| Model-policy receipt | `0bb386bf6fff5f9a5197a57cea5789ee250231a163dfd01bbe828776e1cc5064` |
| Tasklist-freeze receipt | `583955c6996bcc18e8fe05d323c30f5f77e489cdd5a66ecb1783ac42c9d24a24` |
| Attempt-5 packet | `f2c2224d6b46eda303b1768a4a2e520fc08224eef9c93e506daa14ea3b2042d7` |
| Attempt-5 triage receipt | `dedf5870dc889b137484202290925482b4813a742414233dc83ecd7c5fa18b5a` |
| Attempt-5 execution brief | `78db1ef340df0dd87e8ab40ee31aa801eb163008ec7deb1247efdbefe343f13a` |
| Attempt-5 executor finding | `8cf68b20bb089f98639787c6aa1ad23d1ad24701843d802c4f79aa67eb77c197` |
| Attempt-5 executor receipt | `4acbb75c4bc9526265bf14438d194288bdf4aaf79cc63525f729830c6f93f160` |
| Attempt-5 Luna check-in | `670dbde42ab483ac36e08f2d1222d83b80a42248c6036d47cbeb77459649a8a6` |
| Attempt-5 Luna receipt | `4d96b1922cb6dca3b79c5d414092cb0407f49c32c95236e54fb08530994cc143` |
| Attempt-5 Grok check-in | `49c7bb1e94f828536be0800372d06aca55388667730870e1d5ee7e0efdf42aa6` |
| Attempt-5 Grok receipt | `537225951f608611b290c413a8e133a1a897f911c3ee49be9f13ea3bd03670ef` |
| Current owned production diff | `7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411` |
| Unchanged `test_incident_ledger.py` | SHA-256 `83e8464c9dfd289aa08de41d044257936072e29ae1d8648f52b84f441f79a195`; blob `44dc3adb87ad4dd077aed449c2f5ccc3526d8d93` |
| Oracle verdict on attempt 5 | `ACCEPTED_ISSUES` |

The attempt-5 production diff digest is the **reviewed attempt-5 identity**,
not a future target. Attempt-6 execution must measure and bind its own
post-fix tree. Do not rewrite attempt-5 artifacts when that digest changes.
Keep `7b46da5c…` separate from historical attempt-4 `aaaa86ba…` and earlier
digests.

Focused `123 passed` and legacy `78 passed` are observations, never
acceptance targets. Preserve historical evidence as historical: start-gate
52→61, unreproducible `4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70`,
failed-handoff `50c864900a2f9d0fd5b6bc4240d97d365148e4cf2dd511749e9701fa059a09bf`,
attempt-1 78/78 and `e060f650e112ecc8c73f4f2491e8504f3a1f1c9943b80f4e5aa97590b2925801`,
attempt-2 `16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d`,
attempt-3 `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8`,
attempt-4 `aaaa86ba2de9775df83d9a35f561b5fdcb8428a448f3e561937f00edf85a6e41`,
and attempt-5 `7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411`.

**Classification:** `[XHARD]: none.`

RW6-01 is ordinary deterministic named behavioral-test work, and only if
needed a minimal validator correction, already specified by settled-plan
§§4.4–4.13 and frozen C02/C13. Breadth, file span, prior incomplete
attempts, and test count are not an exceptional threshold. Plan §7 and
the frozen tasklist already classified NBF-01 as Normal / GPT-5.6 Luna.
Attempts 1–5 did not reopen that call and this attempt does not either.
There is no irreducible judgment kernel: the surviving hole is that named
tests feed incomplete dictionaries and assert any `ValueError`, so they
never reach the intended payload-family or identity checks. Decomposition
is sufficient. Any proposed `[XHARD]` classification is rejected unless it
proves both that decomposition is insufficient and that the Normal pool
cannot reliably execute the specific kernel.

**Executor model for RW6-01:** GPT-5.6 Luna (`codex:gpt-5.6-luna`).
Exploration, implementation, validation, and the later independent review
are Luna. Grok 4.6 is Oracle and the later gate only. This packet does not
dispatch either model.

**Not authorized by this tasklist:** commit, push, merge, rebase, reset,
clean, staging, plan mutation, frozen-tasklist mutation, Batch 2 dispatch,
main merge, box mutation, a second journal/projection/scheduler/policy
owner, another custody edit, rewriting historical receipts, implementation
by this Oracle, a second implementation issue, a cleanup/environment-repair/
policy/evidence-normalization program, or any Batch 1 pass decision before
the later Grok Oracle gate.

Build on the existing dirty candidate tree. Do not stash or overwrite
orchestrator-owned `.oracle` artifacts except the attempt-6 evidence files
this tasklist explicitly owns.

---

## Scope reminder (frozen NBF-01 ownership)

Own only the NBF-01 primitives already on this candidate: schemas,
`DispatchOutcome.kind=worker_disposition`, disposition-to-terminal mapping,
one existing-journal CAS, terminal writer, changed-precondition producers,
keyed provider-failure-key replay mechanics, probe leases, one composite
`provider_route_child_reserved`, post-commit receipt derivation,
reconciliation, two-scan confirmation, and the disposition helper/CLI.

**Prohibited files and behaviors (every task):**

- Do not edit admission callers, `dispatch_with_admission`, scheduler loops,
  T7 cooldown policy, T8 thresholds/degradation/hold/probe-policy/fallback
  selection/return-to-primary, physical doors, launch adapters, WBC
  construction, Python or shell signal-site wiring, `fallback_chains.py`
  policy, `workers/_impl.py`, `workers/omp.py`,
  `cloud/babysitter/launch.py`, `handlers/shared.py`, `auto.py`,
  `recovery_policy.py`, or any later-task file.
- Do not add a second authority store, generic producer escape hatch,
  signature service, speculative plugin/registry system, second journal,
  store, prepare/commit protocol, rotator, family lease, second projection
  authority, or new policy owner.
- Do not implement T8 policy from the §4.16 transition table's
  "Route-policy effect" column.
- Do not edit `.oracle/tasklist.md`, `.oracle/plan.md`,
  `.oracle/northstar.md`, `.oracle/agent_goal.md`, `.oracle/custody.md`,
  `.oracle/status.md`, or any historical Batch 1 / attempt-1 through
  attempt-5 receipt, finding, check-in, brief, or rework packet.
- Do not rewrite history to make the mutated 52-vs-61 count, unreproducible
  `4aee815d...`, failed-handoff `50c86490...`, attempt-1 `e060f650...`,
  attempt-2 `16f6f854...`, attempt-3 `8fe64464...`, attempt-4
  `aaaa86ba...`, or attempt-5 `7b46da5c...` look consistent. Current
  123/78 are observations, not waivers or targets.
- Do not request or perform another custody edit. RW-CUSTODY is MET.
- Do not signal from the CLI. One JSON acknowledgement on stdout;
  diagnostics on stderr only.
- Do not invent a generic unit-of-work / two-phase framework. Reuse the
  existing `_IncidentEventJournal` sequence-sidecar `fcntl.flock`,
  `_locked`, `_append_nbf_locked`, and `_emit_locked` pattern.
- Do not reopen C19–C21 authority (closed in attempt 5 / RW5-01).
- Do not reopen C39 confirmation evidence-digest equality (closed in
  attempt 5 / RW5-03).
- Do not reopen C36, C37, or C38 reconciliation semantics.
- Do not reopen C01 via overweight `PhaseResult.from_dict` round-trip
  expansion.
- Do not expand C40 cache-mismatch or a broad cache/projection-version
  matrix.
- Do not restore the two broad-suite missing modules or otherwise repair
  the pre-existing environment blocker.
- Do not add a second implementation issue, cleanup program, speculative
  abstraction, or broader criterion expansion.
- Do not reopen C11/C32/C33/C34 keyed/recovery named proof (RW4-03 MET),
  C09/C28 race/crash (RW4-04 MET), C41 CLI redesign, or RW4-06 evidence
  protocol (MET). C41 CLI 0/2/3/4/5 is a regression rerun only if later
  execution evidence reruns it.

Owned source scope remains: five modified production files, new
`incident/disposition.py`, eight named new test modules.
`test_incident_ledger.py` remains unchanged versus `origin/main`.

---

## Explicit exclusions — no task, no silent widening

This packet contains **no task** for:

- C19–C21 changed-precondition authority (Grok marked them MET after RW5-01).
- C39 confirmation evidence-digest equality (Grok marked it MET after RW5-03).
- C36, C37, or C38 reconciliation semantics.
- C01 via overweight `PhaseResult.from_dict` round-trip expansion.
- C40 cache-mismatch or broad cache/projection-version matrix expansion.
- T8 thresholds, degradation policy, retry scheduling, or escalation policy.
- Restoring `arnold.agent.costing.model_resource_capabilities` /
  `tools.environments.singularity` or any other environment repair.
- Custody edits or re-adjudication.
- Historical receipt/check-in rewrite or evidence normalization.
- Admission callers, scheduler, physical doors, launch adapters,
  signal-site wiring, fallback policy, family leases, rotators, second
  journal/store, prepare/commit, main merge, or Batch 2.
- RW4-03 keyed/recovery proof, RW4-04 race/crash proof, RW4-06 executor
  evidence protocol, C41 CLI redesign.
- RW5-01 / RW5-03 reopeners.
- Residual `_IncidentEventJournal._emit_locked` journal-primitive exposure
  named by attempt-5 Grok as out of RW5-01's frozen door set.

Attempt-5 Grok classified the broad-suite missing modules as
`PRE_EXISTING_OUT_OF_SCOPE_BLOCKER`: context, not an NBF regression and
not a waiver. Attempt 6 must record the full sweep evidence in later
execution evidence only if that single existing sweep is rerun, and must
not turn that environment issue into an implementation task. C01/C40
remain unevidenced context; this packet does not expand them.

Triage found **no concrete contradiction** between these exclusions and
RW6-01. If execution discovers one, stop and return to Oracle; do not
silently widen scope.

---

## Prior-MET behavior that must be preserved

Attempt 5 closed RW5-01 and RW5-03 and left the C02/C13 *source* validators
rejecting correctly shaped illegal records. Do not regress that while
completing the named proof.

Preserve from earlier attempts, still MET:

- One `_IncidentEventJournal` + sequence-sidecar flock. NBF writes enter
  `_locked` / `_append_nbf_locked`.
- C03 `no_launch` cannot serialize with `launch_state=accepted`.
- C04 worker-disposition required accepted launch, disposition_id, receipt,
  fingerprint, phase/spec, logical/worker identity, start/finish.
- C05 worker disposition cannot carry provider-exhaustion or no-launch
  state. Carrying an applicable `provider_failure_key` identity on a
  terminal payload for keyed-stream targeting is not provider-exhaustion
  evidence and must not reintroduce `provider_evidence` on
  `worker_disposition`.
- C06 lossless map to `worker_terminal_outcome(outcome_kind=worker_disposition)`.
- C08 never coerced into ordinary failure.
- C09 distinct-ID two-process terminal linkage.
- C12 `no_launch` produces no worker terminal/fingerprint/provider/streak.
- C14 positive OOM and legal unknown-death append paths.
- C15 TERM vs KILL ladder IDs remain distinct.
- C16 semantic fingerprint excludes volatile liveness and logical/family IDs.
- C17 route-liveness digest absent from fingerprint and provider-failure key.
- C18 / C25 two-OS-process same-fingerprint reservation contention yields
  one winner.
- C19–C21 coherent forged changed-precondition rejected at `from_dict`,
  `validate_nbf_event`, `_append_nbf` / `_append_nbf_locked`, public append,
  projection via those doors, and `reserve()`. Valid reader still appends
  and consumes once. Do not weaken this.
- C22 valid changed-precondition consumed at most once.
- C23–C28 named probe/recovery/composite/crash proofs.
- C29 reducer order: provider/fingerprint reduction still runs before
  reservation `closed=True`.
- C30 / C31 matching-stream increment and different-key rekey at one.
- C32 / C33 / C34 keyed non-latest isolation, restart, and canonical
  probe-lease recovery.
- C35 scheduling / no-launch / unresolved / time / liveness refresh do not
  mutate provider streak.
- C36–C38 reconciliation semantics.
- C39 confirmation evidence-digest mismatch and omission now named; matching
  consume-once, restart, replacement, expiry, and one-consumer remain.
- C41 CLI 0/2/3/4/5 including expired and already-consumed matching replay.
- CP04 / CP10: no second journal, store, prepare/commit, scheduler,
  rotator, or family lease.
- CP05: only accepted `provider_exhausted` terminals increment observations.
- CP09 type/state distinction among no-launch, unresolved, ordinary
  failure, provider exhaustion, and worker disposition.
- RW-CUSTODY: already MET. Do not edit `.oracle/custody.md`.
- Route-child wrapper deletion: `hasattr(IncidentLedger,
  "reserve_provider_route_child_with_receipt")` is false (A3-09).
- Executor evidence completeness (RW4-06 / A3-08) remains a later-execution
  protocol, not a new implementation issue.

Keep those named tests and behaviors. Strengthen thin same-name tests in
place; do not delete them to invent a new count. Test-count growth is not
proof. New or strengthened tests must be behavioral, deterministic, and
must fail against the current attempt-5 candidate for the named proof gap
they close.

---

## Independent confirmation of the surviving issue

Oracle re-read frozen C01–C41 / CP01–CP11, the current
`DispatchOutcome.__post_init__` / `from_dict`, `_typed_worker_identity`,
`validate_nbf_event` worker-terminal branch, public
`append_terminal_outcome` / `append_disposition`, and the named tests in
`test_worker_disposition.py`. Oracle independently reproduced the named
public-terminal loop and a correctly shaped six-kind matrix. Probe
transcript: `/tmp/oracle-nbf01-rework6-grok/rw6_probe.json` SHA-256
`fc0885dc74083b733daeaab24e22ef55528f1ae8a3c3ae18ec9a9481073be6ec`.

**Source validators reject correctly shaped illegal pairings.** Direct
construction, `from_dict` of a complete `to_dict()` record, public
`append_terminal_outcome` of that record, `validate_nbf_event` of a
complete `worker_terminal_outcome`, and public `append_disposition` of
that terminal event all emit the intended payload-family errors:

| Kind | Intended error family (correctly shaped) |
| --- | --- |
| `no_launch` + `success_payload` | `no_launch cannot carry worker/provider/disposition evidence` |
| `unresolved_launch` + structured `provider_evidence` | same no-launch/unresolved evidence error |
| `success` + `terminal_failure` | `success cannot carry failure/provider/disposition evidence` |
| `ordinary_terminal_failure` + `success_payload` | `ordinary failure cannot carry success evidence` / `success_payload is only valid for success terminals` |
| `provider_exhausted` + `disposition_id` | `provider exhaustion cannot carry disposition/success evidence` / `only worker disposition terminals carry disposition_id` |
| `worker_disposition` + `success_payload` | `worker_disposition cannot carry success evidence` / `invalid worker disposition success payload` |

Legal positive OOM, unknown-death, non-worker, and worker-disposition
public `append_disposition` paths still accept.

**The named tests do not prove that.** They still pass on the current
candidate because they assert only `pytest.raises(ValueError)`:

1. `test_dispatch_outcome_incompatible_payload_matrix`
   (`test_worker_disposition.py:39-94`) constructs six illegal pairings
   at the constructor, then extends `from_dict` / `validate_nbf_event` /
   private `_append_nbf` only for `worker_disposition` + `success_payload`.
   The later six-kind loop builds incomplete dictionaries missing
   `schema_version`, `provider_failure_key`, `reconciliation_event_id`,
   `terminal_outcome_event_id`, and the unused exclusive-payload Nones
   required by `DispatchOutcome.from_dict`. Independent reproduction:
   every kind rejects `missing DispatchOutcome fields: [...]`.
   `append_disposition` is called with a *terminal-event* dict, not a
   disposition record, and public `append_terminal_outcome` is never
   called from this test.

2. `test_incompatible_matrix_rejects_at_public_terminal_append`
   (`test_worker_disposition.py:97-122`) is the named public-terminal
   door. It feeds the same incomplete `common` dicts into
   `append_terminal_outcome`. `ledger.py:684-685` converts dicts via
   `DispatchOutcome.from_dict` first. Independent reproduction of the
   loop as written: all six kinds reject `missing DispatchOutcome fields`,
   never the payload-family errors above. Incomplete named dicts never
   reach `__post_init__` payload-family checks.

3. `test_typed_identity_matrix_rejects_missing_and_fabricated_worker_at_all_doors`
   (`test_worker_disposition.py:125-132`) covers missing, bare-string, and
   incomplete `{host, pid}` worker identities at `from_dict`,
   `validate_nbf_event`, and `append_disposition` of a terminal dict.
   It does **not** call invalid direct construction or public
   `append_terminal_outcome`. Wrong-version and mismatched typed worker
   identities are absent.

4. `test_observed_and_non_worker_reject_missing_schema_version_and_identity`
   (`test_worker_disposition.py:191-202`) is selected omissions:
   observed `schema_version=2`; non-worker `schema_version=2` and empty
   `lifecycle_identity`; public append of those two version cases; bare
   worker identity on a terminal event at `validate_nbf_event` and
   `_append_nbf` only. Missing/fabricated observed victim identity,
   fabricated killer/subject/cause, missing/fabricated non-worker
   lifecycle identity, and wrong-version at every applicable door are
   not a complete matrix. Private `_append_nbf` is not a substitute for
   public `append_disposition`.

This is incomplete named proof, not a production acceptance bypass and
not a second authority architecture. Green 123/78 cannot substitute.
Legal OOM / unknown-death / non-worker positives remain and must stay.

No fourth issue is authorized. Residual `_emit_locked` journal-primitive
exposure remains out of this packet, exactly as attempt-5 Grok classified
it.

---

## One-issue to task mapping

| Issue | Severity | Criteria | Task | Merge rationale |
| --- | --- | --- | --- | --- |
| 1 named four-door / six-kind payload and typed-identity proof remains incomplete | major | C02, C13, RW5-02, RW4-02, A3-02; preserve C03–C08, C12, C14 | **RW6-01** | Sole serial task. Named tests already exist; they must feed correctly shaped records and assert intended error families at all four doors. One writer owns the overlapping schema/phase/ledger/test seams. |

Do not silently add a second implementation issue. Do not give two tasks
concurrent ownership of the same file.

**Luna serial order:**

```text
completed RW5-01 C19–C21
completed RW5-03 C39
  → RW6-01 C02/C13 complete six-kind/four-door payload and typed-identity matrix
  → later fresh Normal execution evidence, exactly one independent Luna review,
    and a separate Grok Oracle gate
```

Do not dispatch those later phases from this triage turn.

---

## Shared validation commands

Exact frozen focused command (settled plan §6 / NBF-01 / frozen tasklist):

```bash
python -m pytest -q \
  tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py \
  tests/arnold_pipelines/megaplan/test_provider_route_projection.py \
  tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_supervision_confirmation.py \
  tests/arnold_pipelines/megaplan/test_terminal_outcomes.py \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger.py
```

Legacy regressions (do not treat as NBF-01 acceptance by themselves):

```bash
python -m pytest -q \
  tests/arnold_pipelines/megaplan/test_incident_projection.py \
  tests/arnold_pipelines/megaplan/test_incident_summaries.py \
  tests/arnold_pipelines/megaplan/test_incident_bridge.py \
  tests/arnold_pipelines/megaplan/test_phase_result_classify.py
```

Compile and whitespace:

```bash
python -m py_compile \
  arnold_pipelines/megaplan/incident/__init__.py \
  arnold_pipelines/megaplan/incident/ledger.py \
  arnold_pipelines/megaplan/incident/schema.py \
  arnold_pipelines/megaplan/incident/disposition.py \
  arnold_pipelines/megaplan/orchestration/phase_result.py \
  arnold_pipelines/megaplan/orchestration/phase_result_classify.py

git diff --check
```

CLI (Contract G / settled-plan §4.21), invoked as a real subprocess only
if later execution evidence reruns C41 as a regression. Do not redesign
the CLI:

```bash
python -m arnold_pipelines.megaplan.incident.disposition record \
  --ledger-root "$LEDGER_ROOT" \
  --json-stdin
```

Prefer `multiprocessing`/`subprocess` against one on-disk ledger (real
`fcntl.flock`) over in-process threading. Do not inflate test count with
duplicate happy-path stubs. Do not modify
`tests/arnold_pipelines/megaplan/test_incident_ledger.py` unless a frozen
must-criterion cannot live in the eight new modules.

Empty stdout/stderr SHA-256, when truly empty, is the full 64-hex
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
Never truncate it.

Tests must be behavioral and deterministic, not pass-count inflation.
Record exact argv, cwd, exit, UTC timestamps, complete stdout/stderr, and
full stream SHA-256 digests for every command. Do not cite pass counts as
a substitute for streams.

---

## RW6-01 — complete the C02/C13 payload and typed-identity proof

- **ID:** RW6-01
- **Issue closed:** surviving attempt-5 Issue 2 / RW5-02
- **Criteria:** C02, C13
- **Prior IDs:** RW5-02, RW4-02, A3-02
- **Severity:** major
- **Classification:** Normal / GPT-5.6 Luna
- **`[XHARD]`: none.** Completing an already-specified constructor / decode /
  `validate_nbf_event` / public locked-append rejection matrix is ordinary
  schema proof. Not a new type system and not C01 transport expansion.
  Importance, file span, prior incomplete attempts, and test count do not
  meet the exceptional threshold. Decomposition is sufficient. There is
  no irreducible judgment kernel. Any `[XHARD]` proposal must prove both
  that decomposition is insufficient and that the Normal pool cannot
  reliably execute this kernel; absent that evidence, retain Normal/Luna.
- **Executor:** GPT-5.6 Luna
- **Depends on:** completed RW5-01 and RW5-03
- **Serial order:** sole remaining implementation task.
- **Overlapping-file lock:** sole writer of `phase_result.py`
  `DispatchOutcome` doors, `schema.py` worker/observed-death/non-worker
  / `validate_nbf_event` payload-identity branches, the locked public
  append validation used by those records, and the existing named tests
  in `test_scheduling_conditions.py`, `test_worker_disposition.py`, and
  `test_terminal_outcomes.py`.
- **Affected goal / North Star:** Goal criteria 3 foundation (typed death
  records). North Star “Deaths speak” and “one door per invariant.”
  Anti-pattern prevented: anonymous or incidental rejection standing in
  for typed payload-family and identity checks.

### Owned files and symbols

- Production (edit only if a correctly shaped named case reveals a real
  validator hole; default is test-only):
  - `arnold_pipelines/megaplan/orchestration/phase_result.py`
    (`DispatchOutcome.__post_init__`, `DispatchOutcome.from_dict`, the
    six-kind decode path).
  - `arnold_pipelines/megaplan/incident/schema.py`
    (`WorkerDisposition`, `ObservedProcessDeath`,
    `NonWorkerSignalDisposition`, `_typed_worker_identity`,
    `validate_nbf_event` including the `worker_terminal_outcome` branch).
  - `arnold_pipelines/megaplan/incident/ledger.py`
    (`append_disposition`, `append_terminal_outcome`, `_append_nbf_locked`
    validation door only).
- Tests:
  - `tests/arnold_pipelines/megaplan/test_scheduling_conditions.py`
  - `tests/arnold_pipelines/megaplan/test_worker_disposition.py`
    (matrix, identity, legal positives; do not rewrite CLI tests)
  - `tests/arnold_pipelines/megaplan/test_terminal_outcomes.py`

### Preserved prior-MET behavior

Constructor rejection of illegal pairings, C03–C08, C12 no-launch /
unresolved distinction, C14 legal OOM and unknown-death append paths,
C05 provider-exhaustion/no-launch rejection on worker disposition, C08
coercion rejection, lossless worker disposition, RW5-01 authority
closure, RW5-03 confirmation evidence equality, CLI tests untouched.

### Prohibited scope

- Do not reopen C01 by forcing overweight records through
  `PhaseResult.from_dict`. Keep
  `test_scheduling_condition_is_lossless_through_phase_result` as the
  existing scheduling proof; do not expand it into a six-kind PhaseResult
  transport program.
- Do not reopen C14 OOM/unknown-death source doors; they are MET. Keep
  legal positive OOM and legal unknown-death append paths.
- Do not reopen or weaken C19–C21 producers (RW5-01).
- Do not reopen or weaken C39 confirmation equality (RW5-03).
- Do not add a ninth test module.
- Do not treat `_append_nbf` of a hand-built dict as a substitute for
  public `append_terminal_outcome` / `append_disposition` coverage in the
  named matrix.
- Do not assert only `pytest.raises(ValueError)`. Negative cases must
  match the intended payload-family or identity error, not incidental
  `missing DispatchOutcome fields` or unknown-field errors.

### Narrowly bounded outcome

Correctly shaped records for all six payload kinds must be exercised
through direct construction, decode, validation, public terminal append,
and public disposition append. Complete typed worker, observed-death,
and non-worker identity mismatch coverage must be exercised at each
applicable door. Each negative assertion must reach the intended
payload-family or identity validation rather than fail first on
incidental missing fields. Preserve legal positive OOM, unknown-death,
non-worker, and worker-disposition behavior.

Default work is named-test repair. Change production validators only
when a correctly shaped case is accepted or rejected by the wrong
family. Independent Oracle probe of the current attempt-5 source already
rejects correctly shaped six-kind illegal pairings; do not expand
validators “while you are here.”

### Work

Strengthen existing named tests in place across **four doors**:

```text
1. direct construction
2. from_dict decode
3. validate_nbf_event
4. real public locked append (append_terminal_outcome and append_disposition)
```

A correctly shaped `DispatchOutcome` record is `legal.to_dict()` (every
`DispatchOutcome._FIELDS` key present, exclusive unused payloads explicitly
`None`) with exactly one incompatible field mutated. Do not hand-build
partial dicts. `append_terminal_outcome` converts dicts through
`DispatchOutcome.from_dict` (`ledger.py:684-685`); incomplete dicts die
on missing fields and never reach payload-family checks.

Legal kind/state map (unchanged):

```text
no_launch                 -> not_started
success                   -> accepted
ordinary_terminal_failure -> accepted
provider_exhausted        -> accepted
worker_disposition        -> accepted
unresolved_launch         -> ambiguous
```

Required six-kind illegal combinations (complete required fields, one
incompatible family):

```text
no_launch                 + success_payload
unresolved_launch         + provider_evidence   (complete structured evidence)
success                   + terminal_failure
ordinary_terminal_failure + success_payload
provider_exhausted        + disposition_id      (complete provider_evidence retained)
worker_disposition        + success_payload     (the repaired pairing)
```

Door mapping for the six-kind payload matrix:

- Direct construction and `from_dict`: all six kinds, using complete
  records. Observed error must be the payload-family message, not
  `missing DispatchOutcome fields`.
- `validate_nbf_event`: for the four terminal kinds, feed a complete
  `worker_terminal_outcome` whose `outcome_kind` and exclusive payloads
  match the mutated `DispatchOutcome`. For `no_launch` /
  `unresolved_launch`, a complete `worker_terminal_outcome` with those
  `outcome_kind` values must reject `invalid terminal outcome kind`
  rather than a missing-field error.
- Public `append_terminal_outcome`: pass the complete mutated
  `DispatchOutcome` dict or object. For accepted kinds, observed error
  must be the payload-family message. For `no_launch` /
  `unresolved_launch`, after a correctly shaped *legal* record the
  public terminal door rejects `scheduling outcomes have no worker
  terminal event`; a correctly shaped *illegal* record must still hit
  the payload-family check at `from_dict` first. Both are required:
  illegal payload family at decode, and legal scheduling kinds still
  have no terminal event.
- Public `append_disposition`: for the four terminal kinds, pass the
  complete mutated `worker_terminal_outcome` dict. Observed error must
  be the payload-family / identity message from `validate_nbf_event`,
  not an earlier malformed-record error. Private `_append_nbf` coverage
  is insufficient and may remain only as a non-substitute extra.

Typed identity at those same applicable doors:

- Worker semantic fingerprint is a canonical 64-hex SHA-256.
- Worker identity is the typed `host` / `pid` / `boot_id` structure.
  A bare string or arbitrary mapping is not a worker identity.
- Cover missing (`None`), fabricated (non-mapping / wrong types),
  bare-string, wrong-version (`schema_version != 1` on
  `DispatchOutcome` / disposition schemas), incomplete mapping, and
  mismatched typed worker identity (wrong `host`/`pid`/`boot_id` types
  or non-positive pid) at direct construction, `from_dict`,
  `validate_nbf_event`, public `append_terminal_outcome`, and public
  `append_disposition` where that door applies.
- Observed-death subject/cause remain `worker|external_process` with
  `observed_dead_unknown` or `cgroup_oom` only. Missing or fabricated
  subject, cause, killer, victim identity evidence, and wrong
  `schema_version` reject at direct construction, `from_dict`,
  `validate_nbf_event(mutated.to_dict())` (do not inject extra
  `event_id`/`actor`/`recorded_at` onto the typed schema record; that
  incidental unknown-field path is not the identity check), and public
  `append_disposition`.
- Non-worker subject is `non_worker_lifecycle`; worker-specific causes
  reject. Missing/fabricated/empty lifecycle identity, wrong subject,
  wrong `schema_version`, and worker causes reject at the same
  applicable doors.
- Negative cases must reach identity checks, not incidental missing
  `DispatchOutcome` fields.
- Legal positive cases remain: legal `worker_disposition`, legal
  observed-death unknown, legal non-worker lifecycle shutdown, legal
  success/ordinary/provider terminals with matching payloads, legal
  positive cgroup OOM.

### Step-by-step behavioral acceptance

- The named matrix uses correctly shaped records for every six-kind
  illegal combination and drives all four doors, including public
  `append_terminal_outcome` and public `append_disposition`; private-only
  `_append_nbf` coverage is insufficient.
- The matrix includes the repaired `worker_disposition` + `success_payload`
  rejection and every incompatible payload family with complete required
  fields, so the observed error is the intended payload-family rejection.
- Missing, fabricated, bare-string, wrong-version, and mismatched typed
  worker, observed-death, and non-worker identities are each covered at
  direct, decode, validation, and applicable public append doors.
  Negative cases must reach identity checks, not incidental missing
  `DispatchOutcome` fields.
- Legal positive OOM and unknown-death paths, legal non-worker records,
  no-launch/unresolved distinction, lossless worker disposition, and
  prior C03–C08/C12/C14 semantics remain intact.
- Tests are deterministic behavioral regressions and fail against the
  current attempt-5 candidate for the named proof gap. Concretely: if
  the named public-terminal loop still feeds incomplete dicts, a
  substring assertion on the payload-family message must fail. Do not
  expand C01 by adding an overweight `PhaseResult.from_dict` round trip.
- No authority store, second journal, generic producer bypass, second
  projection, policy owner, or unrelated source/test scope is introduced.
- RW5-01 coherent-forgery rejection remains closed. RW5-03 confirmation
  evidence-digest named matrix remains closed.

### Exact validation commands

Run from repository root
`/Users/peteromalley/Documents/Arnold-oracle-nbf`. Record literal argv,
cwd, UTC start/end, exit, complete stdout/stderr, and SHA-256
stream/transcript digests:

```text
python -m pytest -q tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py
python -m pytest -q tests/arnold_pipelines/megaplan/test_worker_disposition.py -k "incompatible_matrix or observed_and_non_worker"
python -m pytest -q tests/arnold_pipelines/megaplan/test_terminal_outcomes.py -k "append or disposition or worker"
python -m pytest -q tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py tests/arnold_pipelines/megaplan/test_provider_route_projection.py tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_supervision_confirmation.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_incident_ledger.py
python -m pytest -q tests/arnold_pipelines/megaplan/test_incident_ledger.py
python -m py_compile arnold_pipelines/megaplan/incident/__init__.py arnold_pipelines/megaplan/incident/ledger.py arnold_pipelines/megaplan/incident/schema.py arnold_pipelines/megaplan/incident/disposition.py arnold_pipelines/megaplan/orchestration/phase_result.py arnold_pipelines/megaplan/orchestration/phase_result_classify.py
git diff --check
```

Require fresh targeted behavioral probes or named test cases that
demonstrate all four doors and intended error families. Preserve C41 CLI
0/2/3/4/5 as a regression only if execution evidence reruns it; do not
redesign the CLI. Preserve broad-suite collection evidence as
`PRE_EXISTING_OUT_OF_SCOPE_BLOCKER` only if later execution runs the
existing single sweep; do not restore missing modules or create a broad
task here.

Present — keep and strengthen:

- `test_dispatch_outcome_incompatible_payload_matrix`
  (full six-kind matrix at all four doors, including
  worker-disposition + `success_payload`; public append of correctly
  shaped records, not only `_append_nbf`; assert intended error family)
- `test_incompatible_matrix_rejects_at_public_terminal_append`
  (rewrite to feed `legal.to_dict()` then one mutation; assert
  payload-family / scheduling-no-terminal errors, not missing fields)
- `test_typed_identity_matrix_rejects_missing_and_fabricated_worker_at_all_doors`
  (add direct invalid construction and public `append_terminal_outcome`;
  cover missing/fabricated/bare-string/wrong-version/mismatched typed
  worker identity)
- `test_worker_disposition_rejects_success_payload_at_append`
  (keep; not a substitute for putting that pairing in the named matrix)
- `test_observed_and_non_worker_reject_missing_schema_version_and_identity`
  (complete missing/fabricated/wrong-version identity at decode and
  public append, not only schema_version / empty lifecycle / bare-string)
- `test_no_launch_rejects_accepted_launch_state`
- `test_unresolved_launch_rejects_success_provider_failure_disposition_payloads`
- `test_success_rejects_provider_and_disposition_payloads`
- `test_outcome_never_coerces_disposition_to_failure`
- `test_worker_disposition_round_trip_and_distinct_outcome`
- `test_legal_positive_oom_appends`
- `test_legal_unknown_death_remains_unknown_after_append`
- `test_scheduling_condition_is_lossless_through_phase_result`

The named matrix must fail on the unmodified attempt-5 candidate for the
incomplete-dict / any-`ValueError` hole.

### Immutable evidence requirements

Record exact argv, cwd, timestamp, exit, complete stdout/stderr, and
full stream SHA-256 for each command above, including the three named
modules and their full incompatible-payload/typed-identity matrix.
Capture complete streams and digests, not just pass counts. Bind the
post-fix owned production diff separately from attempt-5
`7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411`.

---

## Later gate (not dispatched)

After RW6-01:

```text
fresh Normal/Luna execution evidence
  → exactly one independent Luna review
  → separate Grok 4.6 Oracle gate
```

This triage turn does not dispatch those phases. It does not issue
`PASS_BATCH_1` or `ACCEPTED_ISSUES`.

---

## Broad-suite classification (mandatory statement)

Any `pytest -q tests/arnold_pipelines/megaplan` collection failure for
missing `arnold.agent.costing.model_resource_capabilities` or
`tools.environments.singularity` remains
`PRE_EXISTING_OUT_OF_SCOPE_BLOCKER`. It is not an implementation task.
Record the full sweep verbatim in later execution evidence only if that
existing single sweep is rerun. Do not repair those modules.

---

## Next authorized action

Dispatch the Normal/Luna attempt-6 executor against
`.oracle/rework/batch-1-attempt-6.md`.

```text
REWORK_TASKLIST_READY
NBF-01_UNACCEPTED
BATCH_2_PROHIBITED
XHARD_NONE
CUSTODY_MET_NO_FURTHER_EDIT
NO_IMPLEMENTATION_PERFORMED
NO_PASS_BATCH_1
NO_ACCEPTED_ISSUES_FROM_THIS_TRIAGE
RW6-01_SOLE_TASK
```
