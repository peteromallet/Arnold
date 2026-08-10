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

Do not start this milestone until
`.megaplan/initiatives/native-python-pipelines-completion/chain.yaml` has
completed through M7 and the native-first completion branch is clean.

## Files To Change And Instructions

- `arnold_pipelines/megaplan/workflows/workflow.py`
  Rework the canonical Megaplan declaration into compositional units. Split the
  top-level workflow into explicit nested native workflows where the domain has
  real boundaries: planning/prep, critique/revise loop, gate/tiebreaker handling,
  finalize/execute/review, and any human-gated continuation path. Every
  subworkflow must use explicit stable IDs and declared inputs/outputs from the
  M0 contract.
- `arnold_pipelines/megaplan/workflows/planning.py`
  Keep the package builder pointing at the migrated canonical workflow and
  record any compatibility shell/projection behavior that remains.
- `arnold_pipelines/megaplan/workflows/components.py`
  Remove product-level `handler_ref` carriers for report-owned semantics or
  classify retained handlers as pure phase bodies in the carrier table.
- `arnold_pipelines/megaplan/pipeline.py`
  Keep this facade aligned with the migrated workflow and prove CLI/package
  registration resolves through it to the live workflow source.
- `arnold_pipelines/megaplan/native_runner.py`
  If this path exists in the live checkout, keep runner behavior stable while
  dispatching the compositional Megaplan workflow. If it does not exist, the
  source-path reconciliation table must name the current live equivalent or
  classify the reference as stale before implementation starts. Remove any
  special-case stage-order assumptions that the new workflow structure makes
  obsolete.
- `arnold_pipelines/megaplan/native_hooks.py`
  If this path exists in the live checkout, preserve Megaplan-specific hook
  behavior while making child workflow completion, suspension, and envelope
  joining explicit. If it does not exist, the source-path reconciliation table
  must name the current live equivalent or classify the reference as stale
  before implementation starts. No hidden graph fallback semantics. Lock the
  existing hook details with unit tests: override priority
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
  Add the scenario manifest required by the alignment audits:
  prep blocking questions and resume-clarify; imported criteria in declared
  plan outputs; tiebreaker `pick`, `escalate`, and `replan`; finalize task
  generation, scoped/full baseline selection, missing-scoped-baseline fallback,
  `user_actions.md`, before/after execute actions, and synthetic
  before-execute gate; approve, deny, cancel, resume, bare no-review-to-done,
  non-review robustness with deferred must criteria to human verification;
  below-cap review rework, at-cap deterministic blocker escalating through a
  declared recoverable-block/control route, at-cap cosmetic-only
  force-proceed/done, and infra failure retry-to-review.
- `docs/arnold/megaplan-artifact-manifest.md`
  Create or update a golden artifact manifest for migrated Megaplan runs,
  including expected files and schema keys for proceed, review-needs-rework, and
  execute failure/resume paths. Cover `review.json`, `finalize.json`,
  `final.md`, `execution_audit.json`, receipt metrics, warrant source refs, and
  any renamed equivalents.
- `tests/arnold/pipeline/native/`
  Add minimal compiler/runtime fixtures required to lock the Megaplan shape.
- `docs/arnold/megaplan-source-path-reconciliation.md`
  Create or update a launch-gating table before implementation starts. It must
  identify the live canonical source (`arnold_pipelines/megaplan/workflows/workflow.py`,
  `planning.py`, `components.py`, and `pipeline.py` facade), installed package
  import path, CLI/auto-drive entrypoints, and any stale future-looking
  `arnold/pipelines/...` references retained only as migration targets.
- `docs/arnold/megaplan-semantics-carrier-table.md`
  Create a row-by-row carrier table for every formerly hidden report semantic:
  canonical workflow source, declared policy, or retained pure phase body. Each
  retained handler needs file references, purity classification, and the
  source-invariant test that proves it does not own routing, loop exits,
  fanout, retry, suspension, override dispatch, or implicit state transition.

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
- The source-path reconciliation table exists before workflow edits land and
  proves that package registration, CLI, auto-drive, and tests inspect the same
  live canonical workflow source.
