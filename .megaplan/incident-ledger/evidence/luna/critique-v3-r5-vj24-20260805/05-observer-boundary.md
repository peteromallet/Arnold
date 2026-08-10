# L5 — observer/cloud-status and credential boundary

## Verdict

The L5 concern is **supported**: recovery proof must use fresh host/provider evidence plus authoritative Run Authority/Custody/WBC state; the deployed observer could not obtain the canonical snapshot and then fell into a nested SSH path that lacked host credentials, while stale marker/watchdog projections contradicted the stopped lease.

**Classification:** `both` — the canonical status contract exists but was bypassed/not adopted in this failure path, and the required authoritative read-coherent status structure joining lease/epoch, fence, runtime, and WBC evidence is absent.

## Scope and artifact inventory

Investigation vantage: local checkout `/Users/peteromalley/Documents/Arnold`; observation `2026-08-05T09:24:06Z`. No remote command was run. Remote facts below come only from the evidence pack; local and remote trees are not assumed identical.

Required `00-common.md`: absent under `/Users/peteromalley`; no local copy was available.

Local inspected paths all existed. Central metadata:

| Local path | mtime | SHA-256 |
|---|---:|---|
| `arnold_pipelines/megaplan/cloud/status_snapshot.py` | `2026-07-09T20:32:17Z` | `3a26435027fb3f24ea5a543986a06fbf73ca412831a887fc09277bb5e159b688` |
| `arnold_pipelines/megaplan/cloud/cli.py` | `2026-08-04T16:48:55Z` | `c383e7d91812e4caf648ea78fcb62f1d52e10512cfbb5420209971fc1a1295e4` |
| `arnold_pipelines/megaplan/cloud/providers/ssh.py` | `2026-08-04T16:39:56Z` | `0a4803a831e04ddb331bfa69d4e3f5f397bb869cc4d1d7e9bd2e4181a3a687a2` |
| `arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog` | `2026-07-09T20:32:17Z` | `d4fec5b1179d5ea0e30277fa0d49fb6f5e67aefd82c74051e12e88068317cd0c` |
| `arnold_pipelines/megaplan/cloud/templates/entrypoint.sh.tmpl` | `2026-07-20T17:48:41Z` | `c4f95fe2739efa4dea0d9ea4c8612cd9bcefd4fbcc6b65684dd32f8b4167126e` |
| `arnold_pipelines/megaplan/resident/profile.py` | `2026-07-09T18:16:18Z` | `bbfb5175a32fc8c566438a8cc05aaba91cbae80f53e723a15e68856c4a188872` |
| `arnold_pipelines/megaplan/cloud/spec.py` | `2026-08-04T16:39:56Z` | `32e4bacd674382dad96612f1d7e3f9bef823ebabb6cada4b2fffa186` |
| `arnold_pipelines/megaplan/cloud/auth.py` | `2026-06-23T13:01:02Z` | `4265fae0d50acbed2d03934819407cc1c828e4945e73c7ef0180a1e69b8bf11b` |
| `arnold_pipelines/megaplan/cloud/redact.py` | `2026-07-02T13:18:20Z` | `befbe8f14e442ac5b7e3b5b025ed0bb4e7aca8acb0419645a7a0d9b098113f9f` |
| `.megaplan/initiatives/custody-control-plane/NORTHSTAR.md` | `2026-07-23T19:02:53Z` | `1c2904bde9f4bea5370c141772a135363c5a0d242b9a9f4eb8462be1905f2d6f` |
| `.megaplan/initiatives/custody-control-plane/briefs/m11-conformance-and-legacy-retirement.md` | `2026-07-28T10:27:15Z` | `98d189f5fa23cbf40bfdce723a50f91c75b2052c2630046c9d7d61211557e5f3` |

Additional inspected local paths: `cloud/providers/base.py`, `cloud/systemd/{ensure-megaplan-watchdog,megaplan-watchdog-ensure.service,megaplan-watchdog-ensure.timer}`, `resident/config.py`, `run_state/resolver.py`, `observability/liveness.py`, `docs/cloud.md`, `docs/configuration.md`, `docs/ops/elegant-cloud-status-resident-plan.md`, `docs/arnold/watchdog-snapshot-staleness-fix.md`, `docs/arnold/security.md`, three cloud status tests, and the M5 evidence/completion/proof manifests.

Remote paths and facts from the evidence pack:

