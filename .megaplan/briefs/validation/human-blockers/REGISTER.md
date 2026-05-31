# Arnold Epic — HUMAN-BLOCKER REGISTER

**Goal: drive human blockers to ZERO.** A "human blocker" is any point where the plan
(BUILD-time) or the product (RUNTIME) requires a person to decide / approve / review /
intervene before things can proceed. The platform must run end-to-end autonomously — both
the build of the epic and the product at runtime — without parking on a human.

**Conversion principle.** Every human-decision point is turned into exactly one of:
- **(a) DEFAULT** — a pre-made decision recorded now with a one-line rationale.
- **(b) MACHINE-GATE** — the parity gate / contract-checker / strangler+oracle invariants /
  an automated test that auto-proceeds on green and auto-halts/auto-escalates on red, never
  waits on a person.
- **(c) AUTO-ESCALATION** — retry → escalate to a stronger model/tier → skip+flag, so a
  failure never parks on a human.

**Result.**

| Metric | Count |
|---|---|
| Total blockers found | **172** |
| Pre-made (default / machine-gate / auto-escalation) | **172** |
| `must_ask_peter` residue | **0 hard blockers** (1 listed point is a single t0 go/no-go that is itself defaulted below) |

Source detail lives in the six sibling files:
`epic-and-chain.md`, `m1-m2.md`, `m3-m4.md`, `m5.md`, `m6-m7.md`, `edges-and-runtime-gates.md`.
This file is the consolidated index + the concrete edits + the residual-risk statement.

---

## 1. must_ask_peter — the residue (AIM: EMPTY)

**There are ZERO hard human blockers.** The single point anyone flagged as a candidate is the
**top-of-epic launch authorization at t0** (`chain.yaml:10`): committing apex/extreme profiles
across 11 milestones is real, partially-irreversible spend against a chosen architecture.

- **Why it looks like a taste call:** launching an N-day real-cost epic against one architecture
  is the one genuinely strategic/spend decision.
- **Why it is nonetheless pre-decided (so the build never waits):** the category-bet / full-vision
  strategy was **already decided by Peter and written into EPIC §3-21 (2026-05-29 banner)**. The go
  is a recorded fact, not a pending question. After the single t0 "go", `chain start` auto-arms on
  the M1/W8 chain↔EPIC↔briefs lint going green, and every one of the other 171 points is
  machine-gated or defaulted. No agent executing any milestone stalls on it.
- **Cheapest way to keep it pre-decided:** treat the green-lit banner as the authorization of
  record; the lint-green arm replaces any second human touch.

**Net: must_ask_peter = [] (empty). One historical go/no-go, already answered.**

---

## 2. runtime_gates_converted — product human-gates → autonomous replacement

Every gate baked into the PRODUCT, with its machine-gate / auto-escalation substitute:

