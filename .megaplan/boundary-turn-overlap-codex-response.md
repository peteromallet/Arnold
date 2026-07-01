Reading additional input from stdin...
2026-07-01T00:41:14.117268Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/.agents/skills/enrich-upload-external-workflows/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.137.0
--------
workdir: /Users/peteromalley/Documents/Arnold
model: gpt-5.5
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019f1b1f-73c3-7f01-ab4c-676d0d2fb871
--------
user
# Codex subagent brief: BoundaryTurn overlap with native epics

Working directory: `/Users/peteromalley/Documents/Arnold`.

You are a Codex subagent doing an independent architecture/program-shaping
sense-check. Do not edit files. Read the listed files and return a direct
recommendation.

## Question

Can the BoundaryTurn end-to-end epic be done at the same time as these existing
native follow-up epics if we are willing to spend some time merging the plans
together?

- `.megaplan/initiatives/native-python-pipelines-completion/chain.yaml`
- `.megaplan/initiatives/native-composition-followup/chain.yaml`
- `.megaplan/initiatives/native-platform-followup/chain.yaml`

Also read the current BoundaryTurn epic:

- `.megaplan/initiatives/boundary-turn-end-to-end/chain.yaml`
- `.megaplan/initiatives/boundary-turn-end-to-end/NORTHSTAR.md`
- `.megaplan/initiatives/boundary-turn-end-to-end/briefs/m1-boundary-foundation.md`
- `.megaplan/initiatives/boundary-turn-end-to-end/briefs/m2-primary-stage-boundaries.md`
- `.megaplan/initiatives/boundary-turn-end-to-end/briefs/m3-reducer-stage-boundaries.md`
- `.megaplan/initiatives/boundary-turn-end-to-end/briefs/m4-recipe-conformance.md`

And the design inputs:

- `docs/arnold/megaplan-boundary-turn-design.md`
- `docs/arnold/megaplan-boundary-turn-load-bearing-questions.md`

## What to decide

Give an opinionated answer on whether BoundaryTurn should:

1. remain a separate epic with dependency edges to those chains;
2. be merged into `native-python-pipelines-completion`;
3. be merged into `native-composition-followup`;
4. be merged into `native-platform-followup`;
5. be split across them.

Assume the team is willing to spend some time merging plans and resolving brief
overlap, but does not want accidental scope bloat or months of unnecessary
sequencing.

## Evaluation criteria

- Does BoundaryTurn naturally depend on native Python completion?
- Does it naturally depend on composition semantics?
- Does it naturally depend on platform side-effect/idempotency/checkpoint work?
- Which BoundaryTurn milestones can safely run in parallel with which existing
  milestones?
- Which milestones would create merge conflicts or conceptual drift if run in
  parallel?
- What is the shortest robust program shape?
- What should the chain dependency/precondition structure be?

## Output format

Return only Markdown, under 2200 words:

1. `Verdict`: one paragraph.
2. `Recommended Shape`: concrete chain/milestone placement.
3. `Parallelization Map`: what can run together, what must wait.
4. `Merge Risks`: top risks and mitigations.
5. `Proposed Edits`: specific changes to the BoundaryTurn chain or existing
   chains, if any.

Be blunt. If the current 4-milestone BoundaryTurn epic is still too big, say so.
If merging into the native epics is worse than keeping it separate, say so.
codex
I’ll treat this as the subagent pass: read the existing chain/brief inputs only, compare program boundaries, and return a recommendation without editing anything.
exec
/bin/zsh -lc "sed -n '1,240p' .megaplan/initiatives/native-python-pipelines-completion/chain.yaml" in /Users/peteromalley/Documents/Arnold
exec
/bin/zsh -lc "sed -n '1,260p' .megaplan/initiatives/native-composition-followup/chain.yaml" in /Users/peteromalley/Documents/Arnold
 succeeded in 0ms:
base_branch: main

anchors:
  north_star: NORTHSTAR.md

launch_preconditions:
  - name: native representation end-state anchor exists
    path: docs/arnold/megaplan-native-representation-report.md
    check:
      kind: contains_text
      text: "Native Python Representation Report"
  - name: alignment plan exists
    path: docs/arnold/megaplan-native-representation-alignment-plan.md
    check:
      kind: contains_text
      text: "Completion Standard"
  - name: review execution log has no unaddressed blockers
    path: docs/arnold/megaplan-native-representation-review-execution.md
    check:
      kind: review_log_clean
  - name: launch readiness ledger exists
    path: docs/arnold/megaplan-native-representation-launch-readiness.md
    check:
      kind: contains_text
      text: "No-Bypass Rules"
  - name: machine-readable traceability exists
    path: docs/arnold/megaplan-native-representation-traceability.yaml
    check:
      kind: contains_text
      text: "arnold.megaplan_native_representation.traceability.v1"
  - name: fixed scenario manifest exists
    path: docs/arnold/megaplan-native-representation-scenarios.yaml
    check:
      kind: contains_text
      text: "arnold.megaplan_native_representation.scenarios.v1"
  - name: completion initiative source is committed and clean
    kind: git_tracked
    path: .megaplan/initiatives/native-python-pipelines-completion
  - name: native representation report is committed and clean
    kind: git_tracked
    path: docs/arnold/megaplan-native-representation-report.md
  - name: alignment plan is committed and clean
    kind: git_tracked
    path: docs/arnold/megaplan-native-representation-alignment-plan.md
  - name: review execution log is committed and clean
    kind: git_tracked
    path: docs/arnold/megaplan-native-representation-review-execution.md
  - name: launch readiness ledger is committed and clean
    kind: git_tracked
    path: docs/arnold/megaplan-native-representation-launch-readiness.md
  - name: traceability artifact is committed and clean
    kind: git_tracked
    path: docs/arnold/megaplan-native-representation-traceability.yaml
  - name: scenario manifest is committed and clean
    kind: git_tracked
    path: docs/arnold/megaplan-native-representation-scenarios.yaml

milestones:
  - label: m1-platform-contract
    idea: .megaplan/initiatives/native-python-pipelines-completion/briefs/m1-platform-contract.md
    profile: partnered-5
    robustness: thorough
    depth: high

  - label: m2-megaplan-subpipelines-layout
    idea: .megaplan/initiatives/native-python-pipelines-completion/briefs/m2-megaplan-subpipelines-layout.md
    profile: partnered-5
    robustness: thorough
    depth: high
    depends_on:
      - m1-platform-contract

  - label: m3-root-and-shared-package-migrations
    idea: .megaplan/initiatives/native-python-pipelines-completion/briefs/m3-root-and-shared-package-migrations.md
    profile: partnered-5
    robustness: thorough
    depth: high
    depends_on:
      - m2-megaplan-subpipelines-layout

  - label: m3-5-canonical-megaplan-migration
    idea: .megaplan/initiatives/native-python-pipelines-completion/briefs/m3-5-canonical-megaplan-migration.md
    profile: partnered-5
    robustness: extreme
    depth: max
    depends_on:
      - m3-root-and-shared-package-migrations

  - label: m4-evidence-pack-native-migration
    idea: .megaplan/initiatives/native-python-pipelines-completion/briefs/m4-evidence-pack-native-migration.md
    profile: partnered-5
    robustness: thorough
    depth: high
    depends_on:
      - m3-5-canonical-megaplan-migration

  - label: m5-native-test-and-golden-trace-cleanup
    idea: .megaplan/initiatives/native-python-pipelines-completion/briefs/m5-native-test-and-golden-trace-cleanup.md
    profile: partnered-5
    robustness: thorough
    depth: high
    depends_on:
      - m4-evidence-pack-native-migration

  - label: m6-docs-and-scaffolds-native-first
    idea: .megaplan/initiatives/native-python-pipelines-completion/briefs/m6-docs-and-scaffolds-native-first.md
    profile: partnered-5
    robustness: thorough
    depth: high
    depends_on:
      - m5-native-test-and-golden-trace-cleanup

  - label: m7-megaplan-relocation-and-final-purge
    idea: .megaplan/initiatives/native-python-pipelines-completion/briefs/m7-megaplan-relocation-and-final-purge.md
    profile: partnered-5
    robustness: thorough
    depth: high
    depends_on:
      - m6-docs-and-scaffolds-native-first

on_failure:
  abort: stop_chain

on_escalate:
  abort: stop_chain

merge_policy: review

driver:
  auto_approve: false
  require_clean_base: true
  robustness: thorough
  poll_sleep: 8.0

 succeeded in 0ms:
base_branch: main

anchors:
  north_star: NORTHSTAR.md

# Epic: Native Composition Follow-Up
# Prerequisite: .megaplan/initiatives/native-python-pipelines-completion/chain.yaml complete.
# Intent: evolve the completed native-first runtime into a true compositional
# workflow layer. M0 defines the contract. M1 migrates canonical Megaplan first
# under that contract so the abstraction is validated against the hardest real
# workflow without letting Megaplan-specific hacks define the general model.

launch_preconditions:
  - name: native python completion chain completed
    kind: chain_completed
    chain: .megaplan/initiatives/native-python-pipelines-completion/chain.yaml
    require_manifest: true
  - name: native representation end-state anchor exists
    path: docs/arnold/megaplan-native-representation-report.md
    check:
      kind: contains_text
      text: "Native Python Representation Report"
  - name: alignment plan exists
    path: docs/arnold/megaplan-native-representation-alignment-plan.md
    check:
      kind: contains_text
      text: "Completion Standard"
  - name: review execution log has no unaddressed blockers
    path: docs/arnold/megaplan-native-representation-review-execution.md
    check:
      kind: review_log_clean
  - name: machine-readable traceability exists
    path: docs/arnold/megaplan-native-representation-traceability.yaml
    check:
      kind: contains_text
      text: "arnold.megaplan_native_representation.traceability.v1"
  - name: fixed scenario manifest exists
    path: docs/arnold/megaplan-native-representation-scenarios.yaml
    check:
      kind: contains_text
      text: "arnold.megaplan_native_representation.scenarios.v1"
  - name: composition initiative source is committed and clean
    kind: git_tracked
    path: .megaplan/initiatives/native-composition-followup
  - name: native representation report is committed and clean
    kind: git_tracked
    path: docs/arnold/megaplan-native-representation-report.md
  - name: alignment plan is committed and clean
    kind: git_tracked
    path: docs/arnold/megaplan-native-representation-alignment-plan.md
  - name: review execution log is committed and clean
    kind: git_tracked
    path: docs/arnold/megaplan-native-representation-review-execution.md
  - name: launch readiness ledger is committed and clean
    kind: git_tracked
    path: docs/arnold/megaplan-native-representation-launch-readiness.md
  - name: traceability artifact is committed and clean
    kind: git_tracked
    path: docs/arnold/megaplan-native-representation-traceability.yaml
  - name: scenario manifest is committed and clean
    kind: git_tracked
    path: docs/arnold/megaplan-native-representation-scenarios.yaml

milestones:
  - label: m0-composition-contract-and-examples
    idea: .megaplan/initiatives/native-composition-followup/briefs/m0-composition-contract-and-examples.md
    profile: partnered-5
    robustness: thorough
    depth: high

  - label: m1-megaplan-compositional-migration
    idea: .megaplan/initiatives/native-composition-followup/briefs/m1-megaplan-compositional-migration.md
    profile: partnered-5
    robustness: extreme
    depth: max
    depends_on: [m0-composition-contract-and-examples]

  - label: m2-routing-validator-and-authoring-boundary
    idea: .megaplan/initiatives/native-composition-followup/briefs/m2-routing-validator-and-authoring-boundary.md
    profile: partnered-5
    robustness: thorough
    depth: high
    depends_on: [m0-composition-contract-and-examples, m1-megaplan-compositional-migration]

  - label: m3-general-nested-workflow-invocation
    idea: .megaplan/initiatives/native-composition-followup/briefs/m3-general-nested-workflow-invocation.md
    profile: partnered-5
    robustness: thorough
    depth: high
    depends_on: [m0-composition-contract-and-examples, m1-megaplan-compositional-migration, m2-routing-validator-and-authoring-boundary]

  - label: m4-tree-graph-trace-and-audit-skeleton
    idea: .megaplan/initiatives/native-composition-followup/briefs/m4-tree-graph-trace-and-audit-skeleton.md
    profile: partnered-5
    robustness: thorough
    depth: high
    depends_on: [m2-routing-validator-and-authoring-boundary, m3-general-nested-workflow-invocation]

  - label: m5-composite-resume-and-start-from-path
    idea: .megaplan/initiatives/native-composition-followup/briefs/m5-composite-resume-and-start-from-path.md
    profile: partnered-5
    robustness: extreme
    depth: max
    depends_on: [m3-general-nested-workflow-invocation, m4-tree-graph-trace-and-audit-skeleton]

  - label: m6-composition-docs-and-conformance
    idea: .megaplan/initiatives/native-composition-followup/briefs/m6-composition-docs-and-conformance.md
    profile: partnered-5
    robustness: thorough
    depth: high
    depends_on: [m5-composite-resume-and-start-from-path]

