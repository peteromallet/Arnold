"""Registry parity tests for template_registry.

Every enforced model-generated ``StepContract.phase_identity`` must have
a ``TemplateRegistration`` with a builder, batch assembly entry, explicit
exemption, or documented deferred reason.  No phase identity may fall
through the cracks.

These tests gate T3 (builder wiring) and downstream handler integration:
the registry must be complete and correctly classified before builders
are added or handlers are rewired.
"""

from __future__ import annotations

import pytest

from arnold.pipelines.megaplan.step_contracts import STEP_CONTRACTS, StepContract
from arnold.pipelines.megaplan.template_registry import (
    _TEMPLATE_REGISTRY,  # deliberately test the internal dict for parity
    RegistryMode,
    TemplateRegistration,
    get_phases_by_mode,
    get_registered_phases,
    get_template_registration,
    is_registered,
)

# ---------------------------------------------------------------------------
# Expected mode assignments — the authoritative map for T2
# ---------------------------------------------------------------------------

#: Every phase identity → expected RegistryMode.
#: This is the single source of truth; the registry must match exactly.
_EXPECTED_MODES: dict[str, RegistryMode] = {
    # file_fill — structured JSON, model-fill path
    "finalize": "file_fill",
    "critique": "file_fill",
    "review": "file_fill",
    "gate": "file_fill",
    "critique_evaluator": "file_fill",
    # batch_assembly
    "execute": "batch_assembly",
    # markdown_exempt
    "plan": "markdown_exempt",
    "revise": "markdown_exempt",
    # subloop_exempt
    "tiebreaker_researcher": "subloop_exempt",
    "tiebreaker_challenger": "subloop_exempt",
    # deferred — handler integration deferred, current behaviour preserved
    "prep": "deferred",
    "prep-triage": "deferred",
    "prep-distill": "deferred",
    "prep-research": "deferred",
    "feedback": "deferred",
    "loop_plan": "deferred",
    "loop_execute": "deferred",
}

#: Phases that must have a non-empty scratch_filename.
_EXPECT_SCRATCH_FILENAME: frozenset[str] = frozenset({
    "file_fill",
    "batch_assembly",
    "deferred",
})

#: Phases that must have builder=None because no builder is required yet.
_BUILDER_NONE_MODES: frozenset[str] = frozenset({
    "markdown_exempt",
    "subloop_exempt",
    "deferred",
})

#: All 17 phase identities from StepContract registry.
_ALL_PHASES: frozenset[str] = frozenset(STEP_CONTRACTS.keys())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _phase_note(phase: str) -> str:
    """Return the note from the registration, or '' if missing."""
    reg = get_template_registration(phase)
    return reg.note if reg else ""


# ---------------------------------------------------------------------------
# Coverage: every StepContract phase_identity is registered
# ---------------------------------------------------------------------------


class TestCoverage:
    """Every ``StepContract.phase_identity`` must have a registry entry."""

    def test_all_17_phases_registered(self) -> None:
        """All 17 phase identities from STEP_CONTRACTS are in the registry."""
        registered = get_registered_phases()
        missing = _ALL_PHASES - registered
        extra = registered - _ALL_PHASES
        assert not missing, (
            f"Phases in STEP_CONTRACTS but NOT in template registry: "
            f"{sorted(missing)}"
        )
        assert not extra, (
            f"Phases in template registry but NOT in STEP_CONTRACTS: "
            f"{sorted(extra)}"
        )
        assert len(registered) == 17, (
            f"Expected 17 registered phases, got {len(registered)}"
        )

    def test_every_phase_is_registered(self) -> None:
        """``is_registered()`` returns True for every StepContract phase."""
        for phase in _ALL_PHASES:
            assert is_registered(phase), (
                f"{phase!r} is in STEP_CONTRACTS but is_registered() returns False"
            )

    def test_every_contract_has_template_registration_property(self) -> None:
        """``StepContract.template_registration`` is non-None for every phase."""
        for phase, contract in STEP_CONTRACTS.items():
            reg = contract.template_registration
            assert reg is not None, (
                f"{phase}: StepContract.template_registration is None"
            )
            assert isinstance(reg, TemplateRegistration), (
                f"{phase}: template_registration is not a TemplateRegistration"
            )
            assert reg.phase_identity == phase, (
                f"{phase}: template_registration.phase_identity is {reg.phase_identity!r}"
            )


# ---------------------------------------------------------------------------
# Mode correctness
# ---------------------------------------------------------------------------


