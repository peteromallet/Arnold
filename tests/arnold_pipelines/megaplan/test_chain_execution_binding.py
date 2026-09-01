from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from arnold_pipelines.megaplan import chain as chain_module
from arnold_pipelines.megaplan.chain.execution_binding import (
    active_execution_identity,
    assert_execution_binding,
    bind_execution_identity,
    binding_policy,
    cutover_runtime_identity,
    execution_binding_report,
    expected_worker_launch_values,
    find_bound_chain_spec,
    migrate_execution_binding,
    require_bound_chain_spec,
    rebind_execution_identity,
    rebind_runtime_identity,
    verify_external_runtime_identity,
)
from arnold_pipelines.megaplan.chain.operator_pause import AUTHORITY_SCHEMA
from arnold_pipelines.megaplan.chain.spec import (
    ChainState,
    _state_path_for,
    load_chain_state,
    load_spec,
    save_chain_state,
)
from arnold_pipelines.megaplan.cloud.runtime_cutover import normalize_runtime_identity
from arnold_pipelines.megaplan.cloud.runtime_manifest import (
    MANIFEST_SCHEMA_VERSION,
    RuntimeManifest,
    write_manifest,
)
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


def _pinned_chain(
    tmp_path: Path,
    labels: tuple[str, ...] = ("c1", "c2", "c3"),
    *,
    require_runtime_match: bool = False,
    execution_binding: str = "required",
) -> Path:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "tests@example.com")
    _git(tmp_path, "config", "user.name", "Tests")
    spec_path = _write_chain(tmp_path, labels)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "initiative revision")
    revision = _git(tmp_path, "rev-parse", "HEAD")
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    raw["driver"]["intended_initiative_revision"] = revision
    raw["driver"]["require_editable_runtime_match"] = require_runtime_match
    raw["driver"]["execution_binding"] = execution_binding
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return spec_path


def _bound_state(spec_path: Path) -> ChainState:
    state = ChainState()
    report = bind_execution_identity(spec_path, state)
    assert report["status"] == "match"
    save_chain_state(spec_path, state)
    return state


def test_cloud_chain_defaults_runtime_match_to_trusted_container(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cloud chain launches default require_editable_runtime_match to True.

    The trusted-container env is set on every cloud chain start; the spec's
    explicit value always wins over the default.
    """
    spec_path = _write_chain(tmp_path, ("c1",))
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    raw["driver"].pop("require_editable_runtime_match", None)
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    monkeypatch.delenv("MEGAPLAN_TRUSTED_CONTAINER", raising=False)
    assert binding_policy(spec_path)["require_editable_runtime_match"] is False

    monkeypatch.setenv("MEGAPLAN_TRUSTED_CONTAINER", "1")
    assert binding_policy(spec_path)["require_editable_runtime_match"] is True

    # An explicit spec value always wins over the environment default.
    raw["driver"]["require_editable_runtime_match"] = False
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    monkeypatch.setenv("MEGAPLAN_TRUSTED_CONTAINER", "1")
    assert binding_policy(spec_path)["require_editable_runtime_match"] is False


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


def _engine_root_drift_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, ChainState, dict, dict, str]:
    """Bound chain with a drift successor AND an initialized engine_root.

    Mirrors the T-0101b migrate output: metadata.execution_binding +
    metadata.execution_environment.engine_root (== old runtime root) both
    present, cursor progressed, successor runtime drifted in.
    """
    spec_path = _pinned_chain(tmp_path)
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    raw["driver"]["require_editable_runtime_match"] = True
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "require runtime binding")
    raw["driver"]["intended_initiative_revision"] = _git(
        tmp_path, "rev-parse", "HEAD"
    )
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
    original_runtime = json.loads(
        json.dumps(
            state.metadata["execution_binding"]["runtime_binding"][
                "current_identity"
            ]
        )
    )
    successor_root = str((tmp_path / "runtime-b").resolve())
    successor = json.loads(json.dumps(initial_active))
    successor["runtime"].update(
        {
            "import_root": successor_root,
            "editable_root": successor_root,
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
    state.metadata["execution_environment"] = {
        "engine_root": original_runtime["import_root"]
    }
    drift = execution_binding_report(spec_path, state)
    assert drift["status"] == "match"
    assert drift["runtime_binding"]["status"] == "drift"
    return spec_path, state, original_runtime, drift, successor_root


def test_runtime_cutover_command_moves_engine_root_atomically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_path, state, original_runtime, drift, successor_root = (
        _engine_root_drift_case(tmp_path, monkeypatch)
    )
    before = state.to_dict()

    cutover = cutover_runtime_identity(
        spec_path,
        state,
        expected_previous_runtime_sha256=original_runtime["content_sha256"],
        expected_active_runtime_sha256=drift["runtime_binding"]["active"][
            "content_sha256"
        ],
        expected_current_milestone="c1",
        expected_current_plan="c1-plan",
        reason="cut over to verified runtime b",
    )

    assert cutover["runtime_binding"]["status"] == "match"
    assert cutover["verification_mode"] == "active_control_runtime"
    assert cutover["event"]["from_engine_root"] == str(
        Path(original_runtime["import_root"]).resolve()
    )
    assert cutover["event"]["to_engine_root"] == successor_root
    assert cutover["engine_root_transition"] == {
        "from_engine_root": str(Path(original_runtime["import_root"]).resolve()),
        "to_engine_root": successor_root,
    }
    assert (
        state.metadata["execution_environment"]["engine_root"] == successor_root
    )
    assert (
        state.metadata["execution_binding"]["runtime_binding"]["current_identity"][
            "content_sha256"
        ]
        == drift["runtime_binding"]["active"]["content_sha256"]
    )
    for field in before:
        if field != "metadata":
            assert state.to_dict()[field] == before[field]
    # The only metadata change is the binding + engine_root; cursor fields are
    # preserved byte-for-byte.
    assert state.current_milestone_index == 0
    assert state.current_plan_name == "c1-plan"


def test_runtime_cutover_rollback_direction_moves_engine_root_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_path, state, original_runtime, drift, successor_root = (
        _engine_root_drift_case(tmp_path, monkeypatch)
    )
    # Model a PRIOR cutover: the chain now persists runtime B with the B
    # engine root; the control runtime is still B (active), so the receipted
    # A runtime is the restore target supplied externally.
    successor_identity = json.loads(
        json.dumps(drift["runtime_binding"]["active"])
    )
    state.metadata["execution_binding"]["runtime_binding"][
        "current_identity"
    ] = successor_identity
    state.metadata["execution_binding"]["runtime_binding"]["rebind_events"] = [
        {
            "schema": "arnold.megaplan.chain_runtime_rebind.v1",
            "direction": "cutover",
            "from_runtime_sha256": original_runtime["content_sha256"],
            "to_runtime_sha256": successor_identity["content_sha256"],
        }
    ]
    state.metadata["execution_environment"] = {"engine_root": successor_root}
    before = state.to_dict()

    cutover = cutover_runtime_identity(
        spec_path,
        state,
        # Swapped guards: X is the current (successor) runtime, Y is the
        # runtime being restored via its independently receipted identity.
        expected_previous_runtime_sha256=successor_identity["content_sha256"],
        expected_active_runtime_sha256=original_runtime["content_sha256"],
        expected_current_milestone="c1",
        expected_current_plan="c1-plan",
        direction="rollback",
        reason="roll the engine root back to runtime a",
        verified_external_runtime_identity=original_runtime,
    )

    assert cutover["runtime_binding"]["status"] == "match"
    assert cutover["event"]["direction"] == "rollback"
    assert cutover["verification_mode"] == "external_interpreter_receipt"
    assert cutover["event"]["from_engine_root"] == successor_root
    assert cutover["event"]["to_engine_root"] == str(
        Path(original_runtime["import_root"]).resolve()
    )
    assert (
        state.metadata["execution_environment"]["engine_root"]
        == str(Path(original_runtime["import_root"]).resolve())
    )
    assert (
        state.metadata["execution_binding"]["runtime_binding"]["current_identity"][
            "content_sha256"
        ]
        == original_runtime["content_sha256"]
    )
    for field in before:
        if field != "metadata":
            assert state.to_dict()[field] == before[field]


def test_runtime_cutover_refuses_missing_engine_root_before_any_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_path, state, original_runtime, drift, _successor_root = (
        _engine_root_drift_case(tmp_path, monkeypatch)
    )
    state.metadata.pop("execution_environment", None)
    before = json.loads(json.dumps(state.to_dict()))

    with pytest.raises(CliError, match="engine_root is missing"):
        cutover_runtime_identity(
            spec_path,
            state,
            expected_previous_runtime_sha256=original_runtime["content_sha256"],
            expected_active_runtime_sha256=drift["runtime_binding"]["active"][
                "content_sha256"
            ],
            expected_current_milestone="c1",
            expected_current_plan="c1-plan",
            reason="must fail closed without a recorded engine root",
        )
    assert state.to_dict() == before


def test_runtime_cutover_refuses_engine_root_mismatch_before_any_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_path, state, original_runtime, drift, successor_root = (
        _engine_root_drift_case(tmp_path, monkeypatch)
    )
    state.metadata["execution_environment"] = {
        "engine_root": str(tmp_path / "unrelated-root")
    }
    before = json.loads(json.dumps(state.to_dict()))

    with pytest.raises(CliError, match="recorded engine root does not match"):
        cutover_runtime_identity(
            spec_path,
            state,
            expected_previous_runtime_sha256=original_runtime["content_sha256"],
            expected_active_runtime_sha256=drift["runtime_binding"]["active"][
                "content_sha256"
            ],
            expected_current_milestone="c1",
            expected_current_plan="c1-plan",
            reason="must refuse split engine root custody",
        )
    assert state.to_dict() == before
    assert state.metadata["execution_environment"]["engine_root"] != successor_root


def test_runtime_cutover_refuses_unbound_chain_before_any_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cutover requires the T-0101b migrate output: an unbound progressed
    chain is refused exactly like a runtime rebind."""
    spec_path = _pinned_chain(tmp_path)
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    raw["driver"]["require_editable_runtime_match"] = True
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "require runtime binding")
    raw["driver"]["intended_initiative_revision"] = _git(
        tmp_path, "rev-parse", "HEAD"
    )
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    state = _bound_state(spec_path)
    state.current_milestone_index = 0
    state.current_plan_name = "c1-plan"
    state.metadata.pop("execution_binding", None)
    state.metadata["execution_environment"] = {
        "engine_root": str(tmp_path / "runtime")
    }
    before = json.loads(json.dumps(state.to_dict()))

    with pytest.raises(CliError, match="persisted runtime identity is missing"):
        cutover_runtime_identity(
            spec_path,
            state,
            expected_previous_runtime_sha256="a" * 64,
            expected_active_runtime_sha256="b" * 64,
            expected_current_milestone="c1",
            expected_current_plan="c1-plan",
            reason="migrate must run before any cutover",
        )
    assert state.to_dict() == before


