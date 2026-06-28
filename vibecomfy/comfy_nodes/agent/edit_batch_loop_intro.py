# Generated from edit.py. Keep behavior changes in the installed source body.
# Contents: Batch REPL setup, prompt assembly, provider calls, and first clarify rejection branch.

SOURCE = r'''
def _stage_agent_batch_repl(
    state: AgentEditState,
    _context: TurnContext,
    *,
    deepseek_client: DeepSeekClient | None = None,
    route: str | None = None,
    model: str | None = None,
    client_id: str | None = None,
    conversation_messages: list[dict[str, Any]] | None = None,
) -> StageResult:
    from vibecomfy.porting.edit import session as edit_session_module

    start = time.monotonic()
    prepared_ui = state.guard_original_ui or state.graph
    session = edit_session_module.EditSession(prepared_ui, schema_provider=state.schema_provider)
    state.batch_session = session
    initial_render = session.render()
    present_types = _present_class_types(session)
    focus_types = set(present_types)
    effective_task = _effective_implementation_task(state)
    focus_types.update(_seed_focus_types_for_authoring(state))
    focus_types.update(_focus_types_from_research_brief(state.executor_research_brief))
    if _is_code_node_intent(effective_task):
        focus_types.add("vibecomfy.exec")
    signature_catalog = session.search(focus_types=sorted(focus_types), formatted=True)
    available_node_names = _format_available_node_names(session.search(formatted=False))
    state.python_before = initial_render
    state.before_py_path.write_text(initial_render, encoding="utf-8")
    if isinstance(signature_catalog, str):
        state.batch_signature_catalog = signature_catalog

    classification = (
        state.request_payload.get("executor_classification")
        if isinstance(state.request_payload, dict)
        else None
    )
    intent = classification.get("intent") if isinstance(classification, dict) else ""
    # explain_graph intent now maps to the executor inspect route, which
    # never reaches the agent-edit pipeline.  Keep the text-pattern fallback
    # for revise / adapt operations where the task reads like a graph
    # explanation (provides helpful context in the batch-REPL prompt).
    prefetch_explain = not intent and _is_graph_explain_intent(effective_task)
    prefetch_research_summary = state.executor_research_summary or (
        _prefetch_research_summary(effective_task) if prefetch_explain else ""
    )
    research_brief_prompt = _format_research_brief_for_prompt(state.executor_research_brief)
    if prefetch_research_summary and state.executor_research_warnings:
        warning_lines = [
            f"- {warning}" for warning in state.executor_research_warnings[:6]
        ]
        prefetch_research_summary = (
            f"{prefetch_research_summary}\n\n"
            "Research warnings:\n"
            + "\n".join(warning_lines)
        )
    if prefetch_research_summary and state.executor_research_sources:
        source_lines = [
            json.dumps(source, sort_keys=True)
            for source in state.executor_research_sources[:8]
        ]
        prefetch_research_summary = (
            f"{prefetch_research_summary}\n\n"
            "Structured research sources (JSON lines):\n"
            + "\n".join(source_lines)
        )
    prefetch_graph_report = (
        _build_graph_report(state.graph) if prefetch_explain else ""
    )
    # Build compact adaptation plan prompt for adapt route.
    precedent_adaptation_prompt = ""
    adapt_scoped_research_context = ""
    canonical_route = _canonical_agent_edit_route(state.route or route)
    research_only_route = canonical_route == "research"
    if canonical_route == "adapt":
        if state.executor_adaptation_plan:
            precedent_adaptation_prompt = _build_precedent_adaptation_prompt(
                state.executor_adaptation_plan,
                state.executor_precedent_slices,
            )
        # SD3: scoped adapt prefetch from execution_protocol_notes and
        # research_context_packet — discardable, evidence-only context.
        if state.execution_protocol_notes or state.research_context_packet or state.graph_facts:
            parts: list[str] = []
            discard_note: str | None = None
            if state.execution_protocol_notes:
                notes = dict(state.execution_protocol_notes)
                discard_note = notes.pop("_discardability", None)
                notes_str = json.dumps(notes, indent=2, sort_keys=True)
                parts.append(
                    "## Scoped Research Context (execution_protocol_notes)\n"
                    "This is contextual evidence, NOT authoritative guidance.\n"
                    f"{notes_str}"
                )
            if state.research_context_packet:
                packet_str = json.dumps(
                    state.research_context_packet, indent=2, sort_keys=True
                )
                parts.append(
                    "## Research Context Packet (discardable)\n"
                    "Precedent evidence from research phase. "
                    "Discard if empty, irrelevant, or contradictory.\n"
                    f"{packet_str}"
                )
            # SD2: compact graph facts from topology/readiness collectors.
            if state.graph_facts:
                facts_str = json.dumps(state.graph_facts, indent=2, sort_keys=True)
                parts.append(
                    "## Graph Facts (workflow topology evidence)\n"
                    "Deterministic topology/readiness evidence about the current graph. "
                    "Use this to understand the workflow structure, terminal outputs, "
                    "and any known blockers. NOT a revision verdict.\n"
                    f"{facts_str}"
                )
            if discard_note:
                parts.append(f"**Discardability**: {discard_note}")
            adapt_scoped_research_context = "\n\n".join(parts)

    max_batches = max(1, int(state.batch_max_turns or 1))
    max_consecutive_errors = max(1, int(state.batch_max_consecutive_errors or 1))
    state.batch_budget_state = {
        "max_batches": max_batches,
        "max_consecutive_errors": max_consecutive_errors,
        "remaining_batches": max_batches,
        "remaining_consecutive_errors": max_consecutive_errors,
    }
    state.artifacts = {
        "request": str(state.request_path),
        "original_ui": str(state.original_ui_path),
        "before_python": str(state.before_py_path),
        "after_python": str(state.after_py_path),
        "model_request": str(state.model_request_path),
        "model_response": str(state.model_response_path),
        "candidate_ui": str(state.candidate_ui_path),
        "revision_evidence": str(state.revision_evidence_path),
        "messages": str(state.messages_path),
    }

    current_render = initial_render
    last_diff = ""
    last_report = ""
    last_landed_count: int | None = None
    previous_model_message = ""
    consecutive_errors = 0
    total_landed = 0
    done_noop_nudges = 0
    done_error_nudges = 0
    done_candidate_rejection_nudges = 0
    failed_edit_turns = 0
    last_failed_edit_turn = -1
    last_successful_edit_turn_after_failure = -1
    request_log: list[dict[str, Any]] = []
    response_log: list[dict[str, Any]] = []

    for turn_number in range(max_batches):
        budget_remaining = max_batches - turn_number
        include_full_render = turn_number == 0 or last_landed_count == 0
        node_variable_index = _format_node_variable_index(session)
        research_memory = _batch_research_memory_summary(state)
        turn_research_summary = prefetch_research_summary if turn_number == 0 else ""
        if research_memory:
            turn_research_summary = (
                f"{turn_research_summary}\n\nPrior research/query memory:\n{research_memory}"
            ).strip()
        messages = build_batch_messages(
            task=effective_task,
            turn_number=turn_number,
            python_source=(initial_render if turn_number == 0 else current_render)
            if include_full_render
            else "",
            node_variable_index=node_variable_index,
            previous_model_message=previous_model_message,
            signature_catalog=state.batch_signature_catalog if turn_number == 0 else "",
            available_node_names=available_node_names if turn_number == 0 else "",
            diff=last_diff,
            report=last_report,
            budget_remaining=budget_remaining,
            max_batches=max_batches,
            conversation_messages=conversation_messages if turn_number == 0 else None,
            research_only=research_only_route,
            research_brief=research_brief_prompt if turn_number == 0 else "",
            research_summary=turn_research_summary,
            graph_report=prefetch_graph_report if turn_number == 0 else "",
            precedent_adaptation_plan=(
                (precedent_adaptation_prompt + "\n\n" + adapt_scoped_research_context).strip()
                if turn_number == 0
                else ""
            ),
            revision_evidence_json=_revision_evidence_prompt_json(state)
            if turn_number == 0
            else "",
        )
        request_entry = {
            "turn_number": turn_number,
            "messages": messages,
            "budget_remaining": budget_remaining,
            "node_variable_index": node_variable_index,
            "included_full_render": include_full_render,
        }
        request_log.append(request_entry)
        write_json_artifact(
            state.model_request_path,
            {"response_contract": "batch_repl", "turns": request_log},
        )

        try:
            if deepseek_client is not None:
                turn_result = _normalize_test_client_batch_response(deepseek_client(messages))
            else:
                turn_result = run_agent_turn_batch(
                    state.task,
                    messages,
                    route=route,
                    model=model,
                )
        except (MalformedModelJSON, MissingRequiredField) as exc:
            feedback = (
                f"Agent response format error: {exc} "
                "Respond with one user-facing sentence followed by exactly one ```batch fenced block."
            )
            error_record = {
                "turn_number": turn_number,
                "task": state.task,
                "message": "",
                "batch": "",
                "error": str(exc),
                "error_type": type(exc).__name__,
                "request_messages": messages,
            }
            response_log.append(
                {
                    "turn_number": turn_number,
                    "error": {
                        "type": type(exc).__name__,
                        "message": str(exc),
                        "retrying": consecutive_errors + 1 < max_consecutive_errors,
                    },
                }
            )
            write_json_artifact(state.model_response_path, {"turns": response_log})
            state.messages_path.open("a", encoding="utf-8").write(
                json.dumps(error_record, sort_keys=True) + "\n"
            )
            if consecutive_errors + 1 >= max_consecutive_errors:
                raise
            last_report = feedback
            previous_model_message = ""
            last_landed_count = 0
            consecutive_errors += 1
            continue
        except Exception as exc:
            error_record = {
                "turn_number": turn_number,
                "task": state.task,
                "message": "",
                "batch": "",
                "error": str(exc),
                "error_type": type(exc).__name__,
                "request_messages": messages,
            }
            response_log.append(
                {
                    "turn_number": turn_number,
                    "error": {
                        "type": type(exc).__name__,
                        "message": str(exc),
                    },
                }
            )
            write_json_artifact(state.model_response_path, {"turns": response_log})
            state.messages_path.open("a", encoding="utf-8").write(
                json.dumps(error_record, sort_keys=True) + "\n"
            )
            raise

        state.provider_metadata = dict(turn_result.audit_metadata or {})
        state.user_message = turn_result.message
        previous_model_message = turn_result.message
        clarify_split = split_terminal_clarify(turn_result.batch)
        clarify_message = clarify_split.message
        editable_batch = clarify_split.batch if clarify_message is not None else turn_result.batch
        response_log.append(
            {
                "turn_number": turn_number,
                "response": turn_result.to_dict(),
                "status": "received",
            }
        )
        write_json_artifact(state.model_response_path, {"turns": response_log})
        if clarify_message is not None and not editable_batch.strip():
            clarify_feedback = (
                _premature_workflow_schema_clarify_feedback(
                    state,
                    clarify_message,
                )
                or _premature_missing_custom_node_clarify_feedback(
                    state,
                    clarify_message,
                )
            )
            if clarify_feedback:
                consecutive_errors += 1
                turn_record = {
                    "turn_number": turn_number,
                    "batch": turn_result.batch,
                    "message": turn_result.message,
                    "route": turn_result.route,
                    "model": turn_result.model,
                    "provider_metadata": _json_safe(dict(turn_result.audit_metadata or {})),
                    "batch_ok": False,
                    "landed_op_count": 0,
                    "raw_landed_op_count": 0,
                    "statement_count": 1,
                    "diagnostics": [
                        {
                            "code": "premature_missing_custom_node_clarify",
                            "message": clarify_feedback,
                            "severity": "error",
                        }
                    ],
                    "report": clarify_feedback,
                    "field_changes": [],
                }
                state.batch_turns.append(turn_record)
                state.batch_feedback = clarify_feedback
                state.batch_turn_count = turn_number + 1
                state.batch_budget_state = {
                    "max_batches": max_batches,
                    "max_consecutive_errors": max_consecutive_errors,
                    "remaining_batches": max_batches - state.batch_turn_count,
                    "remaining_consecutive_errors": max(0, max_consecutive_errors - consecutive_errors),
                    "consecutive_errors": consecutive_errors,
                }
                response_log[-1] = {
                    "turn_number": turn_number,
                    "response": turn_result.to_dict(),
                    "rejected_clarification": turn_record,
                }
                write_json_artifact(state.model_response_path, {"turns": response_log})
                state.messages_path.open("a", encoding="utf-8").write(
                    json.dumps(
                        {
                            "turn_number": turn_number,
                            "task": state.task,
                            "message": turn_result.message,
                            "batch": turn_result.batch,
'''
