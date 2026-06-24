"""Tests for deterministic resume-cursor routing (T16).

Covers:
- classify_resume_cursor returns "graph" for cursors without native key
- classify_resume_cursor returns "native" for valid native cursors
- classify_resume_cursor returns "none" when no cursor file exists
- classify_resume_cursor raises NativeCursorCorruptError for corrupt native cursors
- Integration: run_pipeline_dispatch routes to native executor for native-born cursors
- Integration: run_pipeline_dispatch routes to graph executor for graph-born cursors
- Integration: run_pipeline_dispatch fails closed for corrupt native cursors
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from arnold.pipeline.native.checkpoint import (
    NATIVE_CURSOR_VERSION,
    NativeCursorCorruptError,
    classify_resume_cursor,
    persist_native_cursor,
    read_native_cursor,
)
from arnold.pipeline.resume import (
    RESUME_CURSOR_FILENAME,
    persist_resume_cursor,
)


# ── Unit tests: classify_resume_cursor ───────────────────────────────


class TestClassifyResumeCursor:
    """Unit tests for classify_resume_cursor function."""

    # ── "none" cases ────────────────────────────────────────────────

    def test_no_cursor_file_returns_none(self, tmp_path: Path) -> None:
        """No resume_cursor.json → "none"."""
        assert classify_resume_cursor(tmp_path) == "none"

    def test_unreadable_json_returns_none(self, tmp_path: Path) -> None:
        """Malformed JSON that can't be parsed → "none"."""
        (tmp_path / RESUME_CURSOR_FILENAME).write_text("{", encoding="utf-8")
        assert classify_resume_cursor(tmp_path) == "none"

    def test_non_dict_json_returns_none(self, tmp_path: Path) -> None:
        """JSON that isn't a dict → "none"."""
        (tmp_path / RESUME_CURSOR_FILENAME).write_text("[1, 2, 3]", encoding="utf-8")
        assert classify_resume_cursor(tmp_path) == "none"

    # ── "graph" cases ───────────────────────────────────────────────

    def test_cursor_without_native_key_returns_graph(self, tmp_path: Path) -> None:
        """Cursor with no 'native' key → graph-born."""
        persist_resume_cursor(
            tmp_path,
            stage="prep",
            resume_cursor="cursor-1",
            reason="awaiting_human",
        )
        assert classify_resume_cursor(tmp_path) == "graph"

    def test_cursor_with_null_native_returns_graph(self, tmp_path: Path) -> None:
        """Cursor with 'native': null → treated as absent → graph."""
        payload = {
            "stage": "prep",
            "resume_cursor": None,
            "native": None,
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        assert classify_resume_cursor(tmp_path) == "graph"

    def test_graph_cursor_with_extra_fields_returns_graph(self, tmp_path: Path) -> None:
        """Graph cursor with extra fields (but no native key) → graph."""
        payload = {
            "stage": "review",
            "resume_cursor": "c-123",
            "stages": ["prep", "plan"],
            "loops": {},
            "frames": {},
            "extra_field": "some_value",
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        assert classify_resume_cursor(tmp_path) == "graph"

    # ── "native" cases ──────────────────────────────────────────────

    def test_valid_native_cursor_returns_native(self, tmp_path: Path) -> None:
        """Valid native cursor → native-born."""
        persist_native_cursor(
            tmp_path,
            stage="megaplan__prep__pc0",
            pc=0,
        )
        assert classify_resume_cursor(tmp_path) == "native"

    def test_valid_native_cursor_with_all_fields_returns_native(self, tmp_path: Path) -> None:
        """Full native cursor → native-born."""
        persist_native_cursor(
            tmp_path,
            stage="megaplan__plan__pc1",
            pc=1,
            stages=["megaplan__prep__pc0"],
            loops={"gate_loop": 2},
            frames={"gate_loop": {"iteration_data": {}}},
            resume_cursor="opaque-cursor",
            cursor_id="abc123def456",
            stage_reentry_points={"prep": "megaplan__prep__pc0"},
        )
        assert classify_resume_cursor(tmp_path) == "native"

    def test_native_cursor_minimal_valid_returns_native(self, tmp_path: Path) -> None:
        """Minimal valid native cursor (just pc + version) → native."""
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": {"pc": 0, "version": 1},
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        assert classify_resume_cursor(tmp_path) == "native"

    # ── NativeCursorCorruptError cases ──────────────────────────────

    def test_native_not_dict_raises_corrupt_error(self, tmp_path: Path) -> None:
        """native key is a string → NativeCursorCorruptError."""
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": "not-a-dict",
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        with pytest.raises(NativeCursorCorruptError) as exc_info:
            classify_resume_cursor(tmp_path)
        assert "not a JSON object" in str(exc_info.value)
        assert exc_info.value.cursor_path is not None

    def test_native_is_list_raises_corrupt_error(self, tmp_path: Path) -> None:
        """native key is a list → NativeCursorCorruptError."""
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": [1, 2, 3],
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        with pytest.raises(NativeCursorCorruptError) as exc_info:
            classify_resume_cursor(tmp_path)
        assert "not a JSON object" in str(exc_info.value)

    def test_native_missing_pc_raises_corrupt_error(self, tmp_path: Path) -> None:
        """native dict missing 'pc' → NativeCursorCorruptError."""
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": {"version": 1},
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        with pytest.raises(NativeCursorCorruptError) as exc_info:
            classify_resume_cursor(tmp_path)
        assert "missing the required 'pc'" in str(exc_info.value)

    def test_native_missing_version_raises_corrupt_error(self, tmp_path: Path) -> None:
        """native dict missing 'version' → NativeCursorCorruptError."""
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": {"pc": 0},
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        with pytest.raises(NativeCursorCorruptError) as exc_info:
            classify_resume_cursor(tmp_path)
        assert "missing the required 'version'" in str(exc_info.value)

    def test_native_pc_not_int_raises_corrupt_error(self, tmp_path: Path) -> None:
        """native.pc is a string → NativeCursorCorruptError."""
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": {"pc": "zero", "version": 1},
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        with pytest.raises(NativeCursorCorruptError) as exc_info:
            classify_resume_cursor(tmp_path)
        assert "unreadable" in str(exc_info.value).lower() or "expected int" in str(exc_info.value)

    def test_native_version_not_int_raises_corrupt_error(self, tmp_path: Path) -> None:
        """native.version is a string → NativeCursorCorruptError."""
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": {"pc": 0, "version": "one"},
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        with pytest.raises(NativeCursorCorruptError) as exc_info:
            classify_resume_cursor(tmp_path)
        assert "unreadable" in str(exc_info.value).lower() or "expected int" in str(exc_info.value)

    def test_native_pc_is_float_raises_corrupt_error(self, tmp_path: Path) -> None:
        """native.pc is a float → NativeCursorCorruptError (not an int)."""
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": {"pc": 1.5, "version": 1},
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        with pytest.raises(NativeCursorCorruptError):
            classify_resume_cursor(tmp_path)

    def test_corrupt_error_includes_cursor_path(self, tmp_path: Path) -> None:
        """NativeCursorCorruptError carries the cursor path."""
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": "bad",
        }
        cursor_path = tmp_path / RESUME_CURSOR_FILENAME
        cursor_path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(NativeCursorCorruptError) as exc_info:
            classify_resume_cursor(tmp_path)
        assert exc_info.value.cursor_path == str(cursor_path)


# ── Integration tests: run_pipeline_dispatch resume routing ──────────


class TestDispatchResumeRouting:
    """Integration tests for resume routing in run_pipeline_dispatch."""

    _NATIVE_STAGE_ORDER: tuple[str, ...] = (
        "prep",
        "plan",
        "critique",
        "gate",
        "revise",
        "finalize",
        "execute",
        "review",
        "tiebreaker",
    )

    def _make_ctx(self, state: dict | None = None, *, artifact_root: str = "/tmp") -> object:
        """Build a minimal StepContext-like object for dispatch tests."""
        from arnold.pipelines.megaplan._pipeline.types import StepContext

        return StepContext(
            plan_dir=Path(artifact_root),
            state=state or {},
            profile=None,
            mode="test",
            inputs={},
            budget=None,
        )

    def _make_native_capable_megaplan_pipeline(self) -> object:
        return SimpleNamespace(
            entry="prep",
            stages={name: object() for name in self._NATIVE_STAGE_ORDER},
            resource_bundles=self._NATIVE_STAGE_ORDER,
        )

    def test_native_born_cursor_routes_to_native(self, tmp_path: Path) -> None:
        """When a valid native cursor exists, dispatch routes to native executor
        even when _native_execution is False."""
        from arnold.pipelines.megaplan._pipeline._bridge import run_pipeline_dispatch

        # Write a native cursor
        persist_native_cursor(
            tmp_path,
            stage="megaplan__prep__pc0",
            pc=0,
        )

        ctx = self._make_ctx(
            {"_native_execution": False}, artifact_root=str(tmp_path)
        )

        # Patch NativeMegaplanRunner to avoid actual execution
        with patch(
            "arnold.pipelines.megaplan.native_runner.NativeMegaplanRunner.run_native_pipeline"
        ) as mock_run:
            mock_run.return_value = type(
                "FakeResult", (),
                {
                    "state": {"_native_execution": True, "resumed": True},
                    "stages": ["megaplan__prep__pc0"],
                    "suspended": False,
                    "envelope": None,
                },
            )()

            # Patch build_pipeline to avoid actual pipeline construction
            with patch(
                "arnold.pipelines.megaplan._pipeline._bridge.run_pipeline_bridged",
                return_value={"state": {}, "final_stage": "prep", "status": "completed"},
            ):
                result = run_pipeline_dispatch(
                    pipeline=None,
                    ctx=ctx,
                    artifact_root=tmp_path,
                    pipeline_key="megaplan",
                )

        # Should have called the native runner with resume=True
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["resume"] is True, (
            f"Expected resume=True for native-born cursor, got {call_kwargs.get('resume')}"
        )

    def test_graph_born_cursor_routes_to_graph(self, tmp_path: Path) -> None:
        """When a graph-born cursor exists (no native key), dispatch routes
        to the graph executor even when _native_execution is True."""
        from arnold.pipelines.megaplan._pipeline._bridge import run_pipeline_dispatch

        # Write a graph-born cursor (no native key)
        persist_resume_cursor(
            tmp_path,
            stage="prep",
            resume_cursor="cursor-1",
            reason="awaiting_human",
        )

        ctx = self._make_ctx(
            {"_native_execution": True}, artifact_root=str(tmp_path)
        )

        legacy_called = []

        def fake_legacy_run(pipeline_arg, ctx_arg, *, artifact_root):
            legacy_called.append(True)
            return {
                "state": ctx_arg.state if hasattr(ctx_arg, "state") else {},
                "final_stage": "prep",
                "halt_reason": None,
                "envelope": None,
                "status": "completed",
                "contract_result": None,
            }

        with patch(
            "arnold.pipelines.megaplan._pipeline.executor.run_pipeline",
            fake_legacy_run,
        ):
            result = run_pipeline_dispatch(
                pipeline=None,
                ctx=ctx,
                artifact_root=tmp_path,
                pipeline_key="megaplan",
            )

        # Should have called the legacy graph executor
        assert len(legacy_called) == 1, (
            f"Expected legacy executor to be called for graph-born cursor, "
            f"got {len(legacy_called)} calls"
        )

    def test_corrupt_native_cursor_fails_closed(self, tmp_path: Path) -> None:
        """When a corrupt native cursor exists, dispatch must fail closed
        and NOT fall back to the graph executor."""
        from arnold.pipelines.megaplan._pipeline._bridge import run_pipeline_dispatch

        # Write a corrupt native cursor (native is not a dict)
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": "corrupt",
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )

        ctx = self._make_ctx(
            {"_native_execution": False}, artifact_root=str(tmp_path)
        )

        # Should raise NativeCursorCorruptError (fail closed)
        with pytest.raises(NativeCursorCorruptError) as exc_info:
            run_pipeline_dispatch(
                pipeline=None,
                ctx=ctx,
                artifact_root=tmp_path,
                pipeline_key="megaplan",
            )
        assert "not a JSON object" in str(exc_info.value)

    def test_no_cursor_uses_flag_routing_native(self, tmp_path: Path) -> None:
        """When no cursor exists, the _native_execution flag controls routing."""
        from arnold.pipelines.megaplan._pipeline._bridge import run_pipeline_dispatch

        ctx = self._make_ctx(
            {"_native_execution": True}, artifact_root=str(tmp_path)
        )

        with patch(
            "arnold.pipelines.megaplan.native_runner.NativeMegaplanRunner.run_native_pipeline"
        ) as mock_run:
            mock_run.return_value = type(
                "FakeResult", (),
                {
                    "state": {"_native_execution": True},
                    "stages": ["megaplan__prep__pc0"],
                    "suspended": False,
                    "envelope": None,
                },
            )()

            with patch(
                "arnold.pipelines.megaplan._pipeline._bridge.run_pipeline_bridged",
                return_value={"state": {}, "final_stage": "prep", "status": "completed"},
            ):
                result = run_pipeline_dispatch(
                    pipeline=None,
                    ctx=ctx,
                    artifact_root=tmp_path,
                    pipeline_key="megaplan",
                )

        # Should route to native with resume=False (fresh run)
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs.get("resume") is False

    def test_no_cursor_uses_flag_routing_graph(self, tmp_path: Path) -> None:
        """When no cursor exists and _native_execution is False, route to graph."""
        from arnold.pipelines.megaplan._pipeline._bridge import run_pipeline_dispatch

        ctx = self._make_ctx(
            {"_native_execution": False}, artifact_root=str(tmp_path)
        )

        legacy_called = []

        def fake_legacy_run(pipeline_arg, ctx_arg, *, artifact_root):
            legacy_called.append(True)
            return {
                "state": ctx_arg.state if hasattr(ctx_arg, "state") else {},
                "final_stage": None,
                "halt_reason": None,
                "envelope": None,
                "status": "completed",
                "contract_result": None,
            }

        with patch(
            "arnold.pipelines.megaplan._pipeline.executor.run_pipeline",
            fake_legacy_run,
        ):
            result = run_pipeline_dispatch(
                pipeline=None,
                ctx=ctx,
                artifact_root=tmp_path,
                pipeline_key="megaplan",
            )

        assert len(legacy_called) == 1

    def test_no_cursor_native_capable_fresh_defaults_native(self, tmp_path: Path) -> None:
        """When no cursor or explicit graph marker exists, converted Megaplan
        graphs default to native execution."""
        from arnold.pipelines.megaplan._pipeline._bridge import run_pipeline_dispatch

        ctx = self._make_ctx({}, artifact_root=str(tmp_path))

        with patch(
            "arnold.pipelines.megaplan.native_runner.NativeMegaplanRunner.run_native_pipeline"
        ) as mock_run:
            mock_run.return_value = type(
                "FakeResult",
                (),
                {
                    "state": {"resumed": False},
                    "stages": ["megaplan__prep__pc0"],
                    "suspended": False,
                    "envelope": None,
                },
            )()

            run_pipeline_dispatch(
                pipeline=self._make_native_capable_megaplan_pipeline(),
                ctx=ctx,
                artifact_root=tmp_path,
                pipeline_key="megaplan",
            )

        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs.get("resume") is False

    def test_no_cursor_explicit_graph_overrides_native_default(self, tmp_path: Path) -> None:
        """A fresh explicit graph marker keeps a converted pipeline on graph."""
        from arnold.pipelines.megaplan._pipeline._bridge import run_pipeline_dispatch

        ctx = self._make_ctx(
            {
                "runtime_envelope": {"runtime": "graph"},
                "meta": {"executor": "native"},
            },
            artifact_root=str(tmp_path),
        )

        legacy_called = []

        def fake_legacy_run(pipeline_arg, ctx_arg, *, artifact_root):
            legacy_called.append(True)
            return {
                "state": dict(ctx_arg.state),
                "final_stage": None,
                "halt_reason": None,
                "envelope": None,
                "status": "completed",
                "contract_result": None,
            }

        with patch(
            "arnold.pipelines.megaplan._pipeline.executor.run_pipeline",
            fake_legacy_run,
        ):
            run_pipeline_dispatch(
                pipeline=self._make_native_capable_megaplan_pipeline(),
                ctx=ctx,
                artifact_root=tmp_path,
                pipeline_key="megaplan",
            )

        assert len(legacy_called) == 1

    def test_no_cursor_persisted_runtime_envelope_graph_overrides_native_default(
        self,
        tmp_path: Path,
    ) -> None:
        """Persisted state.json runtime markers participate in fresh routing."""
        from arnold.pipelines.megaplan._pipeline._bridge import run_pipeline_dispatch

        (tmp_path / "state.json").write_text(
            json.dumps(
                {
                    "runtime_envelope": {"runtime": "graph"},
                    "meta": {"executor": "graph"},
                }
            ),
            encoding="utf-8",
        )
        ctx = self._make_ctx({}, artifact_root=str(tmp_path))

        legacy_called = []

        def fake_legacy_run(pipeline_arg, ctx_arg, *, artifact_root):
            legacy_called.append(True)
            return {
                "state": dict(ctx_arg.state),
                "final_stage": None,
                "halt_reason": None,
                "envelope": None,
                "status": "completed",
                "contract_result": None,
            }

        with patch(
            "arnold.pipelines.megaplan._pipeline.executor.run_pipeline",
            fake_legacy_run,
        ):
            run_pipeline_dispatch(
                pipeline=self._make_native_capable_megaplan_pipeline(),
                ctx=ctx,
                artifact_root=tmp_path,
                pipeline_key="megaplan",
            )

        assert len(legacy_called) == 1


