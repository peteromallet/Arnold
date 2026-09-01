from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from agentbox.tmux import SessionStatus
from arnold_pipelines.megaplan.cloud import chain_drive


def test_dead_existing_chain_drive_operation_reclaims_same_operation(
    tmp_path: Path, monkeypatch
) -> None:
    operation_id = "megaplan-chain-drive-dead-session"
    dead_resource = SimpleNamespace(
        id=f"{operation_id}:process-session",
        operation_id=operation_id,
        resource_type=chain_drive.ResourceType.PROCESS_SESSION,
        name="dead-session",
        details={},
    )
    replacement_resource = SimpleNamespace(
        id=f"{operation_id}:process-session:retry-1",
        operation_id=operation_id,
        resource_type=chain_drive.ResourceType.PROCESS_SESSION,
        name="replacement-session",
        details={"state": "running"},
    )
    operation = SimpleNamespace(id=operation_id)
    store = SimpleNamespace(
        list_typed_resources=lambda _operation: (dead_resource,),
    )
    prepared = object()
    started = SimpleNamespace(process_session_resource=replacement_resource)

    monkeypatch.setattr(chain_drive, "_operation_id", lambda _key: operation_id)
    monkeypatch.setattr(chain_drive, "load_agentbox_config", lambda: object())
    monkeypatch.setattr(chain_drive, "load_agentbox_operation", lambda *_args, **_kwargs: operation)
    monkeypatch.setattr(chain_drive, "open_operation_store", lambda _config: store)
    monkeypatch.setattr(
        chain_drive,
        "inspect_session",
        lambda _name: SessionStatus(
            session_name="dead-session", state="dead", exists=False
        ),
    )
    monkeypatch.setattr(
        chain_drive, "prepare_host_resources", lambda *_args, **_kwargs: prepared
    )
    captured: dict[str, object] = {}

    def fake_start(*_args, **kwargs):
        captured.update(kwargs)
        return started

    monkeypatch.setattr(chain_drive, "start_host_session", fake_start)

    spec = tmp_path / "chain.yaml"
    manifest = tmp_path / "manifest.json"
    receipt = tmp_path / "receipt.json"
    canonical_log = tmp_path / "chain.log"
    spec.write_text("spec\n", encoding="utf-8")
    manifest.write_text(
        '{"epic":{"expected_head":"source"}}\n', encoding="utf-8"
    )

    payload = chain_drive.launch_chain_drive(
        session="native-build-forward",
        occurrence="4c0190500877",
        plan="native-c2-completion-binding-20260831-2100",
        workspace=tmp_path,
        spec=spec,
        engine_dir=tmp_path,
        interpreter=tmp_path / "python",
        manifest=manifest,
        receipt_path=receipt,
        canonical_log=canonical_log,
        one=True,
    )

    assert payload["operation_id"] == operation_id
    assert payload["process_resource_id"] == replacement_resource.id
    assert captured["process_resource_id"] == f"{operation_id}:process-session:retry-1"
    assert receipt.exists()
