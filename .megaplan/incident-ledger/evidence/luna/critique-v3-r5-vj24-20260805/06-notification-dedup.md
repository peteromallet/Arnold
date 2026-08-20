# Question L6 — stale/repeated notification custody

1. **Verdict:** The local system permits repeated alerts from repeated or stale observations and lacks canonical occurrence/version-keyed provider custody, but the evidence pack proves no provider receipt or actual repeated delivery.

2. **Classification:** `undetermined`.

**Scope/vantage.** Read-only inspection from `/Users/peteromalley/Documents/Arnold`, observed 2026-08-05 UTC. `.megaplan/incident-ledger/evidence/00-common.md` is absent. The remote source checkout was not available; the pack supplies only launch head `c116f38cc83de11a1a508eff6153205504d1ba5a` and pinned runtime digest `d0fa249a...3e92c7d`. Local and remote code were not assumed identical.

## Artifact inventory

Local paths inspected were present unless marked absent:

- Incident path: `arnold_pipelines/megaplan/incident/{schema.py,ledger.py,projection.py}`
- Bridge/legacy path: `arnold_pipelines/megaplan/cloud/{incident_bridge.py,repair_contract.py,status_snapshot.py}`
- Delivery path: `arnold_pipelines/megaplan/resident/{scheduler.py,discord.py,profile.py}`
- Storage path: `arnold_pipelines/megaplan/store/{base.py,_file/conversations.py,_file/operations.py,_db/conversations.py,_db/operations.py}`
- Guardian path: `agentbox/guardian/{notifications.py,state.py,worker.py,scheduler.py}`, `agentbox/notify.py`
- Tests: `tests/arnold_pipelines/megaplan/test_{incident_bridge,incident_ledger,incident_projection}.py`, `tests/agentbox/test_{guardian_notifications,notify}.py`
- Contracts: `.megaplan/initiatives/custody-control-plane/{NORTHSTAR.md,briefs/m10-safe-retry-recovery-and-effects.md,briefs/m11-conformance-and-legacy-retirement.md}`
- Incident amendment: `.megaplan/initiatives/critique-ledger-post-relaunch-completion/{evidence/incident-specific-control-amendment-20260804.md,UNFINISHED_WORK.md,briefs/m4-production-acceptance.md}`
- Local incident state exists: `.megaplan/incident-ledger/{events.jsonl,incidents.json,problems.json}`.
- Absent: `.megaplan/incident-ledger/evidence/00-common.md`.

Critical local SHA-256/mtime samples:

| Path | SHA-256 | mtime |
|---|---|---|
| `incident_bridge.py` | `c2bc1801...a34a3b` | 2026-07-09 13:22:15Z |
| `resident/scheduler.py` | `6e9a09fd...7eda0c3e` | 2026-07-05 00:35:19Z |
| `resident/discord.py` | `c59b1828...5ebf0` | 2026-07-03 03:53:28Z |
| `incident/schema.py` | `5e45c574...1b5892e` | 2026-07-04 09:10:50Z |
| `incident/projection.py` | `8b3ab012...09599f9` | 2026-07-04 09:10:50Z |
| `guardian/notifications.py` | `c6470a45...45ba765` | 2026-06-25 18:13:00Z |
| `guardian/state.py` | `db30a42c...f6e3a81` | 2026-06-25 18:13:00Z |
| `repair_contract.py` | `bb4a9e8f...f2872f` | 2026-07-10 01:32:56Z |
| `incident-specific-control-amendment-20260804.md` | `853eca8f...80453` | 2026-08-04 19:48:21Z |
| `UNFINISHED_WORK.md` | `8cef89dc...4d587` | 2026-08-04 19:47:59Z |

Remote paths and pack facts:

