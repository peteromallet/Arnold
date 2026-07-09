from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from arnold_pipelines.megaplan.cloud.github_sync import (
    GitHubSyncConfig,
    GitHubSyncThresholds,
    main,
    sync_persistent_problems,
)
from arnold_pipelines.megaplan.cloud.incident_bridge import append_github_issue_published
from arnold_pipelines.megaplan.incident import IncidentLedger


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
    assert payload["next_expected_event"] == "six_hour_auditor.diagnosis"
    assert payload["evidence"][-1]["url"] == "https://github.com/acme/repo/issues/42"
    assert payload["links"]["publication"]["occurrence_count"] == 2


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
        )

    assert result["published"] == []
    assert result["failed"][0]["error"] == "rate limited"
    payload = _read_ledger_events(tmp_path)[-1]["payload"]
    assert payload["type"] == "github_sync.issue_publish_failed"
    assert payload["next_expected_event"] == "github_sync.retry"


def test_sync_persistent_problems_retries_without_missing_labels(tmp_path: Path) -> None:
    projections = _projections(_problem_projection(), _incident_projection())

    with patch("arnold_pipelines.megaplan.cloud.github_sync.github_cli.create_issue") as create_issue:
        create_issue.side_effect = [
            {
                "ok": False,
                "error": "could not add label: 'incident-control-plane' not found",
                "fix_command": "gh auth login",
            },
            {
                "ok": True,
                "evidence_ref": {
                    "kind": "github.issue",
                    "repo": "acme/repo",
                    "number": 42,
                    "url": "https://github.com/acme/repo/issues/42",
                    "action": "created",
                },
            },
        ]

        result = sync_persistent_problems(
            config=GitHubSyncConfig(repo="acme/repo", repo_path=tmp_path),
            root=tmp_path,
            projections=projections,
        )

    assert result["failed"] == []
    assert result["published"][0]["issue_number"] == 42
    assert create_issue.call_args_list[0].kwargs["labels"] == ["incident-control-plane", "persistent-problem"]
    assert create_issue.call_args_list[1].kwargs["labels"] == ["persistent-problem"]

    payload = _read_ledger_events(tmp_path)[-1]["payload"]
    assert payload["type"] == "github_sync.issue_published"
    assert payload["links"]["label_fallback"] == {
        "omitted_labels": ["incident-control-plane"],
        "applied_labels": ["persistent-problem"],
    }


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
        )

    assert result["published"] == []
    assert result["skipped"] == [{"problem_id": "prob-sync-1", "reason": "threshold_not_met"}]
    create_issue.assert_not_called()


def test_main_prints_json_result(tmp_path: Path, capsys: object) -> None:
    projections = _projections(_problem_projection(), _incident_projection())
    with patch("arnold_pipelines.megaplan.cloud.github_sync.rebuild_projections", return_value=projections):
        with patch("arnold_pipelines.megaplan.cloud.github_sync.github_cli.create_issue") as create_issue:
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

            exit_code = main(["--repo", "acme/repo", "--repo-path", str(tmp_path), "--root", str(tmp_path)])

    out, _ = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(out)
    assert payload["repo"] == "acme/repo"
    assert payload["published"][0]["problem_id"] == "prob-sync-1"
