# Receipt — NBF-01 Batch 1 rework triage, attempt 6 (Grok 4.6)

- Oracle: Grok 4.6 (manager/validator only)
- Date: 2026-08-30
- Role: sixth supplemental rework triage after attempt-5 `ACCEPTED_ISSUES`
- Implementation performed: **none**
- Review dispatch: **none**
- Luna dispatch: **none**
- Scout dispatch: **none** (no OpenRouter/credit failure to record)
- Production / test / frozen-plan / custody / historical-receipt edits: **none**
- Commit / push / merge / rebase / reset / clean / Batch 2: **none authorized, none performed**
- Batch 1 pass decision: **not authorized in this triage turn**
- `PASS_BATCH_1`: **not issued**
- `ACCEPTED_ISSUES`: **not issued from this triage brief**

## Source identities (verified this turn)

| Artifact | SHA-256 / git identity | Result |
| --- | --- | --- |
| `.oracle/northstar.md` | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` | MATCH |
| `.oracle/plan.md` (settled v8) | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` | MATCH |
| `.oracle/tasklist.md` (frozen) | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` | MATCH |
| `.oracle/custody.md` | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` | MATCH |
| `.oracle/agent_goal.md` | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` | MATCH |
| `.oracle/receipts/model-policy-grok-switch.md` | `0bb386bf6fff5f9a5197a57cea5789ee250231a163dfd01bbe828776e1cc5064` | MATCH |
| Tasklist-freeze receipt | `583955c6996bcc18e8fe05d323c30f5f77e489cdd5a66ecb1783ac42c9d24a24` | MATCH |
| Immutable source base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` | MATCH |
| Candidate branch | `megado-nbf-guard-0826` | MATCH |
| Planning HEAD | `922241d0bdb3e993c3b554cc69f19948adef7bc3` | MATCH |
| Merge-base with `origin/main` | `798c50619204010ed3f4297fbb57988fe9381924` | MATCH |
| Attempt-5 owned production diff | `7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411` | MATCH |
| Unchanged `test_incident_ledger.py` | SHA-256 `83e8464c9dfd289aa08de41d044257936072e29ae1d8648f52b84f441f79a195`; blob `44dc3adb87ad4dd077aed449c2f5ccc3526d8d93` | MATCH |

All four sealed attempt-5 gate artifacts MATCH the brief:

1. Luna check-in `.oracle/checkins/batch-1-rework5-luna.md` `670dbde42ab483ac36e08f2d1222d83b80a42248c6036d47cbeb77459649a8a6`
2. Luna receipt `.oracle/receipts/oracle-nbf01-rework5-luna.md` `4d96b1922cb6dca3b79c5d414092cb0407f49c32c95236e54fb08530994cc143`
3. Grok check-in `.oracle/checkins/batch-1-rework5-grok.md` `49c7bb1e94f828536be0800372d06aca55388667730870e1d5ee7e0efdf42aa6`
4. Grok receipt `.oracle/receipts/oracle-nbf01-rework5-grok.md` `537225951f608611b290c413a8e133a1a897f911c3ee49be9f13ea3bd03670ef`

Attempt-5 supporting artifacts independently rehashed MATCH:

| Artifact | SHA-256 | Result |
| --- | --- | --- |
| `.oracle/rework/batch-1-attempt-5.md` | `f2c2224d6b46eda303b1768a4a2e520fc08224eef9c93e506daa14ea3b2042d7` | MATCH |
| `.oracle/receipts/rework-triage-batch-1-attempt-5-grok.md` | `dedf5870dc889b137484202290925482b4813a742414233dc83ecd7c5fa18b5a` | MATCH |
| `.oracle/briefs/execution-nbf01-rework5-luna.md` | `78db1ef340df0dd87e8ab40ee31aa801eb163008ec7deb1247efdbefe343f13a` | MATCH |
| `.oracle/findings/execution-nbf01-rework5-luna.md` | `8cf68b20bb089f98639787c6aa1ad23d1ad24701843d802c4f79aa67eb77c197` | MATCH |
| `.oracle/receipts/execution-nbf01-rework5-luna.md` | `4acbb75c4bc9526265bf14438d194288bdf4aaf79cc63525f729830c6f93f160` | MATCH |

