# Generated from edit.py. Keep behavior changes in the installed source body.
# Contents: Revision evidence scoping, readiness extraction, and artifact writing.

SOURCE = r'''
def _seed_focus_types_for_authoring(state: AgentEditState) -> set[str]:
    task = _effective_implementation_task(state).lower()
    if not _empty_graph_authoring_request(state):
        return set()
    if (
        "sd1.5" in task
        or "sd 1.5" in task
        or "sd15" in task
        or "stable diffusion" in task
        or "text-to-image" in task
        or "text to image" in task
    ):
        return set(_TEXT_TO_IMAGE_SEED_TYPES)
    return set()


def _focus_types_from_research_brief(brief: Mapping[str, Any] | None) -> set[str]:
    """Return exact authoring focus types from structured classifier fields only.

    Search directions are retrieval hints, not class-name evidence. Pulling
    capitalized prose tokens from them creates bogus local schema misses such as
    ``Adapting``, ``ComfyUI``, or ``SDXL`` in the first implement prompt.
    Workflow/adapt routes get exact class names from selected workflow evidence
    instead, so this helper intentionally avoids free-text extraction.
    """
    if not brief:
        return set()
    candidates: set[str] = set()
    for key in ("focus_types", "class_types", "node_types"):
        values = brief.get(key)
        if not isinstance(values, (list, tuple)):
            continue
        for value in values:
            if not isinstance(value, str):
                continue
            cleaned = value.strip(".,;:\"'")
            if cleaned:
                candidates.add(cleaned)
    return candidates


def _focus_types_from_research_sources(sources: Any) -> set[str]:
    """Seed local schema lookup from high-confidence workflow research hits."""
    if not isinstance(sources, (list, tuple)):
        return set()
    candidates: set[str] = set()
    for index, source in enumerate(sources[:8]):
        if not isinstance(source, Mapping):
            continue
        strong = source.get("strong_relevance_match") is True
        source_kind = str(source.get("source") or "")
        if not strong and source_kind not in {"ready_template", "source_workflow"}:
            continue
        if index >= 3 and not strong:
            continue
        class_type = source.get("class_type")
        if isinstance(class_type, str) and class_type and class_type.isascii():
            candidates.add(class_type)
        node_types = source.get("node_types")
        if isinstance(node_types, (list, tuple)):
            for node_type in node_types[:80]:
                if not isinstance(node_type, str):
                    continue
                text = node_type.strip()
                if text and text.isascii() and len(text) <= 80:
                    candidates.add(text)
    return candidates


def _can_attempt_local_additive_revise(state: AgentEditState) -> bool:
    evidence = state.revision_evidence
    if evidence is None:
        return False
    topology = evidence.topology
    readiness = evidence.readiness
    if _empty_graph_authoring_request(state):
        if topology.dangling_links or topology.absent_endpoint_nodes:
            return False
        if readiness.no_gpu_detected or readiness.validation_errors or readiness.readiness_blockers:
            return False
        return True
    if not _runtime_code_additive_request(state):
        return False
    if topology.missing_graph or topology.dangling_links or topology.absent_endpoint_nodes:
        return False
    if readiness.no_gpu_detected or readiness.validation_errors or readiness.readiness_blockers:
        return False
    return bool(
        topology.unknown_class_types
        or topology.missing_required_inputs
        or readiness.missing_models
        or readiness.missing_node_packs
    )


def _can_attempt_direct_existing_parameter_tweak(state: AgentEditState) -> bool:
    """Allow concrete local parameter edits despite unrelated readiness blockers."""
    evidence = state.revision_evidence
    if evidence is None:
        return False
    if not _task_looks_like_parameter_tweak(state):
        return False
    if not _existing_parameter_tweak_targets(state, max_targets=1):
        return False
    topology = evidence.topology
    readiness = evidence.readiness
    if topology.missing_graph or topology.dangling_links or topology.absent_endpoint_nodes:
        return False
    if readiness.no_gpu_detected or readiness.validation_errors or readiness.readiness_blockers:
        return False
    return bool(
        topology.unknown_class_types
        or topology.missing_required_inputs
        or readiness.missing_models
        or readiness.missing_node_packs
        or not evidence.safe_candidate_possible
    )


def _stable_blocker_key(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, default=str)
    except TypeError:
        return str(value)


def _subtract_existing_blockers(
    current: tuple[Any, ...],
    existing: tuple[Any, ...],
) -> tuple[Any, ...]:
    existing_keys = {_stable_blocker_key(item) for item in existing}
    return tuple(item for item in current if _stable_blocker_key(item) not in existing_keys)


def _localized_additive_scoped_evidence(
    state: AgentEditState,
    *,
    candidate_topology: TopologyFindings,
    candidate_readiness: ReadinessReport,
) -> tuple[
    TopologyFindings | None,
    ReadinessReport | None,
    TopologyFindings | None,
    ReadinessReport | None,
]:
    scoped_local_edit = (
        _can_attempt_local_additive_revise(state)
        or _can_attempt_direct_existing_parameter_tweak(state)
    )
    if not scoped_local_edit or state.revision_evidence is None:
        return None, None, None, None
    topology = state.revision_evidence.topology
    readiness = state.revision_evidence.readiness
    empty_graph_authoring = _empty_graph_authoring_request(state)
    filtered_original_topology = TopologyFindings(
        missing_graph=False if empty_graph_authoring else topology.missing_graph,
        dangling_links=topology.dangling_links,
        absent_endpoint_nodes=topology.absent_endpoint_nodes,
        socket_type_mismatches=topology.socket_type_mismatches,
        schema_available=topology.schema_available,
        summary=(
            "pre-existing empty-graph authoring baseline ignored for new workflow"
            if empty_graph_authoring
            else "pre-existing unknown/custom-node blockers ignored for localized "
            "runtime code-node addition"
        ),
    )
    filtered_original_readiness = ReadinessReport(
        validation_errors=readiness.validation_errors,
        no_gpu_detected=readiness.no_gpu_detected,
        readiness_blockers=readiness.readiness_blockers,
        object_info_available=readiness.object_info_available,
        summary=(
            "pre-existing missing model/node-pack blockers ignored for localized "
            "runtime code-node addition"
        ),
    )
    filtered_candidate_topology = TopologyFindings(
        missing_graph=candidate_topology.missing_graph,
        dangling_links=candidate_topology.dangling_links,
        absent_endpoint_nodes=candidate_topology.absent_endpoint_nodes,
        socket_type_mismatches=_subtract_existing_blockers(
            candidate_topology.socket_type_mismatches,
            topology.socket_type_mismatches,
        ),
        unknown_class_types=_subtract_existing_blockers(
            candidate_topology.unknown_class_types,
            topology.unknown_class_types,
        ),
        missing_required_inputs=_subtract_existing_blockers(
            candidate_topology.missing_required_inputs,
            topology.missing_required_inputs,
        ),
        schema_available=candidate_topology.schema_available,
        summary=(
            "pre-existing unknown/custom-node blockers subtracted for localized "
            "runtime code-node addition"
        ),
    )
    filtered_candidate_readiness = ReadinessReport(
        missing_models=_subtract_existing_blockers(
            candidate_readiness.missing_models,
            readiness.missing_models,
        ),
        missing_node_packs=_subtract_existing_blockers(
            candidate_readiness.missing_node_packs,
            readiness.missing_node_packs,
        ),
        validation_errors=candidate_readiness.validation_errors,
        no_gpu_detected=candidate_readiness.no_gpu_detected,
        readiness_blockers=candidate_readiness.readiness_blockers,
        object_info_available=candidate_readiness.object_info_available,
        summary=(
            "pre-existing missing model/node-pack blockers subtracted for localized "
            "runtime code-node addition"
        ),
    )
    return (
        filtered_original_topology,
        filtered_original_readiness,
        filtered_candidate_topology,
        filtered_candidate_readiness,
    )


def _session_reference_map_for_evidence(
    conversation_messages: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    if not conversation_messages:
        return {}
    compact: dict[str, Any] = {"recent_message_count": len(conversation_messages)}
    latest = conversation_messages[-1] if conversation_messages else None
    if isinstance(latest, Mapping):
        outcome = latest.get("outcome")
        if isinstance(outcome, Mapping) and isinstance(outcome.get("kind"), str):
            compact["latest_outcome_kind"] = outcome["kind"]
        text = latest.get("text")
        if isinstance(text, str) and text.strip():
            compact["latest_text_preview"] = text.strip()[:160]
    clarification = _latest_clarification_context(conversation_messages)
    if clarification is not None:
        compact["pending_clarification"] = {
            "prior_request": clarification["prior_request"][:240],
            "question": clarification["question"][:240],
        }
    latest_candidate = next(
        (
            msg
            for msg in reversed(conversation_messages)
            if isinstance(msg, Mapping)
            and isinstance(msg.get("text"), str)
            and "Latest candidate reference" in msg["text"]
        ),
        None,
    )
    if isinstance(latest_candidate, Mapping):
        compact["latest_candidate_reference"] = str(latest_candidate.get("text", ""))[:400]
    return compact


def _runtime_execution_requested(task: str | None, payload: Mapping[str, Any]) -> bool:
    text = (task or "").lower()
    if any(word in text for word in ("run", "queue", "execute", "render", "generate")):
        return True
    requested = payload.get("execution_requested") or payload.get("run_requested")
    if requested is True:
        return True
    runtime = payload.get("runtime")
    return isinstance(runtime, Mapping) and runtime.get("execution_requested") is True


def _extract_ready_metadata(payload: Mapping[str, Any], graph: Mapping[str, Any] | None) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in ("ready_metadata", "ready_template_metadata", "metadata", "requirements"):
        value = payload.get(key)
        if isinstance(value, Mapping):
            metadata[key] = dict(value)
    if isinstance(graph, Mapping):
        extra = graph.get("extra")
        if isinstance(extra, Mapping):
            vibecomfy = extra.get("vibecomfy")
            if isinstance(vibecomfy, Mapping):
                metadata["vibecomfy"] = dict(vibecomfy)
            for key in ("ready_metadata", "requirements", "diagnostics"):
                value = extra.get(key)
                if isinstance(value, Mapping):
                    metadata[key] = dict(value)
                elif isinstance(value, list):
                    metadata[key] = list(value)
    return metadata


def _extract_readiness_diagnostics(payload: Mapping[str, Any], graph: Mapping[str, Any] | None) -> tuple[dict[str, Any], ...]:
    diagnostics: list[dict[str, Any]] = []
    for source in (payload, graph if isinstance(graph, Mapping) else {}):
        raw = source.get("diagnostics") if isinstance(source, Mapping) else None
        if isinstance(raw, list):
            diagnostics.extend(dict(item) for item in raw if isinstance(item, Mapping))
    if isinstance(graph, Mapping):
        extra = graph.get("extra")
        if isinstance(extra, Mapping) and isinstance(extra.get("diagnostics"), list):
            diagnostics.extend(dict(item) for item in extra["diagnostics"] if isinstance(item, Mapping))
    runtime = payload.get("runtime")
    if isinstance(runtime, Mapping) and runtime.get("no_gpu_detected") is True:
        diagnostics.append(
            {
                "code": "no_gpu_detected",
                "severity": "error",
                "message": "No GPU is available for runtime execution.",
            }
        )
    return tuple(diagnostics)


def _request_no_gpu_detected(payload: Mapping[str, Any]) -> bool:
    if payload.get("no_gpu_detected") is True:
        return True
    runtime = payload.get("runtime")
    return isinstance(runtime, Mapping) and runtime.get("no_gpu_detected") is True


def _revision_target_node_ids(
    state: AgentEditState,
    *,
    route: str | None,
) -> tuple[str, ...]:
    payload = state.request_payload if isinstance(state.request_payload, Mapping) else {}
    values: list[Any] = []
    for key in ("target_node_ids", "target_nodes", "node_ids"):
        raw = payload.get(key)
        if isinstance(raw, list):
            values.extend(raw)
        elif raw is not None:
            values.append(raw)
    classification = payload.get("executor_classification")
    if isinstance(classification, Mapping):
        raw = classification.get("target_node_ids") or classification.get("target_nodes")
        if isinstance(raw, list):
            values.extend(raw)
        elif raw is not None:
            values.append(raw)
    task = state.task or ""
    values.extend(re.findall(r"(?:node|#)\s*(\d+)", task, flags=re.IGNORECASE))
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return tuple(result)


def _revision_evidence_artifact_payload(
    state: AgentEditState,
    *,
    route: str | None,
    conversation_messages: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    classification = (
        state.request_payload.get("executor_classification")
        if isinstance(state.request_payload, Mapping)
        else None
    )
    return {
        "revision_evidence": (
            state.revision_evidence.to_dict()
            if state.revision_evidence is not None
            else {}
        ),
        "classification": _json_safe(classification)
        if isinstance(classification, Mapping)
        else {"route": _canonical_agent_edit_route(state.route or route)},
        "session_reference_map": _session_reference_map_for_evidence(conversation_messages),
    }


def _write_revision_evidence_artifact(
    state: AgentEditState,
    *,
    route: str | None,
    conversation_messages: list[dict[str, Any]] | None,
) -> ArtifactRef:
    payload = _revision_evidence_artifact_payload(
        state,
        route=route,
        conversation_messages=conversation_messages,
    )
    state.revision_evidence_payload = payload
    state.artifacts = {
        **(state.artifacts or {}),
        "revision_evidence": str(state.revision_evidence_path),
    }
    return write_json_artifact(state.revision_evidence_path, payload)


'''
