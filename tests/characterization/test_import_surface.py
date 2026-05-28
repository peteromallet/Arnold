"""Import-surface characterization — verify that the public (and de-facto public)
symbols resolved by the codebase actually exist and are importable.

Modules with ``__all__``
  *megaplan.store* and *megaplan.workers* declare ``__all__``.  Every symbol in
  those lists MUST resolve.  This is the *explicit* public API contract.

Modules without ``__all__``
  *megaplan.cli*, *megaplan.chain*, and *megaplan.orchestration.evaluation* do
  not declare ``__all__``.  For these we survey every existing test file and
  collect **every** symbol that a test imports directly from the module.  This
  is the *de-facto* public surface — if a test depends on it, breaking it is a
  regression.

Remote-exec guard (forced inclusion)
  ``megaplan.cloud.supervise`` constructs a remote Python one-liner that
  imports ``_capture_sync_state``, ``ChainState``, ``save_chain_state``, and
  ``load_chain_state`` from ``megaplan.chain``.  These four symbols MUST
  resolve.  ``_capture_sync_state`` is also asserted to be a callable function
  and ``ChainState`` to be a class so that the remote-exec protocol is not
  silently broken by a type change.

Design decision (per plan SD1 + gate sign-off)
  For modules without ``__all__`` we include *all* symbols that existing tests
  import, including underscore-prefixed private helpers.  This captures the
  de-facto surface the codebase actually depends on.  When a symbol is later
  promoted to a proper public API it can be moved to an ``__all__`` block; at
  that point this test switches from "de-facto" to "explicit" mode for that
  module.
"""

from __future__ import annotations

import inspect

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _assert_resolves(module_name: str, symbols: list[str]) -> None:
    """Import every symbol from *module_name* and fail loudly if any is missing."""
    module = __import__(module_name, fromlist=symbols)
    missing: list[str] = []
    for name in symbols:
        try:
            getattr(module, name)
        except AttributeError:
            missing.append(name)
    if missing:
        names = "\n  ".join(missing)
        raise AssertionError(
            f"{len(missing)} symbol(s) missing from {module_name}:\n  {names}"
        )


# ---------------------------------------------------------------------------
# Modules with __all__
# ---------------------------------------------------------------------------

STORE_ALL = [
    "ArnoldBlobAdapter",
    "ArnoldStoreAdapter",
    "ArtifactRef",
    "ArtifactStat",
    "Backend",
    "BlobMissingError",
    "BlobRef",
    "BlobStat",
    "BlobStore",
    "ChecklistItemInput",
    "CloudRun",
    "CloudRunInput",
    "ControlMessageInput",
    "DBStore",
    "deterministic_idempotency_key",
    "EpicSummary",
    "FileStore",
    "HotContext",
    "Lease",
    "LeaseConflict",
    "LockConflict",
    "LocalDirBlobStore",
    "MessageSearchHit",
    "MultiStore",
    "PlanRepository",
    "ProgressEventInput",
    "require_actor_id",
    "ResidentConversation",
    "ResidentConversationInput",
    "resolve_actor_id",
    "RevisionConflict",
    "ScheduledJob",
    "ScheduledJobInput",
    "SprintItemInput",
    "SprintWithItems",
    "Store",
    "StoreError",
    "SupabaseStorageBlobStore",
    "Transaction",
    "validate_actor_exists",
]

WORKERS_ALL = [
    "AgentMode",
    "CommandResult",
    "WorkerResult",
    "STEP_SCHEMA_FILENAMES",
    "_build_mock_payload",
    "_codex_child_env",
    "_codex_timeout_for_step",
    "_diagnose_codex_failure",
    "_external_worker_env",
    "_extract_claude_usage",
    "_is_agent_available",
    "_is_poisoned_environmental_failure",
    "_is_session_too_large_for_compact",
    "_merge_partial_output",
    "_recover_codex_payload",
    "validate_payload",
    "run_codex_prep_step",
    "run_step_with_worker",
    "resolve_agent_mode",
    "set_work_dir_override",
    "session_key_for",
    "update_session_state",
    "mock_worker_output",
]


# ---------------------------------------------------------------------------
# Modules without __all__ — symbols imported by existing tests
# ---------------------------------------------------------------------------

