from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import pytest
import yaml

from arnold_pipelines.megaplan.chain import run_chain_cli
from arnold_pipelines.megaplan.cli import handle_initiative
from arnold_pipelines.megaplan.cloud.cli import _run_chain_wrapper, _run_preflight
from arnold_pipelines.megaplan.cloud.spec import (
    CloudSpec,
    CodexSpec,
    MegaplanSpec,
    RepoSpec,
    ResourcesSpec,
    SshSpec,
)
from arnold_pipelines.megaplan.types import CliError


def _cloud_spec() -> CloudSpec:
    return CloudSpec(
        provider="ssh",
        repo=RepoSpec(url="https://github.com/example/app.git", branch="main"),
        agents={"default": "codex"},
        codex=CodexSpec(),
        mode="idle",
        megaplan=MegaplanSpec(),
        resources=ResourcesSpec(),
        secrets=[],
        ssh=SshSpec(host="testhost"),
    )


def _initiative_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "initiative_action": "new",
        "slug": "Cloud Ready Project",
        "title": None,
        "description": None,
        "description_file": None,
        "north_star": None,
        "north_star_file": None,
        "strategy": False,
        "doc": [],
        "chain": False,
        "milestone": ["m1=First Sprint"],
        "base_branch": "main",
        "merge_policy": "auto",
        "branch_prefix": None,
        "profile": "partnered-5",
        "vendor": "codex",
        "robustness": "full",
        "depth": "high",
        "no_with_prep": False,
        "cloud": True,
        "repo_url": None,
        "chain_session": None,
        "force": False,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_initiative_new_scaffolds_cloud_ready_canonical_layout(tmp_path: Path) -> None:
    source_doc = tmp_path / "strategy.md"
    source_doc.write_text("# Strategy\n\nUse this as the research starting point.\n", encoding="utf-8")

    result = handle_initiative(tmp_path, _initiative_args(doc=[f"research={source_doc}"]))

    root = tmp_path / ".megaplan" / "initiatives" / "cloud-ready-project"
    chain_path = root / "chain.yaml"
    cloud_path = root / "cloud.yaml"

    assert result["success"] is True
    assert result["chain"] == str(chain_path)
    assert result["cloud_yaml"] == str(cloud_path)
    assert (root / "README.md").read_text(encoding="utf-8").startswith("# Cloud Ready Project\n\nTODO_")
    assert "TODO_NORTH_STAR_END_STATE" in (root / "NORTHSTAR.md").read_text(encoding="utf-8")
    assert (root / "briefs" / "m1.md").is_file()
    assert (root / "research" / "strategy.md").read_text(encoding="utf-8") == source_doc.read_text(
        encoding="utf-8"
    )
    assert result["docs"] == [str(root / "research" / "strategy.md")]

    chain = yaml.safe_load(chain_path.read_text(encoding="utf-8"))
    assert chain["anchors"] == {"north_star": "NORTHSTAR.md"}
    assert chain["merge_policy"] == "auto"
    assert chain["milestones"][0]["branch"] == "megaplan/cloud-ready-project/m1"
    assert chain["milestones"][0]["with_prep"] is True

    cloud = yaml.safe_load(cloud_path.read_text(encoding="utf-8"))
    assert cloud["repo"]["url"] == "TODO_REPO_URL"
    assert cloud["ssh"]["host"] == "TODO_SSH_HOST"
    assert cloud["chain_session"] == "cloud-ready-project"
    assert result["next"]["launch"].endswith(f"cloud chain {chain_path} --cloud-yaml {cloud_path}")


def test_initiative_retire_hides_discovery_and_blocks_chain_continuation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    handle_initiative(tmp_path, _initiative_args(slug="old-work", cloud=False))
    handle_initiative(tmp_path, _initiative_args(slug="replacement", cloud=False))
    old_root = tmp_path / ".megaplan" / "initiatives" / "old-work"
    chain_path = old_root / "chain.yaml"
    evidence = old_root / "handoff" / "replacement-evidence.json"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text('{"replacement":"replacement"}\n', encoding="utf-8")
    chain_sha = hashlib.sha256(chain_path.read_bytes()).hexdigest()

    result = handle_initiative(
        tmp_path,
        argparse.Namespace(
            initiative_action="retire",
            slug="old-work",
            superseded_by="replacement",
            reason="replacement owns the remaining work",
            expect_chain_sha256=chain_sha,
            evidence=[str(evidence.relative_to(tmp_path))],
        ),
    )

    assert result["success"] is True
    assert result["retirement"]["truthfulness"] == {
        "completion_asserted": False,
        "unfinished_milestones_completed": False,
        "historical_evidence_deleted": False,
    }
    assert (old_root / ".retired").is_file()

    listed = handle_initiative(
        tmp_path,
        argparse.Namespace(initiative_action="list", limit=None, include_retired=False),
    )
    assert [item["slug"] for item in listed["initiatives"]] == ["replacement"]
    historical = handle_initiative(
        tmp_path,
        argparse.Namespace(initiative_action="list", limit=None, include_retired=True),
    )
    assert {item["slug"] for item in historical["initiatives"]} == {"old-work", "replacement"}
    search = handle_initiative(
        tmp_path,
        argparse.Namespace(
            initiative_action="search",
            keywords=["old-work"],
            keywords_all=True,
            limit=None,
            include_retired=False,
        ),
    )
    assert "old-work" not in {item["slug"] for item in search["initiatives"]}
    historical_search = handle_initiative(
        tmp_path,
        argparse.Namespace(
            initiative_action="search",
            keywords=["old-work"],
            keywords_all=True,
            limit=None,
            include_retired=True,
        ),
    )
    assert "old-work" in {item["slug"] for item in historical_search["initiatives"]}

    rc = run_chain_cli(
        tmp_path,
        argparse.Namespace(chain_action="start", spec=str(chain_path)),
    )
    assert rc != 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "initiative_retired"


