"""Tests for ``megaplan._core.state_store`` (M3 Step 16 / T21).

Coverage:
  - module docstring contains literal ``\"distinct from megaplan.store\"``
  - all five public symbols are exported
  - ``StateStoreModel`` Literal has the three expected members
  - ``StateStoreBackend`` is a Protocol (structural subtype check)
  - ``ForwardOnlyStateStoreBackend`` conforms to the protocol
  - ``ReversibleStateStoreBackend`` conforms to the protocol
  - ``EventSourcedStateStoreBackend`` raises ``NotImplementedError``
    on construction, ``write_state``, and ``read_state``
  - ``ForwardOnlyStateStoreBackend`` write/read round-trip
  - ``ReversibleStateStoreBackend`` write/read + snapshot/restore round-trip
"""

from __future__ import annotations

import typing
from pathlib import Path

import pytest

from megaplan._core.state_store import (
    EventSourcedStateStoreBackend,
    ForwardOnlyStateStoreBackend,
    ReversibleStateStoreBackend,
    StateStoreBackend,
    StateStoreModel,
)


# ---------------------------------------------------------------------------
# Docstring gate
# ---------------------------------------------------------------------------


def test_module_docstring_contains_distinct_from_megaplan_store():
    """The module docstring carries the literal phrase for the grep audit."""
    import megaplan._core.state_store as m

    doc = m.__doc__ or ""
    assert "distinct from megaplan.store" in doc, (
        "module docstring must contain literal 'distinct from megaplan.store'"
    )


# ---------------------------------------------------------------------------
# Symbol export gate
# ---------------------------------------------------------------------------


def test_all_public_symbols_exported():
    """Every required symbol is importable from the module."""
    symbols = [
        ("StateStoreModel", StateStoreModel),
        ("StateStoreBackend", StateStoreBackend),
        ("ForwardOnlyStateStoreBackend", ForwardOnlyStateStoreBackend),
        ("ReversibleStateStoreBackend", ReversibleStateStoreBackend),
        ("EventSourcedStateStoreBackend", EventSourcedStateStoreBackend),
    ]
    for name, obj in symbols:
        assert obj is not None, f"{name} is None"


# ---------------------------------------------------------------------------
# StateStoreModel Literal
# ---------------------------------------------------------------------------


def test_state_store_model_literal_members():
    """The Literal has exactly the three expected members."""
    args = set(typing.get_args(StateStoreModel))
    assert args == {"forward_only", "reversible", "event_sourced"}


# ---------------------------------------------------------------------------
# Protocol conformance (structural)
# ---------------------------------------------------------------------------


def test_forward_only_conforms_to_protocol():
    """ForwardOnlyStateStoreBackend structurally satisfies StateStoreBackend."""
    backend = ForwardOnlyStateStoreBackend()
    assert isinstance(backend, StateStoreBackend)


def test_reversible_conforms_to_protocol():
    """ReversibleStateStoreBackend structurally satisfies StateStoreBackend."""
    backend = ReversibleStateStoreBackend()
    assert isinstance(backend, StateStoreBackend)


# ---------------------------------------------------------------------------
# EventSourcedStateStoreBackend — NotImplementedError
# ---------------------------------------------------------------------------


def test_event_sourced_init_raises_not_implemented():
    """Constructing EventSourcedStateStoreBackend raises NotImplementedError."""
    with pytest.raises(NotImplementedError, match="not implemented"):
        EventSourcedStateStoreBackend()


def test_event_sourced_write_state_raises_not_implemented():
    """Even if we could construct it, write_state would raise."""
    # Construct via object.__new__ to bypass __init__
    backend = object.__new__(EventSourcedStateStoreBackend)
    with pytest.raises(NotImplementedError, match="write_state"):
        backend.write_state(Path("/tmp"), {})


def test_event_sourced_read_state_raises_not_implemented():
    """Even if we could construct it, read_state would raise."""
    backend = object.__new__(EventSourcedStateStoreBackend)
    with pytest.raises(NotImplementedError, match="read_state"):
        backend.read_state(Path("/tmp"))


