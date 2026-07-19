"""Agent runner protocols for resident turns."""

from __future__ import annotations

import asyncio
import contextvars
from datetime import UTC, datetime
import hashlib
import json
import os
import signal
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping, Protocol

from pydantic import BaseModel, ValidationError

from arnold.execution.step_invocation import StepInvocation
from arnold.agent.routing import MANAGED_AGENT_BACKENDS, resolve_managed_agent_route
from arnold_pipelines.megaplan.model_seam import ModelBudgetError, ModelTier, render_step_message

from .config import ResidentConfig
from .provenance import environment_with_provenance
from .provider_runtime import (
    claude_tools_for,
    collect_provider_evidence,
    normalize_toolsets,
    provider_execution_contract,
    reserve_session_id,
    write_normalized_events,
)
from .request_summary import current_request_summary_line
from .tool_schemas import ToolCallAuditRecord, ToolResult
from .tool_registry import ToolRegistry


@dataclass(frozen=True)
class ToolRuntimeContext:
    conversation_id: str
    subject: Any | None = None
    launch_origin: Mapping[str, Any] | None = None
    tool_call_id: str | None = None


_TOOL_RUNTIME_CONTEXT: contextvars.ContextVar[ToolRuntimeContext | None] = contextvars.ContextVar(
    "resident_tool_runtime_context",
    default=None,
)


def current_tool_runtime_context() -> ToolRuntimeContext | None:
    return _TOOL_RUNTIME_CONTEXT.get()


