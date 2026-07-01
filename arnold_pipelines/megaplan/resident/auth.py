"""Authorization primitives for resident inbound events and tool actions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import secrets
from typing import Any, Literal

from arnold_pipelines.megaplan.store.base import JSONDict, ScheduledJobInput, Store, deterministic_idempotency_key

from .config import ResidentConfig

ActionKind = Literal[
    "read",
    "write",
    "cloud_start",
    "cloud_read",
    "admin",
    "repo_write",
    "artifact_write",
    "export",
    "archive_logs",
    "reconcile_apply",
]
ConfirmationStatus = Literal["pending", "approved", "denied", "expired"]

HIGH_IMPACT_ACTIONS: frozenset[ActionKind] = frozenset(
    {
        "cloud_start",
        "admin",
        "repo_write",
        "artifact_write",
        "export",
        "archive_logs",
        "reconcile_apply",
    }
)

CONFIRMED_HIGH_IMPACT_ACTIONS: frozenset[ActionKind] = frozenset(
    {
        "repo_write",
        "artifact_write",
        "export",
        "archive_logs",
        "reconcile_apply",
    }
)


@dataclass(frozen=True)
class AuthorizationSubject:
    user_id: str
    guild_id: str | None = None
    channel_id: str | None = None


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    reason: str | None = None
    audit: dict[str, object] | None = None


@dataclass(frozen=True)
class AuthorizationDenialRecord:
    user_id: str
    guild_id: str | None
    channel_id: str | None
    action: str
    reason: str
    occurred_at: datetime

    def redacted(self) -> JSONDict:
        return {
            "user_id": self.user_id,
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "action": self.action,
            "reason": self.reason,
            "occurred_at": self.occurred_at.isoformat().replace("+00:00", "Z"),
        }


@dataclass(frozen=True)
class ConfirmationRequest:
    id: str
    subject: AuthorizationSubject
    action: ActionKind
    target_summary: str
    exact_phrase: str
    expires_at: datetime
    metadata: JSONDict
    created_at: datetime


@dataclass(frozen=True)
class ConfirmationDecision:
    status: ConfirmationStatus
    allowed: bool
    request_id: str | None = None
    reason: str | None = None


class ResidentAuthorizer:
    """Allowlist-based authorization with admin checks for side effects."""

    def __init__(self, config: ResidentConfig) -> None:
        self.config = config
        self.denials: list[AuthorizationDenialRecord] = []

    def authorize_inbound(self, subject: AuthorizationSubject) -> AuthorizationDecision:
        if self.config.allowed_user_ids and subject.user_id not in self.config.allowed_user_ids:
            return self._deny(subject, "inbound", "user_not_allowed")
        if (
            self.config.allowed_guild_ids
            and subject.guild_id is not None
            and subject.guild_id not in self.config.allowed_guild_ids
        ):
            return self._deny(subject, "inbound", "guild_not_allowed")
        if self.config.allowed_channel_ids and subject.channel_id not in self.config.allowed_channel_ids:
            return self._deny(subject, "inbound", "channel_not_allowed")
        return AuthorizationDecision(True)

    def authorize_action(self, subject: AuthorizationSubject, action: ActionKind) -> AuthorizationDecision:
        inbound = self.authorize_inbound(subject)
        if not inbound.allowed:
            return inbound
        if action in HIGH_IMPACT_ACTIONS and subject.user_id not in self.config.admin_user_ids:
            return self._deny(subject, action, "admin_required")
        return AuthorizationDecision(True)

    def _deny(self, subject: AuthorizationSubject, action: str, reason: str) -> AuthorizationDecision:
        denial = AuthorizationDenialRecord(
            user_id=subject.user_id,
            guild_id=subject.guild_id,
            channel_id=subject.channel_id,
            action=action,
            reason=reason,
            occurred_at=datetime.now(UTC),
        )
        self.denials.append(denial)
        return AuthorizationDecision(False, reason, audit=denial.redacted())


class ConfirmationManager:
    """Exact-phrase confirmation guard for high-impact resident actions."""

    def __init__(self, config: ResidentConfig) -> None:
        self.config = config
        self._pending: dict[str, ConfirmationRequest] = {}

    def required_for(self, action: ActionKind) -> bool:
        if action == "cloud_start":
            return self.config.require_cloud_start_confirmation
        return action in CONFIRMED_HIGH_IMPACT_ACTIONS

    def request_confirmation(
        self,
        *,
        subject: AuthorizationSubject,
        action: ActionKind,
        target_summary: str,
        metadata: JSONDict | None = None,
        now: datetime | None = None,
    ) -> ConfirmationRequest:
        created_at = _aware_now(now)
        seed = f"{subject.user_id}:{action}:{target_summary}:{created_at.isoformat()}:{secrets.token_hex(4)}"
        request_id = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
        exact_phrase = f"confirm {action} {request_id}"
        if action == "cloud_start":
            exact_phrase = f"{exact_phrase} {target_summary}"
        request = ConfirmationRequest(
            id=request_id,
            subject=subject,
            action=action,
            target_summary=target_summary,
            exact_phrase=exact_phrase,
            expires_at=created_at + timedelta(seconds=self.config.confirmation_expiry_s),
            metadata=dict(metadata or {}),
            created_at=created_at,
        )
        self._pending[request.id] = request
        return request

    def confirm(
        self,
        *,
        request_id: str,
        subject: AuthorizationSubject,
        phrase: str,
        now: datetime | None = None,
    ) -> ConfirmationDecision:
        request = self._pending.get(request_id)
        if request is None:
            return ConfirmationDecision("denied", False, request_id=request_id, reason="confirmation_not_found")
        current = _aware_now(now)
        if request.expires_at <= current:
            self._pending.pop(request_id, None)
            return ConfirmationDecision("expired", False, request_id=request_id, reason="confirmation_expired")
        if request.subject.user_id != subject.user_id:
            return ConfirmationDecision("denied", False, request_id=request_id, reason="confirmation_user_mismatch")
        if phrase.strip() != request.exact_phrase:
            return ConfirmationDecision("denied", False, request_id=request_id, reason="confirmation_phrase_mismatch")
        self._pending.pop(request_id, None)
        return ConfirmationDecision("approved", True, request_id=request_id)

    def expire_due(self, *, now: datetime | None = None) -> list[ConfirmationRequest]:
        current = _aware_now(now)
        expired = [request for request in self._pending.values() if request.expires_at <= current]
        for request in expired:
            self._pending.pop(request.id, None)
        return sorted(expired, key=lambda request: (request.expires_at, request.id))

    def pending(self) -> tuple[ConfirmationRequest, ...]:
        return tuple(sorted(self._pending.values(), key=lambda request: (request.expires_at, request.id)))


class StoreBackedConfirmationManager(ConfirmationManager):
    """Confirmation manager that persists pending requests as scheduled jobs."""

    def __init__(self, config: ResidentConfig, store: Store) -> None:
        super().__init__(config)
        self.store = store

    def request_confirmation(
        self,
        *,
        subject: AuthorizationSubject,
        action: ActionKind,
        target_summary: str,
        metadata: JSONDict | None = None,
        now: datetime | None = None,
    ) -> ConfirmationRequest:
        request = super().request_confirmation(
            subject=subject,
            action=action,
            target_summary=target_summary,
            metadata=metadata,
            now=now,
        )
        self.store.create_scheduled_job(
            ScheduledJobInput(
                job_type="confirmation_expiry",
                payload={"confirmation": _confirmation_to_payload(request)},
                scheduled_for=request.expires_at,
                max_attempts=1,
            ),
            idempotency_key=deterministic_idempotency_key("resident-confirmation-request", request.id),
        )
        return request

    def confirm(
        self,
        *,
        request_id: str,
        subject: AuthorizationSubject,
        phrase: str,
        now: datetime | None = None,
    ) -> ConfirmationDecision:
        self._hydrate_request(request_id)
        decision = super().confirm(request_id=request_id, subject=subject, phrase=phrase, now=now)
        if decision.allowed:
            self._complete_confirmation_job(request_id, "fired")
        elif decision.status == "expired":
            self._complete_confirmation_job(request_id, "cancelled")
        return decision

    def expire_due(self, *, now: datetime | None = None) -> list[ConfirmationRequest]:
        current = _aware_now(now)
        expired: list[ConfirmationRequest] = []
        for job in self.store.list_scheduled_jobs(job_type="confirmation_expiry", limit=1000):
            if job.status not in {"pending", "claimed"}:
                continue
            request = _confirmation_from_payload(job.payload.get("confirmation"))
            if request is None or request.expires_at > current:
                continue
            expired.append(request)
            self._pending.pop(request.id, None)
            self._complete_confirmation_job(request.id, "cancelled")
        expired.extend(super().expire_due(now=current))
        unique = {request.id: request for request in expired}
        return list(sorted(unique.values(), key=lambda request: (request.expires_at, request.id)))

    def pending(self) -> tuple[ConfirmationRequest, ...]:
        rows = self.store.list_scheduled_jobs(status="pending", job_type="confirmation_expiry", limit=1000)
        durable = [_confirmation_from_payload(row.payload.get("confirmation")) for row in rows]
        combined = {request.id: request for request in super().pending()}
        combined.update({request.id: request for request in durable if request is not None})
        return tuple(sorted(combined.values(), key=lambda request: (request.expires_at, request.id)))

    def _hydrate_request(self, request_id: str) -> None:
        if request_id in self._pending:
            return
        for job in self.store.list_scheduled_jobs(job_type="confirmation_expiry", limit=1000):
            if job.status not in {"pending", "claimed"}:
                continue
            request = _confirmation_from_payload(job.payload.get("confirmation"))
            if request is not None and request.id == request_id:
                self._pending[request.id] = request
                return

    def _complete_confirmation_job(self, request_id: str, status: Literal["fired", "cancelled"]) -> None:
        for job in self.store.list_scheduled_jobs(job_type="confirmation_expiry", limit=1000):
            if job.status not in {"pending", "claimed"}:
                continue
            request = _confirmation_from_payload(job.payload.get("confirmation"))
            if request is None or request.id != request_id:
                continue
            changes: dict[str, Any] = {"status": status}
            if status == "fired":
                changes["fired_at"] = datetime.now(UTC)
            else:
                changes["cancelled_at"] = datetime.now(UTC)
            self.store.update_scheduled_job(
                job.id,
                **changes,
                idempotency_key=deterministic_idempotency_key("resident-confirmation-complete", request_id, status),
            )
            return


def _aware_now(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _confirmation_to_payload(request: ConfirmationRequest) -> JSONDict:
    return {
        "id": request.id,
        "subject": {
            "user_id": request.subject.user_id,
            "guild_id": request.subject.guild_id,
            "channel_id": request.subject.channel_id,
        },
        "action": request.action,
        "target_summary": request.target_summary,
        "exact_phrase": request.exact_phrase,
        "expires_at": request.expires_at.isoformat().replace("+00:00", "Z"),
        "metadata": request.metadata,
        "created_at": request.created_at.isoformat().replace("+00:00", "Z"),
    }


def _confirmation_from_payload(payload: object) -> ConfirmationRequest | None:
    if not isinstance(payload, dict):
        return None
    subject_payload = payload.get("subject")
    if not isinstance(subject_payload, dict):
        return None
    return ConfirmationRequest(
        id=str(payload["id"]),
        subject=AuthorizationSubject(
            user_id=str(subject_payload["user_id"]),
            guild_id=_optional_str(subject_payload.get("guild_id")),
            channel_id=_optional_str(subject_payload.get("channel_id")),
        ),
        action=payload["action"],  # type: ignore[arg-type]
        target_summary=str(payload["target_summary"]),
        exact_phrase=str(payload["exact_phrase"]),
        expires_at=datetime.fromisoformat(str(payload["expires_at"]).replace("Z", "+00:00")).astimezone(UTC),
        metadata=dict(payload.get("metadata") or {}),
        created_at=datetime.fromisoformat(str(payload["created_at"]).replace("Z", "+00:00")).astimezone(UTC),
    )


def _optional_str(value: object) -> str | None:
    return None if value is None else str(value)
