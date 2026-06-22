"""Import-free discovery and validation for judge sidecar manifests."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from arnold_pipelines.megaplan._pipeline.contracts import BindResult, RepairGradient, bind
from arnold_pipelines.megaplan._pipeline.judge_manifest import (
    EVALUAND_RECORD_CONTENT_TYPE,
    JUDGE_KIND,
    JudgePieceManifest,
    JUDGE_MANIFEST_SCHEMA,
    load_judge_manifest,
)
from arnold_pipelines.megaplan._pipeline.registry import _get_scan_roots
from arnold_pipelines.megaplan._pipeline.types import CONTENT_TYPES, Pipeline, Port, PortRef


@dataclass(frozen=True)
class JudgeManifestMatch:
    name: str
    path: Path
    manifest: JudgePieceManifest


@dataclass(frozen=True)
class JudgeManifestDiagnostics:
    manifest: JudgePieceManifest
    path: Path
    defects: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.defects


def _iter_judge_manifest_paths() -> tuple[Path, ...]:
    paths: list[Path] = []
    for root, _package_prefix in _get_scan_roots():
        if not root.exists() or not root.is_dir():
            continue
        paths.extend(sorted(root.rglob("*.judge.json")))
    return tuple(paths)


def discover_judge_manifests() -> tuple[JudgeManifestMatch, ...]:
    """Load all sidecar judge manifests without importing implementations."""

    matches: list[JudgeManifestMatch] = []
    for path in _iter_judge_manifest_paths():
        manifest = load_judge_manifest(path)
        matches.append(
            JudgeManifestMatch(name=manifest.name, path=path, manifest=manifest)
        )
    return tuple(matches)


def find_judge_manifest(name: str) -> Optional[JudgeManifestMatch]:
    """Return the first sidecar manifest named *name*, or ``None``."""

    expected_filename = f"{name}.judge.json"
    for path in _iter_judge_manifest_paths():
        try:
            manifest = load_judge_manifest(path)
        except Exception:
            if path.name == expected_filename:
                raise
            continue
        if manifest.name == name:
            return JudgeManifestMatch(name=manifest.name, path=path, manifest=manifest)
    return None


def validate_judge_manifest(
    manifest: JudgePieceManifest,
    *,
    path: str | Path,
) -> JudgeManifestDiagnostics:
    """Validate the import-free M5 judge manifest contract."""

    defects: list[str] = []
    for field_name in (
        "name",
        "implementation",
        "arnold_api_version",
        "piece_version",
        "judge_version",
        "rubric_hash",
        "model_identity",
    ):
        value = getattr(manifest, field_name)
        if not isinstance(value, str) or not value:
            defects.append(f"{field_name} must be a non-empty string")

    if manifest.schema != JUDGE_MANIFEST_SCHEMA:
        defects.append(f"schema must be {JUDGE_MANIFEST_SCHEMA!r}")
    if manifest.kind != JUDGE_KIND:
        defects.append(f"kind must be {JUDGE_KIND!r}")
    if not manifest.consumes:
        defects.append("consumes must declare at least one input port")
    if not manifest.produces:
        defects.append("produces must declare at least one output port")

    for field_name in ("piece_version", "judge_version", "rubric_hash"):
        value = getattr(manifest, field_name)
        if isinstance(value, str) and value and len(value) != 64:
            defects.append(f"{field_name} must be a 64-character SHA-256 hex digest")

    for port_group, ports in (
        ("consumes", manifest.consumes),
        ("produces", manifest.produces),
    ):
        for port in ports:
            if not isinstance(port.name, str) or not port.name:
                defects.append(f"{port_group} port name must be a non-empty string")
            if not isinstance(port.content_type, str) or not port.content_type:
                defects.append(
                    f"{port_group}.{port.name or '<unnamed>'} content_type must be a non-empty string"
                )
                continue
            if port.content_type not in CONTENT_TYPES:
                defects.append(
                    f"{port_group}.{port.name} uses unknown content type "
                    f"{port.content_type!r}"
                )

    if not any(
        port.content_type == EVALUAND_RECORD_CONTENT_TYPE
        for port in manifest.produces
    ):
        defects.append(
            f"produces must include {EVALUAND_RECORD_CONTENT_TYPE!r}"
        )

    return JudgeManifestDiagnostics(
        manifest=manifest,
        path=Path(path),
        defects=tuple(defects),
    )


def manifest_to_binder_ports(
    manifest: JudgePieceManifest,
) -> tuple[tuple[PortRef, ...], tuple[Port, ...]]:
    """Represent manifest ports using the existing binder port types."""

    consumes = tuple(
        PortRef(port_name=port.name, content_type=port.content_type)
        for port in manifest.consumes
    )
    produces = tuple(
        Port(
            name=port.name,
            content_type=port.content_type,
            taint=frozenset(port.taint),
        )
        for port in manifest.produces
    )
    return consumes, produces


def validate_manifest_bindings(
    pipeline: Pipeline,
    *,
    judge_stage_name: str,
    manifest: JudgePieceManifest,
) -> BindResult | RepairGradient:
    """Run the existing typed binder against a judge manifest stage view."""

    if judge_stage_name not in pipeline.stages:
        raise KeyError(f"no stage named {judge_stage_name!r}")

    consumes, produces = manifest_to_binder_ports(manifest)
    stages = dict(pipeline.stages)
    stages[judge_stage_name] = dataclasses.replace(
        stages[judge_stage_name],
        consumes=consumes,
        produces=produces,
    )
    edges = [
        (src, edge.target)
        for src, stage in stages.items()
        for edge in getattr(stage, "edges", ())
        if edge.target != "halt"
    ]
    return bind(stages, edges)


__all__ = [
    "JudgeManifestDiagnostics",
    "JudgeManifestMatch",
    "discover_judge_manifests",
    "find_judge_manifest",
    "manifest_to_binder_ports",
    "validate_manifest_bindings",
    "validate_judge_manifest",
]
