from __future__ import annotations

import json
import os
import runpy
import subprocess
from pathlib import Path

from arnold_pipelines.megaplan.cloud import repair_requests
from arnold_pipelines.megaplan.cloud.engine_runtime_repair import ENGINE_RUNTIME_REPAIR_SCHEMA
from arnold_pipelines.megaplan.cloud.six_hour_auditor import enqueue_audit_repair_request
from arnold_pipelines.megaplan.managed_agent import (
    MANAGED_AGENT_CUSTODIAN,
    MANAGED_AGENT_SCHEMA,
    stable_managed_run_id,
)
from tests.cloud import test_repair_trigger_wrapper as tw
from tests.cloud.repair_identity_fixtures import repair_identity


def _charge(occurrence: str) -> dict[str, object]:
    return {
        "schema_version": ENGINE_RUNTIME_REPAIR_SCHEMA,
        "admission_id": "charge:managed-test",
        "effect_class": "engine_runtime",
        "repair_scope": "source_repair",
        "occurrence_fingerprint": occurrence,
        "candidate": {
            "revision": "0123456789abcdef0123456789abcdef01234567",
            "runtime_sha256": "a" * 64,
            "verification_digest": "b" * 64,
            "provenance_digest": "c" * 64,
            "effect_barrier_digest": "d" * 64,
        },
        "authority": {
            "decision": "approved",
            "model": "gpt-5.6-sol",
            "profile": "horizon-a",
        },
        "run_authority_receipt": "run-authority:managed-test",
        "custody_receipt": "custody:managed-test",
        "wbc_receipt": "wbc:managed-test",
        "fence_token": "fence:managed-test",
        "one_effect": True,
    }


def test_explicit_horizon_a_charge_reaches_managed_worker(monkeypatch, tmp_path):
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    spec = tw._write_marker(marker_dir, workspace)
    tw._write_chain_state_for_spec(workspace, spec)
    identity = repair_identity(
        session="demo", plan="m3", failure_kind="L3_TRUE_STALL",
        phase="progress_auditor", task="managed-test",
    )
    occurrence = repair_requests.repair_identity_key(identity)
    charge = _charge(occurrence)
    charge["engine_runtime_root"] = str(tw.REPO_ROOT)
    queued = enqueue_audit_repair_request(
        {
            "plan": "m3",
            "session": "demo",
            "workspace": str(workspace),
            "current_state": "blocked",
            "repair_identity": identity,
            "operator_charge": charge,
            "session_header": {"kind": "chain"},
            "deterministic_superfixer_evidence": {
                "actionable": True,
                "accepted_unclaimed_request_ids": ["legacy-request"],
                "retry_budget": {"max_attempts": 3, "remaining_attempts": 2, "claim_max_retries": 3},
            },
            "l3_escalation_gate": {
                "eligible": True,
                "decision": "true_stall",
                "escalation_id": "l3-escalation-managed-test",
                "evidence_digest": "a" * 64,
                "route": {"promotion_reason": "exhausted_l1_l2_custody"},
            },
        },
        queue_root=tw._queue_root(workspace),
    )
    assert queued and queued["status"] == "queued"
    # Exercise the production _dispatch path in-process while stubbing only
    # the external child constructor and manifest validator.  The fake writes
    # the exact managed manifest fields the real custody validator requires;
    # no direct repair/state mutation is mocked.
    ns = runpy.run_path(str(tw.TRIGGER), run_name="arnold_repair_trigger_test")
    dispatch_globals = ns["_dispatch"].__globals__
    monkeypatch.setenv("ARNOLD_AUTONOMY", "1")
    monkeypatch.setenv("ARNOLD_AUDIT_AUTOFIX_ENABLED", "1")
    # runpy returns the script globals separately from function.__globals__ in
    # this wrapper; patch the actual function namespace so _dispatch sees the
    # test seams (the production path remains unmocked).
    dispatch_globals["validate_automatic_managed_manifest"] = lambda *_a, **_k: None
    dispatch_globals["_session_is_live"] = lambda _session: False
    dispatch_globals["_pid_is_live"] = lambda _pid: False

    class FakeProc:
        pid = 424242

        def poll(self):
            return None

    real_popen = subprocess.Popen

    def fake_popen(argv, *args, **kwargs):
        if "--run-kind" not in argv:
            return real_popen(argv, *args, **kwargs)
        env = kwargs["env"]
        run_kind = argv[argv.index("--run-kind") + 1]
        identity_key = argv[argv.index("--identity-key") + 1]
        project_dir = Path(argv[argv.index("--project-dir") + 1])
        managed_run_id = stable_managed_run_id(run_kind, identity_key)
        manifest_path = (
            project_dir / ".megaplan" / "plans" / "resident-subagents"
            / managed_run_id / "manifest.json"
        )
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": MANAGED_AGENT_SCHEMA,
                    "custodian": MANAGED_AGENT_CUSTODIAN,
                    "run_id": managed_run_id,
                    "incident_attempt_event_id": "attempt:managed-test",
                    "repair_claim": {
                        "request_id": env["CLOUD_WATCHDOG_REPAIR_REQUEST_ID"],
                        "blocker_id": env["CLOUD_WATCHDOG_REPAIR_BLOCKER_ID"],
                    },
                }
            ),
            encoding="utf-8",
        )
        return FakeProc()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    result = ns["_scan_under_lock"](
        marker_dir=marker_dir,
        queue_dir=tw._queue_root(workspace),
        repair_data_dir=None,
        repair_bin=tmp_path / "repair-loop",
        meta_repair_bin=tmp_path / "meta-repair-loop",
        enabled=True,
        authorized=True,
    )
    assert result == 0
    mp = workspace / ".megaplan" / "plans" / "resident-subagents"
    decisions = tw._decisions(marker_dir)
    assert any(item.get("decision") == "dispatched" for item in decisions)
    attempts = repair_requests.iter_repair_attempts(tw._queue_root(workspace))
    assert attempts and attempts[0]["managed_run_id"].startswith("managed-")