class TestModeCorrectness:
    """Every registration must have the correct ``RegistryMode``."""

    def test_all_modes_match_expected(self) -> None:
        """Every phase's mode matches the authoritative expected map."""
        for phase, expected_mode in sorted(_EXPECTED_MODES.items()):
            reg = get_template_registration(phase)
            assert reg is not None, f"{phase}: not registered"
            assert reg.mode == expected_mode, (
                f"{phase}: expected mode={expected_mode!r}, got {reg.mode!r}"
            )

    def test_no_phase_has_unexpected_mode(self) -> None:
        """No phase should have a mode not in the expected map."""
        for phase in _ALL_PHASES:
            assert phase in _EXPECTED_MODES, (
                f"{phase}: missing from _EXPECTED_MODES — update the test"
            )

    def test_get_phases_by_mode_consistency(self) -> None:
        """``get_phases_by_mode`` returns correct sets for each mode."""
        for mode in ("file_fill", "batch_assembly", "markdown_exempt",
                     "subloop_exempt", "deferred"):
            phases = get_phases_by_mode(mode)
            expected = frozenset(
                p for p, m in _EXPECTED_MODES.items() if m == mode
            )
            assert phases == expected, (
                f"get_phases_by_mode({mode!r}): got {sorted(phases)}, "
                f"expected {sorted(expected)}"
            )


# ---------------------------------------------------------------------------
# File-fill entries: scratch filenames present
# ---------------------------------------------------------------------------


class TestFileFillEntries:
    """Every ``file_fill`` registration must carry a scratch filename."""

    def test_all_file_fill_have_scratch_filename(self) -> None:
        """``scratch_filename`` is non-empty for every file_fill phase."""
        for phase in get_phases_by_mode("file_fill"):
            reg = get_template_registration(phase)
            assert reg is not None
            assert reg.scratch_filename, (
                f"{phase}: file_fill but scratch_filename is empty"
            )
            assert reg.scratch_filename.endswith("_output.json"), (
                f"{phase}: scratch_filename {reg.scratch_filename!r} "
                f"does not end with '_output.json'"
            )

    def test_file_fill_scratch_filenames_are_unique(self) -> None:
        """No two file_fill phases share the same scratch filename."""
        names: dict[str, str] = {}
        for phase in get_phases_by_mode("file_fill"):
            reg = get_template_registration(phase)
            assert reg is not None
            fname = reg.scratch_filename
            if fname in names:
                raise AssertionError(
                    f"scratch_filename {fname!r} used by both "
                    f"{names[fname]!r} and {phase!r}"
                )
            names[fname] = phase


# ---------------------------------------------------------------------------
# Batch assembly: execute
# ---------------------------------------------------------------------------


class TestBatchAssembly:
    """Execute is batch_assembly — single-file promotion must NOT apply."""

    def test_execute_is_batch_assembly(self) -> None:
        """``execute`` must be registered as batch_assembly."""
        reg = get_template_registration("execute")
        assert reg is not None
        assert reg.mode == "batch_assembly", (
            f"execute: expected batch_assembly, got {reg.mode!r}"
        )

    def test_execute_has_scratch_filename_for_parity(self) -> None:
        """``execute`` has a scratch_filename for parity/documentation."""
        reg = get_template_registration("execute")
        assert reg is not None
        assert reg.scratch_filename == "execute_output.json", (
            f"execute: expected 'execute_output.json', got {reg.scratch_filename!r}"
        )

    def test_execute_has_note_explaining_batch_assembly(self) -> None:
        """``execute`` note documents why it is batch_assembly."""
        note = _phase_note("execute")
        assert "batch" in note.lower() or "assembled" in note.lower(), (
            f"execute: note does not explain batch_assembly: {note!r}"
        )


# ---------------------------------------------------------------------------
# Markdown exemptions: plan, revise
# ---------------------------------------------------------------------------


class TestMarkdownExempt:
    """Plan and revise are markdown_exempt — no structured JSON templates."""

    def test_plan_is_markdown_exempt(self) -> None:
        reg = get_template_registration("plan")
        assert reg is not None
        assert reg.mode == "markdown_exempt"
        assert reg.builder is None, "plan: markdown_exempt should not have a builder"
        assert reg.scratch_filename == "", (
            f"plan: markdown_exempt should have empty scratch_filename"
        )

    def test_revise_is_markdown_exempt(self) -> None:
        reg = get_template_registration("revise")
        assert reg is not None
        assert reg.mode == "markdown_exempt"
        assert reg.builder is None, "revise: markdown_exempt should not have a builder"
        assert reg.scratch_filename == "", (
            f"revise: markdown_exempt should have empty scratch_filename"
        )

    def test_markdown_exempt_phases_have_note(self) -> None:
        """Every markdown_exempt phase has a non-empty note."""
        for phase in get_phases_by_mode("markdown_exempt"):
            note = _phase_note(phase)
            assert note, f"{phase}: markdown_exempt but note is empty"


# ---------------------------------------------------------------------------
# Subloop exemptions: tiebreaker phases
# ---------------------------------------------------------------------------


