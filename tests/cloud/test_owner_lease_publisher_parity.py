from __future__ import annotations

import inspect
import json
import shlex
import subprocess
from pathlib import Path

import arnold_pipelines.megaplan.cli as megaplan_cli
from arnold_pipelines.megaplan import agentbox_adapter
from arnold_pipelines.megaplan.cloud import cli as cloud_cli
from arnold_pipelines.megaplan.cloud import template as cloud_template
from arnold_pipelines.megaplan.cloud import liveness_lease
from arnold_pipelines.megaplan.cloud.spec import (
    AutoSpec,
    ChainSubSpec,
    CloudSpec,
    CodexSpec,
    MegaplanSpec,
    RepoSpec,
    ResourcesSpec,
)


def _spec(*, mode: str) -> CloudSpec:
    return CloudSpec(
        provider="ssh",
        repo=RepoSpec(
            url="https://github.com/example/app.git", workspace="/workspace/app"
        ),
        agents={"default": "codex"},
        codex=CodexSpec(),
        mode=mode,
        megaplan=MegaplanSpec(),
        resources=ResourcesSpec(),
        secrets=[],
        auto=(
            AutoSpec(plan_name="demo-plan", idea_file="/workspace/app/idea.txt")
            if mode == "auto"
            else None
        ),
        chain=(
            ChainSubSpec(spec="/workspace/app/chain.yaml") if mode == "chain" else None
        ),
    )


def _assert_managed_contract(command: str, *, session: str, run_kind: str) -> None:
    assert (
        "unset ARNOLD_LIVENESS_OWNER_PID ARNOLD_LIVENESS_OWNER_PROCESS_START" in command
    )
    assert f"ARNOLD_REPAIR_SESSION={session}" in command
    assert f"ARNOLD_REPAIR_RUN_KIND={run_kind}" in command
    assert "ARNOLD_REPAIR_MARKER_DIR=" in command


def test_chain_plan_auto_and_epic_launchers_share_one_environment_contract() -> None:
    chain = cloud_cli._chain_start_command(
        "/workspace/app/chain.yaml",
        project_dir="/workspace/app",
        repair_session="chain-session",
    )
    plan = cloud_cli._plan_auto_command(
        "demo-plan",
        workspace="/workspace/app",
        log_relative=".megaplan/plan.log",
        repair_session="plan-session",
    )
    epic = cloud_cli._epic_chain_start_command(
        "/workspace/app/epic-chain.yaml",
        workspace="/workspace/app",
        log_relative=".megaplan/epic.log",
        repair_session="epic-session",
    )

    _assert_managed_contract(chain, session="chain-session", run_kind="chain")
    _assert_managed_contract(plan, session="plan-session", run_kind="plan")
    _assert_managed_contract(epic, session="epic-session", run_kind="epic_chain")
    for command in (chain, plan, epic):
        assert "python" in command and "arnold_pipelines.megaplan" in command


def test_bootstrap_and_image_entrypoints_materialize_marker_before_managed_run() -> (
    None
):
    bootstrap = cloud_cli._bootstrap_launch_command(
        workspace="/workspace/app",
        remote_idea_path="/workspace/app/idea.txt",
        plan_name="demo-plan",
        robustness="standard",
        session_name="plan-session",
    )
    _assert_managed_contract(bootstrap, session="plan-session", run_kind="plan")
    assert '"run_id":' in bootstrap
    assert bootstrap.index('"run_id":') < bootstrap.index(
        "arnold_pipelines.megaplan init"
    )
    # T-0021: bootstrap is manifest-bound — the pin gate precedes init and no
    # engine_dir argument / shared-root fallback is consulted.
    assert "isolated_chain_runtime_binding_drift" in bootstrap
    assert 'PYTHONPATH="$ENGINE_DIR"' in bootstrap
    assert 'PYTHONPATH="/workspace/arnold' not in bootstrap

    auto_entrypoint = cloud_template._auto_command(_spec(mode="auto"))
    chain_entrypoint = cloud_template._chain_command(_spec(mode="chain"))
    _assert_managed_contract(auto_entrypoint, session="agent", run_kind="plan")
    _assert_managed_contract(chain_entrypoint, session="agent", run_kind="chain")
    assert "arnold_pipelines.megaplan auto" in auto_entrypoint
    assert "arnold-chain" in chain_entrypoint
    assert '"run_id": str(uuid.uuid4())' in auto_entrypoint
    assert '"run_id": str(uuid.uuid4())' in chain_entrypoint
    for quoted_script in (auto_entrypoint, chain_entrypoint):
        script = shlex.split(quoted_script)[0]
        parsed = subprocess.run(
            ["bash", "-n"], input=script, text=True, capture_output=True, check=False
        )
        assert parsed.returncode == 0, parsed.stderr


def test_managed_cli_has_one_publisher_boundary_and_chain_has_no_private_copy() -> None:
    main_source = inspect.getsource(megaplan_cli.main)
    assert "with managed_runner_lifecycle():" in main_source

    root = Path(__file__).resolve().parents[2]
    chain_source = (root / "arnold_pipelines/megaplan/chain/__init__.py").read_text(
        encoding="utf-8"
    )
    production = root / "arnold_pipelines/megaplan"
    start_callers = []
    for path in production.rglob("*.py"):
        if path.name == "liveness_lease.py":
            continue
        if "start_from_environment" in path.read_text(encoding="utf-8"):
            start_callers.append(path.relative_to(root).as_posix())

    assert "start_from_environment" not in chain_source
    assert start_callers == []


