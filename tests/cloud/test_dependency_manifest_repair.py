from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan.chain.spec import (
    ChainSpec,
    ChainState,
    load_chain_state,
    save_chain_state,
    validate_paths,
)
from arnold_pipelines.megaplan.cloud.dependency_manifest_repair import (
    _sync_completed_prerequisite,
    repair_dependency_manifests,
)


def test_dependency_manifest_repair_marks_review_chain_state_only_publication(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    source_root.mkdir()
    target_root.mkdir()
    source_chain = source_root / ".megaplan" / "initiatives" / "upstream" / "chain.yaml"
    target_chain = target_root / ".megaplan" / "initiatives" / "upstream" / "chain.yaml"
    source_chain.parent.mkdir(parents=True)
    target_chain.parent.mkdir(parents=True)
    body = """
merge_policy: review
milestones:
  - label: m1
    idea: m1.md
"""
    source_chain.write_text(body, encoding="utf-8")
    target_chain.write_text(body, encoding="utf-8")
    (target_root / "m1.md").write_text("# M1\n", encoding="utf-8")
    spec = ChainSpec.from_dict(
        {
            "merge_policy": "review",
            "milestones": [{"label": "m1", "idea": "m1.md"}],
        }
    )
    state = ChainState(
        current_milestone_index=1,
        completed=[{"label": "m1", "status": "done", "plan": "plan-m1"}],
    )

    result = _sync_completed_prerequisite(
        target_root=target_root,
        target_chain=target_chain,
        source_root=source_root,
        source_chain=source_chain,
        spec=spec,
        state=state,
    )

    manifest_path = Path(result["manifest"]["manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["milestones"][0]["publication_evidence"] == "chain_state_only"
    saved = load_chain_state(target_chain)
    assert saved.completed[0]["publication_evidence"] == "chain_state_only"

    dependent_path = target_root / "dependent.yaml"
    dependent_path.write_text("milestones: []\n", encoding="utf-8")
    dependent_spec = ChainSpec.from_dict(
        {
            "launch_preconditions": [
                {
                    "name": "upstream complete",
                    "kind": "chain_completed",
                    "chain": str(target_chain.relative_to(target_root)),
                    "require_manifest": True,
                }
            ],
            "milestones": [],
        }
    )
    validate_paths(dependent_spec, target_root, spec_path=dependent_path)


def test_dependency_manifest_repair_finds_legacy_dot_chain_sibling(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    marker_dir = tmp_path / "markers"
    source_root.mkdir()
    target_root.mkdir()
    marker_dir.mkdir()
    source_chain = source_root / ".megaplan" / "initiatives" / "upstream.chain" / "chain.yaml"
    target_chain = target_root / ".megaplan" / "initiatives" / "upstream" / "chain.yaml"
    source_chain.parent.mkdir(parents=True)
    target_chain.parent.mkdir(parents=True)
    source_chain.write_text(
        """
milestones:
  - label: m1
    idea: .megaplan/initiatives/upstream.chain/briefs/m1.md
""",
        encoding="utf-8",
    )
    target_chain.write_text(
        """
milestones:
  - label: m1
    idea: .megaplan/initiatives/upstream/briefs/m1.md
""",
        encoding="utf-8",
    )
    (source_chain.parent / "briefs").mkdir()
    (target_chain.parent / "briefs").mkdir()
    (source_chain.parent / "briefs" / "m1.md").write_text("# M1\n", encoding="utf-8")
    (target_chain.parent / "briefs" / "m1.md").write_text("# M1\n", encoding="utf-8")
    save_chain_state(
        source_chain,
        ChainState(
            current_milestone_index=1,
            completed=[{"label": "m1", "status": "done", "plan": "plan-m1"}],
        ),
    )
    marker = marker_dir / "upstream.json"
    marker.write_text(json.dumps({"workspace": str(source_root)}) + "\n", encoding="utf-8")
    dependent_chain = target_root / "dependent-chain.yaml"
    dependent_chain.write_text(
        """
launch_preconditions:
  - name: upstream complete
    kind: chain_completed
    chain: .megaplan/initiatives/upstream/chain.yaml
    require_manifest: true
milestones: []
""",
        encoding="utf-8",
    )

    result = repair_dependency_manifests(
        workspace=target_root,
        remote_spec=dependent_chain,
        marker_dir=marker_dir,
    )

    assert result.repaired is True
    manifest = json.loads(target_chain.with_name("completion-manifest.json").read_text(encoding="utf-8"))
    assert manifest["chain"]["path"] == ".megaplan/initiatives/upstream/chain.yaml"
    assert manifest["milestones"][0]["brief_path"] == (
        ".megaplan/initiatives/upstream/briefs/m1.md"
    )
    validate_paths(
        ChainSpec.from_dict(
            {
                "launch_preconditions": [
                    {
                        "name": "upstream complete",
                        "kind": "chain_completed",
                        "chain": ".megaplan/initiatives/upstream/chain.yaml",
                        "require_manifest": True,
                    }
                ],
                "milestones": [],
            }
        ),
        target_root,
        spec_path=dependent_chain,
    )
