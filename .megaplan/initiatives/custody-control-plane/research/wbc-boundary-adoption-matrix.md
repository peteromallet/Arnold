---
type: research
date: 2026-07-21
schema: custody-control-plane-wbc-boundary-inventory-v2
m9_updated: true
---

# Maintained WBC boundary adoption matrix

## Authority and evidence baseline

This matrix is the canonical universal-adoption register for this initiative.
It does not replace the WBC contract-to-producer matrix; M6 generates an exact
row-level inventory from the final landed WBC revision and joins it here to
production call sites, consumers, implementation commits, tests, and runtime
traces.

Read-only audit observed completed candidate
`cbe69337d6f469fd7ae12f1fd0a51007d93b5d70`, subsequently landed by audited
no-ff merge `24afce006b9ad20391ac7af10ef67ea0b1774f9f`. The candidate's
`ExecutionAttemptLedger` is schema-only, and
its 35-row producer matrix reports 5 auto-matched, 8 manual-emission, 13
declared-only, and 9 unknown contracts. Its 76-entry support manifest therefore
cannot establish universal runtime adoption. M6 must replace this observational
baseline with exact landed/source/editable/runtime proof and must reject the old
four-milestone cloud terminal label as completion of the current C1-C6 chain.

## M9 consumer/projection migration evidence (Step 14 — T23)

This section records the reader inventory and adoption evidence generated during
M9 Steps 1–13 (T1–T22). Every consumer listed below has been migrated to
canonical WBC queries with exact source-cursor vectors. Display-only projections
carry `evidence_extracted_non_authoritative` or `evidence_extracted_display_only`
authority markers and cannot feed dispatch, completion, cancellation,
publication, or delivery.

### Canonical WBC query facade (T1–T2)
- **`arnold/workflow/wbc_queries.py`** — typed read-only facade over
  `AttemptLedgerStore`/`SqliteAttemptLedgerStore`. Returns immutable envelopes
  (`WbcStartEnvelope`, `WbcTerminalEnvelope`, `WbcLedgerEnvelope`,
  `WbcGapEnvelope`, `WbcSourceCursorEnvelope`) with `GateStatus`
  (`VERIFIED`/`INCOMPLETE`/`INDETERMINATE`/`INCOHERENT`). No second authority
  store. Exported from `arnold/workflow/__init__.py`. 43 focused tests pass.

### Projection primitives (T3–T4)
- **`arnold_pipelines/megaplan/_core/io.py`** — 14 shared primitives:
  `ProjectionCursor`, `ProjectionRecord`, `ProjectionCursorMismatchError`,
  deterministic serialization (`_projection_canonical_dumps`), atomic
  append/replay/rebuild, monotonic cursor validation, mismatch preservation.
  72 focused tests pass.

### Custody projections (T5)
- **`arnold_pipelines/megaplan/custody/projections.py`** — stabilized against
  `_core/io.py` primitives. 52 focused tests: append, replay, rebuild, cursor
  mismatch, recovery snapshots, source-cursor validation, batch append,
  non-authoritative outputs, store lifecycle, event types. All custody
  projection outputs are non-authoritative.

### Rebuild registry (T6)
- **`arnold_pipelines/megaplan/observability/projection_rebuild.py`** —
  `ProjectionRegistry` for in-scope projection builders, source cursor vectors,
  ordered view digesting, delete/rebuild comparison. Never mutates source
  evidence. 45 focused tests pass.

### Run-state model with M9 dimensions (T7–T8)
- **`arnold_pipelines/megaplan/run_state/model.py`** — extended with
  `FailureTokenKind`, `NormalizedFailureToken`, `WbcEvidenceRef`,
  `RunAuthorityRef`, `CustodyRef`, `UncertaintyLevel`. Seven M9 fields added to
  `CanonicalRunState` (failure_token, wbc_refs, run_authority_ref, custody_ref,
  freshness_seconds, lag_seconds, uncertainty). Stable to_dict/from_dict
  round-trips.
- **`arnold_pipelines/megaplan/run_state/classifiers.py`** — normalized failure
  token extraction from chain_state/plan_state/run_metadata evidence. Pure
  read-only resolver. 36 focused tests pass.

