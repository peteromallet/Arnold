from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

from arnold_pipelines.megaplan.cloud.github_sync import (
    GitHubSyncConfig,
    GitHubSyncThresholds,
    main,
    sync_persistent_problems,
)
from arnold_pipelines.megaplan.custody.action_validator import GateResult
from arnold_pipelines.megaplan.notification_safety import FixtureSafetyDecision
from arnold_pipelines.megaplan.cloud.incident_bridge import append_github_issue_published
from arnold_pipelines.megaplan.incident import IncidentLedger


def _authorized_publication_adapter():
    """Test publication adapter: explicit AUTHORIZED gate over a mock protocol.

    T-0017: publications must be routed through an adapter that owns the
    action gate — a direct github_cli call is never allowed.
    """
    from arnold_pipelines.megaplan.cloud.publication_adapter import PublicationAdapter

    protocol = Mock()
    reservation = Mock()
    reservation.global_logical_effect_key = "glek-test-t0017"
    protocol.reserve_and_start.return_value = reservation
    return PublicationAdapter(
        protocol,
        action_gate_check=lambda family, target_key: GateResult.AUTHORIZED,
    )


def _problem_projection(
    *,
    problem_id: str = "prob-sync-1",
    title: str = "Open problem with token sk-secret-value",
    status: str = "open",
    occurrence_count: int = 2,
    recurred_after_fix: bool = False,
    linked_incident_ids: list[str] | None = None,
) -> dict[str, object]:
    return {
        "problem_id": problem_id,
        "title": title,
        "status": status,
        "occurrence_count": occurrence_count,
        "recurred_after_fix": recurred_after_fix,
        "owner_actor": "watchdog",
        "next_review_ts": "2026-07-03T12:00:00Z",
        "linked_incident_ids": linked_incident_ids or ["inc-sync-1"],
        "fix_commits": [],
    }


def _incident_projection(
    *,
    incident_id: str = "inc-sync-1",
    summary: str = "Observed ghp_secret and sk-secret-value in logs",
) -> dict[str, object]:
    return {
        "incident_id": incident_id,
        "summary": summary,
        "state": "repair_attempt",
        "outcome": "started",
        "next_expected_event": "meta_repair.repair_attempt",
        "last_seq": 12,
        "session_ids": ["session-sync-1"],
    }


def _projections(problem: dict[str, object], incident: dict[str, object]) -> dict[str, object]:
    return {
        "problems": {
            "problems": [problem],
        },
        "incidents": {
            "incidents": [incident],
        },
    }


