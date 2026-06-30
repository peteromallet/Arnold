# M2 - Megaplan Subpipelines Layout

## Objective

Normalize Megaplan-owned package layout and import names before behavioral migrations so downstream milestones operate on stable package paths instead of one-off modules and hyphenated directories.

## Files To Change And Instructions

- `arnold/pipelines/megaplan/pipelines/writing_panel_strict.py`
  Replace the single-file entrypoint with a package-form entrypoint and reduce this module to a compatibility shim or remove it once imports are updated.
- `arnold/pipelines/megaplan/pipelines/writing-panel-strict/profiles/standard.toml`
  Move or copy this profile into the new `writing_panel_strict/` package location.
- `arnold/pipelines/megaplan/pipelines/writing-panel-strict/prompts/optimist.md`
  Move into `arnold/pipelines/megaplan/pipelines/writing_panel_strict/prompts/optimist.md`.
- `arnold/pipelines/megaplan/pipelines/writing-panel-strict/prompts/pessimist.md`
  Move into `arnold/pipelines/megaplan/pipelines/writing_panel_strict/prompts/pessimist.md`.
- `arnold/pipelines/megaplan/pipelines/writing-panel-strict/prompts/structuralist.md`
  Move into `arnold/pipelines/megaplan/pipelines/writing_panel_strict/prompts/structuralist.md`.
- `arnold/pipelines/megaplan/pipelines/writing-panel-strict/prompts/synth.md`
  Move into `arnold/pipelines/megaplan/pipelines/writing_panel_strict/prompts/synth.md`.
- `arnold/pipelines/megaplan/pipelines/writing-panel-strict/prompts/revise.md`
  Move into `arnold/pipelines/megaplan/pipelines/writing_panel_strict/prompts/revise.md`.
- `arnold/pipelines/megaplan/pipelines/writing_panel_strict/__init__.py`
  Create the canonical package export and put package metadata plus `build_pipeline(...)` here.
- `arnold/pipelines/megaplan/pipelines/writing_panel_strict/pipeline.py`
  Create the native declaration home for the strict writing-panel package.
- `arnold/pipelines/megaplan/pipelines/writing_panel_strict/steps.py`
  Move runtime-agnostic step logic here.
- `arnold/pipelines/megaplan/pipelines/writing_panel_strict/_legacy.py`
  Create only if a temporary graph baseline still needs a private legacy builder.
- `arnold/pipelines/megaplan/pipelines/select-tournament/__init__.py`
  Replace the hyphenated-package entrypoint with a compatibility shim and move real exports to `select_tournament/`.
- `arnold/pipelines/megaplan/pipelines/select-tournament/steps.py`
  Move into `arnold/pipelines/megaplan/pipelines/select_tournament/steps.py`.
- `arnold/pipelines/megaplan/pipelines/select-tournament/prompts/__init__.py`
  Move into `arnold/pipelines/megaplan/pipelines/select_tournament/prompts/__init__.py`.
- `arnold/pipelines/megaplan/pipelines/select_tournament/__init__.py`
  Create the canonical normalized package export.
- `arnold/pipelines/megaplan/pipelines/select_tournament/pipeline.py`
  Create the native declaration home for the renamed package.
- `arnold/pipelines/megaplan/pipelines/select_tournament/steps.py`
  Hold the moved runtime logic under the normalized package name.
- `arnold/pipelines/megaplan/pipelines/select_tournament/prompts/__init__.py`
  Re-home prompt package exports under the normalized name.
- `tests/_pipeline/test_writing_panel_e2e.py`
  Update imports and fixture setup to the new package-form `writing_panel_strict` layout.
- `tests/arnold/pipelines/megaplan/test_writing_panel_strict_native_parity.py`
  Update imports and package references without changing behavioral assertions yet.
- `tests/pipelines/test_select_tournament_pipeline.py`
  Update imports and any path-based assumptions to `select_tournament`.
- `tests/arnold/pipelines/megaplan/test_select_tournament_native_parity.py`
  Update imports and registered-package names to `select_tournament`.
- `tests/test_pipeline_run_cli.py`
  Update describe-path coverage if it still refers to `select-tournament` or old `writing_panel_strict.py` import paths.

## Verifiable Completion Criterion

- `writing_panel_strict` is a package under `arnold/pipelines/megaplan/pipelines/writing_panel_strict/`.
- `select_tournament` is the only canonical Python package name; the hyphenated path no longer owns live package code.
- The named tests import the normalized package paths successfully.

## Native Representation Alignment

- Matrix rows affected: Canonical source path reconciliation; Behavior parity with existing Megaplan.
- Expected status change: substrate `enabled` only. This milestone stabilizes package paths so later report-conformance reviews inspect the live source.
- Proof artifacts: import smoke tests for normalized package names, stale-path search results, and updated CLI/package references.
- False-pass guard: moving files without proving the registered package/import path changed leaves reviewers auditing stale source.
- Deferrals: no report-level Megaplan semantics are implemented here; those remain owned by completion M3.5/M5 and composition M1/M6.
- Canonical paths/imports: create or update a path note when `arnold/pipelines/...` docs and `arnold_pipelines/...` compatibility modules diverge.

## Risks And Blockers

- Package moves can leave stale imports in tests, docs, and registration metadata.
- `writing_panel_strict` has human-gate behavior, so layout changes must not hide accidental runtime changes.
- Compatibility shims can linger indefinitely unless M3 finishes the behavioral conversion quickly.

## Dependencies

- Depends on M1.
- Must finish before M3 because M3 assumes the normalized package paths already exist.
