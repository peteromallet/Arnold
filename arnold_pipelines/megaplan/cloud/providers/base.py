"""Abstract base classes for cloud providers.

Sprint 2 will add `init_plan(...)`-style workflows and more providers. Provider
implementations should stay stateless beyond local CLI discovery and credential
resolution so the CLI can instantiate them on demand.
"""

from __future__ import annotations

import abc
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from arnold_pipelines.megaplan.custody.process_adapter_wbc import (
    ProcessAdapterWbcAttempt,
    begin_process_adapter_attempt,
)
from arnold_pipelines.megaplan.cloud.spec import CloudSpec
from arnold_pipelines.megaplan.types import CliError


@dataclass
class DeployStepReport:
    name: str
    status: str
    detail: str = ""
    stdout: str = ""
    stderr: str = ""
    log_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeployReport:
    success: bool
    provider: str
    service: str | None
    deploy_dir: str
    steps: list[DeployStepReport] = field(default_factory=list)
    image_rebuild: str = "unknown"
    image_ref: str | None = None
    no_op: bool = False
    vars_updated: int = 0
    logs: dict[str, Any] = field(default_factory=dict)
    verdict: str = ""
    warnings: list[str] = field(default_factory=list)
    exit_code: int = 0


def _missing_cli_error(binary: str, install_url: str) -> None:
    raise CliError(
        "provider_unavailable",
        f"Missing required CLI '{binary}'. Install: {install_url}",
    )


def _logs_follow(
    argv: list[str],
    *,
    cwd: Path | None = None,
    secret_names: list[str] | tuple[str, ...] = (),
    env: dict[str, str] | None = None,
) -> int:
    from arnold_pipelines.megaplan.cloud.redact import stream_redact

    try:
        proc = subprocess.Popen(
            argv,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except FileNotFoundError as exc:
        raise CliError("provider_failed", str(exc)) from exc

    for chunk in stream_redact(proc, secret_names, env=env):
        sys.stdout.write(chunk)

    returncode = proc.wait()
    if returncode != 0:
        raise CliError("provider_failed", f"Command failed: {' '.join(argv)}")
    return 0


def _write_redacted_output(
    result: subprocess.CompletedProcess[str],
    *,
    secret_names: list[str] | tuple[str, ...] = (),
    env: dict[str, str] | None = None,
) -> None:
    from arnold_pipelines.megaplan.cloud.redact import redact

    if getattr(result, "stdout", ""):
        sys.stdout.write(redact(result.stdout, secret_names, env=env))
    if getattr(result, "stderr", ""):
        sys.stderr.write(redact(result.stderr, secret_names, env=env))


class Provider(abc.ABC):
    supports_session = False

    def _process_adapter_evidence_root(self) -> Path:
        return Path(tempfile.gettempdir()) / "arnold-process-adapter-wbc"

    def _begin_process_adapter_attempt(
        self,
        *,
        surface: str,
        start_details: dict[str, Any] | None = None,
        adapter_name: str | None = None,
    ) -> ProcessAdapterWbcAttempt:
        return begin_process_adapter_attempt(
            self._process_adapter_evidence_root(),
            producer_family="cloud_provider_adapter",
            adapter_name=adapter_name or type(self).__name__,
            surface=surface,
            start_details=start_details,
        )

    @abc.abstractmethod
    def build(self, deploy_dir: Path) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    def deploy(self, deploy_dir: Path, *, secrets: dict[str, str]) -> int | DeployReport:
        raise NotImplementedError

    @abc.abstractmethod
    def ssh_exec(self, command: str) -> subprocess.CompletedProcess:
        raise NotImplementedError

    @abc.abstractmethod
    def upload_file(self, src: Path, dest: str) -> None:
        raise CliError("not_implemented", "This provider does not support file upload")

    def upload_archive(self, src: Path, dest_dir: str) -> None:
        raise CliError("not_implemented", "This provider does not support archive upload")

    @abc.abstractmethod
    def read_remote_file(self, path: str) -> str:
        raise CliError("not_implemented", "This provider does not support remote file reads")

    @abc.abstractmethod
    def attach(self) -> int:
        """Attach to the remote tmux session.

        Interactive attach is intentionally not redacted line-by-line; unlike
        `logs -f`, the attached PTY is a raw interactive stream.
        """
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


ProviderFactory = Callable[[CloudSpec], Provider]


def _local_provider(spec: CloudSpec) -> Provider:
    from arnold_pipelines.megaplan.cloud.providers.local import LocalProvider

    return LocalProvider(spec)


def _ssh_provider(spec: CloudSpec) -> Provider:
    from arnold_pipelines.megaplan.cloud.providers.ssh import SshProvider

    return SshProvider(spec)


_PROVIDER_FACTORIES: dict[str, ProviderFactory] = {
    "local": _local_provider,
    "ssh": _ssh_provider,
}


def get_provider(name: str, spec: CloudSpec) -> Provider:
    provider_factory = _PROVIDER_FACTORIES.get(name)
    if provider_factory is None:
        raise CliError("invalid_spec", f"Unknown cloud provider '{name}'")
    return provider_factory(spec)
