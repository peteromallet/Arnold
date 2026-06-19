"""Graph trace capture and canonical diff helpers for native/graph parity tests.

Provides:

* :class:`TraceCaptureHooks` — ``NullExecutorHooks`` subclass that records
  stage sequence, final state, hook order, envelope, and artifact inventory
  during a graph executor run.
* :class:`ParityTrace` — normalized trace dataclass for comparison.
* :func:`normalize_state`, :func:`normalize_events`, :func:`normalize_cursor`
  — volatile-field masking for state, events, and resume cursors.
* :func:`inventory_artifacts` — content-hash-based inventory of output files.
* :func:`diff_traces` — surface-localized difference report between two traces.
* :func:`capture_graph_trace` — convenience wrapper that runs a pipeline
  through the graph executor with ``TraceCaptureHooks`` and returns a
  normalized ``ParityTrace``.

Volatile fields that are masked during normalization:

* Timestamps (``ts_utc``, ``ts_rel_init_s``, ``init_ts``)
* Run-identity fields (``run_id``, ``plugin_id``)
* Artifact-root paths (``artifact_root``, ``plan_dir``, absolute paths)
* Resume cursor references (``resume_cursor``)
* Sequence numbers (``seq`` → replaced with index)
* Envelope metadata keys that carry runtime identity
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from arnold.pipeline.hooks import NullExecutorHooks
from arnold.pipeline.types import (
    ParallelStage,
    Stage,
    StepContext,
    StepResult,
)

# ═══════════════════════════════════════════════════════════════════════
# Trace data class
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class ParityTrace:
    """Normalized trace captured from a single pipeline run.

    All fields have been normalized to remove volatile runtime data
    (timestamps, run IDs, absolute paths, etc.) so two runs with
    semantically identical behaviour produce equal traces.
    """

    topology_hash: str
    """``sha256:<hex>`` topology hash of the pipeline graph."""

    stage_sequence: list[str]
    """Ordered list of stage names visited (from ``on_stage_complete``)."""

    final_state: dict[str, Any]
    """Normalized working state at run completion."""

    events: list[dict[str, Any]]
    """Normalized event journal entries (sorted by index, timestamps masked)."""

    cursor: dict[str, Any] | None
    """Normalized resume cursor, or ``None`` if no cursor was persisted."""

    artifacts: dict[str, str]
    """Artifact inventory mapping relative path → ``sha256:<hex>`` content hash."""

    hook_order: list[str]
    """Ordered list of hook callback invocations."""

    accumulated_envelope: Any
    """Normalized accumulated envelope at run completion."""


# ═══════════════════════════════════════════════════════════════════════
# Trace capture hooks
# ═══════════════════════════════════════════════════════════════════════


class TraceCaptureHooks(NullExecutorHooks):
    """Graph executor hooks that capture a complete parity trace.

    Records stage sequence, final state, hook invocation order, envelope
    accumulation, and an artifact inventory.  Designed to be passed to
    :func:`arnold.pipeline.executor.run_pipeline`.

    Usage::

        hooks = TraceCaptureHooks()
        run_pipeline(pipeline, initial_state, envelope, hooks=hooks)
        trace = hooks.to_trace(topology_hash, artifact_dir)
    """

    def __init__(self) -> None:
        super().__init__()
        self.stages: list[str] = []
        self.final_state: dict[str, Any] = {}
        self.hook_order: list[str] = []
        self.accumulated_envelope: Any = None
        self.stage_states: dict[str, dict[str, Any]] = {}

    # ── Hook overrides ────────────────────────────────────────────────

    def on_step_start(self, stage, ctx):
        self.hook_order.append(f"on_step_start:{stage.name}")
        return super().on_step_start(stage, ctx)

    def on_step_end(self, stage, ctx, result):
        self.hook_order.append(f"on_step_end:{stage.name}")
        # Routing fixup for phase steps (same as TracingGraphHooks in runtime parity).
        is_decision = bool(getattr(stage, "decision_vocabulary", None))
        loop_cond = getattr(stage, "loop_condition", None)
        if not is_decision and loop_cond is None and result.next == "halt":
            edges = getattr(stage, "edges", ())
            non_halt = [e for e in edges if getattr(e, "target", None) != "halt"]
            if len(non_halt) == 1:
                label = getattr(non_halt[0], "label", None)
                if label:
                    result = StepResult(
                        outputs=getattr(result, "outputs", {}),
                        verdict=getattr(result, "verdict", None),
                        next=label,
                        state_patch=getattr(result, "state_patch", {}),
                        contract_result=getattr(result, "contract_result", None),
                        hook_metadata=getattr(result, "hook_metadata", {}),
                    )
        return super().on_step_end(stage, ctx, result)

    def on_step_error(self, stage, ctx, exc):
        self.hook_order.append(f"on_step_error:{stage.name}")
        return super().on_step_error(stage, ctx, exc)

    def merge_state(self, stage, current_state, patch, owned_keys):
        self.hook_order.append(f"merge_state:{stage.name}")
        return super().merge_state(stage, current_state, patch, owned_keys)

    def join_envelope(self, stage, current_envelope, step_envelope):
        self.hook_order.append(f"join_envelope:{stage.name}")
        result = super().join_envelope(stage, current_envelope, step_envelope)
        self.accumulated_envelope = result
        return result

    def should_suspend(self, stage, state, result):
        self.hook_order.append(f"should_suspend:{stage.name}")
        return super().should_suspend(stage, state, result)

    def should_halt_loop(self, stage, state, iteration):
        self.hook_order.append(f"should_halt_loop:{stage.name}")
        return super().should_halt_loop(stage, state, iteration)

    def on_stage_complete(self, stage, ctx, result, state, owned_keys):
        self.hook_order.append(f"on_stage_complete:{stage.name}")
        self.stages.append(stage.name)
        if isinstance(state, dict):
            self.stage_states[stage.name] = dict(state)
            self.final_state = dict(state)
        return super().on_stage_complete(stage, ctx, result, state, owned_keys)

    def on_edge_traverse(self, producer_stage, consumer_stage, ctx, result):
        self.hook_order.append(
            f"on_edge_traverse:{producer_stage.name}->{consumer_stage.name}"
        )
        return super().on_edge_traverse(producer_stage, consumer_stage, ctx, result)

    def resolve_routing_fallback(self, stage, result, edges, error):
        self.hook_order.append(f"resolve_routing_fallback:{stage.name}")
        return super().resolve_routing_fallback(stage, result, edges, error)

    # ── Trace export ──────────────────────────────────────────────────

    def to_trace(
        self,
        topology_hash: str,
        artifact_dir: Path | str,
        *,
        cursor: dict[str, Any] | None = None,
    ) -> ParityTrace:
        """Build a normalized ``ParityTrace`` from captured data.

        Parameters
        ----------
        topology_hash:
            ``sha256:<hex>`` topology hash for the pipeline graph.
        artifact_dir:
            Directory to scan for output artifacts.
        cursor:
            Optional normalized resume cursor dict.
        """
        return ParityTrace(
            topology_hash=topology_hash,
            stage_sequence=list(self.stages),
            final_state=normalize_state(self.final_state),
            events=[],  # caller fills from file if needed
            cursor=cursor,
            artifacts=inventory_artifacts(Path(artifact_dir)),
            hook_order=list(self.hook_order),
            accumulated_envelope=self.accumulated_envelope,
        )


# ═══════════════════════════════════════════════════════════════════════
# Volatile-field masking helpers
# ═══════════════════════════════════════════════════════════════════════

# Keys that are always stripped from normalized state/envelope dicts.
_STATE_SKIP_KEYS: frozenset[str] = frozenset({
    "__state__",
    "__envelope__",
})

# Keys in event dicts whose values are masked (timestamps, run identity).
_EVENT_VOLATILE_KEYS: frozenset[str] = frozenset({
    "ts_utc",
    "ts_rel_init_s",
})

# Keys in cursor dicts whose values are masked.
_CURSOR_VOLATILE_KEYS: frozenset[str] = frozenset({
    "resume_cursor",
})

# Sentinel for normalized volatile fields.
_VOLATILE_SENTINEL: str = "<masked>"

# Regex for detecting absolute paths (UNIX + macOS).
_ABS_PATH_RE = re.compile(r"^(/[^\s\"',;:{}[\]()]+)+")


def _mask_paths_in_string(value: str) -> str:
    """Replace absolute paths in a string with ``<path>``."""
    return _ABS_PATH_RE.sub("<path>", value)


def _mask_paths_in_value(value: Any) -> Any:
    """Recursively replace absolute paths in strings/dicts/lists."""
    if isinstance(value, str):
        return _mask_paths_in_string(value)
    if isinstance(value, dict):
        return {k: _mask_paths_in_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_mask_paths_in_value(v) for v in value]
    return value


def normalize_state(state: dict[str, Any]) -> dict[str, Any]:
    """Return a normalized copy of *state* with internal keys and paths removed.

    Strips ``__state__`` and ``__envelope__`` keys, and masks absolute
    paths in string values.
    """
    clean: dict[str, Any] = {}
    for k, v in state.items():
        if k in _STATE_SKIP_KEYS:
            continue
        clean[k] = _mask_paths_in_value(v)
    return clean


def normalize_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a normalized copy of *events* with volatile fields masked.

    For each event:
    * ``ts_utc`` and ``ts_rel_init_s`` are replaced with ``<masked>``.
    * ``seq`` is replaced with a zero-based index.
    * Absolute paths in string values are replaced with ``<path>``.
    """
    normalized: list[dict[str, Any]] = []
    for idx, event in enumerate(events):
        entry: dict[str, Any] = {}
        for k, v in event.items():
            if k in _EVENT_VOLATILE_KEYS:
                entry[k] = _VOLATILE_SENTINEL
            elif k == "seq":
                entry[k] = idx
            else:
                entry[k] = _mask_paths_in_value(v)
        normalized.append(entry)
    return normalized


