"""Arnold console entry point.

Arnold is the module-oriented namespace over the pipeline registry. It keeps the
existing ``megaplan`` console script live while exposing discovered pipeline
modules without a privileged legacy-planning branch.
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from arnold.runtime.operations import OperationKind
from arnold_pipelines.megaplan.registry import (
    override_catalog_for,
    pipeline_metadata,
    read_pipeline_skill_md,
    supported_operations_for,
)
from arnold_pipelines.megaplan.runtime.discovery import (
    canonical_pipeline_name,
    discover_python_pipelines,
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
# Legacy constant name retained to avoid churn in Arnold docs/tests; the
# canonical pipeline identity routed through this surface is ``megaplan``.
PLANNING_MODULE_VERBS: tuple[str, ...] = (*MODULE_VERBS, "override")

# Subcommand surface exposed by ``arnold pipelines``.
PIPELINES_ACTIONS: tuple[str, ...] = (
    "check",
    "describe",
    "doctor",
    "list",
    "new",
)


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
    if command == "pipeline":
        from arnold.pipeline._cli_check import run as _run_pipeline_cli

        return _run_pipeline_cli(rest)
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
    from arnold_pipelines.megaplan.cli import main as megaplan_main

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
    describe_parser = sub.add_parser("describe", help="Describe a discovered module")
    describe_parser.add_argument("module")
    sub.add_parser("doctor", help="Print discovery dispositions")
    new_parser = sub.add_parser("new", help="Scaffold a new module")
    new_parser.add_argument("module")
    new_parser.add_argument(
        "--driver",
        choices=["graph"],
        default="graph",
        help="Scaffold driver shape. Only 'graph' is supported today.",
    )
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
    if ns.action == "describe":
        return _print_pipeline_describe(canonical_pipeline_name(ns.module))
    if ns.action == "doctor":
        return _megaplan_main(["pipelines", "doctor"])
    if ns.action == "new":
        return _megaplan_main(
            [
                "pipelines",
                "new",
                canonical_pipeline_name(ns.module),
                "--driver",
                ns.driver,
            ]
        )
    return 2


def _format_metadata_value(value: object) -> str:
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return ", ".join(str(item) for item in sorted(value, key=str))
    return str(value)


def _print_pipeline_describe(module: str) -> int:
    if module not in _discovered_module_names():
        print(f"arnold pipelines describe: unknown module {module!r}", file=sys.stderr)
        return 2

    metadata = pipeline_metadata(module)
    lines: list[str] = [f"Pipeline: {module}"]
    source_path = metadata.get("source_path")
    if source_path:
        lines.append(f"Source: {source_path}")
    description = metadata.get("description")
    if description:
        lines.append("")
        lines.append(str(description))
    default_profile = metadata.get("default_profile")
    if default_profile:
        lines.append("")
        lines.append(f"Default profile: {default_profile}")
    recommended = metadata.get("recommended_profiles") or ()
    if recommended:
        lines.append(f"Recommended: {_format_metadata_value(recommended)}")
    modes = metadata.get("supported_modes") or ()
    if modes:
        lines.append(f"Modes: {_format_metadata_value(modes)}")
    driver = metadata.get("driver")
    if driver:
        lines.append(f"Driver: {_format_metadata_value(driver)}")
    entrypoint = metadata.get("entrypoint")
    if entrypoint:
        lines.append(f"Entrypoint: {entrypoint}")

    skill_md = read_pipeline_skill_md(module)
    if skill_md:
        lines.append("")
        lines.append("─── SKILL.md ───")
        lines.append(skill_md.strip())

    print("\n".join(lines))
    return 0


def _handle_auto(argv: list[str]) -> int:
    module = "megaplan"
    rest = list(argv)
    if rest and not rest[0].startswith("-"):
        module = canonical_pipeline_name(rest.pop(0))
    if module != "megaplan":
        print("arnold auto currently supports the megaplan module only", file=sys.stderr)
        return 2
    return _megaplan_main(["auto", *rest])


def _handle_umbrella_override(argv: list[str]) -> int:
    if not argv:
        return _megaplan_main(["override"])
    action = argv[0]
    catalog = _megaplan_override_catalog()
    if action in _megaplan_scoped_override_actions(catalog):
        print(
            f"arnold override: {action!r} is megaplan-scoped; "
            f"use 'arnold megaplan override {action}'",
            file=sys.stderr,
        )
        return 2
    if action not in _umbrella_override_actions(catalog):
        print(f"arnold override: unknown action {action!r}", file=sys.stderr)
        return 2
    return _megaplan_main(["override", *argv])


def _handle_planning_override(argv: list[str]) -> int:
    if not argv:
        return _megaplan_main(["override"])
    action = argv[0]
    catalog = _megaplan_override_catalog()
    if action in _umbrella_override_actions(catalog):
        print(
            f"arnold megaplan override: {action!r} is umbrella-scoped; "
            f"use 'arnold override {action}'",
            file=sys.stderr,
        )
        return 2
    if (
        not _megaplan_override_apply_advertised()
        or action not in _megaplan_scoped_override_actions(catalog)
    ):
        print(f"arnold megaplan override: unknown action {action!r}", file=sys.stderr)
        return 2
    return _megaplan_main(["override", *argv])


def _megaplan_override_catalog() -> dict[str, object]:
    try:
        supported = supported_operations_for("megaplan")
    except RuntimeError:
        supported = frozenset({OperationKind.OVERRIDE_LIST, OperationKind.OVERRIDE_APPLY})
    if OperationKind.OVERRIDE_LIST not in supported:
        return {}
    try:
        return override_catalog_for("megaplan")
    except RuntimeError:
        from arnold_pipelines.megaplan.planning.operations import override_catalog

        return override_catalog()


def _megaplan_override_apply_advertised() -> bool:
    try:
        return OperationKind.OVERRIDE_APPLY in supported_operations_for("megaplan")
    except RuntimeError:
        return True


def _catalog_actions_by_kind(
    catalog: dict[str, object],
    kinds: set[str],
) -> set[str]:
    actions: set[str] = set()
    for action, meta in catalog.items():
        if isinstance(action, str) and isinstance(meta, dict) and meta.get("kind") in kinds:
            actions.add(action)
    return actions


def _megaplan_scoped_override_actions(catalog: dict[str, object]) -> set[str]:
    return _catalog_actions_by_kind(catalog, {"transition", "recovery"})


def _umbrella_override_actions(catalog: dict[str, object]) -> set[str]:
    return _catalog_actions_by_kind(catalog, {"annotation", "termination", "config"})


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
    if verb == "override" and module == "megaplan":
        return _handle_planning_override(rest)
    if verb == "override":
        print(
            f"arnold {module}: override is only available for the megaplan module",
            file=sys.stderr,
        )
        return 2
    print(f"arnold {module}: unknown verb {verb!r}", file=sys.stderr)
    return 2


def _print_usage(*, file=None) -> None:  # type: ignore[no-untyped-def]
    target = file or sys.stdout
    print(
        "usage: arnold run ... | arnold pipelines {list,check,describe,doctor,new} | "
        "arnold <module> {run,check,doctor,describe,auto} | "
        "arnold megaplan override ... | arnold auto [megaplan] ... | "
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
