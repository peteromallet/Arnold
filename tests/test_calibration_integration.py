from __future__ import annotations

import json
from pathlib import Path

import pytest

import megaplan
from megaplan.calibration import (
    CapabilityClaim,
    EvaluandRef,
    ModelIdentity,
    project_tier_models,
    read_capability_claims,
    resolve_evaluand,
    write_capability_claim,
)
from megaplan.calibration.ledger import _canonical_json
from megaplan.handlers.execute import _extract_execute_tier_map
from megaplan.handlers.finalize import _write_finalize_artifacts
from megaplan.execute.batch import _batch_task_signature, _calibration_tier_spec
from megaplan.observability.evaluand import EvaluandRecord, write_evaluand_event
from tests.conftest import bootstrap_fixture, load_state, make_args_factory, read_json


_PROFILE_TEXT = """\
[profiles.cal-int]
vendor_locked = false
plan = "claude:low"
execute = "hermes:deepseek-flash"
feedback = "claude:low"

[profiles.cal-int.tier_models.execute]
2 = "hermes:deepseek-flash"
4 = "claude:medium"
5 = "claude:high"
"""


def _init_calibration_plan(root: Path, project_dir: Path) -> tuple[Path, dict, Path]:
    profiles_path = project_dir / ".megaplan" / "profiles.toml"
    profiles_path.parent.mkdir(parents=True, exist_ok=True)
    profiles_path.write_text(_PROFILE_TEXT, encoding="utf-8")

    make_args = make_args_factory(project_dir)
    response = megaplan.handle_init(
        root,
        make_args(
            profile="cal-int",
            name="calibration-integration",
            auto_approve=True,
            robustness="standard",
        ),
    )
    plan_dir = megaplan.plans_root(root) / response["plan"]
    state = load_state(plan_dir)
    return plan_dir, state, profiles_path


