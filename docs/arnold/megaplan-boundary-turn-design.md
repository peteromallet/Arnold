# Megaplan Boundary Turn Design

## Purpose

Megaplan already has a partial clean boundary for model-produced structured
outputs: the harness writes a scratch template such as `finalize_output.json`,
the worker fills that exact file, and the handler validates/promotes the result
into canonical artifacts such as `finalize.json`.

This note proposes making that pattern the general boundary for every
model-controlled transition. The target is a small transaction abstraction:
the model may edit harness-provided draft files, but only the harness may
promote validated output into durable artifacts, state, history, receipts, and
next-step routing.

BoundaryTurn governs model-output capture and plan-directory canonical
promotion. It is not a rollback mechanism for external workspace mutations.
The execute phase can edit the target repository before any plan artifact is
promoted; BoundaryTurn can make those effects explicit, evidenced, and
resumable, but it cannot make them atomic.

## Current Facts

The current implementation has three relevant pieces already in place:

- `arnold_pipelines/megaplan/template_registry.py` registers template coverage
  for structured phases. Major JSON phases use `file_fill`; `execute` is
  `batch_assembly`; `plan` and `revise` are `markdown_exempt`; tiebreaker
  substeps are `subloop_exempt`; prep/feedback/loop variants remain
  `deferred`.
- `arnold_pipelines/megaplan/handlers/structured_output.py` implements shared
  scratch-file classification and promotion for JSON: expected-path-only reads,
  missing/unmodified fallback, modified-invalid hard failure for file-fill
  workers, and unknown-key stripping.
- Prompt builders already exist for the main structured phases:
  `critique_output.json`, `critique_evaluator_output.json`,
  `gate_output.json`, `finalize_output.json`, `review_output.json`, and an
  execute scaffold used for registry parity rather than single-file promotion.

The remaining inconsistency is that this scratch-file contract is JSON-phase
specific. Markdown stages, execute batches, review/rework loops, gate reprompts,
tiebreakers, subpipelines, and state transitions still close their boundaries
through handler-specific code, `auto.py` policy, workflow graph conditions, and
ad hoc artifact naming.

## Proposed Abstraction

Introduce a first-class `BoundaryTurn`: a transaction around one
model-controlled stage boundary.

Core types:

```python
@dataclass(frozen=True)
class BoundarySpec:
    phase_identity: str
    draft_kind: Literal["json", "markdown", "batch", "subpipeline"]
    template_builder: Callable[..., BoundaryDraft] | None
    validator: BoundaryValidator
    promoter: BoundaryPromoter
    canonical_targets: tuple[str, ...]
    route_policy: RoutePolicy | None = None
    fallback_policy: FallbackPolicy = FallbackPolicy.legacy_recovery

@dataclass(frozen=True)
class BoundaryDraft:
    paths: tuple[Path, ...]
    seed_hashes: Mapping[Path, str]
    attempt: int
    iteration: int
    parent_turn_id: str | None = None

@dataclass(frozen=True)
class BoundaryCapture:
    status: Literal["missing", "unmodified", "filled", "invalid"]
    payload: Mapping[str, Any] | str | None
    raw_worker_output: Mapping[str, Any] | str | None
    diagnostics: tuple[BoundaryDiagnostic, ...] = ()

@dataclass(frozen=True)
class PromotionResult:
    artifact_delta: tuple[Path, ...]
    state_delta: Mapping[str, Any]
    external_side_effects: tuple[ExternalEffectRef, ...] = ()
    observability_events: tuple[EventRef, ...] = ()
    phase_result: Mapping[str, Any] | None = None
    receipts: tuple[Receipt, ...] = ()
    workflow_transition: WorkflowTransition | None = None
```

Fallback policy must be explicit:

- `legacy_recovery` preserves today's JSON scratch behavior: expected draft path
  wins, missing/unmodified scratch may fall back to recovered worker payload,
  modified-invalid plus file-fill instruction fails hard, worker/model-seam
  recovery runs before classification.
