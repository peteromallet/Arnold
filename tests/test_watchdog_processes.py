"""Tests for watchdog process scanning."""

from __future__ import annotations

from arnold.pipelines.megaplan.watchdog.processes import ProcessRecord, scan_processes


def test_scanner_parses_process_signatures():
    lines = [
        "  PID ARGS",
        "12345 /Users/peter/.local/bin/megaplan auto --plan foo",
        "12346 /Users/peter/.local/bin/arnold pipelines run live-supervisor",
        "12347 /opt/homebrew/bin/shannon --session abc",
        "12348 /usr/local/bin/codex",
        "12349 /Applications/Claude.app/Contents/MacOS/claude",
        "12350 /bin/bash /some/other/script",
    ]
    records = scan_processes(lines)
    by_pid = {r.pid: r for r in records}
    assert len(by_pid) == 5
    assert by_pid[12345].category == "megaplan"
    assert by_pid[12346].category == "arnold"
    assert by_pid[12347].category == "shannon"
    assert by_pid[12348].category == "codex"
    assert by_pid[12349].category == "claude"


def test_scanner_extracts_cwd_from_claude_spawned_by():
    lines = [
        '19074 /Users/peter/.local/bin/claude daemon run --origin transient --spawned-by {"label":"claude","cwd":"/Users/peter/Documents/megaplan","pid":6766}',
    ]
    records = scan_processes(lines)
    assert len(records) == 1
    assert records[0].cwd == "/Users/peter/Documents/megaplan"


def test_scanner_extracts_cwd_from_tmux_cmdline():
    lines = [
        "15151 tmux new-session -d -s sess -c /Users/peter/project env claude",
    ]
    records = scan_processes(lines)
    assert len(records) == 1
    assert records[0].cwd == "/Users/peter/project"


def test_scanner_checks_pid_liveness(monkeypatch):
    def _fake_pid_is_live(pid: int) -> bool:
        return pid == 42

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.watchdog.processes._pid_is_live",
        _fake_pid_is_live,
    )
    lines = [
        " 42 megaplan auto --plan foo",
        " 99 megaplan auto --plan bar",
    ]
    records = scan_processes(lines)
    assert records[0].is_live is True
    assert records[1].is_live is False


def test_scanner_categorizes_dotted_module_path():
    # Dotted module paths must be tokenized so these processes are detected at all.
    lines = [
        "32646 /Users/peter/.pyenv/versions/3.11.11/bin/python3 -m arnold.pipelines.megaplan init .megaplan/briefs/audio-lifecycle-gremlin-catcher-after-20260615-1910.md --project-dir . --profile partnered-5 --vendor codex --auto-approve --auto-start --name audio-lifecycle-gremlin-catcher",
        "32647 /Users/peter/.pyenv/versions/3.11.11/bin/python3 -m megaplan.server",
        "32648 /Users/peter/.pyenv/versions/3.11.11/bin/python3 -m arnold.cli.run",
    ]
    records = scan_processes(lines)
    by_pid = {r.pid: r for r in records}
    assert 32646 in by_pid
    assert by_pid[32646].category in ("arnold", "megaplan")
    assert 32647 in by_pid
    assert by_pid[32647].category == "megaplan"
    assert 32648 in by_pid
    assert by_pid[32648].category == "arnold"


def test_scanner_ignores_header_and_empty_lines():
    lines = ["", "  PID ARGS", "   "]
    assert scan_processes(lines) == ()
