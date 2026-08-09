"""Content attestation for fixer edit targets (the shadow gate).

Phase-0 deliverable of the fixer-unification design, rule 7: ``realpath`` +
``st_dev``/``st_ino`` is NOT inherently shadow-proof — a bind mount can
preserve the apparent path and filesystem identity. A fixer pre-flight must
assert an independent content/mount attestation: the executing module's
``__file__`` must resolve inside the declared tree, its digest must match the
tree's copy of that file, and the tree's mount identity must be attestable on
Linux.

Semantics of the shadow check
-----------------------------
A tree is *shadowed* (an inert edit target) when either:

* the executing module's ``__file__`` (observed via ``importlib`` in the
  running process) lives outside ``tree_path`` — e.g. a bind-mounted RO copy
  elsewhere on the filesystem preserves the apparent path; or
* the observed module's content digest differs from the digest of the same
  file inside ``tree_path``.

``tree_digest`` covers a bounded, deterministic content subset (never hashes a
57G tree): all ``arnold_pipelines/megaplan/cloud/*.py`` plus every file under
``arnold_pipelines/megaplan/cloud/wrappers/`` (recursively), sorted by relative
posix path, hashed as lines ``<relpath>:<sha256>\\n``.

``mount_id`` is ``"<major:minor>:<st_ino>"`` from the deepest
``/proc/self/mountinfo`` entry covering ``tree_path`` (device = mount
major:minor, inode = the tree's ``st_ino``); ``"unavailable"`` on non-Linux or
when the probe fails, with a corresponding entry in ``errors``.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from arnold_pipelines.megaplan.cloud.runtime_attestation import _git_revision, _sha256_file

MOUNT_UNAVAILABLE = "unavailable"

# Bounded content subset for tree_digest: the runtime-relevant python surface.
_SUBSET_ROOT = "arnold_pipelines/megaplan/cloud"


class ShadowedTargetError(RuntimeError):
    """Raised when a fixer target fails content attestation (shadowed/inert path)."""


@dataclass(frozen=True)
class ContentAttestation:
    """Observed content/mount identity of a fixer edit target.

    ``declared_vs_observed_match`` is True when the executing module's digest
    equals the digest of the same file inside ``tree_path``.
    """

    tree_path: str
    tree_head: str
    tree_digest: str
    module_file: str
    module_digest: str
    mount_id: str
    declared_vs_observed_match: bool
    errors: list[str]


# ── helpers ─────────────────────────────────────────────────────────────────


def _sha256_or_empty(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return _sha256_file(path)
    except OSError:
        return ""


def _git_revision_readonly(root: Path) -> str:
    """Read-only git HEAD probe; empty string when the tree has no HEAD."""
    try:
        return _git_revision(root)
    except Exception:  # noqa: BLE001 - the attestation must never crash
        return ""


def _find_spec_origin(module_name: str) -> str:
    """Origin of *module_name* in the observed namespace, or ``""``.

    Wrapped so tests can simulate a non-importable module by monkeypatching
    this seam; in production it is the real ``importlib.util.find_spec`` probe.
    """
    try:
        spec = importlib.util.find_spec(module_name)
    except (ImportError, ModuleNotFoundError, ValueError, TypeError):
        return ""
    origin = getattr(spec, "origin", None)
    if not isinstance(origin, str) or not origin:
        return ""
    return origin


def _module_path_in_tree(tree: Path, module_name: str) -> Path | None:
    """The tree's copy of *module_name* (package ``__init__.py`` or module file)."""
    rel = Path(*module_name.split("."))
    init = tree / rel / "__init__.py"
    if init.is_file():
        return init
    single = tree / f"{rel}.py"
    if single.is_file():
        return single
    return None


def _resolve_module_file(tree: Path, module_name: str) -> str:
    """Resolve the module file: observed namespace first, then the tree copy.

    The observed namespace wins because the whole point of the attestation is
    to catch a module that resolves OUTSIDE the declared tree (bind-mount
    shadowing). When the module is not importable, fall back to the tree's
    copy of the package/module file.
    """
    origin = _find_spec_origin(module_name)
    if origin:
        return origin
    tree_module = _module_path_in_tree(tree, module_name)
    return str(tree_module) if tree_module is not None else ""


def _tree_content_digest(tree: Path, errors: list[str]) -> str:
    """sha256 over ``<relpath>:<sha256>\\n`` lines for the bounded subset.

    Subset: every ``arnold_pipelines/megaplan/cloud/*.py`` plus every file under
    ``arnold_pipelines/megaplan/cloud/wrappers/`` (recursively), sorted by
    relative posix path. Deterministic for identical trees; unreadable files
    are recorded in *errors* and skipped.
    """
    subset: list[Path] = []
    cloud_dir = tree / _SUBSET_ROOT
    if cloud_dir.is_dir():
        subset.extend(sorted(cloud_dir.glob("*.py")))
        wrappers_dir = cloud_dir / "wrappers"
        if wrappers_dir.is_dir():
            subset.extend(sorted(wrappers_dir.rglob("*")))
    hasher = hashlib.sha256()
    for path in subset:
        if not path.is_file():
            continue
        rel = path.relative_to(tree).as_posix()
        try:
            digest = _sha256_file(path)
        except OSError as exc:
            errors.append(f"tree_digest_unreadable:{rel}:{exc}")
            continue
        hasher.update(rel.encode("utf-8"))
        hasher.update(b":")
        hasher.update(digest.encode("ascii"))
        hasher.update(b"\n")
    return hasher.hexdigest()


