# Grok 4.6 Oracle verdict — NBF-01 / Batch 1 rework 2

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
- Attempt-2 rework tasklist SHA-256: `6d625cc406ff7fe2c8764d6aae813005942a40203a01e346c290a2c6804be721`
- Executor receipt: `.oracle/receipts/execution-nbf01-rework2-luna.md` (`d03d259725484d4eac22cae1e2582288a85a2d2dbfbbfbba7a2b0878b9b02e51`)
- Executor findings: `.oracle/findings/execution-nbf01-rework2-luna.md` (`896cc4f1f657e8edb0c197465c14886e8cd08ae3c7e8b718941f560cea06a9bb`)
- Luna review brief: `.oracle/briefs/oracle-nbf01-rework2-luna-review.md` (`b4647bc377366ef4e2f6eeeb8bfc24f480bc0dbe2de21858873bcad372cde456`)
- Luna review: `.oracle/checkins/batch-1-rework2-luna.md` (`bfc5e036f7d61827cd77ba4c0349318ce5c6beedfe832b50bfafe9270456668a`)
- Luna review receipt: `.oracle/receipts/oracle-nbf01-rework2-luna.md` (`53a69d3e8a4a232c63e7f25fcda279b0059162087a7d45244ba0bf8d271f6f2e`)
- This check-in: `.oracle/checkins/batch-1-rework2-grok.md`
- This decision receipt: `.oracle/receipts/oracle-nbf01-rework2-grok.md`

Do not commit, push, or begin Batch 2 on this candidate. `[XHARD]` remains none.

## Gate and evidence identity

Exactly one fresh independent GPT-5.6 Luna full review was commissioned. No second reviewer, fan-out, or self-review.

Independently verified frozen identities match the brief. Owned production diff independently reproduces `16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d`. Owned untracked file hashes match the executor finding. `test_incident_ledger.py` is unchanged versus `origin/main`. Scope remains the five modified production files, new `incident/disposition.py`, and the eight named new test modules.

Luna independently reproduced focused `101 passed in 14.11s` (stdout SHA-256 `1996f644e0e8cea7e6cc65ae3b0b8215b9a139b9996049bcb91160cc25f85292`) and legacy `78 passed in 1.52s` (stdout SHA-256 `a96ce9348b20653cb0c42b3ca9a255dd7cad88327a9c7506d2017b889095c310`). CLI 0/2/3/4/5 independent subprocess transcripts exist under `/tmp/oracle-nbf01-rework2-luna/`. Status 0 emitted one JSON acknowledgement with a consumed matching worker confirmation and did not signal. `py_compile` and `git diff --check` exit 0 with empty-stdout SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

The attempt-2 executor receipt exists and is the single execution artifact, but it fails the hard evidence protocol: no explicit candidate HEAD, truncated `git diff --check` digest `e3b0c44298fc1c1499b934ca495991b7852b855`, no per-command stderr SHA-256, and CLI 0/2/3/4/5 cited as pytest names rather than independent subprocess transcripts. Luna’s `/tmp` transcripts are the bound current command evidence. Luna’s review receipt also dropped two hex characters from the executor-receipt SHA (`…bfbbba7a…` vs independently recomputed `…bfbbfbba7a…`); that is a review-receipt transcription error, not a second executor artifact. Oracle uses the independently recomputed hash above.

Historical evidence remains historical and was not rewritten: start-gate 52→61, unreproducible `4aee815d…`, failed-handoff `50c86490…`, attempt-1 78/78 and `e060f650…`. Current focused **101** is an observation, not a target.

Luna recommended `RECOMMEND_ACCEPTED_ISSUES`. Oracle independently re-read the cited symbols and Luna’s source/provider probes. The blockers hold.

## Hard gates

| Gate | Status |
| --- | --- |
| One fresh immutable attempt-2 Luna execution receipt/finding | **MET as an artifact; NOT_MET as protocol completeness** (HEAD missing, abbreviated command/CLI evidence) |
| Exactly one fresh independent Luna full review at required paths | **MET** |
| Candidate/diff and independent test-transcript digests recorded | **MET** via Luna review, not the executor receipt |
| North Star disposition, KISS/YAGNI stated by Luna and Grok | **MET** as statements |
| All frozen NBF-01 must criteria met with behavioral evidence | **NOT_MET** |
| 52-vs-61 and `4aee815d…` treated as historical, not rewritten | **MET** |
| RW-CUSTODY unchanged | **MET** |

