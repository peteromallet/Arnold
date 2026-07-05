from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from arnold.agent.tools import mcp_tool
from arnold.security import ActionResult, ActionVerdict, build_mcp_git_action_request


class _TextBlock:
    text = "ok"


class _FakeSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, tool_name: str, arguments: dict):
        self.calls.append((tool_name, arguments))
        return SimpleNamespace(isError=False, content=[_TextBlock()])


class _FakeBrokerClient:
    def __init__(self, result: ActionResult) -> None:
        self.result = result
        self.requests = []

    def evaluate_action(self, request):
        self.requests.append(request)
        return self.result


class _ErrorSession(_FakeSession):
    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    async def call_tool(self, tool_name: str, arguments: dict):
        self.calls.append((tool_name, arguments))
        return SimpleNamespace(
            isError=True,
            content=[SimpleNamespace(text=self._message)],
        )


def test_mcp_github_push_to_protected_branch_is_denied_before_handler(monkeypatch) -> None:
    session = _FakeSession()
    broker = _FakeBrokerClient(
        ActionResult(
            verdict=ActionVerdict.DENY,
            summary="Push to protected branch main is denied",
            metadata={"branch": "main", "action_type": "git_push"},
        )
    )
    monkeypatch.setitem(
        mcp_tool._servers,
        "github",
        SimpleNamespace(session=session),
    )
    monkeypatch.setattr(
        "arnold.security.git.BrokerClient.from_environment",
        lambda: broker,
    )

    handler = mcp_tool._make_tool_handler("github", "push_files", 1)
    payload = json.loads(handler({"owner": "acme", "repo": "service", "branch": "main"}))

    assert payload["broker"]["verdict"] == "deny"
    assert payload["broker"]["metadata"]["branch"] == "main"
    assert "protected branch main" in payload["error"]
    assert session.calls == []
    assert broker.requests[0].repo == "acme/service"
    assert broker.requests[0].branch == "main"


def test_mcp_github_allowed_mutation_returns_broker_refs_and_executes(monkeypatch) -> None:
    session = _FakeSession()
    broker = _FakeBrokerClient(
        ActionResult(
            verdict=ActionVerdict.ALLOW,
            summary="git_push allowed",
            action_id="act-123",
            effect_refs=("effect-456",),
            metadata={"branch": "feature/demo", "action_type": "git_push"},
        )
    )
    monkeypatch.setitem(
        mcp_tool._servers,
        "github",
        SimpleNamespace(session=session),
    )
    monkeypatch.setattr(
        "arnold.security.git.BrokerClient.from_environment",
        lambda: broker,
    )
    monkeypatch.setattr(mcp_tool, "_run_on_mcp_loop", lambda coro, timeout: asyncio.run(coro))

    handler = mcp_tool._make_tool_handler("github", "create_or_update_file", 1)
    payload = json.loads(
        handler({"owner": "acme", "repo": "service", "branch": "feature/demo"})
    )

    assert payload["result"] == "ok"
    assert payload["broker"]["verdict"] == "allow"
    assert payload["broker"]["action_id"] == "act-123"
    assert payload["broker"]["effect_refs"] == ["effect-456"]
    assert session.calls == [
        ("create_or_update_file", {"owner": "acme", "repo": "service", "branch": "feature/demo"})
    ]


def test_build_mcp_git_action_request_classifies_pr_create() -> None:
    request = build_mcp_git_action_request(
        "github",
        "create_pull_request",
        {"owner": "acme", "repo": "service", "base": "main"},
    )

    assert request is not None
    assert request.action_type == "git_pr_create"
    assert request.repo == "acme/service"
    assert request.branch == "main"


def test_non_sensitive_mcp_tool_preserves_existing_path(monkeypatch) -> None:
    session = _FakeSession()
    monkeypatch.setitem(
        mcp_tool._servers,
        "filesystem",
        SimpleNamespace(session=session),
    )
    monkeypatch.setattr(
        "arnold.security.git.BrokerClient.from_environment",
        lambda: (_ for _ in ()).throw(AssertionError("broker should not be used")),
    )
    monkeypatch.setattr(mcp_tool, "_run_on_mcp_loop", lambda coro, timeout: asyncio.run(coro))

    handler = mcp_tool._make_tool_handler("filesystem", "read_file", 1)
    payload = json.loads(handler({"path": "/tmp/example"}))

    assert payload == {"result": "ok"}
    assert session.calls == [("read_file", {"path": "/tmp/example"})]


