"""Tests for FaultRegistry."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from megaplan._pipeline.faults import (
    Fault,
    FaultIterationEntry,
    FaultRegistry,
)


def test_load_empty_when_no_file(tmp_path: Path) -> None:
    reg = FaultRegistry.load(tmp_path)
    assert reg.faults == {}
    assert reg.iteration == 0


def test_add_new_fault_records_history_entry(tmp_path: Path) -> None:
    reg = FaultRegistry(iteration=1)
    reg.add(Fault(id="short-sentences", kind="style", details="3 short."))
    f = reg.faults["short-sentences"]
    assert f.status == "open"
    assert len(f.history) == 1
    assert f.history[0].iteration == 1
    assert f.history[0].status == "open"


def test_re_adding_same_fault_appends_history(tmp_path: Path) -> None:
    reg = FaultRegistry(iteration=1)
    reg.add(Fault(id="x", kind="style"))
    reg.iteration = 2
    reg.add(Fault(id="x", kind="style", status="addressed"))
    f = reg.faults["x"]
    assert len(f.history) == 2
    assert f.status == "addressed"
    assert [h.iteration for h in f.history] == [1, 2]


def test_mark_appends_status_change(tmp_path: Path) -> None:
    reg = FaultRegistry(iteration=1)
    reg.add(Fault(id="y", kind="logic"))
    reg.iteration = 2
    reg.mark("y", "addressed", note="fixed in revise")
    assert reg.faults["y"].status == "addressed"
    assert reg.faults["y"].history[-1].note == "fixed in revise"


def test_mark_unknown_raises(tmp_path: Path) -> None:
    reg = FaultRegistry()
    with pytest.raises(KeyError, match="no fault"):
        reg.mark("ghost", "addressed")


def test_addressed_then_reopened_count(tmp_path: Path) -> None:
    reg = FaultRegistry(iteration=1)
    reg.add(Fault(id="flap", kind="style"))
    reg.iteration = 2
    reg.mark("flap", "addressed")
    reg.iteration = 3
    reg.mark("flap", "open")
    reg.iteration = 4
    reg.mark("flap", "addressed")
    reg.iteration = 5
    reg.mark("flap", "open")
    assert reg.faults["flap"].addressed_then_reopened_count == 2


def test_save_then_load_round_trip(tmp_path: Path) -> None:
    reg = FaultRegistry(iteration=3)
    reg.add(Fault(id="alpha", kind="style", severity="significant", details="a"))
    reg.add(Fault(id="beta", kind="logic", severity="minor"))
    reg.mark("alpha", "addressed", note="fixed")
    path = reg.save(tmp_path)
    assert path == tmp_path / "faults.json"

    reloaded = FaultRegistry.load(tmp_path)
    assert reloaded.iteration == 3
    assert set(reloaded.faults.keys()) == {"alpha", "beta"}
    assert reloaded.faults["alpha"].status == "addressed"
    assert len(reloaded.faults["alpha"].history) == 2


def test_open_significant_filter(tmp_path: Path) -> None:
    reg = FaultRegistry(iteration=1)
    reg.add(Fault(id="a", kind="style", severity="significant"))
    reg.add(Fault(id="b", kind="style", severity="minor"))
    reg.add(Fault(id="c", kind="style", severity="significant", status="addressed"))
    open_sig = reg.open_significant()
    assert {f.id for f in open_sig} == {"a"}


def test_reopened_repeatedly_filter(tmp_path: Path) -> None:
    reg = FaultRegistry(iteration=1)
    reg.add(Fault(id="flap", kind="style"))
    for i, status in enumerate(["addressed", "open", "addressed", "open"], start=2):
        reg.iteration = i
        reg.mark("flap", status)
    reg.add(Fault(id="stable", kind="logic"))

    repeats = reg.reopened_repeatedly(threshold=2)
    assert {f.id for f in repeats} == {"flap"}

    repeats_threshold_3 = reg.reopened_repeatedly(threshold=3)
    assert repeats_threshold_3 == []


def test_load_resilient_to_corrupt_file(tmp_path: Path) -> None:
    (tmp_path / "faults.json").write_text("{not valid json")
    reg = FaultRegistry.load(tmp_path)
    assert reg.faults == {}
