# L8 — Causal occurrence timeline

**Verdict:** The earliest trustworthy recovery checkpoint is the durable VJ24 block at `2026-08-04T20:30:48Z`; the evidence supports the causal ordering, but does not contain a canonical occurrence ID sufficient to join the blocker to Run Authority/Custody/WBC records.

**Classification:** `undetermined`

## Scope and artifact status

Observation command ran at `2026-08-05T09:21:10Z`, cwd `/Users/peteromalley/Documents/Arnold`. Remote source was not available; the evidence pack states that canonical cloud status failed and “the observer could not establish a fresh canonical snapshot from the box.”

Local files inspected:

| Local path | Status | Size / mtime | SHA-256 |
|---|---:|---:|---|
| `.megaplan/incident-ledger/evidence/critique-v3-r5-vj24-20260805.md` | present | 9722 / `2026-08-05T11:12:23+0200` | `5553df7bc6d6782014fdbcfd3788ca5d9b2a7f31382ab0a77e1c3370bdf21b4a` |
| `.megaplan/incident-ledger/evidence/critique-v3-r5-vj24-20260805-sol-stage1.md` | present | 8483 / `2026-08-05T11:17:55+0200` | `b0c0c358f853726848e477b8ae4ea19a34ef0142fbf57610b11f39408384fa6a` |
| `.megaplan/incident-ledger/evidence/00-common.md` | absent | — | — |
| `.megaplan/incident-ledger/events.jsonl` | present; no target-session matches | 257091 / `2026-07-09T15:22:15+0200` | `711ddc407fa42ed74391a22c634ba530dfb51858a009d9d9ad8753289b07cdb1` |
| `.megaplan/incident-ledger/incidents.json` | present; no target-session matches | 367781 / `2026-07-09T15:22:15+0200` | `17ebd05331a564c3c98024ac926d3a6cad35e97a80acffaa5a265ba17a0043f3` |
| `.megaplan/incident-ledger/problems.json` | present; no target-session matches | 6408 / `2026-07-09T15:22:15+0200` | `b5083c2a8579db44f8e19ce3f66031a194fe5ddbfe33127d3a258efb7f17552c` |

Relevant local contract files inspected:

- `.megaplan/initiatives/custody-control-plane/NORTHSTAR.md`
- `.megaplan/initiatives/custody-control-plane/briefs/m11-conformance-and-legacy-retirement.md`
- `.megaplan/initiatives/critique-ledger-post-relaunch-completion/NORTHSTAR.md`
- `.megaplan/initiatives/critique-ledger-post-relaunch-completion/evidence/architecture-fit-and-minimality-gate-20260804.md`

No local copy of the r5 plan, remote validator source, remote chain log, marker, lease, or runtime source was available.

## Joinable identities

- Session: `critique-ledger-accountability-v3-r5-20260803`
- Remote workspace: `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold`
- Chain spec: `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold/.megaplan/initiatives/critique-ledger/chain.yaml`
- Plan: `cl2-wbc-backed-ledger-20260803-1357`
- Chain state: `chain-a5c760402ea2.json`
- Launch source head: `c116f38cc83de11a1a508eff6153205504d1ba5a`
- Pinned runtime: `/workspace/runtime-candidates/arnold-wbc-full-20260804`
- Runtime content SHA: `d0fa249a1310cd42920d345e6f664807318bd6fffbe699f1e0f3208563e92c7d`
- Validation jobs: `VJ2`, `VJ8`, `VJ9`, `VJ19`, `VJ24`
- Tasks/sense checks: `T18`, `T23`, `SC18`, `SC23`
- Batch artifact: `execute_batch_15_output.json`
- Batch scope artifact: `execute_batches/batch_15/tasks_35a34c851b8f.json`
- Selector: `tests/arnold/critique_ledger/test_replay_v2.py`
- Lease path: `/workspace/.megaplan/cloud-sessions/critique-ledger-accountability-v3-r5-20260803.liveness-lease.json`
- Lease state: `status=stopped`, target PID `610293`, runner fence `11`
- Watchdog scope: `/workspace/r5-watchdog-scope-c3b0be1398/watchdog-report.json`
- Binding tokens:
  - expected `e5de49a5ead7`, active `117b71d9caf9`
  - expected `117b71d9caf9`, active `cb6afb801753`
  - expected `d0fa249a1310`, active `bf86f59d7417`

Unavailable: canonical `run_id`, immutable `run_revision`, occurrence ID, normalized blocker fingerprint, attempt ID, Run Authority decision/fence, Custody epoch, WBC attempt/effect ID, repair request/claim/dispatch ID, and notification/message ID.

## UTC timeline

