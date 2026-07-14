---
type: research
date: 2026-07-14
status: read-only-planning-evidence
---

# WBC revision, producer, and consumer adoption audit

## Durable evidence lineage

Three resident-managed read-only investigations were launched for the planning
update and completed with child delivery suppressed:

| Run ID | Scope | Result artifact |
| --- | --- | --- |
| `subagent-20260714-132411-1dc7f084` | authoritative WBC branch, revision, contracts, schema and conformance audit | `.megaplan/plans/resident-subagents/subagent-20260714-132411-1dc7f084/result.md` |
| `subagent-20260714-132411-3b9a22df` | production boundary producer/writer and common call-site inventory | `.megaplan/plans/resident-subagents/subagent-20260714-132411-3b9a22df/result.md` |
| `subagent-20260714-132411-ed86573d` | consumer, runtime, retention/privacy/migration and verification inventory | `.megaplan/plans/resident-subagents/subagent-20260714-132411-ed86573d/result.md` |

The project/runtime baseline inspected by the synthesis owner was
`612b139971e1a65d2a40f9e387a5e8ff3e2ab960`. The checkout was concurrently
dirty, so no claim is made that it was deployable and no unrelated work was
normalized.

## Revision verdict

- Completed WBC candidate: remote-tracking
  `origin/megaplan/s4-consumption-and-general-20260714-0128` at
  `cbe69337d6f469fd7ae12f1fd0a51007d93b5d70`, inspected in detached worktree
  `/workspace/arnold-wbc-source-verify`.
- Candidate milestone ancestry includes `9a1d3f02…`, `3e788c90…`,
  `599cd2fa…`, then `cbe69337…`.
- Audited integration: no-ff merge commit
  `24afce006b9ad20391ac7af10ef67ea0b1774f9f` joined the WBC candidate into
  canonical main. Consolidation run `subagent-20260714-124257-a1b920cf`
  independently verified its exact parents, remote containment, and activated
  source/editable/runtime vector at `1fc545cc0c95c933a88fbf5b2556b479d76a31bd`.
- `origin/editible-install` `405eb641…`, local `editible-install` `91a33dab…`,
  and old detached WBC baseline `826863ce…` are stale/non-authoritative for this
  work and lack the audited ledger/conformance core.

M6 must verify the audited merge against the then-current landed and
source/editable/install/runtime vector. It must not fabricate a completion
manifest for the current C1-C6 chain from the old S1-S4 terminal state.

## Contract and substrate verdict

At the completed candidate:

- `arnold/workflow/execution_attempt_ledger.py` explicitly describes
  `ExecutionAttemptLedger` as schema-only. There is no production append/read
  store, transaction coordinator, WAL, outbox, or prepare/commit API and no
  production reference beyond exports/manifests/docs/tests.
- Identity, lifecycle precedence and typed `INDETERMINATE` vocabulary exist,
  but empty/non-terminal ledgers, cross-event idempotency uniqueness, multiple
  terminals, post-terminal events and dispatch-before-start are not all
  operationally prevented.
- `arnold/workflow/boundary_evidence.py` and
  `boundary_conformance.py` define receipts, contracts, findings and static
  checks; they do not make production persistence mandatory.
- `durable_refs.py` and `payload_policy.py` validate privacy, redaction,
  retention, legal-hold, tombstone and encryption metadata. They do not encrypt,
  retain, redact, delete or migrate stored bytes; an unencrypted default remains
  possible.
- Generated evidence includes `contract_to_producer_matrix.json`,
  `source_to_owner_matrix.json`, `support_manifest.json` and fixture generators.
  The 35-contract producer matrix reports 5 auto-matched, 8 manual-emission, 13
  declared-only and 9 unknown rows, which conflicts with treating all 76 support
  manifest entries as operationally supported.

Focused candidate tests produced 924 passed and 3 skipped. A broader static/
template/evidence suite produced 679 passed and 3 failures. Neither run supplies
real crash injection, WAL/outbox durability, restart replay, transaction
migration, external-effect idempotent retry, full production execution, or a
repo-wide legacy-writer negative proof.

## Producer and writer seams

The generated M6 inventory must discover symbols rather than trust this seed,
but the read-only audit found these production families:

- admission and control: `handlers/init.py::handle_init`, `auto.py::run_auto`,
  `auto.py::drive`, `supervisor/driver.py::DefaultRunDriver.drive`;
- common phase lifecycle: `handlers/shared.py::_run_worker` and `_finish_step`,
  plus plan/prep, critique/revise, gate, execute, review, feedback, tiebreaker
  and finalize leaves;
- worker/provider/process: `workers/_impl.py::run_step_with_worker`, provider
  attempt/command paths and `runtime/process.py`;
- fanout/reducers: prep research, parallel critique, `_core/worker_fanout`,
  runtime batch and execute aggregation;
- lifecycle retry/replay/resume: `auto.py::drive`, workflow state and overrides;
- chain/epic/bakeoff/finalize/publication: `supervisor/chain_runner.py`, ladder,
  epic chain, bakeoff, auto publish, Git and PR merge paths;
- managed/resident children and delivery: `managed_agent.py`,
  `resident/subagent.py`, `resident/runtime.py`, agent loop, scheduler and
  ordinary/scheduled Discord delivery;
- cloud/operator adapters and generated wrappers; and
- watchdog, repair loop, meta-repair and progress-auditor paths.

Known hazards include generic and execute-only best-effort receipt helpers,
feedback/tiebreaker bypass, suppressed exceptions, phase-result absence
becoming success in some paths, mutable aliases, and shell `|| true`. The
progress auditor was the only audited production caller of one dispatch receipt
API. M8 must replace every required fail-open writer and prove start plus
exactly-one-terminal at the common execution seams and each leaf.

## Consumer and operational seams

No audited local/cloud/resident/repair/status consumer on the pinned project
baseline uses canonical semantic-health queries end-to-end. M9 must inventory
and migrate:

- local status, progress, introspect, trace and doctor;
- cloud status snapshots/formatters/current-target and resident cloud status;
- watchdog, repair, meta-repair, progress auditor and incident reasoning;
- chain advancement, finalization, PR/publication and final delivery;
- scheduler, managed-agent completion, cancellation/resume/recovery;
- resident ordinary/scheduled outboxes and parent-owned child aggregation;
- projections/export and historical adapters;
- retention, legal hold, privacy, encryption, deletion and compaction; and
- storage/schema migration, failure injection, replay and runtime tracing.

Current hazards include token/prose classification, best-effort evidence writes
that preserve routing, raw/mutable fallback, disableable redaction, mtime-based
cleanup, no WBC SQL/data migration, and no implemented payload-reference store.
Consumers require typed exact-version queries and must return explicit unknown/
indeterminate on gaps, migration uncertainty or persistence failure.

## Planning disposition

- M6 binds the audited merge and current landed/runtime vector and generates exact set
  equality across contracts, call sites, consumers, wrappers and traces.
- M6A implements the WBC-owned transactional store/query/data-policy/migration
  substrate without moving ownership to Custody.
- M7 implements the separate Custody lease/epoch writer contract and references
  WBC events rather than duplicating them.
- M8 migrates every producer, including all phase and operational families.
- M9 migrates every consumer plus retention/privacy/migration operations.
- M10 proves failure injection, replay, effect ambiguity and recovery.
- M11 runs mixed-version/cross-contract acceptance and negative bypass proof.

The maintained row-level acceptance contract is
`research/wbc-boundary-adoption-matrix.md`.
