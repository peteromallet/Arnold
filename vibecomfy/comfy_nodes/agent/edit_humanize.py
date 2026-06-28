# Generated from edit.py. Keep behavior changes in the installed source body.
# Contents: Human-readable edit messages and operation details.

SOURCE = r'''
def _field_change_is_noop(
    change: FieldChange,
    *,
    lint_dropped_op_ids: frozenset[tuple[str, str]] | None = None,
) -> bool:
    """Return True when *change* is a no-op.

    By default a change is a no-op when the old value is present and
    matches the new value.  When ``lint_dropped_op_ids`` is provided,
    any field change whose ``(uid, field_path)`` appears in that set is
    ALSO classified as a no-op — lint-owned classification wins.
    """
    if lint_dropped_op_ids is not None:
        key = (change.uid, change.field_path)
        if key in lint_dropped_op_ids:
            return True
    return change.old is not _ABSENT_FIELD_OLD and change.old == change.new


def _real_field_changes(
    changes: tuple[FieldChange, ...],
    *,
    lint_dropped_op_ids: frozenset[tuple[str, str]] | None = None,
) -> tuple[FieldChange, ...]:
    return tuple(
        change
        for change in changes
        if not _field_change_is_noop(change, lint_dropped_op_ids=lint_dropped_op_ids)
    )


def _noop_field_changes(
    changes: tuple[FieldChange, ...],
    *,
    lint_dropped_op_ids: frozenset[tuple[str, str]] | None = None,
) -> tuple[FieldChange, ...]:
    return tuple(
        change
        for change in changes
        if _field_change_is_noop(change, lint_dropped_op_ids=lint_dropped_op_ids)
    )


def _batch_candidate_graph_changed(state: AgentEditState) -> bool:
    if not isinstance(state.ui_payload, Mapping):
        return False
    if _real_field_changes(tuple(state.batch_field_changes or ())):
        return True
    return structural_graph_hash(state.ui_payload) != structural_graph_hash(state.graph)


def _landed_edit_lead(state: AgentEditState) -> str:
    count = _total_landed_edit_count(state)
    if count <= 0:
        return ""
    noun = "edit" if count == 1 else "edits"
    return f"Applied {count} {noun}."


def _display_value(value: Any, *, limit: int = 48) -> str:
    if isinstance(value, str):
        text = value
    elif value is None:
        text = "null"
    elif isinstance(value, (int, float, bool)):
        text = str(value)
    else:
        try:
            text = json.dumps(_json_safe(value), sort_keys=True)
        except (TypeError, ValueError):
            text = str(value)
    text = " ".join(text.split())
    if len(text) > limit:
        return text[: max(0, limit - 1)] + "…"
    return text


def _node_label_by_uid(*graphs: Mapping[str, Any] | None) -> dict[str, str]:
    labels: dict[str, str] = {}
    for graph in graphs:
        if not isinstance(graph, Mapping):
            continue
        for node in _iter_ui_graph_nodes(graph):
            class_type = node.get("type") or node.get("class_type")
            title = node.get("title")
            label = title if isinstance(title, str) and title.strip() else class_type
            if isinstance(label, str) and label.strip():
                for uid in _ui_node_uid_aliases(node):
                    labels[str(uid)] = label.strip()
    return labels


def _change_subject(change: FieldChange, labels: Mapping[str, str] | None = None) -> str:
    uid = str(change.uid or "node").strip() or "node"
    field = str(change.field_path or "field").strip() or "field"
    label = labels.get(uid) if labels else None
    if isinstance(label, str) and label.strip():
        return f"{label.strip()} {field}"
    if labels is not None and _looks_internal_uid(uid):
        return f"node {field}"
    return f"{uid}.{field}"


def _looks_internal_uid(uid: str) -> bool:
    return bool(re.fullmatch(r"n\d+|.*_\d+|\d+", uid.strip()))


def _link_endpoint_parts(value: Any) -> tuple[str, int | str] | None:
    """Return ``(uid, output_slot)`` for supported FieldChange link endpoint shapes.

    Accepts both ``list`` / ``tuple`` and the batch editor's mapping form because
    ``FieldChange.__post_init__`` freezes JSON-ish mappings into ``MappingProxyType``.
    """
    if (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and isinstance(value[0], (int, str))
        and isinstance(value[1], int)
    ):
        return str(value[0]), value[1]
    if isinstance(value, Mapping):
        uid = value.get("uid")
        output_slot = value.get("output_slot")
        if isinstance(uid, (int, str)) and isinstance(output_slot, (int, str)):
            return str(uid), output_slot
    return None


def _is_link_endpoint(value: Any) -> bool:
    return _link_endpoint_parts(value) is not None


def _resolve_output_slot_name(graph: Mapping[str, Any], uid: str, slot_index: int | str) -> str | None:
    """Return the human-readable output-slot name for *uid* / *slot_index*, or None."""
    if isinstance(slot_index, str):
        return slot_index
    for node in _iter_ui_graph_nodes(graph):
        if uid not in _ui_node_uid_aliases(node):
            continue
        outputs = node.get("outputs")
        if isinstance(outputs, list) and 0 <= slot_index < len(outputs):
            entry = outputs[slot_index]
            if isinstance(entry, Mapping):
                name = entry.get("name")
                if isinstance(name, str) and name.strip():
                    return name.strip()
        break
    return None


def _resolve_endpoint_label(
    endpoint: Any,
    node_labels: Mapping[str, str],
    graph: Mapping[str, Any],
    *fallback_graphs: Mapping[str, Any] | None,
) -> str:
    """Resolve a link endpoint ``[uid, slot]`` to a label like ``'VAE Decode IMAGE'``."""
    parts = _link_endpoint_parts(endpoint)
    if parts is None:
        return "unknown source"
    uid, slot = parts
    node_label = node_labels.get(uid)
    slot_name = _resolve_output_slot_name(graph, uid, slot)
    if slot_name is None:
        for fallback_graph in fallback_graphs:
            if isinstance(fallback_graph, Mapping):
                slot_name = _resolve_output_slot_name(fallback_graph, uid, slot)
                if slot_name is not None:
                    break
    if node_label and slot_name:
        return f"{node_label} {slot_name}"
    if node_label:
        return node_label
    if slot_name:
        return slot_name
    return "unknown source"


def _ui_node_by_uid(graph: Mapping[str, Any] | None) -> dict[str, Mapping[str, Any]]:
    if not isinstance(graph, Mapping):
        return {}
    result: dict[str, Mapping[str, Any]] = {}
    for node in _iter_ui_graph_nodes(graph):
        uid = _ui_node_uid(node)
        if uid:
            result[str(uid)] = node
    return result


def _node_class_label(node: Mapping[str, Any]) -> str:
    class_type = node.get("type") or node.get("class_type")
    if isinstance(class_type, str) and class_type.strip():
        return class_type.strip()
    title = node.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return "node"


def _ui_display_widget_value_for_field(node: Mapping[str, Any], field: str) -> Any:
    widgets = node.get("widgets")
    widgets_values = node.get("widgets_values")
    if isinstance(widgets, list) and isinstance(widgets_values, list):
        for index, widget in enumerate(widgets):
            if (
                isinstance(widget, Mapping)
                and widget.get("name") == field
                and index < len(widgets_values)
            ):
                return widgets_values[index]
    return _ui_widget_value_for_field(node, field)


def _node_key_values(node: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for field in ("scale_by", "scale", "upscale_method", "filename_prefix", "seed", "steps", "denoise"):
        value = _ui_display_widget_value_for_field(node, field)
        if value is _MISSING_FIELD_CHANGE_OLD:
            continue
        if field in {"scale_by", "scale"} and isinstance(value, (int, float)) and 0 < float(value) <= 1:
            values.append(f"{round(float(value) * 100):g}%")
        elif field == "filename_prefix":
            values.append(str(value))
        else:
            values.append(_display_value(value, limit=28))
    return values[:3]


def _node_phrase(node: Mapping[str, Any]) -> str:
    label = _node_class_label(node)
    values = _node_key_values(node)
    if values:
        return f"{label} ({', '.join(values)})"
    return label


def _article_for(text: str) -> str:
    first = text[:1].lower()
    return "an" if first in {"a", "e", "i", "o", "u"} else "a"


def _first_link_source_label(
    node: Mapping[str, Any],
    graph: Mapping[str, Any] | None,
    labels: Mapping[str, str],
) -> str | None:
    if not isinstance(graph, Mapping):
        return None
    inputs = node.get("inputs")
    links = graph.get("links")
    if not isinstance(inputs, list) or not isinstance(links, list):
        return None
    link_id = None
    for input_slot in inputs:
        if isinstance(input_slot, Mapping) and isinstance(input_slot.get("link"), (int, float)):
            link_id = int(input_slot["link"])
            break
    if link_id is None:
        return None
    by_id: dict[int, Any] = {}
    for link in links:
        if isinstance(link, Mapping) and isinstance(link.get("id"), (int, float)):
            by_id[int(link["id"])] = link
        elif isinstance(link, (list, tuple)) and link and isinstance(link[0], (int, float)):
            by_id[int(link[0])] = link
    link = by_id.get(link_id)
    if isinstance(link, Mapping):
        source_id = link.get("origin_id")
        source_slot = link.get("origin_slot", 0)
    elif isinstance(link, (list, tuple)) and len(link) >= 3:
        source_id = link[1]
        source_slot = link[2]
    else:
        return None
    source_uid = None
    for candidate in _iter_ui_graph_nodes(graph):
        if candidate.get("id") == source_id:
            source_uid = _ui_node_uid(candidate)
            break
    if not source_uid:
        return None
    return _resolve_endpoint_label({"uid": source_uid, "output_slot": source_slot}, labels, graph)


def _structural_change_phrases(state: AgentEditState, labels: Mapping[str, str]) -> list[str]:
    before_by_uid = _ui_node_by_uid(state.graph)
    after_by_uid = _ui_node_by_uid(state.ui_payload)
    if not after_by_uid:
        return []
    added = [after_by_uid[uid] for uid in sorted(set(after_by_uid) - set(before_by_uid))]
    removed = [before_by_uid[uid] for uid in sorted(set(before_by_uid) - set(after_by_uid))]
    phrases: list[str] = []
    if added:
        parts: list[str] = []
        for node in added[:8]:
            node_text = _node_phrase(node)
            source = _first_link_source_label(node, state.ui_payload, labels)
            if source:
                node_text = f"{node_text} fed by {source}"
            parts.append(node_text)
        text = _join_human_list(parts)
        remaining = len(added) - len(parts)
        if remaining > 0:
            noun = "other node" if remaining == 1 else "other nodes"
            text = f"{text}, plus {remaining} {noun}"
        article = _article_for(parts[0]) if len(parts) == 1 else ""
        phrases.append(f"added {article + ' ' if article else ''}{text}")
    if removed:
        parts = [_node_phrase(node) for node in removed[:3]]
        phrases.append(f"removed {_join_human_list(parts)}")
    return phrases


def _join_human_list(parts: list[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return f"{', '.join(parts[:-1])}, and {parts[-1]}"


def _human_change_phrase(
    change: FieldChange,
    labels: Mapping[str, str] | None = None,
    *,
    graph: Mapping[str, Any] | None = None,
    old_graph: Mapping[str, Any] | None = None,
    new_graph: Mapping[str, Any] | None = None,
) -> str:
    subject = _change_subject(change, labels)
    if graph is not None and labels is not None:
        old_endpoint_graph = old_graph if isinstance(old_graph, Mapping) else graph
        new_endpoint_graph = new_graph if isinstance(new_graph, Mapping) else graph
        old_link = _is_link_endpoint(change.old)
        new_link = _is_link_endpoint(change.new)
        if old_link and new_link:
            old_label = _resolve_endpoint_label(change.old, labels, old_endpoint_graph, graph, new_graph)
            new_label = _resolve_endpoint_label(change.new, labels, new_endpoint_graph, graph, old_graph)
            return f"rewired {subject} to come from {new_label} instead of {old_label}"
        if new_link and not old_link:
            new_label = _resolve_endpoint_label(change.new, labels, new_endpoint_graph, graph, old_graph)
            return f"connected {subject} to {new_label}"
        if old_link and not new_link:
            old_label = _resolve_endpoint_label(change.old, labels, old_endpoint_graph, graph, new_graph)
            return f"disconnected {subject} from {old_label}"
    if change.old is None or change.old is _ABSENT_FIELD_OLD:
        return f"set {subject} to {_display_value(change.new)}"
    return (
        f"updated {subject} from "
        f"{_display_value(change.old)} to {_display_value(change.new)}"
    )


def _sentence_case(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    return stripped[0].upper() + stripped[1:]


def _humanized_edit_message(state: AgentEditState) -> str:
    changes = _real_field_changes(tuple(state.batch_field_changes or ()))
    labels = _node_label_by_uid(state.graph, state.ui_payload)
    structural_phrases = _structural_change_phrases(state, labels)
    if structural_phrases:
        return _sentence_case(
            ensure_sentence_message(
                _join_human_list(structural_phrases),
                fallback="Updated the workflow structure.",
            )
        )
    if not changes:
        return ensure_sentence_message(
            "",
            fallback="The candidate is ready to review.",
        )
    if len(changes) == 1:
        return _sentence_case(
            ensure_sentence_message(
                _human_change_phrase(
                    changes[0],
                    labels,
                    graph=state.graph,
                    old_graph=state.graph,
                    new_graph=state.ui_payload,
                ),
                fallback="Updated the workflow.",
            )
        )
    phrases = [
        _human_change_phrase(
            change,
            labels,
            graph=state.graph,
            old_graph=state.graph,
            new_graph=state.ui_payload,
        )
        for change in changes[:3]
    ]
    if len(changes) == 2:
        text = f"{phrases[0]} and {phrases[1]}"
    else:
        text = f"{phrases[0]}, {phrases[1]}, and {phrases[2]}"
        remaining = len(changes) - 3
        if remaining > 0:
            noun = "other field" if remaining == 1 else "other fields"
            text = f"{text}, plus {remaining} {noun}"
    return _sentence_case(ensure_sentence_message(text, fallback=f"Updated {len(changes)} workflow fields."))


def _terminal_answer_message(state: AgentEditState) -> str | None:
    if state.lint_noop_messages or state.batch_noop_field_changes or state.batch_field_changes:
        return None
    if state.batch_exit_mode != _BATCH_EXIT_NOOP:
        return None

    for turn in reversed(state.batch_turns or []):
        if not isinstance(turn, Mapping):
            continue
        statements = turn.get("statements")
        has_terminal_done = False
        if isinstance(statements, list):
            has_terminal_done = any(
                isinstance(stmt, Mapping) and stmt.get("op_kind") == "done"
                for stmt in statements
            )
        batch = turn.get("batch")
        if not has_terminal_done and isinstance(batch, str):
            has_terminal_done = batch.strip().startswith("done(")
        if not has_terminal_done:
            continue
        message = turn.get("message")
        if isinstance(message, str) and message.strip():
            return ensure_sentence_message(message.strip(), fallback="No graph changes were needed.")
    return None


def _humanized_noop_message(state: AgentEditState) -> str:
    revision_message = _revision_rejected_candidate_message(state)
    if revision_message:
        return revision_message

    # Prefer lint normalization messages when available (they carry
    # class/title/field/slot context and avoid raw gate text or uids).
    if state.lint_noop_messages:
        msgs = state.lint_noop_messages
        if len(msgs) == 1:
            return _sentence_case(ensure_sentence_message(msgs[0], fallback="No change needed."))
        return "The requested changes are already in place; no updates needed."

    changes = tuple(state.batch_noop_field_changes or ())
    labels = _node_label_by_uid(state.graph, state.ui_payload)
    if len(changes) == 1:
        change = changes[0]
        return _sentence_case(
            ensure_sentence_message(
                f"{_change_subject(change, labels)} is already {_display_value(change.new)}; no change needed",
                fallback="No change needed.",
            )
        )
    if len(changes) > 1:
        return "The requested fields already match the current graph; no change needed."
    answer = _terminal_answer_message(state)
    if answer:
        return answer
    summary = (state.batch_done_summary or "").strip()
    gate_jargon = bool(re.search(r"\bGate\s+[AB]\b|identity verified|No operations were applied", summary, re.I))
    if summary and not gate_jargon:
        return ensure_sentence_message(summary, fallback="No graph changes were needed.")
    if gate_jargon:
        return "Nothing needed changing; the workflow already matches that."
    return "No graph changes were needed."


def _revision_rejected_candidate_message(state: AgentEditState) -> str:
    evidence = state.revision_evidence
    scoped = evidence.scoped_diff if evidence is not None else None
    if evidence is None or scoped is None or evidence.candidate_eligible is True:
        return ""
    blockers = list(scoped.eligibility_blockers or ())
    mismatch_reasons = [
        str(item.get("reason") or "").strip()
        for item in evidence.topology.socket_type_mismatches
        if isinstance(item, Mapping) and str(item.get("reason") or "").strip()
    ]
    if "candidate_topology_blockers" in blockers and mismatch_reasons:
        return ensure_sentence_message(
            "I left the graph unchanged because the candidate did not repair existing socket type mismatches first: "
            + "; ".join(mismatch_reasons[:3]),
            fallback="I left the graph unchanged because the candidate would not produce a valid workflow.",
        )
    if blockers:
        return ensure_sentence_message(
            "I left the graph unchanged because the candidate was not safe to apply: "
            + ", ".join(blockers),
            fallback="I left the graph unchanged because the candidate was not safe to apply.",
        )
    return "I left the graph unchanged because the candidate was not safe to apply."


def _revision_candidate_retry_hint(state: AgentEditState) -> str:
    message = _revision_rejected_candidate_message(state)
    evidence = state.revision_evidence
    mismatch_reasons = []
    if evidence is not None:
        mismatch_reasons = [
            str(item.get("reason") or "").strip()
            for item in evidence.topology.socket_type_mismatches
            if isinstance(item, Mapping) and str(item.get("reason") or "").strip()
        ]
    details = "; ".join(mismatch_reasons[:3])
    if details:
        return (
            "the candidate still leaves invalid graph wiring. Repair these existing "
            f"socket mismatches first: {details}. Then add the save/export path. "
            "Prefer installed local nodes from search results such as CreateVideo -> SaveVideo "
            "or SaveAnimatedWEBP when their signatures are available; use vibecomfy.exec only "
            "for explicit code/Python requests or when no installed node path exists."
        )
    return (
        (message or "the candidate was not safe to apply")
        + " Fix the reported eligibility blockers, then call done() again."
    )


def _operation_detail_payload(changes: tuple[FieldChange, ...]) -> list[dict[str, Any]]:
    return [
        {
            **change.to_dict(),
            "summary": (
                f"Set {_change_subject(change)} to {_display_value(change.new)}."
                if change.old is None or change.old is _ABSENT_FIELD_OLD
                else (
                    f"Changed {_change_subject(change)} from "
                    f"{_display_value(change.old)} to {_display_value(change.new)}."
                )
            ),
        }
        for change in _real_field_changes(changes)
    ]


def _change_details_payload(state: AgentEditState, context: TurnContext) -> dict[str, Any]:
    gate_snapshot = context.gate_snapshot()
    gate_a = gate_snapshot.get("edit_scope_ok") or gate_snapshot.get("python_load_ok")
    gate_b = gate_snapshot.get("isomorphic_ok") or gate_snapshot.get("ui_fidelity_ok")
    operations = _operation_detail_payload(tuple(state.batch_field_changes or ()))
    return {
        "landed_operation_count": _total_landed_edit_count(state),
        "done_summary": state.batch_done_summary or "",
        "final_summary": state.batch_final_summary or "",
        "gate_a": _json_safe(gate_a),
        "gate_b": _json_safe(gate_b),
        "operations": operations,
        "batch_turns": _json_safe(state.batch_turns),
    }


def _batch_warning_sentence(
    state: AgentEditState,
    *,
    failure: FailureEnvelope | None = None,
    outcome: TurnOutcome | None = None,
) -> str:
    if failure is not None:
        if failure.kind is FailureKind.STALE_STATE_MISMATCH:
            return ensure_sentence_message(
                failure.user_facing_message,
                fallback="The canvas changed since the current baseline. Rebaseline and resubmit from the current canvas.",
            )
        if state.batch_exit_mode == _BATCH_EXIT_BUDGET:
            return ensure_sentence_message(
                "I ran out of turn budget before completing the remaining changes",
                fallback=state.batch_final_summary or failure.message,
            )
        return ensure_sentence_message(
            failure.user_facing_message,
            fallback=failure.message or "The graph is unchanged.",
        )
    if outcome is not None and outcome.kind == "edit+clarify":
        return ensure_sentence_message(
            outcome.question,
            fallback=state.user_message or "I still need clarification before continuing.",
        )
    return ""


def _synthesize_batch_repl_message(
    state: AgentEditState,
    *,
    outcome: TurnOutcome | None = None,
    failure: FailureEnvelope | None = None,
) -> str:
    lead = _landed_edit_lead(state)
    if failure is not None:
        warning = _batch_warning_sentence(state, failure=failure)
        if lead:
            return f"{lead} {warning}".strip()
        return warning
    if outcome is None:
        return ensure_sentence_message(state.user_message, fallback="The agent edit turn completed.")
    if outcome.kind == "edit":
        return _humanized_edit_message(state)
    if outcome.kind == "edit+clarify":
        warning = _batch_warning_sentence(state, outcome=outcome)
        if lead:
            return f"{lead} {warning}".strip()
        return warning
    if outcome.kind == "clarify":
        return ensure_sentence_message(
            outcome.question,
            fallback=state.user_message or "I need clarification before continuing.",
        )
    if outcome.kind == "budget":
        return ensure_sentence_message(
            "I ran out of turn budget before completing the requested changes",
            fallback=state.batch_final_summary or state.user_message,
        )
    if outcome.kind == "noop" and _resolver_candidates_from_batch_turns(state):
        return ensure_sentence_message(
            state.user_message,
            fallback=(
                "I found custom-node evidence, but could not apply a grounded "
                "workflow pattern to the current graph."
            ),
        )
    if outcome.kind == "noop":
        return _humanized_noop_message(state)
    return ensure_sentence_message(state.user_message, fallback="The agent edit turn completed.")


'''
