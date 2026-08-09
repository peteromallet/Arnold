#!/usr/bin/env python3
"""Authoritative read-only CL2 admission command.

This is the sole executable entry point that derives the accepted CL2 binding
hash. It is **strictly read-only**: it reads exactly one manifest file and the
four declared artifact paths, calls :func:`verify_cl2_admission`, and on
success prints the accepted ``binding_hash`` to stdout. It performs no writes
of any kind — to disk, to the ledger, or anywhere else — on either success or
failure.

Exit semantics (fail-closed on every invalid state):

* ``0``  — admission accepted; the binding hash is the only stdout content.
* ``2``  — admission rejected: the bundle was reachable but a typed
  :class:`CL2AdmissionError` subclass was raised (missing/hashedrift/malformed
  bundle, untrusted reviewer, expired review, bad signature, drift, etc.).
* ``1``  — usage or manifest error: no manifest supplied, manifest unreadable,
  manifest malformed, or an unexpected internal error.

Every nonzero path writes a single diagnostic line to **stderr** and leaves the
filesystem untouched. No accepted v2 store open or public writer may proceed
without the binding hash this command alone produces.

Manifest format (JSON object)::

    {
      "amended_handoff": {"path": "...", "sha256": "<hex>"},
      "policy_bundle":   {"path": "...", "sha256": "<hex>"},
      "review_receipt":  {"path": "...", "sha256": "<hex>"},
      "reviewer_trust":  {"path": "...", "sha256": "<hex>"},
      "reviewer_fingerprint": "<hex>",
      "target_schema": "cl.handoff.v1",
      "amendment_checksum": "<hex>",
      "policy_revisions": {
        "prompt_revision": "<hex>",
        "implementation_revision": "<hex>",
        "briefing_revision": "<hex>",
        "near_match_policy_revision": "<hex>",
        "false_positive_budget_revision": "<hex>",
        "audit_policy_revision": "<hex>"
      }
    }

Relative artifact ``path`` values resolve against the manifest file's parent
directory so that a reviewed bundle is portable as a single directory. The
command never searches, globs, or invents paths — it opens exactly the four
declared paths plus the manifest.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Resolve the repository root and ensure the local package is importable when
# the script is invoked directly (e.g. ``python3 scripts/check_cl2_admission.py``).
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from arnold.critique_ledger.contract_gate import (  # noqa: E402
    CL2AdmissionError,
    CL2AdmissionInput,
    PolicyRevisions,
    verify_cl2_admission,
)

#: Exit code for admission rejection (typed gate error).
EXIT_ADMISSION_REJECTED = 2
#: Exit code for usage / manifest / unexpected errors.
EXIT_USAGE_ERROR = 1
#: Exit code for success.
EXIT_OK = 0

_REQUIRED_ARTIFACT_KEYS = (
    "amended_handoff",
    "policy_bundle",
    "review_receipt",
    "reviewer_trust",
)
_REQUIRED_META_KEYS = (
    "reviewer_fingerprint",
    "target_schema",
    "amendment_checksum",
    "policy_revisions",
)


def _fail(message: str, code: int = EXIT_USAGE_ERROR) -> int:
    """Write *message* to stderr and return *code* without writing anywhere."""
    print(f"check_cl2_admission: {message}", file=sys.stderr)
    return code


def _require_str(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _resolve_artifact(
    raw: Any, base_dir: Path, label: str
) -> tuple[Path, str]:
    """Parse one ``{"path": ..., "sha256": ...}`` artifact entry.

    Paths resolve against *base_dir* (the manifest's parent directory) when
    relative. Only the four declared artifacts are ever resolved here.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"{label}: artifact entry must be an object")
    raw_path = raw.get("path")
    raw_sha = raw.get("sha256")
    path_str = _require_str(raw_path, f"{label}.path")
    sha = _require_str(raw_sha, f"{label}.sha256")
    path = Path(path_str)
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return path, sha


