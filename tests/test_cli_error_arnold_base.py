"""Parity tests: ``CliError`` subclasses ``ArnoldError`` and preserves all five public attributes."""

from __future__ import annotations

import pytest

from arnold.runtime.errors import ArnoldError
from arnold.pipelines.megaplan.types import CliError


class TestCliErrorArnoldBase:
    """Verify that CliError is-a ArnoldError and its full attribute contract is intact."""

    # ── subclass relationship ──────────────────────────────────────────

    def test_cli_error_subclasses_arnold_error(self) -> None:
        assert issubclass(CliError, ArnoldError)

    def test_cli_error_instance_is_arnold_error(self) -> None:
        err = CliError("E_TEST", "test message")
        assert isinstance(err, ArnoldError)

    def test_cli_error_instance_is_exception(self) -> None:
        err = CliError("E_TEST", "test message")
        assert isinstance(err, Exception)

    # ── all five public attributes ─────────────────────────────────────

    def test_code_preserved(self) -> None:
        err = CliError("E_CODE", "msg")
        assert err.code == "E_CODE"

    def test_message_preserved(self) -> None:
        err = CliError("E_CODE", "hello world")
        assert err.message == "hello world"

    def test_valid_next_preserved(self) -> None:
        err = CliError("E_CODE", "msg", valid_next=["review", "execute"])
        assert err.valid_next == ["review", "execute"]

    def test_valid_next_defaults_to_empty_list(self) -> None:
        err = CliError("E_CODE", "msg")
        assert err.valid_next == []

    def test_extra_preserved(self) -> None:
        err = CliError("E_CODE", "msg", extra={"key": "value"})
        assert err.extra == {"key": "value"}

    def test_extra_defaults_to_empty_dict(self) -> None:
        err = CliError("E_CODE", "msg")
        assert err.extra == {}

    def test_exit_code_preserved(self) -> None:
        err = CliError("E_CODE", "msg", exit_code=42)
        assert err.exit_code == 42

    def test_exit_code_defaults_to_1(self) -> None:
        err = CliError("E_CODE", "msg")
        assert err.exit_code == 1

    # ── round-trip through ArnoldError ─────────────────────────────────

    def test_round_trip_via_arnold_error_catch(self) -> None:
        """A CliError caught as ArnoldError still carries all five attributes."""
        err = CliError(
            "E_ROUND",
            "round trip",
            valid_next=["finalize"],
            extra={"ctx": 99},
            exit_code=7,
        )
        assert isinstance(err, ArnoldError)
        assert err.code == "E_ROUND"
        assert err.message == "round trip"
        assert err.valid_next == ["finalize"]
        assert err.extra == {"ctx": 99}
        assert err.exit_code == 7

    # ── str / repr ─────────────────────────────────────────────────────

    def test_str_returns_message(self) -> None:
        err = CliError("E_STR", "display me")
        assert str(err) == "display me"

    def test_repr_includes_class_and_message(self) -> None:
        err = CliError("E_REPR", "repr test")
        r = repr(err)
        assert "CliError" in r
        assert "repr test" in r
