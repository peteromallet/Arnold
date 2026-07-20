from __future__ import annotations

from arnold_pipelines.megaplan.resident.config import ResidentConfig


def test_special_requests_defaults() -> None:
    config = ResidentConfig()
    assert config.special_requests_enabled is True
    assert config.special_requests_interval_s == 21600
    assert str(config.special_requests_todo_path) == ".megaplan/resident/vp_todo_list.json"
    assert config.special_requests_conversation_key is None
    assert config.special_requests_subject_user_id is None
    assert config.special_requests_subagent_toolsets == "file,web,terminal"
    assert config.special_requests_subagent_timeout_s is None
    assert config.special_requests_subagent_max_tokens == 65536


def test_special_requests_from_env() -> None:
    env = {
        "MEGAPLAN_RESIDENT_SPECIAL_REQUESTS_ENABLED": "true",
        "MEGAPLAN_RESIDENT_SPECIAL_REQUESTS_INTERVAL_S": "60",
        "MEGAPLAN_RESIDENT_SPECIAL_REQUESTS_TODO_PATH": "/tmp/foo.json",
        "MEGAPLAN_RESIDENT_SPECIAL_REQUESTS_CONVERSATION_KEY": "discord:guild:g:channel:c",
        "MEGAPLAN_RESIDENT_SPECIAL_REQUESTS_SUBJECT_USER_ID": "admin-1",
        "MEGAPLAN_RESIDENT_SPECIAL_REQUESTS_SUBAGENT_TOOLSETS": "file,web",
        "MEGAPLAN_RESIDENT_SPECIAL_REQUESTS_SUBAGENT_TIMEOUT_S": "30",
        "MEGAPLAN_RESIDENT_SPECIAL_REQUESTS_SUBAGENT_MAX_TOKENS": "4096",
    }
    config = ResidentConfig.from_env(env)
    assert config.special_requests_enabled is True
    assert config.special_requests_interval_s == 60
    assert str(config.special_requests_todo_path) == "/tmp/foo.json"
    assert config.special_requests_conversation_key == "discord:guild:g:channel:c"
    assert config.special_requests_subject_user_id == "admin-1"
    assert config.special_requests_subagent_toolsets == "file,web"
    assert config.special_requests_subagent_timeout_s is None
    assert config.model_timeout_s is None
    assert config.special_requests_subagent_max_tokens == 4096


def test_special_requests_enabled_by_default_in_env() -> None:
    config = ResidentConfig.from_env({})
    assert config.special_requests_enabled is True
    assert config.special_requests_conversation_key is None


def test_special_requests_can_be_disabled_in_env() -> None:
    config = ResidentConfig.from_env(
        {"MEGAPLAN_RESIDENT_SPECIAL_REQUESTS_ENABLED": "false"}
    )
    assert config.special_requests_enabled is False
