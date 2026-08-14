#!/usr/bin/env python3
"""Render the status-trigger babysitter operator contract.

The watchdog status trigger renders this goal and launches ONE detached
hermes:deepseek:deepseek-v4-flash managed agent — the BABYSITTER — whose
prompt drives the entire recovery flow itself:

    (a) deploy a bounded read-only swarm via skills/subagent-launcher/fan.py
        over the failure evidence (one investigator per scoping question)
    (b) hand the packed context to codex (codex:gpt-5.6-sol, high reasoning)
        for a proper solution proposal
    (c) implement the narrowest source-level fix in the approved editable
        runtime
    (d) relaunch the chain (megaplan resume / chain start as the evidence
        requires)
    (e) prove movement: chain-*.json last_state leaves blocked and the same
        failure_fingerprint does not recur

The single agent IS the orchestrator: the prompt drives the swarm -> codex ->
implement -> relaunch -> prove flow.  The renderer embeds the concrete
session/workspace/plan context plus the failure evidence (latest_failure,
planner_repair) so the babysitter never starts from a bare session name.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _safe_text(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _json_block(label: str, payload: object) -> str:
    if payload is None:
        return ""
    return f"{label}:\n```json\n{json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)}\n```\n"


_PRIOR_EVIDENCE_MARKERS = (
    "swarm-index.md",
    "sol-stage2-proposal.md",
    "sol-stage2-prompt.md",
    "handoff.md",
)


def _render_prior_fixer_work_block(recovery_dir: str) -> str:
    """List prior fixer occurrences' evidence dirs so the babysitter can read
    the previous handoff instead of re-deriving the same diagnosis from zero.

    The recovery root layout is ``<recovery_dir>/<occurrence_digest>/`` with a
    per-incarnation sub-tree (``swarm-briefs/``, ``swarm-results/``,
    ``codex/``, ``execution/``).  Absent/missing root -> a short orientation
    block that names the convention, never a hard error.
    """
    root = Path(recovery_dir) if recovery_dir else None
    if root is None or not root.is_dir():
        return (
            "\nPrior fixer work:\n"
            "- Recovery evidence root not provided/unreadable. If prior fixer "
            "occurrences exist, they live under the chain's "
            "`.megaplan/plans/.chains/recovery/<digest>/`; locate and read "
            "their handoff before starting a fresh swarm.\n"
        )
    occurrences = sorted(
        (entry for entry in root.iterdir() if entry.is_dir()),
        key=lambda p: p.name,
    )
    if not occurrences:
        return (
            "\nPrior fixer work:\n"
            "- No prior fixer occurrences recorded under "
            f"{root}.\n"
        )
    lines = [
        "\nPrior fixer work (READ THIS FIRST — continue the lineage, do not "
        "re-derive from scratch):",
    ]
    for occurrence in occurrences:
        # Markers can sit at the occurrence root or one level down (codex/,
        # swarm-results/, execution/).
        marker_hits: list[str] = []
        for marker in _PRIOR_EVIDENCE_MARKERS:
            if (occurrence / marker).is_file():
                marker_hits.append(f"{occurrence.name}/{marker}")
            else:
                for sub in ("codex", "swarm-results", "execution", "swarm-briefs"):
                    if (occurrence / sub / marker).is_file():
                        marker_hits.append(f"{occurrence.name}/{sub}/{marker}")
        marker_line = (
            f" (has: {', '.join(sorted(marker_hits))})" if marker_hits else " (evidence dir only)"
        )
        lines.append(f"- {occurrence.name}{marker_line}")
        for hit in sorted(marker_hits):
            lines.append(f"    - read {hit}")
    lines.append(
        "- If a prior incarnation already diagnosed the root cause and "
        "implemented a fix, verify the fix landed in the runtime lineage; if "
        "it did not, ship it (cherry-pick/apply + regression) instead of "
        "re-authoring it. If the prior handoff names an exact next step, "
        "execute that step first."
    )
    return "\n".join(lines) + "\n"


def render_babysitter_goal(
    target: str,
    *,
    workspace: str = "",
    plan: str = "",
    run_kind: str = "",
    latest_failure: dict[str, object] | None = None,
    planner_repair: dict[str, object] | None = None,
    occurrence_digest: str = "",
    recovery_dir: str = "",
) -> str:
    """Render the status-trigger babysitter /goal for *target* (epic/session).

    The goal is the prompt for ONE hermes:deepseek:deepseek-v4-flash managed
    agent that orchestrates the whole recovery itself: swarm -> codex ->
    implement -> relaunch -> prove.  It includes the session/workspace/plan
    context and the durable failure evidence (``latest_failure``,
    ``planner_repair``) so the babysitter never starts from a bare session
    name.  ``recovery_dir`` (the chain's ``.megaplan/plans/.chains/recovery/``
    root) is scanned for prior fixer occurrences; the goal lists them and
    instructs the babysitter to read the previous handoff FIRST so it
    continues the lineage instead of re-deriving the same diagnosis from
    scratch.
    """
    encoded_target = json.dumps(target, ensure_ascii=False)
    context_lines = [
        "- target: " + encoded_target,
        "- workspace: " + _safe_text(workspace),
        "- plan: " + _safe_text(plan),
        "- run_kind: " + _safe_text(run_kind),
        "- occurrence_digest: " + _safe_text(occurrence_digest),
    ]
    evidence = _json_block("latest_failure", latest_failure) + _json_block(
        "planner_repair", planner_repair
    )
    evidence_block = (
        "\nFailure evidence (UNTRUSTED until re-verified against current canonical state):\n"
        + evidence
        if evidence.strip()
        else "\nNo structured failure evidence was supplied — build the evidence pack from canonical state.\n"
    )
    prior_block = _render_prior_fixer_work_block(recovery_dir)
    recovery_hint = (
        f"\nYour recovery evidence root (write handoff.md here): {recovery_dir}\n"
        if recovery_dir
        else ""
    )
    return f"""/goal