`PASS_BATCH_1` is unavailable because the must-criterion gate and the executor-evidence protocol both fail.

## Criterion dispositions

Statuses: `MET` | `NOT_MET` | `UNEVIDENCED`. Oracle confirmation is against the post-attempt-2 candidate plus Luna’s reproduced commands and probes. Luna numbering is preserved. Oracle calibrations are noted.

### NBF-01 acceptance criteria (tasklist)

| ID | Criterion | Status | Evidence |
| --- | --- | --- | --- |
| C01 | Strict round-trip of scheduling / six outcome kinds; unknown-field rejection | **NOT_MET** (partial) | `DispatchOutcome.from_dict` / `SchedulingCondition.from_dict` reject unknown/missing fields (`phase_result.py:141-208`). Named matrix is rejection-only. Luna’s `PhaseResult.from_dict` overweight remains rejected; that is not the C01 door. |
| C02 | Invalid kind/state/payload combinations reject | **NOT_MET** | Ordinary-failure+`success_payload` and provider-exhausted+`terminal_failure` now reject (`phase_result.py:180-191`). `worker_disposition` still accepts `success_payload` (`:169-173`). Luna probe `worker_disposition_success_payload=accepted`. |
| C03 | `no_launch` cannot serialize with `launch_state=accepted` | **MET** | `phase_result.py:151-155`; named test remains. |
| C04 | `worker_disposition` requires accepted launch, disposition_id, receipt, fingerprint, phase/spec, logical/worker identity, start/finish | **MET** | `phase_result.py:156-171`; valid-shape round-trip remains. |
| C05 | Worker disposition cannot carry provider-exhaustion or no-launch state | **MET** | `phase_result.py:159-173`. Does not cure C02 success-payload hole. |
| C06 | Maps only to `worker_terminal_outcome(outcome_kind=worker_disposition)` | **MET** | `phase_result_classify.py:204-218`; `ledger.py:715` writes `outcome.kind`. |
| C07 | Mapping validates exactly one already-committed matching disposition; never re-appends it | **MET** as sequential CAS | Locked check at `ledger.py:688-694`; recovered-disposition and sequential once-link tests exist. Concurrent distinct-ID proof remains C09. |
| C08 | Never coerced into ordinary failure | **MET** | `phase_result.py:174-175`; named coercion test remains. |
| C09 | Duplicate linkage idempotent; conflicting linkage/kinds reject | **NOT_MET** | `test_two_process_terminal_linkage_is_atomic` races the **same** outcome/ID (`test_incident_ledger_transactions.py:81-102`); event-ID idempotency makes both `ok`. Distinct terminal IDs/kinds are not raced. |
| C10 | Reservation closure and terminal-fingerprint projection occur exactly once | **NOT_MET** | Context compare exists under `_locked` (`ledger.py:659-718`). No persisted `controlled_adapter_state` accepted marker is required. Replay sets `accepted_launch=True` from the terminal itself (`:573-575`). Luna probe `terminal_without_persisted_accepted_marker.accepted=true`. |
| C11 | Worker disposition breaks provider-exhaustion consecutiveness without entering degradation | **NOT_MET** (keyed) | Streams exist (`ledger.py:552-569`), but success/ordinary/disposition without a key mutate `latest_stream_key` for `active_base` (`:557-569`). Luna probe: success for A after B was latest left A at streak 2 and reset B to 0. |
| C12 | `no_launch` produces no worker terminal/fingerprint/provider/streak | **MET** | Terminal writer rejects `no_launch`/`unresolved_launch` (`ledger.py:657-658`). |
| C13 | Worker / observed-death / non-worker schemas reject incomplete or fabricated identities | **NOT_MET** | Version/enum checks exist. Worker fingerprint is a non-empty string; worker identity is any non-empty dict; named append coverage is still selected cases. |
| C14 | OOM requires positive cgroup evidence; unknown death remains unknown | **NOT_MET** as complete criterion | Constructor rules are typed (`schema.py:127-132,368-384`). Named append-path matrix does not cover every false/zero/negative OOM and both fabricated killer and signal. |
| C15 | TERM and KILL ladder IDs are distinct | **MET** | `schema.py:339-341`; named test remains. |
| C16 | Semantic fingerprint excludes volatile liveness and logical/family IDs | **MET** | `schema.py:205-237`; named test remains. |
| C17 | Route-liveness digest absent from fingerprint and provider-failure key | **MET** | `schema.py:259-277`. |
| C18 | Different logical IDs with same projection key + fingerprint contend for one reservation | **MET** | Locked `reserve` (`ledger.py:611-649`); `test_two_process_reservation_contention_one_winner` remains a real two-OS-process race. |
| C19 | Only allowlisted reason-specific producers may mint changes | **NOT_MET** | Reason wrappers still route through generic `ChangedPrecondition.produce` that accepts caller `before`/`after`/`evidence` (`schema.py:516-539,657+`). |
| C20 | Producer, evidence, subject, version, before/after, provider-key binding validated | **NOT_MET** | IDs are hashes of caller snapshots (`schema.py:538-539`). Append checks snapshot equality, not authoritative source derivation. |
| C21 | Forged unequal content IDs or provider-failure-key transitions reject | **NOT_MET** | `test_forged_valid_hex_content_ids_reject` mutates `after_content_id` without recomputing `event_id`. Luna probe `forged_provider_transition=accepted` via `from_dict`. |
| C22 | Valid changed-precondition consumed at most once | **MET** | Locked consume (`ledger.py:934-944`); `test_consumed_change_cannot_authorize_second_reservation` exists. Producer authority remains C19–C21. |
| C23 | `provider_recovery_verified` may authorize one linked same-route child without resetting/rekeying | **NOT_MET** | `reserve_provider_route_child` (`ledger.py:746-775`) rejects a repeated authorizer but does not require a passed canonical probe plus evidence-bound recovery consume. |
| C24 | Other allowlisted change resets/rekeys only when canonical before/after keys differ | **NOT_MET** | Reducer rekeys from caller-carried before/after (`ledger.py:576-585`) without authoritative derivation. |
| C25 | Ordinary two-process reservation contention yields one winner | **MET** | Same evidence as C18. |
| C26 | `provider_route_child_reserved` is one record and contains no child receipt-ID input | **MET** for shape | One append; no child receipt-ID argument. Authorization remains C23. |
| C27 | Receipt identity derives after append and reproduces byte-for-byte after fresh replay | **NOT_MET** | `test_fresh_replay_receipt_is_byte_identical` is still an ordinary reservation (`test_provider_route_projection.py:44-49`). Composite case is a different name. |
| C28 | Torn or failed writes cannot expose partial transitions, receipts, or projections | **NOT_MET** | `test_torn_composite_write_exposes_neither_transition_nor_receipt` writes a truncated JSON prefix (`test_incident_ledger_transactions.py:36-42`); it does not inject during `_emit_locked` of a real composite. |
| C29 | Every accepted terminal outcome projects fingerprint state before reservation closure | **MET** for reducer order | Provider/fingerprint reduction runs before `closed=True` (`ledger.py:559-575`). Self-authorized accepted-launch remains C10. |
| C30 | Matching accepted `provider_exhausted` increments keyed streak | **MET** for matching stream | Increment at `ledger.py:559-562`; matching keyed test exists. Isolation failures are C11/C32. |
| C31 | Nonmatching accepted `provider_exhausted` rekeys at one | **MET** for first observation of a new key | `test_nonmatching_key_rekeys_at_one` asserts both streams at 1. Does not cure latest-stream targeting. |
| C32 | Accepted worker success resets applicable streak and active key | **NOT_MET** | Success without a key uses `latest_stream_key` (`ledger.py:557-566`). Probe reset the wrong stream. |
| C33 | Intervening ordinary failure or worker disposition breaks consecutiveness without becoming degradation | **NOT_MET** as keyed behavior | Same latest-stream fallback (`ledger.py:567-569`). Named disposition test covers one stream. No T8 degradation policy (correctly out of scope). |
| C34 | Probe results and `provider_recovery_verified` create/consume preserve matching streak | **NOT_MET** | Probes have no streak branch; recovery/child authorization is not evidence-bound (C23). |
| C35 | Scheduling, no-launch, unresolved, time, liveness refresh do not mutate provider streak | **MET** as primitive | Those events have no provider-terminal reducer branch. |
| C36 | Reconciliation permits only positive `released_no_launch`, recovered terminal, or durable ambiguous hold | **NOT_MET** | Arbitrary nonempty marker IDs are tighter, but a generic persisted `controlled_adapter_state` still authorizes release; sequencing provenance is not proven. |
| C37 | Recovered worker disposition links one existing canonical disposition and never duplicates | **NOT_MET** | Recovered-disposition test appends the terminal first; recovery does not itself establish matching disposition/terminal context. |
| C38 | Blind release, conflicting reconciliation, and accepted-launch release as no-launch reject | **NOT_MET** | Conflict/identical replay exists. Accepted/closed release and authoritative marker provenance are incomplete. |
| C39 | Durable two-scan state survives restart; TTL, scan separation, identity equality, single consumption, replacement/expiry | **NOT_MET** | Locked five-field compare exists. Required same-name test mutates only process-start. `expire_confirmation` can overwrite consumed with expired. |
| C40 | Ledger lock, append, schema, projection-version, and cache failures fail closed | **NOT_MET** | `_locked` / `_append_nbf_locked` wrap NBF writes; invalid replay now raises. Named fail-closed test is reservation-version only; cache-mismatch CAS is absent. |
| C41 | Disposition CLI schema validation, acknowledgements, and exit codes match §4.21 | **NOT_MET** | Independent subprocesses reached 0/2/3/4/5; status 0 is a consumed worker confirmation. Named status-5 matrix omits expired and a distinct already-consumed replay. |

