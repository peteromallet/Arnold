"""Filesystem discovery and loading for YAML-defined pipelines.

Discovers pipeline definitions from two directory trees:

* **Built-in**: ``megaplan/pipelines/<name>/pipeline.yaml`` (relative to the
  ``megaplan`` package root).
* **User**: ``~/.megaplan/pipelines/<name>/pipeline.yaml``.

The namespace is **flat** — the pipeline is identified by the directory
slug, not by a ``builtin/`` or ``user/`` prefix.  When the same name
exists in both locations the user copy wins and a warning is emitted.

Discovery API
-------------

* :func:`discover_pipelines` — scan both dirs, return ``{name: LoadedPipeline}``.
* :func:`load_pipeline` — load a single pipeline by name, raising if not found.
* :func:`list_pipeline_names` — convenience wrapper.
* :func:`describe_pipeline` — return metadata + optional SKILL.md content.

LoadedPipeline
--------------

A lightweight dataclass bundling:

* ``spec`` — the validated :class:`PipelineSpec`.
* ``path`` — the absolute path to ``pipeline.yaml``.
* ``dir`` — the enclosing pipeline directory (for resolving .md prompts).
* ``content_hash`` — sha256 hex digest covering ``pipeline.yaml`` plus all
  referenced ``.md`` prompt files (profile content is excluded — the hash
  captures *pipeline identity*, not run identity).
* ``skill_md`` — the content of ``SKILL.md`` if it exists alongside
  ``pipeline.yaml``, or ``None``.
"""

from __future__ import annotations

import hashlib
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from megaplan._pipeline.schema import PipelineSpec


# ── Loaded pipeline bundle ────────────────────────────────────────────


@dataclass(frozen=True)
class LoadedPipeline:
    """A pipeline definition fully validated and ready for compilation.

    ``content_hash`` is a stable sha256 hex digest of the pipeline's identity:
    it covers the raw ``pipeline.yaml`` content plus every referenced ``.md``
    prompt file (recursively sorted by path so ordering differences don't
    change the hash).  Profile files are deliberately excluded — the hash
    captures pipeline identity, not run identity.
    """

    spec: PipelineSpec
    path: Path
    dir: Path
    content_hash: str
    skill_md: str | None = None

    @property
    def name(self) -> str:
        """The pipeline name from ``pipeline.yaml`` (``spec.name``)."""
        return self.spec.name


# ── Directory resolution ─────────────────────────────────────────────


def _builtin_pipelines_dir() -> Path:
    """Return ``megaplan/pipelines/`` relative to the megaplan package root."""
    import megaplan._pipeline

    package_file = Path(megaplan._pipeline.__file__).resolve()
    # megaplan/_pipeline/__init__.py → up to megaplan/
    return package_file.parent.parent / "pipelines"


def _user_pipelines_dir() -> Path:
    """Return ``~/.megaplan/pipelines/``."""
    return Path.home() / ".megaplan" / "pipelines"


# ── YAML loading with error-path annotation ──────────────────────────


def _load_yaml_file(path: Path) -> dict[str, Any]:
    """Read *path* and return the parsed YAML dict.

    Raises :class:`yaml.YAMLError` with a message that includes the file path
    for diagnosis.
    """
    raw = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise yaml.YAMLError(f"{path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(
            f"{path}: expected a YAML mapping at top level, got {type(data).__name__}"
        )
    return data


class PipelineLoadError(Exception):
    """Raised when a ``pipeline.yaml`` cannot be loaded or validated.

    Wraps the original exception and prepends the file path so the user
    can identify *which* pipeline is broken.
    """

    def __init__(self, path: Path, original: Exception) -> None:
        self.path = path
        self.original = original
        super().__init__(f"{path}: {original}")


def _load_and_validate(path: Path) -> PipelineSpec:
    """Load a ``pipeline.yaml`` file and validate it through :class:`PipelineSpec`.

    Pydantic validation errors are re-raised with the file path prepended
    so the user can identify which file caused the failure.
    """
    try:
        data = _load_yaml_file(path)
        return PipelineSpec.model_validate(data)
    except Exception as exc:
        raise PipelineLoadError(path, exc) from exc


# ── Content hash ─────────────────────────────────────────────────────


def _compute_content_hash(pipeline_path: Path, spec: PipelineSpec) -> str:
    """Compute a stable sha256 hash of the pipeline's identity.

    Covers:
    * The raw ``pipeline.yaml`` content.
    * Every referenced ``.md`` prompt file, read from the pipeline directory.

    Files are sorted by relative path before hashing so that filesystem
    ordering differences do not change the hash.  Profile files and other
    non-prompt assets are deliberately excluded.
    """
    pipeline_dir = pipeline_path.parent
    hasher = hashlib.sha256()

    # 1. pipeline.yaml content (use raw bytes for stability, not parsed YAML)
    hasher.update(pipeline_path.read_bytes())

    # 2. Collect unique .md prompt references from all stages
    md_refs: set[str] = set()
    for stage in spec.stages:
        # Agent and gate stages carry prompt directly
        prompt: str | None = getattr(stage, "prompt", None)
        if prompt and prompt.endswith(".md"):
            md_refs.add(prompt)
        # Panel stages carry prompts inside reviewer specs
        reviewers: list[Any] = getattr(stage, "reviewers", None) or []
        for reviewer in reviewers:
            rp: str | None = getattr(reviewer, "prompt", None)
            if rp and rp.endswith(".md"):
                md_refs.add(rp)

    # 3. Hash prompt files in sorted order (stability)
    for ref in sorted(md_refs):
        prompt_path = (pipeline_dir / ref).resolve()
        if prompt_path.is_file():
            hasher.update(prompt_path.read_bytes())

    return hasher.hexdigest()


