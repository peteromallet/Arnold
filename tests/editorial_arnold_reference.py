"""Arnold Sprint 4 editorial parity checklist.

Audited reference files only:
- arnold-source/agent_kit/gating.py
- arnold-source/agent_kit/tools/editorial.py
- arnold-source/agent_kit/tools/editorial_reads.py
- arnold-source/agent_kit/sprints.py
"""

ARNOLD_EDITORIAL_PARITY_CHECKLIST = {
    "lifecycle_transitions": (
        "same-state transitions are allowed",
        "shaping -> sprinting requires a substantial body, Goal, Deliverable, and mostly resolved checklist",
        "sprinting -> planned requires all checklist items terminal, at least one sprint, locked sprint statuses, PM handoff fidelity, and lockdown phrase scan",
        "unsupported transitions are blocked with unsupported_transition",
        "forced transitions preserve bypassed blockers and emit forced handoff history",
    ),
    "prerequisites": (
        "body length must be more than 500 characters for both accepted advances",
        "Goal and Deliverable are required for shaping -> sprinting and sprinting -> planned",
        "Key Decisions is additionally required for PM handoff fidelity before planned",
        "planned handoff requires every sprint to have at least one PM-level item",
    ),
    "lockdown": (
        "unresolved decision phrases are rejected outside Open Questions",
        "lockdown scan ignores fenced code blocks",
        "lockdown blocker reports phrase, section, and line number",
    ),
    "body_validation": (
        "only one body operation may be applied at a time",
        "supported operations are new_content, sections, append, add_section/add_sections, remove_sections, rename_section, and reorder",
        "writes validate parsed body shape before persistence",
        "expected_diff mismatch blocks the write and returns the actual diff",
        "section errors surface SectionNotFound, SectionExists, or InvalidPosition",
    ),
    "checklist_behavior": (
        "update, add, delete, and replace operations are supported",
        "checklist changes are persisted inside the edit transaction",
        "checklist_change events preserve prior item snapshots",
        "terminal gate statuses are done, skipped, and superseded",
    ),
    "sprint_queue_behavior": (
        "replace and upsert validate sprint number, name, goal, status, target weeks, and at least one item",
        "valid sprint statuses are proposed, queued, pending, and done",
        "lock_in rejects duplicate queued numbers, unknown numbers, and queued/pending overlap",
        "default lock_in queues the first sprint and pends the rest",
        "queue and reorder normalize queued positions to a gapless sequence",
        "pending sprints require or receive a pending reason",
    ),
    "hot_context_shape": (
        "recent_messages reads from store.load_hot_context(epic_id)['recent_messages']",
        "recent_messages caps requested output at ten and returns requested_n, returned_n, max_available, and recent_messages",
        "get_self_understanding joins epic, open checklist, events, images, and second-opinion events through Store reads",
    ),
}


def test_arnold_editorial_parity_checklist_covers_sprint_4_audit_categories():
    assert set(ARNOLD_EDITORIAL_PARITY_CHECKLIST) == {
        "lifecycle_transitions",
        "prerequisites",
        "lockdown",
        "body_validation",
        "checklist_behavior",
        "sprint_queue_behavior",
        "hot_context_shape",
    }
    assert all(ARNOLD_EDITORIAL_PARITY_CHECKLIST.values())
