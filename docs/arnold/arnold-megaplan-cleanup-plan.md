# Arnold/Megaplan Cleanup Plan

## Goal

Make the architecture match the product model:

- **Arnold** is the package, platform, and plugin runtime.
- **Megaplan** is Arnold's built-in robust planning and execution plugin.
- Generic Arnold runtime code must not know about Megaplan, planning phases, planning state names, or planning gate literals.
- Megaplan should be a beautiful composition of small Arnold primitives, not a privileged workflow smeared through the platform.

This is allowed to be a breaking cleanup. Do not preserve old names through compatibility shims unless a later product decision explicitly reintroduces them.

## Current Diagnosis

The current branch is a mid-strangler. It made planning discoverable as a first-class pipeline, but it did not make planning plugin-clean.

Good foundations already exist:

- Pipeline dataclasses: `megaplan/_pipeline/types.py`
- Registry and discovery: `megaplan/_pipeline/registry.py`
- Graph executor: `megaplan/_pipeline/executor.py`
- Builder and composition helpers: `megaplan/_pipeline/builder.py`
- Reusable-ish steps: `megaplan/_pipeline/steps/agent.py`, `panel.py`, `human_gate.py`
- Pipeline wrapper: `megaplan/pipelines/planning/`

But the real Megaplan implementation still lives across platform-looking modules:

- `megaplan/types.py`
- `megaplan/_pipeline/types.py`
- `megaplan/_pipeline/planning.py`
- `megaplan/_pipeline/planning_bindings.py`
- `megaplan/_pipeline/stages/*`
- `megaplan/handlers/*`
- `megaplan/prompts/*`
- `megaplan/planning/control_binding.py`
- `megaplan/auto.py`
- `megaplan/control_interface.py`
- `megaplan/_core/workflow.py`
- `megaplan/cli/arnold.py`
- `megaplan/profiles/__init__.py`

The cleanup is therefore not a rename. It is an extraction of Megaplan policy out of Arnold runtime.

## Design Principles

1. **Arnold runtime is policy-blind**
   - It knows how to run pipelines, not what Megaplan is.
   - It has no `planning` string literals.
   - It has no `proceed | iterate | tiebreaker | escalate` baked into generic types.

2. **Megaplan owns planning vocabulary**
   - Concrete planning stage implementations.
   - Robustness levels.
   - Planning state transitions.
   - Gate decisions.
   - Override actions.
   - Prompts.
   - Critique lenses.
   - Profiles over Megaplan stages.
   - Shared words such as `prep`, `critique`, `revise`, and `finalize` are not automatically Megaplan-only; other plugins already reuse them. The policy is in the concrete implementations, routing vocabulary, robustness behavior, prompts, and schemas.

3. **Primitives are reusable and boring**
   - `AgentStep`
   - `PanelStep`
   - `DecisionStep` / generic gate routing with plugin-owned decision keys
   - `Loop`
   - `Subpipeline`
   - `HumanGate`
   - `ArtifactStore`
   - `PromptLoader`
   - `ControlBinding`
   - `PipelineBuilder`
   - `ParallelStage`
   - fanout/fan-in joins and reducers
   - loop predicates and max-iteration caps
   - typed ports, content types, taint/provenance, and CAS state deltas
   - prompt overlays and callable prompt builders
   - subpipeline promotion

4. **Megaplan reads like composition**
   - The plugin's `pipeline.py` should show the workflow plainly.
   - Implementation detail belongs in plugin-local stages, prompts, schemas, and control code.
   - The public authoring surface should preserve the existing builder and pattern library. Dataclass graph literals are a low-level representation and documentation aid, not a replacement DSL.

5. **Boundary tests come early**
   - Do not rely on discipline.
   - Add static gates before the large moves so new leakage fails CI.
   - Add behavior parity smoke tests before moves so load-bearing auto, resume, feedback, tiebreaker, override/fallback, robustness, status, and profile behavior cannot disappear behind a clean-looking tree.

## Reusable Primitives vs Megaplan Policy

The core boundary rule is:

> Arnold provides pipeline mechanics. Megaplan provides robust-planning intent.

If a component answers "how do pipelines compose, run, pause, route, fan out, persist artifacts, or validate data?", it belongs in reusable Arnold runtime. If it answers "how should a robust planning and execution workflow behave?", it belongs in the Megaplan plugin.

### Reusable Arnold primitives

These are generic mechanics because many plugins need them:

- graph/runtime types: `Pipeline`, `Stage`, `ParallelStage`, `Edge`, `Step`, `StepContext`, `StepResult`, `PipelineVerdict`
- authoring surface: `PipelineBuilder` plus the existing pattern library
- generic steps: `AgentStep`, `PanelStep`, `HumanGate`, command/batch steps, artifact steps, reducer steps
- fanout/fan-in: static fanout, dynamic fanout from artifacts, joins, reducers, votes, selections, merge policies, and budget/governor hooks
- loops: loop predicates, stop conditions, max-iteration caps, consensus loops, bounded back-edges, and multi-stage cycle composers parameterized by decision keys
- decision routing: plugin-owned decision keys, edge dispatch on those keys, validator checks against each decision stage's declared vocabulary
- override routing: a separate generic axis from model decisions, with plugin-owned override actions and extra/fallback edges
- human pause/resume: generic awaited-decision files, resume markers, and status projection hooks
- subpipelines: explicit input mapping, output mapping, artifact subdirectories, child-state export, and `promote` functions
- dataflow: typed ports, content types, artifact refs, variable refs, schema/content validation, taint/provenance, and artifact binding
- state safety: `StateDelta`, compare-and-swap key versions, merge policies, and state-conflict reporting
- prompts: package prompt resources resolved against a bundle-scoped directory; `prompt` accepts `str` (`.md` file path or inline literal) or `Callable[[StepContext], str]` (dynamic builder); prompt overlays/modes, prompt identity, and interpolation are advanced features layered on the same `str | Callable` base
- plugin resources: a `PipelineResourceBundle` concept covering module/package path, prompt resources, profiles, `SKILL.md`, examples, plugin manifest, manifest hash, trust tier, quarantine state, and quotas. This is a **runtime-internal carrier** constructed by the platform from on-disk conventions — plugin authors never subclass or implement it. Simple plugins see only their directory layout (`prompts/`, `SKILL.md`, optionally `profiles/`); the runtime assembles the bundle.
- plugin discovery: manifests, `plugin.toml` if kept, trust tiers, quarantine, import-free metadata reads, out-of-tree quotas, sibling-file pipelines, package pipelines, user pipelines, and registry lookup
- runtime services: envelopes, deadlines, cancellation, leases/fencing, cost accounting, progress events, observability, and store interfaces
- runtime service provider: state store, event sink, governor, envelope factory, progress reporter, deadline/cancellation source, activation lifecycle, and observability sinks injected into the executor rather than imported from Megaplan modules
- runtime settings: per-run and per-stage operational settings such as wall timeout, idle timeout, heartbeat interval, poll cadence, max workers, retry budget envelope, deadline, cancellation, isolation, and cost caps. These are Arnold mechanics; Megaplan owns only the defaults and meanings attached to its phases.
- control/status contracts: generic `ControlBinding`, status projection, override listing, run outcome projection, and watch/progress plumbing
- terminal policy: result sentinel `next == "halt"`, edge target `"halt"`, paused halt reasons, and cleanup-on-resume semantics
- execution drivers: in-process and subprocess-isolated execution drivers, including reusable phase-step adapters where the handler callable is plugin policy
- batch execution: generic batched command/agent execution, timeouts, aggregation, merge behavior, and per-task result envelopes
- profile mechanics: generic model-routing data validated against the target pipeline's declared stage keys, not against Megaplan's keys
- reusable topology patterns such as pass/fail preflight gates, alternating-turn patterns, conditional escape edges, and parameterized critique/revise/decision cycles

### Megaplan custom policy

These encode the built-in robust planning plugin and must stay under `arnold/pipelines/megaplan/`:

- the concrete Megaplan workflow: `prep`, `plan`, `critique`, `gate`, `revise`, `tiebreaker`, `finalize`, `execute`, `review`, and `feedback`
- Megaplan's decision labels: `proceed`, `iterate`, `tiebreaker`, `escalate`
- Megaplan override actions and their semantics: `force_proceed`, `abort`, `replan`, `add_note`, blocked-task recovery, and clarification/resume flows
- robustness levels and topology policy: `bare`, `light`, `full`, `thorough`, `extreme`, reviewer counts, loop depth, optional prep/feedback paths, and escalation behavior
- critique lens selection, review panels, tiebreaker semantics, gate fallback behavior, and settled-decision handling
- planning state machine, persisted run state, plan directory conventions, resume migration for old plans, manifest-hash checks, and blocked-run recovery
- Megaplan prompt builders that depend on diffs, tickets, contracts, settled tiebreaker decisions, prior findings, project context, and robustness config
- stateful stage handlers for execute/finalize/review, including batch execution, state diffs, retry-blocked-tasks, user-approved flags, and review coupling
- Megaplan auto-driver policy and run-phase adapter
- `auto.py` as the Megaplan workflow driver, including phase ordering, escalation, blocked-task retry, feedback, progress environment mapping, and phase argument parsing
- `_core/workflow.py` as Megaplan's state machine and robustness transition policy; generic control/status contracts carry opaque state, while Megaplan interprets the state keys
- Megaplan status/control projection and override policy
- Megaplan profile defaults, stage routing defaults, depth/tier semantics, critic choices, and prep-model selection
- Megaplan orchestration policy: gate checks, signals, iteration pressure, recovery policy, rubber-stamp detection, tiebreaker support, plan audit, plan contracts, plan structure, prep research, parallel critique policy, feedback, completion contracts, critique status, and verifiability checks
- planning-specific execute policy layered on top of generic batch execution: step editing, quality gates, blocked task recovery, review coupling, and Megaplan-specific binding
- planning-specific routing bridges such as `_forward_m2_m3.py` mappings from Megaplan recommendations to generic routing keys, including `restore_and_diverge`
- Megaplan skills, agent-facing docs, examples, and plugin-local tests

