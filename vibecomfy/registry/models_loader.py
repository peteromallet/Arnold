from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

import yaml

from vibecomfy import fetch as fetch_assets


DEFAULT_REGISTRY_PATH = Path(__file__).with_name("models.yaml")
RESERVED_TAGS = {
    "phase:core",
    "phase:gguf",
    "phase:ltx",
    "phase:wan_wrapper",
    "phase:qwen_image",
    "ltx_lean_excluded",
    "requires_hf_token",
    "excluded_in_public_scope",
}
LTX_LEAN_EXCLUDED_SCOPES = {"ltx_official", "ltx_official_public", "ltx_lightricks", "ltx_iclora", "ltx_iclora_public"}
PUBLIC_SCOPES = {"ltx_official_public", "ltx_iclora_public"}


@dataclass(frozen=True)
class ModelSource:
    kind: str
    repo: str | None = None
    filename: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class ModelTarget:
    node_pack: str
    path: str


@dataclass(frozen=True)
class ModelEntry:
    id: str
    source: ModelSource
    min_size: int
    targets: tuple[ModelTarget, ...]
    canonical_name: str | None = None
    aliases: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    notes: str | None = None


_REGISTRY_CACHE: dict[Path, tuple[ModelEntry, ...]] = {}


def load_registry(path: str | Path | None = None) -> tuple[ModelEntry, ...]:
    registry_path = _registry_path(path)
    cached = _REGISTRY_CACHE.get(registry_path)
    if cached is not None:
        return cached
    with registry_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    entries_data = data.get("models", data) if isinstance(data, Mapping) else data
    if not isinstance(entries_data, list):
        raise ValueError(f"{registry_path}: registry must be a list or contain a 'models' list")
    entries = tuple(_parse_entry(raw, registry_path=registry_path) for raw in entries_data)
    _validate_registry(entries, registry_path=registry_path)
    _REGISTRY_CACHE[registry_path] = entries
    return entries


def stage_entry(entry: ModelEntry, *, models_root: Path) -> list[Path]:
    source = _download_source(entry, models_root=models_root)
    _check_size(source, entry.min_size, entry.id)
    staged_paths: list[Path] = []
    for target in entry.targets:
        staged = models_root / target.path
        staged.parent.mkdir(parents=True, exist_ok=True)
        if os.path.lexists(staged):
            _check_collision(staged, source, entry.id)
            staged.unlink()
        try:
            os.link(source, staged)
        except OSError:
            os.symlink(source, staged)
        _check_size(staged, entry.min_size, entry.id)
        staged_paths.append(staged)
    return staged_paths


def stage_many(entries: Sequence[ModelEntry], *, models_root: Path, ids: Sequence[str] | None = None) -> None:
    selected = _select_by_ids(entries, ids)
    for entry in selected:
        stage_entry(entry, models_root=models_root)


def normalize_alias(value: str, *, registry: Sequence[ModelEntry] | None = None, node_pack: str | None = None) -> str | None:
    entries = registry if registry is not None else load_registry()
    for entry in entries:
        if node_pack is not None and all(target.node_pack != node_pack for target in entry.targets):
            continue
        if value in entry.aliases:
            return canonical_filename(entry.id, registry=entries)
    return None


def canonical_filename(model_id: str, *, registry: Sequence[ModelEntry] | None = None) -> str:
    entries = registry if registry is not None else load_registry()
    for entry in entries:
        if entry.id == model_id:
            if entry.canonical_name:
                return entry.canonical_name
            filename = _source_filename(entry.source)
            if filename:
                return filename
            raise ValueError(f"{entry.id}: source filename could not be inferred")
    raise KeyError(f"unknown model id: {model_id}")


def _clear_cache() -> None:
    _REGISTRY_CACHE.clear()


def _registry_path(path: str | Path | None) -> Path:
    return (Path(path) if path is not None else DEFAULT_REGISTRY_PATH).expanduser().resolve()


