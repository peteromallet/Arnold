# A2 — Critique-Loop CAP / TERMINATION Policy

**Problem (confirmed):** the plan-critique loop (critique → gate → ITERATE → revise → critique)
has no round ceiling. `_apply_gate_outcome` (`megaplan/handlers/gate.py:360-361`) returns
`("revise", ...)` unconditionally on ITERATE. No `max_critique_*` key exists in `DEFAULTS`
(`megaplan/types.py:672-690`). The harness already *computes* plateau warnings
(`gate_signals.py:208-213`, iter≥5/≥12) and a force-proceed HINT (`gate_checks.py:125-129`)
but never *enforces* them. The execute-review loop, by contrast, IS capped
(`review.py:238-254`: counts `prior_rework_count` from history, then appends a note and
force-proceeds). **This policy mirrors that exact mechanism for critique.**

## 1. How many rounds

Scale the cap with robustness, mirroring the review cap's `max_review_rework_cycles` /
`max_robust_review_rework_cycles` split. The cap counts **ITERATE rounds** (a round = one
critique→gate→revise cycle), keyed off `state["iteration"]`.

| robustness | `max_critique_iterations` | rationale |
|---|---|---|
| bare    | 0 (loop disabled — workflow has no revise edge) | already terminal in `_ROBUSTNESS_OVERRIDES` (`workflow_data.py:108`) |
| light   | 2 | light revises straight to GATED (`workflow_data.py:103-105`); 2 keeps it cheap |
| full    | 4 | empirically most plans converge by 3; 4 leaves one buffer round. **Default.** |
| thorough| 6 | fills the empty thorough override (`workflow_data.py:93`) — its only round policy |
| extreme | 8 | matches the existing hard-stop intuition (`gate_signals.py:210`, iter≥12 ≈ pathological) |

Plan size does **not** scale the cap directly — a bigger plan yields more *flags per round*,
not more rounds-to-converge; rounds measure loop progress, not surface area. The one
size-sensitive knob is the no-progress threshold (§4), which already normalizes by flag delta.

## 2. Telling the agent it's the near-last round

Inject round context into the **revise** prompt (built where the gate handler dispatches
`next_step="revise"`; thread `iteration` + `max_critique_iterations` through to the reviser
prompt builder alongside the existing critique payload). Three tiers:

- **Normal round** (`iter < max-1`): `"Revision round {iter} of up to {max}. Address all
  blocking flags; you have headroom for nice-to-haves."`
- **Penultimate round** (`iter == max-1`): `"Revision round {iter} of {max} — this is your
  SECOND-TO-LAST round. After the next critique the gate FORCE-PROCEEDS. Prioritize
  correctness/security flags now; defer cosmetic ones."`
- **Final round** (`iter == max`): `"FINAL revision round ({iter}/{max}). The gate will
  force-proceed after this regardless of remaining cosmetic flags. ONLY change the plan to
  resolve correctness-critical or security flags (severity significant / likely-significant).
  Do NOT introduce new scope or churn on style — that risks a no-net-progress stall."`

Symmetrically, tell the **critic** on the final round to down-rank stylistic flags so it does
not manufacture fresh cosmetic blockers the loop can't act on. This converts the existing
advisory plateau HINT (`gate_checks.py:125-129`) into an actionable instruction.

## 3. What happens at the cap

Hook in `_apply_gate_outcome` (`gate.py:360`), replacing the unconditional ITERATE return:

```python
if gate_summary["recommendation"] == "ITERATE":
    prior = sum(1 for e in state.get("history", [])
                if e.get("step") == "gate" and e.get("result") == "iterate")
    max_iter = get_effective("execution", _critique_cap_key(robustness))
    if prior >= max_iter:
        open_critical = [f for f in blocking_open_flags
                         if f.get("severity") in ("significant", "likely-significant")]
        if open_critical:
            summary = (f"Max critique iterations ({max_iter}) reached with "
                       f"{len(open_critical)} unresolved correctness-critical flag(s). Escalating.")
            return "critique_cap_escalate", "override add-note", summary, []  # ESCALATE path
        summary = (f"Max critique iterations ({max_iter}) reached. "
                   "Force-proceeding to finalize despite open cosmetic flags.")
        state["current_state"] = STATE_GATED
        return "blocked", "finalize", summary, []  # mirror review.py force-proceed note
    return result, "revise", summary, []
```

- **Cosmetic-only open flags at cap → force-proceed-with-note** to finalize (exactly the
  review-loop behavior at `review.py:248-252`). The note lands in the gate summary/history so
  the deferred flags are auditable.
- **Correctness-critical open flag at cap → escalate** via the existing ESCALATE→`override
  add-note` route (`gate.py:362-363`), which under `strict_notes` already stops for the user
  (`gate_checks.py:118-122`). Never silently ship a plan with an unresolved significant flag.

This routes through `STATE_CRITIQUED`'s existing transitions (`workflow_data.py:60-65`) — no
new states needed.

## 4. No-net-progress early stop (before the hard cap)

Detect a stalled loop two rounds early. Per round, gate_signals already has `resolved_flags`
and the open/blocking flag list (`gate_signals.py:186`, `gate_checks.py:101`). Define, over a
trailing window of 2 rounds:

- `resolved_delta` = blocking flags resolved this round
- `new_blocking` = blocking flags first appearing this round
- **stall** when, for 2 consecutive rounds: `resolved_delta == 0` AND `new_blocking >= 1`
  (the loop is treading water — churning new flags without closing old ones), OR the weighted
  score is non-improving (`gate_checks.py:104`, `plateaued`) for 2 rounds with
  `recurring_critiques` non-empty.

On stall, take the **same branch as the hard cap** (§3): escalate if a correctness-critical
flag is open, else force-proceed-with-note. This generalizes the existing
`max_execute_no_progress` (default 3, `types.py:679`) to the critique side.

## 5. Configurable vs hard-coded

Add to `DEFAULTS` (`types.py:672`) and register in `_SETTABLE_NUMERIC` (`types.py:717-724`):

```python
"execution.max_critique_iterations": 4,            # full default
"execution.max_robust_critique_iterations": 6,     # thorough/extreme
"execution.max_critique_no_progress": 2,           # §4 window
```

Robustness-scoped selection mirrors `review.py:238-242`:

```python
def _critique_cap_key(robustness):
    return ("max_robust_critique_iterations"
            if robustness in {"thorough", "extreme"} else "max_critique_iterations")
```

light overrides to 2 via the workflow/profile layer (where light already narrows transitions,
`workflow_data.py:99-107`); bare is structurally 0 (no revise edge). **Hard-coded:** the
prompt-signaling text (§2), the severity vocabulary (`significant`/`likely-significant`), and
the stall *shape* (the metric formula) — only its window length is a key.

## 6. Interaction with severity

Severity is the *switch* at every termination point (cap §3 and stall §4):

- open flags filtered to `severity in ("significant","likely-significant")` —
  the exact predicate already used at `gate.py:328` — are **blocking**: their presence at the
  cap forces **escalate**, not force-proceed.
- everything else is **cosmetic**: deferred with an auditable note, loop terminates to finalize.

This makes the cap safe: it can never bury an unresolved correctness/security concern, but it
also can't be held hostage forever by stylistic nits the loop keeps re-flagging.
