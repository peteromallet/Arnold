"""One-way GitHub publication for persistent incident problems."""

from __future__ import annotations

import argparse
import json
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from arnold.runtime.event_journal import read_event_journal_paged

from agentbox import github as github_cli
from arnold_pipelines.megaplan.cloud.incident_bridge import (
    append_github_issue_publish_failed,
    append_github_issue_published,
)
from arnold_pipelines.megaplan.cloud.github_sync_wbc import (
    GITHUB_SYNC_COMMENT_SURFACE,
    GITHUB_SYNC_COMMENT_WRITER_ID,
    GITHUB_SYNC_CREATE_SURFACE,
    GITHUB_SYNC_CREATE_WRITER_ID,
    GitHubSyncRule,
    validate_github_sync_publication,
)
from arnold_pipelines.megaplan.cloud.redact import redact_text
from arnold_pipelines.megaplan.incident.projection import rebuild_projections
from arnold_pipelines.megaplan.incident.schema import validate_incident_event
from arnold_pipelines.megaplan.types import CliError

_INCIDENT_LEDGER_DIR = Path(".megaplan") / "incident-ledger"
_EVENTS_FILE = "events.jsonl"
_PUBLICATION_TEXT_LIMIT_BYTES = 2 * 1024
_PUBLICATION_TEXT_TRUNCATION = "\n[truncated to fit 2KB publication gate]"
_MISSING_LABEL_RE = re.compile(r"could not add label: ['\"]?([^'\"]+)['\"]? not found", re.IGNORECASE)


@dataclass(frozen=True)
class GitHubSyncThresholds:
    create_min_occurrences: int = 2
    update_every_occurrences: int = 5


@dataclass(frozen=True)
class GitHubSyncConfig:
    repo: str
    repo_path: Path | str
    issue_labels: tuple[str, ...] = ("incident-control-plane", "persistent-problem")
    thresholds: GitHubSyncThresholds = field(default_factory=GitHubSyncThresholds)