Historical attempt-4 identities, labeled historical, independently MATCH:

| Artifact | SHA-256 |
| --- | --- |
| Attempt-4 packet | `4df7024a285e3d0c373278dbd72aed98a0d5af26b05f1f880cf64e9f20a2d534` |
| Attempt-4 triage receipt | `3d20f7bc585e5b5495a38b7a2a26caf1050c90f6dc14f719a95d3203516cfa2c` |
| Attempt-4 execution brief | `25b981e7e20cda6e7aff2027074631dc3b713ec11b0015df81238138e484c79d` |
| Attempt-4 executor finding | `b277eced2d19b92a1a70a5496c40a75a19fc7e14aa116678dfad865aeef4d6c1` |
| Attempt-4 executor receipt | `8739b5ebf73d2d4bdb9d9c089e7da80b3005f230794c0fe2fae306428f1a247f` |
| Attempt-4 Luna check-in | `01b8f596c33342fd3529f3982c9bba2605cd3fa41c44d36a0091b3dd8330972c` |
| Attempt-4 Luna receipt | `de0c6265e58a477b120f944740d5b88ba1834347ae3829d3def4517922e345ee` |
| Attempt-4 Grok check-in | `81a0018acd1d61835988bcc623d265376ec2a3ec8cac8634a902199b750936cf` |
| Attempt-4 Grok receipt | `dfba88485d5e101e86aaec541131a22312bbebe1b910b90455c53545fe90a607` |
| Attempt-4 production diff | `aaaa86ba2de9775df83d9a35f561b5fdcb8428a448f3e561937f00edf85a6e41` |

Supplemental tasklist written this turn:

- Path: `.oracle/rework/batch-1-attempt-6.md`
- SHA-256: `b776d6cc5b090fb4cbb278ec5fff265cb5cf92896c22c0fe0fed066713609b83`
- Size: 39136 bytes

This receipt:

- Path: `.oracle/receipts/rework-triage-batch-1-attempt-6-grok.md`

Frozen `.oracle/tasklist.md`, settled plan v8, North Star, custody, status,
agent goal, historical evidence, and all prior briefs/check-ins/findings/
receipts were not mutated.

Current production identity `7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411`
is kept separate from historical attempt-4 `aaaa86ba…` and earlier digests.

## Git identity commands

Cwd for every command: `/Users/peteromalley/Documents/Arnold-oracle-nbf`.
Empty stderr SHA-256 is
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
Isolated transcript root: `/tmp/oracle-nbf01-rework6-grok/`.

| UTC start | argv | Exit | stdout SHA-256 | stderr SHA-256 | stdout |
| --- | --- | ---: | --- | --- | --- |
| 2026-08-30T05:12:06.154289+00:00 | `git rev-parse HEAD` | 0 | `6eefd4262d52ff083bbc92dc11f69973634a793c3576de7911331cc6911f4542` | empty | `922241d0bdb3e993c3b554cc69f19948adef7bc3` |
| 2026-08-30T05:12:06.192687+00:00 | `git rev-parse --abbrev-ref HEAD` | 0 | `d16a4b7e75934804a550403f7aeaede152310ae73b9091d09b5a60599bed7333` | empty | `megado-nbf-guard-0826` |
| 2026-08-30T05:12:06.233510+00:00 | `git rev-parse origin/main` | 0 | `9fedff586a6415779c6e0e9f8cbad5fd4e0c2e0b5e91379e5a28ec22753a1430` | empty | `798c50619204010ed3f4297fbb57988fe9381924` |
| 2026-08-30T05:12:06.264791+00:00 | `git merge-base HEAD origin/main` | 0 | `9fedff586a6415779c6e0e9f8cbad5fd4e0c2e0b5e91379e5a28ec22753a1430` | empty | `798c50619204010ed3f4297fbb57988fe9381924` |
| 2026-08-30T05:12:06.345+00:00 | `git log -1 --format=%H %s` | 0 | `84e0e37a9d2b398fef7ab286556664c588031bd6c5f87f7e8aad20b82a4cc421` | empty | `922241d0bdb3e993c3b554cc69f19948adef7bc3 megado: record Sol-Luna resume custody` |
| 2026-08-30T05:12:06.370+00:00 | `git diff origin/main --` six owned production files | 0 | `7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411` | empty | production diff, 161199 bytes |

