"""T13: Audit and non-exposure tests for broker/content audit records.

Covers:
- BrokerAuditEntry field storage and to_dict redaction
- Git/effect refs, prompt/completion refs in audit records
- Redaction status, retention policy, [REDACTED] placeholders
- NDJSON output free of raw PAT/API-key/token strings
- Broker responses, error messages, agent-visible config free of raw credentials
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from arnold.pipeline.native.audit import AuditHooks, AuditRecord
from arnold.pipeline.native.decorators import phase, pipeline
from arnold.pipeline.native.runtime import run_native_pipeline
from arnold.security import (
    REDACTED,
    ActionRequest,
    ActionResult,
    ActionVerdict,
    RedactionStatus,
    RetentionPolicy,
    claim_broker_audit_entry,
    record_broker_audit_entry,
    redact_mapping,
    redact_text,
    redact_value,
)
from arnold.security.audit import BrokerAuditEntry
from arnold.security.types import ActionVerdict as AV

# ── Sentinel values for non-exposure assertions ──────────────────────

_SENTINEL_PAT = "ghp_sentinel_pat_value_0123456789abcdef"
_SENTINEL_API_KEY = "sk-sentinel-api-key-for-testing-only-7890"
_SENTINEL_BEARER = "github_pat_sentinel_bearer_token_xyz"
_SENTINEL_GHU = "ghu_sentinel_user_token_abcdef123456"
_SENTINEL_GHS = "ghs_sentinel_server_token_zyxwvu987654"
_SENTINEL_GHR = "ghr_sentinel_refresh_token_qwerty456789"

_ALL_SENTINELS = (
    _SENTINEL_PAT,
    _SENTINEL_API_KEY,
    _SENTINEL_BEARER,
    _SENTINEL_GHU,
    _SENTINEL_GHS,
    _SENTINEL_GHR,
)

_CREDENTIAL_LIKE_RE = re.compile(
    r"gh[pousr]_[A-Za-z0-9_]{10,}"
    r"|sk-[A-Za-z0-9_-]{10,}"
    r"|github_pat_[A-Za-z0-9_]{10,}"
    r"|Bearer\s+[A-Za-z0-9_\-+=]{10,}",
)


# ── Helpers ──────────────────────────────────────────────────────────

def _assert_no_raw_credentials(text: str, *, label: str = "") -> None:
    """Fail if *text* contains credential-like substrings."""
    match = _CREDENTIAL_LIKE_RE.search(text)
    assert match is None, (
        f"{label + ' ' if label else ''}unexpected credential-like pattern "
        f"'{match.group()}' in: {text[:300]}"
    )


def _assert_no_raw_credentials_in_json(payload: object, *, label: str = "") -> None:
    """Recursively scan a JSON-serializable payload for credential-like values."""
    serialized = json.dumps(payload, sort_keys=True, default=str)
    _assert_no_raw_credentials(serialized, label=label)


def _assert_no_sentinels(text: str, *, label: str = "") -> None:
    """Verify none of the sentinel values appear in *text*."""
    for sentinel in _ALL_SENTINELS:
        assert sentinel not in text, (
            f"{label + ' ' if label else ''}sentinel '{sentinel[:20]}...' "
            f"found in output"
        )


def _assert_no_sentinels_in_json(payload: object, *, label: str = "") -> None:
    """Verify no sentinel values appear in JSON-serialized payload."""
    serialized = json.dumps(payload, sort_keys=True, default=str)
    _assert_no_sentinels(serialized, label=label)


def _assert_redacted_placeholders(text: str, *, min_count: int = 1) -> None:
    """Verify [REDACTED] appears at least *min_count* times."""
    count = text.count(REDACTED)
    assert count >= min_count, (
        f"Expected at least {min_count} [REDACTED] placeholders, found {count}"
    )


# ── BrokerAuditEntry unit tests ─────────────────────────────────────

class TestBrokerAuditEntryFields:
    """BrokerAuditEntry correctly stores and redacts all ref fields."""

    def test_git_command_ref_stored_and_redacted_in_to_dict(self) -> None:
        entry = BrokerAuditEntry(
            run_id="run-01",
            step_path="root/step",
            git_command_ref=f"git push origin feature --token={_SENTINEL_PAT}",
        )
        assert entry.git_command_ref == f"git push origin feature --token={_SENTINEL_PAT}"

        d = entry.to_dict()
        # to_dict applies redact_text to git_command_ref
        assert _SENTINEL_PAT not in d["git_command_ref"]
        assert REDACTED in d["git_command_ref"]

    def test_git_effect_ref_stored_and_redacted_in_to_dict(self) -> None:
        entry = BrokerAuditEntry(
            run_id="run-01",
            step_path="root/step",
            git_effect_ref=f"artifact://git-effect?key={_SENTINEL_API_KEY}",
        )
        assert entry.git_effect_ref == f"artifact://git-effect?key={_SENTINEL_API_KEY}"

        d = entry.to_dict()
        assert _SENTINEL_API_KEY not in d["git_effect_ref"]
        assert REDACTED in d["git_effect_ref"]

    def test_prompt_ref_stored_and_redacted_in_to_dict(self) -> None:
        entry = BrokerAuditEntry(
            run_id="run-01",
            step_path="root/step",
            prompt_ref=f"artifact://prompt/1?token={_SENTINEL_BEARER}",
        )
        assert entry.prompt_ref == f"artifact://prompt/1?token={_SENTINEL_BEARER}"

        d = entry.to_dict()
        assert _SENTINEL_BEARER not in d["prompt_ref"]
        assert REDACTED in d["prompt_ref"]

    def test_completion_ref_stored_and_redacted_in_to_dict(self) -> None:
        entry = BrokerAuditEntry(
            run_id="run-01",
            step_path="root/step",
            completion_ref=f"artifact://completion/1?auth={_SENTINEL_GHU}",
        )
        assert entry.completion_ref == f"artifact://completion/1?auth={_SENTINEL_GHU}"

        d = entry.to_dict()
        assert _SENTINEL_GHU not in d["completion_ref"]
        assert REDACTED in d["completion_ref"]

    def test_redaction_status_default_and_explicit(self) -> None:
        entry = BrokerAuditEntry(run_id="run-01", step_path="root/step")
        assert entry.redaction_status == RedactionStatus.SANITIZED.value

        d = entry.to_dict()
        assert d["redaction_status"] == "sanitized"

    def test_retention_policy_default_and_explicit(self) -> None:
        entry = BrokerAuditEntry(run_id="run-01", step_path="root/step")
        assert entry.retention_policy == RetentionPolicy.AUDIT.value

        d = entry.to_dict()
        assert d["retention_policy"] == "audit"

    def test_all_refs_none_to_dict_returns_none(self) -> None:
        entry = BrokerAuditEntry(run_id="run-01", step_path="root/step")
        d = entry.to_dict()
        assert d["git_command_ref"] is None
        assert d["git_effect_ref"] is None
        assert d["prompt_ref"] is None
        assert d["completion_ref"] is None

    def test_effect_refs_redacted_in_to_dict(self) -> None:
        entry = BrokerAuditEntry(
            run_id="run-01",
            step_path="root/step",
            effect_refs=(f"effect-with-key={_SENTINEL_API_KEY}", "clean-effect"),
        )
        d = entry.to_dict()
        assert _SENTINEL_API_KEY not in str(d["effect_refs"])
        assert REDACTED in d["effect_refs"][0]


class TestBrokerAuditEntryMerge:
    """BrokerAuditEntry.merge preserves newer non-empty values."""

    def test_merge_newer_refs_win(self) -> None:
        old = BrokerAuditEntry(
            run_id="run-01",
            step_path="root/step",
            git_command_ref="old-cmd",
            git_effect_ref="old-effect",
        )
        new = BrokerAuditEntry(
            run_id="run-01",
            step_path="root/step",
            git_command_ref="new-cmd",
            git_effect_ref="",
        )
        merged = old.merge(new)
        assert merged.git_command_ref == "new-cmd"
        # Empty newer value falls back to old
        assert merged.git_effect_ref == "old-effect"

    def test_merge_preserves_run_id_and_step_path(self) -> None:
        old = BrokerAuditEntry(
            run_id="run-A",
            step_path="root/a",
            action_id="act-1",
        )
        new = BrokerAuditEntry(
            run_id="run-A",
            step_path="root/a",
            prompt_ref="new-prompt",
        )
        merged = old.merge(new)
        assert merged.run_id == "run-A"
        assert merged.step_path == "root/a"
        assert merged.action_id == "act-1"  # preserved from old
        assert merged.prompt_ref == "new-prompt"  # from new

    def test_merge_metadata_is_redacted(self) -> None:
        old = BrokerAuditEntry(
            run_id="run-01",
            step_path="root/step",
            metadata={"api_key": _SENTINEL_API_KEY},
        )
        new = BrokerAuditEntry(
            run_id="run-01",
            step_path="root/step",
            metadata={"extra": f"Bearer {_SENTINEL_BEARER}"},
        )
        merged = old.merge(new)
        assert merged.metadata is not None
        assert _SENTINEL_API_KEY not in str(merged.metadata)
        assert _SENTINEL_BEARER not in str(merged.metadata)
        assert merged.metadata["api_key"] == REDACTED
        assert REDACTED in merged.metadata["extra"]


# ── record / claim cycle tests ──────────────────────────────────────

class TestBrokerAuditRecordClaimCycle:
    """record_broker_audit_entry / claim_broker_audit_entry cycle."""

    def test_record_and_claim_returns_redacted_payload(self) -> None:
        record_broker_audit_entry(
            run_id="run-cyc",
            step_path="root/step",
            action_id="act-1",
            git_command_ref=f"git push --token={_SENTINEL_PAT}",
            git_effect_ref=f"effect?key={_SENTINEL_API_KEY}",
            prompt_ref=f"prompt?auth={_SENTINEL_BEARER}",
            completion_ref=f"completion?secret={_SENTINEL_GHU}",
            redaction_status=RedactionStatus.SANITIZED.value,
            retention_policy=RetentionPolicy.AUDIT.value,
            metadata={"token": _SENTINEL_GHS},
        )

        payload = claim_broker_audit_entry("run-cyc", "root/step")
        assert payload is not None

        # All refs must be redacted
        assert _SENTINEL_PAT not in str(payload)
        assert _SENTINEL_API_KEY not in str(payload)
        assert _SENTINEL_BEARER not in str(payload)
        assert _SENTINEL_GHU not in str(payload)
        assert _SENTINEL_GHS not in str(payload)

        # Redaction status and retention policy present
        assert payload["redaction_status"] == "sanitized"
        assert payload["retention_policy"] == "audit"

        # [REDACTED] placeholders present
        serialized = json.dumps(payload, sort_keys=True)
        assert REDACTED in serialized

    def test_record_merge_on_duplicate_key(self) -> None:
        record_broker_audit_entry(
            run_id="run-merge",
            step_path="root/step",
            git_command_ref="first-cmd",
            prompt_ref="first-prompt",
        )
        record_broker_audit_entry(
            run_id="run-merge",
            step_path="root/step",
            git_command_ref="second-cmd",
            completion_ref="second-completion",
        )

        payload = claim_broker_audit_entry("run-merge", "root/step")
        assert payload is not None
        # Newer non-empty values win
        assert payload["git_command_ref"] == "second-cmd"
        assert payload["prompt_ref"] == "first-prompt"  # unchanged
        assert payload["completion_ref"] == "second-completion"  # new

    def test_claim_nonexistent_returns_none(self) -> None:
        payload = claim_broker_audit_entry("nonexistent-run", "no/such/step")
        assert payload is None

    def test_claim_removes_entry(self) -> None:
        record_broker_audit_entry(run_id="run-pop", step_path="root/x", action_id="act-pop")
        first = claim_broker_audit_entry("run-pop", "root/x")
        assert first is not None
        second = claim_broker_audit_entry("run-pop", "root/x")
        assert second is None  # already popped


# ── Audit NDJSON non-exposure integration tests ─────────────────────

class TestAuditNdjsonNonExposure:
    """NDJSON audit output must be free of raw credentials and contain [REDACTED]."""

    def test_ndjson_contains_redacted_placeholders(self, tmp_path: Path) -> None:
        """Audit NDJSON must contain [REDACTED] for broker-injected sentinel values."""
        audit_dir = tmp_path / "audit"
        hooks = AuditHooks(audit_dir=audit_dir)

        @phase
        def brokered_step(ctx: dict) -> dict:
            record_broker_audit_entry(
                run_id=hooks._run_id,
                step_path=ctx["step_path"],
                git_command_ref=f"push --token={_SENTINEL_PAT}",
                git_effect_ref=f"effect/{_SENTINEL_API_KEY}",
                prompt_ref=f"prompt?key={_SENTINEL_BEARER}",
                completion_ref=f"completion?secret={_SENTINEL_GHU}",
                metadata={
                    "authorization": f"Bearer {_SENTINEL_GHS}",
                    "token": _SENTINEL_GHR,
                },
            )
            return {"ok": True}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            state = yield brokered_step(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        run_native_pipeline(prog, hooks=hooks)

        # Read NDJSON
        audit_file = audit_dir / "audit.ndjson"
        assert audit_file.exists()
        ndjson_text = audit_file.read_text(encoding="utf-8")

        # Must contain [REDACTED] placeholders
        _assert_redacted_placeholders(ndjson_text, min_count=3)

        # Must NOT contain any sentinel values
        _assert_no_sentinels(ndjson_text, label="NDJSON output")

        # Must NOT contain credential-like patterns
        _assert_no_raw_credentials(ndjson_text, label="NDJSON output")

    def test_ndjson_audit_record_has_all_broker_ref_fields(self, tmp_path: Path) -> None:
        """NDJSON step records must include git/prompt/completion ref fields."""
        audit_dir = tmp_path / "audit"
        hooks = AuditHooks(audit_dir=audit_dir)

        @phase
        def brokered_step(ctx: dict) -> dict:
            record_broker_audit_entry(
                run_id=hooks._run_id,
                step_path=ctx["step_path"],
                git_command_ref="git-push-ref",
                git_effect_ref="git-effect-ref",
                prompt_ref="prompt-ref",
                completion_ref="completion-ref",
            )
            return {"ok": True}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            state = yield brokered_step(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        run_native_pipeline(prog, hooks=hooks)

        audit_file = audit_dir / "audit.ndjson"
        lines = [
            json.loads(line)
            for line in audit_file.read_text(encoding="utf-8").strip().splitlines()
            if line.strip() and "attempt_id" in line
        ]
        assert len(lines) == 1
        rec = lines[0]

        # All broker ref fields present
        assert "git_command_ref" in rec
        assert "git_effect_ref" in rec
        assert "prompt_ref" in rec
        assert "completion_ref" in rec
        assert "redaction_status" in rec
        assert "retention_policy" in rec

        assert rec["redaction_status"] == "sanitized"
        assert rec["retention_policy"] == "audit"

    def test_ndjson_redacts_broker_refs_with_sentinel_patterns(self, tmp_path: Path) -> None:
        """Broker ref fields (git/prompt/completion) with sentinel patterns must be redacted in NDJSON."""
        audit_dir = tmp_path / "audit"
        hooks = AuditHooks(audit_dir=audit_dir)

        @phase
        def brokered_step(ctx: dict) -> dict:
            record_broker_audit_entry(
                run_id=hooks._run_id,
                step_path=ctx["step_path"],
                git_command_ref=f"git push --token={_SENTINEL_PAT}",
                git_effect_ref=f"effect/{_SENTINEL_API_KEY}",
                prompt_ref=f"prompt?key={_SENTINEL_BEARER}",
                completion_ref=f"completion?secret={_SENTINEL_GHU}",
            )
            return {"ok": True}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            state = yield brokered_step(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        run_native_pipeline(prog, hooks=hooks)

        audit_file = audit_dir / "audit.ndjson"
        ndjson_text = audit_file.read_text(encoding="utf-8")

        _assert_no_sentinels(ndjson_text, label="NDJSON with sentinel refs")
        _assert_no_raw_credentials(ndjson_text, label="NDJSON with sentinel refs")
        _assert_redacted_placeholders(ndjson_text, min_count=2)

    def test_multiple_brokered_steps_in_ndjson(self, tmp_path: Path) -> None:
        """Multiple brokered steps all produce redacted NDJSON records."""
        audit_dir = tmp_path / "audit"
        hooks = AuditHooks(audit_dir=audit_dir)

        @phase
        def step_a(ctx: dict) -> dict:
            record_broker_audit_entry(
                run_id=hooks._run_id,
                step_path=ctx["step_path"],
                git_command_ref=f"cmd-a?token={_SENTINEL_PAT}",
            )
            return {"a": 1}

        @phase
        def step_b(ctx: dict) -> dict:
            record_broker_audit_entry(
                run_id=hooks._run_id,
                step_path=ctx["step_path"],
                prompt_ref=f"prompt-b?key={_SENTINEL_API_KEY}",
            )
            return {"b": 2}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            s = yield step_b(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        run_native_pipeline(prog, hooks=hooks)

        audit_file = audit_dir / "audit.ndjson"
        ndjson_text = audit_file.read_text(encoding="utf-8")

        _assert_no_sentinels(ndjson_text, label="multi-step NDJSON")
        _assert_no_raw_credentials(ndjson_text, label="multi-step NDJSON")
        _assert_redacted_placeholders(ndjson_text, min_count=2)


# ── ActionResult broker response non-exposure tests ──────────────────

class TestActionResultNonExposure:
    """ActionResult.to_json() must never leak raw credentials."""

    def test_action_result_to_json_redacts_summary(self) -> None:
        result = ActionResult(
            verdict=ActionVerdict.ALLOW,
            summary=f"Allowed push with token={_SENTINEL_PAT} and key={_SENTINEL_API_KEY}",
            metadata={"action_type": "git_push"},
        )
        payload = result.to_json()
        _assert_no_raw_credentials_in_json(payload, label="ActionResult summary")
        assert _SENTINEL_PAT not in payload["summary"]
        assert _SENTINEL_API_KEY not in payload["summary"]
        assert REDACTED in payload["summary"]

    def test_action_result_to_json_redacts_metadata(self) -> None:
        result = ActionResult(
            verdict=ActionVerdict.DENY,
            summary="Denied",
            metadata={
                "branch": "main",
                "token": _SENTINEL_BEARER,
                "nested": {"api_key": _SENTINEL_API_KEY},
                "auth_header": f"Authorization: Bearer {_SENTINEL_GHU}",
            },
        )
        payload = result.to_json()
        _assert_no_sentinels_in_json(payload, label="ActionResult metadata")
        _assert_no_raw_credentials_in_json(payload, label="ActionResult metadata")

    def test_action_result_metadata_sensitive_keys_are_redacted(self) -> None:
        result = ActionResult(
            verdict=ActionVerdict.ALLOW,
            summary="ok",
            metadata={
                "api_key": _SENTINEL_API_KEY,
                "password": _SENTINEL_BEARER,
                "secret": _SENTINEL_GHU,
                "token": _SENTINEL_GHS,
                "credential": _SENTINEL_PAT,
                "authorization": f"Bearer {_SENTINEL_GHR}",
            },
        )
        payload = result.to_json()
        # All sensitive-key values must be fully replaced with REDACTED
        for key in ("api_key", "password", "secret", "token", "credential", "authorization"):
            assert payload["metadata"][key] == REDACTED, (
                f"metadata['{key}'] should be [REDACTED], got {payload['metadata'][key]}"
            )
        _assert_no_sentinels_in_json(payload, label="sensitive keys")

    def test_action_result_effect_refs_are_preserved_as_opaque_ids(self) -> None:
        """Effect refs are opaque identifiers — they are preserved as-is in to_json."""
        result = ActionResult(
            verdict=ActionVerdict.ALLOW,
            summary="ok",
            effect_refs=("effect-1", "effect-2"),
        )
        payload = result.to_json()
        assert payload["effect_refs"] == ["effect-1", "effect-2"]
        _assert_no_raw_credentials_in_json(payload, label="effect_refs")

    def test_action_result_redaction_status_and_retention_policy(self) -> None:
        result = ActionResult(
            verdict=ActionVerdict.ALLOW,
            summary="ok",
        )
        payload = result.to_json()
        assert payload["redaction_status"] == "sanitized"
        assert payload["retention_policy"] == "audit"


# ── Error message non-exposure tests ─────────────────────────────────

class TestErrorMessageNonExposure:
    """Error paths must not leak raw credentials in error messages."""

    def test_redact_text_handles_error_like_messages(self) -> None:
        """redact_text scrubs credential patterns from error-like strings."""
        error_msg = (
            f"Push failed: authentication error with token={_SENTINEL_PAT} "
            f"and api_key={_SENTINEL_API_KEY}. "
            f"Header: Authorization: Bearer {_SENTINEL_BEARER}"
        )
        redacted = redact_text(error_msg)
        _assert_no_sentinels(redacted, label="redacted error message")
        _assert_no_raw_credentials(redacted, label="redacted error message")
        _assert_redacted_placeholders(redacted, min_count=3)

    def test_redact_value_handles_nested_error_dict(self) -> None:
        """redact_value sanitizes nested error structures."""
        error_payload = {
            "error": {
                "message": f"auth failed: {_SENTINEL_PAT}",
                "details": {
                    "api_key": _SENTINEL_API_KEY,
                    "headers": {"Authorization": f"Bearer {_SENTINEL_BEARER}"},
                },
            }
        }
        sanitized = redact_value(error_payload)
        serialized = json.dumps(sanitized, sort_keys=True)
        _assert_no_sentinels(serialized, label="nested error structure")
        _assert_no_raw_credentials(serialized, label="nested error structure")
        _assert_redacted_placeholders(serialized, min_count=3)

    def test_redact_mapping_fully_masks_sensitive_error_keys(self) -> None:
        """redact_mapping replaces sensitive field values with [REDACTED]."""
        error_map = {
            "message": "operation failed",
            "api_key": _SENTINEL_API_KEY,
            "token": _SENTINEL_PAT,
            "credential": _SENTINEL_BEARER,
            "safe_field": "visible-value",
        }
        sanitized = redact_mapping(error_map)
        assert sanitized["message"] != REDACTED  # not a sensitive key
        assert sanitized["safe_field"] == "visible-value"
        assert sanitized["api_key"] == REDACTED
        assert sanitized["token"] == REDACTED
        assert sanitized["credential"] == REDACTED

    def test_action_result_with_error_summary_is_sanitized(self) -> None:
        """ActionResult constructed with error-like summary is sanitized."""
        result = ActionResult(
            verdict=ActionVerdict.DENY,
            summary=f"ERROR: api_key={_SENTINEL_API_KEY} invalid for Bearer {_SENTINEL_BEARER}",
            metadata={"error_detail": f"token={_SENTINEL_PAT}"},
        )
        payload = result.to_json()
        _assert_no_sentinels_in_json(payload, label="error ActionResult")
        _assert_no_raw_credentials_in_json(payload, label="error ActionResult")
        _assert_redacted_placeholders(json.dumps(payload), min_count=2)


# ── Agent-visible config non-exposure tests ──────────────────────────

class TestAgentVisibleConfigNonExposure:
    """Agent-visible config must not contain raw credential values."""

    def test_action_request_sanitizes_metadata_on_construction(self) -> None:
        """ActionRequest.__post_init__ must redact metadata with sentinel keys."""
        request = ActionRequest(
            action_type="git_push",
            repo="acme/service",
            branch="feature/x",
            metadata={
                "api_key": _SENTINEL_API_KEY,
                "token": _SENTINEL_PAT,
                "detail": f"Bearer {_SENTINEL_BEARER}",
                "safe": "visible",
            },
        )
        assert request.metadata["api_key"] == REDACTED
        assert request.metadata["token"] == REDACTED
        assert REDACTED in request.metadata["detail"]
        assert request.metadata["safe"] == "visible"

    def test_action_request_command_is_stable_tuple(self) -> None:
        """ActionRequest.command should not contain sentinel values used in construction."""
        request = ActionRequest(
            action_type="git_push",
            command=("git", "push", f"https://token={_SENTINEL_PAT}@github.com"),
        )
        # Command is preserved as-is (it's part of the action request, not redacted at this layer)
        assert _SENTINEL_PAT in request.command[2]

    def test_redacted_placeholder_constant_is_stable(self) -> None:
        """The REDACTED constant is exactly '[REDACTED]'."""
        assert REDACTED == "[REDACTED]"

    def test_action_result_to_json_is_deterministic_and_clean(self) -> None:
        """Multiple serializations of the same ActionResult produce identical clean output."""
        result = ActionResult(
            verdict=ActionVerdict.ALLOW,
            summary="Push allowed",
            action_id="act-1",
            effect_refs=("effect-1",),
            metadata={"branch": "feature/x"},
        )
        payload1 = json.dumps(result.to_json(), sort_keys=True)
        payload2 = json.dumps(result.to_json(), sort_keys=True)
        assert payload1 == payload2
        _assert_no_raw_credentials(payload1, label="deterministic output")

    def test_broker_audit_entry_construction_rejects_empty_run_id(self) -> None:
        with pytest.raises(ValueError, match="run_id"):
            BrokerAuditEntry(run_id="", step_path="root/step")

    def test_broker_audit_entry_construction_rejects_empty_step_path(self) -> None:
        with pytest.raises(ValueError, match="step_path"):
            BrokerAuditEntry(run_id="run-01", step_path="")


# ── Needed import for compile_pipeline inside test functions ─────────

from arnold.pipeline.native.compiler import compile_pipeline
