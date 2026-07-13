"""CLI entrypoints for arnold cloud commands."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, replace
from importlib import resources
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any, Mapping

import yaml

from arnold_pipelines.megaplan.cloud.auth import seed_codex_oauth
from arnold_pipelines.megaplan.cloud.providers.base import (
    DeployReport,
    DeployStepReport,
    _write_redacted_output,
    get_provider,
)
from arnold_pipelines.megaplan.cloud.redact import redact
from arnold_pipelines.megaplan.cloud.spec import CloudSpec, apply_repo_overrides, load_spec as load_cloud_spec
from arnold_pipelines.megaplan.cloud import status_format, status_snapshot
from arnold_pipelines.megaplan.fallback_chains import decode_phase_model_value, encode_phase_model_value
from arnold_pipelines.megaplan.cloud.template import materialize_deploy_dir, render_ensure_repos_block
from arnold_pipelines.megaplan.layout import is_canonical_chain_spec
from arnold_pipelines.megaplan.types import CliError


load_spec = load_cloud_spec
CLOUD_STATUS_CLI_MAX_AGE_S = 5 * 60

# Cloud deployments always drive phases via subprocess (remote SSH exec);
# the substrate is pinned here so the cloud CLI explicitly declares its
# execution model to _phase_command (M3 Step 12 compatibility boundary).
cloud_substrate: str = "subprocess_isolated"

_TEMPLATE_PLACEHOLDER_RE = re.compile(
    r"\bTODO(?:_[A-Z0-9]+)+\b|<box-ip>|TODO_SSH_HOST|TODO_REPO_URL"
)


def _register_cloud_subcommands(cloud_parser: argparse.ArgumentParser) -> None:
    cloud_sub = cloud_parser.add_subparsers(dest="cloud_action", required=True)

    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "--cloud-yaml",
        default=None,
        help="Path to cloud.yaml (default: <project-root>/cloud.yaml)",
    )

    init_parser = cloud_sub.add_parser(
        "init",
        parents=[shared],
        help="Scaffold a cloud.yaml file at the project root",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing cloud.yaml",
    )

    cloud_sub.add_parser("build", parents=[shared], help="Build the cloud image")
    cloud_sub.add_parser("deploy", parents=[shared], help="Deploy the cloud runner")

    quickstart_parser = cloud_sub.add_parser(
        "quickstart",
        parents=[shared],
        help="Create a cloud-ready one-sprint initiative from one brief, preflight it, and optionally launch",
    )
    quickstart_parser.add_argument("--slug", required=True, help="Initiative slug and default cloud session name")
    quickstart_parser.add_argument("--brief", required=True, help="Markdown/text brief to use as the milestone input")
    quickstart_parser.add_argument(
        "--north-star",
        required=True,
        help="Existing North Star markdown/text file to copy into the generated initiative",
    )
    quickstart_parser.add_argument("--title", default=None, help="Human title for README/North Star")
    quickstart_parser.add_argument("--milestone-title", default="First Sprint", help="Milestone title")
    quickstart_parser.add_argument("--base-branch", default=None, help="Base branch (default: current git branch, else main)")
    quickstart_parser.add_argument("--profile", default="partnered-5", help="Megaplan profile for the generated milestone")
    quickstart_parser.add_argument("--vendor", default="codex", help="Vendor for the generated milestone")
    quickstart_parser.add_argument("--depth", default="high", help="Reasoning depth for the generated milestone")
    quickstart_parser.add_argument("--robustness", default="thorough", help="Robustness setting for chain driver/milestone")
    quickstart_parser.add_argument("--branch", default=None, help="Implementation branch (default: slug)")
    quickstart_parser.add_argument("--repo-url", default=None, help="Repo URL (default: inferred from git remote origin)")
    quickstart_parser.add_argument(
        "--target",
        default="hetzner-agentbox",
        choices=("hetzner-agentbox", "custom"),
        help="Cloud target profile. Use custom with --ssh-host for non-default boxes.",
    )
    quickstart_parser.add_argument(
        "--extra-repo",
        action="append",
        default=[],
        metavar="ROLE=URL[@BRANCH[:WORKSPACE]]",
        help=(
            "Add an extra repo checkout to cloud.yaml. Repeatable. Common form: "
            "worker=https://github.com/org/worker.git. Advanced: "
            "worker=https://github.com/org/worker.git@develop:/workspace/custom-worker. "
            "Legacy URL@branch=/workspace/path is also accepted."
        ),
    )
    quickstart_parser.add_argument("--ssh-host", default=None, help="SSH host override")
    quickstart_parser.add_argument("--ssh-user", default="root", help="SSH user")
    quickstart_parser.add_argument("--ssh-port", type=int, default=22, help="SSH port")
    quickstart_parser.add_argument("--engine-ref", default="editible-install", help="Cloud megaplan engine ref")
    quickstart_parser.add_argument(
        "--sync-local-engine",
        action="store_true",
        help="Also sync this local Arnold checkout to editible-install before launch",
    )
    quickstart_parser.add_argument(
        "--launch",
        action="store_true",
        help="After writing and preflighting the initiative, start the cloud chain",
    )
    quickstart_parser.add_argument(
        "--fresh",
        "--reset",
        dest="fresh",
        action="store_true",
        help="When launching, reset this chain's remote state first",
    )
    quickstart_parser.add_argument("--force", action="store_true", help="Overwrite generated initiative/cloud files")
    quickstart_parser.add_argument(
        "--skip-remote",
        action="store_true",
        help="Only run local preflight checks; do not SSH to the worker",
    )

    chain_parser = cloud_sub.add_parser(
        "chain",
        parents=[shared],
        help="Upload a chain spec and start it remotely",
    )
    chain_parser.add_argument("spec", help="Local chain spec path")
    chain_parser.add_argument(
        "--on-box",
        action="store_true",
        help="Launch from inside the agentbox without SSH, preserving cloud tmux/marker/watchdog setup",
    )
    chain_parser.add_argument(
        "--idea-dir",
        default=None,
        help="Directory containing local idea files referenced by the chain spec",
    )
    chain_parser.add_argument(
        "--fresh",
        "--reset",
        dest="fresh",
        action="store_true",
        help="Reset this chain's remote state before launch",
    )
    chain_parser.add_argument(
        "--no-git-refresh",
        action="store_true",
        help=(
            "Pass --no-git-refresh to the remote `python -m arnold_pipelines.megaplan chain start`, "
            "skipping the automatic base-branch refresh."
        ),
    )
    chain_parser.add_argument(
        "--no-editable-install-sync",
        action="store_true",
        help=(
            "Skip the pre-launch push that merges the current local HEAD into "
            "the cloud editable install branch."
        ),
    )
    chain_parser.add_argument(
        "--force-clean-editable-install",
        action="store_true",
        help=(
            "Before remote editable-install refresh, reset and clean only "
            "megaplan.src_path. Opt-in recovery for dirty remote Arnold checkouts."
        ),
    )
    chain_parser.add_argument(
        "--allow-loose-chain-spec",
        action="store_true",
        help=(
            "Allow launching a chain spec outside .megaplan/initiatives/<initiative>/chain.yaml. "
            "Intended only for temporary compatibility."
        ),
    )
    chain_parser.add_argument(
        "--allow-template-placeholders",
        action="store_true",
        help=(
            "Required override to launch even when initiative/cloud files still contain "
            "template placeholders such as TODO_REPO_URL or TODO_SSH_HOST."
        ),
    )
    chain_parser.add_argument(
        "--allow-human-gates",
        action="store_true",
        help=(
            "Required override to launch a cloud chain whose chain.yaml uses "
            "merge_policy != auto or driver.auto_approve: false."
        ),
    )
    _add_repo_override_args(chain_parser)

    sync_parser = cloud_sub.add_parser(
        "sync-megaplan",
        parents=[shared],
        help="Upload durable .megaplan planning artifacts to the cloud workspace",
    )
    sync_parser.add_argument(
        "spec",
        nargs="?",
        help=(
            "Optional local .megaplan/initiatives/<initiative>/chain.yaml. When supplied, "
            "uses the same derived cloud workspace as `cloud chain`."
        ),
    )
    sync_parser.add_argument(
        "--workspace",
        default=None,
        help="Explicit remote workspace override. Use only for manual migration.",
    )
    sync_parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove remote durable .megaplan/initiatives, tickets, and ideas before upload.",
    )
    sync_parser.add_argument(
        "--allow-loose-chain-spec",
        action="store_true",
        help="Allow a sync target chain spec outside .megaplan/initiatives/<initiative>/chain.yaml.",
    )
    _add_repo_override_args(sync_parser)

    launch_epic_parser = cloud_sub.add_parser(
        "launch-epic",
        parents=[shared],
        help="Validate, canonicalize, upload, launch, and watchdog-verify a cloud epic",
    )
    launch_epic_parser.add_argument("spec_or_dir", help="Local chain.yaml or epic brief directory")
    launch_epic_parser.add_argument(
        "--on-box",
        action="store_true",
        help="Launch from inside the agentbox without SSH, preserving cloud tmux/marker/watchdog setup",
    )
    launch_epic_parser.add_argument(
        "--slug",
        default=None,
        help="Override the canonical epic slug (default: chain directory name)",
    )
    launch_epic_parser.add_argument(
        "--fresh",
        "--reset",
        dest="fresh",
        action="store_true",
        help="Reset this chain's remote state before launch",
    )
    launch_epic_parser.add_argument(
        "--no-git-refresh",
        action="store_true",
        help="Pass --no-git-refresh to the remote chain start command",
    )
    launch_epic_parser.add_argument(
        "--no-editable-install-sync",
        action="store_true",
        help="Skip syncing the launching Arnold checkout to editible-install before launch",
    )
    _add_repo_override_args(launch_epic_parser)

    preflight_parser = cloud_sub.add_parser(
        "preflight",
        parents=[shared],
        help="Validate a cloud chain spec and probe the worker before launch",
    )
    preflight_parser.add_argument("spec", help="Local .megaplan/initiatives/<initiative>/chain.yaml")
    preflight_parser.add_argument(
        "--skip-remote",
        action="store_true",
        help="Only run local spec/profile validation; do not SSH to the worker",
    )
    preflight_parser.add_argument(
        "--allow-loose-chain-spec",
        action="store_true",
        help="Allow a chain spec outside .megaplan/initiatives/<initiative>/chain.yaml.",
    )
    preflight_parser.add_argument(
        "--allow-template-placeholders",
        action="store_true",
        help=(
            "Required override to pass preflight even when initiative/cloud files still "
            "contain template placeholders."
        ),
    )
    preflight_parser.add_argument(
        "--allow-human-gates",
        action="store_true",
        help=(
            "Required override to pass preflight for cloud chains that intentionally "
            "pause for human PR merges or verification gates."
        ),
    )
    _add_repo_override_args(preflight_parser)

    epic_chain_parser = cloud_sub.add_parser(
        "epic-chain",
        parents=[shared],
        help="Upload durable epic-chain inputs and start the parent epic-chain remotely",
    )
    epic_chain_parser.add_argument("spec", help="Local epic-chain spec path")
    epic_chain_parser.add_argument(
        "--fresh",
        "--reset",
        dest="fresh",
        action="store_true",
        help="Reset this parent epic-chain state before launch",
    )
    epic_chain_parser.add_argument(
        "--one",
        action="store_true",
        help="Advance at most one completed child epic, then stop cleanly",
    )
    epic_chain_parser.add_argument(
        "--no-editable-install-sync",
        action="store_true",
        help="Skip syncing the launching Arnold checkout to editible-install before launch",
    )
    _add_repo_override_args(epic_chain_parser)

    bootstrap_parser = cloud_sub.add_parser(
        "bootstrap",
        parents=[shared],
        help="Upload an idea file and start arnold init remotely",
    )
    bootstrap_parser.add_argument("idea_file", help="Local idea file path")
    bootstrap_parser.add_argument("--plan-name", default=None, help="Optional remote plan name")
    bootstrap_parser.add_argument("--robustness", default="standard")
    _add_repo_override_args(bootstrap_parser)

    status_parser = cloud_sub.add_parser(
        "status",
        parents=[shared],
        help="Fetch remote `arnold status` JSON",
    )
    status_parser.add_argument(
        "--chain",
        action="store_true",
        help="Fetch remote chain_state.json and render core chain status",
    )
    status_parser.add_argument(
        "--all",
        action="store_true",
        help="List all known cloud sessions from the marker registry with live/health evidence",
    )
    status_parser.add_argument(
        "--compact",
        action="store_true",
        help="With --all, print a compact operator table before the JSON payload",
    )
    status_parser.add_argument(
        "--since",
        default=None,
        help="With --all, filter sessions to real activity since a duration or ISO timestamp, e.g. 12h",
    )
    status_parser.add_argument(
        "--remote-spec",
        default=None,
        help="Explicit remote chain spec path for `cloud status --chain`",
    )
    status_parser.add_argument("--plan", help="Optional plan name to query remotely")

    attach_parser = cloud_sub.add_parser(
        "attach",
        parents=[shared],
        help="Attach to the remote tmux session",
    )
    attach_parser.add_argument(
        "--session",
        help="Override the remote tmux session name for providers that support sessions",
    )

    logs_parser = cloud_sub.add_parser(
        "logs",
        parents=[shared],
        help="Stream or fetch remote logs",
    )
    logs_parser.add_argument(
        "--no-follow",
        action="store_true",
        help="Fetch recent logs without streaming",
    )

    chains_parser = cloud_sub.add_parser(
        "chains",
        parents=[shared],
        help="List active cloud chain tmux sessions on the shared runner",
    )
    chains_parser.add_argument(
        "--compact",
        action="store_true",
        help="Print a compact operator table before the JSON payload",
    )
    chains_parser.add_argument(
        "--since",
        default=None,
        help="Filter sessions to real activity since a duration or ISO timestamp, e.g. 12h",
    )

    exec_parser = cloud_sub.add_parser(
        "exec",
        parents=[shared],
        help="Run an arbitrary remote command",
    )
    exec_parser.add_argument("command", help="Command string to execute remotely")

    resume_parser = cloud_sub.add_parser(
        "resume",
        parents=[shared],
        help="Resume the remote plan's next step",
    )
    resume_parser.add_argument("--plan", help="Optional plan name to resume")

    pause_chain_parser = cloud_sub.add_parser(
        "pause-chain", parents=[shared], help="Durably pause one chain and stop only its runner"
    )
    pause_chain_parser.add_argument("--reason", required=True)
    pause_chain_parser.add_argument("--actor", default="operator")

    resume_chain_parser = cloud_sub.add_parser(
        "resume-chain", parents=[shared], help="Explicitly resume a durably paused chain"
    )
    resume_chain_parser.add_argument("--actor", default="operator")

    cloud_sub.add_parser("down", parents=[shared], help="Pause the deployment without deleting volume")

    supervise_parser = cloud_sub.add_parser(
        "supervise",
        parents=[shared],
        help="Run a one-shot supervisor tick against a cloud chain",
    )
    supervise_parser.add_argument(
        "--chain",
        action="store_true",
        help="Supervise the remote chain (required)",
    )
    supervise_parser.add_argument(
        "--remote-spec",
        default=None,
        help="Explicit remote chain spec path for supervision",
    )

    destroy_parser = cloud_sub.add_parser(
        "destroy",
        parents=[shared],
        help="Tear down the deployment and delete the volume if configured",
    )
    destroy_parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive destroy confirmation",
    )


def build_cloud_parser(subparsers: Any) -> None:
    cloud_parser = subparsers.add_parser(
        "cloud",
        help="Manage provider-backed arnold cloud runners",
    )
    _register_cloud_subcommands(cloud_parser)


def _add_repo_override_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo-url", default=None, help="Override cloud.yaml repo.url in memory")
    parser.add_argument("--repo-branch", default=None, help="Override cloud.yaml repo.branch in memory")
    parser.add_argument("--repo-workspace", default=None, help="Override cloud.yaml repo.workspace in memory")


def run_cloud_cli(root: Path, args: argparse.Namespace) -> int:
    try:
        action = getattr(args, "cloud_action")
        if action == "init":
            return _run_init(root, args)
        if action == "quickstart":
            return _run_quickstart(root, args)

        spec = _load_cloud_spec(root, args)
        provider = _provider_for_action(spec, args)

        if action == "chain":
            with _materialized_deploy_dir(spec):
                return _run_chain_wrapper(root, args, spec, provider)

        if action == "sync-megaplan":
            return _run_sync_megaplan(root, args, spec, provider)

        if action == "launch-epic":
            with _materialized_deploy_dir(spec):
                return _run_launch_epic_wrapper(root, args, spec, provider)

        if action == "preflight":
            return _run_preflight(root, args, spec, provider)

        if action == "epic-chain":
            with _materialized_deploy_dir(spec):
                return _run_epic_chain_wrapper(root, args, spec, provider)

        if action == "bootstrap":
            with _materialized_deploy_dir(spec):
                return _run_bootstrap_wrapper(args, spec, provider)

        if action == "build":
            with _materialized_deploy_dir(spec) as deploy_dir:
                return provider.build(deploy_dir)

        if action == "deploy":
            secrets = {name: os.environ.get(name, "") for name in spec.secrets}
            with _materialized_deploy_dir(spec) as deploy_dir:
                result = provider.deploy(deploy_dir, secrets=secrets)
                report = _coerce_deploy_report(result, spec=spec, deploy_dir=deploy_dir)
                report.steps = [
                    *_deploy_context_steps(deploy_dir),
                    *report.steps,
                ]
            if report.exit_code == 0:
                seed_messages: list[str] = []
                seed_result = seed_codex_oauth(spec, provider, writer=seed_messages.append)
                report.steps.append(
                    DeployStepReport(
                        name="seed Codex OAuth",
                        status="ok",
                        detail=_oauth_seed_detail(seed_result),
                        stderr="".join(seed_messages),
                        metadata=seed_result,
                    )
                )
            _emit_deploy_report(report, secret_names=spec.secrets, env=os.environ)
            return report.exit_code

        if action == "status":
            if bool(getattr(args, "all", False)):
                return _run_status_all(spec, provider, args=args)
            if _status_should_use_chain(root, args, spec):
                return _run_chain_status(root, args, spec, provider)
            payload = cloud_status_payload(args, spec, provider)
            sys.stdout.write(json.dumps(payload, indent=2) + "\n")
            return 0

        if action == "attach":
            return provider.attach()

        if action == "logs":
            return provider.logs(follow=not bool(getattr(args, "no_follow", False)))

        if action == "chains":
            return _run_cloud_chains(spec, provider, args=args)

        if action == "exec":
            result = provider.ssh_exec(args.command)
            _relay_output(result, secret_names=spec.secrets, env=os.environ)
            return 0

        if action == "resume":
            resume_workspace = _resolve_resume_workspace(root, args, spec, provider)
            payload = provider.status_payload(
                plan=getattr(args, "plan", None),
                workspace=resume_workspace,
            )
            next_step = payload.get("next_step")
            if not isinstance(next_step, str) or not next_step:
                raise CliError("invalid_status", "Remote status did not include a next_step")
            plan_name = getattr(args, "plan", None)
            if payload.get("state") == "failed" and isinstance(plan_name, str) and plan_name:
                argv = ["resume", "--plan", plan_name]
            else:
                from arnold_pipelines.megaplan.auto import _phase_command

                argv = list(_phase_command(next_step, substrate=cloud_substrate))
                if plan_name:
                    argv.extend(["--plan", plan_name])
            command = f"cd {shlex.quote(resume_workspace)} && arnold {shlex.join(argv)}"
            result = provider.ssh_exec(command)
            _relay_output(result, secret_names=spec.secrets, env=os.environ)
            return 0

        if action in {"pause-chain", "resume-chain"}:
            marker = _load_marker(root, args)
            if not isinstance(marker, dict):
                raise CliError("missing_marker", "No canonical last-chain marker is available")
            workspace = str(marker.get("workspace") or "").strip()
            remote_spec = str(marker.get("remote_spec") or "").strip()
            session = str(marker.get("chain_session") or marker.get("session") or "").strip()
            marker_path = str(marker.get("marker_path") or "").strip()
            if not marker_path and session:
                marker_path = str(PurePosixPath(_CHAIN_SESSION_MARKER_DIR) / f"{session}.json")
            if not all((workspace, remote_spec, session, marker_path)):
                raise CliError("invalid_marker", "Chain marker lacks workspace/spec/session custody")
            argv = [
                "python3", "-P", "-m", "arnold_pipelines.megaplan.cloud.operator_control",
                "pause" if action == "pause-chain" else "resume",
                "--spec", remote_spec, "--workspace", workspace,
                "--session", session, "--marker", marker_path,
                "--actor", str(getattr(args, "actor", None) or "operator"),
            ]
            if action == "pause-chain":
                argv.extend(["--reason", str(args.reason)])
            result = provider.ssh_exec(shlex.join(argv))
            _relay_output(result, secret_names=spec.secrets, env=os.environ)
            return result.returncode

        if action == "down":
            return provider.down()

        if action == "supervise":
            if bool(getattr(args, "chain", False)):
                return _run_supervise_tick(root, args, spec, provider)
            raise CliError(
                "invalid_args",
                "`cloud supervise` requires --chain. Try `arnold cloud supervise --chain`.",
            )

        if action == "destroy":
            if not bool(getattr(args, "yes", False)) and not _confirm_destroy(spec):
                return 1
            result = provider.destroy(volume=spec.resources.volume)
            _clear_persistent_deploy_dir(spec)
            return result

        raise CliError("invalid_args", f"Unknown cloud action: {action}")
    except CliError as exc:
        return _emit_error(exc)


def _cloud_yaml_path(root: Path, args: argparse.Namespace) -> Path:
    raw = getattr(args, "cloud_yaml", None)
    if not raw:
        return root / "cloud.yaml"
    return Path(raw).expanduser().resolve()


def _load_cloud_spec(root: Path, args: argparse.Namespace) -> CloudSpec:
    spec = load_spec(_cloud_yaml_path(root, args))
    return apply_repo_overrides(
        spec,
        repo_url=getattr(args, "repo_url", None),
        repo_branch=getattr(args, "repo_branch", None),
        repo_workspace=getattr(args, "repo_workspace", None),
    )


def _status_should_use_chain(root: Path, args: argparse.Namespace, spec: CloudSpec) -> bool:
    if bool(getattr(args, "chain", False)):
        return True
    if getattr(args, "remote_spec", None):
        return True
    if spec.mode == "chain" and spec.chain is not None:
        return True
    marker_path = _marker_path_no_create(_cloud_yaml_path(root, args)) / "last_chain.json"
    try:
        return marker_path.exists()
    except OSError:
        return False


def _provider_for_action(spec: CloudSpec, args: argparse.Namespace):
    if bool(getattr(args, "on_box", False)):
        action = getattr(args, "cloud_action", None)
        if action not in {"chain", "launch-epic"}:
            raise CliError("invalid_args", "--on-box is supported only for cloud chain and launch-epic")
        from arnold_pipelines.megaplan.cloud.providers.on_box import OnBoxProvider

        return OnBoxProvider(spec)
    # Gate session overrides on provider capability, not on a provider-name special case.
    base_provider = get_provider(spec.provider, spec)
    session_name = getattr(args, "session", None)
    if not session_name:
        return base_provider
    raise CliError("invalid_args", "--session override is not supported by configured providers")


def _ensure_repo_command(spec: CloudSpec) -> str:
    # Clone the primary repo AND every declared `extra_repos` sibling. The
    # container entrypoint clones the full set at boot, but boot only runs once
    # per `cloud deploy`. A `cloud chain` launched against a container that
    # pre-dates an `extra_repos` edit would otherwise silently leave siblings
    # missing on the persistent volume, blocking any milestone that depends on
    # them.
    return render_ensure_repos_block(spec)


def _ensure_repo_checkout(spec: CloudSpec, provider, *, relay: bool = True) -> None:
    result = provider.ssh_exec(_ensure_repo_command(spec))
    if relay:
        _relay_output(result, secret_names=spec.secrets, env=os.environ)
    if result.returncode != 0:
        repos = [spec.repo, *spec.extra_repos]
        targets = ", ".join(f"{r.url}@{r.branch} into {r.workspace}" for r in repos)
        raise CliError(
            "provider_failed",
            f"ensure repo checkout failed for {targets} (exit {result.returncode})",
        )


def _run_init(root: Path, args: argparse.Namespace) -> int:
    target = _cloud_yaml_path(root, args)
    if target.exists() and not bool(getattr(args, "force", False)):
        raise CliError(
            "invalid_args",
            f"cloud spec already exists: {target}. Use --force to overwrite.",
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    template = resources.files("arnold_pipelines.megaplan.cloud.templates").joinpath("cloud.yaml.tmpl")
    target.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    sys.stdout.write(json.dumps({"success": True, "cloud_yaml": str(target)}, indent=2) + "\n")
    return 0


_CLOUD_TARGETS: dict[str, dict[str, Any]] = {
    "hetzner-agentbox": {
        "provider": "ssh",
        "ssh": {
            "host_env": "MEGAPLAN_CLOUD_SSH_HOST",
            "host": "159.69.51.216",
            "user": "root",
            "port": 22,
            "remote_dir": "/opt/megaplan-cloud/deploy",
            "workspace_dir": "/opt/megaplan-cloud/workspace",
            "container": "megaplan-cloud-agent",
        },
    }
}


def _git_stdout(root: Path, args: list[str]) -> str | None:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    value = (proc.stdout or "").strip()
    return value or None


def _normalise_git_url(url: str) -> str:
    if url.startswith("git@github.com:"):
        return "https://github.com/" + url.removeprefix("git@github.com:")
    if url.startswith("ssh://git@github.com/"):
        return "https://github.com/" + url.removeprefix("ssh://git@github.com/")
    return url


def _infer_repo_url(root: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    inferred = _git_stdout(root, ["config", "--get", "remote.origin.url"])
    if not inferred:
        raise CliError(
            "quickstart_missing_repo_url",
            "Could not infer repo URL from git remote origin. Pass --repo-url.",
        )
    return _normalise_git_url(inferred)


def _infer_base_branch(root: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    return _git_stdout(root, ["branch", "--show-current"]) or "main"


def _quickstart_target_ssh(args: argparse.Namespace) -> dict[str, Any]:
    if args.target == "custom" and not args.ssh_host:
        raise CliError("invalid_args", "--target custom requires --ssh-host")
    target = _CLOUD_TARGETS.get(args.target, {})
    ssh = dict(target.get("ssh") or {})
    env_name = ssh.pop("host_env", None)
    host = args.ssh_host or (os.environ.get(env_name) if env_name else None) or ssh.get("host")
    if not host:
        raise CliError("invalid_args", f"target {args.target!r} has no SSH host; pass --ssh-host")
    return {
        "host": host,
        "user": args.ssh_user or ssh.get("user") or "root",
        "port": args.ssh_port or ssh.get("port") or 22,
        "remote_dir": ssh.get("remote_dir") or "/opt/megaplan-cloud/deploy",
        "workspace_dir": ssh.get("workspace_dir") or "/opt/megaplan-cloud/workspace",
        "container": ssh.get("container") or "megaplan-cloud-agent",
    }


def _split_repo_url_branch(raw_url: str, *, default_branch: str) -> tuple[str, str]:
    url = raw_url.strip()
    branch = default_branch
    at_index = url.rfind("@")
    if at_index > 0 and "/" not in url[at_index:]:
        branch = url[at_index + 1 :] or default_branch
        url = url[:at_index]
    return _normalise_git_url(url), branch


def _parse_quickstart_extra_repo(raw: str, *, slug: str, default_branch: str) -> dict[str, str]:
    value = raw.strip()
    if "=" not in value:
        raise CliError(
            "invalid_args",
            "--extra-repo must be formatted as ROLE=URL[@BRANCH[:WORKSPACE]]",
        )
    left, right = value.split("=", 1)
    left = left.strip()
    right = right.strip()
    if not left or not right:
        raise CliError(
            "invalid_args",
            "--extra-repo must include a non-empty role/URL and repo URL/workspace",
        )

    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", left):
        role = _slugify_chain_identity(left)
        url_part = right
        workspace = f"/workspace/{slug}/{role}"
        colon_index = right.rfind(":")
        scheme_index = right.find("://")
        if colon_index > 0 and right[colon_index + 1 :].startswith("/") and colon_index != scheme_index:
            url_part = right[:colon_index]
            workspace = right[colon_index + 1 :]
        url, branch = _split_repo_url_branch(url_part, default_branch=default_branch)
    else:
        url, branch = _split_repo_url_branch(left, default_branch=default_branch)
        workspace = right

    if not PurePosixPath(workspace).is_absolute():
        raise CliError("invalid_args", f"--extra-repo workspace must be absolute: {workspace}")
    return {"url": url, "branch": branch, "workspace": workspace}


def _write_text_once(path: Path, text: str, *, force: bool, written: list[str], reused: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        reused.append(str(path))
        return
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    written.append(str(path))


def _call_cloud_step_quietly(func, *call_args) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            rc = int(func(*call_args) or 0)
    except CliError:
        captured_out = stdout.getvalue()
        captured_err = stderr.getvalue()
        if captured_out:
            sys.stdout.write(captured_out)
        if captured_err:
            sys.stderr.write(captured_err)
        raise
    return rc, stdout.getvalue(), stderr.getvalue()


def _json_from_captured_stdout(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    idx = 0
    last: dict[str, Any] | None = None
    while idx < len(text):
        while idx < len(text) and text[idx].isspace():
            idx += 1
        if idx >= len(text):
            break
        try:
            value, end = decoder.raw_decode(text, idx)
        except json.JSONDecodeError:
            break
        if isinstance(value, dict):
            last = value
        idx = end
    return last


def _run_quickstart(root: Path, args: argparse.Namespace) -> int:
    slug = _slugify_chain_identity(str(args.slug))
    if not slug:
        raise CliError("invalid_args", "--slug must contain at least one alphanumeric character")
    brief_source = Path(args.brief).expanduser().resolve()
    if not brief_source.is_file():
        raise CliError("invalid_args", f"--brief does not exist or is not a file: {brief_source}")
    north_star_source = Path(args.north_star).expanduser().resolve()
    if not north_star_source.is_file():
        raise CliError("invalid_args", f"--north-star does not exist or is not a file: {north_star_source}")

    brief_text = brief_source.read_text(encoding="utf-8")
    north_star_text = north_star_source.read_text(encoding="utf-8")
    title = (args.title or slug.replace("-", " ").title()).strip()
    base_branch = _infer_base_branch(root, args.base_branch)
    repo_url = _infer_repo_url(root, args.repo_url)
    ssh = _quickstart_target_ssh(args)
    initiative = root / ".megaplan" / "initiatives" / slug
    cloud_yaml = Path(args.cloud_yaml).expanduser().resolve() if args.cloud_yaml else initiative / "cloud.yaml"
    chain_path = initiative / "chain.yaml"
    milestone_label = f"m1-{slug}"
    milestone_path = initiative / "briefs" / f"{milestone_label}.md"
    branch = args.branch or slug
    written: list[str] = []
    reused: list[str] = []

    readme = f"# {title}\n\nCloud quickstart initiative generated from `{brief_source}`.\n"
    milestone = "\n".join(
        [
            f"# {args.milestone_title}",
            "",
            "This milestone was generated by `megaplan cloud quickstart` from the source brief below.",
            "",
            "## Source Brief",
            "",
            brief_text.rstrip(),
        ]
    )
    chain_payload = {
        "base_branch": base_branch,
        "anchors": {"north_star": "NORTHSTAR.md"},
        "milestones": [
            {
                "label": milestone_label,
                "idea": f".megaplan/initiatives/{slug}/briefs/{milestone_label}.md",
                "profile": args.profile,
                "vendor": args.vendor,
                "robustness": args.robustness,
                "depth": args.depth,
                "branch": branch,
                "prep_clarify": False,
            }
        ],
        "on_failure": {"abort": "stop_chain"},
        "on_escalate": {"abort": "stop_chain"},
        "merge_policy": "auto",
        "driver": {
            "robustness": args.robustness,
            "auto_approve": True,
            "max_iterations": 24,
            "poll_sleep": 8.0,
        },
    }
    workspace = f"/workspace/{slug}/{_repo_dir_name(repo_url)}"
    extra_repos = [
        _parse_quickstart_extra_repo(raw, slug=slug, default_branch=base_branch)
        for raw in (args.extra_repo or [])
    ]
    cloud_payload: dict[str, Any] = {
        "provider": "ssh",
        "repo": {"url": repo_url, "branch": base_branch, "workspace": workspace},
        "agents": {"default": args.vendor},
        "codex": {"model": "gpt-5.6-sol", "reasoning": args.depth},
        "chain_session": slug,
        "mode": "idle",
        "chain": {"spec": f"{workspace}/.megaplan/initiatives/{slug}/chain.yaml"},
        "megaplan": {
            "ref": args.engine_ref,
            "codex_auth": "chatgpt",
            "repo": "https://github.com/peteromallet/Arnold.git",
            "src_path": "/workspace/arnold",
        },
        "resources": {"volume": "agent-volume", "port": 8080},
        "ssh": ssh,
        "secrets": [],
    }
    if extra_repos:
        cloud_payload["extra_repos"] = extra_repos

    force = bool(args.force)
    _write_text_once(initiative / "README.md", readme, force=force, written=written, reused=reused)
    _write_text_once(initiative / "NORTHSTAR.md", north_star_text, force=force, written=written, reused=reused)
    _write_text_once(milestone_path, milestone, force=force, written=written, reused=reused)
    _write_text_once(chain_path, yaml.safe_dump(chain_payload, sort_keys=False), force=force, written=written, reused=reused)
    _write_text_once(cloud_yaml, yaml.safe_dump(cloud_payload, sort_keys=False), force=force, written=written, reused=reused)

    preflight_args = argparse.Namespace(
        cloud_yaml=str(cloud_yaml),
        spec=str(chain_path),
        skip_remote=bool(args.skip_remote),
        allow_loose_chain_spec=False,
        allow_template_placeholders=False,
        allow_human_gates=False,
        repo_url=None,
        repo_branch=None,
        repo_workspace=None,
    )
    spec = _load_cloud_spec(root, preflight_args)
    provider = _provider_for_action(spec, preflight_args)
    preflight_rc, preflight_stdout, preflight_stderr = _call_cloud_step_quietly(
        _run_preflight,
        root,
        preflight_args,
        spec,
        provider,
    )
    if preflight_rc != 0:
        if preflight_stdout:
            sys.stdout.write(preflight_stdout)
        if preflight_stderr:
            sys.stderr.write(preflight_stderr)
        return preflight_rc
    preflight_payload = _json_from_captured_stdout(preflight_stdout) or {}

    launch_payload: dict[str, Any] | None = None
    if bool(args.launch):
        chain_args = argparse.Namespace(
            cloud_yaml=str(cloud_yaml),
            spec=str(chain_path),
            idea_dir=None,
            fresh=bool(args.fresh),
            no_git_refresh=False,
            no_editable_install_sync=not bool(args.sync_local_engine),
            force_clean_editable_install=False,
            allow_loose_chain_spec=False,
            allow_template_placeholders=False,
            allow_human_gates=False,
            repo_url=None,
            repo_branch=None,
            repo_workspace=None,
            _canonicalized_epic=True,
            _generated_canonical_files=[],
        )
        with _materialized_deploy_dir(spec):
            rc, launch_stdout, launch_stderr = _call_cloud_step_quietly(
                _run_chain_wrapper,
                root,
                chain_args,
                spec,
                provider,
            )
        if rc != 0:
            if launch_stdout:
                sys.stdout.write(launch_stdout)
            if launch_stderr:
                sys.stderr.write(launch_stderr)
            return rc
        launch_provenance = _json_from_captured_stdout(launch_stdout) or {}
        log_payload = launch_provenance.get("log")
        verification = launch_provenance.get("verification")
        launch_payload = {
            "launched": True,
            "session": slug,
            "workspace": workspace,
            "spec": f"{workspace}/.megaplan/initiatives/{slug}/chain.yaml",
            "local_engine_sync": bool(args.sync_local_engine),
            "chain_log": log_payload.get("chain_log") if isinstance(log_payload, dict) else None,
            "verification": verification if isinstance(verification, dict) else None,
        }

    remote_payload = preflight_payload.get("remote") if isinstance(preflight_payload.get("remote"), dict) else {}
    payload = {
        "success": True,
        "event": "cloud_quickstart",
        "initiative": str(initiative),
        "chain": str(chain_path),
        "cloud_yaml": str(cloud_yaml),
        "milestone": str(milestone_path),
        "written": written,
        "reused": reused,
        "preflight": {
            "success": bool(preflight_payload.get("success", True)),
            "expected_workspace": remote_payload.get("expected_workspace", workspace),
            "expected_session": remote_payload.get("expected_session", slug),
            "warnings": preflight_payload.get("warnings", []),
        },
        "launch": launch_payload
        or {
            "launched": False,
            "next": (
                "Rerun with --launch, or run "
                f"python -m arnold_pipelines.megaplan cloud chain {chain_path} "
                f"--cloud-yaml {cloud_yaml} --fresh --no-editable-install-sync"
            ),
        },
    }
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    return 0


def _relative_remote_path(*, workspace: str, remote_path: str) -> Path:
    remote = PurePosixPath(remote_path)
    workspace_path = PurePosixPath(workspace)
    if remote == workspace_path:
        return Path()
    elif str(remote).startswith(f"{workspace_path}/"):
        return Path(*remote.relative_to(workspace_path).parts)
    elif remote.is_absolute():
        return Path(*remote.parts[1:])
    return Path(*remote.parts)


def _append_unique_path(paths: list[Path], candidate: Path) -> None:
    if candidate not in paths:
        paths.append(candidate)


def _local_idea_source_candidates(*, root: Path, idea_dir: Path, workspace: str, remote_path: str) -> list[Path]:
    relative_remote = _relative_remote_path(workspace=workspace, remote_path=remote_path)
    candidates: list[Path] = []
    _append_unique_path(candidates, idea_dir / relative_remote)
    _append_unique_path(candidates, root / relative_remote)

    try:
        idea_dir_tail = idea_dir.relative_to(root)
    except ValueError:
        idea_dir_tail = None
    if idea_dir_tail is not None:
        try:
            deduped_tail = relative_remote.relative_to(idea_dir_tail)
        except ValueError:
            deduped_tail = None
        if deduped_tail is not None:
            _append_unique_path(candidates, idea_dir / deduped_tail)

    remote = PurePosixPath(remote_path)
    if remote.is_absolute() and not str(remote).startswith(f"{PurePosixPath(workspace)}/"):
        _append_unique_path(candidates, idea_dir / remote.name)
    return candidates


def _resolve_local_idea_source(*, root: Path, idea_dir: Path, workspace: str, remote_path: str) -> tuple[Path | None, list[Path]]:
    candidates = _local_idea_source_candidates(root=root, idea_dir=idea_dir, workspace=workspace, remote_path=remote_path)
    for candidate in candidates:
        if candidate.exists():
            return candidate, candidates
    return None, candidates


def _read_chain_yaml(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _chain_spec_has_explicit_base_branch(path: Path) -> bool:
    return "base_branch" in _read_chain_yaml(path)


def _rewrite_remote_workspace_path(remote_path: str, *, source_workspace: str, target_workspace: str) -> str:
    source = PurePosixPath(source_workspace)
    target = PurePosixPath(target_workspace)
    path = PurePosixPath(remote_path)
    if path == source:
        return str(target)
    if path.is_absolute() and str(path).startswith(f"{source}/"):
        return str(target / path.relative_to(source))
    return remote_path


def _remote_chain_upload_path(remote_path: str, *, source_workspace: str, target_workspace: str) -> str:
    rewritten = _rewrite_remote_workspace_path(
        remote_path,
        source_workspace=source_workspace,
        target_workspace=target_workspace,
    )
    path = PurePosixPath(rewritten)
    if path.is_absolute():
        return str(path)
    return str(PurePosixPath(target_workspace) / path)


def _remote_chain_anchor_upload_path(anchor_path: str, *, remote_spec_path: str) -> str:
    path = PurePosixPath(anchor_path)
    if path.is_absolute():
        return str(path)
    return str(PurePosixPath(remote_spec_path).parent / path)


def _append_unique_upload(uploads: list[tuple[Path, str]], local_source: Path, remote_path: str) -> None:
    item = (local_source, remote_path)
    if item not in uploads:
        uploads.append(item)


def _chain_anchor_uploads(local_spec_path: Path, remote_spec_path: str, chain_spec: Any) -> list[tuple[Path, str]]:
    from arnold_pipelines.megaplan.anchors import resolve_anchor_path

    uploads: list[tuple[Path, str]] = []
    top_anchor = getattr(getattr(chain_spec, "anchors", None), "north_star", None)
    if isinstance(top_anchor, str) and top_anchor:
        _append_unique_upload(
            uploads,
            resolve_anchor_path(local_spec_path, top_anchor),
            _remote_chain_anchor_upload_path(top_anchor, remote_spec_path=remote_spec_path),
        )
    for milestone in getattr(chain_spec, "milestones", []):
        milestone_anchor = getattr(getattr(milestone, "anchors", None), "north_star", None)
        if isinstance(milestone_anchor, str) and milestone_anchor:
            _append_unique_upload(
                uploads,
                resolve_anchor_path(local_spec_path, milestone_anchor),
                _remote_chain_anchor_upload_path(milestone_anchor, remote_spec_path=remote_spec_path),
            )
    return uploads


def _git_repo_root(path: Path) -> Path | None:
    """Best-effort git toplevel for the repo containing ``path``."""
    import subprocess
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(path.parent if path.is_file() else path),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    if proc.returncode != 0:
        return None
    top = proc.stdout.strip()
    return Path(top).resolve() if top else None


def _chain_project_root(local_spec_path: Path, fallback_root: Path) -> Path:
    """Return the app/project root that owns a local chain spec.

    Cloud commands are often invoked through an Arnold checkout while the chain
    spec lives in a different application repository.  Chain idea paths are
    project-relative, so validation and upload source resolution must use the
    spec's repository root, not the caller's current working directory.
    """
    return _git_repo_root(local_spec_path) or fallback_root.expanduser().resolve()


def _validate_chain_spec_location(
    local_spec_path: Path,
    project_root: Path,
    *,
    allow_loose: bool = False,
) -> None:
    """Require durable chain specs to live under .megaplan/initiatives/<initiative>/.

    Cloud launches upload the spec and its idea files into a long-lived remote
    checkout. Keeping the local source in the durable initiatives tree is what
    makes the remote copy auditable instead of another loose cloud-only artifact.
    """
    if allow_loose:
        return
    try:
        relative = local_spec_path.expanduser().resolve().relative_to(
            project_root.expanduser().resolve()
        )
    except ValueError as exc:
        raise CliError(
            "chain_spec_outside_project",
            (
                f"chain spec {local_spec_path} is outside project root {project_root}. "
                "Move it under .megaplan/initiatives/<initiative>/chain.yaml or pass "
                "--allow-loose-chain-spec for a temporary compatibility launch."
            ),
        ) from exc
    if is_canonical_chain_spec(local_spec_path, project_root):
        return
    raise CliError(
        "chain_spec_layout_violation",
        (
            "cloud chain specs must live at "
            ".megaplan/initiatives/<initiative>/chain.yaml; got "
            f"{relative.as_posix()}. Move the chain and milestone briefs into "
            "that durable initiative folder or pass --allow-loose-chain-spec "
            "for a temporary compatibility launch."
        ),
        extra={"chain_spec": relative.as_posix()},
    )


def _arnold_engine_repo_root() -> Path:
    """Return the Arnold checkout whose code is currently launching cloud."""
    return _git_repo_root(Path(__file__)) or Path(__file__).resolve().parents[3]


def _remote_chain_workspace_path(local_path: Path, *, local_root: Path, target_workspace: str) -> str:
    path = local_path.expanduser().resolve()
    root = local_root.expanduser().resolve()
    relative: PurePosixPath | None = None
    try:
        relative = PurePosixPath(path.relative_to(root))
    except ValueError:
        relative = None
    # local_root isn't always the spec's repo root (it can be a cloud cache dir
    # or a project dir that doesn't contain the spec). Fall back to the spec's
    # OWN git repo root so the spec lands at its repo-relative path on the box —
    # this keeps the chain spec, its north_star anchor, and idea files at the
    # same relative paths, so chain.yaml-dir-relative anchor resolution works
    # identically locally and remotely. Bare path.name is the last resort.
    if relative is None:
        git_root = _git_repo_root(path)
        if git_root is not None:
            try:
                relative = PurePosixPath(path.relative_to(git_root))
            except ValueError:
                relative = None
    if relative is None:
        return str(PurePosixPath(target_workspace) / path.name)
    return str(PurePosixPath(target_workspace).joinpath(*relative.parts))


def _normalized_chain_upload_spec(
    local_spec_path: Path,
    *,
    base_branch: str,
    source_workspace: str | None = None,
    target_workspace: str | None = None,
    driver_overrides: dict[str, Any] | None = None,
    phase_model_by_label: dict[str, list[str]] | None = None,
) -> Path:
    raw = _read_chain_yaml(local_spec_path)
    workspace_changed = (
        bool(source_workspace)
        and bool(target_workspace)
        and source_workspace != target_workspace
    )
    if (
        "base_branch" in raw
        and not workspace_changed
        and not driver_overrides
        and not phase_model_by_label
    ):
        return local_spec_path
    normalized = dict(raw)
    if "base_branch" not in normalized:
        normalized["base_branch"] = base_branch
    if driver_overrides:
        driver = normalized.get("driver")
        driver_mapping = dict(driver) if isinstance(driver, dict) else {}
        driver_mapping.update(driver_overrides)
        normalized["driver"] = driver_mapping
    if (workspace_changed or phase_model_by_label) and isinstance(normalized.get("milestones"), list):
        rewritten: list[Any] = []
        for item in normalized["milestones"]:
            if isinstance(item, dict):
                copied = dict(item)
                if workspace_changed and isinstance(copied.get("idea"), str):
                    copied["idea"] = _rewrite_remote_workspace_path(
                        copied["idea"],
                        source_workspace=source_workspace or "",
                        target_workspace=target_workspace or "",
                    )
                if phase_model_by_label and isinstance(copied.get("label"), str):
                    phase_models = phase_model_by_label.get(copied["label"])
                    if phase_models:
                        copied["phase_model"] = list(phase_models)
                rewritten.append(copied)
            else:
                rewritten.append(item)
        normalized["milestones"] = rewritten
    with NamedTemporaryFile("w", suffix=".yaml", encoding="utf-8", delete=False) as handle:
        yaml.safe_dump(normalized, handle, sort_keys=False)
        return Path(handle.name)


def _missing_configured_secrets(spec: CloudSpec, env: dict[str, str]) -> list[str]:
    return sorted(name for name in spec.secrets if not env.get(name))


def _remote_dependency_check_command(commands: list[str]) -> str:
    quoted_commands = " ".join(shlex.quote(command) for command in commands)
    return (
        "missing=''; "
        f"for cmd in {quoted_commands}; do "
        'if ! command -v "$cmd" >/dev/null 2>&1; then missing="$missing $cmd"; fi; '
        "done; "
        'printf "%s\\n" "$missing"'
    )


def _run_remote_dependency_check(provider, commands: list[str]) -> list[str]:
    if not commands:
        return []
    result = provider.ssh_exec(_remote_dependency_check_command(commands))
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "remote dependency check failed").strip()
        raise CliError("provider_failed", message)
    return sorted({part for part in result.stdout.split() if part})


def _remote_megaplan_import_check_command() -> str:
    script = """
