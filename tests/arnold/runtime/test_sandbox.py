"""Tests for neutral runtime sandbox path validators."""

from __future__ import annotations

from pathlib import Path

import pytest

from arnold.runtime.sandbox import (
    SANDBOX_CWD,
    SandboxViolation,
    get_sandbox_cwd,
    validate_terminal_command,
    validate_v4a_patch,
    validate_write_path,
)


def test_sandbox_cwd_contextvar_round_trips(tmp_path: Path) -> None:
    token = SANDBOX_CWD.set(tmp_path)
    try:
        assert get_sandbox_cwd() == tmp_path
    finally:
        SANDBOX_CWD.reset(token)

    assert get_sandbox_cwd() is None


def test_terminal_command_without_leading_cd_passes_through(tmp_path: Path) -> None:
    command = "pytest tests -q"

    assert validate_terminal_command(command, tmp_path) == command


def test_terminal_command_strips_leading_cd_to_root(tmp_path: Path) -> None:
    command = f"cd {tmp_path} && pytest"

    assert validate_terminal_command(command, tmp_path) == "pytest"


def test_terminal_command_rewrites_leading_cd_to_child_as_relative(tmp_path: Path) -> None:
    child = tmp_path / "src"
    child.mkdir()

    command = f'cd "{child}" && pytest'

    assert validate_terminal_command(command, tmp_path) == "cd src && pytest"


def test_terminal_command_refuses_leading_cd_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    other = tmp_path / "other"
    root.mkdir()
    other.mkdir()

    with pytest.raises(SandboxViolation, match="outside the sandbox root"):
        validate_terminal_command(f"cd {other} && touch file.txt", root)


def test_write_path_relative_resolves_under_root(tmp_path: Path) -> None:
    assert Path(validate_write_path("src/file.py", tmp_path)) == (
        tmp_path / "src/file.py"
    ).resolve()


def test_write_path_absolute_inside_root_passes(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "file.py"

    assert Path(validate_write_path(str(target), tmp_path)) == target.resolve()


def test_write_path_refuses_absolute_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    other = tmp_path / "other.py"
    root.mkdir()

    with pytest.raises(SandboxViolation, match="outside the sandbox root"):
        validate_write_path(str(other), root)


def test_write_path_refuses_traversal_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()

    with pytest.raises(SandboxViolation):
        validate_write_path("../escape.py", root)


def test_write_path_refuses_empty_value(tmp_path: Path) -> None:
    with pytest.raises(SandboxViolation, match="non-empty"):
        validate_write_path("", tmp_path)


def test_v4a_patch_accepts_inside_paths(tmp_path: Path) -> None:
    patch = (
        "*** Begin Patch\n"
        "*** Update File: src/main.py\n"
        "@@\n"
        "-old\n"
        "+new\n"
        "*** End Patch\n"
    )

    validate_v4a_patch(patch, tmp_path)


def test_v4a_patch_refuses_outside_absolute_path(tmp_path: Path) -> None:
    root = tmp_path / "root"
    other = tmp_path / "other.py"
    root.mkdir()
    patch = (
        "*** Begin Patch\n"
        f"*** Add File: {other}\n"
        "+leak\n"
        "*** End Patch\n"
    )

    with pytest.raises(SandboxViolation):
        validate_v4a_patch(patch, root)
