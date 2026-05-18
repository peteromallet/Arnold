"""Regression test for the `parse_agent_output` `plan_mode` NameError bug.

Prior to the fix, ``parse_agent_output`` referenced a ``plan_mode`` symbol
inside its execute-phase fallback (``_reconstruct_execute_payload`` call)
without accepting it as a parameter. ``plan_mode`` was only defined inside
``run_hermes_step`` — a separate function — so the fallback path raised
``NameError: name 'plan_mode' is not defined`` whenever:

  * step == "execute", AND
  * the model produced no parseable JSON via any earlier path (template
    file, final response, reasoning extraction, prior-assistant content),

which is exactly what happened with deepseek-v4-pro returning malformed
JSON for an Astrid sprint-02 brief.

The fix threads ``plan_mode`` through ``parse_agent_output`` as a kwarg
(default ``"code"`` so non-execute callers — parallel critique / parallel
review — keep working without change; that default is unreachable for
non-execute steps).

These tests don't hit the network: they construct a result dict that
deliberately falls through to the execute reconstruction branch and
assert it produces a payload without ``NameError``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from megaplan._core import atomic_write_json, atomic_write_text, read_json, schemas_root
from megaplan.workers.hermes import parse_agent_output
from megaplan.workers import STEP_SCHEMA_FILENAMES


REPO_ROOT = Path(__file__).resolve().parents[1]


def _execute_schema() -> dict:
    # STEP_SCHEMA_FILENAMES["execute"] points at the code-mode execution
    # schema; that's the right reference shape for the execute fallback,
    # which only runs when ``step == "execute"``.
    return read_json(schemas_root(REPO_ROOT) / STEP_SCHEMA_FILENAMES["execute"])


def _scaffold(tmp_path: Path) -> tuple[Path, Path]:
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    # Make the project look like a git repo so the fallback's `git diff`
    # call doesn't blow up — it's wrapped in try/except, but keeping the
    # fixture realistic avoids spurious stderr noise.
    (project_dir / ".git").mkdir()
    return plan_dir, project_dir


class _FakeAgent:
    """Minimal stand-in for AIAgent — we only need run_conversation
    so the in-fallback summary prompt path is exercisable.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def run_conversation(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        # Return empty so we definitely fall through to the reconstruction branch.
        return {"final_response": "", "messages": kwargs.get("conversation_history", [])}


def _execute_messages_with_tool_calls() -> list[dict]:
    """Build a messages list that:
      - has assistant tool_calls (so the "empty + tool calls" branch fires)
      - has no parseable JSON anywhere
      - includes a write_file tool call so _reconstruct_execute_payload
        produces a non-None result.
    """
    return [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "function": {
                        "name": "write_file",
                        "arguments": json.dumps({"path": "foo/bar.py", "content": "x = 1\n"}),
                    }
                }
            ],
        },
        {"role": "tool", "content": "ok"},
        # Final assistant message: no content, no JSON, no reasoning.
        {"role": "assistant", "content": ""},
    ]


def test_parse_agent_output_execute_fallback_does_not_raise_name_error(
    tmp_path: Path,
) -> None:
    """The canonical regression: execute-step fallback used to raise
    ``NameError: name 'plan_mode' is not defined``. With the fix in place
    (``plan_mode`` threaded as a kwarg, defaulting to ``"code"``), the
    call must succeed and return a reconstructed payload.
    """
    plan_dir, project_dir = _scaffold(tmp_path)
    schema = _execute_schema()
    result = {"final_response": "", "messages": _execute_messages_with_tool_calls()}

    payload, raw_output = parse_agent_output(
        _FakeAgent(),
        result,
        output_path=None,
        schema=schema,
        step="execute",
        project_dir=project_dir,
        plan_dir=plan_dir,
        # Intentionally omit plan_mode — exercise the default.
    )

    assert isinstance(payload, dict)
    # Reconstruction path always sets files_changed for code mode.
    assert "files_changed" in payload
    assert "foo/bar.py" in payload["files_changed"]
    assert isinstance(raw_output, str)


def test_parse_agent_output_execute_fallback_honors_doc_plan_mode(
    tmp_path: Path,
) -> None:
    """When plan_mode='doc' is threaded through, the reconstructed
    payload must use the doc-mode shape (sections_written, no
    files_changed) rather than the code-mode shape. This proves the
    parameter is actually wired to ``_reconstruct_execute_payload``
    and not silently ignored.
    """
    plan_dir, project_dir = _scaffold(tmp_path)
    schema = _execute_schema()
    # Doc mode reconstruction reads task_updates from checkpoint files.
    atomic_write_json(
        plan_dir / "execution_batch_001.json",
        {
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "wrote section",
                    "sections_written": ["intro", "background"],
                }
            ]
        },
    )
    result = {"final_response": "", "messages": _execute_messages_with_tool_calls()}

    payload, _ = parse_agent_output(
        _FakeAgent(),
        result,
        output_path=None,
        schema=schema,
        step="execute",
        project_dir=project_dir,
        plan_dir=plan_dir,
        plan_mode="doc",
    )

    assert isinstance(payload, dict)
    # Doc shape: sections_written present, no files_changed key.
    assert "sections_written" in payload
    assert payload["sections_written"] == ["background", "intro"]
    assert "files_changed" not in payload


def test_parse_agent_output_non_execute_step_does_not_touch_plan_mode(
    tmp_path: Path,
) -> None:
    """The parallel critique / parallel review call sites don't pass
    plan_mode (it's irrelevant to those steps). Confirm that path still
    works — i.e. the execute-only branch is guarded by ``step == 'execute'``
    and the default value is never read for non-execute steps.
    """
    plan_dir, project_dir = _scaffold(tmp_path)
    # Use a trivial JSON-able schema; we just need *something* validates as a dict.
    schema = {
        "type": "object",
        "properties": {"checks": {"type": "array"}},
        "required": ["checks"],
    }
    payload_text = json.dumps({"checks": []})
    result = {
        "final_response": payload_text,
        "messages": [{"role": "assistant", "content": payload_text}],
    }

    payload, _ = parse_agent_output(
        _FakeAgent(),
        result,
        output_path=None,
        schema=schema,
        step="critique",
        project_dir=project_dir,
        plan_dir=plan_dir,
        # plan_mode omitted on purpose
    )
    assert payload == {"checks": []}
