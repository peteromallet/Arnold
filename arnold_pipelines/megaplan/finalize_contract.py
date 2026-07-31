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
        "validation_jobs": {
            "type": "array",
            "description": (
                "Harness-owned validation jobs compiled from test_selection and "
                "narrow_tests. The model MUST emit an empty array; the handler "
                "derives deterministic no-file validation jobs."
            ),
            "items": {
                "type": "object",
                "required": [
                    "id",
                    "scope",
                    "command",
                    "environment",
                    "expected_exit_codes",
                    "timeout_seconds",
                    "content_hash_algorithm",
                    "evidence_label",
                    "mutates",
                    "reason",
                ],
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Stable validation-job identifier (VJ-prefixed).",
                    },
                    "kind": {
                        "type": "string",
                        "enum": [
                            "post_execute_suite",
                            "narrow_recheck",
                        ],
                        "description": (
                            "post_execute_suite: authoritative harness-owned suite run. "
                            "narrow_recheck: bounded recheck of a single task's narrow test selectors."
                        ),
                    },
                    "command": {
                        "type": "string",
                        "description": "Deterministic pytest command with timeout prefix.",
                    },
                    "scope": {
                        "type": "string",
                        "description": "Deterministic scope label (post_execute_suite or narrow_recheck:<task_id>).",
                    },
                    "environment": {
                        "type": "object",
                        "description": "Pinned subprocess environment overrides (empty for harness-owned jobs).",
                    },
                    "expected_exit_codes": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Exit codes that mean the validation ran and passed (harness-owned jobs expect [0]).",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Maximum wall-clock seconds for this validation run.",
                    },
                    "content_hash_algorithm": {
                        "type": "string",
                        "enum": ["sha256"],
                        "description": "Content-addressing algorithm for validation evidence.",
                    },
                    "evidence_label": {
                        "type": "string",
                        "description": "Stable label for the content-addressed evidence artifact.",
                    },
                    "mutates": {
                        "type": "boolean",
                        "description": "Always false for harness-owned validation jobs.",
                    },
                    "selectors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Test selectors scoped to one task's write-set blast radius.",
                    },
                    "max_seconds": {
                        "type": "integer",
                        "description": "Maximum wall-clock seconds for this validation run.",
                    },
                    "max_runs": {
                        "type": "integer",
                        "description": "Maximum execution attempts before circuit-open.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why this validation job exists (e.g. task T1 narrow recheck).",
                    },
                    "task_id": {
                        "type": "string",
                        "description": "Source task id for narrow_recheck jobs.",
                    },
                    "writes_files": {
                        "type": "boolean",
                        "description": "Always false for harness-owned validation jobs.",
                    },
                },
            },
        },
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