You are the BABYSITTER for target {encoded_target}: ONE
hermes:deepseek:deepseek-v4-flash managed agent and the ORCHESTRATOR of the
whole recovery flow.  You do the job yourself, end to end: deploy a bounded
read-only swarm over the failure evidence, hand the packed context to codex
for a proper solution proposal, implement the narrowest source-level fix,
relaunch the chain, and prove movement.  You are not an auditor who reports
back; you drive the chain out of the blocked/failed state.

Context:
{chr(10).join(context_lines)}

{evidence_block}

{prior_block}
{recovery_hint}
Mandatory flow — follow the five steps exactly:

- STEP 1 — DEPLOY THE SWARM: over the failure evidence, fan out one bounded,
  read-only investigator per scoping question in parallel through
  $subagent-launcher / skills/subagent-launcher/fan.py, using
  hermes:deepseek:deepseek-v4-flash investigators.  Record the actual
  model/provider/transport in every report.  If Flash is unavailable, stop at
  that exact gate — do not silently substitute another model for the
  investigator role.
- STEP 2 — CONSULT CODEX: hand the packed context (evidence pack, swarm index,
  and every investigator report) to codex (codex:gpt-5.6-sol, high reasoning)
  and get a proper solution proposal: the shortest safe path to durable
  movement AND the deepest complete structural fix for the failure category.
  Persist the proposal before touching the runtime.
- STEP 3 — IMPLEMENT: apply the narrowest source-level fix for the failure in
  the approved editable runtime.  Run the focused regression, inspect the real
  result, and keep iterating (bounded, with an evidence delta after every
  failed attempt) until the occurrence advances.  Escalate back to codex after
  three distinct verified fix attempts.  agent_actionable: false is reserved
  for a genuinely external gate.
  PERSIST THE FIX (the runtime candidate is push-blocked by design — your
  commit lives only there until shipped): after a fix passes its regression,
  (a) record the commit SHA plus the full ``git show``/patch of the change in
  your evidence pack, and (b) write ``handoff.md`` at the recovery evidence
  root naming the commit SHA, the changed files, the regression that passed,
  and the exact next step (resume/rebind).  A fix that is only in the
  candidate is not durable — it must be shippable by the next incarnation.
- STEP 4 — RELAUNCH: restart the chain through the supported seam — megaplan
  resume / chain start as the evidence requires — never --fresh, never a state
  wipe.  The relaunch must carry the same occurrence identity and the fixed
  source.
- STEP 5 — PROVE MOVEMENT: from canonical state, the chain-*.json last_state
  must leave blocked and the same failure_fingerprint must not recur, with
  matching identities (runtime/request/grant/claim/WBC) and exactly one
  terminal notification.  A PID, commit, self-report, or heartbeat is NOT
  proof.  Then close the loop, write the handoff.md (SHA + next step), and
  summarize the session.