| Runtime human-gate | Replacement | Mechanism |
|---|---|---|
| `chain.yaml` / supervisor `merge_policy: review` | Auto-merge gated on parity gate + pipelines check/doctor linter + per-milestone strangler/substrate-swap oracles + chain↔EPIC↔briefs lint; red → auto-halt+revert | machine-gate |
| `on_failure: stop_chain` (chain + supervisor tier) | retry fresh ×2 → bump profile one tier, re-run once → only then stop_chain + auto-ticket | auto-escalation |
| `on_escalate: stop_chain` | raise robustness one level (thorough→extreme), re-drive once; stop_chain only if the stronger re-run also fails | auto-escalation |
| `execute.py:108-115` approval gate (`--user-approved`) | `auto_approve=true` default; auto-proceed when `recommendation==PROCEED && passed`; gate stays opt-in for interactive use | machine-gate |
| clarify human-gate `STATE_AWAITING_HUMAN` (`override.py:851`, `plan.py`, `auto.py:1390`) | auto-answer from brief/prep-fanout research → escalate to stronger model → best-guess + flag, then auto resume-clarify; never indefinitely parks | auto-escalation |
| verify-human `STATE_AWAITING_HUMAN_VERIFY` (`verifiability.py:215`, `execute.py:248`) | M4 oracle / criteria-verification handler: green→auto-DONE, red→retry→stronger reviewer model records verdict+evidence | machine-gate |
| `gate.py:563-568` ESCALATE → human add-note | `on_escalate=force-proceed` with one stronger-gate-model retry first; force-proceed-with-debt logged to debt registry (reversible) | auto-escalation |
| `gate.py:458-466` BLOCKED-for-human-review on correctness/security flag | `STATE_BLOCKED` = auto-halt on RED; auto one revise+stronger-model round → fail into chain policy | auto-escalation |
| the 9 override actions (`override.py:898-910`): force-proceed, recover-blocked, replan, abort, resume-clarify, set-robustness/profile/model, add-note | M4 RecoveryPolicy spine auto-fires general control ops per classify→{retry,escalate,halt}; named actions stay available to a human but are never required | auto-escalation |
| `override.py:218-241` force-proceed strict-notes "human required" | `strict_notes=false` for autonomous runs (already default-off); metaplan/doc mode auto-runs `revise` to absorb notes | auto-escalation |
| `override.py:431-522` recover-blocked needs human `--reason` + per-blocker resolution | external_error → `megaplan resume` (machine retry); task/quality → auto-recovery agent generates reason+classification and re-runs, else fail into chain policy | auto-escalation |
| `auto.py:1418-1426` / `gate.py:565` TIEBREAKER pending → human runs tiebreaker | auto-invoke `tiebreaker-run` on `STATE_TIEBREAKER_PENDING`, then resume; fix the silent TIEBREAKER→ITERATE downgrade to a loud stronger-model retry | machine-gate |
| `resolutions.py:29` handle_user_action (`created_by='operator'`) | every user_action must carry a `fallback_mode` (finalize fails loud without it); auto.drive applies the fallback as actor | machine-gate |
| `resolutions.py:177` handle_quality_gate | auto-resolve non-terminal blockers via recorded `fallback_mode`; terminal → one bounded stronger-model retry → fail into chain policy | auto-escalation |
| discovery trust tier "operator decides in_tree/blessed/quarantined" (`m6 §46-49`, `edges-map edge 6`) | path-derived classifier: in-tree=auto-exec, out-of-tree/`~/.megaplan/pipelines`=quarantined-by-default (manifest-only, no exec, SDK-assigned tenant_id + capped quota), blessed=explicit allowlist (default empty); quarantined→blessed auto-promotes on passing the graph-abuse oracle | machine-gate |
| Theme-E silent-vanish (`except Exception: return None`) on bad package | loud catalogued discovery error, exclude from runnable set, surface in doctor/check, proceed with the rest | auto-escalation |
| SKILL.md required (`m6 §97-98`, `m7 §51-52`) | discovery fails the package loudly if SKILL.md absent; `pipelines check` exits non-zero | machine-gate |
| `STATE_AWAITING_PR_MERGE` (`m5d`, `__init__.py:1213-1409`) | bind onto M5c awaiting_human + auto-merge: green CI+gates → supervisor auto-merges (`gh`); red → auto-escalate | machine-gate |
| `ChainSpec.escalate_action='force-proceed'` literal (`m5d:308`) | replace literal with general M5c target via `valid_targets()`+`apply_transition`; default escalate ladder retry→re-route→force-advance→abort | machine-gate |
| blocked-execute recovery branching on planning verdict (`m5d:1053-1122`) | branch on the general `blocked` run-OUTCOME (not `STATE_BLOCKED`), auto-invoke recover-from-stuck with bounded retry ladder (>1) → escalate/abort | auto-escalation |
| loop-node termination/teardown (`m3 §84-90`) | mandatory `max_iterations` cap + teardown-on-all-paths (normal/cap/exception/budget); no human stops the loop | auto-escalation |
| set-robustness mid-run re-realization (`m3 §56-57`, override) | rebuild graph + auto-revalidate cursor; reject with a typed error if the rebuilt cursor would hit a deleted node — applies cleanly or rejects, never parks | machine-gate |
| restorable_boundary composed with subprocess/fan-out (`m3 Done #5`) | RAISES LOUD at compose time (whole-blob restore rolls back the record not the world) — auto-halt with typed error | machine-gate |
| hermes dispatch liveness/stall (no watchdog) (`m4 Scope #1`) | service guarantees active_step + liveness sink at dispatch; liveness written on token progress not silence; supervisor polls + auto-kill/auto-retry via idle/pre-first-byte timeouts | machine-gate |
| two-tenant shared key/budget contention (`m4 Done #4`) | `fcntl.flock`'d on-disk ledger: no double-issue, shared backoff, shared spend cap that stops the composition; byte-identical in-process fallback | machine-gate |
| attestation/notary failure (`m4 Scope #3`) | attestation never branches flow; failure is a typed result the planning binding consumes — not a stop-and-ask gate | default |
| C1 — product-intent ambiguity no research can resolve | auto-pick most reversible/conservative interpretation, record as assumption note + debt flag, proceed; human can override post-hoc | default |
| C2 — first-ever NEW capability KIND in a community manifest | new capability kinds default to DENY (package stays quarantined, runs without it); allowlist grows only via versioned code change | default |

