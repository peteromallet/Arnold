"""``vibecomfy schemas`` — object_info cache management and coverage validation."""

from __future__ import annotations

import argparse
import ast
import json as json_module
from pathlib import Path
from typing import Any

from vibecomfy.commands._output import emit
from vibecomfy.porting.object_info.consume import get_class, list_classes
from vibecomfy.porting.object_info.serialize import CACHE_DIR, refresh_from_source


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _extract_class_types_from_template(template_path: str | Path) -> list[str]:
    """Parse a narrative template and return every class type used in node calls.

    The ``_node`` helper signature is::

        _node(wf, class_type: str, _id: str, ...)
        _at(wf, _id: str, class_type: str, ...)
        raw_call(wf, class_type: str, _id: str, ...)

    We extract the second positional argument (a string literal).
    """
    source = Path(template_path).read_text(encoding="utf-8")
    tree = ast.parse(source)
    class_types: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func
        if isinstance(func, ast.Name) and func.id in {"_node", "node", "raw_call"}:
            class_arg_index = 0 if func.id == "raw_call" and node.args and isinstance(node.args[0], ast.Constant) else 1
        elif isinstance(func, ast.Name) and func.id == "_at":
            class_arg_index = 2
        elif isinstance(func, ast.Attribute):
            if func.attr == "_node":
                class_arg_index = 1
            elif func.attr == "_at":
                class_arg_index = 2
            else:
                continue
        else:
            continue

        if len(node.args) > class_arg_index:
            arg = node.args[class_arg_index]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                class_types.append(arg.value)

    return class_types


# ---------------------------------------------------------------------------
# subcommand: refresh
# ---------------------------------------------------------------------------


def _cmd_schemas_refresh(args: argparse.Namespace) -> int:
    """``schemas refresh --source <path>``"""
    if args.runtime is not None:
        raise NotImplementedError(
            f"--runtime {args.runtime} is not implemented yet. "
            "TODO: support --runtime embedded|server|runpod for live object_info fetching."
        )
    result = refresh_from_source(args.source)
    msg = (
        f"Cache refreshed: {result['classes_indexed']} classes "
        f"across {result['packs_written']} packs → {result['cache_dir']}"
    )
    return emit(result, json=args.json, text_renderer=lambda _: msg)


# ---------------------------------------------------------------------------
# subcommand: validate-coverage
# ---------------------------------------------------------------------------


def _cmd_schemas_validate_coverage(args: argparse.Namespace) -> int:
    """``schemas validate-coverage <template>``"""
    template_path = Path(args.template)
    if not template_path.is_file():
        print(f"Template not found: {template_path}", file=__import__("sys").stderr)
        return 1

    class_types = _extract_class_types_from_template(template_path)
    all_cached = set(list_classes())
    unique = sorted(set(class_types))
    covered: list[str] = []
    missing: list[str] = []

    for ct in unique:
        if get_class(ct) is not None:
            covered.append(ct)
        else:
            missing.append(ct)

    payload: dict[str, Any] = {
        "template": str(template_path),
        "classes_found": len(unique),
        "covered": len(covered),
        "missing": len(missing),
        "covered_classes": covered,
        "missing_classes": missing,
        "cache_classes_total": len(all_cached),
    }

    if not args.json:
        print(f"Template: {template_path}")
        print(f"Classes found: {len(unique)}  |  covered: {len(covered)}  |  missing: {len(missing)}")
        if covered:
            print(f"  Covered: {', '.join(covered)}")
        if missing:
            print(f"  Missing:  {', '.join(missing)}")
        print(f"Cache: {len(all_cached)} classes indexed")
        return 0

    return emit(payload, json=True, text_renderer=lambda _: None)


# ---------------------------------------------------------------------------
# subcommand: ensure
# ---------------------------------------------------------------------------


