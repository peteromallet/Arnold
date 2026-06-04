from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from .agent_contracts import FailureEnvelope, FailureKind, TurnContext, failure_envelope

STATE_FILE_NAME = "session_state.json"
LOCK_FILE_NAME = ".session_state.lock"
STATE_SCHEMA_VERSION = 1
# Bumped whenever `structural_graph_projection` changes shape. A baseline hash
# stored by an older version is recomputed from the on-disk accepted graph on
# read, so a projection change never strands an open session on a stale baseline
# it can no longer match (the StaleStateMismatch-on-every-submit failure mode).
STRUCTURAL_PROJECTION_VERSION = 2
DEFAULT_LOCK_TIMEOUT_SECONDS = 10.0
LOCK_POLL_SECONDS = 0.025

OperationScope = Literal["edit", "accept", "reject"]
TurnState = Literal["candidate", "accepted", "rejected", "unknown"]


@dataclass(frozen=True)
class IdempotencyReplay:
    response: dict[str, Any]
    record: dict[str, Any]


@dataclass(frozen=True)
class IdempotencyConflict:
    failure: FailureEnvelope
    record: dict[str, Any]


@dataclass(frozen=True)
class TurnAllocation:
    context: TurnContext
    session_dir: Path
    turn_dir: Path
    state: dict[str, Any]
    request_hash: str
    unknown_transitions: tuple[dict[str, Any], ...] = ()
    idempotency_record_key: str | None = None
    replay: IdempotencyReplay | None = None
    conflict: IdempotencyConflict | None = None


def session_dir_for(root: Path, session_id: str) -> Path:
    return root / session_id


def turn_dir_for(root: Path, session_id: str, turn_id: str) -> Path:
    return session_dir_for(root, session_id) / "turns" / turn_id


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def payload_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class SessionStateLock:
    def __init__(
        self,
        session_dir: Path,
        *,
        timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
    ) -> None:
        self.session_dir = session_dir
        self.lock_path = session_dir / LOCK_FILE_NAME
        self.timeout_seconds = timeout_seconds
        self._fd: int | None = None

    def __enter__(self) -> "SessionStateLock":
        self.session_dir.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            try:
                self._fd = os.open(
                    self.lock_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600,
                )
                os.write(self._fd, f"{os.getpid()} {time.time()}\n".encode("ascii"))
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timed out acquiring session lock {self.lock_path}")
                time.sleep(LOCK_POLL_SECONDS)

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            self.lock_path.unlink()
        except FileNotFoundError:
            pass


def default_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "next_turn_index": 1,
        "baseline_turn_id": None,
        "baseline_graph_hash": None,
        "baseline_graph_hash_kind": None,
        "turns": {},
        "idempotency_records": {},
    }


