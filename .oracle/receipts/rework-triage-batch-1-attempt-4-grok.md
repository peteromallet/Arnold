# Receipt — NBF-01 Batch 1 rework triage, attempt 4 (Grok 4.6)

- Oracle: Grok 4.6 (manager/validator only)
- Date: 2026-08-30
- Role: fourth supplemental rework triage after attempt-3 `ACCEPTED_ISSUES`
- Implementation performed: **none**
- Review dispatch: **none**
- Production / test / frozen-plan / custody / historical-receipt edits: **none**
- Commit / push / merge / rebase / reset / clean / Batch 2: **none authorized, none performed**
- Batch 1 pass decision: **not authorized in this triage turn**

## Source identities (verified this turn)

| Artifact | SHA-256 / git identity |
| --- | --- |
| `.oracle/northstar.md` | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| `.oracle/plan.md` (settled v8) | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| `.oracle/tasklist.md` (frozen) | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| `.oracle/custody.md` (unchanged this turn) | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| `.oracle/agent_goal.md` | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` |
| `.oracle/receipts/model-policy-grok-switch.md` | `0bb386bf6fff5f9a5197a57cea5789ee250231a163dfd01bbe828776e1cc5064` |
| Tasklist-freeze receipt | `583955c6996bcc18e8fe05d323c30f5f77e489cdd5a66ecb1783ac42c9d24a24` |
| Attempt-1 rework tasklist | `5149fdcf7fd91a255ec6cfe34f447a9b1eb46bf3b56db92a2e03939fbc9d1d2c` |
| Attempt-1 triage receipt | `7565016b618293fa666f61710f0f95bb8847d6d2336568ff064d8843699efa1e` |
| Attempt-2 rework tasklist | `6d625cc406ff7fe2c8764d6aae813005942a40203a01e346c290a2c6804be721` |
| Attempt-2 triage receipt | `3f1c460d06966d5eef2999e5e4b99e5324b2aa920609d10ffe2d54af81a41703` |
| Attempt-3 rework tasklist | `c4c93f8b14e253060c0a403869e22a23aadc6444e63b32f48fd55cf95b63e779` |
| Attempt-3 triage receipt | `2d025f9614d5dcf3f4e00de881962f1152a8be222b7cb4868055cf5a47856f4b` |
| Attempt-3 executor finding `.oracle/findings/execution-nbf01-rework3-luna.md` | `4897b2c7484aa7cc221488f7535339b716f780f3e70d62a202096504ac254e9f` |
| Attempt-3 executor receipt `.oracle/receipts/execution-nbf01-rework3-luna.md` | `e34f901febedc434e27d778c3be5e070a6ded93a961a26dc1c4c62577339351f` |
| Attempt-3 Luna review `.oracle/checkins/batch-1-rework3-luna.md` | `573ce524b0c348445c7a0d89ee2a391fc3386135c72a124d09678735e1d727bd` |
| Attempt-3 Luna review receipt `.oracle/receipts/oracle-nbf01-rework3-luna.md` | `ad0e4e947a29dc796adf98ed40b04e26b92a6877d6457de98ab2ee3bf897a425` |
| Attempt-3 Grok check-in `.oracle/checkins/batch-1-rework3-grok.md` | `4bd93c1d24e55c1860add92abbce5c44c979c2d0b83dd63b1ceb798db783af02` |
| Attempt-3 Grok Oracle receipt `.oracle/receipts/oracle-nbf01-rework3-grok.md` | `95ec60c0f981217500b9922ac86ffb95d6c60036d39ea32d07761731716c3a30` |
| Attempt-3 gate brief `.oracle/briefs/oracle-nbf01-rework3-grok.md` | `5b062d0ded7552ce01bb7b4a7231a349419102a219c967c9a05cfbf46f2fdc01` |
| Immutable source base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` |
| Candidate branch | `megado-nbf-guard-0826` |
| Planning HEAD | `922241d0bdb3e993c3b554cc69f19948adef7bc3` |
| Merge-base with `origin/main` | `798c50619204010ed3f4297fbb57988fe9381924` |
| Attempt-3 owned tracked-production diff (reviewed identity, not a future target) | `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8` |
| Unchanged `test_incident_ledger.py` | SHA-256 `83e8464c9dfd289aa08de41d044257936072e29ae1d8648f52b84f441f79a195`; blob `44dc3adb87ad4dd077aed449c2f5ccc3526d8d93` |

