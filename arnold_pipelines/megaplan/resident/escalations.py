"""Ledger-backed authorization for resident escalation answers."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Protocol

from arnold_pipelines.megaplan.store import deterministic_idempotency_key

from .auth import ActionKind, AuthorizationSubject, ConfirmationManager, ResidentAuthorizer


class EscalationAuditSink(Protocol):
    def log_system_event(
        self,
        *,
        level: str,
        category: str,
        event_type: str,
        message: str,
        details: dict[str, Any] | None = None,
        turn_id: str | None = None,
        epic_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        ...


@dataclass(frozen=True)
class EscalationTarget:
    escalation_id: str
    session: str
    target_id: str
    current_plan: str
    channel_id: str
    responder_user_id: str
    message_ids: tuple[str, ...]
    resume_handler: str = ""
    superseded: bool = False
    unavailable: bool = False


@dataclass(frozen=True)
class EscalationAnswerDecision:
    allowed: bool
    reason: str | None = None
    target: EscalationTarget | None = None


@dataclass(frozen=True)
class EscalationConfirmationDecision:
    allowed: bool
    confirmation_required: bool = False
    reason: str | None = None
    request_id: str | None = None
    exact_phrase: str | None = None


def authorize_escalation_answer(
    *,
    authorizer: ResidentAuthorizer,
    subject: AuthorizationSubject,
    action: ActionKind,
    escalation_id: str,
    repair_data_dir: str | Path,
    audit_sink: EscalationAuditSink | None = None,
    idempotency_key: str = "",
) -> EscalationAnswerDecision:
    """Authorize an answer before any resident state mutation."""

    if action not in {"escalation_reply", "escalation_resolve"}:
        raise ValueError(f"unsupported escalation action: {action}")

    action_decision = authorizer.authorize_action(subject, action)
    if not action_decision.allowed:
        _audit_denial(audit_sink, subject, action, escalation_id, action_decision.reason or "action_denied", idempotency_key)
        return EscalationAnswerDecision(False, action_decision.reason)

    target = load_escalation_target(repair_data_dir, escalation_id)
    if target is None:
        _audit_denial(audit_sink, subject, action, escalation_id, "escalation_not_found", idempotency_key)
        return EscalationAnswerDecision(False, "escalation_not_found")
    if target.superseded:
        _audit_denial(audit_sink, subject, action, escalation_id, "escalation_superseded", idempotency_key)
        return EscalationAnswerDecision(False, "escalation_superseded", target)
    if target.unavailable or not target.message_ids:
        _audit_denial(audit_sink, subject, action, escalation_id, "escalation_not_delivered", idempotency_key)
        return EscalationAnswerDecision(False, "escalation_not_delivered", target)
    if target.responder_user_id and subject.user_id != target.responder_user_id:
        _audit_denial(audit_sink, subject, action, escalation_id, "responder_user_mismatch", idempotency_key)
        return EscalationAnswerDecision(False, "responder_user_mismatch", target)
    if target.channel_id and subject.channel_id != target.channel_id:
        _audit_denial(audit_sink, subject, action, escalation_id, "responder_channel_mismatch", idempotency_key)
        return EscalationAnswerDecision(False, "responder_channel_mismatch", target)

    current_target_id = _current_marker_target_id(repair_data_dir, target.session)
    if target.target_id and current_target_id != target.target_id:
        _audit_denial(
            audit_sink,
            subject,
            action,
            escalation_id,
            "stale_target_mismatch",
            idempotency_key,
            {"expected_target_id": target.target_id, "current_target_id": current_target_id},
        )
        return EscalationAnswerDecision(False, "stale_target_mismatch", target)

    return EscalationAnswerDecision(True, target=target)


def load_escalation_target(repair_data_dir: str | Path, escalation_id: str) -> EscalationTarget | None:
    records = _read_escalation_records(repair_data_dir, escalation_id)
    if not records:
        return None

    session = ""
    target_id = ""
    current_plan = ""
    channel_id = ""
    responder_user_id = ""
    message_ids: tuple[str, ...] = ()
    resume_handler = ""
    superseded = False
    unavailable = False

    for record in records:
        event = _string(record.get("event"))
        session = _string(record.get("session")) or session
        if event == "opened":
            target_id = _string(record.get("target_id")) or target_id
            current_plan = _string(record.get("current_plan")) or current_plan
            responder_user_id = _string(record.get("dm_user_id")) or responder_user_id
            resume_handler = _string(record.get("resume_handler")) or resume_handler
        elif event == "delivered":
            channel_id = _string(record.get("channel_id")) or channel_id
            responder_user_id = _string(record.get("dm_user_id")) or responder_user_id
            resume_handler = _string(record.get("resume_handler")) or resume_handler
            raw_ids = record.get("message_ids")
            if isinstance(raw_ids, list):
                message_ids = tuple(str(item).strip() for item in raw_ids if str(item).strip())
        elif event == "superseded":
            superseded = True
        elif event == "unavailable":
            unavailable = True

    return EscalationTarget(
        escalation_id=escalation_id,
        session=session,
        target_id=target_id,
        current_plan=current_plan,
        channel_id=channel_id,
        responder_user_id=responder_user_id,
        message_ids=message_ids,
        resume_handler=resume_handler,
        superseded=superseded,
        unavailable=unavailable,
    )


def confirm_escalation_resolution(
    *,
    confirmation_manager: ConfirmationManager | None,
    subject: AuthorizationSubject,
    escalation_id: str,
    target: EscalationTarget,
    answer_text: str,
    resume_handler: str,
) -> EscalationConfirmationDecision:
    """Require exact confirmation before an escalation answer mutates repair state."""

    if confirmation_manager is None or not confirmation_manager.required_for("escalation_resolve"):
        return EscalationConfirmationDecision(True)

    pending = _pending_confirmation_for_escalation(
        confirmation_manager,
        subject=subject,
        escalation_id=escalation_id,
    )
    if pending is not None:
        decision = confirmation_manager.confirm(
            request_id=pending.id,
            subject=subject,
            phrase=answer_text,
        )
        if decision.allowed:
            return EscalationConfirmationDecision(True, request_id=pending.id)
        return EscalationConfirmationDecision(
            False,
            confirmation_required=True,
            reason=decision.reason,
            request_id=pending.id,
            exact_phrase=pending.exact_phrase,
        )

    request = confirmation_manager.request_confirmation(
        subject=subject,
        action="escalation_resolve",
        target_summary=target.current_plan or target.target_id or escalation_id,
        metadata={
            "tool": "escalation_resolve",
            "escalation_id": escalation_id,
            "resume_handler": resume_handler,
        },
    )
    return EscalationConfirmationDecision(
        False,
        confirmation_required=True,
        reason="confirmation_required",
        request_id=request.id,
        exact_phrase=request.exact_phrase,
    )


def _pending_confirmation_for_escalation(
    confirmation_manager: ConfirmationManager,
    *,
    subject: AuthorizationSubject,
    escalation_id: str,
) -> Any | None:
    for request in confirmation_manager.pending():
        if request.action != "escalation_resolve":
            continue
        if request.subject.user_id != subject.user_id:
            continue
        if _string(request.metadata.get("escalation_id")) == escalation_id:
            return request
    return None


def _read_escalation_records(repair_data_dir: str | Path, escalation_id: str) -> list[dict[str, Any]]:
    ledger_path = Path(repair_data_dir) / "escalations" / "escalations.jsonl"
    if not ledger_path.exists():
        return []
    records: list[dict[str, Any]] = []
    try:
        lines = ledger_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return records
    for raw_line in lines:
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and _string(record.get("escalation_id")) == escalation_id:
            records.append(record)
    return records


def _current_marker_target_id(repair_data_dir: str | Path, session: str) -> str:
    if not session:
        return ""
    try:
        payload = json.loads((Path(repair_data_dir) / f"{session}.needs-human.json").read_text(encoding="utf-8"))
    except Exception:
        return ""
    return _string(payload.get("target_id")) if isinstance(payload, dict) else ""


def _audit_denial(
    audit_sink: EscalationAuditSink | None,
    subject: AuthorizationSubject,
    action: str,
    escalation_id: str,
    reason: str,
    idempotency_key: str,
    extra: dict[str, Any] | None = None,
) -> None:
    if audit_sink is None:
        return
    details = {
        "reason": reason,
        "action": action,
        "escalation_id": escalation_id,
        "user_id": subject.user_id,
        "guild_id": subject.guild_id,
        "channel_id": subject.channel_id,
    }
    if extra:
        details.update(extra)
    audit_sink.log_system_event(
        level="warn",
        category="system",
        event_type="escalation_answer_unauthorized",
        message="Escalation answer denied before resident mutation",
        details=details,
        idempotency_key=deterministic_idempotency_key(
            "resident-escalation-denial",
            idempotency_key or escalation_id,
            reason,
        ),
    )


def _string(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""