import importlib.util, json

def present(name):
    try:
        return importlib.util.find_spec(name) is not None
    except Exception as exc:
        return {"error": str(exc)}

checks = {
    "arnold_pipelines.megaplan": present("arnold_pipelines.megaplan"),
    "arnold_pipelines.megaplan.cli": present("arnold_pipelines.megaplan.cli"),
    "arnold.pipelines.megaplan": present("arnold.pipelines.megaplan"),
}
errors = []
if checks["arnold_pipelines.megaplan"] is not True:
    errors.append("missing modern arnold_pipelines.megaplan import")
if checks["arnold_pipelines.megaplan.cli"] is not True:
    errors.append("missing modern arnold_pipelines.megaplan.cli import")
print(json.dumps({"checks": checks, "errors": errors}, sort_keys=True))
raise SystemExit(1 if errors else 0)
"""
    return f"python3 - <<'MEGAPLAN_IMPORT_CHECK'\n{script.strip()}\nMEGAPLAN_IMPORT_CHECK"


def _run_remote_megaplan_import_check(provider) -> dict[str, Any]:
    result = provider.ssh_exec(_remote_megaplan_import_check_command())
    raw = (result.stdout or "").strip().splitlines()
    try:
        payload = json.loads(raw[-1] if raw else "{}")
    except json.JSONDecodeError as exc:
        payload = {
            "checks": {},
            "errors": [f"import check output was not JSON: {exc}"],
            "raw": result.stdout,
        }
    if result.returncode != 0:
        payload.setdefault("errors", [])
        if result.stderr:
            payload["errors"].append(result.stderr.strip())
    payload["status"] = "ok" if not payload.get("errors") else "failed"
    return payload


def _cloud_profile_warnings(preflight_summary: Mapping[str, Any], spec: CloudSpec) -> list[str]:
    warnings: list[str] = []
    required_agents = {
        str(agent)
        for agent in preflight_summary.get("required_agents", [])
        if isinstance(agent, str)
    }
    configured_secrets = set(spec.secrets)
    if "claude" in required_agents or "shannon" in required_agents:
        if "ANTHROPIC_API_KEY" not in configured_secrets:
            warnings.append(
                "resolved chain routing includes Claude/Shannon phases. "
                "Codex-only cloud workers should use profile all-codex or explicit codex phase_model pins; "
                "mixed profiles need Claude CLI/auth and ANTHROPIC_API_KEY available on the worker."
            )
    if required_agents == {"codex"}:
        warnings.append("resolved chain routing is Codex-only; this is compatible with all-codex-style cloud workers.")
    return warnings


def _phase_model_by_label_from_preflight(preflight_summary: Mapping[str, Any]) -> dict[str, list[str]]:
    """Return phase pins that must be materialized in the uploaded chain spec.

    Cloud chain launch may resolve routing from cloud-only defaults such as
    ``agents.default``. The remote ``chain start`` process only sees the
    uploaded chain YAML, so the resolved routing must be materialized into that
    temporary upload spec or init can fall back to a different local default.

    Do not materialize resolved profile routes for profiled milestones. Profiles
    can carry ``tier_models.execute``/``tier_models.critique`` tables; flattening
    their resolved phase map into ``phase_model`` erases adaptive per-batch
    routing and pins execute to one model.
    """
    phase_model_by_label: dict[str, list[str]] = {}
    for milestone in preflight_summary.get("milestones", []):
        if not isinstance(milestone, Mapping):
            continue
        label = milestone.get("label")
        profile = milestone.get("profile")
        explicit = milestone.get("explicit_phase_model")
        resolved_phase_chains = milestone.get("resolved_phase_chains")
        if isinstance(profile, str) and profile:
            if (
                isinstance(label, str)
                and isinstance(explicit, list)
                and all(isinstance(item, str) for item in explicit)
                and explicit
            ):
                phase_model_by_label[label] = list(explicit)
            continue
        resolved = milestone.get("resolved_phase_map")
        if not isinstance(label, str):
            continue
        phase_models: list[str] = []
        explicit_steps: set[str] = set()
        if isinstance(explicit, list) and all(isinstance(item, str) for item in explicit):
            for entry in explicit:
                if "=" not in entry:
                    continue
                phase, _chain = decode_phase_model_value(entry)
                explicit_steps.add(phase)
                phase_models.append(entry)
        if isinstance(resolved_phase_chains, Mapping):
            for phase, specs in resolved_phase_chains.items():
                if not isinstance(phase, str) or phase in explicit_steps:
                    continue
                if not isinstance(specs, list) or not all(isinstance(item, str) for item in specs) or not specs:
                    continue
                phase_models.append(encode_phase_model_value(phase, specs))
        elif isinstance(resolved, Mapping):
            for phase, spec in resolved.items():
                if isinstance(phase, str) and isinstance(spec, str) and phase and spec and phase not in explicit_steps:
                    phase_models.append(f"{phase}={spec}")
        if phase_models:
            phase_model_by_label[label] = phase_models
    return phase_model_by_label


def _remote_repo_head(provider, workspace: str) -> dict[str, str | None]:
    command = (
        f"git -C {shlex.quote(workspace)} rev-parse --abbrev-ref HEAD 2>/dev/null && "
        f"git -C {shlex.quote(workspace)} rev-parse HEAD 2>/dev/null"
    )
    result = provider.ssh_exec(command)
    if result.returncode != 0:
        return {"branch": None, "head": None}
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return {
        "branch": lines[0] if len(lines) >= 1 else None,
        "head": lines[1] if len(lines) >= 2 else None,
    }


def _remote_chain_sessions(provider) -> list[dict[str, Any]]:
    result = provider.ssh_exec(_cloud_chains_command())
    if result.returncode != 0:
        return []
    try:
        payload = json.loads((result.stdout or "").strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        return []
    sessions = payload.get("sessions") if isinstance(payload, dict) else None
    return [item for item in sessions if isinstance(item, dict)] if isinstance(sessions, list) else []


def _chain_state_for_remote_spec(provider, remote_spec: str):
    from arnold_pipelines.megaplan import chain as chain_module

    state_path = chain_module._state_path_for(Path(remote_spec))
    return chain_module.ChainState.from_dict(json.loads(provider.read_remote_file(str(state_path))))


def _workspace_from_chain_marker(
    spec: CloudSpec,
    marker: Mapping[str, Any],
    provider,
    *,
    plan: str | None,
) -> str | None:
    remote_spec = marker.get("remote_spec")
    workspace = marker.get("workspace")
    if not isinstance(remote_spec, str) or not remote_spec:
        return workspace if isinstance(workspace, str) and workspace.strip() else None
    try:
        chain_state = _chain_state_for_remote_spec(provider, remote_spec)
    except Exception:
        return workspace if isinstance(workspace, str) and workspace.strip() else None
    if plan and chain_state.current_plan_name != plan:
        return None
    ctx = _resolve_chain_execution_context(spec, chain_state, dict(marker), remote_spec)
    resolved = ctx.get("workspace")
    return resolved if isinstance(resolved, str) and resolved.strip() else None


def _resolve_resume_workspace(root: Path, args: argparse.Namespace, spec: CloudSpec, provider) -> str:
    """Resolve the workspace for ``cloud resume``.

    Chain launches can derive a per-chain workspace even when cloud.yaml keeps
    the default ``repo.workspace``. Prefer the local last-chain marker, then
    remote chain session markers, and fall back to the static spec workspace.
    """
    plan = getattr(args, "plan", None)
    marker = _load_marker(root, args)
    if marker:
        workspace = _workspace_from_chain_marker(spec, marker, provider, plan=plan)
        if workspace:
            return workspace

    if plan:
        for session in _remote_chain_sessions(provider):
            workspace = _workspace_from_chain_marker(spec, session, provider, plan=plan)
            if workspace:
                return workspace

    return spec.repo.workspace


def _git_run(
    root: Path,
    args: list[str],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    if check and proc.returncode != 0:
        raise CliError(
            "editable_install_sync_failed",
            f"git {' '.join(args)} failed: {(proc.stderr or proc.stdout or '').strip()}",
            extra={
                "command": ["git", *args],
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            },
        )
    return proc


def _git_relative_path(root: Path, path: Path) -> str | None:
    try:
        return path.expanduser().resolve().relative_to(root.expanduser().resolve()).as_posix()
    except ValueError:
        return None


def _porcelain_path(line: str) -> str:
    path = line[3:] if len(line) > 3 else ""
    if " -> " in path:
        path = path.rsplit(" -> ", 1)[-1]
    return path.strip()


def _sync_launch_head_to_editable_install_branch(
    root: Path,
    *,
    branch: str = "editible-install",
    remote: str = "origin",
    ignore_dirty_paths: list[Path] | None = None,
) -> dict[str, Any]:
    """Publish the local launch HEAD to the cloud editable-install branch.

    The cloud worker refreshes `/workspace/arnold` from `editible-install`.
    Before launching any new cloud chain, publish the code currently being used
    to launch the run into that branch as well. If the editable branch has
    unique commits that are not already contained by the launch HEAD, refuse to
    sync so the divergent code can be reconciled deliberately first.
    """
    root = root.expanduser().resolve()
    inside = _git_run(root, ["rev-parse", "--is-inside-work-tree"])
    if inside.stdout.strip() != "true":
        raise CliError(
            "editable_install_sync_failed",
            f"cloud chain must be launched from a git worktree to sync {branch}",
        )
    ignored = {
        relative
        for path in (ignore_dirty_paths or [])
        if (relative := _git_relative_path(root, path)) is not None
    }
    dirty_lines = [
        line
        for line in _git_run(root, ["status", "--porcelain", "--untracked-files=all"]).stdout.splitlines()
        if _porcelain_path(line) not in ignored
    ]
    if dirty_lines:
        raise CliError(
            "editable_install_sync_dirty",
            (
                f"Cannot sync cloud editable install branch {branch!r}: "
                "the launch checkout has uncommitted changes. Commit or stash them, "
                "or pass --no-editable-install-sync."
            ),
            extra={"dirty": dirty_lines},
        )

    launch_head = _git_run(root, ["rev-parse", "HEAD"]).stdout.strip()
    launch_branch = _git_run(root, ["branch", "--show-current"], check=False).stdout.strip() or None
    _git_run(root, ["fetch", remote, branch], check=False)
    remote_ref = f"{remote}/{branch}"
    remote_exists = _git_run(root, ["rev-parse", "--verify", remote_ref], check=False).returncode == 0
    if remote_exists:
        remote_head = _git_run(root, ["rev-parse", remote_ref]).stdout.strip()
        contains_launch = _git_run(
            root,
            ["merge-base", "--is-ancestor", launch_head, remote_ref],
            check=False,
        ).returncode == 0
        if contains_launch:
            return {
                "status": "already_contains",
                "branch": branch,
                "remote": remote,
                "launch_head": launch_head,
                "launch_branch": launch_branch,
                "editable_head": remote_head,
            }
        launch_contains_remote = _git_run(
            root,
            ["merge-base", "--is-ancestor", remote_ref, launch_head],
            check=False,
        ).returncode == 0
        if not launch_contains_remote:
            counts = _git_run(
                root,
                ["rev-list", "--left-right", "--count", f"{launch_head}...{remote_ref}"],
                check=False,
            ).stdout.strip().split()
            launch_only = int(counts[0]) if len(counts) == 2 else None
            editable_only = int(counts[1]) if len(counts) == 2 else None
            editable_commits = _git_run(
                root,
                ["log", "--oneline", "--max-count=5", f"{launch_head}..{remote_ref}"],
                check=False,
            ).stdout.strip().splitlines()
            raise CliError(
                "editable_install_sync_diverged",
                (
                    f"Refusing to sync {branch!r}: {remote_ref} has commits that "
                    "are not contained in the launch HEAD. Merge or cherry-pick "
                    "the editable-install work first, then retry the cloud sync."
                ),
                extra={
                    "branch": branch,
                    "remote": remote,
                    "launch_head": launch_head,
                    "launch_branch": launch_branch,
                    "editable_head": remote_head,
                    "launch_only_commits": launch_only,
                    "editable_only_commits": editable_only,
                    "editable_only_sample": editable_commits,
                },
            )
    else:
        remote_head = None

    with TemporaryDirectory(prefix="editable-install-sync-") as tmp:
        worktree = Path(tmp) / "worktree"
        if remote_exists:
            _git_run(root, ["worktree", "add", "--detach", str(worktree), launch_head])
            _git_run(worktree, ["checkout", "-B", branch])
            before = remote_head
            merged = False
        else:
            _git_run(root, ["worktree", "add", "--detach", str(worktree), launch_head])
            _git_run(worktree, ["checkout", "-B", branch])
            before = None
            merged = False

        after = _git_run(worktree, ["rev-parse", "HEAD"]).stdout.strip()
        push = _git_run(
            worktree,
            ["push", "--no-verify", remote, f"HEAD:{branch}"],
            check=False,
        )
        if push.returncode != 0:
            raise CliError(
                "editable_install_sync_failed",
                f"Could not push {branch}: {(push.stderr or push.stdout or '').strip()}",
                extra={
                    "branch": branch,
                    "launch_head": launch_head,
                    "stdout": push.stdout,
                    "stderr": push.stderr,
                },
            )

    _git_run(root, ["worktree", "prune"], check=False)
    return {
        "status": "pushed",
        "branch": branch,
        "remote": remote,
        "launch_head": launch_head,
        "launch_branch": launch_branch,
        "editable_head_before": before,
        "editable_head": after,
        "merge_commit_created": merged,
    }


def _tmux_launch_status(result, *, session_name: str = "megaplan-chain") -> str:
    output = f"{getattr(result, 'stdout', '')}\n{getattr(result, 'stderr', '')}"
    if "already running" in output:
        return "already_running"
    if f"started {session_name} session" in output:
        return "started"
    return "unknown"


def _resolved_phase_map_summary(preflight_summary: dict[str, Any]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for milestone in preflight_summary.get("milestones", []):
        if not isinstance(milestone, dict):
            continue
        summaries.append(
            {
                "label": milestone.get("label"),
                "profile": milestone.get("profile"),
                "explicit_phase_model": milestone.get("explicit_phase_model", []),
                "resolved_phase_map": milestone.get("resolved_phase_map", {}),
                "required_agents": milestone.get("required_agents", []),
                "runtime_commands": milestone.get("runtime_commands", []),
                "env_hints": milestone.get("env_hints", []),
                "provider_requirements": milestone.get("provider_requirements", []),
            }
        )
    return summaries


def _cloud_chain_launch_provenance(
    *,
    spec: CloudSpec,
    ctx: ChainLaunchContext,
    chain_spec,
    preflight_summary: dict[str, Any],
    uploaded_idea_count: int,
    repo_head: dict[str, str | None],
    tmux_result,
    editable_install_sync: dict[str, Any] | None = None,
    verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current_milestone = chain_spec.milestones[0].label if chain_spec.milestones else None
    payload = {
        "success": True,
        "event": "cloud_chain_launched",
        "remote_spec": ctx.remote_spec_path,
        "current_milestone": current_milestone,
        "plan_name": None,
        "pr_number": None,
        "repo": {
            "url": spec.repo.url,
            "branch": spec.repo.branch,
            "workspace": ctx.workspace,
            "head": repo_head.get("head"),
            "checked_out_branch": repo_head.get("branch"),
        },
        "chain": {
            "base_branch": chain_spec.base_branch,
            "milestone_count": len(chain_spec.milestones),
            "resolved_phase_map_summary": _resolved_phase_map_summary(preflight_summary),
            "prerequisite_policy": chain_spec.prerequisite_policy,
            "validation_policy": chain_spec.validation_policy,
            "review_policy": dict(chain_spec.review_policy or {}),
        },
        "megaplan": {
            "ref": spec.megaplan.ref,
            "install_source": "cloud_image_runtime",
            "editable_install_sync": editable_install_sync or {"status": "skipped"},
        },
        "uploaded_idea_count": uploaded_idea_count,
        "tmux": {
            "session": ctx.session_name,
            "status": _tmux_launch_status(tmux_result, session_name=ctx.session_name),
        },
        "log": {"chain_log": ctx.log_path},
        "launch": {
            "identity_digest": ctx.digest,
            "session_marker": ctx.marker_path,
            "derived_workspace": not spec.repo.workspace_explicit,
            "derived_session": not spec.chain_session_explicit,
        },
        "verification": verification or {},
    }
    from arnold_pipelines.megaplan.resident.provenance import safe_provenance_projection

    resident_delegation = safe_provenance_projection()
    if resident_delegation is not None:
        payload["resident_delegation"] = resident_delegation
    return payload


# ---------------------------------------------------------------------------
# Shared chain command helper — canonical session / log / env / quoting
# ---------------------------------------------------------------------------

CHAIN_SESSION_NAME = "megaplan-chain"
_CHAIN_LOG_RELATIVE = ".megaplan/cloud-chain.log"
_CLOUD_HOT_ENV_PATH = "/workspace/.cloud-hot-env"
_CHAIN_SESSION_MARKER_DIR = "/workspace/.megaplan/cloud-sessions"
_CHAIN_VERIFY_ATTEMPTS = 6
_CHAIN_VERIFY_SLEEP_SECONDS = 5
_EDITABLE_INSTALL_BRANCH = "editible-install"


@dataclass(frozen=True)
class ChainLaunchContext:
    identity: str
    slug: str
    digest: str
    workspace: str
    remote_spec_path: str
    session_name: str
    log_relative: str
    log_path: str
    state_path: str
    marker_path: str


def _slugify_chain_identity(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip().lower()).strip(".-")
    return slug[:48] or "chain"


def _repo_dir_name(repo_url: str) -> str:
    tail = repo_url.rstrip("/").rsplit("/", 1)[-1] or "app"
    if tail.endswith(".git"):
        tail = tail[:-4]
    return _slugify_chain_identity(tail) or "app"


def _epic_slug_for_spec_path(local_spec_path: Path) -> str:
    if local_spec_path.name == "chain.yaml" and local_spec_path.parent.name:
        return _slugify_chain_identity(local_spec_path.parent.name)
    return _slugify_chain_identity(local_spec_path.stem)


def _chain_identity_for(local_spec_path: Path, chain_spec: Any) -> tuple[str, str, str]:
    labels = ",".join(m.label for m in getattr(chain_spec, "milestones", []) if getattr(m, "label", None))
    seed = getattr(chain_spec, "seed_plan", None) or ""
    slug = _epic_slug_for_spec_path(local_spec_path)
    identity = f"{slug}:{seed}:{labels}"
    digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:10]
    return identity, slug, digest


@dataclass(frozen=True)
class CanonicalEpicMaterialization:
    spec_path: Path
    project_root: Path
    slug: str
    brief_dir: Path
    copied_files: list[str]
    created_files: list[str]
    generated_chain: bool


def _copy_if_different(src: Path, dest: Path) -> bool:
    src = src.expanduser().resolve()
    dest = dest.expanduser().resolve()
    if src == dest:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return True


def _resolve_chain_local_artifact(
    raw_path: str,
    *,
    project_root: Path,
    spec_dir: Path,
) -> Path:
    path = Path(raw_path).expanduser()
    candidates = [path] if path.is_absolute() else [project_root / path, spec_dir / path]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    tried = "\n".join(f"- {candidate}" for candidate in candidates)
    raise CliError(
        "missing_epic_artifact",
        f"required chain artifact not found: {raw_path}\nTried:\n{tried}",
        extra={"missing_artifact": raw_path, "tried_paths": [str(candidate) for candidate in candidates]},
    )


def _milestone_label_from_brief(path: Path) -> str:
    return _slugify_chain_identity(path.stem)


def _brief_markdown_files(directory: Path) -> list[Path]:
    excluded = {"northstar.md", "north_star.md", "readme.md", "goal.md"}
    files = [
        path
        for path in directory.glob("*.md")
        if path.name.lower() not in excluded and path.is_file()
    ]
    return sorted(files, key=lambda item: item.name)


def _default_generated_chain_yaml(
    *,
    slug: str,
    base_branch: str,
    brief_names: list[str],
) -> dict[str, Any]:
    return {
        "base_branch": base_branch,
        "anchors": {"north_star": "NORTHSTAR.md"},
        "milestones": [
            {
                "label": _milestone_label_from_brief(Path(name)),
                "idea": f".megaplan/initiatives/{slug}/briefs/{name}",
                "branch": f"epic/{slug}/{_milestone_label_from_brief(Path(name))}",
                "vendor": "codex",
                "depth": "high",
                "robustness": "full",
                "with_prep": True,
            }
            for name in brief_names
        ],
        "on_failure": {"abort": "stop_chain"},
        "on_escalate": {"abort": "stop_chain"},
        "merge_policy": "auto",
        "driver": {
            "robustness": "full",
            "auto_approve": True,
            "max_iterations": 80,
            "poll_sleep": 8.0,
        },
    }


def _materialize_canonical_epic_input(
    *,
    root: Path,
    spec: CloudSpec,
    spec_or_dir: str,
    slug_override: str | None = None,
) -> CanonicalEpicMaterialization:
    source = Path(spec_or_dir).expanduser().resolve()
    if not source.exists():
        raise CliError("missing_epic_artifact", f"epic input not found: {source}")

    source_dir = source if source.is_dir() else source.parent
    source_spec = source if source.is_file() else source_dir / "chain.yaml"
    slug_source = slug_override or (source_dir.name if source_spec.name == "chain.yaml" else source_spec.stem)
    slug = _slugify_chain_identity(slug_source)
    if not slug:
        raise CliError("invalid_epic_slug", f"unable to derive epic slug from {source}")

    project_root = _chain_project_root(source_spec if source_spec.exists() else source_dir, root)
    canonical_dir = project_root / ".megaplan" / "initiatives" / slug
    canonical_brief_dir = canonical_dir / "briefs"
    canonical_dir.mkdir(parents=True, exist_ok=True)
    canonical_brief_dir.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    created: list[str] = []
    generated_chain = False

    if source_spec.exists():
        raw = _read_chain_yaml(source_spec)
        anchors = raw.get("anchors")
        if not isinstance(anchors, dict) or not isinstance(anchors.get("north_star"), str) or not anchors["north_star"].strip():
            raise CliError(
                "missing_north_star",
                "chain.yaml must declare anchors.north_star: NORTHSTAR.md for cloud launch",
                extra={"spec": str(source_spec)},
            )
        north_source = _resolve_chain_local_artifact(
            anchors["north_star"],
            project_root=project_root,
            spec_dir=source_spec.parent,
        )
        if north_source.name != "NORTHSTAR.md":
            north_dest = canonical_dir / "NORTHSTAR.md"
        else:
            north_dest = canonical_dir / north_source.name
        north_existed = north_dest.exists()
        if _copy_if_different(north_source, north_dest):
            copied.append(str(north_dest))
            if not north_existed:
                created.append(str(north_dest))
        raw = dict(raw)
        raw["anchors"] = {"north_star": "NORTHSTAR.md"}
        milestones = raw.get("milestones")
        if not isinstance(milestones, list) or not milestones:
            raise CliError("missing_epic_artifact", "chain.yaml must contain at least one milestone")
        rewritten: list[Any] = []
        seen_dest_names: set[str] = set()
        for idx, item in enumerate(milestones):
            if not isinstance(item, dict):
                raise CliError("invalid_spec", f"milestones[{idx}] must be a mapping")
            idea = item.get("idea")
            if not isinstance(idea, str) or not idea.strip():
                raise CliError("invalid_spec", f"milestones[{idx}].idea is required")
            idea_source = _resolve_chain_local_artifact(
                idea,
                project_root=project_root,
                spec_dir=source_spec.parent,
            )
            dest_name = idea_source.name
            if dest_name in seen_dest_names:
                dest_name = f"{idx + 1:02d}-{dest_name}"
            seen_dest_names.add(dest_name)
            idea_dest = canonical_brief_dir / dest_name
            idea_existed = idea_dest.exists()
            if _copy_if_different(idea_source, idea_dest):
                copied.append(str(idea_dest))
                if not idea_existed:
                    created.append(str(idea_dest))
            copied_item = dict(item)
            copied_item["idea"] = f".megaplan/initiatives/{slug}/briefs/{dest_name}"
            rewritten.append(copied_item)
        raw["milestones"] = rewritten
    else:
        north_source = source_dir / "NORTHSTAR.md"
        if not north_source.is_file():
            raise CliError(
                "missing_north_star",
                f"epic directory must contain NORTHSTAR.md before launch: {source_dir}",
                extra={"missing_artifact": str(north_source)},
            )
        north_dest = canonical_dir / "NORTHSTAR.md"
        north_existed = north_dest.exists()
        if _copy_if_different(north_source, north_dest):
            copied.append(str(north_dest))
            if not north_existed:
                created.append(str(north_dest))
        briefs = _brief_markdown_files(source_dir)
        if not briefs:
            raise CliError(
                "missing_epic_artifact",
                f"epic directory has no milestone markdown briefs: {source_dir}",
            )
        brief_names: list[str] = []
        for brief in briefs:
            dest = canonical_brief_dir / brief.name
            dest_existed = dest.exists()
            if _copy_if_different(brief, dest):
                copied.append(str(dest))
                if not dest_existed:
                    created.append(str(dest))
            brief_names.append(brief.name)
        raw = _default_generated_chain_yaml(
            slug=slug,
            base_branch=spec.repo.branch,
            brief_names=brief_names,
        )
        generated_chain = True

    canonical_spec = canonical_dir / "chain.yaml"
    canonical_spec_existed = canonical_spec.exists()
    canonical_spec.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    copied.append(str(canonical_spec))
    if not canonical_spec_existed:
        created.append(str(canonical_spec))

    # Validate after materialization so the exact files being uploaded are the
    # files accepted by the chain runner and watchdog contract.
    chain_spec = _read_chain_yaml(canonical_spec)
    if not isinstance(chain_spec.get("anchors"), dict) or chain_spec["anchors"].get("north_star") != "NORTHSTAR.md":
        raise CliError("missing_north_star", "canonical chain.yaml must declare anchors.north_star: NORTHSTAR.md")
    from arnold_pipelines.megaplan import chain as chain_module

    loaded = chain_module.load_spec(canonical_spec)
    chain_module.chain_spec.validate_anchor_requirement(loaded, canonical_spec)
    chain_module.chain_spec.validate_paths(loaded, project_root, spec_path=canonical_spec)

    return CanonicalEpicMaterialization(
        spec_path=canonical_spec,
        project_root=project_root,
        slug=slug,
        brief_dir=canonical_dir,
        copied_files=copied,
        created_files=created,
        generated_chain=generated_chain,
    )


def _derive_chain_launch_context(
    *,
    root: Path,
    spec: CloudSpec,
    local_spec_path: Path,
    chain_spec: Any,
) -> ChainLaunchContext:
    from arnold_pipelines.megaplan import chain as chain_module

    identity, slug, digest = _chain_identity_for(local_spec_path, chain_spec)
    session_name = (
        spec.chain_session
        if spec.chain_session_explicit
        else f"{CHAIN_SESSION_NAME}-{slug}-{digest[:8]}"
    )
    workspace = (
        spec.repo.workspace
        if spec.repo.workspace_explicit
        else f"/workspace/{slug}-{digest[:8]}/{_repo_dir_name(spec.repo.url)}"
    )
    remote_spec_path = _remote_chain_workspace_path(
        local_spec_path,
        local_root=root,
        target_workspace=workspace,
    )
    state_path = str(chain_module._state_path_for(Path(remote_spec_path)))
    log_relative = f".megaplan/cloud-chain-{session_name}.log"
    log_path = str(PurePosixPath(workspace) / log_relative)
    marker_path = str(PurePosixPath(_CHAIN_SESSION_MARKER_DIR) / f"{session_name}.json")
    return ChainLaunchContext(
        identity=identity,
        slug=slug,
        digest=digest,
        workspace=workspace,
        remote_spec_path=remote_spec_path,
        session_name=session_name,
        log_relative=log_relative,
        log_path=log_path,
        state_path=state_path,
        marker_path=marker_path,
    )


def _get_provider_identity(spec: CloudSpec) -> str | None:
    """Return a stable provider-level identity for marker enrichment and
    consistency checks.

    This is the provider's *service/project identity*, never an SSH attach
    session name or chain tmux session name.
    """
    if spec.provider == "local":
        if spec.local is not None:
            return spec.local.compose_project
        return None
    if spec.provider == "ssh":
        if spec.ssh is not None:
            return spec.ssh.host
        return None
    return None


def _deploy_log_hint(spec: CloudSpec) -> dict[str, Any]:
    if spec.provider == "local":
        return {"command": "arnold cloud logs --no-follow"}
    if spec.provider == "ssh":
        return {"command": "arnold cloud logs --no-follow"}
    return {"status": "unknown"}


def _deploy_context_steps(deploy_dir: Path) -> list[DeployStepReport]:
    steps: list[DeployStepReport] = []
    for relative in ("Dockerfile", "entrypoint.sh"):
        path = deploy_dir / relative
        if not path.exists():
            steps.append(
                DeployStepReport(
                    name=f"render {relative}",
                    status="missing",
                    detail=f"{relative} was not materialized",
                )
            )
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        steps.append(
            DeployStepReport(
                name=f"render {relative}",
                status="ok",
                detail=f"sha256={digest}",
                metadata={"path": str(path), "sha256": digest},
            )
        )
    return steps


def _coerce_deploy_report(result: Any, *, spec: CloudSpec, deploy_dir: Path) -> DeployReport:
    if isinstance(result, DeployReport):
        report = result
        report.deploy_dir = str(deploy_dir)
        if not report.logs:
            report.logs = _deploy_log_hint(spec)
        if not report.provider:
            report.provider = spec.provider
        if report.service is None:
            report.service = _get_provider_identity(spec)
        return report

    exit_code = int(result)
    success = exit_code == 0
    return DeployReport(
        success=success,
        provider=spec.provider,
        service=_get_provider_identity(spec),
        deploy_dir=str(deploy_dir),
        steps=[
            DeployStepReport(
                name="provider deploy",
                status="ok" if success else "failed",
                detail="provider returned an exit code only; image rebuild decision is provider-controlled",
            )
        ],
        image_rebuild="unknown",
        no_op=False,
        logs=_deploy_log_hint(spec),
        verdict=(
            "deploy: provider deploy completed; image rebuild outcome unknown"
            if success
            else f"deploy: provider deploy failed with exit {exit_code}"
        ),
        exit_code=exit_code,
    )


def _oauth_seed_detail(seed_result: dict[str, list[dict[str, str]]]) -> str:
    events = seed_result.get("events", [])
    counts: dict[str, int] = {}
    for event in events:
        status = event.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1
    if not counts:
        return "no oauth seed events"
    return ", ".join(f"{status}={count}" for status, count in sorted(counts.items()))


def _tail_text(text: str, *, max_lines: int = 20, max_chars: int = 4000) -> str:
    if not text:
        return ""
    lines = text.splitlines()
    tail = "\n".join(lines[-max_lines:])
    if len(tail) > max_chars:
        tail = tail[-max_chars:]
    return tail


def _step_payload(
    step: DeployStepReport,
    *,
    secret_names: list[str] | tuple[str, ...],
    env: dict[str, str] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": step.name,
        "status": step.status,
    }
    if step.detail:
        payload["detail"] = step.detail
    if step.log_ref:
        payload["log_ref"] = step.log_ref
    stdout_tail = _tail_text(step.stdout)
    stderr_tail = _tail_text(step.stderr)
    if stdout_tail:
        payload["stdout_tail"] = redact(stdout_tail, secret_names, env=env)
    if stderr_tail:
        payload["stderr_tail"] = redact(stderr_tail, secret_names, env=env)
    if step.metadata:
        payload["metadata"] = step.metadata
    return payload


def _deploy_report_payload(
    report: DeployReport,
    *,
    secret_names: list[str] | tuple[str, ...],
    env: dict[str, str] | None,
) -> dict[str, Any]:
    return {
        "success": report.success,
        "event": "cloud_deploy",
        "provider": report.provider,
        "service": report.service,
        "deploy_dir": report.deploy_dir,
        "steps": [
            _step_payload(step, secret_names=secret_names, env=env)
            for step in report.steps
        ],
        "image_rebuild": report.image_rebuild,
        "image_ref": report.image_ref,
        "no_op": report.no_op,
        "vars_updated": report.vars_updated,
        "logs": report.logs,
        "warnings": report.warnings,
        "verdict": report.verdict,
        "note": (
            "cloud deploy updates the thin runner service. Routine arnold behavior "
            "refreshes from the on-volume source clone during cloud chain launch."
        ),
    }


def _emit_deploy_report(
    report: DeployReport,
    *,
    secret_names: list[str] | tuple[str, ...],
    env: dict[str, str] | None,
) -> None:
    sys.stdout.write(f"cloud deploy: provider={report.provider} service={report.service or '<unknown>'}\n")
    for step in report.steps:
        detail = f" ({step.detail})" if step.detail else ""
        sys.stdout.write(f"- {step.name}: {step.status}{detail}\n")
        stdout_tail = _tail_text(step.stdout)
        stderr_tail = _tail_text(step.stderr)
        if stdout_tail:
            redacted = redact(stdout_tail, secret_names, env=env)
            sys.stdout.write("  stdout tail:\n")
            for line in redacted.splitlines():
                sys.stdout.write(f"    {line}\n")
        if stderr_tail:
            redacted = redact(stderr_tail, secret_names, env=env)
            sys.stdout.write("  stderr tail:\n")
            for line in redacted.splitlines():
                sys.stdout.write(f"    {line}\n")
    if report.logs:
        sys.stdout.write(f"logs: {json.dumps(report.logs, sort_keys=True)}\n")
    for warning in report.warnings:
        sys.stdout.write(f"warning: {warning}\n")
    sys.stdout.write(f"{report.verdict}\n")
    sys.stdout.write(
        json.dumps(
            _deploy_report_payload(report, secret_names=secret_names, env=env),
            indent=2,
        )
        + "\n"
    )


def _chain_start_command(
    remote_spec_path: str,
    *,
    project_dir: str | None = None,
    engine_dir: str | None = None,
    one_shot: bool = False,
    no_git_refresh: bool = False,
    log_relative: str = _CHAIN_LOG_RELATIVE,
) -> str:
    """Construct the ``python -m arnold_pipelines.megaplan chain start`` command with canonical quoting.

    Both ``_run_chain_wrapper`` and ``cloud_supervise_tick`` use this helper
    so the session name, log path, trusted env var, and shell quoting stay
    consistent across all entry points.
    """
    flags = f"--spec {shlex.quote(remote_spec_path)}"
    if project_dir:
        flags += f" --project-dir {shlex.quote(project_dir)}"
    if one_shot:
        flags += " --one"
    if no_git_refresh:
        flags += " --no-git-refresh"
    log_target = (
        shlex.quote(str(PurePosixPath(project_dir) / log_relative))
        if project_dir
        else shlex.quote(log_relative)
    )
    prefix = (
        f"if [ -f {shlex.quote(_CLOUD_HOT_ENV_PATH)} ]; then "
        f"set -a; . {shlex.quote(_CLOUD_HOT_ENV_PATH)}; set +a; fi; "
    )
    if engine_dir:
        cwd = shlex.quote(project_dir or engine_dir)
        engine_path = shlex.quote(engine_dir)
        prefix += (
            'ENGINE_DIR="${MEGAPLAN_RUNTIME_SRC:-}"; '
            f'if [ -z "$ENGINE_DIR" ]; then ENGINE_DIR={engine_path}; fi; '
            f'cd {cwd} && PYTHONSAFEPATH=1 PYTHONPATH="$ENGINE_DIR:${{PYTHONPATH:-}}" '
        )
    return (
        f"{prefix}MEGAPLAN_TRUSTED_CONTAINER=1 python -P -m arnold_pipelines.megaplan chain start {flags} "
        f">> {log_target} 2>&1"
    )


def _write_session_marker_command(marker_path: str, marker_payload: dict[str, Any]) -> str:
    marker_json = json.dumps(marker_payload, sort_keys=True)
    return f"printf %s {shlex.quote(marker_json)} > {shlex.quote(marker_path)}"


def _plan_auto_command(
    plan_name: str,
    *,
    workspace: str,
    engine_dir: str | None = None,
    log_relative: str,
) -> str:
    log_target = shlex.quote(str(PurePosixPath(workspace) / log_relative))
    prefix = (
        f"if [ -f {shlex.quote(_CLOUD_HOT_ENV_PATH)} ]; then "
        f"set -a; . {shlex.quote(_CLOUD_HOT_ENV_PATH)}; set +a; fi; "
    )
    if engine_dir:
        engine_path = shlex.quote(engine_dir)
        prefix += f"cd {shlex.quote(workspace)} && PYTHONSAFEPATH=1 PYTHONPATH={engine_path}:${{PYTHONPATH:-}} "
        command = (
            f"python3 -P -m arnold_pipelines.megaplan auto "
            f"--plan {shlex.quote(plan_name)} --project-dir {shlex.quote(workspace)}"
        )
    else:
        command = (
            f"cd {shlex.quote(workspace)} && "
            f"arnold auto --plan {shlex.quote(plan_name)} --project-dir {shlex.quote(workspace)}"
        )
    return f"{prefix}MEGAPLAN_TRUSTED_CONTAINER=1 {command} >> {log_target} 2>&1"


def _megaplan_refresh_command(
    spec: CloudSpec | None = None,
    *,
    force_clean_editable_install: bool = False,
    runtime_src_path: str | None = None,
) -> str:
    src = spec.megaplan.src_path if spec is not None else "/workspace/arnold"
    repo = (spec.megaplan.repo or "") if spec is not None else ""
    ref = _EDITABLE_INSTALL_BRANCH
    lines = [
        "set -e",
        "echo \"[megaplan-refresh] $(date -Iseconds) starting\"",
        f"SRC={shlex.quote(src)}",
        f"REPO={shlex.quote(repo)}",
        f"REF={shlex.quote(ref)}",
        f"RUNTIME_SRC={shlex.quote(runtime_src_path or '')}",
        'if [ -n "$REPO" ] && [ ! -d "$SRC/.git" ]; then',
        '  mkdir -p "$(dirname "$SRC")"',
        '  CLONE_URL="$REPO"',
        '  if [ -n "${GITHUB_TOKEN:-}" ]; then',
        '    case "$CLONE_URL" in',
        '      https://github.com/*) CLONE_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/${CLONE_URL#https://github.com/}" ;;',
        "    esac",
        "  fi",
        '  git clone --branch "$REF" "$CLONE_URL" "$SRC"',
        "fi",
        'if [ -d "$SRC/.git" ]; then',
        '  git -C "$SRC" fetch origin "$REF"',
        '  BRANCH="$(git -C "$SRC" branch --show-current)"',
        '  if [ "$BRANCH" != "$REF" ]; then git -C "$SRC" checkout "$REF"; fi',
        *(
            [
                '  echo "[megaplan-refresh] force-clean enabled: resetting and cleaning $SRC"',
                '  git -C "$SRC" reset --hard "origin/$REF"',
                '  git -C "$SRC" clean -fd',
            ]
            if force_clean_editable_install
            else []
        ),
        '  if [ -n "$(git -C "$SRC" status --porcelain --untracked-files=no)" ]; then',
        '    if [ -n "$RUNTIME_SRC" ]; then',
        '      echo "[megaplan-refresh] source checkout dirty; using clean runtime mirror at $RUNTIME_SRC"',
        '      rm -rf "$RUNTIME_SRC"',
        '      mkdir -p "$(dirname "$RUNTIME_SRC")"',
        '      git clone --shared --no-checkout "$SRC" "$RUNTIME_SRC"',
        '      git -C "$RUNTIME_SRC" fetch origin "$REF"',
        '      git -C "$RUNTIME_SRC" checkout --detach "origin/$REF"',
        '      export MEGAPLAN_RUNTIME_SRC="$RUNTIME_SRC"',
        "    else",
        '      echo "[megaplan-refresh] refusing editable install refresh: tracked changes in source checkout at $SRC"',
        "      exit 19",
        "    fi",
        "  else",
        '    if ! git -C "$SRC" merge-base --is-ancestor HEAD "origin/$REF"; then',
        '      echo "[megaplan-refresh] source checkout has local commits not contained in origin/$REF; attempting push"',
        '      git -C "$SRC" log --oneline --max-count=5 "origin/$REF..HEAD" || true',
        '      if git -C "$SRC" push origin "$REF"; then',
        '        git -C "$SRC" fetch origin "$REF"',
        '      else',
        '        echo "[megaplan-refresh] refusing editable install refresh: $SRC has unpushed local commits not contained in origin/$REF"',
        "        exit 20",
        "      fi",
        "    fi",
        '    git -C "$SRC" pull --ff-only origin "$REF"',
        '    export MEGAPLAN_RUNTIME_SRC="$SRC"',
        "  fi",
        '  if ! git -C "$MEGAPLAN_RUNTIME_SRC" merge-base --is-ancestor HEAD "origin/$REF"; then',
        '    echo "[megaplan-refresh] refusing editable install refresh: $MEGAPLAN_RUNTIME_SRC has local commits not contained in origin/$REF"',
        '    git -C "$MEGAPLAN_RUNTIME_SRC" log --oneline --max-count=5 "origin/$REF..HEAD" || true',
        "    exit 20",
        "  fi",
        '  pip install -e "$MEGAPLAN_RUNTIME_SRC"',
        '  RUNTIME_REVISION="$(git -C "$MEGAPLAN_RUNTIME_SRC" rev-parse HEAD)"',
        '  PYTHONSAFEPATH=1 PYTHONPATH="$MEGAPLAN_RUNTIME_SRC:${PYTHONPATH:-}" python -P -m arnold_pipelines.megaplan.cloud.runtime_provenance --expected-root "$MEGAPLAN_RUNTIME_SRC" --expected-revision "$RUNTIME_REVISION"',
        "else",
        '  echo "[megaplan-refresh] source clone missing at $SRC; skipping editable install"',
        "fi",
        'echo "[megaplan-refresh] done"',
        "true",
    ]
    return "\n".join(lines)


def _refresh_then_chain_start_command(
    remote_spec_path: str,
    *,
    spec: CloudSpec | None = None,
    project_dir: str | None = None,
    one_shot: bool = False,
    no_git_refresh: bool = False,
    force_clean_editable_install: bool = False,
    log_relative: str = _CHAIN_LOG_RELATIVE,
) -> str:
    runtime_src_path = (
        str(PurePosixPath(project_dir) / ".megaplan" / "runtime" / "editable-engine")
        if project_dir
        else None
    )
    refresh = _megaplan_refresh_command(
        spec,
        force_clean_editable_install=force_clean_editable_install,
        runtime_src_path=runtime_src_path,
    )
    engine_dir = spec.megaplan.src_path if spec is not None else "/workspace/arnold"
    return (
        f"{{ {refresh}; }} >> {shlex.quote(log_relative)} 2>&1 && "
        f"{_chain_start_command(remote_spec_path, project_dir=project_dir, engine_dir=engine_dir, one_shot=one_shot, no_git_refresh=no_git_refresh, log_relative=log_relative)}"
    )


def _tmux_chain_launch_command(
    workspace: str,
    remote_spec_path: str,
    *,
    one_shot: bool = False,
    no_git_refresh: bool = False,
    force_clean_editable_install: bool = False,
    session_name: str | None = None,
    spec: CloudSpec | None = None,
    log_relative: str = _CHAIN_LOG_RELATIVE,
    marker_path: str | None = None,
    identity_digest: str | None = None,
    marker_payload: dict[str, Any] | None = None,
) -> str:
    """Return a single shell command that ensures a tmux session is running the chain.

    When the session already exists the command is a no-op (prints a notice).
    Otherwise a new detached session is created.

    *session_name* defaults to :data:`CHAIN_SESSION_NAME` (``megaplan-chain``)
    when not provided.
    """
    name = session_name or CHAIN_SESSION_NAME
    if log_relative == _CHAIN_LOG_RELATIVE and name != CHAIN_SESSION_NAME:
        log_relative = f".megaplan/cloud-chain-{name}.log"
    chain_cmd = _refresh_then_chain_start_command(
        remote_spec_path,
        spec=spec,
        project_dir=workspace,
        one_shot=one_shot,
        no_git_refresh=no_git_refresh,
        force_clean_editable_install=force_clean_editable_install,
        log_relative=log_relative,
    )
    marker = marker_path or str(PurePosixPath(_CHAIN_SESSION_MARKER_DIR) / f"{name}.json")
    digest = identity_digest or ""
    marker_payload = marker_payload or {
        "session": name,
        "workspace": workspace,
        "remote_spec": remote_spec_path,
        "identity_digest": digest,
        "run_kind": "chain",
    }
    from arnold_pipelines.megaplan.notification_safety import (
        notification_context_for_current_execution,
    )

    notification_context = notification_context_for_current_execution()
    if notification_context is not None:
        marker_payload = dict(marker_payload)
        marker_payload.setdefault("notification_context", notification_context)
    from arnold_pipelines.megaplan.resident.provenance import (
        DELEGATION_CONTEXT_ENV,
        encoded_provenance,
        safe_provenance_projection,
    )

    resident_delegation = safe_provenance_projection()
    if resident_delegation is not None:
        marker_payload = dict(marker_payload)
        marker_payload.setdefault("resident_delegation", resident_delegation)
        chain_cmd = (
            f"export {DELEGATION_CONTEXT_ENV}="
            f"{shlex.quote(encoded_provenance(resident_delegation))}; {chain_cmd}"
        )
    return (
        f"mkdir -p {shlex.quote(str(PurePosixPath(workspace) / '.megaplan'))} "
        f"{shlex.quote(str(PurePosixPath(marker).parent))}"
        " && "
        f"if tmux has-session -t {shlex.quote(name)} 2>/dev/null; then "
        f"if [ -f {shlex.quote(marker)} ] && grep -F {shlex.quote(digest)} {shlex.quote(marker)} >/dev/null 2>&1; then "
        f"echo {shlex.quote(f'{name} session already running for this chain')}; "
        "else "
        f"echo {shlex.quote(f'ERROR: {name} session already running for a different chain; refusing to disturb it')}; "
        "exit 17; "
        "fi; "
        "else "
        f"{_write_session_marker_command(marker, marker_payload)}; "
        f"tmux new-session -d -s {shlex.quote(name)} -c {shlex.quote(workspace)} {shlex.quote(chain_cmd)}; "
        f"echo {shlex.quote(f'started {name} session')}; "
        "fi"
    )


def _epic_chain_identity_for(local_spec_path: Path, epic_chain_spec: Any) -> tuple[str, str, str]:
    child_ids = ",".join(epic.id for epic in getattr(epic_chain_spec, "epics", []))
    slug = _slugify_chain_identity(local_spec_path.stem)
    if local_spec_path.name == "epic-chain.yaml" and local_spec_path.parent.parent.name:
        slug = _slugify_chain_identity(local_spec_path.parent.parent.name)
    identity = f"epic-chain:{slug}:{child_ids}"
    digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:10]
    return identity, slug, digest


def _remote_epic_chain_state_path(remote_spec_path: str) -> str:
    spec = PurePosixPath(remote_spec_path)
    digest = hashlib.sha1(remote_spec_path.encode("utf-8")).hexdigest()[:12]
    return str(spec.parent / ".megaplan" / "plans" / ".epic_chains" / f"{spec.stem}-{digest}.json")


def _derive_epic_chain_launch_context(
    *,
    root: Path,
    spec: CloudSpec,
    local_spec_path: Path,
    epic_chain_spec: Any,
) -> ChainLaunchContext:
    identity, slug, digest = _epic_chain_identity_for(local_spec_path, epic_chain_spec)
    session_name = (
        spec.chain_session
        if spec.chain_session_explicit
        else f"{CHAIN_SESSION_NAME}-{slug}-parent-{digest[:8]}"
    )
    workspace = (
        spec.repo.workspace
        if spec.repo.workspace_explicit
        else f"/workspace/{slug}-parent-{digest[:8]}/{_repo_dir_name(spec.repo.url)}"
    )
    remote_spec_path = _remote_chain_workspace_path(
        local_spec_path,
        local_root=root,
        target_workspace=workspace,
    )
    log_relative = f".megaplan/cloud-epic-chain-{session_name}.log"
    log_path = str(PurePosixPath(workspace) / log_relative)
    marker_path = str(PurePosixPath(_CHAIN_SESSION_MARKER_DIR) / f"{session_name}.json")
    return ChainLaunchContext(
        identity=identity,
        slug=slug,
        digest=digest,
        workspace=workspace,
        remote_spec_path=remote_spec_path,
        session_name=session_name,
        log_relative=log_relative,
        log_path=log_path,
        state_path=_remote_epic_chain_state_path(remote_spec_path),
        marker_path=marker_path,
    )


def _epic_chain_start_command(
    remote_spec_path: str,
    *,
    workspace: str,
    engine_dir: str | None = None,
    one_shot: bool = False,
    log_relative: str,
) -> str:
    flags = f"--spec {shlex.quote(remote_spec_path)} --project-dir {shlex.quote(workspace)}"
    if one_shot:
        flags += " --one"
    log_target = shlex.quote(str(PurePosixPath(workspace) / log_relative))
    prefix = (
        f"if [ -f {shlex.quote(_CLOUD_HOT_ENV_PATH)} ]; then "
        f"set -a; . {shlex.quote(_CLOUD_HOT_ENV_PATH)}; set +a; fi; "
    )
    if engine_dir:
        engine_path = shlex.quote(engine_dir)
        prefix += (
            'ENGINE_DIR="${MEGAPLAN_RUNTIME_SRC:-}"; '
            f'if [ -z "$ENGINE_DIR" ]; then ENGINE_DIR={engine_path}; fi; '
            f'cd {shlex.quote(workspace)} && PYTHONSAFEPATH=1 PYTHONPATH="$ENGINE_DIR:${{PYTHONPATH:-}}" '
        )
    return (
        f"{prefix}MEGAPLAN_TRUSTED_CONTAINER=1 python -P -m arnold_pipelines.megaplan epic-chain start {flags} "
        f">> {log_target} 2>&1"
    )


def _refresh_then_epic_chain_start_command(
    remote_spec_path: str,
    *,
    spec: CloudSpec | None = None,
    workspace: str,
    one_shot: bool = False,
    log_relative: str,
) -> str:
    refresh = _megaplan_refresh_command(
        spec,
        runtime_src_path=str(PurePosixPath(workspace) / ".megaplan" / "runtime" / "editable-engine"),
    )
    engine_dir = spec.megaplan.src_path if spec is not None else "/workspace/arnold"
    log_target = str(PurePosixPath(workspace) / log_relative)
    return (
        f"{{ {refresh}; }} >> {shlex.quote(log_target)} 2>&1 || true; "
        f"{_epic_chain_start_command(remote_spec_path, workspace=workspace, engine_dir=engine_dir, one_shot=one_shot, log_relative=log_relative)}"
    )


def _tmux_epic_chain_launch_command(
    workspace: str,
    remote_spec_path: str,
    *,
    one_shot: bool = False,
    session_name: str,
    spec: CloudSpec | None = None,
    log_relative: str,
    marker_path: str,
    identity_digest: str,
    marker_payload: dict[str, Any],
) -> str:
    epic_chain_cmd = _refresh_then_epic_chain_start_command(
        remote_spec_path,
        spec=spec,
        workspace=workspace,
        one_shot=one_shot,
        log_relative=log_relative,
    )
    from arnold_pipelines.megaplan.resident.provenance import (
        DELEGATION_CONTEXT_ENV,
        encoded_provenance,
        safe_provenance_projection,
    )

    resident_delegation = safe_provenance_projection()
    if resident_delegation is not None:
        marker_payload = dict(marker_payload)
        marker_payload.setdefault("resident_delegation", resident_delegation)
        epic_chain_cmd = (
            f"export {DELEGATION_CONTEXT_ENV}="
            f"{shlex.quote(encoded_provenance(resident_delegation))}; {epic_chain_cmd}"
        )
    return (
        f"mkdir -p {shlex.quote(str(PurePosixPath(workspace) / '.megaplan'))} "
        f"{shlex.quote(str(PurePosixPath(marker_path).parent))}"
        " && "
        f"if tmux has-session -t {shlex.quote(session_name)} 2>/dev/null; then "
        f"if [ -f {shlex.quote(marker_path)} ] && grep -F {shlex.quote(identity_digest)} {shlex.quote(marker_path)} >/dev/null 2>&1; then "
        f"echo {shlex.quote(f'{session_name} session already running for this epic-chain')}; "
        "else "
        f"echo {shlex.quote(f'ERROR: {session_name} session already running for a different run; refusing to disturb it')}; "
        "exit 17; "
        "fi; "
        "else "
        f"{_write_session_marker_command(marker_path, marker_payload)}; "
        f"tmux new-session -d -s {shlex.quote(session_name)} -c {shlex.quote(workspace)} {shlex.quote(epic_chain_cmd)}; "
        f"echo {shlex.quote(f'started {session_name} session')}; "
        "fi"
    )


def _tmux_chain_restart_command(
    workspace: str,
    remote_spec_path: str,
    *,
    session_name: str | None = None,
    spec: CloudSpec | None = None,
    log_relative: str = _CHAIN_LOG_RELATIVE,
    marker_path: str | None = None,
) -> str:
    """Return a shell command that kills any existing tmux session and starts a
    fresh one-shot tick.

    Only the supervisor uses this path — it is never called from the normal
    ``cloud chain`` launch flow.

    *session_name* defaults to :data:`CHAIN_SESSION_NAME` (``megaplan-chain``)
    when not provided.
    """
    name = session_name or CHAIN_SESSION_NAME
    if log_relative == _CHAIN_LOG_RELATIVE and name != CHAIN_SESSION_NAME:
        log_relative = f".megaplan/cloud-chain-{name}.log"
    chain_cmd = _refresh_then_chain_start_command(
        remote_spec_path,
        spec=spec,
        one_shot=True,
        log_relative=log_relative,
    )
    marker = marker_path or str(PurePosixPath(_CHAIN_SESSION_MARKER_DIR) / f"{name}.json")
    return (
        f"mkdir -p {shlex.quote(str(PurePosixPath(workspace) / '.megaplan'))}"
        " && "
        f"if tmux has-session -t {shlex.quote(name)} 2>/dev/null; then "
        f"if [ -f {shlex.quote(marker)} ] && grep -F {shlex.quote(remote_spec_path)} {shlex.quote(marker)} >/dev/null 2>&1; then "
        f"tmux kill-session -t {shlex.quote(name)} 2>/dev/null; "
        "else "
        f"echo {shlex.quote(f'ERROR: {name} session marker does not match {remote_spec_path}; refusing restart')}; "
        "exit 17; "
        "fi; "
        "fi; "
        f"tmux new-session -d -s {shlex.quote(name)} -c {shlex.quote(workspace)} {shlex.quote(chain_cmd)}; "
        f"echo {shlex.quote(f'restarted {name} session')}"
    )


def _chain_state_reset_command(
    *,
    workspace: str,
    state_path: str,
    log_relative: str,
    force: bool = False,
) -> str:
    script = f"""
