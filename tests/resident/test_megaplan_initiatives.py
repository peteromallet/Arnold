from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from arnold_pipelines.megaplan.resident.cloud import CloudToolRequest, CloudToolResult
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.profile import (
    MegaplanResidentProfile,
    _compact_restart_lifecycle,
)
from arnold_pipelines.megaplan.store import FileStore, ResidentConversationInput


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


def test_restart_lifecycle_compacts_real_listing_shape() -> None:
    compact = _compact_restart_lifecycle(
        {
            "count": 17,
            "records": [
                {
                    "notification_id": "reset-one",
                    "initiator": {"source_record_id": "msg-source"},
                    "restart": {
                        "status": "succeeded",
                        "requested_at": "2026-07-13T19:07:55Z",
                        "completed_at": "2026-07-13T19:08:00Z",
                    },
                    "delivery": {
                        "status": "delivered",
                        "delivered_at": "2026-07-13T19:08:01Z",
                    },
                }
            ],
        }
    )

    assert compact["record_count"] == 17
    assert compact["latest"] == [
        {
            "reset_id": "reset-one",
            "restart_status": "succeeded",
            "delivery_status": "delivered",
            "requested_at": "2026-07-13T19:07:55Z",
            "completed_at": "2026-07-13T19:08:00Z",
            "delivered_at": "2026-07-13T19:08:01Z",
            "source_record_id": "msg-source",
        }
    ]


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
    assert "Default to `launch_subagent` for any user-requested execution work" in prompt
    assert "make that tool call before replying" in prompt
    assert "Do not babysit normal delegated work or Megaplan/cloud chains" in prompt
    assert "Babysitting should be exceptionally rare" in prompt
    assert "Use `progress.display_state` as its canonical status label" in prompt
    assert "falling back to `progress.plan_state` only when `display_state` is absent" in prompt
    assert "active execute step as `executing`" in prompt


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


def test_megaplan_resident_hot_context_identifies_complete_conversation_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    store_root = tmp_path / "resident-store"
    store = FileStore(store_root)
    conversation = store.upsert_resident_conversation(
        ResidentConversationInput(
            transport="discord",
            conversation_key="discord:dm:42",
            channel_id="1001",
            dm_user_id="42",
        )
    )
    store.create_message(
        epic_id=None,
        conversation_id=conversation.id,
        direction="inbound",
        content="older durable message outside a bounded prompt window",
        discord_message_id="123456789012345678",
    )
    profile = MegaplanResidentProfile(store=store)
    monkeypatch.chdir(project)

    context = asyncio.run(profile.load_hot_context(conversation.id))

    history = context["conversation_history"]
    assert history["conversation_id"] == conversation.id
    assert history["location"]["backend"] == "FileStore"
    assert history["location"]["store_root"] == str(store_root.resolve())
    assert history["location"]["conversation_record"] == str(
        store_root.resolve()
        / "resident_conversations"
        / f"{conversation.id}.json"
    )
    assert history["location"]["message_collection"] == str(
        store_root.resolve() / "messages"
    )
    assert history["location"]["message_selector"] == {
        "conversation_id": conversation.id
    }
    assert history["search"]["tool"] == "search_messages"
    assert history["search"]["arguments"]["conversation_id"] == conversation.id
    assert history["ordering_field"] == "sent_at"
    assert "not the full history" in history["hot_context_caveat"]
    assert "conversation_history" in profile.system_prompt()


def test_megaplan_resident_hot_context_surfaces_safe_restart_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    profile = MegaplanResidentProfile(store=FileStore(tmp_path / "store"))
    monkeypatch.chdir(project)

    context = asyncio.run(profile.load_hot_context("missing-conversation"))

    restart = context["resident_runtime"]["restart"]
    assert restart["canonical_command"] == (
        "agentbox services restart agentbox-discord-resident"
    )
    assert "KillMode" in restart["procedure"]
    assert "ExecStopPost" in restart["procedure"]
    assert "tmux pane" in restart["procedure"]
    assert "refuses" in restart["procedure"]
    assert "resident process/pane only" in restart["stop_scope"]
    assert any("subagents are not signaled" in item for item in restart["safety_guarantees"])
    assert any("Megaplan and cloud chains" in item for item in restart["safety_guarantees"])
    assert "in-flight Discord resident turn" in restart["operational_caveat"]
    assert "pkill/killall" in restart["forbidden_shortcuts"]

    prompt = profile.system_prompt()
    assert "use only the canonical command in hot context" in prompt
    assert "never use pkill, killall" in prompt


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
    assert "cloud chain" in context["cloud_launch_guidance"]["canonical_command"]
    assert "unique" in context["cloud_launch_guidance"]["requirements"]
    assert "--on-box" in context["cloud_launch_guidance"]["on_box_command"]
    assert "without SSH" in context["cloud_launch_guidance"]["transport_choice"]
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


