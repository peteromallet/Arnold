"""Pure Shannon session planning shared by tmux and stream workers."""

from __future__ import annotations

import dataclasses
import hashlib
import random
import uuid
from typing import Any

from megaplan.types import PlanState


_SHANNON_READINESS_PROMPTS = (
    "Hey, I just opened this agent window. Say ready when you are good to go.",
    "Hi, checking that this new agent tab is awake. A quick ready is enough.",
    "Hello. I am about to send the actual brief. Tell me when you are ready.",
    "Hey there, this is just a quick warmup message. Say all set when you are.",
    "Hi, making sure this new session is live. Just say yep when you can take the brief.",
    "Hey, I am getting this agent window started. Let me know when you are ready.",
    "Hello, I will send the task in a moment. Say good to go when you are set.",
    "Hi, just checking that you are loaded in. Answer with ready when you are.",
    "Hey, new session check before I paste the work. Say send it when ready.",
    "Hello, this is a quick hello before the real request. Just confirm you are ready.",
    "Hey, can you confirm this window is ready? A short yes is fine.",
    "Hi, I am opening a fresh agent session. Say all good when you are set.",
    "Hello, I am going to hand you a brief next. Tell me when you are ready.",
    "Hey, quick startup check. Say ready when you can continue.",
    "Hi, making sure the agent is ready before the task. Give me a quick okay.",
    "Hey, I just spun up this session. Say ready whenever you are.",
    "Hello, checking in before I send the work. A quick all set is fine.",
    "Hi, this is the little pre-task ping. Just answer when you are ready.",
    "Hey, waiting for this new agent window to settle. Say settled when it has.",
    "Hello, I am about to send instructions. Confirm when you can receive them.",
    "Hi, quick check that you are here. Say here when you are ready.",
    "Hey, I opened this session for a task. Let me know when you are set.",
    "Hello, the actual brief is coming next. Say ready for it when you are.",
    "Hi, just making sure the session started cleanly. Send a quick okay.",
    "Hey, before I send the real prompt, tell me you are ready.",
    "Hello, new agent window is up. Say good to go when you are.",
    "Hi, I am checking this session before sending the brief. Confirm you are ready.",
    "Hey, this is just a starter message. Say all set when you are.",
    "Hello, can you let me know you are ready? Any short confirmation works.",
    "Hi, I will send the request after you answer. Say ready when ready.",
    "Hey, quick agent-window check. Tell me when you can start.",
    "Hello, I am waiting for the new session to be usable. Say usable when it is.",
    "Hi, this is just to wake up the session. Give me a quick yep.",
    "Hey, I am opening with a small check first. Let me know when you are ready.",
    "Hello, please confirm you are ready for the brief. Keep it short.",
    "Hi, new window looks open. Say ready when it is actually ready.",
    "Hey, I have a task to send after this. Say all set when you are.",
    "Hello, just testing the session before the brief. A quick ready is fine.",
    "Hi, I am here with the next task shortly. Tell me when you are ready.",
    "Hey, let me know this agent window is responsive. Say yep if it is.",
    "Hello, I am going to pass you the real request next. Say send it when ready.",
    "Hi, quick first message for the new session. Say ready when you are set.",
    "Hey, checking that this session can accept input. Confirm when it can.",
    "Hello, please answer with any short ready check once this window is ready.",
    "Hi, I just launched this agent. Say good when you are good.",
    "Hey, the task is coming in the next message. Tell me when you are ready.",
    "Hello, warmup first, brief second. Say all set when you are.",
    "Hi, making sure this fresh session is working. A quick okay works.",
    "Hey, I am about to give you work. Say ready when you are set.",
    "Hello, this is just a quick session check. Reply with a short confirmation.",
    "Hi, new agent session here. Say ready for the brief when you can take it.",
    "Hey, checking the room before I send the actual request. Say good when ready.",
    "Hello, I need this session ready before the brief. Confirm when it is.",
    "Hi, I am waiting on this agent window to be ready. Say ready when ready.",
    "Hey, simple startup ping. A quick yep is enough.",
    "Hello, I will paste the task after this. Say send it when ready.",
    "Hi, can you confirm the session is ready? Just say yes if it is.",
    "Hey, first message in a new agent window. Say all set when you are.",
    "Hello, the actual instructions will follow. Give me a short ready check.",
    "Hi, just making sure you are not still starting up. Say ready when you are done.",
    "Hey, I am checking that this new window is alive. Say alive when ready.",
    "Hello, please get ready for the brief. Tell me when you are ready.",
    "Hi, this is only the handshake message. Say all set when you are.",
    "Hey, quick check before I send the actual prompt. A short okay is fine.",
    "Hello, I opened a new session for the next task. Confirm when ready.",
    "Hi, I am going to send the brief once you answer. Say ready when ready.",
    "Hey, confirm you are ready and I will send the work. Any short yes works.",
    "Hello, just starting this agent window. Say good to go when you are good.",
    "Hi, I am giving the session a second before the task. Let me know when ready.",
    "Hey, this is a preflight hello. Say set when you are set.",
    "Hello, checking that you can respond before the real ask. Say yep if you can.",
    "Hi, I have the task queued up. Tell me when you are ready.",
    "Hey, new Claude window check. Say ready when you are ready.",
    "Hello, I am about to hand over the brief. Say send it when ready.",
    "Hi, please confirm this session is ready to work. A quick ready works.",
    "Hey, I am waiting for the agent to be ready. Say all good when it is.",
    "Hello, this is just the opener for a new session. Say ready when ready.",
    "Hi, I will send details once you confirm. Say set when you are set.",
    "Hey, making sure the window is responsive first. Give me a quick yep.",
    "Hello, the real message comes next. Tell me when you are ready.",
    "Hi, I am doing a quick startup check. A short ready is enough.",
    "Hey, I just opened this for a task. Say good to go when you are set.",
    "Hello, please answer with ready when this session can take the brief.",
    "Hi, quick handshake before the request. Say all set when ready.",
    "Hey, I need to know you are ready before I send the task. Just confirm.",
    "Hello, checking this new agent window before the brief. Say okay when ready.",
    "Hi, I am about to send the work over. Say good when you are good.",
    "Hey, just confirming this session is usable. Tell me when it is.",
    "Hello, I will send the main request after your reply. Say send it when ready.",
    "Hi, new session opened. Say ready for the brief when you are.",
    "Hey, small opening message before the task. A quick yep works.",
    "Hello, please confirm you are up and ready. Keep it short.",
    "Hi, I am checking that this agent has started. Say started when it has.",
    "Hey, the next message will have the actual brief. Say ready when ready.",
    "Hello, first I need a ready check. Say all set when you are set.",
    "Hi, just a quick new-window hello. Tell me when ready.",
    "Hey, I am about to send you the real prompt. Say send it when ready.",
    "Hello, making sure we are connected before the task. A short yes works.",
    "Hi, please let me know this session is ready. Say ready when ready.",
    "Hey, ready check before I pass over the brief. Say good to go when ready.",
)


