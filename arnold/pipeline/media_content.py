"""Pure reference-metadata validators for Arnold media content types.

This module defines validators for the three media builtin content types
(``video/mp4``, ``audio/wav``, ``application/x-astrid-timeline``) and a
registration helper that installs them into a
:class:`~arnold.pipeline.content_validation.ContentValidatorRegistry`.

Every validator inspects **only** the reference-metadata shape —
``content_type``, ``uri``, optional ``digest``, optional non-negative
integer ``size_bytes``, and optional ``name``.  No validator opens,
parses, fetches, or inspects referenced blob bytes; external content
dereferencing is never performed.

Design contract
---------------
* **Zero megaplan imports.**  This module lives under ``arnold.pipeline``
  and must not import or reference any megaplan module or vocabulary.
* **Validator registration only.**  Validators are callables matching
  :class:`~arnold.pipeline.content_validation.ContentValidator`;
  the public entry point is :func:`register_media_content_validators`.
* **Additive.**  Existing non-media content validators and the
  :class:`~arnold.pipeline.content_validation.ContentValidatorRegistry`
  default (``no_op_content_validator``) are untouched.
"""

from __future__ import annotations

from typing import Any, Mapping

from arnold.pipeline.content_validation import ContentValidatorRegistry
from arnold.pipeline.contract_validation import ValidationDiagnostic, ValidationResult


def _validate_video_mp4(blob_metadata: Mapping[str, Any]) -> ValidationResult:
    """Strict validator for ``video/mp4`` reference metadata.

    Required fields: ``content_type`` (must equal ``"video/mp4"``),
    ``uri`` (non-empty string).

    Optional fields: ``digest`` (string, if present), ``size_bytes``
    (non-negative integer, if present), ``name`` (string, if present).

    This validator never opens, parses, fetches, or inspects the
    referenced video blob.
    """
    diagnostics: list[ValidationDiagnostic] = []

    # --- content_type ---------------------------------------------------
    ct = blob_metadata.get("content_type")
    if ct != "video/mp4":
        diagnostics.append(
            ValidationDiagnostic(
                code="invalid_content_type",
                message=f"expected content_type 'video/mp4', got {ct!r}",
            )
        )

    # --- uri ------------------------------------------------------------
    uri = blob_metadata.get("uri")
    if not isinstance(uri, str) or not uri:
        diagnostics.append(
            ValidationDiagnostic(
                code="missing_uri",
                message="uri must be a non-empty string",
            )
        )

    # --- digest (optional) ----------------------------------------------
    digest = blob_metadata.get("digest")
    if digest is not None and not isinstance(digest, str):
        diagnostics.append(
            ValidationDiagnostic(
                code="invalid_digest",
                message="digest must be a string when present",
            )
        )

    # --- size_bytes (optional, non-negative integer) --------------------
    size_bytes = blob_metadata.get("size_bytes")
    if size_bytes is not None:
        if not isinstance(size_bytes, int) or isinstance(size_bytes, bool):
            diagnostics.append(
                ValidationDiagnostic(
                    code="invalid_size_bytes",
                    message="size_bytes must be an integer when present",
                )
            )
        elif size_bytes < 0:
            diagnostics.append(
                ValidationDiagnostic(
                    code="invalid_size_bytes",
                    message="size_bytes must be non-negative",
                )
            )

    # --- name (optional) ------------------------------------------------
    name = blob_metadata.get("name")
    if name is not None and not isinstance(name, str):
        diagnostics.append(
            ValidationDiagnostic(
                code="invalid_name",
                message="name must be a string when present",
            )
        )

    return ValidationResult(diagnostics=tuple(diagnostics))


