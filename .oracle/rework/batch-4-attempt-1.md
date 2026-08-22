Reading additional input from stdin...
2026-08-21T21:57:58.186487Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-21T21:57:58.186522Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-21T21:57:58.186530Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.148.0
--------
workdir: /Users/peteromalley/Documents/arnold-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: danger-full-access
reasoning effort: high
reasoning summaries: none
session id: 01a02654-aa06-7191-8f6b-6bda54121396
--------
user
# Batch 4 rework triage — GPT-5.6 Sol (oracle)

> DELEGATION MANDATE — You are a manager and validator of the normal execution pool, NOT a worker. Direct, then validate.

Worktree: `/Users/peteromalley/Documents/arnold-oracle`. Read `.oracle/checkins/batch-4-review.txt` (1 blocking finding with fix), `.oracle/tasklist.md` (Batch 4), delta `git diff f3bdcb9635..42f86de734`, and `resident/cli.py` `_resident_profile` (~1362-1369).

Judge the finding and emit `.oracle/rework/batch-4-attempt-1.md` (I save it): finding + evidence, affected criterion + North Star principle, required outcome + scope, classification + rationale, selected model, acceptance + exact validation. The reviewer's fix: default `CloudCliBackend()` assigned to AgentBox/external profile instances in `_resident_profile()` post-construction (attribute assignment), preserving the 4-arg external constructor contract and explicit-None clear-failure semantics. Confirm whether `CloudCliBackend()` is cheap/safe to construct unconditionally (check its import and constructor). Normal → Luna unless cross-cutting. Under 350 words, verbatim emit.
codex
I’m using the repository’s context-minimizing delegation guidance because you explicitly require me to direct and validate, not perform the investigation myself. I’ll delegate the evidence gathering, then independently validate the returned claims before emitting only the requested triage note.
exec
/bin/zsh -lc "sed -n '1,240p' /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md" in /Users/peteromalley/Documents/arnold-oracle
 succeeded in 0ms:
---
name: contextminning-subagentmaxxing
description: >
  Keep the main-thread context as lean as possible while working. Two moves: (1)
  context minning — after each turn, look for a natural break-off point to condense,
  save state to markdown, and compact - write .md docs to make sure you don't lose 
  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
  a subagent (especially the DeepSeek/Kimi agents via subagent-launcher) should research,
  validate, or execute it so the verbose work never lands in your context. Use on 
  any long, multi-step, or research-heavy task.
---

# Context Minning & Subagent Maxxing

The goal of this skill is singular: **keep the actual work in the main thread's
context as small as possible.** Long contexts get slow, expensive, and forgetful.
Every turn, the most useful tokens should be present and the rest should be
elsewhere — in a file, in a summary, or in a subagent that already finished.

It runs as two continuous moves — a posture, not a one-time cleanup. This file is the
philosophy and the high level; each move has a standalone skill with the mechanics,
syntax, and anti-patterns. **Invoke those for the how.**

---

## Move 1 — Context minning: condense at the seams

When a chunk of work becomes *done and durable* — a plan spec'd out, a bug
root-caused, a long read distilled to one answer — the path to that conclusion is dead
weight. At those seams: **write the conclusion to a durable artifact, then compact from
there.** Prefer landing real work as a megaplan asset (plan file or ticket) over a loose
note, so what you shed becomes trackable work rather than vanishing.

The discipline is *write it down first* — you can only safely forget what you can
re-read. And don't over-do it: compact at seams, never on a timer; a slightly long
context costs less than a lost decision.

→ **`minimize-context`** for the seam catalogue, the `/compact` · `/clear` · `/context`
mechanics, megaplan-asset detail, and the over-minning failure mode.

→ **`context-usage`** to *see* the context filling: a turn-by-turn token-growth chart
read from the session transcript, with every compaction boundary marked. Use it to
check whether you're minning at the right seams or letting context balloon to
auto-compaction. (`/context` is the live snapshot; `context-usage` is the trajectory.)

## Move 2 — Subagent maxxing: do the work elsewhere

**Default to doing work in a subagent, not the thread.** Flip the question from "should
a subagent do this?" to "is there any reason this *can't*?" Its tool calls, file reads,
and reasoning stay in *its* context; only the conclusion returns to you. **Execution is
the headline case** — implementing, investigating, building is where byproduct piles up,
so it's the first thing to hand off, not the last. Be willing to launch **many**, even
in parallel, until you have clarity — that's cheaper than carrying the trail inline.

