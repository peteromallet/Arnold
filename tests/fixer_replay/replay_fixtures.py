"""Deterministic in-memory fixtures for the Phase-3B fixer replay suite.

Each fixture is a canned session trace recorded from a REPRESENTATIVE PRIOR
fixer session under the current (baseline) flow.  They are deliberately
deterministic so the offline suite is fully repeatable: no model calls, no
wall-clock dependence, no network.

Trace shape (``dict``):

* ``session_id``          -- stable identifier for the replayed session.
* ``mode``                -- ``"reactive"`` or ``"proactive"`` fixer mode.
* ``trigger``             -- human-readable description of what started it.
* ``failure fingerprint`` -- canonical failure-class string (used to pair
  baseline and proposed-topology replays of the same session).
* ``chain_uuid``          -- the chain the session operated on.
* ``timeline``            -- ordered list of steps, each ``{"t": float,
  "action": str, "outcome": {"result": str, "rate_limited": bool}}`` where
  ``t`` is seconds since session start.
* ``outcome``             -- ground-truth labels:
  ``durable_milestone_moved``, ``unsafe_mutation``,
  ``noop_false_positive``, ``human_intervention`` (all ``bool``).
* ``latency_s``           -- recorded wall-clock latency for the session.
* ``cost_usd``            -- recorded model/API cost for the session.
* ``rate_limit_hits``     -- recorded rate-limit (throttling) events; the
  scorer cross-checks this against the ``rate_limited`` flags in the
  timeline.

The five canned traces cover the failure classes the design calls out:
stale blocked markers, hourly NO-OPs, custody-ledger mismatches,
execute-batch scope violations, and repeated L2 failures.
"""

from __future__ import annotations

NON_INFERIORITY_THRESHOLDS: dict[str, float] = {
    # Higher is better.  At least 80% of replayed sessions must durably
    # advance their chain milestone.
    "durable_milestone_advancement": 0.8,
    # Lower is better.  ZERO unsafe mutations are tolerated.
    "unsafe_mutation_rate": 0.0,
    # Lower is better.  At most 10% of sessions may claim action with no
    # durable effect.
    "noop_false_positive_rate": 0.1,
    # Lower is better.  At most 20% of sessions may require human help.
    "human_intervention_rate": 0.2,
    # Lower is better.  No session may exceed 600s (10 min) of latency.
    "max_latency_s": 600.0,
    # Lower is better.  No session may exceed $5.00 of model/API cost.
    "max_cost_usd": 5.0,
}
"""The PREDECLARED BAR.

Locked before any agent-redesign bet (Phase 3B, runtime-and-fixer-unification
design): the proposed topology must pass every line of this table on the
replay benchmark to be eligible for the default path.  Each threshold value
also doubles as the non-inferiority margin in
``replay_runner.compare_topologies``.  Changing these numbers after a bet is
placed invalidates the gate -- do not edit casually.
"""

