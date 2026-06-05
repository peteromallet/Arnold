"""M4 T23 — EvaluandRecord tests."""
from __future__ import annotations

import json
import hashlib

import pytest

from arnold.pipelines.megaplan.observability import (
    BetterResult,
    EvaluandRecord,
    RecordedModelIO,
    ReJudgeOutcome,
    derive_params_hash,
    raw_prompt_sha256,
    re_judge,
)
from arnold.pipelines.megaplan.observability.evaluand import (
    _evaluand_transaction_boundary,
    _reset_for_tests,
    better,
    read_evaluand,
    read_evaluand_events,
    stage_receipt,
    write_evaluand,
    write_evaluand_event,
)
from arnold.pipelines.megaplan.observability.events import (
    EventKind,
    compute_model_identity,
    read_events,
)


@pytest.fixture(autouse=True)
def _clean():
    _reset_for_tests()
    yield
    _reset_for_tests()


def test_write_then_no_recompute_read_returns_record():
    rec = EvaluandRecord(
        judge_version="j-1",
        rubric_version="r-2",
        input_set_hash="abc123",
        score=0.83,
    )
    write_evaluand("run-7", rec)
    out = read_evaluand("run-7")
    assert out is rec
    assert out.score == pytest.approx(0.83)
    assert out.judge_version == "j-1"


def test_legacy_constructor_defaults_attribution_metadata():
    rec = EvaluandRecord("j", "r", "h", 0.0)

    assert rec.judge_version == "j"
    assert rec.rubric_version == "r"
    assert rec.input_set_hash == "h"
    assert rec.score == pytest.approx(0.0)
    assert rec.piece_version is None
    assert rec.provenance == {}
    assert rec.taint == ()
    assert rec.model_io_ref is None
    assert rec.recorded_model_io_ref is None
    assert rec.attribution_key() is None


def test_legacy_five_arg_constructor_still_sets_recorded_at():
    rec = EvaluandRecord("j", "r", "h", 0.0, 123.0)

    assert rec.recorded_at == pytest.approx(123.0)
    assert rec.piece_version is None


def test_attribution_key_requires_piece_version_when_strict():
    rec = EvaluandRecord("j", "r", "h", 0.0)

    with pytest.raises(ValueError, match="piece_version"):
        rec.attribution_key(strict=True)


def test_attribution_key_includes_piece_version_for_new_records():
    rec = EvaluandRecord(
        "judge-v1",
        "rubric-v2",
        "input-hash",
        0.7,
        piece_version="piece-v3",
        provenance={"source": "unit"},
        taint=("trusted",),
        model_io_ref="model-io:1",
        recorded_model_io_ref="recorded-io:1",
    )

    assert rec.attribution_key(strict=True) == (
        "piece-v3",
        "judge-v1",
        "rubric-v2",
        "input-hash",
    )
    assert rec.provenance == {"source": "unit"}
    assert rec.taint == ("trusted",)
    assert rec.model_io_ref == "model-io:1"
    assert rec.recorded_model_io_ref == "recorded-io:1"


def test_recorded_model_io_identity_keeps_raw_canonical_params():
    params = {"temperature": 0, "tools": ["judge"], "top_p": 1}
    io = RecordedModelIO(
        model_name="gpt-5.4",
        reported_version="2026-05-31",
        prompt="score this candidate",
        response='{"score":0.9}',
        params=params,
    )
    payload = io.to_json()
    ref = io.ref()

    assert payload["prompt_sha256"] == raw_prompt_sha256("score this candidate")
    assert payload["response_sha256"] == hashlib.sha256(
        b'{"score":0.9}'
    ).hexdigest()
    assert payload["model_identity"] == compute_model_identity(
        "gpt-5.4", "2026-05-31"
    )
    assert payload["params"] == params
    assert payload["params_canonical"] == (
        '{"temperature":0,"tools":["judge"],"top_p":1}'
    )
    assert payload["params_hash"] == derive_params_hash(params)
    assert ref.to_json()["params_canonical"] == payload["params_canonical"]
    assert ref.to_json()["params_hash"] == payload["params_hash"]


