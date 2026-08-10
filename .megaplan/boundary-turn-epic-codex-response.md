Reading additional input from stdin...
2026-06-30T23:09:47.442110Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/.agents/skills/enrich-upload-external-workflows/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.137.0
--------
workdir: /Users/peteromalley/Documents/Arnold
model: gpt-5.5
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019f1acb-bb46-7440-a6b2-e814640e399c
--------
user
# Codex subagent brief: BoundaryTurn end-to-end epic shaping

Working directory: `/Users/peteromalley/Documents/Arnold`.

You are a Codex subagent asked to shape an end-to-end Megaplan epic. Do not edit
files. Read the relevant docs and return a concrete epic plan that another
agent can write into `.megaplan/initiatives/<slug>/`.

## Required inputs to read

- `docs/arnold/megaplan-boundary-turn-design.md`
- `docs/arnold/megaplan-boundary-turn-load-bearing-questions.md`
- `.megaplan/boundary-turn-lbq/results/_report.json`
- The individual `.megaplan/boundary-turn-lbq/results/*.txt` files as needed.
- `/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/arnold/pipelines/megaplan/data/_codex_skills/megaplan-prep/SKILL.md`
- Existing chain examples under `.megaplan/initiatives/*/chain.yaml`, only enough to match local format.

## Goal

Design the full epic that builds BoundaryTurn end-to-end, not just the first
JSON facade sprint. Use the `megaplan-prep` rubric explicitly:

- Size the work into sprint-sized megaplans, each roughly <= two weeks of human
  work.
- Give each milestone a self-contained brief title, outcome, scope, locked
  decisions, open questions, constraints, done criteria, touchpoints, and
  anti-scope.
- Score overall plan difficulty per milestone and select profile/robustness/
  depth/vendor.
- Explain where prep is needed and provide `prep_direction` text.
- Preserve the principle that BoundaryTurn is a promotion-time abstraction, not
  a worker parser, route engine, or phase-policy replacement.

## Required epic coverage

The epic must carry the design from first foundation to end-state:

1. Conservative JSON facade over existing scratch behavior.
2. Ordered promotion/checkpoint/receipt semantics.
3. Plan/revise structured-payload boundary without metadata loss.
4. Gate reprompt semantics and route-policy preservation.
5. Finalize multi-artifact promotion, baseline side-effect recording, and
   finalize-to-revise route.
6. Execute child batch turns plus aggregate reducer, side-effect evidence, resume
   mapping, tier routing, and `finalize.json` child updates.
7. Review single-worker plus parallel/extreme child reducer, infra failure,
   transition-policy denial, rework caps, flag provenance, and conditional
   `review.json` re-promotion.
8. Tiebreaker/subpipeline child turns plus reducer, `gate.json` evidence refs,
   versioned iterations, audits, and flag-registry mutation checkpoints.
9. General Arnold recipe/protocols so non-Megaplan pipeline authors can adopt
   the draft/capture/validate/promote pattern without importing Megaplan
   registries.
10. Final conformance/docs/acceptance gate proving no stage functionality was
   lost and the recipe is reusable.

## Output format

Return only Markdown, under 4500 words, with:

1. `Epic Recommendation`: slug, one-paragraph north star, whether this should be
   an epic and why.
2. `Milestones`: a table with label, title, profile, robustness, depth, vendor,
   prep yes/no, dependencies, and one-sentence purpose.
3. `Milestone Briefs`: one subsection per milestone with self-contained brief
   content. These should be concrete enough to paste into `.md` brief files.
4. `Chain YAML Sketch`: valid-looking YAML matching local examples.
5. `Risk Notes`: the top risks that should be called out in the epic.

