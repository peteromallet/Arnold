from __future__ import annotations

import inspect
from dataclasses import fields, is_dataclass
from types import MappingProxyType
from typing import Any

import pytest

import arnold.patterns as patterns
import arnold.workflow as workflow
from arnold.patterns import (
    PatternBlock,
    agent,
    branch,
    external_call,
    fanout,
    human_gate,
    loop,
    merge,
    panel,
    retry,
    revise,
    subpipeline,
    tournament,
)
from arnold.workflow import (
    Capability,
    Input,
    LoopPolicy,
    Output,
    Pipeline,
    RefDiagnosticError,
    RetryPolicy,
    Route,
    SourceSpan,
    Step,
    WorkflowPolicy,
    compile_pipeline,
)
from tests.arnold.patterns import _fixtures

HASH_A = "sha256:" + "a" * 64


class CallablePrompt:
    def __call__(self, draft: str) -> str:
        return f"callable({draft})"


def _no_live_objects(value: Any) -> None:
    """Recursively assert no function, method, or callable-instance capture."""

    if value is None:
        return
    if inspect.isfunction(value) or inspect.ismethod(value) or inspect.isbuiltin(value):
        raise AssertionError(f"captured live function/method: {value!r}")
    if callable(value) and not isinstance(value, type):
        raise AssertionError(f"captured callable instance: {value!r}")
    if isinstance(value, (str, int, float, bool)):
        return
    if is_dataclass(value):
        for item in fields(value):
            _no_live_objects(getattr(value, item.name))
        return
    if isinstance(value, MappingProxyType):
        for subvalue in value.values():
            _no_live_objects(subvalue)
        return
    if isinstance(value, dict):
        for subvalue in value.values():
            _no_live_objects(subvalue)
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            _no_live_objects(item)
        return


def test_base_constructors_are_pure_and_use_durable_refs() -> None:
    step = agent(
        "plan",
        task="draft",
        prompt_ref="tests.arnold.patterns._fixtures:agent_prompt",
        outputs=("draft",),
        capabilities=(Capability("agent:planner"),),
        source_span=SourceSpan("pipeline.py", 5),
    )

    assert step.kind == "agent"
    assert step.metadata["prompt_ref"] == "tests.arnold.patterns._fixtures:agent_prompt"
    _no_live_objects(step)


def test_base_constructors_accept_import_ref_and_hook_ref() -> None:
    import_ref = workflow.ImportRef.from_callable(_fixtures.agent_prompt)
    hook_ref = workflow.HookRef.from_callable(_fixtures.decide_condition)

    assert agent("a", task="t", prompt_ref=import_ref).metadata["prompt_ref"] == import_ref.spec
    assert external_call("e", endpoint_ref=hook_ref).metadata["endpoint_ref"] == hook_ref.spec
    assert merge("m", reducer_ref=hook_ref).metadata["reducer_ref"] == hook_ref.spec


def test_base_constructors_reject_unstable_callables() -> None:
    captured = "state"

    def closure() -> str:
        return captured

    cases = [
        ("prompt_ref", lambda: "x"),
        ("endpoint_ref", closure),
        ("reducer_ref", CallablePrompt()),
    ]
    for field_name, bad in cases:
        with pytest.raises(RefDiagnosticError) as exc_info:
            if field_name == "prompt_ref":
                agent("a", task="t", prompt_ref=bad)
            elif field_name == "endpoint_ref":
                external_call("e", endpoint_ref=bad)
            else:
                merge("m", reducer_ref=bad)

        assert field_name in str(exc_info.value)


def test_subpipeline_step_carries_subpipeline_ref() -> None:
    step = subpipeline("inner", manifest_hash=HASH_A, alias="nested")

    assert step.kind == "subpipeline"
    assert step.subpipeline is not None
    assert step.subpipeline.manifest_hash == HASH_A
    assert step.subpipeline.alias == "nested"


def test_branch_pattern_lowers_to_explicit_routes() -> None:
    block = branch(
        "decide",
        condition_ref="tests.arnold.patterns._fixtures:decide_condition",
        then_id="plan",
        else_id="fallback",
    )

    assert isinstance(block, PatternBlock)
    assert len(block.steps) == 1
    assert block.steps[0].kind == "branch"
    assert len(block.routes) == 2
    assert {route.label for route in block.routes} == {"then", "else"}
    _no_live_objects(block)


