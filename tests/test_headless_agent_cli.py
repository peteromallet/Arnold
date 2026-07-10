from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest


def _main_module() -> Any:
    import vibecomfy.agent.__main__ as cli_mod

    return cli_mod


def test_cli_blocked_on_missing_profile(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output_dir = tmp_path / "out"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo_root) + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vibecomfy.agent",
            "test query",
            "--profile",
            "__missing_profile_for_test__",
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
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked_prerequisite"
    assert payload["ok"] is False
    assert (output_dir / "flow_metadata.json").is_file()


def test_cli_requires_query() -> None:
    cli_mod = _main_module()
    with pytest.raises(SystemExit):
        cli_mod.main([])


def test_cli_successful_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    cli_mod = _main_module()
    from vibecomfy.agent import service as svc

    def fake_run_headless(request: Any, **kwargs: Any) -> Any:
        return svc.HeadlessAgentResult(
            status="success",
            ok=True,
            response={"reply": "hello"},
            artifacts={"output_dir": str(tmp_path / "out")},
        )

    monkeypatch.setattr(svc, "run_headless", fake_run_headless)

    exit_code = cli_mod.main(["test query", "--output-dir", str(tmp_path / "out")])
    assert exit_code == 0


def test_cli_parses_required_flags(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    cli_mod = _main_module()
    from vibecomfy.agent import service as svc

    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text('{"nodes": []}', encoding="utf-8")
    captured: dict[str, Any] = {}

    def fake_run_headless(request: Any, **kwargs: Any) -> Any:
        captured["request"] = request
        captured["kwargs"] = kwargs
        return svc.HeadlessAgentResult(
            status="success",
            ok=True,
            response={"reply": "hello"},
            artifacts={"output_dir": str(tmp_path / "out")},
        )

    monkeypatch.setattr(svc, "run_headless", fake_run_headless)

    exit_code = cli_mod.main(
        [
            "--query",
            "test query",
            "--workflow",
            str(workflow_path),
            "--output",
            str(tmp_path / "out"),
            "--profile",
            "default",
            "--no-live",
            "--dry-run",
            "--research",
            "required",
            "--apply",
            "--no-network",
            "--timeout",
            "12.5",
        ]
    )

    assert exit_code == 0
    request = captured["request"]
    assert request.query == "test query"
    assert request.graph == {"nodes": []}
    assert request.output_dir == str(tmp_path / "out")
    assert request.profile == "default"
    assert request.live is False
    assert request.dry_run is True
    assert request.apply is True
    assert request.network is False
    assert request.timeout == 12.5
    assert request.extra == {"research": "required"}
    assert captured["kwargs"] == {"entrypoint": "headless_cli"}


def test_cli_dry_run_status(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    cli_mod = _main_module()
    from vibecomfy.agent import service as svc

    def fake_run_headless(request: Any, **kwargs: Any) -> Any:
        return svc.HeadlessAgentResult(
            status="dry_run",
            ok=True,
            response={"reply": "[dry-run] classified route: respond"},
            artifacts={"output_dir": str(tmp_path / "out")},
        )

    monkeypatch.setattr(svc, "run_headless", fake_run_headless)

    exit_code = cli_mod.main(["test query", "--dry-run", "--output-dir", str(tmp_path / "out")])
    assert exit_code == 0


def test_cli_json_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    cli_mod = _main_module()
    from vibecomfy.agent import service as svc

    def fake_run_headless(request: Any, **kwargs: Any) -> Any:
        return svc.HeadlessAgentResult(
            status="success",
            ok=True,
            response={"reply": "hello"},
            artifacts={"output_dir": str(tmp_path / "out")},
        )

    monkeypatch.setattr(svc, "run_headless", fake_run_headless)

    captured = io.StringIO()
    monkeypatch.setattr("sys.stdout", captured)
    exit_code = cli_mod.main(["test query", "--output-dir", str(tmp_path / "out"), "--json"])
    assert exit_code == 0
    payload = json.loads(captured.getvalue())
    assert payload["status"] == "success"


@pytest.mark.parametrize(
    ("status", "expected_exit_code"),
    [
        ("success", 0),
        ("dry_run", 0),
        ("blocked_prerequisite", 1),
        ("validation_failure", 2),
        ("executor_failure", 2),
    ],
)
def test_cli_status_exit_code_mapping(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    status: str,
    expected_exit_code: int,
) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    cli_mod = _main_module()
    from vibecomfy.agent import service as svc

    def fake_run_headless(request: Any, **kwargs: Any) -> Any:
        return svc.HeadlessAgentResult(
            status=status,
            ok=status in {"success", "dry_run"},
            response={"reply": status},
            artifacts={"output_dir": str(tmp_path / "out")},
            error="boom" if status in {"validation_failure", "executor_failure"} else None,
        )

    monkeypatch.setattr(svc, "run_headless", fake_run_headless)

    assert cli_mod.main(["test query", "--output-dir", str(tmp_path / "out")]) == expected_exit_code


def test_console_script_entrypoint_registered() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert (
        pyproject["project"]["scripts"]["vibecomfy-agent"]
        == "vibecomfy.agent.__main__:main"
    )