def test_write_evaluand_event_stores_recorded_model_io_payload(tmp_path):
    io = RecordedModelIO(
        model_name="gpt-5.4",
        reported_version="2026-05-31",
        prompt="judge prompt",
        response="judge response",
        params={"temperature": 0, "seed": 7},
    )
    rec = EvaluandRecord(
        "judge-v1",
        "rubric-v1",
        "input-hash",
        0.9,
        piece_version="piece-v1",
    )

    write_evaluand_event("run-io", rec, plan_dir=tmp_path, recorded_model_io=io)

    events = list(read_events(tmp_path, kinds=[EventKind.EVALUAND_RECORDED]))
    assert len(events) == 1
    payload = events[0]["payload"]
    assert payload["recorded_model_io"]["prompt"] == "judge prompt"
    assert payload["recorded_model_io"]["response"] == "judge response"
    assert payload["recorded_model_io"]["params"] == {"temperature": 0, "seed": 7}
    assert payload["recorded_model_io"]["params_canonical"] == (
        '{"seed":7,"temperature":0}'
    )
    assert payload["recorded_model_io"]["params_hash"] == derive_params_hash(
        {"temperature": 0, "seed": 7}
    )
    assert payload["model_io_ref"]["params_canonical"] == (
        '{"seed":7,"temperature":0}'
    )
    assert payload["model_io_ref"]["params_hash"] == payload[
        "recorded_model_io"
    ]["params_hash"]

    folded = read_evaluand_events(tmp_path)
    stored = folded[rec.attribution_key(strict=True)]
    assert stored.model_io_ref["params_hash"] == payload["model_io_ref"][
        "params_hash"
    ]


def test_recorded_model_io_unavailable_legacy_payload_is_explicit(tmp_path):
    io = RecordedModelIO.unavailable(
        "legacy record had no captured model I/O",
        model_name="legacy-model",
        params={"temperature": 0.2},
    )
    rec = EvaluandRecord(
        "judge-v1",
        "rubric-v1",
        "input-hash",
        0.5,
        piece_version="piece-v1",
    )

    write_evaluand_event("run-legacy", rec, plan_dir=tmp_path, recorded_model_io=io)

    payload = list(read_events(tmp_path, kinds=[EventKind.EVALUAND_RECORDED]))[0][
        "payload"
    ]
    recorded = payload["recorded_model_io"]
    assert recorded["prompt"] is None
    assert recorded["response"] is None
    assert recorded["prompt_sha256"] is None
    assert recorded["unavailable_reason"] == "legacy record had no captured model I/O"
    assert recorded["params"] == {"temperature": 0.2}
    assert recorded["params_hash"] == derive_params_hash({"temperature": 0.2})


def test_recorded_model_io_redacted_payload_keeps_hashes_and_params():
    io = RecordedModelIO.redacted_payload(
        model_name="gpt-5.4",
        reported_version="2026-05-31",
        prompt_sha256="p" * 64,
        response_sha256="r" * 64,
        params={"temperature": 0},
        reason="policy redaction",
    )
    payload = io.to_json()

    assert payload["redacted"] is True
    assert payload["prompt"] is None
    assert payload["response"] is None
    assert payload["prompt_sha256"] == "p" * 64
    assert payload["response_sha256"] == "r" * 64
    assert payload["unavailable_reason"] == "policy redaction"
    assert payload["params"] == {"temperature": 0}
    assert payload["ref"]["params_canonical"] == '{"temperature":0}'


def test_re_judge_uses_supplied_scorer_and_appends_distinct_event(tmp_path):
    io = RecordedModelIO(
        model_name="gpt-5.4",
        reported_version="2026-05-31",
        prompt="judge prompt",
        response="judge response",
        params={"temperature": 0},
    )
    original = EvaluandRecord(
        "judge-v1",
        "rubric-v1",
        "input-hash",
        0.9,
        piece_version="piece-v1",
    )
    write_evaluand_event(
        "run-original",
        original,
        plan_dir=tmp_path,
        recorded_model_io=io,
    )
    calls: list[RecordedModelIO] = []

    def scorer(recorded_io: RecordedModelIO) -> float:
        calls.append(recorded_io)
        assert recorded_io.prompt == "judge prompt"
        assert recorded_io.response == "judge response"
        return 0.42

    outcome = re_judge(
        plan_dir=tmp_path,
        recorded_io_key=io.ref().key,
        scorer=scorer,
        piece_version="piece-rejudge",
        judge_version="judge-v2",
        rubric_version="rubric-v2",
        run_id="run-rejudged",
    )

    assert isinstance(outcome, ReJudgeOutcome)
    assert outcome.status == "recorded"
    assert len(calls) == 1
    assert outcome.record is not None
    assert outcome.record.score == pytest.approx(0.42)
    assert outcome.source_attribution_key == original.attribution_key(strict=True)
    assert outcome.new_attribution_key == (
        "piece-rejudge",
        "judge-v2",
        "rubric-v2",
        "input-hash",
    )

    events = list(read_events(tmp_path, kinds=[EventKind.EVALUAND_RECORDED]))
    assert len(events) == 2
    folded = read_evaluand_events(tmp_path)
    assert folded[original.attribution_key(strict=True)].score == pytest.approx(0.9)
    assert folded[outcome.new_attribution_key].score == pytest.approx(0.42)


