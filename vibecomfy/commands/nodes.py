from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path
import subprocess
import sys

from vibecomfy.analysis.corpus import build_corpus_snapshot
from vibecomfy.analysis.node_coverage import build_workflow_coverage
from vibecomfy.commands._output import emit
from vibecomfy.commands._index_files import IndexReadError, print_index_error, read_index_json
from vibecomfy.porting.workbench import load_port_source
from vibecomfy.registry import load_workflow_reference
from vibecomfy.registry.pack_resolver import PackResolverError, resolve_pack
from vibecomfy.schema import ObjectInfoSchemaProvider, SchemaIndexError, SourceSchemaProvider, get_schema_provider
from vibecomfy.schema.cache import object_info_cache_candidates
import vibecomfy.node_packs_install as node_packs_install
from vibecomfy.node_packs_lockfile import LockEntry, read_lockfile, write_lockfile


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
    return emit(rows[: args.limit], json=args.json, text_renderer=lambda selected: "\n".join(str(row) for row in selected))


def _cmd_nodes_spec(args: argparse.Namespace) -> int:
    if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", args.class_type, re.I):
        return _cmd_nodes_spec_subgraph(args)
    provider = ObjectInfoSchemaProvider(args.object_info_cache) if args.object_info_cache else get_schema_provider("auto")
    try:
        schema = provider.get_schema(args.class_type)
    except SchemaIndexError as exc:
        print(f"{exc}; run `vibecomfy sources sync` to rebuild indexes.")
        return 1
    if schema is None:
        schema = SourceSchemaProvider().get_schema(args.class_type)
    if schema is None and not args.object_info_cache:
        for cache_path in object_info_cache_candidates():
            try:
                schema = ObjectInfoSchemaProvider(cache_path).get_schema(args.class_type)
            except SchemaIndexError:
                continue
            if schema is not None:
                break
    if schema is None:
        print(
            f"node schema not found for {args.class_type!r}; run `vibecomfy sources sync`, "
            "start a runtime with /object_info, or install the custom node source locally"
        )
        return 1
    print(json.dumps(asdict(schema), indent=2, sort_keys=True))
    return 0


def _cmd_nodes_spec_subgraph(args: argparse.Namespace) -> int:
    candidates: list[Path] = []
    source = getattr(args, "source", None)
    if source:
        candidates.append(Path(source))
    else:
        candidates.extend(Path("workflow_corpus").rglob("*.json"))
    for path in candidates:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        definitions = raw.get("definitions") if isinstance(raw, dict) else None
        subgraphs = definitions.get("subgraphs") if isinstance(definitions, dict) else None
        if isinstance(subgraphs, dict):
            iterable = subgraphs.values()
        elif isinstance(subgraphs, list):
            iterable = subgraphs
        else:
            iterable = ()
        for subgraph in iterable:
            if not isinstance(subgraph, dict) or str(subgraph.get("id")) != args.class_type:
                continue
            class_counts: dict[str, int] = {}
            for node in subgraph.get("nodes") or ():
                if isinstance(node, dict):
                    class_type = str(node.get("type") or node.get("class_type") or "Unknown")
                    class_counts[class_type] = class_counts.get(class_type, 0) + 1
            payload = {
                "uuid": args.class_type,
                "name": subgraph.get("name"),
                "inputs": subgraph.get("inputs") or [],
                "outputs": subgraph.get("outputs") or [],
                "inner_node_count": len(subgraph.get("nodes") or []),
                "inner_node_class_types": dict(sorted(class_counts.items())),
                "inner_graph": {"edges": subgraph.get("links") or []},
                "source": str(path),
            }
            return emit(payload, json=getattr(args, "json", False), text_renderer=lambda data: data["name"] or data["uuid"])
    print(f"subgraph UUID not found: {args.class_type}", file=sys.stderr)
    return 1


def _cmd_nodes_install_plan(args: argparse.Namespace) -> int:
    schema_provider = get_schema_provider("auto")
    workflow = load_workflow_reference(args.path, schema_provider=schema_provider, allow_scratchpad=True)
    try:
        missing_classes = node_packs_install.missing_class_types_for_workflow(workflow)
        packs, unresolved = node_packs_install.missing_packs_for_workflow(workflow)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return _print_install_plan(args.path, missing_classes, packs, unresolved, json_output=args.json)


