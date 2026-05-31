# Pre-launch sequencing re-check — Arnold epic (under the autonomy/oracle-machinery-unbuilt gaps)

**Vantage:** SEQUENCING RE-CHECK. Given (a) the autonomy ladder is unimplemented in the harness and
(b) the oracle/gate hooks are to-be-built BY the milestones, does the sequenced order in
`.megaplan/briefs/validation/sequencing/PROGRAM.md` still hold so the chain can actually self-drive after one
t0 "go"? Short answer: **the milestone DEPENDENCY order is sound, but the program's claimed
self-driving FRONT is fictional.** The autonomy ladder + clean-base enforcement + the strangler/oracle
*gate runner* are prerequisites of M0 itself, none exist in the harness today, and several are
chicken-and-egg with the very milestones meant to build them. The chain as written will halt on a human
at the first non-clean failure — by harness behavior, not by design intent.

---

## A. Re-confirmed baseline (the exemplar of the class)

`megaplan/chain/__init__.py`:
- `_action()` (`:335-345`) reads **only** `block.get("abort", default)` (`:339`). The `retry:` and
  `escalate:` ladder keys in `chain.yaml on_failure`/`on_escalate` are **silently dropped** — not
  validated, not stored, not consulted.
- `VALID_FAILURE_ACTIONS = ("stop_chain", "skip_milestone", "retry_milestone")` (`:89`). There is no
  `bump_profile`/`bump_robustness`. Grep across `megaplan/`: **zero hits** for `bump_profile`,
  `bump_robustness`.
- `_handle_outcome()` (`:1208-1234`) maps a failed/stalled/escalated/aborted plan through `on_failure`
  / `on_escalate` to exactly one of `stop` / `skip` / `retry`. With this chain.yaml both resolve to
  `abort: stop_chain` → returns `"stop"` → `run_chain` returns `_result("stopped", …)` (`:1469-1476`)
  and the chain **halts, waiting for a human**.
- `require_clean_base` (chain.yaml `driver:` `:128`): grep across `megaplan/` → **zero hits**. The
  driver dataclass (`:295-310`, constructed `:403-421`) never parses it. The chain instead snapshots
  `preexisting_dirty_paths = _dirty_worktree_paths(root)` at start (`:1250`) and *tolerates* carried
  WIP — the exact false-positive source MEMORY `worktree_carry_review_falsepositive` documents.

So at runtime the chain.yaml autonomy block (`:102-128`) is **aspirational config the harness drops**.
`merge_policy: auto` and `driver.auto_approve: true` ARE honored (`:349`, `:401`, `:1502`); the
ladders and clean-base are not.

This is the EXEMPLAR. The sequencing re-check below hunts the same class: **milestones placed as if
their prerequisite harness/oracle machinery already exists, when it does not — including the bootstrap
circularity that the chain needs autonomy/gate/oracle machinery the milestones are supposed to BUILD.**

---

## B. The corrected FRONT of the sequence

The PROGRAM's stated front is `M0 → M1 → M2.5 → M3 …` with "one t0 go, then no human in the loop"
(`PROGRAM.md:340`, `:363-364`; `REGISTER.md:42-46`). Under the gaps, the true front is:

```
[ M(-1) MANUAL PRE-STEP, off-chain, human-run once ]
   ├─ build/implement the autonomy ladder in the chain harness
   │    (retry×N counter + bump_profile + bump_robustness), OR
   │    accept stop_chain semantics and staff a human for chain restarts
   ├─ implement & honor driver.require_clean_base (or enforce clean base by hand each milestone)
   └─ build the strangler/oracle GATE RUNNER that M0's W6 assumes already exists
          ↓
[ M0 keep-alive floor ]  ← only NOW can run, and even M0 is double-duty (see D)
          ↓
   M1 → M2 ∥ M2.5 → M3 (apex) → M4 → {M5a ∥ M5b ∥ M5-eval} → M5-cal → M5c → M6 ∥ M5d → M7-*
```

The **dependency-DAG body** (M1 onward, including the `M5-eval → M5-cal` non-negotiable edge and the
M6-last atomic swap) is **correct and unchanged** — that part of the re-derivation holds. What does
NOT hold is the claim that the chain *self-drives from t0*. The autonomy/clean-base/gate-runner triad
is a true M(-1) that must land **before M0 can autonomously run**, and it is unbuilt.

---

## C. The bootstrap circularity (the deep finding)

The program is **self-referential at the front in a way it does not acknowledge**:

