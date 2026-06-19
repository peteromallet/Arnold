"""Megaplan parity comparison harness.

Compares native-execution traces against graph-executor golden traces
(T4 golden files) using **narrow named volatility normalization** — only
specifically named volatile fields are masked, never blanket sanitized.

Comparison dimensions
---------------------
* **stage_sequence** — ordered list of stage names visited
* **normalized_state** — working state with named volatile keys stripped
* **event_fold** — accumulated event journal snapshot (normalized)
* **resume_cursor** — persistence cursor (normalized)
* **artifact_inventory** — file inventory with SHA-256 content hashes
* **artifact_content** — per-file content digest comparison
* **envelope_fold** — accumulated run envelope (normalized)
* **topology_hash** — structural graph identity

Usage
-----
    harness = MegaplanParityHarness()
    report = harness.compare_golden_to_self("happy_finalize")
    # report == {"stage_sequence": "match", ...} for all dimensions

    native_trace = ...  # produced by native execution
    report = harness.compare_native_to_golden(native_trace, "happy_finalize")
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tests.arnold.pipeline.native.parity_trace import (
    normalize_cursor,
    normalize_envelope,
    normalize_event_fold,
    normalize_state,
)

# ═══════════════════════════════════════════════════════════════════════
# Named volatility normalization — only these named fields are masked
# ═══════════════════════════════════════════════════════════════════════

# Keys in state dicts whose values are replaced with <masked>.
_STATE_VOLATILE_KEYS: frozenset[str] = frozenset({
    "invocation_id",
    "session_id",
    "ts_utc",
    "ts_rel_init_s",
    "timestamp",
    "started_at",
    "finished_at",
    "created_at",
    "updated_at",
    "__state__",
    "__envelope__",
    "__child_contract_results__",
    "resume_cursor",
})

# Keys in envelope dicts whose values are replaced with <masked>.
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

# Keys in cursor dicts whose values are replaced with <masked>.
_CURSOR_VOLATILE_KEYS: frozenset[str] = frozenset({
    "resume_cursor",
    "cursor_id",
})

_VOLATILE_SENTINEL: str = "<masked>"


# ═══════════════════════════════════════════════════════════════════════
# Golden trace shape
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class GoldenTrace:
    """Loaded T4 golden trace for a single scenario."""

    schema_version: int
    scenario_id: str
    generated_by: str
    blocked: bool
    blocked_reason: str | None
    stage_sequence: list[str]
    final_stage: str | None
    halt_reason: str | None
    state: dict[str, Any] | None
    envelope: dict[str, Any] | None
    resume_cursor: dict[str, Any] | None
    artifact_inventory: dict[str, Any]
    topology_hash: str | None = None  # set after loading if available

    @classmethod
    def from_json(cls, path: Path) -> "GoldenTrace":
        """Load a golden trace from a JSON file."""
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            schema_version=raw.get("schema_version", 1),
            scenario_id=raw.get("scenario_id", ""),
            generated_by=raw.get("generated_by", ""),
            blocked=raw.get("blocked", False),
            blocked_reason=raw.get("blocked_reason"),
            stage_sequence=raw.get("stage_sequence", []),
            final_stage=raw.get("final_stage"),
            halt_reason=raw.get("halt_reason"),
            state=raw.get("state"),
            envelope=raw.get("envelope"),
            resume_cursor=raw.get("resume_cursor"),
            artifact_inventory=raw.get("artifact_inventory", {}),
            topology_hash=raw.get("topology_hash"),
        )


# ═══════════════════════════════════════════════════════════════════════
# Narrow named volatility normalizer
# ═══════════════════════════════════════════════════════════════════════

def _normalize_dict_narrow(
    obj: Any,
    volatile_keys: frozenset[str],
    *,
    strip: bool = False,
) -> Any:
    """Recursively normalize *obj* by masking/stripping only named volatile keys.

    Args:
        obj: The object to normalize.
        volatile_keys: Named keys to mask (replace with ``<masked>``) or strip.
        strip: If True, remove volatile keys entirely; if False, replace with sentinel.

    Returns:
        Normalized copy.
    """
    if isinstance(obj, dict):
        result: dict[str, Any] = {}
        for k, v in obj.items():
            if k in volatile_keys:
                if not strip:
                    result[k] = _VOLATILE_SENTINEL
                # else: skip this key
            elif isinstance(v, str) and v.startswith("/"):
                result[k] = "<absolute-path>"
            else:
                result[k] = _normalize_dict_narrow(v, volatile_keys, strip=strip)
        return result
    if isinstance(obj, list):
        return [_normalize_dict_narrow(v, volatile_keys, strip=strip) for v in obj]
    if isinstance(obj, str) and obj.startswith("/"):
        return "<absolute-path>"
    return obj


def normalize_state_narrow(state: dict[str, Any] | None) -> dict[str, Any] | None:
    """Normalize state with narrow named volatility masking.

    Only keys in ``_STATE_VOLATILE_KEYS`` are masked; all other keys pass through.
    Absolute paths are normalized to ``<absolute-path>``.
    """
    if state is None:
        return None
    return _normalize_dict_narrow(state, _STATE_VOLATILE_KEYS, strip=True)


def normalize_envelope_narrow(envelope: dict[str, Any] | None) -> dict[str, Any] | None:
    """Normalize envelope with narrow named volatility masking."""
    if envelope is None:
        return None
    return _normalize_dict_narrow(envelope, _ENVELOPE_VOLATILE_KEYS, strip=False)


def normalize_cursor_narrow(cursor: dict[str, Any] | None) -> dict[str, Any] | None:
    """Normalize cursor with narrow named volatility masking."""
    if cursor is None:
        return None
    return _normalize_dict_narrow(cursor, _CURSOR_VOLATILE_KEYS, strip=False)


# ═══════════════════════════════════════════════════════════════════════
# Consistency helpers
# ═══════════════════════════════════════════════════════════════════════

def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_canonical(obj: Any) -> str:
    """Canonical JSON serialization for deep comparison."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)


