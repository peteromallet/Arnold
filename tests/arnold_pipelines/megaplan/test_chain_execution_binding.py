from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

from arnold_pipelines.megaplan import chain as chain_module
from arnold_pipelines.megaplan.chain.execution_binding import (
    active_execution_identity,
    bind_execution_identity,
    execution_binding_report,
    rebind_execution_identity,
)
from arnold_pipelines.megaplan.chain.spec import (
    ChainState,
    load_chain_state,
    load_spec,
    save_chain_state,
)
from arnold_pipelines.megaplan.types import CliError


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _write_chain(root: Path, labels: tuple[str, ...]) -> Path:
    initiative = root / ".megaplan" / "initiatives" / "demo"
    briefs = initiative / "briefs"
    briefs.mkdir(parents=True, exist_ok=True)
    (initiative / "NORTHSTAR.md").write_text("# Durable destination\n", encoding="utf-8")
    milestones = []
    for label in labels:
        brief = briefs / f"{label}.md"
        if not brief.exists():
            brief.write_text(f"# {label}\n", encoding="utf-8")
        milestones.append(
            {
                "label": label,
                "idea": f".megaplan/initiatives/demo/briefs/{label}.md",
            }
        )
    payload = {
        "anchors": {"north_star": "NORTHSTAR.md"},
        "milestones": milestones,
        "driver": {
            "execution_binding": "required",
            "initiative_path": ".megaplan/initiatives/demo",
            "intended_initiative_revision": "UNSET_REQUIRED_BEFORE_LAUNCH",
            "require_editable_runtime_match": False,
        },
    }
    spec_path = initiative / "chain.yaml"
    spec_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return spec_path


def _pinned_chain(tmp_path: Path, labels: tuple[str, ...] = ("c1", "c2", "c3")) -> Path:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "tests@example.com")
    _git(tmp_path, "config", "user.name", "Tests")
    spec_path = _write_chain(tmp_path, labels)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "initiative revision")
    revision = _git(tmp_path, "rev-parse", "HEAD")
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    raw["driver"]["intended_initiative_revision"] = revision
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return spec_path


def _bound_state(spec_path: Path) -> ChainState:
    state = ChainState()
    report = bind_execution_identity(spec_path, state)
    assert report["status"] == "match"
    save_chain_state(spec_path, state)
    return state


def _replace_and_repin(spec_path: Path, labels: tuple[str, ...]) -> None:
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    raw["milestones"] = []
    for label in labels:
        brief = spec_path.parent / "briefs" / f"{label}.md"
        if not brief.exists():
            brief.write_text(f"# {label}\n", encoding="utf-8")
        raw["milestones"].append(
            {
                "label": label,
                "idea": f".megaplan/initiatives/demo/briefs/{label}.md",
            }
        )
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    root = spec_path.parents[3]
    _git(root, "add", ".")
    _git(root, "commit", "-m", "replace initiative revision")
    raw["driver"]["intended_initiative_revision"] = _git(root, "rev-parse", "HEAD")
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")


def test_binding_records_spec_sequence_anchor_briefs_revision_and_runtime(tmp_path: Path) -> None:
    spec_path = _pinned_chain(tmp_path)

    state = _bound_state(spec_path)
    identity = state.metadata["execution_binding"]["launched_identity"]

    assert identity["ready"] is True
    assert [item["label"] for item in identity["milestone_sequence"]] == ["c1", "c2", "c3"]
    assert [item["kind"] for item in identity["assets"]] == [
        "north_star",
        "milestone_brief:0",
        "milestone_brief:1",
        "milestone_brief:2",
    ]
    assert all(item["sha256"] for item in identity["assets"])
    assert len(identity["chain_spec_sha256"]) == 64
    assert len(identity["bundle_sha256"]) == 64
    assert len(identity["runtime"]["source_revision"]) == 40
    assert identity["revision_verification"]["ok"] is True


def test_c1_bound_to_old_successors_cannot_adopt_corrective_sequence(tmp_path: Path) -> None:
    spec_path = _pinned_chain(tmp_path, ("c1", "s2", "s3", "s4"))
    state = _bound_state(spec_path)
    state.current_milestone_index = 1
    state.current_plan_name = "c1-plan"
    state.completed = [{"label": "c1", "plan": "c1-plan", "status": "done"}]
    save_chain_state(spec_path, state)

    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    raw["milestones"] = [
        {
            "label": label,
            "idea": f".megaplan/initiatives/demo/briefs/{label}.md",
        }
        for label in ("c1", "c2", "c3", "c4", "c5", "c6")
    ]
    for label in ("c2", "c3", "c4", "c5", "c6"):
        (spec_path.parent / "briefs" / f"{label}.md").write_text(
            f"# {label}\n", encoding="utf-8"
        )
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    with pytest.raises(CliError, match="immutable chain execution binding is drift"):
        load_chain_state(spec_path)

    unchanged = load_chain_state(spec_path, verify_execution_binding=False)
    assert unchanged.current_milestone_index == 1
    assert unchanged.current_plan_name == "c1-plan"
    assert [item["label"] for item in unchanged.completed] == ["c1"]


