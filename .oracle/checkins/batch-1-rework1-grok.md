# Grok 4.6 Oracle verdict — NBF-01 / Batch 1 rework 1

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
- Rework tasklist SHA-256: `5149fdcf7fd91a255ec6cfe34f447a9b1eb46bf3b56db92a2e03939fbc9d1d2c`
- Executor receipt: `.oracle/receipts/execution-nbf01-rework1-luna.md` (`1acba71b835c7bb2d854773d200c988f1fd344fa4ecdfab8eb64306ba7c69143`)
- Executor findings: `.oracle/findings/execution-nbf01-rework1-luna.md` (`e7607cf15818e2c05b1fc997d92a06f133fe98e12d543e6d8555ddea96192f91`)
- Custody receipt: `.oracle/receipts/rework-nbf01-custody-luna.md` (`48f540c4bec63ab17949b7a004395057be887f5dc9623cd87832be20ee375cb9`)
- Current custody.md SHA-256: `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`
- Luna review: `.oracle/checkins/batch-1-rework1-luna.md` (`cdc6cd9b0ecfc3097c0c2940bb9ce85b810a84ab81ceb777ead97dfdc86ec89b`)
- Luna review receipt: `.oracle/receipts/oracle-nbf01-rework1-luna.md` (`79a1ff3c42f97888d4faa3ab876618ae9506f7cd3f0755f015050810419e57ec`)
- This check-in: `.oracle/checkins/batch-1-rework1-grok.md`
- This decision receipt: `.oracle/receipts/oracle-nbf01-rework1-grok.md`

Do not commit, push, or begin Batch 2 on this candidate.

## Gate and evidence identity

Hard start-gate artifacts exist and are bound to the candidate actually reviewed:

- Execution receipt `.oracle/receipts/execution-nbf01-rework1-luna.md` is present and was not rewritten after this decision.
- Custody receipt proves current source `798c506...`, historical `f8725af...`, and post-rework ownership of `.oracle/custody.md`.
- Exactly one fresh independent GPT-5.6 Luna full re-review exists at the required check-in and receipt paths. No second review, fan-out, or self-review was commissioned.
- Owned production diff independently reproduces `e060f650e112ecc8c73f4f2491e8504f3a1f1c9943b80f4e5aa97590b2925801`.
- Luna independently reproduced focused `78 passed in 1.53s` (stdout SHA-256 `9cf73370d5321101a5f60d46e4572164f52630f3338b5d41a1f8cda4fcd4a006`) and legacy `78 passed in 2.06s` (stdout SHA-256 `84f2299be394af8fc77dcda51eaca94e685326f456ebae809e5bbfd92fc18514`). Oracle re-hashed those transcript stdout sections; they match.
- CLI 0/2/3/4/5 subprocess transcripts exist under `/tmp/oracle-nbf01-rework1-luna/`. Status 0 emitted one JSON acknowledgement and did not signal.
- `py_compile` and `git diff --check` exit 0 with empty-stdout SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- Owned source scope is MET: five modified production files, new `incident/disposition.py`, eight named new test modules. `test_incident_ledger.py` is unchanged versus `origin/main`. No later-task production file changed.

Executor evidence of the prior handoff remains historical and was not rewritten: start-gate focused **52**, later mutated to **61**, unreproducible digest `4aee815d...`, prior independent Luna snapshot `50c86490...`. Current focused **78** is an observation, not a target. The rework execution receipt is digest-consistent for the production diff but still abbreviates argv and omits per-command stdout hashes; Luna’s `/tmp` transcripts are the bound current evidence.

Luna recommended `RECOMMEND_ACCEPTED_ISSUES`. Oracle independently re-read the cited symbols. One calibration: Luna again over-weights `PhaseResult.from_dict` as the C01 door, and overstated the unresolved-launch payload hole (`phase_result.py:159-161` now rejects those fields for both `no_launch` and `unresolved_launch`). That does not salvage C02, CAS binding, producers, keyed replay, confirmation, CLI named tests, or missing required behavioral names.

## Hard gates

| Gate | Status |
| --- | --- |
| Rework execution receipt exists, immutable, with custody receipt | **MET** |
| Exactly one fresh independent Luna full review at required paths | **MET** |
| Candidate/diff and test-transcript digests recorded, reproducible, bound | **MET** |
| North Star disposition, KISS/YAGNI stated by Luna and Grok | **MET** as statements |
| All frozen NBF-01 must criteria met with behavioral evidence | **NOT_MET** |
| 52-vs-61 and `4aee815d...` treated as historical, not rewritten | **MET** |

