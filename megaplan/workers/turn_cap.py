"""Host-wide premium worker turn admission control."""

from __future__ import annotations

import json
import os
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import fcntl

from megaplan.types import CliError


DEFAULT_TURN_CAP = 3
TURN_CAP_ENV = "MEGAPLAN_WORKER_TURN_CAP"
TURN_CAP_DIR_ENV = "MEGAPLAN_WORKER_TURN_CAP_DIR"
HOST_TURN_CAP_SOURCE = "host_turn_cap"


@dataclass(frozen=True)
class TurnSlot:
    """A held host-turn slot."""

    index: int | None
    path: Path | None
    metadata: dict[str, Any]
    enabled: bool = True


def _configured_cap(env: dict[str, str] | None = None) -> int:
    raw = (env or os.environ).get(TURN_CAP_ENV)
    if raw is None or raw == "":
        return DEFAULT_TURN_CAP
    try:
        cap = int(raw)
    except ValueError as exc:
        raise CliError(
            "invalid_args",
            f"{TURN_CAP_ENV} must be an integer, got {raw!r}",
            extra={"source": HOST_TURN_CAP_SOURCE},
        ) from exc
    if cap < 0:
        raise CliError(
            "invalid_args",
            f"{TURN_CAP_ENV} must be >= 0, got {cap}",
            extra={"source": HOST_TURN_CAP_SOURCE},
        )
    return cap


def _default_lock_dir(env: dict[str, str] | None = None) -> Path:
    raw = (env or os.environ).get(TURN_CAP_DIR_ENV)
    if raw:
        return Path(raw)
    return Path(tempfile.gettempdir()) / "megaplan-worker-turn-cap"


def _slot_path(lock_dir: Path, index: int) -> Path:
    return lock_dir / f"slot-{index}.json"


def _read_metadata(path: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    except OSError:
        return None
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _pid_is_live(pid: object) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _live_metadata(path: Path) -> dict[str, Any] | None:
    metadata = _read_metadata(path)
    if not metadata:
        return None
    return metadata if _pid_is_live(metadata.get("pid")) else None


def _build_metadata(
    *,
    engine: str,
    channel: str | None,
    step: str | None,
    plan: str | os.PathLike[str] | None,
) -> dict[str, Any]:
    return {
        "pid": os.getpid(),
        "engine": engine,
        "channel": channel,
        "step": step,
        "plan": str(plan) if plan is not None else None,
        "acquired": time.time(),
    }


def _rate_limit_error(*, cap: int, lock_dir: Path) -> CliError:
    active_slots: list[dict[str, Any]] = []
    for index in range(cap):
        metadata = _live_metadata(_slot_path(lock_dir, index))
        if metadata:
            active_slots.append({"slot": index, **metadata})
    return CliError(
        "rate_limit",
        f"Host premium-turn cap exhausted ({len(active_slots)}/{cap} slots active).",
        extra={
            "source": HOST_TURN_CAP_SOURCE,
            "retryable": True,
            "cap": cap,
            "lock_dir": str(lock_dir),
            "active_slots": active_slots,
        },
    )


@contextmanager
def acquire_turn_slot(
    *,
    engine: str,
    channel: str | None = None,
    step: str | None = None,
    plan: str | os.PathLike[str] | None = None,
    cap: int | None = None,
    lock_dir: str | os.PathLike[str] | None = None,
) -> Iterator[TurnSlot]:
    """Acquire one host-wide premium-turn slot or raise retryable rate_limit.

    Slots are represented by files in a shared lock directory and guarded with
    non-blocking ``fcntl`` locks. The JSON body is operational metadata only;
    the lock itself is the concurrency primitive.
    """

    resolved_cap = _configured_cap() if cap is None else cap
    if resolved_cap < 0:
        raise CliError(
            "invalid_args",
            "turn cap must be >= 0",
            extra={"source": HOST_TURN_CAP_SOURCE},
        )
    metadata = _build_metadata(engine=engine, channel=channel, step=step, plan=plan)
    if resolved_cap == 0:
        yield TurnSlot(index=None, path=None, metadata=metadata, enabled=False)
        return

    resolved_lock_dir = Path(lock_dir) if lock_dir is not None else _default_lock_dir()
    resolved_lock_dir.mkdir(parents=True, exist_ok=True)

    held_file: Any | None = None
    held_path: Path | None = None
    held_index: int | None = None
    for index in range(resolved_cap):
        path = _slot_path(resolved_lock_dir, index)
        live = _live_metadata(path)
        if live is not None:
            continue
        slot_file = path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(slot_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            slot_file.close()
            continue
        slot_file.seek(0)
        slot_file.truncate()
        slot_file.write(json.dumps(metadata, sort_keys=True))
        slot_file.write("\n")
        slot_file.flush()
        os.fsync(slot_file.fileno())
        held_file = slot_file
        held_path = path
        held_index = index
        break

    if held_file is None or held_path is None or held_index is None:
        raise _rate_limit_error(cap=resolved_cap, lock_dir=resolved_lock_dir)

    try:
        yield TurnSlot(index=held_index, path=held_path, metadata=metadata)
    finally:
        try:
            held_file.seek(0)
            held_file.truncate()
            held_file.flush()
            os.fsync(held_file.fileno())
        finally:
            fcntl.flock(held_file.fileno(), fcntl.LOCK_UN)
            held_file.close()