@dataclasses.dataclass(frozen=True)
class Turn:
    """A single Shannon invocation described as data."""

    session_id: str
    resume: bool
    body: str
    delivery: str
    expect: str
    timeout: int
    pre_sleep_s: float


@dataclasses.dataclass(frozen=True)
class SessionPlan:
    """The full plan for one Shannon worker invocation."""

    kind: str
    session_id: str
    pre_turns: tuple[Turn, ...]
    main: Turn
    voice: str


def _serialize_session_plan(plan: SessionPlan) -> dict[str, Any]:
    """Serialize ``plan`` into the ``shannon_plan`` receipt field."""
    pre_turn_records: list[dict[str, Any]] = []
    for pt in plan.pre_turns:
        if pt.expect == "non_empty":
            pt_kind = "handshake"
        elif pt.body.startswith("/clear"):
            pt_kind = "clear"
        elif pt.body.startswith("/compact"):
            pt_kind = "compact"
        else:
            pt_kind = "context_op"
        pre_turn_records.append(
            {
                "kind": pt_kind,
                "session_id": pt.session_id,
                "pre_sleep_s": pt.pre_sleep_s,
            }
        )
    return {
        "kind": plan.kind,
        "session_id": plan.session_id,
        "voice": plan.voice,
        "pre_turns": pre_turn_records,
        "main": {
            "delivery": plan.main.delivery,
            "resume": plan.main.resume,
            "pre_sleep_s": plan.main.pre_sleep_s,
        },
    }


def _rng_session_id(rng: random.Random) -> str:
    """Build a deterministic UUIDv4 from the injected rng."""
    b = bytearray(rng.randbytes(16))
    b[6] = (b[6] & 0x0F) | 0x40
    b[8] = (b[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(b)))