`PASS_BATCH_1` is unavailable because the must-criterion gate fails.

## Criterion dispositions

Statuses: `MET` | `NOT_MET` | `UNEVIDENCED`. Oracle confirmation is against the post-rework candidate plus Luna’s reproduced commands. Luna numbering is preserved.

### NBF-01 acceptance criteria (tasklist)

| ID | Criterion | Status | Evidence |
| --- | --- | --- | --- |
| C01 | Strict round-trip of scheduling / six outcome kinds; unknown-field rejection | **NOT_MET** (partial) | `DispatchOutcome.from_dict` / `SchedulingCondition.from_dict` reject unknown/missing fields (`phase_result.py:91-99,195-203`). Scheduling tests remain one round-trip plus one bad reason. Remaining illegal-payload holes are C02. Luna’s `PhaseResult.from_dict` overweight is not the C01 door. |
| C02 | Invalid kind/state/payload combinations reject | **NOT_MET** | Kind/state map and several payload rejects exist (`phase_result.py:151-183`). Unresolved now shares the no-launch payload reject at `:159-161`. Remaining holes: ordinary failure still accepts `success_payload`; provider exhaustion still accepts `terminal_failure`. Named matrix test is not a full six-kind matrix; no append-path variants. |
| C03 | `no_launch` cannot serialize with `launch_state=accepted` | **MET** | Direct reject at `phase_result.py:151-155`; `test_no_launch_rejects_accepted_launch_state` is a real named regression. |
| C04 | `worker_disposition` requires accepted launch, disposition_id, receipt, fingerprint, phase/spec, logical/worker identity, start/finish | **MET** | `phase_result.py:156-167`; valid-shape round-trip remains. |
| C05 | Worker disposition cannot carry provider-exhaustion or no-launch state | **MET** | `phase_result.py:159-169`. Does not cure C02. |
| C06 | Maps only to `worker_terminal_outcome(outcome_kind=worker_disposition)` | **MET** | `phase_result_classify.py:212-217`; `ledger.py:602-604` writes `outcome.kind`. No coercion branch. |
| C07 | Mapping validates exactly one already-committed matching disposition; never re-appends it | **NOT_MET** as complete CAS | Now under `_locked` (`ledger.py:563-593`). Sequential matching exists. Required `test_recovered_disposition_links_existing_record_without_duplicate` and two-process terminal linkage are absent. |
| C08 | Never coerced into ordinary failure | **MET** | Distinct kind; ordinary-failure-with-`disposition_id` rejects (`phase_result.py:170-171`); named coercion test exists. |
| C09 | Duplicate linkage idempotent; conflicting linkage/kinds reject | **NOT_MET** | Locked sequential idempotency/conflict at `ledger.py:594-601`. Required `test_two_process_terminal_linkage_is_atomic` is absent. |
| C10 | Reservation closure and terminal-fingerprint projection occur exactly once | **NOT_MET** | Context compare exists but skips `logical_dispatch_id` for provider exhaustion and treats empty reservation fields as unconstrained (`ledger.py:570-586`). Reducer sets `closed=True` before provider-state projection (`:495-500`). Required context-mismatch test absent. |
| C11 | Worker disposition breaks provider-exhaustion consecutiveness without entering degradation | **NOT_MET** (keyed) | `_project_records` keeps `provider_streams` (`ledger.py:476-531`) but success/disposition reset every same-base stream (`:505-514`). Named test only asserts `len(provider_streaks)==2`. Global `observation_streak` is still the latest stream. |
| C12 | `no_launch` produces no worker terminal/fingerprint/provider/streak/phase-failure/breaker input | **MET** as primitive | Terminal writer rejects `no_launch` (`ledger.py:561-562`). Breaker/scheduler remain later-batch. |
| C13 | Worker / observed-death / non-worker schemas reject incomplete or fabricated identities | **NOT_MET** | Field sets and selected constructor tests exist. Required append-path / `validate_nbf_event` variants absent. Worker PID/fingerprint typing remains incomplete. |
| C14 | OOM requires positive cgroup evidence; unknown death remains unknown | **NOT_MET** as complete criterion | `_positive_cgroup_delta` now requires `positive is True` and finite `delta>0` (`schema.py:127-132`); unknown death forces `external_unknown` / `signal is None` (`:333-338`). Constructor tests exist. Required append-path variants absent; cannot accept from source inspection alone. |
| C15 | TERM and KILL ladder IDs are distinct | **MET** | `schema.py:296-298`; named test remains. |
| C16 | Semantic fingerprint excludes volatile liveness and logical/family IDs | **MET** | `schema.py:180-186`; provider/fingerprint test covers logical-ID and liveness-digest invariance. |
| C17 | Route-liveness digest absent from fingerprint and provider-failure key | **MET** | Provider-failure key is phase/spec/class/epoch (`schema.py:220-239`). |
| C18 | Different logical IDs with same projection key + fingerprint contend for one reservation | **MET** | `reservation_key` ignores logical ID (`ledger.py:40-43`); `reserve` compares under `_locked` (`:536-553`); `test_two_process_reservation_contention_one_winner` is a real two-OS-process race. |
| C19 | Only allowlisted reason-specific producers may mint changes | **NOT_MET** | Reasons and fixed producer-kind pairs exist (`schema.py:410-438`). Generic `produce` / `produce_changed_precondition` / `_producer(..., **kwargs)` remain (`:452-565`). |
| C20 | Producer, evidence, subject, version, before/after, provider-key binding validated | **NOT_MET** | `produce` hashes caller `before`/`after`/`evidence` (`schema.py:474-475`). It does not read authoritative sources. |
| C21 | Forged unequal content IDs or provider-failure-key transitions reject | **NOT_MET** | `test_forged_valid_hex_content_ids_reject` mutates `after_content_id` to `"a"*64` without recomputing `event_id` — inconsistent-identity coverage, not a coherent forged event. Caller key-transition reject exists for non-recovery reasons. |
| C22 | Valid changed-precondition consumed at most once | **NOT_MET** | Consume is under `_locked` (`ledger.py:741-751`). Required `test_consumed_change_cannot_authorize_second_reservation` is absent. |
| C23 | `provider_recovery_verified` may authorize one linked same-route child without resetting/rekeying the streak | **NOT_MET** | Route-child checks a persisted authorizer (`ledger.py:630-654`) but does not consume a canonical evidence-bound recovery event as a distinct single-use record. Required probe/recovery/one-child test absent. |
| C24 | Other allowlisted change resets/rekeys only when canonical before/after keys differ | **NOT_MET** | Projection stores changes (`ledger.py:515-519`) and does not reduce by `provider_failure_key_before/after`. Required test absent. |
| C25 | Ordinary two-process reservation contention yields one winner | **MET** | Same evidence as C18. |
| C26 | `provider_route_child_reserved` is one record and contains no child receipt-ID input | **MET** for shape | One append at `ledger.py:652-654`; no child receipt-ID argument. Authorization remains C23. |
| C27 | Receipt identity derives after append and reproduces byte-for-byte after fresh replay | **UNEVIDENCED** as complete criterion | `derive_receipt` is post-append (`ledger.py:656-658`). `test_fresh_replay_receipt_is_byte_identical` covers an ordinary reservation only, not a composite route-child. |
| C28 | Torn or failed writes cannot expose partial transitions, receipts, or projections | **UNEVIDENCED** | Torn-line skip exists. Required `test_torn_composite_write_exposes_neither_transition_nor_receipt` is absent. `_emit_locked` writes NDJSON directly (`ledger.py:261-271`). |
| C29 | Every accepted terminal outcome projects fingerprint state before reservation closure | **NOT_MET** | Same as C10: closure precedes provider/fingerprint projection (`ledger.py:492-500`). |
| C30 | Matching accepted `provider_exhausted` increments keyed streak | **NOT_MET** as keyed behavior | Increment exists (`ledger.py:502-504`). Existing test still proves a latest-stream streak of 2, not isolated keys. |
| C31 | Nonmatching accepted `provider_exhausted` rekeys at one | **NOT_MET** | Different-key streams can be created; required named rekey-at-one test absent. |
| C32 | Accepted worker success resets applicable streak and active key | **NOT_MET** | Success resets every same-base stream (`ledger.py:505-509`), not only the applicable key. Required test absent. |
| C33 | Intervening ordinary failure or worker disposition breaks consecutiveness without becoming degradation | **NOT_MET** as keyed behavior | Same-base broadcast reset (`ledger.py:510-514`). Required disposition named test absent. Distinct kinds retained; no degradation policy (correctly out of scope). |
| C34 | Probe results and `provider_recovery_verified` create/consume preserve matching streak | **NOT_MET** | Probe/recovery have no streak branch (leave values unchanged) but authorization/consumption is incomplete (C23) and the required live-streak test is absent. |
| C35 | Scheduling, no-launch, unresolved, time, liveness refresh do not mutate provider streak | **MET** as primitive | Those events have no provider-terminal reducer branch. |
| C36 | Reconciliation permits only positive `released_no_launch`, recovered terminal, or durable ambiguous hold | **NOT_MET** | Schema membership exists (`schema.py:505-517`). `reconcile_reservation` still accepts arbitrary nonempty `controlled_adapter` marker IDs (`ledger.py:678-680`). No persisted adapter-bound proof. |
| C37 | Recovered worker disposition links one existing canonical disposition and never duplicates disposition/signal | **NOT_MET** | No recovered-disposition path. Required named test absent. |
| C38 | Blind release, conflicting reconciliation, and accepted-launch release as no-launch reject | **NOT_MET** | Sequential conflict/identical replay exists under lock (`ledger.py:671-675`). Blind release with `("marker",)` still accepted by `test_positive_no_launch_reconciliation_only`. Required accepted-launch-release and conflict named tests absent. |
| C39 | Durable two-scan state survives restart; TTL, scan separation, PID/process-start/progress/incarnation equality, single consumption, replacement/expiry | **NOT_MET** | Confirmation IDs bind identity fields (`disposition.py:32-33`). `consume_confirmation` treats identity arguments as optional (`:88-90`); omitted second-scan identity is timestamp/evidence consumption. `consume_confirmation` also reads `ledger.projection()` before the locked observe. Replacement is PID-limited (`ledger.py:691-701`). Required reopen, two-process consumer, and expiry-replay tests absent. |
| C40 | Ledger lock, append, schema, projection-version, and cache failures fail closed | **NOT_MET** | NBF methods now use `_locked` / `_append_nbf_locked` (`ledger.py:405-465,536-759`). Required `test_lock_schema_and_projection_version_mismatch_fail_closed` is absent. Cache-mismatch CAS is still missing. Invalid records are filtered from projection rather than always failing closed. |
| C41 | Disposition CLI schema validation, acknowledgements, and exit codes match settled-plan §4.21 / Contract G | **NOT_MET** | Independent subprocesses reached 0/2/3/4/5. Status 0 used a non-worker record and did not prove consumed confirmation. Status 5 covered missing confirmation only, not already-consumed. All six required CLI/confirmation named tests are absent from the eight modules. |

