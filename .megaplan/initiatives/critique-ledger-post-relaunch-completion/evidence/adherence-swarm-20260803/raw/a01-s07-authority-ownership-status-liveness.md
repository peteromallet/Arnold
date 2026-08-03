# a01-s07-authority-ownership-status-liveness: authority-ownership × status-liveness

## Verdict

**FAIL.** A canonical identity-bound liveness reducer exists, but callers bypass it.

Observed P0 authority-mutation gaps:

- Watchdog repair/relaunch decisions use independent tmux/PID/process reducers.
- Watchdog retirement deletes canonical markers and tracking state directly.

Observed P1 status-misreporting gaps:

- Cloud status snapshots classify `running`/`complete` from raw probes and watchdog reports.
- Provider status uses unbound remote tmux/`ps`.
- Lease observation accepts a valid lease when its runner fence is missing or malformed.
- Watchdog observers append liveness evidence and use an unlocked JSONL writer.

## Intended canonical contract

The M9 contract requires exact-version projections over Run Authority, WBC, lifecycle, and Custody; uncertainty must never become running, complete, repairable, or dispatchable (`.megaplan/initiatives/custody-control-plane/briefs/m9-rebuildable-projections-and-liveness.md:13-18`). Positive control paths must reread live Run Authority grant/fence, Custody lease/epoch, and WBC evidence; projections cannot authorize (`.../m9-rebuildable-projections-and-liveness.md:45-48`).

The canonical implementation is `observe_current_target_liveness()`: only namespace-and-process-start-bound local identity or a marker-bound runner lease can establish liveness; all other evidence is `unknown` (`arnold_pipelines/megaplan/cloud/current_target_liveness.py:1-8,146-272`). Its tests cover foreign namespaces, PID reuse, bound absence, active-step identity, and cross-container leases (`tests/cloud/test_current_target_liveness.py:37-162`).

## Evidence and complete path inventory

I searched with `rg --files` and `rg -n` across `arnold_pipelines`, `tests`, `docs`, `scripts`, `.megaplan`, and `evidence` for `liveness`, `watchdog`, `status`, `lease`, `probe`, `retir`, `whats-cooking`, `load_cloud_status_snapshot`, `session_health_status`, `dispatch`, and the canonical liveness symbols. I then inspected definitions and call sites with numbered source output.

Writers and reducers:

- Runner leases: `cloud/liveness_lease.py:157-201,204-307`.
- Canonical target observation: `cloud/current_target.py:149-203`.
- Cloud snapshot builder/writer: `cloud/status_snapshot.py:390-604`.
- Watchdog report items/report: `cloud/wrappers/arnold-watchdog:389-444,1655-1745`.
- Partial-liveness sidecar: `cloud/wrappers/arnold-watchdog:4529-4590`.
- Independent wrapper reducers: `arnold-watchdog:498-980,2348-2600`.
- Parallel watchdog reducer: `watchdog/correlate.py:161-286`, consumed by `watchdog/snapshot.py:416-475`.

Readers and consumers:

- Snapshot loader accepts JSON plus optional age only: `cloud/status_snapshot.py:607-638`.
- Resident broad status reads it directly: `resident/profile.py:1713-1742`.
- `/whats-cooking` collects and renders that status path: `resident/discord.py:1580-1628`.
- Resident CLI reads the same projection: `resident/cli.py:830-865`.
- Cloud CLI reads it in-container: `cloud/cli.py:6787-6795`.
- Provider status performs raw remote tmux/`ps` checks: `cloud/cli.py:7347-7385`.
- Watchdog repair paths call `session_health_status`, `dispatch_kimi_repair`, and `repair_unintended_stop`: `cloud/wrappers/arnold-watchdog:8394-8504,8695-8708`.
- Canonical retirement implementations are `cloud/status_retirement.py:82-205` and `cloud/session_retirement.py:56-80,120-205`.

## Adherence gaps

1. **P0 — authority mutation: watchdog liveness bypass.**  
   `launch_chain_tick` obtains a canonical target observation, but independently calls `session_health_status` (`arnold-watchdog:8283-8299,8394-8395,8482-8504`). That reducer treats tmux existence, command-line matches, and bare `os.kill(pid, 0)` as `alive` (`arnold-watchdog:2348-2468,2472-2515,2518-2600`). Its stale-active-step result directly calls `repair_unintended_stop` (`arnold-watchdog:8695-8708`). This is an observed mutation-capable bypass, not merely display drift.

2. **P0 — authority mutation: watchdog owns retirement outside canonical retirement.**  
   After repeated workspace/spec absence, the wrapper persists `ENVIRONMENT_GONE` and deletes the canonical session marker, needs-human marker, chain-health artifacts, and progress file (`arnold-watchdog:4613-4637,4640-4688,8466-8474`). The canonical status-retirement contract instead requires an exact marker hash, runtime proof, a durable tombstone, preserved marker artifacts, and postcondition validation (`cloud/status_retirement.py:1-7,117-204`). The wrapper bypass is therefore both an ownership violation and an irreversible retirement mutation.

