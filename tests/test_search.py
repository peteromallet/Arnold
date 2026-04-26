from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from vibecomfy.search import SearchBootstrapError, ensure_indexes, search_entries
from vibecomfy.search.index import build_search_corpus
from vibecomfy.search.index import SearchEntry


REPO_ROOT = Path(__file__).resolve().parents[1]


def _cli_env() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(REPO_ROOT) if not existing else f"{REPO_ROOT}{os.pathsep}{existing}"
    return env


def test_search_task_alias_hits_expected_entry() -> None:
    entries = [
        SearchEntry(
            class_type="WanImageToVideoSampler",
            pack="wan-pack",
            description="image to video generation node",
            tags=("video",),
            tasks=("i2v",),
            source="curated",
        ),
        SearchEntry(
            class_type="AudioReactiveNode",
            pack="audio-pack",
            description="audio reactive animation",
            tags=("audio",),
            tasks=("audio_reactive",),
            source="curated",
        ),
    ]

    results = search_entries(entries, "wan", task="i2v", limit=10)

    assert [result.entry.class_type for result in results] == ["WanImageToVideoSampler"]
    assert results[0].score > 0
    assert "alias" in results[0].reasons


def test_exact_class_type_wins_over_partial_description_match() -> None:
    entries = [
        SearchEntry(
            class_type="WanVideoSamplerXL",
            description="WanVideoSampler helper",
            source="curated",
        ),
        SearchEntry(
            class_type="WanVideoSampler",
            description="generic node",
            source="curated",
        ),
    ]

    results = search_entries(entries, "WanVideoSampler", limit=10)

    assert [result.entry.class_type for result in results] == ["WanVideoSampler", "WanVideoSamplerXL"]
    assert results[0].score > results[1].score


def test_pack_match_ranks_above_description_only_match() -> None:
    entries = [
        SearchEntry(
            class_type="DescriptionOnlyNode",
            description="wan capable processor",
            source="curated",
        ),
        SearchEntry(
            class_type="PackNode",
            pack="wan",
            description="generic processor",
            source="curated",
        ),
    ]

    results = search_entries(entries, "wan", limit=10)

    assert [result.entry.class_type for result in results] == ["PackNode", "DescriptionOnlyNode"]
    assert "pack" in results[0].reasons
    assert "description" in results[1].reasons


def test_ensure_indexes_raises_without_index_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SearchBootstrapError, match="vibecomfy sources sync"):
        ensure_indexes(auto_sync=False)


def test_search_cli_surfaces_bootstrap_error_from_empty_cwd(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "vibecomfy.cli", "search", "wan"],
        cwd=tmp_path,
        env=_cli_env(),
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "vibecomfy sources sync" in result.stdout


def test_search_cli_smoke_returns_wan_i2v_hits_after_sources_sync() -> None:
    sync = subprocess.run(
        [sys.executable, "-m", "vibecomfy.cli", "sources", "sync"],
        cwd=REPO_ROOT,
        env=_cli_env(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert sync.returncode == 0, sync.stderr or sync.stdout

    result = subprocess.run(
        [sys.executable, "-m", "vibecomfy.cli", "search", "wan", "--task", "i2v"],
        cwd=REPO_ROOT,
        env=_cli_env(),
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    rows = [line for line in result.stdout.splitlines() if line.strip()]
    assert rows[0] == "id\tclass_type\tpack\tscore\tsource"
    assert len(rows) >= 2


def test_build_search_corpus_warns_when_explicit_schema_provider_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "node_index.json").write_text("[]", encoding="utf-8")
    (tmp_path / "template_index.json").write_text("[]", encoding="utf-8")
    (tmp_path / "external_workflow_index.json").write_text("[]", encoding="utf-8")
    coverage = tmp_path / "workflow_corpus" / "manifests" / "coverage.json"
    coverage.parent.mkdir(parents=True)
    coverage.write_text('{"workflows": []}', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    warnings = []

    entries = build_search_corpus(schema_provider=FailingSchemaProvider(), warnings=warnings)

    assert entries == []
    assert len(warnings) == 1
    assert warnings[0].source == "object_info"
    assert "object_info schema discovery failed" in warnings[0].message
    assert "RuntimeError: boom" in warnings[0].message


class FailingSchemaProvider:
    def schemas(self):
        raise RuntimeError("boom")
