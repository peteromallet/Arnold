from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic import ValidationError

from arnold_pipelines.megaplan.resident.cloud import CloudToolRequest, CloudToolResult
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.profile import MegaplanResidentProfile
from arnold_pipelines.megaplan.store import FileStore


class FakeCloudBackend:
    def __init__(self) -> None:
        self.requests: list[CloudToolRequest] = []

    async def run(self, request: CloudToolRequest) -> CloudToolResult:
        self.requests.append(request)
        return CloudToolResult(
            classification="running",
            summary="cloud_status_chain: active chain running",
            details={"payload": {"active_cloud_chains": 1}},
        )


def test_megaplan_resident_tool_catalog_exposes_initiatives_policy(tmp_path: Path) -> None:
    profile = MegaplanResidentProfile(store=FileStore(tmp_path / "store"))

    names = {tool.name for tool in profile.tools().list()}

    assert {
        "list_initiatives",
        "search_initiatives",
        "create_initiative",
        "read_initiative",
        "write_initiative_doc",
        "classify_initiative_doc",
        "migrate_initiative_layout",
    }.issubset(names)
    prompt = profile.system_prompt()
    assert ".megaplan/initiatives/<slug>/" in prompt
    assert "Never create planning docs directly under .megaplan/briefs" in prompt
    assert "search initiatives by rough slug/title/description first" in prompt


