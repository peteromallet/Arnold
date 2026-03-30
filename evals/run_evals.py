"""Workspace setup and megaplan loop helpers for next-evals experiments."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from .audit import EvalAudit, collect_phase_trace, get_session_message_count
from .config import EvalConfig, capture_environment, load_config
from .scoring import check_build, generate_results_json, run_eval_ts
from utils import atomic_json_write

if TYPE_CHECKING:
    from .benchmarks import VerifyResult


CommandRunner = Callable[[list[str], Path, int | None], subprocess.CompletedProcess[str]]
MegaplanRunner = Callable[[list[str], Path, int | None, dict[str, str]], tuple[dict[str, object], str]]

# When True, subprocess stderr streams live to terminal instead of being captured
_VERBOSE = False


# ---------------------------------------------------------------------------
# Live progress logging
# ---------------------------------------------------------------------------

def _log(eval_name: str, msg: str, *, phase: str | None = None, dim: bool = False) -> None:
    """Print a live progress line to stderr so it's visible even when stdout is piped."""
    prefix = f"[{eval_name}]"
    if phase:
        prefix += f" {phase.upper()}"
    if dim:
        # Grey for less important info
        line = f"\033[90m{prefix} {msg}\033[0m"
    else:
        line = f"{prefix} {msg}"
    print(line, file=sys.stderr, flush=True)


def _phase_summary(response: dict[str, object], phase: str) -> str:
    """Extract a short human-readable summary from a megaplan phase response."""
    summary = response.get("summary")
    if isinstance(summary, str) and summary:
        # Truncate long summaries
        if len(summary) > 120:
            return summary[:117] + "..."
        return summary

    # Fallback: pull key fields per phase type
    if phase == "gate":
        rec = response.get("recommendation", "?")
        return f"recommendation={rec}"
    if phase == "critique":
        flags = response.get("open_flags", [])
        if isinstance(flags, list):
            sig = sum(1 for f in flags if isinstance(f, dict) and f.get("severity") == "significant")
            return f"{len(flags)} flags ({sig} significant)"
    if phase == "plan":
        criteria = response.get("success_criteria", [])
        if isinstance(criteria, list):
            return f"{len(criteria)} success criteria"
    if phase == "review":
        verdict = response.get("review_verdict") or response.get("verdict")
        if verdict:
            return f"verdict={verdict}"

    state = response.get("state", "")
    return f"state={state}" if state else "done"


def _extract_diagnostics(
    trace_messages: list[dict[str, Any]],
    response: dict[str, object],
    phase: str,
) -> list[str]:
    """Extract actionable warnings from trace messages and phase response."""
    issues: list[str] = []

    # Check for tool call errors in trace
    for msg in trace_messages:
        if msg.get("role") != "tool":
            continue
        content = msg.get("content", "")
        if isinstance(content, str):
            content_lower = content.lower()
            # Detect common error patterns
            if any(err in content_lower for err in (
                "error:", "exception:", "traceback", "command failed",
                "permission denied", "not found", "timed out", "enoent",
                "rate limit", "429", "500", "502", "503",
            )):
                # Truncate for display
                snippet = content.strip().split("\n")[0][:120]
                tool_name = msg.get("tool_name") or msg.get("name") or "?"
                issues.append(f"Tool '{tool_name}' error: {snippet}")

    # Check for failed shell commands in trace
    for msg in trace_messages:
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {}) if isinstance(tc.get("function"), dict) else {}
            name = fn.get("name") or tc.get("name") or ""
            if name.lower() not in ("terminal", "shell"):
                continue
            args = fn.get("arguments", "")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except (json.JSONDecodeError, TypeError):
                    args = {}
            if isinstance(args, dict):
                cmd = args.get("command", "")
                if isinstance(cmd, str) and cmd:
                    # Find the corresponding tool result
                    call_id = tc.get("id") or tc.get("call_id")
                    for result_msg in trace_messages:
                        if result_msg.get("role") == "tool" and result_msg.get("tool_call_id") == call_id:
                            result_content = result_msg.get("content", "")
                            if isinstance(result_content, str) and "exit code" in result_content.lower():
                                # Extract exit code
                                import re
                                exit_match = re.search(r'exit.?code[:\s]+(\d+)', result_content, re.IGNORECASE)
                                if exit_match and exit_match.group(1) != "0":
                                    issues.append(f"Shell command failed (exit {exit_match.group(1)}): {cmd[:80]}")

    # Check for empty trace (model didn't do anything)
    if phase == "execute" and not trace_messages:
        issues.append("No trace messages captured — session log may be missing")
    elif phase == "execute":
        tool_calls = sum(1 for m in trace_messages for _ in (m.get("tool_calls") or []))
        if tool_calls == 0:
            issues.append("Execute phase produced no tool calls — model may not have acted on the plan")

    # Check for megaplan-level warnings
    warnings = response.get("warnings")
    if isinstance(warnings, list):
        for w in warnings[:3]:  # Cap at 3
            if isinstance(w, str):
                issues.append(w[:120])

    # Check for critique flags (useful to surface significant ones)
    if phase == "critique":
        flags = response.get("open_flags", [])
        if isinstance(flags, list):
            for flag in flags:
                if isinstance(flag, dict) and flag.get("severity") == "significant":
                    concern = flag.get("concern", "")
                    if isinstance(concern, str):
                        issues.append(f"Flag: {concern[:100]}")

    # Deduplicate
    seen = set()
    unique = []
    for issue in issues:
        if issue not in seen:
            seen.add(issue)
            unique.append(issue)
    return unique[:10]  # Cap total diagnostics


def _trace_tool_summary(trace_messages: list[dict[str, Any]]) -> str:
    """Summarize tool calls from trace messages for display."""
    tool_names: list[str] = []
    for msg in trace_messages:
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {})
            name = fn.get("name") if isinstance(fn, dict) else tc.get("name")
            if isinstance(name, str):
                tool_names.append(name)
    if not tool_names:
        return ""
    # Count and show top tools
    from collections import Counter
    counts = Counter(tool_names)
    parts = [f"{name}×{count}" if count > 1 else name for name, count in counts.most_common(5)]
    remainder = len(tool_names) - sum(c for _, c in counts.most_common(5))
    summary = ", ".join(parts)
    if remainder > 0:
        summary += f", +{remainder} more"
    return f" [tools: {summary}]"


@dataclass(slots=True)
class PreparedWorkspace:
    path: str
    eval_name: str
    initial_commit_sha: str
    metadata: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MegaplanLoopResult:
    plan_name: str
    plan_dir: str
    final_state: str
    gate_recommendation: str | None
    escalated: bool
    phase_order: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _next_evals_backend():
    from .benchmarks.next_evals import NextEvalsBackend

    return NextEvalsBackend()


