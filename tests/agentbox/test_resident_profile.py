from __future__ import annotations

import argparse
import hashlib
import contextvars
import asyncio
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from arnold.runtime.durable_ops import OperationState
from agentbox.config import AgentBoxConfig
from agentbox.operations import (
    create_agentbox_operation,
    load_agentbox_operation,
    update_agentbox_operation,
)
from agentbox.resident_profile import (
    AGENTBOX_OPERATOR_TOOL_NAMES,
    AgentBoxOperatorProfile,
)
from agentbox.run_dirs import append_stdout, ensure_run_dir
from arnold_pipelines.megaplan.resident.cli import (
    _register_resident_subcommands,
    _resident_config,
    _resident_discord,
    _resident_profile,
    _resident_profile_module_name,
)
from arnold_pipelines.megaplan.cli import main as megaplan_main
from arnold_pipelines.megaplan.resident.profile import MegaplanResidentProfile
from arnold_pipelines.megaplan.types import CliError
from arnold_pipelines.megaplan.resident.agent_loop import (
    AgentRequest,
    AgentResponse,
    FakeAgentRunner,
    FakeAgentStep,
    ToolRuntimeContext,
    _TOOL_RUNTIME_CONTEXT,
)
from arnold_pipelines.megaplan.resident.auth import (
    AuthorizationSubject,
    ConfirmationManager,
    ResidentAuthorizer,
    StoreBackedConfirmationManager,
)
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.runtime import InboundEvent, OutboundMessage, ResidentRuntime
from arnold_pipelines.megaplan.store import FileStore, ResidentConversationInput


def _set_runtime_subject(subject: object) -> contextvars.Token:
    """Set the resident tool runtime context so tools see an authorized subject.

    The real agent loop wraps each tool handler in ``_run_tool_handler`` which
    sets ``_TOOL_RUNTIME_CONTEXT``; FakeAgentRunner does not, so subagent tools
    that read ``current_tool_runtime_context()`` would see no subject and
    return ``runtime_subject_required``. The caller keeps the returned token
    alive for the duration of the run and resets it after.
    """
    return _TOOL_RUNTIME_CONTEXT.set(
        ToolRuntimeContext(
            conversation_id="conversation-1",
            subject=subject,
            launch_origin=None,
            tool_call_id="tool-call-1",
        )
    )


def test_arnold_agent_prompt_has_raw_byte_parity_with_resident_profile() -> None:
    agent_file = Path(__file__).parents[2] / "agentbox" / "agents" / "arnold.md"
    raw = agent_file.read_bytes()
    assert raw.startswith(b"---")

    closing_index = raw.index(b"\n---", 3)
    assert raw[closing_index : closing_index + 5] == b"\n---\n"
    raw_body = raw[closing_index + 5 :]

    normalized = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    normalized_closing_index = normalized.index("\n---", 3)
    parsed_body = normalized[normalized_closing_index + 4 :].strip().encode()
    expected_prompt = AgentBoxOperatorProfile().system_prompt().encode()

    # Semantic prompt edits MUST change both the agent file and resident_profile.py
    # and bump AGENTBOX_OPERATOR_PROMPT_VERSION; raw-bytes is the authority
    # (no whitespace normalization).
    assert parsed_body == expected_prompt
    assert raw_body == expected_prompt + b"\n"


def test_agentbox_operator_profile_registers_exact_v0_tool_catalog(
    tmp_path: Path,
) -> None:
    profile = AgentBoxOperatorProfile(
        store=FileStore(tmp_path / "store"),
        agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
    )

    tools = profile.tools().list()

    assert tuple(tool.name for tool in tools) == AGENTBOX_OPERATOR_TOOL_NAMES
    assert {field for tool in tools for field in tool.input_model.model_fields} >= {
        "title",
        "repo",
        "spec",
        "operation",
        "stream",
        "lines",
        "kind",
        "query",
    }
    assert "actor_user_id" not in {
        field for tool in tools for field in tool.input_model.model_fields
    }
    assert "guild_id" not in {
        field for tool in tools for field in tool.input_model.model_fields
    }
    assert "channel_id" not in {
        field for tool in tools for field in tool.input_model.model_fields
    }


def test_agentbox_operator_help_lists_v0_capabilities_without_slash_commands(
    tmp_path: Path,
) -> None:
    profile = AgentBoxOperatorProfile(
        store=FileStore(tmp_path / "store"),
        agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
    )
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call("help", {}),
            FakeAgentStep.final("done"),
        ]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "help"},),
                system_prompt="test",
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result

    assert result["ok"] is True
    assert result["data"] == {
        "profile": "agentbox_operator",
        "action": "help",
        "next_state": "choose_v0_tool",
        "tools": [
            {
                "name": "ticket_new",
                "capability": "create a tracked AgentBox ticket",
                "required_fields": ["title"],
                "optional_fields": ["body", "tags", "repo", "codebase_id"],
            },
            {
                "name": "chain_launch",
                "capability": "launch a Megaplan chain through AgentBox",
                "required_fields": ["repo", "spec"],
                "optional_fields": [
                    "operation_id",
                    "base_ref",
                    "confirmation_request_id",
                    "confirmation_phrase",
                ],
            },
            {
                "name": "status",
                "capability": "inspect AgentBox operation status",
                "required_fields": [],
                "optional_fields": ["operation"],
            },
            {
                "name": "logs",
                "capability": "read bounded AgentBox operation logs",
                "required_fields": ["operation"],
                "optional_fields": ["stream", "lines"],
            },
            {
                "name": "help",
                "capability": "list AgentBox Operator v0 tool capabilities",
                "required_fields": [],
                "optional_fields": [],
            },
            {
                "name": "resolve",
                "capability": "resolve operation, repo, or ticket references without side effects",
                "required_fields": ["query"],
                "optional_fields": ["kind"],
            },
        ],
    }
    assert "slash" not in str(result["data"]).lower()


def test_agentbox_operator_profile_loads_bounded_hot_context(
    tmp_path: Path,
) -> None:
    store = FileStore(tmp_path / "store")
    conversation = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c1",
            guild_id="g1",
            channel_id="c1",
        )
    )
    for index in range(7):
        message = store.create_message(
            epic_id=None,
            conversation_id=conversation.id,
            direction="inbound",
            content=f"message {index}",
        )
        turn = store.create_turn(
            epic_id=None,
            triggered_by_message_ids=[message.id],
        )
        store.record_tool_call(
            turn_id=turn.id,
            tool_name="help",
            operation_kind="read",
            arguments={},
            result={"ok": True, "index": index},
            duration_ms=1,
        )
    agentbox_config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    for index in range(7):
        create_agentbox_operation(agentbox_config, f"op-{index}", command="echo hi")
    profile = AgentBoxOperatorProfile(
        store=store,
        agentbox_config_factory=lambda: agentbox_config,
    )

    context = asyncio.run(profile.load_hot_context(conversation.id))

    assert context["profile"] == "agentbox_operator"
    assert context["conversation"]["id"] == conversation.id
    assert len(context["recent_messages"]) == 5
    assert len(context["recent_tool_calls"]) == 5
    assert len(context["recent_operations"]) == 5
    assert all("text" not in entry for op in context["recent_operations"] for entry in op["logs"])


