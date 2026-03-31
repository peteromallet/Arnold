"""Terminal-Bench benchmark backend."""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import yaml

from . import ScoringResult
from .docker_utils import build_image, docker_version, pull_image


INCOMPATIBLE_TASKS = {
    "qemu-startup",
    "qemu-alpine-ssh",
    "crack-7z-hash",
}


class TerminalBenchBackend:
    """Adapter for repository-backed Terminal-Bench tasks."""

    def setup_source(
        self,
        config,
        *,
        timeout_seconds: int | None = None,
        runner=None,
    ) -> Path:
        from evals.run_evals import _checkout_repo_ref, _run_command

        runner = runner or _run_command
        repo_spec = config.terminal_bench_repo
        repo_path = Path(repo_spec).expanduser()

        if repo_path.exists():
            resolved = repo_path.resolve()
            _checkout_repo_ref(resolved, config.terminal_bench_ref, runner, timeout_seconds)
            return resolved

        source_root = Path(config.workspace_dir).expanduser().resolve().parent / "_sources"
        cloned_repo = source_root / "terminal-bench"
        if cloned_repo.exists():
            runner(["git", "fetch", "--all", "--tags"], cloned_repo, timeout_seconds)
        else:
            source_root.mkdir(parents=True, exist_ok=True)
            runner(["git", "clone", repo_spec, str(cloned_repo)], source_root, timeout_seconds)

        _checkout_repo_ref(cloned_repo, config.terminal_bench_ref, runner, timeout_seconds)
        return cloned_repo

    def list_tasks(
        self,
        source_root: Path,
        configured: list[str],
        cli_selected: list[str] | None,
    ) -> list[str]:
        tasks_root = Path(source_root) / "original-tasks"
        available = [
            path.name
            for path in sorted(tasks_root.iterdir())
            if path.is_dir() and self._has_task_definition(path)
        ]
        requested = set(configured or available)
        if cli_selected:
            requested &= set(cli_selected)
        selected = [
            name for name in available
            if name in requested and name not in INCOMPATIBLE_TASKS
        ]
        missing = sorted(requested - set(available))
        if missing:
            raise FileNotFoundError(
                f"Configured tasks not found in {tasks_root}: {', '.join(missing)}"
            )
        return selected

    def prepare_workspace(
        self,
        task_name: str,
        source_root: str | Path,
        config,
        *,
        timeout_seconds: int | None = None,
        runner=None,
    ):
        from evals.run_evals import PreparedWorkspace, _git_stdout, _log, _run_command

        runner = runner or _run_command
        source_path = Path(source_root).expanduser().resolve()
        task_dir = source_path / "original-tasks" / task_name
        if not task_dir.exists():
            raise FileNotFoundError(f"Task directory not found: {task_dir}")

        workspace_root = Path(config.workspace_dir).expanduser().resolve()
        workspace_root.mkdir(parents=True, exist_ok=True)
        destination = workspace_root / task_name
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(task_dir, destination)
        self._materialize_test_support(task_dir, destination, source_path)
        _log(task_name, f"Copied to {destination}", dim=True)

        image = self._resolve_or_build_image(task_dir, task_name, destination, runner, config.docker_timeout)
        _log(task_name, f"Docker image ready: {image}", dim=True)

        runner(["git", "init"], destination, timeout_seconds)
        runner(["git", "config", "user.email", "evals@hermes.local"], destination, timeout_seconds)
        runner(["git", "config", "user.name", "Hermes Evals"], destination, timeout_seconds)
        runner(["git", "add", "-A"], destination, timeout_seconds)
        runner(["git", "commit", "-m", "initial"], destination, timeout_seconds)
        initial_commit_sha = _git_stdout(["git", "rev-parse", "HEAD"], destination, timeout_seconds, runner)
        _log(task_name, f"Workspace ready (initial commit {initial_commit_sha[:8]})")
        return PreparedWorkspace(
            path=str(destination),
            eval_name=task_name,
            initial_commit_sha=initial_commit_sha,
            metadata={"docker_image": image},
        )

    def read_prompt(self, task_name: str, source_root: str | Path) -> str:
        task_dir = Path(source_root).expanduser().resolve() / "original-tasks" / task_name

        # Primary: instruction field in task.yaml (standard terminal-bench format)
        task_config = self._load_task_config(task_dir)
        for key in ("instruction", "description"):
            value = task_config.get(key)
            if isinstance(value, str) and value.strip():
                return value

        # Fallback: instruction.md file
        instruction_path = task_dir / "instruction.md"
        if instruction_path.exists():
            return instruction_path.read_text(encoding="utf-8")

        # Fallback: descriptions array
        descriptions = task_config.get("descriptions")
        if isinstance(descriptions, list):
            for entry in descriptions:
                if isinstance(entry, dict) and isinstance(entry.get("description"), str):
                    return entry["description"]

        raise FileNotFoundError(f"No instruction found for task {task_name}")

    def score(
        self,
        prepared,
        audit,
        config,
        *,
        build_fn: Any = None,
        results_fn: Any = None,
        eval_fn: Any = None,
    ) -> ScoringResult:
        from evals.run_evals import _audit_relative_path, _duration_seconds

        workspace_path = Path(prepared.path).expanduser().resolve()
        image = prepared.metadata.get("docker_image")
        if not image:
            raise ValueError(f"Missing docker_image metadata for {prepared.eval_name}")

        command = self._score_command(workspace_path, image)
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=config.test_timeout,
                check=False,
            )
            duration = time.monotonic() - started
            success = completed.returncode == 0
            status = "passed" if success else "failed"
            test_result = {
                "success": success,
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "command": command,
                "duration_seconds": duration,
                "script": self._score_script_name(workspace_path),
                "docker_image": image,
            }
        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - started
            status = "error"
            test_result = {
                "success": False,
                "returncode": -1,
                "stdout": exc.stdout or "",
                "stderr": (exc.stderr or "") + f"\nTimed out after {config.test_timeout}s",
                "command": command,
                "duration_seconds": duration,
                "script": self._score_script_name(workspace_path),
                "docker_image": image,
            }
        except FileNotFoundError as exc:
            duration = time.monotonic() - started
            status = "error"
            test_result = {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": str(exc),
                "command": command,
                "duration_seconds": duration,
                "script": self._score_script_name(workspace_path),
                "docker_image": image,
            }
        results_json = {
            "status": status,
            "benchmark": "terminal-bench",
            "model": config.models.get("execute", ""),
            "duration": _duration_seconds(audit),
            "transcriptPath": _audit_relative_path(audit, "traces/execute_v1.json"),
            "transcriptRawPath": _audit_relative_path(audit, "raw/execute_v1.txt"),
            "outputPaths": {"test": _audit_relative_path(audit, "scoring/test.json")},
        }
        return ScoringResult(
            status=status,
            test_result=test_result,
            results_json=results_json,
        )

    def capture_environment(self, source_root: str | Path) -> dict[str, Any]:
        from evals.config import capture_environment

        environment = capture_environment(
            benchmark_source_root=source_root,
            benchmark_name="terminal-bench",
        )
        try:
            environment.setdefault("runtime", {})["docker"] = {
                "version": docker_version(timeout=30),
            }
        except Exception as exc:
            environment.setdefault("runtime", {})["docker"] = {
                "version": None,
                "error": str(exc),
            }
        return environment

    def megaplan_env_overrides(self, prepared) -> dict[str, str]:
        image = prepared.metadata.get("docker_image", "")
        return {
            "TERMINAL_ENV": "docker",
            "TERMINAL_DOCKER_IMAGE": image,
            "TERMINAL_DOCKER_MOUNT_CWD_TO_WORKSPACE": "true",
        }

    def cleanup_workspace(self, prepared) -> None:
        shutil.rmtree(prepared.path, ignore_errors=True)

    @staticmethod
    def _has_task_definition(task_dir: Path) -> bool:
        return (task_dir / "task.yaml").exists() or (task_dir / "instruction.md").exists()

    @staticmethod
    def _load_task_config(task_dir: Path) -> dict[str, Any]:
        config_path = task_dir / "task.yaml"
        if not config_path.exists():
            return {}
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            raise ValueError(f"Expected a YAML object in {config_path}")
        return payload

    def _resolve_or_build_image(self, task_dir: Path, task_name: str, workspace: Path, runner, timeout: int) -> str:
        """Build from Dockerfile if present, otherwise try to pull a named image."""
        from evals.run_evals import _log

        dockerfile = task_dir / "Dockerfile"
        if dockerfile.exists():
            tag = f"tb2-{task_name}:latest"
            _log(task_name, f"Building Docker image from Dockerfile...", dim=True)
            build_image(tag, task_dir, dockerfile=dockerfile, runner=runner, timeout=timeout)
            return tag

        # No Dockerfile — try to resolve and pull a named image
        image = self._resolve_task_image(task_dir, task_name)
        _log(task_name, f"Pulling Docker image {image}...", dim=True)
        pull_image(image, runner=runner, timeout=timeout)
        return image

    def _resolve_task_image(self, task_dir: Path, task_name: str) -> str:
        task_config = self._load_task_config(task_dir)
        candidates: list[str] = []

        for key in ("docker_image", "image"):
            value = task_config.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())

        docker_block = task_config.get("docker")
        if isinstance(docker_block, dict):
            value = docker_block.get("image")
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())

        compose_candidate = self._compose_client_image(task_dir)
        if compose_candidate:
            candidates.append(compose_candidate)

        candidates.append(f"ghcr.io/laude-institute/terminal-bench/{task_name}:latest")

        dockerfile_base = self._dockerfile_base_image(task_dir / "Dockerfile")
        if dockerfile_base:
            candidates.append(dockerfile_base)

        for candidate in candidates:
            if candidate and "${" not in candidate:
                return candidate
        raise ValueError(f"Could not resolve a Docker image for task {task_name}")

    @staticmethod
    def _compose_client_image(task_dir: Path) -> str | None:
        for name in ("docker-compose.yaml", "docker-compose.yml"):
            compose_path = task_dir / name
            if not compose_path.exists():
                continue
            payload = yaml.safe_load(compose_path.read_text(encoding="utf-8")) or {}
            if not isinstance(payload, dict):
                continue
            services = payload.get("services")
            if not isinstance(services, dict):
                continue
            client = services.get("client")
            if isinstance(client, dict):
                image = client.get("image")
                if isinstance(image, str) and image.strip():
                    return image.strip()
            for service in services.values():
                if isinstance(service, dict):
                    image = service.get("image")
                    if isinstance(image, str) and image.strip():
                        return image.strip()
        return None

    @staticmethod
    def _dockerfile_base_image(dockerfile_path: Path) -> str | None:
        if not dockerfile_path.exists():
            return None
        for line in dockerfile_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("FROM "):
                return stripped.split(None, 1)[1].strip()
        return None

    def _materialize_test_support(self, task_dir: Path, destination: Path, source_root: Path) -> None:
        task_config = self._load_task_config(task_dir)
        tests_dir = destination / "tests"
        tests_dir.mkdir(exist_ok=True)
        scripts = task_config.get("test_scripts")
        if not isinstance(scripts, list):
            scripts = ["setup-uv-pytest.sh", "run-uv-pytest.sh"]

        for script_name in scripts:
            if not isinstance(script_name, str) or not script_name.strip():
                continue
            destination_path = tests_dir / script_name
            if destination_path.exists():
                continue
            for root_name in ("scripts_bash", "scripts_python"):
                source_path = source_root / root_name / script_name
                if source_path.exists():
                    shutil.copy2(source_path, destination_path)
                    break

    def _score_script_name(self, workspace_path: Path) -> str:
        if (workspace_path / "run-tests.sh").exists():
            return "run-tests.sh"
        if (workspace_path / "test.sh").exists():
            return "test.sh"
        return "task.yaml:test_scripts"

    def _score_command(self, workspace_path: Path, image: str) -> list[str]:
        workspace = workspace_path.resolve()
        shell_parts = [
            "export TEST_DIR=/workspace/tests",
            "export T_BENCH_TEST_DIR=/workspace/tests",
            "export T_BENCH_TASK_LOGS_PATH=/workspace/logs",
            "export T_BENCH_CONTAINER_LOGS_PATH=/workspace/logs",
            "mkdir -p /workspace/logs",
        ]

        if (workspace_path / "run-tests.sh").exists():
            shell_parts.append("bash /workspace/run-tests.sh")
        elif (workspace_path / "test.sh").exists():
            shell_parts.append("bash /workspace/test.sh")
        else:
            task_config = self._load_task_config(workspace_path)
            scripts = task_config.get("test_scripts") or ["setup-uv-pytest.sh", "run-uv-pytest.sh"]
            if not isinstance(scripts, list) or not scripts:
                raise FileNotFoundError(f"No run-tests.sh, test.sh, or test_scripts for {workspace_path.name}")
            chained: list[str] = []
            for index, script_name in enumerate(scripts):
                if not isinstance(script_name, str) or not script_name.strip():
                    continue
                script_path = f"/workspace/tests/{script_name}"
                if index < len(scripts) - 1:
                    chained.append(f"source {script_path}")
                else:
                    chained.append(f"bash {script_path}")
            shell_parts.append(" && ".join(chained))

        return [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{workspace}:/workspace",
            "-w",
            "/workspace",
            image,
            "bash",
            "-lc",
            " && ".join(shell_parts),
        ]
