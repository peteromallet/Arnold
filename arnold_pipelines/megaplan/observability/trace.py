"""``megaplan trace`` — event-stream readers over ``events.ndjson``.

Three formatters:
- ``json``: one JSON event per line, pipe-friendly.
- ``pretty``: colored kind labels, relative timestamps.
- ``narrative``: synthesised prose; consecutive ``llm_token_heartbeat``
  events are grouped into a single summary line.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

from arnold_pipelines.megaplan.observability.events import read_events


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _since_seconds(raw: str | None) -> float | None:
    """Parse a duration string like ``30s``, ``5m``, ``1h`` into seconds."""
    if raw is None:
        return None
    raw = raw.strip().lower()
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    for suffix, mult in multipliers.items():
        if raw.endswith(suffix):
            try:
                return float(raw[: -len(suffix)]) * mult
            except ValueError:
                return None
    try:
        return float(raw)  # bare number = seconds
    except ValueError:
        return None


def _relative_timestamp(ts_str: str, now: datetime) -> str:
    """Return a human-friendly relative time like ``38m 22s ago``."""
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return ts_str
    diff = (now - ts).total_seconds()
    if diff < 0:
        return "just now"
    if diff < 60:
        return f"{int(diff)}s ago"
    if diff < 3600:
        mins = int(diff // 60)
        secs = int(diff % 60)
        return f"{mins}m {secs}s ago"
    hours = int(diff // 3600)
    mins = int((diff % 3600) // 60)
    return f"{hours}h {mins}m ago"


def _kind_label(kind: str) -> str:
    """Return a short, color-keyed label for an event kind."""
    labels: dict[str, str] = {
        "init": "INIT",
        "phase_start": "▶ START",
        "phase_end": "◼ END",
        "phase_retry": "↻ RETRY",
        "state_transition": "→ STATE",
        "lock_acquired": "🔒 LOCK+",
        "lock_released": "🔓 LOCK-",
        "plan_aborted": "✗ ABORT",
        "plan_finished": "✓ DONE",
        "subprocess_spawned": "▶ PROC",
        "subprocess_exited": "◼ PROC",
        "subprocess_signaled": "☠ SIGNAL",
        "llm_call_start": "★ LLM",
        "llm_token_heartbeat": "♡ TOK",
        "llm_call_end": "☆ LLM",
        "llm_call_error": "✗ LLM",
        "artifact_written": "📄 ART",
        "artifact_invalidated": "🗑 ART",
        "anchor_captured": "⚓ ANCHOR",
        "anchor_missing_artifact": "⚓ MISSING",
        "override_applied": "⚡ OVERRIDE",
        "flag_raised": "🚩 FLAG+",
        "flag_resolved": "✅ FLAG-",
        "note_added": "📝 NOTE",
        "cost_recorded": "💰 COST",
        "health_check_failed": "💥 HEALTH",
        "drift_detected": "↯ DRIFT",
        "session_start": "▷ SESSION",
        "inference": "⚙ INFER",
        "tool": "🔧 TOOL",
        "git": "⎇ GIT",
        "transition": "↪ TRANS",
    }
    return labels.get(kind, kind.upper())


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def format_json(events: Sequence[dict]) -> str:
    """One JSON event per line, no decoration."""
    lines = [json.dumps(ev, ensure_ascii=False, separators=(",", ":")) for ev in events]
    return "\n".join(lines)


def format_pretty(events: Sequence[dict], *, now: datetime | None = None) -> str:
    """Colored kind labels with relative timestamps."""
    if now is None:
        now = _now_utc()
    lines: list[str] = []
    for ev in events:
        ts = ev.get("ts_utc", "")
        rel = _relative_timestamp(ts, now) if ts else ""
        kind = ev.get("kind", "?")
        label = _kind_label(kind)
        seq = ev.get("seq", "?")
        phase = ev.get("phase", "")
        payload = ev.get("payload", {})

        line = f"[{seq:>5d}] {ts[:19].replace('T', ' ')} ({rel:>12s}) {label}"
        if phase:
            line += f"  [{phase}]"
        # Show key payload fields compactly
        for key in ("path", "model", "provider", "tokens_emitted_so_far", "cost_usd"):
            val = payload.get(key)
            if val is not None:
                line += f"  {key}={val}"
        lines.append(line)
    return "\n".join(lines)


def format_narrative(events: Sequence[dict], *, now: datetime | None = None) -> str:
    """Synthesised prose; groups consecutive llm_token_heartbeat events."""
    if now is None:
        now = _now_utc()

    if not events:
        return "(no events)"

    lines: list[str] = []
    heartbeat_buffer: list[dict] = []
    last_llm_model: str | None = None

    def _flush_heartbeats() -> None:
        nonlocal last_llm_model
        if not heartbeat_buffer:
            return
        first = heartbeat_buffer[0]
        last = heartbeat_buffer[-1]
        count = len(heartbeat_buffer)
        tokens_first = first.get("payload", {}).get("tokens_emitted_so_far", 0)
        tokens_last = last.get("payload", {}).get("tokens_emitted_so_far", 0)

        ts_first = first.get("ts_utc", "")
        try:
            t_first = datetime.fromisoformat(ts_first.replace("Z", "+00:00"))
            t_last = datetime.fromisoformat(ts_last.replace("Z", "+00:00"))
            elapsed = (t_last - t_first).total_seconds()
            tok_s = (tokens_last - tokens_first) / elapsed if elapsed > 0 else 0
        except Exception:
            elapsed = 0
            tok_s = 0

        ts_last = last.get("ts_utc", "")
        rel = _relative_timestamp(ts_last, now) if ts_last else ""
        model_str = f" using {last_llm_model}" if last_llm_model else ""
        lines.append(
            f"{ts_last[:19].replace('T', ' ')} ({rel}) →"
            f" Token stream{model_str}: emitted {tokens_last} tokens at ~{tok_s:.0f} tok/s"
            f" ({count} heartbeats over {elapsed:.0f}s)"
        )
        heartbeat_buffer.clear()

    for ev in events:
        kind = ev.get("kind", "")
        if kind == "llm_token_heartbeat":
            heartbeat_buffer.append(ev)
            continue
        else:
            _flush_heartbeats()

        ts = ev.get("ts_utc", "")
        rel = _relative_timestamp(ts, now) if ts else ""
        phase = ev.get("phase", "")
        payload = ev.get("payload", {})

        if kind == "init":
            plan_name = payload.get("plan_name", "?")
            lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → Plan '{plan_name}' initialized.")
        elif kind == "phase_start":
            name = payload.get("phase") or phase or "?"
            model = payload.get("model", "")
            model_str = f" with {model}" if model else ""
            lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → Phase '{name}' started{model_str}.")
        elif kind == "phase_end":
            name = payload.get("phase") or phase or "?"
            dur = payload.get("duration_s", 0)
            lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → Phase '{name}' ended (took {dur:.0f}s).")
        elif kind == "phase_retry":
            name = payload.get("phase") or phase or "?"
            reason = payload.get("reason", "")
            lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → Phase '{name}' retry: {reason}.")
        elif kind == "state_transition":
            frm = payload.get("from", "?")
            to = payload.get("to", "?")
            lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → State transition: {frm} → {to}.")
        elif kind == "lock_acquired":
            lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → Lock acquired.")
        elif kind == "lock_released":
            lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → Lock released.")
        elif kind == "plan_aborted":
            reason = payload.get("reason", "")
            lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → Plan aborted. {reason}")
        elif kind == "plan_finished":
            lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → Plan finished.")
        elif kind == "subprocess_spawned":
            pid = payload.get("pid", "?")
            role = payload.get("role", "?")
            lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → Subprocess spawned: pid={pid} role={role}.")
        elif kind == "subprocess_exited":
            pid = payload.get("pid", "?")
            rc = payload.get("returncode", "?")
            dur = payload.get("duration_s", 0)
            lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → Subprocess pid={pid} exited with code={rc} after {dur:.0f}s.")
        elif kind == "subprocess_signaled":
            pid = payload.get("pid", "?")
            sig = payload.get("signal", "?")
            lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → Subprocess pid={pid} killed by signal {sig}.")
        elif kind == "llm_call_start":
            model = payload.get("model", "?")
            provider = payload.get("provider", "?")
            last_llm_model = model
            lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → LLM call started: {provider}/{model}.")
        elif kind == "llm_call_end":
            tokens_in = payload.get("tokens_in", 0)
            tokens_out = payload.get("tokens_out", 0)
            cost = payload.get("cost_usd", 0)
            dur = payload.get("duration_s", 0)
            lines.append(
                f"{ts[:19].replace('T', ' ')} ({rel}) → LLM call ended: "
                f"{tokens_in}+{tokens_out} tokens, ${cost:.4f}, {dur:.0f}s."
            )
        elif kind == "llm_call_error":
            err = payload.get("provider_error_code", "?")
            retry = payload.get("retry_after_s", 0)
            lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → LLM call error: {err}, retry after {retry}s.")
        elif kind == "artifact_written":
            path = payload.get("path", "?")
            if isinstance(path, str) and path.startswith("anchors/"):
                lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → Anchor artifact written: {path}.")
            else:
                lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → Artifact written: {path}.")
        elif kind == "artifact_invalidated":
            path = payload.get("path", "?")
            lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → Artifact invalidated: {path}.")
        elif kind == "anchor_captured":
            lines.append(
                f"{ts[:19].replace('T', ' ')} ({rel}) → Anchor captured: "
                f"{payload.get('anchor_type', 'anchor')}/{payload.get('scope', 'unknown')} at {payload.get('artifact_path', '?')}."
            )
        elif kind == "anchor_missing_artifact":
            lines.append(
                f"{ts[:19].replace('T', ' ')} ({rel}) → Anchor artifact missing: "
                f"{payload.get('anchor_type', 'anchor')} {payload.get('artifact_path', '?')}."
            )
        elif kind == "override_applied":
            action = payload.get("action", "?")
            reason = payload.get("reason", "")
            lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → Override '{action}' applied. {reason}")
        elif kind == "flag_raised":
            fid = payload.get("flag_id", "?")
            severity = payload.get("severity", "?")
            lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → Flag raised: {fid} [{severity}].")
        elif kind == "flag_resolved":
            fid = payload.get("flag_id", "?")
            lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → Flag resolved: {fid}.")
        elif kind == "note_added":
            tag = payload.get("tag", "")
            note = payload.get("note", "")
            lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → Note added: {tag} — {note}.")
        elif kind == "cost_recorded":
            cost = payload.get("cost_usd", 0)
            provider = payload.get("provider", "?")
            model = payload.get("model", "?")
            lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → Cost: ${cost:.4f} ({provider}/{model}).")
        elif kind == "health_check_failed":
            check = payload.get("check", "?")
            lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → Health check failed: {check}.")
        elif kind == "drift_detected":
            msg = payload.get("message", "")
            lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → Drift detected: {msg}.")
        elif kind == "session_start":
            session_id = payload.get("session_id", "?")
            env = payload.get("environment", "")
            env_str = f" env={env}" if env else ""
            lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → Session started: {session_id}{env_str}.")
        elif kind == "inference":
            model = payload.get("model", "?")
            provider = payload.get("provider", "?")
            dur = payload.get("duration_s", 0)
            tokens_in = payload.get("tokens_in", 0)
            tokens_out = payload.get("tokens_out", 0)
            lines.append(
                f"{ts[:19].replace('T', ' ')} ({rel}) → Inference: {provider}/{model}, "
                f"{tokens_in}+{tokens_out} tokens, {dur:.0f}s."
            )
        elif kind == "tool":
            tool_name = payload.get("tool_name", "?")
            dur = payload.get("duration_s", 0)
            lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → Tool: {tool_name} ({dur:.0f}s).")
        elif kind == "git":
            operation = payload.get("operation", "?")
            repo = payload.get("repo", "")
            repo_str = f" [{repo}]" if repo else ""
            lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → Git: {operation}{repo_str}.")
        elif kind == "transition":
            frm = payload.get("from", "?")
            to = payload.get("to", "?")
            trigger = payload.get("trigger", "")
            trig_str = f" via {trigger}" if trigger else ""
            lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → Transition: {frm} → {to}{trig_str}.")
        else:
            lines.append(f"{ts[:19].replace('T', ' ')} ({rel}) → {kind}: {json.dumps(payload)}")

    _flush_heartbeats()
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def handle_trace(root: Path, args: argparse.Namespace) -> int:
    """``megaplan trace`` entry point; returns exit code."""
    from arnold_pipelines.megaplan._core import find_plan_dir

    cwd = Path.cwd()
    plan_dir = find_plan_dir(cwd, args.plan)
    if plan_dir is None:
        print(f"trace: plan '{args.plan}' not found", file=sys.stderr)
        return 1

    ndjson = plan_dir / "events.ndjson"
    if not ndjson.exists():
        print(f"trace: no events.ndjson for plan '{args.plan}'", file=sys.stderr)
        return 1

    fmt = getattr(args, "format", "pretty")
    follow = getattr(args, "follow", False)
    phase_filter = getattr(args, "phase", None)
    since_raw: str | None = getattr(args, "since", None)

    since_cutoff = _since_seconds(since_raw)

    if follow:

        def _follow_loop() -> None:
            last_size: int = 0
            last_seq: int | None = None
            while True:
                try:
                    stat = ndjson.stat()
                    current_size = stat.st_size
                except FileNotFoundError:
                    time.sleep(1)
                    continue
                if current_size > last_size:
                    events = list(read_events(plan_dir, since_seq=last_seq))
                    if events:
                        now = _now_utc()
                        filtered: list[dict] = []
                        for ev in events:
                            if phase_filter and ev.get("phase") != phase_filter:
                                continue
                            if since_cutoff is not None:
                                try:
                                    ts = datetime.fromisoformat(
                                        ev.get("ts_utc", "").replace("Z", "+00:00")
                                    )
                                    if (now - ts).total_seconds() > since_cutoff:
                                        continue
                                except (ValueError, TypeError):
                                    pass
                            filtered.append(ev)
                        if filtered:
                            if fmt == "json":
                                print(format_json(filtered), flush=True)
                            elif fmt == "narrative":
                                print(format_narrative(filtered, now=now), flush=True)
                            else:
                                print(format_pretty(filtered, now=now), flush=True)
                            last_seq = filtered[-1].get("seq")
                    last_size = current_size
                time.sleep(1)

        try:
            _follow_loop()
        except KeyboardInterrupt:
            return 0
    else:
        events = list(read_events(plan_dir))
        now = _now_utc()
        filtered: list[dict] = []
        for ev in events:
            if phase_filter and ev.get("phase") != phase_filter:
                continue
            if since_cutoff is not None:
                try:
                    ts = datetime.fromisoformat(ev.get("ts_utc", "").replace("Z", "+00:00"))
                    if (now - ts).total_seconds() > since_cutoff:
                        continue
                except (ValueError, TypeError):
                    pass
            filtered.append(ev)

        if fmt == "json":
            print(format_json(filtered))
        elif fmt == "narrative":
            print(format_narrative(filtered, now=now))
        else:
            print(format_pretty(filtered, now=now))

    return 0