on_failure:
  retry: retry_milestone
  escalate: bump_profile
  abort: stop_chain

on_escalate:
  abort: stop_chain

merge_policy: review

driver:
  auto_approve: false
  max_iterations: 80
  require_clean_base: true
  robustness: thorough
  poll_sleep: 8.0

exec
/bin/zsh -lc "sed -n '1,260p' .megaplan/initiatives/native-platform-followup/chain.yaml" in /Users/peteromalley/Documents/Arnold
 succeeded in 0ms:
base_branch: main

anchors:
  north_star: NORTHSTAR.md

# Epic: Native Platform Follow-Up
# Prerequisites:
# - .megaplan/initiatives/native-python-pipelines-completion/chain.yaml complete
# - .megaplan/initiatives/native-composition-followup/chain.yaml complete
# Intent: add production platform, security, sharing/versioning, side-effect
# safety, and fleet supervision around the native composition primitive.

launch_preconditions:
  - name: native python completion chain completed
    kind: chain_completed
    chain: .megaplan/initiatives/native-python-pipelines-completion/chain.yaml
    require_manifest: true
  - name: native composition chain completed
    kind: chain_completed
    chain: .megaplan/initiatives/native-composition-followup/chain.yaml
    require_manifest: true
  - name: native representation end-state anchor exists
    path: docs/arnold/megaplan-native-representation-report.md
    check:
      kind: contains_text
      text: "Native Python Representation Report"
  - name: review execution log has no unaddressed blockers
    path: docs/arnold/megaplan-native-representation-review-execution.md
    check:
      kind: review_log_clean
  - name: machine-readable traceability exists
    path: docs/arnold/megaplan-native-representation-traceability.yaml
    check:
      kind: contains_text
      text: "arnold.megaplan_native_representation.traceability.v1"
  - name: fixed scenario manifest exists
    path: docs/arnold/megaplan-native-representation-scenarios.yaml
    check:
      kind: contains_text
      text: "arnold.megaplan_native_representation.scenarios.v1"
  - name: platform initiative source is committed and clean
    kind: git_tracked
    path: .megaplan/initiatives/native-platform-followup
  - name: native representation report is committed and clean
    kind: git_tracked
    path: docs/arnold/megaplan-native-representation-report.md
  - name: alignment plan is committed and clean
    kind: git_tracked
    path: docs/arnold/megaplan-native-representation-alignment-plan.md
  - name: review execution log is committed and clean
    kind: git_tracked
    path: docs/arnold/megaplan-native-representation-review-execution.md
  - name: launch readiness ledger is committed and clean
    kind: git_tracked
    path: docs/arnold/megaplan-native-representation-launch-readiness.md
  - name: traceability artifact is committed and clean
    kind: git_tracked
    path: docs/arnold/megaplan-native-representation-traceability.yaml
  - name: scenario manifest is committed and clean
    kind: git_tracked
    path: docs/arnold/megaplan-native-representation-scenarios.yaml
  - name: composition conformance report exists
    path: docs/arnold/megaplan-composition-conformance-report.md
    check:
      kind: contains_text
      text: "Megaplan composition conformance"
  - name: composition conformance report is committed and clean
    kind: git_tracked
    path: docs/arnold/megaplan-composition-conformance-report.md

milestones:
  - label: m1-side-effect-reconcile-and-idempotency
    idea: .megaplan/initiatives/native-platform-followup/briefs/m1-side-effect-reconcile-and-idempotency.md
    profile: partnered-5
    robustness: extreme
    depth: max

  - label: m2-security-broker-and-approval-gates
    idea: .megaplan/initiatives/native-platform-followup/briefs/m2-security-broker-and-approval-gates.md
    profile: partnered-5
    robustness: extreme
    depth: max
    depends_on: [m1-side-effect-reconcile-and-idempotency]

  - label: m3-shared-library-packs-and-versioning
    idea: .megaplan/initiatives/native-platform-followup/briefs/m3-shared-library-packs-and-versioning.md
    profile: partnered-5
    robustness: thorough
    depth: high
    depends_on: [m1-side-effect-reconcile-and-idempotency]

  - label: m4-durable-substrate-and-checkpoint-backend
    idea: .megaplan/initiatives/native-platform-followup/briefs/m4-durable-substrate-and-checkpoint-backend.md
    profile: partnered-5
    robustness: thorough
    depth: high
    depends_on:
      [
        m1-side-effect-reconcile-and-idempotency,
        m2-security-broker-and-approval-gates,
        m3-shared-library-packs-and-versioning,
      ]

  - label: m5-worker-fleet-supervision-and-cancellation
    idea: .megaplan/initiatives/native-platform-followup/briefs/m5-worker-fleet-supervision-and-cancellation.md
    profile: partnered-5
    robustness: extreme
    depth: max
    depends_on: [m4-durable-substrate-and-checkpoint-backend]

  - label: m6-platform-docs-conformance-and-rollout
    idea: .megaplan/initiatives/native-platform-followup/briefs/m6-platform-docs-conformance-and-rollout.md
    profile: partnered-5
    robustness: thorough
    depth: high
    depends_on: [m5-worker-fleet-supervision-and-cancellation]
    validate:
      - kind: final_conformance_gate
        traceability: docs/arnold/megaplan-native-representation-traceability.yaml
        conformance: docs/arnold/megaplan-native-representation-conformance.yaml
        validator: scripts/validate_native_representation_conformance.py
        proof_map: .megaplan/initiatives/native-platform-followup/proof-map.json

on_failure:
  retry: retry_milestone
  escalate: bump_profile
  abort: stop_chain

on_escalate:
  abort: stop_chain

merge_policy: review

driver:
  auto_approve: false
  max_iterations: 80
  require_clean_base: true
  robustness: thorough
  poll_sleep: 8.0

codex
I have the three native chains. The dependency intent is already explicit: completion precedes composition, and composition precedes platform, so I’m checking whether BoundaryTurn is a cross-cutting refinement or a misplaced milestone inside one of those tracks.
exec
/bin/zsh -lc "sed -n '1,260p' docs/arnold/megaplan-boundary-turn-design.md" in /Users/peteromalley/Documents/Arnold
exec
/bin/zsh -lc "sed -n '1,260p' .megaplan/initiatives/boundary-turn-end-to-end/chain.yaml" in /Users/peteromalley/Documents/Arnold
 succeeded in 0ms:
base_branch: main

anchors:
  north_star: NORTHSTAR.md

milestones:
  - label: m1-boundary-foundation
    idea: .megaplan/initiatives/boundary-turn-end-to-end/briefs/m1-boundary-foundation.md
    profile: partnered-5
    vendor: codex
    robustness: thorough
    depth: high
    branch: boundary-turn-m1-foundation
    prep_clarify: false
    prep_direction: "Map structured_output, template registry, worker/model-seam recovery, JSON phase promotion tests, artifact/state/history/receipt writes, and resume behavior. Preserve legacy recovery exactly."
    notes: "Build the BoundaryTurn JSON facade plus ordered promotion/checkpoint foundation."

  - label: m2-primary-stage-boundaries
    idea: .megaplan/initiatives/boundary-turn-end-to-end/briefs/m2-primary-stage-boundaries.md
    profile: partnered-5
    vendor: codex
    robustness: thorough
    depth: high
    branch: boundary-turn-m2-primary-stages
    depends_on:
      - m1-boundary-foundation
    prep_clarify: false
    prep_direction: "Inventory plan/revise metadata, gate reprompts/routing, finalize multi-artifact promotion, baseline side effects, and finalize-to-revise behavior before migration."
    notes: "Migrate plan/revise, gate, and finalize onto BoundaryTurn without changing stage policy."

  - label: m3-reducer-stage-boundaries
    idea: .megaplan/initiatives/boundary-turn-end-to-end/briefs/m3-reducer-stage-boundaries.md
    profile: partnered-5
    vendor: codex
    robustness: thorough
    depth: high
    branch: boundary-turn-m3-reducers
    depends_on:
      - m2-primary-stage-boundaries
    prep_clarify: false
    prep_direction: "Trace execute child batches, review single/parallel paths, tiebreaker child outputs, reducers, side-effect evidence, resume keys, and flag mutations."
    notes: "Add child-turn/reducer boundaries for execute, review, and tiebreaker."

  - label: m4-recipe-conformance
    idea: .megaplan/initiatives/boundary-turn-end-to-end/briefs/m4-recipe-conformance.md
    profile: partnered-4
    vendor: codex
    robustness: thorough
    depth: medium
    branch: boundary-turn-m4-recipe-conformance
    depends_on:
      - m3-reducer-stage-boundaries
    prep_clarify: false
    prep_direction: "Find neutral Arnold runtime homes and a small non-Megaplan example; build the conformance matrix proving no Megaplan stage functionality was lost."
    notes: "General Arnold recipe plus final acceptance gate."

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

exec
/bin/zsh -lc "sed -n '1,260p' .megaplan/initiatives/boundary-turn-end-to-end/NORTHSTAR.md" in /Users/peteromalley/Documents/Arnold
 succeeded in 0ms:
---
type: anchor
anchor_type: north_star
slug: boundary-turn-end-to-end
title: "North Star: BoundaryTurn End To End"
---

# North Star: BoundaryTurn End To End

Build BoundaryTurn as the clean, reusable boundary between model-authored draft
outputs and harness-owned canonical artifacts.

The end state is:

- Models edit drafts.
- Validators inspect expected drafts or explicit legacy recovery payloads.
- The harness alone promotes canonical artifacts, state, history, receipts, and
  route proposals.
- Worker parsing, model-seam recovery, phase validators, transition policy, and
  stage-specific semantics remain in their proper layers.
- Megaplan gets cleaner boundaries without losing any behavior.
- Other Arnold pipeline authors get a standard draft/capture/validate/promote
  recipe without importing Megaplan registries or artifact names.

This epic must not flatten Megaplan stages into a generic engine. It should make
the mechanics elegant while preserving the meaning of each stage.

exec
/bin/zsh -lc "sed -n '1,260p' docs/arnold/megaplan-boundary-turn-load-bearing-questions.md" in /Users/peteromalley/Documents/Arnold
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

codex
BoundaryTurn’s design is narrower than “native platform”: it is promotion-time ownership around model outputs, with explicit non-atomic external effects. Now I’m reading the milestone briefs to judge whether the current four milestones are shaped correctly or whether one should move into an existing chain.
exec
/bin/zsh -lc "sed -n '1,300p' .megaplan/initiatives/boundary-turn-end-to-end/briefs/m1-boundary-foundation.md" in /Users/peteromalley/Documents/Arnold
 succeeded in 0ms:
# M1: Boundary Foundation

## Outcome

Build the reusable BoundaryTurn foundation without changing Megaplan behavior:
a JSON scratch facade over existing structured output plus ordered promotion
checkpoints for canonical artifacts, state, history, receipts, and diagnostics.

## Scope

IN:

- `BoundaryTurn`, `BoundarySpec`, capture diagnostics, fallback policies, and
  `PromotionResult`.
- A thin facade over `handlers/structured_output.py`.
- `legacy_recovery` as the default policy for existing JSON phases.
- Ordered promotion checkpoints with idempotent resume.
- Parity tests for wrong path, direct canonical path, missing draft, unmodified
  draft, modified-invalid draft, inline fallback, unknown keys, and receipt
  deduplication.
- Migrate one low-risk JSON phase and one higher-value JSON phase through the
  facade.

OUT:

- Plan/revise migration.
- Execute/review/tiebreaker reducers.
- Generic Arnold public protocols.
- Any attempt to make target-repository mutations transactional.

## Locked Decisions

- BoundaryTurn is a promotion-time abstraction, not a worker parser.
- Worker/model-seam recovery runs before boundary classification in
  `legacy_recovery`.
- Current artifact names do not change.
- `workflow_transition` is a proposal or record, not an authoritative route.
- Missing and unmodified drafts remain distinct diagnostics.

## Open Questions

- Should direct canonical writes hard-fail or be diagnostics in legacy mode?
- Should checkpoint state live in `PlanRepository`, a new boundary module, or
  plan-dir checkpoint artifacts?

## Constraints

- Preserve DeepSeek/Kimi recovery, tool-markup extraction, malformed-inline /
  valid-file recovery, phase normalizers, and current `promote_scratch`
  behavior.
