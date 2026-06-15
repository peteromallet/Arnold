"""Tests for ``arnold.runtime.settings`` (T6 / SC6)."""

from __future__ import annotations

import dataclasses

import pytest

from arnold.runtime.settings import (
    EffectiveSetting,
    GloballyAggregatedSettings,
    InheritableSettings,
    IsolationSettings,
    SettingSource,
    StageLocalSettings,
)


class TestSettingSourceEnumeration:
    def test_exactly_five_sources(self) -> None:
        assert len(list(SettingSource)) == 5

    def test_all_prescribed_source_values_present(self) -> None:
        values = {s.value for s in SettingSource}
        assert values == {
            "arnold_default",
            "plugin_default",
            "profile",
            "run_override",
            "env_override",
        }

    def test_source_values_are_strings(self) -> None:
        for src in SettingSource:
            assert isinstance(src.value, str)


class TestDataclassFreezing:
    def test_inheritable_settings_is_frozen(self) -> None:
        s = InheritableSettings()
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.wall_timeout_s = 1.0  # type: ignore[misc]

    def test_globally_aggregated_settings_is_frozen(self) -> None:
        s = GloballyAggregatedSettings()
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.max_workers = 4  # type: ignore[misc]

    def test_stage_local_settings_is_frozen(self) -> None:
        s = StageLocalSettings(stage_id="my_stage")
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.stage_id = "other"  # type: ignore[misc]

    def test_isolation_settings_is_frozen(self) -> None:
        s = IsolationSettings()
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.isolation_mode = "subprocess_isolated"  # type: ignore[misc]

    def test_effective_setting_is_frozen(self) -> None:
        s = EffectiveSetting(
            key="wall_timeout_s",
            value=30.0,
            source=SettingSource.ARNOLD_DEFAULT,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.value = 99.0  # type: ignore[misc]


class TestCategoryExclusivity:
    """No field name may appear in more than one category dataclass."""

    def _field_names(self, cls: type) -> set[str]:
        return {f.name for f in dataclasses.fields(cls)}

    def test_no_key_in_two_categories(self) -> None:
        categories = [
            InheritableSettings,
            GloballyAggregatedSettings,
            StageLocalSettings,
            IsolationSettings,
        ]
        seen: dict[str, str] = {}
        for cls in categories:
            for name in self._field_names(cls):
                assert name not in seen, (
                    f"Field {name!r} appears in both {seen[name]} and {cls.__name__}"
                )
                seen[name] = cls.__name__

    def test_exactly_four_categories(self) -> None:
        categories = [
            InheritableSettings,
            GloballyAggregatedSettings,
            StageLocalSettings,
            IsolationSettings,
        ]
        assert len(categories) == 4
        for cls in categories:
            assert dataclasses.is_dataclass(cls)


class TestModuleDocstring:
    def test_module_docstring_mentions_in_scope(self) -> None:
        import arnold.runtime.settings as mod
        assert mod.__doc__ is not None
        assert "IN SCOPE" in mod.__doc__

    def test_module_docstring_mentions_deferred(self) -> None:
        import arnold.runtime.settings as mod
        assert mod.__doc__ is not None
        assert "DEFERRED" in mod.__doc__

    def test_module_docstring_names_target_milestones(self) -> None:
        import arnold.runtime.settings as mod
        assert mod.__doc__ is not None
        # Must name at least one target milestone label (M3a, M5a, M3c, M7)
        doc = mod.__doc__
        assert any(tag in doc for tag in ("M3a", "M3c", "M5a", "M7")), (
            "Module docstring must enumerate at least one DEFERRED target milestone"
        )