def test_loop_pattern_is_valid_bounded_reentry() -> None:
    block = loop(
        "loop",
        body_id="body",
        until_ref="tests.arnold.patterns._fixtures:decide_condition",
        max_iterations=3,
        reentry_id="retry",
    )
    pipeline = Pipeline(
        id="looping",
        version="v1",
        steps=[
            Step(id="body", kind="agent"),
            *block.steps,
        ],
        routes=[
            Route(id="loop-body", source="loop", target="body", label="go"),
            *block.routes,
        ],
    )

    manifest = compile_pipeline(pipeline)
    assert any(edge.condition_ref == "retry" for edge in manifest.edges)


def test_retry_pattern_is_valid_bounded_reentry() -> None:
    block = retry("retry", target_id="fragile", max_attempts=3, retry_on=("error",))
    pipeline = Pipeline(
        id="retrying",
        version="v1",
        steps=[Step(id="fragile", kind="agent"), *block.steps],
        routes=[*block.routes],
    )

    manifest = compile_pipeline(pipeline)
    assert any(edge.condition_ref == "retry:retry" for edge in manifest.edges)


def test_panel_pattern_lowers_fanout_and_join_routes() -> None:
    block = panel(
        "fan",
        branch_ids=("branch-a", "branch-b"),
        merge_id="merged",
        reducer_ref="tests.arnold.patterns._fixtures:reducer",
    )

    assert len(block.steps) == 2  # fanout + merge
    fanout_step = block.steps[0]
    assert fanout_step.kind == "fanout"
    assert fanout_step.policy is not None
    assert fanout_step.policy.fanout is not None
    assert fanout_step.policy.fanout.reducer_ref == "tests.arnold.patterns._fixtures:reducer"
    join_routes = [route for route in block.routes if route.label == "join"]
    assert len(join_routes) == 2


def test_human_gate_is_generic_suspension_step() -> None:
    step = human_gate("gate", capability_id="human:operator", reentry_id="resume")

    assert step.kind == "suspension"
    assert step.capabilities[0].id == "human:operator"
    assert step.policy is not None
    assert step.policy.suspension_routes[0].reentry_id == "resume"


def test_tournament_lowers_two_full_tiebreaker_rounds() -> None:
    block = tournament(
        "tourney",
        candidate_ids=("candidate-a", "candidate-b"),
        merge_id="winner",
        winner_ref="tests.arnold.patterns._fixtures:judge_winner",
        tie_ref="tests.arnold.patterns._fixtures:decide_condition",
    )

    ids = {step.id for step in block.steps}
    assert "tourney-judge" in ids
    assert "tourney-tiebreak-1" in ids
    assert "tourney-tiebreak-2" in ids
    assert "winner" in ids

    tie_routes = [route for route in block.routes if route.label == "tie"]
    assert len(tie_routes) == 2
    assert tie_routes[0].source == "tourney-judge"
    assert tie_routes[0].target == "tourney-tiebreak-1"
    assert tie_routes[1].source == "tourney-tiebreak-1"
    assert tie_routes[1].target == "tourney-tiebreak-2"

    winner_routes = [route for route in block.routes if route.label == "winner"]
    assert len(winner_routes) == 3  # judge, tiebreak1, tiebreak2 -> merge


def test_revise_pattern_lowers_bounded_reentry() -> None:
    block = revise(
        "revise",
        target_id="draft",
        revise_ref="tests.arnold.patterns._fixtures:agent_prompt",
        until_ref="tests.arnold.patterns._fixtures:decide_condition",
        max_iterations=4,
        reentry_id="retry",
    )

    assert block.steps[0].kind == "revise"
    assert block.steps[0].policy is not None
    assert block.steps[0].policy.loop is not None
    assert block.steps[0].policy.loop.max_iterations == 4


def test_patterns_module_exports_stability_markers() -> None:
    assert hasattr(patterns, "PUBLIC_EXPORTS")
    assert hasattr(patterns, "PROVISIONAL_EXPORTS")
    assert hasattr(patterns, "INTERNAL_EXPORTS")
    assert hasattr(patterns, "__all__")
    assert "agent" in patterns.PUBLIC_EXPORTS
    assert "tournament" in patterns.PUBLIC_EXPORTS
    assert "tournament" in patterns.PROVISIONAL_EXPORTS