def test_build_safe_env_strips_github_pat_in_broker_mode(monkeypatch) -> None:
    monkeypatch.setenv("ARNOLD_BROKER_SOCKET", "/tmp/arnold-broker.sock")
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("HOME", "/tmp/home")

    env = mcp_tool._build_safe_env(
        {
            "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_super_secret_value_1234567890",
            "GITHUB_TOKEN": "github_pat_super_secret_value_1234567890",
            "KEEP_ME": "visible",
        },
        server_name="github",
    )

    assert env["PATH"] == "/usr/bin"
    assert env["HOME"] == "/tmp/home"
    assert env["KEEP_ME"] == "visible"
    assert "GITHUB_PERSONAL_ACCESS_TOKEN" not in env
    assert "GITHUB_TOKEN" not in env


def test_load_mcp_config_strips_github_auth_fields_in_broker_mode(monkeypatch) -> None:
    monkeypatch.setenv("ARNOLD_BROKER_SOCKET", "/tmp/arnold-broker.sock")
    monkeypatch.setenv("GITHUB_PAT", "ghp_super_secret_value_1234567890")
    monkeypatch.setattr(
        "arnold.agent.hermes_cli.config.load_config",
        lambda: {
            "mcp_servers": {
                "github": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {
                        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PAT}",
                        "SAFE_FLAG": "1",
                    },
                    "headers": {
                        "Authorization": "Bearer ${GITHUB_PAT}",
                        "X-Trace": "trace-id",
                    },
                }
            }
        },
    )
    monkeypatch.setattr(
        "arnold.agent.hermes_cli.env_loader.load_hermes_dotenv",
        lambda: None,
    )

    config = mcp_tool._load_mcp_config()

    assert config["github"]["env"] == {"SAFE_FLAG": "1"}
    assert config["github"]["headers"] == {"X-Trace": "trace-id"}
    assert "ghp_super_secret_value_1234567890" not in json.dumps(config)


def test_mcp_handler_sanitizes_github_pat_error_text(monkeypatch) -> None:
    session = _ErrorSession(
        "Authentication failed for github_pat_abcdefghijklmnopqrstuvwxyz and token=ghu_secret_value_1234567890"
    )
    broker = _FakeBrokerClient(
        ActionResult(
            verdict=ActionVerdict.ALLOW,
            summary="git_push allowed",
            metadata={"branch": "feature/demo", "action_type": "git_push"},
        )
    )
    monkeypatch.setitem(
        mcp_tool._servers,
        "github",
        SimpleNamespace(session=session),
    )
    monkeypatch.setattr(
        "arnold.security.git.BrokerClient.from_environment",
        lambda: broker,
    )
    monkeypatch.setattr(mcp_tool, "_run_on_mcp_loop", lambda coro, timeout: asyncio.run(coro))

    handler = mcp_tool._make_tool_handler("github", "create_or_update_file", 1)
    payload = json.loads(
        handler({"owner": "acme", "repo": "service", "branch": "feature/demo"})
    )

    assert "github_pat_abcdefghijklmnopqrstuvwxyz" not in payload["error"]
    assert "ghu_secret_value_1234567890" not in payload["error"]
    assert "[REDACTED]" in payload["error"]


# ---------------------------------------------------------------------------
# T6: Git broker integration tests — force-push approval, master denial,
#     credential-free responses / env / config / logs
# ---------------------------------------------------------------------------

_CREDENTIAL_LIKE_RE = __import__("re").compile(
    r"gh[pousr]_[A-Za-z0-9_]{10,}"
    r"|sk-[A-Za-z0-9_-]{10,}"
    r"|github_pat_[A-Za-z0-9_]{10,}"
    r"|Bearer\s+[A-Za-z0-9_\-+=]{10,}",
)


def _assert_no_raw_credentials(text: str, *, label: str = "") -> None:
    """Fail if *text* contains credential-like substrings."""
    match = _CREDENTIAL_LIKE_RE.search(text)
    assert match is None, (
        f"{label+' ' if label else ''}unexpected credential-like pattern "
        f"'{match.group()}' in: {text[:200]}"
    )


def _assert_no_raw_credentials_in_json(payload: object, *, label: str = "") -> None:
    """Recursively scan a JSON-serializable payload for credential-like values."""
    serialized = json.dumps(payload, sort_keys=True)
    _assert_no_raw_credentials(serialized, label=label)


