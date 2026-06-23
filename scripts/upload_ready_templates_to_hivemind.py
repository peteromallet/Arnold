#!/usr/bin/env python3
"""Upload VibeComfy ready-template Python workflows to Hivemind.

Hivemind's generic workflow ingester accepts ComfyUI JSON. VibeComfy's
agent-facing workflow assets are Python ready templates, so this script uses
the Hivemind contribute edge function directly and stores the `.py`
representation in both searchable text and structured payload metadata.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_CONTRIBUTE_URL = "https://ujlwuvkrxlvoswwkerdf.supabase.co/functions/v1/contribute"
DEFAULT_HIVEMIND_API_URL = "https://ujlwuvkrxlvoswwkerdf.supabase.co/rest/v1"
DEFAULT_HIVEMIND_ANON_KEY = "sb_publishable_O38oPBafrBoFrpi_rlWJvA_UJrulFsx"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_coverage(coverage_path: Path) -> dict[str, dict[str, Any]]:
    if not coverage_path.exists():
        return {}
    data = json.loads(coverage_path.read_text(encoding="utf-8"))
    rows = data.get("workflows", []) if isinstance(data, dict) else []
    coverage: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("id"), str):
            coverage[row["id"]] = row
    return coverage


def _load_templates(index_path: Path, *, coverage_path: Path | None = None) -> list[dict[str, Any]]:
    data = json.loads(index_path.read_text(encoding="utf-8"))
    rows = data.get("templates", [])
    if not isinstance(rows, list):
        raise ValueError(f"{index_path} does not contain a templates list")
    coverage = _load_coverage(coverage_path) if coverage_path else {}
    templates: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        path = row.get("path")
        template_id = row.get("id")
        if not isinstance(path, str) or not path.endswith(".py"):
            continue
        if not isinstance(template_id, str) or not template_id:
            continue
        merged = dict(row)
        coverage_key = template_id.split("/", 1)[-1]
        coverage_row = coverage.get(coverage_key)
        if coverage_row:
            source_path = coverage_row.get("path")
            if isinstance(source_path, str) and source_path.endswith(".json"):
                merged.setdefault("source_workflow", source_path)
                merged["converted_from_json"] = source_path
            for key in ("source", "model_family", "task", "media", "approach"):
                if key in coverage_row and key not in merged:
                    merged[key] = coverage_row[key]
        templates.append(merged)
    return templates


def _names(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    names: list[str] = []
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            names.append(item["name"])
        elif isinstance(item, str):
            names.append(item)
    return names


def _models(row: dict[str, Any]) -> list[str]:
    requirements = row.get("requirements")
    if isinstance(requirements, dict):
        models = requirements.get("models")
        if isinstance(models, list):
            return [str(model) for model in models if str(model)]
    models = row.get("models")
    if isinstance(models, list):
        return [str(model) for model in models if str(model)]
    return []


def _clean_description(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())


def _description(row: dict[str, Any]) -> str:
    return _clean_description(row.get("description") or row.get("workflow_description"))


def _body(row: dict[str, Any], python_source: str) -> str:
    template_id = str(row["id"])
    path = str(row["path"])
    capability = row.get("capability") or row.get("media") or "workflow"
    readiness = row.get("readiness_class") or row.get("readiness") or ""
    coverage = row.get("coverage_tier") or ""
    public_inputs = _names(row.get("public_inputs"))
    public_outputs = _names(row.get("public_outputs"))
    custom_nodes = [str(node) for node in row.get("custom_nodes") or [] if str(node)]
    models = _models(row)
    source_workflow = row.get("source_workflow") or row.get("source_json")
    converted_from_json = row.get("converted_from_json")
    description = _description(row)

    lines = [
        f"VibeComfy ready-template Python workflow: {template_id}",
        f"Template path: {path}",
        f"Capability: {capability}",
    ]
    if readiness:
        lines.append(f"Readiness: {readiness}")
    if coverage:
        lines.append(f"Coverage tier: {coverage}")
    if description:
        lines.append(f"Description: {description}")
    if source_workflow:
        lines.append(f"Converted source workflow: {source_workflow}")
    if converted_from_json:
        lines.append(
            "Upload representation: converted from ComfyUI JSON to VibeComfy Python ready-template."
        )
    if public_inputs:
        lines.append("Public inputs: " + ", ".join(public_inputs) + ".")
    if public_outputs:
        lines.append("Public outputs: " + ", ".join(public_outputs) + ".")
    if models:
        lines.append("Models: " + ", ".join(models) + ".")
    if custom_nodes:
        lines.append("Custom nodes: " + ", ".join(custom_nodes) + ".")
    lines.extend(["", "Python ready-template source:", python_source])
    return "\n".join(lines)


def _envelope(row: dict[str, Any], python_source: str) -> dict[str, Any]:
    template_id = str(row["id"])
    path = str(row["path"])
    description = _description(row)
    metadata = {
        "asset_kind": "vibecomfy_ready_template",
        "ready_template_id": template_id,
        "path": path,
        "source_workflow": row.get("source_workflow") or row.get("source_json"),
        "converted_from_json": row.get("converted_from_json"),
        "capability": row.get("capability") or row.get("media"),
        "model_family": row.get("model_family"),
        "task": row.get("task"),
        "approach": row.get("approach"),
        "description": description or None,
        "coverage_tier": row.get("coverage_tier"),
        "readiness_class": row.get("readiness_class") or row.get("readiness"),
        "public_inputs": _names(row.get("public_inputs")),
        "public_outputs": _names(row.get("public_outputs")),
        "custom_nodes": [str(node) for node in row.get("custom_nodes") or [] if str(node)],
        "models": _models(row),
        "model_count": row.get("model_count", row.get("models_count")),
        "representation": "python",
    }
    return {
        "action": "add_resource",
        "data": {
            "kind": "workflow",
            "source": "vibecomfy",
            "external_id": f"vibecomfy:ready_template:{template_id}",
            "title": template_id,
            "body": _body(row, python_source),
            "url": f"file://{path}",
            "metadata": metadata,
            "payload": {
                "ready_template_id": template_id,
                "python_path": path,
                "python_source": python_source,
                "converted_from_json": row.get("converted_from_json"),
                "description": description or None,
            },
        },
    }


def _load_description_map(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object keyed by template id or path")
    descriptions: dict[str, str] = {}
    for key, value in data.items():
        if not isinstance(key, str):
            continue
        description = _clean_description(value)
        if description:
            descriptions[key] = description
    return descriptions


def _read_description_args(args: argparse.Namespace, *, root: Path) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    if args.description_map:
        descriptions.update(_load_description_map((root / args.description_map).resolve()))
    description = _clean_description(args.description)
    if args.description_file:
        description_path = (root / args.description_file).resolve()
        description = _clean_description(description_path.read_text(encoding="utf-8"))
    if description:
        descriptions["*"] = description
    return descriptions


def _apply_description(row: dict[str, Any], descriptions: dict[str, str]) -> dict[str, Any]:
    if not descriptions:
        return row
    template_id = str(row.get("id", ""))
    path = str(row.get("path", ""))
    description = (
        descriptions.get(template_id)
        or descriptions.get(path)
        or descriptions.get(Path(path).name)
        or descriptions.get("*")
    )
    if not description:
        return row
    enriched = dict(row)
    enriched["description"] = description
    return enriched


def _post(envelope: dict[str, Any], *, contribute_url: str, contributor_key: str) -> dict[str, Any]:
    body = json.dumps(envelope).encode("utf-8")
    request = urllib.request.Request(
        contribute_url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Contributor-Key": contributor_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _postgrest_get(
    table: str,
    params: dict[str, str],
    *,
    api_url: str,
    anon_key: str,
) -> Any:
    query = urllib.parse.urlencode(params)
    url = f"{api_url.rstrip('/')}/{table}?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _verify_recorded(
    envelope: dict[str, Any],
    *,
    api_url: str,
    anon_key: str,
) -> dict[str, Any]:
    data = envelope["data"]
    expected_description = ((data.get("metadata") or {}).get("description") or "").strip()
    rows = _postgrest_get(
        "external_resources",
        {
            "select": "id,kind,source,external_id,title,body,metadata,payload",
            "source": f"eq.{data['source']}",
            "external_id": f"eq.{data['external_id']}",
            "limit": "1",
        },
        api_url=api_url,
        anon_key=anon_key,
    )
    row = rows[0] if isinstance(rows, list) and rows else None
    if not isinstance(row, dict):
        return {
            "ok": False,
            "reason": "not_found",
            "source": data.get("source"),
            "external_id": data.get("external_id"),
        }

    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    body = row.get("body") if isinstance(row.get("body"), str) else ""
    checks = {
        "kind": row.get("kind") == data.get("kind"),
        "source": row.get("source") == data.get("source"),
        "external_id": row.get("external_id") == data.get("external_id"),
        "title": row.get("title") == data.get("title"),
        "metadata_description": (
            not expected_description or metadata.get("description") == expected_description
        ),
        "payload_description": (
            not expected_description or payload.get("description") == expected_description
        ),
        "body_description": (
            not expected_description or f"Description: {expected_description}" in body
        ),
    }
    return {
        "ok": all(checks.values()),
        "resource_id": row.get("id"),
        "checks": checks,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", default="template_index.json", help="template_index.json path")
    parser.add_argument(
        "--coverage",
        default="ready_templates/sources/manifests/coverage.json",
        help="coverage manifest used to annotate JSON-to-Python conversions",
    )
    parser.add_argument("--only", action="append", default=[], help="Substring filter; may be repeated")
    parser.add_argument("--limit", type=int, help="Maximum number of templates to process")
    parser.add_argument("--dry-run", action="store_true", help="Write envelopes without uploading")
    parser.add_argument("--out-dir", help="Directory for dry-run envelopes or upload responses")
    parser.add_argument(
        "--description",
        help="Optional description to add to every selected workflow upload",
    )
    parser.add_argument(
        "--description-file",
        help="Read an optional description for every selected workflow upload from a text file",
    )
    parser.add_argument(
        "--description-map",
        help="JSON object mapping template id, template path, or Python filename to descriptions",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="After real uploads, read external_resources back and verify body/metadata/payload fields",
    )
    parser.add_argument(
        "--hivemind-api-url",
        default=os.environ.get("HIVEMIND_API_URL", DEFAULT_HIVEMIND_API_URL),
        help="PostgREST API URL used by --verify",
    )
    parser.add_argument(
        "--hivemind-anon-key",
        default=os.environ.get("HIVEMIND_ANON_KEY", DEFAULT_HIVEMIND_ANON_KEY),
        help="PostgREST anon key used by --verify",
    )
    parser.add_argument("--sleep", type=float, default=0.1, help="Seconds to sleep between uploads")
    parser.add_argument("--contribute-url", default=os.environ.get("HIVEMIND_CONTRIBUTE_URL", DEFAULT_CONTRIBUTE_URL))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = _repo_root()
    index_path = (root / args.index).resolve()
    coverage_path = (root / args.coverage).resolve() if args.coverage else None
    templates = _load_templates(index_path, coverage_path=coverage_path)
    descriptions = _read_description_args(args, root=root)
    if descriptions:
        templates = [_apply_description(row, descriptions) for row in templates]
    if args.only:
        needles = tuple(item.lower() for item in args.only)
        templates = [
            row
            for row in templates
            if any(needle in str(row.get("id", "")).lower() or needle in str(row.get("path", "")).lower() for needle in needles)
        ]
    if args.limit is not None:
        templates = templates[: args.limit]

    out_dir = Path(args.out_dir).resolve() if args.out_dir else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    contributor_key = os.environ.get("HIVEMIND_CONTRIBUTOR_KEY")
    if not args.dry_run and not contributor_key:
        print("error: set HIVEMIND_CONTRIBUTOR_KEY or use --dry-run", file=sys.stderr)
        return 1

    results: list[dict[str, Any]] = []
    for row in templates:
        template_id = str(row["id"])
        py_path = (root / str(row["path"])).resolve()
        if not py_path.exists():
            raise FileNotFoundError(f"{template_id}: missing Python template {py_path}")
        python_source = py_path.read_text(encoding="utf-8")
        envelope = _envelope(row, python_source)
        safe_name = template_id.replace("/", "__")

        if args.dry_run:
            result = {"template_id": template_id, "status": "dry_run", "envelope": envelope}
            if out_dir:
                (out_dir / f"{safe_name}.json").write_text(json.dumps(envelope, indent=2, sort_keys=True), encoding="utf-8")
        else:
            try:
                response = _post(
                    envelope,
                    contribute_url=args.contribute_url,
                    contributor_key=contributor_key or "",
                )
                result = {"template_id": template_id, "status": "uploaded", "response": response}
                if args.verify:
                    verify = _verify_recorded(
                        envelope,
                        api_url=args.hivemind_api_url,
                        anon_key=args.hivemind_anon_key,
                    )
                    result["verify"] = verify
                    if not verify.get("ok"):
                        result["status"] = "verify_failed"
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode("utf-8", errors="replace")
                result = {"template_id": template_id, "status": "error", "http_status": exc.code, "body": raw}
                results.append(result)
                if out_dir:
                    (out_dir / f"{safe_name}.response.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
                break
            if out_dir:
                (out_dir / f"{safe_name}.response.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
            time.sleep(args.sleep)
        results.append(result)
        print(json.dumps({"template_id": template_id, "status": result["status"]}), flush=True)

    summary = {"count": len(results), "statuses": {}}
    for result in results:
        status = str(result["status"])
        summary["statuses"][status] = summary["statuses"].get(status, 0) + 1
    if out_dir:
        (out_dir / "_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0 if not any(result["status"] in {"error", "verify_failed"} for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
