"""Build navigable retrospective reports from plan-local audit artifacts."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan._core import atomic_write_json, atomic_write_text, load_plan, read_json, resolve_plan_dir

RECEIPT_RE = re.compile(r"^step_receipt_(?P<phase>[a-z_]+)_v(?P<iteration>\d+)\.json$")


def _safe_read_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return read_json(path)
    except Exception:
        return None


def _receipt_sort_key(path: Path) -> tuple[int, str, str]:
    match = RECEIPT_RE.match(path.name)
    if not match:
        return (10_000, path.name, path.name)
    iteration = int(match.group("iteration"))
    phase_order = {
        "prep": 0,
        "plan": 1,
        "critique": 2,
        "gate": 3,
        "revise": 4,
        "finalize": 5,
        "execute": 6,
        "review": 7,
    }.get(match.group("phase"), 99)
    return (iteration, f"{phase_order:02d}-{match.group('phase')}", path.name)


def _collect_receipts(plan_dir: Path) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for path in sorted(plan_dir.glob("step_receipt_*_v*.json"), key=_receipt_sort_key):
        payload = _safe_read_json(path)
        if not isinstance(payload, dict):
            continue
        match = RECEIPT_RE.match(path.name)
        payload = dict(payload)
        payload["_file"] = path.name
        if match:
            payload.setdefault("phase", match.group("phase"))
            payload.setdefault("iteration", int(match.group("iteration")))
        receipts.append(payload)
    return sorted(receipts, key=lambda receipt: (str(receipt.get("timestamp_utc") or ""), _receipt_sort_key(plan_dir / receipt["_file"])))


def _collect_dispatch_receipts(plan_dir: Path) -> list[dict[str, Any]]:
    """Collect current authoritative automatic-dispatch snapshots.

    Only the runtime-resolved model is projected as the report's model.
    Configuration describes a request and remains separate metadata; only the
    started receipt is evidence of the command boundary that actually ran.
    """
    rows: list[dict[str, Any]] = []
    receipt_dir = plan_dir / "dispatch_receipts"
    for path in sorted(receipt_dir.glob("*.json")):
        payload = _safe_read_json(path)
        if not isinstance(payload, dict) or not payload.get("dispatch_id"):
            continue
        resolved_model = payload.get("resolved_runtime_model")
        configured_model = payload.get("configured_model")
        rows.append(
            {
                "dispatch_id": payload.get("dispatch_id"),
                "action": payload.get("action"),
                "model": resolved_model or "",
                "resolved_runtime_model": resolved_model,
                "configured_model": configured_model,
                "subprocess_started": payload.get("subprocess_started") is True,
                "outcome": payload.get("outcome"),
                "mutation_facts": payload.get("mutation_facts") or {},
                "updated_at_utc": payload.get("updated_at_utc"),
            }
        )
    return sorted(rows, key=lambda row: (str(row.get("updated_at_utc") or ""), str(row["dispatch_id"])))


def _artifact_summary(plan_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    interesting = (
        "plan_v*.md",
        "plan_v*.meta.json",
        "critique*.json",
        "gate*.json",
        "faults.json",
        "finalize.json",
        "execution*.json",
        "batch_*.json",
        "review.json",
        "final.md",
        "phase_result.json",
    )
    seen: set[Path] = set()
    for pattern in interesting:
        for path in plan_dir.glob(pattern):
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            rows.append({"name": path.name, "bytes": path.stat().st_size})
    return sorted(rows, key=lambda row: row["name"])


def _duration(seconds_ms: Any) -> str:
    if not isinstance(seconds_ms, int | float):
        return ""
    seconds = float(seconds_ms) / 1000.0
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    rest = int(seconds % 60)
    return f"{minutes}m {rest}s"


def _money(value: Any) -> str:
    if not isinstance(value, int | float):
        return ""
    return f"${float(value):.4f}"


def _tokens(value: Any) -> str:
    if not isinstance(value, int | float):
        return ""
    return f"{int(value):,}"


def _history_index(state: dict[str, Any]) -> dict[tuple[str, Any], dict[str, Any]]:
    index: dict[tuple[str, Any], dict[str, Any]] = {}
    phase_counts: dict[str, int] = defaultdict(int)
    for entry in state.get("history") or []:
        if not isinstance(entry, dict):
            continue
        phase = entry.get("step")
        if not isinstance(phase, str) or not phase:
            continue
        phase_counts[phase] += 1
        iteration = entry.get("iteration") or phase_counts[phase]
        index[(phase, iteration)] = entry
        # Most plans only run one phase per plan iteration. Keep this fallback
        # for legacy receipts that lack an explicit iteration.
        index.setdefault((phase, None), entry)
    return index


def _phase_rows(receipts: list[dict[str, Any]], state: dict[str, Any]) -> list[dict[str, Any]]:
    history = _history_index(state)
    rows: list[dict[str, Any]] = []
    for receipt in receipts:
        phase = receipt.get("phase") or ""
        iteration = receipt.get("iteration")
        history_entry = history.get((str(phase), iteration)) or history.get((str(phase), None)) or {}
        rows.append(
            {
                "phase": phase,
                "iteration": iteration or "",
                "result": receipt.get("result") or receipt.get("verdict") or history_entry.get("result") or "",
                "agent": receipt.get("agent") or "",
                "model": receipt.get("model_actual") or receipt.get("model_configured") or "",
                "duration_ms": receipt.get("duration_ms"),
                "cost_usd": receipt.get("cost_usd"),
                "prompt_tokens": receipt.get("prompt_tokens"),
                "completion_tokens": receipt.get("completion_tokens"),
                "output_file": receipt.get("output_file") or history_entry.get("output_file") or "",
                "file": receipt.get("_file") or "",
                "session_id": receipt.get("session_id") or "",
                "configured_specs": receipt.get("configured_specs") or history_entry.get("configured_specs") or [],
                "attempted_specs": receipt.get("attempted_specs") or history_entry.get("attempted_specs") or [],
                "selected_spec_index": receipt.get("selected_spec_index", history_entry.get("selected_spec_index", 0)),
                "selected_spec_total": receipt.get("selected_spec_total", history_entry.get("selected_spec_total", 0)),
                "fallback_trigger": receipt.get("fallback_trigger") or history_entry.get("fallback_trigger"),
                "failed_attempt_reasons": (
                    receipt.get("failed_attempt_reasons")
                    or history_entry.get("failed_attempt_reasons")
                    or []
                ),
            }
        )
    return rows


def _totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "duration_ms": sum(float(row["duration_ms"]) for row in rows if isinstance(row.get("duration_ms"), int | float)),
        "cost_usd": sum(float(row["cost_usd"]) for row in rows if isinstance(row.get("cost_usd"), int | float)),
        "prompt_tokens": sum(int(row["prompt_tokens"]) for row in rows if isinstance(row.get("prompt_tokens"), int | float)),
        "completion_tokens": sum(
            int(row["completion_tokens"]) for row in rows if isinstance(row.get("completion_tokens"), int | float)
        ),
    }


def _accounting_warnings(rows: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    by_signature: dict[tuple[str, Any, Any, Any], list[str]] = defaultdict(list)
    for row in rows:
        session_id = row.get("session_id")
        if not session_id:
            continue
        signature = (str(session_id), row.get("cost_usd"), row.get("prompt_tokens"), row.get("completion_tokens"))
        by_signature[signature].append(f"{row.get('phase')} v{row.get('iteration')}")
    for (session_id, cost, prompt, completion), phases in sorted(by_signature.items()):
        if len(phases) < 2:
            continue
        warnings.append(
            "identical cost/token totals reused in one persistent session "
            f"({session_id}): {', '.join(phases)} reported cost={_money(cost)}, "
            f"prompt_tokens={_tokens(prompt)}, completion_tokens={_tokens(completion)}"
        )
    return warnings


def _load_gate_summary(plan_dir: Path) -> dict[str, Any] | None:
    gate = _safe_read_json(plan_dir / "gate.json")
    if not isinstance(gate, dict):
        return None
    return {
        "recommendation": gate.get("recommendation"),
        "must_fix_count": len(gate.get("must_fix") or []),
        "should_fix_count": len(gate.get("should_fix") or []),
        "settled_decisions_count": len(gate.get("settled_decisions") or []),
    }


def _load_execution_summary(plan_dir: Path) -> dict[str, Any] | None:
    execution = _safe_read_json(plan_dir / "execution.json")
    finalize = _safe_read_json(plan_dir / "finalize.json")
    if not isinstance(execution, dict) and not isinstance(finalize, dict):
        return None
    tasks = []
    if isinstance(execution, dict) and isinstance(execution.get("tasks"), list):
        tasks = execution["tasks"]
    elif isinstance(finalize, dict) and isinstance(finalize.get("tasks"), list):
        tasks = finalize["tasks"]
    status_counts: dict[str, int] = defaultdict(int)
    for task in tasks:
        if isinstance(task, dict):
            status_counts[str(task.get("status", "unknown"))] += 1
    return {"task_count": len(tasks), "status_counts": dict(sorted(status_counts.items()))}


def _load_phase_result(plan_dir: Path) -> dict[str, Any] | None:
    phase_result = _safe_read_json(plan_dir / "phase_result.json")
    if not isinstance(phase_result, dict):
        return None
    return {
        "phase": phase_result.get("phase"),
        "exit_kind": phase_result.get("exit_kind"),
        "blocked_tasks": phase_result.get("blocked_tasks") or [],
        "deviations": phase_result.get("deviations") or [],
        "artifacts_written": phase_result.get("artifacts_written") or [],
    }


def _build_report_payload(root: Path, plan_name: str | None, compare_name: str | None = None) -> dict[str, Any]:
    plan_dir, state = load_plan(root, plan_name)
    rows = _phase_rows(_collect_receipts(plan_dir), state)
    payload: dict[str, Any] = {
        "plan": state.get("name") or plan_dir.name,
        "plan_dir": str(plan_dir),
        "state": state.get("current_state"),
        "iteration": state.get("iteration"),
        "created_at": state.get("created_at"),
        "profile": (state.get("config") or {}).get("profile"),
        "robustness": (state.get("config") or {}).get("robustness"),
        "mode": (state.get("config") or {}).get("mode"),
        "total_cost_usd_upper_bound": (state.get("meta") or {}).get("total_cost_usd"),
        "active_step": state.get("active_step"),
        "history_count": len(state.get("history") or []),
        "plan_versions": state.get("plan_versions") or [],
        "phase_rows": rows,
        "dispatch_rows": _collect_dispatch_receipts(plan_dir),
        "receipt_totals": _totals(rows),
        "warnings": _accounting_warnings(rows),
        "gate": _load_gate_summary(plan_dir),
        "execution": _load_execution_summary(plan_dir),
        "phase_result": _load_phase_result(plan_dir),
        "artifacts": _artifact_summary(plan_dir),
        "sessions": state.get("sessions") or {},
    }
    if compare_name:
        compare_dir = resolve_plan_dir(root, compare_name)
        # cache-tolerant: report-only comparison view.
        compare_state = _safe_read_json(compare_dir / "state.json") or {}
        compare_rows = _phase_rows(_collect_receipts(compare_dir), compare_state)
        payload["compare"] = {
            "plan": compare_dir.name,
            "plan_dir": str(compare_dir),
            "phase_rows": compare_rows,
            "receipt_totals": _totals(compare_rows),
            "delta": _totals_delta(payload["receipt_totals"], _totals(compare_rows)),
        }
    return payload


def _totals_delta(current: dict[str, Any], prior: dict[str, Any]) -> dict[str, Any]:
    return {
        key: current.get(key, 0) - prior.get(key, 0)
        for key in ("duration_ms", "cost_usd", "prompt_tokens", "completion_tokens")
    }


def _artifact_line(row: dict[str, Any]) -> str:
    return f"- `{row['name']}` ({row['bytes']:,} bytes)"


def render_audit_report_markdown(payload: dict[str, Any]) -> str:
    active = payload.get("active_step") if isinstance(payload.get("active_step"), dict) else None
    active_phase = active.get("phase") or active.get("step") if active else None
    totals = payload["receipt_totals"]
    lines = [
        f"# Megaplan Audit Report: {payload['plan']}",
        "",
        "## Run",
        "",
        f"- State: `{payload.get('state')}`",
        f"- Iteration: `{payload.get('iteration')}`",
        f"- Profile: `{payload.get('profile')}`",
        f"- Robustness: `{payload.get('robustness')}`",
        f"- Mode: `{payload.get('mode')}`",
        f"- Plan directory: `{payload.get('plan_dir')}`",
        f"- Ledger total cost upper bound: {_money(payload.get('total_cost_usd_upper_bound'))}",
        f"- Receipt total cost: {_money(totals.get('cost_usd'))}",
        f"- Receipt prompt tokens: {_tokens(totals.get('prompt_tokens'))}",
        "",
    ]
    if active:
        configured_specs = active.get("configured_specs") or []
        attempted_specs = active.get("attempted_specs") or []
        lines.extend(
            [
                "## Active Step",
                "",
                f"- Step: `{active_phase}`",
                f"- Agent: `{active.get('agent')}`",
                f"- Started: `{active.get('started_at')}`",
                f"- Attempt: `{active.get('attempt')}`",
                f"- Worker PID: `{active.get('worker_pid')}`",
                f"- Last activity: `{active.get('last_activity_at')}` ({active.get('last_activity_kind')})",
                f"- Selected fallback attempt: `{active.get('selected_spec_index', 0) + 1}/{active.get('selected_spec_total', 0)}`",
                f"- Configured specs: `{configured_specs}`",
                f"- Attempted specs: `{attempted_specs}`",
                f"- Fallback trigger: `{active.get('fallback_trigger')}`",
                f"- Failed attempt reasons: `{active.get('failed_attempt_reasons') or []}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Phase Receipts",
            "",
            "| Phase | Iter | Result | Agent | Model | Duration | Cost | Prompt | Completion | Output |",
            "|---|---:|---|---|---|---:|---:|---:|---:|---|",
        ]
    )
    for row in payload["phase_rows"]:
        lines.append(
            f"| {row['phase']} | {row['iteration']} | {row['result']} | {row['agent']} | {row['model']} | "
            f"{_duration(row['duration_ms'])} | {_money(row['cost_usd'])} | {_tokens(row['prompt_tokens'])} | "
            f"{_tokens(row['completion_tokens'])} | `{row['output_file']}` |"
        )
    lines.extend(
        [
            "",
            "## Automatic Dispatch Receipts",
            "",
            "| Action | Dispatch | Runtime Model | Configured Model | Started | Outcome |",
            "|---|---|---|---|---|---|",
        ]
    )
    dispatch_rows = payload.get("dispatch_rows") or []
    if dispatch_rows:
        for row in dispatch_rows:
            lines.append(
                f"| {row['action']} | `{row['dispatch_id']}` | {row['model']} | "
                f"{row['configured_model'] or ''} | {str(row['subprocess_started']).lower()} | {row['outcome']} |"
            )
    else:
        lines.append("| n/a | n/a |  |  | false | no dispatch receipts |")
    lines.extend(["", "## Signals", ""])
    gate = payload.get("gate")
    if isinstance(gate, dict):
        lines.extend(
            [
                f"- Gate recommendation: `{gate.get('recommendation')}`",
                f"- Gate must-fix count: `{gate.get('must_fix_count')}`",
                f"- Gate settled decisions: `{gate.get('settled_decisions_count')}`",
            ]
        )
    execution = payload.get("execution")
    if isinstance(execution, dict):
        lines.append(f"- Execution tasks: `{execution.get('task_count')}` {execution.get('status_counts')}")
    phase_result = payload.get("phase_result")
    if isinstance(phase_result, dict):
        lines.extend(
            [
                f"- Last phase result: `{phase_result.get('phase')}` / `{phase_result.get('exit_kind')}`",
                f"- Phase deviations: `{len(phase_result.get('deviations') or [])}`",
                f"- Blocked tasks: `{len(phase_result.get('blocked_tasks') or [])}`",
            ]
        )
    if not gate and not execution and not phase_result:
        lines.append("- No gate or execution summary artifacts found yet.")
    if payload.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in payload["warnings"])
    if payload.get("compare"):
        compare = payload["compare"]
        delta = compare["delta"]
        lines.extend(
            [
                "",
                "## Comparison",
                "",
                f"- Prior plan: `{compare['plan']}`",
                f"- Cost delta: {_money(delta.get('cost_usd'))}",
                f"- Duration delta: {_duration(delta.get('duration_ms'))}",
                f"- Prompt token delta: {_tokens(delta.get('prompt_tokens'))}",
                f"- Completion token delta: {_tokens(delta.get('completion_tokens'))}",
            ]
        )
    lines.extend(["", "## Artifacts", ""])
    artifacts = payload.get("artifacts") or []
    if artifacts:
        lines.extend(_artifact_line(row) for row in artifacts)
    else:
        lines.append("- No reportable artifacts found.")
    return "\n".join(lines) + "\n"


def handle_audit_report(root: Path, args: Any) -> Any:
    payload = _build_report_payload(root, getattr(args, "plan", None), getattr(args, "compare", None))
    markdown = render_audit_report_markdown(payload)
    output = getattr(args, "output", None)
    json_output = getattr(args, "json_output", None)
    if output:
        atomic_write_text(Path(output).expanduser(), markdown)
    if json_output:
        atomic_write_json(Path(json_output).expanduser(), payload)
    if getattr(args, "format", "markdown") == "json":
        return payload
    if output or json_output:
        result = {
            "success": True,
            "step": "audit_report",
            "plan": payload["plan"],
            "output": str(Path(output).expanduser()) if output else None,
            "json_output": str(Path(json_output).expanduser()) if json_output else None,
        }
        if not output:
            result["markdown"] = markdown
        return result
    return markdown


__all__ = ["handle_audit_report", "render_audit_report_markdown"]
