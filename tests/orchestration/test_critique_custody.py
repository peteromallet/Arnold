from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan._core import atomic_write_json, atomic_write_text
from arnold_pipelines.megaplan.flags import (
    update_flags_after_critique,
    update_flags_after_gate,
    update_flags_after_revise,
)
from arnold_pipelines.megaplan.handlers.plan import _build_verifiability_flags
from arnold_pipelines.megaplan.orchestration import critique_custody
from arnold_pipelines.megaplan.orchestration.critique_custody import (
    CritiqueCustodyError,
    assert_finalize_custody,
    bind_finalize_custody,
    prepare_critique_payload,
    validate_gate_input_custody,
    validate_finalize_resolution_coverage,
    write_critique_clearance,
    write_critique_production_receipt,
)
from arnold_pipelines.megaplan.orchestration.task_feasibility import (
    compile_task_feasibility,
)


def _state(project_dir: Path, *, iteration: int = 1, robustness: str = "full") -> dict[str, Any]:
    return {
        "name": "custody-test",
        "iteration": iteration,
        "current_state": "critiqued",
        "config": {
            "mode": "code",
            "project_dir": str(project_dir),
            "robustness": robustness,
        },
        "plan_versions": [{"version": iteration, "file": f"plan_v{iteration}.md"}],
        "history": [],
        "meta": {},
        "last_gate": {},
    }


