"""Railway-backed cloud provider implementation."""

from __future__ import annotations

import base64
import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path

from arnold_pipelines.megaplan.cloud.providers.base import (
    DeployReport,
    DeployStepReport,
    Provider,
    _logs_follow,
    _missing_cli_error,
    _write_redacted_output,
)
from arnold_pipelines.megaplan.cloud.spec import CloudSpec, RailwaySpec
from arnold_pipelines.megaplan.types import CliError


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
                "encoding": "utf-8",
                "errors": "replace",
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
        if not args:
            return command
        if args[0] == "link":
            if self._railway.environment:
                return [*command, "--environment", self._railway.environment]
            return command
        if self._railway.environment and args[:2] == ("service", "status"):
            return [
                *command[:3],
                "--environment",
                self._railway.environment,
                *command[3:],
            ]
        scoped: list[str] = []
        if self._railway.environment and args[0] in {
            "down",
            "logs",
            "ssh",
            "up",
            "variables",
            "volume",
        }:
            scoped.extend(["--environment", self._railway.environment])
        return [*command[:2], *scoped, *command[2:]]

    def build(self, deploy_dir: Path) -> int:
        self._run(["docker", "build", "-t", self.image_tag, str(deploy_dir)])
        return 0

    def deploy(self, deploy_dir: Path, *, secrets: dict[str, str]) -> DeployReport:
        missing = [name for name in self._spec.secrets if not secrets.get(name)]
        if missing:
            raise CliError("missing_secrets", f"Missing required secrets: {', '.join(missing)}")

        steps: list[DeployStepReport] = []
        if self._railway.project:
            link_result = self._run(
                self._railway_cmd("link", "--project", self._railway.project),
                cwd=deploy_dir,
            )
            steps.append(
                _step_from_result(
                    "railway link",
                    link_result,
                    detail=f"linked project {self._railway.project}",
                )
            )
            status_result = self._ensure_configured_service(deploy_dir)
            steps.append(
                _step_from_result(
                    "verify Railway service",
                    status_result,
                    detail=f"service {self._railway.service} is configured",
                )
            )

        variable_stdout: list[str] = []
        variable_stderr: list[str] = []
        for name in self._spec.secrets:
            value = secrets[name]
            result = self._run(
                self._railway_cmd(
                    "variables",
                    "--service",
                    self._railway.service,
                    "--set",
                    f"{name}={value}",
                ),
                cwd=deploy_dir,
            )
            variable_stdout.append(result.stdout or "")
            variable_stderr.append(result.stderr or "")
        steps.append(
            DeployStepReport(
                name="set Railway service variables",
                status="ok",
                detail=f"set {len(self._spec.secrets)} service var(s)",
                stdout="".join(variable_stdout),
                stderr="".join(variable_stderr),
                metadata={"count": len(self._spec.secrets)},
            )
        )

        up_result = self._run(
            self._railway_cmd(
                "up",
                "--service",
                self._railway.service,
                "--detach",
                "--ci",
            ),
            cwd=deploy_dir,
        )
        up_classification = _classify_railway_up(up_result)
        up_detail = "ran railway up --detach --ci"
        if up_classification == "not_triggered":
            up_detail = "railway reported no image rebuild"
        elif not (up_result.stdout or up_result.stderr):
            up_detail = "ran railway up --detach --ci; provider returned no stdout/stderr"
        steps.append(
            _step_from_result(
                "railway up",
                up_result,
                detail=up_detail,
                metadata={"image_rebuild": up_classification},
            )
        )

        no_op = up_classification == "not_triggered" and not self._spec.secrets
        if no_op:
            verdict = "deploy: no-op (nothing changed)"
        elif up_classification == "not_triggered":
            verdict = "deploy: vars updated, no image rebuild"
        else:
            verdict = f"deploy: triggered Railway build/deploy for service {self._railway.service}"
        warnings = []
        if up_classification == "triggered" and not (up_result.stdout or up_result.stderr):
            warnings.append(
                "railway up returned no stdout/stderr; verify the Railway deployment logs for build outcome"
            )
        return DeployReport(
            success=True,
            provider="railway",
            service=self._railway.service,
            deploy_dir=str(deploy_dir),
            steps=steps,
            image_rebuild=up_classification,
            no_op=no_op,
            vars_updated=len(self._spec.secrets),
            logs={
                "command": "arnold cloud logs --no-follow",
                "service": self._railway.service,
                "provider": "railway",
            },
            verdict=verdict,
            warnings=warnings,
            exit_code=0,
        )

    def _ensure_configured_service(self, deploy_dir: Path) -> subprocess.CompletedProcess[str]:
        result = self._run(
            self._railway_cmd("service", "status", "--all", "--json"),
            cwd=deploy_dir,
        )
        if _service_output_contains(result.stdout or "", self._railway.service):
            return result
        command = f"railway add --service {shlex.quote(self._railway.service)}"
        raise CliError(
            "railway_service_missing",
            (
                f"Railway service {self._railway.service!r} was not found after project link. "
                f"Run this command from the deploy directory, then rerun deploy: {command}"
            ),
        )

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
        command = f"cd {shlex.quote(workspace)} && arnold status"
        if plan is not None:
            command += f" --plan {shlex.quote(plan)}"
        result = self.ssh_exec(command)
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise CliError("provider_failed", f"arnold status did not return JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise CliError("provider_failed", "arnold status did not return a JSON object")
        return payload

    def down(self) -> int:
        self._run(self._railway_cmd("down", "--service", self._railway.service))
        return 0

    def destroy(self, *, volume: str | None = None) -> int:
        self.down()
        if volume:
            self._run(self._railway_cmd("volume", "delete", volume))
        return 0


def _service_output_contains(output: str, service: str) -> bool:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, str) and item == service:
                return True
            if isinstance(item, dict) and item.get("name") == service:
                return True
    if isinstance(payload, dict):
        items = payload.get("services")
        if isinstance(items, list):
            return _service_output_contains(json.dumps(items), service)
        if payload.get("name") == service:
            return True
    for line in output.splitlines():
        stripped = line.strip()
        if stripped == service or stripped.startswith(f"{service} ") or f" {service} " in stripped:
            return True
    return False


def _step_from_result(
    name: str,
    result: subprocess.CompletedProcess[str],
    *,
    detail: str = "",
    metadata: dict[str, object] | None = None,
) -> DeployStepReport:
    return DeployStepReport(
        name=name,
        status="ok",
        detail=detail,
        stdout=result.stdout or "",
        stderr=result.stderr or "",
        metadata=metadata or {},
    )


def _classify_railway_up(result: subprocess.CompletedProcess[str]) -> str:
    output = f"{result.stdout or ''}\n{result.stderr or ''}".lower()
    no_change_markers = (
        "no changes",
        "nothing to deploy",
        "already up to date",
        "unchanged",
        "skipping build",
    )
    if any(marker in output for marker in no_change_markers):
        return "not_triggered"
    return "triggered"