| UTC | Time type | Event and evidence | Assessment |
|---|---|---|---|
| `2026-08-03T15:40:52Z` | watchdog report time | r5 watchdog: `alive_sessions=0`, `issue_count=1`, `status=repair_unavailable`; message: `deterministic phase-contract failure requires a claimed repair request before relaunch` | Useful scoped diagnostic, but no joinable VJ24 occurrence ID. |
| `2026-08-03T17:52:40Z` | watchdog report time | Generic watchdog reports session `alive`, with `codex_repair_enabled=false`, `push_repairs_enabled=false` | Stale and contradicted by the r5 report and later stopped lease. |
| `2026-08-04T10:24:44Z`, `10:24:54Z` | validation event time | VJ2 exited `None`, expected `[0]` | Prior failure; no attempt or occurrence identity supplied. |
| `2026-08-04T11:27:18Z` | execution observation/event time | Long persistent execute attempt blocked after model work; GLM 5.2 used for batches 2–5 | No durable attempt ID or accepted evidence envelope supplied. |
| `2026-08-04T15:21:17Z` | validation event time | VJ8 exited `1` | Prior failure; details and identity unavailable. |
| `2026-08-04T16:42:29Z`, `16:44:34Z` | provider event time | DeepSeek v4 pro could not run because `DEEPSEEK_API_KEY` was missing | Provider failure; no request/attempt ID supplied. |
| `2026-08-04T16:59:49Z` | validation event time | VJ9 exited `1` | Prior failure; details and identity unavailable. |
| immediately before the run; exact time unavailable | binding event order only | Chain log records runtime/execution binding refusals, including `editable_runtime_import_root_mismatch` and the three runtime-token drifts above | Causally relevant, but unjoinable to a specific run revision or VJ artifact. |
| `2026-08-04T19:35:41Z` | marker field time | Primary marker still had `should_run=true`, with no current status/error | Stale projection, not liveness or recovery authority. Filesystem mtime unavailable. |
| `2026-08-04T20:30:48Z` | durable plan-history event time | VJ24 rejected: `validation job VJ24 references missing selectors that are not declared task outputs` | Earliest trustworthy current recovery checkpoint. |
| after VJ24; exact time unavailable | artifact state | `state.json=blocked`, `active_step=null`, cursor `phase=execute`, `retry_strategy=repair_validation_failure`; T18/T23 remained `pending` | Confirms no accepted batch-15 progress. |
| after VJ24; exact time unavailable | lease state | Lease `stopped`, PID `610293`, fence `11`; no chain process or tmux server | Stronger current-state evidence than stale marker/watchdog projections. |
| after VJ24; exact time unavailable | repair state | No r5 repair-data request; r5 dispatch absent/empty | No occurrence-bound recovery handoff was recorded. |
| `2026-08-05` | evidence-pack capture date; local copy mtime only | Evidence pack captured from canonical agentbox; local copies have mtimes `09:12:23Z` and `09:17:55Z` | Local mtimes are copy times, not remote event times. |

## Exact blocker identity

The strongest available surrogate is:

```text
session=critique-ledger-accountability-v3-r5-20260803
plan=cl2-wbc-backed-ledger-20260803-1357
chain_state=chain-a5c760402ea2.json
phase=execute
retry_strategy=repair_validation_failure
validation=VJ24
event_time=2026-08-04T20:30:48Z
blocker_text="validation job VJ24 references missing selectors that are not declared task outputs"
selector=tests/arnold/critique_ledger/test_replay_v2.py
lease_runner_fence=11
```

This is not a canonical occurrence identity. The required occurrence tuple cannot be completed because run revision, normalized fingerprint, authoritative coordinator fence, Custody epoch, attempt, and repair request IDs are absent.

## Positive and bounded negative evidence

Positive evidence:

- VJ24 is the last durable plan-history event and explicitly blocked the run.
- VJ19 was `status=deferred_task_output`, not a passing validation result.
- No `validation_VJ24*.json` artifact exists; the newest verification artifact is VJ19 deferred.
- Batch 15 contains no commands, output, result envelopes, or accepted worker result; T18/T23 remain pending.
- The selector is absent from the remote r5 workspace according to the evidence pack, despite being listed in `plan_v1.meta.json`, `plan_v2.meta.json`, and Step 15 of `plan_v2.md`.
- Lease/current plan state says stopped/blocked, while marker and generic watchdog projections are stale or contradictory.

Bounded negative search:

- Searched all local `.megaplan/incident-ledger/{events.jsonl,incidents.json,problems.json,summaries/**}` for the target session, plan, `VJ24`, and `test_replay_v2.py`; no matching target records.
- Searched the local workspace file index for the named remote plan, execution, validation, lease, watchdog, chain-log, and selector artifacts; no r5 copies were found.
- This does not establish absence from the remote host beyond the explicit evidence-pack statements. No remote source or fresh remote snapshot was available.
- The supplied evidence contains no notification IDs, webhook receipts, idempotency keys, repair claims, or occurrence-bound notification records; the repeated-notification hypothesis remains unproven.

## Alternative explanation

The strongest alternative is a plan/worktree/runtime revision mismatch: VJ19 and VJ24 may have consumed different normalized selector declarations or different source/runtime revisions.

A falsifying observation would be identical normalized selector→task maps, declaration hashes, validator source identity, runtime identity, and semantics for VJ19 and VJ24.

## Contract classification

**`both` — existing contract violated or bypassed, and required canonical structure absent.**

Baseline: `.megaplan/initiatives/custody-control-plane/NORTHSTAR.md`, M11 conformance brief, and `architecture-fit-minimality-gate.v1`.

The existing contract requires immutable run/revision identity, Run Authority fences, Custody occurrence identity and epochs, WBC attempt/effect evidence, fail-closed validation, and one occurrence-bound repair path. The evidence shows stale projections, binding drift, unaccepted task claims, and no durable repair handoff. It also shows that the canonical occurrence/request/attempt lineage needed to prove or recover this blocker is absent from the available evidence.

## Decision for Sol

Immediate recovery should remain stopped at the preserved VJ24 checkpoint. Do not fabricate the selector, resume, or rebind until the authoritative declaration, run revision, occurrence identity, Custody/Run Authority/WBC records, and repair ownership are reconciled.

Durably, the incident requires adoption of the existing Custody Control Plane ownership model and a single joinable causal history; it does not justify introducing a second fixer or notification authority.