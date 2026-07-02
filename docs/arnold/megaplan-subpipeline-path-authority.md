# Megaplan Subpipeline Path Authority (M2)

## Scope

This note records the canonical path authority for M2 Megaplan subpipelines.
It is **substrate proof only** — it does not claim report-level Megaplan native
representation conformance. See
`docs/arnold/megaplan-native-representation-report.md` for the report-owned
completeness contract.

## Canonical Package Family

| Path | Status |
|------|--------|
| `arnold_pipelines/megaplan/pipelines/writing_panel_strict/` | Canonical Python package |
| `arnold_pipelines/megaplan/pipelines/select_tournament/` | Canonical Python package |

Both directories are live Python packages. Each exposes a `build_pipeline`
callable that returns an `arnold.pipeline.Pipeline` with a non-null
`native_program`. The registry in `arnold_pipelines/discovery.py` records both
as `disposition=migrate`, `migrated=True`, `builder_contract=native`.

## Deleted Legacy Duplicate Family

| Path | Status |
|------|--------|
| `arnold/pipelines/megaplan/pipelines/` | Deleted legacy duplicate — **do not repopulate** |

The `arnold/pipelines/` tree does not exist on disk. All legacy entries under
`arnold/pipelines/megaplan/pipelines/` are recorded in the discovery table as
`disposition=delete`, `migrated=False`. They must not be recreated, imported, or
used as reference targets.

## Underscore vs. Hyphen

| Form | Meaning |
|------|---------|
| `writing_panel_strict` | Python package name (directory, import path) |
| `select_tournament` | Python package name (directory, import path) |
| `writing-panel-strict` | CLI / runtime pipeline identifier (`name` attribute) |
| `select-tournament` | CLI / runtime pipeline identifier (`name` attribute) |

The `name` module-level attribute in each `__init__.py` uses the hyphenated form
as the runtime identity string. The Python package directory and import path use
underscores. This distinction must be preserved: no hyphenated Python package
directories exist, and no underscored CLI identifiers are in use.

## Substrate Proof vs. Report Conformance

A non-null `native_program`, native trace, route label, or projected shell is
**substrate evidence only** unless the report-owned semantics are visible at
that higher level. Report conformance is owned by the
`megaplan-native-representation-report.md` contract and its traceability ledger.
This M2 milestone provides the substrate foundation — confirmed canonical
package locations, live `build_pipeline` exports, and registry disposition — but
does not assert completeness against the full native representation report.
