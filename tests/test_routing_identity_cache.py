from __future__ import annotations

from pathlib import Path

from megaplan.routing import cache_get, cache_set, compute_identity, params_hash
from megaplan.store import FileStore


def test_params_hash_covers_model_side_params_only() -> None:
    base = {
        "temperature": 0.2,
        "max_tokens": 512,
        "top_p": 0.9,
        "seed": 1,
    }
    drifted_non_model_param = {
        "temperature": 0.2,
        "max_tokens": 512,
        "top_p": 0.9,
        "seed": 999,
    }

    assert params_hash(base) == params_hash(drifted_non_model_param)


def test_routing_cache_misses_on_model_version_drift(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    params = {"temperature": 0.2, "max_tokens": 512, "top_p": 0.9}
    stable_prompt = "Summarize this plan."

    v1_identity = compute_identity(stable_prompt, "model-v1", params)
    v2_identity = compute_identity(stable_prompt, "model-v2", params)

    cache_set(store, v1_identity, "cached-v1")

    assert cache_get(store, v2_identity, touch=False) is None


def test_routing_cache_hits_when_identity_components_are_stable(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    params = {"top_p": 0.9, "max_tokens": 512, "temperature": 0.2}
    stable_prompt = "Summarize this plan."

    first_identity = compute_identity(stable_prompt, {"model_version": "model-v1"}, params)
    second_identity = compute_identity(stable_prompt, {"model_version": "model-v1"}, dict(params))

    cache_set(store, first_identity, "cached-output")

    assert cache_get(store, second_identity, touch=False) == "cached-output"