def test_runtime_cutover_inherits_runtime_sha_cas_guards(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_path, state, original_runtime, drift, _successor_root = (
        _engine_root_drift_case(tmp_path, monkeypatch)
    )
    before = json.loads(json.dumps(state.to_dict()))

    with pytest.raises(CliError, match="previous runtime SHA-256 does not match"):
        cutover_runtime_identity(
            spec_path,
            state,
            expected_previous_runtime_sha256="0" * 64,
            expected_active_runtime_sha256=drift["runtime_binding"]["active"][
                "content_sha256"
            ],
            expected_current_milestone="c1",
            expected_current_plan="c1-plan",
            reason="wrong from-guard must refuse",
        )
    assert state.to_dict() == before

    with pytest.raises(CliError, match="active runtime SHA-256 does not match"):
        cutover_runtime_identity(
            spec_path,
            state,
            expected_previous_runtime_sha256=original_runtime["content_sha256"],
            expected_active_runtime_sha256="f" * 64,
            expected_current_milestone="c1",
            expected_current_plan="c1-plan",
            reason="wrong to-guard must refuse",
        )
    assert state.to_dict() == before


def _terminal_runtime_drift_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, ChainState, dict, dict]:
    spec_path = _pinned_chain(tmp_path)
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    raw["driver"]["require_editable_runtime_match"] = True
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "require runtime binding")
    raw["driver"]["intended_initiative_revision"] = _git(
        tmp_path, "rev-parse", "HEAD"
    )
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
    labels = ("c1", "c2", "c3")
    state.current_milestone_index = len(labels)
    state.current_plan_name = None
    state.last_state = "done"
    state.completed = [
        {"label": label, "plan": f"{label}-plan", "status": "done"}
        for label in labels
    ]
    original_runtime = json.loads(
        json.dumps(
            state.metadata["execution_binding"]["runtime_binding"]["current_identity"]
        )
    )
    successor = json.loads(json.dumps(initial_active))
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
    assert drift["runtime_binding"]["status"] == "drift"
    return spec_path, state, original_runtime, drift


def test_runtime_cutover_accepts_exact_completed_terminal_cursor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_path, state, original_runtime, drift = _terminal_runtime_drift_case(
        tmp_path, monkeypatch
    )
    before = state.to_dict()

    cutover = rebind_runtime_identity(
        spec_path,
        state,
        expected_previous_runtime_sha256=original_runtime["content_sha256"],
        expected_active_runtime_sha256=drift["runtime_binding"]["active"][
            "content_sha256"
        ],
        expected_current_milestone="@terminal",
        expected_current_plan="@none",
        reason="promote a verified runtime after chain completion",
    )

    assert cutover["runtime_binding"]["status"] == "match"
    assert cutover["event"]["current_milestone"] == "@terminal"
    assert cutover["event"]["current_plan"] == ""
    for field in before:
        if field != "metadata":
            assert state.to_dict()[field] == before[field]


def _optional_runtime_rebind_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, ChainState, dict, dict, str]:
    """Build an optional-policy chain with durable pause and a drifted target."""
    spec_path = _pinned_chain(tmp_path, execution_binding="required")
    state = _bound_state(spec_path)
    previous = json.loads(
        json.dumps(
            state.metadata["execution_binding"]["runtime_binding"]["current_identity"]
        )
    )
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    raw["driver"]["execution_binding"] = "optional"
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    # Keep a canonical launched bundle while changing only the policy mode in
    # this fixture; the production optional-policy path may otherwise have no
    # launch binding at all (the legacy not_required shape).
    from arnold_pipelines.megaplan.chain.execution_binding import active_execution_identity

    state.metadata["execution_binding"]["launched_identity"] = (
        active_execution_identity(spec_path)
    )
    state.current_milestone_index = 1
    state.current_plan_name = "c2-plan"
    state.completed = [{"label": "c1", "plan": "c1-plan", "status": "done"}]
    state.last_state = "paused"
    state.metadata["operator_pause"] = {
        "schema_version": AUTHORITY_SCHEMA,
        "active": True,
        "paused_at": "2026-08-12T00:00:00+00:00",
        "actor": "test-operator",
        "reason": "pause before optional replacement",
        "previous_chain_last_state": "planned",
        "previous_plan_state": "planned",
        "plan": "c2-plan",
    }
    plan_path = _write_plan_state(tmp_path, "c2-plan")
    plan_state = json.loads(plan_path.read_text(encoding="utf-8"))
    plan_state["meta"] = {
        "operator_pause": {
            "schema_version": AUTHORITY_SCHEMA,
            "active": True,
            "plan": "c2-plan",
        }
    }
    plan_path.write_text(json.dumps(plan_state, sort_keys=True) + "\n", encoding="utf-8")
    # Save once after establishing the durable pause so the persisted
    # chain-spec hash is the exact CAS value the replacement must provide.
    save_chain_state(spec_path, state)
    expected_spec_sha = hashlib.sha256(spec_path.read_bytes()).hexdigest()
    successor = json.loads(json.dumps(previous))
    successor["import_root"] = str(tmp_path / "runtime-successor")
    successor["source_revision"] = "b" * 40
    successor = normalize_runtime_identity(successor)
    successor_execution = active_execution_identity(spec_path)
    successor_execution["runtime"] = dict(successor)
    successor_execution["ready"] = True
    successor_execution["errors"] = []
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.execution_binding.active_execution_identity",
        lambda _path: dict(successor_execution),
    )
    return spec_path, state, previous, successor, expected_spec_sha


def test_optional_runtime_rebind_replaces_identity_without_operational_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_path, state, previous, successor, expected_spec_sha = (
        _optional_runtime_rebind_case(tmp_path, monkeypatch)
    )
    before = json.loads(json.dumps(state.to_dict()))

    result = rebind_runtime_identity(
        spec_path,
        state,
        expected_previous_runtime_sha256=previous["content_sha256"],
        expected_active_runtime_sha256=successor["content_sha256"],
        expected_current_milestone="c2",
        expected_current_plan="c2-plan",
        reason="replace paused optional runtime",
        verified_external_runtime_identity=successor,
        allow_optional_policy=True,
        expected_chain_spec_sha256=expected_spec_sha,
    )

    assert result["runtime_binding"]["status"] == "not_required"
    assert result["event"]["optional_policy_override"] is True
    persisted_successor = dict(successor)
    persisted_successor["editable_revision"] = None
    assert (
        state.metadata["execution_binding"]["runtime_binding"]["current_identity"]
        == persisted_successor
    )
    for field in before:
        if field != "metadata":
            assert state.to_dict()[field] == before[field]
    assert state.metadata["chain_spec_sha256"] == expected_spec_sha
    assert state.metadata["execution_binding"]["launched_identity"] == before[
        "metadata"
    ]["execution_binding"]["launched_identity"]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({}, "runtime rebind is not required"),
        ({"expected_chain_spec_sha256": "0" * 64}, "requires --allow-optional-policy"),
        ({"allow_optional_policy": True, "expected_chain_spec_sha256": "f" * 64}, "supplied and persisted"),
    ],
)
def test_optional_runtime_rebind_refuses_without_exact_opt_in_guards(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kwargs: dict,
    message: str,
) -> None:
    spec_path, state, previous, successor, expected_spec_sha = (
        _optional_runtime_rebind_case(tmp_path, monkeypatch)
    )
    before = json.loads(json.dumps(state.to_dict()))
    args = {
        "expected_previous_runtime_sha256": previous["content_sha256"],
        "expected_active_runtime_sha256": successor["content_sha256"],
        "expected_current_milestone": "c2",
        "expected_current_plan": "c2-plan",
        "reason": "guard refusal",
        "verified_external_runtime_identity": successor,
    }
    args.update(kwargs)
    with pytest.raises(CliError, match=message):
        rebind_runtime_identity(spec_path, state, **args)
    assert state.to_dict() == before


