"""Validation coverage for the frozen cutover configuration contract (CL5 Step 11).

These tests pin the central immutable binding of the CL5 cutover epic:

* a fully-populated :class:`CutoverConfig` whose ``source_revision`` and
  ``north_star_runtime_binding`` equal the North Star pinned runtime
  validates successfully;
* any missing (blank) hash/revision field fails closed;
* ``north_star_runtime_binding`` other than the North Star hash fails closed;
* ``source_revision`` other than the North Star hash fails closed (for this
  epic the migrated runtime commit MUST equal the North Star pinned runtime).

Together these guarantee :func:`validate_config` rejects every missing or
mismatched field and refuses any runtime binding other than
``d5848010695e28ddb9d9cbee8675d7ebe725caae``.
"""

from __future__ import annotations

import pytest

from arnold.critique_ledger.cutover.config import (
    NORTH_STAR_RUNTIME_HASH,
    CutoverConfig,
    CutoverConfigError,
    validate_config,
)

_NS = NORTH_STAR_RUNTIME_HASH  # the immutable North Star pinned runtime


def _valid_config(**overrides: str) -> CutoverConfig:
    """Build a config whose every field is populated and both North Star
    bindings equal the pinned runtime, applying ``overrides`` last."""
    base: dict[str, str] = {
        "source_revision": _NS,
        "target_revision": "sha256:" + "a" * 64,
        "schema_version": "arnold.critique_ledger.v1",
        "wbc_contract_hash": "sha256:" + "b" * 64,
        "m6_oracle_hash": "sha256:" + "c" * 64,
        "corpus_fixture_hash": "sha256:" + "d" * 64,
        "operator_approval_revision": "e" * 40,
        "backup_identity": "sha256:" + "f" * 64,
        "build_revision": "9" * 40,
        "north_star_runtime_binding": _NS,
    }
    base.update(overrides)
    return CutoverConfig(**base)


def test_valid_config_passes_validation() -> None:
    config = _valid_config()
    # validate_config returns the config unchanged on success.
    assert validate_config(config) is config
    # The convenience method composes identically.
    assert config.validate() is config


def test_config_is_frozen_and_cannot_be_mutated() -> None:
    config = _valid_config()
    with pytest.raises((AttributeError, Exception)):
        # Frozen dataclass raises AttributeError on item assignment.
        config.source_revision = "deadbeef"  # type: ignore[misc]


@pytest.mark.parametrize(
    "field_name",
    [
        "source_revision",
        "target_revision",
        "schema_version",
        "wbc_contract_hash",
        "m6_oracle_hash",
        "corpus_fixture_hash",
        "operator_approval_revision",
        "backup_identity",
        "build_revision",
        "north_star_runtime_binding",
    ],
)
def test_missing_hash_field_fails_closed(field_name: str) -> None:
    config = _valid_config(**{field_name: ""})
    with pytest.raises(CutoverConfigError, match=field_name):
        validate_config(config)


@pytest.mark.parametrize(
    "field_name",
    [
        "source_revision",
        "target_revision",
        "wbc_contract_hash",
        "m6_oracle_hash",
        "corpus_fixture_hash",
    ],
)
def test_whitespace_only_hash_field_fails_closed(field_name: str) -> None:
    config = _valid_config(**{field_name: "   "})
    with pytest.raises(CutoverConfigError, match=field_name):
        validate_config(config)


def test_wrong_north_star_runtime_binding_fails_closed() -> None:
    # ANY value other than the North Star pinned runtime must be rejected,
    # even a plausible-looking git revision.
    config = _valid_config(north_star_runtime_binding="0" * 40)
    with pytest.raises(CutoverConfigError, match="north_star_runtime_binding"):
        validate_config(config)


def test_source_revision_other_than_north_star_fails_closed() -> None:
    # For this epic the migrated runtime commit MUST equal the North Star
    # pinned runtime; a different runtime revision is rejected.
    config = _valid_config(source_revision="0" * 40)
    with pytest.raises(CutoverConfigError, match="source_revision"):
        validate_config(config)


def test_both_north_star_bindings_equal_pinned_runtime() -> None:
    # The accepted config carries the exact pinned runtime in BOTH fields.
    config = _valid_config()
    assert config.source_revision == _NS
    assert config.north_star_runtime_binding == _NS
    assert _NS == "d5848010695e28ddb9d9cbee8675d7ebe725caae"
