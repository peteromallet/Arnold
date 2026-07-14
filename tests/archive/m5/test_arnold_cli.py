"""Archived legacy umbrella-CLI tests; active argv compatibility lives separately."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from arnold.pipeline.native.checkpoint import classify_resume_cursor, read_native_cursor
from arnold.pipeline.resume import persist_resume_cursor
from arnold_pipelines.megaplan.cli import arnold
from arnold_pipelines.megaplan.cli import _normalize_execute_compat_argv


def test_arnold_pipelines_list_wraps_discovery_and_lists_first_class_modules(
    capsys,
) -> None:
    rc = arnold.main(["pipelines", "list"])
    assert rc == 0
    out = capsys.readouterr().out
    for name in ("megaplan", "creative", "doc", "jokes"):
        assert name in out
    assert "privilege" not in out.lower()


def test_arnold_module_verb_dispatches_run(monkeypatch) -> None:
    calls: list[list[str]] = []

    monkeypatch.setattr(
        arnold,
        "_megaplan_main",
        lambda argv: calls.append(list(argv)) or 0,
    )

    assert arnold.main(["planning", "run", "--plan-dir", "/tmp/demo"]) == 0
    assert calls == [["run", "megaplan", "--plan-dir", "/tmp/demo"]]






def test_arnold_auto_defaults_to_megaplan(monkeypatch) -> None:
    calls: list[list[str]] = []

    monkeypatch.setattr(
        arnold,
        "_megaplan_main",
        lambda argv: calls.append(list(argv)) or 0,
    )

    assert arnold.main(["auto", "--plan", "demo"]) == 0
    assert calls == [["auto", "--plan", "demo"]]


def test_arnold_auto_accepts_legacy_planning_alias(monkeypatch) -> None:
    calls: list[list[str]] = []

    monkeypatch.setattr(
        arnold,
        "_megaplan_main",
        lambda argv: calls.append(list(argv)) or 0,
    )

    assert arnold.main(["auto", "planning", "--plan", "demo"]) == 0
    assert calls == [["auto", "--plan", "demo"]]


def test_arnold_usage_uses_canonical_megaplan(capsys) -> None:
    assert arnold.main([]) == 2
    out = capsys.readouterr().out
    assert "arnold auto [megaplan]" in out
    assert "[planning]" not in out


def test_arnold_console_module_entry_lists_pipelines() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "arnold_pipelines.megaplan.cli.arnold", "pipelines", "list"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "megaplan" in proc.stdout
    assert "creative" in proc.stdout
    assert "doc" in proc.stdout
    assert "jokes" in proc.stdout


def test_normalize_execute_compat_argv_infers_missing_execute_for_execute_only_flags() -> None:
    assert _normalize_execute_compat_argv(
        [
            "--confirm-destructive",
            "--user-approved",
            "--retry-blocked-tasks",
        ]
    ) == [
        "execute",
        "--confirm-destructive",
        "--user-approved",
        "--retry-blocked-tasks",
    ]


def test_normalize_execute_compat_argv_infers_missing_execute_after_root_flags() -> None:
    assert _normalize_execute_compat_argv(
        [
            "--actor",
            "repair-loop-dev-fix",
            "--backend",
            "file",
            "--confirm-destructive",
            "--user-approved",
            "--retry-blocked-tasks",
        ]
    ) == [
        "--actor",
        "repair-loop-dev-fix",
        "--backend",
        "file",
        "execute",
        "--confirm-destructive",
        "--user-approved",
        "--retry-blocked-tasks",
    ]


def test_normalize_execute_compat_argv_infers_missing_execute_for_mixed_execute_tail() -> None:
    assert _normalize_execute_compat_argv(
        [
            "--actor",
            "repair-loop-dev-fix",
            "--backend",
            "file",
            "--confirm-destructive",
            "--user-approved",
            "--retry-blocked-tasks",
            "--plan",
            "m7-runtime-conformance-and-20260628-1118",
        ]
    ) == [
        "--actor",
        "repair-loop-dev-fix",
        "--backend",
        "file",
        "execute",
        "--confirm-destructive",
        "--user-approved",
        "--retry-blocked-tasks",
        "--plan",
        "m7-runtime-conformance-and-20260628-1118",
    ]