def test_later_brief_change_blocks_load_resume_and_reconcile(tmp_path: Path) -> None:
    spec_path = _pinned_chain(tmp_path)
    state = _bound_state(spec_path)
    state.current_milestone_index = 0
    state.current_plan_name = "c1-plan"
    save_chain_state(spec_path, state)
    (spec_path.parent / "briefs" / "c3.md").write_text(
        "# silently narrowed successor\n", encoding="utf-8"
    )

    with pytest.raises(CliError, match="chain state load/resume refused"):
        load_chain_state(spec_path)
    with pytest.raises(CliError, match="chain reconciliation refused"):
        chain_module._reconcile_chain_from_ground_truth(
            tmp_path,
            spec_path,
            load_spec(spec_path),
            state,
            writer=lambda _message: None,
            push_enabled=False,
        )


def test_progressed_strict_state_without_launch_binding_fails_closed(tmp_path: Path) -> None:
    spec_path = _pinned_chain(tmp_path)
    save_chain_state(
        spec_path,
        ChainState(current_milestone_index=0, current_plan_name="legacy-plan"),
    )

    with pytest.raises(CliError, match="immutable chain execution binding is missing"):
        load_chain_state(spec_path)


def test_status_exposes_expected_and_active_identity_during_drift(tmp_path: Path) -> None:
    spec_path = _pinned_chain(tmp_path)
    _bound_state(spec_path)
    (spec_path.parent / "NORTHSTAR.md").write_text("# Different destination\n", encoding="utf-8")

    state = load_chain_state(spec_path, verify_execution_binding=False)
    summary = chain_module.format_chain_status(
        load_spec(spec_path),
        state,
        spec_path=spec_path,
    )
    binding = summary["execution_binding"]

    assert binding["status"] == "drift"
    assert binding["expected"]["bundle_sha256"] != binding["active"]["bundle_sha256"]
    assert "assets" in binding["drift_fields"]


def test_runtime_revision_is_evidence_but_not_canonical_source_drift(tmp_path: Path, monkeypatch) -> None:
    spec_path = _pinned_chain(tmp_path)
    _bound_state(spec_path)
    original = active_execution_identity(spec_path)["runtime"]

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.execution_binding.runtime_provenance",
        lambda: {
            "import_root": original["import_root"],
            "source_revision": "f" * 40,
            "editable_root": "",
        },
    )

    state = load_chain_state(spec_path, verify_execution_binding=False)
    report = execution_binding_report(spec_path, state)
    assert report["status"] == "match"
    assert report["active"]["runtime"]["source_revision"] == "f" * 40
    assert load_chain_state(spec_path).metadata["execution_binding"]


def test_bound_import_root_outweighs_unrelated_global_editable_metadata(
    tmp_path: Path, monkeypatch
) -> None:
    spec_path = _pinned_chain(tmp_path)
    state = _bound_state(spec_path)
    expected = state.metadata["execution_binding"]["launched_identity"]
    expected["runtime"]["editable_root"] = expected["runtime"]["import_root"]
    active = json.loads(json.dumps(expected))
    active["runtime"]["editable_root"] = str(tmp_path / "unrelated-resident-runtime")
    active["runtime"]["editable_revision"] = "f" * 40
    active["ready"] = False
    active["errors"] = ["editable_runtime_import_root_mismatch"]
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.execution_binding.active_execution_identity",
        lambda _spec_path: active,
    )

    report = execution_binding_report(spec_path, state)

    assert report["status"] == "match"
    assert report["drift_fields"] == []
    assert report["bound_import_root_match"] is True


def test_bound_import_root_does_not_cover_actual_import_drift(
    tmp_path: Path, monkeypatch
) -> None:
    spec_path = _pinned_chain(tmp_path)
    state = _bound_state(spec_path)
    expected = state.metadata["execution_binding"]["launched_identity"]
    expected["runtime"]["editable_root"] = expected["runtime"]["import_root"]
    active = json.loads(json.dumps(expected))
    active["runtime"]["import_root"] = str(tmp_path / "wrong-import-root")
    active["runtime"]["editable_root"] = str(tmp_path / "unrelated-resident-runtime")
    active["ready"] = False
    active["errors"] = ["editable_runtime_import_root_mismatch"]
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.execution_binding.active_execution_identity",
        lambda _spec_path: active,
    )

    report = execution_binding_report(spec_path, state)

    assert report["status"] == "drift"
    assert report["bound_import_root_match"] is False


