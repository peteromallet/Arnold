from __future__ import annotations

from pathlib import Path

from arnold_pipelines.megaplan.cloud.babysitter import launch
from arnold_pipelines.megaplan.cloud.babysitter.routing import (
    CONTINUATION_FIXER_ROLES,
    CONTINUATION_MUSE_MODEL,
    CONTINUATION_MUSE_THINKING,
    resolve_babysitter_routing,
)


def test_babysitter_routing_defaults_to_legacy_deepseek() -> None:
    route = resolve_babysitter_routing({})
    assert route.mode == "legacy"
    assert route.controller_backend == "hermes"
    assert route.controller_model == "omp:deepseek/deepseek-v4-flash"
    assert route.investigator_model == route.controller_model


def test_codex_override_resolves_controller_and_investigators() -> None:
    route = resolve_babysitter_routing({"ARNOLD_BABYSITTER_ROUTING": "codex"})
    assert route.as_dict() == {
        "mode": "codex",
        "controller_backend": "codex",
        "controller_model": "codex:gpt-5.6-luna",
        "investigator_backend": "codex",
        "investigator_model": "codex:gpt-5.6-luna",
    }


def test_unknown_routing_value_fails_closed() -> None:
    import pytest

    with pytest.raises(ValueError, match="ARNOLD_BABYSITTER_ROUTING"):
        resolve_babysitter_routing({"ARNOLD_BABYSITTER_ROUTING": "deepseek"})


def test_continuation_route_closes_every_fixer_role_to_muse_high() -> None:
    session = "native-build-forward-c2-bb000694-20260903-r4"
    route = resolve_babysitter_routing({}, session=session)
    assert route.closed is True
    assert route.mode == "continuation-muse"
    assert route.controller_model == CONTINUATION_MUSE_MODEL
    assert route.investigator_model == CONTINUATION_MUSE_MODEL
    assert route.thinking == CONTINUATION_MUSE_THINKING == "high"
    assert route.as_dict()["role_models"] == {
        role: CONTINUATION_MUSE_MODEL for role in CONTINUATION_FIXER_ROLES
    }


def test_continuation_route_rejects_ambient_alternate_model() -> None:
    session = "native-build-forward-c2-bb000694-20260903-r4"
    import pytest

    with pytest.raises(ValueError, match="closed to Muse"):
        resolve_babysitter_routing(
            {"ARNOLD_BABYSITTER_MODEL": "omp:deepseek/deepseek-v4-flash"},
            session=session,
        )
    with pytest.raises(ValueError, match="closed to Muse"):
        resolve_babysitter_routing(
            {"ARNOLD_BABYSITTER_ROUTING": "codex"}, session=session
        )


def test_continuation_route_normalizes_all_thinking_inputs_to_high() -> None:
    session = "native-build-forward-c2-bb000694-20260903-r4"
    for level in ("auto", "off", "minimal", "low", "medium", "high", "xhigh", "max"):
        route = resolve_babysitter_routing(
            {"ARNOLD_BABYSITTER_MODEL": f"{CONTINUATION_MUSE_MODEL}:{level}"},
            session=session,
        )
        assert route.controller_model == CONTINUATION_MUSE_MODEL
        assert route.thinking == "high"


def test_continuation_managed_spec_pins_nested_omp_dispatch_to_muse_high(
    tmp_path: Path,
) -> None:
    goal = tmp_path / "goal.md"
    goal.write_text("prove movement", encoding="utf-8")
    session = "native-build-forward-c2-bb000694-20260903-r4"
    route = resolve_babysitter_routing({}, session=session)
    ctx = {
        "engine_root": Path(__file__).resolve().parents[2],
        "run_root": tmp_path / "run",
        "session": session,
        "occurrence": "occurrence",
        "run_id": "run",
        "plan": "native-c2",
        "routing": route,
        "model": route.controller_model,
        "difficulty": 8,
        "remote_spec": "",
        "workspace": str(tmp_path),
        "mode": "superfixer",
    }
    spec = launch._managed_spec(ctx, goal_path=goal, identity_key="identity")
    assert spec.backend == "babysitter"
    assert spec.model == CONTINUATION_MUSE_MODEL
    assert spec.reasoning_effort == CONTINUATION_MUSE_THINKING == "high"
    assert f"--model={CONTINUATION_MUSE_MODEL}:{CONTINUATION_MUSE_THINKING}" in spec.argv
    joined = " ".join(spec.argv).lower()
    assert all(name not in joined for name in ("deepseek", "codex", "luna", "grok"))
    assert spec.links["routing"]["thinking"] == CONTINUATION_MUSE_THINKING