def test_agentbox_operator_profile_selected_by_config_and_discord_cli(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("MEGAPLAN_RESIDENT_MODEL_PROVIDER", raising=False)
    monkeypatch.delenv("MEGAPLAN_RESIDENT_MODEL", raising=False)
    parser = argparse.ArgumentParser()
    _register_resident_subcommands(parser)
    args = parser.parse_args(
        [
            "discord",
            "--store-root",
            str(tmp_path / "store"),
            "--profile",
            "agentbox_operator",
            "--dry-run",
        ]
    )

    config = _resident_config(args)
    dry_run = _resident_discord(
        tmp_path,
        FileStore(tmp_path / "store"),
        config,
        dry_run=True,
    )
    selected = _resident_profile(
        root=tmp_path,
        profile=config.profile,
        store=FileStore(tmp_path / "profile-store"),
        authorizer=None,
        config=config,
    )
    megaplan_selected = _resident_profile(
        root=tmp_path,
        profile="megaplan",
        store=FileStore(tmp_path / "megaplan-profile-store"),
        authorizer=None,
        config=ResidentConfig(),
    )
    env_config = ResidentConfig.from_env({"MEGAPLAN_RESIDENT_PROFILE": "agentbox_operator"})

    assert config.profile == "agentbox_operator"
    assert dry_run["profile"] == "agentbox_operator"
    assert dry_run["model_provider"] == "hermes"
    assert dry_run["model"] == "zhipu:glm-5.2"
    assert isinstance(selected, AgentBoxOperatorProfile)
    assert isinstance(megaplan_selected, MegaplanResidentProfile)
    assert ResidentConfig().profile == "megaplan"
    assert ResidentConfig().model_provider == "hermes"
    assert ResidentConfig().model_name == "zhipu:glm-5.2"
    assert env_config.profile == "agentbox_operator"


def _write_external_profile(root: Path, source: str, relative: str = "resident_profile.py") -> str:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return f"{relative}:DemoResidentProfile"


def _demo_external_profile_source(marker: str) -> str:
    return f"""
from agentbox.resident_profile import AgentBoxOperatorProfile


class DemoResidentProfile(AgentBoxOperatorProfile):
    marker = {marker!r}
    constructed = []

    def __init__(self, *, store, authorizer, config, confirmation_manager):
        type(self).constructed.append(
            (store, authorizer, config, confirmation_manager)
        )
        self.received_store = store
        self.received_authorizer = authorizer
        self.received_config = config
        self.received_confirmation_manager = confirmation_manager
        super().__init__(
            store=store,
            authorizer=authorizer,
            config=config,
            confirmation_manager=confirmation_manager,
        )
"""


def _failing_external_profile_source() -> str:
    return """
from agentbox.resident_profile import AgentBoxOperatorProfile


class DemoResidentProfile(AgentBoxOperatorProfile):
    def __init__(self, *, store, authorizer, config, confirmation_manager):
        raise RuntimeError("constructor exploded")
"""


def _load_external_profile(root: Path, spec: str):
    config = ResidentConfig(profile=spec)
    return _resident_profile(
        root=root,
        profile=spec,
        store=FileStore(root / "store"),
        authorizer=None,
        config=config,
    )


def test_external_profile_injects_exact_builtin_constructor_dependencies(tmp_path: Path) -> None:
    spec = _write_external_profile(
        tmp_path,
        _demo_external_profile_source("injected"),
        ".agentbox/resident_profile.py",
    )
    store = FileStore(tmp_path / "store")
    authorizer = object()
    config = ResidentConfig(profile=spec)
    confirmation_manager = object()

    profile = _resident_profile(
        root=tmp_path,
        profile=spec,
        store=store,
        authorizer=authorizer,
        config=config,
        confirmation_manager=confirmation_manager,
    )

    assert isinstance(profile, AgentBoxOperatorProfile)
    assert profile.marker == "injected"
    assert profile.received_store is store
    assert profile.received_authorizer is authorizer
    assert profile.received_config is config
    assert profile.received_confirmation_manager is confirmation_manager


@pytest.mark.parametrize(
    ("spec", "code"),
    [
        ("resident.txt:DemoResidentProfile", "resident_profile_malformed"),
        ("resident_profile.py", "resident_profile_malformed"),
        ("resident_profile.py:bad-name", "resident_profile_malformed"),
        ("resident_profile.py:DemoResidentProfile:Extra", "resident_profile_malformed"),
    ],
)
def test_external_profile_rejects_malformed_specs(
    tmp_path: Path,
    spec: str,
    code: str,
) -> None:
    with pytest.raises(CliError) as error:
        _load_external_profile(tmp_path, spec)

    assert error.value.code == code


def test_external_profile_rejects_absolute_path(tmp_path: Path) -> None:
    path = tmp_path / "resident_profile.py"
    path.write_text(_demo_external_profile_source("absolute"), encoding="utf-8")

    with pytest.raises(CliError) as error:
        _load_external_profile(tmp_path, f"{path}:DemoResidentProfile")

    assert error.value.code == "resident_profile_containment_escape"


def test_external_profile_rejects_windows_absolute_path(tmp_path: Path) -> None:
    with pytest.raises(CliError) as error:
        _load_external_profile(
            tmp_path,
            r"C:\repo\resident_profile.py:DemoResidentProfile",
        )

    assert error.value.code == "resident_profile_containment_escape"


def test_external_profile_rejects_traversal(tmp_path: Path) -> None:
    with pytest.raises(CliError) as error:
        _load_external_profile(tmp_path, "../resident_profile.py:DemoResidentProfile")

    assert error.value.code == "resident_profile_containment_escape"


def test_external_profile_rejects_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside.py"
    outside.write_text(_demo_external_profile_source("outside"), encoding="utf-8")
    link = tmp_path / "resident_profile.py"
    link.symlink_to(outside)

    try:
        with pytest.raises(CliError) as error:
            _load_external_profile(tmp_path, "resident_profile.py:DemoResidentProfile")
    finally:
        outside.unlink()

    assert error.value.code == "resident_profile_containment_escape"


def test_external_profile_rejects_contained_symlink_to_non_python_target(tmp_path: Path) -> None:
    target = tmp_path / "resident_profile.txt"
    target.write_text(_demo_external_profile_source("not-python"), encoding="utf-8")
    link = tmp_path / "resident_profile.py"
    link.symlink_to(target)

    with pytest.raises(CliError) as error:
        _load_external_profile(tmp_path, "resident_profile.py:DemoResidentProfile")

    assert error.value.code == "resident_profile_not_python"


def test_external_profile_reports_missing_file(tmp_path: Path) -> None:
    with pytest.raises(CliError) as error:
        _load_external_profile(tmp_path, "resident_profile.py:DemoResidentProfile")

    assert error.value.code == "resident_profile_missing_file"


def test_external_profile_reports_missing_class(tmp_path: Path) -> None:
    source = "from agentbox.resident_profile import AgentBoxOperatorProfile\n"
    spec = _write_external_profile(tmp_path, source)

    with pytest.raises(CliError) as error:
        _load_external_profile(tmp_path, spec)

    assert error.value.code == "resident_profile_missing_class"


def test_external_profile_reports_wrong_base(tmp_path: Path) -> None:
    source = "DemoResidentProfile = None\n"
    spec = _write_external_profile(tmp_path, source)

    with pytest.raises(CliError) as error:
        _load_external_profile(tmp_path, spec)

    assert error.value.code == "resident_profile_wrong_base"


def test_external_profile_reports_import_error_and_evicts_module(tmp_path: Path) -> None:
    source = "raise RuntimeError('profile import exploded')\n"
    spec = _write_external_profile(tmp_path, source)
    module_name = _resident_profile_module_name(tmp_path.resolve(), Path("resident_profile.py"))

    with pytest.raises(CliError) as error:
        _load_external_profile(tmp_path, spec)

    assert error.value.code == "resident_profile_import_error"
    assert module_name not in sys.modules


def test_external_profile_reports_constructor_error_and_evicts_module(tmp_path: Path) -> None:
    source = """
from agentbox.resident_profile import AgentBoxOperatorProfile


class DemoResidentProfile(AgentBoxOperatorProfile):
    def __init__(self, required):
        super().__init__()
"""
    spec = _write_external_profile(tmp_path, source)
    module_name = _resident_profile_module_name(tmp_path.resolve(), Path("resident_profile.py"))

    with pytest.raises(CliError) as error:
        _load_external_profile(tmp_path, spec)

    assert error.value.code == "resident_profile_constructor_error"
    assert module_name not in sys.modules


def test_external_profile_repeated_loads_are_fresh(tmp_path: Path) -> None:
    spec = _write_external_profile(tmp_path, _demo_external_profile_source("first"))
    first = _load_external_profile(tmp_path, spec)
    (tmp_path / "resident_profile.py").write_text(
        _demo_external_profile_source("second"),
        encoding="utf-8",
    )

    second = _load_external_profile(tmp_path, spec)

    assert first.marker == "first"
    assert second.marker == "second"
    assert first is not second


def test_external_profile_identity_is_deterministic_and_cross_repo_distinct(tmp_path: Path) -> None:
    root_one = tmp_path / "one"
    root_two = tmp_path / "two"
    relative_path = Path("nested/profile-v1.py")
    spec_one = _write_external_profile(
        root_one,
        _demo_external_profile_source("root-one"),
        str(relative_path),
    )
    spec_two = _write_external_profile(
        root_two,
        _demo_external_profile_source("root-two"),
        str(relative_path),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        profiles = list(
            executor.map(
                lambda item: _load_external_profile(*item),
                ((root_one, spec_one), (root_two, spec_two)),
            )
        )
    module_one = _resident_profile_module_name(root_one.resolve(), relative_path)
    module_two = _resident_profile_module_name(root_two.resolve(), relative_path)

    expected_digest_one = hashlib.sha256(
        (str(root_one.resolve()) + "\0" + str(relative_path)).encode("utf-8")
    ).hexdigest()
    expected_digest_two = hashlib.sha256(
        (str(root_two.resolve()) + "\0" + str(relative_path)).encode("utf-8")
    ).hexdigest()

    assert profiles[0].marker == "root-one"
    assert profiles[1].marker == "root-two"
    assert module_one == f"_arnold_resident_profile_profile_v1_{expected_digest_one}"
    assert module_two == f"_arnold_resident_profile_profile_v1_{expected_digest_two}"
    assert module_one == _resident_profile_module_name(root_one.resolve(), relative_path)
    assert module_one != module_two
    assert module_one in sys.modules
    assert module_two in sys.modules


@pytest.mark.parametrize(
    ("spec", "source", "code"),
    [
        ("resident.txt:DemoResidentProfile", None, "resident_profile_malformed"),
        (
            "../resident_profile.py:DemoResidentProfile",
            None,
            "resident_profile_containment_escape",
        ),
        (
            "resident_profile.py:DemoResidentProfile",
            None,
            "resident_profile_missing_file",
        ),
        (
            "resident_profile.py:DemoResidentProfile",
            "from agentbox.resident_profile import AgentBoxOperatorProfile\n",
            "resident_profile_missing_class",
        ),
        (
            "resident_profile.py:DemoResidentProfile",
            "class DemoResidentProfile:\n    pass\n",
            "resident_profile_wrong_base",
        ),
        (
            "resident_profile.py:DemoResidentProfile",
            "raise RuntimeError('profile import exploded')\n",
            "resident_profile_import_error",
        ),
        (
            "resident_profile.py:DemoResidentProfile",
            (
                "from agentbox.resident_profile import AgentBoxOperatorProfile\n\n"
                "class DemoResidentProfile(AgentBoxOperatorProfile):\n"
                "    def __init__(self, required):\n"
                "        super().__init__()\n"
            ),
            "resident_profile_constructor_error",
        ),
    ],
)
def test_external_profile_rejections_are_json_cli_errors(
    tmp_path: Path,
    monkeypatch,
    capsys,
    spec: str,
    source: str | None,
    code: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MEGAPLAN_RESIDENT_PROFILE", raising=False)
    monkeypatch.delenv("MEGAPLAN_RESIDENT_STORE_ROOT", raising=False)
    if source is not None:
        (tmp_path / "resident_profile.py").write_text(source, encoding="utf-8")

    result = megaplan_main(["resident", "discord", "--profile", spec, "--dry-run"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert result == 1
    assert payload["success"] is False
    assert payload["error"] == code
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err



@pytest.mark.parametrize("profile_value", ["", "   "])
def test_invalid_profile_cli_is_a_cli_error(
    profile_value: str,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.delenv("MEGAPLAN_RESIDENT_PROFILE", raising=False)

    result = megaplan_main(
        ["resident", "discord", "--profile", profile_value, "--dry-run"]
    )

    assert result == 1
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["success"] is False
    assert payload["error"] == "invalid_args"
    assert "Invalid resident configuration" in payload["message"]
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err



@pytest.mark.parametrize(
    "resolution_error_type",
    [RuntimeError, ValueError],
    ids=["runtime-error", "value-error"],
)
def test_external_profile_root_resolution_errors_are_json_cli_errors(
    tmp_path: Path,
    monkeypatch,
    capsys,
    resolution_error_type: type[Exception],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MEGAPLAN_RESIDENT_PROFILE", raising=False)
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cli._find_megaplan_root",
        lambda start: tmp_path,
    )
    store = FileStore(tmp_path / "store")
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.resident.cli._resident_store",
        lambda root, args: store,
    )

    def fail_resolve(self: Path, *args, **kwargs):
        raise resolution_error_type("root resolution failed")

    monkeypatch.setattr(Path, "resolve", fail_resolve)

    result = megaplan_main(
        [
            "resident",
            "discord",
            "--profile",
            "resident_profile.py:DemoResidentProfile",
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert result == 1
    assert payload["success"] is False
    assert payload["error"] == "resident_profile_missing_file"
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err


@pytest.mark.parametrize(
    "resolution_error_type",
    [RuntimeError, ValueError],
    ids=["runtime-error", "value-error"],
)
def test_external_profile_candidate_resolution_errors_are_json_cli_errors(
    tmp_path: Path,
    monkeypatch,
    capsys,
    resolution_error_type: type[Exception],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MEGAPLAN_RESIDENT_PROFILE", raising=False)
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cli._find_megaplan_root",
        lambda start: tmp_path,
    )
    store = FileStore(tmp_path / "store")
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.resident.cli._resident_store",
        lambda root, args: store,
    )
    profile_path = tmp_path / "resident_profile.py"
    profile_path.write_text(_demo_external_profile_source("resolution"), encoding="utf-8")
    original_resolve = Path.resolve

    def fail_candidate_resolve(self: Path, *args, **kwargs):
        if self == profile_path:
            raise resolution_error_type("candidate resolution failed")
        return original_resolve(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", fail_candidate_resolve)

    result = megaplan_main(
        [
            "resident",
            "discord",
            "--profile",
            "resident_profile.py:DemoResidentProfile",
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert result == 1
    assert payload["success"] is False
    assert payload["error"] == "resident_profile_missing_file"
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err

def test_external_profile_dry_run_constructs_profile_without_starting_discord(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MEGAPLAN_RESIDENT_PROFILE", raising=False)
    monkeypatch.delenv("MEGAPLAN_RESIDENT_STORE_ROOT", raising=False)
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token-that-dry-run-must-not-read")

    def unexpected_call(*args, **kwargs):
        raise AssertionError("dry-run reached a live Discord/runtime path")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.resident.cli.discord_token_from_env",
        unexpected_call,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.resident.cli._require_discord_runtime_launch",
        unexpected_call,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.resident.cli._resident_runner",
        unexpected_call,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.resident.cli.ResidentDiscordService",
        unexpected_call,
    )

    spec = _write_external_profile(tmp_path, _demo_external_profile_source("dry-run"))
    result = megaplan_main(["resident", "discord", "--profile", spec, "--dry-run"])

    payload = json.loads(capsys.readouterr().out)
    module_name = _resident_profile_module_name(
        tmp_path.resolve(), Path("resident_profile.py")
    )
    constructed = sys.modules[module_name].DemoResidentProfile.constructed
    assert len(constructed) == 1
    received_store, received_authorizer, received_config, received_confirmation = constructed[0]
    assert isinstance(received_store, FileStore)
    assert isinstance(received_authorizer, ResidentAuthorizer)
    assert isinstance(received_config, ResidentConfig)
    assert isinstance(received_confirmation, StoreBackedConfirmationManager)
    assert result == 0
    assert payload["success"] is True
    assert payload["dry_run"] is True
    assert payload["token_configured"] is False
    assert payload["profile"] == spec


def test_external_profile_constructor_failure_is_a_concise_dry_run_cli_error(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MEGAPLAN_RESIDENT_PROFILE", raising=False)
    monkeypatch.delenv("MEGAPLAN_RESIDENT_STORE_ROOT", raising=False)
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token-that-dry-run-must-not-read")

    def unexpected_call(*args, **kwargs):
        raise AssertionError("dry-run reached a live Discord/runtime path")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.resident.cli.discord_token_from_env",
        unexpected_call,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.resident.cli._require_discord_runtime_launch",
        unexpected_call,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.resident.cli._resident_runner",
        unexpected_call,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.resident.cli.ResidentDiscordService",
        unexpected_call,
    )

    spec = _write_external_profile(
        tmp_path, _failing_external_profile_source()
    )
    result = megaplan_main(["resident", "discord", "--profile", spec, "--dry-run"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert result == 1
    assert payload["success"] is False
    assert payload["error"] == "resident_profile_constructor_error"
    assert "constructor exploded" in payload["message"]
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("profile_value", ["", "   "])
def test_invalid_profile_environment_is_a_cli_error(
    profile_value: str,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("MEGAPLAN_RESIDENT_PROFILE", profile_value)

    result = megaplan_main(["resident", "health"])

    assert result == 1
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["success"] is False
    assert payload["error"] == "invalid_args"
    assert "Invalid resident configuration" in payload["message"]
    assert "Traceback" not in captured.err


def test_non_builtin_profile_parses_but_dispatch_rejects_with_cli_error(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.delenv("MEGAPLAN_RESIDENT_PROFILE", raising=False)
    parser = argparse.ArgumentParser()
    _register_resident_subcommands(parser)
    args = parser.parse_args(["discord", "--profile", "custom_profile", "--dry-run"])

    assert args.profile == "custom_profile"
    result = megaplan_main(
        ["resident", "discord", "--profile", "custom_profile", "--dry-run"]
    )

    assert result == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is False
    assert payload["error"] == "invalid_args"
    assert "Unknown resident profile 'custom_profile'" in payload["message"]


def test_non_builtin_profile_rejected_by_profile_constructor(
    tmp_path: Path,
) -> None:
    config = ResidentConfig(profile="custom_profile")

    with pytest.raises(CliError, match="Unknown resident profile"):
        _resident_profile(
            root=tmp_path,
            profile=config.profile,
            store=FileStore(tmp_path / "store"),
            authorizer=None,
            config=config,
        )


def test_agentbox_operator_runs_through_resident_runtime_persistence_and_outbound_sink(
    tmp_path: Path,
) -> None:
    store = FileStore(tmp_path / "store")
    codebase = store.create_codebase(
        owner="owner",
        name="repo",
        default_branch="main",
        codebase_id="codebase-1",
    )
    config = ResidentConfig(
        profile="agentbox_operator",
        allowed_user_ids=("user-1",),
        burst_idle_delay_s=0,
        burst_max_delay_s=1,
    )
    outbound = _FakeOutboundSink()
    runtime = ResidentRuntime(
        config=config,
        authorizer=ResidentAuthorizer(config),
        store=store,
        profile=AgentBoxOperatorProfile(
            store=store,
            authorizer=ResidentAuthorizer(config),
            agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
        ),
        runner=FakeAgentRunner(
            [
                FakeAgentStep.call(
                    "ticket_new",
                    {
                        "repo": "owner/repo",
                        "title": "Runtime Persistence",
                        "body": "Exercise the resident runtime path.",
                        "tags": ["discord", "runtime"],
                    },
                ),
                FakeAgentStep.final("ticket filed"),
            ]
        ),
        outbound=outbound,
    )
    subject = AuthorizationSubject(user_id="user-1", guild_id="g1", channel_id="c1")

    asyncio.run(
        _receive_and_flush(
            runtime,
            InboundEvent(
                idempotency_key="discord:message:m1",
                conversation_key="discord:guild:g1:channel:c1",
                subject=subject,
                content="file a ticket",
                raw={"discord_message_id": "m1", "conversation_metadata": {"source": "test"}},
            ),
        )
    )

    conversations = store.list_resident_conversations(transport="discord")
    assert len(conversations) == 1
    conversation = conversations[0]
    assert conversation.conversation_key == "discord:guild:g1:channel:c1"
    assert conversation.guild_id == "g1"
    assert conversation.channel_id == "c1"
    assert conversation.metadata["last_subject_user_id"] == "user-1"
    assert conversation.metadata["source"] == "test"

    turns = store.list_recent_turns(n=1)
    assert len(turns) == 1
    turn = turns[0]
    assert turn.status == "completed"
    assert turn.message_sent is True
    assert turn.final_output_message_id == conversation.last_outbound_message_id
    assert turn.state_at_turn["profile"] == "agentbox_operator"

    inbound_messages = store.load_messages(turn.triggered_by_message_ids)
    assert len(inbound_messages) == 1
    assert inbound_messages[0].direction == "inbound"
    assert inbound_messages[0].content == "file a ticket"
    assert inbound_messages[0].bot_turn_id == turn.id

    outbound_message = store.latest_outbound_message()
    assert outbound_message is not None
    assert outbound_message.id == turn.final_output_message_id
    assert outbound_message.conversation_id == conversation.id
    assert outbound_message.content == "ticket filed"
    assert outbound.sent == [
        OutboundMessage(
            conversation_key="discord:guild:g1:channel:c1",
            content="ticket filed",
            idempotency_key=outbound_message.idempotency_key,
            metadata={
                "delivery_kind": "interactive_reply",
                "conversation_id": conversation.id,
                "message_id": outbound_message.id,
                "turn_id": turn.id,
                "discord_reply_to_message_id": "m1",
                "discord_processing_message_ids": ["m1"],
                "discord_processing_turn_id": turn.id,
                "discord_processing_continues": False,
            },
        )
    ]

    tool_calls = store.search_tool_calls_by(tool_name="ticket_new", limit=10)
    assert len(tool_calls) == 1
    assert tool_calls[0].turn_id == turn.id
    assert tool_calls[0].result["ok"] is True
    ticket_id = tool_calls[0].result["data"]["ticket_id"]
    ticket = store.load_ticket(ticket_id)
    assert ticket is not None
    assert ticket.title == "Runtime Persistence"
    assert ticket.codebase_id == codebase.id
    assert ticket.filed_by_actor_id == "user-1"


def test_resident_runtime_includes_replied_to_discord_message_in_runner_context(
    tmp_path: Path,
) -> None:
    store = FileStore(tmp_path / "store")
    config = ResidentConfig(
        profile="agentbox_operator",
        allowed_user_ids=("user-1",),
        burst_idle_delay_s=0,
        burst_max_delay_s=1,
    )
    authorizer = ResidentAuthorizer(config)
    runner = _RecordingFakeRunner([FakeAgentStep.final("handled")])
    outbound = _FakeOutboundSink()
    runtime = ResidentRuntime(
        config=config,
        authorizer=authorizer,
        store=store,
        profile=AgentBoxOperatorProfile(
            store=store,
            authorizer=authorizer,
            agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
        ),
        runner=runner,
        outbound=outbound,
    )
    conversation = store.upsert_resident_conversation(
        ResidentConversationInput(
            transport="discord",
            conversation_key="discord:guild:g1:channel:c1",
            guild_id="g1",
            channel_id="c1",
        ),
        idempotency_key="conversation-1",
    )
    store.create_message(
        epic_id=None,
        conversation_id=conversation.id,
        direction="inbound",
        content="prior message body",
        discord_message_id="discord-prior",
        idempotency_key="prior-message",
    )

    asyncio.run(
        _receive_and_flush(
            runtime,
            InboundEvent(
                idempotency_key="discord:message:reply-m1",
                conversation_key="discord:guild:g1:channel:c1",
                subject=AuthorizationSubject(user_id="user-1", guild_id="g1", channel_id="c1"),
                content="answering that",
                raw={
                    "discord_message_id": "reply-m1",
                    "discord_reference_message_id": "discord-prior",
                },
            ),
        )
    )

    assert runner.captured_request is not None
    prompt = runner.captured_request.messages[-1]
    assert prompt["role"] == "user"
    assert "[Discord reply ancestry — nearest parent first; current message excluded]" in prompt["content"]
    assert "Discord message id: discord-prior" in prompt["content"]
    assert "prior message body" in prompt["content"]
    assert prompt["content"].endswith("Content truncated: no\nanswering that")
    assert outbound.sent[-1].metadata["discord_reply_to_message_id"] == "reply-m1"


def test_agentbox_operator_resident_runtime_denies_non_allowlisted_discord_author_before_execution(
    tmp_path: Path,
) -> None:
    store = FileStore(tmp_path / "store")
    config = ResidentConfig(
        profile="agentbox_operator",
        allowed_user_ids=("user-1",),
        burst_idle_delay_s=0,
        burst_max_delay_s=1,
    )
    authorizer = ResidentAuthorizer(config)
    outbound = _FakeOutboundSink()
    runtime = ResidentRuntime(
        config=config,
        authorizer=authorizer,
        store=store,
        profile=AgentBoxOperatorProfile(
            store=store,
            authorizer=authorizer,
            agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
        ),
        runner=_ExplodingAgentRunner(),
        outbound=outbound,
    )

    asyncio.run(
        _receive_and_flush(
            runtime,
            InboundEvent(
                idempotency_key="discord:message:denied-m1",
                conversation_key="discord:guild:g1:channel:c1",
                subject=AuthorizationSubject(user_id="user-2", guild_id="g1", channel_id="c1"),
                content="file a ticket",
                raw={"discord_message_id": "denied-m1"},
            ),
        )
    )

    assert outbound.sent == []
    assert store.list_resident_conversations(transport="discord") == []
    assert store.list_recent_turns(n=10) == []
    assert store.search_tool_calls_by(limit=10) == []
    assert store.latest_outbound_message() is None

    assert len(authorizer.denials) == 1
    denial = authorizer.denials[0]
    assert denial.user_id == "user-2"
    assert denial.guild_id == "g1"
    assert denial.channel_id == "c1"
    assert denial.action == "inbound"
    assert denial.reason == "user_not_allowed"

    log_files = list((tmp_path / "store" / "system_logs").glob("*.json"))
    assert len(log_files) == 1
    log = json.loads(log_files[0].read_text(encoding="utf-8"))
    assert log["level"] == "warn"
    assert log["category"] == "system"
    assert log["event_type"] == "resident_inbound_denied"
    assert log["message"] == "Resident inbound event denied before execution"
    assert log["details"]["reason"] == "user_not_allowed"
    assert log["details"]["audit"] | {"occurred_at": "<dynamic>"} == {
        "user_id": "user-2",
        "guild_id": "g1",
        "channel_id": "c1",
        "action": "inbound",
        "reason": "user_not_allowed",
        "occurred_at": "<dynamic>",
    }


def test_agentbox_operator_ticket_new_uses_runtime_subject_for_actor_and_slug(
    tmp_path: Path,
) -> None:
    store = FileStore(tmp_path / "store")
    codebase = store.create_codebase(
        owner="owner",
        name="repo",
        default_branch="main",
        codebase_id="codebase-1",
    )
    profile = AgentBoxOperatorProfile(
        store=store,
        authorizer=ResidentAuthorizer(ResidentConfig(allowed_user_ids=("user-1",))),
        agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
    )
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call(
                "ticket_new",
                {
                    "repo": "owner/repo",
                    "title": "Fix Discord Thin Path",
                    "body": "Keep the ticket concise.",
                    "tags": ["discord", "agentbox"],
                },
            ),
            FakeAgentStep.final("done"),
        ]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "file a ticket"},),
                system_prompt="test",
                subject=AuthorizationSubject(user_id="user-1", guild_id="g1", channel_id="c1"),
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result
    ticket_id = result["data"]["ticket"]["id"]
    ticket = store.load_ticket(ticket_id)

    assert result["ok"] is True
    assert result["data"]["ticket"] == {
        "id": ticket_id,
        "title": "Fix Discord Thin Path",
        "status": "open",
        "codebase_id": codebase.id,
        "slug": "fix-discord-thin-path",
        "tags": ["discord", "agentbox"],
        "filed_by_actor_id": "user-1",
    }
    assert result["data"]["action"] == "ticket_new"
    assert result["data"]["ticket_id"] == ticket_id
    assert result["data"]["next_state"] == "ticket_open"
    assert ticket is not None
    assert ticket.slug == "fix-discord-thin-path"
    assert ticket.filed_by_actor_id == "user-1"
    assert ticket.codebase_id == codebase.id


def test_agentbox_operator_ticket_new_rejects_unauthorized_runtime_subject(
    tmp_path: Path,
) -> None:
    store = FileStore(tmp_path / "store")
    store.create_codebase(
        owner="owner",
        name="repo",
        default_branch="main",
        codebase_id="codebase-1",
    )
    profile = AgentBoxOperatorProfile(
        store=store,
        authorizer=ResidentAuthorizer(ResidentConfig(allowed_user_ids=("user-1",))),
        agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
    )
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call("ticket_new", {"repo": "owner/repo", "title": "Denied"}),
            FakeAgentStep.final("done"),
        ]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "file a ticket"},),
                system_prompt="test",
                subject=AuthorizationSubject(user_id="user-2", guild_id="g1", channel_id="c1"),
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result

    assert result["ok"] is False
    assert result["data"]["authorization_denied"] is True
    assert store.list_tickets(codebase_id="codebase-1") == []


def test_agentbox_operator_chain_launch_requires_cloud_start_confirmation(
    tmp_path: Path,
) -> None:
    profile = AgentBoxOperatorProfile(
        authorizer=ResidentAuthorizer(
            ResidentConfig(
                allowed_user_ids=("admin-1",),
                admin_user_ids=("admin-1",),
            )
        ),
        confirmation_manager=ConfirmationManager(ResidentConfig()),
        agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
    )
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call(
                "chain_launch",
                {"repo": "owner/repo", "spec": "plans/chain.yaml", "operation_id": "chain-1"},
            ),
            FakeAgentStep.final("done"),
        ]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "launch chain"},),
                system_prompt="test",
                subject=AuthorizationSubject(user_id="admin-1", guild_id="g1", channel_id="c1"),
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result

    assert result["ok"] is False
    assert result["data"]["confirmation_required"] is True
    assert result["data"]["target_summary"] == "owner/repo plans/chain.yaml"
    assert "confirm cloud_start" in result["data"]["exact_phrase"]


def test_agentbox_operator_chain_launch_rejects_non_admin_runtime_subject(
    tmp_path: Path,
) -> None:
    profile = AgentBoxOperatorProfile(
        authorizer=ResidentAuthorizer(
            ResidentConfig(
                allowed_user_ids=("user-1",),
                admin_user_ids=("admin-1",),
            )
        ),
        confirmation_manager=ConfirmationManager(ResidentConfig(require_cloud_start_confirmation=False)),
        agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
    )
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call(
                "chain_launch",
                {"repo": "owner/repo", "spec": "plans/chain.yaml", "operation_id": "chain-1"},
            ),
            FakeAgentStep.final("done"),
        ]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "launch chain"},),
                system_prompt="test",
                subject=AuthorizationSubject(user_id="user-1", guild_id="g1", channel_id="c1"),
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result

    assert result["ok"] is False
    assert result["data"]["authorization_denied"] is True
    assert result["data"]["reason"] == "admin_required"


def test_agentbox_operator_chain_launch_invokes_adapter_after_confirmation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    agentbox_config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    handler = _FakeChainLaunchHandler(agentbox_config)
    monkeypatch.setattr("agentbox.resident_profile.load_operation_adapter", lambda kind: handler)
    resident_config = ResidentConfig(
        allowed_user_ids=("admin-1",),
        admin_user_ids=("admin-1",),
    )
    confirmation_manager = ConfirmationManager(resident_config)
    profile = AgentBoxOperatorProfile(
        authorizer=ResidentAuthorizer(resident_config),
        confirmation_manager=confirmation_manager,
        agentbox_config_factory=lambda: agentbox_config,
    )
    subject = AuthorizationSubject(user_id="admin-1", guild_id="g1", channel_id="c1")
    request = confirmation_manager.request_confirmation(
        subject=subject,
        action="cloud_start",
        target_summary="owner/repo plans/chain.yaml",
        metadata={"tool": "chain_launch"},
    )
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call(
                "chain_launch",
                {
                    "repo": "owner/repo",
                    "spec": "plans/chain.yaml",
                    "operation_id": "chain-1",
                    "base_ref": "main",
                    "confirmation_request_id": request.id,
                    "confirmation_phrase": request.exact_phrase,
                },
            ),
            FakeAgentStep.final("done"),
        ]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "launch chain"},),
                system_prompt="test",
                subject=subject,
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result

    assert result["ok"] is True
    assert handler.launch_calls == [
        {
            "operation_id": "chain-1",
            "repo_name": "owner/repo",
            "spec_path": Path("plans/chain.yaml"),
            "base_ref": "main",
        }
    ]
    assert result["data"] == {
        "profile": "agentbox_operator",
        "action": "chain_launch",
        "next_state": "operation_running",
        "operation_id": "chain-1",
        "operation_type": "megaplan_chain",
        "operation_state": "running",
        "launch_state": "running",
        "repo": "owner/repo",
        "resolved_spec_path": str(agentbox_config.workspace_root / "resolved-chain.yaml"),
        "validation": {
            "status": "passed",
            "spec_path": str(agentbox_config.workspace_root / "resolved-chain.yaml"),
        },
        "diagnostics": {"session": "agentbox-chain-1"},
    }


