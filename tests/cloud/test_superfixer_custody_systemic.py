from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import repair_contract
from arnold_pipelines.megaplan.cloud.meta_repair_policy import (
    check_meta_repair_recursion,
    resolve_authoritative_blocker_id,
)
from arnold_pipelines.megaplan.cloud.progress_auditor_escalation import (
    _l2_failure_fingerprint,
)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def test_repair_data_externalizes_repeated_context_and_deduplicates(tmp_path: Path) -> None:
    repeated = {"failure": "x" * 200_000, "signals": list(range(100))}
    payload = {
        "session": "custody",
        "outcome": "deterministic_failure",
        "attempts": [
            {"attempt_id": str(index), "failure_context": repeated}
            for index in range(20)
        ],
    }
    path = tmp_path / "custody.repair-data.json"
    saved = repair_contract.save_repair_data(path, payload, root=tmp_path)

    assert path.stat().st_size < repair_contract.MAX_REPAIR_DATA_BYTES
    refs = [item["failure_context"] for item in saved["attempts"]]
    assert {item["sha256"] for item in refs} == {refs[0]["sha256"]}
    assert saved["evidence_compaction"]["externalized_field_count"] == 20
    assert saved["evidence_compaction"]["unique_evidence_count"] == 1
    assert repair_contract.load_repair_evidence_reference(refs[0]) == repeated


def test_repair_data_expansion_and_evidence_tampering_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "custody.repair-data.json"
    with pytest.raises(ValueError, match="above 4 MiB"):
        repair_contract.save_repair_data(
            path,
            {"session": "custody", "uncompactable": "z" * (5 * 1024 * 1024)},
            root=tmp_path,
        )

    saved = repair_contract.save_repair_data(
        path,
        {
            "session": "custody",
            "attempts": [{"failure_context": {"blob": "a" * 100_000}}],
        },
        root=tmp_path,
    )
    ref = saved["attempts"][0]["failure_context"]
    Path(ref["path"]).write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="content disagrees"):
        repair_contract.load_repair_evidence_reference(ref)


def test_blocker_authority_corrects_dispatch_drift_and_scopes_recursion(tmp_path: Path) -> None:
    repair_dir = tmp_path / "repair-data"
    goal = tmp_path / "goal.json"
    authoritative = "blocker:v1:authoritative"
    _write(goal, {"target": {"blocker_id": authoritative}})
    _write(
        repair_dir / "custody.repair-data.json",
        {
            "blocker_id": authoritative,
            "repair_goal": {"goal_path": str(goal)},
        },
    )
    _write(
        repair_dir / "meta" / "old.json",
        {"session": "custody", "blocker_id": "blocker:v1:old", "outcome": "FIXED"},
    )
    blocker, drift = resolve_authoritative_blocker_id(
        "custody", repair_data_dir=repair_dir, supplied_blocker_id="blocker:v1:stale"
    )
    assert (blocker, drift) == (authoritative, True)
    assert not check_meta_repair_recursion(
        "custody", repair_data_dir=repair_dir, blocker_id=blocker
    ).recursing


def test_l3_treats_recursion_and_investigator_access_failure_as_backstop_failure() -> None:
    base = {
        "repair_data_summary": {
            "outcome": "repair_exhausted",
            "meta_investigation_summary": {
                "failure_code": "investigator_read_sandbox_unavailable"
            },
        },
        "meta_repair_summary": {"should_dispatch": True},
    }
    assert _l2_failure_fingerprint(base)["investigator_access_failure"] is True
    retained_log_failure = {
        "repair_data_summary": {"outcome": "repair_exhausted"},
        "meta_repair_summary": {
            "should_dispatch": True,
            "meta_run_refs": [
                {"failure_code": "investigator_read_sandbox_unavailable"}
            ],
        },
    }
    retained = _l2_failure_fingerprint(retained_log_failure)
    assert retained["investigator_access_failure"] is True
    assert retained["failure_codes"] == ["investigator_read_sandbox_unavailable"]
    recurrence = {
        **base,
        "repair_data_summary": {"outcome": "repair_exhausted"},
        "meta_repair_summary": {
            "should_dispatch": True,
            "recursion_guard_blocked": True,
        },
    }
    verdict = _l2_failure_fingerprint(recurrence)
    assert verdict["failed"] is True
    assert verdict["recursion_guard_blocked"] is True