def _resolve_benchmark(config: EvalConfig):
    """Return the appropriate benchmark backend for the config."""
    from .benchmarks import Benchmark

    name = config.benchmark
    if name == "next-evals":
        from .benchmarks.next_evals import NextEvalsBackend
        return NextEvalsBackend()
    if name == "terminal-bench":
        from .benchmarks.terminal_bench import TerminalBenchBackend
        return TerminalBenchBackend()
    if name == "swe-bench":
        from .benchmarks.swe_bench import SWEBenchBackend
        return SWEBenchBackend()
    raise ValueError(f"Unknown benchmark: {name!r}. Expected 'next-evals', 'terminal-bench', or 'swe-bench'.")


def setup_evals_repo(
    config: EvalConfig,
    *,
    timeout_seconds: int | None = None,
    runner: CommandRunner | None = None,
) -> Path:
    return _next_evals_backend().setup_source(
        config,
        timeout_seconds=timeout_seconds,
        runner=runner,
    )


def prepare_workspace(
    eval_dir: str | Path,
    workspace_dir: str | Path,
    *,
    timeout_seconds: int | None = 600,
    runner: CommandRunner | None = None,
) -> PreparedWorkspace:
    return _next_evals_backend().prepare_workspace(
        eval_dir,
        workspace_dir,
        None,
        timeout_seconds=timeout_seconds,
        runner=runner,
    )


def _phase_transitions(robustness: str) -> dict[str, str | None]:
    """Phase transitions based on robustness level."""
    if robustness == "heavy":
        return {
            "prep": "plan",
            "plan": "critique",
            "critique": "gate",
            "revise": "critique",
            "finalize": "execute",
            "execute": "review",
            "review": None,
        }
    return {
        "plan": "critique",
        "critique": "gate",
        "revise": "critique",
        "finalize": "execute",
        "execute": "review",
        "review": None,
    }

_MAX_PHASE_RETRIES = 3
_MAX_REWORK_CYCLES = 2


def _route_phase_response(
    response: dict[str, object],
    phase: str,
    phase_retries: dict[str, int],
    gate_iterations: int,
    max_gate_iterations: int,
    transitions: dict[str, str | None] | None = None,
) -> tuple[str, str | None]:
    """Decide what to do with a megaplan phase response.

    Returns (action, target):
      ("retry", reason)      — retry same phase
      ("next", phase_name)   — advance to next phase
      ("rework", phase_name) — jump to a different phase (review→execute)
      ("escalate", reason)   — stop the eval
      ("done", None)         — pipeline complete
    """
    success = response.get("success")
    next_step = response.get("next_step")

    # Gate has its own routing via recommendation
    if phase == "gate" and success is not False:
        rec = response.get("recommendation", "")
        if isinstance(rec, str):
            rec = rec.upper()
        if rec == "ITERATE":
            if gate_iterations >= max_gate_iterations:
                return ("next", "finalize")  # Force proceed after max iterations — don't skip the task
            return ("next", "revise")
        if rec == "ESCALATE":
            return ("escalate", "Gate recommended ESCALATE.")
        if rec == "PROCEED":
            return ("next", "finalize")
        return ("escalate", f"Unexpected gate recommendation: {rec}")

    # Success — normal forward transition
    if success is not False:
        next_phase = (transitions or {}).get(phase)
        return ("done", None) if next_phase is None else ("next", next_phase)

    # Failure — check if it's a rework request (review→execute)
    if next_step and next_step != phase:
        rework_key = f"{phase}_rework"
        rework_count = phase_retries.get(rework_key, 0) + 1
        phase_retries[rework_key] = rework_count
        if rework_count > _MAX_REWORK_CYCLES:
            # Max rework cycles — advance normally instead
            next_phase = (transitions or {}).get(phase)
            return ("done", None) if next_phase is None else ("next", next_phase)
        return ("rework", next_step)

    # Failure — retry same phase
    retries = phase_retries.get(phase, 0) + 1
    phase_retries[phase] = retries
    if retries > _MAX_PHASE_RETRIES:
        # Max retries exhausted — escalate rather than advancing to a phase
        # that will fail because the prerequisite state wasn't reached
        reason = response.get("summary", response.get("message", "unknown"))
        return ("escalate", f"Max retries ({_MAX_PHASE_RETRIES}) exhausted for {phase}: {str(reason)[:100]}")
    reason = response.get("summary", response.get("message", "unknown"))
    return ("retry", str(reason)[:120] if reason else "unknown")


def _inject_feedback(
    config: "EvalConfig",
    plan_name: str,
    workspace_path: Path,
    phase: str,
    response: dict[str, object],
) -> None:
    """Inject failure context into the megaplan plan so the next attempt knows what went wrong."""
    parts = [f"[{phase} failed]"]
    for key in ("summary", "message", "error"):
        val = response.get(key)
        if isinstance(val, str) and val:
            parts.append(f"{key}: {val[:200]}")
    for key in ("deviations", "issues"):
        val = response.get(key)
        if isinstance(val, list) and val:
            parts.append(f"{key}: {'; '.join(str(v)[:60] for v in val[:3])}")
    if phase == "execute":
        parts.append(
            "You MUST modify source code files (write_file/patch). "
            "Reading files and writing checkpoints is not enough."
        )
    try:
        _run_megaplan_json(
            _megaplan_command(config, [
                "override", "add-note",
                "--plan", plan_name,
                "--note", "\n".join(parts),
            ]),
            workspace_path, 30, _megaplan_env(),
        )
    except Exception:
        pass


def _inject_verify_feedback(
    config: "EvalConfig",
    plan_name: str,
    workspace_path: Path,
    verify_result: "VerifyResult",
) -> None:
    """Inject verify failure context into the plan before re-running execute."""
    output_tail = verify_result.test_output[-1500:].strip() or "(no verify output captured)"
    tests_display = ", ".join(verify_result.tests_run) if verify_result.tests_run else "(none)"
    diagnosis = _diagnose_verify_failure(verify_result)
    failing_tests_display = ", ".join(diagnosis["failing_tests"]) if diagnosis["failing_tests"] else "(none)"
    parts = [
        "[verify failed]",
        f"target_tests: {tests_display}",
        f"error_type: {diagnosis['error_type']}",
        f"failing_tests: {failing_tests_display}",
        "traceback_summary:",
        diagnosis["traceback_summary"],
        "Diagnose the root cause from the traceback before making changes.",
        "Fix the implementation and do not modify test files.",
        "verify_output_tail:",
        output_tail,
    ]
    try:
        _run_megaplan_json(
            _megaplan_command(config, [
                "override", "add-note",
                "--plan", plan_name,
                "--note", "\n".join(parts),
            ]),
            workspace_path, 30, _megaplan_env(),
        )
    except Exception:
        pass


