from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import discord

from arnold_pipelines.megaplan.resident import currently_running as module
from arnold_pipelines.megaplan.resident import discord as discord_module
from arnold_pipelines.megaplan.resident.auth import AuthorizationDecision
from arnold_pipelines.megaplan.resident.currently_running import (
    CurrentlyRunningReport,
    collect_currently_running,
    discover_attention_sessions,
    discover_live_managed_agents,
    discover_recently_completed_managed_agents,
    discover_running_sessions,
    render_currently_running,
)
from arnold_pipelines.megaplan.resident.context_tree import build_context_root
from arnold_pipelines.megaplan.resident.discord import (
    DISCORD_APPLICATION_COMMANDS,
    DISCORD_MESSAGE_LIMIT,
    ResidentDiscordService,
    register_discord_application_commands,
    split_discord_message,
)


def test_discovers_running_and_repairing_sessions_and_only_live_managed_agents() -> None:
    status_node = {
        "sessions": [
            {"session": "active", "status": "running"},
            {"session": "repair", "status": "repairing"},
            {"session": "blocked", "status": "blocked"},
            {"session": "done", "status": "complete"},
        ]
    }
    managed = {
        "running": [
            {"run_id": "live", "status": "running", "live": True},
            {"run_id": "stale", "status": "running", "live": False},
            {"run_id": "terminal", "status": "completed", "live": True},
        ]
    }

    assert [row["session"] for row in discover_running_sessions(status_node)] == [
        "active",
        "repair",
    ]
    assert [row["run_id"] for row in discover_live_managed_agents(managed)] == ["live"]


def test_managed_agents_render_running_and_completed_sections_with_hour_boundary() -> None:
    snapshot = datetime(2026, 7, 14, 13, tzinfo=UTC)
    report = CurrentlyRunningReport(
        status_node={"generated_at": "2026-07-14T13:00:00Z", "sessions": []},
        managed_agents={
            "running": [
                {
                    "run_id": "live",
                    "description": "Live managed task",
                    "status": "running",
                    "live": True,
                }
            ],
            "recent": [
                {
                    "run_id": "at-boundary",
                    "description": "Boundary completion",
                    "status": "completed",
                    "finished_at": "2026-07-14T12:00:00Z",
                },
                {
                    "run_id": "recent-completion",
                    "description": "Recent completion",
                    "status": "completed",
                    "finished_at": "2026-07-14T12:59:59Z",
                },
                {
                    "run_id": "old-completion",
                    "description": "Old completion",
                    "status": "completed",
                    "finished_at": "2026-07-14T11:59:59Z",
                },
                {
                    "run_id": "failed",
                    "description": "Failed task",
                    "status": "failed",
                    "finished_at": "2026-07-14T12:59:59Z",
                },
                {
                    "run_id": "mismatched-terminal-outcome",
                    "description": "Mismatched terminal outcome",
                    "status": "completed",
                    "terminal_outcome": "failed",
                    "finished_at": "2026-07-14T12:59:59Z",
                },
            ],
        },
    )

    completed = discover_recently_completed_managed_agents(
        report.managed_agents, snapshot_at=snapshot
    )
    rendered = render_currently_running(report, now=snapshot)

    assert [row["run_id"] for row in completed] == [
        "at-boundary",
        "recent-completion",
    ]
    assert "### 🟢 Running · 1" in rendered
    assert "### ✅ Recently completed · 2" in rendered
    assert "Live managed task" in rendered
    assert "Boundary completion" in rendered
    assert "Recent completion" in rendered
    assert "Old completion" not in rendered
    assert "Failed task" not in rendered
    assert "Mismatched terminal outcome" not in rendered


def test_managed_agent_subsections_have_truthful_empty_states() -> None:
    rendered = render_currently_running(
        CurrentlyRunningReport(
            status_node={"generated_at": "2026-07-14T13:00:00Z", "sessions": []},
            managed_agents={"running": [], "recent": []},
        ),
        now=datetime(2026, 7, 14, 13, tzinfo=UTC),
    )

    assert "### 🟢 Running · 0\n_No live resident-managed agents._" in rendered
    assert (
        "### ✅ Recently completed · 0\n"
        "_No recently completed resident-managed agents._"
    ) in rendered


def test_managed_agents_nest_one_level_and_keep_unrelated_delegated_roots() -> None:
    rendered = render_currently_running(
        CurrentlyRunningReport(
            status_node={"sessions": []},
            managed_agents={
                "running": [
                    {
                        "run_id": "investigator",
                        "parent_run_id": "repair",
                        "description": "Investigate repair",
                        "status": "running",
                        "live": True,
                    },
                    {
                        "run_id": "delegated-root",
                        "description": "User delegated root",
                        "status": "running",
                        "live": True,
                        "aggregation": {
                            "role": "internal_contributor",
                            "delivery_owner_run_id": "repair",
                        },
                    },
                    {
                        "run_id": "repair",
                        "description": "Automatic repair",
                        "status": "running",
                        "live": True,
                    },
                ]
            },
        )
    )

    parent = "• **Automatic repair**\n  `running` · agent `repair`"
    child = "  ↳ **Investigate repair**\n    `running` · agent `investigator`"
    unrelated = "• **User delegated root**\n  `running` · agent `delegated-root`"
    assert parent in rendered
    assert child in rendered
    assert unrelated in rendered
    assert rendered.index(parent) < rendered.index(child) < rendered.index(unrelated)


