from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from arnold_pipelines.megaplan.cloud.source_initiative_repair import (
    repair_source_initiative,
    source_initiative_restore_available,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
REPAIR_LOOP = REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers" / "arnold-repair-loop"


def _write_source_initiative(source_root: Path) -> tuple[Path, Path]:
    chain_dir = source_root / ".megaplan" / "initiatives" / "demo.chain"
    canonical_dir = source_root / ".megaplan" / "initiatives" / "demo"
    chain_dir.mkdir(parents=True)
    canonical_dir.mkdir(parents=True)
    (chain_dir / "chain.yaml").write_text(
        "milestones:\n  - label: m1\n    idea: .megaplan/initiatives/demo.chain/briefs/m1.md\n",
        encoding="utf-8",
    )
    briefs = chain_dir / "briefs"
    briefs.mkdir()
    (briefs / "m1.md").write_text("# Demo\n", encoding="utf-8")
    (canonical_dir / "completion-manifest.json").write_text(
        json.dumps(
            {
                "schema": "arnold.megaplan.chain_completion_manifest.v1",
                "chain": {"path": ".megaplan/initiatives/demo/chain.yaml", "sha256": "unused"},
                "milestones": [{"label": "m1", "status": "done", "plan": "m1-demo"}],
            }
        ),
        encoding="utf-8",
    )
    (canonical_dir / "dependency-completion-proof.json").write_text(
        json.dumps({"source_workspace": "/workspace/demo", "completed": [{"label": "m1", "status": "done"}]}),
        encoding="utf-8",
    )
    (canonical_dir / "proof-map.json").write_text(json.dumps({"m1": ["dependency-completion-proof.json"]}), encoding="utf-8")
    (canonical_dir / "README.md").write_text("# Demo\n", encoding="utf-8")
    return chain_dir, canonical_dir


def test_source_initiative_repair_overlays_canonical_completion_artifacts(tmp_path: Path) -> None:
    source_root = tmp_path / "arnold-src"
    _write_source_initiative(source_root)
    workspace = tmp_path / "workspace"
    remote_spec = workspace / ".megaplan" / "initiatives" / "demo.chain" / "chain.yaml"

    assert source_initiative_restore_available(
        workspace=workspace,
        remote_spec=remote_spec,
        arnold_src=source_root,
    )

    result = repair_source_initiative(
        workspace=workspace,
        remote_spec=remote_spec,
        arnold_src=source_root,
    )

    assert result.repaired is True
    assert result.reason == "source_initiative_restored"
    assert remote_spec.exists()
    assert (remote_spec.parent / "briefs" / "m1.md").exists()
    assert (remote_spec.parent / "completion-manifest.json").exists()
    assert (remote_spec.parent / "dependency-completion-proof.json").exists()
    assert (remote_spec.parent / "proof-map.json").exists()
    assert (remote_spec.parent / "README.md").exists()
    assert result.details["overlay_files"] == [
        ".megaplan/initiatives/demo.chain/README.md",
        ".megaplan/initiatives/demo.chain/completion-manifest.json",
        ".megaplan/initiatives/demo.chain/dependency-completion-proof.json",
        ".megaplan/initiatives/demo.chain/proof-map.json",
    ]


def test_repair_loop_restores_missing_workspace_and_exits_complete(tmp_path: Path) -> None:
    source_root = tmp_path / "arnold-src"
    _write_source_initiative(source_root)
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    workspace = tmp_path / "workspace"
    remote_spec = workspace / ".megaplan" / "initiatives" / "demo.chain" / "chain.yaml"
    session = "demo-chain"

    (marker_dir / f"{session}.json").write_text(
        json.dumps(
            {
                "session": session,
                "workspace": str(workspace),
                "remote_spec": str(remote_spec),
                "run_kind": "chain",
            }
        ),
        encoding="utf-8",
    )

    env = dict(os.environ)
    env["PYTHONPATH"] = f"{REPO_ROOT}:{env.get('PYTHONPATH', '')}"
    env["CLOUD_WATCHDOG_MARKER_DIR"] = str(marker_dir)
    env["CLOUD_WATCHDOG_REPAIR_DATA_DIR"] = str(repair_data_dir)
    env["CLOUD_WATCHDOG_ARNOLD_SRC"] = str(source_root)
    env["CLOUD_WATCHDOG_REPAIR_ROOT"] = str(tmp_path / "repair-root")

    result = subprocess.run(
        ["bash", str(REPAIR_LOOP), session, str(workspace), str(remote_spec)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads((repair_data_dir / f"{session}.repair-data.json").read_text(encoding="utf-8"))
    assert payload["outcome"] == "complete"
    assert remote_spec.exists()
    assert (remote_spec.parent / "completion-manifest.json").exists()