def _validate_audio_wav(blob_metadata: Mapping[str, Any]) -> ValidationResult:
    """Strict validator for ``audio/wav`` reference metadata.

    Required fields: ``content_type`` (must equal ``"audio/wav"``),
    ``uri`` (non-empty string).

    Optional fields: ``digest`` (string, if present), ``size_bytes``
    (non-negative integer, if present), ``name`` (string, if present).

    This validator never opens, parses, fetches, or inspects the
    referenced audio blob.
    """
    diagnostics: list[ValidationDiagnostic] = []

    # --- content_type ---------------------------------------------------
    ct = blob_metadata.get("content_type")
    if ct != "audio/wav":
        diagnostics.append(
            ValidationDiagnostic(
                code="invalid_content_type",
                message=f"expected content_type 'audio/wav', got {ct!r}",
            )
        )

    # --- uri ------------------------------------------------------------
    uri = blob_metadata.get("uri")
    if not isinstance(uri, str) or not uri:
        diagnostics.append(
            ValidationDiagnostic(
                code="missing_uri",
                message="uri must be a non-empty string",
            )
        )

    # --- digest (optional) ----------------------------------------------
    digest = blob_metadata.get("digest")
    if digest is not None and not isinstance(digest, str):
        diagnostics.append(
            ValidationDiagnostic(
                code="invalid_digest",
                message="digest must be a string when present",
            )
        )

    # --- size_bytes (optional, non-negative integer) --------------------
    size_bytes = blob_metadata.get("size_bytes")
    if size_bytes is not None:
        if not isinstance(size_bytes, int) or isinstance(size_bytes, bool):
            diagnostics.append(
                ValidationDiagnostic(
                    code="invalid_size_bytes",
                    message="size_bytes must be an integer when present",
                )
            )
        elif size_bytes < 0:
            diagnostics.append(
                ValidationDiagnostic(
                    code="invalid_size_bytes",
                    message="size_bytes must be non-negative",
                )
            )

    # --- name (optional) ------------------------------------------------
    name = blob_metadata.get("name")
    if name is not None and not isinstance(name, str):
        diagnostics.append(
            ValidationDiagnostic(
                code="invalid_name",
                message="name must be a string when present",
            )
        )

    return ValidationResult(diagnostics=tuple(diagnostics))


def _validate_astrid_timeline(blob_metadata: Mapping[str, Any]) -> ValidationResult:
    """Permissive reference validator for ``application/x-astrid-timeline``.

    Required fields: ``content_type`` (must equal
    ``"application/x-astrid-timeline"``), ``uri`` (non-empty string).

    Optional fields: ``digest``, ``size_bytes``, ``name`` — any type is
    accepted (this is the permissive default).

    This validator never opens, parses, fetches, or inspects the
    referenced timeline blob.  Astrid may replace this validator at
    runtime via the registry when a richer schema is available.
    """
    diagnostics: list[ValidationDiagnostic] = []

    # --- content_type ---------------------------------------------------
    ct = blob_metadata.get("content_type")
    if ct != "application/x-astrid-timeline":
        diagnostics.append(
            ValidationDiagnostic(
                code="invalid_content_type",
                message=f"expected content_type 'application/x-astrid-timeline', got {ct!r}",
            )
        )

    # --- uri ------------------------------------------------------------
    uri = blob_metadata.get("uri")
    if not isinstance(uri, str) or not uri:
        diagnostics.append(
            ValidationDiagnostic(
                code="missing_uri",
                message="uri must be a non-empty string",
            )
        )

    # All other fields are permissively accepted (no further validation).
    # Astrid can replace this validator when a concrete schema exists.

    return ValidationResult(diagnostics=tuple(diagnostics))


def register_media_content_validators(registry: ContentValidatorRegistry) -> None:
    """Register the three media builtin validators into *registry*.

    Installs:
    * ``video/mp4`` → strict reference-metadata validator.
    * ``audio/wav`` → strict reference-metadata validator.
    * ``application/x-astrid-timeline`` → permissive reference validator.

    Existing registrations for these content types are **overwritten**
    (the registry's ``register`` method allows re-registration).
    Callers that need fail-safe behaviour should check ``registry``
    before calling this helper.
    """
    registry.register("video/mp4", _validate_video_mp4)
    registry.register("audio/wav", _validate_audio_wav)
    registry.register("application/x-astrid-timeline", _validate_astrid_timeline)
