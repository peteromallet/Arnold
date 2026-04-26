from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from vibecomfy.commands.index_files import IndexReadError, print_index_error, read_index_json
from vibecomfy.registry import load_workflow_reference
from vibecomfy.schema import SchemaIndexError, get_schema_provider
from vibecomfy.node_packs import resolve_node_packs, unresolved_class_types


def _cmd_nodes_list(args: argparse.Namespace) -> int:
    path = Path("node_index.json")
    if not path.exists():
        print("node_index.json not found; run `vibecomfy sources sync`")
        return 1
    try:
        rows = read_index_json(path, default=[])
    except IndexReadError as exc:
        print_index_error(exc)
        return 1
    for row in rows[: args.limit]:
        print(row)
    return 0


def _cmd_nodes_spec(args: argparse.Namespace) -> int:
    provider = get_schema_provider("auto")
    try:
        schema = provider.get_schema(args.class_type)
    except SchemaIndexError as exc:
        print(f"{exc}; run `vibecomfy sources sync` to rebuild indexes.")
        return 1
    if schema is None:
        print(f"node schema not found for {args.class_type!r}; run `vibecomfy sources sync` or start a runtime with /object_info")
        return 1
    print(json.dumps(asdict(schema), indent=2, sort_keys=True))
    return 0


def _cmd_nodes_install_plan(args: argparse.Namespace) -> int:
    schema_provider = get_schema_provider("auto")
    workflow = load_workflow_reference(args.path, schema_provider=schema_provider, allow_scratchpad=True)
    class_types = {node.class_type for node in workflow.nodes.values()}
    known_classes = _known_schema_classes()
    missing_classes = class_types - known_classes
    packs = resolve_node_packs(missing_classes)
    unresolved = unresolved_class_types(missing_classes)
    if args.json:
        print(
            json.dumps(
                {
                    "path": args.path,
                    "packs": [
                        {
                            "name": pack.name,
                            "repo": pack.repo,
                            "pip_packages": list(pack.pip_packages),
                            "classes": sorted(missing_classes & pack.classes),
                        }
                        for pack in packs
                    ],
                    "unresolved_class_types": unresolved,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1 if unresolved else 0
    if not missing_classes:
        print("No missing custom node classes detected from local node_index.json.")
        return 0
    if packs:
        print("Suggested custom node packs:")
        for pack in packs:
            classes = ", ".join(sorted(missing_classes & pack.classes))
            packages = f" (pip: {', '.join(pack.pip_packages)})" if pack.pip_packages else ""
            print(f"- {pack.name}: {pack.repo}{packages}")
            print(f"  classes: {classes}")
    if unresolved:
        print("Unmapped node classes:")
        for class_type in unresolved:
            print(f"- {class_type}")
        return 1
    return 0


def _known_schema_classes() -> set[str]:
    path = Path("node_index.json")
    if not path.exists():
        return set()
    try:
        rows = read_index_json(path, default=[])
    except IndexReadError:
        return set()
    return {str(row.get("class_type")) for row in rows if isinstance(row, dict) and row.get("class_type")}


def register(subparsers) -> None:
    nodes = subparsers.add_parser("nodes")
    nodes_sub = nodes.add_subparsers(dest="subcmd", required=True)
    nodes_list = nodes_sub.add_parser("list")
    nodes_list.add_argument("--limit", type=int, default=200)
    nodes_list.set_defaults(func=_cmd_nodes_list)
    nodes_spec = nodes_sub.add_parser("spec")
    nodes_spec.add_argument("class_type")
    nodes_spec.set_defaults(func=_cmd_nodes_spec)
    nodes_install = nodes_sub.add_parser("install-plan")
    nodes_install.add_argument("path")
    nodes_install.add_argument("--json", action="store_true")
    nodes_install.set_defaults(func=_cmd_nodes_install_plan)
