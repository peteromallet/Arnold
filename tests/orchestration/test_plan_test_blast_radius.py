from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.handlers.plan import _derive_plan_test_blast_radius


def _write(repo: Path, rel_path: str, content: str = "") -> None:
    path = repo / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content or f"# {rel_path}\n", encoding="utf-8")


def _state(repo: Path) -> dict[str, Any]:
    return {"config": {"mode": "code", "project_dir": str(repo)}}


def test_plan_blast_radius_uses_prep_surface_inventory(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    plan_dir = repo / ".megaplan" / "plans" / "p"
    plan_dir.mkdir(parents=True)
    _write(repo, "pkg/util.py", "VALUE = 1\n")
    _write(repo, "tests/test_util.py", "import pkg.util\n")
    (plan_dir / "prep.json").write_text(
        json.dumps({"relevant_code": [{"file_path": "pkg/util.py"}]}),
        encoding="utf-8",
    )

    radius = _derive_plan_test_blast_radius(
        plan_dir=plan_dir,
        state=_state(repo),
        payload={
            "changed_surfaces": ["pkg/util.py"],
            "success_criteria": [
                {"criterion": "Focused tests pass", "priority": "must", "requires": ["run_tests"]}
            ],
        },
    )

    assert radius is not None
    assert radius["strategy"] == "scoped"
    assert [selector["value"] for selector in radius["selectors"]] == ["tests/test_util.py"]


def test_plan_blast_radius_falls_back_to_prep_relevant_code(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    plan_dir = repo / ".megaplan" / "plans" / "p"
    plan_dir.mkdir(parents=True)
    _write(repo, "pkg/util.py", "VALUE = 1\n")
    _write(repo, "tests/test_util.py", "import pkg.util\n")
    (plan_dir / "prep.json").write_text(
        json.dumps({"relevant_code": [{"file_path": "pkg/util.py"}]}),
        encoding="utf-8",
    )

    radius = _derive_plan_test_blast_radius(
        plan_dir=plan_dir,
        state=_state(repo),
        payload={
            "success_criteria": [
                {"criterion": "Focused tests pass", "priority": "must", "requires": ["run_tests"]}
            ],
        },
    )

    assert radius is not None
    assert radius["strategy"] == "scoped"
    assert [selector["value"] for selector in radius["selectors"]] == ["tests/test_util.py"]


def test_model_partial_changed_surfaces_cannot_narrow_prep_floor(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    plan_dir = repo / ".megaplan" / "plans" / "p"
    plan_dir.mkdir(parents=True)
    _write(repo, "pkg/first.py", "VALUE = 1\n")
    _write(repo, "pkg/second.py", "VALUE = 2\n")
    _write(repo, "tests/test_first.py", "import pkg.first\n")
    _write(repo, "tests/test_second.py", "import pkg.second\n")
    (plan_dir / "prep.json").write_text(
        json.dumps({
            "relevant_code": [
                {"file_path": "pkg/first.py"},
                {"file_path": "pkg/second.py"},
            ]
        }),
        encoding="utf-8",
    )

    radius = _derive_plan_test_blast_radius(
        plan_dir=plan_dir,
        state=_state(repo),
        payload={
            "changed_surfaces": ["pkg/first.py"],
            "test_blast_radius": {
                "strategy": "scoped",
                "selectors": [{"kind": "path", "value": "tests/test_first.py"}],
                "changed_surfaces": ["pkg/first.py"],
            },
            "success_criteria": [],
        },
    )

    assert radius is not None
    assert radius["changed_surfaces"] == ["pkg/first.py", "pkg/second.py"]
    assert [selector["value"] for selector in radius["selectors"]] == [
        "tests/test_first.py",
        "tests/test_second.py",
    ]


def test_plan_blast_radius_does_not_treat_missing_surfaces_as_no_tests(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    plan_dir = repo / ".megaplan" / "plans" / "p"
    plan_dir.mkdir(parents=True)

    radius = _derive_plan_test_blast_radius(
        plan_dir=plan_dir,
        state=_state(repo),
        payload={
            "changed_surfaces": [],
            "success_criteria": [
                {"criterion": "Tests pass", "priority": "must", "requires": ["run_tests"]}
            ],
        },
    )

    assert radius is not None
    assert radius["strategy"] == "full"
    assert "did not declare any concrete changed_surfaces" in radius["rationale"]


def test_model_proposed_absent_node_lands_in_missing_test_selectors(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    plan_dir = repo / ".megaplan" / "plans" / "p"
    plan_dir.mkdir(parents=True)
    _write(repo, "pkg/util.py", "VALUE = 1\n")
    _write(repo, "tests/test_util.py", "import pkg.util\n")
    # The file exists, but the node the model proposes is NOT defined in it.
    _write(
        repo,
        "tests/cloud/test_m1_containment_acceptance.py",
        "def test_some_existing_check():\n    pass\n",
    )
    (plan_dir / "prep.json").write_text(
        json.dumps({"relevant_code": [{"file_path": "pkg/util.py"}]}),
        encoding="utf-8",
    )

    radius = _derive_plan_test_blast_radius(
        plan_dir=plan_dir,
        state=_state(repo),
        payload={
            "changed_surfaces": ["pkg/util.py"],
            "test_blast_radius": {
                "strategy": "scoped",
                "selectors": [
                    {
                        "kind": "path",
                        "value": (
                            "tests/cloud/test_m1_containment_acceptance.py::"
                            "test_no_cloud_conftest_keyword_collection_hook"
                        ),
                    }
                ],
                "changed_surfaces": ["pkg/util.py"],
            },
            "success_criteria": [],
        },
    )

    assert radius is not None
    assert radius["missing_test_selectors"] == [
        "tests/cloud/test_m1_containment_acceptance.py::"
        "test_no_cloud_conftest_keyword_collection_hook"
    ]
    assert all(
        selector["value"]
        != "tests/cloud/test_m1_containment_acceptance.py::"
        "test_no_cloud_conftest_keyword_collection_hook"
        for selector in radius["selectors"]
    )
