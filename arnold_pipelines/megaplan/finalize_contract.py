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
        "task_contract_version": {"type": "integer"},
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
                    "objective": {"type": "string"},
                    "description": {"type": "string"},
                    "status": {"type": "string"},
                    "kind": {"type": "string"},
                    "complexity": {"type": "integer"},
                    "complexity_justification": {"type": "string"},
                    "estimated_minutes": {"type": "integer"},
                    "depends_on": {"type": "array", "items": {"type": "string"}},
                    "dependency_reasons": {"type": "object"},
                    "routing_group": {"type": "string"},
                    "write_set": {
                        "type": "object",
                        "required": ["paths", "complete"],
                        "properties": {
                            "paths": {"type": "array", "items": {"type": "string"}},
                            "complete": {"type": "boolean"},
                        },
                    },
                    "narrow_tests": {
                        "type": "object",
                        "required": ["selectors", "max_seconds", "max_runs"],
                        "properties": {
                            "selectors": {"type": "array", "items": {"type": "string"}},
                            "max_seconds": {"type": "integer"},
                            "max_runs": {"type": "integer"},
                        },
                    },
                    "checkpoint": {
                        "type": "object",
                        "properties": {
                            "required": {"type": "boolean"},
                            "max_interval_seconds": {"type": "integer"},
                            "records": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
            },
        },
        "validation_jobs": {"type": "array"},
        "critique_resolution_coverage": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["finding_id", "task_ids", "resolution_evidence"],
                "properties": {
                    "finding_id": {"type": "string"},
                    "task_ids": {"type": "array", "items": {"type": "string"}},
                    "resolution_evidence": {"type": "string"},
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
