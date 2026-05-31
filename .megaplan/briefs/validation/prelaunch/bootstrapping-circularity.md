# Pre-launch verification — THE BOOTSTRAPPING CIRCULARITY

**Vantage:** the chain is supposed to run autonomously from one t0 "go" AND is also building the
autonomy / gate / oracle / durable machinery it assumes. This doc resolves the chicken-and-egg:
what must ALREADY EXIST in the pinned t0 driving engine vs what is built-by-the-epic, and flags
every place a milestone's *autonomous execution* depends on machinery only a later milestone builds.

Confirmed prior finding (built upon, not re-derived): `chain/__init__.py` parses
`on_failure`/`on_escalate` via `block.get("abort", default)` (`:339`) — it reads ONLY the `abort:`
sub-key and silently drops the `retry:`/`escalate:` ladder keys. `VALID_FAILURE_ACTIONS =
("stop_chain","skip_milestone","retry_milestone")` (`:89`); `bump_profile`/`bump_robustness` are
unimplemented (grep zero across `megaplan/`); `require_clean_base` is never read (grep zero).

---

## The driving engine at t0 IS the pinned `main` HEAD — not a future organ

M0 Open-Q resolves the pin to "**git-sha of the current `main` HEAD at t0**, installed into a venv …
`--no-git-refresh` ON for the whole epic" (`m0-keepalive-floor.md:108-110, 126-128`). The epic
explicitly forbids ever pulling merged milestone code into the running engine
(`m0:126`, locked decision `m0:90-92`, m5d locked decision `:100-105`). M5d's NEW supervisor lands
**default-OFF behind a flag** while "the OLD `chain/__init__.py` + `bakeoff/` supervisor keeps driving
the epic (frozen, pinned external engine … flag-OFF)" (`m5d:100-105`).

**Consequence (the load-bearing fact):** the code that decides retry/escalate/halt/clarify for
*every milestone of this epic* is **today's `main`** for the epic's entire duration. Nothing a
milestone builds can change the driver's behavior mid-flight — by deliberate, correct design. So the
only autonomy that exists during M1..M7 is the autonomy that exists in `main` **right now**. Anything
the REGISTER promises as a "replacement mechanism" that is *built by a milestone* is, for the purposes
of running this epic, **vaporware** — it ships into the tree but never into the live driver.

This is the master circularity: **the epic's autonomy is bounded by the t0 engine, and the t0 engine
is the unmodified `main` that the epic exists to fix.**

---

## What MUST already exist in the t0 engine (and does) vs what the epic BUILDS

| Capability the autonomous run needs | In t0 `main` engine? | Evidence |
|---|---|---|
| Subprocess phase seam (`[sys.executable,-m,megaplan]`) | YES | `auto.py:266,287` |
| `--no-git-refresh` plumbing | YES | `chain/git_ops.py:28,37-38`; `chain/__init__.py:1242,1386,1915,1922` |
| `merge_policy: auto` self-merge (`gh --auto`) | YES | `chain/__init__.py:1520` `_enable_auto_merge` |
| Bounded blocked-execute recovery | PARTIAL (single recover pass) | `_drive_plan_with_blocked_execute_recovery` `:1176`; per MEMORY `max_blocked_retries` was historically hardcoded 1 |
| **Autonomy ladder** (retry×2 → bump profile → bump robustness → stop) | **NO** | parser drops keys `:339`; `_handle_outcome` `:1202-1234` returns only advance/stop/skip/retry; built by **M5d** `:60-72`, default-OFF, after M6 |
| **`require_clean_base` enforcement** | **NO** | grep zero; `ChainSpec.from_dict` never reads it `:384-401` |
| **Auto-answer clarify / auto-verify** (no `STATE_AWAITING_HUMAN` park) | **NO** | `auto.py:1544-1571` returns `awaiting_human` and "automation stopping"; the auto-answer machinery is a REGISTER promise (§60/§61), unbuilt |
| **Auto-invoke `tiebreaker-run` on pending** | **NO** | `auto.py:1572-1580` returns `tiebreaker_pending`, prints a *human* command; REGISTER §67 promise unbuilt |
| **Behavioral-replay / substrate-swap oracle** (the milestone retirement gate) | **NO** | built by **M0** (W4/W5/W6) — see circularity #2 |
| **t0 auto-arm on M1/W8 lint-green** | **NO** | the W8 lint is built by **M1**; `chain start` is a human command — see circularity #3 |

---

## CIRCULARITIES (each: a milestone's autonomous execution depends on machinery only a later — or
the *same* — milestone builds)