### Batch 1 checkpoint

| ID | Checkpoint | Status |
| --- | --- | --- |
| CP01 | Every NBF-01 focused test passes | **MET** as pytest gate only (Luna: `101 passed in 14.11s`). Does not cure thin/ceremonial coverage. |
| CP02 | Schema fields and legal transitions match owned §§4.4–4.13, §4.16, §§4.19–4.21 | **NOT_MET** — C01/C02 remainder, C13, C14 append-path, C36–C41. |
| CP03 | `DispatchOutcome.kind=worker_disposition` is lossless and maps exactly once | **NOT_MET** — sequential mapping is lossless; concurrent distinct-ID and accepted-launch proof are not (C09, C10). |
| CP04 | One incident-ledger authority | **MET** for journal count / lock door; **NOT_MET** as complete contract. |
| CP05 | Accepted exhausted worker outcomes are the only increment inputs | **MET** for current replay; keyed isolation is still not (C11). |
| CP06 | `provider_recovery_verified` remains single-use retry authorization while preserving streak | **NOT_MET** — C23. |
| CP07 | Success resets; different-key rekeys at one; ordinary/disposition break consecutiveness; only authoritative key change otherwise resets/rekeys | **NOT_MET** — C11, C24, C32, C33. |
| CP08 | Composite transition and child reservation remain one append with post-commit replay-stable receipt | **NOT_MET** as complete proof — shape exists; required same-name composite replay/crash incomplete. |
| CP09 | No-launch, unresolved, ordinary failure, provider exhaustion, and worker disposition are mechanically distinct | **MET** for type/state; illegal payload combinations remain (C02). |
| CP10 | No second journal, store, prepare/commit, scheduler, rotator, or policy owner | **MET**. |
| CP11 | Crash, contention, replay, torn-write, linkage, keyed-streak, TTL, incarnation, and single-consumption tests pass | **NOT_MET**. Reservation two-process contention is real; terminal race, composite crash, and several named tests remain ceremonial. |

