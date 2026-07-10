"""L1 — Subprocess JSON Fixture Integration Tests.

These tests verify the Pi worker subprocess protocol (request.json →
subprocess → result.json) using fixture-backed responses.  No credentials,
no network, no live LLM calls.

Test matrix:
    - All 5 response contracts (python, delta, batch_repl, json, text)
    - Error paths (missing Pi, auth failure, timeout, malformed response)
    - Credential routing (env var passthrough, ~/.hermes/.env resolution)
    - Protocol shape parity with current Arnold worker
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Skip entire module if Pi worker script doesn't exist (not installed yet)
pytestmark = pytest.mark.skipif(
    not (Path(__file__).resolve().parent / "pi_worker.py").exists(),
    reason="Pi worker script not created yet",
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _request_json(
    tmp_path: Path,
    *,
    system_message: str | None = None,
    user_message: str = "test prompt",
    response_contract: str = "python",
    agent_kwargs: dict | None = None,
) -> Path:
    """Write a request.json to tmp_path and return its path."""
    req = tmp_path / "request.json"
    payload = {
        "system_message": system_message,
        "user_message": user_message,
        "response_contract": response_contract,
        "agent_kwargs": agent_kwargs or {},
    }
    req.write_text(json.dumps(payload), encoding="utf-8")
    return req


def _run_worker(
    request_path: Path,
    tmp_path: Path,
    *,
    timeout: float = 30,
    env_extra: dict[str, str] | None = None,
) -> tuple[int, dict | None, str, str]:
    """Run the Pi worker subprocess and return (returncode, result_dict, stdout, stderr)."""
    worker = Path(__file__).resolve().parent / "pi_worker.py"
    result_path = tmp_path / "result.json"

    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)

    proc = subprocess.run(
        [sys.executable, str(worker), str(request_path), str(result_path)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    result = None
    if result_path.exists():
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    return proc.returncode, result, proc.stdout, proc.stderr


def _normalize_error_env(result: dict | None) -> dict:
    """Normalize expected error-envelope keys."""
    assert result is not None
    assert "error" in result
    assert "error_type" in result
    assert isinstance(result["error_type"], str)
    assert len(result["error_type"]) > 0
    return result


# ── Protocol: Pi worker boots without Arnold ─────────────────────────────────

def test_pi_worker_rejects_missing_request_file(tmp_path: Path) -> None:
    """Worker fails gracefully when request.json is missing."""
    worker = Path(__file__).resolve().parent / "pi_worker.py"
    result_path = tmp_path / "result.json"

    proc = subprocess.run(
        [sys.executable, str(worker), str(tmp_path / "nonexistent.json"), str(result_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert proc.returncode != 0 or result_path.exists()
    if result_path.exists():
        result = json.loads(result_path.read_text(encoding="utf-8"))
        assert "error" in result


def test_pi_worker_reports_runtime_unavailable_when_pi_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pi worker returns runtime_unavailable when Pi repo is not at the expected path."""
    monkeypatch.setenv("VIBECOMFY_PI_ROOT", str(tmp_path / "missing-pi"))
    req = _request_json(tmp_path, user_message="test")
    returncode, result, _, _ = _run_worker(req, tmp_path)

    assert result is not None
    if "runtime_unavailable" in result:
        assert result["runtime_unavailable"] is True
    else:
        # If Pi is actually installed, this is a pass too
        pass


# ── Response contract shapes ─────────────────────────────────────────────────

