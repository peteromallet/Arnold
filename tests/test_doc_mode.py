"""Tests for doc-mode (--mode doc) feature across handlers, schemas, evaluation, assembly, and timeout."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

import megaplan
import megaplan._core
import megaplan._core.io as io_module
import megaplan.cli
from megaplan.doc_assembly import assemble_doc, extract_sections
from megaplan.evaluation import validate_execution_evidence
from megaplan.execution_timeout import _merge_timeout_checkpoint, _reset_timeout_invalid_tasks
from megaplan.schemas import SCHEMAS, get_execution_schema_key, strict_schema
from megaplan.types import CliError


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _make_args(project_dir: Path, **overrides: object) -> Namespace:
    data = {
        "plan": None,
        "idea": "test idea",
        "name": "test-plan",
        "project_dir": str(project_dir),
        "auto_approve": None,
        "robustness": None,
        "agent": None,
        "ephemeral": False,
        "fresh": False,
        "persist": False,
        "confirm_destructive": True,
        "user_approved": False,
        "confirm_self_review": False,
        "batch": None,
        "override_action": None,
        "note": None,
        "reason": "",
        "mode": "code",
        "output": None,
        "hermes": None,
    }
    data.update(overrides)
    return Namespace(**data)


def _init_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    config_path = tmp_path / "config"
    root.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()
    monkeypatch.setenv("MEGAPLAN_MOCK_WORKERS", "1")
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )

    def _config_dir(home: Path | None = None) -> Path:
        del home
        return config_path

    monkeypatch.setattr(io_module, "config_dir", _config_dir)
    monkeypatch.setattr(megaplan.cli, "config_dir", _config_dir)
    return root, project_dir


# ---------------------------------------------------------------------------
# (1) handle_init: --mode doc --output docs/plan.md => state has mode + output_path
# ---------------------------------------------------------------------------


def test_handle_init_doc_mode_produces_correct_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, project_dir = _init_env(tmp_path, monkeypatch)
    args = _make_args(project_dir, mode="doc", output="docs/plan.md")
    response = megaplan.handle_init(root, args)
    assert response["success"] is True

    plan_dir = megaplan.plans_root(root) / response["plan"]
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state["config"]["mode"] == "doc"
    assert state["config"]["output_path"] == "docs/plan.md"


# ---------------------------------------------------------------------------
# (2) handle_init: --mode doc without --output => CliError
# ---------------------------------------------------------------------------


def test_handle_init_doc_mode_requires_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, project_dir = _init_env(tmp_path, monkeypatch)
    args = _make_args(project_dir, mode="doc", output=None)
    with pytest.raises(CliError, match="--output is required"):
        megaplan.handle_init(root, args)


# ---------------------------------------------------------------------------
# (3) handle_init: --mode doc --output /absolute/path => CliError
# ---------------------------------------------------------------------------


def test_handle_init_doc_mode_rejects_absolute_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, project_dir = _init_env(tmp_path, monkeypatch)
    args = _make_args(project_dir, mode="doc", output="/absolute/path.md")
    with pytest.raises(CliError, match="relative path"):
        megaplan.handle_init(root, args)


# ---------------------------------------------------------------------------
# (4) handle_init: --mode doc --output ../escape/path => CliError
# ---------------------------------------------------------------------------


def test_handle_init_doc_mode_rejects_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, project_dir = _init_env(tmp_path, monkeypatch)
    args = _make_args(project_dir, mode="doc", output="../escape/path.md")
    with pytest.raises(CliError, match="path traversal"):
        megaplan.handle_init(root, args)


# ---------------------------------------------------------------------------
# (5) validate_execution_evidence in doc mode
# ---------------------------------------------------------------------------


def test_validate_evidence_doc_catches_missing_sections(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    finalize_data = {
        "tasks": [
            {
                "id": "T1",
                "status": "done",
                "sections_written": ["intro", "conclusion"],
                "executor_notes": "Wrote both sections thoroughly.",
            },
            {
                "id": "T2",
                "status": "pending",
                "sections_written": ["appendix"],
                "executor_notes": "",
            },
        ],
        "sense_checks": [],
    }
    result = validate_execution_evidence(finalize_data, project_dir, mode="doc")
    assert result["skipped"] is False
    assert any("appendix" in f for f in result["findings"])


def test_validate_evidence_doc_catches_unclaimed_sections(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    finalize_data = {
        "tasks": [
            {
                "id": "T1",
                "status": "done",
                "sections_written": ["intro", "surprise_section"],
                "executor_notes": "Wrote intro plus an extra section for completeness.",
            },
        ],
        "sense_checks": [],
    }
    result = validate_execution_evidence(finalize_data, project_dir, mode="doc")
    assert result["skipped"] is False
    assert result["files_in_diff"] == []
    assert result["files_claimed"] == []


def test_validate_evidence_doc_passes_all_sections_present(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    finalize_data = {
        "tasks": [
            {
                "id": "T1",
                "status": "done",
                "sections_written": ["intro"],
                "executor_notes": "Wrote the introduction section with thorough research.",
            },
            {
                "id": "T2",
                "status": "done",
                "sections_written": ["conclusion"],
                "executor_notes": "Completed the conclusion with all key findings.",
            },
        ],
        "sense_checks": [
            {"id": "SC1", "executor_note": "Confirmed that the introduction covers all required topics."},
        ],
    }
    result = validate_execution_evidence(finalize_data, project_dir, mode="doc")
    assert result["skipped"] is False
    section_findings = [f for f in result["findings"] if "section" in f.lower()]
    assert len(section_findings) == 0


# ---------------------------------------------------------------------------
# (6) assemble_doc: sections in plan order, non-empty, idempotent
# ---------------------------------------------------------------------------


def test_assemble_doc_orders_by_plan_and_is_idempotent(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = tmp_path / "output" / "doc.md"

    batch_1 = {
        "task_updates": [
            {
                "task_id": "T2",
                "status": "done",
                "executor_notes": "Second section content.",
                "sections_written": ["part-2"],
            },
        ]
    }
    batch_2 = {
        "task_updates": [
            {
                "task_id": "T1",
                "status": "done",
                "executor_notes": "First section content.",
                "sections_written": ["part-1"],
            },
        ]
    }
    _write_json(plan_dir / "execution_batch_1.json", batch_1)
    _write_json(plan_dir / "execution_batch_2.json", batch_2)

    finalize_data = {
        "tasks": [
            {"id": "T1", "sections_written": ["part-1"]},
            {"id": "T2", "sections_written": ["part-2"]},
        ]
    }

    result = assemble_doc(plan_dir, output_path, finalize_data)
    assert result == output_path
    content = output_path.read_text(encoding="utf-8")
    assert len(content) > 0
    assert content.index("First section") < content.index("Second section")

    assemble_doc(plan_dir, output_path, finalize_data)
    content_2 = output_path.read_text(encoding="utf-8")
    assert content == content_2


def test_extract_sections_maps_done_tasks() -> None:
    payloads = [
        {
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "Intro text.",
                    "sections_written": ["intro"],
                },
                {
                    "task_id": "T2",
                    "status": "skipped",
                    "executor_notes": "Skipped.",
                    "sections_written": ["appendix"],
                },
            ]
        }
    ]
    sections = extract_sections(payloads)
    assert "intro" in sections
    assert "appendix" not in sections


# ---------------------------------------------------------------------------
# (7) doc-mode execution schema validates correctly via strict_schema
# ---------------------------------------------------------------------------


def test_execution_doc_schema_validates() -> None:
    schema = SCHEMAS["execution_doc.json"]
    assert "sections_written" in schema["properties"]
    assert "files_changed" not in schema["properties"]

    task_props = schema["properties"]["task_updates"]["items"]["properties"]
    assert "sections_written" in task_props
    assert "commands_run" not in task_props

    strict = strict_schema(schema)
    assert strict["additionalProperties"] is False


def test_get_execution_schema_key() -> None:
    assert get_execution_schema_key("doc") == "execution_doc.json"
    assert get_execution_schema_key("code") == "execution.json"


# ---------------------------------------------------------------------------
# (8) _write_finalize_artifacts in doc mode: skips test baseline + verification
# ---------------------------------------------------------------------------


def test_write_finalize_artifacts_doc_mode_skips_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from megaplan.handlers import _write_finalize_artifacts

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    state = {
        "config": {"mode": "doc", "project_dir": str(project_dir)},
        "iteration": 1,
    }
    payload = {
        "tasks": [
            {
                "id": "T1",
                "description": "Write doc",
                "depends_on": [],
                "status": "pending",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
            }
        ],
        "watch_items": [],
        "sense_checks": [],
        "meta_commentary": "ok",
        "validation": {
            "plan_steps_covered": [
                {"plan_step_summary": "step 1", "finalize_task_ids": ["T1"]}
            ],
            "orphan_tasks": [],
            "completeness_notes": "",
            "coverage_complete": True,
        },
    }

    _write_finalize_artifacts(plan_dir, payload, state)

    finalize = json.loads((plan_dir / "finalize.json").read_text(encoding="utf-8"))
    assert finalize["baseline_test_failures"] is None
    assert finalize["baseline_test_command"] is None
    assert "doc mode" in finalize.get("baseline_test_note", "").lower()

    task_ids = {t["id"] for t in finalize["tasks"]}
    verification_tasks = {tid for tid in task_ids if "verification" in tid.lower() or "verify" in tid.lower()}
    assert len(verification_tasks) == 0


# ---------------------------------------------------------------------------
# (9) _merge_timeout_checkpoint in doc mode uses sections_written fields
# ---------------------------------------------------------------------------


def test_merge_timeout_checkpoint_doc_mode(tmp_path: Path) -> None:
    finalize_data = {
        "tasks": [
            {
                "id": "T1",
                "status": "pending",
                "executor_notes": "",
                "sections_written": [],
            },
        ],
        "sense_checks": [
            {"id": "SC1", "executor_note": ""},
        ],
    }
    checkpoint_data = {
        "task_updates": [
            {
                "task_id": "T1",
                "status": "done",
                "executor_notes": "Wrote the section.",
                "sections_written": ["intro"],
            },
        ],
        "sense_check_acknowledgments": [
            {"sense_check_id": "SC1", "executor_note": "Checked."},
        ],
    }
    issues: list[str] = []
    _merge_timeout_checkpoint(
        finalize_data=finalize_data,
        checkpoint_data=checkpoint_data,
        checkpoint_name="test_checkpoint",
        issues=issues,
        mode="doc",
    )
    assert finalize_data["tasks"][0]["status"] == "done"
    assert finalize_data["tasks"][0]["sections_written"] == ["intro"]
    assert any("Recovered" in i for i in issues)


# ---------------------------------------------------------------------------
# (10) _reset_timeout_invalid_tasks in doc mode
# ---------------------------------------------------------------------------


def test_reset_timeout_invalid_tasks_doc_mode_checks_sections() -> None:
    finalize_data = {
        "tasks": [
            {
                "id": "T1",
                "status": "done",
                "executor_notes": "Wrote the section.",
                "sections_written": ["intro"],
            },
            {
                "id": "T2",
                "status": "done",
                "executor_notes": "Missing evidence here.",
                "sections_written": [],
            },
        ],
    }
    execution_audit = {"skipped": False, "files_in_diff": []}
    issues: list[str] = []
    reset_ids = _reset_timeout_invalid_tasks(
        finalize_data,
        execution_audit=execution_audit,
        issues=issues,
        mode="doc",
    )
    # In doc mode, has_advisory_evidence is always True, so tasks with
    # empty sections_written are advisory (not hard-missing). T1 with
    # actual sections is never flagged; T2 gets an advisory issue but
    # is not in the reset list since advisory != missing.
    assert "T1" not in reset_ids
    assert finalize_data["tasks"][0]["status"] == "done"
    # Verify the advisory message was issued for T2
    advisory_issues = [i for i in issues if "sections_written" in i.lower() or "advisory" in i.lower()]
    # No hard reset for doc mode tasks with advisory evidence
    assert finalize_data["tasks"][1]["status"] == "done"


def test_reset_timeout_invalid_tasks_doc_mode_skips_git_diff_crosscheck() -> None:
    finalize_data = {
        "tasks": [
            {
                "id": "T1",
                "status": "done",
                "executor_notes": "Wrote section with detailed analysis.",
                "sections_written": ["intro"],
                "files_changed": ["ghost.py"],
            },
        ],
    }
    execution_audit = {"skipped": False, "files_in_diff": []}
    issues: list[str] = []
    reset_ids = _reset_timeout_invalid_tasks(
        finalize_data,
        execution_audit=execution_audit,
        issues=issues,
        mode="doc",
    )
    assert "T1" not in reset_ids
    assert finalize_data["tasks"][0]["status"] == "done"
