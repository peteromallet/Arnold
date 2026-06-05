"""Golden characterization for the deterministic planning pipeline.

Two scenarios are snapshotted into readable JSON fixtures:

* A fresh mock run driven by ``run_pipeline_with_policy`` through ``done``.
* A resume path that halts after ``finalize``, rereads ``state.json``, then
  resumes to ``done`` via the in-process step driver.

The fixtures intentionally snapshot only stable, normalized outputs:

* structural ``state.json`` fields
* sorted artifact filenames
* selected JSON artifact fields
* SHA256 plus short excerpts for deterministic text artifacts

Volatile values such as UUIDs, timestamps, session ids, absolute temp paths,
and token/accounting metadata are stripped or summarized away.
"""

from __future__ import annotations

import hashlib
import json
import re
import difflib
from argparse import Namespace
from pathlib import Path
from typing import Any

import pytest

import arnold.pipelines.megaplan as megaplan

from arnold.pipelines.megaplan._pipeline.executor import run_pipeline_with_policy
from arnold.pipelines.megaplan._pipeline.planning import compile_planning_pipeline
from arnold.pipelines.megaplan._pipeline.runtime import policy_from_cli_args
from arnold.pipelines.megaplan.stages.inprocess_step import (
    build_inprocess_planning_steps,
    build_revise_step,
    build_review_step,
)
from arnold.pipelines.megaplan._pipeline.types import StepContext
from tests.conftest import PlanFixture, _make_plan_fixture_with_robustness

_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_ISO_8601_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\b"
)
_INVOCATION_ID_RE = re.compile(r"\b[0-9a-f]{16}\b")

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "golden"
FIXTURE_FRESH = FIXTURE_DIR / "pipeline_fresh_run.json"
FIXTURE_RESUME = FIXTURE_DIR / "pipeline_resume_after_finalize.json"

_TEXT_ARTIFACTS = ("plan_v1.md", "plan_v2.md", "final.md")
_TRANSIENT_ARTIFACTS = {"critique_output.json"}


def _make_mock_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    idea: str,
    name: str,
) -> PlanFixture:
    tmp_path.mkdir(parents=True, exist_ok=True)
    fixture = _make_plan_fixture_with_robustness(
        tmp_path,
        monkeypatch,
        robustness="robust",
    )
    init_args = fixture.make_args(
        plan=fixture.plan_name,
        idea=idea,
        name=name,
        robustness="robust",
    )
    state = json.loads((fixture.plan_dir / "state.json").read_text(encoding="utf-8"))
    state["idea"] = idea
    state["name"] = fixture.plan_name
    (fixture.plan_dir / "state.json").write_text(
        json.dumps(state, indent=2) + "\n",
        encoding="utf-8",
    )
    megaplan.handle_override(
        fixture.root,
        Namespace(
            **{
                **vars(init_args),
                "override_action": "add-note",
                "note": "golden characterization",
            }
        ),
    )
    return fixture


def _policy():
    return policy_from_cli_args(
        stall_threshold=999,
        max_iterations=30,
        max_cost_usd=None,
        on_escalate="force-proceed",
    )


def _step_context(fixture: PlanFixture) -> StepContext:
    state = json.loads((fixture.plan_dir / "state.json").read_text(encoding="utf-8"))
    return StepContext(
        plan_dir=fixture.plan_dir,
        state={"name": fixture.plan_name, **state},
        profile={"root": fixture.root, "project_dir": fixture.project_dir},
        mode="code",
        inputs={},
        budget=None,
    )


def _run_fresh_pipeline(fixture: PlanFixture) -> dict[str, Any]:
    result = run_pipeline_with_policy(
        compile_planning_pipeline(),
        _step_context(fixture),
        artifact_root=fixture.plan_dir,
        policy=_policy(),
    )
    snapshot = _build_snapshot(
        fixture.plan_dir,
        scenario="fresh-run",
        extra={
            "final_stage": result.get("final_stage"),
        },
    )
    assert snapshot["state"]["current_state"] == "done"
    return snapshot