@dataclass(frozen=True)
class AgentRequest:
    conversation_id: str
    messages: tuple[dict[str, Any], ...]
    system_prompt: str
    turn_id: str | None = None
    hot_context: dict[str, Any] = field(default_factory=dict)
    model_seam_metadata: Mapping[str, Any] = field(default_factory=dict)
    subject: Any | None = None
    escalation_id: str | None = None
    resume_handler: str | None = None
    target_id: str | None = None
    launch_origin: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class AgentResponse:
    final_text: str
    tool_calls: tuple[ToolCallAuditRecord, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


class DispatchProtocol(Protocol):
    async def run(self, request: AgentRequest, tools: ToolRegistry) -> AgentResponse:
        """Dispatch one resident bot turn through the resident model/tool loop."""


class AgentRunner(DispatchProtocol, Protocol):
    """Resident runner alias for the shared dispatch-shaped Protocol."""


@dataclass(frozen=True)
class FakeToolCall:
    """Scripted fake-model tool request used by tests and local dry runs."""

    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FakeAgentStep:
    """One fake-model step: either call a tool or return final text."""

    tool_call: FakeToolCall | None = None
    final_text: str | None = None

    @classmethod
    def call(cls, tool_name: str, arguments: dict[str, Any] | None = None) -> "FakeAgentStep":
        return cls(tool_call=FakeToolCall(tool_name=tool_name, arguments=dict(arguments or {})))

    @classmethod
    def final(cls, text: str) -> "FakeAgentStep":
        return cls(final_text=text)


class AgentLoopError(RuntimeError):
    """Deterministic resident agent-loop failure."""


class AgentPromptTooLargeError(AgentLoopError):
    """The resident request exceeded its safe budget before model launch."""


class ResidentCredentialError(AgentLoopError):
    """A configured resident API call has no usable credential."""

    def __init__(self, env_name: str) -> None:
        super().__init__(f"{env_name} is required for live resident API calls")
        self.env_name = env_name


class FakeAgentRunner:
    """Deterministic runner that exercises the resident tool-call loop."""

    def __init__(
        self,
        steps: list[FakeAgentStep] | tuple[FakeAgentStep, ...],
        *,
        max_tool_calls: int = 8,
        tool_timeout_s: float = 30.0,
    ) -> None:
        if max_tool_calls <= 0:
            raise ValueError("max_tool_calls must be positive")
        if tool_timeout_s <= 0:
            raise ValueError("tool_timeout_s must be positive")
        self.steps = tuple(steps)
        self.max_tool_calls = max_tool_calls
        self.tool_timeout_s = tool_timeout_s

    async def run(self, request: AgentRequest, tools: ToolRegistry) -> AgentResponse:
        audit_records: list[ToolCallAuditRecord] = []
        tool_call_count = 0
        runtime_context = ToolRuntimeContext(
            conversation_id=request.conversation_id,
            subject=request.subject,
            launch_origin=request.launch_origin,
        )

        for step_index, step in enumerate(self.steps, start=1):
            if step.final_text is not None:
                return AgentResponse(
                    final_text=step.final_text,
                    tool_calls=tuple(audit_records),
                    metadata={"steps_executed": step_index, "tool_calls_executed": tool_call_count},
                )
            if step.tool_call is None:
                raise AgentLoopError(f"fake agent step {step_index} has neither final_text nor tool_call")

            if tool_call_count >= self.max_tool_calls:
                raise AgentLoopError(f"resident tool-call limit exceeded: {self.max_tool_calls}")
            tool_call_count += 1
            audit = await self._execute_tool_call(
                step.tool_call,
                tools,
                tool_call_count,
                _context_for_tool_call(runtime_context, f"fake_tool_{tool_call_count:04d}"),
            )
            audit_records.append(audit)
            handoff = _durable_launch_handoff_response(
                request=request,
                current_tool_calls=(audit,),
                all_tool_calls=audit_records,
                steps_executed=step_index,
            )
            if handoff is not None:
                return handoff

        raise AgentLoopError("fake agent script ended without final_text")

    async def _execute_tool_call(
        self,
        call: FakeToolCall,
        tools: ToolRegistry,
        sequence: int,
        runtime_context: ToolRuntimeContext,
    ) -> ToolCallAuditRecord:
        start = perf_counter()
        arguments = dict(call.arguments)
        tool_name = call.tool_name
        operation_kind = "read"
        try:
            registration = tools.get(call.tool_name)
            tool_name = registration.name
            operation_kind = registration.operation_kind
            tool_input = registration.input_model.model_validate(arguments)
            raw_result = await asyncio.wait_for(
                _run_tool_handler(registration.handler, tool_input, runtime_context),
                timeout=self.tool_timeout_s,
            )
            result_model = _coerce_tool_result(registration.output_model, raw_result)
            result_payload = result_model.model_dump(mode="json")
        except asyncio.TimeoutError:
            result_payload = {
                "ok": False,
                "message": f"tool timed out after {self.tool_timeout_s:g}s",
                "data": {"error": "timeout"},
            }
        except (ValidationError, Exception) as exc:
            result_payload = {
                "ok": False,
                "message": str(exc),
                "data": {"error": exc.__class__.__name__},
            }
        duration_ms = max(0, int((perf_counter() - start) * 1000))
        return ToolCallAuditRecord(
            id=f"fake_tool_{sequence:04d}",
            tool_name=tool_name,
            operation_kind=operation_kind,
            arguments=arguments,
            result=result_payload,
            duration_ms=duration_ms,
        )


class OpenAICompatibleAgentRunner(DispatchProtocol):
    """OpenAI-compatible chat/tool-call runner for live resident operation."""

    def __init__(
        self,
        config: ResidentConfig,
        *,
        max_tool_calls: int | None = None,
        tool_timeout_s: float | None = None,
        client_override: Any | None = None,
        model_override: str | None = None,
    ) -> None:
        self.config = config
        self.max_tool_calls = max_tool_calls or config.max_tool_calls_per_turn
        self.tool_timeout_s = tool_timeout_s or config.model_timeout_s
        self._client_override = client_override
        self._model_override = model_override
        if self.max_tool_calls <= 0:
            raise ValueError("max_tool_calls must be positive")
        if self.tool_timeout_s <= 0:
            raise ValueError("tool_timeout_s must be positive")

    async def run(self, request: AgentRequest, tools: ToolRegistry) -> AgentResponse:
        client = self._client_override or openai_client_from_config(self.config)
        messages = self._messages(request)
        openai_tools = [_openai_tool_schema(tool) for tool in tools.list()]
        audit_records: list[ToolCallAuditRecord] = []

        for step_index in range(1, self.max_tool_calls + 2):
            model_name = self._model_override or _request_model_name(request, self.config.model_name)
            # _pre_dispatch_budget_check sentinel: budget guard for dispatch
            try:
                render_step_message(StepInvocation(kind="model", metadata={
                    **request.model_seam_metadata,
                    "model": model_name,
                    "normalized_model": model_name,
                    "history": messages,
                    "tier": ModelTier.NON_ENFORCED.value,
                    "worker": "resident",
                }))
            except ModelBudgetError:
                raise
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    tools=openai_tools or None,
                    tool_choice="auto" if openai_tools else None,
                    timeout=self.config.model_timeout_s,
                ),
                timeout=self.config.model_timeout_s,
            )
            message = response.choices[0].message
            tool_calls = tuple(message.tool_calls or ())
            if not tool_calls:
                final_text = _message_content_text(message.content)
                return AgentResponse(
                    final_text=final_text,
                    tool_calls=tuple(audit_records),
                    metadata={"steps_executed": step_index, "tool_calls_executed": len(audit_records), "model": model_name},
                )
            if len(audit_records) + len(tool_calls) > self.max_tool_calls:
                raise AgentLoopError(f"resident tool-call limit exceeded: {self.max_tool_calls}")
            messages.append(_assistant_tool_call_message(message))
            current_audits: list[ToolCallAuditRecord] = []
            for tool_call in tool_calls:
                arguments = _tool_call_arguments(tool_call)
                audit = await execute_registered_tool(
                    tools=tools,
                    tool_name=tool_call.function.name,
                    arguments=arguments,
                    audit_id=tool_call.id,
                    timeout_s=self.tool_timeout_s,
                    runtime_context=ToolRuntimeContext(
                        conversation_id=request.conversation_id,
                        subject=request.subject,
                        launch_origin=_origin_for_tool_call(request.launch_origin, tool_call.id),
                        tool_call_id=tool_call.id,
                    ),
                )
                audit_records.append(audit)
                current_audits.append(audit)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(audit.result, sort_keys=True),
                    }
                )
            handoff = _durable_launch_handoff_response(
                request=request,
                current_tool_calls=current_audits,
                all_tool_calls=audit_records,
                steps_executed=step_index,
                model=model_name,
            )
            if handoff is not None:
                return handoff
        raise AgentLoopError("resident model loop ended without final_text")

    def _messages(self, request: AgentRequest) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [{"role": "system", "content": request.system_prompt}]
        if request.hot_context:
            current_request = request.hot_context.get("current_request")
            summary_line = (
                current_request.get("summary_line")
                if isinstance(current_request, Mapping)
                else None
            )
            messages.append(
                {
                    "role": "system",
                    "content": (
                        current_request_summary_line(
                            summary_line.removeprefix("Current request: ")
                            if isinstance(summary_line, str)
                            and summary_line.startswith("Current request: ")
                            else None
                        )
                        + "\nHot context JSON:\n"
                        + json.dumps(request.hot_context, sort_keys=True, default=str)
                    ),
                }
            )
        for message in request.messages:
            role = message.get("role")
            content = message.get("content")
            if role in {"user", "assistant", "system"} and isinstance(content, str):
                messages.append({"role": role, "content": content})
        return messages