- `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold`
- `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold/.megaplan/initiatives/critique-ledger/chain.yaml`
- `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260803-1357`
- `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold/.megaplan/plans/.chains/chain-a5c760402ea2.json`
- `/workspace/runtime-candidates/arnold-wbc-full-20260804`, content SHA `d0fa249a1310cd42920d345e6f664807318bd6fffbe699f1e0f3208563e92c7d`
- `<plan-dir>/state.json`: `blocked`, active step `null`
- `<plan-dir>/execute_v2_raw.txt`: exact content `validation job VJ24 references missing selectors that are not declared task outputs`
- `<plan-dir>/verification/validation_VJ24*.json`: absent
- `<plan-dir>/verification/validation_VJ19_deferred.json`: present; deferred, not pass
- `<plan-dir>/execute_batch_15_output.json`: present but empty output/commands/result envelopes
- `/workspace/.megaplan/cloud-sessions/critique-ledger-accountability-v3-r5-20260803.liveness-lease.json`: `status=stopped`, PID `610293`, runner fence `11`
- `/workspace/.megaplan/cloud-sessions/repair-data/`: no r5 request
- `/workspace/r5-watchdog-scope-c3b0be1398/watchdog-report.json`: `2026-08-03T15:40:52Z`, `alive_sessions=0`, `status=repair_unavailable`
- `/workspace/watchdog-report.json`: `2026-08-03T17:52:40Z`, stale, reports `alive`
- `.megaplan/cloud-chain-critique-ledger-accountability-v3-r5-20260803.log`: runtime-binding refusals

Remote SHA/mtime values were not supplied by the evidence pack except for the pinned runtime content SHA and embedded report timestamps.

## Code trace and raw excerpts

Producer/persistence:

- [`arnold-watchdog`:1557](/Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog:1557) calls `status_snapshot.build_and_write_snapshot(...)` and writes `/workspace/.megaplan/status/cloud-status.json`.
- The watchdog writes a heartbeat and early snapshot before repair/sync work ([lines 7187–7193]( /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog:7187)).
- The mutable report is written by `emit_report()` with `timestamp_utc`, `alive_sessions`, and issue counts ([lines 1462–1488]( /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog:1462)).

Consumer/transport:

- [`status_snapshot.py`:1](/Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/cloud/status_snapshot.py:1) explicitly says “local observation only, never SSH.”
- Trusted in-container CLI reads/builds locally ([`cli.py`:5030–5049](/Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/cloud/cli.py:5030)).
- If the snapshot is unavailable outside that path, CLI falls back to legacy remote listing ([`cli.py`:5051–5060](/Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/cloud/cli.py:5051)).
- [`SshProvider`](/Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/cloud/providers/ssh.py:44) passes `identity_file` to SSH; `status_payload()` executes status inside Docker ([lines 202–209]( /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/cloud/providers/ssh.py:202)).

Liveness/authority:

- The local observer probes only current-namespace tmux/process/PID evidence ([`status_snapshot.py`:1417–1477](/Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/cloud/status_snapshot.py:1417)).
- It does not read the remote `*.liveness-lease.json`; bounded search for the literal `liveness-lease` outside incident evidence returned no matches.
- Its code comments call the watchdog report “the authority on runner truth” ([`status_snapshot.py`:1032–1039](/Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/cloud/status_snapshot.py:1032)), which conflicts with the Custody NORTHSTAR rule that markers, process facts, logs, provider facts, and status snapshots are projections only.

Credential boundary:

- The cloud entrypoint sets `MEGAPLAN_TRUSTED_CONTAINER=1` but does not provision an SSH host key ([`entrypoint.sh.tmpl`:29](/Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/cloud/templates/entrypoint.sh.tmpl:29)).
- The SSH provider is an operator/host-side transport. A workload-side fallback to it therefore creates the observed nested-SSH public-key failure.
- Separately, the current deployment can place configured API keys in the workload environment and persist GitHub credentials in `/root/.git-credentials` ([`entrypoint.sh.tmpl`:38–45](/Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/cloud/templates/entrypoint.sh.tmpl:38)); this is distinct from the missing host SSH identity.

## UTC timeline

