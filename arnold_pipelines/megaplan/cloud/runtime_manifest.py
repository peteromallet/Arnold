"""Schema-versioned per-runtime manifest — the ONLY post-bootstrap runtime resolver.

Phase-2 deliverable of the fixer-unification design (rule 3, §4 Phase 2): one
``runtime-manifest.json`` per runtime is the single post-bootstrap resolver for
repair-bin location, expected head, execution source, indirection, policy, and
promotion history. Something outside the manifest must locate the manifest —
that is the **stable bootstrap path** resolved by :func:`bootstrap_manifest`
(see its docstring for the exact semantics). One authoritative writer: all
writes go through :func:`write_manifest`, which serializes atomically
(tmp file + ``os.replace``) under an exclusive ``flock`` on a sibling
``<name>.lock`` file, so a concurrent reader never observes a partial file and
two writers cannot interleave.

Invariants from the design brief
--------------------------------
* Schema-versioned: ``schema == MANIFEST_SCHEMA_VERSION`` or the manifest is
  refused (``ManifestError``). A future schema bump is a deliberate, loud
  migration point.
* Generation/rollback contract (design rule 0): ``advance_generation`` builds a
  NEW manifest with ``generation + 1`` and records the previous generation +
  commit in ``promotions`` (the rollback record). Manifests are immutable;
  every transition returns a fresh instance.
* State machine: ``state`` is ``"active"`` or ``"closed"`` only;
  :func:`set_state` stamps ``timestamps.closed`` when closing.
* On startup a launcher emits :func:`attest_runtime` — the actual module
  path/digest and mount identity of ``epic.runtime_root`` — rather than
  trusting declared paths (design rule 7 content attestation).
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan.cloud.shadow_attestation import attest_target_content

MANIFEST_SCHEMA_VERSION = "1"

# Canonical manifest filename inside a bootstrap *directory*.
MANIFEST_FILENAME = "runtime-manifest.json"

_VALID_STATES = frozenset({"active", "closed"})

_TOP_LEVEL_REQUIRED = (
    "runtime_id",
    "schema",
    "generation",
    "epic_id",
    "state",
    "owner",
    "base",
    "epic",
    "indirection",
    "policy",
    "promotions",
    "timestamps",
    "gc_policy",
    "commands",
)

_BASE_REQUIRED = ("ref", "commit", "editable_install_path", "venv_path")
_EPIC_REQUIRED = (
    "branch",
    "worktree_path",
    "venv_path",
    "runtime_root",
    "expected_head",
    "repair_bin",
    "deps_lockfile",
)
_INDIRECTION_REQUIRED = (
    "host_path",
    "container_path",
    "mount_table",
    "execution_namespace",
    "verified_head",
    "last_verified_at",
    "attestation",
)
_INDIRECTION_ATTESTATION_REQUIRED = ("module_file", "module_digest", "mount_id")
_POLICY_REQUIRED = ("policy_sha", "model_policy_sha", "sync_policy")
_TIMESTAMPS_REQUIRED = ("created", "updated", "closed")


class ManifestError(ValueError):
    """Raised when a runtime manifest is missing, corrupt, or schema-mismatched."""


def _require_keys(label: str, mapping: Any, required: tuple[str, ...]) -> None:
    if not isinstance(mapping, dict):
        raise ManifestError(f"{label} must be an object")
    missing = [key for key in required if key not in mapping]
    if missing:
        raise ManifestError(f"{label} missing required keys: {', '.join(missing)}")


@dataclass(frozen=True)
class RuntimeManifest:
    """One per-runtime manifest; immutable — transitions return new instances.

    Nested sections (``base``, ``epic``, ``indirection``, ``policy``,
    ``timestamps``) are plain ``dict[str, Any]`` — read them with key access,
    e.g. ``manifest.epic["repair_bin"]``. Required keys are validated in
    ``__post_init__`` (raises :class:`ManifestError`).
    """

    runtime_id: str
    schema: str
    generation: int
    epic_id: str
    state: str
    owner: str
    base: dict[str, Any]
    epic: dict[str, Any]
    indirection: dict[str, Any]
    policy: dict[str, Any]
    promotions: list[dict[str, Any]]
    timestamps: dict[str, Any]
    gc_policy: str
    commands: list[dict[str, Any]]

    def __post_init__(self) -> None:
        if self.schema != MANIFEST_SCHEMA_VERSION:
            raise ManifestError(
                f"unsupported manifest schema {self.schema!r}; "
                f"expected {MANIFEST_SCHEMA_VERSION!r}"
            )
        if not isinstance(self.generation, int) or self.generation < 1:
            raise ManifestError(
                f"generation must be an int >= 1, got {self.generation!r}"
            )
        if self.state not in _VALID_STATES:
            raise ManifestError(
                f"state must be one of {sorted(_VALID_STATES)}, got {self.state!r}"
            )
        _require_keys("base", self.base, _BASE_REQUIRED)
        _require_keys("epic", self.epic, _EPIC_REQUIRED)
        _require_keys("indirection", self.indirection, _INDIRECTION_REQUIRED)
        _require_keys("policy", self.policy, _POLICY_REQUIRED)
        _require_keys("timestamps", self.timestamps, _TIMESTAMPS_REQUIRED)
        attestation = self.indirection.get("attestation")
        if not isinstance(attestation, dict):
            raise ManifestError("indirection.attestation must be an object")
        _require_keys(
            "indirection.attestation", attestation, _INDIRECTION_ATTESTATION_REQUIRED
        )
        if not isinstance(self.promotions, list) or not isinstance(self.commands, list):
            raise ManifestError("promotions and commands must be lists")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RuntimeManifest":
        """Build a manifest from parsed JSON, validating required top-level fields.

        Unknown keys in *data* are ignored (forward-compatible with newer
        schema fields); missing required fields raise :class:`ManifestError`.
        """
        if not isinstance(data, Mapping):
            raise ManifestError("manifest payload must be a JSON object")
        missing = [key for key in _TOP_LEVEL_REQUIRED if key not in data]
        if missing:
            raise ManifestError(
                f"manifest missing required fields: {', '.join(missing)}"
            )
        return cls(**{key: data[key] for key in _TOP_LEVEL_REQUIRED})

    def to_dict(self) -> dict[str, Any]:
        """Plain JSON-serializable dict (deep copy via :func:`dataclasses.asdict`)."""
        return asdict(self)


# ── serialization ───────────────────────────────────────────────────────────


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    """Atomic tmp-file + ``os.replace`` write; identical pattern to
    ``runtime_attestation._atomic_write`` (fsync before rename, cleanup on
    failure). Callers hold the manifest lock.
    """
    path = path.expanduser().resolve(strict=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def write_manifest(manifest: RuntimeManifest, path: Path) -> None:
    """Serialize *manifest* to *path* atomically under an exclusive flock.

    A sibling ``<name>.lock`` file is created (and kept) next to *path*;
    writers take ``flock(LOCK_EX)`` around the tmp+rename so concurrent
    writers serialize and readers never observe a partial file.
    """
    target = Path(path).expanduser().resolve(strict=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_path = target.with_name(target.name + ".lock")
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        _atomic_write(target, manifest.to_dict())
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)


def load_manifest(path: Path) -> RuntimeManifest:
    """Parse and validate the manifest at *path*.

    Raises :class:`ManifestError` on unreadable file, corrupt JSON, schema
    mismatch, or missing required fields.
    """
    target = Path(path).expanduser().resolve(strict=False)
    try:
        raw = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(f"cannot read manifest {target}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"corrupt manifest JSON at {target}: {exc}") from exc
    return RuntimeManifest.from_dict(data)


# ── index ───────────────────────────────────────────────────────────────────


def list_manifests(manifest_dir: Path) -> list[RuntimeManifest]:
    """Read-only index of every valid manifest in *manifest_dir*, sorted by
    ``runtime_id``.

    Files that do not parse as a valid manifest (corrupt JSON, schema
    mismatch, missing fields — e.g. stray JSON in the directory) are skipped
    so they cannot break the index; use :func:`load_manifest` on a specific
    path to surface such errors.
    """
    directory = Path(manifest_dir).expanduser()
    if not directory.is_dir():
        return []
    manifests: list[RuntimeManifest] = []
    for candidate in directory.glob("*.json"):
        try:
            manifests.append(load_manifest(candidate))
        except ManifestError:
            continue
    return sorted(manifests, key=lambda manifest: manifest.runtime_id)


def load_manifest_by_epic(
    epic_id: str, manifest_dir: Path
) -> RuntimeManifest | None:
    """Return the manifest in *manifest_dir* whose ``epic_id`` matches, or
    ``None`` when absent. Invalid/non-manifest files are skipped (see
    :func:`list_manifests`)."""
    for manifest in list_manifests(manifest_dir):
        if manifest.epic_id == epic_id:
            return manifest
    return None


# ── bootstrap ───────────────────────────────────────────────────────────────


def _read_pointer(pointer_path: Path) -> str:
    """First non-comment, non-empty line of *pointer_path* = the manifest path."""
    try:
        text = pointer_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(
            f"cannot read bootstrap pointer {pointer_path}: {exc}"
        ) from exc
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    raise ManifestError(f"bootstrap pointer {pointer_path} contains no manifest path")


def bootstrap_manifest(bootstrap_path: Path) -> RuntimeManifest:
    """Resolve the active runtime manifest from ONE stable bootstrap path.

    Bootstrap semantics (in order):

    1. Missing path -> :class:`ManifestError`.
    2. Directory -> load ``<dir>/runtime-manifest.json``.
    3. File ending in ``.json`` -> loaded directly as a manifest.
    4. Any other file is a POINTER file: the first non-empty, non-comment
       line names the manifest (relative to the pointer file's parent). If
       that target is a directory, ``<target>/runtime-manifest.json`` is used.

    This is the single stable entry point every launcher uses post-bootstrap;
    nothing else may locate the runtime manifest.
    """
    bootstrap = Path(bootstrap_path).expanduser()
    if not bootstrap.exists():
        raise ManifestError(f"bootstrap path does not exist: {bootstrap}")
    if bootstrap.is_dir():
        return load_manifest(bootstrap / MANIFEST_FILENAME)
    if bootstrap.name.endswith(".json"):
        return load_manifest(bootstrap)
    target = Path(_read_pointer(bootstrap))
    if not target.is_absolute():
        target = bootstrap.parent / target
    if target.is_dir():
        target = target / MANIFEST_FILENAME
    if not target.exists():
        raise ManifestError(f"bootstrap pointer target does not exist: {target}")
    return load_manifest(target)


# ── attestation ─────────────────────────────────────────────────────────────


def attest_runtime(
    manifest: RuntimeManifest, *, module_name: str = "arnold_pipelines"
) -> dict[str, Any]:
    """Content attestation of the runtime named by *manifest*.

    Reuses ``shadow_attestation.attest_target_content`` against
    ``manifest.epic["runtime_root"]`` and *module_name*. NEVER raises — probe
    failures are returned in ``errors``. Returns exactly:
    ``{"module_file", "module_digest", "mount_id",
    "declared_vs_observed_match", "errors"}``.
    """
    try:
        attestation = attest_target_content(
            Path(manifest.epic["runtime_root"]), module_name=module_name
        )
        return {
            "module_file": attestation.module_file,
            "module_digest": attestation.module_digest,
            "mount_id": attestation.mount_id,
            "declared_vs_observed_match": attestation.declared_vs_observed_match,
            "errors": list(attestation.errors),
        }
    except Exception as exc:  # noqa: BLE001 - contract: attest_runtime never raises
        return {
            "module_file": "",
            "module_digest": "",
            "mount_id": "",
            "declared_vs_observed_match": False,
            "errors": [f"attestation_failed:{exc}"],
        }


# ── transitions (immutable: every function returns a NEW manifest) ──────────


def _reconstruct(
    manifest: RuntimeManifest, **overrides: Any
) -> RuntimeManifest:
    """New manifest from *manifest* with *overrides* applied to top-level fields."""
    values: dict[str, Any] = {
        "runtime_id": manifest.runtime_id,
        "schema": manifest.schema,
        "generation": manifest.generation,
        "epic_id": manifest.epic_id,
        "state": manifest.state,
        "owner": manifest.owner,
        "base": manifest.base,
        "epic": manifest.epic,
        "indirection": manifest.indirection,
        "policy": manifest.policy,
        "promotions": manifest.promotions,
        "timestamps": manifest.timestamps,
        "gc_policy": manifest.gc_policy,
        "commands": manifest.commands,
    }
    values.update(overrides)
    return RuntimeManifest(**values)


def advance_generation(
    manifest: RuntimeManifest, new_commit: str, *, reason: str
) -> RuntimeManifest:
    """Return a NEW manifest at ``generation + 1`` pinned to *new_commit*.

    ``epic.expected_head`` and ``indirection.verified_head`` move to
    *new_commit*, ``timestamps.updated`` is stamped, and the PREVIOUS
    generation is retained via ``promotions.append`` — the rollback record::

        {"previous_generation", "previous_commit", "reason", "at"}

    The original manifest is untouched.
    """
    previous_commit = str(manifest.epic.get("expected_head", ""))
    now = _utc_now()
    promotions = list(manifest.promotions) + [
        {
            "previous_generation": manifest.generation,
            "previous_commit": previous_commit,
            "reason": reason,
            "at": now,
        }
    ]
    return _reconstruct(
        manifest,
        generation=manifest.generation + 1,
        epic=dict(manifest.epic, expected_head=new_commit),
        indirection=dict(manifest.indirection, verified_head=new_commit),
        promotions=promotions,
        timestamps=dict(manifest.timestamps, updated=now),
    )


def set_state(manifest: RuntimeManifest, state: str) -> RuntimeManifest:
    """Return a NEW manifest with ``state`` changed to *state*.

    *state* must be ``"active"`` or ``"closed"`` (else :class:`ManifestError`).
    Closing stamps ``timestamps.closed``; reopening leaves the historical
    ``closed`` timestamp in place (it records the last close, never cleared).
    """
    if state not in _VALID_STATES:
        raise ManifestError(
            f"state must be one of {sorted(_VALID_STATES)}, got {state!r}"
        )
    timestamps = dict(manifest.timestamps)
    if state == "closed":
        timestamps["closed"] = _utc_now()
    return _reconstruct(manifest, state=state, timestamps=timestamps)


def append_promotion(
    manifest: RuntimeManifest, record: dict[str, Any]
) -> RuntimeManifest:
    """Return a NEW manifest with *record* appended to ``promotions``."""
    if not isinstance(record, dict):
        raise ManifestError("promotion record must be an object")
    return _reconstruct(manifest, promotions=list(manifest.promotions) + [record])


# ── CLI ─────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    write_p = sub.add_parser("write", help="validate + atomically write <path>")
    write_p.add_argument("path", type=Path)
    write_p.add_argument(
        "--from",
        dest="from_file",
        type=Path,
        help="read manifest JSON from FILE (default: stdin)",
    )
    read_p = sub.add_parser("read", help="load + validate <path>, print JSON")
    read_p.add_argument("path", type=Path)
    attest_p = sub.add_parser(
        "attest", help="attest the runtime named by the manifest at <path>"
    )
    attest_p.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.action == "write":
            if args.from_file is not None:
                raw = Path(args.from_file).read_text(encoding="utf-8")
            else:
                raw = sys.stdin.read()
            data = json.loads(raw)
            manifest = RuntimeManifest.from_dict(data)
            write_manifest(manifest, args.path)
            print(json.dumps(manifest.to_dict(), sort_keys=True))
        elif args.action == "read":
            manifest = load_manifest(args.path)
            print(json.dumps(manifest.to_dict(), sort_keys=True, indent=2))
        elif args.action == "attest":
            manifest = load_manifest(args.path)
            print(json.dumps(attest_runtime(manifest), sort_keys=True, indent=2))
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
