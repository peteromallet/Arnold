# Megaplan Native Python Representation Report

## 1. Executive summary

In this report, "native" means more than "the workflow is authored in Python." It means the workflow's product semantics are visible in the Python control flow itself: loops are loops, gates are branches, tiebreakers are subworkflows, review rework is an explicit cycle, human intervention is a suspension point, and task execution fanout is not hidden behind a single opaque handler call.

The current Megaplan planning workflow is Python-authored, but it is still largely an explicit-node manifest graph with handler references. The top-level file `arnold_pipelines/megaplan/workflows/planning.py` defines 13 steps and a route table, but the real behavior of the product is encoded inside handlers in `arnold_pipelines/megaplan/handlers/`, execution code in `arnold_pipelines/megaplan/execute/`, and auto-drive/runtime helpers.

The main finding: a truly native Megaplan pipeline would look like a normal Python program with durable phase calls. Its top-level structure would include:

- a prep clarification gate;
- adaptive critique evaluation with retry;
- parallel critique lenses with fan-in;
- a bounded critique/gate/revise loop with severity-aware termination;
- a tiebreaker subworkflow with researcher/challenger branches and a human decision;
- finalize fallback routes;
- dependency-aware execution over runtime task batches;
- execute/review/rework loops;
- human override and force-proceed routes;
- explicit timeout, retry, escalation, model-routing, and suspension policies.

The repo already has many of the ingredients. Existing native pipeline infrastructure includes `@pipeline`, `@phase`, `@decision`, fixed parallel blocks, native IR compilation, graph projection, bounded loops, suspension routes, retry policy slots, control transition slots, and subpipeline references. The largest missing pieces for Megaplan are runtime-list iteration, dynamic parallel map, source-level retry/timeout/model-routing policy, first-class break/continue or typed loop outcomes, and a top-level way to describe auto-drive/event transitions without forcing handlers to mutate state as a side effect.

## 2. Current state: explicit-node DSL plus handlers

The canonical workflow source is `arnold_pipelines/megaplan/workflows/planning.py`. It describes itself as the product-facing source of truth for the planning graph and says it lowers into the M3 explicit-node `arnold.workflow.dsl.Pipeline` shape consumed by the manifest runtime (`arnold_pipelines/megaplan/workflows/planning.py:3`).

The current graph is a declarative step/route graph:

- steps are `Step(...)` objects with ids such as `prep`, `plan`, `critique`, `gate`, `revise`, `tiebreaker_run`, `tiebreaker_decide`, `finalize`, `execute`, `review`, `halt`, and `override`;
- each phase step stores a `metadata["handler_ref"]` pointing back to `arnold_pipelines.megaplan.handlers:*`;
- route labels and condition refs represent the coarse graph branches;
- a few policy slots are attached, such as loop metadata on `revise` and `tiebreaker_decide`, suspension routes on `gate` and `review`, and control transition slots on `gate`, `review`, and `tiebreaker_decide`.

The high-level route comments in `planning.py` show the intended shape:

```text
prep -> plan -> critique -> gate
                          |-- proceed -> finalize -> execute -> review -> halt
                          |-- iterate -> revise -> critique
                          |-- tiebreaker -> tiebreaker_run -> tiebreaker_decide -> critique
                          |-- escalate / abort / suspend / force-proceed -> override
```

Relevant source locations:

| Area | Source |
| --- | --- |
| Workflow builder entrypoint | `arnold_pipelines/megaplan/workflows/planning.py:91` |
| Step definitions | `arnold_pipelines/megaplan/workflows/planning.py:113` |
| Gate control transitions | `arnold_pipelines/megaplan/workflows/planning.py:141` |
| Revise loop policy | `arnold_pipelines/megaplan/workflows/planning.py:186` |
| Tiebreaker decision loop/policy | `arnold_pipelines/megaplan/workflows/planning.py:211` |
| Review suspension and rework/done transitions | `arnold_pipelines/megaplan/workflows/planning.py:264` |
| Route table | `arnold_pipelines/megaplan/workflows/planning.py:309` |
| Legacy state-machine topology | `arnold_pipelines/megaplan/_core/workflow_data.py:45` |
| Canonical state constants | `arnold_pipelines/megaplan/planning/state.py:7` |

