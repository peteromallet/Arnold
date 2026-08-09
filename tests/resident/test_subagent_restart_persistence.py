from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan.resident import subagent
from arnold_pipelines.megaplan.resident.provenance import DELEGATION_CONTEXT_ENV


class _Supervisor:
    pid = 4242


def _non_discord_provenance() -> dict[str, object]:
    return {
        "schema_version": "arnold-resident-delegation-provenance-v1",
        "applicability": "not_applicable",
        "transport": "non_discord",
        "source_kind": "explicit_non_discord",
    }


def test_queued_successor_persists_across_later_scheduler_sweep(
    tmp_path: Path, monkeypatch
) -> None:
    """A successor launch claim is reconstructed from durable manifests only."""

    monkeypatch.delenv(DELEGATION_CONTEXT_ENV, raising=False)
    monkeypatch.setattr(
        subagent.subprocess, "Popen", lambda *args, **kwargs: _Supervisor()
    )
    provenance = _non_discord_provenance()
    predecessor = subagent.launch_codex_subagent_detached(
        task="Prepare durable predecessor evidence.",
        description="Prepare predecessor evidence",
        project_dir=str(tmp_path),
        launch_origin=provenance,
    )
    predecessor_path = Path(predecessor.manifest_path)
    predecessor_manifest = json.loads(predecessor_path.read_text(encoding="utf-8"))
    predecessor_manifest.update(
        {
            "status": "completed",
            "terminal_outcome": "completed",
            "returncode": 0,
        }
    )
    Path(predecessor_manifest["result_path"]).write_text(
        "Durable predecessor result.", encoding="utf-8"
    )
    predecessor_path.write_text(json.dumps(predecessor_manifest), encoding="utf-8")

    successor = subagent.launch_codex_subagent_detached(
        task="Verify the predecessor after a resident restart.",
        description="Verify durable predecessor evidence",
        project_dir=str(tmp_path),
        launch_origin=provenance,
        depends_on_run_id=predecessor.run_id,
    )
    successor_path = Path(successor.manifest_path)
    launches: list[Path] = []

    def launch(path: Path, manifest: dict[str, object]):
        launches.append(path)
        running = json.loads(path.read_text(encoding="utf-8"))
        running.update({"status": "running", "pid": _Supervisor.pid})
        running["queue"].update({"state": "running", "attention": "none"})
        path.write_text(json.dumps(running), encoding="utf-8")
        return _Supervisor(), running

    monkeypatch.setattr(subagent, "_spawn_managed_supervisor", launch)
    monkeypatch.setattr(
        subagent, "_pid_matches_manifest", lambda pid, path: pid == _Supervisor.pid
    )
    recovered = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path, workspace_root=None
    )
    replay = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path, workspace_root=None
    )

    persisted = json.loads(successor_path.read_text(encoding="utf-8"))
    assert recovered.launched == 1
    assert replay.launched == 0
    assert launches == [successor_path]
    assert persisted["status"] == "running"
    assert persisted["queue"]["attempt_count"] == 1
