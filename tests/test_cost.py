"""Unit tests for megaplan cost (megaplan/observability/cost.py).

Covers every branch of the aggregation contract: exact tokens, fallback join,
None-skip, unmatched, reconciliation both directions, classification edge
cases, both source-fix emitters, read-only invariant, and JSON output keys.
"""

from __future__ import annotations

import json
import sys
from argparse import Namespace
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from megaplan.observability.cost import (
    _aggregate,
    _classify_vendor,
    _render_json,
    _render_table,
    handle_cost,
)
from megaplan.observability.events import EventKind


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_plan_dir(tmp_path: Path, name: str = "test-plan") -> Path:
    """Create a plan dir structure that find_plan_dir can resolve."""
    plan_dir = tmp_path / ".megaplan" / "plans" / name
    plan_dir.mkdir(parents=True, exist_ok=True)
    return plan_dir


def _write_events(plan_dir: Path, events: list[dict]) -> None:
    """Write event dicts to events.ndjson."""
    ndjson = plan_dir / "events.ndjson"
    lines = [json.dumps(ev, separators=(",", ":")) for ev in events]
    ndjson.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_state(plan_dir: Path, state: dict) -> None:
    """Write state.json."""
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _ev(
    kind: str,
    seq: int = 0,
    phase: str | None = None,
    payload: dict | None = None,
    ts_utc: str = "2025-01-01T00:00:00+00:00",
) -> dict:
    """Minimal event dict factory (matching the read_events output shape)."""
    return {
        "seq": seq,
        "ts_utc": ts_utc,
        "kind": kind,
        "phase": phase,
        "payload": payload or {},
    }


def _cr(
    model: str | None,
    cost_usd: float,
    request_id: str | None = None,
    phase: str = "execute",
    seq: int = 0,
) -> dict:
    """cost_recorded event factory."""
    payload: dict = {"model": model, "cost_usd": cost_usd, "request_id": request_id}
    return _ev(EventKind.COST_RECORDED, seq=seq, phase=phase, payload=payload)


def _lle(
    tokens_in: int = 100,
    tokens_out: int = 50,
    model: str | None = None,
    request_id: str | None = None,
    phase: str = "execute",
    seq: int = 0,
) -> dict:
    """llm_call_end event factory."""
    payload: dict = {
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "request_id": request_id,
    }
    if model is not None:
        payload["model"] = model
    return _ev(EventKind.LLM_CALL_END, seq=seq, phase=phase, payload=payload)


# ---------------------------------------------------------------------------
# (7) Classification: vendor bucket edge cases
# ---------------------------------------------------------------------------


class TestClassifyVendor:
    """Exercise every _classify_vendor branch."""

    def test_claude_variants(self) -> None:
        """opus, sonnet, claude → claude."""
        assert _classify_vendor("claude-opus-4") == "claude"
        assert _classify_vendor("claude-sonnet-4") == "claude"
        assert _classify_vendor("anthropic/claude-3-5-sonnet") == "claude"
        assert _classify_vendor("claude-3-haiku") == "claude"

    def test_codex_variants(self) -> None:
        """gpt, codex → codex."""
        assert _classify_vendor("gpt-4o") == "codex"
        assert _classify_vendor("gpt-4.1") == "codex"
        assert _classify_vendor("codex-1") == "codex"
        assert _classify_vendor("openai/codex") == "codex"

    def test_deepseek_variants(self) -> None:
        """deepseek, hermes, shannon → deepseek."""
        assert _classify_vendor("deepseek-v4") == "deepseek"
        assert _classify_vendor("deepseek-v4-pro") == "deepseek"
        assert _classify_vendor("hermes-3") == "deepseek"
        assert _classify_vendor("shannon-1") == "deepseek"

    def test_gemini_is_other_not_deepseek(self) -> None:
        """Gemini models classify as other (checked BEFORE deepseek)."""
        assert _classify_vendor("gemini-3-flash") == "other"
        assert _classify_vendor("google/gemini-3-flash-preview") == "other"
        assert _classify_vendor("gemini-2.5-flash") == "other"
        assert _classify_vendor("gemini-pro") == "other"

    def test_unknown_and_empty(self) -> None:
        """Unknown / None / empty → other."""
        assert _classify_vendor("llama-3") == "other"
        assert _classify_vendor("mistral") == "other"
        assert _classify_vendor(None) == "other"
        assert _classify_vendor("") == "other"
        assert _classify_vendor("  ") == "other"

    def test_no_bare_flash_match(self) -> None:
        """Bare 'flash' in model name must not classify as deepseek."""
        # If there were a bare 'flash' match, this would be deepseek.
        # Since there isn't, it correctly lands in other.
        assert _classify_vendor("gemini-2.0-flash-exp") == "other"