### C1 — The autonomy ladder is built LAST, by M5d, behind a flag, after M6 (CRITICAL)
The ladder the whole launch story rests on ("after one go, no per-milestone human restart",
chain.yaml line 17-22; REGISTER §57/§58/§91/§92) is the **NEW supervisor tier M5d builds**
(`m5d:60-72`: "default escalate ladder = retry → re-route → force-advance → abort"; replaces the
`escalate_action="force-proceed"` literal with general targets). Per chain.yaml ORDER NOTE
"m5d (supervisor) runs AFTER m6", and per m5d locked decision `:94` "Back-edge: M5d depends on M6".
And even once built it lands **default-OFF** while the OLD pinned engine keeps driving (`m5d:100-105`).

So during M1..M6 — every load-bearing milestone, including the apex/extreme/max ones (M2, M3 the
hinge, M6 the atomic swap) — the live policy is the t0 `main` ladder, which is: **one retry, then
`stop_chain`** (`_handle_outcome:1227-1234`, applied at `:1467-1483`; on_failure resolved to
`stop_chain` because the `retry:` key is dropped at `:339`). A single non-`done` outcome on the
hardest milestones halts the chain on a human. The ladder that would prevent that is the thing being
built two nodes later, and never goes live for this run at all.
**This is circular: M1..M6 autonomy depends on M5d's ladder; M5d is the 13th of 14 nodes.**

### C2 — The milestone oracle GATE that authorizes every later retirement is built by M0 itself
M0 W6 ships "a single machine-gate entrypoint … so from M1 on every milestone boundary auto-runs
OLD-alive AND NEW-alive AND replay-MATCH; red auto-halts/auto-reverts or enters the bounded
escalation ladder" (`m0:81-84`, Done #8 `:161-162`). Two problems:
  (a) **The "bounded escalation ladder" W6 routes red into does not exist** (C1) — so a red oracle
      gate falls back to the t0 engine's behavior, i.e. `stop_chain`, not an auto-revert ladder.
  (b) M0 is a *milestone of this chain* (`chain.yaml` first entry, `on_failure`/`on_escalate` apply
      to it too). If M0 itself produces any non-`done` outcome while building the oracle, the t0
      engine halts on a human — and there is by definition no oracle yet to gate M0's own
      retirement. **M0 must run to green under exactly the impoverished autonomy it is trying to
      replace.** This is the tightest loop: the keep-alive floor needs the keep-alive floor.

### C3 — The t0 auto-arm depends on a lint built by M1, but the chain must already be running M1
chain.yaml line 18-22 and REGISTER §1 (L40-46) make the launch authorization "one t0 go, then
`chain start` auto-arms on the M1/W8 chain↔EPIC↔briefs lint going green". But W8 (the lint) is a
**deliverable of M1** (`m1-foundation.md:88-92,144-146`). For the lint to be green, M1 must have
already executed — which requires the chain to already be running. There is no "auto-arm on
lint-green" code path in the engine (`grep` zero); `chain start` is an unconditional human CLI
command. The "arm" is therefore either (a) the human `chain start` at t0 (fine, but then it is the
*single* go and the lint-arm framing is decorative), or (b) genuinely circular if read as "the chain
arms itself once M1's lint passes". Either way the lint cannot gate the start of the run that
produces it. **Low blast radius (it collapses to the one human `chain start`), but the REGISTER's
"auto-arm" claim is not a mechanism that exists.**

### C4 — `require_clean_base` (carried-WIP guard) is config the engine never reads
REGISTER §94 / chain.yaml `driver.require_clean_base: true` is sold as the cure for the
carried-WIP false-positive review halts that MEMORY records twice
(`project_worktree_carry_review_falsepositive`, `..._breaks_pr_isolation`). The t0 engine never reads
the key (`ChainSpec.from_dict:384-401` parses only stall/max_iter/poll/timeouts/on_escalate/robustness/
auto_approve). So a milestone forked off a dirty `main` will carry WIP, and the very review-halt class
the field was meant to kill remains live — and a review halt on the running OLD engine routes to
`on_failure → stop_chain` (human halt). The guard is built nowhere in the epic either (no milestone
claims a clean-base pre-run assertion in driver code; M0 W1 only verifies `--no-git-refresh`/pinned
engine, not clean base). **Circular-ish + dropped: the autonomy depends on a guard that is neither in
t0 nor scheduled to be built into the live driver.**

### C5 — Clarify / verify / tiebreaker human-parks are live in the t0 engine; their auto-replacements are unbuilt
REGISTER §60/§61/§67 promise: clarify auto-answers from brief/prep-fanout → escalate → best-guess;
verify-human becomes an oracle green/red; `STATE_TIEBREAKER_PENDING` auto-invokes `tiebreaker-run`.
None of these exist in the t0 engine: `auto.py:1544-1571` parks on `STATE_AWAITING_HUMAN`
("automation stopping"), `:1572-1580` prints a *human* `tiebreaker-run` command on
`STATE_TIEBREAKER_PENDING`. In `_handle_outcome` these statuses (`awaiting_human`,
`tiebreaker_pending`) are none of `done`/`aborted`/`escalated`, so they hit the `else` failure branch
(`:1224-1227`) → `on_failure` → `stop_chain`. **Any milestone whose plan surfaces a blocking clarify
question, a human-verify criterion, or a gate tiebreaker halts the autonomous chain on a human.**
These auto-replacements are scattered across M5c (control-plane run-outcome vocabulary) and the
verify oracle (M4) — i.e. built mid-to-late epic, behind the new control plane, never wired into the
live OLD driver.