def test_managed_agents_render_multiple_ancestry_levels() -> None:
    rendered = render_currently_running(
        CurrentlyRunningReport(
            status_node={"sessions": []},
            managed_agents={
                "running": [
                    {
                        "run_id": "retry",
                        "parent_run_id": "investigator",
                        "description": "Repair retry",
                        "status": "running",
                        "live": True,
                    },
                    {
                        "run_id": "investigator",
                        "parent_run_id": "repair",
                        "description": "Investigator",
                        "status": "running",
                        "live": True,
                    },
                    {
                        "run_id": "repair",
                        "description": "Repair root",
                        "status": "running",
                        "live": True,
                    },
                ]
            },
        )
    )

    assert "• **Repair root**" in rendered
    assert "  ↳ **Investigator**\n    `running`" in rendered
    assert "    ↳ **Repair retry**\n      `running`" in rendered


def test_recently_completed_agents_nest_beneath_completed_parent() -> None:
    snapshot = datetime(2026, 7, 15, 12, tzinfo=UTC)
    rendered = render_currently_running(
        CurrentlyRunningReport(
            status_node={"generated_at": snapshot.isoformat(), "sessions": []},
            managed_agents={
                "running": [],
                "recent": [
                    {
                        "run_id": "completed-child",
                        "parent_run_id": "completed-parent",
                        "description": "Completed investigator",
                        "status": "completed",
                        "finished_at": "2026-07-15T11:59:00Z",
                    },
                    {
                        "run_id": "completed-parent",
                        "description": "Completed repair",
                        "status": "completed",
                        "finished_at": "2026-07-15T11:58:00Z",
                    },
                ],
            },
        ),
        now=snapshot,
    )

    parent = "• **Completed repair**\n  `completed` · agent `completed-parent`"
    child = (
        "  ↳ **Completed investigator**\n"
        "    `completed` · agent `completed-child`"
    )
    assert rendered.index(parent) < rendered.index(child)


def test_mixed_live_completed_ancestry_preserves_section_semantics() -> None:
    snapshot = datetime(2026, 7, 15, 12, tzinfo=UTC)
    rendered = render_currently_running(
        CurrentlyRunningReport(
            status_node={"generated_at": snapshot.isoformat(), "sessions": []},
            managed_agents={
                "running": [
                    {
                        "run_id": "live-parent",
                        "description": "Live parent",
                        "status": "running",
                        "live": True,
                    }
                ],
                "recent": [
                    {
                        "run_id": "completed-child",
                        "parent_run_id": "live-parent",
                        "description": "Completed child",
                        "status": "completed",
                        "terminal_outcome": "completed",
                        "started_at": "2026-07-15T11:50:00Z",
                        "finished_at": "2026-07-15T11:55:00Z",
                        "completion_delivery": {"status": "delivered"},
                    }
                ],
            },
        ),
        now=snapshot,
    )

    running_heading = rendered.index("### 🟢 Running · 1")
    completed_heading = rendered.index("### ✅ Recently completed · 1")
    child = rendered.index("• **Completed child**")
    assert running_heading < rendered.index("• **Live parent**") < completed_heading
    assert completed_heading < child
    assert "`completed` · 5m elapsed · delivery delivered" in rendered
    assert "parent 'live-parent' is in Running" in rendered


def test_missing_parent_and_bad_provenance_remain_visible_as_roots() -> None:
    rows = [
        {
            "run_id": "orphan",
            "parent_run_id": "expired-parent",
            "description": "Bounded orphan",
            "status": "running",
            "live": True,
        },
        {
            "run_id": "malformed",
            "parent_run_id": 42,
            "description": "Malformed ancestry",
            "status": "running",
            "live": True,
        },
    ]
    rendered = render_currently_running(
        CurrentlyRunningReport(
            status_node={"sessions": []}, managed_agents={"running": rows}
        )
    )

    assert "• **Bounded orphan**" in rendered
    assert "parent 'expired-parent' is outside this status window" in rendered
    assert "• **Malformed ancestry**" in rendered
    assert "invalid parent provenance" in rendered


def test_cycles_and_duplicate_parent_ids_are_safe_and_deterministic() -> None:
    rows = [
        {"run_id": "a", "parent_run_id": "b", "status": "running", "live": True},
        {"run_id": "b", "parent_run_id": "a", "status": "running", "live": True},
        {"run_id": "dup", "status": "running", "live": True},
        {"run_id": "dup", "status": "running", "live": True},
        {
            "run_id": "ambiguous-child",
            "parent_run_id": "dup",
            "status": "running",
            "live": True,
        },
    ]

    first = render_currently_running(
        CurrentlyRunningReport(
            status_node={"sessions": []}, managed_agents={"running": rows}
        )
    )
    second = render_currently_running(
        CurrentlyRunningReport(
            status_node={"sessions": []}, managed_agents={"running": rows}
        )
    )

    assert first == second
    assert first.count("invalid parent cycle; shown as a root") == 2
    assert first.count("duplicate run ID; hierarchy unavailable") == 2
    assert "parent 'dup' is ambiguous" in first
    assert first.count("• **Resident-managed task**") == len(rows)


