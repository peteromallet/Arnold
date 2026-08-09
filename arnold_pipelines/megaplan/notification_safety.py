"""Safety policy for user-facing notifications.

Test and fixture executions may exercise production watchdog/repair paths, but
they must never inherit authority to contact a real user.  This module keeps
the classification small and transport-independent so producers and final
delivery boundaries can apply the same policy.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePath
from typing import Any


_TRUE = frozenset({"1", "true", "yes", "on", "test", "fixture", "pytest"})
_TEST_CONTEXT_KEYS = frozenset(
    {
        "is_test",
        "test_execution",
        "test_fixture",
        "fixture_execution",
        "notification_test_mode",
    }
)
_IDENTITY_KEYS = frozenset(
    {
        "actor_id",
        "actor_user_id",
        "bot_id",
        "bot_identity",
        "execution_identity",
        "source_kind",
    }
)
_TEST_IDENTITY = re.compile(
    r"^(?:pytest|test(?:[-_](?:bot|fixture|runner|session))?|fixture[-_](?:bot|runner))$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class NotificationSafetyDecision:
    allowed: bool
    reason: str = ""


@dataclass(frozen=True)
class FixtureSafetyDecision:
    authorized: bool
    reason: str = ""


def classify_fixture_safety(
    *,
    payload: Mapping[str, Any] | None = None,
    workspace: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> FixtureSafetyDecision:
    """Return whether fixture/test safety policy explicitly authorizes action."""

    environment = os.environ if env is None else env
    if environment.get("PYTEST_CURRENT_TEST"):
        return FixtureSafetyDecision(True, "pytest_environment")
    for key in ("MEGAPLAN_TEST_EXECUTION", "ARNOLD_TEST_EXECUTION"):
        if str(environment.get(key) or "").strip().lower() in _TRUE:
            return FixtureSafetyDecision(True, f"test_environment:{key}")

    candidate = str(workspace or "").strip()
    if candidate and _is_pytest_workspace(candidate):
        return FixtureSafetyDecision(True, "pytest_workspace")

    if isinstance(payload, Mapping):
        found = _classify_mapping(payload)
        if found:
            return FixtureSafetyDecision(True, found)

    return FixtureSafetyDecision(False)


def classify_user_notification(
    *,
    payload: Mapping[str, Any] | None = None,
    workspace: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> NotificationSafetyDecision:
    """Return whether a user-facing notification may be delivered.

    Session names are deliberately not used: names such as ``demo-chain`` can
    be legitimate in production.  Suppression requires durable fixture path
    evidence, an explicit test context/identity, or a live pytest environment.
    """

    environment = os.environ if env is None else env
    if environment.get("PYTEST_CURRENT_TEST"):
        return NotificationSafetyDecision(False, "pytest_environment")
    for key in ("MEGAPLAN_TEST_EXECUTION", "ARNOLD_TEST_EXECUTION"):
        if str(environment.get(key) or "").strip().lower() in _TRUE:
            return NotificationSafetyDecision(False, f"test_environment:{key}")
    for key in ("MEGAPLAN_ACTOR_ID", "ARNOLD_ACTOR_ID", "BOT_ID"):
        if _is_test_identity(environment.get(key)):
            return NotificationSafetyDecision(False, f"test_identity:{key}")

    candidate = str(workspace or "").strip()
    if candidate and _is_pytest_workspace(candidate):
        return NotificationSafetyDecision(False, "pytest_workspace")

    if isinstance(payload, Mapping):
        found = _classify_mapping(payload)
        if found:
            return NotificationSafetyDecision(False, found)

    return NotificationSafetyDecision(True)


def notification_context_for_current_execution(
    *, env: Mapping[str, str] | None = None
) -> dict[str, str] | None:
    """Return a durable marker projection when the current process is a test."""

    decision = classify_user_notification(env=env)
    if decision.allowed:
        return None
    return {"audience": "test_only", "reason": decision.reason}


def _classify_mapping(payload: Mapping[str, Any], *, depth: int = 0) -> str:
    if depth > 5:
        return ""
    for key, value in payload.items():
        normalized_key = str(key).strip().lower()
        if normalized_key in {"workspace", "project_dir", "cwd"}:
            if isinstance(value, (str, os.PathLike)) and _is_pytest_workspace(str(value)):
                return f"pytest_workspace:{normalized_key}"
        if normalized_key in _TEST_CONTEXT_KEYS and _truthy_test_value(value):
            return f"explicit_test_context:{normalized_key}"
        if normalized_key == "audience" and str(value).strip().lower() == "test_only":
            return "explicit_test_context:audience"
        if normalized_key in _IDENTITY_KEYS and _is_test_identity(value):
            return f"test_identity:{normalized_key}"
        if isinstance(value, Mapping):
            nested = _classify_mapping(value, depth=depth + 1)
            if nested:
                return nested
    return ""


def _truthy_test_value(value: object) -> bool:
    if value is True:
        return True
    return str(value or "").strip().lower() in _TRUE


def _is_test_identity(value: object) -> bool:
    text = str(value or "").strip()
    return bool(text and _TEST_IDENTITY.fullmatch(text))


def _is_pytest_workspace(value: str) -> bool:
    normalized = value.replace("\\", "/")
    parts = PurePath(normalized).parts
    return any(
        part == "pytest-current"
        or part.startswith("pytest-of-")
        or bool(re.fullmatch(r"pytest-\d+", part))
        for part in parts
    )


__all__ = [
    "FixtureSafetyDecision",
    "classify_fixture_safety",
    "NotificationSafetyDecision",
    "classify_user_notification",
    "notification_context_for_current_execution",
]