Supplemental tasklist written this turn:

- Path: `.oracle/rework/batch-1-attempt-4.md`
- SHA-256: `4df7024a285e3d0c373278dbd72aed98a0d5af26b05f1f880cf64e9f20a2d534`

Frozen `.oracle/tasklist.md`, settled plan v8, North Star, custody, status,
agent goal, historical evidence, and all prior briefs/check-ins/findings/
receipts were not mutated.

## Issue-to-task mapping

| Issue | Severity | Criteria | Task | Classification | Executor | `[XHARD]` |
| --- | --- | --- | --- | --- | --- | --- |
| 1 changed-precondition authority remains forgeable | blocker | C19–C21; preserve C22; RW3-01; A3-03 | RW4-01 | Normal / GPT-5.6 Luna | Luna | none |
| 2 strict payload and typed-identity proof incomplete | blocker | C02, C13; RW3-01; A3-02 | RW4-02 | Normal / GPT-5.6 Luna | Luna | none |
| 3 applicable-key and recovery named proof missing | major | C11, C32, C33, C34, CP06, CP07; RW3-02; A3-04, A3-05 | RW4-03 | Normal / GPT-5.6 Luna | Luna | none |
| 4 composite and terminal-race evidence incomplete | major | C09, C28, CP08, CP11; RW3-03; A3-06 | RW4-04 | Normal / GPT-5.6 Luna | Luna | none |
| 5 durable confirmation equality matrix incomplete | major | C39; C41 regression; RW3-04; A3-07 | RW4-05 | Normal / GPT-5.6 Luna | Luna | none |
| 6 immutable executor evidence protocol incomplete | major | RW3-06; A3-08 | RW4-06 | Normal / GPT-5.6 Luna | Luna | none |
| Fresh execution + independent Luna review + Grok Oracle | gate | Batch 1 gate | RW4-GATE | Oracle | Luna review, Grok verdict | none |

All six accepted issues are mapped. None is omitted. No seventh implementation
issue is authorized. Adjacent seams were not combined: RW4-01 must close
coherent forgery before later writers touch `schema.py` / `ledger.py`.
File-ownership inspection did not require splitting RW4-01.

## Dependency order and model routing

```text
RW4-01 (Issue 1, C19–C21)
  -> RW4-02 (Issue 2, C02/C13)
  -> RW4-03 (Issue 3, keyed/recovery)
  -> RW4-04 (Issue 4, race/crash)
  -> RW4-05 (Issue 5, confirmation)
  -> RW4-06 (Issue 6, executor evidence)
  -> RW4-GATE
```

`ledger.py` has one writer at a time in that serial order. RW4-06 runs last
against the stable post-fix candidate. Issue 1 is not reordered behind
evidence-only work.

**Model routing:** every implementation, validation, and evidence task is
Normal / GPT-5.6 Luna. Deterministic schema, journal, reducer, behavioral-test,
and receipt corrections do not meet the exceptional threshold.
**`[XHARD]: none`.** Grok 4.6 remains Oracle and RW4-GATE only. This turn
did not dispatch Luna or Grok.

## Explicit exclusions (no task)

- C36, C37, or C38 reconciliation semantics (attempt-3 Grok: MET).
- C01 via overweight `PhaseResult.from_dict` round-trip expansion.
- C40 cache-mismatch or broad cache/projection-version matrix expansion.
- T8 thresholds, degradation policy, retry scheduling, or escalation policy.
- Restoring the two broad-suite missing modules or other environment repair.
- Custody edits or re-adjudication.
- Historical receipt/check-in rewrite or evidence normalization.
- Admission callers, scheduler, physical doors, launch adapters, signal-site
  wiring, fallback policy, family leases, rotators, second journal/store,
  prepare/commit, main merge, or Batch 2.

