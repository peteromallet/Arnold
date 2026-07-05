# Oracle Decision: Unified Agent Surface Plan

Decision date: 2026-07-04  
Input packet: `ORACLE_REVIEW_PACKET.md`  
Plan updated: `PI_ABSOLUTE_REPLACEMENT_PLAN.md`
Codex deviation review: `CODEX_DEVIATION_REVIEW.md`

## Overall Verdict

**Split into smaller migrations with a mandated sequence.**

Do not execute the original monolithic plan as written. It bundles five
separable migrations into one cutover:

- observability/data contracts
- fanout runtime
- Shannon retirement
- Codex governance
- security policy

The direction is sound and should not be rejected. Fragmented launch paths,
incompatible artifacts, missing unified kill/history/cost control, and a bespoke
Claude worker layer are real problems. The existing adapter/dispatcher seam is
also a real starting point.

The required structural change is:

> Ship the facade first as a thin recording/control wrapper around existing
> launchers. Replace runtimes later, path by path, with evidence-backed deletion
> gates.

The facade must collect the baselines, telemetry, adoption data, and contract
evidence the rest of the plan depends on.

## Confidence

Confidence in **split**: moderate, about 65%.

Confidence that **execute as written** is wrong: high, about 90%.

Evidence that could change the verdict:

- Toward execute as written: measured `fan.py` baselines plus a working pooled
  Pi/facade fanout spike showing N=50 parity, and evidence that Shannon tmux is
  effectively unused.
- Toward reject/narrow fix: evidence that more than 80% of pain is only
  Shannon flakiness plus artifact-contract chaos.
- Toward one resequenced project: evidence that all launch paths share one
  owning team and deploy target, making independent shipping unnecessary.

## Top Missing Context

1. Measured `fan.py` baselines: memory, latency p50/p95, orphan rate, success
   rate, cost, and artifact behavior at N=8, N=32, N=50, and N=100.
2. Shannon channel usage: percentage of runs on tmux vs stream, and which
   workloads require interactivity, session rotation, or multi-turn state.
3. Engine capability facts: Pi process/pooling model, `claude -p` session and
   permission surface, Codex sandbox and exit semantics.
4. Consumer inventory for `shannon_plan` and old artifacts.
5. Credential and runner architecture: where provider keys live, how they reach
   subprocesses, and cloud/CI constraints.

## Required Plan Changes

1. Invert the sequence: thin facade first, runtime replacement later.
2. Make fanout a hard numeric spike before deleting `fan.py`.
3. Add credential mediation as the primary enforcement mechanism.
4. Split security into policy translation and OS-level enforcement.
5. Extend the adapter contract with streaming events, liveness/heartbeat,
   graceful vs hard kill, `doctor()`, facade-owned retries, and cost-event
   timing.

## Revised Milestone Order

| Milestone | Content | Gate |
| --- | --- | --- |
| M0: Evidence and contracts | Launcher inventory, old contracts, schemas, Shannon depth audit, measured fanout/Shannon baselines | Executable conformance tests exist; no unknown Shannon audit rows |
| M1: Thin facade | `agent ask/launch/kill/history/doctor` wrapping existing launchers; uniform run records, telemetry, cost, credential brokering begins | Adoption target hit; `agent ask` overhead within budget |
| M2: Fanout spike | Pooled adapter absorbing `fan.py` mechanism; N=50/N=100 measurements | Parity or better vs baseline, or fanout track aborts/redesigns |
| M3: `claude -p` adapter + stream-Shannon retirement | Replace `shannon_stream.py` only; facade legacy-route translation | Contract tests pass; zero stream-Shannon production imports |
| M4: Tmux-Shannon disposition | Build sessionful adapter, signed drop, or proven `claude -p` replacement; migrate `shannon_plan` to `engine_plan` | Import graph and installed artifact scans clean |
| M5: Codex governance | `agent review/apply` over Codex with seeded review/patch evaluation | No quality regression beyond declared thresholds |
| M6: Security hardening | OS-level enforcement, credential mediation, web/browser context boundaries, supply-chain checklist | Threat-model sign-off; bypass attempts fail |
| M7: Deletion and bakeoff | Per-path deletion tests, statistical bakeoff, docs, runbooks, telemetry observation window | Forbidden patterns absent from callers, installed artifacts, and runtime telemetry |

Key property: M2 failure must not block M3-M5. M3 failure must not block M5.
Each milestone must either ship something useful, delete something, or produce
evidence that stops only that track.

## Smaller 80-Percent Plan

The smaller plan:

1. Freeze and test artifact/error/run-record contracts.
2. Ship a thin facade wrapping existing launchers for history, telemetry, kill,
   cost, and `agent ask`.
