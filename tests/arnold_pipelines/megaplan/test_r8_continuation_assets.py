"""Asset admission checks for the Native Build Forward r8 continuation."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.chain.spec import ChainSpec, load_spec, validate_paths
from arnold_pipelines.megaplan.types import CliError


REPO_ROOT = Path(__file__).resolve().parents[3]
R8_RELATIVE = Path(
    ".megaplan/initiatives/native-build-forward-continuation-20260903-r8"
)
R8_SPEC = REPO_ROOT / R8_RELATIVE / "chain.yaml"


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_r8_all_launch_assets_are_tracked_and_present_at_head() -> None:
    """The pinned continuation cannot rely on ignored working-tree assets."""

    expected = {
        R8_RELATIVE / "chain.yaml",
        R8_RELATIVE / "NORTHSTAR.md",
        R8_RELATIVE / "cloud.yaml",
        *(
            R8_RELATIVE / "briefs" / name
            for name in (
                "native-c2-completion-evaluation.md",
                "native-s2r-durable-primitives.md",
                "native-s3a-plan-quality-cutover.md",
                "native-s3b-gate-revise-cutover.md",
                "native-s4-tiebreaker-finalize-reentry.md",
                "native-s5a-delivery-shadow.md",
                "native-s5b-live-delivery.md",
                "native-s6-control-plane.md",
                "native-s7-conformance.md",
                "platform-s1-inventory.md",
                "platform-s2a-runtime-authority.md",
                "platform-s2b-authoring-core.md",
                "platform-s3-developer-tooling.md",
                "platform-s4-recomposition.md",
                "platform-s5-second-consumer.md",
                "platform-s6-certification.md",
            )
        ),
    }
    spec = load_spec(R8_SPEC)
    tracked_preconditions = {
        Path(item.path)
        for item in spec.launch_preconditions
        if item.kind == "git_tracked" and item.path is not None
    }
    assert tracked_preconditions == expected
    assert len(tracked_preconditions) == 19

    # This exercises the same path validator used by chain verify/start.
    validate_paths(spec, REPO_ROOT, spec_path=R8_SPEC)

    for relative in sorted(expected):
        result = _git(REPO_ROOT, "cat-file", "-e", f"HEAD:{relative.as_posix()}")
        assert result.returncode == 0, result.stderr
        tree = _git(REPO_ROOT, "ls-tree", "-r", "--name-only", "HEAD", "--", relative.as_posix())
        assert tree.returncode == 0, tree.stderr
        assert tree.stdout.strip() == relative.as_posix()


def test_ignored_working_tree_asset_is_rejected_as_untracked(tmp_path: Path) -> None:
    """An ignored cloud file is not enough to satisfy a tracked precondition."""

    assert _git(tmp_path, "init").returncode == 0
    (tmp_path / ".gitignore").write_text("cloud.yaml\n", encoding="utf-8")
    cloud = tmp_path / "cloud.yaml"
    cloud.write_text("provider: ssh\n", encoding="utf-8")
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    assert _git(tmp_path, "add", ".gitignore", "chain.yaml").returncode == 0
    assert _git(
        tmp_path,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-m",
        "fixture",
    ).returncode == 0

    spec = ChainSpec.from_dict(
        {
            "launch_preconditions": [
                {"name": "cloud configuration", "kind": "git_tracked", "path": "cloud.yaml"}
            ],
            "milestones": [],
        }
    )
    with pytest.raises(CliError, match="not committed in HEAD"):
        validate_paths(spec, tmp_path, spec_path=spec_path)
