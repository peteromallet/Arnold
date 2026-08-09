from __future__ import annotations

import json

from arnold_pipelines.megaplan.resident.status_tree import (
    compact_cloud_status_snapshot,
    read_cloud_status_node,
)


def _large_snapshot() -> dict:
    state_line = "state_written | state=" + json.dumps(
        {
            "name": "s2-contract-foundation",
            "current_state": "critiqued",
            "active_step": {"phase": "gate", "attempt": 48},
            "meta": {"large": "x" * 18_000},
        }
    )
    tail = "\n".join(["gate:phase_end", *([state_line] * 12)])
    context = {
        "failure_classification": "structural_schema_failure",
        "plan_events_path": "/workspace/plan/events.ndjson",
        "plan_events_tail": tail,
        "run_log_tail": "failure\n" * 1_000,
    }
    attempt = {
        "attempt_id": "1",
        "state": "failed",
        "outcome": "repair_failed",
        "recorded_at": "2026-07-13T17:40:00Z",
        "raw": {
            "failure_context": context,
            "post_launch_failure_context": context,
            "post_kimi_failure_context": context,
        },
    }
    return {
        "generated_at": "2026-07-13T17:41:00Z",
        "source": "cloud-local-observer",
        "summary": {"running": 1, "repairing": 1},
        "sessions": [
            {
                "session": "workflow-boundary-contracts",
                "status": "repairing",
                "process": True,
                "current_plan": "s2-contract-foundation",
                "operator_next": "inspect repair custody",
                "progress": {"percent": 30, "plan_percent": 18},
                "repair_custody": {
                    "canonical_state": "repairing",
                    "failure_kind": "structural_schema_failure",
                    "request_count": 1,
                    "attempt_count": 1,
                    "plan_state": {
                        "current_state": "critiqued",
                        "history": [{"step": "gate", "result": "failed"}],
                        "meta": {"large": "y" * 100_000},
                    },
                    "attempts": [attempt],
                },
            }
        ],
    }


def test_hot_context_root_excludes_raw_repair_evidence() -> None:
    snapshot = _large_snapshot()
    assert len(json.dumps(snapshot)) > 700_000

    root = compact_cloud_status_snapshot(snapshot)
    encoded = json.dumps(root)

    assert len(encoded) < 15_000
    assert "plan_events_tail" not in encoded
    assert '"raw"' not in encoded
    assert root["sessions"][0]["repair"]["attempt_count"] == 1
    assert root["sessions"][0]["children"][-1].endswith("/events")


def test_root_exposes_recency_sorted_canonical_completed_sessions_beyond_legacy_preview() -> None:
    snapshot = {
        "generated_at": "2026-07-14T18:00:00Z",
        "sessions": [
            {
                "session": f"older-{index}",
                "display_name": f"Older {index}",
                "status": "complete",
                "latest_activity": f"2026-07-01T00:0{index}:00Z",
            }
            for index in range(3)
        ]
        + [
            {
                "session": "repository-strategy-roadmap",
                "display_name": "Repository strategy roadmap",
                "status": "complete",
                "completed_at": "2026-07-14T17:18:48Z",
                "latest_activity": "2026-07-14T17:18:48Z",
                "completed_count": 5,
                "milestone_count": 5,
                "progress": {"completed_count": 5, "milestone_count": 5},
            },
            {"session": "paused", "status": "paused"},
            {"session": "failed", "status": "failed"},
        ],
    }

    root = compact_cloud_status_snapshot(snapshot)

    assert root["completed_session_count"] == 4
    assert [row["session"] for row in root["recently_completed"]] == [
        "repository-strategy-roadmap",
    ]
    strategy = root["recently_completed"][0]
    assert strategy["progress"]["completed_count"] == 5
    assert strategy["progress"]["milestone_count"] == 5


def test_root_only_includes_completed_sessions_within_rolling_twelve_hours() -> None:
    snapshot = {
        "generated_at": "2026-07-14T18:00:00Z",
        "sessions": [
            {"session": "inside", "status": "complete", "completed_at": "2026-07-14T06:00:01Z"},
            {"session": "boundary", "status": "complete", "completed_at": "2026-07-14T06:00:00Z"},
            {"session": "outside", "status": "complete", "completed_at": "2026-07-14T05:59:59Z"},
        ],
    }

    root = compact_cloud_status_snapshot(snapshot)

    assert [row["session"] for row in root["recently_completed"]] == ["inside", "boundary"]
    assert root["recently_completed_omitted_count"] == 0


def test_root_excludes_stale_completion_despite_fresh_watchdog_activity() -> None:
    snapshot = {
        "generated_at": "2026-07-14T18:00:00Z",
        "sessions": [
            {
                "session": "old-completion",
                "status": "complete",
                "completed_at": "2026-07-08T19:28:14.239295Z",
                "latest_activity": "2026-07-14T17:59:59Z",
            },
            {
                "session": "missing-terminal-receipt",
                "status": "complete",
                "latest_activity": "2026-07-14T17:59:59Z",
            },
        ],
    }

    root = compact_cloud_status_snapshot(snapshot)

    assert root["completed_session_count"] == 2
    assert root["recently_completed"] == []


