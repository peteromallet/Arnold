# L3 evidence report — blocked transition / occurrence-bound repair

1. **Question ID / verdict**

**L3 — supported.** The repair was not lost to an authority-token mismatch: the existing queue/claim/dispatch contract was not reached for the `blocked + execute + repair_validation_failure` shape, and the canonical transition for that shape is absent from the inspected local contract.

2. **Classification**

`SUPPORTED`

Explicit architecture classification: **both** — existing contract present but not adopted, and required canonical structure absent.

Baseline contracts:

- `Canonical Run-State Resolver` North Star.
- `North Star: Custody / Cluster Control Plane with Run Authority and WBC`.
- M7 controlled-writer/repair-occurrence contract.
- M10 safe-retry contract.
- M11 cross-contract conformance/legacy-retirement contract.

3. **Scope and artifact inventory**

`00-common.md` was searched under `/Users/peteromalley/Documents/Arnold` and is absent. No substitute was treated as authoritative.

Local evidence files:

| Path | Existence / local metadata |
|---|---|
| `.megaplan/incident-ledger/evidence/critique-v3-r5-vj24-20260805.md` | present; mtime `2026-08-05T11:12:23+0200`; SHA-256 `5553df7bc6d6782014fdbcfd3788ca5d9b2a7f31382ab0a77e1c3370bdf21b4a` |
| `.megaplan/incident-ledger/evidence/critique-v3-r5-vj24-20260805-sol-stage1.md` | present; mtime `2026-08-05T11:17:55+0200`; SHA-256 `b0c0c358f853726848e477b8ae4ea19a34ef0142fbf57610b11f39408384fa6a` |

Inspected local contracts:

- `arnold_pipelines/megaplan/run_state/{model.py,resolver.py,classifiers.py,evidence.py}`
- `arnold_pipelines/megaplan/cloud/{repair_contract.py,repair_requests.py,repair_lock.py,repair_recurrence.py,feature_flags.py,meta_repair.py,meta_repair_policy.py}`
- `arnold_pipelines/megaplan/cloud/wrappers/{arnold-watchdog,arnold-repair-trigger,arnold-meta-repair-loop,arnold-supervise}`
- `.megaplan/initiatives/canonical-run-state-control-plane/NORTHSTAR.md`
- `.megaplan/initiatives/custody-control-plane/{NORTHSTAR.md,briefs/m7-controlled-authoritative-writers.md,briefs/m10-safe-retry-recovery-and-effects.md,briefs/m11-conformance-and-legacy-retirement.md}`

The local checkout is dirty; the inspected `arnold-watchdog` is modified (`git status` reports `M`). Local and remote code identities are therefore not assumed equivalent.

Remote paths/facts supplied by the evidence pack:

- `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold`
- `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260803-1357/state.json`
- `.../execute_v2_raw.txt`
- `.../execute_batch_15_output.json`
- `.../execute_batches/batch_15/tasks_35a34c851b8f.json`
- `.../verification/validation_VJ19_deferred.json`
- `.../verification/validation_VJ24*.json` — absent
- `/workspace/.megaplan/cloud-sessions/critique-ledger-accountability-v3-r5-20260803.liveness-lease.json`
- `/workspace/.megaplan/cloud-sessions/repair-data/` — no r5 repair-data request
- `/workspace/r5-watchdog-scope-c3b0be1398/watchdog-report.json`
- `/workspace/watchdog-report.json`
- `/workspace/runtime-candidates/arnold-wbc-full-20260804` — pinned runtime; content SHA-256 `d0fa249a1310cd42920d345e6f664807318bd6fffbe699f1e0f3208563e92c7d`

No remote source checkout was available for direct inspection. Remote plan-artifact SHA/mtime values were not supplied.

4. **Read-only commands and excerpts**

Working directory for all commands: `/Users/peteromalley/Documents/Arnold`.