- Make the facade incremental; handlers must be migratable one at a time.

## Done Criteria

- Existing structured-output tests pass.
- New BoundaryTurn tests prove parity and fail-closed promotion behavior.
- State cannot advance without required canonical artifacts.
- Interrupted promotion resumes or fails closed without duplicate receipts.
- The milestone leaves clear instructions for migrating additional phases.

## Touchpoints

- `arnold_pipelines/megaplan/handlers/structured_output.py`
- `arnold_pipelines/megaplan/template_registry.py`
- JSON phase handlers/tests
- Plan repository/artifact writers
- State/history/receipt code
- `arnold_pipelines/megaplan/workers/hermes.py`
- `arnold_pipelines/megaplan/model_seam.py`

## Anti-Scope

- Do not move gate/review routing policy into BoundaryTurn.
- Do not rewrite provider parsing or model-seam recovery.
- Do not change canonical artifact names.

## Run Notes

Overall plan difficulty: 5/5; selected profile: `partnered-5`; because this is
the core boundary placement and a bad foundation can silently weaken recovery,
resume, or artifact invariants.

Use `partnered-5/thorough/high @codex +prep`.

exec
/bin/zsh -lc "sed -n '1,320p' .megaplan/initiatives/boundary-turn-end-to-end/briefs/m2-primary-stage-boundaries.md" in /Users/peteromalley/Documents/Arnold
 succeeded in 0ms:
# M2: Primary Stage Boundaries

## Outcome

Migrate the primary non-reducer stages onto BoundaryTurn while preserving their
stage-specific policy: plan/revise structured payloads, gate attempts, and
finalize multi-artifact promotion.

## Scope

IN:

- Plan/revise as structured-payload boundaries preserving `plan_vN.md` and
  `plan_vN.meta.json`.
- Plan/revise metadata parity: questions, assumptions, success criteria,
  imported decision criteria, changed surfaces, test blast radius, note
  receipts, cache-hit guards, carried blast radius, and flag updates.
- Gate BoundaryTurns for attempts/reprompts, with canonical gate artifacts
  promoted once after final gate policy resolution.
- Finalize multi-artifact promotion: `finalize.json`, `final.md`,
  `contract.json`, `user_actions.md`, `finalize_snapshot.json`, capability
  claims, baseline cache, validation injection, and finalize-to-revise route.

OUT:

- Markdown-only plan/revise drafts.
- Execute child batches.
- Review parallel reducers.
- Tiebreaker child turns.

## Locked Decisions

- Plan/revise do not become Markdown-only drafts in this milestone.
- `_apply_gate_outcome`, transition policy, and auto-driver route derivation
  stay outside BoundaryTurn.
- Intermediate gate attempts validate but do not promote canonical gate
  artifacts.
- Finalize model drafts do not own harness-computed `validation`.
- Baseline capture is recorded as a side effect, not treated as rollback-safe.

## Open Questions

- Should plan/revise start as `inline_only` structured boundaries or stable
  draft paths?
- What side-effect schema should baseline capture use?

## Constraints

- Preserve gate blocked/gated distinctions, debt writes, flag events, invalid
  recommendation fallback, no-progress termination, and tiebreaker validation.
- Preserve finalize baseline-selection failure routing to revise via
  gate/feedback artifacts.

## Done Criteria

- Golden tests prove plan/revise Markdown plus metadata parity.
- Gate tests prove validate-without-promote reprompts and one final canonical
  promotion.
- Finalize tests prove all canonical artifacts, baseline cache behavior,
  harness-computed validation, and finalize-to-revise artifacts.
- No stage loses existing route or state behavior.

## Touchpoints

- Plan/revise handlers and prompt builders
- Gate handler, route policy, flag/debt registries
- Finalize handler, baseline/cache code, contract/user-action writers
- BoundaryTurn foundation from M1

## Anti-Scope

- Do not implement reducer-style execute/review/tiebreaker.
- Do not flatten stage policies into BoundaryTurn.

## Run Notes

Overall plan difficulty: 5/5; selected profile: `partnered-5`; because this
milestone touches the main planning loop, loop-control gate, and user-facing
finalization contract.

Use `partnered-5/thorough/high @codex +prep`.

exec
/bin/zsh -lc "sed -n '261,620p' docs/arnold/megaplan-boundary-turn-design.md" in /Users/peteromalley/Documents/Arnold
 succeeded in 0ms:

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
/bin/zsh -lc "sed -n '1,340p' .megaplan/initiatives/boundary-turn-end-to-end/briefs/m3-reducer-stage-boundaries.md" in /Users/peteromalley/Documents/Arnold
 succeeded in 0ms:
# M3: Reducer Stage Boundaries

## Outcome

Implement BoundaryTurn child/reducer semantics for the stages that cannot be
represented as single draft files: execute, parallel/extreme review, and
tiebreaker subpipelines.

## Scope

IN:

- Execute child turns for `execution_batch_N.json` plus an aggregate reducer for
  `execution.json`.
- Execute side-effect evidence for target-repo mutations, approval/preflight,
  timeout recovery, quality gates, blocked-task reset, prerequisite blocks,
  audit/trace output, skipped-review stubs, tier routing, active-step session
  keys, stable batch numbering, and `finalize.json` child updates.
- Review single-worker scratch path plus parallel/extreme child reducer.
- Review infra failure detection, empty-approved backfill, verdict merge into
  finalize projection, maker stop, transition-policy denial, rework caps,
  conditional `review.json` re-promotion, receipts, flag provenance, and
  `final.md` rewrites.
- Tiebreaker researcher/challenger child turns, versioned iterations,
  `gate.json` evidence refs, `tiebreaker_decisions.json`, audits, flag-registry
  mutation checkpoints, and human/replan/revise route choices.

OUT:

- Generic Arnold public recipe.
- New execution/review/tiebreaker product behavior.
- Target-repository rollback.

## Locked Decisions

- Execute cannot be atomic; it records side-effect evidence and supports resume.
- Child turns never write parent artifacts or advance parent state directly.
- Parent state advances only during reducer promotion.
- Review outcome policy and transition-policy denial stay outside BoundaryTurn.
- Reducers validate child evidence before canonical promotion or flag mutation.

## Open Questions

- How much execute/review audit output should be `ExternalEffectRef` versus
  observability event?
- Should tiebreaker reducer reprompts reuse one draft path or versioned attempt
  paths?

## Constraints

- Batch numbering must be stable across resume.
- Parallel review must preserve concerned task IDs, deterministic-check
  evidence, flag IDs, and infra-failure signals.
- Tiebreaker must reject direct child writes to canonical parent artifacts.

## Done Criteria

- Execute tests cover partial resume, stable task-slot mapping, side-effect
  evidence, child `finalize.json` updates, reducer validation, tier routing, and
  timeout/blocked paths.
- Review tests cover simple approve, rework cap, infra failure, parallel
  reducer, transition denial, conditional re-promotion, and flag provenance.
- Tiebreaker tests cover missing evidence, direct canonical write rejection,
  versioned iterations, audit recording, checkpointed flag mutation, and route
  selection.

## Touchpoints

- Execute handler and batch artifacts
- Quality gates, audit/trace writers, resume state
- Review handler, parallel review orchestration, transition policy, final
  projection, flag registry
- Tiebreaker orchestration and flag registry

## Anti-Scope

- Do not make BoundaryTurn the route engine.
- Do not hide execute/review/tiebreaker special cases behind generic code.

## Run Notes

Overall plan difficulty: 5/5; selected profile: `partnered-5`; because reducer
stages have real external side effects, fanout evidence, resume semantics, and
state mutation ordering risks.

Use `partnered-5/thorough/high @codex +prep`.

exec
/bin/zsh -lc "sed -n '1,300p' .megaplan/initiatives/boundary-turn-end-to-end/briefs/m4-recipe-conformance.md" in /Users/peteromalley/Documents/Arnold
 succeeded in 0ms:
# M4: Recipe And Conformance

## Outcome

Turn BoundaryTurn from a Megaplan implementation detail into a reusable Arnold
recipe, then prove no Megaplan stage functionality was lost.

## Scope

IN:

- Generic Arnold-level `BoundarySpec`/validator/promoter protocols or equivalent
  mechanical surface.
- Draft-kind adapters and canonical target declarations that do not depend on
  Megaplan artifact names.
- Runtime event/journal mapping for artifact deltas, state deltas,
  observability events, receipts, and route proposals.
- A small non-Megaplan example using Markdown draft -> validate -> promote.
- Stage preservation matrix covering every Megaplan stage.
- Conformance tests for wrong-path, invalid, unmodified, direct canonical,
  resume, side-effect evidence, reducers, and non-Megaplan clean import.
- Documentation for future pipeline authors.

OUT:

- New phase migrations.
- Reopening architecture settled in M1-M3.
- Migrating unrelated pipelines beyond the proof example.

## Locked Decisions

- The reusable recipe standardizes mechanics, not stage meaning.
- Non-Megaplan adoption must not import Megaplan registries, state classes, or
  artifact names.
- This milestone is an acceptance gate; blockers are regressions against prior
  milestones, not invitations to redesign.

## Open Questions

- Final public module path/name for the neutral protocols.
- How much of the recipe should be public API versus internal Arnold runtime
  helper in this epic.

## Constraints

- The conformance gate must run on the integrated branch.
- Docs must identify stages intentionally left policy-owned.
- The example must prove the recipe is not Megaplan-shaped.

## Done Criteria

- Full test suite plus BoundaryTurn conformance suite passes.
- Stage preservation matrix shows prep, plan, revise, critique,
  critique_evaluator, gate, finalize, execute, review, feedback, and tiebreaker
  behavior preserved or explicitly out of scope.
- A non-Megaplan pipeline uses the draft/capture/validate/promote pattern
  without importing Megaplan.
- Docs provide a standardized recipe others can follow.
- The original design docs are updated to match the implemented end state.

## Touchpoints

- Neutral Arnold runtime/protocol modules
- Megaplan BoundaryTurn adapters
- Example pipeline
- Tests and conformance scripts
- `docs/arnold/megaplan-boundary-turn-design.md`
- `docs/arnold/megaplan-boundary-turn-load-bearing-questions.md`

## Anti-Scope

- Do not add unrelated public API.
- Do not convert additional pipelines beyond the proof example.

## Run Notes

Overall plan difficulty: 4/5; selected profile: `partnered-4`; because the
architecture should be settled by this point, but generic public shape and
conformance still need strong planning.

Use `partnered-4/thorough/medium @codex +prep`.

codex
The BoundaryTurn milestones are coherent but they overlap three different native concerns: native artifact contracts, composition reducers, and platform idempotency. I’m sampling the native briefs now, especially contract, composition, resume, and side-effect milestones, to avoid guessing from milestone names.
exec
/bin/zsh -lc "for f in .megaplan/initiatives/native-platform-followup/briefs/*.md; do printf '\\n### %s\\n' \""'$f"; rg -n "''^#|''^## Outcome|''^## Scope|''^## Done|''^IN:|''^OUT:|Boundary|composition|side-effect|resume|idempot|contract|artifact|state|receipt|checkpoint|execute|review|gate|finalize|durable|security|worker|fleet" "$f" | head -n 140; done' in /Users/peteromalley/Documents/Arnold
 succeeded in 0ms:

### .megaplan/initiatives/native-platform-followup/briefs/m1-side-effect-reconcile-and-idempotency.md
1:# M1 - Side Effect Reconcile And Idempotency
3:## Objective
5:Make native compositional resume safe around real-world side effects. A path
6:resume that restores Python state but ignores the worktree can resume into
7:corruption. This milestone wires side-effect idempotency and worktree
8:reconcile-on-resume into the native execution path.
10:## Prerequisite
15:`.megaplan/initiatives/native-composition-followup/chain.yaml` has completed
18:## Files To Change And Instructions
21:  Invoke reconcile checks before executing a resumed side-effecting step and
23:- `arnold/pipeline/native/checkpoint.py`
24:  Persist enough side-effect metadata to reconcile by path and attempt.
26:  Attach idempotency keys and side-effect class metadata to per-attempt records.
29:  contract for known git/file operations. Include a reconcile-action table for
30:  each supported state: clean, dirty-with-owned-changes, dirty-with-unknown
34:  Ensure worktree state checks can distinguish clean, dirty, in-progress
37:  Connect idempotency-key deduplication to native step execution.
39:  Add fixtures that kill/resume around file writes and git operations.
44:## Verifiable Completion Criterion
46:- Side-effecting steps declare or derive idempotency keys from
50:  state or fails closed with a diagnostic.
52:  state and the metadata required to choose it; unknown states fail closed
54:- Composite resume invokes reconciliation for nested child workflow paths.
58:## Native Representation Alignment
60:- Matrix rows owned or affected: Dependency-aware execute batches; Auto-drive/event/liveness transitions; Behavior parity with existing Megaplan.
61:- Expected status change: platform `enabled` for side-effect safety; it must preserve composition-owned visible routes rather than replacing them with hidden reconcile decisions.
62:- Proof artifacts: idempotency-key tests, reconcile-action table, interrupted git/file resume fixtures, composite path reconcile tests, and fail-closed diagnostics.
63:- False-pass guard: a successful resume that guesses worktree state or silently mutates unknown user changes is not valid proof.
64:- Deferrals: broker approval gates are M2; DB-backed durable storage is M4; worker leases and cancellation are M5.
65:- Canonical paths/imports: reconcile hooks must operate on path/attempt metadata emitted by the composition runtime, not Megaplan handler-local fields.
67:## Risks And Blockers
71:  owned-operation metadata from the checkpoint/effect ledger; user-authored
73:- Worktree ownership belongs to the same project/run lease used by the worker
74:  fleet in M5; this milestone should preserve the hook points even before the
75:  fleet exists.
77:## Dependencies

