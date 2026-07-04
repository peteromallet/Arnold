"""Compositional native workflow example for the ``_template`` package."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from arnold.pipeline import StepResult
from arnold.pipeline.native import (
    compile_pipeline,
    decision,
    parallel_map,
    phase,
    pipeline,
    start_from_trace,
    workflow,
)
from arnold.pipeline.native.ir import NativeProgram


def _required_schema(*names: str) -> dict[str, Any]:
    return {"type": "object", "required": list(names)}


@phase(
    name="draft_outline",
    id="template.draft_outline",
    outputs=_required_schema("outline"),
)
def draft_outline(ctx: dict[str, Any]) -> StepResult:
    del ctx
    return StepResult(outputs={"outline": "TODO: outline.md"}, next="halt")


@phase(
    name="review_findings",
    id="template.review_findings",
    inputs=_required_schema("outline"),
    outputs=_required_schema("findings"),
)
def review_findings(ctx: dict[str, Any]) -> StepResult:
    outline = ctx["state"].get("working_outline") or ctx["state"].get("outline") or "TODO"
    return StepResult(outputs={"findings": f"Findings for {outline}"}, next="halt")


@phase(
    name="review_verdict",
    id="template.review_verdict",
    inputs=_required_schema("findings"),
    outputs=_required_schema("verdict"),
)
def review_verdict(ctx: dict[str, Any]) -> StepResult:
    del ctx
    return StepResult(outputs={"verdict": "approved"}, next="halt")


@phase(
    name="revise_outline",
    id="template.revise_outline",
    inputs=_required_schema("working_outline", "first_findings"),
    outputs=_required_schema("outline"),
)
def revise_outline(ctx: dict[str, Any]) -> StepResult:
    outline = ctx["state"].get("working_outline") or "TODO: outline.md"
    findings = ctx["state"].get("first_findings") or "TODO findings"
    revised = f"{outline} revised after {findings}"
    return StepResult(outputs={"outline": revised}, next="halt")


@phase(
    name="parallel_item_review",
    id="template.parallel_item_review",
    inputs=_required_schema("item_id"),
    outputs=_required_schema("item_review"),
)
def parallel_item_review(ctx: dict[str, Any]) -> StepResult:
    item_id = str(ctx["state"].get("item_id", "item"))
    return StepResult(outputs={"item_review": f"reviewed:{item_id}"}, next="halt")


@phase(
    name="publish_artifact",
    id="template.publish_artifact",
    inputs=_required_schema("working_outline"),
    outputs=_required_schema("final_artifact"),
)
def publish_artifact(ctx: dict[str, Any]) -> StepResult:
    outline = ctx["state"].get("working_outline") or "TODO: outline.md"
    return StepResult(outputs={"final_artifact": f"published:{outline}"}, next="halt")


@workflow(
    name="review_pass",
    id="template.review_pass",
    inputs=_required_schema("outline"),
    outputs=_required_schema("findings", "verdict"),
)
def review_pass(ctx: dict[str, Any]) -> Any:
    state = yield review_findings(ctx, id="review-findings", outputs={"findings": "findings"})
    state = yield review_verdict(ctx, id="review-verdict", outputs={"verdict": "verdict"})
    return state


@workflow(
    name="parallel_review_item",
    id="template.parallel_review_item",
    inputs=_required_schema("item_id"),
    outputs=_required_schema("item_review"),
)
def parallel_review_item_flow(ctx: dict[str, Any]) -> Any:
    state = yield parallel_item_review(
        ctx,
        id="parallel-item-review",
        outputs={"item_review": "item_review"},
    )
    return state


def collect_parallel_reviews(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {"parallel_reviews": results}


@decision(name="publish_gate", vocabulary={"publish", "revise"})
def publish_gate(ctx: dict[str, Any]) -> str:
    del ctx
    return "publish"


inputs: dict[str, Any] = {
    "type": "object",
    "required": ["brief", "checks"],
    "properties": {
        "brief": {"type": "string"},
        "checks": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["item_id"],
                "properties": {"item_id": {"type": "string"}},
            },
        },
    },
}

outputs: dict[str, Any] = _required_schema("final_artifact")


@pipeline(
    name="my-pipeline",
    id="template.parent",
    description="Template compositional pipeline with child workflows and path-addressed fan-out.",
    inputs=inputs,
    outputs=outputs,
)
def my_pipeline_native(ctx: dict[str, Any]) -> Any:
    state = yield draft_outline(
        ctx,
        id="draft-outline",
        outputs={"outline": "working_outline"},
    )
    state = yield review_pass(
        ctx,
        id="first-review",
        outputs={"findings": "first_findings", "verdict": "first_verdict"},
    )
    if publish_gate(ctx) == "revise":
        state = yield revise_outline(
            ctx,
            id="revise-outline",
            outputs={"outline": "working_outline"},
        )
        state = yield review_pass(
            ctx,
            id="second-review",
            outputs={"findings": "second_findings", "verdict": "second_verdict"},
        )
    state = yield parallel_map(
        items="checks",
        step=parallel_review_item_flow,
        reducer=collect_parallel_reviews,
        path_template="checks/{item_id}",
        name="parallel_review_items",
        id="parallel-review-items",
    )
    state = yield publish_artifact(
        ctx,
        id="publish-artifact",
        outputs={"final_artifact": "final_artifact"},
    )
    return state


def build_native_program() -> NativeProgram:
    return compile_pipeline(my_pipeline_native)


def resume_from_trace_example(
    trace_dir: str | Path,
    artifact_root: str | Path,
    *,
    target_path: str = "root/second-review/review_verdict",
) -> Any:
    """Debug/test-only example showing path-addressed resume from a child call site."""
    return start_from_trace(build_native_program(), trace_dir, target_path, artifact_root)
