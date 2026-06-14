from __future__ import annotations

from datetime import UTC, datetime, timedelta

from arnold.pipelines.megaplan.resident import (
    AuthorizationSubject,
    ConfirmationManager,
    ResidentAuthorizer,
    ResidentConfig,
    StoreBackedConfirmationManager,
)
from arnold.pipelines.megaplan.store import FileStore


def test_resident_config_loads_allowlists_and_runtime_settings_from_env() -> None:
    config = ResidentConfig.from_env(
        {
            "MEGAPLAN_RESIDENT_MODE": "production",
            "MEGAPLAN_RESIDENT_ALLOWED_GUILDS": "g1,g2",
            "MEGAPLAN_RESIDENT_ALLOWED_CHANNELS": "c1, c2",
            "MEGAPLAN_RESIDENT_ALLOWED_USERS": "u1",
            "MEGAPLAN_RESIDENT_ADMIN_USERS": "admin",
            "MEGAPLAN_RESIDENT_MODEL_PROVIDER": "openrouter",
            "MEGAPLAN_RESIDENT_MODEL": "openai/gpt-5.4",
            "MEGAPLAN_RESIDENT_MODEL_API_KEY_ENV": "OPENROUTER_API_KEY",
            "MEGAPLAN_RESIDENT_MODEL_BASE_URL": "https://openrouter.ai/api/v1",
            "MEGAPLAN_RESIDENT_MODEL_TIMEOUT_S": "45.5",
            "MEGAPLAN_RESIDENT_MAX_TOOL_CALLS": "5",
            "MEGAPLAN_RESIDENT_SCHEDULER_POLL_S": "2.5",
            "MEGAPLAN_RESIDENT_SCHEDULER_BATCH_SIZE": "7",
            "MEGAPLAN_RESIDENT_STALE_CLAIM_TIMEOUT_S": "33",
            "MEGAPLAN_RESIDENT_STALE_TURN_TIMEOUT_S": "44",
            "MEGAPLAN_RESIDENT_STALE_CONTROL_CLAIM_TIMEOUT_S": "55",
            "MEGAPLAN_RESIDENT_BURST_IDLE_S": "0.25",
            "MEGAPLAN_RESIDENT_BURST_MAX_S": "3",
            "MEGAPLAN_RESIDENT_CONFIRMATION_EXPIRY_S": "60",
            "MEGAPLAN_RESIDENT_REQUIRE_CLOUD_CONFIRMATION": "false",
            "MEGAPLAN_RESIDENT_CLOUD_YAML": "ops/cloud.yaml",
            "MEGAPLAN_RESIDENT_EXPORT_ROOT": "ops/exports",
        }
    )

    assert config.is_production is True
    assert config.allowed_guild_ids == ("g1", "g2")
    assert config.allowed_channel_ids == ("c1", "c2")
    assert config.allowed_user_ids == ("u1",)
    assert config.admin_user_ids == ("admin",)
    assert config.model_provider == "openrouter"
    assert config.model_name == "openai/gpt-5.4"
    assert config.model_api_key_env == "OPENROUTER_API_KEY"
    assert config.model_base_url == "https://openrouter.ai/api/v1"
    assert config.model_timeout_s == 45.5
    assert config.max_tool_calls_per_turn == 5
    assert config.scheduler_poll_interval_s == 2.5
    assert config.scheduler_batch_size == 7
    assert config.stale_claim_timeout_s == 33
    assert config.stale_turn_timeout_s == 44
    assert config.stale_control_claim_timeout_s == 55
    assert config.burst_idle_delay_s == 0.25
    assert config.burst_max_delay_s == 3
    assert config.confirmation_expiry_s == 60
    assert config.require_cloud_start_confirmation is False
    assert str(config.cloud_yaml_path) == "ops/cloud.yaml"
    assert str(config.resident_export_root) == "ops/exports"


def test_resident_config_accepts_arnold_v2_discord_user_whitelist_fallback() -> None:
    config = ResidentConfig.from_env({"DISCORD_USER_WHITELIST": "u1, u2"})

    assert config.allowed_user_ids == ("u1", "u2")
    assert config.admin_user_ids == ("u1", "u2")


