"""Pure fold-over-events projection for plan state.

W9b: provides two public functions:

- ``read_events(plan_dir)`` — return all events from events.ndjson in seq order.
- ``fold_events(events)`` — pure, I/O-free last-snapshot-wins replay over
  STATE_WRITTEN events; ignores all other event kinds.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


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


def rebuild_state_from_wal(plan_dir: Path) -> Dict[str, Any]:
    """Rebuild plan state from the shadow-WAL events.ndjson.

    Thin alias for ``fold_events(read_events(plan_dir))`` — the canonical
    WAL-fold projection consumed by ``read_plan_state_cached`` under R1
    authority mode.
    """
    return fold_events(read_events(Path(plan_dir)))


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


def lift_driver_events_to_wal(events: List[dict]) -> List[dict]:
    """Lift driver-level events into shadow-WAL ``STATE_WRITTEN`` form.

    The M2.5 corpus records driver transitions as flat dicts carrying
    ``state`` / ``next_step`` / ``valid_next`` / ``iteration`` (and friendly
    ``msg`` lines for non-transition events such as ``phase`` runs). This
    function synthesizes one ``state_written`` WAL event per driver-level
    state transition (any event with a ``state`` field), assigning a
    monotonic ``seq`` so the synthesized stream can be fed straight into
    ``fold_events`` / ``rebuild_state_from_wal``.

    Non-transition driver events (phase commands, terminal markers, completion
    verdicts) are skipped — only events that carry a driver ``state`` snapshot
    contribute to the WAL projection.
    """
    wal: List[dict] = []
    seq = 0
    for ev in events:
        if not isinstance(ev, dict):
            continue
        if "state" not in ev:
            continue
        snapshot: Dict[str, Any] = {"current_state": ev.get("state")}
        if "next_step" in ev:
            snapshot["next_step"] = ev.get("next_step")
        if "valid_next" in ev:
            snapshot["valid_next"] = ev.get("valid_next")
        if "iteration" in ev:
            snapshot["iteration"] = ev.get("iteration")
        seq += 1
        wal.append(
            {
                "seq": seq,
                "kind": "state_written",
                "payload": {"state": snapshot},
            }
        )
    return wal


@dataclass(frozen=True)
class OracleFailure:
    name: str
    reason: str
    expected: Any
    actual: Any


@dataclass(frozen=True)
class OracleResult:
    passed: int
    failed: int
    total: int
    failures: List[OracleFailure] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.failed == 0


def _default_expected_from_outcome(corpus: Dict[str, Any]) -> Dict[str, Any]:
    """Project the corpus outcome into the comparison shape.

    Only goldens that record at least one driver-level state transition carry
    a meaningful ``final_state`` in shadow-WAL projection terms — corpora that
    fail before any driver transition (e.g. ``cost_cap_exceeded`` mid-phase,
    ``status_lookup_failed`` on initial probe) synthesize ``final_state`` from
    the outcome record alone. The WAL projection of such corpora is empty,
    so we mirror that by projecting ``current_state=None`` so the two sides
    match.
    """
    outcome = corpus.get("outcome") or {}
    events = corpus.get("events") or []
    has_transition = any(
        isinstance(ev, dict) and "state" in ev for ev in events
    )
    if not has_transition:
        return {"current_state": None}
    return {"current_state": outcome.get("final_state")}


def _default_observed_from_fold(folded: Dict[str, Any]) -> Dict[str, Any]:
    return {"current_state": folded.get("current_state")}


def fold_equivalence_oracle(
    manifest_path: Path,
    *,
    lift: Callable[[List[dict]], List[dict]] = lift_driver_events_to_wal,
    fold: Callable[[List[dict]], Dict[str, Any]] = fold_events,
    expected_from_corpus: Callable[
        [Dict[str, Any]], Dict[str, Any]
    ] = _default_expected_from_outcome,
    observed_from_fold: Callable[
        [Dict[str, Any]], Dict[str, Any]
    ] = _default_observed_from_fold,
) -> OracleResult:
    """Parameterized fold-equivalence oracle over a corpus MANIFEST.

    Reads the MANIFEST at ``manifest_path``, iterates each golden, loads its
    ``corpus_filename`` sibling, lifts the driver events into shadow-WAL form,
    runs the WAL fold, and asserts the projected final state matches the
    corpus's recorded outcome. All extension seams (``lift`` / ``fold`` /
    ``expected_from_corpus`` / ``observed_from_fold``) are parameterized so
    later milestones can plug richer projections without forking the oracle.

    Returns an ``OracleResult`` reporting pass/fail counts plus per-golden
    failure detail. Callers wire ``OracleResult.ok`` into the hinge gate.
    """
    manifest_path = Path(manifest_path)
    corpus_dir = manifest_path.parent
    with open(manifest_path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)

    goldens = manifest.get("goldens") or []
    passed = 0
    failures: List[OracleFailure] = []

    for entry in goldens:
        name = entry.get("name") or entry.get("corpus_filename") or "<unnamed>"
        corpus_file = corpus_dir / entry["corpus_filename"]
        if not corpus_file.exists():
            failures.append(
                OracleFailure(
                    name=name,
                    reason=f"missing corpus file: {corpus_file}",
                    expected=None,
                    actual=None,
                )
            )
            continue
        with open(corpus_file, "r", encoding="utf-8") as fh:
            corpus = json.load(fh)

        events = corpus.get("events") or []
        wal_events = lift(events)
        folded = fold(wal_events)

        expected = expected_from_corpus(corpus)
        observed = observed_from_fold(folded)

        expected_norm = json.loads(json.dumps(expected, sort_keys=True))
        observed_norm = json.loads(json.dumps(observed, sort_keys=True))

        if expected_norm == observed_norm:
            passed += 1
        else:
            failures.append(
                OracleFailure(
                    name=name,
                    reason="fold projection diverged from corpus outcome",
                    expected=expected_norm,
                    actual=observed_norm,
                )
            )

    total = len(goldens)
    return OracleResult(
        passed=passed,
        failed=total - passed,
        total=total,
        failures=failures,
    )
