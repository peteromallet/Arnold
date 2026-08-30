# Receipt — NBF-01 Batch 1 rework triage, attempt 3 (Grok 4.6)

- Oracle: Grok 4.6 (manager/validator only)
- Date: 2026-08-30
- Role: third supplemental rework triage after attempt-2 `ACCEPTED_ISSUES`
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
| Attempt-1 rework tasklist | `5149fdcf7fd91a255ec6cfe34f447a9b1eb46bf3b56db92a2e03939fbc9d1d2c` |
| Attempt-1 triage receipt | `7565016b618293fa666f61710f0f95bb8847d6d2336568ff064d8843699efa1e` |
| Attempt-2 rework tasklist | `6d625cc406ff7fe2c8764d6aae813005942a40203a01e346c290a2c6804be721` |
| Attempt-2 triage receipt | `3f1c460d06966d5eef2999e5e4b99e5324b2aa920609d10ffe2d54af81a41703` |
| Attempt-2 executor finding `.oracle/findings/execution-nbf01-rework2-luna.md` | `896cc4f1f657e8edb0c197465c14886e8cd08ae3c7e8b718941f560cea06a9bb` |
| Attempt-2 executor receipt `.oracle/receipts/execution-nbf01-rework2-luna.md` | `d03d259725484d4eac22cae1e2582288a85a2d2dbfbbfbba7a2b0878b9b02e51` |
| Attempt-2 Luna review brief | `b4647bc377366ef4e2f6eeeb8bfc24f480bc0dbe2de21858873bcad372cde456` |
| Attempt-2 Luna review `.oracle/checkins/batch-1-rework2-luna.md` | `bfc5e036f7d61827cd77ba4c0349318ce5c6beedfe832b50bfafe9270456668a` |
| Attempt-2 Luna review receipt | `53a69d3e8a4a232c63e7f25fcda279b0059162087a7d45244ba0bf8d271f6f2e` |
| Attempt-2 Grok check-in `.oracle/checkins/batch-1-rework2-grok.md` | `5ceb712841cb02a0abeb5142864b08107f86695020c872861dc1d1b8bc940455` |
| Attempt-2 Grok Oracle receipt | `622126f1a8ba909a6439a8f012c3e688c7c7bd4afe89ed1580bec1d06bb32e67` |
| Immutable source base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` |
| Candidate branch | `megado-nbf-guard-0826` |
| Planning HEAD | `922241d0bdb3e993c3b554cc69f19948adef7bc3` |
| Merge-base with `origin/main` | `798c50619204010ed3f4297fbb57988fe9381924` |
| Attempt-2 owned tracked-production diff (reviewed identity, not a future target) | `16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d` |

Supplemental tasklist written this turn:

- Path: `.oracle/rework/batch-1-attempt-3.md`
- SHA-256: `c4c93f8b14e253060c0a403869e22a23aadc6444e63b32f48fd55cf95b63e779`

Frozen `.oracle/tasklist.md`, settled plan v8, North Star, custody, status,
agent goal, historical evidence, and all prior briefs/check-ins/findings/
receipts were not mutated.

## Nine-issue-to-task mapping

| Issue | Severity | Task | Classification | Executor |
| --- | --- | --- | --- | --- |
| A3-01 terminal accepted-launch is self-authorized (C10) | blocker | RW3-01 | Normal | Luna |
| A3-02 payload and typed identity matrix holes (C02/C13/C14) | blocker | RW3-01 | Normal | Luna |
| A3-03 changed-precondition authority remains forgeable (C19–C21) | blocker | RW3-01 | Normal | Luna |
| A3-04 applicable provider stream is not selected (C11/C32/C33) | major | RW3-02 | Normal | Luna |
| A3-05 recovery/child authorization is not evidence-bound (C23/C34) | major | RW3-02 | Normal | Luna |
| A3-06 composite replay/crash and terminal-race evidence (C27/C28/C09) | major | RW3-03 | Normal | Luna |
| A3-07 confirmation and CLI evidence remains thin (C39/C41) | major | RW3-04 | Normal | Luna |
| A3-09 unofficial convenience surface remains | minor | RW3-05 | Normal | Luna |
| A3-08 immutable executor evidence protocol incomplete (RW2-04) | major | RW3-06 | Normal | Luna |
| Fresh execution + independent Luna review + Grok Oracle | gate | RW3-GATE | Oracle | Luna review, Grok verdict |

All nine confirmed issues are mapped. None is omitted. Adjacent seams are
combined only where one writer must own one overlapping file.

## Dependency order and model routing

```text
RW3-01 (A3-01, A3-02, A3-03)
  -> RW3-02 (A3-04, A3-05)
  -> RW3-05 (A3-09)
  -> RW3-03 (A3-06)
  -> RW3-04 (A3-07)
  -> RW3-06 (A3-08)
  -> RW3-GATE