### .megaplan/initiatives/native-platform-followup/briefs/m2-security-broker-and-approval-gates.md
1:# M2 - Security Broker And Approval Gates
3:## Objective
6:actions behind scoped authority and approval gates. The agent should request
10:## Files To Change And Instructions
12:- `arnold/security/` or an equivalent broker package
22:  gates must state that those paths are not production-covered.
29:  Add approval-gate handling for protected operations: force-push, push to
31:  waits must suspend durably and resume or cancel through the workflow runtime,
37:  Add execute-gate scenarios covering approve, deny, cancel, resume, bare
38:  no-review-to-done, non-review robustness with deferred must criteria to
42:## Verifiable Completion Criterion
51:- Approval-gated operations pause for approval and denial routes into
53:- Approval waits use a documented durable wait primitive. Before M4 this may be
54:  implemented on the existing checkpoint substrate; after M4 it must run on the
55:  DB-backed durable substrate.
59:- Approval/no-review/deferred-human behavior is visible as declared suspension,
61:  `state["meta"]["user_approved_gate"]` alone does not satisfy conformance.
63:## Native Representation Alignment
65:- Matrix rows owned or affected: Human decision/suspension; Execute approval/no-review/deferred-human gates; Override full action surface; Model routing by phase/task complexity.
66:- Expected status change: platform `enabled` for protected action gates and credential policy; composition routes must remain visible.
67:- Proof artifacts: broker threat model, approval approve/deny/cancel/resume tests, no-review/deferred-human scenario tests, branch-policy tests, credential non-exposure tests, audit-log redaction tests, and uncovered-path matrix.
69:- Deferrals: durable approval waits move to the DB-backed backend in M4; fleet-level cancellation is M5; final preservation check is M6.
70:- Canonical paths/imports: approval gates must integrate with declared workflow suspension points, not with private handler waits.
72:## Risks And Blockers
81:  docs, rollout gates, and conformance output.
83:## Dependencies

### .megaplan/initiatives/native-platform-followup/briefs/m3-shared-library-packs-and-versioning.md
1:# M3 - Shared Library Packs And Versioning
3:## Objective
5:Turn compositional workflows into reusable units that can be shared safely.
10:## Files To Change And Instructions
24:  Classify interface changes, removed/renamed units, reordered already-executed
33:## Verifiable Completion Criterion
43:  the nesting/dependency depth bound from the composition contract.
48:## Native Representation Alignment
50:- Matrix rows owned or affected: Source readability; Canonical source path reconciliation; Path-addressed checkpoints.
51:- Expected status change: platform `enabled` for shared unit identity/versioning while preserving the composition contract.
52:- Proof artifacts: pack manifest tests, lockfile/pin tests, transitive dependency query tests, structural diff tests, cycle/depth rejection tests.
55:- Canonical paths/imports: pack metadata must expose stable IDs and declared interfaces from the composition IR, not separate product-specific names.
57:## Risks And Blockers
60:  contract needed for safe reuse.
61:- Stable IDs and declared interfaces from the composition epic are prerequisites;
64:## Dependencies

### .megaplan/initiatives/native-platform-followup/briefs/m4-durable-substrate-and-checkpoint-backend.md
1:# M4 - Durable Substrate And Checkpoint Backend
3:## Objective
5:Make checkpoint, trace, audit, and resume storage backend-swappable and deliver
6:one real DB-backed durable execution backend path. The composition model must
10:## Files To Change And Instructions
12:- `arnold/pipeline/native/checkpoint.py`
13:  Extract checkpoint persistence behind an interface that supports file-backed
16:  Depend on the checkpoint/audit/durable-execution interfaces rather than
17:  hardcoded files. The interface must cover more than CRUD: durable human waits,
18:  resume/reattach, retry state, and child-workflow start/continuation hooks.
21:  checkpoints.
24:  equivalent, for checkpoints, trace indexes, audit skeleton/content refs, and
28:  by an equivalent durable backend. The decision must address the
29:  repeatable-not-deterministic contract, transaction boundaries, operational
32:  Run the same resume/trace/audit/human-gate conformance suite against the file
35:## Verifiable Completion Criterion
37:- Native runtime persistence and durable execution primitives are
42:- Human-gate suspension survives process death and can be reattached by a
49:## Native Representation Alignment
51:- Matrix rows owned or affected: Prep clarification gate; Human decision/suspension; Execute approval/no-review/deferred-human gates; Review infrastructure retry and cap outcomes; Timeout/deadline policy; Auto-drive/event/liveness transitions; Path-addressed checkpoints; Gate flag/debt/fallback handling.
52:- Expected status change: platform `enabled` for durable storage/persistence; report semantics must remain in workflow structure or declared policy.
53:- Proof artifacts: backend-swappable checkpoint tests, DB-backed resume/trace/audit/human-gate suite, event replay tests, liveness policy tests, and DBOS/Postgres decision note.
54:- False-pass guard: moving state into a DB does not prove native representation if route decisions become hidden runtime side effects.
55:- Deferrals: worker leases/cancellation are M5; final platform conformance and preservation checks are M6.
56:- Canonical paths/imports: DB-backed resume must persist and restore composition path identity produced by M4/M5 of the composition epic.
58:## Risks And Blockers
60:- Do not rewrite the composition model to fit a persistence backend.
63:- Do not split leases, checkpoints, trace indexes, and audit storage across
67:## Dependencies

### .megaplan/initiatives/native-platform-followup/briefs/m5-worker-fleet-supervision-and-cancellation.md
1:# M5 - Worker Fleet Supervision And Cancellation
3:## Objective
6:concurrency gates, cancellation, poison-project quarantine, and staggered
10:## Files To Change And Instructions
30:## Verifiable Completion Criterion
32:- Two workers cannot own the same project/worktree simultaneously under normal
34:- A project with an expired lease can be safely claimed by another worker after
35:  reconcile-on-resume.
40:  warn/notify, checkpoint restart where safe, or cancel and flag for human
41:  review.
42:- Concurrency gates prevent configured heavy operations from exceeding capacity
46:## Native Representation Alignment
48:- Matrix rows owned or affected: Dependency-aware execute batches; Review infrastructure retry and cap outcomes; Timeout/deadline policy; Auto-drive/event/liveness transitions.
49:- Expected status change: platform `enabled` for liveness, cancellation, and worker supervision around the already-visible workflow.
50:- Proof artifacts: lease claim/takeover tests, double-run prevention, cancellation tests, stuck-run escalation fixtures, poison quarantine tests, progress-signal tests, and capacity gate tests.
53:- Canonical paths/imports: worker status and cancellation must report stable workflow paths from the composition trace/audit layer.
55:## Risks And Blockers
62:## Dependencies

