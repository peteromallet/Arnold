"""Profile/flag smoke matrix.

One place to eyeball "the tier x flag matrix still produces sane phase
maps." Each parametrized case exercises one canonical profile + one
flag combination and asserts on a handful of key phase resolutions.

This is the cross-cutting backstop for the four dials (profile,
robustness, depth, vendor/critic) plus the --with-prep toggle: when we
change a flag-related setting in the future, this file is the
first thing to update — failures here mean the rewrite chain shifted.

No model calls. Profiles are loaded from the built-in TOMLs; the
vendor default is pinned to claude for determinism; handle_init is
invoked with handler-level args (no real CLI, no subprocesses).
"""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

import megaplan
import megaplan.profiles as profiles_module
from megaplan._core.workflow import _workflow_for_robustness
from megaplan.profiles import apply_profile_expansion
from megaplan.planning.state import STATE_INITIALIZED


DEEPSEEK = "hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro"
DEEPSEEK_DIRECT = "hermes:deepseek:deepseek-v4-pro"
KIMI = "hermes:fireworks:accounts/fireworks/models/kimi-k2p6"


def _pin_user_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin profile-loader config dir + default vendor so dev-machine
    state doesn't leak into the matrix."""
    fake_home_config = tmp_path / ".config" / "megaplan"
    monkeypatch.setattr(profiles_module, "config_dir", lambda home=None: fake_home_config)
    monkeypatch.setattr(profiles_module, "_resolve_default_vendor", lambda: "claude")


def _worker_args(**overrides: object) -> Namespace:
    """Mirror tests/test_profiles.py::_worker_args, kept local so this
    file is self-contained and the matrix is easy to read in one place.
    """
    data: dict[str, object] = {
        "agent": None,
        "confirm_self_review": False,
        "ephemeral": False,
        "fresh": False,
        "hermes": None,
        "persist": False,
        "phase_model": [],
        "profile": None,
    }
    data.update(overrides)
    return Namespace(**data)


def _resolved_phase_map(profile: str, **flag_overrides: object) -> dict[str, str]:
    """Run a profile + flags through ``apply_profile_expansion`` and
    return the resolved phase -> spec map (first-match wins, matching
    ``resolve_agent_mode``'s lookup rule)."""
    args = _worker_args(profile=profile, **flag_overrides)
    apply_profile_expansion(args, None)
    out: dict[str, str] = {}
    for pm in args.phase_model:
        if "=" not in pm:
            continue
        step, spec = pm.split("=", 1)
        out.setdefault(step, spec)
    return out


# ---------------------------------------------------------------------------
# The matrix — one row per (profile, flags, expected phase assertions) case.
#
# Each row is:
#   id              — human-readable label (shows up in pytest -v output)
#   profile         — canonical profile name
#   flags           — kwargs forwarded to _worker_args
#   expected        — {phase: expected_spec, ...}; subset of the full map
#                     so a row can pin just the slots it cares about.
# ---------------------------------------------------------------------------