### C6 — "Parallel" milestones (M2.5 ∥ M2; M4's 5 ∥ PRs; m5a ∥ m5b) have no harness support (SECONDARY)
chain.yaml comments and PROGRAM.md (`:124,194-195`) describe M2.5 running ∥ M2 and M4 as "5 parallel
PRs". `run_chain` executes `spec.milestones` strictly sequentially in one `while idx` loop
(`chain/__init__.py:1313,1544`); there is no parallel/concurrent primitive (grep zero). The chain
lists M2.5 as its own sequential node *between* M2 and M3 (correct), so this is harmless for the
chain itself, but any brief text implying intra-run concurrency is aspirational and must not be read
as a harness guarantee.

---

## The honest launch posture (what t0 actually buys)

After one human `chain start` at t0, the epic runs on **today's `main`** with: subprocess isolation,
`--no-git-refresh`, `auto_approve=true` (skips the pre-execute park), `merge_policy: auto` self-merge,
and a **single** blocked-execute recovery pass. Its failure semantics are: **any non-`done` milestone
outcome — fail, stall, cap, escalate, abort, awaiting_human, tiebreaker_pending — resolves to
`stop_chain` (a human halt)**, because (a) the ladder keys are dropped at parse, (b) the ladder organ
is M5d/after-M6/flag-OFF, and (c) the clarify/verify/tiebreaker auto-answers are unbuilt. The "zero
human blockers" guarantee is therefore aspirational config the live driver does not honor — exactly
the exemplar class. The chain will run autonomously **only while every milestone goes green on the
first or second attempt and never surfaces a clarify/verify/tiebreaker**; the first real failure on an
apex/extreme node parks on a person, which for a multi-day apex/extreme/max program is the expected
case, not the edge case.

---

## Resolution map: pre-build-into-t0-engine BEFORE the go vs build-by-epic

**Must be pre-built into the pinned engine BEFORE t0 (none of these can be deferred to a milestone,
because the milestones run *on* this engine):**
1. The autonomy ladder in `_handle_outcome`: parse `retry:`/`escalate:` keys (fix `:339`), implement
   `bump_profile`/`bump_robustness` re-drive with a bounded counter (retry×2 → tier bump → stop).
   This is a small, self-contained patch to `main` — it does NOT need any organ.
2. `require_clean_base` read + a clean-base pre-run assertion (auto-clean or fail-loud) in the
   milestone loop before `_init_plan`.
3. Auto-handling for `awaiting_human` / `tiebreaker_pending` outcomes in `_handle_outcome`: at minimum
   auto-invoke `tiebreaker-run` then resume; for clarify, a brief-sourced best-guess-and-flag path or
   an explicit policy mapping these to the ladder rather than the silent `else→stop_chain`.
4. Confirm `max_blocked_retries` > 1 (MEMORY records it was hardcoded 1) for the epic's drive.

These are days-1 hardening of the *driver* and belong in a **pre-M0 "engine-readiness" patch to
`main`** that the t0 pin then freezes — NOT inside any milestone, because a milestone cannot retroactively
fix the engine that is already driving it.

**Legitimately build-by-epic (no circularity, because they ship into the tree as organs, not into the
live driver, and are exercised by throwaway/canary plans):**
- M0 oracle harnesses (W4/W5/W6) — *provided* their red-path routes to the **pre-built** ladder of
  (1), not the unbuilt M5d ladder; otherwise C2(a) bites.
- M1..M7 organs, M5c control-plane vocabulary, M5d supervisor tier (the *productized* ladder, distinct
  from the driver hardening above) — all correctly behind flags, OLD path keeps driving.

---

## Findings summary (severity)

- **C1 ladder built last/flag-OFF** — blocks-launch. The headline autonomy guarantee is inert for the
  entire M1..M6 run.
- **C2(b) M0 self-bootstrap + C2(a) red routes to nonexistent ladder** — must-fix-in-M0/M1.
- **C4 require_clean_base dropped** — must-fix-in-M0/M1 (it's a known recurring halt class).
- **C5 clarify/verify/tiebreaker parks live, auto-replacements unbuilt** — must-fix-in-M0/M1.
- **C3 t0 auto-arm-on-lint is not a mechanism** — minor (collapses to the one human `chain start`).
- **C6 parallel milestones unsupported** — minor (chain is sequential; briefs' ∥ text is aspirational).
