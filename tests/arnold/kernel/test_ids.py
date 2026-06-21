from __future__ import annotations

import pytest

from arnold.kernel import derive_idempotency_key, derive_pipeline_identity


def test_pipeline_identity_derives_from_alias_and_manifest_hash() -> None:
    manifest_hash = "sha256:" + "a" * 64

    assert derive_pipeline_identity("planning", manifest_hash) == derive_pipeline_identity(
        "planning", manifest_hash
    )
    assert derive_pipeline_identity("planning", manifest_hash) != derive_pipeline_identity(
        "other", manifest_hash
    )


def test_idempotency_key_is_ordered_and_fail_closed() -> None:
    assert derive_idempotency_key("run", "node", "effect") != derive_idempotency_key(
        "effect", "node", "run"
    )
    with pytest.raises(ValueError):
        derive_idempotency_key("run", "")