def test_managed_agent_bounded_inventory_omissions_are_accounted_for() -> None:
    snapshot = datetime(2026, 7, 15, 12, tzinfo=UTC)
    rendered = render_currently_running(
        CurrentlyRunningReport(
            status_node={"generated_at": snapshot.isoformat(), "sessions": []},
            managed_agents={
                "running": [],
                "recent": [
                    {
                        "run_id": "recent",
                        "description": "Visible completion",
                        "status": "completed",
                        "finished_at": "2026-07-15T11:59:00Z",
                    }
                ],
                "recent_omitted_count": 3,
            },
        ),
        now=snapshot,
    )

    assert "• **Visible completion**" in rendered
    assert (
        "…3 additional terminal managed runs omitted by the bounded inventory"
        in rendered
    )


def test_render_preserves_canonical_epic_percent_and_prefers_display_state() -> None:
    report = CurrentlyRunningReport(
        status_node={
            "sessions": [
                {
                    "session": "custody-control",
                    "display_name": "Custody control plane",
                    "status": "running",
                    "current_plan": "m7-runtime-adoption",
                    "progress": {
                        "percent": 42.5,
                        "epic_delta_1h": 2.5,
                        "plan_percent": 73,
                        "display_state": "executing",
                        "plan_state": "finalized",
                    },
                }
            ]
        },
        managed_agents={"running": []},
    )

    rendered = render_currently_running(report)

    assert "## ⛓️ Epics & chains · 1 active" in rendered
    assert "### 🟢 Running · 1" in rendered
    assert "`Custody control plane` · `m7-runtime-adoption`" in rendered
    assert "`executing`" in rendered
    assert "42.5% overall" in rendered
    assert "+2.5 pp in the past hour" in rendered
    assert "73% plan bookkeeping (not acceptance)" in rendered
    assert "finalized" not in rendered


def test_render_labels_full_task_bookkeeping_during_review_rework() -> None:
    rendered = render_currently_running(
        CurrentlyRunningReport(
            status_node={
                "sessions": [
                    {
                        "session": "custody-control",
                        "status": "running",
                        "progress": {
                            "percent": 20,
                            "plan_percent": 100,
                            "plan_percent_basis": (
                                "plan lifecycle and recorded task-weight bookkeeping; "
                                "not implementation acceptance"
                            ),
                            "display_state": "reworking",
                            "plan_state": "finalized",
                        },
                    }
                ]
            },
            managed_agents={"running": []},
        )
    )

    assert "`reworking` · 20% overall · 100% plan bookkeeping (not acceptance)" in rendered
    assert "finalized" not in rendered
    assert "`completed`" not in rendered


def test_render_shows_truthful_hourly_percentage_point_deltas_only_with_telemetry() -> None:
    rendered = render_currently_running(
        CurrentlyRunningReport(
            status_node={
                "sessions": [
                    {"session": "positive", "status": "running", "progress": {"percent": 50, "epic_delta_1h": 4}},
                    {"session": "zero", "status": "running", "progress": {"percent": 50, "epic_delta_1h": 0}},
                    {"session": "negative", "status": "running", "progress": {"percent": 50, "epic_delta_1h": -3}},
                    {"session": "no-history", "status": "running", "progress": {"percent": 50, "epic_delta_1h": None}},
                ]
            },
            managed_agents={"running": []},
        )
    )

    assert "`positive`\n  `running` · 50% overall · +4 pp in the past hour" in rendered
    assert "`zero`\n  `running` · 50% overall · +0 pp in the past hour" in rendered
    assert "`negative`\n  `running` · 50% overall · -3 pp in the past hour" in rendered
    assert "`no-history`\n  `running` · 50% overall\n" in rendered


def test_active_executing_attention_remains_listed_with_overlay_visible() -> None:
    status_node = {
        "sessions": [
            {
                "session": "custody-control-plane-20260714",
                "status": "attention",
                "process": True,
                "active_phase": "execute",
                "operator_next": "chain custody mismatch",
                "progress": {
                    "percent": 33,
                    "display_state": "executing",
                    "plan_state": "finalized",
                },
            }
        ]
    }

    assert [row["session"] for row in discover_running_sessions(status_node)] == [
        "custody-control-plane-20260714"
    ]
    rendered = render_currently_running(
        CurrentlyRunningReport(status_node=status_node, managed_agents={"running": []})
    )

    assert "## ⛓️ Epics & chains · 1 active" in rendered
    assert "`executing`" in rendered
    assert "⚠️ attention" in rendered
    assert "chain custody mismatch" in rendered
    assert "finalized" not in rendered