def test_initiative_retire_rejects_changed_chain(tmp_path: Path) -> None:
    handle_initiative(tmp_path, _initiative_args(slug="old-work", cloud=False))
    handle_initiative(tmp_path, _initiative_args(slug="replacement", cloud=False))

    with pytest.raises(CliError, match="Chain SHA-256 changed"):
        handle_initiative(
            tmp_path,
            argparse.Namespace(
                initiative_action="retire",
                slug="old-work",
                superseded_by="replacement",
                reason="replacement owns the remaining work",
                expect_chain_sha256="0" * 64,
                evidence=[],
            ),
        )


def test_initiative_new_can_scaffold_root_strategy_without_briefs_fallback(
    tmp_path: Path,
) -> None:
    result = handle_initiative(
        tmp_path,
        _initiative_args(
            slug="Product Direction",
            strategy=True,
            milestone=[],
            chain=False,
            cloud=False,
        ),
    )

    initiative = tmp_path / ".megaplan" / "initiatives" / "product-direction"
    strategy = initiative / "STRATEGY.md"
    assert result["strategy"] == str(strategy)
    assert strategy.is_file()
    assert "schema_version: megaplan-strategy-v1" in strategy.read_text(encoding="utf-8")
    assert not (tmp_path / ".megaplan" / "briefs").exists()


def test_cloud_preflight_rejects_template_placeholders_without_override(
    tmp_path: Path,
    capsys,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True, text=True)
    handle_initiative(project, _initiative_args())

    chain_path = project / ".megaplan" / "initiatives" / "cloud-ready-project" / "chain.yaml"
    cloud_path = project / ".megaplan" / "initiatives" / "cloud-ready-project" / "cloud.yaml"

    args = argparse.Namespace(
        spec=str(chain_path),
        cloud_yaml=str(cloud_path),
        skip_remote=True,
        allow_loose_chain_spec=False,
        allow_template_placeholders=False,
        repo_url=None,
        repo_branch=None,
        repo_workspace=None,
    )
    rc = _run_preflight(project, args, _cloud_spec(), provider=None)

    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["success"] is False
    assert payload["template_placeholders"]
    assert any(item["placeholder"] == "TODO_REPO_URL" for item in payload["template_placeholders"])
    assert any(item["placeholder"] == "TODO_NORTH_STAR_END_STATE" for item in payload["template_placeholders"])

    args.allow_template_placeholders = True
    rc = _run_preflight(project, args, _cloud_spec(), provider=None)

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["success"] is True
    assert payload["template_placeholders"]


def test_cloud_preflight_rejects_human_gated_policy_without_override(
    tmp_path: Path,
    capsys,
) -> None:
    project = tmp_path / "project"
    spec_dir = project / ".megaplan" / "initiatives" / "human-gated"
    briefs_dir = spec_dir / "briefs"
    briefs_dir.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True, text=True)
    (spec_dir / "NORTHSTAR.md").write_text("ship unattended cloud work\n", encoding="utf-8")
    (briefs_dir / "m1.md").write_text("do the work\n", encoding="utf-8")
    chain_path = spec_dir / "chain.yaml"
    chain_path.write_text(
        "anchors:\n"
        "  north_star: NORTHSTAR.md\n"
        "merge_policy: review\n"
        "driver:\n"
        "  auto_approve: false\n"
        "milestones:\n"
        "  - label: m1\n"
        "    idea: .megaplan/initiatives/human-gated/briefs/m1.md\n",
        encoding="utf-8",
    )

    args = argparse.Namespace(
        spec=str(chain_path),
        cloud_yaml=None,
        skip_remote=True,
        allow_loose_chain_spec=False,
        allow_template_placeholders=False,
        allow_human_gates=False,
        repo_url=None,
        repo_branch=None,
        repo_workspace=None,
    )
    rc = _run_preflight(project, args, _cloud_spec(), provider=None)

    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["success"] is False
    assert {item["field"] for item in payload["human_gates"]} == {
        "merge_policy",
        "driver.auto_approve",
    }
    assert any("human-gated cloud chain policy present" in error for error in payload["errors"])

    args.allow_human_gates = True
    rc = _run_preflight(project, args, _cloud_spec(), provider=None)

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["success"] is True
    assert payload["human_gates"]


def test_cloud_chain_rejects_template_placeholders_before_remote_work(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True, text=True)
    handle_initiative(project, _initiative_args())

    chain_path = project / ".megaplan" / "initiatives" / "cloud-ready-project" / "chain.yaml"
    cloud_path = project / ".megaplan" / "initiatives" / "cloud-ready-project" / "cloud.yaml"
    args = argparse.Namespace(
        spec=str(chain_path),
        cloud_yaml=str(cloud_path),
        idea_dir=None,
        fresh=False,
        no_git_refresh=False,
        no_editable_install_sync=True,
        force_clean_editable_install=False,
        allow_loose_chain_spec=False,
        allow_template_placeholders=False,
        repo_url=None,
        repo_branch=None,
        repo_workspace=None,
        _canonicalized_epic=True,
        _generated_canonical_files=[],
    )

    try:
        _run_chain_wrapper(project, args, _cloud_spec(), provider=None)
    except CliError as exc:
        assert exc.code == "template_placeholders_present"
        placeholders = {
            finding["placeholder"]
            for finding in exc.extra["template_placeholders"]
        }
        assert "TODO_REPO_URL" in placeholders
        assert "TODO_NORTH_STAR_END_STATE" in placeholders
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("cloud chain unexpectedly accepted template placeholders")
