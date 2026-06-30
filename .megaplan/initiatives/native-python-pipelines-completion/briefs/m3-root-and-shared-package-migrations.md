# M3 - Root And Shared Package Migrations

## Objective

Migrate the shared package set that is closest to the final contract so each package returns a projected `Pipeline` shell with `native_program`, keeps only private legacy graph baselines where strictly required, and stops depending on graph-first discovery or runtime assumptions.

## Files To Change And Instructions

- `arnold/pipelines/megaplan/pipelines/creative/__init__.py`
  Move package metadata and `build_pipeline(...)` to the final contract and stop exporting graph-first behavior as canonical.
- `arnold/pipelines/megaplan/pipelines/creative/steps.py`
  Keep runtime logic here and remove graph-only assumptions from orchestration.
- `arnold/pipelines/megaplan/pipelines/creative/prompts/__init__.py`
  Remove centralized prompt-export wiring such as `_CREATIVE_PROMPT_EXPORTS`; keep only package-owned prompt exports.
- `arnold/pipelines/megaplan/pipelines/creative/pipeline.py`
  Create the native declaration and attach `native_program` from `build_pipeline(...)`.
- `tests/pipelines/test_creative_pipeline.py`
  Update runtime assertions to the native-backed package contract.
- `tests/arnold/pipelines/megaplan/test_creative_native_parity.py`
  Convert the suite into native-truth behavioral coverage rather than graph-structure comparison.

- `arnold/pipelines/megaplan/pipelines/doc/__init__.py`
  Move package metadata and `build_pipeline(...)` to the final contract.
- `arnold/pipelines/megaplan/pipelines/doc/steps.py`
  Preserve parameterized fanout behavior without relying on graph-shape assertions.
- `arnold/pipelines/megaplan/pipelines/doc/prompts/__init__.py`
  Keep prompt exports package-local and update any stale graph-era registration assumptions.
- `arnold/pipelines/megaplan/pipelines/doc/pipeline.py`
  Create the native declaration for the doc package.
- `tests/pipelines/test_doc_pipeline.py`
  Assert runtime behavior and outputs instead of graph topology.
- `tests/test_doc_assembly.py`
  Keep doc-assembly behavior aligned with the migrated package contract.
- `tests/arnold/pipelines/megaplan/test_doc_native_parity.py`
  Convert to native-truth trace or behavior assertions.

- `arnold/pipelines/megaplan/pipelines/jokes/__init__.py`
  Move metadata and `build_pipeline(...)` to the final native-backed contract.
- `arnold/pipelines/megaplan/pipelines/jokes/steps.py`
  Preserve package behavior while removing graph-first construction assumptions.
- `arnold/pipelines/megaplan/pipelines/jokes/prompts/__init__.py`
  Keep prompt exports local to the package.
- `arnold/pipelines/megaplan/pipelines/jokes/pipeline.py`
  Create the native declaration; keep `_JokesNativeAdapter` only if it is still needed for config-to-state wiring.
- `tests/pipelines/test_jokes_pipeline.py`
  Update contract expectations to `native_program` plus projected-shell behavior.
- `tests/arnold/pipelines/megaplan/test_jokes_native_parity.py`
  Convert to native-truth runtime coverage.

- `arnold/pipelines/megaplan/pipelines/live_supervisor/__init__.py`
  Make the package metadata and `build_pipeline(...)` native-first.
- `arnold/pipelines/megaplan/pipelines/live_supervisor/pipelines.py`
  Reduce this module to private compatibility code or delete its public builder role.
- `arnold/pipelines/megaplan/pipelines/live_supervisor/steps.py`
  Keep shared runtime logic here.
- `arnold/pipelines/megaplan/pipelines/live_supervisor/model.py`
  Remove any graph-specific data-shape assumptions.
- `arnold/pipelines/megaplan/pipelines/live_supervisor/repair_agent.py`
  Keep repair behavior compatible with the native runtime contract.
- `arnold/pipelines/megaplan/pipelines/live_supervisor/rules.py`
  Preserve policy behavior while removing graph-runtime coupling.
- `arnold/pipelines/megaplan/pipelines/live_supervisor/pipeline.py`
  Create the native declaration for the package.
- `tests/pipelines/test_live_supervisor_pipeline.py`
  Update the package-contract assertions.
- `tests/pipelines/test_live_supervisor_model.py`
  Keep model-shape coverage aligned with the migrated package.
- `tests/pipelines/test_live_supervisor_repair_agent.py`
  Keep repair-agent behavior stable under native execution.
- `tests/pipelines/test_live_supervisor_rules.py`
  Update rule-evaluation expectations if the runtime envelope changes.
- `tests/pipelines/test_live_supervisor_steps.py`
  Keep step-level behavior intact.
