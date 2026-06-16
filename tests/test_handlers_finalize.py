from __future__ import annotations

from pathlib import Path

import pytest

import arnold.pipelines.megaplan as megaplan
from arnold.pipelines.megaplan.handlers.finalize import (
    _apply_programmatic_coverage,
    _validate_finalize_payload,
    _write_finalize_artifacts,
)
from arnold.pipelines.megaplan.model_seam import (
    audit_step_payload,
    ModelStructuralAuditError,
    schema_audits_step_payload,
    CompatibilityMode,
)
from arnold.pipelines.megaplan.types import CliError
from arnold.pipelines.megaplan.workers import WorkerResult
from tests.conftest import PlanFixture, load_state, read_json


def _state(project_dir: Path) -> dict:
    return {
        "name": "coverage",
        "idea": "coverage",
        "current_state": "gated",
        "iteration": 1,
        "config": {"project_dir": str(project_dir), "mode": "code"},
        "plan_versions": [{"version": 1, "file": "plan_v1.md", "hash": "sha256:test"}],
        "history": [],
        "sessions": {},
        "meta": {},
    }


def _payload(description: str) -> dict:
    return {
        "tasks": [
            {
                "id": "T1",
                "description": description,
                "depends_on": [],
                "status": "pending",
                "complexity": 2,
                "complexity_justification": "Localized change with an obvious test update → tier 2.",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
            }
        ],
        "watch_items": [],
        "sense_checks": [],
        "user_actions": [],
        "meta_commentary": "ok",
    }