Attempt-3 Grok classified the broad-suite missing modules as
`PRE_EXISTING_OUT_OF_SCOPE_BLOCKER`. Attempt 4 records the full sweep in
RW4-06 and does not turn that environment issue into an implementation task.
C01/C40 remain unevidenced context and are not expanded.

Triage found **no concrete contradiction** between these exclusions and
Issues 1–6. Scope was not silently widened.

## Preservation

- Custody remains `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`.
  `f8725af...` historical; `798c506...` current. No further custody edit.
  RW-CUSTODY remains MET.
- Frozen tasklist remains `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`.
- Historical evidence remains historical: start-gate 52→61, unreproducible
  `4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70`,
  failed-handoff `50c864900a2f9d0fd5b6bc4240d97d365148e4cf2dd511749e9701fa059a09bf`,
  attempt-1 78/78 and `e060f650e112ecc8c73f4f2491e8504f3a1f1c9943b80f4e5aa97590b2925801`,
  attempt-2 `16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d`,
  attempt-3 `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8`.
  Focused 112 / legacy 78 remain observations, not targets.
- Prior-MET behavior named by the attempt-3 Grok verdict is required
  preserved: single `_IncidentEventJournal` and sequence-sidecar flock, one
  `_locked` NBF mutation door, C03–C08, C10, C12, C14–C18, C22, C25, C26
  shape, C27, C29 order, C30/C31 matching/rekey-at-one, C35–C38, C41,
  CP04 journal count, CP05 increment rule, CP09 type/state, CP10, RW-CUSTODY,
  A3-01, A3-09, RW3-05. Attempt-3 closures also preserved: persisted
  accepted-launch markers, positive OOM and legal unknown-death append paths,
  worker+success source rejection, keyed reducer without latest-stream
  mutation fallback, real composite fresh replay, `_emit_locked` failure
  injection, complete CLI 0/2/3/4/5 including expired/already-consumed,
  expiry-after-consume rejection, route-child wrapper deletion, one journal,
  one lock door.
- Attempt-3 owned production diff `8fe64464…` is the reviewed attempt-3
  identity, not an attempt-4 target. Attempt-3 artifacts must not be
  rewritten when the post-fix digest changes.

## Integrity statement

This Oracle read the required North Star, agent goal, custody, frozen
tasklist, freeze receipt, settled plan v8, all supplemental packets and
triage receipts through attempt 3, the attempt-3 executor finding/receipt,
the bound attempt-3 Luna review check-in/receipt, the bound attempt-3 Grok
verdict check-in/receipt, and `.oracle/briefs/oracle-nbf01-rework3-grok.md`.
Independent `shasum -a 256` and `git` identities matched the brief,
including attempt-3 production digest
`8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8`.
Independent re-read of `_authoritative_source`, `_produce_authoritative`,
the seven `produce_*` wrappers, `ChangedPrecondition.from_dict`,
`append_changed_precondition`, `consume_changed_precondition`,
`DispatchOutcome.__post_init__` / `from_dict`, `validate_nbf_event`,
`_project_records`, `append_probe_result`, `reserve_provider_route_child`,
`_emit_locked`, confirmation consume/expire, and the eight new NBF test
modules plus unchanged `test_incident_ledger.py` confirmed Issues 1–6 still
exist on the current candidate and that the listed exclusions do not
contradict them. This turn wrote only the attempt-4 supplemental packet and
this receipt.

## Confirmation of non-mutation

No production code, test code, frozen tasklist, settled plan, North Star,
custody, status, agent goal, or prior brief/check-in/finding/receipt was
edited. Nothing was staged, committed, pushed, merged, rebased, reset, or
cleaned. Batch 2 was not started. No executor or reviewer was dispatched.
`PASS_BATCH_1` is not issued.

## Next authorized action

Dispatch the Normal/Luna attempt-4 executor against
`.oracle/rework/batch-1-attempt-4.md`.

```text
REWORK_TASKLIST_READY
NBF-01_UNACCEPTED
BATCH_2_PROHIBITED
XHARD_NONE
CUSTODY_MET_NO_FURTHER_EDIT
NO_IMPLEMENTATION_PERFORMED
NO_PASS_BATCH_1
```