import json, pathlib, shutil
workspace = pathlib.Path({workspace!r})
state_path = pathlib.Path({state_path!r})
force = {bool(force)!r}
reason = None
removed = []
if state_path.exists():
    try:
        raw = json.loads(state_path.read_text())
    except Exception as exc:
        raw = {{}}
        reason = "invalid-json:" + str(exc)
    completed = raw.get("completed") or []
    last_state = raw.get("last_state")
    current_plan = raw.get("current_plan_name")
    current_index = raw.get("current_milestone_index", -1)
    no_progress = not completed and current_index in (-1, 0)
    if force:
        reason = reason or "forced"
    elif not completed and last_state == "stalled":
        reason = "stalled-without-completed-milestones"
    elif no_progress and last_state is None and not current_plan:
        reason = "empty-no-progress-state"
    if reason:
        state_path.unlink(missing_ok=True)
        removed.append(str(state_path))
        if isinstance(current_plan, str) and current_plan and "/" not in current_plan:
            plan_dir = workspace / ".megaplan" / "plans" / current_plan
            try:
                plan_dir.relative_to(workspace / ".megaplan" / "plans")
                if plan_dir.exists():
                    shutil.rmtree(plan_dir)
                    removed.append(str(plan_dir))
            except Exception as exc:
                print("[chain-reset] skipped plan dir:", exc)
        print(json.dumps({{"status": "reset", "reason": reason, "removed": removed}}, sort_keys=True))
    else:
        print(json.dumps({{"status": "preserved", "reason": "resumable-or-progressed-state", "state_path": str(state_path)}}, sort_keys=True))
