"""Repro for T9 rework: strict write commands must fail closed on invalid authority.

Run from the project dir: python _repro_t9.py
Deleted after verification.
"""
import sys
import tempfile
from pathlib import Path

# Ensure the project-dir copy of arnold_pipelines is imported (script dir is
# sys.path[0] when run as `python _repro_t9.py`).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from arnold_pipelines.megaplan.handlers.strategy import (  # noqa: E402
    handle_strategy_add,
    handle_strategy_remove,
    handle_strategy_move,
    CliError,
)


class Args:
    pass


def _make_bad_strategy(repo):
    """Create a STRATEGY.md with an unsupported schema_version: 999."""
    (repo / ".megaplan").mkdir(parents=True, exist_ok=True)
    (repo / ".megaplan" / "STRATEGY.md").write_text(
        "---\n"
        "schema_version: 999\n"
        "---\n\n"
        "# Strategy\n\n"
        "## Now\n\n"
        "- [ticket:01H8XGJHBWCA7N3XKQ4Z8P5M0N] An item\n\n"
        "## Next\n\n"
        "## Later\n",
        encoding="utf-8",
    )


def _check(cmd_name, fn, args, repo, before):
    try:
        fn(str(repo), args)
    except CliError as exc:
        print(f"  {cmd_name}: CliError({exc.code!r}) -> REJECTED (good)")
        return
    after = (repo / ".megaplan" / "STRATEGY.md").read_text(encoding="utf-8")
    changed = after != before
    print(
        f"  {cmd_name}: NO ERROR RAISED, file {'CHANGED' if changed else 'unchanged'} "
        f"-> BUG (should have failed closed)"
    )


def main():
    with tempfile.TemporaryDirectory() as d:
        repo = Path(d)
        _make_bad_strategy(repo)
        strat = repo / ".megaplan" / "STRATEGY.md"
        before = strat.read_text(encoding="utf-8")

        a = Args()
        a.type = "ticket"
        a.ref = "01H8XGJHBWCA7N3XKQ4Z8P5M0N"
        a.title = "An item"
        a.horizon = "Now"

        r = Args()
        r.type = "ticket"
        r.ref = "01H8XGJHBWCA7N3XKQ4Z8P5M0N"

        m = Args()
        m.type = "ticket"
        m.ref = "01H8XGJHBWCA7N3XKQ4Z8P5M0N"
        m.horizon = "Later"

        print("schema_version: 999 strategy — strict write commands:")
        _check("strategy add", handle_strategy_add, a, repo, before)
        _check("strategy remove", handle_strategy_remove, r, repo, before)
        _check("strategy move", handle_strategy_move, m, repo, before)

    # Sanity: a valid v1 strategy must still allow writes.
    with tempfile.TemporaryDirectory() as d:
        repo = Path(d)
        (repo / ".megaplan").mkdir(parents=True, exist_ok=True)
        (repo / ".megaplan" / "STRATEGY.md").write_text(
            "---\n"
            "schema_version: megaplan-strategy-v1\n"
            "---\n\n"
            "# Strategy\n\n"
            "## Now\n\n"
            "## Next\n\n"
            "## Later\n",
            encoding="utf-8",
        )
        a = Args()
        a.type = "ticket"
        a.ref = "01H8XGJHBWCA7N3XKQ4Z8P5M0N"
        a.title = "An item"
        a.horizon = "Now"
        try:
            out = handle_strategy_add(str(repo), a)
            print(f"\nvalid v1 strategy add -> success={out.get('success')} (good: not over-rejecting)")
        except CliError as exc:
            print(f"\nvalid v1 strategy add -> CliError({exc.code!r}) (unexpected over-rejection)")


if __name__ == "__main__":
    main()
