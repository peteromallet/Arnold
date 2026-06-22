"""M4 T23 — EvaluandRecord: versioned verify/judge record.

The verify/judge surface writes a versioned :class:`EvaluandRecord`
into the one Ledger, using the Step 7b R5 join key (``run_id``) — never
a bare float — so a downstream reader can answer "what did we score?"
without recomputation.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, Mapping, Optional, Protocol


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def raw_prompt_sha256(prompt: str) -> str:
    """Return the SHA-256 identity of the exact raw model prompt."""

    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def derive_params_hash(params: Mapping[str, Any] | None) -> str:
    """Return the derived hash of canonical model params."""

    return hashlib.sha256(
        _canonical_json(dict(params or {})).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class ModelIORef:
    """Stable identity key for a recorded model I/O exchange.

    ``params_canonical`` deliberately keeps the raw canonical parameter string
    as key material. ``params_hash`` is derived for quick comparison only.
    """

    model_identity: str
    prompt_sha256: Optional[str]
    params_canonical: str
    params_hash: str

    @property
    def key(self) -> str:
        return hashlib.sha256(
            _canonical_json(self.to_json()).encode("utf-8")
        ).hexdigest()

    def to_json(self) -> dict[str, Any]:
        return {
            "model_identity": self.model_identity,
            "prompt_sha256": self.prompt_sha256,
            "params_canonical": self.params_canonical,
            "params_hash": self.params_hash,
        }

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "ModelIORef":
        return cls(
            model_identity=str(value["model_identity"]),
            prompt_sha256=(
                str(value["prompt_sha256"])
                if value.get("prompt_sha256") is not None
                else None
            ),
            params_canonical=str(value["params_canonical"]),
            params_hash=str(value["params_hash"]),
        )


@dataclass(frozen=True)
class RecordedModelIO:
    """Recorded prompt/response/params payload used for deterministic replay."""

    model_name: Optional[str] = None
    reported_version: Optional[str] = None
    prompt: Optional[str] = None
    response: Optional[str] = None
    params: Mapping[str, Any] = field(default_factory=dict)
    prompt_sha256: Optional[str] = None
    response_sha256: Optional[str] = None
    unavailable_reason: Optional[str] = None
    redacted: bool = False

    @classmethod
    def unavailable(
        cls,
        reason: str,
        *,
        model_name: Optional[str] = None,
        reported_version: Optional[str] = None,
        params: Mapping[str, Any] | None = None,
    ) -> "RecordedModelIO":
        return cls(
            model_name=model_name,
            reported_version=reported_version,
            params=dict(params or {}),
            unavailable_reason=reason,
        )

    @classmethod
    def redacted_payload(
        cls,
        *,
        model_name: Optional[str],
        reported_version: Optional[str] = None,
        prompt_sha256: str,
        response_sha256: Optional[str] = None,
        params: Mapping[str, Any] | None = None,
        reason: str = "redacted",
    ) -> "RecordedModelIO":
        return cls(
            model_name=model_name,
            reported_version=reported_version,
            params=dict(params or {}),
            prompt_sha256=prompt_sha256,
            response_sha256=response_sha256,
            unavailable_reason=reason,
            redacted=True,
        )

    @property
    def params_canonical(self) -> str:
        return _canonical_json(dict(self.params or {}))

    @property
    def params_hash(self) -> str:
        return derive_params_hash(self.params)

    @property
    def model_identity(self) -> str:
        from arnold_pipelines.megaplan.observability.events import compute_model_identity

        return compute_model_identity(self.model_name, self.reported_version)

    def ref(self) -> ModelIORef:
        prompt_hash = (
            self.prompt_sha256
            if self.prompt_sha256 is not None
            else raw_prompt_sha256(self.prompt)
            if self.prompt is not None
            else None
        )
        return ModelIORef(
            model_identity=self.model_identity,
            prompt_sha256=prompt_hash,
            params_canonical=self.params_canonical,
            params_hash=self.params_hash,
        )

    def to_json(self) -> dict[str, Any]:
        prompt_hash = (
            self.prompt_sha256
            if self.prompt_sha256 is not None
            else raw_prompt_sha256(self.prompt)
            if self.prompt is not None
            else None
        )
        response_hash = (
            self.response_sha256
            if self.response_sha256 is not None
            else hashlib.sha256(self.response.encode("utf-8")).hexdigest()
            if self.response is not None
            else None
        )
        return {
            "model_name": self.model_name,
            "reported_version": self.reported_version,
            "model_identity": self.model_identity,
            "prompt": None if self.redacted else self.prompt,
            "response": None if self.redacted else self.response,
            "params": dict(self.params or {}),
            "params_canonical": self.params_canonical,
            "params_hash": self.params_hash,
            "prompt_sha256": prompt_hash,
            "response_sha256": response_hash,
            "unavailable_reason": self.unavailable_reason,
            "redacted": self.redacted,
            "ref": self.ref().to_json(),
        }

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "RecordedModelIO":
        return cls(
            model_name=(
                str(value["model_name"])
                if value.get("model_name") is not None
                else None
            ),
            reported_version=(
                str(value["reported_version"])
                if value.get("reported_version") is not None
                else None
            ),
            prompt=str(value["prompt"]) if value.get("prompt") is not None else None,
            response=(
                str(value["response"]) if value.get("response") is not None else None
            ),
            params=dict(value.get("params") or {}),
            prompt_sha256=(
                str(value["prompt_sha256"])
                if value.get("prompt_sha256") is not None
                else None
            ),
            response_sha256=(
                str(value["response_sha256"])
                if value.get("response_sha256") is not None
                else None
            ),
            unavailable_reason=(
                str(value["unavailable_reason"])
                if value.get("unavailable_reason") is not None
                else None
            ),
            redacted=bool(value.get("redacted", False)),
        )


@dataclass(frozen=True)
class EvaluandRecord:
    """A versioned verify/judge result.

    Fields
    ------
    judge_version:
        Opaque version string of the judge that produced ``score``.
    rubric_version:
        Opaque version string of the rubric being applied.
    input_set_hash:
        Content hash of the input set scored.  Lets the no-recompute read
        confirm a stored record applies to the asked-about input set.
    score:
        The numeric score itself (never written naked — always inside a
        full record).
    recorded_at:
        Wall-clock epoch seconds at write time.
    piece_version:
        Stable identity of the judge piece that emitted this record.  Legacy
        records may omit it; strict attribution rejects those records.
    provenance:
        JSON-friendly source metadata for the recorded judgment.
    taint:
        JSON-friendly taint labels propagated into the judgment.
    model_io_ref / recorded_model_io_ref:
        Optional references to recorded model input/output payloads.
    """

    judge_version: str
    rubric_version: str
    input_set_hash: str
    score: float
    recorded_at: float = field(default_factory=time.time)
    piece_version: Optional[str] = None
    provenance: Dict[str, object] = field(default_factory=dict)
    taint: tuple[str, ...] = field(default_factory=tuple)
    model_io_ref: Optional[str] = None
    recorded_model_io_ref: Optional[str] = None

    def attribution_key(
        self, *, strict: bool = False
    ) -> Optional[tuple[str, str, str, str]]:
        """Return the attribution join key for this record.

        Legacy records created before M5 do not have ``piece_version``.  They
        remain readable through ``_LEDGER`` by run id, but cannot participate
        in strict attribution joins.
        """
        if self.piece_version:
            return (
                self.piece_version,
                self.judge_version,
                self.rubric_version,
                self.input_set_hash,
            )
        if strict:
            raise ValueError("EvaluandRecord attribution requires piece_version")
        return None


@dataclass(frozen=True)
class BetterResult:
    """Pure read-side result for comparing two recorded Evaluand judgments."""

    status: str
    winner_piece_version: Optional[str] = None
    scores: Dict[str, float] = field(default_factory=dict)
    attribution: Dict[str, tuple[str, str, str, str]] = field(default_factory=dict)
    reason: Optional[str] = None


@dataclass(frozen=True)
class ReJudgeOutcome:
    """Result of replaying a recorded model I/O payload through a scorer."""

    status: str
    recorded_io_key: str
    record: Optional[EvaluandRecord] = None
    event: Optional[dict[str, Any]] = None
    reason: Optional[str] = None
    source_attribution_key: Optional[tuple[str, str, str, str]] = None
    new_attribution_key: Optional[tuple[str, str, str, str]] = None


class RecordedIOUnavailable(RuntimeError):
    """Raised by callers that choose exception-style unavailable handling."""


class RecordedIOScorer(Protocol):
    """Explicit replay scorer over recorded model I/O.

    Implementations must be deterministic over the supplied payload. The
    ``re_judge`` helper never constructs or imports a live model client.
    """

    def __call__(self, recorded_io: RecordedModelIO) -> float: ...


class LedgerTarget(Protocol):
    """Minimal event sink shape used by Evaluand persistence."""

    def emit(
        self,
        kind: str,
        *,
        payload: Optional[dict] = None,
        scope: Optional[str] = None,
        phase: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Any:  # pragma: no cover - Protocol
        ...


# In-process Ledger for the verify/judge surface.  Keyed by the R5 join
# key (``run_id``) so the read surface can no-recompute lookup by run.
_LEDGER: Dict[str, EvaluandRecord] = {}


def write_evaluand(run_id: str, record: EvaluandRecord) -> None:
    """Write the versioned record into the one Ledger.

    Raises ``TypeError`` if ``record`` is a bare float — the schema
    invariant the M4 brief locks.
    """
    if not isinstance(record, EvaluandRecord):
        raise TypeError(
            "evaluand write requires a versioned EvaluandRecord, "
            f"not a bare {type(record).__name__}"
        )
    if not run_id:
        raise ValueError("run_id is required for the R5 join key")
    _LEDGER[run_id] = record


def _validate_record(record: EvaluandRecord) -> None:
    if not isinstance(record, EvaluandRecord):
        raise TypeError(
            "evaluand write requires a versioned EvaluandRecord, "
            f"not a bare {type(record).__name__}"
        )


def _json_ref(value: Any) -> Any:
    if isinstance(value, ModelIORef):
        return value.to_json()
    return value


def _evaluand_payload(
    run_id: str,
    record: EvaluandRecord,
    *,
    recorded_model_io: RecordedModelIO | None = None,
) -> dict[str, Any]:
    payload = asdict(record)
    payload["model_io_ref"] = _json_ref(record.model_io_ref)
    payload["recorded_model_io_ref"] = _json_ref(record.recorded_model_io_ref)
    payload["run_id"] = run_id
    payload["attribution_key"] = list(record.attribution_key(strict=True))
    if recorded_model_io is not None:
        io_payload = recorded_model_io.to_json()
        payload["recorded_model_io"] = io_payload
        if payload.get("model_io_ref") is None:
            payload["model_io_ref"] = io_payload["ref"]
        if payload.get("recorded_model_io_ref") is None:
            payload["recorded_model_io_ref"] = io_payload["ref"]
    return payload


def write_evaluand_event(
    run_id: str,
    record: EvaluandRecord,
    *,
    plan_dir: Path | str | None = None,
    event_sink: LedgerTarget | None = None,
    recorded_model_io: RecordedModelIO | None = None,
    phase: Optional[str] = None,
    scope: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> dict | None:
    """Write an attributable Evaluand record through the canonical event ledger.

    When ``plan_dir`` or ``event_sink`` is supplied, the Evaluand event is
    appended before the legacy in-process ``_LEDGER`` cache is updated.  With
    no ledger target, this preserves the old ``write_evaluand`` behavior.
    """
    _validate_record(record)
    if not run_id:
        raise ValueError("run_id is required for the R5 join key")

    if event_sink is None and plan_dir is None:
        write_evaluand(run_id, record)
        return None

    payload = _evaluand_payload(
        run_id,
        record,
        recorded_model_io=recorded_model_io,
    )
    if event_sink is None:
        from arnold_pipelines.megaplan.observability.event_sink import NdjsonBackend

        event_sink = NdjsonBackend(Path(plan_dir))  # type: ignore[arg-type]

    from arnold_pipelines.megaplan.observability.events import EventKind

    event = event_sink.emit(
        EventKind.EVALUAND_RECORDED,
        payload=payload,
        scope=scope,
        phase=phase,
        idempotency_key=idempotency_key,
    )
    _LEDGER[run_id] = record
    return event


def _record_from_event_payload(
    payload: dict[str, Any], *, strict: bool
) -> EvaluandRecord | None:
    def _ref_value(field_name: str) -> Any:
        value = payload.get(field_name)
        if value is None or isinstance(value, (str, dict)):
            return value
        return str(value)

    try:
        record = EvaluandRecord(
            judge_version=str(payload["judge_version"]),
            rubric_version=str(payload["rubric_version"]),
            input_set_hash=str(payload["input_set_hash"]),
            score=float(payload["score"]),
            recorded_at=float(payload.get("recorded_at", time.time())),
            piece_version=(
                str(payload["piece_version"])
                if payload.get("piece_version") is not None
                else None
            ),
            provenance=dict(payload.get("provenance") or {}),
            taint=tuple(payload.get("taint") or ()),
            model_io_ref=_ref_value("model_io_ref"),
            recorded_model_io_ref=_ref_value("recorded_model_io_ref"),
        )
        if record.attribution_key(strict=strict) is None:
            return None
        return record
    except (KeyError, TypeError, ValueError) as exc:
        if strict:
            raise ValueError(f"invalid evaluand_recorded payload: {payload!r}") from exc
        return None


def _model_io_ref_from_value(value: Any) -> ModelIORef | None:
    if isinstance(value, ModelIORef):
        return value
    if isinstance(value, Mapping):
        try:
            return ModelIORef.from_json(value)
        except (KeyError, TypeError, ValueError):
            return None
    return None


def _recorded_io_key_from_payload(payload: Mapping[str, Any]) -> str | None:
    recorded = payload.get("recorded_model_io")
    if isinstance(recorded, Mapping):
        ref = _model_io_ref_from_value(recorded.get("ref"))
        if ref is not None:
            return ref.key

    for field_name in ("recorded_model_io_ref", "model_io_ref"):
        value = payload.get(field_name)
        ref = _model_io_ref_from_value(value)
        if ref is not None:
            return ref.key
        if isinstance(value, str) and value:
            return value
    return None


def _iter_evaluand_event_payloads(plan_dir: Path | str) -> Iterator[dict[str, Any]]:
    from arnold_pipelines.megaplan.observability.events import EventKind, read_events

    for event in read_events(Path(plan_dir), kinds=[EventKind.EVALUAND_RECORDED]):
        payload = event.get("payload")
        if isinstance(payload, dict):
            yield payload


def _source_attribution_key(
    payload: Mapping[str, Any],
) -> Optional[tuple[str, str, str, str]]:
    raw = payload.get("attribution_key")
    if isinstance(raw, (list, tuple)) and len(raw) == 4:
        return tuple(str(item) for item in raw)  # type: ignore[return-value]
    try:
        record = _record_from_event_payload(dict(payload), strict=True)
    except ValueError:
        return None
    if record is None:
        return None
    return record.attribution_key(strict=True)


def re_judge(
    *,
    plan_dir: Path | str,
    recorded_io_key: str,
    scorer: RecordedIOScorer,
    piece_version: str,
    judge_version: str,
    rubric_version: str,
    run_id: Optional[str] = None,
) -> ReJudgeOutcome:
    """Replay recorded model I/O through an explicit scorer and append a record.

    The lookup source is only ``plan_dir/events.ndjson``. No live model client or
    model callback is accepted. Unavailable, redacted, or missing recorded I/O
    returns a typed ``unavailable`` outcome and writes no event.
    """

    if not plan_dir:
        raise ValueError("plan_dir is required for re_judge")
    if not recorded_io_key:
        raise ValueError("recorded_io_key is required for re_judge")
    if scorer is None:
        raise ValueError("scorer is required for re_judge")

    source_payload: dict[str, Any] | None = None
    recorded_payload: Mapping[str, Any] | None = None
    for payload in _iter_evaluand_event_payloads(plan_dir):
        if _recorded_io_key_from_payload(payload) != recorded_io_key:
            continue
        recorded = payload.get("recorded_model_io")
        if isinstance(recorded, Mapping):
            source_payload = payload
            recorded_payload = recorded
            break

    if source_payload is None or recorded_payload is None:
        return ReJudgeOutcome(
            status="unavailable",
            recorded_io_key=recorded_io_key,
            reason="recorded_io_not_found",
        )

    recorded_io = RecordedModelIO.from_json(recorded_payload)
    unavailable_reason = recorded_io.unavailable_reason
    if (
        unavailable_reason
        or recorded_io.redacted
        or recorded_io.prompt is None
        or recorded_io.response is None
    ):
        return ReJudgeOutcome(
            status="unavailable",
            recorded_io_key=recorded_io_key,
            reason=unavailable_reason or "recorded_io_unavailable",
            source_attribution_key=_source_attribution_key(source_payload),
        )

    score = scorer(recorded_io)
    record = EvaluandRecord(
        judge_version=judge_version,
        rubric_version=rubric_version,
        input_set_hash=str(source_payload["input_set_hash"]),
        score=float(score),
        piece_version=piece_version,
        provenance={
            "source": "re_judge",
            "recorded_io_key": recorded_io_key,
            "source_attribution_key": list(
                _source_attribution_key(source_payload) or ()
            ),
        },
        taint=tuple(source_payload.get("taint") or ()),
        model_io_ref=source_payload.get("model_io_ref"),
        recorded_model_io_ref=source_payload.get("recorded_model_io_ref"),
    )
    source_key = _source_attribution_key(source_payload)
    new_key = record.attribution_key(strict=True)
    if source_key == new_key:
        raise ValueError("re_judge requires a distinct attribution key")

    event = write_evaluand_event(
        run_id
        or (
            "re-judge:"
            + hashlib.sha256(
                f"{recorded_io_key}\x00{time.time_ns()}".encode("utf-8")
            ).hexdigest()
        ),
        record,
        plan_dir=plan_dir,
        recorded_model_io=recorded_io,
        phase="re_judge",
        scope="evaluand",
        idempotency_key=f"re_judge:{recorded_io_key}:{piece_version}:{judge_version}",
    )
    return ReJudgeOutcome(
        status="recorded",
        recorded_io_key=recorded_io_key,
        record=record,
        event=event,
        source_attribution_key=source_key,
        new_attribution_key=new_key,
    )


def _undetermined(
    reason: str,
    *,
    scores: Optional[Dict[str, float]] = None,
    attribution: Optional[Dict[str, tuple[str, str, str, str]]] = None,
) -> BetterResult:
    return BetterResult(
        status="undetermined",
        scores=dict(scores or {}),
        attribution=dict(attribution or {}),
        reason=reason,
    )


def better(
    piece_a_version: str,
    piece_b_version: str,
    *,
    plan_dir: Path | str | None = None,
    judge_version: str,
    rubric_version: str,
    input_set_hash: str,
) -> BetterResult:
    """Compare two pieces using only recorded Evaluand events.

    No judge/model callback is accepted.  The comparison is a pure fold over
    ``plan_dir/events.ndjson`` via :func:`read_evaluand_events`.
    """
    if plan_dir is None:
        raise ValueError("plan_dir is required for Evaluand ledger joins")

    key_a = (piece_a_version, judge_version, rubric_version, input_set_hash)
    key_b = (piece_b_version, judge_version, rubric_version, input_set_hash)
    try:
        records = read_evaluand_events(plan_dir, strict=True)
    except ValueError:
        return _undetermined("incomplete_record")

    rec_a = records.get(key_a)
    rec_b = records.get(key_b)
    scores: Dict[str, float] = {}
    attribution: Dict[str, tuple[str, str, str, str]] = {}
    if rec_a is not None:
        scores[piece_a_version] = rec_a.score
        attribution[piece_a_version] = key_a
    if rec_b is not None:
        scores[piece_b_version] = rec_b.score
        attribution[piece_b_version] = key_b

    if rec_a is None or rec_b is None:
        return _undetermined(
            "missing_record",
            scores=scores,
            attribution=attribution,
        )
    if rec_a.score == rec_b.score:
        return _undetermined("tie", scores=scores, attribution=attribution)

    winner = piece_a_version if rec_a.score > rec_b.score else piece_b_version
    return BetterResult(
        status="winner",
        winner_piece_version=winner,
        scores=scores,
        attribution=attribution,
    )


def read_evaluand_events(
    plan_dir: Path | str,
    *,
    strict: bool = True,
) -> dict[tuple[str, str, str, str], EvaluandRecord]:
    """Fold canonical Evaluand events by attribution key in file order.

    Later events with the same attribution key replace earlier records.  This
    reader intentionally ignores the legacy in-process ``_LEDGER`` cache.
    """
    from arnold_pipelines.megaplan.observability.events import EventKind

    ndjson_path = Path(plan_dir) / "events.ndjson"
    folded: dict[tuple[str, str, str, str], EvaluandRecord] = {}
    if not ndjson_path.exists():
        return folded

    with ndjson_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                if strict:
                    raise RuntimeError(
                        "EVALUAND_EVENTS_NDJSON_DECODE_ERROR: "
                        f"path={ndjson_path} line={line_number} err={exc}"
                    ) from exc
                continue
            if not isinstance(event, dict):
                if strict:
                    raise ValueError(
                        "invalid evaluand event envelope: "
                        f"path={ndjson_path} line={line_number}"
                    )
                continue
            if event.get("kind") != EventKind.EVALUAND_RECORDED:
                continue

            payload = event.get("payload")
            if not isinstance(payload, dict):
                if strict:
                    raise ValueError(
                        "invalid evaluand_recorded payload: "
                        f"path={ndjson_path} line={line_number}"
                    )
                continue
            try:
                record = _record_from_event_payload(payload, strict=strict)
            except ValueError as exc:
                raise ValueError(
                    "invalid evaluand_recorded payload: "
                    f"path={ndjson_path} line={line_number}"
                ) from exc
            if record is None:
                continue
            folded[record.attribution_key(strict=True)] = record
    return folded


def read_evaluand(run_id: str) -> Optional[EvaluandRecord]:
    """No-recompute read: return the stored record for ``run_id`` if any."""
    return _LEDGER.get(run_id)


def _reset_for_tests() -> None:
    _LEDGER.clear()
    _PENDING_RECEIPTS.clear()


# ---------------------------------------------------------------------------
# T24 — Evaluand transaction boundary
# ---------------------------------------------------------------------------

# Receipts written within an active boundary; cleared on commit, discarded
# on rollback so the {state, receipt, ledger} triple flips atomically.
_PENDING_RECEIPTS: list[
    tuple[
        str,
        EvaluandRecord,
        Path | str | None,
        LedgerTarget | None,
        Optional[str],
        Optional[str],
        Optional[str],
    ]
] = []


def stage_receipt(
    run_id: str,
    record: EvaluandRecord,
    *,
    plan_dir: Path | str | None = None,
    event_sink: LedgerTarget | None = None,
    phase: Optional[str] = None,
    scope: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> None:
    """Stage a receipt to be committed at the end of the active
    evaluand transaction boundary. Outside a boundary, writes through
    immediately to preserve legacy single-call semantics."""
    if not _IN_BOUNDARY:
        if plan_dir is not None or event_sink is not None:
            write_evaluand_event(
                run_id,
                record,
                plan_dir=plan_dir,
                event_sink=event_sink,
                phase=phase,
                scope=scope,
                idempotency_key=idempotency_key,
            )
        else:
            write_evaluand(run_id, record)
        return
    _validate_record(record)
    _PENDING_RECEIPTS.append(
        (run_id, record, plan_dir, event_sink, phase, scope, idempotency_key)
    )


_IN_BOUNDARY: bool = False


@contextlib.contextmanager
def _evaluand_transaction_boundary(
    envelope: object | None = None,
    *,
    store: object | None = None,
) -> Iterator[None]:
    """T24 — open a transactional boundary around state-merge + receipt
    write. On clean exit, staged receipts commit and the optional
    Store.transaction commits. On exception, staged receipts are
    discarded and the Store rolls back.
    """
    global _IN_BOUNDARY
    epic_id: Optional[str] = None
    if envelope is not None:
        epic_id = getattr(envelope, "epic_id", None)

    prev = _IN_BOUNDARY
    _IN_BOUNDARY = True
    staged_before = len(_PENDING_RECEIPTS)
    if store is not None:
        cm = store.transaction(epic_id=epic_id)
    else:
        cm = contextlib.nullcontext()
    try:
        with cm:
            yield
            # Commit: flush staged receipts into the ledger.
            for (
                run_id,
                record,
                plan_dir,
                event_sink,
                phase,
                scope,
                idempotency_key,
            ) in _PENDING_RECEIPTS[staged_before:]:
                if plan_dir is not None or event_sink is not None:
                    write_evaluand_event(
                        run_id,
                        record,
                        plan_dir=plan_dir,
                        event_sink=event_sink,
                        phase=phase,
                        scope=scope,
                        idempotency_key=idempotency_key,
                    )
                else:
                    _LEDGER[run_id] = record
            del _PENDING_RECEIPTS[staged_before:]
    except BaseException:
        # Rollback: discard staged receipts; Store transaction rolls back
        # via its own __exit__.
        del _PENDING_RECEIPTS[staged_before:]
        raise
    finally:
        _IN_BOUNDARY = prev


__all__ = [
    "EvaluandRecord",
    "BetterResult",
    "better",
    "write_evaluand",
    "write_evaluand_event",
    "read_evaluand_events",
    "read_evaluand",
    "stage_receipt",
]
