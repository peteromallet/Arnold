#!/usr/bin/env python3
"""In-process fan-out of N hermes/AIAgent subagents.

Resource-efficient companion to ``launch_hermes_agent.py``: the latter is a
subprocess per call (~150MB RSS each, full megaplan import tree N times). This
script imports megaplan / hermes ONCE at module load and shares a single
``SessionDB`` across a ``ThreadPoolExecutor`` of AIAgent instances. The GIL is
released during HTTPS I/O so the threads truly overlap the network-bound work.

Math (observed locally): N=5 → ~250MB peak in one process vs ~750MB across 5
subprocesses; N=50 → ~400MB vs ~7.5GB.

Kill-switch layers (see SKILL.md for full design notes):
    1. ``--task-timeout=SECONDS``        per-task deadline (default 600)
    2. SIGINT (Ctrl-C)                   graceful, double-tap = hard exit
    3. SIGTERM + pidfile                 graceful kill from another shell
    4. ``--isolation=processes``         opt-in per-task SIGKILL surface

Usage:
    PYENV_VERSION=3.11.11 python fan.py \\
        --briefs-dir=/tmp/briefs --output-dir=/tmp/results \\
        --max-workers=5 --model="deepseek:deepseek-v4-pro" \\
        --toolsets="file,web" --max-tokens=65536 --task-timeout=1800

    # Positional briefs:
    python fan.py /tmp/b1.md /tmp/b2.md --output-dir=/tmp/results

    # Per-brief model overrides (glob → model):
    python fan.py --briefs-dir=/tmp/briefs --output-dir=/tmp/out \\
        --model-map="flash:scan-*.md,pro:verdict-*.md"

    # Process isolation (per-task SIGKILL surface; see SKILL.md):
    python fan.py --briefs-dir=/tmp/briefs --output-dir=/tmp/out \\
        --isolation=processes --max-workers=4

Output layout:
    <output-dir>/<brief-stem>.txt        — final agent response
    <output-dir>/<brief-stem>.meta.json  — timestamps, elapsed, tool count, status
    <output-dir>/<brief-stem>.pid        — child PID (processes mode only)
    <output-dir>/_fan.pid                — parent PID (lifetime of the fan)
    <output-dir>/_report.json            — aggregate (per-task summaries + totals)

Exit code: 0 iff every task succeeded; 1 if any failed; 130 on SIGINT; 143 on
SIGTERM. stdout = aggregate progress / summary. stderr = per-agent activity,
each line prefixed with the brief name so concurrent streams don't garble.
"""

from __future__ import annotations

import concurrent.futures
import errno
import fnmatch
import json
import multiprocessing
import os
import signal
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional
from urllib.parse import unquote, urlparse

# Ensure this module is reachable as ``fan`` even when invoked directly
# (``python fan.py`` → ``__main__``).  fan_process.py does lazy ``import fan``
# and must resolve to this module, not a second copy.
if __name__ != "fan":
    sys.modules.setdefault("fan", sys.modules[__name__])

from fan_process import _ProcTask, _ProcessTaskRunner


# ---------------------------------------------------------------------------
# Module-level imports of megaplan / hermes. This is THE point of fan.py: every
# worker shares this import work instead of re-doing it N times. Each worker
# call below uses the names imported here; do not move these into run_one().
# ---------------------------------------------------------------------------


def _eprint(*args, **kwargs) -> None:
    kwargs.setdefault("file", sys.stderr)
    print(*args, **kwargs)
    sys.stderr.flush()


def _load_hermes_env() -> None:
    """Replicate the minimal .env loader from launch_hermes_agent.py."""
    env_path = Path.home() / ".hermes" / ".env"
    if not env_path.exists():
        return
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip().strip("'").strip('"')
    except OSError as exc:
        _eprint(f"[fan] warning: could not read {env_path}: {exc}")


def _check_codex_network_sandbox() -> None:
    """Fail fast if launched from inside a `codex exec` sandbox without network.

    `codex exec --sandbox read-only|workspace-write` sets
    `CODEX_SANDBOX_NETWORK_DISABLED=1` and blocks outbound sockets. Hermes
    agents need to reach provider APIs, so running from those modes always
    fails later with cryptic DNS/socket errors. The fix is to launch from a
    normal shell, or to run the Codex subagent with
    `--sandbox danger-full-access`.
    """
    disabled = os.environ.get("CODEX_SANDBOX_NETWORK_DISABLED")
    if disabled:
        _eprint(
            "[fan] FATAL: running inside a `codex exec` sandbox with network "
            f"disabled (CODEX_SANDBOX_NETWORK_DISABLED={disabled}). "
            "Hermes agents cannot reach provider APIs.\n"
            "\n"
            "Fix one of:\n"
            "  1. Launch this fan directly from a normal shell, or\n"
            "  2. Run the parent Codex subagent with "
            "`--sandbox danger-full-access`.\n"
            "\n"
            "See the subagent-launcher SKILL.md for details."
        )
        sys.exit(1)


