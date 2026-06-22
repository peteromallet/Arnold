"""Repair-agent protocol and fake/degraded implementations."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from arnold_pipelines.megaplan.pipelines.live_supervisor.model import (
    Incident,
    RepairRecommendation,
)


class RepairUnavailable(Exception):
    """Raised when no repair agent credentials or launcher is available."""


class RepairAgent(Protocol):
    """Bounded repair-agent interface."""

    def diagnose_and_recommend(
        self,
        incident: Incident,
        diagnostic_bundle: Mapping[str, Any],
    ) -> RepairRecommendation:
        """Return a recommended repair command for the incident."""
        ...


class FakeRepairAgent:
    """Deterministic repair agent for tests."""

    def __init__(
        self,
        recommendation_map: Mapping[str, RepairRecommendation] | None,
        default: RepairRecommendation | None = None,
    ) -> None:
        self._map = recommendation_map or {}
        self._default = default

    def diagnose_and_recommend(
        self,
        incident: Incident,
        diagnostic_bundle: Mapping[str, Any],
    ) -> RepairRecommendation:
        plan_id = incident.plan_entry.plan_id
        if plan_id in self._map:
            return self._map[plan_id]
        if self._default is not None:
            return self._default
        return RepairRecommendation(command="doctor", context={"plan_name": incident.plan_entry.plan_name})


class HermesRepairAgent:
    """Repair agent backed by a Hermes/Codex-style model launcher.

    When the launcher handle is absent, raises ``RepairUnavailable`` so the
    pipeline degrades to report-only rather than crashing.
    """

    def __init__(self, launcher: Any | None = None) -> None:
        self._launcher = launcher

    def diagnose_and_recommend(
        self,
        incident: Incident,
        diagnostic_bundle: Mapping[str, Any],
    ) -> RepairRecommendation:
        if self._launcher is None:
            raise RepairUnavailable("no repair-agent launcher configured")
        # Real launch would go here; the protocol keeps the surface testable.
        raise NotImplementedError("HermesRepairAgent.launch not implemented in MVP")


__all__ = [
    "RepairAgent",
    "RepairUnavailable",
    "FakeRepairAgent",
    "HermesRepairAgent",
]
