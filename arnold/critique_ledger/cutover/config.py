"""Frozen cutover configuration contract (CL5 Step 11).

The :class:`CutoverConfig` is the **central immutable binding** of the entire
CL5 cutover epic. Every field is a content hash or revision string — there is
no mutable state. The two fields that pin the cutover to the exact North Star
runtime are both validated against :data:`NORTH_STAR_RUNTIME_HASH` by
:func:`validate_config`:

* ``source_revision`` — the actual runtime commit being cut over. For this
  epic the runtime commit being migrated *is* the North Star pinned runtime,
  so it MUST equal :data:`NORTH_STAR_RUNTIME_HASH`.
* ``north_star_runtime_binding`` — the dedicated, independently verifiable
  North Star pin (``NORTHSTAR.md``: "the exact editable runtime that the
  stopped r5 run actually imported"). This makes the North Star requirement
  explicit and executable: an executor cannot set it to any other value
  without :func:`validate_config` rejecting the config.

:func:`validate_config` fail-closes on *any* missing or mismatched field. In
particular it rejects any ``north_star_runtime_binding`` (or
``source_revision``) value other than
``d5848010695e28ddb9d9cbee8675d7ebe725caae``, operationalizing the North
Star's exact-runtime-binding requirement into an executable, verifiable
contract rather than a prose note.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# The exact North Star pinned runtime hash. NORTHSTAR.md pins the cutover to
# "the exact editable runtime that the stopped r5 run actually imported
# (`d5848010695e28ddb9d9cbee8675d7ebe725caae`)". This is the central binding
# of the entire epic — the cutover MUST run against this exact runtime.
NORTH_STAR_RUNTIME_HASH: str = "d5848010695e28ddb9d9cbee8675d7ebe725caae"

# Field names validated as required non-empty hash/revision strings. These are
# all content hashes or revision strings; none may be blank.
_REQUIRED_HASH_FIELDS: tuple[str, ...] = (
    "target_revision",
    "schema_version",
    "wbc_contract_hash",
    "m6_oracle_hash",
    "corpus_fixture_hash",
    "operator_approval_revision",
    "backup_identity",
    "build_revision",
)


class CutoverConfigError(ValueError):
    """Raised when a :class:`CutoverConfig` is missing a field or carries a
    hash/revision that fails the North Star exact-runtime binding.

    Subclasses :class:`ValueError` so it propagates as a plain validation
    failure rather than an unexpected crash, while remaining a distinct type
    callers (and the cutover smoke tests) can match on.
    """


@dataclass(frozen=True)
class CutoverConfig:
    """Immutable binding of every revision and hash the cutover depends on.

    All fields are content hashes or revision strings — there is no mutable
    runtime state, and the dataclass is frozen so a constructed config cannot
    be mutated in place. Two fields are pinned to the North Star runtime:

    * ``source_revision`` — the actual runtime commit being cut over. For this
      epic this MUST equal :data:`NORTH_STAR_RUNTIME_HASH`.
    * ``north_star_runtime_binding`` — the dedicated, independently verifiable
      North Star exact-runtime pin. This MUST equal
      :data:`NORTH_STAR_RUNTIME_HASH` for any accepted config.

    Both bindings are enforced by :func:`validate_config`; constructing a
    config with the wrong values is allowed (so the error is observable and
    testable), but such a config will never validate.
    """

    source_revision: str
    target_revision: str
    schema_version: str
    wbc_contract_hash: str
    m6_oracle_hash: str
    corpus_fixture_hash: str
    operator_approval_revision: str
    backup_identity: str
    build_revision: str
    north_star_runtime_binding: str

    def validate(self) -> "CutoverConfig":
        """Validate this config in place and return ``self``.

        Convenience wrapper around :func:`validate_config` so callers can write
        ``config.validate()``.
        """
        return validate_config(self)


def validate_config(config: CutoverConfig) -> CutoverConfig:
    """Fail-closed validation of every :class:`CutoverConfig` field.

    Raises :class:`CutoverConfigError` if:

    * any required hash/revision field is missing (empty/whitespace) or not a
      string;
    * ``source_revision`` is anything other than
      :data:`NORTH_STAR_RUNTIME_HASH` (for this epic the migrated runtime
      commit MUST equal the North Star pinned runtime);
    * ``north_star_runtime_binding`` is anything other than
      :data:`NORTH_STAR_RUNTIME_HASH`.

    Returns the config unchanged on success so the call composes:
    ``cfg = validate_config(CutoverConfig(...))``.
    """
    # 1. Every required field must be a non-empty string. A missing or blank
    #    hash/revision fails closed — the config cannot bind a cutover whose
    #    inputs are unknown.
    for field_name in ("source_revision", "north_star_runtime_binding"):
        value = getattr(config, field_name)
        _require_non_empty(config, field_name, value)

    for field_name in _REQUIRED_HASH_FIELDS:
        value = getattr(config, field_name)
        _require_non_empty(config, field_name, value)

    # 2. The two North Star exact-runtime bindings are immutable pins. For
    #    this epic BOTH must equal the North Star pinned runtime hash; a
    #    permissive check here could cut over the wrong runtime.
    if config.north_star_runtime_binding != NORTH_STAR_RUNTIME_HASH:
        raise CutoverConfigError(
            "north_star_runtime_binding must equal the North Star pinned "
            f"runtime {NORTH_STAR_RUNTIME_HASH!r}; got "
            f"{config.north_star_runtime_binding!r}. The cutover MUST run "
            "against the exact editable runtime the stopped r5 run imported."
        )

    if config.source_revision != NORTH_STAR_RUNTIME_HASH:
        raise CutoverConfigError(
            "source_revision must equal the North Star pinned runtime "
            f"{NORTH_STAR_RUNTIME_HASH!r} for this epic; got "
            f"{config.source_revision!r}. The migrated runtime commit MUST "
            "be the exact editable runtime the stopped r5 run imported."
        )

    return config


def _require_non_empty(config: Any, field_name: str, value: Any) -> None:
    """Raise :class:`CutoverConfigError` if ``value`` is missing or blank."""
    if not isinstance(value, str) or not value.strip():
        raise CutoverConfigError(
            f"{type(config).__name__}.{field_name} is required and must be a "
            f"non-empty hash/revision string; got {value!r}."
        )
