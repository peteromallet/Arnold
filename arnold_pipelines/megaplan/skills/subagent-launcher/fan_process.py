"""macOS-fork-safety-aware per-task process runner for fan.py.

This module contains the ``--isolation=processes`` subsystem extracted from
``fan.py``.  It replaces ``concurrent.futures.ProcessPoolExecutor`` in order
to avoid the ``BrokenProcessPool`` cascade: when any child dies abruptly the
standard pool poisons *all* pending and running futures.  This runner spawns
one ``multiprocessing.Process`` per task and tracks them independently — a
SIGKILL on one task only affects that task.

The ``fork`` multiprocessing context is used so children inherit the parent's
already-imported megaplan tree (the entire point of fan.py's in-process design).
The caller must drive the runner from the main thread because macOS Obj-C
fork-safety checks SIGABRT children forked from background threads.
"""

from __future__ import annotations

import os
import signal
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

__all__ = ["_ProcTask", "_ProcessTaskRunner"]


@dataclass
class _ProcTask:
    """A scheduled / running process task. Mutated as the task transitions."""

    task_args: tuple
    brief: Path
    chosen_model: str
    # Filled when the task starts:
    proc: Any = None
    queue: Any = None
    started_at_mono: float = 0.0
    deadline: float = 0.0
    # Filled when done:
    result: Optional[dict] = None
    done: bool = False


def _process_worker_with_queue(
    result_queue: Any,
    brief_path_str: str,
    output_dir_str: str,
    model: str,
    toolset_list: list[str],
    max_tokens: int,
    session_id: Optional[str],
    task_timeout: float,
) -> None:
    """Top-level callable for ``multiprocessing.Process`` in isolation=processes mode.

    Each task runs in its own forked child.  The child inherits the parent's
    already-imported megaplan tree (the entire point of using ``fork`` context
    on macOS — pickled spawn would lose this).  The child writes its result
    back through *result_queue* so a SIGKILL on the child surfaces to the
    parent as "queue.get timed out / no result" rather than poisoning a whole
    pool the way ``ProcessPoolExecutor`` does.

    We re-init ``_SHARED_SESSION_DB`` in the child since the parent's
    inherited SQLite connection isn't safe to use post-fork.
    """
    # Lazy module-level import to avoid circular import (fan_process ← fan).
    import fan as _fan

    _fan._SHARED_SESSION_DB = None  # force re-init in this child

    output_dir = Path(output_dir_str)
    brief_path = Path(brief_path_str)
    stem = brief_path.stem

    pid_path = output_dir / f"{stem}.pid"
    try:
        pid_path.write_text(str(os.getpid()), encoding="utf-8")
    except OSError:
        pass

    try:
        result = _fan._run_one(
            brief_path=brief_path,
            output_dir=output_dir,
            model=model,
            toolset_list=toolset_list,
            max_tokens=max_tokens,
            session_id=session_id,
            task_timeout=task_timeout,
        )
        try:
            result_queue.put(asdict(result))
        except Exception:
            # Queue may be broken if parent died; ignore.
            pass
    finally:
        try:
            if pid_path.exists():
                pid_path.unlink()
        except OSError:
            pass


