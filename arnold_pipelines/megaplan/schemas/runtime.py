"""JSON schema definitions for megaplan step outputs."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from arnold_pipelines.megaplan.north_star_actions import (
    NORTH_STAR_ACTION_ADDRESSED_SCHEMA,
    NORTH_STAR_ACTION_SCHEMA,
)

STANCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "challenge_engaged": {"type": "string"},
        "angle_taken": {"type": "string"},
        "what_changed": {"type": "string"},
    },
    "required": ["challenge_engaged", "angle_taken", "what_changed"],
}

STOP_SIGNAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "requested": {"type": "boolean"},
        "defense": {"type": "string"},
    },
    "required": ["requested", "defense"],
}

PREP_RESEARCH_AREA_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "area": {"type": "string"},
        "brief": {"type": "string"},
        "suggested_files": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["id", "area", "brief", "suggested_files"],
}

PREP_RESEARCH_FINDING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "area": {"type": "string"},
        "brief": {"type": "string"},
        "status": {
            "type": "string",
            "enum": ["complete", "partial", "timed_out", "error", "not_needed"],
        },
        "findings": {"type": "array", "items": {"type": "string"}},
        "files": {"type": "array", "items": {"type": "string"}},
        "code_refs": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "error": {"type": "string"},
    },
    "required": ["area", "brief", "status", "findings", "files", "code_refs", "confidence"],
}

TOKEN_USAGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "cost_usd": {"type": "number"},
        "prompt_tokens": {"type": "integer"},
        "completion_tokens": {"type": "integer"},
        "total_tokens": {"type": "integer"},
        "elapsed_time_ms": {"type": "integer"},
    },
    "required": [
        "cost_usd",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "elapsed_time_ms",
    ],
}

TEST_BLAST_RADIUS_SELECTOR_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "kind": {"type": "string"},
        "value": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["kind", "value", "reason"],
}

TEST_BLAST_RADIUS_IMPORT_GRAPH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "degraded": {"type": "boolean"},
        "dependent_tests": {"type": "integer"},
        "unresolved": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["degraded", "dependent_tests", "unresolved"],
}

TEST_BLAST_RADIUS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "strategy": {"type": "string", "enum": ["none", "scoped", "full"]},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "selectors": {
            "type": "array",
            "items": deepcopy(TEST_BLAST_RADIUS_SELECTOR_SCHEMA),
        },
        "changed_surfaces": {"type": "array", "items": {"type": "string"}},
        "always_run": {"type": "array", "items": {"type": "string"}},
        "full_suite_fallback": {"type": "boolean"},
        "rationale": {"type": "string"},
        "import_graph": deepcopy(TEST_BLAST_RADIUS_IMPORT_GRAPH_SCHEMA),
    },
    "required": [
        "strategy",
        "confidence",
        "selectors",
        "changed_surfaces",
        "always_run",
        "full_suite_fallback",
        "rationale",
        "import_graph",
    ],
}

CRITIQUE_EVALUATOR_CHECK_IDS: list[str] = [
    "issue_hints",
    "correctness",
    "scope",
    "all_locations",
    "callers",
    "conventions",
    "verification",
    "criteria_quality",
    "prerequisite_ordering",
]


def _build_critique_evaluator_schema() -> dict[str, Any]:
    """Single source of truth for stored critique-evaluator artifacts.

    This schema must remain compatible with:
    - legacy stored selections routed by `critic_model`
    - current catalog selections routed by `complexity`
    - current additive `"other"` custom-area selections
    """
    check_ids = CRITIQUE_EVALUATOR_CHECK_IDS
    selectable_check_ids = [*check_ids, "other"]

    legacy_selection_schema = {
        "x-preserve-explicit-required": True,
        "type": "object",
        "properties": {
            "check_id": {"type": "string", "enum": selectable_check_ids},
            "critic_model": {"type": "string"},
            "why": {"type": "string"},
            "area": {"type": "string"},
        },
        "required": ["check_id", "critic_model", "why"],
        "additionalProperties": False,
    }
    catalog_selection_schema = {
        "x-preserve-explicit-required": True,
        "type": "object",
        "properties": {
            "check_id": {"type": "string", "enum": check_ids},
            "complexity": {"type": "integer", "minimum": 1, "maximum": 10},
            "complexity_justification": {"type": "string"},
            "area": {"type": "string"},
        },
        "required": ["check_id", "complexity", "complexity_justification"],
        "additionalProperties": False,
    }
    other_selection_schema = {
        "x-preserve-explicit-required": True,
        "type": "object",
        "properties": {
            "check_id": {"type": "string", "const": "other"},
            "area": {"type": "string"},
            "why": {"type": "string"},
            "complexity": {"type": "integer", "minimum": 1, "maximum": 10},
            "complexity_justification": {"type": "string"},
        },
        "required": [
            "check_id",
            "area",
            "why",
            "complexity",
            "complexity_justification",
        ],
        "additionalProperties": False,
    }
    return {
        "x-preserve-explicit-required": True,
        "type": "object",
        "properties": {
            "selections": {
                "type": "array",
                "items": {
                    "oneOf": [
                        legacy_selection_schema,
                        catalog_selection_schema,
                        other_selection_schema,
                    ]
                },
            },
            "skipped": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "check_id": {"type": "string", "enum": check_ids},
                        "why": {"type": "string"},
                    },
                    "required": ["check_id", "why"],
                    "additionalProperties": False,
                },
            },
            "evaluator_model": {"type": "string"},
            "flag_verifications": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "flag_id": {"type": "string"},
                        "lens": {"type": "string"},
                        "outcome": {
                            "type": "string",
                            "enum": ["verified", "open", "accepted_tradeoff"],
                        },
                        "rationale": {"type": "string"},
                    },
                    "required": ["flag_id", "lens", "outcome", "rationale"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["selections", "skipped", "evaluator_model"],
        "additionalProperties": False,
    }


SCHEMAS: dict[str, dict[str, Any]] = {
    "plan.json": {
        "type": "object",
        "properties": {
            "plan": {
                "type": "string",
                "description": (
                    "Complete plan markdown. Must include exactly one H1 title, "
                    "a `## Overview` section, at least one step heading in the "
                    "form `## Step N: ...` or `### Step N: ...` under a phase, "
                    "and `## Execution Order` or `## Validation Order`. Do not "
                    "return a prose numbered list without Step headings."
                ),
            },
            "questions": {"type": "array", "items": {"type": "string"}},
            "success_criteria": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "criterion": {"type": "string"},
                        "priority": {"type": "string", "enum": ["must", "should", "info"]},
                        "requires": {"type": "array", "items": {"type": "string"}, "default": []},
                    },
                    "required": ["criterion", "priority"],
                },
            },
            "assumptions": {"type": "array", "items": {"type": "string"}},
            "changed_surfaces": {"type": "array", "items": {"type": "string"}},
            "test_blast_radius": deepcopy(TEST_BLAST_RADIUS_SCHEMA),
        },
        "required": ["plan", "questions", "success_criteria", "assumptions"],
    },
    "prep.json": {
        "x-preserve-explicit-required": True,
        "type": "object",
        "properties": {
            "skip": {"type": "boolean"},
            "task_summary": {"type": "string"},
            "key_evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "point": {"type": "string"},
                        "source": {"type": "string"},
                        "relevance": {"type": "string", "enum": ["high", "medium", "low"]},
                    },
                    "required": ["point", "source", "relevance"],
                },
            },
            "relevant_code": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string"},
                        "why": {"type": "string"},
                        "functions": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["file_path", "why", "functions"],
                },
            },
            "test_expectations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "test_id": {"type": "string"},
                        "what_it_checks": {"type": "string"},
                        "status": {"type": "string", "enum": ["fail_to_pass", "pass_to_pass"]},
                    },
                    "required": ["test_id", "what_it_checks", "status"],
                },
            },
            "constraints": {"type": "array", "items": {"type": "string"}},
            "primary_criterion": {"type": "string"},
            "suggested_approach": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "array", "items": {"type": "string"}},
                ]
            },
            "open_questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "severity": {
                            "type": "string",
                            "enum": ["blocking", "assume_and_proceed"],
                        },
                        "question": {"type": "string"},
                        "assumption": {"type": "string"},
                    },
                    "required": ["severity", "question"],
                },
            },
        },
        "required": [
            "skip",
            "task_summary",
            "key_evidence",
            "relevant_code",
            "test_expectations",
            "constraints",
            "suggested_approach",
        ],
    },
    "prep_triage.json": {
        "type": "object",
        "properties": {
            "triage_framing": {"type": "string"},
            "areas": {"type": "array", "items": deepcopy(PREP_RESEARCH_AREA_SCHEMA)},
        },
        "required": ["triage_framing", "areas"],
    },
    "research.json": {
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "items": deepcopy(PREP_RESEARCH_FINDING_SCHEMA),
            },
        },
        "required": ["findings"],
    },
    "prep_research_finding.json": deepcopy(PREP_RESEARCH_FINDING_SCHEMA),
    "prep_metrics.json": {
        "type": "object",
        "properties": {
            "area_count": {"type": "integer"},
            "fanout_count": {"type": "integer"},
            "completed_count": {"type": "integer"},
            "partial_count": {"type": "integer"},
            "timed_out_count": {"type": "integer"},
            "error_count": {"type": "integer"},
            "missed_units": {"type": "array", "items": {"type": "string"}},
            "total_cost_usd": {"type": "number"},
            "prompt_tokens": {"type": "integer"},
            "completion_tokens": {"type": "integer"},
            "total_tokens": {"type": "integer"},
            "elapsed_time_ms": {"type": "integer"},
            "files": {"type": "array", "items": {"type": "string"}},
            "code_refs": {"type": "array", "items": {"type": "string"}},
            "gap_notes": {"type": "array", "items": {"type": "string"}},
            "contradiction_notes": {"type": "array", "items": {"type": "string"}},
            "overlap_groups": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": ["file", "code_ref"]},
                        "value": {"type": "string"},
                        "areas": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["kind", "value", "areas"],
                },
            },
            "cross_reference": {
                "type": "object",
                "properties": {
                    "performed": {"type": "boolean"},
                    "checked_files": {"type": "array", "items": {"type": "string"}},
                    "existing_files": {"type": "array", "items": {"type": "string"}},
                    "missing_files": {"type": "array", "items": {"type": "string"}},
                    "shared_files": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "performed",
                    "checked_files",
                    "existing_files",
                    "missing_files",
                    "shared_files",
                ],
            },
            "stage_metrics": {
                "type": "object",
                "properties": {
                    "triage": deepcopy(TOKEN_USAGE_SCHEMA),
                    "fanout": deepcopy(TOKEN_USAGE_SCHEMA),
                    "distill": deepcopy(TOKEN_USAGE_SCHEMA),
                },
                "required": ["triage", "fanout", "distill"],
            },
            "per_unit": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "area": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["complete", "partial", "timed_out", "error", "not_needed"],
                        },
                        "elapsed_time_ms": {"type": "integer"},
                        "files": {"type": "array", "items": {"type": "string"}},
                        "code_refs": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["area", "status", "elapsed_time_ms", "files", "code_refs"],
                },
            },
        },
        "required": [
            "area_count",
            "fanout_count",
            "completed_count",
            "partial_count",
            "timed_out_count",
            "error_count",
            "missed_units",
            "total_cost_usd",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "elapsed_time_ms",
            "files",
            "code_refs",
            "gap_notes",
            "contradiction_notes",
            "overlap_groups",
            "cross_reference",
            "stage_metrics",
            "per_unit",
        ],
    },
    "revise.json": {
        "x-preserve-explicit-required": True,
        "type": "object",
        "properties": {
            "plan": {"type": "string"},
            "changes_summary": {"type": "string"},
            "flags_addressed": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "resolution": {"type": "string", "enum": ["addressed", "rejected"]},
                        "reason": {"type": "string"},
                        "where": {"type": "string"},
                    },
                    "required": ["id", "resolution", "reason"],
                    "additionalProperties": False,
                },
            },
            "north_star_actions_addressed": {
                "type": "array",
                "items": deepcopy(NORTH_STAR_ACTION_ADDRESSED_SCHEMA),
            },
            "assumptions": {"type": "array", "items": {"type": "string"}},
            "success_criteria": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "criterion": {"type": "string"},
                        "priority": {"type": "string", "enum": ["must", "should", "info"]},
                        "requires": {"type": "array", "items": {"type": "string"}, "default": []},
                    },
                    "required": ["criterion", "priority"],
                },
            },
            "questions": {"type": "array", "items": {"type": "string"}},
            "changed_surfaces": {"type": "array", "items": {"type": "string"}},
            "test_blast_radius": deepcopy(TEST_BLAST_RADIUS_SCHEMA),
        },
        "required": [
            "plan",
            "changes_summary",
            "flags_addressed",
            "assumptions",
            "success_criteria",
            "questions",
        ],
    },
    "gate.json": {
        "x-preserve-explicit-required": True,
        "type": "object",
        "properties": {
            "recommendation": {
                "type": "string",
                "enum": ["PROCEED", "ITERATE", "ESCALATE", "TIEBREAKER"],
            },
            "rationale": {"type": "string"},
            "signals_assessment": {"type": "string"},
            "warnings": {"type": "array", "items": {"type": "string"}},
            "settled_decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "decision": {"type": "string"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["id", "decision", "rationale"],
                },
            },
            "flag_resolutions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "flag_id": {"type": "string"},
                        "action": {
                            "type": "string",
                            "enum": ["dispute", "accept_tradeoff", "verify_fixed"],
                        },
                        "evidence": {"type": "string"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["flag_id", "action", "evidence", "rationale"],
                },
            },
            "accepted_tradeoffs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "flag_id": {"type": "string"},
                        "concern": {"type": "string"},
                        "subsystem": {"type": "string"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["flag_id", "concern", "subsystem", "rationale"],
                },
            },
            "tiebreaker_question": {"type": "string"},
            "tiebreaker_flag_ids": {
                "type": "array",
                "items": {"type": "string"},
            },
            "tiebreaker_fuzzy_group_id": {"type": "string"},
            "north_star_actions": {
                "type": "array",
                "items": deepcopy(NORTH_STAR_ACTION_SCHEMA),
            },
        },
        "required": [
            "recommendation",
            "rationale",
            "signals_assessment",
            "warnings",
            "settled_decisions",
            "flag_resolutions",
            "accepted_tradeoffs",
            "north_star_actions",
        ],
    },
    "critique.json": {
        "type": "object",
        "properties": {
            "checks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "question": {"type": "string"},
                        "findings": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "detail": {"type": "string"},
                                    "flagged": {"type": "boolean"},
                                    "category": {"type": "string"},
                                    "severity_hint": {"type": "string"},
                                    "evidence": {"type": "string"},
                                    "finding_id": {"type": "string"},
                                },
                                "required": ["detail", "flagged"],
                            },
                        },
                    },
                    "required": ["id", "question", "findings"],
                },
            },
            "flags": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "concern": {"type": "string"},
                        "category": {
                            "type": "string",
                            "enum": [
                                "correctness",
                                "security",
                                "completeness",
                                "performance",
                                "maintainability",
                                "doc-quality",
                                "other",
                                "verifiability",
                            ],
                        },
                        "severity_hint": {
                            "type": "string",
                            "enum": ["likely-significant", "likely-minor", "uncertain"],
                        },
                        "evidence": {"type": "string"},
                        "source_check_id": {"type": "string"},
                        "producer_category": {"type": "string"},
                        "producer_severity": {"type": "string"},
                    },
                    "required": ["id", "concern", "category", "severity_hint", "evidence"],
                },
            },
            "verified_flag_ids": {"type": "array", "items": {"type": "string"}},
            "disputed_flag_ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["checks", "flags", "verified_flag_ids", "disputed_flag_ids"],
    },
    "critique_evaluator.json": _build_critique_evaluator_schema(),
"finalize.json": {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "description": {"type": "string"},
                        "depends_on": {"type": "array", "items": {"type": "string"}},
                        "status": {"type": "string", "enum": ["pending", "done", "skipped", "blocked"]},
                        "kind": {
                            "type": "string",
                            "enum": ["code", "audit", "test", "docs", "research"],
                        },
                        "executor_notes": {"type": "string"},
                        "files_changed": {"type": "array", "items": {"type": "string"}},
                        "commands_run": {"type": "array", "items": {"type": "string"}},
                        "auto_attributed_files": {"type": ["boolean", "null"]},
                        "evidence_files": {"type": "array", "items": {"type": "string"}},
                        "reviewer_verdict": {"type": "string"},
                        "complexity": {"type": "integer", "minimum": 1, "maximum": 10},
                        "complexity_justification": {"type": "string"},
                        "stance": deepcopy(STANCE_SCHEMA),
                        "stop_signal": deepcopy(STOP_SIGNAL_SCHEMA),
                    },
                    "required": [
                        "id",
                        "description",
                        "depends_on",
                        "status",
                        "complexity",
                        "complexity_justification",
                        "executor_notes",
                        "files_changed",
                        "commands_run",
                        "evidence_files",
                        "reviewer_verdict",
                    ],
                    "x-preserve-explicit-required": True,
                },
            },
            "watch_items": {"type": "array", "items": {"type": "string"}},
            "sense_checks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "task_id": {"type": "string"},
                        "question": {"type": "string"},
                        "executor_note": {"type": "string"},
                        "verdict": {"type": "string"},
                    },
                    "required": ["id", "task_id", "question", "executor_note", "verdict"],
                },
            },
            "user_actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "description": {"type": "string"},
                        "phase": {"type": "string", "enum": ["before_execute", "after_execute"]},
                        "blocks_task_ids": {"type": "array", "items": {"type": "string"}},
                        "rationale": {"type": "string"},
                        "requires_human_only_reason": {"type": "string"},
                    },
                    "required": ["id", "description", "phase"],
                    "x-preserve-explicit-required": True,
                },
            },
            "meta_commentary": {"type": "string"},
            "critique_custody": {"type": "object"},
            "critique_resolution_coverage": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "finding_id": {"type": "string"},
                        "task_ids": {"type": "array", "items": {"type": "string"}},
                        "resolution_evidence": {"type": "string"},
                    },
                    "required": ["finding_id", "task_ids", "resolution_evidence"],
                },
            },
            "validation": {
                "type": "object",
                "properties": {
                    "plan_steps_covered": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "plan_step_summary": {"type": "string"},
                                "finalize_item_ids": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": ["plan_step_summary", "finalize_item_ids"],
                        },
                    },
                    "orphan_tasks": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "completeness_notes": {"type": "string"},
                    "coverage_complete": {"type": "boolean"},
                },
                "required": [
                    "plan_steps_covered",
                    "orphan_tasks",
                    "completeness_notes",
                    "coverage_complete",
                ],
            },
            "baseline_test_failures": {
                "type": ["array", "null"],
                "items": {"type": "string"},
            },
            "baseline_test_command": {"type": ["string", "null"]},
            "baseline_test_note": {"type": "string"},
            "suite_runs_ndjson_path": {"type": ["string", "null"]},
        },
        "required": ["tasks", "watch_items", "sense_checks", "user_actions", "meta_commentary", "validation"],
    },
    "directors_notes.json": {
        "type": "object",
        "properties": {
            "form": {"type": "string"},
            "primary_criterion": {"type": ["string", "null"]},
            "passes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "iteration": {"type": "integer"},
                        "provocateur_voice": {"type": ["string", "null"]},
                        "provocations_fired": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "vector": {"type": "string", "enum": ["cut", "force", "spark"]},
                                    "subtype": {"type": "string"},
                                },
                                "required": ["id", "vector", "subtype"],
                            },
                        },
                        "stances": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "task_id": {"type": "string"},
                                    "challenge_engaged": {"type": "string"},
                                    "angle_taken": {"type": "string"},
                                    "what_changed": {"type": "string"},
                                    "stance_violations": {"type": "array", "items": {"type": "string"}},
                                },
                                "required": [
                                    "task_id",
                                    "challenge_engaged",
                                    "angle_taken",
                                    "what_changed",
                                    "stance_violations",
                                ],
                            },
                        },
                        "stop_requested": {"type": "boolean"},
                        "stop_defense": {"type": "string"},
                    },
                    "required": [
                        "iteration",
                        "provocateur_voice",
                        "provocations_fired",
                        "stances",
                        "stop_requested",
                        "stop_defense",
                    ],
                },
            },
        },
        "required": ["form", "primary_criterion", "passes"],
    },
    "execution.json": {
        "type": "object",
        "properties": {
            "output": {"type": "string"},
            "files_changed": {"type": "array", "items": {"type": "string"}},
            "commands_run": {"type": "array", "items": {"type": "string"}},
            "deviations": {"type": "array", "items": {"type": "string"}},
            "task_updates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "status": {"type": "string", "enum": ["done", "skipped", "completed", "blocked", "pending"]},
                        "executor_notes": {"type": "string"},
                        "files_changed": {"type": "array", "items": {"type": "string"}},
                        "commands_run": {"type": "array", "items": {"type": "string"}},
                        "auto_attributed_files": {"type": ["boolean", "null"]},
                    },
                    "required": ["task_id", "status", "executor_notes", "files_changed", "commands_run"],
                    "x-preserve-explicit-required": True,
                },
            },
            "sense_check_acknowledgments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "sense_check_id": {"type": "string"},
                        "executor_note": {"type": "string"},
                    },
                    "required": ["sense_check_id", "executor_note"],
                },
            },
        },
        "required": ["output", "files_changed", "commands_run", "deviations", "task_updates", "sense_check_acknowledgments"],
    },
    "loop_plan.json": {
        "type": "object",
        "properties": {
            "spec_updates": {
                "type": "object",
                "additionalProperties": True,
            },
            "next_action": {"type": "string"},
            "reasoning": {"type": "string"},
        },
        "required": ["spec_updates", "next_action", "reasoning"],
    },
    "tiebreaker_researcher.json": {
        "type": "object",
        "properties": {
            "question": {"type": "string"},
            "evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim": {"type": "string"},
                        "evidence_type": {
                            "type": "string",
                            "enum": ["code", "measurement", "pattern", "doc"],
                        },
                        "file_paths": {"type": "array", "items": {"type": "string"}},
                        "quote": {"type": "string"},
                    },
                    "required": ["claim", "evidence_type", "file_paths", "quote"],
                },
            },
            "options": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "assumptions": {"type": "array", "items": {"type": "string"}},
                        "costs": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["name", "description", "assumptions", "costs"],
                },
            },
            "preliminary_pick": {
                "type": "object",
                "properties": {
                    "option_name": {"type": "string"},
                    "rationale": {"type": "string"},
                    "what_im_least_sure_about": {"type": "string"},
                },
                "required": ["option_name", "rationale", "what_im_least_sure_about"],
            },
        },
        "required": ["question", "evidence", "options", "preliminary_pick"],
    },
    "tiebreaker_challenger.json": {
        "type": "object",
        "properties": {
            "measurements_vs_assumptions": {"type": "string"},
            "missing_options": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "why_missed": {"type": "string"},
                    },
                    "required": ["name", "description", "why_missed"],
                },
            },
            "hard_cases": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "scenario": {"type": "string"},
                        "which_option_breaks": {"type": "string"},
                        "severity": {"type": "string"},
                    },
                    "required": ["scenario", "which_option_breaks", "severity"],
                },
            },
            "reframings": {"type": "array", "items": {"type": "string"}},
            "aging_analysis": {"type": "string"},
            "counter_recommendation": {
                "type": "object",
                "properties": {
                    "option_name": {"type": "string"},
                    "rationale": {"type": "string"},
                    "agrees_with_researcher": {"type": "boolean"},
                },
                "required": ["option_name", "rationale", "agrees_with_researcher"],
            },
        },
        "required": [
            "measurements_vs_assumptions",
            "missing_options",
            "hard_cases",
            "reframings",
            "aging_analysis",
            "counter_recommendation",
        ],
    },
    "loop_execute.json": {
        "type": "object",
        "properties": {
            "diagnosis": {"type": "string"},
            "fix_description": {"type": "string"},
            "files_to_change": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "string"},
            "outcome": {"type": "string"},
            "should_pause": {"type": "boolean"},
        },
        "required": ["diagnosis", "fix_description", "files_to_change", "confidence", "outcome", "should_pause"],
    },
    "feedback.json": {
        "type": "object",
        "properties": {
            "overall": {
                "type": "object",
                "properties": {
                    "rating": {"type": "integer", "minimum": 0, "maximum": 10},
                    "comment": {"type": "string"},
                },
                "required": ["rating", "comment"],
            },
            "stages": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "rating": {"type": "integer", "minimum": 0, "maximum": 10},
                        "comment": {"type": "string"},
                    },
                    "required": ["rating", "comment"],
                },
            },
        },
        "required": ["overall", "stages"],
    },
    "review.json": {
        "x-preserve-explicit-required": True,
        "type": "object",
        "properties": {
            "review_verdict": {"type": "string", "enum": ["approved", "needs_rework"]},
            "checks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "question": {"type": "string"},
                        "guidance": {"type": "string"},
                        "findings": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "detail": {"type": "string"},
                                    "flagged": {"type": "boolean"},
                                    "status": {"type": "string"},
                                    "evidence_file": {"type": "string"},
                                },
                                "required": ["detail", "flagged", "status", "evidence_file"],
                            },
                        },
                        "prior_findings": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "detail": {"type": "string"},
                                    "flagged": {"type": "boolean"},
                                    "status": {"type": "string"},
                                },
                                "required": ["detail", "flagged", "status"],
                            },
                        },
                        "concerned_task_ids": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["id", "question", "guidance", "findings", "prior_findings", "concerned_task_ids"],
                },
            },
            "pre_check_flags": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "check": {"type": "string"},
                        "detail": {"type": "string"},
                        "severity": {"type": "string"},
                        "evidence_file": {"type": "string"},
                    },
                    "required": ["id", "check", "detail", "severity", "evidence_file"],
                },
            },
            "verified_flag_ids": {"type": "array", "items": {"type": "string"}},
            "disputed_flag_ids": {"type": "array", "items": {"type": "string"}},
            "criteria": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "priority": {"type": "string", "enum": ["must", "should", "info"]},
                        "pass": {"type": "string", "enum": ["pass", "fail", "waived", "deferred_human"]},
                        "evidence": {"type": "string"},
                    },
                    "required": ["name", "priority", "pass", "evidence"],
                },
            },
            "issues": {"type": "array", "items": {"type": "string"}},
            "north_star_actions": {
                "type": "array",
                "items": deepcopy(NORTH_STAR_ACTION_SCHEMA),
            },
            "rework_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "issue": {"type": "string"},
                        "expected": {"type": "string"},
                        "actual": {"type": "string"},
                        "evidence_file": {"type": "string"},
                        "flag_id": {"type": ["string", "null"]},
                        "source": {"type": ["string", "null"]},
                        "target": {
                            "x-preserve-explicit-required": True,
                            "type": ["object", "null"],
                            "additionalProperties": False,
                            "properties": {
                                "kind": {
                                    "type": "string",
                                    "enum": ["task", "bulk", "manifest", "global"],
                                },
                                "task_id": {"type": ["string", "null"]},
                                "task_ids": {"type": "array", "items": {"type": "string"}},
                                "id": {"type": ["string", "null"]},
                            },
                            "required": [
                                "kind",
                                "task_id",
                                "task_ids",
                                "id",
                            ],
                        },
                        "deterministic_check": {
                            "x-preserve-explicit-required": True,
                            "type": ["object", "null"],
                            "additionalProperties": False,
                            "properties": {
                                "command": {"type": "string"},
                                "baseline_status": {"type": "string"},
                                "post_status": {"type": "string"},
                                "evidence_file": {"type": ["string", "null"]},
                            },
                            "required": [
                                "command",
                                "baseline_status",
                                "post_status",
                                "evidence_file",
                            ],
                        },
                    },
                    "required": [
                        "task_id",
                        "issue",
                        "expected",
                        "actual",
                        "evidence_file",
                        "flag_id",
                        "source",
                        "target",
                        "deterministic_check",
                    ],
                },
            },
            "summary": {"type": "string"},
            "task_verdicts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "reviewer_verdict": {"type": "string"},
                        "evidence_files": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["task_id", "reviewer_verdict", "evidence_files"],
                },
            },
            "sense_check_verdicts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "sense_check_id": {"type": "string"},
                        "verdict": {"type": "string"},
                    },
                    "required": ["sense_check_id", "verdict"],
                },
            },
        },
        "required": [
            "review_verdict",
            "criteria",
            "issues",
            "rework_items",
            "summary",
            "task_verdicts",
            "sense_check_verdicts",
        ],
    },
}


def _build_execution_doc_schema() -> dict[str, Any]:
    schema = deepcopy(SCHEMAS["execution.json"])
    schema["properties"]["sections_written"] = schema["properties"].pop("files_changed")
    task_update_schema = schema["properties"]["task_updates"]["items"]
    task_update_schema["properties"]["sections_written"] = task_update_schema["properties"].pop("files_changed")
    task_update_schema["properties"]["stance"] = deepcopy(STANCE_SCHEMA)
    task_update_schema["properties"]["stop_signal"] = deepcopy(STOP_SIGNAL_SCHEMA)
    task_update_schema["properties"].pop("commands_run", None)
    task_update_schema["properties"].pop("auto_attributed_files", None)
    task_update_schema["required"] = ["task_id", "status", "executor_notes", "sections_written"]
    schema["required"] = [
        "output",
        "sections_written",
        "commands_run",
        "deviations",
        "task_updates",
        "sense_check_acknowledgments",
    ]
    return schema


def _build_execution_batch_relaxed_schema() -> dict[str, Any]:
    """Execute capture schema for batch-shaped outputs.

    Execute workers may legitimately return only per-task evidence during batch
    execution. This relaxed variant keeps the same property/item contracts as
    ``execution.json`` while requiring only the batch-specific keys.
    """

    schema = deepcopy(SCHEMAS["execution.json"])
    task_update_schema = schema["properties"]["task_updates"]["items"]
    task_update_schema["required"] = []
    sense_check_schema = schema["properties"]["sense_check_acknowledgments"]["items"]
    sense_check_schema["required"] = []
    schema["required"] = [
        "task_updates",
        "sense_check_acknowledgments",
    ]
    return schema


SCHEMAS["execution_doc.json"] = _build_execution_doc_schema()
SCHEMAS["execution_batch_relaxed.json"] = _build_execution_batch_relaxed_schema()


def get_execution_schema_key(mode: str, form: str | None = None) -> str:
    if mode == "creative" and form:
        from arnold_pipelines.megaplan.forms import get_form

        return get_form(form).execution_schema_key
    from arnold_pipelines.megaplan._core import is_prose_mode

    return "execution_doc.json" if is_prose_mode({"config": {"mode": mode}}) else "execution.json"


def _preserve_explicit_required(path: tuple[str, ...]) -> bool:
    # `review.rework_items[]` uses explicit required fields because OpenAI
    # structured outputs require every property key to appear in `required`.
    return path[-3:] == ("properties", "rework_items", "items") or path[-4:] == (
        "properties",
        "rework_items",
        "items",
        "properties",
    )


def _is_object_schema_type(value: Any) -> bool:
    return value == "object" or (isinstance(value, list) and "object" in value)


def strict_schema(schema: Any, _path: tuple[str, ...] = ()) -> Any:
    if isinstance(schema, dict):
        updated = {key: strict_schema(value, _path + (key,)) for key, value in schema.items()}
        preserve_explicit_required = bool(updated.pop("x-preserve-explicit-required", False))
        if _is_object_schema_type(updated.get("type")):
            updated.setdefault("additionalProperties", False)
            if "properties" in updated:
                property_keys = list(updated["properties"].keys())
                if preserve_explicit_required or _preserve_explicit_required(_path):
                    required = list(updated.get("required", []))
                    updated["required"] = required + [
                        key for key in property_keys if key not in required
                    ]
                else:
                    updated["required"] = property_keys
        return updated
    if isinstance(schema, list):
        return [strict_schema(item, _path) for item in schema]
    return schema