### Status/CLI projection migration (T9)
- **`arnold_pipelines/megaplan/status_projection.py`** — threaded exact source
  cursor vectors and canonical WBC query inputs. 40 display-fallback authority
  tests prove display cannot feed dispatch/completion/cancellation/publication/
  delivery.
- **`arnold_pipelines/megaplan/cli/status_view.py`** and
  **`cli/projection.py`** — migrated to canonical inputs. Review/rework behavior
  preserved from commit `07f428d361f63c465b0dafaca9783585efeaa4b9`.

### Chain status WBC authority (T10)
- **`arnold_pipelines/megaplan/chain/status.py`** — terminal and completion
  status reads derive from canonical WBC terminal/gap queries. Drift records
  emitted when live active attempts invalidate stale terminal labels. Legacy
  chain JSON is compatibility projection only. 25 focused tests pass.

### CHAIN-01 enforcement and warn-only audit (T11–T14)
- **CHAIN-01** (`_latest_execution_batch_all_tasks_done` in chain/__init__.py)
  is the sole enforced positive-authorization route. 22 warn-only routes, 1
  informational, 5 deferred. All 29 AUTHORITY_ROUTES have traceable
  dispositions. Zero new failures vs recorded baseline across all verification
  steps.

### Cloud status/target/blocker migration (T15–T16)
- **`arnold_pipelines/megaplan/cloud/status_snapshot.py`** and
  **`status_format.py`** — migrated from marker/watchdog/report/plan-state
  authority reads to canonical query projections. Stale/degraded display fields
  preserved as structured evidence gaps.
- **`arnold_pipelines/megaplan/cloud/current_target.py`** and
  **`human_blockers.py`** — canonical query projections with typed evidence
  gaps. Same-input agreement tests against CLI, cloud status, and resident
  outputs. 41+26+82 = 149 focused tests pass.

### Watchdog liveness correlation (T17)
- **`arnold_pipelines/megaplan/watchdog/processes.py`**,
  **`correlate.py`**, **`snapshot.py`** — process/tmux/heartbeat/activity facts
  are correlated evidence only. `classify_worker_liveness` returns
  matched/recycled/hung/dead/unrelated; every non-matched class maps to
  `RUNNER_UNKNOWN` or `RUNNER_LOST`. Never success/repair/complete/verified.
  56 focused tests pass.

### Repair dispatch identity (T18–T19)
- **`arnold_pipelines/megaplan/cloud/repair_requests.py`** — `RepairDispatchIdentity`
  frozen dataclass binding environment/session/chain/plan_revision/phase/task/
  attempt/normalized_failure_kind/dispatch_digest_kind/dispatch_digest/
  coordinator_fence_token with provenance.
- **`arnold_pipelines/megaplan/cloud/repair_contract.py`** and
  **`repair_revalidation.py`** — require source rereads before repair, retry,
  escalation, cancellation, or adoption. 66 focused tests pass.

### Projection rebuild metadata (T21–T22)
- **`arnold_pipelines/megaplan/schema_projection.py`**,
  **`capsule_projection.py`**, **`strategy/projection.py`** — rebuild metadata
  (source cursor, freshness/lag, digest) added to deterministic reducers.
  Reducers kept pure; side effects moved outside rebuild paths. 55+50 = 105
  focused tests pass.
- **`arnold_pipelines/megaplan/prompts/_projection.py`**,
  **`workers/_projection_caps.py`**,
  **`orchestration/advisory_projection.py`** — rebuild metadata, freshness/lag
  fields, digest calculation. Reducers pure and side-effect-free. 50 focused
  tests pass.

### Resident/Discord display verification (T20)
- Resident views (`currently_running_command`, `status_tree`,
  `discord_adapter`) verified as display-only. 53 tests pass. No new failures
  vs recorded baseline.

### Cross-surface test baseline
- **428 tests** across M9 foundation+consumer+projection surface: all pass.
- **`tests/arnold/workflow/`**: 1380 passed / 9 failed — exact match to recorded
  pre-existing baseline (canonical_megaplan_conformance, native_wbc_adoption,
  source_compiler_api×4, static_scans×3 — none touch wbc_queries.py or M9
  projection code).
