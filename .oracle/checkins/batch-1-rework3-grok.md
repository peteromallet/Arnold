# Grok 4.6 Oracle verdict — NBF-01 / Batch 1 rework 3

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
- Attempt-3 rework tasklist SHA-256: `c4c93f8b14e253060c0a403869e22a23aadc6444e63b32f48fd55cf95b63e779`
- Attempt-3 triage receipt: `2d025f9614d5dcf3f4e00de881962f1152a8be222b7cb4868055cf5a47856f4b`
- Executor finding: `.oracle/findings/execution-nbf01-rework3-luna.md` (`4897b2c7484aa7cc221488f7535339b716f780f3e70d62a202096504ac254e9f`)
- Executor receipt: `.oracle/receipts/execution-nbf01-rework3-luna.md` (`e34f901febedc434e27d778c3be5e070a6ded93a961a26dc1c4c62577339351f`)
- Luna review brief: `.oracle/briefs/oracle-nbf01-rework3-luna-review.md` (`a9210962bb5251585011256942c4c37795c1c444e22d43356eaf9a56a5cea911`)
- Luna review: `.oracle/checkins/batch-1-rework3-luna.md` (`573ce524b0c348445c7a0d89ee2a391fc3386135c72a124d09678735e1d727bd`)
- Luna review receipt: `.oracle/receipts/oracle-nbf01-rework3-luna.md` (`ad0e4e947a29dc796adf98ed40b04e26b92a6877d6457de98ab2ee3bf897a425`)
- Gate brief: `.oracle/briefs/oracle-nbf01-rework3-grok.md` (`5b062d0ded7552ce01bb7b4a7231a349419102a219c967c9a05cfbf46f2fdc01`)
- Owned production diff SHA-256: `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8`
- `incident/disposition.py` SHA-256: `2a59e440d7bcae53700b7ea63fdd2d15b1b1705eeb6914d24ea4f37300ab505a`; git blob `291c66ed2ac9b984e2c3d1f763bafcf7b86ca1c1`
- This check-in: `.oracle/checkins/batch-1-rework3-grok.md`
- This decision receipt: `.oracle/receipts/oracle-nbf01-rework3-grok.md`

Do not commit, push, or begin Batch 2 on this candidate. `[XHARD]` remains none.

## Gate and evidence identity

Exactly one independent GPT-5.6 Luna full review is already satisfied. No second reviewer, fan-out, helper review, or Grok self-review was commissioned. This turn is Oracle synthesis only.

Independently verified frozen identities match the resume brief. Owned tracked-production diff independently reproduces `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8`. `disposition.py` hashes match. `tests/arnold_pipelines/megaplan/test_incident_ledger.py` is unchanged versus `origin/main` (blob `44dc3adb87ad4dd077aed449c2f5ccc3526d8d93`, SHA-256 `83e8464c9dfd289aa08de41d044257936072e29ae1d8648f52b84f441f79a195`). Scope remains the five modified production files, new `incident/disposition.py`, and the eight named new test modules. Current custody SHA-256 `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` is unchanged. RW-CUSTODY remains MET.

Luna independently reproduced focused `112 passed in 15.31s` (stdout SHA-256 `b295944369c7307eae526dbb7f26489f657782bc8f7f7f104a1a5613ebfaaac3`) and legacy `78 passed in 1.47s` (stdout SHA-256 `6bf9fdef28e576401171fa27f28aed01180b01cf2c0864567bc6bc54d21d4f7b`). Oracle rehashed those isolated transcripts; they match. `py_compile` and `git diff --check` exit 0 with empty-stream SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. Counts remain observations, not targets.

Luna's check-in/receipt transcribe `collect_unchanged.json` stdout as `208afccf84501ad8455173d54844085406ca307fdd52686e935328bd860c9b3` (63 hex). The isolated transcript file itself is internally consistent; Oracle independently recomputes stdout SHA-256 `208afccf84501ad84544173d54844085406ca307fdd52686e935328bd860c9b3`. That is a review-receipt transcription error, not a second review and not a moving tree.

