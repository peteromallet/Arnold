"""CLI entrypoints for megaplan cloud commands."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from dataclasses import replace
from importlib import resources
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from megaplan.cloud.providers.base import get_provider
from megaplan.cloud.spec import CloudSpec, RailwaySpec, load_spec
from megaplan.cloud.template import materialize_deploy_dir
from megaplan.types import CliError


def build_cloud_parser(subparsers: Any) -> None:
    cloud_parser = subparsers.add_parser(
        "cloud",
        help="Manage provider-backed megaplan cloud runners",
    )
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

    status_parser = cloud_sub.add_parser(
        "status",
        parents=[shared],
        help="Fetch remote `megaplan status` JSON",
    )
    status_parser.add_argument("--plan", help="Optional plan name to query remotely")

    attach_parser = cloud_sub.add_parser(
        "attach",
        parents=[shared],
        help="Attach to the remote tmux session",
    )
    attach_parser.add_argument("--session", help="Override the Railway tmux session name")

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


def run_cloud_cli(root: Path, args: argparse.Namespace) -> int:
    try:
        action = getattr(args, "cloud_action")
        if action == "init":
            return _run_init(root, args)

        spec = _load_cloud_spec(root, args)
        provider = _provider_for_action(spec, args)

        if action == "build":
            with _materialized_deploy_dir(spec) as deploy_dir:
                return provider.build(deploy_dir)

        if action == "deploy":
            secrets = {name: os.environ.get(name, "") for name in spec.secrets}
            with _materialized_deploy_dir(spec) as deploy_dir:
                return provider.deploy(deploy_dir, secrets=secrets)

        if action == "status":
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
            _relay_output(result)
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
            _relay_output(result)
            return 0

        if action == "down":
            return provider.down()

        if action == "destroy":
            if not bool(getattr(args, "yes", False)) and not _confirm_destroy(spec):
                return 1
            return provider.destroy(volume=spec.resources.volume)

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
    session = getattr(args, "session", None)
    if not session:
        return get_provider(spec.provider, spec)
    railway = spec.railway or RailwaySpec()
    overridden = replace(spec, railway=replace(railway, session=session))
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


def _materialized_deploy_dir(spec: CloudSpec):
    class _DeployDirContext:
        def __enter__(self_inner) -> Path:
            self_inner._tmpdir = TemporaryDirectory(prefix="megaplan-cloud-")
            path = Path(self_inner._tmpdir.name)
            materialize_deploy_dir(spec, path)
            return path

        def __exit__(self_inner, exc_type, exc, tb) -> None:
            self_inner._tmpdir.cleanup()

    return _DeployDirContext()


def _confirm_destroy(spec: CloudSpec) -> bool:
    volume = spec.resources.volume or "<no volume>"
    response = input(
        f"Destroy cloud deployment and delete volume {volume!r}? [y/N]: "
    ).strip().lower()
    return response in {"y", "yes"}


def _relay_output(result) -> None:
    if getattr(result, "stdout", ""):
        sys.stdout.write(result.stdout)
    if getattr(result, "stderr", ""):
        sys.stderr.write(result.stderr)


def _emit_error(error: CliError) -> int:
    payload = {"success": False, "error": error.code, "message": error.message}
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    return error.exit_code or 1