Commands JSON inventory: `/tmp/oracle-nbf01-rework6-grok/commands.json`
SHA-256 `38862522c6029ccc8e0a0f923402184608bd4bc192ed67a54f74aa5ebdac028b`.
File-hash inventory JSON SHA-256
`eaf4e8ce67e772ac46aec21419eff7110087ca595e61525c8ad160a6fb208b85`.

`git status --porcelain` at first identity capture showed
`## megado-nbf-guard-0826` plus the already-dirty NBF production/test
files and untracked `.oracle` planning/evidence artifacts. This receipt
makes no clean-tree claim.

Owned-file SHA-256 / git-blob identities independently reproduced against
the attempt-5 inventory:

| Path | SHA-256 | git blob |
| --- | --- | --- |
| `incident/__init__.py` | `8a5afee7861ac777071f355e60627913b9a67a6178375ae141d57f983b75b923` | `e9d4ecd617ae4e7eadf0c0450cba0a73d0720f1b` |
| `incident/ledger.py` | `5506175a236792607aee13a0adc403e536d3c2076c391391cc9ed3f1fbe317f9` | `192f68694ad7cd29c1d28f74539fc7b9f2a82734` |
| `incident/schema.py` | `5c150cdc5a55769a209f216ea7954831f76f8aae64606bf36a14a003312a27b1` | `eedfad759321236ed217cc71943227a7cd122bca` |
| `incident/disposition.py` | `8edad79ca55a3e999ab325158f7ce4f2c247b8f9698b4f2677b1c05d57512cf5` | `74d640b20fe1b4c8edc58cbafd5d3d5756712ec3` |
| `orchestration/phase_result.py` | `b3621d08c8c0367b65a3d3fbba2abee10d42d90a14896ebd1f9f83e65dfc0d28` | `eb60256d6d4501dc97a37b90fe92191a611878ae` |
| `orchestration/phase_result_classify.py` | `a6a05b2c0689320bf3d2b6df89cc6d140592fbb3afc12702f76a3aff6dd3f641` | `6f14c61e1b95609858dbb7b49a5bfa4b98de1cf5` |
| `test_changed_precondition_producers.py` | `89b6e14ea7a1180b9c809cbae0d29d1461806f4a02254b6fa4a992594e67a215` | `0773a0f629712065d4f410502b316155f4b8cf89` |
| `test_incident_ledger_transactions.py` | `118f174629869fb9aa4a7dbe6cfa127d317d71f2bfb90b10dcdbd353e7e837f8` | `c91963087ae35fce9f50ae322663825e4642bb59` |
| `test_provider_route_projection.py` | `6d036f349fa14cf31f585996ca67033aeaa7b131b591958dcde1632cb656a949` | `6de73b1e16d59ade8c22c5428dfdad5b660b072c` |
| `test_reservation_reconciliation.py` | `8f2d756b8b7fd22b1f1c871829f593260e7a374c7b68e55a26c7870eb05f0a0e` | `2d2ec909688040de467fb82f16e0676c1e69e8cd` |
| `test_scheduling_conditions.py` | `2b5663dd1b8f787d74c1482ba88ce1800be1e1066d3778069e8c6a3dbca62eeb` | `fc54999a025f23d89860facda94b260d1d7e5bb3` |
| `test_supervision_confirmation.py` | `cc3648f366d4ed884f93de426182df3bcbd5f5146628fec0e80c36a68074f50c` | `2a5a3a88cbae92d69260c93525246846adeb3547` |
| `test_terminal_outcomes.py` | `70d05156ff467c79f4ccc55446e7b5d692d1f4d362a8a21021230c22f0e80915` | `1dcb901b9623e320642f4b96dae499e0c8e336a2` |
| `test_worker_disposition.py` | `61d85e93036f00426a857136dc3ca10a01b233128b8984b0cc02b75dfaa28a84` | `45b23313a67229de5d3bbb1c896ab7729b4d09da` |
| `test_incident_ledger.py` | `83e8464c9dfd289aa08de41d044257936072e29ae1d8648f52b84f441f79a195` | `44dc3adb87ad4dd077aed449c2f5ccc3526d8d93` |

