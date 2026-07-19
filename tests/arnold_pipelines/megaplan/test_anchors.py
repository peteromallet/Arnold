from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.anchors import (
    AnchorCaptureRequest,
    anchor_show_payload,
    attach_anchor_documents,
    format_anchor_show_text,
    render_anchor_block,
    render_anchor_context,
)
from arnold_pipelines.megaplan.chain.spec import (
    ChainSpec,
    validate_anchor_paths,
    validate_anchor_requirement,
    validate_required_anchor,
    warn_undeclared_north_star,
)
from arnold_pipelines.megaplan.cli import build_parser
from arnold_pipelines.megaplan.types import CliError


def _state(tmp_path: Path) -> dict:
    return {
        "config": {
            "plan": "anchor-plan",
            "plan_name": "anchor-plan",
            "project_dir": str(tmp_path),
            "mode": "code",
        },
        "meta": {},
        "current_state": "initialized",
    }


def _attach_anchor(plan_dir: Path, tmp_path: Path, *, text: str = "# North Star\n\nKeep the final contract stable.\n") -> dict:
    source = tmp_path / "NORTHSTAR.md"
    source.write_text(text, encoding="utf-8")
    state = _state(tmp_path)
    attach_anchor_documents(
        plan_dir=plan_dir,
        state=state,
        documents=[
            AnchorCaptureRequest(
                anchor_type="north_star",
                scope="plan",
                source_path=source,
                source_kind="cli",
            )
        ],
        project_root=tmp_path,
    )
    return state


def test_chain_schema_accepts_and_rejects_anchor_shapes(tmp_path: Path) -> None:
    spec = ChainSpec.from_dict(
        {
            "anchors": {"north_star": "NORTHSTAR.md"},
            "driver": {"require_anchor": True, "missing_anchor_ack": "not used because anchor is present"},
            "milestones": [
                {
                    "label": "m1",
                    "idea": "m1.md",
                    "anchors": {"north_star": "m1-northstar.md"},
                }
            ],
        }
    )

    assert spec.anchors.north_star == "NORTHSTAR.md"
    assert spec.require_anchor is True
    assert spec.missing_anchor_ack == "not used because anchor is present"
    assert spec.milestones[0].anchors.north_star == "m1-northstar.md"

    with pytest.raises(CliError, match="only supports `north_star`"):
        ChainSpec.from_dict({"anchors": {"vision": "x.md"}, "milestones": []})

    with pytest.raises(CliError, match="non-empty string"):
        ChainSpec.from_dict({"anchors": {"north_star": ""}, "milestones": []})


def test_anchor_path_validation_and_required_warning(tmp_path: Path) -> None:
    chain_path = tmp_path / "chain.yaml"
    chain_path.write_text("anchors:\n  north_star: NORTHSTAR.md\nmilestones: []\n", encoding="utf-8")
    (tmp_path / "NORTHSTAR.md").write_text("# Epic\n", encoding="utf-8")
    spec = ChainSpec.from_dict({"anchors": {"north_star": "NORTHSTAR.md"}, "milestones": []})

    validate_anchor_paths(spec, chain_path)
    validate_required_anchor(spec)

    missing = ChainSpec.from_dict({"milestones": []})
    assert missing.require_anchor is True
    with pytest.raises(CliError, match="requires a North Star"):
        validate_required_anchor(missing)

    assert warn_undeclared_north_star(missing, chain_path)


def test_chain_anchor_requirement_defaults_and_opt_out_ack(tmp_path: Path) -> None:
    chain_path = tmp_path / "chain.yaml"
    chain_path.write_text("milestones: []\n", encoding="utf-8")
    spec = ChainSpec.from_dict({"milestones": []})

    with pytest.raises(CliError, match="requires a North Star"):
        validate_anchor_requirement(spec, chain_path)

    with pytest.raises(CliError, match="missing_anchor_ack"):
        validate_anchor_requirement(spec, chain_path, require_anchor_override=False)

    resolved = validate_anchor_requirement(
        spec,
        chain_path,
        require_anchor_override=False,
        missing_anchor_ack_override="Mechanical cleanup chain.",
    )
    assert resolved.require_anchor is False
    assert "Mechanical cleanup chain." in (resolved.warning or "")

    (tmp_path / "NORTHSTAR.md").write_text("# Undeclared\n", encoding="utf-8")
    resolved_with_warning = validate_anchor_requirement(
        spec,
        chain_path,
        require_anchor_override=False,
        missing_anchor_ack_override="No durable destination.",
    )
    assert "NORTHSTAR.md exists next to" in (resolved_with_warning.warning or "")


