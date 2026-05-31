# Brief: critique resolution-verifier (v1.1 — "did the fix actually land?")

Builds directly on the v1 `--adaptive-critique` evaluator already present in THIS worktree (`megaplan/handlers/critique.py` front-of-critique/differential path ~L90-133, `megaplan/audits/critique_evaluator.py`). This is a small, tightly-scoped follow-on.

## 1. Outcome
On a revise loop, the next critique must **verify whether each flag's resolution actually landed** — instead of blindly trusting `revise` or blindly re-raising the flag. Concretely: extend the existing front-of-critique evaluator so that, for each flag a prior iteration's `revise` touched, it reads {the original finding, what revise claims it did, the actual plan change} and sets the flag's status to **verified** / **reopen** / **accepted_tradeoff**. Plus fix a data bug that currently destroys the evidence this needs.

## 2. Scope (IN — exactly these 6 items)
1. **Fix the evidence-overwrite bug + add a resolution slot.** `update_flags_after_revise` (`megaplan/flags.py` ~L209) overwrites the flag's original `evidence` with the revise summary. Stop that. Add an additive `resolution` field to the flag record: `{kind: "fixed" | "rejected", claim: str, where: str}` (where = plan section / files the claim points at), written by revise. Original `concern`/`evidence` preserved untouched.
2. **Wire resolution + the plan diff into the next critique's context.** Today the critique/lens prompt surfaces only `{id, concern, severity, status}`. Add: each flag's `resolution`, AND the **plan-version unified text diff** (`plan_v{N-1}.md` → `plan_v{N}.md`) — a real `difflib` unified diff, NOT the scalar `compute_plan_delta_percent`.
3. **The verify step** (inside the front-of-critique evaluator, the v1 hook): for each flag carrying a `resolution`, adjudicate claim-vs-diff using the single most relevant existing lens (not all lenses) → set status: `verified` (claim supported by the diff), `open`/reopen (unsupported/cosmetic), or `accepted_tradeoff` (a sound rejection). Write the outcome + rationale onto the flag.
4. **Rejected-flag handling (no re-litigation).** When `revise` marked a flag `kind:"rejected"`, the verify step's prompt instruction is: "this flag was rejected as invalid — only re-raise if you have NEW evidence the author missed"; if the rejection stands → `accepted_tradeoff`.
5. **Tests** (`tests/test_critique.py`): (a) flag-off / `--adaptive-critique` absent → critique behaves byte-for-byte as today (regression); (b) verify CONFIRMS a real fix → `verified`; (c) verify REOPENS a cosmetic/no-op change → `open`; (d) a `rejected` flag is NOT blindly re-raised; (e) old `faults.json` (no `resolution` field) still loads.
6. **Selection-`why` cleanup.** The evaluator's per-lens selection `why` is written to `evaluator_verdict.json` but never read. Either feed it to the critic (per-lens targeting note) or drop the field. Pick the former if cheap, else drop it.

## 3. Locked decisions (do not relitigate)
- The verifier is a **STEP INSIDE the critique phase** (the existing v1 front-of-critique evaluator) — NOT a new phase, NOT a new store, NOT a new CLI flag.
- **Reuse existing flag statuses** (`open`/`addressed`/`verified`/`disputed`/`accepted_tradeoff`/`gate_disputed`). No new status vocabulary.
- **v1 verify point = the in-loop plan-version diff ONLY.** The review-time / code-diff verification is a deliberate fast-follow, OUT of scope here.
- Fix the evidence bug by **separating original evidence from the resolution** (additive field), not by repurposing `evidence`.
- **Code-mode only** — creative/joke mode bypasses the evaluator (`critique.py:66 not is_creative_mode`); leave that path untouched.
- The `resolution` field is **additive and optional** — old plans without it must still load.
- Keep v1's hard coverage validation + rater≥dispatchee intact.

## 4. Open questions
None — all material decisions are locked above. Do not introduce a user-action gate; if a choice arises, take the option consistent with the locked decisions.

## 5. Constraints
- `--adaptive-critique` OFF must be byte-for-byte identical to today (regression test gates this).
- Do NOT regress existing `faults.json` consumers: `build_gate_signals` (`evaluation.py`), `compute_iteration_pressure` (`iteration.py`), review's `verified_flag_ids` (`review.py`), tiebreaker. The `resolution` field is additive.
- Backward-compatible reading of pre-existing `faults.json`.

## 6. Done criteria
- All 5 tests in #2 pass; the full existing suite stays green.
- `--adaptive-critique` ON + a revise loop: a flag whose fix landed → `verified`; a cosmetic fix → reopened; a sound rejection → `accepted_tradeoff`; a rejected flag is not re-raised without new evidence.
- The evidence-overwrite bug is fixed (original critique evidence survives a revise).

## 7. Touchpoints
`megaplan/flags.py` (`update_flags_after_revise`, the FlagRecord shape) · `megaplan/handlers/critique.py` (front-of-critique evaluator / differential path) · `megaplan/prompts/critique.py` (`_critique_context` / lens context) · `megaplan/audits/critique_evaluator.py` (verdict schema, selection-`why`) · `faults.json` schema · `tests/test_critique.py`.

## 8. Anti-scope (do NOT build)
No directive entity or directive ledger. No separate store. No multi-agent fan-out / subagent investigations. No dispute→tiebreaker edge (let persistent disagreement ride the existing recurrence path). No review/code-diff verify point. No creative/joke-mode support. Do not refactor the lens catalog. Do not widen `run_parallel_critique`'s signature. Do not add a CLI flag (this rides the existing `--adaptive-critique`).