def test_programmatic_coverage_check_detects_uncovered_step(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    (plan_dir / "plan_v1.md").write_text("## Step 1: Update auth.py\nShip auth fix.\n", encoding="utf-8")
    payload = _payload("Update db.py")

    _apply_programmatic_coverage(payload, plan_dir, _state(project_dir))

    validation = payload["validation"]
    assert validation["coverage_complete"] is False
    assert validation["plan_steps_covered"] == [
        {"plan_step_summary": "Update auth.py", "finalize_item_ids": []}
    ]
    assert "auto-detected uncovered step: Update auth.py" in validation["completeness_notes"]


def test_programmatic_coverage_check_passes_when_covered(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    (plan_dir / "plan_v1.md").write_text("## Step 1: Update auth.py\nShip auth fix.\n", encoding="utf-8")
    payload = _payload("Update auth.py")

    _apply_programmatic_coverage(payload, plan_dir, _state(project_dir))

    validation = payload["validation"]
    assert validation["coverage_complete"] is True
    assert validation["plan_steps_covered"] == [
        {"plan_step_summary": "Update auth.py", "finalize_item_ids": ["T1"]}
    ]


def test_finalize_snapshot_status(plan_fixture: PlanFixture) -> None:
    state = load_state(plan_fixture.plan_dir)
    state["config"]["mode"] = "code"
    state["plan_versions"] = [{"version": 1, "file": "plan_v1.md", "hash": "sha256:test"}]
    (plan_fixture.plan_dir / "plan_v1.md").write_text(
        "## Step 1: Implement test idea\nShip the code change.\n",
        encoding="utf-8",
    )
    payload = _payload("Implement test idea")
    payload["tasks"].append(
        {
            "id": "T2",
            "description": "Run pytest to verify the change.",
            "depends_on": ["T1"],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
            "kind": "test",
        }
    )

    _write_finalize_artifacts(plan_fixture.plan_dir, payload, state)

    assert (plan_fixture.plan_dir / "finalize_snapshot.json").exists()
    assert read_json(plan_fixture.plan_dir / "finalize_snapshot.json") == read_json(
        plan_fixture.plan_dir / "finalize.json"
    )


def test_strict_finalize_validation_accepts_missing_final_test_task(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = load_state(plan_fixture.plan_dir)
    state["config"]["mode"] = "code"
    worker = WorkerResult(
        payload=_payload("Implement test idea"),
        raw_output="missing test task",
        duration_ms=1,
        cost_usd=0.0,
        session_id="strict-finalize",
    )
    monkeypatch.setenv("MEGAPLAN_FINALIZE_STRICT_VALIDATION", "1")

    _validate_finalize_payload(plan_fixture.plan_dir, state, worker)


def test_validate_finalize_payload_strips_nullable_optional_task_objects(
    plan_fixture: PlanFixture,
) -> None:
    state = load_state(plan_fixture.plan_dir)
    payload = _payload("Implement test idea")
    payload["tasks"][0]["stance"] = None
    payload["tasks"][0]["stop_signal"] = None
    worker = WorkerResult(
        payload=payload,
        raw_output="nullable optional objects",
        duration_ms=1,
        cost_usd=0.0,
        session_id="strict-finalize-null-optionals",
    )

    _validate_finalize_payload(plan_fixture.plan_dir, state, worker)

    assert "stance" not in payload["tasks"][0]
    assert "stop_signal" not in payload["tasks"][0]


# ---------------------------------------------------------------------------
# T8: finalize seam audit migration tests
# ---------------------------------------------------------------------------

_FINALIZE_VALID_PAYLOAD: dict = {
    "tasks": [
        {
            "id": "T1",
            "description": "Implement the change.",
            "depends_on": [],
            "status": "pending",
            "complexity": 2,
            "complexity_justification": "Simple change with clear test path.",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        }
    ],
    "watch_items": [],
    "sense_checks": [],
    "user_actions": [],
    "meta_commentary": "ok",
    "validation": {
        "plan_steps_covered": [],
        "orphan_tasks": [],
        "completeness_notes": "",
        "coverage_complete": True,
    },
}


def test_audit_step_payload_rejects_wrong_typed_tasks() -> None:
    """Schema audit must reject a finalize payload where tasks is not a list."""
    payload = dict(_FINALIZE_VALID_PAYLOAD)
    payload["tasks"] = "not-a-list"
    with pytest.raises(ModelStructuralAuditError) as exc_info:
        audit_step_payload("finalize", payload)
    assert "type_mismatch" in str(exc_info.value)


def test_audit_step_payload_rejects_missing_required_field() -> None:
    """Schema audit must reject a finalize payload missing a required top-level field."""
    payload = dict(_FINALIZE_VALID_PAYLOAD)
    del payload["sense_checks"]
    with pytest.raises(ModelStructuralAuditError):
        audit_step_payload("finalize", payload)


def test_audit_step_payload_rejects_hallucinated_top_level_key() -> None:
    """Schema audit must reject a finalize payload with an unknown top-level key."""
    payload = dict(_FINALIZE_VALID_PAYLOAD)
    payload["extra_hallucinated_field"] = "should-not-be-here"
    with pytest.raises(ModelStructuralAuditError):
        audit_step_payload("finalize", payload)


def test_audit_step_payload_accepts_valid_finalize_payload() -> None:
    """Schema audit must accept a valid finalize payload."""
    audit_step_payload("finalize", dict(_FINALIZE_VALID_PAYLOAD))


def test_audit_step_payload_rejects_task_without_complexity() -> None:
    """Schema audit must reject a task missing the required complexity field."""
    payload = dict(_FINALIZE_VALID_PAYLOAD)
    payload["tasks"] = [
        {
            "id": "T1",
            "description": "Missing complexity",
            "depends_on": [],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        }
    ]
    with pytest.raises(ModelStructuralAuditError):
        audit_step_payload("finalize", payload)


def test_audit_step_payload_rejects_task_with_wrong_type_complexity() -> None:
    """Schema audit must reject a task where complexity is a string instead of int."""
    payload = dict(_FINALIZE_VALID_PAYLOAD)
    payload["tasks"] = [
        {
            "id": "T1",
            "description": "Wrong type complexity",
            "depends_on": [],
            "status": "pending",
            "complexity": "high",
            "complexity_justification": "bogus",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        }
    ]
    with pytest.raises(ModelStructuralAuditError) as exc_info:
        audit_step_payload("finalize", payload)
    assert "type_mismatch" in str(exc_info.value)


def test_finalize_is_native_capture() -> None:
    """finalize must be in the native capture set (schema-audited, no legacy compat repair)."""
    assert schema_audits_step_payload("finalize") is True


def test_finalize_native_mode_is_compatibility_native() -> None:
    """finalize compatibility mode must be NATIVE."""
    from arnold.pipelines.megaplan.model_seam import _compatibility_mode_for_step
    assert _compatibility_mode_for_step("finalize") is CompatibilityMode.NATIVE


# ---------------------------------------------------------------------------
# T8: finalize scratch promotion tests
# ---------------------------------------------------------------------------

_SCRATCH_PAYLOAD: dict = {
    "tasks": [
        {
            "id": "T1",
            "description": "Scratch-promoted task.",
            "depends_on": [],
            "status": "pending",
            "complexity": 3,
            "complexity_justification": "Scratch file task.",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        }
    ],
    "watch_items": ["watch scratch"],
    "sense_checks": [],
    "user_actions": [],
    "meta_commentary": "from scratch",
}

_INLINE_PAYLOAD: dict = {
    "tasks": [
        {
            "id": "T2",
            "description": "Inline fallback task.",
            "depends_on": [],
            "status": "pending",
            "complexity": 1,
            "complexity_justification": "Inline fallback.",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        }
    ],
    "watch_items": ["watch inline"],
    "sense_checks": [],
    "user_actions": [],
    "meta_commentary": "from inline",
}


def _make_worker(payload: dict[str, Any] | None = None) -> WorkerResult:
    return WorkerResult(
        payload=payload or dict(_INLINE_PAYLOAD),
        raw_output="test",
        duration_ms=1,
        cost_usd=0.0,
        session_id="scratch-test",
    )


def _write_seed(plan_dir: Path, content: dict[str, Any] | None = None) -> str:
    """Write a seed template and return its JSON text."""
    import json
    seed = content if content is not None else {
        "tasks": [],
        "user_actions": [],
        "sense_checks": [],
        "watch_items": [],
        "meta_commentary": "",
    }
    text = json.dumps(seed, indent=2)
    (plan_dir / "finalize_output.json").write_text(text, encoding="utf-8")
    return text


def _write_filled_scratch(plan_dir: Path, content: dict[str, Any]) -> None:
    """Write a filled (different from seed) scratch file."""
    import json
    (plan_dir / "finalize_output.json").write_text(
        json.dumps(content, indent=2), encoding="utf-8"
    )


def _known_keys() -> frozenset[str]:
    return frozenset({"tasks", "user_actions", "sense_checks", "watch_items", "meta_commentary"})


def test_promote_scratch_prefers_filled_over_worker_payload(tmp_path: Path) -> None:
    """T8: Valid filled scratch must be preferred over worker.payload."""
    from arnold.pipelines.megaplan.handlers.structured_output import promote_scratch

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    seed_json = _write_seed(plan_dir)
    _write_filled_scratch(plan_dir, dict(_SCRATCH_PAYLOAD))
    worker = _make_worker()

    status, payload = promote_scratch(
        plan_dir,
        "finalize_output.json",
        _known_keys(),
        worker,
        seed_json=seed_json,
        file_fill_instructed=True,
    )

    assert status == "filled"
    assert payload["tasks"][0]["id"] == "T1"  # scratch wins
    assert payload["meta_commentary"] == "from scratch"


def test_promote_scratch_falls_back_on_missing_scratch(tmp_path: Path) -> None:
    """T8: Missing scratch file must fall back to worker.payload."""
    from arnold.pipelines.megaplan.handlers.structured_output import promote_scratch

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    # No seed, no scratch file
    worker = _make_worker()

    status, payload = promote_scratch(
        plan_dir,
        "finalize_output.json",
        _known_keys(),
        worker,
        seed_json=None,
        file_fill_instructed=True,
    )

    assert status == "missing"
    assert payload["tasks"][0]["id"] == "T2"  # inline fallback
    assert payload["meta_commentary"] == "from inline"


def test_promote_scratch_falls_back_on_unmodified_scratch(tmp_path: Path) -> None:
    """T8: Unmodified scratch (byte-identical to seed) must fall back to worker.payload."""
    from arnold.pipelines.megaplan.handlers.structured_output import promote_scratch

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    seed_json = _write_seed(plan_dir)
    # Scratch file is byte-identical to seed — the model did not fill it.
    worker = _make_worker()

    status, payload = promote_scratch(
        plan_dir,
        "finalize_output.json",
        _known_keys(),
        worker,
        seed_json=seed_json,
        file_fill_instructed=True,
    )

    assert status == "unmodified"
    assert payload["tasks"][0]["id"] == "T2"  # inline fallback
    assert payload["meta_commentary"] == "from inline"


def test_promote_scratch_fails_hard_on_modified_invalid_with_file_fill(
    tmp_path: Path,
) -> None:
    """T8: Modified-but-invalid scratch + file_fill_instructed=True → ValueError."""
    from arnold.pipelines.megaplan.handlers.structured_output import promote_scratch

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    seed_json = _write_seed(plan_dir)
    # Write invalid JSON that differs from seed
    (plan_dir / "finalize_output.json").write_text("not valid json {{{", encoding="utf-8")
    worker = _make_worker()

    with pytest.raises(ValueError, match="does not contain valid JSON"):
        promote_scratch(
            plan_dir,
            "finalize_output.json",
            _known_keys(),
            worker,
            seed_json=seed_json,
            file_fill_instructed=True,
        )


def test_promote_scratch_falls_back_on_modified_invalid_without_file_fill(
    tmp_path: Path,
) -> None:
    """T8: Modified-but-invalid scratch + file_fill_instructed=False → fallback."""
    from arnold.pipelines.megaplan.handlers.structured_output import promote_scratch

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    seed_json = _write_seed(plan_dir)
    (plan_dir / "finalize_output.json").write_text("not valid json {{{", encoding="utf-8")
    worker = _make_worker()

    status, payload = promote_scratch(
        plan_dir,
        "finalize_output.json",
        _known_keys(),
        worker,
        seed_json=seed_json,
        file_fill_instructed=False,
    )

    assert status == "invalid"
    assert payload["tasks"][0]["id"] == "T2"  # inline fallback


def test_promote_scratch_strips_unknown_keys(tmp_path: Path) -> None:
    """T8: Unknown top-level keys must be stripped from promoted scratch."""
    from arnold.pipelines.megaplan.handlers.structured_output import promote_scratch

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    seed_json = _write_seed(plan_dir)
    filled = dict(_SCRATCH_PAYLOAD)
    filled["extra_hallucinated"] = "should-be-stripped"
    filled["another_bogus"] = 42
    _write_filled_scratch(plan_dir, filled)
    worker = _make_worker()

    status, payload = promote_scratch(
        plan_dir,
        "finalize_output.json",
        _known_keys(),
        worker,
        seed_json=seed_json,
        file_fill_instructed=True,
    )

    assert status == "filled"
    assert "extra_hallucinated" not in payload
    assert "another_bogus" not in payload
    assert payload["tasks"][0]["id"] == "T1"  # scratch content preserved


def test_handle_finalize_scratch_promotion_integration(
    plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T8: handle_finalize (mock) creates canonical artifacts; scratch promotion
    is wired and the seed file is written by the prompt builder.

    In mock mode the seed is always written by _finalize_prompt (via
    render_prompt_for_dispatch), so the scratch is unmodified and the
    handler falls back to worker.payload.  We verify the promotion
    wiring does not break the existing artifact pipeline."""
    import json
    from arnold.pipelines.megaplan._core import atomic_write_json
    from arnold.pipelines.megaplan.handlers.finalize import handle_finalize

    monkeypatch.setenv("MEGAPLAN_MOCK_WORKERS", "1")
    state = load_state(plan_fixture.plan_dir)
    state["config"]["mode"] = "code"
    state["config"]["project_dir"] = str(plan_fixture.project_dir)
    state["plan_versions"] = [{"version": 1, "file": "plan_v1.md", "hash": "sha256:test"}]
    state["current_state"] = "gated"
    # Persist the modified state so load_plan_locked picks it up
    atomic_write_json(plan_fixture.plan_dir / "state.json", state)
    (plan_fixture.plan_dir / "plan_v1.md").write_text(
        "## Step 1: Implement feature\nShip the feature.\n",
        encoding="utf-8",
    )

    import argparse
    args = argparse.Namespace()
    args.plan = plan_fixture.plan_dir.name
    args.profile = None
    args.mode = None
    args.robustness = None
    args.auto_approve = False
    args.phase_model = None
    args.agent = None
    args.refresh = False
    args.write = True

    response = handle_finalize(plan_fixture.root, args)

    assert response["success"] is True
    assert response["step"] == "finalize"

    # Canonical artifacts exist — scratch promotion is wired and the
    # handler fell back to worker.payload (mock mode seed may or may not
    # be written by render_prompt_for_dispatch).
    assert (plan_fixture.plan_dir / "finalize.json").exists()
    assert (plan_fixture.plan_dir / "contract.json").exists()
    assert (plan_fixture.plan_dir / "final.md").exists()
    assert (plan_fixture.plan_dir / "user_actions.md").exists()

    finalize_json = read_json(plan_fixture.plan_dir / "finalize.json")
    assert "tasks" in finalize_json
    assert "sense_checks" in finalize_json
    assert "watch_items" in finalize_json
    # The mock worker payload (inline JSON) was promoted via fallback
    assert isinstance(finalize_json["tasks"], list)


def test_handle_finalize_prefers_worker_filled_scratch_over_inline_payload(
    plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A valid worker-filled finalize_output.json beats stale inline JSON."""
    import argparse
    from arnold.pipelines.megaplan._core import atomic_write_json
    from arnold.pipelines.megaplan.handlers import finalize as finalize_handler

    state = load_state(plan_fixture.plan_dir)
    state["config"]["mode"] = "code"
    state["config"]["project_dir"] = str(plan_fixture.project_dir)
    state["plan_versions"] = [{"version": 1, "file": "plan_v1.md", "hash": "sha256:test"}]
    state["current_state"] = "gated"
    atomic_write_json(plan_fixture.plan_dir / "state.json", state)
    (plan_fixture.plan_dir / "plan_v1.md").write_text(
        "## Step 1: Implement feature\nShip the feature.\n",
        encoding="utf-8",
    )

    scratch_payload = _payload("Implement feature")
    inline_payload = _payload("Stale inline worker self-report")
    inline_payload["tasks"][0]["status"] = "done"

    def fake_run_worker(*_args, **_kwargs):
        _write_filled_scratch(plan_fixture.plan_dir, scratch_payload)
        return _make_worker(inline_payload), "codex", "persistent", False

    monkeypatch.setattr(finalize_handler, "_run_worker", fake_run_worker)

    args = argparse.Namespace(
        plan=plan_fixture.plan_dir.name,
        profile=None,
        mode=None,
        robustness=None,
        auto_approve=False,
        phase_model=None,
        agent=None,
        refresh=False,
        write=True,
    )

    response = finalize_handler.handle_finalize(plan_fixture.root, args)

    assert response["success"] is True
    finalize_json = read_json(plan_fixture.plan_dir / "finalize.json")
    assert finalize_json["tasks"][0]["description"] == "Implement feature"
    assert finalize_json["tasks"][0]["status"] == "pending"


# ---------------------------------------------------------------------------
# T9: finalize artifact regression tests
# ---------------------------------------------------------------------------

_FULL_FINALIZE_PAYLOAD: dict = {
    "tasks": [
        {
            "id": "T1",
            "description": "Implement the feature.",
            "depends_on": [],
            "status": "pending",
            "kind": "code",
            "complexity": 2,
            "complexity_justification": "Simple change with clear test path.",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "auto_attributed_files": None,
            "evidence_files": [],
            "reviewer_verdict": "",
            "stance": None,
            "stop_signal": None,
        }
    ],
    "watch_items": [],
    "sense_checks": [
        {
            "id": "SC1",
            "task_id": "T1",
            "question": "Is the feature working?",
            "executor_note": "",
            "verdict": "",
        }
    ],
    "user_actions": [
        {
            "id": "U1",
            "description": "Verify deployment config",
            "phase": "before_execute",
            "blocks_task_ids": None,
            "rationale": None,
            "requires_human_only_reason": None,
        }
    ],
    "meta_commentary": "All tasks look good.",
    "validation": {
        "plan_steps_covered": [
            {"plan_step_summary": "Implement feature", "finalize_item_ids": ["T1"]}
        ],
        "orphan_tasks": [],
        "completeness_notes": "All plan steps mapped.",
        "coverage_complete": True,
    },
    "baseline_test_failures": None,
    "baseline_test_command": None,
    "baseline_test_note": "",
    "suite_runs_ndjson_path": None,
}


def test_write_finalize_artifacts_produces_all_files(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T9: _write_finalize_artifacts must produce finalize.json, contract.json,
    final.md, user_actions.md, and finalize_snapshot.json."""
    monkeypatch.setenv("MEGAPLAN_MOCK_WORKERS", "1")
    state = load_state(plan_fixture.plan_dir)
    state["config"]["mode"] = "code"
    state["plan_versions"] = [{"version": 1, "file": "plan_v1.md", "hash": "sha256:test"}]
    (plan_fixture.plan_dir / "plan_v1.md").write_text(
        "## Step 1: Implement feature\nShip the feature.\n",
        encoding="utf-8",
    )

    payload = dict(_FULL_FINALIZE_PAYLOAD)
    _write_finalize_artifacts(plan_fixture.plan_dir, payload, state)

    assert (plan_fixture.plan_dir / "finalize.json").exists()
    assert (plan_fixture.plan_dir / "contract.json").exists()
    assert (plan_fixture.plan_dir / "final.md").exists()
    assert (plan_fixture.plan_dir / "user_actions.md").exists()
    assert (plan_fixture.plan_dir / "finalize_snapshot.json").exists()


def test_finalize_json_preserves_task_shape(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T9: finalize.json must preserve the task shape written by _write_finalize_artifacts."""
    monkeypatch.setenv("MEGAPLAN_MOCK_WORKERS", "1")
    state = load_state(plan_fixture.plan_dir)
    state["config"]["mode"] = "code"
    state["plan_versions"] = [{"version": 1, "file": "plan_v1.md", "hash": "sha256:test"}]
    (plan_fixture.plan_dir / "plan_v1.md").write_text(
        "## Step 1: Implement feature\nShip the feature.\n",
        encoding="utf-8",
    )

    payload = dict(_FULL_FINALIZE_PAYLOAD)
    _write_finalize_artifacts(plan_fixture.plan_dir, payload, state)

    finalized = read_json(plan_fixture.plan_dir / "finalize.json")
    # The first task may be an injected gate task from _ensure_user_actions_pre_gate_task,
    # so find T1 by id rather than relying on index 0.
    task = next(t for t in finalized["tasks"] if t["id"] == "T1")
    assert task["id"] == "T1"
    assert task["description"] == "Implement the feature."
    # depends_on may be extended by _ensure_user_actions_pre_gate_task injection
    assert isinstance(task["depends_on"], list)
    assert task["status"] == "pending"
    assert task["kind"] == "code"
    assert task["complexity"] == 2
    assert task["complexity_justification"] == "Simple change with clear test path."
    assert task["executor_notes"] == ""
    assert task["files_changed"] == []
    assert task["commands_run"] == []
    assert task["evidence_files"] == []
    assert task["reviewer_verdict"] == ""
    assert task["stance"] is None
    assert task["stop_signal"] is None


def test_contract_json_preserves_provides_and_assumes(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T9: contract.json must contain the provides/assumes structure."""
    monkeypatch.setenv("MEGAPLAN_MOCK_WORKERS", "1")
    state = load_state(plan_fixture.plan_dir)
    state["config"]["mode"] = "code"
    state["plan_versions"] = [{"version": 1, "file": "plan_v1.md", "hash": "sha256:test"}]
    (plan_fixture.plan_dir / "plan_v1.md").write_text(
        "## Step 1: Implement feature\nShip the feature.\n",
        encoding="utf-8",
    )

    payload = dict(_FULL_FINALIZE_PAYLOAD)
    payload["provides"] = []
    payload["assumes"] = []
    _write_finalize_artifacts(plan_fixture.plan_dir, payload, state)

    contract = read_json(plan_fixture.plan_dir / "contract.json")
    assert "provides" in contract
    assert "assumes" in contract
    assert isinstance(contract["provides"], list)
    assert isinstance(contract["assumes"], list)


def test_final_md_contains_task_and_sense_check_content(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T9: final.md must contain rendered task descriptions and sense checks."""
    monkeypatch.setenv("MEGAPLAN_MOCK_WORKERS", "1")
    state = load_state(plan_fixture.plan_dir)
    state["config"]["mode"] = "code"
    state["plan_versions"] = [{"version": 1, "file": "plan_v1.md", "hash": "sha256:test"}]
    (plan_fixture.plan_dir / "plan_v1.md").write_text(
        "## Step 1: Implement feature\nShip the feature.\n",
        encoding="utf-8",
    )

    payload = dict(_FULL_FINALIZE_PAYLOAD)
    _write_finalize_artifacts(plan_fixture.plan_dir, payload, state)

    final_md = (plan_fixture.plan_dir / "final.md").read_text(encoding="utf-8")
    assert "Implement the feature" in final_md
    assert "Is the feature working?" in final_md


def test_user_actions_md_contains_actions(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T9: user_actions.md must contain listed user actions by phase."""
    monkeypatch.setenv("MEGAPLAN_MOCK_WORKERS", "1")
    state = load_state(plan_fixture.plan_dir)
    state["config"]["mode"] = "code"
    state["plan_versions"] = [{"version": 1, "file": "plan_v1.md", "hash": "sha256:test"}]
    (plan_fixture.plan_dir / "plan_v1.md").write_text(
        "## Step 1: Implement feature\nShip the feature.\n",
        encoding="utf-8",
    )

    payload = dict(_FULL_FINALIZE_PAYLOAD)
    _write_finalize_artifacts(plan_fixture.plan_dir, payload, state)

    user_actions_md = (plan_fixture.plan_dir / "user_actions.md").read_text(encoding="utf-8")
    assert "# User Actions" in user_actions_md
    assert "U1" in user_actions_md
    assert "Verify deployment config" in user_actions_md
    assert "Before Execute" in user_actions_md


def test_finalize_snapshot_matches_finalize_json(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T9: finalize_snapshot.json must be byte-identical to finalize.json."""
    monkeypatch.setenv("MEGAPLAN_MOCK_WORKERS", "1")
    state = load_state(plan_fixture.plan_dir)
    state["config"]["mode"] = "code"
    state["plan_versions"] = [{"version": 1, "file": "plan_v1.md", "hash": "sha256:test"}]
    (plan_fixture.plan_dir / "plan_v1.md").write_text(
        "## Step 1: Implement feature\nShip the feature.\n",
        encoding="utf-8",
    )

    payload = dict(_FULL_FINALIZE_PAYLOAD)
    _write_finalize_artifacts(plan_fixture.plan_dir, payload, state)

    finalized = read_json(plan_fixture.plan_dir / "finalize.json")
    snapshot = read_json(plan_fixture.plan_dir / "finalize_snapshot.json")
    assert finalized == snapshot


def test_finalize_worker_normalization_helper_is_deleted() -> None:
    import arnold.pipelines.megaplan.workers._impl as workers_impl

    assert not hasattr(workers_impl, "_normalize_worker_payload")


def test_finalize_schema_audit_is_validation_authority() -> None:
    """T9: schema audit (audit_step_payload) must be the sole structural
    validation authority for finalize — the schema-audit path catches
    structural violations that legacy validate_payload would miss.

    validate_payload only checks key presence, not types. Schema audit
    rejects wrong types. This proves the migration is complete.
    """
    with pytest.raises(ImportError):
        exec("from arnold.pipelines.megaplan.workers._impl import validate_payload", {})

    # Schema audit is now the only structural validation authority.
    with pytest.raises(ModelStructuralAuditError) as exc_info:
        audit_step_payload(
            "finalize",
            {
                "tasks": "not-a-list",
                "watch_items": None,
                "sense_checks": {},
                "user_actions": 7,
                "meta_commentary": True,
                "validation": object(),
                "baseline_test_failures": None,
                "baseline_test_command": None,
                "baseline_test_note": "",
                "suite_runs_ndjson_path": None,
            },
        )
    assert "type_mismatch" in str(exc_info.value)