def _diagnose_verify_failure(verify_result: "VerifyResult") -> dict[str, object]:
    """Extract structured hints from a failed verify run."""
    output = verify_result.test_output or ""
    failing_tests = list(dict.fromkeys(_extract_failing_tests(output, verify_result.tests_run)))
    return {
        "error_type": _categorize_verify_error(output),
        "failing_tests": failing_tests,
        "traceback_summary": _summarize_verify_traceback(output),
    }


def _extract_failing_tests(output: str, tests_run: list[str]) -> list[str]:
    failing_tests = [test_name for test_name in tests_run if isinstance(test_name, str) and test_name.strip()]
    patterns = (
        re.compile(r"^(?:FAILED|ERROR)\s+([^\s]+)"),
        re.compile(r"^_{3,}\s+([^\s]+)\s+_{3,}$"),
    )
    for line in output.splitlines():
        stripped = line.strip()
        for pattern in patterns:
            match = pattern.match(stripped)
            if match:
                failing_tests.append(match.group(1))
                break
    return failing_tests


def _categorize_verify_error(output: str) -> str:
    normalized = output.lower()
    if "timed out" in normalized or "timeout" in normalized:
        return "timeout"
    if "syntaxerror" in normalized or "syntax error" in normalized:
        return "syntax_error"
    if (
        "importerror" in normalized
        or "modulenotfounderror" in normalized
        or "cannot import name" in normalized
    ):
        return "import_error"
    if "attributeerror" in normalized or "has no attribute" in normalized:
        return "attribute_error"
    if "assertionerror" in normalized or re.search(r"^e\s+assert", normalized, flags=re.MULTILINE):
        return "assertion_error"
    return "unknown"


def _summarize_verify_traceback(output: str) -> str:
    lines = [line.rstrip() for line in output.splitlines() if line.strip()]
    if not lines:
        return "(no verify output captured)"

    traceback_start = None
    for index, line in enumerate(lines):
        if line.lstrip().startswith("Traceback"):
            traceback_start = index
    if traceback_start is not None:
        snippet = lines[traceback_start:traceback_start + 5]
        return " | ".join(snippet)[:400]

    interesting = [
        line
        for line in lines
        if any(token in line for token in ("FAILED", "ERROR", "AssertionError", "AttributeError", "ImportError", "SyntaxError", "E   "))
    ]
    if interesting:
        return " | ".join(interesting[-4:])[:400]
    return " | ".join(lines[-4:])[:400]


