"""Railway-backed cloud provider implementation."""

from __future__ import annotations

import base64
import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path

from megaplan.cloud.providers.base import Provider, _logs_follow, _missing_cli_error, _write_redacted_output
from megaplan.cloud.spec import CloudSpec, RailwaySpec
from megaplan.types import CliError


INSTALL_LINK = "Install: https://docs.railway.app/develop/cli"


class RailwayProvider(Provider):
    """Thin wrapper around the Railway CLI for sprint-1 cloud flows."""

    supports_session = True

    def __init__(self, spec: CloudSpec) -> None:
        self._spec = spec
        self._railway = spec.railway or RailwaySpec()
        self._workspace = spec.repo.workspace
        self._volume = spec.resources.volume
        self._binary = shutil.which("railway")
        if self._binary is None:
            _missing_cli_error("railway", INSTALL_LINK.removeprefix("Install: "))

    @property
    def image_tag(self) -> str:
        return f"megaplan-cloud-{self._railway.service}"

    def _run(
        self,
        argv: list[str],
        *,
        cwd: Path | None = None,
        capture_output: bool = True,
        input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        try:
            kwargs: dict[str, object] = {
                "cwd": cwd,
                "capture_output": capture_output,
                "text": True,
                "check": False,
            }
            if input is not None:
                kwargs["input"] = input
            result = subprocess.run(
                argv,
                **kwargs,
            )
        except FileNotFoundError as exc:
            raise CliError("provider_failed", str(exc)) from exc
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise CliError("provider_failed", stderr or f"Command failed: {' '.join(argv)}")
        return result

    def _railway_cmd(self, *args: str) -> list[str]:
        command = [self._binary or "railway", *args]
        scoped: list[str] = []
        if self._railway.project:
            scoped.extend(["--project", self._railway.project])
        if self._railway.environment:
            scoped.extend(["--environment", self._railway.environment])
        if scoped and args and args[0] == "link":
            return command
        return [*command[:2], *scoped, *command[2:]]

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
                "--",
                command,
            )
        )

    def upload_file(self, src: Path, dest: str) -> None:
        payload = base64.b64encode(src.read_bytes()).decode("ascii")
        dest_path = shlex.quote(dest)
        dest_dir = shlex.quote(str(Path(dest).parent))
        command = (
            f"mkdir -p {dest_dir} && "
            f"base64 -d > {dest_path} <<'MEGAPLAN_UPLOAD'\n"
            f"{payload}\n"
            "MEGAPLAN_UPLOAD"
        )
        self._run(
            self._railway_cmd(
                "ssh",
                "--service",
                self._railway.service,
                "--",
                command,
            )
        )

    def read_remote_file(self, path: str) -> str:
        result = self._run(
            self._railway_cmd(
                "ssh",
                "--service",
                self._railway.service,
                "--",
                f"cat {shlex.quote(path)}",
            )
        )
        return result.stdout

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
        if follow:
            return _logs_follow(argv, secret_names=self._spec.secrets, env=os.environ)
        argv.extend(["--lines", "200"])
        result = self._run(argv)
        _write_redacted_output(result, secret_names=self._spec.secrets, env=os.environ)
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
