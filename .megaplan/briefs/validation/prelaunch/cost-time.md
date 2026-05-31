# Pre-launch: COST / TIME / BLAST-RADIUS of the t0 "go"

**Vantage:** what does pressing "go" at t0 actually commit, in dollars and wall-clock?
This is for eyes-open commitment, not a gate. Date: 2026-05-29.

## TL;DR

Pressing "go" arms a **14-milestone sequential autonomous chain** whose realistic single-pass
spend is **~$500–$1,200 (midpoint ~$850)** over **~3–7 days of continuous wall-clock**. Three
apex+extreme+max milestones (M3 hinge, M5c control-plane, M6 swap) are **~$260–$580 combined —
roughly half the total** — and are exactly the milestones most likely to fail-and-retry.

The single biggest commitment surprise is **not** the headline number, it is the failure shape:
the chain.yaml advertises a bounded auto-retry ladder (retry ×2 → bump profile/robustness → halt),
but **the harness does not honor it** (confirmed below). So the *real* worst case is not a 3×
cost blow-out — it is the chain **silently halting on the first milestone failure** and parking
on a human, with all upstream spend already sunk. The cost ceiling is bounded by the halt; the
*time* ceiling is unbounded (it waits for a person).

---

## How the numbers were derived

### Tier → model (from `megaplan/profiles/apex.toml`, `premium.toml`)

- **apex** (tier 5, vendor-locked): Claude (Opus-class) on plan/prep/revise/gate/finalize/loop_plan
  + critique-evaluator; **Codex (GPT-5.5)** on critique/execute/review/loop_execute/tiebreakers.
  Execute tier_models: 1–2 = DeepSeek-v4-pro (Fireworks), 3 = Sonnet-4-6, 4 = Opus-4-7, **5 = Codex**.
- **premium** (tier 4): single-vendor Claude `:low` on every phase. Execute tier 5 = Opus-4-7.

### Per-1M-token rates (from `megaplan/pricing/{claude,codex,fireworks}.py`)

- Opus-4: `$15 in / $75 out` (`claude.py:39`). Sonnet-4: `$3 / $15`.
- GPT-5.5 (codex default): `$5 in / $30 out` (`codex.py:35`).
- DeepSeek-v4-pro: `$1.74 in / $3.48 out` (`fireworks.py:24`).

So apex milestones are the expensive ones: Opus authoring + Codex critique/execute, both at the
top of the rate table, run through the full thorough/extreme workflow.

### Robustness multiplier (from `megaplan/types.py:781-783`, `_core/workflow_data.py:91-122`)

- `ROBUSTNESS_LEVELS = (bare, light, full, thorough, extreme)` (`types.py:410`).
- thorough/extreme use `max_robust_critique_iterations = 6` (vs 4 for full/light) — **up to 6
  plan-critique rounds** plus the extra provocations/audits gated on `{thorough,extreme}`
  (`forms/provocations.py:22`, `audits/robustness.py:234`). extreme/thorough run the workflow with
  **no shortcut transitions** (`_ROBUSTNESS_OVERRIDES["extreme"]={}`, `["thorough"]={}`), i.e. every
  phase fires. extreme+max = the most compute-heavy shape megaplan can produce.

### Calibration anchors (real `state.json` `meta.total_cost_usd` on disk)

| Run | profile / robustness | $ | note |
|---|---|---|---|
| `m1-core-resolution-contract-20260520` | partnered / full | **$7.07** | THIS epic's earlier M1 attempt — but contract-only, small |
| `pipeline-week1-cleanup` | all-codex / full / high | **$47.44** | heavy architecture sprint |
| `implement-shannon` | thoughtful / std | **$45.41** | feature sprint |
| `prep-fanout-3step` | partnered / full | **$69.96** | |
| `cloud-runtime-correctness` | thoughtful / std | **$96.92** | big multi-file sprint |
| `add-the-full-resident-discord` | all-codex / std | **$157.65** | large feature |
| `resident-discord-cloud-orchestrator` | all-codex / std | **$419.98** | multi-week-scale feature |

The epic's apex+extreme+max milestones (M3/M5c/M6) are each *larger and deeper* than
`pipeline-week1-cleanup` ($47) and at a strictly higher tier/robustness than every $45–$97
anchor above — M3 alone is "~2,500-LOC auto.py port + authority flip" per PROGRAM.md, which is
resident-orchestrator-class work. That is why I band them at **$80–$200 each**.

---

## Per-milestone single-pass cost bands

| Milestone | profile | rob | depth | $ band |
|---|---|---|---|---|
| m0-keepalive-floor | premium | thorough | high | $12–30 |
| m1-foundation | apex | thorough | high | $35–80 |
| m2-types-and-port | apex | thorough | high | $35–80 |
| m2.5-autopy-spike | premium | thorough | high | $12–30 |
| **m3-hinge** | **apex** | **extreme** | **max** | **$90–200** |
| m4-services-spine | apex | thorough | high | $40–90 |
| m5a-node-library | premium | thorough | high | $15–40 |
| m5b-execute-realm | premium | thorough | high | $15–40 |
| m5-eval | apex | thorough | high | $35–80 |
| m5-cal | premium | thorough | high | $15–40 |
| **m5c-control-plane** | **apex** | **extreme** | **max** | **$80–180** |
| **m6-strangler-swap** | **apex** | **extreme** | **max** | **$90–200** |
| m5d-supervisor-tier | premium | thorough | high | $20–50 |
| m7-sinks | premium | thorough | high | $15–40 |

