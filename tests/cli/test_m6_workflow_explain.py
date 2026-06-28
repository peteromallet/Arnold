from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold.cli import workflow as workflow_cli


FIXTURE_DIR = Path("tests/fixtures/workflow_authoring")


def test_explain_source_json_has_enriched_step_entries(capsys) -> None:
    source_path = FIXTURE_DIR / "valid_function_linear.py"

    rc = workflow_cli.main(["explain", str(source_path), "--format", "json"])

    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["workflow"]["id"] == "linear-function"
    entries = payload["entries"]
    step_entries = [e for e in entries if e["kind"] == "step"]
    assert len(step_entries) == 3
    assert [entry["id"] for entry in step_entries] == ["plan", "execute", "review"]
    plan = step_entries[0]
    assert plan["id"] == "plan"
    assert plan["component_ref"] == "tests.fixtures.workflow_authoring.components:plan"
    assert "source" in plan
    assert "inputs" in plan
    assert "node_id" in plan


def test_explain_source_human_lists_steps(capsys) -> None:
    source_path = FIXTURE_DIR / "valid_function_linear.py"

    rc = workflow_cli.main(["explain", str(source_path)])

    captured = capsys.readouterr()
    assert rc == 0
    assert "Workflow linear-function" in captured.out
    assert "[step] plan" in captured.out
    assert "[step] execute" in captured.out
    assert "[step] review" in captured.out


def test_explain_source_human_renders_nested_entries(capsys) -> None:
    source_path = FIXTURE_DIR / "m3" / "valid_m3_branch_routes.py"

    rc = workflow_cli.main(["explain", str(source_path)])

    captured = capsys.readouterr()
    assert rc == 0
    assert "2 [branch] branch-on-decision" in captured.out
    assert "  2.1 [branch_arm] branch-on-decision-arm-0" in captured.out
    assert "    2.1.1 [step] execute" in captured.out
    assert "    2.1.2 [step] review-approved" in captured.out
    assert "  2.3 [branch_arm] branch-on-decision-arm-2" in captured.out


def test_explain_source_json_preserves_nested_branch_children(capsys) -> None:
    source_path = FIXTURE_DIR / "m3" / "valid_m3_branch_routes.py"

    rc = workflow_cli.main(["explain", str(source_path), "--format", "json"])

    captured = capsys.readouterr()
    assert rc == 0
    entries = json.loads(captured.out)["entries"]
    branch = next(entry for entry in entries if entry["kind"] == "branch")
    assert branch["decision_output"] == "decision"
    assert [child["kind"] for child in branch["children"]] == [
        "branch_arm",
        "branch_arm",
        "branch_arm",
    ]
    approve_arm, revise_arm, fallback_arm = branch["children"]
    assert approve_arm["condition"]["literal"] == "approve"
    assert [child["id"] for child in approve_arm["children"]] == [
        "execute",
        "review-approved",
    ]
    assert revise_arm["condition"]["literal"] == "revise"
    assert [child["id"] for child in revise_arm["children"]] == [
        "revise-plan",
        "review-revised",
    ]
    assert fallback_arm["condition"] is None
    assert [child["id"] for child in fallback_arm["children"]] == ["review-fallback"]


def test_explain_source_json_preserves_nested_loop_children(capsys) -> None:
    source_path = FIXTURE_DIR / "m3" / "valid_m3_bounded_loop.py"

    rc = workflow_cli.main(["explain", str(source_path), "--format", "json"])

    captured = capsys.readouterr()
    assert rc == 0
    entries = json.loads(captured.out)["entries"]
    loop = next(entry for entry in entries if entry["kind"] == "loop")
    assert loop["max_iterations"] == 3
    assert loop["reentry_id"] == "execute"
    assert [child["id"] for child in loop["children"]] == [
        "execute",
        "review",
        "branch-on-verdict",
        "revise",
    ]


def test_graph_source_dot(capsys) -> None:
    source_path = FIXTURE_DIR / "valid_function_linear.py"

    rc = workflow_cli.main(["graph", str(source_path), "--format", "dot"])

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.startswith("digraph workflow {")
    assert '"plan" -> "execute"' in captured.out
    assert '"execute" -> "review"' in captured.out


def test_graph_source_dot_annotates_branch_condition_literals(capsys) -> None:
    source_path = FIXTURE_DIR / "m3" / "valid_m3_branch_routes.py"

    rc = workflow_cli.main(["graph", str(source_path), "--format", "dot"])

    captured = capsys.readouterr()
    assert rc == 0
    assert '"route" -> "execute" [label="approve (route.decision.eq.approve)"]' in (
        captured.out
    )
    assert '"route" -> "review-fallback" [label="else (route.decision.else)"]' in (
        captured.out
    )


