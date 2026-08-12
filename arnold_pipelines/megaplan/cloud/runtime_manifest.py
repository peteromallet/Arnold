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
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan.cloud.shadow_attestation import attest_target_content

MANIFEST_SCHEMA_VERSION = "1"

# Canonical manifest filename inside a bootstrap *directory*.
MANIFEST_FILENAME = "runtime-manifest.json"

# Marker for a NON-AUTHORITATIVE active pointer (G2 correction 1 + second
# re-run): a manifest pointer file at the bootstrap path whose JSON carries
# ``"compatibility_only": true`` is compatibility telemetry ONLY — every
# resolver treats it as ABSENT for admission (permit check applies; block
# without a valid permit). It can never select a runtime. The marker is an
# EXPLICIT preserved manifest field (schema stays "1", optional, default
# False) so no read/write transition can strip it (G2 second re-run);
# resolvers still check it explicitly (:func:`is_compatibility_only_pointer`)
# because it is per-pointer telemetry, not part of a per-slug authoritative
# manifest.
COMPATIBILITY_ONLY_KEY = "compatibility_only"

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

# Public aliases for the canonical required-key sets.  cloud.cli generates
# the stdlib-only, fail-closed shell read of the pinned runtime manifest
# from these (G6 round-2 finding 2), so the shell gate can never drift from
# the canonical schema definition.
TOP_LEVEL_REQUIRED = _TOP_LEVEL_REQUIRED
EPIC_REQUIRED = _EPIC_REQUIRED
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

    ``deviations`` is an OPTIONAL list of expiring exception records (typed
    deviation/fallback events, e.g. an ``allow_manifestless`` permit). It is
    preserved verbatim by every read/write transition and serialized on disk;
    old manifests (schema ``"1"`` without the key) load with ``[]``. Expired
    records STAY loadable — expiry is enforced at admission/addition
    (:func:`validate_deviation`, :func:`has_valid_allow_manifestless_permit`),
    never at load time.

    ``compatibility_only`` is an OPTIONAL boolean demotion marker for
    NON-AUTHORITATIVE pointers (G2 correction 1 + second re-run): a manifest
    with it ``True`` is compatibility telemetry ONLY and can never select a
    runtime — every resolver treats it as ABSENT for admission. Per-slug
    authoritative manifests leave it ``False``. It is preserved verbatim by
    every read/write transition (:func:`_reconstruct`) and serialized on
    disk; old manifests (schema ``"1"`` without the key) load with ``False``.
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
    deviations: list[dict[str, Any]] = field(default_factory=list)
    compatibility_only: bool = False

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
        if not isinstance(self.deviations, list) or not all(
            isinstance(record, dict) for record in self.deviations
        ):
            raise ManifestError("deviations must be a list of objects")
        if not isinstance(self.compatibility_only, bool):
            raise ManifestError("compatibility_only must be a boolean")

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
        values: dict[str, Any] = {key: data[key] for key in _TOP_LEVEL_REQUIRED}
        # deviations is OPTIONAL: old manifests (schema "1") load with [].
        values["deviations"] = data.get("deviations", [])
        # compatibility_only is OPTIONAL: old manifests (schema "1") load
        # with False (authoritative); only a pointer explicitly marked True is
        # non-authoritative telemetry. As a real field it is preserved by
        # to_dict/_reconstruct — no transition can strip the marker (G2
        # second re-run).
        values[COMPATIBILITY_ONLY_KEY] = data.get(COMPATIBILITY_ONLY_KEY, False)
        return cls(**values)

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


def _write_payload(
    manifest: RuntimeManifest, target: Path, *, pointer_write: bool = False
) -> dict[str, Any]:
    """Serialized payload for writing *manifest* to *target*, enforcing the
    demotion invariant (G2 second re-run): a demoted (``compatibility_only``)
    pointer can never be re-admitted authoritative by ANY writer. This is the
    ONE preservation point — both :func:`write_manifest` (the lowest-level
    writer) and :func:`write_active_pointer` route their payloads through it:

    - Generic write (``pointer_write=False``): only the ACTIVE-generation
      pointer path (:func:`active_manifest_path`) is protected — when *target*
      IS that path and the file already there is a ``compatibility_only``
      pointer, the marker is forced ON even for an authoritative manifest.
    - Pointer write (``pointer_write=True``): every target is a pointer, so
      any path that already holds a ``compatibility_only`` pointer stays
      demoted.

    Any other target (per-slug manifests, retention copies) is written exactly
    as *manifest* declares.
    """
    payload = manifest.to_dict()
    pointer_target = pointer_write or (
        target == active_manifest_path().expanduser().resolve(strict=False)
    )
    if pointer_target and is_compatibility_only_pointer(target):
        payload[COMPATIBILITY_ONLY_KEY] = True
    return payload