def test_agentbox_operator_chain_launch_returns_validation_diagnostics(
    tmp_path: Path,
    monkeypatch,
) -> None:
    agentbox_config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    handler = _FakeChainLaunchHandler(
        agentbox_config,
        error_diagnostics={"kind": "missing_spec", "message": "spec not found"},
    )
    monkeypatch.setattr("agentbox.resident_profile.load_operation_adapter", lambda kind: handler)
    profile = AgentBoxOperatorProfile(
        authorizer=ResidentAuthorizer(
            ResidentConfig(
                allowed_user_ids=("admin-1",),
                admin_user_ids=("admin-1",),
                require_cloud_start_confirmation=False,
            )
        ),
        agentbox_config_factory=lambda: agentbox_config,
    )
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call(
                "chain_launch",
                {"repo": "owner/repo", "spec": "missing.yaml", "operation_id": "chain-1"},
            ),
            FakeAgentStep.final("done"),
        ]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "launch chain"},),
                system_prompt="test",
                subject=AuthorizationSubject(user_id="admin-1", guild_id="g1", channel_id="c1"),
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result

    assert result["ok"] is False
    assert result["data"]["operation_id"] == "chain-1"
    assert result["data"]["operation_state"] == "failed"
    assert result["data"]["launch_state"] == "failed_before_running"
    assert result["data"]["repo"] == "owner/repo"
    assert result["data"]["validation"] == {"status": "failed"}
    assert result["data"]["diagnostics"] == {"kind": "missing_spec", "message": "spec not found"}


