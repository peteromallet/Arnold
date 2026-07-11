"""Tests for ``north_star_critical: true`` robustness validation.

Covers chain-level and milestone-level ``north_star_critical`` settings,
milestone robustness precedence, clear ``CliError`` messages for ``bare``/``light``
rejection, and backward compatibility when the field is omitted.
"""

from __future__ import annotations

import pytest

from arnold_pipelines.megaplan.chain.spec import ChainSpec
from arnold_pipelines.megaplan.types import CliError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chain(
    driver_robustness: str = "full",
    milestones: list[dict] | None = None,
    driver_north_star_critical: bool | None = None,
) -> dict:
    """Build a minimal chain spec dict for testing north_star_critical."""
    driver: dict = {"robustness": driver_robustness}
    if driver_north_star_critical is not None:
        driver["north_star_critical"] = driver_north_star_critical
    spec: dict = {"driver": driver, "milestones": milestones or []}
    return spec


def _ms(
    label: str = "m1",
    robustness: str | None = None,
    north_star_critical: bool | None = None,
) -> dict:
    """Build a minimal milestone dict."""
    ms: dict = {"label": label, "idea": f"Idea for {label}."}
    if robustness is not None:
        ms["robustness"] = robustness
    if north_star_critical is not None:
        ms["north_star_critical"] = north_star_critical
    return ms


# ---------------------------------------------------------------------------
# Chain-level north_star_critical
# ---------------------------------------------------------------------------

class TestChainNorthStarCriticalAcceptsValidRobustness:
    """Chain ``north_star_critical: true`` accepts ``full``, ``thorough``, ``extreme``."""

    @pytest.mark.parametrize("robustness", ["full", "thorough", "extreme"])
    def test_chain_critical_accepts(self, robustness: str) -> None:
        spec = ChainSpec.from_dict(
            _make_chain(
                driver_robustness=robustness,
                driver_north_star_critical=True,
                milestones=[_ms("m1")],
            )
        )
        assert spec.north_star_critical is True
        assert spec.robustness == robustness

    @pytest.mark.parametrize("robustness", ["standard", "superrobust"])
    def test_chain_critical_accepts_aliases(self, robustness: str) -> None:
        """Aliases ``standard``→``full``, ``superrobust``→``extreme`` are accepted."""
        spec = ChainSpec.from_dict(
            _make_chain(
                driver_robustness=robustness,
                driver_north_star_critical=True,
                milestones=[_ms("m1")],
            )
        )
        assert spec.north_star_critical is True


class TestChainNorthStarCriticalRejectsBareLight:
    """Chain ``north_star_critical: true`` rejects ``bare`` and ``light``."""

    @pytest.mark.parametrize("robustness", ["bare", "light"])
    def test_chain_critical_rejects(self, robustness: str) -> None:
        with pytest.raises(
            CliError,
            match=r"north_star_critical enabled but effective robustness",
        ):
            ChainSpec.from_dict(
                _make_chain(
                    driver_robustness=robustness,
                    driver_north_star_critical=True,
                    milestones=[_ms("m1")],
                )
            )

    @pytest.mark.parametrize("robustness,label", [("bare", "bare"), ("light", "light")])
    def test_chain_critical_rejects_message_includes_robustness(
        self, robustness: str, label: str
    ) -> None:
        """Error message names the rejected robustness level."""
        with pytest.raises(CliError, match=rf"is {label!r}"):
            ChainSpec.from_dict(
                _make_chain(
                    driver_robustness=robustness,
                    driver_north_star_critical=True,
                    milestones=[_ms("m1")],
                )
            )

    @pytest.mark.parametrize("alias", ["tiny"])
    def test_chain_critical_rejects_alias_tiny(self, alias: str) -> None:
        """Alias ``tiny`` → ``bare`` is also rejected."""
        with pytest.raises(CliError, match=r"north_star_critical enabled"):
            ChainSpec.from_dict(
                _make_chain(
                    driver_robustness=alias,
                    driver_north_star_critical=True,
                    milestones=[_ms("m1")],
                )
            )

    def test_chain_critical_rejects_code_is_invalid_spec(self) -> None:
        """CliError code is ``invalid_spec``."""
        with pytest.raises(CliError) as exc_info:
            ChainSpec.from_dict(
                _make_chain(
                    driver_robustness="bare",
                    driver_north_star_critical=True,
                    milestones=[_ms("m1")],
                )
            )
        assert exc_info.value.code == "invalid_spec"

    def test_chain_critical_rejects_message_mentions_full_requirement(self) -> None:
        """Error message tells user the minimum required robustness."""
        with pytest.raises(
            CliError, match=r"requires at least `full` robustness"
        ):
            ChainSpec.from_dict(
                _make_chain(
                    driver_robustness="light",
                    driver_north_star_critical=True,
                    milestones=[_ms("m1")],
                )
            )