### Batch 1 checkpoint

| ID | Checkpoint | Status |
| --- | --- | --- |
| CP01 | Every NBF-01 focused test passes | **MET** as pytest gate only (Luna: `78 passed in 1.53s`). Does not cure thin/missing coverage. |
| CP02 | Schema fields and legal transitions match owned §§4.4–4.13, §4.16, §§4.19–4.21 | **NOT_MET** — C01/C02 remainder, C13, C14 append-path, C36–C41. |
| CP03 | `DispatchOutcome.kind=worker_disposition` is lossless and maps exactly once | **NOT_MET** — happy-path kind is lossless; concurrent exactly-once mapping is not (C07, C09, C10). |
| CP04 | One incident-ledger authority owns reservation, terminal, linkage, keyed replay, reconciliation, change, confirmation, dispositions | **MET** for journal count / lock door; **NOT_MET** as complete contract. Methods live on `IncidentLedger` and reuse `_IncidentEventJournal` + sequence-sidecar flock. Binding/reducer holes remain C10/C11/C36–C40. |
| CP05 | Accepted exhausted worker outcomes are the only inputs that create/increment provider observations | **MET** for current replay; keyed isolation is still not (C11). |
| CP06 | `provider_recovery_verified` remains single-use retry authorization while preserving streak | **NOT_MET** — C23. |
| CP07 | Success resets; different-key rekeys at one; ordinary/disposition break consecutiveness; only authoritative key change otherwise resets/rekeys | **NOT_MET** — C11, C24, C30–C33. |
| CP08 | Composite transition and child reservation remain one append with post-commit replay-stable receipt | **NOT_MET** as complete proof — one-record shape exists; composite replay/crash/authorization incomplete. |
| CP09 | No-launch, unresolved, ordinary failure, provider exhaustion, and worker disposition are mechanically distinct | **MET** for type/state distinctions; illegal payload combinations remain (C02). |
| CP10 | No second journal, store, prepare/commit protocol, scheduler, rotator, or policy owner | **MET**. |
| CP11 | Crash, contention, replay, torn-write, linkage, keyed-streak, TTL, incarnation, and single-consumption tests pass | **NOT_MET**. Reservation two-process contention is the one real race; the rest of the required matrix is missing or ceremonial. |