def test_agentbox_operator_chain_launch_persists_guardian_notification_metadata(
    tmp_path: Path,
    monkeypatch,
) -> None:
    agentbox_config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    handler = _FakeChainLaunchHandler(agentbox_config)
    monkeypatch.setattr("agentbox.resident_profile.load_operation_adapter", lambda kind: handler)
    store = FileStore(tmp_path / "store")
    conversation = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c1",
            active_epic_id="epic-1",
        ),
        idempotency_key="conversation-1",
    )
    profile = AgentBoxOperatorProfile(
        store=store,
        authorizer=ResidentAuthorizer(
            ResidentConfig(
                allowed_user_ids=("admin-1",),
                admin_user_ids=("admin-1",),
                require_cloud_start_confirmation=False,
            )
        ),
        agentbox_config_factory=lambda: agentbox_config,
    )
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call(
                "chain_launch",
                {"repo": "owner/repo", "spec": "plans/chain.yaml", "operation_id": "chain-1"},
            ),
            FakeAgentStep.final("done"),
        ]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id=conversation.id,
                messages=({"role": "user", "content": "launch chain"},),
                system_prompt="test",
                subject=AuthorizationSubject(user_id="admin-1", guild_id="g1", channel_id="c1"),
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result
    run = load_agentbox_operation(agentbox_config, "chain-1")

    assert result["ok"] is True
    assert run.metadata["guardian_notification_conversation_id"] == conversation.id
    assert (
        run.metadata["guardian_notification_conversation_key"]
        == "discord:guild:g1:channel:c1"
    )
    assert run.metadata["guardian_notifications_disabled"] is False


