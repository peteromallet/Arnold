"""Compatibility shim: moved to ``arnold.pipelines.megaplan.step_io_policy_adapter``.

This module re-exports the canonical implementation so that legacy imports
continue to work during the M7 purge window. New code should import from the
canonical path.
"""

from __future__ import annotations

from arnold.pipelines.megaplan.step_io_policy_adapter import (
    STEP_IO_POLICY_ENV,
    STEP_IO_READ_LENIENT_ENV,
    has_megaplan_step_io_self_validation_marker,
    load_megaplan_step_io_policy,
    load_megaplan_step_io_policy_path,
    megaplan_policy_for_envelope,
    megaplan_step_io_policy_path,
    megaplan_step_io_read_lenient_escape_on,
    record_megaplan_step_io_self_validation_marker,
    resolve_megaplan_step_io_policy,
    write_megaplan_step_io_policy,
)

__all__ = [
    "STEP_IO_POLICY_ENV",
    "STEP_IO_READ_LENIENT_ENV",
    "has_megaplan_step_io_self_validation_marker",
    "load_megaplan_step_io_policy",
    "load_megaplan_step_io_policy_path",
    "megaplan_policy_for_envelope",
    "megaplan_step_io_policy_path",
    "megaplan_step_io_read_lenient_escape_on",
    "record_megaplan_step_io_self_validation_marker",
    "resolve_megaplan_step_io_policy",
    "write_megaplan_step_io_policy",
]
