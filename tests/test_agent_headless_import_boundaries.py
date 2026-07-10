from __future__ import annotations

import subprocess
import sys
import textwrap


def _run_headless_probe(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
        timeout=60,
    )


_FORBIDDEN_IMPORTS = (
    "aiohttp",
    "server",
    "vibecomfy.comfy_nodes.agent.routes",
)


def _assert_headless_probe_passes(code: str) -> None:
    result = _run_headless_probe(code)
    assert result.returncode == 0, result.stderr or result.stdout


def _import_recorder_source() -> str:
    forbidden_repr = repr(_FORBIDDEN_IMPORTS)
    return f"""
        import importlib.abc
        import os
        import sys

        os.environ["VIBECOMFY_HEADLESS"] = "1"
        forbidden = {forbidden_repr}
        attempts = []

        class Recorder(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname in forbidden:
                    attempts.append(fullname)
                return None

        sys.meta_path.insert(0, Recorder())
    """


def test_executor_response_headless_import_does_not_touch_server_or_routes() -> None:
    _assert_headless_probe_passes(
        _import_recorder_source()
        + """
        import vibecomfy.comfy_nodes.agent.executor_response

        loaded = set(sys.modules)
        assert not attempts, sorted(attempts)
        assert not set(forbidden) & loaded, sorted(set(forbidden) & loaded)
        """
    )


def test_executor_durable_headless_import_does_not_touch_server_or_routes() -> None:
    _assert_headless_probe_passes(
        _import_recorder_source()
        + """
        import vibecomfy.comfy_nodes.agent.executor_durable

        loaded = set(sys.modules)
        assert not attempts, sorted(attempts)
        assert not set(forbidden) & loaded, sorted(set(forbidden) & loaded)
        """
    )


def test_provider_readiness_headless_probe_does_not_touch_server_or_routes() -> None:
    _assert_headless_probe_passes(
        _import_recorder_source()
        + """
        from vibecomfy.comfy_nodes.agent import provider

        status = provider.readiness(route="openrouter", model="agent-edit")

        loaded = set(sys.modules)
        assert isinstance(status, dict)
        assert "ready" in status
        assert not attempts, sorted(attempts)
        assert not set(forbidden) & loaded, sorted(set(forbidden) & loaded)
        """
    )