The separate state-machine data in `arnold_pipelines/megaplan/_core/workflow_data.py` is simpler than the handler behavior. It covers the coarse state path from initialized/prepped/planned through critique, gate, finalize, execute, review, done, plus blocked, human, and tiebreaker states. It also has robustness overrides; for example, `bare` allows `planned -> finalize`, and `light` bypasses the full review path by emptying `STATE_EXECUTED` transitions (`arnold_pipelines/megaplan/_core/workflow_data.py:95`).

The mismatch is the central issue: the top-level graph contains phase names and broad edges, while the handlers implement most of the actual control flow.

## 3. Product flow in plain English

Megaplan is a plan-and-execute workflow with multiple quality loops. The full product path is:

```text
initialized
  -> prep
  -> plan
  -> critique
  -> gate
  -> revise/gate loop until acceptable
  -> finalize
  -> execute
  -> review
  -> rework loop if needed
  -> done, blocked, aborted, or awaiting human verification
```

### Prep

Prep gathers task context before planning. It can run research orchestration and produce artifacts such as relevant code, test expectations, open questions, and criteria.

The important product decision is the prep clarification gate. `_apply_prep_clarify_gate()` checks prep output for blocking open questions. If blocking questions exist, the plan enters `STATE_AWAITING_HUMAN_VERIFY`; otherwise it enters `STATE_PREPPED` (`arnold_pipelines/megaplan/handlers/plan.py:21`, `arnold_pipelines/megaplan/handlers/plan.py:209`).

In a native pipeline, this is not just an implementation detail. It is:

```python
prep_payload = await prep()
if has_blocking_questions(prep_payload):
    answers = await suspend_for_human("prep_clarification", prep_payload.open_questions)
    await resume_clarify(answers)
```

### Plan

Plan invokes the planner model, writes a versioned plan artifact, merges/imports criteria, and derives planning metadata such as changed surfaces and test blast radius (`arnold_pipelines/megaplan/handlers/plan.py:140`).

This phase is comparatively linear. Most of it can remain a phase implementation, not top-level topology.

### Critique

Critique judges the plan before execution. It may:

- skip on `bare` robustness;
- run adaptive critique evaluator logic;
- select a subset of critique lenses;
- retry the evaluator once;
- fan out parallel critique workers over selected checks;
- fall back to sequential critique if parallel execution fails;
- write scratch and structured critique artifacts.

The retry and fanout are top-level product structure hidden in `handle_critique()` (`arnold_pipelines/megaplan/handlers/critique.py:279`). The evaluator retry loop starts around `_MAX_EVAL_ATTEMPTS = 2` (`arnold_pipelines/megaplan/handlers/critique.py:384`). Parallel critique dispatch is at `run_parallel_critique(...)` (`arnold_pipelines/megaplan/handlers/critique.py:710`).

In native form, critique is a small subworkflow:

```python
if robustness == "bare":
    return SkipCritique()

selection = await retry(critique_evaluator, attempts=2)
findings = await parallel_map(selection.active_checks, run_critique_lens)
critique_payload = await merge_critique(findings)
```

### Gate

Gate is the central plan-quality decision. It builds signals, invokes a gate worker, normalizes or recovers the worker response, validates flag resolution, reprompts once when unresolved blocking flags remain, applies high-complexity unverifiable-check backstops, records debt on accepted tradeoffs, and routes to proceed, iterate, tiebreaker, blocked, abort, or override.

Key source points:

- `_apply_gate_outcome()` starts at `arnold_pipelines/megaplan/handlers/gate.py:494`;
- `handle_gate()` starts at `arnold_pipelines/megaplan/handlers/gate.py:792`;
- high-complexity unverifiable checks are applied after the worker result (`arnold_pipelines/megaplan/handlers/gate.py:879`);
- unresolved blocking flags trigger a gate reprompt (`arnold_pipelines/megaplan/handlers/gate.py:911`);
- the second pass is merged and can still downgrade to iterate (`arnold_pipelines/megaplan/handlers/gate.py:984`).

Gate is where the critique/gate/revise loop is controlled. At a cap or no-progress threshold, critical unresolved flags lead to `STATE_BLOCKED`, while cosmetic-only unresolved work can force-proceed to `STATE_GATED`. That termination policy is product topology, not incidental parsing logic.

### Revise

Revise updates the plan based on gate feedback. It is the body of the critique loop. `handle_revise()` starts at `arnold_pipelines/megaplan/handlers/critique.py:1055`.

The current top-level graph already marks `revise` with a bounded loop policy (`arnold_pipelines/megaplan/workflows/planning.py:191`), but the branch of whether to go back through critique, gate, or terminate is still distributed across handler state mutations and workflow state logic.

