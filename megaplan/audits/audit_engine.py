"""Compatibility facade for the canonical audit engine module."""

from arnold.pipelines.megaplan.audits.audit_engine import *  # noqa: F401,F403
from arnold.pipelines.megaplan.audits.audit_engine import _compute_totals, _empty_totals, _next_index

__all__ = [
    "AUDIT_FILE",
    "_compute_totals",
    "_empty_totals",
    "_next_index",
    "aggregate_tiebreaker_audit",
    "load_tiebreaker_audit",
    "record_tiebreaker_audit",
    "render_audit_report",
    "resolve_plan_dir",
]