# ---------------------------------------------------------------------------
# Milestone-level north_star_critical
# ---------------------------------------------------------------------------

class TestMilestoneNorthStarCriticalAcceptsValidRobustness:
    """Milestone ``north_star_critical: true`` accepts ``full``/``thorough``/``extreme``."""

    @pytest.mark.parametrize("robustness", ["full", "thorough", "extreme"])
    def test_milestone_critical_accepts_explicit_robustness(self, robustness: str) -> None:
        spec = ChainSpec.from_dict(
            _make_chain(
                driver_robustness="bare",  # driver is bare but milestone overrides
                milestones=[_ms("m1", robustness=robustness, north_star_critical=True)],
            )
        )
        assert spec.milestones[0].north_star_critical is True

    @pytest.mark.parametrize("robustness", ["standard", "superrobust"])
    def test_milestone_critical_accepts_aliases(self, robustness: str) -> None:
        spec = ChainSpec.from_dict(
            _make_chain(
                driver_robustness="bare",
                milestones=[_ms("m1", robustness=robustness, north_star_critical=True)],
            )
        )
        assert spec.milestones[0].north_star_critical is True

    def test_milestone_critical_falls_back_to_driver_full(self) -> None:
        """Milestone with no explicit robustness inherits driver ``full`` → accepted."""
        spec = ChainSpec.from_dict(
            _make_chain(
                driver_robustness="full",
                milestones=[_ms("m1", north_star_critical=True)],
            )
        )
        assert spec.milestones[0].north_star_critical is True


class TestMilestoneNorthStarCriticalRejectsBareLight:
    """Milestone ``north_star_critical: true`` rejects ``bare``/``light``."""

    @pytest.mark.parametrize("robustness", ["bare", "light"])
    def test_milestone_critical_rejects_explicit(self, robustness: str) -> None:
        with pytest.raises(CliError, match=r"north_star_critical enabled"):
            ChainSpec.from_dict(
                _make_chain(
                    milestones=[_ms("m1", robustness=robustness, north_star_critical=True)],
                )
            )

    def test_milestone_critical_rejects_code_invalid_spec(self) -> None:
        with pytest.raises(CliError) as exc_info:
            ChainSpec.from_dict(
                _make_chain(
                    milestones=[_ms("m1", robustness="bare", north_star_critical=True)],
                )
            )
        assert exc_info.value.code == "invalid_spec"

    def test_milestone_critical_rejects_message_includes_label(self) -> None:
        """Error message names the offending milestone by label."""
        with pytest.raises(CliError, match=r"milestones\[0\] \('my-ms'\)"):
            ChainSpec.from_dict(
                _make_chain(
                    milestones=[
                        _ms("my-ms", robustness="light", north_star_critical=True)
                    ],
                )
            )

    def test_milestone_critical_rejects_message_includes_robustness(self) -> None:
        with pytest.raises(CliError, match=rf"is {chr(39)}light{chr(39)}"):
            ChainSpec.from_dict(
                _make_chain(
                    milestones=[_ms("ms", robustness="light", north_star_critical=True)],
                )
            )

    def test_milestone_critical_rejects_fallback_driver_bare(self) -> None:
        """Milestone inherits driver ``bare`` → rejected."""
        with pytest.raises(CliError, match=r"north_star_critical enabled"):
            ChainSpec.from_dict(
                _make_chain(
                    driver_robustness="bare",
                    milestones=[_ms("m1", north_star_critical=True)],
                )
            )

    def test_milestone_critical_rejects_fallback_driver_light(self) -> None:
        """Milestone inherits driver ``light`` → rejected."""
        with pytest.raises(CliError, match=r"north_star_critical enabled"):
            ChainSpec.from_dict(
                _make_chain(
                    driver_robustness="light",
                    milestones=[_ms("m1", north_star_critical=True)],
                )
            )

    def test_milestone_critical_rejects_alias_tiny(self) -> None:
        """Alias ``tiny`` → ``bare`` is rejected at milestone level."""
        with pytest.raises(CliError, match=r"north_star_critical enabled"):
            ChainSpec.from_dict(
                _make_chain(
                    milestones=[_ms("m1", robustness="tiny", north_star_critical=True)],
                )
            )


