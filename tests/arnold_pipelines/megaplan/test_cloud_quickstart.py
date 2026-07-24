from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]


def _run_quickstart(tmp_path: Path, *extra_args: str) -> tuple[dict[str, object], Path]:
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=project, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "git@github.com:example/project.git"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    )
    brief = project / "brief.md"
    brief.write_text("# Repair Loop\n\nFix the alive-but-failed launch path.\n", encoding="utf-8")
    north_star = project / "NORTHSTAR.md"
    north_star.write_text(
        "# North Star\n\n## End State\n\nUse explicit human-authored intent only.\n",
        encoding="utf-8",
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{REPO_ROOT}{os.pathsep}{env.get('PYTHONPATH', '')}"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "arnold_pipelines.megaplan",
            "cloud",
            "quickstart",
            "--slug",
            "repair-loop",
            "--brief",
            str(brief),
            "--north-star",
            str(north_star),
            "--skip-remote",
            *extra_args,
        ],
        cwd=project,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(proc.stdout)
    return payload, project


def test_cloud_quickstart_generates_canonical_initiative_from_one_brief(tmp_path: Path) -> None:
    payload, project = _run_quickstart(tmp_path)

    initiative = project / ".megaplan" / "initiatives" / "repair-loop"
    chain = yaml.safe_load((initiative / "chain.yaml").read_text(encoding="utf-8"))
    cloud = yaml.safe_load((initiative / "cloud.yaml").read_text(encoding="utf-8"))
    north_star = (initiative / "NORTHSTAR.md").read_text(encoding="utf-8")
    milestone = (initiative / "briefs" / "m1-repair-loop.md").read_text(encoding="utf-8")

    assert payload["event"] == "cloud_quickstart"
    assert payload["preflight"]["success"] is True
    assert payload["launch"]["launched"] is False
    assert chain["anchors"] == {"north_star": "NORTHSTAR.md"}
    assert chain["merge_policy"] == "auto"
    assert chain["driver"]["auto_approve"] is True
    assert chain["milestones"][0]["idea"] == ".megaplan/initiatives/repair-loop/briefs/m1-repair-loop.md"
    assert cloud["repo"]["url"] == "https://github.com/example/project.git"
    assert cloud["repo"]["workspace"] == "/workspace/repair-loop/project"
    assert cloud["chain_session"] == "repair-loop"
    assert cloud["secrets"] == []
    assert north_star == "# North Star\n\n## End State\n\nUse explicit human-authored intent only.\n"
    assert "Fix the alive-but-failed launch path." in milestone


def test_cloud_quickstart_stdout_is_single_json_payload(tmp_path: Path) -> None:
    payload, _project = _run_quickstart(tmp_path)

    assert set(payload) >= {"success", "event", "preflight", "launch"}


def test_cloud_quickstart_can_infer_extra_repo_workspace_from_role(tmp_path: Path) -> None:
    _payload, project = _run_quickstart(
        tmp_path,
        "--extra-repo",
        "worker=https://github.com/example/worker.git",
    )

    cloud = yaml.safe_load(
        (project / ".megaplan" / "initiatives" / "repair-loop" / "cloud.yaml").read_text(
            encoding="utf-8"
        )
    )

    assert cloud["extra_repos"] == [
        {
            "url": "https://github.com/example/worker.git",
            "branch": "main",
            "workspace": "/workspace/repair-loop/worker",
        }
    ]


def test_cloud_quickstart_extra_repo_supports_branch_and_workspace_override(tmp_path: Path) -> None:
    _payload, project = _run_quickstart(
        tmp_path,
        "--extra-repo",
        "worker=https://github.com/example/worker.git@develop:/workspace/custom-worker",
    )

    cloud = yaml.safe_load(
        (project / ".megaplan" / "initiatives" / "repair-loop" / "cloud.yaml").read_text(
            encoding="utf-8"
        )
    )

    assert cloud["extra_repos"] == [
        {
            "url": "https://github.com/example/worker.git",
            "branch": "develop",
            "workspace": "/workspace/custom-worker",
        }
    ]