MATRIX: list[tuple[str, str, dict[str, object], dict[str, str]]] = [
    # --- solo (tier 1) — no premium slots ---
    (
        "solo-default",
        "solo",
        {},
        # solo runs DeepSeek end-to-end (including critique/review); no Kimi.
        {"plan": DEEPSEEK_DIRECT, "critique": DEEPSEEK_DIRECT, "review": DEEPSEEK_DIRECT, "execute": DEEPSEEK_DIRECT},
    ),
    (
        "solo-vendor-codex-noop",
        "solo",
        {"vendor": "codex"},
        # No premium slots — vendor flip is a silent no-op.
        {"plan": DEEPSEEK_DIRECT, "critique": DEEPSEEK_DIRECT, "review": DEEPSEEK_DIRECT},
    ),
    # --- directed (tier 2) — premium plan only ---
    (
        "directed-default",
        "directed",
        {},
        {
            "plan": "claude:low",
            "loop_plan": "claude:low",
            "critique": DEEPSEEK_DIRECT,
            "review": DEEPSEEK_DIRECT,
            "revise": DEEPSEEK_DIRECT,
        },
    ),
    # directed-vendor-codex: --vendor codex now raises vendor_swap_model_conflict
    # (tier_models.execute has pinned claude:claude-sonnet-4-6 / claude:claude-opus-4-7).
    # This case has been removed from the success matrix; see
    # test_directed_profile_flips_to_codex_under_vendor_codex in test_profiles.py.
    (
        "directed-default-finalize-premium",
        "directed",
        {},
        # finalize is now claude:claude-opus-4-7 (premium finalize, raised for rater>=dispatchee).
        {"plan": "claude:low", "loop_plan": "claude:low", "finalize": "claude:claude-opus-4-7",
         "critique": DEEPSEEK_DIRECT, "review": DEEPSEEK_DIRECT},
    ),
    (
        "directed-depth-high",
        "directed",
        {"depth": "high"},
        {"plan": "claude:high", "loop_plan": "claude:high", "critique": DEEPSEEK_DIRECT},
    ),
    # --- partnered (tier 3) — premium author/reviewer, cheap critique under
    # premium critique-evaluator direction ---
    (
        "partnered-default",
        "partnered",
        {},
        {
            "plan": "claude:low",
            # critique now runs cheap (DeepSeek) directed by the premium evaluator.
            "critique": DEEPSEEK_DIRECT,
            "revise": "claude:low",
            "review": "claude:low",
            "prep": DEEPSEEK_DIRECT,
            "execute": DEEPSEEK_DIRECT,
        },
    ),
    (
        "partnered-critic-kimi",
        "partnered",
        {"critic": "kimi"},
        {
            "plan": "claude:low",
            "revise": "claude:low",
            "critique": KIMI,
            "review": KIMI,
        },
    ),
    # partnered-vendor-codex-depth-medium-critic-cross: --vendor codex on partnered
    # now raises vendor_swap_model_conflict (tier_models.execute has pinned specs).
    # Replaced with a partnered default entry that verifies finalize is now premium.
    (
        "partnered-default-finalize-premium",
        "partnered",
        {},
        {
            "plan": "claude:low",
            # critique now runs cheap (DeepSeek) directed by the premium evaluator.
            "critique": DEEPSEEK_DIRECT,
            "revise": "claude:low",
            "review": "claude:low",
            # finalize is now claude:low (premium finalize).
            "finalize": "claude:low",
            "prep": DEEPSEEK_DIRECT,
            "execute": DEEPSEEK_DIRECT,
        },
    ),
    (
        "partnered-depth-high-with-prep-flag",
        "partnered",
        {"depth": "high", "with_prep": True},
        # with_prep doesn't touch phase resolutions — it changes the
        # workflow shape. Phase map should still be tier-3 at :high.
        {
            "plan": "claude:high",
            "revise": "claude:high",
            # critique is cheap DeepSeek; --depth never rewrites it.
            "critique": DEEPSEEK_DIRECT,
            "prep": DEEPSEEK_DIRECT,
        },
    ),
    # --- premium (tier 4) — single-vendor premium end-to-end ---
    (
        "premium-default",
        "premium",
        {},
        {
            "plan": "claude:low",
            "critique": "claude:low",
            "execute": "claude:low",
            "review": "claude:low",
            "prep": "claude:low",
        },
    ),
    # premium-vendor-codex: --vendor codex on premium now raises vendor_swap_model_conflict
    # (tier_models.execute has pinned claude:claude-sonnet-4-6 / claude:claude-opus-4-7).
    # Replaced with premium-depth-high to keep coverage of the premium profile dials.
    (
        "premium-depth-high",
        "premium",
        {"depth": "high"},
        {
            "plan": "claude:high",
            "revise": "claude:high",
            # Critic phases stay at existing :low (asymmetry principle).
            "critique": "claude:low",
            "review": "claude:low",
        },
    ),
    (
        "premium-critic-kimi-at-tier-4",
        "premium",
        {"critic": "kimi"},
        # Legal at tier 4: keep premium author, swap critic to Kimi.
        {"plan": "claude:low", "critique": KIMI, "review": KIMI, "execute": "claude:low"},
    ),
    # --- apex (tier 5) — vendor-locked; --vendor and --critic
    # are silent no-ops; --depth still applies. ---
    (
        "apex-default",
        "apex",
        {},
        # Vendor-locked Claude+Codex split: Claude on author/repo-reading
        # side, Codex on critique/structural-analysis side.
        {"plan": "claude", "critique": "codex", "execute": "codex", "review": "codex"},
    ),
    (
        "apex-depth-high-honored-on-locked",
        "apex",
        {"depth": "high"},
        # --depth still applies on vendor-locked profiles; rewrites the
        # author-side claude slots to claude:high. Critic / mechanical
        # slots untouched (asymmetry principle).
        {
            "plan": "claude:high",
            "revise": "claude:high",
            "critique": "codex",
            "execute": "codex",
        },
    ),
]