## Independent named-proof probe

Probe script ran in-process against the live candidate modules after the
identity capture. Transcript:
`/tmp/oracle-nbf01-rework6-grok/rw6_probe.json`
SHA-256 `fc0885dc74083b733daeaab24e22ef55528f1ae8a3c3ae18ec9a9481073be6ec`.
Started during the 2026-08-30T05:12Z identity window.

Method: (1) replay
`test_incompatible_matrix_rejects_at_public_terminal_append` and the
named six-kind `from_dict` loop exactly as written; (2) build legal
`DispatchOutcome.to_dict()` records, mutate one incompatible field, and
drive construction, `from_dict`, `validate_nbf_event`, public
`append_terminal_outcome`, and public `append_disposition`; (3) drive
missing/bare/incomplete worker identities at those doors; (4) confirm
legal OOM, unknown-death, non-worker, and worker-disposition appends.

| Observation | Result |
| --- | --- |
| Named public-terminal loop, all six kinds | **rejected** `missing DispatchOutcome fields: [...]`. Never reached payload-family checks. `append_terminal_outcome` converts dicts via `DispatchOutcome.from_dict` (`ledger.py:684-685`). |
| Named six-kind `from_dict` loop, all six kinds | **rejected** the same missing-field set (`schema_version`, `provider_failure_key`, `reconciliation_event_id`, `terminal_outcome_event_id`, unused exclusive Nones). |
| Correctly shaped six-kind illegal pairings | **rejected** at ctor/`from_dict`/public terminal with intended payload-family messages (`no_launch cannot carry…`, `success cannot carry…`, `ordinary failure cannot carry success evidence`, `provider exhaustion cannot carry disposition/success evidence`, `worker_disposition cannot carry success evidence`). `validate_nbf_event` of complete terminal events matches those families for the four terminal kinds; scheduling kinds reject `invalid terminal outcome kind`. |
| Missing/bare/incomplete worker identity | source **rejects** at ctor/`from_dict`/`validate_nbf_event`/public terminal/public disposition. Named identity test still omits direct construction and public terminal append. |
| Legal OOM / unknown-death / non-worker / worker disposition public append | **accepted**. |
| Observed/non-worker named test | selected `schema_version` / empty-lifecycle / bare-string cases. Complete missing/fabricated victim, killer, subject, cause, and lifecycle identity at every applicable door is not present. |

This is a genuine named-proof defect, not a production acceptance bypass.
Green focused `123 passed` cannot substitute because the named tests
assert any `ValueError`.

## Frozen criterion wording independently re-read

Frozen `.oracle/tasklist.md` C01–C41 (lines 116–163) and CP01–CP11
(lines 190–200) were read in full. Surviving must-criteria:

- C02 (line 117): “Invalid kind/state combinations reject.”
- C13 (line 135): “Worker, observed-death, and non-worker disposition
  schemas reject incomplete or fabricated identities.”
- CP02 (line 191): schema fields and legal transitions match owned
  §§4.4–4.13, §4.16, §§4.19–4.21.
