# Megaplan Product Policy Catalogue (M4)

> **Status:** M4 Phase 1 baseline.  This catalogue records the legacy policy
> semantics that must be preserved when Megaplan moves to the manifest runtime.
> Every entry pins the behavior to a legacy implementation reference.

## 1. Gate transitions

| Policy | Legacy reference | M4 preservation rule |
| --- | --- | --- |
| `PROCEED` | `arnold_pipelines/megaplan/handlers/gate.py::handle_gate` | Allowed only when no unresolved significant flags remain and preflight is unblocked. |
| `ITERATE` | `arnold_pipelines/megaplan/handlers/gate.py::handle_gate` | Default when critique/gate finds actionable issues; returns to `revise`. |
| `SUSPEND` (human gate) | `arnold_pipelines/megaplan/handlers/gate.py::handle_gate` | Emitted when a human gate is required or confidence is below threshold; runtime suspends before the next node. |
| `ABORT` | `arnold_pipelines/megaplan/handlers/gate.py::handle_gate` | Emitted on catastrophic failure or operator abort; terminates the run. |
| Auto-downgrade `PROCEED` → `ITERATE` | `arnold_pipelines/megaplan/handlers/gate.py::_resolve_revise_transition` | High-complexity unverifiable proceed verdicts are downgraded with rationale; parity test must preserve the rationale text. |
| Post-revise gate allowance | `arnold_pipelines/megaplan/handlers/gate.py::_post_revise_gate_allowed` | A gate immediately after revise may use relaxed thresholds based on the last revision scope. |
| Significant-flag debt recording | `arnold_pipelines/megaplan/handlers/gate.py::_record_gate_debt_entries` | Accepted-but-significant flags are recorded as debt entries for the review phase. |

## 2. Override / fallback meanings

| Policy | Legacy reference | M4 preservation rule |
| --- | --- | --- |
| CLI override label → internal ID | `arnold_pipelines/megaplan/routing/__init__.py::cli_to_internal_override` | Stable bijection between CLI labels (`proceed`, `iterate`, `suspend`, `abort`, `force-proceed`) and internal control IDs. |
| Internal override → CLI label | `arnold_pipelines/megaplan/routing/__init__.py::internal_to_cli_override` | Reverse mapping for projection helpers. |
| Planning gate edges | `arnold_pipelines/megaplan/routing/__init__.py::planning_gate_edges` | Returns the canonical proceed/iterate/suspend/abort edges for the planning gate. |
| Planning override edges | `arnold_pipelines/megaplan/routing/__init__.py::planning_override_edges` | Builds override edges from a mapping of active overrides. |
| Critique→revise→gate routing | `arnold_pipelines/megaplan/routing/__init__.py::critique_revise_gate_routing` | Stable loop topology for critique/revise/gate cycles. |
| Tiebreaker edges | `arnold_pipelines/megaplan/routing/__init__.py::tiebreaker_edges` | Edges used when a tiebreaker is invoked after gate disagreement. |

## 3. Auto-escalation

| Policy | Legacy reference | M4 preservation rule |
| --- | --- | --- |
| Escalation trigger | `arnold_pipelines/megaplan/handlers/gate.py::handle_gate` | Repeated `ITERATE` with no material improvement triggers escalation. |
| Force-proceed (soft) | `arnold_pipelines/megaplan/handlers/gate.py::handle_gate` | Operator may force proceed past significant flags; debt is still recorded. |
| Force-proceed (hard) | `arnold_pipelines/megaplan/handlers/gate.py::handle_gate` | Operator may force proceed and suppress review requirements; must emit an `override` event. |
| Auto-escalation config | `arnold_pipelines/megaplan/policy_settings.py` | Thresholds for iteration count and confidence floor. |

## 4. Tiebreaker recursion