- Before workflow edits land, the milestone produces a doctrine proof stating
  which artifacts are source authority, compiled manifest/runtime output, and
  `native_program` compatibility dispatch. Any stale `arnold/pipelines/...`
  reference must be classified as migration target, compatibility alias, or dead
  path before implementation starts.
- The semantics carrier table exists and covers every matrix row touched by
  this milestone.
- No report row is marked `implemented` by M1 unless the row has wrapper-
  detection conformance in this milestone. Otherwise status remains pending
  implementation evidence until M2 source-invariant checks and M6 structural
  conformance/mutation gates pass.
- The milestone produces `docs/arnold/megaplan-composition-handoff.md`, listing
  every temporary Megaplan-specific compiler/runtime path with file references
  and whether M2-M5 must generalize or delete it.
- Every temporary Megaplan-specific compiler/runtime path listed in the handoff
  is mechanically findable with a shared marker such as
  `TEMPORARY_MEGAPLAN_ONLY`, so M3 can verify removal rather than relying on
  human comparison alone.
- Every temporary compiler/runtime path listed in the handoff is marked
  `BLOCKING` unless M2/M3 must remove or generalize it before any affected row
  can become `implemented`.
- Any report row that depends on a `TEMPORARY_MEGAPLAN_ONLY` compiler/runtime
  path remains non-conformant until M3 proves the behavior through neutral
  native fixtures and removes or reclassifies the temporary path.
- Before M2 begins, at least one non-Megaplan aspirational example from M0 runs
  through the same compiler/runtime paths introduced for Megaplan. If an M1 path
  only works for Megaplan's shape, it is generalized immediately or marked
  `BLOCKING` in the handoff and must be resolved before M3.

## Native Representation Alignment

- Matrix rows owned or affected: Prep clarification gate; Plan artifact/version metadata; Critique skip on bare robustness; Adaptive critique evaluator retry; Parallel critique lenses with fan-in; Bounded critique/gate/revise loop; Gate preflight and payload normalization; Gate signal building and reprompt; Gate flag/debt/fallback handling; Tiebreaker researcher/challenger path; Human decision/suspension; Finalize fallback routes; Dependency-aware execute batches; Execute approval/no-review/deferred-human gates; Execute/review/rework loop; Review parallel checks/fan-in; Review infrastructure retry and cap outcomes; Override full action surface; Timeout/deadline policy; Model routing by phase/task complexity; Runtime-list iteration; Dynamic parallel map; Typed loop outcomes or break/continue; Auto-drive/event/liveness transitions; Trace-only native shadow topology; Handler topology extraction/purity audit; Behavior parity with existing Megaplan; Source readability.
- Expected status change: composition-owned rows should move from `enabled` planning status toward implementation evidence, except any explicitly deferred platform durability rows. M1 may not mark a report row `implemented` unless it also lands wrapper-detection conformance for that row; otherwise implementation status waits for M2 validator/source-invariant checks and M6 structural conformance/mutation gates.
- Proof artifacts: source excerpts from canonical Megaplan workflow, source-path reconciliation table, per-row semantics carrier table, rendered topology with untaken branches, handler inventory, artifact manifest, D1/D5/D6/D8/D10 scenario goldens, override matrix, and `megaplan run`/`arnold pipelines` compatibility tests.
- False-pass guard: wrapping old handlers in native nodes is not enough. The milestone must fail if `critique`, `gate`, `tiebreaker`, `execute`, `review`, or `override` are single handler-backed stages that still own product routing.
- Doctrine gate: M1 is the first real proof of the final Megaplan authoring
  doctrine. It must prove compositional source owns report semantics and that
  manifests/native shells are derived artifacts, not parallel semantic owners.
- Deferrals: durable DB waits, broker enforcement, worker leases, and production reconcile remain platform-owned, but M1 must leave explicit suspension/effect hooks for them.
- Canonical source paths/imports: every proof must identify the actual canonical workflow source used by CLI, auto-drive, and package registry.

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