def normalize_cursor(cursor: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return a normalized copy of *cursor* with volatile fields masked.

    * ``resume_cursor`` is replaced with ``<masked>``.
    * Absolute paths in string values are replaced with ``<path>``.
    """
    if cursor is None:
        return None
    clean: dict[str, Any] = {}
    for k, v in cursor.items():
        if k in _CURSOR_VOLATILE_KEYS:
            clean[k] = _VOLATILE_SENTINEL
        else:
            clean[k] = _mask_paths_in_value(v)
    return clean


# ═══════════════════════════════════════════════════════════════════════
# Artifact inventory
# ═══════════════════════════════════════════════════════════════════════

# Files excluded from artifact inventory.
_ARTIFACT_SKIP_NAMES: frozenset[str] = frozenset({
    ".events.seq",
    ".events.init_ts",
    "events.ndjson",
    "resume_cursor.json",
})

def normalize_envelope(envelope: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return a normalized copy of *envelope* with named volatile fields masked.

    Named volatile fields that are masked (replaced with ``<masked>``):
    * ``run_id``, ``plugin_id`` — runtime identity
    * ``lease_id``, ``fencing_token`` — infrastructure tokens
    * ``deadline`` — wall-clock derived
    * ``created_at``, ``updated_at`` — timestamps
    * ``cost`` — non-deterministic across executors
    * ``capacity_grant`` — runtime-derived
    * Absolute paths in string values — replaced with ``<absolute-path>``.
    """
    if envelope is None:
        return None

    _ENVELOPE_VOLATILE_KEYS: frozenset[str] = frozenset({
        "run_id",
        "plugin_id",
        "lease_id",
        "fencing_token",
        "deadline",
        "created_at",
        "updated_at",
        "cost",
        "capacity_grant",
    })

    def _clean_env(obj: Any) -> Any:
        if isinstance(obj, dict):
            result: dict[str, Any] = {}
            for k, v in obj.items():
                if k in _ENVELOPE_VOLATILE_KEYS:
                    result[k] = _VOLATILE_SENTINEL
                elif isinstance(v, str) and v.startswith("/"):
                    result[k] = "<absolute-path>"
                else:
                    result[k] = _clean_env(v)
            return result
        if isinstance(obj, list):
            return [_clean_env(v) for v in obj]
        if isinstance(obj, str) and obj.startswith("/"):
            return "<absolute-path>"
        return obj

    return _clean_env(envelope)


def normalize_event_fold(event_fold: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return a normalized copy of an event-fold dict.

    Event folds are produced by :func:`arnold.runtime.wal_fold.fold_journal`
    and merge event payloads into a single accumulated state snapshot.
    This normalizer strips **named volatile keys** and masks absolute paths.

    Named volatile fields that are stripped:
    * ``invocation_id``, ``session_id`` — runtime identity
    * ``ts_utc``, ``ts_rel_init_s``, ``timestamp`` — timestamps
    * ``started_at``, ``finished_at``, ``created_at``, ``updated_at``
    * ``seq`` — volatile sequence numbers
    * ``__state__``, ``__envelope__`` — internal runtime scaffolding
    * Absolute paths in string values → ``<absolute-path>``.
    """
    if event_fold is None:
        return None

    _FOLD_VOLATILE_KEYS: frozenset[str] = frozenset({
        "invocation_id",
        "session_id",
        "ts_utc",
        "ts_rel_init_s",
        "timestamp",
        "started_at",
        "finished_at",
        "created_at",
        "updated_at",
        "seq",
        "__state__",
        "__envelope__",
    })

    def _clean_fold(obj: Any) -> Any:
        if isinstance(obj, dict):
            result: dict[str, Any] = {}
            for k, v in obj.items():
                if k in _FOLD_VOLATILE_KEYS:
                    continue
                elif isinstance(v, str) and v.startswith("/"):
                    result[k] = "<absolute-path>"
                else:
                    result[k] = _clean_fold(v)
            return result
        if isinstance(obj, list):
            return [_clean_fold(v) for v in obj]
        if isinstance(obj, str) and obj.startswith("/"):
            return "<absolute-path>"
        return obj

    return _clean_fold(event_fold)


def inventory_artifacts(
    directory: Path | str,
    *,
    skip_names: frozenset[str] | None = None,
) -> dict[str, str]:
    """Return a mapping of relative-path → ``sha256:<hex>`` for all files under *directory*.

    Skips the event journal sidecar files and resume cursor by default.
    """
    if skip_names is None:
        skip_names = _ARTIFACT_SKIP_NAMES

    directory = Path(directory)
    if not directory.exists() or not directory.is_dir():
        return {}

    inventory: dict[str, str] = {}
    for root, _dirs, files in os.walk(str(directory)):
        for fname in sorted(files):
            if fname in skip_names:
                continue
            fpath = Path(root) / fname
            try:
                content = fpath.read_bytes()
            except (OSError, PermissionError):
                continue
            digest = hashlib.sha256(content).hexdigest()
            rel = str(fpath.relative_to(directory))
            inventory[rel] = f"sha256:{digest}"

    return inventory


# ═══════════════════════════════════════════════════════════════════════
# Surface-localized diff reporting
# ═══════════════════════════════════════════════════════════════════════

# The surfaces that diff_traces compares.
_SURFACES: tuple[str, ...] = (
    "topology_hash",
    "stage_sequence",
    "final_state",
    "events",
    "cursor",
    "artifacts",
    "hook_order",
)


def _json_normalize(obj: Any) -> Any:
    """Canonical JSON round-trip to normalize dict ordering for comparison."""
    return json.loads(json.dumps(obj, sort_keys=True, default=str))


def diff_traces(
    native: ParityTrace,
    graph: ParityTrace,
) -> dict[str, Any]:
    """Return a surface-localized diff report between *native* and *graph* traces.

    Each key is a surface name (``"topology_hash"``, ``"stage_sequence"``,
    ``"final_state"``, ``"events"``, ``"cursor"``, ``"artifacts"``,
    ``"hook_order"``).  Each value is either ``"match"`` or a dict with
    ``native`` / ``graph`` / ``detail`` describing the difference.

    Parameters
    ----------
    native:
        Trace from the native runtime.
    graph:
        Trace from the graph executor.

    Returns
    -------
    dict
        Surface → result mapping.  All surfaces are present; a surface
        that matches yields ``"match"``, otherwise a mismatch dict.
    """
    report: dict[str, Any] = {}

    # ── topology_hash ────────────────────────────────────────────────
    if native.topology_hash == graph.topology_hash:
        report["topology_hash"] = "match"
    else:
        report["topology_hash"] = {
            "native": native.topology_hash,
            "graph": graph.topology_hash,
            "detail": "Topology hash mismatch — graphs differ structurally.",
        }

    # ── stage_sequence ───────────────────────────────────────────────
    if native.stage_sequence == graph.stage_sequence:
        report["stage_sequence"] = "match"
    else:
        report["stage_sequence"] = {
            "native": native.stage_sequence,
            "graph": graph.stage_sequence,
            "detail": _sequence_diff_detail(
                native.stage_sequence, graph.stage_sequence
            ),
        }

    # ── final_state ──────────────────────────────────────────────────
    native_state = _json_normalize(native.final_state)
    graph_state = _json_normalize(graph.final_state)
    if native_state == graph_state:
        report["final_state"] = "match"
    else:
        report["final_state"] = {
            "native": native.final_state,
            "graph": graph.final_state,
            "detail": _dict_diff_detail(native.final_state, graph.final_state),
        }

    # ── events ───────────────────────────────────────────────────────
    native_events = _json_normalize(native.events)
    graph_events = _json_normalize(graph.events)
    if native_events == graph_events:
        report["events"] = "match"
    else:
        report["events"] = {
            "native_count": len(native.events),
            "graph_count": len(graph.events),
            "detail": _events_diff_detail(native.events, graph.events),
        }

    # ── cursor ───────────────────────────────────────────────────────
    native_cursor = _json_normalize(native.cursor)
    graph_cursor = _json_normalize(graph.cursor)
    if native_cursor == graph_cursor:
        report["cursor"] = "match"
    else:
        report["cursor"] = {
            "native": native.cursor,
            "graph": graph.cursor,
            "detail": _dict_diff_detail(
                native.cursor or {}, graph.cursor or {}
            ),
        }

    # ── artifacts ────────────────────────────────────────────────────
    if native.artifacts == graph.artifacts:
        report["artifacts"] = "match"
    else:
        native_keys = set(native.artifacts.keys())
        graph_keys = set(graph.artifacts.keys())
        only_native = native_keys - graph_keys
        only_graph = graph_keys - native_keys
        common = native_keys & graph_keys
        hash_mismatches = {
            k: {"native": native.artifacts[k], "graph": graph.artifacts[k]}
            for k in sorted(common)
            if native.artifacts[k] != graph.artifacts[k]
        }
        report["artifacts"] = {
            "only_in_native": sorted(only_native),
            "only_in_graph": sorted(only_graph),
            "hash_mismatches": hash_mismatches,
        }

    # ── hook_order ───────────────────────────────────────────────────
    if native.hook_order == graph.hook_order:
        report["hook_order"] = "match"
    else:
        report["hook_order"] = {
            "native": native.hook_order,
            "graph": graph.hook_order,
            "detail": _sequence_diff_detail(
                native.hook_order, graph.hook_order
            ),
        }

    # ── accumulated_envelope ─────────────────────────────────────────
    native_env = _json_normalize(native.accumulated_envelope)
    graph_env = _json_normalize(graph.accumulated_envelope)
    if native_env == graph_env:
        report["accumulated_envelope"] = "match"
    else:
        # Normalize both for comparison
        native_normalized = normalize_envelope(native.accumulated_envelope)
        graph_normalized = normalize_envelope(graph.accumulated_envelope)
        if _json_normalize(native_normalized) == _json_normalize(graph_normalized):
            report["accumulated_envelope"] = "match_after_normalization"
        else:
            report["accumulated_envelope"] = {
                "native": native_normalized,
                "graph": graph_normalized,
                "detail": _dict_diff_detail(
                    native_normalized or {}, graph_normalized or {}
                ),
            }

    return report


def _sequence_diff_detail(a: list, b: list) -> str:
    """Return a human-readable summary of differences between two sequences."""
    if len(a) != len(b):
        return (
            f"Length mismatch: {len(a)} vs {len(b)}. "
            f"First diff at index "
            f"{_first_diff_index(a, b)}."
        )
    idx = _first_diff_index(a, b)
    if idx is None:
        return "Sequences are equal (should not reach here)."
    return (
        f"Mismatch at index {idx}: {a[idx]!r} vs {b[idx]!r}"
    )


def _first_diff_index(a: list, b: list) -> int | None:
    """Return the first index where *a* and *b* differ, or None if equal."""
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    if len(a) != len(b):
        return min(len(a), len(b))
    return None


def _dict_diff_detail(a: dict, b: dict) -> str:
    """Return a human-readable summary of differences between two dicts."""
    a_keys = set(a.keys())
    b_keys = set(b.keys())
    only_a = a_keys - b_keys
    only_b = b_keys - a_keys
    common = a_keys & b_keys
    diffs = [k for k in sorted(common) if a.get(k) != b.get(k)]
    parts: list[str] = []
    if only_a:
        parts.append(f"Only in native: {sorted(only_a)}")
    if only_b:
        parts.append(f"Only in graph: {sorted(only_b)}")
    if diffs:
        parts.append(f"Value mismatch on keys: {diffs}")
    if not parts:
        parts.append("Dicts appear equal (type difference?)")
    return "; ".join(parts)


def _events_diff_detail(
    native_events: list[dict], graph_events: list[dict]
) -> str:
    """Return a human-readable summary of event journal differences."""
    if len(native_events) != len(graph_events):
        return (
            f"Event count mismatch: {len(native_events)} (native) "
            f"vs {len(graph_events)} (graph)"
        )
    for i, (ne, ge) in enumerate(zip(native_events, graph_events)):
        if ne != ge:
            n_kind = ne.get("kind", "?")
            g_kind = ge.get("kind", "?")
            if n_kind != g_kind:
                return f"Event {i}: kind mismatch ({n_kind!r} vs {g_kind!r})"
            n_payload_keys = sorted(ne.get("payload", {}).keys())
            g_payload_keys = sorted(ge.get("payload", {}).keys())
            if n_payload_keys != g_payload_keys:
                return (
                    f"Event {i} ({n_kind!r}): payload key mismatch "
                    f"({n_payload_keys} vs {g_payload_keys})"
                )
            return f"Event {i} ({n_kind!r}): payload value mismatch"
    return "Events appear equal (should not reach here)."


# ═══════════════════════════════════════════════════════════════════════
# Convenience: capture a full graph trace
# ═══════════════════════════════════════════════════════════════════════


def capture_graph_trace(
    pipeline: Any,
    initial_state: dict[str, Any],
    envelope: Any,
    topology_hash: str,
    artifact_dir: Path,
    *,
    cursor: dict[str, Any] | None = None,
) -> ParityTrace:
    """Run *pipeline* through the graph executor and return a normalized trace.

    Parameters
    ----------
    pipeline:
        A ``Pipeline`` instance to run.
    initial_state:
        Initial working state dict.
    envelope:
        A ``RuntimeEnvelope`` instance.
    topology_hash:
        ``sha256:<hex>`` topology hash for the pipeline.
    artifact_dir:
        Directory where the run writes artifacts (events, state, etc.).
    cursor:
        Optional pre-normalized resume cursor.

    Returns
    -------
    ParityTrace
        Normalized trace with all volatile fields masked.
    """
    from arnold.pipeline.executor import run_pipeline
    from arnold.runtime.event_journal import read_event_journal

    hooks = TraceCaptureHooks()
    run_pipeline(pipeline, initial_state, envelope, hooks=hooks)

    # Read events from the journal written by the executor.
    events_raw = read_event_journal(artifact_dir)
    normalized_events = normalize_events(events_raw)

    # Read cursor if one was persisted.
    cursor_data: dict[str, Any] | None = None
    cursor_path = artifact_dir / "resume_cursor.json"
    if cursor_path.exists():
        try:
            cursor_data = json.loads(cursor_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            cursor_data = None
    normalized_cursor = normalize_cursor(cursor_data)

    # Read state if written to disk.
    state_path = artifact_dir / "state.json"
    if state_path.exists():
        try:
            state_data = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(state_data, dict):
                hooks.final_state = state_data
        except (json.JSONDecodeError, OSError):
            pass

    return hooks.to_trace(
        topology_hash,
        artifact_dir,
        cursor=normalized_cursor,
    )


__all__ = [
    "ParityTrace",
    "TraceCaptureHooks",
    "capture_graph_trace",
    "diff_traces",
    "inventory_artifacts",
    "normalize_cursor",
    "normalize_envelope",
    "normalize_event_fold",
    "normalize_events",
    "normalize_state",
]