# ── Discovery ────────────────────────────────────────────────────────


def discover_pipelines(
    *,
    builtin_dir: Path | None = None,
    user_dir: Path | None = None,
) -> dict[str, LoadedPipeline]:
    """Scan built-in and user pipeline directories.

    Parameters
    ----------
    builtin_dir:
        Override the built-in directory (default: ``megaplan/pipelines/``).
    user_dir:
        Override the user directory (default: ``~/.megaplan/pipelines/``).

    Returns
    -------
    dict[str, LoadedPipeline]
        Pipeline name → loaded pipeline.  When the same name exists in both
        locations, the user copy wins and a warning is emitted.

    Raises
    ------
    yaml.YAMLError
        If any ``pipeline.yaml`` contains invalid YAML.
    pydantic.ValidationError
        If any ``pipeline.yaml`` fails schema validation.
    """
    builtin_dir = builtin_dir or _builtin_pipelines_dir()
    user_dir = user_dir or _user_pipelines_dir()

    loaded: dict[str, LoadedPipeline] = {}

    # Built-in pipelines first
    if builtin_dir.is_dir():
        for child in sorted(builtin_dir.iterdir()):
            if not child.is_dir():
                continue
            pipeline_yaml = child / "pipeline.yaml"
            if not pipeline_yaml.is_file():
                continue
            name = child.name
            lp = _load_one(pipeline_yaml)
            loaded[name] = lp

    # User pipelines — shadow built-in with warning
    if user_dir.is_dir():
        for child in sorted(user_dir.iterdir()):
            if not child.is_dir():
                continue
            pipeline_yaml = child / "pipeline.yaml"
            if not pipeline_yaml.is_file():
                continue
            name = child.name
            lp = _load_one(pipeline_yaml)
            if name in loaded:
                warnings.warn(
                    f"User pipeline '{name}' ({pipeline_yaml}) shadows "
                    f"built-in pipeline ({loaded[name].path}). "
                    f"Using user copy.",
                    stacklevel=2,
                )
            loaded[name] = lp

    return loaded


def _load_one(pipeline_yaml: Path) -> LoadedPipeline:
    """Load a single PipelineSpec from *pipeline_yaml* and return a bundle."""
    spec = _load_and_validate(pipeline_yaml)
    pipeline_dir = pipeline_yaml.parent
    content_hash = _compute_content_hash(pipeline_yaml, spec)
    skill_md = _read_skill_md(pipeline_dir)
    return LoadedPipeline(
        spec=spec,
        path=pipeline_yaml.resolve(),
        dir=pipeline_dir.resolve(),
        content_hash=content_hash,
        skill_md=skill_md,
    )


# ── SKILL.md ─────────────────────────────────────────────────────────


def _read_skill_md(pipeline_dir: Path) -> str | None:
    """Read SKILL.md from *pipeline_dir* if present, else None."""
    skill_path = pipeline_dir / "SKILL.md"
    if skill_path.is_file():
        return skill_path.read_text(encoding="utf-8")
    return None


# ── Public convenience ───────────────────────────────────────────────


def load_pipeline(
    name: str,
    *,
    builtin_dir: Path | None = None,
    user_dir: Path | None = None,
) -> LoadedPipeline:
    """Load a single pipeline by name.

    Raises :class:`KeyError` if not found in either built-in or user dirs.
    """
    pipelines = discover_pipelines(builtin_dir=builtin_dir, user_dir=user_dir)
    if name not in pipelines:
        available = sorted(pipelines)
        raise KeyError(
            f"No pipeline named {name!r}. "
            f"Available: {available if available else '(none discovered)'}"
        )
    return pipelines[name]


def list_pipeline_names(
    *,
    builtin_dir: Path | None = None,
    user_dir: Path | None = None,
) -> tuple[str, ...]:
    """Return sorted pipeline names discovered on the filesystem."""
    pipelines = discover_pipelines(builtin_dir=builtin_dir, user_dir=user_dir)
    return tuple(sorted(pipelines))


def describe_pipeline(
    name: str,
    *,
    builtin_dir: Path | None = None,
    user_dir: Path | None = None,
) -> str:
    """Return a human-readable description of *name*.

    Includes the ``description`` field from ``pipeline.yaml`` and, if
    present, the content of ``SKILL.md``.
    """
    lp = load_pipeline(name, builtin_dir=builtin_dir, user_dir=user_dir)
    lines: list[str] = []
    lines.append(f"Pipeline: {lp.spec.name} (v{lp.spec.version})")
    lines.append(f"Source:   {lp.path}")
    if lp.spec.description:
        lines.append("")
        lines.append(lp.spec.description)
    if lp.spec.default_profile:
        lines.append("")
        lines.append(f"Default profile: {lp.spec.default_profile}")
    if lp.spec.recommended_profiles:
        lines.append(f"Recommended:     {', '.join(lp.spec.recommended_profiles)}")
    if lp.spec.supported_modes:
        lines.append(f"Modes:           {', '.join(lp.spec.supported_modes)}")
    if lp.skill_md:
        lines.append("")
        lines.append("─── SKILL.md ───")
        lines.append(lp.skill_md.strip())
    return "\n".join(lines)