### Tiebreaker

Tiebreaker handles split or ambiguous gate judgments. It has two handler phases:

- `handle_tiebreaker_run()` runs the tiebreaker subflow (`arnold_pipelines/megaplan/handlers/_tiebreaker_impl.py:37`);
- `handle_tiebreaker_decide()` applies a human or requested decision (`arnold_pipelines/megaplan/handlers/_tiebreaker_impl.py:76`).

The product semantics are:

```text
gate says TIEBREAKER
  -> researcher and challenger investigate rival interpretations
  -> human/system decision chooses pick, escalate, or replan
  -> pick goes back into revise/critique, escalate waits for human, replan restarts planning
```

The graph knows about `tiebreaker_run` and `tiebreaker_decide`, but the researcher/challenger split and decision routing are hidden behind handlers.

### Finalize

Finalize turns a gated plan into executable tasks, sense checks, watch items, user actions, validation metadata, and baseline/test-selection details. `handle_finalize()` starts at `arnold_pipelines/megaplan/handlers/finalize.py:1661`.

One topology-relevant branch is error fallback: `FinalizeBaselineSelectionError` can route back to revise (`arnold_pipelines/megaplan/handlers/finalize.py:64`, `arnold_pipelines/megaplan/handlers/finalize.py:1713`).

### Execute

Execute runs the finalized task plan. `handle_execute()` starts at `arnold_pipelines/megaplan/handlers/execute.py:134`.

Execution hides a substantial workflow:

- asks for destructive/user-approved confirmation in relevant modes;
- chooses batch or auto-loop execution;
- dispatches tasks by model tier and task complexity;
- forces fresh sessions for review rework or blocked retries;
- tracks blocked tasks and quality-gate failures;
- writes stub reviews when review is skipped;
- transitions directly to done or human verification for no-review robustness levels.

The large auto-execute loop is `handle_execute_auto_loop()` (`arnold_pipelines/megaplan/execute/batch.py:2278`). Single-batch execution starts at `handle_execute_one_batch()` (`arnold_pipelines/megaplan/execute/batch.py:1201`).

### Review

Review judges the completed work. `handle_review()` starts at `arnold_pipelines/megaplan/handlers/review.py:1297`.

Review can:

- approve the work;
- request rework;
- block;
- route to human verification for deferred human criteria;
- retry review on infrastructure failure;
- run parallel review checks for extreme robustness;
- classify rework as blocking or advisory;
- cap rework cycles and decide between blocked and force-proceed.

The main outcome state machine is `_resolve_review_outcome()` (`arnold_pipelines/megaplan/handlers/review.py:722`). Parallel review is dispatched through `run_parallel_review(...)` (`arnold_pipelines/megaplan/handlers/review.py:1466`).

### Override and human gates

Override is a human/control-plane dispatcher. `_OVERRIDE_ACTIONS` is defined at `arnold_pipelines/megaplan/handlers/override.py:1763`; `handle_override()` starts at `arnold_pipelines/megaplan/handlers/override.py:1780`.

Override actions include add-note, abort, force-proceed, replan, recover-blocked, resume-clarify, set-robustness, set-profile, set-model, and set-vendor. Some are side effects; others are hard control-flow edges.

Native topology should model these as named human/control transitions, not as one opaque `override` handler with an action string.

## 4. Inventory of currently hidden logic

