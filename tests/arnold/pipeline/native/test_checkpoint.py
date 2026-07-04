"""Tests for native pipeline checkpoint persistence.

Covers:
- Round-trip persist/read of the native cursor
- Required native fields (pc, version) are validated on read
- Explicit handling of missing, malformed, or non-native cursors
- Additive shape does not break the base read_resume_cursor path
- Top-level fields (stage, resume_cursor, stages, loops, frames, native)
  are present and correctly typed
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold.pipeline.native.checkpoint import (
    COMPOSITE_PARENT_CHILD_CURSOR_KIND,
    CursorUpgradeError,
    NATIVE_CURSOR_VERSION,
    NativeCursorCorruptError,
    STANDARD_NATIVE_CURSOR_KIND,
    classify_resume_cursor,
    classify_native_cursor_kind,
    persist_native_cursor,
    read_native_cursor,
    upgrade_graph_cursor_to_native,
)
from arnold.pipeline.native.ir import NativeInstruction, NativeProgram
from arnold.pipeline.resume import (
    RESUME_CURSOR_FILENAME,
    persist_resume_cursor,
    read_resume_cursor,
)


# ── round-trip tests ──────────────────────────────────────────────────


class TestRoundTrip:
    """Persist a native cursor and read it back successfully."""

    def test_minimal_cursor_round_trip(self, tmp_path: Path) -> None:
        path = persist_native_cursor(
            tmp_path,
            stage="my_pipe__do_work__pc0",
            pc=0,
        )
        assert path == tmp_path / RESUME_CURSOR_FILENAME
        assert path.exists()

        cursor = read_native_cursor(tmp_path)
        assert cursor is not None
        assert cursor["stage"] == "my_pipe__do_work__pc0"
        assert cursor["resume_cursor"] is None
        assert cursor["stages"] == []
        assert cursor["loops"] == {}
        assert cursor["frames"] == {}
        assert cursor["native"] == {"pc": 0, "version": 1}

    def test_full_cursor_round_trip(self, tmp_path: Path) -> None:
        path = persist_native_cursor(
            tmp_path,
            stage="my_pipe__guard__pc2",
            pc=2,
            stages=["my_pipe__setup__pc0", "my_pipe__body__pc1"],
            loops={"my_guard": 3},
            frames={"my_guard": {"last_result": "again"}},
            resume_cursor="cursor-abc",
            version=1,
        )
        assert path.exists()

        cursor = read_native_cursor(tmp_path)
        assert cursor is not None
        assert cursor["stage"] == "my_pipe__guard__pc2"
        assert cursor["resume_cursor"] == "cursor-abc"
        assert cursor["stages"] == ["my_pipe__setup__pc0", "my_pipe__body__pc1"]
        assert cursor["loops"] == {"my_guard": 3}
        assert cursor["frames"] == {"my_guard": {"last_result": "again"}}
        assert cursor["native"] == {"pc": 2, "version": 1}

    def test_path_metadata_round_trip(self, tmp_path: Path) -> None:
        persist_native_cursor(
            tmp_path,
            stage="my_pipe__review__pc2",
            pc=2,
            run_path="root/child_call",
            step_path="root/child_call/review",
            call_site_path=["child_call"],
            path_stack=[
                {
                    "header_pc": 1,
                    "segment": "review_loop[2]",
                    "parent_run_path": "root",
                }
            ],
        )

        cursor = read_native_cursor(tmp_path)
        assert cursor is not None
        assert cursor["run_path"] == "root/child_call"
        assert cursor["step_path"] == "root/child_call/review"
        assert cursor["call_site_path"] == ("child_call",)
        assert cursor["path_stack"] == [
            {
                "header_pc": 1,
                "segment": "review_loop[2]",
                "parent_run_path": "root",
            }
        ]
        assert cursor["native_cursor_kind"] == STANDARD_NATIVE_CURSOR_KIND

    def test_effect_metadata_round_trip(self, tmp_path: Path) -> None:
        persist_native_cursor(
            tmp_path,
            stage="my_pipe__write__pc0",
            pc=0,
            effect={
                "idempotency_key": "my_pipe/write:file_write:out/report.json",
                "step_path": "root/write",
                "operation": "file_write",
                "target": "out/report.json",
                "attempt": 2,
                "lifecycle_state": "fulfilled",
                "effect_class": "filesystem_mutation",
                "duplicate_action": "skip",
            },
        )

        cursor = read_native_cursor(tmp_path)
        assert cursor is not None
        assert cursor["effect"] == {
            "idempotency_key": "my_pipe/write:file_write:out/report.json",
            "step_path": "root/write",
            "operation": "file_write",
            "target": "out/report.json",
            "attempt": 2,
            "lifecycle_state": "fulfilled",
            "effect_class": "filesystem_mutation",
            "duplicate_action": "skip",
        }

    def test_composite_parent_child_cursor_round_trip(self, tmp_path: Path) -> None:
        persist_native_cursor(
            tmp_path,
            stage="parent__child_call__pc4",
            pc=4,
            native_extra={"suspension_kind": "child_suspended"},
            composite={
                "kind": "parent_child",
                "parent": {
                    "pc": 4,
                    "run_path": "root/parent",
                    "path_stack": [{"kind": "loop", "segment": "review[2]"}],
                    "state": {"approved": False},
                    "stages": ["parent__prep__pc0", "parent__review__pc3"],
                    "loops": {"review": 2},
                    "frames": {"review": {"last_result": "pending"}},
                    "envelope": {"lease": "L1"},
                    "cursor_id": "parent-cursor-1",
                },
                "child": {
                    "cursor_path": "_children/review/resume_cursor.json",
                    "run_path": "root/parent/review_child",
                    "call_site_path": ["review_child"],
                },
            },
        )

        cursor = read_native_cursor(tmp_path)
        assert cursor is not None
        assert cursor["native_cursor_kind"] == COMPOSITE_PARENT_CHILD_CURSOR_KIND
        assert classify_native_cursor_kind(cursor) == COMPOSITE_PARENT_CHILD_CURSOR_KIND
        assert classify_resume_cursor(tmp_path) == "native"
        assert cursor["composite"] == {
            "kind": "parent_child",
            "parent": {
                "pc": 4,
                "run_path": "root/parent",
                "path_stack": [{"kind": "loop", "segment": "review[2]"}],
                "state": {"approved": False},
                "stages": ["parent__prep__pc0", "parent__review__pc3"],
                "loops": {"review": 2},
                "frames": {"review": {"last_result": "pending"}},
                "envelope": {"lease": "L1"},
                "cursor_id": "parent-cursor-1",
            },
            "child": {
                "cursor_path": "_children/review/resume_cursor.json",
                "run_path": "root/parent/review_child",
                "call_site_path": ("review_child",),
            },
        }

    def test_file_is_valid_json(self, tmp_path: Path) -> None:
        persist_native_cursor(
            tmp_path,
            stage="s",
            pc=5,
            stages=["a", "b"],
            loops={"L": 1},
            frames={"L": {"x": [1, 2]}},
        )
        raw = (tmp_path / RESUME_CURSOR_FILENAME).read_text(encoding="utf-8")
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)
        assert "native" in parsed
        assert parsed["native"]["pc"] == 5


def _upgrade_program() -> NativeProgram:
    return NativeProgram(
        name="megaplan",
        instructions=(
            NativeInstruction(pc=0, op="phase", name="prep"),
            NativeInstruction(pc=1, op="phase", name="plan"),
            NativeInstruction(pc=2, op="phase", name="critique"),
        ),
    )


def _ambiguous_upgrade_program() -> NativeProgram:
    return NativeProgram(
        name="megaplan",
        instructions=(
            NativeInstruction(pc=0, op="phase", name="gate"),
            NativeInstruction(pc=1, op="phase", name="revise"),
            NativeInstruction(pc=2, op="phase", name="gate"),
        ),
    )


class TestGraphCursorUpgrade:
    """Explicit graph-to-native cursor upgrade behavior."""

    def test_upgrade_dry_run_is_default_and_does_not_mutate_cursor(
        self,
        tmp_path: Path,
    ) -> None:
        persist_resume_cursor(
            tmp_path,
            stage="prep",
            resume_cursor="graph-cursor",
            reason="awaiting_human",
        )
        cursor_path = tmp_path / RESUME_CURSOR_FILENAME
        before = cursor_path.read_text(encoding="utf-8")

        result = upgrade_graph_cursor_to_native(tmp_path, program=_upgrade_program())

        assert result.dry_run is True
        assert result.written is False
        assert result.graph_stage == "prep"
        assert result.native_stage == "megaplan__prep__pc0"
        assert result.native_pc == 0
        assert result.backup_path is None
        assert cursor_path.read_text(encoding="utf-8") == before
        assert classify_resume_cursor(tmp_path) == "graph"

    def test_upgrade_write_keeps_backup_and_persists_native_cursor(
        self,
        tmp_path: Path,
    ) -> None:
        persist_resume_cursor(
            tmp_path,
            stage="plan",
            resume_cursor="opaque-graph-cursor",
            reason="awaiting_human",
        )

        result = upgrade_graph_cursor_to_native(
            tmp_path,
            program=_upgrade_program(),
            dry_run=False,
        )

        assert result.written is True
        assert result.dry_run is False
        assert result.native_stage == "megaplan__plan__pc1"
        assert result.native_pc == 1
        assert result.backup_path is not None

        backup_path = Path(result.backup_path)
        assert backup_path.exists()
        backup = json.loads(backup_path.read_text(encoding="utf-8"))
        assert backup["stage"] == "plan"
        assert "native" not in backup

        cursor = read_native_cursor(tmp_path)
        assert cursor is not None
        assert cursor["stage"] == "megaplan__plan__pc1"
        assert cursor["resume_cursor"] == "opaque-graph-cursor"
        assert cursor["reentry_stage"] == "megaplan__plan__pc1"
        assert cursor["native"]["pc"] == 1
        assert cursor["native"]["upgraded_from_graph"] is True
        assert cursor["native"]["graph_stage"] == "plan"
        assert cursor["graph_cursor_backup"] == backup_path.name
        assert classify_resume_cursor(tmp_path) == "native"

    def test_upgrade_fails_diagnostically_on_ambiguous_graph_stage(
        self,
        tmp_path: Path,
    ) -> None:
        persist_resume_cursor(tmp_path, stage="gate", resume_cursor="graph-cursor")

        with pytest.raises(CursorUpgradeError) as exc_info:
            upgrade_graph_cursor_to_native(
                tmp_path,
                program=_ambiguous_upgrade_program(),
                dry_run=False,
            )

        error = exc_info.value
        assert error.code == "ambiguous_graph_stage"
        assert error.details["graph_stage"] == "gate"
        assert len(error.details["candidates"]) == 2
        assert classify_resume_cursor(tmp_path) == "graph"
        assert not list(tmp_path.glob("*.graph-backup*.json"))

    def test_upgrade_accepts_stable_stage_id_when_public_stage_is_ambiguous(
        self,
        tmp_path: Path,
    ) -> None:
        persist_resume_cursor(
            tmp_path,
            stage="megaplan__gate__pc2",
            resume_cursor="graph-cursor",
        )

        result = upgrade_graph_cursor_to_native(
            tmp_path,
            program=_ambiguous_upgrade_program(),
        )

        assert result.native_pc == 2
        assert result.native_stage == "megaplan__gate__pc2"
        assert classify_resume_cursor(tmp_path) == "graph"


# ── additive shape tests ───────────────────────────────────────────────


class TestAdditiveShape:
    """The native cursor must be readable by the base read_resume_cursor.

    Extra keys (stages, loops, frames, native) must not prevent the
    base reader from returning a valid dict.
    """

    def test_base_reader_accepts_native_cursor(self, tmp_path: Path) -> None:
        persist_native_cursor(
            tmp_path,
            stage="s",
            pc=7,
            stages=["a"],
            loops={"L": 0},
            frames={"L": {}},
        )
        data = read_resume_cursor(tmp_path)
        assert data is not None
        assert data["stage"] == "s"
        assert data["stages"] == ["a"]
        assert data["loops"] == {"L": 0}
        assert data["frames"] == {"L": {}}
        assert data["native"] == {"pc": 7, "version": 1}

    def test_native_cursor_has_all_top_level_keys(self, tmp_path: Path) -> None:
        persist_native_cursor(
            tmp_path,
            stage="s",
            pc=0,
            stages=["x"],
            loops={"y": 1},
            frames={"y": {"z": True}},
            resume_cursor="r",
        )
        cursor = read_native_cursor(tmp_path)
        assert cursor is not None
        for key in ("stage", "resume_cursor", "stages", "loops", "frames", "native"):
            assert key in cursor, f"Missing top-level key: {key}"

        native = cursor["native"]
        assert isinstance(native, dict)
        assert "pc" in native
        assert "version" in native
        assert isinstance(native["pc"], int)
        assert isinstance(native["version"], int)


# ── validation / rejection tests ──────────────────────────────────────


class TestValidation:
    """read_native_cursor rejects cursors without valid native fields."""

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        assert read_native_cursor(tmp_path) is None

    def test_non_dict_json_raises_corrupt_error(self, tmp_path: Path) -> None:
        (tmp_path / RESUME_CURSOR_FILENAME).write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(NativeCursorCorruptError, match="expected JSON object"):
            read_native_cursor(tmp_path)

    def test_malformed_json_raises_corrupt_error(self, tmp_path: Path) -> None:
        (tmp_path / RESUME_CURSOR_FILENAME).write_text("{", encoding="utf-8")
        with pytest.raises(NativeCursorCorruptError, match="could not be decoded"):
            read_native_cursor(tmp_path)

    def test_missing_native_key_returns_none(self, tmp_path: Path) -> None:
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "stages": [],
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        assert read_native_cursor(tmp_path) is None

    def test_native_not_a_dict_raises_corrupt_error(self, tmp_path: Path) -> None:
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": "not-a-dict",
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        with pytest.raises(NativeCursorCorruptError, match="not a JSON object"):
            read_native_cursor(tmp_path)

    def test_native_missing_pc_raises_corrupt_error(self, tmp_path: Path) -> None:
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": {"version": 1},
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        with pytest.raises(NativeCursorCorruptError, match="required 'pc'"):
            read_native_cursor(tmp_path)

    def test_native_missing_version_raises_corrupt_error(self, tmp_path: Path) -> None:
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": {"pc": 0},
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        with pytest.raises(NativeCursorCorruptError, match="required 'version'"):
            read_native_cursor(tmp_path)

    def test_composite_with_absolute_child_cursor_path_raises_corrupt_error(
        self, tmp_path: Path
    ) -> None:
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": {"pc": 0, "version": 1, "suspension_kind": "child_suspended"},
            "composite": {
                "kind": "parent_child",
                "parent": {
                    "pc": 0,
                    "run_path": "root",
                    "path_stack": [],
                    "state": {},
                    "stages": [],
                    "loops": {},
                    "frames": {},
                },
                "child": {
                    "cursor_path": "/tmp/child/resume_cursor.json",
                    "run_path": "root/child",
                    "call_site_path": ["child"],
                },
            },
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        with pytest.raises(NativeCursorCorruptError, match="child.cursor_path"):
            read_native_cursor(tmp_path)
        with pytest.raises(NativeCursorCorruptError, match="child.cursor_path"):
            classify_resume_cursor(tmp_path)

    def test_composite_with_non_dict_parent_raises_corrupt_error(
        self, tmp_path: Path
    ) -> None:
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": {"pc": 0, "version": 1, "suspension_kind": "child_suspended"},
            "composite": {
                "kind": "parent_child",
                "parent": "not-a-dict",
                "child": {"cursor_path": "child/resume_cursor.json"},
            },
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        with pytest.raises(NativeCursorCorruptError, match="parent and child frames"):
            read_native_cursor(tmp_path)

    def test_native_pc_not_int_raises_corrupt_error(self, tmp_path: Path) -> None:
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": {"pc": "zero", "version": 1},
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        with pytest.raises(NativeCursorCorruptError, match="native.pc"):
            read_native_cursor(tmp_path)

    def test_native_version_not_int_raises_corrupt_error(self, tmp_path: Path) -> None:
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": {"pc": 0, "version": "one"},
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        with pytest.raises(NativeCursorCorruptError, match="native.version"):
            read_native_cursor(tmp_path)

    def test_non_native_cursor_from_base_persist_returns_none(self, tmp_path: Path) -> None:
        """A cursor persisted by the base persist_resume_cursor (no native key)
        should be rejected by read_native_cursor."""
        from arnold.pipeline.resume import persist_resume_cursor

        persist_resume_cursor(
            tmp_path,
            stage="human_review",
            resume_cursor="cursor-1",
            reason="awaiting_human",
        )
        assert read_native_cursor(tmp_path) is None
        assert classify_resume_cursor(tmp_path) == "graph"


# ── edge cases ────────────────────────────────────────────────────────


class TestEdgeCases:
    """Edge case behaviour for persist/read native cursor."""

    def test_empty_stages_loops_frames_default(self, tmp_path: Path) -> None:
        persist_native_cursor(tmp_path, stage="s", pc=1)
        cursor = read_native_cursor(tmp_path)
        assert cursor is not None
        assert cursor["stages"] == []
        assert cursor["loops"] == {}
        assert cursor["frames"] == {}

    def test_explicit_none_stages_normalised_to_empty_list(self, tmp_path: Path) -> None:
        # Simulate an on-disk cursor with None stages
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "stages": None,
            "loops": {},
            "frames": {},
            "native": {"pc": 0, "version": 1},
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        cursor = read_native_cursor(tmp_path)
        assert cursor is not None
        assert cursor["stages"] == []

    def test_explicit_none_loops_normalised_to_empty_dict(self, tmp_path: Path) -> None:
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "stages": [],
            "loops": None,
            "frames": {},
            "native": {"pc": 0, "version": 1},
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        cursor = read_native_cursor(tmp_path)
        assert cursor is not None
        assert cursor["loops"] == {}

    def test_explicit_none_frames_normalised_to_empty_dict(self, tmp_path: Path) -> None:
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "stages": [],
            "loops": {},
            "frames": None,
            "native": {"pc": 0, "version": 1},
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        cursor = read_native_cursor(tmp_path)
        assert cursor is not None
        assert cursor["frames"] == {}

    def test_deeply_nested_frames_preserved(self, tmp_path: Path) -> None:
        deep = {"a": {"b": {"c": [1, 2, 3], "d": None, "e": True}}}
        persist_native_cursor(
            tmp_path,
            stage="s",
            pc=42,
            frames={"loop1": deep},
        )
        cursor = read_native_cursor(tmp_path)
        assert cursor is not None
        assert cursor["frames"] == {"loop1": deep}

    def test_native_cursor_version_constant(self) -> None:
        assert NATIVE_CURSOR_VERSION == 1

    def test_importable_from_package(self) -> None:
        from arnold.pipeline.native import (
            NATIVE_CURSOR_VERSION,
            persist_native_cursor,
            read_native_cursor,
        )
        assert callable(persist_native_cursor)
        assert callable(read_native_cursor)
        assert NATIVE_CURSOR_VERSION == 1
