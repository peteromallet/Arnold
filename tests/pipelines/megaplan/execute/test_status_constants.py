from __future__ import annotations

from arnold.pipelines.megaplan.execute.status_constants import (
    EXECUTE_TASK_STATUS_ALIASES,
    TERMINAL_TASK_STATUSES,
    normalize_execute_task_status,
)


# ---------------------------------------------------------------------------
# Export count — exactly three public names
# ---------------------------------------------------------------------------

def test_module_exports_exactly_three_names() -> None:
    """The module must export only TERMINAL_TASK_STATUSES, EXECUTE_TASK_STATUS_ALIASES,
    and normalize_execute_task_status."""
    import arnold.pipelines.megaplan.execute.status_constants as mod

    public = {name for name in dir(mod) if not name.startswith("_")}
    # Exclude standard Python dunder names like __builtins__, __doc__, etc.
    # and the __future__ annotations import marker.
    dunders = {
        "__builtins__",
        "__cached__",
        "__doc__",
        "__file__",
        "__loader__",
        "__name__",
        "__package__",
        "__spec__",
        "annotations",
    }
    public -= dunders
    assert public == {
        "TERMINAL_TASK_STATUSES",
        "EXECUTE_TASK_STATUS_ALIASES",
        "normalize_execute_task_status",
    }, f"Unexpected public names: {public}"


# ---------------------------------------------------------------------------
# TERMINAL_TASK_STATUSES
# ---------------------------------------------------------------------------

def test_terminal_task_statuses_is_frozenset() -> None:
    assert isinstance(TERMINAL_TASK_STATUSES, frozenset)


def test_terminal_task_statuses_contains_canonical_and_compat() -> None:
    assert TERMINAL_TASK_STATUSES == frozenset({"done", "skipped", "completed", "blocked"})


# ---------------------------------------------------------------------------
# EXECUTE_TASK_STATUS_ALIASES
# ---------------------------------------------------------------------------

def test_aliases_is_dict() -> None:
    assert isinstance(EXECUTE_TASK_STATUS_ALIASES, dict)


def test_all_four_aliases_present() -> None:
    assert EXECUTE_TASK_STATUS_ALIASES == {
        "completed": "done",
        "complete": "done",
        "skip": "skipped",
        "verified": "done",
    }


def test_subset_invariant_all_alias_values_in_terminal_set() -> None:
    """Every alias value must be a member of TERMINAL_TASK_STATUSES."""
    for alias_value in EXECUTE_TASK_STATUS_ALIASES.values():
        assert alias_value in TERMINAL_TASK_STATUSES, (
            f"Alias value {alias_value!r} not in TERMINAL_TASK_STATUSES"
        )


# ---------------------------------------------------------------------------
# normalize_execute_task_status
# ---------------------------------------------------------------------------

def test_alias_completed_normalizes_to_done() -> None:
    assert normalize_execute_task_status("completed") == "done"


def test_alias_complete_normalizes_to_done() -> None:
    assert normalize_execute_task_status("complete") == "done"


def test_alias_skip_normalizes_to_skipped() -> None:
    assert normalize_execute_task_status("skip") == "skipped"


def test_alias_verified_normalizes_to_done() -> None:
    assert normalize_execute_task_status("verified") == "done"


def test_canonical_done_passes_through() -> None:
    assert normalize_execute_task_status("done") == "done"


def test_canonical_skipped_passes_through() -> None:
    assert normalize_execute_task_status("skipped") == "skipped"


def test_canonical_blocked_passes_through() -> None:
    assert normalize_execute_task_status("blocked") == "blocked"


def test_unknown_string_passes_through() -> None:
    assert normalize_execute_task_status("finished") == "finished"


def test_none_passes_through() -> None:
    assert normalize_execute_task_status(None) is None


def test_non_string_passes_through() -> None:
    assert normalize_execute_task_status(42) == 42
    assert normalize_execute_task_status(True) is True
    assert normalize_execute_task_status([]) == []
