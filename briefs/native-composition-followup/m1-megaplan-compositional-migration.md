# M1 - Megaplan Compositional Migration

## Objective

Migrate canonical Megaplan into the new compositional workflow format as the
first real proof target after M0 defines the contract. Megaplan should be
expressed as a native workflow composed from named subworkflows and steps, with
review/revise/execute loops represented as workflow structure rather than
one-off runtime or graph-era orchestration. This milestone proves the target
abstraction against Arnold's hardest real workflow without letting Megaplan
invent one-off semantics outside the M0 contract.

## Prerequisite

Do not start this milestone until `briefs/native-python-pipelines-completion/chain.yaml`
has completed through M7 and the native-first completion branch is clean.

## Files To Change And Instructions

- `arnold/pipelines/megaplan/pipeline.py`
  Rework the canonical Megaplan declaration into compositional units. Split the
  top-level workflow into explicit nested native workflows where the domain has
  real boundaries: planning/prep, critique/revise loop, gate/tiebreaker handling,
  finalize/execute/review, and any human-gated continuation path. Every
  subworkflow must use explicit stable IDs and declared inputs/outputs from the
  M0 contract.
- `arnold/pipelines/megaplan/native_runner.py`
  Keep runner behavior stable while dispatching the compositional Megaplan
  workflow. Remove any special-case stage-order assumptions that the new
  workflow structure makes obsolete.
- `arnold/pipelines/megaplan/native_hooks.py`
  Preserve Megaplan-specific hook behavior while making child workflow
  completion, suspension, and envelope joining explicit. No hidden graph fallback
  semantics. Lock the existing hook details with unit tests: override priority
  `termination > transition > recovery`, additive `add-note` / `set-profile` /
  `set-model` / `set-vendor`, `UnknownOverrideError`, event emission,
  policy-backed loop guards, typed-port CAS merge, executor-key disk merge,
  envelope conflict propagation, subloop promotion, and composite suspension
  cursor dual-write.
- `arnold/pipeline/native/compiler.py`
  Add only the compiler support needed by canonical Megaplan's compositional
  declaration if general lowering is not yet present. Keep the implementation
  narrow and covered; M3 generalizes the feature. Any temporary narrow support
  must use the M0 invocable metadata and path model, must not create a semantic
  side channel, and must be listed in the handoff.
- `arnold/pipeline/native/runtime.py`
  Support the Megaplan composition shape without changing unrelated runtime
  behavior. If child execution semantics are insufficient, document the general
  fix needed for M2 instead of adding Megaplan-only runtime hacks.
- `tests/arnold/pipelines/megaplan/`
  Add or update tests proving the compositional Megaplan workflow preserves the
  existing native behavior for proceed, iterate, tiebreaker, escalation,
  execute/review, human-gated continue, and abort/stop paths. Add a Megaplan
  run CLI compatibility matrix covering `--runtime`, deprecated `--executor`,
  `--vendor`, creative-only `--form` / `--primary-criterion`, profile loading,
  `PROFILE_VALIDATE` dispatch, manifest/runtime identity persistence, demo
  exclusion, and registered non-Megaplan pipelines such as `epic-blitz` and
  `writing-panel-strict`.
- `docs/arnold/megaplan-artifact-manifest.md`
  Create or update a golden artifact manifest for migrated Megaplan runs,
  including expected files and schema keys for proceed, review-needs-rework, and
  execute failure/resume paths. Cover `review.json`, `finalize.json`,
  `final.md`, `execution_audit.json`, receipt metrics, warrant source refs, and
  any renamed equivalents.
- `tests/arnold/pipeline/native/`
  Add minimal compiler/runtime fixtures required to lock the Megaplan shape.

## Verifiable Completion Criterion

- Canonical Megaplan is authored as a composition of native workflows and steps,
  not as a flat stage list with hidden graph-era orchestration.
- Each Megaplan subworkflow has a stable ID, declared inputs, and declared
  outputs; parent workflows interact with child workflows through that declared
  interface rather than ambient state reach-through.
- The critique/revise loop records loop iteration identity in a way compatible
  with the M0 path rules.
- `megaplan run` and `arnold pipelines describe/run` still resolve the canonical
  Megaplan pipeline through the native-first contract.
- Existing Megaplan native behavior remains green for the core scenario set:
  proceed, iterate/revise, tiebreaker, escalation, execute/review, human-gated
  continue, and stop/abort.
- `tests/test_pipeline_run_cli.py` compatibility cases relevant to Megaplan and
  registered Megaplan-family pipelines remain green or are deliberately updated
  with a documented compatibility decision.
- Stage-name aliases keep existing profile slots, override targets, status
  payloads, and legacy cursors working while stable IDs become authoritative.
- The Megaplan artifact manifest is produced and tested against at least the
  proceed, review-needs-rework, and execute failure/resume paths.
- The milestone produces `docs/arnold/megaplan-composition-handoff.md`, listing
  every temporary Megaplan-specific compiler/runtime path with file references
  and whether M2-M5 must generalize or delete it.
- Every temporary Megaplan-specific compiler/runtime path listed in the handoff
  is mechanically findable with a shared marker such as
  `TEMPORARY_MEGAPLAN_ONLY`, so M3 can verify removal rather than relying on
  human comparison alone.
- Before M2 begins, at least one non-Megaplan aspirational example from M0 runs
  through the same compiler/runtime paths introduced for Megaplan. If an M1 path
  only works for Megaplan's shape, it is generalized immediately or marked
  `BLOCKING` in the handoff and must be resolved before M3.

## Risks And Blockers

- Megaplan is the highest-risk workflow because it exercises loops, gates,
  overrides, execution, review, artifacts, and resume.
- A superficially clean nested declaration can still break route labels,
  envelope joins, artifact ownership, or human-gate resume.
- Do not hide missing general support behind Megaplan-only compatibility shims;
  this epic is explicitly moving away from shims.
- M1 must not bless a weaker interface than M0. If Megaplan needs a feature not
  covered by M0, update the contract explicitly before landing the migration.

## Dependencies

- Depends on M0 and completion of the native-python-pipelines-completion epic.