### Smell test

A would-be generic primitive is suspect if it contains any of:

- a hardcoded `planning` or `megaplan` identity
- Megaplan gate labels as type-level policy
- Megaplan phase lists as platform constants
- robustness names in generic runtime
- prompt assumptions specific to planning artifacts
- resume defaults that silently pick Megaplan
- status/control projections that import Megaplan code directly
- profile validation keyed to Megaplan stages instead of the target pipeline's declared stages
- orchestration policy imported by a would-be generic `store`, `workers`, `chain`, or runtime module
- generic-looking routing keys whose kind names mirror Megaplan decisions such as `revise` or `escalate`

The canonical bad example is `GateRecommendation = Literal["proceed", "iterate", "tiebreaker", "escalate"]` in a generic types module. The reusable primitive is "route on a plugin-owned decision key"; Megaplan owns those four keys.

## Abstraction Discipline

The cleanup must not turn every Megaplan behavior into an Arnold concept. Generalize seams, carriers, and mechanics; keep workflow meaning in the plugin.

Megaplan should become the large, robust reference plugin for Arnold: proof that the platform can host sophisticated planning/execution workflows without the platform itself knowing Megaplan's policy. That means the cleanup should be cautious about Megaplan meanings, but not timid about platform-grade surfaces that any serious plugin will need.

### Candidate seams to classify now

These are seams worth classifying early, not permission to build a large platform object for each one before M-1 proves the boundary. Generalize the narrow mechanics already used outside Megaplan or required to remove privileged dispatch; leave richer service/provider abstractions behind explicit disposition rows and tests.

For every configurable seam, the plan must answer four questions: where the setting is declared, how it inherits, how it can be overridden, and who owns its meaning. A supported setting must always have an effective value or an explicit "unset/unsupported" state; silent implicit behavior is not acceptable. Defaults may come from Arnold, a plugin, a profile, the pipeline, or the run invocation, but `arnold run --dry-run` and validation should be able to explain the final value and source.

- Optional plugin operation dispatch with neutral request/result envelopes:
  - run/phase execution
  - status projection
  - resume
  - override listing and application
  - profile validation
- Control/status/override carriers:
  - generic status projection carriers
  - override catalogs
  - override application envelopes
  - human control surfaces
  - CLI/UI plumbing that asks plugins what controls exist rather than hardcoding actions
- Runtime service provider contracts, only as individual seams when current code needs them:
  - state store
  - artifact store
  - prompt service
  - event sink
  - governor/budget checker
  - deadline/cancellation source
  - progress reporter
  - activation lifecycle
- Observability substrate, initially as event envelopes and open plugin-owned event kinds:
  - event envelopes
  - run ids
  - progress streams
  - effect ledgers
  - trace/event sinks
  - plugin-owned event kinds carried as open strings
- Resource/dataflow seams:
  - narrow `PipelineResources` / resolver for prompt, profile, `SKILL.md`, and package-relative resource lookup
  - bundle-scoped prompt loading
  - `ArtifactRef` / `ArtifactStore`
  - typed ports and binding maps
  - runtime-owned state metadata separate from opaque plugin state
- Runtime settings seams:
  - `OperationSettings` / `StageRuntimeSettings` as neutral carriers for wall timeout, idle timeout, heartbeat interval, poll cadence, max workers, retry budget envelope, deadline, cancellation, isolation, and cost caps
  - deterministic precedence: Arnold defaults < plugin defaults < profile settings < run/CLI overrides < env overrides where env is intentionally supported
  - scoped inheritance: run defaults apply to every stage unless overridden; stage settings override one named stage; child-operation settings apply inside panels, fanouts, batches, and subpipelines only where the primitive naturally has children
  - nested propagation: subpipelines inherit parent run settings by default, then apply child pipeline defaults, child profile/settings, child stage overrides, and explicit invocation overrides
  - category rules: timeouts, idle timeouts, heartbeat cadence, retry envelopes, model/profile selection, tracing, and isolation are inheritable; cost/token caps, total deadline, cancellation, and global concurrency are aggregated/enforced globally; worker caps, prompt overlays, output schemas, reducer strategy, and read/write contracts are local to the stage or primitive that supports them
  - effective-settings introspection in dry-run output, including the source of each value
  - validation for unknown stage keys, impossible timeout pairs, unsupported isolation modes, invalid worker caps, and settings declared for stages the pipeline does not expose
- Cross-cutting configuration seams:
  - identity/discovery settings: plugin name, pipeline name, manifest hash, version, trust tier, resource roots, aliases, and migration identity
  - model/profile routing: default profile, per-stage model overrides, fallback models, reviewer/critic models, vendor constraints, and plugin-owned metadata
  - prompt/context configuration: prompt resource, callable prompt builder, overlay/mode, extra context files, variable bindings, dynamic inputs, and redaction rules
  - artifact/dataflow policy: reads/writes, typed ports, schemas, artifact retention, cache behavior, stale artifact handling, provenance/taint, and child artifact promotion
  - control/resume policy: pause points, human gates, override catalogs, cancellation, resume cursor behavior, blocked state, and force/abort/retry controls
  - recovery/failure policy: retryable classes, backoff, escalation thresholds, timeout recovery, partial-result handling, and plugin-owned recovery meanings
  - resource/security policy: token/cost caps, concurrency/fanout/recursion caps, filesystem/network permissions, secret exposure, and cleanup policy
  - isolation/environment policy: in-process/subprocess/worktree/container execution, cwd, env vars, dependency setup, write scope, and teardown behavior
  - observability/audit policy: event verbosity, trace retention, progress frequency, status projection, effect ledger, log redaction, and dry-run visibility
  - composition/subpipeline policy: input/output maps, child profile mapping, budget sharing or slicing, parent/child cancellation, nested observability, independent child resume, and promotion semantics
- Execution mechanics:
  - drivers
  - subprocess isolation
  - generic command/agent batch envelopes
  - timeout and aggregation hooks
- Recovery policy interface, only after the generic classifier can be separated from Megaplan retry/escalation defaults:
  - neutral `RecoveryPolicy.classify(error, context) -> RecoveryDecision`
  - plugin-supplied retry/escalation vocabularies and budgets
- Control mechanics:
  - opaque state carriers
  - plugin-owned target ids
  - plugin-owned event kinds
  - plugin-owned stage, decision, override, and profile vocabularies

### Do not generalize yet

- Megaplan's auto loop as a universal workflow state machine.
- Megaplan phase names as generic Arnold concepts.
- Robustness/depth/prep-model semantics.
- Megaplan override action meanings.
- Universal CLI parsing for plugin phases.
- Static markdown as the only prompt model. The canonical Arnold prompt type supports `str` (`.md` file, inline literal) and `Callable[[StepContext], str]`; Megaplan-specific prompt builders that depend on diffs, tickets, contracts, or robustness config remain plugin-local code, not a generalized `PromptTemplate` framework.
- A plugin VM, package manager, remote plugin registry, signing chain, or full schema-coercion framework.
- `chain`, `cloud`, `resident`, `supervisor`, `review`, and most `orchestration` modules as Arnold runtime. They are product features or Megaplan policy until the M-1 inventory proves otherwise.
- Megaplan's current `auto.py` policy as a generic state machine. The generic extraction is a checkpointed stepwise driver contract, not Megaplan's phase loop, retry ladder, cost policy, or robustness behavior.
- Experimental topology helpers as stable primitives before they are either used by multiple real pipelines or reduced to policy-free parameterized forms.

### Minimality rule

An Arnold abstraction is justified only when at least one of these is true:

- It is already used by non-Megaplan pipelines.
- It removes a proven Megaplan leak from generic runtime.
- It is needed to keep the Megaplan plugin callable without privileged dispatch.
- It protects behavior parity during the move.

Otherwise, leave the behavior plugin-local and revisit after the cleanup lands.

## Target Tree

