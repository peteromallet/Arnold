# Supplemental rework tasklist — NBF-01 / Batch 1, attempt 5

**Status:** supplemental rework only. NBF-01 remains **unaccepted**. Batch 2
is **prohibited** until a later Grok 4.6 Oracle gate returns `PASS_BATCH_1`.

This file does not mutate the frozen NBF tasklist, settled plan v8, North Star,
source base, custody, status, agent goal, or any prior brief, check-in,
finding, receipt, or rework packet. It is the smallest follow-on tasklist
after attempt 4 received `ACCEPTED_ISSUES`. Build on the existing dirty
candidate. Preserve every prior-MET primitive, every attempt-4 closure, and
the already-corrected custody document.

**Authority:** Grok 4.6 Oracle triage of the three accepted issues in
`.oracle/checkins/batch-1-rework4-grok.md`, grounded in Luna review
`.oracle/checkins/batch-1-rework4-luna.md` and independent re-read plus
reproduction of the current candidate symbols and tests. This turn is
triage only. It does not dispatch implementation or review.

**Identities (verified 2026-08-30T03:46:42Z):**

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
| Attempt-4 packet | `4df7024a285e3d0c373278dbd72aed98a0d5af26b05f1f880cf64e9f20a2d534` |
| Attempt-4 triage brief | `d6c559d694c006d4fd310ae706779604ebe228f713a27a40669d6c5c1c040c0f` |
| Attempt-4 triage receipt | `3d20f7bc585e5b5495a38b7a2a26caf1050c90f6dc14f719a95d3203516cfa2c` |
| Attempt-4 execution brief | `25b981e7e20cda6e7aff2027074631dc3b713ec11b0015df81238138e484c79d` |
| Attempt-4 executor finding | `b277eced2d19b92a1a70a5496c40a75a19fc7e14aa116678dfad865aeef4d6c1` |
| Attempt-4 executor receipt | `8739b5ebf73d2d4bdb9d9c089e7da80b3005f230794c0fe2fae306428f1a247f` |
| Attempt-4 Luna check-in | `01b8f596c33342fd3529f3982c9bba2605cd3fa41c44d36a0091b3dd8330972c` |
| Attempt-4 Luna receipt | `de0c6265e58a477b120f944740d5b88ba1834347ae3829d3def4517922e345ee` |
| Attempt-4 Grok check-in | `81a0018acd1d61835988bcc623d265376ec2a3ec8cac8634a902199b750936cf` |
| Attempt-4 Grok receipt | `dfba88485d5e101e86aaec541131a22312bbebe1b910b90455c53545fe90a607` |
| Current owned tracked-production diff | `aaaa86ba2de9775df83d9a35f561b5fdcb8428a448f3e561937f00edf85a6e41` |
| Unchanged `test_incident_ledger.py` | SHA-256 `83e8464c9dfd289aa08de41d044257936072e29ae1d8648f52b84f441f79a195`; blob `44dc3adb87ad4dd077aed449c2f5ccc3526d8d93` |
| Oracle verdict on attempt 4 | `ACCEPTED_ISSUES` |

The attempt-4 tracked-production diff digest is the **reviewed attempt-4
identity**, not a future target. Attempt-5 execution must measure and bind
its own post-fix tree. Do not rewrite attempt-4 artifacts when that digest
changes.

Focused `121 passed` and legacy `78 passed` are observations, never
acceptance targets. Preserve historical evidence as historical: start-gate
52→61, unreproducible `4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70`,
failed-handoff `50c864900a2f9d0fd5b6bc4240d97d365148e4cf2dd511749e9701fa059a09bf`,
attempt-1 78/78 and `e060f650e112ecc8c73f4f2491e8504f3a1f1c9943b80f4e5aa97590b2925801`,
attempt-2 `16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d`,
attempt-3 `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8`,
and attempt-4 `aaaa86ba2de9775df83d9a35f561b5fdcb8428a448f3e561937f00edf85a6e41`.

**Classification:** `[XHARD]: none.`

Every item is ordinary deterministic schema, journal, reducer, behavioral-test,
or receipt work already specified by settled-plan §§4.4–4.13, §4.16,
§§4.19–4.21 and frozen NBF-01. Breadth is not an exceptional threshold.
Plan §7 and the frozen tasklist already classified NBF-01 as Normal /
GPT-5.6 Luna. Attempts 1–4 did not reopen that call and this attempt
does not either. There is no irreducible judgment kernel that the Normal
pool cannot execute: RW5-01 is one producer/reader contract at existing
decode/append/consume/reserve doors; RW5-02 is a named four-door matrix;
RW5-03 is two missing equality cases in an existing test. Decomposition
is sufficient. Any proposed `[XHARD]` classification is rejected.

**Executor model for RW5-01..RW5-03:** GPT-5.6 Luna (`codex:gpt-5.6-luna`).
Exploration, implementation, validation, and the later independent review
are Luna. Grok 4.6 is Oracle and the later gate only. This packet does not
dispatch either model.

**Not authorized by this tasklist:** commit, push, merge, rebase, reset,
clean, staging, plan mutation, frozen-tasklist mutation, Batch 2 dispatch,
main merge, box mutation, a second journal/projection/scheduler/policy
owner, another custody edit, rewriting historical receipts, implementation
by this Oracle, a fourth issue, a cleanup/environment-repair/policy/
evidence-normalization program, or any Batch 1 pass decision before the
later Grok Oracle gate.

Build on the existing dirty candidate tree. Do not stash or overwrite
orchestrator-owned `.oracle` artifacts except the attempt-5 evidence files
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
  "Route-policy effect" column. Replay the streak/key mechanics only.