def test_capture_load_show_and_truncation(tmp_path: Path) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "anchor-plan"
    plan_dir.mkdir(parents=True)
    state = _attach_anchor(plan_dir, tmp_path, text="# North Star\n\n" + ("A" * 140))

    artifact = plan_dir / "anchors" / "north_star" / "plan.md"
    combined = plan_dir / "anchors" / "north_star" / "combined.md"
    assert artifact.read_text(encoding="utf-8").startswith("# North Star")
    assert combined.exists()
    events = plan_dir / "events.ndjson"
    assert events.exists()
    assert any(
        json.loads(line).get("kind") == "anchor_captured"
        for line in events.read_text(encoding="utf-8").splitlines()
    )

    block = render_anchor_block(state, plan_dir, audience="plan", max_chars_per_document=25)
    assert "## Anchor Context: North Star" in block
    assert "truncated from" in block
    assert "Build a plan that advances" in block

    payload = anchor_show_payload(state, plan_dir)
    assert payload["present"] is True
    assert payload["health"] == "ok"
    shown = format_anchor_show_text("anchor-plan", payload)
    assert "--- Combined North Star ---" in shown
    assert "North Star" in shown

    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    from arnold_pipelines.megaplan.handlers.anchors import handle_anchors

    handler_output = handle_anchors(
        tmp_path,
        argparse.Namespace(anchors_action="show", plan="anchor-plan", anchor_type="north_star", as_json=False, json=False),
    )
    assert isinstance(handler_output, str)
    assert "North Star" in handler_output


def test_anchor_context_render_modes(tmp_path: Path) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "anchor-plan"
    plan_dir.mkdir(parents=True)
    state = _attach_anchor(plan_dir, tmp_path)

    full = render_anchor_context(state, plan_dir, audience="plan")
    check = render_anchor_context(state, plan_dir, audience="review")

    assert "## Anchor Context: North Star" in full
    assert "## Anchor Check: North Star" in check
    assert "Do not restate the North Star" in check
    assert "Keep the final contract stable" not in check
    assert render_anchor_context(state, plan_dir, audience="execute") == ""
    assert render_anchor_context(state, plan_dir, audience="execute-batch") == ""
    assert render_anchor_context(state, plan_dir, audience="feedback") == ""


def test_epic_and_milestone_anchor_composition(tmp_path: Path) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "milestone"
    plan_dir.mkdir(parents=True)
    epic = tmp_path / "NORTHSTAR.md"
    milestone = tmp_path / "m1.md"
    epic.write_text("# Epic North Star\n\nPreserve the migration destination.\n", encoding="utf-8")
    milestone.write_text("# Milestone North Star\n\nKeep the API bridge compatible.\n", encoding="utf-8")
    state = _state(tmp_path)

    attach_anchor_documents(
        plan_dir=plan_dir,
        state=state,
        documents=[
            AnchorCaptureRequest("north_star", "epic", epic, "chain"),
            AnchorCaptureRequest("north_star", "plan", milestone, "milestone", label="m1"),
        ],
        project_root=tmp_path,
    )

    combined = (plan_dir / "anchors" / "north_star" / "combined.md").read_text(encoding="utf-8")
    assert combined.index("Epic North Star") < combined.index("Milestone North Star")
    block = render_anchor_block(state, plan_dir, audience="review")
    assert "Epic North Star" in block
    assert "Milestone North Star" in block
    assert "Scope map:" in block
    assert "overall chain/epic objective" in block
    assert "Plan North Star (current milestone m1): Milestone North Star" in block
    assert "Current milestone: `m1`" in block
    assert "Review against the issue" in block

    check_block = render_anchor_context(state, plan_dir, audience="review")
    assert "## Anchor Check: North Star" in check_block
    assert "Epic North Star (overall chain/epic objective): `anchors/north_star/epic.md`" in check_block
    assert "Sprint/Milestone North Star (current milestone m1): `anchors/north_star/plan.md`" in check_block
    assert "Do not restate the North Star" in check_block


def test_prompt_injection_standard_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from arnold_pipelines.megaplan import prompts

    plan_dir = tmp_path / ".megaplan" / "plans" / "anchor-plan"
    plan_dir.mkdir(parents=True)
    state = _attach_anchor(plan_dir, tmp_path)

    monkeypatch.setitem(
        prompts._AGENT_REGISTRY,
        "codex",
        ({"plan": lambda state, plan_dir, contract_context=None: "PLAN BODY"}, "Codex"),
    )

    prompt = prompts.create_prompt("codex", "plan", state, plan_dir)
    assert prompt.startswith("You are already running inside the megaplan harness")
    assert "## Anchor Context: North Star" in prompt
    assert prompt.index("## Anchor Context: North Star") < prompt.index("PLAN BODY")


