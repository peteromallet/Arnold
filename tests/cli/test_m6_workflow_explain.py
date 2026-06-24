from __future__ import annotations

import json
from pathlib import Path

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


def test_graph_source_dot(capsys) -> None:
    source_path = FIXTURE_DIR / "valid_function_linear.py"

    rc = workflow_cli.main(["graph", str(source_path), "--format", "dot"])

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.startswith("digraph workflow {")
    assert '"plan" -> "execute"' in captured.out
    assert '"execute" -> "review"' in captured.out


def test_graph_source_mermaid(capsys) -> None:
    source_path = FIXTURE_DIR / "valid_function_linear.py"

    rc = workflow_cli.main(["graph", str(source_path), "--format", "mermaid"])

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.startswith("flowchart TD")
    assert "plan -->|default| execute" in captured.out
    assert "execute -->|default| review" in captured.out


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


def test_shipped_example_compiles(capsys, tmp_path: Path) -> None:
    source_path = Path("examples/workflow_authoring/hello/workflow.py")
    out_path = tmp_path / "manifest.json"

    rc = workflow_cli.main(["compile", str(source_path), "--out", str(out_path)])

    captured = capsys.readouterr()
    assert rc == 0
    assert out_path.exists()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["id"] == "hello-world"
    assert payload["version"] == "1.0"
    assert len(payload["nodes"]) == 2


def test_negative_unsupported_control_flow_rejected(capsys) -> None:
    source_path = FIXTURE_DIR / "invalid_unsupported_control_flow.py"

    rc = workflow_cli.main(["check", str(source_path)])

    captured = capsys.readouterr()
    assert rc == 1
    assert "AWF002_UNSUPPORTED_SYNTAX" in captured.out
    assert "for section in brief.split():" in captured.out