def test_agentbox_operator_chain_launch_disables_guardian_notifications_without_conversation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    agentbox_config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    handler = _FakeChainLaunchHandler(agentbox_config)
    monkeypatch.setattr("agentbox.resident_profile.load_operation_adapter", lambda kind: handler)
    store = FileStore(tmp_path / "store")
    profile = AgentBoxOperatorProfile(
        store=store,
        authorizer=ResidentAuthorizer(
            ResidentConfig(
                allowed_user_ids=("admin-1",),
                admin_user_ids=("admin-1",),
                require_cloud_start_confirmation=False,
            )
        ),
        agentbox_config_factory=lambda: agentbox_config,
    )
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call(
                "chain_launch",
                {"repo": "owner/repo", "spec": "plans/chain.yaml", "operation_id": "chain-1"},
            ),
            FakeAgentStep.final("done"),
        ]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="missing-conversation",
                messages=({"role": "user", "content": "launch chain"},),
                system_prompt="test",
                subject=AuthorizationSubject(user_id="admin-1", guild_id="g1", channel_id="c1"),
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result
    run = load_agentbox_operation(agentbox_config, "chain-1")

    assert result["ok"] is True
    assert run.metadata["guardian_notification_conversation_id"] == "missing-conversation"
    assert run.metadata["guardian_notifications_disabled"] is True
    assert (
        run.metadata["guardian_notifications_disabled_reason"]
        == "resident_conversation_not_found"
    )


def test_agentbox_operator_status_resolves_operation_before_shared_status_view(
    tmp_path: Path,
) -> None:
    agentbox_config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    create_agentbox_operation(
        agentbox_config,
        "chain-running",
        command="echo running",
        repo_names=["owner/repo"],
        launch_state="running",
        metadata={"resolved_spec_path": "owner/repo/chain.yaml"},
    )
    update_agentbox_operation(agentbox_config, "chain-running", state=OperationState.RUNNING)
    profile = AgentBoxOperatorProfile(agentbox_config_factory=lambda: agentbox_config)
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call("status", {"operation": "owner/repo"}),
            FakeAgentStep.final("done"),
        ]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "status owner/repo"},),
                system_prompt="test",
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result

    assert result["ok"] is True
    assert result["data"]["resolve"]["status"] == "single"
    assert result["data"]["resolve"]["operation"]["operation_id"] == "chain-running"
    assert result["data"]["status"]["operation_id"] == "chain-running"
    assert result["data"]["status"]["operation_state"] == "running"
    assert result["data"]["status"]["repo_names"] == ["owner/repo"]