| Step / area | Current source | Hidden control flow | Should be top-level? |
| --- | --- | --- | --- |
| `prep` | `arnold_pipelines/megaplan/handlers/plan.py:21`, `:209` | Blocking open questions route to awaiting-human state. | Yes, as a conditional human suspension. |
| `plan` | `arnold_pipelines/megaplan/handlers/plan.py:140` | Mostly linear worker invocation and artifact write. | No, phase body is fine. |
| `critique` | `arnold_pipelines/megaplan/handlers/critique.py:279` | Bare skip, adaptive evaluator, evaluator retry, active-lens selection, parallel critique fanout, sequential fallback. | Yes. |
| Critique evaluator retry | `arnold_pipelines/megaplan/handlers/critique.py:384` | One initial evaluator attempt plus one retry, with raw-output recovery. | Yes, as retry policy on a sub-step. |
| Parallel critique | `arnold_pipelines/megaplan/handlers/critique.py:710` | Multiple checks run concurrently and merge. | Yes, as parallel map/fan-in. |
| `gate` | `arnold_pipelines/megaplan/handlers/gate.py:792` | Signal build, worker call, validation, retry/reprompt, recommendation recovery, debt recording, route selection. | Yes. |
| Gate outcome routing | `arnold_pipelines/megaplan/handlers/gate.py:494` | Proceed/iterate/tiebreaker/escalate/blocked decisions plus cap/no-progress termination. | Yes, as a decision node plus loop policy. |
| Gate reprompt | `arnold_pipelines/megaplan/handlers/gate.py:911` | Re-run gate worker once when blocking unresolved flags remain. | Yes, as retry/repair edge. |
| Gate high-complexity backstop | `arnold_pipelines/megaplan/handlers/gate.py:879` | PROCEED is auto-downgraded to ITERATE if high-complexity unverifiable checks exist. | Yes, as post-gate validation branch. |
| Gate debt recording | `arnold_pipelines/megaplan/handlers/gate.py:78` | Accepted tradeoffs/unresolved concerns become debt entries on PROCEED. | Partial, as an effect on the proceed edge. |
| `revise` | `arnold_pipelines/megaplan/handlers/critique.py:1055` | Updates plan and re-enters critique/gate loop. | Partial; top-level loop already exists, but routing should be clearer. |
| Tiebreaker validation | `arnold_pipelines/megaplan/handlers/critique.py:1194` | Validates tiebreaker eligibility and can reprompt/route. | Yes, as explicit tiebreaker gate. |
| `tiebreaker_run` | `arnold_pipelines/megaplan/handlers/_tiebreaker_impl.py:37` | Researcher/challenger sub-invocations. | Yes, as a subworkflow with fanout. |
| `tiebreaker_decide` | `arnold_pipelines/megaplan/handlers/_tiebreaker_impl.py:76` | Pick/escalate/replan decision routing. | Yes, as human/control decision. |
| `finalize` | `arnold_pipelines/megaplan/handlers/finalize.py:1661` | Baseline-selection failure fallback to revise. | Yes, as error edge. |
| `execute` | `arnold_pipelines/megaplan/handlers/execute.py:134` | Batch vs auto-loop, user/destructive gates, blocked retry, fresh sessions, no-review terminal routing. | Yes. |
| Execute single batch | `arnold_pipelines/megaplan/execute/batch.py:1201` | Batch unit execution and result merge. | Yes, as task batch subworkflow. |
| Execute auto loop | `arnold_pipelines/megaplan/execute/batch.py:2278` | Dependency-aware task scheduling, blocked-task handling, batch iteration. | Yes, as dynamic foreach/map over task batches. |
| `review` | `arnold_pipelines/megaplan/handlers/review.py:1297` | Review mode selection, parallel review, outcome state machine, rework cap, human verification. | Yes. |
| Review outcome | `arnold_pipelines/megaplan/handlers/review.py:722` | Approved/needs-rework/blocked routing, cap behavior, force-proceed vs blocked. | Yes, as decision plus loop. |
| Parallel review | `arnold_pipelines/megaplan/handlers/review.py:1466` | Extreme robustness fanout and merge. | Yes. |
| Override | `arnold_pipelines/megaplan/handlers/override.py:1763`, `:1780` | Action dispatch to abort, force-proceed, replan, resume, recover, profile/model changes. | Yes, at least for routing actions. |
| Phase runtime observability | `arnold_pipelines/megaplan/_core/phase_runtime.py` | Expected durations, stale/dead worker detection, timeout metadata. | Partial, as top-level timing/escalation policy. |
| Auto-drive loop | `arnold_pipelines/megaplan/auto.py` | Re-derives next steps, applies retry/escalation/cost/stall policies. | Yes, as runtime policy and event loop rather than handler side effects. |

The recurring pattern is clear: the graph has phase labels, while handlers are mini-orchestrators. A true native pipeline would lift those mini-orchestrators into named, inspectable topology.

## 5. Native Python representation

Below is an aspirational `arnold_pipelines/megaplan/workflows/planning_native.py`. It is intentionally unconstrained by the current manifest/compiler restrictions. The syntax uses ordinary Python plus imagined durable decorators and helpers. The goal is to show what the workflow would look like if everything that belongs at the top level could actually be expressed there.