Historical evidence remains historical and was not rewritten: start-gate 52→61, unreproducible `4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70`, failed-handoff `50c864900a2f9d0fd5b6bc4240d97d365148e4cf2dd511749e9701fa059a09bf`, attempt-1 78/78 and `e060f650e112ecc8c73f4f2491e8504f3a1f1c9943b80f4e5aa97590b2925801`, attempt-2 production digest `16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d`. Current candidate digest `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8` is not an attempt-2 target.

Luna recommended `RECOMMEND_ACCEPTED_ISSUES`. Oracle independently re-read the cited producer/append symbols and reproduced the coherent-forgery probe. The blocker holds. Consume of the same forged event also succeeded, which Luna did not need to show once append accepted.

## Hard gates

| Gate | Status |
| --- | --- |
| One fresh immutable attempt-3 Luna execution receipt/finding | **MET as an artifact; NOT_MET as protocol completeness** (missing per-file `git hash-object` / SHA-256 inventory for `disposition.py` plus the eight new test modules; broad-suite output abbreviated) |
| Exactly one fresh independent Luna full review at required paths | **MET** |
| Candidate/diff and independent test-transcript digests recorded | **MET** via Luna review plus Oracle rehash; executor inventory incomplete |
| North Star disposition, KISS/YAGNI stated by Luna and Grok | **MET** as statements |
| All frozen NBF-01 must criteria met with behavioral evidence | **NOT_MET** |
| 52-vs-61 and `4aee815d…` treated as historical, not rewritten | **MET** |
| RW-CUSTODY unchanged | **MET** |

`PASS_BATCH_1` is unavailable because C19–C21 remain behaviorally false and several RW3 named-proof contracts remain unmet.

## Criterion dispositions

Statuses: `MET` | `NOT_MET` | `UNEVIDENCED`. Oracle confirmation is against the post-attempt-3 candidate, Luna's isolated `/tmp/oracle-nbf01-rework3-luna/` transcripts, and Oracle's independent `/tmp/oracle-nbf01-rework3-grok/` coherent-forgery probe. Luna numbering is preserved. Oracle calibrations are noted.

### NBF-01 acceptance criteria (tasklist)

