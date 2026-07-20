# Three-hour babysitter: agent-aware repair ownership gate

This block is embedded in `sched_pinned_e894_epics_babysit_3h`. It is the
decision contract for every unhealthy target and does not expand the
schedule's existing authorization or target allowlist.

## Agent-aware repair ownership gate

Before any repair, resume, relaunch, or source mutation for an unhealthy
target, enumerate active resident-managed agents from the canonical unified
inventory and verify candidate manifests and artifacts directly. Include
resident-delegated and automatic-repair managed runs discoverable below the
allowlisted workspace roots; do not infer an agent from a PID, tmux pane, or
free-text process listing.

Match target to agent explicitly, never by text similarity alone. Record and
compare all of:

- the exact session identity and marker or chain-spec identity;
- the canonical workspace path;
- the current blocker identity and declared recovery objective; and
- the managed run ID, canonical manifest, declared prompt/description, and
  provenance or linked repair objective.

A candidate is relevant only when its declared scope explicitly names the
same session or chain and workspace, and its blocker/recovery objective covers
the target's currently observed blocker without a conflicting target. Missing
fields may make a candidate plausible but uncertain; a conflicting session,
chain, workspace, or objective is durable off-path evidence.

For `custody-control-plane-20260714`, treat
`subagent-20260720-193054-5b0373d2` as an explicitly linked candidate for the
provider-timeout/fallback and safe Custody recovery objective. Reassess it
from its canonical artifacts on every fire. Do not launch another Custody
repair while it remains fresh and on-path, and do not take over its source
changes or independently resume Custody.

Use evidence time, not observation time. Substantive progress is a new or
changed durable target state/recovery receipt, a committed or inspectable
source artifact/diff with verified checks, a new execution artifact with
meaningful task output, or a phase/task/batch/milestone transition. A PID,
process liveness, tmux presence, heartbeat, token heartbeat, log touch with no
new semantic content, or an in-flight call alone is not substantive progress.
Evidence is fresh for 6 hours from its own durable timestamp. Six hours spans
two schedule cadences, so a long verified implementation turn is not displaced
after one quiet fire.

Classify and decide conservatively:

1. `defer_to_agent`: explicit relevant match plus substantive evidence no more
   than 6 hours old. The agent owns the repair; skip a duplicate.
2. `hold_uncertain_no_duplicate`: the candidate is plausibly relevant but
   linkage or substantive progress is incomplete, older than 6 hours, or not
   yet conclusive, and durable off-path evidence is absent. Leave it running,
   skip a duplicate, record the uncertainty, and reassess next occurrence.
3. `replace_agent`: only durable evidence proves an explicit target mismatch,
   a terminal failed/interrupted outcome with no valid continuing owner, or at
   least 12 hours since the last substantive evidence (or since start when
   none exists) together with a specifically identified, better-supported,
   currently valid recovery route. Twelve hours is four schedule cadences;
   elapsed time is only one required fact and is never sufficient by itself.
4. `repair_without_candidate`: no relevant or plausibly relevant active
   candidate exists. The normal supported repair path may proceed.

Never cancel for slowness, lack of a final answer, liveness alone, or stale
heartbeat alone. Absence of evidence alone is not off-path proof. Before any
cancellation, re-read the manifest and latest artifacts to close the race,
verify the same run/session/blocker assessment still holds, and use only a
supported resident-managed cancellation/supersession operation. Require a
durable receipt naming the run ID, requested action, evidence basis, timestamp,
and observed terminal/superseded result. If that supported operation or receipt
is unavailable, do not signal or kill the process, do not launch a replacement,
and classify `hold_uncertain_no_duplicate`.

The existing one-at-a-time rule is global across these three targets for the
fire: choose at most one repair owner/intervention at a time. A deferred or
uncertain active relevant agent occupies that repair slot. Observe and report
the other targets, but do not start a parallel repair. A replacement may start
only after the prior owner's verified cancellation/supersession receipt.

For every target, write an `agent_assessment` into the occurrence result with:

- target session, chain/spec/marker, workspace, and current blocker/objective;
- each candidate run ID and canonical manifest, explicit match fields,
  observed lifecycle status, substantive evidence kind/path/digest or cursor,
  the evidence's UTC timestamp, assessment UTC timestamp, and evidence age;
- classification, decision, rationale, uncertainty, and whether the candidate
  occupies the one-at-a-time slot; and
- when applicable, the cancellation/supersession receipt and replacement run
  receipt with both run IDs and timestamps.

Immediately before reporting, re-read every chosen candidate and cited
artifact. The occurrence result must distinguish target-chain recovery from
agent progress; never claim the chain recovered from source changes or tests
alone.

## Decision fixtures

These fixtures define the required classification boundary:

- Linked Custody candidate with a matching declared objective and a new
  verified diff/test artifact within 6 hours -> `defer_to_agent`; no duplicate
  and no cancellation.
- Live agent for another session/workspace or another blocker -> unrelated;
  it does not block the target's normal repair path and is not cancelled by
  this schedule.
- Matching candidate with a durable terminal failure -> `replace_agent` only
  after revalidation and a supported cancellation/supersession receipt when
  one is still applicable; otherwise record terminal evidence and use the
  normal one-at-a-time repair path.
- No relevant or plausible candidate -> `repair_without_candidate` under the
  existing pinned-runtime and safety gates.