3. Retire only `shannon_stream.py` in favor of a `claude -p` adapter.
4. Leave `fan.py`, tmux-Shannon, and direct Codex in place as legacy routes
   with telemetry.

This is not acceptable as the endpoint because it leaves the bespoke fanout
contract, Shannon tmux burden, and unenforced security bypasses alive. It is,
however, the right first slice of the full plan.

## Direct Answers To The Ten Oracle Questions

### 1. Strategic Premise

Verdict: pass with changes.

The plan solves fragmentation, Shannon burden, fanout sustainability, and
operator trust. A unified control plane is justified, but only in split form.
Pi must be framed as one engine, not the substrate.

Kill condition remains live until M0 evidence proves this is broader than a
Shannon/artifact cleanup.

### 2. Shared-Surface Boundary

Verdict: pass with changes.

Use the existing dispatcher/adapter seam as the foundation. Add streaming event
channels, liveness, graceful/hard kill, `doctor()`, version pinning, no
adapter-level retries, and credential mediation.

Without credential mediation or equivalent hard enforcement, the cutover
criterion is unenforceable.

### 3. Contract Fidelity

Verdict: pass with changes, hard gate.

Consumer inventory decides what is contract vs quirk. Every field downstream
code reads is a contract until proven otherwise. M0 must produce executable
golden/conformance tests.

No implementation should begin without this.

### 4. High-N Fanout

Verdict: resequence into a gating spike.

Most plausible path: absorb `fan.py` import-once/in-process execution as pooled
adapter internals, fronted by a facade-owned scheduler.

If the spike fails, only the fanout track is blocked.

### 5. Shannon Retirement

Verdict: split stream now, tmux by evidence.

Stream-Shannon is close to `claude -p` and can be retired first. Tmux-Shannon
must be dispositioned by audit: reproduce, obsolete, move to facade, or drop
with sign-off.

Any production Shannon import after cutover is failure by definition.

### 6. Review/Apply Quality

Verdict: pass.

Govern Codex; do not replace its quality. Keep `agent review/apply` narrow and
quality-gated. Pi-vs-Codex arbitration is a later bakeoff, not part of this
critical path.

### 7. Security And Prompt Injection

Verdict: pass with major changes.

The current plan's weakest area. Policy translation is not enough. Add OS-level
enforcement for write-capable and web/browser profiles, explicit env allowlists,
credential brokering, context-boundary protections, and source-dependent tool
attenuation.

As written, the kill condition triggers; it is fixable with tier-two
enforcement.

### 8. Observability And Data Model

Verdict: pass with changes.

Schemas move to M0/M1. `agent replay` means guaranteed timeline reconstruction
plus best-effort re-execution, not deterministic replay. `engine_plan` replaces
`shannon_plan`, with a migration shim and dated rejection deadline.

### 9. Migration, Rollback, Deletion

Verdict: pass with changes.

Rollback must be facade-owned, artifact-stable, telemetered, scan-visible, and
time-boxed. Every compatibility path needs a deletion test and deadline when it
is created.

### 10. Operations, Cost, Adoption

Verdict: pass with changes.

Adoption is the second-largest failure mode after fanout. M1 must ship
`agent ask` before deletion. Add one-command install, `agent doctor`, global
cost ceilings, rate-limit admission, incident runbooks, and debugging parity.

## Non-Negotiable Gates

1. **Contract gate:** all M0 docs exist and old-contract conformance tests pass
   against the current system.
2. **Shannon audit gate:** no unknown audit rows; every intentionally dropped
   behavior has named sign-off.
3. **Fanout gate:** N=50 pooled execution measured at parity-or-better versus
   `fan.py` before deleting `fan.py`.
4. **Enforcement gate:** credential mediation or equivalent hard enforcement is
   live, plus import graph and installed-artifact scans in CI.
5. **Ergonomics gate:** `agent ask` is within the latency/keystroke budget of
   direct CLI use and easier to diagnose on seeded failure.
6. **Deletion gate:** every compatibility path has a CI deletion test and
   calendar deadline.
7. **Security gate:** OS-level enforcement tier is operational for write-capable
   and web/browser profiles.
8. **Quality gate:** Codex review/apply seeded-evaluation thresholds pass before
   cutover.

## Final Summary

The direction survives review; the original shape does not. Split it. Ship the
recording facade first. Gate fanout and Shannon tmux on evidence. Enforce with
credentials rather than grep alone. Make every deletion a test with a date.

## Codex Follow-Up Note

A later high-reasoning Codex review agreed with the split verdict but added one
important refinement: consumer migration/adoption should be its own epic, and
minimum security/enforcement requirements should constrain M0/M1 rather than
waiting for a later hardening track. See `CODEX_DEVIATION_REVIEW.md`.
