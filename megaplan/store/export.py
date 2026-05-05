"""Byte-oriented epic export collection."""

from __future__ import annotations

import gzip
import hashlib
import io
import tarfile
from pathlib import Path
from typing import Any

from megaplan.store.snapshot import canonical_json_dumps


def _json_bytes(value: Any) -> bytes:
    return (canonical_json_dumps(value) + "\n").encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _model_json(model: Any) -> dict[str, Any]:
    return model.model_dump(mode="json")


def collect_epic_export(store: Any, epic_id: str, *, allow_missing_blobs: bool = False) -> dict[str, Any]:
    """Collect deterministic row/artifact/blob bytes without mutating store state."""
    epic = store.load_epic(epic_id)
    if epic is None:
        raise FileNotFoundError(epic_id)
    source = store._route_for_epic(epic_id)
    entities = store._migration_entities(source, epic_id)
    files: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    rows = {
        "epic": _model_json(entities["epic"]),
        "body": store.load_body(epic_id),
        "checklist_items": [_model_json(row) for row in entities["checklist_items"]],
        "sprints": [_model_json(row) for row in entities["sprints"]],
        "sprint_items": [_model_json(row) for row in entities["sprint_items"]],
        "plans": [_model_json(row) for row in entities["plans"]],
        "images": [_model_json(row) for row in entities["images"]],
        "second_opinions": [_model_json(row) for row in entities["second_opinions"]],
        "feedback": [_model_json(row) for row in entities["feedback"]],
        "code_artifacts": [_model_json(row) for row in entities["code_artifacts"]],
        "epic_events": [_model_json(row) for row in entities["epic_events"]],
    }
    for name, value in sorted(rows.items()):
        data = _json_bytes(value)
        files.append({"path": f"rows/{name}.json", "kind": "row_json", "bytes": data, "size_bytes": len(data), "sha256": _sha(data)})

    for plan_id, artifacts in sorted(entities["plan_artifacts"].items()):
        for ref, data in sorted(artifacts, key=lambda item: item[0].name):
            files.append({
                "path": f"plan_artifacts/{plan_id}/{ref.name}",
                "kind": "plan_artifact",
                "plan_id": plan_id,
                "artifact_name": ref.name,
                "bytes": data,
                "size_bytes": len(data),
                "sha256": _sha(data),
            })

    blob_store = getattr(source, "blobs", None)
    for image in sorted(entities["images"], key=lambda row: row.id):
        if not image.blob_id:
            continue
        blob_meta = {
            "image_id": image.id,
            "blob_id": image.blob_id,
            "blob_backend": image.blob_backend,
            "declared_sha256": image.blob_sha256,
            "declared_size_bytes": image.blob_size_bytes,
            "content_type": image.content_type,
        }
        if blob_store is None:
            errors.append({**blob_meta, "error": "blob_store_unavailable"})
            continue
        try:
            data = blob_store.get(image.blob_id)
            stat = blob_store.stat(image.blob_id)
        except Exception as exc:  # deliberately captured into manifest errors
            entry = {**blob_meta, "error": type(exc).__name__, "message": str(exc)}
            (warnings if allow_missing_blobs else errors).append(entry)
            continue
        digest = _sha(data)
        if image.blob_sha256 and image.blob_sha256.removeprefix("sha256:") != digest:
            entry = {**blob_meta, "error": "sha256_mismatch", "actual_sha256": digest}
            (warnings if allow_missing_blobs else errors).append(entry)
            if not allow_missing_blobs:
                continue
        meta_bytes = _json_bytes({**blob_meta, "stat": stat.model_dump(mode="json") if stat else None, "sha256": digest, "size_bytes": len(data)})
        files.append({"path": f"blobs/{image.blob_id}/meta.json", "kind": "blob_metadata", "bytes": meta_bytes, "size_bytes": len(meta_bytes), "sha256": _sha(meta_bytes)})
        files.append({"path": f"blobs/{image.blob_id}/payload.bin", "kind": "blob_payload", "bytes": data, "size_bytes": len(data), "sha256": digest})

    manifest_entries = [
        {key: value for key, value in file.items() if key != "bytes"}
        for file in sorted(files, key=lambda item: item["path"])
    ]
    manifest = {
        "format": "megaplan-epic-export-v1",
        "epic_id": epic_id,
        "file_count": len(files),
        "files": manifest_entries,
        "warnings": warnings,
        "errors": errors,
    }
    return {
        "epic_id": epic_id,
        "files": sorted(files, key=lambda item: item["path"]),
        "manifest": manifest,
        "warnings": warnings,
        "errors": errors,
    }


def write_epic_export_tar(collected: dict[str, Any], output: str | Path, *, gzip_output: bool = False) -> dict[str, Any]:
    output_path = Path(output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    members = list(collected["files"])
    manifest_bytes = _json_bytes(collected["manifest"])
    members.append({
        "path": "manifest.json",
        "kind": "manifest",
        "bytes": manifest_bytes,
        "size_bytes": len(manifest_bytes),
        "sha256": _sha(manifest_bytes),
    })
    fileobj: Any
    closer: Any
    raw = output_path.open("wb")
    if gzip_output:
        fileobj = gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0)
        closer = fileobj
    else:
        fileobj = raw
        closer = raw
    try:
        with tarfile.open(fileobj=fileobj, mode="w") as tar:
            for member in sorted(members, key=lambda item: item["path"]):
                data = member["bytes"]
                info = tarfile.TarInfo(member["path"])
                info.size = len(data)
                info.mtime = 0
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                info.mode = 0o644
                tar.addfile(info, io.BytesIO(data))
    finally:
        closer.close()
        if closer is not raw:
            raw.close()
    payload = output_path.read_bytes()
    return {
        "path": str(output_path),
        "size_bytes": len(payload),
        "sha256": _sha(payload),
        "gzip": gzip_output,
        "member_count": len(members),
    }