- Do not edit `.oracle/tasklist.md`, `.oracle/plan.md`,
  `.oracle/northstar.md`, `.oracle/agent_goal.md`, `.oracle/custody.md`,
  `.oracle/status.md`, or any historical Batch 1 / attempt-1 / attempt-2 /
  attempt-3 / attempt-4 receipt, finding, check-in, brief, or rework packet.
- Do not rewrite history to make the mutated 52-vs-61 count, unreproducible
  `4aee815d...`, failed-handoff `50c86490...`, attempt-1 `e060f650...`,
  attempt-2 `16f6f854...`, attempt-3 `8fe64464...`, or attempt-4
  `aaaa86ba...` look consistent. Current 121/78 are observations, not
  waivers or targets.
- Do not request or perform another custody edit. `f8725af...` is already
  labeled historical; `798c506...` is current. RW-CUSTODY is MET.
- Do not signal from the CLI. One JSON acknowledgement on stdout;
  diagnostics on stderr only.
- Do not invent a generic unit-of-work / two-phase framework. Reuse the
  existing `_IncidentEventJournal` sequence-sidecar `fcntl.flock`,
  `_locked`, `_append_nbf_locked`, and `_emit_locked` pattern.
- Do not reopen C36, C37, or C38 reconciliation semantics.
- Do not reopen C01 via overweight `PhaseResult.from_dict` round-trip
  expansion.
- Do not expand C40 cache-mismatch or a broad cache/projection-version
  matrix.
- Do not restore the two broad-suite missing modules or otherwise repair
  the pre-existing environment blocker.
- Do not add a fourth implementation issue, cleanup program, speculative
  abstraction, or broader criterion expansion.
- Do not reopen C11/C32/C33/C34 keyed/recovery named proof (RW4-03 MET),
  C09/C28 race/crash (RW4-04 MET), C41 CLI redesign, or RW4-06 evidence
  protocol (MET). C41 CLI 0/2/3/4/5 is a regression rerun only.

Owned source scope remains: five modified production files, new
`incident/disposition.py`, eight named new test modules.
`test_incident_ledger.py` remains unchanged versus `origin/main`.

---

## Explicit exclusions — no task, no silent widening

This packet contains **no task** for:

- C36, C37, or C38 reconciliation semantics (Grok marked them MET).
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

Attempt-4 Grok classified the broad-suite missing modules as
`PRE_EXISTING_OUT_OF_SCOPE_BLOCKER`: context, not an NBF regression and
not a waiver. Attempt 5 must record the full sweep evidence in later
execution evidence but must not turn that environment issue into an
implementation task. C01/C40 remain unevidenced context; this packet does
not expand them.

Triage found **no concrete contradiction** between these exclusions and
Issues 1–3. If execution discovers one, stop and return to Oracle; do not
silently widen scope.

Any broad-suite missing-module collection failures remain
`PRE_EXISTING_OUT_OF_SCOPE_BLOCKER`, not an implementation task.

---

## Prior-MET behavior that must be preserved

Attempt 4 landed real progress. Do not regress it while closing the
remaining holes.

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
  one winner (`test_two_process_reservation_contention_one_winner`).
- C22 valid changed-precondition consumed at most once.
- C23–C28 named probe/recovery/composite/crash proofs.
- C26 composite child is one record and contains no child receipt-ID input.
- C29 reducer order: provider/fingerprint reduction still runs before
  reservation `closed=True`.
- C30 / C31 for matching streams: matching accepted exhaustion increments
  that key; a first observation of a different key starts that stream at 1.
- C32 / C33 / C34 keyed non-latest isolation, restart, and canonical
  probe-lease recovery.
- C35 scheduling / no-launch / unresolved / time / liveness refresh do not
  mutate provider streak.
- C36–C38 reconciliation: only positive `released_no_launch`, recovered
  terminal, or durable ambiguous hold; recovered disposition links one
  existing record; blind/conflicting/accepted-launch-as-no-launch reject.
- C41 CLI 0/2/3/4/5 including expired and already-consumed matching replay.
- CP04 / CP10: no second journal, store, prepare/commit, scheduler,
  rotator, or family lease.
- CP05: only accepted `provider_exhausted` terminals increment observations.
- CP09 type/state distinction among no-launch, unresolved, ordinary
  failure, provider exhaustion, and worker disposition.
- RW-CUSTODY: already MET. Do not edit `.oracle/custody.md`.
- Real two-process reservation contention remains a real `fcntl.flock` race.
- Historical evidence stays historical.
- Route-child wrapper deletion: `hasattr(IncidentLedger,
  "reserve_provider_route_child_with_receipt")` is false (A3-09).
- Executor evidence completeness (RW4-06 / A3-08) remains a later-execution
  protocol, not a new implementation issue.

Keep those named tests and behaviors. Strengthen thin same-name tests in
place; do not delete them to invent a new count. Test-count growth is not
proof. New or strengthened tests must be behavioral, deterministic, and
must fail on the unmodified attempt-4 candidate for the hole they close.

---

## Independent confirmation of the three accepted issues

Oracle re-read the cited symbols on the current dirty tree and independently
reproduced the coherent-forgery path. They still behave as the attempt-4
verdict described. No fourth issue is authorized.