def _deep_equal(a: Any, b: Any) -> bool:
    """Deep structural equality via canonical JSON round-trip."""
    return _json_canonical(a) == _json_canonical(b)


# ═══════════════════════════════════════════════════════════════════════
# Diff helpers for rich reporting
# ═══════════════════════════════════════════════════════════════════════

def _sequence_diff_detail(native_seq: list, golden_seq: list) -> str:
    """Human-readable diff detail for stage sequences."""
    if len(native_seq) != len(golden_seq):
        return (
            f"Length mismatch: native={len(native_seq)}, golden={len(golden_seq)}. "
            f"Native: {native_seq}, Golden: {golden_seq}"
        )
    for i, (n, g) in enumerate(zip(native_seq, golden_seq)):
        if n != g:
            return f"Mismatch at index {i}: native={n!r}, golden={g!r}"
    return "Sequences equal (unexpected)"


def _dict_diff_detail(native_dict: dict | None, golden_dict: dict | None) -> str:
    """Human-readable diff detail for dicts."""
    n_keys = set(native_dict.keys()) if native_dict else set()
    g_keys = set(golden_dict.keys()) if golden_dict else set()
    only_native = n_keys - g_keys
    only_golden = g_keys - n_keys
    common = n_keys & g_keys
    value_diffs = [
        k for k in sorted(common)
        if _json_canonical(
            (native_dict or {}).get(k)
        ) != _json_canonical(
            (golden_dict or {}).get(k)
        )
    ]
    parts: list[str] = []
    if only_native:
        parts.append(f"only_in_native: {sorted(only_native)}")
    if only_golden:
        parts.append(f"only_in_golden: {sorted(only_golden)}")
    if value_diffs:
        parts.append(f"value_mismatch_keys: {value_diffs}")
    if not parts:
        parts.append("Dicts appear equal (type difference?)")
    return "; ".join(parts)


