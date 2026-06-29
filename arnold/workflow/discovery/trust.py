"""Path-derived package metadata for pipeline discovery.

This module preserves the historical path-derived discovery surface for
package metadata only.  Its classifications and tenant ids describe where a
pipeline package was discovered from; they are not runtime, replay, deletion,
or workflow identity authorities.

Trust grades are computed from the filesystem origin of a pipeline module, not
from module-level constants or user-supplied metadata.  The three package
discovery grades:

- ``AUTO_EXEC``   — in-tree package under a recognised prefix subtree;
                    eligible for the legacy discovery auto-exec package tier.
- ``QUARANTINED`` — out-of-tree / user-home module; manifest-only at
                    discovery; execution requires explicit promotion to
                    ``BLESSED``.
- ``BLESSED``     — either origin, explicitly listed in the blessed
                    allowlist; shares the legacy discovery package tier with
                    ``AUTO_EXEC``.

The neutral Arnold version accepts an *in_tree_path_fragment* parameter
so that consumers can define their own "in-tree" prefix.  Megaplan
passes ``"megaplan/pipelines"`` through the bridge.

Runtime, replay, deletion, and workflow identity gates must use the
manifest-hash-backed workflow identity APIs instead of trusting values derived
from package paths.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import enum
import hashlib
from pathlib import Path

from arnold.kernel.ids import (
    JudgeManifestCrossReference,
    WorkflowIdentity,
    derive_workflow_tenant_id as _derive_workflow_tenant_id,
    workflow_identity,
)

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

# Allowlist of blessed pipeline install-path strings.  Default empty — no
# out-of-tree modules are promoted automatically.  To promote a user module,
# add its absolute path string (resolved) to this tuple.
BLESSED_ALLOWLIST: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# TrustGrade
# ---------------------------------------------------------------------------


class TrustGrade(enum.Enum):
    """Package-discovery classification for a discovered pipeline module.

    These values are compatibility metadata for package discovery.  They are
    not sufficient authority for runtime, replay, deletion, or workflow
    identity decisions.
    """

    AUTO_EXEC = "auto_exec"
    QUARANTINED = "quarantined"
    BLESSED = "blessed"


class WorkflowTrustEvidenceKind(enum.Enum):
    """Evidence category supporting a manifest-backed workflow trust decision."""

    MANIFEST = "manifest"
    JUDGE = "judge"
    PACKAGE_PROMOTION = "package_promotion"


@dataclass(frozen=True)
class WorkflowTrustDecision:
    """Manifest-backed workflow trust decision for runtime gates.

    Unlike :func:`classify`, this decision is anchored by a workflow alias plus
    manifest hash.  Package promotion evidence may explain a decision, but it
    cannot replace the manifest-backed identity anchor.
    """

    grade: TrustGrade
    alias: str
    manifest_hash: str
    pipeline_identity: str
    tenant_id: str
    evidence_kind: WorkflowTrustEvidenceKind = WorkflowTrustEvidenceKind.MANIFEST
    judge_manifest_cross_reference: JudgeManifestCrossReference | None = None
    package_promotion_evidence: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        grade = self.grade
        if not isinstance(grade, TrustGrade):
            try:
                grade = TrustGrade(grade)
            except ValueError as exc:
                raise ValueError("grade must be a known TrustGrade") from exc

        evidence_kind = self.evidence_kind
        if not isinstance(evidence_kind, WorkflowTrustEvidenceKind):
            try:
                evidence_kind = WorkflowTrustEvidenceKind(evidence_kind)
            except ValueError as exc:
                raise ValueError(
                    "evidence_kind must be a known WorkflowTrustEvidenceKind"
                ) from exc

        identity = workflow_identity(self.alias, self.manifest_hash)
        if self.pipeline_identity != identity.pipeline_identity:
            raise ValueError("pipeline_identity must match alias plus manifest_hash")
        if self.tenant_id != identity.tenant_id:
            raise ValueError("tenant_id must match alias plus manifest_hash")

        judge_ref = self.judge_manifest_cross_reference
        if evidence_kind is WorkflowTrustEvidenceKind.JUDGE:
            if not isinstance(judge_ref, JudgeManifestCrossReference):
                raise ValueError(
                    "judge-backed workflow trust requires "
                    "JudgeManifestCrossReference"
                )
            if judge_ref.manifest_hash.lower() != identity.manifest_hash:
                raise ValueError(
                    "judge_manifest_cross_reference manifest_hash must match "
                    "the workflow manifest_hash"
                )
        elif judge_ref is not None and not isinstance(
            judge_ref, JudgeManifestCrossReference
        ):
            raise ValueError(
                "judge_manifest_cross_reference must be JudgeManifestCrossReference"
            )

        package_evidence = self.package_promotion_evidence
        if package_evidence is not None:
            if not isinstance(package_evidence, Mapping):
                raise ValueError("package_promotion_evidence must be a mapping")
            package_evidence = {
                str(key): str(value) for key, value in sorted(package_evidence.items())
            }

        object.__setattr__(self, "grade", grade)
        object.__setattr__(self, "alias", identity.alias)
        object.__setattr__(self, "manifest_hash", identity.manifest_hash)
        object.__setattr__(self, "pipeline_identity", identity.pipeline_identity)
        object.__setattr__(self, "tenant_id", identity.tenant_id)
        object.__setattr__(self, "evidence_kind", evidence_kind)
        object.__setattr__(self, "package_promotion_evidence", package_evidence)

    @property
    def workflow_identity(self) -> WorkflowIdentity:
        """Return the canonical workflow identity anchor."""

        return workflow_identity(self.alias, self.manifest_hash)


# ---------------------------------------------------------------------------
# Core evaluator
# ---------------------------------------------------------------------------


def classify(
    module_path: Path,
    *,
    blessed_allowlist: tuple[str, ...] = BLESSED_ALLOWLIST,
    in_tree_path_fragment: str | None = None,
) -> TrustGrade:
    """Return the package-discovery trust grade for *module_path*.

    Classification order:

    1. If ``str(module_path.resolve())`` is in *blessed_allowlist* → ``BLESSED``.
    2. If *in_tree_path_fragment* is set and *module_path* is inside that
       subtree → ``AUTO_EXEC``.
    3. Otherwise → ``QUARANTINED``.

    The *blessed_allowlist* and *in_tree_path_fragment* parameters exist so
    callers can inject their own definitions without mutating module-level
    constants (useful in tests and for non-Megaplan consumers).

    This is a package metadata classifier kept for existing discovery callers.
    It does not establish runtime authority, replay authority, deletion
    authority, or canonical workflow identity.
    """
    resolved = str(module_path.resolve())

    if resolved in blessed_allowlist:
        return TrustGrade.BLESSED

    if in_tree_path_fragment is not None:
        normalised = resolved.replace("\\", "/")
        fragment_with_sep = "/" + in_tree_path_fragment + "/"
        if fragment_with_sep in normalised or normalised.endswith(
            "/" + in_tree_path_fragment
        ):
            return TrustGrade.AUTO_EXEC

    return TrustGrade.QUARANTINED


def derive_workflow_tenant_id(alias: str, manifest_hash: str) -> str:
    """Return the manifest-backed workflow tenant id.

    This delegates to :mod:`arnold.kernel.ids` and derives from the canonical
    alias plus manifest hash identity pair.  It is the workflow/runtime tenant
    helper; :func:`derive_tenant_id` remains package-discovery metadata only.
    """

    return _derive_workflow_tenant_id(alias, manifest_hash)


def classify_workflow_trust(
    grade: TrustGrade,
    *,
    alias: str,
    manifest_hash: str,
    evidence_kind: WorkflowTrustEvidenceKind = WorkflowTrustEvidenceKind.MANIFEST,
    judge_manifest_cross_reference: JudgeManifestCrossReference | None = None,
    package_promotion_evidence: Mapping[str, str] | None = None,
) -> WorkflowTrustDecision:
    """Return a manifest-backed workflow trust decision.

    Runtime, replay, and deletion gates should use this API instead of
    path-derived package discovery evidence.  The required ``alias`` and
    ``manifest_hash`` inputs derive the canonical pipeline identity and tenant
    id through :mod:`arnold.kernel.ids`; package promotion evidence remains
    explanatory metadata.
    """

    identity = workflow_identity(alias, manifest_hash)
    return WorkflowTrustDecision(
        grade=grade,
        alias=identity.alias,
        manifest_hash=identity.manifest_hash,
        pipeline_identity=identity.pipeline_identity,
        tenant_id=identity.tenant_id,
        evidence_kind=evidence_kind,
        judge_manifest_cross_reference=judge_manifest_cross_reference,
        package_promotion_evidence=package_promotion_evidence,
    )


def derive_tenant_id(cli_name: str, module_path: Path) -> str:
    """Return the SDK-derived package-discovery tenant id.

    The id is stable for the same CLI name and resolved install path, and is
    never read from user manifest metadata.

    This compatibility id is package metadata only.  It is not a runtime tenant
    authority, replay key, deletion key, or workflow identity; use
    manifest-hash-backed workflow identity APIs for those decisions.
    """

    raw = f"{cli_name}\0{module_path.resolve()}".encode("utf-8")
    return "pipeline_" + hashlib.sha256(raw).hexdigest()[:24]