Be opinionated. Avoid hedging. If you split differently from the numbered
coverage above, explain why in the milestone purpose.
codex
I’ll use the `megaplan-prep` guidance directly and keep this to read-only shaping work. I’m going to inspect the design docs, LBQ report, and a few existing chain examples to match the local epic format.
exec
/bin/zsh -lc "sed -n '1,220p' .megaplan/boundary-turn-lbq/results/_report.json" in /Users/peteromalley/Documents/Arnold
exec
/bin/zsh -lc "sed -n '1,260p' docs/arnold/megaplan-boundary-turn-load-bearing-questions.md" in /Users/peteromalley/Documents/Arnold
exec
/bin/zsh -lc "sed -n '1,240p' docs/arnold/megaplan-boundary-turn-design.md" in /Users/peteromalley/Documents/Arnold
 succeeded in 0ms:
{
  "briefs_dir": ".megaplan/boundary-turn-lbq/briefs",
  "default_model": "deepseek:deepseek-v4-pro",
  "failed_count": 0,
  "isolation": "threads",
  "max_tokens": 65536,
  "max_workers": 10,
  "model_map": [],
  "output_dir": "/Users/peteromalley/Documents/Arnold/.megaplan/boundary-turn-lbq/results",
  "project_dir": "/Users/peteromalley/Documents/Arnold",
  "stopped_by_signal": false,
  "succeeded_count": 10,
  "sum_agent_seconds": 638.374,
  "task_timeout_s": 1800,
  "tasks": [
    {
      "brief": "/Users/peteromalley/Documents/Arnold/.megaplan/boundary-turn-lbq/briefs/01_scope_and_atomicity.md",
      "elapsed_s": 64.15040533314459,
      "error": null,
      "error_class": null,
      "finish_reason": null,
      "finished_at": "2026-06-30T22:37:57Z",
      "meta_file": "/Users/peteromalley/Documents/Arnold/.megaplan/boundary-turn-lbq/results/01_scope_and_atomicity.meta.json",
      "model": "deepseek:deepseek-v4-pro",
      "pid": 64962,
      "raw_result_keys": [
        "api_calls",
        "base_url",
        "cache_read_tokens",
        "cache_write_tokens",
        "completed",
        "completion_tokens",
        "cost_source",
        "cost_status",
        "estimated_cost_usd",
        "final_response",
        "input_tokens",
        "interrupted",
        "last_prompt_tokens",
        "last_reasoning",
        "media_cost_lines",
        "media_cost_source",
        "media_cost_status",
        "messages",
        "model",
        "output_tokens",
        "partial",
        "prompt_tokens",
        "provider",
        "reasoning_tokens",
        "response_previewed",
        "total_tokens"
      ],
      "response_chars": 7472,
      "response_file": "/Users/peteromalley/Documents/Arnold/.megaplan/boundary-turn-lbq/results/01_scope_and_atomicity.txt",
      "started_at": "2026-06-30T22:36:53Z",
      "status": "ok",
      "stem": "01_scope_and_atomicity",
      "task_timeout_s": 1800,
      "tool_calls": 38
    },
    {
      "brief": "/Users/peteromalley/Documents/Arnold/.megaplan/boundary-turn-lbq/briefs/02_plan_revise_payloads.md",
      "elapsed_s": 51.98640204197727,
      "error": null,
      "error_class": null,
      "finish_reason": null,
      "finished_at": "2026-06-30T22:37:45Z",
      "meta_file": "/Users/peteromalley/Documents/Arnold/.megaplan/boundary-turn-lbq/results/02_plan_revise_payloads.meta.json",
      "model": "deepseek:deepseek-v4-pro",
      "pid": 64962,
      "raw_result_keys": [
        "api_calls",
        "base_url",
        "cache_read_tokens",
        "cache_write_tokens",
        "completed",
        "completion_tokens",
        "cost_source",
        "cost_status",
        "estimated_cost_usd",
        "final_response",
        "input_tokens",
        "interrupted",
        "last_prompt_tokens",
        "last_reasoning",
        "media_cost_lines",
        "media_cost_source",
        "media_cost_status",
        "messages",
        "model",
        "output_tokens",
        "partial",
        "prompt_tokens",
        "provider",
        "reasoning_tokens",
        "response_previewed",
        "total_tokens"
      ],
      "response_chars": 6767,
      "response_file": "/Users/peteromalley/Documents/Arnold/.megaplan/boundary-turn-lbq/results/02_plan_revise_payloads.txt",
      "started_at": "2026-06-30T22:36:53Z",
      "status": "ok",
      "stem": "02_plan_revise_payloads",
      "task_timeout_s": 1800,
      "tool_calls": 26
    },
    {
      "brief": "/Users/peteromalley/Documents/Arnold/.megaplan/boundary-turn-lbq/briefs/03_worker_recovery_policy.md",
      "elapsed_s": 104.74689829116687,
      "error": null,
      "error_class": null,
      "finish_reason": null,
      "finished_at": "2026-06-30T22:38:37Z",
      "meta_file": "/Users/peteromalley/Documents/Arnold/.megaplan/boundary-turn-lbq/results/03_worker_recovery_policy.meta.json",
      "model": "deepseek:deepseek-v4-pro",
      "pid": 64962,
      "raw_result_keys": [
        "api_calls",
        "base_url",
        "cache_read_tokens",
        "cache_write_tokens",
        "completed",
        "completion_tokens",
        "cost_source",
        "cost_status",
        "estimated_cost_usd",
        "final_response",
        "input_tokens",
        "interrupted",
        "last_prompt_tokens",
        "last_reasoning",
        "media_cost_lines",
        "media_cost_source",
        "media_cost_status",
        "messages",
        "model",
        "output_tokens",
        "partial",
        "prompt_tokens",
        "provider",
        "reasoning_tokens",
        "response_previewed",
        "total_tokens"
      ],
      "response_chars": 10840,
      "response_file": "/Users/peteromalley/Documents/Arnold/.megaplan/boundary-turn-lbq/results/03_worker_recovery_policy.txt",
      "started_at": "2026-06-30T22:36:53Z",
      "status": "ok",
      "stem": "03_worker_recovery_policy",
      "task_timeout_s": 1800,
      "tool_calls": 48
    },
    {
      "brief": "/Users/peteromalley/Documents/Arnold/.megaplan/boundary-turn-lbq/briefs/04_state_routing_policy.md",
      "elapsed_s": 64.41523004206829,
      "error": null,
      "error_class": null,
      "finish_reason": null,
      "finished_at": "2026-06-30T22:37:57Z",
      "meta_file": "/Users/peteromalley/Documents/Arnold/.megaplan/boundary-turn-lbq/results/04_state_routing_policy.meta.json",
      "model": "deepseek:deepseek-v4-pro",
      "pid": 64962,
      "raw_result_keys": [
        "api_calls",
        "base_url",
        "cache_read_tokens",
        "cache_write_tokens",
        "completed",
        "completion_tokens",
        "cost_source",
        "cost_status",
        "estimated_cost_usd",
        "final_response",
        "input_tokens",
        "interrupted",
        "last_prompt_tokens",
        "last_reasoning",
        "media_cost_lines",
        "media_cost_source",
        "media_cost_status",
        "messages",
        "model",
        "output_tokens",
        "partial",
        "prompt_tokens",
        "provider",
        "reasoning_tokens",
        "response_previewed",
        "total_tokens"
      ],
      "response_chars": 5970,
      "response_file": "/Users/peteromalley/Documents/Arnold/.megaplan/boundary-turn-lbq/results/04_state_routing_policy.txt",
      "started_at": "2026-06-30T22:36:53Z",
      "status": "ok",
      "stem": "04_state_routing_policy",
      "task_timeout_s": 1800,
      "tool_calls": 44
    },
    {
      "brief": "/Users/peteromalley/Documents/Arnold/.megaplan/boundary-turn-lbq/briefs/05_gate_preservation.md",
      "elapsed_s": 57.74600737495348,
      "error": null,
      "error_class": null,
      "finish_reason": null,
      "finished_at": "2026-06-30T22:37:50Z",
      "meta_file": "/Users/peteromalley/Documents/Arnold/.megaplan/boundary-turn-lbq/results/05_gate_preservation.meta.json",
      "model": "deepseek:deepseek-v4-pro",
      "pid": 64962,
      "raw_result_keys": [
        "api_calls",
        "base_url",
        "cache_read_tokens",
        "cache_write_tokens",
        "completed",
        "completion_tokens",
        "cost_source",
        "cost_status",
        "estimated_cost_usd",
        "final_response",

 succeeded in 0ms:
# BoundaryTurn Load-Bearing Questions

## Context

This note records the load-bearing questions for
`docs/arnold/megaplan-boundary-turn-design.md`. Each question has a reviewed
answer based on an independent DeepSeek Pro subagent check, so implementation
planning should use this file rather than conversation memory.

## Questions And Reviewed Answers

### 1. What exactly is the scope of BoundaryTurn?

**Question:** Does BoundaryTurn govern only model-output capture and plan-dir
artifact promotion, or does it also promise atomicity for external workspace
mutations?

**Answer:** BoundaryTurn governs model-output capture and plan-dir canonical
promotion. It must not promise rollback for target-repository edits, test runs,
provider calls, subprocesses, or other external effects. Execute must record
external side effects with evidence and resumable checkpoints.

**DeepSeek check:** Sound, but the doc must say why rollback is not the goal.
The safe invariant is that BoundaryTurn prevents phantom canonical claims and
state advancement without evidence; it does not undo real workspace mutation.

### 2. How should plan and revise fit?

**Question:** Should plan and revise become Markdown draft boundaries, or must
they remain structured payload boundaries first?

**Answer:** They must remain structured payload boundaries first. Current
plan/revise outputs contain Markdown plus metadata, and promotion writes both
`plan_vN.md` and `plan_vN.meta.json`. Markdown-only drafts are a later option
only if metadata parity is proven.

**DeepSeek check:** This is load-bearing. The metadata at risk includes
questions, assumptions, success criteria, imported decision criteria, changed
surfaces, test blast radius, plan-version deltas, note-consumption receipts,
cache-hit guards, carried blast radius, flag updates, and validation summaries.

### 3. What happens to worker recovery paths?

**Question:** Can strict expected-path capture replace Hermes/model-seam
recovery immediately?

**Answer:** No. Existing phases should start under a `legacy_recovery` policy:
expected draft path wins, but known worker/model-seam fallbacks remain available
until tests prove a stricter policy is safe. BoundaryTurn needs explicit
fallback policies: `strict_file_fill`, `legacy_recovery`, `inline_when_missing`,
and `inline_only`.

**DeepSeek check:** The recovery cascade must run before boundary
classification under `legacy_recovery`. Hermes tool-markup extraction,
empty-response retry, execute/gate payload reconstruction, model-seam recovery,
phase normalizers, compatibility projection, and current `promote_scratch`
semantics are all load-bearing. Missing and unmodified drafts must remain
distinct diagnostics.

### 4. Who owns routing and state transitions?

**Question:** Can BoundaryTurn reduce next routing to a generic string or state
delta?

**Answer:** No. BoundaryTurn may return a validated workflow transition result,
but routing must remain policy-aware. Gate, review, and execute depend on
robustness settings, blocking classes, phase results, auto-driver behavior,
operator overrides, and recovery policies.

**DeepSeek check:** `workflow_transition` is a proposal, not a command. The
auto-driver re-derives routes from state, and transition policy can deny a
handler's intended move. BoundaryTurn must not absorb `_apply_gate_outcome`,
`_resolve_review_outcome`, or review-done evidence gating.

### 5. What must gate preserve?

**Question:** Can gate be reduced to `gate_output.json` -> `gate.json`?

**Answer:** No. BoundaryTurn can standardize gate capture/promotion, but gate
must preserve `gate_signals_vN.json`, `gate_carry.json`, `last_gate`, invalid
recommendation fallback, full-replacement reprompts, no-progress and
max-iteration termination, debt writes, flag events, tiebreaker validation, and
blocked/gated state distinctions.

**DeepSeek check:** Gate's reprompt loop is the risky edge. Intermediate
attempts should validate but not promote. `gate.json` and `gate_carry.json`
should be written once after the final attempt and any PROCEED-to-ITERATE
auto-downgrade.

### 6. What must finalize preserve?

**Question:** Is finalize just `finalize_output.json` -> `finalize.json`?

**Answer:** No. Finalize also produces `final.md`, `contract.json`,
`user_actions.md`, `finalize_snapshot.json`, capability claims, baseline/cache
behavior, scoped baseline selection, execution baseline, and sometimes
finalize-to-revise feedback artifacts. The model-fill draft must not own
harness-computed `validation`.

**DeepSeek check:** Finalize needs explicit multi-artifact mapping. Baseline
capture is a heavyweight harness side effect and must be recorded as such.
Baseline-selection failure is a route-to-revise path that writes gate/feedback
artifacts rather than a normal promotion.

### 7. What is the execute shape?

**Question:** Can execute use the same single-draft pattern as JSON phases?

**Answer:** No. Execute needs child turns for `execution_batch_N.json` and a
reducer turn for `execution.json`. It must preserve stable batch numbering,
resume mapping, target-repo mutations, approval/preflight, tier routing,
timeout recovery, quality gates, blocked-task reset, prerequisite blocks,
`finalize.json` updates, audit/trace outputs, and skipped-review stubs.

**DeepSeek check:** Confirmed. The important nuance is that child batch turns
can mutate the target repo and update `finalize.json` before aggregate
`execution.json` exists. Per-batch tier routing and active-step session keys
are child-turn harness behavior, not model output.

### 8. What is the review shape?

**Question:** Does BoundaryTurn cover review if it wraps `review_output.json`?

**Answer:** Only for the simple path. Review also has parallel/extreme review
merges, infrastructure-failure detection, empty-approved backfill, verdict
merge into finalize projection, maker stop, transition-policy denial artifacts,
rework caps, receipts, flag updates, and `final.md` rewrites.

**DeepSeek check:** The parallel/extreme path is not a single scratch file. It
needs child per-check turns and a reducer turn before the shared
`_finalize_review_outcome` flow. The reducer must preserve deterministic-check
evidence, task IDs, flag IDs, infra-failure signals, transition-policy denial,
and conditional `review.json` re-promotion.

### 9. How do tiebreakers and subpipelines fit?

**Question:** Is parent/child BoundaryTurn enough for tiebreaker?

**Answer:** Directionally yes, but only if child outputs are treated as
evidence and parent state advances solely through a reducer decision. The
tiebreaker path must preserve `gate.json` input, researcher/challenger outputs,
`tiebreaker_decisions.json`, audits, flag registry mutation, and
human/replan/revise state choices.

**DeepSeek check:** The design was under-specified. Child researcher/challenger
runs need real draft/capture/validate/promote boundaries, not direct canonical
writes. The reducer must receive `gate.json` as an evidence ref, validate child
artifacts, checkpoint flag-registry mutation, and model versioned runs via
iteration metadata.

### 10. Is this a recipe other pipeline authors can follow?

**Question:** Does BoundaryTurn standardize enough to be reusable without
flattening stage semantics?

**Answer:** Yes if the recipe standardizes boundary mechanics, not stage
meaning. Authors should define a spec, build drafts, prompt expected paths,
capture, validate, semantically check, promote, emit state/history/receipts,
and test wrong-path, invalid, unmodified, and resume behavior.

**DeepSeek check:** As originally written, no: it was too Megaplan-specific to
be an Arnold-wide recipe. The design now needs a generalization boundary:
generic `BoundarySpec`/validator/promoter protocols, no dependency on
Megaplan's template registry, canonical targets declared by the spec, runtime
event/journal mapping, and at least one non-Megaplan example.

## Subagent Review Synthesis

All ten DeepSeek subagents completed. The strongest conclusion is that
BoundaryTurn is robust only if it is a promotion-time abstraction, not a
replacement for worker parsing, phase validators, route policy, or recovery
logic.

The implementation plan should therefore start conservative:

1. Wrap existing JSON scratch behavior with `legacy_recovery`.
2. Prove byte-for-byte or behavior-for-behavior parity for each migrated phase.
3. Tighten individual phases only after provider-path tests show strict capture
   is safe.
4. Treat execute, parallel review, and tiebreaker as child-turn/reducer
   structures, not as single-draft phases.
5. Keep Megaplan-specific policy in handlers and transition policy while
   making the draft/capture/validate/promote recipe reusable.

## Cross-Cutting Acceptance Tests

- Direct canonical writes do not count as valid model output.
- Missing or unmodified drafts fall back only under an explicit policy.
- Modified invalid drafts fail under strict/file-fill policy.
- Worker/model-seam recovery runs before `legacy_recovery` boundary
  classification.
- Unknown JSON keys are stripped or rejected according to phase policy.
- Plan/revise preserve metadata and `plan_vN.meta.json`.
- Execute records external side effects instead of pretending they are atomic.
- Gate reprompts retain complete-replacement semantics and promote canonical
  gate artifacts once.
- Parallel review uses child turns plus reducer behavior.
- Tiebreaker reducer validates child evidence and checkpointed flag mutation.
- Promotion never advances Megaplan state without the required canonical
  artifacts and recorded side effects.
- A non-Megaplan pipeline can use BoundaryTurn without importing Megaplan
  registries or artifact names.

 succeeded in 0ms:
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

exec
/bin/zsh -lc "sed -n '1,260p' /Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/arnold/pipelines/megaplan/data/_codex_skills/megaplan-prep/SKILL.md" in /Users/peteromalley/Documents/Arnold
 succeeded in 0ms:
---
name: megaplan-prep
description: Set up a megaplan run before invoking it — size the work, write the brief, score overall plan difficulty, and choose robustness/depth. Consult before every `python -m arnold.pipelines.megaplan init`.
---

# Megaplan Setup

Three dials decide how to run a sprint:

| | Question | Dial | What it scales | Flag |
|---|---|---|---|---|
| 1 | How model-quality-sensitive is the planning loop? | **Overall plan difficulty** | model quality for plan/revise/finalize | `--profile partnered-3|partnered-4|partnered-5` |
| 2 | What level of process rigor does this need? | **Planning complexity** | `# of calls` | `--robustness` |
| 3 | How deeply does each model need to think? | **Depth** | `tokens/call` | `--depth` (with `--phase-model` as the surgical escape hatch) |

**Always run a megaplan, even for tiny work.** The harness captures the brief, plan, execution, and outcome — that record is worth the few seconds of overhead. `bare` is the floor; there is no "skip megaplan" option.

**Run megaplan inside a subagent by default**, off the main thread — keeping the orchestrating conversation thin while the harness handles its own multi-phase chatter. On-thread is the exception, reserved for when you want to watch each phase live. The subagent is the venue; megaplan is still the harness — never skip megaplan in favor of "just doing it in a subagent."

The dials are independent — work through each one ignoring the others — then weigh the three together holistically. A high tier with low robustness is usually a mismatch; so is a low tier with `max` depth. When the three pull in opposite directions, the work probably needs to be split.

**The dials measure residual complexity, not nominal scope.** Discount for decisions already made; add for unknowns remaining. A spec-shaped brief with everything known lands a tier lower than the same nominal scope arriving as a sketch.

**Defaults to keep in mind:** score the run first; use `--profile partnered-3 --vendor codex` for overall plan difficulty 1–3, `partnered-4` for 4, and `partnered-5` for 5. Keep `--robustness full` and `--depth` unset unless you can name the specific reason to change them. Built-in profiles live in `megaplan/profiles/`; per-user (`~/.config/megaplan/profiles.toml`) and per-project (`<project>/.megaplan/profiles.toml`) TOML overrides win over them.

---

## Sizing and briefing

Two decisions come before the three dials: **how many megaplans you need**, and **what each brief covers**. Get these wrong and the dials can't save the run.

### Size each megaplan to ~2 weeks of work

A megaplan should fit roughly **two weeks of human work** — the time a skilled engineer would take to plan, build, and review the same scope. Wall-clock for the harness itself is unrelated; this is about scope, not duration.

If the work is bigger, **split it into an epic** — a chain of sprint-sized megaplans driven sequentially by `python -m arnold.pipelines.megaplan chain`. Each sprint in the chain gets its own brief, its own overall plan difficulty score, its own profile, and its own retrospective. See the **megaplan-epic** skill for spec format, per-milestone rubric, and end-to-end usage. Cramming a month of work into one plan means the brief drifts, the critique loses focus, and the review can't hold the whole shape in one pass.

Signs you should split:

- Multiple major architectural decisions — each deserves its own sprint.
- Deliverables with different stakes — high-stakes infra warrants its own sprint, at a higher tier; bundling it with cheap work either over-pays for the cheap work or under-protects the expensive part.
- You can't describe the outcome in one or two sentences.

When you split, structure the dependency graph explicitly. Each handoff is a written artifact — schema, API surface, doc — that the next brief can cite. Sprints without that artifact between them are really one sprint pretending to be two.

For high-confidence epic handoffs, use the chain completion manifest feature instead of relying only on prose or chain state. A downstream `chain.yaml` can require a prerequisite chain to be complete with `kind: chain_completed` plus `require_manifest: true`; the prerequisite chain then emits `completion-manifest.json` via `megaplan chain manifest --spec ... --proof-map ...`. The manifest hashes the chain spec, North Star when declared, milestone briefs, and explicit proof artifacts; it also records completed milestone labels, plan names, and review-merge PR metadata when applicable. Downstream launch then rejects missing, stale, or mismatched manifest evidence.

**But: one profile per sprint.** Within a sprint, score the overall planning difficulty for the sprint as a whole. Operational simplicity beats the savings from splitting by difficulty alone. Only split when lower-difficulty work is *substantial* (multiple days) **and** independent. Structure the plan so easier work lives in easier sprints, not interleaved inside harder ones.

### What goes in the brief

**Tightening the brief beats picking a higher tier** — and is usually cheaper. Invest here before anywhere else.

**The brief must be locked in before init** — fully self-contained so the model can run end-to-end without coming back for clarification. The harness snapshots the brief at `init`; later edits to the idea-file are not re-read. If you find yourself wanting to "ask the model" what to do, write that decision down first.

**Store durable briefs in `.megaplan/initiatives/`.** Single-plan ideas live at `.megaplan/initiatives/<slug>/briefs/<slug>.md`. Epics live at `.megaplan/initiatives/<epic-slug>/chain.yaml` with their milestone briefs in the same directory. `.megaplan/plans/` is generated run state; `.megaplan/initiatives/` is the committed input material you hand to `python -m arnold.pipelines.megaplan init` or `python -m arnold.pipelines.megaplan chain start`. Use `python -m arnold.pipelines.megaplan brief new` or `python -m arnold.pipelines.megaplan brief epic` to create the canonical files.

A good brief covers:

1. **Outcome** — what's being delivered, in one or two sentences. The thing a reviewer would check.
2. **Scope** — what's IN, what's OUT, sized to ≤2 weeks of work.
3. **Locked decisions** — architecture, interfaces, libraries, patterns already chosen. Naming them stops the planner from relitigating.
4. **Open questions** — things you don't know yet that the planner needs to resolve. Naming them stops the planner from quietly inventing answers.
5. **Constraints** — performance budgets, security requirements, backward-compat needs, deadlines.
6. **Done criteria** — what "done" looks like: a test that passes, a workflow that completes, a metric below a threshold.
7. **Touchpoints** — which files / modules / surfaces the work touches.
8. **Anti-scope** — explicit "don't touch X" or "don't refactor Y" so the planner doesn't drift into bonus work.

A brief missing #3 or #4 surfaces those gaps as critique flags — better to write them down up front than have the harness rediscover them mid-run.

---

## Dial 1 — Overall Plan Difficulty

> **"How model-quality-sensitive is the planning/revision/adjudication loop?"**

Score the whole plan's residual difficulty from **1 to 5** before choosing the profile. This is not the same as per-task execution complexity: it decides how strong the planning/revision/adjudication loop should be for the run as a whole. Task execution still gets routed later by `finalize` through `tier_models.execute`.

The score is intentionally more granular than the profile map: scores `1`, `2`, and `3` all use `partnered-3`. The extra resolution is for auditability and repeatability, not fake precision. Only move to `partnered-4` or `partnered-5` when the plan itself is model-quality-sensitive.

| Score | Profile | Use when |
|---|---|---|
| `1` | `partnered-3` | Small, local, well-specified work with obvious files and tests. |
| `2` | `partnered-3` | Moderate implementation where patterns are known and failure is easy to detect. |
| `3` | `partnered-3` | Default for real engineering work: some judgment calls, but no unusually hard architecture or validation problem. |
| `4` | `partnered-4` | Hard planning or decomposition: unfamiliar code, cross-system behavior, subtle ordering, import/package topology, or a difficult task-difficulty adjudication problem. |
| `5` | `partnered-5` | Highest-stakes or hardest plans: architecture pivots, production data, security, public contracts, migrations, or failures that could pass tests while causing non-local damage. |

Use these guardrails:

- Do not upscore for size alone. Large repetitive work should split into an epic, raise `--robustness`, or cap execution spend; it should not become `partnered-5` just because there are many edits.
- Raise to `4` for package moves, import graph changes, public re-exports, shared initialization paths, dependency inversion, or other topology work, even when the desired behavior is unchanged.
- Use `5` when a bad plan could still pass local tests while damaging a contract, invariant, migration path, data model, security boundary, or downstream architecture.
- Score the highest plausible planning failure, not the scariest noun. Production data, auth, or schemas do not automatically mean `5` if the actual change is local and well-proven.

When genuinely torn between two scores, choose the lower score and raise `--depth` or `--robustness` first, unless the specific risk is bad task decomposition, bad task-difficulty adjudication, or a bad architecture choice. Those are profile-selection risks.

Use the dials separately:

- Unclear requirements or missing context -> `--with-prep` or higher `--robustness`.
- Need more deliberation from the same planner -> higher `--depth`.
- Need a better model for decomposition/adjudication/architecture -> higher profile.

Always record the choice in the prep output:

```text
Overall plan difficulty: N/5; selected profile: partnered-3|partnered-4|partnered-5; because: <one sentence naming the planning failure being guarded against>.
```

---

## Dial 2 — Planning complexity

> **"What level of process rigor does this need?"**

The `--robustness` flag. Picks how many phases run and how many critique passes happen. The five levels form a coherent process-completeness scale: **bare → light → full → thorough → extreme**.

| Setting | Workflow | When to use |
|---|---|---|
| `bare` | plan → finalize → execute (no prep, no critique, no gate, no review) | **The floor — use this when nothing heavier earns its cost.** Single-file fixes, mechanical changes, tasks you'd otherwise do inline. The 3-phase run captures what you did and why, even when critique would be a no-op. Always preferable to skipping the harness. |
| `light` | plan → critique → revise → finalize → execute (no prep, no gate, no review) | Small/scoped, well-known feature, low blast radius — but you want **one** sense-check pass on the plan before committing. ~5 phases instead of 8. |
| `full` *(default)* | prep → plan → critique → gate → revise → finalize → execute → review; up to 6 critique lenses | Cross-cutting, unfamiliar code, ambiguous brief. **This is almost always perfect for everything.** |
| `thorough` | Same shape as `full`, up to 9 critique lenses + parallel critique | Security, data migration, public API contract — anything where a regression = production incident. **Extremely rare.** You should be able to name the specific stakes that warrant it. |
| `extreme` | `thorough` + parallel review | Both deep critique *and* concurrent review matter. **Vanishingly rare.** Only when the user specifically asks for it. |

Cost scales ~1.5-2× from `light` → `full`, another ~1.3× to `thorough`.

The "critique lenses" counts above are the **static** lens pools used when adaptive critique is **off**. When adaptive critique is **on**, the evaluator selects which lenses fire from the same 9-lens catalog per iteration — the robustness dial no longer fixes a count; the evaluator does (see [`docs/critique.md`](critique.md)). Robustness still governs the surrounding workflow shape (whether `gate`/`review` run, whether prep/parallel critique are forced).

---

## Dial 3 — Depth

> **"How deeply does each model need to think within the tier I picked?"**

Picks the thinking strength of the premium model(s) the tier brought in. Independent of tier and robustness — orthogonal lever. Spelled out in the agent spec after a colon (`claude:low`, `codex:medium`, etc.).

| Pattern | When to use |
|---|---|
| `low` planner / `low` critic | **The default.** The pattern is mechanical, intuition is enough, the codebase is well-known. A lot of work lands here even at tier 3 — premium models at `low` thinking are still substantially smarter than DeepSeek, so the upgrade isn't free but doesn't need to be expensive either. |
| `medium` planner / `low` critic | Brief is clear but the work has real judgment calls. The plan needs deliberation beyond intuition; the critic still doesn't. |
| `high` planner / `low` critic | Brief is long OR codebase is unfamiliar. The planner needs substantial repo-reading and structural reasoning. |
| `xhigh` / `max` planner only | Genuinely novel architectural decision. Use sparingly — most "hard" plans don't actually need this. |

Available strengths: Claude is `low / medium / high / xhigh / max`; Codex is `minimal / low / medium / high`.

**The asymmetry principle:** author phases (plan, revise) can scale all the way up to `max` when the work demands deliberation; sense-check phases (critique, gate, review) plateau at `low` regardless of stakes. A `claude:high` planner + `claude:low` critic is the right shape when the plan needs real thinking — not `claude:medium` everywhere.

Default to `low`; only spend on depth when you can name the specific reason the planner needs to deliberate. "Just in case" doesn't earn the cost.

---

## When the dials turn out wrong — mid-flight escalation

**If a run is struggling, escalate mid-flight rather than letting it grind.** Common signals: the plan keeps missing concerns critique surfaces; revise doesn't resolve the critique's flags; the executor produces work review can't accept; iteration cycles through the same defects without converging. Don't sit through a degenerate run — one wasted phase costs much less than restarting the sprint.

- `python -m arnold.pipelines.megaplan override set-profile --profile NAME --plan ID` — swap profile mid-run. Started on `partnered-3`, hit something gnarlier, escalate to `partnered-4` or `partnered-5` for the remainder.
- `python -m arnold.pipelines.megaplan override set-robustness --robustness LEVEL --plan ID` — same for the planning-complexity dial.
- `python -m arnold.pipelines.megaplan override replan --plan ID` — back up to planning and redo with whatever models / robustness are now active.
- `python -m arnold.pipelines.megaplan override add-note --plan ID --note "..."` — inject guidance into an active plan without restarting any phase. Read by every subsequent phase. The brief is snapshotted at `init`; later edits to the idea-file are NOT re-read, so this is the verb for "I missed something." **`python -m arnold.pipelines.megaplan feedback` is end-of-run rating, not in-flight guidance** — common confusion.

Lean on these instead of inventing more profile names. If you find yourself thinking "I want a profile that's *like* `partnered-3` but with X" — the answer is usually `partnered-3` plus an override, unless it matches the explicit `partnered-4` or `partnered-5` rubric above.

---

## Optional phases (`--with-prep`, `--with-feedback`)

Two narrower levers orthogonal to the three dials. Both off by default.

### Prep (`--with-prep`)

> **"Does the planner need to do explicit research before it can commit to a plan?"**

`prep` is a visible research phase that runs *before* `plan` — the planner explicitly reads external docs, surveys an unfamiliar library, maps an API surface, or disambiguates a vague brief. Enable with `--with-prep`.

**Reach for it when at least one of these is true:**

- **External APIs whose semantics aren't already known** — the planner has to read API docs before deciding what calls to make.
- **Unfamiliar libraries or frameworks** — codebase patterns aren't enough; the planner needs to survey the library's API surface first.
- **Research-heavy briefs** — the work is research-bounded ("figure out how X behaves, then implement").
- **Ambiguous or under-specified requirements** — the planner needs a budget to disambiguate explicitly instead of interleaving with planning.
- **Integration work where target-system behavior must be discovered** — wire formats, error semantics, performance characteristics undocumented in the codebase.

"Prep just in case" doesn't earn its cost. Redundant at `thorough` and `extreme` (those already include prep); the flag's value is at `light` and `full`, where prep is normally skipped.

**Steering prep with `--prep-direction`.** When prep runs (either via `--with-prep` or because robustness is `thorough`/`extreme`), you can hand it explicit guidance about *what* to explore: `python -m arnold.pipelines.megaplan init … --prep-direction "focus on the worker shutdown path; ignore CLI plumbing"`. It's shown to the prep worker as a distinct "User direction for prep" section — steering, not a replacement for the task. Use it when prep would otherwise wander (broad codebase, multiple plausible entry points) or when you want it to skip the obvious file and trace a specific call chain. You can also set or replace it after init with `python -m arnold.pipelines.megaplan prep --direction "…"` before the phase runs, and chain milestones accept `prep_direction:` per milestone. Has no effect if prep is skipped.

### Feedback (`--with-feedback`)

> **"Do you want a per-stage ratings template waiting on disk when the run finishes?"**

`--with-feedback` adds a `feedback` step between `review` and `done` that scaffolds `feedback.md` (a per-stage ratings template) and then completes the plan. Enable with `--with-feedback`.

**Reach for it when at least one of these is true:**

- **You're uncertain whether enough model was used** — there's real ambiguity about whether the tier choice was right, and you want a per-stage record that lets you go back and decide whether to step up (or down) next time.
- **The user specifically requests it.**

The auto driver runs this non-interactively — never blocks on human input, never opens `$EDITOR`. The file is just left on disk. The user fills in `feedback.md` afterward (or ignores it — no reminders, no prompts).

"Feedback just in case" doesn't earn its cost. The template exists to be used; if nobody is going to rate the run, skip the flag.

---

## Notation

Write `profile/robustness/depth`, omit defaults, append modifiers. Order is fixed left-to-right: tier → robustness → depth, matching dial numbers 1 → 2 → 3. The `//` reads as "skip the middle slot — defaults there."

| Shorthand | Meaning |
|---|---|
| `partnered-3` | Overall plan difficulty 1–3, defaults throughout |
| `partnered-4//high` | Overall plan difficulty 4, high depth, default robustness |
| `partnered-3//high @codex +prep` | Overall plan difficulty 1–3, high depth, codex vendor, with prep phase |
| `partnered-5/thorough/high` | Overall plan difficulty 5, thorough, high depth |

Modifier conventions: `@<vendor>` for vendor override, `, critic=<kind>` for critic override, `+prep` to enable prep, `+feedback` to enable feedback. Append modifiers without disturbing the spine.

The shorthand is for recording (sprint notes, brief headers, commit messages), not for the CLI. The actual invocation is still `python -m arnold.pipelines.megaplan init --profile … --robustness … --depth …` — see "Running it" below.

---

## Running it — profile plus the knobs

The invocation has three layers: three flags for the dials, four modifiers for orthogonal toggles, one escape hatch for surgical needs.

### The three dial flags

1. **`--profile`** — `partnered-3`, `partnered-4`, or `partnered-5`, chosen from the overall plan difficulty score.
2. **`--robustness bare|light|full|thorough|extreme`** — `full` is home base.
3. **`--depth low|medium|high|xhigh|max`** — rewrites the effort suffix on author-side claude/codex slots (plan, revise, loop_plan, tiebreaker_*) at the resolved vendor. Critic + mechanical phases plateau at their existing depth (the asymmetry principle). Defaults to whatever the profile sets (usually `:low`). Honored on vendor-locked profiles. Codex caps at `high`; Claude adds `xhigh` and `max`.

### The modifier flags

- **`--vendor claude|codex`** — vendor override where the selected profile exposes premium vendor slots. Defaults to `[defaults].vendor` in `~/.config/megaplan/config.toml` (or `claude` if unset).
- **`--critic cross`** — overrides the critique+review pair to the other premium vendor relative to `--vendor`, when supported by the selected profile.
- **`--deepseek-provider direct`** — keeps canonical DeepSeek v4-pro slots on DeepSeek's direct API. Defaults to `direct`; Fireworks is not a supported DeepSeek route.
- **`--with-prep`** — force the `prep` research phase into the workflow regardless of `--robustness`. Off by default; no-op at `thorough`/`extreme`. See "Optional phases" above.
- **`--prep-direction "…"`** — steering text shown to the prep worker (when prep runs) as a "User direction for prep" section. Points prep at specific files / subsystems / questions to explore. Can also be set or replaced later with `python -m arnold.pipelines.megaplan prep --direction "…"` before the phase runs. No-op if prep is skipped. See "Optional phases" above.
- **`--with-feedback`** — force the `feedback` phase into the workflow regardless of `--robustness`. Scaffolds `feedback.md` (a per-stage ratings template) between `review` and `done`, then completes the plan non-interactively. Off by default. See "Optional phases" above.

### The escape hatch

**`--phase-model phase=spec`**, repeatable. For when `--depth` is too coarse — e.g. bump just `critique` without touching the rest. Most runs don't need it.

For an in-flight plan, `python -m arnold.pipelines.megaplan override set-model --phase PHASE --model MODEL`
updates that phase's persisted `phase_model` entry. If you are switching premium
vendors, pass a full premium spec such as `--model claude:sonnet` or
`--model codex:gpt-5.5`; passing only `--model sonnet` keeps the phase's
currently inferred premium agent and changes only its model token.

Important: `--phase-model critique=...` and `override set-model --phase critique`
pin the critique **phase/orchestrator**. They do not by themselves pin the
per-lens critics chosen by adaptive critique. In the normal adaptive path, a
premium evaluator/director may run first and then dispatch the selected critique
lenses to cheaper DeepSeek/Kimi-style workers; seeing `critique_evaluator` on a
premium model followed by `critique` on Hermes/DeepSeek is expected. Only pin
`execution.critic_model` when you intentionally want to override that adaptive
critic-worker routing.

### The critique == review invariant

exec
/bin/zsh -lc "find .megaplan/initiatives -path '*/chain.yaml' -maxdepth 3 -print | head -12" in /Users/peteromalley/Documents/Arnold
 succeeded in 0ms:
.megaplan/initiatives/workflow-manifest-runtime/chain.yaml
.megaplan/initiatives/agentbox-persistent-machine/chain.yaml
.megaplan/initiatives/step-io-contract/chain.yaml
.megaplan/initiatives/step-io-contract-condensed/chain.yaml
.megaplan/initiatives/native-composition-followup/chain.yaml
.megaplan/initiatives/python-shaped-workflow-authoring/chain.yaml
.megaplan/initiatives/native-platform-followup/chain.yaml
.megaplan/initiatives/arnold-pipeline-friction/chain.yaml
.megaplan/initiatives/aggressive-generalized-pipeline-migration/chain.yaml
.megaplan/initiatives/epic-pipeline-unification/chain.yaml
.megaplan/initiatives/arnold-complete-cleanup-single-root/chain.yaml
.megaplan/initiatives/shannon-stream/chain.yaml

codex
The design and LBQ synthesis already lock the key architectural stance: BoundaryTurn is promotion-time only, with legacy recovery and route-policy preservation staying outside the abstraction. I’m checking the subagent result files now for implementation-level warnings that should affect sprint boundaries.
exec
/bin/zsh -lc "sed -n '241,520p' docs/arnold/megaplan-boundary-turn-design.md" in /Users/peteromalley/Documents/Arnold
 succeeded in 0ms:
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

exec
/bin/zsh -lc "sed -n '1,220p' .megaplan/initiatives/step-io-contract/chain.yaml" in /Users/peteromalley/Documents/Arnold
 succeeded in 0ms:
anchors:
  north_star: NORTHSTAR.md

base_branch: arnold-epic

milestones:
  - label: m0a-contract-result-type
    idea: .megaplan/initiatives/step-io-contract/briefs/m0a-contract-result-type.md
    profile: apex
    robustness: thorough
    depth: high
    notes: "Core ContractResult TYPE both planes import: typed payload + schema_version + status {completed|suspended|failed} + first-class ArtifactRef + Suspension INTERACTION-envelope (kind/display_refs/resume_input_schema/deadline) + generic evidence_refs/authority_level/provenance/freshness. No behavior. Frozen early as shared boundary; Evidence-First imports this only. Type stays small, no 4th status. Designed against a 2nd (evidence-pack) pipeline, not megaplan-only."

  - label: m0b-validator-schema-registry
    idea: .megaplan/initiatives/step-io-contract/briefs/m0b-validator-schema-registry.md
    profile: premium
    robustness: thorough
    depth: high
    notes: "Structural-type-audit validator fn (every field in schema, every type matches) + schema registry with version RETENTION (validate vs schema-in-effect-when-written; schemas versioned/retained, never mutated in place). B5 CUT: full/manifest-by-size split + policy HOOK, NO receipt/sampled profiles. Pluggable content-validators keyed by content_type. Schema versioning supports logical_type + accepted_version_RANGE. Behavioral risk lives here. No enforcement wiring yet."

  - label: m1-compat-chokepoint-shadow-observability
    idea: .megaplan/initiatives/step-io-contract/briefs/m1-compat-chokepoint-shadow-observability.md
    profile: premium
    robustness: thorough
    depth: high
    notes: "Single validation chokepoint at disk-engine seam (read_artifact_json @ plan_repository.py:150); read-lenient/write-strict gated by artifact schema_version; enforce-only-when-both-typed (gradual typing); per-seam off->shadow(log-only)->warn->enforce with violation telemetry (per-seam attribution + why-rejected diagnostics) driving promotion. Dogfood kill-switch: global enforcement-off escape + engine self-validates its OWN artifacts before any seam promotes to enforce. The de-risking core; jury's #1 add."

  - label: m2-data-seam-typed-ports
    idea: .megaplan/initiatives/step-io-contract/briefs/m2-data-seam-typed-ports.md
    profile: premium
    robustness: thorough
    depth: high
    notes: "Wire the dormant typed Ports (arnold/pipeline/types.py:234): produces/consumes on the 9 stages; executor enforces when both sides typed; StepResult carries a typed payload not a free-form Mapping. DEFINES the StepInvocation seam + adapter registry (model adapter SLOT only; unknown kinds fail closed). Ports carry content_type + cardinality {singleton|collection|stream, stream RESERVED} + version-range. Step->step contract goes live, shadow-first per seam, gradually. Co-designed vs the evidence-pack pipeline."

  - label: m3-model-seam-degraded-mode
    idea: .megaplan/initiatives/step-io-contract/briefs/m3-model-seam-degraded-mode.md
    profile: premium
    robustness: thorough
    depth: high
    notes: "CENTERPIECE (over-invested). The MODEL ADAPTER of the m2 StepInvocation seam (not 'the inbound chokepoint'). Two-tier trust (enforced wire-trust + always-on structural audit); render_step_message (data-by-ref + token budget with real per-model tokenizers + media budgets for multimodal); capture_step_output (schema-validate, preserve Codex repair loop). Closed prompt-assembly coverage + single-inbound-chokepoint on the COMBINED model input (not bare prompt). Boundary tripwire fires if the vendored boundary moves. Prove on execute (Hermes-no-structured, riskiest). Degraded modes explicit/bounded/observable/non-authoritative-unless-validated; no worker deadlocks."

  - label: m4-suspension-aware-composition
    idea: .megaplan/initiatives/step-io-contract/briefs/m4-suspension-aware-composition.md
    profile: partnered
    robustness: thorough
    depth: high
    notes: "Make status=suspended first-class in composition: SubloopStep/fan-out check halt_reason and propagate a suspended child UP (today they silently complete it, _pipeline/subloop.py:23-105); define how ContractResults compose/reduce across fan-out/subloop. Suspension = the m0a interaction envelope. Built default = barrier / max-wins reduce; scoped-suspension-propagation + policy-driven reduce are DEFERRED extension points. status enum already lives in m0a."

  - label: m5-migrate-load-bearing
    idea: .megaplan/initiatives/step-io-contract/briefs/m5-migrate-load-bearing.md
    profile: partnered
    robustness: full
    depth: medium
    notes: "Migrate + delete the load-bearing 5 (finalize/critique/review/gate; execute done in m3) onto the contract. Kill _normalize_worker_payload fuzzy key-drift patching; make execute validate_payload batch-relaxation native; preserve _recover_codex_payload fallbacks + critique completeness scoring. Delete old stringly-typed path per-site as migrated."

  - label: m6-migrate-long-tail
    idea: .megaplan/initiatives/step-io-contract/briefs/m6-migrate-long-tail.md
    profile: directed
    robustness: full
    depth: medium
    notes: "Migrate + delete the ~28-site long tail onto the contract. Per-site delete of f-string prompt concat + regex output recovery as each site is migrated. The real win is removing the old seams, not adding a new one."

  - label: m7-authoring-api-enforcement
    idea: .megaplan/initiatives/step-io-contract/briefs/m7-authoring-api-enforcement.md
    profile: premium
    robustness: thorough
    depth: high
    notes: "Make the authoring API's reads/writes ENFORCED: an author declares {input contracts, invocation spec (kind + adapter_config), output contract} and the runtime handles every crossing — 'instruction' demoted to the model adapter's config. Capability declarations verified by `arnold pipeline check`. Seam-4 / the 50-pipelines-overnight unlock. Additive under the planned public authoring API; does not disturb a running chain."

  - label: m8-acceptance-gate
    idea: .megaplan/initiatives/step-io-contract/briefs/m8-acceptance-gate.md
    profile: partnered
    robustness: thorough
    depth: medium
    notes: "Hard acceptance gate: regression of all 4 motivating failures (wrong-typed passes, char->token overflow, first-key-valid parse, suspended-child-silently-completed) + a validation-overhead/concurrency benchmark + a seam-coverage matrix (every spine seam implemented/delegated/out-of-scope) + a 2nd toy pipeline riding the contract as a platform-scale generalization proof. States the SHAPE-not-MEANING limit explicitly (a well-typed lie still passes; structural != semantic). Outbound coverage proof artifact (every validate_payload/parse site catalogued + closure-proven, twin of m3's inbound closure)."

on_failure:
  abort: stop_chain
on_escalate:
  abort: stop_chain
merge_policy: review

driver:
  robustness: thorough
  auto_approve: true
  max_iterations: 80
  poll_sleep: 8.0

exec
/bin/zsh -lc "sed -n '1,220p' .megaplan/initiatives/aggressive-generalized-pipeline-migration/chain.yaml" in /Users/peteromalley/Documents/Arnold
 succeeded in 0ms:
anchors:
  north_star: NORTHSTAR.md

base_branch: main

milestones:
  - label: m0-boundary-lock
    idea: .megaplan/initiatives/aggressive-generalized-pipeline-migration/briefs/m0-boundary-lock.md
    profile: partnered-5
    vendor: claude
    robustness: thorough
    depth: high
    notes: "Protect the generic Arnold substrate before moving more code. Add hard import/string leak gates, inventory blessed primitives, remove/quarantine .megaplan assumptions from arnold.pipeline, and prove evidence_pack stays non-Megaplan."

  - label: m1-neutral-outcome-control
    idea: .megaplan/initiatives/aggressive-generalized-pipeline-migration/briefs/m1-neutral-outcome-control.md
    profile: partnered-5
    vendor: claude
    robustness: thorough
    depth: high
    notes: "First extraction PR: move neutral run outcome/control carrier vocabulary out of Megaplan into Arnold-owned modules, keep compatibility re-exports, and split Megaplan bridge policy from generic control data."

  - label: m2-step-contract-registry
    idea: .megaplan/initiatives/aggressive-generalized-pipeline-migration/briefs/m2-step-contract-registry.md
    profile: partnered-5
    vendor: claude
    robustness: thorough
    depth: high
    notes: "Make Megaplan phase metadata authoritative through StepContract. Derive old schema/capture/normalizer/routing views from one registry before deleting duplicated maps."

  - label: m3-executor-convergence
    idea: .megaplan/initiatives/aggressive-generalized-pipeline-migration/briefs/m3-executor-convergence.md
    profile: partnered-5
    vendor: claude
    robustness: thorough
    depth: high
    notes: "Converge the real production Megaplan walker and the neutral Arnold executor. Move capabilities behind hook interfaces and expose thin run_step/run_pipeline APIs without creating a second runner."

  - label: m4-supervisor-extraction
    idea: .megaplan/initiatives/aggressive-generalized-pipeline-migration/briefs/m4-supervisor-extraction.md
    profile: partnered-5
    vendor: claude
    robustness: thorough
    depth: high
    notes: "Extract generic cross-run orchestration carriers and ladder machinery into arnold.supervisor while keeping chain YAML, Git, PR, profile, robustness, and completion-contract policy in Megaplan."

  - label: m5-oracle-gated-strangler
    idea: .megaplan/initiatives/aggressive-generalized-pipeline-migration/briefs/m5-oracle-gated-strangler.md
    profile: partnered-5
    vendor: claude
    robustness: thorough
    depth: high
    notes: "Turn replay/oracle coverage into milestone gates: fold/WAL equivalence, topology parity, replay oracle, dual-run oracle, artifact parity, and semantic comparison where timestamps/IDs differ."

  - label: m6-runtime-foundation
    idea: .megaplan/initiatives/aggressive-generalized-pipeline-migration/briefs/m6-runtime-foundation.md
    profile: partnered-5
    vendor: claude
    robustness: thorough
    depth: high
    notes: "FOUNDATION (own gate, small change set, outsized blast radius): make the cross-cutting carriers generic FIRST so the runtime extractions above don't silently re-couple. Move the real RunEnvelope (+join algebra) to arnold/runtime/envelope.py (reconciling the shape-incompatible stub); lift a minimal ArnoldError base to arnold/runtime/errors.py (CliError subclasses it, 50+ sites); add an optional RunContext protocol field to the generic StepContext. Megaplan imports these FROM arnold. Both m7 and m8 depend on this."

  - label: m7-agent-runtime-extraction
    idea: .megaplan/initiatives/aggressive-generalized-pipeline-migration/briefs/m7-agent-runtime-extraction.md
    profile: partnered-5
    vendor: claude
    robustness: thorough
    depth: high
    depends_on: m6-runtime-foundation
    notes: "Extract the agent EXECUTION runtime (AIAgent + streaming, tool registry/dispatch, tool-call sandbox, agent contracts) to arnold/agent/ + arnold/runtime/sandbox.py, plus a THIN ProviderPool (key acquisition only — the governor/budget triad stays cohesive in Megaplan and wraps it). Consumes the m6 envelope/error foundation; imports them from arnold, never megaplan. Closes the m0 blind spot: AgentStep is hollow today, so the substrate can't run an agent without Megaplan."

  - label: m8-state-lifecycle-runtime
    idea: .megaplan/initiatives/aggressive-generalized-pipeline-migration/briefs/m8-state-lifecycle-runtime.md
    profile: partnered-5
    vendor: claude
    robustness: thorough
    depth: high
    depends_on: m6-runtime-foundation
    notes: "Extract MECHANISMS not engines: the fcntl-NDJSON event-journal append/read (opaque kind:str, no enum), the lock+atomic-write state helper (megaplan keeps its modes/validators), and a pure fold_journal combinator -> arnold/runtime/. PLUS the generic suspend/resume lifecycle the substrate lacks: Suspension as a Protocol, run_pipeline_resume + resume cursor, and a generic HumanGateStep writing to artifact_root not plan_dir. Durable fix for the no-ground-truth-authority root (state-as-projection)."

  - label: m9-deliberation-pipeline
    idea: .megaplan/initiatives/aggressive-generalized-pipeline-migration/briefs/m9-deliberation-pipeline.md
    profile: partnered-5
    vendor: claude
    robustness: thorough
    depth: high
    depends_on:
      - m7-agent-runtime-extraction
      - m8-state-lifecycle-runtime
    notes: "BOUNDARY-RATIFYING external consumer (OSS-framework goal: a self-built reducer can't validate a public API). Build the Deliberation Pipeline — idea -> Opus load-bearing questions -> HUMAN gate (suspend/resume) -> three layered critique passes (high/mid/low abstraction, fan-out up to 10 each, skeptical synthesis not consensus) -> change report. Genuinely non-planning; forces exactly the features a reducer dodges: human-gate suspend/resume, non-{agent,model,effort} profiles (abstraction level), plan-version lineage via fold, public fan-out, semantic replay. Zero Megaplan imports (proven by the m6 clean-venv import test). Forges the public SPI by demand-pull; every fork/monkeypatch point -> real arnold.* API. Real e2e test required. This is the workflow we refine plans with, productized."

  - label: m10-megaplan-flagship-app
    idea: .megaplan/initiatives/aggressive-generalized-pipeline-migration/briefs/m7-megaplan-flagship-app.md
    profile: partnered-5
    branch: megaplan/m10-megaplan-flagship-app
    vendor: claude
    robustness: thorough
    depth: high
    notes: "Make Megaplan the flagship Arnold app: expose a planning pipeline manifest/build_pipeline, route through generic orchestration where parity is proven. PLUS a vocabulary-decontamination pass (TrustTier->TrustClass, OperationKind.RUN_PHASE->EXECUTE, planning terms out of generic type/field names, binding_map injectable). Names the Typed Step-IO Envelope successor epic but does NOT start it. BOUNDARY-FREEZE DISCIPLINE (OSS goal): deleting deprecated shims / declaring 'this is the public API' waits until the m9 Deliberation Pipeline has actually ratified each extension point — do NOT freeze a framework boundary that only Megaplan + a self-built consumer have exercised. Keep escape hatches until the real consumer validated the cut."

  - label: m11-unified-agent-dispatcher
    idea: .megaplan/initiatives/aggressive-generalized-pipeline-migration/briefs/m11-unified-agent-dispatcher.md
    profile: partnered-5
    branch: megaplan/m11-unified-agent-dispatcher
    vendor: claude
    robustness: thorough
    depth: high
    depends_on:
      - m7-agent-runtime-extraction
      - m8-state-lifecycle-runtime
    notes: "Build the concrete unified dispatcher arnold/agent/dispatcher.py::ArnoldDispatcher implementing dispatch(AgentRequest)->AgentResult over ALL 3 backends — the one piece m7-m10 leave undone (they keep the 3-way run_step_with_worker branch at _impl.py:3108-3320 intact and never implement a concrete dispatcher). DeepSeek KEEPS the full Hermes/AIAgent runtime (NO thin client — locked). Codex/Shannon stay megaplan-resident and are INJECTED as adapters (DI; do not force-move them). Additive + flag-gated (MEGAPLAN_USE_AGENT_DISPATCHER default OFF; run_step_with_worker becomes a shim delegating to dispatch, WorkerResult preserved via the bridge, one-env rollback). Session bookkeeping/routing ledger/retry/fallback stay ABOVE the dispatch call. Done = a non-megaplan caller drives all 3 backends through arnold.agent.dispatch importing only arnold.agent (ratifies the boundary the way m7/m9 do) + flag-on parity + flag-off byte-identical. This is the public arnold.agent execution API the VibeComfy consumer (separate cross-repo follow-up) then ratifies."

on_failure:
  abort: stop_chain
on_escalate:
  abort: stop_chain
merge_policy: auto

driver:
  robustness: thorough
  auto_approve: true
  max_iterations: 100
  poll_sleep: 8.0

exec
/bin/zsh -lc "sed -n '1,220p' .megaplan/initiatives/workflow-manifest-runtime/chain.yaml" in /Users/peteromalley/Documents/Arnold
 succeeded in 0ms:
base_branch: main

anchors:
  north_star: NORTHSTAR.md

milestones:
  - label: m1-baseline-manifest-contract
    idea: .megaplan/initiatives/workflow-manifest-runtime/briefs/m1-baseline-manifest-contract.md
    profile: partnered-5
    vendor: codex
    robustness: thorough
    depth: high
    branch: workflow-manifest-runtime-m1-baseline
    prep_clarify: false
    prep_direction: "Start from native-python-working-tree. Read the committed workflow decision docs and current mainline guardrails, goldens, conformance checks, and salvage candidates needed to freeze the baseline and define WorkflowManifest v1. Do not rely on uncommitted /tmp source material."
    notes: "Freeze behavior and define the durable manifest/kernel contract before any package move or runtime rewrite. Use completed native Python work only as quarry."

  - label: m2-explicit-node-dsl-compiler
    idea: .megaplan/initiatives/workflow-manifest-runtime/briefs/m2-explicit-node-dsl-compiler.md
    profile: partnered-5
    vendor: codex
    robustness: thorough
    depth: high
    branch: workflow-manifest-runtime-m2-dsl
    depends_on:
      - m1-baseline-manifest-contract
    prep_clarify: false
    prep_direction: "Use the M1 manifest contract as fixed input. Focus on arnold.workflow, arnold.patterns, compile-to-manifest, validation, inspect, dry-run, importable hook identity, source spans, and the canonical explicit-node Megaplan shape. Do not implement the runner yet."
    notes: "Build the explicit-node Python data DSL and compiler surface that all later runtime and product work must consume."

  - label: m3-manifest-runner-runtime
    idea: .megaplan/initiatives/workflow-manifest-runtime/briefs/m3-manifest-runner-runtime.md
    profile: partnered-5
    vendor: codex
    robustness: thorough
    depth: high
    branch: workflow-manifest-runtime-m3-runner
    depends_on:
      - m2-explicit-node-dsl-compiler
    prep_clarify: false
    prep_direction: "Treat the M1 manifest and M2 compiler as locked. Build arnold.execution and arnold.kernel runtime behavior around manifests, append-only events, artifact hashes, resume cursors, branch/loop/fanout/retry/subpipeline/generic-suspension semantics, fake backends, and replay."
    notes: "Make manifest execution real before moving Megaplan product code onto it."

  - label: m4-megaplan-product-migration
    idea: .megaplan/initiatives/workflow-manifest-runtime/briefs/m4-megaplan-product-migration.md
    profile: partnered-5
    vendor: codex
    robustness: thorough
    depth: high
    branch: workflow-manifest-runtime-m4-megaplan
    depends_on:
      - m3-manifest-runner-runtime
    prep_clarify: false
    prep_direction: "Use the clean-break end-state as authoritative. Move Megaplan product logic toward arnold_pipelines.megaplan and rewrite canonical Megaplan build_pipeline() as explicit-node data over the manifest runner. Preserve behavior with goldens; do not keep permanent arnold.pipelines.megaplan, top-level megaplan, _pipeline, bridge, native_runner, or native_hooks surfaces."
    notes: "Migrate the load-bearing Megaplan package and canonical planning flow onto the Arnold workflow substrate."

  - label: m5-shipped-pipelines-cli-docs
    idea: .megaplan/initiatives/workflow-manifest-runtime/briefs/m5-shipped-pipelines-cli-docs.md
    profile: partnered-5
    vendor: codex
    robustness: thorough
    depth: high
    branch: workflow-manifest-runtime-m5-pipelines-docs
    depends_on:
      - m4-megaplan-product-migration
    prep_clarify: false
    prep_direction: "After M4, migrate the remaining shipped/example pipelines, CLI workflow commands, docs, scaffolds, and inventory checks to arnold.workflow / arnold.patterns. Keep restricted-Python generator DSL work private/context-only unless needed for tests."
    notes: "Finish user-facing authoring and operator surfaces without reopening the core manifest architecture."

  - label: m6-clean-break-purge-conformance
    idea: .megaplan/initiatives/workflow-manifest-runtime/briefs/m6-clean-break-purge-conformance.md
    profile: partnered-5
    vendor: codex
    robustness: thorough
    depth: high
    branch: workflow-manifest-runtime-m6-purge
    depends_on:
      - m5-shipped-pipelines-cli-docs
    prep_clarify: false
    prep_direction: "Make the clean-break end-state true. Delete obsolete public/native/compatibility surfaces only after inventory, parity, installed-wheel, docs/scaffold, import graph, and golden behavior gates are green. Preserve no permanent shims."
    notes: "Final public API contract cutover and deletion sprint."

  - label: m7-merge-result-conformance
    idea: .megaplan/initiatives/workflow-manifest-runtime/briefs/m7-merge-result-conformance.md
    profile: partnered-5
    vendor: codex
    robustness: thorough
    depth: high
    branch: workflow-manifest-runtime-m7-merge-result-conformance
    depends_on:
      - m6-clean-break-purge-conformance
    prep_clarify: false
    prep_direction: "Run only post-merge release gates on the integrated checkout. Build the wheel from the merge result, rerun installed-wheel conformance and generated-artifact freshness, run scripts/chain_done_gate.py with blockers.json, run scripts/m6_purge_gate.py, and prove deleted files/imports were not resurrected. Do not reintroduce or repair legacy pipeline content here."
    notes: "Blocks final chain completion unless the merged state, not just milestone branches, proves the clean-break contract."

on_failure:
  abort: stop_chain
on_escalate:
  abort: stop_chain
merge_policy: review

driver:
  robustness: thorough
  auto_approve: true
  max_iterations: 120
  poll_sleep: 8.0

exec
/bin/zsh -lc "for f in .megaplan/boundary-turn-lbq/results/*.txt; do printf '\\n### %s\\n' \""'$f"; rg -n "''^(#|##|###|Recommendation|Verdict|Conclusion|Critical|Load-bearing|Implementation|Risk|Acceptance|Test|Preserve|Do not|Must)" "$f" | head -80; done' in /Users/peteromalley/Documents/Arnold
 succeeded in 0ms:

### .megaplan/boundary-turn-lbq/results/01_scope_and_atomicity.txt
5:## 1. Verdict: **Sound**
22:## 2. What functionality would be lost if this scope were wrong
34:## 3. Specific design-doc edits and acceptance tests
36:### Design-doc edits
45:# external_side_effects are recorded evidence of mutations that already
46:# occurred in the target repository. They are NEVER promises of rollback.
47:# They exist so downstream phases (review, finalize, gate) and audits
48:# can inspect what the worker did without re-executing.
55:### Acceptance tests

### .megaplan/boundary-turn-lbq/results/02_plan_revise_payloads.txt
1:## 1. Verdict
7:## 2. Metadata or behavior at risk if switched to Markdown-only
28:## 3. Specific design-doc edits or acceptance tests
30:### Design-doc edits
43:### Acceptance tests to add (migration step 4, line 251)

### .megaplan/boundary-turn-lbq/results/03_worker_recovery_policy.txt
5:## 1. Verdict
17:## 2. Recovery Behavior That Must Remain
21:### A. Hermes-side recovery (must fire *before* BoundaryTurn capture)
31:### B. Model-seam recovery (must remain callable from BoundaryTurn.validate)
39:### C. Handler-side promotion (the current `promote_scratch` semantics)
51:## 3. Design-Doc Edits and Acceptance Tests
53:### Required design-doc edits
84:### Acceptance tests to add before migrating any phase

### .megaplan/boundary-turn-lbq/results/04_state_routing_policy.txt
5:## 1. Verdict
11:## 2. Routing Behavior at Risk
27:## 3. Specific Design-Doc Edits and Acceptance Tests
29:### Edits to `megaplan-boundary-turn-design.md`
43:### Acceptance Tests

### .megaplan/boundary-turn-lbq/results/05_gate_preservation.txt
1:## 1. Verdict
7:## 2. Gate Behavior at Risk
25:## 3. Specific Design-Doc Edits and Acceptance Tests
27:### Edit 1 (lines 213–216, after "reprompt attempts")
33:### Edit 2 (preservation checklist, add to lines 348–358)
37:### Acceptance Tests

### .megaplan/boundary-turn-lbq/results/06_finalize_preservation.txt
1:## 1. Verdict
7:## 2. Finalize Behavior at Risk
17:## 3. Design-Doc Edits and Acceptance Tests

### .megaplan/boundary-turn-lbq/results/07_execute_batches.txt
5:## 1. Verdict
11:## 2. Execute Behavior at Risk
23:## 3. Specific Design-Doc Edits / Acceptance Tests
25:### Design-doc edits
31:### Acceptance tests

### .megaplan/boundary-turn-lbq/results/08_review_parallel_rework.txt
1:## Verdict (Question 8)
7:## Review Behavior at Risk
25:## Specific Design-Doc Edits and Acceptance Tests

### .megaplan/boundary-turn-lbq/results/09_subpipeline_tiebreaker.txt
1:## 1. Verdict
7:## 2. Subpipeline/Tiebreaker Behavior At Risk
23:## 3. Specific Design-Doc Edits and Acceptance Tests
25:### Edits to `megaplan-boundary-turn-design.md`
73:### Acceptance tests to add

### .megaplan/boundary-turn-lbq/results/10_standard_recipe_and_adoption.txt
5:## Question 10: Does BoundaryTurn Provide a Standard Recipe?
7:### 1. Verdict
13:### 2. Where the Recipe Is Too Megaplan-Specific
22:### 3. Where the Recipe Is Too Vague
31:### 4. Specific Design-Doc Edits and Acceptance Tests

codex
## Epic Recommendation

**Slug:** `boundary-turn-end-to-end`

BoundaryTurn should be built as an epic because it changes the model-output boundary for every load-bearing Megaplan stage while deliberately preserving each stage’s existing policy. The north star is: models edit drafts; validators inspect only expected drafts or explicit legacy recovery payloads; harness-owned promotion writes canonical artifacts, state, history, receipts, and route proposals in ordered, resumable steps. BoundaryTurn is not a worker parser, route engine, phase-policy replacement, or rollback system for target-repository mutations.

## Milestones

| Label | Title | Profile | Robustness | Depth | Vendor | Prep | Dependencies | Purpose |
|---|---|---:|---|---|---|---|---|---|
| `m1-json-facade` | Conservative JSON BoundaryTurn Facade | `partnered-5` | `thorough` | `high` | `codex` | yes | none | Wrap current JSON scratch behavior without changing artifacts or recovery semantics. |
| `m2-promotion-checkpoints` | Ordered Promotion, Checkpoints, Receipts | `partnered-5` | `thorough` | `high` | `codex` | yes | `m1` | Make canonical writes/state/history/receipts fail-closed and resumable. |
| `m3-plan-revise-payloads` | Plan/Revise Structured Payload Boundary | `partnered-5` | `thorough` | `high` | `codex` | yes | `m2` | Preserve Markdown plus metadata before considering Markdown draft surfaces. |
| `m4-gate-boundary` | Gate Reprompts and Route Policy Preservation | `partnered-5` | `thorough` | `high` | `codex` | yes | `m2` | Model gate attempts as turns while leaving gate route policy intact. |
| `m5-finalize-boundary` | Finalize Multi-Artifact Promotion | `partnered-5` | `thorough` | `high` | `codex` | yes | `m2` | Preserve finalize artifacts, baseline effects, and finalize-to-revise routing. |
| `m6-execute-boundary` | Execute Child Batches and Aggregate Reducer | `partnered-5` | `thorough` | `high` | `codex` | yes | `m5` | Add child batch turns, reducer promotion, resume mapping, side-effect evidence. |
| `m7-review-boundary` | Review Single/Parallel Reducers and Rework Caps | `partnered-5` | `thorough` | `high` | `codex` | yes | `m6` | Preserve simple review plus parallel/extreme reducer and transition denial behavior. |
| `m8-subpipeline-tiebreaker` | Tiebreaker/Subpipeline Boundary Turns | `partnered-5` | `thorough` | `high` | `codex` | yes | `m4`, `m7` | Make child evidence and reducer promotion the only parent-state advance path. |
| `m9-arnold-recipe` | General Arnold Boundary Protocols | `partnered-4` | `full` | `high` | `codex` | yes | `m8` | Extract reusable draft/capture/validate/promote protocols without Megaplan registries. |
| `m10-conformance-gate` | Final Conformance, Docs, Acceptance Gate | `partnered-4` | `thorough` | `medium` | `codex` | no | `m9` | Prove stage parity, reusable recipe, and no lost Megaplan functionality. |

## Milestone Briefs

### `m1-json-facade` — Conservative JSON BoundaryTurn Facade

**Outcome:** Introduce `BoundaryTurn`, `BoundarySpec`, draft capture, validation, and promotion result types as a thin facade over `handlers/structured_output.py`. Migrate at least `critique_evaluator` and one higher-value JSON phase while preserving behavior.

**Scope:** JSON file-fill only; `legacy_recovery` policy; expected-path capture; missing/unmodified/filled/invalid diagnostics; direct canonical write rejection/diagnostics; compatibility with template registry metadata.

**Locked decisions:** Existing worker/model-seam recovery runs before boundary classification. Current artifact names do not change. Unknown keys follow existing phase policy. BoundaryTurn does not parse provider output itself.

**Open questions:** Whether direct canonical writes are hard failures for all file-tool workers or only diagnostics in legacy mode.

**Constraints:** No stricter fallback behavior until provider-path tests prove it safe.

**Done criteria:** Existing structured-output tests pass; new tests cover wrong path, canonical path, missing, unmodified, invalid, inline fallback, and unknown keys.

**Touchpoints:** `arnold_pipelines/megaplan/handlers/structured_output.py`, `template_registry.py`, JSON phase handlers/tests.

**Anti-scope:** No plan/revise Markdown drafts, execute batches, route-policy rewrites, or state checkpoint refactors.

**Run:** Overall plan difficulty 5/5; `partnered-5/thorough/high @codex`. Prep direction: “Map current structured_output, template registry, worker/model-seam recovery, and JSON phase promotion tests. Identify exact parity assertions before editing.”

### `m2-promotion-checkpoints` — Ordered Promotion, Checkpoints, Receipts

**Outcome:** Move canonical artifact writes, state deltas, history, receipts, and workflow transition proposals behind ordered promotion checkpoints.

**Scope:** Promotion journal/checkpoint API; idempotent resume; artifact-before-state ordering; receipt emission; external side-effect references; promotion-result persistence.

**Locked decisions:** Promotion may record external effects that already happened, never promise rollback. `workflow_transition` is a proposal; transition policy and auto-driver remain authoritative.

**Open questions:** Final checkpoint storage location, with preference for `PlanRepository`/plan-dir owned checkpoint files rather than handler-local ad hoc state.

**Constraints:** Existing handlers must be migratable incrementally.

**Done criteria:** Tests prove state cannot advance without required canonical artifacts; interrupted promotion resumes or fails closed; receipts are not duplicated.

**Touchpoints:** plan repository, state/history writers, receipt code, phase result handling, auto-driver transition evidence.

**Anti-scope:** No behavior changes to gate/review routing decisions.

**Run:** Difficulty 5/5; `partnered-5/thorough/high @codex`. Prep direction: “Trace every canonical artifact/state/history/receipt write in JSON phases and identify the minimum common checkpoint surface.”

### `m3-plan-revise-payloads` — Plan/Revise Structured Payload Boundary

**Outcome:** Wrap plan and revise as structured-payload BoundaryTurns that promote both Markdown and metadata without loss.

**Scope:** Existing worker payload shape; `plan_vN.md`; `plan_vN.meta.json`; questions, assumptions, success criteria, imported decision criteria, changed surfaces, test blast radius, version deltas, note-consumption receipts, cache-hit guards, flag updates.

**Locked decisions:** Do not switch to Markdown-only drafts. Metadata parity is required before any later Markdown surface.

**Open questions:** Whether plan/revise use stable draft paths or payload-only `inline_only` first.

**Constraints:** Versioning and delta tracking must remain byte/behavior compatible where tests exist.

**Done criteria:** Golden tests prove `plan_vN.md` and meta parity for plan and revise; revise still preserves prior-plan deltas, notes, flags, and validation summaries.

**Touchpoints:** plan/revise handlers, prompt builders, plan versioning, metadata writers, flag registry updates.

**Anti-scope:** No Markdown draft validation redesign.

**Run:** Difficulty 5/5; `partnered-5/thorough/high @codex`. Prep direction: “Inventory plan/revise payload fields and all consumers of `plan_vN.meta.json`; build a parity checklist before migration.”

### `m4-gate-boundary` — Gate Reprompts and Route Policy Preservation

**Outcome:** Model each gate attempt as a BoundaryTurn while promoting canonical gate artifacts only once after final valid attempt and auto-downgrade logic.

**Scope:** `gate_output.json`, `gate_signals_vN.json`, `gate.json`, `gate_carry.json`, `last_gate`, complete-replacement reprompts, invalid recommendation fallback, no-progress/max-iteration termination, debt writes, flag events, tiebreaker validation, blocked/gated distinctions.

**Locked decisions:** `_apply_gate_outcome`, transition policy, and auto-driver route derivation stay outside BoundaryTurn.

**Open questions:** Whether reducer-style gate attempts should get per-attempt checkpoint artifacts beyond diagnostics.

**Constraints:** Reprompts reuse the same draft path where current behavior requires full replacement.

**Done criteria:** Tests show intermediate reprompts validate without canonical promotion; final promotion preserves route-policy evidence and carry artifacts.

**Touchpoints:** gate handler, gate prompt, route policy, state transitions, flag/debt registries.

**Anti-scope:** No tiebreaker child-turn implementation yet.

**Run:** Difficulty 5/5; `partnered-5/thorough/high @codex`. Prep direction: “Trace gate attempt lifecycle, reprompt replacement semantics, and every artifact/state mutation from gate output to next route.”

### `m5-finalize-boundary` — Finalize Multi-Artifact Promotion

**Outcome:** Wrap finalize promotion across all finalize-owned artifacts and harness-computed side effects.

**Scope:** `finalize.json`, `final.md`, `contract.json`, `user_actions.md`, `finalize_snapshot.json`, capability claims, scoped baseline selection, baseline cache, execution baseline, validation injection, finalize-to-revise feedback.

**Locked decisions:** Model draft does not own harness-computed `validation`. Baseline capture is an external side effect with command/timing/evidence refs.

**Open questions:** Exact side-effect schema for baseline evidence.

**Constraints:** Baseline-selection failure routes to revise by writing gate/feedback artifacts, not by pretending finalize promoted normally.

**Done criteria:** Tests cover successful multi-artifact promotion, baseline failure route, capability claims, cache reuse, and finalize-to-revise artifacts.

**Touchpoints:** finalize handler, baseline/cache code, contract/user action writers, gate feedback path.

**Anti-scope:** No execute batch migration.

**Run:** Difficulty 5/5; `partnered-5/thorough/high @codex`. Prep direction: “Inventory finalize artifact mapping, baseline side effects, validation injection, and finalize-to-revise route before editing.”

### `m6-execute-boundary` — Execute Child Batches and Aggregate Reducer

**Outcome:** Represent execute as child batch BoundaryTurns plus an aggregate reducer that promotes `execution.json`.

**Scope:** `execution_batch_N.json`, stable task-slot mapping, resume mapping, target-repo mutation evidence, approval/preflight, tier routing, active-step session keys, timeout recovery, quality gates, blocked-task reset, prerequisite blocks, `finalize.json` child updates, audit/trace outputs, skipped-review stubs.

**Locked decisions:** Child turns may mutate the target repo and update `finalize.json` before aggregate `execution.json`; those are harness side effects, not atomic promotions.

**Open questions:** How much existing execute audit output becomes `ExternalEffectRef` versus observability event.

**Constraints:** Batch numbering must be stable across resume.

**Done criteria:** Tests prove partial resume maps task IDs to original slots, side effects are recorded with evidence, reducer validates all children before aggregate promotion, tier routing remains handler-owned.

**Touchpoints:** execute handler, batch artifacts, quality gates, finalize update code, resume state, audit/trace writers.

**Anti-scope:** No review reducer.

**Run:** Difficulty 5/5; `partnered-5/thorough/high @codex`. Prep direction: “Trace execute batch lifecycle, resume keys, target mutation evidence, finalize updates, and reducer construction.”

### `m7-review-boundary` — Review Single/Parallel Reducers and Rework Caps

**Outcome:** Wrap single-worker review and add child/reducer shape for parallel and extreme review while preserving rework routing.

**Scope:** `review_output.json`, `review.json`, infra failure detection, empty-approved backfill, verdict merge into finalize projection, maker stop, transition-policy denial artifacts, rework caps, receipts, flag provenance, `final.md` rewrites, conditional `review.json` re-promotion.

**Locked decisions:** Review draft does not mutate execute artifacts. `_resolve_review_outcome` and transition-policy denial stay policy-owned.

**Open questions:** Reducer artifact naming for per-check parallel review evidence.

**Constraints:** Concerned task IDs, deterministic-check evidence, and flag IDs must survive reducer normalization.

**Done criteria:** Tests cover simple approve, rework cap, infra failure, parallel reducer, transition denial, conditional re-promotion, and flag provenance.

**Touchpoints:** review handler, parallel review orchestration, transition policy, final projection, flag registry.

**Anti-scope:** No tiebreaker/subpipeline generalization.

**Run:** Difficulty 5/5; `partnered-5/thorough/high @codex`. Prep direction: “Inventory review simple path, parallel/extreme path, denial artifacts, rework caps, and final projection writes.”

### `m8-subpipeline-tiebreaker` — Tiebreaker/Subpipeline Boundary Turns

**Outcome:** Implement child-scoped BoundaryTurns and reducer promotion for tiebreaker/subpipeline flows.

**Scope:** researcher/challenger child drafts, versioned iterations, child evidence refs, `gate.json` evidence input, `tiebreaker_decisions.json`, audits, human/replan/revise states, flag-registry mutation checkpoints.

**Locked decisions:** Child turns never write parent artifacts or advance parent state. Parent state advances only during reducer promotion.

**Open questions:** Whether reducer reprompts reuse one path or versioned attempt paths; choose versioned unless compatibility requires stable.

**Constraints:** Reducer validates child artifacts and `gate.json` refs before writing decisions or mutating flags.

**Done criteria:** Tests reject direct canonical child writes, validate child evidence, checkpoint flag mutation, preserve iteration metadata, and route correctly.

**Touchpoints:** tiebreaker orchestration, subpipeline runtime, flag registry, gate artifacts, audit writers.

**Anti-scope:** No generic Arnold recipe yet.

**Run:** Difficulty 5/5; `partnered-5/thorough/high @codex`. Prep direction: “Trace tiebreaker run/decide flow, child artifact naming, latest-output selection, flag mutation, and parent-state transitions.”

### `m9-arnold-recipe` — General Arnold Boundary Protocols

**Outcome:** Extract reusable Arnold-level protocols for draft/capture/validate/promote without depending on Megaplan registries, artifact names, or state classes.

**Scope:** Generic `BoundarySpec`/validator/promoter protocols; draft-kind adapters; runtime event/journal mapping; canonical target declarations; non-Megaplan example; author docs.

**Locked decisions:** The recipe standardizes mechanics, not stage meaning. Megaplan supplies its own specs and policies.

**Open questions:** Public package location and naming; prefer neutral Arnold runtime module, with Megaplan adapters importing it.

**Constraints:** Clean import test must prove non-Megaplan pipeline can use the protocols without importing Megaplan.

**Done criteria:** Toy non-Megaplan pipeline uses Markdown draft -> validate -> promote; wrong-path canonical write is diagnostic; docs explain adoption.

**Touchpoints:** Arnold runtime/protocol modules, docs, example pipeline, Megaplan adapter imports.

**Anti-scope:** No migration of unrelated pipelines.

**Run:** Difficulty 4/5; `partnered-4/full/high @codex`. Prep direction: “Identify neutral runtime modules and existing non-Megaplan examples; define the smallest protocol surface that Megaplan can consume.”

### `m10-conformance-gate` — Final Conformance, Docs, Acceptance Gate

**Outcome:** Build the acceptance gate proving BoundaryTurn preserved Megaplan behavior and is reusable outside Megaplan.

**Scope:** Stage preservation matrix; cross-stage acceptance tests; docs; migration notes; wrong-path/invalid/unmodified/resume tests; side-effect evidence audits; no-lost-functionality proof.

**Locked decisions:** This milestone fixes conformance and documentation only; it does not reopen architecture.

**Open questions:** None expected; blockers become regressions against prior milestones.

**Constraints:** Must run against integrated branch, not isolated milestone branches.

**Done criteria:** Full test suite plus BoundaryTurn conformance suite passes; docs list every stage and preserved behavior; non-Megaplan example passes clean import gate.

**Touchpoints:** tests, docs, conformance scripts, examples.

**Anti-scope:** No new phase migrations beyond acceptance fixes.

**Run:** Difficulty 4/5; `partnered-4/thorough/medium @codex`. Prep: no.

## Chain YAML Sketch

```yaml
base_branch: main

anchors:
  north_star: NORTHSTAR.md

milestones:
  - label: m1-json-facade
    idea: .megaplan/initiatives/boundary-turn-end-to-end/briefs/m1-json-facade.md
    profile: partnered-5
    vendor: codex
    robustness: thorough
    depth: high
    branch: boundary-turn-m1-json-facade
    prep_clarify: false
    prep_direction: "Map structured_output, template registry, worker/model-seam recovery, and JSON phase promotion tests. Preserve legacy recovery exactly."
    notes: "Conservative JSON facade over existing scratch behavior; no artifact or route changes."

  - label: m2-promotion-checkpoints
    idea: .megaplan/initiatives/boundary-turn-end-to-end/briefs/m2-promotion-checkpoints.md
    profile: partnered-5
    vendor: codex
    robustness: thorough
    depth: high
    branch: boundary-turn-m2-promotion
    depends_on:
      - m1-json-facade
    prep_clarify: false
    prep_direction: "Trace canonical artifact, state, history, receipt, and phase-result writes; design ordered resumable promotion checkpoints."
    notes: "Make promotion fail-closed without making external workspace mutations transactional."

  - label: m3-plan-revise-payloads
    idea: .megaplan/initiatives/boundary-turn-end-to-end/briefs/m3-plan-revise-payloads.md
    profile: partnered-5
    vendor: codex
    robustness: thorough
    depth: high
    branch: boundary-turn-m3-plan-revise
    depends_on:
      - m2-promotion-checkpoints
    prep_clarify: false
    prep_direction: "Inventory plan/revise structured payload metadata and all consumers of plan_vN.meta.json."
    notes: "Structured-payload boundary first; no Markdown-only draft migration."

  - label: m4-gate-boundary
    idea: .megaplan/initiatives/boundary-turn-end-to-end/briefs/m4-gate-boundary.md
    profile: partnered-5
    vendor: codex
    robustness: thorough
    depth: high
    branch: boundary-turn-m4-gate
    depends_on:
      - m2-promotion-checkpoints
    prep_clarify: false
    prep_direction: "Trace gate attempts, reprompts, carry artifacts, route policy, tiebreaker validation, and flag/debt writes."
    notes: "Gate turns validate attempts; final promotion happens once after gate policy resolves."

  - label: m5-finalize-boundary
    idea: .megaplan/initiatives/boundary-turn-end-to-end/briefs/m5-finalize-boundary.md
    profile: partnered-5
    vendor: codex
    robustness: thorough
    depth: high
    branch: boundary-turn-m5-finalize
    depends_on:
      - m2-promotion-checkpoints
    prep_clarify: false
    prep_direction: "Inventory finalize multi-artifact mapping, baseline side effects, validation injection, and finalize-to-revise behavior."
    notes: "Finalize promotion preserves baseline evidence and multi-artifact outputs."

  - label: m6-execute-boundary
    idea: .megaplan/initiatives/boundary-turn-end-to-end/briefs/m6-execute-boundary.md
    profile: partnered-5
    vendor: codex
    robustness: thorough
    depth: high
    branch: boundary-turn-m6-execute
    depends_on:
      - m5-finalize-boundary
    prep_clarify: false
    prep_direction: "Trace execute child batches, resume mapping, target mutations, tier routing, finalize updates, and aggregate reducer."
    notes: "Execute becomes child batch turns plus reducer, with side-effect evidence."

  - label: m7-review-boundary
    idea: .megaplan/initiatives/boundary-turn-end-to-end/briefs/m7-review-boundary.md
    profile: partnered-5
    vendor: codex
    robustness: thorough
    depth: high
    branch: boundary-turn-m7-review
    depends_on:
      - m6-execute-boundary
    prep_clarify: false
    prep_direction: "Inventory single review, parallel/extreme review, infra failure, transition denial, rework caps, and flag provenance."
    notes: "Review preserves simple scratch path and parallel child reducer path."

  - label: m8-subpipeline-tiebreaker
    idea: .megaplan/initiatives/boundary-turn-end-to-end/briefs/m8-subpipeline-tiebreaker.md
    profile: partnered-5
    vendor: codex
    robustness: thorough
    depth: high
    branch: boundary-turn-m8-tiebreaker
    depends_on:
      - m4-gate-boundary
      - m7-review-boundary
    prep_clarify: false
    prep_direction: "Trace tiebreaker researcher/challenger child outputs, reducer decision, gate evidence refs, audits, and flag-registry mutation."
    notes: "Subpipeline children are evidence; reducer alone advances parent state."

  - label: m9-arnold-recipe
    idea: .megaplan/initiatives/boundary-turn-end-to-end/briefs/m9-arnold-recipe.md
    profile: partnered-4
    vendor: codex
    robustness: full
    depth: high
    branch: boundary-turn-m9-arnold-recipe
    depends_on:
      - m8-subpipeline-tiebreaker
    prep_clarify: false
    prep_direction: "Find neutral Arnold runtime homes and a small non-Megaplan example; keep Megaplan registries out of the generic protocol."
    notes: "General reusable recipe for draft/capture/validate/promote mechanics."

  - label: m10-conformance-gate
    idea: .megaplan/initiatives/boundary-turn-end-to-end/briefs/m10-conformance-gate.md
    profile: partnered-4
    vendor: codex
    robustness: thorough
    depth: medium
    branch: boundary-turn-m10-conformance
    depends_on:
      - m9-arnold-recipe
    prep_clarify: false
    notes: "Integrated acceptance gate proving no stage functionality was lost and the recipe is reusable."

on_failure:
  abort: stop_chain
on_escalate:
  abort: stop_chain
merge_policy: review

driver:
  robustness: thorough
  auto_approve: true
  max_iterations: 120
  poll_sleep: 8.0
```

## Risk Notes

- The main risk is over-generalization: BoundaryTurn must not swallow worker parsing, phase validators, gate/review/execute policy, or auto-driver route derivation.
- Legacy recovery is load-bearing. Tightening expected-path capture too early will break provider paths that currently recover useful payloads.
- Plan/revise can silently lose metadata if treated as Markdown drafts before structured-payload parity is proven.
- Ordered promotion is harder than JSON facade work because artifact writes, state, history, receipts, and route proposals must be checkpointed together.
- Execute cannot be made atomic. The only honest invariant is recorded side-effect evidence plus resumable aggregate promotion.
- Parallel review and tiebreaker must be child/reducer structures; treating them as single scratch files will lose evidence, flag provenance, and transition-policy behavior.
- The Arnold-wide recipe must stay mechanical and neutral. If it imports Megaplan registries, it fails the reuse goal.
tokens used
56,504
## Epic Recommendation

**Slug:** `boundary-turn-end-to-end`

BoundaryTurn should be built as an epic because it changes the model-output boundary for every load-bearing Megaplan stage while deliberately preserving each stage’s existing policy. The north star is: models edit drafts; validators inspect only expected drafts or explicit legacy recovery payloads; harness-owned promotion writes canonical artifacts, state, history, receipts, and route proposals in ordered, resumable steps. BoundaryTurn is not a worker parser, route engine, phase-policy replacement, or rollback system for target-repository mutations.

## Milestones

| Label | Title | Profile | Robustness | Depth | Vendor | Prep | Dependencies | Purpose |
|---|---|---:|---|---|---|---|---|---|
| `m1-json-facade` | Conservative JSON BoundaryTurn Facade | `partnered-5` | `thorough` | `high` | `codex` | yes | none | Wrap current JSON scratch behavior without changing artifacts or recovery semantics. |
| `m2-promotion-checkpoints` | Ordered Promotion, Checkpoints, Receipts | `partnered-5` | `thorough` | `high` | `codex` | yes | `m1` | Make canonical writes/state/history/receipts fail-closed and resumable. |
| `m3-plan-revise-payloads` | Plan/Revise Structured Payload Boundary | `partnered-5` | `thorough` | `high` | `codex` | yes | `m2` | Preserve Markdown plus metadata before considering Markdown draft surfaces. |
| `m4-gate-boundary` | Gate Reprompts and Route Policy Preservation | `partnered-5` | `thorough` | `high` | `codex` | yes | `m2` | Model gate attempts as turns while leaving gate route policy intact. |
| `m5-finalize-boundary` | Finalize Multi-Artifact Promotion | `partnered-5` | `thorough` | `high` | `codex` | yes | `m2` | Preserve finalize artifacts, baseline effects, and finalize-to-revise routing. |
| `m6-execute-boundary` | Execute Child Batches and Aggregate Reducer | `partnered-5` | `thorough` | `high` | `codex` | yes | `m5` | Add child batch turns, reducer promotion, resume mapping, side-effect evidence. |
| `m7-review-boundary` | Review Single/Parallel Reducers and Rework Caps | `partnered-5` | `thorough` | `high` | `codex` | yes | `m6` | Preserve simple review plus parallel/extreme reducer and transition denial behavior. |
| `m8-subpipeline-tiebreaker` | Tiebreaker/Subpipeline Boundary Turns | `partnered-5` | `thorough` | `high` | `codex` | yes | `m4`, `m7` | Make child evidence and reducer promotion the only parent-state advance path. |
| `m9-arnold-recipe` | General Arnold Boundary Protocols | `partnered-4` | `full` | `high` | `codex` | yes | `m8` | Extract reusable draft/capture/validate/promote protocols without Megaplan registries. |
| `m10-conformance-gate` | Final Conformance, Docs, Acceptance Gate | `partnered-4` | `thorough` | `medium` | `codex` | no | `m9` | Prove stage parity, reusable recipe, and no lost Megaplan functionality. |

## Milestone Briefs

### `m1-json-facade` — Conservative JSON BoundaryTurn Facade

**Outcome:** Introduce `BoundaryTurn`, `BoundarySpec`, draft capture, validation, and promotion result types as a thin facade over `handlers/structured_output.py`. Migrate at least `critique_evaluator` and one higher-value JSON phase while preserving behavior.

**Scope:** JSON file-fill only; `legacy_recovery` policy; expected-path capture; missing/unmodified/filled/invalid diagnostics; direct canonical write rejection/diagnostics; compatibility with template registry metadata.

**Locked decisions:** Existing worker/model-seam recovery runs before boundary classification. Current artifact names do not change. Unknown keys follow existing phase policy. BoundaryTurn does not parse provider output itself.

**Open questions:** Whether direct canonical writes are hard failures for all file-tool workers or only diagnostics in legacy mode.

**Constraints:** No stricter fallback behavior until provider-path tests prove it safe.

**Done criteria:** Existing structured-output tests pass; new tests cover wrong path, canonical path, missing, unmodified, invalid, inline fallback, and unknown keys.

**Touchpoints:** `arnold_pipelines/megaplan/handlers/structured_output.py`, `template_registry.py`, JSON phase handlers/tests.

**Anti-scope:** No plan/revise Markdown drafts, execute batches, route-policy rewrites, or state checkpoint refactors.

**Run:** Overall plan difficulty 5/5; `partnered-5/thorough/high @codex`. Prep direction: “Map current structured_output, template registry, worker/model-seam recovery, and JSON phase promotion tests. Identify exact parity assertions before editing.”

### `m2-promotion-checkpoints` — Ordered Promotion, Checkpoints, Receipts

**Outcome:** Move canonical artifact writes, state deltas, history, receipts, and workflow transition proposals behind ordered promotion checkpoints.

**Scope:** Promotion journal/checkpoint API; idempotent resume; artifact-before-state ordering; receipt emission; external side-effect references; promotion-result persistence.

**Locked decisions:** Promotion may record external effects that already happened, never promise rollback. `workflow_transition` is a proposal; transition policy and auto-driver remain authoritative.

**Open questions:** Final checkpoint storage location, with preference for `PlanRepository`/plan-dir owned checkpoint files rather than handler-local ad hoc state.

**Constraints:** Existing handlers must be migratable incrementally.

**Done criteria:** Tests prove state cannot advance without required canonical artifacts; interrupted promotion resumes or fails closed; receipts are not duplicated.

**Touchpoints:** plan repository, state/history writers, receipt code, phase result handling, auto-driver transition evidence.

**Anti-scope:** No behavior changes to gate/review routing decisions.

**Run:** Difficulty 5/5; `partnered-5/thorough/high @codex`. Prep direction: “Trace every canonical artifact/state/history/receipt write in JSON phases and identify the minimum common checkpoint surface.”

### `m3-plan-revise-payloads` — Plan/Revise Structured Payload Boundary

**Outcome:** Wrap plan and revise as structured-payload BoundaryTurns that promote both Markdown and metadata without loss.

**Scope:** Existing worker payload shape; `plan_vN.md`; `plan_vN.meta.json`; questions, assumptions, success criteria, imported decision criteria, changed surfaces, test blast radius, version deltas, note-consumption receipts, cache-hit guards, flag updates.

**Locked decisions:** Do not switch to Markdown-only drafts. Metadata parity is required before any later Markdown surface.

**Open questions:** Whether plan/revise use stable draft paths or payload-only `inline_only` first.

**Constraints:** Versioning and delta tracking must remain byte/behavior compatible where tests exist.

**Done criteria:** Golden tests prove `plan_vN.md` and meta parity for plan and revise; revise still preserves prior-plan deltas, notes, flags, and validation summaries.

**Touchpoints:** plan/revise handlers, prompt builders, plan versioning, metadata writers, flag registry updates.

**Anti-scope:** No Markdown draft validation redesign.

**Run:** Difficulty 5/5; `partnered-5/thorough/high @codex`. Prep direction: “Inventory plan/revise payload fields and all consumers of `plan_vN.meta.json`; build a parity checklist before migration.”

### `m4-gate-boundary` — Gate Reprompts and Route Policy Preservation

**Outcome:** Model each gate attempt as a BoundaryTurn while promoting canonical gate artifacts only once after final valid attempt and auto-downgrade logic.

**Scope:** `gate_output.json`, `gate_signals_vN.json`, `gate.json`, `gate_carry.json`, `last_gate`, complete-replacement reprompts, invalid recommendation fallback, no-progress/max-iteration termination, debt writes, flag events, tiebreaker validation, blocked/gated distinctions.

**Locked decisions:** `_apply_gate_outcome`, transition policy, and auto-driver route derivation stay outside BoundaryTurn.

**Open questions:** Whether reducer-style gate attempts should get per-attempt checkpoint artifacts beyond diagnostics.

**Constraints:** Reprompts reuse the same draft path where current behavior requires full replacement.

**Done criteria:** Tests show intermediate reprompts validate without canonical promotion; final promotion preserves route-policy evidence and carry artifacts.

**Touchpoints:** gate handler, gate prompt, route policy, state transitions, flag/debt registries.

**Anti-scope:** No tiebreaker child-turn implementation yet.

**Run:** Difficulty 5/5; `partnered-5/thorough/high @codex`. Prep direction: “Trace gate attempt lifecycle, reprompt replacement semantics, and every artifact/state mutation from gate output to next route.”

### `m5-finalize-boundary` — Finalize Multi-Artifact Promotion

**Outcome:** Wrap finalize promotion across all finalize-owned artifacts and harness-computed side effects.

**Scope:** `finalize.json`, `final.md`, `contract.json`, `user_actions.md`, `finalize_snapshot.json`, capability claims, scoped baseline selection, baseline cache, execution baseline, validation injection, finalize-to-revise feedback.

**Locked decisions:** Model draft does not own harness-computed `validation`. Baseline capture is an external side effect with command/timing/evidence refs.

**Open questions:** Exact side-effect schema for baseline evidence.

**Constraints:** Baseline-selection failure routes to revise by writing gate/feedback artifacts, not by pretending finalize promoted normally.

**Done criteria:** Tests cover successful multi-artifact promotion, baseline failure route, capability claims, cache reuse, and finalize-to-revise artifacts.

**Touchpoints:** finalize handler, baseline/cache code, contract/user action writers, gate feedback path.

**Anti-scope:** No execute batch migration.

**Run:** Difficulty 5/5; `partnered-5/thorough/high @codex`. Prep direction: “Inventory finalize artifact mapping, baseline side effects, validation injection, and finalize-to-revise route before editing.”

### `m6-execute-boundary` — Execute Child Batches and Aggregate Reducer

**Outcome:** Represent execute as child batch BoundaryTurns plus an aggregate reducer that promotes `execution.json`.

**Scope:** `execution_batch_N.json`, stable task-slot mapping, resume mapping, target-repo mutation evidence, approval/preflight, tier routing, active-step session keys, timeout recovery, quality gates, blocked-task reset, prerequisite blocks, `finalize.json` child updates, audit/trace outputs, skipped-review stubs.

**Locked decisions:** Child turns may mutate the target repo and update `finalize.json` before aggregate `execution.json`; those are harness side effects, not atomic promotions.

**Open questions:** How much existing execute audit output becomes `ExternalEffectRef` versus observability event.

**Constraints:** Batch numbering must be stable across resume.

**Done criteria:** Tests prove partial resume maps task IDs to original slots, side effects are recorded with evidence, reducer validates all children before aggregate promotion, tier routing remains handler-owned.

**Touchpoints:** execute handler, batch artifacts, quality gates, finalize update code, resume state, audit/trace writers.

**Anti-scope:** No review reducer.

**Run:** Difficulty 5/5; `partnered-5/thorough/high @codex`. Prep direction: “Trace execute batch lifecycle, resume keys, target mutation evidence, finalize updates, and reducer construction.”

### `m7-review-boundary` — Review Single/Parallel Reducers and Rework Caps

**Outcome:** Wrap single-worker review and add child/reducer shape for parallel and extreme review while preserving rework routing.

**Scope:** `review_output.json`, `review.json`, infra failure detection, empty-approved backfill, verdict merge into finalize projection, maker stop, transition-policy denial artifacts, rework caps, receipts, flag provenance, `final.md` rewrites, conditional `review.json` re-promotion.

**Locked decisions:** Review draft does not mutate execute artifacts. `_resolve_review_outcome` and transition-policy denial stay policy-owned.

**Open questions:** Reducer artifact naming for per-check parallel review evidence.

**Constraints:** Concerned task IDs, deterministic-check evidence, and flag IDs must survive reducer normalization.

**Done criteria:** Tests cover simple approve, rework cap, infra failure, parallel reducer, transition denial, conditional re-promotion, and flag provenance.

**Touchpoints:** review handler, parallel review orchestration, transition policy, final projection, flag registry.

**Anti-scope:** No tiebreaker/subpipeline generalization.

**Run:** Difficulty 5/5; `partnered-5/thorough/high @codex`. Prep direction: “Inventory review simple path, parallel/extreme path, denial artifacts, rework caps, and final projection writes.”

### `m8-subpipeline-tiebreaker` — Tiebreaker/Subpipeline Boundary Turns

**Outcome:** Implement child-scoped BoundaryTurns and reducer promotion for tiebreaker/subpipeline flows.

**Scope:** researcher/challenger child drafts, versioned iterations, child evidence refs, `gate.json` evidence input, `tiebreaker_decisions.json`, audits, human/replan/revise states, flag-registry mutation checkpoints.

**Locked decisions:** Child turns never write parent artifacts or advance parent state. Parent state advances only during reducer promotion.

**Open questions:** Whether reducer reprompts reuse one path or versioned attempt paths; choose versioned unless compatibility requires stable.

**Constraints:** Reducer validates child artifacts and `gate.json` refs before writing decisions or mutating flags.

**Done criteria:** Tests reject direct canonical child writes, validate child evidence, checkpoint flag mutation, preserve iteration metadata, and route correctly.

**Touchpoints:** tiebreaker orchestration, subpipeline runtime, flag registry, gate artifacts, audit writers.

**Anti-scope:** No generic Arnold recipe yet.

**Run:** Difficulty 5/5; `partnered-5/thorough/high @codex`. Prep direction: “Trace tiebreaker run/decide flow, child artifact naming, latest-output selection, flag mutation, and parent-state transitions.”

### `m9-arnold-recipe` — General Arnold Boundary Protocols

**Outcome:** Extract reusable Arnold-level protocols for draft/capture/validate/promote without depending on Megaplan registries, artifact names, or state classes.

**Scope:** Generic `BoundarySpec`/validator/promoter protocols; draft-kind adapters; runtime event/journal mapping; canonical target declarations; non-Megaplan example; author docs.

**Locked decisions:** The recipe standardizes mechanics, not stage meaning. Megaplan supplies its own specs and policies.

**Open questions:** Public package location and naming; prefer neutral Arnold runtime module, with Megaplan adapters importing it.

**Constraints:** Clean import test must prove non-Megaplan pipeline can use the protocols without importing Megaplan.

**Done criteria:** Toy non-Megaplan pipeline uses Markdown draft -> validate -> promote; wrong-path canonical write is diagnostic; docs explain adoption.

**Touchpoints:** Arnold runtime/protocol modules, docs, example pipeline, Megaplan adapter imports.

**Anti-scope:** No migration of unrelated pipelines.

**Run:** Difficulty 4/5; `partnered-4/full/high @codex`. Prep direction: “Identify neutral runtime modules and existing non-Megaplan examples; define the smallest protocol surface that Megaplan can consume.”

### `m10-conformance-gate` — Final Conformance, Docs, Acceptance Gate

**Outcome:** Build the acceptance gate proving BoundaryTurn preserved Megaplan behavior and is reusable outside Megaplan.

**Scope:** Stage preservation matrix; cross-stage acceptance tests; docs; migration notes; wrong-path/invalid/unmodified/resume tests; side-effect evidence audits; no-lost-functionality proof.

**Locked decisions:** This milestone fixes conformance and documentation only; it does not reopen architecture.

**Open questions:** None expected; blockers become regressions against prior milestones.

**Constraints:** Must run against integrated branch, not isolated milestone branches.

**Done criteria:** Full test suite plus BoundaryTurn conformance suite passes; docs list every stage and preserved behavior; non-Megaplan example passes clean import gate.

**Touchpoints:** tests, docs, conformance scripts, examples.

**Anti-scope:** No new phase migrations beyond acceptance fixes.

**Run:** Difficulty 4/5; `partnered-4/thorough/medium @codex`. Prep: no.

## Chain YAML Sketch

```yaml
base_branch: main

anchors:
  north_star: NORTHSTAR.md

milestones:
  - label: m1-json-facade
    idea: .megaplan/initiatives/boundary-turn-end-to-end/briefs/m1-json-facade.md
    profile: partnered-5
    vendor: codex
    robustness: thorough
    depth: high
    branch: boundary-turn-m1-json-facade
    prep_clarify: false
    prep_direction: "Map structured_output, template registry, worker/model-seam recovery, and JSON phase promotion tests. Preserve legacy recovery exactly."
    notes: "Conservative JSON facade over existing scratch behavior; no artifact or route changes."

  - label: m2-promotion-checkpoints
    idea: .megaplan/initiatives/boundary-turn-end-to-end/briefs/m2-promotion-checkpoints.md
    profile: partnered-5
    vendor: codex
    robustness: thorough
    depth: high
    branch: boundary-turn-m2-promotion
    depends_on:
      - m1-json-facade
    prep_clarify: false
    prep_direction: "Trace canonical artifact, state, history, receipt, and phase-result writes; design ordered resumable promotion checkpoints."
    notes: "Make promotion fail-closed without making external workspace mutations transactional."

  - label: m3-plan-revise-payloads
    idea: .megaplan/initiatives/boundary-turn-end-to-end/briefs/m3-plan-revise-payloads.md
    profile: partnered-5
    vendor: codex
    robustness: thorough
    depth: high
    branch: boundary-turn-m3-plan-revise
    depends_on:
      - m2-promotion-checkpoints
    prep_clarify: false
    prep_direction: "Inventory plan/revise structured payload metadata and all consumers of plan_vN.meta.json."
    notes: "Structured-payload boundary first; no Markdown-only draft migration."

  - label: m4-gate-boundary
    idea: .megaplan/initiatives/boundary-turn-end-to-end/briefs/m4-gate-boundary.md
    profile: partnered-5
    vendor: codex
    robustness: thorough
    depth: high
    branch: boundary-turn-m4-gate
    depends_on:
      - m2-promotion-checkpoints
    prep_clarify: false
    prep_direction: "Trace gate attempts, reprompts, carry artifacts, route policy, tiebreaker validation, and flag/debt writes."
    notes: "Gate turns validate attempts; final promotion happens once after gate policy resolves."

  - label: m5-finalize-boundary
    idea: .megaplan/initiatives/boundary-turn-end-to-end/briefs/m5-finalize-boundary.md
    profile: partnered-5
    vendor: codex
    robustness: thorough
    depth: high
    branch: boundary-turn-m5-finalize
    depends_on:
      - m2-promotion-checkpoints
    prep_clarify: false
    prep_direction: "Inventory finalize multi-artifact mapping, baseline side effects, validation injection, and finalize-to-revise behavior."
    notes: "Finalize promotion preserves baseline evidence and multi-artifact outputs."

  - label: m6-execute-boundary
    idea: .megaplan/initiatives/boundary-turn-end-to-end/briefs/m6-execute-boundary.md
    profile: partnered-5
    vendor: codex
    robustness: thorough
    depth: high
    branch: boundary-turn-m6-execute
    depends_on:
      - m5-finalize-boundary
    prep_clarify: false
    prep_direction: "Trace execute child batches, resume mapping, target mutations, tier routing, finalize updates, and aggregate reducer."
    notes: "Execute becomes child batch turns plus reducer, with side-effect evidence."

  - label: m7-review-boundary
    idea: .megaplan/initiatives/boundary-turn-end-to-end/briefs/m7-review-boundary.md
    profile: partnered-5
    vendor: codex
    robustness: thorough
    depth: high
    branch: boundary-turn-m7-review
    depends_on:
      - m6-execute-boundary
    prep_clarify: false
    prep_direction: "Inventory single review, parallel/extreme review, infra failure, transition denial, rework caps, and flag provenance."
    notes: "Review preserves simple scratch path and parallel child reducer path."

  - label: m8-subpipeline-tiebreaker
    idea: .megaplan/initiatives/boundary-turn-end-to-end/briefs/m8-subpipeline-tiebreaker.md
    profile: partnered-5
    vendor: codex
    robustness: thorough
    depth: high
    branch: boundary-turn-m8-tiebreaker
    depends_on:
      - m4-gate-boundary
      - m7-review-boundary
    prep_clarify: false
    prep_direction: "Trace tiebreaker researcher/challenger child outputs, reducer decision, gate evidence refs, audits, and flag-registry mutation."
    notes: "Subpipeline children are evidence; reducer alone advances parent state."

  - label: m9-arnold-recipe
    idea: .megaplan/initiatives/boundary-turn-end-to-end/briefs/m9-arnold-recipe.md
    profile: partnered-4
    vendor: codex
    robustness: full
    depth: high
    branch: boundary-turn-m9-arnold-recipe
    depends_on:
      - m8-subpipeline-tiebreaker
    prep_clarify: false
    prep_direction: "Find neutral Arnold runtime homes and a small non-Megaplan example; keep Megaplan registries out of the generic protocol."
    notes: "General reusable recipe for draft/capture/validate/promote mechanics."

  - label: m10-conformance-gate
    idea: .megaplan/initiatives/boundary-turn-end-to-end/briefs/m10-conformance-gate.md
    profile: partnered-4
    vendor: codex
    robustness: thorough
    depth: medium
    branch: boundary-turn-m10-conformance
    depends_on:
      - m9-arnold-recipe
    prep_clarify: false
    notes: "Integrated acceptance gate proving no stage functionality was lost and the recipe is reusable."

on_failure:
  abort: stop_chain
on_escalate:
  abort: stop_chain
merge_policy: review

driver:
  robustness: thorough
  auto_approve: true
  max_iterations: 120
  poll_sleep: 8.0
```

## Risk Notes

- The main risk is over-generalization: BoundaryTurn must not swallow worker parsing, phase validators, gate/review/execute policy, or auto-driver route derivation.
- Legacy recovery is load-bearing. Tightening expected-path capture too early will break provider paths that currently recover useful payloads.
- Plan/revise can silently lose metadata if treated as Markdown drafts before structured-payload parity is proven.
- Ordered promotion is harder than JSON facade work because artifact writes, state, history, receipts, and route proposals must be checkpointed together.
- Execute cannot be made atomic. The only honest invariant is recorded side-effect evidence plus resumable aggregate promotion.
- Parallel review and tiebreaker must be child/reducer structures; treating them as single scratch files will lose evidence, flag provenance, and transition-policy behavior.
- The Arnold-wide recipe must stay mechanical and neutral. If it imports Megaplan registries, it fails the reuse goal.
