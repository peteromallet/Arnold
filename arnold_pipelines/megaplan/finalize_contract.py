"""Model-owned finalize boundary contract shared by producer and handler."""

from __future__ import annotations

from typing import Any


# This schema describes the model's file-fill output before the handler adds
# validation, execution evidence, and baseline-test metadata. Keeping it here
# lets template production, scratch promotion, and input validation project
# from the same object without creating a prompt/handler import cycle.
FINALIZE_MODEL_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "tasks",
        "sense_checks",
        "watch_items",
        "user_actions",
        "meta_commentary",
    ],
    "properties": {
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "id",
                    "description",
                    "status",
                    "complexity",
                    "complexity_justification",
                ],
                "properties": {
                    "id": {"type": "string"},
                    "description": {"type": "string"},
                    "status": {"type": "string"},
                    "complexity": {"type": "integer"},
                    "complexity_justification": {"type": "string"},
                },
            },
        },
        "sense_checks": {"type": "array"},
        "watch_items": {"type": "array"},
        "meta_commentary": {"type": "string"},
        "user_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "description", "phase"],
                "properties": {
                    "id": {"type": "string"},
                    "description": {"type": "string"},
                    "phase": {"type": "string"},
                },
            },
        },
    },
}


__all__ = ["FINALIZE_MODEL_OUTPUT_SCHEMA"]
