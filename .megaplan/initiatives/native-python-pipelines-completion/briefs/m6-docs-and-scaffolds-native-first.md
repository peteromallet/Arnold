# M6 - Docs And Scaffolds Native First

## Objective

Make authored docs, generated docs, authoring helpers, and scaffolds stop
teaching graph-era, opt-in-runtime, rollout-flag, or shim-based package shapes.
M6 is intentionally **subtractive and corrective**: it removes misleading
legacy guidance and makes new scaffolds native-first, but it must not invent a
large positive authoring story that the composition follow-up epic will replace.

The desired posture is no shims for new work. New docs, generated references,
helpers, and scaffolds must not tell users to create `_legacy.py`, graph
fallback builders, compatibility namespaces, or temporary wrapper modules. If
M7's import inventory proves a runtime compatibility surface must remain for
existing callers, M6 may document it only as internal/deprecated retention, not
as an authoring pattern.

## Files To Change And Instructions

- `docs/arnold/package-authoring-contract.md`
  Remove graph-first and shim-based package guidance. Document the current
  native-first package contract narrowly: `build_pipeline(...)` returns a
  projected shell with `native_program`, required metadata is present, and new
  packages do not create compatibility shims. Do not present flat-native
  examples as the final long-term composition model.
- `docs/arnold/package-contract.md`
  Document the required metadata, `driver = ("native", "<kind>")`, and final
  registry/discovery contract as the only supported package shape for new work.
- `docs/arnold/authoring-guide.md`
  Remove graph-first authoring guidance, native-opt-in instructions, and any
  guidance that encourages authors to keep compatibility shims. Where positive
  composition guidance would be needed, point to the forthcoming native
  composition contract instead of teaching an intermediate flat-native idiom.
- `docs/arnold/creating-a-new-pipeline.md`
  Remove `--driver graph` as recommended usage and describe only the
  native-first scaffold path. Do not include a shim/fallback scaffold variant.
- `docs/arnold/examples/jokes.md`
  Regenerate the example from the migrated native-backed `jokes` package, but
  keep the example scoped to current native package mechanics rather than
  claiming to define the future compositional authoring model.
- `docs/arnold/examples/select-tournament.md`
  Update the example to `select_tournament` and the migrated package contract.
- `docs/reference/arnold-projections.md`
  Regenerate or edit the generated reference so it no longer documents
  `MEGAPLAN_M6_MANIFEST_DISCOVERY` as a real rollout gate.
- `scripts/generate_arnold_docs.py`
  Stop generating docs that imply manifest flags, graph-first scaffolds, or
  compatibility shims are part of the primary authoring path.
- `arnold/pipelines/_authoring.py`
  Make the authoring helper emit only the native-first package shape and remove
  graph-first scaffold, shim, fallback, or `_legacy.py` language from helper
  text and comments.
- `arnold/pipelines/_template/__init__.py`
  Update the template package metadata and entrypoint to the native-first
  package contract.
- `arnold/pipelines/_template/pipelines.py`
  Replace graph-oriented construction examples with the native declaration path;
  the template must not include compatibility wrappers or shim placeholders.
- `arnold/pipelines/_template/SKILL.md`
  Update template instructions so they match the native-first scaffold output
  and explicitly avoid shim/fallback package patterns.
- `tests/arnold/pipelines/test_authoring.py`
  Keep authoring-helper coverage aligned with the native-first scaffold
  contract.
- `tests/arnold/pipelines/test_package_authoring_contract.py`
  Update contract expectations to the native-first package shape and assert new
  packages do not generate shim files.
- `tests/arnold/pipelines/test_template_e2e.py`
  Verify the template still produces a runnable native-first package.
- `tests/docs/test_arnold_external_builder.py`
  Remove assertions that instruct the user to run
  `arnold pipelines new ... --driver graph` and keep the docs-to-scaffold
  workflow green.
- `tests/test_pipelines_new.py`
  Update scaffold-generation coverage to the native-first-only authoring path.

## Verifiable Completion Criterion

- No named doc or scaffold file tells users to set `ARNOLD_NATIVE_RUNTIME=1`,
  `MEGAPLAN_M6_MANIFEST_DISCOVERY=1`, or use `--driver graph` as the primary
  path.
- No named doc, generated reference, authoring helper, or scaffold teaches or
  emits compatibility shims, `_legacy.py`, graph fallback builders,
  compatibility namespaces, or temporary wrapper modules for new packages.
- M6 does not claim to be the final compositional authoring guide. Any deeper
  examples involving workflow nesting, tree traces, path resume, stable unit
  IDs, or invocable interfaces are explicitly left to the native composition
  follow-up epic.
- The template and authoring tests generate and validate native-first packages
  successfully.
- `docs/reference/arnold-projections.md` matches the behavior produced by
  `scripts/generate_arnold_docs.py`.

## Risks And Blockers

- Docs can drift from reality if generated references are not regenerated after
  helper changes.
- Template cleanup can break tests that exercise the public authoring flow
  rather than the runtime itself.
- It is easy to leave behind one or two graph-first or shim-based examples that
  keep confusing future migrations and external users.
- If M7 inventory discovers a retained runtime compatibility surface, M6 must
  not retroactively teach that surface as an authoring pattern. It remains
  internal/deprecated retention until M7 decides deletion vs. explicit internal
  compatibility.
- Teaching a rich flat-native model here would create churn because the next
  epic replaces it with compositional workflows. Keep this milestone focused on
  removing bad guidance and generating clean native-first package skeletons.

## Dependencies

- Depends on M5.
- Must finish before M7 deletes remaining compatibility surfaces, but final
  claims about retained/deleted runtime compatibility must be checked against
  M7's import inventory.