def test_meta_wrapper_uses_bounded_broker_without_tool_authority() -> None:
    wrapper = Path(
        "arnold_pipelines/megaplan/cloud/wrappers/arnold-meta-repair-loop"
    ).read_text(encoding="utf-8")
    assert "observe-meta" in wrapper
    assert 'investigator_mode="brokered_no_tools"' in wrapper
    assert '--toolsets ""' in wrapper
    assert "ARNOLD_NESTED_MANAGED_AGENT_WORKER=1 exec" in wrapper
    assert "bwrap --ro-bind / / true" in wrapper
    assert 'META_INVESTIGATION_ACTION" == "replan"' in wrapper
    assert "meta_repair_replan_handoff" in wrapper
    assert "ordinary_l1_repair" in wrapper
    assert "reconcile_l2_replan" in wrapper
    assert "already reconciled; refusing duplicate ordinary retrigger" in wrapper
    assert '"replan_epoch": active_replan_epoch' in Path(
        "arnold_pipelines/megaplan/cloud/repair_goal.py"
    ).read_text(encoding="utf-8")
    assert 'export ARNOLD_REPAIR_L2_HANDOFF_PATH="$META_INVESTIGATION_OBSERVATION_PATH"' in wrapper
    assert 'export ARNOLD_REPAIR_L2_CONTEXT_DIGEST="$META_INVESTIGATION_CONTEXT_DIGEST"' in wrapper
    repair_wrapper = Path(
        "arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop"
    ).read_text(encoding="utf-8")
    assert 'for handoff_key in ("meta_investigation", "meta_replan_handoff")' in repair_wrapper
    assert "payload[handoff_key] = dict(handoff_value)" in repair_wrapper
    assert '--l2-handoff-path "$ARNOLD_REPAIR_L2_HANDOFF_PATH"' in repair_wrapper
    assert '--l2-context-digest "${ARNOLD_REPAIR_L2_CONTEXT_DIGEST:-}"' in repair_wrapper
    assert '"latest_failure", "workspace_head"' in repair_wrapper
    assert "successor blocker should receive its bounded repair action" in repair_wrapper
    assert "load_json(pathlib.Path(receipt_path), default={})" not in repair_wrapper
    assert 'pathlib.Path(receipt_path).read_text(encoding="utf-8")' in repair_wrapper
    assert "<<'PY' || return 1" in repair_wrapper
    assert "load_json(pathlib.Path(receipt_path), default={})" not in wrapper
    assert "load_json(pathlib.Path(observation_path), default={})" not in wrapper
    assert 'pathlib.Path(observation_path).read_text(encoding="utf-8")' in wrapper
    assert "<<'PY' >>\"$RUN_LOG\" 2>&1 || return 1" in wrapper
    assert "STATE MISMATCH DETECTED — NOT CLEARED" in repair_wrapper
    assert 'mismatch_cleared = state_mismatch.get("cleared") is True' in repair_wrapper
    assert "Action taken: cleared chain last_state to match plan current_state" not in repair_wrapper
    launcher = Path(
        "arnold_pipelines/megaplan/skills/subagent-launcher/launch_hermes_agent.py"
    ).read_text(encoding="utf-8")
    assert "enabled_toolsets=toolset_list," in launcher
    assert "enabled_toolsets=toolset_list or None" not in launcher


def test_meta_dispatch_retries_failed_generation_without_false_receipt() -> None:
    watchdog = Path(
        "arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog"
    ).read_text(encoding="utf-8")

    assert (
        'managed_identity="meta-repair:${session}:${trigger_label}:'
        '${request_id:-none}:$(date +%s%N)"'
    ) in watchdog
    assert 'terminal_failed = manifest.get("status") == "failed"' in watchdog
    assert "and not terminal_failed" in watchdog
    assert "if terminal_failed:" in watchdog