def _print_install_plan(path: str, missing_classes, packs, unresolved, *, json_output: bool) -> int:
    if json_output:
        print(
            json.dumps(
                {
                    "path": path,
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


def _cmd_nodes_install(args: argparse.Namespace) -> int:
    try:
        result = node_packs_install.install_pack(name=args.name, repo=args.repo, force=args.force)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    detail = f" {result.git_commit_sha}" if result.git_commit_sha else ""
    print(f"{result.name}: {result.status}{detail}")
    if result.error:
        print(result.error, file=sys.stderr)
    return 0 if result.status in {"installed", "refreshed"} else 1


def _cmd_nodes_lookup(args: argparse.Namespace) -> int:
    try:
        resolution = resolve_pack(args.query)
    except PackResolverError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    payload = {
        "query": resolution.query,
        "query_type": resolution.query_type,
        "pack": resolution.ref.to_dict(),
        "candidates": [candidate.to_dict() for candidate in resolution.candidates],
        "cache_hit": resolution.cache_hit,
        "endpoint": resolution.endpoint,
    }
    return emit(payload, json=args.json, text_renderer=lambda data: data["pack"]["slug"])


def _cmd_nodes_refresh_template(args: argparse.Namespace) -> int:
    path = Path(args.file)
    original = path.read_text(encoding="utf-8")
    workflow = load_workflow_reference(str(path), allow_scratchpad=True)
    classes = {str(node.class_type) for node in workflow.nodes.values()}
    refs = []
    for entry in read_lockfile():
        class_set = set(getattr(entry, "class_set", ()) or ())
        if classes & class_set:
            refs.append(entry)
    slugs = sorted({getattr(entry, "slug", None) or entry.name for entry in refs})
    replacement = original
    if "custom_node_refs=" not in replacement:
        marker = "    output_prefix="
        insert = f"    custom_node_refs={slugs!r},\n"
        lines = replacement.splitlines(keepends=True)
        for index, line in enumerate(lines):
            if line.startswith(marker):
                lines.insert(index + 1, insert)
                replacement = "".join(lines)
                break
    diff = "".join(difflib.unified_diff(original.splitlines(True), replacement.splitlines(True), fromfile=str(path), tofile=str(path)))
    status = "dry-run" if args.dry_run else "updated"
    if not args.dry_run:
        path.write_text(replacement, encoding="utf-8")
    payload = {"status": status, "custom_nodes": slugs, "diff": diff if args.diff else ""}
    return emit(payload, json=args.json, text_renderer=lambda data: data["status"])


def _cmd_nodes_ensure(args: argparse.Namespace) -> int:
    path = args.template or args.workflow
    schema_provider = get_schema_provider("auto")
    workflow = load_workflow_reference(path, schema_provider=schema_provider, allow_scratchpad=True)
    try:
        missing_classes = node_packs_install.missing_class_types_for_workflow(workflow)
        packs, unresolved = node_packs_install.missing_packs_for_workflow(workflow)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.dry_run:
        return _print_install_plan(path, missing_classes, packs, unresolved, json_output=False)
    if not missing_classes:
        print("No missing custom node classes detected from local node_index.json.")
        return 0
    if unresolved:
        print("Unmapped node classes:")
        for class_type in unresolved:
            print(f"- {class_type}")
        return 1
    for pack in packs:
        result = node_packs_install.install_pack(name=pack.name)
        detail = f" {result.git_commit_sha}" if result.git_commit_sha else ""
        print(f"{result.name}: {result.status}{detail}")
        if result.error:
            print(result.error, file=sys.stderr)
        if result.status not in {"installed", "refreshed"}:
            return 1
    print(
        "Nodepacks installed/refreshed. If a vibecomfy session is active, "
        "call session.reload_for_nodepack_change(...) or restart it."
    )
    return 0


def _cmd_nodes_lock(args: argparse.Namespace) -> int:
    lockfile_path = Path(getattr(args, "path", "custom_nodes.lock"))
    entries = read_lockfile(lockfile_path)
    locked: list[LockEntry] = []
    for entry in entries:
        pack_dir = _installed_nodepack_dir(entry.name)
        git_commit_sha = entry.git_commit_sha
        if entry.semantic_label and pack_dir is not None:
            git_commit_sha = _git_head(pack_dir) or git_commit_sha
        source_sha256 = dict(entry.source_sha256)
        if getattr(args, "with_source_sha256", False) and pack_dir is not None:
            source_sha256 = _source_sha256(pack_dir)
        locked.append(
            LockEntry(
                name=entry.name,
                git_commit_sha=git_commit_sha,
                url=entry.url,
                semantic_label=entry.semantic_label,
                source_sha256=source_sha256,
            )
        )
    write_lockfile(locked, lockfile_path)
    print(f"Wrote {lockfile_path} ({len(locked)} nodepacks)")
    return 0


def _cmd_nodes_restore(args: argparse.Namespace) -> int:
    entries = read_lockfile(Path(args.lockfile))
    ok = True
    for entry in entries:
        result = node_packs_install.restore_pack(entry)
        detail = f" {result.git_commit_sha}" if result.git_commit_sha else ""
        print(f"{result.name}: {result.status}{detail}")
        if result.error:
            print(result.error, file=sys.stderr)
        ok = ok and result.status in {"installed", "refreshed"}
    return 0 if ok else 1


def _installed_nodepack_dir(name: str) -> Path | None:
    candidate = node_packs_install.DEFAULT_INSTALL_ROOT / name
    return candidate if candidate.is_dir() else None


def _git_head(pack_dir: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(pack_dir), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _source_sha256(pack_dir: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for source in sorted(pack_dir.rglob("*.py")):
        if ".git" in source.parts:
            continue
        rel = source.relative_to(pack_dir).as_posix()
        hashes[rel] = hashlib.sha256(source.read_bytes()).hexdigest()
    return hashes


def _cmd_nodes_coverage(args: argparse.Namespace) -> int:
    """Schema completeness report for a workflow's class types."""
    schema_provider = get_schema_provider("auto")
    try:
        loaded = load_port_source(args.workflow, schema_provider=schema_provider)
    except Exception as exc:
        print(f"Failed to load workflow: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    lock_path = Path(args.lockfile) if getattr(args, "lockfile", None) else Path("custom_nodes.lock")
    coverage = build_workflow_coverage(
        loaded.workflow,
        schema_provider=schema_provider,
        lock_path=lock_path,
    )
    if args.json:
        print(json.dumps(coverage.to_json(), indent=2, sort_keys=True))
    else:
        print(_format_coverage(coverage))
    return 0


def _format_coverage(coverage) -> str:
    lines = []
    for entry in coverage.per_class:
        icon = {"typed_wrapper": "✅ typed wrapper", "raw_call": "⚡ raw_call", "missing_lock": "❌ missing_lock"}.get(
            entry["coverage"], f"? {entry['coverage']}"
        )
        lines.append(f"{entry['class_type']:40s} {entry['pack']:30s} {icon}")
    lines.append("")
    lines.append(f"Coverage: {coverage.typed_wrapper}/{coverage.total} ({coverage.to_json()['coverage_pct']}%)")
    lines.append(f"Falls through to raw_call: {coverage.raw_call}")
    lines.append(f"Missing from custom_nodes.lock: {coverage.missing_lock}")
    return "\n".join(lines)


def _cmd_nodes_drift(args: argparse.Namespace) -> int:
    """Schema-drift detector for a custom-node pack."""
    pack_name: str = args.pack
    from_ref: str | None = getattr(args, "from_ref", None)
    to_ref: str | None = getattr(args, "to_ref", None)

    # Resolve pack dir
    pack_dir = node_packs_install.DEFAULT_INSTALL_ROOT / pack_name
    if not pack_dir.is_dir():
        payload = {
            "status": "unavailable",
            "pack": pack_name,
            "message": f"Pack directory not found: {pack_dir}. Install the pack first with `vibecomfy nodes install {pack_name}`.",
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"Pack unavailable: {pack_name}")
            print(f"  Directory not found: {pack_dir}")
            print(f"  Install with: vibecomfy nodes install {pack_name}")
        return 0

    # Check git
    if not (pack_dir / ".git").is_dir():
        payload = {
            "status": "unavailable",
            "pack": pack_name,
            "message": f"Pack directory {pack_dir} is not a git repository.",
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"Pack unavailable: {pack_name}")
            print(f"  {pack_dir} is not a git repository")
        return 0

    # Resolve refs
    if from_ref is None:
        from_ref = "HEAD~1"
    if to_ref is None:
        to_ref = "HEAD"

    # Get schema snapshots
    from_python = _extract_pack_python_api(pack_dir, from_ref)
    to_python = _extract_pack_python_api(pack_dir, to_ref)

    if from_python is None or to_python is None:
        payload = {
            "status": "unavailable",
            "pack": pack_name,
            "from_ref": from_ref,
            "to_ref": to_ref,
            "message": "Could not extract Python API from one or both refs.",
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"Schema diff unavailable for {pack_name}: {from_ref}..{to_ref}")
        return 0

    # Diff classes
    from_classes = _parse_class_defs(from_python)
    to_classes = _parse_class_defs(to_python)

    added = set(to_classes) - set(from_classes)
    removed = set(from_classes) - set(to_classes)
    modified: list[dict[str, Any]] = []

    for cls_name in set(from_classes) & set(to_classes):
        if from_classes[cls_name] != to_classes[cls_name]:
            modified.append({
                "class": cls_name,
                "from_inputs": from_classes[cls_name],
                "to_inputs": to_classes[cls_name],
            })

    # Find affected templates
    affected_templates: list[str] = []
    all_modified_classes = {m["class"] for m in modified} | added | removed
    if all_modified_classes:
        try:
            snapshot = build_corpus_snapshot()
            for tpl in snapshot.templates_list:
                tpl_path = Path(tpl["path"])
                if tpl_path.is_file():
                    source = tpl_path.read_text(encoding="utf-8")
                    for ct in all_modified_classes:
                        if f"'{ct}'" in source or f'"{ct}"' in source:
                            affected_templates.append(tpl["id"])
                            break
        except Exception:
            pass

    payload = {
        "pack": pack_name,
        "from_ref": from_ref,
        "to_ref": to_ref,
        "added_classes": sorted(added),
        "removed_classes": sorted(removed),
        "modified_classes": modified,
        "affected_templates": sorted(set(affected_templates)),
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Schema diff: {pack_name} {from_ref}..{to_ref}")
        print(f"Added classes: {sorted(added) if added else '(none)'}")
        print(f"Removed classes: {sorted(removed) if removed else '(none)'}")
        if modified:
            print("Modified classes:")
            for m in modified:
                print(f"  {m['class']}: inputs changed")
        else:
            print("Modified classes: (none)")
        if affected_templates:
            print(f"\nAffected templates (use modified classes):")
            for tid in sorted(set(affected_templates)):
                print(f"  {tid}")
        else:
            print("\nAffected templates: (none)")
    return 0


def _extract_pack_python_api(pack_dir: Path, ref: str) -> str | None:
    """Extract combined Python source from all .py files at a git ref."""
    try:
        result = subprocess.run(
            ["git", "-C", str(pack_dir), "ls-tree", "-r", "--name-only", ref],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    py_files = [f for f in result.stdout.strip().split("\n") if f.endswith(".py")]
    if not py_files:
        return None

    combined: list[str] = []
    for py_file in py_files[:50]:  # limit to prevent huge output
        try:
            r = subprocess.run(
                ["git", "-C", str(pack_dir), "show", f"{ref}:{py_file}"],
                check=True,
                capture_output=True,
                text=True,
            )
            combined.append(r.stdout)
        except (OSError, subprocess.CalledProcessError):
            continue

    return "\n".join(combined) if combined else None


def _parse_class_defs(source: str) -> dict[str, dict[str, Any]]:
    """Parse INPUT_TYPES-like class definitions from Python source."""
    classes: dict[str, dict[str, Any]] = {}
    # Find class definitions and their INPUT_TYPES
    class_pattern = re.compile(r"class\s+(\w+)\s*[:\(]")
    inputs_pattern = re.compile(r"INPUT_TYPES\s*\(\s*\)\s*:\s*\n?\s*return\s*\{[^}]*\}")

    for cls_match in class_pattern.finditer(source):
        cls_name = cls_match.group(1)
        # Try to find INPUT_TYPES after the class
        rest = source[cls_match.end():]
        next_class = class_pattern.search(rest)
        section = rest[:next_class.start()] if next_class else rest

        # Extract required inputs
        required = re.findall(r'"required"\s*:\s*\{([^}]*)\}', section, re.DOTALL)
        if required:
            classes[cls_name] = {"has_required_inputs": True}
        else:
            classes[cls_name] = {"has_required_inputs": False}

    return classes


def register(subparsers) -> None:
    nodes = subparsers.add_parser("nodes")
    nodes_sub = nodes.add_subparsers(dest="subcmd", required=True)
    nodes_list = nodes_sub.add_parser("list")
    nodes_list.add_argument("--limit", type=int, default=200)
    nodes_list.add_argument("--json", action="store_true")
    nodes_list.set_defaults(func=_cmd_nodes_list)
    nodes_spec = nodes_sub.add_parser("spec")
    nodes_spec.add_argument("class_type")
    nodes_spec.add_argument(
        "--object-info-cache",
        help="Use a captured ComfyUI /object_info JSON file, for example one fetched from a RunPod runtime.",
    )
    nodes_spec.set_defaults(func=_cmd_nodes_spec)
    nodes_install = nodes_sub.add_parser("install-plan")
    nodes_install.add_argument("path")
    nodes_install.add_argument("--json", action="store_true")
    nodes_install.set_defaults(func=_cmd_nodes_install_plan)
    nodes_install_pack = nodes_sub.add_parser("install")
    nodes_install_pack.add_argument("name", nargs="?")
    nodes_install_pack.add_argument("--repo")
    nodes_install_pack.add_argument("--force", action="store_true", default=False)
    nodes_install_pack.set_defaults(func=_cmd_nodes_install)
    nodes_lookup = nodes_sub.add_parser("lookup")
    nodes_lookup.add_argument("query")
    nodes_lookup.add_argument("--json", action="store_true")
    nodes_lookup.set_defaults(func=_cmd_nodes_lookup)
    nodes_refresh = nodes_sub.add_parser("refresh-template")
    nodes_refresh.add_argument("file")
    nodes_refresh.add_argument("--dry-run", action="store_true")
    nodes_refresh.add_argument("--diff", action="store_true")
    nodes_refresh.add_argument("--json", action="store_true")
    nodes_refresh.set_defaults(func=_cmd_nodes_refresh_template)
    nodes_ensure = nodes_sub.add_parser("ensure")
    ensure_source = nodes_ensure.add_mutually_exclusive_group(required=True)
    ensure_source.add_argument("--template")
    ensure_source.add_argument("--workflow")
    nodes_ensure.add_argument("--dry-run", action="store_true")
    nodes_ensure.set_defaults(func=_cmd_nodes_ensure)
    nodes_lock = nodes_sub.add_parser("lock")
    nodes_lock.add_argument("--path", default="custom_nodes.lock")
    nodes_lock.add_argument("--with-source-sha256", action="store_true", default=False)
    nodes_lock.set_defaults(func=_cmd_nodes_lock)
    nodes_restore = nodes_sub.add_parser("restore")
    nodes_restore.add_argument("--lockfile", default="custom_nodes.lock")
    nodes_restore.set_defaults(func=_cmd_nodes_restore)

    nodes_coverage = nodes_sub.add_parser("coverage", help="Schema completeness report for a workflow's class types.")
    nodes_coverage.add_argument("workflow")
    nodes_coverage.add_argument("--json", action="store_true")
    nodes_coverage.add_argument("--lockfile", default="custom_nodes.lock", help="Path to custom_nodes.lock")
    nodes_coverage.set_defaults(func=_cmd_nodes_coverage)

    nodes_drift = nodes_sub.add_parser("drift", help="Schema-drift detector for a custom-node pack.")
    nodes_drift.add_argument("pack", help="Custom node pack name (e.g. ComfyUI-KJNodes)")
    nodes_drift.add_argument("--from", dest="from_ref", help="Source git ref (default: HEAD~1)")
    nodes_drift.add_argument("--to", dest="to_ref", help="Target git ref (default: HEAD)")
    nodes_drift.add_argument("--json", action="store_true")
    nodes_drift.set_defaults(func=_cmd_nodes_drift)
