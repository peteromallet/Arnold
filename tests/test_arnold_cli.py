from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from arnold.pipeline.native.checkpoint import classify_resume_cursor, read_native_cursor
from arnold.pipeline.resume import persist_resume_cursor
from arnold.pipelines.megaplan.cli import arnold


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


def test_arnold_pipelines_run_forwards_runtime_flags(monkeypatch) -> None:
    calls: list[list[str]] = []

    monkeypatch.setattr(
        arnold,
        "_megaplan_main",
        lambda argv: calls.append(list(argv)) or 0,
    )

    assert (
        arnold.main(
            [
                "pipelines",
                "run",
                "planning",
                "--runtime",
                "graph",
                "--plan-dir",
                "/tmp/demo",
            ]
        )
        == 0
    )
    assert calls == [
        ["run", "megaplan", "--runtime", "graph", "--plan-dir", "/tmp/demo"]
    ]


def test_arnold_pipelines_upgrade_cursor_defaults_to_dry_run(
    tmp_path: Path,
    capsys,
) -> None:
    persist_resume_cursor(tmp_path, stage="prep", resume_cursor="graph-cursor")

    assert arnold.main(["pipelines", "upgrade-cursor", str(tmp_path)]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    assert payload["dry_run"] is True
    assert payload["written"] is False
    assert payload["graph_stage"] == "prep"
    assert payload["native_stage"] == "megaplan__prep__pc0"
    assert classify_resume_cursor(tmp_path) == "graph"


def test_arnold_pipelines_upgrade_cursor_write_preserves_graph_backup(
    tmp_path: Path,
    capsys,
) -> None:
    persist_resume_cursor(tmp_path, stage="plan", resume_cursor="graph-cursor")

    assert arnold.main(["pipelines", "upgrade-cursor", str(tmp_path), "--write"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    assert payload["dry_run"] is False
    assert payload["written"] is True
    assert payload["backup_path"]
    backup_path = Path(payload["backup_path"])
    assert backup_path.exists()
    backup = json.loads(backup_path.read_text(encoding="utf-8"))
    assert backup["stage"] == "plan"
    assert "native" not in backup

    cursor = read_native_cursor(tmp_path)
    assert cursor is not None
    assert cursor["stage"] == "megaplan__plan__pc1"
    assert cursor["native"]["pc"] == 1


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
        [sys.executable, "-m", "arnold.pipelines.megaplan.cli.arnold", "pipelines", "list"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "megaplan" in proc.stdout
    assert "creative" in proc.stdout
    assert "doc" in proc.stdout
    assert "jokes" in proc.stdout
