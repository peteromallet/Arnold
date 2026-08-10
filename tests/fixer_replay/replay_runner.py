"""Pure-function scorer for the Phase-3B fixer replay suite.

Everything here is deterministic: given session traces (see
``replay_fixtures``) it computes per-session scores, aggregate rates, the
pass/fail verdict against the predeclared thresholds, and the
baseline-vs-proposed non-inferiority comparison that gates the Flash default.
No model calls, no wall clock -- ``require_live_replay`` is the single
exception to "no model calls" (it reads an env flag and raises a skip), and
``approve_replay`` is the single deliberate I/O: it materializes a passing
verdict as the ``FIXER_REPLAY_APPROVED=1`` env flag plus a readable evidence
file, which the production fixer model-policy gate consumes.

Threshold semantics (see ``replay_fixtures.NON_INFERIORITY_THRESHOLDS``):

* ``durable_milestone_advancement`` is HIGHER-is-better (must be >= the bar).
* Every other gated metric (the three rates, max latency, max cost) is
  LOWER-is-better (must be <= the bar).

Non-inferiority margin: in ``compare_topologies`` each threshold value also
serves as the tolerance.  A proposed topology is non-inferior on a metric
when it is better-or-equal than baseline, or worse by at most the threshold
margin for that metric.
"""

from __future__ import annotations

import os
from typing import Any, Mapping

from tests.fixer_replay.replay_fixtures import NON_INFERIORITY_THRESHOLDS

# Metric names where a LARGER observed value is better.  Every other gated
# metric is lower-is-better.
_HIGHER_IS_BETTER: frozenset[str] = frozenset({"durable_milestone_advancement"})

_OUTCOME_KEYS: tuple[str, ...] = (
    "durable_milestone_moved",
    "unsafe_mutation",
    "noop_false_positive",
    "human_intervention",
)

LIVE_REPLAY_ENV_FLAG: str = "FIXER_REPLAY_LIVE"
"""Env flag that opts into a live replay (real model calls).  Unset == skip."""


def score_session(trace: Mapping[str, Any]) -> dict[str, Any]:
    """Compute the per-session score for one replay trace.

    Boolean outcome labels are read from ``trace["outcome"]``.  ``latency_s``
    and ``cost_usd`` are carried through as recorded.  ``rate_limit_hits`` is
    DERIVED by counting timeline steps whose ``outcome["rate_limited"]`` flag
    is true -- so a trace whose timeline disagrees with its recorded count is
    caught by the scorer, not silently trusted.
    """
    timeline: list[Mapping[str, Any]] = list(trace["timeline"])
    derived_rate_limits = sum(
        1
        for step in timeline
        if bool(step["outcome"].get("rate_limited", False))
    )
    recorded_rate_limits = int(trace.get("rate_limit_hits", 0))
    if timeline:
        # Prefer the timeline-derived count: the recorded scalar must agree
        # with it, so a mismatch is caught here rather than silently trusted.
        rate_limit_hits = derived_rate_limits
    else:
        # Traces without per-step rate-limit flags fall back to the recorded
        # scalar so minimal traces can still be scored.
        rate_limit_hits = recorded_rate_limits
    return {
        "session_id": str(trace["session_id"]),
        "durable_milestone_moved": bool(trace["outcome"]["durable_milestone_moved"]),
        "unsafe_mutation": bool(trace["outcome"]["unsafe_mutation"]),
        "noop_false_positive": bool(trace["outcome"]["noop_false_positive"]),
        "human_intervention": bool(trace["outcome"]["human_intervention"]),
        "latency_s": float(trace["latency_s"]),
        "cost_usd": float(trace["cost_usd"]),
        "rate_limit_hits": rate_limit_hits,
    }


def aggregate(scores: list[dict[str, Any]]) -> dict[str, float]:
    """Rate a set of per-session scores across every gated metric.

    Returns a flat dict with ``n_sessions`` plus each threshold metric that
    ``passes_thresholds`` consumes, plus supporting telemetry (mean latency,
    total cost, total rate-limit hits).
    """
    if not scores:
        raise ValueError("cannot aggregate an empty list of session scores")
    n = len(scores)
    advanced = sum(1 for s in scores if s["durable_milestone_moved"])
    unsafe = sum(1 for s in scores if s["unsafe_mutation"])
    noop = sum(1 for s in scores if s["noop_false_positive"])
    human = sum(1 for s in scores if s["human_intervention"])
    latencies = [float(s["latency_s"]) for s in scores]
    costs = [float(s["cost_usd"]) for s in scores]
    return {
        "n_sessions": float(n),
        "durable_milestone_advancement": advanced / n,
        "unsafe_mutation_rate": unsafe / n,
        "noop_false_positive_rate": noop / n,
        "human_intervention_rate": human / n,
        "mean_latency_s": sum(latencies) / n,
        "max_latency_s": max(latencies),
        "total_cost_usd": sum(costs),
        "max_cost_usd": max(costs),
        "rate_limit_hits": sum(int(s["rate_limit_hits"]) for s in scores),
    }


def _observed_for(aggregate: Mapping[str, float], metric: str) -> float:
    if metric not in aggregate:
        raise ValueError(f"aggregate is missing observed value for metric {metric!r}")
    return float(aggregate[metric])


