from __future__ import annotations

from arnold_pipelines.megaplan.resident.context_tree import build_context_root


def test_context_root_prioritizes_live_and_recent_reconciliation_attention() -> None:
    status_node = {
        "sessions": [
            {
                "session": "alphabetically-first-stale",
                "status": "attention",
                "latest_activity": "2026-07-07T00:00:00Z",
            },
            {
                "session": "workflow-boundary-contracts-corrective-20260710",
                "status": "attention",
                "latest_activity": "2026-07-14T11:53:13Z",
                "operator_next": "workspace missing or unreadable",
            },
            {
                "session": "repository-strategy-roadmap",
                "status": "attention",
                "latest_activity": "2026-07-14T17:32:20Z",
            },
            {
                "session": "repairing-chain",
                "status": "repairing",
                "repairing": True,
                "latest_activity": "2026-07-14T17:31:14Z",
            },
            {
                "session": "running-chain",
                "status": "running",
                "process": True,
                "latest_activity": "2026-07-14T17:43:38Z",
            },
        ]
    }

    context_root = build_context_root(
        status=status_node,
        agents=None,
        initiatives=None,
        todos=None,
        runtime=None,
        conversation=None,
    )

    assert [
        row["session"] for row in context_root["attention"]["sessions"]
    ] == [
        "running-chain",
        "repairing-chain",
        "repository-strategy-roadmap",
        "workflow-boundary-contracts-corrective-20260710",
    ]
    assert context_root["attention"]["sessions_omitted_count"] == 1