Two principles carry most of the value: spend the subagent on the *byproduct-heavy*
part and ask it to **return the conclusion, not the trail**; and **use the cheapest
model that can do the job** (cheap scan-work → reasoning → frontier only for real
complexity), preparing the context well enough that a cheaper tier can win. Don't
dispatch if you already have the answer.

**Match the venue to the scale.** A one-shot subagent dispatch is for ad-hoc work —
research, a sense-check, a contained fix. Once something is more than ~a day or two of
work it's a *deliverable*: run it as a **megaplan** (itself launched in a subagent) and
use **`megaplan-decision`** to size the tier/robustness/depth. Past ~2 weeks → an epic.

→ **`subagent-launcher`** for the pathways, the cost-escalation ladder with model
identifiers, and how to shape a self-contained subagent prompt.

---

## The loop, in one line

Every turn: *Did I just hit a seam? → write it down, compact. Am I about to do real
work? → hand it to a subagent.* Keep the main thread holding only what the next
decision needs.

2026-08-21T21:58:15.434586Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-21T21:58:15.434742Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-21T21:58:15.434750Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-21T21:58:19.326241Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-21T21:58:19.326265Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-21T21:58:19.326271Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-21T21:58:23.538366Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-21T21:58:23.538447Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-21T21:58:23.538453Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
codex
Three Luna workers are now checking the finding from separate angles: requirement/diff alignment, constructor safety, and independent acceptance criteria. I’ll reconcile any disagreement and verify the decisive evidence directly.
collab: Wait
collab: Wait
codex
The workers agree on the defect, fix shape, and constructor safety. The only meaningful judgment call is classification: although the code change is tiny, Batch 4 explicitly frames this inherited constructor/factory seam as XHARD and it spans built-in plus external profiles, so I’m validating that as cross-cutting before choosing Sol.
exec
/bin/zsh -lc "sed -n '1,220p' .oracle/checkins/batch-4-review.txt
rg -n -A45 -B8 'Batch 4|T7|Compatibility is a contract|One runtime, one seam|Done Criterion 3|R3' .oracle/tasklist.md .oracle/NORTHSTAR.md NORTHSTAR.md 2>/dev/null
git diff --stat f3bdcb9635..42f86de734
git diff f3bdcb9635..42f86de734 -- resident/cli.py resident/cloud.py agentbox/resident_profile.py resident/runtime.py tests/agentbox/test_resident_profile.py
sed -n '1275,1380p' resident/cli.py
sed -n '1,95p' resident/cloud.py" in /Users/peteromalley/Documents/arnold-oracle
 exited 1 in 77ms:
 agentbox/resident_profile.py                  |   1 +
 arnold_pipelines/megaplan/resident/cli.py     |  25 ++--
 arnold_pipelines/megaplan/resident/runtime.py |   7 +-
 tests/agentbox/test_resident_profile.py       | 202 +++++++++++++++++++++++++-
 4 files changed, 219 insertions(+), 16 deletions(-)
diff --git a/agentbox/resident_profile.py b/agentbox/resident_profile.py
index 4edbcd8c75..c4c1ad339c 100644
--- a/agentbox/resident_profile.py
+++ b/agentbox/resident_profile.py
@@ -119,6 +119,7 @@ class AgentBoxOperatorProfile:
     authorizer: Any | None = None
     config: Any = field(default_factory=lambda: _resident_symbol("config", "ResidentConfig")())
     confirmation_manager: Any | None = None
+    cloud_backend: Any | None = None
     agentbox_config_factory: Callable[[], AgentBoxConfig] = load_agentbox_config
     tool_registry: Any = field(default_factory=lambda: _resident_symbol("tool_registry", "ToolRegistry")())
     _registered_default_tools: bool = False
diff --git a/tests/agentbox/test_resident_profile.py b/tests/agentbox/test_resident_profile.py
index 72ad2c3d09..459ff37919 100644
--- a/tests/agentbox/test_resident_profile.py
+++ b/tests/agentbox/test_resident_profile.py
@@ -42,8 +42,18 @@ from arnold_pipelines.megaplan.resident.agent_loop import (
     ToolRuntimeContext,
     _TOOL_RUNTIME_CONTEXT,
 )