### .megaplan/initiatives/native-platform-followup/briefs/m6-platform-docs-conformance-and-rollout.md
1:# M6 - Platform Docs, Conformance, And Rollout
3:## Objective
6:boundaries clear: composition is the primitive, platform safety handles
7:side-effects, credentials, shared reuse, durability, and fleet operation.
9:## Files To Change And Instructions
12:  Create or update a platform overview covering reconcile, idempotency,
13:  credential broker, packs/versioning, durable backend, fleet supervision, and
17:- `docs/arnold/security.md`
18:  Document broker posture, scoped credentials, branch policy, approval gates,
23:- `docs/arnold/package-authoring-contract.md`
24:  Add pack/versioning/re-pin guidance without weakening the composition
25:  contract.
29:  call where covered, records forensic audit refs, resumes after interruption
30:  with reconcile on the DB-backed backend, passes through an approval gate, and
33:  PR-merge wait advancement, remote `_capture_sync_state`, and chain state
35:  Rerun the exact composition M6 structural conformance, handler-purity,
37:  and source-path reconciliation suites against the installed package artifact,
64:  `proof_artifacts` for each row. `proof_categories` must cover every proof
65:  label listed in the matching traceability row's `proof_artifacts` field, and
73:  `.yaml`, `.yml`, `.json`, or `.md` policy artifacts.
84:## Verifiable Completion Criterion
88:  shared pack dependency, durable DB-backed checkpoint backend, worker lease,
89:  approval pause/resume, cancellation, stuck-run escalation, and audit lookup.
91:  state, PR helper, and sync-state behavior under the new broker/durable
94:  broker, DB durability, reconcile, worker leases, cancellation, and rollout
103:  completion, delivered by composition, delivered by platform, intentionally
117:  and proof artifacts in a machine-readable form. `python
123:  artifacts needed to audit the three-chain sequence.
125:## Native Representation Alignment
127:- Matrix rows owned or affected: all platform-affected rows in `docs/arnold/megaplan-native-representation-alignment-plan.md`, especially Human decision/suspension; Execute approval/no-review/deferred-human gates; Auto-drive/event/liveness transitions; Golden trace regeneration guard; Canonical source path reconciliation; Behavior parity with existing Megaplan.
129:- Proof artifacts: end-to-end platform conformance scenario, Megaplan chain/PR conformance, installed-package post-hardening structural conformance rerun, handler-purity inventory rerun, mutation/static-topology/scenario/policy/override/source-path reruns, production-covered/local-only matrix, rollout and rollback checklist, final `docs/arnold/megaplan-native-representation-conformance-report.md`, final `docs/arnold/megaplan-native-representation-conformance.yaml`, final conformance YAML validator output, final `proof-map.json`, and final `completion-manifest.json`.
133:  Platform events, manifests, broker hooks, reconcile logic, DB resume, and
134:  worker supervision must remain consumers of compositional source semantics,
137:  completion, delivered by composition, delivered by platform, intentionally
141:  execute/review decisions, replay semantics, or source authority back into
145:## Risks And Blockers
150:  understand every fleet implementation detail.
152:## Dependencies

exec
/bin/zsh -lc "for f in .megaplan/initiatives/native-composition-followup/briefs/*.md; do printf '\\n### %s\\n' \""'$f"; rg -n "''^#|''^## Outcome|''^## Scope|''^## Done|''^IN:|''^OUT:|Boundary|composition|side-effect|resume|idempot|contract|artifact|state|receipt|checkpoint|execute|review|gate|finalize|nested|reducer" "$f" | head -n 140; done' in /Users/peteromalley/Documents/Arnold
 succeeded in 0ms:

### .megaplan/initiatives/native-composition-followup/briefs/m0-composition-contract-and-examples.md
1:# M0 - Composition Contract And Examples
3:## Objective
5:Define the native composition contract before any broad migration hardens the
12:## Prerequisite
18:## Files To Change And Instructions
20:- `docs/arnold/native-composition-contract.md`
21:  Create the contract document. Define:
32:    `critique`, `gate`, `revise`, `tiebreaker`, `finalize`, `execute`, and
33:    `review` must remain accepted aliases where users, profiles, overrides,
46:    substitute, declared policy-call metadata at call sites, nested workflow
48:- `docs/arnold/python-shaped-authoring-contract.md`
49:  Add the V2 authoring-contract scope for compositional source. Define syntax
50:  examples and accepted/rejected fixtures for nested workflow invocation,
61:  - a review/revise loop over recorded state with path-resume comments. The
66:  Add or plan the decorator metadata needed by the contract: stable `id`,
74:  Add contract-level tests or pending conformance fixtures for the examples.
76:## Verifiable Completion Criterion
78:- The composition contract names the invocable interface and makes stable IDs,
81:- The contract defines how legacy stage names map to stable IDs during
87:  ordinary control flow, and function calls. Path resume is demonstrated as a
89:- The follow-up milestones can cite this contract instead of inventing local
91:- Canonical Megaplan M1 is blocked on this contract and may not introduce
93:- The contract states that Megaplan fanout, execute DAG, review checks, policy
96:- The Python-shaped authoring contract has a V2 section or follow-up contract
98:  fixtures for composition features needed by Megaplan.
100:## Native Representation Alignment
102:- Matrix rows owned or affected: Runtime-list iteration; Dynamic parallel map; Typed loop outcomes or break/continue; Path-addressed checkpoints; Trace-only native shadow topology; Bounded critique/gate/revise loop.
103:- Expected status change: `enabled` by defining the authoring language and shadow-topology contract M1 must satisfy.
104:- Proof artifacts: native composition contract, aspirational examples, expected-failing or compiling fixtures, stable ID/path rules, accepted/rejected syntax fixtures, and explicit fixtures for runtime-list fanout, typed loop exits, policy calls, nested invocation, and Megaplan-only helper rejection.
106:- Doctrine gate: M0 must explicitly define the source/manifest/native_program
107:  relationship. Author-written compositional Python source owns Megaplan
114:## Risks And Blockers
117:  composition work. This milestone defines metadata foundations, not the pack
120:  but the contract must present the user-facing two-kind model clearly.
122:## Dependencies
124:- First milestone of the native composition follow-up epic.

### .megaplan/initiatives/native-composition-followup/briefs/m1-megaplan-compositional-migration.md
1:# M1 - Megaplan Compositional Migration
3:## Objective
5:Migrate canonical Megaplan into the new compositional workflow format as the
6:first real proof target after M0 defines the contract. Megaplan should be
8:review/revise/execute loops represented as workflow structure rather than
11:invent one-off semantics outside the M0 contract.
13:## Prerequisite
19:## Files To Change And Instructions
22:  Rework the canonical Megaplan declaration into compositional units. Split the
23:  top-level workflow into explicit nested native workflows where the domain has
24:  real boundaries: planning/prep, critique/revise loop, gate/tiebreaker handling,
25:  finalize/execute/review, and any human-gated continuation path. Every
27:  M0 contract.
39:  dispatching the compositional Megaplan workflow. If it does not exist, the
57:  Add only the compiler support needed by canonical Megaplan's compositional
63:  Support the Megaplan composition shape without changing unrelated runtime
67:  Add or update tests proving the compositional Megaplan workflow preserves the
69:  execute/review, human-gated continue, and abort/stop paths. Add a Megaplan
76:  prep blocking questions and resume-clarify; imported criteria in declared
77:  plan outputs; tiebreaker `pick`, `escalate`, and `replan`; finalize task
79:  `user_actions.md`, before/after execute actions, and synthetic
80:  before-execute gate; approve, deny, cancel, resume, bare no-review-to-done,
81:  non-review robustness with deferred must criteria to human verification;
82:  below-cap review rework, at-cap deterministic blocker escalating through a
84:  force-proceed/done, and infra failure retry-to-review.
85:- `docs/arnold/megaplan-artifact-manifest.md`
86:  Create or update a golden artifact manifest for migrated Megaplan runs,
87:  including expected files and schema keys for proceed, review-needs-rework, and
88:  execute failure/resume paths. Cover `review.json`, `finalize.json`,
89:  `final.md`, `execution_audit.json`, receipt metrics, warrant source refs, and
104:  fanout, retry, suspension, override dispatch, or implicit state transition.
106:## Verifiable Completion Criterion
108:- Canonical Megaplan is authored as a composition of native workflows and steps,
112:  interface rather than ambient state reach-through.
116:  Megaplan pipeline through the native-first contract.
118:  proceed, iterate/revise, tiebreaker, escalation, execute/review, human-gated
125:- The Megaplan artifact manifest is produced and tested against at least the
126:  proceed, review-needs-rework, and execute failure/resume paths.
131:  which artifacts are source authority, compiled manifest/runtime output, and
140:  conformance/mutation gates pass.
141:- The milestone produces `docs/arnold/megaplan-composition-handoff.md`, listing
159:## Native Representation Alignment
161:- Matrix rows owned or affected: Prep clarification gate; Plan artifact/version metadata; Critique skip on bare robustness; Adaptive critique evaluator retry; Parallel critique lenses with fan-in; Bounded critique/gate/revise loop; Gate preflight and payload normalization; Gate signal building and reprompt; Gate flag/debt/fallback handling; Tiebreaker researcher/challenger path; Human decision/suspension; Finalize fallback routes; Dependency-aware execute batches; Execute approval/no-review/deferred-human gates; Execute/review/rework loop; Review parallel checks/fan-in; Review infrastructure retry and cap outcomes; Override full action surface; Timeout/deadline policy; Model routing by phase/task complexity; Runtime-list iteration; Dynamic parallel map; Typed loop outcomes or break/continue; Auto-drive/event/liveness transitions; Trace-only native shadow topology; Handler topology extraction/purity audit; Behavior parity with existing Megaplan; Source readability.
162:- Expected status change: composition-owned rows should move from `enabled` planning status toward implementation evidence, except any explicitly deferred platform durability rows. M1 may not mark a report row `implemented` unless it also lands wrapper-detection conformance for that row; otherwise implementation status waits for M2 validator/source-invariant checks and M6 structural conformance/mutation gates.
163:- Proof artifacts: source excerpts from canonical Megaplan workflow, source-path reconciliation table, per-row semantics carrier table, rendered topology with untaken branches, handler inventory, artifact manifest, D1/D5/D6/D8/D10 scenario goldens, override matrix, and `megaplan run`/`arnold pipelines` compatibility tests.
164:- False-pass guard: wrapping old handlers in native nodes is not enough. The milestone must fail if `critique`, `gate`, `tiebreaker`, `execute`, `review`, or `override` are single handler-backed stages that still own product routing.
165:- Doctrine gate: M1 is the first real proof of the final Megaplan authoring
166:  doctrine. It must prove compositional source owns report semantics and that
167:  manifests/native shells are derived artifacts, not parallel semantic owners.
171:## Risks And Blockers
173:- Megaplan is the highest-risk workflow because it exercises loops, gates,
174:  overrides, execution, review, artifacts, and resume.
175:- A superficially clean nested declaration can still break route labels,
176:  envelope joins, artifact ownership, or human-gate resume.
180:  covered by M0, update the contract explicitly before landing the migration.
182:## Dependencies

### .megaplan/initiatives/native-composition-followup/briefs/m2-routing-validator-and-authoring-boundary.md
1:# M2 - Routing Validator And Authoring Boundary
3:## Objective
7:and safe to replay. This validator must gate Megaplan's compositional workflow
8:before general nesting, tree traces, or composite resume depend on it.
10:## Files To Change And Instructions
23:  Ensure the compositional Megaplan workflow validates under the new rules.
29:  recorded state, and replay-consistency failure cases the validator cannot
32:  Ensure the compositional Megaplan workflow passes the validator.
34:## Verifiable Completion Criterion
40:- Megaplan's compositional workflow validates cleanly.
42:- A replay-consistency fixture exists: run, interrupt, resume, and assert the
43:  resumed final structure/state is equivalent to an uninterrupted run.
45:  handler-local `current_state`, `next_step`, `workflow_transition`,
46:  `run_parallel_*`, override action dispatch, or equivalent implicit state
52:## Native Representation Alignment
54:- Matrix rows owned or affected: Bounded critique/gate/revise loop; Gate preflight and payload normalization; Gate signal building and reprompt; Gate flag/debt/fallback handling; Review infrastructure retry and cap outcomes; Override full action surface; Typed loop outcomes or break/continue; Handler topology extraction/purity audit.
56:- Proof artifacts: routing validator tests, line-specific diagnostics, replay-consistency fixture, Megaplan validator pass, generic-coupling/semantic-vocabulary scans, and source-invariant scans for retained handlers.
57:- False-pass guard: a readable workflow that routes through hidden state mutation, nondeterministic calls, or handler-owned `next_step` changes must fail validation or conformance.
58:- Deferrals: static tree snapshots and path resume proofs remain M4/M5; production event replay and durability remain platform M4/M6.
61:## Risks And Blockers
70:## Dependencies

### .megaplan/initiatives/native-composition-followup/briefs/m3-general-nested-workflow-invocation.md
1:# M3 - General Nested Workflow Invocation
3:## Objective
5:Generalize the nested workflow support proven by Megaplan so any native workflow
8:composition nodes satisfying the M0 invocable interface, not as package-specific
11:## Files To Change And Instructions
14:  Implement or finalize workflow metadata for stable unit IDs, declared inputs,
17:  Lower nested `@pipeline` / `@workflow` invocations into child workflow
21:  for selected critique/review checks and execute batches; literal-only
25:  `docs/arnold/python-shaped-authoring-contract.md`
37:  the default contract.
39:  Project nested workflows in a way that preserves the compatibility shell
40:  without flattening away all composition information needed by tooling.
42:  Cover nested workflow lowering, duplicate child names, stable IDs, unsupported
47:  Add V2 authoring diagnostics and source fixtures for nested invocation,
51:  Cover parent/child execution, child state isolation, typed output merge,
54:## Verifiable Completion Criterion
62:- Megaplan's M1 compositional declaration uses only the general support from
64:- Megaplan fanout, execute batching, review fanout, typed loop exits, and
71:## Native Representation Alignment
73:- Matrix rows owned or affected: Parallel critique lenses with fan-in; Tiebreaker researcher/challenger path; Dependency-aware execute batches; Review parallel checks/fan-in; Runtime-list iteration; Dynamic parallel map.
74:- Expected status change: Megaplan-only composition support must become general native support before rows can be considered implemented.
75:- Proof artifacts: nested invocation compiler/runtime tests, repeated child workflow tests, depth-3 nesting, runtime-list fanout fixtures for critique/review/execute, typed loop outcome fixtures, policy-call metadata fixtures, cycle/dynamic-dispatch rejection tests, and Megaplan-only helper rejection tests.
76:- False-pass guard: if fanout, tiebreaker, or execute batching work only through a bespoke Megaplan helper, the row remains a false pass.
77:- Deferrals: tree rendering/audit snapshots are M4; resume-from-path is M5; production worker hardening is platform M5.
80:## Risks And Blockers
83:  composition information that M4 needs for static graph and tree traces.
85:  copied parent state rather than explicit outputs.
88:## Dependencies

### .megaplan/initiatives/native-composition-followup/briefs/m4-tree-graph-trace-and-audit-skeleton.md
1:# M4 - Tree Graph, Trace, And Audit Skeleton
3:## Objective
6:composition graph, a tree-shaped run trace, stable path addressing, and a
10:## Files To Change And Instructions
13:  Emit or expose the static composition tree for workflows, including untaken
22:  Emit tree-aware run trace events and durable trace artifacts. Preserve enough
23:  data to render a nested run and query any executed node by path.
28:  logically separate from operational checkpoints even if the initial storage is
33:- `arnold/pipeline/native/checkpoint.py`
37:  Add golden fixtures for nested traces, static graph queries, repeated child
41:  Update Megaplan compositional trace expectations so the major subworkflows
44:  subworkflow with `pick`, `escalate`, and `replan` decision routes; review
45:  `criteria_verdict`, every selected review-check child, reducer/fan-in, and
46:  infra-retry trace; and execute DAG/batch children rather than a single opaque
47:  execute node.
49:## Verifiable Completion Criterion
53:- Native traces represent executed nested workflows as a tree, not only as an
58:  display labels, and the contract states whether a rename is breaking or
64:- Existing non-nested workflows still produce usable traces.
65:- The static topology snapshot includes untaken tiebreaker `replan`, review
66:  fanout/reducer, execute-batch, approval/deferred-human, and no-review routes.
68:  node, collection schema, mapper, reducer/fan-in, declared policy, and stable
73:## Native Representation Alignment
75:- Matrix rows owned or affected: Tiebreaker researcher/challenger path; Dependency-aware execute batches; Execute/review/rework loop; Review parallel checks/fan-in; Path-addressed checkpoints; Handler topology extraction/purity audit; Behavior parity with existing Megaplan.
77:- Proof artifacts: static derived graph snapshots with untaken branches, nested trace goldens, per-attempt audit skeletons, Megaplan compositional trace expectations, tiebreaker `replan` topology, review fanout/reducer topology, execute DAG topology, infra-retry trace, and failed-attempt audit tests.
82:- Deferrals: kill/resume from nested paths is M5; broker content logs and DB audit storage are platform M2/M4.
85:## Risks And Blockers
89:- Path stability is a contract. Do not base it on incidental program counters
95:## Dependencies

### .megaplan/initiatives/native-composition-followup/briefs/m5-composite-resume-and-start-from-path.md
1:# M5 - Composite Resume And Start From Path
3:## Objective
5:Make resume work through nested workflows and loops using path as the primary
6:address. A run suspended inside a child workflow must resume at the child path
10:## Files To Change And Instructions
12:- `arnold/pipeline/native/checkpoint.py`
14:  fail-closed native cursor validation. Path is the primary resume locator; PC
22:  Mark suspension and resume events at the path where they occur.
23:- `arnold/pipeline/resume.py`
24:  Route native path-based resume through the native runtime contract. Preserve
25:  or migrate existing Megaplan resume file surfaces: `state.json::resume_cursor`,
26:  `resume_cursor.json`, `composite_resume_cursor.json`, `awaiting_user.json`,
27:  typed suspended `contract_result`, and fail-soft extraction.
29:  Add kill/suspend/resume tests for child workflows, loops inside child
30:  workflows, repeated child call sites, depth-3 nested resume, and loop
33:  Prove Megaplan can resume from inside its compositional critique/revise,
34:  tiebreaker, execute/review, and human-gated paths. Include backward-compatible
35:  tests for every existing Megaplan cursor source and for human-gate continue
36:  repointing the primary input to the latest edited artifact.
37:  Include execute-gate resume scenarios for approve, deny, cancel, resume,
38:  bare no-review-to-done, deferred-human verification, and protected action
41:## Verifiable Completion Criterion
43:- Resume from inside a nested workflow succeeds without duplicating completed
45:- Resume from inside a loop inside a nested workflow succeeds, with loop frames
47:- `kill -9` / process interruption during a child workflow phase can be resumed
50:  nested Megaplan path and one neutral native fixture.
51:- Existing Megaplan resume file surfaces either continue to work through
52:  `arnold.pipeline.resume` or fail closed with a migration diagnostic; no
54:- Human-gated continue preserves the current behavior of resuming from the
55:  user's latest edited artifact rather than stale pre-gate input.
57:  supplied state against declared interfaces where available.
58:- Replay-consistency CI covers at least one nested loop: run uninterrupted, run
59:  with interruption/resume, and assert equivalent final structure/state.
61:## Native Representation Alignment
63:- Matrix rows owned or affected: Prep clarification gate; Human decision/suspension; Execute approval/no-review/deferred-human gates; Execute/review/rework loop; Path-addressed checkpoints; Auto-drive/event/liveness transitions.
64:- Expected status change: suspension/resume rows gain implementation proof on the file-backed/native substrate; DB-backed durability remains platform-owned.
65:- Proof artifacts: kill/suspend/resume tests for child workflows and loops, Megaplan resume tests for critique/revise/tiebreaker/execute/review/human paths, execute-gate resume tests for approve/deny/cancel/no-review/deferred-human/protected action paths, legacy cursor compatibility tests, start-from-path fixture, replay-consistency CI.
66:- False-pass guard: resume must start from persisted path coordinates, not handler-local fields or implicit `current_state` guesses.
67:- Deferrals: DB-backed resume, durable human wait reattach, cancellation, and reconcile-on-resume are platform M1/M4/M5.
68:- Canonical source paths/imports: every migrated Megaplan cursor surface must route through `arnold.pipeline.resume` or fail closed with a migration diagnostic.
70:## Risks And Blockers
72:- Side effects do not replay. This milestone must test idempotency expectations
73:  for side-effecting steps, but full git/worktree reconcile belongs to the
81:## Dependencies

### .megaplan/initiatives/native-composition-followup/briefs/m6-composition-docs-and-conformance.md
1:# M6 - Composition Docs And Conformance
3:## Objective
5:Turn the implemented composition model into the documented and tested Arnold
6:authoring contract. Docs, scaffolds, and conformance suites should teach the
7:actual end state for this epic: stable invocable steps/workflows, declared
8:inputs/outputs, workflow-in-workflow composition, loops over recorded state,
9:static graph queries, tree traces, per-attempt audit skeletons, and path resume.
11:## Files To Change And Instructions
14:  Document compositional workflows, stable IDs, declared interfaces, nested
16:- `docs/arnold/package-authoring-contract.md`
17:  Update package-level expectations for compositional workflows and stable
20:  Add examples for a single workflow, a nested workflow, a loop over recorded
21:  state, repeated child workflow use, and a path-resume scenario.
22:- `docs/arnold/native-composition-contract.md`
23:  Ensure the final implemented contract matches the M0 contract, or update the
24:  contract with deliberate decisions made during implementation.
26:  Ensure generated scaffolds use the compositional format and no shim/fallback
27:  package pattern. The scaffold should generate a small compositional example,
30:  Update template code and skill instructions to the compositional contract.
32:  Add a conformance suite for composition: nested invocation, tree trace,
33:  static graph queries, per-attempt audit skeleton, composite resume, routing
38:  fixed scenario manifest for D1-D15: prep blocking/resume-clarify and imported
39:  criteria outputs; critique variants/retry/fanout/fallback; gate
42:  critique/gate/revise cap/no-progress/severity termination, including
44:  tiebreaker pick/escalate/replan; finalize task generation, scoped/full
46:  finalize failure golden, `user_actions.md`, before/after execute actions, and
47:  synthetic before-execute gate; execute DAG, approval, no-review,
48:  deferred-human and protected actions; review fanout, reducer ordering, infra
52:  runtime-list fanout; typed loop exits; trace/resume; and handler extraction.
56:## Verifiable Completion Criterion
58:- A new author following docs/scaffolds writes the compositional format by
60:- Documentation includes Megaplan as the real-world compositional reference.
61:- Conformance tests lock stable unit IDs, declared interfaces, nested
63:  per-attempt audit skeletons, and composite resume as public behavior.
64:- Conformance includes a replay-consistency gate: run an equivalent nested
65:  workflow uninterrupted and with interruption/resume, then assert the final
66:  state and committed side-effect record are equivalent.
67:- Structural conformance fails if `critique`, `gate`, `tiebreaker`, `execute`,
68:  `review`, or `override` remain single handler-backed stages or if a report
70:  implicit `current_state`/`next_step` mutation.
71:- Review cap conformance fails if cap-exhausted blocking review outcomes are
72:  represented only by retained review-handler mutation of `STATE_BLOCKED`,
73:  `resume_cursor`, `current_state`, or `next_step`; the canonical workflow
85:  artifact-contract, or suspension policies do not count unless the compiled
90:- Docs are explicit that this epic delivers composition on the existing native
93:  covered by the platform follow-up epic, not by this composition epic.
95:  `docs/arnold/megaplan-composition-conformance-report.md`, an explicit
96:  `proof-map.json` for the composition chain, and
97:  `.megaplan/initiatives/native-composition-followup/completion-manifest.json`
99:  .megaplan/initiatives/native-composition-followup/chain.yaml --proof-map
102:## Native Representation Alignment
104:- Matrix rows owned or affected: all composition-owned rows in `docs/arnold/megaplan-native-representation-alignment-plan.md`, especially Source readability; Handler topology extraction/purity audit; Golden trace regeneration guard; Behavior parity with existing Megaplan.
105:- Expected status change: no composition-owned row may remain `missing` or merely planning-only `enabled`; each must be `implemented` with proof or explicitly `deferred` to a downstream owner.
106:- Proof artifacts: row-by-row alignment proof, structural conformance test, handler-purity inventory and scans, mutation tests moving logic back into handlers, fixed D1-D15 scenario manifest, generated override action matrix, rendered policy view, static topology snapshots, rendered topology diff, docs/scaffold tests, installed-package smoke test, source-path reconciliation proof, `docs/arnold/megaplan-composition-conformance-report.md`, the explicit `proof-map.json` used for platform handoff, and the generated `completion-manifest.json`.
108:- Doctrine gate: final docs and conformance must prove that canonical
109:  compositional source is the semantic authority, `WorkflowManifest` is the
110:  compiled runtime/replay/inspection artifact, and `Pipeline.native_program`
120:## Risks And Blockers
123:  generated artifact check.
127:  composition system for the full production operating model described in the
130:## Dependencies

exec
/bin/zsh -lc "for f in .megaplan/initiatives/native-python-pipelines-completion/briefs/*.md; do printf '\\n### %s\\n' \""'$f"; rg -n "''^#|''^## Outcome|''^## Scope|''^## Done|''^IN:|''^OUT:|Boundary|composition|side-effect|resume|idempot|contract|artifact|state|receipt|checkpoint|execute|review|gate|finalize" "$f" | head -n 120; done' in /Users/peteromalley/Documents/Arnold
 succeeded in 0ms:

### .megaplan/initiatives/native-python-pipelines-completion/briefs/m1-platform-contract.md
1:# M1 - Platform Contract
3:## Objective
7:## Files To Change And Instructions
20:  Export the compiler, projection, runtime, and resume helpers package authors will use after M1.
33:- `arnold/pipeline/resume.py`
34:  Route resume through the native runtime contract and remove assumptions that continuation always means "build another graph."
36:  Point pipeline CLI entrypoints at the native-first contract and stop presenting graph runtime as canonical.
38:  Align `arnold pipelines check` and `arnold pipelines describe` with the new projected-shell-plus-`native_program` contract.
49:- `tests/arnold/pipeline/test_resume.py`
50:  Verify resume works through the native-backed contract.
60:  Verify registry and manifest discovery stay aligned after the M1 contract change.
63:- `tests/resume/test_pre_m6_alias.py`
68:  Keep end-to-end `pipelines check` coverage aligned with the new validator contract.
70:## Verifiable Completion Criterion
77:## Native Representation Alignment
79:- Matrix rows affected: Plan artifact/version metadata; Path-addressed checkpoints; Canonical source path reconciliation; Behavior parity with existing Megaplan.
80:- Expected status change: substrate `enabled` only. This milestone creates native execution, resume, registry, and projection truth; it does not claim Megaplan report conformance.
81:- Proof artifacts: executor-selection tests, registry/validator tests, resume-through-native tests, projected-shell `native_program` assertions, and CLI describe/run coverage.
83:- Doctrine gate: `Pipeline.native_program` is a dispatch and compatibility
86:- Deferrals: visible Megaplan product control flow remains owned by native composition M1/M6; durable human waits remain owned by platform M4/M6.
89:## Risks And Blockers
95:## Dependencies
98:- M2 through M7 all depend on this contract being in place before package-level cleanup starts.

### .megaplan/initiatives/native-python-pipelines-completion/briefs/m2-megaplan-subpipelines-layout.md
1:# M2 - Megaplan Subpipelines Layout
3:## Objective
7:## Files To Change And Instructions
56:## Verifiable Completion Criterion
62:## Native Representation Alignment
65:- Expected status change: substrate `enabled` only. This milestone stabilizes package paths so later report-conformance reviews inspect the live source.
66:- Proof artifacts: import smoke tests for normalized package names, stale-path search results, and updated CLI/package references.
67:- False-pass guard: moving files without proving the registered package/import path changed leaves reviewers auditing stale source.
68:- Deferrals: no report-level Megaplan semantics are implemented here; those remain owned by completion M3.5/M5 and composition M1/M6.
71:## Risks And Blockers
74:- `writing_panel_strict` has human-gate behavior, so layout changes must not hide accidental runtime changes.
77:## Dependencies

### .megaplan/initiatives/native-python-pipelines-completion/briefs/m3-5-canonical-megaplan-migration.md
1:# M3.5 - Canonical Megaplan Migration
3:## Objective
5:Migrate the canonical `megaplan` pipeline, native runner, and auto-drive path onto the native-first contract before test cleanup so the repo no longer depends on stage-order heuristics, bundle-carried execution metadata, or legacy topology-hash assumptions for the flagship workflow. This is substrate migration only: it must not claim final Megaplan authoring conformance unless the product semantics are visible in canonical workflow source, declared policy, or audited pure phase bodies.
7:## Files To Change And Instructions
18:  Make canonical Megaplan metadata and package exports resolve through the native-first contract. Before editing, verify whether this path is a live source path or a stale migration target; current proofs must name the actual `arnold_pipelines/...` source if that is what CLI/package registration uses.
20:  Rewrite canonical `build_pipeline(...)` so it compiles the native declaration, projects the compatibility shell, attaches `native_program`, and stops encoding execution state through `resource_bundles` strings or `_LEGACY_STAGE_ORDER`-style shortcuts. Verify this is the live canonical source before implementation; if it is only a migration-target path, update the source-path reconciliation table instead of silently editing a dead path.
27:  Route auto-drive, resume, and recovery through the canonical native-backed pipeline instead of graph-era runner assumptions.
41:  Keep driver-lock behavior stable after the runtime contract change.
47:  Assert the canonical auto path now runs against the native-backed contract.
54:- `tests/arnold/conformance/test_megaplan_coupling_gate.py`
55:  Keep the coupling gate aligned with the migrated canonical contract.
56:- `tests/arnold/pipeline/native/test_resume_routing.py`
57:  Assert native resume routing no longer depends on Megaplan-specific stage-order heuristics.
66:- `tests/arnold/pipelines/megaplan/test_pipeline_contracts.py`
67:  Assert canonical Megaplan now satisfies the same `native_program` contract as the subpipelines.
69:## Verifiable Completion Criterion
72:- `native_runner.py` and `auto.py` execute canonical Megaplan through `native_program` rather than stage-order strings or graph-first bundle payloads.
75:## Native Representation Alignment
77:- Matrix rows affected: Plan artifact/version metadata; Auto-drive/event/liveness transitions; Behavior parity with existing Megaplan; Canonical source path reconciliation.
79:- Proof artifacts: native runner/auto-drive tests, routing-heuristic deletion proof, canonical Megaplan native contract tests, characterization/golden updates with semantic diff notes.
80:- False-pass guard: `native_program` plus removed stage-order heuristics can still be a false pass if `critique`, `gate`, `execute`, `review`, or `override` remain opaque handler-backed nodes.
81:- Doctrine gate: `native_program` is compatibility dispatch proof, not final
85:- Deferrals: visible critique/gate/tiebreaker/execute/review structure remains owned by composition M1/M6; platform durability remains owned by platform M4/M6.
88:## Risks And Blockers
90:- This is the highest-risk migration outside `evidence_pack` because it touches the flagship runtime, CLI, auto drive, resume, and characterization goldens together.
94:## Dependencies
97:- Must finish before M4 shares the final resume contract broadly and before M5 rewrites test truth around native execution.

### .megaplan/initiatives/native-python-pipelines-completion/briefs/m3-root-and-shared-package-migrations.md
1:# M3 - Root And Shared Package Migrations
3:## Objective
5:Migrate the shared package set that is closest to the final contract so each package returns a projected `Pipeline` shell with `native_program`, keeps only private legacy graph baselines where strictly required, and stops depending on graph-first discovery or runtime assumptions.
7:## Files To Change And Instructions
10:  Move package metadata and `build_pipeline(...)` to the final contract and stop exporting graph-first behavior as canonical.
18:  Update runtime assertions to the native-backed package contract.
23:  Move package metadata and `build_pipeline(...)` to the final contract.
33:  Keep doc-assembly behavior aligned with the migrated package contract.
38:  Move metadata and `build_pipeline(...)` to the final native-backed contract.
44:  Create the native declaration; keep `_JokesNativeAdapter` only if it is still needed for config-to-state wiring.
46:  Update contract expectations to `native_program` plus projected-shell behavior.
59:  Keep repair behavior compatible with the native runtime contract.
65:  Update the package-contract assertions.
78:  Finish the final-contract migration started in M2.
80:  Preserve exact `continue` and `stop` gate semantics under native suspension and resume.
86:  Keep end-to-end behavior constant while shifting the runtime contract.
93:  Keep end-to-end behavior stable under the migrated contract.
100:  Create the native declaration and replace hardcoded candidate assumptions with argument-driven state wiring.
106:  Keep package-contract coverage aligned with the migrated package.
111:  Move metadata and `build_pipeline(...)` to the final contract.
113:  Remove assumptions that native execution requires graph flattening or env-gated runtime.
117:  Update runtime and contract assertions to the final native-backed package shape.
120:  Stop overloading `build_pipeline()` for discovery vs runtime and move to the final contract.
126:  Keep package metadata aligned with the required final contract.
134:  Update contract assumptions to the new package shape.
138:  Ensure the contract cleanup does not leak old import surfaces.
140:## Verifiable Completion Criterion
143:- `creative`, `doc`, `jokes`, `live_supervisor`, `writing_panel_strict`, `epic_blitz`, `select_tournament`, `folder_audit`, and `deliberation` are validator-clean under the M1 contract.
146:## Native Representation Alignment
148:- Matrix rows affected: Plan artifact/version metadata; Canonical source path reconciliation; Behavior parity with existing Megaplan.
149:- Expected status change: substrate `enabled` by proving the native-first contract works across multiple real packages before canonical Megaplan M3.5.
150:- Proof artifacts: package contract tests, validator-clean package assertions, native-truth runtime tests, and explicit private-baseline inventory for any remaining graph builders.
152:- Deferrals: canonical Megaplan flagship behavior remains M3.5; final trace/golden cleanup remains M5; report-level composition conformance remains the composition epic.
155:## Risks And Blockers
159:- `live_supervisor` spans multiple modules, so package-contract cleanup can leave behind split-brain builder logic unless it is tightened deliberately.
161:## Dependencies

### .megaplan/initiatives/native-python-pipelines-completion/briefs/m4-evidence-pack-native-migration.md
1:# M4 - Evidence Pack Native Migration
3:## Objective
5:Migrate `evidence_pack` to the native-first contract, including shared native suspension and resume, while preserving ingest, fanout, reduction, human review, attestation, and downstream example behavior.
7:## Files To Change And Instructions
10:  Move metadata and `build_pipeline(...)` to the final projected-shell-plus-`native_program` contract.
12:  Create the native declaration for ingest, validator fanout, reduction, human review, and attestation emission.
19:- `arnold/pipelines/evidence_pack/resume.py`
20:  Remove package-specific continuation architecture and route resume through shared native runtime semantics.
22:  Keep verification and attestation behavior aligned with the migrated pipeline contract.
24:  Update the example package exports to stop importing graph-era review concepts.
26:  Repoint example construction to the migrated `evidence_pack` contract.
30:  Keep the end-to-end review lifecycle stable under the native-backed contract.
32:  Rework hooks coverage around the new runtime-neutral contract.
35:- `tests/arnold/pipelines/evidence_pack/test_resume.py`
36:  Verify shared native suspension and resume behavior.
42:  Keep expressibility coverage aligned with the migrated declaration and resume contract.
43:- `tests/arnold/pipeline/test_composite_resume.py`
44:  Update shared resume coverage if `evidence_pack` changes the common continuation path.
46:## Verifiable Completion Criterion
49:- Human review and resume flow through shared native runtime semantics rather than package-specific continuation builders.
50:- The named end-to-end, resume, conformance, and expressibility tests all pass against the migrated package contract.
52:## Native Representation Alignment
54:- Matrix rows affected: Human decision/suspension; Path-addressed checkpoints; Behavior parity with existing Megaplan.
55:- Expected status change: substrate `enabled` by proving shared native suspension/resume works outside Megaplan.
56:- Proof artifacts: evidence-pack resume tests, human-review suspension tests, conformance fixture, and expressibility coverage.
57:- False-pass guard: a package-specific continuation builder or handler-local wait state would not prove the shared suspension primitive Megaplan needs.
58:- Deferrals: Megaplan-specific human gates and resume paths remain owned by composition M1/M5 and platform M4/M6.
59:- Canonical paths/imports: record any shared resume/import surfaces changed so Megaplan M3.5/M5 can depend on the same contract.
61:## Risks And Blockers
63:- `evidence_pack` combines fanout, reduction, human review, and continuation, so it is easy to get a structurally valid but behaviorally wrong migration.
65:- Shared resume changes can regress other human-gated packages if the common contract is not stable after M3.5.
67:## Dependencies

### .megaplan/initiatives/native-python-pipelines-completion/briefs/m5-native-test-and-golden-trace-cleanup.md
1:# M5 - Native Test And Golden Trace Cleanup
3:## Objective
5:Replace the old graph-parity and graph-baseline test contract with native-truth tests and native-owned golden traces, while explicitly naming every old-contract suite that must be rewritten, narrowed, or deleted.
7:## Files To Change And Instructions
14:  Delete or rewrite into direct projection-contract coverage that no longer treats graph parity as the oracle.
15:- `tests/parity/test_no_state_carry.py`
16:  Fold the useful state-carry assertions into a native-truth suite.
24:  Delete or rewrite as topology-contract coverage that does not compare against the graph runtime.
25:- `tests/test_workflow_topology_parity_gate.py`
26:  Delete or rewrite as a native-contract gating test.
28:  Delete or rewrite as behavior coverage under the native contract.
31:- `tests/_pipeline/test_receipt_planning_parity.py`
32:  Delete or rewrite as receipt behavior coverage under the native path.
34:  Remove graph-parity posture; keep only direct projection or execution contract checks that still matter.
67:- `tests/arnold/pipelines/megaplan/test_step_contracts_parity.py`
68:  Rewrite as direct step-contract coverage.
75:- `tests/arnold/pipelines/megaplan/data/native_parity/execute_review_artifact_golden_graph_trace.json`
77:- `tests/arnold/pipelines/megaplan/data/native_parity/happy_finalize_golden_graph_trace.json`
85:- `tests/arnold/pipelines/megaplan/data/native_parity/suspension_resume_golden_graph_trace.json`
90:## Verifiable Completion Criterion
92:- Every named old-contract suite has been either rewritten, narrowed into one deliberate legacy suite, or deleted.
96:## Native Representation Alignment
98:- Matrix rows affected: Plan artifact/version metadata; Golden trace regeneration guard; Behavior parity with existing Megaplan.
99:- Expected status change: substrate `enabled` with fixed native-truth scenarios and a regeneration guard; final report conformance still waits on composition M6.
100:- Proof artifacts: golden scenario manifest, semantic diff checklist, rewritten native-truth tests, and an explicit legacy-baseline inventory.
101:- False-pass guard: tests must fail on unreviewed regenerated goldens; green tests after overwriting trace fixtures are not proof.
102:- Deferrals: static topology snapshots with untaken branches and handler-purity conformance remain owned by composition M4/M6.
105:## Risks And Blockers
111:## Dependencies

### .megaplan/initiatives/native-python-pipelines-completion/briefs/m6-docs-and-scaffolds-native-first.md
1:# M6 - Docs And Scaffolds Native First
3:## Objective
9:large positive authoring story that the composition follow-up epic will replace.
18:## Files To Change And Instructions
20:- `docs/arnold/package-authoring-contract.md`
22:  native-first package contract narrowly: `build_pipeline(...)` returns a
25:  examples as the final long-term composition model.
26:- `docs/arnold/package-contract.md`
28:  registry/discovery contract as the only supported package shape for new work.
32:  composition guidance would be needed, point to the forthcoming native
33:  composition contract instead of teaching an intermediate flat-native idiom.
40:  claiming to define the future compositional authoring model.
42:  Update the example to `select_tournament` and the migrated package contract.
45:  `MEGAPLAN_M6_MANIFEST_DISCOVERY` as a real rollout gate.
55:  package contract.
64:  contract.
65:- `tests/arnold/pipelines/test_package_authoring_contract.py`
66:  Update contract expectations to the native-first package shape and assert new
77:## Verifiable Completion Criterion
85:- M6 does not claim to be the final compositional authoring guide. Any deeper
86:  examples involving workflow nesting, tree traces, path resume, stable unit
87:  IDs, or invocable interfaces are explicitly left to the native composition
94:## Native Representation Alignment
97:- Expected status change: substrate `enabled` for native-first docs/scaffolds only. This milestone must avoid overclaiming the later composition end state.
98:- Proof artifacts: doc search results for graph-era guidance, scaffold generation tests, generated-doc diff, and links to the composition follow-up for nested workflows.
100:- Doctrine gate: docs must explain that native-first `Pipeline.native_program`
102:  direction is compositional workflow source compiled to runtime manifests, not
104:- Deferrals: workflow nesting, tree traces, path resume, stable unit IDs, dynamic fanout, and handler-purity conformance remain owned by composition M0-M6.
107:## Risks And Blockers
120:  epic replaces it with compositional workflows. Keep this milestone focused on
123:## Dependencies

### .megaplan/initiatives/native-python-pipelines-completion/briefs/m7-megaplan-relocation-and-final-purge.md
1:# M7 - Megaplan Relocation And Final Purge
3:## Objective
7:## Files To Change And Instructions
21:- `arnold/pipelines/megaplan/_pipeline/resume.py`
22:  Delete or shim only after shared native resume has replaced all call sites.
28:  Remove only after the inventory proves all legacy env gates are gone.
35:- `arnold/pipelines/megaplan/_pipeline/artifact_adapter.py`
40:  Delete or shim only after trust-gate imports are migrated.
55:- `tests/arnold/pipelines/megaplan/test_execute_imports.py`
59:- `tests/arnold/pipelines/megaplan/test_review_imports.py`
68:  Update or narrow the public import-surface contract to the final intended
69:  survivors. This suite is a hard gate for de-facto public Megaplan surfaces,
70:  including `arnold_pipelines.megaplan` store, workers, cli, chain, execute,
79:## Verifiable Completion Criterion
87:- `_pipeline/resume.py` is not deleted until existing Megaplan resume file
88:  surfaces pass through `arnold.pipeline.resume` or have explicit migration
90:- Chain import contracts and PR helper behavior remain covered by
92:  not break `ChainState`, `save_chain_state`, `load_chain_state`,
93:  `_capture_sync_state`, `_ensure_milestone_pr`, `_commit_and_push_phase`, or
96:  that implement the native contract. "No shims" means no graph-era fallback,
101:## Native Representation Alignment
104:- Expected status change: substrate `enabled` by proving reviewers and runtime call sites agree on the canonical source/import surface.
105:- Proof artifacts: final import inventory, `rg` results for legacy flags/imports,
109:- Completion-manifest gate: before this chain can hand off to composition,
116:  and declared proof artifact paths. It must also record ordered milestone
117:  labels, completed plan names, merged PR numbers/states/merge SHAs, and final
119:  canonical chain state. `native-composition-followup` must keep
121:  is absent, stale, lacks proof artifacts, or no longer matches the current
122:  chain source, state records, or proof file hashes.
123:- False-pass guard: deleting `_pipeline` or compatibility modules without proving callers moved can break resume/chain behavior while appearing clean.
125:  this completion milestone. It is not report conformance unless composition M6
129:- Canonical paths/imports: this milestone owns the authoritative reconciliation table for `arnold.*`, `arnold_pipelines.*`, CLI, chain, resume, and PR helper surfaces.
131:## Risks And Blockers
137:## Dependencies

codex
**Verdict**

Split it, but mostly into `native-composition-followup`. Do not keep BoundaryTurn as a fourth standalone epic after the three native epics, and do not merge it into `native-python-pipelines-completion` or `native-platform-followup` wholesale. BoundaryTurn is not substrate completion and not production platform hardening; it is the missing model-output/promotion contract that composition needs in order to stop hiding Megaplan semantics inside handlers. The shortest robust shape is: finish native Python completion, fold BoundaryTurn foundation and stage migration into composition, then let platform consume the resulting side-effect/checkpoint metadata.

**Recommended Shape**

Add BoundaryTurn to `native-composition-followup` as part of the composition program:

- Add `m0.5-boundary-turn-foundation` after `m0-composition-contract-and-examples`.
  Use current BoundaryTurn M1. It defines the draft/capture/validate/promote contract and wraps existing JSON scratch behavior without changing behavior.

- Fold current BoundaryTurn M2 into composition M1/M2.
  Composition M1’s Megaplan migration should not just expose workflow structure; it should migrate plan/revise/gate/finalize boundaries so artifact promotion is harness-owned. Composition M2 validator should reject hidden route/state mutation and direct canonical artifact writes as model output.

- Split current BoundaryTurn M3 across composition M3/M4/M5.
  Execute batches, parallel review, and tiebreaker child/reducer semantics belong with nested workflow invocation, tree trace/audit, and path resume. Do not make this one giant reducer milestone.

- Fold current BoundaryTurn M4 into composition M6.
  The reusable Arnold recipe, non-Megaplan example, and conformance matrix are composition conformance deliverables.

- Update `native-platform-followup` M1 to consume BoundaryTurn’s side-effect/effect-ref/checkpoint records.
  Platform should add reconcile/idempotency around those records, not invent a parallel side-effect ledger.

Leave `native-python-pipelines-completion` alone except for a handoff note/manifest saying BoundaryTurn is composition-owned after native completion.

**Parallelization Map**

Can run together:

- BoundaryTurn design refinement can run alongside native Python completion.
- BoundaryTurn foundation can run alongside composition M0 if the contract docs are coordinated.
- BoundaryTurn JSON facade work can run before full nested composition support, as long as it waits until native completion has stabilized canonical Megaplan paths/imports.
- Non-Megaplan recipe docs can be drafted during composition M3-M5, but final conformance must wait for integrated behavior.

Must wait:

- BoundaryTurn implementation should wait for `native-python-pipelines-completion` to finish, or at least for canonical Megaplan migration/import relocation to settle. Otherwise it will chase moving source paths, tests, and artifact surfaces.
- BoundaryTurn reducer work should wait for composition M0/M1 stable IDs and source structure. Child/reducer turns need composition path identity.
- Platform side-effect reconcile/idempotency should wait for BoundaryTurn effect records and composition path/checkpoint identity.
- Final BoundaryTurn conformance must wait for composition M5 path resume.

Do not run in parallel:

- BoundaryTurn M2 primary stage migration versus composition M1 Megaplan migration as separate branches. They touch the same stage semantics, artifacts, and goldens.
- BoundaryTurn M3 reducer migration versus composition M3/M4/M5 as separate plans. That would create duplicate child workflow, trace, resume, and reducer models.
- BoundaryTurn M4 conformance versus composition M6 as separate gates. They should be one gate.

**Merge Risks**

- Hidden route ownership drift: BoundaryTurn could accidentally become the route engine.
  Mitigation: keep `workflow_transition` as a proposal/record; composition validator rejects hidden `current_state`/`next_step` mutation.

- Duplicate side-effect models: BoundaryTurn and platform could define competing ledgers.
  Mitigation: BoundaryTurn records effect refs and promotion checkpoints; platform owns reconcile, idempotency keys, leases, durability, and cancellation.

- Big-bang reducer scope: current BoundaryTurn M3 is too large as one milestone.
  Mitigation: split execute, review, and tiebreaker across composition nested invocation, trace/audit, and resume milestones.

- Test/golden churn: doing BoundaryTurn after composition would rewrite newly migrated Megaplan behavior.
  Mitigation: fold BoundaryTurn into composition migration before composition conformance.

- Over-generalized public API too early.
  Mitigation: keep M0.5 Megaplan-facing but runtime-neutral enough; make public Arnold recipe final in composition M6.

**Proposed Edits**

- Retire `.megaplan/initiatives/boundary-turn-end-to-end/chain.yaml` as an executable standalone chain, or convert it into a planning/handoff artifact.

- In `native-composition-followup/chain.yaml`, insert:
  `m0.5-boundary-turn-foundation`, depending on `m0-composition-contract-and-examples`.

- Amend composition M1 to include BoundaryTurn primary-stage promotion for plan/revise/gate/finalize.

- Amend composition M2 validator to check artifact-promotion boundaries: direct canonical writes do not count, hidden state/route mutation is invalid, and promotion is fail-closed.

- Amend composition M3/M4/M5 to carry BoundaryTurn child/reducer, effect refs, promotion checkpoints, trace events, and path-resume validation.

- Amend composition M6 to absorb BoundaryTurn recipe/conformance and the non-Megaplan proof example.

- Amend platform M1 to depend on BoundaryTurn-emitted effect/checkpoint metadata and explicitly forbid a second platform-only side-effect schema.

Bluntly: the current four-milestone BoundaryTurn epic is useful as analysis, but too big and too cross-cutting as an independent execution chain. Its work should become part of the composition epic, with platform consuming the side-effect contract afterward.
tokens used
62,502
**Verdict**

Split it, but mostly into `native-composition-followup`. Do not keep BoundaryTurn as a fourth standalone epic after the three native epics, and do not merge it into `native-python-pipelines-completion` or `native-platform-followup` wholesale. BoundaryTurn is not substrate completion and not production platform hardening; it is the missing model-output/promotion contract that composition needs in order to stop hiding Megaplan semantics inside handlers. The shortest robust shape is: finish native Python completion, fold BoundaryTurn foundation and stage migration into composition, then let platform consume the resulting side-effect/checkpoint metadata.

**Recommended Shape**

Add BoundaryTurn to `native-composition-followup` as part of the composition program:

- Add `m0.5-boundary-turn-foundation` after `m0-composition-contract-and-examples`.
  Use current BoundaryTurn M1. It defines the draft/capture/validate/promote contract and wraps existing JSON scratch behavior without changing behavior.

- Fold current BoundaryTurn M2 into composition M1/M2.
  Composition M1’s Megaplan migration should not just expose workflow structure; it should migrate plan/revise/gate/finalize boundaries so artifact promotion is harness-owned. Composition M2 validator should reject hidden route/state mutation and direct canonical artifact writes as model output.

- Split current BoundaryTurn M3 across composition M3/M4/M5.
  Execute batches, parallel review, and tiebreaker child/reducer semantics belong with nested workflow invocation, tree trace/audit, and path resume. Do not make this one giant reducer milestone.

- Fold current BoundaryTurn M4 into composition M6.
  The reusable Arnold recipe, non-Megaplan example, and conformance matrix are composition conformance deliverables.

- Update `native-platform-followup` M1 to consume BoundaryTurn’s side-effect/effect-ref/checkpoint records.
  Platform should add reconcile/idempotency around those records, not invent a parallel side-effect ledger.

Leave `native-python-pipelines-completion` alone except for a handoff note/manifest saying BoundaryTurn is composition-owned after native completion.

**Parallelization Map**

Can run together:

- BoundaryTurn design refinement can run alongside native Python completion.
- BoundaryTurn foundation can run alongside composition M0 if the contract docs are coordinated.
- BoundaryTurn JSON facade work can run before full nested composition support, as long as it waits until native completion has stabilized canonical Megaplan paths/imports.
- Non-Megaplan recipe docs can be drafted during composition M3-M5, but final conformance must wait for integrated behavior.

Must wait:

- BoundaryTurn implementation should wait for `native-python-pipelines-completion` to finish, or at least for canonical Megaplan migration/import relocation to settle. Otherwise it will chase moving source paths, tests, and artifact surfaces.
- BoundaryTurn reducer work should wait for composition M0/M1 stable IDs and source structure. Child/reducer turns need composition path identity.
- Platform side-effect reconcile/idempotency should wait for BoundaryTurn effect records and composition path/checkpoint identity.
- Final BoundaryTurn conformance must wait for composition M5 path resume.

Do not run in parallel:

- BoundaryTurn M2 primary stage migration versus composition M1 Megaplan migration as separate branches. They touch the same stage semantics, artifacts, and goldens.
- BoundaryTurn M3 reducer migration versus composition M3/M4/M5 as separate plans. That would create duplicate child workflow, trace, resume, and reducer models.
- BoundaryTurn M4 conformance versus composition M6 as separate gates. They should be one gate.

**Merge Risks**

- Hidden route ownership drift: BoundaryTurn could accidentally become the route engine.
  Mitigation: keep `workflow_transition` as a proposal/record; composition validator rejects hidden `current_state`/`next_step` mutation.

- Duplicate side-effect models: BoundaryTurn and platform could define competing ledgers.
  Mitigation: BoundaryTurn records effect refs and promotion checkpoints; platform owns reconcile, idempotency keys, leases, durability, and cancellation.

- Big-bang reducer scope: current BoundaryTurn M3 is too large as one milestone.
  Mitigation: split execute, review, and tiebreaker across composition nested invocation, trace/audit, and resume milestones.

- Test/golden churn: doing BoundaryTurn after composition would rewrite newly migrated Megaplan behavior.
  Mitigation: fold BoundaryTurn into composition migration before composition conformance.

- Over-generalized public API too early.
  Mitigation: keep M0.5 Megaplan-facing but runtime-neutral enough; make public Arnold recipe final in composition M6.

**Proposed Edits**

- Retire `.megaplan/initiatives/boundary-turn-end-to-end/chain.yaml` as an executable standalone chain, or convert it into a planning/handoff artifact.

- In `native-composition-followup/chain.yaml`, insert:
  `m0.5-boundary-turn-foundation`, depending on `m0-composition-contract-and-examples`.

- Amend composition M1 to include BoundaryTurn primary-stage promotion for plan/revise/gate/finalize.

- Amend composition M2 validator to check artifact-promotion boundaries: direct canonical writes do not count, hidden state/route mutation is invalid, and promotion is fail-closed.

- Amend composition M3/M4/M5 to carry BoundaryTurn child/reducer, effect refs, promotion checkpoints, trace events, and path-resume validation.

- Amend composition M6 to absorb BoundaryTurn recipe/conformance and the non-Megaplan proof example.

- Amend platform M1 to depend on BoundaryTurn-emitted effect/checkpoint metadata and explicitly forbid a second platform-only side-effect schema.

Bluntly: the current four-milestone BoundaryTurn epic is useful as analysis, but too big and too cross-cutting as an independent execution chain. Its work should become part of the composition epic, with platform consuming the side-effect contract afterward.
