#!/usr/bin/env python3
"""Validate and normalize the exact offline structural-smoke container config."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


EXPECTED_CAP_ADD = [
    "CHOWN",
    "DAC_READ_SEARCH",
    "KILL",
    "SETGID",
    "SETPCAP",
    "SETUID",
]
EXPECTED_TMPFS_OPTIONS = {
    "rw",
    "noexec",
    "nosuid",
    "nodev",
    "size=268435456",
    "mode=0711",
}


def _empty(value: object) -> bool:
    return value is None or value == {} or value == []


def _normalized_cap_add(value: object) -> object:
    """Normalize Docker's daemon-dependent CAP_ display prefix."""
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return value
    return [item.removeprefix("CAP_") for item in value]


def _unpublished_ports(config: dict[str, Any], network: dict[str, Any]) -> bool:
    """Accept the image's 8080 metadata, but never a published runtime port."""
    if config.get("ExposedPorts") not in ({"8080/tcp": {}}, {"8080/tcp": None}):
        return False
    runtime = network.get("Ports")
    return runtime in (None, {}, {"8080/tcp": None})


def validated_summary(
    payload: object,
    *,
    container_id: str,
    container_name: str,
    image_id: str,
    bind_source: str,
) -> dict[str, Any]:
    if not isinstance(payload, list) or len(payload) != 1:
        raise ValueError("docker inspect must contain exactly one container")
    item = payload[0]
    if not isinstance(item, dict):
        raise ValueError("docker inspect container must be an object")
    host = item.get("HostConfig")
    config = item.get("Config")
    network = item.get("NetworkSettings")
    mounts = item.get("Mounts")
    if not all(isinstance(value, dict) for value in (host, config, network)):
        raise ValueError("docker inspect omitted typed runtime sections")
    if not isinstance(mounts, list):
        raise ValueError("docker inspect mounts must be a list")
    assert isinstance(host, dict) and isinstance(config, dict)
    assert isinstance(network, dict)

    restart = host.get("RestartPolicy")
    tmpfs = host.get("Tmpfs")
    expected_name = f"/{container_name}"
    checks = {
        "container id": item.get("Id") == container_id,
        "container name": item.get("Name") == expected_name,
        "image id": item.get("Image") == image_id,
        "network none": host.get("NetworkMode") == "none",
        "restart no": restart == {"Name": "no", "MaximumRetryCount": 0},
        "cap drop": host.get("CapDrop") == ["ALL"],
        "cap add": _normalized_cap_add(host.get("CapAdd")) == EXPECTED_CAP_ADD,
        "no new privileges": host.get("SecurityOpt") == ["no-new-privileges:true"],
        "ipc none": host.get("IpcMode") == "none",
        "pid limit": host.get("PidsLimit") == 256,
        "memory": host.get("Memory") == 4_294_967_296,
        "memory swap": host.get("MemorySwap") == 4_294_967_296,
        "no host-config ports": _empty(host.get("PortBindings")),
        "no published ports": _unpublished_ports(config, network),
        "no volumes": _empty(config.get("Volumes")),
        "no alternate mounts": _empty(host.get("Mounts")),
        "exact tmpfs destination": isinstance(tmpfs, dict)
        and set(tmpfs) == {"/run/megaplan-zero-recovery"},
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError("container runtime drift: " + ", ".join(failed))
    assert isinstance(tmpfs, dict)
    tmpfs_options = tmpfs["/run/megaplan-zero-recovery"]
    if not isinstance(tmpfs_options, str) or set(tmpfs_options.split(",")) != (
        EXPECTED_TMPFS_OPTIONS
    ):
        raise ValueError("container runtime drift: tmpfs options")
    if len(mounts) != 1 or not isinstance(mounts[0], dict):
        raise ValueError("container runtime drift: exactly one runtime mount required")
    mount = mounts[0]
    expected_mount = {
        "Type": "bind",
        "Source": str(Path(bind_source).resolve()),
        "Destination": "/workspace",
        "Mode": "",
        "RW": True,
        "Propagation": "rprivate",
    }
    if mount != expected_mount:
        raise ValueError("container runtime drift: sole rprivate workspace bind")
    summary: dict[str, Any] = {
        "schema": "arnold.megaplan.zero_recovery_offline_smoke_runtime.v1",
        "validated": True,
        "container_id": container_id,
        "container_name": container_name,
        "image_id": image_id,
        "network_mode": "none",
        "restart_policy": "no",
        "cap_drop": ["ALL"],
        "cap_add": EXPECTED_CAP_ADD,
        "security_opt": ["no-new-privileges:true"],
        "ipc_mode": "none",
        "pids_limit": 256,
        "memory_bytes": 4_294_967_296,
        "memory_swap_bytes": 4_294_967_296,
        "bind": {
            "source": expected_mount["Source"],
            "destination": "/workspace",
            "read_write": True,
            "propagation": "rprivate",
        },
        "tmpfs": {
            "destination": "/run/megaplan-zero-recovery",
            "options": sorted(EXPECTED_TMPFS_OPTIONS),
        },
        "ports": [],
        "volumes": [],
    }
    summary["summary_digest"] = hashlib.sha256(
        json.dumps(summary, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return summary


def main() -> int:
    if len(sys.argv) != 6:
        raise SystemExit(
            "usage: validate_container_inspect.py "
            "<inspect-json> <container-id> <container-name> <image-id> <bind-source>"
        )
    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    try:
        summary = validated_summary(
            payload,
            container_id=sys.argv[2],
            container_name=sys.argv[3],
            image_id=sys.argv[4],
            bind_source=sys.argv[5],
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