1. **The ladder that is supposed to keep the build human-free is unbuilt, and no milestone builds it
   in the harness.** The RRECOVERYPolicy spine `classify(error)->{retry|escalate|halt}` is M4
   (`PROGRAM.md:187-188`), and the supervisor/`ChainSpec.escalate_action` rework is M5d
   (`REGISTER.md:74`). But the chain that DRIVES M0–M4 is the *pinned external engine* (M0 W1,
   `m0-keepalive-floor.md:38-47`) — frozen at t0 `main` HEAD. So even after M4/M5d build a ladder in
   the working tree, the **driving engine never gets it** (it is pinned, `--no-git-refresh`). The
   autonomy ladder therefore has to exist in the PINNED engine at t0 — i.e. it must be built as a
   manual pre-step and committed to `main` BEFORE the t0 pin, never as a chain milestone. The program
   places ladder-building inside the chain (M4/M5d) while relying on the ladder to drive the chain
   from M0. Circular.

2. **M0's own done-criteria assume the ladder already runs.** `m0-keepalive-floor.md` Done #8 (`:161-162`)
   and Open-question "red strangler gate" (`:120-122`) both say red "enters the bounded ladder
   (REGISTER §3 chain.yaml ladder), retry ×2 → bump profile/robustness → stop_chain + ticket, never a
   human wait." That ladder is the unimplemented one. M0 cannot satisfy its own autonomy done-criterion
   on the harness as shipped — its gate red-path falls through to `stop_chain` (human halt).

3. **The strangler/oracle GATE RUNNER M0/W6 wires up does not exist yet either.** W6
   (`m0-keepalive-floor.md:81-84`) is "a single machine-gate entrypoint … consumable by the chain's
   per-milestone gate." But there is no per-milestone strangler-gate hook in `chain/__init__.py` to
   consume it (the chain's only post-plan decision logic is `_handle_outcome` on plan status +
   `merge_policy`; there is no "run external oracle, gate advance on its verdict" path). So M0 is not
   merely *configuring* a gate runner — it must **build the harness hook that invokes it**, which is
   itself harness machinery the rest of the epic relies on. That hook is a prerequisite of M1's
   advance, so it too belongs in M(-1) or must be explicitly scoped as M0 harness work (today M0's
   brief frames it as "wiring," understating it).

Net: **the front three rungs of self-driving (autonomy ladder, clean-base enforcement, oracle-gate
runner) are prerequisite MACHINERY that the milestones are nominally supposed to provide but in fact
cannot provide to the engine that is driving them, because that engine is pinned-frozen at t0.** They
must be a manual pre-step landed to `main` before the pin.

---

## D. M0 is doing double-duty (manual setup AND a chain milestone)

`PROGRAM.md:69-82` and `chain.yaml:18-22` place `m0-keepalive-floor` as the first **chain milestone** —
i.e. it is driven BY a `megaplan chain`. But M0's deliverable W1 (`m0-keepalive-floor.md:38-47`) is
"build/install a frozen megaplan from a pinned tag into its own venv and invoke `megaplan chain` from
THAT interpreter." That is the launcher the chain runs *inside*. **A milestone cannot build the engine
that is executing it.** Concretely:

- To run M0 *as a chain milestone* you already need a driving engine. If that engine is the editable
  tree, you are in the dogfood-shadow trap M0 exists to kill (MEMORY `dogfood_engine_shadow`). If it is
  a pinned engine, then the pin/venv/launcher (W1) already happened **before** M0 ran — i.e. W1 is a
  manual pre-step, not a chain milestone deliverable.
- Same for W2's report-only validator and W6's gate hook: the chain must already tolerate unstamped
  state and already invoke the strangler gate *to drive M0 at all*; M0 cannot be the first place those
  land if M0 is itself chain-driven.

**Fix:** split M0. `M0a (manual pre-step, off-chain)` = pinned-engine launcher + venv + `--no-git-refresh`
wiring + report-only schema reader + the chain's per-milestone oracle-gate HOOK + the autonomy ladder
(§C) + clean-base enforcement — all landed to `main` and committed, THEN the t0 pin is taken against
that HEAD. `M0b (first chain milestone)` = the dual-run rig + replay-oracle corpus + substrate-swap
skeleton (W3/W4/W5), which CAN be chain-driven because they run on throwaway plans and don't touch the
driver. The current single `m0` conflates an engine-bootstrap (must precede the chain) with chain work.

---

## E. Does the per-milestone "oracle is sole retirement authority" gate require the oracle BEFORE M1 retires anything?

