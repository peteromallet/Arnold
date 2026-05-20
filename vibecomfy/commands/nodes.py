from __future__ import annotations

import argparse
from collections import Counter
import difflib
import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path
import subprocess
import sys
from typing import Any

from vibecomfy.commands._output import emit
from vibecomfy.commands._index_files import IndexReadError, print_index_error, read_index_json
from vibecomfy.custom_node_refs import lock_entry_to_ref
from vibecomfy.registry import load_workflow_reference
from vibecomfy.registry.pack_resolver import AmbiguousPackError, PackNotFoundError, lookup_class_candidates, resolve_pack
from vibecomfy.schema import ObjectInfoSchemaProvider, SchemaIndexError, SourceSchemaProvider, get_schema_provider
from vibecomfy.schema.cache import object_info_cache_candidates
import vibecomfy.node_packs_install as node_packs_install
from vibecomfy.node_packs_lockfile import LockEntry, compute_schema_hash, read_lockfile, write_lockfile


UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


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
    if UUID_RE.match(args.class_type):
        return _cmd_nodes_subgraph_spec(args)
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


def _cmd_nodes_subgraph_spec(args: argparse.Namespace) -> int:
    try:
        path, subgraph = _find_subgraph_definition(args.class_type, getattr(args, "source", None))
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    payload = _summarize_subgraph(args.class_type, path, subgraph, verbose=getattr(args, "verbose", False))
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_render_subgraph_spec(payload, verbose=getattr(args, "verbose", False)))
    return 0


def _find_subgraph_definition(uuid: str, source: str | None) -> tuple[Path, dict[str, Any]]:
    paths = [Path(source)] if source else sorted(Path("workflow_corpus").glob("**/*.json"))
    for path in paths:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise FileNotFoundError(f"workflow JSON not found: {path}") from None
        except json.JSONDecodeError:
            continue
        if not isinstance(raw, dict):
            continue
        subgraph = _subgraph_by_uuid(raw, uuid)
        if subgraph is not None:
            return path, subgraph
    scope = f" in {source}" if source else " under workflow_corpus/**/*.json"
    raise ValueError(f"subgraph UUID not found{scope}: {uuid}")


def _subgraph_by_uuid(raw: dict[str, Any], uuid: str) -> dict[str, Any] | None:
    definitions = raw.get("definitions", {})
    if not isinstance(definitions, dict):
        return None
    subgraphs = definitions.get("subgraphs", [])
    if isinstance(subgraphs, dict):
        iterable = subgraphs.values()
    elif isinstance(subgraphs, list):
        iterable = subgraphs
    else:
        return None
    for subgraph in iterable:
        if isinstance(subgraph, dict) and subgraph.get("id") == uuid:
            return subgraph
    return None


def _summarize_subgraph(uuid: str, path: Path, subgraph: dict[str, Any], *, verbose: bool) -> dict[str, Any]:
    nodes = [node for node in subgraph.get("nodes", []) if isinstance(node, dict)]
    class_counts: Counter[str] = Counter()
    for node in nodes:
        class_type = node.get("type") or node.get("class_type")
        if class_type:
            class_counts[str(class_type)] += 1
    payload: dict[str, Any] = {
        "uuid": uuid,
        "source": str(path),
        "name": subgraph.get("name"),
        "inputs": [_port_item(item) for item in subgraph.get("inputs", []) if isinstance(item, dict)],
        "outputs": [_port_item(item) for item in subgraph.get("outputs", []) if isinstance(item, dict)],
        "inner_node_count": len(nodes),
        "inner_node_class_types": dict(sorted(class_counts.items())),
    }
    if verbose:
        payload["inner_graph"] = {
            "nodes": nodes,
            "edges": subgraph.get("links", []) if isinstance(subgraph.get("links", []), list) else [],
        }
    return payload


def _port_item(item: dict[str, Any]) -> dict[str, Any]:
    return {"name": item.get("name"), "type": item.get("type")}


def _render_subgraph_spec(payload: dict[str, Any], *, verbose: bool) -> str:
    lines = [
        f"Subgraph {payload['uuid']}",
        f"source: {payload['source']}",
        f"name: {payload.get('name') or '<unnamed>'}",
        f"inputs: {_render_ports(payload.get('inputs', []))}",
        f"outputs: {_render_ports(payload.get('outputs', []))}",
        f"inner nodes: {payload['inner_node_count']}",
        "inner node class types:",
    ]
    class_types = payload.get("inner_node_class_types") or {}
    if isinstance(class_types, dict) and class_types:
        lines.extend(f"- {name}: {count}" for name, count in class_types.items())
    else:
        lines.append("- <none>")
    if verbose:
        inner_graph = payload.get("inner_graph") if isinstance(payload.get("inner_graph"), dict) else {}
        lines.append("inner graph:")
        lines.append(json.dumps(inner_graph, indent=2, sort_keys=True))
    return "\n".join(lines)