- `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260803-1357/state.json`: present; `blocked`, cursor `phase=execute`, `retry_strategy=repair_validation_failure`.
- Same plan directory: `execute_v2_raw.txt` present; `execution.json`, `execution_audit.json`, `execute_batch_15_output.json`, `execute_batches/batch_15/tasks_35a34c851b8f.json`, `plan_v1.meta.json`, `plan_v2.meta.json`, `plan_v2.md`, and `verification/validation_VJ19_deferred.json` reported present.
- `/workspace/.../verification/validation_VJ24*.json`: absent.
- `/workspace/.../tests/arnold/critique_ledger/test_replay_v2.py`: absent.
- `/workspace/.megaplan/cloud-sessions/critique-ledger-accountability-v3-r5-20260803.liveness-lease.json`: present, `status=stopped`, PID `610293`, runner fence `11`.
- `/workspace/.megaplan/cloud-sessions/repair-data/`: no r5 request reported.
- `/workspace/r5-watchdog-scope-c3b0be1398/watchdog-report.json`: present, `repair_unavailable`.
- `/workspace/watchdog-report.json`: present but stale/contradictory.
- `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold/.megaplan/cloud-chain-critique-ledger-accountability-v3-r5-20260803.log`: present; records runtime/execution binding drift.
- `/workspace/runtime-candidates/arnold-wbc-full-20260804`: pinned runtime path; content SHA supplied above.

The pack supplies no remote file sizes, mtimes, notification IDs, provider request IDs, message IDs, receipts, occurrence ID, normalized fingerprint, claim ID, WBC GLEK, or immutable run-revision ID.

## Commands and raw excerpts

CWD for all commands: `/Users/peteromalley/Documents/Arnold`.

- Required common-file read: exit `2`; stderr:  
  `sed: .megaplan/incident-ledger/evidence/00-common.md: No such file or directory`
- Evidence-pack reads: exit `0`.
- Bounded local code search for webhook/provider custody terms: exit `0`, no matches:
  ```text
  rg -n -i --glob '*.py' '(webhook|provider_receipt|provider.*receipt|effect.*ledger|notification.*(lease|fence)|message.*receipt)' arnold_pipelines/megaplan/cloud arnold_pipelines/megaplan/incident arnold_pipelines/megaplan/resident agentbox
  ```
- Bounded evidence-pack search for notification/provider receipt identities: exit `1`, empty stdout:
  ```text
  rg -n -i '(notification(_| )?id|message(_| )?id|provider(_| )?(request_)?id|receipt|effect(_| )?(intent|outcome|ledger)|discord)' .megaplan/incident-ledger/evidence/critique-v3-r5-vj24-20260805.md
  ```
- Exact remote failure excerpt:
  ```text
  validation job VJ24 references missing selectors that are not declared task outputs
  ```
- Exact remote deferred record:
  ```text
  status=deferred_task_output
  task_id=T18
  missing_selectors=[tests/arnold/critique_ledger/test_replay_v2.py]
  reason=selector_is_declared_task_output
  ```
- Local scheduler excerpts:
  - `resident/scheduler.py:198-205`: `notify_every_check` invokes notification on every check.
  - `resident/scheduler.py:419`: key is derived from `job.id` and `job.attempt_count`.
  - `resident/scheduler.py:487-511`: terminal notification key is `run.id + classification`, with metadata-based suppression.
- Local bridge excerpts:
  - `cloud/incident_bridge.py:78-80`: event IDs use random UUID fragments.
  - `incident/schema.py:23-52`: required fields include no occurrence, state version, notification key, lease, or fence.
  - `incident/projection.py:292-304`: every event increments `problem["occurrence_count"]`.
  - `incident/projection.py:649-660`: repair-attempt fingerprint covers actor/summary/outcome/decision/actions only.

## UTC timeline

| UTC time | Event |
|---|---|
| 2026-08-03 15:40:52 | r5 watchdog: `alive_sessions=0`, `repair_unavailable`; claimed repair request required. |
| 2026-08-03 17:52:40 | Generic watchdog reported `alive`, but was stale and had repair disabled. |
| 2026-08-04 10:24:44 / 10:24:54 | VJ2 exited `None`, expected `[0]`. |
| 2026-08-04 11:27:18 | Persistent execute attempt blocked after model work. |
| 2026-08-04 15:21:17 | VJ8 exited `1`. |
| 2026-08-04 16:42:29 / 16:44:34 | DeepSeek v4 pro unavailable because `DEEPSEEK_API_KEY` was missing. |
| 2026-08-04 16:59:49 | VJ9 exited `1`. |
| 2026-08-04 20:30:48 | VJ24 rejected the missing task-output selector; T18/T23 were never dispatched. |
| 2026-08-05 | Evidence pack captured; local pack mtime is 09:12:23Z. |