1. **Issue 1 / C19–C21, RW4-01, A3-03 — blocker.**
   Typed handles now guard the public producer. `_authoritative_source`
   (`schema.py:693-696`) requires `_AuthoritativeSourceHandle`.
   `ChangedPrecondition.from_dict` (`schema.py:546-549`) raises. Public
   `append_changed_precondition` (`ledger.py:774-797`) and
   `consume_changed_precondition` (`ledger.py:1028-1039`) call
   `_validate_producer_binding`. Independent probe
   `/tmp/oracle-nbf01-rework5-grok/independent_probes.json` (SHA-256
   `bfdfe1f29a6ba2271a73faedfdc3b27d4b57c0fc6d0d362ff2fdfdfd3f1c9781`)
   confirms: `from_dict` rejected; public append rejected; public consume
   of a handle-less object rejected; a valid reason-specific reader event
   still appends and consumes once.

   That is not the remaining door. `_validate_changed_precondition_wire`
   (`schema.py:556-601`) still accepts a caller dict whose snapshots hash
   to the cited IDs. `validate_nbf_event` routes `changed_precondition`
   through that function (`schema.py:1010-1011`). `_append_nbf`
   (`ledger.py:438-447`) and `_append_nbf_locked` (`ledger.py:408-436`)
   validate only through `validate_nbf_event`, then emit. Projection
   (`ledger.py:573-574`) stores any such event. `reserve()`
   (`ledger.py:628-631`) authorizes from the projected map.

   Independent Oracle probe rebuilt `after_snapshot.content`,
   `provider_failure_key_after`, `after_content_id`, `before_content_id`,
   `evidence_digest`, and `event_id`. Results:

   - `validate_nbf_event(forged)` — **accepted** (`aa19dd70603e3e772cbc376336fc84e34ca39ceec3b770cc08fc0e65875a5fcd`)
   - `IncidentLedger._append_nbf(forged)` — **accepted**
   - fresh projection — forged event present, `consumed=false`
   - `reserve(..., changed_precondition_event_id=forged["event_id"])` — **accepted**
     (`c11221162d3201ee6809af8d072ed6e93ebb8674b89a73adbc50e94d713174b2`)

   Named `test_coherent_forged_provider_transition_with_recomputed_ids_rejects`
   still only hits `from_dict`, public append, and consume. It never calls
   `validate_nbf_event`, `_append_nbf`, projection, or `reserve()`. This
   is a genuine authorization defect, not test ceremony: a
   self-consistent wire snapshot is treated as authority at the canonical
   NBF append door and then consumed as reservation authorization.

2. **Issue 2 / C02, C13, RW4-02, A3-02 — major.**
   `DispatchOutcome.__post_init__` (`phase_result.py:187-221`) and
   `from_dict` (`phase_result.py:232-240`) reject illegal pairings at
   construction. `validate_nbf_event` worker-terminal branch
   (`schema.py:1085-1134`) rejects `worker_disposition` +
   `success_payload`. Named
   `test_dispatch_outcome_incompatible_payload_matrix`
   (`test_worker_disposition.py:39-67`) constructs six cases, then
   exercises `from_dict` / `validate_nbf_event` / private `_append_nbf`
   only for the worker-disposition + success pairing. It does not drive
   the six kinds through all four required doors, and it never calls
   public `append_terminal_outcome` / `append_disposition`. Named
   `test_observed_and_non_worker_reject_missing_schema_version_and_identity`
   is selected schema_version / empty-lifecycle / bare-string cases, not
   the complete missing/fabricated worker, observed-death, and non-worker
   identity matrix at every door. Legal positive OOM and unknown-death
   append paths remain and must stay. This is incomplete named proof, not
   a second authority architecture.

3. **Issue 3 / C39, RW4-05, A3-07 — major.**
   `IncidentLedger.consume_confirmation` (`ledger.py:966-977`) compares
   `second_evidence_digest` to `prior["evidence_digest"]`. Helper
   `consume_confirmation` (`disposition.py:58-88`) hashes
   `second_evidence`. Named
   `test_confirmation_compares_pid_start_progress_incarnation_cause`
   (`test_supervision_confirmation.py:31-50`) mutates/omits
   `victim_pid`, start, progress, incarnation, cause, `scan_interval_s`,
   `expires_at`, `confirmation_policy_identity`, and `schema_version`.
   It never mutates or omits `second_evidence`. Restart, replacement,
   expiration, reopen, expiry-after-consume, and locked one-consumer
   tests remain and must stay. C41 CLI 0/2/3/4/5 is already complete
   and is a regression rerun only.

Rejected / not tasked:

- RW4-03 keyed/recovery named proof — MET; do not reopen.
- RW4-04 race/crash named proof — MET; do not reopen.
- RW4-06 executor evidence protocol — MET; later execution writes new
  attempt-5 evidence, not a fourth issue.
- C01 / C40 — unevidenced context; do not expand.
- Broad missing modules — `PRE_EXISTING_OUT_OF_SCOPE_BLOCKER`.
- Public-producer handle guard — already MET; RW5-01 must not weaken it.
- C41 CLI redesign — prohibited.

---

## Three-issue to task mapping

| Issue | Severity | Criteria | Task | Merge rationale |
| --- | --- | --- | --- | --- |
| 1 coherent changed-precondition authority remains forgeable | blocker | C19–C21, C22 preserve, RW4-01, A3-03 | **RW5-01** | First serial task. Producer derivation is schema-side; canonical append, projection, and `reserve()` are the same lock. No split: one writer until coherent forgery is closed at every authorization door. |
| 2 strict payload and typed-identity proof incomplete | major | C02, C13, RW4-02, A3-02 | **RW5-02** | Named four-door matrix on already-closed source doors. Waits so Issue 1 owns `schema.py`/`ledger.py` first. Must not weaken the RW5-01 rejection boundary. |
| 3 confirmation evidence-digest equality incomplete | major | C39, C41 regression, RW4-05, A3-07 | **RW5-03** | Last behavioral fix. Contract G identity matrix on the existing confirmation test. CLI already complete. |
| Fresh execution + independent Luna review + Grok Oracle | gate | Batch 1 gate | later | Not implementation. Not dispatched from this triage turn. |