CLI_SYMBOLS = [
    # test_cli_entry.py (top-level)
    "COMMAND_HANDLERS",
    "_build_status_payload",
    "cli_entry",
    "handle_quality_gate",
    "handle_user_action",
    # test_cli_entry.py (inline imports)
    "main",
    "build_parser",
    # test_pipeline_run_cli.py
    "handle_list",
    "handle_describe",
    # test_resolve_project_root.py
    "_resolve_project_root",
    # test_feedback.py
    "_filter_feedback_rows",
    "_render_feedback_table",
    "_collect_feedback_rows",
    # test_feedback_phase.py
    "handle_feedback",
    # test_resolutions.py
    "_compute_user_action_blockers",
    "_build_progress_payload",
    # test_lifecycle_states.py
    # (already covered: _build_status_payload, handle_list)
    # editorial_run_lifecycle.py
    # (imports megaplan.cli.main — already covered)
]

CHAIN_SYMBOLS = [
    # test_chain.py (top-level)
    "ChainSpec",
    "ChainState",
    "MilestoneSpec",
    "_commit_and_push_phase",
    "_command_env",
    "_enable_auto_merge",
    "_pr_state",
    "_run_command",
    "_should_retry_gh_without_env",
    "_state_path_for",
    "format_chain_status",
    "load_chain_state",
    "load_spec",
    "run_chain",
    "run_chain_cli",
    "save_chain_state",
    # test_chain.py (inline imports)
    "_refresh_base_branch",
    "_plan_state",
    "_init_plan",
    "_ensure_milestone_pr",
    "_checkout_milestone_branch",
    # Remote-exec guard (forced inclusion per plan)
    "_capture_sync_state",
]

EVALUATION_SYMBOLS = [
    # test_evaluation.py (top-level)
    "PLAN_STRUCTURE_REQUIRED_STEP_ISSUE",
    "_strip_fenced_blocks",
    "build_gate_artifact",
    "build_orchestrator_guidance",
    "build_gate_signals",
    "compute_plan_delta_percent",
    "compute_recurring_critiques",
    "flag_weight",
    "is_rubber_stamp",
    "parse_plan_sections",
    "reassemble_plan",
    "renumber_steps",
    "validate_execution_evidence",
    "validate_plan_structure",
    # test_init_plan.py
    # (already covered: PLAN_STRUCTURE_REQUIRED_STEP_ISSUE,
    #  validate_plan_structure)
    # test_doc_mode.py
    # (already covered: validate_execution_evidence)
    # test_critique.py
    # (already covered: build_gate_signals)
    # test_workers.py
    # (already covered: validate_plan_structure)
]

EXECUTE_CORE_SYMBOLS = [
    # Direct imports from megaplan.execute.core
    # test_creative_mode_smoke.py, test_directors_notes_idempotency.py
    "_build_aggregate_execution_payload",
    # test_execute_merge_creative.py
    "_merge_batch_results",
    # Attribute access (megaplan.execute.core.X) and monkeypatch targets
    # test_execute.py — attribute access
    "BatchResult",
    "handle_execute_auto_loop",
    "handle_execute_one_batch",
    "_has_code_task_advisory_evidence",
    # test_execute.py — monkeypatch targets
    "_capture_git_status_snapshot",
    "_capture_git_status_snapshot_recursive",
    "_compute_execute_scope_drift",
    "_resolve_tier_spec",
    "_run_and_merge_batch",
    "load_config",
    # test_init_plan.py — attribute access
    "build_monitor_hint",
    # test_scope_drift_doc_mode.py — attribute access (via execute_core alias)
    # (_compute_execute_scope_drift already listed above)
    # test_review.py — source inspection (via execution_module alias)
    # (_merge_batch_results already listed above)
    # test_receipts_drift_blocking.py — monkeypatch target
    # (_capture_git_status_snapshot already listed above)
]

EXECUTE_SYMBOLS = [
    # From megaplan.execute.__all__ — explicit public API
    "BatchResult",
    "build_blocking_reasons",
    "build_monitor_hint",
    "handle_execute_auto_loop",
    "handle_execute_one_batch",
    "worker_module",
    "run_quality_checks",
    "_validate_and_merge_batch",
]


# ====================================================================
# Tests
# ====================================================================

class TestStoreImportSurface:
    """Every ``megaplan.store.__all__`` symbol must resolve."""

    def test_all_symbols_resolve(self) -> None:
        _assert_resolves("megaplan.store", STORE_ALL)


