"""SWE-bench benchmark backend."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from . import ScoringResult, VerifyResult


# Representative sample: ~2-3 per repo, covering different difficulty levels
REPRESENTATIVE_SAMPLE = [
    # django (largest repo in SWE-bench Lite)
    "django__django-11099",
    "django__django-11179",
    "django__django-13230",
    "django__django-14016",
    "django__django-16139",
    # sympy
    "sympy__sympy-20590",
    "sympy__sympy-13146",
    "sympy__sympy-18199",
    # matplotlib
    "matplotlib__matplotlib-23314",
    "matplotlib__matplotlib-25311",
    # scikit-learn
    "scikit-learn__scikit-learn-13241",
    "scikit-learn__scikit-learn-25570",
    # pytest
    "pytest-dev__pytest-5692",
    "pytest-dev__pytest-7373",
    # sphinx
    "sphinx-doc__sphinx-8282",
    # astropy
    "astropy__astropy-12907",
    # requests
    "psf__requests-2317",
    # pylint
    "pylint-dev__pylint-7114",
    # xarray
    "pydata__xarray-4094",
    # flask
    "pallets__flask-4992",
]


def _extract_planned_files(workspace_path: Path) -> list[str]:
    """Extract files_changed from finalize.json to filter the diff."""
    import json as _json
    planned: set[str] = set()
    for finalize_path in workspace_path.rglob(".megaplan/plans/*/finalize.json"):
        try:
            data = _json.loads(finalize_path.read_text())
            for task in data.get("tasks", []):
                for f in task.get("files_changed", []):
                    if isinstance(f, str) and f.strip():
                        planned.add(f.strip())
        except Exception:
            continue
    return sorted(planned)


class SWEBenchBackend:
    """Adapter for SWE-bench evaluation."""

    def __init__(self):
        self._dataset: list[dict[str, Any]] | None = None
        self._instances: dict[str, dict[str, Any]] = {}

    def _load_dataset(self, dataset_name: str = "princeton-nlp/SWE-bench_Lite") -> list[dict[str, Any]]:
        if self._dataset is not None:
            return self._dataset
        from datasets import load_dataset

        ds = load_dataset(dataset_name, split="test")
        self._dataset = [dict(row) for row in ds]
        self._instances = {row["instance_id"]: row for row in self._dataset}
        return self._dataset

    def setup_source(
        self,
        config,
        *,
        timeout_seconds: int | None = None,
        runner=None,
    ) -> Path:
        from evals.run_evals import _log

        dataset_name = getattr(config, "swebench_dataset", "princeton-nlp/SWE-bench_Lite")
        _log("swe-bench", f"Loading dataset {dataset_name}...")
        data = self._load_dataset(dataset_name)
        _log("swe-bench", f"Loaded {len(data)} instances")

        # Return a marker path — SWE-bench doesn't have a traditional source root
        source_marker = Path(config.workspace_dir).expanduser().resolve().parent / "_sources" / "swe-bench"
        source_marker.mkdir(parents=True, exist_ok=True)
        return source_marker

    def list_tasks(
        self,
        source_root: Path,
        configured: list[str],
        cli_selected: list[str] | None,
    ) -> list[str]:
        self._load_dataset()
        all_ids = [row["instance_id"] for row in self._dataset]

        if cli_selected:
            selected = [i for i in cli_selected if i in self._instances]
            missing = [i for i in cli_selected if i not in self._instances]
            if missing:
                raise FileNotFoundError(f"Instance IDs not found: {', '.join(missing)}")
            return selected

        if configured:
            selected = [i for i in configured if i in self._instances]
            missing = [i for i in configured if i not in self._instances]
            if missing:
                raise FileNotFoundError(f"Instance IDs not found: {', '.join(missing)}")
            return selected

        # No filter: run all tasks
        return all_ids

    def prepare_workspace(
        self,
        task_name: str,
        source_root: str | Path,
        config=None,
        *,
        timeout_seconds: int | None = 600,
        runner=None,
    ):
        from evals.run_evals import PreparedWorkspace, _log, _run_command

        runner = runner or _run_command
        instance = self._instances.get(task_name)
        if not instance:
            self._load_dataset()
            instance = self._instances.get(task_name)
        if not instance:
            raise FileNotFoundError(f"SWE-bench instance not found: {task_name}")

        repo = instance["repo"]
        base_commit = instance["base_commit"]
        workspace_root = Path(config.workspace_dir).expanduser().resolve()
        workspace_root.mkdir(parents=True, exist_ok=True)

        # Use instance_id as workspace name (replace / with __)
        safe_name = task_name.replace("/", "__")
        destination = workspace_root / safe_name
        if destination.exists():
            shutil.rmtree(destination)

        started = time.monotonic()

        # Cache repo clones — clone once per repo, then worktree for each task
        repo_url = f"https://github.com/{repo}.git"
        repo_cache_name = repo.replace("/", "__")
        cache_dir = workspace_root.parent / "_repo_cache" / repo_cache_name
        cache_dir.parent.mkdir(parents=True, exist_ok=True)

        if not (cache_dir / ".git").exists() and not (cache_dir / "HEAD").exists():
            _log(task_name, f"Cloning {repo} (first time, will be cached)...")
            runner(["git", "clone", "--bare", repo_url, str(cache_dir)], workspace_root, timeout_seconds)
        else:
            # Fetch latest (in case new commits needed)
            try:
                runner(["git", "fetch", "--all"], cache_dir, timeout_seconds)
            except Exception:
                pass  # Best effort — cached repo might be enough

        # Create worktree at the specific commit
        _log(task_name, f"Creating worktree at {base_commit[:8]}...")
        try:
            # Clean up any stale worktree reference
            runner(["git", "worktree", "prune"], cache_dir, 30)
        except Exception:
            pass
        runner(["git", "worktree", "add", "--detach", str(destination), base_commit], cache_dir, timeout_seconds)
        runner(["git", "config", "user.email", "evals@hermes.local"], destination, timeout_seconds)
        runner(["git", "config", "user.name", "Hermes Evals"], destination, timeout_seconds)

        _log(task_name, f"Workspace ready in {time.monotonic() - started:.0f}s")

        return PreparedWorkspace(
            path=str(destination),
            eval_name=task_name,
            initial_commit_sha=base_commit,
            metadata={
                "repo": repo,
                "base_commit": base_commit,
                "instance_id": task_name,
                "fail_to_pass": instance.get("FAIL_TO_PASS", "[]"),
            },
        )

    def read_prompt(self, task_name: str, source_root: str | Path) -> str:
        instance = self._instances.get(task_name)
        if not instance:
            self._load_dataset()
            instance = self._instances.get(task_name)
        if not instance:
            raise FileNotFoundError(f"SWE-bench instance not found: {task_name}")

        problem = instance["problem_statement"]
        hints = instance.get("hints_text", "")
        repo = instance["repo"]

        # Parse FAIL_TO_PASS test IDs
        fail_to_pass_raw = instance.get("FAIL_TO_PASS", "[]")
        if isinstance(fail_to_pass_raw, str):
            try:
                fail_to_pass = json.loads(fail_to_pass_raw)
            except json.JSONDecodeError:
                fail_to_pass = []
        else:
            fail_to_pass = fail_to_pass_raw or []

        prompt = f"""You are fixing a bug in the {repo} repository.

