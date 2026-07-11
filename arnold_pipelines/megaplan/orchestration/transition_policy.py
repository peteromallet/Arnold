"""Review-to-done transition policy for M3 evidence enforcement."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from arnold_pipelines.megaplan._core.io import atomic_write_json
from arnold_pipelines.megaplan.orchestration.evidence_contract import (
    EvidenceRef,
    EvidenceStatus,
    TransitionDecision,
    TrustClass,
)
from arnold_pipelines.megaplan.planning.state import STATE_DONE

TRANSITION_DECISION_REVIEW_DONE_FILENAME = "transition_decision_review_done.json"


@dataclass(frozen=True)
class TransitionPolicyDecision:
    """The verdict returned by ``TransitionPolicy.evaluate_review_done``.

    ``allowed`` is the authoritative gate flag consumed by the review
    handler when it writes the transition decision. ``reasons`` are the
    hard denial reasons (empty when allowed). ``advisory`` are non-blocking
    notes that surface in the written decision but never flip ``allowed``.
    """

    allowed: bool
    reasons: tuple[str, ...] = ()
    advisory: tuple[str, ...] = ()

    def merge_denial_reasons(self, extra_reasons: Sequence[str]) -> "TransitionPolicyDecision":
        """Return a copy forced denied with the extra hard denial reasons appended.

        Used by review-side pre-checks (e.g. the North Star closeout blocker
        gate) that must deny the review→done transition *independently* of the
        normal policy evaluation, while still routing through the existing
        denial path. The decision becomes denied whenever any extra reason is
        present; with no extra reasons the decision is returned unchanged.

        This intentionally does not change the ``TransitionPolicy`` API: the
        North Star check stays a separate pre-check and the policy keeps its
        existing concerns (evidence freshness, completion status).
        """
        extras = tuple(str(reason) for reason in extra_reasons if str(reason).strip())
        if not extras:
            return self
        return TransitionPolicyDecision(
            allowed=False,
            reasons=self.reasons + extras,
            advisory=self.advisory,
        )


class TransitionWriter:
    """Persist review->done transition decisions without changing the schema."""

    @staticmethod
    def write_review_done(
        plan_dir: Path,
        decision: TransitionDecision,
        *,
        retryable: bool,
        next_action: str,
        denial_kind: str | None = None,
        operator_summary: str | None = None,
        fresh_evidence_path: str = "review_evidence.json",
    ) -> Path:
        compact_evidence_refs = [
            {
                "kind": ref.kind,
                "status": ref.status.value if isinstance(ref.status, EvidenceStatus) else str(ref.status),
                "summary": ref.summary,
                "artifact_path": ref.artifact.path if ref.artifact is not None else None,
            }
            for ref in decision.evidence
        ]
        routing_provenance = dict(decision.routing_provenance)
        routing_provenance.update(
            {
                "retryable": retryable,
                "next_action": next_action,
                "denial_kind": denial_kind,
                "operator_summary": operator_summary,
                "fresh_evidence_path": fresh_evidence_path,
                "evidence_refs_compact": compact_evidence_refs,
            }
        )
        payload = TransitionDecision(
            decision_id=decision.decision_id,
            subject=decision.subject,
            from_state=decision.from_state,
            to_state=decision.to_state,
            action=decision.action,
            status=decision.status,
            evidence=decision.evidence,
            would_block_reasons=decision.would_block_reasons,
            invocation_id=decision.invocation_id,
            phase=decision.phase,
            iteration=decision.iteration,
            base_sha=decision.base_sha,
            head_sha=decision.head_sha,
            code_hash=decision.code_hash,
            routing_provider=decision.routing_provider,
            routing_provenance=routing_provenance,
        ).to_dict()
        output_path = plan_dir / TRANSITION_DECISION_REVIEW_DONE_FILENAME
        atomic_write_json(output_path, payload)
        return output_path


class TransitionPolicy:
    """Evaluate normal approved review -> done transitions without side effects."""

    @classmethod
    def evaluate_review_done(
        cls,
        *,
        result: str,
        next_state: str,
        review_payload: Mapping[str, Any] | None = None,
        review_evidence: Mapping[str, Any] | None = None,
        project_dir: Path | None = None,
    ) -> TransitionPolicyDecision:
        if result != "success" or next_state != STATE_DONE:
            return TransitionPolicyDecision(True, advisory=("not a normal success-to-done review route",))

        review_payload = review_payload or {}
        review_evidence = review_evidence or {}
        denial_reasons: list[str] = []
        advisory: list[str] = []

        completion_status = str(review_payload.get("review_completion_status") or "").lower()
        if completion_status == "incomplete":
            denial_reasons.append("review approval is incomplete")

        verdict = str(review_payload.get("review_verdict") or "").lower()
        if verdict and verdict != "approved":
            denial_reasons.append(f"review verdict is not approved: {verdict}")

        if cls._review_reports_no_inspection(review_payload):
            denial_reasons.append("review approval did not inspect the repository")

        blocking_contradictions = cls._blocking_contradictions(review_payload)
        denial_reasons.extend(blocking_contradictions)

        stale_reason = cls._stale_evidence_reason(review_evidence, project_dir)
        if stale_reason:
            advisory.append(stale_reason)
        else:
            denial_reasons.extend(cls._fresh_required_unsatisfied_reasons(review_evidence))

        provider_diagnostics = review_evidence.get("provider_diagnostics")
        if isinstance(provider_diagnostics, Mapping):
            for provider, diagnostic in provider_diagnostics.items():
                if isinstance(diagnostic, Mapping) and diagnostic.get("ok") is False:
                    advisory.append(f"provider-error evidence is advisory: {provider}")

        if not review_evidence:
            advisory.append("missing review evidence is advisory")

        return TransitionPolicyDecision(
            allowed=not denial_reasons,
            reasons=tuple(denial_reasons),
            advisory=tuple(advisory),
        )

    @staticmethod
    def _review_reports_no_inspection(review_payload: Mapping[str, Any]) -> bool:
        inspected = review_payload.get("repository_inspected")
        if inspected is False:
            return True
        for key in ("issues", "summary"):
            value = review_payload.get(key)
            texts = value if isinstance(value, list) else [value]
            for item in texts:
                text = str(item or "").lower()
                if "no repository inspection" in text or "could not inspect the repository" in text:
                    return True
        return False

    @staticmethod
    def _blocking_contradictions(review_payload: Mapping[str, Any]) -> list[str]:
        reasons: list[str] = []
        items = (
            review_payload.get("blocking_rework_items")
            or review_payload.get("rework_items")
            or review_payload.get("unsupported_blockers")
            or review_payload.get("unsupported_rework_items")
            or []
        )
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, Mapping):
                    continue
                status = str(item.get("status") or item.get("severity") or "").lower()
                if status == "blocking" or item.get("blocking") is True or item.get("deterministic_check"):
                    reasons.append("approved review still contains blocking rework")
                    break
        unsupported = review_payload.get("unsupported_blockers") or review_payload.get("unsupported_rework_items") or []
        if isinstance(unsupported, list) and unsupported:
            reasons.append("approved review still contains unsupported blockers")
        for key in ("authority_status", "routing_authority_status"):
            status = str(review_payload.get(key) or "").lower()
            if status == EvidenceStatus.unsatisfied.value:
                reasons.append(f"routing authority contradiction: {key}=unsatisfied")
        return reasons

    @staticmethod
    def _stale_evidence_reason(review_evidence: Mapping[str, Any], project_dir: Path | None) -> str | None:
        if not review_evidence or project_dir is None:
            return None
        head_sha = review_evidence.get("head_sha")
        if not isinstance(head_sha, str) or not head_sha:
            return None
        try:
            current = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=project_dir,
                capture_output=True,
                check=True,
                text=True,
            ).stdout.strip()
        except Exception:
            return "could not prove review evidence freshness; treating evidence as advisory"
        if current and current != head_sha:
            return "stale review evidence is advisory"
        return None

    @staticmethod
    def _fresh_required_unsatisfied_reasons(review_evidence: Mapping[str, Any]) -> list[str]:
        reasons: list[str] = []
        raw_evidence = review_evidence.get("evidence", [])
        if not isinstance(raw_evidence, list):
            return reasons
        for raw in raw_evidence:
            if not isinstance(raw, Mapping):
                continue
            ref = EvidenceRef.from_dict(dict(raw))
            if ref.status is not EvidenceStatus.unsatisfied:
                continue
            details = ref.details if isinstance(ref.details, dict) else {}
            required = bool(details.get("required") is True or details.get("priority") == "must")
            trust_class = ref.trust_class
            if isinstance(trust_class, TrustClass):
                is_advisory_trust = trust_class in {TrustClass.claim, TrustClass.judgment}
            else:
                is_advisory_trust = False
            if required and not is_advisory_trust:
                reasons.append(f"fresh required evidence unsatisfied: {ref.kind}")
        return reasons


__all__ = [
    "TRANSITION_DECISION_REVIEW_DONE_FILENAME",
    "TransitionPolicy",
    "TransitionPolicyDecision",
    "TransitionWriter",
]
