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
        from arnold.pipelines.megaplan.workers import (
            validate_payload,
            warn_if_work_dir_differs_from_project_dir,
        )

        assert callable(validate_payload)
        assert callable(warn_if_work_dir_differs_from_project_dir)

    def test_handler_critique_imports(self) -> None:
        from arnold.pipelines.megaplan.workers import WorkerResult, validate_payload

        assert WorkerResult is not None
        assert callable(validate_payload)

    def test_handler_review_imports(self) -> None:
        from arnold.pipelines.megaplan.workers import (
            WorkerResult,
            validate_payload,
            warn_if_work_dir_differs_from_project_dir,
        )
        assert WorkerResult is not None
        assert callable(validate_payload)
        assert callable(warn_if_work_dir_differs_from_project_dir)

    def test_handler_gate_imports(self) -> None:
        from arnold.pipelines.megaplan.workers import WorkerResult

        assert WorkerResult is not None

    def test_handler_finalize_imports(self) -> None:
        from arnold.pipelines.megaplan.workers import WorkerResult

        assert WorkerResult is not None

    def test_handler_shared_imports(self) -> None:
        from arnold.pipelines.megaplan.workers import WorkerResult

        assert WorkerResult is not None

    def test_handler_init_imports(self) -> None:
        from arnold.pipelines.megaplan.workers import resolve_agent_mode

        assert callable(resolve_agent_mode)


class TestSeamAccessCompatibility:
    """Validation wrappers and seam helpers that handlers rely on
    must remain reachable through the workers export surface."""

    def test_validate_payload_is_directly_importable(self) -> None:
        from arnold.pipelines.megaplan.workers import validate_payload

        assert callable(validate_payload)

    def test_worker_result_type_available(self) -> None:
        from arnold.pipelines.megaplan.workers import WorkerResult

        assert WorkerResult is not None

    def test_step_schema_filenames_available(self) -> None:
        from arnold.pipelines.megaplan.workers import STEP_SCHEMA_FILENAMES

        assert isinstance(STEP_SCHEMA_FILENAMES, dict)

    def test_work_dir_warning_available(self) -> None:
        """warn_if_work_dir_differs_from_project_dir must be importable;
        handlers/execute.py and handlers/review.py depend on it."""
        from arnold.pipelines.megaplan.workers import (
            warn_if_work_dir_differs_from_project_dir,
        )

        assert callable(warn_if_work_dir_differs_from_project_dir)


class TestWorkersAllIsNarrow:
    """The workers __all__ must stay narrow: handler-level validation
    wrappers and glue helpers only.  Model-seam primitives are accessed
    through ``arnold.pipelines.megaplan``, not through workers."""

    def test_all_does_not_include_model_seam_primitives(self) -> None:
        import arnold.pipelines.megaplan.workers as _workers

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
        import arnold.pipelines.megaplan.workers as _workers

        required = {
            "WorkerResult",
            "validate_payload",
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
# T1 characterization: _normalize_worker_payload must remain private and
# validate_payload must remain reachable for long-tail handlers until m6.
# ---------------------------------------------------------------------------


class TestT1CallSiteInventory:
    """Characterization tests pinning which worker-level symbols are
    currently called by handlers and which are private."""

    def test_normalize_worker_payload_is_private(self) -> None:
        """_normalize_worker_payload must NOT be in workers.__all__ and
        should not be directly importable through the public surface."""
        import arnold.pipelines.megaplan.workers as _workers

        assert "_normalize_worker_payload" not in getattr(_workers, "__all__", []), (
            "_normalize_worker_payload must remain private"
        )

    def test_validate_payload_is_callable_and_still_needed_by_long_tail(self) -> None:
        """validate_payload must remain importable and callable for long-tail
        handlers (critique→revise) even after migrated sites stop using it."""
        from arnold.pipelines.megaplan.workers import validate_payload

        assert callable(validate_payload)

        # Long-tail steps must still pass.
        validate_payload(
            "revise",
            {
                "plan": "x",
                "changes_summary": "y",
                "flags_addressed": [],
                "assumptions": [],
                "success_criteria": [],
                "questions": [],
            },
        )
        # execute batch-relaxed still passes for legacy callers outside review.
        validate_payload(
            "execute",
            {
                "task_updates": [{"task_id": "T1", "status": "done"}],
                "sense_check_acknowledgments": [],
            },
        )

    def test_recovery_helpers_remain_importable(self) -> None:
        """Recovery helpers (_recover_codex_payload,
        _recover_codex_payload_with_provenance) must stay importable
        because recovery still owns both the legacy normalization path and the
        migrated-step schema-audit path."""
        from arnold.pipelines.megaplan.workers._impl import (
            _normalize_worker_payload,
            _recover_codex_payload,
            _recover_codex_payload_with_provenance,
        )

        assert callable(_normalize_worker_payload)
        assert callable(_recover_codex_payload)
        assert callable(_recover_codex_payload_with_provenance)