```

`ledger.py` has one writer at a time in that serial order. RW3-04 is
independent of confirmation/CLI semantics but shares `ledger.py`, so it
waits. RW3-06 runs last against the stable post-fix candidate.

**Model routing:** every implementation task is Normal / GPT-5.6 Luna.
Deterministic schema, ledger, reducer, CLI, test, and evidence work does
not meet the exceptional threshold. **`[XHARD]: none`.** Grok 4.6 remains
Oracle and RW3-GATE only. This turn did not dispatch Luna or Grok.

A3-09 inspection: `reserve_provider_route_child_with_receipt` has no
production, test, frozen-tasklist, or settled-plan caller. The packet
requires deletion, not a typed wrapper.

## Preservation

- Custody remains `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`.
  `f8725af...` historical; `798c506...` current. No further custody edit.
- Frozen tasklist remains `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`.
- Historical evidence remains historical: start-gate 52→61, unreproducible
  `4aee815d…`, failed-handoff `50c86490…`, attempt-1 78/78 and `e060f650…`.
  Focused 101 / legacy 78 remain observations, not targets.
- Prior-MET behavior named by the attempt-2 Grok verdict is required
  preserved: single `_IncidentEventJournal` and sequence-sidecar flock, one
  `_locked` NBF mutation door, C03–C06, C08, C12, C15–C18, C22, C25, C26
  shape, C29 order, C30/C31 for matching streams, C35, real two-process
  reservation contention, no second journal/store, RW-CUSTODY.
- Attempt-2 owned production diff `16f6f854…` is the reviewed attempt-2
  identity, not an attempt-3 target. Attempt-2 artifacts must not be
  rewritten when the post-fix digest changes.

## Integrity statement

This Oracle read the required North Star, agent goal, frozen tasklist,
settled plan v8, both prior rework packets, both prior triage receipts,
original and attempt-1 Batch 1 Luna/Grok check-ins, model-policy receipt,
custody, and every bound attempt-2 Luna/Grok artifact in the brief.
Independent `shasum -a 256` and `git` identities matched the brief.
Independent re-read of `append_terminal_outcome`, `_project_records`,
`DispatchOutcome.__post_init__`, `validate_nbf_event`,
`ChangedPrecondition.produce`, `reserve_provider_route_child`,
`_emit_locked`, `expire_confirmation`, `_record_cli`, and the eight new
test modules plus unchanged `test_incident_ledger.py` confirmed the nine
holes still exist on the current candidate. This turn wrote only the
attempt-3 supplemental packet and this receipt.

## Confirmation of non-mutation

No production code, test code, frozen tasklist, settled plan, North Star,
custody, status, agent goal, or prior brief/check-in/finding/receipt was
edited. Nothing was staged, committed, pushed, merged, rebased, reset, or
cleaned. Batch 2 was not started. No executor or reviewer was dispatched.
`PASS_BATCH_1` is not issued.

## Next authorized action

Dispatch the Normal/Luna attempt-3 executor against
`.oracle/rework/batch-1-attempt-3.md`.

```text
REWORK_TASKLIST_READY
NBF-01_UNACCEPTED
BATCH_2_PROHIBITED
XHARD_NONE
CUSTODY_MET_NO_FURTHER_EDIT
NO_IMPLEMENTATION_PERFORMED
NO_PASS_BATCH_1
```
