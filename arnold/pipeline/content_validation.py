"""Content-type keyed validation hooks for blob-reference metadata shapes only."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from arnold.pipeline.contract_validation import ValidationResult


class ContentValidator(Protocol):
    """Callable validator for caller-provided blob metadata/reference shapes."""

    def __call__(self, blob_metadata: Mapping[str, Any]) -> ValidationResult: ...


def no_op_content_validator(blob_metadata: Mapping[str, Any]) -> ValidationResult:
    """Accept any caller-provided metadata without inspecting external content."""

    del blob_metadata
    return ValidationResult()


@dataclass
class ContentValidatorRegistry:
    """Instance-local registry distinct from ContentTypeRegistry schema mapping."""

    _validators: dict[str, ContentValidator] = field(default_factory=dict)
    default_validator: ContentValidator = no_op_content_validator

    def register(self, content_type: str, validator: ContentValidator) -> None:
        if not content_type:
            raise ValueError("content_type must be non-empty")
        self._validators[content_type] = validator

    def get(self, content_type: str) -> ContentValidator:
        return self._validators.get(content_type, self.default_validator)

    def validate(self, content_type: str, blob_metadata: Mapping[str, Any]) -> ValidationResult:
        return self.get(content_type)(blob_metadata)

    def __contains__(self, content_type: str) -> bool:
        return content_type in self._validators

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._validators))