def test_optional_runtime_rebind_refuses_missing_binding_and_bad_prefix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_path, state, previous, successor, expected_spec_sha = (
        _optional_runtime_rebind_case(tmp_path, monkeypatch)
    )
    binding = state.metadata["execution_binding"]["runtime_binding"]
    binding.pop("current_identity")
    before = json.loads(json.dumps(state.to_dict()))
    with pytest.raises(CliError, match="persisted runtime identity is missing"):
        rebind_runtime_identity(
            spec_path,
            state,
            expected_previous_runtime_sha256=previous["content_sha256"],
            expected_active_runtime_sha256=successor["content_sha256"],
            expected_current_milestone="c2",
            expected_current_plan="c2-plan",
            reason="missing current identity",
            verified_external_runtime_identity=successor,
            allow_optional_policy=True,
            expected_chain_spec_sha256=expected_spec_sha,
        )
    assert state.to_dict() == before


@pytest.mark.parametrize("tamper", ["chain_schema", "plan_pause", "plan_identity"])
def test_optional_runtime_rebind_rejects_forged_or_mismatched_pause(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tamper: str,
) -> None:
    spec_path, state, previous, successor, expected_spec_sha = (
        _optional_runtime_rebind_case(tmp_path, monkeypatch)
    )
    plan_path = tmp_path / ".megaplan" / "plans" / "c2-plan" / "state.json"
    plan_state = json.loads(plan_path.read_text(encoding="utf-8"))
    if tamper == "chain_schema":
        state.metadata["operator_pause"].pop("schema_version")
    elif tamper == "plan_pause":
        plan_state["meta"]["operator_pause"].pop("schema_version")
        plan_path.write_text(json.dumps(plan_state) + "\n", encoding="utf-8")
    else:
        plan_state["name"] = "foreign-plan"
        plan_path.write_text(json.dumps(plan_state) + "\n", encoding="utf-8")
    before = json.loads(json.dumps(state.to_dict()))
    with pytest.raises(CliError, match="pause|plan identity"):
        rebind_runtime_identity(
            spec_path,
            state,
            expected_previous_runtime_sha256=previous["content_sha256"],
            expected_active_runtime_sha256=successor["content_sha256"],
            expected_current_milestone="c2",
            expected_current_plan="c2-plan",
            reason="reject forged pause authority",
            verified_external_runtime_identity=successor,
            allow_optional_policy=True,
            expected_chain_spec_sha256=expected_spec_sha,
        )
    assert state.to_dict() == before


def test_optional_runtime_rebind_rejects_bound_brief_drift_without_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_path, state, previous, successor, expected_spec_sha = (
        _optional_runtime_rebind_case(tmp_path, monkeypatch)
    )
    brief = spec_path.parent / "briefs" / "c1.md"
    brief.write_text(
        brief.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8"
    )
    drifted_execution = active_execution_identity(spec_path)
    drifted_execution["runtime"] = dict(successor)
    drifted_execution["ready"] = True
    drifted_execution["errors"] = []
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.execution_binding.active_execution_identity",
        lambda _path: dict(drifted_execution),
    )
    before = json.loads(json.dumps(state.to_dict()))
    spec_bytes = spec_path.read_bytes()
    with pytest.raises(CliError, match="non-runtime immutable"):
        rebind_runtime_identity(
            spec_path,
            state,
            expected_previous_runtime_sha256=previous["content_sha256"],
            expected_active_runtime_sha256=successor["content_sha256"],
            expected_current_milestone="c2",
            expected_current_plan="c2-plan",
            reason="reject bound brief drift",
            verified_external_runtime_identity=successor,
            allow_optional_policy=True,
            expected_chain_spec_sha256=expected_spec_sha,
        )
    assert state.to_dict() == before
    assert spec_path.read_bytes() == spec_bytes


@pytest.mark.parametrize("guard", ["from", "to"])
def test_optional_runtime_rebind_wrong_runtime_cas_is_zero_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    guard: str,
) -> None:
    spec_path, state, previous, successor, expected_spec_sha = (
        _optional_runtime_rebind_case(tmp_path, monkeypatch)
    )
    before = json.loads(json.dumps(state.to_dict()))
    from_sha = "0" * 64 if guard == "from" else previous["content_sha256"]
    to_sha = "1" * 64 if guard == "to" else successor["content_sha256"]
    with pytest.raises(CliError, match="runtime SHA-256 does not match"):
        rebind_runtime_identity(
            spec_path,
            state,
            expected_previous_runtime_sha256=from_sha,
            expected_active_runtime_sha256=to_sha,
            expected_current_milestone="c2",
            expected_current_plan="c2-plan",
            reason="wrong runtime CAS",
            verified_external_runtime_identity=successor,
            allow_optional_policy=True,
            expected_chain_spec_sha256=expected_spec_sha,
        )
    assert state.to_dict() == before


def test_optional_runtime_rebind_is_typed_idempotent_on_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_path, state, previous, successor, expected_spec_sha = (
        _optional_runtime_rebind_case(tmp_path, monkeypatch)
    )
    rebind_runtime_identity(
        spec_path,
        state,
        expected_previous_runtime_sha256=previous["content_sha256"],
        expected_active_runtime_sha256=successor["content_sha256"],
        expected_current_milestone="c2",
        expected_current_plan="c2-plan",
        reason="first optional replacement",
        verified_external_runtime_identity=successor,
        allow_optional_policy=True,
        expected_chain_spec_sha256=expected_spec_sha,
    )
    save_chain_state(spec_path, state)
    before = json.loads(json.dumps(state.to_dict()))
    with pytest.raises(CliError, match="previous runtime SHA-256 does not match"):
        rebind_runtime_identity(
            spec_path,
            state,
            expected_previous_runtime_sha256=previous["content_sha256"],
            expected_active_runtime_sha256=successor["content_sha256"],
            expected_current_milestone="c2",
            expected_current_plan="c2-plan",
            reason="replay optional replacement",
            verified_external_runtime_identity=successor,
            allow_optional_policy=True,
            expected_chain_spec_sha256=expected_spec_sha,
        )
    assert state.to_dict() == before


def test_optional_runtime_rebind_rejects_optional_flag_on_required_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_path = _pinned_chain(tmp_path, require_runtime_match=True)
    state = ChainState()
    before = json.loads(json.dumps(state.to_dict()))
    with pytest.raises(CliError, match="only valid when driver.execution_binding is optional"):
        rebind_runtime_identity(
            spec_path,
            state,
            expected_previous_runtime_sha256="0" * 64,
            expected_active_runtime_sha256="1" * 64,
            expected_current_milestone="c1",
            expected_current_plan="c1-plan",
            reason="required policy misuse",
            allow_optional_policy=True,
            expected_chain_spec_sha256="2" * 64,
        )
    assert state.to_dict() == before


def test_runtime_rebind_parser_dispatches_optional_policy_guards() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    chain_module.build_chain_parser(subparsers)
    args = parser.parse_args(
        [
            "chain",
            "runtime-rebind",
            "--spec",
            "chain.yaml",
            "--from-runtime-sha256",
            "0" * 64,
            "--to-runtime-sha256",
            "1" * 64,
            "--expected-current-milestone",
            "c1",
            "--expected-current-plan",
            "c1-plan",
            "--reason",
            "parser coverage",
            "--allow-optional-policy",
            "--expected-chain-spec-sha256",
            "2" * 64,
        ]
    )
    assert args.chain_action == "runtime-rebind"
    assert args.allow_optional_policy is True
    assert args.expected_chain_spec_sha256 == "2" * 64


def test_runtime_cutover_cas_uses_verified_legacy_persisted_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_path, state, original_runtime, drift = _terminal_runtime_drift_case(
        tmp_path, monkeypatch
    )
    legacy_runtime = json.loads(json.dumps(original_runtime))
    legacy_runtime["shannon_dependencies"] = {
        "schema": "arnold.megaplan.shannon_dependencies.v1",
        "ready": True,
        "content_sha256": "c" * 64,
    }
    legacy_payload = {
        key: value
        for key, value in legacy_runtime.items()
        if key != "content_sha256"
    }
    legacy_runtime["content_sha256"] = _canonical_sha256(legacy_payload)
    state.metadata["execution_binding"]["runtime_binding"][
        "current_identity"
    ] = legacy_runtime

    cutover = rebind_runtime_identity(
        spec_path,
        state,
        expected_previous_runtime_sha256=legacy_runtime["content_sha256"],
        expected_active_runtime_sha256=drift["runtime_binding"]["active"][
            "content_sha256"
        ],
        expected_current_milestone="@terminal",
        expected_current_plan="@none",
        reason="accept the exact legacy persisted runtime digest",
    )

    assert cutover["runtime_binding"]["status"] == "match"
    assert cutover["event"]["from_runtime_sha256"] == legacy_runtime[
        "content_sha256"
    ]


def test_runtime_cutover_rejects_normalized_alias_for_legacy_persisted_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_path, state, original_runtime, drift = _terminal_runtime_drift_case(
        tmp_path, monkeypatch
    )
    legacy_runtime = json.loads(json.dumps(original_runtime))
    legacy_runtime["shannon_dependencies"] = {"ready": True}
    legacy_runtime["content_sha256"] = _canonical_sha256(
        {
            key: value
            for key, value in legacy_runtime.items()
            if key != "content_sha256"
        }
    )
    state.metadata["execution_binding"]["runtime_binding"][
        "current_identity"
    ] = legacy_runtime

    with pytest.raises(CliError, match="previous runtime SHA-256 does not match"):
        rebind_runtime_identity(
            spec_path,
            state,
            expected_previous_runtime_sha256=original_runtime["content_sha256"],
            expected_active_runtime_sha256=drift["runtime_binding"]["active"][
                "content_sha256"
            ],
            expected_current_milestone="@terminal",
            expected_current_plan="@none",
            reason="reject a normalized alias instead of the persisted digest",
        )