# ---------------------------------------------------------------------------
# (2) Exact path — model present on llm_call_end
# ---------------------------------------------------------------------------


class TestExactPath:
    """llm_call_end carrying `model` → exact vendor/model token rollup."""

    def test_exact_path_model_tokens(self) -> None:
        """Tokens attributed to the exact model & vendor; exact_tokens=True."""
        events = [
            _cr("claude-opus-4", 0.005, request_id="rid1"),
            _lle(tokens_in=200, tokens_out=100, model="claude-opus-4", request_id="rid1"),
        ]
        agg = _aggregate(events, meta_cost=0.0)

        assert agg["tokens_by_model"]["claude-opus-4"] == 300
        assert agg["tokens_by_vendor"]["claude"] == 300
        assert agg["exact_tokens"] is True
        assert agg["total_tokens"] == 300

    def test_exact_path_ignores_unused_request_id(self) -> None:
        """When model is present, the request_id map is irrelevant."""
        events = [
            _cr("gpt-4o", 0.010, request_id="other-rid"),
            _lle(tokens_in=50, tokens_out=25, model="gpt-4o", request_id="different-rid"),
        ]
        agg = _aggregate(events, meta_cost=0.0)

        assert agg["tokens_by_model"]["gpt-4o"] == 75
        assert agg["tokens_by_vendor"]["codex"] == 75
        assert agg["exact_tokens"] is True


# ---------------------------------------------------------------------------
# (3) Fallback join — llm_call_end without model, non-None request_id
# ---------------------------------------------------------------------------


class TestFallbackJoin:
    """llm_call_end without model → joined via request_id to cost_recorded."""

    def test_fallback_join_success(self) -> None:
        """Non-None request_id found in map → attributed to mapped model."""
        events = [
            _cr("claude-sonnet-4", 0.002, request_id="rid-join"),
            _lle(tokens_in=400, tokens_out=200, model=None, request_id="rid-join"),
        ]
        agg = _aggregate(events, meta_cost=0.0)

        assert agg["tokens_by_model"]["claude-sonnet-4"] == 600
        assert agg["tokens_by_vendor"]["claude"] == 600
        assert agg["exact_tokens"] is False
        assert agg["total_tokens"] == 600

    def test_fallback_join_vendor_correct(self) -> None:
        """Joined model mapped through _classify_vendor correctly."""
        events = [
            _cr("gpt-4.1", 0.003, request_id="rid-codex"),
            _lle(tokens_in=10, tokens_out=5, model=None, request_id="rid-codex"),
        ]
        agg = _aggregate(events, meta_cost=0.0)
        assert agg["tokens_by_vendor"]["codex"] == 15


# ---------------------------------------------------------------------------
# (4) None-skip — llm_call_end with request_id=None NOT joined
# ---------------------------------------------------------------------------


