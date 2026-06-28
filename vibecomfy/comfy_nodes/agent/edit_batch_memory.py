# Generated from edit.py. Keep behavior changes in the installed source body.
# Contents: Batch prompt context, research memory, and clarify feedback.

SOURCE = r'''
def _normalize_test_client_response(response: dict[str, str]) -> AgentTurnResult:
    python = response.get("python")
    message = response.get("message")
    if not isinstance(python, str):
        raise ValueError("Agent JSON must include string key `python`.")
    if not isinstance(message, str):
        raise ValueError("Agent JSON must include string key `message`.")
    return AgentTurnResult(
        python=python,
        message=message,
        route="test_client",
        audit_metadata={"provider": "test_client"},
    )


def _normalize_test_client_batch_response(response: dict[str, str]) -> BatchTurnResult:
    batch = response.get("batch")
    message = response.get("message")
    if not isinstance(batch, str):
        raise ValueError("Batch agent response must include string key `batch`.")
    if not isinstance(message, str):
        raise ValueError("Batch agent response must include string key `message`.")
    return BatchTurnResult(
        batch=batch,
        message=message,
        route="test_client",
        audit_metadata={"provider": "test_client", "response_contract": "batch_repl"},
    )


def _render_batch_diff(before: str, after: str, *, max_chars: int = 2000) -> str:
    diff = "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile="before.py",
            tofile="after.py",
            n=2,
        )
    ).strip()
    if len(diff) <= max_chars:
        return diff
    return diff[: max(0, max_chars - 15)].rstrip() + "\n... [truncated]"


def _format_statement_source(source: str, *, max_chars: int = 72) -> str:
    """Truncate a statement source string for inline display."""
    if len(source) <= max_chars:
        return source
    return source[: max(0, max_chars - 3)] + "..."


def _iter_ui_nodes(ui_payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return root and nested UI node dictionaries from a LiteGraph payload."""
    found: list[Mapping[str, Any]] = []

    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            nodes = value.get("nodes")
            if isinstance(nodes, list):
                for node in nodes:
                    if isinstance(node, Mapping):
                        found.append(node)
                        visit(node)
            for key in ("graphs", "subgraphs"):
                nested = value.get(key)
                if isinstance(nested, list):
                    for item in nested:
                        visit(item)
                elif isinstance(nested, Mapping):
                    for item in nested.values():
                        visit(item)

    visit(ui_payload)
    return found


def _present_class_types(session: Any) -> list[str]:
    """Enumerate class types currently present in an EditSession working graph."""
    working_ui = getattr(session, "working_ui", None)
    if not isinstance(working_ui, Mapping):
        return []
    types: set[str] = set()
    for node in _iter_ui_nodes(working_ui):
        class_type = node.get("type") or node.get("class_type")
        if isinstance(class_type, str) and class_type:
            types.add(class_type)
    return sorted(types)


def _format_node_variable_index(session: Any) -> str:
    """Return ``var = ClassType`` lines for the current EditSession graph."""
    working_ui = getattr(session, "working_ui", None)
    name_by_uid = getattr(session, "name_by_uid", None)
    if not isinstance(working_ui, Mapping) or not isinstance(name_by_uid, Mapping):
        return ""
    rows: list[tuple[str, str, str]] = []
    for node in _iter_ui_nodes(working_ui):
        uid = _ui_node_uid(node)
        if not uid:
            continue
        name = name_by_uid.get(uid)
        class_type = node.get("type") or node.get("class_type")
        if isinstance(name, str) and name and isinstance(class_type, str) and class_type:
            rows.append((name, uid, class_type))
    rows.sort(key=lambda item: (item[0], item[1]))
    return "\n".join(f"{name} = {class_type}" for name, _uid, class_type in rows)


def _format_available_node_names(
    rows: Any,
    *,
    max_line_chars: int = 96,
    max_names: int = 80,
) -> str:
    """Format NodeSignatureRow-like objects as a bounded deterministic name list.

    Large ComfyUI installs can expose hundreds of node types. Dumping the full
    registry into the first edit prompt makes simple turns slow and brittle, and
    the batch REPL already has ``search(...)`` for exact schema lookup when a
    new type is needed.
    """
    names = sorted(
        {
            class_type
            for row in rows or []
            if isinstance((class_type := getattr(row, "class_type", None)), str)
            and class_type
        }
    )
    if not names:
        return ""
    total_count = len(names)
    if max_names > 0 and total_count > max_names:
        names = names[:max_names]
    lines: list[str] = []
    current = names[0]
    for name in names[1:]:
        candidate = f"{current}, {name}"
        if len(candidate) > max_line_chars:
            lines.append(current)
            current = name
        else:
            current = candidate
    lines.append(current)
    if total_count > len(names):
        lines.append(
            f"... [{total_count - len(names)} more node type names omitted; "
            "use search(...) for exact local schema lookup before adding an omitted type]"
        )
    return "\n".join(lines)


def _format_query_output(text: str, *, max_chars: int | None = 4000) -> str:
    """Bound read-only query output before it is included in agent feedback."""
    if max_chars is None:
        return text
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 18)].rstrip() + "\n... [truncated]"


def _batch_research_memory_summary(state: Any, *, max_items: int = 3) -> str:
    """Carry compact prior research/query evidence across batch turns.

    Packet-aware: when a statement detail includes ``precedent_packet``, a
    compact summary is built from structured option fields (source title,
    source tier, one-line pattern summary, caveat count) instead of
    reserializing the full packet or dumping ``query_output`` verbatim.
    Statements without a packet fall back to the marker-matched
    ``query_output`` path for non-research turns (e.g. ``search()``).
    """
    records: list[str] = []
    for turn in getattr(state, "batch_turns", ()) or ():
        if not isinstance(turn, Mapping):
            continue
        statements = turn.get("statements")
        if not isinstance(statements, list):
            continue
        turn_number = turn.get("turn_number")
        for statement in statements:
            if not isinstance(statement, Mapping):
                continue
            detail = statement.get("detail")
            if not isinstance(detail, Mapping):
                continue

            # ── packet-aware compact path ────────────────────────────
            precedent_packet = detail.get("precedent_packet")
            if isinstance(precedent_packet, Mapping):
                packet_record = _summarize_precedent_packet(
                    precedent_packet, turn_number
                )
                if packet_record:
                    records.append(packet_record)
                continue

            # ── legacy marker-matched query_output path ──────────────
            query_output = str(detail.get("query_output") or "").strip()
            if not query_output:
                continue
            relevant = any(
                marker in query_output
                for marker in (
                    "Concrete workflow pattern found",
                    "github_workflow_json",
                    "source_workflow_path",
                    "No node signature found",
                    "registry/schema lookup",
                    "Registry check",
                )
            ) or bool(detail.get("resolver_candidates"))
            if not relevant:
                continue
            query = str(detail.get("research_query") or detail.get("query") or "").strip()
            sources = detail.get("requested_research_sources") or detail.get("research_sources")
            source_text = f" sources={tuple(sources)!r}" if isinstance(sources, (list, tuple)) else ""
            header = f"turn {turn_number}: {query or statement.get('source') or 'query'}{source_text}"
            records.append(f"- {header}\n{_format_query_output(query_output, max_chars=1000)}")
    if not records:
        return ""
    return "\n\n".join(records[-max_items:])


def _summarize_precedent_packet(
    packet: Mapping[str, Any], turn_number: Any
) -> str | None:
    """Build a compact one-line-per-option summary from a precedent packet dict.

    Carries only source title, source tier, one-line pattern summary, and
    caveat count.  Does **not** reserialize the full packet and omits every
    forbidden public-key name (winner, best, selected, score, rank, primary,
    preferred, chosen, pick, choice, top, recommended).
    """
    options = packet.get("options")
    if not isinstance(options, (list, tuple)) or not options:
        return None

    packet_warnings = packet.get("warnings")
    packet_caveats = (
        len(packet_warnings) if isinstance(packet_warnings, (list, tuple)) else 0
    )

    lines: list[str] = [
        f"turn {turn_number}: research evidence "
        f"({len(options)} precedent option(s)):"
    ]
    for opt in options:
        if not isinstance(opt, Mapping):
            continue

        title = str(opt.get("source_class_type") or "(unknown)")

        # ── one-line pattern summary ─────────────────────────────────
        description = str(opt.get("description", "")).strip()
        if description:
            summary_line = description.split("\n")[0].strip()
            if len(summary_line) > 120:
                summary_line = summary_line[:117] + "..."
        else:
            summary_line = "(no description)"

        # ── source tier from notes ───────────────────────────────────
        notes = opt.get("notes")
        tier = ""
        option_caveats = 0
        if isinstance(notes, (list, tuple)):
            for note in notes:
                if not isinstance(note, str):
                    continue
                if note.startswith("source: "):
                    tier = note[len("source: "):]
                elif note.strip():
                    option_caveats += 1

        caveats = packet_caveats + option_caveats
        caveat_str = f" [{caveats} caveat(s)]" if caveats else ""
        tier_str = f" tier={tier}" if tier else ""

        lines.append(f"  - {title}{tier_str}: {summary_line}{caveat_str}")

    return "\n".join(lines)


def _premature_missing_custom_node_clarify_feedback(
    state: Any,
    clarify_message: str,
) -> str:
    """Reject missing-custom-node stops that skipped required registry evidence."""
    message_text = str(clarify_message or "").casefold()
    if not any(term in message_text for term in ("missing", "not installed", "install", "custom node")):
        return ""

    concrete_workflow_seen = False
    last_missing_turn = -1
    missing_classes: list[str] = []
    registry_after_missing = False
    for turn in getattr(state, "batch_turns", ()) or ():
        if not isinstance(turn, Mapping):
            continue
        raw_turn_number = turn.get("turn_number")
        turn_number = raw_turn_number if isinstance(raw_turn_number, int) else -1
        statements = turn.get("statements")
        if not isinstance(statements, list):
            continue
        for statement in statements:
            if not isinstance(statement, Mapping):
                continue
            detail = statement.get("detail")
            if not isinstance(detail, Mapping):
                continue
            query_output = str(detail.get("query_output") or "")
            if "Concrete workflow pattern found" in query_output or "github_workflow_json" in query_output:
                concrete_workflow_seen = True
            if (
                detail.get("query") == "research"
                and "registry" in tuple(detail.get("requested_research_sources") or ())
                and turn_number > last_missing_turn >= 0
            ):
                registry_after_missing = True
            if "No node signature found for exact class type(s):" in query_output:
                last_missing_turn = turn_number
                registry_after_missing = False
                for match in re.findall(r"'([^']+)'", query_output):
                    if match and match not in missing_classes:
                        missing_classes.append(match)

    if not concrete_workflow_seen or last_missing_turn < 0 or registry_after_missing:
        return ""

    class_text = ", ".join(missing_classes[:8]) if missing_classes else "the exact missing workflow classes"
    return (
        "Premature missing-custom-node clarification rejected: workflow/example evidence has named "
        f"missing exact class(es) ({class_text}), but no registry/schema research turn has verified "
        "the owning custom-node pack after that local schema miss. Next turn must run "
        "`research(\"<exact missing class names or concrete pack/family>\", sources=[\"registry\"])` "
        "using the workflow-sourced class names, then either apply with grounded schemas/provisional "
        "custom-node evidence or clarify with the registry-backed missing pack."
    )


def _premature_workflow_schema_clarify_feedback(
    state: Any,
    clarify_message: str,
) -> str:
    """Reject stops that ignore concrete workflow-derived constructor schemas."""
    message_text = str(clarify_message or "").casefold()
    if not any(term in message_text for term in ("not found", "lacks", "missing", "cannot", "without knowing")):
        return ""

    schema_classes: list[str] = []
    last_schema_turn = -1
    landed_after_schema = False
    for turn in getattr(state, "batch_turns", ()) or ():
        if not isinstance(turn, Mapping):
            continue
        raw_turn_number = turn.get("turn_number")
        turn_number = raw_turn_number if isinstance(raw_turn_number, int) else -1
        landed_count = turn.get("landed_op_count")
        if isinstance(landed_count, int) and landed_count > 0 and turn_number > last_schema_turn >= 0:
            landed_after_schema = True
        statements = turn.get("statements")
        if not isinstance(statements, list):
            continue
        for statement in statements:
            if not isinstance(statement, Mapping):
                continue
            detail = statement.get("detail")
            if not isinstance(detail, Mapping):
                continue
            query_output = str(detail.get("query_output") or "")
            matches = [
                *re.findall(r"workflow_schema\s+([A-Za-z_][A-Za-z0-9_]*)\s*:", query_output),
                *re.findall(r"def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", query_output),
            ]
            if not matches:
                continue
            last_schema_turn = max(last_schema_turn, turn_number)
            landed_after_schema = False
            for class_type in matches:
                if class_type not in schema_classes:
                    schema_classes.append(class_type)

    if not schema_classes or landed_after_schema:
        return ""
    class_text = ", ".join(schema_classes[:8])
    return (
        "Premature clarification rejected: workflow-derived constructor schemas are already available "
        f"for {class_text}. The current graph lacking those nodes is not a reason to stop; it is the "
        "reason to add the workflow-sourced provisional nodes. Next turn must land the smallest "
        "evidence-backed workflow-pattern edit using those constructors, or run a strictly necessary "
        "additional schema/registry lookup for a named class that is still actually missing."
    )


_PARAMETER_TWEAK_ACTION_TERMS = (
    "increase",
    "decrease",
    "adjust",
    "tweak",
    "change",
    "set",
    "raise",
    "lower",
    "reduce",
    "boost",
)
_PARAMETER_TWEAK_TARGET_TERMS = (
    "detail",
    "frame",
    "fps",
    "rate",
    "step",
    "strength",
    "cfg",
    "seed",
    "scale",
    "denoise",
    "resolution",
    "width",
    "height",
    "duration",
    "quality",
    "prompt",
    "format",
    "codec",
)


def _task_looks_like_parameter_tweak(state: Any) -> bool:
    text = (
        f"{getattr(state, 'task', '')} "
        f"{getattr(state, 'request_payload', {}).get('query', '')} "
        f"{_executor_classification_text(state)}"
    ).casefold()
    return any(term in text for term in _PARAMETER_TWEAK_ACTION_TERMS) and any(
        term in text for term in _PARAMETER_TWEAK_TARGET_TERMS
    )


def _existing_parameter_tweak_targets(state: Any, *, max_targets: int = 4) -> list[str]:
    graph = getattr(state, "graph", None)
    if not isinstance(graph, Mapping):
        return []
    nodes = graph.get("nodes")
    if not isinstance(nodes, Mapping):
        return []

    query_text = (
        f"{getattr(state, 'task', '')} {getattr(state, 'request_payload', {}).get('query', '')}"
    ).casefold()
    ranked_targets: list[tuple[int, str]] = []
    for node_id, node in nodes.items():
        if not isinstance(node, Mapping):
            continue
        class_type = str(node.get("class_type") or node.get("type") or "").strip()
        if not class_type:
            continue
        inputs = node.get("inputs")
        input_fields = [
            str(name)
            for name, value in (inputs.items() if isinstance(inputs, Mapping) else ())
            if not isinstance(value, (Mapping, list, tuple))
        ]
        widget_fields: list[str] = []
        widgets = node.get("widgets")
        if isinstance(widgets, Mapping):
            widget_fields = [str(name) for name in sorted(widgets, key=str)]
        raw_widgets = node.get("raw_widgets")
        raw_widget_count = None
        if isinstance(raw_widgets, Mapping):
            values = raw_widgets.get("values")
            if isinstance(values, list):
                raw_widget_count = len(values)
        if not input_fields and not widget_fields and not raw_widget_count:
            continue
        fields = input_fields + widget_fields
        if raw_widget_count and not widget_fields:
            fields.extend(f"widget_{index}" for index in range(min(raw_widget_count, 4)))
        if not fields:
            continue
        preview = ", ".join(fields[:4])
        if len(fields) > 4:
            preview += ", ..."
        class_text = class_type.casefold()
        field_text = " ".join(fields).casefold()
        score = 0
        if any(term in class_text for term in _PARAMETER_TWEAK_TARGET_TERMS):
            score += 5
        if any(term in field_text for term in _PARAMETER_TWEAK_TARGET_TERMS):
            score += 4
        if any(token and token in class_text for token in query_text.split() if len(token) >= 5):
            score += 4
        if any(token and token in field_text for token in query_text.split() if len(token) >= 5):
            score += 3
        if widget_fields or raw_widget_count:
            score += 3
        if class_type in {"MarkdownNote", "Preview3D", "SaveVideo", "LoadImage"}:
            score -= 6
        ranked_targets.append((score, f"{class_type} [{node_id}] ({preview})"))

    ranked_targets.sort(key=lambda item: (-item[0], item[1]))
    return [target for _score, target in ranked_targets[:max_targets]]


def _direct_existing_parameter_tweak_feedback(
    state: Any,
    clarify_message: str | None = None,
) -> str:
    if not _task_looks_like_parameter_tweak(state):
        return ""
    if clarify_message is not None:
        message_text = str(clarify_message or "").casefold()
        if not any(
            term in message_text
            for term in ("precedent", "schema", "custom node", "not found", "missing", "cannot")
        ):
            return ""
    targets = _existing_parameter_tweak_targets(state)
    if not targets:
        return ""
    target_text = "; ".join(targets)
    return (
        "Direct existing-node tweak fallback applies here: the current graph already contains editable "
        f"target nodes ({target_text}). Stop searching for workflow precedent. Land the smallest local "
        "parameter change on the existing node instead. Prefer a visible named field when present; when "
        "the node is already in the graph and only stable widget slots are visible, a minimal existing "
        "`widget_N` tweak is allowed as a last-resort local parameter edit. Do not add or replace nodes."
    )


'''