- `python -m compileall arnold arnold_pipelines tests` — clean, zero errors.

## Generated artifact and completion equation

M6 must implement and version `tools/generate_wbc_boundary_inventory.py`, commit
discovery rules in `evidence/wbc-boundary-discovery-rules.yaml`, generate and
thereafter update `evidence/wbc-boundary-inventory.json`, maintain historical
adapters in `evidence/wbc-historical-adapters.json`, and add blocking CI
acceptance for all four. The generator
must derive rows from all of the following:

1. the exact landed WBC contract and producer inventories;
2. independent AST/semantic discovery of Python/native dispatch, worker/provider execution,
   lifecycle transition, effect, fanout/reducer, publication/delivery, repair,
   resident, cloud, subprocess and wrapper call sites;
3. discovery of consumers that classify, advance, repair, publish, deliver,
   retain, migrate, or project attempt/boundary state; and
4. an independent channel of captured runtime traces from representative success, failure,
   cancellation, suspension/resume, retry/replay, crash, and migration cases.

The generator must expose declared-only, static-only, runtime-only, consumer-
only, wrapper/dynamic-only, and adapter-only unmatched sets separately. Each
must be empty or have a default-deny registered row. Dynamic/generated/native/
shell/provider surfaces cannot disappear because a Python AST scanner cannot
resolve them. The discovered set must equal the union of registered canonical
rows and explicit read-only historical adapters. There is no unexplained or
manually excluded bucket. A historical adapter row must name exact path/symbol,
read operations, supported versions, zero-authority-caller proof, owner,
approver, expiry and deletion gate. A row is complete only when all required fields below are
populated by content-addressed evidence and its positive and negative tests
pass. Schema presence, a support-manifest label, a fixture-only emitter, or a
manual assertion cannot complete a row.

## Required fields per generated row

| Field | Required evidence |
| --- | --- |
| identity | stable boundary ID, family, immutable landed base contract/profile/version/hash, approved WBC substrate/API revision, adopter revision, exact installed/editable/cloud/resident runtime vector, run/subject/WBC attempt IDs, causal parents |
| ownership | contract owner, named producer owner, named consumer owner, operational approver; no overlapping writer |
| producer | source path/symbol or wrapper, durable reservation/start writer, phase/effect writer, exactly-one-terminal writer |
| semantics | success/failure/cancel/suspend/resume/retry/indeterminate behavior; transaction/outbox and post-write reread |
| consumer | canonical query path/symbol, cursor/version checks, unknown/incoherent behavior, projection-only declaration where applicable |
| data policy | payload/reference class, tenant/access, encryption/key scope, retention/legal hold/tombstone/deletion and migration version |
| migration | current state, backfill/read-only policy, compatibility expiry, rollback/forward-fix, legacy writer/reader deletion gate |
| proof | implementation commit, static call-site case, runtime trace digest, positive test, negative bypass test, fault/replay/migration case |
| status | `observed`, `blocked`, `substrate-ready`, `producer-adopted`, `consumer-adopted`, `conformant`, or `retired`; never inferred from prose |

## Contract-family rows from the audited candidate

M6 preserves the final landed IDs exactly; the names below are the minimum
audited baseline and may only be changed by evidence from that landed revision.

| Family owner | Required boundary IDs | Current audited state | Implementation milestone | Acceptance owner |
| --- | --- | --- | --- | --- |
| auto phase transitions — Megaplan runtime | `prep_to_plan`, `plan_to_critique`, `critique_to_gate`, `gate_to_revise`, `revise_to_critique` | auto-matched, runtime durability unproven | M8 | M11 |
| execute/batch — execute runtime | `execute_approval`, `execute_approval_denial`, `execute_batch_checkpoint`, `execute_partial_failure`, `execute_blocked_anchor`, `execute_resume_anchor`, `execute_aggregate_promotion`, `execute_no_review_terminal` | manual emission, durability unproven | M8 | M10/M11 |
| tiebreaker — tiebreaker workflow | `researcher_to_challenger`, `challenger_to_synthesis`, `synthesis_to_decision`, `decision_to_parent` | declared-only | M8 | M11 |
| replan — auto/override workflow | `replan_authority` | unknown | M8 | M11 |
| child/reducer — parent workflow | `parent_rejoin_promotion` | declared-only | M8 | M10/M11 |
| review/rework — review workflow | `child_outputs`, `reducer_promotion`, `rework_effects`, `cap_authority`, `human_verification` | declared-only | M8 | M10/M11 |
| finalize/publication — finalize/chain workflow | `finalize_artifacts`, `finalize_fallback`, `final_projection` | declared-only | M8 | M10/M11 |
| human/operator overrides — override workflow | `abort`, `force_proceed`, `replan`, `recover_blocked`, `resume_clarify`, `adopt_execution`, `suspension`, `human_gate` | unknown | M8 | M10/M11 |

