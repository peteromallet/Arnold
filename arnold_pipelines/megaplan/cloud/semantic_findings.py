"""Cloud-side consumer projection for semantic findings (S4).

This module provides read-only projection helpers that consume
:class:`SemanticFinding` lists (produced by
:func:`arnold_pipelines.megaplan.semantic_health.inspect_semantic_health`)
and produce stable, serializable payloads for cloud consumers:

* **status** — uses projected counts to render semantic health separately
  from activity and custody.
* **repair-loop** — uses the fingerprint to detect unchanged finding sets.
* **auditor** — uses counts-by-dimension for six-hour audit reports.
* **meta-repair** — uses fingerprint stability to trigger escalation.

All functions here are intentionally **read-only**: they never mutate plan
state, lifecycle routing, receipts, or custody classifications.  They only
serialize, count, fingerprint, and project findings produced by the single
source of semantic truth (:func:`inspect_semantic_health` plus custody
classification).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from arnold.workflow.boundary_evidence import SemanticFinding
from arnold_pipelines.megaplan.semantic_health import (
    compute_finding_fingerprint,
    count_findings_by_boundary,
    count_findings_by_kind,
    count_findings_by_phase,
    count_findings_by_repair_domain,
    project_semantic_findings,
)


def project_cloud_findings(
    findings: list[SemanticFinding],
    *,
    session_id: str = "default",
    plan_dir: Path | None = None,
    cloud_meta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Project findings for cloud consumption with optional cloud metadata.

    Extends :func:`project_semantic_findings` with cloud-specific fields
    (target, provider, session markers) drawn from *cloud_meta*.  The
    resulting payload is directly consumable by cloud status, auditor,
    and repair-loop views.

    Returns the same shape as :func:`project_semantic_findings` plus:

    * ``cloud_target`` — cloud target identifier (if provided)
    * ``cloud_provider`` — cloud provider name (if provided)
    * ``session_markers`` — additional session-level markers
    """
    projection = project_semantic_findings(
        findings,
        session_id=session_id,
        plan_dir=plan_dir,
    )

    if isinstance(cloud_meta, Mapping):
        target = cloud_meta.get("target")
        if target is not None:
            projection["cloud_target"] = str(target)
        provider = cloud_meta.get("provider")
        if provider is not None:
            projection["cloud_provider"] = str(provider)
        markers = cloud_meta.get("session_markers")
        if isinstance(markers, Mapping) and markers:
            projection["session_markers"] = dict(markers)

    return projection


def fingerprint_for_session(
    findings: list[SemanticFinding],
    *,
    session_id: str = "default",
) -> dict[str, str]:
    """Return ``{session_id: fingerprint}`` for meta-repair comparison.

    The fingerprint is a stable content hash of the finding identities.
    Meta-repair consumers compare this across repeated inspections to
    detect unchanged finding sets that may need escalation.
    """
    return {session_id: compute_finding_fingerprint(findings)}


def cloud_counts_summary(
    findings: list[SemanticFinding],
    *,
    session_id: str = "default",
) -> dict[str, Any]:
    """Return a minimal cloud-readable counts summary.

    This is the lightest-weight projection: no individual findings, no
    full serialization — just the dimension counts and fingerprint.
    Suitable for watchdog/status consumers that only need the aggregate.
    """
    return {
        "schema": "arnold.workflow.cloud_counts_summary.v1",
        "session_id": session_id,
        "fingerprint": compute_finding_fingerprint(findings),
        "total_count": len(findings),
        "counts_by_boundary": count_findings_by_boundary(findings),
        "counts_by_phase": count_findings_by_phase(findings),
        "counts_by_kind": count_findings_by_kind(findings),
        "counts_by_repair_domain": count_findings_by_repair_domain(findings),
    }


__all__ = [
    "cloud_counts_summary",
    "fingerprint_for_session",
    "project_cloud_findings",
]