def test_agentbox_operator_logs_resolves_operation_and_returns_bounded_metadata(
    tmp_path: Path,
) -> None:
    agentbox_config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    create_agentbox_operation(
        agentbox_config,
        "chain-logs",
        command="echo logs",
        repo_names=["owner/repo"],
        metadata={"resolved_spec_path": "owner/repo/chain.yaml"},
    )
    paths = ensure_run_dir(agentbox_config, "chain-logs")
    append_stdout(paths, "one\n")
    append_stdout(paths, "two\n")
    append_stdout(paths, "three\n")
    profile = AgentBoxOperatorProfile(agentbox_config_factory=lambda: agentbox_config)
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call(
                "logs",
                {"operation": "owner/repo", "stream": "stdout", "lines": 2},
            ),
            FakeAgentStep.final("done"),
        ]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "logs owner/repo"},),
                system_prompt="test",
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result

    assert result["ok"] is True
    assert result["data"]["resolve"]["status"] == "single"
    assert result["data"]["logs"]["operation_id"] == "chain-logs"
    assert result["data"]["logs"]["logs"][0]["text"] == "two\nthree\n"
    assert result["data"]["logs"]["logs"][0]["requested_lines"] == 2
    assert result["data"]["logs"]["logs"][0]["returned_lines"] == 2
    assert result["data"]["logs"]["logs"][0]["truncated"] is True
    assert result["data"]["logs"]["logs"][0]["source"] == "file"


def test_agentbox_operator_status_and_resolve_ask_one_clarifying_question_on_ambiguity(
    tmp_path: Path,
) -> None:
    agentbox_config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    create_agentbox_operation(
        agentbox_config,
        "alpha-chain",
        command="echo alpha",
        metadata={"resolved_spec_path": "shared/chain.yaml"},
    )
    create_agentbox_operation(
        agentbox_config,
        "beta-chain",
        command="echo beta",
        metadata={"resolved_spec_path": "shared/chain.yaml"},
    )
    create_agentbox_operation(
        agentbox_config,
        "gamma-chain",
        command="echo gamma",
        repo_names=["owner/repo"],
        launch_state="running",
        metadata={"resolved_spec_path": "unique/chain.yaml"},
    )
    profile = AgentBoxOperatorProfile(agentbox_config_factory=lambda: agentbox_config)
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call("status", {"operation": "shared"}),
            FakeAgentStep.call("resolve", {"kind": "operation", "query": "gamma-chain"}),
            FakeAgentStep.call("resolve", {"kind": "operation", "query": "shared"}),
            FakeAgentStep.call("resolve", {"kind": "operation", "query": "missing"}),
            FakeAgentStep.final("done"),
        ]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "status shared"},),
                system_prompt="test",
            ),
            profile.tools(),
        )
    )

    status_result = response.tool_calls[0].result
    resolve_single = response.tool_calls[1].result
    resolve_ambiguous = response.tool_calls[2].result
    resolve_missing = response.tool_calls[3].result

    assert status_result["ok"] is False
    assert status_result["message"] == "Which operation did you mean: alpha-chain, beta-chain?"
    assert status_result["data"]["resolve"]["status"] == "ambiguous"
    assert [row["operation_id"] for row in status_result["data"]["resolve"]["candidates"]] == [
        "alpha-chain",
        "beta-chain",
    ]
    assert resolve_single["ok"] is True
    assert resolve_single["message"] == "gamma-chain"
    assert resolve_single["data"]["operation_id"] == "gamma-chain"
    assert resolve_single["data"]["next_state"] == "resolved"
    assert resolve_single["data"]["resolve"] == {
        "status": "single",
        "query": "gamma-chain",
        "operation": {
            "operation_id": "gamma-chain",
            "operation_type": "agentbox_host",
            "operation_state": "pending",
            "launch_state": "running",
            "repo_names": ["owner/repo"],
            "matched_by": "operation_id_exact",
        },
        "candidates": [],
        "question": None,
    }
    assert resolve_ambiguous["ok"] is False
    assert resolve_ambiguous["message"] == "Which operation did you mean: alpha-chain, beta-chain?"
    assert resolve_ambiguous["data"]["resolve"] == status_result["data"]["resolve"]
    assert resolve_ambiguous["data"]["action"] == "resolve"
    assert resolve_ambiguous["data"]["next_state"] == "needs_clarification"
    assert resolve_missing["ok"] is False
    assert resolve_missing["message"] == "No AgentBox operation matched 'missing'. Which operation id should I use?"
    assert resolve_missing["data"]["next_state"] == "not_found"
    assert resolve_missing["data"]["resolve"] == {
        "status": "no_match",
        "query": "missing",
        "operation": None,
        "candidates": [],
        "question": "No AgentBox operation matched 'missing'. Which operation id should I use?",
    }


def test_agentbox_operator_resolve_shapes_repo_and_ticket_results_without_side_effects(
    tmp_path: Path,
) -> None:
    store = FileStore(tmp_path / "store")
    codebase = store.create_codebase(
        owner="owner",
        name="repo",
        default_branch="main",
        codebase_id="codebase-1",
    )
    other_codebase = store.create_codebase(
        owner="owner",
        name="repo-tools",
        default_branch="main",
        codebase_id="codebase-2",
    )
    ticket = store.create_ticket(
        codebase_id=codebase.id,
        title="Fix Discord Thin Path",
        body="Keep it thin.",
        tags=["discord"],
        slug="fix-discord-thin-path",
    )
    other_ticket = store.create_ticket(
        codebase_id=codebase.id,
        title="Fix Discord Fixtures",
        body="Keep fixtures thin.",
        tags=["discord"],
        slug="fix-discord-fixtures",
    )
    profile = AgentBoxOperatorProfile(
        store=store,
        agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
    )
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call("resolve", {"kind": "repo", "query": "owner/repo"}),
            FakeAgentStep.call("resolve", {"kind": "repo", "query": "repo"}),
            FakeAgentStep.call("resolve", {"kind": "ticket", "query": ticket.id}),
            FakeAgentStep.call("resolve", {"kind": "ticket", "query": "discord"}),
            FakeAgentStep.call("resolve", {"kind": "ticket", "query": "missing"}),
            FakeAgentStep.final("done"),
        ]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "resolve things"},),
                system_prompt="test",
            ),
            profile.tools(),
        )
    )

    repo_single = response.tool_calls[0].result
    repo_ambiguous = response.tool_calls[1].result
    ticket_single = response.tool_calls[2].result
    ticket_ambiguous = response.tool_calls[3].result
    ticket_missing = response.tool_calls[4].result

    assert repo_single["ok"] is True
    assert repo_single["data"] == {
        "profile": "agentbox_operator",
        "action": "resolve",
        "next_state": "resolved",
        "resolve": {
            "status": "single",
            "kind": "repo",
            "query": "owner/repo",
            "repo": {
                "codebase_id": codebase.id,
                "repo": "owner/repo",
                "owner": "owner",
                "name": "repo",
                "default_branch": "main",
            },
            "candidates": [],
            "question": None,
        },
    }
    assert repo_ambiguous["ok"] is False
    assert repo_ambiguous["data"]["resolve"]["status"] == "ambiguous"
    assert [row["codebase_id"] for row in repo_ambiguous["data"]["resolve"]["candidates"]] == [
        codebase.id,
        other_codebase.id,
    ]
    assert ticket_single["ok"] is True
    assert ticket_single["data"]["ticket_id"] == ticket.id
    assert ticket_single["data"]["resolve"]["ticket"]["title"] == "Fix Discord Thin Path"
    assert ticket_ambiguous["ok"] is False
    assert ticket_ambiguous["data"]["next_state"] == "needs_clarification"
    assert [row["ticket_id"] for row in ticket_ambiguous["data"]["resolve"]["candidates"]] == [
        other_ticket.id,
        ticket.id,
    ]
    assert ticket_missing["ok"] is False
    assert ticket_missing["data"]["next_state"] == "not_found"
    assert ticket_missing["data"]["resolve"] == {
        "status": "no_match",
        "kind": "ticket",
        "query": "missing",
        "ticket": None,
        "candidates": [],
        "question": "No AgentBox ticket matched 'missing'. Which ticket id should I use?",
    }


