"""Megaplan Incident Ledger — schema, append, projection, and CLI.

This package provides the M1 incident-ledger core:
* ``schema`` — validation and normalization of incident events.
* ``ledger`` — append-only event journal wrapper (T2).
* ``projection`` — deterministic projection rebuild and briefs (T3/T4).
* ``cli`` — ``megaplan incident list/brief`` CLI commands (T5).
"""

from __future__ import annotations

from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
from arnold_pipelines.megaplan.incident.projection import (
    build_brief,
    list_incidents,
    rebuild_projections,
)
from arnold_pipelines.megaplan.incident.schema import validate_incident_event

__all__ = [
    "IncidentLedger",
    "build_brief",
    "list_incidents",
    "rebuild_projections",
    "validate_incident_event",
]
