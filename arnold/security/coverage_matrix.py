"""Machine-readable credential surface coverage matrix for M2 Security Broker.

Each :class:`CoverageEntry` classifies one credential surface discovered in
the Arnold/Hermes codebase.  The matrix is the single source of truth for
conformance checks and audit reporting.

Classification rules
--------------------
* ``covered`` — fully brokered; raw credentials never reach the agent process.
* ``deferred`` — acknowledged gap deferred to a later milestone (M4–M6).
* ``uncovered`` — documented but not planned for broker coverage (typically
  free/local providers or architecture-infeasible paths).

Residual risk
-------------
* ``low`` — limited blast radius; attribute only.
* ``medium`` — credential could enable non-trivial lateral movement.
* ``high`` — credential grants mutation access to production resources.
* ``critical`` — credential grants unrestricted admin/mutation access.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List

class CoverageStatus(str, Enum):
    COVERED = "covered"
    DEFERRED = "deferred"
    UNCOVERED = "uncovered"

class ResidualRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass(frozen=True, slots=True)
class CoverageEntry:
    """One classified credential surface."""

    credential_surface: str
    credential_type: str
    m2_status: CoverageStatus
    residual_risk: ResidualRisk
    deferral_target: str | None
    notes: str

def get_coverage_matrix() -> List[CoverageEntry]:
    """Return the complete M2 credential coverage matrix.

    Every credential surface named in the approved M2 plan and discovered
    during codebase audit must appear here.  Conformance checks cross-
    reference this matrix against the actual codebase.
    """

    return [
        # ── Git push-class mutations ────────────────────────────────────
        CoverageEntry(
            credential_surface="arnold.security.policy.SecurityPolicy.evaluate (git_push to protected branch)",
            credential_type="git PAT / push credential",
            m2_status=CoverageStatus.COVERED,
            residual_risk=ResidualRisk.LOW,
            deferral_target=None,
            notes=(
                "Broker denies push to configured protected branches (main, master). "
                "Force-push and credential_escalation produce broker_approval_gate suspensions. "
                "All agent-visible results are sanitized."
            ),
        ),
        CoverageEntry(
            credential_surface="arnold.security.policy.SecurityPolicy.evaluate (git_force_push, git_branch_delete, git_pr_merge, credential_escalation)",
            credential_type="git PAT / push credential",
            m2_status=CoverageStatus.COVERED,
            residual_risk=ResidualRisk.LOW,
            deferral_target=None,
            notes=(
                "Broker requires durable human approval for high-risk git operations. "
                "OperationRun transitions to AWAITING_APPROVAL with suspension_kind='broker_approval_gate'."
            ),
        ),


        # ── LLM API-key providers (covered) ─────────────────────────────
        CoverageEntry(
            credential_surface="arnold_pipelines.megaplan.runtime.key_pool.KeyPool.acquire (OpenAI-compatible API keys)",
            credential_type="LLM API key",
            m2_status=CoverageStatus.COVERED,
            residual_risk=ResidualRisk.LOW,
            deferral_target=None,
            notes=(
                "OpenAI, DeepSeek, Google Gemini, Fireworks, and custom OpenAI-compatible endpoints. "
                "Broker proxies LLM requests so raw keys never reach the agent process. "
                "resolve_provider_client() returns broker-backed client in production mode."
            ),
        ),
        CoverageEntry(
            credential_surface="arnold_pipelines.megaplan.runtime.key_pool.KeyPool.acquire (zhipu/GLM API keys)",
            credential_type="LLM API key",
            m2_status=CoverageStatus.COVERED,
            residual_risk=ResidualRisk.LOW,
            deferral_target=None,
            notes="Zhipu/GLM API key sourced from ZHIPU_API_KEY/GLM_API_KEY env vars or api_keys.json via KeyPathSource.",
        ),
        CoverageEntry(
            credential_surface="arnold_pipelines.megaplan.runtime.key_pool.KeyPool.acquire (kimi/Moonshot API keys)",
            credential_type="LLM API key",
            m2_status=CoverageStatus.COVERED,
            residual_risk=ResidualRisk.LOW,
            deferral_target=None,
            notes="Kimi/Moonshot API key sourced from KIMI_API_KEY/MOONSHOT_API_KEY env vars. Coding keys (sk-kimi-) routed to Kimi coding endpoint.",
        ),
        CoverageEntry(
            credential_surface="arnold_pipelines.megaplan.runtime.key_pool.KeyPool.acquire (minimax API keys)",
            credential_type="LLM API key",
            m2_status=CoverageStatus.COVERED,
            residual_risk=ResidualRisk.LOW,
            deferral_target=None,
            notes="MiniMax API key sourced from MINIMAX_API_KEY env var.",
        ),
        CoverageEntry(
            credential_surface="arnold_pipelines.megaplan.runtime.key_pool.KeyPool.acquire (mimo API keys)",
            credential_type="LLM API key",
            m2_status=CoverageStatus.COVERED,
            residual_risk=ResidualRisk.LOW,
            deferral_target=None,
            notes="MiMo API key sourced from MIMO_API_KEY env var.",
        ),




        # ── LLM OAuth/refresh-token providers (deferred) ────────────────




        # ── Skills hub GitHub auth (deferred) ───────────────────────────


        # ── MCP subprocess credentials (deferred) ───────────────────────


        # ── Non-LLM tool credentials ────────────────────────────────────







        # ── MCP OAuth (deferred) ────────────────────────────────────────


        # ── Terminal/SSH/gh bypasses (deferred) ─────────────────────────

        CoverageEntry(
            credential_surface="terminal_tool.py — gh CLI keychain access",
            credential_type="gh CLI OAuth token (from keychain)",
            m2_status=CoverageStatus.DEFERRED,
            residual_risk=ResidualRisk.HIGH,
            deferral_target="M5–M6",
            notes=(
                "'gh auth token' returns the GitHub CLI OAuth token from the system keychain. "
                "An agent with terminal access can extract this token. Deferred to M5–M6."
            ),
        ),

        # ── Environment loader (documented as metadata-only) ────────────


        # ── Free/local providers (documented uncovered — no secrets) ────



    ]

def get_uncovered_surfaces() -> List[CoverageEntry]:
    """Return only entries that are deferred or uncovered (not broker-covered)."""
    return [
        e
        for e in get_coverage_matrix()
        if e.m2_status in (CoverageStatus.DEFERRED, CoverageStatus.UNCOVERED)
    ]

def get_covered_surfaces() -> List[CoverageEntry]:
    """Return only entries that are broker-covered in production mode."""
    return [
        e for e in get_coverage_matrix() if e.m2_status == CoverageStatus.COVERED
    ]

def get_high_risk_deferrals() -> List[CoverageEntry]:
    """Return deferred entries with high or critical residual risk."""
    return [
        e
        for e in get_coverage_matrix()
        if e.m2_status == CoverageStatus.DEFERRED
        and e.residual_risk in (ResidualRisk.HIGH, ResidualRisk.CRITICAL)
    ]

__all__ = [
    "CoverageEntry",
    "CoverageStatus",
    "ResidualRisk",
    "get_coverage_matrix",
    "get_covered_surfaces",
    "get_high_risk_deferrals",
    "get_uncovered_surfaces",
]