def test_agentbox_operator_runtime_exercises_all_six_v0_tools(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = FileStore(tmp_path / "store")
    store.create_codebase(
        owner="owner",
        name="repo",
        default_branch="main",
        codebase_id="codebase-1",
    )
    agentbox_config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    handler = _FakeChainLaunchHandler(agentbox_config)
    monkeypatch.setattr("agentbox.resident_profile.load_operation_adapter", lambda kind: handler)

    create_agentbox_operation(
        agentbox_config,
        "op-chain-1",
        operation_type="megaplan_chain",
        command=("fake", "chain"),
        repo_names=("owner/repo",),
        launch_state="running",
        metadata={"resolved_spec_path": str(agentbox_config.workspace_root / "resolved-chain.yaml")},
    )
    update_agentbox_operation(agentbox_config, "op-chain-1", state=OperationState.RUNNING)
    create_agentbox_operation(
        agentbox_config,
        "op-other",
        operation_type="megaplan_chain",
        command=("fake", "chain"),
        repo_names=("owner/repo",),
        launch_state="running",
        metadata={"resolved_spec_path": str(agentbox_config.workspace_root / "other-chain.yaml")},
    )
    update_agentbox_operation(agentbox_config, "op-other", state=OperationState.RUNNING)

    config = ResidentConfig(
        profile="agentbox_operator",
        allowed_user_ids=("admin-1",),
        admin_user_ids=("admin-1",),
        burst_idle_delay_s=0,
        burst_max_delay_s=1,
    )
    authorizer = ResidentAuthorizer(config)
    confirmation_manager = ConfirmationManager(config)
    subject = AuthorizationSubject(user_id="admin-1", guild_id="g1", channel_id="c1")
    request = confirmation_manager.request_confirmation(
        subject=subject,
        action="cloud_start",
        target_summary="owner/repo plans/chain.yaml",
        metadata={"tool": "chain_launch"},
    )

    outbound = _FakeOutboundSink()
    runtime = ResidentRuntime(
        config=config,
        authorizer=authorizer,
        store=store,
        profile=AgentBoxOperatorProfile(
            store=store,
            authorizer=authorizer,
            confirmation_manager=confirmation_manager,
            agentbox_config_factory=lambda: agentbox_config,
        ),
        runner=FakeAgentRunner(
            [
                FakeAgentStep.call(
                    "ticket_new",
                    {
                        "repo": "owner/repo",
                        "title": "Runtime coverage",
                        "body": "Exercise all six v0 tools.",
                        "tags": ["runtime"],
                    },
                ),
                FakeAgentStep.call(
                    "chain_launch",
                    {
                        "repo": "owner/repo",
                        "spec": "plans/chain.yaml",
                        "operation_id": "chain-1",
                        "confirmation_request_id": request.id,
                        "confirmation_phrase": request.exact_phrase,
                    },
                ),
                FakeAgentStep.call("status", {"operation": "chain-1"}),
                FakeAgentStep.call("logs", {"operation": "chain-1", "lines": 10}),
                FakeAgentStep.call("resolve", {"kind": "operation", "query": "op-chain-1"}),
                FakeAgentStep.call("resolve", {"kind": "operation", "query": "op"}),
                FakeAgentStep.call("help", {}),
                FakeAgentStep.final("all tools exercised"),
            ]
        ),
        outbound=outbound,
    )

    asyncio.run(
        _receive_and_flush(
            runtime,
            InboundEvent(
                idempotency_key="discord:message:all-tools",
                conversation_key="discord:guild:g1:channel:c1",
                subject=subject,
                content="run all tools",
                raw={
                    "discord_message_id": "all-tools",
                    "conversation_metadata": {"source": "test"},
                },
            ),
        )
    )

    turns = store.list_recent_turns(n=1)
    assert len(turns) == 1
    turn = turns[0]
    assert turn.status == "completed"

    ticket_call = store.search_tool_calls_by(tool_name="ticket_new", limit=1)[0]
    ticket_id = ticket_call.result["data"]["ticket_id"]
    assert ticket_id is not None
    ticket = store.load_ticket(ticket_id)
    assert ticket.title == "Runtime coverage"
    assert ticket.filed_by_actor_id == "admin-1"

    chain_call = store.search_tool_calls_by(tool_name="chain_launch", limit=1)[0]
    assert chain_call.result["ok"] is True
    assert chain_call.result["data"]["operation_id"] == "chain-1"
    assert chain_call.result["data"]["next_state"] == "operation_running"
    assert handler.launch_calls == [
        {
            "operation_id": "chain-1",
            "repo_name": "owner/repo",
            "spec_path": Path("plans/chain.yaml"),
            "base_ref": None,
        }
    ]

    status_call = store.search_tool_calls_by(tool_name="status", limit=1)[0]
    assert status_call.result["data"]["operation_id"] == "chain-1"
    assert status_call.result["data"]["next_state"] == "inspected_operation"

    logs_call = store.search_tool_calls_by(tool_name="logs", limit=1)[0]
    assert logs_call.result["data"]["operation_id"] == "chain-1"
    assert logs_call.result["data"]["next_state"] == "inspected_logs"

    resolve_calls = store.search_tool_calls_by(tool_name="resolve", limit=2)
    single_results = [
        call for call in resolve_calls
        if call.result["data"]["resolve"]["status"] == "single"
    ]
    ambiguous_results = [
        call for call in resolve_calls
        if call.result["data"]["resolve"]["status"] == "ambiguous"
    ]
    assert len(single_results) == 1
    assert len(ambiguous_results) == 1
    single_result = single_results[0].result
    ambiguous_result = ambiguous_results[0].result
    assert single_result["data"]["operation_id"] == "op-chain-1"
    assert single_result["data"]["next_state"] == "resolved"
    assert ambiguous_result["data"]["resolve"]["status"] == "ambiguous"
    assert ambiguous_result["data"]["next_state"] == "needs_clarification"
    assert "question" in ambiguous_result["data"]["resolve"]
    assert len(ambiguous_result["data"]["resolve"]["candidates"]) >= 2

    help_call = store.search_tool_calls_by(tool_name="help", limit=1)[0]
    assert help_call.result["data"]["next_state"] == "choose_v0_tool"
    assert any(tool["name"] == "chain_launch" for tool in help_call.result["data"]["tools"])

    assert outbound.sent
    assert outbound.sent[0].content == "all tools exercised"


def test_resident_runtime_injects_conversation_history_before_current_burst(
    tmp_path: Path,
) -> None:
    store = FileStore(tmp_path / "store")
    conversation = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c1",
            guild_id="g1",
            channel_id="c1",
        )
    )
    store.create_message(
        epic_id=None,
        conversation_id=conversation.id,
        direction="inbound",
        content="earlier user message",
        discord_message_id="earlier-user-message",
    )
    store.create_message(
        epic_id=None,
        conversation_id=conversation.id,
        direction="outbound",
        content="earlier bot reply",
    )
    config = ResidentConfig(
        profile="agentbox_operator",
        allowed_user_ids=("user-1",),
        history_window=10,
        burst_idle_delay_s=0,
        burst_max_delay_s=1,
    )
    authorizer = ResidentAuthorizer(config)
    runner = _RecordingFakeRunner([FakeAgentStep.final("ok")])
    runtime = ResidentRuntime(
        config=config,
        authorizer=authorizer,
        store=store,
        profile=AgentBoxOperatorProfile(
            store=store,
            authorizer=authorizer,
            agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
        ),
        runner=runner,
        outbound=_FakeOutboundSink(),
    )

    asyncio.run(
        _receive_and_flush(
            runtime,
            InboundEvent(
                idempotency_key="discord:message:h1",
                conversation_key="discord:guild:g1:channel:c1",
                subject=AuthorizationSubject(user_id="user-1", guild_id="g1", channel_id="c1"),
                content="current burst message",
                raw={"discord_message_id": "h1"},
            ),
        )
    )

    messages = runner.captured_request.messages
    assert [(message["role"], message["content"]) for message in messages[:2]] == [
        ("user", "earlier user message"),
        ("assistant", "earlier bot reply"),
    ]
    assert messages[2]["role"] == "user"
    assert "No parent message" in messages[2]["content"]
    assert messages[2]["content"].endswith(
        "Content truncated: no\ncurrent burst message"
    )
    # The already-persisted current burst is excluded from history (no double-count).
    assert sum(1 for m in messages if m["content"].endswith("\ncurrent burst message")) == 1


def test_resident_runtime_skips_history_when_window_is_zero(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    conversation = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c1",
            guild_id="g1",
            channel_id="c1",
        )
    )
    store.create_message(
        epic_id=None,
        conversation_id=conversation.id,
        direction="inbound",
        content="ignored history",
    )
    config = ResidentConfig(
        profile="agentbox_operator",
        allowed_user_ids=("user-1",),
        history_window=0,
        burst_idle_delay_s=0,
        burst_max_delay_s=1,
    )
    authorizer = ResidentAuthorizer(config)
    runner = _RecordingFakeRunner([FakeAgentStep.final("ok")])
    runtime = ResidentRuntime(
        config=config,
        authorizer=authorizer,
        store=store,
        profile=AgentBoxOperatorProfile(
            store=store,
            authorizer=authorizer,
            agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
        ),
        runner=runner,
        outbound=_FakeOutboundSink(),
    )

    asyncio.run(
        _receive_and_flush(
            runtime,
            InboundEvent(
                idempotency_key="discord:message:h0",
                conversation_key="discord:guild:g1:channel:c1",
                subject=AuthorizationSubject(user_id="user-1", guild_id="g1", channel_id="c1"),
                content="current burst message",
                raw={"discord_message_id": "h0"},
            ),
        )
    )

    assert len(runner.captured_request.messages) == 1
    assert runner.captured_request.messages[0]["content"].endswith(
        "Content truncated: no\ncurrent burst message"
    )


