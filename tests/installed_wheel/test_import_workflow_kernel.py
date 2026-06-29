from __future__ import annotations

import subprocess


def test_built_wheel_imports_workflow_and_kernel(installed_wheel) -> None:
    result = subprocess.run(
        [
            str(installed_wheel.python),
            "-c",
            "import arnold.workflow, arnold.kernel; print('ok')",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert result.stdout.strip() == "ok"


def test_installed_arnold_workflow_entrypoint_starts(installed_wheel) -> None:
    result = subprocess.run(
        [
            str(installed_wheel.arnold),
            "workflow",
            "--help",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "usage: arnold workflow" in result.stdout