# ── Edge case tests ──────────────────────────────────────────────────


class TestResumeRoutingEdgeCases:
    """Edge cases for resume routing."""

    def test_empty_dict_native_raises_corrupt_error(self, tmp_path: Path) -> None:
        """native key is an empty dict → missing pc and version → corrupt."""
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": {},
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        with pytest.raises(NativeCursorCorruptError) as exc_info:
            classify_resume_cursor(tmp_path)
        assert "missing the required 'pc'" in str(exc_info.value)

    def test_native_with_extra_keys_is_valid(self, tmp_path: Path) -> None:
        """native dict with extra keys beyond pc/version is still valid."""
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": {
                "pc": 5,
                "version": 2,
                "extra_field": "ignored",
                "nested": {"a": 1},
            },
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        assert classify_resume_cursor(tmp_path) == "native"

    def test_classify_then_read_consistency(self, tmp_path: Path) -> None:
        """classify_resume_cursor("native") implies read_native_cursor succeeds."""
        persist_native_cursor(
            tmp_path,
            stage="megaplan__finalize__pc3",
            pc=3,
            stages=["megaplan__prep__pc0", "megaplan__plan__pc1", "megaplan__critique__pc2"],
        )
        assert classify_resume_cursor(tmp_path) == "native"
        cursor = read_native_cursor(tmp_path)
        assert cursor is not None
        assert cursor["native"]["pc"] == 3
        assert cursor["native"]["version"] == NATIVE_CURSOR_VERSION

    def test_classify_graph_then_read_returns_none(self, tmp_path: Path) -> None:
        """classify_resume_cursor("graph") implies read_native_cursor returns None."""
        persist_resume_cursor(
            tmp_path,
            stage="human_review",
            resume_cursor="c-1",
            reason="awaiting_human",
        )
        assert classify_resume_cursor(tmp_path) == "graph"
        assert read_native_cursor(tmp_path) is None

    def test_native_cursor_version_constant_used(self, tmp_path: Path) -> None:
        """The NATIVE_CURSOR_VERSION constant is respected."""
        assert NATIVE_CURSOR_VERSION == 1
        persist_native_cursor(tmp_path, stage="s", pc=0, version=NATIVE_CURSOR_VERSION)
        cursor = read_native_cursor(tmp_path)
        assert cursor is not None
        assert cursor["native"]["version"] == NATIVE_CURSOR_VERSION

    def test_nested_directory_artifact_root(self, tmp_path: Path) -> None:
        """classify_resume_cursor works with nested artifact_root paths."""
        nested = tmp_path / "deep" / "path"
        nested.mkdir(parents=True)
        assert classify_resume_cursor(nested) == "none"

        persist_native_cursor(nested, stage="s", pc=0)
        assert classify_resume_cursor(nested) == "native"

    def test_string_artifact_root_accepted(self, tmp_path: Path) -> None:
        """classify_resume_cursor accepts string paths."""
        persist_native_cursor(tmp_path, stage="s", pc=0)
        assert classify_resume_cursor(str(tmp_path)) == "native"