### Rework tasks

| ID | Status | Evidence |
| --- | --- | --- |
| RW-01 | **NOT_MET** | Lock moved inside; six required names still missing; terminal/recon binding still forgeable/bypassable. |
| RW-02 | **NOT_MET** | Seven names exist; matrix and append-path coverage incomplete. |
| RW-03 | **NOT_MET** | Generic `**kwargs` producer remains; forged-hash test is not coherent; second-consumption name missing. |
| RW-04 | **NOT_MET** | Partial `provider_streams`; five required names missing; existing keyed test is a dict-length assertion. |
| RW-05 | **NOT_MET** | CLI statuses reachable by subprocess; six required pytest names missing; confirmation identity still optional. |
| RW-06 | **NOT_MET** | Torn-composite name missing; executor finding still abbreviates argv; historical 52-vs-61 preserved. |
| RW-CUSTODY | **MET** | `f8725af...` labeled historical; current source remains `798c506...`. |

## North Star

### Enduring principles

1. **One door per invariant — NOT MET for the Batch 1 primitive.** NBF writes now share one `_IncidentEventJournal` sequence-sidecar flock via `_locked` / `_append_nbf_locked`. That is real progress versus the prior unlocked compare-then-append. It is not yet one door: terminal compares skip fields, reconciliation accepts caller marker IDs, `consume_confirmation` still pre-reads `projection()` in the helper, and generic producer/CLI surfaces remain unofficial doors. Physical admission/dispatch/death doors are correctly untouched.
2. **Deaths speak — foundation only, not truthful end-state.** Typed worker / observed-death / non-worker records exist, with tighter OOM and unknown-death constructors. Signal-site wiring is correctly deferred. Missing append-path evidence and incomplete CLI/confirmation proof mean the primitive is not yet fail-closed.
3. **Models are admitted, not assumed — correctly deferred.** No admission/catalog/live-provider caller changed. Scope discipline, not Batch 1 acceptance evidence for the end-state principle.
4. **Fixes ship on main through the fixer contract — not evidenced.** No commit/push/merge, as required for this uncommitted gate. Delivery proof belongs to later NBF-07 after a passing Batch 1.

