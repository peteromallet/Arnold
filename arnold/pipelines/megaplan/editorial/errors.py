"""Shared exceptions for Store-backed editorial operations."""

from __future__ import annotations

from typing import Any


class EditorialError(RuntimeError):
    """Base class for editorial operation failures."""

    code = "editorial_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {"error": self.code, "message": str(self), "details": self.details}


class EditorialNotFound(EditorialError):
    code = "not_found"


class EditorialValidationError(EditorialError):
    code = "validation_error"


class EditorialWorkflowError(EditorialError):
    code = "workflow_error"