def test_mcp_github_force_push_requires_approval_before_execution(monkeypatch) -> None:
    """Force-push mutations must return approval_required and never reach the session."""
    session = _FakeSession()
    broker = _FakeBrokerClient(
        ActionResult(
            verdict=ActionVerdict.APPROVAL_REQUIRED,
            summary="git_force_push requires approval",
            action_id="act-force-1",
            metadata={
                "branch": "feature/demo",
                "action_type": "git_force_push",
                "force": True,
            },
        )
    )
    monkeypatch.setitem(
        mcp_tool._servers,
        "github",
        SimpleNamespace(session=session),
    )
    monkeypatch.setattr(
        "arnold.security.git.BrokerClient.from_environment",
        lambda: broker,
    )

    handler = mcp_tool._make_tool_handler("github", "push_files", 1)
    payload = json.loads(
        handler({"owner": "acme", "repo": "service", "branch": "feature/demo", "force": "true"})
    )

    # Broker verdict is approval_required
    assert payload["broker"]["verdict"] == "approval_required"
    assert payload["broker"]["action_id"] == "act-force-1"
    assert "requires approval" in payload["error"]

    # Handler must NOT have called through to the MCP session
    assert session.calls == []

    # Broker request metadata
    assert broker.requests[0].force is True
    assert broker.requests[0].action_type == "git_force_push"
    assert broker.requests[0].branch == "feature/demo"

    # Response must be free of raw credentials
    _assert_no_raw_credentials_in_json(payload, label="force-push response")


def test_mcp_github_push_to_master_is_denied_before_handler(monkeypatch) -> None:
    """Push to protected 'master' must be denied before reaching the MCP session."""
    session = _FakeSession()
    broker = _FakeBrokerClient(
        ActionResult(
            verdict=ActionVerdict.DENY,
            summary="Push to protected branch master is denied",
            metadata={"branch": "master", "action_type": "git_push"},
        )
    )
    monkeypatch.setitem(
        mcp_tool._servers,
        "github",
        SimpleNamespace(session=session),
    )
    monkeypatch.setattr(
        "arnold.security.git.BrokerClient.from_environment",
        lambda: broker,
    )

    handler = mcp_tool._make_tool_handler("github", "push_files", 1)
    payload = json.loads(
        handler({"owner": "acme", "repo": "service", "branch": "master"})
    )

    assert payload["broker"]["verdict"] == "deny"
    assert payload["broker"]["metadata"]["branch"] == "master"
    assert "protected branch master" in payload["error"]
    assert session.calls == []
    assert broker.requests[0].repo == "acme/service"
    assert broker.requests[0].branch == "master"

    # Response must be free of raw credentials
    _assert_no_raw_credentials_in_json(payload, label="master-deny response")


def test_allowed_mcp_git_response_is_credential_free(monkeypatch) -> None:
    """Even on ALLOW, the broker payload in the handler response must be free of raw credentials."""
    session = _FakeSession()
    # Simulate a broker that accidentally includes a raw token in metadata
    broker = _FakeBrokerClient(
        ActionResult(
            verdict=ActionVerdict.ALLOW,
            summary="git_push allowed (token=ghp_1a2b3c4d5e6f7g8h9i0j)",
            action_id="act-raw-check",
            effect_refs=("effect-1",),
            metadata={
                "branch": "feature/x",
                "action_type": "git_push",
                "raw_token_value": "ghp_super_secret_value_1234567890",
            },
        )
    )
    monkeypatch.setitem(
        mcp_tool._servers,
        "github",
        SimpleNamespace(session=session),
    )
    monkeypatch.setattr(
        "arnold.security.git.BrokerClient.from_environment",
        lambda: broker,
    )
    monkeypatch.setattr(mcp_tool, "_run_on_mcp_loop", lambda coro, timeout: asyncio.run(coro))

    handler = mcp_tool._make_tool_handler("github", "create_or_update_file", 1)
    payload = json.loads(
        handler({"owner": "acme", "repo": "service", "branch": "feature/x"})
    )

    # The ActionResult __post_init__ should have already sanitized summary and metadata.
    # Verify that the handler response JSON contains no raw credential fragments.
    _assert_no_raw_credentials_in_json(payload, label="allowed response")

    # Specifically verify the known injected patterns are not present
    serialized = json.dumps(payload)
    assert "ghp_super_secret_value_1234567890" not in serialized
    assert "ghp_1a2b3c4d5e6f7g8h9i0j" not in serialized


