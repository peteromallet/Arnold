from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Sequence

from vibecomfy.node_packs_lockfile import LockEntry, read_lockfile
from vibecomfy.node_packs_install import install_pack, missing_packs_for_workflow
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


class FakeRunner:
    def __init__(
        self,
        *,
        sha: str = "abc123",
        porcelain: str = "",
        fail_clone: bool = False,
        fail_pip: bool = False,
    ) -> None:
        self.sha = sha
        self.porcelain = porcelain
        self.fail_clone = fail_clone
        self.fail_pip = fail_pip
        self.calls: list[list[str]] = []

    def __call__(
        self,
        args: Sequence[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        call = list(args)
        self.calls.append(call)
        assert check is True
        assert capture_output is True
        assert text is True
        if call[:2] == ["git", "clone"]:
            if self.fail_clone:
                raise subprocess.CalledProcessError(1, call, stderr="clone failed")
            return subprocess.CompletedProcess(call, 0, stdout="", stderr="")
        if call[:4] == ["git", "-C", call[2], "status"]:
            return subprocess.CompletedProcess(call, 0, stdout=self.porcelain, stderr="")
        if call[:4] == ["git", "-C", call[2], "rev-parse"]:
            return subprocess.CompletedProcess(call, 0, stdout=f"{self.sha}\n", stderr="")
        if len(call) >= 4 and call[1:4] == ["-m", "pip", "install"]:
            if self.fail_pip:
                raise subprocess.CalledProcessError(1, call, stderr="pip failed")
            return subprocess.CompletedProcess(call, 0, stdout="", stderr="")
        raise AssertionError(f"unexpected subprocess call: {call!r}")


def test_install_clones_and_upserts_on_success(tmp_path: Path) -> None:
    runner = FakeRunner(sha="feedface")
    lockfile = tmp_path / "custom_nodes.lock"

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
    )

    assert result.status == "installed"
    assert result.git_commit_sha == "feedface"
    assert runner.calls[0] == [
        "git",
        "clone",
        "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git",
        str(tmp_path / "custom_nodes" / "ComfyUI-VideoHelperSuite"),
    ]
    assert read_lockfile(lockfile) == [
        LockEntry(
            name="ComfyUI-VideoHelperSuite",
            git_commit_sha="feedface",
            url="https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git",
        )
    ]


def test_install_no_lockfile_mutation_on_clone_failure(tmp_path: Path) -> None:
    runner = FakeRunner(fail_clone=True)
    lockfile = tmp_path / "custom_nodes.lock"
    original = "Existing abc https://example.test/existing.git\n"
    lockfile.write_text(original, encoding="utf-8")

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
    )

    assert result.status == "failed"
    assert "clone failed" in (result.error or "")
    assert lockfile.read_text(encoding="utf-8") == original


def test_install_no_lockfile_mutation_on_pip_failure(tmp_path: Path) -> None:
    runner = FakeRunner(fail_pip=True)
    lockfile = tmp_path / "custom_nodes.lock"
    original = "Existing abc https://example.test/existing.git\n"
    lockfile.write_text(original, encoding="utf-8")

    result = install_pack(
        name="ComfyUI-KJNodes",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
    )

    assert result.status == "failed"
    assert "pip failed" in (result.error or "")
    assert lockfile.read_text(encoding="utf-8") == original


def test_install_idempotent_when_clean(tmp_path: Path) -> None:
    install_dir = tmp_path / "custom_nodes" / "ComfyUI-VideoHelperSuite"
    install_dir.mkdir(parents=True)
    runner = FakeRunner(sha="cleanhead", porcelain="")
    lockfile = tmp_path / "custom_nodes.lock"

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
    )

    assert result.status == "refreshed"
    assert not any(call[:2] == ["git", "clone"] for call in runner.calls)
    assert read_lockfile(lockfile) == [
        LockEntry(
            name="ComfyUI-VideoHelperSuite",
            git_commit_sha="cleanhead",
            url="https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git",
        )
    ]


def test_install_refuses_dirty_without_force(tmp_path: Path) -> None:
    install_dir = tmp_path / "custom_nodes" / "ComfyUI-VideoHelperSuite"
    install_dir.mkdir(parents=True)
    runner = FakeRunner(porcelain=" M nodes.py\n")
    lockfile = tmp_path / "custom_nodes.lock"
    original = "Existing abc https://example.test/existing.git\n"
    lockfile.write_text(original, encoding="utf-8")

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
    )

    assert result.status == "skipped_dirty"
    assert not any(call[:2] == ["git", "clone"] for call in runner.calls)
    assert lockfile.read_text(encoding="utf-8") == original


def test_install_force_dirty_does_not_clone_and_upserts_head(tmp_path: Path) -> None:
    install_dir = tmp_path / "custom_nodes" / "ComfyUI-VideoHelperSuite"
    install_dir.mkdir(parents=True)
    runner = FakeRunner(sha="dirtyhead", porcelain=" M nodes.py\n")
    lockfile = tmp_path / "custom_nodes.lock"

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        force=True,
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
    )

    assert result.status == "refreshed"
    assert not any(call[:2] == ["git", "clone"] for call in runner.calls)
    assert read_lockfile(lockfile) == [
        LockEntry(
            name="ComfyUI-VideoHelperSuite",
            git_commit_sha="dirtyhead",
            url="https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git",
        )
    ]


def test_install_with_repo_url_infers_name_and_skips_pip_when_uncatalogued(tmp_path: Path) -> None:
    runner = FakeRunner(sha="uncatalogued")
    lockfile = tmp_path / "custom_nodes.lock"

    result = install_pack(
        repo="https://example.test/some-pack.git",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
    )

    assert result.name == "some-pack"
    assert result.status == "installed"
    assert runner.calls[0] == [
        "git",
        "clone",
        "https://example.test/some-pack.git",
        str(tmp_path / "custom_nodes" / "some-pack"),
    ]
    assert not any(len(call) >= 4 and call[1:4] == ["-m", "pip", "install"] for call in runner.calls)
    assert read_lockfile(lockfile) == [
        LockEntry(
            name="some-pack",
            git_commit_sha="uncatalogued",
            url="https://example.test/some-pack.git",
        )
    ]


def test_missing_packs_for_workflow_returns_resolved_and_unresolved(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "node_index.json").write_text(
        '[{"class_type": "SaveImage", "pack": "core", "inputs": {}, "outputs": []}]',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    workflow = VibeWorkflow("missing-packs", WorkflowSource("missing-packs"))
    workflow.nodes["1"] = VibeNode("1", "SaveImage")
    workflow.nodes["2"] = VibeNode("2", "Qwen3CustomVoice")
    workflow.nodes["3"] = VibeNode("3", "UnknownCustomNode")

    packs, unresolved = missing_packs_for_workflow(workflow)

    assert [pack.name for pack in packs] == ["ComfyUI-Qwen3-TTS"]
    assert unresolved == ["UnknownCustomNode"]