def _build_admission(
    manifest: dict[str, Any], manifest_path: Path
) -> CL2AdmissionInput:
    """Construct the closed :class:`CL2AdmissionInput` from a manifest.

    Resolves **only** the four declared artifact paths against the manifest's
    parent directory. No searching, no fallbacks, no extra reads.
    """
    missing_top = [
        k for k in (*_REQUIRED_ARTIFACT_KEYS, *_REQUIRED_META_KEYS)
        if k not in manifest
    ]
    if missing_top:
        raise ValueError(
            "manifest missing required keys: " + ", ".join(sorted(missing_top))
        )

    base_dir = manifest_path.resolve().parent
    kwargs: dict[str, Any] = {}
    for key in _REQUIRED_ARTIFACT_KEYS:
        path, sha = _resolve_artifact(manifest[key], base_dir, key)
        kwargs[f"{key}_path"] = path
        kwargs[f"{key}_sha256"] = sha

    kwargs["reviewer_fingerprint"] = _require_str(
        manifest["reviewer_fingerprint"], "reviewer_fingerprint"
    )
    kwargs["target_schema"] = _require_str(
        manifest["target_schema"], "target_schema"
    )
    kwargs["amendment_checksum"] = _require_str(
        manifest["amendment_checksum"], "amendment_checksum"
    )
    policy_raw = manifest["policy_revisions"]
    if not isinstance(policy_raw, dict):
        raise ValueError("policy_revisions must be an object")
    kwargs["policy_revisions"] = PolicyRevisions.from_dict(policy_raw)
    return CL2AdmissionInput(**kwargs)


def run(argv: list[str]) -> int:
    """Command entry point. Returns a process exit code; never raises."""
    if len(argv) != 2 or argv[1] in ("--help", "-h"):
        _fail(
            "usage: check_cl2_admission.py <manifest.json> "
            "(prints the accepted binding hash on success)",
            EXIT_USAGE_ERROR,
        )
        return EXIT_USAGE_ERROR

    manifest_path = Path(argv[1])
    if not manifest_path.is_file():
        _fail(f"manifest not found: {manifest_path}", EXIT_USAGE_ERROR)
        return EXIT_USAGE_ERROR

    # Read the manifest (the only non-artifact file the command opens).
    try:
        text = manifest_path.read_text(encoding="utf-8")
        manifest = json.loads(text)
    except (OSError, ValueError) as exc:
        _fail(f"cannot parse manifest {manifest_path}: {exc}", EXIT_USAGE_ERROR)
        return EXIT_USAGE_ERROR
    if not isinstance(manifest, dict):
        _fail(
            f"manifest must be a JSON object, got {type(manifest).__name__}",
            EXIT_USAGE_ERROR,
        )
        return EXIT_USAGE_ERROR

    try:
        admission = _build_admission(manifest, manifest_path)
    except ValueError as exc:
        _fail(f"invalid manifest: {exc}", EXIT_USAGE_ERROR)
        return EXIT_USAGE_ERROR
    except Exception as exc:  # pragma: no cover - defensive fail-closed
        _fail(f"invalid manifest: {exc}", EXIT_USAGE_ERROR)
        return EXIT_USAGE_ERROR

    # Delegate all admission semantics to the strict, read-only gate.
    try:
        binding = verify_cl2_admission(admission)
    except CL2AdmissionError as exc:
        # Admission rejected — fail closed with a typed reason on stderr.
        _fail(
            f"admission rejected ({type(exc).__name__}): {exc}",
            EXIT_ADMISSION_REJECTED,
        )
        return EXIT_ADMISSION_REJECTED
    except Exception as exc:  # pragma: no cover - defensive fail-closed
        _fail(f"unexpected error during verification: {exc}", EXIT_USAGE_ERROR)
        return EXIT_USAGE_ERROR

    # Success — the binding hash is the ONLY thing written to stdout.
    print(binding.binding_hash)
    return EXIT_OK


def main() -> None:
    sys.exit(run(sys.argv))


if __name__ == "__main__":
    main()
