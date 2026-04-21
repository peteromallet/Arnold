"""Railway-backed cloud provider implementation."""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from pathlib import Path

from megaplan.cloud.providers.base import Provider
from megaplan.cloud.spec import CloudSpec, RailwaySpec
from megaplan.types import CliError


INSTALL_LINK = "Install: https://docs.railway.app/develop/cli"


class RailwayProvider(Provider):
    """Thin wrapper around the Railway CLI for sprint-1 cloud flows."""

    def __init__(self, spec: CloudSpec) -> None:
        self._spec = spec
        self._railway = spec.railway or RailwaySpec()
        self._workspace = spec.repo.workspace
        self._volume = spec.resources.volume
        self._binary = shutil.which("railway")
        if self._binary is None:
            raise CliError("provider_unavailable", INSTALL_LINK)

    @property
    def image_tag(self) -> str:
        return f"megaplan-cloud-{self._railway.service}"

    def _run(
        self,
        argv: list[str],
        *,
        cwd: Path | None = None,
        capture_output: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                argv,
                cwd=cwd,
                capture_output=capture_output,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise CliError("provider_failed", str(exc)) from exc
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise CliError("provider_failed", stderr or f"Command failed: {' '.join(argv)}")
        return result

    def _railway_cmd(self, *args: str) -> list[str]:
        return [self._binary or "railway", *args]

    def build(self, deploy_dir: Path) -> int:
        self._run(["docker", "build", "-t", self.image_tag, str(deploy_dir)])
        return 0

    def deploy(self, deploy_dir: Path, *, secrets: dict[str, str]) -> int:
        missing = [name for name in self._spec.secrets if not secrets.get(name)]
        if missing:
            raise CliError("missing_secrets", f"Missing required secrets: {', '.join(missing)}")

        if self._railway.project:
            self._run(
                self._railway_cmd("link", "--project", self._railway.project),
                cwd=deploy_dir,
            )

        for name in self._spec.secrets:
            value = secrets[name]
            self._run(
                self._railway_cmd(
                    "variables",
                    "--service",
                    self._railway.service,
                    "--set",
                    f"{name}={value}",
                ),
                cwd=deploy_dir,
            )

        self._run(
            self._railway_cmd(
                "up",
                "--service",
                self._railway.service,
                "--detach",
                "--ci",
            ),
            cwd=deploy_dir,
        )
        return 0

    def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
        return self._run(
            self._railway_cmd(
                "ssh",
                "--service",
                self._railway.service,
                "--session",
                self._railway.session,
                "--",
                command,
            )
        )

    def attach(self) -> int:
        self._run(
            self._railway_cmd(
                "ssh",
                "--service",
                self._railway.service,
                "--session",
                self._railway.session,
            ),
            capture_output=False,
        )
        return 0

    def logs(self, *, follow: bool = True) -> int:
        argv = self._railway_cmd("logs", "--service", self._railway.service)
        if not follow:
            argv.extend(["--lines", "200"])
        self._run(argv, capture_output=False)
        return 0

    def status_payload(self, *, plan: str | None, workspace: str) -> dict:
        command = f"cd {shlex.quote(workspace)} && megaplan status"
        if plan is not None:
            command += f" --plan {shlex.quote(plan)}"
        result = self.ssh_exec(command)
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise CliError("provider_failed", f"megaplan status did not return JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise CliError("provider_failed", "megaplan status did not return a JSON object")
        return payload

    def down(self) -> int:
        self._run(self._railway_cmd("down", "--service", self._railway.service))
        return 0

    def destroy(self, *, volume: str | None = None) -> int:
        self.down()
        if volume:
            self._run(self._railway_cmd("volume", "delete", volume))
        return 0