- `inline_when_missing` falls back only when no draft was actually present. An
  unmodified draft is a diagnostic, not the same thing as no file tools.
- `strict_file_fill` accepts only the expected draft path. Wrong-path writes and
  inline payloads do not count.
- `inline_only` has no draft-file requirement but still validates before
  canonical promotion.

The API should be intentionally small:

```python
turn = BoundaryTurn.open(spec, plan_dir=plan_dir, state=state)
prompt = turn.render_prompt(base_prompt)
worker = run_worker(prompt)
capture = turn.capture(worker)
validated = turn.validate(capture)
result = turn.promote(validated)
```

Only `promote()` may write plan-directory canonical artifacts, mutate
Megaplan state, append history, emit receipts, or select the next workflow
transition. Execute and other mutating phases must register external side
effects separately and attach evidence to the promotion result.

## Lifecycle

1. The handler or runtime opens a `BoundaryTurn` from `StepContract` plus the
   template registry entry.
2. The harness writes one or more draft files under the plan directory.
3. The prompt names the exact draft paths and states that canonical-path writes
   do not count.
4. The worker runs.
5. Worker/provider recovery runs before boundary classification in
   `legacy_recovery` mode. Hermes tool-markup extraction, empty-response retry,
   phase payload reconstruction, `model_seam` recovery, phase normalizers, and
   compatibility projection remain upstream of `BoundaryTurn.capture()`.
6. The turn captures only expected draft paths and records raw worker output.
7. Capture is classified as `missing`, `unmodified`, `filled`, or `invalid`.
8. Validation runs before state or canonical artifacts are touched.
9. Harness-side effects that are part of the boundary, such as finalize baseline
   capture or execute quality checks, are recorded as `ExternalEffectRef`
   entries. They are not assumed to roll back.
10. Promotion writes canonical artifacts, receipts, state delta, history, and the
   transition decision in an ordered, fail-closed sequence with resumable
   checkpoints. True atomicity is not assumed for target-repository mutations,
   subprocess side effects, tests, or provider calls.

If a harness-level check blocks promotion but must route the run elsewhere, the
handler returns a route result rather than a normal `PromotionResult`. Finalize
baseline selection failure is the important example: it writes gate/feedback
artifacts, rewinds state to critique/revise flow, and records the failure before
the next phase is selected.

## Drafts Versus Canonical Artifacts

Draft files are model-editable proposal surfaces:

- JSON drafts may contain placeholders, empty arrays, stable IDs, and
  model-fill-only fields.
- Markdown drafts may contain required headings, TODO markers, checklist
  anchors, or section skeletons.
- Batch drafts may be keyed by batch slot, task IDs, or fanout item IDs.
- Subpipeline drafts are scoped below the parent turn and do not directly
  advance parent state.

Canonical artifacts are harness-owned records declared by
`BoundarySpec.canonical_targets`. In Megaplan those include files such as
`plan_vN.md`, `critique_vN.json`, `gate.json`, `finalize.json`, `final.md`,
`execution_batch_N.json`, `execution.json`, `review.json`, `phase_result.json`,
and `state.json`. Draft paths and canonical targets must be disjoint, and no
canonical path should appear in a model-fill template.

A direct model write to a canonical artifact is not a valid boundary output. It
should either be ignored, as the JSON scratch helper does today, or recorded as
a boundary violation diagnostic. It should never be promoted by virtue of being
present at the canonical path.

## Validation Rules

Validation is fail-closed before state mutation.

For JSON:

- Parse only the expected draft file.
- Require a JSON object unless the spec explicitly allows another shape.
- Strip or reject unknown top-level keys according to the phase policy.
- Validate against the model-fill schema first.
- Run phase-specific semantic validators second.
- Add harness-computed fields only during promotion.

For Markdown:

- Read only the expected Markdown draft path.
- Validate required headings, section order, task IDs, success-criteria
  structure, and forbidden placeholders.
- Validate references to prior artifacts where applicable.
- Promote to canonical Markdown only after structure passes.

