from __future__ import annotations

import arnold.workflow as workflow
from arnold.workflow import (
    Capability,
    Input,
    Output,
    Pipeline,
    Route,
    SourceSpan,
    Step,
    SuspensionRoute,
    WorkflowPolicy,
    compile_pipeline,
    dry_run,
    inspect_manifest,
    to_dot,
    to_yaml,
)


def _sample_pipeline() -> Pipeline:
    return Pipeline(
        id="planning",
        version="authoring-v1",
        steps=[
            Step(
                id="plan",
                kind="agent",
                outputs=[Output("draft")],
                capabilities=[Capability("agent:planner")],
                source_span=SourceSpan("pipeline.py", 10),
            ),
            Step(
                id="review",
                kind="agent",
                inputs=[Input("draft", value_ref="plan.draft"), Input("criteria")],
                policy=WorkflowPolicy(
                    suspension_routes=(SuspensionRoute("operator", reentry_id="resume-review"),)
                ),
            ),
        ],
        routes=[Route(id="plan-review", source="plan", target="review", label="review")],
    )


def test_inspect_manifest_exposes_stable_fields() -> None:
    manifest = compile_pipeline(_sample_pipeline())
    view = inspect_manifest(manifest)

    assert view["node_ids"] == ("plan", "review")
    assert "node:plan" in view["refs"]["nodes"]
    assert "edge:plan->review:review" in view["refs"]["edges"]
    assert view["dependencies"]["review"][0].startswith("value:review.draft")
    assert view["unresolved_inputs"] == {"review": ("criteria",)}
    assert view["hash_inputs"]["topology_hash"] == manifest.topology_hash
    assert view["hash_inputs"]["manifest_hash"] == manifest.manifest_hash
    assert view["control_routes"][0]["source"] == "plan"
    assert view["suspension_points"][0]["reentry_id"] == "resume-review"
    assert view["topology_summary"]["node_count"] == 2
    assert view["topology_summary"]["edge_count"] == 1
    assert "plan" in view["topology_summary"]["entry_nodes"]
    assert "review" in view["topology_summary"]["exit_nodes"]


def test_inspect_manifest_reports_manifest_level_capabilities() -> None:
    manifest = compile_pipeline(
        Pipeline(
            id="cap",
            version="v1",
            steps=[Step(id="plan", kind="agent")],
            capabilities=[Capability("agent:planner", route="fast")],
        )
    )
    view = inspect_manifest(manifest)

    assert view["capabilities"]["manifest"][0]["capability_id"] == "agent:planner"


def test_dry_run_reports_routes_and_unresolved_inputs_without_execution() -> None:
    manifest = compile_pipeline(_sample_pipeline())
    report = dry_run(manifest)

    assert report["id"] == "planning"
    assert report["node_count"] == 2
    assert report["edge_count"] == 1
    assert report["possible_routes"][0]["source"] == "plan"
    assert report["unresolved_inputs"] == {"review": ("criteria",)}
    assert report["suspension_point_count"] == 1


def test_dot_helper_is_diagnostic_and_contains_nodes_and_edges() -> None:
    manifest = compile_pipeline(_sample_pipeline())
    dot = to_dot(manifest)

    assert dot.startswith("digraph workflow {")
    assert '"plan"' in dot
    assert '"review"' in dot
    assert '"plan" -> "review"' in dot


def test_yaml_helper_serializes_inspect_data() -> None:
    manifest = compile_pipeline(_sample_pipeline())
    yaml_text = to_yaml(inspect_manifest(manifest))

    assert "node_ids" in yaml_text
    assert "plan" in yaml_text


def test_inspect_manifest_does_not_expose_source_spans_as_stable() -> None:
    manifest = compile_pipeline(_sample_pipeline())
    view = inspect_manifest(manifest)

    assert "source_spans" not in view
    # Source spans remain reachable through the manifest nodes for diagnostics.
    assert manifest.nodes[0].source_span is not None


def test_dry_run_reports_topology_summary() -> None:
    manifest = compile_pipeline(_sample_pipeline())
    report = dry_run(manifest)

    assert report["topology_summary"]["node_count"] == 2
    assert report["topology_summary"]["edge_count"] == 1
    assert "plan" in report["topology_summary"]["entry_nodes"]
    assert "review" in report["topology_summary"]["exit_nodes"]


def test_inspect_and_dry_run_are_exposed_from_workflow_namespace() -> None:
    assert hasattr(workflow, "inspect_manifest")
    assert hasattr(workflow, "dry_run")
    assert hasattr(workflow, "to_dot")
    assert hasattr(workflow, "to_yaml")


def test_inspect_does_not_execute_hooks_or_steps() -> None:
    manifest = compile_pipeline(_sample_pipeline())

    # The inspect helpers must not mutate state or call user code.  Calling them
    # repeatedly yields identical stable output.
    first = inspect_manifest(manifest)
    second = inspect_manifest(manifest)
    assert first == second
    assert dry_run(manifest) == dry_run(manifest)