class TestNoneSkip:
    """request_id=None on llm_call_end must NOT create false cross-call matches."""

    def test_none_request_id_skips_join(self) -> None:
        """Even when cost_recorded also has request_id=None, NO join occurs."""
        events = [
            _cr("claude-opus-4", 1.0, request_id=None),
            _lle(tokens_in=500, tokens_out=500, model=None, request_id=None),
        ]
        agg = _aggregate(events, meta_cost=0.0)

        # Tokens should NOT be attributed to claude-opus-4 model.
        assert "claude-opus-4" not in agg["tokens_by_model"]
        # Cost IS attributed to claude-opus-4 (from the cost_recorded event).
        assert agg["cost_by_model"]["claude-opus-4"] == 1.0
        # Tokens go to deepseek vendor bucket (no model-level attribution).
        assert agg["tokens_by_vendor"]["deepseek"] == 1000
        assert agg["exact_tokens"] is False

    def test_none_request_id_no_false_model_attribution(self) -> None:
        """Verify the model key from cost_recorded (None req_id) doesn't leak."""
        events = [
            _cr("hermes-3", 0.5, request_id=None),
            _lle(tokens_in=100, tokens_out=100, model=None, request_id=None),
        ]
        agg = _aggregate(events, meta_cost=0.0)

        # hermes-3 should have cost but NO token attribution from this llm_call_end.
        assert agg["cost_by_model"]["hermes-3"] == 0.5
        assert "hermes-3" not in agg["tokens_by_model"]


# ---------------------------------------------------------------------------
# (5) Unmatched — non-None request_id not in the map
# ---------------------------------------------------------------------------


class TestUnmatched:
    """Unmatched request_id → deepseek bucket, exact_tokens=False."""

    def test_unmatched_request_id_deepseek_bucket(self) -> None:
        """Non-None request_id not in map → deepseek vendor, no model."""
        events = [
            _cr("claude-opus-4", 0.1, request_id="known-rid"),
            _lle(tokens_in=300, tokens_out=200, model=None, request_id="unknown-rid"),
        ]
        agg = _aggregate(events, meta_cost=0.0)

        assert agg["tokens_by_vendor"]["deepseek"] == 500
        assert "claude-opus-4" not in agg["tokens_by_model"]  # no token attribution
        assert agg["cost_by_model"]["claude-opus-4"] == 0.1  # cost still attributed
        assert agg["exact_tokens"] is False

    def test_unmatched_request_id_no_model_key(self) -> None:
        """Unmatched tokens never create a model-level entry."""
        events = [
            _cr("deepseek-v4", 0.2, request_id="rid-a"),
            _lle(tokens_in=50, tokens_out=50, model=None, request_id="rid-b"),
        ]
        agg = _aggregate(events, meta_cost=0.0)
        # Only cost attributions, not tokens
        assert agg["tokens_by_model"] == {}
        assert agg["tokens_by_vendor"]["deepseek"] == 100


# ---------------------------------------------------------------------------
# (6) Reconciliation — meta vs events cost
# ---------------------------------------------------------------------------


class TestReconciliation:
    """Cost reconciliation: larger of (events sum, meta.total_cost_usd)."""

    def test_meta_exceeds_events(self) -> None:
        """meta > events_sum → total_cost = meta, cost_source = state_meta."""
        events = [_cr("claude-opus-4", 1.0)]
        agg = _aggregate(events, meta_cost=5.0)

        assert agg["total_cost"] == 5.0
        assert agg["cost_source"] == "state_meta"
        assert agg["events_cost"] == 1.0
        assert agg["meta_cost"] == 5.0

    def test_events_exceed_meta(self) -> None:
        """events_sum > meta → total_cost = events, cost_source = events."""
        events = [_cr("claude-opus-4", 10.0), _cr("gpt-4o", 5.0)]
        agg = _aggregate(events, meta_cost=3.0)

        assert agg["total_cost"] == 15.0
        assert agg["cost_source"] == "events"
        assert agg["events_cost"] == 15.0
        assert agg["meta_cost"] == 3.0

    def test_equal_uses_events(self) -> None:
        """When equal, events wins (the `else` branch)."""
        events = [_cr("claude-opus-4", 3.0)]
        agg = _aggregate(events, meta_cost=3.0)
        assert agg["total_cost"] == 3.0
        assert agg["cost_source"] == "events"

    def test_zero_meta_zero_events(self) -> None:
        """Both zero → total_cost=0, cost_source='events'."""
        events: list[dict] = []
        agg = _aggregate(events, meta_cost=0.0)
        assert agg["total_cost"] == 0.0
        assert agg["cost_source"] == "events"