| UTC time | Event |
|---|---|
| 2026-08-03 15:40:52 | r5 watchdog report: `alive_sessions=0`, `issue_count=1`, `repair_unavailable`; requires claimed repair request before relaunch. |
| 2026-08-03 17:52:40 | Generic watchdog report says `alive`; evidence identifies it as stale and contradictory. |
| 2026-08-04 10:24:44 / 10:24:54 | VJ2 exited `None`, expected `[0]`. |
| 2026-08-04 11:27:18 | Persistent execute attempt blocked after model work; GLM 5.2 used for batches 2–5. |
| 2026-08-04 15:21:17 | VJ8 exited `1`. |
| 2026-08-04 16:42:29 / 16:44:34 | DeepSeek v4 pro unavailable because `DEEPSEEK_API_KEY` was missing. |
| 2026-08-04 16:59:49 | VJ9 exited `1`. |
| 2026-08-04 20:30:48 | VJ24 deterministic execute stop. |
| 2026-08-05 09:12:23 | Local evidence pack mtime; pack states it was captured on 2026-08-05. |
| 2026-08-05 09:17:55 | Local Sol stage-1 evidence mtime. |
| 2026-08-05 09:24:06 | This read-only investigation observation. |

## Joinable identities

- Session: `critique-ledger-accountability-v3-r5-20260803`
- Plan: `cl2-wbc-backed-ledger-20260803-1357`
- Chain state identity: `chain-a5c760402ea2.json`
- Run/revision: no explicit immutable run ID or revision supplied
- Source: launch head `c116f38cc83de11a1a508eff6153205504d1ba5a`
- Runtime: `/workspace/runtime-candidates/arnold-wbc-full-20260804`; SHA `d0fa249a...`
- Binding refusals: `e5de49a5ead7→117b71d9caf9`, `117b71d9caf9→cb6afb801753`, `d0fa249a1310→bf86f59d7417`; error `editable_runtime_import_root_mismatch`
- Occurrence/fingerprint: no durable occurrence ID or fingerprint ID; semantic fingerprint is the exact VJ24 error string above
- Attempt: no WBC/repair attempt ID supplied; history length `32`
- Tasks: `T18`, `T23`; sense checks `SC18`, `SC23`
- Validation: `VJ19` deferred; `VJ24` rejected
- Request/claim/dispatch: no r5 repair request, claim, or durable dispatch ID
- Lease: exact lease path above; `stopped`; target PID `610293`
- Fence: runner fence `11`; no coordinator fence or Custody epoch supplied
- Notifications: no notification/message/idempotency IDs supplied

## Evidence assessment

Positive evidence:

- Fresh authoritative snapshot is the documented intended path.
- Source tests explicitly require in-container status to avoid SSH.
- The remote lease is stopped and no chain/tmux process remains.
- The r5 watchdog report correctly indicates repair unavailable, while the generic report is stale.
- The canonical snapshot code can detect missing process/tmux evidence when it successfully runs in the same container.

Bounded negative evidence:

- Local search scope: `arnold_pipelines`, `tests`, `docs`, `.megaplan/initiatives`; no local implementation reference to `liveness-lease`.
- No remote filesystem, process, SSH, or provider command was executed.
- No remote source checkout, deployed wrapper hash, snapshot contents, lease epoch, Run Authority decision, Custody claim, WBC attempt, or notification ledger was available beyond the evidence pack.
- Therefore the exact reason snapshot creation failed—missing path, stale deployment, write error, or runtime mismatch—remains unproven.

Strongest alternative explanation: the watchdog was dead/hung or snapshot writing failed, so the canonical snapshot was simply unavailable. A fresh `/workspace/.megaplan/status/cloud-status.json` generated after the lease stopped, joined to the stopped lease and current plan state, would falsify the transport-boundary explanation.

## Confidence

**Medium.** The local producer/consumer/SSH boundary is directly evidenced, and the remote contradictions are explicit; confidence is limited because the remote runtime and the missing `00-common.md` were unavailable.

## Recovery decision for Sol

Immediate recovery should establish an authoritative before-state from Run Authority/Custody/WBC and obtain status through a host-side/provider transport or a fresh local container snapshot. Do not use stale watchdog/marker projections, nested SSH from the workload, or infer liveness from PID/tmux/heartbeat alone.

Durably, adopt the snapshot only as a rebuildable observer projection; keep SSH credentials host-side, expose only a narrow redacted host/provider read path, and add a coherent authoritative status read joining current lease/epoch, coordinator fence, runtime/source identity, and WBC evidence. Baseline contract: [Custody Control Plane NORTHSTAR](/Users/peteromalley/Documents/Arnold/.megaplan/initiatives/custody-control-plane/NORTHSTAR.md:11), with the [M11 conformance brief](/Users/peteromalley/Documents/Arnold/.megaplan/initiatives/custody-control-plane/briefs/m11-conformance-and-legacy-retirement.md:9) as the adoption gate.