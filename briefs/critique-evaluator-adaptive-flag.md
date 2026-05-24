# Brief: A critique evaluator — let a strong agent decide the critique (separate `--adaptive-critique` flag)

**Status:** design, pre-implementation (revised after pre-mortem)
**Related:** [[project_complexity_adjudication]] (finalize tier 1–5), [[project_gate_tiebreaker_downgrade]] (gate silent downgrade), [[project_fanout_primitive]] (`briefs/multi-agent-fanout-primitive.md`), [[project_planning_pipeline_unification]]

---

## 0. Pre-mortem outcome (3-agent DeepSeek panel, 2026-05-24)

An earlier draft of this brief encoded the feature as a new `variable` **robustness level**. A 3-lens adversarial pre-mortem (complexity / bugs / confusion) **converged on one root cause**: `robustness` is an overloaded scalar that flows through a single normalizer (`normalize_robustness`, `types.py:360`, which falls back to `"full"` for unknown strings) and dozens of `robustness in {…}` membership checks (`review.py:491,493`, `finalize.py:609`, `execute.py:187`, …). Bolting a *mode* onto that scalar produced a dead-path, ~7 silently-mis-routing branches, and no single source of truth. All three lenses traced their worst finding to that one encoding mistake.

**Decisions taken from the pre-mortem:**
- **Encode the evaluator as a separate, orthogonal `--adaptive-critique` flag — never a `robustness` value.** This deletes the entire convergent bug class *by construction*: the decision never touches `robustness` or `normalize_robustness`. This is the central change in this revision.
- **Single source of truth for the lens set.** The evaluator's verdict must thread through `active_checks` / `expected_ids` / the recovery and parallel→sequential fallback paths, or it gets silently discarded (bug class #2).
- **Keep "agent decides with full context" — fix the *inputs*, not the freedom.** Replace vague instructions with: a concrete **ranked** model list (not "rough strength/cost") and **fire-by-default / justify-to-skip** (a skip without a reason is a hard reject — makes "conservative" machine-auditable without collapsing to a tier funnel).
- **Per-lens model assignment is a clean v2.** Lowest-validated, highest-plumbing (`run_parallel_critique` widening); land selection-only first.

