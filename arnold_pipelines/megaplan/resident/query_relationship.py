"""Durable, bounded classification of resident query relationships.

Automatic folding is deliberately conservative: only immutable Discord reply
ancestry, resolved against authoritative conversation records, may establish a
follow-up. Nearby/hot excerpts and lexical similarity are never sufficient.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.schemas import Message, ResidentConversation
from agentbox.redaction import redact_text

from .request_summary import canonical_request_description


QUERY_RELATIONSHIP_SCHEMA = "arnold-resident-query-relationship-v1"
MAX_AUTHORITATIVE_MESSAGES = 200


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ref(message: Message) -> dict[str, str | None]:
    return {
        "source_record_id": message.id,
        "discord_message_id": message.discord_message_id,
        "source_content_sha256": hashlib.sha256(
            message.content.encode("utf-8")
        ).hexdigest(),
    }


def _author_id(message: Message) -> str:
    provenance = message.discord_reply_provenance
    return (
        str(provenance.get("source_author_id") or "")
        if isinstance(provenance, Mapping)
        else ""
    )


def _bounded_rationale(value: object) -> str:
    normalized = " ".join(redact_text(str(value or "")).split())
    if not normalized:
        raise ValueError("semantic follow-up rationale is required")
    if len(normalized) > 300:
        raise ValueError("semantic follow-up rationale exceeds 300 characters")
    return normalized


def _relationship_root(record: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if not isinstance(record, Mapping):
        return None
    root = record.get("root_request")
    return root if isinstance(root, Mapping) else None


def relationship_store_root(store: object, project_root: str | Path) -> Path:
    configured = getattr(store, "root", None)
    if configured is not None:
        return Path(configured).resolve()
    return Path(project_root).resolve() / ".megaplan" / "resident"


def relationship_path(store_root: str | Path, source_record_id: str) -> Path:
    return Path(store_root) / "query_relationships" / f"{source_record_id}.json"


def load_query_relationship(
    source_record_id: str,
    *,
    store_root: str | Path,
) -> dict[str, Any] | None:
    path = relationship_path(store_root, source_record_id)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return None
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != QUERY_RELATIONSHIP_SCHEMA
        or (value.get("current_request") or {}).get("source_record_id")
        != source_record_id
    ):
        return None
    return value


def persist_query_relationship(
    relationship: Mapping[str, Any],
    *,
    store_root: str | Path,
) -> Path:
    current = relationship.get("current_request")
    source_record_id = (
        str(current.get("source_record_id") or "")
        if isinstance(current, Mapping)
        else ""
    )
    if not source_record_id:
        raise ValueError("query relationship current source record is required")
    path = relationship_path(store_root, source_record_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = load_query_relationship(source_record_id, store_root=store_root)
        if existing != dict(relationship):
            raise ValueError("query relationship classification is already immutable")
        return path
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(dict(relationship), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def classify_query_relationship(
    *,
    store: Any,
    conversation: ResidentConversation,
    current: Message,
    project_root: str | Path,
) -> dict[str, Any]:
    """Classify one query from bounded authoritative records.

    Explicit reply ancestry is high-confidence evidence. If its immediate
    parent is an inbound user query in this conversation, the query is folded.
    If it is an outbound resident message, its owning turn is resolved back to
    the authoritative inbound query that triggered it. All other cases remain
    independent rather than guessing from semantic similarity.
    """

    store_root = relationship_store_root(store, project_root)
    existing = load_query_relationship(current.id, store_root=store_root)
    if existing is not None:
        return existing

    records = store.list_conversation_messages(
        conversation.id,
        limit=MAX_AUTHORITATIVE_MESSAGES,
        exclude_ids=[current.id],
    )
    parent: Message | None = None
    provenance = current.discord_reply_provenance
    if isinstance(provenance, Mapping):
        ancestors = provenance.get("ancestors")
        immediate = ancestors[0] if isinstance(ancestors, list) and ancestors else None
        if isinstance(immediate, Mapping) and immediate.get("status") == "available":
            parent_id = str(immediate.get("message_id") or "")
            if parent_id:
                parent = store.find_conversation_message_by_discord_id(
                    conversation.id, parent_id
                )

    earlier: Message | None = None
    basis = "no_authoritative_reply_relationship"
    if parent is not None and parent.conversation_id == conversation.id:
        current_author = (
            str(provenance.get("source_author_id") or "")
            if isinstance(provenance, Mapping)
            else ""
        )
        parent_provenance = parent.discord_reply_provenance
        parent_author = (
            str(parent_provenance.get("source_author_id") or "")
            if isinstance(parent_provenance, Mapping)
            else ""
        )
        if (
            parent.direction == "inbound"
            and current_author
            and parent_author == current_author
        ):
            earlier = parent
            basis = "immutable_reply_to_inbound_query"
        elif parent.direction == "outbound" and parent.bot_turn_id:
            for turn in store.list_recent_turns(n=1000):
                if turn.id != parent.bot_turn_id:
                    continue
                candidates = store.load_messages(turn.triggered_by_message_ids)
                earlier = next(
                    (
                        message
                        for message in reversed(candidates)
                        if message.direction == "inbound"
                        and message.conversation_id == conversation.id
                    ),
                    None,
                )
                if earlier is not None and _author_id(earlier) == current_author:
                    basis = "immutable_reply_to_resident_turn_for_inbound_query"
                else:
                    earlier = None
                break

    earlier_relationship = (
        load_query_relationship(earlier.id, store_root=store_root)
        if earlier is not None
        else None
    )
    root = _relationship_root(earlier_relationship)
    root_ref = dict(root) if root is not None else _ref(earlier or current)
    current_ref = _ref(current)
    classification = "follow_up" if earlier is not None else "independent"
    relationship: dict[str, Any] = {
        "schema_version": QUERY_RELATIONSHIP_SCHEMA,
        "classification": classification,
        "classification_basis": basis,
        "classified_at": _utc_now(),
        "authority": "authoritative_conversation_records_and_immutable_discord_provenance",
        "conversation_id": conversation.id,
        "records_inspected": len(records),
        "records_limit": MAX_AUTHORITATIVE_MESSAGES,
        "root_request": root_ref,
        "current_request": current_ref,
        "delivery_owner": current_ref,
        "aggregation_owner": current_ref,
    }
    if earlier is not None:
        relationship["earlier_request"] = _ref(earlier)
    path = relationship_path(store_root, current.id)
    relationship["evidence_path"] = str(path)
    persist_query_relationship(relationship, store_root=store_root)
    return relationship


def correlate_semantic_follow_up(
    *,
    store: Any,
    conversation: ResidentConversation,
    current_source_record_id: str,
    earlier_source_record_id: str | None,
    semantic_description: object,
    rationale: object | None = None,
    project_root: str | Path,
) -> dict[str, Any]:
    """Enrich or safely promote a relationship from an explicit model judgment.

    The model supplies only a candidate record id and semantic metadata.  This
    function re-resolves both records authoritatively and fails closed across
    author, conversation, ordering, or existing-relationship conflicts.
    """

    description = canonical_request_description(semantic_description)
    if description is None:
        raise ValueError("semantic request description is required")
    current = store.load_message(current_source_record_id)
    if (
        current is None
        or current.direction != "inbound"
        or current.conversation_id != conversation.id
    ):
        raise ValueError("current semantic relationship source is unavailable")
    earlier = store.load_message(earlier_source_record_id) if earlier_source_record_id else None
    if earlier is not None and (
        earlier.direction != "inbound"
        or earlier.conversation_id != conversation.id
        or earlier.id == current.id
        or earlier.sent_at > current.sent_at
        or not _author_id(current)
        or _author_id(earlier) != _author_id(current)
    ):
        raise ValueError("semantic follow-up candidate violates authoritative custody")
    if earlier_source_record_id and earlier is None:
        raise ValueError("semantic follow-up candidate is unavailable")

    store_root = relationship_store_root(store, project_root)
    path = relationship_path(store_root, current.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(".lock")
    with lock_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        existing = load_query_relationship(current.id, store_root=store_root)
        if existing is None:
            existing = classify_query_relationship(
                store=store,
                conversation=conversation,
                current=current,
                project_root=project_root,
            )
        existing_current = existing.get("current_request")
        if earlier is None and isinstance(existing_current, Mapping) and (
            existing_current.get("description") == description
        ):
            return existing
        normalized_rationale = _bounded_rationale(rationale) if earlier is not None else None
        existing_semantic = existing.get("semantic_judgment")
        existing_earlier = existing.get("earlier_request")
        if (
            earlier is not None
            and isinstance(existing_earlier, Mapping)
            and existing_earlier.get("source_record_id") == earlier.id
            and isinstance(existing_current, Mapping)
            and existing_current.get("description") == description
            and isinstance(existing_semantic, Mapping)
            and existing_semantic.get("rationale") == normalized_rationale
        ):
            return existing
        relationship = dict(existing)
        current_ref = _ref(current)
        current_ref["description"] = description
        relationship["current_request"] = current_ref
        relationship["delivery_owner"] = dict(current_ref)
        relationship["aggregation_owner"] = dict(current_ref)

        if earlier is not None:
            existing_earlier = _relationship_root(existing)
            existing_ref = existing.get("earlier_request")
            if existing.get("classification") == "follow_up" and isinstance(
                existing_ref, Mapping
            ) and str(existing_ref.get("source_record_id") or "") != earlier.id:
                raise ValueError("semantic follow-up conflicts with immutable reply ancestry")
            earlier_relationship = load_query_relationship(
                earlier.id, store_root=store_root
            )
            root = _relationship_root(earlier_relationship) or existing_earlier
            relationship.update(
                {
                    "classification": "follow_up",
                    "classification_basis": (
                        existing.get("classification_basis")
                        if str(existing.get("classification_basis") or "").startswith(
                            "immutable_reply_"
                        )
                        else "resident_model_semantic_judgment"
                    ),
                    "root_request": dict(root) if root is not None else _ref(earlier),
                    "earlier_request": _ref(earlier),
                    "semantic_judgment": {
                        "source": "resident_model_launch_tool",
                        "description": description,
                        "rationale": normalized_rationale,
                        "judged_at": _utc_now(),
                    },
                }
            )
        relationship["updated_at"] = _utc_now()
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(relationship, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
        return relationship


def relationship_from_environment_or_project(
    source_record_id: str | None,
    *,
    project_root: str | Path,
) -> dict[str, Any] | None:
    if not source_record_id:
        return None
    import os

    configured = str(os.environ.get("MEGAPLAN_RESIDENT_STORE_ROOT") or "").strip()
    store_root = (
        Path(configured).resolve()
        if configured
        else Path(project_root).resolve() / ".megaplan" / "resident"
    )
    return load_query_relationship(source_record_id, store_root=store_root)
