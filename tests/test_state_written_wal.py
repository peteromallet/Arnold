"""W9a — STATE_WRITTEN shadow-WAL tests."""
import json
from pathlib import Path

from megaplan._core.state import write_plan_state
from megaplan.loop.engine import save_loop_state
from megaplan.observability.events import EventKind
from megaplan.planning.state import STATE_INITIALIZED


def _state(**overrides):
    state = {
        "name": "p",
        "idea": "i",
        "current_state": STATE_INITIALIZED,
        "iteration": 1,
        "created_at": "2026-01-01T00:00:00Z",
        "config": {"project_dir": "/p"},
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {},
    }
    state.update(overrides)
    return state


def _read_events(plan_dir: Path) -> list[dict]:
    path = plan_dir / "events.ndjson"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def test_write_plan_state_emits_one_state_written(tmp_path: Path) -> None:
    write_plan_state(tmp_path, mode="replace", state=_state())
    evs = [e for e in _read_events(tmp_path) if e["kind"] == EventKind.STATE_WRITTEN]
    assert len(evs) == 1
    payload = evs[0]["payload"]
    assert payload["effect_class"] == "state_write"
    assert payload["taint"] == "trusted"
    assert "schema_version" in payload
    assert isinstance(payload["state"], dict)
    assert payload["state"]["name"] == "p"


def test_write_plan_state_no_op_emits_zero(tmp_path: Path) -> None:
    # active-step-heartbeat with no matching active_step ⇒ should_write=False.
    write_plan_state(tmp_path, mode="replace", state=_state())
    before = len([e for e in _read_events(tmp_path) if e["kind"] == EventKind.STATE_WRITTEN])
    write_plan_state(
        tmp_path,
        mode="active-step-heartbeat",
        run_id="nonexistent-run-id",
        kind="heartbeat",
    )
    after = len([e for e in _read_events(tmp_path) if e["kind"] == EventKind.STATE_WRITTEN])
    assert after == before


def test_save_loop_state_emits_one_state_written(tmp_path: Path) -> None:
    save_loop_state(tmp_path, {"name": "loop", "iteration": 0})
    evs = [e for e in _read_events(tmp_path) if e["kind"] == EventKind.STATE_WRITTEN]
    assert len(evs) == 1
    assert evs[0]["payload"]["effect_class"] == "state_write"