Every contract row requires a durable start-before-dispatch and exactly one
terminal result, even when a boundary also has a phase-specific receipt. “No
user code dispatched” must still terminate the accepted attempt as failed,
cancelled, or indeterminate.

## Operational boundary-family rows

| Family | Named production owner | Required implementation/evidence | Milestone |
| --- | --- | --- | --- |
| admission and common phase execution | Megaplan runtime | init/auto/supervisor admission plus common worker start/finish use the WBC API; phase-result absence cannot become success | M8 |
| worker/provider/process dispatch | Megaplan executor | reservation/start before `run_step_with_worker`, provider command, subprocess or managed process; signal-safe terminal/reconcile | M8/M10 |
| fanout, children, reducers and aggregation | Megaplan workflow owners | child attempt lineage, reducer input/output, partial child failure and parent terminal evidence; no unparented promotion/delivery | M8/M10 |
| chain, epic, bakeoff, finalize, PR/publication | Megaplan chain/publication | phase and external-effect intents/outcomes around advancement, finalize, merge, publication and fallback | M8/M10 |
| resident managed children, scheduler and delivery | Resident runtime | launch/start/terminal plus parent-owned aggregation and ordinary/scheduled delivery effect evidence | M8/M10 |
| cloud/AgentBox/provider adapters and wrappers | Megaplan Cloud / AgentBox | process-safe API, exact runtime identity, no shell `|| true` or swallowed required append | M8/M10 |
| watchdog, L1/L2/L3 repair and progress auditor | Custody / Maintenance | canonical WBC queries/triggers, exact occurrence joins, persistence gaps explicit; findings never self-authorize repair | M9/M10 |
| local/resident/cloud status, trace and operator views | Observability / Resident / Cloud | exact-cursor canonical WBC query, pure rebuildable projection, no token/prose/raw-state authority | M9 |
| cancellation, suspension/resume, retry/replay/recovery | lifecycle / workflow owner | every accepted branch terminates prior attempt and records new causal attempt/effect; ambiguity stays indeterminate | M8/M10 |
| retention, privacy, encryption and deletion | WBC data-policy owner | enforcement against stored bytes, key/version audit, tenant isolation, legal hold, tombstone/deletion evidence | M6A/M9/M11 |
| schema/data migration and historical reads | WBC migration owner | deterministic checksum migration/backfill, crash-resume, mixed versions, explicit unknown, read-only expiry | M6A/M9/M11 |
| generated static/runtime conformance | WBC conformance owner | call-site set equality, runtime-trace coverage and bypass-negative suite regenerated at pinned runtime revision | M6/M8/M11 |

## Mandatory negative checks

The generated suite fails if it finds any of the following without an approved,
read-only, expiring historical-adapter row:

- a direct legacy attempt/effect/status writer outside the WBC API;
- dispatch, worker/provider/subprocess start, transition, publication or
  delivery without a durable attempt start;
- an accepted attempt with no terminal, multiple terminals, or an event after
  terminal;
- `except Exception`/warn-and-continue, `without raising`, evidence-only,
  best-effort, or shell `|| true` behavior around a required write;
- a phase-specific or generic receipt that can be omitted while lifecycle
  success/advancement still occurs;
- a consumer deriving positive status or action authority from raw JSON, prose,
  tokens, filenames, markers, process facts, mutable receipts, or implicit
  latest contract/schema;
