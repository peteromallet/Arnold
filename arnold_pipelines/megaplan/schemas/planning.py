"""Planning schema contracts shared across gate and tiebreaker flows."""

from __future__ import annotations

from typing import Any, TypedDict

from arnold_pipelines.megaplan.north_star_actions import NorthStarAction
from arnold_pipelines.megaplan.types import FlagRecord, SettledDecision


class TiebreakerDecision(TypedDict, total=False):
    fuzzy_group_id: str
    flag_ids: list[str]
    question: str
    researcher_pick: str
    challenger_pick: str
    human_pick: str
    action: str
    rationale: str
    timestamp: str


class GatePayload(TypedDict):
    recommendation: str
    rationale: str
    signals_assessment: str
    warnings: list[str]
    settled_decisions: list[SettledDecision]


class GateArtifact(TypedDict, total=False):
    passed: bool
    criteria_check: dict[str, Any]
    preflight_results: dict[str, bool]
    unresolved_flags: list[FlagRecord]
    recommendation: str
    rationale: str
    signals_assessment: str
    warnings: list[str]
    settled_decisions: list[SettledDecision]
    override_forced: bool
    orchestrator_guidance: str
    robustness: str
    signals: dict[str, Any]
    north_star_actions: list[NorthStarAction]


class GateSignals(TypedDict, total=False):
    robustness: str
    signals: dict[str, Any]
    warnings: list[str]
