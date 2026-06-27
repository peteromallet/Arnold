#!/usr/bin/env python3
"""Hot-upload runtime files to an SSH-backed Megaplan cloud container.

This is an operator convenience for wrapper/entrypoint/env hotfixes. It does
not rebuild the Docker image and intentionally dry-runs unless --apply is set.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from arnold_pipelines.megaplan.cloud.spec import CloudSpec, SshSpec, load_spec


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLOUD_YAML = REPO_ROOT / ".megaplan-worktrees/workflow-manifest-runtime/cloud.yaml"
FALLBACK_CLOUD_YAML = REPO_ROOT / "cloud.yaml"
WRAPPER_DIR = REPO_ROOT / "arnold_pipelines/megaplan/cloud/wrappers"
REMOTE_BIN_DIR = "/usr/local/bin"

KNOWN_SESSION_COMMANDS = {
    "watchdog": "/usr/local/bin/arnold-watchdog",
    "heartbeat": "/usr/local/bin/arnold-heartbeat",
}


@dataclass(frozen=True)
class Upload:
    src: Path
    dest: str
    mode: str | None = None
    sensitive: bool = False
    host: bool = False


class HotUploadError(RuntimeError):
    pass


class Remote:
    def __init__(self, ssh: SshSpec, *, apply: bool) -> None:
        self.ssh = ssh
        self.apply = apply
        self.ssh_binary = shutil.which("ssh") or "ssh"

    @property
    def target(self) -> str:
        if self.ssh.user:
            return f"{self.ssh.user}@{self.ssh.host}"
        return self.ssh.host

    def argv(self, command: str) -> list[str]:
        argv = [self.ssh_binary, "-p", str(self.ssh.port)]
        if self.ssh.identity_file:
            argv.extend(["-i", self.ssh.identity_file])
        argv.extend([self.target, command])
        return argv

    def run(
        self,
        command: str,
        *,
        input_text: str | None = None,
        sensitive: bool = False,
    ) -> subprocess.CompletedProcess[str] | None:
        rendered = f"ssh -p {self.ssh.port} {self.target} {shlex.quote(command)}"
        if not self.apply:
            suffix = " <redacted-stdin>" if sensitive and input_text is not None else ""
            print(f"[dry-run] {rendered}{suffix}")
            return None
        try:
            result = subprocess.run(
                self.argv(command),
                input=input_text,
                text=True,
                capture_output=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise HotUploadError(f"ssh executable not found: {exc}") from exc
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise HotUploadError(stderr or f"remote command failed: {command}")
        return result

    def docker_exec(
        self,
        command: str,
        *,
        input_text: str | None = None,
        sensitive: bool = False,
    ) -> subprocess.CompletedProcess[str] | None:
        quoted = shlex.quote(command)
        return self.run(
            f"docker exec -i {shlex.quote(self.ssh.container)} bash -lc {quoted}",
            input_text=input_text,
            sensitive=sensitive,
        )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Hot-upload files to an SSH Megaplan cloud container.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        allow_abbrev=False,
    )
    parser.add_argument(
        "--cloud-yaml",
        type=Path,
        default=DEFAULT_CLOUD_YAML if DEFAULT_CLOUD_YAML.exists() else FALLBACK_CLOUD_YAML,
        help="Cloud spec to read SSH host/container settings from.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform mutations. Without this, commands are printed only.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify uploaded/requested files and print container status. This is the default.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Do not upload; verify requested remote files and print tmux sessions.",
    )
    parser.add_argument(
        "--wrapper",
        action="append",
        default=[],
        help="Wrapper name under arnold_pipelines/megaplan/cloud/wrappers to upload.",
    )
    parser.add_argument(
        "--all-wrappers",
        action="store_true",
        help="Upload every executable-style wrapper in the cloud wrappers directory.",
    )
    parser.add_argument(
        "--upload",
        action="append",
        default=[],
        metavar="LOCAL:REMOTE",
        help="Upload an explicit local file to an absolute path inside the container.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help=(
            "Replace the host-side Docker env file with this local file. "
            "Requires --recreate-container to affect process env."
        ),
    )
    parser.add_argument(
        "--env-name",
        action="append",
        default=[],
        help=(
            "Append one local environment variable to /workspace/.cloud-hot-env "
            "inside the container for tmux-session restarts. Repeatable."
        ),
    )
    parser.add_argument(
        "--recreate-container",
        action="store_true",
        help="Recreate the container from the existing image, volumes, ports, and env file.",
    )
    parser.add_argument(
        "--restart-session",
        action="append",
        default=[],
        help="Kill and restart a tmux session after upload. Known: watchdog, heartbeat.",
    )
    parser.add_argument(
        "--session-command",
        action="append",
        default=[],
        metavar="SESSION=COMMAND",
        help="Command to use when --restart-session names a custom session.",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip sha256/stat verification after uploads.",
    )
    return parser.parse_args(argv)


def load_ssh_spec(path: Path) -> CloudSpec:
    spec = load_spec(path)
    if spec.provider != "ssh" or spec.ssh is None:
        raise HotUploadError(f"{path} must use provider: ssh")
    return spec


def parse_upload(raw: str) -> Upload:
    if ":" not in raw:
        raise HotUploadError(f"--upload must be LOCAL:REMOTE, got {raw!r}")
    local, remote = raw.split(":", 1)
    src = Path(local).expanduser()
    if not remote.startswith("/"):
        raise HotUploadError(f"remote upload destination must be absolute: {remote!r}")
    return Upload(src=src, dest=remote, mode="755")


def wrapper_uploads(args: argparse.Namespace) -> list[Upload]:
    names = list(args.wrapper)
    if args.all_wrappers:
        names.extend(
            path.name
            for path in sorted(WRAPPER_DIR.iterdir())
            if path.is_file() and not path.name.startswith("__")
        )
    uploads = []
    for name in dict.fromkeys(names):
        if "/" in name or name in {"", ".", ".."}:
            raise HotUploadError(f"invalid wrapper name: {name!r}")
        src = WRAPPER_DIR / name
        uploads.append(Upload(src=src, dest=f"{REMOTE_BIN_DIR}/{name}", mode="755"))
    return uploads


def collect_uploads(args: argparse.Namespace, spec: CloudSpec) -> list[Upload]:
    uploads = wrapper_uploads(args)
    uploads.extend(parse_upload(raw) for raw in args.upload)
    if args.env_file:
        uploads.append(
            Upload(
                src=args.env_file.expanduser(),
                dest=f"{spec.ssh.remote_dir}/.env",  # type: ignore[union-attr]
                mode="600",
                sensitive=True,
                host=True,
            )
        )
    for upload in uploads:
        if not upload.src.exists() or not upload.src.is_file():
            raise HotUploadError(f"local file not found: {upload.src}")
    return uploads


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def upload_file(remote: Remote, upload: Upload) -> None:
    payload = base64.b64encode(upload.src.read_bytes()).decode("ascii")
    parent = str(Path(upload.dest).parent)
    command = f"mkdir -p {shlex.quote(parent)} && base64 -d > {shlex.quote(upload.dest)}"
    if upload.mode:
        command += f" && chmod {shlex.quote(upload.mode)} {shlex.quote(upload.dest)}"
    if upload.host:
        remote.run(command, input_text=payload, sensitive=upload.sensitive)
    else:
        remote.docker_exec(command, input_text=payload, sensitive=upload.sensitive)
    verb = "uploaded" if remote.apply else "[dry-run] would upload"
    print(f"{verb} {upload.src} -> {upload.dest}")


def upload_env_names(remote: Remote, names: list[str]) -> None:
    if not names:
        return
    lines = []
    for name in dict.fromkeys(names):
        if not name.replace("_", "").isalnum() or ((not name[0].isalpha()) and name[0] != "_"):
            raise HotUploadError(f"invalid environment variable name: {name!r}")
        if name not in os.environ:
            raise HotUploadError(f"environment variable is not set locally: {name}")
        lines.append(f"export {name}={shlex.quote(os.environ[name])}")
    payload = "\n".join(lines) + "\n"
    encoded = base64.b64encode(payload.encode("utf-8")).decode("ascii")
    command = (
        "umask 077; "
        "tmp=$(mktemp); "
        "trap 'rm -f \"$tmp\"' EXIT; "
        "base64 -d > \"$tmp\"; "
        "python3 - \"$tmp\" <<'PY'\n"
        "from pathlib import Path\n"
        "import sys\n"
        "incoming_path = Path(sys.argv[1])\n"
        "path = Path('/workspace/.cloud-hot-env')\n"
        "existing = path.read_text() if path.exists() else ''\n"
        "incoming = incoming_path.read_text()\n"
        "names = {line.split('=', 1)[0].replace('export ', '', 1) for line in incoming.splitlines() if line.startswith('export ')}\n"
        "kept = [line for line in existing.splitlines() if not any(line.startswith(f'export {name}=') for name in names)]\n"
        "path.write_text('\\n'.join(kept + incoming.splitlines()) + '\\n')\n"
        "path.chmod(0o600)\n"
        "PY"
    )
    remote.docker_exec(command, input_text=encoded, sensitive=True)
    rendered = ", ".join(dict.fromkeys(names))
    verb = "uploaded" if remote.apply else "[dry-run] would upload"
    print(f"{verb} env names to /workspace/.cloud-hot-env: {rendered}")


def verify_file(remote: Remote, upload: Upload) -> bool:
    expected = sha256(upload.src)
    command = (
        f"test -f {shlex.quote(upload.dest)} && "
        f"stat -c '%a %s %n' {shlex.quote(upload.dest)} && "
        f"sha256sum {shlex.quote(upload.dest)}"
    )
    result = remote.run(command) if upload.host else remote.docker_exec(command)
    if result is None:
        print(f"[dry-run] would verify sha256 {expected} for {upload.dest}")
        return True
    stdout = result.stdout.strip()
    print(stdout)
    actual = stdout.splitlines()[-1].split()[0] if stdout else ""
    if actual != expected:
        print(f"VERIFY FAILED {upload.dest}: expected {expected}, got {actual}", file=sys.stderr)
        return False
    print(f"verified {upload.dest}: sha256 {actual}")
    return True


def parse_session_commands(raw_items: list[str]) -> dict[str, str]:
    commands = dict(KNOWN_SESSION_COMMANDS)
    for raw in raw_items:
        if "=" not in raw:
            raise HotUploadError(f"--session-command must be SESSION=COMMAND, got {raw!r}")
        session, command = raw.split("=", 1)
        if not session or not command:
            raise HotUploadError(f"--session-command must be SESSION=COMMAND, got {raw!r}")
        commands[session] = command
    return commands


def restart_sessions(remote: Remote, sessions: list[str], commands: dict[str, str]) -> None:
    for session in sessions:
        command = commands.get(session)
        if command is None:
            raise HotUploadError(
                f"no restart command for tmux session {session!r}; pass --session-command {session}=..."
            )
        inner = (
            "set -a; "
            "[ ! -f /workspace/.cloud-hot-env ] || . /workspace/.cloud-hot-env; "
            "set +a; "
            f"exec {command}"
        )
        restart = (
            f"tmux kill-session -t {shlex.quote(session)} 2>/dev/null || true; "
            f"tmux new-session -d -s {shlex.quote(session)} -c /workspace "
            f"{shlex.quote(f'bash -lc {shlex.quote(inner)}')}"
        )
        remote.docker_exec(restart)
        verb = "restarted" if remote.apply else "[dry-run] would restart"
        print(f"{verb} tmux session {session}: {command}")


def recreate_container(remote: Remote, spec: CloudSpec) -> None:
    ssh = spec.ssh
    assert ssh is not None
    env_path = f"{ssh.remote_dir}/.env"
    image_probe = (
        f"docker inspect -f '{{{{.Config.Image}}}}' {shlex.quote(ssh.container)} "
        f"2>/dev/null || printf %s {shlex.quote(ssh.container)}"
    )
    command = " ".join(
        [
            f"image=$({image_probe});",
            f"docker rm -f {shlex.quote(ssh.container)} >/dev/null 2>&1 || true;",
            "docker run -d",
            f"--name {shlex.quote(ssh.container)}",
            "--restart unless-stopped",
            f"--env-file {shlex.quote(env_path)}",
            f"-p {spec.resources.port}:{spec.resources.port}",
            f"-v {shlex.quote(ssh.workspace_dir)}:/workspace",
            f"-v {shlex.quote(f'{ssh.cache_dir}/pip')}:/root/.cache/pip",
            f"-v {shlex.quote(f'{ssh.cache_dir}/npm')}:/root/.npm",
            '"$image"',
        ]
    )
    remote.run(command)
    verb = "recreated" if remote.apply else "[dry-run] would recreate"
    print(f"{verb} container {ssh.container} from existing image")


def report(remote: Remote) -> None:
    print("\nRemote container:")
    result = remote.run(
        f"docker ps --filter name={shlex.quote(remote.ssh.container)} "
        "--format '{{.Names}} {{.Status}} {{.Image}}'"
    )
    if result is not None:
        print(result.stdout.strip() or "(container not listed)")
    print("\nTmux sessions:")
    result = remote.docker_exec("tmux ls 2>/dev/null || true")
    if result is not None:
        print(result.stdout.strip() or "(none)")


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        spec = load_ssh_spec(args.cloud_yaml)
        assert spec.ssh is not None
        uploads = collect_uploads(args, spec)
        if args.verify_only and not uploads:
            uploads = wrapper_uploads(argparse.Namespace(wrapper=["arnold-watchdog"], all_wrappers=False))
        if not uploads and not args.recreate_container and not args.restart_session and not args.env_name:
            raise HotUploadError(
                "nothing to do; pass --wrapper, --upload, --env-name, --env-file, or --restart-session"
            )

        remote = Remote(spec.ssh, apply=args.apply)
        print(f"cloud yaml: {args.cloud_yaml}")
        print(f"target: {remote.target}:{spec.ssh.port}, container: {spec.ssh.container}")
        print("mode: apply" if args.apply else "mode: dry-run")

        if not args.verify_only:
            for upload in uploads:
                upload_file(remote, upload)
            upload_env_names(remote, args.env_name)

        if args.env_name:
            print(
                "NOTE: /workspace/.cloud-hot-env is sourced by sessions restarted through "
                "this helper; it does not change already-running process env."
            )

        if args.env_file and not args.recreate_container:
            print(
                "NOTE: env file upload does not change a running container's process env; "
                "rerun with --recreate-container when ready."
            )

        if args.recreate_container:
            if not args.apply:
                print("[dry-run] would recreate container to apply env/entrypoint changes")
            recreate_container(remote, spec)

        if args.restart_session:
            restart_sessions(remote, args.restart_session, parse_session_commands(args.session_command))

        if not args.no_verify:
            ok = True
            for upload in uploads:
                ok = verify_file(remote, upload) and ok
            report(remote)
            if not ok:
                return 2
        return 0
    except HotUploadError as exc:
        print(f"cloud_hot_upload: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
