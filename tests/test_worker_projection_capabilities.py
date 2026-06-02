from __future__ import annotations

from megaplan.workers._projection_caps import (
    codex_projection_capabilities,
    hermes_projection_capabilities,
    shannon_projection_capabilities,
)


def test_codex_projection_capabilities_fresh_session_has_plan_access() -> None:
    caps = codex_projection_capabilities(resumed_session=False)

    assert caps.can_read_plan_dir is True
    assert caps.can_read_project_dir is True
    assert caps.has_file_tools is True
    assert caps.checkpoint_write_access is True


def test_codex_projection_capabilities_resumed_session_is_conservative_without_metadata() -> None:
    caps = codex_projection_capabilities(resumed_session=True)

    assert caps.can_read_plan_dir is False
    assert caps.can_read_project_dir is True
    assert caps.has_file_tools is True
    assert caps.checkpoint_write_access is True


def test_codex_projection_capabilities_resumed_session_honors_explicit_plan_access() -> None:
    caps = codex_projection_capabilities(
        resumed_session=True,
        session_has_plan_dir_access=True,
        checkpoint_write_access=False,
    )

    assert caps.can_read_plan_dir is True
    assert caps.can_read_project_dir is True
    assert caps.has_file_tools is True
    assert caps.checkpoint_write_access is False


def test_hermes_projection_capabilities_toolless_finalize_is_conservative() -> None:
    caps = hermes_projection_capabilities(None)

    assert caps.can_read_plan_dir is False
    assert caps.can_read_project_dir is False
    assert caps.has_file_tools is False
    assert caps.checkpoint_write_access is False


def test_hermes_projection_capabilities_readonly_file_phase_can_read_without_checkpoint_access() -> None:
    caps = hermes_projection_capabilities(["file-readonly", "web"])

    assert caps.can_read_plan_dir is True
    assert caps.can_read_project_dir is True
    assert caps.has_file_tools is True
    assert caps.checkpoint_write_access is False


def test_hermes_projection_capabilities_execute_phase_can_write_checkpoint() -> None:
    caps = hermes_projection_capabilities(["terminal", "file", "web"])

    assert caps.can_read_plan_dir is True
    assert caps.can_read_project_dir is True
    assert caps.has_file_tools is True
    assert caps.checkpoint_write_access is True


def test_shannon_projection_capabilities_read_only_keeps_reads_without_checkpoint_writes() -> None:
    caps = shannon_projection_capabilities(read_only=True)

    assert caps.can_read_plan_dir is True
    assert caps.can_read_project_dir is True
    assert caps.has_file_tools is True
    assert caps.checkpoint_write_access is False


def test_shannon_projection_capabilities_write_mode_can_checkpoint() -> None:
    caps = shannon_projection_capabilities(read_only=False)

    assert caps.can_read_plan_dir is True
    assert caps.can_read_project_dir is True
    assert caps.has_file_tools is True
    assert caps.checkpoint_write_access is True