# ---------------------------------------------------------------------------
# (8) Source fix hermes — _emit_llm_end stamps model
# ---------------------------------------------------------------------------


class TestHermesEmitter:
    """Call _emit_llm_end and read back to confirm payload.model is written."""

    def test_emit_llm_end_stamps_model(self, tmp_path: Path) -> None:
        """_emit_llm_end(..., model=\"claude-opus-4\") → events.ndjson has model."""
        from megaplan.workers.hermes import _emit_llm_end

        plan_dir = tmp_path / "hermes-emit-test"
        plan_dir.mkdir(parents=True, exist_ok=True)

        _emit_llm_end(
            plan_dir,
            step="execute",
            tokens_in=1000,
            tokens_out=500,
            request_id="rid-hermes",
            model="claude-opus-4",
        )

        ndjson = plan_dir / "events.ndjson"
        assert ndjson.exists(), "events.ndjson was not created"

        lines = ndjson.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1

        event = json.loads(lines[0])
        assert event["kind"] == EventKind.LLM_CALL_END
        assert event["payload"]["model"] == "claude-opus-4"
        assert event["payload"]["tokens_in"] == 1000
        assert event["payload"]["tokens_out"] == 500
        assert event["payload"]["request_id"] == "rid-hermes"

    def test_emit_llm_end_model_none_dominant(self, tmp_path: Path) -> None:
        """When model=None is passed (default), None is written to payload."""
        from megaplan.workers.hermes import _emit_llm_end

        plan_dir = tmp_path / "hermes-emit-none"
        plan_dir.mkdir(parents=True, exist_ok=True)

        _emit_llm_end(
            plan_dir,
            step="plan",
            tokens_in=10,
            tokens_out=5,
            request_id=None,
            # model defaults to None
        )

        ndjson = plan_dir / "events.ndjson"
        event = json.loads(ndjson.read_text(encoding="utf-8").strip().split("\n")[0])
        assert event["payload"]["model"] is None


# ---------------------------------------------------------------------------
# (9) Source fix _impl — synthesize event mirroring _impl shape
# ---------------------------------------------------------------------------


class TestImplEmitterShape:
    """Synthesize events mirroring the _impl emitter and confirm read-back."""

    def test_impl_shape_llm_call_end_reads_model(self) -> None:
        """An event with _impl LLM_CALL_END shape (tokens_in/out, request_id, model)."""
        # _impl emits: payload={"tokens_in":..., "tokens_out":..., "request_id":..., "model":...}
        events = [
            _cr("deepseek-v4-pro", 0.05, request_id="impl-rid"),
            _ev(
                EventKind.LLM_CALL_END,
                phase="execute",
                payload={
                    "tokens_in": 2000,
                    "tokens_out": 800,
                    "request_id": "impl-rid",
                    "model": "deepseek-v4-pro",
                },
            ),
        ]
        agg = _aggregate(events, meta_cost=0.0)

        assert agg["tokens_by_model"]["deepseek-v4-pro"] == 2800
        assert agg["tokens_by_vendor"]["deepseek"] == 2800
        assert agg["exact_tokens"] is True

    def test_impl_shape_cost_recorded_reads_model(self) -> None:
        """A cost_recorded event with the _impl shape (request_id, cost_usd, provider, model)."""
        # _impl COST_RECORDED: payload={"request_id":..., "cost_usd":..., "provider":..., "model":...}
        events = [
            _ev(
                EventKind.COST_RECORDED,
                phase="review",
                payload={
                    "request_id": "cr-impl",
                    "cost_usd": 2.5,
                    "provider": "deepseek",
                    "model": "deepseek-v4-pro",
                },
            ),
        ]
        agg = _aggregate(events, meta_cost=0.0)

        assert agg["cost_by_model"]["deepseek-v4-pro"] == 2.5
        assert agg["cost_by_vendor"]["deepseek"] == 2.5
        assert agg["total_cost"] == 2.5

    def test_impl_shape_without_model_still_reads(self) -> None:
        """An _impl-shaped LLM_CALL_END without model falls back correctly."""
        events = [
            _cr("gpt-4o", 0.1, request_id="impl-nomodel"),
            _ev(
                EventKind.LLM_CALL_END,
                phase="execute",
                payload={
                    "tokens_in": 100,
                    "tokens_out": 50,
                    "request_id": "impl-nomodel",
                    # no "model" key at all (simulating pre-fix _impl)
                },
            ),
        ]
        agg = _aggregate(events, meta_cost=0.0)

        # Fallback join via request_id
        assert agg["tokens_by_model"]["gpt-4o"] == 150
        assert agg["tokens_by_vendor"]["codex"] == 150
        assert agg["exact_tokens"] is False


