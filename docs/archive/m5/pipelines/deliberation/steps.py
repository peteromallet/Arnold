"""Deliberation pipeline steps — QuestionGen, HumanGate, DraftPlan, and
CritiquePanel stages.

Provides :func:`build_question_gen_stage` for wiring the initial
question-generation node, :func:`load_questions` for reading back
versioned JSON artifacts, :func:`parse_llm_json` for robust
JSON extraction from raw LLM output, :func:`build_human_gate_stage`
for the boundary-ratifying human suspension point,
:func:`build_draft_plan_stage` for the initial draft-plan synthesis
(with an answers.json precondition guard), and
:func:`build_critique_panel_stage` for the per-layer fan-out critique
panel.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from arnold.pipeline.pattern_joins import aggregate_panel_join
from arnold.pipeline.resources import PromptSource
from arnold.pipeline.steps.agent import AgentStep, WorkerFn
from arnold.pipeline.steps.human_gate import HumanGateStep
from arnold.pipeline.steps.panel import PanelReviewerStep
from arnold.pipeline.types import Edge, ParallelStage, Stage
from arnold.runtime.event_journal import EventSink, read_event_journal
from arnold.runtime.wal_fold import fold_journal, last_state_snapshot_projector

# ---------------------------------------------------------------------------
# parse_llm_json
# ---------------------------------------------------------------------------

_JSON_FENCE_RE = re.compile(r"```json\s*\n(.*?)```", re.DOTALL)


def parse_llm_json(text: str) -> dict[str, Any]:
    """Parse a JSON ``dict`` from raw LLM output.

    Tries three strategies in order:

    1. Direct ``json.loads`` of the whole string (ideal case).
    2. Extract content from the first `` ```json ... ``` `` fenced block.
    3. Scan for the first decodable ``{...}`` JSON object.

    Returns the parsed ``dict`` on success.

    Raises :exc:`ValueError` when no valid JSON **object** can be
    extracted — arrays, scalars, and unparsable text all produce an
    error because the deliberation contract always expects a top-level
    object.
    """
    stripped = text.strip()
    if not stripped:
        raise ValueError("LLM output is empty")

    # Strategy 1 — direct parse
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Strategy 2 — ```json ... ``` fenced block
    for block in _JSON_FENCE_RE.findall(stripped):
        try:
            parsed = json.loads(block.strip())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    # Strategy 3 — first decodable {...} object
    decoder = json.JSONDecoder()
    cursor = 0
    while True:
        brace = stripped.find("{", cursor)
        if brace < 0:
            break
        try:
            parsed, _end = decoder.raw_decode(stripped[brace:])
        except json.JSONDecodeError:
            cursor = brace + 1
            continue
        if isinstance(parsed, dict):
            return parsed
        cursor = brace + 1

    raise ValueError("Could not extract a valid JSON object from LLM output")


# ---------------------------------------------------------------------------
# build_question_gen_stage
# ---------------------------------------------------------------------------


def build_question_gen_stage(
    prompt_source: PromptSource,
    worker: WorkerFn,
) -> Stage:
    """Build the ``question_gen`` :class:`Stage` for the deliberation pipeline.

    The returned stage wraps an :class:`~arnold.pipeline.steps.agent.AgentStep`
    configured with:

    * ``name='question_gen'``
    * ``_output_label='questions'`` — so artifacts land under
      ``<artifact_root>/question_gen/questions/``
    * ``_output_suffix='json'`` — producing ``v1.json``, ``v2.json``, etc.
    * A single outgoing edge ``Edge(label='done', target='human_gate')``

    Parameters
    ----------
    prompt_source:
        Resolvable prompt that instructs the model to produce a
        strict-JSON ``{questions: [{q, rationale}, ...]}`` structure.
    worker:
        Callable invoked by :class:`AgentStep` to produce the model
        response.  Must accept ``prompt``, ``step_name``,
        ``pipeline_name``, ``inputs``, and ``mode`` keyword arguments.
    """
    step = AgentStep(
        name="question_gen",
        kind="produce",
        prompt_key="question_gen",
        _prompt_source=prompt_source,
        _output_label="questions",
        _output_suffix="json",
        _worker=worker,
    )
    return Stage(
        name="question_gen",
        step=step,
        edges=(Edge(label="done", target="human_gate"),),
    )


# ---------------------------------------------------------------------------
# load_questions
# ---------------------------------------------------------------------------

_VERSION_RE = re.compile(r"^v(\d+)\.json$")


def load_questions(
    artifact_root: str | Path,
    stage_name: str = "question_gen",
) -> dict[str, Any]:
    """Load the questions dict from the latest versioned JSON artifact.

    Scans ``<artifact_root>/<stage_name>/questions/v*.json``, picks
    the highest version number, reads the file content, and parses it
    via :func:`parse_llm_json`.

    Returns the parsed ``dict`` (expected shape:
    ``{"questions": [{"q": ..., "rationale": ...}, ...]}``).

    Raises :exc:`ValueError` when:

    * The artifact directory does not exist.
    * No ``v*.json`` files are found.
    * The latest artifact is empty.
    * :func:`parse_llm_json` cannot extract a valid object.
    """
    root = Path(artifact_root)
    questions_dir = root / stage_name / "questions"

    if not questions_dir.is_dir():
        raise ValueError(
            f"Questions artifact directory not found: {questions_dir}"
        )

    candidates: list[tuple[int, Path]] = []
    for path in questions_dir.glob("v*.json"):
        m = _VERSION_RE.match(path.name)
        if m:
            candidates.append((int(m.group(1)), path))

    if not candidates:
        raise ValueError(
            f"No versioned JSON artifacts found in {questions_dir}"
        )

    candidates.sort(key=lambda x: x[0], reverse=True)
    latest = candidates[0][1]

    content = latest.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(f"Questions artifact is empty: {latest}")

    return parse_llm_json(content)


# ---------------------------------------------------------------------------
# build_human_gate_stage
# ---------------------------------------------------------------------------


_HUMAN_GATE_PROMPT = (
    "Please review the generated questions in the question_gen artifact. "
    "Answer each question thoughtfully and save your answers as a JSON file "
    "named 'answers.json' in the artifact root with the structure: "
    '{"answers": [{"q": "question text", "a": "your answer"}, ...]}. '
    "When done, set the _resume_choice in awaiting_user.json to "
    "'answers_collected' to continue the deliberation pipeline."
)


def build_human_gate_stage() -> Stage:
    """Build the ``human_gate`` :class:`Stage` for the deliberation pipeline.

    The returned stage wraps a
    :class:`~arnold.pipeline.steps.human_gate.HumanGateStep` configured with:

    * ``name='human_gate'``
    * ``_artifact_stage='question_gen'`` — user reviews the questions artifact
    * ``_choices=['answers_collected']`` — the single valid resume choice
    * ``_checkpoint_filename='awaiting_user.json'``
    * A descriptive ``_prompt`` instructing the user to answer questions and
      write ``answers.json``

    A single outgoing edge ``Edge(label='answers_collected', target='draft_plan')``
    carries execution to the draft-plan synthesis stage after the human
    answers are collected.
    """
    step = HumanGateStep(
        name="human_gate",
        kind="decide",
        _artifact_stage="question_gen",
        _choices=["answers_collected"],
        _checkpoint_filename="awaiting_user.json",
        _prompt=_HUMAN_GATE_PROMPT,
    )
    return Stage(
        name="human_gate",
        step=step,
        edges=(Edge(label="answers_collected", target="draft_plan"),),
    )


# ---------------------------------------------------------------------------
# build_draft_plan_stage
# ---------------------------------------------------------------------------


def _make_guarded_worker(worker: WorkerFn) -> WorkerFn:
    """Wrap *worker* with a precondition guard that validates ``answers.json``.

    The guard reads the ``answers`` entry from the worker's ``inputs``
    dict (a filesystem path), verifies the file exists and contains valid
    JSON, and then enriches the ``inputs`` dict by replacing each
    path-based value with the corresponding file content before delegating
    to the real *worker*.

    Raises :exc:`ValueError` when:

    * ``answers`` is missing from ``inputs``
    * ``answers.json`` does not exist at the given path
    * ``answers.json`` is empty
    * ``answers.json`` is not valid JSON
    """

    def guarded(**kwargs: Any) -> Any:
        inputs: dict[str, Any] = dict(kwargs.get("inputs", {}))

        # ── precondition: answers.json must exist and be valid JSON ──
        answers_path_str = inputs.get("answers", "")
        if not answers_path_str:
            raise ValueError("answers key not found in worker inputs")
        answers_path = Path(answers_path_str)
        if not answers_path.exists():
            raise ValueError(f"answers.json not found at {answers_path}")
        try:
            answers_text = answers_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ValueError(
                f"Could not read answers.json at {answers_path}: {exc}"
            ) from exc
        if not answers_text:
            raise ValueError("answers.json is empty")
        try:
            json.loads(answers_text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"answers.json is not valid JSON: {exc}"
            ) from exc

        # ── enrich: replace file paths with content so prompt
        #    interpolation receives actual text, not paths ──
        enriched: dict[str, str] = {}
        for key, val in inputs.items():
            try:
                p = Path(str(val))
                if p.exists():
                    enriched[key] = p.read_text(encoding="utf-8")
                    continue
            except (OSError, UnicodeDecodeError):
                pass
            enriched[key] = str(val)

        return worker(**{**kwargs, "inputs": enriched})

    return guarded


def build_draft_plan_stage(
    prompt_source: PromptSource,
    worker: WorkerFn,
) -> Stage:
    """Build the ``draft_plan`` :class:`Stage` for the deliberation pipeline.

    The returned stage wraps an :class:`~arnold.pipeline.steps.agent.AgentStep`
    configured with:

    * ``name='draft_plan'``
    * ``_output_label='plan'`` — artifacts land under
      ``<artifact_root>/draft_plan/plan/``
    * ``_output_suffix='json'``
    * ``_input_refs=['questions', 'answers']`` — reads the questions from the
      upstream ``question_gen`` stage and the user-provided answers
    * A precondition guard (via worker wrapping) that validates
      ``answers.json`` exists and is valid JSON before the real worker runs

    A single outgoing edge ``Edge(label='done', target='layer_0_synth')``
    carries execution to the first layered synthesis stage.
    """
    guarded_worker = _make_guarded_worker(worker)
    step = AgentStep(
        name="draft_plan",
        kind="produce",
        prompt_key="draft_plan",
        _prompt_source=prompt_source,
        _output_label="plan",
        _output_suffix="json",
        _input_refs=["questions", "answers"],
        _worker=guarded_worker,
    )
    return Stage(
        name="draft_plan",
        step=step,
        edges=(Edge(label="done", target="layer_0_synth"),),
    )


# ---------------------------------------------------------------------------
# DEFAULT_PERSONAS_FOR_LAYER
# ---------------------------------------------------------------------------

#: Per-abstraction-level default panel personas.
#:
#: Each level maps to exactly 10 personas — the maximum allowed by
#: :func:`build_critique_panel_stage`.  Downstream code can override
#: individual personas via the ``panel_personas`` key in the profile
#: dict config.
DEFAULT_PERSONAS_FOR_LAYER: dict[str, list[str]] = {
    "high": [
        "strategist",
        "visionary",
        "contrarian",
        "ethicist",
        "systems_thinker",
        "risk_manager",
        "synthesizer",
        "scout",
        "bridge_builder",
        "lateral_thinker",
    ],
    "mid": [
        "analyst",
        "pragmatist",
        "implementor",
        "tester",
        "integrator",
        "optimizer",
        "debugger",
        "reviewer",
        "auditor",
        "documenter",
    ],
    "low": [
        "precisionist",
        "consistency_checker",
        "edge_case_hunter",
        "grammarian",
        "fact_checker",
        "spec_compliance",
        "thorough_reader",
        "completionist",
        "redundancy_eliminator",
        "formalist",
    ],
}

# ---------------------------------------------------------------------------
# build_critique_panel_stage
# ---------------------------------------------------------------------------


def _normalize_panel_config(
    layer: int,
    profile_layer_config: str | dict[str, Any],
) -> dict[str, Any]:
    """Normalize *profile_layer_config* to a dict with ``level`` and
    ``panel_personas`` keys.

    String configs are treated as abstraction-level keys; their
    personas are resolved from :data:`DEFAULT_PERSONAS_FOR_LAYER`.
    Dict configs must contain an ``abstraction_level`` key; optional
    ``panel_personas`` override the defaults.
    """
    if isinstance(profile_layer_config, str):
        level = profile_layer_config.strip()
        if level not in DEFAULT_PERSONAS_FOR_LAYER:
            raise ValueError(
                f"Unknown abstraction level {level!r} for layer {layer}; "
                f"expected one of {sorted(DEFAULT_PERSONAS_FOR_LAYER)}"
            )
        return {
            "level": level,
            "panel_personas": list(DEFAULT_PERSONAS_FOR_LAYER[level]),
        }

    if isinstance(profile_layer_config, dict):
        level = profile_layer_config.get("abstraction_level")
        if not isinstance(level, str) or not level.strip():
            raise ValueError(
                f"Dict config for layer {layer} missing valid "
                f"'abstraction_level' key; got {level!r}"
            )
        level = level.strip()
        if level not in DEFAULT_PERSONAS_FOR_LAYER:
            raise ValueError(
                f"Unknown abstraction level {level!r} for layer {layer}; "
                f"expected one of {sorted(DEFAULT_PERSONAS_FOR_LAYER)}"
            )
        personas = profile_layer_config.get("panel_personas")
        if personas is None:
            personas = list(DEFAULT_PERSONAS_FOR_LAYER[level])
        elif not isinstance(personas, list):
            raise ValueError(
                f"'panel_personas' for layer {layer} must be a list, "
                f"got {type(personas).__name__}"
            )
        return {"level": level, "panel_personas": list(personas)}

    raise TypeError(
        f"profile_layer_config for layer {layer} must be str or dict, "
        f"got {type(profile_layer_config).__name__}"
    )


def build_critique_panel_stage(
    layer: int,
    *,
    profile_layer_config: str | dict[str, Any],
    prompt_source: PromptSource,
    worker: WorkerFn,
) -> ParallelStage:
    """Build a per-layer fan-out critique panel as a :class:`ParallelStage`.

    Each persona in the resolved panel-persona list becomes a
    :class:`~arnold.pipeline.steps.panel.PanelReviewerStep` that reviews
    the layer's synthesis output through its own persona lens.

    Parameters
    ----------
    layer:
        Zero-based layer index.  Used to derive stage names (e.g.
        ``layer_0_panel`` → ``layer_0_synth``).
    profile_layer_config:
        Either a plain abstraction-level string (``'high'``, ``'mid'``,
        or ``'low'``) which resolves to the default persona set for
        that level, or a dict with an ``abstraction_level`` key and an
        optional ``panel_personas`` list override.
    prompt_source:
        Resolvable prompt source used by every reviewer in the panel.
    worker:
        Callable invoked by each :class:`PanelReviewerStep`.

    Returns
    -------
    ParallelStage
        A parallel fan-out stage with:

        * ``name`` = ``'layer_{layer}_panel'``
        * ``steps`` = one :class:`PanelReviewerStep` per persona
        * ``max_workers`` = ``10``
        * ``join`` = :func:`aggregate_panel_join` with
          ``next_label='panel_done'``
        * ``edges`` = ``Edge('panel_done', 'layer_{layer}_synth')``

    Raises
    ------
    ValueError
        If the resolved persona list exceeds 10 entries or if the
        abstraction level is unknown.
    TypeError
        If *profile_layer_config* is neither a string nor a dict.
    """
    config = _normalize_panel_config(layer, profile_layer_config)
    personas: list[str] = config["panel_personas"]

    if len(personas) > 10:
        raise ValueError(
            f"Layer {layer} panel has {len(personas)} personas; "
            f"maximum is 10"
        )

    stage_name = f"layer_{layer}_panel"

    # Build one PanelReviewerStep per persona.
    steps: list[PanelReviewerStep] = []
    for persona in personas:
        step = PanelReviewerStep(
            name=f"{stage_name}.{persona}",
            kind="produce",
            prompt_key=f"layer_{layer}_panel",
            _prompt_source=prompt_source,
            _pipeline_name="deliberation",
            _input_refs=["plan"],
            _reviewer_id=persona,
            _worker=worker,
            _mode="default",
        )
        steps.append(step)

    join_fn = aggregate_panel_join(next_label="panel_done")

    return ParallelStage(
        name=stage_name,
        steps=tuple(steps),
        max_workers=10,
        join=join_fn,
        edges=(Edge(label="panel_done", target=f"layer_{layer}_synth"),),
    )


# ---------------------------------------------------------------------------
# build_skeptical_synthesis_stage
# ---------------------------------------------------------------------------


_SYNTHESIS_PROMPT = (
    "You are a Skeptical Synthesis agent for the Arnold Deliberation Pipeline.\n"
    "Your task is to review the **current plan** and the **panel critiques**\n"
    "and produce a revised plan that reflects your **independent judgment**.\n"
    "\n"
    "## Judgment rules\n"
    "\n"
    "- You are NOT a vote-counter.  A critique may be accepted even when it is\n"
    "  the minority view, provided it is well-reasoned and material.\n"
    "- Conversely, a majority critique may be **rejected** when it is poorly\n"
    "  reasoned, irrelevant, or contradicts known constraints.\n"
    "- A critique may be **reframed** — its core insight preserved but the\n"
    "  concrete change re-expressed in a more useful form.\n"
    "- Every critique you process MUST appear in the changelog with an\n"
    "  explicit verdict (``accept``, ``reject``, or ``reframe``) and a brief\n"
    "  reason.\n"
    "\n"
    "## Output format\n"
    "\n"
    "Respond with a **single JSON object** — no preamble, no markdown outside\n"
    "of a ```json fenced block, but the object itself must be parseable\n"
    "directly:\n"
    "\n"
    "```json\n"
    "{\n"
    '  "plan_version": <int — incremented from previous plan_version>,\n'
    '  "sections": [\n'
    "    {\n"
    '      "title": "string",\n'
    '      "content": "string — the revised section text"\n'
    "    }\n"
    "  ],\n"
    '  "changelog": [\n'
    "    {\n"
    '      "critique": "string — the critique being evaluated",\n'
    '      "verdict": "accept | reject | reframe",\n'
    '      "reason": "string — why this verdict was reached",\n'
    '      "applied_change": "string — what changed in the plan (empty for reject)"\n'
    "    }\n"
    "  ]\n"
    "}\n"
    "```\n"
    "\n"
    "## Constraints\n"
    "\n"
    "- ``plan_version`` MUST be an integer >= 0 (0 for the initial draft).\n"
    "- ``sections`` MUST be a non-empty array of objects with ``title``\n"
    "  and ``content``.\n"
    "- ``changelog`` MUST be a non-empty array — every critique from the\n"
    "  panel MUST be acknowledged.\n"
    "- ``verdict`` MUST be exactly ``accept``, ``reject``, or ``reframe``.\n"
    "- ``applied_change`` MUST be a non-empty string for ``accept`` and\n"
    "  ``reframe`` verdicts, and MUST be an empty string for ``reject``.\n"
    "- The JSON MUST be valid and parseable by a strict ``json.loads``\n"
    "  parser.\n"
    "\n"
    "Current plan:\n"
    "{plan}\n"
    "\n"
    "Panel critiques:\n"
    "{panel_reviews}\n"
)


def _make_journaling_worker(
    worker: WorkerFn,
    journal: EventSink,
    layer: int,
) -> WorkerFn:
    """Wrap *worker* so a ``state`` checkpoint event is emitted after every run.

    After the real *worker* returns, the wrapper attempts to parse the
    result as JSON (best-effort) and emits a ``state`` event to *journal*
    with the parsed plan in the payload.  If parsing fails, the raw text
    is stored under ``raw_output`` instead.

    The event is emitted with ``kind='state'`` and
    ``phase='layer_{layer}_synth'`` so that :func:`fold_journal` can
    reconstruct the latest plan snapshot by filtering on ``'state'``
    events and projecting the ``state`` field.
    """

    def journaling(**kwargs: Any) -> Any:
        result_text = worker(**kwargs)
        result_str = str(result_text)

        # Best-effort: parse the result as JSON for the state payload.
        try:
            parsed = json.loads(result_str)
        except json.JSONDecodeError:
            parsed = None

        payload: dict[str, Any] = {
            "layer": layer,
            "raw_output": result_str,
        }
        if isinstance(parsed, dict):
            payload["state"] = parsed
            payload["plan_version"] = parsed.get("plan_version")

        journal.emit(
            "state",
            payload=payload,
            phase=f"layer_{layer}_synth",
        )

        return result_text

    return journaling


def build_skeptical_synthesis_stage(
    layer: int,
    *,
    next_target: str,
    prompt_source: PromptSource,
    worker: WorkerFn,
    journal: EventSink,
) -> Stage:
    """Build a skeptical-synthesis :class:`Stage` for layer *layer*.

    The returned stage wraps an :class:`~arnold.pipeline.steps.agent.AgentStep`
    that takes the current plan and panel reviews, applies independent
    judgment over the critiques, and produces a revised plan with a
    full changelog.

    A single outgoing edge ``Edge(label='done', target=next_target)``
    carries execution to *next_target* (typically the next layer's
    panel or the final report stage).

    Parameters
    ----------
    layer:
        Zero-based layer index.  The stage is named
        ``layer_{layer}_synth``.
    next_target:
        Name of the downstream stage (e.g. ``'layer_1_panel'`` or
        ``'final_report'``).
    prompt_source:
        Resolvable prompt source.  When *prompt_source* is ``None``,
        the built-in :data:`_SYNTHESIS_PROMPT` is used as a fallback.
    worker:
        Callable invoked by :class:`AgentStep` to produce the model
        response.
    journal:
        Event sink where a ``state`` checkpoint event is emitted after
        every successful synthesis run.  The emitted event carries
        ``kind='state'`` and ``phase='layer_{layer}_synth'`` so that
        :func:`reconstruct_plan_from_journal` can replay the lineage.

    Returns
    -------
    Stage
        A single-step stage named ``layer_{layer}_synth`` with:
        * ``AgentStep(name='layer_{layer}_synth', _output_label='plan',
          _output_suffix='json')``
        * ``edges = (Edge(label='done', target=next_target),)``
    """
    stage_name = f"layer_{layer}_synth"
    journaling_worker = _make_journaling_worker(worker, journal, layer)

    step = AgentStep(
        name=stage_name,
        kind="produce",
        prompt_key=f"layer_{layer}_synth",
        _prompt_source=prompt_source,
        _output_label="plan",
        _output_suffix="json",
        _input_refs=["plan", "panel_reviews"],
        _worker=journaling_worker,
    )

    return Stage(
        name=stage_name,
        step=step,
        edges=(Edge(label="done", target=next_target),),
    )


# ---------------------------------------------------------------------------
# reconstruct_plan_from_journal
# ---------------------------------------------------------------------------


def reconstruct_plan_from_journal(
    artifact_root: str | Path,
) -> dict[str, Any] | None:
    """Reconstruct the latest plan snapshot from the event journal.

    Reads ``<artifact_root>/events.ndjson``, folds all ``state`` events
    via :func:`fold_journal` with :func:`last_state_snapshot_projector`,
    and returns the final accumulator — the most recent ``state`` dict
    seen in the journal.

    Returns ``None`` when no ``state`` events exist in the journal.

    This is the authoritative reconstruction path: the plan lineage is
    fully recoverable from ``events.ndjson`` alone, without requiring
    the per-stage artifact tree.
    """
    root = Path(artifact_root)
    events = read_event_journal(root)
    if not events:
        return None

    result = fold_journal(
        events,
        kind_filter="state",
        projector=last_state_snapshot_projector,
        initial=None,
    )
    return result if isinstance(result, dict) else None


# ---------------------------------------------------------------------------
# build_final_report_stage
# ---------------------------------------------------------------------------


def build_final_report_stage(
    prompt_source: PromptSource,
    worker: WorkerFn,
) -> Stage:
    """Build the ``final_report`` :class:`Stage` for the deliberation pipeline.

    The returned stage wraps an :class:`~arnold.pipeline.steps.agent.AgentStep`
    configured with:

    * ``name='final_report'``
    * ``_output_label='report'`` — artifacts land under
      ``<artifact_root>/final_report/report/``
    * ``_output_suffix='md'`` — producing ``v1.md``, ``v2.md``, etc.
    * ``_input_refs=['plan']`` — reads the final plan from the last
      synthesis stage
    * A single outgoing edge ``Edge(label='done', target='halt')``
      which terminates the pipeline

    Parameters
    ----------
    prompt_source:
        Resolvable prompt that instructs the model to produce a final
        report in markdown format.
    worker:
        Callable invoked by :class:`AgentStep` to produce the model
        response.
    """
    step = AgentStep(
        name="final_report",
        kind="produce",
        prompt_key="final_report",
        _prompt_source=prompt_source,
        _output_label="report",
        _output_suffix="md",
        _input_refs=["plan"],
        _worker=worker,
    )
    return Stage(
        name="final_report",
        step=step,
        edges=(Edge(label="done", target="halt"),),
    )


__all__ = [
    "DEFAULT_PERSONAS_FOR_LAYER",
    "build_critique_panel_stage",
    "build_draft_plan_stage",
    "build_final_report_stage",
    "build_human_gate_stage",
    "build_question_gen_stage",
    "build_skeptical_synthesis_stage",
    "load_questions",
    "parse_llm_json",
    "reconstruct_plan_from_journal",
]
