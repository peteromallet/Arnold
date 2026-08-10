from __future__ import annotations

from pathlib import Path

import pytest

from scripts import generate_m11_audit_manifest as audit_manifest


def _write_cycle(root: Path, cycle_id: str, *, complete: bool) -> None:
    cycle = root / cycle_id
    cycle.mkdir(parents=True)
    names = (
        audit_manifest.REQUIRED_FILES
        if complete
        else ("operator-prompt.txt", "output-schema.json")
    )
    for name in names:
        (cycle / name).write_text(f"{cycle_id}:{name}\n", encoding="utf-8")


def _historical_tree(tmp_path: Path) -> Path:
    root = tmp_path / "audit"
    for cycle_id in audit_manifest.REQUIRED_CYCLES[:3]:
        _write_cycle(root, cycle_id, complete=True)
    _write_cycle(root, audit_manifest.REQUIRED_CYCLES[3], complete=False)
    return root


def _substitution(
    missing: dict, replacement_id: str
) -> dict:
    value = {
        "schema": audit_manifest.SUBSTITUTION_SCHEMA,
        "missing_cycle_id": missing["cycle_id"],
        "missing_cycle_sha256": missing["cycle_tree_sha256"],
        "replacement_cycle_id": replacement_id,
        "reason": "The original cycle stopped before operator completion.",
        "authority": {
            "actor": "m11-acceptance-owner",
            "receipt_sha256": "sha256:" + "a" * 64,
        },
        "source_commit": "b" * 40,
    }
    value["content_sha256"] = audit_manifest.substitution_digest(value)
    return value


def test_three_complete_cycles_and_partial_fourth_are_preserved(
    tmp_path: Path,
) -> None:
    root = _historical_tree(tmp_path)
    first = audit_manifest.build_manifest(root, repo_root=tmp_path)
    second = audit_manifest.build_manifest(root, repo_root=tmp_path)
    assert first == second
    assert first["schema"] == "m11.audit-cycle-trees.v1"
    assert first["complete"] is False
    assert first["incomplete_cycle_ids"] == ["20260727T204730.361503Z"]
    assert [row["is_complete"] for row in first["audit_cycle_trees"]] == [
        True, True, True, False,
    ]
    partial = first["audit_cycle_trees"][3]
    assert partial["provenance_digest"] == ""
    assert partial["missing_files"] == [
        "operator-result.json",
        "operator-transcript.jsonl",
        "report.json",
        "report.md",
    ]
    assert partial["cycle_tree_sha256"].startswith("sha256:")
    for cycle in first["audit_cycle_trees"][:3]:
        assert [row["filename"] for row in cycle["files"]] == list(
            audit_manifest.REQUIRED_FILES
        )
        assert cycle["provenance_digest"].startswith("sha256:")


def test_file_mutation_changes_bound_tree_and_manifest_digest(
    tmp_path: Path,
) -> None:
    root = _historical_tree(tmp_path)
    before = audit_manifest.build_manifest(root, repo_root=tmp_path)
    changed = root / audit_manifest.REQUIRED_CYCLES[0] / "report.md"
    changed.write_text("mutated\n", encoding="utf-8")
    after = audit_manifest.build_manifest(root, repo_root=tmp_path)
    assert (
        before["audit_cycle_trees"][0]["cycle_tree_sha256"]
        != after["audit_cycle_trees"][0]["cycle_tree_sha256"]
    )
    assert before["content_sha256"] != after["content_sha256"]


def test_committed_authorized_substitution_requires_complete_fresh_cycle(
    tmp_path: Path,
) -> None:
    root = _historical_tree(tmp_path)
    baseline = audit_manifest.build_manifest(root, repo_root=tmp_path)
    replacement_id = "20260731T120000.000000Z"
    _write_cycle(root, replacement_id, complete=True)
    substitution = _substitution(
        baseline["audit_cycle_trees"][3], replacement_id
    )
    result = audit_manifest.build_manifest(
        root,
        repo_root=tmp_path,
        substitution=substitution,
        commit_verifier=lambda _root, revision: revision == "b" * 40,
    )
    assert result["complete"] is True
    assert result["incomplete_cycle_ids"] == []
    # Historical truth is retained; only the effective view substitutes it.
    assert result["audit_cycle_trees"][3]["is_complete"] is False
    assert result["effective_cycle_trees"][3]["cycle_id"] == replacement_id
    assert result["effective_cycle_trees"][3]["is_complete"] is True
    assert result["substitutions"][0]["authorization"] == substitution


@pytest.mark.parametrize(
    "mutation,error",
    [
        (lambda row: row.update(missing_cycle_sha256="sha256:" + "0" * 64),
         "substitution_missing_cycle_digest_mismatch"),
        (lambda row: row.update(reason=""), "substitution_reason_missing"),
        (lambda row: row.update(authority={}), "substitution_authority_invalid"),
    ],
)
def test_rejects_unbound_substitution(
    tmp_path: Path, mutation, error: str
) -> None:
    root = _historical_tree(tmp_path)
    baseline = audit_manifest.build_manifest(root, repo_root=tmp_path)
    replacement_id = "20260731T120000.000000Z"
    _write_cycle(root, replacement_id, complete=True)
    substitution = _substitution(
        baseline["audit_cycle_trees"][3], replacement_id
    )
    mutation(substitution)
    substitution["content_sha256"] = audit_manifest.substitution_digest(
        substitution
    )
    with pytest.raises(audit_manifest.AuditManifestError, match=error):
        audit_manifest.build_manifest(
            root,
            repo_root=tmp_path,
            substitution=substitution,
            commit_verifier=lambda _root, _revision: True,
        )


def test_rejects_uncommitted_substitution(tmp_path: Path) -> None:
    root = _historical_tree(tmp_path)
    baseline = audit_manifest.build_manifest(root, repo_root=tmp_path)
    replacement_id = "20260731T120000.000000Z"
    _write_cycle(root, replacement_id, complete=True)
    substitution = _substitution(
        baseline["audit_cycle_trees"][3], replacement_id
    )
    with pytest.raises(
        audit_manifest.AuditManifestError, match="substitution_not_committed"
    ):
        audit_manifest.build_manifest(
            root,
            repo_root=tmp_path,
            substitution=substitution,
            commit_verifier=lambda _root, _revision: False,
        )


def test_rejects_incomplete_replacement(tmp_path: Path) -> None:
    root = _historical_tree(tmp_path)
    baseline = audit_manifest.build_manifest(root, repo_root=tmp_path)
    replacement_id = "20260731T120000.000000Z"
    _write_cycle(root, replacement_id, complete=False)
    substitution = _substitution(
        baseline["audit_cycle_trees"][3], replacement_id
    )
    with pytest.raises(
        audit_manifest.AuditManifestError,
        match="substitution_replacement_incomplete",
    ):
        audit_manifest.build_manifest(
            root,
            repo_root=tmp_path,
            substitution=substitution,
            commit_verifier=lambda _root, _revision: True,
        )
