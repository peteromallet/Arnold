from __future__ import annotations

import argparse
import json

import pytest

from vibecomfy.commands.analyze import _cmd_corpus, _cmd_tracefield


# ── analyze corpus ──────────────────────────────────────────────────────


def test_analyze_corpus_json_returns_stats(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_corpus(argparse.Namespace(json=True))
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert "templates_total" in payload
    assert "templates_regeneratable" in payload
    assert "templates_deferred" in payload
    assert "total_loc" in payload
    assert "by_category" in payload
    assert "node_type_distribution" in payload
    assert "custom_pack_usage" in payload
    assert "uuid_subgraph_instances" in payload
    assert "templates_with_manual_marker" in payload
    assert isinstance(payload["templates_total"], int)
    assert isinstance(payload["total_loc"], int)
    assert payload["templates_total"] > 0
    assert payload["total_loc"] > 0


def test_analyze_corpus_text_renders_header(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_corpus(argparse.Namespace(json=False))
    text = capsys.readouterr().out
    assert code == 0
    assert "Corpus snapshot" in text
    assert "templates:" in text
    assert "LOC" in text


# ── analyze tracefield ──────────────────────────────────────────────────


def test_analyze_tracefield_json_returns_resolution_chain(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_tracefield(
        argparse.Namespace(workflow="video/wan_i2v", field="prompt", json=True)
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert "field" in payload
    assert payload["field"] == "prompt"
    assert "resolution_chain" in payload
    assert isinstance(payload["resolution_chain"], list)
    assert len(payload["resolution_chain"]) > 0
    # Verify chain entries have expected shape
    for entry in payload["resolution_chain"]:
        assert "priority" in entry
        # Entries have source, value; some have field, node_id, class_type
        assert "source" in entry or "description" in entry
    assert "aliases" in payload
    assert "bound_node" in payload
    assert "node_id" in payload["bound_node"]
    assert "class_type" in payload["bound_node"]
    assert "field" in payload["bound_node"]


def test_analyze_tracefield_unknown_field_returns_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_tracefield(
        argparse.Namespace(workflow="video/wan_i2v", field="nonexistent_field_xyz", json=True)
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert "error" in payload


def test_analyze_tracefield_text_renders_chain(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_tracefield(
        argparse.Namespace(workflow="video/wan_i2v", field="prompt", json=False)
    )
    text = capsys.readouterr().out
    assert code == 0
    assert "field:" in text
    assert "resolution chain" in text
    assert "bound to:" in text
