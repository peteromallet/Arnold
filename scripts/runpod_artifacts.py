"""Artifact-format readers for vibecomfy RunPod runs.

These functions interpret the artifact archive produced by a RunPod run
and generate manifests, reports, and structured summaries.  They are
vibecomfy-specific — they understand vibecomfy's output conventions
(prompt-ids, watchdog JSON, metadata.json, corpus_matrix paths) and
are intentionally kept OUT of runpod-lifecycle.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REMOTE_ROOT = "/workspace/vibecomfy"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _sha256(path: Path) -> str | None:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _load_watchdog_json(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start < 0:
            return None
        try:
            return json.loads(text[start:])
        except json.JSONDecodeError:
            return None


def _extract_prompt_id(value: Any) -> str | None:
    if isinstance(value, dict):
        direct = value.get("prompt_id")
        if isinstance(direct, str):
            return direct
        for item in value.values():
            found = _extract_prompt_id(item)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _extract_prompt_id(item)
            if found:
                return found
    if isinstance(value, str):
        match = re.search(r"""(?:prompt_id['\"]?\s*[:=]\s*['\"]?)([A-Za-z0-9_.:-]+)""", value)
        if match:
            return match.group(1)
    return None


def _parse_detached_exit(stdout: str) -> int | None:
    lines = stdout.splitlines()
    for index, line in enumerate(lines):
        if line == "--- EXIT ---" and index + 1 < len(lines):
            value = lines[index + 1].strip()
            if value.isdigit():
                return int(value)
    return None


# ---------------------------------------------------------------------------
# Artifact root
# ---------------------------------------------------------------------------

def _new_artifact_root() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = ROOT / "out" / "runpod_artifacts" / stamp
    if not root.exists():
        return root
    suffix = 1
    while True:
        candidate = ROOT / "out" / "runpod_artifacts" / f"{stamp}-{suffix}"
        if not candidate.exists():
            return candidate
        suffix += 1


# ---------------------------------------------------------------------------
# TSV parsing
# ---------------------------------------------------------------------------

def _parse_tsv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            if not reader.fieldnames:
                return []
            rows: list[dict[str, str]] = []
            for row in reader:
                rows.append({str(key): "" if value is None else value for key, value in row.items() if key is not None})
            return rows
    except OSError:
        return []


# ---------------------------------------------------------------------------
# Image info
# ---------------------------------------------------------------------------

def _png_info(path: Path) -> dict[str, Any] | None:
    if path.suffix.lower() != ".png":
        return None
    try:
        with path.open("rb") as handle:
            header = handle.read(24)
    except OSError:
        return None
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", header[16:24])
    return {
        "width": width,
        "height": height,
        "format": "PNG",
        "mode": None,
    }


def _image_info(path: Path) -> dict[str, Any] | None:
    try:
        from PIL import Image
    except Exception:
        return _png_info(path)
    try:
        with Image.open(path) as image:
            return {
                "width": image.width,
                "height": image.height,
                "format": image.format,
                "mode": image.mode,
            }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# File record
# ---------------------------------------------------------------------------

def _file_record(path: Path, root: Path) -> dict[str, Any] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return {
        "path": _display_path(path),
        "relative_path": path.relative_to(root).as_posix(),
        "bytes": stat.st_size,
        "extension": path.suffix.lower(),
        "sha256": _sha256(path),
    }


# ---------------------------------------------------------------------------
# Collectors
# ---------------------------------------------------------------------------

def _count_failures(rows: list[dict[str, str]]) -> int:
    passing = {"ok", "pass", "passed", "success", "succeeded"}
    failures = 0
    for row in rows:
        status = (row.get("status") or row.get("result") or "").strip().lower()
        if status and status not in passing:
            failures += 1
    return failures


def _collect_outputs(local_root: Path) -> list[dict[str, Any]]:
    output_root = local_root / "output"
    if not output_root.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(item for item in output_root.rglob("*") if item.is_file()):
        record = _file_record(path, local_root)
        if record is None:
            continue
        record["output_relative_path"] = path.relative_to(output_root).as_posix()
        info = _image_info(path)
        if info is not None:
            record["image"] = info
        records.append(record)
    return records


def _collect_run_metadata(local_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    runs_root = local_root / "out" / "runs"
    if not runs_root.exists():
        return records, warnings
    for path in sorted(runs_root.glob("*/metadata.json")):
        data = _load_json(path)
        if not isinstance(data, dict):
            warnings.append(f"invalid run metadata: {_display_path(path)}")
            continue
        queued = data.get("queued")
        prompt_id = _extract_prompt_id(queued)
        outputs = data.get("outputs") if isinstance(data.get("outputs"), list) else []
        records.append(
            {
                "path": _display_path(path),
                "relative_path": path.relative_to(local_root).as_posix(),
                "run_id": data.get("run_id") or path.parent.name,
                "workflow_id": data.get("workflow_id"),
                "runtime": data.get("runtime"),
                "prompt_id": prompt_id,
                "outputs": outputs,
                "workflow_hash": data.get("workflow_hash"),
                "git_sha": data.get("git_sha"),
                "metadata": data,
            }
        )
    return records, warnings


def _collect_watchdogs(
    local_root: Path,
    run_metadata: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    outputs_by_run = {
        str(record.get("run_id")): bool(record.get("outputs"))
        for record in run_metadata
        if record.get("run_id")
    }
    runs_root = local_root / "out" / "runs"
    if not runs_root.exists():
        return records, warnings
    for path in sorted(runs_root.glob("*/watchdog.json")):
        data = _load_watchdog_json(path)
        if not isinstance(data, dict):
            warnings.append(f"invalid watchdog report: {_display_path(path)}")
            continue
        state = data.get("state") if isinstance(data.get("state"), dict) else {}
        run_id = path.parent.name
        diagnosis = data.get("diagnosis")
        stop_reason = state.get("stop_reason")
        record = {
            "path": _display_path(path),
            "relative_path": path.relative_to(local_root).as_posix(),
            "run_id": run_id,
            "diagnosis": diagnosis,
            "diagnosis_reason": data.get("diagnosis_reason"),
            "stop_reason": stop_reason,
            "elapsed_seconds": data.get("elapsed_seconds"),
            "prompt_id": state.get("prompt_id"),
            "current_node_id": state.get("current_node_id"),
            "current_node_class_type": state.get("current_node_class_type"),
            "state": state,
        }
        records.append(record)
        if diagnosis == "crashed" and stop_reason == "completed" and outputs_by_run.get(run_id):
            warnings.append(
                f"watchdog diagnosis=crashed for run_id={run_id} but stop_reason=completed and outputs exist"
            )
    return records, warnings


def _collect_remote_logs(local_root: Path) -> list[dict[str, Any]]:
    candidates = [
        local_root / "out" / "corpus_matrix" / "remote_live.log",
        local_root / "out" / "corpus_matrix" / "live.log",
        local_root / "out" / "corpus_matrix" / "remote_run.sh",
    ]
    runs_root = local_root / "out" / "runs"
    if runs_root.exists():
        candidates.extend(sorted(runs_root.glob("*/*.log")))
    seen: set[Path] = set()
    logs: list[dict[str, Any]] = []
    for path in candidates:
        if path in seen or not path.exists() or not path.is_file():
            continue
        seen.add(path)
        record = _file_record(path, local_root)
        if record is not None:
            logs.append(record)
    return logs


# ---------------------------------------------------------------------------
# Manifest, report, summary
# ---------------------------------------------------------------------------

def _build_artifact_manifest(
    local_root: Path,
    *,
    pod_id: str | None = None,
    exit_code: int | None = None,
    mode: str = "detached",
    terminated: bool | None = None,
    remote_command: str | None = None,
    upload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    loaded_manifest = _load_json(local_root / "manifest.json")
    existing = loaded_manifest if isinstance(loaded_manifest, dict) else {}
    generated_at = existing.get("generated_at") or datetime.now(timezone.utc).isoformat()
    archive = local_root / "artifacts.tar.gz"
    results_path = local_root / "out" / "corpus_matrix" / "results.tsv"
    results = _parse_tsv(results_path)
    outputs = _collect_outputs(local_root)
    run_metadata, metadata_warnings = _collect_run_metadata(local_root)
    watchdogs, watchdog_warnings = _collect_watchdogs(local_root, run_metadata)
    remote_logs = _collect_remote_logs(local_root)
    remote_script = _file_record(local_root / "out" / "corpus_matrix" / "remote_run.sh", local_root)
    failures = _count_failures(results)
    warnings = metadata_warnings + watchdog_warnings
    status = "unknown"
    if exit_code is not None:
        status = "pass" if exit_code == 0 and failures == 0 else "fail"
    manifest: dict[str, Any] = {
        "generated_at": generated_at,
        "pod_id": pod_id,
        "mode": mode,
        "remote_root": REMOTE_ROOT,
        "artifact_root": _display_path(local_root),
        "exit_code": exit_code,
        "terminated": terminated,
        "status": status,
        "summary": {
            "status": status,
            "outputs": len(outputs),
            "result_rows": len(results),
            "failures": failures,
            "warnings": len(warnings),
            "exit_code": exit_code,
            "terminated": terminated,
        },
        "archive": _file_record(archive, local_root) if archive.exists() else None,
        "upload": upload or {},
        "remote_command": remote_command,
        "remote_script": remote_script,
        "results": {
            "path": _display_path(results_path) if results_path.exists() else None,
            "rows": results,
        },
        "outputs": outputs,
        "run_metadata": run_metadata,
        "watchdogs": watchdogs,
        "remote_logs": remote_logs,
        "warnings": warnings,
    }
    return manifest


def _write_artifact_report(local_root: Path, manifest: dict[str, Any]) -> Path:
    report_path = local_root / "report.md"
    summary = manifest.get("summary", {})
    lines = [
        "# RunPod Evidence Report",
        "",
        "## Summary",
        "",
        f"- status: {summary.get('status')}",
        f"- exit_code: {summary.get('exit_code')}",
        f"- pod_id: {manifest.get('pod_id') or '-'}",
        f"- terminated: {summary.get('terminated')}",
        f"- artifact_root: {manifest.get('artifact_root')}",
        f"- outputs: {summary.get('outputs')}",
        f"- failures: {summary.get('failures')}",
        f"- warnings: {summary.get('warnings')}",
        "",
        "## Evidence",
        "",
        f"- archive: {((manifest.get('archive') or {}).get('relative_path')) or '-'}",
        f"- remote_script: {((manifest.get('remote_script') or {}).get('relative_path')) or '-'}",
        f"- upload_mode: {((manifest.get('upload') or {}).get('mode')) or '-'}",
        f"- remote_command: `{_md(manifest.get('remote_command') or '-')}`",
        "",
    ]
    remote_logs = manifest.get("remote_logs") or []
    if remote_logs:
        lines.extend(["## Logs", ""])
        for log in remote_logs:
            lines.append(f"- {log.get('relative_path')} ({log.get('bytes')} bytes)")
        lines.append("")
    warnings = manifest.get("warnings") or []
    if warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {_md(str(warning))}" for warning in warnings)
        lines.append("")
    rows = (manifest.get("results") or {}).get("rows") or []
    if rows:
        lines.extend(["## Results", ""])
        columns = list(rows[0].keys())
        lines.append("| " + " | ".join(_md(column) for column in columns) + " |")
        lines.append("| " + " | ".join("---" for _ in columns) + " |")
        for row in rows:
            lines.append("| " + " | ".join(_md(row.get(column, "")) for column in columns) + " |")
        lines.append("")
    outputs = manifest.get("outputs") or []
    if outputs:
        lines.extend(["## Outputs", ""])
        lines.append("| path | bytes | extension | dimensions |")
        lines.append("| --- | ---: | --- | --- |")
        for output in outputs:
            image = output.get("image") or {}
            dimensions = f"{image.get('width')}x{image.get('height')}" if image.get("width") and image.get("height") else "-"
            lines.append(
                "| "
                + " | ".join(
                    [
                        _md(output.get("relative_path", "")),
                        str(output.get("bytes", "")),
                        _md(output.get("extension", "")),
                        _md(dimensions),
                    ]
                )
                + " |"
            )
        lines.append("")
    run_metadata = manifest.get("run_metadata") or []
    if run_metadata:
        lines.extend(["## Runs", ""])
        lines.append("| run_id | workflow_id | runtime | prompt_id | outputs |")
        lines.append("| --- | --- | --- | --- | ---: |")
        for record in run_metadata:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _md(record.get("run_id", "")),
                        _md(record.get("workflow_id", "")),
                        _md(record.get("runtime", "")),
                        _md(record.get("prompt_id", "")),
                        str(len(record.get("outputs") or [])),
                    ]
                )
                + " |"
            )
        lines.append("")
    watchdogs = manifest.get("watchdogs") or []
    if watchdogs:
        lines.extend(["## Watchdogs", ""])
        lines.append("| run_id | diagnosis | stop_reason | elapsed_seconds | prompt_id |")
        lines.append("| --- | --- | --- | ---: | --- |")
        for record in watchdogs:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _md(record.get("run_id", "")),
                        _md(record.get("diagnosis", "")),
                        _md(record.get("stop_reason", "")),
                        str(record.get("elapsed_seconds", "")),
                        _md(record.get("prompt_id", "")),
                    ]
                )
                + " |"
            )
        lines.append("")
    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report_path