```text
arnold/
  __init__.py
  py.typed

  pipeline/
    __init__.py
    types.py
    registry.py
    executor.py
    builder.py
    prompts.py
    artifacts.py
    control.py
    runtime.py
    patterns/
      fanout.py
      gate.py
      joins.py
      loop.py
      topology.py
    steps/
      agent.py
      artifact.py
      command.py
      human_gate.py
      panel.py
      reducer.py
      subpipeline.py

  cli/
    __init__.py
    main.py
    pipelines.py

  runtime/
    drivers.py              # generic process/step drivers, not Megaplan auto policy
    run_envelope.py         # routing/resume metadata outside opaque plugin state
  store/
  observability/
  cloud/
  integrations/
    hermes_agent/

  pipelines/
    megaplan/
      plugin.toml
      __init__.py
      pipeline.py
      state.py
      schemas.py
      artifacts.py
      control.py
      profiles/
      skills/
      stages/
        prep.py
        plan.py
        critique.py
        gate.py
        revise.py
        finalize.py
        execute.py
        review.py
        tiebreaker.py
      prompts/
        prep.md
        plan.md
        critique.md
        gate.md
        revise.md
        finalize.md
        execute.md
        review.md
        tiebreaker.md
      tests/
```

This target tree is aspirational. Broad buckets such as `runtime/`, `store/`, `observability/`, `cloud/`, and `integrations/` do not mean those current packages should move wholesale into Arnold runtime. M-1 must classify each module first.

### Chain, Cloud, Supervisor, Resident, And Orchestration

These areas should not be moved wholesale by name. They are where "Megaplan as a product" and "Arnold as a platform" are easiest to confuse.

Default disposition:

- `chain/`: Megaplan/product workflow until split. Arnold may eventually own a generic multi-run sequencing interface, but Megaplan owns epic/sprint semantics, chain YAML policy, milestone planning behavior, and completion rules. Physical post-rename home: `arnold/pipelines/megaplan/chain/`, not generic runtime.
- `cloud/`: split. Arnold can own provider/runtime substrate such as workspace provisioning, process supervision, volume/env wiring, and deployment adapters. Megaplan owns cloud templates and commands that assume `megaplan init`, `megaplan auto`, `.megaplan/plans`, robustness, chain sessions, and phase routing. Physical post-rename home for workflow/templates: `arnold/pipelines/megaplan/cloud/`.
- `supervisor/`: product/plugin policy until split. Arnold may own generic watchdog/control-loop primitives, but Megaplan owns ladder escalation, robustness/profile bump order, force-advance/recover actions, and auto-driver escalation behavior. Physical post-rename home: `arnold/pipelines/megaplan/supervisor/`.
- `resident/`: product app, not Arnold core. It may consume Arnold services, but should not define runtime primitives during this cleanup. Physical post-rename home: `arnold/pipelines/megaplan/resident/` unless M-1 classifies it as a separate product app.
- `orchestration/`: Megaplan policy by default. Gate checks, plan audit, tiebreaker support, iteration pressure, completion contracts, critique status, execution evidence, and verifiability stay plugin-local unless a module is reduced to a policy-free interface with at least one non-Megaplan user. Physical post-rename home: `arnold/pipelines/megaplan/orchestration/`.
- `bakeoff/`: product feature over Megaplan runs. It may later prove a generic fanout/subpipeline pattern, but current worktree management, judging, merge semantics, and profile comparison policy stay plugin-local at `arnold/pipelines/megaplan/bakeoff/`.
- `workers/`: split. Arnold may own generic worker runners, command result envelopes, session keys, and payload validation. Megaplan owns agent-specific adapters, `.megaplan` path assumptions, and Shannon/Hermes routing policy until extracted explicitly.

Potential Arnold extractions from these areas must be named as narrow substrate:

- sequencing carrier/protocol, not Megaplan chain semantics
- cloud provider adapter, not Megaplan cloud workflow
- watchdog/recovery interface, not Megaplan supervisor policy
- evidence/verifiability interface, not Megaplan completion criteria
- recovery classifier interface, not Megaplan retry/escalation defaults

String-level couplings must be gated as seriously as Python imports. Generic Arnold runtime modules must not contain shell commands or path/env assumptions such as `megaplan init`, `megaplan auto`, `megaplan status`, `megaplan chain start`, `python -m megaplan`, `.megaplan/plans`, `.megaplan/bakeoffs`, `MEGAPLAN_*`, or cloud wrapper commands. Plugin-local code and migration docs may contain them, but M6 must render cloud templates and subprocess commands through the new canonical `arnold` CLI or an explicitly retained `megaplan` console forwarder.

`chain` and `bakeoff` may later become good examples of plugin-owned meta-pipelines or fanout/subpipeline patterns, but this cleanup should not force that representation before M-1 classifies their behavior. `cloud` is runtime service infrastructure around pipelines, with provider adapters as possible Arnold substrate and Megaplan templates as plugin policy. `supervisor` is hybrid: Arnold may own a generic watchdog/recovery interface, while Megaplan keeps ladder escalation and outcome interpretation.

### Runtime Execution And Resume Contracts

Two contracts must be explicit before the large moves:

1. **Stepwise/checkpointed execution driver.** Arnold should own the mechanics for advancing one node or plugin operation, checkpointing, exiting, resuming from a cursor, selecting in-process vs subprocess isolation, enforcing deadlines, recording progress events, and preserving artifact boundaries. Megaplan owns the policy that decides which phase to run, how to translate phase args, when to retry/escalate, how cost/stall/blocked-task behavior works, and what a phase result means. `Pipeline.run_phase()` is the current contaminated implementation of this pattern; it should be split, not merely moved wholesale into the plugin.
2. **Run envelope outside opaque plugin state.** Arnold must be able to route and integrity-check a run before importing plugin state. Persist a runtime-owned envelope with at least `plugin_identity`, `manifest_hash`, `schema_version`, `run_id`, `artifact_root`, `resume_cursor`, `trust_tier`, `created_at`, and `plugin_state_schema_version`. Plugin state remains opaque after dispatch. Legacy plan dirs that only know `planning` require a tested migration path to `megaplan`, including manifest-hash handling for the rename.

Nested/subpipeline runs eventually need their own child envelopes and artifact roots. For this cleanup, the hard requirement is explicit input/output mapping, artifact isolation, and `promote(child_result, parent_ctx) -> StateDelta`; child envelopes, independent resume, and discoverable child references should land when a real composed-pipeline use case needs them.

### Megaplan Plugin Package Shape

`arnold/pipelines/megaplan/` should be rich enough to hold Megaplan's real sophistication instead of leaking it back into Arnold runtime:

```text
arnold/pipelines/megaplan/
  __init__.py              # metadata constants and entrypoint
  pipeline.py              # build_pipeline(config): handle + flow composition
  SKILL.md
  state.py                 # PlanState, STATE_* constants, robustness/state machine data
  schemas.py               # GatePayload, findings, contracts, completion shapes
  artifacts.py             # plan_dir layout and Megaplan artifact conventions
  operations.py            # run_phase, status, resume, overrides, profile validation
  auto.py                  # Megaplan auto loop and escalation policy
  workflow.py              # Megaplan workflow transitions and resume migration
  control.py               # Megaplan ControlBinding/status projection
  stages/                  # Step wrappers and stateful stage adapters
  handlers/                # kept only where handler/stage separation is still useful
  prompts/                 # Python prompt builders plus any genuinely static prompts
  orchestration/           # gate checks, plan audit, recovery, completion, verifiability
  execute_policy/          # quality, step edit, timeout recovery, Megaplan batch binding
  profiles/                # Megaplan model-routing defaults and policy-specific validation
  chain/                   # epic/sprint sequencing product policy
  cloud/                   # Megaplan cloud workflows/templates
  supervisor/              # Megaplan ladder escalation and recovery policy
  resident/                # product app surface, if retained in this package
  bakeoff/                 # Megaplan profile/worktree comparison feature
  workers/                 # Megaplan-specific agent adapters after generic worker split
  skills/
  tests/
```

Generic Arnold batch/runtime code may provide schedulers, process drivers, timeout supervision, envelopes, and reducers. Megaplan's `execute_policy/` owns task complexity, blocked-task recovery, destructive confirmation, evidence checks, review coupling, `execution_batch_*.json`, and final-plan artifact conventions.

## What Megaplan Should Look Like

`arnold/pipelines/megaplan/pipeline.py` should be small enough to read as composition, but it must not be less expressive than the current runtime. The snippets below are illustrative graph shape, not a mandate to replace `PipelineBuilder`, pattern helpers, callable prompts, typed ports, loop caps, override edges, fallback edges, or subpipeline promotion with a smaller static DSL.

```python
def build_pipeline(config: MegaplanConfig) -> Pipeline:
    return (
        MegaplanPipelineBuilder("megaplan")
        .agent("prep", prompt=build_prep_prompt)       # callable: (StepContext) -> str
        .agent("plan", prompt=build_plan_prompt)       # callable: reads diffs, tickets, robustness
        .panel("critique", reviewers=critique_lenses(config), join=megaplan_critique_join)
        .decision(
            "gate",
            decisions=("proceed", "iterate", "tiebreaker", "escalate"),
            overrides=("force_proceed", "abort", "replan", "add_note"),
            extra_edges=megaplan_gate_fallback_edges(),
        )
        .agent("revise", prompt="revise.md")            # static markdown from bundle
        .subpipeline("tiebreaker", child=build_tiebreaker_pipeline(), promote=promote_tiebreaker)
        .agent("finalize", prompt="finalize.md")        # static markdown from bundle
        .stage(ExecuteBatches())
        .panel("review", reviewers=review_lenses(config), join=megaplan_review_join)
        .with_robustness(config.robustness)
        .build()
    )
```

