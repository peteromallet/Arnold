from __future__ import annotations

from arnold.pipeline.content_validation import (
    ContentValidatorRegistry,
    no_op_content_validator,
)
from arnold.pipeline.contract_validation import (
    ValidationDiagnostic,
    ValidationResult,
    validate_payload_against_schema,
)
from arnold.pipeline.types import ContentTypeRegistry


def test_registry_defaults_to_no_op_validator() -> None:
    registry = ContentValidatorRegistry()

    result = registry.validate("image/png", {"uri": "x", "size_bytes": 12})

    assert result == ValidationResult()
    assert registry.get("image/png") is no_op_content_validator


def test_registry_is_instance_local_and_keyed_by_content_type() -> None:
    left = ContentValidatorRegistry()
    right = ContentValidatorRegistry()

    def png_validator(blob_metadata: object) -> ValidationResult:
        del blob_metadata
        return ValidationResult(
            diagnostics=(ValidationDiagnostic(code="bad", message="bad png"),)
        )

    left.register("image/png", png_validator)

    assert "image/png" in left
    assert "image/png" not in right
    assert left.validate("image/png", {"uri": "a"}).diagnostics[0].code == "bad"
    assert right.validate("image/png", {"uri": "a"}) == ValidationResult()


def test_content_validator_failure_is_independent_of_manifest_schema_validation() -> None:
    registry = ContentValidatorRegistry()
    manifest_registry = ContentTypeRegistry()
    manifest_schema = {
        "type": "object",
        "required": ["uri", "size_bytes"],
        "properties": {
            "uri": {"type": "string"},
            "size_bytes": {"type": "integer"},
        },
        "additionalProperties": False,
    }
    blob_metadata = {"uri": "blob://image.png", "size_bytes": 7}

    def fake_image_validator(metadata: object) -> ValidationResult:
        return ValidationResult(
            diagnostics=(
                ValidationDiagnostic(
                    code="blob_digest_missing",
                    message=f"metadata missing digest: {metadata!r}",
                ),
            )
        )

    registry.register("image/png", fake_image_validator)
    manifest_digest = manifest_registry.register("image/png", manifest_schema)
    manifest_validation = validate_payload_against_schema(blob_metadata, manifest_schema)
    content_validation = registry.validate("image/png", blob_metadata)

    assert manifest_digest
    assert manifest_validation.ok
    assert content_validation.ok is False
    assert content_validation.diagnostics[0].code == "blob_digest_missing"


def test_registry_overrides_only_requested_content_type() -> None:
    registry = ContentValidatorRegistry()

    def markdown_validator(blob_metadata: object) -> ValidationResult:
        return ValidationResult(
            diagnostics=(
                ValidationDiagnostic(
                    code="missing_uri",
                    message=str(blob_metadata),
                ),
            )
        )

    registry.register("text/markdown", markdown_validator)

    assert registry.validate("text/markdown", {"name": "notes"}).diagnostics
    assert registry.validate("image/png", {"name": "img"}) == ValidationResult()