def test_megaplan_resident_write_initiative_doc_creates_canonical_folder(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    profile = MegaplanResidentProfile(store=FileStore(tmp_path / "store"))
    tool = profile.tools().get("write_initiative_doc")

    result = tool.handler(
        tool.input_model(
            project_root=str(project),
            initiative_slug="Project Alpha",
            doc_kind="research",
            filename="notes.md",
            content_text="# Notes\n",
        )
    )

    assert result.ok is True
    path = project / ".megaplan" / "initiatives" / "project-alpha" / "research" / "notes.md"
    assert path.read_text(encoding="utf-8") == "# Notes\n"
    assert not (project / ".megaplan" / "briefs").exists()


def test_megaplan_resident_create_initiative_writes_description_metadata(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    profile = MegaplanResidentProfile(store=FileStore(tmp_path / "store"))
    tool = profile.tools().get("create_initiative")

    result = tool.handler(
        tool.input_model(
            project_root=str(project),
            slug="Discord Context",
            title="Discord Context",
            description="Classify worker messages and preserve initiative structure.",
            create_chain=True,
        )
    )

    assert result.ok is True
    initiative = result.data["initiative"]
    assert initiative["slug"] == "discord-context"
    assert initiative["description"] == "Classify worker messages and preserve initiative structure."
    root = project / ".megaplan" / "initiatives" / "discord-context"
    assert (root / "README.md").read_text(encoding="utf-8") == (
        "# Discord Context\n\n"
        "Classify worker messages and preserve initiative structure.\n"
    )
    assert (root / "chain.yaml").exists()


def test_megaplan_resident_create_initiative_requires_description(tmp_path: Path) -> None:
    profile = MegaplanResidentProfile(store=FileStore(tmp_path / "store"))
    tool = profile.tools().get("create_initiative")

    with pytest.raises(ValidationError):
        tool.input_model(project_root=str(tmp_path), slug="No Description")


def test_megaplan_resident_search_initiatives_uses_fuzzy_title_description(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    profile = MegaplanResidentProfile(store=FileStore(tmp_path / "store"))
    create = profile.tools().get("create_initiative")
    search = profile.tools().get("search_initiatives")

    create.handler(
        create.input_model(
            project_root=str(project),
            slug="Discord Context",
            title="Discord Context",
            description="Classify worker messages and preserve initiative structure.",
        )
    )
    create.handler(
        create.input_model(
            project_root=str(project),
            slug="Cloud Agents",
            title="Cloud Agents",
            description="Remote execution and worker routing.",
        )
    )

    result = search.handler(
        search.input_model(
            project_root=str(project),
            query="discrod struture",
            keywords_all=True,
        )
    )

    assert result.ok is True
    assert [item["slug"] for item in result.data["initiatives"]] == ["discord-context"]
    assert result.data["initiatives"][0]["matched_terms"] == ["discrod", "struture"]


def test_megaplan_resident_hot_context_includes_compact_initiative_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    store = FileStore(tmp_path / "store")
    profile = MegaplanResidentProfile(store=store)
    create = profile.tools().get("create_initiative")
    create.handler(
        create.input_model(
            project_root=str(project),
            slug="Discord Context",
            title="Discord Context",
            description="Classify worker messages and preserve initiative structure with enough detail to trim.",
            create_chain=True,
        )
    )
    monkeypatch.chdir(project)

    context = asyncio.run(profile.load_hot_context("missing-conversation"))

    assert len(context["initiative_index"]) == 1
    row = context["initiative_index"][0]
    assert row["slug"] == "discord-context"
    assert row["title"] == "Discord Context"
    assert row["description"] == "Classify worker messages and preserve initiative structure with enough detail to trim."
    assert row["chain"] is True
    assert {"README.md", "chain.yaml"}.issubset(set(row["recent_docs"]))


def test_megaplan_resident_hot_context_includes_live_cloud_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "cloud.active.yaml").write_text("provider: local\n", encoding="utf-8")
    backend = FakeCloudBackend()
    profile = MegaplanResidentProfile(
        store=FileStore(tmp_path / "store"),
        config=ResidentConfig(cloud_yaml_path=Path("cloud.active.yaml")),
        cloud_backend=backend,
    )
    monkeypatch.chdir(project)

    context = asyncio.run(profile.load_hot_context("missing-conversation"))

    assert context["configured_cloud_yaml"] == "cloud.active.yaml"
    assert context["resident_runtime"]["codex_sandbox"] == "workspace-write"
    assert context["live_cloud_chain"]["available"] is True
    assert context["live_cloud_chain"]["classification"] == "running"
    assert backend.requests[0].operation == "cloud_status_chain"
    assert backend.requests[0].arguments["cloud_yaml"] == "cloud.active.yaml"


def test_megaplan_resident_hot_context_includes_local_epic_chain_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    epic_state_dir = project / ".megaplan" / "plans" / ".epic_chains"
    chain_state_dir = project / "initiative" / ".megaplan" / "plans" / ".chains"
    plan_dir = project / ".megaplan" / "plans" / "m1-demo"
    epic_state_dir.mkdir(parents=True)
    chain_state_dir.mkdir(parents=True)
    plan_dir.mkdir(parents=True)
    (epic_state_dir / "epic-chain-demo.json").write_text(
        '{"current_epic_id":"native-python","current_epic_index":0,"last_state":"running","completed":[]}',
        encoding="utf-8",
    )
    (chain_state_dir / "chain-demo.json").write_text(
        (
            '{"current_plan_name":"m1-demo","current_milestone_index":0,'
            '"last_state":"awaiting_human_verify","completed":[],'
            '"metadata":{"chain_spec_path":"chain.yaml",'
            '"execution_environment":{"work_dir":"%s"}}}'
        )
        % str(project),
        encoding="utf-8",
    )
    (plan_dir / "state.json").write_text(
        '{"current_state":"initialized","iteration":0,"active_step":null}',
        encoding="utf-8",
    )
    monkeypatch.chdir(project)
    profile = MegaplanResidentProfile(
        store=FileStore(tmp_path / "store"),
        config=ResidentConfig(cloud_yaml_path=Path("missing-cloud.yaml")),
    )

    context = asyncio.run(profile.load_hot_context("missing-conversation"))

    local_state = context["local_epic_chain_state"]
    assert local_state["epic_chains"][0]["current_epic_id"] == "native-python"
    assert local_state["active_chains"][0]["current_plan_name"] == "m1-demo"
    assert local_state["active_chains"][0]["plan_state"]["current_state"] == "initialized"


def test_megaplan_resident_hot_context_prefers_cloud_status_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Broad-status context carries the canonical snapshot, labeled degraded when absent."""
    import json
    from datetime import datetime, timezone

    project = tmp_path / "project"
    project.mkdir()
    snapshot_path = tmp_path / "cloud-status.json"
    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": "cloud-local-observer",
        "summary": {"running": 1, "blocked": 0, "repairing": 0, "complete": 0, "attention": 0},
        "sessions": [
            {
                "session": "demo",
                "status": "running",
                "current_plan": "m1",
                "operator_next": "executing",
                "latest_activity": "2026-07-04T22:00:00Z",
            }
        ],
        "degraded": None,
    }
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    profile = MegaplanResidentProfile(
        store=FileStore(tmp_path / "store"),
        config=ResidentConfig(status_snapshot_path=snapshot_path),
        cloud_backend=FakeCloudBackend(),
    )
    monkeypatch.chdir(project)

    context = asyncio.run(profile.load_hot_context("missing-conversation"))

    assert context["cloud_status_snapshot"] is not None
    assert context["cloud_status_snapshot"]["summary"]["running"] == 1
    assert context["cloud_status_degraded"] is None
    summary = context["plan_activity_summary"]
    assert summary["degraded"] is False
    assert [e["session"] for e in summary["active_working"]] == ["demo"]


def test_megaplan_resident_hot_context_labels_missing_snapshot_degraded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    profile = MegaplanResidentProfile(
        store=FileStore(tmp_path / "store"),
        config=ResidentConfig(status_snapshot_path=tmp_path / "absent.json"),
        cloud_backend=FakeCloudBackend(),
    )
    monkeypatch.chdir(project)

    context = asyncio.run(profile.load_hot_context("missing-conversation"))

    assert context["cloud_status_snapshot"] is None
    assert context["cloud_status_degraded"] is not None
    assert "missing" in context["cloud_status_degraded"]
    assert context["plan_activity_summary"]["degraded"] is True


def test_megaplan_resident_hot_context_builds_fresh_snapshot_in_trusted_container(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In-container, the resident builds a fresh local snapshot each turn instead
    of reading the (stale, hourly) on-disk file, so newly-started sessions appear
    immediately and the on-disk file is refreshed."""
    import json
    from arnold_pipelines.megaplan.cloud import status_snapshot

    marker_dir = tmp_path / "cloud-sessions"
    marker_dir.mkdir()
    ws = tmp_path / "live"
    ws.mkdir()
    (marker_dir / "live.json").write_text(
        json.dumps(
            {
                "session": "live",
                "workspace": str(ws),
                "remote_spec": "/spec/live",
                "started_at": "2026-07-04T20:00:00Z",
                "run_kind": "chain",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MEGAPLAN_TRUSTED_CONTAINER", "1")
    monkeypatch.setattr(status_snapshot, "DEFAULT_MARKER_DIR", marker_dir)
    monkeypatch.setattr(status_snapshot, "DEFAULT_WATCHDOG_REPORT", tmp_path / "absent-report.json")
    on_disk = tmp_path / "cloud-status.json"

    profile = MegaplanResidentProfile(
        store=FileStore(tmp_path / "store"),
        # Points at a nonexistent file; in-container it must be ignored in favor of a fresh build.
        config=ResidentConfig(status_snapshot_path=on_disk),
        cloud_backend=FakeCloudBackend(),
    )
    monkeypatch.chdir(tmp_path)

    context = asyncio.run(profile.load_hot_context("c"))

    snap = context["cloud_status_snapshot"]
    assert snap is not None
    assert context["cloud_status_degraded"] is None
    assert any(s["session"] == "live" for s in snap["sessions"])
    # The fresh build also refreshed the on-disk file for CLI/laptop consumers.
    assert on_disk.exists()
    written = json.loads(on_disk.read_text(encoding="utf-8"))
    assert any(s["session"] == "live" for s in written["sessions"])


def test_megaplan_resident_hot_context_builds_fresh_with_markers_without_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P0: marker-dir presence (not the trust env var) triggers a fresh build, so
    a resident that lost MEGAPLAN_TRUSTED_CONTAINER on a manual restart still
    serves live per-turn data. Without the env var it must NOT clobber the shared
    cache."""
    import json
    from arnold_pipelines.megaplan.cloud import status_snapshot

    marker_dir = tmp_path / "cloud-sessions"
    marker_dir.mkdir()
    ws = tmp_path / "live"
    ws.mkdir()
    (marker_dir / "live.json").write_text(
        json.dumps(
            {
                "session": "live",
                "workspace": str(ws),
                "remote_spec": "/spec/live",
                "started_at": "2026-07-04T20:00:00Z",
                "run_kind": "chain",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("MEGAPLAN_TRUSTED_CONTAINER", raising=False)
    monkeypatch.setattr(status_snapshot, "DEFAULT_MARKER_DIR", marker_dir)
    monkeypatch.setattr(status_snapshot, "DEFAULT_WATCHDOG_REPORT", tmp_path / "absent-report.json")
    on_disk = tmp_path / "cloud-status.json"

    profile = MegaplanResidentProfile(
        store=FileStore(tmp_path / "store"),
        config=ResidentConfig(status_snapshot_path=on_disk),
        cloud_backend=FakeCloudBackend(),
    )
    monkeypatch.chdir(tmp_path)

    context = asyncio.run(profile.load_hot_context("c"))

    snap = context["cloud_status_snapshot"]
    assert snap is not None
    assert context["cloud_status_degraded"] is None
    # Fresh build reflects the live marker even without the trust env var...
    assert any(s["session"] == "live" for s in snap["sessions"])
    # ...visibility reports the actual trust/marker state.
    assert context["resident_runtime"]["has_local_markers"] is True
    assert context["resident_runtime"]["trusted_container"] is False
    # Without the trust env var, the shared cache must NOT be written.
    assert not on_disk.exists()


def test_megaplan_resident_hot_context_sanitizes_stale_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P1: a present-but-stale cache snapshot is sanitized — sessions/summary
    stripped and a stale_banner attached — so the resident cannot cite frozen
    numbers as authoritative, and plan_activity_summary marks it degraded."""
    import json
    from datetime import datetime, timedelta, timezone
    from arnold_pipelines.megaplan.cloud import status_snapshot

    project = tmp_path / "project"
    project.mkdir()
    old = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat().replace("+00:00", "Z")
    snapshot_path = tmp_path / "cloud-status.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "generated_at": old,
                "source": "cloud-local-observer",
                "summary": {"running": 1, "blocked": 0, "repairing": 0, "complete": 0, "attention": 0},
                "sessions": [{"session": "frozen", "status": "running", "current_plan": "m1"}],
                "degraded": None,
            }
        ),
        encoding="utf-8",
    )
    # No marker dir on a laptop/CLI host -> cache-read path is taken.
    monkeypatch.setattr(status_snapshot, "DEFAULT_MARKER_DIR", tmp_path / "no-cloud-sessions")

    profile = MegaplanResidentProfile(
        store=FileStore(tmp_path / "store"),
        config=ResidentConfig(status_snapshot_path=snapshot_path),
        cloud_backend=FakeCloudBackend(),
    )
    monkeypatch.chdir(project)

    context = asyncio.run(profile.load_hot_context("c"))

    snap = context["cloud_status_snapshot"]
    assert snap is not None
    assert snap["sessions"] == []                # stale numbers withheld
    assert snap["summary"]["running"] == 0
    assert snap["stale_banner"]
    assert "WATCHDOG STALE" in snap["stale_banner"]
    assert context["cloud_status_degraded"] is not None
    assert context["plan_activity_summary"]["degraded"] is True
