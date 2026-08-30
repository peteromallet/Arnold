ACCEPTED_ISSUES

# Grok 4.6 Oracle verdict — NBF-01 / Batch 1 rework 4

**Verdict:** `ACCEPTED_ISSUES`

- Oracle: Grok 4.6 (manager/validator only; no implementation)
- Date: 2026-08-30
- Source base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924` (verified)
- Candidate branch: `megado-nbf-guard-0826`
- HEAD (planning, not NBF-01 code): `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- Merge-base with `origin/main`: `798c50619204010ed3f4297fbb57988fe9381924`
- Frozen tasklist SHA-256: `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- Settled plan v8 SHA-256: `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`
- North Star SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Custody SHA-256: `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`
- Agent goal SHA-256: `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864`
- Attempt-4 packet SHA-256: `4df7024a285e3d0c373278dbd72aed98a0d5af26b05f1f880cf64e9f20a2d534`
- Attempt-4 triage receipt: `3d20f7bc585e5b5495a38b7a2a26caf1050c90f6dc14f719a95d3203516cfa2c`
- Executor finding: `.oracle/findings/execution-nbf01-rework4-luna.md` (`b277eced2d19b92a1a70a5496c40a75a19fc7e14aa116678dfad865aeef4d6c1`)
- Executor receipt: `.oracle/receipts/execution-nbf01-rework4-luna.md` (`8739b5ebf73d2d4bdb9d9c089e7da80b3005f230794c0fe2fae306428f1a247f`)
- Luna review brief: `.oracle/briefs/oracle-nbf01-rework4-luna-review.md` (`901efaafab9af281c1e9e847b0790cd334ca436b9109890d33a8e0097ceb9096`)
- Luna review: `.oracle/checkins/batch-1-rework4-luna.md` (`01b8f596c33342fd3529f3982c9bba2605cd3fa41c44d36a0091b3dd8330972c`)
- Luna review receipt: `.oracle/receipts/oracle-nbf01-rework4-luna.md` (`de0c6265e58a477b120f944740d5b88ba1834347ae3829d3def4517922e345ee`)
- Gate brief: `.oracle/briefs/oracle-nbf01-rework4-grok.md` (`01cf0e10566043085028bc3c31a19c687b76aca0f12e917489e80013e631af8a`)
- Owned production diff SHA-256: `aaaa86ba2de9775df83d9a35f561b5fdcb8428a448f3e561937f00edf85a6e41`
- Isolated Oracle probe root: `/tmp/oracle-nbf01-rework4-grok/`
- Isolated Luna review root: `/tmp/oracle-nbf01-rework4-luna-review/`
- This check-in: `.oracle/checkins/batch-1-rework4-grok.md`
- This decision receipt: `.oracle/receipts/oracle-nbf01-rework4-grok.md` (`dfba88485d5e101e86aaec541131a22312bbebe1b910b90455c53545fe90a607`)

Do not commit, push, or begin Batch 2 on this candidate. `[XHARD]` remains none.

## Gate and evidence identity

Exactly one independent GPT-5.6 Luna full review was commissioned at high
reasoning. No second reviewer, fan-out, helper review, or Grok self-review was
commissioned. This turn is Oracle synthesis only.

Launcher:

```text
python /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py \
  --model="codex:gpt-5.6-luna:high" \
  --query-file=/Users/peteromalley/Documents/Arnold-oracle-nbf/.oracle/briefs/oracle-nbf01-rework4-luna-review.md \
  --project-dir=/Users/peteromalley/Documents/Arnold-oracle-nbf \
  --timeout=3600 \
  --metadata-file=/tmp/oracle-nbf01-rework4-gate/luna_launch.meta.json