| ID | Criterion | Status | Evidence |
| --- | --- | --- | --- |
| C01 | Strict round-trip of scheduling / six outcome kinds; unknown-field rejection | **UNEVIDENCED** | Constructor/decode reject unknown fields. Named matrix is rejection-only. Attempt-3 correctly did not reopen C01-as-`PhaseResult.from_dict` overweight; the six-kind round-trip remains unproved. |
| C02 | Invalid kind/state/payload combinations reject | **NOT_MET** | Source now rejects `worker_disposition`+`success_payload` at constructor (`phase_result.py:192-193`); independent constructor probe rejected. Required `test_dispatch_outcome_incompatible_payload_matrix` is still constructor-only, omits that pairing, and does not exercise `from_dict` / `validate_nbf_event` / append. |
| C03 | `no_launch` cannot serialize with `launch_state=accepted` | **MET** | `DispatchOutcome.__post_init__`; named test remains; focused transcript `b2959443…`. |
| C04 | `worker_disposition` requires accepted launch, disposition_id, receipt, fingerprint, phase/spec, logical/worker identity, start/finish | **MET** | Constructor plus `append_terminal_outcome` accepted-marker bind; named context tests. |
| C05 | Worker disposition cannot carry provider-exhaustion or no-launch state | **MET** | Constructor and `validate_nbf_event`; Luna probe `62fa6b24…`. Does not cure C02 named-matrix hole. |
| C06 | Maps only to `worker_terminal_outcome(outcome_kind=worker_disposition)` | **MET** | `terminal_outcome_kind` / `append_terminal_outcome`; named once-link test. |
| C07 | Mapping validates exactly one already-committed matching disposition; never re-appends it | **MET** as sequential CAS | Locked identical-replay; recovered-disposition test. Concurrent distinct-ID proof remains C09. |
| C08 | Never coerced into ordinary failure | **MET** | Named coercion test; focused transcript. |
| C09 | Duplicate linkage idempotent; conflicting linkage/kinds reject | **NOT_MET** | Required `test_two_process_terminal_linkage_is_atomic` still races the same outcome/ID and both children return `ok` (`test_incident_ledger_transactions.py:100-121`). Distinct-ID conflicting-kind race exists only under `test_distinct_terminal_ids_conflicting_kinds_have_one_winner`. Frozen contract makes the required name the proof. |
| C10 | Reservation closure and terminal-fingerprint projection occur exactly once, with persisted accepted launch | **MET** | `append_terminal_outcome` requires one receipt-bound accepted `controlled_adapter_state`. Replay sets `accepted_launch` from the marker, not the terminal (`ledger.py:604-610`). Luna and Oracle probes reject a fully populated terminal without the marker. |
| C11 | Worker disposition breaks provider-exhaustion consecutiveness without entering degradation | **NOT_MET** as named proof | Reducer mutates only a supplied `provider_failure_key` (`ledger.py:547-567`); missing key no longer falls back to `latest_stream_key`. Luna probe `nonlatest_success_A=2 latest_B=1`. Required non-latest disposition / ordinary-failure names are absent; `test_disposition_breaks_consecutiveness_without_degradation` still targets one stream. |
| C12 | `no_launch` produces no worker terminal/fingerprint/provider/streak | **MET** | Terminal writer rejects `no_launch` / `unresolved_launch`. |
| C13 | Worker / observed-death / non-worker schemas reject incomplete or fabricated identities | **UNEVIDENCED** | `_typed_worker_identity` now requires `host`/`pid`/`boot_id`; independent probe rejects a bare string. Named identity test is still selected omissions/version cases, not the complete decode/append matrix. |
| C14 | OOM requires positive cgroup evidence; unknown death remains unknown | **MET** | Constructor and append reject false/zero/negative OOM; legal positive OOM appends; fabricated killer and fabricated signal reject; legal unknown remains unknown after append. Luna probe `62fa6b24…`. |
| C15 | TERM and KILL ladder IDs are distinct | **MET** | Named test remains. |
| C16 | Semantic fingerprint excludes volatile liveness and logical/family IDs | **MET** | Named provider/fingerprint test. |
| C17 | Route-liveness digest absent from fingerprint and provider-failure key | **MET** | Same named test. |
| C18 | Different logical IDs with same projection key + fingerprint contend for one reservation | **MET** | Real two-OS-process `fcntl.flock` race; transaction subset `a64d95de…`. |
| C19 | Only allowlisted reason-specific producers may mint changes | **NOT_MET** | Generic `ChangedPrecondition.produce` and `produce_changed_precondition` now raise. The seven wrappers still accept caller dicts via `_authoritative_source`, which only checks `authority_kind`/`subject`/`content`. A caller-shaped snapshot is treated as the source. |
| C20 | Producer, evidence, subject, version, before/after, provider-key binding validated | **NOT_MET** | `append_changed_precondition` checks that a cited ledger event exists and that snapshots hash; it does not re-derive from an authoritative handle. |
| C21 | Forged unequal content IDs or provider-failure-key transitions reject | **NOT_MET** | Required `test_coherent_forged_provider_transition_with_recomputed_ids_rejects` mutates `provider_failure_key_after` without updating `after_snapshot`, so it rejects for snapshot/key mismatch. Oracle independently rebuilt snapshots, content IDs, and `event_id`: `from_dict` accepted, `append_changed_precondition` accepted, `consume_changed_precondition` accepted (`/tmp/oracle-nbf01-rework3-grok/independent_probes.json`, stdout SHA-256 `0979b341b6f9e933210bed6e992f7dc946a3a09541951388a5f20c4bc343be83`). Luna probe `62fa6b24…` independently accepted decode and append. |
| C22 | Valid changed-precondition consumed at most once | **MET** | Locked consume; `test_consumed_change_cannot_authorize_second_reservation`. Producer authority remains C19–C21. |
| C23 | `provider_recovery_verified` may authorize one linked same-route child without resetting/rekeying | **NOT_MET** | `reserve_provider_route_child` now checks a passed probe, matching lease, parent, and one authorizer; Luna recovery probe `89baff32…` shows missing/failed/second-use rejection plus one valid child. `append_probe_result` still accepts caller-supplied lease/key/evidence. Required full negative matrix names are absent. |
| C24 | Other allowlisted change resets/rekeys only when canonical before/after keys differ | **NOT_MET** | Reducer rekeys when before≠after (`ledger.py:575-581`), but those keys remain caller-forgeable (C19–C21). Named rekey test does not assert the unchanged streak numerically. |
| C25 | Ordinary two-process reservation contention yields one winner | **MET** | Same evidence as C18. |
| C26 | `provider_route_child_reserved` is one record and contains no child receipt-ID input | **MET** for shape | One append; no child receipt-ID argument. Authorization remains C23. |
| C27 | Receipt identity derives after append and reproduces byte-for-byte after fresh replay | **MET** | Required `test_fresh_replay_receipt_is_byte_identical` is now a real composite and reopens the ledger; provider subset `808c3d14…`. |
| C28 | Torn or failed writes cannot expose partial transitions, receipts, or projections | **NOT_MET** | Required torn-composite name calls real `reserve_provider_route_child` and injects `_emit_locked`. It does not inject the post-append receipt-derivation boundary required by RW3-03. |
| C29 | Every accepted terminal outcome projects fingerprint state before reservation closure | **MET** for reducer order | Provider/fingerprint reduction runs before `closed=True` (`ledger.py:568-572`). |
| C30 | Matching accepted `provider_exhausted` increments keyed streak | **MET** for matching stream | Increment at `ledger.py:557-559`. |
| C31 | Nonmatching accepted `provider_exhausted` rekeys at one | **MET** for first observation of a new key | `test_nonmatching_key_rekeys_at_one`. |
| C32 | Accepted worker success resets applicable streak and active key | **NOT_MET** as named proof | Source resets only the keyed stream when `provider_failure_key` is present; Luna probe success for A after B left A=2, B=1. Required `test_success_for_non_latest_key_does_not_reset_latest` is absent; `test_success_resets_only_applicable_key` is still A,A,B then success for latest B. |
| C33 | Intervening ordinary failure or worker disposition breaks consecutiveness without becoming degradation | **NOT_MET** as named proof | Reducer has keyed break code. Required `test_ordinary_failure_breaks_only_applicable_stream` is absent. |
| C34 | Probe results and `provider_recovery_verified` create/consume preserve matching streak | **NOT_MET** | Valid child preserves streak in the existing single-use test and recovery probe, but required preservation/negative matrix names are absent. |
| C35 | Scheduling, no-launch, unresolved, time, liveness refresh do not mutate provider streak | **MET** as primitive | Those events have no provider-terminal reducer branch. |
| C36 | Reconciliation permits only positive `released_no_launch`, recovered terminal, or durable ambiguous hold | **MET** | `ReservationReconciled.RESOLUTIONS`; named no-launch / hold tests. Attempt-3 correctly did not reopen marker provenance. |
| C37 | Recovered worker disposition links one existing canonical disposition and never duplicates | **MET** | Named recovered-disposition once-link test. |
| C38 | Blind release, conflicting reconciliation, and accepted-launch release as no-launch reject | **MET** | `test_blind_release_and_accepted_launch_release_reject`. |
| C39 | Durable two-scan state survives restart; TTL, scan separation, identity equality, single consumption, replacement/expiry | **NOT_MET** | `consume_confirmation` compares five identity fields, evidence digest, and persisted scan/expiry (`ledger.py:963-987`). `expire_confirmation` now rejects after consume. Required named identity test still omits TTL / `expires_at` / `scan_interval_s` / evidence-digest omissions. |
| C40 | Ledger lock, append, schema, projection-version, and cache failures fail closed | **UNEVIDENCED** | One journal and `_locked` fail-closed paths exist. Attempt-3 correctly did not expand cache-mismatch CAS; that complete matrix remains unproved. |
| C41 | Disposition CLI schema validation, acknowledgements, and exit codes match §4.21 | **MET** | Independent Luna subprocesses `cli2_*.json` exercise 0, malformed/schema 2, append 3, invalid location 4, missing/expired/same-identity/distinct-consumed 5. Status 0 is one JSON ack and does not signal. Oracle rehashed those streams. |

