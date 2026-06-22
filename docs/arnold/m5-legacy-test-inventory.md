<!-- M5 Phase 1 inventory: legacy test roots. -->

# M5 Legacy Test Inventory

| Test root | Status | M6 disposition | Notes |
| --- | --- | --- | --- |
| `tests/_pipeline/` | archive | delete | Native pipeline builder tests; behavior captured by workflow conformance fixtures. |
| `tests/arnold/pipeline/` | migrate | keep | Pipeline ID registry and neutral runtime tests; retain registry tests, migrate old builder tests to `arnold.workflow`. |
| `tests/pipelines/` | archive | delete | Old product pipeline tests; parity captured in `tests/arnold/conformance/workflow_manifest_runtime`. |
| Root `test_*.py` files | review | mixed | Migrate workflow-relevant tests; archive native-builder-only tests. |
| `tests/cli/test_arnold_parser_snapshot.py` | migrate | keep | Old parser snapshot kept as transition record; extended by `tests/cli/test_m5_dispatch.py`. |
| `tests/docs/test_arnold_external_builder.py` | archive | delete | Depends on native builder API; replaced by workflow external-builder tests in Phase 4. |
| `tests/arnold/conformance/workflow_manifest_runtime/` | keep | keep | Neutral conformance goldens and boundary tests. |
| `tests/arnold/workflow/` | keep | keep | Core workflow DSL, compiler, inspect, dry-run, and static-scan tests. |
| `tests/arnold/execution/` | keep | keep | Manifest runtime and execution CLI tests. |

## Notes

- `archive` tests are preserved as read-only fixtures under `tests/archive/m5/` if they capture behavior needed for parity proofs.
- No test root is whitelisted; every root has a clear migrate/archive/delete disposition.
