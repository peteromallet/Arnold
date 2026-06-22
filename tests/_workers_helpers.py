"""Shared helpers for split worker tests."""

from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan.workers import _build_mock_payload


def _mock_state(tmp_path: Path, *, iteration: int = 1) -> tuple[Path, dict]:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    state = {
        "name": "test-plan",
        "idea": "test the mock workers",
        "current_state": "critiqued",
        "iteration": iteration,
        "created_at": "2026-03-20T00:00:00Z",
        "config": {
            "project_dir": str(project_dir),
            "auto_approve": False,
            "robustness": "standard",
        },
        "sessions": {},
        "plan_versions": [
            {"version": iteration, "file": f"plan_v{iteration}.md", "hash": "sha256:test", "timestamp": "2026-03-20T00:00:00Z"}
        ],
        "history": [],
        "meta": {
            "significant_counts": [],
            "weighted_scores": [],
            "plan_deltas": [],
            "recurring_critiques": [],
            "total_cost_usd": 0.0,
            "overrides": [],
            "notes": [],
        },
        "last_gate": {},
    }
    (plan_dir / f"plan_v{iteration}.md").write_text("# Plan\nDo it.\n", encoding="utf-8")
    (plan_dir / f"plan_v{iteration}.meta.json").write_text(
        json.dumps({"version": iteration, "timestamp": "2026-03-20T00:00:00Z", "hash": "sha256:test", "success_criteria": [{"criterion": "criterion", "priority": "must", "requires": []}], "questions": [], "assumptions": []}),
        encoding="utf-8",
    )
    (plan_dir / "faults.json").write_text(json.dumps({"flags": []}), encoding="utf-8")
    (plan_dir / "gate.json").write_text(
        json.dumps(
            {
                "passed": True,
                "recommendation": "PROCEED",
                "rationale": "ok",
                "signals_assessment": "ok",
                "warnings": [],
                "settled_decisions": [],
                "criteria_check": {},
                "preflight_results": {},
                "unresolved_flags": [],
                "override_forced": False,
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "execution.json").write_text(
        json.dumps(_build_mock_payload("execute", state, plan_dir, output="done")),
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            _build_mock_payload(
                "finalize",
                state,
                plan_dir,
                watch_items=["Watch repository assumptions."],
                tasks=[
                    {
                        "id": "T1",
                        "description": "Do work",
                        "depends_on": [],
                        "status": "pending",
                        "executor_notes": "",
                        "files_changed": [],
                        "commands_run": [],
                        "evidence_files": [],
                        "reviewer_verdict": "",
                    },
                    {
                        "id": "T2",
                        "description": "Verify work",
                        "depends_on": ["T1"],
                        "status": "pending",
                        "executor_notes": "",
                        "files_changed": [],
                        "commands_run": [],
                        "evidence_files": [],
                        "reviewer_verdict": "",
                    },
                ],
                sense_checks=[
                    {"id": "SC1", "task_id": "T1", "question": "Did it work?", "executor_note": "", "verdict": ""},
                    {"id": "SC2", "task_id": "T2", "question": "Was it verified?", "executor_note": "", "verdict": ""},
                ],
                meta_commentary="Mock finalize output.",
            )
        ),
        encoding="utf-8",
    )
    return plan_dir, state


def _write_codex_rollout(
    codex_home: Path,
    session_id: str,
    total_token_usage: dict,
    *,
    date: str = "2026/05/05",
    timestamp: str = "0000-1234567890",
) -> Path:
    """Write a fake codex rollout JSONL and return its path."""
    sessions_dir = codex_home / "sessions" / date
    sessions_dir.mkdir(parents=True, exist_ok=True)
    path = sessions_dir / f"rollout-{timestamp}-{session_id}.jsonl"
    lines = [
        json.dumps(
            {
                "type": "session_meta",
                "payload": {
                    "id": session_id,
                    "timestamp": "2026-05-05T09:00:00Z",
                    "model_provider": "openai",
                },
            }
        ),
        json.dumps(
            {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "total_token_usage": total_token_usage,
                        "last_token_usage": total_token_usage,
                        "model_context_window": 258400,
                    },
                },
            }
        ),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


class FakeShutil:
    """Minimal shutil stub for testing Shannon dependency detection."""

    def __init__(self, *present: str) -> None:
        self._present = set(present)

    def which(self, name: str) -> str | None:
        return f"/usr/bin/{name}" if name in self._present else None
