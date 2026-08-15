"""Normalized maintenance environment namespace helper.

Maintenance custody must always name an explicit environment namespace so a
test or fixture store can never silently alias a production ledger.  This
module is the single place that accepts an explicit namespace argument or a
``ARNOLD_MAINTENANCE_ENVIRONMENT`` env value and normalizes it to one of the
four accepted identities:

* ``production``
* ``staging``
* ``test``
* ``fixture``

Anything else fails closed (raises) rather than guessing.  Case and surrounding
whitespace are normalized, but no other alias is accepted: ``prod`` does not
mean ``production`` here.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any


#: Env var consulted when no explicit namespace is provided.
MAINTENANCE_ENVIRONMENT_ENV_VAR = "ARNOLD_MAINTENANCE_ENVIRONMENT"

#: The complete, closed set of accepted maintenance environment namespaces.
VALID_MAINTENANCE_ENVIRONMENTS: tuple[str, ...] = (
    "production",
    "staging",
    "test",
    "fixture",
)


class MaintenanceEnvironmentError(ValueError):
    """Raised when a maintenance environment namespace is missing or invalid."""


def _normalize(raw: Any) -> str:
    return str(raw or "").strip().casefold()


def resolve_maintenance_environment(
    explicit: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Normalize a maintenance environment namespace, failing closed.

    Prefers the *explicit* argument, then
    :data:`MAINTENANCE_ENVIRONMENT_ENV_VAR`.  Returns the canonical lowercase
    namespace (``production``, ``staging``, ``test``, or ``fixture``) and
    raises :class:`MaintenanceEnvironmentError` for any missing or unrecognized
    identity.
    """
    if explicit is not None:
        raw = explicit
    else:
        env = os.environ if environ is None else environ
        raw = env.get(MAINTENANCE_ENVIRONMENT_ENV_VAR)

    normalized = _normalize(raw)
    if not normalized:
        raise MaintenanceEnvironmentError(
            "maintenance environment namespace is required; set "
            f"{MAINTENANCE_ENVIRONMENT_ENV_VAR} or pass an explicit namespace"
        )
    if normalized not in VALID_MAINTENANCE_ENVIRONMENTS:
        raise MaintenanceEnvironmentError(
            f"unknown maintenance environment namespace {raw!r}; expected one of "
            f"{sorted(VALID_MAINTENANCE_ENVIRONMENTS)}"
        )
    return normalized


def is_production(namespace: str | None) -> bool:
    """Return ``True`` when *namespace* normalizes to ``production``.

    Invalid identities are not silently treated as non-production: this
    predicate reuses :func:`resolve_maintenance_environment` and therefore
    fails closed instead of returning ``False`` for garbage.
    """
    return resolve_maintenance_environment(namespace) == "production"


def is_non_production(namespace: str | None) -> bool:
    """Return ``True`` when *namespace* normalizes to a non-production identity."""
    return resolve_maintenance_environment(namespace) != "production"


__all__ = [
    "MAINTENANCE_ENVIRONMENT_ENV_VAR",
    "MaintenanceEnvironmentError",
    "VALID_MAINTENANCE_ENVIRONMENTS",
    "is_non_production",
    "is_production",
    "resolve_maintenance_environment",
]
