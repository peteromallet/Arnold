# Census receipts (G1) — content-addressed evidence log

Every receipt records: UTC timestamp, actor/model, exact command, exit code, SHA-256 of input/output. Box: `159.69.51.216`, container `megaplan-cloud-agent-resident-only`. Local: `/Users/peteromalley/Documents/Arnold`. All commands read-only.

## Artifact digests (final, 2026-08-11 ~15:30 UTC)

| Artifact | SHA-256 |
|---|---|
| docs/fixer-recovery-evidence/census-S1-S4.md | 81aa05b91d5ad1421d9825cf773ed6ed34b3f648e984c203750bc227e6d0121a |
| docs/fixer-recovery-evidence/census-S5-S8.md | 679384f040408470bcbf777128bc0537ace83f3652fc1c47d5283ad288c85d85 |
| docs/fixer-recovery-evidence/census-S9-S12.md | 85d83a4c7f5813ae55c46377f291219cbbacb965a50b8c57b92728b374e42855 |
| docs/fixer-recovery-evidence/baseline-tests.md | d198c37c00873786c2a6d8ac0321c7b045cbcbdb3a2a1dd22bdcff09445881e8 |
| docs/fixer-recovery-evidence/raw-outputs.md | 46957f356b524e3a058239d8278ea7aa73b19a8e9f9fc6e827003642b08f0292 |
| docs/fixer-recovery-evidence/receipts.md | (external digest file: raw-outputs.md header / digests.txt) |

## Local pytest runs (actor: main thread, model deepseek-v4-flash)

| # | UTC (approx) | Exact command (cwd=/Users/peteromalley/Documents/Arnold) | Exit | Result |
|---|---|---|---|---|
| L1 | 2026-08-11 14:26 | `./.venv/bin/python -m pytest -q tests/cloud/test_watchdog_wrappers.py` | 1 | 16 failed, 414 passed |
| L2 | 2026-08-11 14:40 | `./.venv/bin/python -m pytest -q tests/cloud/test_cloud_chain_command.py` | 0 | 82 passed |
| L3 | 2026-08-11 14:41 | `./.venv/bin/python -m pytest -q tests/cloud/test_editable_install_sync.py` | 0 | 3 passed |
| L4 | 2026-08-11 14:42 | `./.venv/bin/python -m pytest -q tests/arnold_pipelines/megaplan/test_chain_execution_binding.py` | 0 | 43 passed |
| L5 | 2026-08-11 14:44 | `./.venv/bin/python -m pytest -q tests/arnold_pipelines/megaplan/test_epic_chain.py` | 0 | 10 passed |
| L6 | 2026-08-11 14:46 | `./.venv/bin/python -m pytest -q tests/cloud/test_runtime_lifecycle.py` | 0 | 27 passed |
| L7 | 2026-08-11 15:05 | `grep -n 'child_agent_launch_authority_or_reject()\|durable_operator_pause_active()\|operator_pause_active()' arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog` | 0 | 4460, 6007, 2364, 5365, 6057 |
| L8 | 2026-08-11 15:06 | `./.venv/bin/python -m pytest tests/cloud/test_watchdog_wrappers.py -q 2>&1 | grep -E '^FAILED'` | 1 | 16 FAILED lines captured (see baseline-tests.md) |

Failing test list (L1): test_repair_loop_exits_immediately_for_completed_chain; test_watchdog_allows_concurrent_repairs_for_different_sessions; test_watchdog_kimi_dispatch_emits_incident_dispatch_statuses; test_repair_loop_missing_goal_custody_cleans_pidfile_on_term; test_repair_loop_preserves_unbound_pidfile_and_uses_durable_lock; test_repair_loop_reclaims_pidfile_after_kill9_with_child_alive; test_repair_loop_busy_directory_lock_exits_without_mutating_repair_data; test_watchdog_env_gone_clears_artifacts_after_strikes_threshold; test_watchdog_env_gone_below_threshold_does_not_clear; test_repair_loop_env_gone_at_entry_exits_zero_without_iteration; test_repair_loop_missing_spec_retires_stale_marker_as_complete; test_repair_loop_missing_chain_spec_at_entry_retires_stale_marker_as_complete; test_meta_repair_dispatch_enabled_success; test_meta_repair_dispatch_passes_trigger_to_wrapper; test_meta_repair_dispatch_ignores_launch_failure_record; test_meta_repair_dispatch_logs_are_redacted.

## Box read commands (actor: main thread, model deepseek-v4-flash, via `docker exec ... bash -lc`)

