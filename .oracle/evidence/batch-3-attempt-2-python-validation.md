# Batch 3 attempt 2 — Python validation evidence

Validation snapshot: 2026-08-31T16:21:20Z  
Candidate HEAD: `7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e`  
Tasklist SHA-256: `70a9185d40cf7502a25cbaedd46db3d3bb16ea1f139bc8a8f6b7082c070dbc73`

## Results

| Lane | Exact command / scope | Result |
|---|---|---|
| Watchdog wrappers | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q --cache-clear --basetemp <unique /private/tmp> tests/cloud/test_watchdog_wrappers.py` | 266 collected; 266 passed |
| Managed agent | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q --cache-clear --basetemp <unique /private/tmp> tests/test_managed_agent.py` | 26 passed |
| Authority/ledger/operator/custody | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q --cache-clear --basetemp <unique /private/tmp> tests/arnold_pipelines/megaplan/test_custody_lease_store.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/cloud/test_operator_control.py` | 129 passed |
| Inventory/no-bare | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/cloud/test_repository_signal_inventory.py tests/arnold_pipelines/megaplan/test_python_signal_inventory.py tests/test_no_bare_subprocess.py --disable-warnings --cache-clear` | 14 passed |

Executed total: **435 tests; 435 passed**.

The initial watchdog shard had one stale fixture failure in
`test_watchdog_manual_review_plan_state_reports_needs_human_not_complete`.
Two independent fresh runs reproduced the same failure in distinct basetemps:
`/private/tmp/nbf-b3-watchdog-one.mMyKUh` and
`/private/tmp/nbf-b3-watchdog-two.nG0lio`. Both failed only at
`tests/cloud/test_watchdog_wrappers.py:3810`; the fixture's own
`notify_needs_human()` wrote `needs-human webhook unset` at fixture line 3793,
while the assertion required that string to be absent. The report and all
needs-human/no-complete/no-repair/no-relaunch safety assertions passed.

The narrow test-only repair changed that fixture log marker to
`needs-human notification fixture`, leaving the safety assertions and
production watchdog unchanged. The repaired node passed once in a fresh
basetemp, and the complete watchdog shard then passed **266/266** in
410.75s. The runbook's historical baseline note is superseded for this exact
fixture contradiction; no production regression was present.

## Inventory and static checks

- Generator `python3 scripts/generate_nbf_signal_inventory.py --check`: passed.
- `py_compile scripts/generate_nbf_signal_inventory.py`: passed.
- `git diff --check`: passed.
- Inventory SHA-256: `1d9d9ad599ec4508c728776999e882ea809f5b60d753d1c80b435a2e0b9872be`.
- Inventory entries: `123`.
- Inventory `source_inputs_sha256`: `cf65ded241e0f06543ed9f6a1c616f15619ebe86ede5ea5a051e7334710e2e75`.
- Four ensure-service `arnold_supervisor_signal_bound_pid` rows are
  `non-worker-lifecycle`, `worker_kill=false`, `two_scan_required=true`, and
  `canonical-non-worker-two-scan`.

## Evidence boundary

The contaminated historical run reporting `174 pass / 9 fail / 187 setup
errors` is explicitly excluded from this acceptance evidence. Its setup and
environment failures are not merged, averaged, or double-counted here.

No Oracle tasklist, NBF08 artifact, or source implementation file was changed
by this validation lane. One stale watchdog test fixture was narrowly migrated
as described above; the inventory artifact was regenerated as authorized, and
the focused Python baseline expectation was narrowly migrated separately to
remove one vanished `fan_kill` key.