# ---------------------------------------------------------------------------
# Milestone robustness precedence
# ---------------------------------------------------------------------------

class TestMilestoneRobustnessPrecedence:
    """Milestone-level robustness takes precedence over driver-level robustness."""

    def test_milestone_full_overrides_driver_bare(self) -> None:
        """Milestone ``full`` + critical accepted even when driver is ``bare``."""
        spec = ChainSpec.from_dict(
            _make_chain(
                driver_robustness="bare",
                milestones=[_ms("m1", robustness="full", north_star_critical=True)],
            )
        )
        assert spec.milestones[0].north_star_critical is True
        assert spec.milestones[0].robustness == "full"

    def test_milestone_bare_overrides_driver_full_and_rejects(self) -> None:
        """Milestone ``bare`` + critical rejected even when driver is ``full``."""
        with pytest.raises(CliError, match=r"north_star_critical enabled"):
            ChainSpec.from_dict(
                _make_chain(
                    driver_robustness="full",
                    milestones=[_ms("m1", robustness="bare", north_star_critical=True)],
                )
            )

    def test_milestone_light_overrides_driver_full_and_rejects(self) -> None:
        """Milestone ``light`` + critical rejected even when driver is ``full``."""
        with pytest.raises(CliError, match=r"north_star_critical enabled"):
            ChainSpec.from_dict(
                _make_chain(
                    driver_robustness="full",
                    milestones=[_ms("m1", robustness="light", north_star_critical=True)],
                )
            )

    def test_milestone_thorough_overrides_driver_bare(self) -> None:
        """Milestone ``thorough`` + critical accepted when driver is ``bare``."""
        spec = ChainSpec.from_dict(
            _make_chain(
                driver_robustness="bare",
                milestones=[_ms("m1", robustness="thorough", north_star_critical=True)],
            )
        )
        assert spec.milestones[0].north_star_critical is True

    def test_milestone_extreme_overrides_driver_light(self) -> None:
        """Milestone ``extreme`` + critical accepted when driver is ``light``."""
        spec = ChainSpec.from_dict(
            _make_chain(
                driver_robustness="light",
                milestones=[_ms("m1", robustness="extreme", north_star_critical=True)],
            )
        )
        assert spec.milestones[0].north_star_critical is True

    def test_milestone_no_robustness_falls_back_to_driver_full_accepted(self) -> None:
        """Driver ``full`` + milestone critical (no own robustness) → accepted."""
        spec = ChainSpec.from_dict(
            _make_chain(
                driver_robustness="full",
                milestones=[_ms("m1", north_star_critical=True)],
            )
        )
        assert spec.milestones[0].north_star_critical is True

    def test_milestone_no_robustness_falls_back_to_driver_light_rejected(self) -> None:
        """Driver ``light`` + milestone critical (no own robustness) → rejected."""
        with pytest.raises(CliError, match=r"north_star_critical enabled"):
            ChainSpec.from_dict(
                _make_chain(
                    driver_robustness="light",
                    milestones=[_ms("m1", north_star_critical=True)],
                )
            )

    def test_multiple_milestones_mixed_precedence(self) -> None:
        """First milestone OK (own full), second rejected (inherits driver bare)."""
        with pytest.raises(CliError, match=r"milestones\[1\]"):
            ChainSpec.from_dict(
                _make_chain(
                    driver_robustness="bare",
                    milestones=[
                        _ms("ok-ms", robustness="full", north_star_critical=True),
                        _ms("bad-ms", north_star_critical=True),
                    ],
                )
            )

    def test_multiple_milestones_both_valid_different_sources(self) -> None:
        """One milestone uses own robustness, another inherits driver."""
        spec = ChainSpec.from_dict(
            _make_chain(
                driver_robustness="thorough",
                milestones=[
                    _ms("a", robustness="full", north_star_critical=True),
                    _ms("b", north_star_critical=True),  # inherits thorough
                ],
            )
        )
        assert spec.milestones[0].north_star_critical is True
        assert spec.milestones[1].north_star_critical is True


# ---------------------------------------------------------------------------
# OR semantics: chain-level OR milestone-level
# ---------------------------------------------------------------------------

