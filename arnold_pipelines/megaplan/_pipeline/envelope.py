"""Re-export shim: arnold_pipelines.megaplan._pipeline.envelope → arnold.runtime.envelope.

All canonical symbols live in ``arnold.runtime.envelope``.  This module is a
thin re-export so existing megaplan importers continue to resolve without
source changes.  No local constants, no wrappers, no legacy env-var overrides.

Dependency direction: megaplan → arnold.runtime (never the reverse).
"""
from __future__ import annotations

from arnold.runtime.envelope import (
    EMPTY_ENVELOPE,
    ENVELOPE_ENV_VAR,
    ENVELOPE_IN_FILENAME,
    ENVELOPE_OUT_FILENAME,
    ENVELOPE_STDERR_TAG,
    EnvelopeDroppedError,
    LeaseIdConflict,
    RunEnvelope,
    _envelope_ctx,
    _fanout_active_ctx,
    consume_envelope_in,
    current_envelope,
    format_envelope_stderr_tag,
    make_envelope,
    parse_envelope_stderr_tag,
    read_envelope_out,
    write_envelope_in,
    write_envelope_out,
)

__all__ = [
    "RunEnvelope",
    "EMPTY_ENVELOPE",
    "make_envelope",
    "current_envelope",
    "EnvelopeDroppedError",
    "LeaseIdConflict",
    "_envelope_ctx",
    "_fanout_active_ctx",
    "ENVELOPE_ENV_VAR",
    "ENVELOPE_STDERR_TAG",
    "ENVELOPE_IN_FILENAME",
    "ENVELOPE_OUT_FILENAME",
    "write_envelope_in",
    "consume_envelope_in",
    "write_envelope_out",
    "read_envelope_out",
    "format_envelope_stderr_tag",
    "parse_envelope_stderr_tag",
]