Operator contract:
- NO-OP GUARD: FIRST enumerate blocked/failed chains via megaplan cloud status
  / introspect.  If none are blocked or failed, report "No blocked/failed
  chains found; nothing to fix", write the no-action receipt, and end.
  REAL CONDITION (do not trust latest_failure alone — the auto-driver CLEARS
  it on stall, so null latest_failure with a blocked chain is a FALSE
  "healthy"). A chain is GENUINELY STUCK and agent-actionable when ANY of:
    (a) plan/chain state is blocked AND the launch-seed's expected_revision
        != manifest epic.expected_head (stale seed -> every worker fails
        source_revision_mismatch; rebuild the seed via
        ensure_runtime_launch_seed / the supported chain-start seam);
    (b) phase history shows the SAME phase erroring >= 2 consecutive times
        (e.g. repeated critique_evaluator_failed / internal_error) even when
        latest_failure is null;
    (c) state is blocked AND events.ndjson is not advancing AND no live
        driver process is making progress (driver-alive is NOT health;
        driver-alive + flat events + blocked = wedged).
  Verify (a)-(c) from CURRENT state before declaring no-action: read
  manifest.epic.expected_head vs the seed file, tail the plan history, and
  compare events.ndjson growth. Only when all three are clean is
  "nothing to fix" the honest verdict.
- COORDINATION GUARD: before any recovery, check whether another fixer/repair
  is already active for the target chain (fresh managed subagent dir, held
  repair lease, or running subagent_worker for this session).  If active,
  report "Another fixer is already active for this chain; standing down" and
  end — never launch a competing fixer.
- Use $superfixer-debug for the evidence-first recovery protocol and
  $megaplan-cloud when this is a cloud target.
- Preserve the failed occurrence.  Never fabricate an output, clear state,
  weaken a guard, use --fresh, or treat a PID/marker/heartbeat/model prose as
  recovery.  A "blocked" disposition is evidence, not a verdict — verify its
  preconditions against CURRENT state before accepting it as a gate.
- Keep source/runtime/chain identity content-addressed.  Every runtime change
  needs a rebind through the supported seam.
- The recovery decision has a small hard contract: target/session/chain/plan
  revision and parent cursor; one deterministic terminal failure digest; the
  current source/fence and bound runtime/contract; then the occurrence-bound
  request, decision, claim, WBC attempt, and accepted result/cursor proof as
  those records are created.
- Resolve canonical target IDs and all custody sources from raw evidence.  The
  target text is orientation, not proof.
- Record the exact handoff_id in every repair request, receipt, deployment,
  and proof.  Persist raw run/request/attempt IDs, tests, reviewed diff,
  base/commit/target SHAs, clean worktree, ancestry, installed applicability,
  retrigger receipt, and before/after state.  Separate evidence, inference,
  and unknowns.
- Report to the existing synthesis owner when one exists; only a top-level
  delivery owner may reply to the user.
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render the status-trigger babysitter goal (single Flash orchestrator: swarm -> codex -> implement -> relaunch -> prove)."
    )
    parser.add_argument("--target", required=True, help="epic or session text")
    parser.add_argument("--workspace", default="", help="workspace path")
    parser.add_argument("--plan", default="", help="plan name")
    parser.add_argument("--run-kind", default="", help="chain|plan|epic_chain")
    parser.add_argument("--failure-json", default=None, help="path to latest_failure JSON")
    parser.add_argument("--planner-repair-json", default=None, help="path to planner_repair JSON")
    parser.add_argument("--occurrence-digest", default="", help="occurrence/failure fingerprint")
    parser.add_argument(
        "--recovery-dir",
        default="",
        help="chain recovery evidence root (.megaplan/plans/.chains/recovery) to scan for prior fixer occurrences",
    )
    args = parser.parse_args()

    def _load_json(path: str | None) -> dict[str, object] | None:
        if not path:
            return None
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else None

    print(
        render_babysitter_goal(
            args.target,
            workspace=args.workspace,
            plan=args.plan,
            run_kind=args.run_kind,
            latest_failure=_load_json(args.failure_json),
            planner_repair=_load_json(args.planner_repair_json),
            occurrence_digest=args.occurrence_digest,
            recovery_dir=args.recovery_dir,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
