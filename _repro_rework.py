"""Reproduce the two rework bugs (T8 + T9) before fixing."""
from __future__ import annotations

import sys
import traceback
from pathlib import Path
import tempfile


def repro_t8() -> None:
    print("=== T8: inspect_strategy_migration NameError ===")
    from arnold_pipelines.megaplan.strategy.migration import inspect_strategy_migration

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        (repo / ".megaplan").mkdir(parents=True)
        try:
            report = inspect_strategy_migration(repo)
            print("OK absent strategy:", report.status)
        except Exception:
            print("FAIL absent strategy:")
            traceback.print_exc()

        # Also test with a current strategy + ticket with legacy epics
        (repo / ".megaplan" / "STRATEGY.md").write_text(
            "---\n"
            "schema_version: megaplan-strategy-v1\n"
            "title: T\n"
            "---\n\n"
            "## Mission\n\nx\n\n"
            "## Principles\n\nx\n\n"
            "## Architecture Direction\n\nx\n\n"
            "## Constraints\n\nx\n\n"
            "## Non-Goals\n\nx\n\n"
            "## Now\n\n- [ticket:01HZABCDEFGHIJKLMNOPQRSTUVWXYZ012345] T\n\n"
            "## Next\n\n\n"
            "## Later\n\n\n",
            encoding="utf-8",
        )
        td = repo / ".megaplan" / "tickets"
        td.mkdir()
        (td / "01HZABC.md").write_text(
            "---\nid: 01HZABCDEFGHIJKLMNOPQRSTUVWXYZ012345\nepics:\n- epic-1\n---\nb\n",
            encoding="utf-8",
        )
        try:
            report = inspect_strategy_migration(repo)
            print("OK current+legacy:", report.status,
                  "actions:", [a.kind for a in report.proposed_actions])
        except Exception:
            print("FAIL current+legacy:")
            traceback.print_exc()


def repro_t9() -> None:
    print("\n=== T9: write handlers fail closed on invalid schema_version ===")
    import argparse
    from arnold_pipelines.megaplan.handlers.strategy import (
        handle_strategy_add,
        handle_strategy_move,
        handle_strategy_remove,
    )

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        mp = repo / ".megaplan"
        mp.mkdir(parents=True)
        strat = (
            "---\n"
            "schema_version: 999\n"
            "title: T\n"
            "---\n\n"
            "## Mission\n\nx\n\n"
            "## Principles\n\nx\n\n"
            "## Architecture Direction\n\nx\n\n"
            "## Constraints\n\nx\n\n"
            "## Non-Goals\n\nx\n\n"
            "## Now\n\n- [ticket:01HZABCDEFGHIJKLMNOPQRSTUVWXYZ012345] T\n\n"
            "## Next\n\n\n"
            "## Later\n\n\n"
        )
        (mp / "STRATEGY.md").write_text(strat, encoding="utf-8")
        # No tickets needed for remove/move; add needs artifact exist check,
        # but fail-closed on authority should happen before/around it.

        ns_remove = argparse.Namespace(type="ticket", ref="01HZABCDEFGHIJKLMNOPQRSTUVWXYZ012345")
        ns_move = argparse.Namespace(type="ticket", ref="01HZABCDEFGHIJKLMNOPQRSTUVWXYZ012345", horizon="Later")
        ns_add = argparse.Namespace(type="ticket", ref="01HZABCDEFGHIJKLMNOPQRSTUVWXYZ012345", title="T", horizon="Later")

        for name, fn, ns in (("remove", handle_strategy_remove, ns_remove),
                             ("move", handle_strategy_move, ns_move),
                             ("add", handle_strategy_add, ns_add)):
            before = (mp / "STRATEGY.md").read_text()
            try:
                res = fn(repo, ns)
                after = (mp / "STRATEGY.md").read_text()
                mutated = before != after
                print(f"{name}: NO FAIL-CLOSED  success={res.get('success')} mutated={mutated}")
            except Exception as exc:
                print(f"{name}: RAISED {type(exc).__name__}: {exc}")
            # restore content
            (mp / "STRATEGY.md").write_text(strat, encoding="utf-8")


if __name__ == "__main__":
    repro_t8()
    repro_t9()