### Rework tasks

| ID | Status | Evidence |
| --- | --- | --- |
| RW2-01 | **NOT_MET** | Lock/read/compare/append is real; C18/C25 preserved. Terminal accepted-launch is self-derived; producers remain caller-hashed; payload/identity matrix incomplete. |
| RW2-02 | **NOT_MET** | Keyed streams and matching/rekey-at-one exist. Success/disposition target `latest_stream_key`. Required same-name composite replay is still ordinary-reservation. |
| RW2-03 | **NOT_MET** | Locked identity compare and independent CLI 0/2/3/4/5 exist. Named identity matrix is thin; expiry can overwrite consumed; CLI 5 omits expired/already-consumed replay. |
| RW2-04 | **NOT_MET** | Torn-composite and ordinary-replay names are ceremonial. Executor receipt omits HEAD, stderr hashes, and independent CLI transcripts. Listed unofficial aliases are gone; `reserve_provider_route_child_with_receipt` remains. |
| RW-CUSTODY | **MET** | Custody SHA `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` unchanged. `f8725af…` historical; `798c506…` current. |

## Preserved prior-MET result

Independently confirmed intact: one `_IncidentEventJournal` + sequence-sidecar flock; NBF writes enter `_locked` / `_append_nbf_locked`; C03–C06, C08, C12, C15–C18, C25, C26 shape, C35; CP04 journal count, CP05 increment rule, CP10; real two-process reservation contention; owned source scope; RW-CUSTODY. Preservation is not Batch 1 acceptance.