### Anti-patterns

- **Single-scan verdicts as sustained truth — NOT MET.** Confirmation IDs bind PID/process-start/progress/incarnation/cause, but consumption still accepts omitted identity fields (`disposition.py:88-90`).
- **Anonymous integer exit codes where a disposition belongs — PARTIALLY MET.** Typed `worker_disposition` and frozen enums exist. CLI 0/2/3/4/5 are reachable by subprocess, but named regressions and consumed-confirmation status 0/5 are missing. Real signal wiring is later.
- **Judgment-based “healthy” claims without positive proof — NOT MET.** Reconciliation still accepts caller-asserted adapter marker IDs. Confirmation consumption is not mandatory identity equality.
- **Redispatch of an identical failure fingerprint without a changed precondition — NOT MET as a complete durable block.** Two-process same-fingerprint reservation now contends (C18/C25). Forgeable producers and unlocked-optional confirmation still prevent trusting the rest of the block.

## KISS / YAGNI / scope creep

- **File scope:** MET. No admission caller, scheduler, T7/T8 policy, physical door, launch adapter, signal site, fallback policy, second journal, or rotator was added.
- **KISS:** NOT MET at quality. `_locked` is the right small door. Remaining aliases (`append_worker_disposition`, `write_terminal_outcome`, `reserve_admission`, `reconcile`, `replay_projection` at `ledger.py:768-772`) and generic `**kwargs` producers (`schema.py:547-565`) still do not enforce the contracts they name.
- **YAGNI:** MET in batch boundary; no UnitOfWork / two-phase / extra projection service.
- **Ceremonial validation:** NOT MET. 36 new tests of 78 collected; 42 are unchanged `test_incident_ledger.py`. Many required names are missing; several present names are one-line stubs (torn-line renamed as crash-before-append; reconciliation still uses `("marker",)`; keyed test is `len==2`).
- **Duplicate doors:** One journal; incomplete compare bindings and helper-side `projection()` reads remain unofficial doors.
- **Later-batch behavior in the candidate:** MET (absent).

## Independent confirmation of Luna blockers

Oracle read the cited symbols; they exist and behave as Luna described, with the C01/C02 calibrations above.

