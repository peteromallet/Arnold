# Megaplan Functionality Regression Review

## Inputs

- Current Megaplan implementation and tests under `arnold/pipelines/megaplan/`
  and `tests/arnold/pipelines/megaplan/`.
- CLI and import characterization tests:
  `tests/test_pipeline_run_cli.py` and
  `tests/characterization/test_import_surface.py`.
- Current completion epic plus the composition and platform follow-up epics.

## Codex Verdict

Regression risk was **high** before tightening the plan. The broad Megaplan
control flow was protected, but several compatibility details were only
implicitly covered.

## Functionality-Loss Risks Accepted As Real

- `megaplan run` compatibility extends beyond canonical Megaplan. It includes
  runtime/executor flags, vendor/profile options, creative-only validation,
  manifest/runtime identity, registered non-Megaplan pipelines, and
  `PROFILE_VALIDATE` dispatch.
- Megaplan native hook semantics are detailed enough that "preserve hooks" is
  too vague. Override priority, additive overrides, loop guards, typed-port CAS
  merge, envelope conflict propagation, subloop promotion, and suspension
  cursor dual-write now need explicit tests.
- Existing resume file surfaces must survive or receive migration diagnostics:
  `state.json::resume_cursor`, `resume_cursor.json`,
  `composite_resume_cursor.json`, `awaiting_user.json`, typed suspended
  `contract_result`, and human-gate edited-artifact repointing.
- De-facto public import surfaces include more than `_pipeline`; the
  characterization suite covers `arnold_pipelines.megaplan` store, workers,
  cli, chain, execute, agent runtime, cloud modules, and private-but-used chain
  helpers.
- Chain/PR/remote execution behavior must remain protected under the new
  broker/durable substrate.
- Artifact schemas and filenames such as `review.json`, `finalize.json`,
  `final.md`, and `execution_audit.json` need a golden manifest.
- Legacy stage names must remain accepted aliases for profiles, overrides,
  status payloads, and old cursors while stable IDs become authoritative.

## Changes Made

- Composition M0 now requires legacy stage-name alias rules.
- Composition M1 now requires a Megaplan run CLI compatibility matrix, detailed
  native hook tests, stage alias compatibility, and a golden artifact manifest.
- Composition M5 now requires compatibility or migration diagnostics for
  existing Megaplan resume files and human-gate edited-artifact resume behavior.
- Completion M7 now inventories both `arnold.pipelines.megaplan.*` and
  `arnold_pipelines.megaplan.*`, treats `tests/test_pipeline_run_cli.py` and
  `tests/characterization/test_import_surface.py` as hard gates, protects
  `_pipeline/resume.py` until resume migration is proven, and explicitly names
  chain/PR helper compatibility.
- Platform M6 now adds Megaplan chain/PR and remote execution conformance under
  the platform substrate.

## Judgement

These additions are necessary. They do not change the destination, but they
close the biggest gap between a clean architectural migration and a migration
that preserves what users and tests actually rely on today.
