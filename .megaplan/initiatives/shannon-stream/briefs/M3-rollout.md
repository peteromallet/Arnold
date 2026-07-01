# M3: Rollout — concurrency cap, API-adapter proof, sampled shadow, flag-gated cutover (keep tmux)

**Milestone id:** `M3-rollout` · **Profile:** `partnered` · **Robustness:** `full` · **Depth:** `medium` · **Vendor:** `codex` · **Repo:** megaplan

Read `00-OVERVIEW.md` for the epic invariants. DEPENDS ON M1 (seam) + M2 (the worker emitting
`rate_limit`, behind a flag). This is the milestone that flips the default to stream-json — but does NOT
delete tmux.

**Internal sequencing (do in order):** A (cap) → B (API proof) → C (shadow) → D (cutover). C depends on A
(the cap protects shadow from starving the subscription); D depends on C (parity gate green).

## Outcome
The headless stream-json channel becomes the **default**, protected by a blunt concurrency cap, validated
by a sampled shadow-parity gate, with the subscription→API flip proven and tmux retained as a maintained
fallback.

## Part A — Concurrency cap (replaces the governor)
- **Outcome:** a blunt host-wide cap (~3) that bounds concurrent Claude+Codex turns and refuses retryably.
- **Scope:** generalize today's flock `subscription_gate` into a simple cap that ALSO gates Codex turns
  (zero admission control today, same ChatGPT subscription); surface + LOG the `rate_limit` signal for
  backpressure visibility. **OUT:** any dynamic governor / token-bucket / hysteresis (DEFERRED).
- **Locked:** cap, not governor; host-wide + engine-spanning; refusal retryable, never terminal; a held
  slot must not starve a cheap finalize (release on backoff / fixed acquisition order vs the baseline gate).
- **Open:** cap value (~2 vs ~3, default ~3); single global pool vs per-auth-channel pools.

## Part B — API-adapter proof (the validated flip)
- **Outcome:** the same `run_step` seam proven on an API key — one real phase completed via API billing
  with cost/quota/tool-permission parity measured — plus a written **migration-trigger list**.
- **Scope:** implement the auth/billing axis (subscription-OAuth ↔ API-key) as a real selector; run one
  phase on an API key through `ShannonStreamWorker`; record cost/quota/parity; write the trigger list into
  `docs/shannon-stream-channel-plan.md`. **OUT:** any forced migration to API billing (only prove it).
- **Locked:** subscription stays the daily driver; API is a bounded, tested alternative; migration is
  trigger-driven, not now.
- **Open:** whether an API key is available in this environment; if not, degrade to a documented dry-run of
  the adapter path (state which). Migration-trigger thresholds (utilization ceiling + which signals flip).

## Part C — Sampled shadow (the confidence gate)
- **Outcome:** a sampled shadow mode that proves parity on deterministic artifacts at N≥5.
- **Scope:** run BOTH channels on a **≤10% sample** of phases (NEVER double every Opus turn — the
  subscription is ~0.84 of its 7-day cap; doubling induces the starvation it's testing); compare on
  **deterministic artifacts only** — same `exit_kind` class, payload schema validity, `landed_diff` status,
  `worker_did_work` status. Cost/latency are drift-monitoring, NOT gating. **Reuse the existing bakeoff A/B
  harness + shadow completion-contract** — no new scaffolding. The shadow arm respects the Part-A cap.
- **Locked:** sampled, not full doubling; deterministic-artifact parity at N≥5; reuse bakeoff.
- **Open:** how to adapt bakeoff for channel (not profile) A/B; sample rate; whether to gate sampling on
  low utilization.

## Part D — Cutover (keep tmux)
- **Outcome:** stream-json is the default; tmux is one flag away and verified working; babysit doc rewritten.
- **Scope:** flip the flag (stream-json default); the channel switch is safe **per-phase** (sessions keyed
  per step+agent+model) **only if the switch forces `fresh=True`** — never mid-phase-retry; rewrite the
  babysit skill's "ground truth = tmux pane" section to point at stream-json stdout / transcript tail.
  **OUT — DO NOT delete:** the tmux path, readiness probe, paste-buffer, transcript-tailing, bun driver.
  ALL retained as the maintained fallback (deletion is a separate, later decision gated on the API path
  being production-proven).
- **Locked:** keep tmux; per-phase `fresh=True` on switch; a single flag flip restores tmux with no state
  corruption.
- **Open:** the cutover flag's home (plan state vs env) and read granularity.

## Constraints (whole milestone)
Vendor codex; execute on the codex family (off Shannon); additive — the flag defaults to stream-json only
at Part D; the shadow arm must respect the Part-A cap; keep tmux. OS-user is the safety boundary.

## Done criteria
- Cap bounds concurrent Claude+Codex turns under induced load, refuses retryably, no priority inversion.
- `rate_limit` logged per turn; no dynamic governor built.
- Auth axis selects API-key vs subscription; a phase completes on the API channel (or documented dry-run);
  cost/quota/parity recorded; migration-trigger list written.
- Sampled shadow runs; **N≥5** phases at deterministic-artifact parity; no landed-guard regressions.
- stream-json is default; tmux reachable via one flag and verified post-cutover; switch forces `fresh=True`
  (test shows no corruption); babysit ground-truth section rewritten.

## Touchpoints
`megaplan/workers/subscription_gate.py`, the codex dispatch path + the cutover flag in
`megaplan/workers/_impl.py`, `megaplan/workers/shannon_stream.py` (auth axis, session/fresh),
`megaplan/runtime/key_pool.py`, `megaplan/bakeoff/*`,
`megaplan/orchestration/completion_contract.py` + `phase_result.py` (parity comparands), the babysit skill
doc, `docs/shannon-stream-channel-plan.md` / `shannon-tmux-architecture.md`.

## Rubric
Must: cap bounds Claude+Codex retryably (no inversion); API proof or documented dry-run + trigger list;
sampled shadow (not full doubling) at N≥5 on deterministic artifacts; flag-gated cutover with working tmux
fallback + per-phase `fresh=True`; babysit doc rewritten; tmux NOT deleted. Should: cap-value + pooling
rationale; bakeoff reuse; sample-rate rationale.
