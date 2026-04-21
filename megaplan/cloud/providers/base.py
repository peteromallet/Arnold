"""Abstract base classes for cloud providers.

Sprint 2 will add `init_plan(...)`-style workflows and more providers. Provider
implementations should stay stateless beyond local CLI discovery and credential
resolution so the CLI can instantiate them on demand.
"""

from __future__ import annotations

import abc
import subprocess
from pathlib import Path

from megaplan.cloud.spec import CloudSpec
from megaplan.types import CliError


class Provider(abc.ABC):
    @abc.abstractmethod
    def build(self, deploy_dir: Path) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    def deploy(self, deploy_dir: Path, *, secrets: dict[str, str]) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    def ssh_exec(self, command: str) -> subprocess.CompletedProcess:
        raise NotImplementedError

    @abc.abstractmethod
    def attach(self) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    def logs(self, *, follow: bool = True) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    def status_payload(self, *, plan: str | None, workspace: str) -> dict:
        raise NotImplementedError

    @abc.abstractmethod
    def down(self) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    def destroy(self, *, volume: str | None = None) -> int:
        raise NotImplementedError


def get_provider(name: str, spec: CloudSpec) -> Provider:
    if name != "railway":
        raise CliError("invalid_spec", f"Unknown cloud provider '{name}'")

    from megaplan.cloud.providers.railway import RailwayProvider

    providers = {"railway": RailwayProvider}
    provider_cls = providers[name]
    return provider_cls(spec)