def _drive_until(
    fixture: PlanFixture,
    *,
    halt_after: str | None = None,
    max_steps: int = 25,
) -> dict[str, Any]:
    inprocess_steps = build_inprocess_planning_steps()
    revise_step = build_revise_step()
    review_step = build_review_step()
    visits: list[str] = []

    for _ in range(max_steps):
        live_state = json.loads((fixture.plan_dir / "state.json").read_text(encoding="utf-8"))
        current_state = live_state.get("current_state", "initialized")
        if current_state in {"done", "aborted"}:
            return {"visits": visits, "final_state": current_state}

        if current_state == "initialized":
            step = inprocess_steps["prepped"]
        elif current_state == "prepped":
            step = inprocess_steps["planned"]
        elif current_state == "planned":
            step = inprocess_steps["critiqued"]
        elif current_state == "critiqued":
            step = inprocess_steps["gated"]
        elif current_state == "gated":
            step = inprocess_steps["finalized"]
        elif current_state == "finalized":
            step = inprocess_steps["executed"]
        elif current_state == "executed":
            step = review_step
        else:
            raise RuntimeError(f"unexpected state {current_state!r}")

        result = step.run(_step_context(fixture))
        visits.append(f"{current_state}->{step.name}={result.next}")

        if (
            step.name == "gate"
            and result.verdict is not None
            and result.verdict.recommendation == "iterate"
        ):
            revise_result = revise_step.run(_step_context(fixture))
            visits.append(f"revise={revise_result.next}")

        if halt_after and step.name == halt_after:
            return {"visits": visits, "final_state": "halted"}

    return {"visits": visits, "final_state": "max_steps_exhausted"}


def _run_resume_pipeline(fixture: PlanFixture) -> dict[str, Any]:
    halted = _drive_until(fixture, halt_after="finalize")
    assert halted["final_state"] == "halted"

    halted_state = json.loads((fixture.plan_dir / "state.json").read_text(encoding="utf-8"))
    assert halted_state["current_state"] == "finalized"
    reread_state = json.loads((fixture.plan_dir / "state.json").read_text(encoding="utf-8"))
    assert reread_state["current_state"] == "finalized"

    resumed = _drive_until(fixture)
    assert resumed["final_state"] == "done"

    snapshot = _build_snapshot(
        fixture.plan_dir,
        scenario="resume-after-finalize",
        extra={
            "halt_visits": halted["visits"],
            "resume_visits": resumed["visits"],
            "halt_state": _snapshot_state(halted_state),
            "artifact_filenames_at_halt": sorted(
                p.name for p in fixture.plan_dir.iterdir() if p.name not in _TRANSIENT_ARTIFACTS
            ),
        },
    )
    assert snapshot["state"]["current_state"] == "done"
    return snapshot


def _replace_paths(value: str, replacements: list[str]) -> str:
    for original in replacements:
        if original:
            value = value.replace(original, "{{WORKDIR}}")
    return value


def _normalize_scalar(value: Any, replacements: list[str]) -> Any:
    if isinstance(value, str):
        normalized = _replace_paths(value, replacements)
        normalized = _UUID_RE.sub("{{UUID}}", normalized)
        normalized = _ISO_8601_RE.sub("{{TIMESTAMP}}", normalized)
        normalized = _INVOCATION_ID_RE.sub("{{INVOCATION_ID}}", normalized)
        return normalized
    if isinstance(value, list):
        return [_normalize_scalar(item, replacements) for item in value]
    if isinstance(value, dict):
        return {
            key: _normalize_scalar(item, replacements)
            for key, item in value.items()
        }
    return value


def _snapshot_state(raw_state: dict[str, Any]) -> dict[str, Any]:
    config = raw_state.get("config", {})
    meta = raw_state.get("meta", {})
    snapshot: dict[str, Any] = {
        "current_state": raw_state.get("current_state"),
        "iteration": raw_state.get("iteration"),
        "config": {
            "adaptive_critique": config.get("adaptive_critique"),
            "agent": config.get("agent"),
            "auto_approve": config.get("auto_approve"),
            "max_tasks_per_batch": config.get("max_tasks_per_batch"),
            "mode": config.get("mode"),
            "project_dir": config.get("project_dir"),
            "robustness": config.get("robustness"),
            "strict_notes": config.get("strict_notes"),
        },
        "sessions": {
            name: {
                "mode": session.get("mode"),
                "refreshed": session.get("refreshed"),
            }
            for name, session in sorted(raw_state.get("sessions", {}).items())
        },
        "plan_versions": [
            {
                "version": item.get("version"),
                "file": item.get("file"),
            }
            for item in raw_state.get("plan_versions", [])
        ],
        "history": [
            {
                key: entry[key]
                for key in (
                    "step",
                    "result",
                    "agent",
                    "session_mode",
                    "output_file",
                    "recommendation",
                    "flags_count",
                    "flags_addressed",
                    "approval_mode",
                    "environment",
                )
                if key in entry
            }
            for entry in raw_state.get("history", [])
        ],
        "meta": {
            "notes": [
                {
                    "note": item.get("note"),
                    "source": item.get("source"),
                }
                for item in meta.get("notes", [])
            ],
            "overrides": [
                {
                    "action": item.get("action"),
                    "note": item.get("note"),
                    "source": item.get("source"),
                }
                for item in meta.get("overrides", [])
            ],
            "user_approved_gate": meta.get("user_approved_gate"),
        },
        "last_gate": {
            key: raw_state.get("last_gate", {}).get(key)
            for key in (
                "recommendation",
                "rationale",
                "reprompted",
                "signals_assessment",
                "warnings",
                "settled_decisions",
                "passed",
                "preflight_results",
                "orchestrator_guidance",
            )
            if key in raw_state.get("last_gate", {})
        },
    }
    if "resume_cursor" in raw_state:
        snapshot["resume_cursor"] = raw_state["resume_cursor"]
    return snapshot


