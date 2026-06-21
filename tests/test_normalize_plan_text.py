from __future__ import annotations

import pytest

from arnold.pipelines.megaplan.handlers.shared import _normalize_plan_text


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("already\nhas newlines\n", "already\nhas newlines\n"),
        (
            "line 1\\nline 2\\nline 3",
            "line 1\nline 2\nline 3",
        ),
        (
            "line 1\\r\\nline 2\\r\\nline 3",
            "line 1\nline 2\nline 3",
        ),
        (
            "no newlines and no escapes",
            "no newlines and no escapes",
        ),
    ],
)
def test_normalize_plan_text_decodes_literal_newlines(raw: str, expected: str) -> None:
    assert _normalize_plan_text(raw) == expected