def test_re_judge_writes_nothing_when_recorded_io_unavailable(tmp_path):
    io = RecordedModelIO.unavailable(
        "legacy record had no captured model I/O",
        model_name="legacy-model",
    )
    rec = EvaluandRecord(
        "judge-v1",
        "rubric-v1",
        "input-hash",
        0.5,
        piece_version="piece-v1",
    )
    write_evaluand_event("run-legacy", rec, plan_dir=tmp_path, recorded_model_io=io)

    def scorer(recorded_io: RecordedModelIO) -> float:
        raise AssertionError("scorer must not run for unavailable recorded I/O")

    outcome = re_judge(
        plan_dir=tmp_path,
        recorded_io_key=io.ref().key,
        scorer=scorer,
        piece_version="piece-rejudge",
        judge_version="judge-v2",
        rubric_version="rubric-v2",
    )

    assert outcome.status == "unavailable"
    assert outcome.reason == "legacy record had no captured model I/O"
    assert outcome.record is None
    events = list(read_events(tmp_path, kinds=[EventKind.EVALUAND_RECORDED]))
    assert len(events) == 1


def test_re_judge_missing_recorded_io_key_writes_nothing(tmp_path):
    def scorer(recorded_io: RecordedModelIO) -> float:
        raise AssertionError("scorer must not run for a missing recorded I/O key")

    outcome = re_judge(
        plan_dir=tmp_path,
        recorded_io_key="missing-key",
        scorer=scorer,
        piece_version="piece-rejudge",
        judge_version="judge-v2",
        rubric_version="rubric-v2",
    )

    assert outcome.status == "unavailable"
    assert outcome.reason == "recorded_io_not_found"
    assert list(read_events(tmp_path, kinds=[EventKind.EVALUAND_RECORDED])) == []


def test_re_judge_rejects_same_attribution_key_to_avoid_overwrite(tmp_path):
    io = RecordedModelIO(
        model_name="gpt-5.4",
        prompt="judge prompt",
        response="judge response",
    )
    rec = EvaluandRecord(
        "judge-v1",
        "rubric-v1",
        "input-hash",
        0.5,
        piece_version="piece-v1",
    )
    write_evaluand_event("run-original", rec, plan_dir=tmp_path, recorded_model_io=io)

    with pytest.raises(ValueError, match="distinct attribution"):
        re_judge(
            plan_dir=tmp_path,
            recorded_io_key=io.ref().key,
            scorer=lambda recorded_io: 0.7,
            piece_version="piece-v1",
            judge_version="judge-v1",
            rubric_version="rubric-v1",
        )

    events = list(read_events(tmp_path, kinds=[EventKind.EVALUAND_RECORDED]))
    assert len(events) == 1


def test_write_evaluand_event_appends_event_before_ledger_update():
    class RecordingSink:
        def __init__(self):
            self.events = []

        def emit(self, kind, *, payload=None, **kwargs):
            assert read_evaluand("run-7") is None
            self.events.append({"kind": kind, "payload": payload, **kwargs})
            return self.events[-1]

    sink = RecordingSink()
    rec = EvaluandRecord(
        "judge-v1",
        "rubric-v1",
        "input-hash",
        0.9,
        piece_version="piece-v1",
    )

    event = write_evaluand_event("run-7", rec, event_sink=sink)

    assert event is sink.events[0]
    assert len(sink.events) == 1
    assert sink.events[0]["kind"] == EventKind.EVALUAND_RECORDED
    assert sink.events[0]["payload"]["run_id"] == "run-7"
    assert sink.events[0]["payload"]["piece_version"] == "piece-v1"
    assert sink.events[0]["payload"]["attribution_key"] == [
        "piece-v1",
        "judge-v1",
        "rubric-v1",
        "input-hash",
    ]
    assert read_evaluand("run-7") is rec