Some Megaplan stages can be thin adapters over Arnold primitives:

```python
# Callable prompt: reads artifacts and state to build the plan prompt
PlanStage = AgentStep(
    name="plan",
    prompt=build_plan_prompt,              # Callable[[StepContext], str]
    output_schema=PlanOutput,
    writes=["plan.md", "plan.meta.json"],
)

# Static markdown prompt: resolved from prompts/critique.md in the plugin bundle
CritiquePanel = PanelStep(
    name="critique",
    prompt="critique.md",                  # str -> bundle-scoped file
    reviewers=megaplan_critique_lenses(),
    output_schema=CritiqueFinding,
    writes=["critique.json"],
)

# Callable prompt: reads plan and critique to build the gate prompt
GateDecision = GateStep(
    name="gate",
    prompt=build_gate_prompt,              # Callable[[StepContext], str]
    decisions=["proceed", "iterate", "tiebreaker", "escalate"],
    overrides=["force_proceed", "abort", "replan", "add_note"],
    input_artifacts=["plan.md", "critique.json"],
    writes=["gate.json"],
)
```

Other Megaplan stages are intentionally stateful plugin handlers, not thin adapters. `execute`, `finalize`, `review`, `feedback`, blocked-task retry, and human override flows must move into the plugin with their state-diffing and recovery contracts intact.

## Milestones

### M-1: Inventory Behavior And Classify The Whole Package

Before moving code, classify every top-level `megaplan/*` module into one of:

- Arnold runtime.
- Arnold integration.
- Megaplan plugin policy.
- Shared leaf utility.
- Delete/merge.

Use these stricter definitions:

- **Runtime primitive**: no Megaplan phase, state, robustness, profile, prompt, or artifact-name literals; accepts plugin-declared vocabularies; depends only on service protocols.
- **Integration/shared leaf**: talks to external systems or local process/store primitives; may be reused by plugins; cannot import plugin policy.
- **Built-in plugin policy**: owns Megaplan workflow, prompts, state, cloud templates, chain semantics, profile defaults, recovery behavior, status/control projection, or auto behavior.

The inventory must explicitly cover:

- `agent`
- `chain`
- `cloud`
- `store`
- `workers`
- `orchestration`
- `supervisor`
- `resident`
- `observability`
- `_core`
- `handlers`
- `prompts`
- `execute`
- `review`
- `editorial`
- `receipts`
- `loop`
- `schemas`
- `bakeoff`
- `drivers`
- `_pipeline/_forward_m2_m3.py`
- tickets and epics storage
- skills and skill sync

Also record behavior that must survive:

- auto loop phase execution
- auto orphan/liveness behavior: healthy `active_step` waits without burning iteration budget; stale/dead active steps clear before redispatch; orphan outputs are quarantined
- phase-result freshness and synthesis: stale `phase_result.json` cannot mask the current phase; timeout/context/success/failure results are attributed to the current phase before status advances
- review rework loop semantics: `review.json` changes can reset stall detection, but repeated rework still eventually hits the cap
- synthesized override fallback: repeated `override add-note` failures escalate according to Megaplan policy, including unresolved-flag note contents
- resume and manifest hash checks
- strict-notes and user-approved force-proceed constraints, including rejection codes for unabsorbed notes and gate escalation without approval
- resume phase args for `execute`, including destructive confirmation, user-approved flags, and batch index
- resume failure rollback and successful-resume cleanup of `latest_failure` and `resume_cursor`
- feedback phase
- tiebreaker path
- override and fallback edges
- robustness-dependent topology and loop depth
- blocked-task retry
- execute policy details: destructive confirmation, review-mode approval, blocked lifecycle, retry-blocked-tasks, batch transitions, timeout checkpoint recovery, evidence attribution, and tier selection
- review policy details: incomplete verdicts, empty evidence, rework staying in review, batch-by-batch review, and blocked-status acceptance
- status/watch outcome projection
- profile validation
- CLI dispatch
- cloud, bakeoff, ticket, epic, and skill workflows
- chain PR/branch behavior: configured base checkout, draft PR creation, auto-merge fallback, review-policy wait/resume after PR merge, runtime policy overrides, and policy metadata injection
- bakeoff flag routing and mode validation, including compatibility path versus supervisor path
- cloud wrapper command compatibility, tmux restart refresh, state-reset guards, preflight blocking, marker/provenance output
- completion-contract and capsule-warrant behavior
- dynamic fanout and terminal `next == "halt"` behavior in the doc pipeline
- typed-port binding and reducer outputs in select-tournament
- human pause/resume file shape, halt reason, resume cleanup, and loop-back behavior in writing-panel-strict
- a non-planning research fanout shape: one agent produces structured briefs, multiple agents investigate in parallel, a reducer synthesizes, and an optional write gate applies a doc patch
- registry `SKILL.md` lookup for sibling-file and package pipelines
- override-edge dispatch behavior, including whether the executor consumes `kind="override"` or only label-based `override <action>` edges

Acceptance criteria:

- The target tree has a named home for every classified module.
- Each move has a source-to-destination map.
- A parity test list exists before M0 begins.
- Add `docs/arnold/package-disposition.md` with one row per package/module or finer-grained split: `source`, `target`, `granularity`, `disposition`, `reason`, `blockers`, `allowed imports`, `forbidden imports`, `vocabulary owned`, `string policy`, `extraction prerequisite`, `first extraction unit`, and `tests/gates`.
- Valid dispositions are `arnold-core`, `arnold-service-interface`, `arnold-adapter`, `arnold-shared-leaf`, `megaplan-plugin`, `product-app`, `legacy-hold`, `delete-merge`, and `split-required`.
- The disposition manifest is mechanically enforceable: every tracked `megaplan/**/*.py` source maps to exactly one row, excluding generated/cache artifacts.
- Any `split-required` directory must have child rows before code moves.
- Known hybrid zones require file-level or symbol-level rows, not one vague directory row: `_pipeline/`, `orchestration/`, `execute/`, `runtime/`, `observability/`, `store/`, `workers/`, `drivers/`, each `pipelines/*` package, `cli/arnold.py`, `cli/status_view.py`, `control_interface.py`, `auto.py`, `_core/workflow.py`, and `profiles/__init__.py`.
- Every module proposed for Arnold runtime passes a negative import check against `megaplan.types`, `megaplan.prompts`, `megaplan.handlers`, `megaplan.orchestration`, `megaplan.planning`, and `megaplan._core.workflow`, unless a protocol seam is introduced first.
- Every moved module declares vocabulary ownership: stage keys, phase keys, state keys, decision keys, override actions, event kinds, profile slots, env vars, and artifact names.
- `orchestration/` has a module-by-module classification.
- No generic Arnold module imports Megaplan orchestration policy.
- `execute/` is split into reusable batch/timeout/merge mechanics and Megaplan-specific execution policy.
- `drivers/` and subprocess phase adapters have an explicit generic-vs-plugin boundary.
- Stepwise/checkpointed execution is classified before `Pipeline.run_phase()` is moved: driver mechanics to Arnold runtime, Megaplan phase selection/retry/escalation policy to the plugin.
- Resume identity is classified before opaque state becomes policy-blind: runtime-owned envelope fields vs opaque plugin state are listed explicitly.
- `cloud`, `chain`, `resident`, `supervisor`, `review`, and `agent` are not moved wholesale into Arnold runtime.
- No horizontal package relocation by directory name. Every move is symbol-level or file-level justified by the disposition manifest and passes the boundary gate.
- Platform-grade surfaces are explicitly classified early: plugin operations, control/status/override carriers, resource bundles, dataflow validation, batch/driver substrate, event/observability substrate, and recovery-policy interface.
- String-level boundary gates are included alongside import gates, especially CLI command literals, `.megaplan` path conventions, cloud wrapper commands, and `MEGAPLAN_*` environment variables.
- M-1 does not move files, rewrite imports, design compatibility shims beyond identifying required migration paths, delete product surfaces, introduce a plugin VM/registry/signing system, or generalize Megaplan policy into Arnold just to make a row look cleaner.

### M0: Establish The Clean Arnold Boundary

Create a new `arnold/` package skeleton without changing existing imports.

Move or copy only genuinely neutral primitives into `arnold/pipeline/`:

- `Pipeline`
- `Stage`
- `ParallelStage`
- `Edge`
- `Step`
- `StepContext`
- `StepResult`
- `PipelineVerdict`
- `StateDelta`
- `apply_delta`

Make these changes while keeping current code untouched:

- `PipelineVerdict.recommendation: str | None`
- `PipelineVerdict.override: str | None`
- `StepContext` uses neutral runtime names such as `artifact_root` or `run_root`, not `plan_dir`, and carries opaque state plus resource handles rather than Megaplan `PlanState` assumptions.
- No `GateRecommendation` literal.
- No `OverrideAction` literal.
- No `planning` string.
- No imports from `megaplan`.

Add boundary tests:

- `arnold/pipeline/**` must not import `megaplan`.
- `arnold/pipeline/**` must not contain `"planning"`.
- `arnold/pipeline/**` must not contain Megaplan gate literals as typed policy: `"proceed"`, `"iterate"`, `"tiebreaker"`, `"escalate"`.

Important M0 scope note:

- These gates apply to the new `arnold/pipeline/**` package. The old `megaplan/_pipeline/**` code may temporarily retain `GateRecommendation`, `OverrideAction`, `Pipeline.run_phase()`, and other planning leaks until later migration milestones remove them.
- The new package must not copy `_phase_arg_overrides`, `Pipeline.run_phase()`, `_forward_m2_m3.py` routing bridges, or `restore_and_diverge`.
- The new package is not used by current runtime code yet. M0 creates the neutral target shape; M2/M3 decide when old runtime paths start importing it.

This milestone proves the target shape without risking the old runtime.

Dogfooding boundary: M0 and M1 may be driven by the current Megaplan engine because they are additive or identity-focused. From M2 onward, do not rely on the same in-flight branch's `megaplan auto` to drive the cleanup unless a parity check proves the run/resume path still works. Use a pinned/external engine, direct git/pytest workflow, or another stable driver for milestones that dismantle auto/resume/control dispatch.

### M1: Make Plugin Identity Correct Without Breaking Dispatch

Rename the discovered built-in pipeline from `planning` to `megaplan`.

Do not physically move the production planning pipeline outside the current discovery root until discovery, auto/run-phase, resume, control/status, override, and profile dispatch are plugin-identity based. Current code still scans `megaplan.pipelines`, hardcodes `planning` in auto/resume/control paths, and calls `Pipeline.run_phase()` directly.

Allowed implementation shapes:

- temporarily rename `megaplan/pipelines/planning/` to `megaplan/pipelines/megaplan/`
- keep the file in place while registering/discovering canonical identity `megaplan`

Update metadata:

- `name = "megaplan"`
- `capabilities = ("plan", "execute", "review")` or a richer capability object
- `entrypoint = "build_pipeline"`

Update tests and docs to expect `megaplan` as the plugin name.

Required bridge:

- `PipelineRegistry().get("megaplan")` works.
- `PipelineRegistry().get("planning")` works only through an explicit legacy alias to `megaplan`.
- `arnold pipelines list` shows `megaplan`, not `planning`.
- `arnold auto megaplan` does not fail only because the CLI still hardcodes `planning`.
- Resume of a captured legacy `planning` plan routes to canonical `megaplan`.

Do not move stage implementations yet. The wrapper can still import old stage code for this milestone. The purpose is to fix identity first without stranding the current engine.

### M2: Introduce Plugin Capabilities

Add a plugin capability contract that Arnold uses for dispatch. Capabilities are runtime-derived from manifest data, graph inspection, and optional operation registrations; simple plugins do not export or import a `PluginCapabilities` dataclass.

A simple plugin contract is:

```python
name = "my-reviewer"
entrypoint = "build_pipeline"
arnold_api_version = "1.0"

def build_pipeline() -> Pipeline:
    ...
```

No `PluginOperations`, no operation envelopes, no capabilities export. When a plugin has no custom operations, `arnold run` uses the generic graph executor.

For complex plugins, operations are independently optional and small. A plugin implements only the operations it actually supports:

```python
@dataclass(frozen=True)
class PluginCapabilities:
    name: str
    stages: tuple[str, ...]
    operations: Mapping[str, PluginOperation]
    profile_keys: tuple[str, ...]

RunPhaseOperation = Callable[[PhaseRunRequest], PhaseRunResult]
StatusOperation = Callable[[StatusRequest], StatusProjection]
ResumeOperation = Callable[[ResumeRequest], ResumeResult]
OverrideListOperation = Callable[[OverrideListRequest], OverrideCatalog]
OverrideApplyOperation = Callable[[OverrideRequest], OverrideResult]
ProfileValidateOperation = Callable[[ProfileValidationRequest], ProfileValidationResult]
```

These request/result types are neutral carriers. They may carry `plugin_name`, `run_id`, `plan_dir`, `root`, `project_dir`, `argv/options`, `progress_env`, and opaque `raw_state`. They must not define Megaplan phase names, robustness levels, override meanings, or profile semantics.

Then remove privileged planning dispatch from:

- `megaplan/auto.py`
- `megaplan/control_interface.py`
- `megaplan/cli/arnold.py`
- `megaplan/_core/workflow.py`

Acceptance criteria:

- `auto` resolves a plugin auto/run-phase operation, not `PipelineRegistry().get("planning")`.
- `control_interface` resolves a plugin-provided `ControlBinding`, not string `"planning"`.
- CLI discovers override actions from plugin capabilities.
- Resume refuses missing plugin identity for new runs, while legacy persisted runs without identity have an explicit tested migration path from `planning` to `megaplan`.
- Runtime resume reads a small Arnold-owned run envelope before plugin dispatch. At minimum it carries plugin identity, manifest hash, envelope schema version, plugin state schema version, run id, artifact root, resume cursor, trust/quarantine state, and creation time.
- Legacy resume across the rename is tested against a captured pre-cleanup plan directory; the first migrated resume may handle manifest-hash mismatch explicitly, but subsequent resumes must use the new identity and hash.
- `read_valid_targets()` and similar control APIs do not silently default `binding="planning"`.
- `Pipeline` remains graph data; run/phase/auto/resume/status/control behavior is not a method on the graph dataclass.
- Arnold provides reusable polling/driver/checkpoint helpers where they are policy-free, but Megaplan's auto phase ordering, retry classification, escalation, stall policy, and cost policy remain plugin-owned.
- A stepwise/checkpointed driver seam exists before `Pipeline.run_phase()` is removed from the old graph dataclass: Arnold owns advance/checkpoint/resume/isolation mechanics; Megaplan owns phase policy and argument translation.
- When `operations` is empty, `arnold run` uses the generic graph executor. No basic graph execution path requires plugin operation code.
- Operation-based CLI verbs dispatch only when the target plugin advertises that operation. Override action lists come from `OverrideCatalog`, not Arnold constants.
- The physical plugin move to `arnold/pipelines/megaplan/` is allowed only after the registry scans `arnold.pipelines`, `SKILL.md` and prompt/profile resources resolve there, pipeline-local profiles load there, and legacy `planning` aliases route through the runtime-owned envelope/migration path rather than generic defaults.

This is the most important architectural seam.

### M3: Extract Generic Runtime From `_pipeline`

Move genuinely generic runtime code to `arnold/pipeline/`:

- `registry.py`
- `executor.py`
- `builder.py`
- generic `patterns`
- generic `steps`
- prompt-loading interface
- artifact interface

Split mixed components:

- `PipelineBuilder.gate()` becomes generic and accepts arbitrary gate edges.
- Megaplan's four-way gate helper moves into `arnold/pipelines/megaplan/`.
- `PipelineBuilder.tiebreaker()` moves into Megaplan or disappears.
- `PipelineBuilder.decision()` or equivalent replaces Megaplan-shaped `.gate(on_proceed, on_iterate, on_tiebreaker, on_escalate)` in generic Arnold.
- `critique_revise_gate_loop()` is split into a generic loop helper parameterized by decisions, overrides, fallback edges, and caps, plus a Megaplan-specific wrapper.
- `phase_zero_gate`, `alternating_turns`, and conditional escape-edge patterns are classified as reusable topology patterns and re-homed generically with plugin-owned routing keys.
- `Pipeline.run_phase()` leaves the graph dataclass. Its generic mechanics are split into a stepwise/checkpointed driver contract; Megaplan's phase adapter keeps only Megaplan phase vocabulary, state interpretation, and phase-argument policy.
- `_phase_arg_overrides` leaves generic types entirely and moves with the Megaplan run-phase adapter.
- `GateRecommendation` and `OverrideAction` leave generic runtime. Generic edge dispatch uses plugin-owned routing strings validated against each decision stage's declared vocabulary.
- Override routing is not declared generically complete until the executor's behavior is explicit and tested: either it dispatches `kind="override"` edges or the generic contract documents and preserves label-based `override <action>` routing.
- Prompt loading supports the canonical type `str | Callable[[StepContext], str]`: a `.md`-suffixed string resolves against the plugin bundle's prompt directory; any other string is treated as an inline literal; a callable receives `StepContext` and returns the prompt string. This is the public API. The advanced `prompt_key` + `PromptRegistry` indirection (pipeline/mode-scoped key lookup) remains available for multi-mode pipelines and shared step classes but must not appear in scaffolds, generated plugins, or the one-page guide.
- Prompt resolution is bundle-scoped: the executor receives a `PipelineResourceBundle` that owns the prompt directory, and `.md` paths resolve relative to it. Import-side-effect `register_prompt()` into a global registry is preserved only as a migration bridge for existing Megaplan handlers; new code must not use it.
- Subpipeline execution is a first-class node contract, not filename convention: explicit input/output maps, child artifact scope, and `promote(child_result, parent_ctx) -> StateDelta`. Child run envelopes, nested profile mapping, parent/child observability linkage, and independent child resume are target capabilities, but do not block the initial extraction unless the selected parity fixture requires them.
- `Pipeline` remains graph data. Run, phase, auto, resume, status, and control operations are plugin capability operations or runtime services, not methods on the graph dataclass.
- `ControlBinding` and `RunStateView` carry opaque state generically; Megaplan's control binding interprets Megaplan state constants.
- `ArtifactRef` and `ArtifactStore` are designed as the target contract; raw `Path` outputs remain a migration bridge.
- `reads=[...]` and `writes=[...]` are Level-1 sugar over the same artifact/port model as typed `produces`/`consumes`; simple string artifact names use wildcard content type until a plugin opts into typed ports.
- Add unified control-flow and data-flow validation: `validate_control_flow()` plus `validate_dataflow_paths()`. Required reads/ports must be satisfiable on every incoming path unless marked `optional`, `external`, or `late_bound`.
- Dynamic fanout specifies generated spec schema, specialization, concurrency mode, governor limits, typed output port, and join contract before being treated as stable runtime API.
- Pipeline references should eventually use a `PipelineRef`/registry reference plus explicit bindings when the child pipeline is independently discoverable. Inline subpipelines may pass a `Pipeline` object directly during the first extraction.
- Batch execution is split into a generic batch runtime and Megaplan execution policy.
- Observability/event envelopes, progress streams, effect ledgers, and trace sinks move as platform substrate only after plugin-owned event kinds are made open strings.
- Recovery policy is split into a generic classifier interface and Megaplan-owned retry/escalation defaults.