def test_deny_response_is_credential_free(monkeypatch) -> None:
    """Deny responses must not leak credentials injected into broker summary/metadata."""
    broker = _FakeBrokerClient(
        ActionResult(
            verdict=ActionVerdict.DENY,
            summary="Denied: API_KEY=sk-abcdefghijklmnopqrstuv",
            metadata={
                "branch": "main",
                "action_type": "git_push",
                "leaked": "Bearer ghp_super_secret_value_1234567890",
            },
        )
    )
    monkeypatch.setitem(
        mcp_tool._servers,
        "github",
        SimpleNamespace(session=_FakeSession()),
    )
    monkeypatch.setattr(
        "arnold.security.git.BrokerClient.from_environment",
        lambda: broker,
    )

    handler = mcp_tool._make_tool_handler("github", "push_files", 1)
    payload = json.loads(
        handler({"owner": "acme", "repo": "service", "branch": "main"})
    )

    _assert_no_raw_credentials_in_json(payload, label="deny response")
    serialized = json.dumps(payload)
    assert "sk-abcdefghijklmnopqrstuv" not in serialized
    assert "ghp_super_secret_value_1234567890" not in serialized


def test_approval_required_response_is_credential_free(monkeypatch) -> None:
    """Approval-required responses must not leak credentials."""
    broker = _FakeBrokerClient(
        ActionResult(
            verdict=ActionVerdict.APPROVAL_REQUIRED,
            summary="Force push needs approval (secret=ghu_abcdef1234567890)",
            action_id="act-approve-1",
            metadata={
                "branch": "feature/z",
                "action_type": "git_force_push",
                "force": True,
                "gh_token": "github_pat_11ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            },
        )
    )
    monkeypatch.setitem(
        mcp_tool._servers,
        "github",
        SimpleNamespace(session=_FakeSession()),
    )
    monkeypatch.setattr(
        "arnold.security.git.BrokerClient.from_environment",
        lambda: broker,
    )

    handler = mcp_tool._make_tool_handler("github", "push_files", 1)
    payload = json.loads(
        handler({"owner": "acme", "repo": "service", "branch": "feature/z", "force": "true"})
    )

    _assert_no_raw_credentials_in_json(payload, label="approval-required response")
    serialized = json.dumps(payload)
    assert "ghu_abcdef1234567890" not in serialized
    assert "github_pat_11ABCDEFGHIJKLMNOPQRSTUVWXYZ" not in serialized


def test_env_payload_is_credential_free(monkeypatch) -> None:
    """_build_safe_env must never include raw credential values even with mixed config."""
    monkeypatch.setenv("ARNOLD_BROKER_SOCKET", "/tmp/arnold-broker.sock")
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_super_secret_value_1234567890")
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "ghp_another_secret_token_abc")
    # MY_CUSTOM_VAR is not a safe env key; it should NOT appear

    env = mcp_tool._build_safe_env(
        {
            "CUSTOM": "also-benign",
            "GITHUB_TOKEN": "should_be_removed",
        },
        server_name="github",
    )

    # Convert to JSON for scanning
    _assert_no_raw_credentials_in_json(env, label="safe env payload")

    # Specific known secrets must not appear
    env_str = json.dumps(env)
    assert "ghp_super_secret_value_1234567890" not in env_str
    assert "ghp_another_secret_token_abc" not in env_str
    assert "should_be_removed" not in env_str
    assert env["CUSTOM"] == "also-benign"
    assert "MY_CUSTOM_VAR" not in env  # not a safe env key


def test_handler_log_output_free_of_raw_credentials(monkeypatch, caplog) -> None:
    """Handler log output (including error paths) must not contain raw credential patterns."""
    import logging

    caplog.set_level(logging.WARNING, logger="arnold.agent.tools.mcp_tool")
    caplog.set_level(logging.WARNING, logger="arnold.security.broker_client")

    session = _ErrorSession(
        "Push rejected: remote contains token=ghp_super_secret_value_1234567890"
    )
    broker = _FakeBrokerClient(
        ActionResult(
            verdict=ActionVerdict.ALLOW,
            summary="git_push allowed",
            metadata={"branch": "feature/demo", "action_type": "git_push"},
        )
    )
    monkeypatch.setitem(
        mcp_tool._servers,
        "github",
        SimpleNamespace(session=session),
    )
    monkeypatch.setattr(
        "arnold.security.git.BrokerClient.from_environment",
        lambda: broker,
    )
    monkeypatch.setattr(mcp_tool, "_run_on_mcp_loop", lambda coro, timeout: asyncio.run(coro))

    handler = mcp_tool._make_tool_handler("github", "create_or_update_file", 1)
    handler({"owner": "acme", "repo": "service", "branch": "feature/demo"})

    # Collect all log output
    log_text = "\n".join(record.message for record in caplog.records)

    # Logs must be free of raw credential patterns
    _assert_no_raw_credentials(log_text, label="handler log output")

    # Specifically the error text with raw token must not appear in logs
    assert "ghp_super_secret_value_1234567890" not in log_text