3. **P1 — status misreporting: snapshot reducer ignores canonical liveness.**  
   The snapshot stores `current_target_liveness` but computes its reducer input through `_safe_liveness()` and `_augment_liveness_with_plan_state()` (`cloud/status_snapshot.py:1449-1462,2991-3002`). `_safe_liveness()` returns positive local tmux/process evidence before checking the lease (`cloud/status_snapshot.py:3024-3053`), while `default_liveness_probe()` scans unbound tmux and command lines (`cloud/status_snapshot.py:3056-3130`). `_classify_session()` then reports `complete` from a watchdog item or `running` from those booleans (`cloud/status_snapshot.py:2359-2384`). The module explicitly admits legacy readers accept the file without cursor validation (`cloud/status_snapshot.py:29-44`), and tests demonstrate direct tampering is accepted (`tests/cloud/test_status_snapshot_projection.py:73-95`).

4. **P1 — provider status bypass.**  
   `cloud status` remotely declares `tmux_alive` or `process_alive` from provider SSH output without namespace, process-start, lease, or marker identity binding (`cloud/cli.py:7347-7385`). This is status misreporting; no direct mutation call is observed in this path, but it violates the same canonical-reader boundary.

5. **P1 — malformed/missing fence can report lease live.**  
   `_read_json()` maps malformed or missing fence files to `{}` (`cloud/liveness_lease.py:93-99`). `observe_liveness_lease()` validates the fence only under `if fence:` and otherwise can return `live` for an otherwise valid lease (`cloud/liveness_lease.py:341-380`). This can suppress repair/escalation based on stale lease evidence.

6. **P1 — observer-side evidence mutation and concurrency gap.**  
   `write_partial_liveness_tick()` appends observer-generated `partial_liveness` events and rewrites a shared fixed `.tmp` path without locking (`cloud/wrappers/arnold-watchdog:4529-4590`). `report_item()` appends JSONL without locking (`arnold-watchdog:389-444`), while `emit_report()` assumes every line parses (`arnold-watchdog:1673-1679`). M9 explicitly requires observers not append activity or refresh liveness (`m9-rebuildable-projections-and-liveness.md:70-75`).

7. **P2 — duplicate public reducers.**  
   `progress_auditor_liveness.classify_runner_liveness()` still has a legacy fallback that can return `alive` from raw tmux/PID/watchdog fields when no bound observation is supplied (`cloud/progress_auditor_liveness.py:24-110`). The escalation caller passes the bound observation (`cloud/progress_auditor_escalation.py:491-499`), so this is currently a reachable API bypass more than a demonstrated production mutation. The separate `watchdog/correlate.py` reducer is another parallel implementation, although its documented outputs remain evidence-only (`watchdog/correlate.py:172-191`).

## Incident reachability and severity

The JSONDecode incident is only one consequence. A torn watchdog item can cause report publication to fail because parsing is unguarded (`arnold-watchdog:1673-1748`), but the broader issue is that report, snapshot, tmux, PID, and provider paths independently decide liveness.

The P0 findings are directly reachable from the watchdog loop: raw health reaches repair dispatch, and env-gone heuristics reach deletion. The P1 findings are observed status inconsistencies and latent authority hazards; direct projection-to-mutation from resident/CLI was not found in this audit.

## Minimal generalized remediation

Consolidate all positive liveness decisions on `observe_current_target_liveness()` and `liveness_from_current_target()`. Keep tmux, raw PID, process lists, activity, and watchdog reports as diagnostic fields only. Change the wrapper’s repair gates to require canonical `state` plus a fresh Run Authority/Custody/WBC reread.

Replace env-gone deletion with `retire_deleted_workspace_status()` for status-only retirement, or the stricter `retire_session()` path when true session retirement is intended. Delete `clear_session_tracking_artifacts()`’s direct marker deletion; do not wrap it.

Make missing/invalid lease fences explicitly `degraded`/`unknown`. Give report-item and sidecar writers one locked owner, or remove observer writes entirely.

Delete the legacy reducer branches and raw probe helpers after call-site migration. Prove unreachability with static tests that fail on direct calls/imports to the removed symbols; a wrapper around the old implementation is insufficient.

## Required tests and retirement proof

Add deterministic integration tests for:

- Concurrent lease publishers and watchdog writers; no lost updates, torn JSON, or duplicate fence generations.
- Restart: old lease fenced after restart; expired/missing/malformed lease yields `unknown`.
- Provider SSH tmux/`ps` output, provider unavailable, and provider restart never establishes canonical liveness.
- Mutation traps: forged/stale snapshot, watchdog report, activity sidecar, or raw PID must not dispatch, relaunch, retry, or retire.
- Same PID with changed start identity, foreign PID namespace, two-container PID collision, and valid cross-container runner lease.
- Concurrent retirement against marker replacement; exact hash mismatch must block and preserve the marker.

Retirement proof must include repository-wide searches showing no non-retirement caller deletes canonical markers, no wrapper calls the removed reducer, and only the canonical retirement modules write retirement tombstones. Rebuild/delete projection parity must preserve source evidence and produce identical cursor/digest results.

## Unknowns

I did not launch services or inspect live cloud state, so production concurrency frequency and provider deployment topology are unverified. I found no current direct resident/CLI mutation call from `load_cloud_status_snapshot`; the projection authority risk there is therefore partly inferred from its unchecked loader and reducer behavior.