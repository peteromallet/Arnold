from __future__ import annotations

import base64
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from arnold_pipelines.megaplan.cloud.spec import CloudSpec, SshSpec
from arnold_pipelines.megaplan.types import CliError

from .base import Provider, _logs_follow, _missing_cli_error, _write_redacted_output


INSTALL_LINK = "Install: https://www.openssh.com/"


class SshProvider(Provider):
    def __init__(self, spec: CloudSpec) -> None:
        self._spec = spec
        self._ssh = spec.ssh or SshSpec(host="localhost")
        self._ssh_binary = shutil.which("ssh")
        self._scp_binary = shutil.which("scp")
        self._rsync_binary = shutil.which("rsync")
        if self._ssh_binary is None:
            _missing_cli_error("ssh", INSTALL_LINK.removeprefix("Install: "))
        if self._scp_binary is None and self._rsync_binary is None:
            _missing_cli_error("scp/rsync", INSTALL_LINK.removeprefix("Install: "))

    def _target(self) -> str:
        if self._ssh.user:
            return f"{self._ssh.user}@{self._ssh.host}"
        return self._ssh.host

    def _ssh_transport_argv(self) -> list[str]:
        argv = [self._ssh_binary or "ssh", "-p", str(self._ssh.port)]
        if self._ssh.identity_file:
            argv.extend(["-i", self._ssh.identity_file])
        return argv

    def _process_adapter_evidence_root(self) -> Path:
        return Path(tempfile.gettempdir()) / "arnold-process-adapter-wbc" / "ssh"

    def _run(
        self,
        argv: list[str],
        *,
        capture_output: bool = True,
        input: str | None = None,
        surface: str = "shell_command",
    ) -> subprocess.CompletedProcess[str]:
        attempt = self._begin_process_adapter_attempt(
            surface=surface,
            start_details={
                "argv": list(argv),
                "capture_output": capture_output,
                "input_supplied": input is not None,
            },
        )
        try:
            kwargs: dict[str, object] = {
                "capture_output": capture_output,
                "text": True,
                "check": False,
            }
            if input is not None:
                kwargs["input"] = input
            result = subprocess.run(argv, **kwargs)
        except FileNotFoundError as exc:
            attempt.terminal(
                status="failed",
                outcome="blocked",
                details={"error_type": type(exc).__name__, "message": str(exc)},
            )
            raise CliError("provider_failed", str(exc)) from exc
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            attempt.terminal(
                status="failed",
                outcome="indeterminate",
                details={
                    "returncode": result.returncode,
                    "stderr": stderr,
                    "stdout": (result.stdout or "").strip(),
                },
            )
            raise CliError("provider_failed", stderr or f"Command failed: {' '.join(argv)}")
        attempt.terminal(
            status="completed",
            outcome="succeeded",
            details={"returncode": result.returncode},
        )
        return result

    def _remote_run(
        self,
        command: str,
        *,
        capture_output: bool = True,
        input: str | None = None,
        surface: str = "remote_command",
    ) -> subprocess.CompletedProcess[str]:
        return self._run(
            [*self._ssh_transport_argv(), self._target(), command],
            capture_output=capture_output,
            input=input,
            surface=surface,
        )

    def _sync_deploy_dir(self, deploy_dir: Path) -> None:
        remote_dir = shlex.quote(self._ssh.remote_dir)
        if self._rsync_binary is not None:
            self._remote_run(f"mkdir -p {remote_dir}", surface="sync_prepare")
            self._run(
                [
                    self._rsync_binary,
                    "-az",
                    "-e",
                    shlex.join(self._ssh_transport_argv()),
                    f"{deploy_dir}/",
                    f"{self._target()}:{remote_dir}/",
                ],
                surface="sync_rsync",
            )
            return
        sys.stderr.write("WARN: rsync unavailable; falling back to scp -r\n")
        self._remote_run(
            f"rm -rf {remote_dir} && mkdir -p {remote_dir}",
            surface="sync_prepare",
        )
        self._run(
            [
                self._scp_binary or "scp",
                "-r",
                "-P",
                str(self._ssh.port),
                *(["-i", self._ssh.identity_file] if self._ssh.identity_file else []),
                f"{deploy_dir}/.",
                f"{self._target()}:{remote_dir}",
            ],
            surface="sync_scp",
        )

    def build(self, deploy_dir: Path) -> int:
        self._sync_deploy_dir(deploy_dir)
        self._remote_run(
            f"docker build -t {shlex.quote(self._ssh.container)} {shlex.quote(self._ssh.remote_dir)}",
            surface="build",
        )
        return 0

    def deploy(self, deploy_dir: Path, *, secrets: dict[str, str]) -> int:
        del deploy_dir
        env_path = f"{self._ssh.remote_dir}/.env"
        env_lines = [f"PORT={self._spec.resources.port}"]
        env_lines.extend(f"{name}={value}" for name, value in secrets.items())
        self._remote_run(
            "mkdir -p "
            f"{shlex.quote(self._ssh.remote_dir)} "
            f"{shlex.quote(self._ssh.workspace_dir)} "
            f"{shlex.quote(f'{self._ssh.cache_dir}/pip')} "
            f"{shlex.quote(f'{self._ssh.cache_dir}/npm')}",
            surface="deploy_prepare",
        )
        self._remote_run(
            f"cat > {shlex.quote(env_path)}",
            input="\n".join(env_lines) + "\n",
            surface="deploy_env",
        )
        self._remote_run(
            f"docker rm -f {shlex.quote(self._ssh.container)} >/dev/null 2>&1 || true",
            surface="deploy_remove_existing",
        )
        self._remote_run(
            " ".join(
                [
                    "docker run -d",
                    f"--name {shlex.quote(self._ssh.container)}",
                    "--restart unless-stopped",
                    f"--env-file {shlex.quote(env_path)}",
                    f"-p {self._spec.resources.port}:{self._spec.resources.port}",
                    f"-v {shlex.quote(self._ssh.workspace_dir)}:/workspace",
                    f"-v {shlex.quote(f'{self._ssh.cache_dir}/pip')}:/root/.cache/pip",
                    f"-v {shlex.quote(f'{self._ssh.cache_dir}/npm')}:/root/.npm",
                    shlex.quote(self._ssh.container),
                ]
            ),
            surface="deploy_run",
        )
        return 0

    def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
        return self._remote_run(
            f"docker exec {shlex.quote(self._ssh.container)} bash -lc {shlex.quote(command)}",
            surface="ssh_exec",
        )

    def upload_file(self, src: Path, dest: str) -> None:
        payload = base64.b64encode(src.read_bytes()).decode("ascii")
        parent = Path(dest).parent.as_posix()
        inner = f"mkdir -p {shlex.quote(parent)} && base64 -d > {shlex.quote(dest)}"
        self._remote_run(
            f"docker exec -i {shlex.quote(self._ssh.container)} bash -lc {shlex.quote(inner)}",
            input=payload,
            surface="upload_file",
        )

    def upload_archive(self, src: Path, dest_dir: str) -> None:
        payload = base64.b64encode(src.read_bytes()).decode("ascii")
        inner = f"mkdir -p {shlex.quote(dest_dir)} && base64 -d | tar -xzf - -C {shlex.quote(dest_dir)}"
        self._remote_run(
            f"docker exec -i {shlex.quote(self._ssh.container)} bash -lc {shlex.quote(inner)}",
            input=payload,
            surface="upload_archive",
        )

    def read_remote_file(self, path: str) -> str:
        result = self._remote_run(
            f"docker exec {shlex.quote(self._ssh.container)} bash -lc {shlex.quote(f'cat {shlex.quote(path)}')}",
            surface="read_remote_file",
        )
        return result.stdout

    def attach(self) -> int:
        self._remote_run(
            f"docker exec -it {shlex.quote(self._ssh.container)} tmux attach -t agent",
            capture_output=False,
            surface="attach",
        )
        return 0

    def logs(self, *, follow: bool = True) -> int:
        argv = f"docker logs {'-f ' if follow else '--tail 200 '}{shlex.quote(self._ssh.container)}"
        if follow:
            return _logs_follow(
                [*self._ssh_transport_argv(), self._target(), argv.strip()],
                secret_names=self._spec.secrets,
                env=os.environ,
            )
        result = self._remote_run(argv.strip(), surface="logs")
        _write_redacted_output(result, secret_names=self._spec.secrets, env=os.environ)
        return 0

    def status_payload(self, *, plan: str | None, workspace: str) -> dict:
        command = f"cd {shlex.quote(workspace)} && arnold status"
        if plan is not None:
            command += f" --plan {shlex.quote(plan)}"
        result = self.ssh_exec(command)
        payload = json.loads(result.stdout)
        if not isinstance(payload, dict):
            raise CliError("provider_failed", "arnold status did not return a JSON object")
        return payload

    def down(self) -> int:
        self._remote_run(f"docker stop {shlex.quote(self._ssh.container)}", surface="down")
        return 0

    def destroy(self, *, volume: str | None = None) -> int:
        del volume
        self._remote_run(
            f"docker rm -f {shlex.quote(self._ssh.container)} >/dev/null 2>&1 || true && rm -rf {shlex.quote(self._ssh.remote_dir)}",
            surface="destroy",
        )
        return 0