def _read_ledger_events(root: Path) -> list[dict[str, object]]:
    ledger = IncidentLedger(root)
    if not ledger.events_path.exists():
        return []
    return [json.loads(line) for line in ledger.events_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_sync_persistent_problems_creates_redacted_issue_and_appends_publication_event(tmp_path: Path) -> None:
    projections = _projections(_problem_projection(), _incident_projection())

    with patch("arnold_pipelines.megaplan.cloud.github_sync.github_cli.create_issue") as create_issue:
        with patch("arnold_pipelines.megaplan.cloud.github_sync.github_cli.search_issues") as search_issues:
            with patch("arnold_pipelines.megaplan.cloud.github_sync.github_cli.list_issues_by_label") as list_issues:
                create_issue.return_value = {
                    "ok": True,
                    "evidence_ref": {
                        "kind": "github.issue",
                        "repo": "acme/repo",
                        "number": 42,
                        "url": "https://github.com/acme/repo/issues/42",
                        "action": "created",
                    },
                }

                result = sync_persistent_problems(
                    config=GitHubSyncConfig(repo="acme/repo", repo_path=tmp_path),
                    root=tmp_path,
                    projections=projections,
                    publication_adapter=_authorized_publication_adapter(),
                )

    assert result["published"] == [
        {
            "problem_id": "prob-sync-1",
            "action": "created",
            "issue_number": 42,
            "issue_url": "https://github.com/acme/repo/issues/42",
            "ledger_event_id": result["published"][0]["ledger_event_id"],
        }
    ]
    assert result["failed"] == []
    assert result["skipped"] == []
    issue_title = create_issue.call_args.args[2]
    issue_body = create_issue.call_args.args[3]
    assert "sk-secret-value" not in issue_title
    assert "sk-secret-value" not in issue_body
    assert len(issue_body.encode("utf-8")) <= 2048
    search_issues.assert_not_called()
    list_issues.assert_not_called()

    events = _read_ledger_events(tmp_path)
    payload = events[-1]["payload"]
    assert payload["type"] == "github_sync.issue_published"
    assert payload["problem_id"] == "prob-sync-1"
    assert payload["next_expected_event"] == "next_three_hour_auditor.diagnosis"
    assert payload["evidence"][-1]["url"] == "https://github.com/acme/repo/issues/42"
    assert payload["links"]["publication"]["occurrence_count"] == 2


def test_github_sync_publishes_next_three_hour_diagnosis_event(tmp_path: Path) -> None:
    """T34/Step 49: GitHub sync publishes next_three_hour_auditor.diagnosis.

    GitHub publication is a sink — it must hand off to next_three_hour
    diagnosis/reconciliation, NOT to six_hour auditor or repair authority.
    """
    # Use a direct bridge call to verify event shape
    result = append_github_issue_published(
        incident_id="inc-t34-gh",
        problem_id="prob-t34-gh",
        summary="GitHub publication for T34",
        repo="acme/repo",
        number=99,
        url="https://github.com/acme/repo/issues/99",
        action="created",
        next_expected_event="next_three_hour_auditor.diagnosis",
        root=tmp_path,
    )
    assert result["kind"] == "incident.github_sync.issue_published"
    payload = result["payload"]
    assert payload["type"] == "github_sync.issue_published"
    assert payload["next_expected_event"] == "next_three_hour_auditor.diagnosis"
    assert payload["actor"] == "github_sync"

    # Verify the next_expected_event is NOT six_hour or repair authority
    assert payload["next_expected_event"] != "six_hour_auditor.diagnosis"
    assert payload["next_expected_event"] != "immediate_repair.repair_attempt"
    assert payload["next_expected_event"] != "meta_repair.repair_attempt"


def test_sync_persistent_problems_comments_existing_issue_when_threshold_crosses_multiple_of_five(tmp_path: Path) -> None:
    append_github_issue_published(
        summary="Previous publication",
        repo="acme/repo",
        number=42,
        url="https://github.com/acme/repo/issues/42",
        action="created",
        problem_id="prob-sync-1",
        incident_id="inc-sync-1",
        links={"publication": {"occurrence_count": 2, "recurred_after_fix": False, "status": "open"}},
        root=tmp_path,
    )
    projections = _projections(
        _problem_projection(occurrence_count=5),
        _incident_projection(summary="Latest summary after more recurrences"),
    )

    with patch("arnold_pipelines.megaplan.cloud.github_sync.github_cli.comment_issue") as comment_issue:
        comment_issue.return_value = {
            "ok": True,
            "evidence_ref": {
                "kind": "github.issue",
                "repo": "acme/repo",
                "number": 42,
                "url": "https://github.com/acme/repo/issues/42#issuecomment-9",
                "action": "commented",
            },
        }

        result = sync_persistent_problems(
            config=GitHubSyncConfig(repo="acme/repo", repo_path=tmp_path),
            root=tmp_path,
            projections=projections,
            publication_adapter=_authorized_publication_adapter(),
        )

    assert result["published"][0]["action"] == "commented"
    assert comment_issue.call_args.args[2] == 42
    assert "previous_published_occurrence_count: 2" in comment_issue.call_args.args[3]

    payload = _read_ledger_events(tmp_path)[-1]["payload"]
    assert payload["type"] == "github_sync.issue_published"
    assert payload["links"]["prior_publication"]["number"] == 42
    assert payload["links"]["publication"]["occurrence_count"] == 5


def test_sync_persistent_problems_records_publish_failures_in_ledger(tmp_path: Path) -> None:
    projections = _projections(_problem_projection(), _incident_projection())

    with patch("arnold_pipelines.megaplan.cloud.github_sync.github_cli.create_issue") as create_issue:
        create_issue.return_value = {"ok": False, "error": "rate limited", "fix_command": "gh auth login"}

        result = sync_persistent_problems(
            config=GitHubSyncConfig(repo="acme/repo", repo_path=tmp_path),
            root=tmp_path,
            projections=projections,
            publication_adapter=_authorized_publication_adapter(),
        )

    assert result["published"] == []
    assert result["failed"][0]["error"] == "rate limited"
    payload = _read_ledger_events(tmp_path)[-1]["payload"]
    assert payload["type"] == "github_sync.issue_publish_failed"
    assert payload["next_expected_event"] == "github_sync.retry"


def test_sync_persistent_problems_adapter_makes_one_provider_call_on_missing_label_error(
    tmp_path: Path,
) -> None:
    """T-0017: the ungated label-retry fallback is gone — the adapter path
    makes exactly one provider call and records the rejection as a typed
    failure instead of retrying without the missing label."""
    projections = _projections(_problem_projection(), _incident_projection())

    with patch("arnold_pipelines.megaplan.cloud.github_sync.github_cli.create_issue") as create_issue:
        create_issue.return_value = {
            "ok": False,
            "error": "could not add label: 'incident-control-plane' not found",
            "fix_command": "gh auth login",
        }

        result = sync_persistent_problems(
            config=GitHubSyncConfig(repo="acme/repo", repo_path=tmp_path),
            root=tmp_path,
            projections=projections,
            publication_adapter=_authorized_publication_adapter(),
        )

    assert result["published"] == []
    assert result["failed"] == [
        {
            "problem_id": "prob-sync-1",
            "action": "created",
            "error": "could not add label: 'incident-control-plane' not found",
            "ledger_event_id": result["failed"][0]["ledger_event_id"],
        }
    ]
    assert create_issue.call_count == 1

    payload = _read_ledger_events(tmp_path)[-1]["payload"]
    assert payload["type"] == "github_sync.issue_publish_failed"
    assert payload["next_expected_event"] == "github_sync.retry"


def test_sync_persistent_problems_skips_real_publication_when_action_off(tmp_path: Path, monkeypatch) -> None:
    projections = _projections(_problem_projection(), _incident_projection())
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.github_sync_wbc.classify_fixture_safety",
        lambda **_kwargs: FixtureSafetyDecision(False, "not_fixture"),
    )

    with patch("arnold_pipelines.megaplan.cloud.github_sync.github_cli.create_issue") as create_issue:
        result = sync_persistent_problems(
            config=GitHubSyncConfig(repo="acme/repo", repo_path=tmp_path),
            root=tmp_path,
            projections=projections,
            publication_adapter=_authorized_publication_adapter(),
        )

    assert result["published"] == []
    assert result["failed"] == []
    assert result["skipped"] == [
        {
            "problem_id": "prob-sync-1",
            "reason": "action_off",
            "suppression_reason": (
                "megaplan.cloud.github_sync.create remains action-off outside "
                "fixture-authorized execution during WBC adoption"
            ),
        }
    ]
    create_issue.assert_not_called()


