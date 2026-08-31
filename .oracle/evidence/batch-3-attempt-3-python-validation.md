# Batch 3 attempt 3 — Python integration validation

Validation snapshot: 2026-08-31T17:21:07Z; final inventory binding recorded 2026-08-31  
Candidate source snapshot (`HEAD`): `7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e`  
Tasklist SHA-256: `70a9185d40cf7502a25cbaedd46db3d3bb16ea1f139bc8a8f6b7082c070dbc73`

## Integration run

The following clean run used `PYTHONDONTWRITEBYTECODE=1`, pytest
`--cache-clear`, and a unique self-created `--basetemp` under `/private/tmp/`:

```text
python3 -m pytest -q --disable-warnings --cache-clear --basetemp <unique /private/tmp> \
  tests/cloud/test_watchdog_wrappers.py \
  tests/test_managed_agent.py \
  tests/arnold_pipelines/megaplan/test_nbf04_ladder.py \
  tests/cloud/test_controlled_final_launch.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py \
  tests/arnold_pipelines/megaplan/test_signal_authority.py \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_managed_signal_contract.py \
  tests/arnold_pipelines/megaplan/test_subagent_launcher_disposition.py \
  tests/cloud/test_operator_control.py \
  tests/cloud/test_fan_safepath_import.py \
  tests/cloud/test_worker_dispatch_admission.py \
  tests/cloud/test_worker_dispatch_context.py \
  tests/cloud/test_worker_dispatch_spy.py
```

Result: **471 passed, 1 failed** in 536.97s. The sole failure was
`tests/cloud/test_fan_safepath_import.py::test_fan_py_imports_under_pythonsafepath`:
the intentionally stripped environment had no optional `fire` package and
`fan.py` exited with `error: this script requires \`fire\``. This is an
environment/dependency baseline failure, not a candidate signal or custody
regression. The exact self-created basetemp was removed after the run.

## Post-fix race/replay validation

After the wrong-process-handle fence was added to both controlled signal paths,
the focused command was:

```text
python3 -m pytest -q --disable-warnings --cache-clear --basetemp <unique /private/tmp> \
  tests/cloud/test_controlled_final_launch.py \
  tests/arnold_pipelines/megaplan/test_nbf04_ladder.py
```

Result: **42 passed** in 12.33s. This includes TERM/KILL identity mismatch,
wrong-handle-before-poll/signal, crash replay, already-dead replay, and native
timeout teardown cases. The exact self-created basetemp was removed.

## Final lane accounting

The final evidence accounting is:

- Combined Python integration: **471 candidate passes**.
- One explicitly excluded unrelated stripped-environment baseline: the sole
  `test_fan_py_imports_under_pythonsafepath` failure above, caused by optional
  `fire` being unavailable. It is outside the 49-path manifest and is not
  counted as a candidate failure.
- Controlled wrong-handle/race validation: **42 passed**.
- Inventory/static lane: **18 passed/checks**.
- Disposition wrappers lane: **18 passed**.
- Watchdog wrappers: **266 passed**.

The lane counts intentionally overlap where the same focused tests appear in
the combined, controlled, disposition, or watchdog scopes; they are not summed
into a synthetic total.

## Static and identity snapshot

- Write-free `compile()` passed for the six changed Python/test files.
- `git diff --check`: passed.
- Current inventory: `docs/nbf-signal-inventory.json`, 122 entries.
- Final inventory SHA-256:
  `d8052e72a4c6f43d8f164d2de5524a9eae7fd8ee9dfe2ab06fce2042e9fe2e1d`.
- Current `source_inputs_sha256`:
  `5318df4442550596e09b7200b76f2171106a926bee93834790dbe55466849033`.

No Oracle, NBF08, tasklist, shell runtime-lib, operator-control, fan-kill, or
inventory files were edited by this validation lane. The evidence records the
current inventory snapshot because its identity changed in the shared tree
during the lane.