Do not silently merge or omit Issues 1–3. Do not give two tasks concurrent
ownership of the same file. `ledger.py` has one writer at a time, in the
order below. Issue 1 is not reordered behind evidence-only work.

**Why no file-ownership split:** RW5-01's hole is one contract: a
self-consistent wire snapshot is authority at decode, canonical/private
append, projection, and `reserve()`. Those symbols live in `schema.py`
(`_validate_changed_precondition_wire`, `validate_nbf_event`) and
`ledger.py` (`_append_nbf`, `_append_nbf_locked`, `_project_records`,
`reserve`, `append_changed_precondition`, `consume_changed_precondition`)
plus the existing changed-precondition test module. Splitting schema
from ledger would leave one door open while the other closed. Any later
proposed split must preserve serial one-writer ordering: schema/ledger
changed-precondition authority first, then payload matrix, then
confirmation.

**Luna serial order:**

```text
RW5-01 C19–C21 wire/private-append/reserve authorization closure
  → RW5-02 C02/C13 complete six-kind/four-door payload and identity matrix
  → RW5-03 C39 confirmation evidence-digest mismatch/omission matrix
  → later fresh Normal execution evidence, exactly one independent Luna review,
    and a separate Grok Oracle gate
```

Do not dispatch those later phases from this triage turn.

---

## Shared validation commands

Exact frozen focused command (settled plan §6 / NBF-01 / frozen tasklist):

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

Legacy regressions (do not treat as NBF-01 acceptance by themselves):

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_incident_projection.py \
  tests/arnold_pipelines/megaplan/test_incident_summaries.py \
  tests/arnold_pipelines/megaplan/test_incident_bridge.py \
  tests/arnold_pipelines/megaplan/test_phase_result_classify.py
```

Compile and whitespace:

```bash
python -m py_compile \
  arnold_pipelines/megaplan/orchestration/phase_result.py \
  arnold_pipelines/megaplan/orchestration/phase_result_classify.py \
  arnold_pipelines/megaplan/incident/schema.py \
  arnold_pipelines/megaplan/incident/ledger.py \
  arnold_pipelines/megaplan/incident/disposition.py

git diff --check
```

CLI (Contract G / settled-plan §4.21), invoked as a real subprocess, never
as a pytest name standing in for the transcript:

```bash
python -m arnold_pipelines.megaplan.incident.disposition record \
  --ledger-root "$LEDGER_ROOT" \
  --json-stdin