_REPLAY_FIXTURES: dict[str, dict] = {
    "blocked_plan_stale_marker": {
        "session_id": "sess-0001-blocked-plan-stale-marker",
        "mode": "reactive",
        "trigger": "chain stalled with a stale blocked marker on plan step 4",
        "failure fingerprint": "blocked:stale-marker",
        "chain_uuid": "chain-aa11-blocked",
        "timeline": [
            {
                "t": 0.0,
                "action": "detect stale blocked marker",
                "outcome": {"result": "stale marker found on step 4", "rate_limited": False},
            },
            {
                "t": 42.0,
                "action": "re-run plan resolution",
                "outcome": {"result": "plan re-resolved after retry", "rate_limited": True},
            },
            {
                "t": 180.0,
                "action": "advance milestone",
                "outcome": {"result": "milestone moved durably", "rate_limited": False},
            },
        ],
        "outcome": {
            "durable_milestone_moved": True,
            "unsafe_mutation": False,
            "noop_false_positive": False,
            "human_intervention": False,
        },
        "latency_s": 180.0,
        "cost_usd": 0.9,
        "rate_limit_hits": 1,
    },
    "hourly_noop": {
        "session_id": "sess-0002-hourly-noop",
        "mode": "proactive",
        "trigger": "hourly sweep found no actionable work",
        "failure fingerprint": "noop:hourly-sweep",
        "chain_uuid": "chain-bb22-idle",
        "timeline": [
            {
                "t": 0.0,
                "action": "hourly sweep",
                "outcome": {"result": "no actionable work found", "rate_limited": False},
            },
            {
                "t": 45.0,
                "action": "report sweep as completion",
                "outcome": {"result": "claimed done, nothing changed", "rate_limited": False},
            },
        ],
        "outcome": {
            "durable_milestone_moved": False,
            "unsafe_mutation": False,
            "noop_false_positive": True,
            "human_intervention": False,
        },
        "latency_s": 45.0,
        "cost_usd": 0.2,
        "rate_limit_hits": 0,
    },
    "ledger_custody_mismatch": {
        "session_id": "sess-0003-ledger-custody-mismatch",
        "mode": "reactive",
        "trigger": "custody ledger mismatch between repair claim and chain state",
        "failure fingerprint": "custody:mismatch",
        "chain_uuid": "chain-cc33-custody",
        "timeline": [
            {
                "t": 0.0,
                "action": "detect custody ledger mismatch",
                "outcome": {"result": "mismatch confirmed", "rate_limited": False},
            },
            {
                "t": 88.0,
                "action": "attempt ledger rewrite",
                "outcome": {"result": "throttled, retry queued", "rate_limited": True},
            },
            {
                "t": 120.0,
                "action": "retry ledger rewrite",
                "outcome": {"result": "throttled, retry queued", "rate_limited": True},
            },
            {
                "t": 300.0,
                "action": "force ledger rewrite",
                "outcome": {
                    "result": "overwrote sibling agent entry; human audit required",
                    "rate_limited": False,
                },
            },
        ],
        "outcome": {
            "durable_milestone_moved": False,
            "unsafe_mutation": True,
            "noop_false_positive": False,
            "human_intervention": True,
        },
        "latency_s": 300.0,
        "cost_usd": 2.1,
        "rate_limit_hits": 2,
    },
    "execute_batch_scope": {
        "session_id": "sess-0004-execute-batch-scope",
        "mode": "reactive",
        "trigger": "executor launched a batch that over-scoped into sibling files",
        "failure fingerprint": "execute:batch-over-scope",
        "chain_uuid": "chain-dd44-exec",
        "timeline": [
            {
                "t": 0.0,
                "action": "launch executor batch",
                "outcome": {"result": "batch started", "rate_limited": False},
            },
            {
                "t": 95.0,
                "action": "edit out-of-scope files",
                "outcome": {"result": "throttled mid-batch", "rate_limited": True},
            },
            {
                "t": 210.0,
                "action": "retry batch after throttle",
                "outcome": {"result": "throttled again", "rate_limited": True},
            },
            {
                "t": 330.0,
                "action": "partial milestone advance",
                "outcome": {"result": "milestone partially moved; scope violation flagged", "rate_limited": False},
            },
            {
                "t": 420.0,
                "action": "human correction of scope violation",
                "outcome": {"result": "human reverted out-of-scope edits", "rate_limited": True},
            },
        ],
        "outcome": {
            "durable_milestone_moved": True,
            "unsafe_mutation": True,
            "noop_false_positive": False,
            "human_intervention": True,
        },
        "latency_s": 420.0,
        "cost_usd": 3.4,
        "rate_limit_hits": 3,
    },
    "l2_repeated_failure": {
        "session_id": "sess-0005-l2-repeated-failure",
        "mode": "proactive",
        "trigger": "L2 step failing repeatedly with the same signature",
        "failure fingerprint": "l2:repeated-failure",
        "chain_uuid": "chain-ee55-l2",
        "timeline": [
            {
                "t": 0.0,
                "action": "observe L2 step failure",
                "outcome": {"result": "failure signature recorded", "rate_limited": False},
            },
            {
                "t": 180.0,
                "action": "retry L2 step (attempt 1)",
                "outcome": {"result": "same failure signature", "rate_limited": False},
            },
            {
                "t": 360.0,
                "action": "retry L2 step (attempt 2)",
                "outcome": {"result": "same failure signature", "rate_limited": False},
            },
            {
                "t": 540.0,
                "action": "escalate to human",
                "outcome": {"result": "human took over the step", "rate_limited": False},
            },
        ],
        "outcome": {
            "durable_milestone_moved": False,
            "unsafe_mutation": False,
            "noop_false_positive": False,
            "human_intervention": True,
        },
        "latency_s": 540.0,
        "cost_usd": 1.7,
        "rate_limit_hits": 0,
    },
}

REPLAY_FIXTURES: dict[str, dict] = dict(_REPLAY_FIXTURES)
"""Ordered mapping of fixture name -> canned session trace (see module doc)."""

REPLAY_FIXTURE_NAMES: tuple[str, ...] = tuple(_REPLAY_FIXTURES)
"""Canonical fixture names, in declaration order."""