def test_graph_source_dot_reports_check_errors_before_compile(capsys) -> None:
    source_path = FIXTURE_DIR / "invalid_parallel_fanout.py"

    rc = workflow_cli.main(["graph", str(source_path), "--format", "dot"])

    captured = capsys.readouterr()
    assert rc == 1
    assert "AWF002_UNSUPPORTED_SYNTAX" in captured.err
    assert "graph failed" not in captured.err


def test_graph_source_mermaid(capsys) -> None:
    source_path = FIXTURE_DIR / "valid_function_linear.py"

    rc = workflow_cli.main(["graph", str(source_path), "--format", "mermaid"])

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.startswith("flowchart TD")
    assert "plan -->|default| execute" in captured.out
    assert "execute -->|default| review" in captured.out


def test_graph_source_mermaid_groups_branch_arms_and_loops(capsys) -> None:
    branch_path = FIXTURE_DIR / "m3" / "valid_m3_branch_routes.py"
    loop_path = FIXTURE_DIR / "m3" / "valid_m3_bounded_loop.py"

    branch_rc = workflow_cli.main(["graph", str(branch_path), "--format", "mermaid"])
    branch_captured = capsys.readouterr()
    assert branch_rc == 0
    assert 'subgraph branch_on_decision["branch: branch-on-decision"]' in (
        branch_captured.out
    )
    assert 'subgraph branch_on_decision_arm_0["approve"]' in branch_captured.out
    assert 'subgraph branch_on_decision_arm_2["else"]' in branch_captured.out

    loop_rc = workflow_cli.main(["graph", str(loop_path), "--format", "mermaid"])
    loop_captured = capsys.readouterr()
    assert loop_rc == 0
    assert 'subgraph execute["loop: execute"]' in loop_captured.out
    assert 'execute["execute"]' in loop_captured.out
    assert "revise -->|reentry:loop:bounded_review_loop:reentry:execute| execute" in (
        loop_captured.out
    )


def test_graph_source_json(capsys) -> None:
    source_path = FIXTURE_DIR / "valid_function_linear.py"

    rc = workflow_cli.main(["graph", str(source_path), "--format", "json"])

    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert len(payload["nodes"]) == 3
    assert len(payload["edges"]) == 2
    node_ids = {n["id"] for n in payload["nodes"]}
    assert node_ids == {"plan", "execute", "review"}
    topology = payload["source_topology"]
    assert set(topology["nodes"]) == node_ids
    assert topology["nodes"]["plan"]["component_ref"] == (
        "tests.fixtures.workflow_authoring.components:plan"
    )
    assert topology["nodes"]["plan"]["nesting_depth"] == 0
    assert topology["branches"] == []
    assert topology["loops"] == []


def test_graph_source_json_includes_branch_and_loop_boundaries(capsys) -> None:
    branch_path = FIXTURE_DIR / "m3" / "valid_m3_branch_routes.py"
    loop_path = FIXTURE_DIR / "m3" / "valid_m3_bounded_loop.py"

    branch_rc = workflow_cli.main(["graph", str(branch_path), "--format", "json"])
    branch_captured = capsys.readouterr()
    assert branch_rc == 0
    branch_topology = json.loads(branch_captured.out)["source_topology"]
    assert branch_topology["branches"]
    branch = branch_topology["branches"][0]
    assert branch["node_ids"] == [
        "execute",
        "review-approved",
        "revise-plan",
        "review-revised",
        "review-fallback",
    ]
    assert [arm["node_ids"] for arm in branch["arms"]] == [
        ["execute", "review-approved"],
        ["revise-plan", "review-revised"],
        ["review-fallback"],
    ]
    assert [arm["id"] for arm in branch["arms"]] == [
        "branch-on-decision-arm-0",
        "branch-on-decision-arm-1",
        "branch-on-decision-arm-2",
    ]
    assert [arm["nesting_depth"] for arm in branch["arms"]] == [1, 1, 1]
    branch_nodes = json.loads(branch_captured.out)["nodes"]
    execute = next(node for node in branch_nodes if node["id"] == "execute")
    assert execute["nesting_depth"] == 1
    assert execute["source_role"] == "step"
    assert execute["branch_id"] == "branch-on-decision"
    assert execute["branch_arm_id"] == "branch-on-decision-arm-0"
    assert execute["branch_decision_output"] == "decision"
    assert execute["branch_condition_literal"] == "approve"

    loop_rc = workflow_cli.main(["graph", str(loop_path), "--format", "json"])
    loop_captured = capsys.readouterr()
    assert loop_rc == 0
    loop_payload = json.loads(loop_captured.out)
    loop_topology = loop_payload["source_topology"]
    assert loop_topology["loops"]
    loop = loop_topology["loops"][0]
    assert loop["body_node_ids"] == ["execute", "review", "revise"]
    assert loop["entry_node_id"] == "execute"
    assert loop["exit_node_ids"] == []
    assert loop["exit_edges"] == []
    loop_execute = next(node for node in loop_payload["nodes"] if node["id"] == "execute")
    assert loop_execute["nesting_depth"] == 1
    assert loop_execute["source_role"] == "step"
    assert loop_execute["loop_id"] == "execute"
    assert loop_execute["loop_reentry_id"] == "execute"