def run_megaplan_loop(
    prompt: str,
    workspace: str | Path,
    config: EvalConfig,
    audit: EvalAudit,
    *,
    runner: MegaplanRunner | None = None,
    verify_fn: Callable[[], VerifyResult | None] | None = None,
    max_verify_attempts: int = 3,
    log_path: Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> MegaplanLoopResult:
    workspace_path = Path(workspace).expanduser().resolve()
    _active_session_id: list[str | None] = [None]  # mutable container for closure

    if runner is None:
        def _session_resolver() -> str | None:
            return _active_session_id[0]

        def _default_runner(cmd, cwd, timeout, env):
            # For execute/review phases, enable stuck detection (90s no update after last tool call)
            return _run_megaplan_json(
                cmd, cwd, timeout, env,
                log_path=log_path,
                stuck_timeout=90,
                stuck_session_resolver=_session_resolver,
            )
        runner = _default_runner
    plan_name = f"{workspace_path.name}-{int(time.time())}"
    phase_order: list[str] = []
    gate_recommendation: str | None = None

    init_args = [
        "init",
        "--project-dir",
        str(workspace_path),
        "--name",
        plan_name,
        "--auto-approve",
        "--robustness",
        config.robustness,
        "--hermes",
        *config_phase_model_args(config),
        prompt,
    ]
    eval_name = workspace_path.name
    _log(eval_name, f"megaplan init: {plan_name}")
    init_response, init_raw = runner(
        _megaplan_command(config, init_args),
        workspace_path,
        config.eval_timeout_seconds,
        _megaplan_env(extra_env),
    )
    phase_order.append("init")
    plan_dir = workspace_path / ".megaplan" / "plans" / plan_name
    state = _read_state(plan_dir)
    audit.add_phase_result(
        phase="init",
        model="hermes",
        duration_ms=0,
        cost_usd=0.0,
        artifact_name="state.json",
        artifact_payload=state,
        raw_output=init_raw,
        trace_messages=[],
        token_counts={},
    )

    gate_iterations = 0
    phase_retries: dict[str, int] = {}  # per-phase retry counts
    execute_loop_count = 0  # track execute attempts independently (history may not update)
    verify_attempts = 0
    escalated = False
    phase = "prep" if config.robustness == "heavy" else "plan"
    cumulative_cost = 0.0
    while phase is not None:
        if phase == "execute":
            extra_args = ["--confirm-destructive", "--user-approved"]
        else:
            extra_args = []

        model_name = config.models.get(phase, "?")
        iteration = _phase_iteration(_read_state(plan_dir), phase)
        iter_label = f" (iter {iteration})" if iteration > 1 else ""
        _log(eval_name, f"({model_name}) running...{iter_label}", phase=phase)

        phase_start = time.monotonic()
        pre_state = _read_state(plan_dir)
        message_offset = _snapshot_message_offset(pre_state, phase, config.models.get(phase))

        # Tell the stuck detector which session to watch
        _active_session_id[0] = _phase_session_id(pre_state, phase, config.models.get(phase), None)

        phase_timeout = config.eval_timeout_seconds

        try:
            response, raw_output = runner(
                _megaplan_command(
                    config,
                    [
                        phase,
                        "--plan",
                        plan_name,
                        "--hermes",
                        *config_phase_model_args(config),
                        *extra_args,
                    ],
                ),
                workspace_path,
                phase_timeout,
                _megaplan_env(extra_env),
            )
        except _StuckDetected as stuck:
            _log(eval_name, f"Model stuck {stuck.seconds_stuck:.0f}s after {stuck.message_count} msgs — retrying", phase=phase)
            audit.notes.append(f"{phase} stuck: {stuck}")
            # Inject feedback so next attempt knows what happened
            try:
                _run_megaplan_json(
                    _megaplan_command(config, [
                        "override", "add-note",
                        "--plan", plan_name,
                        "--note", (
                            f"[{phase} stuck] Model completed tool calls but final JSON response "
                            f"timed out after {stuck.seconds_stuck:.0f}s. Code changes from tools "
                            "are preserved on disk. On retry: produce the JSON summary quickly."
                        ),
                    ]),
                    workspace_path,
                    30,
                    _megaplan_env(extra_env),
                )
            except Exception:
                pass
            continue
        phase_elapsed = time.monotonic() - phase_start
        phase_order.append(phase)
        state = _read_state(plan_dir)
        history_entry = _latest_history_entry(state, phase)
        session_id = _phase_session_id(state, phase, config.models.get(phase), history_entry)
        trace_messages = collect_phase_trace(session_id, message_offset)
        artifact_name, artifact_payload = _read_phase_artifact(plan_dir, state, phase)
        phase_cost = float(history_entry.get("cost_usd", 0.0) or 0.0)
        cumulative_cost += phase_cost
        audit.add_phase_result(
            phase=phase,
            model=config.models.get(phase, ""),
            duration_ms=int(history_entry.get("duration_ms", 0) or 0),
            cost_usd=phase_cost,
            session_id=session_id,
            message_offset=message_offset,
            iteration=_phase_iteration(state, phase),
            artifact_name=artifact_name,
            artifact_payload=artifact_payload,
            raw_output=raw_output,
            trace_messages=trace_messages,
            token_counts={},
        )

        # Log phase result with summary
        summary_text = _phase_summary(response, phase)
        tool_text = _trace_tool_summary(trace_messages) if phase == "execute" else ""
        cost_text = f" ${phase_cost:.4f}" if phase_cost > 0 else ""
        _log(eval_name, f"{summary_text}{tool_text} ({phase_elapsed:.0f}s{cost_text})", phase=phase)

        # Surface problems from traces so you don't have to dig through files
        diagnostics = _extract_diagnostics(trace_messages, response, phase)
        for diag in diagnostics:
            _log(eval_name, f"  ⚠ {diag}", phase=phase, dim=True)

        # Track gate recommendation for result
        if phase == "gate":
            rec = response.get("recommendation")
            if isinstance(rec, str):
                gate_recommendation = rec

        # Execute phase: if result is "blocked" (incomplete batches), check whether
        # all tasks are actually done. If so, force-proceed past the blocked state.
        # Otherwise re-run for more batches, up to a cap.
        if phase == "execute":
            execute_loop_count += 1
            state_after = _read_state(plan_dir)
            if state_after.get("current_state") == "finalized":
                # Check if all tasks completed despite "blocked" state
                all_done = _all_tasks_done(plan_dir)
                if all_done:
                    verify_result = verify_fn() if verify_fn is not None else None
                    if verify_result is not None:
                        verify_iteration = verify_attempts + 1
                        phase_order.append("verify")
                        audit.add_phase_result(
                            phase="verify",
                            model="swebench-harness",
                            duration_ms=int(verify_result.duration_seconds * 1000),
                            cost_usd=0.0,
                            iteration=verify_iteration,
                            artifact_name=f"verify_v{verify_iteration}.json",
                            artifact_payload=asdict(verify_result),
                            raw_output=verify_result.test_output,
                            trace_messages=[],
                            token_counts={},
                        )
                        if verify_result.passed:
                            _log(eval_name, "Verify passed — proceeding to scoring", phase="verify")
                            break

                        verify_attempts += 1
                        if verify_attempts < max_verify_attempts:
                            _log(
                                eval_name,
                                f"Verify failed ({verify_attempts}/{max_verify_attempts}) — re-running execute",
                                phase="verify",
                            )
                            _inject_verify_feedback(config, plan_name, workspace_path, verify_result)
                            continue

                        _log(
                            eval_name,
                            f"Verify failed after {verify_attempts} attempt(s) — proceeding to scoring",
                            phase="verify",
                        )
                        audit.notes.append(
                            f"verify_failed_after_{verify_attempts}_attempts"
                        )
                        break

                    _log(
                        eval_name,
                        "All tasks done but no verify targets were available — skipping to scoring",
                        phase="execute",
                    )
                    break
                if execute_loop_count >= 12:
                    _log(eval_name, f"Execute loop count {execute_loop_count} — escalating", phase="execute")
                    escalated = True
                    audit.notes.append(f"Execute stuck after {execute_loop_count} attempts")
                    break
                _log(eval_name, f"Execute incomplete (attempt {execute_loop_count}) — continuing...", phase="execute", dim=True)
                continue

        # Route the response — retry, advance, rework, or escalate
        transitions = _phase_transitions(config.robustness)
        action, target = _route_phase_response(
            response, phase, phase_retries, gate_iterations, config.max_gate_iterations,
            transitions=transitions,
        )

        if action == "retry":
            _log(eval_name, f"{target} — re-running ({phase_retries[phase]}/3)", phase=phase)
            _inject_feedback(config, plan_name, workspace_path, phase, response)
            continue

        if action == "rework":
            _log(eval_name, f"Rework requested → {target} ({phase_retries.get('review_rework',0)}/2)", phase=phase)
            _inject_feedback(config, plan_name, workspace_path, phase, response)
            if target == "execute":
                verify_attempts = 0
            phase = target
            continue

        if action == "escalate":
            _log(eval_name, target, phase=phase)
            audit.notes.append(target)
            escalated = True
            break

        if action == "next":
            if target == "revise":
                gate_iterations += 1
                _log(eval_name, f"ITERATE — entering revision cycle {gate_iterations}", phase="gate", dim=True)
            phase = target
            continue

        # action == "done"
        phase = None

    return MegaplanLoopResult(
        plan_name=plan_name,
        plan_dir=str(plan_dir),
        final_state=_as_str(state.get("current_state")) or "",
        gate_recommendation=gate_recommendation,
        escalated=escalated,
        phase_order=phase_order,
    )


def run_all_evals(
    config_path: str | Path,
    eval_names: list[str] | None = None,
    *,
    setup_repo_fn: Callable[[EvalConfig], Path] = setup_evals_repo,
    prepare_workspace_fn: Callable[[str | Path, str | Path], PreparedWorkspace] = prepare_workspace,
    megaplan_loop_fn: Callable[[str, str | Path, EvalConfig, EvalAudit], MegaplanLoopResult] = run_megaplan_loop,
    build_fn: Callable[..., Any] = check_build,
    results_fn: Callable[..., dict[str, Any]] = generate_results_json,
    eval_fn: Callable[..., Any] = run_eval_ts,
    environment_fn: Callable[..., dict[str, Any]] = capture_environment,
) -> dict[str, Any]:
    config = load_config(config_path)
    benchmark = _resolve_benchmark(config)
    print(f"--- Hermes Eval Runner ({config.benchmark}) ---", file=sys.stderr, flush=True)
    print(f"Config: {config_path}", file=sys.stderr, flush=True)
    models_display = ", ".join(f"{k}={v}" for k, v in sorted(config.models.items()))
    print(f"Models: {models_display}", file=sys.stderr, flush=True)

    source_root = Path(benchmark.setup_source(config)).expanduser().resolve()
    environment = benchmark.capture_environment(source_root)
    selected_eval_names = benchmark.list_tasks(source_root, config.evals_to_run, eval_names)
    run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results_root = Path(config.results_dir).expanduser().resolve()
    if config.run_name:
        results_root = results_root / config.run_name
    print(f"Tasks: {len(selected_eval_names)} selected", file=sys.stderr, flush=True)
    print(f"", file=sys.stderr, flush=True)

    # Manifest-driven task iteration or static list
    manifest = None
    if config.manifest_path:
        from evals.manifest import TaskManifest

        manifest = TaskManifest.load(Path(config.manifest_path))

    summary_entries: list[dict[str, Any]] = []
    total_evals = (
        manifest.summary().get("total_tasks", len(selected_eval_names))
        if manifest is not None
        else len(selected_eval_names)
    )
    eval_index = 0

    def _iter_eval_names():
        """Yield task names from the manifest claim loop or the static task list."""
        nonlocal eval_index
        if manifest is not None:
            while batch := manifest.claim_batch(config.worker_id, config.claim_batch_size):
                for name in batch:
                    eval_index += 1
                    yield name
            return

        for name in selected_eval_names:
            eval_index += 1
            yield name

    for eval_name in _iter_eval_names():
      for _task_attempt in range(2):  # retry once on escalation/error
        if _task_attempt > 0:
            _log(eval_name, f"RETRY (attempt {_task_attempt + 1}) — previous attempt {final_status}")

        print(f"{'='*60}", file=sys.stderr, flush=True)
        _log(eval_name, f"Starting ({eval_index}/{total_evals})")

        build_result_dict: dict[str, Any] | None = None
        eval_result_dict: dict[str, Any] | None = None
        test_result_dict: dict[str, Any] | None = None
        results_json: dict[str, Any] | None = None
        notes: list[str] = []
        final_status = "passed"
        conditional = False
        error_text: str | None = None
        prepared = None
        audit = None
        output_dir = results_root

        started = time.monotonic()
        try:
            prepared = benchmark.prepare_workspace(
                eval_name,
                source_root,
                config,
                timeout_seconds=config.eval_timeout_seconds,
            )
            prompt_text = benchmark.read_prompt(eval_name, source_root)
            audit = EvalAudit(
                eval_name=eval_name,
                run_timestamp=run_timestamp,
                results_root=results_root,
                config_snapshot=config.to_dict(),
                environment=environment,
                initial_commit_sha=prepared.initial_commit_sha,
                prompt=prompt_text,
            )
            subprocess_log = audit.output_dir / "logs" / "subprocess.log"
            env_overrides = benchmark.megaplan_env_overrides(prepared)
            verify_fn = None
            if hasattr(benchmark, "verify_after_execute"):
                verify_fn = lambda b=benchmark, p=prepared, c=config: b.verify_after_execute(p, c)
            loop_result = megaplan_loop_fn(
                audit.prompt or "",
                prepared.path,
                config,
                audit,
                verify_fn=verify_fn,
                max_verify_attempts=config.max_verify_attempts,
                log_path=subprocess_log,
                extra_env=env_overrides or None,
            )
            _log(eval_name, f"Megaplan complete: {loop_result.final_state} (phases: {' → '.join(loop_result.phase_order)})")
            notes.append(
                f"megaplan_final_state={loop_result.final_state}; gate={loop_result.gate_recommendation or 'n/a'}"
            )

            if loop_result.escalated:
                final_status = "escalated"
                _log(eval_name, "ESCALATED — skipping scoring")
                notes.append("Megaplan gate escalated; scoring skipped.")
            else:
                _log(eval_name, "Scoring...")
                scoring_result = benchmark.score(
                    prepared,
                    audit,
                    config,
                    build_fn=build_fn,
                    results_fn=results_fn,
                    eval_fn=eval_fn,
                )
                build_result_dict = scoring_result.build_result
                eval_result_dict = scoring_result.eval_result
                test_result_dict = scoring_result.test_result
                results_json = scoring_result.results_json
                audit.build_result = build_result_dict
                audit.eval_result = eval_result_dict
                audit.test_result = test_result_dict
                audit.results_json = results_json
                notes.extend(scoring_result.notes)
                conditional = scoring_result.conditional
                final_status = scoring_result.status

                # Log scoring details
                if build_result_dict is not None:
                    build_success = bool(build_result_dict.get("success"))
                    _log(eval_name, f"Build: {'PASS' if build_success else 'FAIL'} ({build_result_dict.get('duration_seconds', 0):.0f}s)", phase="build")
                if eval_result_dict is not None:
                    reporter = eval_result_dict.get("reporter_json") or {}
                    passed_count = reporter.get("numPassedTests") or reporter.get("passed")
                    total_count = reporter.get("numTotalTests") or reporter.get("total")
                    if passed_count is not None and total_count is not None:
                        _log(eval_name, f"Eval: {passed_count}/{total_count} assertions passed", phase="eval")
                    else:
                        _log(eval_name, f"Eval: {'PASS' if eval_result_dict.get('success') else 'FAIL'}", phase="eval")
                if test_result_dict is not None:
                    _log(eval_name, f"Test: {'PASS' if test_result_dict.get('success') else 'FAIL'} ({test_result_dict.get('duration_seconds', 0):.0f}s)", phase="test")
        except Exception as exc:
            error_text = str(exc)
            final_status = "error"
            _log(eval_name, f"ERROR: {error_text[:200]}")
            notes.append(error_text)
            if results_json is None and audit is not None and prepared is not None:
                results_json = results_fn(
                    _combined_trace_messages(audit),
                    prepared.path,
                    initial_commit_sha=prepared.initial_commit_sha,
                    status="error",
                    duration_seconds=_duration_seconds(audit),
                    model=config.models.get("execute", ""),
                    error=error_text,
                    transcript_path=_audit_relative_path(audit, "traces/execute_v1.json"),
                    transcript_raw_path=_audit_relative_path(audit, "raw/execute_v1.txt"),
                    build_output_path=_audit_relative_path(audit, "scoring/build.json"),
                    eval_output_path=_audit_relative_path(audit, "scoring/eval.json"),
                )
                audit.results_json = results_json
        finally:
            if audit is not None and prepared is not None:
                audit.notes.extend(notes)
                audit.git_diff = _git_diff_patch(Path(prepared.path), prepared.initial_commit_sha)
                output_dir = audit.save_audit()
                _log(eval_name, f"Audit saved to {output_dir}", dim=True)
                # Clean up workspace to save disk
                try:
                    benchmark.cleanup_workspace(prepared)
                except Exception:
                    pass

        elapsed = time.monotonic() - started
        cost = _cost_usd(audit) if audit is not None else 0.0
        entry = {
            "eval_name": eval_name,
            "status": final_status,
            "conditional_pass": conditional,
            "build_pass": _build_pass(build_result_dict),
            "eval_score": _eval_score(eval_result_dict),
            "test_passed": _test_pass(test_result_dict),
            "cost_usd": cost,
            "duration_seconds": elapsed,
            "audit_dir": str(output_dir),
            "error": error_text,
        }
        summary_entries.append(entry)

        # Bold result line
        if conditional:
            status_icon = "✓*"
        else:
            status_icon = {"passed": "✓", "failed": "✗", "error": "!", "escalated": "⊘"}.get(final_status, "?")
        _log(eval_name, f"{status_icon} {final_status.upper()} | build={'pass' if entry['build_pass'] else 'fail' if entry['build_pass'] is not None else 'n/a'} | cost=${cost:.4f} | {elapsed:.0f}s")
        print("", file=sys.stderr, flush=True)

        # Retry on escalation/error (first attempt only)
        if final_status in ("escalated", "error") and _task_attempt == 0:
            _log(eval_name, f"Will retry — {final_status}", dim=True)
            continue  # retry loop
        break  # success or final attempt — exit retry loop

      # After retry loop — mark task in manifest
      if manifest:
          if final_status == "error":
              manifest.mark_error(eval_name, config.worker_id, error_text or "unknown")
          else:
              manifest.mark_done(eval_name, config.worker_id)

    # Final summary
    print(f"{'='*60}", file=sys.stderr, flush=True)
    passed = sum(1 for e in summary_entries if e["status"] == "passed")
    failed = sum(1 for e in summary_entries if e["status"] == "failed")
    errors = sum(1 for e in summary_entries if e["status"] == "error")
    escalated = sum(1 for e in summary_entries if e["status"] == "escalated")
    total_cost = sum(e["cost_usd"] for e in summary_entries)
    total_time = sum(e["duration_seconds"] for e in summary_entries)
    print(f"Results: {passed} passed, {failed} failed, {errors} errors, {escalated} escalated", file=sys.stderr, flush=True)
    print(f"Total cost: ${total_cost:.4f} | Total time: {total_time:.0f}s", file=sys.stderr, flush=True)

    summary = {
        "run_timestamp": run_timestamp,
        "config_path": str(Path(config_path).expanduser().resolve()),
        "results_root": str(results_root),
        "environment": environment,
        "evals": summary_entries,
    }
    summary_path = results_root / f"summary_{run_timestamp}.json"
    atomic_json_write(summary_path, summary, default=str)
    print(f"Summary: {summary_path}", file=sys.stderr, flush=True)
    summary["summary_path"] = str(summary_path)
    return summary


def _checkout_repo_ref(
    repo_path: Path,
    ref: str,
    runner: CommandRunner,
    timeout_seconds: int | None,
) -> None:
    if not (repo_path / ".git").exists():
        return
    runner(["git", "checkout", ref], repo_path, timeout_seconds)


def _run_sync_evals(
    repo_path: Path,
    runner: CommandRunner,
    timeout_seconds: int | None,
) -> None:
    if not (repo_path / "package.json").exists():
        return
    runner(["npm", "run", "sync-evals"], repo_path, timeout_seconds)


def _git_stdout(
    command: list[str],
    cwd: Path,
    timeout_seconds: int | None,
    runner: CommandRunner,
) -> str:
    completed = runner(command, cwd, timeout_seconds)
    return completed.stdout.strip()


def _run_command(
    command: list[str],
    cwd: Path,
    timeout_seconds: int | None,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Command not found: {' '.join(command)}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Command timed out after {timeout_seconds}s: {' '.join(command)}\n"
            f"{(exc.stdout or '')}{(exc.stderr or '')}"
        ) from exc

    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed ({completed.returncode}): {' '.join(command)}\n"
            f"{completed.stdout}{completed.stderr}"
        )
    return completed