def read_state(session_dir: Path) -> dict[str, Any]:
    path = session_dir / STATE_FILE_NAME
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default_state()
    if not isinstance(state, dict):
        return default_state()
    merged = default_state()
    merged.update(state)
    if not isinstance(merged.get("turns"), dict):
        merged["turns"] = {}
    if not isinstance(merged.get("idempotency_records"), dict):
        merged["idempotency_records"] = {}
    if not isinstance(merged.get("next_turn_index"), int) or merged["next_turn_index"] < 1:
        merged["next_turn_index"] = 1
    if isinstance(merged.get("baseline_turn_id"), str):
        baseline_turn = merged["turns"].get(merged["baseline_turn_id"])
        if isinstance(baseline_turn, dict):
            structural_hash = baseline_turn.get("candidate_structural_graph_hash")
            stored_version = baseline_turn.get("candidate_structural_graph_hash_version")
            # Recompute when the hash is missing OR was produced by an older
            # projection version. Recomputing from the on-disk accepted candidate
            # re-runs the CURRENT projection, so a session opened across a code
            # change heals its baseline instead of mismatching on every submit.
            if (
                not isinstance(structural_hash, str)
                or stored_version != STRUCTURAL_PROJECTION_VERSION
            ):
                recomputed = _candidate_structural_hash_from_turn_dir(
                    session_dir=path.parent,
                    turn_id=merged["baseline_turn_id"],
                )
                if isinstance(recomputed, str):
                    structural_hash = recomputed
                    baseline_turn["candidate_structural_graph_hash"] = recomputed
                    baseline_turn[
                        "candidate_structural_graph_hash_version"
                    ] = STRUCTURAL_PROJECTION_VERSION
            if isinstance(structural_hash, str):
                merged["baseline_graph_hash"] = structural_hash
                merged["baseline_graph_hash_kind"] = "structural"
            elif merged.get("baseline_graph_hash") is None:
                migrated_hash = baseline_turn.get("candidate_graph_hash") or baseline_turn.get(
                    "client_graph_hash"
                )
                merged["baseline_graph_hash"] = (
                    migrated_hash if isinstance(migrated_hash, str) else None
                )
                merged["baseline_graph_hash_kind"] = (
                    "raw" if isinstance(merged["baseline_graph_hash"], str) else None
                )
    if (
        merged.get("baseline_graph_hash") is not None
        and merged.get("baseline_graph_hash_kind") is None
    ):
        merged["baseline_graph_hash_kind"] = "raw"
    merged["schema_version"] = STATE_SCHEMA_VERSION
    return merged


def _natural_id_key(value: Any) -> tuple[int, int | str]:
    text = str(value if value is not None else "")
    if re_match := re.fullmatch(r"-?\d+", text):
        return (0, int(re_match.group(0)))
    return (1, text)


def _is_preview_like_key(key: Any) -> bool:
    return re.search(r"(?:^|_)(?:video)?preview(?:_|$)", str(key or ""), re.I) is not None


def _normalize_structural_widget_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_normalize_structural_widget_value(entry) for entry in value]
    if isinstance(value, dict):
        return {
            key: _normalize_structural_widget_value(entry)
            for key, entry in sorted(value.items(), key=lambda item: str(item[0]))
            if not _is_preview_like_key(key)
        }
    # Canonicalise integral floats to ints so the hash matches what the browser
    # round-trips. JS `JSON.stringify(2.0)` emits `2`, so the backend's float
    # widget value (e.g. scale_by=2.0) and the canvas's resubmitted `2` are the
    # same graph and must hash identically. (bool is an int subclass — leave it.)
    if isinstance(value, float) and not isinstance(value, bool):
        if value == value and value not in (float("inf"), float("-inf")):
            if value.is_integer():
                return int(value)
    return value


def _normalize_structural_link(value: Any) -> Any:
    if isinstance(value, list):
        return [_normalize_structural_link(entry) for entry in value]
    if isinstance(value, dict):
        return {
            key: _normalize_structural_link(entry)
            for key, entry in sorted(value.items(), key=lambda item: str(item[0]))
        }
    return value


