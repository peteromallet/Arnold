"""Tests for PhaseResult transport — explicit auto↔phase boundary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from megaplan.orchestration.phase_result import (
    BlockedTask,
    Deviation,
    ExitKind,
    ExternalError,
    PhaseResult,
    _emit_phase_result,
    atomic_write_phase_result,
    generate_invocation_id,
    phase_result_guard,
    read_phase_result,
    validate_phase_result,
)
from megaplan.types import CliError


# ---------------------------------------------------------------------------
# (1) PhaseResult JSON round-trip
# ---------------------------------------------------------------------------


class TestPhaseResultRoundTrip:
    """PhaseResult serialises and deserialises losslessly."""

    def test_minimal_round_trip(self) -> None:
        original = PhaseResult(
            phase="execute",
            invocation_id="abc123",
            exit_kind=ExitKind.success.value,
        )
        as_dict = original.to_dict()
        restored = PhaseResult.from_dict(as_dict)
        assert restored.phase == original.phase
        assert restored.invocation_id == original.invocation_id
        assert restored.exit_kind == original.exit_kind
        assert restored.blocked_tasks == ()
        assert restored.deviations == ()
        assert restored.artifacts_written == ()
        assert restored.cli_provenance == {}

    def test_full_round_trip(self) -> None:
        original = PhaseResult(
            phase="execute",
            invocation_id="abc123",
            exit_kind=ExitKind.blocked_by_prereq.value,
            blocked_tasks=(
                BlockedTask(task_id="T1", reason="missing env", notes="set API_KEY"),
                BlockedTask(task_id="T2", reason="user action"),
            ),
            deviations=(
                Deviation(kind="quality_gate", message="task missing evidence", task_id="T3"),
                Deviation(kind="advisory", message="file count high"),
            ),
            artifacts_written=("execution.json", "final.md"),
            cli_provenance={"args": ["--plan", "test"], "cwd": "/tmp"},
        )
        as_dict = original.to_dict()
        restored = PhaseResult.from_dict(as_dict)

        assert restored.phase == original.phase
        assert restored.invocation_id == original.invocation_id
        assert restored.exit_kind == original.exit_kind
        assert restored.cli_provenance == original.cli_provenance
        assert restored.artifacts_written == original.artifacts_written

        assert len(restored.blocked_tasks) == 2
        assert restored.blocked_tasks[0].task_id == "T1"
        assert restored.blocked_tasks[0].reason == "missing env"
        assert restored.blocked_tasks[0].notes == "set API_KEY"
        assert restored.blocked_tasks[1].task_id == "T2"
        assert restored.blocked_tasks[1].reason == "user action"
        assert restored.blocked_tasks[1].notes == ""

        assert len(restored.deviations) == 2
        assert restored.deviations[0].kind == "quality_gate"
        assert restored.deviations[0].message == "task missing evidence"
        assert restored.deviations[0].task_id == "T3"
        assert restored.deviations[1].task_id is None

    def test_missing_optional_is_empty(self) -> None:
        d = {
            "phase": "plan",
            "invocation_id": "xyz",
            "exit_kind": "success",
            "artifacts_written": [],
            "cli_provenance": {},
            "blocked_tasks": [],
            "deviations": [],
        }
        result = PhaseResult.from_dict(d)
        assert result.phase == "plan"
        assert result.blocked_tasks == ()
        assert result.deviations == ()
        assert result.artifacts_written == ()
        assert result.cli_provenance == {}

    def test_exit_kind_enum_property(self) -> None:
        result = PhaseResult(
            phase="gate", invocation_id="id", exit_kind=ExitKind.blocked_by_quality.value
        )
        assert result.exit_kind_enum is ExitKind.blocked_by_quality


# ---------------------------------------------------------------------------
# (2) Schema validation
# ---------------------------------------------------------------------------


class TestValidatePhaseResult:
    """Structural validation rejects invalid payloads."""

    def test_rejects_invalid_exit_kind(self) -> None:
        payload = {
            "phase": "execute",
            "invocation_id": "abc",
            "exit_kind": "garbage_kind",
            "blocked_tasks": [],
            "deviations": [],
            "artifacts_written": [],
            "cli_provenance": {},
        }
        with pytest.raises(CliError, match="exit_kind must be one of"):
            validate_phase_result(payload)

    def test_rejects_missing_required_fields(self) -> None:
        payload = {"phase": "execute"}
        with pytest.raises(CliError, match="missing required fields"):
            validate_phase_result(payload)

    def test_rejects_non_dict(self) -> None:
        with pytest.raises(CliError, match="must be a dict"):
            validate_phase_result("not a dict")  # type: ignore[arg-type]

    def test_rejects_empty_phase(self) -> None:
        payload = {
            "phase": "",
            "invocation_id": "abc",
            "exit_kind": "success",
            "blocked_tasks": [],
            "deviations": [],
            "artifacts_written": [],
            "cli_provenance": {},
        }
        with pytest.raises(CliError, match="must be a non-empty string"):
            validate_phase_result(payload)

    def test_rejects_empty_invocation_id(self) -> None:
        payload = {
            "phase": "execute",
            "invocation_id": "",
            "exit_kind": "success",
            "blocked_tasks": [],
            "deviations": [],
            "artifacts_written": [],
            "cli_provenance": {},
        }
        with pytest.raises(CliError, match="must be a non-empty string"):
            validate_phase_result(payload)

    def test_rejects_bad_artifacts_written(self) -> None:
        payload = {
            "phase": "execute",
            "invocation_id": "abc",
            "exit_kind": "success",
            "blocked_tasks": [],
            "deviations": [],
            "artifacts_written": [1, 2, 3],  # not strings
            "cli_provenance": {},
        }
        with pytest.raises(CliError, match="list of strings"):
            validate_phase_result(payload)

    def test_rejects_bad_cli_provenance(self) -> None:
        payload = {
            "phase": "execute",
            "invocation_id": "abc",
            "exit_kind": "success",
            "blocked_tasks": [],
            "deviations": [],
            "artifacts_written": [],
            "cli_provenance": "not a dict",
        }
        with pytest.raises(CliError, match="must be a dict"):
            validate_phase_result(payload)

    def test_rejects_bad_blocked_tasks_nested(self) -> None:
        payload = {
            "phase": "execute",
            "invocation_id": "abc",
            "exit_kind": "success",
            "blocked_tasks": ["not an object"],
            "deviations": [],
            "artifacts_written": [],
            "cli_provenance": {},
        }
        with pytest.raises(CliError, match="must be an object"):
            validate_phase_result(payload)

    def test_rejects_blocked_task_missing_task_id(self) -> None:
        payload = {
            "phase": "execute",
            "invocation_id": "abc",
            "exit_kind": "success",
            "blocked_tasks": [{"reason": "x"}],
            "deviations": [],
            "artifacts_written": [],
            "cli_provenance": {},
        }
        with pytest.raises(CliError, match="missing task_id"):
            validate_phase_result(payload)

    def test_rejects_bad_deviations_nested(self) -> None:
        payload = {
            "phase": "execute",
            "invocation_id": "abc",
            "exit_kind": "success",
            "blocked_tasks": [],
            "deviations": [{"message": "x"}],  # missing 'kind'
            "artifacts_written": [],
            "cli_provenance": {},
        }
        with pytest.raises(CliError, match="missing kind or message"):
            validate_phase_result(payload)

    def test_accepts_valid_payload(self) -> None:
        payload = {
            "phase": "execute",
            "invocation_id": "abc",
            "exit_kind": "success",
            "blocked_tasks": [],
            "deviations": [],
            "artifacts_written": [],
            "cli_provenance": {},
        }
        # Should not raise
        validate_phase_result(payload)


# ---------------------------------------------------------------------------
# (3) Atomic I/O
# ---------------------------------------------------------------------------


class TestAtomicIO:
    """atomic_write_phase_result writes; read_phase_result reads it back."""

    def test_write_and_read(self, tmp_path: Path) -> None:
        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        result = PhaseResult(
            phase="execute",
            invocation_id="abc",
            exit_kind=ExitKind.success.value,
            artifacts_written=("a.json", "b.md"),
            cli_provenance={"mode": "auto"},
        )
        atomic_write_phase_result(plan_dir, result)

        path = plan_dir / "phase_result.json"
        assert path.is_file()

        restored = read_phase_result(plan_dir)
        assert restored is not None
        assert restored.phase == "execute"
        assert restored.invocation_id == "abc"
        assert restored.exit_kind == ExitKind.success.value
        assert restored.cli_provenance == {"mode": "auto"}
        assert restored.artifacts_written == ("a.json", "b.md")

    def test_read_missing_file(self, tmp_path: Path) -> None:
        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        assert read_phase_result(plan_dir) is None

    def test_atomic_write_overwrites(self, tmp_path: Path) -> None:
        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        r1 = PhaseResult(phase="plan", invocation_id="id1", exit_kind="success")
        r2 = PhaseResult(phase="execute", invocation_id="id2", exit_kind="blocked_by_quality")

        atomic_write_phase_result(plan_dir, r1)
        atomic_write_phase_result(plan_dir, r2)

        restored = read_phase_result(plan_dir)
        assert restored is not None
        assert restored.phase == "execute"
        assert restored.invocation_id == "id2"
        assert restored.exit_kind == ExitKind.blocked_by_quality.value


# ---------------------------------------------------------------------------
# (4) phase_result_guard
# ---------------------------------------------------------------------------


class TestPhaseResultGuard:
    """phase_result_guard context manager behaviour."""

    def _write_state_file(self, plan_dir: Path, invocation_id: str | None, step: str = "plan") -> None:
        state_path = plan_dir / "state.json"
        data: dict = {
            "meta": {},
            "active_step": {"step": step},
        }
        if invocation_id is not None:
            data["meta"]["current_invocation_id"] = invocation_id
        state_path.write_text(json.dumps(data), encoding="utf-8")

    def test_keyboard_interrupt_propagates_without_writing(self, tmp_path: Path) -> None:
        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        self._write_state_file(plan_dir, "abc123")

        with pytest.raises(KeyboardInterrupt):
            with phase_result_guard(plan_dir):
                raise KeyboardInterrupt()

        assert not (plan_dir / "phase_result.json").exists()

    def test_system_exit_propagates_without_writing(self, tmp_path: Path) -> None:
        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        self._write_state_file(plan_dir, "abc123")

        with pytest.raises(SystemExit):
            with phase_result_guard(plan_dir):
                raise SystemExit(1)

        assert not (plan_dir / "phase_result.json").exists()

    def test_emit_internal_error_on_guarded_exception(self, tmp_path: Path) -> None:
        """When set_active_step has run (invocation_id exists), exception
        emits internal_error phase_result.json and re-raises."""
        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        self._write_state_file(plan_dir, "abc123")

        class TestError(Exception):
            pass

        with pytest.raises(TestError):
            with phase_result_guard(plan_dir):
                raise TestError("test error")

        restored = read_phase_result(plan_dir)
        assert restored is not None
        assert restored.exit_kind == ExitKind.internal_error.value
        assert restored.invocation_id == "abc123"

    def test_skip_emission_without_invocation_id(self, tmp_path: Path) -> None:
        """When state.json has no invocation_id, exception re-raises WITHOUT
        writing phase_result.json."""
        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        self._write_state_file(plan_dir, None)

        class TestError(Exception):
            pass

        with pytest.raises(TestError):
            with phase_result_guard(plan_dir):
                raise TestError("early error")

        assert not (plan_dir / "phase_result.json").exists()

    def test_skip_emission_without_state_json(self, tmp_path: Path) -> None:
        """When state.json doesn't exist at all, exception re-raises WITHOUT
        writing phase_result.json."""
        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()

        class TestError(Exception):
            pass

        with pytest.raises(TestError):
            with phase_result_guard(plan_dir):
                raise TestError("pre setup error")

        assert not (plan_dir / "phase_result.json").exists()

    def test_emits_timeout_for_timeout_expired(self, tmp_path: Path) -> None:
        """subprocess.TimeoutExpired → exit_kind='timeout'."""
        import subprocess

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        self._write_state_file(plan_dir, "abc123")

        with pytest.raises(subprocess.TimeoutExpired):
            with phase_result_guard(plan_dir):
                raise subprocess.TimeoutExpired(cmd="test", timeout=5)

        restored = read_phase_result(plan_dir)
        assert restored is not None
        assert restored.exit_kind == ExitKind.timeout.value


# ---------------------------------------------------------------------------
# (5) _emit_phase_result RuntimeError
# ---------------------------------------------------------------------------


class TestEmitPhaseResult:
    """_emit_phase_result contract."""

    def test_skips_on_missing_invocation_id(self, tmp_path: Path) -> None:
        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        state: dict = {"meta": {}}
        # Should NOT raise — instead log a warning and skip emission
        _emit_phase_result("execute", state, plan_dir, exit_kind="success")
        # Verify no phase_result.json was written
        assert not (plan_dir / "phase_result.json").exists()

    def test_emits_successfully(self, tmp_path: Path) -> None:
        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        inv_id = generate_invocation_id()
        state = {"meta": {"current_invocation_id": inv_id}}

        _emit_phase_result(
            "execute",
            state,
            plan_dir,
            exit_kind=ExitKind.success.value,
            blocked_tasks=(BlockedTask(task_id="T1", reason="blocked"),),
            deviations=(Deviation(kind="quality", message="issue"),),
            artifacts_written=("a.json",),
            cli_provenance={"args": ["--plan"]},
        )

        restored = read_phase_result(plan_dir)
        assert restored is not None
        assert restored.phase == "execute"
        assert restored.invocation_id == inv_id
        assert restored.exit_kind == ExitKind.success.value
        assert len(restored.blocked_tasks) == 1
        assert len(restored.deviations) == 1
        assert restored.artifacts_written == ("a.json",)
        assert restored.cli_provenance == {"args": ["--plan"]}


# ---------------------------------------------------------------------------
# (6) Utility types
# ---------------------------------------------------------------------------


class TestBlockedTask:
    def test_to_dict_from_dict(self) -> None:
        bt = BlockedTask(task_id="T1", reason="missing", notes="set env")
        d = bt.to_dict()
        assert d == {"task_id": "T1", "reason": "missing", "notes": "set env"}
        restored = BlockedTask.from_dict(d)
        assert restored.task_id == "T1"
        assert restored.reason == "missing"
        assert restored.notes == "set env"

    def test_defaults(self) -> None:
        bt = BlockedTask(task_id="T99", reason="test")
        assert bt.notes == ""
        d = bt.to_dict()
        assert d["notes"] == ""


class TestDeviation:
    def test_to_dict_from_dict(self) -> None:
        d = Deviation(kind="quality", message="msg", task_id="T3")
        dd = d.to_dict()
        assert dd == {"kind": "quality", "message": "msg", "task_id": "T3"}
        restored = Deviation.from_dict(dd)
        assert restored.kind == "quality"
        assert restored.message == "msg"
        assert restored.task_id == "T3"

    def test_from_string(self) -> None:
        d = Deviation.from_string("missing files_changed")
        assert d.kind == "quality_gate"
        assert d.message == "missing files_changed"
        assert d.task_id is None


# ---------------------------------------------------------------------------
# (7) generate_invocation_id uniqueness
# ---------------------------------------------------------------------------


class TestGenerateInvocationId:
    def test_is_16_char_hex(self) -> None:
        inv_id = generate_invocation_id()
        assert len(inv_id) == 16
        assert all(c in "0123456789abcdef" for c in inv_id)

    def test_unique_across_calls(self) -> None:
        ids = {generate_invocation_id() for _ in range(100)}
        assert len(ids) == 100, "expected unique IDs across calls"


# ---------------------------------------------------------------------------
# (8) ExternalError classification and transport
# ---------------------------------------------------------------------------


class TestExternalError:
    def test_round_trip(self) -> None:
        error = ExternalError(
            provider="deepseek",
            error_kind="rate_limit",
            message="429 Too Many Requests",
            status_code=429,
            retry_after_s=30.0,
            request_id="req_123",
            provider_error_code="429",
            error_layer="provider_response",
            stall_timeout_s=60.0,
            elapsed_s=61.5,
            content_chunk_count=3,
            reasoning_chunk_count=7,
        )

        restored = ExternalError.from_dict(error.to_dict())

        assert restored == error

    @pytest.mark.parametrize(
        ("message", "kind", "status"),
        [
            ("429 Too Many Requests retry_after: 12", "rate_limit", 429),
            ("402 Payment Required: insufficient balance", "balance", 402),
            ("401 Unauthorized: invalid API key", "auth", 401),
            ("HTTP 403 Forbidden", "auth", 403),
            ("502 Bad Gateway from provider", "provider_failure", 502),
            ("Connection timed out while contacting API", "network", None),
        ],
    )
    def test_from_exception_classifies_external_failures(
        self,
        message: str,
        kind: str,
        status: int | None,
    ) -> None:
        error = ExternalError.from_exception(RuntimeError(message), provider="deepseek")

        assert error is not None
        assert error.provider == "deepseek"
        assert error.error_kind == kind
        assert error.status_code == status

    def test_from_exception_does_not_match_incidental_rate_substrings(self) -> None:
        assert ExternalError.from_exception(ValueError("failed to generate artifact")) is None

    def test_from_exception_preserves_structured_stream_stall_metadata(self) -> None:
        exc = RuntimeError("Request timed out.")
        exc.extra = {
            "external_error": {
                "provider": "unknown",
                "error_kind": "stream_content_stall",
                "message": "Streaming response stalled without content or reasoning progress.",
                "provider_error_code": "timeout",
                "error_layer": "stream_content_stall",
                "stall_timeout_s": 60.0,
                "elapsed_s": 454.0,
                "content_chunk_count": 182,
                "reasoning_chunk_count": 0,
            }
        }

        error = ExternalError.from_exception(exc, provider="deepseek")

        assert error is not None
        assert error.provider == "deepseek"
        assert error.error_kind == "stream_content_stall"
        assert error.provider_error_code == "timeout"
        assert error.error_layer == "stream_content_stall"
        assert error.stall_timeout_s == 60.0
        assert error.elapsed_s == 454.0
        assert error.content_chunk_count == 182
        assert error.reasoning_chunk_count == 0

    def test_phase_result_round_trip_with_external_error(self) -> None:
        error = ExternalError(
            provider="openrouter",
            error_kind="auth",
            message="bad key",
            status_code=401,
        )
        result = PhaseResult(
            phase="execute",
            invocation_id="inv",
            exit_kind=ExitKind.external_error.value,
            external_error=error,
        )

        restored = PhaseResult.from_dict(result.to_dict())

        assert restored.exit_kind == ExitKind.external_error.value
        assert restored.external_error == error

    def test_phase_result_guard_emits_external_error(self, tmp_path: Path) -> None:
        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "meta": {"current_invocation_id": "inv"},
                    "active_step": {"step": "execute"},
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(RuntimeError):
            with phase_result_guard(plan_dir):
                raise RuntimeError("429 Too Many Requests retry_after: 9")

        result = read_phase_result(plan_dir)
        assert result is not None
        assert result.exit_kind == ExitKind.external_error.value
        assert result.external_error is not None
        assert result.external_error.error_kind == "rate_limit"
        assert result.external_error.retry_after_s == 9.0

    def test_phase_result_guard_classifies_shannon_worker_stall(self, tmp_path: Path) -> None:
        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "meta": {"current_invocation_id": "inv"},
                    "active_step": {"step": "plan"},
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(CliError):
            with phase_result_guard(plan_dir):
                raise CliError(
                    "worker_stall",
                    "Worker produced no output for 240s (stalled stream): shannon --model claude-opus-4-7...",
                )

        result = read_phase_result(plan_dir)
        assert result is not None
        assert result.exit_kind == ExitKind.external_error.value
        assert result.external_error is not None
        assert result.external_error.provider in {"shannon", "claude"}
        assert result.external_error.error_kind == "stalled_stream"
