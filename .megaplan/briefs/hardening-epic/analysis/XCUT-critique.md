# XCUT — CRITIQUE & REVIEW effectiveness across the 12-milestone hardening epic

Cross-cutting read of all 13 per-milestone facts + judgment files against `chain.yaml`.
Scope honesty: most captures are the **orchestration layer** (GPT-5.x driver doing
plan/critique/review/gate); execute was farmed to off-log DeepSeek workers. Critique/review
findings below are from what surfaced in the captured orchestration logs.

## (a) Per-milestone critique/review rounds

| Milestone | adaptive_critique | Critique/review rounds | Converged? | Real bugs caught | Wasted tokens (est.) |
|---|---|---|---|---|---|
| m0-characterization | no | 0 real (fixture stderr only) | n/a | 0 (1 test-caught fix, not critique) | ~0 |
| m1-resolution | no | 1 review pass → approved | yes | 0 (premature-verdict self-correct, no action) | small (premature-verdict tokens) |
| m3a-fail-loud-policy | no | 0 (orchestration capture) | n/a | 0 in capture | 5 zombie sessions re-ate ~50KB batch ×5 |
| m2-store | no | **9 critique iters + tiebreaker** | **NO** | YES — FLAG-M2-001 (missed state writers), FLAG-M2-008 (codebase_id schema) | **~1.09M premium (iters 2–9)** |
| m3b-fail-loud-enforce | yes | execute-only capture (not assessable) | n/a | not in capture | n/a |
| m4-naming | yes | **7–8 plan-review rounds, identical 9 check_ids** | **NO** | YES — gate_carry TypeError caught by own verify (1) | **~450K input (5× byte-identical 64,638-tok rounds)** |
| m5a-store-decomp | yes | 1 review, 3 progressive verdicts, all needs_rework | NO (false reject) | 0 real — **false** reject on worktree-carry noise | ~155K-char review payload (carried-context bloat) |
| m5b-godfiles | yes | 1 critique round | yes | YES — FLAG-001/002/003 (chain monkeypatch, CLI setup, helpers) | minor (93.5% cached) |
| m5c-eval-execute | yes | 1 static critique | yes (single) | YES (prose only — caller updates), but jq-crashed on own output | minor; flag "bought nothing" |
| m5d-pipeline-godfiles | yes | 9-lens critique (13 subagents) | yes | minor — 2 stale cross-refs to OTHER plans' test files | minor (95.9% cached) |
| m6a-surface-config | yes | 1 critique-routing turn (critics never returned) | n/a (abandoned post-decompose) | 0 (milestone dropped) | ~40K evaluator turn, no output landed |
| m6b-deadcode-tests | yes | **0 — pipeline bypassed, hand-merged** | n/a | 0 (config inert; red test carried 10h) | n/a (config was a no-op) |

**Net signal-to-noise:** Only **3 of 13** milestones had a critique/review round that caught a
**real, actionable** defect (m2, m5b, m5c). Two non-converging loops (m2, m4) produced the bulk of
critique value AND nearly all the waste. One review (m5a) actively produced a *false* reject. Three
adaptive-flagged milestones (m5a/m6a/m6b) got zero critique value from the flag.

## (b) HEADLINE [HARNESS] FIX — the convergence-guard gap

**There is no iteration ceiling and no convergence-stop anywhere in the critique/review loop.**
`chain.yaml` exposes `max_iterations: 60` and `max_blocked_retries: 3` — both guard *runtime
failure/blocking*, neither caps *critique rounds*. Result:

- **m2-store: 9 critique iterations** (iter 2→9, sequential 20:16→21:04 UTC), flags accreting
  **monotonically** FLAG-M2-001→017, **never converging** — ~**1.09M premium tokens** re-deriving
  and re-flagging the same plan eight extra times. An adversarial premium critic always finds one
  more nit; nothing stops it.
- **m4-naming: 7–8 plan-review rounds** firing the **identical 9 check_ids** each time, **5 of them
  re-sending byte-identical 64,638-token context** → ~**450K wasted input tokens** re-reviewing an
  unchanged plan. Reviews were observational (all `verdict: N/A`) so no gating verdict ever
  terminated the loop.