def test_write_evaluand_event_requires_strict_attribution_with_ledger_target():
    class RecordingSink:
        def emit(self, *args, **kwargs):
            raise AssertionError("strict attribution should fail before emit")

    rec = EvaluandRecord("judge-v1", "rubric-v1", "input-hash", 0.9)

    with pytest.raises(ValueError, match="piece_version"):
        write_evaluand_event("run-7", rec, event_sink=RecordingSink())

    assert read_evaluand("run-7") is None


def test_write_evaluand_event_requires_strict_attribution_with_plan_dir(tmp_path):
    rec = EvaluandRecord("judge-v1", "rubric-v1", "input-hash", 0.9)

    with pytest.raises(ValueError, match="piece_version"):
        write_evaluand_event("run-7", rec, plan_dir=tmp_path)

    assert read_evaluand("run-7") is None
    assert not (tmp_path / "events.ndjson").exists()


def test_write_evaluand_event_uses_events_ndjson_without_second_journal(tmp_path):
    rec = EvaluandRecord(
        "judge-v1",
        "rubric-v1",
        "input-hash",
        0.9,
        piece_version="piece-v1",
        provenance={"source": "unit"},
        taint=("trusted",),
    )

    write_evaluand_event("run-7", rec, plan_dir=tmp_path)

    events = list(read_events(tmp_path, kinds=[EventKind.EVALUAND_RECORDED]))
    assert len(events) == 1
    payload = events[0]["payload"]
    assert payload["run_id"] == "run-7"
    assert payload["score"] == pytest.approx(0.9)
    assert payload["provenance"] == {"source": "unit"}
    assert payload["taint"] == ["trusted"]
    assert read_evaluand("run-7") is rec

    files = {path.name for path in tmp_path.iterdir() if path.is_file()}
    assert "events.ndjson" in files
    assert not {
        name
        for name in files
        if name not in {"events.ndjson", ".events.seq", ".events.init_ts"}
    }


def test_write_evaluand_event_preserves_explicit_model_io_refs(tmp_path):
    explicit_ref = {
        "model_identity": "model:gpt-5.4",
        "prompt_sha256": "a" * 64,
        "params_canonical": '{"temperature":0}',
        "params_hash": "b" * 64,
    }
    explicit_recorded_ref = {
        "model_identity": "model:gpt-5.5",
        "prompt_sha256": "c" * 64,
        "params_canonical": '{"temperature":1}',
        "params_hash": "d" * 64,
    }
    rec = EvaluandRecord(
        "judge-v1",
        "rubric-v1",
        "input-hash",
        0.9,
        piece_version="piece-v1",
        model_io_ref=explicit_ref,
        recorded_model_io_ref=explicit_recorded_ref,
    )
    recorded_io = RecordedModelIO(
        model_name="gpt-5.4",
        prompt="judge prompt",
        response="judge response",
        params={"temperature": 0},
    )

    write_evaluand_event(
        "run-7",
        rec,
        plan_dir=tmp_path,
        recorded_model_io=recorded_io,
    )

    payload = list(read_events(tmp_path, kinds=[EventKind.EVALUAND_RECORDED]))[0][
        "payload"
    ]
    assert payload["model_io_ref"] == explicit_ref
    assert payload["recorded_model_io_ref"] == explicit_recorded_ref
    assert payload["recorded_model_io"]["ref"] != explicit_ref
    assert payload["recorded_model_io"]["ref"] != explicit_recorded_ref


def test_transaction_boundary_flushes_staged_receipt_through_event_ledger(tmp_path):
    rec = EvaluandRecord(
        "judge-v1",
        "rubric-v1",
        "input-hash",
        0.9,
        piece_version="piece-v1",
    )

    with pytest.raises(RuntimeError, match="rollback"):
        with _evaluand_transaction_boundary():
            stage_receipt("run-rollback", rec, plan_dir=tmp_path)
            raise RuntimeError("rollback")

    assert read_evaluand("run-rollback") is None
    assert list(read_events(tmp_path, kinds=[EventKind.EVALUAND_RECORDED])) == []

    with _evaluand_transaction_boundary():
        stage_receipt("run-commit", rec, plan_dir=tmp_path)

    events = list(read_events(tmp_path, kinds=[EventKind.EVALUAND_RECORDED]))
    assert len(events) == 1
    assert events[0]["payload"]["run_id"] == "run-commit"
    assert read_evaluand("run-commit") is rec


