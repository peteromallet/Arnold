# Grok 4.6 Oracle verdict — NBF-01 / Batch 1

**Verdict:** `ACCEPTED_ISSUES`

- Oracle: Grok 4.6 (manager/validator only; no implementation)
- Date: 2026-08-29
- Source base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924` (verified)
- Candidate branch: `megado-nbf-guard-0826`
- HEAD (planning, not NBF-01 code): `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- Merge-base with `origin/main`: `798c50619204010ed3f4297fbb57988fe9381924`
- Frozen tasklist SHA-256: `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- Settled plan v8 SHA-256: `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`
- North Star SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Executor receipt: `.oracle/receipts/execution-nbf01-luna.md`
- Luna review: `.oracle/checkins/batch-1-luna.md` (SHA-256 `7d19a34bc086df1d383d8083ed07f6214151ec55d3b3317609c4506a7af1ede7`)
- Luna review receipt: `.oracle/receipts/oracle-nbf01-luna.md`
- This check-in: `.oracle/checkins/batch-1-grok.md`
- This decision receipt: `.oracle/receipts/oracle-nbf01-grok.md`

Do not commit, push, or begin Batch 2 on this candidate.

## Gate and evidence identity

Hard start gate passed: `.oracle/receipts/execution-nbf01-luna.md` existed and identified a Batch 1 Luna result before this verdict. One independent GPT-5.6 Luna review pass was commissioned from `.oracle/briefs/oracle-nbf01-luna-review.md`; no second pass or fan-out.

Independently verified frozen identities match the brief. The NBF-01 candidate is uncommitted owned working-tree plus untracked owned files on `megado-nbf-guard-0826`. Later batches and dirty `.oracle` planning artifacts are not acceptance evidence.

Executor evidence is internally inconsistent:

- Start-gate receipt (mtime 2026-08-29 23:58, 828 bytes) claimed focused **52 passed**.
- The same path later mutated (mtime 2026-08-30 00:01, 884 bytes) to focused **61 passed**.
- Luna independently reproduced focused `61 passed in 1.20s` and legacy `78 passed in 3.21s`.
- Executor tracked owned production digest `4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70` was not reproduced. Luna recomputed `50c864900a2f9d0fd5b6bc4240d97d365148e4cf2dd511749e9701fa059a09bf` for the five modified owned production files.

Green pytest is necessary and was reproduced by Luna. It is not sufficient: 19 new tests are thin sequential stubs; 42 of 61 focused tests are the unchanged legacy `test_incident_ledger.py`.

Owned source scope is MET: only the five permitted modified production files, new `incident/disposition.py`, and the eight named new test modules. `test_incident_ledger.py` is unchanged. No later-task production file changed.

## Criterion dispositions

Statuses: `MET` | `NOT_MET` | `UNEVIDENCED`. Oracle confirmation is against the candidate source plus Luna's reproduced commands. Luna's numbering is preserved.

### NBF-01 acceptance criteria (tasklist)

| ID | Criterion | Status | Evidence |
| --- | --- | --- | --- |
| C01 | Strict round-trip of scheduling / six outcome kinds; unknown-field rejection | **NOT_MET** (partial) | `SchedulingCondition.from_dict` / `DispatchOutcome.from_dict` reject unknown/missing fields (`phase_result.py:90-97,190-197`). Incomplete payload matrix remains (C02). `PhaseResult.from_dict` is not a full nested validator. New scheduling test is one round-trip plus one bad reason. |
| C02 | Invalid kind/state/payload combinations reject | **NOT_MET** | Kind/state map exists (`phase_result.py:149-153`). `unresolved_launch` still accepts success/provider/failure/disposition payloads; `success` accepts provider/disposition evidence. Frozen Contract A requires a complete incompatible-payload matrix. |
| C03 | `no_launch` cannot serialize with `launch_state=accepted` | **MET** | Direct reject at `phase_result.py:149-153`. No named focused test. |
| C04 | `worker_disposition` requires accepted launch, disposition_id, receipt, fingerprint, phase/spec, logical/worker identity, start/finish | **MET** | `phase_result.py:160-167`; worker-disposition round-trip test exercises the valid shape. |
| C05 | Worker disposition cannot carry provider-exhaustion or no-launch state | **MET** | `phase_result.py:157-167`. Does not cure C02. |
| C06 | Maps only to `worker_terminal_outcome(outcome_kind=worker_disposition)` | **MET** | `phase_result_classify.py:212-219`; `append_terminal_outcome` writes `outcome.kind` at `ledger.py:516-518`. No coercion branch. |
| C07 | Mapping validates exactly one already-committed matching disposition; never re-appends it | **NOT_MET** as CAS | Sequential check at `ledger.py:503-509`. Check is outside the append lock. Sequential idempotency test exists; concurrent writers can both pass. |
| C08 | Never coerced into ordinary failure | **MET** | Distinct kind preserved; ordinary-failure-with-`disposition_id` rejects (`phase_result.py:168-169`). |
| C09 | Duplicate linkage idempotent; conflicting linkage/kinds reject | **NOT_MET** | Pre-lock scan at `ledger.py:495-515`. Same `event_id` is idempotent inside `_append_nbf`; distinct concurrent terminal IDs are not. |
| C10 | Reservation closure and terminal-fingerprint projection occur exactly once | **NOT_MET** | Closure is a later replay branch (`ledger.py:435-439`). Terminal writer does not compare outcome plan/phase/fingerprint/receipt/logical identity to the reservation, and the compare is unlocked. |
| C11 | Worker disposition breaks provider-exhaustion consecutiveness without entering degradation | **NOT_MET** (keyed) | `projection` uses one process-wide `provider_key`/`streak` (`ledger.py:421-451`), not keyed by projection/failure key. Disposition sets global streak 0. No degradation policy (correctly out of scope), but keyed projection is in scope. |
| C12 | `no_launch` produces no worker terminal/fingerprint/provider/streak/phase-failure/breaker input | **MET** as primitive | Terminal writer rejects `no_launch` (`ledger.py:493-494`). No provider/terminal branch for it. Breaker/scheduler behavior is later-batch and absent. |
| C13 | Worker / observed-death / non-worker schemas reject incomplete or fabricated identities | **NOT_MET** | Field sets exist. `ObservedProcessDeath` does not validate schema_version, killer, or signal (`schema.py:309-316`). `NonWorkerSignalDisposition` does not validate schema_version or cause. Unknown death can carry fabricated killer/signal. |
| C14 | OOM requires positive cgroup evidence; unknown death remains unknown | **NOT_MET** | `not self.evidence` / `not self.positive_cgroup_delta` treats any truthy object as positive (`schema.py:275-276,315-316`). `{"positive": false}` passes. Observed unknown death is not forced to `external_unknown` / no-signal. |
| C15 | TERM and KILL ladder IDs are distinct | **MET** | `WorkerDisposition.deterministic_id` includes signal and ladder (`schema.py:286-288`); `test_term_and_kill_ladder_ids_are_distinct` passes. |
| C16 | Semantic fingerprint excludes volatile liveness and logical/family IDs | **MET** | `SemanticDispatchFingerprint.VOLATILE` (`schema.py:144-159`); provider/fingerprint test covers logical-ID and liveness-digest invariance. |
| C17 | Route-liveness digest absent from fingerprint and provider-failure key | **MET** | `ProviderFailureKey` is phase/spec/class/epoch only (`schema.py:174-230`). |
| C18 | Different logical IDs with same projection key + fingerprint contend for one reservation | **MET** sequentially; **NOT_MET** as two-process CAS | `reservation_key` ignores logical ID (`ledger.py:29-33`); sequential test passes. `reserve` reads projection before lock (`ledger.py:469-485`); concurrent different `event_id`s can both append. |
| C19 | Only allowlisted reason-specific producers may mint changes | **NOT_MET** | Reasons are allowlisted (`schema.py:386`). Generic `produce` / `_producer` still accept caller `producer_kind`, `producer_version`, subject, evidence, and `**kwargs` (`schema.py:411-414,484-502`). |
| C20 | Producer, evidence, subject, version, before/after, provider-key binding validated | **NOT_MET** | `ChangedPrecondition.produce` hashes caller `before`/`after`/`evidence` and does not read authoritative sources. `append_changed_precondition` only decodes and appends. |
| C21 | Forged unequal content IDs or provider-failure-key transitions reject | **NOT_MET** | `from_dict` accepts any 64-hex pair (`schema.py:393-398`). Focused test mutates an ID to `"x"` (malformed length), not a forged valid hash. |
| C22 | Valid changed-precondition consumed at most once | **NOT_MET** | `consume_changed_precondition` and `reserve` check consumption outside the lock (`ledger.py:469-485,573-578`). |
| C23 | `provider_recovery_verified` may authorize one linked same-route child without resetting/rekeying the streak | **NOT_MET** | Schema exists. `reserve_provider_route_child` does not require or consume the authorizing recovery event (`ledger.py:529-540`). |
| C24 | Other allowlisted change resets/rekeys only when canonical before/after keys differ | **NOT_MET** | `projection` ignores changed-precondition key-before/after (`ledger.py:452-456`). |
| C25 | Ordinary two-process reservation contention yields one winner | **NOT_MET** | Only sequential contention test. Unlocked compare + distinct event IDs (`ledger.py:483-485`). |
| C26 | `provider_route_child_reserved` is one record and contains no child receipt-ID input | **MET** for shape | One append at `ledger.py:538-540`; signature has no child receipt ID; unknown fields reject. Authorization semantics remain C23. |
| C27 | Receipt identity derives after append and reproduces byte-for-byte after fresh replay | **MET** derivation; **UNEVIDENCED** replay | `derive_receipt` is post-append (`ledger.py:542-548`); `receipt_id` excludes timestamps. No fresh-replay byte-identity test. |
| C28 | Torn or failed writes cannot expose partial transitions, receipts, or projections | **UNEVIDENCED** | Torn JSON lines are skipped (`test_torn_line_is_not_projected`). No injected failed append/fsync/composite-boundary tests. |
| C29 | Every accepted terminal outcome projects fingerprint state before reservation closure | **NOT_MET** | Same as C10: projection is replay-after-append, not an atomic compare/append of reservation context. |
| C30 | Matching accepted `provider_exhausted` increments keyed streak | **MET** for the implemented single stream | `ledger.py:440-445`; provider-route test observes streak 2 after reopen. Not keyed (C11). |
| C31 | Nonmatching accepted `provider_exhausted` rekeys at one | **MET** for the implemented single stream | `ledger.py:440-444`. No direct nonmatching-key focused test. |
| C32 | Accepted worker success resets applicable streak and active key | **MET** for the implemented single stream | `ledger.py:446-447`. Terminal test does not assert the reset. |
| C33 | Intervening ordinary failure or worker disposition breaks consecutiveness without becoming degradation | **MET** as primitive | `ledger.py:448-451`. Distinct outcome kinds retained. |
| C34 | Probe results and `provider_recovery_verified` create/consume preserve matching streak | **UNEVIDENCED** as full criterion | Probe/recovery have no streak branch, so they leave the global value unchanged. No test around a live streak. Recovery is not consumed (C23). |
| C35 | Scheduling, no-launch, unresolved, time, liveness refresh do not mutate provider streak | **MET** as primitive | Those events have no provider-terminal branch. No end-to-end scheduler in this batch. |
| C36 | Reconciliation permits only positive `released_no_launch`, recovered terminal, or durable ambiguous hold | **NOT_MET** | Schema membership exists (`schema.py:444-454`). `reconcile_reservation` only rejects release when `launch_state_identity != not_started` (`ledger.py:550-561`). Arbitrary nonempty evidence IDs suffice; no controlled-adapter proof. |
| C37 | Recovered worker disposition links one existing canonical disposition and never duplicates disposition/signal | **NOT_MET** | No recovered-disposition path. Writer just appends the supplied reconciliation. |
| C38 | Blind release, conflicting reconciliation, and accepted-launch release as no-launch reject | **NOT_MET** | Release accepted with arbitrary evidence after reserve; closed/accepted contradiction is not checked. Conflict check is unlocked. |
| C39 | Durable two-scan state survives restart; TTL, scan separation, PID/process-start/progress/incarnation equality, single consumption, replacement/expiry | **NOT_MET** | TTL and min separation exist (`disposition.py:70-87`) and two simple tests pass. Second scan does not carry or compare PID/process-start/progress/incarnation/cause. No replacement/expiry events, restart proof, or locked single-consumer compare. |
| C40 | Ledger lock, append, schema, projection-version, and cache failures fail closed | **NOT_MET** | `_append_nbf` locks its own append (`ledger.py:378-412`). Reservation/terminal/route-child/probe/confirmation/change compares happen first, unlocked. Cache-mismatch and projection-version CAS are absent on most transitions (`reserve` has an optional version check only). |
| C41 | Disposition CLI schema validation, acknowledgements, and exit codes match settled-plan §4.21 / Contract G | **NOT_MET** | Valid smoke: exit 0, one JSON ack, no signal (`disposition.py:90-123`). Status 2/3 exist. Status 5 is absent. Confirmation is not validated. `IncidentLedger.__init__` (`ledger.py:360-363`) does not reject an invalid location, so the status-4 branch is effectively dead and becomes append failure. |

### Batch 1 checkpoint

| ID | Checkpoint | Status |
| --- | --- | --- |
| CP01 | Every NBF-01 focused test passes | **MET** as pytest gate only (Luna: `61 passed in 1.20s`). Does not cure thin coverage. |
| CP02 | Schema fields and legal transitions match owned §§4.4–4.13, §4.16, §§4.19–4.21 | **NOT_MET** — C01, C02, C13, C14, C36–C41. |
| CP03 | `DispatchOutcome.kind=worker_disposition` is lossless and maps exactly once | **NOT_MET** — happy-path kind is lossless; atomic exactly-once mapping is not (C07, C09, C10). |
| CP04 | One incident-ledger authority owns reservation, terminal, linkage, keyed replay, reconciliation, change, confirmation, dispositions | **NOT_MET** — methods live on `IncidentLedger` and reuse `_IncidentEventJournal`, but they are not one lock/read/compare/append critical section. |
| CP05 | Accepted exhausted worker outcomes are the only inputs that create/increment provider observations | **MET** for current replay; projection is still not keyed (C11). |
| CP06 | `provider_recovery_verified` remains single-use retry authorization while preserving streak | **NOT_MET** — C23. |
| CP07 | Success resets; different-key rekeys at one; ordinary/disposition break consecutiveness; only authoritative key change otherwise resets/rekeys | **NOT_MET** — C11, C24. |
| CP08 | Composite transition and child reservation remain one append with post-commit replay-stable receipt | **MET** for one-record/post-append shape; replay/authorization evidence incomplete. |
| CP09 | No-launch, unresolved, ordinary failure, provider exhaustion, and worker disposition are mechanically distinct | **MET** for type/state distinctions; illegal payload combinations remain (C02). |
| CP10 | No second journal, store, prepare/commit protocol, scheduler, rotator, or policy owner | **MET**. |
| CP11 | Crash, contention, replay, torn-write, linkage, keyed-streak, TTL, incarnation, and single-consumption tests pass | **NOT_MET**. |
| Scope | No excluded later-task file or behavior changed | **MET** on the owned source/test diff. |

## North Star

### Enduring principles

1. **One door per invariant — NOT MET for the Batch 1 primitive.** NBF writes reuse one `_IncidentEventJournal`, and physical admission/dispatch/death doors are correctly untouched. Reservation, terminal, confirmation, probe, and producer methods each pre-compare outside that append lock, which is a second unofficial door and the race the frozen “single ledger transaction” contract forbids.
2. **Deaths speak — foundation only, not truthful.** Typed `WorkerDisposition` / observed-death / non-worker records exist, with killer/signal/elapsed and distinct ladder IDs. Signal-site wiring is correctly deferred. Permissive OOM truthiness and fabricated unknown-death killer/signal fields mean the primitive is not yet fail-closed.
3. **Models are admitted, not assumed — correctly deferred.** No admission/catalog/live-provider caller changed. This is scope discipline, not Batch 1 acceptance evidence for the end-state principle.
4. **Fixes ship on main through the fixer contract — not evidenced.** Executor performed no commit/push/merge, as required for this uncommitted gate. Delivery proof belongs to later NBF-07, after a passing Batch 1.

### Anti-patterns

- **Single-scan verdicts as sustained truth — NOT MET.** Confirmation IDs bind PID/process-start/progress/incarnation/cause and a TTL, but consumption checks only timestamps (`disposition.py:70-87`). A schema-shaped second scan is not two-scan proof.
- **Anonymous integer exit codes where a disposition belongs — PARTIALLY MET.** Typed `worker_disposition` and frozen enums exist in this slice. Real signal wiring is later. Unknown observations can still carry fabricated killer/signal. CLI statuses 4/5 are missing or dead.
- **Judgment-based “healthy” claims without positive proof — NOT MET.** Confirmation consumption does not equal-check progress or incarnation. Reconciliation accepts caller-asserted evidence IDs.
- **Redispatch of an identical failure fingerprint without a changed precondition — NOT_MET.** Sequential same-fingerprint contention works; unlocked `reserve` plus forgeable/unbound changed-preconditions cannot be trusted under concurrency.

## KISS / YAGNI / scope creep

- **File scope:** MET. No admission caller, scheduler, T7/T8 policy, physical door, launch adapter, signal site, fallback policy, second journal, or rotator was added.
- **KISS:** NOT MET at quality. ~1k production lines plus aliases (`append_worker_disposition`, `write_terminal_outcome`, `reserve_admission`, `reconcile`, `replay_projection`) and a generic `**kwargs` producer surface do not enforce the contracts they name.
- **YAGNI:** MET in batch boundary; caution that `validate_nbf_event` exposes policy-shaped event types without their required semantics.
- **Ceremonial validation:** NOT MET. 19 new tests of 61 collected; no two-process race, crash-matrix, forged-valid-hash, reservation-context mismatch, incarnation/replacement confirmation, or CLI 4/5 tests.
- **Duplicate doors:** One journal; many unlocked compare-then-append methods. That is the forbidden duplicate transaction door.
- **Later-batch behavior in the candidate:** MET (absent).

## Independent confirmation of Luna blockers

Oracle read the cited symbols; they exist and behave as Luna described.

1. `IncidentLedger.reserve` / `append_terminal_outcome` / `reserve_provider_route_child` / `reconcile_reservation` / `consume_changed_precondition` / `create_probe_lease` all call `projection()` then `_append_nbf`. `_append_nbf` idempotency is by `event_id`; `reserve` includes `logical_dispatch_id` in the event id, so two processes with the same fingerprint can both append.
2. `ObservedProcessDeath.__post_init__` does not constrain killer/signal. OOM uses Python truthiness.
3. `ChangedPrecondition.produce` hashes caller objects; reason-specific wrappers only pin `reason`.
4. `reconcile_reservation` does not inspect ledger adapter evidence. `append_terminal_outcome` does not bind reservation identity fields before append.
5. `projection` stores one `provider_key` and one `streak`.
6. `consume_confirmation` compares timestamps only.
7. `_record_cli` has no status 5; `IncidentLedger.__init__` does not fail an invalid path.

Luna over-weights `PhaseResult.from_dict` unknown-field handling relative to the frozen DispatchOutcome/SchedulingCondition door. That does not salvage C02 or the CAS/schema blockers.

## Issues

Each issue is a required correction. Do not implement in this Oracle turn.

1. **blocker — non-atomic CAS.**  
   Symbols: `IncidentLedger.reserve`, `append_terminal_outcome`, `reserve_provider_route_child`, `consume_changed_precondition`, `create_probe_lease`, `reconcile_reservation` (`ledger.py:469-585`).  
   Evidence: unlocked `projection()` then `_append_nbf`; sequential-only contention tests (`test_incident_ledger_transactions.py`).  
   Smallest correction: perform each read/compare/consume/conflict/append under the existing journal lock; add a real two-process race regression.

2. **blocker — incomplete strict schema and illegal-state matrix.**  
   Symbols: `DispatchOutcome.__post_init__`, `WorkerDisposition`, `ObservedProcessDeath`, `NonWorkerSignalDisposition`, `ReservationReconciled`.  
   Evidence: unresolved/success payload holes (`phase_result.py:141-177`); OOM truthiness and unconstrained observed-death killer/signal (`schema.py:275-276,309-316`).  
   Smallest correction: enforce the full Contract A payload matrix and close version/enum/identity/OOM-delta invariants at every decode and append.

3. **blocker — changed-precondition producers are not evidence-bound.**  
   Symbols: `ChangedPrecondition.produce`, `_producer`, `append_changed_precondition`, `consume_changed_precondition` (`schema.py:411-414,484-502`; `ledger.py:524-527,573-578`).  
   Evidence: callers choose producer identity and 64-hex IDs; focused test rejects `"x"`, not a forged valid hash (`test_changed_precondition_producers.py`).  
   Smallest correction: fixed reason-specific producers that derive identities from authoritative evidence; validate and consume inside the reservation CAS.

4. **blocker — terminal and reconciliation context is forgeable.**  
   Symbols: `append_terminal_outcome`, `reconcile_reservation` (`ledger.py:487-561`).  
   Evidence: no reservation-identity compare; release accepted from `ReservationReconciled(..., "controlled_adapter", ("marker",), "not_started")` (`test_reservation_reconciliation.py`).  
   Smallest correction: bind every transition to the reservation record and require positive persisted evidence for the three legal resolutions, under the lock.

5. **major — keyed provider replay is a global stream.**  
   Symbol: `IncidentLedger.projection` (`ledger.py:414-467`).  
   Evidence: one `provider_key`/`streak`; recovery and key-changing preconditions have no projection rules.  
   Smallest correction: project by frozen projection-key/failure-key; implement recovery-preserving and authoritative key-change transitions.

6. **major — two-scan confirmation is timestamp-only.**  
   Symbols: `observe_confirmation` / `consume_confirmation` (`disposition.py:54-87`).  
   Evidence: second scan does not submit or compare PID/process-start/progress/incarnation/cause; tests only cover TTL/separation/single sequential consume (`test_supervision_confirmation.py`).  
   Smallest correction: ledger-owned keyed confirmation with identity equality, replacement/expiry, restart replay, and locked one-consumer semantics.

7. **major — CLI contract incomplete.**  
   Symbol: `_record_cli` (`disposition.py:90-123`).  
   Evidence: no status-5 path; no consumed-confirmation check; `IncidentLedger.__init__` never raises on a bad path (`ledger.py:360-363`).  
   Smallest correction: implement exact 0/2/3/4/5 routing, ledger-location validation, and confirmation checks before append.

8. **major — acceptance tests and executor evidence are thinner than the gate.**  
   Evidence: 19 new tests; focused command 61 passed (Luna) vs start-gate receipt 52, later rewritten to 61; unreproduced digest `4aee815d...`.  
   Smallest correction: add behavioral regressions for every frozen must-criterion (races, crash/torn composite, forged hashes, context mismatch, incarnation/replacement, CLI 4/5) and persist command transcripts plus a reproducible owned-diff digest.

## Recommendation

The candidate is in NBF-01 file scope and the reproduced focused/legacy/compile/CLI happy paths are green. Frozen Batch 1 requires durable fail-closed primitives, not type-shaped records plus sequential stubs. CAS races, forgeable evidence, incomplete schemas, illegal reconciliation, global provider projection, confirmation gaps, and missing CLI statuses block the batch.

```text
ACCEPTED_ISSUES
```