| Policy | Legacy reference | M4 preservation rule |
| --- | --- | --- |
| Tiebreaker invocation | `arnold_pipelines/megaplan/orchestration/tiebreaker.py::_run_tiebreaker` | Called when gate signals disagree or confidence is split. |
| Recursive loop | `arnold_pipelines/megaplan/orchestration/tiebreaker.py::_run_tiebreaker` | Must support at least two recursive loops before resolving; parity test locks this. |
| Resolved synthesis | `arnold_pipelines/megaplan/orchestration/tiebreaker.py::_build_resolved` | Combines challenger/researcher/orchestrator outputs into a single verdict. |
| Prompt rendering | `arnold_pipelines/megaplan/prompts/tiebreaker_orchestrator.py`, `tiebreaker_challenger.py`, `tiebreaker_researcher.py`, `tiebreaker_synthesis.py` | Prompt builders must remain addressable by stable `module:qualname` identifiers in manifest metadata. |

## 5. Feedback phase

| Policy | Legacy reference | M4 preservation rule |
| --- | --- | --- |
| Feedback parsing | `arnold_pipelines/megaplan/orchestration/feedback.py::_parse_section`, `_parse_rating`, `_parse_comment` | Rating (1-5) and comment are extracted from structured feedback text. |
| Effective rating/comment | `arnold_pipelines/megaplan/orchestration/feedback.py::effective_rating`, `effective_comment` | Falls back through reviewer, operator, and model-provided feedback layers. |
| Feedback template rendering | `arnold_pipelines/megaplan/orchestration/feedback.py::render_template` | Templates live in `arnold_pipelines/megaplan/data/` after move. |
| Feedback prompt integration | `arnold_pipelines/megaplan/prompts/__init__.py::_feedback_prompt` | Feedback is injected into revise/critique prompts. |

## 6. Supervisor promotion

| Policy | Legacy reference | M4 preservation rule |
| --- | --- | --- |
| Supervisor promotion rules | `arnold_pipelines/megaplan/supervisor/` | Supervisor heuristics decide when to promote a subagent result to the main plan. |
| Live watchdog supervisor | `arnold_pipelines/megaplan/supervisor/`, `.megaplan/briefs/megaplan-live-watchdog-supervisor.md` | Watchdog logs are archived; promotion logic moves to a manifest node in M5+. |
| Full-suite backstop | `arnold_pipelines/megaplan/orchestration/full_suite_backstop.py` | Determines when the full test suite must run before promotion. |

## 7. Robustness overlays

| Policy | Legacy reference | M4 preservation rule |
| --- | --- | --- |
| Robustness levels | `arnold_pipelines/megaplan/profiles/policy.py` | `ROBUSTNESS_LEVELS` defines minimal/moderate/aggressive validation depth. |
| Profile selection | `arnold_pipelines/megaplan/profiles/` | Profiles map modes (code/doc/creative/joke/plan) to tier/model/policy tuples. |
| Recovery policy | `arnold_pipelines/megaplan/orchestration/recovery_policy.py::RecoveryPolicy` | Decides retry vs. quarantine for infrastructure errors. |
| Retryable external errors | `arnold_pipelines/megaplan/orchestration/recovery_policy.py::_is_retryable_external_error` | Provider/network errors are retried; validation errors are not. |
| Blocked retry detection | `arnold_pipelines/megaplan/handlers/execute.py::_is_blocked_retry` | Distinguishes rework re-execution from blocked retry. |

## 8. Prompt builders

| Policy | Legacy reference | M4 preservation rule |
| --- | --- | --- |
| Prompt component registry | `arnold_pipelines/megaplan/prompts/__init__.py::PromptComponents` | Components are assembled per phase. |
| Harness guard prepend | `arnold_pipelines/megaplan/prompts/__init__.py::_prepend_harness_guard` | Stable guard text prepended to all prompts. |
| Execute batch prompt | `arnold_pipelines/megaplan/prompts/__init__.py::_execute_batch_prompt` | Batch prompt builder for execute phase. |
| Phase prompt modules | `arnold_pipelines/megaplan/prompts/prep_doc.py`, `planning.py`, `critique.py`, `critique_evaluator.py`, `execute.py`, `finalize.py`, `gate.py`, `review.py`, `review_doc.py`, `review_joke.py`, `feedback.py` | Each module owns one phase prompt; moved unchanged to `arnold_pipelines/megaplan/prompts/`. |

