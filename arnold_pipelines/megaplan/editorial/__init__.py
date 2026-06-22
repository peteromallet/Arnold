"""Store-backed editorial operation foundations."""

from .errors import (
    EditorialError,
    EditorialNotFound,
    EditorialValidationError,
    EditorialWorkflowError,
)
from .gating import GateResult, evaluate_state_transition, transition_epic_state
from .lockdown import LOCKDOWN_REVIEW_STATES, LockdownFinding, scan_lockdown_phrases
from .reads import load_hot_context
from .types import EditorialOperation, EditorialResult, EpicId
from .body import edit_section, read_body, update_body

__all__ = [
    "EditorialError",
    "EditorialNotFound",
    "EditorialOperation",
    "EditorialResult",
    "EditorialValidationError",
    "EditorialWorkflowError",
    "EpicId",
    "GateResult",
    "LOCKDOWN_REVIEW_STATES",
    "LockdownFinding",
    "evaluate_state_transition",
    "load_hot_context",
    "edit_section",
    "read_body",
    "scan_lockdown_phrases",
    "transition_epic_state",
    "update_body",
]
