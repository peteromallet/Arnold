"""CLI parser snapshot characterization — serialize ``megaplan.cli.build_parser()``
recursively through argparse subparsers into a stable, readable JSON fixture.

Scope: ``build_parser()`` only
  *Captures* every subcommand, nested subcommand, option, positional, and
  mutually-exclusive group declared inside ``build_parser()``.

  *Does NOT capture* the lazy cloud/resident/bakeoff subcommand trees that are
  registered in ``main()`` (cli.py lines 4960-5001).  Only the passthrough
  ``nargs=REMAINDER`` entries for those three top-level commands are included.

Why this exists
  When ``megaplan.cli`` is refactored (e.g. M5b split), this snapshot detects
  accidental changes to the parser shape — renamed flags, missing subcommands,
  changed defaults, altered nargs/choices/metavar, etc.  The fixture is human-
  readable JSON so a reviewer can eyeball diffs directly.

Normalization rules
  * ``argparse.SUPPRESS`` → ``"<SUPPRESS>"``
  * Callables (``type`` functions, ``choices`` callable) → qualified name
    (e.g. ``"int"``, ``"builtins.float"``, ``"arnold_pipelines.megaplan.cli._non_negative_float"``)
  * Classes → qualified name (e.g. ``"builtins.int"``)
  * ``argparse.REMAINDER`` → ``"REMAINDER"``
  * Keys in every JSON object are sorted for deterministic output.
  * The ``--help`` / ``-h`` action (``_HelpAction``) is included so that the
    full action list is represented, but ``option_strings`` are sorted so
    ``--help`` always comes after ``-h``.

Schema
  The top-level JSON object has a ``commands`` key whose value is a
  dictionary keyed by command name (``""`` for the root parser).  Each
  command object has:

  * ``options`` — list of non-subparser actions, each with keys:
    ``option_strings`` (sorted), ``dest``, ``action``, ``nargs``, ``const``,
    ``default``, ``type``, ``choices``, ``required``, ``metavar``, ``help``
  * ``positionals`` — list of positional-only actions (``option_strings`` empty)
  * ``mutually_exclusive_groups`` — list of groups, each with ``required`` and
    ``actions`` (list of action objects as above)
  * ``subcommands`` — dict of nested command objects (empty if leaf)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

_SENTINEL_MAP: dict[Any, str] = {
    argparse.SUPPRESS: "<SUPPRESS>",
}


def _normalize_nargs(nargs: Any) -> str | None:
    """Convert nargs to a deterministic string representation.

    * ``None`` → ``None`` (JSON null)
    * ``?`` → ``"?"``
    * ``*`` → ``"*"``
    * ``+`` → ``"+"``
    * ``argparse.REMAINDER`` → ``"REMAINDER"``
    * integers → their string form (``"0"``, ``"1"``, …)
    """
    if nargs is None:
        return None
    if nargs is argparse.REMAINDER:
        return "REMAINDER"
    return str(nargs)


def _normalize_value(val: Any) -> Any:
    """Return a JSON-serializable representation of *val*.

    Sentinel objects (``argparse.SUPPRESS``) become ``"<SUPPRESS>"``.
    Callables (functions, builtins, classes) become their qualified name.
    Tuples become lists (sorted for determinism).
    Lists and other sequences become lists with normalized elements.
    Everything else is returned as-is (hopefully already JSON-serializable).
    """
    # Unhashable types — handle before the sentinel dict lookup.
    if isinstance(val, list):
        return [_normalize_value(v) for v in val]
    if isinstance(val, tuple):
        return sorted(_normalize_value(v) for v in val)
    # Sentinel dict lookup (hashable types only).
    try:
        if val in _SENTINEL_MAP:
            return _SENTINEL_MAP[val]
    except TypeError:
        pass
    if callable(val):
        # builtin functions like <built-in function print> don't have __qualname__
        return getattr(val, "__qualname__", None) or getattr(val, "__name__", None) or repr(val)
    return val


def _action_to_dict(action: argparse.Action) -> dict[str, Any]:
    """Serialize a single argparse action to a stable dictionary."""
    return {
        "option_strings": sorted(action.option_strings),
        "dest": action.dest,
        "action": type(action).__name__,
        "nargs": _normalize_nargs(action.nargs),
        "const": _normalize_value(action.const),
        "default": _normalize_value(action.default),
        "type": _normalize_value(action.type),
        "choices": _normalize_value(action.choices),
        "required": action.required,
        "metavar": _normalize_value(action.metavar),
        "help": action.help,
    }


# ---------------------------------------------------------------------------
# Recursive parser walker
# ---------------------------------------------------------------------------

def _walk_parser(parser: argparse.ArgumentParser) -> dict[str, Any]:
    """Recursively walk *parser* and return a command dictionary.

    Returns a dict with keys: ``options``, ``positionals``,
    ``mutually_exclusive_groups``, ``subcommands``.
    """
    options: list[dict[str, Any]] = []
    positionals: list[dict[str, Any]] = []
    subcommands: dict[str, Any] = {}

    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            # Recurse into each subcommand
            for name, sub_parser in sorted(action.choices.items()):
                subcommands[name] = _walk_parser(sub_parser)
        elif not action.option_strings:
            # Positional argument (no leading dashes)
            positionals.append(_action_to_dict(action))
        else:
            options.append(_action_to_dict(action))

    # Collect mutually-exclusive groups
    mutex_groups: list[dict[str, Any]] = []
    for group in parser._mutually_exclusive_groups:
        mutex_groups.append({
            "required": group.required,
            "actions": [_action_to_dict(a) for a in group._group_actions],
        })

    return {
        "options": options,
        "positionals": positionals,
        "mutually_exclusive_groups": mutex_groups,
        "subcommands": subcommands,
    }


def build_snapshot() -> dict[str, Any]:
    """Build the complete CLI parser snapshot from ``megaplan.cli.build_parser()``.

    Returns a dict with a single key ``"commands"`` whose value is the
    recursive walk rooted at ``""`` (the root parser).
    """
    from arnold_pipelines.megaplan.cli import build_parser

    root_parser = build_parser()
    root_command = _walk_parser(root_parser)
    return {"commands": {"": root_command}}


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"
FIXTURE_PATH = FIXTURE_DIR / "cli_parser_snapshot.json"


def _read_fixture() -> dict[str, Any]:
    """Read the on-disk fixture, failing the test if it doesn't exist."""
    if not FIXTURE_PATH.exists():
        pytest.fail(
            f"Fixture not found: {FIXTURE_PATH}\n"
            f"Generate it with: python -m pytest {Path(__file__).name} "
            f"-k test_generate_fixture --write-fixture"
        )
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _write_fixture(data: dict[str, Any]) -> None:
    """Write *data* as pretty-printed JSON to the fixture path."""
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCliParserSnapshot:
    """Snapshot characterization for ``megaplan.cli.build_parser()``."""

    def test_snapshot_matches_fixture(self) -> None:
        """Build the parser snapshot in-process and compare against the
        committed fixture.  Fails if the parser shape has changed."""
        current = build_snapshot()
        fixture = _read_fixture()

        # Use JSON round-trip to normalize key ordering and whitespace.
        current_str = json.dumps(current, indent=2, sort_keys=True)
        fixture_str = json.dumps(fixture, indent=2, sort_keys=True)

        if current_str != fixture_str:
            # Produce a helpful diff-style message.
            msg = "CLI parser snapshot has diverged from the committed fixture.\n\n"
            msg += "If the change is intentional, regenerate the fixture with:\n"
            msg += f"  python -m pytest {Path(__file__).name} -k test_generate_fixture --write-fixture\n\n"
            msg += "Changed keys:\n"
            # Quick top-level key comparison
            current_keys = set(current.get("commands", {}).keys()) | {""}
            fixture_keys = set(fixture.get("commands", {}).keys()) | {""}
            if current_keys != fixture_keys:
                added = current_keys - fixture_keys
                removed = fixture_keys - current_keys
                if added:
                    msg += f"  Added: {sorted(added)}\n"
                if removed:
                    msg += f"  Removed: {sorted(removed)}\n"

            # Compare subcommand counts
            cur_root = current.get("commands", {}).get("", {})
            fix_root = fixture.get("commands", {}).get("", {})
            cur_subs = set(cur_root.get("subcommands", {}).keys())
            fix_subs = set(fix_root.get("subcommands", {}).keys())
            if cur_subs != fix_subs:
                sub_added = cur_subs - fix_subs
                sub_removed = fix_subs - cur_subs
                if sub_added:
                    msg += f"  Subcommands added: {sorted(sub_added)}\n"
                if sub_removed:
                    msg += f"  Subcommands removed: {sorted(sub_removed)}\n"

            pytest.fail(msg)

    def test_generate_fixture(self, request: pytest.FixtureRequest) -> None:
        """Generate (or overwrite) the JSON fixture on disk.

        Opt-in via ``--write-fixture``::

            python -m pytest tests/characterization/test_cli_parser_snapshot.py \\
                -k test_generate_fixture --write-fixture
        """
        if not request.config.getoption("--write-fixture", default=False):
            pytest.skip("Pass --write-fixture to regenerate the fixture")

        snapshot = build_snapshot()
        _write_fixture(snapshot)

        # Verify round-trip: read it back and compare
        reloaded = _read_fixture()
        current_str = json.dumps(snapshot, indent=2, sort_keys=True)
        reloaded_str = json.dumps(reloaded, indent=2, sort_keys=True)
        assert current_str == reloaded_str, (
            "Fixture round-trip failed: written JSON does not match in-memory snapshot"
        )

    def test_lazy_subcommands_are_passthrough_only(self) -> None:
        """Document that cloud/resident/bakeoff subcommands are dispatched
        before ``build_parser()`` in ``main()`` and are *not* registered
        inside ``build_parser()``.

        The real subcommand trees for cloud, resident, and bakeoff are
        intercepted at the top of ``main()`` (cli.py lines 3236-3289)
        before the parser is even built.  This test asserts that they
        are absent from ``build_parser()`` so that a future refactor
        that moves them into the parser is immediately visible.
        """
        fixture = _read_fixture()
        root = fixture["commands"][""]
        subcommands = root.get("subcommands", {})

        for cmd in ("cloud", "resident", "bakeoff"):
            assert cmd not in subcommands, (
                f"'{cmd}' should NOT be in build_parser() — it is dispatched "
                f"before the parser in main(). If this fails, the lazy "
                f"dispatch was moved into build_parser() and this test must "
                f"be updated."
            )

    def test_root_parser_has_expected_top_level_options(self) -> None:
        """Sanity-check that the root parser has ``--actor`` and ``--backend``
        global options plus a required ``command`` subparser."""
        fixture = _read_fixture()
        root = fixture["commands"][""]

        option_dests = {o["dest"] for o in root["options"]}
        assert "actor" in option_dests, "Root parser missing --actor"
        assert "backend" in option_dests, "Root parser missing --backend"

        # The root must have subcommands (the 'command' subparser).
        assert root["subcommands"], "Root parser must declare subcommands"

    def test_at_least_expected_subcommands_exist(self) -> None:
        """Ensure key subcommands that the codebase depends on are present."""
        fixture = _read_fixture()
        root = fixture["commands"][""]
        subcommands = set(root.get("subcommands", {}).keys())

        expected = {
            "setup", "init", "brief", "ticket", "strategy",
            "resume", "audit", "plan", "prep", "critique",
            "revise", "gate", "finalize", "execute", "review",
            "override", "user-action", "quality-gate",
            "verify-human", "audit-verifiability",
            "auto", "chain", "epic-chain",
            "introspect", "trace", "doctor", "record-tag",
            "status", "progress", "watch",
            "initiative", "authority-inventory",
            "migrate-layout", "pipelines",
        }
        missing = expected - subcommands
        assert not missing, (
            f"Missing expected subcommands: {sorted(missing)}"
        )

    def test_nested_subcommands_present(self) -> None:
        """Verify known nested subcommand trees are captured."""
        fixture = _read_fixture()
        root = fixture["commands"][""]
        subs = root["subcommands"]

        # brief -> new, list, show, search, epic
        brief_subs = set(subs.get("brief", {}).get("subcommands", {}).keys())
        assert {"new", "list", "show", "search", "epic"}.issubset(brief_subs), (
            f"brief subcommands incomplete: {sorted(brief_subs)}"
        )

        # ticket -> new, list, show, edit, link, search, promote, ...
        ticket_subs = set(subs.get("ticket", {}).get("subcommands", {}).keys())
        assert {"new", "list", "show", "edit", "search", "promote"}.issubset(ticket_subs), (
            f"ticket subcommands incomplete: {sorted(ticket_subs)}"
        )

        # strategy -> init, validate, show, list, project, add, remove, move
        strategy_subs = set(subs.get("strategy", {}).get("subcommands", {}).keys())
        assert {"init", "validate", "show", "list", "project", "add", "remove", "move"}.issubset(strategy_subs), (
            f"strategy subcommands incomplete: {sorted(strategy_subs)}"
        )

        # initiative -> new, list, search
        initiative_subs = set(subs.get("initiative", {}).get("subcommands", {}).keys())
        assert {"new", "list", "search"}.issubset(initiative_subs), (
            f"initiative subcommands incomplete: {sorted(initiative_subs)}"
        )

    def test_all_option_strings_are_sorted(self) -> None:
        """Ensure every action's ``option_strings`` list is sorted, which
        guarantees deterministic JSON output for flag synonyms like
        ``-h`` / ``--help``."""
        fixture = _read_fixture()

        def _check(obj: dict[str, Any], path: str) -> None:
            for opt in obj.get("options", []):
                oss = opt["option_strings"]
                assert oss == sorted(oss), (
                    f"{path}:option_strings not sorted: {oss}"
                )
            for pos in obj.get("positionals", []):
                oss = pos["option_strings"]
                assert oss == sorted(oss), (
                    f"{path}:positional option_strings not sorted: {oss}"
                )
            for mg in obj.get("mutually_exclusive_groups", []):
                for act in mg.get("actions", []):
                    oss = act["option_strings"]
                    assert oss == sorted(oss), (
                        f"{path}:mutex action option_strings not sorted: {oss}"
                    )
            for name, sub in obj.get("subcommands", {}).items():
                _check(sub, f"{path}/{name}")

        _check(fixture["commands"][""], "")

    def test_fixture_is_readable_json(self) -> None:
        """The fixture must be valid JSON and parse without error."""
        fixture = _read_fixture()
        assert isinstance(fixture, dict)
        assert "commands" in fixture
        assert "" in fixture["commands"]

    def test_tiebreaker_run_has_work_dir(self) -> None:
        """``tiebreaker-run`` is dispatched before ``build_parser()`` in
        ``main()`` (alongside ``tiebreaker`` at cli.py line 3388) and is
        therefore *not* registered inside ``build_parser()``.

        The ``--work-dir`` flag is handled by the common dispatch path
        in ``main()`` (line 3318) before any handler is called, so it
        applies uniformly regardless of parser registration.
        """
        fixture = _read_fixture()
        root = fixture["commands"][""]
        tb_run = root.get("subcommands", {}).get("tiebreaker-run", {})
        assert not tb_run, (
            "tiebreaker-run should NOT be in build_parser() — it is dispatched "
            "before the parser in main(). If this fails, tiebreaker-run was "
            "moved into build_parser() and this test must be updated."
        )