### Batch 1 checkpoint

| ID | Checkpoint | Status |
| --- | --- | --- |
| CP01 | Every NBF-01 focused test passes | **MET** as pytest gate only (Luna: `112 passed in 15.31s`). Does not cure ceremonial coverage. |
| CP02 | Schema fields and legal transitions match owned §§4.4–4.13, §4.16, §§4.19–4.21 | **NOT_MET** — C02 named matrix, C13 completeness, C19–C21, C39. |
| CP03 | `DispatchOutcome.kind=worker_disposition` is lossless and maps exactly once | **NOT_MET** — sequential mapping is lossless; required concurrent distinct-ID name is not (C09). |
| CP04 | One incident-ledger authority | **MET** for journal count / lock door. |
| CP05 | Accepted exhausted worker outcomes are the only increment inputs | **MET** for current replay. |
| CP06 | `provider_recovery_verified` remains single-use retry authorization while preserving streak | **NOT_MET** — C23/C34 named matrix. |
| CP07 | Success resets; different-key rekeys at one; ordinary/disposition break consecutiveness; only authoritative key change otherwise resets/rekeys | **NOT_MET** — required non-latest names absent; producer keys forgeable. |
| CP08 | Composite transition and child reservation remain one append with post-commit replay-stable receipt | **NOT_MET** as complete proof — composite replay is real; post-append receipt-boundary crash is not. |
| CP09 | No-launch, unresolved, ordinary failure, provider exhaustion, and worker disposition are mechanically distinct | **MET** for type/state; illegal payload named matrix remains (C02). |
| CP10 | No second journal, store, prepare/commit, scheduler, rotator, or policy owner | **MET**. |
| CP11 | Crash, contention, replay, torn-write, linkage, keyed-streak, TTL, incarnation, and single-consumption tests pass | **NOT_MET**. Reservation two-process contention is real; required terminal-race name, post-append crash, coherent producer forgery, and confirmation TTL matrix remain. |