def test_config_load_is_credential_free_in_broker_mode(monkeypatch) -> None:
    """MCP config loading must never include raw PAT values when broker mode is active."""
    monkeypatch.setenv("ARNOLD_BROKER_SOCKET", "/tmp/arnold-broker.sock")
    monkeypatch.setenv("GITHUB_PAT", "ghp_super_secret_value_1234567890")
    monkeypatch.setenv("GH_TOKEN_EXTRA", "ghs_another_token_value_xyz")

    monkeypatch.setattr(
        "arnold.agent.hermes_cli.config.load_config",
        lambda: {
            "mcp_servers": {
                "github": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {
                        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PAT}",
                        "GITHUB_TOKEN": "ghp_direct_inline_token_abc",
                        "GH_TOKEN": "${GH_TOKEN_EXTRA}",
                        "SAFE_VAR": "visible",
                    },
                    "headers": {
                        "Authorization": "Bearer ${GITHUB_PAT}",
                        "x-github-token": "ghp_header_token_def",
                        "X-Trace": "trace-123",
                    },
                }
            }
        },
    )
    monkeypatch.setattr(
        "arnold.agent.hermes_cli.env_loader.load_hermes_dotenv",
        lambda: None,
    )

    config = mcp_tool._load_mcp_config()

    # Scan entire config as JSON
    _assert_no_raw_credentials_in_json(config, label="loaded MCP config")

    config_str = json.dumps(config)
    assert "ghp_super_secret_value_1234567890" not in config_str
    assert "ghs_another_token_value_xyz" not in config_str
    assert "ghp_direct_inline_token_abc" not in config_str
    assert "ghp_header_token_def" not in config_str
    assert "Bearer" not in config_str

    # Safe values must be preserved
    assert config.get("github", {}).get("env", {}).get("SAFE_VAR") == "visible"
    assert config.get("github", {}).get("headers", {}).get("X-Trace") == "trace-123"


def test_handler_response_across_all_verdicts_is_credential_free(monkeypatch) -> None:
    """Comprehensive scan: ALLOW + DENY + APPROVAL_REQUIRED paths all return clean JSON."""
    scenarios = [
        # (verdict, tool_name, args, expected_error_keyword)
        (
            ActionVerdict.ALLOW,
            "create_or_update_file",
            {"owner": "a", "repo": "r", "branch": "feature/safe"},
            "result",
            _FakeSession(),
        ),
        (
            ActionVerdict.DENY,
            "push_files",
            {"owner": "a", "repo": "r", "branch": "main"},
            "Decision: deny",
            _FakeSession(),
        ),
        (
            ActionVerdict.APPROVAL_REQUIRED,
            "push_files",
            {"owner": "a", "repo": "r", "branch": "feature/force", "force": "true"},
            "Decision: approval_required",
            _FakeSession(),
        ),
    ]

    for verdict, tool_name, args, expected_keyword, session in scenarios:
        broker = _FakeBrokerClient(
            ActionResult(
                verdict=verdict,
                summary=f"Decision: {verdict.value} (backup=ghp_t0k3n_s3cr3t)",
                action_id=f"act-{verdict.value}" if verdict is not ActionVerdict.DENY else None,
                metadata={
                    "branch": args.get("branch", "unknown"),
                    "action_type": "git_push",
                    "secret_backup": "sk-proj-deadbeef1234567890",
                },
            )
        )
        monkeypatch.setitem(
            mcp_tool._servers,
            "github",
            SimpleNamespace(session=session),
        )
        monkeypatch.setattr(
            "arnold.security.git.BrokerClient.from_environment",
            lambda b=broker: b,
        )
        monkeypatch.setattr(
            mcp_tool, "_run_on_mcp_loop", lambda coro, timeout: asyncio.run(coro),
        )

        handler = mcp_tool._make_tool_handler("github", tool_name, 1)
        payload = json.loads(handler(args))

        _assert_no_raw_credentials_in_json(
            payload, label=f"verdict={verdict.value} response"
        )

        serialized = json.dumps(payload)
        assert "ghp_t0k3n_s3cr3t" not in serialized
        assert "sk-proj-deadbeef1234567890" not in serialized

        if expected_keyword in ("result",):
            assert expected_keyword in payload
        else:
            assert expected_keyword in payload.get("error", "")
