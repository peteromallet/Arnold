"""Direct provider transport for commands already running inside the agentbox.

This deliberately implements the same small provider surface used by the cloud
chain launcher, but executes against the mounted ``/workspace`` filesystem
instead of bouncing through SSH and ``docker exec``.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from arnold_pipelines.megaplan.cloud.spec import CloudSpec
from arnold_pipelines.megaplan.types import CliError

from .base import Provider


class OnBoxProvider(Provider):
    supports_session = True

    def __init__(self, spec: CloudSpec) -> None:
        self._spec = spec

    def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", "-lc", command],
            capture_output=True,
            text=True,
            check=False,
        )

    def upload_file(self, src: Path, dest: str) -> None:
        target = Path(dest)
        target.parent.mkdir(parents=True, exist_ok=True)
        if src.resolve() == target.resolve():
            return
        shutil.copy2(src, target)

    def upload_archive(self, src: Path, dest_dir: str) -> None:
        target = Path(dest_dir)
        target.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["tar", "-xzf", str(src), "-C", str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise CliError("provider_failed", result.stderr.strip() or "archive extraction failed")

    def read_remote_file(self, path: str) -> str:
        return Path(path).read_text(encoding="utf-8")

    def _unsupported(self, action: str):
        raise CliError("invalid_args", f"on-box transport does not support cloud {action}")

    def build(self, deploy_dir: Path) -> int:
        del deploy_dir
        return self._unsupported("build")

    def deploy(self, deploy_dir: Path, *, secrets: dict[str, str]) -> int:
        del deploy_dir, secrets
        return self._unsupported("deploy")

    def attach(self) -> int:
        return self._unsupported("attach")

    def logs(self, *, follow: bool = True) -> int:
        del follow
        return self._unsupported("logs")

    def status_payload(self, *, plan: str | None, workspace: str) -> dict:
        del plan, workspace
        return self._unsupported("status")

    def down(self) -> int:
        return self._unsupported("down")

    def destroy(self, *, volume: str | None = None) -> int:
        del volume
        return self._unsupported("destroy")
