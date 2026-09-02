"""Cloud auth seeding helpers."""

from __future__ import annotations

import base64
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Any

from arnold_pipelines.megaplan.cloud.spec import CloudSpec
from arnold_pipelines.megaplan.types import CliError


_CODEX_SOURCE = Path(".codex/auth.json")


@dataclass(frozen=True)
class OAuthSeed:
    label: str
    local_relative: Path
    persistent_dest: str
    root_dest: str


OAUTH_SEEDS = (
    OAuthSeed(
        label="codex",
        local_relative=_CODEX_SOURCE,
        persistent_dest="/workspace/.creds/codex-auth.json",
        root_dest="/root/.codex/auth.json",
    ),
)


# The AgentBox mounts the durable Git credential file on the shared control
# volume.  Keep this in the cloud-auth module so on-box transports use the
# same credential policy as the rest of cloud orchestration rather than
# growing a provider-local secret convention.
ON_BOX_GIT_CREDENTIAL_FILE = "/workspace/.creds/git-credentials"
ON_BOX_GIT_CREDENTIAL_FILE_ENV = "ARNOLD_ON_BOX_GIT_CREDENTIAL_FILE"
_SAFE_ON_BOX_GIT_ENV = frozenset(
    {
        "PATH",
        "HOME",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TMPDIR",
        "GIT_TERMINAL_PROMPT",
    }
)


def on_box_git_credential_env(
    *,
    env: dict[str, str] | None = None,
    credential_file: str | os.PathLike[str] | None = None,
    home: str | os.PathLike[str] | None = None,
    required: bool = True,
) -> dict[str, str]:
    """Return a sanitized environment for on-box Git operations.

    Only the credential-helper *path* is placed in Git's configuration
    environment.  The helper file is deliberately never opened here, so its
    contents cannot enter argv, receipts, or an exception message.  A missing
    or unreadable helper is a typed setup failure when authentication is
    required.  ``GIT_CONFIG_GLOBAL``/``GIT_CONFIG_NOSYSTEM`` retain the
    hermetic on-box environment while replacing inherited Git config with the
    single path-only helper entry.
    """
    source = dict(env if env is not None else os.environ)
    configured = credential_file or source.get(ON_BOX_GIT_CREDENTIAL_FILE_ENV)
    raw_path = str(configured or ON_BOX_GIT_CREDENTIAL_FILE).strip()
    path = Path(raw_path)
    valid = path.is_absolute() and path.is_file() and os.access(path, os.R_OK)
    if required and not valid:
        raise CliError(
            "on_box_git_auth_unavailable",
            "on-box Git credential helper file is absent or unreadable",
        )
    if not valid:
        return source

    # Do not forward the ambient cloud process environment: it can contain
    # provider tokens unrelated to Git.  Git gets only ordinary process
    # plumbing plus the path-only helper configuration below.
    safe = {key: value for key, value in source.items() if key in _SAFE_ON_BOX_GIT_ENV}
    safe["GIT_CONFIG_NOSYSTEM"] = "1"
    safe["GIT_CONFIG_GLOBAL"] = os.devnull
    safe["GIT_CONFIG_KEY_0"] = "credential.helper"
    safe["GIT_CONFIG_VALUE_0"] = f"store --file={path}"
    safe["GIT_CONFIG_COUNT"] = "1"
    if home is not None:
        safe["HOME"] = str(home)
    return safe


def _remote_seed_command(*, payload_b64: str, persistent_dest: str, root_dest: str) -> str:
    persistent = PurePosixPath(persistent_dest)
    root = PurePosixPath(root_dest)
    persistent_tmp = persistent.with_name(f".{persistent.name}.tmp.$$")
    root_tmp = root.with_name(f".{root.name}.tmp.$$")
    return " ".join(
        [
            "umask 077;",
            f"mkdir -p {shlex.quote(str(persistent.parent))} {shlex.quote(str(root.parent))};",
            f"AUTH_B64={shlex.quote(payload_b64)};",
            f"tmp={shlex.quote(str(persistent_tmp))};",
            'printf %s "$AUTH_B64" | base64 -d > "$tmp" &&',
            f"mv \"$tmp\" {shlex.quote(str(persistent))} &&",
            f"chmod 600 {shlex.quote(str(persistent))} &&",
            f"tmp={shlex.quote(str(root_tmp))};",
            'printf %s "$AUTH_B64" | base64 -d > "$tmp" &&',
            f"mv \"$tmp\" {shlex.quote(str(root))} &&",
            f"chmod 600 {shlex.quote(str(root))};",
            "unset AUTH_B64",
        ]
    )