def test_non_active_attention_stays_on_attention_surface_not_running_list() -> None:
    attention_session = {
        "session": "stopped-chain",
        "status": "attention",
        "process": False,
        "should_run": True,
        "latest_activity": "2026-07-14T17:59:59Z",
        "operator_next": "workspace missing or unreadable",
        "progress": {"display_state": "blocked", "plan_state": "blocked"},
    }
    status_node = {
        "generated_at": "2026-07-14T18:00:00Z",
        "sessions": [attention_session],
        "session_count": 1,
    }

    assert discover_running_sessions(status_node) == []
    context_root = build_context_root(
        status=status_node,
        agents=None,
        initiatives=None,
        todos=None,
        runtime=None,
        conversation=None,
    )
    assert context_root["attention"]["sessions"] == [
        {
            "session": "stopped-chain",
            "status": "attention",
            "latest_activity": "2026-07-14T17:59:59Z",
            "operator_next": "workspace missing or unreadable",
            "progress": {"display_state": "blocked", "plan_state": "blocked"},
        }
    ]


def test_needs_attention_only_shows_authoritative_activity_in_preceding_twelve_hours() -> None:
    status_node = {
        "generated_at": "2026-07-14T18:00:00Z",
        "sessions": [
            {
                "session": "just-inside",
                "status": "attention",
                "process": False,
                "repairing": False,
                "latest_activity": "2026-07-14T06:00:01Z",
            },
            {
                "session": "exact-boundary",
                "status": "blocked",
                "process": False,
                "latest_activity": "2026-07-14T06:00:00Z",
            },
            {
                "session": "just-outside",
                "status": "attention",
                "process": False,
                "latest_activity": "2026-07-14T05:59:59Z",
            },
            {"session": "missing-activity", "status": "attention", "process": False},
            {
                "session": "invalid-activity",
                "status": "blocked",
                "process": False,
                "latest_activity": "not-a-timestamp",
            },
        ]
    }

    assert discover_running_sessions(status_node) == []
    assert [row["session"] for row in discover_attention_sessions(status_node)] == [
        "just-inside",
        "exact-boundary",
    ]
    rendered = render_currently_running(
        CurrentlyRunningReport(status_node=status_node, managed_agents={"running": []})
    )

    assert "### ⚠️ Needs attention · 2" in rendered
    assert "`just-inside`" in rendered
    assert "`exact-boundary`" in rendered
    for session in ("just-outside", "missing-activity", "invalid-activity"):
        assert f"**{session}**" not in rendered


def test_recently_active_installed_session_remains_visible_as_attention() -> None:
    status_node = {
        "generated_at": "2026-07-14T18:00:00Z",
        "sessions": [
            {
                "session": "custody-control-plane-20260714",
                "display_name": "Custody control plane",
                "run_kind": "installed",
                "status": "attention",
                "process": False,
                "repairing": False,
                "latest_activity": "2026-07-14T17:31:31Z",
                "operator_next": "workspace missing or unreadable",
                "progress": {"display_state": "executed", "percent": 0},
            }
        ],
    }

    rendered = render_currently_running(
        CurrentlyRunningReport(status_node=status_node, managed_agents={"running": []})
    )

    assert "### ⚠️ Needs attention · 1" in rendered
    assert "`Custody control plane`" in rendered
    assert "`executed` · 0% overall · ⚠️ attention · workspace missing or unreadable" in rendered


def test_active_execute_phase_is_executing_when_display_state_is_absent() -> None:
    report = CurrentlyRunningReport(
        status_node={
            "sessions": [
                {
                    "session": "epic",
                    "status": "running",
                    "progress": {
                        "active_phase": {"phase": "execute"},
                        "plan_state": "finalized",
                    },
                }
            ]
        },
        managed_agents={"running": []},
    )

    rendered = render_currently_running(report)

    assert "`epic`" in rendered
    assert "`executing` · overall progress unavailable" in rendered


def test_plan_state_is_used_only_when_display_state_and_execute_are_absent() -> None:
    rendered = render_currently_running(
        CurrentlyRunningReport(
            status_node={
                "sessions": [
                    {
                        "session": "blocked-plan",
                        "status": "running",
                        "progress": {"plan_state": "blocked"},
                    }
                ]
            },
            managed_agents={"running": []},
        )
    )

    assert "`blocked-plan`" in rendered
    assert "`blocked` · overall progress unavailable · chain running" in rendered


def test_render_uses_epics_parent_and_nonempty_h3_status_subsections() -> None:
    rendered = render_currently_running(
        CurrentlyRunningReport(
            status_node={
                "sessions": [
                    {
                        "session": "status-refresh",
                        "status": "running",
                        "progress": {"display_state": "executing", "percent": 25},
                    }
                ]
            },
            managed_agents={
                "running": [
                    {
                        "run_id": "status-agent",
                        "description": "Refresh resident status",
                        "status": "running",
                        "live": True,
                    }
                ]
            },
        )
    )

    assert rendered == (
        "# Currently running\n"
        "## ⛓️ Epics & chains · 1 active\n"
        "### 🟢 Running · 1\n"
        "• `status-refresh`\n"
        "  `executing` · 25% overall · chain running\n"
        "\n"
        "## 🤖 Managed agents · 1 live · 0 recently completed\n"
        "### 🟢 Running · 1\n"
        "• **Refresh resident status**\n"
        "  `running` · agent `status-agent`\n"
        "### ✅ Recently completed · 0\n"
        "_No recently completed resident-managed agents._"
    )


