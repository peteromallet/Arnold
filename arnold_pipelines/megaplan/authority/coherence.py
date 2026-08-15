"""Read-only coherent capture helpers for Megaplan authority evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

from arnold_pipelines.megaplan.observability.fold import fold_events
from arnold_pipelines.run_authority.contracts import CoherentObservationEnvelope


COHERENCE_SCHEMA_VERSION = 1


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canonical_hash(value: Any) -> str:
    data = json.dumps(_plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return _sha256(data)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class CoherenceSource:
    """One filesystem source to capture before any reduction is attempted."""

    source_id: str
    relative_path: str
    required: bool = True

    def __post_init__(self) -> None:
        if not self.source_id or "/" in self.source_id:
            raise ValueError("source_id must be a non-empty local identifier")
        relative = Path(self.relative_path)
        if relative.is_absolute() or any(part == ".." for part in relative.parts):
            raise ValueError(f"relative_path must stay inside the plan tree: {self.relative_path!r}")


@dataclass(frozen=True, slots=True)
class CapturedSource:
    """Captured bytes and metadata for one source path."""

    source_id: str
    relative_path: str
    path: Path
    required: bool
    exists: bool
    data: bytes | None
    size: int | None
    mtime_ns: int | None
    sha256: str | None
    error: str = ""

    @property
    def stable_signature(self) -> tuple[str, str, bool, int | None, int | None, str | None, str]:
        return (
            self.source_id,
            self.relative_path,
            self.exists,
            self.size,
            self.mtime_ns,
            self.sha256,
            self.error,
        )

    def metadata(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "relative_path": self.relative_path,
            "path": str(self.path),
            "required": self.required,
            "exists": self.exists,
            "size": self.size,
            "mtime_ns": self.mtime_ns,
            "sha256": self.sha256,
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class CoherentCapture:
    """Reduced coherence view derived only from already captured bytes."""

    plan_dir: Path
    collection_id: str
    captured_at: str
    coherence_state: str
    source_revision: str
    source_cursor: int | None
    source_digests: Mapping[str, str]
    coherence_reasons: tuple[str, ...]
    sources: tuple[CapturedSource, ...]
    attempts: int
    phase1_signatures: tuple[tuple[str, str, bool, int | None, int | None, str | None, str], ...]
    phase2_signatures: tuple[tuple[str, str, bool, int | None, int | None, str | None, str], ...]
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_digests", _freeze(self.source_digests))
        object.__setattr__(self, "coherence_reasons", tuple(sorted(set(self.coherence_reasons))))
        object.__setattr__(self, "sources", tuple(sorted(self.sources, key=lambda item: item.source_id)))
        object.__setattr__(self, "payload", _freeze(self.payload))

    def metadata(self) -> dict[str, Any]:
        return {
            "schema_version": COHERENCE_SCHEMA_VERSION,
            "collection_id": self.collection_id,
            "captured_at": self.captured_at,
            "coherence_state": self.coherence_state,
            "source_revision": self.source_revision,
            "source_cursor": self.source_cursor,
            "source_digests": _plain(self.source_digests),
            "coherence_reasons": list(self.coherence_reasons),
            "attempts": self.attempts,
            "sources": {source.source_id: source.metadata() for source in self.sources},
        }

    def observation_envelope(self) -> CoherentObservationEnvelope:
        dispatch_state = "UNKNOWN" if self.coherence_state == "COHERENT" else "NON_DISPATCHABLE"
        terminal_state = "UNKNOWN" if self.coherence_state == "COHERENT" else "NON_TERMINAL"
        return CoherentObservationEnvelope(
            observation_id=self.collection_id,
            run_id=self.plan_dir.name,
            run_revision=self.source_revision,
            observation_type="coherence",
            source="megaplan.authority.coherence",
            evidence_ids=tuple(
                f"{source.source_id}:{source.sha256}"
                for source in self.sources
                if source.sha256 is not None
            ),
            payload=self.payload,
            coherence_state=self.coherence_state,
            terminal_state=terminal_state,
            dispatch_state=dispatch_state,
            collection_id=self.collection_id,
            captured_at=self.captured_at,
            source_revision=self.source_revision,
            source_cursor=self.source_cursor,
            source_digests=self.source_digests,
            coherence_reasons=self.coherence_reasons,
            extensions={"metadata": self.metadata()},
        )


DEFAULT_COHERENCE_SOURCES: tuple[CoherenceSource, ...] = (
    CoherenceSource("state", "state.json"),
    CoherenceSource("events", "events.ndjson"),
    CoherenceSource("finalize_projection", "finalize.json"),
    CoherenceSource("completion_verdict", "completion_verdict.json", required=False),
)

SourceReader = Callable[[Path, CoherenceSource], CapturedSource]


def _capture_source(plan_dir: Path, source: CoherenceSource) -> CapturedSource:
    path = plan_dir / source.relative_path
    try:
        if not path.exists():
            return CapturedSource(
                source.source_id,
                source.relative_path,
                path,
                source.required,
                False,
                None,
                None,
                None,
                None,
                "missing",
            )
        data = path.read_bytes()
        stat = path.stat()
    except OSError as exc:
        return CapturedSource(
            source.source_id,
            source.relative_path,
            path,
            source.required,
            False,
            None,
            None,
            None,
            None,
            f"unreadable: {type(exc).__name__}: {exc}",
        )
    return CapturedSource(
        source.source_id,
        source.relative_path,
        path,
        source.required,
        True,
        data,
        len(data),
        stat.st_mtime_ns,
        _sha256(data),
    )


def _capture_all(
    plan_dir: Path,
    sources: Sequence[CoherenceSource],
    *,
    source_reader: SourceReader,
) -> tuple[CapturedSource, ...]:
    return tuple(source_reader(plan_dir, source) for source in sources)


def _signatures(
    captured: Sequence[CapturedSource],
) -> tuple[tuple[str, str, bool, int | None, int | None, str | None, str], ...]:
    return tuple(source.stable_signature for source in sorted(captured, key=lambda item: item.source_id))


def _parse_json(source: CapturedSource, reasons: list[str]) -> Any | None:
    if source.data is None:
        if source.required:
            reasons.append(f"{source.source_id}_missing")
        return None
    try:
        return json.loads(source.data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        reasons.append(f"{source.source_id}_invalid_json:{type(exc).__name__}")
        return None


def _parse_events(source: CapturedSource, reasons: list[str]) -> tuple[list[dict[str, Any]], int | None]:
    events: list[dict[str, Any]] = []
    if source.data is None:
        if source.required:
            reasons.append("events_missing")
        return events, None
    try:
        lines = source.data.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        reasons.append(f"events_invalid_utf8:{type(exc).__name__}")
        return events, None
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            reasons.append(f"events_invalid_json_line:{line_number}")
            continue
        if not isinstance(value, dict):
            reasons.append(f"events_non_object_line:{line_number}")
            continue
        events.append(value)
    seqs = [event.get("seq") for event in events if isinstance(event.get("seq"), int)]
    if len(seqs) != len(set(seqs)):
        reasons.append("events_duplicate_seq")
    if seqs != sorted(seqs):
        reasons.append("events_out_of_order_seq")
    if seqs and sorted(seqs) != list(range(min(seqs), max(seqs) + 1)):
        reasons.append("events_seq_gap")
    return events, max(seqs) if seqs else None


def _reduce_capture(
    plan_dir: Path,
    *,
    captured_at: str,
    sources: Sequence[CapturedSource],
    attempts: int,
    phase1_signatures: tuple[tuple[str, str, bool, int | None, int | None, str | None, str], ...],
    phase2_signatures: tuple[tuple[str, str, bool, int | None, int | None, str | None, str], ...],
    unstable: bool,
) -> CoherentCapture:
    reasons: list[str] = []
    source_by_id = {source.source_id: source for source in sources}
    if unstable:
        reasons.append("source_changed_during_two_phase_capture")
    for source in sources:
        if source.error and (source.required or source.error != "missing"):
            reasons.append(f"{source.source_id}_{source.error.replace(' ', '_')}")

    state = _parse_json(source_by_id["state"], reasons) if "state" in source_by_id else None
    finalize = (
        _parse_json(source_by_id["finalize_projection"], reasons)
        if "finalize_projection" in source_by_id
        else None
    )
    if "completion_verdict" in source_by_id:
        _parse_json(source_by_id["completion_verdict"], reasons)
    events, source_cursor = (
        _parse_events(source_by_id["events"], reasons)
        if "events" in source_by_id
        else ([], None)
    )
    folded = fold_events(events)
    if folded and isinstance(state, Mapping) and dict(state) != folded:
        reasons.append("state_events_projection_mismatch")
    if finalize is not None and not isinstance(finalize, Mapping):
        reasons.append("finalize_projection_not_object")
    if state is not None and not isinstance(state, Mapping):
        reasons.append("state_not_object")

    incoherent_reasons = {
        "source_changed_during_two_phase_capture",
        "state_events_projection_mismatch",
        "events_duplicate_seq",
        "events_out_of_order_seq",
        "events_seq_gap",
    }
    coherence_state = (
        "INCOHERENT"
        if any(reason in incoherent_reasons for reason in reasons)
        else ("DEGRADED" if reasons else "COHERENT")
    )
    source_digests = {
        source.source_id: source.sha256
        for source in sorted(sources, key=lambda item: item.source_id)
        if source.sha256 is not None
    }
    revision_payload = {
        "sources": source_digests,
        "cursor": source_cursor,
        "coherence_state": coherence_state,
        "reasons": sorted(set(reasons)),
    }
    source_revision = _canonical_hash(revision_payload)
    payload = {
        "schema_version": COHERENCE_SCHEMA_VERSION,
        "plan": plan_dir.name,
        "coherence_state": coherence_state,
        "source_revision": source_revision,
        "source_cursor": source_cursor,
        "source_digests": source_digests,
        "coherence_reasons": sorted(set(reasons)),
        "captured_sources": {source.source_id: source.metadata() for source in sources},
    }
    collection_id = "coherent-capture:" + hashlib.sha256(
        json.dumps(
            {
                "captured_at": captured_at,
                "plan_dir": str(plan_dir),
                "source_revision": source_revision,
                "attempts": attempts,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return CoherentCapture(
        plan_dir=plan_dir,
        collection_id=collection_id,
        captured_at=captured_at,
        coherence_state=coherence_state,
        source_revision=source_revision,
        source_cursor=source_cursor,
        source_digests=source_digests,
        coherence_reasons=tuple(reasons),
        sources=tuple(sources),
        attempts=attempts,
        phase1_signatures=phase1_signatures,
        phase2_signatures=phase2_signatures,
        payload=payload,
    )


def capture_authority_coherence(
    plan_dir: str | Path,
    *,
    sources: Sequence[CoherenceSource] = DEFAULT_COHERENCE_SOURCES,
    captured_at: str | None = None,
    max_attempts: int = 2,
    source_reader: SourceReader = _capture_source,
) -> CoherentCapture:
    """Capture authority inputs with two stable read phases before reduction.

    The function performs no projection materialization or recovery.  It reads
    source bytes and filesystem metadata first, compares a second read phase,
    retries if allowed, and only then parses the captured bytes.
    """

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    plan_path = Path(plan_dir)
    captured_at_value = captured_at or _now()
    last_first: tuple[CapturedSource, ...] = ()
    last_second: tuple[CapturedSource, ...] = ()
    last_first_signature: tuple[tuple[str, str, bool, int | None, int | None, str | None, str], ...] = ()
    last_second_signature: tuple[tuple[str, str, bool, int | None, int | None, str | None, str], ...] = ()
    for attempt in range(1, max_attempts + 1):
        first = _capture_all(plan_path, sources, source_reader=source_reader)
        second = _capture_all(plan_path, sources, source_reader=source_reader)
        first_signature = _signatures(first)
        second_signature = _signatures(second)
        last_first = first
        last_second = second
        last_first_signature = first_signature
        last_second_signature = second_signature
        if first_signature == second_signature:
            return _reduce_capture(
                plan_path,
                captured_at=captured_at_value,
                sources=first,
                attempts=attempt,
                phase1_signatures=first_signature,
                phase2_signatures=second_signature,
                unstable=False,
            )
    return _reduce_capture(
        plan_path,
        captured_at=captured_at_value,
        sources=last_second or last_first,
        attempts=max_attempts,
        phase1_signatures=last_first_signature,
        phase2_signatures=last_second_signature,
        unstable=True,
    )


__all__ = [
    "COHERENCE_SCHEMA_VERSION",
    "DEFAULT_COHERENCE_SOURCES",
    "CapturedSource",
    "CoherenceSource",
    "CoherentCapture",
    "capture_authority_coherence",
]