def _parse_entry(raw: Any, *, registry_path: Path) -> ModelEntry:
    if not isinstance(raw, Mapping):
        raise ValueError(f"{registry_path}: each model entry must be a mapping")
    entry_id = _required_str(raw, "id", "<unknown>")
    source_raw = raw.get("source")
    if not isinstance(source_raw, Mapping):
        raise ValueError(f"{entry_id}: source must be a mapping")
    source = ModelSource(
        kind=_required_str(source_raw, "kind", entry_id),
        repo=_optional_str(source_raw.get("repo")),
        filename=_optional_str(source_raw.get("filename")),
        url=_optional_str(source_raw.get("url")),
    )
    if not isinstance(targets_raw := raw.get("targets", []), list) or not targets_raw:
        raise ValueError(f"{entry_id}: targets must be a non-empty list")
    targets = tuple(_parse_target(target, entry_id=entry_id) for target in targets_raw)
    canonical_name = _optional_str(raw.get("canonical_name"))
    aliases = _str_tuple(raw.get("aliases", []), entry_id=entry_id, field="aliases")
    tags = _str_tuple(raw.get("tags", []), entry_id=entry_id, field="tags")
    if not isinstance(min_size := raw.get("min_size"), int) or min_size < 0:
        raise ValueError(f"{entry_id}: min_size must be a non-negative integer")
    if (notes := raw.get("notes")) is not None and not isinstance(notes, str):
        raise ValueError(f"{entry_id}: notes must be a string")
    return ModelEntry(
        id=entry_id,
        source=source,
        min_size=min_size,
        targets=targets,
        canonical_name=canonical_name,
        aliases=aliases,
        tags=tags,
        notes=notes,
    )


def _parse_target(raw: Any, *, entry_id: str) -> ModelTarget:
    if not isinstance(raw, Mapping):
        raise ValueError(f"{entry_id}: target must be a mapping")
    node_pack = _required_str(raw, "node_pack", entry_id)
    path = _required_str(raw, "path", entry_id)
    _validate_target_path(path, entry_id=entry_id)
    return ModelTarget(node_pack=node_pack, path=path)


def _validate_registry(entries: Sequence[ModelEntry], *, registry_path: Path) -> None:
    seen_ids: set[str] = set()
    seen_aliases: dict[str, str] = {}
    for entry in entries:
        if entry.id in seen_ids:
            raise ValueError(f"{registry_path}: duplicate model id {entry.id!r}")
        seen_ids.add(entry.id)
        if entry.source.kind == "huggingface":
            if not entry.source.repo or not entry.source.filename:
                raise ValueError(f"{entry.id}: huggingface source requires repo and filename")
        elif entry.source.kind == "url":
            if not entry.source.url:
                raise ValueError(f"{entry.id}: url source requires url")
        else:
            raise ValueError(f"{entry.id}: unsupported source kind {entry.source.kind!r}")
        for tag in entry.tags:
            if tag not in RESERVED_TAGS:
                raise ValueError(f"{entry.id}: unknown tag {tag!r}")
        for alias in entry.aliases:
            owner = seen_aliases.get(alias)
            if owner is not None:
                raise ValueError(f"{entry.id}: duplicate alias {alias!r}; already used by {owner}")
            seen_aliases[alias] = entry.id


def _validate_target_path(path: str, *, entry_id: str) -> None:
    if not path:
        raise ValueError(f"{entry_id}: invalid target.path {path!r}: path must be non-empty")
    if path.startswith("models/") or path.startswith("models\\"):
        raise ValueError(f"{entry_id}: invalid target.path {path!r}: path is relative to models_root and must not start with models/")
    posix, windows = PurePosixPath(path), PureWindowsPath(path)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        raise ValueError(f"{entry_id}: invalid target.path {path!r}: absolute paths are not allowed")
    if ".." in posix.parts or ".." in windows.parts:
        raise ValueError(f"{entry_id}: invalid target.path {path!r}: '..' segments are not allowed")


def _download_source(entry: ModelEntry, *, models_root: Path) -> Path:
    if entry.source.kind == "huggingface":
        from huggingface_hub import hf_hub_download

        path = hf_hub_download(repo_id=entry.source.repo, filename=entry.source.filename)
        return Path(path).resolve(strict=True)
    if entry.source.kind == "url":
        filename = _source_filename(entry.source)
        downloaded = fetch_assets.download({"name": filename, "subdir": "_registry", "url": entry.source.url}, root=models_root)
        return downloaded.resolve(strict=True)
    raise ValueError(f"{entry.id}: unsupported source kind {entry.source.kind!r}")