def test_resident_hot_context_projects_live_execute_over_finalized_lifecycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    chain_state_dir = project / ".megaplan" / "plans" / ".chains"
    plan_dir = project / ".megaplan" / "plans" / "m1-live"
    chain_state_dir.mkdir(parents=True)
    plan_dir.mkdir(parents=True)
    (chain_state_dir / "chain-live.json").write_text(
        (
            '{"current_plan_name":"m1-live","current_milestone_index":0,'
            '"last_state":"running","completed":[],"metadata":{'
            '"chain_spec_path":"chain.yaml","execution_environment":{"work_dir":"%s"}}}'
        )
        % str(project),
        encoding="utf-8",
    )
    (plan_dir / "state.json").write_text(
        '{"current_state":"finalized","iteration":0,"active_step":{"phase":"execute"}}',
        encoding="utf-8",
    )
    monkeypatch.chdir(project)
    profile = MegaplanResidentProfile(
        store=FileStore(tmp_path / "store"),
        config=ResidentConfig(cloud_yaml_path=Path("missing-cloud.yaml")),
    )

    context = asyncio.run(profile.load_hot_context("missing-conversation"))
    chain = next(
        row
        for row in context["local_epic_chain_state"]["active_chains"]
        if row["current_plan_name"] == "m1-live"
    )
    state = chain["plan_state"]

    assert state["current_state"] == "finalized"
    assert state["active_phase"] == "execute"
    assert state["execution_state"] == "executing"
    assert state["display_state"] == "executing"


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
    # Force the cache-read path even when this test runs on the shared cloud
    # worker, where the real canonical marker directory exists.
    from arnold_pipelines.megaplan.cloud import status_snapshot

    monkeypatch.setattr(status_snapshot, "DEFAULT_MARKER_DIR", tmp_path / "no-cloud-sessions")
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


