from __future__ import annotations

from arnold_pipelines.megaplan.workers._impl import (
    _extract_json_candidates_from_raw,
    _json_decode_error_for_raw,
)
from arnold_pipelines.megaplan.workers.hermes import (
    _deescape_double_encoded_json,
    _parse_json_response,
)


DOUBLE_ENCODED = r'{\"title\":\"Plan\",\"steps\":[{\"id\":\"S1\"}]}'
EXPECTED = {"title": "Plan", "steps": [{"id": "S1"}]}


def test_hermes_parser_recovers_double_encoded_object_response() -> None:
    assert _parse_json_response(DOUBLE_ENCODED) == EXPECTED


def test_worker_candidate_extraction_recovers_double_encoded_object_response() -> None:
    assert _extract_json_candidates_from_raw(DOUBLE_ENCODED)[0] == EXPECTED
    assert _json_decode_error_for_raw(DOUBLE_ENCODED) is None


def test_double_encoded_recovery_is_narrow() -> None:
    clean = '{"title":"Plan"}'
    prose = r'Use \"quoted\" words in prose.'

    assert _deescape_double_encoded_json(clean) is None
    assert _deescape_double_encoded_json(prose) is None
    assert _parse_json_response(clean) == {"title": "Plan"}