def test_authorizer_denies_unauthorized_before_execution_and_redacts_denial() -> None:
    authorizer = ResidentAuthorizer(
        ResidentConfig(
            allowed_guild_ids=("g1",),
            allowed_channel_ids=("c1",),
            allowed_user_ids=("u1",),
            admin_user_ids=("admin",),
        )
    )

    denied = authorizer.authorize_inbound(AuthorizationSubject(user_id="u2", guild_id="g1", channel_id="c1"))
    assert denied.allowed is False
    assert denied.reason == "user_not_allowed"
    assert denied.audit == {
        "user_id": "u2",
        "guild_id": "g1",
        "channel_id": "c1",
        "action": "inbound",
        "reason": "user_not_allowed",
        "occurred_at": denied.audit["occurred_at"],
    }
    assert "token" not in str(denied.audit).lower()
    assert authorizer.denials[-1].redacted() == denied.audit

    channel_denied = authorizer.authorize_inbound(
        AuthorizationSubject(user_id="u1", guild_id="g1", channel_id="c2")
    )
    assert channel_denied.allowed is False
    assert channel_denied.reason == "channel_not_allowed"


def test_cloud_start_requires_admin_and_exact_confirmation() -> None:
    config = ResidentConfig(
        allowed_user_ids=("admin", "user"),
        admin_user_ids=("admin",),
        confirmation_expiry_s=30,
    )
    authorizer = ResidentAuthorizer(config)
    manager = ConfirmationManager(config)

    ordinary = AuthorizationSubject(user_id="user")
    admin = AuthorizationSubject(user_id="admin")
    assert authorizer.authorize_action(ordinary, "cloud_start").reason == "admin_required"
    assert authorizer.authorize_action(admin, "cloud_start").allowed is True
    assert manager.required_for("cloud_start") is True
    for action in ("repo_write", "artifact_write", "export", "archive_logs", "reconcile_apply"):
        assert authorizer.authorize_action(ordinary, action).reason == "admin_required"
        assert authorizer.authorize_action(admin, action).allowed is True
        assert manager.required_for(action) is True

    now = datetime(2026, 5, 6, tzinfo=UTC)
    request = manager.request_confirmation(
        subject=admin,
        action="cloud_start",
        target_summary="chain production",
        metadata={"secret": "should-not-be-echoed"},
        now=now,
    )
    assert request.exact_phrase.startswith("confirm cloud_start ")
    assert "chain production" in request.exact_phrase
    assert "should-not-be-echoed" not in request.exact_phrase
    assert manager.confirm(request_id=request.id, subject=admin, phrase="confirm cloud_start wrong", now=now).allowed is False
    assert manager.confirm(request_id=request.id, subject=ordinary, phrase=request.exact_phrase, now=now).reason == "confirmation_user_mismatch"

    approved = manager.confirm(request_id=request.id, subject=admin, phrase=request.exact_phrase, now=now)
    assert approved.allowed is True
    assert approved.status == "approved"
    assert manager.pending() == ()

    expired = manager.request_confirmation(
        subject=admin,
        action="cloud_start",
        target_summary="bootstrap",
        now=now,
    )
    decision = manager.confirm(
        request_id=expired.id,
        subject=admin,
        phrase=expired.exact_phrase,
        now=now + timedelta(seconds=31),
    )
    assert decision.status == "expired"
    assert decision.allowed is False


def test_store_backed_confirmations_survive_restart_and_are_queryable(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    config = ResidentConfig(confirmation_expiry_s=30)
    now = datetime(2026, 5, 6, tzinfo=UTC)
    manager = StoreBackedConfirmationManager(config, store)
    request = manager.request_confirmation(
        subject=AuthorizationSubject(user_id="admin", guild_id="g1", channel_id="c1"),
        action="cloud_start",
        target_summary="chain production",
        now=now,
    )

    restarted = StoreBackedConfirmationManager(config, store)
    assert [pending.id for pending in restarted.pending()] == [request.id]

    approved = restarted.confirm(
        request_id=request.id,
        subject=AuthorizationSubject(user_id="admin", guild_id="g1", channel_id="c1"),
        phrase=request.exact_phrase,
        now=now,
    )
    assert approved.allowed is True
    assert restarted.pending() == ()
    assert store.list_scheduled_jobs(job_type="confirmation_expiry", status="pending") == []
    assert store.list_scheduled_jobs(job_type="confirmation_expiry", status="fired")