Acceptance criteria:

- A toy plugin runs using only `arnold.pipeline`.
- `arnold.pipeline` tests pass even if the Megaplan plugin directory is absent.
- Existing non-Megaplan pipelines still build against the re-homed primitives.
- The toy plugin exercises fanout/fan-in with a join, a loop cap, a human gate, typed artifacts, callable prompt loading, and subpipeline promotion.
- `arnold.pipeline` retains dynamic fanout, joins/reducers, loop predicates, max-iteration caps, prompt overlays, typed ports, taint/provenance, CAS state deltas, override edges, and manifest discovery trust/quarantine behavior where those are generic.
- `doc` dynamic fanout and terminal `next == "halt"` behavior are preserved.
- `select-tournament` typed-port binding and reducer outputs are preserved.
- `writing-panel-strict` human pause/resume with `continue` looping and `stop` halting is preserved.
- Registry `SKILL.md` lookup works for sibling-file pipelines and package pipelines.
- Planning `feedback` executes via a Megaplan plugin run operation, not by forcing `feedback` to become a generic graph stage.
- Halt short-circuit via `result.next == "halt"` and halt-edge dispatch via target `"halt"` are both preserved and tested.
- Parallel join ordering, override dispatch, typed routing validation, subpipeline artifact isolation/promotion, subprocess timeout behavior, and driver selection are covered by parity tests.
- Subpipeline artifact isolation and promotion are covered by parity tests. Independent child resume is a later target unless M-1 selects a current workflow that already depends on it.
- Non-Megaplan dataflow parity is covered for `doc`, `creative`, and `select-tournament`; control-flow parity alone is not enough.
- A research-fanout toy pipeline or fixture demonstrates runtime-generated briefs, parallel investigation tasks, provenance-preserving collection outputs, and reducer synthesis without importing Megaplan policy.
- A non-Megaplan toy plugin can expose status and at least one override/control action through generic operation carriers without importing Megaplan policy.
- A batch-oriented toy plugin can use Arnold batch/driver substrate with plugin-owned result meanings.

### M4: Move Megaplan Stage Implementations Into The Plugin

Move planning-specific stages:

- `megaplan/_pipeline/stages/prep.py`
- `megaplan/_pipeline/stages/plan.py`
- `megaplan/_pipeline/stages/critique.py`
- `megaplan/_pipeline/stages/gate.py`
- `megaplan/_pipeline/stages/revise.py`
- `megaplan/_pipeline/stages/finalize.py`
- `megaplan/_pipeline/stages/execute.py`
- `megaplan/_pipeline/stages/review.py`
- `megaplan/_pipeline/stages/tiebreaker.py`

To:

- `arnold/pipelines/megaplan/stages/`

Move planning-specific handlers or collapse them into stage adapters:

- `megaplan/handlers/plan.py`
- `megaplan/handlers/critique.py`
- `megaplan/handlers/gate.py`
- `megaplan/handlers/finalize.py`
- `megaplan/handlers/execute.py`
- `megaplan/handlers/review.py`
- `megaplan/handlers/tiebreaker.py`

To:

- `arnold/pipelines/megaplan/stages/`
- or `arnold/pipelines/megaplan/handlers/` if keeping adapter separation is useful.

Acceptance criteria:

- Megaplan plugin imports its own stages locally.
- Generic runtime has no imports from Megaplan stages or handlers.

### M5: Move Megaplan Prompts, State, Profiles, And Control

Move global planning prompt modules into plugin-local prompt files or prompt builders:

- `megaplan/prompts/planning.py`
- `megaplan/prompts/critique.py`
- `megaplan/prompts/gate.py`
- `megaplan/prompts/finalize.py`
- `megaplan/prompts/execute.py`
- `megaplan/prompts/review.py`
- `megaplan/prompts/tiebreaker_*`

To:

- `arnold/pipelines/megaplan/prompts/`

Do not flatten dynamic prompt modules into static markdown when they currently compute prompts from state, diffs, tickets, contracts, robustness, unresolved findings, or settled tiebreaker decisions. Static `.md` prompts are allowed for simple cases; Megaplan's planning prompts remain prompt builders when they need code.

Move planning state and control:

- `megaplan/types.py` planning constants -> `arnold/pipelines/megaplan/state.py`
- `DEFAULT_AGENT_ROUTING` -> plugin profile defaults
- `ROBUSTNESS_LEVELS` -> plugin policy
- `GateArtifact`, `GatePayload`, gate check types -> plugin schemas
- `megaplan/planning/control_binding.py` -> `arnold/pipelines/megaplan/control.py`
- `megaplan/profiles/__init__.py` phase validation -> plugin-declared profile keys

Acceptance criteria:

- Platform profiles are generic model-routing data.
- Generic profile validation is parameterized by the target pipeline's declared stage keys.
- Generic profile validation handles dotted keys by validating the declared stage prefix; sub-slot meaning belongs to the plugin or step.
- Unknown profile metadata is not interpreted by Arnold. It is passed through to an optional plugin profile-validation operation, which may accept or reject plugin-specific fields.
- Composed pipelines have explicit profile scoping. A parent may let a child use its default profile, pass a named child profile, or provide a nested profile map validated against the child's declared stage/profile keys.
- For the first cleanup pass, composed-pipeline profile scoping is specified as a target contract and recipe, not a blocker for simple plugins or inline subpipelines that do not expose child profile overrides.
- Megaplan profile validation comes from Megaplan's declared stage keys and policy-specific depth/tier rules.
- Generic Arnold code does not import Megaplan state constants.

### M6: Package Rename And CLI Surface

Make `arnold` the canonical package.

Update:

- `pyproject.toml`
- package build config
- console scripts
- imports
- docs
- tests

Canonical commands:

```bash
arnold pipelines list
arnold run megaplan ...
arnold auto megaplan ...
arnold megaplan ...
```

Optional command:

```bash
megaplan ...
```

If kept, `megaplan` should be a console entry that invokes the Megaplan plugin directly, not a Python package shim.

Acceptance criteria:

- No source imports from `megaplan.*` in the renamed source tree. Plugin-internal imports must use `arnold.pipelines.megaplan.*`, not the old package name; generic Arnold runtime modules still cannot import from that plugin namespace.
- String-level gates catch stale generic-runtime uses of `megaplan init`, `megaplan auto`, `megaplan status`, `megaplan chain`, `python -m megaplan`, `.megaplan/plans`, `.megaplan/bakeoffs`, and `MEGAPLAN_*`, with explicit exceptions for plugin-local migration code and user-facing compatibility docs.
- `python -m arnold` works.
- `arnold run megaplan --describe` works.
- `arnold pipelines list` shows `megaplan`.
- Cloud template rendering and chain/bakeoff subprocess command construction are tested against the canonical `arnold` CLI or the deliberately retained `megaplan` console forwarder.
- If the `megaplan` console command is retained, it is a thin command forwarder/deprecation surface, not an importable Python package shim.

### M7: Delete Old Privileged Paths

Delete or fully retire:

- `megaplan/_pipeline/planning.py`
- `megaplan/_pipeline/planning_bindings.py`
- `megaplan/planning/`
- planning-specific code under `megaplan/_pipeline/stages/`
- global planning prompt modules
- hardcoded `"planning"` defaults
- old `megaplan` package if the package rename is complete

Do not delete plugin-owned product surfaces merely because they used to live under the top-level `megaplan` package. `chain/`, `cloud/`, `supervisor/`, `resident/`, `orchestration/`, `bakeoff/`, and Megaplan-specific worker adapters survive under `arnold.pipelines.megaplan/` unless M-1 explicitly classified a module for Arnold substrate extraction or deletion.

Acceptance criteria:

- Static gates pass.
- Generic Arnold tests pass without Megaplan installed.
- Megaplan plugin tests pass as one plugin.
- Another non-Megaplan plugin proves the primitives are reusable.

### M8: Make New Pipeline Authoring Astonishingly Easy

This cleanup is not complete just because the internals are clean. A developer should be able to create a useful new pipeline from Arnold primitives without reading the Megaplan implementation.

Target authoring flow:

