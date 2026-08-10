"""Durable, adapter-owned Discord reaction effect fencing."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import fcntl
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence
import uuid

from agentbox.redaction import redact_text


REACTION_EFFECT_SCHEMA = "arnold-resident-discord-reaction-effect-v1"
_CLAIM_LEASE_S = 60
_PHASE_ORDER = {
    "working": 0,
    "interrupted_cleanup": 1,
    "completion": 1,
    "terminal_cleanup": 2,
}


@dataclass(frozen=True)
class ReactionEffectSweepResult:
    scanned: int = 0
    applied: int = 0
    retry_pending: int = 0
    skipped: int = 0


class DiscordReactionEffectLedger:
    """Small JSON outbox for Discord reaction effects.

    Discord's reaction endpoints are idempotent for one bot/emoji/message
    tuple.  This ledger adds durable intent, retry evidence, and a short claim
    lease so restart replay and concurrent sweeps remain safe.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.effects_dir = self.root / "effects"
        self.lock_path = self.root / ".lock"

    def ensure(
        self,
        *,
        conversation_key: str,
        message_id: str,
        operation: str,
        emoji: str,
        phase: str,
        lifecycle_key: str,
        turn_id: str | None = None,
        depends_on: Sequence[str] = (),
    ) -> dict[str, Any]:
        identity = {
            "conversation_key": conversation_key,
            "message_id": message_id,
            "operation": operation,
            "emoji": emoji,
            "phase": phase,
            "lifecycle_key": lifecycle_key,
        }
        effect_id = "discord-reaction-" + hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:24]
        now = _utc_now()
        with self._locked():
            existing = self._load_unlocked(effect_id)
            if existing is not None:
                # Effect identity deliberately excludes dependencies so a
                # replay cannot create duplicate Discord effects.  Update an
                # unclaimed legacy/pending intent in place, allowing a new
                # ordering guarantee to repair persisted terminal work safely.
                if existing.get("status") == "pending":
                    normalized_dependencies = list(
                        dict.fromkeys(str(value) for value in depends_on if str(value))
                    )
                    if existing.get("depends_on") != normalized_dependencies:
                        existing["depends_on"] = normalized_dependencies
                        existing["updated_at"] = now
                        self._write_unlocked(existing)
                return existing
            effect = {
                "schema_version": REACTION_EFFECT_SCHEMA,
                "effect_id": effect_id,
                **identity,
                "turn_id": turn_id,
                "depends_on": list(
                    dict.fromkeys(str(value) for value in depends_on if str(value))
                ),
                "status": "pending",
                "attempt_count": 0,
                "last_error": "",
                "last_error_class": "",
                "created_at": now,
                "updated_at": now,
            }
            self._write_unlocked(effect)
            return effect

    def claim_due(self, *, only: set[str] | None = None) -> tuple[dict[str, Any], ...]:
        now = datetime.now(UTC)
        claimed: list[dict[str, Any]] = []
        with self._locked():
            effects = self._all_unlocked()
            applied_ids = {
                str(effect.get("effect_id"))
                for effect in effects
                if effect.get("status") == "applied"
            }
            candidates = sorted(
                effects,
                key=lambda effect: (
                    _PHASE_ORDER.get(str(effect.get("phase")), 99),
                    str(effect.get("created_at") or ""),
                    str(effect.get("effect_id") or ""),
                ),
            )
            for effect in candidates:
                effect_id = str(effect.get("effect_id") or "")
                if only is not None and effect_id not in only:
                    continue
                status = str(effect.get("status") or "pending")
                if status == "applied":
                    continue
                if status == "applying" and not _claim_expired(effect, now=now):
                    continue
                dependencies = {
                    str(value) for value in effect.get("depends_on", []) if str(value)
                }
                if not dependencies.issubset(applied_ids):
                    continue
                claim_token = uuid.uuid4().hex
                effect.update(
                    {
                        "status": "applying",
                        "claim_token": claim_token,
                        "claim_expires_at": (now + timedelta(seconds=_CLAIM_LEASE_S)).isoformat(),
                        "attempt_count": int(effect.get("attempt_count") or 0) + 1,
                        "updated_at": now.isoformat(),
                    }
                )
                self._write_unlocked(effect)
                claimed.append(dict(effect))
        return tuple(claimed)

    def finish(self, effect: Mapping[str, Any], *, error: Exception | None = None) -> None:
        effect_id = str(effect.get("effect_id") or "")
        claim_token = str(effect.get("claim_token") or "")
        with self._locked():
            current = self._load_unlocked(effect_id)
            if current is None or str(current.get("claim_token") or "") != claim_token:
                return
            current.pop("claim_token", None)
            current.pop("claim_expires_at", None)
            current["updated_at"] = _utc_now()
            if error is None:
                current.update(
                    {
                        "status": "applied",
                        "applied_at": current["updated_at"],
                        "last_error": "",
                        "last_error_class": "",
                    }
                )
            else:
                current.update(
                    {
                        "status": "pending",
                        "last_error": redact_text(str(error))[:500],
                        "last_error_class": error.__class__.__name__,
                    }
                )
            self._write_unlocked(current)

    def pending_count(self) -> int:
        with self._locked():
            return sum(
                1 for effect in self._all_unlocked() if effect.get("status") != "applied"
            )

    def supersede_pending_working(
        self, *, conversation_key: str, message_ids: Sequence[str]
    ) -> dict[str, list[str]]:
        """Fence working adds and return dependencies for their cleanup.

        Pending adds can be superseded before they touch Discord. An add that
        another sweep already claimed is left alone; cleanup waits for that
        claim to finish, preventing add-after-remove ordering across sweeps.
        """

        targets = {str(value) for value in message_ids if str(value)}
        dependencies = {message_id: [] for message_id in targets}
        with self._locked():
            for effect in self._all_unlocked():
                if (
                    effect.get("phase") != "working"
                    or effect.get("conversation_key") != conversation_key
                    or str(effect.get("message_id") or "") not in targets
                ):
                    continue
                message_id = str(effect.get("message_id") or "")
                dependencies[message_id].append(str(effect.get("effect_id") or ""))
                if effect.get("status") != "pending":
                    continue
                effect.update(
                    {
                        "status": "applied",
                        "outcome": "superseded_before_apply",
                        "applied_at": _utc_now(),
                        "updated_at": _utc_now(),
                    }
                )
                effect.pop("claim_token", None)
                effect.pop("claim_expires_at", None)
                self._write_unlocked(effect)
        return dependencies

    def load(self, effect_id: str) -> dict[str, Any] | None:
        with self._locked():
            return self._load_unlocked(effect_id)

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _all_unlocked(self) -> list[dict[str, Any]]:
        if not self.effects_dir.exists():
            return []
        effects: list[dict[str, Any]] = []
        for path in sorted(self.effects_dir.glob("discord-reaction-*.json")):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                continue
            if isinstance(value, dict) and value.get("schema_version") == REACTION_EFFECT_SCHEMA:
                effects.append(value)
        return effects

    def _load_unlocked(self, effect_id: str) -> dict[str, Any] | None:
        path = self.effects_dir / f"{effect_id}.json"
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        return value if isinstance(value, dict) else None

    def _write_unlocked(self, effect: Mapping[str, Any]) -> None:
        self.effects_dir.mkdir(parents=True, exist_ok=True)
        effect_id = str(effect["effect_id"])
        path = self.effects_dir / f"{effect_id}.json"
        temp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
        payload = json.dumps(dict(effect), sort_keys=True, indent=2) + "\n"
        with temp.open("w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)


def _claim_expired(effect: Mapping[str, Any], *, now: datetime) -> bool:
    value = str(effect.get("claim_expires_at") or "")
    try:
        expires_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= now


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
