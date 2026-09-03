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

    def _command_environment(self, *, require_git_auth: bool) -> dict[str, str]:
        """Build the environment inherited by every on-box command.

        A shell command is not a reliable boundary for Git capability: the
        runtime-create and chain wrappers can invoke Git from Python without
        spelling ``git`` in the command received here. Always inject the
        path-only helper configuration when it is available. Direct Git auth
        operations still fail closed when the helper is missing; non-Git
        commands retain normal local execution semantics.
        """
        return on_box_git_credential_env(required=require_git_auth)

    def git_auth_exec(self, command: str) -> subprocess.CompletedProcess[str]:
        """Run an explicitly authenticated Git operation.

        The caller, rather than shell-text inspection, declares that this
        command is a direct Git authentication boundary.  This is used by
        repository checkout/fetch operations; compound runtime wrappers stay
        on ``ssh_exec`` so their structured JSON remains observable.
        """
        return self.ssh_exec(command, redact_git_output=True)

    def ssh_exec(
        self, command: str, *, redact_git_output: bool = False
    ) -> subprocess.CompletedProcess[str]:
        safe_command = self._safe_command(command)
        try:
            run_env = self._command_environment(require_git_auth=redact_git_output)
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
        kwargs["env"] = run_env
        # This is an explicit call-site intent, not a lexical classification
        # of arbitrary shell text.  A wrapper may contain comments, heredocs,
        # JSON, or invoke Git internally while still returning its own JSON.
        is_git_operation = redact_git_output
        result = subprocess.run(["bash", "-lc", command], **kwargs)
        if result.returncode != 0:
            safe_stderr = self._safe_command((result.stderr or "").strip())
            if redact_git_output and _GIT_AUTH_FAILURE_RE.search(
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
