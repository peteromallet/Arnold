"""JSON schema definitions for megaplan step outputs."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


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


SCHEMAS: dict[str, dict[str, Any]] = {
    "plan.json": {
        "type": "object",
        "properties": {
            "plan": {"type": "string"},
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
            "suggested_approach": {"type": "string"},
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
    "revise.json": {
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
                    },
                    "required": ["id", "resolution", "reason"],
                    "additionalProperties": False,
                },
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
                        "action": {"type": "string", "enum": ["dispute", "accept_tradeoff"]},
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
        },
        "required": [
            "recommendation",
            "rationale",
            "signals_assessment",
            "warnings",
            "settled_decisions",
            "flag_resolutions",
            "accepted_tradeoffs",
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
                    },
                    "required": ["id", "concern", "category", "severity_hint", "evidence"],
                },
            },
            "verified_flag_ids": {"type": "array", "items": {"type": "string"}},
            "disputed_flag_ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["checks", "flags", "verified_flag_ids", "disputed_flag_ids"],
    },
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
                        "executor_notes": {"type": "string"},
                        "files_changed": {"type": "array", "items": {"type": "string"}},
                        "commands_run": {"type": "array", "items": {"type": "string"}},
                        "auto_attributed_files": {"type": "boolean"},
                        "evidence_files": {"type": "array", "items": {"type": "string"}},
                        "reviewer_verdict": {"type": "string"},
                        "stance": deepcopy(STANCE_SCHEMA),
                        "stop_signal": deepcopy(STOP_SIGNAL_SCHEMA),
                    },
                    "required": [
                        "id",
                        "description",
                        "depends_on",
                        "status",
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
                        "status": {"type": "string", "enum": ["done", "skipped", "blocked"]},
                        "executor_notes": {"type": "string"},
                        "files_changed": {"type": "array", "items": {"type": "string"}},
                        "commands_run": {"type": "array", "items": {"type": "string"}},
                        "auto_attributed_files": {"type": "boolean"},
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
    "review.json": {
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
                    },
                    "required": ["id", "question", "guidance", "findings", "prior_findings"],
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
                    },
                    "required": ["task_id", "issue", "expected", "actual", "evidence_file", "flag_id", "source"],
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
            "checks",
            "pre_check_flags",
            "verified_flag_ids",
            "disputed_flag_ids",
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


SCHEMAS["execution_doc.json"] = _build_execution_doc_schema()


def get_execution_schema_key(mode: str, form: str | None = None) -> str:
    if mode == "creative" and form:
        from megaplan.forms import get_form

        return get_form(form).execution_schema_key
    from megaplan._core import is_prose_mode

    return "execution_doc.json" if is_prose_mode({"config": {"mode": mode}}) else "execution.json"


def _preserve_explicit_required(path: tuple[str, ...]) -> bool:
    # `review.rework_items[]` uses explicit required fields because OpenAI
    # structured outputs require every property key to appear in `required`.
    return path[-3:] == ("properties", "rework_items", "items")


def strict_schema(schema: Any, _path: tuple[str, ...] = ()) -> Any:
    if isinstance(schema, dict):
        updated = {key: strict_schema(value, _path + (key,)) for key, value in schema.items()}
        preserve_explicit_required = bool(updated.pop("x-preserve-explicit-required", False))
        if updated.get("type") == "object":
            updated.setdefault("additionalProperties", False)
            if "properties" in updated and not (
                preserve_explicit_required or _preserve_explicit_required(_path)
            ):
                updated["required"] = list(updated["properties"].keys())
        return updated
    if isinstance(schema, list):
        return [strict_schema(item, _path) for item in schema]
    return schema