def test_state_save_never_rewrites_immutable_launch_identity(tmp_path: Path) -> None:
    spec_path = _pinned_chain(tmp_path)
    state = _bound_state(spec_path)
    expected = json.loads(
        json.dumps(state.metadata["execution_binding"]["launched_identity"])
    )
    state.last_state = "between_milestones"
    save_chain_state(spec_path, state)

    reloaded = load_chain_state(spec_path)
    assert reloaded.metadata["execution_binding"]["launched_identity"] == expected


def test_guarded_rebind_adopts_inserted_successor_without_moving_cursor(tmp_path: Path) -> None:
    spec_path = _pinned_chain(tmp_path, ("m5", "m6"))
    state = _bound_state(spec_path)
    state.current_milestone_index = 0
    state.current_plan_name = "m5-plan"
    state.last_state = "reviewed"
    save_chain_state(spec_path, state)
    before = state.to_dict()
    previous_bundle = state.metadata["execution_binding"]["launched_identity"][
        "bundle_sha256"
    ]

    _replace_and_repin(spec_path, ("m5", "m5a", "m6"))
    active_bundle = active_execution_identity(spec_path)["bundle_sha256"]
    result = rebind_execution_identity(
        spec_path,
        state,
        expected_previous_bundle_sha256=previous_bundle,
        expected_active_bundle_sha256=active_bundle,
        expected_current_milestone="m5",
        expected_current_plan="m5-plan",
        expected_next_milestone="m5a",
        reason="insert atomic fail-closed completion boundary",
    )

    after = state.to_dict()
    assert result["execution_binding"]["status"] == "match"
    assert result["event"]["next_milestone"] == "m5a"
    assert len(result["event"]["content_sha256"]) == 64
    for field in before:
        if field != "metadata":
            assert after[field] == before[field]
    labels = [
        item["label"]
        for item in state.metadata["execution_binding"]["launched_identity"][
            "milestone_sequence"
        ]
    ]
    assert labels == ["m5", "m5a", "m6"]


@pytest.mark.parametrize(
    ("guard", "message"),
    [
        ("previous", "previous bundle SHA-256 does not match"),
        ("active", "active bundle SHA-256 does not match"),
        ("next", "active next milestone does not match"),
    ],
)
def test_guarded_rebind_fails_closed_on_wrong_content_or_successor(
    tmp_path: Path,
    guard: str,
    message: str,
) -> None:
    spec_path = _pinned_chain(tmp_path, ("m5", "m6"))
    state = _bound_state(spec_path)
    state.current_milestone_index = 0
    state.current_plan_name = "m5-plan"
    previous_bundle = state.metadata["execution_binding"]["launched_identity"][
        "bundle_sha256"
    ]
    _replace_and_repin(spec_path, ("m5", "m5a", "m6"))
    active_bundle = active_execution_identity(spec_path)["bundle_sha256"]
    before = json.loads(json.dumps(state.to_dict()))

    with pytest.raises(CliError, match=message):
        rebind_execution_identity(
            spec_path,
            state,
            expected_previous_bundle_sha256=(
                "0" * 64 if guard == "previous" else previous_bundle
            ),
            expected_active_bundle_sha256=(
                "f" * 64 if guard == "active" else active_bundle
            ),
            expected_current_milestone="m5",
            expected_current_plan="m5-plan",
            expected_next_milestone="m6" if guard == "next" else "m5a",
            reason="guard regression",
        )
    assert state.to_dict() == before


def test_guarded_rebind_rejects_changed_completed_or_current_prefix(tmp_path: Path) -> None:
    spec_path = _pinned_chain(tmp_path, ("m4", "m5", "m6"))
    state = _bound_state(spec_path)
    state.current_milestone_index = 1
    state.current_plan_name = "m5-plan"
    state.completed = [{"label": "m4", "plan": "m4-plan", "status": "done"}]
    previous_bundle = state.metadata["execution_binding"]["launched_identity"][
        "bundle_sha256"
    ]
    _replace_and_repin(spec_path, ("m4-renamed", "m5", "m5a", "m6"))
    active_bundle = active_execution_identity(spec_path)["bundle_sha256"]

    with pytest.raises(CliError, match="completed milestone prefix changed"):
        rebind_execution_identity(
            spec_path,
            state,
            expected_previous_bundle_sha256=previous_bundle,
            expected_active_bundle_sha256=active_bundle,
            expected_current_milestone="m5",
            expected_current_plan="m5-plan",
            expected_next_milestone="m5a",
            reason="must not rewrite history",
        )