@pytest.mark.parametrize("tamper", ["digest", "unknown_field"])
def test_runtime_cutover_rejects_unverified_persisted_runtime_extensions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tamper: str,
) -> None:
    spec_path, state, original_runtime, drift = _terminal_runtime_drift_case(
        tmp_path, monkeypatch
    )
    persisted = json.loads(json.dumps(original_runtime))
    if tamper == "digest":
        persisted["shannon_dependencies"] = {"ready": True}
    else:
        persisted["unexpected_extension"] = {"ready": True}
        persisted["content_sha256"] = _canonical_sha256(
            {
                key: value
                for key, value in persisted.items()
                if key != "content_sha256"
            }
        )
    state.metadata["execution_binding"]["runtime_binding"][
        "current_identity"
    ] = persisted

    message = (
        "persisted runtime identity digest is invalid"
        if tamper == "digest"
        else "unsupported fields"
    )
    with pytest.raises(CliError, match=message):
        rebind_runtime_identity(
            spec_path,
            state,
            expected_previous_runtime_sha256=persisted["content_sha256"],
            expected_active_runtime_sha256=drift["runtime_binding"]["active"][
                "content_sha256"
            ],
            expected_current_milestone="@terminal",
            expected_current_plan="@none",
            reason="reject an unauthenticated persisted identity",
        )


@pytest.mark.parametrize(
    ("invalid_state", "message"),
    [
        ("milestone_guard", "@terminal milestone guard"),
        ("plan_guard", "@none plan guard"),
        ("active_plan", "current plan remains"),
        ("last_state", "canonical last_state 'done'"),
        ("missing_completion", "exact ordered milestone set"),
        ("out_of_order_completion", "exact ordered milestone set"),
        ("non_done_completion", "exact ordered milestone set"),
        ("past_terminal", "outside the bound sequence"),
        ("active_cursor_terminal_token", "current milestone does not match"),
    ],
)
def test_runtime_cutover_terminal_path_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    invalid_state: str,
    message: str,
) -> None:
    spec_path, state, original_runtime, drift = _terminal_runtime_drift_case(
        tmp_path, monkeypatch
    )
    expected_milestone = "@terminal"
    expected_plan = "@none"
    if invalid_state == "milestone_guard":
        expected_milestone = "c3"
    elif invalid_state == "plan_guard":
        expected_plan = "c3-plan"
    elif invalid_state == "active_plan":
        state.current_plan_name = "c3-plan"
    elif invalid_state == "last_state":
        state.last_state = "blocked"
    elif invalid_state == "missing_completion":
        state.completed.pop()
    elif invalid_state == "out_of_order_completion":
        state.completed[0], state.completed[1] = state.completed[1], state.completed[0]
    elif invalid_state == "non_done_completion":
        state.completed[-1]["status"] = "waived"
    elif invalid_state == "past_terminal":
        state.current_milestone_index += 1
    elif invalid_state == "active_cursor_terminal_token":
        state.current_milestone_index = 0
        state.current_plan_name = "c1-plan"
    before = json.loads(json.dumps(state.to_dict()))

    with pytest.raises(CliError, match=message):
        rebind_runtime_identity(
            spec_path,
            state,
            expected_previous_runtime_sha256=original_runtime["content_sha256"],
            expected_active_runtime_sha256=drift["runtime_binding"]["active"][
                "content_sha256"
            ],
            expected_current_milestone=expected_milestone,
            expected_current_plan=expected_plan,
            reason="terminal guard regression",
        )
    assert state.to_dict() == before


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


def test_b_cli_runtime_cutover_moves_engine_root_to_receipted_a(
    tmp_path: Path,
    offline_rollback_runtime: dict[str, Path | str],
) -> None:
    spec_path = _pinned_chain(tmp_path)
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    raw["driver"]["require_editable_runtime_match"] = True
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "require runtime binding")
    raw["driver"]["intended_initiative_revision"] = _git(
        tmp_path, "rev-parse", "HEAD"
    )
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
                "s.metadata['execution_environment']={'engine_root': "
                "s.metadata['execution_binding']['runtime_binding']"
                "['current_identity']['import_root']};"
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
    recorded_root = before.metadata["execution_environment"]["engine_root"]
    assert str(Path(recorded_root).resolve()) == str(
        Path(runtime_b["import_root"]).resolve()
    )
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
            "runtime-cutover",
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
            "real B CLI cutover to independently observed A runtime",
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
    assert payload["action"] == "runtime-cutover"
    assert payload["verification_mode"] == "external_interpreter_receipt"
    assert payload["event"]["direction"] == "rollback"
    assert payload["runtime_binding"]["status"] == "match"
    assert payload["engine_root_transition"]["to_engine_root"] == str(
        Path(identity_a["import_root"]).resolve()
    )
    after = load_chain_state(spec_path, verify_execution_binding=False)
    assert (
        after.metadata["execution_binding"]["runtime_binding"]["current_identity"]
        == identity_a
    )
    assert after.metadata["execution_environment"]["engine_root"] == str(
        Path(identity_a["import_root"]).resolve()
    )
    assert after.current_milestone_index == before.current_milestone_index
    assert after.current_plan_name == before.current_plan_name
    assert after.completed == before.completed