class TestSubloopExempt:
    """Tiebreaker phases are subloop_exempt."""

    def test_tiebreaker_researcher_is_subloop_exempt(self) -> None:
        reg = get_template_registration("tiebreaker_researcher")
        assert reg is not None
        assert reg.mode == "subloop_exempt"
        assert reg.builder is None
        assert reg.scratch_filename == ""

    def test_tiebreaker_challenger_is_subloop_exempt(self) -> None:
        reg = get_template_registration("tiebreaker_challenger")
        assert reg is not None
        assert reg.mode == "subloop_exempt"
        assert reg.builder is None
        assert reg.scratch_filename == ""

    def test_subloop_exempt_phases_have_note(self) -> None:
        """Every subloop_exempt phase has a non-empty note."""
        for phase in get_phases_by_mode("subloop_exempt"):
            note = _phase_note(phase)
            assert note, f"{phase}: subloop_exempt but note is empty"


# ---------------------------------------------------------------------------
# Deferred entries
# ---------------------------------------------------------------------------


class TestDeferred:
    """Deferred phases have a note explaining why integration is postponed."""

    _DEFERRED_PHASES: frozenset[str] = frozenset({
        "prep", "prep-triage", "prep-distill", "prep-research",
        "feedback", "loop_plan", "loop_execute",
    })

    def test_all_deferred_phases_match_expected_set(self) -> None:
        """The deferred set matches the authoritative list."""
        actual = get_phases_by_mode("deferred")
        assert actual == self._DEFERRED_PHASES, (
            f"deferred phases: got {sorted(actual)}, "
            f"expected {sorted(self._DEFERRED_PHASES)}"
        )

    def test_every_deferred_phase_has_note(self) -> None:
        """Every deferred phase has a non-empty note."""
        for phase in self._DEFERRED_PHASES:
            note = _phase_note(phase)
            assert note, (
                f"{phase}: deferred but note is empty — must document why"
            )

    def test_every_deferred_note_mentions_deferral(self) -> None:
        """Deferred notes should mention deferral or preserved behavior."""
        for phase in self._DEFERRED_PHASES:
            note = _phase_note(phase).lower()
            assert "defer" in note or "preserved" in note, (
                f"{phase}: deferred note does not mention deferral or "
                f"preserved behavior: {note!r}"
            )

    def test_deferred_phases_have_scratch_filenames(self) -> None:
        """Deferred phases have scratch filenames (for future wiring)."""
        for phase in self._DEFERRED_PHASES:
            reg = get_template_registration(phase)
            assert reg is not None
            assert reg.scratch_filename, (
                f"{phase}: deferred but scratch_filename is empty"
            )


# ---------------------------------------------------------------------------
# Builder presence constraints
# ---------------------------------------------------------------------------


class TestBuilderPresence:
    """Builder presence follows registry mode semantics."""

    def test_file_fill_phases_have_builders(self) -> None:
        """Every file_fill phase has a concrete template builder."""
        for phase in get_phases_by_mode("file_fill"):
            reg = get_template_registration(phase)
            assert reg is not None
            assert reg.builder is not None, f"{phase}: file_fill phase missing builder"
            assert callable(reg.builder), f"{phase}: builder is not callable"

    def test_batch_assembly_has_builder(self) -> None:
        """Execute has a builder for parity/documentation."""
        reg = get_template_registration("execute")
        assert reg is not None
        assert reg.builder is not None
        assert callable(reg.builder)

    def test_exempt_and_deferred_builders_are_none(self) -> None:
        """Markdown/subloop/deferred phases do not expose active builders."""
        for mode in _BUILDER_NONE_MODES:
            for phase in get_phases_by_mode(mode):  # type: ignore[arg-type]
                reg = get_template_registration(phase)
                assert reg is not None
                assert reg.builder is None, (
                    f"{phase}: {mode} phase should not have an active builder"
                )

    def test_step_contract_template_builder_matches_registration(self) -> None:
        """``StepContract.template_builder`` proxies the template registry."""
        for phase, contract in STEP_CONTRACTS.items():
            reg = get_template_registration(phase)
            assert reg is not None
            assert contract.template_builder is reg.builder

    def test_pre_populated_only_on_file_fill(self) -> None:
        """pre_populated is worker metadata for file_fill phases only."""
        for phase in _ALL_PHASES:
            reg = get_template_registration(phase)
            assert reg is not None
            if reg.pre_populated:
                assert reg.mode == "file_fill", (
                    f"{phase}: pre_populated set on non-file_fill phase"
                )

    def test_review_and_critique_are_pre_populated(self) -> None:
        """Review and critique builders seed IDs/checks into the scratch file."""
        assert get_template_registration("review").pre_populated is True
        assert get_template_registration("critique").pre_populated is True

    def test_other_file_fill_phases_not_marked_pre_populated(self) -> None:
        for phase in {"finalize", "gate", "critique_evaluator"}:
            reg = get_template_registration(phase)
            assert reg is not None
            assert reg.pre_populated is False, (
                f"{phase}: unexpectedly marked pre_populated"
            )