else:
    print(json.dumps({{"status": "absent", "state_path": str(state_path)}}, sort_keys=True))
"""
    return (
        f"cd {shlex.quote(workspace)} && "
        f"python3 - <<'MEGAPLAN_RESET' >> {shlex.quote(log_relative)} 2>&1\n"
        f"{script.strip()}\n"
        "MEGAPLAN_RESET"
    )


_DURABLE_MEGAPLAN_DIRS = ("initiatives", "tickets", "ideas")


def _is_durable_megaplan_upload_file(path: Path) -> bool:
    if path.name == ".DS_Store":
        return False
    if path.name.startswith("._"):
        return False
    if "__MACOSX" in path.parts:
        return False
    return True


def _durable_megaplan_uploads(project_root: Path, workspace: str) -> list[tuple[Path, str]]:
    """Return local durable .megaplan files and their remote workspace paths."""
    root = project_root.expanduser().resolve()
    uploads: list[tuple[Path, str]] = []
    for name in _DURABLE_MEGAPLAN_DIRS:
        local_dir = root / ".megaplan" / name
        if not local_dir.exists():
            continue
        for path in sorted(local_dir.rglob("*")):
            if not path.is_file():
                continue
            if not _is_durable_megaplan_upload_file(path):
                continue
            relative = path.relative_to(root)
            remote = str(PurePosixPath(workspace).joinpath(*relative.parts))
            uploads.append((path, remote))
    return uploads


def _write_durable_megaplan_archive(project_root: Path, uploads: list[tuple[Path, str]]) -> Path:
    """Write a tar.gz containing uploads at repo-relative archive names."""
    root = project_root.expanduser().resolve()
    handle = NamedTemporaryFile(suffix=".megaplan-durable.tar.gz", delete=False)
    archive_path = Path(handle.name)
    handle.close()
    with tarfile.open(archive_path, "w:gz") as tar:
        for local_source, _remote_path in uploads:
            arcname = local_source.expanduser().resolve().relative_to(root).as_posix()
            tar.add(local_source, arcname=arcname, recursive=False)
    return archive_path


def _clean_remote_durable_megaplan_command(workspace: str) -> str:
    roots = " ".join(
        shlex.quote(str(PurePosixPath(workspace) / ".megaplan" / name))
        for name in _DURABLE_MEGAPLAN_DIRS
    )
    return f"rm -rf {roots} && mkdir -p {shlex.quote(str(PurePosixPath(workspace) / '.megaplan'))}"


def _resolve_sync_megaplan_context(root: Path, args: argparse.Namespace, spec: CloudSpec):
    from arnold_pipelines.megaplan import chain as chain_module

    explicit_workspace = getattr(args, "workspace", None)
    raw_spec = getattr(args, "spec", None)
    if raw_spec:
        local_spec_path = Path(raw_spec).expanduser().resolve()
        project_root = _chain_project_root(local_spec_path, root)
        _validate_chain_spec_location(
            local_spec_path,
            project_root,
            allow_loose=bool(getattr(args, "allow_loose_chain_spec", False)),
        )
        chain_spec = chain_module.load_spec(local_spec_path)
        ctx = _derive_chain_launch_context(
            root=project_root,
            spec=spec,
            local_spec_path=local_spec_path,
            chain_spec=chain_spec,
        )
        workspace = explicit_workspace or ctx.workspace
        return project_root, workspace, ctx.remote_spec_path, ctx.session_name
    project_root = root.expanduser().resolve()
    workspace = explicit_workspace or spec.repo.workspace
    return project_root, workspace, None, None


def _run_sync_megaplan(root: Path, args: argparse.Namespace, spec: CloudSpec, provider) -> int:
    project_root, workspace, remote_spec, session_name = _resolve_sync_megaplan_context(
        root,
        args,
        spec,
    )
    sync_spec = replace(spec, repo=replace(spec.repo, workspace=workspace))
    _ensure_repo_checkout(sync_spec, provider, relay=False)
    uploads = _durable_megaplan_uploads(project_root, workspace)
    if bool(getattr(args, "clean", False)):
        result = provider.ssh_exec(_clean_remote_durable_megaplan_command(workspace))
        if result.returncode != 0:
            _relay_output(result, secret_names=spec.secrets, env=os.environ)
            raise CliError(
                "provider_failed",
                f"remote .megaplan durable clean failed (exit {result.returncode})",
            )
    archive_path: Path | None = None
    try:
        archive_path = _write_durable_megaplan_archive(project_root, uploads)
        provider.upload_archive(archive_path, workspace)
    finally:
        if archive_path is not None:
            archive_path.unlink(missing_ok=True)
    payload = {
        "success": True,
        "project_root": str(project_root),
        "workspace": workspace,
        "remote_spec": remote_spec,
        "chain_session": session_name,
        "uploaded_files": len(uploads),
        "uploaded_roots": list(_DURABLE_MEGAPLAN_DIRS),
        "cleaned": bool(getattr(args, "clean", False)),
    }
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    return 0


def _initiative_template_placeholder_findings(
    local_spec_path: Path,
    *,
    project_root: Path,
    cloud_yaml: Path | None = None,
) -> list[dict[str, Any]]:
    """Return template placeholders that require an explicit launch override."""
    roots: list[Path] = []
    if is_canonical_chain_spec(local_spec_path, project_root):
        roots.append(local_spec_path.parent)
    else:
        roots.append(local_spec_path)
    if cloud_yaml is not None:
        roots.append(cloud_yaml)

    findings: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for root in roots:
        candidates: list[Path]
        if root.is_dir():
            candidates = [
                path
                for path in root.rglob("*")
                if path.is_file() and path.suffix.lower() in {".md", ".yaml", ".yml"}
            ]
        else:
            candidates = [root]
        for path in candidates:
            resolved = path.expanduser().resolve()
            if resolved in seen or not resolved.exists():
                continue
            seen.add(resolved)
            try:
                text = resolved.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for line_no, line in enumerate(text.splitlines(), start=1):
                match = _TEMPLATE_PLACEHOLDER_RE.search(line)
                if match is None:
                    continue
                findings.append(
                    {
                        "path": str(resolved),
                        "line": line_no,
                        "placeholder": match.group(0),
                    }
                )
    return findings


def _human_gate_findings(chain_spec: Any) -> list[dict[str, Any]]:
    """Return chain-policy settings that intentionally require human action."""
    findings: list[dict[str, Any]] = []
    merge_policy = getattr(chain_spec, "merge_policy", None)
    if merge_policy and merge_policy != "auto":
        findings.append(
            {
                "field": "merge_policy",
                "value": merge_policy,
                "impact": (
                    "milestone PRs park instead of auto-merging; unattended cloud "
                    "chains can stop at awaiting_pr_merge"
                ),
            }
        )
    auto_approve = getattr(chain_spec, "auto_approve", None)
    if auto_approve is False:
        findings.append(
            {
                "field": "driver.auto_approve",
                "value": False,
                "impact": (
                    "prep clarification and human verification gates require an "
                    "operator instead of being converted into conservative assumptions"
                ),
            }
        )
    return findings


_NORTH_STAR_TEMPLATE_PHRASES = (
    "Describe the durable destination every milestone must preserve",
    "List invariants the chain must not violate",
    "Name tempting work that is intentionally out of scope",
    "Describe any acceptable short-lived compromises",
    "List signs the chain is solving the wrong problem",
)


def _multi_sprint_north_star_findings(local_spec_path: Path, chain_spec: Any) -> list[dict[str, Any]]:
    """Return blocking findings for multi-sprint chains with stub North Stars."""
    milestones = list(getattr(chain_spec, "milestones", []) or [])
    if len(milestones) <= 1:
        return []
    north_star = getattr(getattr(chain_spec, "anchors", None), "north_star", None)
    if not isinstance(north_star, str) or not north_star.strip():
        return [
            {
                "code": "missing_north_star",
                "message": "multi-sprint cloud chains require anchors.north_star",
            }
        ]
    from arnold_pipelines.megaplan.anchors import resolve_anchor_path

    path = resolve_anchor_path(local_spec_path, north_star)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [
            {
                "code": "north_star_unreadable",
                "path": str(path),
                "message": str(exc),
            }
        ]
    findings: list[dict[str, Any]] = []
    if _TEMPLATE_PLACEHOLDER_RE.search(text):
        findings.append(
            {
                "code": "north_star_template_placeholder",
                "path": str(path),
                "message": "North Star still contains template placeholders",
            }
        )
    for phrase in _NORTH_STAR_TEMPLATE_PHRASES:
        if phrase in text:
            findings.append(
                {
                    "code": "north_star_default_template_text",
                    "path": str(path),
                    "message": f"North Star still contains default template text: {phrase}",
                }
            )
            break
    body_words = [
        word
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
        for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", line)
    ]
    if len(body_words) < 40:
        findings.append(
            {
                "code": "north_star_too_thin",
                "path": str(path),
                "message": "Multi-sprint North Star must contain at least 40 non-heading words",
                "word_count": len(body_words),
            }
        )
    return findings


def _run_preflight(root: Path, args: argparse.Namespace, spec: CloudSpec, provider) -> int:
    from arnold_pipelines.megaplan import chain as chain_module
    from arnold_pipelines.megaplan.cloud.preflight import resolve_cloud_chain_runtime_dependencies

    local_spec_path = Path(args.spec).expanduser().resolve()
    project_root = _chain_project_root(local_spec_path, root)
    _validate_chain_spec_location(
        local_spec_path,
        project_root,
        allow_loose=bool(getattr(args, "allow_loose_chain_spec", False)),
    )
    placeholder_findings = _initiative_template_placeholder_findings(
        local_spec_path,
        project_root=project_root,
        cloud_yaml=_cloud_yaml_path(root, args),
    )
    chain_spec = chain_module.load_spec(local_spec_path)
    human_gate_findings = _human_gate_findings(chain_spec)
    north_star_findings = _multi_sprint_north_star_findings(local_spec_path, chain_spec)
    anchor_requirement = chain_module.chain_spec.validate_anchor_requirement(chain_spec, local_spec_path)
    chain_module.chain_spec.validate_paths(chain_spec, project_root, spec_path=local_spec_path)
    launch_ctx = _derive_chain_launch_context(
        root=project_root,
        spec=spec,
        local_spec_path=local_spec_path,
        chain_spec=chain_spec,
    )
    preflight_summary = resolve_cloud_chain_runtime_dependencies(
        chain_spec,
        project_dir=project_root,
        cloud_default_agent=spec.agents.get("default"),
    )
    missing_env = _missing_configured_secrets(spec, os.environ)
    remote: dict[str, Any] = {"skipped": bool(getattr(args, "skip_remote", False))}
    if not remote["skipped"]:
        import_check = _run_remote_megaplan_import_check(provider)
        missing_commands = _run_remote_dependency_check(
            provider,
            list(preflight_summary.get("runtime_commands", [])),
        )
        remote.update(
            {
                "import_check": import_check,
                "missing_commands": missing_commands,
            }
        )
    errors: list[str] = []
    if placeholder_findings and not bool(getattr(args, "allow_template_placeholders", False)):
        errors.append(
            "template placeholders remain; edit them or pass --allow-template-placeholders"
        )
    if human_gate_findings and not bool(getattr(args, "allow_human_gates", False)):
        errors.append(
            "human-gated cloud chain policy present; use merge_policy: auto and "
            "driver.auto_approve: true for unattended cloud runs, or pass "
            "--allow-human-gates to acknowledge intentional pauses"
        )
    if north_star_findings:
        errors.append(
            "multi-sprint cloud chain North Star is missing or still looks like a template; fill it in before launch"
        )
    if missing_env:
        errors.append("missing configured local secrets: " + ", ".join(missing_env))
    if remote.get("import_check", {}).get("errors"):
        errors.extend(str(item) for item in remote["import_check"]["errors"])
    if remote.get("missing_commands"):
        errors.append("missing remote commands: " + ", ".join(remote["missing_commands"]))
    payload = {
        "success": not errors,
        "event": "cloud_preflight",
        "project_root": str(project_root),
        "spec": str(local_spec_path),
        "canonical_layout": is_canonical_chain_spec(local_spec_path, project_root),
        "remote": {
            **remote,
            "expected_workspace": launch_ctx.workspace,
            "expected_remote_spec": launch_ctx.remote_spec_path,
            "expected_session": launch_ctx.session_name,
        },
        "anchor": {
            "require_anchor": anchor_requirement.require_anchor,
            "north_star": chain_spec.anchors.north_star,
            "warning": anchor_requirement.warning,
        },
        "preflight": preflight_summary,
        "warnings": _cloud_profile_warnings(preflight_summary, spec),
        "missing_env": missing_env,
        "template_placeholders": placeholder_findings,
        "human_gates": human_gate_findings,
        "north_star_findings": north_star_findings,
        "errors": errors,
    }
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    return 0 if not errors else 1


def _chain_launch_verification_command(
    *,
    workspace: str,
    session_name: str,
    state_path: str,
    log_path: str,
    attempts: int = _CHAIN_VERIFY_ATTEMPTS,
    sleep_seconds: int = _CHAIN_VERIFY_SLEEP_SECONDS,
) -> str:
    script = f"""
	import json, pathlib, re, subprocess, time
