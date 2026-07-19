# Megaplan North Star Sense Checks in Revise

Generated: 2026-07-09

## Purpose

This note explains how North Star sense-check questions should fit into
Megaplan, especially the revise loop.

The goal is simple: when a plan or sprint drifts away from its North Star, the
system should not merely write prose like "needs work." It should create a
structured action that Megaplan can route into revise, turn into concrete plan
changes, and later enforce at gate/review.

This is meant to support the lean/hybrid version of the native semantic parity
plan: keep the hard programmatic blockers for known false-pass risks, and use
North Star questions for judgment-heavy checks.

## Where The Questions Are Defined

Questions should be defined explicitly, not generated from prose in v1.

There are three related concepts:

1. **Epic-level North Star**
   `.megaplan/initiatives/<initiative>/NORTHSTAR.md`

   This is the durable destination for the whole chain. It is already required
   for epics by the Megaplan epic flow unless explicitly opted out.

2. **Milestone/sprint North Star extension**
   `.megaplan/initiatives/<initiative>/briefs/sN-*.md` or an optional milestone
   anchor declared in `chain.yaml`

   This narrows what the North Star means for a specific sprint. It does not
   replace the epic North Star. Example: the epic North Star says "semantic
   authority must live in source"; the S4 sprint extension says "execute
   approval denial and partial resume must be source-owned in this sprint."

3. **Sprint Review / North Star Sense Check questions**
   Either in `NORTHSTAR.md` for reusable questions or in the sprint brief for
   sprint-specific questions.

   These are operational review prompts derived from the North Star. They are
   not the North Star itself. They are the questions that gate/revise/review use
   to detect drift and create actions.

Example epic-level questions:

   ```md
   ## Sprint Review / North Star Sense Check

   1. Can every claimed route/branch/loop/fanout be understood from source,
      without reading components.py, handlers, manifest maps, auto, CLI, or
      compatibility projections?
   2. Which old carriers did this sprint replace, and are they deleted, fenced,
      or proven unable to route behavior?
   3. Did this sprint introduce a second route brain?
   ```

Example sprint-specific questions:

   ```md
   ## Sprint Review / North Star Sense Check

   1. Is destructive approval denial now source-owned, not handler-owned?
   2. Does partial execute resume still preserve existing resume labels?
   3. Is old execute scheduling dead-deleted or fenced?
   ```

The effective question set for a sprint is:

```text
epic North Star questions
+ sprint-specific questions
= questions for this sprint's plan/gate/revise/review cycle
```

## Phase Responsibilities

The questions should travel with the North Star through the planning workflow,
but each phase has a different responsibility. They are not only a review-stage
artifact.

| Phase | Responsibility |
| --- | --- |
| `prep` / brief authoring | Suggest and validate that durable inputs contain appropriate questions for North-Star-critical work. Prep should not be the only place the questions live. |
| `plan` | Read the questions alongside the North Star and structure the plan so each question can be answered by planned steps, gates, scenarios, or evidence. |
| `critique` | Use the questions as a checklist to find missing plan elements, weak evidence, or drift from the end-state. |
| `gate` | Convert bad, unclear, or missing answers into structured `north_star_actions` and route to revise/escalate when blocking. |
| `revise` | Apply `north_star_actions` as concrete plan changes, or halt when the action is unmappable or needs a human decision. |
| `finalize` | Lower plan obligations created by North Star actions into executable tasks, user actions, and verification checks. |
| `execute` | Execute the finalized tasks. It does not reinterpret the questions; it receives their effects through tasks/checks. |
| `review` | Verify the promised evidence exists and block closeout for unresolved blocking actions. |

Only gate/review should create enforceable blockers. Plan and critique use the
questions to shape and inspect the plan; execute sees the resulting tasks rather
than the raw questionnaire.

## Are Questions Mandatory?

Not for every Megaplan.

They should be mandatory when either condition is true:

- The run is an epic chain with a required North Star and robustness `full` or
  above.
- The run or chain is explicitly marked `north_star_critical: true` or contains a
  `## Sprint Review / North Star Sense Check` section.

They should be optional for:

- Ordinary one-off plans.
- `bare` and `light` robustness runs, because those modes intentionally skip
  gate/review structure.
- Mechanical cleanup chains that explicitly opt out of a North Star.

