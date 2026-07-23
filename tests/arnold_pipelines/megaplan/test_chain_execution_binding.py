from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from arnold_pipelines.megaplan import chain as chain_module
from arnold_pipelines.megaplan.chain.execution_binding import (
    active_execution_identity,
    assert_execution_binding,
    bind_execution_identity,
    execution_binding_report,
    expected_worker_launch_values,
    find_bound_chain_spec,
    require_bound_chain_spec,
    rebind_execution_identity,
    rebind_runtime_identity,
    verify_external_runtime_identity,
)
from arnold_pipelines.megaplan.chain.spec import (
    ChainState,
    load_chain_state,
    load_spec,
    save_chain_state,
)
from arnold_pipelines.megaplan.cloud.runtime_cutover import normalize_runtime_identity
from arnold_pipelines.megaplan.types import CliError


REPO_ROOT = Path(__file__).resolve().parents[3]


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _canonical_sha256(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@pytest.fixture(scope="module")
def offline_rollback_runtime(
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[str, Path | str]:
    root = tmp_path_factory.mktemp("offline-runtime-rollback")
    source_a = root / "runtime-a"
    venv_a = root / "venv-a"
    venv_b = root / "venv-b"
    subprocess.run(
        ["git", "clone", "--shared", "--no-checkout", str(REPO_ROOT), str(source_a)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "-C", str(source_a), "checkout", "--detach", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "venv",
            "--copies",
            "--system-site-packages",
            str(venv_a),
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "venv",
            "--copies",
            "--system-site-packages",
            str(venv_b),
        ],
        check=True,
    )
    python_a = venv_a / "bin" / "python3"
    python_b = venv_b / "bin" / "python3"
    for python, source in ((python_a, source_a), (python_b, REPO_ROOT)):
        subprocess.run(
            [str(python), "-m", "pip", "install", "--no-deps", "-e", str(source)],
            check=True,
            capture_output=True,
            text=True,
        )
    revision_a = _git(source_a, "rev-parse", "HEAD")
    receipt = root / "runtime-a-receipt.json"
    identity = root / "runtime-a-identity.json"
    provenance_program = (
        REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "runtime_provenance.py"
    )
    result = subprocess.run(
        [
            str(python_a),
            "-P",
            str(provenance_program),
            "--expected-root",
            str(source_a),
            "--expected-revision",
            revision_a,
            "--receipt-out",
            str(receipt),
            "--identity-out",
            str(identity),
            "--emit-receipt",
        ],
        check=False,
        capture_output=True,
        text=True,
        env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
    )
    assert result.returncode == 0, result.stderr
    return {
        "root": root,
        "source_a": source_a,
        "python_a": python_a,
        "python_b": python_b,
        "revision_a": revision_a,
        "receipt": receipt,
        "identity": identity,
    }


def _write_chain(root: Path, labels: tuple[str, ...]) -> Path:
    initiative = root / ".megaplan" / "initiatives" / "demo"
    briefs = initiative / "briefs"
    briefs.mkdir(parents=True, exist_ok=True)
    (initiative / "NORTHSTAR.md").write_text(
        "# Durable destination\n", encoding="utf-8"
    )
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


def test_binding_records_spec_sequence_anchor_briefs_revision_and_runtime(
    tmp_path: Path,
) -> None:
    spec_path = _pinned_chain(tmp_path)

    state = _bound_state(spec_path)
    identity = state.metadata["execution_binding"]["launched_identity"]

    assert identity["ready"] is True
    assert [item["label"] for item in identity["milestone_sequence"]] == [
        "c1",
        "c2",
        "c3",
    ]
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


def test_binding_includes_declared_non_milestone_seed_assets(tmp_path: Path) -> None:
    spec_path = _pinned_chain(tmp_path)
    decision = spec_path.parent / "decisions" / "closure.md"
    decision.parent.mkdir()
    decision.write_text("# Structural closure\n\n- Must bind.\n", encoding="utf-8")
    external = tmp_path / "docs" / "incident-plan.md"
    external.parent.mkdir()
    external.write_text("# Incident plan\n", encoding="utf-8")
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    raw["driver"]["execution_binding_assets"] = [
        ".megaplan/initiatives/demo/decisions/closure.md",
        "docs/incident-plan.md",
    ]
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "bind structural seed assets")
    raw["driver"]["intended_initiative_revision"] = _git(
        tmp_path, "rev-parse", "HEAD"
    )
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    identity = active_execution_identity(spec_path)
    bound = [
        item for item in identity["assets"] if item["kind"].startswith("bound_asset:")
    ]

    assert identity["ready"] is True
    assert [item["declared_path"] for item in bound] == [
        ".megaplan/initiatives/demo/decisions/closure.md",
        "docs/incident-plan.md",
    ]
    assert all(item["sha256"] and item["semantic_sha256"] for item in bound)
    checks = identity["revision_verification"]["checks"]
    assert all(
        check["matches"]
        for check in checks
        if str(check["kind"]).startswith("bound_asset:")
    )


def test_binding_rejects_declared_asset_outside_project_root(tmp_path: Path) -> None:
    spec_path = _pinned_chain(tmp_path)
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    raw["driver"]["execution_binding_assets"] = ["../../../../outside.md"]
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    with pytest.raises(CliError, match="escapes project root"):
        active_execution_identity(spec_path)


def test_c1_bound_to_old_successors_cannot_adopt_corrective_sequence(
    tmp_path: Path,
) -> None:
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


def test_progressed_strict_state_without_launch_binding_fails_closed(
    tmp_path: Path,
) -> None:
    spec_path = _pinned_chain(tmp_path)
    save_chain_state(
        spec_path,
        ChainState(current_milestone_index=0, current_plan_name="legacy-plan"),
    )

    with pytest.raises(CliError, match="immutable chain execution binding is missing"):
        load_chain_state(spec_path)


def test_status_exposes_expected_and_active_identity_during_drift(
    tmp_path: Path,
) -> None:
    spec_path = _pinned_chain(tmp_path)
    _bound_state(spec_path)
    (spec_path.parent / "NORTHSTAR.md").write_text(
        "# Different destination\n", encoding="utf-8"
    )

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


def test_runtime_revision_is_evidence_but_not_canonical_source_drift(
    tmp_path: Path, monkeypatch
) -> None:
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


def test_guarded_rebind_adopts_inserted_successor_without_moving_cursor(
    tmp_path: Path,
) -> None:
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


def test_guarded_rebind_accepts_explicit_no_current_plan_sentinel(
    tmp_path: Path,
) -> None:
    spec_path = _pinned_chain(tmp_path, ("m5", "m6", "m7"))
    state = _bound_state(spec_path)
    state.completed = [{"label": "m5", "plan": "m5-plan", "status": "done"}]
    state.current_milestone_index = 1
    state.current_plan_name = None
    previous_bundle = state.metadata["execution_binding"]["launched_identity"][
        "bundle_sha256"
    ]

    _replace_and_repin(spec_path, ("m5", "m6", "m7a"))
    active_bundle = active_execution_identity(spec_path)["bundle_sha256"]
    result = rebind_execution_identity(
        spec_path,
        state,
        expected_previous_bundle_sha256=previous_bundle,
        expected_active_bundle_sha256=active_bundle,
        expected_current_milestone="m6",
        expected_current_plan="@none",
        expected_next_milestone="m7a",
        reason="adopt successor while parked between milestone plans",
    )

    assert result["event"]["current_plan"] == ""
    assert state.current_plan_name is None
    assert result["execution_binding"]["status"] == "match"


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


def test_guarded_rebind_rejects_changed_completed_or_current_prefix(
    tmp_path: Path,
) -> None:
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


def test_runtime_cutover_is_separate_from_spec_binding(
    tmp_path: Path,
    monkeypatch,
) -> None:
    spec_path = _pinned_chain(tmp_path)
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    raw["driver"]["require_editable_runtime_match"] = True
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "require runtime binding")
    raw["driver"]["intended_initiative_revision"] = _git(tmp_path, "rev-parse", "HEAD")
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    initial_active = active_execution_identity(spec_path)
    initial_active["runtime"]["editable_root"] = initial_active["runtime"][
        "import_root"
    ]
    initial_active["runtime"]["editable_revision"] = initial_active["runtime"][
        "source_revision"
    ]
    initial_active["ready"] = True
    initial_active["errors"] = []
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.execution_binding.active_execution_identity",
        lambda _path: initial_active,
    )
    state = _bound_state(spec_path)
    state.current_milestone_index = 0
    state.current_plan_name = "c1-plan"
    original_spec_identity = json.loads(
        json.dumps(state.metadata["execution_binding"]["launched_identity"])
    )
    original_runtime = json.loads(
        json.dumps(
            state.metadata["execution_binding"]["runtime_binding"]["current_identity"]
        )
    )
    assert (
        normalize_runtime_identity(original_runtime)["content_sha256"]
        == original_runtime["content_sha256"]
    )
    active = json.loads(json.dumps(initial_active))
    successor = json.loads(json.dumps(active))
    successor["runtime"].update(
        {
            "import_root": str(tmp_path / "runtime-b"),
            "editable_root": str(tmp_path / "runtime-b"),
            "source_revision": "b" * 40,
            "editable_revision": "b" * 40,
        }
    )
    successor["runtime"]["content_sha256"] = "ignored-and-recomputed"
    successor["ready"] = True
    successor["errors"] = []
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.execution_binding.active_execution_identity",
        lambda _path: successor,
    )
    drift = execution_binding_report(spec_path, state)
    assert drift["status"] == "match"
    assert drift["runtime_binding"]["status"] == "drift"
    with pytest.raises(CliError, match="runtime binding is drift"):
        assert_execution_binding(spec_path, state, operation="chain resume")
    before = state.to_dict()

    cutover = rebind_runtime_identity(
        spec_path,
        state,
        expected_previous_runtime_sha256=original_runtime["content_sha256"],
        expected_active_runtime_sha256=drift["runtime_binding"]["active"][
            "content_sha256"
        ],
        expected_current_milestone="c1",
        expected_current_plan="c1-plan",
        reason="activate verified runtime b",
    )

    assert cutover["runtime_binding"]["status"] == "match"
    assert (
        state.metadata["execution_binding"]["launched_identity"]
        == original_spec_identity
    )
    for field in before:
        if field != "metadata":
            assert state.to_dict()[field] == before[field]


