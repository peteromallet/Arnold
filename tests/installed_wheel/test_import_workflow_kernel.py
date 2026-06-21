from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_editable_install_imports_workflow_and_kernel() -> None:
    repo = Path(__file__).resolve().parents[2]

    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".", "--quiet"],
        cwd=repo,
        check=True,
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import arnold.workflow, arnold.kernel; print('ok')",
        ],
        cwd=repo,
        check=True,
        text=True,
        capture_output=True,
    )

    assert result.stdout.strip() == "ok"