class CodexCliAgentRunner(DispatchProtocol):
    """Resident runner backed by the local ``codex exec`` CLI and OAuth auth."""

    def __init__(
        self,
        config: ResidentConfig,
        *,
        cwd: str | Path,
        sandbox: str | None = None,
    ) -> None:
        self.config = config
        self.cwd = Path(cwd)
        self.sandbox = sandbox or config.codex_sandbox

    async def run(self, request: AgentRequest, tools: ToolRegistry) -> AgentResponse:
        model_name = _request_model_name(request, self.config.model_name)
        prompt = self._prompt(request, tools)
        with tempfile.NamedTemporaryFile(prefix="resident-codex-", suffix=".txt") as output:
            cmd = [
                "codex",
                "exec",
                "--model",
                model_name,
                "-c",
                f'model_reasoning_effort="{self.config.codex_reasoning_effort}"',
                "-c",
                'approval_policy="never"',
                "--sandbox",
                self.sandbox,
                "--skip-git-repo-check",
                "--output-last-message",
                output.name,
                "-C",
                str(self.cwd),
                "-",
            ]
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=environment_with_provenance(request.launch_origin),
                )
            except FileNotFoundError as exc:
                raise AgentLoopError("codex CLI is required for resident model_provider=codex") from exc
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(prompt.encode("utf-8")),
                    timeout=self.config.model_timeout_s,
                )
            except asyncio.TimeoutError as exc:
                proc.kill()
                await proc.wait()
                raise AgentLoopError(f"codex exec timed out after {self.config.model_timeout_s:g}s") from exc
            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")
            output.seek(0)
            final_text = output.read().decode("utf-8", errors="replace").strip()
        if proc.returncode != 0:
            detail = (stderr_text or stdout_text).strip()
            raise AgentLoopError(f"codex exec failed with exit {proc.returncode}: {detail[-2000:]}")
        if not final_text:
            final_text = _last_nonempty_line(stdout_text)
        return AgentResponse(
            final_text=final_text,
            tool_calls=(),
            metadata={
                "runner": "codex_cli",
                "model": model_name,
                "reasoning_effort": self.config.codex_reasoning_effort,
                "sandbox": self.sandbox,
            },
        )

    def _prompt(self, request: AgentRequest, tools: ToolRegistry) -> str:
        payload = {
            "hot_context": request.hot_context,
            "messages": request.messages,
            "launch_provenance": request.launch_origin,
            "available_resident_tools": tools.as_compact_catalog(),
        }
        prompt = (
            f"{request.system_prompt}\n\n"
            "You are running through the Codex CLI resident runner in the project repository. "
            "Use the local filesystem and Megaplan CLI for durable project actions. "
            "For initiatives, prefer `python -P -m arnold_pipelines.megaplan initiative ...`; "
            "initiative creation requires a non-empty description. The resident tool catalog below is "
            "reference material for equivalent CLI capabilities, not a set of callable Codex functions. "
            "For Discord reply ancestry older than the three ancestors preloaded in the current message, "
            "use only `python -P -m arnold_pipelines.megaplan resident read-reply-chain --cursor <cursor>`; "
            "it is store-backed and restricted by the immutable active conversation envelope. "
            "When native function exposure is absent and delegated work is required, use the supported "
            "local resident seam before replying: write the complete task to a file, then run "
            "`python -P -m arnold_pipelines.megaplan.resident.subagent launch --task-file <path> "
            "--task-kind <kind> --difficulty <D1-D10>`. Do not call a generic subagent launcher in its place. "
            "The `-P` isolation flag is mandatory: this resident may intentionally run from a pinned "
            "runtime source while its working directory contains another checkout, and importing from "
            "that checkout would split launch manifests from status and delivery. "
            "Immutable delegation provenance is injected into this process. Any resident-managed child "
            "launch must inherit it; never replace it with a recent conversation cursor, infer it from "
            "final text, or construct discord_origin manually. A malformed/ambiguous envelope must stop "
            "the launch. "
            "When cloud status is needed, use the configured cloud YAML from hot context. "
            "Keep final Discord replies concise. Messages are delivered to the user through Discord, "
            "so do not reference local filesystem paths or local-file links in user-facing replies; "
            "describe durable artifacts by run ID or human-readable name instead.\n\n"
            "Resident request JSON:\n"
            + json.dumps(payload, sort_keys=True, default=str)
        )
        if len(prompt) > self.config.max_prompt_chars:
            raise AgentPromptTooLargeError(
                "resident prompt exceeds the safe pre-dispatch budget: "
                f"{len(prompt)} > {self.config.max_prompt_chars} characters"
            )
        return prompt