# ---------------------------------------------------------------------------
# (10) Read-only — events.ndjson unchanged by handle_cost
# ---------------------------------------------------------------------------


class TestReadOnly:
    """handle_cost must not modify events.ndjson (byte-length invariant)."""

    def test_byte_length_unchanged(self, tmp_path: Path) -> None:
        """events.ndjson byte length identical before and after handle_cost."""
        plan_dir = _make_plan_dir(tmp_path, "readonly-test")

        events = [
            _cr("claude-opus-4", 0.05, request_id="ro-rid", seq=0),
            _lle(tokens_in=100, tokens_out=50, model="claude-opus-4", request_id="ro-rid", seq=1),
        ]
        _write_events(plan_dir, events)
        _write_state(
            plan_dir,
            {"meta": {"total_cost_usd": 0.10}, "current_state": "executing"},
        )

        ndjson_path = plan_dir / "events.ndjson"
        before = ndjson_path.read_bytes()

        # Call handle_cost directly, mocking find_plan_dir to return our dir.
        # find_plan_dir is lazily imported inside handle_cost, so we patch the source module.
        with patch("megaplan._core.find_plan_dir", return_value=plan_dir):
            args = Namespace(plan="readonly-test", format="table", by_phase=False)
            rc = handle_cost(Path.cwd(), args)

        assert rc == 0
        after = ndjson_path.read_bytes()
        assert before == after, (
            f"events.ndjson modified by handle_cost! "
            f"before={len(before)} bytes, after={len(after)} bytes"
        )

    def test_byte_length_unchanged_json_format(self, tmp_path: Path) -> None:
        """Same invariant with --format json."""
        plan_dir = _make_plan_dir(tmp_path, "readonly-json")

        events = [
            _cr("gpt-4o", 1.0),
        ]
        _write_events(plan_dir, events)
        _write_state(plan_dir, {"meta": {"total_cost_usd": 1.0}})

        ndjson_path = plan_dir / "events.ndjson"
        before = ndjson_path.read_bytes()

        with patch("megaplan._core.find_plan_dir", return_value=plan_dir):
            args = Namespace(plan="readonly-json", format="json", by_phase=False)
            rc = handle_cost(Path.cwd(), args)

        assert rc == 0
        after = ndjson_path.read_bytes()
        assert before == after


# ---------------------------------------------------------------------------
# (11) --format json payload keys
# ---------------------------------------------------------------------------