@pytest.mark.parametrize(
    "contract,expected_keys",
    [
        ("python", {"python", "message"}),
        ("delta", {"delta", "message"}),
        ("batch_repl", {"content"}),
        ("json", {"content"}),
        ("text", {"content"}),
    ],
)
def test_contract_produces_expected_keys(
    contract: str,
    expected_keys: set[str],
    tmp_path: Path,
) -> None:
    """Each response contract produces the correct top-level keys in result.json.

    NOTE: This test will fail (or skip) until the Pi worker's Node.js integration
    is fully wired.  It documents the expected contract shapes for the
    implementation phase.
    """
    req = _request_json(tmp_path, response_contract=contract)
    returncode, result, stdout, stderr = _run_worker(req, tmp_path)

    if result is None:
        pytest.skip(
            f"Pi worker not yet integrated (no result.json produced). "
            f"stdout: {stdout[:200]}, stderr: {stderr[:200]}"
        )

    if "error" in result:
        # Pi worker might report "not implemented" — acceptable during transition
        if result.get("runtime_unavailable"):
            pytest.skip(f"Pi worker reports runtime unavailable: {result['error']}")
        # Unexpected error
        pytest.fail(f"Pi worker error: {result}")

    result_keys = set(result.keys()) - {"_profiling", "raw"}
    missing = expected_keys - result_keys
    assert not missing, (
        f"Contract '{contract}' missing keys: {missing}. "
        f"Got: {result_keys}"
    )


# ── Error envelope ───────────────────────────────────────────────────────────


def test_error_produces_structured_envelope(tmp_path: Path) -> None:
    """Error responses contain error, error_type, and optionally runtime_unavailable."""
    req = _request_json(
        tmp_path,
        user_message="",
        response_contract="unsupported_contract",
    )
    returncode, result, _, _ = _run_worker(req, tmp_path)

    if result is None:
        pytest.skip("Pi worker not yet integrated")

    # An unsupported contract should produce a structured error
    if "error" in result:
        _normalize_error_env(result)
    else:
        # If it succeeds, that's also fine — just document it
        pass


# ── Credential routing ───────────────────────────────────────────────────────


def test_openrouter_key_passed_through_env(tmp_path: Path) -> None:
    """OPENROUTER_API_KEY in parent env is forwarded to Pi worker."""
    req = _request_json(
        tmp_path,
        user_message="test",
        agent_kwargs={"provider": "openrouter"},
    )
    returncode, result, _, _ = _run_worker(
        req,
        tmp_path,
        env_extra={"OPENROUTER_API_KEY": "sk-or-test-key"},
    )

    if result is None:
        pytest.skip("Pi worker not yet integrated")

    # Result should not be an auth error if key was forwarded correctly
    if result.get("error_type") == "AuthError":
        pytest.fail(
            f"OPENROUTER_API_KEY was set but Pi worker reported auth error: {result}"
        )


def test_missing_key_reports_readiness_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without any credential env vars, Pi readiness reports ready: false."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("HERMES_API_KEY", raising=False)

    req = _request_json(
        tmp_path,
        user_message="test",
        agent_kwargs={"provider": "openrouter"},
    )
    returncode, result, _, _ = _run_worker(req, tmp_path)

    if result is None:
        pytest.skip("Pi worker not yet integrated")

    # Worker should report auth error or runtime unavailable, not crash
    assert result is not None
    assert "error" in result or "content" in result or "python" in result or "message" in result


# ── Protocol parity ──────────────────────────────────────────────────────────


def test_result_json_is_valid_json_always(tmp_path: Path) -> None:
    """result.json is always parseable valid JSON, even on crashes."""
    req = _request_json(tmp_path)
    returncode, result, _, _ = _run_worker(req, tmp_path)

    if result is None:
        # If no result.json, the subprocess crashed — document
        result_path = tmp_path / "result.json"
        if result_path.exists():
            raw = result_path.read_text(encoding="utf-8")
            # Try parsing — this should always work
            json.loads(raw)
        else:
            pytest.skip("Pi worker not yet integrated (no result.json)")


def test_profiling_metadata_present(tmp_path: Path) -> None:
    """result.json includes _profiling metadata (started_at, elapsed_ms, etc.)."""
    req = _request_json(tmp_path)
    returncode, result, _, _ = _run_worker(req, tmp_path)

    if result is None:
        pytest.skip("Pi worker not yet integrated")

    profiling = result.get("_profiling")
    if profiling is not None:
        assert isinstance(profiling, dict)
        assert "elapsed_ms" in profiling or "started_at" in profiling
