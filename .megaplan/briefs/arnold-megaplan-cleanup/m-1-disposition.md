# M-1: Disposition Manifest And Parity Gates

## Outcome

Prepare the Arnold/Megaplan cleanup for implementation by producing a mechanically enforceable package-disposition manifest and parity-gate plan. This sprint must not move code. It should leave the repo with clear inputs for later sprints: what moves where, at what granularity, under which import/string gates, and which current behaviors must be preserved.

## Scope

In:
- Write `docs/arnold/package-disposition.md`.
- Classify every tracked `megaplan/**/*.py` source into exactly one disposition row, excluding generated/cache artifacts.
- Use `granularity` values `directory`, `file`, `symbol`, or `split`.
- Add child rows for each `split-required` directory before any later move can be inferred.
- Cover known hybrid zones at file or symbol level: `_pipeline/`, `orchestration/`, `execute/`, `runtime/`, `observability/`, `store/`, `workers/`, `drivers/`, each `pipelines/*` package, `cli/arnold.py`, `cli/status_view.py`, `control_interface.py`, `auto.py`, `_core/workflow.py`, and `profiles/__init__.py`.
- Use YAML as the machine-readable source of truth and generate or maintain a Markdown review view from it.
- Add a source-coverage validation script or documented command proving every tracked Python source maps to exactly one row.
- Produce a parity-gate list and mark each item as already-tested, needs-new-smoke-test, or static-gate-only.
- Trace `Pipeline.run_phase`, `auto.py` planning dispatch, `_core/workflow.py` resume defaults, `control_interface.py`, and `profiles/__init__.py` as directed by the chain `prep_direction`.

Out:
- No file moves.
- No import rewrites.
- No runtime behavior changes.
- No compatibility shim implementation.
- No plugin VM, remote registry, signing system, package manager, or broad platform buildout.

## Locked Decisions

- Arnold is the package, platform, and plugin runtime.
- Megaplan is Arnold's built-in robust planning and execution plugin.
- The cleanup plan to follow is `docs/arnold/arnold-megaplan-cleanup-plan.md`.
- Physical relocation of the production plugin to `arnold/pipelines/megaplan/` waits until discovery, dispatch, resource resolution, profile loading, and legacy-alias routing can support it. M-1 itself moves no code.
- Profiles are scoped to target pipeline stage keys. Arnold owns generic loading/inheritance/agent-spec validation; plugins own metadata semantics.
- The manifest source of truth is YAML; Markdown is for review/readability.
- The coverage script is in scope because it validates the manifest and moves no production code.
- Required manifest row fields: `source`, `target`, `granularity`, `disposition`, `reason`, `blockers`, `allowed_imports`, `forbidden_imports`, `vocabulary_owned`, `string_policy`, `extraction_prerequisite`, `first_extraction_unit`, and `tests_gates`.
- Valid dispositions: `arnold-core`, `arnold-service-interface`, `arnold-adapter`, `arnold-shared-leaf`, `megaplan-plugin`, `product-app`, `legacy-hold`, `delete-merge`, and `split-required`.
- `chain.yaml` and `docs/arnold/arnold-megaplan-cleanup-plan.md` are authoritative for this epic. Older sizing and gap docs remain useful evidence but do not override the current chain split.
- Every configurable seam classified in the disposition manifest must answer: where the setting is declared, how it inherits, how it can be overridden, and who owns its meaning. A supported setting must have an effective value or an explicit unset/unsupported state.
- Runtime settings classification must cover precedence, scoped inheritance, child-operation settings, nested subpipeline propagation, dry-run source reporting, and validation for unknown stage keys, impossible timeout pairs, unsupported isolation modes, invalid worker caps, and settings for undeclared stages.

## Required Outputs

- Which modules are `arnold-shared-leaf` versus `arnold-service-interface`?
- Which parity behaviors already have adequate tests, and which need new smoke tests?
- Which string policies should become future static gates versus plugin-local exceptions?

## Constraints

- Keep the manifest specific enough to prevent horizontal rename churn.
- Every row must identify vocabulary ownership: stage keys, phase keys, state keys, decision keys, override actions, event kinds, profile slots, env vars, artifact/path names.
- Import gates must be derivable from disposition rows.
- String gates must cover old CLI command literals, `.megaplan` path conventions, cloud wrapper commands, and `MEGAPLAN_*` env vars.
- Do not generalize Megaplan policy into Arnold to make a row cleaner.
- Generic Arnold carriers must not silently default to Megaplan behavior, planning identity, Megaplan phase names, or Megaplan state assumptions.
- No horizontal package relocation by directory name. Every future move must be file-level or symbol-level justified by the disposition manifest.

## Done Criteria

- `docs/arnold/package-disposition.yaml` and `docs/arnold/package-disposition.md` exist, or the sprint documents why a single file satisfies both machine and review needs.
- Every tracked `megaplan/**/*.py` source is covered by exactly one row or an explicit generated/cache exclusion.
- `split-required` directories have child rows before any move can be inferred.
- The manifest distinguishes Arnold runtime/service/adapters/shared leaves from Megaplan plugin/product policy.
- The manifest includes import policy and string policy per row or row group.
- The coverage script/command passes.
- The parity gate list covers auto liveness, phase-result freshness, review rework loops, override fallback and guardrails, resume phase args and rollback, feedback, tiebreaker, execute/review policy, chain PR behavior, bakeoff routing, cloud wrapper compatibility, completion contracts, non-Megaplan fanout, typed ports, pause/resume behavior, `SKILL.md` lookup, and override-edge dispatch.
- The output recommends the next milestone and explicitly calls out the M2a/M2b capability-seam split.

## Touchpoints

- `docs/arnold/arnold-megaplan-cleanup-plan.md`
- `docs/arnold/arnold-megaplan-subagent-review-synthesis.md`
- `docs/arnold/arnold-abstraction-vetting-synthesis.md`
- `docs/arnold/megaplan-plugin-clean-gap.md`
- `docs/arnold/megaplan-plugin-clean-codex-assessment.md`
- `megaplan/`
- `tests/`

## Anti-Scope

- Do not start M0 implementation.
- Do not move or rename code.
- Do not fix unrelated bugs.
- Do not create compatibility shims except to specify required migration paths.