## North Star

1. **One door per invariant — NOT MET for the Batch 1 primitive.** One journal and one `_locked` door are real progress. Terminal accepted-launch is self-derived, producers remain a generic caller-snapshot door, and provider success/disposition select the latest stream. Physical admission/dispatch/death doors are correctly untouched.
2. **Deaths speak — foundation only.** Typed worker / observed-death / non-worker records and a non-signalling CLI exist. Signal-site wiring is correctly deferred. Incomplete append-path identity and confirmation evidence keep the primitive from fail-closed.
3. **Models are admitted, not assumed — correctly deferred.** No admission/catalog/live-provider caller changed.
4. **Fixes ship on main through the fixer contract — not evidenced.** No commit/push/merge, as required for this uncommitted gate.

### Anti-patterns

- **Single-scan verdicts as sustained truth — NOT MET.** Locked five-field compare exists; the required identity matrix and expiry-after-consumed guard do not.
- **Anonymous integer exit codes — PARTIALLY MET.** Typed `worker_disposition` and CLI 0/2/3/4/5 are reachable. Named expired/already-consumed status 5 remains thin. Real signal wiring is later.
- **Judgment-based “healthy” claims — NOT MET.** Terminal acceptance does not require a persisted accepted-launch marker. Reconciliation still treats schema-shaped adapter records as proof.
- **Identical-fingerprint redispatch without a changed precondition — NOT MET as a complete durable block.** Two-process reservation contends (C18/C25). Forgeable producers and coherent forged key transitions prevent trusting the rest of the block.

## KISS / YAGNI / scope creep

- **File scope:** MET. No admission caller, scheduler, T7/T8 policy, physical door, launch adapter, signal site, fallback policy, second journal, or rotator was added.
- **KISS:** NOT MET at quality. `_locked` is the right small door. `ChangedPrecondition.produce` still hashes caller snapshots. `reserve_provider_route_child_with_receipt` is an extra convenience surface.
- **YAGNI:** MET in batch boundary; no UnitOfWork / two-phase / extra projection service.
- **Ceremonial validation:** NOT MET. 59 new tests of 101 collected; 42 are unchanged `test_incident_ledger.py`. Same-ID terminal race, truncated-JSON torn-composite, ordinary-reservation “fresh replay”, and incoherent forged-hash tests remain.
- **Later-batch behavior in the candidate:** MET (absent).

## Independent confirmation of Luna blockers

Oracle read the cited symbols; they exist and behave as Luna described.

1. `append_terminal_outcome` binds reservation fields under `_locked` but never requires a persisted accepted controlled-adapter marker; replay sets `accepted_launch` from the terminal (`ledger.py:573-575,677-678`).
2. `worker_disposition` rejects provider/failure payloads and still accepts `success_payload` (`phase_result.py:169-173`).
3. `ChangedPrecondition.produce` hashes caller `before`/`after`/`evidence` (`schema.py:538-539`); coherent `from_dict` provider-key forgery appends.
4. Success/disposition without a provider key mutate `latest_stream_key` (`ledger.py:557-569`).
5. `test_two_process_terminal_linkage_is_atomic` shares one outcome ID.
6. `test_fresh_replay_receipt_is_byte_identical` is ordinary reservation; torn-composite writes a prefix, not an `_emit_locked` composite crash.
7. Listed unofficial aliases are gone; `reserve_provider_route_child_with_receipt` remains (`ledger.py:781-783`).

## Issues

Each issue is a required correction. Do not implement in this Oracle turn.

1. **blocker — terminal accepted-launch is self-authorized (C10).**  
   Symbols: `append_terminal_outcome`, `_project_records` (`ledger.py:659-718,544-575`).  
   Evidence: Luna probe `terminal_without_persisted_accepted_marker.accepted=true`; replay sets `accepted_launch` from the terminal.  
   Smallest correction: require one persisted receipt-bound accepted `controlled_adapter_state` before terminal append; add a negative test with a fully populated outcome.