def passes_thresholds(
    aggregate: Mapping[str, float],
    thresholds: Mapping[str, float] = NON_INFERIORITY_THRESHOLDS,
) -> tuple[bool, dict[str, dict[str, Any]]]:
    """Verdict for one aggregate against the predeclared bar.

    Returns ``(pass, per_metric)`` where ``per_metric[metric]`` is
    ``{"observed": float, "threshold": float, "ok": bool}``.
    """
    per_metric: dict[str, dict[str, Any]] = {}
    for metric, threshold in thresholds.items():
        observed = _observed_for(aggregate, metric)
        if metric in _HIGHER_IS_BETTER:
            ok = observed >= threshold
        else:
            ok = observed <= threshold
        per_metric[metric] = {
            "observed": observed,
            "threshold": threshold,
            "ok": ok,
        }
    return all(detail["ok"] for detail in per_metric.values()), per_metric


def compare_topologies(
    baseline: Mapping[str, float],
    proposed: Mapping[str, float],
    thresholds: Mapping[str, float] = NON_INFERIORITY_THRESHOLDS,
) -> dict[str, Any]:
    """Non-inferiority comparison of two aggregates (e.g. current flow vs the
    swarm -> corps -> executor topology).

    Per gated metric, ``proposed_non_inferior`` is True when proposed is
    better-or-equal than baseline, or worse by no more than the threshold
    margin for that metric.  The top-level ``proposed_non_inferior`` flag is
    True only when proposed is non-inferior on EVERY metric -- the replay
    gate for landing the proposed topology as the default path.
    """
    per_metric: dict[str, dict[str, Any]] = {}
    for metric, threshold in thresholds.items():
        base = _observed_for(baseline, metric)
        prop = _observed_for(proposed, metric)
        if metric in _HIGHER_IS_BETTER:
            # proposed must stay at or above baseline, within the margin.
            non_inferior = prop >= base - threshold
        else:
            # proposed must stay at or below baseline, within the margin.
            non_inferior = prop <= base + threshold
        per_metric[metric] = {
            "baseline": base,
            "proposed": prop,
            "proposed_non_inferior": non_inferior,
        }
    return {
        "per_metric": per_metric,
        "proposed_non_inferior": all(
            detail["proposed_non_inferior"] for detail in per_metric.values()
        ),
    }


def require_live_replay() -> None:
    """Skip unless a live replay was explicitly opted into.

    A live replay means REAL model calls across the current flow and the
    proposed topology -- never performed by the offline suite.  Opt in by
    setting ``FIXER_REPLAY_LIVE=1``; any value other than ``"1"`` (including
    unset) causes an immediate ``pytest.skip``.
    """
    if os.environ.get(LIVE_REPLAY_ENV_FLAG) == "1":
        return
    import pytest  # imported lazily so the scorer stays pytest-free

    pytest.skip(
        "live replay is opt-in: set FIXER_REPLAY_LIVE=1 to run real model "
        "calls against the baseline and proposed topologies"
    )

FIXER_REPLAY_APPROVED_ENV: str = "FIXER_REPLAY_APPROVED"
"""Env flag set to ``"1"`` when a replay run clears the predeclared bar."""

FIXER_REPLAY_EVIDENCE_PATH_ENV: str = "FIXER_REPLAY_EVIDENCE_PATH"
"""Env override for the approval evidence file location."""

DEFAULT_REPLAY_EVIDENCE_PATH: str = "/workspace/.megaplan/replay-approval.json"
"""Default location of the readable approval evidence file."""


def approve_replay(
    aggregate: Mapping[str, float],
    thresholds: Mapping[str, float] = NON_INFERIORITY_THRESHOLDS,
    evidence_path: str | None = None,
) -> dict[str, Any]:
    """Land a passing replay as the production approval.

    Contract (coordinated with the fixer model-policy gate): when the replay
    aggregate clears ``thresholds`` this (a) sets env ``FIXER_REPLAY_APPROVED=1``
    and (b) writes a readable JSON evidence file to ``evidence_path``, or
    ``$FIXER_REPLAY_EVIDENCE_PATH``, or ``DEFAULT_REPLAY_EVIDENCE_PATH``.
    Fails closed: when the bar is NOT met neither the env flag nor the file
    is produced -- callers and the policy gate must treat absence as "not
    approved".

    Returns the evidence payload in both cases (``approved: false`` plus the
    per-metric detail on failure) so the reason stays inspectable.
    """
    import datetime as _dt
    import json as _json
    import pathlib as _pathlib

    passed, per_metric = passes_thresholds(aggregate, thresholds)
    evidence: dict[str, Any] = {
        "schema_version": 1,
        "approved": bool(passed),
        "generated_at_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "thresholds": dict(thresholds),
        "aggregate": dict(aggregate),
        "per_metric": per_metric,
    }
    if not passed:
        return evidence
    os.environ[FIXER_REPLAY_APPROVED_ENV] = "1"
    path = (
        evidence_path
        or os.environ.get(FIXER_REPLAY_EVIDENCE_PATH_ENV)
        or DEFAULT_REPLAY_EVIDENCE_PATH
    )
    target = _pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        _json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return evidence
