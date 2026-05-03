from __future__ import annotations

import sqlite3

import pytest

from agent_kit.store.sqlite import SQLiteStore


@pytest.fixture
def store(tmp_path):
    return SQLiteStore(tmp_path / "codebases.db")


def test_codebase_uniqueness_and_lowercase_normalization(store) -> None:
    created = store.create_codebase(
        owner="PeterOmallet",
        name="Arnold-V2",
        default_branch="main",
        group_name="Core",
    )

    assert created["owner"] == "peteromallet"
    assert created["name"] == "arnold-v2"

    with pytest.raises(sqlite3.IntegrityError):
        store.create_codebase(
            owner=" peteromallet ",
            name="ARNOLD-v2",
            default_branch="main",
        )

    upserted = store.upsert_codebase(
        owner="PETEROMALLET",
        name="Arnold-V2",
        default_branch="trunk",
        group_name="Core",
    )

    assert upserted["id"] == created["id"]
    assert upserted["default_branch"] == "trunk"
    assert len(store.list_codebases()) == 1


def test_codebase_scope_group_and_epic_filtering(store) -> None:
    epic_1 = store.create_epic(
        title="Epic 1",
        goal="Investigate code",
        body="# Epic 1",
    )
    epic_2 = store.create_epic(
        title="Epic 2",
        goal="Investigate other code",
        body="# Epic 2",
    )
    store.create_codebase(
        owner="peteromallet",
        name="global-api",
        default_branch="main",
        scope="global",
        group_name="backend",
    )
    epic_specific = store.create_codebase(
        owner="banodoco",
        name="campaign-app",
        default_branch="main",
        scope="epic_specific",
        group_name="frontend",
        associated_epic_id=epic_1["id"],
    )
    store.create_codebase(
        owner="banodoco",
        name="other-app",
        default_branch="main",
        scope="epic_specific",
        group_name="frontend",
        associated_epic_id=epic_2["id"],
    )

    assert [row["name"] for row in store.list_codebases(scope="global")] == [
        "global-api"
    ]
    assert {row["name"] for row in store.list_codebases(group_name="frontend")} == {
        "campaign-app",
        "other-app",
    }
    assert {
        row["id"]
        for row in store.list_codebases(epic_id=epic_1["id"], include_global=True)
    } == {epic_specific["id"], store.find_codebase("peteromallet", "global-api")["id"]}
    assert [
        row["id"]
        for row in store.list_codebases(epic_id=epic_1["id"], include_global=False)
    ] == [epic_specific["id"]]


def test_api_cache_ttl_hit_miss_and_cleanup(store) -> None:
    fresh = store.upsert_api_cache(
        cache_key="tree:peteromallet/arnold-v2",
        content="fresh tree",
        metadata={"request": "tree"},
        expires_at="2026-04-30T13:00:00Z",
    )
    expired = store.upsert_api_cache(
        cache_key="file:peteromallet/arnold-v2/app.py",
        content="expired file",
        metadata={"request": "file"},
        expires_at="2026-04-30T11:00:00Z",
    )
    excerpt = store.create_code_artifact(
        kind="excerpt",
        source="codebase",
        content="keep me",
        expires_at="2026-04-30T11:00:00Z",
    )

    assert store.get_api_cache(
        "tree:peteromallet/arnold-v2",
        now="2026-04-30T12:00:00Z",
        touch=False,
    )["id"] == fresh["id"]
    assert store.get_api_cache(
        "file:peteromallet/arnold-v2/app.py",
        now="2026-04-30T12:00:00Z",
    ) is None

    assert store.cleanup_expired_api_cache(now="2026-04-30T12:00:00Z") == 1
    assert store.load_code_artifact(expired["id"]) is None
    assert store.load_code_artifact(fresh["id"]) is not None
    assert store.load_code_artifact(excerpt["id"]) is not None