### Rework tasks

| ID | Status | Evidence |
| --- | --- | --- |
| RW3-01 | **NOT_MET** | Accepted-launch marker and several payload/OOM/unknown-death doors closed (C10, C14). Coherent changed-precondition forgery still appends and consumes. Named six-kind matrix remains constructor-only. |
| RW3-02 | **NOT_MET** | Reducer is keyed in source and Luna's non-latest success probe works. All six required provider/recovery names are absent. `append_probe_result` remains caller-shaped. |
| RW3-03 | **NOT_MET** | Required fresh-replay name is a real composite. Required terminal-linkage name is still same-ID idempotency. Post-append receipt-boundary injection is absent. |
| RW3-04 | **NOT_MET** | CLI 0/2/3/4/5 including expired and matching already-consumed replay is independently proved (C41). Confirmation TTL/scan/evidence omission matrix remains thin (C39). |
| RW3-05 | **MET** | `hasattr(IncidentLedger, "reserve_provider_route_child_with_receipt")` is false; `reserve_provider_route_child` and `derive_receipt` remain. Independent Oracle probe confirmed. |
| RW3-06 | **NOT_MET** | Attempt-3 finding/receipt bind HEAD, source, and the production diff. They omit the required `git hash-object` and SHA-256 inventory for `disposition.py` plus all eight new test modules, and they abbreviate the broad sweep. Independent Luna transcripts cannot repair that immutable executor artifact. |
| RW3-GATE | **NOT_MET** | This Oracle gate returns `ACCEPTED_ISSUES`. |
| RW-CUSTODY | **MET** | Custody SHA `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` unchanged. `f8725af…` historical; `798c506…` current. |

