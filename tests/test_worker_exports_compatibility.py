"""Import-compatibility coverage for worker exports consumed by handlers.

T18 (M3 Model Seam): Ensures handler-level imports that require stable
access to migrated seam helpers and validation wrappers stay importable
without broadening the worker package surface.  This test catches
accidental removals or renames that would break handler-glue code.
"""

from __future__ import annotations

import pytest


class TestHandlerImportCompatibility:
    """Every symbol that handler modules import from workers."""

    def test_handler_execute_imports(self) -> None:
        from arnold_pipelines.megaplan.workers import warn_if_work_dir_differs_from_project_dir

        assert callable(warn_if_work_dir_differs_from_project_dir)

    def test_handler_critique_imports(self) -> None:
        from arnold_pipelines.megaplan.workers import WorkerResult

        assert WorkerResult is not None

    def test_handler_review_imports(self) -> None:
        from arnold_pipelines.megaplan.workers import (
            WorkerResult,
            warn_if_work_dir_differs_from_project_dir,
        )
        assert WorkerResult is not None
        assert callable(warn_if_work_dir_differs_from_project_dir)

    def test_handler_gate_imports(self) -> None:
        from arnold_pipelines.megaplan.workers import WorkerResult

        assert WorkerResult is not None

    def test_handler_finalize_imports(self) -> None:
        from arnold_pipelines.megaplan.workers import WorkerResult

        assert WorkerResult is not None

    def test_handler_shared_imports(self) -> None:
        from arnold_pipelines.megaplan.workers import WorkerResult

        assert WorkerResult is not None

    def test_handler_init_imports(self) -> None:
        from arnold_pipelines.megaplan.workers import resolve_agent_mode

        assert callable(resolve_agent_mode)


class TestSeamAccessCompatibility:
    """Validation wrappers and seam helpers that handlers rely on
    must remain reachable through the workers export surface."""

    def test_validate_payload_is_not_importable_from_workers(self) -> None:
        with pytest.raises(ImportError):
            exec(
                "from arnold_pipelines.megaplan.workers import validate_payload",
                {},
            )

    def test_validate_phase_result_is_directly_importable(self) -> None:
        from arnold_pipelines.megaplan.orchestration.phase_result import validate_phase_result

        assert callable(validate_phase_result)

    def test_worker_result_type_available(self) -> None:
        from arnold_pipelines.megaplan.workers import WorkerResult

        assert WorkerResult is not None

    def test_step_schema_filenames_available(self) -> None:
        from arnold_pipelines.megaplan.workers import STEP_SCHEMA_FILENAMES

        assert isinstance(STEP_SCHEMA_FILENAMES, dict)

    def test_work_dir_warning_available(self) -> None:
        """warn_if_work_dir_differs_from_project_dir must be importable;
        handlers/execute.py and handlers/review.py depend on it."""
        from arnold_pipelines.megaplan.workers import (
            warn_if_work_dir_differs_from_project_dir,
        )

        assert callable(warn_if_work_dir_differs_from_project_dir)


class TestWorkersAllIsNarrow:
    """The workers __all__ must stay narrow: handler-level validation
    wrappers and glue helpers only.  Model-seam primitives are accessed
    through ``arnold_pipelines.megaplan``, not through workers."""

    def test_all_does_not_include_model_seam_primitives(self) -> None:
        import arnold_pipelines.megaplan.workers as _workers

        seam_names = {
            "capture_step_output",
            "render_step_message",
            "render_prompt_for_dispatch",
            "ModelTier",
            "TierMetadata",
            "ModelSeamTelemetry",
            "ModelBudget",
            "ModelFamily",
            "AuditStatus",
            "BudgetStatus",
            "CaptureOutcome",
            "RenderedStepMessage",
            "TerminalStatus",
        }
        actual_all = set(getattr(_workers, "__all__", []))
        leaked = seam_names & actual_all
        assert not leaked, (
            f"workers.__all__ leaks model-seam symbols: {sorted(leaked)}. "
            "Keep __all__ narrow; model-seam access is through megaplan directly."
        )

    def test_all_includes_handler_imports(self) -> None:
        import arnold_pipelines.megaplan.workers as _workers

        required = {
            "WorkerResult",
            "warn_if_work_dir_differs_from_project_dir",
            "resolve_agent_mode",
        }
        actual_all = set(getattr(_workers, "__all__", []))
        missing = required - actual_all
        assert not missing, (
            f"workers.__all__ is missing symbols that handlers import: "
            f"{sorted(missing)}"
        )


# ---------------------------------------------------------------------------
# T1 characterization: the deleted legacy normalizer must stay gone and
# recovery exports must remain reachable.
# ---------------------------------------------------------------------------


class TestT1CallSiteInventory:
    """Characterization tests pinning which worker-level symbols are
    currently called by handlers and which are private."""

    def test_normalize_worker_payload_is_deleted(self) -> None:
        """_normalize_worker_payload must no longer be importable."""
        import arnold_pipelines.megaplan.workers as _workers

        assert not hasattr(_workers, "_normalize_worker_payload")
        assert "_normalize_worker_payload" not in getattr(_workers, "__all__", [])

    def test_normalize_worker_payload_cannot_be_imported_from_workers(self) -> None:
        with pytest.raises(ImportError):
            exec(
                "from arnold_pipelines.megaplan.workers import "
                "_normalize_worker_payload",
                {},
            )

    def test_validate_payload_is_not_importable_from_impl(self) -> None:
        """The orphan legacy helper is deleted from the implementation module."""
        with pytest.raises(ImportError):
            exec("from arnold_pipelines.megaplan.workers._impl import validate_payload", {})

    def test_worker_recovery_helpers_are_deleted(self) -> None:
        """Codex recovery now lives behind model_seam capture only."""
        import arnold_pipelines.megaplan.workers._impl as workers_impl
        from arnold_pipelines.megaplan.model_seam import _recover_payload_with_provenance

        assert not hasattr(workers_impl, "_recover_codex_payload")
        assert not hasattr(workers_impl, "_recover_codex_payload_with_provenance")
        assert callable(_recover_payload_with_provenance)