def write_manifest(manifest: RuntimeManifest, path: Path) -> None:
    """Serialize *manifest* to *path* atomically under an exclusive flock.

    A sibling ``<name>.lock`` file is created (and kept) next to *path*;
    writers take ``flock(LOCK_EX)`` around the tmp+rename so concurrent
    writers serialize and readers never observe a partial file.

    Demotion invariant (G2 second re-run): when *path* IS the active-
    generation pointer path and the existing file there is a
    ``compatibility_only`` pointer, the written payload is forced to keep the
    marker (see :func:`_write_payload`) — a generic authoritative write can
    never re-admit a demoted pointer.
    """
    target = Path(path).expanduser().resolve(strict=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_path = target.with_name(target.name + ".lock")
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        _atomic_write(target, _write_payload(manifest, target))
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


def is_compatibility_only_pointer(path: Path) -> bool:
    """True iff *path* is a NON-AUTHORITATIVE ``compatibility_only`` pointer.

    A pointer file at the bootstrap path whose JSON carries
    ``"compatibility_only": true`` at the top level is compatibility telemetry
    (legacy launchers may still read it) and can NEVER select a runtime: every
    resolver treats it as ABSENT for admission (G2 correction 1). The marker
    must be checked explicitly because :func:`load_manifest` ignores unknown
    keys by design. Absent, unreadable, or non-JSON files return False — they
    fail on their own as absent/invalid rather than being compatibility
    telemetry.
    """
    target = Path(path).expanduser()
    if not target.is_file():
        return False
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(payload, dict) and payload.get(COMPATIBILITY_ONLY_KEY) is True


def manifest_present(path: Path) -> bool:
    """True iff *path* resolves to a present, valid, AUTHORITATIVE manifest.

    Admission probe: a ``compatibility_only`` pointer is treated as ABSENT
    (never authoritative), and a missing, corrupt, or schema-invalid file is
    absent too. Returns False on every non-admissible state — callers that
    need to distinguish "absent-for-admission" from "present-but-invalid" can
    combine it with :func:`is_compatibility_only_pointer` and
    :func:`load_manifest`.
    """
    if is_compatibility_only_pointer(path):
        return False
    try:
        load_manifest(path)
    except ManifestError:
        return False
    return True


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


def _load_authoritative(path: Path) -> RuntimeManifest:
    """Load *path* as the runtime manifest, REFUSING a ``compatibility_only``
    pointer.

    A ``compatibility_only`` pointer is non-authoritative telemetry (G2
    correction 1): the resolver treats it as ABSENT/not-found (raises
    :class:`ManifestError`) so it can never select a runtime — admission falls
    through to the permit check and blocks without a valid permit.
    """
    if is_compatibility_only_pointer(path):
        raise ManifestError(
            f"bootstrap target {path} is a compatibility_only pointer; "
            "non-authoritative — refusing to select a runtime from it"
        )
    return load_manifest(path)


def bootstrap_manifest(bootstrap_path: Path) -> RuntimeManifest:
    """Resolve the active runtime manifest from ONE stable bootstrap path.

    Bootstrap semantics (in order):

    1. Missing path -> :class:`ManifestError`.
    2. Directory -> load ``<dir>/runtime-manifest.json``.
    3. File ending in ``.json`` -> loaded directly as a manifest.
    4. Any other file is a POINTER file: the first non-empty, non-comment
       line names the manifest (relative to the pointer file's parent). If
       that target is a directory, ``<target>/runtime-manifest.json`` is used.

    A ``compatibility_only`` pointer at any resolution step is NON-AUTHORITATIVE
    telemetry (G2 correction 1): it is treated as ABSENT — :class:`ManifestError`
    is raised, so it can never select a runtime.

    This is the single stable entry point every launcher uses post-bootstrap;
    nothing else may locate the runtime manifest.
    """
    bootstrap = Path(bootstrap_path).expanduser()
    if not bootstrap.exists():
        raise ManifestError(f"bootstrap path does not exist: {bootstrap}")
    if bootstrap.is_dir():
        return _load_authoritative(bootstrap / MANIFEST_FILENAME)
    if bootstrap.name.endswith(".json"):
        return _load_authoritative(bootstrap)
    target = Path(_read_pointer(bootstrap))
    if not target.is_absolute():
        target = bootstrap.parent / target
    if target.is_dir():
        target = target / MANIFEST_FILENAME
    if not target.exists():
        raise ManifestError(f"bootstrap pointer target does not exist: {target}")
    return _load_authoritative(target)


# ── active-generation pointer ───────────────────────────────────────────────


def active_manifest_path() -> Path:
    """Stable path of the active-generation pointer.

    The canonical bootstrap path is ``/workspace/.megaplan/runtime-manifest.json``;
    env ``ARNOLD_RUNTIME_MANIFEST`` overrides it. The file AT this path IS the
    active generation — it holds a full manifest JSON (not a sidecar pointer
    file), so ``bootstrap_manifest(active_manifest_path())`` resolves it
    directly. One active pointer, one authoritative writer (the wrapper that
    performs the atomic switch: runtime-create at creation, promote on
    advancement, close on closing).
    """
    env_path = os.environ.get("ARNOLD_RUNTIME_MANIFEST")
    if env_path:
        return Path(env_path).expanduser()
    return Path("/workspace/.megaplan") / MANIFEST_FILENAME


def _retain_previous_generation(pointer: Path, manifest: RuntimeManifest) -> None:
    """Retain the pointer's current manifest before a generation switch.

    Called with the pointer's exclusive flock already held. When *pointer*
    holds a manifest of a strictly EARLIER generation than *manifest*, that
    manifest is written to ``<pointer>.previous-<generation>.json`` (the
    rollback record) BEFORE the pointer moves — a crash between the two writes
    leaves the pointer on the old generation with a harmless duplicate
    retention copy. An existing-but-invalid pointer is REFUSED (fail-closed)
    rather than silently overwritten.
    """
    if not pointer.exists():
        return
    try:
        previous = load_manifest(pointer)
    except ManifestError as exc:
        raise ManifestError(
            f"active pointer {pointer} holds an invalid manifest; refusing to "
            f"overwrite it (fail-closed): {exc}"
        ) from exc
    if previous.generation < manifest.generation:
        retention = Path(str(pointer) + f".previous-{previous.generation}.json")
        _atomic_write(retention, previous.to_dict())


def write_active_pointer(manifest: RuntimeManifest, path: Path | None = None) -> Path:
    """Atomically switch the active-generation pointer to *manifest*.

    The pointer is the manifest file AT the stable bootstrap path (see
    :func:`active_manifest_path`) — the file itself IS the active generation.
    Under an exclusive flock on a sibling ``<name>.lock``: the previous
    generation (when the pointer already holds an earlier one) is retained at
    ``<path>.previous-<N>.json`` for rollback, then *manifest* is written to
    *path* via atomic tmp+rename. Returns the pointer path.

    The pointer's ``compatibility_only`` demotion is DURABLE (G2 second
    re-run): once the pointer holds a ``compatibility_only`` manifest (as
    ``arnold-runtime-create`` always writes it), EVERY subsequent pointer
    write keeps the marker, so ``advance_generation`` (arnold-promote) and
    pointer ``set_state`` (arnold-close) can never re-admit the global
    pointer as authoritative. Preservation lives in the single shared
    payload builder :func:`_write_payload` — the same one the generic
    :func:`write_manifest` uses, so a demoted pointer can never be re-admitted
    authoritative by ANY writer (G2 final fix).
    """
    pointer = Path(path) if path is not None else active_manifest_path()
    pointer = pointer.expanduser().resolve(strict=False)
    pointer.parent.mkdir(parents=True, exist_ok=True)
    lock_path = pointer.with_name(pointer.name + ".lock")
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        _retain_previous_generation(pointer, manifest)
        _atomic_write(pointer, _write_payload(manifest, pointer, pointer_write=True))
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)
    return pointer


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
        "deviations": manifest.deviations,
        "compatibility_only": manifest.compatibility_only,
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


