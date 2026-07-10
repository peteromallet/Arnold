"""LIVE AGENTIC TESTS.

Live agentic harness tests using real DeepSeek models via OpenRouter.

These tests call the actual model backend.  They are skipped automatically when
no OpenRouter/DeepSeek credential is available, and they keep token budgets
tight so the calls stay small.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any, Generator

import pytest

from tests.live_agentic_harness.guard import guard_output_dir
from vibecomfy.agent.contracts import HeadlessAgentRequest
from vibecomfy.executor.profiles import set_profile_override_dir


_LIVE_MODEL = os.getenv("VIBECOMFY_LIVE_TEST_MODEL", "deepseek/deepseek-chat")
_LIVE_MAX_TOKENS = os.getenv("VIBECOMFY_LIVE_TEST_MAX_TOKENS", "1024")


def _write_toml(dir_path: Path, name: str, content: str) -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"{name}.toml"
    file_path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return file_path


@pytest.fixture
def profile_dir(tmp_path: Path) -> Generator[Path, None, None]:
    dir_path = tmp_path / "profiles"
    profile = f"""
    [classify]
    agent = "hermes"
    model = "openrouter:{_LIVE_MODEL}"
    effort = "low"

    [research]
    agent = "hermes"
    model = "openrouter:{_LIVE_MODEL}"
    effort = "medium"

    [implement]
    agent = "hermes"
    model = "openrouter:{_LIVE_MODEL}"
    effort = "medium"

    [reply]
    agent = "hermes"
    model = "openrouter:{_LIVE_MODEL}"
    effort = "low"
    """
    _write_toml(dir_path, "default", profile)
    set_profile_override_dir(dir_path)
    yield dir_path
    set_profile_override_dir(None)


@pytest.fixture
def live_readiness() -> dict[str, Any]:
    """Probe OpenRouter readiness and skip the test if no credential is present."""
    os.environ["VIBECOMFY_HEADLESS"] = "1"
    from vibecomfy.comfy_nodes.agent import provider

    status = provider.readiness(route="openrouter", model=_LIVE_MODEL)
    if not status.get("ready"):
        pytest.skip(f"Live DeepSeek/OpenRouter not ready: {status.get('reason')}")
    return status


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _pretty(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, default=str)


def _minimal_graph() -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": 1,
                "class_type": "CheckpointLoaderSimple",
                "inputs": [],
                "outputs": [{"name": "MODEL"}, {"name": "CLIP"}, {"name": "VAE"}],
            },
            {
                "id": 2,
                "class_type": "CLIPTextEncode",
                "inputs": [{"name": "clip", "link": 1}],
                "outputs": [{"name": "CONDITIONING"}],
            },
            {
                "id": 3,
                "class_type": "KSampler",
                "inputs": [
                    {"name": "model", "link": 2},
                    {"name": "positive", "link": 3},
                ],
                "outputs": [{"name": "LATENT"}],
            },
        ],
        "links": [
            [1, 1, 1, 2, 0, "CLIP"],
            [2, 1, 0, 3, 0, "MODEL"],
            [3, 2, 0, 3, 1, "CONDITIONING"],
        ],
    }


@pytest.mark.live
def test_live_deepseek_headless_graph_explanation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    profile_dir: Path,
    live_readiness: dict[str, Any],
) -> None:
    """Run a real DeepSeek classify + reply through the headless service."""
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    monkeypatch.setenv("VIBECOMFY_AGENT_TURN_TIMEOUT", "120")
    monkeypatch.setenv("VIBECOMFY_OPENROUTER_MAX_TOKENS", _LIVE_MAX_TOKENS)

    from vibecomfy.agent import service as svc

    # Keep durable session artifacts inside the test tmp dir.
    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.executor_durable.DEFAULT_SESSION_ROOT",
        tmp_path / "sessions",
    )

    output_dir = tmp_path / "live-inspect-out"
    request = HeadlessAgentRequest(
        query="Explain what this graph does in one sentence.",
        graph=_minimal_graph(),
        output_dir=output_dir,
        live=True,
        profile="default",
    )

    result = svc.run_headless(request, entrypoint="agentic_live")

    # ── Deep diagnostics (printed so failures and -s runs show what happened) ──
    print("\n=== live readiness ===")
    print(_pretty({k: v for k, v in live_readiness.items() if "key" not in k.lower()}))
    print("\n=== headless result ===")
    print(_pretty(result.to_dict()))

    assert result.status == "success", result
    assert result.ok is True

    classification = _read_json(output_dir / "classification.json")
    response = _read_json(output_dir / "response.json")
    flow_metadata = _read_json(output_dir / "flow_metadata.json")

    print("\n=== classification.json ===")
    print(_pretty(classification))
    print("\n=== response.json ===")
    print(_pretty(response))
    print("\n=== flow_metadata.json ===")
    print(_pretty(flow_metadata))

    assert classification["route"] in {"inspect", "respond"}
    assert response["ok"] is True
    reply = response.get("reply", "")
    assert isinstance(reply, str) and reply.strip()
    print(f"\n=== model reply ===\n{reply}")
    assert flow_metadata["dispatcher"] == "real"
    assert flow_metadata["model_behavior"] == "agentic"
    assert flow_metadata["live"] is True
    assert flow_metadata["status"] == "success"

    guard = guard_output_dir(output_dir)
    print("\n=== guard verdict ===")
    print(_pretty(guard))
    assert guard["live_agentic_success"] is True


@pytest.mark.live
def test_live_deepseek_harness_runner_graph_explanation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    profile_dir: Path,
    live_readiness: dict[str, Any],
) -> None:
    """Run a real DeepSeek scenario through the agentic harness runner."""
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    monkeypatch.setenv("VIBECOMFY_AGENT_TURN_TIMEOUT", "120")
    monkeypatch.setenv("VIBECOMFY_OPENROUTER_MAX_TOKENS", _LIVE_MAX_TOKENS)

    from tests.live_agentic_harness.runner import run_tag

    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.executor_durable.DEFAULT_SESSION_ROOT",
        tmp_path / "sessions",
    )

    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir(parents=True, exist_ok=True)
    scenario_path = scenarios_dir / "live-graph-explanation.json"
    scenario_path.write_text(
        json.dumps(
            {
                "id": "live-graph-explanation",
                "query": "Explain what this graph does in one sentence.",
                "graph": _minimal_graph(),
                "profile": "default",
            }
        ),
        encoding="utf-8",
    )

    summary = run_tag(
        "live-run",
        scenarios_dir=scenarios_dir,
        output_base=tmp_path / "out",
    )

    print("\n=== harness runner summary ===")
    print(_pretty(summary))

    assert summary["tag"] == "live-run"
    assert summary["scenario_count"] == 1
    assert summary["overall_success"] is True

    scenario_summary = summary["scenarios"][0]
    assert scenario_summary["scenario_id"] == "live-graph-explanation"
    assert scenario_summary["status"] == "success"
    assert scenario_summary["ok"] is True
    assert scenario_summary["guard"]["live_agentic_success"] is True

    output_dir = Path(scenario_summary["output_dir"])
    response = _read_json(output_dir / "response.json")
    assert response["ok"] is True
    assert isinstance(response.get("reply", ""), str) and response["reply"].strip()


@pytest.mark.live
def test_live_deepseek_astrid_subprocess_graph_explanation(
    tmp_path: Path,
    live_readiness: dict[str, Any],
) -> None:
    """Run the headless CLI as an external process, as Astrid would invoke it."""
    repo_root = Path(__file__).resolve().parents[1]
    output_dir = tmp_path / "live-cli-out"

    graph_path = tmp_path / "workflow.json"
    graph_path.write_text(json.dumps(_minimal_graph()), encoding="utf-8")

    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo_root) + os.pathsep + env.get("PYTHONPATH", "")
    env["VIBECOMFY_HEADLESS"] = "1"
    env["VIBECOMFY_AGENT_TURN_TIMEOUT"] = "120"
    env["VIBECOMFY_OPENROUTER_MAX_TOKENS"] = _LIVE_MAX_TOKENS

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vibecomfy.agent",
            "--query",
            "Explain what this graph does in one sentence.",
            "--workflow",
            str(graph_path),
            "--profile",
            "default",
            "--output-dir",
            str(output_dir),
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )

    print("\n=== Astrid-style CLI stdout ===")
    print(result.stdout)
    if result.stderr:
        print("\n=== Astrid-style CLI stderr ===")
        print(result.stderr)

    assert result.returncode == 0, result.stderr
    cli_payload = json.loads(result.stdout)

    print("\n=== CLI payload ===")
    print(_pretty(cli_payload))

    assert cli_payload["status"] == "success"
    assert cli_payload["ok"] is True

    response = _read_json(output_dir / "response.json")
    flow_metadata = _read_json(output_dir / "flow_metadata.json")

    assert response["ok"] is True
    assert isinstance(response.get("reply", ""), str) and response["reply"].strip()
    assert flow_metadata["flow_kind"] == "live_agentic_headless"
    assert flow_metadata["dispatcher"] == "real"
    assert flow_metadata["model_behavior"] == "agentic"
    assert flow_metadata["entrypoint"] == "headless_cli"
    assert flow_metadata["status"] == "success"

    guard = guard_output_dir(output_dir)
    assert guard["live_agentic_success"] is True
