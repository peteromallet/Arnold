"""Cloud auth seeding helpers."""

from __future__ import annotations

import base64
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Any

from megaplan.cloud.spec import CloudSpec


_CODEX_SOURCE = Path(".codex/auth.json")
_HERMES_SOURCE = Path(".hermes/auth.json")


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
    OAuthSeed(
        label="hermes",
        local_relative=_HERMES_SOURCE,
        persistent_dest="/workspace/.creds/hermes-auth.json",
        root_dest="/root/.hermes/auth.json",
    ),
)


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
