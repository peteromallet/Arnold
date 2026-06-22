import argparse
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.bakeoff.cli import build_bakeoff_parser, run_bakeoff_cli
from arnold_pipelines.megaplan.types import CliError


def test_bakeoff_run_robustness_parsing() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    build_bakeoff_parser(subparsers)

    args = parser.parse_args(["bakeoff", "run", "--idea-file", "i.md", "--profiles", "p", "--robustness", "light"])
    assert args.robustness == "light"

    args = parser.parse_args(["bakeoff", "run", "--idea-file", "i.md", "--profiles", "p"])
    assert args.robustness is None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    build_bakeoff_parser(subparsers)
    return parser


def test_bakeoff_run_mode_defaults_to_code_with_no_output() -> None:
    parser = _build_parser()
    args = parser.parse_args(["bakeoff", "run", "--idea-file", "i.md", "--profiles", "p"])
    assert args.mode == "code"
    assert args.output is None


def test_bakeoff_run_accepts_doc_mode_with_output() -> None:
    parser = _build_parser()
    args = parser.parse_args(
        ["bakeoff", "run", "--idea-file", "i.md", "--profiles", "p", "--mode", "doc", "--output", "docs/foo.md"]
    )
    assert args.mode == "doc"
    assert args.output == "docs/foo.md"


def test_bakeoff_run_rejects_metaplan_mode() -> None:
    """After 0.23's metaplan-alias removal, `--mode metaplan` is no longer a
    valid bake-off mode; argparse rejects it at the choices boundary."""
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["bakeoff", "run", "--idea-file", "i.md", "--profiles", "p", "--mode", "metaplan", "--output", "docs/foo.md"]
        )


def test_bakeoff_run_rejects_unknown_mode() -> None:
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["bakeoff", "run", "--idea-file", "i.md", "--profiles", "p", "--mode", "joke"]
        )


def test_run_bakeoff_cli_rejects_output_without_doc_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    parser = _build_parser()
    args = parser.parse_args(
        ["bakeoff", "run", "--idea-file", "i.md", "--profiles", "p", "--output", "docs/foo.md"]
    )

    # Should never reach the orchestrator — fail before dispatch.
    def boom(*_a, **_kw) -> int:  # pragma: no cover - asserts not called
        raise AssertionError("orchestrator should not be invoked when validation fails")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.bakeoff.orchestrator.run_bakeoff_run_handler", boom
    )
    with pytest.raises(CliError) as excinfo:
        run_bakeoff_cli(Path("/tmp"), args)
    assert excinfo.value.code == "invalid_args"
    assert "--output" in excinfo.value.message


def test_run_bakeoff_cli_rejects_doc_mode_without_output(monkeypatch: pytest.MonkeyPatch) -> None:
    parser = _build_parser()
    args = parser.parse_args(
        ["bakeoff", "run", "--idea-file", "i.md", "--profiles", "p", "--mode", "doc"]
    )

    def boom(*_a, **_kw) -> int:  # pragma: no cover - asserts not called
        raise AssertionError("orchestrator should not be invoked when validation fails")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.bakeoff.orchestrator.run_bakeoff_run_handler", boom
    )
    with pytest.raises(CliError) as excinfo:
        run_bakeoff_cli(Path("/tmp"), args)
    assert excinfo.value.code == "invalid_args"
    assert "--output is required" in excinfo.value.message


def test_run_bakeoff_cli_metaplan_rejected_at_parser_layer() -> None:
    """The 0.23 metaplan-alias removal means `metaplan` is rejected at the
    argparse choices boundary BEFORE `run_bakeoff_cli` runs — there is no
    downstream coercion to dispatch."""
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["bakeoff", "run", "--idea-file", "i.md", "--profiles", "p",
             "--mode", "metaplan", "--output", "docs/foo.md"]
        )


# ---------------------------------------------------------------------------
# Supervisor-tier routing smoke tests (T37)
# ---------------------------------------------------------------------------