```bash
arnold new pipeline my-reviewer
arnold pipeline check my-reviewer
arnold run my-reviewer --input brief=brief.md
```

Generated skeleton:

```text
arnold/pipelines/my_reviewer/
  pipeline.py
  prompts/
    draft.md
    risk.md
    ux.md
    revise.md
    gate.md
  SKILL.md
  tests/
    test_pipeline.py
```

The common case should read like composition:

```python
from arnold.pipeline import HALT, Pipeline, majority_vote

def build_dynamic_critique(ctx) -> str:
    """Callable prompt: reads prior findings from artifacts at runtime."""
    findings = ctx.artifacts.get("critique_report.json", "{}")
    return f"You are a document critic. Prior findings:\n{findings}\n\nRate this draft."

def build_pipeline():
    p = Pipeline("my-reviewer")

    brief = p.input("brief", file=True)

    # Static markdown prompt: resolved from prompts/draft.md in the plugin bundle
    draft = p.agent("draft", prompt="draft.md", reads=[brief], writes=["draft.md"])

    # Inline literal prompt: no file needed for trivial prompts
    critique = p.panel(
        "critique",
        reviewers={
            "risk": "risk.md",
            "ux": "ux.md",
            "dynamic": build_dynamic_critique,   # callable prompt builder
        },
        reads=[draft],
        writes=["critique_report.json"],
        join=majority_vote,
    )

    # File-relative markdown prompt
    revise = p.agent(
        "revise",
        prompt="revise.md",
        reads=[draft, critique],
        writes=["revised_draft.md"],
    )

    gate = p.decision(
        "gate",
        prompt="gate.md",
        reads=[draft, critique],
        routes={
            "ship": HALT,
            "revise": revise,
        },
    )

    p.flow(brief, draft, critique, gate)
    p.flow(revise, critique)

    return p
```

Canonical authoring style:

- Public docs and scaffolds use named handles plus explicit `p.flow(...)` wiring.
- Input handles must be unambiguous: if `p.input(...)` participates in `p.flow(...)`, it is an input node that produces an artifact handle; pure artifact refs should use explicit artifact/port APIs.
- Node handles, not string names, are used for route targets wherever possible.
- `HALT` is a typed sentinel, not a string.
- Decision branches are declared on `p.decision(..., routes=...)`; linear/successor flow is declared with `p.flow(...)`.
- Control flow and data flow are distinct: `p.flow(...)` defines ordering/reachability, while `reads=[...]`, typed ports, and artifact refs define what data a step requires.
- Dataclass graph literals and fluent chains are not the public style.
- New scaffolds should prefer the chosen public style once implemented. Existing `PipelineBuilder` docs may remain until the handle/flow API exists and at least two real pipelines have migrated; they must then be marked legacy or rewritten.

Why this style:

- A bounded Claude/DeepSeek spoof-pipeline edit test favored named handles over fluent chains for agent comprehension.
- Fluent chains caused duplicate graph sources of truth: route dictionaries plus separate `.edge(...)` calls that can drift.
- Named handles made additive edits more local and reduced string-reference mistakes.
- The test also exposed a required validator: control-flow reachability is not enough. A route can be syntactically valid while bypassing the producer of data the target step requires.

Required validation:

- every declared node is reachable or explicitly marked external/operation-only
- every route target and flow target is known
- every decision label has exactly one route unless explicitly optional
- no decision node is given an implicit default successor through `p.flow(...)`
- cycles without a decision/loop guard are rejected or warned
- node names are unique and stable for serialization
- both termination forms are handled explicitly: route/flow target `HALT`, and runtime result sentinel if a step halts itself
- every step's required `reads` are satisfiable on every incoming control-flow path, or explicitly marked optional/late-bound
- `arnold pipeline check` warns when a route bypasses the producer of an artifact a target step claims to require

Acceptance criteria:

- `arnold new pipeline <name>` creates a runnable plugin with prompts, manifest, skill stub, and tests.
- `arnold pipeline check <name>` validates manifest, prompts, declared decisions, edge targets, typed artifacts, profile keys, and missing resources.
- `arnold run <name> --dry-run` prints the realized graph, input contract, prompt/resource bundle, and operation capabilities.
- `arnold pipeline check --explain <name>` or equivalent explains dataflow failures, missing prompts, unknown routes, and unguarded cycles in author-facing language.
- Author-facing examples cover:
  - a linear agent pipeline
  - a panel plus decision plus revise loop
  - dynamic fanout plus reducer, including a research-panel example where one stage produces structured briefs, a fanout stage runs one investigation per brief, and a reducer synthesizes the reports
  - human pause/resume
  - subpipeline promotion, including a parent pipeline calling a discoverable child pipeline by reference with explicit input/output mapping
  - a minimal optional profile file showing how stage keys and dotted panel slots map to model routes
  - validation failure examples for missing prompt, route bypassing a required read, unknown decision route, and unguarded cycle
- A one-page guide explains "build your first pipeline in 10 minutes" without mentioning Megaplan internals.
- The first 10-minute guide covers only `Pipeline`, `HALT`, `p.input`, `p.agent`, `p.panel`, `p.decision`, `p.flow`, `reads`, `writes`, and `prompt`. Profiles, dynamic fanout, typed ports, and subpipelines are second-page recipes.
- The toy plugin tests exercise the same public APIs a new author uses, not private constructors.
- Generated tests assert build, check, dry-run, prompt existence, and one intentional dataflow failure case.
- New plugin authors never need to import from `arnold.pipelines.megaplan` or know Megaplan's decision labels.
- Advanced features are progressive: a small pipeline does not need typed ports, custom operations, subpipelines, or profile machinery until it opts in.

Anti-goals:

- Do not make authors hand-wire every `Edge` for normal linear and decision flows.
- Do not require a plugin operation implementation for simple pipelines.
- Do not expose `StepContext` internals in the happy-path authoring guide.
- Do not require static markdown prompts when callable prompts are needed, or callable prompts when markdown is enough.
- Do not expose `prompt_key`, `PromptRegistry`, import-side-effect `register_prompt()`, or `prompt_registry=` builder arguments in scaffolds, generated plugins, docs, or the one-page guide. Those are advanced features for multi-mode pipelines and shared step classes. The canonical `prompt=` parameter accepts `str` (`.md` path or inline literal) or `Callable[[StepContext], str]`.
- Do not use a global mutable prompt registry for bundle-scoped resolution. Prompt files resolve against the plugin's `PipelineResourceBundle` prompt directory. The executor receives the bundle at construction time, not via import-time side effects.
- Do not show custom operations, run envelopes, trust tiers, quarantine, typed ports, dynamic fanout, or subpipeline references in the first 10-minute guide.

### Manifest minimalism for simple plugins

The current manifest reader requires more module-level constants than a
simple plugin should need. For simple plugins — no auto loop, no resume,
no overrides — only 3 are genuinely mandatory. The rest should have
documented defaults and be treated as progressive disclosure.

| Field | Simple-plugin stance |
|---|---|
| `name` | **Required.** CLI identity. |
| `entrypoint` | **Required.** Almost always `"build_pipeline"`. |
| `arnold_api_version` | **Required.** Default `"1.0"` in scaffolds. |
| `description` | **Optional.** Default `""`. First line of `SKILL.md` is a reasonable auto-population target for future tooling. |
| `default_profile` | **Optional.** Default `None`. |
| `supported_modes` | **Optional.** Default `()`. Modes are an advanced prompt-variant feature. |
| `driver` | **Optional.** Default `("graph",)` when `build_pipeline()` returns a `Pipeline`. The executor can derive the driver from the graph shape; the literal is only needed for dispatch routing (in-process vs. subprocess isolation). |
| `capabilities` | **Optional.** Default `()`. An empty tuple means "no capability-based dispatch." The `KNOWN_CAPABILITIES` allowlist in `discovery/trust.py` gates capability strings for complex plugins; empty tuples pass through. |

`SKILL.md` remains required as a sibling file — it is the agent-facing
contract and must exist at discovery time.

The manifest reader should be updated so that `driver`, `capabilities`,
`supported_modes`, `description`, and `default_profile` have documented
defaults when absent from module constants. A missing required field
(`name`, `entrypoint`, `arnold_api_version`) or a missing `SKILL.md`
remains a loud `ManifestError`.

`PipelineResourceBundle` is a runtime-internal carrier assembled from
on-disk conventions — plugin authors never subclass or implement it.
Simple plugins see only their directory layout (`prompts/`, `SKILL.md`,
optionally `profiles/`); the runtime assembles the bundle. Trust tiers
and quarantine are path-derived infrastructure concerns that do not
appear in plugin module code.

The first implementation should keep this carrier narrow. Prompt/profile/
`SKILL.md` resolution belongs in `PipelineResources`; manifest hashes,
trust tiers, quarantine state, quotas, and other discovery/security metadata
belong in discovery/runtime metadata unless M-1 proves they need to travel
with resource lookup.

`plugin.toml` is not part of the simple scaffold unless M-1 explicitly
keeps it. Module constants are the minimal manifest; a separate TOML file
must not become a second required metadata source that can drift.

When manifest minimalism lands, update `docs/arnold/package-contract.md`
and `docs/arnold/authoring-guide.md` so the old, wider manifest contract
does not remain as conflicting author guidance.

