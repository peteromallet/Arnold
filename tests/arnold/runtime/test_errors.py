"""Unit tests for ``arnold.runtime.errors.ArnoldError``."""

from __future__ import annotations

import pytest

from arnold.runtime.errors import ArnoldError


class TestArnoldError:
    """ArnoldError is the minimal runtime error carrier."""

    def test_constructor_assigns_code_message_exit_code(self) -> None:
        err = ArnoldError("E_PERM", "permission denied", exit_code=13)
        assert err.code == "E_PERM"
        assert err.message == "permission denied"
        assert err.exit_code == 13

    def test_default_exit_code_is_1(self) -> None:
        err = ArnoldError("E_GENERIC", "something went wrong")
        assert err.exit_code == 1

    def test_is_exception_subclass(self) -> None:
        assert issubclass(ArnoldError, Exception)

    def test_str_returns_message(self) -> None:
        err = ArnoldError("E_FOO", "foo happened")
        assert str(err) == "foo happened"

    def test_no_valid_next_attribute(self) -> None:
        """ArnoldError must NOT carry valid_next (that is CLI vocabulary)."""
        err = ArnoldError("E_X", "msg")
        assert not hasattr(err, "valid_next")

    def test_no_extra_attribute(self) -> None:
        """ArnoldError must NOT carry extra (that is CLI vocabulary)."""
        err = ArnoldError("E_X", "msg")
        assert not hasattr(err, "extra")

    def test_importable_from_runtime_package(self) -> None:
        """ArnoldError must be importable via arnold.runtime."""
        from arnold.runtime import ArnoldError as AE  # noqa: F811

        assert AE is ArnoldError

    def test_no_megaplan_substring_in_module(self) -> None:
        """The errors module must not contain the MEGAPLAN_ literal."""
        import arnold.runtime.errors

        source = __import__("inspect").getsource(arnold.runtime.errors)
        assert "MEGAPLAN_" not in source, (
            "arnold/runtime/errors.py must not contain MEGAPLAN_ substring"
        )

    def test_repr_includes_message(self) -> None:
        """repr() delegates to Exception.__repr__, which shows the message."""
        err = ArnoldError("E_REPR", "repr test")
        r = repr(err)
        assert "repr test" in r
        assert "ArnoldError" in r