`north_star_critical` needs to be a real schema field, not a convention. Put it
in `chain.yaml` under `driver` for the whole chain, and optionally on a
milestone to opt a single sprint in:

```yaml
driver:
  north_star_critical: true

milestones:
  - label: s4-execute
    idea: .megaplan/initiatives/foo/briefs/s4.md
    north_star_critical: true
```

If an epic requires a North Star but no sense-check questions are defined, the
first implementation should not fail the chain automatically. It should create a
warning and a review action:

```text
North Star exists, but no Sprint Review / North Star Sense Check questions were
defined. Add questions or explicitly mark this chain as not North-Star-critical.
```

For North-Star-critical epics, missing questions become a blocking planning/gate
issue before execution.

For `bare` and `light` robustness, do not silently raise robustness. Reject the
combination when `north_star_critical: true` or explicit sense-check questions
are present, because those modes skip the gate/review machinery that enforces
the actions.

## Skill Documentation Integration

This should be documented in the Megaplan skills because agents follow the skill
contract when creating and running chains.

Update `megaplan-epic` skill documentation:

- In the **North Star requirement** section, add that high-stakes or
  North-Star-critical epics should include a
  `## Sprint Review / North Star Sense Check` section in `NORTHSTAR.md`.
- In **Milestone fields**, note that milestone briefs may add sprint-specific
  sense-check questions, and milestone anchors may extend but not replace the
  top-level North Star.
- In **Failure semantics**, state that unresolved blocking North Star actions
  route to revise/escalate and should stop the chain rather than skip a
  milestone by default.

Update `megaplan` skill documentation:

- In `--north-star` docs, add that `NORTHSTAR.md` may include explicit
  sense-check questions.
- In **Step Rules**:
  - `plan`: answer any explicit North Star questions at plan level when present.
  - `critique`: flag missing or weak North Star answers.
  - `gate`: convert bad answers into structured `north_star_actions`.
  - `revise`: address `north_star_actions` as concrete plan changes or halt.
  - `review`: block closeout when blocking North Star actions lack evidence.
- In **Workflow**, note that this only applies when questions are present and the
  robustness mode includes the relevant phases. For `bare`/`light`, reject
  North-Star-critical mode or explicit sense-check questions with a clear error;
  do not silently raise robustness to `full`.

Do not make agents infer questions from arbitrary North Star prose in v1. The
skill docs should tell agents to write the questions explicitly.

## How The Questions Are Populated

The sprint brief carries the question text. During plan/gate/review, the agent
answers each question with evidence.

For explanation-style questions such as "can a reviewer understand this behavior
from source alone?", the answer must come from a clean-context reviewer agent
that predicts behavior from source without reading the executor's narrative, then
checks that prediction against an actual run or generated evidence. The executor
may supply pointers and artifacts, but it cannot be the sole answerer for these
questions.

Run occasional canaries against this audit path. At least twice per epic, seed a
known North Star defect into a disposable fixture or branch and require the
clean-context reviewer to catch it. If the reviewer passes the canary, halt the
methodology; the sense check has become a diary instead of a tripwire.

An answer is not enough. A bad or unclear answer must produce a structured
`north_star_action`.

Example:

```json
{
  "id": "NS-ACT-S4-001",
  "question_id": "NS-S4-approval-denial",
  "north_star_ref": "briefs/s4-execute-dag.md#Sprint Review / North Star Sense Check",
  "finding": "Destructive approval denial is still routed through handlers/execute.py.",
  "severity": "blocking",
  "action_type": "add_exit_gate",
  "required_change": "Revise S4 so approval denial is source-owned and add a dead-delete test proving the handler path cannot route denial behavior.",
  "acceptance_evidence": [
    "strict checker row evidence for approval denial",
    "dead-delete behavior test",
    "split-outcome approval denial scenario"
  ],
  "halt_if_unmappable": true
}
```

If all answers pass, no blocking action is created and the plan continues.

If a question exposes a problem, the action is routed into revise.

## How It Reaches Revise

Megaplan already has a feedback path into revise. Today, revise consumes gate
feedback and unresolved flags. It does not need a totally new orchestration loop.

The new part is to make North Star findings structured.

Recommended carrier:

```text
gate.json / gate_carry.json
  -> north_star_actions[]
  -> revise prompt
  -> revised plan
  -> gate checks again
```

The loop becomes:

```text
plan created
  -> critique/gate answers North Star questions
  -> bad answer becomes north_star_action
  -> revise receives north_star_action
  -> revise updates plan with concrete step/gate/test/halt
  -> gate re-runs
  -> execution proceeds only when blocking actions are addressed
```

`gate_carry.json` should be the preferred compact carrier when present, with
`gate.json` as the fallback. Revise must explicitly load this data; today the
revise path consumes gate summary/flags, but the carry artifact is not
automatically part of the revise prompt. The implementation must add this read
instead of assuming `gate_carry.json` already reaches revise.

## What Revise Does With Actions

Revise should not produce a narrative acknowledgement. It must either change the
plan or refuse to proceed.

Action types:

| Action type | Revise behavior |
| --- | --- |
| `add_plan_item` | Add a concrete numbered plan step with target files and success evidence. |
| `add_exit_gate` | Add a must-pass gate with command/test/artifact evidence. |
| `add_scenario_test` | Add or expand a split-outcome scenario. |
| `add_checker_row` | Add a checker/row-registry task and expected diagnostic/evidence output. |
| `add_dead_delete_test` | Add deletion/fencing plus a behavior test proving the old carrier cannot route. |
| `add_carrier_mapping` | Add carrier scan/row-registry reconciliation work. |
| `add_verification_only` | Add a verification step/gate when the work may already be present but evidence is missing. |
| `note_advisory` | Record a non-blocking answer with evidence without routing to revise. |
| `add_human_halt` | Stop before revise rewrites anything; require human decision. |
| `escalate_robustness` | Do not silently modify the plan; route to gate/escalation policy. |
| `reject_closeout` | Add closeout blocker enforced later by review/finalize. |

Revise should write which actions it handled, for example:

```json
{
  "north_star_actions_addressed": [
    {
      "id": "NS-ACT-S4-001",
      "resolution": "Added S4 exit gate and dead-delete approval denial test.",
      "plan_refs": ["Step 4", "Exit Gates / Approval denial"]
    }
  ]
}
```

This prevents "handled" from becoming untraceable prose.

It is not enough for revise to claim an action was addressed. After the worker
returns, the revise handler must validate that each addressed action has a real
plan reference and a structural marker appropriate to the action type. For
example, `add_exit_gate` must point to an exit-gate section, `add_dead_delete_test`
must point to a deletion/fencing step and behavior test, and `add_checker_row`
must point to checker/row-registry work. A claim with only prose fails and the
action remains unresolved.

## Enforcement Rules

Good answer:

- No blocking action is created.
- Gate continues normally.

Bad but fixable answer:

- Gate creates a blocking `north_star_action`.
- Gate routes to revise.
- Revise must add the requested concrete plan change.
- Gate re-checks the action.
- Execution continues only after the action is resolved.

Bad and human-decision answer:

- Gate creates `add_human_halt`.
- Revise should not try to solve it with prose.
- The run blocks or escalates.

Bad at closeout:

- Review returns `needs_rework` or blocks completion.
- Closeout cannot pass while a blocking North Star action lacks evidence.

Important rule:

Blocking North Star actions are treated like correctness/security blockers. They
cannot be force-proceeded through a cosmetic/low-risk path.

Severity is assigned by schema for dangerous categories, not by the answering
agent's discretion. Any sense-check finding involving route authority, baseline
rewrites, row/carrier exemptions, target narrowing, generated conformance
authority, or live-plan topology/resume risk is `blocking` by rule. The answerer
can add evidence or recommend an action, but it cannot downgrade those categories
to advisory.

This override belongs in the gate/review handler, not only in prompts. The agent
may propose severity, but the handler normalizes dangerous categories to
`blocking` before routing.

## What Already Exists

Most of the skeleton already exists:

- Megaplan already has North Star/anchor concepts for epic and milestone context.
- Chain scaffolding already creates initiative `NORTHSTAR.md` files.
- Gate already routes unresolved plan quality problems back to revise.
- Revise already consumes gate feedback and unresolved flags.
- Finalize already converts plan content into tasks, sense checks, and user
  actions.
- Review already has `needs_rework`, blocked, and done outcomes.