## What Not To Move First

Do not start by moving `megaplan/_pipeline/stages/*`.

Those stage classes depend on handlers, prompts, state constants, workflow assumptions, and in-process adapters. Moving them first creates import churn without establishing the clean boundary.

Do not start by moving prompts.

The prompts import `_core`, `types`, forms, tickets, contract renderers, and state readers. They are leaf policy code, not the boundary.

Do not start by deleting `GateRecommendation`.

It is wrong in the generic layer, but it is widely used. First create generic replacement types in `arnold/pipeline`, then migrate consumers.

Do not start with a package-wide import rename.

That would produce a giant diff while preserving the same muddled architecture under a new name.

## First Concrete PR

Title:

```text
arnold: inventory package architecture and parity gates
```

Scope:

- Add the whole-package classification table.
- Add source-to-target move map placeholders.
- Add parity smoke-test plan for auto, resume, feedback, tiebreaker, overrides, robustness, status, profiles, CLI, cloud, bakeoff, tickets, epics, and skills.
- Mark the sample `pipeline.py` as illustrative and preserve the existing builder/pattern surface as the target author API.

Do not change runtime behavior in this PR.

Why this first:

- It prevents the cleanup from solving only `_pipeline` while orphaning the rest of the package.
- It turns behavior preservation into explicit acceptance criteria before directory churn.
- It resolves the architecture questions that decide where code moves.

## First Code PR

Title:

```text
arnold: bootstrap neutral pipeline primitives
```

Scope:

- Add `arnold/__init__.py`.
- Add `arnold/py.typed`.
- Add `arnold/pipeline/__init__.py`.
- Add `arnold/pipeline/types.py` with only neutral primitives.
- Add tests enforcing:
  - no import from `megaplan`
  - no `"planning"` literal
  - no Megaplan gate recommendation literals in generic types

Do not change existing runtime behavior in this PR.

Why this first:

- It establishes the destination.
- It forces the generic-vs-policy line in a small reviewable surface.
- It gives later milestones a boundary gate.
- It avoids breaking the current pipeline while the cleanup begins.

## Done Criteria

The cleanup is done when:

- `arnold.pipeline` can run a toy plugin with no Megaplan imports.
- `arnold.pipelines.megaplan` contains the Megaplan workflow, prompts, state, control, profiles, and stage adapters.
- The generic runtime has no hardcoded planning identity or Megaplan gate literals.
- `arnold pipelines list` discovers `megaplan`.
- `arnold run megaplan` works.
- `arnold auto megaplan` works through plugin capabilities.
- `arnold new pipeline demo-reviewer` creates a runnable plugin in one command.
- A developer can build and run a panel/decision/revise pipeline using only public docs and generated examples.
- `arnold pipeline check` catches missing prompts, invalid decisions, broken edge targets, and invalid profile keys before runtime.
- Generic runtime tests still pass if `arnold/pipelines/megaplan/` is temporarily removed.
- Megaplan tests are plugin tests, not platform tests.

## M7 Outcome — Megaplan As The Flagship Arnold App

M7 converged Megaplan into a regular Arnold pipeline package and decontaminated the
generic Arnold substrate of planning-flavored vocabulary. The work spanned three
interconnected tracks: vocabulary decontamination, shim deletion, and manifest
finalization.

### Completed

| # | Item | Detail |
|---|---|---|
| C1 | `CrossCuttingEnvelope` alias deleted | Zero production callers; `RunEnvelope` is canonical. Removed from `arnold/runtime/envelope.py`. |
| C2 | `arnold/cli/forwarder.py` deleted | Pure passthrough to `arnold.cli.main()`. `megaplan` console-script entry removed from `pyproject.toml`. |
| C3 | `routing.py` "Tier N" comments → "Priority N" | 4 cosmetic-only lines; zero behavioral impact. |
| C4 | `TrustTier` → `TrustGrade` rename | `arnold/pipeline/discovery/trust.py` enum renamed; all call sites updated. `TrustClass` (Evidence-First, types.py:603) untouched. |
| C5 | `OperationKind.RUN_PHASE` → `EXECUTE` | Symbol-only rename; wire value `"run_phase"` preserved for state-replay compatibility. 15 call sites updated. |
| C6 | Megaplan content-types migrated out of `_BUILTIN_CONTENT_TYPES` | 4 megaplan-specific MIME types moved to plugin-app `CONTENT_TYPES.register()` call; 3 genuinely generic types stay. |
| C7 | `Pipeline.binding_map` made injectable | `PipelineBuilder.build()` accepts opt-in `derive_bindings`; non-typed-port pipelines never see a derived `binding_map`. |
| C8 | `plan_dir` kwarg → `state_dir` rename | Generic envelope kwarg renamed; `plan_state_lock` function name preserved per SD2. All megaplan call sites updated. |
| C9 | Oracle traces recorded, `CompatibilityMode.LEGACY` deleted | Fresh NATIVE oracle traces in `tests/oracle/fixtures/manifest.json`; LEGACY fallback and `CompatibilityMode` enum removed per oracle-backed proof. |
| C10 | `_legacy_subprocess/` package deleted | Full legacy snapshot removed behind the NATIVE oracle gate. `_FORBIDDEN_PATTERNS` tuple and `scoped_legacy_audit()` removed. |
| C11 | Agent shim audit completed | Full inventory of 30+ importlib shims under `arnold/agent/` recorded in `docs/arnold/m7-agent-shim-audit.md`. No non-empty shim deleted per SD5. |
| C12 | Dual manifest deduplicated | `pipelines/planning/__init__.py` converted to thin re-export; `"plan"` added to canonical `supported_modes`. Registry emits exactly one Megaplan plugin. |
| C13 | M3a compatibility bridge deleted | `_pipeline/discovery/manifest.py` (37-line bridge) deleted; all consumers migrated. `_pipeline/registry.py` retained as megaplan-owned policy authority per SD3. |
| C14 | Docs updated | `docs/pipelines.md` rewritten to describe generic Arnold substrate + Megaplan as consumer plugin. Two successor tickets filed. |

### Deferred (explicit — not forgotten)

| # | Item | Deferred to | Detail |
|---|---|---|---|
| D1 | `SupervisorVariantKind.CHAIN` = `"chain"` | Ticket A (Typed Step-IO Envelope) | Planning-flavored supervisor variant name in generic model. |
| D2 | `RunRecord.plan_id` field | Ticket A | Planning-identity field on generic supervisor record. |
| D3 | `RunRecord.last_phase` field | Ticket A | Megaplan phase name on generic record. |
| D4 | `RunRecord.tier_escalations_used` field | Ticket A | Robustness-tier counter on generic record. |
| D5 | `RunRecord.escalation_tier_pin` field | Ticket A | Tier pin on generic record. |
| D6 | `RunRecord.pr_number` field | Ticket A | Chain PR number on generic record. |
| D7 | `RunRecord.pr_state` field | Ticket A | Chain PR state on generic record. |
| D8 | `NormalizedOutcome.plan` field | Ticket A | Planning name on generic outcome. |
| D9 | `NormalizedOutcome.last_phase` field | Ticket A | Phase name on generic outcome. |
| D10 | `NormalizedOutcome.tier_escalations_used` field | Ticket A | Tier counter on generic outcome. |
| D11 | `OperationKind.OVERRIDE_LIST` enum member | Ticket A | Override-list operation kind — deferred pending Typed Step-IO carrier types. |
| D12 | `OperationKind.OVERRIDE_APPLY` enum member | Ticket A | Override-apply operation kind — deferred pending Typed Step-IO carrier types. |
| D13 | `OperationKind.PROFILE_VALIDATE` enum member | Ticket A | Profile-validate operation kind — deferred pending Typed Step-IO carrier types. |
| D14 | `OperationKind.RESUME` enum member | Ticket A | Resume operation kind — deferred pending Typed Step-IO carrier types. |
| D15 | 15+ planning keys in `OperationRequest.payload` / `StepContext.state` / `hook_extensions` | Ticket A | By-convention dict keys (`phase`, `plan_dir`, `tier_spec`, `success_criteria`, …) crossing the generic control-plane seam as untyped megaplan dicts. |
| D16 | Step 9 oracle traces use un-renamed names | Ticket A | Oracle traces recorded with planning-flavored names; may need re-recording when the Typed Step-IO Envelope epic lands. |
| D17 | Agent shim deletion | Ticket B (Agent Runtime Extraction) | 30+ importlib shims under `arnold/agent/` bridging to `arnold.pipelines.megaplan.agent/`; full audit at `docs/arnold/m7-agent-shim-audit.md`. |
| D18 | Agent real-module relocation | Ticket B | `toolsets.py`, `run_agent.py`, `contracts.py`, `hermes_time.py`, `utils.py`, `providers/*` — real implementations under generic `arnold.agent/` namespace need relocation to megaplan agent package. |
| D19 | Empty `__init__.py` package cleanup | Ticket B | 6 empty `__init__.py` files under `arnold/agent/` already staged as 0-byte; deletion belongs to agent extraction epic. |
| D20 | Deeper supervisor data-model restructuring | Ticket A | Field-level renaming of planning-flavored supervisor fields to plugin-supplied vocabulary — addressed holistically by the Typed Step-IO Envelope epic. |