class _ProcessTaskRunner:
    """Per-task process executor that survives individual child deaths.

    Unlike ``ProcessPoolExecutor`` (which broadcasts BrokenProcessPool to
    *all* pending/running futures when any child dies abruptly), this runner
    spawns one ``multiprocessing.Process`` per task and tracks them
    independently.  A SIGKILL on one task only affects that task.

    macOS fork-safety constraint: forking from a non-main thread (or while
    other Python threads exist that have touched Obj-C frameworks) triggers
    SIGABRT in the child via libobjc's fork-safety check.  To avoid this we
    do NOT use a worker thread pool.  The caller drives the runner from the
    main thread via ``poll()`` calls; ``Process.start()`` and queue polling
    both happen on the main thread.
    """

    def __init__(self, max_workers: int, mp_context: Any) -> None:
        self._max_workers = max_workers
        self._ctx = mp_context
        self._pending: list[_ProcTask] = []
        self._running: list[_ProcTask] = []
        self._completed: list[_ProcTask] = []
        self._shutdown = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit(self, task_args: tuple, brief: Path, chosen_model: str) -> _ProcTask:
        """Enqueue a task for later execution (does not start it yet)."""
        t = _ProcTask(task_args=task_args, brief=brief, chosen_model=chosen_model)
        self._pending.append(t)
        return t

    def poll(self, *, drain_only: bool = False) -> list[_ProcTask]:
        """Advance the runner: start new tasks if under max_workers, harvest
        any finished/dead children, return newly-completed tasks.

        Must be called from the main thread.  Non-blocking (returns within
        ~0 ms on average; up to a few ms on queue.get_nowait per running task).
        """
        newly_done: list[_ProcTask] = []

        # 1) harvest dead/finished running processes
        still_running: list[_ProcTask] = []
        for t in self._running:
            alive = t.proc.is_alive()
            if not alive:
                self._harvest_done(t)
                newly_done.append(t)
                continue
            # Try non-blocking queue drain — successful drain means the child
            # has put its result and will exit soon.
            try:
                t.result = t.queue.get_nowait()
            except Exception:
                pass
            # Deadline / shutdown enforcement
            if self._shutdown:
                try:
                    t.proc.terminate()
                except Exception:
                    pass
                still_running.append(t)
                continue
            if time.monotonic() > t.deadline:
                try:
                    t.proc.terminate()
                except Exception:
                    pass
                still_running.append(t)
                continue
            still_running.append(t)
        self._running = still_running

        # 2) launch new tasks if we have slack and aren't shutting down
        if not drain_only and not self._shutdown:
            while self._pending and len(self._running) < self._max_workers:
                self._start_one(self._pending.pop(0))

        return newly_done

    def cancel_pending(self) -> list[_ProcTask]:
        """Drain still-pending tasks; return them so the caller can record
        them as 'cancelled'.  Called when the stop event fires."""
        cancelled = list(self._pending)
        self._pending.clear()
        return cancelled

    def terminate_all(self, sig: int = signal.SIGTERM) -> None:
        """Send *sig* to every running child.  Called by the signal handler
        plumbing in the caller."""
        for t in self._running:
            try:
                if t.proc.is_alive():
                    os.kill(t.proc.pid, sig)
            except (OSError, AttributeError):
                pass

    def shutdown(self, *, hard: bool = False) -> None:
        """Gracefully (or forcefully) wind down all children.

        If *hard* is ``True``, sends SIGKILL immediately.  Otherwise sends
        SIGTERM and gives children a few seconds to exit before escalating.
        """
        self._shutdown = True
        if hard:
            self.terminate_all(signal.SIGKILL)
        else:
            self.terminate_all(signal.SIGTERM)
        # Final reap pass — give children a few seconds to die.
        end = time.monotonic() + 5.0
        while self._running and time.monotonic() < end:
            self.poll(drain_only=True)
            time.sleep(0.1)
        # Force-kill any survivors.
        for t in self._running:
            try:
                if t.proc.is_alive():
                    t.proc.kill()
                t.proc.join(timeout=1)
            except Exception:
                pass
            self._harvest_done(t)
        self._running.clear()

    def has_work(self) -> bool:
        """Return ``True`` if there are pending or running tasks."""
        return bool(self._pending or self._running)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _start_one(self, t: _ProcTask) -> None:
        """Spawn a child process for a single pending task."""
        q = self._ctx.Queue()
        proc = self._ctx.Process(
            target=_process_worker_with_queue,
            args=(q, *t.task_args),
            daemon=False,
        )
        proc.start()
        t.proc = proc
        t.queue = q
        t.started_at_mono = time.monotonic()
        # The child has its own task_timeout watchdog; add slop here so the
        # child's watchdog wins normal completion races.
        t.deadline = t.started_at_mono + max(t.task_args[6], 5.0) + 30.0
        self._running.append(t)

    def _harvest_done(self, t: _ProcTask) -> None:
        """Move a finished/dead task to the completed list with a result."""
        # Lazy import to avoid circular import (fan_process ← fan).
        from fan import TaskResult  # noqa: F811

        # Killed children (SIGKILL etc.) never reach their own finally-clause
        # pidfile cleanup. Remove the orphan here so the output dir stays tidy.
        # task_args = (brief, output_dir, model, toolsets, max_tokens, session, timeout)
        try:
            pid_path = Path(t.task_args[1]) / f"{t.brief.stem}.pid"
            if pid_path.exists():
                pid_path.unlink()
        except (OSError, IndexError):
            pass

        # Try to drain the result queue (non-blocking) — the child may have
        # put a result then been killed before exiting cleanly.
        if t.result is None and t.queue is not None:
            try:
                t.result = t.queue.get_nowait()
            except Exception:
                pass
        if t.result is None:
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            exitcode = getattr(t.proc, "exitcode", None)
            killed_signal = (
                -exitcode if (exitcode is not None and exitcode < 0) else None
            )
            t.result = asdict(
                TaskResult(
                    brief=str(t.brief),
                    stem=t.brief.stem,
                    model=t.chosen_model,
                    status="killed",
                    elapsed_s=time.monotonic() - t.started_at_mono,
                    started_at=now,
                    finished_at=now,
                    error=(
                        f"child process died (exitcode={exitcode}"
                        + (f", signal={killed_signal}" if killed_signal else "")
                        + ")"
                    ),
                    error_class="ChildExited",
                    task_timeout_s=t.task_args[6],
                    pid=getattr(t.proc, "pid", None),
                )
            )
        t.done = True
        self._completed.append(t)
