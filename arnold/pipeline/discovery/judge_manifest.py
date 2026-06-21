"""Import-free judge manifest primitives for pipeline judge pieces."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping


JUDGE_MANIFEST_SCHEMA = "arnold.judge-manifest.v1"
JUDGE_KIND = "judge"
EVALUAND_RECORD_CONTENT_TYPE = "application/x-evaluand-record+json"


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _canonical_digest(value: Any) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class JudgeManifestPort:
    """Typed port declaration stored in a judge sidecar manifest."""

    name: str
    content_type: str
    taint: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "content_type": self.content_type,
            "taint": list(self.taint),
        }

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "JudgeManifestPort":
        return cls(
            name=str(value["name"]),
            content_type=str(value["content_type"]),
            taint=tuple(str(item) for item in value.get("taint", ())),
        )


@dataclass(frozen=True)
class JudgePieceManifest:
    """Import-free metadata contract for a judge pipeline piece."""

    name: str
    implementation: str
    arnold_api_version: str
    piece_version: str
    judge_version: str
    rubric_hash: str
    model_identity: str
    consumes: tuple[JudgeManifestPort, ...] = field(default_factory=tuple)
    produces: tuple[JudgeManifestPort, ...] = field(default_factory=tuple)
    schema: str = JUDGE_MANIFEST_SCHEMA
    kind: str = JUDGE_KIND

    def to_json(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "name": self.name,
            "kind": self.kind,
            "implementation": self.implementation,
            "arnold_api_version": self.arnold_api_version,
            "piece_version": self.piece_version,
            "judge_version": self.judge_version,
            "rubric_hash": self.rubric_hash,
            "model_identity": self.model_identity,
            "consumes": [port.to_json() for port in self.consumes],
            "produces": [port.to_json() for port in self.produces],
        }

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "JudgePieceManifest":
        return cls(
            schema=str(value.get("schema", JUDGE_MANIFEST_SCHEMA)),
            name=str(value["name"]),
            kind=str(value.get("kind", JUDGE_KIND)),
            implementation=str(value["implementation"]),
            arnold_api_version=str(value["arnold_api_version"]),
            piece_version=str(value["piece_version"]),
            judge_version=str(value["judge_version"]),
            rubric_hash=str(value["rubric_hash"]),
            model_identity=str(value["model_identity"]),
            consumes=tuple(
                JudgeManifestPort.from_json(port)
                for port in value.get("consumes", ())
            ),
            produces=tuple(
                JudgeManifestPort.from_json(port)
                for port in value.get("produces", ())
            ),
        )


def compute_rubric_hash(rubric_body: Any) -> str:
    """Return the canonical rubric identity hash."""

    return _canonical_digest({"rubric_body": rubric_body})


def compute_piece_version(
    *,
    implementation: str,
    arnold_api_version: str,
    consumes: tuple[JudgeManifestPort, ...] = (),
    produces: tuple[JudgeManifestPort, ...] = (),
    source_hash: str | None = None,
    extra_identity: Mapping[str, Any] | None = None,
) -> str:
    """Return the canonical identity hash for a judge implementation piece."""

    return _canonical_digest(
        {
            "schema": JUDGE_MANIFEST_SCHEMA,
            "kind": JUDGE_KIND,
            "implementation": implementation,
            "arnold_api_version": arnold_api_version,
            "source_hash": source_hash,
            "consumes": [port.to_json() for port in consumes],
            "produces": [port.to_json() for port in produces],
            "extra_identity": dict(extra_identity or {}),
        }
    )


def compute_judge_version(
    *,
    piece_version: str,
    model_identity: str,
    rubric_body: Any | None = None,
    rubric_hash: str | None = None,
    extra_identity: Mapping[str, Any] | None = None,
) -> str:
    """Return the canonical identity hash for a judge configuration."""

    if rubric_hash is None:
        if rubric_body is None:
            raise ValueError("rubric_body or rubric_hash is required")
        rubric_hash = compute_rubric_hash(rubric_body)

    return _canonical_digest(
        {
            "schema": JUDGE_MANIFEST_SCHEMA,
            "piece_version": piece_version,
            "rubric_hash": rubric_hash,
            "model_identity": model_identity,
            "extra_identity": dict(extra_identity or {}),
        }
    )


def make_judge_manifest(
    *,
    name: str,
    implementation: str,
    arnold_api_version: str,
    model_identity: str,
    rubric_body: Any | None = None,
    rubric_hash: str | None = None,
    consumes: tuple[JudgeManifestPort, ...] = (),
    produces: tuple[JudgeManifestPort, ...] = (),
    source_hash: str | None = None,
    piece_extra_identity: Mapping[str, Any] | None = None,
    judge_extra_identity: Mapping[str, Any] | None = None,
) -> JudgePieceManifest:
    """Build a manifest and derive its canonical version hashes."""

    resolved_rubric_hash = (
        rubric_hash
        if rubric_hash is not None
        else compute_rubric_hash(rubric_body)
    )
    piece_version = compute_piece_version(
        implementation=implementation,
        arnold_api_version=arnold_api_version,
        consumes=consumes,
        produces=produces,
        source_hash=source_hash,
        extra_identity=piece_extra_identity,
    )
    judge_version = compute_judge_version(
        piece_version=piece_version,
        rubric_hash=resolved_rubric_hash,
        model_identity=model_identity,
        extra_identity=judge_extra_identity,
    )
    return JudgePieceManifest(
        name=name,
        implementation=implementation,
        arnold_api_version=arnold_api_version,
        piece_version=piece_version,
        judge_version=judge_version,
        rubric_hash=resolved_rubric_hash,
        model_identity=model_identity,
        consumes=consumes,
        produces=produces,
    )


def dump_judge_manifest(manifest: JudgePieceManifest, path: str | Path) -> None:
    """Write *manifest* as stable JSON with a trailing newline."""

    target = Path(path)
    target.write_text(
        json.dumps(manifest.to_json(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_judge_manifest(path: str | Path) -> JudgePieceManifest:
    """Load a judge manifest sidecar without importing judge code."""

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("judge manifest JSON must be an object")
    manifest = JudgePieceManifest.from_json(raw)
    if manifest.schema != JUDGE_MANIFEST_SCHEMA:
        raise ValueError(f"unsupported judge manifest schema {manifest.schema!r}")
    if manifest.kind != JUDGE_KIND:
        raise ValueError(f"judge manifest kind must be {JUDGE_KIND!r}")
    return manifest


__all__ = [
    "EVALUAND_RECORD_CONTENT_TYPE",
    "JUDGE_KIND",
    "JUDGE_MANIFEST_SCHEMA",
    "JudgeManifestPort",
    "JudgePieceManifest",
    "compute_judge_version",
    "compute_piece_version",
    "compute_rubric_hash",
    "dump_judge_manifest",
    "load_judge_manifest",
    "make_judge_manifest",
]
