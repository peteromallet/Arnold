"""Pi worker harness for subprocess JSON-fixture integration tests.

This module provides the test infrastructure for L1–L2 of the Pi transition
plan.  It mirrors the current ``runtime._run_worker()`` pattern but drives Pi
instead of the Arnold/AIAgent dispatch.

All tests in this directory use this harness.  No real API keys are required —
the Pi worker is configured with a fixture-backed provider for deterministic,
offline testing.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

# ── Paths ────────────────────────────────────────────────────────────────────
_PI_REPO = Path("/tmp/pi-compare/pi")
_PI_BINARY = os.environ.get("VIBECOMFY_PI_BINARY", "node")
_PI_WORKER_SCRIPT = (
    Path(__file__).resolve().parent / "pi_worker.mjs"
)


@dataclass(frozen=True, slots=True)
class PiTurnResult:
    """Structured result from a single Pi worker turn.

    Mirrors the contract shapes in vibecomfy's ``provider.py``:
    ``AgentTurnResult``, ``BatchTurnResult``, and the raw content variants.
    """
    content: str | None = None
    json_payload: dict[str, Any] | None = None
    python: str | None = None
    message: str | None = None
    delta: list[dict[str, Any]] | None = None
    batch: str | None = None
    error: str | None = None
    error_type: str | None = None
    runtime_unavailable: bool = False
    raw: dict[str, Any] = field(default_factory=dict)
    profiling: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_result_json(cls, result: dict[str, Any]) -> PiTurnResult:
        profiling = result.get("_profiling") if isinstance(result.get("_profiling"), dict) else {}
        return cls(
            content=result.get("content"),
            json_payload=result.get("json"),
            python=result.get("python"),
            message=result.get("message"),
            delta=result.get("delta"),
            batch=result.get("batch"),
            error=result.get("error"),
            error_type=result.get("error_type"),
            runtime_unavailable=bool(result.get("runtime_unavailable")),
            raw=result,
            profiling=profiling,
        )


def run_pi_turn(
    *,
    system_message: str | None = None,
    user_message: str,
    response_contract: str = "python",
    agent_kwargs: dict[str, Any] | None = None,
    timeout: float | None = None,
    env_extra: dict[str, str] | None = None,
) -> PiTurnResult:
    """Run one Pi agent turn in an isolated subprocess.

    Parameters
    ----------
    system_message:
        Optional system prompt.
    user_message:
        The user's request text.
    response_contract:
        One of ``"python"``, ``"delta"``, ``"batch_repl"``, ``"json"``, ``"text"``.
    agent_kwargs:
        Pi provider kwargs (model, api_key, base_url, provider, max_tokens).
        When absent, the worker uses a fixture-backed faux provider.
    timeout:
        Seconds before raising TimeoutError. Defaults to
        ``VIBECOMFY_AGENT_TURN_TIMEOUT`` env var or 180.
    env_extra:
        Additional env vars to pass to the subprocess.

    Returns
    -------
    PiTurnResult:
        Structured result parsed from the worker's ``result.json``.
    """
    if timeout is None:
        timeout = float(os.environ.get("VIBECOMFY_AGENT_TURN_TIMEOUT", "180"))

    with tempfile.TemporaryDirectory(prefix="vibecomfy-pi-") as tmp:
        req_path = os.path.join(tmp, "request.json")
        res_path = os.path.join(tmp, "result.json")

        with open(req_path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "system_message": system_message,
                    "user_message": user_message,
                    "response_contract": response_contract,
                    "agent_kwargs": agent_kwargs or {},
                },
                fh,
            )

        env = dict(os.environ)
        if env_extra:
            env.update(env_extra)

        try:
            proc = subprocess.run(
                [sys.executable, str(_PI_WORKER_SCRIPT), req_path, res_path],
                cwd=tmp,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(
                f"Pi worker timed out after {timeout:g} seconds."
            ) from exc

        try:
            with open(res_path, encoding="utf-8") as fh:
                result = json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            return PiTurnResult(
                error=f"Failed to read result.json: {exc}",
                error_type=type(exc).__name__,
                runtime_unavailable=True,
            )

        turn_result = PiTurnResult.from_result_json(result)

        # Surface subprocess stderr on errors
        if turn_result.error and proc.stderr:
            turn_result = PiTurnResult(
                **{
                    **vars(turn_result),
                    "error": f"{turn_result.error}\n\nWorker stderr:\n{proc.stderr.strip()}",
                }
            )

        return turn_result


def run_pi_turns_parallel(
    turns: Sequence[dict[str, Any]],
    *,
    timeout: float | None = None,
    max_workers: int = 10,
) -> list[PiTurnResult]:
    """Run multiple Pi turns concurrently using thread pool.

    Each turn dict must have the same kwargs as :func:`run_pi_turn`.

    Parameters
    ----------
    turns:
        List of turn kwargs dicts.
    timeout:
        Per-turn timeout in seconds.
    max_workers:
        Maximum concurrent subprocesses.

    Returns
    -------
    list[PiTurnResult]:
        Results in the same order as the input turns.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results: list[PiTurnResult | None] = [None] * len(turns)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(run_pi_turn, timeout=timeout, **turn): idx
            for idx, turn in enumerate(turns)
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception as exc:
                results[idx] = PiTurnResult(
                    error=str(exc),
                    error_type=type(exc).__name__,
                    runtime_unavailable=isinstance(exc, TimeoutError),
                )

    return [r for r in results if r is not None]


# ── Fixture-backed convenience ───────────────────────────────────────────────


def run_pi_turn_fixture(
    *,
    user_message: str,
    response_contract: str = "python",
    fixture_key: str | None = None,
    system_message: str | None = None,
    timeout: float | None = None,
) -> PiTurnResult:
    """Run a Pi turn with fixture-backed provider (no real API).

    The Pi worker script reads from ``tests/pi_transition/fixtures/``
    when no ``agent_kwargs`` with credentials are provided.
    """
    kwargs: dict[str, Any] = {"use_fixtures": True}
    if fixture_key:
        kwargs["fixture_key"] = fixture_key

    return run_pi_turn(
        system_message=system_message,
        user_message=user_message,
        response_contract=response_contract,
        agent_kwargs=kwargs,
        timeout=timeout,
    )
