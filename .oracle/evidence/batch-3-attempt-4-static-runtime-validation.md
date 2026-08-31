# Batch 3 attempt 4 — final static/runtime validation

This evidence is bound to the final shared-tree identities:

- Branch: `reconcile/nbf-attempt4-2297`
- HEAD: `7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e`
- Tasklist SHA-256: `70a9185d40cf7502a25cbaedd46db3d3bb16ea1f139bc8a8f6b7082c070dbc73`
- Inventory: `docs/nbf-signal-inventory.json`
- Inventory SHA-256: `44331a169f8f8b4d5ae6141c5fe905cd79691e404bdaaa0fbe72c16c45525bf1`
- Inventory entries: `122`
- Inventory source-input SHA-256: `60d5d933e722d8f49905b534866e1a2bdb6d0c7766103f3176adacd7cd33a958`
- Generator version: `nbf05-signal-inventory-v1`
- Discovery rules version: `nbf05-discovery-rules-v1`
- Source digest version: `nbf05-source-inputs-v2`

## Commands and results

All commands ran from the repository root with fresh temporary pytest
basetemps. `PYTHONDONTWRITEBYTECODE=1` was used for pytest.

1. `python3 scripts/generate_nbf_signal_inventory.py`
   Result: PASS; deterministic inventory regenerated.
2. `python3 scripts/generate_nbf_signal_inventory.py --check`
   Result: PASS; first independent freshness check.
3. `python3 scripts/generate_nbf_signal_inventory.py --check`
   Result: PASS; second independent freshness check.
4. `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q --cache-clear --basetemp "$(mktemp -d /private/tmp/nbf-final-evidence.XXXXXX)" tests/cloud/test_repository_signal_inventory.py tests/arnold_pipelines/megaplan/test_python_signal_inventory.py tests/test_no_bare_subprocess.py tests/arnold_pipelines/megaplan/test_subagent_launcher_disposition.py`
   Result: PASS: 30 passed.
   This includes the three exact inventory validators, the fan-kill
   classification tests, and the normalized-discovery-rules content mutation
   regression that proves `--check` becomes stale.
5. In-memory `compile()` over all touched Python files reported by
   `git status --porcelain`.
   Result: PASS: 38 files compiled; no bytecode was written.
6. `git diff --check`
   Result: PASS.
7. Direct import/callability check for
   `test_shell_signal_sites_are_classified`,
   `test_python_generated_shell_controls_are_classified`,
   `test_shell_inventory_exclusions_are_explicit`, and
   `test_source_digest_binds_normalized_discovery_rules_content`.
   Result: PASS: all 4 symbols resolve.

The final Sol changes are limited to inventory contract metadata/digest
coverage, inventory test baselines, and deterministic generated inventory
classification. No production semantics were changed after the Sol fixes;
production `fan_kill.py`, tasklist, Oracle packet, and NBF08 artifacts were not
edited in this lane.