```python
from __future__ import annotations

from arnold.pipeline.native import (
    effect,
    foreach,
    human_gate,
    model_route,
    parallel_map,
    phase,
    pipeline,
    retry,
    subworkflow,
)


@phase(model=model_route("prep"))
async def prep(ctx) -> PrepPayload: ...

@phase(model=model_route("planner"))
async def plan(ctx, prep_payload) -> PlanPayload: ...

@subworkflow
async def critique(ctx, plan_payload) -> CritiquePayload:
    if ctx.robustness == "bare":
        return CritiquePayload.skipped("bare robustness")

    selection = await retry(critique_evaluator, attempts=2)(ctx, plan_payload)
    findings = await parallel_map(
        selection.active_checks,
        lambda check: critique_lens(ctx, check, plan_payload),
        reducer=merge_critique,
        fallback="sequential",
    )
    return findings

@subworkflow
async def gate(ctx, plan_payload, critique_payload, loop_state) -> tuple[GateAction, GatePayload]:
    signals = await build_gate_signals(ctx, plan_payload, critique_payload)
    payload = await normalize_gate_payload(await gate_worker(ctx, signals), signals)

    unresolved = await validate_flag_resolution(payload, signals)
    if unresolved.blocking_ids:
        payload = await retry(
            reprompt_gate_worker,
            attempts=1,
            on_exhausted="downgrade_to_iterate",
        )(ctx, signals, unresolved.blocking_ids)

    if signals.has_high_complexity_unverifiable_checks and payload.recommendation == "proceed":
        return "iterate", payload.with_reason("unverifiable high-complexity check")

    if loop_state.exhausted_or_stalled:
        return ("blocked" if signals.has_correctness_or_security_blockers else "force_proceed"), payload

    if payload.recommendation in {"proceed", "force_proceed"}:
        await effect("record_gate_debt", payload=payload, signals=signals)

    return payload.recommendation, payload

@phase(model=model_route("planner"))
async def revise(ctx, plan_payload, gate_payload) -> PlanPayload: ...

@subworkflow
async def tiebreaker(ctx, gate_payload) -> TiebreakerDecision:
    researcher, challenger = await parallel_map(
        ["researcher", "challenger"],
        lambda role: run_tiebreaker_role(ctx, role, gate_payload),
        reducer=list,
    )
    action = await human_gate("tiebreaker_decide", choices=("pick", "escalate", "replan"))(
        gate_payload,
        [researcher, challenger],
    )
    return TiebreakerDecision(action=action, arguments=[researcher, challenger])

@phase(model=model_route("finalize"))
async def finalize(ctx, plan_payload, gate_payload) -> FinalizePayload: ...

@subworkflow
async def execute(ctx, finalize_payload) -> ExecutePayload:
    if finalize_payload.requires_user_approval and not ctx.user_approved:
        await human_gate("execute_approval")(finalize_payload)

    batch_results = []
    async for batch in foreach.dag_batches(finalize_payload.tasks, depends_on="depends_on"):
        result = await execute_task_batch(ctx, batch, model=model_route("execute", by="task.complexity"))
        batch_results.append(result)
        if result.blocked and not result.retryable:
            break
    return await merge_execution_results(batch_results)

@subworkflow
async def review(ctx, execute_payload, rework_loop) -> tuple[ReviewAction, ReviewPayload]:
    if ctx.robustness == "extreme":
        payload = await parallel_map(
            ReviewCheck.for_robustness(ctx.robustness),
            lambda check: review_check(ctx, check, execute_payload),
            reducer=merge_review,
        )
    else:
        payload = await retry(review_worker, attempts=2, retry_on={"infrastructure_failure"})(
            ctx,
            execute_payload,
        )
    return resolve_review_action(payload, rework_loop), payload

@pipeline(name="megaplan-planning-native")
async def planning_native(ctx) -> MegaplanResult:
    prep_payload = await prep(ctx)
    if prep_payload.has_blocking_questions:
        answers = await human_gate("prep_clarification")(prep_payload.open_questions)
        prep_payload = prep_payload.with_clarification(answers)

    plan_payload = await plan(ctx, prep_payload)
    critique_loop = LoopState(max_iterations=ctx.max_critique_iterations)

    while True:
        critique_payload = await critique(ctx, plan_payload)
        gate_action, gate_payload = await gate(ctx, plan_payload, critique_payload, critique_loop)

        if gate_action in {"proceed", "force_proceed"}:
            break
        if gate_action == "iterate":
            plan_payload = await revise(ctx, plan_payload, gate_payload)
            critique_loop = critique_loop.next_round(gate_payload)
            continue
        if gate_action == "tiebreaker":
            decision = await tiebreaker(ctx, gate_payload)
            if decision.action == "pick":
                plan_payload = await revise(ctx, plan_payload, gate_payload.with_tiebreaker(decision))
                continue
            if decision.action == "replan":
                plan_payload = await plan(ctx, prep_payload)
                continue
        action = await human_gate("override", reason=f"gate:{gate_action}")(gate_payload)
        if action.kind == "abort":
            return MegaplanResult.aborted(action.reason)
        if action.kind == "force-proceed":
            break
        if action.kind == "replan":
            plan_payload = await plan(ctx, prep_payload)

    try:
        finalize_payload = await finalize(ctx, plan_payload, gate_payload)
    except FinalizeBaselineSelectionError as error:
        plan_payload = await revise(ctx, plan_payload, GatePayload.from_error(error))
        finalize_payload = await finalize(ctx, plan_payload, gate_payload)

    rework_loop = LoopState(max_iterations=ctx.max_review_rework_cycles)
    while True:
        execute_payload = await execute(ctx, finalize_payload)
        if execute_payload.blocked:
            action = await human_gate("override", reason="execution_blocked")(execute_payload)
            if action.kind != "recover-blocked":
                return MegaplanResult.blocked(execute_payload)
            continue

        if ctx.robustness in {"bare", "light"} and not execute_payload.requires_human_verify:
            return MegaplanResult.done(execute_payload)

        review_action, review_payload = await review(ctx, execute_payload, rework_loop)
        if review_action == "approved":
            return MegaplanResult.done(review_payload)
        if review_action == "human_verify":
            await human_gate("review_human_verify")(review_payload)
            return MegaplanResult.done(review_payload)
        if review_action == "needs_rework":
            finalize_payload = finalize_payload.scope_to_rework(review_payload.rework_items)
            rework_loop = rework_loop.next_round(review_payload)
            continue
        if review_action == "blocked":
            return MegaplanResult.blocked(review_payload)
```