2. **blocker — remaining payload/identity matrix holes (C02/C13/C14).**  
   Symbols: `DispatchOutcome.__post_init__`, disposition constructors, `validate_nbf_event`.  
   Evidence: `worker_disposition` accepts `success_payload`; append-path OOM/unknown-signal/identity coverage is selected, not complete.  
   Smallest correction: reject every incompatible payload at constructor, `from_dict`, `validate_nbf_event`, and append, with named tests for each family.

3. **blocker — changed-precondition producers remain caller-forgeable (C19–C21).**  
   Symbols: `ChangedPrecondition.produce`, `_produce_reason_specific`, `append_changed_precondition` (`schema.py:516-539`; `ledger.py:730-744`).  
   Evidence: caller snapshots hashed; forged hex test does not recompute `event_id`; probe `forged_provider_transition=accepted`.  
   Smallest correction: reason-specific producers that read authoritative sources; reject coherent forged events at append/consume.

4. **major — applicable provider stream is not selected (C11/C32/C33).**  
   Symbol: `_project_records` (`ledger.py:494-569`).  
   Evidence: probe success for A after B was latest left A at 2 and reset B to 0.  
   Smallest correction: carry applicable provider-failure-key identity on success/ordinary/disposition and mutate only that stream; add non-latest-target tests. Do not add T8 policy.

5. **major — recovery/child authorization is not evidence-bound (C23/C34).**  
   Symbol: `reserve_provider_route_child` (`ledger.py:746-775`).  
   Evidence: repeated-authorizer reject exists; passed canonical probe plus producer-derived recovery consume does not.  
   Smallest correction: require a persisted successful probe and fixed `provider_recovery_verified`, consume it in the one composite append, preserve the keyed streak.

6. **major — composite replay/crash tests are ceremonial (C27/C28/C09).**  
   Evidence: ordinary-reservation same-name replay; truncated-JSON torn-composite; same-ID terminal race.  
   Smallest correction: put composite replay under `test_fresh_replay_receipt_is_byte_identical`; inject `_emit_locked` composite failure; race distinct terminal IDs/kinds.

7. **major — confirmation/CLI named evidence still thin (C39/C41).**  
   Symbols: `consume_confirmation`, `expire_confirmation`, `_record_cli`.  
   Evidence: identity test mutates only process-start; expiry can overwrite consumed; CLI 5 omits expired and distinct already-consumed.  
   Smallest correction: strengthen the named identity/omission/expiry matrix; reject expiry after consumption; add CLI expired and already-consumed subprocess cases.

8. **major — executor evidence protocol incomplete (RW2-04).**  
   Artifact: `.oracle/receipts/execution-nbf01-rework2-luna.md`.  
   Evidence: no HEAD; truncated `git diff --check` SHA; no stderr hashes; CLI via pytest names. Independent Luna transcripts do not rewrite the executor artifact.  
   Smallest correction: a new immutable executor receipt bound to the exact post-fix tree, with HEAD, complete changed-file inventory, and per-command argv/cwd/exit/stdout/stderr SHA-256.

9. **minor — unofficial convenience surface remains.**  
   Symbol: `IncidentLedger.reserve_provider_route_child_with_receipt` (`ledger.py:781-783`).  
   Smallest correction: delete unless a frozen downstream symbol is documented to require it.

## Recommendation

Attempt 2 landed real progress: one locked journal door, a true two-process reservation race, typed OOM/unknown-death constructors, keyed stream scaffolding, locked confirmation identity, independent CLI 0/2/3/4/5, deleted listed aliases, and no scope expansion. Frozen Batch 1 still requires fail-closed authoritative semantics and named behavioral proof. Those are not present. Batch 2 remains prohibited.

Smallest next action: write `.oracle/rework/batch-1-attempt-3.md` covering issues 1–9 only; dispatch GPT-5.6 Luna; require one complete HEAD-bound execution receipt; then one fresh independent Luna review and a separate Grok Oracle gate. Do not implement, commit, push, merge, edit custody, rewrite historical receipts, or start Batch 2 in this turn.

```text
ACCEPTED_ISSUES
```
