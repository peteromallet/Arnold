# a02-s07-identity-version-provenance-status-liveness: identity-version-provenance × status-liveness

## Verdict

Non-conformant. A strong canonical liveness observer exists, but production callers bypass it.

P0 authority-boundary gaps exist in watchdog/repair decisions and supervisor status-driven actions. P1 status misreporting exists in the canonical snapshot, watchdog-report join, resident “what’s-cooking,” CLI fallback, and retirement probes. The repository’s own inventory confirms that persisted status reports have no required sequence and process observations have no stable PID-reuse identity (`arnold_pipelines/megaplan/authority/INVENTORY_READER_AUDIT.md:56-71`).

## Intended canonical contract

`observe_current_target_liveness()` is the canonical implementation: local liveness requires matching PID namespace and process-start identity; cross-container liveness requires a fresh marker-bound lease; otherwise the result is `unknown`, with control, mutation, escalation, and retrigger permission false (`arnold_pipelines/megaplan/cloud/current_target_liveness.py:1-9`, `118-143`, `146-272`).

`resolve_current_target()` correctly obtains that result and exposes it as `current_target_liveness` (`arnold_pipelines/megaplan/cloud/current_target.py:171-183`, `425-496`). `status_projection.py` correctly declares display projections non-authoritative (`arnold_pipelines/megaplan/status_projection.py:1-14`).

The lease implementation also binds process-start identity, namespace, boot identity, runner fence, marker binding, and atomic publication (`arnold_pipelines/megaplan/cloud/liveness_lease.py:71-82`, `204-275`). However, its explicit payload has no `run_id`, `attempt_id`, or status/version cursor; those are not required by `marker_binding()` (`arnold_pipelines/megaplan/cloud/liveness_lease.py:71-82`, `247-269`). That is an incomplete provenance envelope even though the runner fence and process incarnation reduce stale-lease risk.

## Evidence and complete path inventory

Search performed: `rg --files`; repository-wide `rg -n` for `liveness`, `tmux`, `ps`, `os.kill`, `watchdog_report`, `status_snapshot`, `cloud_chain_status_payload`, `session_health_status`, retirement functions, and all callers. I then read definitions, call sites, tests, schemas, wrappers, and the authority inventory directly.

Writers:

- Lease/fence: `cloud/liveness_lease.py:180-201`, `204-275`.
- Watchdog item/report: `cloud/wrappers/arnold-watchdog:389-445`, `1655-1714`.
- Broad snapshot: `cloud/status_snapshot.py:390-435`; watchdog wrapper invokes it without a bound probe (`cloud/wrappers/arnold-watchdog:1813-1838`).
- Retirement tombstones and refreshed projections: `cloud/status_retirement.py:82-205`, `421-428`; `cloud/session_retirement.py:56-317`.

Readers and consumers:

- Broad snapshot classification and watchdog join: `cloud/status_snapshot.py:1405-1462`, `2267-2414`, `2442-2469`.
- Resident/profile refresh: `resident/profile.py:1750-1769`; “what’s-cooking” consumes rows in `resident/currently_running.py:71-164`, `204-276`, `485-513`.
- Compact resident tree: `resident/status_tree.py:27-112`, `295-367`.
- CLI targeted status and supervisor: `cloud/cli.py:7275-7520`; `cloud/supervise.py:416-430`, `690-728`.
- Watchdog and repair-loop control paths: `cloud/wrappers/arnold-watchdog:8283-8318`, `8482-8586`, `8695-8708`; `cloud/wrappers/arnold-repair-loop:1074-1104`, `1297-1361`.

Positive evidence: canonical tests cover foreign namespaces, PID reuse, missing identity, active-step precedence, and remote leases (`tests/cloud/test_current_target_liveness.py:37-161`; `tests/cloud/test_liveness_lease.py:37-109`).

## Adherence gaps

- **P0 — authority mutation/suppression: watchdog raw liveness bypass.** `plan_attention_status_env()` uses bare `os.kill(pid, 0)` for an active-step PID, without namespace, process-start, attempt, or version binding (`cloud/wrappers/arnold-watchdog:922-961`). That value controls stale-active-step repair at `8695-8708`. Separately, `session_health_status()` treats tmux presence and command-line matches as alive, using `ps` string matching without incarnation or provenance (`cloud/wrappers/arnold-watchdog:2348-2468`, `2518-2600`). `launch_chain_tick()` calls this duplicate reducer despite already resolving canonical current-target evidence (`8283-8303`, `8482-8485`). An unrelated/reused process can therefore suppress repair, or trigger relaunch/cleanup decisions.

- **P0 — authority mutation/suppression: repair-loop duplicate.** The repair wrapper independently classifies plan/chain liveness from command-line matches and an active-step resolver fallback (`cloud/wrappers/arnold-repair-loop:1074-1125`, `1297-1361`). Its recovery checks use that result (`5591-5600`, `6303-6320`). This is a second mutation-adjacent bypass, not merely a presentation path.