def _prefer_legacy_megaplan_distribution() -> None:
    """Put the legacy ``megaplan`` checkout before Arnold guard paths."""

    try:
        from importlib.metadata import distribution

        dist = distribution("megaplan")
        direct_url = dist.read_text("direct_url.json")
        if not direct_url:
            return
        url = json.loads(direct_url).get("url", "")
        parsed = urlparse(url)
        if parsed.scheme != "file":
            return
        root = Path(unquote(parsed.path))
        if not (root / "megaplan" / "agent" / "__init__.py").exists():
            return
        root_str = str(root)
        sys.path[:] = [p for p in sys.path if p != root_str]
        sys.path.insert(0, root_str)
    except Exception as exc:
        if "No package metadata was found for megaplan" in str(exc):
            return
        _eprint(f"[fan] warning: could not prefer legacy megaplan distribution: {exc}")


def _add_fallback_megaplan_paths() -> None:
    """If the editable ``megaplan`` distribution isn't installed, add known source roots.

    Codex and other clean shells often don't have the editable install metadata,
    but the source checkout still exists on disk. This fallback lets the launcher
    work without a manual ``PYTHONPATH``.
    """
    try:
        import megaplan.agent  # noqa: F401 — probe only
        return
    except ModuleNotFoundError:
        pass

    candidates = []
    for env_name in ("MEGPLAN_PATH", "MEGPLAN_ENGINE", "ARNOLD_PATH"):
        env_path = os.environ.get(env_name)
        if env_path:
            candidates.append(Path(env_path))

    home = Path.home()
    cwd = Path.cwd()
    candidates.extend(
        [
            home / "Documents" / "megaplan",
            home / "Documents" / "megaplan-engine",
            home / "Documents" / "megaplan-engine-main",
            home / "Documents" / "Arnold",
            home / "src" / "megaplan",
            home / "megaplan",
            home / "workspace" / "megaplan",
            cwd.parent / "megaplan",
            cwd.parent / "megaplan-engine",
            cwd.parent / "megaplan-engine-main",
            cwd.parent / "Arnold",
        ]
    )

    for root in candidates:
        if not root.exists():
            continue
        if (
            (root / "megaplan" / "agent" / "__init__.py").exists()
            or (root / "arnold" / "pipelines" / "megaplan" / "agent" / "__init__.py").exists()
            or (root / "arnold" / "agent" / "run_agent.py").exists()
        ):
            root_str = str(root)
            if root_str not in sys.path:
                sys.path.insert(0, root_str)
            return


_load_hermes_env()
_prefer_legacy_megaplan_distribution()
_add_fallback_megaplan_paths()
_check_codex_network_sandbox()
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

# Heavy imports — happen exactly once per process.
try:
    try:
        import megaplan.agent  # noqa: F401 — sets up hermes sys.path
        from run_agent import AIAgent
        from hermes_state import SessionDB
        from megaplan.runtime.key_pool import resolve_model
    except ModuleNotFoundError as legacy_exc:
        if legacy_exc.name not in {"megaplan", "run_agent", "hermes_state"}:
            raise
        try:
            from arnold.agent.run_agent import AIAgent
            from arnold.agent.hermes_state import SessionDB
            from arnold_pipelines.megaplan.runtime.key_pool import resolve_model
        except ModuleNotFoundError as current_exc:
            if current_exc.name not in {"arnold", "arnold.agent", "arnold.agent.run_agent", "arnold.agent.hermes_state"}:
                raise
            vendored_agent = Path.cwd() / "arnold" / "pipelines" / "megaplan" / "agent"
            if vendored_agent.exists():
                vendored_agent_str = str(vendored_agent)
                if vendored_agent_str not in sys.path:
                    sys.path.insert(0, vendored_agent_str)
            from arnold.agent.run_agent import AIAgent
            from arnold.agent.hermes_state import SessionDB
            from arnold_pipelines.megaplan.runtime.key_pool import resolve_model
except Exception:
    _eprint("[fan] FATAL: could not import megaplan/hermes runtime:")
    _eprint(traceback.format_exc())
    sys.exit(3)


def _no_op_stream(_text: str) -> None:
    """Sentinel callback forcing AIAgent's streaming path on deepseek/fireworks
    when ``max_tokens > 4096``. Same pattern as launch_hermes_agent.py."""
    return None


_no_op_stream._megaplan_force_stream = True  # type: ignore[attr-defined]


_MODEL_SHORTCUTS = {
    "pro": "deepseek:deepseek-v4-pro",
    "flash": "deepseek:deepseek-v4-flash",
    "fast": "mimo:mimo-v2.5-pro-ultraspeed",
    "mimo": "mimo:mimo-v2.5-pro-ultraspeed",
    "mimo-fast": "mimo:mimo-v2.5-pro-ultraspeed",
    "kimi": "fireworks:accounts/fireworks/models/kimi-k2p5",
    "kimi26": "fireworks:accounts/fireworks/models/kimi-k2p6",
    "glm": "zhipu:glm-4.6",
}

_HIGH_TOKEN_STREAM_PROVIDERS = ("fireworks:", "deepseek:", "mimo:")
_HIGH_TOKEN_STREAM_MAX_TOKENS = 4096


def _resolve_model_shortcut(model: str) -> str:
    return _MODEL_SHORTCUTS.get(str(model).strip(), model)


