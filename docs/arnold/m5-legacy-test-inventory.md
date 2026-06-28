<!-- M5 Phase 1 inventory: legacy test roots. -->

# M5 Legacy Test Inventory

| Test root | Status | M6 disposition | Notes |
| --- | --- | --- | --- |
| `tests/_pipeline/` | archive | delete | Moved to `tests/archive/m5/_pipeline`; native pipeline builder tests; behavior captured by workflow conformance fixtures. |
| `tests/arnold/pipeline/` | migrate | keep | Pipeline ID registry and neutral runtime tests; retain registry tests, migrate old builder tests to `arnold.workflow`. |
| `tests/pipelines/` | mixed | mixed | `test_folder_audit.py` and `test_shared_native_contract.py` are kept as native-backed compatibility coverage; other old product pipeline tests are archived under `tests/archive/m5/pipelines`. Parity is captured in `tests/arnold/conformance/workflow_manifest_runtime`. |
| `tests/arnold_pipelines/test_discovery.py` | migrate | keep | Discovery contract tests for shipped `arnold_pipelines` packages. |
| `tests/arnold_pipelines/test_shipped_pipeline_migration.py` | migrate | keep | Compile, dry-run, fake-run, and manifest-hash tests for workflow-target shipped pipelines; native contract checks for native-backed targets. |
| `tests/arnold_pipelines/test_template_e2e.py` | migrate | keep | Canonical workflow-first scaffold contract tests. |
| Root `test_*.py` files | review | mixed | Migrate workflow-relevant tests; archive native-builder-only tests. |
| `tests/cli/test_arnold_parser_snapshot.py` | migrate | keep | Old parser snapshot kept as transition record; extended by `tests/cli/test_m5_dispatch.py`. |
| `tests/cli/test_m5_workflow_cli.py` | migrate | keep | Workflow CLI semantic tests (check, manifest, dot, dry-run, run, resume, describe). |
| `tests/cli/test_m5_dispatch.py` | migrate | keep | Top-level dispatch and workflow subcommand surface tests. |
| `tests/cli/test_m5_operators.py` | migrate | keep | Retained operator command tests (status, trace, inspect, override). |
| `tests/docs/test_arnold_external_builder.py` | archive | delete | Moved to `tests/archive/m5/docs`; depends on native builder API. |
| `tests/arnold/conformance/workflow_manifest_runtime/` | keep | keep | Neutral conformance goldens and boundary tests. |
| `tests/arnold/workflow/` | keep | keep | Core workflow DSL, compiler, inspect, dry-run, and static-scan tests. |
| `tests/arnold/execution/` | keep | keep | Manifest runtime and execution CLI tests. |

## Notes

- `archive` tests are preserved as read-only fixtures under `tests/archive/m5/` if they capture behavior needed for parity proofs.
- No test root is whitelisted; every root has a clear migrate/archive/delete disposition.