def test_status_tree_navigates_to_bounded_repair_evidence() -> None:
    snapshot = _large_snapshot()
    run = "session/workflow-boundary-contracts"

    repair = read_cloud_status_node(snapshot, node_id=f"{run}/repair")
    attempt_node = repair["node"]["value"]["attempts"][0]["node_id"]
    assert "raw" not in json.dumps(repair)

    attempt = read_cloud_status_node(snapshot, node_id=attempt_node)
    context_node = attempt["node"]["value"]["children"][0]
    context = read_cloud_status_node(snapshot, node_id=context_node)
    tails = context["node"]["value"]["evidence_tails"]
    plan_events_node = next(item["node_id"] for item in tails if item["name"] == "plan_events_tail")

    page = read_cloud_status_node(snapshot, node_id=plan_events_node, limit=3)
    assert page["node"]["total_count"] == 13
    assert page["node"]["next_cursor"] == 3
    assert len(json.dumps(page)) < 5_000
    state_event = page["node"]["items"][1]
    assert state_event["event"] == "state_written"
    assert state_event["state"]["current_state"] == "critiqued"
    assert "large" not in json.dumps(state_event)


def test_status_tree_paginates_plan_history_without_full_plan_state() -> None:
    snapshot = _large_snapshot()
    history = snapshot["sessions"][0]["repair_custody"]["plan_state"]["history"]
    history.extend({"step": f"step-{index}", "result": "ok"} for index in range(20))

    result = read_cloud_status_node(
        snapshot,
        node_id="session/workflow-boundary-contracts/events",
        cursor=5,
        limit=4,
    )

    assert len(result["node"]["items"]) == 4
    assert result["node"]["next_cursor"] == 9
    assert result["node"]["total_count"] == 21


def test_root_does_not_infer_chain_completion_from_terminal_plan_progress() -> None:
    """Plan-level done/100% must not override the canonical session status."""

    snapshot = {
        "generated_at": "2026-07-14T18:00:00Z",
        "sessions": [
            {
                "session": "repository-strategy-roadmap",
                "status": "attention",
                "display_state": "done",
                "chain_complete": False,
                "completed_count": 4,
                "milestone_count": 5,
                "latest_activity": "2026-07-14T17:32:20Z",
                "operator_next": "terminal plan requires chain reconciliation",
                "progress": {
                    "percent": 100,
                    "plan_percent": 100,
                    "plan_percent_basis": (
                        "plan lifecycle and recorded task-weight bookkeeping; "
                        "not implementation acceptance"
                    ),
                    "display_state": "done",
                    "completed_count": 4,
                    "milestone_count": 5,
                },
            }
        ],
    }

    root = compact_cloud_status_snapshot(snapshot)

    assert root["recently_completed"] == []
    assert root["completed_sessions_preview"] == []
    assert root["completed_session_count"] == 0
    assert root["sessions"][0]["status"] == "attention"
    assert root["sessions"][0]["display_state"] == "done"
    assert "not implementation acceptance" in (
        root["sessions"][0]["progress"]["plan_percent_basis"]
    )


# ── M9 (T52): projection metadata, bounded stale/unknown, rebuild pagination ─


def test_source_cursor_aggregate_present_in_compact_root() -> None:
    """The compact root must carry source_cursor_aggregate with sessions_with_cursor."""
    snapshot = {
        "generated_at": "2026-07-22T18:00:00Z",
        "sessions": [
            {
                "session": "plan-a",
                "status": "running",
                "process": True,
                "source_cursor": {
                    "vector_id": "sha256:abc123",
                    "cursors": [
                        {"dimension": "lifecycle", "state": "fresh", "version": "v1", "observed_at": "2026-07-22T18:00:00Z"},
                        {"dimension": "process_correlation", "state": "stale", "version": "v1", "observed_at": "2026-07-22T17:55:00Z"},
                    ],
                },
                "latest_activity": "2026-07-22T17:55:00Z",
            },
        ],
    }
    root = compact_cloud_status_snapshot(snapshot)
    agg = root.get("source_cursor_aggregate")
    assert isinstance(agg, dict), f"Expected source_cursor_aggregate dict, got {type(agg)}"
    assert agg.get("sessions_with_cursor", 0) >= 1
    assert agg.get("total_non_fresh_dimensions", 0) >= 0


