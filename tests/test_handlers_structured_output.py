"""Tests for the strict scratch promotion helper in ``handlers/structured_output.py``.

Covers:
  - filled/missing/unmodified/invalid status classification
  - seed comparison (byte-for-byte identical detection)
  - unknown top-level key stripping
  - expected-path-only reads (ignores wrong-path writes)
  - wrong-path canonical writes are ignored
  - invalid modified scratch failure semantics (file_fill_instructed)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold.pipelines.megaplan.handlers.structured_output import (
    ScratchStatus,
    _scratch_path,
    _read_scratch_json,
    _strip_unknown_keys,
    classify_scratch,
    promote_scratch,
    resolve_scratch_filename_for_phase,
)
from arnold.pipelines.megaplan.workers import WorkerResult
from arnold.pipelines.megaplan.template_registry import (
    TemplateRegistration,
    _TEMPLATE_REGISTRY,
    register,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _worker(payload: dict | None = None) -> WorkerResult:
    """Build a minimal WorkerResult with the given inline payload."""
    return WorkerResult(
        payload=payload or {"summary": "worker fallback"},
        raw_output="raw",
        duration_ms=100,
        cost_usd=0.0,
    )


def _seed() -> str:
    """Return a representative seed JSON string (a template the model would fill)."""
    return json.dumps({"tasks": [], "sense_checks": []}, indent=2)


KNOWN_KEYS = frozenset({"tasks", "sense_checks"})


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# _scratch_path
# ---------------------------------------------------------------------------


def test_scratch_path_resolves_inside_plan_dir(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    path = _scratch_path(plan_dir, "gate_output.json")
    assert path == plan_dir / "gate_output.json"
    assert str(path).startswith(str(plan_dir.resolve()))


def test_scratch_path_rejects_traversal(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    with pytest.raises(ValueError, match="escapes plan_dir"):
        _scratch_path(plan_dir, "../escape.json")


# ---------------------------------------------------------------------------
# _read_scratch_json
# ---------------------------------------------------------------------------


def test_read_scratch_json_valid_dict(tmp_path: Path) -> None:
    path = tmp_path / "valid.json"
    _write_file(path, '{"key": "value"}')
    assert _read_scratch_json(path) == {"key": "value"}


def test_read_scratch_json_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "nonexistent.json"
    assert _read_scratch_json(path) is None


def test_read_scratch_json_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    _write_file(path, "not json at all")
    assert _read_scratch_json(path) is None


def test_read_scratch_json_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.json"
    _write_file(path, "")
    assert _read_scratch_json(path) is None


def test_read_scratch_json_binary_file(tmp_path: Path) -> None:
    path = tmp_path / "binary.bin"
    path.write_bytes(b"\x00\x01\x02")
    assert _read_scratch_json(path) is None


def test_read_scratch_json_scalar_value(tmp_path: Path) -> None:
    """A scalar top-level value parses fine — but classify_scratch rejects it."""
    path = tmp_path / "scalar.json"
    _write_file(path, '"just a string"')
    # _read_scratch_json returns any valid JSON; classify_scratch does the dict-check
    assert _read_scratch_json(path) == "just a string"


def test_read_scratch_json_list_value(tmp_path: Path) -> None:
    """A list top-level value parses fine — but classify_scratch rejects it."""
    path = tmp_path / "list.json"
    _write_file(path, '[1, 2, 3]')
    assert _read_scratch_json(path) == [1, 2, 3]


# ---------------------------------------------------------------------------
# _strip_unknown_keys
# ---------------------------------------------------------------------------


def test_strip_unknown_keys_removes_extra_fields() -> None:
    payload = {"tasks": [{"id": "T1"}], "sense_checks": [], "extra_field": "drop_me", "commentary": 42}
    known = frozenset({"tasks", "sense_checks"})
    result = _strip_unknown_keys(payload, known)
    assert result == {"tasks": [{"id": "T1"}], "sense_checks": []}
    assert "extra_field" not in result
    assert "commentary" not in result


def test_strip_unknown_keys_keeps_all_known() -> None:
    payload = {"tasks": [{"id": "T1"}], "sense_checks": [{"id": "SC1"}]}
    known = frozenset({"tasks", "sense_checks"})
    result = _strip_unknown_keys(payload, known)
    assert result == payload


def test_strip_unknown_keys_empty_known_set() -> None:
    payload = {"tasks": [], "sense_checks": []}
    result = _strip_unknown_keys(payload, frozenset())
    assert result == {}


def test_strip_unknown_keys_non_dict_input() -> None:
    """Non-dict input is returned unchanged."""
    assert _strip_unknown_keys("string", frozenset({"a"})) == "string"
    assert _strip_unknown_keys([1, 2], frozenset({"a"})) == [1, 2]


def test_strip_unknown_keys_no_unknown_keys() -> None:
    payload = {"tasks": []}
    known = frozenset({"tasks", "sense_checks"})
    result = _strip_unknown_keys(payload, known)
    assert result == {"tasks": []}


def test_strip_unknown_keys_long_list_of_unknown() -> None:
    """Many unknown keys — all stripped."""
    payload = {"tasks": [], "a": 1, "b": 2, "c": 3, "d": 4, "e": 5}
    known = frozenset({"tasks"})
    result = _strip_unknown_keys(payload, known)
    assert result == {"tasks": []}


# ---------------------------------------------------------------------------
# classify_scratch
# ---------------------------------------------------------------------------


def test_classify_missing(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    status, payload = classify_scratch(plan_dir, "output.json", seed_json=_seed())
    assert status == "missing"
    assert payload is None


def test_classify_unmodified_seed_match(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    seed = _seed()
    _write_file(plan_dir / "output.json", seed)
    status, payload = classify_scratch(plan_dir, "output.json", seed_json=seed)
    assert status == "unmodified"
    assert payload is None


def test_classify_filled_valid_json(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    filled = json.dumps({"tasks": [{"id": "T1"}], "sense_checks": [{"id": "SC1"}]})
    _write_file(plan_dir / "output.json", filled)
    status, payload = classify_scratch(plan_dir, "output.json", seed_json=_seed())
    assert status == "filled"
    assert payload == {"tasks": [{"id": "T1"}], "sense_checks": [{"id": "SC1"}]}


def test_classify_filled_no_seed(tmp_path: Path) -> None:
    """Without a seed, a valid JSON dict is classified as 'filled' (no unmodified detection)."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    filled = json.dumps({"tasks": [{"id": "T1"}]})
    _write_file(plan_dir / "output.json", filled)
    status, payload = classify_scratch(plan_dir, "output.json", seed_json=None)
    assert status == "filled"
    assert payload == {"tasks": [{"id": "T1"}]}