class _StuckDetected(Exception):
    """Raised when the session log indicates the model is stuck waiting for an API response."""
    def __init__(self, session_id: str, last_updated: str, seconds_stuck: float, message_count: int):
        self.session_id = session_id
        self.last_updated = last_updated
        self.seconds_stuck = seconds_stuck
        self.message_count = message_count
        super().__init__(
            f"Model stuck for {seconds_stuck:.0f}s (session {session_id}, "
            f"{message_count} msgs, last_updated {last_updated})"
        )


def _run_megaplan_json(
    command: list[str],
    cwd: Path,
    timeout_seconds: int | None,
    env: dict[str, str],
    log_path: Path | None = None,
    stuck_timeout: int | None = None,
    stuck_session_resolver: Callable[[], str | None] | None = None,
) -> tuple[dict[str, object], str]:
    """Run a megaplan command and parse JSON output.

    If stuck_timeout and stuck_session_resolver are provided, polls the
    Hermes session log every 10s.  When the session's last_updated hasn't
    changed for stuck_timeout seconds AND the last message is a tool result
    (meaning the model is waiting for an API response), raises _StuckDetected
    so the caller can retry.
    """
    proc = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )

    deadline = time.monotonic() + timeout_seconds if timeout_seconds else None
    last_session_check = time.monotonic()
    last_session_mtime: float | None = None

    try:
        while True:
            try:
                stdout, stderr = proc.communicate(timeout=10)
                break  # Process finished
            except subprocess.TimeoutExpired:
                # Process still running — check for stuck state
                elapsed = time.monotonic() - (deadline - timeout_seconds) if deadline else 0

                if _VERBOSE and int(elapsed) % 30 == 0 and elapsed > 5:
                    print(f"    | ... waiting ({elapsed:.0f}s)", file=sys.stderr, flush=True)

                # Check overall timeout
                if deadline and time.monotonic() > deadline:
                    proc.kill()
                    proc.wait()
                    raise subprocess.TimeoutExpired(command, timeout_seconds)

                # Check session log for stuck model
                if stuck_timeout and stuck_session_resolver and time.monotonic() - last_session_check > 10:
                    last_session_check = time.monotonic()
                    _check = _check_session_stuck(
                        stuck_session_resolver, stuck_timeout, last_session_mtime,
                    )
                    if _check is not None:
                        proc.kill()
                        proc.wait()
                        raise _check
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"Command timed out after {timeout_seconds}s: {' '.join(command)}"
        )

    returncode = proc.returncode
    stderr_text = stderr or ""

    # Save stderr to log file (always — this is the audit trail)
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"CMD: {' '.join(command)}\n")
            f.write(f"CWD: {cwd}\n")
            f.write(f"EXIT: {returncode}\n")
            f.write(f"{'='*60}\n")
            if stderr_text:
                f.write(stderr_text)
                if not stderr_text.endswith("\n"):
                    f.write("\n")

    # In verbose mode, also stream stderr to terminal
    if _VERBOSE and stderr_text.strip():
        for line in stderr_text.splitlines():
            print(f"    | {line}", file=sys.stderr, flush=True)

    raw_output = stdout or stderr_text
    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Megaplan returned non-JSON output for {' '.join(command)}:\n"
            f"stdout: {stdout[:500] if stdout else '(empty)'}\n"
            f"stderr: {stderr_text[:500]}"
        ) from exc
    if returncode != 0 or payload.get("success") is False:
        # Always return the payload — let the caller decide whether to
        # retry, rework, or error. Never raise on parseable JSON responses.
        return payload, raw_output
    return payload, raw_output