- `tests/arnold/pipelines/megaplan/test_live_supervisor_native_parity.py`
  Convert to native-truth runtime coverage.

- `arnold/pipelines/megaplan/pipelines/writing_panel_strict/__init__.py`
  Finish the final-contract migration started in M2.
- `arnold/pipelines/megaplan/pipelines/writing_panel_strict/pipeline.py`
  Preserve exact `continue` and `stop` gate semantics under native suspension and resume.
- `arnold/pipelines/megaplan/pipelines/writing_panel_strict/steps.py`
  Keep runtime logic separate from declaration.
- `arnold/pipelines/megaplan/pipelines/writing_panel_strict/_legacy.py`
  Leave only a private graph baseline builder if the legacy suite still needs it.
- `tests/_pipeline/test_writing_panel_e2e.py`
  Keep end-to-end behavior constant while shifting the runtime contract.
- `tests/arnold/pipelines/megaplan/test_writing_panel_strict_native_parity.py`
  Convert to native-truth assertions.

- `arnold/pipelines/megaplan/pipelines/epic_blitz.py`
  Keep the file in place, attach a real `native_program`, and remove graph fallback as the actual execution path.
- `tests/_pipeline/test_epic_blitz_e2e.py`
  Keep end-to-end behavior stable under the migrated contract.
- `tests/arnold/pipelines/megaplan/test_epic_blitz_native_parity.py`
  Convert to native-truth runtime coverage.

- `arnold/pipelines/megaplan/pipelines/select_tournament/__init__.py`
  Finalize the renamed package metadata and `build_pipeline(...)`.
- `arnold/pipelines/megaplan/pipelines/select_tournament/pipeline.py`
  Create the native declaration and replace hardcoded candidate assumptions with argument-driven state wiring.
- `arnold/pipelines/megaplan/pipelines/select_tournament/steps.py`
  Keep runtime logic here after the rename.
- `arnold/pipelines/megaplan/pipelines/select_tournament/prompts/__init__.py`
  Keep prompt exports local to the renamed package.
- `tests/pipelines/test_select_tournament_pipeline.py`
  Keep package-contract coverage aligned with the migrated package.
- `tests/arnold/pipelines/megaplan/test_select_tournament_native_parity.py`
  Convert to native-truth runtime coverage.

- `arnold/pipelines/folder_audit/__init__.py`
  Move metadata and `build_pipeline(...)` to the final contract.
- `arnold/pipelines/folder_audit/native.py`
  Remove assumptions that native execution requires graph flattening or env-gated runtime.
- `arnold/pipelines/folder_audit/pipeline.py`
  Create the native declaration for the package.
- `tests/pipelines/test_folder_audit.py`
  Update runtime and contract assertions to the final native-backed package shape.

- `arnold/pipelines/deliberation/__init__.py`
  Stop overloading `build_pipeline()` for discovery vs runtime and move to the final contract.
- `arnold/pipelines/deliberation/pipelines.py`
  Reduce this module to private legacy baselines or helper code only.
- `arnold/pipelines/deliberation/steps.py`
  Keep runtime step logic isolated from declaration concerns.
- `arnold/pipelines/deliberation/profile.py`
  Keep package metadata aligned with the required final contract.
- `arnold/pipelines/deliberation/pipeline.py`
  Create the native declaration.
- `tests/arnold/pipelines/deliberation/test_e2e.py`
  Keep end-to-end runtime behavior stable.
- `tests/arnold/pipelines/deliberation/test_native_parity.py`
  Convert to native-truth runtime coverage.
- `tests/arnold/pipelines/deliberation/test_skeleton.py`
  Update contract assumptions to the new package shape.
- `tests/arnold/pipelines/deliberation/test_steps.py`
  Keep step-level behavior intact.
- `tests/boundary/test_deliberation_import_leak.py`
  Ensure the contract cleanup does not leak old import surfaces.

## Verifiable Completion Criterion

- Every file listed above now participates in a package that returns a projected `Pipeline` with non-null `native_program`.
- `creative`, `doc`, `jokes`, `live_supervisor`, `writing_panel_strict`, `epic_blitz`, `select_tournament`, `folder_audit`, and `deliberation` are validator-clean under the M1 contract.
- Remaining graph builders are private baselines only and no longer masquerade as the primary runtime path.

## Risks And Blockers

- `writing_panel_strict`, `epic_blitz`, and `deliberation` all have behavior that can appear structurally correct while being runtime-wrong.
- `folder_audit` still contains explicit native-runtime guard logic today and may hide transition bugs.
- `live_supervisor` spans multiple modules, so package-contract cleanup can leave behind split-brain builder logic unless it is tightened deliberately.

## Dependencies

- Depends on M1 and M2.
- Must finish before M3.5, M5, and M7.