For batches:

- Validate each child draft independently.
- Promote child outputs into batch artifacts only after per-child validation.
- Run a reducer validation before updating aggregate artifacts such as
  `execution.json`.
- Treat target-repository edits, test runs, timeout recovery, and quality gates
  as external side effects that must be recorded before aggregate promotion.

For subpipelines:

- Each child is a full `BoundaryTurn` with its own draft, validator, and
  child-scoped promoter. Child turns never write parent artifacts or mutate
  parent state.
- The reducer is a separate turn whose payload contains the decision,
  child-evidence refs, route, and state-delta proposal.
- Prior-turn canonical artifacts required by the reducer, such as `gate.json`
  for tiebreaker, are passed as read-only evidence refs.
- Parent state advances only during reducer promotion, which also applies flag
  registry mutations, writes audits as observability events, and records
  receipts in checkpointed order.

## Stage Coverage

| Stage | Current boundary | BoundaryTurn target |
| --- | --- | --- |
| `prep` and prep subphases | Multi-step triage/research/distill behavior writes `prep.json`, `prep_dossier.md`, and `prep_metrics.json`; may pause for human clarification. | Keep deferred at first; later model prep as a multi-artifact boundary preserving clarify-gate semantics. |
| `plan` | Worker returns structured payload containing Markdown plus metadata; handler writes `plan_vN.md` and `plan_vN.meta.json`. | Do not switch directly to Markdown-only. First wrap the existing structured payload; only later consider a Markdown draft if metadata parity is preserved. |
| `revise` | Same structured-payload shape as plan, plus prior-plan/gate/critique context and flag updates. | Preserve structured metadata, plan versioning, delta tracking, and flag behavior before adding any Markdown draft surface. |
| `critique` | JSON scratch file already shared | Wrap existing `promote_scratch()` behavior in `BoundaryTurn`. |
| `critique_evaluator` | JSON scratch file already shared | Wrap existing evaluator-specific validation; keep empty `flag_verifications` behavior. |
| `gate` | JSON scratch file plus reprompt reuse | Model each attempt as a `BoundaryTurn`; reuse the same draft path for reprompt attempts when compatibility requires it. Intermediate reprompts validate without canonical promotion. |
| `finalize` | JSON scratch file promotes to multiple finalize artifacts | Wrap existing behavior; promote `finalize.json`, `final.md`, `contract.json`, `user_actions.md`, and `finalize_snapshot.json`; keep harness-computed `validation`, capability claims, and baseline cache behavior outside the draft. |
| `execute` | Execute-specific batch artifacts, project mutations, blocked-task retry, timeout recovery, `finalize.json` updates, audit output, and reducer. | Add child `BoundaryTurn`s for `execution_batch_N.json`; reducer turn promotes `execution.json`, while external side effects and resumable checkpoints remain explicit. |
| `review` | JSON scratch file plus rework routing and optional parallel/extreme fanout | Single-worker review wraps scratch promotion. Parallel/extreme review is a child-subpipeline reducer whose merged payload feeds the same finalize-review outcome path. |
| `feedback` | Markdown-ish/deferred behavior | Defer unless feedback becomes load-bearing; otherwise add a Markdown draft. |
| `tiebreaker` | Subloop/exempt behavior | Keep child-scoped subpipeline turns; parent promotes only the final tiebreaker decision. |

## Multi-Stage Semantics

Loops are not special files. They are repeated turns with explicit
`iteration`/`attempt` metadata.

Gate reprompts:

- Use the same draft path when the existing handler semantics require a full
  replacement response.
- Capture the seed before each attempt.
- Intermediate attempts call validation only. Only the final attempt promotes
  `gate.json` and `gate_carry.json`; PROCEED-to-ITERATE auto-downgrade remains
  gate-handler logic before canonical writes.
- Treat modified-invalid drafts as hard failures for file-tool workers.

Review rework:

- A single-worker review boundary produces either a validated done decision or
  validated rework items.