**Combined wasted critique tokens across the epic: ~1.5M+** (m2 ~1.09M + m4 ~450K), concentrated in
two milestones with zero convergence machinery.

**The fix (single highest-ROI change):** Add a convergence guard to the critique/review controller
(`megaplan/handlers/critique.py` iteration loop + the review-selection step):
1. **Hard ceiling** on critique rounds (e.g. 3), driver-configurable as `max_critique_iterations`.
2. **No-progress stop:** if round N raises ≥1 new flag while resolving 0 prior flags for 2
   consecutive rounds → force TIEBREAKER / gate-stop instead of another revise→critique cycle.
3. **Plan-hash short-circuit:** hash the plan artifact; skip a re-review when the hash is unchanged
   (kills m4's byte-identical re-sends outright).

## (c) ADAPTIVE-CRITIQUE VERDICT

**The known "silent static-fallback (KeyError critique_evaluator) on EVERY codex milestone" bug did
NOT reproduce as a KeyError anywhere in this epic.** But adaptive critique was **inconsistent**, not
uniformly healthy — the prior bug's *symptom* (static, inline, no `critic_model`) appears on a
subset:

- **Genuinely adaptive (verified):** m4 (mixed `critic_model`: deepseek-v4-pro/flash, sonnet-4-6,
  gpt-5.5; no KeyError/fallback), m5d (`evaluator_model: gpt-5`, lens→model assignment, 0 premium
  critics, `skipped:[]`), m6a (`evaluator_model: gpt-5.5`, 9 lens→model assignments).
- **Degraded to static / inert despite the flag:** **m5b** (critique done **inline as GPT-5, NO
  `critic_model` field** — the textbook fallback signature), **m5c** (single static 9-check critique,
  jq-crashed on its own `critique_output.json:164`, flag "bought nothing"), **m5a** (adaptive
  configured, **no critique model ever invoked at all**).
- **Flag was a pure no-op:** **m6b** bypassed the pipeline entirely (hand-merge), **m6a** abandoned
  after critique-routing (critics never returned), **m3b** execute-only capture.

**Definitive answer:** Adaptive critique *works when it fires* (m4/m5d/m6a prove the routing path is
alive). The failure mode is no longer a hard KeyError — it's **silent inconsistency**: on m5a/m5b/m5c
the flag produced static-inline or absent critique with no error and no marker, so you cannot tell
adaptive-fired from adaptive-fell-back from logs alone. The flag promises coverage it doesn't always
deliver, and emits no fail-loud signal when it degrades.

## (d) TOP 3 CRITIQUE/REVIEW FIXES

1. **[HARNESS] Convergence guard on the critique/review loop** — ceiling + no-net-progress stop +
   plan-hash short-circuit (detail in (b)). Eliminates the ~1.5M-token m2/m4 waste and the epic's #1
   inefficiency. *Single highest-ROI change.*

2. **[HARNESS] Make adaptive-critique fail loud + capture a pre-run baseline.** (i) When
   `adaptive_critique: true`, assert the critique record carries a `critic_model`/`evaluator_model`
   marker and **WARN-and-fail** if it falls back to static-inline (kills the silent m5a/m5b/m5c
   inconsistency); normalize `critique_output.json` so `jq` indexing survives (m5c crash). (ii)
   Snapshot a `pytest` failure baseline at worktree creation and feed it to the review gate so review
   can subtract inherited failures — this is what false-rejected m5a's correct work.

3. **[DRIVING] Split orchestration tier from gate rigor; cap lenses by task class.** Every milestone
   ran 100% premium GPT-5.x as the *driver* even for mechanical refactors (m0/m3a/m4/m5a/m5b/m5d/m6b
   all flagged tier-mismatch). Route critique re-verification rounds (iter ≥2) and review/gate turns
   on behavior-preserving milestones to a cheaper tier, and scale assigned lenses to blast radius
   (cap ~4–5 for `directed`/`light` housekeeping — m6a fired 9/9 on trivial edits). Keep premium for
   round-1 plan critique on genuinely design-bearing milestones (m2-class).