def _check_session_stuck(
    session_resolver: Callable[[], str | None],
    stuck_timeout: int,
    prev_mtime: float | None,
) -> _StuckDetected | None:
    """Check if the Hermes session log indicates a stuck model.

    Returns _StuckDetected if the session log hasn't been updated for
    stuck_timeout seconds AND the last message is a tool result (meaning
    the model finished tool calls but the API response hasn't arrived).
    """
    session_id = session_resolver()
    if not session_id:
        return None

    hermes_home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    log_path = hermes_home / "sessions" / f"session_{session_id}.json"
    if not log_path.exists():
        # Session log doesn't exist yet — model hasn't started.
        # If this persists for 2x stuck_timeout, something is wrong.
        return None  # Can't determine stuck without a session log

    try:
        mtime = log_path.stat().st_mtime
        seconds_since_update = time.time() - mtime
        if seconds_since_update < stuck_timeout:
            return None

        payload = json.loads(log_path.read_text(encoding="utf-8"))
        messages = payload.get("messages", [])
        if not messages:
            return None

        last_msg = messages[-1]
        last_role = last_msg.get("role", "")
        # Stuck if:
        # 1. Last message is a tool result (model finished tools, waiting for final response)
        # 2. OR session hasn't been updated in 2x stuck_timeout (model never even started)
        if last_role == "tool" or seconds_since_update > stuck_timeout * 2:
            return _StuckDetected(
                session_id=session_id,
                last_updated=payload.get("last_updated", "?"),
                seconds_stuck=seconds_since_update,
                message_count=len(messages),
            )
    except Exception:
        pass
    return None


