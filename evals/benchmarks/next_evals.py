"""Next-evals benchmark backend."""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any

from . import ScoringResult


class NextEvalsBackend:
    """Adapter for the existing next-evals workspace and scoring flow."""

    def setup_source(
        self,
        config,
        *,
        timeout_seconds: int | None = None,
        runner=None,
    ) -> Path:
        from evals.run_evals import _checkout_repo_ref, _run_command, _run_sync_evals

        runner = runner or _run_command
        repo_spec = config.next_evals_repo
        repo_path = Path(repo_spec).expanduser()

        if repo_path.exists():
            resolved = repo_path.resolve()
            _checkout_repo_ref(resolved, config.next_evals_ref, runner, timeout_seconds)
            _run_sync_evals(resolved, runner, timeout_seconds)
            return resolved

        source_root = Path(config.workspace_dir).expanduser().resolve().parent / "_sources"
        cloned_repo = source_root / "next-evals-oss"
        if cloned_repo.exists():
            runner(["git", "fetch", "--all", "--tags"], cloned_repo, timeout_seconds)
        else:
            source_root.mkdir(parents=True, exist_ok=True)
            runner(["git", "clone", repo_spec, str(cloned_repo)], source_root, timeout_seconds)

        _checkout_repo_ref(cloned_repo, config.next_evals_ref, runner, timeout_seconds)
        _run_sync_evals(cloned_repo, runner, timeout_seconds)
        return cloned_repo

    def list_tasks(
        self,
        source_root: Path,
        configured: list[str],
        cli_selected: list[str] | None,
    ) -> list[str]:
        available = [
            path.name
            for path in sorted((Path(source_root) / "evals").iterdir())
            if path.is_dir()
        ]
        requested = set(configured or available)
        if cli_selected:
            requested &= set(cli_selected)
        selected = [name for name in available if name in requested]
        missing = sorted(requested - set(available))
        if missing:
            raise FileNotFoundError(
                f"Configured evals not found in {Path(source_root) / 'evals'}: {', '.join(missing)}"
            )
        return selected

    def prepare_workspace(
        self,
        task_name: str | Path,
        source_root: str | Path,
        config=None,
        *,
        timeout_seconds: int | None = 600,
        runner=None,
    ):
        from evals.run_evals import PreparedWorkspace, _git_stdout, _log, _run_command

        runner = runner or _run_command
        task_path = Path(task_name).expanduser()
        if task_path.exists():
            eval_path = task_path.resolve()
            workspace_root = Path(source_root).expanduser().resolve()
        else:
            eval_path = Path(source_root).expanduser().resolve() / "evals" / str(task_name)
            workspace_root = Path(config.workspace_dir).expanduser().resolve()

        eval_name = eval_path.name
        workspace_root.mkdir(parents=True, exist_ok=True)
        destination = workspace_root / eval_name
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(eval_path, destination)
        _log(eval_name, f"Copied to {destination}", dim=True)

        runner(["git", "init"], destination, timeout_seconds)
        runner(["git", "config", "user.email", "evals@hermes.local"], destination, timeout_seconds)
        runner(["git", "config", "user.name", "Hermes Evals"], destination, timeout_seconds)

        _log(eval_name, "Running npm install...")
        started = time.monotonic()
        runner(["npm", "install"], destination, timeout_seconds)
        runner(["npm", "install", "next@canary"], destination, timeout_seconds)
        _log(eval_name, f"npm install complete ({time.monotonic() - started:.0f}s)")

        runner(["git", "add", "-A"], destination, timeout_seconds)
        runner(["git", "commit", "-m", "initial"], destination, timeout_seconds)
        initial_commit_sha = _git_stdout(["git", "rev-parse", "HEAD"], destination, timeout_seconds, runner)
        _log(eval_name, f"Workspace ready (initial commit {initial_commit_sha[:8]})")
        return PreparedWorkspace(
            path=str(destination),
            eval_name=eval_name,
            initial_commit_sha=initial_commit_sha,
        )

    def read_prompt(self, task_name: str | Path, source_root: str | Path | None = None) -> str:
        task_path = Path(task_name).expanduser()
        if task_path.exists() and task_path.is_dir():
            eval_path = task_path.resolve()
        else:
            eval_path = Path(source_root).expanduser().resolve() / "evals" / str(task_name)
        return (eval_path / "PROMPT.md").read_text(encoding="utf-8")

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
        from evals.run_evals import _audit_relative_path, _combined_trace_messages, _duration_seconds, _to_dict
        from evals.scoring import check_build, generate_results_json, run_eval_ts

        build_fn = build_fn or check_build
        results_fn = results_fn or generate_results_json
        eval_fn = eval_fn or run_eval_ts

        build_result = build_fn(prepared.path, timeout_seconds=config.eval_timeout_seconds)
        build_result_dict = _to_dict(build_result)
        build_success = bool(build_result_dict.get("success"))

        results_json = results_fn(
            _combined_trace_messages(audit),
            prepared.path,
            initial_commit_sha=prepared.initial_commit_sha,
            status="passed",
            duration_seconds=_duration_seconds(audit),
            model=config.models.get("execute", ""),
            transcript_path=_audit_relative_path(audit, "traces/execute_v1.json"),
            transcript_raw_path=_audit_relative_path(audit, "raw/execute_v1.txt"),
            build_output_path=_audit_relative_path(audit, "scoring/build.json"),
            eval_output_path=_audit_relative_path(audit, "scoring/eval.json"),
        )

        eval_result = eval_fn(
            prepared.path,
            results_json,
            timeout_seconds=config.eval_timeout_seconds,
        )
        eval_result_dict = _to_dict(eval_result)
        eval_success = bool(eval_result_dict.get("success"))
        reporter = eval_result_dict.get("reporter_json") or {}
        passed = reporter.get("numPassedTests")
        if passed is None:
            passed = reporter.get("passed")
        total = reporter.get("numTotalTests")
        if total is None:
            total = reporter.get("total")

        all_assertions_passed = (
            passed is not None
            and total is not None
            and total > 0
            and passed == total
        )
        conditional = False
        notes: list[str] = []
        status = "passed"
        if not build_success and all_assertions_passed:
            conditional = True
            notes.append("Conditional pass: build failed, but all eval assertions passed.")
        elif not build_success or not eval_success:
            status = "failed"
        results_json["status"] = status

        return ScoringResult(
            status=status,
            build_result=build_result_dict,
            eval_result=eval_result_dict,
            results_json=results_json,
            notes=notes,
            conditional=conditional,
        )

    def capture_environment(self, source_root: str | Path) -> dict[str, Any]:
        from evals.config import capture_environment

        return capture_environment(next_evals_root=source_root)

    def megaplan_env_overrides(self, prepared) -> dict[str, str]:
        return {}

    def cleanup_workspace(self, prepared) -> None:
        shutil.rmtree(prepared.path, ignore_errors=True)
