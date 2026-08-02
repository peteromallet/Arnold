from __future__ import annotations

import base64
import inspect
import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from arnold_pipelines.megaplan.cloud.spec import (
    CloudSpec,
    SshSpec,
    validate_ssh_host,
    validate_ssh_identity_file,
    validate_ssh_port,
    validate_ssh_user,
)
from arnold_pipelines.megaplan.types import CliError

from .base import Provider, _logs_follow, _missing_cli_error, _write_redacted_output
from .ssh_preflight import (
    capacity_inventory_command,
    classify_container_inspect,
    container_inspect_command,
    parse_capacity_inventory_result,
    parse_workspace_prelaunch_result,
    validate_workspace_dir,
    workspace_prelaunch_command,
)
from .zero_recovery import (
    bootstrap_reclaim_command,
    build_bootstrap_reclaim_transaction,
    build_predeploy_transaction,
    fence_command,
    parse_bootstrap_reclaim_receipt,
    parse_fence_receipt,
    validate_bootstrap_reclaim_transaction,
    validate_predeploy_transaction,
)

LOGGER = logging.getLogger(__name__)

INSTALL_LINK = "Install: https://www.openssh.com/"


class SshProvider(Provider):
    def __init__(
        self,
        spec: CloudSpec,
        *,
        ssh_effect_adapter: Any | None = None,
    ) -> None:
        self._spec = spec
        self._ssh = spec.ssh or SshSpec(host="localhost")
        self._validated_host = validate_ssh_host(self._ssh.host)
        self._validated_user = validate_ssh_user(self._ssh.user)
        self._validated_port = validate_ssh_port(self._ssh.port)
        self._validated_identity_file = validate_ssh_identity_file(
            self._ssh.identity_file
        )
        self._ssh_binary = shutil.which("ssh")
        self._scp_binary = shutil.which("scp")
        self._rsync_binary = shutil.which("rsync")
        self._ssh_effect_adapter = ssh_effect_adapter
        self._consumed_zero_recovery_transactions: set[str] = set()
        if self._ssh_binary is None:
            _missing_cli_error("ssh", INSTALL_LINK.removeprefix("Install: "))
        if self._scp_binary is None and self._rsync_binary is None:
            _missing_cli_error("scp/rsync", INSTALL_LINK.removeprefix("Install: "))

    def _target(self) -> str:
        if self._validated_user:
            return f"{self._validated_user}@{self._validated_host}"
        return self._validated_host

    def _ssh_transport_argv(self) -> list[str]:
        argv = [self._ssh_binary or "ssh", "-p", str(self._validated_port)]
        if self._validated_identity_file:
            argv.extend(["-i", self._validated_identity_file])
        return argv

    def _ssh_destination_argv(self) -> list[str]:
        return [*self._ssh_transport_argv(), "--", self._target()]

    def _process_adapter_evidence_root(self) -> Path:
        return Path(tempfile.gettempdir()) / "arnold-process-adapter-wbc" / "ssh"

    def _run(
        self,
        argv: list[str],
        *,
        capture_output: bool = True,
        input: str | None = None,
        surface: str = "shell_command",
        raise_on_failure: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        attempt = self._begin_process_adapter_attempt(
            surface=surface,
            start_details={
                "executable": Path(argv[0]).name if argv else "",
                "argument_count": len(argv),
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
            message = self._redact_failure_text(str(exc))
            attempt.terminal(
                status="failed",
                outcome="blocked",
                details={"error_type": type(exc).__name__, "message": message},
            )
            raise CliError("provider_failed", message) from exc
        if result.returncode != 0:
            stderr = self._redact_failure_text((result.stderr or "").strip())
            stdout = self._redact_failure_text((result.stdout or "").strip())
            attempt.terminal(
                status="failed",
                outcome="indeterminate",
                details={
                    "returncode": result.returncode,
                    "stderr": stderr,
                    "stdout": stdout,
                },
            )
            if raise_on_failure:
                details = [
                    f"provider command failed (surface={surface}, returncode={result.returncode})"
                ]
                if stderr:
                    details.append(f"stderr: {stderr}")
                if stdout:
                    details.append(f"stdout: {stdout}")
                if not stderr and not stdout:
                    details.append("stderr: <empty>; stdout: <empty>")
                raise CliError("provider_failed", "; ".join(details))
            return result
        attempt.terminal(
            status="completed",
            outcome="succeeded",
            details={"returncode": result.returncode},
        )
        return result

    def _redact_failure_text(self, value: str) -> str:
        from arnold_pipelines.megaplan.cloud.redact import redact

        failure_env = dict(os.environ)
        # Provider failures and their WBC evidence must never become a secret
        # exfiltration surface, even when ordinary output redaction is disabled.
        failure_env["ARNOLD_REDACTION_ENABLED"] = "1"
        return redact(value, self._spec.secrets, env=failure_env)

    def _remote_run(
        self,
        command: str,
        *,
        capture_output: bool = True,
        input: str | None = None,
        surface: str = "remote_command",
        raise_on_failure: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        return self._run(
            [*self._ssh_destination_argv(), command],
            capture_output=capture_output,
            input=input,
            surface=surface,
            raise_on_failure=raise_on_failure,
        )

    def _host_observation(self, operation: str) -> subprocess.CompletedProcess[str]:
        """Run one of two internally constructed host observations."""
        if operation == "container":
            command = container_inspect_command(self._ssh.container)
            surface = "observe_container"
        elif operation == "predecessor-container":
            predecessor = self._spec.zero_recovery_predecessor_container
            if not predecessor:
                raise CliError(
                    "invalid_provider_observation",
                    "predecessor observation requires a zero-recovery predecessor",
                )
            command = container_inspect_command(predecessor)
            surface = "observe_predecessor_container"
        elif operation == "prelaunch-capacity":
            command = workspace_prelaunch_command(
                validate_workspace_dir(self._ssh.workspace_dir),
                min_free_bytes=self._spec.resources.prelaunch_min_free_bytes,
                min_free_inodes=self._spec.resources.prelaunch_min_free_inodes,
                receipt_reserve_bytes=self._spec.resources.prelaunch_receipt_reserve_bytes,
            )
            surface = "observe_prelaunch_capacity"
        elif operation == "capacity-inventory":
            command = capacity_inventory_command(
                workspace_dir=self._ssh.workspace_dir,
                remote_dir=self._ssh.remote_dir,
                cache_dir=self._ssh.cache_dir,
            )
            surface = "observe_capacity_inventory"
        else:
            raise CliError(
                "invalid_provider_observation",
                "SSH host observation is not allowlisted",
            )
        return self._run(
            [*self._ssh_destination_argv(), command],
            capture_output=True,
            surface=surface,
            raise_on_failure=False,
        )

    def observe_container(self) -> dict[str, Any]:
        result = self._host_observation("container")
        return classify_container_inspect(
            returncode=result.returncode,
            stdout=self._redact_failure_text(result.stdout or ""),
            stderr=self._redact_failure_text(result.stderr or ""),
            expected_container=self._ssh.container,
        )

    def observe_zero_recovery_predecessor(self) -> dict[str, Any]:
        predecessor = self._spec.zero_recovery_predecessor_container
        if not predecessor:
            raise CliError(
                "zero_recovery_predeploy_invalid", "zero-recovery predecessor missing"
            )
        result = self._host_observation("predecessor-container")
        return classify_container_inspect(
            returncode=result.returncode,
            stdout=self._redact_failure_text(result.stdout or ""),
            stderr=self._redact_failure_text(result.stderr or ""),
            expected_container=predecessor,
        )

    def observe_zero_recovery_predecessor_capacity(self) -> dict[str, Any]:
        workspace = validate_workspace_dir(self._ssh.workspace_dir)
        container = self.observe_zero_recovery_predecessor()
        mount = container.get("workspace_bind")
        if not isinstance(mount, dict) or (
            mount.get("status") != "present"
            or mount.get("type") != "bind"
            or mount.get("source") != workspace
            or mount.get("rw") is not True
        ):
            return {
                "schema": "arnold.cloud.ssh_workspace_prelaunch.v1",
                "status": "no-go",
                "verdict": "NO-GO",
                "workspace": workspace,
                "errors": ["configured_workspace_bind_mismatch"],
                "container": container,
            }
        result = self._host_observation("prelaunch-capacity")
        payload = parse_workspace_prelaunch_result(
            returncode=result.returncode,
            stdout=self._redact_failure_text(result.stdout or ""),
            stderr=self._redact_failure_text(result.stderr or ""),
            expected_workspace=workspace,
            min_free_bytes=self._spec.resources.prelaunch_min_free_bytes,
            min_free_inodes=self._spec.resources.prelaunch_min_free_inodes,
            receipt_reserve_bytes=self._spec.resources.prelaunch_receipt_reserve_bytes,
        )
        payload["container"] = container
        return payload

    def observe_prelaunch_capacity(self) -> dict[str, Any]:
        """Probe only the configured host bind; no arbitrary host path is accepted."""
        workspace = validate_workspace_dir(self._ssh.workspace_dir)
        container = self.observe_container()
        mount = container.get("workspace_bind")
        if not isinstance(mount, dict) or (
            mount.get("status") != "present"
            or mount.get("type") != "bind"
            or mount.get("source") != workspace
            or mount.get("rw") is not True
        ):
            return {
                "schema": "arnold.cloud.ssh_workspace_prelaunch.v1",
                "status": "no-go",
                "verdict": "NO-GO",
                "workspace": workspace,
                "errors": ["configured_workspace_bind_mismatch"],
                "container": container,
            }
        result = self._host_observation("prelaunch-capacity")
        payload = parse_workspace_prelaunch_result(
            returncode=result.returncode,
            stdout=self._redact_failure_text(result.stdout or ""),
            stderr=self._redact_failure_text(result.stderr or ""),
            expected_workspace=workspace,
            min_free_bytes=self._spec.resources.prelaunch_min_free_bytes,
            min_free_inodes=self._spec.resources.prelaunch_min_free_inodes,
            receipt_reserve_bytes=self._spec.resources.prelaunch_receipt_reserve_bytes,
        )
        payload["container"] = container
        expected_mount = container.get("workspace_bind", {}).get("source")
        if payload.get("workspace") != workspace or expected_mount != workspace:
            payload["status"] = "no-go"
            payload["verdict"] = "NO-GO"
            payload.setdefault("errors", []).append("observed_workspace_mount_mismatch")
        return payload

    def observe_capacity_inventory(self) -> dict[str, Any]:
        """Return a fixed read-only inventory; this method never reclaims data."""
        paths = [self._ssh.workspace_dir, self._ssh.remote_dir, self._ssh.cache_dir]
        result = self._host_observation("capacity-inventory")
        return parse_capacity_inventory_result(
            returncode=result.returncode,
            stdout=self._redact_failure_text(result.stdout or ""),
            stderr=self._redact_failure_text(result.stderr or ""),
            expected_paths=paths,
        )

    def _zero_recovery_target(self) -> dict[str, Any]:
        return {
            "host": self._validated_host,
            "user": self._validated_user,
            "port": self._validated_port,
            "container": self._spec.zero_recovery_predecessor_container,
            "canary_container": self._ssh.container,
            "workspace": validate_workspace_dir(self._ssh.workspace_dir),
            "capacity_scopes": [
                validate_workspace_dir(self._ssh.workspace_dir),
                validate_workspace_dir(self._ssh.remote_dir),
                validate_workspace_dir(self._ssh.cache_dir),
            ],
            "capacity_floor_bytes": (
                self._spec.resources.prelaunch_min_free_bytes
                + self._spec.resources.prelaunch_receipt_reserve_bytes
            ),
        }

    def prepare_zero_recovery_predeploy_transaction(self) -> dict[str, Any]:
        if not self._spec.zero_recovery_canary:
            raise CliError(
                "zero_recovery_predeploy_invalid",
                "predeploy transactions are only available for zero-recovery canaries",
            )
        outer = self.observe_zero_recovery_predecessor()
        capacity = self.observe_zero_recovery_predecessor_capacity()
        return build_predeploy_transaction(
            outer=outer,
            capacity=capacity,
            target=self._zero_recovery_target(),
        )

    def prepare_zero_recovery_bootstrap_reclaim(self) -> dict[str, Any]:
        """Prepare a dry-run-only, expiring bootstrap containment proposal."""
        if not self._spec.zero_recovery_canary:
            raise CliError(
                "zero_recovery_bootstrap_invalid",
                "bootstrap reclaim is only available for a zero-recovery canary",
            )
        outer = self.observe_zero_recovery_predecessor()
        prelaunch = self.observe_zero_recovery_predecessor_capacity()
        inventory = self.observe_capacity_inventory()
        return build_bootstrap_reclaim_transaction(
            outer=outer,
            prelaunch=prelaunch,
            inventory=inventory,
            target=self._zero_recovery_target(),
        )

    def apply_zero_recovery_bootstrap_reclaim(
        self, proposal: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Apply the one fixed stop/fence/dangling-build-cache bootstrap."""
        if not self._spec.zero_recovery_canary:
            raise CliError(
                "zero_recovery_bootstrap_invalid",
                "bootstrap reclaim is only available for a zero-recovery canary",
            )
        # These are the final client-side checks. The fixed remote script repeats
        # identity/inventory checks before its first containment mutation.
        outer = self.observe_zero_recovery_predecessor()
        prelaunch = self.observe_zero_recovery_predecessor_capacity()
        inventory = self.observe_capacity_inventory()
        transaction = validate_bootstrap_reclaim_transaction(
            proposal,
            target=self._zero_recovery_target(),
            outer=outer,
            prelaunch=prelaunch,
            inventory=inventory,
        )
        result = self._remote_run_compatible(
            bootstrap_reclaim_command(transaction),
            surface="zero_recovery_bootstrap_fence_reclaim",
        )
        return parse_bootstrap_reclaim_receipt(
            stdout=result.stdout or "",
            transaction_id=transaction["transaction_id"],
            transaction_digest=transaction["transaction_digest"],
        )

    def seed_zero_recovery_codex_oauth(self, auth_json: str) -> None:
        """Seed only Codex OAuth through one fixed container command."""
        if not self._spec.zero_recovery_canary or self._spec.megaplan.codex_auth != "chatgpt":
            raise CliError("zero_recovery_auth_invalid", "Codex ChatGPT OAuth required")
        try:
            payload = json.loads(auth_json)
        except json.JSONDecodeError as exc:
            raise CliError("zero_recovery_auth_invalid", "Codex auth was invalid JSON") from exc
        if not isinstance(payload, dict):
            raise CliError("zero_recovery_auth_invalid", "Codex auth must be an object")
        script = (
            "import os,pathlib,sys; data=sys.stdin.read(); "
            "targets=[pathlib.Path('/workspace/.creds/codex-auth.json'),pathlib.Path('/root/.codex/auth.json')]; "
            "[(p.parent.mkdir(parents=True,exist_ok=True),p.write_text(data,encoding='utf-8'),os.chmod(p,0o600)) for p in targets]; "
            "c=pathlib.Path('/root/.codex/config.toml'); c.write_text('preferred_auth_method = \\\"chatgpt\\\"\\nforced_login_method = \\\"chatgpt\\\"\\nmodel = \\\"gpt-5.6-sol\\\"\\nmodel_reasoning_effort = \\\"high\\\"\\napproval_policy = \\\"never\\\"\\nsandbox_mode = \\\"danger-full-access\\\"\\n',encoding='utf-8'); os.chmod(c,0o600)"
        )
        self._remote_run_compatible(
            shlex.join(
                [
                    "docker",
                    "exec",
                    "-i",
                    self._ssh.container,
                    "python3",
                    "-c",
                    script,
                ]
            ),
            input=auth_json,
            surface="zero_recovery_codex_oauth_seed",
        )

    def _observe_zero_recovery_canary_runtime(
        self, *, expected_running: bool = True
    ) -> dict[str, Any]:
        command = shlex.join(
            [
                "docker",
                "inspect",
                "--type",
                "container",
                "--format",
                "{{json .State}}\n{{json .Config.Env}}\n{{json .Config.Cmd}}\n{{json .HostConfig.RestartPolicy}}",
                self._ssh.container,
            ]
        )
        result = self._remote_run_compatible(
            command, surface="observe_zero_recovery_canary_runtime"
        )
        lines = (result.stdout or "").splitlines()
        try:
            state, env, cmd, restart = [json.loads(line) for line in lines]
        except (ValueError, json.JSONDecodeError) as exc:
            raise CliError(
                "zero_recovery_canary_unknown", "canary runtime evidence malformed"
            ) from exc
        if (
            len(lines) != 4
            or not isinstance(state, dict)
            or state.get("Running") is not expected_running
            or not isinstance(env, list)
            or "MEGAPLAN_ZERO_RECOVERY_CANARY=1" not in env
            or cmd != ["/usr/local/bin/entrypoint.sh"]
            or restart != {"Name": "no", "MaximumRetryCount": 0}
        ):
            raise CliError(
                "zero_recovery_canary_unknown",
                "canary runtime flag, entrypoint, lifecycle, or restart policy mismatch",
            )
        return {"state": state, "env": env, "cmd": cmd, "restart_policy": restart}

    def run_zero_recovery_canary(
        self, *, source_commit: str, source_tree: str
    ) -> int:
        """Invoke only the tracked finite runner in one exact fresh checkout."""
        if not self._spec.zero_recovery_canary:
            raise CliError("zero_recovery_canary_unavailable", "zero profile required")
        self._observe_zero_recovery_canary_runtime()
        if (
            len(source_commit) != 40
            or any(character not in "0123456789abcdef" for character in source_commit)
            or len(source_tree) != 40
            or any(character not in "0123456789abcdef" for character in source_tree)
        ):
            raise CliError(
                "zero_recovery_canary_invalid",
                "zero canary repo.branch must be an exact lowercase source commit",
            )
        workspace = PurePosixPath(self._spec.repo.workspace)
        if not workspace.is_absolute() or workspace == PurePosixPath("/"):
            raise CliError("zero_recovery_canary_invalid", "invalid canary workspace")
        runner = workspace / ".megaplan/initiatives/critique-ledger-safe-v3-canary/run_canary.py"
        inner = " && ".join(
            [
                f"test ! -e {shlex.quote(str(workspace))}",
                f"git clone --single-branch --branch {shlex.quote(self._spec.repo.branch)} --no-checkout -- {shlex.quote(self._spec.repo.url)} {shlex.quote(str(workspace))}",
                f"git -C {shlex.quote(str(workspace))} checkout --detach {source_commit}",
                f"test \"$(git -C {shlex.quote(str(workspace))} rev-parse HEAD)\" = {source_commit}",
                f"test \"$(git -C {shlex.quote(str(workspace))} rev-parse HEAD^{{tree}})\" = {source_tree}",
                f"cd {shlex.quote(str(workspace))}",
                f"MEGAPLAN_ZERO_RECOVERY_CANARY=1 PYTHONPATH={shlex.quote(str(workspace))} python3 -P {shlex.quote(str(runner))}",
            ]
        )
        run_error: Exception | None = None
        try:
            self._remote_run_compatible(
                shlex.join(
                    [
                        "docker",
                        "exec",
                        self._ssh.container,
                        "bash",
                        "-lc",
                        inner,
                    ]
                ),
                capture_output=False,
                surface="zero_recovery_finite_canary_run",
            )
        except Exception as exc:
            run_error = exc
        self._remote_run_compatible(
            shlex.join(["docker", "stop", self._ssh.container]),
            surface="zero_recovery_finite_canary_stop",
        )
        stopped = self.observe_container()
        if (
            stopped.get("status") != "available"
            or stopped.get("lifecycle") != "stopped"
            or stopped.get("container") != self._ssh.container
        ):
            raise CliError(
                "zero_recovery_canary_stop_unknown",
                "finite canary did not prove an exact stopped terminal container",
            )
        self._observe_zero_recovery_canary_runtime(expected_running=False)
        if run_error is not None:
            raise run_error
        return 0

    def execute_zero_recovery_canary(
        self, auth_json: str, *, source_commit: str, source_tree: str
    ) -> int:
        """Terminal-safe orchestration from first credential mutation onward."""
        terminal_error: Exception | None = None
        result = 1
        try:
            self._observe_zero_recovery_canary_runtime()
            self.seed_zero_recovery_codex_oauth(auth_json)
            result = self.run_zero_recovery_canary(
                source_commit=source_commit, source_tree=source_tree
            )
        except Exception as exc:
            terminal_error = exc
        observation = self.observe_container()
        if observation.get("lifecycle") == "running":
            self._remote_run_compatible(
                shlex.join(["docker", "stop", self._ssh.container]),
                surface="zero_recovery_finite_canary_terminal_stop",
            )
            observation = self.observe_container()
        if observation.get("lifecycle") != "stopped":
            raise CliError(
                "zero_recovery_canary_stop_unknown",
                "terminal reconciliation did not prove a stopped canary",
            )
        self._observe_zero_recovery_canary_runtime(expected_running=False)
        if terminal_error is not None:
            raise terminal_error
        return result

    def zero_recovery_canary_status(self) -> dict[str, Any]:
        """Read one fixed host-side receipt directory; never container-exec."""
        repo_workspace = PurePosixPath(self._spec.repo.workspace)
        workspace_root = PurePosixPath("/workspace")
        try:
            relative = repo_workspace.relative_to(workspace_root)
        except ValueError as exc:
            raise CliError(
                "zero_recovery_canary_invalid",
                "canary repo workspace must be below /workspace",
            ) from exc
        host_receipts = (
            PurePosixPath(self._ssh.workspace_dir)
            / relative
            / ".megaplan/initiatives/critique-ledger-safe-v3-canary/receipts"
        )
        script = (
            "import hashlib,json,pathlib,sys; root=pathlib.Path(sys.argv[1]); "
            "files=sorted(root.glob('*.run-receipt.json')) if root.is_dir() else []; "
            "payload={'schema':'arnold.cloud.zero_recovery_canary_status.v1','status':'available' if len(files)==1 else 'unknown','receipt':json.loads(files[0].read_text(encoding='utf-8')) if len(files)==1 else None,'receipt_sha256':hashlib.sha256(files[0].read_bytes()).hexdigest() if len(files)==1 else None,'receipt_count':len(files)}; "
            "print(json.dumps(payload,sort_keys=True))"
        )
        result = self._remote_run_compatible(
            shlex.join(["python3", "-c", script, str(host_receipts)]),
            surface="zero_recovery_canary_status",
        )
        try:
            payload = json.loads(result.stdout or "")
        except json.JSONDecodeError as exc:
            raise CliError(
                "zero_recovery_canary_unknown", "canary status was invalid JSON"
            ) from exc
        if (
            not isinstance(payload, dict)
            or set(payload)
            != {"schema", "status", "receipt", "receipt_sha256", "receipt_count"}
            or payload.get("schema") != "arnold.cloud.zero_recovery_canary_status.v1"
            or payload.get("status") not in {"available", "unknown"}
            or type(payload.get("receipt_count")) is not int
        ):
            raise CliError(
                "zero_recovery_canary_unknown", "canary status schema mismatch"
            )
        observation = self.observe_container()
        reconciled_stop = False
        if payload.get("status") == "available" and observation.get("lifecycle") == "running":
            self._remote_run_compatible(
                shlex.join(["docker", "stop", self._ssh.container]),
                surface="zero_recovery_finite_canary_reconcile_stop",
            )
            observation = self.observe_container()
            reconciled_stop = True
        if payload.get("status") == "available" and observation.get("lifecycle") != "stopped":
            raise CliError(
                "zero_recovery_canary_stop_unknown",
                "terminal receipt exists without an exact stopped canary",
            )
        payload["container_observation"] = observation
        payload["reconciled_stop"] = reconciled_stop
        return payload

    def _remote_run_compatible(
        self,
        command: str,
        *,
        capture_output: bool = True,
        input: str | None = None,
        surface: str,
    ) -> subprocess.CompletedProcess[str]:
        """Preserve provenance while supporting predecessor provider overrides."""
        parameters = inspect.signature(self._remote_run).parameters
        if "surface" in parameters:
            return self._remote_run(
                command,
                capture_output=capture_output,
                input=input,
                surface=surface,
            )
        return self._remote_run(
            command,
            capture_output=capture_output,
            input=input,
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
                    shlex.join([*self._ssh_transport_argv(), "--"]),
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
                str(self._validated_port),
                *(
                    ["-i", self._validated_identity_file]
                    if self._validated_identity_file
                    else []
                ),
                "--",
                f"{deploy_dir}/.",
                f"{self._target()}:{remote_dir}",
            ],
            surface="sync_scp",
        )

    # ── Step 13F: WBC routing integration ─────────────────────────────────

    def _maybe_route_through_wbc(
        self,
        shard: str,
        intent_payload: dict[str, Any],
        apply_fn: Any,
    ) -> int:
        """Route an SSH mutation through the WBC adapter if configured.

        Step 13F: When the ssh_effect_adapter is provided, route build/deploy/
        destroy through the WBC protocol.  Returns 0 on success, raises on
        failure (matching existing SshProvider semantics).
        """
        adapter = self._ssh_effect_adapter
        if adapter is None:
            # No adapter configured — run directly (backward compat)
            return apply_fn(intent_payload) or 0

        from arnold_pipelines.megaplan.cloud.ssh_effect_adapter import (
            SshEffectShard,
            SshTarget,
        )

        target = SshTarget(
            shard=SshEffectShard(shard),
            host=self._ssh.host,
            container=self._ssh.container,
            operation=shard,
        )

        outcome = adapter.route(
            target=target,
            intent_payload=intent_payload,
            apply_fn=lambda _: apply_fn(intent_payload),
        )

        if not outcome.ok:
            raise CliError(
                "provider_failed",
                outcome.error or f"WBC gate blocked SSH {shard}",
            )
        return 0

    def build(self, deploy_dir: Path) -> int:
        # Step 13F: route through WBC when adapter is configured
        if self._ssh_effect_adapter is not None:
            return self._maybe_route_through_wbc(
                "build",
                {"deploy_dir": str(deploy_dir), "container": self._ssh.container},
                lambda _: self._build_direct(deploy_dir),
            )
        return self._build_direct(deploy_dir)

    def _build_direct(self, deploy_dir: Path) -> int:
        self._sync_deploy_dir(deploy_dir)
        self._remote_run(
            f"docker build -t {shlex.quote(self._ssh.container)} {shlex.quote(self._ssh.remote_dir)}",
            surface="build",
        )
        return 0

    def deploy(
        self,
        deploy_dir: Path,
        *,
        secrets: dict[str, str],
        predeploy_transaction: Mapping[str, Any] | None = None,
    ) -> int:
        # Step 13F: route through WBC when adapter is configured
        if self._ssh_effect_adapter is not None:
            return self._maybe_route_through_wbc(
                "deploy",
                {
                    "deploy_dir": str(deploy_dir),
                    "container": self._ssh.container,
                    "port": self._spec.resources.port,
                },
                lambda _: self._deploy_direct(
                    deploy_dir,
                    secrets=secrets,
                    predeploy_transaction=predeploy_transaction,
                ),
            )
        return self._deploy_direct(
            deploy_dir,
            secrets=secrets,
            predeploy_transaction=predeploy_transaction,
        )

    def _deploy_direct(
        self,
        deploy_dir: Path,
        *,
        secrets: dict[str, str],
        predeploy_transaction: Mapping[str, Any] | None = None,
    ) -> int:
        del deploy_dir
        transaction: dict[str, Any] | None = None
        launch_container = True
        if self._spec.zero_recovery_canary:
            if predeploy_transaction is None:
                raise CliError(
                    "zero_recovery_predeploy_required",
                    "zero-recovery deploy requires a fresh predeploy transaction",
                )
            final_outer = self.observe_zero_recovery_predecessor()
            final_capacity = self.observe_zero_recovery_predecessor_capacity()
            transaction = validate_predeploy_transaction(
                predeploy_transaction,
                target=self._zero_recovery_target(),
                outer=final_outer,
                capacity=final_capacity,
            )
            transaction_id = transaction["transaction_id"]
            if transaction_id in self._consumed_zero_recovery_transactions:
                raise CliError(
                    "zero_recovery_predeploy_replayed",
                    "zero-recovery predeploy transaction was already consumed",
                )
            # Consume before the first mutation. A later ambiguous failure may
            # be reconciled, but this provider instance never redispatches it.
            self._consumed_zero_recovery_transactions.add(transaction_id)
            apply_fence = self._remote_run_compatible(
                fence_command(
                    self._ssh.workspace_dir,
                    action="apply",
                    transaction_id=transaction_id,
                    transaction_digest=transaction["transaction_digest"],
                ),
                surface="zero_recovery_fence_apply",
            )
            parse_fence_receipt(
                stdout=apply_fence.stdout or "",
                transaction_id=transaction_id,
                transaction_digest=transaction["transaction_digest"],
                stage="apply",
            )
            canary_observation = self.observe_container()
            if canary_observation.get("lifecycle") == "missing":
                launch_container = True
            elif (
                canary_observation.get("status") == "available"
                and canary_observation.get("lifecycle") == "running"
                and canary_observation.get("image_ref") == self._ssh.container
                and canary_observation.get("workspace_bind")
                == {
                    "status": "present",
                    "type": "bind",
                    "source": self._ssh.workspace_dir,
                    "destination": "/workspace",
                    "rw": True,
                }
            ):
                self._observe_zero_recovery_canary_runtime()
                launch_container = False
            else:
                raise CliError(
                    "zero_recovery_canary_collision",
                    "canary target name exists with an unknown or mismatched identity",
                )
        env_path = f"{self._ssh.remote_dir}/.env"
        env_lines = [f"PORT={self._spec.resources.port}"]
        if self._spec.zero_recovery_canary:
            env_lines.append("MEGAPLAN_ZERO_RECOVERY_CANARY=1")
        env_lines.extend(f"{name}={value}" for name, value in secrets.items())
        if launch_container:
            self._remote_run_compatible(
                "mkdir -p "
                f"{shlex.quote(self._ssh.remote_dir)} "
                f"{shlex.quote(self._ssh.workspace_dir)} "
                f"{shlex.quote(f'{self._ssh.cache_dir}/pip')} "
                f"{shlex.quote(f'{self._ssh.cache_dir}/npm')}",
                surface="deploy_prepare",
            )
            self._remote_run_compatible(
                f"cat > {shlex.quote(env_path)}",
                input="\n".join(env_lines) + "\n",
                surface="deploy_env",
            )
        if not self._spec.zero_recovery_canary:
            self._remote_run_compatible(
                f"docker rm -f {shlex.quote(self._ssh.container)} >/dev/null 2>&1 || true",
                surface="deploy_remove_existing",
            )
        if launch_container:
            self._remote_run_compatible(
                " ".join(
                [
                    "docker run -d",
                    f"--name {shlex.quote(self._ssh.container)}",
                    "--restart no"
                    if self._spec.zero_recovery_canary
                    else "--restart unless-stopped",
                    *(
                        ["-e MEGAPLAN_ZERO_RECOVERY_CANARY=1"]
                        if self._spec.zero_recovery_canary
                        else []
                    ),
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
        if transaction is not None:
            verify_fence = self._remote_run_compatible(
                fence_command(
                    self._ssh.workspace_dir,
                    action="verify",
                    transaction_id=transaction["transaction_id"],
                    transaction_digest=transaction["transaction_digest"],
                ),
                surface="zero_recovery_fence_verify",
            )
            parse_fence_receipt(
                stdout=verify_fence.stdout or "",
                transaction_id=transaction["transaction_id"],
                transaction_digest=transaction["transaction_digest"],
                stage="verify",
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
                [*self._ssh_destination_argv(), argv.strip()],
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
        # Step 13F: route through WBC when adapter is configured
        if self._ssh_effect_adapter is not None:
            return self._maybe_route_through_wbc(
                "destroy",
                {"container": self._ssh.container, "remote_dir": self._ssh.remote_dir},
                lambda _: self._destroy_direct(volume=volume),
            )
        return self._destroy_direct(volume=volume)

    def _destroy_direct(self, *, volume: str | None = None) -> int:
        del volume
        self._remote_run(
            f"docker rm -f {shlex.quote(self._ssh.container)} >/dev/null 2>&1 || true && rm -rf {shlex.quote(self._ssh.remote_dir)}",
            surface="destroy",
        )
        return 0