def _excerpt_text(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return lines[:12]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _summarize_critique(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "checks": [
            {
                "id": check.get("id"),
                "flagged": [
                    finding.get("flagged")
                    for finding in check.get("findings", [])
                ],
            }
            for check in payload.get("checks", [])
        ],
        "flags": [
            {
                "id": flag.get("id"),
                "category": flag.get("category"),
                "severity_hint": flag.get("severity_hint"),
                "status": flag.get("status"),
            }
            for flag in payload.get("flags", [])
        ],
        "verified_flag_ids": payload.get("verified_flag_ids", []),
        "disputed_flag_ids": payload.get("disputed_flag_ids", []),
    }


def _summarize_gate(payload: dict[str, Any]) -> dict[str, Any]:
    signals = payload.get("signals", {})
    return {
        "passed": payload.get("passed"),
        "recommendation": payload.get("recommendation"),
        "rationale": payload.get("rationale"),
        "signals_assessment": payload.get("signals_assessment"),
        "preflight_results": payload.get("preflight_results", {}),
        "criteria_check": payload.get("criteria_check", {}),
        "robustness": payload.get("robustness"),
        "signals": {
            "iteration": signals.get("iteration"),
            "significant_flags": signals.get("significant_flags"),
            "resolved_flag_ids": [
                item.get("id")
                for item in signals.get("resolved_flags", [])
            ],
            "unresolved_flag_ids": list(signals.get("unresolved_flags", [])),
        },
    }


def _summarize_finalize(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "tasks": [
            {
                "id": task.get("id"),
                "description": task.get("description"),
                "status": task.get("status"),
                "complexity": task.get("complexity"),
            }
            for task in payload.get("tasks", [])
        ],
        "watch_items": payload.get("watch_items", []),
        "sense_checks": [
            {
                "id": item.get("id"),
                "task_id": item.get("task_id"),
                "question": item.get("question"),
            }
            for item in payload.get("sense_checks", [])
        ],
        "baseline_test_command": payload.get("baseline_test_command"),
        "baseline_test_failures": payload.get("baseline_test_failures"),
        "validation": {
            "coverage_complete": payload.get("validation", {}).get("coverage_complete"),
            "orphan_tasks": payload.get("validation", {}).get("orphan_tasks", []),
        },
    }


def _summarize_execution(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "commands_run": payload.get("commands_run", []),
        "files_changed": payload.get("files_changed", []),
        "deviations": payload.get("deviations", []),
        "task_updates": [
            {
                "task_id": item.get("task_id"),
                "status": item.get("status"),
                "files_changed": item.get("files_changed", []),
                "commands_run": item.get("commands_run", []),
            }
            for item in payload.get("task_updates", [])
        ],
        "sense_check_acknowledgments": payload.get("sense_check_acknowledgments", []),
    }


def _summarize_review(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_verdict": payload.get("review_verdict"),
        "pre_check_flag_ids": [
            item.get("id")
            for item in payload.get("pre_check_flags", [])
        ],
        "criteria": [
            {
                "name": item.get("name"),
                "priority": item.get("priority"),
                "pass": item.get("pass"),
            }
            for item in payload.get("criteria", [])
        ],
        "issues": payload.get("issues", []),
        "task_verdicts": [
            {
                "task_id": item.get("task_id"),
                "reviewer_verdict": item.get("reviewer_verdict"),
            }
            for item in payload.get("task_verdicts", [])
        ],
        "sense_check_verdicts": payload.get("sense_check_verdicts", []),
    }


def _summarize_plan_meta(payload: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "version": payload.get("version"),
        "questions": payload.get("questions", []),
        "success_criteria": payload.get("success_criteria", []),
        "assumptions": payload.get("assumptions", []),
        "structure_warnings": payload.get("structure_warnings", []),
    }
    if "changes_summary" in payload:
        summary["changes_summary"] = payload.get("changes_summary")
    if "flags_addressed" in payload:
        summary["flags_addressed"] = payload.get("flags_addressed", [])
    return summary


def _selected_json_artifacts(plan_dir: Path) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    for filename in sorted(p.name for p in plan_dir.iterdir() if p.suffix == ".json"):
        path = plan_dir / filename
        if filename == "state.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if filename == "prep.json":
            summaries[filename] = payload
        elif filename.startswith("critique_v"):
            summaries[filename] = _summarize_critique(payload)
        elif filename == "gate.json":
            summaries[filename] = _summarize_gate(payload)
        elif filename == "finalize.json":
            summaries[filename] = _summarize_finalize(payload)
        elif filename == "execution.json":
            summaries[filename] = _summarize_execution(payload)
        elif filename == "review.json":
            summaries[filename] = _summarize_review(payload)
        elif filename.startswith("plan_v") and filename.endswith(".meta.json"):
            summaries[filename] = _summarize_plan_meta(payload)
    return summaries


def _text_artifact_summaries(plan_dir: Path) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    for filename in _TEXT_ARTIFACTS:
        path = plan_dir / filename
        if not path.exists():
            continue
        summaries[filename] = {
            "sha256": _sha256(path),
            "excerpt": _excerpt_text(path),
        }
    return summaries


def _build_snapshot(
    plan_dir: Path,
    *,
    scenario: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw_state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    replacements = sorted(
        {
            str(plan_dir),
            str(plan_dir.resolve()),
            str(plan_dir.parent),
            str(plan_dir.parent.resolve()),
            str(plan_dir.parent.parent),
            str(plan_dir.parent.parent.resolve()),
            str(plan_dir.parent.parent.parent),
            str(plan_dir.parent.parent.parent.resolve()),
            str(raw_state.get("config", {}).get("project_dir", "")),
            str(Path(raw_state.get("config", {}).get("project_dir", ".")).resolve()),
        },
        key=len,
        reverse=True,
    )
    snapshot = {
        "scenario": scenario,
        "state": _snapshot_state(raw_state),
        "artifact_filenames": sorted(
            p.name for p in plan_dir.iterdir() if p.name not in _TRANSIENT_ARTIFACTS
        ),
        "json_artifacts": _selected_json_artifacts(plan_dir),
        "text_artifacts": _text_artifact_summaries(plan_dir),
    }
    if extra:
        snapshot.update(extra)
    return _normalize_scalar(snapshot, replacements)


def _read_fixture(path: Path) -> dict[str, Any]:
    if not path.exists():
        pytest.fail(
            f"Fixture not found: {path}\n"
            f"Generate it with: python -m pytest {Path(__file__).name} "
            f"-k test_generate_fixtures --write-fixture"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _write_fixture(path: Path, payload: dict[str, Any]) -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _assert_matches_fixture(current: dict[str, Any], fixture_path: Path) -> None:
    expected = _read_fixture(fixture_path)
    current_str = json.dumps(current, indent=2, sort_keys=True)
    expected_str = json.dumps(expected, indent=2, sort_keys=True)
    if current_str != expected_str:
        diff = "\n".join(
            difflib.unified_diff(
                expected_str.splitlines(),
                current_str.splitlines(),
                fromfile="fixture",
                tofile="current",
                n=3,
            )
        )
        pytest.fail(
            "Pipeline golden fixture diverged.\n\n"
            f"Fixture: {fixture_path}\n"
            "If the change is intentional, regenerate with:\n"
            f"  python -m pytest {Path(__file__).name} "
            "-k test_generate_fixtures --write-fixture\n\n"
            f"{diff}\n"
        )


class TestPipelineGolden:
    def test_fresh_run_matches_fixture(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fixture = _make_mock_plan(
            tmp_path / "fresh",
            monkeypatch,
            idea="golden fresh run",
            name="golden-fresh",
        )
        current = _run_fresh_pipeline(fixture)
        _assert_matches_fixture(current, FIXTURE_FRESH)

    def test_resume_after_finalize_matches_fixture(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fixture = _make_mock_plan(
            tmp_path / "resume",
            monkeypatch,
            idea="golden resume run",
            name="golden-resume",
        )
        current = _run_resume_pipeline(fixture)
        _assert_matches_fixture(current, FIXTURE_RESUME)

    def test_generate_fixtures(
        self,
        request: pytest.FixtureRequest,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        if not request.config.getoption("--write-fixture", default=False):
            pytest.skip("Pass --write-fixture to regenerate the fixtures")

        fresh_fixture = _make_mock_plan(
            tmp_path / "fresh-generate",
            monkeypatch,
            idea="golden fresh run",
            name="golden-fresh",
        )
        resume_fixture = _make_mock_plan(
            tmp_path / "resume-generate",
            monkeypatch,
            idea="golden resume run",
            name="golden-resume",
        )
        _write_fixture(FIXTURE_FRESH, _run_fresh_pipeline(fresh_fixture))
        _write_fixture(FIXTURE_RESUME, _run_resume_pipeline(resume_fixture))

        assert _read_fixture(FIXTURE_FRESH)["scenario"] == "fresh-run"
        assert _read_fixture(FIXTURE_RESUME)["scenario"] == "resume-after-finalize"
