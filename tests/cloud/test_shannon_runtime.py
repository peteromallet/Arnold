from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import shannon_runtime


def _vendor_tree(tmp_path: Path, *, commander: bool = True) -> Path:
    root = tmp_path / "shannon"
    root.mkdir()
    (root / "package.json").write_text(
        json.dumps({"name": "@dexh/shannon", "version": "0.0.2"}),
        encoding="utf-8",
    )
    (root / "bun.lock").write_text('{"lockfileVersion": 1}\n', encoding="utf-8")
    (root / "index.ts").write_text(
        'import { Command } from "commander"; export { Command };\n',
        encoding="utf-8",
    )
    names = ["@anthropic-ai/claude-agent-sdk", "zod"]
    if commander:
        names.append("commander")
    for index, name in enumerate(names):
        package_root = root / "node_modules" / name
        package_root.mkdir(parents=True)
        (package_root / "package.json").write_text(
            json.dumps({"name": name, "version": f"1.0.{index}"}),
            encoding="utf-8",
        )
    return root


def _successful_bun(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, ...]]:
    commands: list[tuple[str, ...]] = []
    monkeypatch.setattr(shannon_runtime.shutil, "which", lambda _name: "/usr/bin/bun")

    def run(command, **_kwargs):
        commands.append(tuple(command))
        if command[1:] == ["--version"]:
            return subprocess.CompletedProcess(command, 0, "1.3.14\n", "")
        if command[1] == "-e":
            return subprocess.CompletedProcess(
                command, 0, "shannon-index-commander-ok\n", ""
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(shannon_runtime.subprocess, "run", run)
    return commands


def test_dependency_vector_binds_inventory_and_executes_shannon_smoke(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _vendor_tree(tmp_path)
    commands = _successful_bun(monkeypatch)

    payload = shannon_runtime.dependency_vector(root)

    assert payload["ready"] is True
    assert payload["errors"] == []
    assert {item["name"] for item in payload["packages"]} == {
        "@anthropic-ai/claude-agent-sdk",
        "commander",
        "zod",
    }
    assert payload["dependency_tree_sha256"]
    assert payload["smoke"]["stdout"] == "shannon-index-commander-ok"
    assert any(command[1] == "-e" and "./index.ts" in command[2] for command in commands)


def test_dependency_vector_fails_closed_when_commander_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _vendor_tree(tmp_path, commander=False)
    _successful_bun(monkeypatch)

    payload = shannon_runtime.dependency_vector(root)

    assert payload["ready"] is False
    assert "required_package_missing:commander" in payload["errors"]


def test_prepare_replaces_stale_tree_and_uses_frozen_production_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _vendor_tree(tmp_path)
    stale = root / "node_modules" / "stale"
    stale.mkdir()
    (stale / "package.json").write_text(
        json.dumps({"name": "stale", "version": "9.9.9"}),
        encoding="utf-8",
    )
    commands = _successful_bun(monkeypatch)
    real_run = shannon_runtime.subprocess.run

    def install_then_probe(command, **kwargs):
        if command[1:] == list(shannon_runtime._INSTALL_ARGS):
            assert not (root / "node_modules").exists()
            _vendor_tree_packages = (
                "@anthropic-ai/claude-agent-sdk",
                "commander",
                "zod",
            )
            for index, name in enumerate(_vendor_tree_packages):
                package_root = root / "node_modules" / name
                package_root.mkdir(parents=True)
                (package_root / "package.json").write_text(
                    json.dumps({"name": name, "version": f"2.0.{index}"}),
                    encoding="utf-8",
                )
            commands.append(tuple(command))
            return subprocess.CompletedProcess(command, 0, "", "")
        return real_run(command, **kwargs)

    monkeypatch.setattr(shannon_runtime.subprocess, "run", install_then_probe)

    payload = shannon_runtime.prepare_dependencies(root)

    assert payload["ready"] is True
    assert "stale" not in {item["name"] for item in payload["packages"]}
    assert (
        "/usr/bin/bun",
        "install",
        "--frozen-lockfile",
        "--production",
        "--ignore-scripts",
    ) in commands