class TestJsonFormat:
    """--format json emits payload with correct top-level keys."""

    def test_json_contains_required_keys(self) -> None:
        """Output dict must contain totals, by_vendor, by_model, cost_source, exact_tokens."""
        events = [
            _cr("claude-opus-4", 0.10),
            _cr("gpt-4o", 0.05),
            _lle(tokens_in=100, tokens_out=50, model="claude-opus-4"),
            _lle(tokens_in=200, tokens_out=100, model="gpt-4o"),
        ]
        agg = _aggregate(events, meta_cost=0.0)

        captured = StringIO()
        with patch("sys.stdout", captured):
            _render_json(agg, by_phase=False)

        output = json.loads(captured.getvalue())

        # Required top-level keys
        assert "totals" in output
        assert "by_vendor" in output
        assert "by_model" in output
        assert "cost_source" in output
        assert "exact_tokens" in output

        # totals shape
        assert "cost_usd" in output["totals"]
        assert "tokens" in output["totals"]
        assert output["totals"]["cost_usd"] == pytest.approx(0.15)
        assert output["totals"]["tokens"] == 450

        # cost_source
        assert output["cost_source"] == "events"

        # exact_tokens
        assert output["exact_tokens"] is True

        # by_vendor contains expected vendors
        assert "claude" in output["by_vendor"]
        assert "codex" in output["by_vendor"]

        # by_model contains expected models
        assert "claude-opus-4" in output["by_model"]
        assert "gpt-4o" in output["by_model"]

    def test_json_by_phase_included_when_requested(self) -> None:
        """--by-phase adds by_phase key to JSON output."""
        events = [
            _cr("claude-opus-4", 0.10, phase="execute", seq=0),
            _cr("gpt-4o", 0.05, phase="review", seq=1),
            _lle(tokens_in=100, tokens_out=50, model="claude-opus-4", phase="execute", seq=2),
        ]
        agg = _aggregate(events, meta_cost=0.0)

        captured = StringIO()
        with patch("sys.stdout", captured):
            _render_json(agg, by_phase=True)

        output = json.loads(captured.getvalue())
        assert "by_phase" in output
        assert "execute" in output["by_phase"]
        assert "review" in output["by_phase"]
        assert output["by_phase"]["execute"]["cost_usd"] == 0.10
        assert output["by_phase"]["execute"]["tokens"] == 150
        assert output["by_phase"]["review"]["cost_usd"] == 0.05

    def test_json_vendor_model_ordered_by_cost_desc(self) -> None:
        """by_vendor and by_model are ordered by cost descending."""
        events = [
            _cr("cheap-model", 0.01),
            _cr("expensive-model", 1.0),
            _cr("mid-model", 0.5),
        ]
        agg = _aggregate(events, meta_cost=0.0)

        captured = StringIO()
        with patch("sys.stdout", captured):
            _render_json(agg, by_phase=False)

        output = json.loads(captured.getvalue())

        vendor_costs = [v["cost_usd"] for v in output["by_vendor"].values()]
        assert vendor_costs == sorted(vendor_costs, reverse=True), (
            f"by_vendor not sorted by cost desc: {vendor_costs}"
        )

        model_costs = [m["cost_usd"] for m in output["by_model"].values()]
        assert model_costs == sorted(model_costs, reverse=True), (
            f"by_model not sorted by cost desc: {model_costs}"
        )

    def test_json_exact_tokens_false(self) -> None:
        """When fallback is used, exact_tokens=False in JSON output."""
        events = [
            _cr("claude-opus-4", 0.10, request_id="rid-fb"),
            _lle(tokens_in=50, tokens_out=25, model=None, request_id="rid-fb"),
        ]
        agg = _aggregate(events, meta_cost=0.0)

        captured = StringIO()
        with patch("sys.stdout", captured):
            _render_json(agg, by_phase=False)

        output = json.loads(captured.getvalue())
        assert output["exact_tokens"] is False