def test_bakeoff_run_flag_off_routes_to_old_orchestrator(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When MEGAPLAN_SUPERVISOR_TIER is unset, the run action uses the old
    orchestrator path."""
    parser = _build_parser()
    args = parser.parse_args(
        ["bakeoff", "run", "--idea-file", "i.md", "--profiles", "p"]
    )
    orchestrator_called = False
    supervisor_called = False

    def fake_orchestrator(_root: Path, _args: argparse.Namespace) -> int:
        nonlocal orchestrator_called
        orchestrator_called = True
        return 0

    def fake_supervisor(_root: Path, _args: argparse.Namespace) -> int:
        nonlocal supervisor_called
        supervisor_called = True
        return 0

    monkeypatch.delenv("MEGAPLAN_SUPERVISOR_TIER", raising=False)
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.bakeoff.orchestrator.run_bakeoff_run_handler",
        fake_orchestrator,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.supervisor.bakeoff_runner.run_bakeoff_run_handler",
        fake_supervisor,
    )

    rc = run_bakeoff_cli(tmp_path, args)

    assert rc == 0
    assert orchestrator_called is True
    assert supervisor_called is False


def test_bakeoff_run_flag_off_explicit_zero_routes_to_old_orchestrator(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """MEGAPLAN_SUPERVISOR_TIER=0 keeps the old orchestrator path."""
    parser = _build_parser()
    args = parser.parse_args(
        ["bakeoff", "run", "--idea-file", "i.md", "--profiles", "p"]
    )
    orchestrator_called = False
    supervisor_called = False

    def fake_orchestrator(_root: Path, _args: argparse.Namespace) -> int:
        nonlocal orchestrator_called
        orchestrator_called = True
        return 0

    def fake_supervisor(_root: Path, _args: argparse.Namespace) -> int:
        nonlocal supervisor_called
        supervisor_called = True
        return 0

    monkeypatch.setenv("MEGAPLAN_SUPERVISOR_TIER", "0")
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.bakeoff.orchestrator.run_bakeoff_run_handler",
        fake_orchestrator,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.supervisor.bakeoff_runner.run_bakeoff_run_handler",
        fake_supervisor,
    )

    rc = run_bakeoff_cli(tmp_path, args)

    assert rc == 0
    assert orchestrator_called is True
    assert supervisor_called is False


def test_bakeoff_run_flag_on_routes_to_supervisor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """MEGAPLAN_SUPERVISOR_TIER=1 routes the run action through the
    supervisor bakeoff runner."""
    parser = _build_parser()
    args = parser.parse_args(
        ["bakeoff", "run", "--idea-file", "i.md", "--profiles", "p"]
    )
    orchestrator_called = False
    supervisor_called = False

    def fake_orchestrator(_root: Path, _args: argparse.Namespace) -> int:
        nonlocal orchestrator_called
        orchestrator_called = True
        return 0

    def fake_supervisor(_root: Path, _args: argparse.Namespace) -> int:
        nonlocal supervisor_called
        supervisor_called = True
        return 0

    monkeypatch.setenv("MEGAPLAN_SUPERVISOR_TIER", "1")
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.bakeoff.orchestrator.run_bakeoff_run_handler",
        fake_orchestrator,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.supervisor.bakeoff_runner.run_bakeoff_run_handler",
        fake_supervisor,
    )

    rc = run_bakeoff_cli(tmp_path, args)

    assert rc == 0
    assert orchestrator_called is False
    assert supervisor_called is True


def test_bakeoff_validation_before_routing_flag_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validation of mode/output happens before routing even when the
    supervisor tier flag is on."""
    parser = _build_parser()
    args = parser.parse_args(
        ["bakeoff", "run", "--idea-file", "i.md", "--profiles", "p",
         "--output", "docs/foo.md"]
    )
    orchestrator_reached = False
    supervisor_reached = False

    def fake_orchestrator(_root: Path, _args: argparse.Namespace) -> int:
        nonlocal orchestrator_reached
        orchestrator_reached = True
        raise AssertionError("should not reach orchestrator")

    def fake_supervisor(_root: Path, _args: argparse.Namespace) -> int:
        nonlocal supervisor_reached
        supervisor_reached = True
        raise AssertionError("should not reach supervisor")

    monkeypatch.setenv("MEGAPLAN_SUPERVISOR_TIER", "1")
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.bakeoff.orchestrator.run_bakeoff_run_handler",
        fake_orchestrator,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.supervisor.bakeoff_runner.run_bakeoff_run_handler",
        fake_supervisor,
    )

    with pytest.raises(CliError) as excinfo:
        run_bakeoff_cli(Path("/tmp"), args)

    assert excinfo.value.code == "invalid_args"
    assert "--output" in excinfo.value.message
    assert orchestrator_reached is False
    assert supervisor_reached is False


