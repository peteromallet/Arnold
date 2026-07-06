"""Audit helpers for the vendored Hermes runtime surface."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

RUNTIME_REQUIRED_ENTRIES = (
    "run_agent.py",
    "hermes_state.py",
    "hermes_cli",
    "model_tools.py",
    "pyproject.toml",
)

JOB_B_SCOPE_FENCE_ENTRIES = (
    "skills",
    "tools",
    "acp_adapter",
    "acp_registry",
    "environments",
    "hermes_cli",
)

DEAD_WEIGHT_PATTERNS = (
    "evals",
    "landingpage",
    "website",
    "demo",
    "assets",
    "node_modules",
    "package.json",
    "package-lock.json",
    "tinker-atropos",
    "mini-swe-agent",
    "cli.py",
    "auto_improve",
    "batch_runner.py",
    "rl_cli.py",
    "datagen-config-examples",
    "RELEASE_v*.md",
    "setup-hermes.sh",
    "cli-config.yaml.example",
)

CONDITIONAL_RETENTION_DIRS = ("gateway", "cron", "honcho_integration")

_RETENTION_IMPORT_PATTERNS = {
    name: re.compile(rf"\b(?:from|import)\s+{re.escape(name)}(?:\.|\s|$)")
    for name in CONDITIONAL_RETENTION_DIRS
}


@dataclass(frozen=True)
class VendoredAgentTreeAudit:
    missing_runtime_entries: list[str]
    missing_scope_fence_entries: list[str]
    unexpected_dead_weight: list[str]
    root_json_files: list[str]
    retention_import_sites: dict[str, list[str]]


@dataclass(frozen=True)
class VendoredAgentHistoryAudit:
    tracked: bool
    preserved_history: bool
    commit_lines: list[str]
    error: str | None = None


def audit_vendored_agent_tree(repo_root: Path) -> VendoredAgentTreeAudit:
    agent_root = repo_root / "arnold" / "pipelines" / "megaplan" / "agent"

    missing_runtime_entries = [
        entry for entry in RUNTIME_REQUIRED_ENTRIES if not (agent_root / entry).exists()
    ]
    missing_scope_fence_entries = [
        entry for entry in JOB_B_SCOPE_FENCE_ENTRIES if not (agent_root / entry).exists()
    ]

    unexpected_dead_weight: list[str] = []
    for pattern in DEAD_WEIGHT_PATTERNS:
        matches = sorted(agent_root.glob(pattern))
        unexpected_dead_weight.extend(
            str(match.relative_to(agent_root))
            for match in matches
            if match.exists()
        )

    root_json_files = sorted(path.name for path in agent_root.glob("*.json"))
    retention_import_sites = find_retention_import_sites(agent_root)

    return VendoredAgentTreeAudit(
        missing_runtime_entries=missing_runtime_entries,
        missing_scope_fence_entries=missing_scope_fence_entries,
        unexpected_dead_weight=unexpected_dead_weight,
        root_json_files=root_json_files,
        retention_import_sites=retention_import_sites,
    )


def find_retention_import_sites(
    agent_root: Path,
    *,
    include_tests: bool = False,
) -> dict[str, list[str]]:
    findings = {name: [] for name in CONDITIONAL_RETENTION_DIRS}

    for py_file in sorted(agent_root.rglob("*.py")):
        relative = py_file.relative_to(agent_root)
        relative_parts = relative.parts
        if py_file.name.startswith(".") or any(part.startswith(".") for part in relative_parts):
            continue
        if any(part in CONDITIONAL_RETENTION_DIRS for part in relative_parts):
            continue
        if not include_tests and "tests" in relative_parts:
            continue

        try:
            lines = py_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue

        for lineno, line in enumerate(lines, start=1):
            for name, pattern in _RETENTION_IMPORT_PATTERNS.items():
                if pattern.search(line):
                    findings[name].append(f"{relative}:{lineno}")

    return findings


def audit_vendored_agent_history(repo_root: Path) -> VendoredAgentHistoryAudit:
    log_result = subprocess.run(
        ["git", "-C", str(repo_root), "log", "--oneline", "--", "arnold/pipelines/megaplan/agent/"],
        capture_output=True,
        text=True,
        check=False,
    )
    if log_result.returncode != 0:
        return VendoredAgentHistoryAudit(
            tracked=False,
            preserved_history=False,
            commit_lines=[],
            error=log_result.stderr.strip() or log_result.stdout.strip() or "git log failed",
        )

    commit_lines = [line for line in log_result.stdout.splitlines() if line.strip()]
    tracked_result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "ls-files",
            "--error-unmatch",
            "arnold/pipelines/megaplan/agent/run_agent.py",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    tracked = tracked_result.returncode == 0

    return VendoredAgentHistoryAudit(
        tracked=tracked,
        preserved_history=tracked and len(commit_lines) > 1,
        commit_lines=commit_lines,
        error=None,
    )
