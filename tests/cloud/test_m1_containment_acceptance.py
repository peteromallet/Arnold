"""Conservative M1 containment acceptance tests against production adapters.

The authoritative July 10 audit is unavailable.  Until it is recovered, this
is the mechanical, provisional mapping that must be reconciled before M1 is
declared complete:

* ranks 1-3 -> master-plus-path authorization for L1/L2/L3 mutation;
* rank 4 -> one explicit central repair queue and no inferred custody;
* rank 5 -> production current-target evidence stays typed and never green;
* rank 6 -> liveness/process success remains provisional recovery evidence;
* rank 7 -> test incident stores cannot alias production custody;
* addition 1 -> dispatch identity and receipt initialization precede launch;
* addition 2 -> automatic dispatch proves the exact resolved runtime model;
* addition 3 -> the six-hour auditor is read-only and only queues repairs;
* addition 4 -> every attempted launch permanently falsifies report-only;
* addition 10 -> missing/stale/partial/contradictory evidence fails closed.

These tests call shipped Python contracts and execute shipped shell-wrapper
functions.  Subprocess and filesystem effects are controlled at their real
boundaries; no test-only implementation stands in for a production contract.
"""

from __future__ import annotations

import json
import os
import shlex
import stat
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from arnold_pipelines.megaplan.cloud import feature_flags, repair_contract, repair_requests
from arnold_pipelines.megaplan.cloud.current_target import resolve_current_target
from arnold_pipelines.megaplan.cloud.incident_bridge import IncidentStoreWriter
from arnold_pipelines.megaplan.cloud.six_hour_auditor import (
    enqueue_audit_repair_request,
    validate_audit_model_inputs,
)
from arnold_pipelines.megaplan.receipts import writer as receipt_writer


REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER_DIR = REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers"
AUDIT_WRAPPER = WRAPPER_DIR / "arnold-progress-auditor"

PROVISIONAL_AUDIT_MAPPING = {
    "rank-1": "l1_master_plus_path_gate",
    "rank-2": "l2_master_plus_path_gate",
    "rank-3": "l3_master_plus_path_gate",
    "rank-4": "central_queue_custody",
    "rank-5": "typed_current_target_evidence",
    "rank-6": "provisional_recovery",
    "rank-7": "incident_store_isolation",
    "addition-1": "durable_dispatch_identity",
    "addition-2": "resolved_runtime_model_receipt",
    "addition-3": "auditor_read_only_routing",
    "addition-4": "report_only_launch_truth",
    "addition-10": "typed_unknown_fail_closed",
}


def _audit_wrapper_text() -> str:
    return AUDIT_WRAPPER.read_text(encoding="utf-8")


def _extract_auditor_function(name: str) -> str:
    text = _audit_wrapper_text()
    start = text.index(f"{name}() {{")
    end = text.index("\n}\n", start) + 3
    return text[start:end]


def _extract_report_assembler() -> str:
    text = _audit_wrapper_text()
    marker = (
        'python3 - "$GATHER_DIR/findings.json" "$JSON_OUT" "$MD_OUT" '
        '"$REPORT_LOG" "$TS" "$AUDIT_MUTATION_AUTHORIZED_FLAG" '
        '"$AUDIT_LAUNCH_ATTEMPTED" "$RECOVERY_EVIDENCE" '
        '"$AUDIT_CODEX_MODEL" <<\'PY\''
    )
    start = text.index("\n", text.index(marker)) + 1
    return text[start : text.index("\nPY\n", start)]


