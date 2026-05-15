from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
import subprocess
import sys

from vibecomfy.commands._output import emit
from vibecomfy.commands.index_files import IndexReadError, print_index_error, read_index_json
from vibecomfy.registry import load_workflow_reference
from vibecomfy.schema import ObjectInfoSchemaProvider, SchemaIndexError, SourceSchemaProvider, get_schema_provider
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
    provider = ObjectInfoSchemaProvider(args.object_info_cache) if args.object_info_cache else get_schema_provider("auto")
    try:
        schema = provider.get_schema(args.class_type)
    except SchemaIndexError as exc:
        print(f"{exc}; run `vibecomfy sources sync` to rebuild indexes.")
        return 1
    if schema is None:
        schema = SourceSchemaProvider().get_schema(args.class_type)
    if schema is None:
        print(
            f"node schema not found for {args.class_type!r}; run `vibecomfy sources sync`, "
            "start a runtime with /object_info, or install the custom node source locally"
        )
        return 1
    print(json.dumps(asdict(schema), indent=2, sort_keys=True))
    return 0


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