workspace = pathlib.Path({workspace!r})
session = {session_name!r}
state_path = pathlib.Path({state_path!r})
log_path = pathlib.Path({log_path!r})
attempts = {int(attempts)!r}
sleep_seconds = {int(sleep_seconds)!r}
last_state = None
advanced = False
for idx in range(max(1, attempts)):
    alive = subprocess.run(["tmux", "has-session", "-t", session], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    log_size = log_path.stat().st_size if log_path.exists() else 0
    state = None
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text())
        except Exception as exc:
            state = {{"error": str(exc)}}
    plan_dirs = []
    plans_root = workspace / ".megaplan" / "plans"
    if plans_root.exists():
        plan_dirs = sorted(p.name for p in plans_root.iterdir() if p.is_dir() and p.name != ".chains")
    advanced = bool(
        state
        and (
            state.get("current_plan_name")
            or state.get("completed")
            or int(state.get("current_milestone_index", -1)) >= 0
        )
    ) or bool(plan_dirs)
    last_state = {{
        "session_alive": alive,
        "chain_log": str(log_path),
        "chain_log_size": log_size,
        "state_path": str(state_path),
        "state_present": state_path.exists(),
        "advanced_past_init": advanced,
        "plan_dirs": plan_dirs[:5],
        "attempts": idx + 1,
    }}
    if alive and advanced:
        break
    if idx + 1 < attempts:
        time.sleep(sleep_seconds)
likely = None
failure_code = None
log_tail = []
if log_path.exists():
    try:
        log_tail = log_path.read_text(errors="replace").splitlines()[-80:]
    except Exception as exc:
        log_tail = [f"<unable to read chain log: {{exc}}>"]
tail_text = "\\n".join(log_tail)
if not last_state["session_alive"]:
    likely = "driver exited; inspect chain log for missing megaplan or dependency failures"
elif not last_state["advanced_past_init"]:
    likely = "driver stayed at init; inspect chain log for stale state, git refresh conflict, or missing megaplan"
if "[megaplan-refresh] refusing editable install refresh" in tail_text:
    likely = "editable install refresh failed before chain start"
    if "tracked changes in source checkout" in tail_text:
        failure_code = "editable_install_refresh_dirty"
    elif "local commits not contained" in tail_text:
        failure_code = "editable_install_refresh_diverged"
    else:
        failure_code = "editable_install_refresh_failed"
last_state["likely_cause"] = likely
last_state["failure_code"] = failure_code
last_state["log_tail"] = log_tail
print(json.dumps(last_state, sort_keys=True))
"""
    return f"python3 - <<'MEGAPLAN_VERIFY'\n{script.strip()}\nMEGAPLAN_VERIFY"


def _run_chain_launch_verification(provider, ctx: ChainLaunchContext) -> dict[str, Any]:
    result = provider.ssh_exec(
        _chain_launch_verification_command(
            workspace=ctx.workspace,
            session_name=ctx.session_name,
            state_path=ctx.state_path,
            log_path=ctx.log_path,
        )
    )
    raw = (result.stdout or "").strip().splitlines()
    if result.returncode != 0:
        return {
            "session_alive": False,
            "advanced_past_init": False,
            "chain_log": ctx.log_path,
            "status": "verification_failed",
            "likely_cause": (result.stderr or result.stdout or "verification command failed").strip(),
        }
    try:
        payload = json.loads(raw[-1] if raw else "{}")
    except json.JSONDecodeError as exc:
        return {
            "session_alive": None,
            "advanced_past_init": None,
            "chain_log": ctx.log_path,
            "status": "verification_unparseable",
            "likely_cause": f"verification output was not JSON: {exc}",
            "raw": result.stdout,
        }
    payload["status"] = "ok" if payload.get("session_alive") and payload.get("advanced_past_init") else "warning"
    return payload


def _watchdog_tracking_verification_command(ctx: ChainLaunchContext) -> str:
    script = f"""
import json, pathlib, sys
marker_path = pathlib.Path({ctx.marker_path!r})
workspace = pathlib.Path({ctx.workspace!r})
remote_spec = pathlib.Path({ctx.remote_spec_path!r})
session = {ctx.session_name!r}
identity_digest = {ctx.digest!r}
checks = {{
    "marker_path": str(marker_path),
    "workspace": str(workspace),
    "remote_spec": str(remote_spec),
    "session": session,
    "marker_present": marker_path.is_file(),
    "workspace_present": workspace.is_dir(),
    "spec_present": remote_spec.is_file(),
    "tracked": False,
    "errors": [],
}}
payload = {{}}
if not checks["marker_present"]:
    checks["errors"].append("marker missing")
else:
    try:
        payload = json.loads(marker_path.read_text())
    except Exception as exc:
        checks["errors"].append(f"marker unreadable: {{exc}}")
if payload:
    for key, expected in {{
        "session": session,
        "workspace": str(workspace),
        "remote_spec": str(remote_spec),
        "identity_digest": identity_digest,
    }}.items():
        if payload.get(key) != expected:
            checks["errors"].append(f"marker {{key}}={{payload.get(key)!r}} expected {{expected!r}}")
if not checks["workspace_present"]:
    checks["errors"].append("workspace missing")
if not checks["spec_present"]:
    checks["errors"].append("remote_spec missing")
checks["tracked"] = not checks["errors"]
print(json.dumps(checks, sort_keys=True))
sys.exit(0 if checks["tracked"] else 1)
"""
    return f"python3 - <<'MEGAPLAN_WATCHDOG_TRACKING'\n{script.strip()}\nMEGAPLAN_WATCHDOG_TRACKING"


def _run_watchdog_tracking_verification(provider, ctx: ChainLaunchContext) -> dict[str, Any]:
    result = provider.ssh_exec(_watchdog_tracking_verification_command(ctx))
    raw = (result.stdout or "").strip().splitlines()
    try:
        payload = json.loads(raw[-1] if raw else "{}")
    except json.JSONDecodeError as exc:
        payload = {
            "tracked": False,
            "errors": [f"tracking verification output was not JSON: {exc}"],
            "raw": result.stdout,
        }
    if result.returncode != 0:
        payload.setdefault("tracked", False)
        if result.stderr:
            payload.setdefault("errors", []).append(result.stderr.strip())
    payload["status"] = "tracked" if payload.get("tracked") else "not_tracked"
    return payload


def _run_chain_wrapper(root: Path, args: argparse.Namespace, spec: CloudSpec, provider) -> int:
    from arnold_pipelines.megaplan import chain as chain_module
    from arnold_pipelines.megaplan.cloud.preflight import resolve_cloud_chain_runtime_dependencies

    generated_canonical_files = [
        Path(path)
        for path in getattr(args, "_generated_canonical_files", []) or []
    ]
    if not bool(getattr(args, "_canonicalized_epic", False)):
        materialized = _materialize_canonical_epic_input(
            root=root,
            spec=spec,
            spec_or_dir=args.spec,
        )
        generated_canonical_files = [Path(path) for path in materialized.created_files]
        sys.stderr.write(
            "cloud chain canonicalized: "
            f"slug={materialized.slug} "
            f"spec={materialized.spec_path} "
            f"generated_chain={materialized.generated_chain}\n"
        )
        args = argparse.Namespace(
            **{
                **vars(args),
                "spec": str(materialized.spec_path),
                "idea_dir": str(materialized.project_root),
                "_canonicalized_epic": True,
                "_generated_canonical_files": [str(path) for path in generated_canonical_files],
            }
        )

    local_spec_path = Path(args.spec).expanduser().resolve()
    project_root = _chain_project_root(local_spec_path, root)
    _validate_chain_spec_location(
        local_spec_path,
        project_root,
        allow_loose=bool(getattr(args, "allow_loose_chain_spec", False)),
    )
    chain_spec = chain_module.load_spec(local_spec_path)
    chain_module.chain_spec.validate_anchor_requirement(chain_spec, local_spec_path)
    chain_module.chain_spec.validate_paths(chain_spec, project_root, spec_path=local_spec_path)
    north_star_findings = _multi_sprint_north_star_findings(local_spec_path, chain_spec)
    if north_star_findings:
        raise CliError(
            "multi_sprint_north_star_not_filled",
            (
                "Multi-sprint cloud chains require a filled-in North Star. "
                "Edit the declared anchors.north_star file before launch."
            ),
            extra={"north_star_findings": north_star_findings},
        )
    human_gate_findings = _human_gate_findings(chain_spec)
    if human_gate_findings and not bool(getattr(args, "allow_human_gates", False)):
        sample = ", ".join(
            f"{item['field']}={item['value']!r}"
            for item in human_gate_findings
        )
        raise CliError(
            "human_gated_cloud_chain",
            (
                "Cloud chain policy contains human gates. For unattended cloud runs, "
                "set merge_policy: auto and driver.auto_approve: true. If these "
                "pauses are intentional, relaunch with --allow-human-gates. "
                f"Findings: {sample}"
            ),
            extra={"human_gates": human_gate_findings},
        )
    placeholder_findings = _initiative_template_placeholder_findings(
        local_spec_path,
        project_root=project_root,
        cloud_yaml=_cloud_yaml_path(root, args),
    )
    if placeholder_findings and not bool(getattr(args, "allow_template_placeholders", False)):
        sample = ", ".join(
            f"{Path(item['path']).name}:{item['line']}={item['placeholder']}"
            for item in placeholder_findings[:5]
        )
        raise CliError(
            "template_placeholders_present",
            (
                "Initiative/cloud template placeholders remain. Edit the generated values "
                "before cloud launch, or pass --allow-template-placeholders to override. "
                f"Examples: {sample}"
            ),
            extra={"template_placeholders": placeholder_findings},
        )
    explicit_base_branch = _chain_spec_has_explicit_base_branch(local_spec_path)
    if not explicit_base_branch:
        chain_spec.base_branch = spec.repo.branch
    editable_install_sync: dict[str, Any] | None
    if bool(getattr(args, "no_editable_install_sync", False)):
        editable_install_sync = {"status": "skipped", "reason": "disabled_by_flag"}
    else:
        editable_install_sync = _sync_launch_head_to_editable_install_branch(
            _arnold_engine_repo_root(),
            branch=_EDITABLE_INSTALL_BRANCH,
            ignore_dirty_paths=generated_canonical_files,
        )
        sys.stderr.write(
            "cloud chain editable-install sync: "
            f"status={editable_install_sync.get('status')} "
            f"branch={editable_install_sync.get('branch')} "
            f"head={str(editable_install_sync.get('editable_head') or '')[:12]}\n"
        )
    driver_overrides: dict[str, Any] = {}
    if spec.driver is not None and spec.driver.max_stall_iterations is not None:
        chain_spec.stall_threshold = spec.driver.max_stall_iterations
        driver_overrides["max_stall_iterations"] = spec.driver.max_stall_iterations
    launch_ctx = _derive_chain_launch_context(
        root=project_root,
        spec=spec,
        local_spec_path=local_spec_path,
        chain_spec=chain_spec,
    )
    launch_spec = replace(
        spec,
        repo=replace(spec.repo, workspace=launch_ctx.workspace),
        chain_session=launch_ctx.session_name,
    )
    preflight_summary = resolve_cloud_chain_runtime_dependencies(
        chain_spec,
        project_dir=project_root,
        cloud_default_agent=spec.agents.get("default"),
    )
    idea_dir = Path(args.idea_dir).expanduser().resolve() if args.idea_dir else local_spec_path.parent.resolve()
    remote_spec_path = launch_ctx.remote_spec_path
    uploads: list[tuple[Path, str]] = []

    for milestone in chain_spec.milestones:
        local_source, tried_paths = _resolve_local_idea_source(
            root=project_root,
            idea_dir=idea_dir,
            workspace=spec.repo.workspace,
            remote_path=milestone.idea,
        )
        if local_source is None:
            tried = "\n".join(f"- {path}" for path in tried_paths)
            raise CliError(
                "missing_idea_file",
                (
                    f"milestone '{milestone.label}' idea not found on disk. Tried:\n"
                    f"{tried}\n"
                    "Invoke from the repository root or adjust --idea-dir to the directory containing chain ideas."
                ),
                extra={
                    "milestone": milestone.label,
                    "tried_paths": [str(path) for path in tried_paths],
                },
            )
        uploads.append(
            (
                local_source,
                _remote_chain_upload_path(
                    milestone.idea,
                    source_workspace=spec.repo.workspace,
                    target_workspace=launch_ctx.workspace,
                ),
            )
        )
    for local_anchor, remote_anchor in _chain_anchor_uploads(local_spec_path, remote_spec_path, chain_spec):
        _append_unique_upload(uploads, local_anchor, remote_anchor)

    missing_env = _missing_configured_secrets(spec, os.environ)
    if missing_env:
        raise CliError(
            "cloud_preflight_failed",
            "Missing configured cloud secrets in the local environment: " + ", ".join(missing_env),
            extra={
                "missing_commands": [],
                "missing_env": missing_env,
                "preflight": preflight_summary,
            },
        )

    _ensure_repo_checkout(launch_spec, provider, relay=False)
    required_commands = list(preflight_summary.get("runtime_commands", []))
    missing_commands = _run_remote_dependency_check(provider, required_commands)
    if missing_commands:
        raise CliError(
            "agent_deps_missing",
            "Remote cloud runner is missing required runtime commands: " + ", ".join(missing_commands),
            extra={
                "missing_commands": missing_commands,
                "missing_env": [],
                "preflight": preflight_summary,
            },
        )

    seed_codex_oauth(spec, provider)
    repo_head = _remote_repo_head(provider, launch_ctx.workspace)
    for local_source, remote_path in uploads:
        provider.upload_file(local_source, remote_path)
    upload_spec_path = _normalized_chain_upload_spec(
        local_spec_path,
        base_branch=chain_spec.base_branch,
        source_workspace=spec.repo.workspace,
        target_workspace=launch_ctx.workspace,
        driver_overrides=driver_overrides or None,
        phase_model_by_label=_phase_model_by_label_from_preflight(preflight_summary),
    )
    try:
        provider.upload_file(upload_spec_path, remote_spec_path)
    finally:
        if upload_spec_path != local_spec_path:
            upload_spec_path.unlink(missing_ok=True)
    reset_result = provider.ssh_exec(
        _chain_state_reset_command(
            workspace=launch_ctx.workspace,
            state_path=launch_ctx.state_path,
            log_relative=launch_ctx.log_relative,
            force=bool(getattr(args, "fresh", False)),
        )
    )
    if reset_result.returncode != 0:
        _relay_output(reset_result, secret_names=spec.secrets, env=os.environ)
        raise CliError(
            "provider_failed",
            f"remote chain state reset check failed (exit {reset_result.returncode})",
        )

    launch_session = launch_ctx.session_name
    session_name = launch_ctx.session_name
    marker_payload = {
        "session": launch_ctx.session_name,
        "workspace": launch_ctx.workspace,
        "remote_spec": launch_ctx.remote_spec_path,
        "identity_digest": launch_ctx.digest,
        "chain_slug": launch_ctx.slug,
        "run_kind": "chain",
        "allow_human_gates": bool(getattr(args, "allow_human_gates", False)),
        "relaunch_command": _refresh_then_chain_start_command(
            remote_spec_path,
            spec=launch_spec,
            project_dir=launch_ctx.workspace,
            log_relative=launch_ctx.log_relative,
            no_git_refresh=bool(getattr(args, "no_git_refresh", False)),
            force_clean_editable_install=bool(getattr(args, "force_clean_editable_install", False)),
        ),
        "editable_source_branch": _EDITABLE_INSTALL_BRANCH,
        "editable_source_head": (
            editable_install_sync.get("editable_head")
            or editable_install_sync.get("launch_head")
        ),
        "editable_install_sync": editable_install_sync,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    result = provider.ssh_exec(
        _tmux_chain_launch_command(
            launch_ctx.workspace,
            remote_spec_path,
            session_name=session_name,
            spec=launch_spec,
            log_relative=launch_ctx.log_relative,
            marker_path=launch_ctx.marker_path,
            identity_digest=launch_ctx.digest,
            marker_payload=marker_payload,
            no_git_refresh=bool(getattr(args, "no_git_refresh", False)),
            force_clean_editable_install=bool(getattr(args, "force_clean_editable_install", False)),
        )
    )
    _relay_output(result, secret_names=spec.secrets, env=os.environ)
    if result.returncode != 0:
        raise CliError(
            "chain_session_collision" if result.returncode == 17 else "provider_failed",
            (result.stderr or result.stdout or "remote tmux launch failed").strip(),
        )
    tracking = _run_watchdog_tracking_verification(provider, launch_ctx)
    if not tracking.get("tracked"):
        raise CliError(
            "watchdog_tracking_failed",
            "cloud launch completed but watchdog tracking verification failed: "
            + "; ".join(str(item) for item in tracking.get("errors", []) or ["unknown error"]),
            extra={"watchdog_tracking": tracking},
        )
    verification = _run_chain_launch_verification(provider, launch_ctx)
    provenance = _cloud_chain_launch_provenance(
        spec=spec,
        ctx=launch_ctx,
        chain_spec=chain_spec,
        preflight_summary=preflight_summary,
        uploaded_idea_count=len(uploads),
        repo_head=repo_head,
        tmux_result=result,
        editable_install_sync=editable_install_sync,
        verification={**verification, "watchdog_tracking": tracking},
    )
    sys.stderr.write(
        "cloud chain launch: "
        f"session={launch_ctx.session_name} "
        f"alive={verification.get('session_alive')} "
        f"advanced={verification.get('advanced_past_init')} "
        f"log={launch_ctx.log_path}"
        + (f" likely_cause={verification.get('likely_cause')}" if verification.get("likely_cause") else "")
        + "\n"
    )
    sys.stdout.write(json.dumps(provenance, indent=2) + "\n")

    marker_path = _marker_dir(_cloud_yaml_path(root, args)) / "last_chain.json"
    marker_path.write_text(
        json.dumps(
            {
                "remote_spec": remote_spec_path,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "base_branch": chain_spec.base_branch,
                "provenance": provenance,
                "editable_install_sync": editable_install_sync,
                "workspace": launch_ctx.workspace,
                "chain_session": launch_session,
                "chain_log": launch_ctx.log_path,
                "extra_repos": [
                    {"url": repo.url, "branch": repo.branch, "workspace": repo.workspace}
                    for repo in launch_spec.extra_repos
                ],
                "provider": spec.provider,
                "provider_identity": _get_provider_identity(spec),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


def _run_launch_epic_wrapper(root: Path, args: argparse.Namespace, spec: CloudSpec, provider) -> int:
    materialized = _materialize_canonical_epic_input(
        root=root,
        spec=spec,
        spec_or_dir=args.spec_or_dir,
        slug_override=getattr(args, "slug", None),
    )
    sys.stderr.write(
        "cloud launch-epic canonicalized: "
        f"slug={materialized.slug} "
        f"spec={materialized.spec_path} "
        f"generated_chain={materialized.generated_chain}\n"
    )
    chain_args = argparse.Namespace(
        **{
            **vars(args),
            "spec": str(materialized.spec_path),
            "idea_dir": str(materialized.project_root),
            "_canonicalized_epic": True,
            "_generated_canonical_files": materialized.created_files,
        }
    )
    return _run_chain_wrapper(root, chain_args, spec, provider)


def _validate_epic_chain_local_inputs(
    *,
    project_root: Path,
    local_spec_path: Path,
    epic_chain_spec: Any,
) -> None:
    from arnold_pipelines.megaplan import chain as chain_module

    parent_north_star = getattr(getattr(epic_chain_spec, "anchors", None), "north_star", None)
    if parent_north_star:
        _resolve_chain_local_artifact(
            parent_north_star,
            project_root=project_root,
            spec_dir=local_spec_path.parent,
        )
    for child in getattr(epic_chain_spec, "epics", []):
        child_spec_path = Path(child.spec).expanduser()
        if not child_spec_path.is_absolute():
            child_spec_path = (local_spec_path.parent / child.spec).resolve()
        if not child_spec_path.is_file():
            raise CliError(
                "missing_epic_artifact",
                f"child epic {child.id!r} spec not found: {child_spec_path}",
            )
        chain_spec = chain_module.load_spec(child_spec_path)
        chain_module.chain_spec.validate_anchor_requirement(chain_spec, child_spec_path)
        child_north_star = getattr(getattr(chain_spec, "anchors", None), "north_star", None)
        if child_north_star:
            _resolve_chain_local_artifact(
                child_north_star,
                project_root=project_root,
                spec_dir=child_spec_path.parent,
            )
        for milestone in getattr(chain_spec, "milestones", []):
            _resolve_chain_local_artifact(
                milestone.idea,
                project_root=project_root,
                spec_dir=child_spec_path.parent,
            )
            milestone_north_star = getattr(getattr(milestone, "anchors", None), "north_star", None)
            if milestone_north_star:
                _resolve_chain_local_artifact(
                    milestone_north_star,
                    project_root=project_root,
                    spec_dir=child_spec_path.parent,
                )


def _epic_chain_state_reset_command(*, state_path: str, force: bool) -> str:
    if not force:
        return "true"
    script = f"""
