"""Canonical fixer model policy: mode/rung -> {agent_backend, provider_spec, model, budget}.

The unified fixer seam (design: docs/runtime-and-fixer-unification-design-20260807.md,
section 3) keys one model policy table by mode+rung.  This module is the single
source of truth for which backend/provider/model executes each repair rung and
how much budget it gets.

Replay gate (fail closed)
-------------------------
Every DeepSeek Flash row is marked ``status="gated"``: Flash must EARN the
default by passing the historical replay/evaluation suite (tests/fixer_replay/)
with predeclared non-inferiority thresholds before it may be dispatched without
an explicit ``replay_approved=True``.  Until then ``resolve_model_policy``
refuses gated rows unless the caller proves replay approval, so "Flash for
everything" is a measured policy choice, never an assumption.  The
``l3_orchestrator`` row (codex + deepseek-v4-pro) is the current production
reality and stays ``status="default"``.

Credentials hygiene
-------------------
``.cloud-hot-env`` is demoted to provider credentials/keys only: no
``*_MODEL`` / ``MODEL`` override variables.  ``validate_hot_env_credentials_only``
flags any such override so a stale model pin cannot silently diverge the
running fixer from this table.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Mapping, Sequence

MODEL_POLICY_SHA_ALGORITHM = "sha256"

# Budgets are seconds per repair rung.  Values follow the existing wrapper
# conventions: reactive repair defaults to 7200s total in arnold-repair-loop
# (split across investigator + mutator), L2/L3 mirror META_REPAIR_BUDGET_SECS
# (5400s), and proactive (hourly) is deliberately the longest budget.
_BUDGET_REACTIVE_STAGE_SECS = 3600
_BUDGET_PROACTIVE_SECS = 10800
_BUDGET_L2_SECS = 5400
_BUDGET_L3_ORCHESTRATOR_SECS = 5400

# Model-override variable names are forbidden in .cloud-hot-env: a bare MODEL
# var or any * _MODEL suffix is a policy override, not a credential.
_MODEL_OVERRIDE_SUFFIX = "_MODEL"
_MODEL_OVERRIDE_EXACT = "MODEL"


class PolicyError(Exception):
    """Raised when a fixer model policy row cannot be resolved or is gated."""


@dataclass(frozen=True)
class PolicyRow:
    """One mode/rung entry in the canonical fixer model policy table.

    ``model`` holds the full dispatchable provider:model spec (for example
    ``deepseek:deepseek-v4-flash``) exactly as the design table lists it;
    ``provider_spec`` names the provider used for credential selection.
    ``budget`` is the repair budget in seconds.
    """

    mode_rung: str
    agent_backend: str
    provider_spec: str
    model: str
    budget: int
    status: Literal["default", "gated"]


# Canonical policy table.  Order is declaration order; model_policy_sha()
# serializes rows sorted by mode_rung so the digest is order-independent.
MODEL_POLICY_TABLE: tuple[PolicyRow, ...] = (
    PolicyRow(
        mode_rung="reactive_investigator",
        agent_backend="deepseek",
        provider_spec="deepseek",
        model="deepseek:deepseek-v4-flash",
        budget=_BUDGET_REACTIVE_STAGE_SECS,
        status="gated",
    ),
    PolicyRow(
        mode_rung="reactive_mutator",
        agent_backend="deepseek",
        provider_spec="deepseek",
        model="deepseek:deepseek-v4-flash",
        budget=_BUDGET_REACTIVE_STAGE_SECS,
        status="gated",
    ),
    PolicyRow(
        mode_rung="proactive",
        agent_backend="deepseek",
        provider_spec="deepseek",
        model="deepseek:deepseek-v4-flash",
        budget=_BUDGET_PROACTIVE_SECS,
        status="gated",
    ),
    PolicyRow(
        mode_rung="l2",
        agent_backend="deepseek",
        provider_spec="deepseek",
        model="deepseek:deepseek-v4-flash",
        budget=_BUDGET_L2_SECS,
        status="gated",
    ),
    PolicyRow(
        mode_rung="l3_orchestrator",
        agent_backend="codex",
        provider_spec="deepseek",
        model="deepseek:deepseek-v4-pro",
        budget=_BUDGET_L3_ORCHESTRATOR_SECS,
        status="default",
    ),
)


def resolve_model_policy(
    mode_rung: str,
    *,
    replay_approved: bool = False,
    replay_evidence_path: str | None = None,
) -> PolicyRow:
    """Resolve the policy row for *mode_rung*.

    Gated rows (DeepSeek Flash) fail closed: they raise PolicyError unless the
    caller proves replay-suite approval via ``replay_approved=True`` AND names
    a readable evidence file in ``replay_evidence_path`` (the replay suite's
    durable approval record — a bare flag alone is not evidence).  Unknown
    mode/rung values always raise PolicyError.
    """
    for row in MODEL_POLICY_TABLE:
        if row.mode_rung == mode_rung:
            if row.status == "gated":
                _require_replay_evidence(
                    mode_rung,
                    replay_approved=replay_approved,
                    replay_evidence_path=replay_evidence_path,
                )
            return row
    known = ", ".join(row.mode_rung for row in MODEL_POLICY_TABLE)
    raise PolicyError(f"unknown fixer mode/rung {mode_rung!r}; known: {known}")


def _require_replay_evidence(
    mode_rung: str, *, replay_approved: bool, replay_evidence_path: str | None
) -> None:
    """Fail closed unless durable replay approval evidence is provable.

    Gated rows require BOTH the ``replay_approved`` flag AND a readable
    evidence file: the flag records that the replay suite passed, the file
    (whose mtime/digest the caller may check) is the durable artifact that
    makes the claim auditable.  A missing or unreadable file is a PolicyError,
    never a silent pass.
    """
    if not replay_approved:
        raise PolicyError(
            f"model policy row {mode_rung!r} is gated: "
            "DeepSeek Flash must pass the replay/evaluation suite "
            "(tests/fixer_replay/) before it becomes the default; "
            "replay approval is read from durable evidence, not assumed"
        )
    if not replay_evidence_path:
        raise PolicyError(
            f"model policy row {mode_rung!r} is gated and replay_approved=True "
            "was passed without replay_evidence_path: the replay suite's "
            "durable approval record must be named, not just asserted"
        )
    evidence = Path(replay_evidence_path)
    try:
        evidence.stat()
        with evidence.open("rb"):
            pass
    except (OSError, ValueError) as exc:
        raise PolicyError(
            f"model policy row {mode_rung!r} is gated: replay approval "
            f"evidence file is unreadable at {replay_evidence_path}: {exc}"
        ) from exc


def validate_hot_env_credentials_only(env: Mapping[str, str]) -> list[str]:
    """Return model-override violations in *env* (empty list = clean).

    ``.cloud-hot-env`` is demoted to provider credentials/keys only.  Any
    variable named ``MODEL`` or ending in ``_MODEL`` is a policy override and
    is returned (sorted) as a violation.  Credential variables (KEY/TOKEN/
    SECRET/API and anything else) are tolerated.
    """
    violations: list[str] = []
    for name in env:
        upper = name.upper()
        if upper == _MODEL_OVERRIDE_EXACT or upper.endswith(
            _MODEL_OVERRIDE_SUFFIX
        ):
            violations.append(name)
    return sorted(violations)


def _canonical_table_serialization() -> str:
    """Deterministic JSON serialization of MODEL_POLICY_TABLE sorted by mode_rung."""
    rows = sorted(
        (asdict(row) for row in MODEL_POLICY_TABLE),
        key=lambda row: row["mode_rung"],
    )
    return json.dumps(rows, sort_keys=True, ensure_ascii=True)


def model_policy_sha() -> str:
    """Deterministic digest over the canonical serialization of the policy table."""
    return hashlib.new(
        MODEL_POLICY_SHA_ALGORITHM,
        _canonical_table_serialization().encode("utf-8"),
    ).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    """Print the canonical fixer model policy table and its policy SHA."""
    parser = argparse.ArgumentParser(
        description="Print the canonical fixer model policy table and its policy SHA"
    )
    parser.parse_args(argv)
    header = (
        "mode_rung",
        "agent_backend",
        "provider_spec",
        "model",
        "budget_s",
        "status",
    )
    rows = [
        (
            row.mode_rung,
            row.agent_backend,
            row.provider_spec,
            row.model,
            str(row.budget),
            row.status,
        )
        for row in MODEL_POLICY_TABLE
    ]
    widths = [
        max(len(header[i]), *(len(row[i]) for row in rows))
        for i in range(len(header))
    ]

    def _format(row: Sequence[str]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))

    print(_format(header))
    for row in rows:
        print(_format(row))
    print(f"model_policy_sha={model_policy_sha()}")
    return 0


__all__ = [
    "MODEL_POLICY_TABLE",
    "MODEL_POLICY_SHA_ALGORITHM",
    "PolicyError",
    "PolicyRow",
    "main",
    "model_policy_sha",
    "resolve_model_policy",
    "validate_hot_env_credentials_only",
]


if __name__ == "__main__":
    raise SystemExit(main())
