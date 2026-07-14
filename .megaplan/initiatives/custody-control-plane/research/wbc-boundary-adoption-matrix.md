---
type: research
date: 2026-07-14
schema: custody-control-plane-wbc-boundary-inventory-v1
---

# Maintained WBC boundary adoption matrix

## Authority and evidence baseline

This matrix is the canonical universal-adoption register for this initiative.
It does not replace the WBC contract-to-producer matrix; M6 generates an exact
row-level inventory from the final landed WBC revision and joins it here to
production call sites, consumers, implementation commits, tests, and runtime
traces.

Read-only audit observed the completed candidate
`cbe69337d6f469fd7ae12f1fd0a51007d93b5d70` and an in-progress integration
merge `24afce006b9ad20391ac7af10ef67ea0b1774f9f`. Neither is declared the final
landed revision. The candidate's `ExecutionAttemptLedger` is schema-only, and
its 35-row producer matrix reports 5 auto-matched, 8 manual-emission, 13
declared-only, and 9 unknown contracts. Its 76-entry support manifest therefore
cannot establish universal runtime adoption. M6 must replace this observational
baseline with exact landed/source/editable/runtime proof supplied after merge.

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

## Milestone gates

- **M6:** bind the final landed WBC revision and runtime vector; generate the
  exact inventory and classify every row. Unknown or missing proof blocks.
- **M6A:** make the WBC store/API, payload policy and migrations operational.
- **M8:** migrate every producer/writer family and attach static plus runtime
  evidence to each row. No “residual only” or manifest-proven exemption.
- **M9:** migrate every consumer/projection/retention operational surface.
- **M10:** prove crash, failure injection, effect reconciliation, replay,
  cancellation/resume and cross-host recovery behavior.
- **M11:** run cross-contract and mixed-version acceptance, prove exact static
  and runtime set equality, retire proven bypasses, and generate the completion
  proof map. Any row below `conformant` or approved read-only `retired` fails the
  initiative.