def _run_auditor_dispatch(tmp_path: Path) -> dict[str, object]:
    workspace = tmp_path / "workspace"
    gather_dir = tmp_path / "gather"
    workspace.mkdir()
    gather_dir.mkdir()
    finding = gather_dir / "finding.json"
    finding.write_text(
        json.dumps(
            {
                "workspace": str(workspace),
                "plan": "m1-acceptance",
                "session": "m1-session",
                "reasons": ["watchdog_report_stale"],
                "session_header": {"kind": "chain"},
            }
        ),
        encoding="utf-8",
    )
    codex = tmp_path / "codex"
    argv_path = tmp_path / "codex.argv"
    codex.write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' \"$@\" > {shlex.quote(str(argv_path))}\n"
        "printf 'PASSIVE\\nno-op\\n'\n",
        encoding="utf-8",
    )
    codex.chmod(codex.stat().st_mode | stat.S_IXUSR)

    functions = (
        "redact_inline_text",
        "redact_file_in_place",
        "log",
        "audit_flag_enabled",
        "autofix_allowed_targets_markdown",
        "autofix_policy_markdown",
        "audit_dispatch_receipt_root",
        "initialize_audit_dispatch_receipt",
        "record_audit_dispatch_started",
        "finalize_audit_dispatch_receipt",
        "dispatch_one",
    )
    script = "\n\n".join(
        [*(_extract_auditor_function(name) for name in functions),
         f"WRAPPER_REPO_ROOT={shlex.quote(str(REPO_ROOT))}",
         f"ARNOLD_SRC={shlex.quote(str(REPO_ROOT))}",
         f"GATHER_DIR={shlex.quote(str(gather_dir))}",
         f"REPORT_DIR={shlex.quote(str(tmp_path / 'reports'))}",
         "TS=20260713T210000Z",
         "DEEPSEEK_MODEL=deepseek:deepseek-v4-pro",
         "AUDIT_CODEX_MODEL=gpt-5.6-sol",
         "SUBAGENT_PROFILE=partnered-5",
         "CODEX_TIMEOUT=30",
         'AUDIT_AUTOFIX_ENABLED_FLAG="$(audit_flag_enabled audit_autofix_enabled)"',
         'AUDIT_MUTATION_AUTHORIZED_FLAG="$(audit_flag_enabled audit_autofix_mutation_authorized)"',
         'AUDIT_AUTOFIX_COMMIT_ENABLED_FLAG="$(audit_flag_enabled audit_autofix_commit_enabled)"',
         f"dispatch_one {shlex.quote(str(finding))}"]
    )
    env = dict(os.environ)
    env.update(
        {
            "PATH": f"{tmp_path}:{env.get('PATH', '')}",
            "PYTHONPATH": f"{REPO_ROOT}:{env.get('PYTHONPATH', '')}",
            "ARNOLD_AUTONOMY": "1",
            "ARNOLD_AUDIT_AUTOFIX_ENABLED": "1",
        }
    )
    result = subprocess.run(
        ["bash", "-lc", script], capture_output=True, text=True, env=env, check=False
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(finding.read_text(encoding="utf-8"))
    payload["codex_argv"] = argv_path.read_text(encoding="utf-8").splitlines()
    return payload


def _run_report_assembler(tmp_path: Path, findings: dict[str, object]) -> dict[str, object]:
    program = tmp_path / "report_assembler.py"
    program.write_text(_extract_report_assembler(), encoding="utf-8")
    findings_path = tmp_path / "findings.json"
    json_out = tmp_path / "audit.json"
    recovery_path = tmp_path / "recovery.json"
    findings_path.write_text(json.dumps(findings), encoding="utf-8")
    recovery_path.write_text(
        json.dumps(
            {
                "enabled": False,
                "watchdog_exit_code": None,
                "sessions_discovered": 0,
                "should_run_count": 0,
                "decisions": [],
            }
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            str(program),
            str(findings_path),
            str(json_out),
            str(tmp_path / "audit.md"),
            str(tmp_path / "audit.log"),
            "20260710T200000Z",
            "1",
            "1",
            str(recovery_path),
            "gpt-5.6-sol",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(json_out.read_text(encoding="utf-8"))


def test_provisional_mapping_is_explicit_and_retains_reconciliation_obligation() -> None:
    assert set(PROVISIONAL_AUDIT_MAPPING) == {
        *(f"rank-{number}" for number in range(1, 8)),
        "addition-1",
        "addition-2",
        "addition-3",
        "addition-4",
        "addition-10",
    }
    assert "must be reconciled before M1 is declared complete" in " ".join(__doc__.split())


def test_master_plus_path_gate_and_real_l1_wrapper_fail_closed(tmp_path: Path) -> None:
    path_env = {
        feature_flags.MUTATION_PATH_L1: "ARNOLD_REPAIR_TRIGGER_ENABLED",
        feature_flags.MUTATION_PATH_L2: "ARNOLD_META_REPAIR_ENABLED",
        feature_flags.MUTATION_PATH_L3: "ARNOLD_AUDIT_AUTOFIX_ENABLED",
    }
    for path, env_name in path_env.items():
        for master in ("0", "1"):
            for path_gate in ("0", "1"):
                with mock.patch.dict(
                    os.environ,
                    {"ARNOLD_AUTONOMY": master, env_name: path_gate},
                    clear=True,
                ):
                    assert feature_flags.mutation_authorized(path) is (
                        master == path_gate == "1"
                    )

    effects = tmp_path / "effects"
    command = tmp_path / "effect-spy"
    command.write_text(
        "#!/usr/bin/env bash\nmkdir -p \"$1\"\n"
        "for effect in subprocess state source commit push; do "
        "printf mutated > \"$1/$effect\"; done\n",
        encoding="utf-8",
    )
    command.chmod(command.stat().st_mode | stat.S_IXUSR)
    env = dict(os.environ)
    env.update(
        {
            "PYTHONPATH": f"{REPO_ROOT}:{env.get('PYTHONPATH', '')}",
            "ARNOLD_AUTONOMY": "0",
            "ARNOLD_REPAIR_TRIGGER_ENABLED": "1",
            "ARNOLD_SUPERVISE_LOG": str(tmp_path / "supervise.log"),
        }
    )
    result = subprocess.run(
        ["bash", str(WRAPPER_DIR / "arnold-supervise"), "m1", str(command), str(effects)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert not effects.exists()
    assert "observed: L1 supervisor mutation blocked" in result.stdout


def test_all_repair_producers_share_explicit_central_queue(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    queue_root = workspace / ".megaplan" / "repair-queue"
    generic = repair_requests.enqueue_repair_request(
        queue_root=queue_root,
        session="generic",
        source="m1_acceptance",
        workspace=workspace,
        problem_signature={"failure_kind": "execute_failed", "blocked_task_id": "T1"},
    )
    human = repair_requests.enqueue_human_gate_repair_request(
        queue_root=queue_root,
        marker_dir=workspace / ".megaplan" / "plans" / "m1",
        session="human",
        workspace=workspace,
        run_kind="plan",
        plan_name="m1",
        pipeline_name="megaplan",
        artifact_stage="execute",
        step_name="approval",
        prompt="approval required",
    )
    assert generic["request"]["queue_dir"] == human["request"]["queue_dir"] == str(queue_root)
    assert {item["session"] for item in repair_requests.iter_repair_requests(queue_root)} == {
        "generic",
        "human",
    }
    with pytest.raises(ValueError):
        repair_requests.validate_queue_root(workspace / ".megaplan" / "plans" / "m1")


@pytest.mark.parametrize(
    ("session", "prepare", "unknown_type"),
    [
        ("missing", lambda _markers, _workspace: None, "missing"),
        (
            "partial",
            lambda markers, _workspace: (markers / "partial.json").write_text(
                '{"workspace":', encoding="utf-8"
            ),
            "partial",
        ),
    ],
)
def test_production_current_target_adapter_fails_closed_with_typed_unknown(
    tmp_path: Path, session: str, prepare: object, unknown_type: str
) -> None:
    markers = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    markers.mkdir()
    workspace.mkdir()
    prepare(markers, workspace)  # type: ignore[operator]
    record = resolve_current_target(
        session,
        marker_dir=markers,
        repair_data_dir=markers / "repair-data",
        workspace_hint=workspace,
    )
    assert record["evidence_state"] == {
        "status": "unknown",
        "unknown_type": unknown_type,
        "issue_kinds": record["evidence_state"]["issue_kinds"],
        "mutation_eligible": False,
        "authorizes_mutation": False,
        "green": False,
    }


def test_liveness_and_process_success_remain_provisional() -> None:
    for observation in (
        {"kind": "pid", "pid_alive": True},
        {"kind": "heartbeat", "heartbeat_active": True},
        {"kind": "partial_liveness", "is_live": True},
        {"kind": "subprocess_success", "returncode": 0},
    ):
        result = repair_contract.classify_recovery_verification(
            original_blocker={"blocker_id": "blocker-42"},
            observation=observation,
            repair_completed_at="2026-07-10T19:00:00+00:00",
        )
        assert result["status"] == repair_contract.RECOVERY_PROVISIONAL
        assert result["authorizes_verified_recovered"] is False


def test_incident_test_namespace_cannot_alias_production_store(tmp_path: Path) -> None:
    production_root = tmp_path / "production"
    production_ledger = production_root / ".megaplan" / "incident-ledger"
    production_ledger.mkdir(parents=True)
    with pytest.raises(ValueError, match="production ledger, projection, or journal"):
        IncidentStoreWriter.isolated_test(
            production_root, production_root=production_root, identity="test:m1"
        )
    with pytest.raises(ValueError, match="test or fixture identity"):
        IncidentStoreWriter.production(production_root, identity="test:m1")
    isolated = IncidentStoreWriter.isolated_test(
        tmp_path / "isolated", production_root=production_root, identity="test:m1"
    )
    assert isolated.events_path != production_ledger / "events.jsonl"


def test_dispatch_identity_and_initialized_snapshot_are_durable_before_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_dir = tmp_path / "plan"
    prepared = receipt_writer.prepare_dispatch_receipt(
        action="automatic-repair", configured_model="gpt-5.6-sol", dispatch_id="m1-dispatch"
    )
    observed: list[dict[str, object]] = []

    def launch() -> object:
        observed.append(
            json.loads(
                receipt_writer.dispatch_receipt_path(plan_dir, "m1-dispatch").read_text(
                    encoding="utf-8"
                )
            )
        )
        assert (plan_dir / "dispatch_receipts" / "m1-dispatch.identity").exists()
        return object()

    started, _process = receipt_writer.initialize_and_launch_dispatch(plan_dir, prepared, launch)
    assert observed[0]["sequence"] == 1
    assert observed[0]["subprocess_started"] is False
    assert started["subprocess_started"] is True

    blocked_launch = mock.Mock()
    monkeypatch.setattr(
        receipt_writer, "atomic_write_json", mock.Mock(side_effect=OSError("snapshot unavailable"))
    )
    with pytest.raises(receipt_writer.DispatchInitializationError):
        receipt_writer.initialize_and_launch_dispatch(
            tmp_path / "blocked",
            receipt_writer.prepare_dispatch_receipt(
                action="automatic-repair",
                configured_model="gpt-5.6-sol",
                dispatch_id="blocked-dispatch",
            ),
            blocked_launch,
        )
    blocked_launch.assert_not_called()


def test_real_auditor_dispatch_proves_exact_model_and_read_only_receipt(tmp_path: Path) -> None:
    assert validate_audit_model_inputs({}) == "gpt-5.6-sol"
    with pytest.raises(ValueError):
        validate_audit_model_inputs({"CODEX_MODEL": "gpt-5.5"})

    result = _run_auditor_dispatch(tmp_path)
    assert result["codex_argv"] == [
        "exec",
        "--sandbox",
        "read-only",
        "-c",
        "model=gpt-5.6-sol",
        "-c",
        "model_reasoning_effort=high",
        "-",
    ]
    receipt_path = (
        Path(str(result["dispatch_receipt_root"]))
        / "dispatch_receipts"
        / f"{result['dispatch_id']}.json"
    )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["configured_model"] == receipt["resolved_runtime_model"] == "gpt-5.6-sol"
    assert receipt["subprocess_started"] is True
    assert receipt["mutation_facts"] == {
        "state": False,
        "source": False,
        "commit": False,
        "push": False,
    }


def test_auditor_ordinary_finding_stays_report_only_without_true_stall_gate(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    queue_root = workspace / ".megaplan" / "repair-queue"
    routed = enqueue_audit_repair_request(
        {
            "plan": "m1",
            "session": "m1-session",
            "workspace": str(workspace),
            "session_header": {"kind": "chain"},
            "incident_projection": {"state": "blocked"},
            "incident_audit": {
                "incident_id": "inc-m1",
                "problem_id": "problem-m1",
                "diagnosis": {"summary": "watchdog evidence stale"},
                "findings": [
                    {
                        "status": "error",
                        "layer": "watchdog",
                        "code": "watchdog_report_stale",
                        "recommendation": "watchdog.dispatch",
                    }
                ],
            },
        },
        queue_root=queue_root,
    )
    assert routed is None
    assert not (workspace / ".git").exists()
    assert not (workspace / ".megaplan" / "plans").exists()

    report = _run_report_assembler(
        tmp_path,
        {
            "window_hours": 6,
            "stall_summary": "one finding",
            "findings": [{"plan": "m1", "codex_launch_attempted": True}],
            "green_checks": [],
        },
    )
    summary = report["dispatch_summary"]
    assert summary["mode"] == "report_only"
    assert summary["model_dispatched"] is False
    assert report["data_quality"]["canonical_launch_disagreements"]
