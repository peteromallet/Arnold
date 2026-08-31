# Batch 3 attempt 3 — static/runtime validation

This evidence is bound to the following shared-tree identities:

- Branch: `reconcile/nbf-attempt4-2297`
- HEAD: `7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e`
- Tasklist SHA-256: `70a9185d40cf7502a25cbaedd46db3d3bb16ea1f139bc8a8f6b7082c070dbc73`
- Inventory: `docs/nbf-signal-inventory.json`
- Inventory SHA-256: `d8052e72a4c6f43d8f164d2de5524a9eae7fd8ee9dfe2ab06fce2042e9fe2e1d`
- Inventory entries: `122`
- Inventory source-input SHA-256: `5318df4442550596e09b7200b76f2171106a926bee93834790dbe55466849033`

## Commands and results

All commands ran from the repository root with a fresh temporary pytest
basetemp where applicable. `PYTHONDONTWRITEBYTECODE=1` was used for pytest.

1. `python3 scripts/generate_nbf_signal_inventory.py`
   Result: PASS; regenerated the deterministic inventory.
2. `python3 scripts/generate_nbf_signal_inventory.py --check`
   Result: PASS; fresh inventory.
3. `python3 scripts/generate_nbf_signal_inventory.py --check`
   Result: PASS; independent second freshness check.
4. `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q --cache-clear --basetemp "$(mktemp -d /private/tmp/nbf-postfix-static3.XXXXXX)" tests/cloud/test_repository_signal_inventory.py tests/arnold_pipelines/megaplan/test_python_signal_inventory.py tests/test_no_bare_subprocess.py tests/cloud/test_watchdog_dispositions.py::test_shell_signal_sites_have_no_raw_delivery_primitives tests/cloud/test_watchdog_dispositions.py::test_shell_consumers_bind_target_context_and_use_bound_signal_door tests/cloud/test_watchdog_dispositions.py::test_tmux_replacement_and_missing_context_are_fail_closed tests/cloud/test_watchdog_dispositions.py::test_tmux_teardown_uses_marker-owned-pane-and-captured-socket`
   Result: PASS: 18 passed. The exact tmux node used was
   `tests/cloud/test_watchdog_dispositions.py::test_tmux_teardown_uses_marker_owned_pane_and_captured_socket`.
5. `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q --cache-clear --basetemp "$(mktemp -d /private/tmp/nbf-postfix-wrappers.XXXXXX)" tests/cloud/test_watchdog_dispositions.py`
   Result: PASS: 18 passed.
6. `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q --cache-clear --basetemp "$(mktemp -d /private/tmp/nbf-postfix-watchdog.XXXXXX)" tests/cloud/test_watchdog_wrappers.py`
   Result: PASS: 266 passed.
7. `find arnold_pipelines/megaplan/cloud/wrappers arnold_pipelines/megaplan/cloud/systemd -type f ... bash -n`
   Result: PASS: 6 modified shell files syntax-checked.
8. In-memory `compile()` over touched Python files from `git status --porcelain`.
   Result: PASS: 37 files compiled; no bytecode was written.
9. `git diff --check`
   Result: PASS.

The full watchdog-wrapper run overlaps the focused disposition-wrapper tests;
it was retained as the complete shell-wrapper regression gate. No live tmux
integration test was required or run in this lane; the exercised tmux tests
use deterministic fixtures/mocks and the missing/replacement-context cases
remain fail-closed.
