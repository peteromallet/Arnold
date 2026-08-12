# Baseline test counts + fallback inventory (T-0004)

Collected: 2026-08-11 (UTC). Commands run in /Users/peteromalley/Documents/Arnold with ./.venv/bin/python.

## Test runs (six files, run separately)

| File | Result | Exit |
|---|---|---|
| tests/cloud/test_watchdog_wrappers.py | 16 failed, 414 passed | 1 |
| tests/cloud/test_cloud_chain_command.py | 82 passed | 0 |
| tests/cloud/test_editable_install_sync.py | 3 passed | 0 |
| tests/arnold_pipelines/megaplan/test_chain_execution_binding.py | 43 passed | 0 |
| tests/arnold_pipelines/megaplan/test_epic_chain.py | 10 passed | 0 |
| tests/cloud/test_runtime_lifecycle.py | 27 passed | 0 |

**TOTAL: 16 failed / 579 passed.**

The 16 failures are all in `test_watchdog_wrappers.py`. Local grep confirms the
functions ARE present in the live wrapper — `child_agent_launch_authority_or_reject()`
at arnold-watchdog:4460 (called 2364, 5365), `durable_operator_pause_active()` at 6007
(called 6057); literal `operator_pause_active()` exists NOWHERE (stale/misquoted name).
**The TESTS are stale**, not the wrapper: the extracted-function test scaffold
(test_watchdog_wrappers.py:18148) omits these dependencies when it re-extracts
wrapper functions, so the subprocess run fails with `command not found`. This is a
test-harness defect (scaffold must source the full wrapper or stub the missing
functions), NOT a production regression.

The 16 failures (full list):
- test_repair_loop_exits_immediately_for_completed_chain
- test_watchdog_allows_concurrent_repairs_for_different_sessions
- test_watchdog_kimi_dispatch_emits_incident_dispatch_statuses
- test_repair_loop_missing_goal_custody_cleans_pidfile_on_term
- test_repair_loop_preserves_unbound_pidfile_and_uses_durable_lock
- test_repair_loop_reclaims_pidfile_after_kill9_with_child_alive
- test_repair_loop_busy_directory_lock_exits_without_mutating_repair_data
- test_watchdog_env_gone_clears_artifacts_after_strikes_threshold
- test_watchdog_env_gone_below_threshold_does_not_clear
- test_repair_loop_env_gone_at_entry_exits_zero_without_iteration
- test_repair_loop_missing_spec_retires_stale_marker_as_complete
- test_repair_loop_missing_chain_spec_at_entry_retires_stale_marker_as_complete
- test_meta_repair_dispatch_enabled_success
- test_meta_repair_dispatch_passes_trigger_to_wrapper
- test_meta_repair_dispatch_ignores_launch_failure_record
- test_meta_repair_dispatch_logs_are_redacted

Failure classes observed: (a) missing-function scaffold errors (command not
found for the two gate functions) — PROVEN STALE (functions exist at
watchdog:4460, 6007); (b) meta-repair dispatch tests expecting `RESULT=dispatched`
but harness yields `launch_failed` (canonical launch evidence unavailable in the
sandbox) — per-test investigation required, not yet attributed; (c) lock/pidfile
behavioral mismatches (busy_directory_lock expects 75, gets 78) — per-test
investigation required; (d) env-gone tests expecting report rows the sandbox
doesn't emit — per-test investigation required. ONLY class (a) is proven stale;
classes (b)–(d) remain open per-test investigations tracked in T-0013.

## Fallback inventory (rg hits, tests/cloud + tests/arnold_pipelines/megaplan)

Positive fallback assertions still present (these are the behaviors the recovery
must remove or re-classify):

1. **ENGINE_DIR fallback** — `test_cloud_chain_command.py:215` asserts
   `if [ -z "$ENGINE_DIR" ]; then ENGINE_DIR=/workspace/arnold; fi;`; same at
   `test_editable_install_sync.py:97`. This is THE silent shared-root fallback
   (cli.py:3581). T-0011 removes it; these tests flip.
2. **engine_dir=/workspace/arnold** — many fixtures pass
   `engine_dir="/workspace/arnold"` (test_cloud_chain_command.py:196,229,1000;
   test_owner_lease_publisher_parity.py:92; test_editable_install_sync.py:108;
   test_progress_auditor.py:48 `AUDITOR_SOURCE_ROOT="${AUDITOR_SOURCE_ROOT:-/workspace/arnold}"`).
   The fixed `/workspace/arnold` fallback is blessed in fixtures.
3. **manifestless permit** — `allow_manifestless` sidecar tests are extensive and
   POSITIVE (test_launcher_manifest_conformance.py, test_repair_trigger_wrapper.py,
   test_repair_loop_mode_seam.py, test_repair_claim_cleanup.py,
   test_runtime_lifecycle.py:219-235, test_runtime_manifest.py). The P1 admission
   kernel treats absent-manifest + valid permit as ADMITTED — this is by design
   (expiring deviation), keep, but G1 should confirm none of these bless
   manifestless PRODUCTION chains without a permit.
4. **compatibility_only pointer** — positive tests (test_runtime_lifecycle.py:191,
   254, 277, 305, 423; test_runtime_manifest.py:670-680; test_schedule_runner_pin.py:148)
   assert the compatibility pointer is REFUSED (exit 2 / ManifestError). This is the
   GOOD direction (deny-by-default) — keep.
5. **MEGAPLAN_RUNTIME_SRC / MEGAPLAN_LAUNCH_RUNTIME_SRC** — NEGATIVE assertions
   (assert "MEGAPLAN_RUNTIME_SRC" not in command) dominate in cloud chain +
   editable_install_sync tests: selectors are retired. Remaining positives:
   test_cloud_hot_upload.py:97-109 sets all selector envs to "/workspace/stale" and
   expects them NOT to appear in the uploaded env (good); test_runtime_attestation.py:567
   builds a hot-env with selectors to prove they're stripped; test_runtime_census.py
   reads MEGAPLAN_RUNTIME_SRC from /proc environ (observation, fine).
6. **SYNC_BRANCH / editible-install** — test_cloud_hot_upload.py:98 sets
   CLOUD_WATCHDOG_SYNC_BRANCH=editible-install and expects it stripped; runtime
   lifecycle uses base/editable-install as a base_ref in sandbox fixtures.
7. **pip install -e** — NEGATIVE assertions (assert "pip install -e" not in command)
   in test_cloud_chain_command.py:320,642 and test_editable_install_sync.py:69,87 —
   editable-install machinery is deleted. test_relaunch_resolution.py:16 treats
   `pip install -e /workspace/old` in a relaunch command as a STALE marker (rejected).
8. **compatibility_only** — field preserved through promote/close
   (test_runtime_lifecycle.py:257-306).

## Working-tree state

`git status --short` shows only the evidence docs created by the census
(docs/fixer-recovery-evidence/*) — no task-created source changes.