def test_sync_persistent_problems_uses_configurable_thresholds(tmp_path: Path) -> None:
    projections = _projections(_problem_projection(occurrence_count=3), _incident_projection())

    with patch("arnold_pipelines.megaplan.cloud.github_sync.github_cli.create_issue") as create_issue:
        result = sync_persistent_problems(
            config=GitHubSyncConfig(
                repo="acme/repo",
                repo_path=tmp_path,
                thresholds=GitHubSyncThresholds(create_min_occurrences=4, update_every_occurrences=3),
            ),
            root=tmp_path,
            projections=projections,
            publication_adapter=_authorized_publication_adapter(),
        )

    assert result["published"] == []
    assert result["skipped"] == [{"problem_id": "prob-sync-1", "reason": "threshold_not_met"}]
    create_issue.assert_not_called()


def test_main_fails_closed_without_explicit_gate(tmp_path: Path, capsys: object) -> None:
    """T-0017: production main() installs no explicit action gate — every
    publication is refused (typed failure), zero github_cli calls, exit 1."""
    projections = _projections(_problem_projection(), _incident_projection())
    with patch("arnold_pipelines.megaplan.cloud.github_sync.rebuild_projections", return_value=projections):
        with patch("arnold_pipelines.megaplan.cloud.github_sync.github_cli.create_issue") as create_issue:
            exit_code = main(["--repo", "acme/repo", "--repo-path", str(tmp_path), "--root", str(tmp_path)])

    out, _ = capsys.readouterr()
    assert exit_code == 1
    payload = json.loads(out)
    assert payload["repo"] == "acme/repo"
    assert payload["published"] == []
    assert len(payload["failed"]) == 1
    assert "refused" in payload["failed"][0]["error"]
    create_issue.assert_not_called()
