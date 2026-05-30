"""Regression test for bug 3: idea brief outside the repo must be copied in.

In plan-all-first, when a finalized milestone is persisted, its ``idea:`` path
is added to the set of immutable plan artifacts. When that idea path is an
absolute path *outside* the project-dir/worktree repo, git cannot add it and
``commit_plan_artifacts_to_base`` previously rejected with ``invalid_plan_artifact``
("plan artifact path is outside the repository: ...").

The durable fix copies the external idea into ``.megaplan/plans/<plan>/idea.md``
inside the repo and persists that in-repo copy instead. When the idea already
lives inside the repo, it is added in place (prior behavior).
"""
from __future__ import annotations

from pathlib import Path

from megaplan.chain import MilestoneSpec, _plan_artifact_paths_for_milestone


def _make_plan_dir(root: Path, plan_name: str) -> Path:
    plan_dir = root / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True)
    return plan_dir


def test_external_idea_is_copied_into_plan_dir(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    plan_dir = _make_plan_dir(repo, "plan-m1")

    # The idea brief lives OUTSIDE the repo (e.g. an absolute path to a brief
    # authored elsewhere on disk).
    external = tmp_path / "external-briefs" / "M1.md"
    external.parent.mkdir(parents=True)
    external.write_text("external idea content\n", encoding="utf-8")

    milestone = MilestoneSpec(label="m1", idea=str(external))
    artifacts = _plan_artifact_paths_for_milestone(repo, "plan-m1", milestone)

    idea_copy = plan_dir / "idea.md"
    assert idea_copy.exists(), "external idea must be copied into the plan dir"
    assert idea_copy.read_text(encoding="utf-8") == "external idea content\n"
    # The in-repo copy (not the external path) must be in the artifact list,
    # and it must be under the repo root so git can add it.
    assert idea_copy in artifacts
    assert external not in artifacts
    assert idea_copy.resolve().is_relative_to(repo.resolve())


def test_external_idea_copy_refreshes_on_content_change(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    plan_dir = _make_plan_dir(repo, "plan-m1")
    external = tmp_path / "external" / "M1.md"
    external.parent.mkdir(parents=True)

    external.write_text("v1\n", encoding="utf-8")
    _plan_artifact_paths_for_milestone(repo, "plan-m1", milestone := MilestoneSpec(label="m1", idea=str(external)))
    assert (plan_dir / "idea.md").read_text(encoding="utf-8") == "v1\n"

    external.write_text("v2\n", encoding="utf-8")
    _plan_artifact_paths_for_milestone(repo, "plan-m1", milestone)
    assert (plan_dir / "idea.md").read_text(encoding="utf-8") == "v2\n"


def test_internal_idea_is_added_in_place(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    plan_dir = _make_plan_dir(repo, "plan-m1")

    # Idea already inside the repo — preserve prior behavior (add in place,
    # do NOT create an idea.md copy).
    inside = repo / "ideas" / "M1.md"
    inside.parent.mkdir(parents=True)
    inside.write_text("inside idea\n", encoding="utf-8")

    milestone = MilestoneSpec(label="m1", idea=str(inside))
    artifacts = _plan_artifact_paths_for_milestone(repo, "plan-m1", milestone)

    assert inside in artifacts
    assert not (plan_dir / "idea.md").exists()


def test_missing_idea_is_skipped(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _make_plan_dir(repo, "plan-m1")
    milestone = MilestoneSpec(label="m1", idea=str(tmp_path / "does-not-exist.md"))
    artifacts = _plan_artifact_paths_for_milestone(repo, "plan-m1", milestone)
    # No idea appended, no copy created.
    assert not (repo / ".megaplan" / "plans" / "plan-m1" / "idea.md").exists()
    assert all(a.name != "idea.md" for a in artifacts)