## Issue Description

{problem}
"""
        if hints and hints.strip():
            prompt += f"""
## Hints

{hints}
"""
        prompt += """
## Instructions

1. Read the issue carefully and understand the problem.
2. Find the relevant source files in the repository.
3. Make the minimal code changes needed to fix the issue.
4. Do NOT modify or add test files — only edit source code.
5. After making changes, run the verification tests listed below to confirm your fix works.
"""
        if fail_to_pass:
            test_list = "\n".join(f"  - `{t}`" for t in fail_to_pass[:10])
            prompt += f"""
## Required Verification (MUST be the final task in your plan)

These existing tests must pass after your fix:
{test_list}

Your plan MUST include a final task that runs these tests against your changes. Run the repo's existing test suite — do NOT create new test files. If any test fails, read the error, fix your code, and re-run until they pass. Do not consider the task complete until these tests pass.
"""
        return prompt

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
        from evals.run_evals import _log

        workspace_path = Path(prepared.path).expanduser().resolve()
        instance_id = prepared.metadata.get("instance_id", prepared.eval_name)
        base_commit = prepared.metadata.get("base_commit", prepared.initial_commit_sha)
        patch_only = getattr(config, "swebench_patch_only", False)

        # Capture the patch (git diff from base_commit)
        # Filter to only planned files — executor may fix unrelated infra issues
        # (e.g., cloudpickle Python 3.11 compat) that contaminate the patch
        planned_files = _extract_planned_files(workspace_path)
        diff_cmd = ["git", "diff", "--text", base_commit]
        if planned_files:
            diff_cmd.append("--")
            diff_cmd.extend(planned_files)
        diff_result = subprocess.run(
            diff_cmd,
            cwd=workspace_path,
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
        )
        model_patch = diff_result.stdout.strip()
        # Ensure patch ends with newline — SWE-bench rejects "malformed" patches without one
        if model_patch and not model_patch.endswith("\n"):
            model_patch += "\n"
        if not model_patch and planned_files:
            # Fallback to full diff if filtered diff is empty (files_changed might be wrong)
            diff_result = subprocess.run(
                ["git", "diff", "--text", base_commit],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                errors="replace",
                check=False,
            )
            model_patch = diff_result.stdout.strip()
            if model_patch and not model_patch.endswith("\n"):
                model_patch += "\n"

        if not model_patch:
            _log(instance_id, "No code changes made — scoring as failed")
            return ScoringResult(
                status="failed",
                test_result={"success": False, "reason": "no_patch", "patch": ""},
                notes=["No code changes were made by the executor"],
            )

        _log(instance_id, f"Patch: {len(model_patch)} chars, {model_patch.count(chr(10))+1} lines")

        # Write predictions JSONL for SWE-bench evaluation
        prediction = {
            "instance_id": instance_id,
            "model_name_or_path": config.models.get("execute", "hermes"),
            "model_patch": model_patch,
        }
        predictions_dir_value = getattr(config, "predictions_dir", "")
        if predictions_dir_value:
            predictions_dir = Path(predictions_dir_value).expanduser().resolve()
        else:
            predictions_dir = workspace_path.parent / "_swebench_predictions"
        predictions_dir.mkdir(parents=True, exist_ok=True)
        predictions_path = predictions_dir / f"{instance_id}.jsonl"
        with open(predictions_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(prediction) + "\n")

        # In patch-only mode, skip Docker scoring — just return the patch
        if patch_only:
            _log(instance_id, f"Patch-only mode: saved {len(model_patch)} chars to {predictions_path}")
            return ScoringResult(
                status="passed",  # Provisional — real scoring happens in batch later
                test_result={
                    "success": None,  # Unknown until batch scoring
                    "patch": model_patch,
                    "patch_lines": model_patch.count("\n") + 1,
                    "instance_id": instance_id,
                    "predictions_path": str(predictions_path),
                    "scoring": "deferred",
                },
                notes=[f"patch_lines={model_patch.count(chr(10))+1}", "scoring=deferred"],
            )

        # Run SWE-bench evaluation
        _log(instance_id, "Running SWE-bench evaluation (Docker)...")
        eval_timeout = getattr(config, "test_timeout", 600)
        score_run_id = f"hermes-{instance_id}"
        try:
            eval_result = subprocess.run(
                [
                    "python", "-m", "swebench.harness.run_evaluation",
                    "--predictions_path", str(predictions_path),
                    "--instance_ids", instance_id,
                    "--max_workers", "1",
                    "--run_id", score_run_id,
                    "--namespace", "",  # Build locally on macOS ARM
                ],
                capture_output=True,
                text=True,
                timeout=eval_timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            _log(instance_id, f"SWE-bench evaluation timed out after {eval_timeout}s")
            stdout = self._normalize_stream(exc.stdout)
            stderr = self._normalize_stream(exc.stderr)
            return ScoringResult(
                status="error",
                test_result={
                    "success": False,
                    "reason": "timeout",
                    "patch": model_patch,
                    "stdout": stdout,
                    "stderr": stderr + f"\nTimed out after {eval_timeout}s",
                },
                notes=[f"SWE-bench evaluation timed out after {eval_timeout}s"],
            )

        # Parse results
        resolved = self._check_resolved(instance_id, eval_result, run_id=score_run_id)
        status = "passed" if resolved else "failed"

        test_result = {
            "success": resolved,
            "returncode": eval_result.returncode,
            "stdout": eval_result.stdout[-2000:] if eval_result.stdout else "",
            "stderr": eval_result.stderr[-2000:] if eval_result.stderr else "",
            "patch": model_patch,
            "patch_lines": model_patch.count("\n") + 1,
            "instance_id": instance_id,
        }

        _log(instance_id, f"SWE-bench: {'RESOLVED' if resolved else 'FAILED'}")

        # Clean up Docker images to free disk space for next task
        self._cleanup_docker_images(instance_id)

        return ScoringResult(
            status=status,
            test_result=test_result,
            notes=[f"patch_lines={test_result['patch_lines']}"],
        )

    def verify_after_execute(self, prepared, config) -> VerifyResult | None:
        from evals.run_evals import _log

        workspace_path = Path(prepared.path).expanduser().resolve()
        instance_id = prepared.metadata.get("instance_id", prepared.eval_name)
        base_commit = prepared.metadata.get("base_commit", prepared.initial_commit_sha)
        tests_run = self._parse_fail_to_pass(prepared.metadata.get("fail_to_pass", "[]"))
        if not tests_run:
            return None

        diff_started = time.monotonic()
        diff_result = subprocess.run(
            ["git", "diff", "--text", base_commit],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
        )
        model_patch = diff_result.stdout.strip()
        if model_patch and not model_patch.endswith("\n"):
            model_patch += "\n"
        diff_elapsed = time.monotonic() - diff_started
        if not model_patch:
            return VerifyResult(
                passed=False,
                test_output="No code changes were made by the executor.",
                tests_run=tests_run,
                duration_seconds=diff_elapsed,
            )

        verify_dir = workspace_path.parent / "_swebench_verify"
        verify_dir.mkdir(parents=True, exist_ok=True)
        predictions_path = verify_dir / f"{instance_id}.jsonl"
        prediction = {
            "instance_id": instance_id,
            "model_name_or_path": config.models.get("execute", "hermes"),
            "model_patch": model_patch,
        }
        predictions_path.write_text(json.dumps(prediction) + "\n", encoding="utf-8")

        verify_run_id = f"hermes-verify-{instance_id}"
        self._cleanup_run_artifacts(verify_run_id)

        _log(instance_id, f"Verify: running {len(tests_run)} FAIL_TO_PASS targets", phase="verify")
        started = time.monotonic()
        eval_timeout = getattr(config, "test_timeout", 600)
        try:
            eval_result = subprocess.run(
                [
                    "python", "-m", "swebench.harness.run_evaluation",
                    "--predictions_path", str(predictions_path),
                    "--instance_ids", instance_id,
                    "--max_workers", "1",
                    "--run_id", verify_run_id,
                    "--namespace", "",
                ],
                capture_output=True,
                text=True,
                timeout=eval_timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            output = self._combine_output(
                self._normalize_stream(exc.stdout),
                self._normalize_stream(exc.stderr),
                extra=f"Timed out after {eval_timeout}s",
            )
            return VerifyResult(
                passed=False,
                test_output=output,
                tests_run=tests_run,
                duration_seconds=time.monotonic() - started,
            )

        output = self._combine_output(eval_result.stdout, eval_result.stderr)
        passed = self._check_resolved(instance_id, eval_result, run_id=verify_run_id)
        return VerifyResult(
            passed=passed,
            test_output=output,
            tests_run=tests_run,
            duration_seconds=time.monotonic() - started,
        )

    def capture_environment(self, source_root: str | Path) -> dict[str, Any]:
        from evals.config import capture_environment

        env = capture_environment(
            benchmark_source_root=source_root,
            benchmark_name="swe-bench",
        )
        try:
            import swebench
            env.setdefault("runtime", {})["swebench"] = {
                "version": getattr(swebench, "__version__", "unknown"),
            }
        except ImportError:
            env.setdefault("runtime", {})["swebench"] = {"version": None, "error": "not installed"}
        return env

    def megaplan_env_overrides(self, prepared) -> dict[str, str]:
        return {}

    def cleanup_workspace(self, prepared) -> None:
        workspace = Path(prepared.path)
        # Remove worktree via git if it's a worktree, otherwise just rmtree
        repo = prepared.metadata.get("repo", "")
        if repo:
            repo_cache_name = repo.replace("/", "__")
            cache_dir = workspace.parent.parent / "_repo_cache" / repo_cache_name
            if cache_dir.exists():
                try:
                    subprocess.run(
                        ["git", "worktree", "remove", "--force", str(workspace)],
                        cwd=cache_dir, capture_output=True, check=False, timeout=30,
                    )
                except Exception:
                    pass
        # Fallback: force delete if worktree remove didn't clean it
        if workspace.exists():
            shutil.rmtree(workspace, ignore_errors=True)
        # Clean up Hermes session files to save disk
        self._cleanup_hermes_sessions()

    @staticmethod
    def _cleanup_hermes_sessions() -> None:
        """Remove Hermes session files to free disk. Sessions aren't needed after scoring."""
        hermes_home = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
        sessions_dir = hermes_home / "sessions"
        if not sessions_dir.exists():
            return
        try:
            for f in sessions_dir.glob("session_*.json"):
                f.unlink(missing_ok=True)
        except Exception:
            pass

    @staticmethod
    def _cleanup_docker_images(instance_id: str) -> None:
        """Remove instance-specific SWE-bench Docker images, keeping the base image."""
        from evals.run_evals import _log

        # Base images are expensive to rebuild — keep them
        KEEP_PREFIXES = ("sweb.base.", "sweb.env.")

        try:
            result = subprocess.run(
                ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}", "--filter", "reference=*sweb*"],
                capture_output=True, text=True, check=False,
            )
            all_images = [img.strip() for img in result.stdout.splitlines() if img.strip()]
            # Only remove instance-level images, keep base and env
            to_remove = [img for img in all_images if not any(img.startswith(p) for p in KEEP_PREFIXES)]

            if to_remove:
                _log(instance_id, f"Cleaning {len(to_remove)} instance Docker images (keeping {len(all_images)-len(to_remove)} base/env)...", dim=True)
                subprocess.run(
                    ["docker", "rmi", "-f", *to_remove],
                    capture_output=True, text=True, check=False, timeout=120,
                )

            # Prune dangling images
            subprocess.run(
                ["docker", "image", "prune", "-f"],
                capture_output=True, text=True, check=False, timeout=60,
            )
        except Exception:
            pass  # Best-effort cleanup

    @staticmethod
    def _cleanup_run_artifacts(run_id: str) -> None:
        for results_dir in [Path("evaluation_results"), Path("logs/run_evaluation")]:
            if not results_dir.exists():
                continue
            matches = [path for path in results_dir.rglob("*") if run_id in str(path)]
            for path in sorted(matches, key=lambda item: len(item.parts), reverse=True):
                try:
                    if path.is_file() or path.is_symlink():
                        path.unlink(missing_ok=True)
                    elif path.is_dir():
                        shutil.rmtree(path, ignore_errors=True)
                except OSError:
                    continue

    @staticmethod
    def _check_resolved(
        instance_id: str,
        eval_result: subprocess.CompletedProcess,
        *,
        run_id: str | None = None,
    ) -> bool:
        """Check if the instance was resolved by parsing SWE-bench output."""
        combined = (eval_result.stdout or "") + (eval_result.stderr or "")

        # Look for the results JSON or resolution indicators
        if f"{instance_id}" in combined and "RESOLVED" in combined.upper():
            return True

        # Check evaluation results directory
        for results_dir in [Path("evaluation_results"), Path("logs/run_evaluation")]:
            if not results_dir.exists():
                continue
            for json_file in results_dir.rglob("*.json"):
                if run_id and run_id not in str(json_file):
                    continue
                try:
                    data = json.loads(json_file.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        resolved = data.get("resolved", data.get("resolved_ids", []))
                        if isinstance(resolved, list) and instance_id in resolved:
                            return True
                        if isinstance(resolved, bool) and resolved:
                            return True
                except (json.JSONDecodeError, OSError):
                    continue

        return False

    @staticmethod
    def _parse_fail_to_pass(raw_value: Any) -> list[str]:
        if isinstance(raw_value, str):
            text = raw_value.strip()
            if not text:
                return []
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return [text]
        elif isinstance(raw_value, list):
            parsed = raw_value
        else:
            return []
        if not isinstance(parsed, list):
            return []
        return [str(item) for item in parsed if str(item)]

    @staticmethod
    def _normalize_stream(stream: str | bytes | None) -> str:
        if isinstance(stream, bytes):
            return stream.decode("utf-8", errors="replace")
        return stream or ""

    @classmethod
    def _combine_output(
        cls,
        stdout: str | bytes | None,
        stderr: str | bytes | None,
        *,
        extra: str | None = None,
    ) -> str:
        parts = [cls._normalize_stream(stdout).strip(), cls._normalize_stream(stderr).strip()]
        if extra:
            parts.append(extra.strip())
        return "\n\n".join(part for part in parts if part)