def _write_execute_history(
    plan_dir: Path,
    state: dict,
    *,
    spec: str,
    projected_tier: int | None,
    counterfactual_tag: str | None,
) -> dict:
    state = json.loads(json.dumps(state))
    history_entry = {
        "step": "execute",
        "timestamp": "2026-05-31T00:00:00Z",
        "duration_ms": 5,
        "cost_usd": 1.5,
        "result": "success",
        "output_file": "execution_batch_1.json",
        "batch_complexity": 4,
        "tier_model_spec": spec,
        "tier_model_resolved": f"resolved::{spec}",
        "tier_projected": projected_tier,
    }
    if counterfactual_tag is not None:
        history_entry["tier_counterfactual_tag"] = counterfactual_tag
    state.setdefault("history", []).append(history_entry)
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps({"task_updates": [{"task_id": "T1", "status": "done"}]}, indent=2) + "\n",
        encoding="utf-8",
    )
    (plan_dir / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return state


def _finalize_payload(ref: EvaluandRef) -> dict:
    return {
        "tasks": [
            {
                "id": "T1",
                "description": "Ship the calibration wiring",
                "depends_on": [],
                "status": "pending",
                "complexity": 4,
                "complexity_justification": "Integration wiring across execute/finalize and ledger.",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
                "metadata": {"evaluand_ref": ref.to_json()},
            },
            {
                "id": "T2",
                "description": "Run the full test module to verify the calibration path.",
                "depends_on": ["T1"],
                "status": "pending",
                "complexity": 2,
                "complexity_justification": "Focused verification work.",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
            },
        ],
        "watch_items": [],
        "sense_checks": [],
    }


def _seed_claim(
    plan_dir: Path,
    ref: EvaluandRef,
    *,
    task_signature: str,
    predicted_tier: int,
    routed_tier_spec: str,
    recorded_at: float,
) -> None:
    write_capability_claim(
        CapabilityClaim(
            outcome=ref,
            task_signature=task_signature,
            routed_model=ModelIdentity(f"seeded::{routed_tier_spec}"),
            recorded_at=recorded_at,
            predicted_tier=predicted_tier,
            route_phase="execute",
            routed_tier_spec=routed_tier_spec,
        ),
        plan_dir=plan_dir,
        phase="execute",
        scope="tests",
    )


def test_calibration_integration_flag_off_preserves_toml_routing_and_semantic_parity(
    bootstrap_fixture: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, project_dir = bootstrap_fixture
    plan_dir, state, profiles_path = _init_calibration_plan(root, project_dir)
    original_profiles = profiles_path.read_text(encoding="utf-8")

    tier_models = state["config"]["tier_models"]
    tier_map = _extract_execute_tier_map(tier_models)
    assert tier_map is not None

    ref = EvaluandRef(
        piece_version="piece-v1",
        judge_version="judge-v1",
        rubric_version="rubric-v1",
        input_set_hash="inputs-v1",
    )
    write_evaluand_event(
        "eval-run-off",
        EvaluandRecord(
            judge_version="judge-v1",
            rubric_version="rubric-v1",
            input_set_hash="inputs-v1",
            score=0.91,
            recorded_at=10_000.0,
            piece_version="piece-v1",
            provenance={"verifier_identity": "judge-mi", "verifier_tier": "4"},
            taint=(),
        ),
        plan_dir=plan_dir,
        phase="judge",
        scope="tests",
    )

    monkeypatch.delenv("MEGAPLAN_CALIBRATION_QUERY_ROUTE", raising=False)
    resolution = _calibration_tier_spec(
        plan_dir=plan_dir,
        tier_map=tier_map,
        batch_task_ids=["T1"],
        batch_complexity=4,
    )
    assert resolution.source == "toml"
    assert resolution.spec == "claude:medium"
    assert resolution.counterfactual_tag is None

    projected = project_tier_models([], tier_models)
    assert _canonical_json(projected) == _canonical_json(tier_models)

    updated_state = _write_execute_history(
        plan_dir,
        state,
        spec=resolution.spec or "claude:medium",
        projected_tier=resolution.projected_tier,
        counterfactual_tag=resolution.counterfactual_tag,
    )
    _write_finalize_artifacts(plan_dir, _finalize_payload(ref), updated_state)

    finalized = read_json(plan_dir / "finalize.json")
    assert finalized["tasks"][0]["complexity"] == 4
    assert finalized["tasks"][0].get("metadata", {}).get("calibration_route_report") is None
    assert read_capability_claims(plan_dir) == ()
    assert profiles_path.read_text(encoding="utf-8") == original_profiles


def test_calibration_integration_flag_on_uses_query_without_rewriting_toml(
    bootstrap_fixture: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, project_dir = bootstrap_fixture
    plan_dir, state, profiles_path = _init_calibration_plan(root, project_dir)
    original_profiles = profiles_path.read_text(encoding="utf-8")

    tier_models = state["config"]["tier_models"]
    tier_map = _extract_execute_tier_map(tier_models)
    assert tier_map is not None

    ref = EvaluandRef(
        piece_version="piece-v1",
        judge_version="judge-v1",
        rubric_version="rubric-v1",
        input_set_hash="inputs-v1",
    )
    record = EvaluandRecord(
        judge_version="judge-v1",
        rubric_version="rubric-v1",
        input_set_hash="inputs-v1",
        score=0.94,
        recorded_at=10_000.0,
        piece_version="piece-v1",
        provenance={"verifier_identity": "judge-mi", "verifier_tier": "4"},
        taint=(),
    )
    write_evaluand_event("eval-run-on", record, plan_dir=plan_dir, phase="judge", scope="tests")

    batch_signature = _batch_task_signature(["T1"], 4)
    finalize_signature = "finalize:task_id=T1:complexity=4"
    for ts in (batch_signature, finalize_signature):
        _seed_claim(
            plan_dir,
            ref,
            task_signature=ts,
            predicted_tier=5,
            routed_tier_spec="claude:high",
            recorded_at=9_990.0,
        )
        _seed_claim(
            plan_dir,
            ref,
            task_signature=ts,
            predicted_tier=5,
            routed_tier_spec="claude:high",
            recorded_at=9_995.0,
        )
    _seed_claim(
        plan_dir,
        ref,
        task_signature="execute:tier-2",
        predicted_tier=2,
        routed_tier_spec="hermes:deepseek-flash",
        recorded_at=9_996.0,
    )
    _seed_claim(
        plan_dir,
        ref,
        task_signature="execute:tier-4-a",
        predicted_tier=4,
        routed_tier_spec="claude:high",
        recorded_at=9_996.5,
    )
    _seed_claim(
        plan_dir,
        ref,
        task_signature="execute:tier-4-b",
        predicted_tier=4,
        routed_tier_spec="claude:high",
        recorded_at=9_998.0,
    )
    _seed_claim(
        plan_dir,
        ref,
        task_signature="execute:tier-5",
        predicted_tier=5,
        routed_tier_spec="claude:high",
        recorded_at=9_997.0,
    )

    monkeypatch.setenv("MEGAPLAN_CALIBRATION_QUERY_ROUTE", "1")
    resolution = _calibration_tier_spec(
        plan_dir=plan_dir,
        tier_map=tier_map,
        batch_task_ids=["T1"],
        batch_complexity=4,
    )
    assert resolution.source == "calibration_query"
    assert resolution.spec == "claude:high"
    assert resolution.projected_tier == 5

    updated_state = _write_execute_history(
        plan_dir,
        state,
        spec=resolution.spec or "claude:high",
        projected_tier=resolution.projected_tier,
        counterfactual_tag=resolution.counterfactual_tag,
    )
    seeded_count = len(read_capability_claims(plan_dir))
    _write_finalize_artifacts(plan_dir, _finalize_payload(ref), updated_state)

    finalized = read_json(plan_dir / "finalize.json")
    report = finalized["tasks"][0]["metadata"]["calibration_route_report"]
    assert report["authoritative_complexity"] == 4
    assert report["suggestion"]["tier_spec"] == "claude:high"
    assert report["suggestion"]["projected_tier"] == 5

    claims = read_capability_claims(plan_dir)
    assert len(claims) == seeded_count + 1
    written = next(
        claim
        for claim in claims
        if claim.verifier_identity == "judge-mi"
        and claim.task_signature == finalize_signature
    )
    payload = written.to_json()
    assert "recorded_at" in payload and "routed_model" in payload
    assert "timestamp" not in payload and "routed_model_identity" not in payload
    assert CapabilityClaim.from_json(payload) == written

    evaluand = resolve_evaluand(plan_dir, written.outcome)
    assert evaluand.is_available
    assert evaluand.record is not None
    assert evaluand.record.attribution_key(strict=True) == ref.key

    projected = project_tier_models(claims, tier_models, now=10_000.0)
    assert projected["execute"]["4"] == "claude:high"
    assert projected["execute"]["4"] != tier_models["execute"]["4"]
    assert projected["execute"]["2"] == "hermes:deepseek-flash"
    assert projected["execute"]["5"] == "claude:high"
    assert profiles_path.read_text(encoding="utf-8") == original_profiles