@pytest.mark.parametrize(
    ("source_path", "workflow_id", "step_ids"),
    [
        (
            Path("examples/workflow_authoring/hello/workflow.py"),
            "hello-world",
            ["greet", "respond"],
        ),
        (
            Path("examples/workflow_authoring/shipped/jokes/workflow.py"),
            "shipped-jokes",
            ["draft", "tighten", "emit"],
        ),
        (
            Path("examples/workflow_authoring/shipped/creative/workflow.py"),
            "shipped-creative",
            [
                "prep",
                "execute_creative",
                "critique_creative",
                "revise_creative",
                "finalize",
            ],
        ),
        (
            Path("examples/workflow_authoring/shipped/live_supervisor/workflow.py"),
            "shipped-live-supervisor",
            ["classify", "diagnose", "repair_decision", "recheck_emit"],
        ),
    ],
)
def test_shipped_example_checks_compiles_and_explains(
    capsys,
    tmp_path: Path,
    source_path: Path,
    workflow_id: str,
    step_ids: list[str],
) -> None:
    out_path = tmp_path / "manifest.json"

    check_rc = workflow_cli.main(["check", str(source_path)])
    check_captured = capsys.readouterr()
    assert check_rc == 0
    assert "ok" in check_captured.out.lower()

    rc = workflow_cli.main(["compile", str(source_path), "--out", str(out_path)])

    captured = capsys.readouterr()
    assert rc == 0
    assert out_path.exists()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["id"] == workflow_id
    assert payload["version"] == "1.0"
    assert {node["id"] for node in payload["nodes"]} == set(step_ids)

    explain_rc = workflow_cli.main(["explain", str(source_path), "--format", "json"])
    explain_captured = capsys.readouterr()
    assert explain_rc == 0
    explain_payload = json.loads(explain_captured.out)
    assert explain_payload["workflow"]["id"] == workflow_id
    assert [entry["id"] for entry in explain_payload["entries"]] == step_ids


@pytest.mark.parametrize(
    (
        "source_path",
        "code",
        "start_line",
        "start_column",
        "end_line",
        "end_column",
    ),
    [
        (
            FIXTURE_DIR / "invalid_parallel_fanout.py",
            "AWF002_UNSUPPORTED_SYNTAX",
            10,
            5,
            11,
            42,
        ),
        (
            FIXTURE_DIR / "invalid_dynamic_component_construction.py",
            "AWF002_UNSUPPORTED_SYNTAX",
            9,
            5,
            12,
            33,
        ),
        (
            FIXTURE_DIR / "invalid_nested_subflow.py",
            "AWF015_UNSUPPORTED_SUBFLOW_REFERENCE",
            11,
            40,
            11,
            62,
        ),
    ],
)
def test_blocked_authoring_patterns_fail_with_stable_diagnostics(
    capsys,
    source_path: Path,
    code: str,
    start_line: int,
    start_column: int,
    end_line: int,
    end_column: int,
) -> None:
    rc = workflow_cli.main(["check", str(source_path), "--format", "json"])

    captured = capsys.readouterr()
    assert rc == 1
    payload = json.loads(captured.out)
    assert payload["ok"] is False
    assert payload["source"] == {"kind": "python", "path": str(source_path)}
    assert len(payload["diagnostics"]) == 1
    diagnostic = payload["diagnostics"][0]
    assert diagnostic["code"] == code
    assert diagnostic["severity"] == "error"
    assert diagnostic["source_span"] == {
        "path": str(source_path),
        "start_line": start_line,
        "start_column": start_column,
        "end_line": end_line,
        "end_column": end_column,
    }


def test_negative_unsupported_control_flow_rejected(capsys) -> None:
    source_path = FIXTURE_DIR / "invalid_unsupported_control_flow.py"

    rc = workflow_cli.main(["check", str(source_path)])

    captured = capsys.readouterr()
    assert rc == 1
    assert "AWF002_UNSUPPORTED_SYNTAX" in captured.out
    assert "for section in brief.split():" in captured.out