## 6. Required top-level constructs

| Construct | Why Megaplan needs it | Exists today? | Evidence |
| --- | --- | --- | --- |
| Sequential durable phases | All major steps need checkpointed phase calls. | Yes. | `@phase` in `arnold/pipeline/native/decorators.py:16`; runtime in `arnold/pipeline/native/runtime.py:198`. |
| Native pipeline functions | Top-level product flow should be a Python function. | Yes, partially. | `@pipeline` in `arnold/pipeline/native/decorators.py:59`; `compile_pipeline()` in `arnold/pipeline/native/compiler.py:53`. |
| Decisions / branches | Gate, review, prep, tiebreaker, override. | Yes. | `@decision` in `arnold/pipeline/native/decorators.py:93`; branch pattern in `arnold/patterns/control.py:33`. |
| Human suspension | Prep clarification, tiebreaker decide, review human verification, override. | Yes. | Human gate metadata in `@decision` (`arnold/pipeline/native/decorators.py:93`); generic `human_gate()` in `arnold/patterns/control.py:230`; `SuspensionRoute` in `arnold/manifest/manifests.py:216`. |
| Bounded loops | Critique/gate/revise and review/rework need caps. | Yes, but awkward. | `LoopPolicy` in `arnold/manifest/manifests.py:87`; loop pattern in `arnold/patterns/control.py:70`; current `revise` loop in `planning.py:191`. |
| While-until predicates | Loop should stop on gate pass, cap, no progress, or severity branch. | Partial. | `LoopPolicy.until_ref` exists (`arnold/manifest/manifests.py:91`), but source compiler only accepts `while True` with literal policy (`arnold/workflow/source_compiler.py:1451`). |
| Break / continue or typed loop outcomes | Native Megaplan wants ordinary loop control. | Missing in compiler subsets. | Source compiler rejects break/continue (`arnold/workflow/source_compiler.py:1525`); native compiler also rejects them (`arnold/pipeline/native/compiler.py:659`). |
| Static parallel fanout | Fixed review panels and fixed critique panels. | Yes. | `parallel()` in `arnold/pipeline/native/decorators.py:177`; `fanout()`/`panel()` in `arnold/patterns/control.py:105`. |
| Dynamic parallel map over runtime lists | Critique selected lenses, finalize task batches, review checks. | Missing at source level. | Dynamic fanout exists as imperative runtime machinery, but native `parallel()` requires literal branches (`arnold/pipeline/native/decorators.py:177`). |
| Fan-in / reducer | Merge critique, tiebreaker, review, execution results. | Yes. | Reducer support on `parallel()` (`arnold/pipeline/native/decorators.py:180`); `FanoutPolicy.reducer_ref` (`arnold/manifest/manifests.py:96`). |
| Subworkflow invocation | Critique, gate, tiebreaker, execute, review should be nested workflows. | Yes, manifest-level. | `subpipeline()` in `arnold/patterns/base.py:112`; `SubpipelineRef` in `arnold/manifest/manifests.py:208`. |
| Retry policy at call site | Critique evaluator, gate reprompt, review infrastructure, external failures. | Partial. | `RetryPolicy` in `arnold/manifest/manifests.py:78`; `retry()` pattern in `arnold/patterns/control.py:185`; no source-level phase-call retry keyword. |
| Timeout/deadline policy | Phase timeouts, stale/dead process detection, auto-drive phase timeout. | Partial. | `TimingPolicy` in `arnold/manifest/manifests.py:154`; phase runtime policy exists in `_core/phase_runtime.py`; not ergonomic at native call site. |
| Event-driven transitions | Override, resume, cancel, pause, recovery, auto-drive liveness events. | Partial. | `ControlTransitionSlot` in `arnold/manifest/manifests.py:173`; planning graph uses slots at `planning.py:141`; source-level event syntax remains limited. |
| Topology overlays | Runtime route mutations or control overlays. | Exists as metadata slot. | `TopologyOverlaySlot` in `arnold/manifest/manifests.py:185`; `_node_policy()` accepts overlays in `planning.py:21`. |
| Model routing | Tiered model choice by phase, task complexity, robustness, vendor overrides. | Missing from workflow manifest. | Agent-level routing exists elsewhere, but no first-class workflow policy slot was found. |
| Edge effects / compensation | Gate debt recording, checkpoints, failure events, state recovery. | Partial. | Effect/compensation policy slots exist in `arnold/manifest/manifests.py:113`, but current Megaplan side effects remain handler code. |
| Resume cursors | Human gates and long-running loops need durable resume. | Exists. | Suspension route support and native runtime resume support; current graph uses reentry ids in `planning.py:194` and `planning.py:219`. |
| Dynamic DAG scheduling | Execute tasks need dependency-aware batching over finalized runtime data. | Missing at source/topology level. | Current implementation is inside `execute/batch.py:2278`. |

