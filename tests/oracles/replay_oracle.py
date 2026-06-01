"""Shared replay helpers for control-interface strangler tests.

The helpers in this module capture the legacy override path as an oracle. They
intentionally do not require a routed result yet; later routing tests can use
``assert_replay_parity`` once an action has been moved behind the control route.
"""

from __future__ import annotations

import json
import difflib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import megaplan
from tests.conftest import PlanFixture, load_state


ActionInvoker = Callable[[PlanFixture], Any]


@dataclass(frozen=True)
class ReplaySnapshot:
    """A normalized result from one override-path invocation."""

    action: str
    accepted: bool
    response: Mapping[str, Any] | None
    exception: Mapping[str, Any] | None
    state: Mapping[str, Any]
    artifacts: Mapping[str, Any]
    events: tuple[Mapping[str, Any], ...]


def capture_events(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Patch observability emission and return the captured event payloads."""

    events: list[dict[str, Any]] = []

    def _emit(
        kind: str,
        *,
        plan_dir: Path,
        payload: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        del plan_dir
        event = {"kind": kind, "payload": payload or {}, **kwargs}
        events.append(event)
        return event

    monkeypatch.setattr("megaplan.observability.events.emit", _emit)
    return events


def capture_legacy_action(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
    *,
    action: str,
    invoke: ActionInvoker,
    artifact_names: Iterable[str] = (),
) -> ReplaySnapshot:
    """Run one legacy override action and snapshot its observable output."""

    events = capture_events(monkeypatch)
    response: Mapping[str, Any] | None = None
    exception: Mapping[str, Any] | None = None
    accepted = True

    try:
        response = megaplan.handle_override(plan_fixture.root, invoke(plan_fixture))
    except megaplan.CliError as exc:
        accepted = False
        exception = {
            "code": exc.code,
            "message": exc.message,
            "extra": dict(exc.extra),
        }

    artifacts = {
        name: _read_artifact(plan_fixture.plan_dir / name)
        for name in artifact_names
        if (plan_fixture.plan_dir / name).exists()
    }
    return ReplaySnapshot(
        action=action,
        accepted=accepted,
        response=_normalized_response(response, plan_fixture.plan_dir),
        exception=exception,
        state=_normalized_state(load_state(plan_fixture.plan_dir)),
        artifacts=artifacts,
        events=tuple(events),
    )


def capture_routed_action(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
    *,
    action: str,
    invoke: ActionInvoker,
    artifact_names: Iterable[str] = (),
) -> ReplaySnapshot:
    """Run one routed override action behind the control-interface flag."""

    monkeypatch.setenv("MEGAPLAN_CONTROL_INTERFACE_ROUTING", "1")
    return capture_legacy_action(
        plan_fixture,
        monkeypatch,
        action=action,
        invoke=invoke,
        artifact_names=artifact_names,
    )


def assert_replay_parity(
    *,
    legacy: ReplaySnapshot,
    routed: ReplaySnapshot | None,
    fields: Iterable[str] = ("accepted", "response", "exception", "state", "artifacts", "events"),
) -> None:
    """Compare routed output to a legacy snapshot for actions already routed.

    Passing ``routed=None`` is a deliberate no-op so Step 11 can establish the
    oracle before any actions are migrated. Later steps should pass a routed
    snapshot and choose the fields that action is ready to enforce.
    """

    if routed is None:
        return

    for field in fields:
        routed_value = getattr(routed, field)
        legacy_value = getattr(legacy, field)
        if routed_value != legacy_value:
            legacy_str = json.dumps(legacy_value, indent=2, sort_keys=True, default=str)
            routed_str = json.dumps(routed_value, indent=2, sort_keys=True, default=str)
            diff = "\n".join(
                difflib.unified_diff(
                    legacy_str.splitlines(),
                    routed_str.splitlines(),
                    fromfile="legacy",
                    tofile="routed",
                    n=3,
                )
            )
            pytest.fail(f"{legacy.action} replay mismatch for {field}\n{diff}")


def _read_artifact(path: Path) -> Any:
    raw = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(raw)
    return raw


def _normalized_response(response: Mapping[str, Any] | None, plan_dir: Path) -> Mapping[str, Any] | None:
    if response is None:
        return None
    normalized = dict(response)
    plan_file = normalized.get("plan_file")
    if isinstance(plan_file, str):
        try:
            normalized["plan_file"] = "{{plan_dir}}/" + str(Path(plan_file).relative_to(plan_dir))
        except ValueError:
            normalized["plan_file"] = plan_file
    return normalized


def _normalized_state(state: Mapping[str, Any]) -> dict[str, Any]:
    raw_config = state.get("config")
    config = dict(raw_config) if isinstance(raw_config, Mapping) else raw_config
    if isinstance(config, dict):
        config["project_dir"] = "{{project_dir}}"
    raw_meta = state.get("meta")
    meta = dict(raw_meta) if isinstance(raw_meta, Mapping) else raw_meta
    if isinstance(meta, dict):
        meta.pop("current_invocation_id", None)
    return {
        "current_state": state.get("current_state"),
        "config": config,
        "meta": meta,
        "latest_failure": state.get("latest_failure"),
        "active_step": state.get("active_step"),
        "resume_cursor": state.get("resume_cursor"),
    }