- Parallel review is a subpipeline boundary: per-check child turns and the
  criteria-verdict side-unit feed a reducer turn. The reducer preserves
  concerned task IDs, deterministic-check grounding, flag IDs, infrastructure
  failure signals, and criteria verdicts before verdict normalization.
- Rework launches later turns; the review draft itself does not mutate execute
  artifacts.
- Transition-policy denial can conditionally re-promote `review.json` and write
  `transition_decision_review_done.json` inside the same review boundary.

Execute batches:

- Each batch is a child turn whose canonical target is `execution_batch_N.json`.
- The aggregate reducer turn validates and writes `execution.json`.
- Batch numbering remains stable through resume by preserving the existing
  task-ID-to-slot mapping.
- Project mutations happen during child turns and must be recorded as external
  side effects with evidence paths, commands, and affected task IDs.
- Per-batch `finalize.json` updates are harness-owned side effects of child
  turns; the reducer reads that mutated state when building `execution.json`.
- Per-batch tier routing and active-step session-key rotation remain child-turn
  harness actions, not model output.
- Blocked-task resets, prerequisite blocks, baseline-unavailable checkpoints,
  timeout recovery, and review-skipped stubs remain execute-specific policy.

Subpipelines:

- Child turns are scoped under a parent turn ID.
- Child artifacts are evidence; parent state changes only via the subpipeline
  reducer.
- Versioned child runs map to `BoundaryDraft.iteration`; the reducer aggregates
  the expected iterations for the same parent turn.

## Migration Plan

1. Wrap `handlers/structured_output.py` with a thin `BoundaryTurn` facade for
   existing JSON phases. Do not change artifact names.
2. Convert `critique`, `critique_evaluator`, `gate`, `finalize`, and `review`
   handlers to call the facade while preserving their phase-specific validators.
3. Add `BoundarySpec` entries that replace the registry mode strings over time.
   Keep `TemplateRegistration` as compatibility metadata during the migration.
4. Wrap `plan` and `revise` as structured-payload boundaries first, preserving
   `plan_vN.md` and `plan_vN.meta.json`. Consider Markdown draft files only
   after metadata parity is proven.
5. Add execute child turns for batch artifacts, then a reducer turn for
   `execution.json`.
6. Add subpipeline child turns for tiebreaker.
7. Move state/history/receipt emission behind ordered promotion checkpoints so
   a successful worker output cannot advance state without the required
   canonical artifacts and recorded external effects.
8. Add tests for every stage table row above, including wrong-path writes,
   unmodified drafts, invalid drafts, direct canonical writes, and resume.

## Non-Goals

- Do not replace existing canonical artifact names.
- Do not force every phase into JSON.
- Do not remove phase-specific validators.
- Do not hide execute/review/gate special cases behind generic code.
- Do not make fallback behavior more permissive than today.
- Do not move neutral Arnold `ContractResult` or Step-IO envelope semantics into
  Megaplan-specific boundary code.
- Do not attempt to make target-repository mutations transactional.
- Do not move worker/provider recovery behavior into handlers if it belongs in
  the worker or model seam.
- Do not run boundary capture/classification before Hermes parsing and
  model-seam recovery have completed under `legacy_recovery`.
- Do not move `_apply_gate_outcome`, `_resolve_review_outcome`,
  transition-policy evidence checks, or auto-driver route derivation into
  `BoundaryTurn`.

## Risks

- Over-generalizing could erase meaningful phase behavior, especially execute
  batch reduction, review rework, and gate reprompts.
- Fallback from draft files to inline payloads can preserve bad behavior if it
  is allowed after a worker was explicitly instructed to edit a draft.
- Markdown validation can become either too weak to matter or too strict for
  useful planning prose.
- Ordered promotion is harder than current handler-local writes because state,
  artifacts, receipts, and history must move together with resumable failure
  points.
- Subpipeline scoping needs care so child artifacts do not accidentally advance
  parent state.