def _cmd_schemas_ensure(args: argparse.Namespace) -> int:
    """``schemas ensure <template>`` — ensure all class schemas are cached.

    Parses class types from the template, diffs against the object_info cache,
    maps missing classes to known node packs, and triggers pack extraction
    (clone + extract) for any needed packs.  No-op when all classes are already
    cached.
    """
    template_path = Path(args.template)
    if not template_path.is_file():
        payload: dict[str, Any] = {
            "template": str(template_path),
            "error": "Template not found",
        }
        if args.json:
            return emit(payload, json=True, text_renderer=lambda _: None)
        print(f"Template not found: {template_path}", file=__import__("sys").stderr)
        return 1

    class_types = _extract_class_types_from_template(template_path)
    all_cached = set(list_classes())
    unique = sorted(set(class_types))
    missing_classes = [ct for ct in unique if ct not in all_cached]
    covered = [ct for ct in unique if ct in all_cached]

    # --- No-op when all classes are cached ---
    if not missing_classes:
        payload = {
            "template": str(template_path),
            "classes_found": len(unique),
            "covered": len(covered),
            "missing": 0,
            "covered_classes": covered,
            "missing_classes": [],
            "cache_classes_total": len(all_cached),
            "packs_needed": [],
            "packs_extracted": [],
            "action": "noop",
        }
        if args.json:
            return emit(payload, json=True, text_renderer=lambda _: None)
        print(f"Template: {template_path}")
        print(f"Classes found: {len(unique)}  |  covered: {len(covered)}  |  missing: 0")
        print("All class schemas already cached — nothing to do.")
        return 0

    # --- Map missing classes to KNOWN_NODE_PACKS ---
    from vibecomfy.node_packs import resolve_node_packs

    packs_needed = resolve_node_packs(set(missing_classes))

    if not packs_needed:
        payload = {
            "template": str(template_path),
            "classes_found": len(unique),
            "covered": len(covered),
            "missing": len(missing_classes),
            "covered_classes": covered,
            "missing_classes": missing_classes,
            "cache_classes_total": len(all_cached),
            "packs_needed": [],
            "packs_extracted": [],
            "unresolved": missing_classes,
            "warning": (
                "Some missing classes could not be mapped to a known node pack. "
                "They may be built-in ComfyUI classes or from unregistered packs."
            ),
            "action": "partial",
        }
        if args.json:
            return emit(payload, json=True, text_renderer=lambda _: None)
        print(f"Template: {template_path}")
        print(f"Classes found: {len(unique)}  |  covered: {len(covered)}  |  missing: {len(missing_classes)}")
        print(f"Missing (unresolved): {', '.join(missing_classes)}")
        print("Warning: some missing classes could not be mapped to a known node pack.")
        return 1

    # --- Extract missing packs ---
    from tools.clone_and_extract_packs import (
        INDEX_PATH,
        load_index,
        process_pack,
    )

    index = load_index()
    original_index = dict(index)

    pack_names_needed = [p.name for p in packs_needed]
    reports = [process_pack(pack, index) for pack in packs_needed]

    # Write updated index if it changed
    if index != original_index:
        INDEX_PATH.write_text(
            json_module.dumps(dict(sorted(index.items())), indent=2) + "\n",
            encoding="utf-8",
        )

    packs_extracted = [
        {
            "name": r.name,
            "class_count": r.class_count,
            "method": r.method or "none",
            "cache_file": r.cache_file or "",
            "cloned": r.cloned,
            "sha7": r.sha7,
            "failures": r.failures,
            "warnings": r.warnings,
        }
        for r in reports
    ]

    payload: dict[str, Any] = {
        "template": str(template_path),
        "classes_found": len(unique),
        "covered": len(covered),
        "missing": len(missing_classes),
        "covered_classes": covered,
        "missing_classes": missing_classes,
        "cache_classes_total": len(all_cached),
        "packs_needed": pack_names_needed,
        "packs_extracted": packs_extracted,
        "action": "extracted",
    }

    if args.json:
        return emit(payload, json=True, text_renderer=lambda _: None)

    print(f"Template: {template_path}")
    print(f"Classes found: {len(unique)}  |  covered: {len(covered)}  |  missing: {len(missing_classes)}")
    print(f"Packs needed: {', '.join(pack_names_needed)}")
    for report in reports:
        print(f"  - {report.name}: {report.class_count} classes, method={report.method or 'none'}")
        if report.cache_file:
            print(f"    cache: {report.cache_file}")
        if report.warnings:
            for warning in report.warnings:
                print(f"    warning: {warning}")
        if report.failures:
            for failure in report.failures:
                print(f"    FAILURE: {failure}")

    return 0 if not any(r.failures and r.class_count == 0 for r in reports) else 1


# ---------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------


def register(subparsers) -> None:
    schemas = subparsers.add_parser("schemas", help="Object_info cache management")

    schemas_sub = schemas.add_subparsers(dest="schemas_subcmd", required=True)

    # --- schemas refresh --------------------------------------------------
    refresh = schemas_sub.add_parser("refresh", help="Regenerate cache from object_info dump")
    refresh.add_argument("--source", required=True, help="Path to object_info JSON dump")
    refresh.add_argument("--json", action="store_true", help="Output as JSON")
    # Stubs for future runtime modes
    refresh.add_argument(
        "--runtime",
        choices=["embedded", "server", "runpod"],
        default=None,
        help="Future: fetch object_info from a live runtime (not implemented)",
    )
    refresh.set_defaults(func=_cmd_schemas_refresh)

    # --- schemas validate-coverage ----------------------------------------
    validate = schemas_sub.add_parser(
        "validate-coverage", help="Check which classes in a template have cache entries"
    )
    validate.add_argument("template", help="Path to narrative template (.py)")
    validate.add_argument("--json", action="store_true", help="Output as JSON")
    validate.set_defaults(func=_cmd_schemas_validate_coverage)

    # --- schemas ensure ---------------------------------------------------
    ensure = schemas_sub.add_parser(
        "ensure", help="Ensure all class schemas in a template are cached"
    )
    ensure.add_argument("template", help="Path to narrative template (.py)")
    ensure.add_argument("--json", action="store_true", help="Output as JSON")
    ensure.set_defaults(func=_cmd_schemas_ensure)
