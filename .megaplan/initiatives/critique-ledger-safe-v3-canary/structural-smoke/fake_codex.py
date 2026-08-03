#!/usr/bin/env python3
"""Deterministic offline Codex stand-in for the built-image structural smoke.

This fixture never contacts a model or provider.  It exists only to drive the
real four-phase CLI, nonroot process boundary, rollout capture, and receipt
sealing code inside the production image.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path


def _argument_value(name: str) -> str:
    try:
        return sys.argv[sys.argv.index(name) + 1]
    except (ValueError, IndexError) as exc:
        raise SystemExit(f"fake codex requires {name}") from exc


def _payload(schema_name: str) -> dict[str, object]:
    if schema_name == "plan.json":
        return {
            "plan": (
                "# Offline Structural Smoke\n\n## Overview\nExercise the finite "
                "canary boundary without provider contact.\n\n## Step 1: Verify "
                "receipts\nRun the exact bounded receipt path.\n\n## Execution "
                "Order\n1. Step 1."
            ),
            "questions": [],
            "success_criteria": [
                {
                    "criterion": "All structural receipts are sealed.",
                    "priority": "must",
                    "requires": [],
                }
            ],
            "assumptions": ["This is offline structural evidence only."],
            "changed_surfaces": ["finite-canary structural smoke"],
            "test_blast_radius": {
                "strategy": "scoped",
                "selectors": [],
                "changed_surfaces": ["finite-canary structural smoke"],
                "full_suite_fallback": False,
                "rationale": "The smoke exercises one bounded lifecycle.",
            },
        }
    if schema_name == "critique.json":
        return {
            "checks": [],
            "flags": [],
            "verified_flag_ids": [],
            "disputed_flag_ids": [],
        }
    if schema_name == "gate.json":
        return {
            "recommendation": "PROCEED",
            "rationale": "The deterministic structural payload is internally consistent.",
            "signals_assessment": "Offline structural smoke only; no provider claim.",
            "warnings": [],
            "settled_decisions": [],
            "flag_resolutions": [],
            "accepted_tradeoffs": [],
            "north_star_actions": [],
            "tiebreaker_question": "",
            "tiebreaker_flag_ids": [],
            "tiebreaker_fuzzy_group_id": "",
        }
    if schema_name == "finalize.json":
        return {
            "tasks": [
                {
                    "id": "SMOKE-1",
                    "description": "Verify the offline finite-canary structural receipts.",
                    "depends_on": [],
                    "status": "pending",
                    "kind": "test",
                    "complexity": 1,
                    "complexity_justification": "One deterministic structural check.",
                    "executor_notes": "Do not interpret as model/provider evidence.",
                    "files_changed": [],
                    "commands_run": [],
                    "auto_attributed_files": False,
                    "evidence_files": [],
                    "reviewer_verdict": "structural-only",
                    "stance": {
                        "challenge_engaged": "Privilege and receipt wiring",
                        "angle_taken": "Offline deterministic execution",
                        "what_changed": "No production source mutation",
                    },
                    "stop_signal": {
                        "requested": False,
                        "defense": "The bounded structural phase may complete.",
                    },
                }
            ],
            "watch_items": [],
            "sense_checks": [],
            "user_actions": [],
            "meta_commentary": "Offline structural smoke only.",
            "critique_custody": {},
            "critique_resolution_coverage": [],
            "validation": {
                "plan_steps_covered": [
                    {
                        "plan_step_summary": "Verify receipts",
                        "finalize_item_ids": ["SMOKE-1"],
                    }
                ],
                "orphan_tasks": [],
                "completeness_notes": "The sole structural step is represented.",
                "coverage_complete": True,
            },
            "baseline_test_failures": None,
            "baseline_test_command": None,
            "baseline_test_note": "Not applicable to offline structural smoke.",
            "suite_runs_ndjson_path": None,
        }
    raise SystemExit(f"unsupported structural-smoke schema: {schema_name}")


def main() -> int:
    output = Path(_argument_value("-o"))
    schema = Path(_argument_value("--output-schema"))
    phase = schema.stem
    session_id = hashlib.sha256((phase + "-offline-smoke").encode()).hexdigest()[:32]
    output.write_text(
        json.dumps(_payload(schema.name), sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    codex_home = Path(os.environ["CODEX_HOME"])
    rollout_dir = codex_home / "sessions/2026/08/03"
    rollout_dir.mkdir(parents=True, exist_ok=True)
    rollout = rollout_dir / f"rollout-offline-smoke-{session_id}.jsonl"
    events = [
        {"type": "turn_context", "payload": {"model": "gpt-5.6-sol"}},
        {
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": {
                        "input_tokens": 1,
                        "cached_input_tokens": 0,
                        "output_tokens": 1,
                        "reasoning_output_tokens": 0,
                    }
                },
            },
        },
    ]
    rollout.write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
        encoding="utf-8",
    )
    print(json.dumps({"type": "thread.started", "thread_id": session_id}))
    print(json.dumps({"type": "item.completed", "phase": phase}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
