"""Neutral parsing and resolution helpers for resume-time re-verification."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping
from urllib.parse import unquote, urlparse

from arnold.pipeline.artifact_io import ArtifactIOBlocked, validate_artifact_io
from arnold.pipeline.content_validation import ContentValidatorRegistry
from arnold.pipeline.media_content import register_media_content_validators
from arnold.pipeline.runtime_contract_diagnostics import diagnostic_from_step_io
from arnold.pipeline.schema_registry import ContractSchemaRegistry
from arnold.pipeline.step_io_contract import StepIOContractContext, StepIOOperation
from arnold.pipeline.step_io_policy import CONTRACT_MODE_ENFORCE, resolve_step_io_policy
from arnold.pipeline.types import HumanSuspension


RESUME_REVERIFY_EXTENSION_KEY = "x-arnold-resume"
RESUME_REVERIFY_DECLARATION_KEY = "reverify_produces"
_RESERVED_KEY = RESUME_REVERIFY_EXTENSION_KEY
_NESTED_DECLARATION_KEY = RESUME_REVERIFY_DECLARATION_KEY
_DEFAULT_INVALID_POLICY = "resuspend"
_MEDIA_CONTENT_TYPES = frozenset(
    {
        "video/mp4",
        "audio/wav",
        "application/x-astrid-timeline",
    }
)


@dataclass(frozen=True)
class ResumeReverifyDeclaration:
    """Parsed declaration describing what to re-verify on resume."""

    port: str | None = None
    content_type: str | None = None
    artifact_path: str | None = None
    artifact_ref: Mapping[str, Any] | None = None
    invalid_policy: str = _DEFAULT_INVALID_POLICY


@dataclass(frozen=True)
class ResumeReverifyResult:
    """Outcome of parsing or resolving a resume re-verification declaration."""

    outcome: Literal["no_op", "valid", "invalid"]
    declaration: ResumeReverifyDeclaration | None = None
    resolved_artifact_path: str | None = None
    diagnostic: Mapping[str, Any] | None = None


def parse_resume_reverify_declaration(
    suspension: HumanSuspension,
) -> ResumeReverifyResult:
    """Parse ``x-arnold-resume`` from a :class:`HumanSuspension`.

    ``no_op`` is returned only when the reserved extension key is absent.
    Any present but malformed declaration fails closed as ``invalid``.
    """

    if not isinstance(suspension, HumanSuspension):
        raise TypeError(
            "parse_resume_reverify_declaration expects HumanSuspension; "
            "deserialize dict payloads with HumanSuspension.from_json() first"
        )

    schema = suspension.resume_input_schema
    if _RESERVED_KEY not in schema:
        return ResumeReverifyResult(outcome="no_op")

    raw_extension = schema.get(_RESERVED_KEY)
    if not isinstance(raw_extension, Mapping):
        return _invalid_result(
            "malformed_declaration",
            f"{_RESERVED_KEY} must be a JSON object",
        )

    raw_declaration = raw_extension
    if _NESTED_DECLARATION_KEY in raw_extension:
        nested = raw_extension.get(_NESTED_DECLARATION_KEY)
        if not isinstance(nested, Mapping):
            return _invalid_result(
                "malformed_declaration",
                f"{_RESERVED_KEY}.{_NESTED_DECLARATION_KEY} must be a JSON object",
            )
        raw_declaration = nested

    try:
        port = _optional_string(raw_declaration, "port")
        content_type = _optional_string(raw_declaration, "content_type")
        artifact_path = _optional_string(raw_declaration, "artifact_path")
        invalid_policy = _optional_string(
            raw_declaration,
            "invalid_policy",
            default=_DEFAULT_INVALID_POLICY,
        )
    except _ResumeDeclarationError as exc:
        return exc.result

    raw_artifact_ref = raw_declaration.get("artifact_ref")
    artifact_ref: dict[str, Any] | None = None
    if raw_artifact_ref is not None:
        if not isinstance(raw_artifact_ref, Mapping):
            return _invalid_result(
                "malformed_declaration",
                "artifact_ref must be a JSON object when provided",
            )
        artifact_ref = dict(raw_artifact_ref)
        if _artifact_ref_name(artifact_ref) is None:
            return _invalid_result(
                "malformed_declaration",
                "artifact_ref.name must be a string when artifact_ref is provided",
            )

    if (
        port is None
        and artifact_path is None
        and artifact_ref is None
    ):
        return _invalid_result(
            "malformed_declaration",
            "declaration must specify artifact_path, artifact_ref, or port",
        )

    return ResumeReverifyResult(
        outcome="valid",
        declaration=ResumeReverifyDeclaration(
            port=port,
            content_type=content_type,
            artifact_path=artifact_path,
            artifact_ref=artifact_ref,
            invalid_policy=invalid_policy,
        ),
    )


def resolve_resume_reverify_artifact(
    suspension: HumanSuspension,
    declaration: ResumeReverifyDeclaration,
    *,
    artifact_root: str | Path,
) -> ResumeReverifyResult:
    """Resolve the declared artifact path without consulting cursor bodies."""

    root = Path(artifact_root).resolve()
    if declaration.artifact_path is not None:
        return _resolve_declared_artifact_path(
            declaration=declaration,
            artifact_root=root,
        )

    ref_name = _artifact_ref_name(declaration.artifact_ref)
    match_name = ref_name if ref_name is not None else declaration.port
    if match_name is None:
        return _invalid_result(
            "artifact_unresolved",
            "declaration did not provide a resolvable artifact selector",
            declaration=declaration,
        )

    matches = [
        ref for ref in suspension.display_refs
        if ref.name == match_name
    ]
    if not matches:
        return _invalid_result(
            "artifact_unresolved",
            f"no display_ref matched name {match_name!r}",
            declaration=declaration,
        )
    if len(matches) > 1:
        return _invalid_result(
            "artifact_ambiguous",
            f"multiple display_refs matched name {match_name!r}",
            declaration=declaration,
        )

    uri_path = _file_uri_to_path(matches[0].uri)
    if uri_path is None:
        return _invalid_result(
            "artifact_unresolved",
            f"display_ref {match_name!r} does not reference a file URI",
            declaration=declaration,
        )

    return _finalize_resolved_path(
        candidate=uri_path,
        artifact_root=root,
        declaration=declaration,
    )


def _resolve_declared_artifact_path(
    *,
    declaration: ResumeReverifyDeclaration,
    artifact_root: Path,
) -> ResumeReverifyResult:
    raw_path = declaration.artifact_path
    assert raw_path is not None
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return _invalid_result(
            "artifact_path_invalid",
            "artifact_path must be relative to artifact_root",
            declaration=declaration,
        )
    return _finalize_resolved_path(
        candidate=artifact_root / candidate,
        artifact_root=artifact_root,
        declaration=declaration,
    )


def _finalize_resolved_path(
    *,
    candidate: Path,
    artifact_root: Path,
    declaration: ResumeReverifyDeclaration,
) -> ResumeReverifyResult:
    try:
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(artifact_root)
    except ValueError:
        return _invalid_result(
            "artifact_path_invalid",
            "resolved artifact path escapes artifact_root",
            declaration=declaration,
        )

    if not resolved.exists():
        return _invalid_result(
            "artifact_missing",
            f"resolved artifact does not exist: {resolved}",
            declaration=declaration,
        )
    if not resolved.is_file():
        return _invalid_result(
            "artifact_not_file",
            f"resolved artifact is not a file: {resolved}",
            declaration=declaration,
        )

    return ResumeReverifyResult(
        outcome="valid",
        declaration=declaration,
        resolved_artifact_path=str(resolved),
    )


def reverify_resume_produces(
    suspension: HumanSuspension,
    *,
    artifact_root: str | Path,
    schema_registry: ContractSchemaRegistry | None = None,
    producer_stage: str = "resume",
) -> ResumeReverifyResult:
    """Parse, resolve, and re-verify a declared resumed artifact JSON."""

    parsed = parse_resume_reverify_declaration(suspension)
    if parsed.outcome != "valid" or parsed.declaration is None:
        return parsed

    resolved = resolve_resume_reverify_artifact(
        suspension,
        parsed.declaration,
        artifact_root=artifact_root,
    )
    if resolved.outcome != "valid" or resolved.resolved_artifact_path is None:
        return resolved

    artifact_path = Path(resolved.resolved_artifact_path)
    try:
        raw_json = json.loads(artifact_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _invalid_result(
            "artifact_missing",
            f"resolved artifact does not exist: {artifact_path}",
            declaration=parsed.declaration,
        )
    except OSError as exc:
        return _invalid_result(
            "artifact_unreadable",
            f"resolved artifact could not be read: {artifact_path}: {exc}",
            declaration=parsed.declaration,
        )
    except json.JSONDecodeError as exc:
        return _invalid_result(
            "artifact_json_invalid",
            f"resolved artifact is not valid JSON: {artifact_path}: {exc.msg}",
            declaration=parsed.declaration,
        )

    if not isinstance(raw_json, Mapping):
        return _invalid_result(
            "artifact_json_shape_invalid",
            "resolved artifact JSON must be an object at the top level",
            declaration=parsed.declaration,
        )

    policy = resolve_step_io_policy(
        configured_mode=CONTRACT_MODE_ENFORCE,
        producer_typed=True,
        consumer_typed=True,
    )
    if not (policy.enforcement_eligible and policy.effective_mode == CONTRACT_MODE_ENFORCE):
        raise AssertionError("resume reverify requires enforce-eligible READ policy")

    context = StepIOContractContext(
        operation=StepIOOperation.READ,
        registry=schema_registry,
    )
    try:
        validated = validate_artifact_io(
            raw_json,
            operation=StepIOOperation.READ,
            policy=policy,
            contract_context=context,
            artifact=str(artifact_path),
        )
    except ArtifactIOBlocked as exc:
        return ResumeReverifyResult(
            outcome="invalid",
            declaration=parsed.declaration,
            resolved_artifact_path=str(artifact_path),
            diagnostic=_step_io_blocked_diagnostic(
                exc=exc,
                declaration=parsed.declaration,
                producer_stage=producer_stage,
            ),
        )

    if parsed.declaration.content_type not in _MEDIA_CONTENT_TYPES:
        if validated.classification.value == "legacy_unknown":
            return _invalid_result(
                "typed_envelope_required",
                "non-media resumed artifacts must be C1 typed envelopes",
                declaration=parsed.declaration,
            )
        return ResumeReverifyResult(
            outcome="valid",
            declaration=parsed.declaration,
            resolved_artifact_path=str(artifact_path),
        )

    blob_metadata = validated.value if isinstance(validated.value, Mapping) else raw_json
    if not isinstance(blob_metadata, Mapping):
        return _invalid_result(
            "media_metadata_invalid",
            "media resumed artifacts must decode to reference metadata objects",
            declaration=parsed.declaration,
        )
    if "content_type" not in blob_metadata:
        return _invalid_result(
            "media_metadata_invalid",
            "media resumed artifact metadata must include content_type",
            declaration=parsed.declaration,
        )

    registry = ContentValidatorRegistry()
    register_media_content_validators(registry)
    media_result = registry.validate(parsed.declaration.content_type, blob_metadata)
    if not media_result.ok:
        return ResumeReverifyResult(
            outcome="invalid",
            declaration=parsed.declaration,
            resolved_artifact_path=str(artifact_path),
            diagnostic=_media_validation_diagnostic(
                declaration=parsed.declaration,
                producer_stage=producer_stage,
                diagnostics=media_result.diagnostics,
            ),
        )

    return ResumeReverifyResult(
        outcome="valid",
        declaration=parsed.declaration,
        resolved_artifact_path=str(artifact_path),
    )


def _artifact_ref_name(artifact_ref: Mapping[str, Any] | None) -> str | None:
    if artifact_ref is None:
        return None
    name = artifact_ref.get("name")
    return name if isinstance(name, str) else None


def _file_uri_to_path(uri: str) -> Path | None:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    if parsed.netloc not in ("", "localhost"):
        return None
    return Path(unquote(parsed.path))


def _optional_string(
    data: Mapping[str, Any],
    key: str,
    *,
    default: str | None = None,
) -> str | None:
    value = data.get(key, default)
    if value is None:
        return None
    if not isinstance(value, str):
        raise_value = _invalid_result(
            "malformed_declaration",
            f"{key} must be a string when provided",
        )
        raise _ResumeDeclarationError(raise_value)
    return value


def _invalid_result(
    code: str,
    detail: str,
    *,
    declaration: ResumeReverifyDeclaration | None = None,
) -> ResumeReverifyResult:
    diagnostic = {
        "kind": "resume_reverify",
        "code": code,
        "detail": detail,
    }
    return ResumeReverifyResult(
        outcome="invalid",
        declaration=declaration,
        diagnostic=diagnostic,
    )


class _ResumeDeclarationError(ValueError):
    def __init__(self, result: ResumeReverifyResult) -> None:
        super().__init__(str(result.diagnostic))
        self.result = result


def _step_io_blocked_diagnostic(
    *,
    exc: ArtifactIOBlocked,
    declaration: ResumeReverifyDeclaration,
    producer_stage: str,
) -> Mapping[str, Any]:
    decision = exc.decision
    if decision is None and exc.result is not None:
        decision = exc.result.decision
    runtime = (
        diagnostic_from_step_io(
            decision=decision,
            producer_stage=producer_stage or "resume",
            consumer_stage="resume_reverify",
            seam_id=declaration.port,
            producer_port=declaration,
            consumer_port=declaration,
        )
        if decision is not None
        else None
    )
    if runtime is None:
        return {
            "kind": "resume_reverify",
            "code": "typed_contract_blocked",
            "detail": str(exc),
            "runtime_contract": {
                "producer_stage": producer_stage or "resume",
                "consumer_stage": "resume_reverify",
                "seam_id": declaration.port,
                "logical_type": "unknown",
                "schema_version": "unknown",
                "failure_code": "typed_contract_blocked",
                "suggested_author_action": "Repair the resumed artifact so it satisfies the declared typed contract before publishing it.",
                "detail": str(exc),
            },
        }
    return {
        "kind": "resume_reverify",
        "code": "typed_contract_blocked",
        "detail": runtime.message,
        "runtime_contract": {
            "producer_stage": runtime.producer_stage,
            "consumer_stage": runtime.consumer_stage,
            "seam_id": runtime.seam_id,
            "logical_type": runtime.logical_type,
            "schema_version": runtime.schema_version,
            "failure_code": runtime.failure_code,
            "suggested_author_action": runtime.suggested_author_action,
            "detail": runtime.detail,
        },
    }


def _media_validation_diagnostic(
    *,
    declaration: ResumeReverifyDeclaration,
    producer_stage: str,
    diagnostics: tuple[Any, ...],
) -> Mapping[str, Any]:
    serialized = [
        {
            "code": str(getattr(diagnostic, "code", "unknown")),
            "message": str(getattr(diagnostic, "message", "unknown")),
            "payload_pointer": str(getattr(diagnostic, "payload_pointer", "") or ""),
            "schema_pointer": str(getattr(diagnostic, "schema_pointer", "") or ""),
        }
        for diagnostic in diagnostics
    ]
    first = serialized[0] if serialized else {
        "code": "media_metadata_invalid",
        "message": "media metadata validation failed",
        "payload_pointer": "",
        "schema_pointer": "",
    }
    return {
        "kind": "resume_reverify",
        "code": "media_metadata_invalid",
        "detail": first["message"],
        "runtime_contract": {
            "producer_stage": producer_stage or "resume",
            "consumer_stage": "resume_reverify",
            "seam_id": declaration.port,
            "logical_type": declaration.content_type or "unknown",
            "schema_version": "media_reference_metadata",
            "failure_code": first["code"],
            "suggested_author_action": "Fix the resumed media reference metadata so it matches the declared content_type without changing the referenced blob bytes.",
            "detail": first["message"],
        },
        "validation_diagnostics": serialized,
    }


__all__ = [
    "ResumeReverifyDeclaration",
    "ResumeReverifyResult",
    "parse_resume_reverify_declaration",
    "reverify_resume_produces",
    "resolve_resume_reverify_artifact",
]