def seed_codex_oauth(
    spec: CloudSpec,
    provider: Any,
    *,
    home: Path | None = None,
    writer: Callable[[str], object] | None = None,
) -> dict[str, list[dict[str, str]]]:
    """Best-effort seed of local ChatGPT Codex OAuth into the cloud box.

    The seed is written both to the persistent volume under ``/workspace/.creds``
    and to the current root home so an already-running box can use it
    immediately. Entrypoint boot copies the persistent files back into ``/root``
    after restarts.
    """
    write = writer or sys.stderr.write
    events: list[dict[str, str]] = []
    if spec.megaplan.codex_auth == "apikey":
        message = "cloud codex OAuth seed: skipped because megaplan.codex_auth=apikey\n"
        write(message)
        return {"events": [{"label": "all", "status": "skipped", "reason": "codex_auth=apikey"}]}

    root = home or Path.home()
    for seed in OAUTH_SEEDS:
        local_path = root / seed.local_relative
        if not local_path.exists():
            message = f"cloud codex OAuth seed: local {local_path} absent; skipping {seed.label}\n"
            write(message)
            events.append({"label": seed.label, "status": "skipped", "reason": "absent"})
            continue
        payload_b64 = base64.b64encode(local_path.read_bytes()).decode("ascii")
        command = _remote_seed_command(
            payload_b64=payload_b64,
            persistent_dest=seed.persistent_dest,
            root_dest=seed.root_dest,
        )
        try:
            result: subprocess.CompletedProcess[str] = provider.ssh_exec(command)
        except Exception as exc:  # pragma: no cover - defensive best-effort path
            write(f"cloud codex OAuth seed: {seed.label} seed failed: {exc}\n")
            events.append({"label": seed.label, "status": "failed", "reason": str(exc)})
            continue
        if result.returncode == 0:
            write(
                f"cloud codex OAuth seed: seeded {seed.label} auth to {seed.persistent_dest} "
                f"and {seed.root_dest}\n"
            )
            events.append({"label": seed.label, "status": "seeded"})
            continue
        reason = (result.stderr or result.stdout or f"exit {result.returncode}").strip()
        write(f"cloud codex OAuth seed: {seed.label} seed failed: {reason}\n")
        events.append({"label": seed.label, "status": "failed", "reason": reason})
    return {"events": events}


def seed_isolated_git_credentials(
    spec: CloudSpec,
    provider: Any,
    *,
    required: bool,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    writer: Callable[[str], object] | None = None,
) -> dict[str, list[dict[str, str]]]:
    """Seed local ``gh`` auth without putting its token in argv or output.

    The local token is captured in memory, then handed to the isolated SSH
    provider which transports it through stdin only.  Returned events are
    deliberately non-secret and suitable for deploy reports.
    """
    if not spec.isolated_chain_runner:
        return {
            "events": [
                {"label": "git", "status": "skipped", "reason": "not_isolated"}
            ]
        }
    write = writer or sys.stderr.write
    try:
        result = runner(
            ["gh", "auth", "token"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        result = None
    token = (result.stdout if result is not None and result.returncode == 0 else "").strip()
    if not token:
        if required:
            raise CliError(
                "isolated_chain_runner_git_auth_unavailable",
                "isolated cloud chain requires local `gh auth token` for durable Git pushes",
            )
        write("cloud isolated Git auth seed: local gh auth unavailable; skipping\n")
        return {
            "events": [
                {"label": "git", "status": "skipped", "reason": "local_gh_auth_unavailable"}
            ]
        }
    installer = getattr(provider, "seed_isolated_chain_runner_git_credentials", None)
    if installer is None:
        raise CliError(
            "isolated_chain_runner_git_auth_unavailable",
            "SSH provider lacks isolated Git credential seeding",
        )
    receipt = installer(token)
    if not isinstance(receipt, dict) or receipt.get("status") != "seeded":
        raise CliError(
            "isolated_chain_runner_git_auth_failed",
            "isolated Git credential seeding did not return a valid receipt",
        )
    write("cloud isolated Git auth seed: seeded github.com credential helper\n")
    return {"events": [{"label": "git", "status": "seeded"}]}