def _requires_streaming(model: str, max_tokens: int) -> bool:
    if not model.startswith(_HIGH_TOKEN_STREAM_PROVIDERS):
        return False
    return max_tokens > _HIGH_TOKEN_STREAM_MAX_TOKENS


# Shared SessionDB — SQLite WAL is multi-thread-safe within one process. One
# instance for all workers; constructing N would waste memory and disk handles.
# In processes mode, each forked child re-inits this to its own connection.
_SHARED_SESSION_DB: Optional[Any] = None
_SESSION_DB_LOCK = threading.Lock()


def _get_session_db() -> Any:
    global _SHARED_SESSION_DB
    if _SHARED_SESSION_DB is None:
        with _SESSION_DB_LOCK:
            if _SHARED_SESSION_DB is None:
                _SHARED_SESSION_DB = SessionDB()
    return _SHARED_SESSION_DB


# Resolved-model cache: resolve_model() pokes env / config, so cache per
# (model_string) so 50 tasks don't redo the same lookup.
_RESOLVE_CACHE: dict[str, tuple[str, dict]] = {}
_RESOLVE_LOCK = threading.Lock()


def _resolve_cached(model: str) -> tuple[str, dict]:
    with _RESOLVE_LOCK:
        if model not in _RESOLVE_CACHE:
            _RESOLVE_CACHE[model] = resolve_model(model)
        # Return a shallow copy of kwargs so callers can mutate freely.
        resolved, kwargs = _RESOLVE_CACHE[model]
        return resolved, dict(kwargs)


# stderr line prefixing — concurrent agents would otherwise interleave.
_STDERR_LOCK = threading.Lock()


def _tagged_eprint(tag: str, msg: str) -> None:
    with _STDERR_LOCK:
        for line in str(msg).splitlines() or [""]:
            print(f"[{tag}] {line}", file=sys.stderr)
        sys.stderr.flush()


# ---------------------------------------------------------------------------
# Parent-side kill state (only meaningful in the main process)
# ---------------------------------------------------------------------------

# Module-global rather than closure-local so the signal handler can flip it
# from the main thread while the executor loop is in `as_completed`.
_STOP_EVENT = threading.Event()
_SIGINT_TIMES: list[float] = []
_SIGINT_DOUBLE_WINDOW_S = 2.0


def _install_signal_handlers(output_dir: Path) -> None:
    """Register SIGINT/SIGTERM handlers on the main thread.

    First signal: graceful (set stop event, cancel pending futures).
    Second SIGINT within ``_SIGINT_DOUBLE_WINDOW_S``: ``os._exit(130)``.
    SIGTERM: behaves like first SIGINT but exits 143 on clean drain.
    """

    def _sigint_handler(signum, frame):  # noqa: ARG001
        now = time.monotonic()
        _SIGINT_TIMES.append(now)
        recent = [t for t in _SIGINT_TIMES if now - t <= _SIGINT_DOUBLE_WINDOW_S]
        if len(recent) >= 2:
            _eprint("[fan] SIGINT (2nd) — hard exit")
            # Best-effort pidfile cleanup; ignore errors.
            try:
                pidfile = output_dir / "_fan.pid"
                if pidfile.exists():
                    pidfile.unlink()
            except OSError:
                pass
            os._exit(130)
        _STOP_EVENT.set()
        _eprint("[fan] SIGINT received — cancelling pending, draining in-flight...")

    def _sigterm_handler(signum, frame):  # noqa: ARG001
        _STOP_EVENT.set()
        _eprint("[fan] SIGTERM received — cancelling pending, draining in-flight...")

    # signal.signal must be called from the main thread; we always are here.
    signal.signal(signal.SIGINT, _sigint_handler)
    signal.signal(signal.SIGTERM, _sigterm_handler)