```

Exact statuses: `0` append succeeded; `2` malformed JSON or schema
violation; `3` ledger append/locking failure; `4` invalid or unavailable
ledger/context location; `5` missing, expired, mismatched, or
already-consumed confirmation.

Prefer `multiprocessing`/`subprocess` against one on-disk ledger (real
`fcntl.flock`) over in-process threading. Use injectable clocks for
TTL/separation. Do not inflate test count with duplicate happy-path stubs.
Do not modify `tests/arnold_pipelines/megaplan/test_incident_ledger.py`
unless a frozen must-criterion cannot live in the eight new modules.

Empty stdout/stderr SHA-256, when truly empty, is the full 64-hex
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
Never truncate it.

Tests must be behavioral and deterministic, not pass-count inflation.

Record exact argv, cwd, exit, and full stdout/stderr SHA-256 digests for
every command. Do not cite pass counts as a substitute for streams.

---

## RW5-01 — Wire / private-append / reserve authorization closure

- **ID:** RW5-01
- **Issue closed:** Issue 1
- **Criteria:** C19, C20, C21; preserve C22
- **Prior IDs:** RW4-01, A3-03
- **Severity:** blocker
- **Classification:** Normal / GPT-5.6 Luna
- **`[XHARD]`: none.** Deterministic schema/journal compare already specified
  by settled-plan §4.6 and frozen C19–C21. Closing the remaining wire and
  canonical-append doors onto the existing typed source-handle contract is
  not a new concurrency protocol, signature service, or schema language.
  Decomposition is one serial task. The Normal pool can execute it.
- **Executor:** GPT-5.6 Luna
- **Depends on:** none
- **Serial order:** first. Blocks RW5-02 and RW5-03.
- **Overlapping-file lock:** sole writer of `schema.py` producer/handle/
  wire-validator symbols and of `ledger.py` `_append_nbf` /
  `_append_nbf_locked` / `_project_records` changed-precondition branch /
  `reserve` / `append_changed_precondition` / `consume_changed_precondition`
  until this task finishes. No later task may proceed until the coherent
  forgery is behaviorally closed at every authorization door.
- **Why no file-ownership split:** the remaining hole is one contract
  (caller-shaped self-consistent snapshot is not authority). Schema
  decode and ledger append/projection/reserve are one writer path. A
  split would leave `_append_nbf` accepting what `from_dict` rejects.

### Owned files and symbols

- Production:
  - `arnold_pipelines/megaplan/incident/schema.py`
    (`ChangedPrecondition`, `_authoritative_source`, `_produce_authoritative`,
    `_produce_reason_specific`, `produce_changed_precondition`, the seven
    allowlisted `produce_*` reason-specific producers, `_source_handles_for`,
    `_validate_producer_binding`, `_validate_changed_precondition_wire`,
    `from_dict` / `__post_init__`, `validate_nbf_event` changed-precondition
    branch).
  - `arnold_pipelines/megaplan/incident/ledger.py`
    (`IncidentLedger.append_changed_precondition`,
    `consume_changed_precondition`, `_append_nbf`, `_append_nbf_locked`,
    `_project_records` changed-precondition branch, `reserve`; existing
    `_locked` only).
- Tests:
  - `tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py`
  - Smallest consume/one-use cases already living in
    `tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py`
    (`test_consumed_change_cannot_authorize_second_reservation`) may be
    strengthened in place. Do not retarget torn-composite or terminal-race
    names.

### Preserved prior-MET behavior

Public typed-handle producer path, generic `ChangedPrecondition.produce`
and `produce_changed_precondition` still raising, C22 single consume,
valid reason-specific reader mint/append/consume-once, one journal, one
lock, keyed recovery producer identity, and all attempt-4 MET behavior
listed above.

### Prohibited scope

- Do not add a second authority store, generic producer escape hatch,
  signature service, speculative plugin/registry system, second journal,
  or new policy owner.
- Do not restore `ChangedPrecondition.produce` or
  `produce_changed_precondition` as minting paths; they already raise and
  must keep raising.
- Do not treat a dataclass whose only fields are `authority_kind`,
  `subject`, and `content` as a typed handle. That is still a
  caller-shaped snapshot.
- Do not rely only on content-address equality an attacker can recompute
  from snapshots they also supply.
- Do not leave `_validate_changed_precondition_wire` as a self-hash
  adapter that `validate_nbf_event` / `_append_nbf` treat as authority.
- Do not change keyed-streak reducer selection, payload matrix (RW5-02),
  composite crash, or confirmation (RW5-03).
- Do not add prepare/commit records or a UnitOfWork.
- Do not reopen C36–C38.

### Narrowly bounded outcome

One authoritative producer/reader contract at every changed-precondition
authorization door: decode, canonical/private append, projection, locked
consume, and `reserve()`. A caller-shaped snapshot is never authority.
A smallest typed authoritative source handle/reader per allowlisted
reason remains the only minting path.

### Work

Keep the seven allowlisted reason-specific producers from settled-plan
§4.6 as the only minting path:

```text
source_revision_changed          -> reads authoritative repository/source receipt
runtime_generation_changed       -> reads authoritative runtime registry/manifest
seed_or_interpreter_binding_changed -> reads seed and interpreter attestations
timeout_policy_changed           -> reads canonical timeout-policy configuration
authorized_route_changed         -> binds jointly admitted composite route event
provider_recovery_verified       -> binds a successful canonical bounded probe result
verified_repair_committed        -> binds repository commit identity and verified digest
```

Each producer has a fixed `producer_kind` and `producer_version`. Each
reason has the smallest typed authoritative source handle **and** a closed
reader for that reason. The handle carries the reason-specific source
identity the reader actually reads, plus `source_version` and subject.
Fixture objects may be passed **as the source to read**, not as
pre-digested IDs or `{authority_kind, subject, content}` blobs.

The reader, not the caller, binds:

```text
producer identity (kind + version, fixed by reason)
reason
authoritative subject
source version
persisted cited evidence event
evidence digest
canonical before/after content
before_content_id / after_content_id (must differ)
provider-failure-key before/after derivation
```

`provider_recovery_verified` keeps before-key == after-key. Callers must
not supply `producer_kind`, `producer_version`, subject, evidence digest,
before/after content IDs, or provider-failure-key transitions as trusted
inputs.

Validate at **every authorization door**, not snapshot self-hash alone
and not only the public producer wrappers:

1. Decode / `ChangedPrecondition.from_dict`. Reconstruct the typed handle
   and re-run the reason-specific reader. Caller-shaped
   `{authority_kind, subject, content}` snapshots reject. A dict that
   mutates a valid event and recomputes every serializable hash/ID
   (`after_snapshot`, `after_content_id`, `evidence_digest`,
   `provider_failure_key_after`, `event_id`, and any other content-addressed
   field) still rejects.
2. `validate_nbf_event` changed-precondition branch. Must not treat
   `_validate_changed_precondition_wire` self-consistency as authority.
   A coherent recomputed wire snapshot rejects here.
3. Canonical/private append: `_append_nbf` and `_append_nbf_locked`.
   Same rejection. A well-formed caller snapshot whose hashes merely
   agree with themselves does not persist.
4. Projection. A rejected wire event must not appear in
   `changed_preconditions`.
5. `append_changed_precondition` under `_locked`. Require the cited
   evidence event to be persisted. Re-derive producer/reason/subject/
   source-version/content IDs/provider keys/evidence digest from that
   persisted evidence plus the typed handle.
6. `consume_changed_precondition` under the same lock. Re-validate the
   same bindings. Unpersisted or non-authoritative objects reject. A valid
   persisted producer event consumes exactly once (preserve C22).
7. `reserve()`. A forged or unauthenticated changed-precondition event
   id must not authorize a new reservation.

Keep KISS: extend compare inside the existing `_append_nbf_locked` /
`validate_nbf_event` door; do not wrap the ledger in a new transaction
API and do not add a second store.

### Step-by-step behavioral acceptance

- Only the matching reason-specific source reader can mint a valid event.
- Generic `ChangedPrecondition.produce` and `produce_changed_precondition`
  still raise.
- Caller-shaped snapshots, independently supplied producer identity,
  independently supplied content IDs, and independently supplied
  provider-key transitions reject.
- A coherent forged transition that recomputes every serializable hash/ID
  rejects at `from_dict`, `validate_nbf_event`, `_append_nbf` /
  `_append_nbf_locked`, public `append_changed_precondition`,
  `consume_changed_precondition`, projection, **and** `reserve()`.
- The adversarial test recomputes every serializable hash/ID and proves
  rejection at each relevant door, including no projection and no
  `reserve()` authorization.
- A valid event minted through the matching reader appends and is consumed
  exactly once under the existing journal lock; a second consume rejects.
- C22 remains: `test_consumed_change_cannot_authorize_second_reservation`
  still holds.
- One journal, one lock door, no second authority store.

### Exact validation commands

```bash
pytest -q tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py