@pytest.mark.parametrize(
    "case_id,profile,flags,expected",
    MATRIX,
    ids=[row[0] for row in MATRIX],
)
def test_profile_flag_matrix(
    case_id: str,
    profile: str,
    flags: dict[str, object],
    expected: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _pin_user_config(tmp_path, monkeypatch)
    resolved = _resolved_phase_map(profile, **flags)
    for phase, spec in expected.items():
        assert resolved.get(phase) == spec, (
            f"[{case_id}] expected {phase}={spec!r}, got {resolved.get(phase)!r}"
        )


def test_apex_vendor_and_critic_are_silent_noops(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--vendor and --critic on a vendor-locked profile must produce the
    same phase map as no flags at all."""
    _pin_user_config(tmp_path, monkeypatch)
    baseline = _resolved_phase_map("apex")
    with_flags = _resolved_phase_map("apex", vendor="claude", critic="kimi")
    assert baseline == with_flags


# ---------------------------------------------------------------------------
# --with-prep — workflow-shape assertions
# ---------------------------------------------------------------------------


def test_with_prep_adds_prep_to_standard_workflow() -> None:
    """At --robustness standard, STATE_INITIALIZED normally jumps
    straight to plan. --with-prep should restore the prep transition(s).
    prep can land in PREPPED or AWAITING_HUMAN, so there may be multiple
    transitions — all must have next_step == 'prep'."""
    workflow = _workflow_for_robustness("standard", with_prep=True)
    transitions = workflow[STATE_INITIALIZED]
    next_steps = [t.next_step for t in transitions]
    assert next_steps and set(next_steps) == {"prep"}, (
        f"with_prep=True at standard should run prep first; got {next_steps}"
    )


def test_with_prep_adds_prep_to_light_workflow() -> None:
    workflow = _workflow_for_robustness("light", with_prep=True)
    next_steps = [t.next_step for t in workflow[STATE_INITIALIZED]]
    assert next_steps and set(next_steps) == {"prep"}


def test_with_prep_is_noop_at_robust() -> None:
    """robust already includes prep; with_prep=True must not break it."""
    workflow = _workflow_for_robustness("robust", with_prep=True)
    next_steps = [t.next_step for t in workflow[STATE_INITIALIZED]]
    assert next_steps and set(next_steps) == {"prep"}


def test_without_with_prep_standard_skips_prep() -> None:
    """Sanity: confirm the default behavior we're flipping is in place."""
    workflow = _workflow_for_robustness("standard")
    assert [t.next_step for t in workflow[STATE_INITIALIZED]] == ["plan"]


# ---------------------------------------------------------------------------
# CLI smoke: handle_init persists the dials into state["config"].
# No model calls — handle_init only writes state.
# ---------------------------------------------------------------------------


def _init_args(project_dir: Path, **overrides: object) -> Namespace:
    data: dict[str, object] = {
        "agent": None,
        "auto_approve": False,
        "auto_start": False,
        "from_doc": None,
        "hermes": None,
        "idea": "smoke-test idea",
        "idea_file": None,
        "mode": "code",
        "name": "smoke-state",
        "output": None,
        "phase_model": [],
        "primary_criterion": None,
        "profile": None,
        "project_dir": str(project_dir),
        "robustness": "standard",
    }
    data.update(overrides)
    return Namespace(**data)


def test_handle_init_persists_full_dial_set_into_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: invoke handle_init with a representative flag combo
    and confirm config.vendor / config.critic / config.depth /
    config.with_prep / config.phase_model land in the persisted state.

    This is the "one place to look" check that args -> state -> downstream
    subprocess phases stays wired correctly.

    Uses all-claude with --vendor codex: its flat slots swap cleanly, and its
    execute tier_models (haiku/sonnet/opus pins) swap to Codex capability
    equivalents via _CLAUDE_MODEL_TO_CODEX_SPEC (haiku/sonnet→gpt-5.4,
    opus→gpt-5.5) — so the swap does NOT raise, unlike partnered/directed/
    premium whose tiers include DeepSeek pins (see test_profiles.py).
    """
    _pin_user_config(tmp_path, monkeypatch)

    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()

    response = megaplan.handle_init(
        root,
        _init_args(
            project_dir,
            profile="all-claude",
            vendor="codex",
            depth="medium",
            critic="kimi",
            with_prep=True,
        ),
    )

    state_path = megaplan.plans_root(root) / response["plan"] / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    config = state["config"]

    assert config["profile"] == "all-claude"
    assert config["vendor"] == "codex"
    assert config["critic"] == "kimi"
    assert config["depth"] == "medium"
    assert config["with_prep"] is True

    # phase_model is persisted as a list of "phase=spec" strings; spot-check
    # that the rewrite chain landed (vendor -> depth -> critic).
    resolved: dict[str, str] = {}
    for pm in config.get("phase_model", []):
        if "=" not in pm:
            continue
        step, spec = pm.split("=", 1)
        resolved.setdefault(step, spec)

    # Author phase at codex:medium (vendor + depth).
    assert resolved["plan"] == "codex:medium"
    assert resolved["revise"] == "codex:medium"
    # Critic phases swapped to Kimi (overriding the cross/depth rewrites).
    assert resolved["critique"] == KIMI
    assert resolved["review"] == KIMI


def test_handle_init_without_dials_omits_them_from_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sanity: a bare init (no vendor/critic/depth/with_prep) doesn't
    leak the flag keys into state. Persistence is opt-in per flag."""
    _pin_user_config(tmp_path, monkeypatch)

    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()

    response = megaplan.handle_init(
        root,
        _init_args(project_dir, profile="solo"),
    )
    state_path = megaplan.plans_root(root) / response["plan"] / "state.json"
    config = json.loads(state_path.read_text(encoding="utf-8"))["config"]

    assert "vendor" not in config
    assert "critic" not in config
    assert "depth" not in config
    assert "with_prep" not in config
