"""Immutable, cursor-addressed evidence coordinates for C2 shadow evaluation.

Evidence authority is a replay coordinate, never a wall-clock interval.  The
records here are neutral and non-authoritative.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Mapping, Sequence

from arnold.workflow.completion.hashing import hash_canonical


_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
_CLOCK_KEY = re.compile(
    r"(?:^|_)(?:time|timestamp|created|updated|expires?|deadline|duration)(?:$|_)",
    re.I,
)
_ISO_CLOCK = re.compile(r"^\d{4}-\d{2}-\d{2}(?:$|[T ]\d{2}:\d{2})")


class EvidenceScopeMismatch(ValueError):
    """Raised when a candidate evidence coordinate is outside the scope."""

    def __init__(self, fields: Sequence[str]):
        self.fields = tuple(fields)
        super().__init__("evidence scope mismatch: " + ", ".join(self.fields))


def _reject_clock(value: Any, field: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{field} must be finite")
    if isinstance(value, str) and _ISO_CLOCK.match(value.strip()):
        raise ValueError(f"{field} cannot use wall-clock time as evidence authority")
    if isinstance(value, Mapping):
        for key, item in value.items():
            name = str(key)
            if _CLOCK_KEY.search(name):
                raise ValueError(f"{field}.{name} cannot be wall-clock authority")
            _reject_clock(item, f"{field}.{name}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, item in enumerate(value):
            _reject_clock(item, f"{field}[{index}]")


def _freeze(value: Any, field: str) -> Any:
    _reject_clock(value, field)
    if isinstance(value, Mapping):
        return tuple(sorted((str(k), _freeze(v, f"{field}.{k}")) for k, v in value.items()))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(_freeze(item, f"{field}[]") for item in value)
    if isinstance(value, (str, int, bool, float)) or value is None:
        return value
    raise TypeError(f"{field} must be JSON-like")


def _thaw(value: Any) -> Any:
    if isinstance(value, tuple):
        if all(isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str) for item in value):
            return {key: _thaw(item) for key, item in value}
        return [_thaw(item) for item in value]
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    _reject_clock(value, field)
    return value.strip()


def _digest(value: str, field: str) -> None:
    if not _HASH.fullmatch(value):
        raise ValueError(f"{field} must be a sha256: digest")


@dataclass(frozen=True, init=False)
class ScalarCursor:
    """One ordinal or opaque cursor coordinate with boundary semantics."""

    value: int | str
    inclusive: bool
    stream_id: str
    cursor_hash: str

    def __init__(self, value: Any = None, inclusive: bool = True, stream_id: str = "", cursor_hash: str = "", *, position: Any = None, sequence: Any = None, ordinal: Any = None, index: Any = None, stream: str | None = None) -> None:
        values = [item for item in (value, position, sequence, ordinal, index) if item is not None]
        if len({repr(item) for item in values}) > 1:
            raise ValueError("ScalarCursor received conflicting value aliases")
        chosen = values[0] if values else None
        if isinstance(chosen, bool) or not isinstance(chosen, (int, str)):
            raise ValueError("ScalarCursor.value must be a non-negative ordinal or opaque token")
        if isinstance(chosen, int) and chosen < 0:
            raise ValueError("ScalarCursor.value must be non-negative")
        if isinstance(chosen, str) and not chosen.strip():
            raise ValueError("ScalarCursor.value must be non-empty")
        _reject_clock(chosen, "ScalarCursor.value")
        if not isinstance(inclusive, bool):
            raise TypeError("ScalarCursor.inclusive must be bool")
        actual_stream = stream if stream is not None else stream_id
        object.__setattr__(self, "value", chosen)
        object.__setattr__(self, "inclusive", inclusive)
        object.__setattr__(self, "stream_id", str(actual_stream))
        expected = hash_canonical({"value": chosen, "inclusive": inclusive, "stream_id": actual_stream})
        if cursor_hash and cursor_hash != expected:
            raise ValueError("ScalarCursor cursor_hash mismatch")
        object.__setattr__(self, "cursor_hash", expected)

    @property
    def position(self) -> int | str:
        return self.value

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "inclusive": self.inclusive, "stream_id": self.stream_id, "cursor_hash": self.cursor_hash}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ScalarCursor":
        return cls(data.get("value", data.get("position", data.get("sequence"))), bool(data.get("inclusive", True)), str(data.get("stream_id", data.get("stream", ""))), str(data.get("cursor_hash", "")))


@dataclass(frozen=True, init=False)
class CursorVector:
    """An ordered, named vector of scalar cursors."""

    coordinates: tuple[tuple[str, ScalarCursor], ...]
    inclusive: bool
    vector_hash: str

    def __init__(self, coordinates: Any = None, inclusive: bool = True, vector_hash: str = "", *, values: Any = None, entries: Any = None, cursors: Any = None) -> None:
        supplied = [item for item in (coordinates, values, entries, cursors) if item is not None]
        if len(supplied) > 1 and any(repr(item) != repr(supplied[0]) for item in supplied[1:]):
            raise ValueError("CursorVector received conflicting coordinate aliases")
        raw = supplied[0] if supplied else None
        if isinstance(raw, Mapping):
            pairs = [(str(key), item) for key, item in sorted(raw.items(), key=lambda pair: str(pair[0]))]
        elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            pairs = [(str(key), item) for key, item in raw]
        else:
            raise ValueError("CursorVector.coordinates must be a mapping or ordered pairs")
        if not pairs or len({key for key, _ in pairs}) != len(pairs) or any(not key for key, _ in pairs):
            raise ValueError("CursorVector coordinates must be non-empty and unique")
        normalized = tuple((key, item if isinstance(item, ScalarCursor) else ScalarCursor(item, inclusive=inclusive, stream_id=key)) for key, item in pairs)
        if not isinstance(inclusive, bool):
            raise TypeError("CursorVector.inclusive must be bool")
        object.__setattr__(self, "coordinates", normalized)
        object.__setattr__(self, "inclusive", inclusive)
        payload = {"coordinates": [{"name": key, "cursor": item.to_dict()} for key, item in normalized], "inclusive": inclusive}
        expected = hash_canonical(payload)
        if vector_hash and vector_hash != expected:
            raise ValueError("CursorVector vector_hash mismatch")
        object.__setattr__(self, "vector_hash", expected)

    @property
    def values(self) -> tuple[tuple[str, ScalarCursor], ...]:
        return self.coordinates

    @property
    def cursor_vector_hash(self) -> str:
        return self.vector_hash

    def __getitem__(self, name: str) -> ScalarCursor:
        return dict(self.coordinates)[name]

    def to_dict(self) -> dict[str, Any]:
        return {"coordinates": {key: item.to_dict() for key, item in self.coordinates}, "inclusive": self.inclusive, "vector_hash": self.vector_hash}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CursorVector":
        raw = data.get("coordinates", data.get("values", data.get("cursors", {})))
        pairs = [(str(key), ScalarCursor.from_dict(item) if isinstance(item, Mapping) else item) for key, item in raw.items()] if isinstance(raw, Mapping) else raw
        return cls(pairs, bool(data.get("inclusive", True)), str(data.get("vector_hash", data.get("cursor_vector_hash", ""))))


ScalarCursorVector = CursorVector
VectorCursor = CursorVector
OrderedScalarCursor = ScalarCursor
OrderedCursorVector = CursorVector


def _coerce_cursor(value: Any) -> ScalarCursor | CursorVector:
    if isinstance(value, (ScalarCursor, CursorVector)):
        return value
    if isinstance(value, Mapping):
        return CursorVector.from_dict(value) if any(key in value for key in ("coordinates", "values", "cursors")) else ScalarCursor.from_dict(value)
    return ScalarCursor(value)


def _cursor_value(value: ScalarCursor | CursorVector) -> Any:
    return value.value if isinstance(value, ScalarCursor) else tuple((key, item.value) for key, item in value.coordinates)


def _compare(left: ScalarCursor | CursorVector, right: ScalarCursor | CursorVector) -> int:
    if type(left) is not type(right):
        raise ValueError("evidence window endpoints must use one cursor kind")
    if isinstance(left, CursorVector) and tuple(key for key, _ in left.coordinates) != tuple(key for key, _ in right.coordinates):
        raise ValueError("evidence window vector coordinates must match in order")
    try:
        return (_cursor_value(left) > _cursor_value(right)) - (_cursor_value(left) < _cursor_value(right))
    except TypeError as exc:
        raise ValueError("cursor values must be comparable") from exc


@dataclass(frozen=True, init=False)
class EvidenceWindow:
    """A cursor-bounded window with explicit inclusive/exclusive ends."""

    start_cursor: ScalarCursor | CursorVector
    end_cursor: ScalarCursor | CursorVector
    start_inclusive: bool
    end_inclusive: bool
    window_hash: str

    def __init__(self, start_cursor: Any = None, end_cursor: Any = None, start_inclusive: bool = True, end_inclusive: bool = False, window_hash: str = "", *, start: Any = None, end: Any = None, lower: Any = None, upper: Any = None, lower_inclusive: bool | None = None, upper_inclusive: bool | None = None) -> None:
        starts = [item for item in (start_cursor, start, lower) if item is not None]
        ends = [item for item in (end_cursor, end, upper) if item is not None]
        if not starts or not ends:
            raise ValueError("EvidenceWindow requires start and end cursors")
        if any(repr(item) != repr(starts[0]) for item in starts[1:]) or any(repr(item) != repr(ends[0]) for item in ends[1:]):
            raise ValueError("EvidenceWindow received conflicting boundary aliases")
        left, right = _coerce_cursor(starts[0]), _coerce_cursor(ends[0])
        start_inclusive = lower_inclusive if lower_inclusive is not None else start_inclusive
        end_inclusive = upper_inclusive if upper_inclusive is not None else end_inclusive
        if not isinstance(start_inclusive, bool) or not isinstance(end_inclusive, bool):
            raise TypeError("EvidenceWindow boundary flags must be bool")
        comparison = _compare(left, right)
        if comparison > 0 or (comparison == 0 and not (start_inclusive and end_inclusive)):
            raise ValueError("EvidenceWindow cursors are unordered or empty")
        object.__setattr__(self, "start_cursor", left)
        object.__setattr__(self, "end_cursor", right)
        object.__setattr__(self, "start_inclusive", start_inclusive)
        object.__setattr__(self, "end_inclusive", end_inclusive)
        expected = hash_canonical(self._hash_payload())
        if window_hash and window_hash != expected:
            raise ValueError("EvidenceWindow window_hash mismatch")
        object.__setattr__(self, "window_hash", expected)

    def _hash_payload(self) -> dict[str, Any]:
        return {"start_cursor": self.start_cursor.to_dict(), "end_cursor": self.end_cursor.to_dict(), "start_inclusive": self.start_inclusive, "end_inclusive": self.end_inclusive}

    @property
    def lower(self) -> ScalarCursor | CursorVector:
        return self.start_cursor

    @property
    def upper(self) -> ScalarCursor | CursorVector:
        return self.end_cursor

    def contains(self, cursor: Any) -> bool:
        candidate = _coerce_cursor(cursor)
        left, right = _compare(self.start_cursor, candidate), _compare(candidate, self.end_cursor)
        return left <= 0 and right <= 0 and (left < 0 or self.start_inclusive) and (right < 0 or self.end_inclusive)

    def to_dict(self) -> dict[str, Any]:
        return {**self._hash_payload(), "window_hash": self.window_hash}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EvidenceWindow":
        return cls(data.get("start_cursor", data.get("start", data.get("lower"))), data.get("end_cursor", data.get("end", data.get("upper"))), bool(data.get("start_inclusive", data.get("lower_inclusive", True))), bool(data.get("end_inclusive", data.get("upper_inclusive", False))), str(data.get("window_hash", "")))


EvidenceWindowRecord = EvidenceWindow


def _identifier(value: Any, key: str) -> Any:
    if isinstance(value, Mapping):
        return value.get("id", value.get(key, value.get("identity", value.get("store_identity"))))
    return getattr(value, "id", value)


def _mapping_value(value: Any, *keys: str) -> Any:
    if isinstance(value, Mapping):
        return next((value[key] for key in keys if key in value), None)
    return None


def _choose(direct: Any, *aliases: Any) -> Any:
    values = [item for item in (direct, *aliases) if item is not None]
    if values and any(repr(item) != repr(values[0]) for item in values[1:]):
        raise ValueError("EvidenceScope received conflicting coordinate aliases")
    return values[0] if values else None


def _scope_inputs(subject_id: Any, occurrence_id: Any, attempt_id: Any, generation: Any, source_lock: Any, runtime_lock: Any, dependency_lock: Any, store_id: Any, store_incarnation: Any, restore_id: Any, restore_generation: Any, evidence_window: Any, custody: Any, authority_fence: Any, epoch: Any, wbc_version: Any, child_digest: Any, *, subject: Any, occurrence: Any, attempt: Any, generation_id: Any, locks: Any, runtime: Any, dependency: Any, store: Any, incarnation: Any, restore: Any, restore_identity: Any, window: Any, cursor_window: Any, fence: Any, child_set_digest: Any, wbc: Any) -> dict[str, Any]:
    restore_source = restore if restore is not None else restore_identity
    return {
        "subject_id": _choose(subject_id, _identifier(subject, "subject_id")),
        "occurrence_id": _choose(occurrence_id, _identifier(occurrence, "occurrence_id")),
        "attempt_id": _choose(attempt_id, _identifier(attempt, "attempt_id")),
        "generation": _choose(generation, generation_id),
        "source_lock": _choose(source_lock, _mapping_value(locks, "source", "source_lock")),
        "runtime_lock": _choose(runtime_lock, _mapping_value(locks, "runtime", "runtime_lock"), runtime),
        "dependency_lock": _choose(dependency_lock, _mapping_value(locks, "dependency", "dependency_lock"), dependency),
        "store_id": _choose(store_id, _identifier(store, "store_id")),
        "store_incarnation": _choose(store_incarnation, incarnation, _mapping_value(store, "incarnation", "store_incarnation")),
        "restore_id": _choose(restore_id, _identifier(restore_source, "restore_id")),
        "restore_generation": _choose(restore_generation, _mapping_value(restore_source, "generation", "restore_generation")),
        "evidence_window": next((item for item in (evidence_window, window, cursor_window) if item is not None), None),
        "custody": custody,
        "authority_fence": _choose(authority_fence, fence),
        "epoch": epoch,
        "wbc_version": _choose(wbc_version, wbc),
        "admitted_child_set_digest": _choose(child_digest, child_set_digest),
    }


@dataclass(frozen=True, init=False)
class EvidenceScope:
    """Complete immutable subject/replay/store/custody evidence coordinates."""

    subject_id: str
    occurrence_id: str
    attempt_id: str
    generation: int
    source_lock: str
    runtime_lock: str
    dependency_lock: str
    store_id: str
    store_incarnation: str
    restore_id: str
    restore_generation: int
    evidence_window: EvidenceWindow
    custody: Any
    authority_fence: Any
    epoch: int
    wbc_version: str
    admitted_child_set_digest: str
    binding_hash: str
    schema_version: str
    scope_hash: str

    def __init__(self, subject_id: Any = None, occurrence_id: Any = None, attempt_id: Any = None, generation: Any = None, source_lock: Any = None, runtime_lock: Any = None, dependency_lock: Any = None, store_id: Any = None, store_incarnation: Any = None, restore_id: Any = None, restore_generation: Any = None, evidence_window: Any = None, custody: Any = None, authority_fence: Any = None, epoch: Any = None, wbc_version: Any = None, admitted_child_set_digest: Any = None, binding_hash: str = "", schema_version: str = "arnold.workflow.completion_evidence_scope.v1", scope_hash: str = "", *, subject: Any = None, occurrence: Any = None, attempt: Any = None, generation_id: Any = None, locks: Any = None, runtime: Any = None, dependency: Any = None, store: Any = None, store_identity: Any = None, incarnation: Any = None, restore: Any = None, restore_identity: Any = None, window: Any = None, cursor_window: Any = None, fence: Any = None, child_set_digest: Any = None, custody_coordinates: Any = None, authority_epoch: Any = None, wbc: Any = None) -> None:
        store = _choose(store, store_identity)
        custody = _choose(custody, custody_coordinates)
        epoch = _choose(epoch, authority_epoch)
        values = _scope_inputs(subject_id, occurrence_id, attempt_id, generation, source_lock, runtime_lock, dependency_lock, store_id, store_incarnation, restore_id, restore_generation, evidence_window, custody, authority_fence, epoch, wbc_version, admitted_child_set_digest, subject=subject, occurrence=occurrence, attempt=attempt, generation_id=generation_id, locks=locks, runtime=runtime, dependency=dependency, store=store, incarnation=incarnation, restore=restore, restore_identity=restore_identity, window=window, cursor_window=cursor_window, fence=fence, child_set_digest=child_set_digest, wbc=wbc)
        if isinstance(values["evidence_window"], Mapping):
            values["evidence_window"] = EvidenceWindow.from_dict(values["evidence_window"])
        if not isinstance(values["evidence_window"], EvidenceWindow):
            raise ValueError("EvidenceScope requires a cursor-bounded evidence_window")
        for name in ("subject_id", "occurrence_id", "attempt_id", "source_lock", "runtime_lock", "dependency_lock", "store_id", "store_incarnation", "restore_id", "wbc_version", "admitted_child_set_digest"):
            values[name] = _text(values[name], f"EvidenceScope.{name}")
        for name in ("generation", "restore_generation", "epoch"):
            if isinstance(values[name], bool) or not isinstance(values[name], int) or values[name] < 0:
                raise ValueError(f"EvidenceScope.{name} must be a non-negative integer")
        if not schema_version.startswith("arnold.workflow.completion_evidence_scope."):
            raise ValueError("EvidenceScope.schema_version is unsupported")
        if binding_hash:
            _digest(binding_hash, "EvidenceScope.binding_hash")
        custody, fence = _freeze(values["custody"], "EvidenceScope.custody"), _freeze(values["authority_fence"], "EvidenceScope.authority_fence")
        if custody is None or fence is None:
            raise ValueError("EvidenceScope custody and authority_fence are required")
        for name, value in values.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "custody", custody)
        object.__setattr__(self, "authority_fence", fence)
        object.__setattr__(self, "binding_hash", binding_hash)
        object.__setattr__(self, "schema_version", schema_version)
        expected = hash_canonical(self._hash_payload())
        if scope_hash and scope_hash != expected:
            raise ValueError("EvidenceScope scope_hash mismatch")
        object.__setattr__(self, "scope_hash", expected)

    def _hash_payload(self) -> dict[str, Any]:
        return {"subject_id": self.subject_id, "occurrence_id": self.occurrence_id, "attempt_id": self.attempt_id, "generation": self.generation, "source_lock": self.source_lock, "runtime_lock": self.runtime_lock, "dependency_lock": self.dependency_lock, "store_id": self.store_id, "store_incarnation": self.store_incarnation, "restore_id": self.restore_id, "restore_generation": self.restore_generation, "evidence_window": self.evidence_window.to_dict(), "custody": _thaw(self.custody), "authority_fence": _thaw(self.authority_fence), "epoch": self.epoch, "wbc_version": self.wbc_version, "admitted_child_set_digest": self.admitted_child_set_digest, "binding_hash": self.binding_hash, "schema_version": self.schema_version}

    @property
    def hash(self) -> str:
        return self.scope_hash

    @property
    def child_set_digest(self) -> str:
        return self.admitted_child_set_digest

    @property
    def generation_id(self) -> int:
        return self.generation

    @property
    def subject(self) -> str:
        return self.subject_id

    @property
    def occurrence(self) -> str:
        return self.occurrence_id

    @property
    def attempt(self) -> str:
        return self.attempt_id

    @property
    def store_identity(self) -> str:
        return self.store_id

    @property
    def restore_identity(self) -> str:
        return self.restore_id

    @property
    def custody_coordinates(self) -> Any:
        return _thaw(self.custody)

    @property
    def cursor_window(self) -> EvidenceWindow:
        return self.evidence_window

    @property
    def fence(self) -> Any:
        return _thaw(self.authority_fence)

    def to_dict(self) -> dict[str, Any]:
        return {**self._hash_payload(), "scope_hash": self.scope_hash}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EvidenceScope":
        locks = data.get("locks") if isinstance(data.get("locks"), Mapping) else None
        return cls(subject_id=data.get("subject_id", data.get("subject")), occurrence_id=data.get("occurrence_id", data.get("occurrence")), attempt_id=data.get("attempt_id", data.get("attempt")), generation=data.get("generation"), source_lock=data.get("source_lock"), runtime_lock=data.get("runtime_lock"), dependency_lock=data.get("dependency_lock"), store_id=data.get("store_id", data.get("store")), store_incarnation=data.get("store_incarnation", data.get("incarnation")), restore_id=data.get("restore_id", data.get("restore_identity")), restore_generation=data.get("restore_generation"), evidence_window=data.get("evidence_window", data.get("window")), custody=data.get("custody"), authority_fence=data.get("authority_fence", data.get("fence")), epoch=data.get("epoch"), wbc_version=data.get("wbc_version", data.get("wbc")), admitted_child_set_digest=data.get("admitted_child_set_digest", data.get("child_set_digest")), binding_hash=str(data.get("binding_hash", "")), schema_version=str(data.get("schema_version", "arnold.workflow.completion_evidence_scope.v1")), scope_hash=str(data.get("scope_hash", data.get("evidence_scope_hash", ""))), locks=locks)


EvidenceCoordinates = EvidenceScope


def scope_mismatches(expected: EvidenceScope, candidate: EvidenceScope | Mapping[str, Any]) -> tuple[str, ...]:
    actual = candidate if isinstance(candidate, EvidenceScope) else EvidenceScope.from_dict(candidate)
    fields = ("subject_id", "occurrence_id", "attempt_id", "generation", "source_lock", "runtime_lock", "dependency_lock", "store_id", "store_incarnation", "restore_id", "restore_generation", "evidence_window", "custody", "authority_fence", "epoch", "wbc_version", "admitted_child_set_digest", "binding_hash", "schema_version")
    return tuple(field for field in fields if getattr(expected, field) != getattr(actual, field))


def validate_evidence_scope(expected: EvidenceScope, candidate: EvidenceScope | Mapping[str, Any], *, binding_hash: str | None = None, cursor: Any = None) -> None:
    actual = candidate if isinstance(candidate, EvidenceScope) else EvidenceScope.from_dict(candidate)
    fields = list(scope_mismatches(expected, actual))
    if binding_hash is not None and binding_hash != expected.binding_hash:
        fields.append("binding_hash")
    if cursor is not None and not expected.evidence_window.contains(cursor):
        fields.append("cursor")
    if fields:
        raise EvidenceScopeMismatch(tuple(dict.fromkeys(fields)))


def admit_evidence(expected: EvidenceScope, candidate: EvidenceScope | Mapping[str, Any], *, binding_hash: str | None = None, cursor: Any = None) -> bool:
    validate_evidence_scope(expected, candidate, binding_hash=binding_hash, cursor=cursor)
    return True


def validate_scope(expected: EvidenceScope, candidate: EvidenceScope | Mapping[str, Any], **kwargs: Any) -> None:
    validate_evidence_scope(expected, candidate, **kwargs)


def scope_matches(expected: EvidenceScope, candidate: EvidenceScope | Mapping[str, Any]) -> bool:
    try:
        validate_evidence_scope(expected, candidate)
    except (EvidenceScopeMismatch, ValueError, TypeError):
        return False
    return True


def make_evidence_scope(**kwargs: Any) -> EvidenceScope:
    return EvidenceScope(**kwargs)


Cursor = ScalarCursor
EvidenceCursor = ScalarCursor
EvidenceCursorVector = CursorVector


def compute_cursor_hash(cursor: ScalarCursor | CursorVector) -> str:
    return cursor.cursor_hash if isinstance(cursor, ScalarCursor) else cursor.vector_hash


def compute_evidence_window_hash(window: EvidenceWindow) -> str:
    return window.window_hash


def compute_window_hash(window: EvidenceWindow) -> str:
    return compute_evidence_window_hash(window)


def compute_evidence_scope_hash(scope: EvidenceScope) -> str:
    return scope.scope_hash


def compute_scope_hash(scope: EvidenceScope) -> str:
    return compute_evidence_scope_hash(scope)


__all__ = ["EvidenceCoordinates", "EvidenceScope", "EvidenceScopeMismatch", "EvidenceWindow", "EvidenceWindowRecord", "ScalarCursor", "Cursor", "EvidenceCursor", "CursorVector", "VectorCursor", "EvidenceCursorVector", "OrderedScalarCursor", "OrderedCursorVector", "ScalarCursorVector", "scope_mismatches", "validate_evidence_scope", "validate_scope", "admit_evidence", "scope_matches", "make_evidence_scope", "compute_cursor_hash", "compute_evidence_window_hash", "compute_window_hash", "compute_evidence_scope_hash", "compute_scope_hash"]