def test_b_cli_rolls_back_to_independently_receipted_a_runtime(
    tmp_path: Path,
    offline_rollback_runtime: dict[str, Path | str],
) -> None:
    spec_path = _pinned_chain(tmp_path)
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    raw["driver"]["require_editable_runtime_match"] = True
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "require runtime binding")
    raw["driver"]["intended_initiative_revision"] = _git(tmp_path, "rev-parse", "HEAD")
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    python_b = Path(offline_rollback_runtime["python_b"])
    env_b = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONPATH", "PYTHONHOME"}
    }
    env_b["PYTHONPATH"] = str(REPO_ROOT)
    setup = subprocess.run(
        [
            str(python_b),
            "-P",
            "-c",
            (
                "from pathlib import Path;"
                "from arnold_pipelines.megaplan.chain.execution_binding import bind_execution_identity;"
                "from arnold_pipelines.megaplan.chain.spec import ChainState,save_chain_state;"
                f"p=Path({str(spec_path)!r});"
                "s=ChainState();"
                "r=bind_execution_identity(p,s);"
                "assert r['runtime_binding']['status']=='match',r;"
                "s.current_milestone_index=0;"
                "s.current_plan_name='c1-plan';"
                "save_chain_state(p,s)"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env_b,
    )
    assert setup.returncode == 0, setup.stderr
    before = load_chain_state(spec_path, verify_execution_binding=False)
    runtime_b = before.metadata["execution_binding"]["runtime_binding"][
        "current_identity"
    ]
    identity_a = json.loads(
        Path(offline_rollback_runtime["identity"]).read_text(encoding="utf-8")
    )

    command = subprocess.run(
        [
            str(python_b),
            "-P",
            "-m",
            "arnold_pipelines.megaplan",
            "chain",
            "runtime-rebind",
            "--spec",
            str(spec_path),
            "--project-dir",
            str(tmp_path),
            "--from-runtime-sha256",
            runtime_b["content_sha256"],
            "--to-runtime-sha256",
            identity_a["content_sha256"],
            "--expected-current-milestone",
            "c1",
            "--expected-current-plan",
            "c1-plan",
            "--direction",
            "rollback",
            "--reason",
            "real B CLI to independently observed A runtime",
            "--actor",
            "test-operator",
            "--runtime-identity",
            str(offline_rollback_runtime["identity"]),
            "--runtime-provenance-receipt",
            str(offline_rollback_runtime["receipt"]),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env_b,
    )
    assert command.returncode == 0, command.stderr
    payload = json.loads(command.stdout)
    assert payload["verification_mode"] == "external_interpreter_receipt"
    assert payload["event"]["direction"] == "rollback"
    assert payload["runtime_binding"]["status"] == "match"
    after = load_chain_state(spec_path, verify_execution_binding=False)
    assert (
        after.metadata["execution_binding"]["runtime_binding"]["current_identity"]
        == identity_a
    )
    assert after.current_milestone_index == before.current_milestone_index
    assert after.current_plan_name == before.current_plan_name
    assert after.completed == before.completed


def test_external_runtime_receipt_rejects_b_self_asserting_a(
    tmp_path: Path,
    offline_rollback_runtime: dict[str, Path | str],
) -> None:
    forged = json.loads(
        Path(offline_rollback_runtime["receipt"]).read_text(encoding="utf-8")
    )
    control = Path(sys.executable).resolve()
    forged["interpreter"] = {
        "executable": str(control),
        "sha256": hashlib.sha256(control.read_bytes()).hexdigest(),
        "prefix": str(Path(sys.prefix).resolve()),
        "base_prefix": str(Path(sys.base_prefix).resolve()),
    }
    core = {
        key: forged[key]
        for key in ("schema", "interpreter", "provenance", "runtime_identity")
    }
    forged["content_sha256"] = _canonical_sha256(core)
    forged_path = tmp_path / "forged-receipt.json"
    forged_path.write_text(json.dumps(forged), encoding="utf-8")

    with pytest.raises(CliError, match="interpreter is not independent"):
        verify_external_runtime_identity(
            Path(offline_rollback_runtime["identity"]),
            forged_path,
        )


def test_external_runtime_receipt_rejects_stale_pth_observation(
    offline_rollback_runtime: dict[str, Path | str],
) -> None:
    receipt = json.loads(
        Path(offline_rollback_runtime["receipt"]).read_text(encoding="utf-8")
    )
    pth_path = Path(receipt["runtime_identity"]["pth"][0]["path"])
    before = pth_path.read_bytes()
    try:
        with pth_path.open("a", encoding="utf-8") as handle:
            handle.write("/tmp/stale-runtime-root\n")
        with pytest.raises(CliError, match="stale or forged"):
            verify_external_runtime_identity(
                Path(offline_rollback_runtime["identity"]),
                Path(offline_rollback_runtime["receipt"]),
            )
    finally:
        pth_path.write_bytes(before)


def test_worker_expectations_resolve_canonical_spec_and_persisted_runtime(
    tmp_path: Path,
) -> None:
    spec_path = _pinned_chain(tmp_path)
    state = _bound_state(spec_path)
    state.current_plan_name = "owned-plan"
    save_chain_state(spec_path, state)
    expected_runtime = state.metadata["execution_binding"]["runtime_binding"][
        "current_identity"
    ]

    resolved = find_bound_chain_spec(tmp_path, plan_name="owned-plan")
    values = expected_worker_launch_values(resolved, root=tmp_path)

    assert resolved == spec_path
    assert values["expected_installed_package_path"] == expected_runtime["import_root"]
    assert values["expected_runtime_revision"] == expected_runtime["source_revision"]
    assert values["expected_source_ref"] == expected_runtime["source_revision"]
    assert values["expected_root"] == expected_runtime["import_root"]
    assert values["expected_chain_spec"] == str(spec_path.resolve())


def test_worker_binding_requirement_rejects_missing_canonical_owner(
    tmp_path: Path,
) -> None:
    with pytest.raises(CliError, match="is missing"):
        require_bound_chain_spec(tmp_path, plan_name="unowned-plan")


def test_worker_binding_requirement_rejects_ambiguous_canonical_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidates = [
        tmp_path / ".megaplan" / "initiatives" / name / "chain.yaml"
        for name in ("one", "two")
    ]
    for candidate in candidates:
        candidate.parent.mkdir(parents=True)
        candidate.write_text("milestones: []\n", encoding="utf-8")

    class _State:
        current_plan_name = "shared-plan"
        metadata = {"execution_binding": {"schema": "bound"}}

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.spec.load_chain_state",
        lambda *_args, **_kwargs: _State(),
    )

    with pytest.raises(CliError, match="is ambiguous") as error:
        require_bound_chain_spec(tmp_path, plan_name="shared-plan")
    assert error.value.extra["canonical_runtime_binding"]["candidates"] == [
        str(path.resolve()) for path in candidates
    ]


def test_worker_expectations_reject_incomplete_bound_runtime(tmp_path: Path) -> None:
    spec_path = _pinned_chain(tmp_path)
    state = _bound_state(spec_path)
    state.current_plan_name = "owned-plan"
    state.metadata["execution_binding"]["runtime_binding"]["current_identity"] = {
        "source_revision": "",
        "import_root": "",
    }
    save_chain_state(spec_path, state)

    with pytest.raises(CliError, match="incomplete worker runtime expectations"):
        expected_worker_launch_values(spec_path, root=tmp_path)