def test_epics_status_groups_are_nonempty_subsections_without_trailing_dashes() -> None:
    rendered = render_currently_running(
        CurrentlyRunningReport(
            status_node={
                "generated_at": "2026-07-14T18:00:00Z",
                "sessions": [
                    {"session": "running-chain", "status": "running"},
                    {
                        "session": "blocked-chain",
                        "status": "attention",
                        "latest_activity": "2026-07-14T17:59:00Z",
                    },
                ],
                "recently_completed": [
                    {"session": "done-chain", "status": "completed"},
                ],
            },
            managed_agents={"running": []},
        )
    )

    assert "## ⛓️ Epics & chains · 1 active" in rendered
    assert "### 🟢 Running · 1" in rendered
    assert "### ⚠️ Needs attention · 1" in rendered
    assert "### ✅ Recently completed · 1 shown" in rendered
    assert rendered.index("## ⛓️ Epics & chains") < rendered.index("### 🟢 Running")
    assert rendered.index("### 🟢 Running") < rendered.index("### ⚠️ Needs attention")
    assert rendered.index("### ⚠️ Needs attention") < rendered.index("### ✅ Recently completed")
    assert "\n## ⚠️ Needs attention" not in rendered
    assert "\n## Recently completed" not in rendered
    assert not any(
        line.endswith("—")
        for line in rendered.splitlines()
        if line.startswith(("##", "###"))
    )


def test_render_includes_recent_completed_strategy_chain_with_terminal_evidence() -> None:
    rendered = render_currently_running(
        CurrentlyRunningReport(
            status_node={
                "sessions": [{"session": "live-work", "status": "running"}],
                "recently_completed": [
                    {
                        "session": "repository-strategy-roadmap",
                        "display_name": "Repository strategy roadmap",
                        "status": "complete",
                        "latest_activity": "2026-07-14T17:18:48Z",
                        "progress": {"completed_count": 5, "milestone_count": 5},
                    }
                ],
            },
            managed_agents={"running": []},
        )
    )

    assert "### ✅ Recently completed · 1 shown" in rendered
    assert "**Repository strategy roadmap**" in rendered
    assert "`completed` · 5/5 milestones" in rendered
    assert "2026-07-14 17:18:48 UTC (UTC+00:00)" in rendered
    assert "## ⛓️ Epics & chains · 1 active" in rendered
    assert "## 🤖 Managed agents · 0 live" in rendered


def test_render_keeps_terminal_plan_without_chain_completion_in_attention() -> None:
    rendered = render_currently_running(
        CurrentlyRunningReport(
            status_node={
                "generated_at": "2026-07-14T18:00:00Z",
                "sessions": [
                    {
                        "session": "repository-strategy-roadmap",
                        "status": "attention",
                        "display_state": "done",
                        "chain_complete": False,
                        "latest_activity": "2026-07-14T17:32:20Z",
                        "operator_next": "terminal plan requires chain reconciliation",
                        "progress": {
                            "percent": 100,
                            "plan_percent": 100,
                            "display_state": "done",
                            "completed_count": 4,
                            "milestone_count": 5,
                        },
                    }
                ],
                "recently_completed": [],
            },
            managed_agents={"running": []},
        )
    )

    assert "### ⚠️ Needs attention · 1" in rendered
    assert "`repository-strategy-roadmap`" in rendered
    assert (
        "`done` · 100% overall · 100% plan bookkeeping (not acceptance) · ⚠️ attention"
        in rendered
    )
    assert "terminal plan requires chain reconciliation" in rendered
    assert "Recently completed · 1 shown" not in rendered
    assert "`completed`" not in rendered


def test_recent_completed_is_bounded_and_rejects_nonterminal_rows() -> None:
    rows = [
        {
            "session": f"completed-{index}",
            "status": "complete",
            "latest_activity": f"2026-07-14T17:{index:02}:00Z",
        }
        for index in range(7)
    ] + [
        {"session": "paused", "status": "paused"},
        {"session": "blocked", "status": "blocked"},
        {"session": "failed", "status": "failed"},
        {"session": "inactive", "status": "attention"},
    ]
    rendered = render_currently_running(
        CurrentlyRunningReport(
            status_node={
                "sessions": [],
                "recently_completed": rows,
                "recently_completed_omitted_count": 2,
            },
            managed_agents={"running": []},
        )
    )

    assert "### ✅ Recently completed · 5 shown" in rendered
    assert "**completed-4**" in rendered
    assert "completed-5" not in rendered
    assert "…2 older completed chains omitted" in rendered
    for name in ("paused", "blocked", "failed", "inactive"):
        assert f"**{name}**" not in rendered


