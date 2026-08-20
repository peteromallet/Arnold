from __future__ import annotations

import json
from pathlib import Path

from arnold.workflow.boundary_evidence import FindingSeverity, SemanticFinding
from arnold.workflow.diagnostics import DiagnosticCode
from arnold_pipelines.megaplan.cloud.repair_contract import (
    _is_known_repairable_shape,
    build_repair_semantic_context,
    classify_repair_dispatch,
    has_repairable_semantic_finding,
)
from tests.cloud.test_watchdog_wrappers import _extract_repair_program, _run_embedded_python


def test_render_failure_summary_prefers_authoritative_live_plan_failure_shape(tmp_path: Path) -> None:
    data_path = tmp_path / "repair-data.json"
    data_path.write_text(
        json.dumps(
            {
                "initial_facts": {},
                "iterations": [
                    {
                        "attempt_id": 4,
                        "failure_classification": "authentication_or_credentials_error",
                        "plan_latest_failure": {
                            "kind": "execution_blocked",
                            "phase": "execute",
                            "current_state": "blocked",
                            "recorded_at": "2026-07-06T19:19:31Z",
                            "message": "execute reported prerequisite-blocked tasks: T4",
                        },
                        "stale_state": {
                            "classification": "LIVE FAILURE",
                            "summary": "latest_failure is recent; no successful event was found after it",
                        },
                        "raw_failure_signals": [
                            "latest_failure.kind: execution_blocked",
                            "latest_failure.message: execute reported prerequisite-blocked tasks: T4",
                            "chain log: missing credentials from stale verifier warning",
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    summary_program = _extract_repair_program(
        "render_failure_summary",
        "python3 - \"$data_path\" <<'PY'",
    )
    result = _run_embedded_python(summary_program, str(data_path))

    assert result.returncode == 0, result.stderr
    summary = result.stdout
    assert "- failure classification: blocked_state_or_recovery_error" in summary
    assert "- latest_failure: kind=execution_blocked recorded_at=2026-07-06T19:19:31Z" in summary
    assert (
        "- recommended repair action: investigate the blocked execute task; "
        "fix the task-level target code or plan state when the blocker is not an Arnold engine bug"
    ) in summary
    assert "dispatch dev-fix to fix the Arnold source root cause" not in summary


# ── S4: semantic-health projection for repair initial facts ─────────────────


def _make_error_finding(
    finding_id: str = "SH-missing-artifact",
    boundary_id: str = "test-boundary",
    description: str = "required artifact is missing",
    diagnostic_code: DiagnosticCode = DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
) -> SemanticFinding:
    return SemanticFinding(
        finding_id=finding_id,
        boundary_id=boundary_id,
        description=description,
        severity=FindingSeverity.ERROR,
        diagnostic_code=diagnostic_code,
    )


def _make_warning_finding(
    finding_id: str = "SH-stale-state",
    boundary_id: str = "test-boundary",
) -> SemanticFinding:
    return SemanticFinding(
        finding_id=finding_id,
        boundary_id=boundary_id,
        description="stale state detected",
        severity=FindingSeverity.WARNING,
    )


class TestBuildRepairSemanticContext:
    def test_includes_semantic_counts_and_has_repairable(self) -> None:
        """Initial facts include projected semantic counts and repairable flag."""
        findings = [
            _make_error_finding("SH-1", "b1", "missing artifact"),
            _make_error_finding("SH-2", "b2", "missing receipt"),
            _make_warning_finding("SH-3", "b3"),
        ]
        context = build_repair_semantic_context(
            findings=findings, session_id="test-session"
        )

        assert context["session_id"] == "test-session"
        assert context["has_repairable"] is True
        assert len(context["repairable_details"]) == 2
        assert context["repairable_details"][0]["finding_id"] == "SH-1"
        assert context["repairable_details"][0]["boundary_id"] == "b1"
        assert context["repairable_details"][1]["finding_id"] == "SH-2"

        # semantic_counts should be populated
        assert "fingerprint" in context["semantic_counts"]
        assert context["semantic_counts"]["total_count"] == 3

        # custody_projection should have repair domains
        assert "repair_domains" in context["custody_projection"]
        assert "boundary_evidence_repairable" in context["custody_projection"]["repair_domains"]

    def test_no_findings_returns_empty_context(self) -> None:
        """Empty findings produce a valid but empty context."""
        context = build_repair_semantic_context(findings=[], session_id="s")
        assert context["has_repairable"] is False
        assert context["repairable_details"] == []
        assert context["semantic_counts"] == {}

    def test_no_plan_dir_or_findings_returns_empty(self) -> None:
        """Neither plan_dir nor findings produces default empty context."""
        context = build_repair_semantic_context(session_id="s")
        assert context["has_repairable"] is False
        assert context["semantic_counts"] == {}

    def test_cloud_meta_passthrough(self) -> None:
        """Cloud metadata is passed through to the context."""
        context = build_repair_semantic_context(
            findings=[],
            session_id="s",
            cloud_meta={"target": "demo-target", "provider": "openai"},
        )
        assert context["cloud_target"] == "demo-target"
        assert context["cloud_provider"] == "openai"

    def test_warning_only_findings_not_repairable(self) -> None:
        """Findings with WARNING severity are not classified as repairable."""
        findings = [
            _make_warning_finding("SH-w1", "b1"),
            _make_warning_finding("SH-w2", "b2"),
        ]
        context = build_repair_semantic_context(findings=findings, session_id="s")
        assert context["has_repairable"] is False
        assert context["repairable_details"] == []


class TestHasRepairableSemanticFinding:
    def test_error_findings_with_repairable_code(self) -> None:
        """Error findings with repairable diagnostic codes are detected."""
        findings = [
            _make_error_finding(
                "SH-1", "b1", "missing evidence",
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
            ),
        ]
        result = has_repairable_semantic_finding(findings)
        assert result["has_repairable"] is True
        assert result["count"] == 1
        assert "SH-1" in result["finding_ids"]

    def test_error_findings_with_non_repairable_code(self) -> None:
        """Error findings with non-repairable codes are still counted as repairable
        because severity=ERROR always triggers repairable classification."""
        findings = [
            _make_error_finding(
                "SH-1", "b1", "unknown error",
                diagnostic_code=DiagnosticCode.INVALID_IMPORT_SOURCE,
            ),
        ]
        result = has_repairable_semantic_finding(findings)
        # ERROR severity always counts as repairable
        assert result["has_repairable"] is True
        assert result["count"] == 1

    def test_no_findings(self) -> None:
        """Empty findings list returns no repairable."""
        result = has_repairable_semantic_finding([])
        assert result["has_repairable"] is False
        assert result["count"] == 0

    def test_info_findings_not_repairable(self) -> None:
        """INFO severity findings are not repairable."""
        findings = [
            SemanticFinding(
                finding_id="SH-info",
                boundary_id="b1",
                description="informational note",
                severity=FindingSeverity.INFO,
            ),
        ]
        result = has_repairable_semantic_finding(findings)
        assert result["has_repairable"] is False


class TestIsKnownRepairableShapeWithSemanticFindings:
    def test_semantic_findings_fallback_when_no_failure_kind(self) -> None:
        """When failure_kind is empty and state is blocked, semantic findings
        with repairable issues enable shape recognition."""
        target = {
            "plan_state": {"present": True, "fingerprint": "sha256:proof"},
            "current_refs": {"current_plan_name": "test-plan"},
        }
        findings = [_make_error_finding("SH-1", "b1", "missing artifact")]
        result = _is_known_repairable_shape(
            current_state="blocked",
            retry_strategy="manual_review",
            failure_kind="",
            current_target=target,
            semantic_findings=findings,
        )
        assert result is True

    def test_semantic_findings_no_fallback_when_failure_kind_present(self) -> None:
        """When failure_kind is provided, semantic findings fallback is not
        needed — the primary path handles it."""
        target = {
            "plan_state": {"present": True, "fingerprint": "sha256:proof"},
            "current_refs": {"current_plan_name": "test-plan"},
        }
        findings = [_make_error_finding("SH-1", "b1", "missing artifact")]
        result = _is_known_repairable_shape(
            current_state="blocked",
            retry_strategy="manual_review",
            failure_kind="blocked_recovery_not_resolved",
            current_target=target,
            semantic_findings=findings,
        )
        # primary path matches before fallback is checked
        assert result is True

    def test_empty_findings_no_fallback(self) -> None:
        """Empty semantic findings do not trigger fallback."""
        target = {
            "plan_state": {"present": True, "fingerprint": "sha256:proof"},
        }
        result = _is_known_repairable_shape(
            current_state="blocked",
            retry_strategy="manual_review",
            failure_kind="",
            current_target=target,
            semantic_findings=[],
        )
        assert result is False

    def test_warning_findings_only_no_fallback(self) -> None:
        """WARNING-only semantic findings do not trigger fallback."""
        target = {
            "plan_state": {"present": True, "fingerprint": "sha256:proof"},
        }
        findings = [_make_warning_finding("SH-w1", "b1")]
        result = _is_known_repairable_shape(
            current_state="blocked",
            retry_strategy="manual_review",
            failure_kind="",
            current_target=target,
            semantic_findings=findings,
        )
        assert result is False


class TestClassifyRepairDispatchWithSemanticFindings:
    def test_dispatch_with_no_latest_failure_but_semantic_findings(self) -> None:
        """When latest_failure is absent but semantic findings exist,
        dispatch can proceed via the legacy path."""
        from arnold_pipelines.megaplan.cloud.repair_contract import (
            DISPATCH_DECISION_L1,
        )

        plan_state = {
            "name": "test-plan",
            "current_state": "blocked",
            "resume_cursor": {"retry_strategy": "manual_review"},
        }
        current_target = {
            "plan_state": {"present": True, "fingerprint": "sha256:proof"},
            "current_refs": {"current_plan_name": "test-plan"},
            "authoritative_source": "plan_state",
        }
        findings = [_make_error_finding("SH-1", "b1", "missing artifact")]

        # Build a custody projection with an active request
        import tempfile
        from arnold_pipelines.megaplan.cloud.repair_requests import (
            enqueue_repair_request,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            megaplan_dir = Path(tmpdir) / ".megaplan"
            megaplan_dir.mkdir()
            queue_root = megaplan_dir / "repair-queue"
            queue_root.mkdir()

            enqueue_repair_request(
                queue_root=queue_root,
                session="test-session",
                source="watchdog",
                problem_signature={
                    "failure_kind": "",
                    "current_state": "blocked",
                },
                target=current_target,
            )

            from arnold_pipelines.megaplan.cloud.repair_contract import project_repair_custody

            custody = project_repair_custody(
                plan_state=plan_state,
                current_target=current_target,
                queue_root=queue_root,
            )

            decision = classify_repair_dispatch(
                plan_state=plan_state,
                current_target=current_target,
                custody_projection=custody,
                semantic_findings=findings,
            )
            # With semantic findings fallback + active request, should dispatch L1
            assert decision.decision == DISPATCH_DECISION_L1
            assert "known repairable blocker" in decision.rationale[0]


# ── S4: wrapper regression — semantic_health in repair initial_facts ────────


def test_repair_data_init_includes_semantic_health_in_initial_facts(
    tmp_path: Path,
) -> None:
    """The persist_repair_initial_facts embedded Python writes semantic_health
    from failure_context into initial_facts."""
    from tests.cloud.test_watchdog_wrappers import (
        _run_repair_data_init,
    )

    data_path = tmp_path / "repair-data.json"
    progress_path = tmp_path / "repair-progress.json"

    failure_context = {
        "resolver_output": {},
        "semantic_health": {
            "schema": "arnold.workflow.semantic_health_projection.v1",
            "session_id": "demo-session",
            "fingerprint": "sha256:abc123",
            "total_count": 3,
            "counts_by_boundary": {"b1": 2, "b2": 1},
            "counts_by_kind": {"ERROR": 2, "WARNING": 1},
            "counts_by_repair_domain": {"boundary_evidence_repairable": 2},
            "findings": [],
        },
        "semantic_context": {
            "schema": "arnold.workflow.repair_semantic_context.v1",
            "has_repairable": True,
            "custody_projection": {
                "repair_domains": ["boundary_evidence_repairable"],
                "suggested_custody_bucket": "repairable_not_repairing",
            },
        },
        "custody_projection": {
            "repair_domains": ["boundary_evidence_repairable"],
            "suggested_custody_bucket": "repairable_not_repairing",
        },
        "plan_latest_failure": {},
        "chain_state_summary": {},
        "failure_classification": "",
        "stale_state": {},
        "state_mismatch": {},
        "raw_failure_signals": [],
        "chain_log_tail": "",
        "chain_log_path": "",
        "run_log_tail": "",
        "run_log_path": "",
        "chain_recent_events": [],
        "plan_events_tail": "",
        "plan_events_path": "",
        "mechanical_log_tail": "",
        "mechanical_log_path": "",
        "plan_runtime_state": {},
        "last_gate": {},
        "user_action_context": {},
        "execute_attempt_context": {},
        "resume_authority_failure": {},
    }

    _run_repair_data_init(
        data_path,
        progress_path=progress_path,
        failure_context=failure_context,
    )

    payload = json.loads(data_path.read_text(encoding="utf-8"))
    initial_facts = payload.get("initial_facts", {})

    assert "semantic_health" in initial_facts, (
        "semantic_health must be present in initial_facts"
    )
    semantic_health = initial_facts["semantic_health"]
    assert semantic_health["schema"] == "arnold.workflow.semantic_health_projection.v1"
    assert semantic_health["total_count"] == 3
    assert semantic_health["fingerprint"] == "sha256:abc123"
    assert initial_facts["semantic_context"]["has_repairable"] is True
    assert initial_facts["custody_projection"] == {
        "repair_domains": ["boundary_evidence_repairable"],
        "suggested_custody_bucket": "repairable_not_repairing",
    }


def test_repair_data_init_semantic_health_empty_when_not_in_failure_context(
    tmp_path: Path,
) -> None:
    """When failure_context has no semantic_health, initial_facts gets {}."""
    from tests.cloud.test_watchdog_wrappers import (
        _run_repair_data_init,
    )

    data_path = tmp_path / "repair-data.json"
    progress_path = tmp_path / "repair-progress.json"

    failure_context = {
        "resolver_output": {},
        "plan_latest_failure": {},
        "chain_state_summary": {},
        "failure_classification": "",
        "stale_state": {},
        "state_mismatch": {},
        "raw_failure_signals": [],
        "chain_log_tail": "",
        "chain_log_path": "",
        "run_log_tail": "",
        "run_log_path": "",
        "chain_recent_events": [],
        "plan_events_tail": "",
        "plan_events_path": "",
        "mechanical_log_tail": "",
        "mechanical_log_path": "",
        "plan_runtime_state": {},
        "last_gate": {},
        "user_action_context": {},
        "execute_attempt_context": {},
        "resume_authority_failure": {},
    }

    _run_repair_data_init(
        data_path,
        progress_path=progress_path,
        failure_context=failure_context,
    )

    payload = json.loads(data_path.read_text(encoding="utf-8"))
    initial_facts = payload.get("initial_facts", {})

    assert "semantic_health" in initial_facts, (
        "semantic_health key must always be present in initial_facts"
    )
    assert initial_facts["semantic_health"] == {}
    assert initial_facts["semantic_context"] == {}
    assert initial_facts["custody_projection"] == {}


def test_collect_failure_context_includes_semantic_health_key(
    tmp_path: Path,
) -> None:
    """The collect_failure_context_json embedded Python output dict
    includes a 'semantic_health' key."""
    from tests.cloud.test_watchdog_wrappers import (
        _extract_repair_program,
        _run_embedded_python,
    )

    # Create a minimal plan directory so the embedded Python can run
    # inspect_semantic_health (even if it produces no findings).
    workspace = tmp_path / "workspace"
    megaplan_dir = workspace / ".megaplan"
    plans_dir = megaplan_dir / "plans"
    plan_dir = plans_dir / "test-plan"
    plan_dir.mkdir(parents=True)

    # Write a minimal state.json so plan_state_path resolution succeeds
    state = {
        "name": "test-plan",
        "current_state": "planned",
        "phase": "plan",
        "history": [],
    }
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

    # Create cloud-sessions marker
    marker_dir = tmp_path / "cloud-sessions"
    marker_dir.mkdir()
    marker_path = marker_dir / "test-session.json"
    marker_path.write_text(
        json.dumps(
            {
                "session": "test-session",
                "workspace": str(workspace),
                "run_kind": "plan",
                "plan_name": "test-plan",
            }
        ),
        encoding="utf-8",
    )

    repair_data_dir = marker_dir / "repair-data"
    repair_data_dir.mkdir()

    # Create a minimal chain.yaml so chain state resolution doesn't fail
    initiatives_dir = workspace / ".megaplan" / "initiatives" / "demo"
    initiatives_dir.mkdir(parents=True)
    (initiatives_dir / "chain.yaml").write_text(
        "milestones:\n  - label: m1\n", encoding="utf-8"
    )

    # Extract the collect_failure_context_json embedded Python
    program = _extract_repair_program(
        "collect_failure_context_json",
        "python3 - \"$workspace\" \"$session\" \"$run_kind\" \"$plan_name\" \"$MARKER_DIR\" \"$DATA_DIR\" \"$REMOTE_SPEC\" <<'PY'",
    )

    result = _run_embedded_python(
        program,
        str(workspace),
        "test-session",
        "plan",
        "test-plan",
        str(marker_dir),
        str(repair_data_dir),
        str(initiatives_dir / "chain.yaml"),
    )

    assert result.returncode == 0, result.stderr

    payload = json.loads(result.stdout)
    assert "semantic_health" in payload, (
        "collect_failure_context_json must include semantic_health key in output"
    )
    assert "semantic_context" in payload
    assert "custody_projection" in payload

    # semantic_health may be None if plan_dir doesn't have all required artifacts,
    # but the key must be present
    sh = payload["semantic_health"]
    if sh is not None:
        assert "schema" in sh
        assert "fingerprint" in sh
        assert "total_count" in sh
