"""Tests that `provider: railway` is rejected by spec validation."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from arnold_pipelines.megaplan.cloud.spec import load_spec
from arnold_pipelines.megaplan.types import CliError


def _write_cloud_yaml(content: dict) -> Path:
    """Write a minimal cloud.yaml to a temp file and return its path."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", encoding="utf-8", delete=False
    )
    yaml.safe_dump(content, tmp)
    tmp.close()
    return Path(tmp.name)


class TestRailwayProviderInvalid:
    """provider: railway must fail spec validation."""

    def test_railway_rejected_directly(self) -> None:
        """Explicit provider: railway must raise CliError."""
        path = _write_cloud_yaml({
            "provider": "railway",
            "repo": {"url": "https://github.com/example/app.git"},
        })
        try:
            with pytest.raises(CliError) as exc_info:
                load_spec(path)
            error = exc_info.value
            assert error.code == "invalid_spec"
            assert "railway" in str(error.message).lower()
        finally:
            path.unlink(missing_ok=True)

    def test_railway_not_in_valid_providers(self) -> None:
        """The VALID_PROVIDERS list must not include 'railway'."""
        from arnold_pipelines.megaplan.cloud.spec import VALID_PROVIDERS
        assert "railway" not in VALID_PROVIDERS

    def test_railway_not_in_future_providers(self) -> None:
        """The FUTURE_PROVIDERS list must not include 'railway'."""
        from arnold_pipelines.megaplan.cloud.spec import FUTURE_PROVIDERS
        assert "railway" not in FUTURE_PROVIDERS

    def test_ssh_is_valid(self) -> None:
        """provider: ssh must be accepted."""
        from arnold_pipelines.megaplan.cloud.spec import VALID_PROVIDERS
        assert "ssh" in VALID_PROVIDERS

    def test_local_is_valid(self) -> None:
        """provider: local must be accepted."""
        from arnold_pipelines.megaplan.cloud.spec import VALID_PROVIDERS
        assert "local" in VALID_PROVIDERS

    def test_provider_default_is_ssh(self) -> None:
        """When provider is omitted, default must be 'ssh'."""
        path = _write_cloud_yaml({
            # no provider key — defaults to 'ssh'
            "repo": {"url": "https://github.com/example/app.git"},
            "ssh": {"host": "testhost"},
        })
        try:
            spec = load_spec(path)
            assert spec.provider == "ssh"
        finally:
            path.unlink(missing_ok=True)
