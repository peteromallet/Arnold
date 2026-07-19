from __future__ import annotations

import sys

from arnold_pipelines.megaplan.planning.operations import _phase_subprocess_command


def test_native_resume_phase_subprocess_uses_safe_path() -> None:
    """A project checkout must not shadow the activated engine on resume."""
    assert _phase_subprocess_command(["critique", "--plan", "demo"]) == [
        sys.executable,
        "-P",
        "-m",
        "arnold_pipelines.megaplan",
        "critique",
        "--plan",
        "demo",
    ]
    assert _phase_subprocess_command(["megaplan", "gate", "--plan", "demo"]) == [
        sys.executable,
        "-P",
        "-m",
        "arnold_pipelines.megaplan",
        "gate",
        "--plan",
        "demo",
    ]