def test_agentbox_search_messages_scopes_to_current_conversation(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    c1 = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c1", guild_id="g1", channel_id="c1"
        )
    )
    c2 = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c2", guild_id="g1", channel_id="c2"
        )
    )
    store.create_message(
        epic_id=None, conversation_id=c1.id, direction="inbound", content="deploy the alpha service"
    )
    store.create_message(
        epic_id=None, conversation_id=c2.id, direction="inbound", content="deploy the beta service"
    )
    profile = AgentBoxOperatorProfile(
        store=store,
        authorizer=ResidentAuthorizer(ResidentConfig(allowed_user_ids=("user-1",))),
        agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
    )
    runner = FakeAgentRunner(
        [FakeAgentStep.call("search_messages", {"query": "deploy"}), FakeAgentStep.final("done")]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id=c1.id,
                messages=({"role": "user", "content": "search deploy"},),
                system_prompt="test",
                subject=AuthorizationSubject(user_id="user-1", guild_id="g1", channel_id="c1"),
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result
    assert result["ok"] is True
    assert result["data"]["action"] == "search_messages"
    assert [m["content"] for m in result["data"]["messages"]] == ["deploy the alpha service"]


def test_agentbox_subagent_returns_inline_result_on_configured_model(
    tmp_path: Path,
) -> None:
    config = ResidentConfig(
        allowed_user_ids=("user-1",),
        subagent_model_name="deepseek:deepseek-chat",
        subagent_models=("kimi:kimi-k2",),
    )
    store = FileStore(tmp_path / "store")
    profile = AgentBoxOperatorProfile(
        store=store,
        authorizer=ResidentAuthorizer(config),
        config=config,
        agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
    )
    fake_sub = _FakeSubRunner(AgentResponse(final_text="found 3 stale chains", tool_calls=()))
    profile._build_subagent_runner = lambda chosen, sub_config, max_calls: (fake_sub, "deepseek-chat")

    runner = FakeAgentRunner(
        [FakeAgentStep.call("subagent", {"prompt": "find stale chains"}), FakeAgentStep.final("summarized")]
    )
    _ctx_token = _set_runtime_subject(
        AuthorizationSubject(user_id="user-1", guild_id="g1", channel_id="c1")
    )
    try:
        response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "investigate"},),
                system_prompt="test",
                subject=AuthorizationSubject(user_id="user-1", guild_id="g1", channel_id="c1"),
            ),
            profile.tools(),
        )
    )
    finally:
        _TOOL_RUNTIME_CONTEXT.reset(_ctx_token)

    result = response.tool_calls[0].result
    assert result["ok"] is True
    assert result["data"]["action"] == "subagent"
    assert result["data"]["final_text"] == "found 3 stale chains"
    assert result["data"]["model"] == "deepseek-chat"
    # The subagent ran on the default model and got a registry WITHOUT subagent (no recursion).
    assert fake_sub.received_request.messages == ({"role": "user", "content": "find stale chains"},)
    assert "subagent" not in {t.name for t in fake_sub.received_tools.list()}


def test_agentbox_subagent_allows_allowlisted_model_override(tmp_path: Path) -> None:
    config = ResidentConfig(
        allowed_user_ids=("user-1",),
        subagent_model_name="deepseek:deepseek-chat",
        subagent_models=("kimi:kimi-k2",),
    )
    store = FileStore(tmp_path / "store")
    profile = AgentBoxOperatorProfile(
        store=store,
        authorizer=ResidentAuthorizer(config),
        config=config,
        agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
    )
    fake_sub = _FakeSubRunner(AgentResponse(final_text="kimi answers", tool_calls=()))
    captured: dict[str, object] = {}

    def build(chosen, sub_config, max_calls):
        captured["chosen"] = chosen
        captured["max_calls"] = max_calls
        return fake_sub, "kimi-k2"

    profile._build_subagent_runner = build

    runner = FakeAgentRunner(
        [FakeAgentStep.call("subagent", {"prompt": "x", "model": "kimi:kimi-k2"}), FakeAgentStep.final("done")]
    )

    _ctx_token = _set_runtime_subject(
        AuthorizationSubject(user_id="user-1", guild_id="g1", channel_id="c1")
    )
    try:
        response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "go"},),
                system_prompt="test",
                subject=AuthorizationSubject(user_id="user-1", guild_id="g1", channel_id="c1"),
            ),
            profile.tools(),
        )
    )
    finally:
        _TOOL_RUNTIME_CONTEXT.reset(_ctx_token)

    result = response.tool_calls[0].result
    assert result["ok"] is True
    assert captured["chosen"] == "kimi:kimi-k2"
    assert result["data"]["model"] == "kimi-k2"


def test_agentbox_subagent_rejects_model_outside_allowlist(tmp_path: Path) -> None:
    config = ResidentConfig(
        allowed_user_ids=("user-1",),
        subagent_model_name="deepseek:deepseek-chat",
        subagent_models=("kimi:kimi-k2",),
    )
    store = FileStore(tmp_path / "store")
    profile = AgentBoxOperatorProfile(
        store=store,
        authorizer=ResidentAuthorizer(config),
        config=config,
        agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
    )

    runner = FakeAgentRunner(
        [FakeAgentStep.call("subagent", {"prompt": "x", "model": "claude:opus"}), FakeAgentStep.final("done")]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "go"},),
                system_prompt="test",
                subject=AuthorizationSubject(user_id="user-1", guild_id="g1", channel_id="c1"),
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result
    assert result["ok"] is False
    assert result["data"]["requested"] == "claude:opus"
    assert result["data"]["default"] == "deepseek:deepseek-chat"
    assert result["data"]["allowed"] == ["kimi:kimi-k2"]


def test_agentbox_subagent_registry_excludes_subagent_tool(tmp_path: Path) -> None:
    profile = AgentBoxOperatorProfile(
        agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    )
    names = {tool.name for tool in profile._build_subagent_registry().list()}
    assert "subagent" not in names
    assert "search_messages" in names
    assert len(names) == len(AGENTBOX_OPERATOR_TOOL_NAMES) - 1


def test_file_store_list_conversation_messages_orders_and_excludes(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    c1 = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c1", guild_id="g1", channel_id="c1"
        )
    )
    c2 = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c2", guild_id="g1", channel_id="c2"
        )
    )
    ids = []
    for index in range(4):
        message = store.create_message(
            epic_id=None, conversation_id=c1.id, direction="inbound", content=f"msg-{index}"
        )
        ids.append(message.id)
    store.create_message(
        epic_id=None, conversation_id=c2.id, direction="inbound", content="other-convo msg-0"
    )

    rows = store.list_conversation_messages(c1.id, limit=10)
    assert [r.content for r in rows] == ["msg-0", "msg-1", "msg-2", "msg-3"]
    assert all(r.conversation_id == c1.id for r in rows)

    excluded = store.list_conversation_messages(c1.id, limit=10, exclude_ids=[ids[0]])
    assert [r.content for r in excluded] == ["msg-1", "msg-2", "msg-3"]

    last_two = store.list_conversation_messages(c1.id, limit=2)
    assert [r.content for r in last_two] == ["msg-2", "msg-3"]


class _FakeChainLaunchHandler:
    def __init__(
        self,
        config: AgentBoxConfig,
        *,
        error_diagnostics: dict[str, object] | None = None,
    ) -> None:
        self.config = config
        self.error_diagnostics = error_diagnostics
        self.launch_calls: list[dict[str, object]] = []

    def launch(
        self,
        config: AgentBoxConfig,
        operation_id: str,
        *,
        repo_name: str,
        spec_path: Path,
        base_ref: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> object:
        assert config == self.config
        self.launch_calls.append(
            {
                "operation_id": operation_id,
                "repo_name": repo_name,
                "spec_path": spec_path,
                "base_ref": base_ref,
            }
        )
        if self.error_diagnostics is not None:
            create_agentbox_operation(
                config,
                operation_id,
                operation_type="megaplan_chain",
                command=("fake", "chain"),
                repo_names=(repo_name,),
                launch_state="failed_before_running",
            metadata={
                **dict(metadata or {}),
                "validation": {"status": "failed"},
                "launch_diagnostics": dict(self.error_diagnostics),
            },
            )
            update_agentbox_operation(config, operation_id, state=OperationState.FAILED)
            raise _FakeChainLaunchError(
                str(self.error_diagnostics["message"]),
                diagnostics=dict(self.error_diagnostics),
            )

        resolved_spec_path = config.workspace_root / "resolved-chain.yaml"
        create_agentbox_operation(
            config,
            operation_id,
            operation_type="megaplan_chain",
            command=("fake", "chain"),
            repo_names=(repo_name,),
            launch_state="running",
            metadata={
                **dict(metadata or {}),
                "resolved_spec_path": str(resolved_spec_path),
                "validation": {
                    "status": "passed",
                    "spec_path": str(resolved_spec_path),
                },
            },
        )
        update_agentbox_operation(config, operation_id, state=OperationState.RUNNING)
        return SimpleNamespace(
            operation_id=operation_id,
            launch_state="running",
            resolved_spec_path=resolved_spec_path,
            host_result=SimpleNamespace(diagnostics={"session": f"agentbox-{operation_id}"}),
        )


class _FakeChainLaunchError(RuntimeError):
    def __init__(self, message: str, *, diagnostics: dict[str, object]) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics


class _FakeOutboundSink:
    def __init__(self) -> None:
        self.sent: list[OutboundMessage] = []

    async def send(self, message: OutboundMessage) -> None:
        self.sent.append(message)


class _ExplodingAgentRunner:
    async def run(self, request: AgentRequest, tools: object) -> object:
        raise AssertionError("resident runner should not execute for denied inbound events")


class _RecordingFakeRunner(FakeAgentRunner):
    """FakeAgentRunner that captures the AgentRequest it was handed."""

    def __init__(self, steps: list[FakeAgentStep]) -> None:
        super().__init__(steps)
        self.captured_request: AgentRequest | None = None

    async def run(self, request: AgentRequest, tools: object) -> AgentResponse:
        self.captured_request = request
        return await super().run(request, tools)


class _FakeSubRunner:
    """Stand-in for a resolved subagent runner; returns a scripted response."""

    def __init__(self, response: AgentResponse) -> None:
        self.response = response
        self.received_request: AgentRequest | None = None
        self.received_tools: object | None = None

    async def run(self, request: AgentRequest, tools: object) -> AgentResponse:
        self.received_request = request
        self.received_tools = tools
        return self.response


async def _receive_and_flush(runtime: ResidentRuntime, event: InboundEvent) -> None:
    await runtime.receive(event)
    await runtime.coalescer.flush_all()