def test_deterministic_verifiability_flags_carry_source_criterion_evidence() -> None:
    criteria = [
        {
            "criterion": "Architecture remains clear to a human reviewer.",
            "priority": "should",
            "requires": ["subjective_judgment"],
        }
    ]

    flags = _build_verifiability_flags(criteria, {"codex": {"file_read"}})

    assert len(flags) == 1
    assert flags[0]["evidence"] == (
        "success_criteria[0]: criterion='Architecture remains clear to a human "
        "reviewer.'; priority='should'; requires=['subjective_judgment']"
    )
    payload = {
        "checks": [],
        "flags": flags,
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    prepare_critique_payload(payload, expected_check_ids=[])
    assert payload["flags"][0]["id"].startswith("CF-")


def _oversized_payload(*, two_findings: bool = False) -> dict[str, Any]:
    findings = [
        {
            "detail": "Step 2 combines protocol, migration, and broad test objectives; split it.",
            "flagged": True,
        }
    ]
    flags = [
        {
            "id": "scope-god-task-2",
            "concern": "Step 2 is an oversized god-task.",
            "category": "completeness",
            "severity_hint": "likely-significant",
            "evidence": findings[0]["detail"],
            "source_check_id": "scope",
        }
    ]
    if two_findings:
        findings.append(
            {
                "detail": "Step 8 combines three independently reviewable consumers; split it.",
                "flagged": True,
            }
        )
        flags.append(
            {
                "id": "scope-god-task-8",
                "concern": "Step 8 is an oversized god-task.",
                "category": "completeness",
                "severity_hint": "likely-significant",
                "evidence": findings[1]["detail"],
                "source_check_id": "scope",
            }
        )
    return {
        "checks": [{"id": "scope", "question": "Are tasks bounded?", "findings": findings}],
        "flags": flags,
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }


def _persist_critique(
    plan_dir: Path,
    state: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    iteration = state["iteration"]
    atomic_write_text(plan_dir / f"plan_v{iteration}.md", f"# Plan v{iteration}\n\nOversized work.\n")
    atomic_write_text(plan_dir / f"critique_raw_v{iteration}.txt", "raw producer critique")
    prepare_critique_payload(payload, expected_check_ids=["scope"])
    atomic_write_json(plan_dir / f"critique_v{iteration}.json", payload)
    receipt = write_critique_production_receipt(
        plan_dir,
        state,
        payload,
        expected_check_ids=["scope"],
    )
    update_flags_after_critique(plan_dir, payload, iteration=iteration)
    return receipt


def _admitted_graph() -> dict[str, Any]:
    payload = {
        "task_contract_version": 2,
        "validation_jobs": [],
        "tasks": [
            {
                "id": "T1",
                "objective": "Implement the bounded critique custody contract.",
                "description": "Implement one independently verifiable contract slice.",
                "kind": "code",
                "complexity": 5,
                "estimated_minutes": 10,
                "depends_on": [],
                "dependency_reasons": {},
                "routing_group": "custody",
                "write_set": {"paths": ["src/custody.py", "tests/test_custody.py"], "complete": True},
                "narrow_tests": {"selectors": ["tests/test_custody.py"], "max_seconds": 120, "max_runs": 2},
                "checkpoint": {"required": False, "max_interval_seconds": 300, "records": []},
            }
        ],
    }
    payload["graph_report"] = compile_task_feasibility(payload, {})
    assert payload["graph_report"]["admitted"] is True
    return payload


def test_valid_oversized_task_finding_survives_normalization_and_reaches_gate(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state(tmp_path)
    payload = _oversized_payload()

    receipt = _persist_critique(plan_dir, state, payload)
    gate_input = validate_gate_input_custody(plan_dir, state)
    canonical_id = payload["flags"][0]["id"]

    assert canonical_id.startswith("CF-")
    assert payload["flags"][0]["producer_flag_id"] == "scope-god-task-2"
    assert receipt["finding_count"] == 1
    assert receipt["normalization"] == {
        "flagged_check_findings": 1,
        "canonical_flags": 1,
        "loss_count": 0,
    }
    assert gate_input["flag_ids"] == [canonical_id]
    assert gate_input["loss_count"] == 0


def test_effectively_clean_or_lost_gate_input_fails_closed(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state(tmp_path)
    payload = _oversized_payload()
    _persist_critique(plan_dir, state, payload)

    erased = deepcopy(payload)
    erased["flags"] = []
    atomic_write_json(plan_dir / "critique_v1.json", erased)

    with pytest.raises(CritiqueCustodyError, match="hash mismatch"):
        validate_gate_input_custody(plan_dir, state)


def test_partial_mapping_remains_blocking_at_finalize(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state(tmp_path)
    payload = _oversized_payload(two_findings=True)
    _persist_critique(plan_dir, state, payload)
    first_id, second_id = [flag["id"] for flag in payload["flags"]]

    atomic_write_text(plan_dir / "plan_v2.md", "# Plan v2\n\nStep 2 is split; Step 8 is not.\n")
    state["iteration"] = 2
    state["plan_versions"].append({"version": 2, "file": "plan_v2.md"})
    update_flags_after_revise(
        plan_dir,
        [{"id": first_id, "resolution": "addressed", "reason": "Split into T2a/T2b.", "where": "Step 2"}],
        plan_file="plan_v2.md",
        summary="Split Step 2.",
    )
    update_flags_after_gate(
        plan_dir,
        [{"flag_id": first_id, "action": "verify_fixed", "evidence": "plan_v2.md Step 2", "rationale": ""}],
    )

    with pytest.raises(CritiqueCustodyError, match=second_id):
        write_critique_clearance(plan_dir, state)


@pytest.mark.parametrize(
    "mutation,code",
    [
        (lambda payload: payload["checks"][0]["findings"][0].update(flagged="yes"), "critique_findings_malformed"),
        (lambda payload: payload["flags"].append(deepcopy(payload["flags"][0])), "critique_finding_identity_invalid"),
        (
            lambda payload: payload["flags"].append(
                {**deepcopy(payload["flags"][0]), "id": "scope-god-task-2-duplicate"}
            ),
            "critique_finding_identity_invalid",
        ),
        (lambda payload: payload["checks"][0]["findings"][0].update(silent_drop=True), "critique_findings_malformed"),
    ],
)
def test_malformed_duplicated_unmapped_or_lossy_findings_fail_closed(
    mutation, code: str
) -> None:
    payload = _oversized_payload()
    mutation(payload)
    with pytest.raises(CritiqueCustodyError) as caught:
        prepare_critique_payload(payload, expected_check_ids=["scope"])
    assert caught.value.code == code


def test_reducer_reassigns_duplicate_worker_local_ids_deterministically() -> None:
    payload = {
        "checks": [
            {
                "id": "correctness",
                "question": "Is it correct?",
                "findings": [{"detail": "Correctness evidence.", "flagged": True}],
            },
            {
                "id": "scope",
                "question": "Is it bounded?",
                "findings": [{"detail": "Scope evidence.", "flagged": True}],
            },
        ],
        "flags": [
            {
                "id": "FLAG-001",
                "concern": "Correctness concern.",
                "category": "correctness",
                "severity_hint": "likely-significant",
                "evidence": "Correctness evidence.",
                "source_check_id": "correctness",
            },
            {
                "id": "FLAG-001",
                "concern": "Scope concern.",
                "category": "completeness",
                "severity_hint": "likely-significant",
                "evidence": "Scope evidence.",
                "source_check_id": "scope",
            },
        ],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    replay = deepcopy(payload)

    prepare_critique_payload(payload, expected_check_ids=["correctness", "scope"])
    prepare_critique_payload(replay, expected_check_ids=["correctness", "scope"])

    assert payload == replay
    assert len({flag["id"] for flag in payload["flags"]}) == 2
    assert all(flag["id"].startswith("CF-") for flag in payload["flags"])
    assert [flag["producer_flag_id"] for flag in payload["flags"]] == [
        "FLAG-001",
        "FLAG-001",
    ]


def test_reducer_reassigns_unique_local_id_reused_for_different_findings() -> None:
    def payload(detail: str) -> dict[str, Any]:
        return {
            "checks": [
                {
                    "id": "verification",
                    "question": "Is the criterion verifiable?",
                    "findings": [{"detail": detail, "flagged": True}],
                }
            ],
            "flags": [
                {
                    "id": "verifiability-0",
                    "concern": detail,
                    "category": "verifiability",
                    "severity_hint": "likely-minor",
                    "evidence": detail,
                    "source_check_id": "verification",
                }
            ],
            "verified_flag_ids": ["verifiability-0"],
            "disputed_flag_ids": [],
        }

    first = payload("Criterion 11 requires human verification.")
    second = payload("Criterion 12 requires human verification.")

    prepare_critique_payload(first, expected_check_ids=["verification"])
    prepare_critique_payload(second, expected_check_ids=["verification"])

    first_id = first["flags"][0]["id"]
    second_id = second["flags"][0]["id"]
    assert first_id.startswith("CF-")
    assert second_id.startswith("CF-")
    assert first_id != second_id
    assert first["flags"][0]["producer_flag_id"] == "verifiability-0"
    assert second["flags"][0]["producer_flag_id"] == "verifiability-0"
    assert first["verified_flag_ids"] == [first_id]
    assert second["verified_flag_ids"] == [second_id]


def test_clearance_migrates_reused_legacy_nonblocking_producer_slot(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state(tmp_path)

    def payload(detail: str) -> dict[str, Any]:
        return {
            "checks": [
                {
                    "id": "scope",
                    "question": "Is the criterion verifiable?",
                    "findings": [{"detail": detail, "flagged": True}],
                }
            ],
            "flags": [
                {
                    "id": "verifiability-0",
                    "concern": detail,
                    "category": "verifiability",
                    "severity_hint": "likely-minor",
                    "evidence": detail,
                    "source_check_id": "scope",
                }
            ],
            "verified_flag_ids": ["verifiability-0"],
            "disputed_flag_ids": [],
        }

    canonical_ids: list[str] = []
    for iteration, detail in enumerate(
        (
            "Criterion 11 requires human verification.",
            "Criterion 12 requires human verification.",
        ),
        start=1,
    ):
        state["iteration"] = iteration
        if iteration > 1:
            state["plan_versions"].append(
                {"version": iteration, "file": f"plan_v{iteration}.md"}
            )
        current = payload(detail)
        receipt = _persist_critique(plan_dir, state, current)
        canonical_id = str(receipt["findings"][0]["finding_id"])
        canonical_ids.append(canonical_id)

        critique_path = plan_dir / f"critique_v{iteration}.json"
        persisted = critique_custody.read_json(critique_path)
        persisted["flags"][0]["id"] = "verifiability-0"
        persisted["flags"][0].pop("producer_flag_id", None)
        persisted["verified_flag_ids"] = ["verifiability-0"]
        atomic_write_json(critique_path, persisted)

        receipt_path = plan_dir / f"critique_custody_v{iteration}.json"
        legacy_receipt = critique_custody.read_json(receipt_path)
        legacy_receipt["critique_sha256"] = critique_custody.sha256_file(critique_path)
        legacy_receipt["critique_payload_digest"] = critique_custody._digest(persisted)
        legacy_receipt["flag_ids"] = ["verifiability-0"]
        legacy_receipt["findings"][0]["flag_id"] = "verifiability-0"
        legacy_receipt.pop("receipt_digest", None)
        legacy_receipt["receipt_digest"] = critique_custody._digest(legacy_receipt)
        atomic_write_json(receipt_path, legacy_receipt)

    atomic_write_json(
        plan_dir / "faults.json",
        {
            "flags": [
                {
                    "id": "verifiability-0",
                    "concern": "Criterion 12 requires human verification.",
                    "category": "verifiability",
                    "severity_hint": "likely-minor",
                    "evidence": "Criterion 12 requires human verification.",
                    "raised_in": "critique_v2.json",
                    "status": "open",
                    "severity": "minor",
                    "verified": True,
                    "verified_in": "critique_v2.json",
                }
            ]
        },
    )

    clearance = write_critique_clearance(plan_dir, state)

    assert clearance["finding_ids"] == [canonical_ids[1]]
    assert clearance["resolutions"] == [
        {
            "finding_id": canonical_ids[1],
            "flag_id": "verifiability-0",
            "disposition": "tracked_nonblocking_observation",
            "evidence": "Criterion 12 requires human verification.",
            "verified_in": "critique_v2.json",
        }
    ]


def test_clearance_accepts_explicit_gate_tradeoff_for_significant_finding(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state(tmp_path)
    payload = _oversized_payload()
    _persist_critique(plan_dir, state, payload)
    finding_id = payload["flags"][0]["id"]
    update_flags_after_gate(
        plan_dir,
        [
            {
                "flag_id": finding_id,
                "action": "accept_tradeoff",
                "evidence": "The bounded gate reviewed the exact remaining concern.",
                "rationale": "The risk is explicit, bounded, and accepted by the gate.",
            }
        ],
    )

    clearance = write_critique_clearance(plan_dir, state)

    assert clearance["resolutions"] == [
        {
            "finding_id": finding_id,
            "flag_id": finding_id,
            "disposition": "minor_tradeoff",
            "evidence": "The risk is explicit, bounded, and accepted by the gate.",
        }
    ]


def test_clearance_rejects_reused_legacy_slot_with_blocking_occurrence(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state(tmp_path)
    first = _oversized_payload()
    first_receipt = _persist_critique(plan_dir, state, first)
    first_receipt["findings"][0]["flag_id"] = "worker-slot-0"
    first_receipt["flag_ids"] = ["worker-slot-0"]
    first_receipt.pop("receipt_digest", None)
    first_receipt["receipt_digest"] = critique_custody._digest(first_receipt)
    atomic_write_json(plan_dir / "critique_custody_v1.json", first_receipt)
    first_payload = critique_custody.read_json(plan_dir / "critique_v1.json")
    first_payload["flags"][0]["id"] = "worker-slot-0"
    first_payload["flags"][0].pop("producer_flag_id", None)
    atomic_write_json(plan_dir / "critique_v1.json", first_payload)
    first_receipt["critique_sha256"] = critique_custody.sha256_file(
        plan_dir / "critique_v1.json"
    )
    first_receipt["critique_payload_digest"] = critique_custody._digest(first_payload)
    first_receipt.pop("receipt_digest", None)
    first_receipt["receipt_digest"] = critique_custody._digest(first_receipt)
    atomic_write_json(plan_dir / "critique_custody_v1.json", first_receipt)

    state["iteration"] = 2
    state["plan_versions"].append({"version": 2, "file": "plan_v2.md"})
    second = _oversized_payload()
    second["flags"][0]["concern"] = "A different blocking concern."
    second["flags"][0]["evidence"] = second["checks"][0]["findings"][0]["detail"]
    second_receipt = _persist_critique(plan_dir, state, second)
    second_receipt["findings"][0]["flag_id"] = "worker-slot-0"
    second_receipt["flag_ids"] = ["worker-slot-0"]
    second_payload = critique_custody.read_json(plan_dir / "critique_v2.json")
    second_payload["flags"][0]["id"] = "worker-slot-0"
    second_payload["flags"][0].pop("producer_flag_id", None)
    atomic_write_json(plan_dir / "critique_v2.json", second_payload)
    second_receipt["critique_sha256"] = critique_custody.sha256_file(
        plan_dir / "critique_v2.json"
    )
    second_receipt["critique_payload_digest"] = critique_custody._digest(second_payload)
    second_receipt.pop("receipt_digest", None)
    second_receipt["receipt_digest"] = critique_custody._digest(second_receipt)
    atomic_write_json(plan_dir / "critique_custody_v2.json", second_receipt)

    with pytest.raises(CritiqueCustodyError, match="blocking occurrence"):
        write_critique_clearance(plan_dir, state)


def test_clearance_binds_exact_final_graph_and_execute_rejects_missing_or_mutated_custody(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state(tmp_path)
    payload = _oversized_payload()
    _persist_critique(plan_dir, state, payload)
    canonical_id = payload["flags"][0]["id"]
    atomic_write_text(plan_dir / "plan_v2.md", "# Plan v2\n\nSplit Step 2 into bounded tasks.\n")
    state["iteration"] = 2
    state["plan_versions"].append({"version": 2, "file": "plan_v2.md"})
    update_flags_after_revise(
        plan_dir,
        [
            {
                "id": canonical_id,
                "resolution": "addressed",
                "reason": "Split into bounded tasks.",
                "where": "Step 2",
            }
        ],
        plan_file="plan_v2.md",
        summary="Split the task.",
    )
    update_flags_after_gate(
        plan_dir,
        [{"flag_id": canonical_id, "action": "verify_fixed", "evidence": "plan_v2.md Step 2", "rationale": ""}],
    )
    clearance = write_critique_clearance(plan_dir, state)
    graph = _admitted_graph()
    graph["critique_resolution_coverage"] = [
        {
            "finding_id": clearance["finding_ids"][0],
            "task_ids": ["T1"],
            "resolution_evidence": "T1 implements the bounded split from plan_v2.md Step 2.",
        }
    ]

    with pytest.raises(CritiqueCustodyError) as missing:
        assert_finalize_custody(plan_dir, graph)
    assert missing.value.code == "finalize_critique_custody_missing"

    bind_finalize_custody(plan_dir, graph, clearance)
    assert_finalize_custody(plan_dir, graph)
    graph["tasks"][0]["objective"] = "Regenerate a different oversized objective after clearance."
    with pytest.raises(CritiqueCustodyError, match="graph hash differs"):
        assert_finalize_custody(plan_dir, graph)


def test_finalizer_partial_or_unknown_finding_mapping_fails_closed() -> None:
    graph = _admitted_graph()
    graph["critique_resolution_coverage"] = [
        {"finding_id": "CF-ONE", "task_ids": ["T1"], "resolution_evidence": "Mapped."}
    ]
    clearance = {"finding_ids": ["CF-ONE", "CF-TWO"]}
    with pytest.raises(CritiqueCustodyError) as partial:
        validate_finalize_resolution_coverage(graph, clearance)
    assert partial.value.code == "finalize_critique_coverage_invalid"

    graph["critique_resolution_coverage"].append(
        {"finding_id": "CF-TWO", "task_ids": ["T404"], "resolution_evidence": "Missing task."}
    )
    with pytest.raises(CritiqueCustodyError, match="unknown task_ids"):
        validate_finalize_resolution_coverage(graph, clearance)


def test_equivalent_35_task_linear_graph_is_deterministically_rejected() -> None:
    tasks: list[dict[str, Any]] = []
    for index in range(1, 36):
        task_id = f"T{index}"
        dependency = f"T{index - 1}" if index > 1 else None
        tasks.append(
            {
                "id": task_id,
                "objective": f"Implement bounded objective {index}.",
                "description": f"Implement slice {index}.",
                "kind": "code",
                "complexity": 4,
                "estimated_minutes": 5,
                "depends_on": [dependency] if dependency else [],
                "dependency_reasons": (
                    {
                        dependency: {
                            "kind": "consumes_output",
                            "reason": "Consumes prior contract.",
                            "required_output": dependency,
                        }
                    }
                    if dependency
                    else {}
                ),
                "routing_group": "",
                "write_set": {"paths": [f"src/task_{index}.py"], "complete": True},
                "narrow_tests": {"selectors": [], "max_seconds": 0, "max_runs": 0},
                "checkpoint": {"required": False, "max_interval_seconds": 300, "records": []},
            }
        )
    report = compile_task_feasibility(
        {"task_contract_version": 2, "validation_jobs": [], "tasks": tasks},
        {"phase_timeout_seconds": 3600},
    )
    assert report["admitted"] is False
    assert report["task_count"] == 35
    assert report["seriality"] == 1.0
    assert "serial_graph_unjustified" in {item["code"] for item in report["diagnostics"]}