- CP11 (line 200): crash/contention/replay/torn-write/linkage/keyed-streak/
  TTL/incarnation/single-consumption tests pass — still NOT_MET through
  the C02/C13 named-proof gap, not through a new crash/race hole.

C19–C21 and C39 remain MET on attempt-5 evidence and were not reopened.

## Issue-to-task mapping

| Issue | Severity | Criteria | Task | Classification | Executor | `[XHARD]` | Disposition |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 named four-door / six-kind payload and typed-identity proof incomplete | major | C02, C13; RW5-02; RW4-02; A3-02; preserve C03–C08, C12, C14 | RW6-01 | Normal / GPT-5.6 Luna | Luna | none | **accepted** |
| Fresh execution + independent Luna review + Grok Oracle | gate | Batch 1 gate | later | Oracle | not dispatched | none | **not this turn** |

Exactly one implementation issue is mapped. None is omitted. No second
implementation issue is authorized.

## Accepted / rejected / duplicate / nonissue reasoning

**Accepted as RW6-01 (major).** Attempt-5 Luna and Grok both marked
C02/C13 / RW5-02 / RW4-02 / A3-02 NOT_MET as named proof. Independent
source read and the fresh probe reproduce it: correctly shaped records
are rejected at the intended doors; named tests still feed incomplete
dicts and never assert the payload-family or identity messages. North
Star “one door per invariant” and “deaths speak” remain incomplete as
*named evidence* while incidental missing-field `ValueError`s stand in
for typed payload-family checks. Not a production bypass.

**Rejected / not tasked (duplicates, nonissues, out of scope):**

- RW5-01 / C19–C21 authority — MET on attempt 5; duplicate if reopened.
- RW5-03 / C39 confirmation evidence equality — MET; duplicate if reopened.
- Residual `_IncidentEventJournal._emit_locked` journal-primitive
  exposure — attempt-5 Grok classified it outside the frozen RW5-01
  door set; not a second issue.
- RW4-03 keyed/recovery named proof — MET; duplicate if reopened.
- RW4-04 race/crash named proof — MET; duplicate if reopened.
- RW4-06 executor evidence protocol — MET; later execution writes new
  attempt-6 evidence, not a second issue.
- C01 via `PhaseResult.from_dict` — unevidenced context; do not expand.
- C40 cache-mismatch — unevidenced context; do not expand.
- C36–C38 reconciliation — MET; do not reopen.
- C41 CLI redesign — complete; regression rerun only if later execution
  evidence reruns it.
- Broad missing modules `arnold.agent.costing.model_resource_capabilities`
  and `tools.environments.singularity` —
  **`PRE_EXISTING_OUT_OF_SCOPE_BLOCKER`**, not an implementation task.
- Custody, historical receipts, admission, scheduler, physical doors,
  launch/signal/fallback policy, family leases, rotators, second stores,
  prepare/commit, merge, Batch 2 — excluded.
- Any `[XHARD]` reclassification — rejected. The work is one Normal/Luna
  named-test (and only if needed, minimal validator) task. Importance,
  file span, and prior incomplete attempts are not the exceptional
  threshold. No evidence that decomposition is insufficient or that the
  Normal pool cannot execute the kernel.

Optional scouts: **none attempted.** No OpenRouter 402/credit failure to
record. Oracle source/test inspection is the authoritative triage
evidence.

## Dependency order and model routing

```text
completed RW5-01 C19–C21
completed RW5-03 C39
  → RW6-01 C02/C13 complete six-kind/four-door payload and typed-identity matrix
  → later fresh Normal execution evidence, exactly one independent Luna review,
    and a separate Grok Oracle gate
```

One writer owns the overlapping schema/phase/ledger/test seams.

**Model routing:** every implementation, validation, and evidence task is
Normal / GPT-5.6 Luna. Deterministic named behavioral-test and optional
minimal validator correction do not meet the exceptional threshold.
**`[XHARD]: none`.** Grok 4.6 remains Oracle only. This turn did not
dispatch Luna or Grok, and did not implement.

## Explicit exclusions (no task)

