"""Anchor capture, loading, inspection, and prompt rendering helpers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.types import CliError

SUPPORTED_ANCHOR_TYPES = frozenset({"north_star"})
DEFAULT_ANCHOR_TYPE = "north_star"
ANCHORS_SCHEMA_VERSION = 1
ANCHOR_RENDER_FULL = "full"
ANCHOR_RENDER_CHECK = "check"
ANCHOR_RENDER_NONE = "none"

ANCHOR_AUDIENCE_INSTRUCTIONS = {
    "plan": "Build a plan that advances the local brief while preserving the North Star. If scope is narrowed, state whether the narrowing is a bridge or a contradiction.",
    "prep": "Use the North Star to decide what repository evidence matters and which unknowns could change the end-state path.",
    "prep-triage": "When splitting prep work, preserve at least one research path for end-state alignment if the North Star is material to the task.",
    "prep-distill": "Carry forward findings that affect North Star alignment. Do not discard them as local implementation details.",
    "critique": "Flag any plan choice that makes the North Star harder to achieve, even if the plan is locally coherent.",
    "critique_evaluator": "Select critique checks that can catch North Star violations, scope substitution, or unsupported claims of alignment.",
    "parallel_critique": "Investigate your focused check with the North Star in view. Anchor mismatch is a valid finding.",
    "revise": "Address critique findings without weakening the North Star. If a finding requires changing the anchor, escalate instead of editing around it.",
    "gate": "Do not recommend proceeding when the plan clearly contradicts the North Star or hides a scope substitution. Recommend iteration or escalation.",
    "finalize": "Convert the approved plan into executable tasks while preserving North Star constraints and visible alignment checks.",
    "execute": "Implement the approved tasks without knowingly violating the North Star. Report deviations explicitly.",
    "execute-batch": "Execute only this batch, but preserve North Star alignment in local implementation choices and report conflicts.",
    "review": "Review against the issue, criteria, and visible North Star alignment. Flag observable drift; require rework only for actionable failures under the review contract.",
    "parallel_review": "Review your focused dimension with North Star alignment in view. Record concrete evidence for any drift.",
    "compact_review": "Even in compact mode, keep North Star alignment in view and inspect the repository where needed.",
    "generic": "Use the North Star as durable alignment context for this stage.",
}

ANCHOR_AUDIENCE_RENDER_MODES = {
    "plan": ANCHOR_RENDER_FULL,
    "prep": ANCHOR_RENDER_FULL,
    "prep-triage": ANCHOR_RENDER_FULL,
    "prep-distill": ANCHOR_RENDER_FULL,
    "critique": ANCHOR_RENDER_FULL,
    "critique_evaluator": ANCHOR_RENDER_FULL,
    "revise": ANCHOR_RENDER_FULL,
    "gate": ANCHOR_RENDER_FULL,
    "finalize": ANCHOR_RENDER_FULL,
    "review": ANCHOR_RENDER_CHECK,
    "compact_review": ANCHOR_RENDER_CHECK,
    "parallel_review": ANCHOR_RENDER_CHECK,
    "parallel_critique": ANCHOR_RENDER_CHECK,
    "execute": ANCHOR_RENDER_NONE,
    "execute-batch": ANCHOR_RENDER_NONE,
    "feedback": ANCHOR_RENDER_NONE,
}

_SCOPE_FILENAME = {"epic": "epic.md", "plan": "plan.md"}
_SCOPE_TITLE = {"epic": "Epic North Star", "plan": "Plan North Star"}
_SCOPE_ORDER = {"epic": 0, "plan": 1}


@dataclass(frozen=True)
class AnchorCaptureRequest:
    anchor_type: str
    scope: str
    source_path: Path
    source_kind: str
    label: str | None = None
    source_spec_path: Path | None = None


@dataclass(frozen=True)
class AnchorDocument:
    metadata: dict[str, Any]
    content: str | None
    error: str | None = None


@dataclass(frozen=True)
class AnchorBundle:
    anchor_type: str
    documents: tuple[AnchorDocument, ...]
    combined_artifact_path: str | None
    health: str
    missing_artifacts: tuple[str, ...] = ()


def resolve_anchor_path(spec_path: Path, anchor_path: str) -> Path:
    path = Path(anchor_path).expanduser()
    return path.resolve() if path.is_absolute() else (spec_path.parent / path).resolve()


def validate_anchor_source(path: Path, *, label: str) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise CliError("missing_anchor_file", f"{label} anchor file not found: {resolved}")
    try:
        resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise CliError("invalid_anchor_file", f"{label} anchor file is not valid UTF-8: {resolved}") from exc
    except OSError as exc:
        raise CliError("invalid_anchor_file", f"{label} anchor file is not readable: {resolved}: {exc}") from exc
    return resolved


def source_path_for_metadata(source_path: Path, project_root: Path | None = None) -> str:
    resolved = source_path.expanduser().resolve()
    if project_root is not None:
        try:
            return str(resolved.relative_to(project_root.expanduser().resolve()))
        except ValueError:
            pass
    return str(resolved)


def extract_anchor_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and stripped[2:].strip():
            return stripped[2:].strip()
    return fallback


def _emit_anchor_event(plan_dir: Path, payload: Mapping[str, Any]) -> None:
    try:
        from arnold_pipelines.megaplan.observability.events import emit

        emit("anchor_captured", plan_dir=plan_dir, payload=dict(payload))
    except Exception:
        # Observability is best-effort; anchor capture itself is load-bearing.
        return


def capture_anchor_document(
    *,
    plan_dir: Path,
    anchor_type: str,
    scope: str,
    source_path: Path,
    source_kind: str,
    label: str | None = None,
    source_spec_path: Path | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    if anchor_type not in SUPPORTED_ANCHOR_TYPES:
        raise CliError("invalid_anchor", f"unsupported anchor type: {anchor_type}")
    if scope not in _SCOPE_FILENAME:
        raise CliError("invalid_anchor", f"unsupported anchor scope: {scope}")
    if source_kind not in {"chain", "milestone", "cli"}:
        raise CliError("invalid_anchor", f"unsupported anchor source_kind: {source_kind}")
    source = validate_anchor_source(source_path, label=f"{scope} {anchor_type}")
    content = source.read_text(encoding="utf-8")
    artifact_rel = Path("anchors") / anchor_type / _SCOPE_FILENAME[scope]
    artifact_path = plan_dir / artifact_rel
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    if artifact_path.exists():
        raise CliError("duplicate_anchor", f"{anchor_type} already has a captured {scope} anchor")
    artifact_path.write_text(content, encoding="utf-8")
    payload = artifact_path.read_bytes()
    meta: dict[str, Any] = {
        "scope": scope,
        "source_kind": source_kind,
        "source_path": source_path_for_metadata(source, project_root),
        "artifact_path": artifact_rel.as_posix(),
        "title": extract_anchor_title(content, _SCOPE_TITLE[scope]),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    if label:
        meta["label"] = label
    if source_spec_path is not None:
        meta["source_spec_path"] = source_path_for_metadata(source_spec_path, project_root)
    _emit_anchor_event(
        plan_dir,
        {
            "anchor_type": anchor_type,
            "scope": scope,
            "source_kind": source_kind,
            "source_path": meta["source_path"],
            "artifact_path": meta["artifact_path"],
            "sha256": meta["sha256"],
            "size_bytes": meta["size_bytes"],
        },
    )
    return meta


def attach_anchor_documents(
    *,
    plan_dir: Path,
    state: MutableMapping[str, Any],
    documents: Sequence[AnchorCaptureRequest],
    project_root: Path | None = None,
) -> MutableMapping[str, Any]:
    if not documents:
        return state
    meta = state.setdefault("meta", {})
    if not isinstance(meta, MutableMapping):
        state["meta"] = meta = {}
    anchors_meta = meta.setdefault("anchors", {"schema_version": ANCHORS_SCHEMA_VERSION, "by_type": {}})
    if not isinstance(anchors_meta, MutableMapping):
        anchors_meta = {"schema_version": ANCHORS_SCHEMA_VERSION, "by_type": {}}
        meta["anchors"] = anchors_meta
    by_type = anchors_meta.setdefault("by_type", {})
    if not isinstance(by_type, MutableMapping):
        by_type = {}
        anchors_meta["by_type"] = by_type
    existing: dict[str, set[str]] = {}
    for anchor_type, type_meta in list(by_type.items()):
        docs = type_meta.get("documents") if isinstance(type_meta, Mapping) else None
        if isinstance(docs, list):
            existing[str(anchor_type)] = {
                str(doc.get("scope"))
                for doc in docs
                if isinstance(doc, Mapping) and isinstance(doc.get("scope"), str)
            }
    grouped: dict[str, list[dict[str, Any]]] = {}
    for request in documents:
        scopes = existing.setdefault(request.anchor_type, set())
        if request.scope in scopes:
            raise CliError("duplicate_anchor", f"{request.anchor_type} already has a {request.scope} anchor")
        metadata = capture_anchor_document(
            plan_dir=plan_dir,
            anchor_type=request.anchor_type,
            scope=request.scope,
            source_path=request.source_path,
            source_kind=request.source_kind,
            label=request.label,
            source_spec_path=request.source_spec_path,
            project_root=project_root,
        )
        grouped.setdefault(request.anchor_type, []).append(metadata)
        scopes.add(request.scope)
    for anchor_type, docs in grouped.items():
        type_meta = by_type.setdefault(anchor_type, {"anchor_type": anchor_type, "documents": []})
        if not isinstance(type_meta, MutableMapping):
            type_meta = {"anchor_type": anchor_type, "documents": []}
            by_type[anchor_type] = type_meta
        all_docs = type_meta.setdefault("documents", [])
        if not isinstance(all_docs, list):
            all_docs = []
            type_meta["documents"] = all_docs
        all_docs.extend(docs)
        all_docs.sort(key=lambda doc: (_SCOPE_ORDER.get(str(doc.get("scope")), 99), str(doc.get("artifact_path", ""))))
        combined_rel = Path("anchors") / anchor_type / "combined.md"
        type_meta["combined_artifact_path"] = combined_rel.as_posix()
        _write_combined_anchor(plan_dir, anchor_type, all_docs)
    anchors_meta["schema_version"] = ANCHORS_SCHEMA_VERSION
    return state


def _write_combined_anchor(plan_dir: Path, anchor_type: str, documents: Sequence[Mapping[str, Any]]) -> None:
    sections: list[str] = []
    for metadata in documents:
        artifact_rel = metadata.get("artifact_path")
        if not isinstance(artifact_rel, str):
            continue
        label = _anchor_document_heading(metadata)
        title = metadata.get("title") if isinstance(metadata.get("title"), str) else label
        try:
            content = (plan_dir / artifact_rel).read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError):
            content = ""
        sections.append(f"## {label}: {title}\n\n{content}".rstrip())
    combined_path = plan_dir / "anchors" / anchor_type / "combined.md"
    combined_path.parent.mkdir(parents=True, exist_ok=True)
    combined_path.write_text("\n\n".join(section for section in sections if section) + "\n", encoding="utf-8")


def load_anchor_bundle(state: Mapping[str, Any], plan_dir: Path, *, anchor_type: str = DEFAULT_ANCHOR_TYPE) -> AnchorBundle | None:
    meta = state.get("meta")
    anchors_meta = meta.get("anchors") if isinstance(meta, Mapping) else None
    by_type = anchors_meta.get("by_type") if isinstance(anchors_meta, Mapping) else None
    type_meta = by_type.get(anchor_type) if isinstance(by_type, Mapping) else None
    docs = type_meta.get("documents") if isinstance(type_meta, Mapping) else None
    if not isinstance(docs, list):
        return None
    documents: list[AnchorDocument] = []
    missing: list[str] = []
    for raw_doc in docs:
        if not isinstance(raw_doc, Mapping):
            continue
        metadata = dict(raw_doc)
        artifact_rel = metadata.get("artifact_path")
        if not isinstance(artifact_rel, str):
            continue
        try:
            content = (plan_dir / artifact_rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            missing.append(artifact_rel)
            documents.append(AnchorDocument(metadata, None, str(exc)))
        else:
            documents.append(AnchorDocument(metadata, content))
    documents.sort(key=lambda doc: (_SCOPE_ORDER.get(str(doc.metadata.get("scope")), 99), str(doc.metadata.get("artifact_path", ""))))
    combined = type_meta.get("combined_artifact_path")
    return AnchorBundle(anchor_type, tuple(documents), combined if isinstance(combined, str) else None, "missing_artifact" if missing else "ok", tuple(missing))


def anchor_summary(state: Mapping[str, Any], plan_dir: Path) -> dict[str, Any]:
    meta = state.get("meta") if isinstance(state, Mapping) else None
    anchors_meta = meta.get("anchors") if isinstance(meta, Mapping) else None
    by_type = anchors_meta.get("by_type") if isinstance(anchors_meta, Mapping) else None
    if not isinstance(by_type, Mapping) or not by_type:
        return {"present": False, "types": []}
    payload: dict[str, Any] = {"present": True, "types": sorted(str(key) for key in by_type)}
    for anchor_type in payload["types"]:
        bundle = load_anchor_bundle(state, plan_dir, anchor_type=anchor_type)
        if bundle is None:
            payload[anchor_type] = {"health": "invalid_metadata", "documents_count": 0, "scopes": []}
            continue
        payload[anchor_type] = {
            "health": bundle.health,
            "documents_count": len(bundle.documents),
            "scopes": [str(doc.metadata.get("scope")) for doc in bundle.documents if isinstance(doc.metadata.get("scope"), str)],
            "combined_artifact_path": bundle.combined_artifact_path,
            "documents": [dict(doc.metadata) for doc in bundle.documents],
        }
        if bundle.missing_artifacts:
            payload[anchor_type]["missing_artifacts"] = list(bundle.missing_artifacts)
            payload[anchor_type]["suggested_command"] = "megaplan anchors show --plan <name>"
    return payload


def render_anchor_block(
    state: Mapping[str, Any],
    plan_dir: Path,
    *,
    audience: str,
    max_chars_per_document: int = 10000,
    max_total_chars: int = 18000,
) -> str:
    bundle = load_anchor_bundle(state, plan_dir)
    if bundle is None or not bundle.documents:
        return ""
    instruction = ANCHOR_AUDIENCE_INSTRUCTIONS.get(audience, ANCHOR_AUDIENCE_INSTRUCTIONS["generic"])
    milestone_label = _current_milestone_label(state, bundle.documents)
    lines = [
        "## Anchor Context: North Star",
        "",
        "These anchors are durable alignment targets captured at plan initialization. They are not ordinary notes, generated success criteria, or optional background. Use them to keep this stage aligned with the end-state intent.",
        "",
        "Scope map:",
        "- Epic North Star: overall chain/epic objective. Preserve this across all milestones.",
        "- Plan/Sprint/Milestone North Star: current plan or milestone objective. It extends or operationalizes the epic North Star for this sprint; it does not override it.",
        "",
        "If local instructions, generated plan content, or a plan-level anchor appear to conflict with an epic anchor, do not resolve the conflict silently. Surface an explicit anchor conflict and explain what decision, replan, or user approval would be needed.",
    ]
    for document in bundle.documents:
        scope = str(document.metadata.get("scope") or "plan")
        heading = _anchor_document_heading(document.metadata)
        title = document.metadata.get("title") if isinstance(document.metadata.get("title"), str) else heading
        artifact = document.metadata.get("artifact_path", "unknown")
        lines.extend(["", f"### {heading}: {title}", f"Source: `{document.metadata.get('source_path', 'unknown')}`", f"Captured artifact: `{artifact}`", f"Checksum: `{document.metadata.get('sha256', 'unknown')}`", "", "```md"])
        if document.content is None:
            lines.append(f"Anchor metadata exists for north_star, but the captured artifact could not be read: {artifact}. Treat this as an orchestration defect and flag it.")
        else:
            lines.append(_truncate_document(document.content, max_chars_per_document, str(artifact)))
        lines.append("```")
    current_stage_lines = ["", "### Current Stage", f"Stage: `{audience}`", f"Plan directory: `{plan_dir}`"]
    if milestone_label:
        current_stage_lines.append(f"Current milestone: `{milestone_label}`")
    lines.extend(current_stage_lines)
    lines.extend(["", "### Phase Instruction", instruction, "", "### Conflict Note", "Plan-level anchors extend epic anchors. They do not override them silently. When in doubt, flag the tension rather than optimizing around it."])
    block = "\n".join(lines).strip()
    if len(block) <= max_total_chars:
        return block
    suffix = "\n\n[Anchor block truncated; captured full copies are available under the plan `anchors/` directory.]"
    return block[: max(0, max_total_chars - len(suffix))].rstrip() + suffix


def render_anchor_context(
    state: Mapping[str, Any],
    plan_dir: Path,
    *,
    audience: str,
    mode: str | None = None,
    max_chars_per_document: int = 10000,
    max_total_chars: int = 18000,
) -> str:
    resolved_mode = mode or ANCHOR_AUDIENCE_RENDER_MODES.get(audience, ANCHOR_RENDER_FULL)
    if resolved_mode == ANCHOR_RENDER_NONE:
        return ""
    if resolved_mode == ANCHOR_RENDER_FULL:
        return render_anchor_block(
            state,
            plan_dir,
            audience=audience,
            max_chars_per_document=max_chars_per_document,
            max_total_chars=max_total_chars,
        )
    if resolved_mode == ANCHOR_RENDER_CHECK:
        return _render_anchor_check_block(state, plan_dir)
    raise CliError("invalid_anchor_mode", f"unsupported anchor render mode: {resolved_mode}")


def _render_anchor_check_block(state: Mapping[str, Any], plan_dir: Path) -> str:
    bundle = load_anchor_bundle(state, plan_dir)
    if bundle is None or not bundle.documents:
        return ""
    milestone_label = _current_milestone_label(state, bundle.documents)
    lines = [
        "## Anchor Check: North Star",
        "",
        "One or more North Stars are captured for this plan.",
        "",
        "Captured anchors:",
    ]
    for document in bundle.documents:
        lines.append(
            f"- {_anchor_check_label(document.metadata, milestone_label)}: `{document.metadata.get('artifact_path', 'unknown')}`"
        )
    lines.extend(
        [
            "",
            "Do not restate the North Star. Do not reinterpret approved scope from scratch.",
            "Raise an explicit anchor conflict/deviation only if the current step visibly violates a captured North Star.",
        ]
    )
    return "\n".join(lines)


def _anchor_document_heading(metadata: Mapping[str, Any]) -> str:
    scope = str(metadata.get("scope") or "plan")
    heading = _SCOPE_TITLE.get(scope, "North Star")
    label = metadata.get("label")
    source_kind = metadata.get("source_kind")
    if scope == "plan" and (source_kind == "milestone" or isinstance(label, str)):
        if isinstance(label, str) and label.strip():
            return f"{heading} (current milestone {label.strip()})"
        return f"{heading} (current milestone)"
    return heading


def _anchor_check_label(metadata: Mapping[str, Any], milestone_label: str | None) -> str:
    scope = str(metadata.get("scope") or "plan")
    if scope == "epic":
        return "Epic North Star (overall chain/epic objective)"
    label = metadata.get("label")
    if not isinstance(label, str) or not label.strip():
        label = milestone_label
    if isinstance(label, str) and label.strip():
        return f"Sprint/Milestone North Star (current milestone {label.strip()})"
    return "Sprint/Milestone North Star (current plan/milestone objective)"


def _current_milestone_label(state: Mapping[str, Any], documents: Sequence[AnchorDocument]) -> str | None:
    meta = state.get("meta") if isinstance(state, Mapping) else None
    chain_policy = meta.get("chain_policy") if isinstance(meta, Mapping) else None
    label = chain_policy.get("milestone_label") if isinstance(chain_policy, Mapping) else None
    if isinstance(label, str) and label.strip():
        return label.strip()
    for document in documents:
        doc_label = document.metadata.get("label")
        if isinstance(doc_label, str) and doc_label.strip():
            return doc_label.strip()
    return None


def _truncate_document(content: str, max_chars: int, artifact_path: str) -> str:
    if len(content) <= max_chars:
        return content.rstrip()
    return content[:max_chars].rstrip() + f"\n\n[Anchor document truncated from {len(content)} to {max_chars} characters. The captured full copy is available at `{artifact_path}`.]"


def anchor_show_payload(state: Mapping[str, Any], plan_dir: Path, *, anchor_type: str = DEFAULT_ANCHOR_TYPE, max_content_chars: int = 50000) -> dict[str, Any]:
    bundle = load_anchor_bundle(state, plan_dir, anchor_type=anchor_type)
    if bundle is None:
        return {"present": False, "anchor_type": anchor_type, "health": "absent", "documents": [], "combined_content": ""}
    docs: list[dict[str, Any]] = []
    for document in bundle.documents:
        item = dict(document.metadata)
        content = document.content or ""
        item["content"] = content[:max_content_chars]
        item["truncated"] = len(content) > max_content_chars
        if document.error:
            item["error"] = document.error
        docs.append(item)
    combined = ""
    combined_truncated = False
    if bundle.combined_artifact_path:
        try:
            combined = (plan_dir / bundle.combined_artifact_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            combined = ""
        combined_truncated = len(combined) > max_content_chars
        combined = combined[:max_content_chars]
    return {"present": bool(docs), "anchor_type": anchor_type, "health": bundle.health, "documents": docs, "combined_artifact_path": bundle.combined_artifact_path, "combined_content": combined, "combined_truncated": combined_truncated, "missing_artifacts": list(bundle.missing_artifacts)}


def format_anchor_show_text(plan_name: str, payload: Mapping[str, Any]) -> str:
    anchor_type = payload.get("anchor_type", DEFAULT_ANCHOR_TYPE)
    lines = [f"Plan: {plan_name}", f"Anchor type: {anchor_type}", f"Health: {payload.get('health', 'unknown')}", "", "Documents:"]
    documents = payload.get("documents")
    if not isinstance(documents, list) or not documents:
        lines.append("- none")
    else:
        for doc in documents:
            if not isinstance(doc, Mapping):
                continue
            lines.extend([f"- scope: {doc.get('scope', 'unknown')}", f"  title: {doc.get('title', '')}", f"  source: {doc.get('source_path', '')}", f"  captured: {doc.get('artifact_path', '')}", f"  sha256: {doc.get('sha256', '')}", f"  size_bytes: {doc.get('size_bytes', '')}"])
            if doc.get("error"):
                lines.append(f"  error: {doc.get('error')}")
    combined = payload.get("combined_content")
    if isinstance(combined, str) and combined:
        lines.extend(["", "--- Combined North Star ---", combined.rstrip()])
    return "\n".join(lines).rstrip() + "\n"


def dumps_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"
