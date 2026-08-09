"""Tests for the Phase-0 verification-probe records (probe_records.py)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.probe_records import (
    VERIFICATION_PROBES,
    ProbeRecord,
    main,
    render_probes_markdown,
)


def test_five_probes_with_sequential_ids() -> None:
    assert len(VERIFICATION_PROBES) == 5
    assert [p.id for p in VERIFICATION_PROBES] == [
        "probe-1",
        "probe-2",
        "probe-3",
        "probe-4",
        "probe-5",
    ]


@pytest.mark.parametrize("probe", VERIFICATION_PROBES, ids=lambda p: p.id)
def test_probe_fields_populated(probe: ProbeRecord) -> None:
    assert probe.id.startswith("probe-")
    assert probe.title
    assert probe.question
    assert probe.answer
    assert probe.evidence
    assert all(isinstance(item, str) and item for item in probe.evidence)
    assert probe.verified_at == "2026-08-07"
    assert probe.method in ("census", "code-inventory", "code", "manual")


def test_render_contains_each_probe_id_and_answer() -> None:
    rendered = render_probes_markdown()
    for probe in VERIFICATION_PROBES:
        assert probe.id in rendered
        assert probe.answer in rendered


def test_render_is_deterministic() -> None:
    first = render_probes_markdown()
    second = render_probes_markdown()
    assert first == second
    # A shuffled input renders identically (ordering is by id).
    shuffled = list(reversed(VERIFICATION_PROBES))
    assert render_probes_markdown(shuffled) == first


def test_render_is_markdown_shaped() -> None:
    rendered = render_probes_markdown()
    assert rendered.startswith("# Verification probes")
    assert "| id | title | answer | method |" in rendered
    for probe in VERIFICATION_PROBES:
        assert f"## {probe.id} —" in rendered
        assert "**Question:**" in rendered
        assert "**Evidence:**" in rendered


def test_main_returns_zero_and_prints_render() -> None:
    assert main([]) == 0
    assert main(["ignored-arg"]) == 0


def test_cli_module_exits_zero() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-m", "arnold_pipelines.megaplan.cloud.probe_records"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.startswith("# Verification probes")
    assert "probe-1" in result.stdout
    assert "probe-5" in result.stdout