def test_classify_invalid_json(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_file(plan_dir / "output.json", "not valid {{{")
    status, payload = classify_scratch(plan_dir, "output.json", seed_json=_seed())
    assert status == "invalid"
    assert payload is None


def test_classify_invalid_scalar(tmp_path: Path) -> None:
    """A modified file that parses as a scalar (not dict) is 'invalid'."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_file(plan_dir / "output.json", '"just a string"')
    status, payload = classify_scratch(plan_dir, "output.json", seed_json=_seed())
    assert status == "invalid"
    assert payload is None


def test_classify_invalid_list(tmp_path: Path) -> None:
    """A modified file that parses as a list (not dict) is 'invalid'."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_file(plan_dir / "output.json", "[1, 2, 3]")
    status, payload = classify_scratch(plan_dir, "output.json", seed_json=_seed())
    assert status == "invalid"
    assert payload is None


def test_classify_unicode_error_returns_missing(tmp_path: Path) -> None:
    """A binary file that can't be decoded as UTF-8 is treated as missing."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "output.json").write_bytes(b"\xff\xfe\x00\x01")
    status, payload = classify_scratch(plan_dir, "output.json", seed_json=_seed())
    assert status == "missing"


def test_classify_permission_error_treated_as_missing(tmp_path: Path) -> None:
    """Unreadable files are treated as missing."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    path = plan_dir / "output.json"
    _write_file(path, '{"k":"v"}')
    path.chmod(0o000)  # remove all permissions
    try:
        status, payload = classify_scratch(plan_dir, "output.json", seed_json=_seed())
        assert status == "missing"
    finally:
        path.chmod(0o644)  # restore so tmp_path can clean up


def test_classify_empty_modified_file_is_invalid(tmp_path: Path) -> None:
    """An empty file differs from the seed and is not valid JSON."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_file(plan_dir / "output.json", "")
    status, payload = classify_scratch(plan_dir, "output.json", seed_json=_seed())
    assert status == "invalid"
    assert payload is None


# ---------------------------------------------------------------------------
# Seed comparison (byte-for-byte)
# ---------------------------------------------------------------------------


def test_seed_comparison_identical_bytes(tmp_path: Path) -> None:
    """Byte-for-byte identical seed and scratch → unmodified."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    seed = '{"tasks":[],"sense_checks":[]}'
    _write_file(plan_dir / "output.json", seed)
    status, _ = classify_scratch(plan_dir, "output.json", seed_json=seed)
    assert status == "unmodified"


def test_seed_comparison_whitespace_diff_is_modified(tmp_path: Path) -> None:
    """Even a whitespace difference counts as modified, not unmodified."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    seed = '{"tasks":[],"sense_checks":[]}'
    different = '{"tasks": [], "sense_checks": []}'  # spaces added
    _write_file(plan_dir / "output.json", different)
    status, _ = classify_scratch(plan_dir, "output.json", seed_json=seed)
    assert status == "filled"  # valid JSON, but different → filled


def test_seed_comparison_trailing_newline_is_modified(tmp_path: Path) -> None:
    """A trailing newline makes the file different from the seed."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    seed = '{"tasks":[],"sense_checks":[]}'
    different = '{"tasks":[],"sense_checks":[]}\n'
    _write_file(plan_dir / "output.json", different)
    status, _ = classify_scratch(plan_dir, "output.json", seed_json=seed)
    assert status == "filled"


# ---------------------------------------------------------------------------
# promote_scratch — missing, unmodified, filled flows
# ---------------------------------------------------------------------------


def test_promote_missing_falls_back_to_worker_payload(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    worker = _worker({"tasks": [{"id": "T1"}], "sense_checks": []})
    status, payload = promote_scratch(
        plan_dir, "output.json", KNOWN_KEYS, worker, seed_json=_seed(),
    )
    assert status == "missing"
    assert payload == worker.payload


def test_promote_unmodified_falls_back_to_worker_payload(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    seed = _seed()
    _write_file(plan_dir / "output.json", seed)
    worker = _worker({"tasks": [{"id": "inline"}], "sense_checks": []})
    status, payload = promote_scratch(
        plan_dir, "output.json", KNOWN_KEYS, worker, seed_json=seed,
    )
    assert status == "unmodified"
    assert payload == worker.payload


def test_promote_filled_strips_unknown_keys(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    filled = json.dumps({
        "tasks": [{"id": "T1"}],
        "sense_checks": [{"id": "SC1"}],
        "extra_model_commentary": "should be stripped",
        "another_extra": 42,
    })
    _write_file(plan_dir / "output.json", filled)
    worker = _worker()
    status, payload = promote_scratch(
        plan_dir, "output.json", KNOWN_KEYS, worker, seed_json=_seed(),
    )
    assert status == "filled"
    assert "extra_model_commentary" not in payload
    assert "another_extra" not in payload
    assert payload["tasks"] == [{"id": "T1"}]
    assert payload["sense_checks"] == [{"id": "SC1"}]


def test_promote_filled_keeps_all_known_keys(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    filled = json.dumps({"tasks": [{"id": "T1"}], "sense_checks": [{"id": "SC1"}]})
    _write_file(plan_dir / "output.json", filled)
    worker = _worker()
    status, payload = promote_scratch(
        plan_dir, "output.json", KNOWN_KEYS, worker, seed_json=_seed(),
    )
    assert status == "filled"
    assert payload == {"tasks": [{"id": "T1"}], "sense_checks": [{"id": "SC1"}]}


def test_promote_filled_subset_of_known_keys(tmp_path: Path) -> None:
    """Model only fills a subset of known keys — that's fine."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    filled = json.dumps({"tasks": [{"id": "T1"}]})
    _write_file(plan_dir / "output.json", filled)
    worker = _worker()
    status, payload = promote_scratch(
        plan_dir, "output.json", KNOWN_KEYS, worker, seed_json=_seed(),
    )
    assert status == "filled"
    assert payload == {"tasks": [{"id": "T1"}]}


# ---------------------------------------------------------------------------
# promote_scratch — invalid + file_fill_instructed semantics
# ---------------------------------------------------------------------------


def test_promote_invalid_file_fill_instructed_raises(tmp_path: Path) -> None:
    """SD3: Modified invalid scratch with file_fill_instructed=True → hard fail."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_file(plan_dir / "output.json", "not valid {{{")
    worker = _worker()
    with pytest.raises(ValueError, match="does not contain valid JSON"):
        promote_scratch(
            plan_dir, "output.json", KNOWN_KEYS, worker,
            seed_json=_seed(), file_fill_instructed=True,
        )


def test_promote_invalid_file_fill_not_instructed_falls_back(tmp_path: Path) -> None:
    """SD3: Modified invalid scratch with file_fill_instructed=False → fallback."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_file(plan_dir / "output.json", "not valid {{{")
    worker = _worker({"tasks": [{"id": "fallback"}]})
    status, payload = promote_scratch(
        plan_dir, "output.json", KNOWN_KEYS, worker,
        seed_json=_seed(), file_fill_instructed=False,
    )
    assert status == "invalid"
    assert payload == worker.payload


def test_promote_invalid_scalar_file_fill_instructed_raises(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_file(plan_dir / "output.json", '"a string"')
    worker = _worker()
    with pytest.raises(ValueError, match="does not contain valid JSON"):
        promote_scratch(
            plan_dir, "output.json", KNOWN_KEYS, worker,
            seed_json=_seed(), file_fill_instructed=True,
        )


def test_promote_invalid_empty_file_fill_instructed_raises(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_file(plan_dir / "output.json", "")
    worker = _worker()
    with pytest.raises(ValueError, match="does not contain valid JSON"):
        promote_scratch(
            plan_dir, "output.json", KNOWN_KEYS, worker,
            seed_json=_seed(), file_fill_instructed=True,
        )


# ---------------------------------------------------------------------------
# Expected-path-only reads (ignores wrong-path writes)
# ---------------------------------------------------------------------------


def test_promote_ignores_canonical_path_write(tmp_path: Path) -> None:
    """Model writes to the canonical artifact path (e.g. gate.json) —
    the handler only reads the expected scratch path (gate_output.json)."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    # Model writes to the canonical path — not the scratch path
    _write_file(plan_dir / "gate.json", '{"tasks":[{"id":"canonical"}],"sense_checks":[]}')
    # Scratch file is missing
    worker = _worker({"tasks": [{"id": "fallback"}]})
    status, payload = promote_scratch(
        plan_dir, "gate_output.json", KNOWN_KEYS, worker, seed_json=_seed(),
    )
    # Even though gate.json exists, we only read gate_output.json → missing
    assert status == "missing"
    assert payload == worker.payload


def test_promote_only_reads_expected_path_when_other_scratch_exists(tmp_path: Path) -> None:
    """Another scratch file exists but not the expected one — still missing."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    # Write to a different scratch file
    _write_file(plan_dir / "other_output.json", '{"tasks":[],"sense_checks":[]}')
    worker = _worker({"tasks": [{"id": "fallback"}]})
    status, payload = promote_scratch(
        plan_dir, "expected_output.json", KNOWN_KEYS, worker, seed_json=_seed(),
    )
    assert status == "missing"
    assert payload == worker.payload


def test_promote_both_scratch_and_canonical_exist_reads_scratch(tmp_path: Path) -> None:
    """Both the scratch path and canonical path exist — read only scratch."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    # Write to canonical path
    _write_file(plan_dir / "gate.json", '{"tasks":[{"id":"canonical"}],"sense_checks":[]}')
    # Write to scratch path (filled)
    _write_file(plan_dir / "gate_output.json", '{"tasks":[{"id":"scratch"}],"sense_checks":[],"extra":"x"}')
    worker = _worker()
    status, payload = promote_scratch(
        plan_dir, "gate_output.json", KNOWN_KEYS, worker, seed_json=_seed(),
    )
    assert status == "filled"
    # Should get the scratch content, not the canonical content
    assert payload["tasks"] == [{"id": "scratch"}]
    # Unknown key stripped
    assert "extra" not in payload


# ---------------------------------------------------------------------------
# promote_scratch — edge cases
# ---------------------------------------------------------------------------


def test_promote_default_file_fill_instructed_is_true(tmp_path: Path) -> None:
    """file_fill_instructed defaults to True."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_file(plan_dir / "output.json", "bad json")
    worker = _worker()
    with pytest.raises(ValueError):
        promote_scratch(
            plan_dir, "output.json", KNOWN_KEYS, worker, seed_json=_seed(),
        )


def test_promote_no_seed_json_skips_unmodified_detection(tmp_path: Path) -> None:
    """Without seed_json, unmodified cannot be detected — falls through to filled/invalid."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    filled = json.dumps({"tasks": [{"id": "T1"}]})
    _write_file(plan_dir / "output.json", filled)
    worker = _worker()
    status, payload = promote_scratch(
        plan_dir, "output.json", frozenset({"tasks"}), worker, seed_json=None,
    )
    assert status == "filled"
    assert payload == {"tasks": [{"id": "T1"}]}


def test_promote_with_frozenset_of_known_keys(tmp_path: Path) -> None:
    """Using a frozenset for known_keys."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    filled = json.dumps({"a": 1, "b": 2, "c": 3})
    _write_file(plan_dir / "output.json", filled)
    worker = _worker()
    status, payload = promote_scratch(
        plan_dir, "output.json", frozenset({"a", "b"}), worker, seed_json=_seed(),
    )
    assert status == "filled"
    assert payload == {"a": 1, "b": 2}
    assert "c" not in payload


def test_promote_empty_known_keys_strips_everything(tmp_path: Path) -> None:
    """If known_keys is empty, everything is stripped."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    filled = json.dumps({"a": 1, "b": 2})
    _write_file(plan_dir / "output.json", filled)
    worker = _worker()
    status, payload = promote_scratch(
        plan_dir, "output.json", frozenset(), worker, seed_json=_seed(),
    )
    assert status == "filled"
    assert payload == {}


# ---------------------------------------------------------------------------
# resolve_scratch_filename_for_phase
# ---------------------------------------------------------------------------


def test_resolve_scratch_filename_for_registered_phase() -> None:
    """A registered file_fill phase returns its scratch filename."""
    result = resolve_scratch_filename_for_phase("gate")
    assert result == "gate_output.json"


def test_resolve_scratch_filename_for_finalize() -> None:
    result = resolve_scratch_filename_for_phase("finalize")
    assert result == "finalize_output.json"


def test_resolve_scratch_filename_for_markdown_exempt() -> None:
    """Markdown-exempt phases have empty scratch_filename → None."""
    result = resolve_scratch_filename_for_phase("plan")
    assert result is None


def test_resolve_scratch_filename_for_unknown_phase() -> None:
    """Unknown phase not in registry → None."""
    result = resolve_scratch_filename_for_phase("nonexistent_phase")
    assert result is None


def test_resolve_scratch_filename_for_subloop_exempt() -> None:
    result = resolve_scratch_filename_for_phase("tiebreaker_researcher")
    assert result is None


# ---------------------------------------------------------------------------
# Registration round-trip
# ---------------------------------------------------------------------------


def test_custom_registration_roundtrip() -> None:
    """Verify register/get_template_registration round-trip."""
    # Use a unique phase ID to avoid clobbering the real registry
    phase = "test_custom_roundtrip_phase"
    reg = TemplateRegistration(
        phase_identity=phase,
        mode="file_fill",
        scratch_filename="test_output.json",
        builder=None,
        note="Test registration.",
    )
    try:
        register(reg)
        assert resolve_scratch_filename_for_phase(phase) == "test_output.json"
    finally:
        # Clean up — don't leave test entries in the module-level registry
        _TEMPLATE_REGISTRY.pop(phase, None)


def test_duplicate_registration_raises() -> None:
    phase = "test_dup_phase"
    reg = TemplateRegistration(
        phase_identity=phase,
        mode="file_fill",
        scratch_filename="test_output.json",
        builder=None,
    )
    try:
        register(reg)
        with pytest.raises(KeyError):
            register(reg)
    finally:
        _TEMPLATE_REGISTRY.pop(phase, None)
