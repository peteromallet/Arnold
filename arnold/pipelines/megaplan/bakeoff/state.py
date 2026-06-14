"""Bake-off coordination state."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Literal, TypedDict

from arnold.pipelines.megaplan._core.io import atomic_write_json, read_json


BAKEOFF_SCHEMA_VERSION: Literal[1] = 1
CHANNEL_SHADOW_SCHEMA_VERSION: Literal[1] = 1
BakeoffPhase = Literal["running", "compared", "picked", "merged", "abandoned"]
ChannelShadowSkipReason = Literal[
    "not_sampled",
    "shadow_disabled",
    "cap_pressure",
    "rate_limited",
    "primary_failed_before_shadow",
    "shadow_unavailable",
]


class BakeoffProfileRecord(TypedDict):
    name: str
    worktree: str
    plan_id: str
    pid: int | None
    launched_at: str | None
    terminated_at: str | None
    outcome: dict[str, Any] | None
    log_path: str
    outcome_path: str


class BakeoffState(TypedDict, total=False):
    schema_version: Literal[1]
    experiment_id: str
    base_sha: str
    idea_hash: str
    idea_path: str
    mode: str
    # Relative (to each worktree) path to the doc artifact in --mode doc bake-offs.
    # Absent / None for code-mode bake-offs. Kept optional so historical state
    # files written before this field existed still load.
    output_path: str | None
    profiles: list[BakeoffProfileRecord]
    phase: BakeoffPhase
    chosen_profile: str | None
    merged_at: str | None
    judge_model: str | None


class ChannelShadowReceiptRecord(TypedDict, total=False):
    receipt_path: str | None
    worker_channel: str
    auth_channel: str | None
    phase: str
    plan_id: str
    exit_kind: str | None
    payload_schema_valid: bool | None
    landed_diff: str | None
    worker_did_work: str | None
    latency_ms: int | None
    cost_usd: float | None
    metadata: dict[str, Any]


class ChannelShadowDecision(TypedDict):
    sampled: bool
    skipped: bool
    skip_reason: ChannelShadowSkipReason | None
    sample_rate: float
    sample_key: str


class ChannelShadowLatencyCostDrift(TypedDict):
    primary_latency_ms: int | None
    shadow_latency_ms: int | None
    latency_drift_ms: int | None
    latency_drift_ratio: float | None
    primary_cost_usd: float | None
    shadow_cost_usd: float | None
    cost_drift_usd: float | None
    cost_drift_ratio: float | None


class ChannelShadowParityResult(TypedDict):
    passed: bool
    exit_kind_match: bool
    payload_schema_valid_match: bool
    landed_diff_match: bool
    worker_did_work_match: bool
    compared_at: str
    details: dict[str, Any]


class ChannelShadowPair(TypedDict):
    primary_worker_channel: str
    primary_auth_channel: str | None
    shadow_worker_channel: str
    shadow_auth_channel: str | None


class ChannelShadowProvenance(TypedDict, total=False):
    source: str
    fixture: bool
    sample_key: str
    plan_id: str
    phase: str


class ChannelShadowGate(TypedDict):
    greenlight: bool
    threshold: int
    real_parity_success_count: int
    real_parity_failure_count: int
    skipped_count: int
    fixture_count: int
    blockers: list[str]
    channel_pair: ChannelShadowPair | None
    provenance: dict[str, Any]
    evaluated_at: str
    api_channel_greenlight: bool
    api_channel_blockers: list[str]


class ChannelShadowRecord(TypedDict, total=False):
    channel_pair: ChannelShadowPair
    provenance: ChannelShadowProvenance
    decision: ChannelShadowDecision
    primary_receipt: ChannelShadowReceiptRecord
    shadow_receipt: ChannelShadowReceiptRecord | None
    drift: ChannelShadowLatencyCostDrift | None
    parity_result: ChannelShadowParityResult | None
    real_parity_success_count: int
    recorded_at: str


class ChannelShadowState(TypedDict):
    schema_version: Literal[1]
    experiment_id: str
    records: list[ChannelShadowRecord]
    real_parity_success_count: int
    gate: ChannelShadowGate


def bakeoff_root(root: Path, exp_id: str) -> Path:
    return root / ".megaplan" / "bakeoffs" / exp_id


def worktree_root(root: Path, exp_id: str) -> Path:
    return root.resolve().parent / ".megaplan-worktrees" / exp_id


def load_bakeoff_state(root: Path, exp_id: str) -> BakeoffState:
    return read_json(bakeoff_root(root, exp_id) / "bakeoff.json")


def save_bakeoff_state(root: Path, state: BakeoffState) -> None:
    atomic_write_json(
        bakeoff_root(root, state["experiment_id"]) / "bakeoff.json",
        state,
    )


def channel_shadow_path(root: Path, exp_id: str) -> Path:
    return bakeoff_root(root, exp_id) / "channel_shadow.json"


def load_channel_shadow_state(root: Path, exp_id: str) -> ChannelShadowState:
    return read_json(channel_shadow_path(root, exp_id))


def save_channel_shadow_state(root: Path, state: ChannelShadowState) -> None:
    atomic_write_json(
        channel_shadow_path(root, state["experiment_id"]),
        state,
    )


def hash_idea_file(path: Path) -> str:
    content = path.read_text(encoding="utf-8").encode("utf-8")
    return hashlib.sha256(content).hexdigest()