Yes, and the program is *internally consistent* on this point — but only because **M1 retires nothing**
(`PROGRAM.md:84-103`: shadow-WAL only, "retires nothing"; M1 Why-here `:102` "WAL is shadow-only —
retires nothing"). The first real retirement is the M3 authority flip (state.json → cache), gated on
the substrate-swap oracle whose skeleton is M0/W5 and whose real cross-version body is M3 itself
(`PROGRAM.md:384`; `m0-keepalive-floor.md:74-79`). So the ordering "oracle skeleton (M0) before first
retirement (M3)" is respected.

**But two cracks under the gaps:**
- The replay-oracle that is the SOLE retirement authority (`PROGRAM.md:381-382`) is only a HARNESS in
  M0; its *verdict must gate chain advance*, and there is no chain hook to make a red oracle block
  advance (§C.3). Without that hook, "oracle is sole retirement authority" is documentation, not an
  enforced gate — a wrong-but-green M3 flip can advance on plan-status alone (`_handle_outcome` only
  looks at `outcome.status`, `:1213-1234`). This is the same disease as the dropped ladder.
- M1's fold-equivalence assertion ("asserted against state.json every milestone", `PROGRAM.md:90-91`)
  is the replay oracle's "first real consumer" (`m0-keepalive-floor.md:70`). If M0b (the corpus) is
  chain-driven and M0a (the hook) is the pre-step, the dependency M1⇐M0b⇐M0a must be made explicit;
  today it is hidden inside one `m0` node.

---

## F. Milestones that CANNOT run autonomously until prerequisite machinery lands

| Milestone | Cannot autonomously run until… | Why (file:line) |
|---|---|---|
| **M0 (as chain milestone)** | pinned-engine launcher + oracle-gate hook + ladder exist in the DRIVING engine | W1 builds the launcher the chain runs inside (`m0:38-47`); Done #8 needs the unbuilt ladder (`m0:161`) |
| **M1** | M0's gate hook + corpus landed; fold-equivalence has an oracle to assert against | `PROGRAM.md:90-95`; consumer of M0/W4 (`m0:70`) |
| **M3 (apex flip)** | substrate-swap oracle is a *gating* verdict, not just a harness | sole-retirement-authority is unenforced without the chain hook (`PROGRAM.md:381-384`; `_handle_outcome :1213-1234`) |
| **ANY milestone that fails/escalates** | autonomy ladder implemented OR a human staffed | `on_failure/on_escalate` both collapse to `stop_chain` (`:339`, `:1228`) — first transient/idle stall halts the chain |
| **ANY milestone forked off dirty main** | `require_clean_base` honored OR clean base enforced by hand | field unread (`:128`, zero hits); carried-WIP tolerated (`:1250`) → review false-positives (MEMORY) |
| **M5d supervisor** | M6 relocation done AND M5c control ops AND the ladder/escalate-action rework actually wired | `PROGRAM.md:291-303`; `ChainSpec.escalate_action` literal still `force-proceed` (`:308`), REGISTER wants it generalized (`REGISTER.md:74`) — unbuilt |

---

## G. Verdict-bearing fixes (concrete, pre-launch)

1. **Insert a true M(-1) manual pre-step** (off-chain, human-run once, landed to `main` BEFORE the t0
   pin): implement the autonomy ladder in `chain/__init__.py` (`_action` must parse `retry:`/`escalate:`;
   add `bump_profile`/`bump_robustness` + a retry counter), implement `driver.require_clean_base`, and
   add the per-milestone strangler/oracle-gate HOOK that gates advance on the oracle verdict. ONLY THEN
   pin the engine. Without this the "one t0 go, zero human blockers" guarantee is false on contact.
2. **Split `m0` into M0a (engine-bootstrap pre-step) and M0b (chain milestone)** — a milestone cannot
   build the engine executing it (§D). Make M1⇐M0b⇐M0a explicit in PROGRAM + chain.yaml.
3. **Either implement the ladder/clean-base OR rewrite the autonomy claims as "stop_chain + human
   restart."** Do not ship chain.yaml `:102-128` and REGISTER `:42-46`/`:57-58` claiming auto-escalation
   the harness silently drops. The honest fallback (stop_chain + auto-ticket) IS implemented and is a
   valid posture — but then `must_ask_peter ≠ 0`: every failed milestone is a human restart.
4. **Wire the oracle verdict into chain advance** so "oracle is sole retirement authority" is enforced,
   not narrated; otherwise M3's flip can auto-advance on plan-status while the substrate oracle is red.
5. **Keep the M1→…→M6→M7 body as-is.** The dependency order, the `M5-eval→M5-cal` non-negotiable edge,
   and M6-as-last-atomic-swap are correctly derived and need no resequencing.

---

## One-line verdict

The milestone DEPENDENCY order is sound, but the program's self-driving FRONT is not: the autonomy
ladder, `require_clean_base`, and the per-milestone oracle-gate runner are unbuilt prerequisite
MACHINERY (zero hits in `megaplan/`), they are circularly assigned to milestones that the pinned t0
engine can never receive, and M0 is double-duty (it builds the engine that runs it) — so they must
become a manual M(-1) pre-step landed before the t0 pin, or the chain halts on a human at the first
failure. **Do not launch as a single t0-armed self-driving chain until §G.1–G.4 land.**