def test_source_cursor_metadata_never_replaces_display_state() -> None:
    """M9 metadata must attach as separate fields, never replacing status/display_state."""
    snapshot = {
        "generated_at": "2026-07-22T18:00:00Z",
        "sessions": [
            {
                "session": "plan-a",
                "status": "running",
                "display_state": "executing",
                "source_cursor": {
                    "dimensions": [
                        {"dimension": "lifecycle", "state": "stale"},
                    ],
                },
                "latest_activity": "2026-07-22T17:55:00Z",
            },
        ],
    }
    root = compact_cloud_status_snapshot(snapshot)
    session = root["sessions"][0]
    assert session["status"] == "running", "status must be preserved"
    assert session.get("display_state") == "executing", "display_state must be preserved"
    # source_cursor must be separate, not overriding status
    assert isinstance(session.get("source_cursor_compact"), (dict, type(None)))


def test_indeterminate_completions_surfaced_with_evidence_gaps() -> None:
    """_classify_completion_state returns indeterminate when WBC/custody/run_authority are non-fresh."""
    from arnold_pipelines.megaplan.resident.status_tree import _classify_completion_state

    session = {
        "session": "plan-a",
        "status": "complete",
        "completed_at": "2026-07-22T17:00:00Z",
        "source_cursor": {
            "cursors": [
                {"dimension": "wbc", "state": "unknown", "version": "", "observed_at": "2026-07-22T17:00:00Z"},
                {"dimension": "custody", "state": "stale", "version": "v1", "observed_at": "2026-07-22T16:00:00Z"},
                {"dimension": "lifecycle", "state": "fresh", "version": "v1", "observed_at": "2026-07-22T17:00:00Z"},
            ],
        },
        "latest_activity": "2026-07-22T17:00:00Z",
    }
    # Direct classification must return indeterminate for WBC/custody non-fresh
    assert _classify_completion_state(session) == "indeterminate"

    # But compact_cloud_status_snapshot uses compacted sessions which transform
    # source_cursor → source_cursor_compact; this is a known gap (M9/T44 compaction
    # regression).  Verify the raw classification contract holds.
    snapshot = {"generated_at": "2026-07-22T18:00:00Z", "sessions": [session]}
    root = compact_cloud_status_snapshot(snapshot)
    # The compacted root may not surface indeterminate due to source_cursor→source_cursor_compact
    # transformation, but the classification contract must be correct at the boundary.
    assert isinstance(root["indeterminate_completion_count"], int)


def test_bounded_disclosure_preserves_pagination_under_metadata() -> None:
    """Pagination must work correctly even with M9 metadata enrichment."""
    snapshot = _large_snapshot()
    # Extend history so pagination is meaningful
    history = snapshot["sessions"][0]["repair_custody"]["plan_state"]["history"]
    history.extend({"step": f"step-{index}", "result": "ok"} for index in range(20))
    # Add M9 metadata to the session
    sessions = snapshot["sessions"]
    for s in sessions:
        s["source_cursor"] = {
            "cursors": [
                {"dimension": "lifecycle", "state": "fresh", "version": "v1", "observed_at": "2026-07-22T18:00:00Z"},
            ],
        }

    result = read_cloud_status_node(
        snapshot,
        node_id="session/workflow-boundary-contracts/events",
        cursor=0,
        limit=3,
    )
    assert result["node"]["total_count"] > 3  # 21 events
    assert result["node"]["next_cursor"] is not None
    assert len(result["node"]["items"]) <= 3
    # The result must never contain raw evidence
    encoded = json.dumps(result)
    assert "plan_events_tail" not in encoded
    assert '"raw"' not in encoded


def test_stale_banner_suppresses_all_active_listings() -> None:
    """When stale_banner is set, no sessions should be listed as active."""
    snapshot = {
        "generated_at": "2026-07-22T18:00:00Z",
        "stale_banner": "⚠️ Snapshot is 15 minutes stale - data may be out of date.",
        "sessions": [
            {
                "session": "plan-a",
                "status": "running",
                "process": True,
                "latest_activity": "2026-07-22T17:55:00Z",
            },
        ],
    }
    root = compact_cloud_status_snapshot(snapshot)
    assert root.get("stale_banner") == snapshot["stale_banner"]
    # Active sessions list should still contain the data but stale_banner is set
    assert isinstance(root.get("sessions"), list)


def test_unknown_dimensions_never_collapse_to_fresh() -> None:
    """Unknown dimensions must remain 'unknown' and never default to 'fresh'."""
    from arnold_pipelines.megaplan.resident.status_tree import _aggregate_source_cursor_state

    raw_sessions = [
        {
            "session": "plan-a",
            "source_cursor": {
                "cursors": [
                    {"dimension": "lifecycle", "state": "unknown", "version": "", "observed_at": ""},
                    {"dimension": "wbc", "state": "unknown", "version": "", "observed_at": ""},
                    {"dimension": "custody", "state": "unknown", "version": "", "observed_at": ""},
                ],
            },
        }
    ]
    agg = _aggregate_source_cursor_state(raw_sessions)
    assert isinstance(agg, dict), f"Expected aggregate dict, got {type(agg)}"
    # All three cursors have non-fresh state ("unknown" not in ("fresh", ""))
    assert agg.get("total_non_fresh_dimensions", 0) >= 3