### A3 dispositions

| A3 item | Status | Hole closed? |
| --- | --- | --- |
| A3-01 | **MET** | Fully populated terminal without persisted accepted marker rejects; single-field marker mismatch rejects. |
| A3-02 | **NOT_MET** | Worker+success source door exists; required named matrix is still constructor-only and incomplete. Typed identity coverage is selected, not complete. |
| A3-03 | **NOT_MET** | Coherent recomputed forgery accepted at `from_dict`, append, and consume. Named test is ceremonial. |
| A3-04 | **NOT_MET** | Source keyed behavior is independently probed; required non-latest named tests are absent. |
| A3-05 | **NOT_MET** | Valid child and some negatives exist; canonical probe binding and required complete matrix are insufficient. |
| A3-06 | **NOT_MET** | Composite fresh-replay is real; required terminal-race name and post-append crash remain. |
| A3-07 | **NOT_MET** | CLI complete; confirmation TTL/separation/evidence omission matrix is not. |
| A3-08 | **NOT_MET** | Executor inventory/stream completeness remains incomplete. |
| A3-09 | **MET** | Unofficial `reserve_provider_route_child_with_receipt` is absent. |

## Broad-suite relevance classification

Fresh Luna `pytest -q tests/arnold_pipelines/megaplan` stopped at collection (exit 2; stdout SHA-256 `602e26d1aaada829260638a8e5c880caa4b0efa7366c8968a7c7df1e489fa096`). Oracle independently confirmed:

1. `test_cli_check_validator.py` → `arnold.workflow.validator` → `arnold.agent.costing.model_resource_capabilities`.
2. `test_key_pool_codex.py` → `arnold.agent.run_agent` → `arnold.agent.tools.terminal_tool` → `tools.environments.singularity`.

Both modules are absent on the candidate and absent at `origin/main`. `git diff origin/main` over those import sites is empty. No owned attempt-3 file introduced, removed, or newly reached either import. Classification for both: **PRE_EXISTING_OUT_OF_SCOPE_BLOCKER**. This reduces broad-suite coverage and does not waive any NBF criterion.

## Preserved prior-MET result

Independently confirmed intact: one `_IncidentEventJournal` + sequence-sidecar flock; NBF writes enter `_locked` / `_append_nbf_locked`; C03–C08, C12, C15–C18, C22, C25, C26 shape, C29 order, C30/C31 matching/rekey-at-one, C35; CP04 journal count, CP05 increment rule, CP10; real two-process reservation contention; owned source scope; RW-CUSTODY; historical-evidence integrity. Attempt-3 additionally closed C10, C14, C27, C41, and A3-09 without opening a second journal or later-batch door. Preservation is not Batch 1 acceptance.

## North Star

1. **One door per invariant — NOT MET for the Batch 1 primitive.** One journal and one `_locked` door remain. The changed-precondition door still treats caller snapshots as authoritative sources, so a second informal minting path exists beside the allowlisted producer names.
2. **Deaths speak — foundation only.** Typed worker / observed-death / non-worker records, positive OOM, legal unknown death, and a non-signalling CLI exist. Signal-site wiring is correctly deferred.
3. **Models are admitted, not assumed — correctly deferred.** No admission/catalog/live-provider caller changed.
4. **Fixes ship on main through the fixer contract — not evidenced.** No commit/push/merge, as required for this uncommitted gate.

