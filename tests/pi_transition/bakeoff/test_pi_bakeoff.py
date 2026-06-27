"""L4 — Golden Real-Brief Bakeoff Tests.

These tests require live API credentials and the ``--run-live`` pytest flag.
They run identical briefs through both Arnold and Pi and compare outputs.

Usage:
    pytest tests/pi_transition/bakeoff/ --run-live -v
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.live


# ── Bakeoff briefs ───────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class BakeoffBrief:
    """A single bakeoff test case."""
    id: str
    query: str
    contract: str = "python"
    system_message: str | None = None
    required_content_signals: list[str] = field(default_factory=list)
    forbidden_content_signals: list[str] = field(default_factory=list)


# Curated briefs covering all contracts and complexity levels
BAKEOFF_BRIEFS: list[BakeoffBrief] = [
    # ── Python contract ──
    BakeoffBrief(
        id="simple-image-generation",
        query="Generate an image of a brass camera on a blue table.",
        contract="python",
        required_content_signals=["image", "prompt", "SaveImage"],
    ),
    BakeoffBrief(
        id="video-workflow-explanation",
        query="Explain how to set up a WAN T2V video workflow.",
        contract="python",
        required_content_signals=["wan", "video", "ready"],
    ),
    # ── Delta contract ──
    BakeoffBrief(
        id="controlnet-patch",
        query="Add a ControlNet depth patch to this image workflow.",
        contract="delta",
        required_content_signals=["controlnet", "depth"],
    ),
    # ── Batch contract ──
    BakeoffBrief(
        id="multi-edit-batch",
        query="Add a CLIPTextEncode node and a KSampler node, then wire them together.",
        contract="batch_repl",
        required_content_signals=["```batch", "CLIPTextEncode", "KSampler"],
    ),
    # ── JSON contract ──
    BakeoffBrief(
        id="classification",
        query="Is this a video or image workflow request?",
        contract="json",
        required_content_signals=["video", "image"],
    ),
    # ── Text contract ──
    BakeoffBrief(
        id="greeting",
        query="Introduce yourself briefly.",
        contract="text",
        required_content_signals=[],
    ),
    # ── Refusal ──
    BakeoffBrief(
        id="impossible-request",
        query="Generate an 8K video with 5000 frames on the free tier.",
        contract="python",
        required_content_signals=["refus", "limit", "free"],
        forbidden_content_signals=[],
    ),
    # ── Long context ──
    BakeoffBrief(
        id="long-context",
        query="Summarize this workflow history: " + ("setup, " * 200) + "finalize.",
        contract="python",
        required_content_signals=["summar"],
    ),
]


# ── Comparison logic ─────────────────────────────────────────────────────────

@dataclass
class BakeoffResult:
    brief_id: str
    arnold_result: dict | None = None
    pi_result: dict | None = None
    arnold_latency_s: float = 0.0
    pi_latency_s: float = 0.0
    arnold_error: str | None = None
    pi_error: str | None = None
    signals_arnold: set[str] = field(default_factory=set)
    signals_pi: set[str] = field(default_factory=set)
    verdict: str = "pending"  # identical, equivalent, divergent, error


def _extract_text(result: dict | None) -> str:
    """Extract all text content from a result dict for signal matching."""
    if result is None:
        return ""
    parts = []
    for key in ("content", "python", "message", "text", "batch"):
        value = result.get(key)
        if isinstance(value, str):
            parts.append(value)
    for key in ("delta",):
        value = result.get(key)
        if isinstance(value, list):
            parts.append(json.dumps(value))
    if isinstance(result.get("json"), dict):
        parts.append(json.dumps(result["json"]))
    return " ".join(parts).lower()


def _find_signals(text: str, signals: list[str]) -> set[str]:
    """Return which signals are present in text (case-insensitive)."""
    return {s for s in signals if s.lower() in text}


def _run_arnold_turn(brief: BakeoffBrief) -> tuple[dict | None, float, str | None]:
    """Run a turn through the current Arnold worker."""
    from vibecomfy.comfy_nodes.agent.runtime import _build_agent_kwargs, _run_worker

    start = time.monotonic()
    try:
        result = _run_worker(
            agent_kwargs=_build_agent_kwargs("hermes", route="openrouter"),
            system_msg=brief.system_message,
            user_msg=brief.query,
            response_contract=brief.contract,
        )
        elapsed = time.monotonic() - start
        return result, elapsed, None
    except Exception as exc:
        elapsed = time.monotonic() - start
        return None, elapsed, str(exc)


def _run_pi_turn(brief: BakeoffBrief) -> tuple[dict | None, float, str | None]:
    """Run a turn through the Pi worker."""
    try:
        from tests.pi_transition.harness import run_pi_turn
    except ImportError:
        return None, 0.0, "Pi harness not available"

    start = time.monotonic()
    try:
        pi_result = run_pi_turn(
            system_message=brief.system_message,
            user_message=brief.query,
            response_contract=brief.contract,
            agent_kwargs={"provider": "openrouter", "model": "deepseek/deepseek-v4-pro"},
        )
        elapsed = time.monotonic() - start

        result_dict = {
            k: v
            for k, v in vars(pi_result).items()
            if v is not None and k not in ("raw", "profiling")
        }
        return result_dict, elapsed, None
    except Exception as exc:
        elapsed = time.monotonic() - start
        return None, elapsed, str(exc)


def _classify_verdict(
    arnold_text: str,
    pi_text: str,
    arnold_signals: set[str],
    pi_signals: set[str],
    required_signals: list[str],
) -> str:
    """Classify the bakeoff outcome."""
    if not arnold_text and not pi_text:
        return "error_both_failed"
    if not arnold_text:
        return "error_arnold_failed"
    if not pi_text:
        return "error_pi_failed"

    # Identical: byte-for-byte match
    if arnold_text == pi_text:
        return "identical"

    # Equivalent: all required signals present in both
    required_lower = {s.lower() for s in required_signals}
    arnold_has_all = required_lower <= arnold_signals
    pi_has_all = required_lower <= pi_signals

    if arnold_has_all and pi_has_all:
        return "equivalent"
    if arnold_has_all and not pi_has_all:
        return "divergent_pi_missing_signals"
    if not arnold_has_all and pi_has_all:
        return "divergent_arnold_missing_signals"
    return "divergent"


# ── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("brief", BAKEOFF_BRIEFS, ids=lambda b: b.id)
def test_bakeoff_single_turn(brief: BakeoffBrief) -> None:
    """Run a single brief through both Arnold and Pi; compare outputs."""
    arnold_result, arnold_latency, arnold_error = _run_arnold_turn(brief)
    pi_result, pi_latency, pi_error = _run_pi_turn(brief)

    arnold_text = _extract_text(arnold_result)
    pi_text = _extract_text(pi_result)

    arnold_signals = _find_signals(arnold_text, brief.required_content_signals)
    pi_signals = _find_signals(pi_text, brief.required_content_signals)

    verdict = _classify_verdict(
        arnold_text, pi_text, arnold_signals, pi_signals,
        brief.required_content_signals,
    )

    result = BakeoffResult(
        brief_id=brief.id,
        arnold_result=arnold_result,
        pi_result=pi_result,
        arnold_latency_s=round(arnold_latency, 3),
        pi_latency_s=round(pi_latency, 3),
        arnold_error=arnold_error,
        pi_error=pi_error,
        signals_arnold=arnold_signals,
        signals_pi=pi_signals,
        verdict=verdict,
    )

    # Record for aggregate reporting
    _bakeoff_results.append(result)

    # Fail only on Pi-specific errors
    if "error_pi_failed" in verdict:
        pytest.fail(
            f"Pi failed while Arnold succeeded for '{brief.id}': "
            f"pi_error={pi_error}"
        )

    # Warn on divergence (don't fail — these are informational during transition)
    if "divergent" in verdict:
        pytest.fail(
            f"Divergent outputs for '{brief.id}': "
            f"arnold_signals={arnold_signals}, pi_signals={pi_signals}"
        )


# ── Aggregate reporting ─────────────────────────────────────────────────────

_bakeoff_results: list[BakeoffResult] = []


@pytest.fixture(autouse=True)
def _reset_bakeoff_results() -> None:
    """Clear results before each test module run."""
    _bakeoff_results.clear()
    yield


def test_bakeoff_aggregate_scorecard() -> None:
    """Print aggregate bakeoff scorecard after all briefs run."""
    if not _bakeoff_results:
        pytest.skip("No bakeoff results collected")

    verdicts: dict[str, int] = {}
    for result in _bakeoff_results:
        verdicts[result.verdict] = verdicts.get(result.verdict, 0) + 1

    total = len(_bakeoff_results)
    identical = verdicts.get("identical", 0)
    equivalent = verdicts.get("equivalent", 0)
    acceptable = identical + equivalent
    pct = acceptable / total * 100 if total > 0 else 0

    # Print scorecard
    print(f"\n{'='*60}")
    print(f"PI BAKEOFF SCORECARD")
    print(f"{'='*60}")
    print(f"Total briefs: {total}")
    for verdict, count in sorted(verdicts.items()):
        print(f"  {verdict}: {count} ({count/total*100:.1f}%)")
    print(f"\nIdentical + Equivalent: {acceptable}/{total} ({pct:.1f}%)")
    print(f"{'='*60}")

    # Gate: ≥90% acceptable
    assert pct >= 90, (
        f"Acceptable rate {pct:.1f}% below 90% threshold. "
        f"Divergent/error briefs: {total - acceptable}"
    )