def _rng_uniform_or_zero(rng: random.Random, low: float, high: float) -> float:
    """Sample ``rng.uniform`` with Shannon's existing delay guard rails."""
    if high <= 0:
        return 0.0
    if low > high:
        low = high
    return rng.uniform(low, high)


def plan_session(
    step: str,
    *,
    stored_id: str | None,
    fresh: bool,
    cfg: Any,
    rng: random.Random,
) -> SessionPlan:
    """Pure, rng-seeded planner for a Shannon run."""
    has_session = stored_id is not None
    explicit_fresh = fresh if step == "execute" else False

    if not has_session:
        kind = "new"
    elif not cfg.session_roulette_enabled:
        kind = "resume" if (step == "execute" and not explicit_fresh) else "new"
    elif explicit_fresh:
        kind = "new"
    else:
        kind = (
            "compact"
            if rng.random() < cfg.session_compact_probability
            else "clear"
        )

    if kind == "new":
        main_session_id = _rng_session_id(rng)
        main_resume = False
    else:
        assert stored_id is not None
        main_session_id = stored_id
        main_resume = True

    pre_turns: list[Turn] = []
    main_pre_sleep = 0.0

    if kind == "new":
        handshake_roll = rng.random()
        if cfg.readiness_probe_forced or handshake_roll < cfg.handshake_probability:
            handshake_sleep = _rng_uniform_or_zero(
                rng,
                cfg.handshake_delay_min_seconds,
                cfg.handshake_delay_max_seconds,
            )
            readiness_prompt = rng.choice(_SHANNON_READINESS_PROMPTS)
            pre_turns.append(
                Turn(
                    session_id=main_session_id,
                    resume=False,
                    body=readiness_prompt,
                    delivery="argv",
                    expect="non_empty",
                    timeout=cfg.readiness_timeout_seconds,
                    pre_sleep_s=handshake_sleep,
                )
            )
            main_resume = True
            main_pre_sleep = _rng_uniform_or_zero(
                rng,
                cfg.handshake_delay_min_seconds,
                cfg.handshake_delay_max_seconds,
            )
    elif kind in ("clear", "compact"):
        op_sleep = _rng_uniform_or_zero(
            rng,
            cfg.context_op_delay_min_seconds,
            cfg.context_op_delay_max_seconds,
        )
        slash = "/clear" if kind == "clear" else "/compact"
        pre_turns.append(
            Turn(
                session_id=main_session_id,
                resume=True,
                body=slash,
                delivery="argv",
                expect="rotation" if kind == "clear" else "completion",
                timeout=cfg.context_op_timeout_seconds,
                pre_sleep_s=op_sleep,
            )
        )

    main = Turn(
        session_id=main_session_id,
        resume=main_resume,
        body="",
        delivery="argv",
        expect="envelope",
        timeout=cfg.execute_timeout_seconds,
        pre_sleep_s=main_pre_sleep,
    )

    return SessionPlan(
        kind=kind,
        session_id=main_session_id,
        pre_turns=tuple(pre_turns),
        main=main,
        voice=cfg.voice,
    )


def _shannon_run_nonce(state: PlanState, step: str) -> int:
    """Advance and return a per-state Shannon run nonce for retry-safe new sessions."""
    iteration = int(state.get("iteration", 0) or 0)
    meta = state.setdefault("meta", {})
    nonces = meta.setdefault("shannon_run_nonces", {})
    if not isinstance(nonces, dict):
        nonces = {}
        meta["shannon_run_nonces"] = nonces
    key = f"{step}:{iteration}"
    current = int(nonces.get(key, 0) or 0) + 1
    nonces[key] = current
    return current


def _seeded_rng_for_run(state: PlanState, step: str, *, nonce: int = 0) -> random.Random:
    """Per-(plan, step, iteration) seeded rng for ``plan_session``."""
    plan_id = str(state.get("name", ""))
    iteration = int(state.get("iteration", 0) or 0)
    seed_bytes = hashlib.sha256(
        f"{plan_id}|{step}|{iteration}|{nonce}".encode("utf-8")
    ).digest()
    return random.Random(int.from_bytes(seed_bytes[:8], "big"))


__all__ = [
    "SessionPlan",
    "Turn",
    "_seeded_rng_for_run",
    "_serialize_session_plan",
    "_shannon_run_nonce",
    "plan_session",
]
