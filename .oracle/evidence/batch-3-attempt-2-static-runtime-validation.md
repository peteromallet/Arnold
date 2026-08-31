# Batch3 attempt-2 static/runtime validation

Validation was run read-only against the shared checkout. No source, tasklist,
status, or NBF08 artifact was changed by this lane.

## Frozen identities

| Item | Value |
|---|---|
| HEAD | `7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e` |
| `.oracle/tasklist.md` SHA-256 | `70a9185d40cf7502a25cbaedd46db3d3bb16ea1f139bc8a8f6b7082c070dbc73` |
| `docs/nbf-signal-inventory.json` SHA-256 | `1d9d9ad599ec4508c728776999e882ea809f5b60d753d1c80b435a2e0b9872be` |
| Generated inventory entries | `123` |
| Inventory `source_inputs_sha256` | `cf65ded241e0f06543ed9f6a1c616f15619ebe86ede5ea5a051e7334710e2e75` |
| `scripts/generate_nbf_signal_inventory.py` SHA-256 | `c92ac935b10747d4549a5bae6dd52da874472d1036723b61e096eb5f5a1ab64a` |

## Commands and results

### Shell syntax

```bash
bash -n \
  arnold_pipelines/megaplan/cloud/wrappers/arnold-supervisor-runtime-lib \
  arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog \
  arnold_pipelines/megaplan/cloud/wrappers/arnold-progress-auditor \
  arnold_pipelines/megaplan/cloud/wrappers/arnold-heartbeat \
  arnold_pipelines/megaplan/cloud/systemd/ensure-megaplan-resident \
  arnold_pipelines/megaplan/cloud/systemd/ensure-megaplan-watchdog
```

Result: **PASS**; six scripts parsed successfully.

### Python compilation

```bash
python -m py_compile \
  arnold_pipelines/megaplan/incident/authority.py \
  arnold_pipelines/megaplan/incident/disposition.py \
  arnold_pipelines/megaplan/incident/ledger.py \
  arnold_pipelines/megaplan/incident/schema.py \
  arnold_pipelines/megaplan/cloud/operator_control.py \
  arnold_pipelines/megaplan/cloud/cli.py \
  arnold_pipelines/megaplan/cloud/controlled_final_launch.py \
  arnold_pipelines/megaplan/cloud/worker_dispatch.py \
  arnold_pipelines/megaplan/managed_agent.py \
  arnold_pipelines/megaplan/watchdog/worker_identity.py \
  scripts/generate_nbf_signal_inventory.py
```

Result: **PASS**; 11 files compiled successfully.

### Generator and static inventory/no-bare assertions

```bash
python scripts/generate_nbf_signal_inventory.py --check
pytest -q \
  tests/arnold_pipelines/megaplan/test_python_signal_inventory.py \
  tests/cloud/test_repository_signal_inventory.py \
  tests/test_no_bare_subprocess.py
```

Results: generator **PASS** (`fresh inventory`); **14 passed** in 121.11s.

### Authority/operator/tmux/delegation boundary tests

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_signal_authority.py::test_real_tmux_marker_binding_round_trips_and_replacement_is_rejected \
  tests/arnold_pipelines/megaplan/test_signal_authority.py::test_marker_replacement_and_pid_reuse_are_rejected \
  tests/arnold_pipelines/megaplan/test_signal_authority.py::test_locked_final_revalidation_blocks_marker_replacement_before_signal \
  tests/cloud/test_watchdog_dispositions.py::test_tmux_replacement_and_missing_context_are_fail_closed \
  tests/cloud/test_watchdog_dispositions.py::test_tmux_teardown_uses_marker_owned_pane_and_captured_socket \
  tests/arnold_pipelines/megaplan/test_operator_pause.py::test_tmux_teardown_requires_exact_marker_binding_and_records_ack \
  tests/arnold_pipelines/megaplan/test_operator_pause.py::test_tmux_teardown_rejects_missing_or_replaced_binding \
  tests/arnold_pipelines/megaplan/test_operator_pause.py::test_cloud_pause_reconciles_dead_writer_flush_after_tmux_stop \
  tests/arnold_pipelines/megaplan/test_operator_pause.py::test_marker_only_stop_without_resume_authority_fails_closed \
  tests/cloud/test_operator_control.py::test_resume_injects_managed_repair_route_into_tmux_session \
  tests/cloud/test_cloud_chain_command.py::test_fresh_chain_stop_is_identity_guarded_before_reset \
  tests/cloud/test_cloud_chain_command.py::test_tmux_chain_launch_default_marker_records_run_kind \
  tests/cloud/test_cloud_chain_command.py::test_tmux_chain_launch_command_is_valid_shell \
  tests/cloud/test_cloud_chain_command.py::test_tmux_chain_launch_never_refreshes_remote_git
```

Result: **14 passed** in 2.42s. The real-tmux binding/producer/resolver and
replacement cases are deterministic fixture tests; `/opt/homebrew/bin/tmux`
is installed, but no live tmux session was created or torn down by this lane.

### Final diff check

```bash
git diff --check
```

Result: **PASS**.

## Disposition

Static, generated-inventory, no-bare, authority, operator, tmux-binding,
delegation, and replacement checks are green. No Batch3 defect was reproduced.