# ---------------------------------------------------------------------------
# Registry integrity
# ---------------------------------------------------------------------------


class TestRegistryIntegrity:
    """Internal consistency of the registry data structure."""

    def test_no_duplicate_phase_identities(self) -> None:
        """The internal dict has exactly 17 unique keys."""
        assert len(_TEMPLATE_REGISTRY) == 17, (
            f"Expected 17 entries, got {len(_TEMPLATE_REGISTRY)}"
        )

    def test_all_keys_match_phase_identity(self) -> None:
        """Every key in _TEMPLATE_REGISTRY matches its value's phase_identity."""
        for key, reg in _TEMPLATE_REGISTRY.items():
            assert key == reg.phase_identity, (
                f"Key {key!r} != registration.phase_identity {reg.phase_identity!r}"
            )

    def test_all_registrations_are_frozen(self) -> None:
        """Every TemplateRegistration is a frozen dataclass instance."""
        for reg in _TEMPLATE_REGISTRY.values():
            assert isinstance(reg, TemplateRegistration)

    def test_mode_values_are_valid_literals(self) -> None:
        """Every registration.mode is a valid RegistryMode."""
        valid: frozenset[str] = frozenset(
            {"file_fill", "batch_assembly", "markdown_exempt",
             "subloop_exempt", "deferred"}
        )
        for reg in _TEMPLATE_REGISTRY.values():
            assert reg.mode in valid, (
                f"{reg.phase_identity}: invalid mode {reg.mode!r}"
            )

    def test_get_template_registration_returns_correct_object(self) -> None:
        """``get_template_registration`` returns the exact same object."""
        for phase in _ALL_PHASES:
            reg = get_template_registration(phase)
            assert reg is _TEMPLATE_REGISTRY[phase], (
                f"{phase}: get_template_registration returned a different object"
            )


# ---------------------------------------------------------------------------
# SC2: every enforced model-generated contract is covered
# ---------------------------------------------------------------------------


class TestParityCoverageSC2:
    """Sense check SC2: every enforced model-generated phase_identity must
    have a builder, batch assembly entry, explicit exemption, or documented
    deferred reason.  No phase may be unaccounted for."""

    # Phases that are NOT model-generated structured output (no enforcement).
    _NON_ENFORCED: frozenset[str] = frozenset({
        "plan",             # markdown_exempt
        "revise",           # markdown_exempt
        "tiebreaker_researcher",  # subloop_exempt
        "tiebreaker_challenger",  # subloop_exempt
    })

    # Enforced model-generated phases.
    _ENFORCED: frozenset[str] = _ALL_PHASES - _NON_ENFORCED

    def test_every_enforced_phase_is_covered(self) -> None:
        """Every enforced phase must be file_fill, batch_assembly, or deferred.

        No enforced phase may be markdown_exempt or subloop_exempt, and
        every enforced phase must have a non-empty scratch_filename.
        """
        for phase in self._ENFORCED:
            reg = get_template_registration(phase)
            assert reg is not None, f"{phase}: not registered"
            assert reg.mode in ("file_fill", "batch_assembly", "deferred"), (
                f"{phase}: enforced phase has mode {reg.mode!r} — "
                f"must be file_fill, batch_assembly, or deferred"
            )
            assert reg.scratch_filename, (
                f"{phase}: enforced phase has empty scratch_filename"
            )

    def test_non_enforced_phases_are_exempt(self) -> None:
        """Non-enforced phases must have an explicit exemption mode."""
        for phase in self._NON_ENFORCED:
            reg = get_template_registration(phase)
            assert reg is not None, f"{phase}: not registered"
            assert reg.mode in ("markdown_exempt", "subloop_exempt"), (
                f"{phase}: non-enforced phase has mode {reg.mode!r} — "
                f"must be markdown_exempt or subloop_exempt"
            )

    def test_enforced_non_enforced_partition_is_complete(self) -> None:
        """The union of enforced and non-enforced covers all 17 phases."""
        assert self._ENFORCED | self._NON_ENFORCED == _ALL_PHASES
        assert self._ENFORCED & self._NON_ENFORCED == set()

    def test_every_deferred_phase_documents_why(self) -> None:
        """Every deferred phase note explains what is deferred."""
        for phase in get_phases_by_mode("deferred"):
            note = _phase_note(phase)
            assert note, (
                f"{phase}: deferred but no note explaining why"
            )
            # Must mention either a follow-up sprint or preserved behavior
            note_lower = note.lower()
            assert any(term in note_lower for term in
                       ("defer", "follow-up", "preserved", "unchanged")), (
                f"{phase}: deferred note does not explain deferral: {note!r}"
            )