def _mount_identity_for_path(path: Path) -> tuple[str, str | None]:
    """Return ``(mount_id, error)`` for *path* via /proc/self/mountinfo.

    mount_id is ``"<device>:<inode>"``: device = the covering mount's
    major:minor, inode = the tree's ``st_ino`` (``os.stat`` with
    ``follow_symlinks=False``). ``"unavailable"`` plus an error entry on
    non-Linux, unreadable mountinfo, no covering entry, or stat failure.
    """
    if sys.platform != "linux":
        return MOUNT_UNAVAILABLE, "mount_id_unavailable:non_linux"
    mountinfo = Path("/proc/self/mountinfo")
    if not os.access(mountinfo, os.R_OK):
        return MOUNT_UNAVAILABLE, "mount_id_unavailable:mountinfo_unreadable"
    try:
        lines = mountinfo.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return MOUNT_UNAVAILABLE, f"mount_id_unavailable:{exc}"
    resolved = path.expanduser().resolve(strict=False)
    best: tuple[str, str] | None = None
    for line in lines:
        fields = line.split()
        if len(fields) < 6:
            continue
        mount_point = fields[4].replace("\\040", " ")
        if resolved == Path(mount_point) or resolved.is_relative_to(Path(mount_point)):
            if best is None or len(mount_point) > len(best[0]):
                best = (mount_point, fields[1])
    if best is None:
        return MOUNT_UNAVAILABLE, "mount_id_unavailable:no_mountinfo_entry"
    try:
        info = os.stat(resolved, follow_symlinks=False)
    except OSError as exc:
        return MOUNT_UNAVAILABLE, f"mount_id_unavailable:{exc}"
    return f"{best[1]}:{info.st_ino}", None


# ── public API ──────────────────────────────────────────────────────────────


def attest_target_content(
    tree_path: Path,
    module_name: str = "arnold_pipelines",
) -> ContentAttestation:
    """Build the content attestation for a fixer edit target.

    All probes are read-only (stat, read-only git HEAD, /proc/self/mountinfo,
    file hashing). Probe failures never raise here — they are recorded in
    ``errors`` and surface via ``refuse_shadowed_target``.
    """
    tree = Path(tree_path).expanduser().resolve(strict=False)
    errors: list[str] = []
    tree_head = _git_revision_readonly(tree)
    tree_digest = _tree_content_digest(tree, errors)
    module_file = _resolve_module_file(tree, module_name)
    module_digest = _sha256_or_empty(Path(module_file) if module_file else None)
    tree_module_path = _module_path_in_tree(tree, module_name)
    tree_module_digest = _sha256_or_empty(tree_module_path)
    declared_vs_observed_match = bool(module_digest) and module_digest == tree_module_digest
    if not module_file:
        errors.append("module_file_unresolved")
    if not module_digest:
        errors.append("module_digest_unreadable")
    if tree_module_path is None:
        errors.append(f"module_not_in_tree:{module_name}")
    elif not tree_module_digest:
        errors.append("tree_module_copy_unreadable")
    mount_id, mount_error = _mount_identity_for_path(tree)
    if mount_error:
        errors.append(mount_error)
    return ContentAttestation(
        tree_path=str(tree),
        tree_head=tree_head,
        tree_digest=tree_digest,
        module_file=module_file,
        module_digest=module_digest,
        mount_id=mount_id,
        declared_vs_observed_match=declared_vs_observed_match,
        errors=errors,
    )


def refuse_shadowed_target(attestation: ContentAttestation) -> None:
    """Raise ``ShadowedTargetError`` when the attestation shows a shadowed target.

    Fails when any of: the observed module file is not under ``tree_path``, the
    observed module digest differs from the tree's copy, or the mount identity
    is unavailable on Linux (on non-Linux the mount probe is inherently
    unavailable and does not gate).
    """
    tree = Path(attestation.tree_path).expanduser().resolve(strict=False)
    failures: list[str] = []
    module_file = Path(attestation.module_file) if attestation.module_file else None
    if module_file is None:
        failures.append("module_file_unresolved")
    else:
        resolved_module = module_file.expanduser().resolve(strict=False)
        if not resolved_module.is_relative_to(tree):
            failures.append(f"module_file_outside_tree:{resolved_module}")
    if not attestation.declared_vs_observed_match:
        failures.append("module_content_mismatch")
    if attestation.mount_id == MOUNT_UNAVAILABLE and sys.platform == "linux":
        failures.append("mount_id_unavailable_on_linux")
    if failures:
        detail = "; ".join(failures)
        raise ShadowedTargetError(
            f"refusing shadowed target {attestation.tree_path}: {detail}"
        )