def test_read_evaluand_events_replaces_duplicates_in_file_order(tmp_path):
    first = EvaluandRecord(
        "judge-v1",
        "rubric-v1",
        "input-hash",
        0.2,
        piece_version="piece-v1",
    )
    second = EvaluandRecord(
        "judge-v1",
        "rubric-v1",
        "input-hash",
        0.8,
        piece_version="piece-v1",
    )
    other = EvaluandRecord(
        "judge-v1",
        "rubric-v1",
        "other-input",
        0.4,
        piece_version="piece-v1",
    )

    write_evaluand_event("run-first", first, plan_dir=tmp_path)
    write_evaluand_event("run-other", other, plan_dir=tmp_path)
    write_evaluand_event("run-second", second, plan_dir=tmp_path)

    folded = read_evaluand_events(tmp_path, strict=True)

    assert folded[first.attribution_key(strict=True)].score == pytest.approx(0.8)
    assert folded[other.attribution_key(strict=True)].score == pytest.approx(0.4)
    assert len(folded) == 2


def test_read_evaluand_events_fails_loudly_on_corrupt_json(tmp_path):
    rec = EvaluandRecord(
        "judge-v1",
        "rubric-v1",
        "input-hash",
        0.2,
        piece_version="piece-v1",
    )
    write_evaluand_event("run-1", rec, plan_dir=tmp_path)
    with (tmp_path / "events.ndjson").open("a", encoding="utf-8") as handle:
        handle.write("{not-json\n")

    with pytest.raises(RuntimeError, match="EVALUAND_EVENTS_NDJSON_DECODE_ERROR"):
        read_evaluand_events(tmp_path, strict=True)


def test_read_evaluand_events_does_not_fallback_to_ledger(tmp_path):
    rec = EvaluandRecord(
        "judge-v1",
        "rubric-v1",
        "input-hash",
        0.2,
        piece_version="piece-v1",
    )

    write_evaluand("run-only-ledger", rec)

    assert read_evaluand("run-only-ledger") is rec
    assert read_evaluand_events(tmp_path, strict=True) == {}


def test_read_evaluand_events_no_second_journal(tmp_path):
    rec = EvaluandRecord(
        "judge-v1",
        "rubric-v1",
        "input-hash",
        0.2,
        piece_version="piece-v1",
    )

    write_evaluand_event("run-1", rec, plan_dir=tmp_path)
    assert read_evaluand_events(tmp_path, strict=True)

    files = {path.name for path in tmp_path.iterdir() if path.is_file()}
    assert "events.ndjson" in files
    assert not {
        name
        for name in files
        if name not in {"events.ndjson", ".events.seq", ".events.init_ts"}
    }


def test_better_requires_plan_dir():
    with pytest.raises(ValueError, match="plan_dir"):
        better(
            "piece-a",
            "piece-b",
            judge_version="judge-v1",
            rubric_version="rubric-v1",
            input_set_hash="input-hash",
        )


def test_better_returns_winner_from_event_ledger_only(tmp_path):
    a = EvaluandRecord(
        "judge-v1",
        "rubric-v1",
        "input-hash",
        0.2,
        piece_version="piece-a",
    )
    b = EvaluandRecord(
        "judge-v1",
        "rubric-v1",
        "input-hash",
        0.9,
        piece_version="piece-b",
    )
    legacy = EvaluandRecord(
        "judge-v1",
        "rubric-v1",
        "input-hash",
        1.0,
        piece_version="piece-a",
    )

    write_evaluand_event("run-a", a, plan_dir=tmp_path)
    write_evaluand_event("run-b", b, plan_dir=tmp_path)
    write_evaluand("legacy-run-a", legacy)

    result = better(
        "piece-a",
        "piece-b",
        plan_dir=tmp_path,
        judge_version="judge-v1",
        rubric_version="rubric-v1",
        input_set_hash="input-hash",
    )
    again = better(
        "piece-a",
        "piece-b",
        plan_dir=tmp_path,
        judge_version="judge-v1",
        rubric_version="rubric-v1",
        input_set_hash="input-hash",
    )

    assert isinstance(result, BetterResult)
    assert result == again
    assert result.status == "winner"
    assert result.winner_piece_version == "piece-b"
    assert result.scores == {"piece-a": 0.2, "piece-b": 0.9}
    assert result.attribution["piece-b"] == (
        "piece-b",
        "judge-v1",
        "rubric-v1",
        "input-hash",
    )