def _finalize_artifacts(
    local_root: Path,
    *,
    pod_id: str | None = None,
    exit_code: int | None = None,
    mode: str = "detached",
    terminated: bool | None = None,
    remote_command: str | None = None,
    upload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = _build_artifact_manifest(
        local_root,
        pod_id=pod_id,
        exit_code=exit_code,
        mode=mode,
        terminated=terminated,
        remote_command=remote_command,
        upload=upload,
    )
    manifest_path = local_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    report_path = _write_artifact_report(local_root, manifest)
    manifest["manifest_path"] = _display_path(manifest_path)
    manifest["report_path"] = _display_path(report_path)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return manifest


def _print_detached_summary(
    *,
    pod_id: str | None,
    exit_code: int,
    terminated: bool,
    artifact_root: Path | None,
) -> None:
    manifest: dict[str, Any] = {}
    if artifact_root is not None:
        loaded = _load_json(artifact_root / "manifest.json")
        if isinstance(loaded, dict):
            manifest = loaded
    summary = manifest.get("summary") if isinstance(manifest.get("summary"), dict) else {}
    failures = int(summary.get("failures") or 0)
    outputs = int(summary.get("outputs") or 0)
    status = summary.get("status") or ("pass" if exit_code == 0 and failures == 0 else "fail")
    print(f"status={status} exit_code={exit_code}", flush=True)
    if pod_id:
        print(f"pod_id={pod_id}", flush=True)
    print(f"terminated={str(terminated).lower()}", flush=True)
    if artifact_root is not None:
        print(f"artifact_dir={_display_path(artifact_root)}", flush=True)
        print(f"manifest={_display_path(artifact_root / 'manifest.json')}", flush=True)
        print(f"report={_display_path(artifact_root / 'report.md')}", flush=True)
    print(f"outputs={outputs}", flush=True)
    print(f"failures={failures}", flush=True)