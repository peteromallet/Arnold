"""Persist fresh review-time evidence for prompt construction."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from arnold.pipelines.megaplan._core.io import atomic_write_json, now_utc
from arnold.pipelines.megaplan.orchestration.completion_contract import (
    CONTRACT_MODE_SHADOW,
    DEFAULT_PROVIDERS,
    CompletionSubject,
    CompletionVerdict,
    EvidenceProvider,
    compute_verdict,
)

REVIEW_EVIDENCE_FILENAME = "review_evidence.json"
REVIEW_EVIDENCE_SCHEMA = "megaplan.review_evidence"
REVIEW_EVIDENCE_SCHEMA_VERSION = 1


class _ProviderProbe:
    """Capture provider crashes while preserving compute_verdict fail-open behavior."""

    def __init__(self, provider: EvidenceProvider, diagnostics: dict[str, dict[str, Any]]) -> None:
        self._provider = provider
        self._diagnostics = diagnostics
        self.kind = getattr(provider, "kind", type(provider).__name__)

    def collect(self, ctx: Any) -> Any:
        try:
            ref = self._provider.collect(ctx)
        except Exception as exc:
            self._diagnostics[self.kind] = {
                "ok": False,
                "error": str(exc),
                "exception_type": type(exc).__name__,
            }
            raise
        self._diagnostics[self.kind] = {"ok": True}
        return ref


def _run_git(project_dir: Path, *args: str) -> tuple[str | None, dict[str, Any]]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception as exc:
        return None, {
            "ok": False,
            "command": ["git", *args],
            "error": str(exc),
            "exception_type": type(exc).__name__,
        }
    return proc.stdout.strip() or None, {"ok": True, "command": ["git", *args]}


def _resolve_base_sha(state: dict[str, Any], project_dir: Path) -> tuple[str | None, dict[str, Any]]:
    meta = state.get("meta") if isinstance(state.get("meta"), dict) else {}
    chain_policy = meta.get("chain_policy") if isinstance(meta.get("chain_policy"), dict) else {}
    candidate = chain_policy.get("milestone_base_sha")
    if isinstance(candidate, str) and candidate.strip():
        return candidate.strip(), {"ok": True, "source": "state.meta.chain_policy.milestone_base_sha"}
    sha, diagnostics = _run_git(project_dir, "rev-parse", "HEAD")
    diagnostics["source"] = "git_rev_parse_head_fallback"
    return sha, diagnostics


def _resolve_head_sha(project_dir: Path) -> tuple[str | None, dict[str, Any]]:
    sha, diagnostics = _run_git(project_dir, "rev-parse", "HEAD")
    diagnostics["source"] = "git_rev_parse_head"
    return sha, diagnostics


def _resolve_invocation_id(state: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    meta = state.get("meta") if isinstance(state.get("meta"), dict) else {}
    value = meta.get("current_invocation_id")
    if isinstance(value, str) and value.strip():
        return value.strip(), {"ok": True, "source": "state.meta.current_invocation_id"}
    return None, {
        "ok": False,
        "source": "state.meta.current_invocation_id",
        "error": "missing invocation id",
    }


def collect_review_evidence(
    *,
    plan_dir: Path,
    project_dir: Path,
    state: dict[str, Any],
    subject: CompletionSubject,
    phase: str = "review",
    iteration: int | None = None,
    mode: str = CONTRACT_MODE_SHADOW,
    providers: tuple[EvidenceProvider, ...] = DEFAULT_PROVIDERS,
) -> dict[str, Any]:
    provider_diagnostics: dict[str, dict[str, Any]] = {}
    probed_providers = tuple(_ProviderProbe(provider, provider_diagnostics) for provider in providers)
    verdict: CompletionVerdict = compute_verdict(
        plan_dir=plan_dir,
        project_dir=project_dir,
        state=state,
        subject=subject,
        mode=mode,
        providers=probed_providers,
    )
    base_sha, base_sha_diagnostics = _resolve_base_sha(state, project_dir)
    head_sha, head_sha_diagnostics = _resolve_head_sha(project_dir)
    invocation_id, invocation_diagnostics = _resolve_invocation_id(state)

    payload = verdict.to_dict()
    payload.update(
        {
            "schema": REVIEW_EVIDENCE_SCHEMA,
            "schema_version": REVIEW_EVIDENCE_SCHEMA_VERSION,
            "artifact": REVIEW_EVIDENCE_FILENAME,
            "generated_at": now_utc(),
            "phase": phase,
            "iteration": iteration,
            "base_sha": base_sha,
            "head_sha": head_sha,
            "invocation_id": invocation_id,
            "provider_diagnostics": provider_diagnostics,
            "diagnostics": {
                "base_sha": base_sha_diagnostics,
                "head_sha": head_sha_diagnostics,
                "invocation_id": invocation_diagnostics,
            },
        }
    )
    atomic_write_json(plan_dir / REVIEW_EVIDENCE_FILENAME, payload)
    return payload