def _check_collision(staged: Path, source: Path, entry_id: str) -> None:
    if staged.is_symlink():
        return
    try:
        if staged.stat().st_ino == source.stat().st_ino and staged.stat().st_dev == source.stat().st_dev:
            return
    except FileNotFoundError:
        return
    raise RuntimeError(f"{entry_id}: refusing to overwrite unrelated existing file at {staged}")


def _check_size(path: Path, min_size: int, entry_id: str) -> None:
    size = path.stat().st_size
    if size < min_size:
        raise RuntimeError(f"{entry_id}: {path} is too small ({size} bytes < {min_size} bytes)")


def _select_by_ids(entries: Sequence[ModelEntry], ids: Sequence[str] | None) -> tuple[ModelEntry, ...]:
    if ids is None:
        return tuple(entries)
    by_id = {entry.id: entry for entry in entries}
    missing = [model_id for model_id in ids if model_id not in by_id]
    if missing:
        raise KeyError(f"unknown model id(s): {', '.join(missing)}")
    return tuple(by_id[model_id] for model_id in ids)


def _filter_entries(entries: Sequence[ModelEntry], *, ids: Sequence[str] | None, select_phase: str | None) -> tuple[ModelEntry, ...]:
    selected = _select_by_ids(entries, ids)
    if select_phase is not None:
        selected = tuple(entry for entry in selected if f"phase:{select_phase}" in entry.tags)
    scope = os.environ.get("VIBECOMFY_MATRIX_SCOPE")
    if scope in LTX_LEAN_EXCLUDED_SCOPES:
        selected = tuple(entry for entry in selected if "ltx_lean_excluded" not in entry.tags)
    if scope in PUBLIC_SCOPES:
        selected = tuple(entry for entry in selected if "excluded_in_public_scope" not in entry.tags)
    if not os.environ.get("HF_TOKEN"):
        selected = tuple(entry for entry in selected if "requires_hf_token" not in entry.tags)
    return selected


def _print_dry_run(entries: Sequence[ModelEntry], *, models_root: Path) -> None:
    for entry in entries:
        source = _source_label(entry.source)
        print(f"{entry.id}: {source}")
        for target in entry.targets:
            staged = models_root / target.path
            if staged.exists():
                size = staged.stat().st_size
                status = "ok" if size >= entry.min_size else f"too-small ({size} < {entry.min_size})"
            else:
                status = "missing"
            print(f"  -> {staged.absolute()} [{status}]")


def _source_filename(source: ModelSource) -> str:
    if source.filename:
        return Path(source.filename).name
    if source.url:
        name = Path(urlsplit(source.url).path).name
        if name:
            return name
    return ""


def _source_label(source: ModelSource) -> str:
    return f"hf://{source.repo}/{source.filename}" if source.kind == "huggingface" else source.url or "url:<missing>"


def _required_str(raw: Mapping[str, Any], key: str, entry_id: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{entry_id}: {key} must be a non-empty string")
    return value


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError("optional string fields must be non-empty strings when set")
    return value


def _str_tuple(value: Any, *, entry_id: str, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{entry_id}: {field} must be a list of non-empty strings")
    return tuple(value)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m vibecomfy.registry.models_loader")
    subparsers = parser.add_subparsers(dest="action", required=True)
    stage = subparsers.add_parser("stage")
    stage.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    stage.add_argument("--models-root", type=Path, required=True)
    stage.add_argument("--ids", nargs="+")
    stage.add_argument("--select-phase", choices=("core", "gguf", "ltx", "wan_wrapper", "qwen_image"))
    stage.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    entries = load_registry(args.registry)
    selected = _filter_entries(entries, ids=args.ids, select_phase=args.select_phase)
    if args.dry_run:
        _print_dry_run(selected, models_root=args.models_root)
    else:
        stage_many(selected, models_root=args.models_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