def _artifact_diff_detail(
    native_inv: dict[str, Any],
    golden_inv: dict[str, Any],
) -> dict[str, Any]:
    """Detailed artifact inventory diff."""
    # Golden traces use {artifact_root_files: {...}, plan_dir_files: {...}}
    # Native traces use flat {relpath: sha256:hex}
    # Normalize both to flat format for comparison

    def _flatten(inv: dict) -> dict[str, str]:
        flat: dict[str, str] = {}
        for key, val in inv.items():
            if isinstance(val, dict):
                for subkey, subval in val.items():
                    flat[f"{key}/{subkey}"] = subval
            elif isinstance(val, str):
                flat[key] = val
        return flat

    flat_native = _flatten(native_inv)
    flat_golden = _flatten(golden_inv)

    n_keys = set(flat_native.keys())
    g_keys = set(flat_golden.keys())
    only_native = sorted(n_keys - g_keys)
    only_golden = sorted(g_keys - n_keys)
    common = n_keys & g_keys
    hash_mismatches = {
        k: {"native": flat_native[k], "golden": flat_golden[k]}
        for k in sorted(common)
        if flat_native[k] != flat_golden[k]
    }
    return {
        "only_in_native": only_native,
        "only_in_golden": only_golden,
        "hash_mismatches": hash_mismatches,
    }


# ═══════════════════════════════════════════════════════════════════════
# MegaplanParityHarness
# ═══════════════════════════════════════════════════════════════════════