def _write_pidfile(output_dir: Path) -> Path:
    """Write parent PID; if a live PID is already there, error out."""
    pidfile = output_dir / "_fan.pid"
    if pidfile.exists():
        try:
            existing = int(pidfile.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            existing = None
        if existing and _pid_alive(existing):
            raise SystemExit(
                f"error: another fan.py is running at PID {existing}; "
                f"--output-dir conflict ({output_dir})"
            )
        # Stale → remove and continue.
        _eprint(f"[fan] stale pidfile (PID {existing} not alive) — removing")
        try:
            pidfile.unlink()
        except OSError:
            pass
    pidfile.write_text(str(os.getpid()), encoding="utf-8")
    return pidfile


def _pid_alive(pid: int) -> bool:
    """POSIX 'is this PID alive' check via signal 0."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # PID exists, owned by another user — counts as alive for our purposes.
        return True
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return False
        return True
    return True


# ---------------------------------------------------------------------------
# Per-task work
# ---------------------------------------------------------------------------


@dataclass
class TaskResult:
    brief: str            # absolute path to the brief
    stem: str             # filename stem (used for output filenames)
    model: str            # model string actually used (after model_map)
    status: str           # "ok" | "error" | "timeout" | "cancelled" | "interrupted" | "killed"
    elapsed_s: float
    started_at: str
    finished_at: str
    error: Optional[str] = None
    error_class: Optional[str] = None
    finish_reason: Optional[str] = None
    tool_calls: int = 0
    response_chars: int = 0
    response_file: Optional[str] = None
    meta_file: Optional[str] = None
    raw_result_keys: list[str] = field(default_factory=list)
    task_timeout_s: Optional[float] = None
    pid: Optional[int] = None  # populated in processes mode


def _extract_tool_call_count(result: Any) -> int:
    """Best-effort tool-call counter — AIAgent's result shape varies a bit."""
    if not isinstance(result, dict):
        return 0
    # Common shapes seen in megaplan/hermes results:
    for key in ("tool_calls", "tool_call_count", "num_tool_calls"):
        v = result.get(key)
        if isinstance(v, int):
            return v
        if isinstance(v, list):
            return len(v)
    history = result.get("messages") or result.get("history") or []
    if isinstance(history, list):
        count = 0
        for m in history:
            if isinstance(m, dict):
                tcs = m.get("tool_calls")
                if isinstance(tcs, list):
                    count += len(tcs)
                elif m.get("role") == "tool":
                    count += 1
        if count:
            return count
    return 0


def _install_task_timeout(agent: Any, task_timeout: float) -> None:
    """Force AIAgent's OpenAI client to honor ``task_timeout`` (seconds).

    AIAgent's ``__init__`` does not accept a ``timeout`` kwarg directly; it
    constructs the ``OpenAI`` client from ``self._client_kwargs`` and also
    spawns per-request clients from the same kwargs (see
    ``_create_request_openai_client``). We mutate the stored kwargs *and*
    replace the primary client so both the shared and per-request paths get
    the new deadline. The OpenAI SDK raises ``openai.APITimeoutError`` (a
    subclass of ``APIConnectionError``) when the read deadline elapses.

    Caveat: streaming chunked responses count each chunk against the read
    timeout, not the total stream wall clock. If the model emits steady
    output but never finishes, the SDK timeout alone won't fire. That's why
    the caller ALSO wraps the agent call in a watchdog wait (see
    ``_run_one``).
    """
    try:
        if not hasattr(agent, "_client_kwargs") or agent._client_kwargs is None:
            return
        agent._client_kwargs["timeout"] = task_timeout
        if hasattr(agent, "_replace_primary_openai_client"):
            agent._replace_primary_openai_client(reason="fan_task_timeout")
        elif getattr(agent, "client", None) is not None:
            # Older code path — fall back to ``with_options`` mutation.
            try:
                agent.client = agent.client.with_options(timeout=task_timeout)
            except Exception:
                pass
    except Exception as exc:  # noqa: BLE001 — best-effort; document below
        _tagged_eprint(
            "fan",
            f"warning: could not install task_timeout={task_timeout}s on agent: {exc}",
        )


def _run_one(
    brief_path: Path,
    output_dir: Path,
    model: str,
    toolset_list: list[str],
    max_tokens: int,
    session_id: Optional[str],
    task_timeout: float = 600.0,
) -> TaskResult:
    """Worker — one AIAgent run, one brief in, one (.txt + .meta.json) out."""
    stem = brief_path.stem
    tag = stem[:40]
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    start = time.monotonic()

    result_obj = TaskResult(
        brief=str(brief_path),
        stem=stem,
        model=model,
        status="error",
        elapsed_s=0.0,
        started_at=started_at,
        finished_at=started_at,
        task_timeout_s=task_timeout,
        pid=os.getpid(),
    )

    response_path = output_dir / f"{stem}.txt"
    meta_path = output_dir / f"{stem}.meta.json"
    result_obj.response_file = str(response_path)
    result_obj.meta_file = str(meta_path)

    def _finalize(write_response: Optional[str] = None) -> None:
        result_obj.elapsed_s = time.monotonic() - start
        result_obj.finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        try:
            if write_response is not None:
                response_path.write_text(write_response, encoding="utf-8")
                result_obj.response_chars = len(write_response)
            meta_path.write_text(
                json.dumps(asdict(result_obj), indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except OSError as exc:
            _tagged_eprint(tag, f"warning: could not write outputs: {exc}")

    try:
        if not brief_path.exists():
            raise FileNotFoundError(f"brief not found: {brief_path}")
        query = brief_path.read_text(encoding="utf-8")
        if not query.strip():
            raise ValueError("brief is empty")

        resolved_model, agent_kwargs = _resolve_cached(model)
        if ":" in model and not agent_kwargs.get("api_key"):
            raise RuntimeError(
                f"no API key resolved for provider prefix in {model!r}; "
                "check ~/.hermes/.env"
            )

        _tagged_eprint(
            tag,
            f"start model={model} → {resolved_model} toolsets={toolset_list or '(none)'} "
            f"max_tokens={max_tokens} task_timeout={task_timeout}s",
        )

        agent = AIAgent(
            model=resolved_model,
            # Preserve an explicit empty capability set; None enables defaults.
            enabled_toolsets=toolset_list,
            session_id=session_id,
            session_db=_get_session_db(),
            max_tokens=max_tokens,
            skip_context_files=True,
            skip_memory=True,
            quiet_mode=True,
            **agent_kwargs,
        )
        # Inject our task-level timeout into the OpenAI client.
        _install_task_timeout(agent, task_timeout)

        # Route agent prints to a tagged stderr writer so logs stay sortable.
        agent._print_fn = lambda *a, **kw: _tagged_eprint(  # noqa: E731
            tag, " ".join(str(x) for x in a)
        )

        run_kwargs: dict = {}
        if _requires_streaming(model, max_tokens):
            run_kwargs["stream_callback"] = _no_op_stream

        # Watchdog wait — belt-and-braces around the SDK timeout. We run the
        # agent on a single-thread executor so we can wait with a deadline.
        # If the deadline fires we return a TimeoutError; the underlying
        # thread keeps draining its current API call (it can't be cancelled
        # mid-recv) but the future is detached — the fan keeps moving.
        watchdog_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix=f"agent-{tag}"
        )
        try:
            agent_future = watchdog_pool.submit(
                agent.run_conversation, user_message=query, **run_kwargs
            )
            try:
                result = agent_future.result(timeout=task_timeout)
            except concurrent.futures.TimeoutError:
                # Mark cancelled (no-op if running) and detach.
                agent_future.cancel()
                raise TimeoutError(
                    f"task exceeded --task-timeout={task_timeout}s "
                    f"(SDK and watchdog both armed)"
                )
        finally:
            # Don't wait for the leaked agent_future on timeout — shutdown
            # with wait=False so the fan can keep moving.
            watchdog_pool.shutdown(wait=False)

        if isinstance(result, dict):
            result_obj.raw_result_keys = sorted(result.keys())
            result_obj.finish_reason = result.get("finish_reason")
            result_obj.tool_calls = _extract_tool_call_count(result)
            final = result.get("final_response")
        else:
            final = None

        if not final:
            raise RuntimeError(
                f"agent returned no final_response (finish_reason="
                f"{result_obj.finish_reason!r})"
            )

        result_obj.status = "ok"
        _tagged_eprint(
            tag,
            f"ok elapsed={time.monotonic() - start:.1f}s "
            f"chars={len(final)} tools={result_obj.tool_calls}",
        )
        _finalize(write_response=final)
        return result_obj

    except KeyboardInterrupt:
        result_obj.status = "interrupted"
        result_obj.error = "KeyboardInterrupt"
        result_obj.error_class = "KeyboardInterrupt"
        _tagged_eprint(tag, "interrupted")
        _finalize()
        raise
    except TimeoutError as exc:
        result_obj.status = "timeout"
        result_obj.error = f"{exc}"
        result_obj.error_class = "TimeoutError"
        _tagged_eprint(tag, f"TIMEOUT after {time.monotonic() - start:.1f}s")
        _finalize()
        return result_obj
    except BaseException as exc:  # broad on purpose — one bad task != fan death
        # Detect SDK-level APITimeoutError and classify it as timeout too.
        cls_name = type(exc).__name__
        if cls_name == "APITimeoutError":
            result_obj.status = "timeout"
        else:
            result_obj.status = "error"
        result_obj.error = f"{exc}"
        result_obj.error_class = cls_name
        _tagged_eprint(tag, f"FAIL ({cls_name}): {exc}")
        # Stash traceback for debugging — surfaced via meta file only.
        try:
            (output_dir / f"{stem}.error.txt").write_text(
                traceback.format_exc(), encoding="utf-8"
            )
        except OSError:
            pass
        _finalize()
        return result_obj



# ---------------------------------------------------------------------------
# Top-level / CLI
# ---------------------------------------------------------------------------


def _parse_model_map(spec: Optional[str]) -> list[tuple[str, str]]:
    """Parse a `--model-map='alias:glob,alias:glob'` spec.

    Aliases are resolved against well-known shortcuts; anything containing a
    colon is treated as a literal model string. Returns ordered (model, glob)
    pairs — first match wins.
    """
    if not spec:
        return []
    out: list[tuple[str, str]] = []
    # Format: alias_or_model:glob[,alias_or_model:glob ...]
    # Model strings may themselves contain ':' (e.g. fireworks:accounts/...),
    # but we treat the FIRST ':' as the alias/glob separator only when the LHS
    # is a known shortcut; otherwise we look for the LAST ':' (so a literal
    # model with a colon can still be paired with a glob).
    for clause in str(spec).split(","):
        clause = clause.strip()
        if not clause:
            continue
        if ":" not in clause:
            raise ValueError(f"bad --model-map clause (missing ':'): {clause!r}")
        head, _, tail = clause.partition(":")
        if head in _MODEL_SHORTCUTS:
            out.append((_MODEL_SHORTCUTS[head], tail.strip()))
        else:
            # Treat the LAST ':' as the separator so literal model strings work.
            model_part, _, glob_part = clause.rpartition(":")
            out.append((model_part.strip(), glob_part.strip()))
    return out


def _pick_model(brief: Path, default_model: str, model_map: list[tuple[str, str]]) -> str:
    name = brief.name
    for model, glob in model_map:
        if glob and fnmatch.fnmatch(name, glob):
            return _resolve_model_shortcut(model)
    return _resolve_model_shortcut(default_model)


def _collect_briefs(
    positional: tuple[str, ...],
    briefs_dir: Optional[str],
) -> list[Path]:
    if positional and briefs_dir:
        raise SystemExit("error: pass positional briefs OR --briefs-dir, not both")
    if positional:
        return [Path(p).expanduser().resolve() for p in positional]
    if not briefs_dir:
        raise SystemExit(
            "error: provide briefs via positional args or --briefs-dir=DIR"
        )
    root = Path(briefs_dir).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"error: --briefs-dir is not a directory: {root}")
    briefs = sorted(p for p in root.iterdir() if p.is_file() and p.suffix == ".md")
    if not briefs:
        raise SystemExit(f"error: no *.md briefs found in {root}")
    return briefs


def _stub_task_result(
    bp: Path,
    model: str,
    *,
    status: str,
    error: str,
    error_class: str,
    task_timeout: float,
) -> TaskResult:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return TaskResult(
        brief=str(bp),
        stem=bp.stem,
        model=model,
        status=status,
        elapsed_s=0.0,
        started_at=now,
        finished_at=now,
        error=error,
        error_class=error_class,
        task_timeout_s=task_timeout,
    )


def run(
    *briefs: str,
    briefs_dir: Optional[str] = None,
    output_dir: str = "./fan_out",
    max_workers: int = 5,
    model: str = "deepseek:deepseek-v4-pro",
    model_map: Optional[str] = None,
    toolsets: str = "file,web",
    max_tokens: int = 65536,
    project_dir: Optional[str] = None,
    session_id: Optional[str] = None,
    task_timeout: float = 1800.0,
    isolation: str = "threads",
) -> None:
    """Fan out N hermes/AIAgent calls in one process.

    Args:
        briefs: Positional brief paths (mutually exclusive with --briefs-dir).
        briefs_dir: Directory of `*.md` briefs. Sorted alphabetically.
        output_dir: Per-brief `.txt` / `.meta.json` and aggregate `_report.json`
            land here. Created if missing.
        max_workers: ThreadPoolExecutor / ProcessPoolExecutor width.
        model: Default model spec (megaplan key-pool prefix convention).
        model_map: Optional `"alias_or_model:glob,..."` mapping. Aliases:
            fast/mimo/mimo-fast/pro/flash/kimi/kimi26/glm. First glob match
            wins; falls back to `--model`. `fast`/`mimo`/`mimo-fast` route to
            `mimo:mimo-v2.5-pro-ultraspeed`.
        toolsets: Comma-separated subset of {file, web, terminal}. `""` for
            pure chat.
        max_tokens: Per-agent response cap (forces streaming for
            deepseek:/fireworks:/mimo: when >4096).
        project_dir: chdir before launching (affects relative file reads).
        session_id: Reuse a prior hermes session id (all workers share it —
            usually leave None so each gets a fresh one).
        task_timeout: Per-task wall-clock deadline (seconds). Installed on
            each agent's OpenAI client and enforced by a watchdog wait.
            Default 1800 (30 min) — forensic briefs routinely exceed 10 min.
        isolation: ``"threads"`` (default) or ``"processes"``. Process mode
            uses ``multiprocessing.get_context(\"fork\")`` so children inherit the parent's
            megaplan import tree; each child writes a ``<stem>.pid`` file so
            external operators can ``kill -9`` an individual task.
    """
    overall_start = time.monotonic()

    if isolation not in ("threads", "processes"):
        raise SystemExit(
            f"error: --isolation must be 'threads' or 'processes', got {isolation!r}"
        )

    if project_dir:
        target = Path(project_dir).expanduser().resolve()
        if not target.is_dir():
            raise SystemExit(f"error: --project-dir is not a directory: {target}")
        os.chdir(target)

    brief_paths = _collect_briefs(briefs, briefs_dir)
    out_root = Path(output_dir).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    if isinstance(toolsets, (tuple, list)):
        toolset_list = [str(t).strip() for t in toolsets if str(t).strip()]
    else:
        toolset_list = [t.strip() for t in str(toolsets).split(",") if t.strip()]

    parsed_map = _parse_model_map(model_map)

    # Pidfile + signal handlers FIRST so an early failure leaves nothing behind
    # and a Ctrl-C during preheat is captured. signal.signal() must run on the
    # main thread; we're guaranteed to be there.
    pidfile_path = _write_pidfile(out_root)
    _install_signal_handlers(out_root)

    _eprint(
        f"[fan] briefs={len(brief_paths)} max_workers={max_workers} "
        f"default_model={model} toolsets={toolset_list or '(none)'} "
        f"max_tokens={max_tokens} task_timeout={task_timeout}s "
        f"isolation={isolation} output_dir={out_root} pid={os.getpid()}"
    )
    if parsed_map:
        _eprint(f"[fan] model_map={parsed_map}")
    if "terminal" in toolset_list:
        _eprint(
            "[fan] WARNING: 'terminal' toolset is enabled; the megaplan sandbox "
            "is NOT installed here — shell runs with the caller's privileges."
        )

    # Preheat per-model resolution so the first batch of workers doesn't race
    # on construction. We deliberately do NOT preheat the shared ``SessionDB``
    # in processes mode — a SQLite WAL handle inherited across ``fork()`` and
    # used concurrently by sibling children triggers SIGABRT from SQLite's
    # consistency checks. In threads mode the parent's SessionDB is shared
    # safely; in processes mode each child constructs its own on first use.
    if isolation != "processes":
        _get_session_db()
    used_models = {model} | {m for m, _ in parsed_map}
    for m in used_models:
        _resolve_cached(m)

    results: list[TaskResult] = []
    exit_code = 0

    # AIAgent's KawaiiSpinner thread captures sys.stdout at construction and
    # writes spinner glyphs to it. We can't intercept that through _print_fn,
    # so swap process-wide for the fan's duration. All workers spawn while the
    # swap is in effect; we restore in finally before printing the summary.
    real_stdout = sys.stdout
    sys.stdout = sys.stderr

    try:
        if isolation == "processes":
            # fork context: children inherit the parent's already-imported
            # megaplan tree. Deprecated as macOS default in 3.14+ but still
            # works in 3.11 and the import-sharing win is the whole point.
            #
            # macOS Obj-C fork-safety: any process that has loaded an Obj-C
            # framework (most Python on macOS via openssl/CoreFoundation) will
            # SIGABRT in forked children unless this env var is set. We set
            # it before constructing the fork context.
            os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")
            ctx = multiprocessing.get_context("fork")
            process_runner = _ProcessTaskRunner(max_workers=max_workers, mp_context=ctx)

            # Submit all tasks (they'll be started as the runner has slack).
            for bp in brief_paths:
                if _STOP_EVENT.is_set():
                    results.append(
                        _stub_task_result(
                            bp,
                            _pick_model(bp, model, parsed_map),
                            status="cancelled",
                            error="not started (stop event set before submit)",
                            error_class="Cancelled",
                            task_timeout=task_timeout,
                        )
                    )
                    continue
                chosen = _pick_model(bp, model, parsed_map)
                process_runner.submit(
                    task_args=(
                        str(bp),
                        str(out_root),
                        chosen,
                        toolset_list,
                        max_tokens,
                        session_id,
                        task_timeout,
                    ),
                    brief=bp,
                    chosen_model=chosen,
                )

            # Main-thread drive loop. All Process.start() and poll() calls
            # happen here, which is required for macOS Obj-C fork safety
            # (no other Python threads are running in the parent).
            signal_at: Optional[float] = None
            grace_s = 10.0
            try:
                while process_runner.has_work():
                    if _STOP_EVENT.is_set():
                        if signal_at is None:
                            signal_at = time.monotonic()
                        cancelled = process_runner.cancel_pending()
                        for t in cancelled:
                            results.append(
                                _stub_task_result(
                                    t.brief,
                                    t.chosen_model,
                                    status="cancelled",
                                    error="cancelled by signal before start",
                                    error_class="Cancelled",
                                    task_timeout=task_timeout,
                                )
                            )
                        process_runner.terminate_all(signal.SIGTERM)
                        if time.monotonic() - signal_at > grace_s:
                            _eprint(
                                f"[fan] grace expired after {grace_s}s — hard-killing "
                                f"{len(process_runner._running)} in-flight child(ren)"
                            )
                            process_runner.shutdown(hard=True)
                            break
                    newly = process_runner.poll()
                    for t in newly:
                        try:
                            results.append(TaskResult(**t.result))
                        except (TypeError, ValueError):
                            # Defensive — should not happen given _harvest_done.
                            results.append(
                                _stub_task_result(
                                    t.brief,
                                    t.chosen_model,
                                    status="error",
                                    error="malformed result dict",
                                    error_class="MalformedResult",
                                    task_timeout=task_timeout,
                                )
                            )
                    # Sleep briefly so we don't spin; signal handler still ticks.
                    time.sleep(0.1)
            finally:
                process_runner.shutdown(hard=_STOP_EVENT.is_set())
                # After shutdown, any tasks moved to completed via harvest:
                for t in process_runner._completed:
                    if not any(r.stem == t.brief.stem for r in results):
                        try:
                            results.append(TaskResult(**t.result))
                        except (TypeError, ValueError):
                            pass
        else:
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
            try:
                futures: dict = {}
                for bp in brief_paths:
                    if _STOP_EVENT.is_set():
                        results.append(
                            _stub_task_result(
                                bp,
                                _pick_model(bp, model, parsed_map),
                                status="cancelled",
                                error="not started (stop event set before submit)",
                                error_class="Cancelled",
                                task_timeout=task_timeout,
                            )
                        )
                        continue
                    chosen = _pick_model(bp, model, parsed_map)
                    fut = executor.submit(
                        _run_one,
                        bp,
                        out_root,
                        chosen,
                        toolset_list,
                        max_tokens,
                        session_id,
                        task_timeout,
                    )
                    futures[fut] = (bp, chosen)

                # When _STOP_EVENT fires, give in-flight tasks a brief grace
                # window to wrap up; then abandon them. Threads can't be killed
                # mid-recv, so "abandon" means: stop waiting on the future,
                # mark it interrupted, exit. The thread itself keeps running
                # until its HTTPS call returns.
                signal_at: Optional[float] = None
                grace_s = 10.0

                while futures:
                    if _STOP_EVENT.is_set():
                        if signal_at is None:
                            signal_at = time.monotonic()
                        pending = [f for f in futures if not f.running() and not f.done()]
                        for f in pending:
                            if f.cancel():
                                bp, chosen = futures[f]
                                results.append(
                                    _stub_task_result(
                                        bp,
                                        chosen,
                                        status="cancelled",
                                        error="cancelled by signal before start",
                                        error_class="Cancelled",
                                        task_timeout=task_timeout,
                                    )
                                )
                                futures.pop(f, None)
                        if time.monotonic() - signal_at > grace_s:
                            _eprint(
                                f"[fan] grace expired after {grace_s}s — "
                                f"abandoning {len(futures)} in-flight task(s) as interrupted"
                            )
                            for f, (bp, chosen) in list(futures.items()):
                                results.append(
                                    _stub_task_result(
                                        bp,
                                        chosen,
                                        status="interrupted",
                                        error=(
                                            "in-flight at signal; abandoned after grace "
                                            "(thread may continue draining its HTTPS call)"
                                        ),
                                        error_class="Interrupted",
                                        task_timeout=task_timeout,
                                    )
                                )
                                futures.pop(f, None)
                            break

                    done, _ = concurrent.futures.wait(
                        list(futures.keys()),
                        timeout=0.5,
                        return_when=concurrent.futures.FIRST_COMPLETED,
                    )
                    for fut in done:
                        bp, chosen = futures.pop(fut)
                        try:
                            r = fut.result()
                            results.append(r)
                        except (concurrent.futures.CancelledError, KeyboardInterrupt) as exc:
                            results.append(
                                _stub_task_result(
                                    bp,
                                    chosen,
                                    status="interrupted",
                                    error=f"{exc}",
                                    error_class=type(exc).__name__,
                                    task_timeout=task_timeout,
                                )
                            )
                        except BaseException as exc:  # noqa: BLE001
                            results.append(
                                _stub_task_result(
                                    bp,
                                    chosen,
                                    status="error",
                                    error=f"executor: {exc}",
                                    error_class=type(exc).__name__,
                                    task_timeout=task_timeout,
                                )
                            )
            finally:
                stopped = _STOP_EVENT.is_set()
                try:
                    executor.shutdown(wait=not stopped, cancel_futures=True)
                except TypeError:
                    executor.shutdown(wait=not stopped)
    finally:
        sys.stdout = real_stdout
        # Always remove the pidfile on the way out; signal-handler hard exit
        # already does this, so a missing file here is fine.
        try:
            if pidfile_path.exists():
                pidfile_path.unlink()
        except OSError:
            pass

    if _STOP_EVENT.is_set():
        # Pick the right exit code: 130 if it was SIGINT, 143 if SIGTERM. We
        # don't track which signal fired separately, but SIGINT is the common
        # case from a terminal and SIGTERM is the explicit kill — the helper
        # ``fan_kill.py`` uses SIGTERM, so use 143 if no SIGINT was logged.
        exit_code = 130 if _SIGINT_TIMES else 143

    results.sort(key=lambda r: r.stem)
    elapsed_total = time.monotonic() - overall_start
    succeeded = [r for r in results if r.status == "ok"]
    failed = [r for r in results if r.status != "ok"]

    report = {
        "briefs_dir": briefs_dir,
        "output_dir": str(out_root),
        "default_model": model,
        "model_map": parsed_map,
        "max_workers": max_workers,
        "toolsets": toolset_list,
        "max_tokens": max_tokens,
        "task_timeout_s": task_timeout,
        "isolation": isolation,
        "project_dir": project_dir,
        "total_count": len(results),
        "succeeded_count": len(succeeded),
        "failed_count": len(failed),
        "stopped_by_signal": _STOP_EVENT.is_set(),
        "wall_clock_s": round(elapsed_total, 3),
        "sum_agent_seconds": round(sum(r.elapsed_s for r in results), 3),
        "tasks": [asdict(r) for r in results],
    }
    report_path = out_root / "_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    print(
        f"fan: {len(succeeded)}/{len(results)} ok, {len(failed)} failed "
        f"in {elapsed_total:.1f}s (sum_agent={report['sum_agent_seconds']}s) "
        f"→ {report_path}"
    )
    for r in failed:
        print(f"  {r.status.upper()} {r.stem}: [{r.error_class}] {r.error}")

    if exit_code:
        # Signal-driven exit: worker threads (in threads mode) may still be
        # blocked in HTTPS recv and would keep the interpreter alive forever
        # since they're non-daemon. ``os._exit`` skips finalizers and exits
        # immediately — the report file already wrote above, so nothing
        # important is lost.
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(exit_code)
    if failed:
        sys.exit(1)


def main() -> None:
    _check_codex_network_sandbox()
    try:
        import fire
    except ImportError:
        _eprint("error: this script requires `fire`. Install with `pip install fire`.")
        sys.exit(1)
    fire.Fire(run)


if __name__ == "__main__":
    main()
