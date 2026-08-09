"""Phase-3B fixer replay/evaluation suite.

This package is the evidence gate that decides whether DeepSeek Flash plus the
swarm -> corps -> executor topology becomes the DEFAULT fixer path.  Per the
runtime-and-fixer-unification design, it is built FIRST, before any agent
redesign bet is landed.

What the suite measures (5 metrics, each against a predeclared bar in
``replay_fixtures.NON_INFERIORITY_THRESHOLDS``):

1. durable milestone advancement  -- fraction of replayed sessions whose
   fixer run durably moved its chain milestone forward.
2. unsafe-mutation rate          -- fraction of sessions that mutated state
   unsafely (out-of-scope edits, custody overwrites, clobbered ledgers).
3. NO-OP false-positive rate     -- fraction of sessions that claimed
   completion/action while nothing actually changed.
4. human-intervention rate       -- fraction of sessions that required a
   human to unstick or audit the fixer.
5. operational efficiency        -- latency (mean/max per session), cost
   (per-session max and run total), and rate-limit hits (throttling events).

How it gates the Flash default: an aggregate over replayed sessions must pass
``NON_INFERIORITY_THRESHOLDS`` (the predeclared bar) AND the proposed
topology must be non-inferior to the current flow on every metric
(``replay_runner.compare_topologies``).  Only if both hold is the
swarm -> corps -> executor topology landed as the default path; otherwise the
current flow stays.

Live replay rule: the offline suite runs green on the recorded/example
session traces in ``replay_fixtures.REPLAY_FIXTURES`` and never makes model
calls.  A live replay (real model calls across the current flow and the
proposed topology) is OPT-IN: set ``FIXER_REPLAY_LIVE=1`` in the environment.
Any test that would perform live model calls calls
``replay_runner.require_live_replay()`` and is skipped (``pytest.skip``)
whenever the flag is unset -- which is the default.
"""

from __future__ import annotations

__all__: list[str] = []