- Plan/revise can lose metadata if treated as Markdown-only outputs too early.
- Worker-side recovery can conflict with strict expected-path semantics unless
  the compatibility policy is explicit.
- Treating `PromotionResult.workflow_transition` as authoritative would bypass
  state-driven `workflow_next()` re-derivation and evidence-policy denials.

## Worker Compatibility

BoundaryTurn must coexist with the current worker and model-seam behavior rather
than bypassing it.

Hermes already:

- Creates scratch templates from `TemplateRegistration`.
- Appends file-fill instructions when file tools are available.
- Falls back to inline JSON when file tools are not available.
- Rewrites scratch templates for retry attempts.
- Parses model text output, assistant-message JSON, reasoning-tag JSON, and some
  wrong-path JSON as provider recovery.
- Reconstructs some execute and gate payloads when models leave templates empty.
- Routes parsed output through `model_seam.capture_step_output` for schema audit
  and recovery.

The clean boundary should define which recovery paths are legacy-compatible and
which are strict. A useful policy split is:

- `strict_file_fill`: only the expected draft path counts; wrong-path writes are
  diagnostics or hard failures.
- `legacy_recovery`: expected draft path wins, but existing worker/model-seam
  recovery may supply fallback payloads for known flaky providers.
- `inline_when_missing`: fall back to inline payload only when no draft exists;
  an unmodified seeded draft remains a diagnostic.
- `inline_only`: no draft file is required; validation still happens before
  canonical promotion.

The first migration should preserve current behavior by using
`legacy_recovery` for existing phases, then tighten individual phases once tests
prove no provider path regresses.

## Generalization Boundary

BoundaryTurn should become a reusable Arnold recipe only at the mechanics layer.
Megaplan can supply Megaplan-specific specs, validators, promoters, and
canonical artifact names, but the generic surface should not import
`template_registry.py`, `step_contracts.py`, or Megaplan state classes.

A non-Megaplan pipeline author should be able to adopt the pattern by defining:

- a `BoundarySpec` with draft paths, canonical targets, fallback policy, and
  validator/promoter implementations;
- a draft-kind implementation that can seed, classify, and validate the model's
  editable surface;
- a worker/runtime adapter that injects exact draft paths into the prompt or
  node payload;
- a promoter that maps `PromotionResult.artifact_delta` to artifact events,
  `state_delta` to node/workflow state, observability events to the runtime
  journal, and `workflow_transition` to the caller's route proposal.

For example, a simple `draft -> tighten -> emit` jokes pipeline could open a
Markdown BoundaryTurn for `draft_output.md`, validate required headings and
absence of placeholders, then promote only to `joke_v1.md` after validation.
Wrong-path writes to `joke_v1.md` would be diagnostics, not accepted output.

## Preservation Checklists

Before migrating a stage to BoundaryTurn, its tests must prove the following
stage-specific behavior remains intact.

### Prep

- Triage/research/distill orchestration still writes `prep_triage.json`,
  per-area research outputs, `prep.json`, `prep_dossier.md`, and
  `prep_metrics.json`.
- The skip path remains compatible with downstream plan prompts.
- Blocking open questions still move the run to human clarification when
  `prep_clarify` is enabled.
- Doc/creative prep prompt variants still select the correct output shape.

### Plan And Revise

- The worker payload remains structured, with Markdown plan text plus metadata.
- `plan_vN.md` and `plan_vN.meta.json` are both preserved.
- Questions, assumptions, success criteria, imported decision criteria, test
  blast radius, plan versions, and structure validation survive promotion.
- Revise preserves prior-plan delta tracking, note consumption receipts,
  cache-hit guards, gate-transition validation, carried blast radius, and flag
  updates.

### Gate

- `gate_signals_vN.json`, `gate.json`, `gate_carry.json`, and `last_gate`
  updates are preserved.
- Invalid or empty recommendation fallback remains available where current
  behavior requires it.
- Reprompt attempts reuse the same scratch path and require a complete
  replacement response.