# ---------------------------------------------------------------------------
# ForwardOnlyStateStoreBackend round-trip
# ---------------------------------------------------------------------------


@pytest.fixture
def plan_dir(tmp_path: Path) -> Path:
    d = tmp_path / "plans" / "plan-1"
    d.mkdir(parents=True)
    return d


def test_forward_only_write_read_round_trip(plan_dir: Path):
    """Write then read returns the same state dict."""
    backend = ForwardOnlyStateStoreBackend()
    state = {"current_state": "planned", "iteration": 2, "notes": "hello"}
    backend.write_state(plan_dir, state)
    result = backend.read_state(plan_dir)
    assert result["current_state"] == "planned"
    assert result["iteration"] == 2
    assert result["notes"] == "hello"


def test_forward_only_model_attribute():
    """model is 'forward_only'."""
    assert ForwardOnlyStateStoreBackend.model == "forward_only"
    backend = ForwardOnlyStateStoreBackend()
    assert backend.model == "forward_only"


def test_forward_only_overwrite(plan_dir: Path):
    """Second write replaces the first (destructive)."""
    backend = ForwardOnlyStateStoreBackend()
    backend.write_state(plan_dir, {"k": "v1"})
    backend.write_state(plan_dir, {"k": "v2"})
    result = backend.read_state(plan_dir)
    assert result["k"] == "v2"
    assert "k" in result


# ---------------------------------------------------------------------------
# ReversibleStateStoreBackend round-trip
# ---------------------------------------------------------------------------


def test_reversible_write_read_round_trip(plan_dir: Path):
    """Write then read returns the same state dict."""
    backend = ReversibleStateStoreBackend()
    state = {
        "schema_version": 0,
        "current_state": "initialized",
        "iteration": 1,
        "config": {"project_dir": str(plan_dir)},
    }
    # Reversible writes require the state dict to have enough shape for
    # the snapshot machinery; we supply a minimal valid shape.
    backend.write_state(plan_dir, state)
    result = backend.read_state(plan_dir)
    assert result["current_state"] == "initialized"
    assert result["iteration"] == 1


def test_reversible_snapshot_restore_round_trip(plan_dir: Path):
    """Snapshot before a mutation, mutate, then restore to the snapshot."""
    backend = ReversibleStateStoreBackend()
    # Initial write seeds the file so snapshot has something to capture.
    backend.write_state(
        plan_dir,
        {
            "schema_version": 0,
            "current_state": "initialized",
            "iteration": 1,
            "config": {"project_dir": str(plan_dir)},
        },
    )
    sid = backend.snapshot(plan_dir)
    assert sid is not None, "snapshot should return an id after a write"

    # Mutate
    backend.write_state(
        plan_dir,
        {
            "schema_version": 0,
            "current_state": "planned",
            "iteration": 2,
            "config": {"project_dir": str(plan_dir)},
        },
    )
    assert backend.read_state(plan_dir)["current_state"] == "planned"

    # Restore
    restored = backend.restore(plan_dir, sid)
    assert restored["current_state"] == "initialized"
    assert restored["iteration"] == 1


def test_reversible_model_attribute():
    """model is 'reversible'."""
    assert ReversibleStateStoreBackend.model == "reversible"
    backend = ReversibleStateStoreBackend()
    assert backend.model == "reversible"


def test_reversible_snapshot_returns_none_when_no_state(plan_dir: Path):
    """Snapshot on a directory with no state.json returns None."""
    backend = ReversibleStateStoreBackend()
    assert backend.snapshot(plan_dir) is None


# ---------------------------------------------------------------------------
# EventSourced model attribute
# ---------------------------------------------------------------------------


def test_event_sourced_model_attribute():
    """model is 'event_sourced' (class-level)."""
    assert EventSourcedStateStoreBackend.model == "event_sourced"