import json, pathlib
state_path = pathlib.Path({state_path!r})
removed = []
if state_path.exists():
    state_path.unlink()
    removed.append(str(state_path))
print(json.dumps({{"status": "reset", "removed": removed}}, sort_keys=True))
"""
    return f"python3 - <<'MEGAPLAN_EPIC_CHAIN_RESET'\n{script.strip()}\nMEGAPLAN_EPIC_CHAIN_RESET"


def _epic_chain_launch_verification_command(
    *,
    workspace: str,
    session_name: str,
    remote_spec_path: str,
    state_path: str,
    marker_path: str,
    log_path: str,
    attempts: int = _CHAIN_VERIFY_ATTEMPTS,
    sleep_seconds: int = _CHAIN_VERIFY_SLEEP_SECONDS,
) -> str:
    script = f"""
import json, pathlib, re, subprocess, time
workspace = pathlib.Path({workspace!r})
session = {session_name!r}
remote_spec = pathlib.Path({remote_spec_path!r})
state_path = pathlib.Path({state_path!r})
marker_path = pathlib.Path({marker_path!r})
log_path = pathlib.Path({log_path!r})
attempts = {int(attempts)!r}
sleep_seconds = {int(sleep_seconds)!r}
last = {{}}
for idx in range(max(1, attempts)):
    alive = subprocess.run(["tmux", "has-session", "-t", session], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    marker = None
    state = None
    if marker_path.exists():
        try:
            marker = json.loads(marker_path.read_text())
        except Exception as exc:
            marker = {{"error": str(exc)}}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text())
        except Exception as exc:
            state = {{"error": str(exc)}}
    advanced = bool(state and (
        state.get("current_epic_id")
        or state.get("current_spec_path")
        or state.get("completed")
        or int(state.get("current_epic_index", -1)) >= 0
    ))
    last = {{
        "session_alive": alive,
        "workspace_present": workspace.is_dir(),
        "spec_present": remote_spec.is_file(),
        "marker_present": marker_path.is_file(),
        "state_present": state_path.is_file(),
        "advanced_past_init": advanced,
        "epic_chain_log": str(log_path),
        "epic_chain_log_size": log_path.stat().st_size if log_path.exists() else 0,
        "marker": marker,
        "attempts": idx + 1,
    }}
    if alive and last["spec_present"] and last["marker_present"] and advanced:
        break
    if idx + 1 < attempts:
        time.sleep(sleep_seconds)
last["status"] = "ok" if last.get("session_alive") and last.get("spec_present") and last.get("marker_present") and last.get("advanced_past_init") else "warning"
print(json.dumps(last, sort_keys=True))
"""
    return f"python3 - <<'MEGAPLAN_EPIC_CHAIN_VERIFY'\n{script.strip()}\nMEGAPLAN_EPIC_CHAIN_VERIFY"


def _run_epic_chain_launch_verification(provider, ctx: ChainLaunchContext) -> dict[str, Any]:
    result = provider.ssh_exec(
        _epic_chain_launch_verification_command(
            workspace=ctx.workspace,
            session_name=ctx.session_name,
            remote_spec_path=ctx.remote_spec_path,
            state_path=ctx.state_path,
            marker_path=ctx.marker_path,
            log_path=ctx.log_path,
        )
    )
    raw = (result.stdout or "").strip().splitlines()
    if result.returncode != 0:
        return {
            "status": "verification_failed",
            "session_alive": False,
            "likely_cause": (result.stderr or result.stdout or "verification command failed").strip(),
        }
    try:
        return json.loads(raw[-1] if raw else "{}")
    except json.JSONDecodeError as exc:
        return {
            "status": "verification_unparseable",
            "likely_cause": f"verification output was not JSON: {exc}",
            "raw": result.stdout,
        }


def _run_epic_chain_wrapper(root: Path, args: argparse.Namespace, spec: CloudSpec, provider) -> int:
    from arnold_pipelines.megaplan.chain import epic_chain as epic_chain_module

    local_spec_path = Path(args.spec).expanduser().resolve()
    project_root = _chain_project_root(local_spec_path, root)
    epic_chain_spec = epic_chain_module.load_epic_chain_spec(local_spec_path)
    _validate_epic_chain_local_inputs(
        project_root=project_root,
        local_spec_path=local_spec_path,
        epic_chain_spec=epic_chain_spec,
    )

    if bool(getattr(args, "no_editable_install_sync", False)):
        editable_install_sync = {"status": "skipped", "reason": "disabled_by_flag"}
    else:
        editable_install_sync = _sync_launch_head_to_editable_install_branch(
            _arnold_engine_repo_root(),
            branch=_EDITABLE_INSTALL_BRANCH,
        )
        sys.stderr.write(
            "cloud epic-chain editable-install sync: "
            f"status={editable_install_sync.get('status')} "
            f"branch={editable_install_sync.get('branch')} "
            f"head={str(editable_install_sync.get('editable_head') or '')[:12]}\n"
        )

    launch_ctx = _derive_epic_chain_launch_context(
        root=project_root,
        spec=spec,
        local_spec_path=local_spec_path,
        epic_chain_spec=epic_chain_spec,
    )
    launch_spec = replace(
        spec,
        repo=replace(spec.repo, workspace=launch_ctx.workspace),
        chain_session=launch_ctx.session_name,
    )
    _ensure_repo_checkout(launch_spec, provider, relay=False)
    seed_codex_oauth(spec, provider)

    clean_result = provider.ssh_exec(_clean_remote_durable_megaplan_command(launch_ctx.workspace))
    if clean_result.returncode != 0:
        _relay_output(clean_result, secret_names=spec.secrets, env=os.environ)
        raise CliError(
            "provider_failed",
            f"remote .megaplan durable clean failed (exit {clean_result.returncode})",
        )
    uploads = _durable_megaplan_uploads(project_root, launch_ctx.workspace)
    archive_path: Path | None = None
    try:
        archive_path = _write_durable_megaplan_archive(project_root, uploads)
        provider.upload_archive(archive_path, launch_ctx.workspace)
    finally:
        if archive_path is not None:
            archive_path.unlink(missing_ok=True)

    reset_result = provider.ssh_exec(
        _epic_chain_state_reset_command(
            state_path=launch_ctx.state_path,
            force=bool(getattr(args, "fresh", False)),
        )
    )
    if reset_result.returncode != 0:
        _relay_output(reset_result, secret_names=spec.secrets, env=os.environ)
        raise CliError(
            "provider_failed",
            f"remote epic-chain state reset failed (exit {reset_result.returncode})",
        )

    relaunch_command = _refresh_then_epic_chain_start_command(
        launch_ctx.remote_spec_path,
        spec=launch_spec,
        workspace=launch_ctx.workspace,
        one_shot=bool(getattr(args, "one", False)),
        log_relative=launch_ctx.log_relative,
    )
    marker_payload = {
        "session": launch_ctx.session_name,
        "workspace": launch_ctx.workspace,
        "remote_spec": launch_ctx.remote_spec_path,
        "identity_digest": launch_ctx.digest,
        "chain_slug": launch_ctx.slug,
        "run_kind": "epic_chain",
        "relaunch_command": relaunch_command,
        "editable_source_branch": _EDITABLE_INSTALL_BRANCH,
        "editable_source_head": (
            editable_install_sync.get("editable_head")
            or editable_install_sync.get("launch_head")
        ),
        "editable_install_sync": editable_install_sync,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    result = provider.ssh_exec(
        _tmux_epic_chain_launch_command(
            launch_ctx.workspace,
            launch_ctx.remote_spec_path,
            session_name=launch_ctx.session_name,
            spec=launch_spec,
            log_relative=launch_ctx.log_relative,
            marker_path=launch_ctx.marker_path,
            identity_digest=launch_ctx.digest,
            marker_payload=marker_payload,
            one_shot=bool(getattr(args, "one", False)),
        )
    )
    _relay_output(result, secret_names=spec.secrets, env=os.environ)
    if result.returncode != 0:
        raise CliError(
            "chain_session_collision" if result.returncode == 17 else "provider_failed",
            (result.stderr or result.stdout or "remote tmux launch failed").strip(),
        )
    tracking = _run_watchdog_tracking_verification(provider, launch_ctx)
    if not tracking.get("tracked"):
        raise CliError(
            "watchdog_tracking_failed",
            "cloud epic-chain launch completed but watchdog tracking verification failed: "
            + "; ".join(str(item) for item in tracking.get("errors", []) or ["unknown error"]),
            extra={"watchdog_tracking": tracking},
        )
    verification = _run_epic_chain_launch_verification(provider, launch_ctx)
    sys.stderr.write(
        "cloud epic-chain launch: "
        f"session={launch_ctx.session_name} "
        f"alive={verification.get('session_alive')} "
        f"advanced={verification.get('advanced_past_init')} "
        f"log={launch_ctx.log_path}\n"
    )
    payload = {
        "success": True,
        "workspace": launch_ctx.workspace,
        "remote_spec": launch_ctx.remote_spec_path,
        "chain_session": launch_ctx.session_name,
        "chain_log": launch_ctx.log_path,
        "state_path": launch_ctx.state_path,
        "uploaded_files": len(uploads),
        "uploaded_roots": list(_DURABLE_MEGAPLAN_DIRS),
        "verification": {**verification, "watchdog_tracking": tracking},
        "editable_install_sync": editable_install_sync,
    }
    from arnold_pipelines.megaplan.resident.provenance import safe_provenance_projection

    resident_delegation = safe_provenance_projection()
    if resident_delegation is not None:
        payload["resident_delegation"] = resident_delegation
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")

    marker_path = _marker_dir(_cloud_yaml_path(root, args)) / "last_chain.json"
    marker_path.write_text(
        json.dumps(
            {
                "remote_spec": launch_ctx.remote_spec_path,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "base_branch": epic_chain_spec.base_branch,
                "provenance": payload,
                "editable_install_sync": editable_install_sync,
                "workspace": launch_ctx.workspace,
                "chain_session": launch_ctx.session_name,
                "chain_log": launch_ctx.log_path,
                "provider": spec.provider,
                "provider_identity": _get_provider_identity(spec),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


def _derive_bootstrap_session_name(spec: CloudSpec) -> str:
    repo_slug = _repo_dir_name(spec.repo.url)
    workspace_slug = _slugify_chain_identity(PurePosixPath(spec.repo.workspace).name)
    workspace_slug = re.sub(r"-20[0-9]{6}$", "", workspace_slug)
    if repo_slug and workspace_slug.startswith(repo_slug):
        return repo_slug
    return repo_slug or workspace_slug or "megaplan-plan"


def _derive_bootstrap_plan_name(args: argparse.Namespace, *, idea_text: str) -> str:
    explicit = getattr(args, "plan_name", None)
    if explicit:
        return explicit
    from arnold_pipelines.megaplan._core.io import slugify

    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    return f"{slugify(idea_text)}-{timestamp}"


def _bootstrap_log_relative(plan_name: str) -> str:
    return f".megaplan/cloud-logs/{plan_name}.log"


def _bootstrap_marker_payload(
    *,
    session_name: str,
    workspace: str,
    remote_spec: str,
    plan_name: str,
    relaunch_command: str,
) -> dict[str, Any]:
    return {
        "session": session_name,
        "workspace": workspace,
        "remote_spec": remote_spec,
        "run_kind": "plan",
        "plan_name": plan_name,
        "relaunch_command": relaunch_command,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }


def _bootstrap_launch_command(
    *,
    workspace: str,
    remote_idea_path: str,
    plan_name: str,
    robustness: str,
    session_name: str,
    engine_dir: str,
) -> str:
    marker_path = str(PurePosixPath(_CHAIN_SESSION_MARKER_DIR) / f"{session_name}.json")
    log_relative = _bootstrap_log_relative(plan_name)
    relaunch_command = _plan_auto_command(
        plan_name,
        workspace=workspace,
        engine_dir=engine_dir,
        log_relative=log_relative,
    )
    marker_payload = _bootstrap_marker_payload(
        session_name=session_name,
        workspace=workspace,
        remote_spec=remote_idea_path,
        plan_name=plan_name,
        relaunch_command=relaunch_command,
    )
    command = (
        f"mkdir -p {shlex.quote(str(PurePosixPath(marker_path).parent))} "
        f"{shlex.quote(str(PurePosixPath(workspace) / '.megaplan' / 'cloud-logs'))} && "
        f"{_write_session_marker_command(marker_path, marker_payload)} && "
        f"cd {shlex.quote(workspace)} && "
        f"arnold init --project-dir {shlex.quote(workspace)} "
        f"--idea-file {shlex.quote(remote_idea_path)} --auto-start "
        f"--robustness {shlex.quote(robustness)} --name {shlex.quote(plan_name)}"
    )
    return command


def _run_bootstrap_wrapper(args: argparse.Namespace, spec: CloudSpec, provider) -> int:
    local_idea_path = Path(args.idea_file).expanduser().resolve()
    if not local_idea_path.exists():
        raise CliError("missing_idea_file", f"idea file not found: {local_idea_path}")
    idea_text = local_idea_path.read_text(encoding="utf-8")
    plan_name = _derive_bootstrap_plan_name(args, idea_text=idea_text)
    remote_idea_path = str(PurePosixPath(spec.repo.workspace) / "idea.txt")
    _ensure_repo_checkout(spec, provider)
    provider.upload_file(local_idea_path, remote_idea_path)
    command = _bootstrap_launch_command(
        workspace=spec.repo.workspace,
        remote_idea_path=remote_idea_path,
        plan_name=plan_name,
        robustness=args.robustness,
        session_name=_derive_bootstrap_session_name(spec),
        engine_dir=spec.megaplan.src_path,
    )
    result = provider.ssh_exec(command)
    _relay_output(result, secret_names=spec.secrets, env=os.environ)
    return 0


def _resolve_remote_chain_spec(root: Path, args: argparse.Namespace, spec: CloudSpec) -> str:
    explicit = getattr(args, "remote_spec", None)
    if explicit:
        return explicit

    marker_path = _marker_path_no_create(_cloud_yaml_path(root, args)) / "last_chain.json"
    try:
        if marker_path.exists():
            try:
                marker = json.loads(marker_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                marker = {}
            remote_spec = marker.get("remote_spec")
            if isinstance(remote_spec, str) and remote_spec:
                return remote_spec
    except OSError:
        pass  # marker dir not accessible, fall through to spec fallback

    if spec.mode == "chain" and spec.chain is not None:
        return spec.chain.spec

    raise CliError(
        "missing_remote_spec",
        "Unable to locate remote chain spec. Pass --remote-spec <path>, run `cloud chain <spec>` first, or set mode: chain in cloud.yaml.",
    )


def _run_chain_status(root: Path, args: argparse.Namespace, spec: CloudSpec, provider) -> int:
    payload = cloud_chain_status_payload(root, args, spec, provider)
    from arnold_pipelines.megaplan import chain as chain_module

    chain_module._write_chain_status_pretty(payload["summary"], writer=sys.stderr.write)
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    return 0


def _run_supervise_tick(root: Path, args: argparse.Namespace, spec: CloudSpec, provider) -> int:
    """Entrypoint for `arnold cloud supervise --chain`.

    Reads chain status, runs supervisor logic, emits JSON on stdout and a
    human-readable summary on stderr.  The full supervision policy is
    implemented in :func:`cloud_supervise_tick`.
    """
    # ── deferred import to keep the CLI module's top-level light ──────────
    from arnold_pipelines.megaplan.cloud.supervise import cloud_supervise_tick  # noqa: F811

    report = cloud_supervise_tick(root, args, spec, provider)

    # Human-readable summary on stderr.
    event = report.get("event", "unknown")
    acted = report.get("acted", False)
    next_action = report.get("next_action", "none")
    refused = report.get("refused_reason")
    status_line = f"supervisor tick: {event} | acted={acted} | next_action={next_action}"
    if refused:
        status_line += f" | refused_reason={refused}"
    sys.stderr.write(status_line + "\n")

    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    return 0 if report.get("success") else 1


def cloud_status_payload(args: argparse.Namespace, spec: CloudSpec, provider) -> dict[str, Any]:
    """Return the same payload printed by `arnold cloud status`."""
    return provider.status_payload(
        plan=getattr(args, "plan", None),
        workspace=spec.repo.workspace,
    )


def _cloud_chains_command() -> str:
    script = f"""
import json, pathlib, re, subprocess, time
from datetime import datetime, timezone
from arnold_pipelines.megaplan.cloud.session_markers import is_canonical_session_marker_path
marker_dir = pathlib.Path({_CHAIN_SESSION_MARKER_DIR!r})
proc = subprocess.run(["tmux", "list-sessions", "-F", "#S"], text=True, capture_output=True)
sessions_by_name = {{}}
tmux_names = set()
untracked_tmux_sessions = []
watchdog_by_session = {{}}