class ManagedProviderCliAgentRunner(DispatchProtocol):
    """Provider-neutral, durable CLI runner for resident root turns.

    Resident conversation and turn records remain the control-plane truth.  In
    addition, every upstream invocation gets the same prompt/result/log/raw/
    manifest/event evidence contract used by resident-managed children.  A
    provider session is bound to the durable resident conversation and resumed
    only after a successful turn confirmed its identity.
    """

    _locks: dict[str, asyncio.Lock] = {}

    def __init__(
        self,
        config: ResidentConfig,
        *,
        cwd: str | Path,
        state_root: str | Path,
        codex_bin: str = "codex",
        hermes_launcher: str | Path | None = None,
        claude_launcher: str | Path | None = None,
    ) -> None:
        self.config = config
        self.cwd = Path(cwd).expanduser().resolve()
        self.state_root = Path(state_root).expanduser().resolve()
        launcher_root = Path(__file__).resolve().parents[1] / "skills" / "subagent-launcher"
        self.codex_bin = codex_bin
        self.hermes_launcher = Path(
            hermes_launcher or launcher_root / "launch_hermes_agent.py"
        )
        self.claude_launcher = Path(
            claude_launcher or launcher_root / "launch_claude_agent.py"
        )

    async def run(self, request: AgentRequest, tools: ToolRegistry) -> AgentResponse:
        lock_key = f"{self.state_root}:{request.conversation_id}"
        lock = self._locks.setdefault(lock_key, asyncio.Lock())
        async with lock:
            return await self._run_locked(request, tools)

    async def _run_locked(
        self, request: AgentRequest, tools: ToolRegistry
    ) -> AgentResponse:
        route = resolve_managed_agent_route(
            backend=self.config.model_provider,
            model=self.config.model_name,
            default_backend=self.config.model_provider,
        )
        if route.backend not in MANAGED_AGENT_BACKENDS:
            raise AgentLoopError(
                f"resident provider {route.backend!r} has no managed CLI adapter"
            )
        contract = provider_execution_contract(
            backend=route.backend,
            toolsets=self.config.model_toolsets,
            max_tokens=self.config.model_max_tokens,
            timeout_s=self.config.model_timeout_s,
        )
        prompt = self._prompt(request, tools, route.backend)
        paths = self._new_run_paths(request.conversation_id)
        for path in paths.values():
            if path.suffix:
                path.parent.mkdir(parents=True, exist_ok=True)
        paths["prompt"].write_text(prompt, encoding="utf-8")
        for name in ("result", "log", "raw", "events", "metadata"):
            paths[name].touch()

        session_path = self._session_path(request.conversation_id)
        prior_session = _read_json_object(session_path)
        resumable = bool(
            prior_session
            and prior_session.get("provider") == route.backend
            and prior_session.get("model") == route.model
            and prior_session.get("state") == "persisted"
            and prior_session.get("session_id")
        )
        session_id = (
            str(prior_session["session_id"])
            if resumable
            else reserve_session_id(route.backend)
        )
        now = _utc_timestamp()
        manifest = {
            "schema_version": "arnold-resident-provider-turn-v1",
            "run_id": paths["run_dir"].name,
            "conversation_id": request.conversation_id,
            "resident_turn_id": request.turn_id,
            "provider": route.backend,
            "model": route.model,
            "model_spec": route.model_spec,
            "status": "launching",
            "created_at": now,
            "updated_at": now,
            "prompt_path": str(paths["prompt"]),
            "result_path": str(paths["result"]),
            "log_path": str(paths["log"]),
            "provider_raw_output_path": str(paths["raw"]),
            "provider_events_path": str(paths["events"]),
            "provider_metadata_path": str(paths["metadata"]),
            "provider_contract": contract,
            "model_session": {
                "provider": route.backend,
                "session_id": session_id,
                "state": "continuing" if resumable else "reserved",
                "persistence": "durable" if resumable else "requested_unconfirmed",
                "resume_semantics": "exact_session",
            },
            "session_dispatch": {
                "mode": "resume" if resumable else "new",
                "session_id": session_id,
            },
            "telemetry": {
                "schema_version": "arnold-managed-provider-telemetry-v1",
                "raw_output_path": str(paths["raw"]),
                "normalized_events_path": str(paths["events"]),
                "raw_stream_equivalence": "provider_specific_not_byte_identical",
            },
            "status_history": [{"status": "launching", "at": now}],
        }
        _atomic_json_file(paths["manifest"], manifest)
        if session_id and not resumable:
            _atomic_json_file(
                session_path,
                {
                    "schema_version": "arnold-resident-provider-session-v1",
                    "conversation_id": request.conversation_id,
                    "provider": route.backend,
                    "model": route.model,
                    "session_id": session_id,
                    "state": "reserved_unconfirmed",
                    "updated_at": now,
                    "last_run_id": manifest["run_id"],
                },
            )

        try:
            argv, stdin_payload, provider_env = self._command(
                backend=route.backend,
                model=route.model,
                effort=route.effort,
                paths=paths,
                session_id=session_id,
                resume=resumable,
            )
        except Exception as exc:
            paths["log"].write_text(
                f"provider command construction failed: {exc.__class__.__name__}: {exc}\n",
                encoding="utf-8",
            )
            evidence = collect_provider_evidence(
                backend=route.backend,
                raw_output_path=paths["raw"],
                metadata_path=paths["metadata"],
                expected_session_id=session_id,
                returncode=127,
                diagnostics_path=paths["log"],
            )
            write_normalized_events(paths["events"], evidence.events)
            manifest["telemetry"].update(
                {
                    "status": "captured",
                    "normalized_event_count": len(evidence.events),
                    "usage": dict(evidence.usage),
                }
            )
            manifest = self._terminal_manifest(
                manifest,
                status="failed",
                returncode=127,
                failure_category="provider_command_invalid",
                failure_message=str(exc),
            )
            _atomic_json_file(paths["manifest"], manifest)
            if isinstance(exc, AgentLoopError):
                raise
            raise AgentLoopError(str(exc)) from exc
        manifest["status"] = "running"
        manifest["started_at"] = _utc_timestamp()
        manifest["updated_at"] = manifest["started_at"]
        manifest["status_history"].append(
            {"status": "running", "at": manifest["started_at"]}
        )
        _atomic_json_file(paths["manifest"], manifest)

        returncode = 1
        with paths["raw"].open("wb") as raw_handle, paths["log"].open("ab") as log_handle:
            log_handle.write(
                (
                    json.dumps(
                        {
                            "event": "provider.process.started",
                            "provider": route.backend,
                            "model": route.model,
                            "resume": resumable,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                ).encode("utf-8")
            )
            try:
                proc = await asyncio.create_subprocess_exec(
                    *argv,
                    stdin=(
                        asyncio.subprocess.PIPE
                        if stdin_payload is not None
                        else asyncio.subprocess.DEVNULL
                    ),
                    stdout=raw_handle,
                    stderr=log_handle,
                    cwd=str(self.cwd),
                    env=environment_with_provenance(
                        request.launch_origin, base=provider_env
                    ),
                    start_new_session=True,
                )
            except FileNotFoundError as exc:
                evidence = collect_provider_evidence(
                    backend=route.backend,
                    raw_output_path=paths["raw"],
                    metadata_path=paths["metadata"],
                    expected_session_id=session_id,
                    returncode=127,
                    diagnostics_path=paths["log"],
                )
                write_normalized_events(paths["events"], evidence.events)
                manifest["telemetry"].update(
                    {
                        "status": "captured",
                        "normalized_event_count": len(evidence.events),
                        "usage": dict(evidence.usage),
                    }
                )
                manifest = self._terminal_manifest(
                    manifest,
                    status="failed",
                    returncode=127,
                    failure_category="provider_cli_missing",
                    failure_message=str(exc),
                )
                _atomic_json_file(paths["manifest"], manifest)
                raise AgentLoopError(str(exc)) from exc
            accepted_at = _utc_timestamp()
            manifest["worker_pid"] = proc.pid
            manifest["session_dispatch"].update(
                {
                    "status": "accepted",
                    "accepted_at": accepted_at,
                    "evidence": f"{route.backend}_provider_process_started",
                }
            )
            _atomic_json_file(paths["manifest"], manifest)
            try:
                await asyncio.wait_for(
                    proc.communicate(
                        stdin_payload.encode("utf-8")
                        if stdin_payload is not None
                        else None
                    ),
                    timeout=self.config.model_timeout_s,
                )
                returncode = int(proc.returncode or 0)
            except asyncio.TimeoutError:
                await _terminate_process_group(proc)
                returncode = 124

        _append_raw_log(paths["log"], paths["raw"], route.backend)
        evidence = collect_provider_evidence(
            backend=route.backend,
            raw_output_path=paths["raw"],
            metadata_path=paths["metadata"],
            expected_session_id=session_id,
            returncode=returncode,
            diagnostics_path=paths["log"],
        )
        write_normalized_events(paths["events"], evidence.events)
        final_text = evidence.final_text
        if route.backend == "codex":
            final_text = paths["result"].read_text(
                encoding="utf-8", errors="replace"
            ).strip() or None
        elif final_text:
            paths["result"].write_text(final_text.rstrip() + "\n", encoding="utf-8")

        resolved_session_id = evidence.session_id
        if route.backend == "hermes" and resumable:
            # The exact handle passed to Hermes is already proven resumable.
            # Some Hermes versions return a different internal session id in
            # metadata after compaction; persisting that value bricks the next
            # turn even though this one completed successfully.
            resolved_session_id = session_id
        failure_category = evidence.failure_category
        failure_message = evidence.failure_message
        if returncode == 0 and not resolved_session_id:
            returncode = 1
            failure_category = "session_identity_missing"
            failure_message = "provider completed without a recoverable session identity"
        if returncode == 0 and not final_text:
            returncode = 1
            failure_category = "empty_result"
            failure_message = "provider completed without a final response"

        if returncode == 0:
            assert resolved_session_id is not None
            _atomic_json_file(
                session_path,
                {
                    "schema_version": "arnold-resident-provider-session-v1",
                    "conversation_id": request.conversation_id,
                    "provider": route.backend,
                    "model": route.model,
                    "session_id": resolved_session_id,
                    "state": "persisted",
                    "persistence": "durable",
                    "resume_semantics": "exact_session",
                    "updated_at": _utc_timestamp(),
                    "last_run_id": manifest["run_id"],
                },
            )
            manifest["model_session"] = {
                "provider": route.backend,
                "session_id": resolved_session_id,
                "state": "persisted",
                "persistence": "durable",
                "resume_semantics": "exact_session",
            }
            manifest["session_dispatch"]["session_id"] = resolved_session_id
            manifest["telemetry"].update(
                {
                    "status": "captured",
                    "normalized_event_count": len(evidence.events),
                    "usage": dict(evidence.usage),
                }
            )
            manifest = self._terminal_manifest(
                manifest, status="completed", returncode=0
            )
            _atomic_json_file(paths["manifest"], manifest)
            return AgentResponse(
                final_text=str(final_text),
                tool_calls=(),
                metadata={
                    "runner": "managed_provider_cli",
                    "provider": route.backend,
                    "model": route.model,
                    "session_id": resolved_session_id,
                    "session_mode": "resume" if resumable else "new",
                    "run_id": manifest["run_id"],
                    "manifest_path": str(paths["manifest"]),
                    "telemetry": dict(manifest["telemetry"]),
                },
            )

        missing_resume_session = (
            route.backend == "hermes"
            and resumable
            and _hermes_resume_session_missing(
                log_path=paths["log"],
                raw_path=paths["raw"],
                metadata_path=paths["metadata"],
                returncode=returncode,
            )
        )
        if missing_resume_session:
            quarantine_path = self._quarantine_session_path(session_path)
            manifest["model_session"] = {
                "provider": route.backend,
                "session_id": session_id,
                "state": "quarantined",
                "persistence": "invalidated_after_missing_resume",
                "resume_semantics": "fresh_retry_required",
            }
            manifest["recovery"] = {
                "strategy": "quarantine_missing_resume_and_retry_fresh",
                "quarantine_path": str(quarantine_path),
                "retry_replays_turn": False,
            }
            manifest["telemetry"].update(
                {
                    "status": "captured",
                    "normalized_event_count": len(evidence.events),
                    "usage": dict(evidence.usage),
                }
            )
            manifest = self._terminal_manifest(
                manifest,
                status="failed",
                returncode=returncode,
                failure_category="resume_session_missing",
                failure_message="Hermes could not resolve the persisted resume session",
            )
            _atomic_json_file(paths["manifest"], manifest)
            # Retry inside the same resident turn.  The quarantined binding
            # makes the recursive dispatch mode=new, so it cannot loop and no
            # inbound message or durable turn is replayed.
            return await self._run_locked(request, tools)

        manifest["model_session"] = (
            {
                "provider": route.backend,
                "session_id": session_id,
                "state": "persisted",
                "persistence": "durable_prior_turn",
                "resume_semantics": "exact_session",
                "last_dispatch": "failed",
            }
            if resumable
            else {
                "provider": route.backend,
                "session_id": resolved_session_id or session_id,
                "state": "reserved_unconfirmed",
                "persistence": "requested_unconfirmed",
                "resume_semantics": "unavailable_until_successfully_confirmed",
            }
        )
        manifest["telemetry"].update(
            {
                "status": "captured",
                "normalized_event_count": len(evidence.events),
                "usage": dict(evidence.usage),
            }
        )
        manifest = self._terminal_manifest(
            manifest,
            status="failed",
            returncode=returncode,
            failure_category=failure_category or "provider_error",
            failure_message=failure_message or f"provider exited with status {returncode}",
        )
        _atomic_json_file(paths["manifest"], manifest)
        raise AgentLoopError(
            f"{route.backend} resident turn failed: "
            f"{manifest['failure']['category']}: {manifest['failure']['message']}"
        )

    def _command(
        self,
        *,
        backend: str,
        model: str,
        effort: str | None,
        paths: dict[str, Path],
        session_id: str | None,
        resume: bool,
    ) -> tuple[list[str], str | None, dict[str, str]]:
        env = os.environ.copy()
        if backend == "codex":
            if resume:
                argv = [
                    self.codex_bin,
                    "exec",
                    "resume",
                    "--json",
                    "--skip-git-repo-check",
                    "-m",
                    model,
                    "-c",
                    f'model_reasoning_effort="{effort or self.config.codex_reasoning_effort}"',
                    "-c",
                    f'sandbox_mode="{self.config.codex_sandbox}"',
                    "-c",
                    'approval_policy="never"',
                    "--output-last-message",
                    str(paths["result"]),
                    str(session_id),
                    "-",
                ]
            else:
                argv = [
                    self.codex_bin,
                    "exec",
                    "--json",
                    "--skip-git-repo-check",
                    "--sandbox",
                    self.config.codex_sandbox,
                    "-m",
                    model,
                    "-c",
                    f'model_reasoning_effort="{effort or self.config.codex_reasoning_effort}"',
                    "-c",
                    'approval_policy="never"',
                    "--output-last-message",
                    str(paths["result"]),
                    "-",
                ]
            return argv, paths["prompt"].read_text(encoding="utf-8"), env
        if backend == "hermes":
            if not self.hermes_launcher.exists():
                raise AgentLoopError(f"Hermes launcher not found: {self.hermes_launcher}")
            argv = [
                sys.executable,
                str(self.hermes_launcher),
                "--model",
                model,
                "--toolsets",
                self.config.model_toolsets,
                "--max-tokens",
                str(self.config.model_max_tokens),
                "--project-dir",
                str(self.cwd),
                "--query-file",
                str(paths["prompt"]),
                "--session-id",
                str(session_id),
                "--metadata-file",
                str(paths["metadata"]),
            ]
            if resume:
                argv.append("--resume-session")
            return argv, None, env
        if backend == "claude":
            if not self.claude_launcher.exists():
                raise AgentLoopError(f"Claude launcher not found: {self.claude_launcher}")
            toolsets = normalize_toolsets(self.config.model_toolsets)
            argv = [
                sys.executable,
                str(self.claude_launcher),
                "--model",
                model,
                "--project-dir",
                str(self.cwd),
                "--query-file",
                str(paths["prompt"]),
                "--timeout",
                str(self.config.model_timeout_s),
                "--output-format",
                "stream-json",
                "--verbose",
                "--tools",
                claude_tools_for(toolsets),
            ]
            argv += ["--resume" if resume else "--session-id", str(session_id)]
            if hasattr(os, "geteuid") and os.geteuid() == 0:
                argv += ["--permission-mode", "auto"]
            else:
                argv.append("--dangerously-skip-permissions")
            if effort in {"low", "medium", "high", "xhigh", "max"}:
                argv += ["--effort", effort]
            env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(self.config.model_max_tokens)
            return argv, None, env
        raise AgentLoopError(f"unsupported resident provider: {backend}")

    def _prompt(
        self, request: AgentRequest, tools: ToolRegistry, backend: str
    ) -> str:
        payload = {
            "hot_context": request.hot_context,
            "messages": request.messages,
            "launch_provenance": request.launch_origin,
            "available_resident_tools": tools.as_compact_catalog(),
        }
        prompt = (
            f"{request.system_prompt}\n\n"
            f"You are the resident agent running through the managed {backend} provider adapter. "
            "Use the local filesystem and Megaplan CLI for durable project actions. The resident "
            "tool catalog is reference material for equivalent CLI capabilities, not callable "
            "provider functions. For older Discord reply ancestry, use only "
            "`python -P -m arnold_pipelines.megaplan resident read-reply-chain --cursor <cursor>`. "
            "For delegated work, use only `python -P -m "
            "arnold_pipelines.megaplan.resident.subagent launch --task-file <path> --task-kind "
            "<kind> --difficulty <D1-D10>`. The `-P` isolation flag is mandatory. Immutable "
            "delegation provenance is injected into the provider process; never reconstruct or "
            "replace it. Keep final Discord replies concise and do not expose local file paths.\n\n"
            "Resident request JSON:\n"
            + json.dumps(payload, sort_keys=True, default=str)
        )
        if len(prompt) > self.config.max_prompt_chars:
            raise AgentPromptTooLargeError(
                "resident prompt exceeds the safe pre-dispatch budget: "
                f"{len(prompt)} > {self.config.max_prompt_chars} characters"
            )
        return prompt

    def _new_run_paths(self, conversation_id: str) -> dict[str, Path]:
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        run_id = f"resident-provider-{stamp}-{uuid.uuid4().hex[:8]}"
        conversation_key = hashlib.sha256(conversation_id.encode("utf-8")).hexdigest()[:20]
        run_dir = self.state_root / "provider_runs" / conversation_key / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        return {
            "run_dir": run_dir,
            "prompt": run_dir / "prompt.md",
            "result": run_dir / "result.md",
            "log": run_dir / "run.log",
            "raw": run_dir / "provider.raw",
            "events": run_dir / "events.jsonl",
            "metadata": run_dir / "provider-metadata.json",
            "manifest": run_dir / "manifest.json",
        }

    def _session_path(self, conversation_id: str) -> Path:
        digest = hashlib.sha256(conversation_id.encode("utf-8")).hexdigest()
        path = self.state_root / "provider_sessions" / f"{digest}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _quarantine_session_path(session_path: Path) -> Path:
        quarantine_dir = session_path.parent / "quarantine"
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        quarantine_path = quarantine_dir / f"{session_path.stem}.stale-{stamp}.json"
        try:
            session_path.replace(quarantine_path)
        except FileNotFoundError as exc:
            raise AgentLoopError(
                "persisted Hermes session binding disappeared during recovery"
            ) from exc
        return quarantine_path

    @staticmethod
    def _terminal_manifest(
        manifest: dict[str, Any],
        *,
        status: str,
        returncode: int,
        failure_category: str | None = None,
        failure_message: str | None = None,
    ) -> dict[str, Any]:
        finished = _utc_timestamp()
        manifest.update(
            {
                "status": status,
                "returncode": returncode,
                "terminal_outcome": status,
                "finished_at": finished,
                "updated_at": finished,
            }
        )
        manifest.setdefault("status_history", []).append(
            {"status": status, "at": finished}
        )
        if failure_category:
            manifest["failure"] = {
                "category": failure_category,
                "message": failure_message,
                "returncode": returncode,
                "captured_at": finished,
            }
        return manifest


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _read_json_object(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _atomic_json_file(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _hermes_resume_session_missing(
    *,
    log_path: Path,
    raw_path: Path,
    metadata_path: Path,
    returncode: int,
) -> bool:
    # Exit 8 is emitted by the launcher before model construction when
    # SessionDB cannot resolve the requested resume handle.  Never retry after
    # ambiguous provider failures: doing so could repeat tool side effects.
    if returncode != 8:
        return False
    try:
        if raw_path.stat().st_size or metadata_path.stat().st_size:
            return False
    except OSError:
        return False
    try:
        diagnostics = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return any(
        line.startswith("error: Hermes session ") and line.endswith(" does not exist")
        for line in diagnostics.splitlines()
    )


def _append_raw_log(log_path: Path, raw_path: Path, backend: str) -> None:
    with log_path.open("ab") as target:
        target.write(
            f"\n[resident-provider-raw begin backend={backend} path={raw_path}]\n".encode()
        )
        try:
            target.write(raw_path.read_bytes())
        except OSError as exc:
            target.write(f"[raw unavailable: {exc.__class__.__name__}]".encode())
        target.write(f"\n[resident-provider-raw end backend={backend}]\n".encode())


async def _terminate_process_group(proc: asyncio.subprocess.Process) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        await asyncio.wait_for(proc.wait(), timeout=5.0)
        return
    except asyncio.TimeoutError:
        pass
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    await proc.wait()


async def _await_maybe(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value


def _origin_for_tool_call(
    origin: Mapping[str, Any] | None,
    tool_call_id: str,
) -> Mapping[str, Any] | None:
    if origin is None:
        return None
    return {**dict(origin), "delegation_id": tool_call_id}


def _context_for_tool_call(
    context: ToolRuntimeContext,
    tool_call_id: str,
) -> ToolRuntimeContext:
    return ToolRuntimeContext(
        conversation_id=context.conversation_id,
        subject=context.subject,
        launch_origin=_origin_for_tool_call(context.launch_origin, tool_call_id),
        tool_call_id=tool_call_id,
    )


async def _run_tool_handler(handler: Any, tool_input: Any, runtime_context: ToolRuntimeContext) -> Any:
    token = _TOOL_RUNTIME_CONTEXT.set(runtime_context)
    try:
        return await _await_maybe(handler(tool_input))
    finally:
        _TOOL_RUNTIME_CONTEXT.reset(token)


def _coerce_tool_result(output_model: type[BaseModel], value: Any) -> BaseModel:
    if isinstance(value, output_model):
        return value
    if isinstance(value, ToolResult) and output_model is not ToolResult:
        return output_model.model_validate(value.model_dump(mode="python"))
    if isinstance(value, BaseModel):
        return output_model.model_validate(value.model_dump(mode="python"))
    return output_model.model_validate(value)


def _request_model_name(request: AgentRequest, default: str) -> str:
    model_name = request.model_seam_metadata.get("normalized_model")
    return str(model_name) if model_name else default


async def execute_registered_tool(
    *,
    tools: ToolRegistry,
    tool_name: str,
    arguments: dict[str, Any],
    audit_id: str,
    timeout_s: float,
    runtime_context: ToolRuntimeContext,
) -> ToolCallAuditRecord:
    start = perf_counter()
    operation_kind = "read"
    try:
        registration = tools.get(tool_name)
        tool_name = registration.name
        operation_kind = registration.operation_kind
        tool_input = registration.input_model.model_validate(arguments)
        raw_result = await asyncio.wait_for(
            _run_tool_handler(registration.handler, tool_input, runtime_context),
            timeout=timeout_s,
        )
        result_model = _coerce_tool_result(registration.output_model, raw_result)
        result_payload = result_model.model_dump(mode="json")
    except asyncio.TimeoutError:
        result_payload = {
            "ok": False,
            "message": f"tool timed out after {timeout_s:g}s",
            "data": {"error": "timeout"},
        }
    except (ValidationError, Exception) as exc:
        result_payload = {
            "ok": False,
            "message": str(exc),
            "data": {"error": exc.__class__.__name__},
        }
    duration_ms = max(0, int((perf_counter() - start) * 1000))
    return ToolCallAuditRecord(
        id=audit_id,
        tool_name=tool_name,
        operation_kind=operation_kind,
        arguments=arguments,
        result=result_payload,
        duration_ms=duration_ms,
    )


_execute_registered_tool = execute_registered_tool


def openai_client_from_config(config: ResidentConfig) -> Any:
    """Build an API client from the resident's configured endpoint and credentials."""

    return openai_client_for_endpoint(
        credential_env=api_credential_env(config),
        base_url=api_base_url(config),
    )


def openai_client_for_endpoint(
    *,
    credential_env: str,
    base_url: str | None = None,
    timeout_s: float | None = None,
) -> Any:
    """Build an OpenAI-compatible client without coupling it to the chat provider."""

    try:
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise AgentLoopError("The openai package is required for resident API calls") from exc
    api_key = os.getenv(credential_env)
    if not api_key:
        raise ResidentCredentialError(credential_env)
    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    if timeout_s is not None:
        kwargs["timeout"] = timeout_s
        # The resident owns the outer timeout and user-facing fallback. Avoid
        # SDK retries extending a failed voice-note request beyond that bound.
        kwargs["max_retries"] = 0
    return AsyncOpenAI(**kwargs)


# Backward-compatible private alias for internal callers that predate the
# transcription path.
_openai_client = openai_client_from_config


def _api_key(config: ResidentConfig) -> str:
    env_name = api_credential_env(config)
    value = os.getenv(env_name)
    if not value:
        raise ResidentCredentialError(env_name)
    return value


def api_credential_env(config: ResidentConfig) -> str:
    """Return the selected API-key environment variable without reading its value."""

    return config.model_api_key_env or _default_api_key_env(config.model_provider)


def _default_api_key_env(provider: str) -> str:
    return "OPENROUTER_API_KEY" if provider == "openrouter" else "OPENAI_API_KEY"


def _base_url(config: ResidentConfig) -> str | None:
    if config.model_base_url:
        return config.model_base_url
    if config.model_provider == "openrouter":
        return "https://openrouter.ai/api/v1"
    return None


def api_base_url(config: ResidentConfig) -> str | None:
    """Return the selected OpenAI-compatible base URL, if explicitly configured."""

    return _base_url(config)


def _client_for_model(model_name: str) -> tuple[Any, str]:
    """Build an OpenAI-compatible client for an arbitrary provider-prefixed model.

    Uses the shared key pool resolver so a subagent can run on a different
    provider than the resident without env-var coupling. Returns the client and
    the normalized model id to send in requests.
    """
    from arnold_pipelines.megaplan.runtime.key_pool import resolve_model

    try:
        normalized_model, agent_kwargs = resolve_model(model_name)
    except Exception as exc:  # pragma: no cover - surfaced to the tool caller
        raise AgentLoopError(f"could not resolve subagent model {model_name!r}: {exc}") from exc
    try:
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise AgentLoopError("The openai package is required for live resident model turns") from exc
    client_kwargs: dict[str, Any] = {"api_key": agent_kwargs.get("api_key") or os.getenv("OPENAI_API_KEY")}
    base_url = agent_kwargs.get("base_url")
    if base_url:
        client_kwargs["base_url"] = base_url
    return AsyncOpenAI(**client_kwargs), normalized_model


def _openai_tool_schema(registration: Any) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": registration.name,
            "description": registration.description,
            "parameters": registration.input_model.model_json_schema(),
        },
    }


_DURABLE_LAUNCH_STATUSES = frozenset({"launching", "running", "completed"})


def _durable_launch_run_id(record: ToolCallAuditRecord) -> str | None:
    if record.tool_name not in {"launch_subagent", "fix_the_fixer"}:
        return None
    result = record.result if isinstance(record.result, dict) else {}
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    run_id = str(data.get("run_id") or "").strip()
    status = str(data.get("status") or "").strip()
    if result.get("ok") is True and run_id and status in _DURABLE_LAUNCH_STATUSES:
        return run_id
    return None


def durable_launch_run_ids(
    tool_calls: list[ToolCallAuditRecord] | tuple[ToolCallAuditRecord, ...],
) -> tuple[str, ...]:
    """Return successful managed run ids without consulting mutable manifests."""

    run_ids: list[str] = []
    for record in tool_calls:
        run_id = _durable_launch_run_id(record)
        if run_id is not None:
            run_ids.append(run_id)
    return tuple(dict.fromkeys(run_ids))


def _durable_launch_handoff_response(
    *,
    request: AgentRequest,
    current_tool_calls: list[ToolCallAuditRecord] | tuple[ToolCallAuditRecord, ...],
    all_tool_calls: list[ToolCallAuditRecord] | tuple[ToolCallAuditRecord, ...],
    steps_executed: int,
    model: str | None = None,
) -> AgentResponse | None:
    """End a Discord turn once its remaining work has durable agent custody.

    The policy is deliberately based on the registered tool result and the
    immutable request launch envelope.  It never reads or reconstructs a
    Discord reply target.  Mixed tool batches, launch failures, and an explicit
    ``continue_turn`` request retain control for same-turn work.
    """

    origin = request.launch_origin
    if not isinstance(origin, Mapping) or origin.get("applicability") != "applicable":
        return None
    if not current_tool_calls or any(
        record.tool_name not in {"launch_subagent", "fix_the_fixer"}
        for record in current_tool_calls
    ):
        return None
    if any(bool(record.arguments.get("continue_turn")) for record in current_tool_calls):
        return None
    if any(_durable_launch_run_id(record) is None for record in current_tool_calls):
        # A failed, synchronous, or malformed launch needs an ordinary resident
        # follow-up; never hide it behind a success acknowledgement.
        return None
    run_ids = durable_launch_run_ids(tuple(all_tool_calls))
    launch_lines: list[str] = []
    for record in all_tool_calls:
        run_id = _durable_launch_run_id(record)
        if run_id is None or run_id not in run_ids:
            continue
        result = record.result if isinstance(record.result, dict) else {}
        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        description = str(
            data.get("description") or record.arguments.get("description") or ""
        ).strip()
        role = str(
            record.arguments.get("aggregation_role") or "synthesis_delivery_owner"
        ).replace("_", " ")
        launch_lines.append(
            f"`{run_id}` ({role}) — {description}"
            if description
            else f"`{run_id}` ({role})"
        )
    rendered_ids = "; ".join(launch_lines)
    noun = "run" if len(run_ids) == 1 else "runs"
    roles = [
        str(record.arguments.get("aggregation_role") or "synthesis_delivery_owner")
        for record in all_tool_calls
        if _durable_launch_run_id(record) in run_ids
    ]
    owner_count = sum(role == "synthesis_delivery_owner" for role in roles)
    delivery_sentence = (
        "One synthesis owner will consolidate terminal results and reply automatically to this message."
        if owner_count == 1
        else "Each independently deliverable run will reply automatically to this message."
    )
    metadata: dict[str, Any] = {
        "steps_executed": steps_executed,
        "tool_calls_executed": len(all_tool_calls),
        "turn_handoff": "durable_subagents",
        "launched_run_ids": list(run_ids),
    }
    if model:
        metadata["model"] = model
    return AgentResponse(
        final_text=(
            f"Launched resident-managed {noun} {rendered_ids}. {delivery_sentence}"
        ),
        tool_calls=tuple(all_tool_calls),
        metadata=metadata,
    )


def _message_content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    if isinstance(content, list):
        return "\n".join(str(part.get("text", part)) if isinstance(part, dict) else str(part) for part in content)
    return str(content)


def _assistant_tool_call_message(message: Any) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": _message_content_text(message.content) or None,
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                },
            }
            for call in (message.tool_calls or ())
        ],
    }


def _tool_call_arguments(tool_call: Any) -> dict[str, Any]:
    raw = tool_call.function.arguments or "{}"
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise AgentLoopError(f"tool call {tool_call.id} arguments must be a JSON object")
    return parsed


def _last_nonempty_line(text: str) -> str:
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if stripped:
            return stripped
    return ""