def test_better_missing_record_is_typed_undetermined(tmp_path):
    rec = EvaluandRecord(
        "judge-v1",
        "rubric-v1",
        "input-hash",
        0.2,
        piece_version="piece-a",
    )
    write_evaluand_event("run-a", rec, plan_dir=tmp_path)

    result = better(
        "piece-a",
        "piece-b",
        plan_dir=tmp_path,
        judge_version="judge-v1",
        rubric_version="rubric-v1",
        input_set_hash="input-hash",
    )

    assert result.status == "undetermined"
    assert result.reason == "missing_record"
    assert result.winner_piece_version is None
    assert result.scores == {"piece-a": 0.2}


def test_better_tie_is_typed_undetermined(tmp_path):
    for piece in ("piece-a", "piece-b"):
        write_evaluand_event(
            f"run-{piece}",
            EvaluandRecord(
                "judge-v1",
                "rubric-v1",
                "input-hash",
                0.5,
                piece_version=piece,
            ),
            plan_dir=tmp_path,
        )

    result = better(
        "piece-a",
        "piece-b",
        plan_dir=tmp_path,
        judge_version="judge-v1",
        rubric_version="rubric-v1",
        input_set_hash="input-hash",
    )

    assert result.status == "undetermined"
    assert result.reason == "tie"
    assert result.scores == {"piece-a": 0.5, "piece-b": 0.5}


def test_better_legacy_only_record_is_typed_undetermined(tmp_path):
    write_evaluand(
        "legacy-run",
        EvaluandRecord(
            "judge-v1",
            "rubric-v1",
            "input-hash",
            1.0,
            piece_version="piece-a",
        ),
    )

    result = better(
        "piece-a",
        "piece-b",
        plan_dir=tmp_path,
        judge_version="judge-v1",
        rubric_version="rubric-v1",
        input_set_hash="input-hash",
    )

    assert result.status == "undetermined"
    assert result.reason == "missing_record"
    assert result.scores == {}


def test_better_incomplete_event_is_typed_undetermined(tmp_path):
    event = {
        "seq": 0,
        "schema_version": 1,
        "kind": EventKind.EVALUAND_RECORDED,
        "phase": None,
        "payload": {
            "run_id": "legacy-event",
            "judge_version": "judge-v1",
            "rubric_version": "rubric-v1",
            "input_set_hash": "input-hash",
            "score": 0.8,
            "recorded_at": 1.0,
        },
    }
    (tmp_path / "events.ndjson").write_text(
        json.dumps(event) + "\n",
        encoding="utf-8",
    )

    result = better(
        "piece-a",
        "piece-b",
        plan_dir=tmp_path,
        judge_version="judge-v1",
        rubric_version="rubric-v1",
        input_set_hash="input-hash",
    )

    assert result.status == "undetermined"
    assert result.reason == "incomplete_record"


def test_better_accepts_no_judge_or_model_callback(tmp_path):
    with pytest.raises(TypeError):
        better(
            "piece-a",
            "piece-b",
            plan_dir=tmp_path,
            judge_version="judge-v1",
            rubric_version="rubric-v1",
            input_set_hash="input-hash",
            judge=lambda *_args, **_kwargs: 1.0,
        )


def test_bare_float_is_rejected():
    with pytest.raises(TypeError):
        write_evaluand("run-7", 0.83)  # type: ignore[arg-type]


def test_missing_run_id_is_rejected():
    rec = EvaluandRecord("j", "r", "h", 0.0)
    with pytest.raises(ValueError):
        write_evaluand("", rec)


def test_read_missing_returns_none():
    assert read_evaluand("nope") is None


def test_exported_from_observability_package():
    from arnold.pipelines.megaplan import observability as ob 
    assert "EvaluandRecord" in ob.__all__
    assert "BetterResult" in ob.__all__
    assert "better" in ob.__all__
    assert "write_evaluand" in ob.__all__
    assert "write_evaluand_event" in ob.__all__
    assert "read_evaluand" in ob.__all__
    assert "read_evaluand_events" in ob.__all__
    assert "stage_receipt" in ob.__all__
