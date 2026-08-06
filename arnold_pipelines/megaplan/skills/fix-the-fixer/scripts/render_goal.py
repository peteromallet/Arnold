#!/usr/bin/env python3
"""Render the single-agent fix-the-fixer operator contract."""

from __future__ import annotations

import argparse
import json


def _target_text(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError("--target must contain epic or session text")
    if "\x00" in value:
        raise argparse.ArgumentTypeError("--target must not contain NUL")
    return value


def render_goal(target: str) -> str:
    encoded_target = json.dumps(target, ensure_ascii=False)
    return f"""/goal
Act as the only implementation/recovery agent for target {encoded_target}.

Diagnose the failed fixer and the backstop that missed it; implement and verify
the fixer repair; use the supported resident/cloud transport; retrigger ordinary
repair; and prove the actual epic or session advances beyond its frozen baseline.

Operator contract:
- Use $superfixer-debug fully and $megaplan-cloud when this is a cloud target.
- Launch no agents or subagents. You are the one mutation owner.
- NO-OP GUARD: FIRST enumerate blocked/failed chains via megaplan cloud status /
  introspect. If none are blocked or failed, report "No blocked/failed chains
  found; nothing to fix" and end. Do not invent work, fabricate a failure, or
  touch healthy/running chains.
- COORDINATION GUARD: before any recovery, check whether another fixer/repair is
  already active for the target chain (per-chain lease held, active repair
  request/claim, or a running managed subagent for that session). If one is
  active, report "Another fixer is already active for this chain; standing down"
  and end — never launch a competing fixer.
- Fast path: if the fix is obvious — unambiguous root cause, minimal/contained
  change, verifiable with a focused test, no authority/credential gate — apply it
  immediately and verify, and keep pushing until verified working.
- Escalate to Sol stage 2 after three distinct, verified fix attempts that do not
  advance the occurrence (never three blind retries); escalate sooner on unchanged
  evidence or an infra/credential blocker. Each escalation carries an evidence
  delta + rollback state; cap Sol cycles to prevent recursion.
- Resolve canonical target IDs, the blocker occurrence, all custody sources,
  pinned source/runtime/installed identities, and effect authority from raw
  evidence. The target text is orientation, not proof.
- Walk TRACKED, FIXED, INTENT, and CONTEXT. Name the first failed fixer layer and
  the higher backstop that failed to catch it. Hunt bounded sibling instances.
- Preserve live productive work. Never weaken guards, edit the epic directly,
  or accept a process, return code, commit, self-report, or heartbeat as recovery.
- For source changes, use a clean isolated worktree from the verified pinned
  target; preserve dirty checkouts; add regressions; review the diff; commit;
  revalidate lineage; and integrate only within inherited authority.
- Do not push, deploy, restart, use broad process control, or expand authority
  unless the immutable invocation envelope explicitly authorizes that effect.
  If a required effect is unauthorized, retain verified work and state the gate.
- Retrigger the ordinary fixer through its supported command/request seam and
  verify its exact claim, attempt, evidence, and action. The meta-fixer must not
  substitute for ordinary recovery.
- Prove the original blocker occurrence cleared and the canonical epic/session
  cursor advanced. Then prove L2/L3 would catch recurrence. A distinct new
  blocker may be reported only after original recovery is demonstrated.
- Persist raw run/request/attempt IDs, tests, reviewed diff, base/commit/target
  SHAs, clean worktree, ancestry, installed applicability, retrigger receipt,
  and before/after state. Separate evidence, inference, and unknowns.

Continue through ordinary failures until every terminal gate passes or a real
target-lineage, external-authority, or human-approval gate prevents progress.
Report the durable result to the existing synthesis/delivery owner; do not emit
an independent user-facing completion when this run is an internal contributor.
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render one durable fix-the-fixer /goal contract."
    )
    parser.add_argument(
        "--target",
        required=True,
        type=_target_text,
        help="Text identifying the epic, session, plan, or incident",
    )
    args = parser.parse_args()
    print(render_goal(args.target), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