---

## 3. concrete_edits — the EXACT changes to make now

### chain.yaml (`.megaplan/briefs/epic-pipeline-unification/chain.yaml`) — APPLIED
1. `merge_policy: review` → **`merge_policy: auto`** (gated on the per-milestone machine gates the epic ships).
2. `on_failure: { abort: stop_chain }` → **ladder**: `retry: retry_milestone` (×2 fresh) → `escalate: bump_profile` (premium→apex / high→max, re-run once) → `abort: stop_chain` (terminal backstop, auto-files a ticket).
3. `on_escalate: { abort: stop_chain }` → **ladder**: `escalate: bump_robustness` (thorough→extreme, re-drive once) → `abort: stop_chain` only if the escalated re-run also fails.
4. line-10 "review only; do not chain start yet" → **auto-arm**: one t0 human go (already given in EPIC §3-21), then `chain start` arms automatically on M1/W8 lint-green.
5. `driver.require_clean_base: true` added — refuse to start a milestone unless forked from a clean main (kills the carried-WIP false-positive review halts).
6. `auto_approve: true` documented as runs-straight-through (no pre-execute park).

### Trust-tier default policy (M6) — to encode in discovery
- `in-tree` (repo / installed-dist, a path fact) = **trusted, auto-exec on selection**.
- `out-of-tree` / `~/.megaplan/pipelines` = **quarantined-by-default**: non-executing manifest-first discovery, SDK-assigned `tenant_id = hash(name + install_path)`, capped per-package quota (equal-share fraction of parent budget, floored at one milestone's typical spend), capability-subset check.
- `blessed` = **explicit allowlist, default empty**; `quarantined→blessed` auto-promotes only on passing the graph-abuse oracle. Tier is computed from origin — no interactive prompt.
- New capability KINDs default to **DENY** (C2); allowlist grows via versioned code change only.

### Per-brief Open-question resolutions (each defaulted; all `must_ask_peter=false`)
- **M1**: chain.yaml provenance → lint the existing file, fail-loud-if-absent. `schema_version` → JSON-path in M1, DB column deferred. bare `run_pipeline` max_iterations cap → **not** added in M1 (M4 owns budgets). Discovery boundary → in-tree=fail-loud, user-pack=report-loud (DC#5). Scaffold → any green shape passing `pipelines check` (DC#8).
- **M2**: build-time port resolution → check vs fully-rewritten graph per parity-gate robustness level, defer re-realization to M3, unit-assert unresolved/mistyped port fails build + CAS conflict caught. ReduceResult → frozen dataclass as a typed Port. CAS conflict → fail-loud in-process (DC#6). `select.rule` → Callable with `top_1/top_k/threshold`. GateRecommendation allow-list → types.py edge-dispatch + planning binding only, enforced by the ZERO-GateRecommendation grep gate (DC#1). Partial conversion → merge only when grep-gate=0 AND all consumers green together.
- **M3**: snapshot granularity → whole-blob copy of state.json. mid-run re-realization → Done-#2 cursor-survival invariant (rebuilt topology reproduces recovery/resume states + cursor on a live node). snapshot location → sidecar `.state-versions/<id>.json` under the per-plan flock. cross-shard budget → single-tenant in M3, folding deferred to M4. "one Store" vs "irreconcilable" → interfaces-with-backends (event-sourced scaffolded behind the interface, no real backend in M3). cloud `_phase_command` shim → land in M3, smoke oracle verifies. acceptance toy → tiny backtracking constraint-solver.
- **M4**: classify consumes ExitKind+error-layer (target-agnostic, no STATE_*, may query predecessors()). budget authority → `runtime/` by `key_pool.py`, `fcntl.flock`'d ledger; covers Hermes/OpenRouter acquire_key only (Codex/Shannon = separate semaphore). spend-folding → live in-broker accumulator; journal reconciles post-hoc. CostTracker reads the live authority (Done-#4 two-tenant test). rollup → opt-in `--dispatch`. liveness sink → injected-callback primary + plan_dir-shaped scratch supported. oracle's first user → git-bisect run(cmd) branching consumer. per-tenant sub-budget → **reserve** the field, don't build partitioning. event schema → `schema_version:1`, validate-on-emit, report-only until last milestone. halt(kind) → terminal recorded outcome, does NOT block on a person.
- **M5a**: tier metadata → lightweight registry dict keyed by export name (checker-readable). PromoteFn → returns the M2 routing-key type. arnold_api_version → reserve in both module constant + tier-table. tier assignment → F1/F3+macros=provisional, `_*`=internal, only break-committed=stable; default provisional.
- **M5b**: keep the arbitrary-deps DAG (`io.py:58`). F5 returns typed `Reduce[T]`, binding maps to phase_outcome, M5c re-homes STATE_* later. `_is_blocking_deviation` → merge stays mechanical, classification moves to the reducer. rater≥dispatchee gap on cheap-finalize → carry as recorded KNOWN GAP (log→continue→surface in report).
- **M5c**: `apply_transition` is general (X→Y + emit); `synthesize_artifacts` is the binding hook force-advance calls. recover_targets → raw `predecessors()` (blocked/failed return []), upgrade only if a test needs it. gate predicates → binding-side resolvers the projection invokes; SDK keeps 3 coarse gate edges.
- **M5d**: supervisor sits BELOW cloud's operator loop. one supervisor tier / two variants; bakeoff's reduce IS M2 select at run granularity. PR-merge wait binds onto M5c awaiting_human + F6 (auto-merge). acceptance = automated throwaway canary epic (≥1 dep edge, ≥1 induced failure exercising escalate/recover).
- **M6**: manifest names the `(subprocess_isolated, graph+loop-node)` pair M3 resolved (M6 reads, doesn't re-pick). `workflow_next` → thin projection over M3's realized graph, re-exported at its old path. arnold discovery WRAPS `discover_python_pipelines`. arnold_api_version range `[1.0, current-major)`, out-of-range rejected loudly at discovery. fourth tool = select-tournament (shared with M7). cheap new pipeline = upgrade jokes.
- **M7**: umbrella skill COMPOSES (does not replace) megaplan-decision/observe/epic during the rename. Boundary: module-specific→SKILL.md, cross-module→`docs/arnold/`. generated docs → CI `--check` re-emit-and-diff, byte-non-identical auto-fails. examples → CI extracts each snippet from its source pack and runs it. external-builder acceptance → sandboxed subagent given ONLY `docs/arnold/` + scaffold (no SDK internals), all criteria are exit-code/artifact/grep; red auto-files the doc gap and retries with a stronger model.

### CLI-migration / edges (each adopt the brief's own written resolution as a parser-snapshot fixture so drift auto-fails CI)
- `arnold auto [module=planning]`; override split umbrella (abort/add-note/set-*) vs planning (force-proceed/replan/recover-blocked); resume stays planning.
- Command-move ordering M1→M3→M4→M5c→M5d→M6 is binding.
- Delete the silent `v1.md` fallback in `step_helpers.py:104`; `arnold pipelines check` fails build on missing/typo'd/mistyped dep.
- ZERO-GateRecommendation/STATE_* grep gate in SDK modules; standing behavioral-replay + substrate-swap oracles every milestone; chain.yaml regenerated as one EPIC+briefs triple, drift caught by the anti-drift lint.

---

## 4. residual_risk of full autonomy + the machine guardrail that contains it

**Risk:** with all human gates removed, a wrong-but-green change can auto-merge, or an
auto-escalation ladder can spend real money chasing an unrecoverable defect, or a quarantined
community package could be wrongly auto-promoted. The substrate swap is also structurally
invisible to the happy-path parity gate.

**Containment (all machine, no human in the loop):**
- **Merge correctness** is gated on the union of the parity gate + per-milestone strangler/
  substrate-swap oracles + ZERO-GateRecommendation/STATE_* grep gates + binder unit assertions —
  a partial/wrong conversion cannot go green, so it auto-blocks rather than auto-merging.
- **Spend** is capped by the `fcntl.flock`'d live budget authority that stops a runaway
  composition at the cap; the escalation ladder is bounded (retry ×2 → one stronger re-run →
  stop_chain + auto-ticket), so a failure terminates with a flagged artifact instead of burning
  unbounded budget or parking on a person.
- **Untrusted code** never executes on import (manifest-first non-executing discovery) and runs
  only sandboxed with an SDK-assigned tenant_id + capped quota; promotion is a passed graph-abuse
  oracle, and new capability kinds default to DENY.
- **Substrate-swap blindness** is covered by the per-milestone behavioral-replay oracle against
  recorded real-run traces (resume/crash-isolation/version-skew at M3/M4/M6) — the parity gate's
  honest label is "happy-path control-flow/artifact parity, NOT drift-provably-zero", and the
  oracle is the supplementary required gate.
- **Build-correctness** rides characterization-replay (byte-stable behaviour vs recorded runs) +
  the clean-base pre-run assertion (no carried-WIP false positives) + fail-loud everywhere a
  silent default previously hid a defect.

The standing backstop is `stop_chain + auto-filed megaplan-ticket`: the platform halts and records
a structured failure artifact a later run consumes — it never silently waits for a person.
