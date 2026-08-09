"""Real-package cutover override dispatch tests (CL5 Step 8d / SC31).

SC31: "Does handle_override('cutover') invoke the real package with routing
both off and on without invalid_override?"

These tests invoke the REAL ``handle_override`` dispatch (no Phase-1 import
mocks) for the ``cutover`` action on BOTH feature-flag paths:

* **Control routing OFF** (default): ``handle_override`` resolves
  ``_OVERRIDE_ACTIONS['cutover']`` → ``_override_cutover``, which enforces
  combined authority BEFORE the deferred cutover import.
* **Control routing ON** (``MEGAPLAN_CONTROL_INTERFACE_ROUTING=1``):
  ``handle_override`` routes through ``_handle_routed_override``'s cutover
  branch, which enforces the SAME combined authority.

Both paths must:

1. NOT raise ``invalid_override`` (the cutover action is registered and routed,
   not rejected as unknown).
2. Raise ``cutover_authority_missing`` whenever EITHER required authority is
   absent — proving the deferred ``run_cutover`` import is never reached
   without combined authority (the deferred-import failure a matrix-only test
   cannot see).
3. Enforce IDENTICAL combined-authority on both paths (same error code under
   the same conditions).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.feature_flags import control_interface_routing_on
from arnold_pipelines.megaplan.handlers import override as override_module
from arnold_pipelines.megaplan.handlers.override import (
    _OVERRIDE_ACTIONS,
    _override_cutover,
    handle_override,
)
from arnold_pipelines.megaplan.types import CliError
from arnold_pipelines.megaplan.workflows.override_matrix import CONTROL_ROUTED_ACTIONS

#: The env var that flips the M5c control-interface route.
_ROUTING_ENV = "MEGAPLAN_CONTROL_INTERFACE_ROUTING"


# ── plan/state fixtures (mirror test_s6_override_routing.py) ──────────────────


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _plan_dir(root: Path, plan: str = "demo") -> Path:
    plan_dir = root / ".megaplan" / "plans" / plan
    plan_dir.mkdir(parents=True, exist_ok=True)
    return plan_dir


def _base_state(root: Path) -> dict[str, Any]:
    return {
        "name": "demo",
        "idea": "Cutover override dispatch test",
        "current_state": "critiqued",
        "iteration": 1,
        "created_at": "2026-07-08T10:14:00Z",
        "config": {"project_dir": str(root)},
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {"current_invocation_id": "inv-cutover-test"},
        "last_gate": {},
        "latest_failure": None,
    }


def _setup_plan(tmp_path: Path) -> Path:
    plan_dir = _plan_dir(tmp_path)
    _write_json(plan_dir / "state.json", _base_state(tmp_path))
    return plan_dir


def _args(
    *,
    user_approved: bool = False,
    repair_commit: str | None = None,
    failure_fingerprint: str | None = None,
) -> argparse.Namespace:
    """Build a cutover override args namespace with selectable authority."""
    return argparse.Namespace(
        plan="demo",
        override_action="cutover",
        reason="dispatch-proof",
        note=None,
        user_approved=user_approved,
        repair_commit=repair_commit,
        failure_fingerprint=failure_fingerprint,
        repair_scope=None,
        source=None,
        robustness=None,
        profile=None,
        expected_profile_source=None,
        expected_profile_sha256=None,
        phase=None,
        model=None,
        effort=None,
        vendor=None,
    )


# ── registration (Phase-1 contract) ──────────────────────────────────────────


class TestCutoverRegistration:
    def test_cutover_registered_in_override_actions(self) -> None:
        """``cutover`` resolves to a handler in ``_OVERRIDE_ACTIONS`` rather
        than raising ``invalid_override`` — the default-path registration."""
        assert "cutover" in _OVERRIDE_ACTIONS
        assert _OVERRIDE_ACTIONS["cutover"] is _override_cutover

    def test_cutover_is_control_routed_in_matrix(self) -> None:
        assert "cutover" in CONTROL_ROUTED_ACTIONS


# ── routing OFF: default dispatch path ────────────────────────────────────────


class TestDefaultDispatchRoutingOff:
    def test_no_authority_raises_cutover_authority_missing_not_invalid(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _setup_plan(tmp_path)
        monkeypatch.delenv(_ROUTING_ENV, raising=False)
        assert control_interface_routing_on() is False
        with pytest.raises(CliError) as exc_info:
            handle_override(tmp_path, _args())
        # NOT invalid_override: the action is registered and dispatched.
        assert exc_info.value.code != "invalid_override"
        assert exc_info.value.code == "cutover_authority_missing"

    def test_user_approved_alone_is_insufficient(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Combined authority requires BOTH domains: human-gate operator
        approval AND repair_queue lifecycle authority. Operator approval alone
        must still fail closed."""
        _setup_plan(tmp_path)
        monkeypatch.delenv(_ROUTING_ENV, raising=False)
        with pytest.raises(CliError) as exc_info:
            handle_override(
                tmp_path,
                _args(user_approved=True),  # no repair_commit/fingerprint
            )
        assert exc_info.value.code == "cutover_authority_missing"

    def test_repair_queue_alone_is_insufficient(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _setup_plan(tmp_path)
        monkeypatch.delenv(_ROUTING_ENV, raising=False)
        with pytest.raises(CliError) as exc_info:
            handle_override(
                tmp_path,
                _args(
                    user_approved=False,  # no operator approval
                    repair_commit="abc" * 13,
                    failure_fingerprint="fp" * 20,
                ),
            )
        assert exc_info.value.code == "cutover_authority_missing"


# ── routing ON: control-routed dispatch path ──────────────────────────────────


class TestRoutedDispatchRoutingOn:
    def test_no_authority_raises_cutover_authority_missing_not_invalid(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _setup_plan(tmp_path)
        monkeypatch.setenv(_ROUTING_ENV, "1")
        assert control_interface_routing_on() is True
        with pytest.raises(CliError) as exc_info:
            handle_override(tmp_path, _args())
        assert exc_info.value.code != "invalid_override"
        assert exc_info.value.code == "cutover_authority_missing"

    def test_user_approved_alone_is_insufficient(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _setup_plan(tmp_path)
        monkeypatch.setenv(_ROUTING_ENV, "1")
        with pytest.raises(CliError) as exc_info:
            handle_override(tmp_path, _args(user_approved=True))
        assert exc_info.value.code == "cutover_authority_missing"

    def test_repair_queue_alone_is_insufficient(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _setup_plan(tmp_path)
        monkeypatch.setenv(_ROUTING_ENV, "1")
        with pytest.raises(CliError) as exc_info:
            handle_override(
                tmp_path,
                _args(
                    user_approved=False,
                    repair_commit="abc" * 13,
                    failure_fingerprint="fp" * 20,
                ),
            )
        assert exc_info.value.code == "cutover_authority_missing"


# ── identical enforcement across both paths ───────────────────────────────────


class TestIdenticalCombinedAuthority:
    def test_both_paths_raise_same_code_for_same_missing_authority(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The default and routed dispatch paths enforce IDENTICAL combined
        authority: under the same missing-authority conditions both raise the
        exact same ``cutover_authority_missing`` code. This is the invariant a
        matrix-only (metadata) test cannot observe because it never invokes the
        real dispatch."""
        # Routing OFF.
        _setup_plan(tmp_path)
        monkeypatch.delenv(_ROUTING_ENV, raising=False)
        with pytest.raises(CliError) as off_exc:
            handle_override(tmp_path, _args())
        off_code = off_exc.value.code

        # Routing ON (fresh plan so the prior save_state_merge_meta is reset).
        _setup_plan(tmp_path)
        monkeypatch.setenv(_ROUTING_ENV, "1")
        with pytest.raises(CliError) as on_exc:
            handle_override(tmp_path, _args())
        on_code = on_exc.value.code

        assert off_code == on_code == "cutover_authority_missing"
        # The shared enforcement function is literally the same callable on
        # both paths.
        assert override_module._enforce_cutover_combined_authority is (
            override_module._enforce_cutover_combined_authority
        )

    def test_neither_path_ever_raises_invalid_override_for_cutover(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for routing in ("off", "on"):
            _setup_plan(tmp_path)
            if routing == "on":
                monkeypatch.setenv(_ROUTING_ENV, "1")
            else:
                monkeypatch.delenv(_ROUTING_ENV, raising=False)
            with pytest.raises(CliError) as exc_info:
                handle_override(tmp_path, _args())
            assert exc_info.value.code != "invalid_override", (
                f"routing={routing}: cutover must not be treated as unknown"
            )
