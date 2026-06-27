"""Pi worker script — isolated subprocess entry point.

Replaces ``vibecomfy/comfy_nodes/agent/worker.py`` for the Pi transition.
Drives Pi's ``@earendil-works/pi-agent-core`` with a fixture-backed or
live provider, depending on the request.

Protocol (mirrors current worker, extended for Pi):
    python pi_worker.mjs <request.json> <result.json>

request.json:
    {
        "system_message": "optional system prompt",
        "user_message": "the user request text",
        "response_contract": "python" | "delta" | "batch_repl" | "json" | "text",
        "agent_kwargs": {
            "model": "deepseek/deepseek-v4-pro",    // optional, defaults from contract
            "api_key": "sk-...",                    // optional
            "provider": "openrouter",               // optional
            "base_url": "https://...",              // optional
            "max_tokens": 2048,                     // optional
            "use_fixtures": true,                   // if true, use fixture provider
            "fixture_key": "smoke_upscale_1"        // optional, forces specific fixture
        }
    }

result.json:
    Success: {"python": "...", "message": "..."}
    Error:   {"error": "...", "error_type": "...", "runtime_unavailable": bool}

Requirements:
    - Node.js >= 22.19.0
    - Pi installed at /tmp/pi-compare/pi (or VIBECOMFY_PI_ROOT env var)
    - For live mode: OPENROUTER_API_KEY or provider-specific credential
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

_PI_ROOT = Path(os.environ.get("VIBECOMFY_PI_ROOT", "/tmp/pi-compare/pi"))
_NODE_BIN = os.environ.get("VIBECOMFY_PI_NODE", "node")


def _check_pi_available() -> None:
    """Verify Pi is importable and Node is available."""
    if not (_PI_ROOT / "packages" / "agent" / "package.json").exists():
        raise ImportError(
            f"Pi not found at {_PI_ROOT}. "
            f"Set VIBECOMFY_PI_ROOT or install Pi to /tmp/pi-compare/pi."
        )

    result = subprocess.run(
        [_NODE_BIN, "--version"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Node.js not available: {result.stderr.strip()}")


def _run_pi_agent_turn(request: dict) -> dict:
    """Execute one Pi agent turn using Pi's agent harness via Node subprocess.

    This is the actual integration point.  The Python worker launches a Node
    script that uses ``@earendil-works/pi-agent-core`` with either a live
    provider or the faux provider for fixture-backed testing.
    """
    agent_script = _PI_ROOT / "scripts" / "pi-agent-turn.mjs"
    if not agent_script.exists():
        # Fall back to using pi binary directly
        return _run_pi_binary(request)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(json.dumps(request))
        tmp_path = tmp.name

    try:
        env = dict(os.environ)
        # Forward credentials if present
        for key in ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "HERMES_API_KEY"):
            if key in os.environ:
                env[key] = os.environ[key]

        result = subprocess.run(
            [_NODE_BIN, str(agent_script), tmp_path],
            cwd=str(_PI_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=float(os.environ.get("VIBECOMFY_AGENT_TURN_TIMEOUT", "180")),
        )

        if result.returncode != 0:
            return {
                "error": result.stderr.strip() or "Pi worker failed",
                "error_type": "RuntimeError",
                "runtime_unavailable": False,
            }

        return json.loads(result.stdout)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _run_pi_binary(request: dict) -> dict:
    """Fallback: run pi binary with -p flag for a single prompt completion.

    This is a simplified path for when the dedicated agent-turn script
    hasn't been created yet.  Uses ``pi -p "<prompt>"`` with JSON output.
    """
    return {
        "error": (
            "Pi agent turn script not found. Create scripts/pi-agent-turn.mjs "
            "in the Pi repo to enable integrated agent turns."
        ),
        "error_type": "NotImplementedError",
        "runtime_unavailable": True,
    }


def main() -> int:
    request_path = sys.argv[1]
    result_path = sys.argv[2]

    try:
        _check_pi_available()
    except Exception as exc:
        result = {
            "error": str(exc),
            "error_type": type(exc).__name__,
            "runtime_unavailable": True,
        }
        with open(result_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh)
        return 1

    with open(request_path, encoding="utf-8") as fh:
        request = json.load(fh)

    try:
        result = _run_pi_agent_turn(request)
    except Exception as exc:
        result = {
            "error": str(exc),
            "error_type": type(exc).__name__,
            "runtime_unavailable": isinstance(exc, (ImportError, ModuleNotFoundError)),
        }

    with open(result_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh)

    return 0 if "error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