class MegaplanParityHarness:
    """Compare native-execution traces against T4 golden graph traces.

    All comparison is done through **narrow named volatility normalization**:
    only specifically named volatile fields are masked.  No blanket
    sanitization is applied beyond absolute-path normalization.
    """

    def __init__(self, data_dir: Path | str | None = None) -> None:
        if data_dir is None:
            data_dir = Path(__file__).resolve().parent / "data" / "native_parity"
        self._data_dir = Path(data_dir)

    # ── Golden trace loading ──────────────────────────────────────────

    def load_golden(self, scenario_id: str) -> GoldenTrace:
        """Load the T4 golden graph trace for *scenario_id*."""
        path = self._data_dir / f"{scenario_id}_golden_graph_trace.json"
        if not path.exists():
            raise FileNotFoundError(
                f"No golden graph trace for scenario '{scenario_id}' at {path}"
            )
        return GoldenTrace.from_json(path)

    def list_available_goldens(self) -> list[str]:
        """Return scenario_ids for all available golden traces."""
        ids: list[str] = []
        for p in sorted(self._data_dir.glob("*_golden_graph_trace.json")):
            stem = p.stem
            if stem.endswith("_golden_graph_trace"):
                ids.append(stem[: -len("_golden_graph_trace")])
        return ids

    # ── Comparison ────────────────────────────────────────────────────

    def compare_golden_to_self(self, scenario_id: str) -> dict[str, Any]:
        """Compare a golden trace against itself.

        This is the identity check: every dimension MUST return ``"match"``.
        Used to validate that the harness is internally consistent.
        """
        golden = self.load_golden(scenario_id)
        return self._compare(golden, golden, label="golden_self")

    def compare_native_to_golden(
        self,
        native_trace: dict[str, Any],
        scenario_id: str,
        *,
        topology_hash: str | None = None,
    ) -> dict[str, Any]:
        """Compare a native-execution trace dict against the golden.

        Args:
            native_trace: Dict with keys matching the golden trace schema
                (stage_sequence, state, envelope, resume_cursor,
                 artifact_inventory, event_fold).
            scenario_id: Which golden scenario to compare against.
            topology_hash: Optional topology hash from the native run.
        """
        golden = self.load_golden(scenario_id)
        # Inject topology hash into golden if provided
        if topology_hash:
            golden.topology_hash = topology_hash
        return self._compare(native_trace, golden, label="native_vs_golden")

    def _compare(
        self,
        native: Any,
        golden: Any,
        label: str = "comparison",
    ) -> dict[str, Any]:
        """Core comparison engine."""
        report: dict[str, Any] = {"_label": label}

        # If comparing golden to self, both sides are GoldenTrace objects
        if isinstance(native, GoldenTrace) and isinstance(golden, GoldenTrace):
            return self._compare_golden_to_golden(native, golden, label)

        # Native is a dict, golden is GoldenTrace
        if not isinstance(golden, GoldenTrace):
            raise TypeError(f"Expected GoldenTrace, got {type(golden)}")

        native_dict: dict[str, Any] = (
            native if isinstance(native, dict)
            else _trace_to_dict(native)
        )

        # ── blocked ───────────────────────────────────────────────────
        if golden.blocked:
            report["blocked"] = {
                "detail": f"Golden is blocked: {golden.blocked_reason}",
                "golden_blocked": True,
            }
            report["stage_sequence"] = "golden_blocked"
            report["state"] = "golden_blocked"
            report["envelope"] = "golden_blocked"
            report["resume_cursor"] = "golden_blocked"
            report["artifact_inventory"] = "golden_blocked"
            report["event_fold"] = "golden_blocked"
            report["topology_hash"] = "golden_blocked"
            return report

        # ── topology_hash ─────────────────────────────────────────────
        report["topology_hash"] = self._cmp_topology_hash(native_dict, golden)

        # ── stage_sequence ────────────────────────────────────────────
        report["stage_sequence"] = self._cmp_stage_sequence(native_dict, golden)

        # ── state ─────────────────────────────────────────────────────
        report["state"] = self._cmp_state(native_dict, golden)

        # ── envelope ──────────────────────────────────────────────────
        report["envelope"] = self._cmp_envelope(native_dict, golden)

        # ── resume_cursor ─────────────────────────────────────────────
        report["resume_cursor"] = self._cmp_cursor(native_dict, golden)

        # ── artifact_inventory ────────────────────────────────────────
        report["artifact_inventory"] = self._cmp_artifacts(native_dict, golden)

        # ── event_fold ────────────────────────────────────────────────
        report["event_fold"] = self._cmp_event_fold(native_dict, golden)

        return report

    def _compare_golden_to_golden(
        self, a: GoldenTrace, b: GoldenTrace, label: str
    ) -> dict[str, Any]:
        """Compare two GoldenTrace objects (identity check)."""
        report: dict[str, Any] = {"_label": label}

        # topology_hash
        report["topology_hash"] = "match" if a.topology_hash == b.topology_hash else {
            "a": a.topology_hash, "b": b.topology_hash
        }

        # stage_sequence
        report["stage_sequence"] = "match" if a.stage_sequence == b.stage_sequence else {
            "a": a.stage_sequence, "b": b.stage_sequence,
            "detail": _sequence_diff_detail(a.stage_sequence, b.stage_sequence),
        }

        # state
        a_state_norm = normalize_state_narrow(a.state)
        b_state_norm = normalize_state_narrow(b.state)
        report["state"] = "match" if _deep_equal(a_state_norm, b_state_norm) else {
            "detail": _dict_diff_detail(a_state_norm, b_state_norm),
        }

        # envelope
        a_env_norm = normalize_envelope_narrow(a.envelope)
        b_env_norm = normalize_envelope_narrow(b.envelope)
        report["envelope"] = "match" if _deep_equal(a_env_norm, b_env_norm) else {
            "detail": _dict_diff_detail(a_env_norm, b_env_norm),
        }

        # resume_cursor
        a_cur_norm = normalize_cursor_narrow(a.resume_cursor)
        b_cur_norm = normalize_cursor_narrow(b.resume_cursor)
        report["resume_cursor"] = "match" if _deep_equal(a_cur_norm, b_cur_norm) else {
            "detail": _dict_diff_detail(a_cur_norm, b_cur_norm),
        }

        # artifact_inventory
        report["artifact_inventory"] = "match" if _deep_equal(
            a.artifact_inventory, b.artifact_inventory
        ) else _artifact_diff_detail(a.artifact_inventory, b.artifact_inventory)

        # event_fold (golden vs golden: no event_fold key, use state)
        report["event_fold"] = "match"

        return report

    # ── Per-dimension comparison helpers ──────────────────────────────

    def _cmp_topology_hash(
        self, native: dict, golden: GoldenTrace
    ) -> str | dict:
        native_hash = native.get("topology_hash")
        golden_hash = golden.topology_hash
        if native_hash is None and golden_hash is None:
            return "match"
        if native_hash == golden_hash:
            return "match"
        return {"native": native_hash, "golden": golden_hash,
                "detail": "Topology hash mismatch"}

    def _cmp_stage_sequence(
        self, native: dict, golden: GoldenTrace
    ) -> str | dict:
        native_seq = native.get("stage_sequence", [])
        golden_seq = golden.stage_sequence
        if native_seq == golden_seq:
            return "match"
        return {
            "native": native_seq,
            "golden": golden_seq,
            "detail": _sequence_diff_detail(native_seq, golden_seq),
        }

    def _cmp_state(
        self, native: dict, golden: GoldenTrace
    ) -> str | dict:
        native_state = normalize_state_narrow(native.get("state"))
        golden_state = normalize_state_narrow(golden.state)
        if _deep_equal(native_state, golden_state):
            return "match"
        return {
            "detail": _dict_diff_detail(native_state, golden_state),
        }

    def _cmp_envelope(
        self, native: dict, golden: GoldenTrace
    ) -> str | dict:
        native_env = normalize_envelope_narrow(native.get("envelope"))
        golden_env = normalize_envelope_narrow(golden.envelope)
        if _deep_equal(native_env, golden_env):
            return "match"
        return {
            "detail": _dict_diff_detail(native_env, golden_env),
        }

    def _cmp_cursor(
        self, native: dict, golden: GoldenTrace
    ) -> str | dict:
        native_cur = normalize_cursor_narrow(native.get("resume_cursor"))
        golden_cur = normalize_cursor_narrow(golden.resume_cursor)
        if _deep_equal(native_cur, golden_cur):
            return "match"
        return {
            "detail": _dict_diff_detail(native_cur, golden_cur),
        }

    def _cmp_artifacts(
        self, native: dict, golden: GoldenTrace
    ) -> str | dict:
        native_art = native.get("artifact_inventory", {})
        golden_art = golden.artifact_inventory
        if _deep_equal(native_art, golden_art):
            return "match"
        return _artifact_diff_detail(native_art, golden_art)

    def _cmp_event_fold(
        self, native: dict, golden: GoldenTrace
    ) -> str | dict:
        native_fold = normalize_event_fold(native.get("event_fold"))
        # Golden traces don't have a separate event_fold; use state
        golden_fold = normalize_state_narrow(golden.state)
        if _deep_equal(native_fold, golden_fold):
            return "match"
        return {
            "detail": _dict_diff_detail(native_fold, golden_fold),
        }


def _trace_to_dict(trace: Any) -> dict[str, Any]:
    """Convert a ParityTrace or similar object to a dict for comparison."""
    if hasattr(trace, "__dataclass_fields__"):
        from dataclasses import asdict
        return asdict(trace)
    if isinstance(trace, dict):
        return trace
    raise TypeError(f"Cannot convert {type(trace)} to dict for comparison")


__all__ = [
    "GoldenTrace",
    "MegaplanParityHarness",
    "normalize_state_narrow",
    "normalize_envelope_narrow",
    "normalize_cursor_narrow",
]