def test_hot_context_cannot_embed_oversized_cloud_repair_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json

    project = tmp_path / "project"
    project.mkdir()
    snapshot_path = tmp_path / "cloud-status.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "source": "cloud-local-observer",
                "summary": {"running": 1},
                "sessions": [
                    {
                        "session": "oversized-repair",
                        "status": "running",
                        "repair_custody": {"raw_history": "x" * 1_100_000},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    from arnold_pipelines.megaplan.cloud import status_snapshot

    monkeypatch.setattr(status_snapshot, "DEFAULT_MARKER_DIR", tmp_path / "no-markers")
    profile = MegaplanResidentProfile(
        store=FileStore(tmp_path / "store"),
        config=ResidentConfig(status_snapshot_path=snapshot_path),
        cloud_backend=FakeCloudBackend(),
    )
    monkeypatch.chdir(project)

    context = asyncio.run(profile.load_hot_context("missing-conversation"))
    serialized = json.dumps(context)

    assert len(serialized) < 100_000
    assert "raw_history" not in serialized
    assert context["cloud_status_snapshot"]["detail_node"] == "status"
    assert any(
        route.get("node_id") == "status"
        for route in context["context_root"]["routes"]
    )


def test_megaplan_resident_hot_context_labels_missing_snapshot_degraded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    from arnold_pipelines.megaplan.cloud import status_snapshot

    monkeypatch.setattr(status_snapshot, "DEFAULT_MARKER_DIR", tmp_path / "no-cloud-sessions")
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


def test_megaplan_resident_hot_context_uses_fallback_then_refreshes_in_background(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Projection rebuilding never blocks the inbound Discord turn."""
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
    monkeypatch.setattr(
        status_snapshot,
        "build_cloud_status_snapshot",
        lambda: {
            "generated_at": datetime.now(UTC).isoformat(),
            "source": "test-background-refresh",
            "summary": {"running": 1},
            "sessions": [{"session": "live", "status": "running"}],
        },
    )
    on_disk = tmp_path / "cloud-status.json"

    profile = MegaplanResidentProfile(
        store=FileStore(tmp_path / "store"),
        # The first turn gets a bounded missing-snapshot fallback while refresh runs.
        config=ResidentConfig(status_snapshot_path=on_disk),
        cloud_backend=FakeCloudBackend(),
    )
    monkeypatch.chdir(tmp_path)

    context = asyncio.run(profile.load_hot_context("c"))

    assert context["cloud_status_snapshot"] is None
    assert context["cloud_status_degraded"] is not None
    assert profile._snapshot_refresh_thread is not None
    profile._snapshot_refresh_thread.join(timeout=5)
    assert on_disk.exists()
    written = json.loads(on_disk.read_text(encoding="utf-8"))
    assert any(s["session"] == "live" for s in written["sessions"])
    refreshed = asyncio.run(profile.load_hot_context("c"))
    assert refreshed["cloud_status_snapshot"] is not None
    assert refreshed["cloud_status_degraded"] is None


def test_megaplan_resident_background_refresh_uses_markers_without_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Marker presence schedules refresh even when the trust env was lost."""
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
    monkeypatch.setattr(
        status_snapshot,
        "build_cloud_status_snapshot",
        lambda: {
            "generated_at": datetime.now(UTC).isoformat(),
            "source": "test-background-refresh",
            "summary": {"running": 1},
            "sessions": [{"session": "live", "status": "running"}],
        },
    )
    on_disk = tmp_path / "cloud-status.json"

    profile = MegaplanResidentProfile(
        store=FileStore(tmp_path / "store"),
        config=ResidentConfig(status_snapshot_path=on_disk),
        cloud_backend=FakeCloudBackend(),
    )
    monkeypatch.chdir(tmp_path)

    context = asyncio.run(profile.load_hot_context("c"))

    assert context["cloud_status_snapshot"] is None
    assert context["cloud_status_degraded"] is not None
    assert context["resident_runtime"]["has_local_markers"] is True
    assert context["resident_runtime"]["trusted_container"] is False
    assert profile._snapshot_refresh_thread is not None
    profile._snapshot_refresh_thread.join(timeout=5)
    assert on_disk.exists()


def test_megaplan_resident_hot_context_never_waits_for_projection_rebuild(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import threading
    import time
    from arnold_pipelines.megaplan.cloud import status_snapshot

    marker_dir = tmp_path / "cloud-sessions"
    marker_dir.mkdir()
    monkeypatch.setattr(status_snapshot, "DEFAULT_MARKER_DIR", marker_dir)
    started = threading.Event()
    release = threading.Event()

    def slow_build():
        started.set()
        release.wait(timeout=5)
        return {
            "generated_at": "2026-07-13T00:00:00Z",
            "source": "test",
            "summary": {},
            "sessions": [],
        }

    monkeypatch.setattr(status_snapshot, "build_cloud_status_snapshot", slow_build)
    profile = MegaplanResidentProfile(
        store=FileStore(tmp_path / "store"),
        config=ResidentConfig(status_snapshot_path=tmp_path / "snapshot.json"),
        cloud_backend=FakeCloudBackend(),
    )
    monkeypatch.chdir(tmp_path)

    async def run_with_heartbeat():
        before = time.monotonic()
        task = asyncio.create_task(profile.load_hot_context("c"))
        await asyncio.sleep(0.05)
        heartbeat_elapsed = time.monotonic() - before
        return await task, heartbeat_elapsed

    context, heartbeat_elapsed = asyncio.run(run_with_heartbeat())

    assert started.wait(timeout=1)
    assert heartbeat_elapsed < 0.5
    assert context["cloud_status_snapshot"] is None
    assert context["cloud_status_degraded"] is not None
    release.set()
    assert profile._snapshot_refresh_thread is not None
    profile._snapshot_refresh_thread.join(timeout=5)


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
