"""Tests that `provider: railway` is accepted by spec validation."""

from __future__ import annotations

import tempfile
from pathlib import Path

import yaml

from arnold_pipelines.megaplan.cloud.spec import FUTURE_PROVIDERS, VALID_PROVIDERS, load_spec


def _write_cloud_yaml(content: dict) -> Path:
    """Write a minimal cloud.yaml to a temp file and return its path."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", encoding="utf-8", delete=False
    )
    yaml.safe_dump(content, tmp)
    tmp.close()
    return Path(tmp.name)


class TestRailwayProviderValid:
    """provider: railway must pass spec validation."""

    def test_railway_accepted_directly(self) -> None:
        """Explicit provider: railway must load a CloudSpec."""
        path = _write_cloud_yaml({
            "provider": "railway",
            "repo": {"url": "https://github.com/example/app.git"},
        })
        try:
            spec = load_spec(path)
            assert spec.provider == "railway"
            assert spec.repo.workspace == "/workspace/app"
        finally:
            path.unlink(missing_ok=True)

    def test_railway_in_valid_providers(self) -> None:
        """The VALID_PROVIDERS list must include 'railway'."""
        assert "railway" in VALID_PROVIDERS

    def test_railway_not_in_future_providers(self) -> None:
        """The FUTURE_PROVIDERS list must not include 'railway'."""
        assert "railway" not in FUTURE_PROVIDERS

    def test_ssh_is_valid(self) -> None:
        """provider: ssh must be accepted."""
        assert "ssh" in VALID_PROVIDERS

    def test_local_is_valid(self) -> None:
        """provider: local must be accepted."""
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