def _megaplan_command(config: EvalConfig, args: list[str]) -> list[str]:
    base = shlex.split(config.megaplan_bin)
    return base + args


def _megaplan_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    python_paths = [
        str(Path(__file__).resolve().parent.parent),
        str(Path(__file__).resolve().parent.parent.parent / "megaplan"),
    ]
    existing = env.get("PYTHONPATH")
    if existing:
        python_paths.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(python_paths)
    if extra:
        env.update(extra)
    return env


def config_phase_model_args(config: EvalConfig) -> list[str]:
    args: list[str] = []
    for phase in ("prep", "plan", "research", "critique", "revise", "gate", "finalize", "execute", "review"):
        model = config.models.get(phase)
        if model:
            args.extend(["--phase-model", f"{phase}=hermes:{model}"])
    return args


def _read_state(plan_dir: Path) -> dict[str, object]:
    state_path = plan_dir / "state.json"
    if not state_path.exists():
        return {}
    return json.loads(state_path.read_text(encoding="utf-8"))


def _all_tasks_done(plan_dir: Path) -> bool:
    """Check if all tasks from finalize.json are completed across batch files."""
    finalize_path = plan_dir / "finalize.json"
    if not finalize_path.exists():
        return False
    try:
        data = json.loads(finalize_path.read_text(encoding="utf-8"))
        all_task_ids = {t["id"] for t in data.get("tasks", [])}
        if not all_task_ids:
            return False

        # Collect completed task IDs from all batch files
        done_ids: set[str] = set()
        for batch_file in sorted(plan_dir.glob("execution_batch_*.json")):
            batch = json.loads(batch_file.read_text(encoding="utf-8"))
            for update in batch.get("task_updates", []):
                if update.get("status") in ("done", "skipped"):
                    done_ids.add(update.get("task_id", ""))

        # Also check aggregate execution.json
        exec_path = plan_dir / "execution.json"
        if exec_path.exists():
            exec_data = json.loads(exec_path.read_text(encoding="utf-8"))
            for update in exec_data.get("task_updates", []):
                if update.get("status") in ("done", "skipped"):
                    done_ids.add(update.get("task_id", ""))

        return all_task_ids <= done_ids
    except (json.JSONDecodeError, OSError):
        return False


def _snapshot_message_offset(
    state: dict[str, object],
    phase: str,
    model: str | None,
) -> int:
    session_id = _phase_session_id(state, phase, model, None)
    return get_session_message_count(session_id)


def _phase_session_id(
    state: dict[str, object],
    phase: str,
    model: str | None,
    history_entry: dict[str, object] | None,
) -> str | None:
    sessions = state.get("sessions", {})
    if isinstance(sessions, dict):
        entry = sessions.get(_session_key_for(phase, "hermes", model))
        if isinstance(entry, dict):
            session_id = entry.get("id")
            if isinstance(session_id, str) and session_id:
                return session_id
    if history_entry:
        session_id = history_entry.get("session_id")
        if isinstance(session_id, str) and session_id:
            return session_id
    return None


def _session_key_for(step: str, agent: str, model: str | None = None) -> str:
    if step in {"plan", "revise"}:
        key = f"{agent}_planner"
    elif step == "critique":
        key = f"{agent}_critic"
    elif step == "gate":
        key = f"{agent}_gatekeeper"
    elif step == "finalize":
        key = f"{agent}_finalizer"
    elif step == "execute":
        key = f"{agent}_executor"
    elif step == "review":
        key = f"{agent}_reviewer"
    else:
        key = f"{agent}_{step}"
    if model:
        import hashlib

        key += f"_{hashlib.sha256(model.encode()).hexdigest()[:8]}"
    return key


def _latest_history_entry(state: dict[str, object], phase: str) -> dict[str, object]:
    history = state.get("history", [])
    if not isinstance(history, list):
        return {}
    for entry in reversed(history):
        if isinstance(entry, dict) and entry.get("step") == phase:
            return entry
    return {}


def _phase_iteration(state: dict[str, object], phase: str) -> int:
    iteration = int(state.get("iteration", 0) or 0)
    if phase in {"init", "finalize", "execute", "review"}:
        return max(iteration, 1)
    return max(iteration, 1)