Joinable identities:

- Session: `critique-ledger-accountability-v3-r5-20260803`
- Plan: `cl2-wbc-backed-ledger-20260803-1357`
- Chain state: `chain-a5c760402ea2.json`
- Source: `c116f38cc83de11a1a508eff6153205504d1ba5a`
- Runtime: `/workspace/runtime-candidates/arnold-wbc-full-20260804`, SHA `d0fa249a...3e92c7d`
- Validations: VJ2, VJ8, VJ9, VJ19, VJ24
- Tasks/sense checks: T18, T23, SC18, SC23
- Batch artifact: `batch_15/tasks_35a34c851b8f.json`
- Lease/fence: stopped lease, PID `610293`, runner fence `11`
- Runtime drift labels: `e5de49a5ead7→117b71d9caf9`, `117b71d9caf9→cb6afb801753`, `d0fa249a1310→bf86f59d7417`
- Occurrence/fingerprint/request/claim/attempt/notification/provider identities: not supplied.

## Positive evidence

1. `notify_every_check` deliberately creates a notification opportunity per scheduler attempt.
2. Guardian dedupe is only `operation_id:transition`; it has no occurrence, accepted state version, fingerprint, lease, or fence.
3. Guardian checks dedupe before sending, but marks the notification sent before provider delivery; concurrent callers can both pass the check, and a crash/provider ambiguity can desynchronize local state from provider state.
4. `DiscordOutboundSink` sends directly to Discord and only places returned Discord IDs into in-memory `message.metadata`; no durable provider-effect receipt is persisted.
5. Incident-bridge events use random IDs; M1 validation and projection do not require occurrence/version/provider-effect identity.
6. Existing store idempotency prevents some duplicate local message rows, but it does not prove at-most-once provider delivery.
7. The post-relaunch amendment explicitly requires durable occurrence/version notification dedupe and unchanged-poll suppression, while `UNFINISHED_WORK.md` records this as incomplete and says provider effects remain fail-closed until an accepted owner exists.

## Bounded negative evidence

Search scope was limited to:

- Python under `arnold_pipelines/megaplan/{cloud,incident,resident}` and `agentbox`
- Evidence-pack text for notification/message/provider/receipt/effect identities

Within that scope there is no webhook/provider-receipt/effect-ledger implementation and no r5 notification receipt. This does **not** prove that Discord received zero messages; provider effects were not queried and are explicitly unknown.

## Strongest alternative

The repeated alerts could be intentional scheduled-check notifications (`notify_every_check`) or provider retry behavior, rather than stale-projection replay.

A falsifier would be durable raw records showing all alerts share one occurrence, accepted state version, target, and notification intent key, while provider message IDs differ; that would establish a custody/provider-effect failure rather than intentional per-check messaging.

## Confidence

**Medium.** Local code and contract evidence strongly establish a custody gap, but the remote runtime may differ from the local checkout and the pack contains no provider receipts or actual notification identities.

## Explicit contract classification

**`both`**, against:

- Custody Control Plane `NORTHSTAR.md`
- M10 safe retry/effects brief
- M11 conformance/legacy-retirement brief
- `incident-specific-control-amendment.v1`

Existing local idempotency and no-op incident-event suppression are present but not adopted as canonical occurrence/version/provider-effect custody. The required canonical owner/effect structure is also absent or not accepted: the unfinished ledger explicitly says notification custody, accepted state versions, provider receipts, and production ownership remain incomplete.

## Decision for Sol

- **Immediate recovery:** treat notification delivery as unknown; suppress provider effects from stale projections, preserve the blocked occurrence, obtain one fresh coherent authoritative snapshot, and do not resend an ambiguous effect. Do not use the stopped lease, stale marker, or watchdog projection as notification authority.
- **Durable architecture:** place the fix in the existing Run Authority/Custody/WBC ownership path, not in projection freshness alone and not in a second incident ledger. Add durable notification intent/effect custody keyed by occurrence + accepted state version + target/effect class, fenced by current lease/epoch, with provider receipt or typed `INDETERMINATE` outcome. Projection freshness must fail closed and cannot mint a new notification key.