| # | UTC (approx) | Command | Exit | Output SHA-256 |
|---|---|---|---|---|
| R1 | 2026-08-11 09:50 | `ls -la /workspace/.megaplan/*.json; for f in ...; python3 -c 'import json,sys; d=json.load(open(f)); print({k:d.get(k) for k in [...]})'` | 0 | c8f29968 (orig S1-S4) |
| R2 | 2026-08-11 09:52 | `for f in /workspace/.megaplan/cloud-sessions/*.json; python3 -c 'session/completed_count/milestone_count/current_plan_name/last_state/updated_at'` | 0 | 21a3c2b2 (S5-S8) |
| R3 | 2026-08-11 10:00 | `for f in /workspace/*/Arnold/.megaplan/plans/.chains/chain-*.json; python3 -c 'engine_root/project_root/target_head/target_base'` | 0 | d207e8be (S9-S12) |
| R4 | 2026-08-11 10:02 | `for d in /workspace/runtime-candidates/*/; git -C $d rev-parse HEAD; symbolic-ref; status` | 0 | candidate matrix |
| R5 | 2026-08-11 10:05 | `git ls-remote origin | grep -E 'fixer/\|reconcile/'` | 0 | 3 fixer refs, 0 reconcile |
| R6 | 2026-08-11 10:10 | `tail -200 /tmp/watchdog.log | grep -A2 -B2 megaplan-maintenance; ls requests/ | wc -l; grep -l megaplan-maintenance requests/*` | 0 | 299 requests; 1 stale |
| R7 | 2026-08-11 12:00 | `cat /workspace/.megaplan/megaplan-maintenance.json` | 0 | full manifest |
| R8 | 2026-08-11 12:05 | `ls occurrence-claims/ | wc -l; ls attempts/ | wc -l; ls -lat attempts | head; ls -lat decisions | head` | 0 | 0 occ-claims; 137 attempts |
| R9 | 2026-08-11 12:10 | `for f in schedules/heads/sched_superfixer_*; python3 -c 'schedule_id/state/revision'` | 0 | all cancelled/exhausted/paused |
| R10 | 2026-08-11 12:15 | `git for-each-ref | grep -c reconcile; ls runtime-candidates/ | wc -l` | 0 | 0 reconcile; 12 candidates |
| R11 | 2026-08-11 15:20 | `for w in arnold-watchdog arnold-repair-loop arnold-repair-trigger arnold-meta-repair-loop arnold-runtime-create; do sha256sum /usr/local/bin/$w; sha256sum <engine>/arnold_pipelines/megaplan/cloud/wrappers/$w; done` | 0 | 4-of-5 MISMATCH (matrix below) |
| R12 | 2026-08-11 15:21 | `grep -n 'SCHEDULE_STORES\|refs/pull\|reference' /workspace/omp-replaces-hermes/Arnold/arnold_pipelines/megaplan/cloud/wrappers/arnold-gc-sweep` | 0 | stores :79-89; pull refs :174-185 |
| R13 | 2026-08-11 15:22 | `cat .../megaplan-maintenance.liveness-lease.json; cat ...liveness-fence.json; git for-each-ref | grep -c pull; ls -la ops/schedules/; stat status/cloud-status.json` | 0 | lease ids; pull=0; 2 ops schedules; snapshot 1,799,215B @12:53:12Z |
| R14 | 2026-08-11T13:20:10Z | `ls active-claims/ | wc -l; ls scheduled_jobs/ | wc -l; ls schedules/heads/ | wc -l; date -u` | 0 | raw in raw-outputs.md: 66 / 73 / 53 @ 13:20:10Z |
| R15 | 2026-08-11T13:19:46Z | claim-lock breakdown (lockfiles/dirs/managedbind/nonlock) | 0 | raw in raw-outputs.md: 66 total = 21 .lock + 45 .managed-run-bind, 0 nonlock, all 0-byte |
| R16 | 2026-08-11T13:20:30Z | `grep -n 'SCHEDULE_STORES\|refs/pull\|_schedule_store_references' arnold-gc-sweep` | 0 | raw in raw-outputs.md: schedule heads NOT covered; missing stores skipped |

## Wrapper SHA-256 matrix (R11)

| Wrapper | /usr/local/bin | engine tree | match |
|---|---|---|---|
| arnold-watchdog | 985c4e945fb6476d16ae78a09ad593aea5472a99016e8c0c7a253ca13f58fda3 | f50bbf31dbd45eae5014f43923c56ff151d6c7c125e20c0871d755f0d487cba0 | NO |
| arnold-repair-loop | 89debf5899b7b8cfe43459ab3f7b49f0378eba1a649979b73e894feebe941afb | ed02b6ffed09cee7f4ebd2742575dadc50b8642c90d85b80f368d03d8d6dfb53 | NO |
| arnold-repair-trigger | c54a2030b071f8070a3996ed65add3f3109322a257bed56108f21689964f5592 | 5906c4bdd691f055fa7ced652eb20a348b5ebd1996a1abdbe1cdaca91b097724 | NO |
| arnold-meta-repair-loop | 0900f59ee472d063afc2d60ee34a8fe184d569fb40f64d7e7111abe5f7edd78d | 87aaec10d54ea64e060a7b31a6d3343732d04743f990aa3f5ae9f011a00ac18c | NO |
| arnold-runtime-create | 6525a01104232f70ae97b9f2fbb6b2c0e93631be8b08760142f79d929efacdb6 | 6525a01104232f70ae97b9f2fbb6b2c0e93631be8b08760142f79d929efacdb6 | YES |

Git SHA: local main @ 53584bb018 (unpushed; origin/main @ 7f6abcbe42). Occurrence IDs: none for the current run (census S6). Watchdog report latest: /workspace/watchdog-reports/20260811T130059Z.json (13:00:59Z).
