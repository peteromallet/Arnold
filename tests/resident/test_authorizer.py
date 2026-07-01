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
