"""Shared policy and safe installation helpers for ``.cloud-hot-env``.

The hot environment is deliberately limited to credentials.  Runtime
selectors, model pins, feature flags, and sync controls belong to the
attested runtime/session configuration and must never be supplied through
this mutable file.
"""

from __future__ import annotations

import re
import shlex
from typing import Mapping


HOT_ENV_RUNTIME_SELECTOR_NAMES: tuple[str, ...] = (
    "MEGAPLAN_RUNTIME_SRC",
    "MEGAPLAN_LAUNCH_RUNTIME_SRC",
    "MEGAPLAN_SUPERVISOR_SOURCE",
    "CLOUD_WATCHDOG_ARNOLD_SRC",
    "MEGAPLAN_META_ARNOLD_SRC",
    "MEGAPLAN_AUDIT_ARNOLD_SRC",
    "CLOUD_WATCHDOG_SYNC_BRANCH",
    "KIMI_GOAL_SYNC_BRANCH",
    "MEGAPLAN_META_SYNC_BRANCH",
    "KIMI_GOAL_ARNOLD_SRC",
    "MEGAPLAN_DISCORD_DM_ARNOLD_SRC",
    "MEGAPLAN_DISCOVER_ARNOLD_SRC",
)

HOT_ENV_FORBIDDEN_NONSECRET_NAMES: tuple[str, ...] = (
    "ARNOLD_META_REPAIR_ENABLED",
    "ARNOLD_META_REPAIR_COMMIT_ENABLED",
    "ARNOLD_AUDIT_AUTOFIX_ENABLED",
    "ARNOLD_AUDIT_AUTOFIX_COMMIT_ENABLED",
)

HOT_ENV_GHOST_CONFIG_NAMES: tuple[str, ...] = (
    "ARNOLD_REPAIR_TRIGGER_SESSION_ALLOWLIST",
)

HOT_ENV_CREDENTIAL_RE = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|API)", re.IGNORECASE)


class HotEnvError(ValueError):
    """Raised when a hot-env mapping violates the credentials-only contract."""


def validate_hot_env_mapping(values: Mapping[str, str]) -> dict[str, str]:
    """Validate and return *values* in insertion order.

    This is the single allowlist used by both canonical SSH deploy and the
    operator hot-upload helper.  Values are retained as strings and are only
    shell-quoted when rendered; NUL is rejected because it cannot be carried
    by an environment assignment safely.
    """

    result: dict[str, str] = {}
    for name, value in values.items():
        if (
            not isinstance(name, str)
            or not name
            or not name.replace("_", "").isalnum()
            or ((not name[0].isalpha()) and name[0] != "_")
        ):
            raise HotEnvError(f"invalid environment variable name: {name!r}")
        if name in HOT_ENV_RUNTIME_SELECTOR_NAMES:
            raise HotEnvError(
                f"refusing hot env runtime selector {name!r}: runtime identity "
                "resolves from the per-epic runtime manifest"
            )
        if name in HOT_ENV_GHOST_CONFIG_NAMES:
            raise HotEnvError(
                f"refusing hot env ghost config name {name!r}: no code reads it"
            )
        if (
            name in HOT_ENV_FORBIDDEN_NONSECRET_NAMES
            or "MODEL" in name.upper()
            or "SYNC" in name.upper()
        ):
            raise HotEnvError(
                f"refusing hot env nonsecret tuning {name!r}: credentials-only"
            )
        if not HOT_ENV_CREDENTIAL_RE.search(name):
            raise HotEnvError(
                f"refusing hot env non-credential env {name!r}: credentials-only"
            )
        if not isinstance(value, str) or any(
            character in value for character in ("\x00", "\r", "\n")
        ):
            # These values also cross the Docker host .env boundary during
            # deploy.  Reject record separators before any host mutation;
            # shell quoting alone cannot make a multiline dotenv value safe.
            raise HotEnvError(f"invalid value for hot env variable {name!r}")
        result[name] = value
    return result