def structural_graph_projection(graph: Any) -> dict[str, Any]:
    if not isinstance(graph, Mapping):
        return {"nodes": [], "links": []}
    raw_nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    # Per-node slot-index -> name maps, so links can be projected by NAME. This
    # makes the hash invariant to ComfyUI materialising declared-but-unwired input
    # slots on apply (which shifts later inputs' slot indices and would otherwise
    # change the hash for a graph whose actual wiring is unchanged).
    input_names: dict[Any, list[Any]] = {}
    output_names: dict[Any, list[Any]] = {}
    for node in raw_nodes:
        if not isinstance(node, Mapping):
            continue
        nid = node.get("id")
        input_names[nid] = [
            (i.get("name") if isinstance(i, Mapping) else None)
            for i in (node.get("inputs") if isinstance(node.get("inputs"), list) else [])
        ]
        output_names[nid] = [
            (o.get("name") if isinstance(o, Mapping) else None)
            for o in (node.get("outputs") if isinstance(node.get("outputs"), list) else [])
        ]
    nodes: list[dict[str, Any]] = []
    for node in raw_nodes:
        if not isinstance(node, Mapping):
            node = {}
        # Only WIRED input names — an unwired slot ComfyUI adds on apply is not
        # meaningful graph state and must not change the hash.
        wired_inputs = sorted(
            str(i.get("name"))
            for i in (node.get("inputs") if isinstance(node.get("inputs"), list) else [])
            if isinstance(i, Mapping)
            and i.get("link") is not None
            and i.get("name") is not None
        )
        live_outputs = sorted(
            str(o.get("name"))
            for o in (node.get("outputs") if isinstance(node.get("outputs"), list) else [])
            if isinstance(o, Mapping) and o.get("links") and o.get("name") is not None
        )
        nodes.append(
            {
                "id": node.get("id"),
                "type": node.get("type"),
                "mode": node.get("mode"),
                "inputs": wired_inputs,
                "outputs": live_outputs,
                "widgets_values": _normalize_structural_widget_value(
                    node.get("widgets_values", [])
                ),
            }
        )
    nodes.sort(
        key=lambda node: (_natural_id_key(node.get("id")), str(node.get("type") or ""))
    )

    def _slot_name(names: list[Any], slot: Any) -> Any:
        if isinstance(slot, int) and 0 <= slot < len(names):
            return names[slot]
        return slot

    # Project links by endpoint NAME (not slot index or link id) so they survive
    # slot reordering and link renumbering across the apply round-trip.
    links: list[dict[str, Any]] = []
    for link in (graph.get("links") if isinstance(graph.get("links"), list) else []):
        if isinstance(link, list) and len(link) >= 6:
            o_id, o_slot, t_id, t_slot, l_type = (
                link[1], link[2], link[3], link[4], link[5],
            )
        elif isinstance(link, Mapping):
            o_id, o_slot = link.get("origin_id"), link.get("origin_slot")
            t_id, t_slot = link.get("target_id"), link.get("target_slot")
            l_type = link.get("type")
        else:
            continue
        links.append(
            {
                "from": o_id,
                "out": _slot_name(output_names.get(o_id, []), o_slot),
                "to": t_id,
                "in": _slot_name(input_names.get(t_id, []), t_slot),
                "type": l_type,
            }
        )
    links.sort(
        key=lambda link: json.dumps(
            link, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
    )
    return {"nodes": nodes, "links": links}


def structural_graph_hash(graph: Any) -> str | None:
    if not isinstance(graph, Mapping):
        return None
    return payload_hash(structural_graph_projection(graph))


def _candidate_structural_hash_from_turn_dir(
    *, session_dir: Path, turn_id: str
) -> str | None:
    for filename in ("candidate.ui.json", "response.json"):
        path = session_dir / "turns" / turn_id / filename
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        graph = (
            payload.get("graph")
            if filename == "response.json" and isinstance(payload, Mapping)
            else payload
        )
        digest = structural_graph_hash(graph)
        if isinstance(digest, str):
            return digest
    return None


def write_state_atomic(session_dir: Path, state: dict[str, Any]) -> None:
    session_dir.mkdir(parents=True, exist_ok=True)
    target = session_dir / STATE_FILE_NAME
    tmp = session_dir / f".{STATE_FILE_NAME}.{os.getpid()}.{time.monotonic_ns()}.tmp"
    tmp.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(target)


def _record_key(scope: OperationScope, idempotency_key: str | None) -> str | None:
    if not idempotency_key:
        return None
    return f"{scope}:{idempotency_key}"


def _load_response(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _conflict_kind(scope: OperationScope) -> FailureKind:
    if scope == "edit":
        return FailureKind.STALE_STATE_MISMATCH
    return FailureKind.EDITOR_AHEAD_CONFLICT


def _mapping_graph_hash(payload: Any, *, field: str = "graph") -> str | None:
    if not isinstance(payload, Mapping):
        return None
    graph = payload.get(field)
    if not isinstance(graph, Mapping):
        return None
    return payload_hash(graph)


def _mapping_graph_structural_hash(payload: Any, *, field: str = "graph") -> str | None:
    if not isinstance(payload, Mapping):
        return None
    return structural_graph_hash(payload.get(field))


def _client_graph_hash(payload: Any) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    value = payload.get("client_graph_hash")
    return value if isinstance(value, str) else None


def _client_structural_graph_hash(payload: Any) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    value = payload.get("client_structural_graph_hash")
    return value if isinstance(value, str) else None


def _client_live_canvas_token(payload: Any) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    value = payload.get("client_live_canvas_token")
    return value if isinstance(value, str) else None


def allocate_turn(
    *,
    session_root: Path,
    session_id: str,
    request_payload: Any,
    idempotency_key: str | None = None,
    lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> TurnAllocation:
    session_dir = session_dir_for(session_root, session_id)
    request_digest = payload_hash(request_payload)
    submit_graph_hash = _mapping_graph_hash(request_payload)
    submit_structural_graph_hash = _mapping_graph_structural_hash(request_payload)
    submitted_client_graph_hash = _client_graph_hash(request_payload)
    submitted_client_structural_graph_hash = _client_structural_graph_hash(request_payload)
    submitted_client_live_canvas_token = _client_live_canvas_token(request_payload)
    key = _record_key("edit", idempotency_key)

    with SessionStateLock(session_dir, timeout_seconds=lock_timeout_seconds):
        state = read_state(session_dir)
        if key is not None:
            existing = state["idempotency_records"].get(key)
            if isinstance(existing, dict):
                context = TurnContext(
                    session_id=session_id,
                    turn_id=existing.get("turn_id"),
                    baseline_turn_id=state.get("baseline_turn_id"),
                    idempotency_key=idempotency_key,
                )
                if existing.get("request_hash") == request_digest:
                    response = _load_response(existing.get("response_path"))
                    if response is not None:
                        return TurnAllocation(
                            context=context,
                            session_dir=session_dir,
                            turn_dir=turn_dir_for(session_root, session_id, str(context.turn_id)),
                            state=state,
                            request_hash=request_digest,
                            idempotency_record_key=key,
                            replay=IdempotencyReplay(response=response, record=dict(existing)),
                        )
                failure = failure_envelope(
                    _conflict_kind("edit"),
                    "ingest",
                    context,
                    agent_failure_context={
                        "explanation": "Idempotency key was reused with a different request hash.",
                        "idempotency_key": idempotency_key,
                        "existing_request_hash": existing.get("request_hash"),
                        "request_hash": request_digest,
                    },
                )
                return TurnAllocation(
                    context=context,
                    session_dir=session_dir,
                    turn_dir=turn_dir_for(session_root, session_id, str(context.turn_id)),
                    state=state,
                    request_hash=request_digest,
                    idempotency_record_key=key,
                    conflict=IdempotencyConflict(failure=failure, record=dict(existing)),
                )

        turn_index = int(state["next_turn_index"])
        turn_id = f"{turn_index:04d}"
        state["next_turn_index"] = turn_index + 1
        state["turns"][turn_id] = {
            "state": "candidate",
            "submit_graph_hash": submit_graph_hash,
            "submit_structural_graph_hash": submit_structural_graph_hash,
            "submitted_client_graph_hash": submitted_client_graph_hash,
            "submitted_client_structural_graph_hash": submitted_client_structural_graph_hash,
            "submitted_client_live_canvas_token": submitted_client_live_canvas_token,
            "candidate_graph_hash": None,
            "candidate_structural_graph_hash": None,
            "agent_edit_protocol": None,
            "client_graph_hash": None,
            "accepted_at": None,
            "rejected_at": None,
            "action_request_hash": None,
            "action_client_graph_hash": None,
            "action_submit_graph_hash": None,
            "created_at": _now(),
        }
        unknown_transitions: list[dict[str, Any]] = []
        for other_turn_id, other_record in state["turns"].items():
            if other_turn_id == turn_id or not isinstance(other_record, dict):
                continue
            if other_record.get("state") != "candidate":
                continue
            other_record["state"] = "unknown"
            other_record["unknown_at"] = other_record.get("unknown_at") or _now()
            other_record["unknown_reason"] = "superseded_by_new_submit"
            other_record["superseded_by_turn_id"] = turn_id
            transitioned_at = other_record["unknown_at"]
            unknown_transitions.append(
                {
                    "session_id": session_id,
                    "turn_id": other_turn_id,
                    "from_state": "candidate",
                    "to_state": "unknown",
                    "reason": "superseded_by_new_submit",
                    "superseded_by_turn_id": turn_id,
                    "transitioned_at": transitioned_at,
                }
            )
        write_state_atomic(session_dir, state)

    turn_dir = turn_dir_for(session_root, session_id, turn_id)
    turn_dir.mkdir(parents=True, exist_ok=True)
    return TurnAllocation(
        context=TurnContext(
            session_id=session_id,
            turn_id=turn_id,
            baseline_turn_id=state.get("baseline_turn_id"),
            idempotency_key=idempotency_key,
        ),
        session_dir=session_dir,
        turn_dir=turn_dir,
        state=state,
        request_hash=request_digest,
        unknown_transitions=tuple(unknown_transitions),
        idempotency_record_key=key,
    )


def record_idempotent_response(
    *,
    session_root: Path,
    session_id: str,
    scope: OperationScope,
    idempotency_key: str | None,
    request_hash: str,
    response: dict[str, Any],
    response_path: Path,
    operation: str,
    turn_id: str | None,
    lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> dict[str, Any] | None:
    key = _record_key(scope, idempotency_key)
    candidate_graph_hash = _mapping_graph_hash(response)
    candidate_structural_graph_hash = _mapping_graph_structural_hash(response)
    agent_edit_protocol = "v2_delta" if isinstance(response.get("delta_ops"), list) else "v1"
    if key is None:
        if scope == "edit" and turn_id is not None:
            session_dir = session_dir_for(session_root, session_id)
            with SessionStateLock(session_dir, timeout_seconds=lock_timeout_seconds):
                state = read_state(session_dir)
                turn_record = state["turns"].get(turn_id)
                if isinstance(turn_record, dict):
                    turn_record["candidate_graph_hash"] = candidate_graph_hash
                    turn_record["candidate_structural_graph_hash"] = candidate_structural_graph_hash
                    turn_record[
                        "candidate_structural_graph_hash_version"
                    ] = STRUCTURAL_PROJECTION_VERSION
                    turn_record["agent_edit_protocol"] = agent_edit_protocol
                    write_state_atomic(session_dir, state)
        return None
    response_path.parent.mkdir(parents=True, exist_ok=True)
    response_path.write_text(json.dumps(response, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    response_digest = payload_hash(response)
    record = {
        "request_hash": request_hash,
        "response_hash": response_digest,
        "response_path": str(response_path),
        "created_at": _now(),
        "operation": operation,
        "turn_id": turn_id,
    }
    session_dir = session_dir_for(session_root, session_id)
    with SessionStateLock(session_dir, timeout_seconds=lock_timeout_seconds):
        state = read_state(session_dir)
        if scope == "edit" and turn_id is not None:
            turn_record = state["turns"].get(turn_id)
            if isinstance(turn_record, dict):
                turn_record["candidate_graph_hash"] = candidate_graph_hash
                turn_record["candidate_structural_graph_hash"] = candidate_structural_graph_hash
                turn_record["agent_edit_protocol"] = agent_edit_protocol
        state["idempotency_records"][key] = record
        write_state_atomic(session_dir, state)
    return record


def _mutate_turn_state(
    *,
    session_root: Path,
    session_id: str,
    turn_id: str,
    scope: Literal["accept", "reject"],
    client_graph_hash: str | None,
    request_payload: Any,
    idempotency_key: str | None = None,
    response_writer: Callable[[dict[str, Any]], Path] | None = None,
    lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> dict[str, Any] | FailureEnvelope:
    session_dir = session_dir_for(session_root, session_id)
    request_digest = payload_hash(request_payload)
    key = _record_key(scope, idempotency_key)

    with SessionStateLock(session_dir, timeout_seconds=lock_timeout_seconds):
        state = read_state(session_dir)
        context = TurnContext(
            session_id=session_id,
            turn_id=turn_id,
            baseline_turn_id=state.get("baseline_turn_id"),
            idempotency_key=idempotency_key,
        )
        if key is not None:
            existing = state["idempotency_records"].get(key)
            if isinstance(existing, dict):
                if existing.get("request_hash") == request_digest:
                    response = _load_response(existing.get("response_path"))
                    if response is not None:
                        return response
                return failure_envelope(
                    _conflict_kind(scope),
                    scope,
                    context,
                    agent_failure_context={
                        "explanation": "Idempotency key was reused with a different request hash.",
                        "idempotency_key": idempotency_key,
                        "existing_request_hash": existing.get("request_hash"),
                        "request_hash": request_digest,
                    },
                )

        turn_record = state["turns"].get(turn_id)
        if not isinstance(turn_record, dict):
            return failure_envelope(
                FailureKind.STALE_STATE_MISMATCH,
                scope,
                context,
                agent_failure_context={"explanation": f"Unknown turn_id {turn_id!r}."},
            )

        current_state = turn_record.get("state")
        target_state: TurnState = "accepted" if scope == "accept" else "rejected"
        opposite_state: TurnState = "rejected" if scope == "accept" else "accepted"
        if current_state == "unknown":
            return failure_envelope(
                FailureKind.STALE_STATE_MISMATCH,
                scope,
                context,
                agent_failure_context={
                    "explanation": f"Turn {turn_id} was superseded by a newer accepted turn.",
                    "accepted_state": current_state,
                },
            )
        if current_state == opposite_state:
            return failure_envelope(
                FailureKind.EDITOR_AHEAD_CONFLICT,
                scope,
                context,
                agent_failure_context={
                    "explanation": f"Turn {turn_id} is already {opposite_state}.",
                    "accepted_state": current_state,
                },
            )

        submit_graph_hash = turn_record.get("submit_graph_hash")
        if not isinstance(submit_graph_hash, str):
            return failure_envelope(
                FailureKind.STALE_STATE_MISMATCH,
                scope,
                context,
                agent_failure_context={
                    "explanation": "Turn has no persisted submit graph hash.",
                    "turn_id": turn_id,
                    "submit_graph_hash_present": False,
                },
            )
        candidate_graph_hash = turn_record.get("candidate_graph_hash")
        if not isinstance(candidate_graph_hash, str):
            return failure_envelope(
                FailureKind.STALE_STATE_MISMATCH,
                scope,
                context,
                agent_failure_context={
                    "explanation": "Turn has no persisted candidate graph hash.",
                    "turn_id": turn_id,
                    "candidate_graph_hash_present": False,
                },
            )
        candidate_structural_graph_hash = turn_record.get("candidate_structural_graph_hash")
        stored_struct_version = turn_record.get("candidate_structural_graph_hash_version")
        if (
            not isinstance(candidate_structural_graph_hash, str)
            or stored_struct_version != STRUCTURAL_PROJECTION_VERSION
        ):
            recomputed = _candidate_structural_hash_from_turn_dir(
                session_dir=session_dir,
                turn_id=turn_id,
            )
            if isinstance(recomputed, str):
                candidate_structural_graph_hash = recomputed
                turn_record["candidate_structural_graph_hash"] = recomputed
                turn_record[
                    "candidate_structural_graph_hash_version"
                ] = STRUCTURAL_PROJECTION_VERSION
        if not isinstance(candidate_structural_graph_hash, str):
            return failure_envelope(
                FailureKind.STALE_STATE_MISMATCH,
                scope,
                context,
                agent_failure_context={
                    "explanation": "Turn has no persisted candidate structural graph hash.",
                    "turn_id": turn_id,
                    "candidate_structural_graph_hash_present": False,
                },
            )
        agent_edit_protocol = turn_record.get("agent_edit_protocol")
        submitted_client_graph_hash = turn_record.get("submitted_client_graph_hash")
        if scope == "accept" and agent_edit_protocol == "v2_delta":
            if not isinstance(request_payload, Mapping):
                return failure_envelope(
                    FailureKind.STALE_STATE_MISMATCH,
                    scope,
                    context,
                    agent_failure_context={"explanation": "Accept request body must be a JSON object."},
                )
            request_submit_graph_hash = request_payload.get("submit_graph_hash")
            request_candidate_graph_hash = request_payload.get("candidate_graph_hash")
            request_live_canvas_token = request_payload.get("client_live_canvas_token")
            submitted_live_canvas_token = turn_record.get("submitted_client_live_canvas_token")
            if request_submit_graph_hash != submit_graph_hash:
                return failure_envelope(
                    FailureKind.STALE_STATE_MISMATCH,
                    scope,
                    context,
                    agent_failure_context={
                        "explanation": "Accepted v2 turn did not echo the server-side submit graph hash.",
                        "turn_id": turn_id,
                        "submit_graph_hash": submit_graph_hash,
                        "request_submit_graph_hash": request_submit_graph_hash,
                    },
                )
            if request_candidate_graph_hash != candidate_graph_hash:
                return failure_envelope(
                    FailureKind.STALE_STATE_MISMATCH,
                    scope,
                    context,
                    agent_failure_context={
                        "explanation": "Accepted v2 turn did not match the persisted candidate graph hash.",
                        "turn_id": turn_id,
                        "candidate_graph_hash": candidate_graph_hash,
                        "request_candidate_graph_hash": request_candidate_graph_hash,
                    },
                )
            if (
                not isinstance(submitted_live_canvas_token, str)
                or not submitted_live_canvas_token
                or request_live_canvas_token != submitted_live_canvas_token
            ):
                return failure_envelope(
                    FailureKind.STALE_STATE_MISMATCH,
                    scope,
                    context,
                    agent_failure_context={
                        "explanation": "Client live-canvas token does not match the token captured at v2 submit time.",
                        "turn_id": turn_id,
                        "client_live_canvas_token": request_live_canvas_token,
                        "submitted_client_live_canvas_token": submitted_live_canvas_token,
                    },
                )
        else:
            # V1 compatibility: the backend's `submit_graph_hash` is canonical,
            # while older browser clients send their own hash. Accept either
            # submit-time fingerprint only for non-v2 turns.
            accepted_submit_hashes = {submit_graph_hash}
            if isinstance(submitted_client_graph_hash, str) and submitted_client_graph_hash:
                accepted_submit_hashes.add(submitted_client_graph_hash)
            if client_graph_hash not in accepted_submit_hashes:
                return failure_envelope(
                    FailureKind.STALE_STATE_MISMATCH,
                    scope,
                    context,
                    agent_failure_context={
                        "explanation": "Client graph hash does not match the graph submitted for this turn.",
                        "turn_id": turn_id,
                        "client_graph_hash": client_graph_hash,
                        "submit_graph_hash": submit_graph_hash,
                        "submitted_client_graph_hash": submitted_client_graph_hash,
                    },
                )

        timestamp_key = "accepted_at" if scope == "accept" else "rejected_at"
        turn_record["state"] = target_state
        turn_record["client_graph_hash"] = client_graph_hash
        turn_record[timestamp_key] = turn_record.get(timestamp_key) or _now()
        turn_record["action_request_hash"] = request_digest
        turn_record["action_client_graph_hash"] = client_graph_hash
        turn_record["action_submit_graph_hash"] = (
            submit_graph_hash if isinstance(submit_graph_hash, str) else None
        )
        unknown_transitions: list[dict[str, Any]] = []
        if scope == "accept":
            state["baseline_turn_id"] = turn_id
            state["baseline_graph_hash"] = candidate_structural_graph_hash
            state["baseline_graph_hash_kind"] = "structural"
            for other_turn_id, other_record in state["turns"].items():
                if other_turn_id == turn_id or not isinstance(other_record, dict):
                    continue
                if other_record.get("state") != "candidate":
                    continue
                other_record["state"] = "unknown"
                other_record["unknown_at"] = other_record.get("unknown_at") or _now()
                other_record["unknown_reason"] = "superseded_by_accept"
                other_record["superseded_by_turn_id"] = turn_id
                transitioned_at = other_record["unknown_at"]
                unknown_transitions.append(
                    {
                        "session_id": session_id,
                        "turn_id": other_turn_id,
                        "from_state": "candidate",
                        "to_state": "unknown",
                        "reason": "superseded_by_accept",
                        "superseded_by_turn_id": turn_id,
                        "transitioned_at": transitioned_at,
                    }
                )

        response = {
            "ok": True,
            "action": scope,
            "session_id": session_id,
            "turn_id": turn_id,
            "baseline_turn_id": state.get("baseline_turn_id"),
            "baseline_graph_hash": state.get("baseline_graph_hash"),
            "baseline_graph_hash_kind": state.get("baseline_graph_hash_kind"),
            "accepted_state": target_state,
            "client_graph_hash": client_graph_hash,
            "submit_graph_hash": submit_graph_hash,
            "submit_structural_graph_hash": turn_record.get("submit_structural_graph_hash"),
            "submitted_client_live_canvas_token": turn_record.get(
                "submitted_client_live_canvas_token"
            ),
            "candidate_graph_hash": turn_record.get("candidate_graph_hash"),
            "candidate_structural_graph_hash": turn_record.get("candidate_structural_graph_hash"),
            "unknown_transitions": unknown_transitions,
            "idempotency_key": idempotency_key,
        }
        if key is not None and response_writer is not None:
            response_path = response_writer(response)
            state["idempotency_records"][key] = {
                "request_hash": request_digest,
                "response_hash": payload_hash(response),
                "response_path": str(response_path),
                "created_at": _now(),
                "operation": scope,
                "turn_id": turn_id,
            }
        write_state_atomic(session_dir, state)
        return response


def accept_turn(
    *,
    session_root: Path,
    session_id: str,
    turn_id: str,
    client_graph_hash: str | None,
    request_payload: Any,
    idempotency_key: str | None = None,
    response_writer: Callable[[dict[str, Any]], Path] | None = None,
) -> dict[str, Any] | FailureEnvelope:
    return _mutate_turn_state(
        session_root=session_root,
        session_id=session_id,
        turn_id=turn_id,
        scope="accept",
        client_graph_hash=client_graph_hash,
        request_payload=request_payload,
        idempotency_key=idempotency_key,
        response_writer=response_writer,
    )


def reject_turn(
    *,
    session_root: Path,
    session_id: str,
    turn_id: str,
    client_graph_hash: str | None,
    request_payload: Any,
    idempotency_key: str | None = None,
    response_writer: Callable[[dict[str, Any]], Path] | None = None,
) -> dict[str, Any] | FailureEnvelope:
    return _mutate_turn_state(
        session_root=session_root,
        session_id=session_id,
        turn_id=turn_id,
        scope="reject",
        client_graph_hash=client_graph_hash,
        request_payload=request_payload,
        idempotency_key=idempotency_key,
        response_writer=response_writer,
    )


__all__ = [
    "IdempotencyConflict",
    "IdempotencyReplay",
    "SessionStateLock",
    "TurnAllocation",
    "accept_turn",
    "allocate_turn",
    "canonical_json_bytes",
    "default_state",
    "payload_hash",
    "read_state",
    "record_idempotent_response",
    "reject_turn",
    "session_dir_for",
    "turn_dir_for",
    "write_state_atomic",
]