def _render_ports(items: object) -> str:
    if not isinstance(items, list) or not items:
        return "<none>"
    return ", ".join(f"{item.get('name')}:{item.get('type')}" for item in items if isinstance(item, dict))


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
    query = args.query
    try:
        resolution = resolve_pack(query)
        candidates = list(resolution.candidates) or [resolution.ref]
        payload = {
            "query": query,
            "status": "resolved",
            "pack": resolution.ref.to_dict(),
            "candidates": [candidate.to_dict() for candidate in candidates],
        }
        return emit(payload, json=args.json, text_renderer=_render_lookup_result)
    except AmbiguousPackError as exc:
        payload = {
            "query": query,
            "status": "ambiguous",
            "candidates": [candidate.to_dict() for candidate in exc.candidates],
        }
        emit(payload, json=args.json, text_renderer=_render_lookup_result)
        return 2
    except PackNotFoundError:
        candidates = lookup_class_candidates(query)
        payload = {
            "query": query,
            "status": "unresolved" if not candidates else "candidates",
            "candidates": [candidate.to_dict() for candidate in candidates],
        }
        emit(payload, json=args.json, text_renderer=_render_lookup_result)
        return 1 if not candidates else 0


def _render_lookup_result(payload: dict[str, object]) -> str:
    status = payload.get("status")
    candidates = payload.get("candidates") or []
    if status == "resolved":
        pack = payload.get("pack")
        slug = pack.get("slug") if isinstance(pack, dict) else "<unknown>"
        source = pack.get("source") if isinstance(pack, dict) else "<unknown>"
        return f"{payload['query']}: {slug} ({source})"
    if status == "ambiguous":
        lines = [f"ambiguous lookup for {payload['query']}:"]
    elif status == "candidates":
        lines = [f"candidate packs for {payload['query']}:"]
    else:
        return (
            f"unknown class: {payload['query']}. "
            f"Run 'nodes lookup {payload['query']}' to find the providing pack, then 'nodes install <slug>'."
        )
    for candidate in candidates:
        if isinstance(candidate, dict):
            lines.append(f"- {candidate.get('slug')} ({candidate.get('source')})")
    return "\n".join(lines)


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
        class_schema_sha256 = _compute_class_schema_sha256(entry.name)
        locked.append(
            LockEntry(
                name=entry.name,
                git_commit_sha=git_commit_sha,
                url=entry.url,
                slug=entry.slug,
                source=entry.source,
                version=entry.version,
                commit=git_commit_sha,
                path=entry.path,
                schema_hash=class_schema_sha256 or entry.schema_hash,
                class_set=entry.class_set,
                last_seen_at=entry.last_seen_at,
                pip_packages=entry.pip_packages,
                semantic_label=entry.semantic_label,
                source_sha256=source_sha256,
                class_schema_sha256=class_schema_sha256,
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


def _cmd_nodes_refresh_template(args: argparse.Namespace) -> int:
    result = _refresh_template(Path(args.file), dry_run=args.dry_run, show_diff=args.diff)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        _print_refresh_result(result)
    return 0 if result["status"] in {"updated", "unchanged", "dry-run"} else 1


def _cmd_nodes_refresh_corpus(args: argparse.Namespace) -> int:
    paths = sorted(Path("ready_templates").glob("**/*.py"))
    results = [_refresh_template(path, dry_run=True if args.dry_run else False, show_diff=args.diff) for path in paths]
    payload = {"templates": results, "updated": sum(1 for item in results if item["status"] == "updated")}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for item in results:
            _print_refresh_result(item)
    return 1 if any(item["status"] == "error" for item in results) else 0


def _refresh_template(path: Path, *, dry_run: bool, show_diff: bool) -> dict[str, object]:
    entries = read_lockfile()
    try:
        workflow = load_workflow_reference(str(path), schema_provider=get_schema_provider("auto"), allow_scratchpad=True)
    except Exception as exc:
        return {"path": str(path), "status": "error", "error": f"{type(exc).__name__}: {exc}"}
    validation = workflow.validate(schema_provider=get_schema_provider("auto"))
    if not validation.ok:
        return {"path": str(path), "status": "error", "error": "local validation failed"}
    refs, unresolved = _pack_refs_for_workflow(workflow.runtime_class_types(), entries)
    if unresolved:
        return {"path": str(path), "status": "error", "error": "unresolved custom node classes", "unresolved": unresolved}
    original = path.read_text(encoding="utf-8")
    updated = _replace_requirements_block(original, refs)
    diff = "".join(difflib.unified_diff(original.splitlines(True), updated.splitlines(True), fromfile=str(path), tofile=str(path)))
    status = "unchanged" if original == updated else ("dry-run" if dry_run else "updated")
    if status == "updated":
        path.write_text(updated, encoding="utf-8")
    result: dict[str, object] = {
        "path": str(path),
        "status": status,
        "custom_nodes": sorted(ref["slug"] for ref in refs if isinstance(ref.get("slug"), str)),
        "custom_node_refs": refs,
    }
    if show_diff and diff:
        result["diff"] = diff
    return result


def _pack_refs_for_workflow(class_types: set[str], entries: list[LockEntry]) -> tuple[list[dict[str, object]], list[str]]:
    refs_by_slug: dict[str, dict[str, object]] = {}
    unresolved: list[str] = []
    for class_type in sorted(class_types):
        matched = [entry for entry in entries if class_type in set(entry.class_set)]
        if not matched:
            continue
        if len(matched) > 1:
            unresolved.append(class_type)
            continue
        ref = lock_entry_to_ref(matched[0])
        refs_by_slug[str(ref["slug"])] = ref
    return [refs_by_slug[key] for key in sorted(refs_by_slug)], unresolved


def _replace_requirements_block(source: str, refs: list[dict[str, object]]) -> str:
    custom_nodes = sorted(ref["slug"] for ref in refs if isinstance(ref.get("slug"), str))
    block = json.dumps({"custom_nodes": custom_nodes, "custom_node_refs": refs}, indent=8, sort_keys=True)
    indented = "\n".join((" " * 8 + line if index else line) for index, line in enumerate(block.splitlines()))
    replacement = f"requirements={indented},"
    if "requirements=" not in source:
        marker = "READY_METADATA = ReadyMetadata.build("
        start = source.find(marker)
        if start == -1:
            return source
        insert_at = source.find("\n)", start)
        if insert_at == -1:
            return source
        return source[:insert_at] + f"\n    {replacement}" + source[insert_at:]
    start = source.find("requirements=")
    value_start = start + len("requirements=")
    end = _find_requirement_value_end(source, value_start)
    if end is None:
        return source
    return source[:start] + replacement + source[end:]


def _find_requirement_value_end(source: str, value_start: int) -> int | None:
    depth = 0
    in_string: str | None = None
    escape = False
    for index in range(value_start, len(source)):
        char = source[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == in_string:
                in_string = None
            continue
        if char in {'"', "'"}:
            in_string = char
            continue
        if char in "([{":
            depth += 1
            continue
        if char in ")]}":
            if depth == 0:
                return index
            depth -= 1
            continue
        if char == "," and depth == 0:
            return index + 1
    return None


def _print_refresh_result(result: dict[str, object]) -> None:
    print(f"{result['path']}: {result['status']}")
    if result.get("error"):
        print(f"  {result['error']}")
    if result.get("diff"):
        print(result["diff"])


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


def _compute_class_schema_sha256(pack_name: str) -> str | None:
    """Compute a deterministic SHA256 of the pack's class schema.

    Canonical projection: sorted class names + sorted input keys from object_info.
    Returns None when object_info is unavailable for any class in the pack.
    """
    try:
        from vibecomfy.node_packs import KNOWN_NODE_PACKS
    except ImportError:
        return None
    pack = next((p for p in KNOWN_NODE_PACKS if p.name == pack_name), None)
    if pack is None or not pack.classes:
        return None
    try:
        from vibecomfy.porting.object_info.consume import get_class
    except ImportError:
        return None
    class_schemas: dict[str, dict] = {}
    for class_type in sorted(pack.classes):
        entry = get_class(class_type)
        if entry is None:
            # Missing schema — cannot compute a stable hash
            return None
        class_schemas[class_type] = entry
    return compute_schema_hash(class_schemas)


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
    nodes_spec.add_argument(
        "--in",
        dest="source",
        help="Source workflow JSON to inspect when class_type is a subgraph UUID.",
    )
    nodes_spec.add_argument(
        "--verbose",
        action="store_true",
        help="For subgraph UUIDs, include full inner nodes and edges.",
    )
    nodes_spec.add_argument("--json", action="store_true", help="Emit JSON output.")
    nodes_spec.set_defaults(func=_cmd_nodes_spec)
    nodes_lookup = nodes_sub.add_parser("lookup")
    nodes_lookup.add_argument("query")
    nodes_lookup.add_argument("--json", action="store_true")
    nodes_lookup.set_defaults(func=_cmd_nodes_lookup)
    nodes_install = nodes_sub.add_parser("install-plan")
    nodes_install.add_argument("path")
    nodes_install.add_argument("--json", action="store_true")
    nodes_install.set_defaults(func=_cmd_nodes_install_plan)
    nodes_install_pack = nodes_sub.add_parser("install")
    nodes_install_pack.add_argument("name", nargs="?")
    nodes_install_pack.add_argument("--repo")
    nodes_install_pack.add_argument("--force", action="store_true", default=False)
    nodes_install_pack.set_defaults(func=_cmd_nodes_install)
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
    nodes_refresh_template = nodes_sub.add_parser("refresh-template")
    nodes_refresh_template.add_argument("file")
    nodes_refresh_template.add_argument("--dry-run", action="store_true")
    nodes_refresh_template.add_argument("--diff", action="store_true")
    nodes_refresh_template.add_argument("--json", action="store_true")
    nodes_refresh_template.set_defaults(func=_cmd_nodes_refresh_template)
    nodes_refresh_corpus = nodes_sub.add_parser("refresh-corpus")
    nodes_refresh_corpus.add_argument("--dry-run", action="store_true")
    nodes_refresh_corpus.add_argument("--diff", action="store_true")
    nodes_refresh_corpus.add_argument("--json", action="store_true")
    nodes_refresh_corpus.set_defaults(func=_cmd_nodes_refresh_corpus)