# ── deviations (expiring exception records) ─────────────────────────────────


_DEVIATION_REQUIRED = (
    "kind",
    "id",
    "issued_at",
    "expires_at",
    "actor",
    "reason",
    "evidence",
    "chain_digest",
)
_DEVIATION_MAX_LIFETIME = timedelta(hours=24)
_ALLOW_MANIFESTLESS_KIND = "allow_manifestless"


def _parse_utc_iso(value: Any, label: str) -> datetime:
    """Parse *value* as a UTC ISO8601 timestamp; raise :class:`ManifestError`
    on anything else (non-string, unparsable, naive, or non-UTC offset)."""
    if not isinstance(value, str) or not value:
        raise ManifestError(f"deviation {label} must be a non-empty ISO8601 string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ManifestError(f"deviation {label} is not ISO8601: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ManifestError(f"deviation {label} must be UTC: {value!r}")
    return parsed


def validate_deviation(record: Any, *, now: str | None = None) -> dict[str, Any]:
    """Validate a deviation/permit record for ADDITION or ADMISSION.

    Rejects (raises :class:`ManifestError`): non-object records; missing or
    empty ``kind``/``id``/``issued_at``/``expires_at``/``actor``/``reason``/
    ``evidence``/``chain_digest``; non-UTC ``issued_at``/``expires_at``;
    lifetimes outside ``0 < expires_at - issued_at <= 24h``; and records
    already expired at *now* (default: UTC now). ``evidence`` must be a list
    of strings. Unknown keys (e.g. a ``revoked_at`` tombstone) are tolerated
    and preserved — the record is returned unchanged on success.

    Expiry is enforced at call time only: an expired record is REFUSED here
    but stays loadable inside a manifest (:func:`load_manifest` never checks
    the clock; admission uses :func:`has_valid_allow_manifestless_permit`).
    """
    if not isinstance(record, dict):
        raise ManifestError("deviation record must be an object")
    missing = [key for key in _DEVIATION_REQUIRED if key not in record]
    if missing:
        raise ManifestError(
            f"deviation missing required fields: {', '.join(missing)}"
        )
    for field_name in ("kind", "id", "actor", "reason", "chain_digest"):
        if not isinstance(record[field_name], str) or not record[field_name]:
            raise ManifestError(
                f"deviation {field_name} must be a non-empty string"
            )
    issued = _parse_utc_iso(record["issued_at"], "issued_at")
    expires = _parse_utc_iso(record["expires_at"], "expires_at")
    evidence = record["evidence"]
    if not isinstance(evidence, list) or not all(
        isinstance(item, str) for item in evidence
    ):
        raise ManifestError("deviation evidence must be a list of strings")
    lifetime = expires - issued
    if lifetime <= timedelta(0) or lifetime > _DEVIATION_MAX_LIFETIME:
        raise ManifestError(
            f"deviation lifetime must be within (0, 24h], got {lifetime}"
        )
    now_dt = _parse_utc_iso(now, "now") if now is not None else datetime.now(timezone.utc)
    if expires <= now_dt:
        raise ManifestError(f"deviation expired at {record['expires_at']}")
    return record


def has_valid_allow_manifestless_permit(manifest: RuntimeManifest) -> bool:
    """True iff *manifest* carries a currently-valid ``allow_manifestless`` permit.

    Admission-time check for manifest-less operation: the manifest must hold a
    deviation with ``kind == "allow_manifestless"`` that is structurally valid
    AND unexpired right now. A revoked permit (a ``revoked_at`` tombstone) or
    an expired one NEVER admits; invalid records are skipped, so one bad record
    cannot admit anything (fail-closed).
    """
    for record in manifest.deviations:
        if record.get("kind") != _ALLOW_MANIFESTLESS_KIND:
            continue
        if record.get("revoked_at"):
            continue
        try:
            validate_deviation(record)
        except ManifestError:
            continue
        return True
    return False


def add_deviation(
    manifest: RuntimeManifest, record: dict[str, Any]
) -> RuntimeManifest:
    """Return a NEW manifest with validated *record* appended to ``deviations``.

    The record is validated (structure, lifetime, current-unexpired) BEFORE
    the append — an invalid record raises :class:`ManifestError` and leaves
    *manifest* untouched. Immutable: the original manifest is never modified.
    """
    validate_deviation(record)
    return _reconstruct(manifest, deviations=list(manifest.deviations) + [record])


def _parse_json_record(arg: str) -> dict[str, Any]:
    """Parse the ``append_promotion`` / ``add_deviation`` CLI *record* argument.

    Accepted forms: inline JSON (``{"from_sha": …}``), ``@FILE`` (read the
    record from FILE), or a bare path to an existing JSON file. Returns the
    parsed record, which MUST be a JSON object.
    """
    if arg.startswith("@"):
        source = Path(arg[1:])
        try:
            raw = source.read_text(encoding="utf-8")
        except OSError as exc:
            raise ManifestError(
                f"cannot read promotion record file {source}: {exc}"
            ) from exc
    else:
        candidate = Path(arg)
        try:
            raw = candidate.read_text(encoding="utf-8")
        except OSError:
            raw = arg
    try:
        record = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"promotion record is not valid JSON: {exc}") from exc
    if not isinstance(record, dict):
        raise ManifestError("promotion record must be a JSON object")
    return record