def test_cli_runtime_cutover_refuses_engine_root_drift_without_writing(
    tmp_path: Path,
    offline_rollback_runtime: dict[str, Path | str],
) -> None:
    """CLI-level fail-closed proof: a mismatched recorded engine_root refuses
    with a typed drift error and the persisted chain state is untouched."""
    spec_path = _pinned_chain(tmp_path)
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    raw["driver"]["require_editable_runtime_match"] = True
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "require runtime binding")
    raw["driver"]["intended_initiative_revision"] = _git(
        tmp_path, "rev-parse", "HEAD"
    )
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
                "s.metadata['execution_environment']={'engine_root': '/unrelated/recorded-root'};"
                "save_chain_state(p,s)"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env_b,
    )
    assert setup.returncode == 0, setup.stderr
    persisted = load_chain_state(spec_path, verify_execution_binding=False)
    runtime_b = persisted.metadata["execution_binding"]["runtime_binding"][
        "current_identity"
    ]
    identity_a = json.loads(
        Path(offline_rollback_runtime["identity"]).read_text(encoding="utf-8")
    )
    state_path = (
        tmp_path
        / ".megaplan"
        / "plans"
        / ".chains"
        / (
            "chain-"
            + hashlib.sha1(
                str(spec_path.resolve(strict=False)).encode("utf-8")
            ).hexdigest()[:12]
            + ".json"
        )
    )
    assert state_path.is_file()
    before_bytes = state_path.read_bytes()

    command = subprocess.run(
        [
            str(python_b),
            "-P",
            "-m",
            "arnold_pipelines.megaplan",
            "chain",
            "runtime-cutover",
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
            "must refuse split engine root custody",
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
    assert command.returncode != 0
    payload = json.loads(command.stdout)
    assert payload["success"] is False
    assert payload["error"] == "chain_runtime_binding_drift"
    assert "recorded engine root does not match" in payload["message"]
    assert state_path.read_bytes() == before_bytes


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


def test_worker_expectations_do_not_pin_runtime_when_policy_opts_out(
    tmp_path: Path,
) -> None:
    spec_path = _pinned_chain(tmp_path)
    state = _bound_state(spec_path)
    state.current_plan_name = "owned-plan"
    save_chain_state(spec_path, state)
    resolved = find_bound_chain_spec(tmp_path, plan_name="owned-plan")
    values = expected_worker_launch_values(resolved, root=tmp_path)

    assert resolved == spec_path
    assert values["expected_installed_package_path"] == ""
    assert values["expected_runtime_revision"] == ""
    assert values["expected_source_ref"] == ""
    assert values["expected_root"] == ""
    assert values["expected_chain_spec"] == str(spec_path.resolve())
    assert values["require_full_vector"] is False


def test_worker_expectations_propagate_strict_runtime_policy(
    tmp_path: Path,
    monkeypatch,
) -> None:
    spec_path = _pinned_chain(tmp_path)
    runtime = {
        "source_revision": "a" * 40,
        "import_root": "/runtime",
    }
    state = SimpleNamespace(
        metadata={
            "execution_binding": {
                "launched_identity": {},
                "runtime_binding": {"current_identity": runtime},
            }
        }
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.execution_binding.binding_policy",
        lambda _path: {"required": True, "require_editable_runtime_match": True},
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.spec.load_chain_state",
        lambda _path, verify_execution_binding=False: state,
    )

    values = expected_worker_launch_values(
        spec_path,
        root=tmp_path,
        runtime_vector_available=True,
    )

    assert values["expected_source_ref"] == "a" * 40
    assert values["expected_root"] == "/runtime"
    assert values["require_full_vector"] is True


def test_worker_expectations_do_not_require_seed_vector_when_unconfigured(
    tmp_path: Path,
    monkeypatch,
) -> None:
    spec_path = _pinned_chain(tmp_path)
    runtime = {
        "source_revision": "a" * 40,
        "import_root": "/runtime",
    }
    state = SimpleNamespace(
        metadata={
            "execution_binding": {
                "launched_identity": {},
                "runtime_binding": {"current_identity": runtime},
            }
        }
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.execution_binding.binding_policy",
        lambda _path: {"required": True, "require_editable_runtime_match": True},
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.spec.load_chain_state",
        lambda _path, verify_execution_binding=False: state,
    )

    values = expected_worker_launch_values(spec_path, root=tmp_path)

    # Root/revision/spec expectations remain populated and therefore strict.
    assert values["expected_source_ref"] == "a" * 40
    assert values["expected_installed_package_path"] == "/runtime"
    assert values["expected_runtime_revision"] == "a" * 40
    assert values["expected_root"] == "/runtime"
    # The module/interpreter/path vector can only come from a verified seed.
    assert values["expected_runtime_vector_sha256"] == ""
    assert values["require_full_vector"] is False


def test_worker_expectations_reject_malformed_binding_policy(tmp_path: Path) -> None:
    spec_path = _pinned_chain(tmp_path)
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    raw["driver"]["execution_binding"] = "sometimes"
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    with pytest.raises(CliError, match="driver.execution_binding"):
        expected_worker_launch_values(spec_path, root=tmp_path)


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


def test_worker_expectations_reject_incomplete_bound_runtime(
    tmp_path: Path,
    monkeypatch,
) -> None:
    spec_path = _pinned_chain(tmp_path)
    state = SimpleNamespace(
        metadata={
            "execution_binding": {
                "launched_identity": {},
                "runtime_binding": {
                    "current_identity": {
                        "source_revision": "",
                        "import_root": "",
                    }
                },
            }
        }
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.execution_binding.binding_policy",
        lambda _path: {"required": True, "require_editable_runtime_match": True},
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.spec.load_chain_state",
        lambda _path, verify_execution_binding=False: state,
    )

    with pytest.raises(CliError, match="incomplete worker runtime expectations"):
        expected_worker_launch_values(spec_path, root=tmp_path)


# ── T-0101b: guarded legacy execution-binding migration ─────────────────────
# The one-time migrate command initializes metadata.execution_binding +
# metadata.execution_environment.engine_root for a durably-paused, progressed,
# UNBOUND chain from its independently verified legacy runtime.  Every guard
# (spec hash, chain-state/plan-state CAS, cursor, branch, marker, per-epic
# manifest) must pass or the transaction refuses with zero mutation.


def _legacy_runtime_identity(root: Path, revision: str = "a" * 40) -> dict:
    identity = {
        "import_root": str(root),
        "source_revision": revision,
        "editable_root": str(root),
        "editable_revision": revision,
        "direct_url": {
            "dir_info": {"editable": True},
            "url": f"file://{root}",
        },
        "pth": [
            {
                "path": "/venv/site-packages/_editable_impl_arnold.pth",
                "entries": [str(root)],
                "readable": True,
            }
        ],
        "imports": {
            "arnold": f"{root}/arnold/__init__.py",
            "arnold_pipelines": f"{root}/arnold_pipelines/__init__.py",
            "megaplan": f"{root}/arnold_pipelines/megaplan/__init__.py",
        },
    }
    identity["content_sha256"] = _canonical_sha256(identity)
    return identity


def _write_plan_state(root: Path, plan: str) -> Path:
    plan_dir = root / ".megaplan" / "plans" / plan
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plan_dir / "state.json"
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "name": plan,
                "idea": "# c1\n",
                "idea_snapshot_path": "idea_snapshot.md",
                "current_state": "paused",
                "iteration": 0,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return plan_path


def _write_cloud_marker(
    root: Path,
    spec_path: Path,
    *,
    session: str,
    plan: str,
    runtime: dict,
    head: str | None = None,
    form: str = "legacy",
) -> Path:
    """Write a cloud-session marker; ``form`` selects the runtime identity
    evidence it carries (T-0101h finding 3):

    - ``"legacy"`` (default): ``editable_source_head`` +
      ``editable_install_sync.source`` — the full legacy evidence pair
    - ``"legacy-head"``: only ``editable_source_head``
    - ``"binding"``: only ``runtime_binding.current_identity``
    - ``"identity-less"``: the exact paused r5 shape (``editable_source_head``
      =None, ``editable_install_sync.status=skipped``, no source) with a
      relaunch naming exactly one ``/workspace/runtime-candidates``-style root
    - ``"none"``: no runtime identity evidence at all (real-root relaunch)
    """
    marker_dir = root / ".megaplan" / "cloud-sessions"
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker_path = marker_dir / f"{session}.json"
    marker = {
        "session": session,
        "workspace": str(root),
        "remote_spec": str(spec_path.resolve(strict=False)),
        "run_kind": "chain",
        "should_run": False,
        "operator_pause": {"active": True, "plan": plan},
        "editable_source_branch": "legacy",
        "relaunch_command": (
            f"PYTHONPATH={runtime['import_root']} python -P -m "
            f"arnold_pipelines.megaplan chain start --spec "
            f"{spec_path.resolve(strict=False)}"
        ),
    }
    if form == "binding":
        marker["runtime_binding"] = {
            "schema": "arnold.megaplan.chain_runtime_binding.v1",
            "current_identity": dict(runtime),
        }
    elif form in {"legacy", "legacy-head"}:
        marker["editable_source_head"] = (
            head if head is not None else runtime["source_revision"]
        )
        if form == "legacy":
            marker["editable_install_sync"] = {
                "status": "private-venv-editable",
                "source": runtime["import_root"],
            }
    elif form == "identity-less":
        marker["editable_source_branch"] = "editible-install"
        marker["editable_source_head"] = None
        marker["editable_install_sync"] = {
            "status": "skipped",
            "reason": "disabled_by_flag",
        }
        marker["relaunch_command"] = (
            f"SRC={runtime['import_root']}; PYTHONPATH={runtime['import_root']} "
            f"python -P -m arnold_pipelines.megaplan chain start --spec "
            f"{spec_path.resolve(strict=False)}"
        )
    elif form != "none":
        raise AssertionError(f"unknown marker form {form!r}")
    marker_path.write_text(
        json.dumps(marker, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return marker_path


def _write_runtime_manifest(
    manifest_path: Path,
    *,
    epic_id: str,
    runtime_root: Path,
    expected_head: str,
) -> Path:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = RuntimeManifest.from_dict(
        {
            "runtime_id": "runtime-canary-1",
            "schema": MANIFEST_SCHEMA_VERSION,
            "generation": 1,
            "epic_id": epic_id,
            "state": "active",
            "owner": "operator",
            "base": {
                "ref": "refs/heads/main",
                "commit": expected_head,
                "editable_install_path": str(runtime_root),
                "venv_path": str(runtime_root / "venv"),
            },
            "epic": {
                "branch": "canary-work",
                "worktree_path": str(runtime_root),
                "venv_path": str(runtime_root / "venv"),
                "runtime_root": str(runtime_root),
                "expected_head": expected_head,
                "repair_bin": str(runtime_root / "venv" / "bin" / "arnold-babysitter"),
                "deps_lockfile": str(runtime_root / "uv.lock"),
            },
            "indirection": {
                "host_path": str(runtime_root),
                "container_path": "/workspace/demo",
                "mount_table": [],
                "execution_namespace": "demo-ns",
                "verified_head": expected_head,
                "last_verified_at": "2026-08-12T00:00:00+00:00",
                "attestation": {
                    "module_file": str(runtime_root / "arnold_pipelines" / "__init__.py"),
                    "module_digest": "0" * 64,
                    "mount_id": "0:0",
                },
            },
            "policy": {
                "policy_sha": "policy-1",
                "model_policy_sha": "model-1",
                "sync_policy": "push-on-promote",
            },
            "promotions": [],
            "timestamps": {
                "created": "2026-08-12T00:00:00+00:00",
                "updated": "2026-08-12T00:00:00+00:00",
                "closed": "",
            },
            "gc_policy": "closed-only",
            "commands": ["megaplan chain"],
        }
    )
    write_manifest(manifest, manifest_path)
    return manifest_path


def _paused_unbound_state(
    spec_path: Path,
    *,
    plan: str,
    session: str,
    milestone_index: int = 0,
    paused: bool = True,
) -> ChainState:
    state = ChainState()
    state.current_milestone_index = milestone_index
    state.current_plan_name = plan
    state.last_state = "paused" if paused else "planned"
    state.chain_session = session
    if paused:
        state.metadata["operator_pause"] = {
            "schema_version": AUTHORITY_SCHEMA,
            "active": True,
            "paused_at": "2026-08-12T00:00:00+00:00",
            "actor": "test-operator",
            "reason": "pause for migration",
            "previous_chain_last_state": "planned",
            "previous_plan_state": "planned",
            "plan": plan,
        }
    save_chain_state(spec_path, state)
    return state


def _migrate_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    runtime: dict | None = None,
    branch: str = "canary-work",
    plan: str = "c1-plan",
    session: str = "canary-session",
    paused: bool = True,
    marker_head: str | None = None,
    marker_form: str = "legacy",
    manifest_root: Path | None = None,
    manifest_head: str | None = None,
    spec_tamper: bool = False,
    execution_binding: str = "required",
) -> dict:
    spec_path = _pinned_chain(
        tmp_path, ("c1", "c2", "c3"), execution_binding=execution_binding
    )
    _git(tmp_path, "checkout", "-b", branch)
    runtime = runtime or _legacy_runtime_identity(tmp_path / "runtime-old")
    _paused_unbound_state(
        spec_path,
        plan=plan,
        session=session,
        paused=paused,
    )
    plan_path = _write_plan_state(tmp_path, plan)
    marker_path = _write_cloud_marker(
        tmp_path,
        spec_path,
        session=session,
        plan=plan,
        runtime=runtime,
        head=marker_head,
        form=marker_form,
    )
    manifest_path = _write_runtime_manifest(
        tmp_path / "runtime-manifest.json",
        epic_id="demo",
        runtime_root=manifest_root or Path(runtime["import_root"]),
        expected_head=manifest_head or runtime["source_revision"],
    )
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(manifest_path))
    if spec_tamper:
        spec_path.write_text(
            spec_path.read_text(encoding="utf-8") + "# tampered\n",
            encoding="utf-8",
        )
    return {
        "spec_path": spec_path,
        "plan_path": plan_path,
        "marker_path": marker_path,
        "manifest_path": manifest_path,
        "runtime": runtime,
        "branch": branch,
        "plan": plan,
        "session": session,
    }


def test_execution_binding_migrate_initializes_binding_on_paused_progressed_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # T-0101h finding 1: the migration IS the transition that creates the
    # binding — it must run against the paused PRE-required (optional) legacy
    # spec; the required bundle + chain rebind harden the chain afterwards.
    fixture = _migrate_fixture(
        tmp_path, monkeypatch, execution_binding="optional"
    )
    spec_path = fixture["spec_path"]
    runtime = fixture["runtime"]
    before = load_chain_state(spec_path, verify_execution_binding=False)

    result = migrate_execution_binding(
        spec_path,
        tmp_path,
        expected_current_milestone="c1",
        expected_current_plan="c1-plan",
        expected_branch="canary-work",
        reason="bind legacy runtime before cutover",
        actor="test-operator",
        verified_external_runtime_identity=runtime,
    )

    assert result["old_runtime_sha256"] == runtime["content_sha256"]
    assert result["old_runtime_root"] == str(Path(runtime["import_root"]).resolve())
    assert result["engine_root"] == str(Path(runtime["import_root"]).resolve())
    assert result["runtime_binding"]["expected"]["content_sha256"] == runtime[
        "content_sha256"
    ]
    assert result["runtime_binding"]["active"]["content_sha256"] == runtime[
        "content_sha256"
    ]

    # The migrated chain must load with full binding verification enabled.
    after = load_chain_state(spec_path)
    binding = after.metadata["execution_binding"]
    assert binding["schema"] == "arnold.megaplan.chain_execution_binding.v1"
    assert binding["bound_at"]
    assert binding["launched_identity"]["runtime"] == runtime
    assert binding["launched_identity"]["ready"] is True
    runtime_binding = binding["runtime_binding"]
    assert runtime_binding["schema"] == "arnold.megaplan.chain_runtime_binding.v1"
    assert runtime_binding["current_identity"] == runtime
    assert runtime_binding["rebind_events"] == []
    assert (
        after.metadata["execution_environment"]["engine_root"]
        == str(Path(runtime["import_root"]).resolve())
    )
    for field in before.to_dict():
        if field != "metadata":
            assert before.to_dict()[field] == after.to_dict()[field]


def test_execution_binding_migrate_refuses_wrong_milestone_zero_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _migrate_fixture(tmp_path, monkeypatch)
    spec_path = fixture["spec_path"]
    state_bytes = _state_path_for(spec_path).read_bytes()
    marker_bytes = fixture["marker_path"].read_bytes()
    manifest_bytes = fixture["manifest_path"].read_bytes()
    plan_bytes = fixture["plan_path"].read_bytes()

    with pytest.raises(CliError, match="current milestone does not match"):
        migrate_execution_binding(
            spec_path,
            tmp_path,
            expected_current_milestone="c2",
            expected_current_plan="c1-plan",
            expected_branch="canary-work",
            reason="wrong milestone guard",
            actor="test-operator",
            verified_external_runtime_identity=fixture["runtime"],
        )
    assert _state_path_for(spec_path).read_bytes() == state_bytes
    assert fixture["marker_path"].read_bytes() == marker_bytes
    assert fixture["manifest_path"].read_bytes() == manifest_bytes
    assert fixture["plan_path"].read_bytes() == plan_bytes


def test_execution_binding_migrate_refuses_wrong_plan_zero_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _migrate_fixture(tmp_path, monkeypatch)
    spec_path = fixture["spec_path"]
    state_bytes = _state_path_for(spec_path).read_bytes()

    with pytest.raises(CliError, match="current plan"):
        migrate_execution_binding(
            spec_path,
            tmp_path,
            expected_current_milestone="c1",
            expected_current_plan="other-plan",
            expected_branch="canary-work",
            reason="wrong plan guard",
            actor="test-operator",
            verified_external_runtime_identity=fixture["runtime"],
        )
    assert _state_path_for(spec_path).read_bytes() == state_bytes


def test_execution_binding_migrate_refuses_wrong_branch_zero_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _migrate_fixture(tmp_path, monkeypatch)
    spec_path = fixture["spec_path"]
    state_bytes = _state_path_for(spec_path).read_bytes()

    with pytest.raises(CliError, match="branch does not match"):
        migrate_execution_binding(
            spec_path,
            tmp_path,
            expected_current_milestone="c1",
            expected_current_plan="c1-plan",
            expected_branch="other-branch",
            reason="wrong branch guard",
            actor="test-operator",
            verified_external_runtime_identity=fixture["runtime"],
        )
    assert _state_path_for(spec_path).read_bytes() == state_bytes


def test_execution_binding_migrate_refuses_unpaused_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _migrate_fixture(tmp_path, monkeypatch, paused=False)
    spec_path = fixture["spec_path"]
    state_bytes = _state_path_for(spec_path).read_bytes()

    with pytest.raises(CliError, match="not durably paused"):
        migrate_execution_binding(
            spec_path,
            tmp_path,
            expected_current_milestone="c1",
            expected_current_plan="c1-plan",
            expected_branch="canary-work",
            reason="unpaused migrate",
            actor="test-operator",
            verified_external_runtime_identity=fixture["runtime"],
        )
    assert _state_path_for(spec_path).read_bytes() == state_bytes


def test_execution_binding_migrate_refuses_spec_sha_change_zero_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _migrate_fixture(tmp_path, monkeypatch, spec_tamper=True)
    spec_path = fixture["spec_path"]
    state_bytes = _state_path_for(spec_path).read_bytes()

    with pytest.raises(CliError, match="chain spec SHA-256 does not match"):
        migrate_execution_binding(
            spec_path,
            tmp_path,
            expected_current_milestone="c1",
            expected_current_plan="c1-plan",
            expected_branch="canary-work",
            reason="tampered spec",
            actor="test-operator",
            verified_external_runtime_identity=fixture["runtime"],
        )
    assert _state_path_for(spec_path).read_bytes() == state_bytes


def test_execution_binding_migrate_refuses_marker_runtime_sha_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _migrate_fixture(
        tmp_path,
        monkeypatch,
        marker_head="b" * 40,
    )
    spec_path = fixture["spec_path"]
    state_bytes = _state_path_for(spec_path).read_bytes()

    with pytest.raises(CliError, match="marker source head does not match"):
        migrate_execution_binding(
            spec_path,
            tmp_path,
            expected_current_milestone="c1",
            expected_current_plan="c1-plan",
            expected_branch="canary-work",
            reason="marker disagrees",
            actor="test-operator",
            verified_external_runtime_identity=fixture["runtime"],
        )
    assert _state_path_for(spec_path).read_bytes() == state_bytes


def test_execution_binding_migrate_accepts_marker_legacy_source_head(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-0101h finding 3: the legacy ``editable_source_head`` matching the
    verified legacy runtime IS accepted marker identity evidence (the migrate
    happy path on the real chain's marker form)."""
    fixture = _migrate_fixture(
        tmp_path,
        monkeypatch,
        execution_binding="optional",
        marker_form="legacy-head",
    )
    spec_path = fixture["spec_path"]
    runtime = fixture["runtime"]

    result = migrate_execution_binding(
        spec_path,
        tmp_path,
        expected_current_milestone="c1",
        expected_current_plan="c1-plan",
        expected_branch="canary-work",
        reason="legacy head marker agrees",
        actor="test-operator",
        verified_external_runtime_identity=runtime,
    )
    assert result["old_runtime_sha256"] == runtime["content_sha256"]
    after = load_chain_state(spec_path)
    assert after.metadata["execution_binding"]["runtime_binding"][
        "current_identity"
    ] == runtime


def test_execution_binding_migrate_accepts_marker_runtime_binding_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-0101h finding 3: a ``runtime_binding.current_identity`` whose digest
    matches the verified legacy runtime is accepted marker identity
    evidence."""
    fixture = _migrate_fixture(
        tmp_path,
        monkeypatch,
        execution_binding="optional",
        marker_form="binding",
    )
    spec_path = fixture["spec_path"]
    runtime = fixture["runtime"]

    result = migrate_execution_binding(
        spec_path,
        tmp_path,
        expected_current_milestone="c1",
        expected_current_plan="c1-plan",
        expected_branch="canary-work",
        reason="runtime-binding marker agrees",
        actor="test-operator",
        verified_external_runtime_identity=runtime,
    )
    assert result["old_runtime_sha256"] == runtime["content_sha256"]
    after = load_chain_state(spec_path)
    assert after.metadata["execution_binding"]["runtime_binding"][
        "current_identity"
    ] == runtime


def test_execution_binding_migrate_refuses_identity_less_marker_without_sha_guard_zero_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-0101h round-3 blocker 1: an identity-less marker is accepted ONLY
    under the explicit marker-SHA guard — a bare identity-less marker with no
    ``expected_marker_sha256`` must refuse with zero mutation (fail-closed —
    absence never "agrees" by itself)."""
    fixture = _migrate_fixture(
        tmp_path,
        monkeypatch,
        execution_binding="optional",
        marker_form="none",
    )
    spec_path = fixture["spec_path"]
    state_bytes = _state_path_for(spec_path).read_bytes()
    marker_bytes = fixture["marker_path"].read_bytes()
    manifest_bytes = fixture["manifest_path"].read_bytes()
    plan_bytes = fixture["plan_path"].read_bytes()

    with pytest.raises(CliError, match="marker SHA-256 guard is required"):
        migrate_execution_binding(
            spec_path,
            tmp_path,
            expected_current_milestone="c1",
            expected_current_plan="c1-plan",
            expected_branch="canary-work",
            reason="identity-less marker without sha guard",
            actor="test-operator",
            verified_external_runtime_identity=fixture["runtime"],
        )
    assert _state_path_for(spec_path).read_bytes() == state_bytes
    assert fixture["marker_path"].read_bytes() == marker_bytes
    assert fixture["manifest_path"].read_bytes() == manifest_bytes
    assert fixture["plan_path"].read_bytes() == plan_bytes


def test_execution_binding_migrate_accepts_identity_less_marker_with_matching_relaunch_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-0101h round-3 blocker 1: the EXACT paused identity-less legacy
    marker (no runtime identity fields) is an accepted marker identity form
    when its exact sha256 is expected AND its relaunch command names exactly
    one /workspace/runtime-candidates-style root equal to the verified legacy
    runtime root.  Migrate only VERIFIES agreement — the strong binding is
    created by the FOLLOWING legacy-marker migration."""
    runtime = _legacy_runtime_identity(
        Path("/workspace/runtime-candidates/arnold-unit-legacy")
    )
    fixture = _migrate_fixture(
        tmp_path,
        monkeypatch,
        execution_binding="optional",
        marker_form="identity-less",
        runtime=runtime,
    )
    spec_path = fixture["spec_path"]
    marker_sha256 = hashlib.sha256(fixture["marker_path"].read_bytes()).hexdigest()
    marker_before = fixture["marker_path"].read_bytes()

    result = migrate_execution_binding(
        spec_path,
        tmp_path,
        expected_current_milestone="c1",
        expected_current_plan="c1-plan",
        expected_branch="canary-work",
        reason="identity-less marker agrees under the explicit guards",
        actor="test-operator",
        expected_marker_sha256=marker_sha256,
        verified_external_runtime_identity=runtime,
    )
    assert result["old_runtime_sha256"] == runtime["content_sha256"]
    assert result["engine_root"] == str(Path(runtime["import_root"]).resolve())
    after = load_chain_state(spec_path)
    assert after.metadata["execution_binding"]["runtime_binding"][
        "current_identity"
    ] == runtime
    # The marker itself is NOT bound by migrate: the identity-less form is
    # consumed byte-unchanged (the strong binding lands in the FOLLOWING
    # legacy-marker migration step).
    assert fixture["marker_path"].read_bytes() == marker_before
    marker = json.loads(fixture["marker_path"].read_text(encoding="utf-8"))
    assert "runtime_binding" not in marker
    assert marker["editable_source_head"] is None


def test_execution_binding_migrate_refuses_identity_less_marker_wrong_relaunch_root_zero_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-0101h round-3 blocker 1: an identity-less marker whose relaunch
    command names a DIFFERENT /workspace/runtime-candidates root than the
    verified legacy runtime root must refuse with zero mutation."""
    runtime = _legacy_runtime_identity(
        Path("/workspace/runtime-candidates/arnold-unit-legacy")
    )
    fixture = _migrate_fixture(
        tmp_path,
        monkeypatch,
        execution_binding="optional",
        marker_form="identity-less",
        runtime=runtime,
    )
    spec_path = fixture["spec_path"]
    marker = json.loads(fixture["marker_path"].read_text(encoding="utf-8"))
    marker["relaunch_command"] = marker["relaunch_command"].replace(
        "/workspace/runtime-candidates/arnold-unit-legacy",
        "/workspace/runtime-candidates/arnold-other-legacy",
    )
    fixture["marker_path"].write_text(
        json.dumps(marker, sort_keys=True) + "\n", encoding="utf-8"
    )
    marker_sha256 = hashlib.sha256(fixture["marker_path"].read_bytes()).hexdigest()
    state_bytes = _state_path_for(spec_path).read_bytes()
    marker_bytes = fixture["marker_path"].read_bytes()
    manifest_bytes = fixture["manifest_path"].read_bytes()
    plan_bytes = fixture["plan_path"].read_bytes()

    with pytest.raises(CliError, match="relaunch command does not name exactly"):
        migrate_execution_binding(
            spec_path,
            tmp_path,
            expected_current_milestone="c1",
            expected_current_plan="c1-plan",
            expected_branch="canary-work",
            reason="identity-less marker relaunches a different root",
            actor="test-operator",
            expected_marker_sha256=marker_sha256,
            verified_external_runtime_identity=runtime,
        )
    assert _state_path_for(spec_path).read_bytes() == state_bytes
    assert fixture["marker_path"].read_bytes() == marker_bytes
    assert fixture["manifest_path"].read_bytes() == manifest_bytes
    assert fixture["plan_path"].read_bytes() == plan_bytes


def test_execution_binding_migrate_refuses_manifest_root_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _migrate_fixture(
        tmp_path,
        monkeypatch,
        manifest_root=tmp_path / "other-runtime",
    )
    spec_path = fixture["spec_path"]
    state_bytes = _state_path_for(spec_path).read_bytes()

    with pytest.raises(CliError, match="epic.runtime_root does not match"):
        migrate_execution_binding(
            spec_path,
            tmp_path,
            expected_current_milestone="c1",
            expected_current_plan="c1-plan",
            expected_branch="canary-work",
            reason="manifest disagrees",
            actor="test-operator",
            verified_external_runtime_identity=fixture["runtime"],
        )
    assert _state_path_for(spec_path).read_bytes() == state_bytes


def test_execution_binding_migrate_refuses_manifest_head_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _migrate_fixture(
        tmp_path,
        monkeypatch,
        manifest_head="c" * 40,
    )
    spec_path = fixture["spec_path"]
    state_bytes = _state_path_for(spec_path).read_bytes()

    with pytest.raises(CliError, match="epic.expected_head does not match"):
        migrate_execution_binding(
            spec_path,
            tmp_path,
            expected_current_milestone="c1",
            expected_current_plan="c1-plan",
            expected_branch="canary-work",
            reason="manifest head disagrees",
            actor="test-operator",
            verified_external_runtime_identity=fixture["runtime"],
        )
    assert _state_path_for(spec_path).read_bytes() == state_bytes


def test_execution_binding_migrate_refuses_already_bound_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _migrate_fixture(tmp_path, monkeypatch)
    spec_path = fixture["spec_path"]
    state = load_chain_state(spec_path, verify_execution_binding=False)
    state.metadata["execution_binding"] = {"schema": "already-bound"}
    save_chain_state(spec_path, state)
    state_bytes = _state_path_for(spec_path).read_bytes()

    with pytest.raises(CliError, match="execution binding already exists"):
        migrate_execution_binding(
            spec_path,
            tmp_path,
            expected_current_milestone="c1",
            expected_current_plan="c1-plan",
            expected_branch="canary-work",
            reason="double migrate",
            actor="test-operator",
            verified_external_runtime_identity=fixture["runtime"],
        )
    assert _state_path_for(spec_path).read_bytes() == state_bytes


def test_execution_binding_migrate_refuses_unprogressed_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _migrate_fixture(tmp_path, monkeypatch)
    spec_path = fixture["spec_path"]
    state = load_chain_state(spec_path, verify_execution_binding=False)
    state.current_milestone_index = -1
    state.current_plan_name = None
    state.last_state = None
    state.chain_session = None
    # Keep the durable pause authority: the progress guard must fire, not the
    # pause guard.
    state.metadata = {"operator_pause": state.metadata["operator_pause"]}
    save_chain_state(spec_path, state)
    state_bytes = _state_path_for(spec_path).read_bytes()

    with pytest.raises(CliError, match="chain has not progressed"):
        migrate_execution_binding(
            spec_path,
            tmp_path,
            expected_current_milestone="c1",
            expected_current_plan="c1-plan",
            expected_branch="canary-work",
            reason="fresh chain migrate",
            actor="test-operator",
            verified_external_runtime_identity=fixture["runtime"],
        )
    assert _state_path_for(spec_path).read_bytes() == state_bytes


def test_execution_binding_migrate_env_marker_dir_takes_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G7: migrate resolves the cloud-session marker through
    ARNOLD_CHAIN_SESSION_MARKER_DIR first.  A valid marker ONLY in the env
    dir — with a corrupt decoy at the project-relative fallback — must be
    resolved: reading the decoy would raise, so success proves the env dir
    wins over the fallback.
    """
    fixture = _migrate_fixture(tmp_path, monkeypatch, session="g7-marker-env")
    spec_path = fixture["spec_path"]
    runtime = fixture["runtime"]
    env_marker_dir = tmp_path / "env-layout" / ".megaplan" / "cloud-sessions"
    _write_cloud_marker(
        tmp_path / "env-layout",
        spec_path,
        session="g7-marker-env",
        plan="c1-plan",
        runtime=runtime,
    )
    # Decoy: the project-relative fallback holds a corrupt marker for the
    # same session — reading it would raise, not silently succeed.
    fixture["marker_path"].write_text("{ not json", encoding="utf-8")
    monkeypatch.setenv("ARNOLD_CHAIN_SESSION_MARKER_DIR", str(env_marker_dir))

    result = migrate_execution_binding(
        spec_path,
        tmp_path,
        expected_current_milestone="c1",
        expected_current_plan="c1-plan",
        expected_branch="canary-work",
        reason="env marker dir precedence",
        actor="test-operator",
        verified_external_runtime_identity=runtime,
    )
    assert result["engine_root"] == str(Path(runtime["import_root"]).resolve())


def test_execution_binding_migrate_canonical_workspace_marker_dir_used_without_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G7: without the env override the CANONICAL workspace marker dir
    (/workspace/.megaplan/cloud-sessions, cli.py:2640) is consulted before
    the project-relative fallback.  The canonical probe is simulated (the
    test host has no /workspace) with the exact bytes a real box marker
    would hold; a corrupt decoy at the fallback proves the canonical dir
    was read first.
    """
    fixture = _migrate_fixture(tmp_path, monkeypatch, session="g7-marker-canonical")
    spec_path = fixture["spec_path"]
    runtime = fixture["runtime"]
    canonical_bytes = _write_cloud_marker(
        tmp_path / "canonical-layout",
        spec_path,
        session="g7-marker-canonical",
        plan="c1-plan",
        runtime=runtime,
    ).read_bytes()
    # Decoy: the project-relative fallback holds a corrupt marker.
    fixture["marker_path"].write_text("{ not json", encoding="utf-8")
    monkeypatch.delenv("ARNOLD_CHAIN_SESSION_MARKER_DIR", raising=False)

    canonical_probe = (
        Path("/workspace/.megaplan/cloud-sessions") / "g7-marker-canonical.json"
    )
    real_exists = Path.exists
    real_read_bytes = Path.read_bytes

    def _fake_exists(self: Path) -> bool:
        return self == canonical_probe or real_exists(self)

    def _fake_read_bytes(self: Path) -> bytes:
        if self == canonical_probe:
            return canonical_bytes
        return real_read_bytes(self)

    monkeypatch.setattr(Path, "exists", _fake_exists)
    monkeypatch.setattr(Path, "read_bytes", _fake_read_bytes)

    result = migrate_execution_binding(
        spec_path,
        tmp_path,
        expected_current_milestone="c1",
        expected_current_plan="c1-plan",
        expected_branch="canary-work",
        reason="canonical marker dir",
        actor="test-operator",
        verified_external_runtime_identity=runtime,
    )
    assert result["engine_root"] == str(Path(runtime["import_root"]).resolve())


def test_execution_binding_migrate_project_relative_marker_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G7: when neither the env override nor the canonical workspace marker
    dir holds the marker, the project-relative .megaplan/cloud-sessions
    fallback (the rehearsal's tmp layout) still resolves it.
    """
    monkeypatch.delenv("ARNOLD_CHAIN_SESSION_MARKER_DIR", raising=False)
    fixture = _migrate_fixture(tmp_path, monkeypatch, session="g7-marker-fallback")
    spec_path = fixture["spec_path"]
    runtime = fixture["runtime"]

    result = migrate_execution_binding(
        spec_path,
        tmp_path,
        expected_current_milestone="c1",
        expected_current_plan="c1-plan",
        expected_branch="canary-work",
        reason="project-relative marker fallback",
        actor="test-operator",
        verified_external_runtime_identity=runtime,
    )
    assert result["engine_root"] == str(Path(runtime["import_root"]).resolve())


def test_execution_binding_migrate_refuses_missing_marker_zero_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G7 negative: with the marker NOWHERE (no env override, no canonical
    workspace marker, no project-relative fallback) migrate refuses with the
    missing-marker guard and mutates nothing.
    """
    monkeypatch.delenv("ARNOLD_CHAIN_SESSION_MARKER_DIR", raising=False)
    fixture = _migrate_fixture(tmp_path, monkeypatch, session="g7-marker-missing")
    spec_path = fixture["spec_path"]
    fixture["marker_path"].unlink()
    state_bytes = _state_path_for(spec_path).read_bytes()
    manifest_bytes = fixture["manifest_path"].read_bytes()
    plan_bytes = fixture["plan_path"].read_bytes()

    with pytest.raises(CliError, match="cloud-session marker is missing"):
        migrate_execution_binding(
            spec_path,
            tmp_path,
            expected_current_milestone="c1",
            expected_current_plan="c1-plan",
            expected_branch="canary-work",
            reason="missing marker guard",
            actor="test-operator",
            verified_external_runtime_identity=fixture["runtime"],
        )
    assert _state_path_for(spec_path).read_bytes() == state_bytes
    assert fixture["manifest_path"].read_bytes() == manifest_bytes
    assert fixture["plan_path"].read_bytes() == plan_bytes


def test_b_cli_execution_binding_migrate_initializes_binding_via_command(
    tmp_path: Path,
    offline_rollback_runtime: dict[str, Path | str],
) -> None:
    spec_path = _pinned_chain(tmp_path, ("c1", "c2", "c3"))
    _git(tmp_path, "checkout", "-b", "canary-work")
    identity = json.loads(
        Path(offline_rollback_runtime["identity"]).read_text(encoding="utf-8")
    )
    runtime_root = Path(identity["import_root"]).resolve()
    revision = identity["source_revision"]

    _paused_unbound_state(
        spec_path,
        plan="c1-plan",
        session="canary-session",
    )
    plan_path = _write_plan_state(tmp_path, "c1-plan")
    marker_path = _write_cloud_marker(
        tmp_path,
        spec_path,
        session="canary-session",
        plan="c1-plan",
        runtime=identity,
    )
    manifest_path = _write_runtime_manifest(
        tmp_path / "runtime-manifest.json",
        epic_id="demo",
        runtime_root=runtime_root,
        expected_head=revision,
    )
    state_bytes = _state_path_for(spec_path).read_bytes()
    marker_bytes = marker_path.read_bytes()
    manifest_bytes = manifest_path.read_bytes()
    plan_bytes = plan_path.read_bytes()

    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONPATH", "PYTHONHOME"}
    }
    env["ARNOLD_RUNTIME_MANIFEST"] = str(manifest_path)
    command = subprocess.run(
        [
            sys.executable,
            "-P",
            "-m",
            "arnold_pipelines.megaplan",
            "chain",
            "execution-binding-migrate",
            "--spec",
            str(spec_path),
            "--project-dir",
            str(tmp_path),
            "--old-runtime-identity",
            str(offline_rollback_runtime["identity"]),
            "--old-runtime-provenance-receipt",
            str(offline_rollback_runtime["receipt"]),
            "--expected-current-milestone",
            "c1",
            "--expected-current-plan",
            "c1-plan",
            "--expected-branch",
            "canary-work",
            "--reason",
            "bind independently receipted legacy runtime",
            "--actor",
            "test-operator",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert command.returncode == 0, command.stderr
    payload = json.loads(command.stdout)
    assert payload["success"] is True
    assert payload["action"] == "execution-binding-migrate"
    assert payload["old_runtime_sha256"] == identity["content_sha256"]
    assert payload["engine_root"] == str(runtime_root)
    assert payload["verification_mode"] == "external_interpreter_receipt"
    assert payload["runtime_binding"]["status"] in {"match", "not_required"}
    assert (
        payload["runtime_binding"]["expected"]["content_sha256"]
        == identity["content_sha256"]
    )

    after = load_chain_state(spec_path)
    binding = after.metadata["execution_binding"]
    assert binding["runtime_binding"]["current_identity"] == identity
    assert binding["launched_identity"]["runtime"] == identity
    assert binding["runtime_binding"]["rebind_events"] == []
    assert after.metadata["execution_environment"]["engine_root"] == str(
        runtime_root
    )
    assert _state_path_for(spec_path).read_bytes() != state_bytes
    assert marker_path.read_bytes() == marker_bytes
    assert manifest_path.read_bytes() == manifest_bytes
    assert plan_path.read_bytes() == plan_bytes


def test_b_cli_execution_binding_migrate_refuses_forged_receipt_zero_mutation(
    tmp_path: Path,
    offline_rollback_runtime: dict[str, Path | str],
) -> None:
    spec_path = _pinned_chain(tmp_path, ("c1", "c2", "c3"))
    _git(tmp_path, "checkout", "-b", "canary-work")
    identity = json.loads(
        Path(offline_rollback_runtime["identity"]).read_text(encoding="utf-8")
    )
    _paused_unbound_state(
        spec_path,
        plan="c1-plan",
        session="canary-session",
    )
    _write_plan_state(tmp_path, "c1-plan")
    _write_cloud_marker(
        tmp_path,
        spec_path,
        session="canary-session",
        plan="c1-plan",
        runtime=identity,
    )
    manifest_path = _write_runtime_manifest(
        tmp_path / "runtime-manifest.json",
        epic_id="demo",
        runtime_root=Path(identity["import_root"]).resolve(),
        expected_head=identity["source_revision"],
    )
    forged_receipt = tmp_path / "forged-receipt.json"
    receipt = json.loads(
        Path(offline_rollback_runtime["receipt"]).read_text(encoding="utf-8")
    )
    receipt["content_sha256"] = "f" * 64
    forged_receipt.write_text(json.dumps(receipt), encoding="utf-8")
    state_bytes = _state_path_for(spec_path).read_bytes()

    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONPATH", "PYTHONHOME"}
    }
    env["ARNOLD_RUNTIME_MANIFEST"] = str(manifest_path)
    command = subprocess.run(
        [
            sys.executable,
            "-P",
            "-m",
            "arnold_pipelines.megaplan",
            "chain",
            "execution-binding-migrate",
            "--spec",
            str(spec_path),
            "--project-dir",
            str(tmp_path),
            "--old-runtime-identity",
            str(offline_rollback_runtime["identity"]),
            "--old-runtime-provenance-receipt",
            str(forged_receipt),
            "--expected-current-milestone",
            "c1",
            "--expected-current-plan",
            "c1-plan",
            "--expected-branch",
            "canary-work",
            "--reason",
            "forged receipt",
            "--actor",
            "test-operator",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert command.returncode != 0
    payload = json.loads(command.stdout)
    assert payload["success"] is False
    assert payload["error"] == "chain_runtime_binding_drift"
    assert _state_path_for(spec_path).read_bytes() == state_bytes