- `find /Users/peteromalley/Documents/Arnold -name '00-common.md' -print` — exit `0`; no output.
- `nl -ba .megaplan/incident-ledger/evidence/...md` — exit `0`.
- `stat ...; shasum -a 256 ...` — exit `0`; produced the metadata above.
- `rg -n 'repair_validation_failure' arnold_pipelines tests docs .megaplan/initiatives/canonical-run-state-control-plane .megaplan/initiatives/custody-control-plane` — no matches in that local source/document scope.
- `rg -n 'RepairOccurrenceKey|repair_occurrence|CustodyLease|coordinator_fence|custody_epoch' arnold_pipelines tests` — no implementation matches; only contract terminology appears in the inspected initiative briefs.
- `git status --short -- arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog ...` — exit `0`; raw relevant output: `M arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog`.

Remote raw excerpts:

> `state.json current state: blocked`  
> `Resume cursor: phase=execute, retry_strategy=repair_validation_failure`  
> `There is no verification/validation_VJ24*.json artifact.`  
> `There is no r5 repair-data request ... No durable fixer dispatch was recorded after VJ24.`  
> `status=repair_unavailable ... deterministic phase-contract failure requires a claimed repair request before relaunch.`

Local raw excerpts:

- `repair_recurrence.py:17-25` defines the signature fields: `failure_kind`, `current_state`, `phase_or_step`, `milestone_or_plan`, `gate_recommendation`, `blocked_task_id`, `event_signature`.
- `repair_requests.py:285-287` accepts only top-level `schema_version`, `kind`, `request_id`, and `problem_signature`.
- `repair_contract.py:179-210` requires blocker fingerprint fields: `current_state`, `retry_strategy`, `failure_kind`, `phase_or_step`, `milestone_or_plan`, `blocked_task_id`, `target_fingerprint`.
- `repair_contract.py:2792-2823` whitelists repairable shapes; `repair_validation_failure` is not included.
- `arnold-watchdog:739` defines `manual_review` only as `current_state == "manual_review"` or `retry_strategy == "manual_review"`.
- `arnold-watchdog:1317-1347` creates a request only inside the manual-review dispatch-status path.
- `arnold-repair-trigger:77-83` returns `empty` when no request exists; it does not synthesize one.
- `arnold-repair-trigger:254-285` claims by `blocker_id` and exports `request_id`, `blocker_id`, and claim-owner PID before dispatch.
- `feature_flags.py:103-129,155-160` defaults request queue and repair trigger on, but resolver enforcement off.
- `meta_repair.py:448-482` recognizes six meta-repair triggers; `repair_validation_failure` is not itself a trigger.

5. **UTC timeline and identities**

| UTC time | Event |
|---|---|
| `2026-08-03T15:40:52Z` | r5 watchdog report: `alive_sessions=0`, one issue, `repair_unavailable`; claimed repair request required. |
| `2026-08-03T17:52:40Z` | Generic watchdog report stale/contradictory: session `alive`, `codex_repair_enabled=false`, `push_repairs_enabled=false`. |
| `2026-08-04T10:24:44Z`, `10:24:54Z` | VJ2 exited `None`. |
| `2026-08-04T11:27:18Z` | Persistent execute attempt blocked after model work. |
| `2026-08-04T15:21:17Z` | VJ8 exited `1`. |
| `2026-08-04T16:42:29Z`, `16:44:34Z` | DeepSeek v4 pro unavailable due missing API key. |
| `2026-08-04T16:59:49Z` | VJ9 exited `1`. |
| `2026-08-04T19:35:41Z` | Primary marker last updated; stale observation surface. |
| `2026-08-04T20:30:48Z` | VJ24 rejected missing task-output selector; plan became/stayed blocked. |
| `2026-08-05` | Evidence captured; exact UTC capture time not supplied. |

Joinable identities:

- Session: `critique-ledger-accountability-v3-r5-20260803`
- Plan: `cl2-wbc-backed-ledger-20260803-1357`
- Chain state: `chain-a5c760402ea2.json`
- Source head: `c116f38cc83de11a1a508eff6153205504d1ba5a`
- Pinned runtime: `/workspace/runtime-candidates/arnold-wbc-full-20260804`
- Runtime content SHA: `d0fa249a1310cd42920d345e6f664807318bd6fffbe699f1e0f3208563e92c7d`
- Runtime drift identities: expected/active prefixes `e5de49a5ead7`, `117b71d9caf9`, `cb6afb801753`, `d0fa249a1310`, `bf86f59d7417`
- Validation jobs: `VJ2`, `VJ8`, `VJ9`, `VJ19`, `VJ24`
- Tasks/sense checks: `T18`, `T23`, `SC18`, `SC23`
- Missing selector: `tests/arnold/critique_ledger/test_replay_v2.py`
- Lease: `/workspace/.megaplan/cloud-sessions/...liveness-lease.json`, `status=stopped`, PID `610293`, runner fence `11`

