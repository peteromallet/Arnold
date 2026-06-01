"""Docker-gated local cloud deploy smoke skeleton.

Exercises the ``megaplan cloud build`` CLI path end-to-end using the
local provider: spec loading → deploy-dir materialization (Dockerfile,
docker-compose.yaml, entrypoint.sh, wrappers) → build dispatch.

No Railway account or real credentials required.
"""

from __future__ import annotations

import shutil
import subprocess
from argparse import ArgumentParser
from pathlib import Path

import pytest

from megaplan.cloud.cli import build_cloud_parser, run_cloud_cli


def _docker_skip_reason() -> str | None:
    """Return a skip reason when Docker is unavailable, else ``None``."""
    if shutil.which("docker") is None:  # pragma: no cover - environment-dependent
        return "docker not available"
    try:
        docker_info = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except subprocess.TimeoutExpired:  # pragma: no cover - environment-dependent
        return "docker daemon unavailable: docker info timed out"
    if docker_info.returncode != 0:  # pragma: no cover - environment-dependent
        return f"docker daemon unavailable: {docker_info.stderr.strip()}"
    return None


@pytest.fixture
def requires_docker() -> None:
    """Skip Docker-dependent tests without turning the file into exit code 5."""
    reason = _docker_skip_reason()
    if reason:
        pytest.skip(reason)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parser() -> ArgumentParser:
    """Build a minimal top-level parser with the ``cloud`` subcommand group."""
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_cloud_parser(subparsers)
    return parser


def _write_minimal_cloud_yaml(path: Path) -> None:
    """Write a valid, minimal cloud.yaml using the local provider in idle mode."""
    path.write_text(
        """\
provider: local
repo:
  url: https://github.com/example/app.git
mode: idle
""",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_cloud_deploy_smoke_build_materializes_and_dispatches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    requires_docker: None,
) -> None:
    """End-to-end smoke test for ``megaplan cloud build``.

    Exercises the full CLI dispatch chain:
      1. YAML spec loading from disk (real ``load_spec``)
      2. Deploy-dir materialization (Dockerfile, docker-compose.yaml,
         entrypoint.sh, wrappers)
      3. Provider dispatch to ``build()``

    The actual ``docker compose build`` is replaced with a recording dummy
    so the test is fast, offline-safe, and deterministic.  The full Docker
    build+deploy lifecycle is covered separately in
    ``tests/test_cloud_local_lifecycle.py``.

    **Why ``deploy`` is not exercised here:** ``deploy`` calls
    ``docker compose up -d``, which requires open ports, spins up a
    long-lived container, and can collide with other running services.
    That is inherently a full lifecycle integration test and belongs in
    ``test_cloud_local_lifecycle.py``.
    """
    # Pin HOME so ``_persistent_deploy_dir`` (used by the local provider)
    # lands inside the tmp_path sandbox instead of the real home directory.
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    # Write the cloud spec YAML to a temp path.
    cloud_yaml_path = tmp_path / "cloud.yaml"
    _write_minimal_cloud_yaml(cloud_yaml_path)

    # ------------------------------------------------------------------
    # Recording dummy provider — captures calls without touching Docker.
    # ------------------------------------------------------------------
    provider_calls: list[tuple[str, Path | None]] = []

    class _DummyProvider:
        supports_session = False

        def build(self, deploy_dir: Path) -> int:
            provider_calls.append(("build", deploy_dir))
            # Verify the materialized deploy dir has the expected artifacts.
            assert (
                deploy_dir / "Dockerfile"
            ).exists(), "Dockerfile not materialized"
            assert (
                deploy_dir / "docker-compose.yaml"
            ).exists(), "docker-compose.yaml not materialized"
            assert (
                deploy_dir / "entrypoint.sh"
            ).exists(), "entrypoint.sh not materialized"
            assert (
                deploy_dir / "wrappers" / "mp-run"
            ).exists(), "wrappers/mp-run not materialized"
            return 0

        def deploy(
            self, deploy_dir: Path, *, secrets: dict[str, str]
        ) -> int:
            del secrets
            provider_calls.append(("deploy", deploy_dir))
            return 0

        def ssh_exec(
            self, command: str
        ) -> subprocess.CompletedProcess[str]:
            provider_calls.append(("exec", None))
            return subprocess.CompletedProcess(
                args=["ssh"], returncode=0, stdout=command, stderr=""
            )

        def upload_file(self, src: Path, dest: str) -> None:
            raise AssertionError("upload_file should not be called")

        def read_remote_file(self, path: str) -> str:
            raise AssertionError("read_remote_file should not be called")

        def attach(self) -> int:
            raise AssertionError("attach should not be called")

        def logs(self, *, follow: bool = True) -> int:
            raise AssertionError("logs should not be called")

        def status_payload(
            self, *, plan: str | None, workspace: str
        ) -> dict:
            raise AssertionError("status_payload should not be called")

        def down(self) -> int:
            raise AssertionError("down should not be called")

        def destroy(self, *, volume: str | None = None) -> int:
            raise AssertionError("destroy should not be called")

    # Replace the provider factory so we never invoke ``docker compose``.
    monkeypatch.setattr(
        "megaplan.cloud.cli.get_provider",
        lambda _name, _spec: _DummyProvider(),
    )

    # ------------------------------------------------------------------
    # Parse and execute ``cloud build`` through the real CLI dispatch.
    # ------------------------------------------------------------------
    parser = _parser()
    args = parser.parse_args(
        ["cloud", "build", "--cloud-yaml", str(cloud_yaml_path)]
    )
    exit_code = run_cloud_cli(tmp_path, args)

    # Assertions
    assert exit_code == 0, f"cloud build exited non-zero: {exit_code}"
    assert len(provider_calls) == 1, (
        f"expected exactly 1 provider call, got {provider_calls}"
    )
    assert provider_calls[0][0] == "build"
    assert provider_calls[0][1] is not None


def test_cloud_yaml_loads_without_docker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the cloud spec can be loaded from a minimal YAML without Docker.

    This test does NOT require Docker — it only validates spec parsing
    and therefore runs even in environments where the Docker guard at the
    module level would otherwise skip.
    """
    # Pin HOME so persistent-dir resolution doesn't leak.
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    cloud_yaml_path = tmp_path / "cloud.yaml"
    _write_minimal_cloud_yaml(cloud_yaml_path)

    from megaplan.cloud.spec import load_spec as load_cloud_spec

    spec = load_cloud_spec(cloud_yaml_path)
    assert spec.provider == "local"
    assert spec.repo.url == "https://github.com/example/app.git"
    assert spec.repo.branch == "main"
    assert spec.repo.workspace == "/workspace/app"
    assert spec.mode == "idle"
    assert spec.local is not None
    assert spec.local.compose_project == "megaplan-cloud"
