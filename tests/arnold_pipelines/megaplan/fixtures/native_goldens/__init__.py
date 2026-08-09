"""Native golden trace helpers.

Provides utilities for comparing and recording directory-based native
golden trace fixtures.  Each fixture directory contains six canonical
files produced by :class:`arnold.pipeline.native.trace.NativeTraceHooks`:

* ``events.ndjson`` — NDJSON event stream
* ``state.json`` — runtime state snapshot
* ``stages.json`` — ordered stage sequence
* ``artifacts.json`` — artifact inventory (``{relpath: sha256:<hex>}``)
* ``checkpoint.json`` — final checkpoint notification
* ``tree.json`` — native execution tree projection

Minimal proven normalization
----------------------------
The comparison strips non-deterministic fields from ``events.ndjson``
entries (``seq``, ``ts_utc``, ``ts_rel_init_s``) before diffing.
All other files are compared as canonical JSON (sorted keys, compact).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

# ── public constants ───────────────────────────────────────────────────────

TRACE_FILE_NAMES: tuple[str, ...] = (
    "events.ndjson",
    "state.json",
    "stages.json",
    "artifacts.json",
    "checkpoint.json",
    "tree.json",
)

# Fields stripped from NDJSON events before comparison (non-deterministic).
_EVENT_STRIP_KEYS: frozenset[str] = frozenset({"seq", "ts_utc", "ts_rel_init_s"})


# ── serialization helpers ──────────────────────────────────────────────────


def _canonical_json(obj: Any) -> str:
    """Serialize *obj* to canonical JSON (sorted keys, compact)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _normalize_event_line(line: str) -> str:
    """Parse an NDJSON line and return its canonical form minus stripped keys."""
    obj = json.loads(line)
    for key in _EVENT_STRIP_KEYS:
        obj.pop(key, None)
    return _canonical_json(obj)


def _normalize_events_ndjson(text: str) -> str:
    """Normalize an NDJSON event stream by stripping non-deterministic fields."""
    lines = text.strip().split("\n")
    normalized = [_normalize_event_line(line) for line in lines if line.strip()]
    return "\n".join(normalized) + "\n" if normalized else ""


def _normalize_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_json_value(item) for item in value]
    if isinstance(value, str) and "/artifacts/" in value:
        return "<artifact_root>/" + value.split("/artifacts/", 1)[1]
    return value


def _normalize_trace_json(filename: str, value: Any) -> Any:
    normalized = _normalize_json_value(value)
    if filename == "artifacts.json" and isinstance(normalized, dict):
        # Artifact bodies include the per-run temp root, so their hashes are
        # not cross-run identities. The stable contract here is inventory.
        return {key: "sha256:<content-dependent>" for key in normalized}
    return normalized


# ── comparison ─────────────────────────────────────────────────────────────


def compare_native_golden_dir(
    golden_dir: str | Path,
    actual_dir: str | Path,
) -> tuple[bool, str]:
    """Compare *actual_dir* against the committed *golden_dir*.

    Returns ``(True, "")`` when all six canonical trace files match
    (after normalization).  Returns ``(False, diagnostic)`` on mismatch.

    The comparison normalizes ``events.ndjson`` by stripping
    ``seq``, ``ts_utc``, and ``ts_rel_init_s`` from every event.
    All other files are compared as canonical JSON.
    """
    golden = Path(golden_dir)
    actual = Path(actual_dir)

    if not golden.is_dir():
        return False, f"Golden directory does not exist: {golden}"
    if not actual.is_dir():
        return False, f"Actual trace directory does not exist: {actual}"

    mismatches: list[str] = []

    for filename in TRACE_FILE_NAMES:
        golden_file = golden / filename
        actual_file = actual / filename

        if not golden_file.is_file():
            mismatches.append(f"Missing golden file: {filename}")
            continue
        if not actual_file.is_file():
            mismatches.append(f"Missing actual file: {filename}")
            continue

        golden_text = golden_file.read_text(encoding="utf-8")
        actual_text = actual_file.read_text(encoding="utf-8")

        if filename == "events.ndjson":
            golden_norm = _normalize_events_ndjson(golden_text)
            actual_norm = _normalize_events_ndjson(actual_text)
            if golden_norm != actual_norm:
                mismatches.append(
                    f"events.ndjson differs after normalization "
                    f"(golden {len(golden_norm)} chars, actual {len(actual_norm)} chars)"
                )
        else:
            # Compare as canonical JSON to normalize key ordering / whitespace.
            try:
                golden_obj = json.loads(golden_text)
                actual_obj = json.loads(actual_text)
            except json.JSONDecodeError as exc:
                mismatches.append(f"{filename}: invalid JSON ({exc})")
                continue
            if _normalize_trace_json(filename, golden_obj) != _normalize_trace_json(
                filename, actual_obj
            ):
                mismatches.append(f"{filename} differs")

    if mismatches:
        return False, "\n".join(mismatches)
    return True, ""


# ── recording ──────────────────────────────────────────────────────────────


def record_native_golden_dir(
    source_dir: str | Path,
    target_dir: str | Path,
    *,
    overwrite: bool = False,
) -> None:
    """Record a native golden trace from *source_dir* into *target_dir*.

    Copies all six canonical trace files.  Raises :class:`FileExistsError`
    when *target_dir* already exists and *overwrite* is ``False``.
    """
    source = Path(source_dir)
    target = Path(target_dir)

    if not source.is_dir():
        raise FileNotFoundError(f"Source trace directory does not exist: {source}")

    if target.exists():
        if not overwrite:
            raise FileExistsError(
                f"Golden target directory already exists: {target}. "
                f"Use overwrite=True to replace it."
            )
        shutil.rmtree(target)

    target.mkdir(parents=True, exist_ok=True)

    for filename in TRACE_FILE_NAMES:
        src_file = source / filename
        if not src_file.is_file():
            raise FileNotFoundError(
                f"Required trace file missing from source: {filename}"
            )
        target_file = target / filename
        if filename in {"state.json", "artifacts.json"}:
            payload = json.loads(src_file.read_text(encoding="utf-8"))
            target_file.write_text(
                json.dumps(_normalize_trace_json(filename, payload), indent=2) + "\n",
                encoding="utf-8",
            )
        else:
            shutil.copy2(src_file, target_file)