def _mtime_payload(path):
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {{"mtime": 0.0, "updated_at": ""}}
    return {{
        "mtime": mtime,
        "updated_at": datetime.fromtimestamp(mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
    }}

def _process_status(remote_spec, workspace="", plan_name=""):
    needles = [value for value in (remote_spec, workspace, plan_name) if value]
    if not needles:
        return "unknown"
    ps = subprocess.run(["ps", "-eww", "-o", "args="], text=True, capture_output=True)
    if ps.returncode != 0:
        return "unknown"
    for line in ps.stdout.splitlines():
        if "arnold_pipelines.megaplan" not in line:
            continue
        if all(needle in line for needle in needles[:1]):
            if (
                " chain start" in line
                or " epic-chain start" in line
                or " auto " in line
            ):
                return "alive"
    return "dead"

def _load_health(name):
    path = marker_dir / (name + ".chain-health.progress.json")
    payload = {{"status": "missing", "path": str(path)}}
    if not path.exists():
        return payload
    payload.update(_mtime_payload(path))
    try:
        health = json.loads(path.read_text())
    except Exception as exc:
        payload.update({{"status": "invalid", "error": str(exc)}})
        return payload
    payload.update({{"status": "present", "payload": health}})
    return payload

def _load_watchdog_sessions():
    paths = [
        pathlib.Path("/workspace/watchdog-report.json"),
        pathlib.Path("/workspace/.megaplan/watchdog-report.json"),
    ]
    for path in paths:
        if not path.exists():
            continue
        evidence = {{"status": "present", "path": str(path), **_mtime_payload(path)}}
        try:
            report = json.loads(path.read_text())
        except Exception as exc:
            return {{}}, {{"status": "invalid", "path": str(path), "error": str(exc)}}
        evidence["report_timestamp_utc"] = report.get("timestamp_utc") or report.get("generated_at") or ""
        by_session = {{}}
        for section in ("issues", "items"):
            items = report.get(section)
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                session = item.get("session")
                if not isinstance(session, str) or not session:
                    continue
                by_session[session] = {{
                    "status": "present",
                    "source": section,
                    "path": str(path),
                    "action": item.get("action") or "",
                    "watchdog_status": item.get("status") or "",
                    "message": item.get("message") or "",
                    "remote_spec": item.get("remote_spec") or "",
                    "workspace": item.get("workspace") or "",
                    "report_timestamp_utc": evidence["report_timestamp_utc"],
                }}
        return by_session, evidence
    return {{}}, {{"status": "missing", "path": str(paths[0])}}

def _display_name(payload):
    remote_spec = payload.get("remote_spec") or payload.get("spec") or ""
    if remote_spec:
        parts = pathlib.PurePosixPath(remote_spec).parts
        for marker in (".megaplan",):
            if marker not in parts:
                continue
            idx = parts.index(marker)
            if idx + 2 < len(parts) and parts[idx + 1] in {{"initiatives", "briefs"}}:
                return parts[idx + 2]
        if "/.megaplan/plans/" in remote_spec:
            return pathlib.PurePosixPath(remote_spec).name
    for key in ("plan_name", "name", "chain_slug", "session"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""

def _active_step_evidence(workspace, plan_name):
    payload = {{"status": "missing", "path": ""}}
    if not workspace or not plan_name:
        return payload
    path = pathlib.Path(workspace) / ".megaplan" / "plans" / plan_name / "state.json"
    payload["path"] = str(path)
    if not path.exists():
        return payload
    try:
        state = json.loads(path.read_text())
    except Exception as exc:
        return {{"status": "invalid", "path": str(path), "error": str(exc)}}
    current_state = state.get("current_state") or state.get("state") or ""
    config = state.get("config") if isinstance(state.get("config"), dict) else {{}}
    clarification = state.get("clarification") if isinstance(state.get("clarification"), dict) else {{}}
    questions = clarification.get("questions") if isinstance(clarification.get("questions"), list) else []
    common = {{
        "path": str(path),
        "current_state": current_state,
        "auto_approve": config.get("auto_approve"),
        "clarification_source": clarification.get("source") or "",
        "clarification_intent": clarification.get("intent_summary") or "",
        "clarification_question_count": len(questions),
        "clarification_questions": [q for q in questions if isinstance(q, str)][:5],
    }}
    active_step = state.get("active_step")
    if not isinstance(active_step, dict) or not active_step:
        return {{"status": "absent", **common}}
    return {{
        "status": "present",
        **common,
        "phase": active_step.get("phase") or active_step.get("step") or "",
        "name": active_step.get("name") or "",
        "attempt": active_step.get("attempt"),
        "worker_pid": active_step.get("worker_pid"),
        "last_activity_at": active_step.get("last_activity_at") or "",
    }}

def _latest_plan_state_evidence(workspace):
    payload = {{"status": "missing", "path": "", "mtime": 0.0, "updated_at": ""}}
    if not workspace:
        return payload
    plans_dir = pathlib.Path(workspace) / ".megaplan" / "plans"
    if not plans_dir.exists():
        payload["path"] = str(plans_dir)
        return payload
    latest = None
    for path in plans_dir.glob("*/state.json"):
        try:
            stat = path.stat()
        except OSError:
            continue
        if latest is None or stat.st_mtime > latest[0]:
            latest = (stat.st_mtime, path)
    if latest is None:
        payload["path"] = str(plans_dir)
        return payload
    mtime, path = latest
    try:
        state = json.loads(path.read_text())
    except Exception as exc:
        return {{
            "status": "invalid",
            "path": str(path),
            "mtime": mtime,
            "updated_at": datetime.fromtimestamp(mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
            "error": str(exc),
        }}
    current_state = state.get("current_state") or state.get("state") or ""
    active_step = state.get("active_step") if isinstance(state.get("active_step"), dict) else {{}}
    active_phase = active_step.get("phase") or active_step.get("step") or ""
    return {{
        "status": "present",
        "path": str(path),
        "plan": path.parent.name,
        "state": current_state,
        "active_phase": active_phase,
        "mtime": mtime,
        "updated_at": datetime.fromtimestamp(mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
    }}

def _event_activity_evidence(workspace, plan_name):
    payload = {{"status": "missing", "path": "", "mtime": 0.0, "updated_at": ""}}
    if not workspace or not plan_name:
        return payload
    path = pathlib.Path(workspace) / ".megaplan" / "plans" / plan_name / "events.ndjson"
    payload["path"] = str(path)
    if not path.exists():
        return payload
    try:
        mtime = path.stat().st_mtime
        lines = path.read_text(errors="replace").splitlines()[-300:]
    except Exception as exc:
        return {{"status": "invalid", "path": str(path), "error": str(exc)}}
    latest_valid = None
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except Exception:
            continue
        if not isinstance(event, dict):
            continue
        latest_valid = event
        phase = event.get("phase")
        payload_obj = event.get("payload") if isinstance(event.get("payload"), dict) else {{}}
        if not phase:
            phase = payload_obj.get("phase")
        if phase:
            return {{
                "status": "present",
                "path": str(path),
                "plan": plan_name,
                "phase": str(phase),
                "kind": str(event.get("kind") or ""),
                "seq": event.get("seq"),
                "ts_utc": str(event.get("ts_utc") or ""),
                "mtime": mtime,
                "updated_at": str(event.get("ts_utc") or datetime.fromtimestamp(mtime, timezone.utc).isoformat().replace("+00:00", "Z")),
            }}
    if latest_valid is None:
        return {{
            "status": "empty",
            "path": str(path),
            "plan": plan_name,
            "mtime": mtime,
            "updated_at": datetime.fromtimestamp(mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
        }}
    return {{
        "status": "present",
        "path": str(path),
        "plan": plan_name,
        "phase": "",
        "kind": str(latest_valid.get("kind") or ""),
        "seq": latest_valid.get("seq"),
        "ts_utc": str(latest_valid.get("ts_utc") or ""),
        "mtime": mtime,
        "updated_at": str(latest_valid.get("ts_utc") or datetime.fromtimestamp(mtime, timezone.utc).isoformat().replace("+00:00", "Z")),
    }}

def _policy_evidence(remote_spec):
    payload = {{"status": "missing", "path": remote_spec or ""}}
    if not remote_spec:
        return payload
    path = pathlib.Path(remote_spec)
    if not path.exists():
        return payload
    try:
        text = path.read_text()
    except Exception as exc:
        return {{"status": "invalid", "path": str(path), "error": str(exc)}}
    merge_policy = "auto"
    match = re.search(r"(?m)^merge_policy:\\s*([^\\s#]+)", text)
    if match:
        merge_policy = match.group(1).strip().strip("'\\\"")
    driver_auto_approve = True
    driver_match = re.search(r"(?ms)^driver:\\s*\\n(?P<body>(?:[ \\t]+[^\\n]*\\n?)*)", text)
    if driver_match:
        auto_match = re.search(r"(?m)^[ \\t]+auto_approve:\\s*([^\\s#]+)", driver_match.group("body"))
        if auto_match:
            raw = auto_match.group(1).strip().strip("'\\\"").lower()
            driver_auto_approve = raw in {{"1", "true", "yes", "on"}}
    return {{
        "status": "present",
        "path": str(path),
        "merge_policy": merge_policy,
        "driver_auto_approve": driver_auto_approve,
        "human_gated": merge_policy != "auto" or driver_auto_approve is False,
    }}

def _operator_status(payload):
    status = payload.get("status") or "unknown"
    active = payload.get("active_step_evidence") if isinstance(payload.get("active_step_evidence"), dict) else {{}}
    policy = payload.get("policy_evidence") if isinstance(payload.get("policy_evidence"), dict) else {{}}
    if status == "awaiting_human_verify":
        if active.get("clarification_source") == "prep":
            count = int(active.get("clarification_question_count") or 0)
            return {{
                "status": "blocked_prep_clarification",
                "reason": f"prep clarification waiting for operator ({{count}} question(s))",
                "next_action": "answer clarification and run resume-clarify, or relaunch an unattended cloud chain with driver.auto_approve: true",
            }}
        return {{
            "status": "blocked_human_verification",
            "reason": "plan is awaiting human verification records",
            "next_action": "record human verification verdicts, or relaunch an unattended cloud chain with driver.auto_approve: true",
        }}
    if status == "awaiting_pr_merge":
        return {{
            "status": "blocked_pr_review_policy",
            "reason": f"merge_policy={{policy.get('merge_policy') or 'review'}} requires human PR merge",
            "next_action": "merge the PR, or use merge_policy: auto for unattended cloud chains",
        }}
    if status == "running" and _watchdog_is_repairing(payload.get("watchdog_evidence")):
        return {{
            "status": "running_repairing",
            "reason": "runner process is alive, but watchdog has dispatched repair/meta-repair",
            "next_action": "observe repair artifacts and verify the session advances before relaunching",
        }}
    if status == "running":
        return {{
            "status": "running_phase",
            "reason": "runner or worker process is alive",
            "next_action": "observe progress",
        }}
    if status == "complete":
        return {{
            "status": "complete",
            "reason": "chain is complete",
            "next_action": "none",
        }}
    if policy.get("human_gated") and not payload.get("allow_human_gates"):
        return {{
            "status": "human_gate_misconfigured",
            "reason": f"unacknowledged human-gated policy on cloud session: merge_policy={{policy.get('merge_policy')}} driver.auto_approve={{policy.get('driver_auto_approve')}}",
            "next_action": "switch to merge_policy: auto and driver.auto_approve: true, or relaunch with --allow-human-gates",
        }}
    if policy.get("human_gated"):
        return {{
            "status": status,
            "reason": f"human-gated policy: merge_policy={{policy.get('merge_policy')}} driver.auto_approve={{policy.get('driver_auto_approve')}}",
            "next_action": "expect human pauses, or switch to merge_policy: auto and driver.auto_approve: true",
        }}
    return {{
        "status": status,
        "reason": "",
        "next_action": "inspect logs/state",
    }}

def _payload_for(name):
    marker = marker_dir / (name + ".json")
    payload = {{
        "session": name,
        "marker": str(marker),
        "marker_evidence": {{"status": "missing", "path": str(marker)}},
        "tmux_evidence": {{"status": "alive" if name in tmux_names else "missing"}},
    }}
    if marker.exists():
        payload["marker_evidence"].update(_mtime_payload(marker))
        try:
            payload.update(json.loads(marker.read_text()))
            payload["marker_evidence"].update({{"status": "present", "path": str(marker)}})
        except Exception as exc:
            payload["marker_evidence"] = {{"status": "invalid", "path": str(marker), "error": str(exc)}}
    payload["chain_health_evidence"] = _load_health(name)
    health_payload = payload["chain_health_evidence"].get("payload")
    if isinstance(health_payload, dict):
        payload["health"] = health_payload
    payload["process_evidence"] = {{
        "status": _process_status(
            payload.get("remote_spec") or "",
            payload.get("workspace") or "",
            payload.get("plan_name") or "",
        ),
        "remote_spec": payload.get("remote_spec") or "",
    }}
    plan_name = payload.get("plan_name")
    if not plan_name and isinstance(health_payload, dict):
        plan_name = health_payload.get("current_plan_name")
    payload["latest_plan_state"] = _latest_plan_state_evidence(payload.get("workspace"))
    latest_plan_state = payload["latest_plan_state"] if isinstance(payload["latest_plan_state"], dict) else {{}}
    if not plan_name and latest_plan_state.get("status") == "present":
        plan_name = latest_plan_state.get("plan")
    payload["active_step_evidence"] = _active_step_evidence(payload.get("workspace"), plan_name)
    payload["event_activity_evidence"] = _event_activity_evidence(payload.get("workspace"), plan_name)
    payload["policy_evidence"] = _policy_evidence(payload.get("remote_spec") or "")
    payload["display_name"] = _display_name(payload)
    payload["marker_status"] = payload["marker_evidence"]["status"]
    payload["tmux_status"] = payload["tmux_evidence"]["status"]
    payload["process_status"] = payload["process_evidence"]["status"]
    payload["chain_health_status"] = payload["chain_health_evidence"]["status"]
    payload["active_step_status"] = payload["active_step_evidence"]["status"]
    payload["event_activity_status"] = payload["event_activity_evidence"]["status"]
    payload["watchdog_evidence"] = watchdog_by_session.get(
        name,
        {{"status": "missing", "path": "/workspace/watchdog-report.json"}},
    )
    payload["watchdog_action"] = payload["watchdog_evidence"].get("action", "")
    payload["watchdog_status"] = payload["watchdog_evidence"].get("watchdog_status", "")
    payload["status"] = _effective_session_status(payload)
    payload["operator_status"] = _operator_status(payload)
    payload["status_reason"] = payload["operator_status"].get("reason", "")
    payload["next_action"] = payload["operator_status"].get("next_action", "")
    payload["watchdog_repairing"] = _watchdog_is_repairing(payload["watchdog_evidence"])
    payload["should_be_running"] = _should_be_running(payload)
    return payload

def _watchdog_is_repairing(evidence):
    if not isinstance(evidence, dict) or evidence.get("status") != "present":
        return False
    custody = evidence.get("repair_custody")
    if not isinstance(custody, dict):
        return False
    active_requests = {{str(value) for value in custody.get("active_request_ids", []) if str(value)}}
    active_claims = {{str(value) for value in custody.get("active_claim_request_ids", []) if str(value)}}
    if active_requests & active_claims:
        return True
    for attempt in custody.get("attempts", []):
        if not isinstance(attempt, dict) or attempt.get("terminal") is not False:
            continue
        if not attempt.get("attempt_id") or not attempt.get("path"):
            continue
        request_id = str(attempt.get("request_id") or "")
        if request_id and request_id in active_requests:
            return True
        if attempt.get("source") == "repair_queue_dispatch_attempt" and attempt.get("blocker_id"):
            return True
    return False

def _should_be_running(payload):
    status = payload.get("status")
    if status == "running":
        return True
    if status in {{
        "complete",
        "awaiting_human_verify",
        "awaiting_pr_merge",
        "blocked",
        "failed",
        "needs_human",
        "authority_divergence",
        "missing_base_ref",
        "retrying_failure",
    }}:
        return False
    watchdog_status = payload.get("watchdog_status")
    if watchdog_status in {{"needs_human", "awaiting_pr_merge"}}:
        return False
    if status in {{"initialized", "prepped", "planned", "gated", "finalized", "executed", "reviewed", "stopped"}}:
        return True
    return False

def _effective_session_status(payload):
    if payload.get("tmux_status") == "alive" or payload.get("process_status") == "alive":
        return "running"
    active_step = payload.get("active_step_evidence")
    if isinstance(active_step, dict):
        current_state = active_step.get("current_state")
        if current_state == "done":
            return "complete"
        if active_step.get("status") == "present" and (
            payload.get("tmux_status") == "alive" or payload.get("process_status") == "alive"
        ):
            return "running"
        if current_state in {{
            "awaiting_human_verify",
            "awaiting_pr_merge",
            "blocked",
            "failed",
            "initialized",
            "prepped",
            "planned",
            "gated",
            "finalized",
            "executed",
                "reviewed",
        }}:
            return str(current_state)
    health = payload.get("health")
    if isinstance(health, dict):
        last_state = health.get("last_state")
        chain_complete = health.get("chain_complete")
        if last_state == "done" and chain_complete is not False:
            return "complete"
        if last_state == "done" and chain_complete is False:
            return "stale_bookkeeping"
        if last_state in {{
            "awaiting_human_verify",
            "awaiting_pr_merge",
            "needs_human",
            "blocked",
            "authority_divergence",
            "missing_base_ref",
            "stalled",
            "retrying_failure",
        }}:
            return str(last_state)
    watchdog_status = payload.get("watchdog_status")
    if watchdog_status == "complete":
        return "complete"
    if watchdog_status in {{"awaiting_pr_merge", "needs_human"}}:
        return str(watchdog_status)
    return "stopped"

watchdog_by_session, watchdog_report_evidence = _load_watchdog_sessions()

if proc.returncode == 0:
    for line in proc.stdout.splitlines():
        name = line.strip()
        if not name:
            continue
        tmux_names.add(name)
        marker = marker_dir / (name + ".json")
        if marker.exists():
            sessions_by_name[name] = _payload_for(name)
        else:
            untracked_tmux_sessions.append(name)
if marker_dir.exists():
    for marker in sorted(marker_dir.glob("*.json")):
        if not is_canonical_session_marker_path(marker):
            continue
        name = marker.stem
        sessions_by_name.setdefault(name, _payload_for(name))
sessions = sorted(sessions_by_name.values(), key=lambda item: item.get("session", ""))
summary = {{}}
operator_summary = {{}}
should_be_running_count = 0
watchdog_repairing_count = 0
for item in sessions:
    summary[item.get("status", "unknown")] = summary.get(item.get("status", "unknown"), 0) + 1
    operator = item.get("operator_status") if isinstance(item.get("operator_status"), dict) else {{}}
    operator_key = operator.get("status") or item.get("status", "unknown")
    operator_summary[operator_key] = operator_summary.get(operator_key, 0) + 1
    if item.get("should_be_running"):
        should_be_running_count += 1
    if item.get("watchdog_repairing"):
        watchdog_repairing_count += 1
print(json.dumps({{
    "success": True,
    "marker_dir": str(marker_dir),
    "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "sessions": sessions,
    "summary": summary,
    "operator_summary": operator_summary,
    "should_be_running_count": should_be_running_count,
    "watchdog_repairing_count": watchdog_repairing_count,
    "watchdog_report_evidence": watchdog_report_evidence,
    "untracked_tmux_sessions": sorted(untracked_tmux_sessions),
}}, sort_keys=True))
"""
    return f"python3 - <<'MEGAPLAN_CHAINS'\n{script.strip()}\nMEGAPLAN_CHAINS"


_SINCE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([smhd])\s*$", re.IGNORECASE)


def _parse_cloud_status_since(value: str | None, *, now: datetime | None = None) -> datetime | None:
    if not value:
        return None
    now = now or datetime.now(timezone.utc)
    match = _SINCE_RE.match(value)
    if match:
        amount = float(match.group(1))
        unit = match.group(2).lower()
        seconds_by_unit = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        return now - timedelta(seconds=amount * seconds_by_unit[unit])
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise CliError("invalid_args", f"invalid --since value {value!r}; use a duration like 12h or an ISO timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_cloud_status_timestamp(value: Any) -> datetime | None:
    if isinstance(value, (int, float)) and value > 0:
        return datetime.fromtimestamp(float(value), timezone.utc)
    if not isinstance(value, str) or not value:
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _cloud_session_real_activity_at(item: Mapping[str, Any]) -> datetime | None:
    """Return the newest timestamp tied to actual chain/plan activity.

    Watchdog health files can be rewritten after a chain is done, so this
    intentionally prefers plan ``state.json`` evidence and launch markers over
    watchdog mtimes.
    """
    event_activity = item.get("event_activity_evidence")
    if isinstance(event_activity, Mapping) and event_activity.get("status") in {"present", "empty", "invalid"}:
        timestamp = _parse_cloud_status_timestamp(event_activity.get("updated_at")) or _parse_cloud_status_timestamp(
            event_activity.get("mtime")
        )
        if timestamp is not None:
            return timestamp
    latest_state = item.get("latest_plan_state")
    if isinstance(latest_state, Mapping) and latest_state.get("status") in {"present", "invalid"}:
        timestamp = _parse_cloud_status_timestamp(latest_state.get("updated_at")) or _parse_cloud_status_timestamp(
            latest_state.get("mtime")
        )
        if timestamp is not None:
            return timestamp
    active = item.get("active_step_evidence")
    if isinstance(active, Mapping):
        timestamp = _parse_cloud_status_timestamp(active.get("last_activity_at"))
        if timestamp is not None:
            return timestamp
    return _parse_cloud_status_timestamp(item.get("started_at"))


def _cloud_session_plan_state(item: Mapping[str, Any]) -> str:
    event_activity = item.get("event_activity_evidence")
    if isinstance(event_activity, Mapping) and event_activity.get("phase"):
        return str(event_activity.get("phase"))
    active = item.get("active_step_evidence")
    if isinstance(active, Mapping) and active.get("phase"):
        return str(active.get("phase"))
    latest_state = item.get("latest_plan_state")
    if isinstance(latest_state, Mapping) and latest_state.get("active_phase"):
        return str(latest_state.get("active_phase"))
    if isinstance(latest_state, Mapping) and latest_state.get("state"):
        return str(latest_state.get("state"))
    if isinstance(active, Mapping) and active.get("current_state"):
        return str(active.get("current_state"))
    health = item.get("health")
    if isinstance(health, Mapping) and health.get("last_state"):
        return str(health.get("last_state"))
    return ""


def _recount_cloud_sessions(payload: dict[str, Any], sessions: list[Any]) -> None:
    summary: dict[str, int] = {}
    operator_summary: dict[str, int] = {}
    should_be_running_count = 0
    watchdog_repairing_count = 0
    for item in sessions:
        if not isinstance(item, Mapping):
            continue
        status = str(item.get("status") or "unknown")
        summary[status] = summary.get(status, 0) + 1
        operator = item.get("operator_status") if isinstance(item.get("operator_status"), Mapping) else {}
        operator_key = str(operator.get("status") or status)
        operator_summary[operator_key] = operator_summary.get(operator_key, 0) + 1
        if item.get("should_be_running"):
            should_be_running_count += 1
        if item.get("watchdog_repairing"):
            watchdog_repairing_count += 1
    payload["sessions"] = sessions
    payload["summary"] = summary
    payload["operator_summary"] = operator_summary
    payload["should_be_running_count"] = should_be_running_count
    payload["watchdog_repairing_count"] = watchdog_repairing_count


def _filter_cloud_sessions_since(payload: dict[str, Any], since: datetime | None) -> None:
    if since is None:
        return
    sessions = payload.get("sessions")
    if not isinstance(sessions, list):
        return
    filtered = []
    for item in sessions:
        if not isinstance(item, Mapping):
            continue
        activity_at = _cloud_session_real_activity_at(item)
        if activity_at is not None and activity_at >= since:
            copied = dict(item)
            copied["real_activity_at"] = activity_at.isoformat().replace("+00:00", "Z")
            filtered.append(copied)
    payload["unfiltered_session_count"] = len(sessions)
    payload["since"] = since.isoformat().replace("+00:00", "Z")
    _recount_cloud_sessions(payload, filtered)


def _cloud_compact_line(item: Mapping[str, Any]) -> str:
    operator = item.get("operator_status") if isinstance(item.get("operator_status"), Mapping) else {}
    latest_state = item.get("latest_plan_state") if isinstance(item.get("latest_plan_state"), Mapping) else {}
    event_activity = item.get("event_activity_evidence") if isinstance(item.get("event_activity_evidence"), Mapping) else {}
    health = item.get("health") if isinstance(item.get("health"), Mapping) else {}
    current_plan = item.get("plan_name") or health.get("current_plan_name") or ""
    activity_plan = latest_state.get("plan") or current_plan
    activity = item.get("real_activity_at") or event_activity.get("updated_at") or latest_state.get("updated_at") or item.get("started_at") or ""
    return (
        f"- {item.get('display_name') or item.get('session')} "
        f"session={item.get('session')} status={item.get('status')} "
        f"operator={operator.get('status') or item.get('status')} "
        f"should_run={'yes' if item.get('should_be_running') else 'no'} "
        f"repairing={'yes' if item.get('watchdog_repairing') else 'no'} "
        f"current_plan={current_plan} activity_plan={activity_plan or ''} "
        f"activity_state={_cloud_session_plan_state(item)} "
        f"activity={activity} workspace={item.get('workspace')}"
    )


def _emit_cloud_sessions_human(payload: dict[str, Any], *, compact: bool) -> None:
    sessions = payload.get("sessions") if isinstance(payload, dict) else []
    if not isinstance(sessions, list):
        return
    since_detail = f" since={payload.get('since')}" if payload.get("since") else ""
    unfiltered_detail = (
        f" filtered_from={payload.get('unfiltered_session_count')}"
        if payload.get("unfiltered_session_count") is not None
        else ""
    )
    sys.stderr.write(
        f"cloud sessions: {len(sessions)}{since_detail}{unfiltered_detail} "
        f"should_be_running={payload.get('should_be_running_count', 0)} "
        f"watchdog_repairing={payload.get('watchdog_repairing_count', 0)} "
        f"operator_summary={payload.get('operator_summary', {})}\n"
    )
    for item in sessions:
        if not isinstance(item, dict):
            continue
        if compact:
            sys.stderr.write(_cloud_compact_line(item) + "\n")
            continue
        health = item.get("health") if isinstance(item.get("health"), dict) else {}
        active = item.get("active_step_evidence") if isinstance(item.get("active_step_evidence"), dict) else {}
        policy = item.get("policy_evidence") if isinstance(item.get("policy_evidence"), dict) else {}
        operator = item.get("operator_status") if isinstance(item.get("operator_status"), dict) else {}
        latest_state = item.get("latest_plan_state") if isinstance(item.get("latest_plan_state"), dict) else {}
        event_activity = item.get("event_activity_evidence") if isinstance(item.get("event_activity_evidence"), dict) else {}
        display_state = active.get("current_state") or (health.get("last_state") if health else "")
        detail = ""
        if health:
            health_state = health.get("last_state")
            health_detail = ""
            if display_state and health_state and display_state != health_state:
                health_detail = f" health_state={health_state}"
            detail = (
                f" state={display_state}{health_detail} "
                f"plan={health.get('current_plan_name') or ''} "
                f"completed={health.get('completed_count')}"
            )
        elif display_state:
            detail = f" state={display_state}"
        if event_activity.get("status") == "present" and event_activity.get("phase"):
            detail += (
                f" active_phase={event_activity.get('phase') or ''}"
                f" active_event={event_activity.get('kind') or ''}"
                f" active_activity={event_activity.get('updated_at') or ''}"
            )
        if latest_state.get("status") == "present":
            detail += (
                f" latest_plan={latest_state.get('plan') or ''}"
                f" lifecycle_state={latest_state.get('state') or ''}"
                f" latest_activity={latest_state.get('updated_at') or ''}"
            )
        watchdog_detail = ""
        if item.get("watchdog_evidence", {}).get("status") == "present":
            watchdog_detail = (
                f" watchdog={item.get('watchdog_status') or ''}"
                f" watchdog_action={item.get('watchdog_action') or ''}"
            )
        policy_detail = ""
        if policy.get("status") == "present":
            policy_detail = (
                f" merge_policy={policy.get('merge_policy')} "
                f"auto_approve={policy.get('driver_auto_approve')}"
            )
        operator_detail = ""
        if operator:
            operator_detail = (
                f" operator={operator.get('status') or ''}"
                f" reason={operator.get('reason') or ''}"
                f" next={operator.get('next_action') or ''}"
            )
        sys.stderr.write(
            f"- {item.get('display_name') or item.get('session')} "
            f"session={item.get('session')} status={item.get('status')} "
            f"should_run={'yes' if item.get('should_be_running') else 'no'} "
            f"repairing={'yes' if item.get('watchdog_repairing') else 'no'} "
            f"tmux={item.get('tmux_status')} process={item.get('process_status')}"
            f"{watchdog_detail}"
            f"{policy_detail}"
            f"{operator_detail}"
            f"{detail} workspace={item.get('workspace')} spec={item.get('remote_spec')}\n"
        )


def _in_trusted_container() -> bool:
    """True when this process is the cloud worker itself (no SSH needed).

    Delegates to :func:`status_snapshot.is_trusted_container` so the CLI and the
    resident share one definition of "we are the box."
    """
    return status_snapshot.is_trusted_container()


def _emit_cloud_status_human(snapshot: dict[str, Any] | None, *, compact: bool) -> None:
    text = (
        status_format.format_cloud_status_short(snapshot, max_chars=10**9)[0]
        if compact
        else status_format.format_cloud_status_detailed(snapshot)
    )
    if text:
        sys.stderr.write(text + "\n")


def _run_status_all(spec: CloudSpec, provider, *, args: argparse.Namespace | None = None) -> int:
    """``cloud status --all`` against the canonical snapshot.

    Inside the trusted container: read the snapshot the watchdog wrote, or
    rebuild it locally from observation only — never SSH back to our own host.
    From a laptop: fetch the same snapshot from the box; if the box has not
    started producing one yet, fall back to the legacy remote listing so the
    command never hard-fails during the rollout.
    """
    compact = bool(getattr(args, "compact", False)) if args is not None else False

    if _in_trusted_container():
        snapshot, _degraded = status_snapshot.load_cloud_status_snapshot(
            status_snapshot.DEFAULT_SNAPSHOT_PATH, max_age_s=3600
        )
        if snapshot is None:
            snapshot = status_snapshot.build_cloud_status_snapshot()
        _emit_cloud_status_human(snapshot, compact=compact)
        sys.stdout.write(json.dumps(snapshot, indent=2) + "\n")
        return 0

    # Laptop path: ask the box for the same snapshot its watchdog produced.
    try:
        raw = provider.read_remote_file(str(status_snapshot.DEFAULT_SNAPSHOT_PATH))
        snapshot = json.loads(raw)
    except (CliError, OSError, ValueError) as exc:
        sys.stderr.write(
            f"cloud status: snapshot unavailable on box ({exc.__class__.__name__}); "
            "falling back to legacy remote listing\n"
        )
        return _run_cloud_chains(spec, provider, args=args)
    if not isinstance(snapshot, dict):
        sys.stderr.write("cloud status: box snapshot malformed; falling back to legacy remote listing\n")
        return _run_cloud_chains(spec, provider, args=args)
    stale_reason = _cloud_status_snapshot_stale_reason(snapshot)
    if stale_reason:
        sys.stderr.write(
            f"cloud status: box snapshot stale ({stale_reason}); "
            "falling back to legacy remote listing\n"
        )
        return _run_cloud_chains(spec, provider, args=args)
    _emit_cloud_status_human(snapshot, compact=compact)
    sys.stdout.write(json.dumps(snapshot, indent=2) + "\n")
    return 0


def _cloud_status_snapshot_stale_reason(snapshot: Mapping[str, Any]) -> str | None:
    generated = status_snapshot._parse_iso(snapshot.get("generated_at"))
    if generated is None:
        return "missing generated_at"
    age = (datetime.now(timezone.utc) - generated).total_seconds()
    if age > CLOUD_STATUS_CLI_MAX_AGE_S:
        return f"{int(age)}s old, limit {CLOUD_STATUS_CLI_MAX_AGE_S}s"
    return None


def _run_cloud_chains(spec: CloudSpec, provider, *, args: argparse.Namespace | None = None) -> int:
    del spec
    result = provider.ssh_exec(_cloud_chains_command())
    if result.returncode != 0:
        _relay_output(result, secret_names=[], env=os.environ)
        raise CliError("provider_failed", "unable to list remote cloud chain sessions")
    try:
        payload = json.loads((result.stdout or "").strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise CliError("provider_failed", f"cloud chains did not return JSON: {exc}") from exc
    since = _parse_cloud_status_since(getattr(args, "since", None) if args is not None else None)
    if isinstance(payload, dict):
        _filter_cloud_sessions_since(payload, since)
        _emit_cloud_sessions_human(payload, compact=bool(getattr(args, "compact", False)) if args is not None else False)
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    return 0


def _try_provider_method(provider, method_name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
    """Call *method_name* on *provider* and return the result, or a structured
    ``unknown``/``unavailable`` entry on failure."""
    meth = getattr(provider, method_name, None)
    if meth is None:
        return {"status": "unavailable", "reason": f"provider does not implement {method_name}"}
    try:
        result = meth(*args, **kwargs)
    except (CliError, OSError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "reason": str(exc)}
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        return {"status": "unknown", "raw": result}
    return {"status": "unknown", "payload": result}


def _classify_effective_status(
    chain_state: Any,
    effective: dict[str, Any],
    milestone_count: int,
    plan_status: dict[str, Any],
    runner: dict[str, Any],
    pr: dict[str, Any],
    sync: dict[str, Any],
    human_verification: dict[str, Any] | None = None,
) -> str:
    """Classify the effective chain status into one of seven categories.

    Returns one of:
      ``complete`` — all milestones processed (terminal).
      ``running`` — a plan is executing and the runner is alive.
      ``awaiting_pr_merge`` — merge_policy is 'review' and chain is waiting.
      ``awaiting_human_verify`` — plan is blocked on human verification criteria.
      ``human_prerequisite`` — prerequisite_policy is 'required' and unmet.
      ``quality_gate`` — validation_policy is 'required' and quality gate is failing.
      ``stale_bookkeeping`` — no live runner, no active plan, chain state is stale.
    """
    last_state = getattr(chain_state, "last_state", None)
    current_plan = getattr(chain_state, "current_plan_name", None)

    # Complete/done: all milestones processed (MUST be first — terminal state
    # takes priority over runner liveness checks).
    current_index = getattr(chain_state, "current_milestone_index", -1)
    if milestone_count > 0 and current_index >= milestone_count:
        return "complete"

    # Explicit awaiting_pr_merge state
    if last_state == "awaiting_pr_merge":
        return "awaiting_pr_merge"

    # ── awaiting_human_verify ──────────────────────────────────────────
    # Checked after terminal / pr-merge so those take priority, but BEFORE
    # the generic «running» / «stalled» logic so pending verification does
    # not get misclassified as stale or blocked for other reasons.
    if plan_status.get("status") == "awaiting_human_verify":
        # If verification facts are unavailable, invalid, or missing
        # latest-verdict semantics, fail closed as blocked (do NOT assume
        # the chain is done or recoverable).
        if human_verification is None:
            return "awaiting_human_verify"
        hv_status = human_verification.get("status")
        if hv_status != "available":
            return "awaiting_human_verify"
        if human_verification.get("semantics") != "latest_verdict":
            return "awaiting_human_verify"

        all_verified = human_verification.get("all_deferred_must_verified", False)
        if not all_verified:
            # Pending deferred must criteria (including latest-verdict
            # ``fail`` records) remain — still blocked.
            return "awaiting_human_verify"

        # All deferred must criteria have latest ``pass`` records.
        runner_alive = runner.get("status") in ("alive", "connected")
        if runner_alive:
            return "running"
        # Runner dead but verification satisfied — chain is stale and
        # recoverable (supervisor can wake it).
        return "stale_bookkeeping"

    # Running: plan is active and runner shows signs of life
    plan_running = plan_status.get("status") in ("running", "active", "in_progress")
    runner_alive = runner.get("status") in ("alive", "connected")
    if plan_running and runner_alive:
        return "running"
    if plan_running and runner.get("status") == "unknown":
        # plan reports as running but we can't probe runner; give benefit of doubt
        return "running"

    # If there's a current plan but no runner, it might be stalled
    if current_plan and not plan_running:
        if sync.get("sync_state") in ("stale", "dirty"):
            return "stale_bookkeeping"
        # Check for prerequisite block (use effective policy dict).
        if effective.get("prerequisite_policy") == "required":
            return "human_prerequisite"
        if effective.get("validation_policy") == "required":
            return "quality_gate"

    # No current plan and no runner: stale bookkeeping
    if not current_plan and not runner_alive:
        return "stale_bookkeeping"

    # Default: running (we have state but can't confirm otherwise)
    return "running"


def _latest_failure_from_plan_status(plan_status: Mapping[str, Any]) -> dict[str, Any] | None:
    failure = plan_status.get("latest_failure")
    if not isinstance(failure, Mapping):
        nested_state = plan_status.get("state")
        if isinstance(nested_state, Mapping):
            failure = nested_state.get("latest_failure")
    if not isinstance(failure, Mapping):
        return None

    metadata = failure.get("metadata")
    if not isinstance(metadata, Mapping):
        metadata = {}
    message = failure.get("message") or failure.get("reason") or metadata.get("message")
    summary: dict[str, Any] = {
        "kind": failure.get("kind"),
        "message": message,
        "phase": failure.get("phase") or metadata.get("phase"),
        "raw": dict(failure),
    }
    return {key: value for key, value in summary.items() if value is not None}


def _resolve_chain_execution_context(
    spec: CloudSpec,
    chain_state,
    marker: dict[str, Any] | None,
    remote_spec: str,
) -> dict[str, Any]:
    """Resolve workspace, session, and extra_repos for the chain.

    Resolution order:
      - workspace:  chain_state.resolved_workspace > marker.workspace >
                    parent of *remote_spec* (``<workspace>/chain.yaml``) >
                    spec.repo.workspace
      - session:    chain_state.chain_session > marker.chain_session >
                    spec.chain.chain_session > CHAIN_SESSION_NAME
      - extra_repos: combine spec.extra_repos + chain_state.extra_repos +
                     marker.extra_repos (deduplicated, order preserved).

    Returns a dict with ``workspace``, ``chain_session``, ``extra_repos``,
    ``remote_spec``, and ``source`` (which data source provided each field).
    """
    if marker is None:
        marker = {}

    # --- workspace -------------------------------------------------------------
    workspace: str | None = None
    workspace_source: str = "default"

    # 1. chain_state.resolved_workspace
    if getattr(chain_state, "resolved_workspace", None):
        workspace = chain_state.resolved_workspace
        workspace_source = "chain_state"
    # 2. marker.workspace
    elif isinstance(marker.get("workspace"), str) and marker["workspace"].strip():
        workspace = marker["workspace"]
        workspace_source = "marker"
    # 3. parent of remote_spec (shaped like <workspace>/chain.yaml)
    elif "/" in remote_spec:
        parent = str(PurePosixPath(remote_spec).parent)
        if parent and parent != "/" and parent != ".":
            workspace = parent
            workspace_source = "remote_spec"
    # 4. spec.repo.workspace
    if workspace is None:
        workspace = spec.repo.workspace
        workspace_source = "spec"

    # --- chain_session ---------------------------------------------------------
    chain_session: str | None = None
    session_source: str = "default"

    # 1. chain_state.chain_session
    cs = getattr(chain_state, "chain_session", None)
    if isinstance(cs, str) and cs.strip():
        chain_session = cs
        session_source = "chain_state"
    # 2. marker.chain_session
    elif isinstance(marker.get("chain_session"), str) and marker["chain_session"].strip():
        chain_session = marker["chain_session"]
        session_source = "marker"
    # 3. spec.chain.chain_session
    elif spec.chain is not None and spec.chain.chain_session:
        chain_session = spec.chain.chain_session
        session_source = "spec"
    # 4. CHAIN_SESSION_NAME
    if chain_session is None:
        chain_session = CHAIN_SESSION_NAME
        session_source = "default"

    # --- extra_repos -----------------------------------------------------------
    seen: set[str] = set()
    extra_repos: list[str] = []
    extra_repos_sources: list[str] = []

    for source_label, source_list in (
        ("spec", list(spec.extra_repos)),
        ("chain_state", list(getattr(chain_state, "extra_repos", []))),
        ("marker", list(marker.get("extra_repos", [])) if isinstance(marker.get("extra_repos"), list) else []),
    ):
        for repo in source_list:
            if isinstance(repo, str) and repo.strip() and repo not in seen:
                seen.add(repo)
                extra_repos.append(repo)
                extra_repos_sources.append(source_label)

    return {
        "workspace": workspace,
        "chain_session": chain_session,
        "extra_repos": extra_repos,
        "remote_spec": remote_spec,
        "source": {
            "workspace": workspace_source,
            "session": session_source,
            "extra_repos": extra_repos_sources,
        },
    }


def _marker_path_no_create(cloud_yaml_path: Path) -> Path:
    """Return the marker directory path without creating any directories.

    This is intentionally read-only so that status / supervisor reads do not
    require write access to ``~/.megaplan/cloud/markers/``.
    """
    marker_key = hashlib.sha256(str(cloud_yaml_path.resolve()).encode()).hexdigest()[:16]
    return Path.home() / ".megaplan" / "cloud" / "markers" / marker_key


def _load_marker(root: Path, args: argparse.Namespace) -> dict[str, Any] | None:
    """Load the last_chain.json marker if it exists, or None.

    Does NOT create any marker directories — the read path is intentionally
    non-creating so that ``cloud_chain_status_payload`` and supervisor ticks
    work when ``~/.megaplan/cloud/markers/`` is not writable.
    """
    marker_path = _marker_path_no_create(_cloud_yaml_path(root, args)) / "last_chain.json"
    try:
        if not marker_path.exists():
            return None
        return json.loads(marker_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _provider_consistency_check(
    spec: CloudSpec,
    marker: dict[str, Any] | None,
    ctx: dict[str, Any],
) -> dict[str, Any]:
    """Compare provider identity across spec, marker, and resolved context.

    This compares **provider identity** (compose project, host), NOT SSH attach
    session names or chain tmux session names.

    Returns a dict with ``status`` (``consistent``, ``mismatch``,
    ``unknown``, or ``not_applicable``) and metadata about each source.
    """
    provider_name = spec.provider
    if provider_name in ("local", "ssh"):
        return {
            "status": "not_applicable",
            "reason": f"provider {provider_name!r} has no comparable provider identity",
            "spec_provider": provider_name,
        }

    return {
        "status": "unknown",
        "reason": f"no consistency check defined for provider {provider_name!r}",
        "spec_provider": provider_name,
    }


def _remote_human_verification_status_command(
    workspace: str, plan_name: str
) -> str:
    """Build a shell command that runs ``verify-human --list --json`` inside
    the resolved workspace.
    """
    return (
        f"cd {shlex.quote(workspace)} && "
        f"MEGAPLAN_TRUSTED_CONTAINER=1 python -m arnold_pipelines.megaplan verify-human --list "
        f"--plan {shlex.quote(plan_name)} --json"
    )


def _remote_human_verification_status(
    provider,
    resolved_workspace: str,
    chain_state,
) -> dict[str, Any]:
    """Fetch remote human-verification status via ``verify-human --list --json``.

    Validates that the remote payload declares ``semantics: latest_verdict``.
    If missing or different, facts are classified as ``unavailable``/``stale``.
    Providers without ``ssh_exec`` return ``{status: 'unavailable'}``.
    """
    current_plan = getattr(chain_state, "current_plan_name", None)
    if not current_plan:
        return {"status": "unavailable", "reason": "no current plan"}

    ssh_meth = getattr(provider, "ssh_exec", None)
    if ssh_meth is None:
        return {
            "status": "unavailable",
            "reason": "provider does not implement ssh_exec",
        }

    try:
        cmd = _remote_human_verification_status_command(
            resolved_workspace, current_plan
        )
        result = ssh_meth(cmd)
        stdout = (result.stdout or "").strip()
        if not stdout:
            return {"status": "unavailable", "reason": "empty stdout"}
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return {"status": "unavailable", "reason": f"invalid JSON: {exc}"}
    except Exception as exc:
        return {"status": "unavailable", "reason": str(exc)}

    # Validate semantics marker.
    semantics = payload.get("semantics")
    if semantics != "latest_verdict":
        return {
            "status": "unavailable",
            "reason": (
                f"remote payload semantics {semantics!r} != 'latest_verdict'; "
                "facts may be stale"
            ),
            "raw_semantics": semantics,
        }

    return {
        "status": "available",
        "pending": payload.get("pending", 0),
        "verified": payload.get("verified", 0),
        "all_deferred_must_verified": payload.get("all_deferred_must_verified", False),
        "rows": payload.get("rows", []),
        "semantics": semantics,
    }


def _marker_evidence(marker: dict[str, Any] | None, *, local_marker_path: Path) -> dict[str, Any]:
    if marker is None:
        return {"status": "missing", "path": str(local_marker_path)}
    return {
        "status": "present",
        "path": str(local_marker_path),
        "workspace": marker.get("workspace") if isinstance(marker.get("workspace"), str) else "",
        "remote_spec": marker.get("remote_spec") if isinstance(marker.get("remote_spec"), str) else "",
        "chain_session": marker.get("chain_session") if isinstance(marker.get("chain_session"), str) else "",
    }


def _active_step_evidence_from_plan_status(plan_status: Mapping[str, Any]) -> dict[str, Any]:
    active_step = plan_status.get("active_step")
    if not isinstance(active_step, Mapping) or not active_step:
        return {"status": "absent"}
    return {
        "status": "present",
        "phase": active_step.get("phase") or active_step.get("step") or "",
        "name": active_step.get("name") or "",
        "attempt": active_step.get("attempt"),
        "worker_pid": active_step.get("worker_pid"),
        "last_activity_at": active_step.get("last_activity_at") or "",
        "configured_specs": active_step.get("configured_specs") or [],
        "attempted_specs": active_step.get("attempted_specs") or [],
        "selected_spec_index": active_step.get("selected_spec_index", 0),
        "selected_spec_total": active_step.get("selected_spec_total", 0),
        "fallback_trigger": active_step.get("fallback_trigger"),
        "failed_attempt_reasons": active_step.get("failed_attempt_reasons") or [],
    }


def cloud_chain_status_payload(root: Path, args: argparse.Namespace, spec: CloudSpec, provider) -> dict[str, Any]:
    """Return the same payload printed by `arnold cloud status --chain`."""
    from arnold_pipelines.megaplan import chain as chain_module
    from arnold_pipelines.megaplan.cloud.current_target import resolve_current_target
    from arnold_pipelines.megaplan.cloud.repair_contract import (
        CUSTODY_BUCKET_BROKEN_SUPERFIXER,
        CUSTODY_BUCKET_REPAIRABLE_NOT_REPAIRING,
        CUSTODY_BUCKET_REPAIRING,
        project_repair_custody,
    )
    from arnold_pipelines.megaplan.run_state.resolver import resolve_run_state

    remote_spec = _resolve_remote_chain_spec(root, args, spec)
    marker = _load_marker(root, args)
    state_path = chain_module._state_path_for(Path(remote_spec))
    try:
        chain_state = chain_module.ChainState.from_dict(json.loads(provider.read_remote_file(str(state_path))))
    except json.JSONDecodeError as exc:
        raise CliError("provider_failed", f"Remote chain state was not valid JSON: {exc}") from exc

    with NamedTemporaryFile("w", suffix=".yaml", encoding="utf-8", delete=False) as handle:
        handle.write(provider.read_remote_file(remote_spec))
        temp_spec = Path(handle.name)
    try:
        chain_spec = chain_module.load_spec(temp_spec)
    finally:
        temp_spec.unlink(missing_ok=True)

    # Resolve execution context (workspace, session, extra_repos).
    ctx = _resolve_chain_execution_context(spec, chain_state, marker, remote_spec)
    resolved_workspace: str = ctx["workspace"]
    resolved_session: str = ctx["chain_session"]

    summary = chain_module.format_chain_status(chain_spec, chain_state)

    # Build additive sections alongside the existing top-level keys.
    # Runtime policy (effective, merging any overrides).
    try:
        runtime_path = chain_module._runtime_policy_path_for(Path(remote_spec))
        runtime_raw = provider.read_remote_file(str(runtime_path))
        runtime_overrides = json.loads(runtime_raw) if runtime_raw else {}
    except Exception:
        runtime_overrides = {}
    effective = chain_module.effective_chain_policy(chain_spec, runtime_overrides)
    policy: dict[str, Any] = effective

    # Sync state from chain state fields.
    sync: dict[str, Any] = {
        "branch_head": chain_state.branch_head,
        "pr_head": chain_state.pr_head,
        "last_pushed_commit": chain_state.last_pushed_commit,
        "dirty_flag": chain_state.dirty_flag,
        "sync_state": chain_state.sync_state,
    }

    # Plan status via provider.status_payload when a current plan exists.
    plan_status: dict[str, Any]
    if chain_state.current_plan_name:
        plan_status = _try_provider_method(
            provider,
            "status_payload",
            plan=chain_state.current_plan_name,
            workspace=resolved_workspace,
        )
    else:
        plan_status = {"status": "missing", "reason": "no current plan"}
    latest_failure = _latest_failure_from_plan_status(plan_status)

    # Runner / heartbeat info via optional ssh_exec probe. Prefer explicit tmux
    # liveness but fall back to matching chain process evidence because tmux can
    # disappear while the chain runner and its child worker remain alive.
    tmux_evidence: dict[str, Any] = {"status": "unavailable", "reason": "runner probe not implemented"}
    process_evidence: dict[str, Any] = {"status": "unavailable", "reason": "runner probe not implemented"}
    runner: dict[str, Any] = {"status": "unavailable", "reason": "runner probe not implemented"}
    try:
        ssh_meth = getattr(provider, "ssh_exec", None)
        if ssh_meth is not None:
            session_esc = shlex.quote(resolved_session)
            spec_esc = shlex.quote(remote_spec)
            proc = ssh_meth(
                "if tmux has-session -t "
                + session_esc
                + " 2>/dev/null; then echo tmux_alive; "
                + "elif ps -eww -o args= | grep -E "
                + shlex.quote("[p]ython[0-9.]*([[:space:]]+-P)?[[:space:]]+-m arnold_pipelines.megaplan (chain|epic-chain) start")
                + " | grep -F -- '--spec' | grep -Fq -- "
                + spec_esc
                + "; then echo process_alive; "
                + "else echo dead; fi"
            )
            stdout = proc.stdout or ""
            if proc.returncode == 0 and "tmux_alive" in stdout:
                tmux_evidence = {"status": "alive", "session": resolved_session}
                process_evidence = {"status": "unknown", "remote_spec": remote_spec}
                runner = {
                    "status": "alive",
                    "session": resolved_session,
                    "detail": "tmux session present",
                    "tmux_status": tmux_evidence["status"],
                    "process_status": process_evidence["status"],
                }
            elif proc.returncode == 0 and "process_alive" in stdout:
                tmux_evidence = {"status": "missing", "session": resolved_session}
                process_evidence = {"status": "alive", "remote_spec": remote_spec}
                runner = {
                    "status": "alive",
                    "session": resolved_session,
                    "detail": "matching chain process present; tmux session absent",
                    "tmux_status": tmux_evidence["status"],
                    "process_status": process_evidence["status"],
                }
            else:
                tmux_evidence = {"status": "missing", "session": resolved_session}
                process_evidence = {"status": "dead", "remote_spec": remote_spec}
                runner = {
                    "status": "dead",
                    "session": resolved_session,
                    "detail": "tmux session absent and no matching chain process",
                    "tmux_status": tmux_evidence["status"],
                    "process_status": process_evidence["status"],
                }
    except Exception as exc:
        tmux_evidence = {"status": "unknown", "reason": str(exc), "session": resolved_session}
        process_evidence = {"status": "unknown", "reason": str(exc), "remote_spec": remote_spec}
        runner = {"status": "unknown", "reason": str(exc)}

    # Log paths (structured from the resolved workspace).
    chain_log_name = (
        f"cloud-chain-{resolved_session}.log"
        if resolved_session != CHAIN_SESSION_NAME
        else "cloud-chain.log"
    )
    chain_log_path = (PurePosixPath(resolved_workspace) / ".megaplan" / chain_log_name).as_posix()
    chain_log_info: dict[str, Any] = {"path": chain_log_path}
    try:
        ssh_meth = getattr(provider, "ssh_exec", None)
        if ssh_meth is not None:
            stat_proc = ssh_meth(
                "stat -c '%Y %s' "
                + shlex.quote(chain_log_path)
                + " 2>/dev/null || echo unavailable"
            )
            stat_out = (stat_proc.stdout or "").strip()
            if stat_out and stat_out != "unavailable":
                parts = stat_out.split()
                if len(parts) >= 2:
                    chain_log_info["mtime"] = int(parts[0]) if parts[0].lstrip("-").isdigit() else parts[0]
                    chain_log_info["size"] = int(parts[1]) if parts[1].isdigit() else parts[1]
            else:
                chain_log_info["status"] = "unavailable"
        else:
            chain_log_info["status"] = "unavailable"
            chain_log_info["reason"] = "provider does not implement ssh_exec"
    except Exception as exc:
        chain_log_info["status"] = "unavailable"
        chain_log_info["reason"] = str(exc)
    logs: dict[str, Any] = {
        "workspace": resolved_workspace,
        "plan_log": (PurePosixPath(resolved_workspace) / ".megaplan" / "logs" / "latest.log").as_posix()
        if chain_state.current_plan_name
        else None,
        "agent_log": (PurePosixPath(resolved_workspace) / "agent.log").as_posix(),
        "chain_log": chain_log_info,
    }

    # PR state.
    pr: dict[str, Any] = {}
    if chain_state.pr_number is not None:
        pr["pr_number"] = chain_state.pr_number
        pr["pr_state"] = chain_state.pr_state
        if chain_state.pr_head:
            pr["pr_head"] = chain_state.pr_head
    else:
        pr = {"status": "none"}

    # Provider / session consistency check (read-only).
    provider_consistency = _provider_consistency_check(spec, marker, ctx)

    # Human-verification status via explicit remote command (T11).
    # Probing here means ``cloud_chain_status_payload`` is self-contained
    # and the supervisor tick's (c2) section only needs to refresh when the
    # effective status is human-verification-related.
    human_verification: dict[str, Any] = _remote_human_verification_status(
        provider, resolved_workspace, chain_state,
    )
    marker_evidence = _marker_evidence(
        marker,
        local_marker_path=_marker_path_no_create(_cloud_yaml_path(root, args)) / "last_chain.json",
    )
    active_step_evidence = _active_step_evidence_from_plan_status(plan_status)
    repair_custody: dict[str, Any] = {"status": "unavailable", "reason": "local custody evidence unavailable"}
    local_workspace = Path(resolved_workspace)
    marker_dir = local_workspace / ".megaplan" / "cloud-sessions"
    queue_root = local_workspace / ".megaplan" / "repair-queue"
    repair_data_dir = marker_dir / "repair-data"
    if local_workspace.exists():
        try:
            current_target = resolve_current_target(
                resolved_session,
                marker_dir=marker_dir,
                repair_data_dir=repair_data_dir,
            )
            canonical_run_state = resolve_run_state(current_target)
            projection = project_repair_custody(
                plan_state=plan_status,
                current_target=current_target,
                canonical_run_state=canonical_run_state,
                queue_root=queue_root,
                repair_data_dir=repair_data_dir,
            )
            bucket = projection["custody_bucket"]
            if bucket in {
                CUSTODY_BUCKET_REPAIRING,
                CUSTODY_BUCKET_REPAIRABLE_NOT_REPAIRING,
                CUSTODY_BUCKET_BROKEN_SUPERFIXER,
            }:
                repair_custody = {
                    "status": "available",
                    "bucket": bucket,
                    "blocker_id": projection["blocker_id"],
                    "active_request_ids": projection["active_request_ids"],
                }
        except Exception as exc:
            repair_custody = {"status": "invalid", "reason": str(exc)}

    # Classify effective status.
    effective_status = _classify_effective_status(
        chain_state, effective, len(chain_spec.milestones), plan_status, runner, pr, sync,
        human_verification=human_verification,
    )

    return {
        "success": True,
        "spec": remote_spec,
        "milestone_count": len(chain_spec.milestones),
        "seed_plan": chain_spec.seed_plan,
        "chain_state": chain_state.to_dict(),
        "summary": summary,
        "effective_status": effective_status,
        "policy": policy,
        "sync": sync,
        "plan_status": plan_status,
        "latest_failure": latest_failure,
        "runner": runner,
        "marker_evidence": marker_evidence,
        "tmux_evidence": tmux_evidence,
        "process_evidence": process_evidence,
        "active_step_evidence": active_step_evidence,
        "repair_custody": repair_custody,
        "logs": logs,
        "pr": pr,
        "provider_consistency": provider_consistency,
        "human_verification": human_verification,
        "resolved_workspace": resolved_workspace,
        "resolved_session": resolved_session,
        "resolved_context": ctx,
    }


def _materialized_deploy_dir(spec: CloudSpec):
    class _DeployDirContext:
        def __enter__(self_inner) -> Path:
            path = _persistent_deploy_dir(spec)
            materialize_deploy_dir(spec, path)
            return path

        def __exit__(self_inner, exc_type, exc, tb) -> None:
            return None

    return _DeployDirContext()


def _cloud_cache_root() -> Path:
    root = Path.home() / ".megaplan" / "cloud"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _persistent_deploy_dir(spec: CloudSpec) -> Path:
    root = _cloud_cache_root()
    if spec.provider == "local":
        compose_project = spec.local.compose_project if spec.local is not None else "megaplan-cloud"
        path = root / compose_project
    elif spec.provider == "ssh":
        host = spec.ssh.host if spec.ssh is not None else "unknown-host"
        path = root / f"ssh-{host}"
    else:
        raise CliError("invalid_spec", f"provider {spec.provider!r} does not use a persistent deploy dir")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _marker_dir(cloud_yaml_path: Path) -> Path:
    marker_key = hashlib.sha256(str(cloud_yaml_path.resolve()).encode()).hexdigest()[:16]
    path = _cloud_cache_root() / "markers" / marker_key
    path.mkdir(parents=True, exist_ok=True)
    return path


def _clear_persistent_deploy_dir(spec: CloudSpec) -> None:
    deploy_dir = _persistent_deploy_dir(spec)
    if deploy_dir.exists():
        shutil.rmtree(deploy_dir)


def _confirm_destroy(spec: CloudSpec) -> bool:
    volume = spec.resources.volume or "<no volume>"
    response = input(
        f"Destroy cloud deployment and delete volume {volume!r}? [y/N]: "
    ).strip().lower()
    return response in {"y", "yes"}


def _relay_output(
    result,
    *,
    secret_names: list[str] | tuple[str, ...] = (),
    env: dict[str, str] | None = None,
) -> None:
    _write_redacted_output(result, secret_names=secret_names, env=env)


def _emit_error(error: CliError) -> int:
    payload = {"success": False, "error": error.code, "message": error.message}
    payload.update(error.extra)
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    return error.exit_code or 1
