"""Tests for megaplan.observability.evaluand.io_key (T3)."""

from megaplan.observability.evaluand import io_key


def _record(
    prompt_hash_canonical=None,
    prompt_hash_raw=None,
    model_identity="model-a",
    params=None,
):
    return {
        "piece_version": "v1",
        "judge_version": "j1",
        "rubric_version": "r1",
        "input_set_hash": "h1",
        "score": 0.9,
        "provenance": {"params": params or {}},
        "taint": "trusted",
        "recorded_at": "2026-01-01T00:00:00Z",
        "model_identity": model_identity,
        "prompt_hash_canonical": prompt_hash_canonical,
        "prompt_hash_raw": prompt_hash_raw,
    }


def test_same_prompt_model_params_equal_key():
    r1 = _record(prompt_hash_canonical="abc", model_identity="m1", params={"t": 0.5})
    r2 = _record(prompt_hash_canonical="abc", model_identity="m1", params={"t": 0.5})
    assert io_key(r1) == io_key(r2)


def test_param_order_permutations_equal_key():
    r1 = _record(prompt_hash_canonical="abc", params={"a": 1, "b": 2})
    r2 = _record(prompt_hash_canonical="abc", params={"b": 2, "a": 1})
    assert io_key(r1) == io_key(r2)


def test_model_swap_distinct_key():
    r1 = _record(prompt_hash_canonical="abc", model_identity="model-a")
    r2 = _record(prompt_hash_canonical="abc", model_identity="model-b")
    assert io_key(r1) != io_key(r2)


def test_both_hashes_none_first_element_empty():
    r = _record(prompt_hash_canonical=None, prompt_hash_raw=None)
    key = io_key(r)
    assert key[0] == ""
