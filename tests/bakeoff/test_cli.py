import argparse
from pathlib import Path

import pytest

from megaplan.bakeoff.cli import build_bakeoff_parser, run_bakeoff_cli
from megaplan.types import CliError


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


def test_bakeoff_run_accepts_metaplan_mode_with_output() -> None:
    parser = _build_parser()
    args = parser.parse_args(
        ["bakeoff", "run", "--idea-file", "i.md", "--profiles", "p", "--mode", "metaplan", "--output", "docs/foo.md"]
    )
    assert args.mode == "metaplan"
    assert args.output == "docs/foo.md"


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
        "megaplan.bakeoff.orchestrator.run_bakeoff_run_handler", boom
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
        "megaplan.bakeoff.orchestrator.run_bakeoff_run_handler", boom
    )
    with pytest.raises(CliError) as excinfo:
        run_bakeoff_cli(Path("/tmp"), args)
    assert excinfo.value.code == "invalid_args"
    assert "--output is required" in excinfo.value.message


def test_run_bakeoff_cli_normalizes_metaplan_to_doc_before_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = _build_parser()
    args = parser.parse_args(
        ["bakeoff", "run", "--idea-file", "i.md", "--profiles", "p",
         "--mode", "metaplan", "--output", "docs/foo.md"]
    )
    seen: dict[str, object] = {}

    def fake(_root: Path, ns: argparse.Namespace) -> int:
        seen["mode"] = ns.mode
        seen["output"] = ns.output
        return 0

    monkeypatch.setattr(
        "megaplan.bakeoff.orchestrator.run_bakeoff_run_handler", fake
    )
    assert run_bakeoff_cli(Path("/tmp"), args) == 0
    assert seen == {"mode": "doc", "output": "docs/foo.md"}