Not supplied/unjoinable:

- VJ24 occurrence ID
- VJ24 blocker fingerprint/digest
- repair request ID
- claim ID/owner
- WBC attempt ID
- Run Authority grant/coordinator fence
- Custody lease ID/epoch
- notification/message IDs
- authoritative validation receipt hash

6. **Positive and bounded negative evidence**

Positive evidence shows a deterministic VJ24 stop, no accepted batch-15 result, stopped liveness, and no durable repair request or dispatch.

Bounded negative searches covered only local `arnold_pipelines/`, `tests/`, `docs/`, and the canonical/custody initiative documents. They found no `repair_validation_failure` transition or implemented `RepairOccurrenceKey`. Remote negative claims are limited to the exact artifacts and directories named in the evidence pack; this is not a remote filesystem-wide search.

7. **Alternative explanation**

Strongest alternative: the pinned remote runtime differed from the current local checkout and contained a producer or compatibility mapping not present locally, or an environment flag suppressed request creation.

One falsifying observation would be a remote event/manifest showing an accepted request ID for the exact VJ24 fingerprint, followed by a claim and dispatch outcome. The evidence pack instead states that no such request or dispatch exists.

8. **Confidence**

**Medium.** The local contract gap and remote absence of request/dispatch are clear, but the remote source/runtime implementation was not available and the local watchdog is modified.

9. **Exact repair-request evidence**

The current local queue schema requires:

```json
{
  "schema_version": 1,
  "kind": "repair_request",
  "request_id": "<stable hash>",
  "created_at": "<UTC>",
  "source": "<producer>",
  "session": "<session>",
  "workspace": "<workspace>",
  "run_kind": "<run kind>",
  "target": {
    "workspace": "<workspace>",
    "remote_spec": "<chain spec>",
    "plan_name": "<plan>"
  },
  "problem_signature": {
    "failure_kind": "<normalized failure>",
    "current_state": "blocked",
    "phase_or_step": "execute",
    "milestone_or_plan": "<plan>",
    "gate_recommendation": "",
    "blocked_task_id": "<task or empty>",
    "event_signature": "<event signature>"
  },
  "problem_signature_key": "<sha256>",
  "root_cause_hint_hash": "<sha256>",
  "root_cause_hint_hash_algorithm": "sha256(redact_payload(root_cause_hint))"
}
```

For an admissible occurrence-bound repair under M7/M10/M11, it must additionally carry exact:

- environment/session, chain, plan revision, phase/task, subject attempt;
- normalized failure kind and blocker/phase-result digest;
- managed-worker/process-birth identity;
- current Run Authority grant and coordinator fence;
- current Custody lease ID, owner/host identity, and custody epoch;
- WBC contract/version and ledger-attempt/effect evidence;
- source/tree/commit, tests/results, runtime/import identity;
- deterministic idempotency key and causal predecessor.

A claim must bind at minimum `blocker_id`, `request_id`, actor, session, complete normalized blocker fingerprint, PID, command, cwd, start/timeout/host metadata. The local implementation derives `request_id` from session/signature/redacted-hint hash and `blocker_id` from the V1 fingerprint, but does not itself carry the full M7/M10 occurrence, authority, WBC, lease, or fence tuple.

10. **Recovery decision**

For Sol’s immediate recovery: preserve the blocked VJ24 occurrence and stale runtime/lease evidence; do not clear state or relaunch. Recovery must first establish the exact occurrence-bound request, current authority/custody evidence, and a claimed repair attempt.

For durable architecture: add a canonical `repair_validation_failure` transition and wire the same occurrence-bound producer through watchdog, trigger, fixer, and meta-repair. Retire raw-label/manual-review compatibility routing only after M11 exact-version, no-bypass, replay, and delayed-verification evidence passes.