def sync_persistent_problems(
    *,
    config: GitHubSyncConfig,
    root: Path | str | None = None,
    projections: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Publish persistent problem projections to GitHub without reading GitHub state."""
    workspace_root = Path.cwd() if root is None else Path(root)
    docs = projections or rebuild_projections(workspace_root)
    incidents_by_id = {
        incident["incident_id"]: incident
        for incident in docs.get("incidents", {}).get("incidents", [])
        if isinstance(incident, dict) and isinstance(incident.get("incident_id"), str)
    }
    history = _load_publication_history(workspace_root)

    published: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for problem in docs.get("problems", {}).get("problems", []):
        if not isinstance(problem, dict):
            continue
        problem_id = str(problem.get("problem_id") or "").strip()
        if not problem_id:
            continue
        incident = _representative_incident(problem, incidents_by_id)
        publication = history.get(problem_id)
        action = _publication_action(problem, publication, config.thresholds)
        if action is None:
            skipped.append(
                {
                    "problem_id": problem_id,
                    "reason": "threshold_not_met",
                }
            )
            continue

        writer_id = GITHUB_SYNC_CREATE_WRITER_ID if action == "create" else GITHUB_SYNC_COMMENT_WRITER_ID
        surface_name = GITHUB_SYNC_CREATE_SURFACE if action == "create" else GITHUB_SYNC_COMMENT_SURFACE
        try:
            validation_evidence = validate_github_sync_publication(
                writer_id=writer_id,
                surface_name=surface_name,
                action=action,
                problem_id=problem_id,
                project_dir=workspace_root,
                rules=(
                    GitHubSyncRule(
                        "problem_open",
                        "open",
                        problem.get("status"),
                        str(problem.get("status") or "") == "open",
                    ),
                    GitHubSyncRule(
                        "repo_present",
                        True,
                        bool(str(config.repo).strip()),
                        bool(str(config.repo).strip()),
                    ),
                ),
                extra={
                    "repo": config.repo,
                    "occurrence_count": int(problem.get("occurrence_count") or 0),
                },
            )
        except CliError as exc:
            if exc.code != "github_sync_action_off":
                raise
            skipped.append(
                {
                    "problem_id": problem_id,
                    "reason": "action_off",
                    "suppression_reason": exc.message,
                }
            )
            continue

        if action == "create":
            issue_title = _issue_title(problem)
            issue_body = _issue_body(problem, incident)
            result = _create_issue_with_label_fallback(
                repo_path=config.repo_path,
                repo=config.repo,
                title=issue_title,
                body=issue_body,
                labels=list(config.issue_labels),
            )
            summary = f"Published persistent problem {problem_id} to GitHub as a new issue"
            publish_action = "created"
        else:
            if publication is None or publication.get("number") is None:
                skipped.append(
                    {
                        "problem_id": problem_id,
                        "reason": "missing_issue_reference",
                    }
                )
                continue
            issue_body = _issue_comment(problem, incident, publication)
            result = github_cli.comment_issue(
                config.repo_path,
                config.repo,
                int(publication["number"]),
                issue_body,
            )
            summary = f"Published persistent problem {problem_id} update to GitHub issue #{publication['number']}"
            publish_action = "commented"

        publication_links = _publication_links(problem, publication, body_text=issue_body)
        event_evidence = _publication_evidence(problem, incident, issue_body)
        event_evidence.append(
            {
                "kind": "github_sync.wbc_validation",
                "surface_name": surface_name,
                "action": action,
                "fixture_safety": validation_evidence["fixture_safety"],
                "source_record": validation_evidence["source_record"],
            }
        )
        if result.get("omitted_labels"):
            publication_links["label_fallback"] = {
                "omitted_labels": list(result["omitted_labels"]),
                "applied_labels": list(result.get("applied_labels") or []),
            }
            event_evidence.append(
                {
                    "kind": "github_sync.label_fallback",
                    "omitted_labels": list(result["omitted_labels"]),
                    "applied_labels": list(result.get("applied_labels") or []),
                }
            )
        incident_id = incident.get("incident_id") if isinstance(incident, dict) else None

        if result.get("ok"):
            evidence_ref = result["evidence_ref"]
            bridge_result = append_github_issue_published(
                summary=summary,
                repo=config.repo,
                number=int(evidence_ref["number"]),
                url=str(evidence_ref["url"]),
                action=publish_action,
                incident_id=incident_id,
                problem_id=problem_id,
                evidence=event_evidence,
                next_expected_event="six_hour_auditor.diagnosis",
                links=publication_links,
                root=workspace_root,
            )
            published.append(
                {
                    "problem_id": problem_id,
                    "action": publish_action,
                    "issue_number": evidence_ref["number"],
                    "issue_url": evidence_ref["url"],
                    "ledger_event_id": bridge_result["payload"]["event_id"],
                }
            )
            continue

        error_text = str(result.get("error") or "GitHub publication failed")
        bridge_result = append_github_issue_publish_failed(
            summary=f"Failed to publish persistent problem {problem_id} to GitHub",
            repo=config.repo,
            action=publish_action,
            error=error_text,
            incident_id=incident_id,
            problem_id=problem_id,
            evidence=event_evidence,
            links=publication_links,
            root=workspace_root,
        )
        failed.append(
            {
                "problem_id": problem_id,
                "action": publish_action,
                "error": error_text,
                "ledger_event_id": bridge_result["payload"]["event_id"],
            }
        )

    return {
        "repo": config.repo,
        "published": published,
        "failed": failed,
        "skipped": skipped,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--repo-path", default=".")
    parser.add_argument("--root", default=".")
    parser.add_argument("--create-min-occurrences", type=int, default=2)
    parser.add_argument("--update-every-occurrences", type=int, default=5)
    parser.add_argument(
        "--label",
        action="append",
        default=None,
        dest="labels",
    )
    args = parser.parse_args(argv)
    result = sync_persistent_problems(
        config=GitHubSyncConfig(
            repo=args.repo,
            repo_path=Path(args.repo_path),
            issue_labels=tuple(args.labels or ("incident-control-plane", "persistent-problem")),
            thresholds=GitHubSyncThresholds(
                create_min_occurrences=args.create_min_occurrences,
                update_every_occurrences=args.update_every_occurrences,
            ),
        ),
        root=Path(args.root),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not result["failed"] else 1


def _create_issue_with_label_fallback(
    *,
    repo_path: Path | str,
    repo: str,
    title: str,
    body: str,
    labels: list[str],
) -> dict[str, Any]:
    requested_labels = [label.strip() for label in labels if str(label).strip()]
    attempted_labels = list(requested_labels)
    omitted_labels: list[str] = []
    while True:
        result = github_cli.create_issue(
            repo_path,
            repo,
            title,
            body,
            labels=attempted_labels or None,
        )
        if result.get("ok"):
            if omitted_labels:
                result["omitted_labels"] = list(omitted_labels)
                result["applied_labels"] = list(attempted_labels)
            return result
        retry_labels = _retry_labels_after_missing_label_error(
            result.get("error"),
            attempted_labels,
        )
        if retry_labels is None:
            return result
        omitted_labels.extend(label for label in attempted_labels if label not in retry_labels)
        attempted_labels = retry_labels


def _retry_labels_after_missing_label_error(
    error: Any,
    attempted_labels: list[str],
) -> list[str] | None:
    if not attempted_labels:
        return None
    match = _MISSING_LABEL_RE.search(str(error or ""))
    if match is None:
        return None
    missing_label = match.group(1).strip()
    if missing_label not in attempted_labels:
        return None
    return [label for label in attempted_labels if label != missing_label]


def _publication_action(
    problem: dict[str, Any],
    publication: dict[str, Any] | None,
    thresholds: GitHubSyncThresholds,
) -> str | None:
    status = str(problem.get("status") or "")
    occurrence_count = int(problem.get("occurrence_count") or 0)
    recurred_after_fix = bool(problem.get("recurred_after_fix"))
    if status != "open":
        return None
    if publication is None:
        return "create" if occurrence_count >= thresholds.create_min_occurrences else None

    published_occurrence_count = int(publication.get("occurrence_count") or 0)
    published_recurred_after_fix = bool(publication.get("recurred_after_fix"))
    crossed_multiple = (
        thresholds.update_every_occurrences > 0
        and occurrence_count >= thresholds.update_every_occurrences
        and (occurrence_count // thresholds.update_every_occurrences)
        > (published_occurrence_count // thresholds.update_every_occurrences)
    )
    recurred_flipped = recurred_after_fix and not published_recurred_after_fix
    if crossed_multiple or recurred_flipped:
        return "comment"
    return None


def _issue_title(problem: dict[str, Any]) -> str:
    raw = f"{problem.get('problem_id')}: {problem.get('title') or 'Persistent problem'}"
    title = redact_text(raw).strip()
    return title[:240]


def _issue_body(problem: dict[str, Any], incident: dict[str, Any] | None) -> str:
    lines = [
        "Persistent problem detected by the incident control plane.",
        "",
        f"- problem_id: {problem.get('problem_id')}",
        f"- status: {problem.get('status')}",
        f"- occurrence_count: {problem.get('occurrence_count')}",
        f"- recurred_after_fix: {bool(problem.get('recurred_after_fix'))}",
        f"- owner_actor: {problem.get('owner_actor') or 'unknown'}",
        f"- next_review_ts: {problem.get('next_review_ts') or 'unknown'}",
        f"- linked_incidents: {', '.join(_string_list(problem.get('linked_incident_ids'))) or 'none'}",
    ]
    fix_commits = _string_list(problem.get("fix_commits"))
    if fix_commits:
        lines.append(f"- fix_commits: {', '.join(fix_commits)}")
    if isinstance(incident, dict):
        lines.extend(
            [
                "",
                "Latest linked incident:",
                f"- incident_id: {incident.get('incident_id')}",
                f"- state: {incident.get('state')}",
                f"- outcome: {incident.get('outcome')}",
                f"- next_expected_event: {incident.get('next_expected_event') or 'none'}",
                f"- summary: {incident.get('summary') or ''}",
            ]
        )
    lines.extend(
        [
            "",
            "GitHub is a publication sink only; the incident ledger remains canonical state.",
        ]
    )
    return _compact_publication_text("\n".join(lines))


def _issue_comment(
    problem: dict[str, Any],
    incident: dict[str, Any] | None,
    publication: dict[str, Any],
) -> str:
    lines = [
        "Incident control plane update.",
        "",
        f"- problem_id: {problem.get('problem_id')}",
        f"- occurrence_count: {problem.get('occurrence_count')}",
        f"- recurred_after_fix: {bool(problem.get('recurred_after_fix'))}",
        f"- previous_published_occurrence_count: {publication.get('occurrence_count') or 0}",
    ]
    if isinstance(incident, dict):
        lines.append(f"- latest_incident_id: {incident.get('incident_id')}")
        lines.append(f"- latest_summary: {incident.get('summary') or ''}")
    return _compact_publication_text("\n".join(lines))


def _compact_publication_text(text: str) -> str:
    redacted = redact_text(text).strip()
    encoded = redacted.encode("utf-8")
    if len(encoded) <= _PUBLICATION_TEXT_LIMIT_BYTES:
        return redacted
    suffix_bytes = _PUBLICATION_TEXT_TRUNCATION.encode("utf-8")
    allowed = _PUBLICATION_TEXT_LIMIT_BYTES - len(suffix_bytes)
    truncated = encoded[:allowed].decode("utf-8", errors="ignore")
    while len((truncated + _PUBLICATION_TEXT_TRUNCATION).encode("utf-8")) > _PUBLICATION_TEXT_LIMIT_BYTES and truncated:
        truncated = truncated[:-1]
    return truncated + _PUBLICATION_TEXT_TRUNCATION


def _publication_evidence(
    problem: dict[str, Any],
    incident: dict[str, Any] | None,
    body_text: str,
) -> list[dict[str, Any]]:
    evidence = [
        {
            "kind": "github_sync.problem_projection",
            "problem_id": problem.get("problem_id"),
            "occurrence_count": problem.get("occurrence_count"),
            "recurred_after_fix": bool(problem.get("recurred_after_fix")),
            "status": problem.get("status"),
        },
        {
            "kind": "github_sync.publication_payload",
            "body_sha256": _sha256_text(body_text),
            "body_bytes": len(body_text.encode("utf-8")),
        },
    ]
    if isinstance(incident, dict):
        evidence.append(
            {
                "kind": "github_sync.incident_projection",
                "incident_id": incident.get("incident_id"),
                "last_seq": incident.get("last_seq"),
                "session_id": (incident.get("session_ids") or [None])[0],
            }
        )
    return evidence


def _publication_links(
    problem: dict[str, Any],
    publication: dict[str, Any] | None,
    *,
    body_text: str,
) -> dict[str, Any]:
    links = {
        "publication": {
            "problem_id": problem.get("problem_id"),
            "occurrence_count": int(problem.get("occurrence_count") or 0),
            "recurred_after_fix": bool(problem.get("recurred_after_fix")),
            "status": problem.get("status"),
            "body_sha256": _sha256_text(body_text),
        }
    }
    if publication is not None:
        links["prior_publication"] = {
            "number": publication.get("number"),
            "url": publication.get("url"),
            "occurrence_count": publication.get("occurrence_count"),
            "recurred_after_fix": publication.get("recurred_after_fix"),
        }
    return links


def _representative_incident(
    problem: dict[str, Any],
    incidents_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    for incident_id in problem.get("linked_incident_ids", []):
        incident = incidents_by_id.get(incident_id)
        if incident is None:
            continue
        if best is None or int(incident.get("last_seq") or 0) > int(best.get("last_seq") or 0):
            best = incident
    return best


def _load_publication_history(root: Path) -> dict[str, dict[str, Any]]:
    events_path = root / _INCIDENT_LEDGER_DIR / _EVENTS_FILE
    if not events_path.exists():
        return {}
    with tempfile.TemporaryDirectory(prefix="github-sync-history-") as tmp_dir:
        tmp_root = Path(tmp_dir)
        (tmp_root / "events.ndjson").write_text(events_path.read_text(encoding="utf-8"), encoding="utf-8")
        journal_events = read_event_journal_paged(tmp_root, sort_page=True)

    history: dict[str, dict[str, Any]] = {}
    for event in journal_events:
        if event.get("kind") != "incident.github_sync.issue_published":
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        try:
            normalized = validate_incident_event(payload)
        except ValueError:
            continue
        problem_id = str(normalized.get("problem_id") or "").strip()
        if not problem_id:
            continue
        publication = _extract_publication_record(normalized)
        if publication is None:
            continue
        publication["seq"] = event.get("seq")
        history[problem_id] = publication
    return history


def _extract_publication_record(payload: dict[str, Any]) -> dict[str, Any] | None:
    issue_ref = None
    for evidence in payload.get("evidence", []):
        if not isinstance(evidence, dict):
            continue
        if evidence.get("kind") == "github.issue" and evidence.get("number") is not None:
            issue_ref = evidence
    if issue_ref is None:
        return None
    publication_links = payload.get("links") if isinstance(payload.get("links"), dict) else {}
    publication_snapshot = publication_links.get("publication") if isinstance(publication_links.get("publication"), dict) else {}
    return {
        "number": issue_ref.get("number"),
        "url": issue_ref.get("url"),
        "repo": issue_ref.get("repo"),
        "occurrence_count": int(publication_snapshot.get("occurrence_count") or 0),
        "recurred_after_fix": bool(publication_snapshot.get("recurred_after_fix")),
    }


def _sha256_text(text: str) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


__all__ = [
    "GitHubSyncConfig",
    "GitHubSyncThresholds",
    "main",
    "sync_persistent_problems",
]


if __name__ == "__main__":
    raise SystemExit(main())