def test_agents_render_lifecycle_duration_and_persisted_token_usage() -> None:
    report = CurrentlyRunningReport(
        status_node={"sessions": []},
        managed_agents={
            "running": [
                {
                    "run_id": "subagent-plain",
                    "status": "running",
                    "live": True,
                    "started_at": "2026-07-14T12:00:00Z",
                    "usage": {"total_tokens": 12_345},
                },
                {
                    "run_id": "subagent-summary",
                    "description": "Review status truth",
                    "status": "launching",
                    "live": True,
                    "started_at": "2026-07-14T12:59:30+00:00",
                },
            ]
        },
    )

    rendered = render_currently_running(
        report, now=datetime(2026, 7, 14, 13, 2, tzinfo=UTC)
    )

    assert (
        "**Resident-managed task**\n"
        "  `running` · 1h 2m elapsed · 12.3k tokens used · agent `subagent-plain`"
    ) in rendered
    assert (
        "**Review status truth**\n"
        "  `launching` · 2m elapsed · agent `subagent-summary`"
    ) in rendered
    assert "Progress unavailable" not in rendered
    assert "tokens used" in rendered


def test_agent_telemetry_omits_missing_or_invalid_usage_and_bad_timestamps() -> None:
    report = CurrentlyRunningReport(
        status_node={"sessions": []},
        managed_agents={
            "running": [
                {
                    "run_id": "no-usage",
                    "status": "running",
                    "live": True,
                    "started_at": "not-a-timestamp",
                },
                {
                    "run_id": "bad-usage",
                    "status": "running",
                    "live": True,
                    "started_at": "2026-07-14T12:00:00Z",
                    "usage": {"total_tokens": -1},
                },
            ]
        },
    )

    rendered = render_currently_running(
        report, now=datetime(2026, 7, 14, 12, 1, tzinfo=UTC)
    )

    assert "Progress unavailable" not in rendered
    assert "tokens used" not in rendered
    assert "**Resident-managed task**\n  `running` · agent `no-usage`" in rendered
    assert "`running` · 1m elapsed · agent `bad-usage`" in rendered


def test_agent_elapsed_uses_finished_timestamp_and_rejects_negative_duration() -> None:
    completed = {
        "run_id": "completed",
        "status": "completed",
        "started_at": "2026-07-14T12:00:00Z",
        "finished_at": "2026-07-14T12:05:45Z",
    }
    future_start = {
        "run_id": "future",
        "status": "running",
        "started_at": "2026-07-14T13:00:00Z",
    }
    live_with_stale_finish = {
        "run_id": "still-live",
        "status": "running",
        "started_at": "2026-07-14T12:00:00Z",
        "finished_at": "2026-07-14T12:01:00Z",
    }

    assert module._agent_elapsed(
        completed, now=datetime(2026, 7, 14, 14, tzinfo=UTC)
    ) == "5m elapsed"
    assert module._agent_elapsed(
        future_start, now=datetime(2026, 7, 14, 12, tzinfo=UTC)
    ) is None
    assert module._agent_elapsed(
        live_with_stale_finish, now=datetime(2026, 7, 14, 12, 3, tzinfo=UTC)
    ) == "3m elapsed"


def test_stale_banner_is_verbatim_first_line_and_frozen_progress_is_suppressed() -> None:
    banner = "⚠️ Canonical cloud status is stale; frozen progress has been withheld."
    report = CurrentlyRunningReport(
        status_node={
            "stale_banner": banner,
            "generated_at": "2026-07-14T16:30:45Z",
            "sessions": [
                {
                    "session": "frozen",
                    "status": "running",
                    "progress": {"percent": 99, "plan_percent": 88},
                }
            ],
        },
        managed_agents={
            "running": [
                {
                    "run_id": "live-agent",
                    "description": "Verify stale status behavior",
                    "status": "running",
                    "live": True,
                }
            ]
        },
    )

    rendered = render_currently_running(report)

    assert rendered.splitlines()[0] == banner
    assert "Snapshot generated 2026-07-14 16:30:45 UTC (UTC+00:00)" in rendered
    assert "99%" not in rendered
    assert "88%" not in rendered
    assert "Progress unavailable — the canonical status snapshot is stale" in rendered
    assert (
        "**Verify stale status behavior**\n"
        "  `running` · agent `live-agent`"
    ) in rendered


def test_degraded_status_is_labeled_without_hiding_available_canonical_items() -> None:
    report = CurrentlyRunningReport(
        status_node={
            "degraded": {"reasons": ["watchdog report missing"]},
            "sessions": [
                {
                    "session": "degraded-epic",
                    "status": "running",
                    "progress": {"percent": 12, "display_state": "planned"},
                }
            ],
        },
        managed_agents={"running": []},
    )

    rendered = render_currently_running(report)

    assert "Canonical epic/chain status is degraded: watchdog report missing." in rendered
    assert "`degraded-epic`\n  `planned` · 12% overall" in rendered


def test_collection_uses_typed_bounded_status_tool_and_managed_agent_inventory(
    monkeypatch, tmp_path
) -> None:
    calls: list[object] = []

    class InputModel:
        def __init__(self, **values):
            self.__dict__.update(values)

    def status_handler(payload):
        calls.append(payload)
        return SimpleNamespace(
            ok=True,
            data={"node": {"node_id": "root", "sessions": []}},
        )

    registration = SimpleNamespace(input_model=InputModel, handler=status_handler)
    registry = SimpleNamespace(
        get=lambda name: registration if name == "read_cloud_status_node" else None
    )
    runtime = SimpleNamespace(
        profile=SimpleNamespace(tools=lambda: registry),
        project_root=tmp_path,
    )
    monkeypatch.setattr(
        module,
        "list_managed_resident_agents",
        lambda **kwargs: {
            "running": [],
            "project_root_seen": str(kwargs["project_root"]),
        },
    )

    report = asyncio.run(collect_currently_running(runtime))

    assert report.status_node == {"node_id": "root", "sessions": []}
    assert report.managed_agents["project_root_seen"] == str(tmp_path)
    assert len(calls) == 1
    assert calls[0].node_id == "root"
    assert calls[0].limit == 25