## 7. Gap analysis

### What exists today and can be reused

The Arnold native/pipeline substrate already has a credible base:

- lightweight decorators for phases, pipelines, decisions, fixed parallel blocks, and panels (`arnold/pipeline/native/decorators.py:16`);
- AST compilation into native IR (`arnold/pipeline/native/compiler.py:53`);
- native runtime execution (`arnold/pipeline/native/runtime.py:198`);
- graph projection for compatibility and topology hashing (`arnold/pipeline/native/graph_projection.py:124`);
- policy dataclasses for retry, loop, fanout, timing, control transitions, subpipelines, suspension, and topology overlays (`arnold/manifest/manifests.py:78`);
- control pattern constructors for branch, loop, fanout, panel, retry, and human gates (`arnold/patterns/control.py:33`);
- subpipeline references (`arnold/patterns/base.py:112`);
- existing native-first packages such as `arnold/pipelines/folder_audit/native.py` and `arnold/pipelines/deliberation/native.py`.

The current `planning.py` already uses some of the manifest-level policy slots:

- gate control transitions and suspension routes (`arnold_pipelines/megaplan/workflows/planning.py:141`);
- revise loop policy (`arnold_pipelines/megaplan/workflows/planning.py:191`);
- tiebreaker decision loop and transitions (`arnold_pipelines/megaplan/workflows/planning.py:216`);
- review human suspension and control transitions (`arnold_pipelines/megaplan/workflows/planning.py:269`).

This means the migration does not require inventing a runtime from nothing. It requires raising the abstraction from explicit nodes plus opaque handlers to native call-site constructs.

### What is missing or too constrained

The biggest gap is dynamic runtime topology.

Megaplan does not know all critique checks, review checks, task batches, or tiebreaker shape as static literal branches at import time. The current native `parallel()` helper requires a literal list/tuple of `@phase` callables (`arnold/pipeline/native/decorators.py:177`). That works for deliberation-style fixed panels; it is not enough for Megaplan's runtime lists.

The second gap is loop expressiveness.

Both current source/compiler subsets treat loops as bounded control constructs, not ordinary Python loops:

- the source compiler requires `while True` with an adjacent literal loop policy (`arnold/workflow/source_compiler.py:1451`);
- it rejects `break` and `continue` (`arnold/workflow/source_compiler.py:1525`);
- the native compiler also rejects `break` and `continue` inside while (`arnold/pipeline/native/compiler.py:659`).