pytest -q \
  tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py \
  -k "coherent_forged or valid_reason_specific_source_reader or forged or producer or authoritative"

pytest -q \
  tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py \
  -k "precondition or consumed_change or forged or producer or authoritative"

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

pytest -q \
  tests/arnold_pipelines/megaplan/test_incident_projection.py \
  tests/arnold_pipelines/megaplan/test_incident_summaries.py \
  tests/arnold_pipelines/megaplan/test_incident_bridge.py \
  tests/arnold_pipelines/megaplan/test_phase_result_classify.py

python -m py_compile \
  arnold_pipelines/megaplan/orchestration/phase_result.py \
  arnold_pipelines/megaplan/orchestration/phase_result_classify.py \
  arnold_pipelines/megaplan/incident/schema.py \
  arnold_pipelines/megaplan/incident/ledger.py \
  arnold_pipelines/megaplan/incident/disposition.py

git diff --check
```

Present — keep and retarget:

- `test_coherent_forged_provider_transition_with_recomputed_ids_rejects`
  (rebuild **every** serializable hash/ID, including `after_snapshot`,
  content IDs, evidence digest, provider keys, and `event_id`; prove
  rejection at `from_dict`, `validate_nbf_event`, `_append_nbf`, public
  append, consume, projection, and `reserve()`)
- `test_valid_reason_specific_source_reader_mints_and_consumes_once`
- `test_reason_specific_producers_reject_caller_producer_identity`
- `test_forged_valid_hex_content_ids_reject`
- `test_caller_supplied_provider_key_transition_rejects`
- `test_authoritative_before_after_digests_match_source`
- `test_producer_derives_unequal_ids_and_recovery_preserves_key`
- `test_free_form_reason_and_reuse_are_rejected`
- `test_consumed_change_cannot_authorize_second_reservation`

These names must fail on the unmodified attempt-4 candidate for the
wire/private-append/`reserve()` hole.

### Immutable evidence requirements

Record exact argv, cwd, timestamp, exit, complete stdout/stderr, and
full stream SHA-256 for each command above. Bind HEAD, source base,
production diff, and owned-file SHA-256 / git-blob inventory. Do not
summarize streams as pass counts.

---

## RW5-02 — C02/C13 complete six-kind / four-door payload and identity matrix

- **ID:** RW5-02
- **Issue closed:** Issue 2
- **Criteria:** C02, C13
- **Prior IDs:** RW4-02, A3-02
- **Severity:** major
- **Classification:** Normal / GPT-5.6 Luna
- **`[XHARD]`: none.** Completing an already-specified constructor / decode /
  `validate_nbf_event` / public locked-append rejection matrix is ordinary
  schema proof. Not a new type system and not C01 transport expansion.
- **Executor:** GPT-5.6 Luna
- **Depends on:** RW5-01
- **Serial order:** second. Must not weaken the RW5-01 rejection boundary.
- **Overlapping-file lock:** sole writer of `phase_result.py`
  `DispatchOutcome` doors, `schema.py` worker/observed-death/non-worker
  / `validate_nbf_event` payload-identity branches, and the locked append
  validation used by those records, after RW5-01.

### Owned files and symbols

- Production:
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

Constructor rejection of illegal pairings, C03–C08, C14 legal OOM and
unknown-death append paths, C05 provider-exhaustion/no-launch rejection
on worker disposition, C08 coercion rejection, RW5-01 authority
closure, CLI tests untouched.

### Prohibited scope

- Do not reopen C01 by forcing overweight records through
  `PhaseResult.from_dict`. Keep
  `test_scheduling_condition_is_lossless_through_phase_result` as the
  existing scheduling proof; do not expand it into a six-kind PhaseResult
  transport program.
- Do not reopen C14 OOM/unknown-death source doors; they are MET. Keep
  legal positive OOM and legal unknown-death append paths.
- Do not reopen or weaken C19–C21 producers (RW5-01).
- Do not add a ninth test module.
- Do not treat `_append_nbf` of a hand-built dict as a substitute for
  public `append_terminal_outcome` / `append_disposition` coverage in the
  named matrix.

### Narrowly bounded outcome

Evidence, and only minimal behavior if necessary, for the complete
incompatible-payload and identity matrix at direct construction,
`from_dict`, `validate_nbf_event`, and real public locked append.
Include all six kinds, missing/fabricated worker, observed-death, and
non-worker identities, and legal positive OOM/unknown/non-worker cases.

### Work

Strengthen existing named tests in place across **four doors**:

```text
direct construction
from_dict
validate_nbf_event
real public locked append (append_terminal_outcome / append_disposition)
```

Legal kind/state map (unchanged):

```text
no_launch                 -> not_started
success                   -> accepted
ordinary_terminal_failure -> accepted
provider_exhausted        -> accepted
worker_disposition        -> accepted
unresolved_launch         -> ambiguous
```

Incompatible payload families to reject for every illegal pairing:

```text
success_payload
terminal_failure
provider_evidence
disposition_id
worker/timing/receipt/fingerprint context on no_launch and unresolved_launch
```

Specifically include the repaired `worker_disposition` + `success_payload`
rejection in the named matrix at all four doors. Preserve C05: still
reject provider-exhaustion and no-launch state on worker disposition.
Preserve the existing source constructor door; add decode, validation,
and public append.

Typed identity at those same doors:

- Worker semantic fingerprint is a canonical 64-hex SHA-256.
- Worker identity is the typed `host` / `pid` / `boot_id` structure.
  A bare string or arbitrary mapping is not a worker identity.
- Observed-death subject/cause remain `worker|external_process` with
  `observed_dead_unknown` or `cgroup_oom` only. Missing or fabricated
  subject, cause, killer, or victim identity reject.
- Non-worker subject is `non_worker_lifecycle`; worker-specific causes
  reject. Missing/fabricated lifecycle identity reject.
- Required/missing/fabricated identity fields reject at decode and append.
- Legal positive cases remain: legal `worker_disposition`, legal
  observed-death unknown, legal non-worker lifecycle shutdown, legal
  success/ordinary/provider terminals with matching payloads.

### Step-by-step behavioral acceptance

- Named six-kind incompatibility matrix rejects every illegal payload
  family at constructor, `from_dict`, `validate_nbf_event`, and real
  public locked append, including `worker_disposition` + `success_payload`.
- Missing and fabricated worker, observed-death, and non-worker identity
  fields reject at those doors.
- Legal positive OOM, unknown-death, and non-worker cases still append.
- C08 coercion rejection still holds with typed worker identity.
- `PhaseResult.from_dict` is not used as a C01 expansion vehicle.
- RW5-01 coherent-forgery rejection remains closed.

### Exact validation commands

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_terminal_outcomes.py

pytest -q \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  -k "incompatible_payload or observed_and_non_worker or legal_positive_oom or legal_unknown_death or worker_disposition_rejects_success"

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

pytest -q \
  tests/arnold_pipelines/megaplan/test_incident_projection.py \
  tests/arnold_pipelines/megaplan/test_incident_summaries.py \
  tests/arnold_pipelines/megaplan/test_incident_bridge.py \
  tests/arnold_pipelines/megaplan/test_phase_result_classify.py

python -m py_compile \
  arnold_pipelines/megaplan/orchestration/phase_result.py \
  arnold_pipelines/megaplan/orchestration/phase_result_classify.py \
  arnold_pipelines/megaplan/incident/schema.py \
  arnold_pipelines/megaplan/incident/ledger.py \
  arnold_pipelines/megaplan/incident/disposition.py

git diff --check
```