```

Resolved model `openai-codex/gpt-5.6-luna`, thinking `high`. Start
`2026-08-30T03:13:33Z`, end `2026-08-30T03:33:29Z`, elapsed `1196.497s`,
launcher exit `0`. Metadata: `/tmp/oracle-nbf01-rework4-gate/luna_launch.meta.json`.

Every bound identity listed in the gate brief was independently rehashed and
matched, including historical attempt-3 artifacts labeled historical. Owned
tracked-production diff independently reproduces
`aaaa86ba2de9775df83d9a35f561b5fdcb8428a448f3e561937f00edf85a6e41`.
`tests/arnold_pipelines/megaplan/test_incident_ledger.py` is unchanged versus
`origin/main` (blob `44dc3adb87ad4dd077aed449c2f5ccc3526d8d93`, SHA-256
`83e8464c9dfd289aa08de41d044257936072e29ae1d8648f52b84f441f79a195`). Scope
remains the five modified production files, new `incident/disposition.py`, and
the eight named new test modules. RW-CUSTODY remains MET.

Executor stream SHA-256 values independently reproduced. Oracle independently
reran focused `121 passed in 18.90s` (stdout SHA-256
`4ecfb82fa61de97c12206a89fc3d64df05dbfd2e97d54ee97ce6341e22810edf`) and legacy
`78 passed in 1.33s` (stdout SHA-256
`8e785d2cefb3d1fa5ef35d4b67eb50c15777ef055b2393bfde2d150058e18b8e`). Luna
independently reran focused `121 passed in 17.43s` (stdout SHA-256
`eb007f81b56a64eda7073a78949932b1f77653d9df6ca93922045251646eba3b`) and legacy
`78 passed in 1.43s` (stdout SHA-256
`211dfb1591ec7c1c795a37c2c284e61936f83ace4f8e319ad3fbeaf9975392a8`). Counts
remain observations, not targets. `py_compile` and `git diff --check` exit 0
with empty-stream SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

Luna's check-in/receipt transcribe status-2 schema-invalid stderr as
`2525d332bcb4199a8f494836678960e858520cbd1e7242cac45f889b0cc7992ee`. The isolated
file `/tmp/oracle-nbf01-rework4-luna-review/cli_status_2_schema.stderr` is
`2525d332bcb419a8f494836678960e858520cbd1e7242cac45f889b0cc7992ee`, matching the
executor. That is a review-receipt transcription error, not a second review and
not a moving tree. Luna's receipt also garbles the broad-suite classification
paragraph around lines 97–100; the check-in classification is coherent and was
independently confirmed.

Historical evidence remains historical and was not rewritten: start-gate 52→61,
unreproducible `4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70`,
failed-handoff `50c864900a2f9d0fd5b6bc4240d97d365148e4cf2dd511749e9701fa059a09bf`,
attempt-1 78/78 and `e060f650e112ecc8c73f4f2491e8504f3a1f1c9943b80f4e5aa97590b2925801`,
attempt-2 production digest `16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d`,
attempt-3 production digest `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8`.
Current candidate digest `aaaa86ba2de9775df83d9a35f561b5fdcb8428a448f3e561937f00edf85a6e41`
is not an attempt-3 target.

Luna recommended `RECOMMEND_ACCEPTED_ISSUES`. Oracle independently re-read the
cited producer/append/reserve symbols and reproduced the coherent-forgery
wire-door probe. The blocker holds. A forged event accepted by `_append_nbf`
also authorized `IncidentLedger.reserve(...)`.

## Hard gates

| Gate | Status |
| --- | --- |
| One fresh immutable attempt-4 Luna execution receipt/finding | **MET** (per-file git hash-object / SHA-256 inventory present; dedicated RW4-06 command transcripts present; broad sweep retained verbatim) |
| Exactly one fresh independent Luna full review at required paths | **MET** |
| Candidate/diff and independent test-transcript digests recorded | **MET** via Luna review plus Oracle rehash/rerun |
| North Star disposition, KISS/YAGNI stated by Luna and Grok | **MET** as statements |
| All frozen NBF-01 must criteria met with behavioral evidence | **NOT_MET** |
| 52-vs-61 and `4aee815d…` treated as historical, not rewritten | **MET** |
| RW-CUSTODY unchanged | **MET** |

`PASS_BATCH_1` is unavailable because C19–C21 remain behaviorally false at the
canonical NBF append door, and two frozen named-proof contracts remain incomplete.

## Criterion dispositions

Statuses: `MET` | `NOT_MET` | `UNEVIDENCED`. Oracle confirmation is against the
post-attempt-4 candidate, Luna's isolated `/tmp/oracle-nbf01-rework4-luna-review/`
transcripts, and Oracle's independent `/tmp/oracle-nbf01-rework4-grok/` probes.

### NBF-01 acceptance criteria (tasklist)

| ID | Criterion | Status | Evidence |
| --- | --- | --- | --- |
| C01 | Strict round-trip of scheduling / six outcome kinds | **UNEVIDENCED** | Attempt 4 correctly did not reopen C01-as-`PhaseResult.from_dict` overweight. |
| C02 | Invalid kind/state/payload combinations reject | **NOT_MET** | Named `test_dispatch_outcome_incompatible_payload_matrix` is constructor-only for the six kinds. Decode/`validate_nbf_event`/`_append_nbf` cover only the worker-disposition+success pairing. Public `append_terminal_outcome`/`append_disposition` are not the named matrix doors. |
| C03 | `no_launch` cannot serialize with `launch_state=accepted` | **MET** | Constructor plus focused transcript. |
| C04 | `worker_disposition` required context | **MET** | Constructor plus named context tests. |
| C05 | Worker disposition cannot carry provider-exhaustion or no-launch state | **MET** | Constructor and `validate_nbf_event`. |
| C06 | Maps only to `worker_terminal_outcome(outcome_kind=worker_disposition)` | **MET** | Classify/append mapping tests. |
| C07 | Mapping validates exactly one already-committed matching disposition | **MET** as sequential CAS | Locked identical-replay. Concurrent distinct-ID proof is C09. |
| C08 | Never coerced into ordinary failure | **MET** | Named coercion test. |
| C09 | Duplicate linkage idempotent; conflicting linkage/kinds reject | **MET** | Required `test_two_process_terminal_linkage_is_atomic` now uses distinct IDs and conflicting kinds; Luna `cross_tx_full.json`. |
| C10 | Persisted accepted launch required | **MET** | Marker-bound terminal writer retained. |
| C11 | Disposition breaks consecutiveness without degradation | **MET** as named proof | Keyed reducer plus non-latest named tests in `test_provider_route_projection.py`. |
| C12 | `no_launch` produces no worker terminal/fingerprint/provider/streak | **MET** | Terminal writer rejects `no_launch` / `unresolved_launch`. |
| C13 | Worker / observed-death / non-worker reject incomplete or fabricated identities | **NOT_MET** as named proof | `_typed_worker_identity` is strong. Named identity test remains selected omissions/version/bare-string cases, not the complete four-door matrix. |
| C14 | OOM requires positive cgroup evidence; unknown death remains unknown | **MET** | Legal positive OOM and unknown-death append paths retained. |
| C15 | TERM and KILL ladder IDs are distinct | **MET** | Named test remains. |
| C16 | Semantic fingerprint excludes volatile liveness and logical/family IDs | **MET** | Named provider/fingerprint test. |
| C17 | Route-liveness digest absent from fingerprint and provider-failure key | **MET** | Same named test. |
| C18 | Same projection key + fingerprint contend for one reservation | **MET** | Real two-OS-process `fcntl.flock` race. |
| C19 | Only allowlisted reason-specific producers may mint changes | **NOT_MET** | Typed handles exist. `_validate_changed_precondition_wire` still treats self-consistent caller snapshots as valid wire. `_append_nbf` persists them. |
| C20 | Producer, evidence, subject, version, before/after, provider-key binding validated | **NOT_MET** | `append_changed_precondition` re-validates producer handles. The canonical NBF append door does not. |
| C21 | Forged unequal content IDs or provider-failure-key transitions reject | **NOT_MET** | Named coherent-forgery test rejects `from_dict`, public append, and consume. Independent Oracle and Luna probes: `validate_nbf_event` accepted, `_append_nbf` accepted, event projected. Oracle additionally authorized `reserve()` with the forged event id (`/tmp/oracle-nbf01-rework4-grok/authz_probes.json`). |
| C22 | Valid changed-precondition consumed at most once | **MET** | Locked consume; valid reader path consumes once. Producer authority remains C19–C21. |
| C23 | `provider_recovery_verified` may authorize one linked same-route child | **MET** | Lease-bound passed probe plus named recovery matrix. |
| C24 | Other allowlisted change resets/rekeys only when canonical before/after keys differ | **MET** as reducer | Keyed rekey tests pass. Forged key transitions remain C19–C21. |
| C25 | Ordinary two-process reservation contention yields one winner | **MET** | Same evidence as C18. |
| C26 | `provider_route_child_reserved` is one record and contains no child receipt-ID input | **MET** | Shape retained. |
| C27 | Receipt identity derives after append and reproduces byte-for-byte | **MET** | Real composite fresh replay retained. |
| C28 | Torn or failed writes cannot expose partial transitions | **MET** | Pre-append `_emit_locked` and post-append receipt-boundary crash/reopen proofs present. |
| C29 | Accepted terminal projects fingerprint state before reservation closure | **MET** | Reducer order retained. |
| C30 | Matching accepted `provider_exhausted` increments keyed streak | **MET** | Matching-stream increment retained. |
| C31 | Nonmatching accepted `provider_exhausted` rekeys at one | **MET** | Named rekey-at-one test. |
| C32 | Accepted worker success resets applicable streak and active key | **MET** as named proof | Required `test_success_for_non_latest_key_does_not_reset_latest` present. |
| C33 | Intervening ordinary failure or worker disposition breaks consecutiveness | **MET** as named proof | Required `test_ordinary_failure_breaks_only_applicable_stream` present. |
| C34 | Probe results and recovery preserve matching streak | **MET** | Canonical probe/recovery named tests present. |
| C35 | Scheduling, no-launch, unresolved, time, liveness refresh do not mutate provider streak | **MET** | No provider-terminal reducer branch. |
| C36 | Reconciliation permits only the three frozen resolutions | **MET** | Not reopened. |
| C37 | Recovered worker disposition links one existing canonical disposition | **MET** | Not reopened. |
| C38 | Blind release, conflicting reconciliation, and accepted-launch release as no-launch reject | **MET** | Not reopened. |
| C39 | Durable two-scan state survives restart; TTL, scan separation, identity equality | **NOT_MET** as named proof | Source compares TTL/expiry/policy/schema and `second_evidence_digest`. Named `test_confirmation_compares_pid_start_progress_incarnation_cause` never mutates or omits evidence. |
| C40 | Ledger lock, append, schema, projection-version, and cache failures fail closed | **UNEVIDENCED** | Attempt 4 correctly did not expand cache-mismatch. |
| C41 | Disposition CLI schema validation, acknowledgements, and exit codes match §4.21 | **MET** | Independent executor and Luna subprocesses cover 0/2/3/4/5 including expired and already-consumed replay. Status 0 is one JSON ack and does not signal. |

### Batch 1 checkpoint

| ID | Checkpoint | Status |
| --- | --- | --- |
| CP01 | Every NBF-01 focused test passes | **MET** as pytest gate only (Oracle: `121 passed in 18.90s`; Luna: `121 passed in 17.43s`). Does not cure ceremonial coverage. |
| CP02 | Schema fields and legal transitions match owned §§4.4–4.13, §4.16, §§4.19–4.21 | **NOT_MET** — C02 named matrix, C13 completeness, C19–C21, C39. |
| CP03 | `DispatchOutcome.kind=worker_disposition` is lossless and maps exactly once | **MET** | Sequential mapping plus required concurrent distinct-ID name. |
| CP04 | One incident-ledger authority | **MET** for journal count / lock door. The wire append still mints without producer handles. |
| CP05 | Accepted exhausted worker outcomes are the only increment inputs | **MET** |
| CP06 | `provider_recovery_verified` remains single-use retry authorization | **MET** |
| CP07 | Success resets; different-key rekeys at one; ordinary/disposition break consecutiveness | **MET** as named keyed proof; producer keys remain forgeable via C19–C21. |
| CP08 | Composite transition and child reservation remain one append with post-commit receipt | **MET** |
| CP09 | No-launch, unresolved, ordinary failure, provider exhaustion, and worker disposition are mechanically distinct | **MET** for type/state; illegal payload named matrix remains (C02). |
| CP10 | No second journal, store, prepare/commit, scheduler, rotator, or policy owner | **MET** |
| CP11 | Crash, contention, replay, torn-write, linkage, keyed-streak, TTL, incarnation, and single-consumption tests pass | **NOT_MET** | Real races/crashes exist; coherent producer forgery and confirmation evidence matrix remain. |

### Rework tasks

| ID | Status | Evidence |
| --- | --- | --- |
| RW4-01 | **NOT_MET** | Public producer path is guarded. Canonical `_append_nbf` / `validate_nbf_event` accept a coherent recomputed forgery and `reserve()` consumes it as authorization. |
| RW4-02 | **NOT_MET** | Named four-door matrix remains constructor-plus-one-pairing. |
| RW4-03 | **MET** | Required non-latest / recovery / lease names are present and green. |
| RW4-04 | **MET** | Distinct-ID terminal race and post-append composite crash/reopen proofs are present. |
| RW4-05 | **NOT_MET** | CLI 0/2/3/4/5 is independently proved (C41). Confirmation evidence-digest mismatch/omission is absent from the required named test. |
| RW4-06 | **MET** | Attempt-4 finding/receipt bind HEAD, source, production diff, per-file inventory, dedicated gate-command transcripts, and verbatim broad sweep. |
| RW4-GATE | **NOT_MET** | This Oracle gate returns `ACCEPTED_ISSUES`. |
| RW-CUSTODY | **MET** | Custody SHA `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` unchanged. |

### A3 dispositions

| A3 item | Status | Hole closed? |
| --- | --- | --- |
| A3-01 | **MET** | Fully populated terminal without persisted accepted marker rejects. |
| A3-02 | **NOT_MET** | Named matrix is still not a complete four-door six-kind proof. |
| A3-03 | **NOT_MET** | Coherent recomputed forgery accepted at `validate_nbf_event` and `_append_nbf`; projected; authorized `reserve()`. |
| A3-04 | **MET** | Required non-latest named tests are present. |
| A3-05 | **MET** | Canonical probe binding and negative matrix are present. |
| A3-06 | **MET** | Distinct terminal race and post-append crash are present. |
| A3-07 | **NOT_MET** | CLI complete; confirmation evidence-digest named matrix is not. |
| A3-08 | **MET** | Attempt-4 executor inventory/stream completeness is present. |
| A3-09 | **MET** | Unofficial `reserve_provider_route_child_with_receipt` remains absent. |

## Broad-suite relevance classification

Oracle independently reran focused/legacy/compile/diffcheck. Luna independently
reran `pytest -q tests/arnold_pipelines/megaplan` (exit 2; stdout SHA-256
`fe5ee29bc0a5dc6c64b50b148a20f01128422c47042d84b06570ce0f2fee817e`). Executor
broad stdout SHA-256
`8fb59a66f2a82c1b28b58912dce97aecc50c5511677ea3bd9a034b4081646c5c` independently
reproduced. Both collection failures remain:

1. `test_cli_check_validator.py` → `arnold.workflow.validator` → `arnold.agent.costing.model_resource_capabilities`.
2. `test_key_pool_codex.py` → `arnold.agent.run_agent` → `arnold.agent.tools.terminal_tool` → `tools.environments.singularity`.

Both modules are absent on the candidate and absent at `origin/main`. No owned
attempt-4 file introduced, removed, or newly reached either import.
Classification for both: **PRE_EXISTING_OUT_OF_SCOPE_BLOCKER**. This reduces
broad-suite coverage and does not waive any NBF criterion.

## Preserved prior-MET result

Independently confirmed intact: one `_IncidentEventJournal` + sequence-sidecar
flock; NBF writes still enter `_locked` / `_append_nbf_locked` for the public
producer path; C03–C08, C09 named race, C10, C12, C14–C18, C22, C23–C28 named
proofs, C29–C35, C36–C38; CP04 journal count, CP05 increment rule, CP06–CP08,
CP10; real two-process reservation contention; owned source scope; RW-CUSTODY;
historical-evidence integrity; CLI 0/2/3/4/5. Attempt 4 additionally closed
RW4-03/RW4-04/RW4-06/A3-08 without opening a second journal or later-batch
door. Preservation is not Batch 1 acceptance.

## North Star

1. **One door per invariant — NOT MET for the Batch 1 primitive.** One journal
   and one flock remain. `_append_nbf` plus `_validate_changed_precondition_wire`
   still mint a second informal changed-precondition path beside the
   allowlisted producer handles. Oracle independently authorized `reserve()`
   from that path.
2. **Deaths speak — foundation only.** Typed worker / observed-death /
   non-worker records, positive OOM, legal unknown death, and a non-signalling
   CLI exist. Signal-site wiring is correctly deferred.
3. **Models are admitted, not assumed — correctly deferred.** No
   admission/catalog/live-provider caller changed.
4. **Fixes ship on main through the fixer contract — not evidenced.** No
   commit/push/merge, as required for this uncommitted gate.

### Anti-patterns

- **Single-scan verdicts as sustained truth — NOT MET as complete confirmation
  identity.** Locked TTL/policy compare exists; evidence-digest named matrix
  does not.
- **Anonymous integer exit codes — MET for the owned CLI primitive.** Typed
  disposition records and CLI 0/2/3/4/5 are independently bound.
- **Judgment-based “healthy” claims — improved, not closed.** Terminal
  acceptance still requires a persisted accepted-launch marker. Changed
  precondition still accepts a well-formed caller snapshot at the wire door.
- **Identical-fingerprint redispatch without a changed precondition — NOT MET
  as a complete durable block.** Two-process reservation contends. A coherent
  forged change can still be appended via `_append_nbf` and used as
  authorization.

## KISS / YAGNI / scope creep

- **File scope:** MET. No admission caller, scheduler, T7/T8 policy, physical
  door, launch adapter, signal site, fallback policy, second journal, or
  rotator was added.
- **KISS:** NOT MET at quality. `_locked` is the right small door.
  `_validate_changed_precondition_wire` is still a self-hash adapter wearing
  an authority name. `_source_handles` is process-local and therefore
  invisible to the canonical append door.
- **YAGNI:** MET in batch boundary; no UnitOfWork / two-phase / extra
  projection service.
- **Ceremonial validation:** NOT MET. Named coherent-forgery, six-kind matrix,
  and confirmation-evidence tests remain thin or bypassable. Green 121/78
  cannot substitute.
- **Later-batch behavior in the candidate:** MET (absent).

## Independent confirmation of Luna blockers

Oracle read the cited symbols and independently reproduced the coherent-forgery
path, then one step further than Luna.

1. `_authoritative_source` now requires a typed `_AuthoritativeSourceHandle`.
   `ChangedPrecondition.from_dict` raises. Public `append_changed_precondition`
   calls `_validate_producer_binding`.
2. `_validate_changed_precondition_wire` (`schema.py:556-601`) still accepts a
   caller dict whose snapshots hash to the cited IDs. `validate_nbf_event`
   routes `changed_precondition` through that function (`schema.py:1010-1011`).
3. `_append_nbf` (`ledger.py:438-447`) validates only through
   `validate_nbf_event`, then emits. Oracle probe
   `/tmp/oracle-nbf01-rework4-grok/bypass_probes.json` and Luna
   `wire_forgery_probe.json` (stdout SHA-256
   `4a292ceb0c1dff3ce9d26125ab82293e6bf5f2013cc8e77be48bec111aabd6aa`) both
   accepted decode-via-wire and raw append.
4. `_project_records` then stores the forged event (`ledger.py:573-582`).
   `reserve()` (`ledger.py:628-631`) treats any projected unconsumed change as
   authorization. Oracle `authz_probes.json` (SHA-256
   `ee31dfee57767a322fe590b3f23a4b8a457eb55ece221179913fc9f708839a1d`):
   `reserve_with_forged_change_fresh_fp.status = ACCEPTED`.
5. Named `test_dispatch_outcome_incompatible_payload_matrix` remains
   constructor-only for six kinds; only worker+success reaches decode/validate
   /`_append_nbf`.
6. Named confirmation identity test omits evidence-digest mismatch/omission.
7. RW4-03/RW4-04/RW4-06 named proofs are present and independently green.

## Issues

Each issue is a required correction. Do not implement in this Oracle turn.

1. **blocker — changed-precondition authority remains forgeable at the
   canonical append door (C19–C21, RW4-01, A3-03).**
   Symbols: `_validate_changed_precondition_wire`, `validate_nbf_event`,
   `_append_nbf`, `_project_records`, `reserve`.
   Evidence: Luna `wire_forgery_probe.json` stdout SHA-256
   `4a292ceb0c1dff3ce9d26125ab82293e6bf5f2013cc8e77be48bec111aabd6aa`; Oracle
   `bypass_probes.json` SHA-256
   `10902f023236bf899323a23588f7ce0c6afa59e0b5fd50a1b66906f391649602`; Oracle
   `authz_probes.json` SHA-256
   `ee31dfee57767a322fe590b3f23a4b8a457eb55ece221179913fc9f708839a1d`. Named
   coherent-forgery test does not exercise `_append_nbf` or `reserve()`.
   Smallest correction: reject caller-shaped wire snapshots at
   `validate_nbf_event` / `_append_nbf` unless they carry producer-bound
   handles; keep one journal/lock; add the independent wire-door plus
   reserve-authorization regression. Do not invent a second store.

2. **major — required strict matrix evidence is incomplete (C02/C13, RW4-02,
   A3-02).**
   Evidence: named matrix is constructor-only except one worker+success
   pairing; typed identity named coverage is selected.
   Smallest correction: strengthen the existing named tests in place across
   constructor, decode, `validate_nbf_event`, and public locked append.

3. **major — durable confirmation evidence-digest equality is incomplete
   (C39, RW4-05, A3-07).**
   Evidence: CLI 0/2/3/4/5 is independently complete (C41). Named confirmation
   test omits evidence-digest mismatch/omission.
   Smallest correction: add explicit wrong and missing second-evidence cases
   to the existing named test.

## Recommendation

Attempt 4 landed real progress: typed source handles on the public producer
path, keyed non-latest named proofs, lease-bound probes, distinct-ID terminal
race, post-append composite crash/reopen, complete executor inventory, and
CLI 0/2/3/4/5. The Batch 1 primitive still admits a coherent forged
changed-precondition at `validate_nbf_event` and `_append_nbf`, projects it,
and authorizes `reserve()`. Green 121/78 cannot close that hole. Batch 2
remains prohibited.

Smallest next action: write `.oracle/rework/batch-1-attempt-5.md` covering
issues 1–3 only, in serial order starting with the C19–C21 wire/private-append
/reserve-authorization blocker. Keep classification **Normal / GPT-5.6 Luna**;
`[XHARD]` remains none. Do not reopen C36–C38, C01-as-`PhaseResult.from_dict`
overweight, C40 cache-mismatch expansion, T8 policy, custody, historical
receipts, environment repair, or Batch 2. Then dispatch Luna, require one
complete HEAD-bound execution receipt, then one fresh independent Luna review
and a separate Grok Oracle gate. Do not implement, commit, push, merge, edit
custody, rewrite historical receipts, or start Batch 2 in this turn.

```text
ACCEPTED_ISSUES
```