1. `_locked` now wraps reserve/terminal/child/recon/change/probe/confirmation appends. That closes the original unlocked-compare defect for reservation contention (C18/C25). Terminal/recon still bypass binding (`ledger.py:574-586,678-680`).
2. OOM constructor is typed; append-path tests are still missing. Unknown-death constructor rejects fabricated killer/signal.
3. `ChangedPrecondition.produce` still hashes caller objects; reason wrappers still accept `**kwargs`.
4. `reconcile_reservation` does not inspect persisted adapter evidence. `append_terminal_outcome` skips logical ID for provider exhaustion and empty expected fields.
5. Provider reducer is a dictionary of streams, but success/disposition broadcast-reset the same base and tests do not prove isolation.
6. `consume_confirmation` optional identity fields plus helper-side `projection()` keep two-scan proof timestamp/evidence shaped.
7. CLI 0/2/3/4/5 subprocesses work; required pytest names and already-consumed status 5 are absent.
8. Required RW-01/03/04/05/06 names listed by Luna are independently missing from the eight modules.

## Issues

Each issue is a required correction. Do not implement in this Oracle turn.

1. **blocker — incomplete reservation-bound terminal/reconciliation CAS.**  
   Symbols: `append_terminal_outcome`, `reconcile_reservation`, `reserve_provider_route_child` (`ledger.py:555-681`).  
   Evidence: provider-exhaustion logical-ID skip; empty-field bypass; arbitrary `controlled_adapter` marker IDs; missing six RW-01 names including two-process terminal linkage and recovered disposition.  
   Smallest correction: bind every field to persisted reservation/adapter/disposition evidence under the existing lock; add the missing OS-process and recovered-disposition regressions.

2. **blocker — incomplete strict schema / illegal-state matrix.**  
   Symbols: `DispatchOutcome.__post_init__`, `WorkerDisposition`, `ObservedProcessDeath`, `NonWorkerSignalDisposition`, `validate_nbf_event`.  
   Evidence: ordinary-failure+`success_payload` and provider-exhausted+`terminal_failure` still accepted; named matrix is not complete; required append-path variants absent.  
   Smallest correction: close the remaining payload combinations at decode and append; add append-path OOM/unknown-death/identity tests.

3. **blocker — changed-precondition producers remain caller-forgeable.**  
   Symbols: `ChangedPrecondition.produce`, `_producer`, `append_changed_precondition` (`schema.py:452-565`; `ledger.py:616-628`).  
   Evidence: hashes of caller objects; generic `**kwargs`; forged-hex test does not recompute `event_id`; missing second-reservation consumption test.  
   Smallest correction: reason-specific producers that read authoritative sources; reject coherent forged events; consume once under the reservation lock with a named test.

4. **major — keyed provider replay is still not the frozen reducer.**  
   Symbol: `IncidentLedger._project_records` (`ledger.py:467-531`).  
   Evidence: same-base broadcast reset; ignored changed-precondition key before/after; five required RW-04 names missing; `len(provider_streaks)==2` is not isolation.  
   Smallest correction: reduce only the applicable key; implement recovery-preserving and authoritative key-change transitions; add the named tests. Do not add T8 policy.

5. **major — two-scan confirmation and CLI named evidence remain incomplete.**  
   Symbols: `consume_confirmation` (`disposition.py:70-93`), `_record_cli` (`:96-141`).  
   Evidence: optional identity compare; helper-side unlocked `projection()`; missing reopen/two-process/CLI pytest names; status 0 not a consumed worker confirmation; status 5 not already-consumed.  
   Smallest correction: mandatory identity equality under the ledger lock; durable replacement/expiry/restart; exact named CLI 0/2/4/5 tests including already-consumed.

6. **major — crash/replay and evidence protocol still thin.**  
   Evidence: required torn-composite test absent; fresh-replay is ordinary-reservation only; executor finding still abbreviates argv. Historical 52-vs-61 and `4aee815d...` correctly preserved.  
   Smallest correction: inject composite torn/failed writes; bind complete command transcripts with stdout SHA-256 to this candidate.

7. **minor — prohibited aliases remain.**  
   Symbols: `ledger.py:768-772`; generic disposition constructors `disposition.py:36-46`.  
   Smallest correction: delete aliases that do not enforce a frozen symbol.

## Recommendation

The rework improved the original unlocked-compare defect, added a real two-process reservation race, tightened some schema constructors, and produced bound current evidence without rewriting the mutated 52-vs-61 history. Frozen Batch 1 still requires durable fail-closed primitives and the named behavioral matrix. Those are not present. Batch 2 remains prohibited.

```text
ACCEPTED_ISSUES
```