### Anti-patterns

- **Single-scan verdicts as sustained truth — NOT MET as complete confirmation identity.** Locked five-field compare and expiry-after-consume exist; TTL/scan/evidence omission matrix does not.
- **Anonymous integer exit codes — MET for the owned CLI primitive.** Typed disposition records and CLI 0/2/3/4/5 are independently bound. Real signal wiring is later.
- **Judgment-based “healthy” claims — improved, not closed.** Terminal acceptance now requires a persisted accepted-launch marker. Changed-precondition still accepts a well-formed caller snapshot as proof.
- **Identical-fingerprint redispatch without a changed precondition — NOT MET as a complete durable block.** Two-process reservation contends (C18/C25). A coherent forged change can still be appended and consumed.

## KISS / YAGNI / scope creep

- **File scope:** MET. No admission caller, scheduler, T7/T8 policy, physical door, launch adapter, signal site, fallback policy, second journal, or rotator was added. Unofficial route-child wrapper was deleted.
- **KISS:** NOT MET at quality. `_locked` is the right small door. `_authoritative_source` is still a caller-dict adapter wearing an authority name.
- **YAGNI:** MET in batch boundary; no UnitOfWork / two-phase / extra projection service.
- **Ceremonial validation:** NOT MET. Named coherent-forgery, six-kind matrix, non-latest keyed, required terminal-race, and confirmation-TTL tests remain thin or absent. Green 112/78 cannot substitute.
- **Later-batch behavior in the candidate:** MET (absent).

## Independent confirmation of Luna blockers

Oracle read the cited symbols and independently reproduced the coherent-forgery path.

1. `_authoritative_source` (`schema.py:562-576`) copies a caller dict after checking `authority_kind`, `subject`, and `content`. `_produce_authoritative` hashes those snapshots. `append_changed_precondition` (`ledger.py:774-794`) only requires a persisted cited event whose digest matches.
2. The named coherent-forgery test (`test_changed_precondition_producers.py:38-48`) changes `provider_failure_key_after` without updating `after_snapshot`; Oracle confirmed that style rejects with `provider_failure_key_after is not derived from its authoritative source`.
3. Rebuilding `after_snapshot`, `after_content_id`, and `event_id` produced a coherent event that `ChangedPrecondition.from_dict` accepted, `IncidentLedger.append_changed_precondition` accepted, and `consume_changed_precondition` accepted.
4. `test_dispatch_outcome_incompatible_payload_matrix` is constructor-only and omits `worker_disposition`+`success_payload`.
5. `test_two_process_terminal_linkage_is_atomic` still shares one outcome ID.
6. Required non-latest / recovery-matrix names listed in RW3-02 are absent from the eight new modules.
7. `test_torn_composite_write_exposes_neither_transition_nor_receipt` injects `_emit_locked` and does not inject post-append receipt derivation.
8. Executor finding/receipt omit the RW3-06 per-file hash inventory.

## Issues

Each issue is a required correction. Do not implement in this Oracle turn.

1. **blocker — changed-precondition authority remains forgeable (C19–C21, RW3-01, A3-03).**  
   Symbols: `_authoritative_source`, `_produce_authoritative`, `append_changed_precondition`, `consume_changed_precondition`.  
   Evidence: Oracle probe `/tmp/oracle-nbf01-rework3-grok/independent_probes.json` stdout SHA-256 `0979b341b6f9e933210bed6e992f7dc946a3a09541951388a5f20c4bc343be83`; Luna `independent_probes.json` stdout SHA-256 `62fa6b24fdf1db5c4e2e098b757c227384d137d0a3384528c0769835f4e115c1`. Named test is ceremonial.  
   Smallest correction: typed authoritative source readers/handles per allowlisted reason; reject a coherent recomputed forgery at `from_dict`, append, **and** consume; retarget the existing named test to that coherent path.

