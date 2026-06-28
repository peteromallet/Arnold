from __future__ import annotations

import argparse
from pathlib import Path

from arnold_pipelines.megaplan import cli


def test_main_consumes_execute_wrapper_flags_left_in_remaining(monkeypatch) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor", default=None)
    parser.add_argument("--backend", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    execute = sub.add_parser("execute")
    execute.add_argument("--plan", default=None)
    execute.add_argument("--project-dir", default=None)

    seen: dict[str, object] = {}

    def fake_execute(root: Path, args: argparse.Namespace) -> int:
        seen["root"] = root
        seen["args"] = args
        return 0

    monkeypatch.setattr(cli, "build_parser", lambda: parser)
    monkeypatch.setattr(cli, "_resolve_project_root", lambda args: Path("/tmp/demo"))
    monkeypatch.setattr(cli, "ensure_runtime_layout", lambda root: None)
    monkeypatch.setitem(cli.COMMAND_HANDLERS, "execute", fake_execute)

    rc = cli.main(
        [
            "execute",
            "--confirm-destructive",
            "--user-approved",
            "--retry-blocked-tasks",
        ]
    )

    assert rc == 0
    args = seen["args"]
    assert isinstance(args, argparse.Namespace)
    assert args.confirm_destructive is True
    assert args.user_approved is True
    assert args.retry_blocked_tasks is True
