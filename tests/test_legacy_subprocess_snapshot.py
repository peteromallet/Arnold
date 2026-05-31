"""Gate: legacy subprocess snapshot is importable and contract-correct.

Verifies the pinned ``megaplan/_legacy_subprocess/`` snapshot:
- imports cleanly
- ``PHASE_TIMEOUT_EXIT_CODE`` == 124
- ``legacy_phase_command`` produces identical output to ``auto._phase_command``
- ``legacy_supervise_subprocess`` is callable with correct signature
- functions are not aliased to the *same* object as auto's (they are copies)
"""

from __future__ import annotations

import inspect

import pytest

import megaplan._legacy_subprocess as _snap
import megaplan.auto as _auto


class TestLegacyPhaseCommand:
    """legacy_phase_command must match auto._phase_command output byte-for-byte."""

    CASES: list[tuple[str, list[str]]] = [
        ("execute", ["execute", "--confirm-destructive", "--user-approved",
                      "--retry-blocked-tasks"]),
        ("feedback", ["feedback", "workflow"]),
        ("review", ["review"]),
        ("step", ["step"]),
        ("plan", ["plan"]),
        ("prep", ["prep"]),
        ("critique", ["critique"]),
        ("revise", ["revise"]),
        ("gate", ["gate"]),
        ("finalize", ["finalize"]),
        ("override add-note", ["override", "add-note"]),
        ("override force-proceed", ["override", "force-proceed"]),
        ("override abort", ["override", "abort"]),
    ]

    @pytest.mark.parametrize("next_step,expected", CASES)
    def test_legacy_phase_command_matches_expected(self, next_step, expected):
        assert _snap.legacy_phase_command(next_step) == expected

    @pytest.mark.parametrize("next_step,_", CASES)
    def test_legacy_phase_command_matches_auto(self, next_step, _):
        """legacy output must be byte-identical to the live auto._phase_command."""
        assert _snap.legacy_phase_command(next_step) == _auto._phase_command(next_step)

    def test_legacy_phase_command_is_separate_object(self):
        """The legacy function must be a copy, not a reference to auto's."""
        assert _snap.legacy_phase_command is not _auto._phase_command


class TestLegacyConstants:
    """Verbatim constants must match the live auto.py values."""

    def test_phase_timeout_exit_code(self):
        assert _snap.PHASE_TIMEOUT_EXIT_CODE == 124
        assert _snap.PHASE_TIMEOUT_EXIT_CODE == _auto.PHASE_TIMEOUT_EXIT_CODE

    def test_default_phase_heartbeat_seconds(self):
        assert _snap.DEFAULT_PHASE_HEARTBEAT_SECONDS == 60.0
        assert (
            _snap.DEFAULT_PHASE_HEARTBEAT_SECONDS
            == _auto.DEFAULT_PHASE_HEARTBEAT_SECONDS
        )


class TestLegacySuperviseSubprocess:
    """legacy_supervise_subprocess must be importable with the right signature."""

    def test_is_callable(self):
        assert callable(_snap.legacy_supervise_subprocess)

    def test_signature_accepts_all_keyword_args(self):
        sig = inspect.signature(_snap.legacy_supervise_subprocess)
        params = sig.parameters
        assert "args" in params
        assert "cwd" in params
        assert "timeout" in params
        assert "idle_timeout" in params
        assert "env" in params
        assert "liveness_plan_dir" in params

    def test_auto_run_megaplan_is_retired(self):
        """auto no longer exposes the legacy subprocess command seam."""
        assert not hasattr(_auto, "_run_megaplan")
        assert _snap.legacy_supervise_subprocess is not _auto._run_planning_phase

    def test_returns_tuple_on_trivial_invocation(self, tmp_path):
        """Call with a trivial command that exits quickly — smoke test."""
        code, stdout, stderr = _snap.legacy_supervise_subprocess(
            ["--help"],
            timeout=10.0,
            cwd=tmp_path,
        )
        assert isinstance(code, int)
        assert isinstance(stdout, str)
        assert isinstance(stderr, str)
        assert code == 0


class TestReadOnlyMarker:
    """Module docstring must carry the READ-ONLY pin."""

    def test_module_docstring_has_read_only(self):
        doc = _snap.__doc__ or ""
        assert "READ-ONLY" in doc

    def test_module_docstring_has_do_not_edit(self):
        doc = _snap.__doc__ or ""
        assert "DO NOT EDIT" in doc


class TestInternalHelpersPresent:
    """The snapshot must include the internal helpers the watcher depends on."""

    def test_plan_liveness_mtime_present(self):
        assert callable(_snap._plan_liveness_mtime)

    def test_phase_heartbeat_interval_present(self):
        assert callable(_snap._phase_heartbeat_interval_seconds)

    def test_format_phase_heartbeat_present(self):
        assert callable(_snap._format_phase_heartbeat)

    def test_phase_command_internal_present(self):
        assert callable(_snap._phase_command)
