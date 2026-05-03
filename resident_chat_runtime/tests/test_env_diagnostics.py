from resident_chat_runtime.diagnostics import build_startup_diagnostics
from resident_chat_runtime.env import EnvSetting, read_env_settings
from resident_chat_runtime.health import HealthResult


def test_env_settings_parse_values_and_hide_secrets() -> None:
    values, statuses = read_env_settings(
        [
            EnvSetting("TOKEN", required=True, secret=True),
            EnvSetting("ENABLED", value_type="bool"),
            EnvSetting("PORT", value_type="int"),
            EnvSetting("OPTIONAL", default="fallback"),
        ],
        {"TOKEN": "secret-token", "ENABLED": "yes", "PORT": "1234"},
    )

    assert values == {
        "TOKEN": "secret-token",
        "ENABLED": True,
        "PORT": 1234,
        "OPTIONAL": "fallback",
    }
    assert {status.name: status.safe_value() for status in statuses}["TOKEN"] == "<configured>"


def test_env_settings_report_missing_required_and_bad_type() -> None:
    values, statuses = read_env_settings(
        [
            EnvSetting("REQUIRED", required=True),
            EnvSetting("COUNT", value_type="int"),
        ],
        {"COUNT": "not-int"},
    )

    assert values == {}
    errors = {status.name: status.error for status in statuses}
    assert errors["REQUIRED"] == "missing"
    assert "invalid literal" in errors["COUNT"]


def test_startup_diagnostics_do_not_expose_secret_values() -> None:
    _, statuses = read_env_settings(
        [EnvSetting("TOKEN", required=True, secret=True), EnvSetting("MISSING")],
        {"TOKEN": "secret-token"},
    )

    diagnostics = build_startup_diagnostics(
        env=statuses,
        health={"provider": HealthResult(ok=True, detail="ok", metadata={"configured": True})},
    )

    by_name = {item.name: item for item in diagnostics}
    assert by_name["env:TOKEN"].ok is True
    assert by_name["env:TOKEN"].value == "<configured>"
    assert "secret-token" not in repr(diagnostics)
    assert by_name["health:provider"].ok is True