So this is not a new workflow engine.

The missing piece is a structured North Star action object that can move through
the existing feedback path.

## What Needs To Be Added

Smallest useful implementation slice:

1. Parse explicit questions from:
   - `NORTHSTAR.md`
   - sprint brief `## Sprint Review / North Star Sense Check`

2. Add `north_star_actions` to:
   - `gate.json`
   - `gate_carry.json`

3. Add gate prompt/template/schema support:
   - include North Star questions and answer requirements
   - allow `north_star_actions` through gate scratch/key promotion
   - normalize dangerous categories to blocking in handler code

4. Render `north_star_actions` in the revise prompt by explicitly loading
   `gate_carry.json` first and `gate.json` as fallback.

5. Add `north_star_actions_addressed` to `revise.json`.

6. Add a pre-worker guard in revise. This is real control-flow work, not just a
   prompt tweak:
   - halt on `add_human_halt`
   - halt on unmappable blocking actions
   - halt on baseline rewrites, route-authoritative exemptions, target narrowing,
     or live-plan topology decisions unless explicitly approved

7. Add post-worker validation in revise:
   - addressed action IDs must map to concrete plan refs
   - action-specific structural markers must be present
   - prose-only "handled" claims fail

8. Add finalize logic:
   - lower North Star plan obligations into executable tasks, user actions, or
     task sense checks as appropriate
   - keep `north_star_actions` separate from task `sense_checks` so severity and
     closeout semantics are not lost

9. Add gate logic:
   - unresolved blocking North Star actions route to revise/escalate
   - blocking North Star actions count against loop/no-progress caps
   - blocking North Star actions cannot be force-proceeded as cosmetic issues

10. Add review and transition-policy logic:
   - unresolved closeout-critical North Star actions produce `needs_rework` or
     block closeout
   - `reject_closeout` blocks the review-to-done transition even if prose says
     the task is complete

## Tests

Minimum test set:

- A fixture North Star with two explicit questions is parsed.
- A sprint brief question overrides/adds to the epic question set.
- A bad answer creates `north_star_actions[]` in `gate.json`.
- Revise prompt includes the action block.
- Revise blocks on `add_human_halt`.
- Revise records `north_star_actions_addressed`.
- A bad action with only prose and no plan change fails.
- A claimed addressed action with an invalid/missing `plan_refs` fails
  post-worker validation.
- Gate routes unresolved blocking actions to revise.
- Gate does not force-proceed unresolved blocking North Star actions.
- Severity-by-schema overrides an answering agent that marks a route-authority,
  baseline, exemption, target-narrowing, generated-conformance, or topology/resume
  finding as advisory.
- Review blocks closeout when action evidence is missing.
- A clean-context reviewer catches a seeded North Star canary defect; if it does
  not, the canary test fails.
- `north_star_critical: true` with `bare` or `light` robustness is rejected.

## What Not To Build First

Do not start with:

- LLM-generated questions from arbitrary North Star prose.
- A database-backed governance ledger.
- Full worker/model I/O replay.
- Autonomous exemption/baseline-amendment bureaucracy.
- A broad new review framework separate from gate/revise/finalize/review.
- Silent robustness auto-upgrades from `bare`/`light` to `full`.
- Overloading task `sense_checks` as the only representation for North Star
  actions.

The first version should be a small structured action path inside the existing
Megaplan loop.

## Implementation Size

The core revise-stage mechanism is one aggressive sprint:

- Parse explicit questions from durable inputs.
- Add `north_star_actions[]` to gate/carry.
- Route blocking actions to revise.
- Render actions in revise.
- Add `north_star_actions_addressed[]` to `revise.json`.
- Block on human-halt and unmappable blocking actions.
- Validate that addressed actions made concrete plan changes.

Review backstops, clean-context canaries, and skill-template polish can be
follow-on work. They are valuable, but they are not five required sprints to add
the revise-stage mechanism.

## Summary

Yes, the questions are defined per epic and/or per sprint. The questions live in
the North Star and sprint briefs. The answers are produced during gate/review.
Bad answers become structured `north_star_actions`. Those actions reach revise
through the existing gate feedback path. Revise must turn them into concrete plan
changes or halt. Gate and review enforce that blocking actions cannot be ignored.

That completes the structure without building a second planning system.
