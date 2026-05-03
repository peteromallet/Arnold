from __future__ import annotations

from pathlib import Path

from scripts.populate_codebases import apply_groups, populate_orgs
from tests.helpers import create_store


class FakeClient:
    def org_repos(self, org: str):
        return {
            "ok": True,
            "repos": [
                {"owner": org, "name": "Repo", "default_branch": "main"},
                {"owner": org, "name": "Gone", "default_branch": "main"},
            ],
        }

    def repo_metadata(self, owner: str, name: str):
        if name == "gone":
            return {"ok": False, "error": {"type": "not_found", "message": "gone"}}
        return {"ok": True, "repo": {"owner": owner, "name": name, "default_branch": "main"}}


def test_populator_verifies_orgs_reports_inaccessible_and_applies_groups(tmp_path) -> None:
    store, _conn = create_store(tmp_path / "arnold.db")

    result = populate_orgs(store, FakeClient(), ["peteromallet", "banodoco"])

    assert sorted(result["verified"]) == ["banodoco/repo", "peteromallet/repo"]
    assert {row["repo"] for row in result["inaccessible"]} == {"peteromallet/gone", "banodoco/gone"}
    assert store.find_codebase("PETEROMALLET", "REPO")["verified_accessible_at"]

    groups = tmp_path / "groups.yaml"
    groups.write_text("groups:\n  product:\n    - peteromallet/repo\n    - missing/repo\n", encoding="utf-8")
    group_result = apply_groups(store, Path(groups))

    assert group_result["updated"] == ["peteromallet/repo"]
    assert group_result["missing"] == ["missing/repo"]
    assert store.find_codebase("peteromallet", "repo")["group_name"] == "product"