## 9. Reducers

| Policy | Legacy reference | M4 preservation rule |
| --- | --- | --- |
| Execute merge / aggregation | `arnold_pipelines/megaplan/execute/merge.py`, `aggregation.py` | Reduces worker outputs into a single `StepResponse`. |
| Quality reducer | `arnold_pipelines/megaplan/execute/quality.py` | Quality scoring and acceptance thresholds. |
| Status constants | `arnold_pipelines/megaplan/execute/status_constants.py` | `pending`, `done`, `blocked`, `failed` task statuses. |
| Execute envelope | `arnold_pipelines/megaplan/execute/_envelope.py` | Envelope format for execute payloads. |

## 10. Dynamic topology

| Policy | Legacy reference | M4 preservation rule |
| --- | --- | --- |
| Topology overlays | `arnold_pipelines/megaplan/_core/topology.py` | Robustness-driven topology overlays (extra critique, extra execute, etc.). |
| Dynamic pattern edges | `arnold_pipelines/megaplan/_pipeline/pattern_dynamic.py`, `pattern_topology.py`, `pattern_joins.py`, `pattern_select.py`, `pattern_stops.py` | Patterns that add/remove edges based on flags or mode. |
| Loop node | `arnold_pipelines/megaplan/_pipeline/loop_node.py` | Loop construct used for critique/revise cycles. |
| Transition policy writer | `arnold_pipelines/megaplan/orchestration/transition_policy.py::TransitionPolicy`, `TransitionWriter` | Encodes phase transition rules as data for the manifest backend. |

## 11. Task satisfaction

| Policy | Legacy reference | M4 preservation rule |
| --- | --- | --- |
| Evidence nucleus normalization | `arnold_pipelines/megaplan/orchestration/task_satisfaction.py::_normalize_evidence_nucleus` | Normalizes evidence references across task/execution outputs. |
| Ancestor HEAD staleness | `arnold_pipelines/megaplan/orchestration/task_satisfaction.py::is_task_satisfied` | Satisfied task is re-evaluated if `HEAD` changed since evidence was produced. |
| Execution window | `arnold_pipelines/megaplan/orchestration/task_satisfaction.py::EvidenceExecutionWindow` | Defines which execution outputs count as evidence for a task. |

## 12. Handler semantic parity checklist

Before M4 parity tests are considered complete, the following handler behaviors
must be shown to match between legacy and manifest-backed runs:

| Behavior | Legacy reference | Test target |
| --- | --- | --- |
| Finalize blast-radius fallback from git diff | `arnold_pipelines/megaplan/handlers/finalize.py` | `tests/arnold_pipelines/megaplan/test_finalize_parity.py` (M4 Phase 5) |
| Execute `pending` task status | `arnold_pipelines/megaplan/handlers/execute.py` | parity test |
| Task-satisfaction ancestor HEAD staleness | `arnold_pipelines/megaplan/orchestration/task_satisfaction.py` | parity test |
| Subprocess/git timeout hardening | `arnold_pipelines/megaplan/handlers/execute.py`, `drivers/` | parity test |
| Critique payload key stripping | `arnold_pipelines/megaplan/handlers/critique.py` | parity test |
| Review payload defaults / task IDs | `arnold_pipelines/megaplan/handlers/review.py` | parity test |
| Plan-text newline normalization | `arnold_pipelines/megaplan/handlers/plan.py` | parity test |
| `infrastructure_error` classification | `arnold_pipelines/megaplan/handlers/review.py::_review_infrastructure_failure` | parity test |

## 13. Notes

* All legacy paths above are relative to `arnold_pipelines/megaplan/`.  After
  M4 Phase 2 the same modules exist under `arnold_pipelines/megaplan/` with
  identical behavior.
* Stable identifiers for prompt builders and topology overlays should be
  recorded as `arnold_pipelines.megaplan.prompts.<module>:<qualname>` or
  `arnold_pipelines.megaplan._core.topology:<qualname>` in manifest metadata
  (M4 Phase 3).
* This catalogue is the parity checklist; every policy here must have a
  corresponding test before M4 is complete.
