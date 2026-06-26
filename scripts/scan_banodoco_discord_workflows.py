#!/usr/bin/env python3
"""Audit Banodoco Discord attachments for ComfyUI workflows.

This is intentionally read-only. It uses the private Brain of BNDC Supabase
archive to enumerate Discord attachment metadata, then uses the Discord bot
token to refresh expired CDN URLs before downloading candidate files.
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures
import hashlib
import json
import os
import re
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from pathlib import Path
from typing import Any


DEFAULT_ENV_FILE = Path("/Users/peteromalley/Documents/banodoco-workspace/brain-of-bndc/.env")
DEFAULT_OUT = Path("/tmp/banodoco-discord-workflow-scan.json")
SUPABASE_PAGE_SIZE = 1000


def load_env_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def http_json(url: str, *, headers: dict[str, str], timeout: int = 60) -> Any:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def http_bytes_with_retry(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 60,
    attempts: int = 5,
) -> tuple[int, bytes, dict[str, str]]:
    merged_headers = {"User-Agent": "Mozilla/5.0"}
    merged_headers.update(headers or {})
    last_error: Exception | None = None
    for attempt in range(attempts):
        request = urllib.request.Request(url, headers=merged_headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, response.read(), dict(response.headers)
        except urllib.error.HTTPError as error:
            if error.code == 429:
                retry_after = error.headers.get("Retry-After")
                try:
                    payload = json.loads(error.read().decode("utf-8"))
                    wait = float(payload.get("retry_after", retry_after or 1))
                except Exception:
                    wait = float(retry_after or 1)
                time.sleep(wait + 0.1)
                continue
            if 500 <= error.code < 600:
                last_error = error
                time.sleep(0.5 * (attempt + 1))
                continue
            body = error.read()
            return error.code, body, dict(error.headers)
        except Exception as error:  # noqa: BLE001 - preserve error text in output.
            last_error = error
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"request failed after retries: {last_error}")


def supabase_headers() -> dict[str, str]:
    key = require_env("SUPABASE_SERVICE_KEY")
    return {"apikey": key, "Authorization": f"Bearer {key}"}


def discord_headers() -> dict[str, str]:
    token = require_env("DISCORD_BOT_TOKEN")
    return {"Authorization": f"Bot {token}", "User-Agent": "vibecomfy-workflow-audit/0.1"}


def supabase_base() -> str:
    return require_env("SUPABASE_URL").rstrip("/") + "/rest/v1"


def channel_map() -> dict[int, str]:
    url = f"{supabase_base()}/discord_channels?select=channel_id,channel_name&limit=10000"
    rows = http_json(url, headers=supabase_headers())
    return {
        int(row["channel_id"]): row.get("channel_name") or str(row["channel_id"])
        for row in rows
        if row.get("channel_id") is not None
    }


def normalize_attachments(value: Any) -> list[dict[str, Any]]:
    if not value:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def attachment_name(attachment: dict[str, Any]) -> str:
    return str(attachment.get("filename") or attachment.get("url") or "").split("?", 1)[0]


def attachment_matches(attachment: dict[str, Any], extensions: tuple[str, ...]) -> bool:
    filename = str(attachment.get("filename") or "").lower()
    url_path = str(attachment.get("url") or "").split("?", 1)[0].lower()
    content_type = str(attachment.get("content_type") or attachment.get("contentType") or "").lower()
    if any(filename.endswith(ext) or url_path.endswith(ext) for ext in extensions):
        return True
    if ".json" in extensions and "application/json" in content_type:
        return True
    if (".png" in extensions or ".jpg" in extensions or ".jpeg" in extensions or ".webp" in extensions) and content_type.startswith("image/"):
        return True
    return False


def enumerate_attachment_candidates(extensions: tuple[str, ...], *, limit_messages: int | None) -> list[dict[str, Any]]:
    channels = channel_map()
    candidates: list[dict[str, Any]] = []
    offset = 0
    scanned = 0
    headers = supabase_headers()
    while True:
        end = offset + SUPABASE_PAGE_SIZE - 1
        page_headers = dict(headers)
        page_headers["Range"] = f"{offset}-{end}"
        query = urllib.parse.urlencode(
            {
                "select": "message_id,guild_id,channel_id,thread_id,created_at,content,attachments",
                "attachments": "not.eq.[]",
                "order": "message_id.asc",
            }
        )
        url = f"{supabase_base()}/discord_messages?{query}"
        request = urllib.request.Request(url, headers=page_headers)
        with urllib.request.urlopen(request, timeout=120) as response:
            rows = json.loads(response.read().decode("utf-8"))
        if not rows:
            break
        for row in rows:
            scanned += 1
            for attachment in normalize_attachments(row.get("attachments")):
                if not attachment_matches(attachment, extensions):
                    continue
                channel_id = int(row["channel_id"]) if row.get("channel_id") is not None else None
                candidates.append(
                    {
                        "message_id": int(row["message_id"]),
                        "guild_id": row.get("guild_id"),
                        "channel_id": channel_id,
                        "channel_name": channels.get(channel_id, str(channel_id)),
                        "thread_id": row.get("thread_id"),
                        "created_at": row.get("created_at"),
                        "filename": str(attachment.get("filename") or ""),
                        "content_type": str(attachment.get("content_type") or attachment.get("contentType") or ""),
                        "url": str(attachment.get("url") or ""),
                        "content_preview": (row.get("content") or "")[:240].replace("\n", " "),
                    }
                )
            if limit_messages and scanned >= limit_messages:
                return candidates
        if len(rows) < SUPABASE_PAGE_SIZE:
            break
        offset += SUPABASE_PAGE_SIZE
        if offset % 25000 == 0:
            print(f"inventory progress rows={offset} candidates={len(candidates)}", flush=True)
    return candidates


def classify_comfy_json(value: Any) -> tuple[str, list[str]] | None:
    if not isinstance(value, dict):
        return None
    nodes = value.get("nodes")
    if isinstance(nodes, list):
        classes = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_type = node.get("type") or node.get("class_type")
            if node_type or "inputs" in node or "widgets_values" in node:
                classes.append(str(node_type or "unknown"))
        if len(classes) >= 2:
            return "comfy_ui", classes
    api_classes = []
    numeric_keys = 0
    for key, node in value.items():
        if str(key).isdigit():
            numeric_keys += 1
        if isinstance(node, dict) and "class_type" in node and "inputs" in node:
            api_classes.append(str(node.get("class_type") or "unknown"))
    if len(api_classes) >= 2 and numeric_keys >= max(1, len(api_classes) // 2):
        return "comfy_api", api_classes
    for key in ("workflow", "prompt"):
        nested = value.get(key)
        if isinstance(nested, str):
            try:
                nested = json.loads(nested)
            except json.JSONDecodeError:
                nested = None
        nested_result = classify_comfy_json(nested) if isinstance(nested, dict) else None
        if nested_result:
            workflow_format, classes = nested_result
            return f"nested_{key}_{workflow_format}", classes
    return None


def fresh_message(channel_id: int, message_id: int) -> dict[str, Any]:
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}"
    status, body, _ = http_bytes_with_retry(url, headers=discord_headers(), timeout=30)
    if status != 200:
        raise RuntimeError(f"Discord message fetch failed: HTTP {status}: {body[:160]!r}")
    return json.loads(body.decode("utf-8"))


def fresh_matching_attachments(candidate: dict[str, Any], extensions: tuple[str, ...]) -> list[dict[str, Any]]:
    message = fresh_message(int(candidate["channel_id"]), int(candidate["message_id"]))
    wanted = Path(candidate.get("filename") or "").name.lower()
    matches = []
    for attachment in message.get("attachments") or []:
        filename = str(attachment.get("filename") or "").lower()
        if filename == wanted or attachment_matches(attachment, extensions):
            matches.append(attachment)
    return matches


def decode_json_bytes(data: bytes) -> Any:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    return json.loads(text)


def scan_png_text_chunks(data: bytes) -> list[dict[str, str]]:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return []
    chunks: list[dict[str, str]] = []
    pos = 8
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        chunk_type = data[pos + 4 : pos + 8]
        payload = data[pos + 8 : pos + 8 + length]
        pos = pos + 12 + length
        try:
            if chunk_type == b"tEXt":
                key, text = payload.split(b"\x00", 1)
                chunks.append({"key": key.decode("latin-1"), "text": text.decode("utf-8", "ignore")})
            elif chunk_type == b"zTXt":
                key, rest = payload.split(b"\x00", 1)
                if rest and rest[0] == 0:
                    chunks.append({"key": key.decode("latin-1"), "text": zlib.decompress(rest[1:]).decode("utf-8", "ignore")})
            elif chunk_type == b"iTXt":
                parts = payload.split(b"\x00", 5)
                if len(parts) == 6:
                    key = parts[0].decode("utf-8", "ignore")
                    compressed = parts[1] == b"\x01"
                    text_data = parts[5]
                    if compressed:
                        text_data = zlib.decompress(text_data)
                    chunks.append({"key": key, "text": text_data.decode("utf-8", "ignore")})
        except Exception:
            continue
        if chunk_type == b"IEND":
            break
    return chunks


def classify_image_workflow(data: bytes) -> dict[str, Any] | None:
    for chunk in scan_png_text_chunks(data):
        key = chunk["key"].lower()
        if key not in {"workflow", "prompt", "parameters"}:
            continue
        text = chunk["text"].strip()
        match = None
        if text.startswith("{"):
            match = text
        else:
            found = re.search(r"(\{.*(?:last_node_id|class_type|nodes).*\})", text, re.DOTALL)
            if found:
                match = found.group(1)
        if not match:
            continue
        try:
            value = json.loads(match)
        except json.JSONDecodeError:
            continue
        classified = classify_comfy_json(value)
        if classified:
            workflow_format, classes = classified
            return {"workflow_format": f"png_{key}_{workflow_format}", "node_count": len(classes), "node_classes": classes}
    return None


def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return cleaned or "attachment"


def save_download(save_dir: Path | None, *, data: bytes, sha256: str, filename: str) -> str | None:
    if save_dir is None:
        return None
    save_dir.mkdir(parents=True, exist_ok=True)
    path = save_dir / f"{sha256[:16]}-{safe_filename(filename)}"
    if not path.exists():
        path.write_bytes(data)
    return str(path)


def classify_candidate(
    candidate: dict[str, Any],
    *,
    kind: str,
    max_bytes: int,
    save_dir: Path | None,
) -> list[dict[str, Any]]:
    extensions = (".json",) if kind == "json" else (".png", ".webp", ".jpg", ".jpeg")
    try:
        attachments = fresh_matching_attachments(candidate, extensions)
    except Exception as error:  # noqa: BLE001
        return [{**candidate, "status": "message_error", "error": str(error)}]
    results = []
    for attachment in attachments:
        filename = str(attachment.get("filename") or candidate.get("filename") or "")
        result = {**candidate, "filename": filename, "size": attachment.get("size"), "content_type": attachment.get("content_type")}
        if attachment.get("size") and int(attachment["size"]) > max_bytes:
            results.append({**result, "status": "skipped_too_large"})
            continue
        try:
            status, data, response_headers = http_bytes_with_retry(str(attachment.get("url")), timeout=90)
            result["download_status"] = status
            result["download_content_type"] = response_headers.get("Content-Type")
            if status != 200:
                results.append({**result, "status": "download_error"})
                continue
            result["sha256"] = hashlib.sha256(data).hexdigest()
            result["bytes"] = len(data)
            if kind == "json":
                classified = classify_comfy_json(decode_json_bytes(data))
                if classified:
                    workflow_format, classes = classified
                    saved_path = save_download(
                        save_dir,
                        data=data,
                        sha256=str(result["sha256"]),
                        filename=filename,
                    )
                    results.append(
                        {
                            **result,
                            "status": "comfy_workflow",
                            "workflow_format": workflow_format,
                            "node_count": len(classes),
                            "node_classes": collections.Counter(classes).most_common(30),
                            "saved_path": saved_path,
                        }
                    )
                else:
                    results.append({**result, "status": "json_non_comfy"})
            else:
                classified_image = classify_image_workflow(data)
                if classified_image:
                    saved_path = save_download(
                        save_dir,
                        data=data,
                        sha256=str(result["sha256"]),
                        filename=filename,
                    )
                    results.append(
                        {
                            **result,
                            "status": "image_embedded_comfy_workflow",
                            "workflow_format": classified_image["workflow_format"],
                            "node_count": classified_image["node_count"],
                            "node_classes": collections.Counter(classified_image["node_classes"]).most_common(30),
                            "saved_path": saved_path,
                        }
                    )
                else:
                    results.append({**result, "status": "image_no_comfy_metadata"})
        except Exception as error:  # noqa: BLE001
            results.append({**result, "status": "exception", "error": str(error)})
    return results or [{**candidate, "status": "no_matching_attachment_after_refresh"}]


def summarize(results: list[dict[str, Any]], *, source_count: int) -> dict[str, Any]:
    statuses = collections.Counter(row.get("status") for row in results)
    workflow_rows = [
        row
        for row in results
        if row.get("status") in {"comfy_workflow", "image_embedded_comfy_workflow"}
    ]
    unique_workflows = {row.get("sha256") for row in workflow_rows if row.get("sha256")}
    by_channel = collections.Counter(row.get("channel_name") or str(row.get("channel_id")) for row in workflow_rows)
    by_format = collections.Counter(row.get("workflow_format") for row in workflow_rows)
    by_month = collections.Counter((row.get("created_at") or "")[:7] for row in workflow_rows)
    return {
        "source_candidates": source_count,
        "result_rows": len(results),
        "statuses": statuses.most_common(),
        "workflow_rows": len(workflow_rows),
        "unique_workflow_sha256": len(unique_workflows),
        "workflow_formats": by_format.most_common(),
        "top_workflow_channels": by_channel.most_common(30),
        "top_workflow_months": by_month.most_common(30),
        "examples": workflow_rows[:20],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--kind", choices=["json", "images"], default="json")
    parser.add_argument("--inventory-only", action="store_true")
    parser.add_argument("--limit-messages", type=int)
    parser.add_argument("--max-workers", type=int, default=8)
    parser.add_argument("--max-bytes", type=int, default=25_000_000)
    parser.add_argument("--save-files", type=Path, help="Directory to save confirmed workflow attachments.")
    args = parser.parse_args()

    load_env_file(args.env_file)
    extensions = (".json",) if args.kind == "json" else (".png", ".webp", ".jpg", ".jpeg")
    candidates = enumerate_attachment_candidates(extensions, limit_messages=args.limit_messages)
    print(f"candidate attachments: {len(candidates)}", flush=True)
    if args.inventory_only:
        payload = {"summary": {"source_candidates": len(candidates)}, "candidates": candidates}
        args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"wrote {args.out}")
        return

    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = [
            executor.submit(
                classify_candidate,
                candidate,
                kind=args.kind,
                max_bytes=args.max_bytes,
                save_dir=args.save_files,
            )
            for candidate in candidates
        ]
        for index, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            results.extend(future.result())
            if index % 250 == 0:
                workflow_count = sum(
                    1
                    for row in results
                    if row.get("status") in {"comfy_workflow", "image_embedded_comfy_workflow"}
                )
                print(f"classify progress candidates={index}/{len(candidates)} workflows={workflow_count}", flush=True)

    payload = {"summary": summarize(results, source_count=len(candidates)), "results": results}
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