def test_collection_replaces_opaque_agent_label_from_exact_inbound_source(
    monkeypatch, tmp_path
) -> None:
    store_root = tmp_path / "resident-store"
    messages = store_root / "messages"
    messages.mkdir(parents=True)
    (messages / "msg_source.json").write_text(
        json.dumps(
            {
                "id": "msg_source",
                "direction": "inbound",
                "conversation_id": "conversation-1",
                "discord_message_id": "12345",
                "content": "No, I meant this!",
                "discord_reply_provenance": {
                    "ancestors": [
                        {"content": "Megaplan needs human review — custody control plane"}
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MEGAPLAN_RESIDENT_STORE_ROOT", str(store_root))

    class InputModel:
        def __init__(self, **values):
            self.__dict__.update(values)

    registration = SimpleNamespace(
        input_model=InputModel,
        handler=lambda _payload: SimpleNamespace(
            ok=True, data={"node": {"node_id": "root", "sessions": []}}
        ),
    )
    runtime = SimpleNamespace(
        profile=SimpleNamespace(tools=lambda: SimpleNamespace(get=lambda _name: registration)),
        project_root=tmp_path,
    )
    monkeypatch.setattr(
        module,
        "list_managed_resident_agents",
        lambda **_kwargs: {
            "running": [
                {
                    "run_id": "subagent-20260714-002539-4f329fbe",
                    "status": "running",
                    "live": True,
                    "description": "Handle the delegated resident request.",
                    "project_dir": str(tmp_path),
                    "launch_provenance": {
                        "source_record_id": "msg_source",
                        "resident_conversation_id": "conversation-1",
                        "discord_message_id": "12345",
                    },
                }
            ]
        },
    )

    report = asyncio.run(collect_currently_running(runtime))
    rendered = render_currently_running(report)

    assert "Handle the delegated resident request" not in rendered
    assert (
        "**No, I meant this! — re: Megaplan needs human review "
        "— custody control plane**"
    ) in rendered
    assert "agent `002539-4f329fbe`" in rendered


def test_currently_running_command_is_registered_with_discord_tree() -> None:
    class FakeTree:
        def __init__(self) -> None:
            self.commands: dict[str, tuple[str, object]] = {}

        def command(self, *, name: str, description: str):
            def decorate(callback):
                self.commands[name] = (description, callback)
                return callback

            return decorate

    class Service:
        async def handle_currently_running_interaction(self, _interaction):
            return None

        async def handle_restart_resident_interaction(self, _interaction):
            return None

        async def handle_dropped_threads_interaction(self, _interaction, *, lookback=None):
            return None

    tree = FakeTree()

    registered = register_discord_application_commands(tree, Service())

    assert registered == ("whats-cooking", "restart-resident", "dropped-threads")
    assert set(tree.commands) == {"whats-cooking", "restart-resident", "dropped-threads"}
    assert tree.commands["whats-cooking"][0].startswith("Show running Megaplan")
    assert [command.name for command in DISCORD_APPLICATION_COMMANDS] == [
        "whats-cooking",
        "restart-resident",
        "dropped-threads",
    ]


def test_real_discord_command_callback_authorizes_collects_and_replies(
    monkeypatch,
) -> None:
    subjects = []

    class Authorizer:
        def authorize_inbound(self, subject):
            subjects.append(subject)
            return AuthorizationDecision(True)

    class Response:
        def __init__(self):
            self.deferred = []

        async def defer(self, **kwargs):
            self.deferred.append(kwargs)

    class Followup:
        def __init__(self):
            self.messages = []

        async def send(self, content, **kwargs):
            self.messages.append((content, kwargs))

    async def fake_collect(runtime):
        assert runtime.authorizer.__class__ is Authorizer
        return CurrentlyRunningReport(
            status_node={"sessions": []}, managed_agents={"running": []}
        )

    monkeypatch.setattr(discord_module, "collect_currently_running", fake_collect)
    service = object.__new__(ResidentDiscordService)
    service.runtime = SimpleNamespace(authorizer=Authorizer())
    client = discord.Client(intents=discord.Intents.none())
    tree = discord.app_commands.CommandTree(client)
    register_discord_application_commands(tree, service)
    command = tree.get_command("whats-cooking")
    interaction = SimpleNamespace(
        user=SimpleNamespace(id=42),
        guild_id=None,
        channel=None,
        channel_id=99,
        response=Response(),
        followup=Followup(),
    )

    asyncio.run(command.callback(interaction))

    assert [(subject.user_id, subject.channel_id) for subject in subjects] == [
        ("42", "99")
    ]
    assert interaction.response.deferred == [{"thinking": True, "ephemeral": True}]
    assert len(interaction.followup.messages) == 1
    content, kwargs = interaction.followup.messages[0]
    assert content.startswith("# Currently running\n")
    assert kwargs == {"ephemeral": True}


def test_currently_running_error_response_is_ephemeral(monkeypatch) -> None:
    class Response:
        def __init__(self):
            self.deferred = []

        async def defer(self, **kwargs):
            self.deferred.append(kwargs)

    class Followup:
        def __init__(self):
            self.messages = []

        async def send(self, content, **kwargs):
            self.messages.append((content, kwargs))

    async def failed_collect(_runtime):
        raise RuntimeError("status store unavailable")

    monkeypatch.setattr(discord_module, "collect_currently_running", failed_collect)
    service = object.__new__(ResidentDiscordService)
    service.runtime = SimpleNamespace(
        authorizer=SimpleNamespace(
            authorize_inbound=lambda _subject: AuthorizationDecision(True)
        )
    )
    interaction = SimpleNamespace(
        user=SimpleNamespace(id=42),
        guild_id=None,
        channel=None,
        channel_id=99,
        response=Response(),
        followup=Followup(),
    )

    asyncio.run(service.handle_currently_running_interaction(interaction))

    assert interaction.response.deferred == [{"thinking": True, "ephemeral": True}]
    assert interaction.followup.messages == [
        (
            "# Currently running\n"
            "⚠️ Canonical status is temporarily unavailable; no running-state claims were made.",
            {"ephemeral": True},
        )
    ]


def test_currently_running_unauthorized_response_is_ephemeral() -> None:
    class Response:
        def __init__(self):
            self.messages = []

        async def send_message(self, content, **kwargs):
            self.messages.append((content, kwargs))

    service = object.__new__(ResidentDiscordService)
    service.runtime = SimpleNamespace(
        authorizer=SimpleNamespace(
            authorize_inbound=lambda _subject: AuthorizationDecision(False)
        )
    )
    interaction = SimpleNamespace(
        user=SimpleNamespace(id=42),
        guild_id=None,
        channel=None,
        channel_id=99,
        response=Response(),
    )

    asyncio.run(service.handle_currently_running_interaction(interaction))

    assert interaction.response.messages == [
        ("This command is not authorized in this Discord context.", {"ephemeral": True})
    ]


def test_long_lists_include_every_live_agent_and_chunk_safely() -> None:
    agents = [
        {
            "run_id": f"run-{index}",
            "description": f"Resident task {index} " + ("x" * 160),
            "status": "running",
            "live": True,
        }
        for index in range(40)
    ]
    rendered = render_currently_running(
        CurrentlyRunningReport(
            status_node={"sessions": []},
            managed_agents={"running": agents},
        )
    )

    chunks = split_discord_message(rendered)

    assert "## 🤖 Managed agents · 40 live" in rendered
    assert "Progress unavailable" not in rendered
    assert rendered.count(" · agent `run-") == 40
    assert "Resident task 39" in rendered
    assert len(chunks) > 1
    assert all(0 < len(chunk) <= DISCORD_MESSAGE_LIMIT for chunk in chunks)


def test_snapshot_time_is_displayed_in_utc_with_date_time_and_offset() -> None:
    rendered = render_currently_running(
        CurrentlyRunningReport(
            status_node={"generated_at": "2026-07-14T16:30:45Z", "sessions": []},
            managed_agents={"running": []},
        )
    )

    assert "Snapshot generated 2026-07-14 16:30:45 UTC (UTC+00:00)" in rendered


def test_repairing_chain_remains_distinct_from_its_progress_display_state() -> None:
    rendered = render_currently_running(
        CurrentlyRunningReport(
            status_node={
                "sessions": [
                    {
                        "session": "recovering-epic",
                        "status": "repairing",
                        "progress": {"display_state": "executing", "percent": 25},
                    }
                ]
            },
            managed_agents={"running": []},
        )
    )

    assert "`executing` · 25% overall · chain repairing" in rendered


def test_session_and_plan_names_are_individually_copyable_inline_code() -> None:
    rendered = render_currently_running(
        CurrentlyRunningReport(
            status_node={
                "sessions": [
                    {
                        "display_name": "Epic `one`",
                        "status": "running",
                        "current_plan": "plan `two`",
                    }
                ]
            },
            managed_agents={"running": []},
        )
    )

    assert "• `Epic 'one'` · `plan 'two'`" in rendered


def test_repairing_signal_overrides_stale_failed_state_but_not_genuine_failure() -> None:
    repairing = {
        "session": "repairing-epic",
        "status": "failed",
        "repairing": True,
        "progress": {"plan_state": "failed"},
    }
    failed = {
        "session": "failed-epic",
        "status": "failed",
        "progress": {"plan_state": "failed"},
    }

    rendered = render_currently_running(
        CurrentlyRunningReport(
            status_node={"sessions": [repairing]}, managed_agents={"running": []}
        )
    )

    assert discover_running_sessions({"sessions": [repairing, failed]}) == [repairing]
    assert "`repairing` · overall progress unavailable" in rendered
    assert "failed" not in rendered
    assert "`failed` · overall progress unavailable" in module._render_session(failed)