def test_cli_boundary_publishes_during_run_and_terminalizes_after_return(
    tmp_path: Path, monkeypatch
) -> None:
    marker_dir = tmp_path / "markers"
    liveness_lease.prepare_managed_run_marker(
        "demo",
        marker_dir=marker_dir,
        workspace=tmp_path,
        remote_spec=tmp_path / "plan.json",
        run_kind="plan",
        run_id="run-1",
    )
    monkeypatch.setenv("ARNOLD_REPAIR_SESSION", "demo")
    monkeypatch.setenv("ARNOLD_REPAIR_MARKER_DIR", str(marker_dir))

    def fake_main(_argv):
        marker = json.loads((marker_dir / "demo.json").read_text(encoding="utf-8"))
        observed = liveness_lease.observe_liveness_lease(marker, marker_dir=marker_dir)
        assert observed["state"] == "live"
        return 17

    monkeypatch.setattr(megaplan_cli, "_main", fake_main)
    assert megaplan_cli.main(["auto"]) == 17
    marker = json.loads((marker_dir / "demo.json").read_text(encoding="utf-8"))
    assert (
        liveness_lease.observe_liveness_lease(marker, marker_dir=marker_dir)["state"]
        == "expired"
    )


def test_every_cloud_managed_command_builder_routes_through_contract_helper() -> None:
    source = inspect.getsource(cloud_cli)
    for function_name in (
        "_chain_start_command",
        "_plan_auto_command",
        "_epic_chain_start_command",
        "_bootstrap_launch_command",
    ):
        start = source.index(f"def {function_name}(")
        next_def = source.find("\ndef ", start + 5)
        body = source[start : next_def if next_def >= 0 else None]
        assert "_managed_run_env_prefix(" in body, function_name

    adapter_command = agentbox_adapter._chain_start_command(
        Path("/workspace/app/chain.yaml"),
        Path("/workspace/app"),
        session="agentbox-demo",
        marker_dir=Path("/workspace/app/.megaplan/cloud-sessions"),
    )
    assert adapter_command[:2] == ("env", "ARNOLD_REPAIR_SESSION=agentbox-demo")
    assert "ARNOLD_REPAIR_RUN_KIND=chain" in adapter_command
    assert "prepare_managed_run_marker(" in inspect.getsource(
        agentbox_adapter.MegaplanChainHandler.launch
    )


def test_recovery_launchers_preserve_the_managed_owner_contract() -> None:
    root = Path(__file__).resolve().parents[2]
    wrappers = root / "arnold_pipelines/megaplan/cloud/wrappers"
    discover = (wrappers / "arnold-cloud-discover").read_text(encoding="utf-8")
    watchdog = (wrappers / "arnold-watchdog").read_text(encoding="utf-8")
    repair_loop = (wrappers / "arnold-repair-loop").read_text(encoding="utf-8")
    chain_wrapper = (wrappers / "arnold-chain").read_text(encoding="utf-8")

    # Discovery persists commands that may be replayed independently, so the
    # route must travel with each command instead of relying on caller state.
    assert "def _managed_route(" in discover
    assert '_managed_route(session, "plan")' in discover
    assert '_managed_route(session, "chain")' in discover

    # Mechanical recovery executes stored commands below a supervisor.  Both
    # recovery owners must clear inherited ownership and bind the replacement
    # to the exact marker/session/kind before exec.
    required = (
        "unset ARNOLD_LIVENESS_OWNER_PID ARNOLD_LIVENESS_OWNER_PROCESS_START",
        "export ARNOLD_REPAIR_MARKER_DIR=",
        "export ARNOLD_REPAIR_SESSION=",
        "export ARNOLD_REPAIR_RUN_KIND=",
    )
    for source in (watchdog, repair_loop):
        for fragment in required:
            assert fragment in source

    # Markerless tmux discovery is diagnostic-only. It must not manufacture a
    # launch identity that could authorize repair/relaunch/retirement.
    assert '"run_id": str(uuid.uuid4())' not in watchdog
    assert "Discovery is retained for operator diagnostics only" in watchdog
    assert chain_wrapper.count(
        "unset ARNOLD_LIVENESS_OWNER_PID ARNOLD_LIVENESS_OWNER_PROCESS_START"
    ) == 2
    hot_env_fence = (
        "set +a; fi; unset ARNOLD_LIVENESS_OWNER_PID "
        "ARNOLD_LIVENESS_OWNER_PROCESS_START"
    )
    assert watchdog.count(hot_env_fence) >= 2
    assert hot_env_fence in repair_loop
    # arnold-chain loads the (credentials-only) hot env once at wrapper top,
    # AFTER pinning ARNOLD_RUNTIME_MANIFEST and BEFORE the mandatory manifest
    # gate / owner-lease unset at each launch boundary (G2 finding 1): the
    # pin is reasserted after the reload, so a stale hot-env value can never
    # select the runtime the launch binds to.
    hot_env_reload = (
        "if [[ -f /workspace/.cloud-hot-env ]]; then set -a; "
        ". /workspace/.cloud-hot-env; set +a; fi;"
    )
    assert chain_wrapper.count(hot_env_reload) == 1
    assert chain_wrapper.index(
        "PINNED_RUNTIME_MANIFEST"
    ) < chain_wrapper.index(hot_env_reload) < chain_wrapper.index(
        "unset ARNOLD_LIVENESS_OWNER_PID ARNOLD_LIVENESS_OWNER_PROCESS_START"
    )

    for wrapper in (
        "arnold-chain",
        "arnold-cloud-discover",
        "arnold-watchdog",
        "arnold-repair-loop",
    ):
        parsed = subprocess.run(
            ["bash", "-n", str(wrappers / wrapper)],
            text=True,
            capture_output=True,
            check=False,
        )
        assert parsed.returncode == 0, f"{wrapper}: {parsed.stderr}"