Megaplan wants loops with semantic exits: gate passed, gate said iterate, tiebreaker requested replan, cap exhausted with critical or cosmetic flags, review approved, review asked for rework, or review cap exhausted. These can be represented without raw Python `break`/`continue` if the runtime supports typed loop outcomes, but they need a first-class form.

The third gap is policy at the phase call site.

Retries, timeouts, model routing, vendor fallback, human authority, and edge effects exist in scattered forms, but Megaplan authors need to be able to write something like:

```python
payload = await retry(gate_worker, attempts=1, on_still_blocked="iterate")(ctx, signals)
findings = await parallel_map(checks, critique_lens, model_route=lambda check: check.tier)
await effect("record_gate_debt", when=gate_action == "proceed")
```

Today, much of that remains inside handlers or profile/runtime code.

The fourth gap is event/control-plane clarity.

Override actions are real product edges. The native representation should make abort, force-proceed, replan, resume-clarify, recover-blocked, and model/vendor/profile/robustness changes visible instead of hiding them behind one action string.

## 8. Recommendation

Build toward the native representation in slices. Do not try to convert the entire Megaplan handler stack at once.

### 1. Start with trace-only native shadow topology

Create `arnold_pipelines/megaplan/workflows/planning_native.py` as a non-executing or dry-run topology shadow. It should call existing handlers as coarse phases while exposing the prep clarification branch, critique/gate/revise loop, tiebreaker branch, finalize fallback, execute/review/rework loop, and override branches.

This gives reviewers a concrete target without changing runtime behavior.

### 2. Add dynamic `foreach` / `parallel_map`

This is the highest-value runtime feature. It unlocks:

- adaptive critique over selected checks;
- extreme review over selected checks;
- execute over finalized task batches;
- any future model-panel or tournament behavior with runtime cardinality.

The construct should lower to an inspectable fanout/fan-in IR with:

- source collection reference;
- item schema;
- per-item phase;
- max workers;
- reducer;
- per-item retry/fallback policy;
- deterministic artifact naming.

### 3. Add source-level phase-call policy

Expose retry, timeout, model routing, and fallback at the call site. The manifest has policy slots, but the authoring experience needs to be native:

```python
await gate_worker(ctx, signals, retry=Retry(max_attempts=2), timeout=Minutes(20))
```

or decorator-based:

```python
@phase(retry=Retry(max_attempts=2), model=model_route("gate"))
async def gate_worker(...): ...
```

This should replace local loops such as the critique evaluator retry and gate reprompt retry.

### 4. Model loop exits explicitly

Choose one approach:

- support `break`/`continue` in native compiler lowering; or
- define typed loop outcomes such as `Loop.continue_(state)`, `Loop.break_(value)`, `Loop.escalate(reason)`.

The second option may be easier to compile into durable topology and clearer for manifests. Megaplan's loops are not arbitrary Python loops; they are policy loops with audit requirements.

### 5. Split handler orchestration from phase bodies

Once the native skeleton exists, move orchestration out of handlers in this order:

1. gate retry/downgrade/debt branch;
2. critique evaluator and critique fanout;
3. review outcome/rework loop;
4. tiebreaker researcher/challenger/decide subworkflow;
5. execute task-batch foreach.

The phase bodies can initially call the old internal functions. The first win is topology visibility, not deleting all existing handler code.

### 6. Make override a control-plane subworkflow

Replace the single opaque `override` node with a small top-level control-plane surface:

- `override_abort`;
- `override_force_proceed`;
- `override_replan`;
- `override_resume_clarify`;
- `override_recover_blocked`;
- `override_config_change`.

Configuration-only overrides can remain effect phases. Routing overrides should be graph-visible.

### 7. Keep graph projection and compatibility during migration

Megaplan has many tests and external expectations around state names, artifact names, route labels, and auto-drive behavior. The native pipeline should project to graph/manifest output for compatibility until the native runtime is proven equivalent.

Minimum parity checks:

- current `planning.py` graph and native projection have matching public phase ids for coarse milestones;
- state-machine transitions remain compatible with `_core/workflow_data.py`;
- characterization tests in the auto-drive corpus still pass;
- artifact names remain stable;
- override and resume commands still work;
- existing `megaplan auto` behavior is unchanged until explicitly switched.

The desired end state is not "handlers disappear." It is that handlers become phase bodies, and the product's real control flow becomes visible, durable, inspectable Python.
