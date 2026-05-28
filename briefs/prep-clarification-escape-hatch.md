# Prep clarification escape hatch — surface blocking ambiguities to the human

Spec shorthand: `partnered/full` (default depth). Codebase touchpoints already mapped below — no `--with-prep` needed.

## Outcome

Give the `prep` phase a first-class way to (1) record open questions / ambiguities structurally as a category distinct from findings, and (2) **optionally halt the run and hand genuinely blocking questions back to a human** instead of silently guessing. The halt behavior is **default-ON** ("prep may ask"); a flag opts out, and the decision doc tells users to opt out on cloud / unattended runs where no human is present to answer.

A reviewer checks: a prep run that hits a blocking ambiguity pauses the plan into `AWAITING_HUMAN` with the questions surfaced; the same run with the opt-out flag proceeds, recording the questions as explicit assumptions; non-blocking questions never halt under either setting.

## Background — why

Today prep already *notices* ambiguity: `_assemble_prep_outputs` writes `gap_notes` and `contradiction_notes` into `prep_metrics.json`, and the distill prompt instructs the model to populate them "when the findings disagree, time out, error, or leave concrete uncertainty." **But those notes live only in the metrics sidecar** — `distill_prep()` filters its payload down to `PREP_COMPATIBLE_KEYS`, which drops them, so nothing downstream (`plan`) ever reads them. Net effect: prep sees the ambiguity, writes it to a file nobody reads, and the planner proceeds to guess. This is the known "prep silently guesses scope instead of failing loud" gap.

The halt-and-ask primitive already exists but is wired only to the plan phase: `STATE_AWAITING_HUMAN` (an automation-terminal state the auto-driver cleanly pauses on) plus the `ClarificationRecord` type (`refined_idea / intent_summary / questions`) stored at `state["clarification"]`. This work threads prep into that existing machinery — it does not invent a new state, a new return channel, or a new interactive loop.

## Scope (IN)

1. **Structured `open_questions` in prep output.** Add an `open_questions[]` field to the prep payload, carried all the way to `plan` (i.e. added to `PREP_COMPATIBLE_KEYS` and the `prep.json` schema). Each entry is classified by severity:
   - `blocking` — a genuine ambiguity that changes the plan and the model cannot responsibly resolve alone.
   - `assume_and_proceed` — uncertainty the model resolved by making an explicit, recorded assumption (carries an `assumption` string).
   Source these from the existing `gap_notes` / `contradiction_notes` signal the distill step already produces; do not build a parallel detection mechanism.

2. **Distill prompt update.** Instruct the distill step to emit `open_questions`, classify each by severity, and for `assume_and_proceed` state the assumption it made. Keep the existing gap/contradiction notes in the metrics sidecar as-is.

   **Consumption disposition (mirror the critique "flags are hypotheses, not verdicts" stance).** Whatever consumes the prep output — the `plan` prompt, and the operator reading a paused run — must be told explicitly that **not everything prep flags is meaningful or relevant**, and to apply discretion about what to act on. A prep `open_question` (blocking or not) is a *candidate concern*, not a mandate: the planner weighs each on its merits, acts on the material ones, and dismisses the immaterial / irrelevant / already-resolved ones with a reason. Question *count* is not itself a signal. Add this framing to the `plan` prompt where it ingests prep output (and to the surfaced text on a paused run), parallel to how the existing critique guidance frames flags. This applies even to `blocking` questions: a human answering a paused run should understand they may legitimately judge a flagged "blocker" to be a non-issue and resume.

3. **Default-ON "may ask" halt.** When prep finishes with ≥1 `blocking` question **and** clarify is enabled (the default), transition the plan to `STATE_AWAITING_HUMAN`, writing the blocking questions into `ClarificationRecord.questions` (reuse the existing type and `state["clarification"]` slot). Add the required `prep → AWAITING_HUMAN` transition to the workflow state machine. Non-blocking questions never trigger this.

4. **Opt-out flag, default enabled.** Add `--no-prep-clarify` (disables the halt). Default = enabled (prep may ask). Persist the setting into `state.config` at `init` so the prep handler reads it. Wire it through `init` and accept it as a per-milestone field for `chain`. Optionally honor a `[defaults]` config key (e.g. `prep_clarify = false`) so a cloud box can opt out once — nice-to-have, not required.

5. **Auto-driver paused outcome surfaces the questions.** The auto-driver already exits cleanly on `AWAITING_HUMAN`; ensure its paused `DriverOutcome.reason` (or log) includes the blocking questions so the operator sees *what* to answer without digging into state.json.

