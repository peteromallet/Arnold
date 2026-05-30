"""W11a — Effect-Ledger type skeleton tests."""
import subprocess
import sys
from pathlib import Path

from megaplan.observability.effect_ledger import Effect, ReplayClass
from megaplan.observability.events import emit_state_wal, EventKind


def _read_events(plan_dir: Path) -> list:
    import json
    path = plan_dir / "events.ndjson"
    if not path.exists():
        return []
    out = []
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


_BASE_SNAP = {
    "name": "p", "idea": "i", "current_state": "initialized",
    "iteration": 1, "created_at": "2026-01-01T00:00:00Z",
    "config": {}, "sessions": {}, "plan_versions": [], "history": [], "meta": {},
}


def test_effect_dataclass_fields_exist():
    e = Effect(replay_class=ReplayClass.pure)
    assert hasattr(e, "replay_class")
    assert hasattr(e, "idempotency_key")
    assert hasattr(e, "compensation")
    assert e.idempotency_key is None
    assert e.compensation is None


def test_effect_replay_class_members():
    assert ReplayClass.pure.value == "pure"
    assert ReplayClass.idempotent_keyed.value == "idempotent_keyed"
    assert ReplayClass.at_most_once.value == "at_most_once"
    assert ReplayClass.pivot.value == "pivot"


def test_effect_idempotent_keyed_with_key():
    e = Effect(replay_class=ReplayClass.idempotent_keyed, idempotency_key="op-abc-123")
    assert e.idempotency_key == "op-abc-123"
    assert e.compensation is None


def test_effect_with_compensation():
    e = Effect(replay_class=ReplayClass.at_most_once, compensation="rollback_write_v1")
    assert e.compensation == "rollback_write_v1"


def test_state_written_payload_has_effect_field(tmp_path: Path):
    """STATE_WRITTEN payload must have an 'effect' key (default None)."""
    emit_state_wal(tmp_path, _BASE_SNAP)
    evs = [e for e in _read_events(tmp_path) if e["kind"] == EventKind.STATE_WRITTEN]
    assert len(evs) == 1
    payload = evs[0]["payload"]
    assert "effect" in payload


def test_state_written_effect_none_by_default(tmp_path: Path):
    emit_state_wal(tmp_path, _BASE_SNAP)
    evs = [e for e in _read_events(tmp_path) if e["kind"] == EventKind.STATE_WRITTEN]
    assert evs[0]["payload"]["effect"] is None


def test_state_written_effect_serialized_when_provided(tmp_path: Path):
    e = Effect(replay_class=ReplayClass.idempotent_keyed, idempotency_key="key-xyz")
    emit_state_wal(tmp_path, _BASE_SNAP, effect=e)
    evs = [e2 for e2 in _read_events(tmp_path) if e2["kind"] == EventKind.STATE_WRITTEN]
    assert len(evs) == 1
    eff = evs[0]["payload"]["effect"]
    assert isinstance(eff, dict)
    assert eff["replay_class"] == "idempotent_keyed"
    assert eff["idempotency_key"] == "key-xyz"
    assert eff["compensation"] is None


def test_effect_field_not_read_for_control_flow():
    """Structural grep: no module outside effect_ledger.py reads 'effect' field for control flow."""
    result = subprocess.run(
        ["grep", "-r", r"\.effect\b", "megaplan/"],
        capture_output=True, text=True, cwd=Path(__file__).parent.parent,
    )
    lines = [ln for ln in result.stdout.splitlines()
             if "effect_ledger" not in ln
             and "emit_state_wal" not in ln
             and "events.py" not in ln
             and "# " not in ln]
    assert lines == [], f"Unexpected effect field reads for control flow:\n" + "\n".join(lines)