Present — keep and strengthen:

- `test_dispatch_outcome_incompatible_payload_matrix`
  (full six-kind matrix at all four doors, including
  worker-disposition + `success_payload`; public append, not only
  `_append_nbf`)
- `test_worker_disposition_rejects_success_payload_at_append`
  (keep; not a substitute for putting that pairing in the named matrix)
- `test_observed_and_non_worker_reject_missing_schema_version_and_identity`
  (complete missing/fabricated identity at decode and public append, not
  only schema_version / empty lifecycle / bare-string)
- `test_no_launch_rejects_accepted_launch_state`
- `test_unresolved_launch_rejects_success_provider_failure_disposition_payloads`
- `test_success_rejects_provider_and_disposition_payloads`
- `test_outcome_never_coerces_disposition_to_failure`
- `test_worker_disposition_round_trip_and_distinct_outcome`
- `test_legal_positive_oom_appends`
- `test_legal_unknown_death_remains_unknown_after_append`
- `test_scheduling_condition_is_lossless_through_phase_result`

The named matrix must fail on the unmodified attempt-4 candidate for the
constructor-plus-one-pairing / omitted public-append hole.

### Immutable evidence requirements

Record exact argv, cwd, timestamp, exit, complete stdout/stderr, and
full stream SHA-256 for each command above, including the three named
modules and their full incompatible-payload/typed-identity matrix.
Capture complete streams and digests, not just pass counts.

---

## RW5-03 — C39 confirmation evidence-digest mismatch / omission matrix

- **ID:** RW5-03
- **Issue closed:** Issue 3
- **Criteria:** C39; C41 regression only
- **Prior IDs:** RW4-05, A3-07
- **Severity:** major
- **Classification:** Normal / GPT-5.6 Luna
- **`[XHARD]`: none.** Adding wrong and omitted `second_evidence` cases to
  an existing equality matrix is ordinary behavioral-test work. Source
  already compares the digest.
- **Executor:** GPT-5.6 Luna
- **Depends on:** RW5-02
- **Serial order:** last among behavioral fixes.
- **Overlapping-file lock:** sole writer of the existing confirmation
  schema/ledger/test seam after RW5-02.

### Owned files and symbols

- Production:
  - `arnold_pipelines/megaplan/incident/ledger.py`
    (`observe_confirmation`, `consume_confirmation`,
    `expire_confirmation`, replacement/replay in `_project_records`)
  - `arnold_pipelines/megaplan/incident/schema.py`
    (`SupervisionConfirmation` codecs/compare only if a frozen field is
    not yet required at consume)
  - `arnold_pipelines/megaplan/incident/disposition.py`
    (`observe_confirmation` / `consume_confirmation` helpers only if the
    named test cannot omit `second_evidence` through the current helper
    signature; do not redesign the CLI)
- Tests:
  - `tests/arnold_pipelines/megaplan/test_supervision_confirmation.py`
  - CLI branches in
    `tests/arnold_pipelines/megaplan/test_worker_disposition.py`
    are **regression only**. Do not redesign them. Do not add a ninth
    module.

### Preserved prior-MET behavior

