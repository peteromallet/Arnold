"""``megaplan cost`` — plan cost breakdown from events.ndjson and state.json.

Mirrors the conventions of trace.py and introspect.py: imported as
``handle_cost(root, args) -> int`` from the CLI layer.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from arnold_pipelines.megaplan.observability.events import EventKind, read_events


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _vendor_for_cost_event(payload: dict, model: str | None) -> str:
    """T27 — R5-aware vendor lookup. When UNIFIED_EMIT=1 or R5_UNIFIED=1 and
    the payload carries a provenance dict with 'vendor', return it directly
    (no _classify_vendor call). Otherwise fall through to the legacy path.
    """
    try:
        from arnold_pipelines.megaplan.feature_flags import unified_emit_on, unified_evaluand_on
        if unified_emit_on() or unified_evaluand_on():
            provenance = payload.get("provenance") if isinstance(payload, dict) else None
            if isinstance(provenance, dict):
                vendor = provenance.get("vendor")
                if isinstance(vendor, str) and vendor:
                    return vendor
    except Exception:
        pass
    return _classify_vendor(model)


def _classify_vendor(model: str | None) -> str:
    """Classify a model string into one of four vendor buckets.

    Ordering is deliberate: ``gemini`` must be checked BEFORE ``deepseek``
    so that Gemini models (including ``gemini-*-flash``) land in ``other``.
    There is NO bare ``flash`` substring check — all real DeepSeek flash
    variants already contain ``deepseek``.
    """
    if not model:
        return "other"

    m = model.lower().strip()

    # Claude: opus, sonnet, or claude
    if "opus" in m or "sonnet" in m or "claude" in m:
        return "claude"

    # OpenAI / Codex: gpt or codex
    if "gpt" in m or "codex" in m:
        return "codex"

    # Gemini → other (checked BEFORE deepseek to keep gemini-*-flash out)
    if "gemini" in m:
        return "other"

    # DeepSeek / Hermes / Shannon
    if "deepseek" in m or "hermes" in m or "shannon" in m:
        return "deepseek"

    return "other"


def _load_state(plan_dir: Path) -> dict | None:
    """Load state.json from *plan_dir*, returning None if missing/unreadable."""
    # cache-tolerant: cost rollup view.
    state_file = plan_dir / "state.json"
    if not state_file.exists():
        return None
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def _aggregate(events: list[dict], meta_cost: float) -> dict:
    """Run the full cost + token aggregation over *events*.

    Returns a dict with all computed structures so the CLI entry point
    (and future output formatters) can access them without re-scanning.
    """
    # ── cost accumulators ──────────────────────────────────────────────
    cost_by_model: dict[str, float] = defaultdict(float)
    cost_by_vendor: dict[str, float] = defaultdict(float)
    events_cost: float = 0.0

    # request_id → model map built from COST_RECORDED (None keys excluded)
    rid_to_model: dict[str, str] = {}

    # ── token accumulators ─────────────────────────────────────────────
    tokens_by_model: dict[str, int] = defaultdict(int)
    tokens_by_vendor: dict[str, int] = defaultdict(int)
    exact_tokens: bool = True

    # ── by-phase accumulators (only when --by-phase is requested) ──────
    phase_cost: dict[str, float] = defaultdict(float)
    phase_tokens: dict[str, int] = defaultdict(int)

    # ── R7 monoculture / cache sensors (output-only) ──────────────────
    phase_cache_read: dict[str, int] = defaultdict(int)
    phase_cache_input: dict[str, int] = defaultdict(int)
    distinct_models: set[str] = set()
    cost_records_total = 0

    # ── single pass over events ────────────────────────────────────────
    for ev in events:
        kind = ev.get("kind")
        payload = ev.get("payload") or {}
        phase = ev.get("phase") or ""

        if kind == EventKind.COST_RECORDED:
            model = payload.get("model")
            cost = float(payload.get("cost_usd", 0) or 0)

            # per-model cost
            model_key = str(model).strip() if model else "unknown"
            cost_by_model[model_key] += cost

            # per-vendor cost
            # T27: R5 read branch — gated UNIFIED_EMIT=1 or R5_UNIFIED=1.
            # When the event payload carries RunEnvelope.provenance with a
            # vendor (Step 10a field), read it directly instead of calling
            # _classify_vendor. Old branch stays live and authoritative.
            vendor = _vendor_for_cost_event(payload, model)
            cost_by_vendor[vendor] += cost

            # running events_cost sum (before reconciliation)
            events_cost += cost

            # request_id → model map (exclude None / empty request_ids)
            rid = payload.get("request_id")
            if rid is not None and model:
                rid_to_model[str(rid)] = str(model)

            # by-phase
            if phase:
                phase_cost[phase] += cost

            # R7 monoculture sensor — count cost records and distinct models.
            cost_records_total += 1
            if model:
                distinct_models.add(str(model))

        elif kind == EventKind.LLM_CALL_END:
            tokens_in = int(payload.get("tokens_in", 0) or 0)
            tokens_out = int(payload.get("tokens_out", 0) or 0)
            tokens = tokens_in + tokens_out
            if tokens <= 0:
                continue

            payload_model = payload.get("model")
            # phase
            if phase:
                phase_tokens[phase] += tokens
                # Prefix-cache-hit-rate sensor (output-only): accumulate
                # cache_read_tokens vs total input tokens per phase.
                phase_cache_read[phase] += int(payload.get("cache_read_tokens", 0) or 0)
                phase_cache_input[phase] += tokens_in

            if payload_model and isinstance(payload_model, str) and payload_model.strip():
                # ── exact path: model is present and truthy ────────────
                m = payload_model.strip()
                tokens_by_model[m] += tokens
                tokens_by_vendor[_classify_vendor(m)] += tokens
            else:
                # ── fallback path ──────────────────────────────────────
                exact_tokens = False
                rid = payload.get("request_id")
                if rid is not None:
                    mapped = rid_to_model.get(str(rid))
                    if mapped is not None:
                        # join succeeded → attribute to mapped model
                        tokens_by_model[mapped] += tokens
                        tokens_by_vendor[_classify_vendor(mapped)] += tokens
                        continue
                # join impossible (None request_id or unmatched) → bucket as deepseek
                tokens_by_vendor["deepseek"] += tokens
                # no model-level attribution in this path

        # M9 T24: INFERENCE events carry model/token/cost data alongside
        # the legacy LLM_CALL_END pathway.  Token keys are tokens_in /
        # tokens_out (same as LLM_CALL_END); cost_usd may be present.
        elif kind == EventKind.INFERENCE:
            tokens_in = int(payload.get("tokens_in", 0) or 0)
            tokens_out = int(payload.get("tokens_out", 0) or 0)
            tokens = tokens_in + tokens_out

            # Cost from inference event (may be absent — only count when present)
            inf_cost = payload.get("cost_usd")
            if inf_cost is not None:
                try:
                    inf_cost = float(inf_cost)
                except (TypeError, ValueError):
                    inf_cost = 0.0
                if inf_cost > 0:
                    payload_model = payload.get("model")
                    model_key = str(payload_model).strip() if payload_model else "unknown"
                    cost_by_model[model_key] += inf_cost
                    vendor = _vendor_for_cost_event(payload, payload_model)
                    cost_by_vendor[vendor] += inf_cost
                    events_cost += inf_cost
                    cost_records_total += 1
                    if payload_model:
                        distinct_models.add(str(payload_model))
                    if phase:
                        phase_cost[phase] += inf_cost

            if tokens <= 0:
                continue

            payload_model = payload.get("model")
            # phase token accumulation
            if phase:
                phase_tokens[phase] += tokens

            if payload_model and isinstance(payload_model, str) and payload_model.strip():
                m = payload_model.strip()
                tokens_by_model[m] += tokens
                tokens_by_vendor[_classify_vendor(m)] += tokens
            else:
                # No model — estimate via vendor default
                exact_tokens = False
                tokens_by_vendor["deepseek"] += tokens

    # ── cost reconciliation (same rule as introspect.py:530-560) ──────
    # Take the larger of events_cost vs meta_cost so we never undercount.
    if meta_cost > events_cost:
        total_cost = meta_cost
        cost_source = "state_meta"
    else:
        total_cost = events_cost
        cost_source = "events"

    # ── grand token total ──────────────────────────────────────────────
    total_tokens = sum(tokens_by_vendor.values())

    # ── percentages (guard divide-by-zero) ─────────────────────────────
    def _pct(part: float, whole: float) -> float:
        if whole == 0.0:
            return 0.0
        return (part / whole) * 100.0

    cost_pct_by_model = {
        m: _pct(c, total_cost) for m, c in cost_by_model.items()
    }
    cost_pct_by_vendor = {
        v: _pct(c, total_cost) for v, c in cost_by_vendor.items()
    }
    tok_pct_by_model = {
        m: _pct(t, total_tokens) for m, t in tokens_by_model.items()
    }
    tok_pct_by_vendor = {
        v: _pct(t, total_tokens) for v, t in tokens_by_vendor.items()
    }

    return {
        "cost_by_model": dict(cost_by_model),
        "cost_by_vendor": dict(cost_by_vendor),
        "tokens_by_model": dict(tokens_by_model),
        "tokens_by_vendor": dict(tokens_by_vendor),
        "cost_pct_by_model": cost_pct_by_model,
        "cost_pct_by_vendor": cost_pct_by_vendor,
        "tok_pct_by_model": tok_pct_by_model,
        "tok_pct_by_vendor": tok_pct_by_vendor,
        "events_cost": events_cost,
        "meta_cost": meta_cost,
        "total_cost": total_cost,
        "total_tokens": total_tokens,
        "cost_source": cost_source,
        "exact_tokens": exact_tokens,
        "phase_cost": dict(phase_cost),
        "phase_tokens": dict(phase_tokens),
        # R7 output-only sensors — recorded only, no consumer (M5-cal owns routing).
        "phase_prefix_cache_hit_rate": {
            p: (phase_cache_read[p] / phase_cache_input[p])
            if phase_cache_input.get(p)
            else 0.0
            for p in set(phase_cache_input) | set(phase_cache_read)
        },
        "monoculture_index": (
            (len(distinct_models) / cost_records_total) if cost_records_total else 0.0
        ),
    }


# ---------------------------------------------------------------------------
# Output rendering (read-only — no emit(), no file writes)
# ---------------------------------------------------------------------------


def _render_table(agg: dict, by_phase: bool) -> None:
    """Print human-readable cost tables to stdout.

    Read-only invariant: this function only reads *agg* and writes to
    stdout/stderr.  It never calls emit() or touches the plan directory.
    """
    # ── grand total line ──────────────────────────────────────────────
    print(f"total cost: ${agg['total_cost']:.6f}  (source: {agg['cost_source']})")
    print(f"total tokens: {agg['total_tokens']}")

    # ── by-vendor table ───────────────────────────────────────────────
    vendor_rows: list[tuple[str, float, float, int, float]] = []
    for vendor in agg["cost_by_vendor"]:
        c = agg["cost_by_vendor"][vendor]
        cp = agg["cost_pct_by_vendor"].get(vendor, 0.0)
        t = agg["tokens_by_vendor"].get(vendor, 0)
        tp = agg["tok_pct_by_vendor"].get(vendor, 0.0)
        vendor_rows.append((vendor, c, cp, t, tp))
    vendor_rows.sort(key=lambda r: r[1], reverse=True)

    # Include any vendors that have tokens but no cost record.
    seen_vendors = {r[0] for r in vendor_rows}
    for vendor in agg["tokens_by_vendor"]:
        if vendor not in seen_vendors:
            t = agg["tokens_by_vendor"][vendor]
            tp = agg["tok_pct_by_vendor"].get(vendor, 0.0)
            vendor_rows.append((vendor, 0.0, 0.0, t, tp))

    if vendor_rows:
        print("\n--- by vendor ---")
        print(f"{'vendor':12s} {'cost':>12s} {'cost%':>7s} {'tokens':>10s} {'tok%':>7s}")
        print("-" * 54)
        for vendor, c, cp, t, tp in vendor_rows:
            print(
                f"{vendor:12s} ${c:>11.6f} {cp:>6.1f}% "
                f"{t:>10d} {tp:>6.1f}%"
            )

    # ── by-model table ────────────────────────────────────────────────
    model_rows: list[tuple[str, float, float, int, float]] = []
    for model in agg["cost_by_model"]:
        c = agg["cost_by_model"][model]
        cp = agg["cost_pct_by_model"].get(model, 0.0)
        t = agg["tokens_by_model"].get(model, 0)
        tp = agg["tok_pct_by_model"].get(model, 0.0)
        model_rows.append((model, c, cp, t, tp))
    model_rows.sort(key=lambda r: r[1], reverse=True)

    seen_models = {r[0] for r in model_rows}
    for model in agg["tokens_by_model"]:
        if model not in seen_models:
            t = agg["tokens_by_model"][model]
            tp = agg["tok_pct_by_model"].get(model, 0.0)
            model_rows.append((model, 0.0, 0.0, t, tp))

    if model_rows:
        # Compute column width for model names (min 12).
        max_name = max((len(m) for m, *_ in model_rows), default=12)
        name_w = max(max_name, 12)
        print("\n--- by model ---")
        print(
            f"{'model':{name_w}s} {'cost':>12s} {'cost%':>7s} "
            f"{'tokens':>10s} {'tok%':>7s}"
        )
        print("-" * (name_w + 42))
        for model, c, cp, t, tp in model_rows:
            print(
                f"{model:{name_w}s} ${c:>11.6f} {cp:>6.1f}% "
                f"{t:>10d} {tp:>6.1f}%"
            )

    # ── by-phase (only when requested) ─────────────────────────────────
    if by_phase:
        all_phases = sorted(
            set(agg["phase_cost"].keys()) | set(agg["phase_tokens"].keys())
        )
        if all_phases:
            print("\n--- by phase ---")
            print(f"{'phase':24s} {'cost':>12s} {'tokens':>10s}")
            print("-" * 50)
            for p in all_phases:
                pc = agg["phase_cost"].get(p, 0.0)
                pt = agg["phase_tokens"].get(p, 0)
                print(f"{p:24s} ${pc:>11.6f} {pt:>10d}")

    # ── estimate note ─────────────────────────────────────────────────
    if not agg["exact_tokens"]:
        print(
            "\n⚠  Token counts are *estimates* — some LLM_CALL_END events "
            "lacked a model field and were attributed via the legacy "
            "request_id → deepseek fallback.",
            file=sys.stderr,
        )


def _render_json(agg: dict, by_phase: bool) -> None:
    """Emit a JSON summary to stdout.

    Read-only invariant: no emit(), no file writes.
    """
    # Order vendor/model objects by cost descending.
    vendor_order = sorted(
        agg["cost_by_vendor"], key=lambda v: agg["cost_by_vendor"][v], reverse=True
    )
    model_order = sorted(
        agg["cost_by_model"], key=lambda m: agg["cost_by_model"][m], reverse=True
    )

    output: dict = {
        "totals": {
            "cost_usd": agg["total_cost"],
            "tokens": agg["total_tokens"],
        },
        "by_vendor": {
            v: {
                "cost_usd": agg["cost_by_vendor"].get(v, 0.0),
                "cost_pct": agg["cost_pct_by_vendor"].get(v, 0.0),
                "tokens": agg["tokens_by_vendor"].get(v, 0),
                "tok_pct": agg["tok_pct_by_vendor"].get(v, 0.0),
            }
            for v in vendor_order
        },
        "by_model": {
            m: {
                "cost_usd": agg["cost_by_model"].get(m, 0.0),
                "cost_pct": agg["cost_pct_by_model"].get(m, 0.0),
                "tokens": agg["tokens_by_model"].get(m, 0),
                "tok_pct": agg["tok_pct_by_model"].get(m, 0.0),
            }
            for m in model_order
        },
        "cost_source": agg["cost_source"],
        "exact_tokens": agg["exact_tokens"],
    }

    if by_phase:
        all_phases = sorted(
            set(agg["phase_cost"].keys()) | set(agg["phase_tokens"].keys())
        )
        output["by_phase"] = {
            p: {
                "cost_usd": agg["phase_cost"].get(p, 0.0),
                "tokens": agg["phase_tokens"].get(p, 0),
            }
            for p in all_phases
        }

    print(json.dumps(output, indent=2))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def handle_cost(root: Path, args: argparse.Namespace) -> int:
    """``megaplan cost`` entry point; returns exit code.

    Read-only invariant: this handler only reads events.ndjson and
    state.json.  It never calls emit() and never writes any file.
    """
    from arnold_pipelines.megaplan._core import find_plan_dir

    cwd = Path.cwd()
    plan_dir = find_plan_dir(cwd, args.plan)
    if plan_dir is None:
        print(f"cost: plan {args.plan!r} not found", file=sys.stderr)
        return 1

    # Read cost-related events once (no new ndjson parser).
    # Read cost-related events once (no new ndjson parser).
    # M9 T24: include INFERENCE events which carry model/token/cost data
    # alongside the legacy LLM_CALL_END pathway.
    events = list(
        read_events(
            plan_dir,
            kinds=[EventKind.COST_RECORDED, EventKind.LLM_CALL_END, EventKind.INFERENCE],
        )
    )

    # Load state and defensively parse meta.total_cost_usd (same pattern as introspect).
    state = _load_state(plan_dir)
    meta_cost: float = 0.0
    if state and isinstance(state, dict):
        meta = state.get("meta")
        if isinstance(meta, dict):
            try:
                meta_cost = float(meta.get("total_cost_usd", 0.0) or 0.0)
            except (TypeError, ValueError):
                meta_cost = 0.0

    # Run aggregation.
    agg = _aggregate(events, meta_cost)

    # Resolve output flags (CLI wiring is a subsequent task; use defensive
    # getattr so the handler works standalone until then).
    fmt: str = getattr(args, "format", "table")
    by_phase: bool = getattr(args, "by_phase", False)

    if fmt == "json":
        _render_json(agg, by_phase)
    else:
        _render_table(agg, by_phase)

    return 0