- Canonical `gate.json` and `gate_carry.json` are written once, after the final
  valid attempt and any auto-downgrade logic.
- No-progress and max-iteration termination still work.
- Debt registry writes, flag events, tiebreaker validation, and
  `STATE_BLOCKED` versus `STATE_GATED` distinctions remain intact.

### Finalize

- `finalize.json`, `final.md`, `contract.json`, `user_actions.md`,
  `finalize_snapshot.json`, capability claims, baseline cache, scoped baseline
  selection, and execution baseline behavior are preserved.
- Harness-computed `validation` remains outside the model-fill draft.
- Baseline capture is recorded as a harness-side effect with command/timing
  evidence; `baseline.json` remains a harness-owned cache artifact.
- Finalize-to-revise feedback still writes `gate.json`, `gate_carry.json`, and
  `finalize_revise_feedback.json` when the finalize validation path requests
  another planning pass.

### Execute

- Child batch turns preserve stable `execution_batch_N.json` numbering and
  resume mapping from task IDs to batch slots.
- Project mutations are recorded as external side effects; they are not assumed
  to roll back.
- Approval gates, mutating preflight, tier routing, timeout recovery, quality
  gates, blocked-task reset, prerequisite blocks, partial resume,
  `execution_audit.json`, trace output, `finalize.json` updates, and
  skipped-review stub generation still work.

### Review

- Single-worker scratch promotion and extreme parallel-review merge both remain
  supported.
- Review infrastructure failure detection, empty-approved-review backfill,
  verdict merge into finalize projection, maker stop, transition-policy denial
  artifacts, rework caps, receipts, flag updates, and `final.md` rewrites remain
  intact.
- Parallel review reducer preserves per-check `concerned_task_ids`,
  deterministic-check evidence, and flag ID provenance.
- Transition-policy denial and conditional `review.json` re-promotion happen in
  the same review boundary.

### Feedback

- Keep feedback outside the first BoundaryTurn migration. The current auto path
  maps to `feedback workflow`, which is scaffold/interactive behavior rather
  than ordinary model-output promotion.

### Tiebreaker

- The run/decide pair continues to read `gate.json`, launch the tiebreaker
  orchestrator, consume latest `tiebreaker_researcher*.json` and
  `tiebreaker_challenger*.json`, write `tiebreaker_decisions.json`, record
  audits, mutate the flag registry, and select human/replan/revise states.
- Child researcher/challenger turns reject direct writes to canonical
  tiebreaker artifacts.
- Reducer promotion validates child evidence and `gate.json` refs before
  writing decisions or mutating the flag registry.

## Open Questions

- Should direct canonical writes be ignored silently, recorded as diagnostics,
  or treated as hard failures for file-tool workers?
- Should Markdown drafts live at stable paths such as `plan_output.md`, or
  versioned paths such as `plan_v3_output.md`?
- Should `TemplateRegistration.mode` be replaced entirely by `BoundarySpec`,
  or retained as a prompt/template-only registry?
- Which deferred phases are actually load-bearing enough to justify draft
  boundaries in the first migration?
- Where should ordered promotion checkpoints live: handler layer,
  `PlanRepository`, or the native runtime executor?
- Should tiebreaker reducer reprompts reuse the same draft path like gate, or
  write new versioned reducer attempts?

## Recommended First Slice

The smallest useful implementation is not a rewrite. Build `BoundaryTurn` as a
facade over the existing JSON scratch helper, then migrate one low-risk phase
such as `critique_evaluator` and one high-value phase such as `finalize`.

Success criteria:

- No artifact names change.
- Existing JSON template tests continue to pass.
- Direct canonical writes are still not accepted as model output.
- Modified invalid scratch files still fail for Hermes/file-tool workers.
- The facade records enough metadata to support loops, batches, and Markdown
  later: phase, attempt, iteration, expected draft path, canonical targets,
  validator, and promotion result.
- The facade preserves worker-side recovery under an explicit compatibility
  policy instead of silently tightening all provider behavior at once.
