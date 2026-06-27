"""Import-cost regression guard for vibecomfy.testing (T5)."""
from __future__ import annotations

import subprocess
import sys


def _run_import_cost_probe(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_importing_vibecomfy_root_does_not_pull_cross_layer_runtime_modules():
    """Subprocess so we measure a clean module table."""
    code = (
        "import vibecomfy, sys; "
        "assert 'workflow_from_template' in vibecomfy.__all__; "
        "assert 'run_embedded_sync' in vibecomfy.__all__; "
        "forbidden = {"
        "'vibecomfy.runtime.client', 'vibecomfy.runtime.server', "
        "'vibecomfy.schema.provider', 'vibecomfy.comfy_command'"
        "}; "
        "loaded = forbidden & set(sys.modules); "
        "assert not loaded, sorted(loaded); "
        "from vibecomfy.registry.library import workflow_from_template; "
        "assert vibecomfy.workflow_from_template is workflow_from_template"
    )
    result = _run_import_cost_probe(code)
    assert result.returncode == 0, result.stderr


def test_importing_vibecomfy_testing_does_not_pull_runtime_or_comfy_command():
    """Subprocess so we measure a clean module table."""
    code = (
        "import vibecomfy.testing, sys; "
        "forbidden = {'vibecomfy.runtime.client', 'vibecomfy.runtime.server', 'vibecomfy.comfy_command'}; "
        "loaded = forbidden & set(sys.modules); "
        "assert not loaded, sorted(loaded)"
    )
    result = _run_import_cost_probe(code)
    assert result.returncode == 0, result.stderr


def test_importing_vibecomfy_agent_does_not_register_comfyui_routes():
    """Future headless package must stay import-safe when it appears."""
    code = (
        "import importlib.util, os, sys; "
        "os.environ.setdefault('VIBECOMFY_HEADLESS', '1'); "
        "spec = importlib.util.find_spec('vibecomfy.agent'); "
        "spec and __import__('vibecomfy.agent'); "
        "forbidden = {"
        "'aiohttp', 'server', 'vibecomfy.comfy_nodes.agent.routes', "
        "'vibecomfy.runtime.client', 'vibecomfy.runtime.server', "
        "'vibecomfy.comfy_command'"
        "}; "
        "loaded = forbidden & set(sys.modules); "
        "assert not loaded, sorted(loaded)"
    )
    result = _run_import_cost_probe(code)
    assert result.returncode == 0, result.stderr
