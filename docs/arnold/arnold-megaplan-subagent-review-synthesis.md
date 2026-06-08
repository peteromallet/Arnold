# Arnold/Megaplan Subagent Review Synthesis

Date: 2026-06-01
Branch: `arnold-epic`
Run artifacts: `/tmp/arnold-subagent-review-20260601-171600`

## Panel

The review used:

- DeepSeek V4 Pro fanout: seven focused probes on end-state elegance, abstraction/composability, prompts, dataflow, loops/gates, parity, and authoring ergonomics.
- Codex: two read-only architecture reviews on elegance and abstractions.
- Claude: two read-only architecture reviews on elegance and abstractions.

All usable reports completed. One duplicate Claude retry produced no useful output and was ignored.

## Consensus Verdict

The boundary thesis is correct: Arnold should own the policy-blind runtime and Megaplan should be one built-in plugin that owns planning policy.

The current cleanup plan is directionally elegant, but its illustrative API is too thin if interpreted literally. The cleanup must be a re-home plus policy extraction, not a rewrite to a smaller pipeline DSL.

The working code already proves composability through non-planning pipelines such as `creative`, `doc`, `jokes`, `writing-panel-strict`, `epic-blitz`, and `select-tournament`. The plan should preserve and re-home that existing builder and pattern vocabulary, not replace it with static `Pipeline(stages={}, edges=[])` sketches.

## Required Plan Corrections

1. Preserve the existing composition surface.
   Keep `PipelineBuilder` and the pattern library as the recommended author API. The dataclass graph can remain the low-level representation, but it should not become the only user-facing API.

2. Treat the sample `pipeline.py` as pseudocode.
   It omits load-bearing behavior: tiebreaker, override edges, fallback edges, loop caps, robustness-dependent topology, dynamic prompt construction, and stateful execute/finalize/review handlers.

3. Make gate routing plugin-owned.
   Generic runtime should use `str` routing keys with per-stage declared decisions. Megaplan owns `proceed`, `iterate`, `tiebreaker`, `escalate` and its override actions. Do not keep `GateRecommendation` or `OverrideAction` as generic literals.

4. Keep decision routing and overrides separate.
   A generic gate/decision primitive needs decisions, override actions, and extra/fallback edges. Do not collapse user overrides such as force-proceed or abort into the same enum as model gate recommendations.

5. Preserve dynamic topology.
   Robustness levels are not just prompt variants. They change graph shape, reviewer counts, loop caps, and optional prep/feedback paths. `build_pipeline(config)` or overlays must be able to compute different graphs.

6. Keep prompt-as-code.
   Megaplan prompts are dynamic builders, not just `.md` files. `PromptLoader` should accept `str | Callable[[StepContext], str]`; static markdown prompts are the simple case, not the canonical case.

7. Preserve typed dataflow and state safety.
   Move typed ports, content types, taint/provenance, artifact binding, `StateDelta`, and compare-and-swap state semantics into Arnold runtime. Bare filenames are not enough for composable fanout/fan-in pipelines.

8. Preserve fanout, joins, reducers, and loop caps.
   Current primitives like `ParallelStage`, `dynamic_fanout`, `majority_vote`, `weighted_vote`, `ReduceResult`, `SelectionResult`, `iterate_until`, and loop predicates are generic. They must survive M3.

9. Preserve subpipeline promotion.
   `SubloopStep.promote`, artifact subdirectories, and explicit parent/child state promotion are the hard part of composition. A `Subpipeline` box without a `promote` contract is insufficient.

10. Add a whole-package classification before the big move.
    The plan currently focuses on `_pipeline` and planning stages while leaving `chain`, `cloud`, `store`, `orchestration`, `supervisor`, `resident`, `workers`, `observability`, `agent`, `execute`, `review`, `editorial`, and other top-level modules under-specified. That classification is the architecture.

11. Seam before move.
    Introduce plugin capability operation interfaces for auto, run-phase, resume, status/control, overrides, and profiles before directory churn. Then moves become mechanical.

12. Add behavior parity gates.
    Static import/string tests are necessary but insufficient. Protect auto, resume, feedback, tiebreaker, override/fallback edges, robustness loop depth, manifest integrity, status projection, profile validation, and CLI dispatch with smoke tests before moving code.

## Highest-Risk Current Code Couplings

- `Pipeline.run_phase()` in `megaplan/_pipeline/types.py`: planning-specific CLI arg parsing, `feedback` special case, `_core` imports, and `inputs={"_pipeline": "planning"}`.
- `auto.py`: `PipelineRegistry().get("planning")` and planning-specific phase assumptions.
- `_core/workflow.py`: resume fallback to `"planning"` and manifest hash checks.
- `control_interface.py` and `cli/status_view.py`: planning-only binding and status projection.
- `_pipeline/types.py`, `_pipeline/builder.py`, `_pipeline/pattern_topology.py`, and `_pipeline/validator.py`: generic-looking gate literals and tiebreaker policy.
- `profiles/__init__.py`: phase validation tied to planning defaults.
- `prompts/*.py`: dynamic prompt builders that must move as code, not flatten to static markdown.

## Practical Next Step

Before executing M0, amend the cleanup plan so M0 starts with a behavior/module inventory and the extraction milestones explicitly retain these proven primitives:

- builder and patterns as the authoring surface
- dynamic fanout and joins
- loop predicates and max-iteration caps
- prompt overlays and callable prompts
- typed ports/content types/taint/CAS state
- subpipeline `promote`
- generic decision routing with plugin-owned vocabularies
- auto/resume/control/status/profile operation interfaces
- behavioral parity smoke tests

Only after those are written into the plan should the cleanup chain start modifying runtime code.