**Explicitly discounted from the panel** (recorded so we don't over-correct): invented usage percentages ("sub-5% of runs"); the prediction that the LLM "will fire all 9 or invent a proxy" (a guess, and the owner has high confidence in pick accuracy — see below); and both agents' reflexive "fix" of retreating to a ranked 1–5 → `tier_map` scalar funnel (that's their determinism bias and was a deliberately-rejected shape).

**Phase 0 (offline pick-accuracy validation) is dropped.** The owner has high confidence a strong model picks the right lenses from a plan; the value hypothesis is accepted. The pre-mortem's surviving findings (scalar overload, wiring) are orthogonal to pick quality and are addressed by the architecture below.

---

## 1. The problem

`robustness` today is a single scalar that picks a **fixed** lens bundle, statically, before the plan exists:

| level | critique behavior (`checks_for_robustness`, `audits/robustness.py:225`) |
|---|---|
| `bare` | critique **skipped entirely** — plan → finalize (`critique.py:58`) |
| `light` | critique runs with **zero structured lenses** — one holistic pass |
| `full` | the **6 core** lenses |
| `thorough`/`extreme` | all **9** lenses |

The 9 code-mode lenses (`CRITIQUE_CHECKS`) carry `category` (completeness / correctness / maintainability) and `tier` (core / extended). Two structural problems:

1. **One scalar conflates three orthogonal axes** — *breadth* (how many lenses), *lens mix* (which categories), and *strength* (one model for all critics, `critique.py:66`). You cannot say "narrow but deep": fire only the correctness lens, on a strong critic, and skip the rest.
2. **The choice is a forecast, made before the plan exists.** A user picks `robustness` up front; the actual critique a plan needs is a function of *what the plan proposed* — which doesn't exist at that point.

---

## 2. The reasoning that fixes the shape (why this design, not the obvious ones)

Endpoint of a deliberate sequence of corrections — recorded so we don't relitigate:

- **Measure, not forecast.** Put the decision *after* the plan, so the decider reads the real artifact. (Killed: "prep forecasts critique difficulty.")
- **Decide "what kind," not just "how much."** A strong critic on the wrong lens is worse than a medium critic on the right one. The decision is genuinely 2-D: breadth × per-lens depth.
- **Don't funnel through a scalar.** An earlier draft had the agent emit a 1–5 tier that mechanically expanded into lenses + model. Rejected: it throws away the context we just paid to give it. A strong agent holding the plan should make the real decision directly.
- **Orthogonal to robustness, not folded into it.** (Pre-mortem.) `robustness` governs workflow *topology* (which phases run; review behavior). The evaluator governs the lens/critic sub-decision *within* critique. They are genuinely different axes — which is exactly why overloading one scalar to carry both was the bug.

---

## 3. Target design — all-in

### 3.1 Trigger — a separate flag, orthogonal to `robustness`
- New opt-in: **`--adaptive-critique`** (config `execution.adaptive_critique: bool`, default `false`). Off → today's static `checks_for_robustness` path, byte-for-byte unchanged.
- **`robustness` is untouched.** It keeps governing workflow topology and serves as the evaluator's **fallback lens set** on evaluator error/absence (fall back to the static set for the configured level; never to `()` unless the level itself is `light`/`bare`).
- The evaluator decision lives in its **own artifact** (`evaluator_verdict.json`) and a resolved lens-set the critique handler consumes. **It never mutates `robustness` and never flows through `normalize_robustness`** → none of the membership-branch bugs can occur.
- Interaction with `bare`: `bare` skips critique entirely, so `--adaptive-critique` is a no-op under `bare` (nothing to evaluate). Document this; don't special-case it.

### 3.2 Where it lives
The **front half of `critique`**, not a new top-level phase. Critique step 1 = evaluator decides; step 2 = run the selected critics. Keeps fresh-eyes independence (it is not the plan's author — authors under-report their own blind spots) without a new pipeline phase, state, or seam.

### 3.3 What it is
A **strong, tool-using agent**. It reads and reasons, it does not receive a pre-chewed block and emit a number:

**Context it gets (or fetches):**
- the finished plan + task graph
- the original goal, issue hints, user notes (intent + stakes the plan text doesn't carry)
- the lens catalog — the 9, with their `question`/`guidance`
- a **concrete ranked model list** (explicit strength ordering + cost, not "rough") so "which critic" is a real choice
- repo access (file tools) to grep what the plan actually touches — concurrency? shared interface? auth path?

**What it emits — a reasoned critique plan, structured:**
```
critique_plan:
  selections: [ { check_id, critic_model, why }, … ]   # fired lenses
  skipped:    [ { check_id, why }, … ]                  # deliberately not fired — why REQUIRED
```
Free-form in *reasoning*, hard-schema in *output*.

### 3.4 How it executes — reuse the fan-out that already exists
`critique.py:72` already calls `run_parallel_critique(..., checks=active_checks)` — each lens is already a separate critic. Today the model is resolved **once** and shared. **Single-source-of-truth requirement:** the evaluator's resolved lens set must become `active_checks` *and* drive `expected_ids` (`critique.py:65`), `_recover_valid_critique_output` (line 99), and the parallel→sequential fallback (line 78) — all from one place — or the verdict gets silently discarded.

### 3.5 The range it can choose
Reproduces any existing level as a special case, plus the new in-between:
- 0 lenses (holistic pass) = `light` ← **floor**
- core 6 = `full`; all 9 = `thorough`
- any custom subset + (v2) heterogeneous per-lens models = the new expressiveness

**Floor is `light`, not `bare`.** The evaluator may dial down to a holistic pass but may **never** skip critique entirely.

### 3.6 Invariants (safety lives here, not in a funnel)
- **Bounded to the catalog** — selects/assigns from the 9; cannot invent lenses → output validatable, hard-reject on unknown ids.
- **Mode-aware** — code plan → code catalog; joke/creative → their own sets (or restrict v1 to code mode; see §8).
- **Fire-by-default / justify-to-skip** — every *skip* needs a reason or the step bounces. Makes "conservative" machine-auditable. (Finalize's hard-reject discipline, `finalize.py:264-274` — explicitly *not* gate's KeyError-and-silent-downgrade.)
- **rater ≥ dispatchee** — the evaluator (strong) must not assign a critic weaker than a lens warrants. Give it a *ranked* list so this is checkable. (Finalize currently violates the analogous guarantee — §5.)

---

## 4. What exists to build on (reuse, don't rebuild)
- **Lens catalog + metadata** — `CRITIQUE_CHECKS` (9), `category`/`tier`, `audits/robustness.py:22`.
- **Per-lens fan-out** — `run_parallel_critique` already runs lenses as separate critics.
- **Static selection** — `checks_for_robustness` / `select_active_checks` stay as the flag-off path and the evaluator's fallback target.
- **Hard-reject template** — finalize's required-field-or-bounce validation is the contract shape to copy.
- **Model resolution** — `resolve_agent_mode` / `tier_map` for turning a chosen model into a concrete agent.

## 5. What's net-new
- **`execution.adaptive_critique` flag + `--adaptive-critique` CLI** (a boolean; *not* a robustness value, *not* in `ROBUSTNESS_LEVELS`, *not* seen by `normalize_robustness`).
- The evaluator agent: prompt, context assembly (incl. file tools + ranked model list), output schema, catalog-bound validation.
- **Single-source-of-truth refactor** of `active_checks` → `expected_ids` / recovery / sequential-fallback in `critique.py`.
- `evaluator_verdict.json` artifact, written **before** the fan-out (crash-safety + data-parity: [[feedback_data_parity]]).
- Fold in **rater ≥ dispatchee** as an invariant (and fix it in finalize while here — `variable`/`directed`/`apex` currently rate with a weaker model than they dispatch).
- **(v2 only)** widen `run_parallel_critique` `model: str` → `model_map: dict[str, str]`.

---

## 6. Phasing & sizing
- **v1** — `--adaptive-critique` on → evaluator selects the lens subset (range `light`→`thorough`) + picks **one** critic model, reasoned from full context. Output feeds the single-source `active_checks` + `model`. No `robustness` changes, no normalizer surgery, no per-lens map. ~a sprint.
- **v2** — **per-lens** model map (`{check_id: model}`); widen `run_parallel_critique`. Trustworthy given high confidence in picks; deferred only because it's the riskiest plumbing — sequencing, not skepticism.
- **Post-launch telemetry** (cheap, do from v1): log the evaluator's chosen lenses against which lenses actually fired a finding. Confirms calibration in production and informs whether v2's per-lens spend pays off.

---

## 7. Relationship to the evaluator-unification question

Third concrete instance of a recurring pattern: gate, finalize-tier, critique-evaluator all *read inputs + rubric → emit verdict + justification → validate → steer downstream*. A 3-DeepSeek investigation (2026-05-23) found: only **two** genuine LLM evaluators exist today; the two **diverge at the verdict shape** (gate routes a state machine with side effects; finalize emits a per-task scalar). **Verdict: build the third concretely; do not extract a base class now.** The shareable part is only the *front-half discipline* (read → justify → hard-validate → log → rater≥dispatchee) — a thin shared validator + convention, not a class hierarchy owning `apply_verdict`. Build this critique-evaluator for **its own** quality (rich critique-plan verdict), not to rhyme with finalize.

---

## 8. Locked decisions (v1 scope)

These were open in earlier drafts; locking them so they don't resurface as critique flags.

1. **v1 is code-mode only.** The evaluator selects from the code-mode `CRITIQUE_CHECKS` catalog. Joke/creative modes (`select_active_checks` creative branch) keep their existing static behavior and **ignore `--adaptive-critique`** entirely. Wiring the creative catalog into the evaluator is explicitly out of scope. *Anti-scope: do not touch the creative/joke selection path.*
2. **Model picks use a concrete, ranked roster.** The evaluator is given an explicit strength-ranked model list (with cost), not "rough" descriptors and not an abstract tier it can't resolve. It assigns a concrete model per fired lens (v2) / one concrete model for the run (v1) from that ranked list.
3. **The `LENS_CATALOG` registry refactor is deferred to v2.** v1 reads the existing `CRITIQUE_CHECKS` / `_CORE_CRITIQUE_CHECKS` as-is. *Anti-scope: do not refactor the lens catalog into a unified registry in v1* — it's a maintainer nicety, not a v1 requirement (tracked as a v2 follow-up).
4. **v1 is selection-only, one critic model.** No per-lens model map; `run_parallel_critique`'s signature is **not** widened in v1. *Anti-scope: do not modify `run_parallel_critique`'s `model` parameter.*

## 9. Risks (accepted)
- **Calibration is the residual risk, not pick-accuracy.** The owner is confident in picks; the surviving exposure is the confident-but-wrong *skip* on a subtle plan, where the downstream-critic escalation net is weakest. Mitigation: fire-by-default/justify-to-skip + §6 telemetry. (Phase-0 validation deliberately skipped.)
- **Front-loading cost.** Every `--adaptive-critique` run pays for the evaluator pass even on trivial plans. Accepted; bounded by opt-in.
- **Reproducibility.** Adaptive runs are non-deterministic; flag-off runs stay deterministic for bakeoffs/debugging. Log the verdict (`evaluator_verdict.json`); pinning deferred.
- **Maintainer hazard (deferred mitigation):** the `tier` field is the only bridge between the static path and the evaluator catalog; a typo silently drops a lens. The v2 `LENS_CATALOG` registry (with `_CORE_CRITIQUE_CHECKS` as a derived view) is the fix; until then, a test asserting every `CRITIQUE_CHECKS` entry has a valid `tier` is the v1 guard.

## 10. Done criteria (v1)
- `--adaptive-critique` (config `execution.adaptive_critique`, default off) added; **off → critique behaves byte-for-byte as today** (regression test).
- On → the evaluator runs in the front half of critique, emits a schema-valid `evaluator_verdict.json` (selections + skips, every skip justified, all ids ∈ catalog) **before** the fan-out.
- The resolved lens set drives `active_checks`, `expected_ids`, `_recover_valid_critique_output`, and the parallel→sequential fallback from **one** source — a test proves the verdict survives the sequential fallback path.
- `robustness` / `normalize_robustness` are **untouched** (grep-level assertion: `"variable"`/`"adaptive"` never added to `ROBUSTNESS_LEVELS`).
- rater ≥ dispatchee holds for the evaluator's assignment; the finalize violation is fixed for `variable`/`directed`/`apex`.