- C19–C21 authority (closed in attempt 5).
- C39 confirmation equality (closed in attempt 5).
- C36, C37, or C38 reconciliation semantics.
- C01 via overweight `PhaseResult.from_dict` round-trip expansion.
- C40 cache-mismatch or broad cache/projection-version matrix expansion.
- T8 thresholds, degradation policy, retry scheduling, or escalation policy.
- Restoring the two broad-suite missing modules or other environment repair.
- Custody edits or re-adjudication.
- Historical receipt/check-in rewrite or evidence normalization.
- Admission callers, scheduler, physical doors, launch adapters, signal-site
  wiring, fallback policy, family leases, rotators, second journal/store,
  prepare/commit, main merge, or Batch 2.
- RW4-03, RW4-04, RW4-06 reopeners; C41 CLI redesign.

Triage found **no concrete contradiction** between these exclusions and
RW6-01. Scope was not silently widened.

Any broad-suite missing-module collection failures remain
`PRE_EXISTING_OUT_OF_SCOPE_BLOCKER`, not an implementation task.

## Preservation

- Custody remains `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`.
  `f8725af...` historical; `798c506...` current. No further custody edit.
  RW-CUSTODY remains MET.
- Frozen tasklist remains `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`.
- Historical evidence remains historical as listed above.
- Prior-MET behavior named by the attempt-5 Grok verdict is required
  preserved: single `_IncidentEventJournal` and sequence-sidecar flock,
  one `_locked` NBF mutation door, C03–C12, C14–C18, C19–C21, C22–C39,
  C41, CP04 journal count, CP05 increment rule, CP06–CP10,
  RW-CUSTODY, A3-01, A3-03 through A3-09, RW4-03, RW4-04, RW4-06,
  RW5-01, RW5-03. C02/C13 *source* rejection of correctly shaped illegal
  pairings must also stay; only the named proof is incomplete.
- Attempt-5 owned production diff `7b46da5c…` is the reviewed attempt-5
  identity, not an attempt-6 target. Attempt-5 artifacts must not be
  rewritten when the post-fix digest changes.

## Integrity statement

This Oracle read the required North Star, agent goal, custody, frozen
tasklist C01–C41 and CP01–CP11, freeze receipt, settled plan v8, all
supplemental packets and triage receipts through attempt 5, the
attempt-5 executor finding/receipt, the bound attempt-5 Luna review
check-in/receipt, and the bound attempt-5 Grok verdict check-in/receipt.
Independent SHA-256 and `git` identities matched the brief, including
attempt-5 production digest
`7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411`
and all four attempt-5 gate artifact hashes.

Oracle independently inspected `DispatchOutcome.__post_init__` /
`from_dict`, `_typed_worker_identity`, `validate_nbf_event`, public
`append_terminal_outcome` / `append_disposition`, and the named tests
in `test_worker_disposition.py`, `test_scheduling_conditions.py`, and
`test_terminal_outcomes.py`. Oracle independently reproduced the named
public-terminal missing-field hole and the correctly shaped six-kind
rejection matrix. No scout was attempted.

This turn did not implement, did not dispatch Luna or any reviewer, did
not stage/commit/push/merge/rebase/reset/clean, did not mutate frozen
tasklist/plan/status/agent goal/custody/North Star, did not rewrite
history or prior evidence, did not issue `PASS_BATCH_1` or
`ACCEPTED_ISSUES`, and did not start Batch 2. The only authorized
worktree writes by this Oracle turn are the attempt-6 supplemental
packet and this receipt.

```text
REWORK_TASKLIST_READY
NBF-01_UNACCEPTED
BATCH_2_PROHIBITED
XHARD_NONE
CUSTODY_MET_NO_FURTHER_EDIT
NO_IMPLEMENTATION_PERFORMED
NO_DISPATCH
NO_PASS_BATCH_1
NO_ACCEPTED_ISSUES_FROM_THIS_TRIAGE
RW6-01_SOLE_TASK
```
