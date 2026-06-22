<!-- M5 Phase 1 inventory: scripts, tools, and root helpers. -->

# M5 Script / Tool Inventory

## `scripts/`

| Script | Status | Final location / action | M6 disposition |
| --- | --- | --- | --- |
| `scripts/check_workflow_pipeline_inventory.py` | migrate | Keep; strengthened M5 scanner. | keep |
| `scripts/check_pipeline_id_registry.py` | migrate | Keep; add hash and survivor-ref validation. | keep |
| `scripts/validate_package_disposition.py` | migrate | Keep; validates package-disposition.yaml. | keep |
| `scripts/render_package_disposition_md.py` | migrate | Keep; renders disposition Markdown. | keep |
| `scripts/generate_arnold_docs.py` | migrate | Update to consume `arnold.workflow` APIs. | keep |
| `scripts/adopt_plan.py` | migrate | Update to use workflow manifest/execution surface. | keep |
| `scripts/backfill_step_receipts.py` | archive | Moved to `docs/archive/m5/scripts/`. | delete |
| `scripts/megaplan_live_watchdog.py` | migrate | Update to call new live-supervisor workflow runtime. | keep |
| `scripts/m4_oracle_bisect.py` | archive | Moved to `docs/archive/m5/scripts/`. | delete |
| `scripts/record_oracle_traces.py` | archive | Moved to `docs/archive/m5/scripts/`. | delete |
| `scripts/record_workflow_next_parity.py` | migrate | Keep; records parity fixtures for workflow runtime. | keep |
| `scripts/simulate_watchdog_end_to_end.py` | migrate | Keep; exercises live-supervisor workflow. | keep |
| `scripts/silent_failure_census.py` | archive | Moved to `docs/archive/m5/scripts/`. | delete |

## `tools/`

| Tool | Status | Final location / action | M6 disposition |
| --- | --- | --- | --- |
| `tools/m4_oracle_bisect.py` | archive | Moved to `docs/archive/m5/tools/`. | delete |

## Root helpers

| Helper | Status | Final location / action | M6 disposition |
| --- | --- | --- | --- |
| `_gen_corpus.py` | archive | Moved to `docs/archive/m5/`. | delete |
| `_gen_golden_traces.py` | archive | Moved to `docs/archive/m5/`. | delete |

## Notes

- `migrate` scripts must run against installed wheel imports, not editable-only old paths.
- Duplicates (e.g., `tools/m4_oracle_bisect.py` vs `scripts/m4_oracle_bisect.py`) are consolidated or archived.
- Whitelist rows: none.
