"""W10 / R7 — model_identity field + cache/monoculture sensors."""

from __future__ import annotations

import hashlib
from pathlib import Path

from megaplan.observability.cost import _aggregate
from megaplan.observability.events import EventKind, compute_model_identity


def test_compute_model_identity_is_deterministic_sha256() -> None:
    a = compute_model_identity("opus-4.7", "2026-05-01")
    b = compute_model_identity("opus-4.7", "2026-05-01")
    assert a == b
    # Bound to the exact hashlib.sha256 of model\x00version (not Python's
    # salted hash()).
    expected = hashlib.sha256(b"opus-4.7\x002026-05-01").hexdigest()
    assert a == expected
    # Empty version still yields a deterministic digest.
    assert compute_model_identity("opus-4.7") == compute_model_identity(
        "opus-4.7", ""
    )


def _evt(kind: str, payload: dict, phase: str = "execute") -> dict:
    return {"kind": kind, "payload": payload, "phase": phase}


def test_aggregate_surfaces_cache_hit_rate_and_monoculture_index() -> None:
    events = [
        _evt(EventKind.COST_RECORDED, {"model": "opus-4.7", "cost_usd": 0.01}),
        _evt(EventKind.COST_RECORDED, {"model": "opus-4.7", "cost_usd": 0.02}),
        _evt(EventKind.COST_RECORDED, {"model": "sonnet-4.6", "cost_usd": 0.005}),
        _evt(
            EventKind.LLM_CALL_END,
            {
                "model": "opus-4.7",
                "tokens_in": 100,
                "tokens_out": 50,
                "cache_read_tokens": 80,
            },
            phase="plan",
        ),
        _evt(
            EventKind.LLM_CALL_END,
            {
                "model": "opus-4.7",
                "tokens_in": 200,
                "tokens_out": 50,
                "cache_read_tokens": 20,
            },
            phase="plan",
        ),
    ]
    agg = _aggregate(events, meta_cost=0.0)
    assert "phase_prefix_cache_hit_rate" in agg
    assert "monoculture_index" in agg
    # plan phase: cache_read=100 / input=300 = ~0.333
    assert abs(agg["phase_prefix_cache_hit_rate"]["plan"] - (100 / 300)) < 1e-9
    # 2 distinct models / 3 cost records = ~0.667
    assert abs(agg["monoculture_index"] - (2 / 3)) < 1e-9


def test_no_control_flow_consumer_of_model_identity_or_sensors() -> None:
    """Structural grep: no megaplan module reads model_identity / the
    derived sensors for control flow. They are recorded-only telemetry."""
    repo_root = Path(__file__).resolve().parent.parent / "megaplan"
    hits: list[tuple[Path, str]] = []
    needles = ["model_identity", "phase_prefix_cache_hit_rate", "monoculture_index"]
    for path in repo_root.rglob("*.py"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for needle in needles:
            for line in text.splitlines():
                if needle not in line:
                    continue
                stripped = line.strip()
                # Permitted: writer (cost.py / events.py / hermes.py emit
                # sites), comments, string literals describing the field.
                if path.name in {"events.py", "cost.py", "hermes.py", "doctor.py"}:
                    continue
                # Anything else would imply a consumer — fail.
                hits.append((path, stripped))
    assert hits == [], f"unexpected control-flow consumer references: {hits}"