class TestNorthStarCriticalORSemantics:
    """Either chain-level or milestone-level ``north_star_critical`` activates validation."""

    def test_chain_critical_true_milestone_false(self) -> None:
        """Chain critical but milestone explicitly False — still validated."""
        with pytest.raises(CliError, match=r"north_star_critical enabled"):
            ChainSpec.from_dict(
                _make_chain(
                    driver_robustness="bare",
                    driver_north_star_critical=True,
                    milestones=[
                        _ms("m1", robustness="bare", north_star_critical=False)
                    ],
                )
            )

    def test_chain_critical_false_milestone_true_rejected(self) -> None:
        """Chain not critical, but milestone True + bare → rejected."""
        with pytest.raises(CliError, match=r"north_star_critical enabled"):
            ChainSpec.from_dict(
                _make_chain(
                    driver_robustness="full",
                    driver_north_star_critical=False,
                    milestones=[_ms("m1", robustness="bare", north_star_critical=True)],
                )
            )

    def test_chain_critical_true_milestone_true_both_bare(self) -> None:
        """Both True, both bare → rejected with single error."""
        with pytest.raises(CliError, match=r"north_star_critical enabled"):
            ChainSpec.from_dict(
                _make_chain(
                    driver_robustness="bare",
                    driver_north_star_critical=True,
                    milestones=[_ms("m1", robustness="bare", north_star_critical=True)],
                )
            )

    def test_chain_critical_true_milestone_robustness_ok(self) -> None:
        """Chain bare but milestone has ``full`` explicit → accepted."""
        spec = ChainSpec.from_dict(
            _make_chain(
                driver_robustness="bare",
                driver_north_star_critical=True,
                milestones=[_ms("m1", robustness="full", north_star_critical=False)],
            )
        )
        assert spec.milestones[0].north_star_critical is False
        # effective_critical = False OR True = True, effective_robustness = full → OK
        assert spec.north_star_critical is True


# ---------------------------------------------------------------------------
# Omitted north_star_critical (backward-compatible)
# ---------------------------------------------------------------------------

class TestNorthStarCriticalOmittedBackwardCompatible:
    """When ``north_star_critical`` is omitted, everything works as before."""

    def test_chain_omitted_defaults_false(self) -> None:
        spec = ChainSpec.from_dict(
            _make_chain(milestones=[_ms("m1")])
        )
        assert spec.north_star_critical is False

    def test_milestone_omitted_defaults_false(self) -> None:
        spec = ChainSpec.from_dict(
            _make_chain(milestones=[_ms("m1")])
        )
        assert spec.milestones[0].north_star_critical is False

    def test_omitted_with_bare_robustness_accepted(self) -> None:
        """Bare robustness without north_star_critical is fine."""
        spec = ChainSpec.from_dict(
            _make_chain(
                driver_robustness="bare",
                milestones=[_ms("m1")],
            )
        )
        assert spec.robustness == "bare"

    def test_omitted_with_light_robustness_accepted(self) -> None:
        """Light robustness without north_star_critical is fine."""
        spec = ChainSpec.from_dict(
            _make_chain(
                driver_robustness="light",
                milestones=[_ms("m1")],
            )
        )
        assert spec.robustness == "light"

    def test_omitted_milestone_level_with_bare_accepted(self) -> None:
        """Milestone bare robustness without critical flag is fine."""
        spec = ChainSpec.from_dict(
            _make_chain(
                milestones=[_ms("m1", robustness="bare")],
            )
        )
        assert spec.milestones[0].robustness == "bare"

    def test_chain_critical_explicitly_false_with_bare_accepted(self) -> None:
        """Explicit ``north_star_critical: false`` with bare is fine."""
        spec = ChainSpec.from_dict(
            _make_chain(
                driver_robustness="bare",
                driver_north_star_critical=False,
                milestones=[_ms("m1")],
            )
        )
        assert spec.north_star_critical is False

    def test_milestone_critical_explicitly_false_with_bare_accepted(self) -> None:
        """Milestone ``north_star_critical: false`` with bare is fine."""
        spec = ChainSpec.from_dict(
            _make_chain(
                milestones=[_ms("m1", robustness="bare", north_star_critical=False)],
            )
        )
        assert spec.milestones[0].north_star_critical is False

    def test_empty_milestones_with_critical_chain_bare(self) -> None:
        """No milestones means no validation loop iteration — should pass."""
        spec = ChainSpec.from_dict(
            _make_chain(
                driver_robustness="bare",
                driver_north_star_critical=True,
                milestones=[],
            )
        )
        assert spec.north_star_critical is True

    def test_omitted_driver_robustness_defaults_to_full(self) -> None:
        """When driver robustness is omitted, it defaults to ``full`` → accepted."""
        spec = ChainSpec.from_dict(
            {
                "driver": {"north_star_critical": True},
                "milestones": [_ms("m1")],
            }
        )
        assert spec.north_star_critical is True
