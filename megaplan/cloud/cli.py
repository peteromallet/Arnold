"""CLI entrypoints for megaplan cloud commands."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import sys
from datetime import datetime, timezone
from dataclasses import replace
from importlib import resources
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any

from megaplan.cloud.providers.base import _write_redacted_output, get_provider
from megaplan.cloud.spec import CloudSpec, RailwaySpec, load_spec as load_cloud_spec
from megaplan.cloud.template import materialize_deploy_dir
from megaplan.types import CliError


load_spec = load_cloud_spec


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

    chain_parser = cloud_sub.add_parser(
        "chain",
        parents=[shared],
        help="Upload a chain spec and start it remotely",
    )
    chain_parser.add_argument("spec", help="Local chain spec path")
    chain_parser.add_argument(
        "--idea-dir",
        default=None,
        help="Directory containing local idea files referenced by the chain spec",
    )

    bootstrap_parser = cloud_sub.add_parser(
        "bootstrap",
        parents=[shared],
        help="Upload an idea file and start megaplan init remotely",
    )
    bootstrap_parser.add_argument("idea_file", help="Local idea file path")
    bootstrap_parser.add_argument("--plan-name", default=None, help="Optional remote plan name")
    bootstrap_parser.add_argument("--robustness", default="standard")

    status_parser = cloud_sub.add_parser(
        "status",
        parents=[shared],
        help="Fetch remote `megaplan status` JSON",
    )
    status_parser.add_argument(
        "--chain",
        action="store_true",
        help="Fetch remote chain_state.json and render core chain status",
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

    cloud_sub.add_parser("down", parents=[shared], help="Pause the deployment without deleting volume")

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
        help="Manage provider-backed megaplan cloud runners",
    )
    _register_cloud_subcommands(cloud_parser)


def run_cloud_cli(root: Path, args: argparse.Namespace) -> int:
    try:
        action = getattr(args, "cloud_action")
        if action == "init":
            return _run_init(root, args)

        spec = _load_cloud_spec(root, args)
        provider = _provider_for_action(spec, args)

        if action == "chain":
            with _materialized_deploy_dir(spec):
                return _run_chain_wrapper(root, args, spec, provider)

        if action == "bootstrap":
            with _materialized_deploy_dir(spec):
                return _run_bootstrap_wrapper(args, spec, provider)

        if action == "build":
            with _materialized_deploy_dir(spec) as deploy_dir:
                return provider.build(deploy_dir)

        if action == "deploy":
            secrets = {name: os.environ.get(name, "") for name in spec.secrets}
            with _materialized_deploy_dir(spec) as deploy_dir:
                return provider.deploy(deploy_dir, secrets=secrets)

        if action == "status":
            if bool(getattr(args, "chain", False)):
                return _run_chain_status(root, args, spec, provider)
            payload = provider.status_payload(
                plan=getattr(args, "plan", None),
                workspace=spec.repo.workspace,
            )
            sys.stdout.write(json.dumps(payload, indent=2) + "\n")
            return 0

        if action == "attach":
            return provider.attach()

        if action == "logs":
            return provider.logs(follow=not bool(getattr(args, "no_follow", False)))

        if action == "exec":
            result = provider.ssh_exec(args.command)
            _relay_output(result, secret_names=spec.secrets, env=os.environ)
            return 0

        if action == "resume":
            payload = provider.status_payload(
                plan=getattr(args, "plan", None),
                workspace=spec.repo.workspace,
            )
            next_step = payload.get("next_step")
            if not isinstance(next_step, str) or not next_step:
                raise CliError("invalid_status", "Remote status did not include a next_step")
            from megaplan.auto import _phase_command

            argv = list(_phase_command(next_step))
            if getattr(args, "plan", None):
                argv.extend(["--plan", args.plan])
            command = f"cd {shlex.quote(spec.repo.workspace)} && megaplan {shlex.join(argv)}"
            result = provider.ssh_exec(command)
            _relay_output(result, secret_names=spec.secrets, env=os.environ)
            return 0

        if action == "down":
            return provider.down()

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
    return load_spec(_cloud_yaml_path(root, args))


def _provider_for_action(spec: CloudSpec, args: argparse.Namespace):
    # Gate session overrides on provider capability, not on a provider-name special case.
    base_provider = get_provider(spec.provider, spec)
    session_name = getattr(args, "session", None)
    if not session_name:
        return base_provider
    supports_session = base_provider.supports_session
    if not supports_session:
        raise CliError("invalid_args", "--session is only supported for provider: railway")
    railway = spec.railway or RailwaySpec()
    overridden = replace(spec, railway=replace(railway, session=session_name))
    return get_provider(overridden.provider, overridden)


def _run_init(root: Path, args: argparse.Namespace) -> int:
    target = _cloud_yaml_path(root, args)
    if target.exists() and not bool(getattr(args, "force", False)):
        raise CliError(
            "invalid_args",
            f"cloud spec already exists: {target}. Use --force to overwrite.",
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    template = resources.files("megaplan.cloud.templates").joinpath("cloud.yaml.tmpl")
    target.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    sys.stdout.write(json.dumps({"success": True, "cloud_yaml": str(target)}, indent=2) + "\n")
    return 0


def _resolve_local_idea_source(*, idea_dir: Path, workspace: str, remote_path: str) -> Path:
    remote = PurePosixPath(remote_path)
    workspace_path = PurePosixPath(workspace)
    if remote == workspace_path:
        tail = Path()
    elif str(remote).startswith(f"{workspace_path}/"):
        tail = Path(*remote.relative_to(workspace_path).parts)
    elif remote.is_absolute():
        tail = Path(remote.name)
    else:
        tail = Path(*remote.parts)
    return idea_dir / tail


def _run_chain_wrapper(root: Path, args: argparse.Namespace, spec: CloudSpec, provider) -> int:
    from megaplan import chain as chain_module

    local_spec_path = Path(args.spec).expanduser().resolve()
    chain_spec = chain_module.load_spec(local_spec_path)
    idea_dir = Path(args.idea_dir).expanduser().resolve() if args.idea_dir else local_spec_path.parent.resolve()
    remote_spec_path = str(PurePosixPath(spec.repo.workspace) / "chain.yaml")

    for milestone in chain_spec.milestones:
        local_source = _resolve_local_idea_source(
            idea_dir=idea_dir,
            workspace=spec.repo.workspace,
            remote_path=milestone.idea,
        )
        if not local_source.exists():
            raise CliError(
                "missing_idea_file",
                f"milestone '{milestone.label}' idea not found on disk at {local_source}. Use --idea-dir to point at the directory containing ideas.",
            )
        provider.upload_file(local_source, milestone.idea)

    provider.upload_file(local_spec_path, remote_spec_path)
    chain_command = (
        f"megaplan chain start --spec {shlex.quote(remote_spec_path)} "
        ">> .megaplan/cloud-chain.log 2>&1"
    )
    result = provider.ssh_exec(
        " && ".join(
            [
                f"mkdir -p {shlex.quote(str(PurePosixPath(spec.repo.workspace) / '.megaplan'))}",
                (
                    "if tmux has-session -t megaplan-chain 2>/dev/null; then "
                    "echo 'megaplan-chain session already running'; "
                    "else "
                    f"tmux new-session -d -s megaplan-chain -c {shlex.quote(spec.repo.workspace)} {shlex.quote(chain_command)}; "
                    "echo 'started megaplan-chain session'; "
                    "fi"
                ),
            ]
        )
    )
    _relay_output(result, secret_names=spec.secrets, env=os.environ)

    marker_path = _marker_dir(_cloud_yaml_path(root, args)) / "last_chain.json"
    marker_path.write_text(
        json.dumps(
            {
                "remote_spec": remote_spec_path,
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


def _run_bootstrap_wrapper(args: argparse.Namespace, spec: CloudSpec, provider) -> int:
    local_idea_path = Path(args.idea_file).expanduser().resolve()
    if not local_idea_path.exists():
        raise CliError("missing_idea_file", f"idea file not found: {local_idea_path}")
    remote_idea_path = str(PurePosixPath(spec.repo.workspace) / "idea.txt")
    provider.upload_file(local_idea_path, remote_idea_path)

    command = (
        f"cd {shlex.quote(spec.repo.workspace)} && "
        f"megaplan init --project-dir {shlex.quote(spec.repo.workspace)} "
        f"--idea-file {shlex.quote(remote_idea_path)} --auto-start "
        f"--robustness {shlex.quote(args.robustness)}"
    )
    if args.plan_name:
        command += f" --name {shlex.quote(args.plan_name)}"
    result = provider.ssh_exec(command)
    _relay_output(result, secret_names=spec.secrets, env=os.environ)
    return 0


def _resolve_remote_chain_spec(root: Path, args: argparse.Namespace, spec: CloudSpec) -> str:
    explicit = getattr(args, "remote_spec", None)
    if explicit:
        return explicit

    marker_path = _marker_dir(_cloud_yaml_path(root, args)) / "last_chain.json"
    if marker_path.exists():
        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            marker = {}
        remote_spec = marker.get("remote_spec")
        if isinstance(remote_spec, str) and remote_spec:
            return remote_spec

    if spec.mode == "chain" and spec.chain is not None:
        return spec.chain.spec

    raise CliError(
        "missing_remote_spec",
        "Unable to locate remote chain spec. Pass --remote-spec <path>, run `cloud chain <spec>` first, or set mode: chain in cloud.yaml.",
    )


def _run_chain_status(root: Path, args: argparse.Namespace, spec: CloudSpec, provider) -> int:
    from megaplan import chain as chain_module

    remote_spec = _resolve_remote_chain_spec(root, args, spec)
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

    summary = chain_module.format_chain_status(chain_spec, chain_state)
    chain_module._write_chain_status_pretty(summary, writer=sys.stderr.write)
    payload = {
        "success": True,
        "spec": remote_spec,
        "milestone_count": len(chain_spec.milestones),
        "seed_plan": chain_spec.seed_plan,
        "chain_state": chain_state.to_dict(),
        "summary": summary,
    }
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    return 0


def _materialized_deploy_dir(spec: CloudSpec):
    class _DeployDirContext:
        def __enter__(self_inner) -> Path:
            self_inner._tmpdir = None
            if spec.provider == "railway":
                self_inner._tmpdir = TemporaryDirectory(prefix="megaplan-cloud-")
                path = Path(self_inner._tmpdir.name)
            else:
                path = _persistent_deploy_dir(spec)
            materialize_deploy_dir(spec, path)
            return path

        def __exit__(self_inner, exc_type, exc, tb) -> None:
            if self_inner._tmpdir is not None:
                self_inner._tmpdir.cleanup()

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
    if spec.provider == "railway":
        return
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
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    return error.exit_code or 1