class TestWorkersImportSurface:
    """Every ``megaplan.workers.__all__`` symbol must resolve."""

    def test_all_symbols_resolve(self) -> None:
        _assert_resolves("megaplan.workers", WORKERS_ALL)


class TestCliImportSurface:
    """De-facto surface: every symbol that existing tests import from
    ``megaplan.cli`` must resolve."""

    def test_surveyed_symbols_resolve(self) -> None:
        _assert_resolves("megaplan.cli", CLI_SYMBOLS)


class TestChainImportSurface:
    """De-facto surface: every symbol that existing tests import from
    ``megaplan.chain`` must resolve.  Includes private helpers because
    the existing tests depend on them."""

    def test_surveyed_symbols_resolve(self) -> None:
        _assert_resolves("megaplan.chain", CHAIN_SYMBOLS)

    def test_remote_exec_guard_callable_or_class(self) -> None:
        """The remote-exec guard in ``megaplan.cloud.supervise`` constructs a
        Python one-liner that calls these four symbols.  They must exist
        AND have the expected type (function vs class) so the remote exec
        does not silently break."""
        from megaplan.chain import (
            ChainState,
            _capture_sync_state,
            load_chain_state,
            save_chain_state,
        )

        # _capture_sync_state must be a callable function (not a class).
        assert callable(_capture_sync_state), (
            "_capture_sync_state must be callable"
        )
        assert isinstance(_capture_sync_state, type(lambda: None)) or not isinstance(
            _capture_sync_state, type
        ), "_capture_sync_state must be a function"

        # ChainState must be a class.
        assert inspect.isclass(ChainState), "ChainState must be a class"

        # save_chain_state and load_chain_state must be callable.
        assert callable(save_chain_state), "save_chain_state must be callable"
        assert callable(load_chain_state), "load_chain_state must be callable"

        # Additional sanity: load_chain_state returns ChainState when given a Path.
        # We don't call it here (no side-effect-free call), just verify the
        # signature includes the expected parameter.
        sig = inspect.signature(load_chain_state)
        assert "spec_path" in sig.parameters, (
            "load_chain_state must accept 'spec_path' parameter"
        )


class TestStoreDeepImportPaths:
    """Deep import paths that runtime code and tests depend on must survive
    decomposition.  Even if assembly modules (``file.py``, ``db.py``) remain
    the canonical entry points, the sub-module namespace must still resolve
    symbols at their historical paths."""

    def test_deep_imports_from_store_submodules(self) -> None:
        # These paths are used by runtime code (tickets/core.py, cli.py,
        # resident/profile.py) and by existing tests.
        from megaplan.store.file import FileStore  # noqa: F401
        from megaplan.store.db import DBStore  # noqa: F401
        from megaplan.store.multi import MultiStore  # noqa: F401
        from megaplan.store.base import HotContext  # noqa: F401
        from megaplan.store.base import EpicSummary  # noqa: F401
        from megaplan.store.base import ArtifactRef  # noqa: F401
        from megaplan.store.base import validate_plan_artifact_name  # noqa: F401
        from megaplan.store.plan_repository import PlanRepository  # noqa: F401

    def test_snapshot_imports_preserved(self) -> None:
        from megaplan.store.snapshot import canonical_json_dumps  # noqa: F401
        from megaplan.store.snapshot import canonical_sha256  # noqa: F401

    def test_epic_summary_alias_identity_is_preserved(self) -> None:
        from megaplan.schemas import EpicSearchSummary
        from megaplan.store import EpicSummary

        assert EpicSearchSummary is EpicSummary


class TestEvaluationImportSurface:
    """De-facto surface: every symbol that existing tests import from
    ``megaplan.orchestration.evaluation`` must resolve."""

    def test_surveyed_symbols_resolve(self) -> None:
        _assert_resolves(
            "megaplan.orchestration.evaluation", EVALUATION_SYMBOLS
        )


class TestExecuteCoreImportSurface:
    """De-facto surface: every symbol that existing tests import from or
    monkeypatch on ``megaplan.execute.core`` must resolve."""

    def test_surveyed_symbols_resolve(self) -> None:
        _assert_resolves("megaplan.execute.core", EXECUTE_CORE_SYMBOLS)


class TestExecuteImportSurface:
    """Explicit surface: every ``megaplan.execute.__all__`` symbol must
    resolve."""

    def test_all_symbols_resolve(self) -> None:
        _assert_resolves("megaplan.execute", EXECUTE_SYMBOLS)
