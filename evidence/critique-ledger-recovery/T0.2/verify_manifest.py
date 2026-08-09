#!/usr/bin/env python3
"""Independent verifier for the T0.2 content-addressed manifest."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "manifest.json"
OBJECT_ROOT = ROOT / "objects" / "sha256"
RECEIPT = ROOT / "verification-receipt.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    manifest_bytes = MANIFEST.read_bytes()
    manifest = json.loads(manifest_bytes)
    claims = manifest.get("claims", [])
    failures: list[str] = []
    verified = 0
    total_bytes = 0
    referenced: set[Path] = set()
    for claim in claims:
        object_rel = claim.get("object_path")
        expected = claim.get("sha256")
        if not object_rel:
            continue
        object_path = (ROOT / object_rel).resolve()
        if ROOT not in object_path.parents:
            failures.append(f"object escapes evidence root: {object_rel}")
            continue
        if not object_path.is_file():
            failures.append(f"missing object: {object_rel}")
            continue
        actual = sha256(object_path)
        referenced.add(object_path)
        total_bytes += object_path.stat().st_size
        if actual != expected:
            failures.append(f"digest mismatch: {object_rel}: expected {expected}, got {actual}")
        else:
            verified += 1

    unexpected: list[str] = []
    if OBJECT_ROOT.exists():
        for path in sorted(p for p in OBJECT_ROOT.glob("*/*") if p.is_file()):
            if path not in referenced:
                unexpected.append(str(path.relative_to(ROOT)))
    if unexpected:
        failures.append("unreferenced objects: " + ", ".join(unexpected[:20]))

    receipt = {
        "schema": "t0.2.verification-receipt.v1",
        "verified_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "clock_basis": "local UTC wall clock",
        "verifier": "verify_manifest.py",
        "verifier_path": str(Path(__file__).resolve()),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "manifest_byte_size": len(manifest_bytes),
        "claims_with_objects": len(referenced),
        "objects_verified": verified,
        "object_bytes_counted_with_duplicate_references": total_bytes,
        "unexpected_objects": unexpected,
        "failures": failures,
        "result": "PASS" if not failures else "FAIL",
        "formal_t02_completion_criterion": bool(not failures and manifest.get("verification", {}).get("formal_completion_criterion")),
    }
    RECEIPT.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
