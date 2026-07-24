from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from arnold_pipelines.megaplan.cloud import session_runtime
from arnold_pipelines.megaplan.cloud.runtime_cutover import normalize_runtime_identity
from arnold_pipelines.megaplan.types import CliError


def _identity(root: str = "/workspace/runtime-a") -> dict:
    return normalize_runtime_identity(
        {
            "import_root": root,
            "source_revision": "a" * 40,
            "editable_root": root,
            "editable_revision": "a" * 40,
            "direct_url": {
                "dir_info": {"editable": True},
                "url": f"file://{root}",
            },
            "pth": [
                {
                    "path": "/runtime-venv/site-packages/_editable_impl_arnold.pth",
                    "entries": [root],
                    "readable": True,
                }
            ],
            "imports": {
                "arnold": f"{root}/arnold/__init__.py",
                "arnold_pipelines": f"{root}/arnold_pipelines/__init__.py",
                "megaplan": f"{root}/arnold_pipelines/megaplan/__init__.py",
            },
        }
    )


def test_prepare_session_runtime_rebinds_seed_to_target_marker_and_spec(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "markers" / "critique.json"
    marker.parent.mkdir()
    marker.write_text(
        json.dumps(
            {
                "session": "critique",
                "workspace": str(tmp_path / "project"),
                "remote_spec": str(tmp_path / "project" / "chain.yaml"),
                "identity_digest": "critique-id",
                "run_kind": "chain",
                "relaunch_command": "launch critique",
            }
        )
        + "\n"
    )
    spec = tmp_path / "project" / "chain.yaml"
    spec.parent.mkdir()
    spec.write_text("driver:\n  execution_binding: required\n")
    supervisor_receipt = tmp_path / "supervisor.json"
    supervisor_receipt.write_text("{}\n")
    base_seed = tmp_path / "custody-seed.json"
    base_seed.write_text(
        json.dumps(
            {
                "expected_root": "/workspace/runtime-a",
                "expected_revision": "a" * 40,
                "hot_env": {
                    "selectors": {
                        "MEGAPLAN_RUNTIME_SRC": "/workspace/runtime-a",
                        "MEGAPLAN_LAUNCH_RUNTIME_SRC": "/workspace/runtime-a",
                    }
                },
                "input_paths": {
                    "supervisor_receipt": str(supervisor_receipt),
                    "chain_spec": "/workspace/custody/chain.yaml",
                    "marker": "/workspace/markers/custody.json",
                },
            }
        )
        + "\n"
    )
    state = SimpleNamespace(metadata={})
    monkeypatch.setattr(
        session_runtime, "binding_policy", lambda _path: {"required": True}
    )
    monkeypatch.setattr(
        session_runtime.chain_spec,
        "load_chain_state",
        lambda *_args, **_kwargs: state,
    )
    saved: list[tuple[Path, object]] = []
    monkeypatch.setattr(
        session_runtime.chain_spec,
        "save_chain_state",
        lambda path, value: saved.append((path, value)),
    )
    monkeypatch.setattr(
        session_runtime, "bind_execution_identity", lambda *_args: None
    )
    monkeypatch.setattr(
        session_runtime,
        "execution_binding_report",
        lambda *_args: {
            "status": "match",
            "runtime_binding": {
                "required": True,
                "status": "match",
                "expected": _identity(),
                "active": _identity(),
            },
        },
    )
    validated: list[tuple[dict, str]] = []
    verified: list[dict] = []
    monkeypatch.setattr(
        session_runtime,
        "verify_runtime_launch_seed_document",
        lambda seed: verified.append(seed),
    )
    monkeypatch.setattr(
        session_runtime,
        "validate_runtime_launch_seed",
        lambda seed, *, component: validated.append((seed, component))
        or {"status": "ready"},
    )
    built: dict = {}

    def fake_build(**kwargs):
        built.update(kwargs)
        return {
            "expected_root": "/workspace/runtime-a",
            "expected_revision": "a" * 40,
            "content_sha256": "b" * 64,
            "ready": True,
            "errors": [],
        }

    monkeypatch.setattr(session_runtime, "build_runtime_launch_seed", fake_build)

    result = session_runtime.prepare_session_runtime(
        marker_path=marker,
        spec_path=spec,
        project_dir=spec.parent,
        base_seed_path=base_seed,
        output_dir=tmp_path / "runtime-sessions" / "critique",
    )

    updated_marker = json.loads(marker.read_text())
    env_text = Path(result["session_env"]).read_text()
    assert saved == [(spec.resolve(), state)]
    assert updated_marker["runtime_binding"]["current_identity"] == _identity()
    assert built["marker_path"] == marker.resolve()
    assert built["chain_spec_path"] == spec.resolve()
    assert built["hot_env_path"] == Path(result["session_env"])
    assert "MEGAPLAN_RUNTIME_LAUNCH_SEED=" in env_text
    assert str(Path(result["session_seed"])) in env_text
    assert "/workspace/custody/chain.yaml" not in env_text
    assert verified == [json.loads(base_seed.read_text())]
    assert len(validated) == 1


def test_successor_session_uses_admitted_runtime_and_matching_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_revision = "a" * 40
    new_revision = "b" * 40
    old_root = tmp_path / "runtime-old"
    new_root = tmp_path / "runtime-new"
    old_receipt = (
        tmp_path / "receipts" / old_revision / "supervisor-python" / "last-prepare.json"
    )
    new_receipt = (
        tmp_path / "receipts" / new_revision / "supervisor-python" / "last-prepare.json"
    )
    new_receipt.parent.mkdir(parents=True)
    supervisor_runtime = tmp_path / "supervisor-new"
    new_receipt.write_text(
        json.dumps(
            {
                "source": str(new_root),
                "source_revision": new_revision,
                "runtime": str(supervisor_runtime),
                "status": "ready",
            }
        )
        + "\n"
    )
    base_seed = {
        "expected_root": str(old_root),
        "expected_revision": old_revision,
        "hot_env": {
            "selectors": {
                "MEGAPLAN_RUNTIME_SRC": str(old_root),
                "MEGAPLAN_SUPERVISOR_SOURCE": str(old_root),
            }
        },
        "input_paths": {"supervisor_receipt": str(old_receipt)},
    }
    identity = _identity(str(new_root))
    identity["source_revision"] = new_revision
    identity["editable_revision"] = new_revision
    identity = normalize_runtime_identity(identity)

    root, revision, receipt, selectors = (
        session_runtime._release_inputs_for_runtime(base_seed, identity)
    )

    assert root == new_root.resolve()
    assert revision == new_revision
    assert receipt == new_receipt.resolve()
    assert selectors["MEGAPLAN_RUNTIME_SRC"] == str(new_root.resolve())
    assert selectors["MEGAPLAN_SUPERVISOR_SOURCE"] == str(new_root.resolve())
    assert selectors["MEGAPLAN_SUPERVISOR_PYTHON"] == str(
        supervisor_runtime.resolve() / "bin" / "python3"
    )
    assert str(old_root) not in set(selectors.values())


def test_successor_session_rejects_foreign_supervisor_receipt(
    tmp_path: Path,
) -> None:
    old_revision = "a" * 40
    new_revision = "b" * 40
    old_receipt = (
        tmp_path / "receipts" / old_revision / "supervisor-python" / "last-prepare.json"
    )
    new_receipt = (
        tmp_path / "receipts" / new_revision / "supervisor-python" / "last-prepare.json"
    )
    new_receipt.parent.mkdir(parents=True)
    new_receipt.write_text(
        json.dumps(
            {
                "source": str(tmp_path / "wrong-runtime"),
                "source_revision": new_revision,
                "runtime": str(tmp_path / "supervisor"),
                "status": "ready",
            }
        )
        + "\n"
    )
    base_seed = {
        "expected_root": str(tmp_path / "runtime-old"),
        "expected_revision": old_revision,
        "hot_env": {"selectors": {}},
        "input_paths": {"supervisor_receipt": str(old_receipt)},
    }
    identity = _identity(str(tmp_path / "runtime-new"))
    identity["source_revision"] = new_revision
    identity["editable_revision"] = new_revision
    identity = normalize_runtime_identity(identity)

    with pytest.raises(CliError, match="no ready supervisor receipt matches"):
        session_runtime._release_inputs_for_runtime(base_seed, identity)


def test_prepared_runtime_identity_accepts_not_required_runtime_match_policy() -> None:
    identity = _identity()

    assert session_runtime._prepared_runtime_identity(
        {
            "status": "match",
            "runtime_binding": {
                "required": False,
                "status": "not_required",
                "expected": identity,
                "active": identity,
            },
        }
    ) == identity


@pytest.mark.parametrize(
    "report",
    [
        {
            "status": "drift",
            "runtime_binding": {
                "required": False,
                "status": "not_required",
                "expected": _identity(),
            },
        },
        {
            "status": "match",
            "runtime_binding": {
                "required": True,
                "status": "not_required",
                "expected": _identity(),
            },
        },
        {
            "status": "match",
            "runtime_binding": {
                "required": False,
                "status": "drift",
                "expected": _identity(),
                "active": _identity(),
            },
        },
        {
            "status": "match",
            "runtime_binding": {
                "required": False,
                "status": "not_required",
                "expected": None,
                "active": None,
            },
        },
        {
            "status": "match",
            "runtime_binding": {
                "required": False,
                "status": "not_required",
                "expected": _identity("/workspace/runtime-a"),
                "active": _identity("/workspace/runtime-b"),
            },
        },
    ],
)
def test_prepared_runtime_identity_rejects_drift_or_invalid_not_required(
    report: dict,
) -> None:
    with pytest.raises(CliError, match="not ready|drifted"):
        session_runtime._prepared_runtime_identity(report)


def test_session_marker_refuses_foreign_runtime(tmp_path: Path) -> None:
    marker = tmp_path / "marker.json"
    marker.write_text(
        json.dumps(
            {
                "workspace": str(tmp_path),
                "remote_spec": str(tmp_path / "chain.yaml"),
                "runtime_binding": {
                    "current_identity": _identity("/workspace/custody-runtime")
                }
            }
        )
        + "\n"
    )

    with pytest.raises(CliError, match="different runtime"):
        session_runtime._bind_marker_runtime(
            marker,
            spec_path=tmp_path / "chain.yaml",
            project_dir=tmp_path,
            runtime_identity=_identity("/workspace/critique-runtime"),
        )


def test_session_marker_refuses_foreign_workspace_or_spec(tmp_path: Path) -> None:
    marker = tmp_path / "marker.json"
    marker.write_text(
        json.dumps(
            {
                "workspace": str(tmp_path / "custody"),
                "remote_spec": str(tmp_path / "custody" / "chain.yaml"),
            }
        )
        + "\n"
    )

    with pytest.raises(CliError, match="does not own"):
        session_runtime._bind_marker_runtime(
            marker,
            spec_path=(tmp_path / "critique" / "chain.yaml").resolve(),
            project_dir=(tmp_path / "critique").resolve(),
            runtime_identity=_identity(),
        )
