"""Repro for T8 rework: inspect_strategy_migration must not crash.

Run from the project dir: python _repro_t8.py
Deleted after verification.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from arnold_pipelines.megaplan.strategy.migration import (  # noqa: E402
    inspect_strategy_migration,
)


def _write(repo, body):
    (repo / ".megaplan").mkdir(parents=True, exist_ok=True)
    (repo / ".megaplan" / "STRATEGY.md").write_text(body, encoding="utf-8")


def _tickets(repo, files):
    tdir = repo / ".megaplan" / "tickets"
    tdir.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        (tdir / name).write_text(body, encoding="utf-8")


def main():
    cases = {
        "absent": ("", []),
        "current": (
            "---\nschema_version: megaplan-strategy-v1\n---\n\n# Strategy\n\n## Now\n\n## Next\n\n## Later\n",
            [],
        ),
        "legacy": (
            "---\nschema_version: megaplan-strategy-v0\n---\n\n# Strategy\n\n## Now\n\n## Next\n\n## Later\n",
            [],
        ),
        "unsupported-new": (
            "---\nschema_version: megaplan-strategy-v99\n---\n\n# Strategy\n\n## Now\n\n## Next\n\n## Later\n",
            [],
        ),
        "with-legacy-epics": (
            "---\nschema_version: megaplan-strategy-v1\n---\n\n# Strategy\n\n## Now\n\n## Next\n\n## Later\n",
            [
                (
                    "01H8XGJHBWCA7N3XKQ4Z8P5M0N-task.md",
                    "---\nid: 01H8XGJHBWCA7N3XKQ4Z8P5M0N\n"
                    "title: A task\nstatus: open\n"
                    "epics:\n"
                    "  - alpha-initiative\n"
                    "---\n\nbody\n",
                )
            ],
        ),
    }

    for name, (strat, tickets) in cases.items():
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            if strat:
                _write(repo, strat)
            if tickets:
                _tickets(repo, {fn: b for fn, b in tickets})
            try:
                r = inspect_strategy_migration(repo)
                print(
                    f"  {name:18s}: status={r.status:15s} "
                    f"version={r.version_status:18s} safe={r.safe_to_apply} "
                    f"findings={len(r.findings)} actions={len(r.proposed_actions)} "
                    f"-> OK"
                )
            except Exception as exc:  # noqa: BLE001
                print(f"  {name:18s}: {type(exc).__name__}: {exc}  -> CRASH (bad)")


if __name__ == "__main__":
    main()
