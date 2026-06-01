from __future__ import annotations

import shutil
import subprocess

import pytest

from megaplan.cloud.spec import (
    CloudSpec,
    CodexSpec,
    MegaplanSpec,
    RailwaySpec,
    RepoSpec,
    ResourcesSpec,
)
from megaplan.cloud.template import materialize_deploy_dir


if shutil.which("docker") is None:  # pragma: no cover - environment-dependent
    pytest.skip("docker not available", allow_module_level=True)

try:
    _docker_info = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
except subprocess.TimeoutExpired:  # pragma: no cover - environment-dependent
    pytest.skip("docker daemon unavailable: docker info timed out", allow_module_level=True)
if _docker_info.returncode != 0:  # pragma: no cover - environment-dependent
    pytest.skip(
        f"docker daemon unavailable: {_docker_info.stderr.strip()}",
        allow_module_level=True,
    )


def _spec() -> CloudSpec:
    return CloudSpec(
        provider="railway",
        repo=RepoSpec(
            url="https://github.com/example/cloud-app.git",
            branch="main",
            workspace="/workspace/app",
        ),
        agents={"default": "codex"},
        codex=CodexSpec(model="ops-model", reasoning="medium"),
        mode="idle",
        megaplan=MegaplanSpec(ref="main"),
        resources=ResourcesSpec(volume="agent-volume", port=8080),
        secrets=[],
        railway=RailwaySpec(service="agent", session="agent", project=None),
    )


@pytest.mark.slow
def test_materialized_cloud_image_builds_and_contains_wrappers(tmp_path) -> None:
    image = "megaplan-cloud-smoke"
    materialize_deploy_dir(_spec(), tmp_path)

    try:
        build = subprocess.run(
            ["docker", "build", "-t", image, "."],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )
        assert build.returncode == 0, build.stderr

        run = subprocess.run(
            ["docker", "run", "--rm", image, "which", "mp-run"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert run.returncode == 0, run.stderr
    finally:
        subprocess.run(
            ["docker", "rmi", "-f", image],
            capture_output=True,
            text=True,
            check=False,
        )
