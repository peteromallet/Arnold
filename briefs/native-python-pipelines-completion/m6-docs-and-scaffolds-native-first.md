# M6 - Docs And Scaffolds Native First

## Objective

Update authored docs, generated docs, authoring helpers, and scaffolds so the repository teaches only the native-first package contract and no longer documents opt-in native runtime, manifest rollout flags, or graph-first scaffolding as the primary path.

## Files To Change And Instructions

- `docs/arnold/package-authoring-contract.md`
  Rewrite the authoring contract around `build_pipeline(...)` returning a projected shell with `native_program`.
- `docs/arnold/package-contract.md`
  Document the required metadata, `driver = ("native", "<kind>")`, and final registry/discovery contract.
- `docs/arnold/authoring-guide.md`
  Remove graph-first authoring guidance and native-opt-in instructions.
- `docs/arnold/creating-a-new-pipeline.md`
  Remove `--driver graph` as recommended usage and describe only the native-first scaffold path.
- `docs/arnold/examples/jokes.md`
  Regenerate the example from the migrated native-backed `jokes` package.
- `docs/arnold/examples/select-tournament.md`
  Update the example to `select_tournament` and the migrated package contract.
- `docs/reference/arnold-projections.md`
  Regenerate or edit the generated reference so it no longer documents `MEGAPLAN_M6_MANIFEST_DISCOVERY` as a real rollout gate.
- `scripts/generate_arnold_docs.py`
  Stop generating docs that imply manifest flags or graph-first scaffolds are the primary path.
- `arnold/pipelines/_authoring.py`
  Make the authoring helper emit the native-first package shape and remove graph-first scaffold language from helper text and comments.
- `arnold/pipelines/_template/__init__.py`
  Update the template package metadata and entrypoint to the final native-first authoring contract.
- `arnold/pipelines/_template/pipelines.py`
  Replace graph-oriented construction examples with the native declaration path.
- `arnold/pipelines/_template/SKILL.md`
  Update template instructions so they match the native-first scaffold output.
- `tests/arnold/pipelines/test_authoring.py`
  Keep authoring-helper coverage aligned with the new scaffold contract.
- `tests/arnold/pipelines/test_package_authoring_contract.py`
  Update the contract expectations to the native-first package shape.
- `tests/arnold/pipelines/test_template_e2e.py`
  Verify the template still produces a runnable native-first package.
- `tests/docs/test_arnold_external_builder.py`
  Remove assertions that instruct the user to run `arnold pipelines new ... --driver graph` and keep the docs-to-scaffold workflow green.
- `tests/test_pipelines_new.py`
  Update scaffold-generation coverage to the native-first-only authoring path.

## Verifiable Completion Criterion

- No named doc or scaffold file tells users to set `ARNOLD_NATIVE_RUNTIME=1`, `MEGAPLAN_M6_MANIFEST_DISCOVERY=1`, or use `--driver graph` as the primary path.
- The template and authoring tests generate and validate native-first packages successfully.
- `docs/reference/arnold-projections.md` matches the behavior produced by `scripts/generate_arnold_docs.py`.

## Risks And Blockers

- Docs can drift from reality if generated references are not regenerated after helper changes.
- Template cleanup can break tests that exercise the public authoring flow rather than the runtime itself.
- It is easy to leave behind one or two graph-first examples that keep confusing future migrations and external users.

## Dependencies

- Depends on M5.
- Must finish before M7 deletes the remaining compatibility surfaces described in older docs and scaffolds.
