"""Pure fold-over-events projection for plan state.

W9b: provides two public functions:

- ``read_events(plan_dir)`` — return all events from events.ndjson in seq order.
- ``fold_events(events)`` — pure, I/O-free last-snapshot-wins replay over
  STATE_WRITTEN events; ignores all other event kinds.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


_NDJSON_FILE = "events.ndjson"


def read_events(plan_dir: Path) -> List[dict]:
    """Return all events from ``plan_dir/events.ndjson`` in seq order.

    Returns an empty list if the file does not exist.  Events are returned in
    file order (the journal guarantees monotonic seq via fcntl.flock so file
    order == seq order).
    """
    ndjson_path = Path(plan_dir) / _NDJSON_FILE
    if not ndjson_path.exists():
        return []
    out: List[dict] = []
    with open(ndjson_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    out.sort(key=lambda e: e.get("seq", 0))
    return out


def fold_events(events: List[dict]) -> Dict[str, Any]:
    """Pure, I/O-free last-snapshot-wins projection over STATE_WRITTEN events.

    Replays only ``kind == "state_written"`` events in seq order and returns
    the ``state`` payload of the last such event (i.e. the most recent full
    snapshot).  All other event kinds are ignored.

    Returns an empty dict if no STATE_WRITTEN events are present.

    This function has no side effects and performs no I/O.
    """
    state_written_events = [
        e for e in events if e.get("kind") == "state_written"
    ]
    state_written_events.sort(key=lambda e: e.get("seq", 0))

    result: Dict[str, Any] = {}
    for event in state_written_events:
        payload = event.get("payload") or {}
        snapshot = payload.get("state")
        if isinstance(snapshot, dict):
            result = snapshot
    return result


def assert_fold_equiv(
    plan_dir: Path,
    *,
    recorded_trace_dir: Optional[Path] = None,
) -> None:
    """Assert ``fold_events(read_events(...))`` equals the live ``state.json``.

    The W9 oracle: state.json remains the sole authority — this only asserts
    that the shadow-WAL projection is equivalent. A divergence raises
    ``AssertionError`` (callers wire this into CI so a divergence auto-fails).

    Both sides of the comparison are JSON-normalized (``json.loads(json.dumps(...))``)
    so that semantically-equal values compare equal regardless of in-memory
    dict-instance identity or non-JSON-roundtrippable types reaching the fold.

    Parameters
    ----------
    plan_dir:
        Plan directory whose ``state.json`` is the authoritative side.
    recorded_trace_dir:
        Documented parametrization seam for the M2.5 recorded-trace corpus.
        When ``None`` (default), events are read from ``plan_dir``. When set,
        events are read from ``recorded_trace_dir`` and folded against the
        live ``plan_dir/state.json`` — the recorded trace is replayed against
        the same authority.
    """
    event_source = recorded_trace_dir if recorded_trace_dir is not None else plan_dir
    folded = fold_events(read_events(Path(event_source)))

    state_path = Path(plan_dir) / "state.json"
    if not state_path.exists():
        raise AssertionError(
            f"assert_fold_equiv: state.json missing at {state_path}"
        )
    with open(state_path, "r", encoding="utf-8") as fh:
        live = json.load(fh)

    folded_norm = json.loads(json.dumps(folded, sort_keys=True))
    live_norm = json.loads(json.dumps(live, sort_keys=True))
    if folded_norm != live_norm:
        raise AssertionError(
            "assert_fold_equiv: fold(events) != live state.json\n"
            f"  fold keys: {sorted(folded_norm.keys()) if isinstance(folded_norm, dict) else type(folded_norm).__name__}\n"
            f"  live keys: {sorted(live_norm.keys()) if isinstance(live_norm, dict) else type(live_norm).__name__}\n"
            f"  fold: {folded_norm!r}\n"
            f"  live: {live_norm!r}"
        )