def test_managed_spec_records_codex_route_and_sealed_goal(tmp_path: Path) -> None:
    goal = tmp_path / "goal.md"
    goal.write_text("prove movement", encoding="utf-8")
    route = resolve_babysitter_routing({"ARNOLD_BABYSITTER_ROUTING": "codex"})
    ctx = {
        "engine_root": Path(__file__).resolve().parents[2],
        "run_root": tmp_path / "run",
        "session": "astrid-first",
        "occurrence": "occurrence",
        "run_id": "run",
        "plan": "m7",
        "routing": route,
        "model": route.controller_model,
        "difficulty": 8,
        "remote_spec": "",
        "workspace": str(tmp_path),
        "mode": "superfixer",
    }
    spec = launch._managed_spec(ctx, goal_path=goal, identity_key="identity")
    assert spec.backend == "codex"
    assert spec.model == "codex:gpt-5.6-luna"
    assert spec.stdin_path == goal
    # The controller boundary strips ambient runtime-identity env (occurrence
    # c2f73c7ddcef) before codex exec.
    assert spec.argv[:5] == (
        "/usr/bin/env",
        "-u",
        "MEGAPLAN_RUNTIME_LAUNCH_SEED",
        "-u",
        "ARNOLD_RUNTIME_MANIFEST",
    )
    assert spec.argv[5:7] == ("codex", "exec")
    assert "gpt-5.6-luna" in spec.argv
    assert all("deepseek" not in arg for arg in spec.argv)
    assert spec.links["routing"] == route.as_dict()


def test_legacy_managed_spec_keeps_hermes_controller(tmp_path: Path) -> None:
    goal = tmp_path / "goal.md"
    goal.write_text("prove movement", encoding="utf-8")
    route = resolve_babysitter_routing({})
    ctx = {
        "engine_root": Path(__file__).resolve().parents[2],
        "run_root": tmp_path / "run",
        "session": "astrid-first",
        "occurrence": "occurrence",
        "run_id": "run",
        "plan": "m7",
        "routing": route,
        "model": route.controller_model,
        "difficulty": 8,
        "remote_spec": "",
        "workspace": str(tmp_path),
        "mode": "superfixer",
    }
    spec = launch._managed_spec(ctx, goal_path=goal, identity_key="identity")
    assert spec.backend == "babysitter"
    assert spec.model == route.controller_model
    assert spec.stdin_path is None
    assert any("launch_hermes_agent.py" in arg for arg in spec.argv)


def test_launch_receipt_contains_resolved_controller_and_investigator_models(tmp_path: Path) -> None:
    route = resolve_babysitter_routing({"ARNOLD_BABYSITTER_ROUTING": "codex"})
    ctx = {
        "session": "astrid-first",
        "occurrence": "occurrence",
        "run_id": "run",
        "run_root": tmp_path,
        "plan": "m7",
        "run_kind": "chain",
        "workspace": str(tmp_path),
        "remote_spec": "",
        "mode": "superfixer",
        "model": route.controller_model,
        "routing": route,
        "launched_at": "2026-08-20T10:00:00Z",
    }
    payload = launch._receipt_payload(ctx, status="running")
    assert payload["controller_backend"] == "codex"
    assert payload["controller_model"] == "codex:gpt-5.6-luna"
    assert payload["investigator_backend"] == "codex"
    assert payload["investigator_model"] == "codex:gpt-5.6-luna"
