from __future__ import annotations

from pathlib import Path


_ROOT_CONFTST = Path(__file__).with_name("conftest.py")


def _write_marker_fixture(pytester) -> None:
    pytester.makeconftest(_ROOT_CONFTST.read_text(encoding="utf-8"))
    pytester.makepyfile(
        test_runpod_markers="""
import pytest


def test_plain():
    assert True


@pytest.mark.runpod
def test_runpod():
    assert True


@pytest.mark.runpod_full
def test_runpod_full():
    assert True


@pytest.mark.runpod
@pytest.mark.runpod_full
def test_runpod_and_full():
    assert True
"""
    )


def test_default_excludes_runpod_and_runpod_full(pytester) -> None:
    _write_marker_fixture(pytester)
    result = pytester.runpytest("-q")
    result.assert_outcomes(passed=1, deselected=3)


def test_runpod_includes_regular_only(pytester) -> None:
    _write_marker_fixture(pytester)
    result = pytester.runpytest("-q", "--runpod")
    result.assert_outcomes(passed=2, deselected=2)


def test_runpod_full_includes_regular_and_full(pytester) -> None:
    _write_marker_fixture(pytester)
    result = pytester.runpytest("-q", "--runpod-full")
    result.assert_outcomes(passed=4)