- a protected payload stored without required encryption/access/retention
  enforcement or deleted without tombstone/audit evidence;
- a migration that fabricates terminal success, loses an unknown, rewrites
  history, or cannot resume after interruption; or
- a contract marked supported with no implementation commit, static call-site
  case, captured runtime trace, positive test, and negative bypass case.

## M9 historical adapter retirements

As of M9 Step 14 (T23), the following six M8-expiry historical adapters are
marked **non-authoritative** with **zero-reader gates** and **retired** status:

| Adapter ID | Adapter Class | Expired At | Reader Name | Zero-Reader Gate |
| --- | --- | --- | --- | --- |
| `legacy-bakeoff-state-reader` | raw_json | M8→M9 | Bakeoff State Consumer | No dispatch, completion, or lifecycle authority permitted |
| `legacy-chain-state-reader` | raw_json | M8→M9 | Chain State Consumer | No dispatch, completion, or lifecycle authority permitted |
| `legacy-heartbeat-state-reader` | raw_json | M8→M9 | Heartbeat State Consumer | No dispatch, completion, or lifecycle authority permitted |
| `legacy-repair-lock-reader` | process | M8→M9 | Repair Lock Consumer | No dispatch, completion, or lifecycle authority permitted |
| `legacy-status-snapshot-reader` | raw_json | M8→M9 | Cloud Status Snapshot Consumer | No dispatch, completion, or lifecycle authority permitted |
| `legacy-supervisor-state-reader` | raw_json | M8→M9 | Supervisor State Consumer | No dispatch, completion, or lifecycle authority permitted |

Six M9-expiry adapters (`historical-filename-reader`, `historical-marker-reader`,
`historical-mutable-receipt-reader`, `historical-process-reader`,
`historical-prose-reader`, `historical-token-reader`) remain compatible through
M9 with read-only diagnostic-only shadow mode. They expire at M9 completion.

All retired adapters have `supported_versions: ["retired"]`,
`non_authoritative: true`, and `zero_reader_gate` active. The zero-reader gate
prohibits reads by any dispatch, completion, cancellation, publication, delivery,
repair, or lifecycle-transition path. Only evidence-extracted non-authoritative
historical references remain permitted for traceability until deletion.

## Persistence and migration coverage (M9)

The `evidence/wbc-boundary-inventory.json` now classifies all 551 rows with
typed `persistence_coverage` and `migration_coverage` fields:

- **Persistence coverage:** 0 coherent / 551 indeterminate / 0 incoherent
- **Migration coverage:** 0 coherent / 551 indeterminate / 0 incoherent

Rows are typed `indeterminate` when they lack canonical WBC query/projection
coverage with exact source-cursor vectors. Rows become `coherent` only when
verified via canonical WBC queries. No row is typed `incoherent` (identity
or cursor disagreement) at this stage. The conservative indeterminate posture
reflects that M9 consumer migration is in progress; M10 and M11 will move
indeterminate rows to coherent through runtime trace and cross-contract
acceptance evidence.

## Milestone gates

- **M6:** bind the final landed WBC revision and runtime vector; generate the
  exact inventory and classify every row. Unknown or missing proof blocks.
  **COMPLETE.**
- **M6A:** make the WBC store/API, payload policy and migrations operational.
  **COMPLETE.**
- **M8:** migrate every producer/writer family and attach static plus runtime
  evidence to each row. No "residual only" or manifest-proven exemption.
  **COMPLETE.**
- **M9:** migrate every consumer/projection/retention operational surface.
  **IN PROGRESS** — Steps 1–13 (T1–T22) complete. Step 14 (T23) retires
  M8-expiry adapters and classifies persistence/migration coverage.
  Steps 15+ (T24–T36) pending: work-ledger, auditor reasons, gate wrapper
  bypasses, and final validation.
- **M10:** prove crash, failure injection, effect reconciliation, replay,
  cancellation/resume and cross-host recovery behavior.
- **M11:** run cross-contract and mixed-version acceptance, prove exact static
  and runtime set equality, retire proven bypasses, and generate the completion
  proof map. Any row below `conformant` or approved read-only `retired` fails the
  initiative.
