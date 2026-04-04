"""Config loading and environment capture for eval runs."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


REQUIRED_MODEL_PHASES = (
    "plan",
    "critique",
    "revise",
    "gate",
    "finalize",
    "execute",
    "review",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_NEXT_EVALS_REPO = "https://github.com/vercel/next-evals-oss"
DEFAULT_NEXT_EVALS_REF = "main"
DEFAULT_WORKSPACE_DIR = PROJECT_ROOT / "evals" / "workspaces"
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "results"


@dataclass(slots=True)
class EvalConfig:
    """Runtime config for an eval experiment.

    `openrouter_params` is stored for reproducibility only. Hermes and megaplan
    do not currently expose inference parameter plumbing, so these values are
    recorded but not enforced at runtime.
    """

    models: dict[str, str]
    benchmark: str = "next-evals"
    max_gate_iterations: int = 3
    eval_timeout_seconds: int = 600
    evals_to_run: list[str] = field(default_factory=list)
    next_evals_repo: str = DEFAULT_NEXT_EVALS_REPO
    next_evals_ref: str = DEFAULT_NEXT_EVALS_REF
    terminal_bench_repo: str = "https://github.com/laude-institute/terminal-bench"
    terminal_bench_ref: str = "main"
    docker_timeout: int = 300
    test_timeout: int = 180
    max_verify_attempts: int = 3
    swebench_dataset: str = "princeton-nlp/SWE-bench_Lite"
    swebench_patch_only: bool = False
    swebench_docker_execute: bool = False
    workers: int = 1
    phase_timeouts: dict[str, int] = field(default_factory=dict)
    openrouter_params: dict[str, Any] = field(default_factory=dict)
    megaplan_bin: str = "megaplan"
    robustness: str = "heavy"
    workspace_dir: str = str(DEFAULT_WORKSPACE_DIR)
    results_dir: str = str(DEFAULT_RESULTS_DIR)
    run_name: str = ""
    manifest_path: str = ""
    worker_id: str = ""
    claim_batch_size: int = 10
    predictions_dir: str = ""

    def __post_init__(self) -> None:
        missing = [phase for phase in REQUIRED_MODEL_PHASES if not self.models.get(phase)]
        if missing:
            required = ", ".join(REQUIRED_MODEL_PHASES)
            missing_display = ", ".join(missing)
            raise ValueError(
                f"models must define all required phases ({required}); missing: {missing_display}"
            )
        if self.max_gate_iterations < 1:
            raise ValueError("max_gate_iterations must be at least 1")
        if self.eval_timeout_seconds < 1:
            raise ValueError("eval_timeout_seconds must be at least 1")
        if self.docker_timeout < 1:
            raise ValueError("docker_timeout must be at least 1")
        if self.test_timeout < 1:
            raise ValueError("test_timeout must be at least 1")
        if self.max_verify_attempts < 1:
            raise ValueError("max_verify_attempts must be at least 1")
        if self.benchmark == "next-evals":
            if not self.next_evals_repo:
                raise ValueError("next_evals_repo must be set for the next-evals benchmark")
            if not self.next_evals_ref:
                raise ValueError("next_evals_ref must be set for the next-evals benchmark")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_config(path: str | Path) -> EvalConfig:
    config_path = Path(path).expanduser().resolve()
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Config at {config_path} must be a JSON object")
    return EvalConfig(**payload)


def capture_environment(
    *,
    hermes_root: str | Path | None = None,
    megaplan_root: str | Path | None = None,
    next_evals_root: str | Path | None = None,
    benchmark_source_root: str | Path | None = None,
    benchmark_name: str = "next-evals",
) -> dict[str, Any]:
    hermes_path = Path(hermes_root or PROJECT_ROOT).expanduser().resolve()
    megaplan_path = Path(megaplan_root or (PROJECT_ROOT.parent / "megaplan")).expanduser().resolve()
    benchmark_root = benchmark_source_root or next_evals_root
    if benchmark_root is None:
        if benchmark_name == "next-evals":
            benchmark_root = PROJECT_ROOT.parent / "next-evals-oss"
        else:
            benchmark_root = PROJECT_ROOT.parent / benchmark_name
    benchmark_path = Path(benchmark_root).expanduser().resolve()
    benchmark_repo_key = _benchmark_repo_key(benchmark_name)

    return {
        "repos": {
            "hermes-agent": _capture_repo(hermes_path),
            "megaplan": _capture_repo(megaplan_path),
            benchmark_repo_key: _capture_repo(benchmark_path),
        },
        "runtime": {
            "python": {
                "version": sys.version.split()[0],
                "executable": sys.executable,
            },
            "node": _capture_command_version(["node", "--version"]),
            "npm": _capture_command_version(["npm", "--version"]),
        },
        "os": {
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python_implementation": platform.python_implementation(),
        },
    }


def _capture_repo(path: Path) -> dict[str, Any]:
    repo_info: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
    }
    if not path.exists():
        repo_info["git_sha"] = None
        repo_info["git_status"] = "missing"
        return repo_info

    repo_info["git_sha"] = _run_text(["git", "rev-parse", "HEAD"], cwd=path)
    repo_info["git_branch"] = _run_text(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=path)
    repo_info["git_status"] = _run_text(["git", "status", "--short"], cwd=path)
    return repo_info


def _capture_command_version(command: list[str]) -> dict[str, Any]:
    return {
        "command": command,
        "version": _run_text(command),
    }


def _run_text(command: list[str], cwd: Path | None = None) -> str | None:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip() or completed.stderr.strip() or None


def _benchmark_repo_key(benchmark_name: str) -> str:
    if benchmark_name == "next-evals":
        return "next-evals-oss"
    return benchmark_name
