"""Tests for SshSpec defaults and validation."""

from __future__ import annotations

import pytest

from arnold_pipelines.megaplan.cloud.spec import SshSpec


class TestSshSpecDefaults:
    """SshSpec must have the correct default paths for persistent host storage."""

    def test_default_remote_dir(self) -> None:
        spec = SshSpec(host="myhost")
        assert spec.remote_dir == "/opt/megaplan-cloud/deploy"

    def test_default_workspace_dir(self) -> None:
        spec = SshSpec(host="myhost")
        assert spec.workspace_dir == "/opt/megaplan-cloud/workspace"

    def test_default_cache_dir(self) -> None:
        spec = SshSpec(host="myhost")
        assert spec.cache_dir == "/opt/megaplan-cloud/cache"

    def test_default_port(self) -> None:
        spec = SshSpec(host="myhost")
        assert spec.port == 22

    def test_default_container(self) -> None:
        spec = SshSpec(host="myhost")
        assert spec.container == "megaplan-cloud-agent"

    def test_default_user_is_none(self) -> None:
        spec = SshSpec(host="myhost")
        assert spec.user is None

    def test_default_identity_file_is_none(self) -> None:
        spec = SshSpec(host="myhost")
        assert spec.identity_file is None

    def test_explicit_workspace_dir(self) -> None:
        spec = SshSpec(host="myhost", workspace_dir="/data/workspace")
        assert spec.workspace_dir == "/data/workspace"

    def test_explicit_cache_dir(self) -> None:
        spec = SshSpec(host="myhost", cache_dir="/data/cache")
        assert spec.cache_dir == "/data/cache"

    def test_explicit_remote_dir(self) -> None:
        spec = SshSpec(host="myhost", remote_dir="/data/deploy")
        assert spec.remote_dir == "/data/deploy"

    def test_remote_dir_and_workspace_dir_are_distinct(self) -> None:
        """remote_dir must stay separate from workspace_dir so Docker build
        context does not include cloned repos/node_modules/.venv."""
        spec = SshSpec(host="myhost")
        assert spec.remote_dir != spec.workspace_dir
        # workspace_dir should not be a subdirectory of remote_dir
        assert not spec.workspace_dir.startswith(spec.remote_dir + "/")
        assert not spec.remote_dir.startswith(spec.workspace_dir + "/")

    def test_frozen_dataclass(self) -> None:
        spec = SshSpec(host="myhost")
        with pytest.raises(Exception):
            spec.workspace_dir = "/changed"  # type: ignore[misc]