def test_bakeoff_validation_before_routing_flag_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validation of mode/output happens before routing when the flag is off."""
    parser = _build_parser()
    args = parser.parse_args(
        ["bakeoff", "run", "--idea-file", "i.md", "--profiles", "p",
         "--mode", "doc"]
    )
    orchestrator_reached = False

    def fake_orchestrator(_root: Path, _args: argparse.Namespace) -> int:
        nonlocal orchestrator_reached
        orchestrator_reached = True
        raise AssertionError("should not reach orchestrator")

    monkeypatch.delenv("MEGAPLAN_SUPERVISOR_TIER", raising=False)
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.bakeoff.orchestrator.run_bakeoff_run_handler",
        fake_orchestrator,
    )

    with pytest.raises(CliError) as excinfo:
        run_bakeoff_cli(Path("/tmp"), args)

    assert excinfo.value.code == "invalid_args"
    assert "--output is required" in excinfo.value.message
    assert orchestrator_reached is False


def test_bakeoff_non_run_action_stays_old_path_with_flag_on(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Non-run actions (status) do not route through the supervisor
    even when MEGAPLAN_SUPERVISOR_TIER=1."""
    parser = _build_parser()
    args = parser.parse_args(
        ["bakeoff", "status", "--exp", "test-exp"]
    )
    supervisor_imported = False

    def fake_supervisor_import():
        nonlocal supervisor_imported
        supervisor_imported = True
        raise ImportError("supervisor module should not be imported")

    def fake_status(_root: Path, _args: argparse.Namespace) -> int:
        return 0

    monkeypatch.setenv("MEGAPLAN_SUPERVISOR_TIER", "1")
    # Prevent the lazy supervisor import from succeeding
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.bakeoff.cli._load_handlers",
        lambda: {"status": fake_status},
    )

    rc = run_bakeoff_cli(tmp_path, args)

    assert rc == 0
    assert supervisor_imported is False


def test_bakeoff_run_flag_on_passes_through_args_to_supervisor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When flag-on, the supervisor handler receives the same root and args."""
    parser = _build_parser()
    idea_file = tmp_path / "i.md"
    idea_file.write_text("test idea", encoding="utf-8")
    args = parser.parse_args(
        ["bakeoff", "run", "--idea-file", str(idea_file),
         "--profiles", "p1", "p2", "--mode", "doc",
         "--output", "out.md", "--exp-id", "my-exp",
         "--allow-dirty", "--robustness", "light"]
    )
    supervisor_args: list[tuple[Path, argparse.Namespace]] = []

    def fake_supervisor(root: Path, sargs: argparse.Namespace) -> int:
        supervisor_args.append((root, sargs))
        return 0

    monkeypatch.setenv("MEGAPLAN_SUPERVISOR_TIER", "1")
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.supervisor.bakeoff_runner.run_bakeoff_run_handler",
        fake_supervisor,
    )

    rc = run_bakeoff_cli(tmp_path, args)

    assert rc == 0
    assert len(supervisor_args) == 1
    root_received, sargs_received = supervisor_args[0]
    assert root_received == tmp_path
    assert sargs_received.idea_file == str(idea_file)
    assert sargs_received.profiles == ["p1", "p2"]
    assert sargs_received.mode == "doc"
    assert sargs_received.output == "out.md"
    assert sargs_received.exp_id == "my-exp"
    assert sargs_received.allow_dirty is True
    assert sargs_received.robustness == "light"


def test_bakeoff_flag_on_non_run_actions_never_import_supervisor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify that status, compare, pick, merge, resume, abandon, and tail
    never trigger a supervisor import even when the flag is on."""
    for action in ("status", "compare", "pick", "merge", "resume", "abandon", "tail"):
        parser = _build_parser()
        arglist = ["bakeoff", action]
        if action in ("compare", "merge", "resume", "abandon", "tail"):
            arglist.extend(["--exp", "test-exp"])
        elif action == "pick":
            arglist.extend(["--exp", "test-exp", "--profile", "p1"])
        args = parser.parse_args(arglist)
        supervisor_reached = False

        def fake_supervisor(*_a, **_kw) -> int:
            nonlocal supervisor_reached
            supervisor_reached = True
            raise AssertionError(f"supervisor should not handle {action}")

        def fake_handler(*_a, **_kw) -> int:
            return 0

        monkeypatch.setenv("MEGAPLAN_SUPERVISOR_TIER", "1")
        monkeypatch.setattr(
            "arnold_pipelines.megaplan.supervisor.bakeoff_runner.run_bakeoff_run_handler",
            fake_supervisor,
        )
        # Provide fake handlers so we don't touch the real FS
        handlers = {action: fake_handler}
        # Ensure any missing handler for this action is covered
        handlers.setdefault("status", fake_handler)
        handlers.setdefault("tail", fake_handler)
        handlers.setdefault("compare", fake_handler)
        handlers.setdefault("pick", fake_handler)
        handlers.setdefault("merge", fake_handler)
        handlers.setdefault("resume", fake_handler)
        handlers.setdefault("abandon", fake_handler)
        monkeypatch.setattr(
            "arnold_pipelines.megaplan.bakeoff.cli._load_handlers",
            lambda: handlers,
        )

        rc = run_bakeoff_cli(tmp_path, args)
        assert rc == 0, f"action={action} failed"
        assert supervisor_reached is False, f"supervisor reached for {action}"
