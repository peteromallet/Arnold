"""Arnold console entry point.

Arnold is the module-oriented namespace over the pipeline registry. It keeps the
existing ``megaplan`` console script live while exposing discovered pipeline
modules without a privileged planning branch.
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from megaplan._pipeline.registry import (
    canonical_pipeline_name,
    discover_python_pipelines,
    pipeline_metadata,
    scan_python_pipelines,
)

UMBRELLA_OVERRIDE_ACTIONS: tuple[str, ...] = (
    "abort",
    "add-note",
    "set-robustness",
    "set-profile",
    "set-model",
    "set-vendor",
)

PLANNING_OVERRIDE_ACTIONS: tuple[str, ...] = (
    "force-proceed",
    "replan",
    "recover-blocked",
    "resume-clarify",
)

MODULE_VERBS: tuple[str, ...] = ("run", "check", "doctor", "describe", "auto")
PLANNING_MODULE_VERBS: tuple[str, ...] = (*MODULE_VERBS, "override")


def cli_entry() -> None:
    sys.exit(main())


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        _print_usage()
        return 2

    command = args[0]
    rest = args[1:]

    if command == "run":
        return _megaplan_main(["run", *rest])
    if command == "pipelines":
        return _handle_pipelines(rest)
    if command == "auto":
        return _handle_auto(rest)
    if command == "override":
        return _handle_umbrella_override(rest)

    modules = _discovered_module_names()
    module = canonical_pipeline_name(command)
    if module in modules:
        return _handle_module_verb(module, rest)

    print(f"arnold: unknown command or module {command!r}", file=sys.stderr)
    _print_usage(file=sys.stderr)
    return 2


def _megaplan_main(argv: list[str]) -> int:
    from megaplan.cli import main as megaplan_main

    return megaplan_main(argv)


def _discovered_module_names() -> set[str]:
    try:
        return {name for name, _builder, _meta, _path in discover_python_pipelines()}
    except RuntimeError:
        return {
            str(d.cli_name)
            for d in scan_python_pipelines()
            if d.status == "discovered" and d.cli_name
        }


def _pipeline_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    try:
        quads = discover_python_pipelines()
    except RuntimeError:
        quads = []
    seen: set[str] = set()
    for name, _builder, meta, source_path in quads:
        seen.add(name)
        merged = dict(meta)
        merged.update(pipeline_metadata(name))
        rows.append(
            {
                "name": name,
                "status": "discovered",
                "description": str(merged.get("description") or ""),
                "source_path": str(source_path),
                "arnold_api_version": merged.get("arnold_api_version"),
                "capabilities": list(merged.get("capabilities") or ()),
                "reason": "",
            }
        )
    for disposition in scan_python_pipelines():
        if not disposition.cli_name or disposition.cli_name in seen:
            continue
        if disposition.status == "discovered" and disposition.manifest is not None:
            manifest = disposition.manifest
            rows.append(
                {
                    "name": disposition.cli_name,
                    "status": "discovered",
                    "description": manifest.description,
                    "source_path": str(disposition.path),
                    "arnold_api_version": manifest.arnold_api_version,
                    "capabilities": list(manifest.capabilities),
                    "reason": disposition.reason,
                }
            )
        elif disposition.status == "rejected":
            rows.append(
                {
                    "name": disposition.cli_name,
                    "status": "rejected",
                    "description": "",
                    "source_path": str(disposition.path),
                    "arnold_api_version": None,
                    "capabilities": [],
                    "reason": disposition.reason,
                }
            )
    return sorted(rows, key=lambda row: str(row["name"]))


def _handle_pipelines(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="arnold pipelines")
    sub = parser.add_subparsers(dest="action", required=True)
    list_parser = sub.add_parser("list", help="List discovered Arnold modules")
    list_parser.add_argument("--json", action="store_true", dest="as_json")
    check_parser = sub.add_parser("check", help="Validate a discovered module")
    check_parser.add_argument("module")
    sub.add_parser("doctor", help="Print discovery dispositions")
    ns = parser.parse_args(argv)

    if ns.action == "list":
        rows = _pipeline_rows()
        if ns.as_json:
            import json

            print(json.dumps({"pipelines": rows}, indent=2))
            return 0
        for row in rows:
            desc = str(row.get("description") or "")
            if row.get("status") == "rejected":
                print(
                    f"{row['name']}\trejected\t{row.get('reason') or ''}",
                    file=sys.stderr,
                )
                continue
            print(f"{row['name']}\t{desc}")
        return 0
    if ns.action == "check":
        return _megaplan_main(["pipelines", "check", canonical_pipeline_name(ns.module)])
    if ns.action == "doctor":
        return _megaplan_main(["pipelines", "doctor"])
    return 2


def _handle_auto(argv: list[str]) -> int:
    module = "planning"
    rest = list(argv)
    if rest and not rest[0].startswith("-"):
        module = canonical_pipeline_name(rest.pop(0))
    if module != "planning":
        print("arnold auto currently supports the planning module only", file=sys.stderr)
        return 2
    return _megaplan_main(["auto", *rest])


def _handle_umbrella_override(argv: list[str]) -> int:
    if not argv:
        return _megaplan_main(["override"])
    action = argv[0]
    if action in PLANNING_OVERRIDE_ACTIONS:
        print(
            f"arnold override: {action!r} is planning-scoped; "
            f"use 'arnold planning override {action}'",
            file=sys.stderr,
        )
        return 2
    if action not in UMBRELLA_OVERRIDE_ACTIONS:
        print(f"arnold override: unknown action {action!r}", file=sys.stderr)
        return 2
    return _megaplan_main(["override", *argv])


def _handle_planning_override(argv: list[str]) -> int:
    if not argv:
        return _megaplan_main(["override"])
    action = argv[0]
    if action in UMBRELLA_OVERRIDE_ACTIONS:
        print(
            f"arnold planning override: {action!r} is umbrella-scoped; "
            f"use 'arnold override {action}'",
            file=sys.stderr,
        )
        return 2
    if action not in PLANNING_OVERRIDE_ACTIONS:
        print(f"arnold planning override: unknown action {action!r}", file=sys.stderr)
        return 2
    return _megaplan_main(["override", *argv])


def _handle_module_verb(module: str, argv: list[str]) -> int:
    if not argv:
        print(f"arnold {module}: missing verb", file=sys.stderr)
        return 2
    verb, rest = argv[0], argv[1:]
    if verb == "run":
        return _megaplan_main(["run", module, *rest])
    if verb == "check":
        return _megaplan_main(["pipelines", "check", module, *rest])
    if verb == "doctor":
        return _megaplan_main(["pipelines", "doctor", *rest])
    if verb == "describe":
        return _megaplan_main(["run", module, "--describe", *rest])
    if verb == "auto":
        return _handle_auto([module, *rest])
    if verb == "override" and module == "planning":
        return _handle_planning_override(rest)
    if verb == "override":
        print(
            f"arnold {module}: override is only available for the planning module",
            file=sys.stderr,
        )
        return 2
    print(f"arnold {module}: unknown verb {verb!r}", file=sys.stderr)
    return 2


def _print_usage(*, file=None) -> None:  # type: ignore[no-untyped-def]
    target = file or sys.stdout
    print(
        "usage: arnold run ... | arnold pipelines {list,check,doctor} | "
        "arnold <module> {run,check,doctor,describe,auto} | "
        "arnold planning override ... | arnold auto [planning] ... | "
        "arnold override ...",
        file=target,
    )


__all__ = [
    "MODULE_VERBS",
    "PLANNING_MODULE_VERBS",
    "PLANNING_OVERRIDE_ACTIONS",
    "UMBRELLA_OVERRIDE_ACTIONS",
    "main",
    "cli_entry",
]


if __name__ == "__main__":
    cli_entry()