def test_cloud_quickstart_extra_repo_keeps_legacy_url_workspace_form(tmp_path: Path) -> None:
    _payload, project = _run_quickstart(
        tmp_path,
        "--extra-repo",
        "https://github.com/example/worker.git@develop=/workspace/repair-loop/worker",
    )

    cloud = yaml.safe_load(
        (project / ".megaplan" / "initiatives" / "repair-loop" / "cloud.yaml").read_text(
            encoding="utf-8"
        )
    )

    assert cloud["extra_repos"] == [
        {
            "url": "https://github.com/example/worker.git",
            "branch": "develop",
            "workspace": "/workspace/repair-loop/worker",
        }
    ]


def _write_multi_sprint_chain(project: Path, *, north_star_text: str) -> tuple[Path, Path]:
    initiative = project / ".megaplan" / "initiatives" / "multi"
    briefs = initiative / "briefs"
    briefs.mkdir(parents=True)
    (initiative / "NORTHSTAR.md").write_text(north_star_text, encoding="utf-8")
    (briefs / "m1.md").write_text("# M1\n\nDo the first sprint.\n", encoding="utf-8")
    (briefs / "m2.md").write_text("# M2\n\nDo the second sprint.\n", encoding="utf-8")
    chain = initiative / "chain.yaml"
    chain.write_text(
        yaml.safe_dump(
            {
                "base_branch": "main",
                "anchors": {"north_star": "NORTHSTAR.md"},
                "milestones": [
                    {
                        "label": "m1",
                        "idea": ".megaplan/initiatives/multi/briefs/m1.md",
                        "profile": "partnered-5",
                        "vendor": "codex",
                        "depth": "high",
                        "branch": "multi/m1",
                    },
                    {
                        "label": "m2",
                        "idea": ".megaplan/initiatives/multi/briefs/m2.md",
                        "profile": "partnered-5",
                        "vendor": "codex",
                        "depth": "high",
                        "branch": "multi/m2",
                    },
                ],
                "merge_policy": "auto",
                "driver": {"auto_approve": True},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    cloud = initiative / "cloud.yaml"
    cloud.write_text(
        yaml.safe_dump(
            {
                "provider": "ssh",
                "repo": {
                    "url": "https://github.com/example/project.git",
                    "branch": "main",
                    "workspace": "/workspace/multi/project",
                },
                "mode": "idle",
                "chain_session": "multi",
                "chain": {"spec": "/workspace/multi/project/.megaplan/initiatives/multi/chain.yaml"},
                "megaplan": {"ref": "editible-install", "codex_auth": "chatgpt"},
                "ssh": {
                    "host": "127.0.0.1",
                    "user": "root",
                    "port": 22,
                    "remote_dir": "/opt/megaplan-cloud/deploy",
                    "workspace_dir": "/opt/megaplan-cloud/workspace",
                    "container": "megaplan-cloud-agent",
                },
                "secrets": [],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return chain, cloud


def _run_preflight(project: Path, chain: Path, cloud: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{REPO_ROOT}{os.pathsep}{env.get('PYTHONPATH', '')}"
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "arnold_pipelines.megaplan",
            "cloud",
            "preflight",
            str(chain),
            "--cloud-yaml",
            str(cloud),
            "--skip-remote",
        ],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_multi_sprint_cloud_preflight_blocks_thin_north_star(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    chain, cloud = _write_multi_sprint_chain(project, north_star_text="# North Star\n\nThin.\n")

    proc = _run_preflight(project, chain, cloud)
    payload = json.loads(proc.stdout)

    assert proc.returncode == 1
    assert payload["success"] is False
    assert payload["north_star_findings"][0]["code"] == "north_star_too_thin"


def test_multi_sprint_cloud_preflight_accepts_filled_north_star(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    filled = (
        "# North Star\n\n"
        "The chain must deliver the planned migration through two coordinated sprints while preserving "
        "the public workflow contract, existing user data, and current operational recovery behavior. "
        "Every sprint should move toward the same end state, avoid local-only assumptions, keep rollback "
        "paths visible, and document any temporary bridge so the follow-up sprint can remove it safely.\n"
    )
    chain, cloud = _write_multi_sprint_chain(project, north_star_text=filled)

    proc = _run_preflight(project, chain, cloud)
    payload = json.loads(proc.stdout)

    assert proc.returncode == 0
    assert payload["success"] is True
    assert payload["north_star_findings"] == []
