import json
import subprocess
from pathlib import Path

import pytest

from evals.config import EvalConfig, capture_environment, load_config


def _git_init_with_commit(path: Path) -> str:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.email", "tests@hermes.local"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Hermes Tests"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    (path / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def test_load_config_applies_defaults(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "models": {
                    "plan": "p",
                    "critique": "c",
                    "revise": "r",
                    "gate": "g",
                    "finalize": "f",
                    "execute": "e",
                    "review": "rv",
                }
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.max_gate_iterations == 3
    assert config.eval_timeout_seconds == 600
    assert config.max_verify_attempts == 3
    assert config.evals_to_run == []
    assert config.next_evals_ref == "main"
    assert config.openrouter_params == {}
    assert config.megaplan_bin == "megaplan"
    assert config.workspace_dir
    assert config.results_dir


def test_eval_config_requires_revise_model():
    with pytest.raises(ValueError, match="missing: revise"):
        EvalConfig(
            models={
                "plan": "p",
                "critique": "c",
                "gate": "g",
                "finalize": "f",
                "execute": "e",
                "review": "rv",
            }
        )


def test_capture_environment_returns_git_shas_for_all_repos(tmp_path):
    hermes_root = tmp_path / "hermes"
    megaplan_root = tmp_path / "megaplan"
    next_evals_root = tmp_path / "next-evals-oss"

    hermes_sha = _git_init_with_commit(hermes_root)
    megaplan_sha = _git_init_with_commit(megaplan_root)
    next_evals_sha = _git_init_with_commit(next_evals_root)

    environment = capture_environment(
        hermes_root=hermes_root,
        megaplan_root=megaplan_root,
        next_evals_root=next_evals_root,
    )

    repos = environment["repos"]
    assert repos["hermes-agent"]["git_sha"] == hermes_sha
    assert repos["megaplan"]["git_sha"] == megaplan_sha
    assert repos["next-evals-oss"]["git_sha"] == next_evals_sha
    assert repos["hermes-agent"]["exists"] is True
    assert environment["runtime"]["python"]["version"]
    assert "platform" in environment["os"]