- **P0 — authority mutation: targeted CLI status feeds supervisor.** `cloud_chain_status_payload()` remotely runs `tmux has-session` or `ps` command matching and emits `runner.status=alive`/`dead` without bound identity (`cloud/cli.py:7347-7403`). Its reducer explicitly converts unknown runner evidence to `running` when the plan says running (`cloud/cli.py:6972-6979`). `cloud_supervise_tick()` consumes this payload and maps `running` to noop or `stale_bookkeeping` to restart (`cloud/supervise.py:424-430`, `690-728`). Provider rereads do not repair the missing run/attempt/incarnation/version fence.

- **P1 — status misreporting: canonical snapshot bypasses its own canonical liveness.** `_build_session_entry()` computes `bound_liveness` but classifies using `_safe_liveness(liveness_probe, marker)` instead (`cloud/status_snapshot.py:1405-1462`). `_safe_liveness()` promotes any injected truthy `tmux`/`process` flag to live (`3024-3053`); `default_liveness_probe()` additionally marks any matching command line alive (`3056-3130`). The generated process-correlation cursor is only `session + boolean tmux/process`, not identity or version (`1288-1332`). The snapshot is marked non-authoritative (`1751-1807`), so this is principally misreporting, but it affects every presentation consumer.

- **P1 — status misreporting: stale watchdog evidence crosses generations.** `report_item()` normally persists only session, action, status, message, workspace, and spec; identity is added only for selected managed-agent launches (`cloud/wrappers/arnold-watchdog:389-445`). `_load_watchdog_report()` joins by session and selects the highest-ranked item without marker hash, run, attempt, incarnation, or report sequence (`cloud/status_snapshot.py:2442-2491`). A prior report for a reused session name can therefore classify a new marker.

- **P1 — status misreporting: resident projection trusts unsafe booleans.** “What’s-cooking” reports rows as running/repairing based on status and timestamp presence (`resident/currently_running.py:116-164`), and `_runner_is_live()` trusts `tmux`/`process` booleans (`269-276`). The compact tree preserves those booleans but not the bound liveness identity (`resident/status_tree.py:295-367`).

- **P1 — authority mutation: retirement uses duplicate raw probes.** Exact marker SHA fencing is good (`status_retirement.py:52-79`; `session_retirement.py:333-350`), but both retirement implementations independently use tmux presence, `/proc/{pid}` existence, cwd, and command-token matching (`status_retirement.py:126-165`, `349-405`; `session_retirement.py:180-198`, `522-572`). False negatives can archive/hide an active target; false positives can block retirement. This is narrower than supervisor control but still mutates durable status/retirement state.

## Incident reachability and severity

Observed path: a stale/recycled or foreign process can satisfy raw tmux/command/PID checks; watchdog or supervisor then treats the target as alive, emits `alive`, suppresses repair, or returns supervisor noop. The same unsafe booleans flow into the snapshot and resident output. These are direct code paths, not hypothetical integrations.

Inference: the Critique-style stale-evidence incident is reachable across provider SSH, trusted-container, resident, watchdog, and two-container PID-namespace deployments. The canonical tests prove the intended result should be `unknown`; the bypasses reintroduce the prohibited result.

## Minimal generalized remediation

Consolidate production control and status observation on `observe_current_target_liveness()` and its schema. Add one strict adapter that accepts only a schema-valid canonical observation; missing, legacy, or boolean-only results become `unknown`.

Extend the shared marker/lease/report envelope with explicit `run_id`, `attempt_id`, incarnation/process-start identity, version/fence, and launch-provenance digest. Reject cross-generation joins before classification. Keep status projections display-only.

Replace watchdog and repair-loop `session_health_status()`, active-step `os.kill`, CLI remote tmux/ps probes, and retirement raw probes with the adapter. Make CLI legacy `_run_cloud_chains()` diagnostic-only and non-actionable (`cloud/cli.py:6823-6853`, `6873-6888`). Do not broadly rewrite reducers: narrow consolidation is sufficient because the canonical observer already exists.

## Required tests and retirement proof

Add deterministic tests for:

- foreign PID namespace, PID reuse, missing start identity, lease expiry, fence advancement, same-marker restart, and missing attempt/version;
- concurrent lease/report writers and stale atomic-writer rejection;
- local, SSH, provider failure, and two-container/PID-namespace parity;
- supervisor/watchdog: unknown cannot noop, suppress repair, restart, or retire; bound dead evidence does;
- stale report/lease from an old run or attempt cannot classify a new session;
- resident compaction preserves provenance and excludes identity-incomplete liveness;
- retirement marker mutation, active process, and exact-marker postconditions.

Retirement proof must include repository-wide AST/`rg` allowlist checks showing no production callers remain for `default_liveness_probe`, `_safe_liveness`, raw `session_health_status`, `chain_process_is_alive`, `plan_process_is_alive`, or bare PID checks in these surfaces. Delete the duplicate implementations and legacy mutation-capable fallback; wrapping them is insufficient.

## Unknowns

No services, providers, cloud state, or generated deployments were touched. It is unknown whether an external wrapper differs from this checked-in `arnold-watchdog`. Runtime markers may contain richer identity fields than these readers consume, but source inspection shows the status/report contracts do not require or validate them.