from __future__ import annotations

import asyncio

import agent_kit.loop
from agent_kit.envelope import Envelope
import arnold
import megaplan.arnold


def test_megaplan_arnold_exports_public_api() -> None:
    assert megaplan.arnold.run_turn is agent_kit.loop.run_turn
    assert megaplan.arnold.arun_turn is agent_kit.loop.arun_turn
    assert megaplan.arnold.Envelope is Envelope
    assert asyncio.iscoroutinefunction(megaplan.arnold.arun_turn)


def test_arnold_exports_public_api() -> None:
    assert arnold.run_turn is agent_kit.loop.run_turn
    assert arnold.arun_turn is agent_kit.loop.arun_turn
    assert arnold.Envelope is Envelope
    assert asyncio.iscoroutinefunction(arnold.arun_turn)
