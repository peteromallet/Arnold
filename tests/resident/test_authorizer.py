from __future__ import annotations

from arnold_pipelines.megaplan.resident.auth import AuthorizationSubject, ResidentAuthorizer
from arnold_pipelines.megaplan.resident.config import ResidentConfig


def test_authorizer_allows_allowlisted_user_dm_when_guilds_are_restricted() -> None:
    authorizer = ResidentAuthorizer(
        ResidentConfig(
            allowed_guild_ids=("guild-1",),
            allowed_user_ids=("user-1",),
        )
    )

    decision = authorizer.authorize_inbound(
        AuthorizationSubject(user_id="user-1", guild_id=None, channel_id="dm-channel")
    )

    assert decision.allowed is True


def test_authorizer_still_rejects_wrong_guild_message() -> None:
    authorizer = ResidentAuthorizer(
        ResidentConfig(
            allowed_guild_ids=("guild-1",),
            allowed_user_ids=("user-1",),
        )
    )

    decision = authorizer.authorize_inbound(
        AuthorizationSubject(user_id="user-1", guild_id="guild-2", channel_id="channel-1")
    )

    assert decision.allowed is False
    assert decision.reason == "guild_not_allowed"


def test_authorizer_accepts_escalation_action_kinds_for_allowed_subject() -> None:
    authorizer = ResidentAuthorizer(
        ResidentConfig(
            allowed_user_ids=("user-1",),
            allowed_channel_ids=("channel-1",),
        )
    )
    subject = AuthorizationSubject(user_id="user-1", channel_id="channel-1")

    assert authorizer.authorize_action(subject, "escalation_reply").allowed is True
    assert authorizer.authorize_action(subject, "escalation_resolve").allowed is True