2. **blocker — required strict matrix evidence is incomplete (C02/C13, RW3-01, A3-02).**  
   Evidence: named matrix is constructor-only; worker+success source door exists but is not in that named test; typed identity named coverage is selected.  
   Smallest correction: strengthen the existing named tests in place across constructor, decode, validation, and append.

3. **major — applicable-key and recovery named proof is missing (C11/C32/C33/C34, CP06/CP07, RW3-02, A3-04/A3-05).**  
   Evidence: source reducer is keyed and Luna's A-after-B success probe works; required names are absent; `append_probe_result` remains caller-shaped.  
   Smallest correction: add the required non-latest and canonical-probe matrix tests with numeric stream assertions; bind probes to an existing unexpired lease.

4. **major — composite and terminal race evidence is incomplete (C09/C28, CP08/CP11, RW3-03, A3-06).**  
   Evidence: required terminal-linkage name is same-ID idempotency; distinct-ID race is under another name; no post-append receipt-boundary injection.  
   Smallest correction: move the distinct-ID OS-process race under the required name and add post-append crash/reopen both-or-neither coverage.

5. **major — durable confirmation equality matrix is incomplete (C39, RW3-04, A3-07).**  
   Evidence: CLI 0/2/3/4/5 is independently complete (C41). Named confirmation test omits TTL / expiry / scan-interval / evidence-digest omissions.  
   Smallest correction: require and compare every frozen confirmation identity/TTL/separation field in the existing named test.

6. **major — immutable executor evidence protocol is incomplete (RW3-06, A3-08).**  
   Artifact: `.oracle/receipts/execution-nbf01-rework3-luna.md` / `.oracle/findings/execution-nbf01-rework3-luna.md`.  
   Evidence: missing per-file `git hash-object` and SHA-256 for `disposition.py` and the eight new test modules; broad sweep summarized. Independent review transcripts do not rewrite the executor artifact.  
   Smallest correction: publish a new immutable executor finding/receipt for the exact post-fix tree; do not edit historical artifacts.

7. **major — broad-suite coverage is reduced (CP01 context).**  
   Classification: **PRE_EXISTING_OUT_OF_SCOPE_BLOCKER**. Not an NBF regression and not a waiver.  
   Smallest correction: restore the two missing modules in the source-base environment or run a source-base-equivalent sweep; do not waive in-scope criteria.

8. **minor — C01/C40 remain unevidenced.**  
   Attempt-3 correctly did not reopen C01-as-`PhaseResult.from_dict` overweight or C40 cache-mismatch expansion. They still are not MET. Do not expand them in attempt 4 unless a frozen must cannot live in the eight new modules.

## Recommendation

Attempt 3 landed real progress: persisted accepted-launch markers, typed OOM/unknown-death append paths, worker+success source rejection, keyed reducer without latest-stream fallback, real composite fresh replay, `_emit_locked` composite crash, CLI 0/2/3/4/5 including expired and matching already-consumed replay, expiry-after-consume rejection, and deletion of the unofficial route-child wrapper. The Batch 1 primitive still admits a coherent forged changed-precondition at decode, append, and consume, and several frozen named proofs remain ceremonial or absent. Green 112/78 cannot close those holes. Batch 2 remains prohibited.

Smallest next action: write `.oracle/rework/batch-1-attempt-4.md` covering issues 1–6 only, in serial order starting with the C19–C21 coherent-forgery blocker (RW4-01), then the remaining evidence-contract holes. Keep classification **Normal / GPT-5.6 Luna**; `[XHARD]` remains none. Do not reopen C36–C38, C01-as-`PhaseResult.from_dict` overweight, C40 cache-mismatch expansion, T8 policy, custody, historical receipts, or Batch 2. Then dispatch Luna, require one complete HEAD-bound execution receipt with the missing per-file inventory, then one fresh independent Luna review and a separate Grok Oracle gate. Do not implement, commit, push, merge, edit custody, rewrite historical receipts, or start Batch 2 in this turn.

```text
ACCEPTED_ISSUES
```
