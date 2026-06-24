# M8 Generated Assets And Merge-Result Conformance Report

## Outcome

The post-authoring final conformance pass is complete. All generated assets now
reflect Python-shaped workflow authoring as the product-facing surface, and the
integrated merge result passes the source/wheel/sdist and runtime gates.

## Regenerated and verified assets

| Asset / gate | Command / test | Result |
|---|---|---|
| Package-disposition manifest + rendered Markdown | `scripts/validate_package_disposition.py --summary` and `scripts/render_package_disposition_md.py --check` | `OK: docs/arnold/package-disposition.md matches generated output.` |
| Arnold reference docs, skills, and registries | `scripts/generate_arnold_docs.py --check` | `Arnold generated artifacts are up to date.` |
| Manifest identity ledger | `scripts/check_pipeline_id_registry.py --write-identity-report` and `--check-identity-report` | `pipeline ID registry check passed` |
| M6 purge gate | `scripts/m6_purge_gate.py` | `m6 purge gate passed` |
| Chain done gate | `scripts/chain_done_gate.py --spec ... --state ...` | Passed after final milestone completion recorded |

## Final conformance gates

| Gate | Evidence |
|---|---|
| Source/wheel/sdist builds | `tests/installed_wheel/test_m7_runtime_conformance.py` builds a wheel and sdist with Hatchling and installs the wheel into a clean venv. |
| Installed-wheel positive and negative tests | M5/M6/M7 installed-wheel tests assert required artifacts are present and deleted surfaces cannot be imported. |
| Dynamic import tracing | `tests/installed_wheel/test_m6_import_failures.py::test_installed_runtime_import_tracing_lacks_deleted_prefixes` |
| `sys.modules` deleted-prefix audit | `tests/installed_wheel/test_m6_import_failures.py::test_m6_no_sys_modules_leakage_in_installed_wheel` and source-tree `tests/arnold_pipelines/megaplan/test_package.py` |
| Python-shaped authoring smoke tests | `tests/arnold/workflow/test_authoring_runtime_equivalence.py` (13 passed) compiles and runs authored M3 fixtures; CLI `check`/`compile`/`explain` exercised from installed wheel. |
| Merge-result conformance | Integrated `python-shaped-workflow-authoring-cleanup` branch contains M1–M8 with passing runtime and packaging gates. |

## Constraints honored

- Stale explicit DSL fixtures were not certified as the final source of truth.
- Generated catalogs and ledgers remain derived artifacts.
- No legacy authoring or runtime surfaces were reintroduced.
