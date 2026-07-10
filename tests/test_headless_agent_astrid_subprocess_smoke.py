from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_astrid_style_consumer_invokes_cli_and_reads_output_artifacts(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output_dir = tmp_path / "astrid-style-output"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo_root) + os.pathsep + env.get("PYTHONPATH", "")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vibecomfy.agent",
            "--query",
            "Explain this graph from a harness subprocess.",
            "--profile",
            "__missing_profile_for_astrid_style_smoke__",
            "--output-dir",
            str(output_dir),
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 1, result.stderr
    cli_payload = json.loads(result.stdout)
    assert cli_payload["status"] == "blocked_prerequisite"
    assert cli_payload["artifacts"]["output_dir"] == str(output_dir)

    response = _read_json(output_dir / "response.json")
    flow_metadata = _read_json(output_dir / "flow_metadata.json")

    assert response["ok"] is False
    assert response["error"]
    assert flow_metadata["flow_kind"] == "live_agentic_headless"
    assert flow_metadata["dispatcher"] == "real"
    assert flow_metadata["model_behavior"] == "agentic"
    assert flow_metadata["entrypoint"] == "headless_cli"
    assert flow_metadata["status"] == "blocked_prerequisite"
    assert flow_metadata["frontend"] == "not_used"
    assert not any(name == "astrid" or name.startswith("astrid.") for name in sys.modules)