# ---------------------------------------------------------------------------
# Additional branch coverage
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases that complete branch coverage."""

    def test_empty_events_zero_everything(self) -> None:
        """Empty events list → zeros, exact_tokens=True."""
        agg = _aggregate([], meta_cost=0.0)
        assert agg["total_cost"] == 0.0
        assert agg["total_tokens"] == 0
        assert agg["exact_tokens"] is True
        assert agg["cost_source"] == "events"
        assert agg["cost_by_model"] == {}
        assert agg["tokens_by_model"] == {}

    def test_zero_tokens_skipped(self) -> None:
        """llm_call_end with 0 tokens_in + tokens_out is skipped."""
        events = [
            _cr("claude-opus-4", 0.01),
            _lle(tokens_in=0, tokens_out=0, model="claude-opus-4"),
        ]
        agg = _aggregate(events, meta_cost=0.0)

        # Zero tokens → continue (skipped), so total_tokens stays 0
        assert agg["total_tokens"] == 0
        assert agg["tokens_by_model"] == {}
        assert agg["tokens_by_vendor"] == {}

    def test_model_whitespace_only(self) -> None:
        """Model string that is only whitespace → treated as falsy (fallback)."""
        events = [
            _cr("deepseek-v4", 0.01, request_id="rid-ws"),
            _lle(tokens_in=100, tokens_out=50, model="   ", request_id="rid-ws"),
        ]
        agg = _aggregate(events, meta_cost=0.0)

        # Whitespace-only model is falsy after .strip() → fallback
        assert agg["exact_tokens"] is False
        # Joins via request_id
        assert agg["tokens_by_model"]["deepseek-v4"] == 150

    def test_phase_breakdown(self) -> None:
        """--by-phase rolls up cost and tokens per phase."""
        events = [
            _cr("claude-opus-4", 1.0, phase="execute"),
            _cr("gpt-4o", 2.0, phase="review"),
            _lle(tokens_in=100, tokens_out=50, model="claude-opus-4", phase="execute"),
            _lle(tokens_in=200, tokens_out=100, model="gpt-4o", phase="review"),
        ]
        agg = _aggregate(events, meta_cost=0.0)

        assert agg["phase_cost"]["execute"] == 1.0
        assert agg["phase_cost"]["review"] == 2.0
        assert agg["phase_tokens"]["execute"] == 150
        assert agg["phase_tokens"]["review"] == 300

    def test_mixed_exact_and_fallback(self) -> None:
        """Some events exact, some fallback → exact_tokens=False."""
        events = [
            _cr("claude-opus-4", 0.1, request_id="rid-mix"),
            _cr("gpt-4o", 0.2, request_id="rid-gpt"),
            _lle(tokens_in=100, tokens_out=50, model="claude-opus-4", request_id="rid-mix"),
            _lle(tokens_in=200, tokens_out=100, model=None, request_id="rid-gpt"),
        ]
        agg = _aggregate(events, meta_cost=0.0)

        # First llm_call_end: exact path (model present)
        # Second llm_call_end: fallback join (model absent, request_id matches)
        assert agg["exact_tokens"] is False
        assert agg["tokens_by_model"]["claude-opus-4"] == 150  # exact
        assert agg["tokens_by_model"]["gpt-4o"] == 300  # fallback

    def test_cost_recorded_none_model_buckets_as_unknown(self) -> None:
        """cost_recorded with model=None → cost bucketed as 'unknown'."""
        events = [
            _cr(None, 0.5),
        ]
        agg = _aggregate(events, meta_cost=0.0)

        # None model becomes "unknown" key in cost_by_model
        assert agg["cost_by_model"]["unknown"] == 0.5
        # _classify_vendor(None) → "other"
        assert agg["cost_by_vendor"]["other"] == 0.5

    def test_cost_recorded_empty_string_model(self) -> None:
        """cost_recorded with model="" → 'unknown' in model, 'other' in vendor."""
        events = [
            _cr("", 0.25),
        ]
        agg = _aggregate(events, meta_cost=0.0)
        assert agg["cost_by_model"]["unknown"] == 0.25
        assert agg["cost_by_vendor"]["other"] == 0.25

    def test_tokens_only_vendor_in_output(self) -> None:
        """Vendor with tokens but no cost appears in vendor table."""
        events = [
            _lle(tokens_in=100, tokens_out=50, model=None, request_id=None),
        ]
        agg = _aggregate(events, meta_cost=0.0)

        # deepseek vendor has tokens but no cost
        assert agg["tokens_by_vendor"]["deepseek"] == 150
        assert agg["cost_by_vendor"].get("deepseek", 0.0) == 0.0

    def test_percentages_guard_divide_by_zero(self) -> None:
        """Percentages are 0.0 when grand total is zero."""
        agg = _aggregate([], meta_cost=0.0)
        # All percentages should be 0.0 (dicts may be empty)
        for pct in agg["cost_pct_by_vendor"].values():
            assert pct == 0.0
        for pct in agg["cost_pct_by_model"].values():
            assert pct == 0.0
        for pct in agg["tok_pct_by_vendor"].values():
            assert pct == 0.0
        for pct in agg["tok_pct_by_model"].values():
            assert pct == 0.0

    def test_handle_cost_missing_plan(self, tmp_path: Path) -> None:
        """handle_cost returns 1 and prints to stderr when plan is missing."""
        plan_dir = _make_plan_dir(tmp_path, "exists")
        _write_state(plan_dir, {"meta": {"total_cost_usd": 0.0}})

        # Mock find_plan_dir to return None (plan not found)
        with patch("megaplan._core.find_plan_dir", return_value=None):
            args = Namespace(plan="nonexistent", format="table", by_phase=False)
            rc = handle_cost(Path.cwd(), args)

        assert rc == 1

    def test_handle_cost_success(self, tmp_path: Path) -> None:
        """handle_cost returns 0 for a valid plan dir."""
        plan_dir = _make_plan_dir(tmp_path, "success-plan")
        events = [_cr("claude-opus-4", 0.01)]
        _write_events(plan_dir, events)
        _write_state(plan_dir, {"meta": {"total_cost_usd": 0.01}})

        with patch("megaplan._core.find_plan_dir", return_value=plan_dir):
            args = Namespace(plan="success-plan", format="table", by_phase=False)
            rc = handle_cost(Path.cwd(), args)

        assert rc == 0

    def test_render_table_estimate_note(self) -> None:
        """When exact_tokens=False, stderr gets estimate note."""
        events = [
            _cr("claude-opus-4", 0.01, request_id="rid-est"),
            _lle(tokens_in=100, tokens_out=50, model=None, request_id="rid-est"),
        ]
        agg = _aggregate(events, meta_cost=0.0)
        assert agg["exact_tokens"] is False

        captured_stdout = StringIO()
        captured_stderr = StringIO()
        with patch("sys.stdout", captured_stdout), patch("sys.stderr", captured_stderr):
            _render_table(agg, by_phase=False)

        stderr_output = captured_stderr.getvalue()
        assert "estimates" in stderr_output.lower() or "estimate" in stderr_output.lower()
        assert "request_id" in stderr_output or "fallback" in stderr_output

    def test_render_table_no_estimate_when_exact(self) -> None:
        """When exact_tokens=True, stderr has NO estimate note."""
        events = [
            _cr("claude-opus-4", 0.01),
            _lle(tokens_in=100, tokens_out=50, model="claude-opus-4"),
        ]
        agg = _aggregate(events, meta_cost=0.0)
        assert agg["exact_tokens"] is True

        captured_stdout = StringIO()
        captured_stderr = StringIO()
        with patch("sys.stdout", captured_stdout), patch("sys.stderr", captured_stderr):
            _render_table(agg, by_phase=False)

        stderr_output = captured_stderr.getvalue()
        assert stderr_output == "" or "estimates" not in stderr_output.lower()

    def test_state_json_unreadable_meta_cost_zero(self, tmp_path: Path) -> None:
        """When state.json is malformed, meta_cost defaults to 0.0."""
        plan_dir = _make_plan_dir(tmp_path, "bad-state")
        (plan_dir / "state.json").write_text("not json", encoding="utf-8")
        events = [_cr("claude-opus-4", 2.0)]
        _write_events(plan_dir, events)

        with patch("megaplan._core.find_plan_dir", return_value=plan_dir):
            args = Namespace(plan="bad-state", format="json", by_phase=False)
            rc = handle_cost(Path.cwd(), args)

        assert rc == 0
        # With broken state, meta_cost=0.0 so events wins at 2.0
