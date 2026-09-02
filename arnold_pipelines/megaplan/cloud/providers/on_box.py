"""Direct provider transport for commands already running inside the agentbox.

This deliberately implements the same small provider surface used by the cloud
chain launcher, but executes against the mounted ``/workspace`` filesystem
instead of bouncing through SSH and ``docker exec``.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from pathlib import Path

from arnold_pipelines.megaplan.cloud.auth import on_box_git_credential_env
from arnold_pipelines.megaplan.cloud.redact import redact_text
from arnold_pipelines.megaplan.cloud.spec import CloudSpec
from arnold_pipelines.megaplan.types import CliError

from .base import Provider


_ON_BOX_CONTROL_ROOT = Path("/workspace/.megaplan/cloud-sessions")
_SCOPE_SLUG_RE = re.compile(r"[^A-Za-z0-9_.-]+")
_GIT_AUTH_COMMAND_RE = re.compile(
    r"(?:^|[;&|]\s*|\s)git(?:\s+(?:-[^\s;&|]+|-[Cc]\s+[^\s;&|]+))*\s+"
    r"(?:clone|fetch|pull|push)\b"
)
_URL_USERINFO_RE = re.compile(r"(https?://|ssh://)[^/@\s]+@", re.IGNORECASE)
_GIT_AUTH_FAILURE_RE = re.compile(
    r"authentication failed|could not read username|terminal prompts disabled|"
    r"invalid username or password|access denied",
    re.IGNORECASE,
)


class OnBoxProvider(Provider):
    supports_session = True

    def __init__(self, spec: CloudSpec) -> None:
        self._spec = spec

    def _process_adapter_evidence_root(self) -> Path:
        """Return an external, deterministic control-plane evidence root.

        Process-adapter evidence is control-plane state, not repository
        checkout state.  Keeping it beside the chain/session marker means the
        first on-box command can safely create its receipt before
        ``_ensure_repo_checkout`` clones the repository.  The hash preserves
        isolation for callers that accidentally reuse the default session
        name across different workspaces/specs.
        """
        session = str(self._spec.chain_session or "megaplan-chain").strip()
        slug = _SCOPE_SLUG_RE.sub("-", session).strip("-.") or "megaplan-chain"
        chain_spec = self._spec.chain.spec if self._spec.chain is not None else ""
        scope = "\0".join((session, str(chain_spec), self._spec.repo.workspace))
        digest = hashlib.sha256(scope.encode("utf-8")).hexdigest()[:16]
        return _ON_BOX_CONTROL_ROOT / f"{slug}-{digest}" / "process-adapter-wbc"

    @staticmethod
    def _safe_command(command: str) -> str:
        """Return command text safe for the WBC journal and diagnostics."""
        return _URL_USERINFO_RE.sub(r"\1<redacted>@", redact_text(command))

    @staticmethod
    def _is_git_auth_operation(command: str) -> bool:
        return _GIT_AUTH_COMMAND_RE.search(command) is not None

    def _git_environment(self, command: str) -> dict[str, str] | None:
        if not self._is_git_auth_operation(command):
            return None
        # Local/file clones do not need the box credential and are useful for
        # deterministic local smoke tests.  Fetch/push/pull use the helper
        # unconditionally because their configured remote is not in argv.
        is_clone = re.search(
            r"(?:^|[;&|]\s*|\s)git(?:\s+(?:-[^\s;&|]+|-[Cc]\s+[^\s;&|]+))*\s+clone\b",
            command,
        ) is not None
        if is_clone and "github.com" not in command.lower():
            return None
        return on_box_git_credential_env()

    def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
        safe_command = self._safe_command(command)
        try:
            run_env = self._git_environment(command)
        except CliError as exc:
            attempt = self._begin_process_adapter_attempt(
                surface="ssh_exec",
                start_details={"command": safe_command},
            )
            attempt.terminal(
                status="failed",
                outcome="blocked",
                details={"error_code": exc.code},
            )
            raise
        attempt = self._begin_process_adapter_attempt(
            surface="ssh_exec",
            start_details={"command": safe_command},
        )
        kwargs: dict[str, object] = {
            "capture_output": True,
            "text": True,
            "check": False,
        }
        if run_env is not None:
            kwargs["env"] = run_env
        is_git_operation = self._is_git_auth_operation(command)
        result = subprocess.run(["bash", "-lc", command], **kwargs)
        if result.returncode != 0:
            safe_stderr = self._safe_command((result.stderr or "").strip())
            if self._is_git_auth_operation(command) and _GIT_AUTH_FAILURE_RE.search(
                result.stderr or ""
            ):
                attempt.terminal(
                    status="failed",
                    outcome="indeterminate",
                    details={
                        "returncode": result.returncode,
                        "error_code": "on_box_git_auth_failed",
                        # Git may echo a credential-bearing URL supplied by a
                        # remote helper. Keep only the typed outcome in WBC;
                        # the raw diagnostic is never journaled.
                        "stderr": "authentication failure (redacted)",
                    },
                )
                raise CliError(
                    "on_box_git_auth_failed",
                    "on-box Git authentication failed; credential contents were not exposed",
                )
            attempt.terminal(
                status="failed",
                outcome="indeterminate",
                details={
                    "returncode": result.returncode,
                    "stderr": "git operation failed (diagnostic redacted)"
                    if is_git_operation
                    else safe_stderr,
                    "stdout": ""
                    if is_git_operation
                    else self._safe_command((result.stdout or "").strip()),
                },
            )
        else:
            attempt.terminal(
                status="completed",
                outcome="succeeded",
                details={"returncode": result.returncode},
            )
        if is_git_operation:
            # Do not relay raw Git output: credential helpers and remotes are
            # allowed to include credential-bearing URLs in diagnostics.
            result = subprocess.CompletedProcess(
                result.args, result.returncode, "", ""
            )
        return result

    def upload_file(self, src: Path, dest: str) -> None:
        attempt = self._begin_process_adapter_attempt(
            surface="upload_file",
            start_details={"src": str(src), "dest": dest},
        )
        target = Path(dest)
        target.parent.mkdir(parents=True, exist_ok=True)
        if src.resolve() == target.resolve():
            attempt.terminal(
                status="completed",
                outcome="succeeded",
                details={"skipped": True, "reason": "source_equals_target"},
            )
            return
        shutil.copy2(src, target)
        attempt.terminal(
            status="completed",
            outcome="succeeded",
            details={"copied_bytes": src.stat().st_size},
        )

    def upload_archive(self, src: Path, dest_dir: str) -> None:
        attempt = self._begin_process_adapter_attempt(
            surface="upload_archive",
            start_details={"src": str(src), "dest_dir": dest_dir},
        )
        target = Path(dest_dir)
        target.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["tar", "-xzf", str(src), "-C", str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            attempt.terminal(
                status="failed",
                outcome="indeterminate",
                details={
                    "returncode": result.returncode,
                    "stderr": (result.stderr or "").strip(),
                },
            )
            raise CliError("provider_failed", result.stderr.strip() or "archive extraction failed")
        attempt.terminal(
            status="completed",
            outcome="succeeded",
            details={"returncode": result.returncode},
        )

    def read_remote_file(self, path: str) -> str:
        attempt = self._begin_process_adapter_attempt(
            surface="read_remote_file",
            start_details={"path": path},
        )
        content = Path(path).read_text(encoding="utf-8")
        attempt.terminal(
            status="completed",
            outcome="succeeded",
            details={"size_bytes": len(content.encode("utf-8"))},
        )
        return content

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

    def status_payload(
        self,
        *,
        plan: str | None,
        workspace: str,
        session: str | None = None,
    ) -> dict:
        del plan, workspace, session
        return self._unsupported("status")

    def down(self) -> int:
        return self._unsupported("down")

    def destroy(self, *, volume: str | None = None) -> int:
        del volume
        return self._unsupported("destroy")