def test_feedback_gets_no_anchor_context(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from arnold_pipelines.megaplan import prompts

    plan_dir = tmp_path / ".megaplan" / "plans" / "anchor-plan"
    plan_dir.mkdir(parents=True)
    state = _attach_anchor(plan_dir, tmp_path)

    monkeypatch.setitem(
        prompts._AGENT_REGISTRY,
        "codex",
        ({"feedback": lambda state, plan_dir: "FEEDBACK BODY"}, "Codex"),
    )

    prompt = prompts.create_prompt("codex", "feedback", state, plan_dir)
    assert "FEEDBACK BODY" in prompt
    assert "Anchor Context" not in prompt
    assert "Anchor Check" not in prompt


def test_execute_prompt_gets_no_anchor_context(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from arnold_pipelines.megaplan import prompts

    plan_dir = tmp_path / ".megaplan" / "plans" / "anchor-plan"
    plan_dir.mkdir(parents=True)
    state = _attach_anchor(plan_dir, tmp_path)

    monkeypatch.setitem(
        prompts._AGENT_REGISTRY,
        "codex",
        ({"execute": lambda state, plan_dir, root=None: "EXECUTE BODY"}, "Codex"),
    )

    prompt = prompts.create_prompt("codex", "execute", state, plan_dir, root=tmp_path)
    assert "EXECUTE BODY" in prompt
    assert "## Anchor Check: North Star" not in prompt
    assert "## Anchor Context: North Star" not in prompt


def test_execute_batch_prompt_gets_no_anchor_context(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan import prompts

    plan_dir = tmp_path / ".megaplan" / "plans" / "anchor-plan"
    plan_dir.mkdir(parents=True)
    state = _attach_anchor(plan_dir, tmp_path)
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "T1",
                        "description": "Make the smallest possible change.",
                        "files": [],
                        "commands": [],
                    }
                ],
                "sense_checks": [{"id": "SC1", "task_id": "T1", "check": "Verify it."}],
            }
        ),
        encoding="utf-8",
    )

    prompt = prompts._execute_batch_prompt(state, plan_dir, ["T1"], root=tmp_path)
    assert "## Anchor Check: North Star" not in prompt
    assert "## Anchor Context: North Star" not in prompt
    assert "Execute only the actionable tasks in this batch" in prompt


def test_execute_batch_inner_builder_does_not_inject_anchor(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan.prompts.execute import _execute_batch_prompt

    plan_dir = tmp_path / ".megaplan" / "plans" / "anchor-plan"
    plan_dir.mkdir(parents=True)
    state = _attach_anchor(plan_dir, tmp_path)
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "T1",
                        "description": "Make the smallest possible change.",
                        "files": [],
                        "commands": [],
                    }
                ],
                "sense_checks": [{"id": "SC1", "task_id": "T1", "check": "Verify it."}],
            }
        ),
        encoding="utf-8",
    )

    prompt = _execute_batch_prompt(state, plan_dir, ["T1"], root=tmp_path)
    assert "Anchor Context" not in prompt
    assert "Anchor Check" not in prompt


def test_parser_exposes_north_star_and_anchor_show() -> None:
    parser = build_parser()
    init_args = parser.parse_args(["init", "--north-star", "NORTHSTAR.md", "idea"])
    assert init_args.north_star == "NORTHSTAR.md"
    init_without_anchor = parser.parse_args(["init", "idea"])
    assert init_without_anchor.north_star is None

    show_args = parser.parse_args(["anchors", "show", "--plan", "anchor-plan", "--json"])
    assert show_args.command == "anchors"
    assert show_args.anchors_action == "show"
    assert show_args.plan == "anchor-plan"
    assert show_args.as_json is True

    chain_args = parser.parse_args(["chain", "start", "--spec", "chain.yaml", "--require-anchor"])
    assert chain_args.require_anchor is True
    no_anchor_args = parser.parse_args(
        ["chain", "start", "--spec", "chain.yaml", "--no-require-anchor", "--missing-anchor-ack", "Mechanical chain"]
    )
    assert no_anchor_args.require_anchor is False
    assert no_anchor_args.missing_anchor_ack == "Mechanical chain"

    epic_chain_args = parser.parse_args(["epic-chain", "start", "--spec", "epic-chain.yaml", "--one"])
    assert epic_chain_args.command == "epic-chain"
    assert epic_chain_args.epic_chain_action == "start"
    assert epic_chain_args.one is True


def test_chain_status_enforces_anchor_requirement_like_start(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from arnold_pipelines.megaplan.chain import run_chain_cli

    idea = tmp_path / "m1.md"
    idea.write_text("# M1\n", encoding="utf-8")
    chain_path = tmp_path / "chain.yaml"
    chain_path.write_text(
        "base_branch: main\n"
        "milestones:\n"
        "  - label: m1\n"
        "    idea: m1.md\n",
        encoding="utf-8",
    )
    args = build_parser().parse_args(["chain", "status", "--spec", str(chain_path)])

    rc = run_chain_cli(tmp_path, args)

    captured = capsys.readouterr()
    assert rc != 0
    assert '"error": "invalid_spec"' in captured.out
    assert "requires a North Star" in captured.out


def test_anchor_docs_and_templates_stay_discoverable() -> None:
    root = Path(__file__).resolve().parents[3]
    paths = [
        root / "docs" / "anchors.md",
        root / "arnold_pipelines" / "megaplan" / "data" / "instructions.md",
        root / "arnold_pipelines" / "megaplan" / "data" / "prep_skill.md",
        root / "arnold_pipelines" / "megaplan" / "data" / "epic_skill.md",
        root / "arnold_pipelines" / "megaplan" / "cloud" / "templates" / "chain.yaml.example",
    ]
    joined = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    for needle in [
        "--north-star",
        "anchors.north_star",
        "NORTHSTAR.md",
        "megaplan anchors show",
        "--no-require-anchor",
        "--missing-anchor-ack",
    ]:
        assert needle in joined