def _read_phase_artifact(
    plan_dir: Path,
    state: dict[str, object],
    phase: str,
) -> tuple[str | None, object | None]:
    iteration = _phase_iteration(state, phase)
    if phase == "init":
        path = plan_dir / "state.json"
        return "state.json", _read_json_file(path)
    if phase == "plan":
        plan_file = plan_dir / f"plan_v{iteration}.md"
        meta_file = plan_dir / f"plan_v{iteration}.meta.json"
        return (
            f"plan_v{iteration}.json",
            {
                "plan_file": plan_file.name,
                "plan": plan_file.read_text(encoding="utf-8") if plan_file.exists() else "",
                "meta_file": meta_file.name,
                "meta": _read_json_file(meta_file),
            },
        )
    if phase == "critique":
        filename = f"critique_v{iteration}.json"
        return filename, _read_json_file(plan_dir / filename)
    if phase == "revise":
        plan_file = plan_dir / f"plan_v{iteration}.md"
        meta_file = plan_dir / f"plan_v{iteration}.meta.json"
        return (
            f"revise_v{iteration}.json",
            {
                "plan_file": plan_file.name,
                "plan": plan_file.read_text(encoding="utf-8") if plan_file.exists() else "",
                "meta_file": meta_file.name,
                "meta": _read_json_file(meta_file),
            },
        )
    if phase == "gate":
        signals_file = plan_dir / f"gate_signals_v{iteration}.json"
        return (
            f"gate_v{iteration}.json",
            {
                "gate": _read_json_file(plan_dir / "gate.json"),
                "signals_file": signals_file.name,
                "signals": _read_json_file(signals_file),
            },
        )
    if phase == "finalize":
        return "finalize.json", _read_json_file(plan_dir / "finalize.json")
    if phase == "execute":
        return "execution.json", _read_json_file(plan_dir / "execution.json")
    if phase == "review":
        return "review.json", _read_json_file(plan_dir / "review.json")
    return None, None


def _read_json_file(path: Path) -> object | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _as_str(value: object | None) -> str | None:
    return value if isinstance(value, str) else None


def _resolve_eval_names(
    repo_path: Path,
    configured: list[str],
    cli_selected: list[str] | None,
) -> list[str]:
    return _next_evals_backend().list_tasks(repo_path, configured, cli_selected)


def _read_prompt(eval_dir: Path) -> str:
    return _next_evals_backend().read_prompt(eval_dir)


def _combined_trace_messages(audit: EvalAudit) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for record in audit.phase_records:
        messages.extend(record.trace_messages)
    return messages


def _duration_seconds(audit: EvalAudit) -> float:
    total_ms = sum(record.duration_ms for record in audit.phase_records)
    return total_ms / 1000.0


def _cost_usd(audit: EvalAudit) -> float:
    return round(sum(record.cost_usd for record in audit.phase_records), 6)


def _audit_relative_path(audit: EvalAudit, relative: str) -> str:
    return str(audit.output_dir / relative)


def _to_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return value
    raise TypeError(f"Unsupported result payload type: {type(value)!r}")


def _build_pass(build_result: dict[str, Any] | None) -> bool | None:
    if build_result is None:
        return None
    return bool(build_result.get("success"))


def _eval_score(eval_result: dict[str, Any] | None) -> dict[str, Any] | None:
    if eval_result is None:
        return None
    reporter = eval_result.get("reporter_json") or {}
    passed = _coerce_int(
        reporter.get("numPassedTests")
        or reporter.get("passed")
        or reporter.get("passedTests")
    )
    total = _coerce_int(
        reporter.get("numTotalTests")
        or reporter.get("total")
        or reporter.get("totalTests")
    )
    fraction = None
    if passed is not None and total:
        fraction = passed / total
    return {
        "success": bool(eval_result.get("success")),
        "passed": passed,
        "total": total,
        "fraction": fraction,
    }


def _test_pass(test_result: dict[str, Any] | None) -> bool | None:
    if test_result is None:
        return None
    return bool(test_result.get("success"))


def _coerce_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _summary_line(entry: dict[str, Any]) -> str:
    build_display = entry["build_pass"]
    eval_score = entry["eval_score"] or {}
    if eval_score.get("passed") is not None and eval_score.get("total") is not None:
        eval_display = f"{eval_score['passed']}/{eval_score['total']}"
    elif eval_score:
        eval_display = "pass" if eval_score.get("success") else "fail"
    else:
        eval_display = "n/a"
    return (
        f"{entry['eval_name']}: status={entry['status']} "
        f"build={build_display} eval={eval_display} "
        f"cost=${entry['cost_usd']:.4f} duration={entry['duration_seconds']:.2f}s"
    )


def _git_diff_patch(workspace: Path, initial_commit_sha: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "diff", initial_commit_sha, "--"],
            cwd=workspace,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return ""
    return completed.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Hermes megaplan evaluations against configured benchmarks.")
    parser.add_argument("--config", help="Path to the eval config JSON file.")
    parser.add_argument(
        "--eval",
        dest="evals",
        action="append",
        default=[],
        help="Limit the run to one eval name. Repeatable.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Stream all subprocess stderr live (Hermes logs, npm output, megaplan internals).",
    )
    parser.add_argument(
        "--setup-only",
        action="store_true",
        help="Only resolve the benchmark source and print its path.",
    )
    parser.add_argument(
        "--prepare-eval",
        help="Prepare a single task and print the workspace metadata as JSON.",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear previous workspace and results before running.",
    )
    parser.add_argument(
        "--run-name",
        default="",
        help="Nest results under this subdirectory for multi-run comparison.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of parallel workers for SWE-bench (patch generation only, batch scoring after).",
    )
    parser.add_argument(
        "--scoring-mode",
        choices=["batch", "watch"],
        default="batch",
        help="Scoring mode for parallel SWE-bench runs.",
    )
    parser.add_argument(
        "--join",
        help="Attach additional workers to an existing SWE-bench parallel run by run_name.",
    )
    parser.add_argument(
        "--add-workers",
        type=int,
        default=5,
        help="Number of workers to add when using --join.",
    )
    args = parser.parse_args(argv)

    global _VERBOSE
    _VERBOSE = args.verbose

    if not args.config and not args.join:
        parser.error("--config is required unless --join is used")

    config = load_config(args.config) if args.config else None
    if args.join:
        from evals.parallel import join_parallel_run

        summary = join_parallel_run(args.config, args.join, args.add_workers)
        print(json.dumps(summary, indent=2))
        return 0

    assert config is not None
    if args.run_name:
        config.run_name = args.run_name
    if args.workers > 1:
        config.workers = args.workers

    if args.clear:
        import shutil
        for d in [config.workspace_dir, config.results_dir]:
            p = Path(d).expanduser().resolve()
            if p.exists():
                shutil.rmtree(p)
                print(f"Cleared {p}", file=sys.stderr, flush=True)
    benchmark = _resolve_benchmark(config)
    source_root = benchmark.setup_source(config)
    if args.setup_only and not args.prepare_eval:
        print(source_root)
        return 0

    if args.prepare_eval:
        prepared = benchmark.prepare_workspace(
            args.prepare_eval,
            source_root,
            config,
            timeout_seconds=config.eval_timeout_seconds,
        )
        print(json.dumps(prepared.to_dict(), indent=2))
        return 0

    if getattr(config, 'workers', 1) > 1 and config.benchmark == "swe-bench":
        from evals.parallel import run_parallel_workers
        summary = run_parallel_workers(
            args.config,
            args.evals or None,
            config.workers,
            scoring_mode=args.scoring_mode,
        )
    else:
        summary = run_all_evals(args.config, args.evals or None)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
