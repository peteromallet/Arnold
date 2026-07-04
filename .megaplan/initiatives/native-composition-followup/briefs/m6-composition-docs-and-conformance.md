# M6 - Composition Docs And Conformance

## Objective

Turn the implemented composition model into the documented and tested Arnold
authoring contract. Docs, scaffolds, and conformance suites should teach the
actual end state for this epic: stable invocable steps/workflows, declared
inputs/outputs, workflow-in-workflow composition, loops over recorded state,
static graph queries, tree traces, per-attempt audit skeletons, and path resume.

## Files To Change And Instructions

- `docs/arnold/authoring-guide.md`
  Document compositional workflows, stable IDs, declared interfaces, nested
  invocation, loops, and the routing boundary.
- `docs/arnold/package-authoring-contract.md`
  Update package-level expectations for compositional workflows and stable
  workflow identity.
- `docs/arnold/workflow-authoring.md`
  Add examples for a single workflow, a nested workflow, a loop over recorded
  state, repeated child workflow use, and a path-resume scenario. Examples
  should use `.pypeline` files for authored workflows and `.py` only for helper
  implementation modules or compatibility shims.
- `docs/arnold/native-composition-contract.md`
  Ensure the final implemented contract matches the M0 contract, or update the
  contract with deliberate decisions made during implementation.
- `arnold/pipelines/_authoring.py`
  Ensure generated scaffolds use the compositional format and no shim/fallback
  package pattern. The scaffold should generate a small compositional example,
  not only a flat step chain.
- `arnold/pipelines/_template/`
  Update template code and skill instructions to the compositional contract.
- `tests/arnold/pipeline/native/`
  Add a conformance suite for composition: nested invocation, tree trace,
  static graph queries, per-attempt audit skeleton, composite resume, routing
  validator, loop iteration paths, depth-3 nesting, and repeated child workflow
  use.
- `tests/arnold/pipelines/megaplan/`
  Add the Megaplan native-representation conformance suite. It must include the
  fixed scenario manifest for D1-D15: prep blocking/resume-clarify and imported
  criteria outputs; critique variants/retry/fanout/fallback; gate
  malformed/empty payload normalization, unavailable-agent preflight route,
  high-complexity downgrade, reprompt, debt, flag-resolution fallback, and
  critique/gate/revise cap/no-progress/severity termination, including
  critical-blocker block/escalate and cosmetic-only force-proceed/debt cases;
  tiebreaker pick/escalate/replan; finalize task generation, scoped/full
  baseline selection, missing-scoped-baseline fallback-to-revise route,
  finalize failure golden, `user_actions.md`, before/after execute actions, and
  synthetic before-execute gate; execute DAG, approval, no-review,
  deferred-human and protected actions; review fanout, reducer ordering, infra
  retry, rework caps, explicit recoverable-block/escalation route for
  cap-exhausted blockers, and force-proceed; every `_OVERRIDE_ACTIONS` action;
  timeout/retry/escalation; phase and task-complexity model routing;
  runtime-list fanout; typed loop exits; trace/resume; and handler extraction.
- `tests/docs/`
  Keep examples and generated docs synchronized with the implemented API.

## Verifiable Completion Criterion

- A new author following docs/scaffolds writes the compositional format by
  default.
- Documentation includes Megaplan as the real-world compositional reference.
- Conformance tests lock stable unit IDs, declared interfaces, nested
  invocation, loops, static graph queries, tree traces, path addressing,
  per-attempt audit skeletons, and composite resume as public behavior.
- Conformance includes a native-Python authoring gate for canonical Megaplan:
  `workflow.pypeline` and imported native subworkflows must express product
  control flow with Python branches, loops, calls, subworkflow calls, and typed
  outcomes. The gate rejects author-facing control flow built from component
  constants, generic stage dispatch, route tables, handler refs, or direct
  manifest/node builders. If `workflow.py` remains, it must be proven to be a
  compatibility loader/re-export with no product semantics.
- Conformance includes a replay-consistency gate: run an equivalent nested
  workflow uninterrupted and with interruption/resume, then assert the final
  state and committed side-effect record are equivalent.
- Structural conformance fails if `critique`, `gate`, `tiebreaker`, `execute`,
  `review`, or `override` remain single handler-backed stages or if a report
  semantic exists only as a `handler_ref`, handler-local route decision, or
  implicit `current_state`/`next_step` mutation.
- Review cap conformance fails if cap-exhausted blocking review outcomes are
  represented only by retained review-handler mutation of `STATE_BLOCKED`,
  `resume_cursor`, `current_state`, or `next_step`; the canonical workflow
  source or declared policy must expose the recoverable-block/escalation route.
