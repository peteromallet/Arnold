"""Codebase management and investigation tools."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import Any
from uuid import uuid4

from agent_kit.code_cache import cache_key, deleted_repo_failure, get_cached, upsert_cached
from agent_kit.code_redaction import redact_code_secrets
from agent_kit.github_client import GitHubClient
from agent_kit.tool_kit import ToolContext, register_tool


JSONDict = dict[str, Any]
MAX_READ_CHARS = 24_000
MAX_EXCERPT_CHARS = 16_000


ADD_CODEBASE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["owner", "name"],
    "properties": {
        "owner": {"type": "string"},
        "name": {"type": "string"},
        "scope": {"type": "string", "enum": ["global", "epic_specific"]},
        "group_name": {"type": ["string", "null"]},
        "epic_id": {"type": ["string", "null"]},
        "notes": {"type": ["string", "null"]},
    },
}

LIST_CODEBASES_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "scope": {"type": ["string", "null"], "enum": ["global", "epic_specific", None]},
        "group": {"type": ["string", "null"]},
        "epic_id": {"type": ["string", "null"]},
        "include_global": {"type": "boolean"},
    },
}

REMOVE_CODEBASE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["codebase_id"],
    "properties": {"codebase_id": {"type": "string"}},
}

TREE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["codebase_id"],
    "properties": {
        "codebase_id": {"type": "string"},
        "path": {"type": ["string", "null"]},
    },
}

READ_FILE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["codebase_id", "file_path"],
    "properties": {
        "codebase_id": {"type": "string"},
        "file_path": {"type": "string"},
        "line_range": {"type": ["string", "array", "null"]},
    },
}

SEARCH_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["codebase_id", "query"],
    "properties": {
        "codebase_id": {"type": "string"},
        "query": {"type": "string"},
        "type": {"type": ["string", "null"], "enum": ["text", "definition", "usages", "pattern", None]},
    },
}

ANALYZE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["codebase_ids", "scope", "question"],
    "properties": {
        "codebase_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "scope": {"type": "string", "enum": ["file", "directory", "cross_codebase"]},
        "question": {"type": "string"},
        "path": {"type": ["string", "null"]},
    },
}

SAVE_EXCERPT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["content"],
    "properties": {
        "content": {"type": "string"},
        "summary": {"type": ["string", "null"]},
        "codebase_id": {"type": ["string", "null"]},
        "epic_id": {"type": ["string", "null"]},
        "file_path": {"type": ["string", "null"]},
        "line_range": {"type": ["string", "array", "null"]},
        "source": {"type": "string", "enum": ["conversation", "codebase"]},
    },
}

MARK_CODE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["artifact_id", "epic_id"],
    "properties": {
        "artifact_id": {"type": "string"},
        "epic_id": {"type": "string"},
        "reason": {"type": ["string", "null"]},
    },
}


@register_tool("add_codebase", schema=ADD_CODEBASE_SCHEMA, operation_kind="write")
def add_codebase(
    context: ToolContext,
    owner: str,
    name: str,
    scope: str = "global",
    group_name: str | None = None,
    epic_id: str | None = None,
    notes: str | None = None,
) -> JSONDict:
    client = _github_client(context)
    owner_l, name_l = _repo_key(owner, name)
    metadata_key = cache_key("repo_metadata", {"owner": owner_l, "name": name_l})
    cached = get_cached(context.store, metadata_key)
    result = cached if cached is not None else client.repo_metadata(owner_l, name_l)
    if not result.get("ok"):
        return result
    if cached is None:
        upsert_cached(context.store, metadata_key, result, metadata={"endpoint": "repo_metadata"})
    repo = result["repo"]
    verified_at = _now()
    row = context.store.upsert_codebase(
        owner=repo["owner"],
        name=repo["name"],
        default_branch=repo["default_branch"],
        scope=scope,
        group_name=group_name,
        associated_epic_id=epic_id,
        added_via="tool",
        verified_accessible_at=verified_at,
        notes=notes,
    )
    if epic_id:
        context.store.record_epic_event(
            epic_id=epic_id,
            transaction_id=uuid4().hex,
            event_type="codebase_added",
            summary=f"Added codebase {repo['owner']}/{repo['name']}",
            prior_state={"codebase_id": row["id"], "group_name": group_name},
            turn_id=context.turn_id,
        )
    return {"ok": True, "codebase": row}


@register_tool("remove_codebase", schema=REMOVE_CODEBASE_SCHEMA, operation_kind="write")
def remove_codebase(context: ToolContext, codebase_id: str) -> JSONDict:
    artifacts = context.store.list_code_artifacts(codebase_id=codebase_id, limit=1)
    context.store.remove_codebase(codebase_id)
    return {
        "ok": True,
        "codebase_id": codebase_id,
        "artifacts_preserved": True,
        "had_artifacts": bool(artifacts),
    }


@register_tool("list_codebases", schema=LIST_CODEBASES_SCHEMA, operation_kind="read")
def list_codebases(
    context: ToolContext,
    scope: str | None = None,
    group: str | None = None,
    epic_id: str | None = None,
    include_global: bool = True,
) -> JSONDict:
    rows = context.store.list_codebases(
        scope=scope,
        group_name=group,
        epic_id=epic_id,
        include_global=include_global,
    )
    return {"ok": True, "codebases": rows}


@register_tool("get_codebase_tree", schema=TREE_SCHEMA, operation_kind="read")
def get_codebase_tree(context: ToolContext, codebase_id: str, path: str | None = None) -> JSONDict:
    codebase = _load_codebase(context, codebase_id)
    if "error" in codebase:
        return codebase
    key = cache_key("tree", {"codebase_id": codebase_id, "path": path})
    cached = get_cached(context.store, key)
    if cached is not None:
        return {**cached, "cache_hit": True}
    client = _github_client(context)
    result = client.tree(codebase["owner"], codebase["name"], codebase["default_branch"], path=path)
    if not result.get("ok"):
        if result.get("error", {}).get("type") == "not_found":
            return deleted_repo_failure(result, cached_artifacts=context.store.list_code_artifacts(codebase_id=codebase_id))
        return result
    context.store.touch_codebase_accessed(codebase_id)
    safe = redact_code_secrets(result)
    upsert_cached(context.store, key, safe, metadata={"endpoint": "tree"}, codebase_id=codebase_id)
    return safe


@register_tool("read_codebase_file", schema=READ_FILE_SCHEMA, operation_kind="read")
def read_codebase_file(
    context: ToolContext,
    codebase_id: str,
    file_path: str,
    line_range: Any = None,
) -> JSONDict:
    codebase = _load_codebase(context, codebase_id)
    if "error" in codebase:
        return codebase
    parsed_range = _parse_line_range(line_range)
    if isinstance(parsed_range, dict) and "error" in parsed_range:
        return parsed_range
    key = cache_key("file", {"codebase_id": codebase_id, "file_path": file_path, "line_range": parsed_range})
    cached = get_cached(context.store, key)
    if cached is not None:
        return {**cached, "cache_hit": True}
    result = _github_client(context).file_content(
        codebase["owner"],
        codebase["name"],
        file_path,
        ref=codebase["default_branch"],
    )
    if not result.get("ok"):
        if result.get("error", {}).get("type") == "not_found":
            return deleted_repo_failure(result, cached_artifacts=context.store.list_code_artifacts(codebase_id=codebase_id))
        return result
    content = str(result["file"]["content"])
    selected = _select_lines(content, parsed_range)
    safe_content = redact_code_secrets(selected)
    payload = {
        "ok": True,
        "codebase_id": codebase_id,
        "file_path": file_path,
        "line_range": parsed_range,
        "content": _truncate(safe_content, MAX_READ_CHARS),
        "truncated": len(safe_content) > MAX_READ_CHARS,
    }
    context.store.touch_codebase_accessed(codebase_id)
    upsert_cached(context.store, key, payload, metadata={"endpoint": "file"}, codebase_id=codebase_id, file_path=file_path, scope="file")
    return payload


@register_tool("search_code", schema=SEARCH_SCHEMA, operation_kind="read")
def search_code(context: ToolContext, codebase_id: str, query: str, type: str | None = None) -> JSONDict:
    codebase = _load_codebase(context, codebase_id)
    if "error" in codebase:
        return codebase
    key = cache_key("search", {"codebase_id": codebase_id, "query": query, "type": type})
    cached = get_cached(context.store, key)
    if cached is not None:
        return {**cached, "cache_hit": True}
    result = _github_client(context).search_code(codebase["owner"], codebase["name"], query)
    if not result.get("ok"):
        if result.get("error", {}).get("type") == "not_found":
            return deleted_repo_failure(result, cached_artifacts=context.store.list_code_artifacts(codebase_id=codebase_id))
        return result
    safe = redact_code_secrets({**result, "codebase_id": codebase_id, "query_type": type or "text"})
    context.store.touch_codebase_accessed(codebase_id)
    upsert_cached(context.store, key, safe, metadata={"endpoint": "search"}, codebase_id=codebase_id)
    return safe


@register_tool("analyze_code", schema=ANALYZE_SCHEMA, operation_kind="read")
def analyze_code(
    context: ToolContext,
    codebase_ids: list[str],
    scope: str,
    question: str,
    path: str | None = None,
) -> JSONDict:
    key = cache_key(
        "analyze_code",
        {"codebase_ids": sorted(codebase_ids), "scope": scope, "question": question, "path": path},
    )
    cached = get_cached(context.store, key)
    if cached is not None:
        return {**cached, "cache_hit": True}
    analyses = []
    for codebase_id in codebase_ids:
        codebase = _load_codebase(context, codebase_id)
        if "error" in codebase:
            analyses.append({"codebase_id": codebase_id, "error": codebase["error"]})
            continue
        tree = _github_client(context).tree(codebase["owner"], codebase["name"], codebase["default_branch"], path=path)
        if not tree.get("ok"):
            analyses.append({"codebase_id": codebase_id, "repo": f"{codebase['owner']}/{codebase['name']}", "error": tree.get("error")})
            continue
        entries = tree.get("tree", [])[:25]
        analyses.append(
            {
                "codebase_id": codebase_id,
                "repo": f"{codebase['owner']}/{codebase['name']}",
                "default_branch": codebase["default_branch"],
                "covered_paths": [row.get("path") for row in entries],
                "summary": _extractive_summary(question, entries),
            }
        )
        context.store.touch_codebase_accessed(codebase_id)
    payload = {
        "ok": True,
        "scope": scope,
        "question": question,
        "analysis": analyses,
        "covered_codebase_ids": codebase_ids,
    }
    safe = redact_code_secrets(payload)
    upsert_cached(
        context.store,
        key,
        safe,
        content_summary=f"Analysis for {len(codebase_ids)} codebase(s): {question[:120]}",
        metadata={"endpoint": "analyze_code", "codebase_ids": codebase_ids},
        epic_id=context.metadata.get("epic_id"),
        scope=scope,
    )
    return safe


@register_tool("save_code_excerpt", schema=SAVE_EXCERPT_SCHEMA, operation_kind="write")
def save_code_excerpt(
    context: ToolContext,
    content: str,
    summary: str | None = None,
    codebase_id: str | None = None,
    epic_id: str | None = None,
    file_path: str | None = None,
    line_range: Any = None,
    source: str = "codebase",
) -> JSONDict:
    parsed_range = _parse_line_range(line_range)
    if isinstance(parsed_range, dict) and "error" in parsed_range:
        return parsed_range
    safe_content = _truncate(redact_code_secrets(content), MAX_EXCERPT_CHARS)
    artifact = context.store.create_code_artifact(
        kind="excerpt",
        source=source,
        content=safe_content,
        codebase_id=codebase_id,
        epic_id=epic_id or context.metadata.get("epic_id"),
        file_path=file_path,
        line_range=parsed_range,
        scope="file" if file_path else None,
        content_summary=summary,
        metadata={"saved_by_tool": "save_code_excerpt"},
    )
    return {"ok": True, "artifact": artifact}


@register_tool("mark_code_in_body", schema=MARK_CODE_SCHEMA, operation_kind="write")
def mark_code_in_body(
    context: ToolContext,
    artifact_id: str,
    epic_id: str,
    reason: str | None = None,
) -> JSONDict:
    artifact = context.store.load_code_artifact(artifact_id)
    if artifact is None:
        return {"error": "artifact_not_found", "artifact_id": artifact_id}
    metadata = dict(artifact.get("metadata") or {})
    metadata["marked_for_body"] = True
    metadata["body_reference_reason"] = reason
    updated = context.store.update_code_artifact(artifact_id, epic_id=epic_id, metadata=metadata)
    event = context.store.record_epic_event(
        epic_id=epic_id,
        transaction_id=uuid4().hex,
        event_type="code_referenced",
        summary=reason or f"Marked code artifact {artifact_id} for body reference",
        prior_state={"artifact_id": artifact_id, "file_path": artifact.get("file_path")},
        turn_id=context.turn_id,
    )
    return {"ok": True, "artifact": updated, "event": event, "body_edited": False}


def _github_client(context: ToolContext) -> GitHubClient:
    injected = context.metadata.get("github_client")
    if injected is not None:
        return injected
    return GitHubClient(store=context.store)


def _load_codebase(context: ToolContext, codebase_id: str) -> JSONDict:
    row = context.store.load_codebase(codebase_id)
    if row is None:
        return {"error": "codebase_not_found", "codebase_id": codebase_id}
    return row


def _repo_key(owner: str, name: str) -> tuple[str, str]:
    return owner.strip().lower(), name.strip().lower()


def _parse_line_range(value: Any) -> list[int] | None | JSONDict:
    if value is None:
        return None
    if isinstance(value, list) and len(value) == 2:
        start, end = int(value[0]), int(value[1])
    elif isinstance(value, str) and "-" in value:
        left, right = value.split("-", 1)
        start, end = int(left), int(right)
    elif isinstance(value, str) and value.strip().isdigit():
        start = end = int(value)
    else:
        return {"error": "malformed_line_range", "line_range": value}
    if start < 1 or end < start:
        return {"error": "malformed_line_range", "line_range": value}
    return [start, end]


def _select_lines(content: str, line_range: list[int] | None) -> str:
    if line_range is None:
        return content
    lines = content.splitlines()
    start, end = line_range
    return "\n".join(lines[start - 1 : end])


def _extractive_summary(question: str, entries: list[JSONDict]) -> str:
    paths = [str(row.get("path")) for row in entries[:8]]
    return f"Question: {question}. Inspected {len(entries)} tree entries. Representative paths: {', '.join(paths)}."


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[:max_chars] + "\n[TRUNCATED]"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