def render_hot_env(values: Mapping[str, str]) -> str:
    """Render a validated mapping as sourceable, non-secret-bearing text."""

    validated = validate_hot_env_mapping(values)
    return "".join(f"export {name}={shlex.quote(value)}\n" for name, value in validated.items())


# The script reads the complete payload from stdin, atomically replaces the
# destination, and verifies the resulting bytes/mode before returning.  It
# intentionally emits no stdout/stderr so neither values nor file contents can
# enter provider logs or evidence.
HOT_ENV_INSTALL_SCRIPT = r'''
import fcntl, hashlib, os, stat, sys

parent = "/workspace"
path = "/workspace/.cloud-hot-env"
if path != os.path.join(parent, ".cloud-hot-env"):
    raise RuntimeError("hot env destination is invalid")
if os.path.realpath(parent) != parent:
    raise RuntimeError("hot env parent is not canonical")
parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
temporary = ".cloud-hot-env.deploy-new"
try:
    # Serialize merge/read/replace transactions across concurrent operators;
    # os.replace alone is atomic but would still allow lost updates.
    fcntl.flock(parent_fd, fcntl.LOCK_EX)
    try:
        payload = sys.stdin.buffer.read()
        if b"\x00" in payload:
            raise RuntimeError("hot env payload contains NUL")
        if "--merge" in sys.argv[1:]:
            incoming = payload.decode("utf-8")
            incoming_lines = incoming.splitlines()
            names = {
                line[7:].split("=", 1)[0]
                for line in incoming_lines
                if line.startswith("export ") and "=" in line[7:]
            }
            try:
                existing_fd = os.open(
                    ".cloud-hot-env", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd
                )
            except FileNotFoundError:
                existing = ""
            else:
                try:
                    existing_stat = os.fstat(existing_fd)
                    if not stat.S_ISREG(existing_stat.st_mode):
                        raise RuntimeError("hot env destination is not a regular file")
                    with os.fdopen(existing_fd, "rb") as handle:
                        existing_fd = -1
                        existing = handle.read().decode("utf-8")
                finally:
                    if existing_fd >= 0:
                        os.close(existing_fd)
            kept = [
                line
                for line in existing.splitlines()
                if not any(line.startswith("export " + name + "=") for name in names)
            ]
            payload = ("\n".join(kept + incoming_lines) + "\n").encode("utf-8")

        try:
            stale = os.stat(temporary, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            stale = None
        if stale is not None:
            if not stat.S_ISREG(stale.st_mode):
                raise RuntimeError("hot env temporary is not a regular file")
            os.unlink(temporary, dir_fd=parent_fd)
        fd = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        try:
            view = memoryview(payload)
            while view:
                view = view[os.write(fd, view):]
            os.fchmod(fd, 0o600)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(temporary, ".cloud-hot-env", src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        os.fsync(parent_fd)
        installed = os.stat(".cloud-hot-env", dir_fd=parent_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(installed.st_mode)
            or stat.S_IMODE(installed.st_mode) != 0o600
            or installed.st_size != len(payload)
        ):
            raise RuntimeError("hot env installation verification failed")
        digest = hashlib.sha256()
        installed_fd = os.open(
            ".cloud-hot-env", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd
        )
        with os.fdopen(installed_fd, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.digest() != hashlib.sha256(payload).digest():
            raise RuntimeError("hot env digest verification failed")
    finally:
        fcntl.flock(parent_fd, fcntl.LOCK_UN)
finally:
    try:
        os.unlink(temporary, dir_fd=parent_fd)
    except FileNotFoundError:
        pass
    os.close(parent_fd)
'''.strip()


def hot_env_install_command(*, container: str, merge: bool = False) -> str:
    """Build the fixed container command used for atomic hot-env install."""

    merge_arg = " --merge" if merge else ""
    return (
        f"docker exec -i {shlex.quote(container)} python3 -c "
        f"{shlex.quote(HOT_ENV_INSTALL_SCRIPT)}{merge_arg}"
    )