- The override matrix is generated from the current `_OVERRIDE_ACTIONS` keys.
  Terminal actions must appear as declared routes; additive/config actions must
  appear as declared effects with tests. A new `_OVERRIDE_ACTIONS` key absent
  from the matrix fails conformance.
- The rendered policy view includes timeout, retryability, escalation, phase
  model routes, and task-complexity model routes. A hidden profile/model picker
  may not satisfy model routing without declared route metadata.
- Policy conformance proves the relevant policy objects are attached to the
  compiled/rendered workflow at the source call site or declared workflow
  policy. Exported module constants such as model-routing, robustness,
  artifact-contract, or suspension policies do not count unless the compiled
  workflow renders and tests them on the affected steps, subworkflows, or
  dynamic-map call sites.
- The source-readability conformance check is mechanical as well as human:
  it scans the canonical workflow source and imported native subworkflow files
  for prohibited graph-era authoring constructs, including `SOURCE_*`-style
  component calls, `handler_ref` carriers, route-label dispatch tables, generic
  stage dispatch, and direct manifest/node construction in product control
  flow. Allowed retained uses must be documented as pure phase bodies or
  compatibility projection code with source-invariant tests.
- The source-path conformance check requires
  `arnold_pipelines/megaplan/workflows/workflow.pypeline` to be the canonical
  authored workflow source. A retained `workflow.py` must be tested as a
  compatibility shim and may not be listed as the semantic carrier for any
  implemented report row.
- No doc or scaffold teaches shims, graph fallback builders, or compatibility
  wrapper modules as an authoring pattern.
- Docs are explicit that this epic delivers composition on the existing native
  substrate. Worktree reconcile, credential brokerage, DBOS/Postgres fleet
  durability, full pack/versioning product, and production supervision are
  covered by the platform follow-up epic, not by this composition epic.
- Before platform can launch, this milestone produces
  `docs/arnold/megaplan-composition-conformance-report.md`, an explicit
  `proof-map.json` for the composition chain, and
  `.megaplan/initiatives/native-composition-followup/completion-manifest.json`
  using `megaplan chain manifest --spec
  .megaplan/initiatives/native-composition-followup/chain.yaml --proof-map
  <proof-map.json>`.

## Native Representation Alignment

- Matrix rows owned or affected: all composition-owned rows in `docs/arnold/megaplan-native-representation-alignment-plan.md`, especially Source readability; Handler topology extraction/purity audit; Golden trace regeneration guard; Behavior parity with existing Megaplan.
- Expected status change: no composition-owned row may remain `missing` or merely planning-only `enabled`; each must be `implemented` with proof or explicitly `deferred` to a downstream owner.
- Proof artifacts: row-by-row alignment proof, structural conformance test, native-Python anti-wrapper test over `workflow.pypeline`, handler-purity inventory and scans, mutation tests moving logic back into handlers, fixed D1-D15 scenario manifest, generated override action matrix, rendered policy view, static topology snapshots, rendered topology diff, docs/scaffold tests, installed-package smoke test, source-path reconciliation proof, `workflow.py` compatibility-shim proof if retained, `docs/arnold/megaplan-composition-conformance-report.md`, the explicit `proof-map.json` used for platform handoff, and the generated `completion-manifest.json`.
- False-pass guard: human-readable docs or route labels do not prove conformance unless structural checks fail when semantics are hidden in handlers.
- Anti-wrapper guard: a decorated Python file that still orchestrates Megaplan
  by calling graph-era component constants, generic stages, handler refs, or
  manifest builders is not native representation conformance. Final M6 must
  fail that shape even if nested traces, route labels, or compiled manifests
  appear correct.
- Doctrine gate: final docs and conformance must prove that canonical
  compositional source is the semantic authority, `WorkflowManifest` is the
  compiled runtime/replay/inspection artifact, and `Pipeline.native_program`
  remains compatibility dispatch substrate. Installed-package smoke tests must
  exercise that relationship, not just source-tree tests.
- Deferrals: platform-only production guarantees must be listed with owner,
  blocking proof, and platform M6 preservation check. A report-owned Megaplan
  semantic cannot be deferred from this milestone because it remains hidden in a
  handler, metadata constant, route label, manifest projection, native trace, or
  `native_program` shell.
- Canonical source paths/imports: final docs and conformance must point to `arnold_pipelines/megaplan/workflows/workflow.pypeline` as the canonical authored workflow source, describe any `workflow.py` compatibility shim, and verify installed package/import path behavior by smoke tests.

## Risks And Blockers

- Docs can outrun implementation. Every example must be backed by a test or a
  generated artifact check.
- The Megaplan example should be explanatory without exposing unnecessary
  internal hook machinery as part of the normal authoring surface.
- If docs hide the deferred platform boundaries, users will mistake the local
  composition system for the full production operating model described in the
  design doc.

## Dependencies

- Depends on M5.
