from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.chain import run_chain_cli
from arnold_pipelines.megaplan.chain.spec import (
    ChainSpec,
    ChainState,
    save_chain_state,
    validate_paths,
)
from arnold_pipelines.megaplan.types import CliError


def _write_chain(tmp_path: Path, body: str) -> Path:
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text(body, encoding="utf-8")
    return spec_path


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _commit_all(root: Path, message: str = "test") -> None:
    _git(root, "add", ".")
    _git(root, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", message)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_launch_preconditions_reject_unknown_keys() -> None:
    with pytest.raises(CliError, match="unknown key `unexpected`"):
        ChainSpec.from_dict(
            {
                "launch_preconditions": [
                    {
                        "name": "artifact",
                        "path": "artifact.md",
                        "unexpected": True,
                    }
                ],
                "milestones": [],
            }
        )


def test_failure_policy_rejects_unknown_nested_keys() -> None:
    with pytest.raises(CliError, match="unknown key `then`"):
        ChainSpec.from_dict(
            {
                "on_failure": {
                    "retry": "retry_milestone",
                    "then": "escalate_with_artifacts",
                    "abort": "stop_chain",
                },
                "milestones": [],
            }
        )


def test_launch_precondition_missing_artifact_fails(tmp_path: Path) -> None:
    spec_path = _write_chain(
        tmp_path,
        """
launch_preconditions:
  - name: required artifact
    path: missing.md
milestones: []
""",
    )
    spec = ChainSpec.from_dict(
        {
            "launch_preconditions": [
                {"name": "required artifact", "path": "missing.md"}
            ],
            "milestones": [],
        }
    )

    with pytest.raises(CliError, match="required artifact missing"):
        validate_paths(spec, tmp_path, spec_path=spec_path)


def test_launch_precondition_contains_text_fails_and_passes(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.md"
    artifact.write_text("# Artifact\n\nwrong text\n", encoding="utf-8")
    spec_path = _write_chain(tmp_path, "milestones: []\n")
    spec = ChainSpec.from_dict(
        {
            "launch_preconditions": [
                {
                    "name": "marker",
                    "path": "artifact.md",
                    "check": {"kind": "contains_text", "text": "right text"},
                }
            ],
            "milestones": [],
        }
    )

    with pytest.raises(CliError, match="does not contain required text"):
        validate_paths(spec, tmp_path, spec_path=spec_path)

    artifact.write_text("# Artifact\n\nright text\n", encoding="utf-8")
    validate_paths(spec, tmp_path, spec_path=spec_path)


def test_launch_precondition_review_log_clean_fails_on_block_and_unaddressed_edit(tmp_path: Path) -> None:
    review_log = tmp_path / "review.md"
    spec_path = _write_chain(tmp_path, "milestones: []\n")
    spec = ChainSpec.from_dict(
        {
            "launch_preconditions": [
                {
                    "name": "review log clean",
                    "path": "review.md",
                    "check": {"kind": "review_log_clean"},
                }
            ],
            "milestones": [],
        }
    )

    review_log.write_text(
        "## Review\n\n- H1 End-State Fit: `PASS WITH EDIT`.\n\nThe edits were applied:\n- fixed.\n",
        encoding="utf-8",
    )
    validate_paths(spec, tmp_path, spec_path=spec_path)

    review_log.write_text("## Review\n\n- H1 End-State Fit: `BLOCK`.\n", encoding="utf-8")
    with pytest.raises(CliError, match="blocking verdict"):
        validate_paths(spec, tmp_path, spec_path=spec_path)

    review_log.write_text("## Review\n\n- H1 End-State Fit: `PASS WITH EDIT`.\n", encoding="utf-8")
    with pytest.raises(CliError, match="unaddressed PASS WITH EDIT"):
        validate_paths(spec, tmp_path, spec_path=spec_path)


def test_git_tracked_precondition_rejects_untracked_file(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    tracked = tmp_path / "tracked.md"
    tracked.write_text("# Tracked\n", encoding="utf-8")
    _commit_all(tmp_path)
    untracked = tmp_path / "untracked.md"
    untracked.write_text("# Untracked\n", encoding="utf-8")
    spec_path = _write_chain(tmp_path, "milestones: []\n")
    spec = ChainSpec.from_dict(
        {
            "launch_preconditions": [
                {
                    "name": "tracked source",
                    "kind": "git_tracked",
                    "path": "untracked.md",
                }
            ],
            "milestones": [],
        }
    )

    with pytest.raises(CliError, match="not committed in HEAD"):
        validate_paths(spec, tmp_path, spec_path=spec_path)


def test_git_tracked_precondition_rejects_staged_only_file(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    staged = tmp_path / "staged.md"
    staged.write_text("# Staged only\n", encoding="utf-8")
    _git(tmp_path, "add", "staged.md")
    spec_path = _write_chain(tmp_path, "milestones: []\n")
    spec = ChainSpec.from_dict(
        {
            "launch_preconditions": [
                {
                    "name": "tracked source",
                    "kind": "git_tracked",
                    "path": "staged.md",
                }
            ],
            "milestones": [],
        }
    )

    with pytest.raises(CliError, match="not committed in HEAD"):
        validate_paths(spec, tmp_path, spec_path=spec_path)


def test_git_tracked_precondition_rejects_uncommitted_files_under_directory(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    required = tmp_path / "required"
    required.mkdir()
    (required / "tracked.md").write_text("# Tracked\n", encoding="utf-8")
    _commit_all(tmp_path)
    spec_path = _write_chain(tmp_path, "milestones: []\n")
    spec = ChainSpec.from_dict(
        {
            "launch_preconditions": [
                {
                    "name": "tracked directory",
                    "kind": "git_tracked",
                    "path": "required",
                }
            ],
            "milestones": [],
        }
    )

    validate_paths(spec, tmp_path, spec_path=spec_path)

    (required / "untracked.md").write_text("# Untracked\n", encoding="utf-8")
    with pytest.raises(CliError, match="required directory has uncommitted changes"):
        validate_paths(spec, tmp_path, spec_path=spec_path)

    (required / "untracked.md").unlink()
    (required / "tracked.md").write_text("# Modified\n", encoding="utf-8")
    with pytest.raises(CliError, match="required directory has uncommitted changes"):
        validate_paths(spec, tmp_path, spec_path=spec_path)


def test_chain_verify_enforces_launch_preconditions(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    spec_path = _write_chain(
        tmp_path,
        """
driver:
  require_anchor: false
  missing_anchor_ack: test chain without a north star
launch_preconditions:
  - name: required artifact
    path: missing.md
milestones: []
""",
    )

    exit_code = run_chain_cli(
        tmp_path,
        argparse.Namespace(
            chain_action="verify",
            spec=str(spec_path),
            project_dir=str(tmp_path),
        ),
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "launch_precondition_failed" in captured.out
    assert "required artifact missing" in captured.out


def test_chain_completed_precondition_fails_when_state_missing(tmp_path: Path) -> None:
    prereq_path = _write_chain(
        tmp_path,
        """
milestones:
  - label: m1
    idea: m1.md
""",
    )
    (tmp_path / "m1.md").write_text("# M1\n", encoding="utf-8")
    dependent_path = tmp_path / "dependent.yaml"
    dependent_path.write_text("milestones: []\n", encoding="utf-8")
    spec = ChainSpec.from_dict(
        {
            "launch_preconditions": [
                {
                    "name": "completion chain complete",
                    "kind": "chain_completed",
                    "chain": str(prereq_path.relative_to(tmp_path)),
                }
            ],
            "milestones": [],
        }
    )

    with pytest.raises(CliError, match="prerequisite chain state missing"):
        validate_paths(spec, tmp_path, spec_path=dependent_path)


def test_chain_completed_precondition_fails_when_milestone_incomplete(tmp_path: Path) -> None:
    prereq_path = _write_chain(
        tmp_path,
        """
milestones:
  - label: m1
    idea: m1.md
  - label: m2
    idea: m2.md
""",
    )
    (tmp_path / "m1.md").write_text("# M1\n", encoding="utf-8")
    (tmp_path / "m2.md").write_text("# M2\n", encoding="utf-8")
    save_chain_state(
        prereq_path,
        ChainState(
            current_milestone_index=2,
            completed=[{"label": "m1", "status": "done", "plan": "plan-m1"}],
        ),
    )
    dependent_path = tmp_path / "dependent.yaml"
    dependent_path.write_text("milestones: []\n", encoding="utf-8")
    spec = ChainSpec.from_dict(
        {
            "launch_preconditions": [
                {
                    "name": "completion chain complete",
                    "kind": "chain_completed",
                    "chain": str(prereq_path.relative_to(tmp_path)),
                }
            ],
            "milestones": [],
        }
    )

    with pytest.raises(CliError, match="missing milestones \\['m2'\\]"):
        validate_paths(spec, tmp_path, spec_path=dependent_path)


def test_chain_completed_precondition_fails_on_stale_hash(tmp_path: Path) -> None:
    prereq_path = _write_chain(
        tmp_path,
        """
milestones:
  - label: m1
    idea: m1.md
""",
    )
    (tmp_path / "m1.md").write_text("# M1\n", encoding="utf-8")
    save_chain_state(
        prereq_path,
        ChainState(
            current_milestone_index=1,
            completed=[{"label": "m1", "status": "done", "plan": "plan-m1"}],
        ),
    )
    prereq_path.write_text(
        """
milestones:
  - label: m1
    idea: m1.md
  - label: m2
    idea: m2.md
""",
        encoding="utf-8",
    )
    (tmp_path / "m2.md").write_text("# M2\n", encoding="utf-8")
    dependent_path = tmp_path / "dependent.yaml"
    dependent_path.write_text("milestones: []\n", encoding="utf-8")
    spec = ChainSpec.from_dict(
        {
            "launch_preconditions": [
                {
                    "name": "completion chain complete",
                    "kind": "chain_completed",
                    "chain": str(prereq_path.relative_to(tmp_path)),
                }
            ],
            "milestones": [],
        }
    )

    with pytest.raises(CliError, match="state hash is stale"):
        validate_paths(spec, tmp_path, spec_path=dependent_path)


def test_chain_completed_precondition_fails_without_plan_evidence(tmp_path: Path) -> None:
    prereq_path = _write_chain(
        tmp_path,
        """
milestones:
  - label: m1
    idea: m1.md
""",
    )
    (tmp_path / "m1.md").write_text("# M1\n", encoding="utf-8")
    save_chain_state(
        prereq_path,
        ChainState(
            current_milestone_index=1,
            completed=[{"label": "m1", "status": "done"}],
        ),
    )
    dependent_path = tmp_path / "dependent.yaml"
    dependent_path.write_text("milestones: []\n", encoding="utf-8")
    spec = ChainSpec.from_dict(
        {
            "launch_preconditions": [
                {
                    "name": "completion chain complete",
                    "kind": "chain_completed",
                    "chain": str(prereq_path.relative_to(tmp_path)),
                }
            ],
            "milestones": [],
        }
    )

    with pytest.raises(CliError, match="has no plan name"):
        validate_paths(spec, tmp_path, spec_path=dependent_path)


def test_chain_completed_precondition_fails_on_finalized_status(tmp_path: Path) -> None:
    prereq_path = _write_chain(
        tmp_path,
        """
milestones:
  - label: m1
    idea: m1.md
""",
    )
    (tmp_path / "m1.md").write_text("# M1\n", encoding="utf-8")
    save_chain_state(
        prereq_path,
        ChainState(
            current_milestone_index=1,
            completed=[{"label": "m1", "status": "finalized", "plan": "plan-m1"}],
        ),
    )
    dependent_path = tmp_path / "dependent.yaml"
    dependent_path.write_text("milestones: []\n", encoding="utf-8")
    spec = ChainSpec.from_dict(
        {
            "launch_preconditions": [
                {
                    "name": "completion chain complete",
                    "kind": "chain_completed",
                    "chain": str(prereq_path.relative_to(tmp_path)),
                }
            ],
            "milestones": [],
        }
    )

    with pytest.raises(CliError, match="missing milestones \\['m1'\\]"):
        validate_paths(spec, tmp_path, spec_path=dependent_path)


def test_chain_completed_precondition_fails_when_review_policy_lacks_merged_pr(tmp_path: Path) -> None:
    prereq_path = _write_chain(
        tmp_path,
        """
merge_policy: review
milestones:
  - label: m1
    idea: m1.md
""",
    )
    (tmp_path / "m1.md").write_text("# M1\n", encoding="utf-8")
    save_chain_state(
        prereq_path,
        ChainState(
            current_milestone_index=1,
            completed=[{"label": "m1", "status": "done", "plan": "plan-m1"}],
        ),
    )
    dependent_path = tmp_path / "dependent.yaml"
    dependent_path.write_text("milestones: []\n", encoding="utf-8")
    spec = ChainSpec.from_dict(
        {
            "launch_preconditions": [
                {
                    "name": "completion chain complete",
                    "kind": "chain_completed",
                    "chain": str(prereq_path.relative_to(tmp_path)),
                }
            ],
            "milestones": [],
        }
    )

    with pytest.raises(CliError, match="requires merged PR evidence"):
        validate_paths(spec, tmp_path, spec_path=dependent_path)


def test_review_chain_completed_precondition_without_manifest_rejects_publication_fallback(tmp_path: Path) -> None:
    prereq_path = _write_chain(
        tmp_path,
        """
merge_policy: review
milestones:
  - label: m1
    idea: m1.md
""",
    )
    (tmp_path / "m1.md").write_text("# M1\n", encoding="utf-8")
    save_chain_state(
        prereq_path,
        ChainState(
            current_milestone_index=1,
            completed=[
                {
                    "label": "m1",
                    "status": "done",
                    "plan": "plan-m1",
                    "publication_evidence": "chain_state_only",
                }
            ],
        ),
    )
    dependent_path = tmp_path / "dependent.yaml"
    dependent_path.write_text("milestones: []\n", encoding="utf-8")
    spec = ChainSpec.from_dict(
        {
            "launch_preconditions": [
                {
                    "name": "completion chain complete",
                    "kind": "chain_completed",
                    "chain": str(prereq_path.relative_to(tmp_path)),
                }
            ],
            "milestones": [],
        }
    )

    with pytest.raises(CliError, match="requires merged PR evidence"):
        validate_paths(spec, tmp_path, spec_path=dependent_path)


def test_chain_completed_precondition_passes_when_all_current_milestones_done(tmp_path: Path) -> None:
    prereq_path = _write_chain(
        tmp_path,
        """
milestones:
  - label: m1
    idea: m1.md
  - label: m2
    idea: m2.md
""",
    )
    (tmp_path / "m1.md").write_text("# M1\n", encoding="utf-8")
    (tmp_path / "m2.md").write_text("# M2\n", encoding="utf-8")
    save_chain_state(
        prereq_path,
        ChainState(
            current_milestone_index=2,
            completed=[
                {"label": "m1", "status": "done", "plan": "plan-m1"},
                {"label": "m2", "status": "done", "plan": "plan-m2"},
            ]
        ),
    )
    dependent_path = tmp_path / "dependent.yaml"
    dependent_path.write_text("milestones: []\n", encoding="utf-8")
    spec = ChainSpec.from_dict(
        {
            "launch_preconditions": [
                {
                    "name": "completion chain complete",
                    "kind": "chain_completed",
                    "chain": str(prereq_path.relative_to(tmp_path)),
                }
            ],
            "milestones": [],
        }
    )

    validate_paths(spec, tmp_path, spec_path=dependent_path)


def test_chain_completed_require_manifest_must_be_boolean() -> None:
    with pytest.raises(CliError, match="require_manifest must be a boolean"):
        ChainSpec.from_dict(
            {
                "launch_preconditions": [
                    {
                        "name": "completion chain complete",
                        "kind": "chain_completed",
                        "chain": "chain.yaml",
                        "require_manifest": "yes",
                    }
                ],
                "milestones": [],
            }
        )


def test_chain_completed_require_manifest_fails_when_manifest_missing(tmp_path: Path) -> None:
    prereq_path = _write_chain(
        tmp_path,
        """
milestones:
  - label: m1
    idea: m1.md
""",
    )
    (tmp_path / "m1.md").write_text("# M1\n", encoding="utf-8")
    save_chain_state(
        prereq_path,
        ChainState(
            current_milestone_index=1,
            completed=[{"label": "m1", "status": "done", "plan": "plan-m1"}],
        ),
    )
    dependent_path = tmp_path / "dependent.yaml"
    dependent_path.write_text("milestones: []\n", encoding="utf-8")
    spec = ChainSpec.from_dict(
        {
            "launch_preconditions": [
                {
                    "name": "completion chain complete",
                    "kind": "chain_completed",
                    "chain": str(prereq_path.relative_to(tmp_path)),
                    "require_manifest": True,
                }
            ],
            "milestones": [],
        }
    )

    with pytest.raises(CliError, match="completion manifest missing"):
        validate_paths(spec, tmp_path, spec_path=dependent_path)


def _write_completion_manifest(
    root: Path,
    chain_path: Path,
    *,
    plan: str = "plan-m1",
    brief_sha256: str | None = None,
    proof_sha256: str | None = None,
) -> None:
    proof_path = root / "proof.md"
    if not proof_path.exists():
        proof_path.write_text("# Proof\n", encoding="utf-8")
    brief_path = root / "m1.md"
    manifest = {
        "schema": "arnold.megaplan.chain_completion_manifest.v1",
        "chain": {
            "path": str(chain_path.relative_to(root)),
            "sha256": _sha256(chain_path),
        },
        "milestones": [
            {
                "label": "m1",
                "brief_path": "m1.md",
                "brief_sha256": brief_sha256 or _sha256(brief_path),
                "status": "done",
                "plan": plan,
                "proof_artifacts": [
                    {
                        "path": "proof.md",
                        "sha256": proof_sha256 or _sha256(proof_path),
                    }
                ],
            }
        ],
    }
    chain_path.with_name("completion-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


def test_chain_completed_require_manifest_passes_with_matching_hashes(tmp_path: Path) -> None:
    prereq_path = _write_chain(
        tmp_path,
        """
milestones:
  - label: m1
    idea: m1.md
""",
    )
    (tmp_path / "m1.md").write_text("# M1\n", encoding="utf-8")
    _write_completion_manifest(tmp_path, prereq_path)
    save_chain_state(
        prereq_path,
        ChainState(
            current_milestone_index=1,
            completed=[{"label": "m1", "status": "done", "plan": "plan-m1"}],
        ),
    )
    dependent_path = tmp_path / "dependent.yaml"
    dependent_path.write_text("milestones: []\n", encoding="utf-8")
    spec = ChainSpec.from_dict(
        {
            "launch_preconditions": [
                {
                    "name": "completion chain complete",
                    "kind": "chain_completed",
                    "chain": str(prereq_path.relative_to(tmp_path)),
                    "require_manifest": True,
                }
            ],
            "milestones": [],
        }
    )

    validate_paths(spec, tmp_path, spec_path=dependent_path)


def test_review_chain_completed_require_manifest_accepts_explicit_publication_fallback(tmp_path: Path) -> None:
    prereq_path = _write_chain(
        tmp_path,
        """
merge_policy: review
milestones:
  - label: m1
    idea: m1.md
""",
    )
    (tmp_path / "m1.md").write_text("# M1\n", encoding="utf-8")
    _write_completion_manifest(tmp_path, prereq_path)
    manifest_path = prereq_path.with_name("completion-manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["milestones"][0]["publication_evidence"] = "chain_state_only"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    save_chain_state(
        prereq_path,
        ChainState(
            current_milestone_index=1,
            completed=[
                {
                    "label": "m1",
                    "status": "done",
                    "plan": "plan-m1",
                    "publication_evidence": "chain_state_only",
                }
            ],
        ),
    )
    dependent_path = tmp_path / "dependent.yaml"
    dependent_path.write_text("milestones: []\n", encoding="utf-8")
    spec = ChainSpec.from_dict(
        {
            "launch_preconditions": [
                {
                    "name": "completion chain complete",
                    "kind": "chain_completed",
                    "chain": str(prereq_path.relative_to(tmp_path)),
                    "require_manifest": True,
                }
            ],
            "milestones": [],
        }
    )

    validate_paths(spec, tmp_path, spec_path=dependent_path)


def test_chain_completed_require_manifest_rejects_stale_brief_hash(tmp_path: Path) -> None:
    prereq_path = _write_chain(
        tmp_path,
        """
milestones:
  - label: m1
    idea: m1.md
""",
    )
    brief_path = tmp_path / "m1.md"
    brief_path.write_text("# M1\n", encoding="utf-8")
    _write_completion_manifest(tmp_path, prereq_path)
    brief_path.write_text("# M1 changed\n", encoding="utf-8")
    save_chain_state(
        prereq_path,
        ChainState(
            current_milestone_index=1,
            completed=[{"label": "m1", "status": "done", "plan": "plan-m1"}],
        ),
    )
    dependent_path = tmp_path / "dependent.yaml"
    dependent_path.write_text("milestones: []\n", encoding="utf-8")
    spec = ChainSpec.from_dict(
        {
            "launch_preconditions": [
                {
                    "name": "completion chain complete",
                    "kind": "chain_completed",
                    "chain": str(prereq_path.relative_to(tmp_path)),
                    "require_manifest": True,
                }
            ],
            "milestones": [],
        }
    )

    with pytest.raises(CliError, match="hash mismatch for m1.md"):
        validate_paths(spec, tmp_path, spec_path=dependent_path)


def test_chain_completed_require_manifest_rejects_stale_proof_hash(tmp_path: Path) -> None:
    prereq_path = _write_chain(
        tmp_path,
        """
milestones:
  - label: m1
    idea: m1.md
""",
    )
    (tmp_path / "m1.md").write_text("# M1\n", encoding="utf-8")
    proof_path = tmp_path / "proof.md"
    proof_path.write_text("# Proof\n", encoding="utf-8")
    _write_completion_manifest(tmp_path, prereq_path)
    proof_path.write_text("# Proof changed\n", encoding="utf-8")
    save_chain_state(
        prereq_path,
        ChainState(
            current_milestone_index=1,
            completed=[{"label": "m1", "status": "done", "plan": "plan-m1"}],
        ),
    )
    dependent_path = tmp_path / "dependent.yaml"
    dependent_path.write_text("milestones: []\n", encoding="utf-8")
    spec = ChainSpec.from_dict(
        {
            "launch_preconditions": [
                {
                    "name": "completion chain complete",
                    "kind": "chain_completed",
                    "chain": str(prereq_path.relative_to(tmp_path)),
                    "require_manifest": True,
                }
            ],
            "milestones": [],
        }
    )

    with pytest.raises(CliError, match="hash mismatch for proof.md"):
        validate_paths(spec, tmp_path, spec_path=dependent_path)


def test_chain_manifest_command_writes_manifest_that_satisfies_precondition(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    prereq_path = _write_chain(
        tmp_path,
        """
milestones:
  - label: m1
    idea: m1.md
""",
    )
    (tmp_path / "m1.md").write_text("# M1\n", encoding="utf-8")
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    (tmp_path / "proof-map.json").write_text(
        json.dumps({"m1": ["proof.md"]}) + "\n",
        encoding="utf-8",
    )
    save_chain_state(
        prereq_path,
        ChainState(
            current_milestone_index=1,
            completed=[{"label": "m1", "status": "done", "plan": "plan-m1"}],
        ),
    )

    rc = run_chain_cli(
        tmp_path,
        argparse.Namespace(
            chain_action="manifest",
            spec=str(prereq_path),
            project_dir=str(tmp_path),
            proof_map="proof-map.json",
            output=None,
        ),
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    manifest_path = Path(payload["manifest"])
    assert manifest_path == prereq_path.with_name("completion-manifest.json")
    assert payload["manifest_sha256"] == _sha256(manifest_path)

    dependent_path = tmp_path / "dependent.yaml"
    dependent_path.write_text("milestones: []\n", encoding="utf-8")
    spec = ChainSpec.from_dict(
        {
            "launch_preconditions": [
                {
                    "name": "completion chain complete",
                    "kind": "chain_completed",
                    "chain": str(prereq_path.relative_to(tmp_path)),
                    "require_manifest": True,
                }
            ],
            "milestones": [],
        }
    )
    validate_paths(spec, tmp_path, spec_path=dependent_path)


def test_review_chain_manifest_command_writes_explicit_publication_fallback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    prereq_path = _write_chain(
        tmp_path,
        """
merge_policy: review
milestones:
  - label: m1
    idea: m1.md
""",
    )
    (tmp_path / "m1.md").write_text("# M1\n", encoding="utf-8")
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    (tmp_path / "proof-map.json").write_text(
        json.dumps({"m1": ["proof.md"]}) + "\n",
        encoding="utf-8",
    )
    save_chain_state(
        prereq_path,
        ChainState(
            current_milestone_index=1,
            completed=[
                {
                    "label": "m1",
                    "status": "done",
                    "plan": "plan-m1",
                    "publication_evidence": "chain_state_only",
                }
            ],
        ),
    )

    rc = run_chain_cli(
        tmp_path,
        argparse.Namespace(
            chain_action="manifest",
            spec=str(prereq_path),
            project_dir=str(tmp_path),
            proof_map="proof-map.json",
            output=None,
        ),
    )

    assert rc == 0
    capsys.readouterr()
    manifest = json.loads(
        prereq_path.with_name("completion-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["milestones"][0]["publication_evidence"] == "chain_state_only"


def test_chain_manifest_command_requires_explicit_proof_for_every_milestone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    prereq_path = _write_chain(
        tmp_path,
        """
milestones:
  - label: m1
    idea: m1.md
  - label: m2
    idea: m2.md
""",
    )
    (tmp_path / "m1.md").write_text("# M1\n", encoding="utf-8")
    (tmp_path / "m2.md").write_text("# M2\n", encoding="utf-8")
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    (tmp_path / "proof-map.json").write_text(
        json.dumps({"m1": ["proof.md"]}) + "\n",
        encoding="utf-8",
    )
    save_chain_state(
        prereq_path,
        ChainState(
            current_milestone_index=2,
            completed=[
                {"label": "m1", "status": "done", "plan": "plan-m1"},
                {"label": "m2", "status": "done", "plan": "plan-m2"},
            ],
        ),
    )

    rc = run_chain_cli(
        tmp_path,
        argparse.Namespace(
            chain_action="manifest",
            spec=str(prereq_path),
            project_dir=str(tmp_path),
            proof_map="proof-map.json",
            output=None,
        ),
    )

    assert rc != 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "invalid_args"
    assert "proof map missing proof artifacts for milestone 'm2'" in payload["message"]