-from arnold_pipelines.megaplan.resident.auth import AuthorizationSubject, ConfirmationManager, ResidentAuthorizer
+from arnold_pipelines.megaplan.resident.auth import (
+    AuthorizationSubject,
+    ConfirmationManager,
+    ResidentAuthorizer,
+    StoreBackedConfirmationManager,
+)
+from arnold_pipelines.megaplan.resident.cloud import CloudToolRequest, CloudToolResult
 from arnold_pipelines.megaplan.resident.config import ResidentConfig
+from arnold_pipelines.megaplan.resident.escalations import (
+    EscalationAnswerDecision,
+    EscalationTarget,
+)
 from arnold_pipelines.megaplan.resident.runtime import InboundEvent, OutboundMessage, ResidentRuntime
 from arnold_pipelines.megaplan.store import FileStore, ResidentConversationInput
 
@@ -120,6 +130,68 @@ def test_agentbox_operator_profile_registers_exact_v0_tool_catalog(
     }
 
 
+def test_generated_agentbox_profile_subclass_retains_exact_v0_tool_catalog() -> None:
+    class GeneratedResidentProfile(AgentBoxOperatorProfile):
+        pass
+
+    profile = GeneratedResidentProfile()
+
+    assert tuple(tool.name for tool in profile.tools().list()) == AGENTBOX_OPERATOR_TOOL_NAMES
+
+
+def test_agentbox_profile_cloud_resume_uses_injected_backend(tmp_path: Path) -> None:
+    backend = _RecordingCloudBackend()
+    repair_data_dir = tmp_path / "repair-data"
+    config = ResidentConfig(
+        profile="agentbox_operator",
+        escalation_repair_lock_dir=tmp_path / "repair-lock",
+    )
+    store = FileStore(tmp_path / "store")
+    authorizer = ResidentAuthorizer(config)
+    runtime = ResidentRuntime(
+        config=config,
+        authorizer=authorizer,
+        store=store,
+        profile=AgentBoxOperatorProfile(
+            store=store,
+            authorizer=authorizer,
+            config=config,
+            cloud_backend=backend,
+        ),
+        runner=_ExplodingAgentRunner(),
+        outbound=_FakeOutboundSink(),
+    )
+    event, decision = _cloud_resume_fixture()
+
+    asyncio.run(runtime._handle_escalation_resolution(event, decision, str(repair_data_dir)))
+
+    assert len(backend.calls) == 1
+    assert backend.calls[0].operation == "cloud_resume"
+    assert backend.calls[0].target_id == "plan-1"
+
+
+def test_agentbox_profile_cloud_resume_without_backend_fails_clearly(tmp_path: Path) -> None:
+    repair_data_dir = tmp_path / "repair-data"
+    config = ResidentConfig(
+        profile="agentbox_operator",
+        escalation_repair_lock_dir=tmp_path / "repair-lock",
+    )
+    store = FileStore(tmp_path / "store")
+    authorizer = ResidentAuthorizer(config)
+    runtime = ResidentRuntime(
+        config=config,
+        authorizer=authorizer,
+        store=store,
+        profile=AgentBoxOperatorProfile(store=store, authorizer=authorizer, config=config),
+        runner=_ExplodingAgentRunner(),
+        outbound=_FakeOutboundSink(),
+    )
+    event, decision = _cloud_resume_fixture()
+
+    with pytest.raises(RuntimeError, match=r"cloud_resume escalation requires profile\.cloud_backend"):
+        asyncio.run(runtime._handle_escalation_resolution(event, decision, str(repair_data_dir)))
+
+
 def test_agentbox_operator_help_lists_v0_capabilities_without_slash_commands(
     tmp_path: Path,
 ) -> None:
@@ -315,8 +387,12 @@ from agentbox.resident_profile import AgentBoxOperatorProfile
 
 class DemoResidentProfile(AgentBoxOperatorProfile):
     marker = {marker!r}
+    constructed = []
 
     def __init__(self, *, store, authorizer, config, confirmation_manager):
+        type(self).constructed.append(
+            (store, authorizer, config, confirmation_manager)
+        )
         self.received_store = store
         self.received_authorizer = authorizer
         self.received_config = config