def _write_manifest_or_pointer(manifest: RuntimeManifest, path: Path) -> None:
    """Write *manifest* to *path*, through the active pointer when *path* IS
    the active-generation pointer (state transitions written to the pointer
    keep the file AT the stable path the active generation); otherwise a
    plain per-runtime manifest write."""
    if Path(path).expanduser().resolve(strict=False) == active_manifest_path().expanduser().resolve(strict=False):
        write_active_pointer(manifest, path)
    else:
        write_manifest(manifest, path)


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
    set_p = sub.add_parser(
        "set_state",
        help="set <state> on the manifest at <path> and write it atomically",
    )
    set_p.add_argument("path", type=Path)
    set_p.add_argument("state", choices=sorted(_VALID_STATES))
    prom_p = sub.add_parser(
        "append_promotion",
        help="append a promotion record to the manifest at <path> and write it atomically",
    )
    prom_p.add_argument("path", type=Path)
    prom_p.add_argument(
        "record",
        help="promotion record as inline JSON, or @FILE to read it from FILE",
    )
    dev_p = sub.add_parser(
        "add_deviation",
        help="validate + append a deviation record to the manifest at <path> and write it atomically",
    )
    dev_p.add_argument("path", type=Path)
    dev_p.add_argument(
        "record",
        help="deviation record as inline JSON, or @FILE to read it from FILE",
    )
    adv_p = sub.add_parser(
        "advance_generation",
        help="advance the generation at <path> AND atomically switch the active-generation pointer",
    )
    adv_p.add_argument("path", type=Path)
    adv_p.add_argument(
        "new_commit", help="expected_head/verified_head of the new generation"
    )
    adv_p.add_argument(
        "--reason", required=True, help="reason recorded in the rollback record"
    )
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
        elif args.action == "set_state":
            manifest = load_manifest(args.path)
            updated = set_state(manifest, args.state)
            _write_manifest_or_pointer(updated, args.path)
            print(json.dumps(updated.to_dict(), sort_keys=True))
        elif args.action == "append_promotion":
            manifest = load_manifest(args.path)
            record = _parse_json_record(args.record)
            updated = append_promotion(manifest, record)
            write_manifest(updated, args.path)
            print(json.dumps(updated.to_dict(), sort_keys=True))
        elif args.action == "add_deviation":
            manifest = load_manifest(args.path)
            record = _parse_json_record(args.record)
            updated = add_deviation(manifest, record)
            write_manifest(updated, args.path)
            print(json.dumps(updated.to_dict(), sort_keys=True))
        elif args.action == "advance_generation":
            manifest = load_manifest(args.path)
            advanced = advance_generation(manifest, args.new_commit, reason=args.reason)
            pointer = active_manifest_path()
            if Path(args.path).expanduser().resolve(strict=False) == pointer.expanduser().resolve(strict=False):
                # The caller passed the pointer itself — the switch IS the write.
                write_active_pointer(advanced, pointer)
            else:
                # Pointer switch FIRST (atomic, retains the previous generation
                # for rollback), then the per-slug manifest: a retry after a
                # mid-write failure re-reads the pre-advance slug and lands on
                # the same generation + commit (idempotent).
                write_active_pointer(advanced, pointer)
                write_manifest(advanced, args.path)
            print(json.dumps(advanced.to_dict(), sort_keys=True))
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
