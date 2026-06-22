"""Activation identity and readiness model for the hinge layer.

An :class:`Activation` represents a specific invocation of a pipeline node
with a fixed set of input ports and a profile.  Its id is a 16-hex-char
content address derived exclusively from (node, input_ports, profile) so that
two processes that agree on those three values always agree on the id.

SD2 (settled): id = hashlib.sha256(canonical_json_dumps({...}).encode()).hexdigest()[:16]
— direct hashlib, NOT the ``sha256:``-prefixed ``canonical_sha256`` helper.
"""

from __future__ import annotations

import enum
import hashlib
from dataclasses import dataclass, field
from typing import Any, FrozenSet, Optional

from arnold_pipelines.megaplan.store.snapshot import canonical_json_dumps


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ReadinessRule(str, enum.Enum):
    """When is an activation ready to run?"""
    UPSTREAM_DONE = "upstream_done"
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    EXTERNAL_EVENT = "external_event"


class LifecycleState(str, enum.Enum):
    """Coarse lifecycle of an activation."""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

def compute_activation_id(
    node: str,
    input_ports: Any,
    profile: str,
) -> str:
    """Return a 16-hex-char content address for (node, input_ports, profile).

    ``input_ports`` may be a list or tuple; both are normalised to a list
    before hashing so the id is stable across representations.
    """
    payload = {
        "node": node,
        "input_ports": list(input_ports),
        "profile": profile,
    }
    return hashlib.sha256(
        canonical_json_dumps(payload).encode("utf-8")
    ).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Activation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Activation:
    """Immutable description of one node invocation."""

    id: str
    node: str
    input_ports: FrozenSet[str]
    profile: str
    readiness_rule: ReadinessRule
    lifecycle: LifecycleState = LifecycleState.PENDING

    def is_ready(self) -> bool:
        """Return True when the activation is eligible to run.

        Only :attr:`ReadinessRule.UPSTREAM_DONE` is implemented; all other
        rules raise :exc:`NotImplementedError`.
        """
        if self.readiness_rule is ReadinessRule.UPSTREAM_DONE:
            return self.lifecycle is LifecycleState.READY
        raise NotImplementedError(
            f"is_ready not implemented for readiness_rule={self.readiness_rule!r}"
        )