@@ -330,6 +406,17 @@ class DemoResidentProfile(AgentBoxOperatorProfile):
 """
 
 
+def _failing_external_profile_source() -> str:
+    return """
+from agentbox.resident_profile import AgentBoxOperatorProfile
+
+
+class DemoResidentProfile(AgentBoxOperatorProfile):
+    def __init__(self, *, store, authorizer, config, confirmation_manager):
+        raise RuntimeError("constructor exploded")
+"""
+
+
 def _load_external_profile(root: Path, spec: str):
     config = ResidentConfig(profile=spec)
     return _resident_profile(
@@ -754,17 +841,94 @@ def test_external_profile_dry_run_constructs_profile_without_starting_discord(
     monkeypatch.chdir(tmp_path)
     monkeypatch.delenv("MEGAPLAN_RESIDENT_PROFILE", raising=False)
     monkeypatch.delenv("MEGAPLAN_RESIDENT_STORE_ROOT", raising=False)
-    spec = _write_external_profile(tmp_path, _demo_external_profile_source("dry-run"))
+    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token-that-dry-run-must-not-read")
+
+    def unexpected_call(*args, **kwargs):
+        raise AssertionError("dry-run reached a live Discord/runtime path")
+
+    monkeypatch.setattr(
+        "arnold_pipelines.megaplan.resident.cli.discord_token_from_env",
+        unexpected_call,
+    )
+    monkeypatch.setattr(
+        "arnold_pipelines.megaplan.resident.cli._require_discord_runtime_launch",
+        unexpected_call,
+    )
+    monkeypatch.setattr(
+        "arnold_pipelines.megaplan.resident.cli._resident_runner",
+        unexpected_call,
+    )
+    monkeypatch.setattr(
+        "arnold_pipelines.megaplan.resident.cli.ResidentDiscordService",
+        unexpected_call,
+    )
 
+    spec = _write_external_profile(tmp_path, _demo_external_profile_source("dry-run"))
     result = megaplan_main(["resident", "discord", "--profile", spec, "--dry-run"])
 
     payload = json.loads(capsys.readouterr().out)
+    module_name = _resident_profile_module_name(
+        tmp_path.resolve(), Path("resident_profile.py")
+    )
+    constructed = sys.modules[module_name].DemoResidentProfile.constructed
+    assert len(constructed) == 1
+    received_store, received_authorizer, received_config, received_confirmation = constructed[0]
+    assert isinstance(received_store, FileStore)
+    assert isinstance(received_authorizer, ResidentAuthorizer)
+    assert isinstance(received_config, ResidentConfig)
+    assert isinstance(received_confirmation, StoreBackedConfirmationManager)
     assert result == 0
     assert payload["success"] is True
     assert payload["dry_run"] is True
+    assert payload["token_configured"] is False
     assert payload["profile"] == spec
 
 
+def test_external_profile_constructor_failure_is_a_concise_dry_run_cli_error(
+    tmp_path: Path,
+    monkeypatch,
+    capsys,
+) -> None:
+    monkeypatch.chdir(tmp_path)
+    monkeypatch.delenv("MEGAPLAN_RESIDENT_PROFILE", raising=False)
+    monkeypatch.delenv("MEGAPLAN_RESIDENT_STORE_ROOT", raising=False)
+    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token-that-dry-run-must-not-read")
+
+    def unexpected_call(*args, **kwargs):
+        raise AssertionError("dry-run reached a live Discord/runtime path")
+
+    monkeypatch.setattr(
+        "arnold_pipelines.megaplan.resident.cli.discord_token_from_env",
+        unexpected_call,
+    )
+    monkeypatch.setattr(
+        "arnold_pipelines.megaplan.resident.cli._require_discord_runtime_launch",
+        unexpected_call,
+    )
+    monkeypatch.setattr(
+        "arnold_pipelines.megaplan.resident.cli._resident_runner",
+        unexpected_call,
+    )
+    monkeypatch.setattr(
+        "arnold_pipelines.megaplan.resident.cli.ResidentDiscordService",
+        unexpected_call,
+    )
+
+    spec = _write_external_profile(
+        tmp_path, _failing_external_profile_source()
+    )
+    result = megaplan_main(["resident", "discord", "--profile", spec, "--dry-run"])
+
+    captured = capsys.readouterr()
+    payload = json.loads(captured.out)
+    assert result == 1
+    assert payload["success"] is False
+    assert payload["error"] == "resident_profile_constructor_error"
+    assert "constructor exploded" in payload["message"]
+    assert "Traceback" not in captured.out
+    assert "Traceback" not in captured.err
+
+
 @pytest.mark.parametrize("profile_value", ["", "   "])
 def test_invalid_profile_environment_is_a_cli_error(
     profile_value: str,
@@ -2424,6 +2588,40 @@ class _FakeOutboundSink:
         self.sent.append(message)
 
 
+class _RecordingCloudBackend:
+    def __init__(self) -> None:
+        self.calls: list[CloudToolRequest] = []
+
+    async def run(self, request: CloudToolRequest) -> CloudToolResult:
+        self.calls.append(request)
+        return CloudToolResult(classification="running", summary="cloud_resume: running")
+
+
+def _cloud_resume_fixture() -> tuple[InboundEvent, EscalationAnswerDecision]:
+    target = EscalationTarget(
+        escalation_id="esc-1",
+        session="session-1",
+        target_id="target-1",
+        current_plan="plan-1",
+        channel_id="channel-1",
+        responder_user_id="user-1",
+        message_ids=("message-1",),
+        resume_handler="cloud_resume",
+    )
+    return (
+        InboundEvent(
+            idempotency_key="discord:message:answer-1",
+            conversation_key="discord:dm:user-1",
+            subject=AuthorizationSubject(user_id="user-1", channel_id="channel-1"),
+            content="resume it",
+            escalation_id="esc-1",
+            resume_handler="cloud_resume",
+            raw={"discord_message_id": "answer-1"},
+        ),
+        EscalationAnswerDecision(allowed=True, target=target),
+    )
+
+
 class _ExplodingAgentRunner:
     async def run(self, request: AgentRequest, tools: object) -> object:
         raise AssertionError("resident runner should not execute for denied inbound events")
sed: resident/cli.py: No such file or directory
sed: resident/cloud.py: No such file or directory

exec
/bin/zsh -lc "sed -n '1288,1380p' arnold_pipelines/megaplan/resident/cli.py
sed -n '1,90p' arnold_pipelines/megaplan/resident/cloud.py
sed -n '1470,1505p' arnold_pipelines/megaplan/resident/runtime.py
git diff f3bdcb9635..42f86de734 -- arnold_pipelines/megaplan/resident/cli.py arnold_pipelines/megaplan/resident/runtime.py" in /Users/peteromalley/Documents/arnold-oracle
 succeeded in 0ms:

            target = getattr(module, class_name, _MISSING_EXTERNAL_PROFILE_CLASS)
            if target is _MISSING_EXTERNAL_PROFILE_CLASS:
                raise _external_profile_error(
                    "resident_profile_missing_class",
                    f"Resident profile class {class_name!r} was not found in {path_text!r}",
                )

            if (
                not isinstance(target, type)
                or target is AgentBoxOperatorProfile
                or not issubclass(target, AgentBoxOperatorProfile)
            ):
                raise _external_profile_error(
                    "resident_profile_wrong_base",
                    f"Resident profile class {class_name!r} must subclass AgentBoxOperatorProfile",
                )
            try:
                profile_instance = target(
                    store=store,
                    authorizer=authorizer,
                    config=config,
                    confirmation_manager=confirmation_manager,
                )
            except Exception as exc:
                raise _external_profile_error(
                    "resident_profile_constructor_error",
                    f"Could not construct resident profile {class_name!r}: {exc}",
                ) from exc
            module_loaded_successfully = True
            return profile_instance
        except CliError:
            raise
        except Exception as exc:
            raise _external_profile_error(
                "resident_profile_import_error",
                f"Could not import resident profile {path_text!r}: {exc}",
            ) from exc
        finally:
            if not module_loaded_successfully:
                sys.modules.pop(module_name, None)


def _validate_resident_profile(profile: str) -> None:
    if profile in {"megaplan", "agentbox_operator"}:
        return
    if ":" not in profile and "/" not in profile and "\\" not in profile and not profile.endswith(".py"):
        raise CliError(
            "invalid_args",
            f"Unknown resident profile {profile!r}; expected 'megaplan' or 'agentbox_operator'",
        )
    _parse_external_profile_spec(profile)


def _resident_profile(
    *,
    root: Path,
    profile: str,
    store: Store,
    authorizer: ResidentAuthorizer,
    config: ResidentConfig,
    confirmation_manager: StoreBackedConfirmationManager | None = None,
):
    _validate_resident_profile(profile)
    confirmation_manager = confirmation_manager or StoreBackedConfirmationManager(config, store)
    if profile == "agentbox_operator":
        from agentbox.resident_profile import AgentBoxOperatorProfile

        return AgentBoxOperatorProfile(
            store=store,
            authorizer=authorizer,
            config=config,
            confirmation_manager=confirmation_manager,
        )
    if profile == "megaplan":
        return MegaplanResidentProfile(
            store=store,
            authorizer=authorizer,
            config=config,
            confirmation_manager=confirmation_manager,
            cloud_backend=CloudCliBackend(),
        )
    return _load_external_resident_profile(
        root=root,
        profile=profile,
        store=store,
        authorizer=authorizer,
        config=config,
        confirmation_manager=confirmation_manager,
    )


def _model(row: Any) -> dict[str, Any]:
"""Constrained Megaplan cloud operation wrappers for resident tools."""

from __future__ import annotations

import argparse
import contextlib
from dataclasses import dataclass, field
from io import StringIO
import json
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol

from arnold_pipelines.megaplan.cloud.cli import build_cloud_parser, run_cloud_cli
from .provenance import provenance_scope

CloudClassification = Literal["running", "blocked", "failed", "gate-needed", "completed", "unknown"]
CloudOperation = Literal[
    "cloud_status",
    "cloud_status_chain",
    "cloud_start_chain",
    "cloud_bootstrap",
    "cloud_resume",
    "cloud_logs",
]


@dataclass(frozen=True)
class CloudToolRequest:
    operation: CloudOperation
    target_id: str | None = None
    arguments: dict[str, str] = field(default_factory=dict)
    confirmed: bool = False
    launch_provenance: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class CloudToolResult:
    classification: CloudClassification
    summary: str
    details: dict[str, object] = field(default_factory=dict)


class CloudToolBackend(Protocol):
    async def run(self, request: CloudToolRequest) -> CloudToolResult:
        """Execute one constrained cloud operation."""


class CloudCliBackend:
    """Default resident backend that dispatches through existing cloud CLI code."""

    async def run(self, request: CloudToolRequest) -> CloudToolResult:
        argv = _argv_for_request(request)
        root = Path(request.arguments.get("project_root") or ".").expanduser().resolve()
        parser = argparse.ArgumentParser()
        build_cloud_parser(parser.add_subparsers(dest="command", required=True))
        args = parser.parse_args(["cloud", *argv])
        stdout = StringIO()
        stderr = StringIO()
        with provenance_scope(request.launch_provenance), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = run_cloud_cli(root, args)
        output = stdout.getvalue().strip()
        error_output = stderr.getvalue().strip()
        payload = _json_payload(output)
        classification = classify_cloud_payload(payload or {"returncode": code, "stderr": error_output})
        ok = code == 0
        summary = _summary_for_payload(request.operation, classification, payload, ok=ok)
        return CloudToolResult(
            classification=classification if ok else "failed",
            summary=summary,
            details={
                "returncode": code,
                "stdout": output,
                "stderr": error_output,
                "payload": payload,
                "argv": argv,
            },
        )


def classify_cloud_payload(payload: object) -> CloudClassification:
    """Classify status/chain payloads without depending on provider-specific text."""
    flat = " ".join(str(value).lower() for value in _walk_values(payload))
    if not flat.strip():
        return "unknown"
    if any(token in flat for token in ("gate-needed", "gate_needed", "gate pending", "gate_pending", "state_gated")):
        return "gate-needed"
    if any(token in flat for token in ("failed", "failure", "error", "state_failed", "traceback")):
        return "failed"
    if any(token in flat for token in ("blocked", "execution_blocked", "state_blocked")):
        return "blocked"
        resume_status = "unsupported_handler"
        try:
            writer.write_answered(
                target.session,
                escalation_id=event.escalation_id,
                responder_user_id=event.subject.user_id,
                channel_id=event.subject.channel_id or "",
                message_id=_optional_string(event.raw.get("discord_message_id")) or "",
                extra={"resume_handler": resume_handler},
            )
            marker_path = Path(repair_data_dir) / f"{target.session}.needs-human.json"
            if resume_handler == "cloud_resume":
                cloud_backend = getattr(self.profile, "cloud_backend", None)
                if cloud_backend is None:
                    raise RuntimeError(
                        "cloud_resume escalation requires profile.cloud_backend"
                    )
                cloud_result = await cloud_backend.run(
                    CloudToolRequest(
                        operation="cloud_resume",
                        target_id=target.current_plan or target.target_id,
                        arguments={
                            "plan": target.current_plan or target.target_id,
                            "cloud_yaml": str(self.config.cloud_yaml_path),
                        },
                        confirmed=True,
                    )
                )
                resume_status = cloud_result.classification
                clear_needs_human_marker(marker_path)
            writer.write_resume_attempted(
                target.session,
                escalation_id=event.escalation_id,
                action=resume_handler,
                resume_status=resume_status,
            )
diff --git a/arnold_pipelines/megaplan/resident/cli.py b/arnold_pipelines/megaplan/resident/cli.py
index 251a4be516..bf8e2f85d1 100644
--- a/arnold_pipelines/megaplan/resident/cli.py
+++ b/arnold_pipelines/megaplan/resident/cli.py
@@ -1011,27 +1011,25 @@ def _resident_discord(
     listener_only: bool = False,
     recovery_seed: str | None = None,
 ) -> dict[str, Any]:
-    token = discord_token_from_env(config.discord_bot_token_env)
     _validate_resident_profile(config.profile)
     if dry_run:
-        if config.profile not in {"megaplan", "agentbox_operator"}:
-            authorizer = ResidentAuthorizer(config)
-            confirmation_manager = StoreBackedConfirmationManager(config, store)
-            _resident_profile(
-                root=root,
-                profile=config.profile,
-                store=store,
-                authorizer=authorizer,
-                config=config,
-                confirmation_manager=confirmation_manager,
-            )
+        authorizer = ResidentAuthorizer(config)
+        confirmation_manager = StoreBackedConfirmationManager(config, store)
+        _resident_profile(
+            root=root,
+            profile=config.profile,
+            store=store,
+            authorizer=authorizer,
+            config=config,
+            confirmation_manager=confirmation_manager,
+        )
         return {
             "success": True,
             "step": "resident",
             "action": "discord",
             "dry_run": True,
             "listener_only": listener_only,
-            "token_configured": bool(token),
+            "token_configured": False,
             "profile": config.profile,
             "model_provider": config.model_provider,
             "model": config.model_name,
@@ -1039,6 +1037,7 @@ def _resident_discord(
             "model_max_tokens": config.model_max_tokens,
             "conversation_count": len(store.list_resident_conversations(transport="discord", limit=100)),
         }
+    token = discord_token_from_env(config.discord_bot_token_env)
     if token is None:
         raise CliError("missing_discord_token", f"{config.discord_bot_token_env} is required")
     _require_discord_runtime_launch(
diff --git a/arnold_pipelines/megaplan/resident/runtime.py b/arnold_pipelines/megaplan/resident/runtime.py
index a641d4d4ef..5c587a5716 100644
--- a/arnold_pipelines/megaplan/resident/runtime.py
+++ b/arnold_pipelines/megaplan/resident/runtime.py
@@ -1479,7 +1479,12 @@ class ResidentRuntime:
             )
             marker_path = Path(repair_data_dir) / f"{target.session}.needs-human.json"
             if resume_handler == "cloud_resume":
-                cloud_result = await self.profile.cloud_backend.run(
+                cloud_backend = getattr(self.profile, "cloud_backend", None)
+                if cloud_backend is None:
+                    raise RuntimeError(
+                        "cloud_resume escalation requires profile.cloud_backend"
+                    )
+                cloud_result = await cloud_backend.run(
                     CloudToolRequest(
                         operation="cloud_resume",
                         target_id=target.current_plan or target.target_id,

codex
# Batch 4 rework — Attempt 1

## Finding + evidence

**Blocking — T7 backend injection is incomplete.** `AgentBoxOperatorProfile.cloud_backend` defaults to `None` (`agentbox/resident_profile.py:118-124`). `_resident_profile()` supplies `CloudCliBackend()` only to `MegaplanResidentProfile` (`arnold_pipelines/megaplan/resident/cli.py:1362-1369`); CLI-selected `agentbox_operator` and external/generated subclasses therefore reach inherited `cloud_resume` without a backend and trigger the new clear `RuntimeError` (`resident/runtime.py:1481-1487`). Current coverage proves only manual fake-backend injection.

`CloudCliBackend()` is cheap and safe to construct unconditionally. It is already imported by `resident/cli.py`; the class has no `__init__`, state, I/O, environment access, subprocess, parser construction, or network activity. Work begins only in async `run()`.

## Criterion + North Star

Affected: **Batch 4 T7**, its checkpoint, and **R3 / Done Criterion 3**.

Principles: **Compatibility is a contract** and **One runtime, one seam**.

## Required outcome + scope

In `_resident_profile()`, construct built-in AgentBox and external profiles using the existing four keyword arguments, then assign:

```python
profile_instance.cloud_backend = CloudCliBackend()
```

Return that instance. Do not add a constructor argument or change external loading, runtime escalation, tool registration, or catalog semantics. Preserve direct/manual `cloud_backend=None` behavior and its clear failure.

## Classification + model

**Cross-cutting / XHARD.** The implementation is narrow, but it crosses the CLI factory, inherited profile contract, external subclass compatibility, and shared runtime escalation.

**Selected model:** `codex:gpt-5.6-sol`.

## Acceptance + exact validation

Built-in and external CLI-factory profiles receive `CloudCliBackend`; four-argument external constructors remain compatible; direct explicit `None` raises `cloud_resume escalation requires profile.cloud_backend`; tool registries remain unchanged.

```bash
python -m pytest tests/agentbox/test_resident_profile.py -q
python -m pytest tests/agentbox/test_cli.py tests/agentbox/test_resident_profile.py -q
python -c "from arnold_pipelines.megaplan.resident.cloud import CloudCliBackend; CloudCliBackend()"
```
tokens used
37,141
# Batch 4 rework — Attempt 1

## Finding + evidence

**Blocking — T7 backend injection is incomplete.** `AgentBoxOperatorProfile.cloud_backend` defaults to `None` (`agentbox/resident_profile.py:118-124`). `_resident_profile()` supplies `CloudCliBackend()` only to `MegaplanResidentProfile` (`arnold_pipelines/megaplan/resident/cli.py:1362-1369`); CLI-selected `agentbox_operator` and external/generated subclasses therefore reach inherited `cloud_resume` without a backend and trigger the new clear `RuntimeError` (`resident/runtime.py:1481-1487`). Current coverage proves only manual fake-backend injection.

`CloudCliBackend()` is cheap and safe to construct unconditionally. It is already imported by `resident/cli.py`; the class has no `__init__`, state, I/O, environment access, subprocess, parser construction, or network activity. Work begins only in async `run()`.

## Criterion + North Star

Affected: **Batch 4 T7**, its checkpoint, and **R3 / Done Criterion 3**.

Principles: **Compatibility is a contract** and **One runtime, one seam**.

## Required outcome + scope

In `_resident_profile()`, construct built-in AgentBox and external profiles using the existing four keyword arguments, then assign:

```python
profile_instance.cloud_backend = CloudCliBackend()
```

Return that instance. Do not add a constructor argument or change external loading, runtime escalation, tool registration, or catalog semantics. Preserve direct/manual `cloud_backend=None` behavior and its clear failure.

## Classification + model

**Cross-cutting / XHARD.** The implementation is narrow, but it crosses the CLI factory, inherited profile contract, external subclass compatibility, and shared runtime escalation.

**Selected model:** `codex:gpt-5.6-sol`.

## Acceptance + exact validation

Built-in and external CLI-factory profiles receive `CloudCliBackend`; four-argument external constructors remain compatible; direct explicit `None` raises `cloud_resume escalation requires profile.cloud_backend`; tool registries remain unchanged.

```bash
python -m pytest tests/agentbox/test_resident_profile.py -q
python -m pytest tests/agentbox/test_cli.py tests/agentbox/test_resident_profile.py -q
python -c "from arnold_pipelines.megaplan.resident.cloud import CloudCliBackend; CloudCliBackend()"
```