6. **Resume path documented (reuse existing verbs).** The human answers by injecting guidance via the existing `override add-note`, then resumes the plan. Document this loop. Do **not** build a new `clarify --answer` command.

7. **Decision-doc update** (`megaplan/data/decision_skill.md`, the symlinked source behind the `megaplan-decision` skill). Document the default-ON behavior, the `--no-prep-clarify` flag, and explicit guidance: **opt out on cloud / unattended runs** (no human to answer → a blocking question would just strand the run at `AWAITING_HUMAN`). Place it in the Prep optional-phase section and add the modifier to the flag list.

## Scope (OUT) / anti-scope

- **Do not** add a new interactive CLI command for answering questions; reuse `override add-note` + resume.
- **Do not** add cloud auto-detection — the cloud opt-out is *documented guidance* + the flag, not runtime detection.
- **Do not** make the auto-driver block/wait on input; it must keep its non-interactive contract (pause-and-exit only).
- **Do not** rework the plan-phase clarification path beyond reusing `ClarificationRecord`.
- **Do not** redesign the gap/contradiction capture in `prep_metrics.json`; source from it, leave it intact.
- **Do not** change prep's 3-step pipeline shape (triage → fan-out → distill) or its model routing.

## Locked decisions

- Reuse `STATE_AWAITING_HUMAN` and `ClarificationRecord` — no new state or type.
- Halt is **default-ON**; opt-out flag is `--no-prep-clarify`.
- Severity gating: only `blocking` halts; `assume_and_proceed` rides forward as a recorded assumption visible to `plan`.
- Cloud opt-out is documentation + flag, not auto-detection.
- Resume = `override add-note` + resume; no new command.

## Open questions for the planner

- Exact field name/shape for severity classification and the assumption string within `open_questions[]` — pick something consistent with existing prep schema conventions.
- Whether the `[defaults].prep_clarify` config key is worth including now or deferred — planner's call; it's optional.

## Constraints

- The auto-driver must remain strictly non-interactive (pause-and-exit, never block on stdin).
- Backward-compat: existing prep outputs / `prep.json` consumers must not break when `open_questions` is absent or empty (treat as no questions).
- A run with `--no-prep-clarify` must behave exactly like today's halt-free flow, except that blocking questions are now recorded (as assumptions/notes) rather than dropped.

## Done criteria

- Tests:
  - prep yielding a `blocking` question with clarify enabled → plan transitions to `AWAITING_HUMAN`, questions present in `ClarificationRecord`.
  - same with `--no-prep-clarify` → plan proceeds past prep; blocking question recorded (not dropped, not halting).
  - `assume_and_proceed` questions never cause a halt under either setting.
  - `prep.json` schema validates `open_questions[]`; absence/empty is valid.
  - auto-driver paused outcome/log includes the blocking question text.
- `decision_skill.md` updated with flag + cloud opt-out guidance.
- Existing prep/auto test suites still pass.

## Touchpoints (file:line from current tree)

- `megaplan/orchestration/prep_research.py` — `PREP_COMPATIBLE_KEYS` (~32–41), `distill_prep()` (~904–944), `_assemble_prep_outputs` gap/contradiction notes (~469–474), `prep.json` assembly (~1011, the `_artifact_json(plan_dir, "prep.json", …)` write).
- `megaplan/schemas/runtime.py` — the `prep.json` schema is defined inline here (~98–153, under the `"prep.json"` key); add `open_questions[]` there. (There is no `.megaplan/schemas/prep.json` file.)
- `megaplan/prompts/planning.py` — `_prep_distill_prompt` distill prompt (~475–531), and the `plan` prompt's prep-ingestion section (add the "use discretion; not every flag is meaningful" framing here, parallel to the existing critique-flag guidance).
- `megaplan/types.py` — `ClarificationRecord` (~130–133), state constants & `AUTOMATION_TERMINAL_STATES` (~13–37).
- `megaplan/_core/workflow_data.py` — transitions (~76–78); add `prep → AWAITING_HUMAN`.
- `megaplan/auto.py` — paused-outcome handling for `AWAITING_HUMAN` (~1143–1178).
- `megaplan/handlers/override.py` — `_override_add_note()` (~133–168) for the documented resume loop (reference only).
- CLI init + chain milestone parsing — `megaplan/cli.py` (existing prep flags ~L3114/L3710) and `megaplan/chain.py` (`_init_plan` ~L1441); wire `--no-prep-clarify` and per-milestone field; persist into `state.config`.
- `megaplan/data/decision_skill.md` — doc update.