Restart, replacement, expiration, reopen, expiry-after-consume,
locked one-consumer, TTL/scan-separation, identity-field mismatch/
omission already present, and C41 CLI 0/2/3/4/5 including expired and
already-consumed replay.

### Prohibited scope

- No wrapper-local confirmation files or second store.
- No signalling from the CLI.
- No free-form caller TTL; keep
  `confirmation_ttl_s = min(max(2 * scan_interval_s, 30.0), 300.0)`.
- Do not implement keyed replay or producers here.
- Do not redesign C41. Rerun the existing named CLI subprocesses.
- Do not drop already-MET confirmation tests to invent a new count.

### Narrowly bounded outcome

Explicit wrong and missing second-evidence cases in the existing
equality matrix, retaining all already-MET restart, replacement,
expiration, reopen, expiry-after-consume, and locked one-consumer
behavior. C41 is a regression rerun only.

### Work

Require, persist, and compare every frozen identity, timing, and evidence
field, including:

```text
victim_pid
victim_process_start_identity
relevant_progress_identity
supervisor_incarnation_identity
cause_kind
evidence digest / second_evidence
TTL / expires_at
scan_interval_s / scan separation
confirmation_policy_identity / schema_version where the frozen schema requires it
```

Strengthen `test_confirmation_compares_pid_start_progress_incarnation_cause`
with each single-field mismatch **and** omission for that full set,
including a wrong `second_evidence` payload and an omitted
`second_evidence` argument. The current test already covers pid/start/
progress/incarnation/cause and TTL/policy/version; do not delete those
cases.

Preserve restart, replacement, expiration, reopen, expiry-after-consume
rejection, and locked one-consumer race behavior.

If the helper currently hashes `second_evidence` and therefore cannot
express omission, add the omission case at the helper/ledger door that
actually accepts the digest so the named test proves both wrong digest
and missing evidence. Do not invent a second confirmation store.

### Step-by-step behavioral acceptance

- Wrong second-evidence digest rejects consume.
- Omitted second-evidence rejects consume.
- Each already-covered identity/timing/policy field mismatch and omission
  still rejects.
- Replacement and expiry remain durable; restart preserves original expiry.
- Expiry after consumption rejects; consumed state survives replay.
- Two processes racing consume still yield one consumer.
- CLI 0/2/3/4/5 subprocesses still pass, including expired 5 and distinct
  already-consumed matching replay.

### Exact validation commands

```bash
pytest -q tests/arnold_pipelines/megaplan/test_supervision_confirmation.py::test_confirmation_compares_pid_start_progress_incarnation_cause

pytest -q tests/arnold_pipelines/megaplan/test_supervision_confirmation.py

pytest -q \
  tests/arnold_pipelines/megaplan/test_supervision_confirmation.py \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  -k "cli_status or confirmation"

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

pytest -q \
  tests/arnold_pipelines/megaplan/test_incident_projection.py \
  tests/arnold_pipelines/megaplan/test_incident_summaries.py \
  tests/arnold_pipelines/megaplan/test_incident_bridge.py \
  tests/arnold_pipelines/megaplan/test_phase_result_classify.py

python -m py_compile \
  arnold_pipelines/megaplan/orchestration/phase_result.py \
  arnold_pipelines/megaplan/orchestration/phase_result_classify.py \
  arnold_pipelines/megaplan/incident/schema.py \
  arnold_pipelines/megaplan/incident/ledger.py \
  arnold_pipelines/megaplan/incident/disposition.py

git diff --check
```

Plus independent CLI 0/2/3/4/5 subprocesses of
`python -m arnold_pipelines.megaplan.incident.disposition record`. Do not
skip 3/4/5. Do not treat pytest names as the independent CLI evidence.

Present — keep and strengthen:

- `test_confirmation_compares_pid_start_progress_incarnation_cause`
  (every frozen field mismatch and every omission, **including wrong and
  omitted second-evidence**)
- `test_confirmation_ttl_and_single_consumption`
- `test_second_scan_too_early_and_expired_rejected`
- `test_confirmation_replacement_and_expiry_are_durable`
- `test_confirmation_survives_ledger_reopen_with_original_expiry`
- `test_expire_confirmation_after_consume_rejects`
- `test_two_process_confirmation_single_consumer`
- `test_cli_status_0_one_json_ack_no_signal`
- `test_cli_status_2_malformed_or_schema`
- `test_cli_status_3_append_or_lock_failure`
- `test_cli_status_4_invalid_ledger_location`
- `test_cli_status_5_missing_and_already_consumed_confirmation`
- `test_cli_status_5_expired_confirmation`
- `test_cli_status_5_distinct_already_consumed_replay`

### Immutable evidence requirements

Record exact argv, cwd, timestamp, exit, complete stdout/stderr, and
full stream SHA-256 for the named confirmation test, the CLI 0/2/3/4/5
subprocess matrix, the frozen focused and legacy suites, `py_compile`,
and `git diff --check`. Capture complete streams and digests, not just
pass counts.

---

## Later gate (not dispatched)

After RW5-01..RW5-03:

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
Record the full sweep verbatim in later execution evidence. Do not
repair those modules.

---

## Next authorized action

Dispatch the Normal/Luna attempt-5 executor against
`.oracle/rework/batch-1-attempt-5.md`.

```text
REWORK_TASKLIST_READY
NBF-01_UNACCEPTED
BATCH_2_PROHIBITED
XHARD_NONE
CUSTODY_MET_NO_FURTHER_EDIT
NO_IMPLEMENTATION_PERFORMED
NO_PASS_BATCH_1
NO_ACCEPTED_ISSUES_FROM_THIS_TRIAGE
```