**Single-pass total: ~$509 – $1,180 (midpoint ~$844).**

These are deliberately wide; megaplan run cost has ~3× variance even at fixed config (compare the
$45 vs $97 anchors). Treat the midpoint as the planning number and ~$1.2k as the realistic ceiling
*if every milestone succeeds first try*.

## Wall-clock

`megaplan chain` runs milestones **strictly sequentially** (`chain/__init__.py:1597`
`for index, milestone in enumerate(spec.milestones)`). The PROGRAM.md "parallel tracks"
(M1∥M2, M5a∥M5b∥M5-eval, M6∥M5d) **cannot be exploited by the harness** — they are a planning-time
fiction. So wall-clock is the *sum* of all 14, not the critical path.

- Per-phase worker cap is 2h (`worker_timeout_seconds=7200`, `types.py:772`); a thorough/apex
  milestone runs plan→critique×(≤6)→revise→gate→execute→review×(≤3)→finalize.
- Banded: **~64–167 h continuous = ~2.7–7.0 days** of uninterrupted machine time, assuming zero
  human waits and zero retries. M3 and M6 alone are ~10–28 h each.

---

## Findings

### 1. The advertised auto-retry/bump ladder is NOT honored — failure = silent human halt (confirms the exemplar)
`chain.yaml:104-114` declares `on_failure: {retry: retry_milestone, escalate: bump_profile,
abort: stop_chain}` and `on_escalate: {escalate: bump_robustness, abort: stop_chain}`. The parser
reads **only** `block.get("abort", default)` (`chain/__init__.py:339`); `VALID_FAILURE_ACTIONS =
("stop_chain","skip_milestone","retry_milestone")` (`:89`) — `bump_profile`/`bump_robustness`
**do not exist** (grep: zero implementations) and the `retry:`/`escalate:` ladder sub-keys are
dropped. At runtime `on_failure` resolves to `stop_chain` (`:347`), and `_classify` returns `"stop"`
(`:1228`). **Cost/time consequence:** the "zero-human-blocker, spend-more-compute-never-fetch-a-
person" guarantee is fiction. The actual t0 commitment is: *run until the first milestone fails,
then halt and wait for a human* — with all prior milestone spend sunk.

### 2. The retry-ladder, IF ever built, multiplies cost on exactly the most expensive milestones
The ladder text ("retry ×2 fresh → bump profile one tier → re-run once") is up to **3 extra full
milestone runs** before halt. Applied to M3 (apex+extreme+max, $90–200/pass) that is a **+$270 to
+$600 blow-out on M3 alone**, and "bump profile" on an already-apex milestone is undefined (no tier
above apex). So the ladder is doubly broken: unimplemented today, and if implemented as written it
would burn the budget hardest on the hinge milestones that are most likely to need it.

### 3. Half the budget rides on three apex+extreme+max milestones — and they are the riskiest to repeat
M3/M5c/M6 = **$260–$580 combined (~half the total)**. M3 is the R1 authority flip (PROGRAM.md
risk #1: "single point of maximum danger"); M6 is the irreversible atomic strangler swap
(risk #5). A red-then-rerun on either — once any retry path exists, or done by hand after a halt —
re-spends a $90–200 milestone. These are the cost-volatile nodes; the cheap premium milestones
(M0, M2.5, M5a/b/cal, M7 at $12–50) are budget noise by comparison.

### 4. Bootstrapping circularity inflates the realistic cost above the single-pass band
The milestones BUILD the autonomy/oracle/governor machinery the chain ASSUMES is already running
(M0 builds the dual-run rig and oracle skeleton; M3 builds the Governor/Capacity-Lease that is
supposed to bound fork-bomb spend; M5-cal builds the routing the chain pretends to have). For the
duration of the run there is **no Governor enforcing a tree/spend budget** — the very fork-bomb-
against-the-wallet that UU#8 names is unmitigated until M3 lands, and the spend ceiling is whatever
the chain happens to do, not a bounded lease. Combined with the ~3× per-run cost variance, plan for
the **upper band (~$1.2k) plus a contingency for at least one hand-driven re-run of an apex/extreme
milestone after a halt (+$80–200)** rather than the midpoint.

### 5. Wall-clock is the sum of 14 serial milestones, not the critical path the PROGRAM advertises
`chain/__init__.py:1597` runs milestones in list order; there is no parallel dispatch
(no asyncio/threadpool over milestones). The PROGRAM.md parallel tracks save nothing in practice.
Eyes-open: this is a **multi-day continuous machine commitment (~3–7 days)** that, per finding #1,
will in reality be punctuated by human-halts of unbounded duration — so calendar time is
effectively open-ended, not 3–7 days.

---

## Verdict

Pressing "go" commits **~$500–$1.2k and ~3–7 days of continuous machine time (realistically more
calendar time)**, with **~half the spend concentrated in three apex+extreme+max milestones
(M3/M5c/M6)** — and the advertised "no-human, auto-retry-and-bump" autonomy that justifies the
single-go commitment **is not implemented** (`chain/__init__.py:339`), so the run will silently
halt on the first milestone failure with upstream spend sunk. Eyes-open: budget the upper band plus
a re-run contingency, and know that the "fire-and-forget" framing is false — this needs a babysitter.
