"""Shared Shannon session planner parity tests."""

from __future__ import annotations

import dataclasses
import importlib
import random
import sys


def test_shared_session_planner_import_has_no_tmux_side_effects() -> None:
    sys.modules.pop("arnold.pipelines.megaplan.workers.shannon_session", None)
    sys.modules.pop("arnold.pipelines.megaplan.workers.shannon", None)
    sys.modules.pop("arnold.pipelines.megaplan.runtime.process", None)

    module = importlib.import_module("arnold.pipelines.megaplan.workers.shannon_session")

    assert module.plan_session is not None
    assert "arnold.pipelines.megaplan.workers.shannon" not in sys.modules
    assert "arnold.pipelines.megaplan.runtime.process" not in sys.modules


def test_shannon_reexports_shared_session_planner() -> None:
    import arnold.pipelines.megaplan.workers.shannon as shannon
    import arnold.pipelines.megaplan.workers.shannon_session as shared

    assert shannon.Turn is shared.Turn
    assert shannon.SessionPlan is shared.SessionPlan
    assert shannon.plan_session(
        "execute",
        stored_id="stored-session",
        fresh=False,
        cfg=shannon.ShannonConfig.load({}, env={}),
        rng=random.Random(7),
    ) == shared.plan_session(
        "execute",
        stored_id="stored-session",
        fresh=False,
        cfg=shannon.ShannonConfig.load({}, env={}),
        rng=random.Random(7),
    )
    assert shannon._serialize_session_plan is shared._serialize_session_plan
    assert shannon._seeded_rng_for_run is shared._seeded_rng_for_run
    assert shannon._shannon_run_nonce is shared._shannon_run_nonce


def test_shared_session_planner_pins_new_resume_clear_compact_parity() -> None:
    from arnold.pipelines.megaplan.workers.shannon import ShannonConfig
    from arnold.pipelines.megaplan.workers.shannon_session import _serialize_session_plan, plan_session

    base = dataclasses.replace(
        ShannonConfig.load({}, env={}),
        handshake_probability=0.0,
        handshake_delay_min_seconds=0.0,
        handshake_delay_max_seconds=0.0,
        context_op_delay_min_seconds=0.0,
        context_op_delay_max_seconds=0.0,
    )

    cases = [
        (
            "new",
            dataclasses.replace(base, session_roulette_enabled=True),
            {"step": "plan", "stored_id": None, "fresh": False},
        ),
        (
            "resume",
            dataclasses.replace(base, session_roulette_enabled=False),
            {"step": "execute", "stored_id": "stored-session", "fresh": False},
        ),
        (
            "clear",
            dataclasses.replace(
                base,
                session_roulette_enabled=True,
                session_compact_probability=0.0,
            ),
            {"step": "execute", "stored_id": "stored-session", "fresh": False},
        ),
        (
            "compact",
            dataclasses.replace(
                base,
                session_roulette_enabled=True,
                session_compact_probability=1.0,
            ),
            {"step": "execute", "stored_id": "stored-session", "fresh": False},
        ),
    ]

    for expected_kind, cfg, kwargs in cases:
        first = plan_session(**kwargs, cfg=cfg, rng=random.Random(1234))
        second = plan_session(**kwargs, cfg=cfg, rng=random.Random(1234))
        assert first == second
        assert first.kind == expected_kind
        assert _serialize_session_plan(first) == _serialize_session_plan(second)
        if expected_kind == "resume":
            assert first.pre_turns == ()
            assert first.main.resume is True
        if expected_kind in {"clear", "compact"}:
            assert len(first.pre_turns) == 1
            assert first.pre_turns[0].body == f"/{expected_kind}"
            assert first.main.resume is True
        if expected_kind == "new":
            assert first.pre_turns == ()
            assert first.main.resume is False


def test_shared_session_planner_probability_threshold_matches_tmux_selector() -> None:
    from arnold.pipelines.megaplan.workers import shannon
    from arnold.pipelines.megaplan.workers.shannon import ShannonConfig
    from arnold.pipelines.megaplan.workers.shannon_session import plan_session

    cfg = dataclasses.replace(
        ShannonConfig.load({}, env={}),
        session_roulette_enabled=True,
        session_compact_probability=0.25,
        context_op_delay_min_seconds=0.0,
        context_op_delay_max_seconds=0.0,
    )

    class FixedRng:
        def __init__(self, value: float) -> None:
            self.value = value

        def random(self) -> float:
            return self.value

        def uniform(self, low: float, high: float) -> float:
            return low

        def randbytes(self, n: int) -> bytes:
            return b"\0" * n

        def choice(self, seq):  # type: ignore[no-untyped-def]
            return seq[0]

    for roll in (0.0, 0.249999, 0.25, 0.999):
        original_random = shannon.random.random
        try:
            shannon.random.random = lambda roll=roll: roll  # type: ignore[method-assign]
            tmux_kind = shannon._select_session_strategy(
                "execute",
                has_session=True,
                explicit_fresh=False,
                slash_supported=True,
                cfg=cfg,
            )
        finally:
            shannon.random.random = original_random  # type: ignore[method-assign]

        shared_kind = plan_session(
            "execute",
            stored_id="stored-session",
            fresh=False,
            cfg=cfg,
            rng=FixedRng(roll),  # type: ignore[arg-type]
        ).kind
        assert shared_kind == tmux_kind
