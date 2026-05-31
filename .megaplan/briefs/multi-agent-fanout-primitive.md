# Brief: A unified multi-agent fan-out primitive (scatter → invoke → reduce)

**Status:** DESIGN — REFINED after 5-agent adversarial review + adjudication (2026-05-23). The
core thesis (one stateless `run_oneshot` contract + shared scatter/gather across backends) stands;
what was cut is the over-parameterized single entry point (split into two) and the speculative
Phase 4. See **§0 Review outcome** for the adjudicated verdict. Original full proposal preserved
below §0. Drafted 2026-05-23 after a 4-wave investigation (critique-step mechanics, Hermes-only
gating root-cause, concurrent-site inventory, read/write-merge machinery sweep).
**Authors:** Claude + DeepSeek investigation; decisions by Peter.
**Related:** supersedes the narrow "parallel Claude/Codex critique" idea; touches the
critique/review/bakeoff/pipeline subsystems.

---

## 0. Review outcome (5-agent DeepSeek panel, 2026-05-23)

Five adversarial lenses ran; below is the **adjudicated** result — what was accepted, and where the
panel's confidence was discounted on grounds the (repo-bounded) reviewers couldn't see.

**Accepted (these change the plan):**
- **Split the entry point (abstraction, lens 1).** `isolate` and `reduce` are coupled, not orthogonal
  (SHARED+git-merge / WORKTREE+flag-union are nonsense). Read-merge is *combine-all/commutative*;
  write-merge is *select-one/competing with an all-finish barrier*. **→ expose two top-level APIs —
  `fan_out` (aggregate) + `compete` (select-one) — over the SAME shared core (`run_oneshot` +
  scatter/gather). The shared core is preserved; only the single over-parameterized entry is cut.**
- **Sequence Shannon-first + prove the write axis early (lens 3).** Genuine improvement; adopted.
- **Do the cheap dedup before anything (lens 4's minimal cut).** Real win regardless of the rest.

**⚠️ CORRECTION (2026-05-23, supersedes the earlier "headless door" finding below).** The
`claude -p` headless path is **rejected for the Claude backend** — confirmed, not speculative:
- **Why.** Shannon drives Claude *interactively in tmux specifically to use the Claude subscription
  via OAuth* (`shannon.py:937-948`: empty `ANTHROPIC_API_KEY` → "falls back to OAuth credentials").
  `claude -p` print mode forces **metered API-key billing**. The "$0.21, schema-valid" probe I ran
  earlier was not a win — it cost $0.21 *because it billed the API*, i.e. it demonstrated exactly the
  path megaplan avoids. So "headless door is feasible" was the wrong conclusion: it's *technically*
  feasible but *economically* rejected.
- **What this breaks in this brief.** The clean "headless `run_oneshot` on Claude" story has a hole:
  a stateless Claude per-call contract still can't use `-p` without losing subscription billing, so
  Claude's `run_oneshot` would itself have to ride *hardened interactive Shannon*, not a `-p`
  subprocess. The Hermes/Codex `run_oneshot` story is unaffected; only Claude is constrained.
- **The real Shannon root cause (diagnosed empirically 2026-05-23).** Shannon runs Claude as an
  *interactive TTY app in a detached tmux session*. Two proven failure modes: (1) interactive gates
  (workspace-trust dialog) hang capture — Claude only skips the trust dialog for non-TTY/`-p`, and a
  tmux pane *is* a TTY (reproduced: a clean `shannon -p` hung 240s on "Do you trust this folder?",
  zero stdout); (2) the detached tmux session survives its launcher's death, so a killed worker
  *silently strands* finished work in an orphaned pane (observed: 2+ leaked `shannon-*` sessions).
- **The real fix (not `claude -p`).** Harden the interactive-tmux worker, keeping OAuth billing:
  (a) pre-seed Claude's first-run gates (`hasTrustDialogAccepted` etc.) in `~/.claude.json` for the
  work-dir, atomic+locked against concurrent writers; (b) make capture **file-based** + deterministic
  tmux session teardown (`finally`/`atexit`/signal) + an orphan janitor; (c) add staleness-based
  `active_step` recovery in megaplan-core so a dead worker → retry/fail, not eternal freeze. Sized
  `partnered/full/medium @codex +prep` — run on **Codex** (you can't build the Shannon fix on Shannon).

- **"Quality regresses" — UNPROVEN, likely tolerable.** Claude/Codex critique is bundled today, true.
  But **Hermes already isolates checks and that is the default robustness path** — strong evidence
  the interaction-reasoning loss is acceptable, and bundling has its own failure mode (dilution
  across 4–8 asks in one prompt). Treat as a thing to *measure*, not a settled regression.
- **"Don't build / YAGNI" — overridden by roadmap authority.** "No user filed an issue" is weak
  against platform work; the forcing function is the owner's stated "we'll need this repeatedly."

**Refined recommendation (supersedes §5 phasing):**
1. **Ship the minimal dedup now (~1–2 days, Hermes-side, zero new abstraction):** extract
   `_merge_unique` → `_core`; a shared `_scatter_gather_hermes_checks(checks, run_one_fn, reduce_fn,
   *, max_concurrent)` that both `run_parallel_critique` and `run_parallel_review` call; and a
   `_with_429_openrouter_fallback(...)` wrapper.
2. **Land the Shannon-hardening sprint** (see ⚠️ CORRECTION above) — *not* a headless `-p` worker.
   This is a prerequisite for any Claude-backend `run_oneshot`, and it fixes the production wedge
   (Claude-vendor megaplan runs silently strand on a killed driver). `partnered/full/medium @codex +prep`.
3. **Keep the two-API direction (`fan_out` / `compete`) live** on roadmap authority — but build it
   only after (2) lands and the read-side dedup has shaken out the shared harness shape. Note Claude's
   `run_oneshot` must ride hardened-interactive-Shannon (OAuth billing), not `claude -p`.
4. **Real residual risks to carry (panel was right):** no 429 retry on CLI paths; deeper-than-"small"
   Codex `state` coupling; `faults.json` fold is last-write-wins (needs a serial reduce step);
   `_run_parallel_stage` shallow-copies only top-level state. Multi-branch (not single-winner) merge
   needs a post-merge semantic gate before any Phase-4 best-of-N — clean `git apply` ≠ correct.

---

## 0.1 UPDATE 2026-05-30 — blast radius confirmed; first slice bundled into the critique-routing sprint

A 4-agent code-grounded sweep (2026-05-30) made the duplication concrete and surfaced a partial implementation that already exists on a branch. Net: the primitive is needed, the mechanism is proven, and DECIDED — its first real extraction rides the **critique-complexity-routing** sprint (`.megaplan/briefs/critique-complexity-routing.md`), not a standalone Phase-0.

**The Hermes per-unit scaffold is copied 4× (5th counting a re-defined importer), each hardcoding `_import_hermes_runtime()` → fan-out is HERMES-ONLY:**
- `orchestration/parallel_critique.py::_run_check`
- `review/parallel.py::_run_check`
- `review/parallel.py::_run_criteria_verdict`
- `orchestration/prep_research.py::_run_research_child` (+ its OWN duplicate `_import_hermes_runtime` at `:644`) — **NEW fan-out site not in the §1 table below; prep post-dates this brief.**

**The 3 collapse gates that exist ONLY because the runners are Hermes-pinned** (kill the pinning → all three dissolve, unlocking Claude/Codex parallelism at once): `handlers/critique.py:378`, `handlers/review.py:527`, the prep-fanout gates (`prep_research.py:226/613/947`, `profiles/__init__.py:261`).

**Proof-of-mechanism already exists (prep-vendor-agnostic branch, commit 6e536827).** `scatter_over_worker_step` / `_process` (NOT in `_core` — they live prep-local at `orchestration/prep_research.py:240/284`). What it proves and what it lacks:
- ✅ **Genuinely vendor-agnostic** — each unit dispatches via `run_step_with_worker` → claude(Shannon)/codex/hermes (`_impl.py:2552/2589/2601/2645`), not a pinned `AIAgent`. Prep consumes it live (`:970-974`). This is the first empirical proof of Axis A on CLI backends.
- ⚠️ **NOTE — it rides `run_step_with_worker` directly**, contradicting this brief's §2 thesis that `run_oneshot` must be a *separate* stateless contract. The read/vendor-agnostic path worked through the execute-shaped contract anyway (via `read_only=True` + caller-owned output path + ephemeral mode). The `run_oneshot`-vs-`run_step_with_worker` split may be softer than §1's root-cause analysis assumed — at least for the read family. Re-test the separation assumption when extracting.
- ❌ **Pins ONE model per scatter** — the per-unit `resolved_model_spec` mechanism exists (`:252`) but the only caller stamps one model on every unit (`:957-967`). **This is the decisive gap:** critique complexity-routing needs lens-by-lens *different* models in the same scatter. Per-unit model must become a first-class parameter.
- ❌ **Prep-local, prompt/parse hardcoded** — it's a per-unit *adapter*, not a fan-out primitive. Promote the *pattern*, not the function.

**Target shape to lift into `_core`** (smallest form that serves critique's per-lens routing AND prep/review's one-model-per-scatter):
```python
# megaplan/_core/worker_fanout.py
@dataclass(frozen=True)
class WorkerUnit:
    step: str
    resolved: AgentMode          # PER-UNIT agent+model+effort → enables lens-by-lens routing
    prompt: str                  # PER-UNIT prompt (caller's make_prompt(unit))
    output_path: Path
    read_only: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

def scatter_over_worker_step(units, *, state, plan_dir, root,
    parse, reduce, isolation="thread", max_concurrent=None, on_unit_error=None): ...
```
The one load-bearing change vs. the branch: `resolved` + `prompt` + `parse` move into the per-unit `WorkerUnit` (caller varies them per unit) instead of being hardcoded to prep. Critique passes a different `resolved` per lens; prep/review pass the same to every unit.

**DECIDED sequencing (supersedes §5's "Phase 0 standalone" for the immediate path):** extract this `_core` primitive **inside** the critique-complexity-routing sprint (its Block B) — the primitive is born serving its hardest first consumer (per-lens routing), then prep and review migrate onto it as **follow-ups**. The wider epic below (write/WORKTREE isolation, bakeoff re-expression, `compete`) remains future work; only the read-family vendor-agnostic core is pulled forward. Landing the prep-vendor-agnostic branch first still helps (gives the proven `run_step_with_worker` dispatch code to lift + avoids a `prep_research.py` collision), but is no longer a hard blocker since this sprint does the generalization itself.

---

## 0.2 UPDATE 2026-05-31 — runtime extraction, fan-out naming, and follow-up notes

**The proven one-shot shape.** `AgentRequest` / `AgentResult` (the runtime contracts in
`megaplan.agent_runtime`) generalize the pattern that was proven on the prep-vendor-agnostic
branch: `run_step_with_worker(read_only=True, output_path=<caller-owned>)`. That one-shot
call — a stateless read-only worker invocation with a deterministic output path — is what
made the first vendor-agnostic parallel fan-out work. `AgentRequest` captures the same
semantics (agent, mode, model, output path, read_only, prompt, timeout, parse hooks) in a
standard dataclass so injected dispatchers, process fan-out, and future read/write reducers
all speak the same contract.

**Worker fan-out vs. pipeline fan-out.** These are two distinct dispatch layers:
- **Worker fan-out** (`megaplan._core.worker_fanout`) scatters work through
  `run_step_with_worker` — the CLI-backed worker function that drives Claude (via
  Shannon/tmux), Codex, and Hermes. It is *process fan-out*: each unit runs in a
  separate process via `scatter_gather_processes`, with caller-supplied per-unit prompts,
  output paths, parse hooks, and error handlers.
- **Pipeline fan-out** (`megaplan._pipeline.executor._run_parallel_stage`) scatters work
  through a pipeline executor that can invoke any backend via the pipeline's own dispatch
  machinery. It is thread-based and used for pipeline-internal parallelism (panel reviews,
  demo judges). It does not use `run_step_with_worker`.

The two share the scatter/gather *pattern*, but worker fan-out is the proven CLI path,
while pipeline fan-out is the executor path. The naming reflects the dispatch target, not
the reduce strategy.

**The public Claude route is Shannon-backed.** The `claude` agent route in megaplan always
uses the Shannon interactive tmux worker — it does *not* use a headless `claude -p`
subprocess. This preserves OAuth subscription billing (no API-key metering) and ensures
the same Claude Code session machinery (workspace trust gates, tool permissions, file
access) is active for every invocation. The Shannon hardening sprint (see §0) makes this
worker robust against tmux-session leaks and interactive-gate hangs.

**Follow-up notes.**

- **Write fan-out.** The current worker fan-out (`scatter_worker_units`) is read-only.
  A write-capable variant (worktree isolation per unit, `git apply` merge with conflict
  hard-gating) is downstream future work — the read-only core must stabilize first, and
  bakeoff's write-merge machinery (`bakeoff/worktree.py`, `bakeoff/merge.py`) is the
  natural extraction source.

- **Operator diagnostics.** The `FanoutResult` and `GenericScatterResult` types carry
  aggregate cost and token counts. Future operator-facing diagnostics (per-unit latency
  histograms, 429-retry counts, stale-session recovery events) should attach to these
  result types or their metadata dicts rather than inventing a separate telemetry channel.

- **External package publishing.** `megaplan.agent_runtime` is the vendorable boundary
  for external consumers. When published as a standalone package, the public surface is
  exactly `megaplan.agent_runtime.__all__` (contracts + adapter protocols + process
  fan-out aliases). The underlying `megaplan._core.*` modules remain private and may
  change without notice.

- **`megaplan.runtime` vs. `megaplan.agent_runtime` naming.** `megaplan.runtime` is the
  pre-existing internal runtime module (worker dispatch, session plumbing, pipeline
  machinery). `megaplan.agent_runtime` is the *new*, additive vendorable contract surface
  created in this extraction sprint. The two are distinct namespaces: `megaplan.runtime`
  stays internal; `megaplan.agent_runtime` is the public boundary. Do not merge them.

---

Everything below this line is the **original full proposal**, retained for the record.

---

**Goal.** Have **one** primitive for "fan out N agents that each do the same task, then reduce
the results" — usable across **all three backends** (Hermes, Codex, Shannon/Claude), spanning
both the **read** case (each agent investigates, merge findings) and the **write** case (each
agent edits code in isolation, merge branches back). Today this pattern is reimplemented ~5 ways,
Hermes-only where it matters, and the write-merge half is locked inside bakeoff.

**Two framing decisions (driving everything below):**
1. **The unit of variation is three orthogonal axes, not N bespoke implementations:**
   *invoke* (which backend, stateless), *isolate* (shared dir vs worktree), *reduce* (how results
   combine). Every existing fan-out site is one point in that cube.
2. **Critique's pain was never a critique problem.** It was the absence of a stateless per-unit
   invocation contract that works on CLI backends. Fix that contract once and ~5 sites benefit.

---

## 1. The problem: one pattern, reimplemented five ways, and split read-vs-write

The pattern "scatter a task into N independent agent invocations, gather, reduce" appears in:

| Site | Unit | Stateless? | Backends | Concurrency | Reduce |
|---|---|---|---|---|---|
| `orchestration/parallel_critique.py:205` | critique check | yes (but routed statefully) | **Hermes only** (`:59-61`) | threads (`:234`) | flag union `_merge_unique:36` |
| `review/parallel.py:326` | review check | yes | **Hermes only** (`:85`) | threads (`:353`) | flag union `_merge_unique:41` |
| `_pipeline/patterns.py:133` panel_parallel | reviewer | yes | any | via executor | collate by key `:168` |
| `_pipeline/demo_judges.py` | judge | yes (deterministic) | n/a | via executor | `_join_judges` |
| `agent/tools/mixture_of_agents_tool.py:88` | model response | yes | multi-model | `asyncio.gather:297` | aggregator pass |
| `bakeoff/orchestrator.py:33` | **whole plan** | **stateful** | **all** | asyncio+subprocess (`:122`) | judge-pick + git-apply |

Two findings make the case:

- **`parallel_critique.py` and `review/parallel.py` are line-for-line duplicates** — `_merge_unique`
  copy-pasted (`:36` / `:41`), identical agent setup, identical 429-fallback. ~160 lines, twice.
  That is the signature of an un-factored pattern.
- **There is already a partial shared primitive** — `_pipeline/executor.py:_run_parallel_stage:163-201`
  is backend-agnostic, stateless, takes a custom join callable. The pipeline does this *right*.
  Critique/review just didn't use it; they rolled Hermes-only versions instead.

The **write** case (parallel edits → merge branches) exists **only in bakeoff** and is fully
private to it: `worktree.py` (isolation), `merge.py` (two-pass `git apply --check`→apply,
conflict hard-gate, `:55-56`), `judge.py:69` (rank), `comparison.py:39` (assemble). Peter's point:
"write N variants and merge temporary branches back" is a capability we will want *outside*
bakeoff (best-of-N execute, parallel refactors, speculative fixes). It should not be bakeoff-private.

### Why parallelizing critique was "hard" (the root cause)

Critique is a stateless `(plan, repo, one check) → findings` function, but it is routed through the
**execute-shaped** worker contract (`run_step_with_worker:2527`), which carries sessions, persistence,
and fixed I/O paths. The "blockers" are all execute's statefulness leaking in:
shared session key `session_key_for("critique","claude")→"claude_critic"` for all checks (`_impl.py:1778`),
shared prompt file `critique_shannon_prompt.txt` (`shannon.py:271`), shared `critique_output.json`
(`shannon.py:1047`), and the `state["sessions"].setdefault` mutation (`_impl.py:2272`). Hermes is the
only backend that already has a *stateless* invocation shape (`_run_check` spins a fresh `AIAgent`),
which is the entire reason it's the only one that parallelizes.

---

## 2. Target architecture: one fan-out, three axes

```
fan_out(
    units:    list[Unit],          # checks | reviewers | samples | implementation-tasks
    *,
    invoke:   OneShot,             # run_oneshot(agent, prompt, ctx) -> payload   (axis A)
    isolate:  Isolation,           # SHARED (read-only) | WORKTREE (writable fork)  (axis B)
    reduce:   Reduce,              # flag-union | synthesis | judge-pick | git-merge | field-merge (axis C)
) -> Result
```

**Axis A — `run_oneshot`: the missing contract.** A *stateless* per-unit agent call, distinct from
`run_step_with_worker` (which stays the contract for stateful serial iteration, i.e. execute/loop).
No session key, no resume, no fixed filename — the caller owns the output path. The single-check
prompt builders are *already agent-agnostic* (`prompts/critique.py:write_single_check_template:266`,
`single_check_critique_prompt:343`), and both CLI workers already accept `prompt_override`
(`shannon.py:830-841`, `_impl.py:1858-1871`) and already emit the same critique payload that passes
`validate_payload`. So the prompt/schema/parse layer is done; only the *invocation mode* is missing.

**Axis B — isolation.** SHARED = same plan dir, per-unit output path (the read family). WORKTREE =
fork at a pinned SHA, agent writes freely, diff captured (the write family). Both already exist
separately; the primitive makes isolation a parameter, not a fork in the code.

**Axis C — reduce.** Pluggable strategy. Every existing reduce becomes a registered strategy
(inventory in §3). Read-merges and write-merges are just different reducers over the same scatter.

**The payoff:** the `agent_type == "hermes"` gate disappears everywhere at once; Codex and Shannon
get parallel critique *and* review *and* panel review for free; bakeoff's write-merge becomes a
reusable `reduce`, available to any future best-of-N flow.

### What stays *out* of this primitive
- **Execute / loop** — single-agent, serial, stateful by design. Keeps `run_step_with_worker`.
- **Findings stay structured.** Critique writes `critique_v{N}.json` + folds into the append-only
  flag registry `faults.json` (`handlers/critique.py:127`, `flags.py:update_flags_after_critique:161`).
  Do **not** introduce a prose `.md` that agents append to (re-creates the shared-mutable-doc race).
  If a human-readable critique doc is wanted, render `faults.json → critique.md` as a pure projection.

---

## 3. What exists to build on (reuse, don't rebuild)

- **Scatter skeleton:** `_pipeline/executor.py:_run_parallel_stage:163-201` — backend-agnostic,
  stateless, custom join, shallow per-thread state copy (`:194`), already rejects non-thread-safe
  in-process steps (`:177-184`). This is the seed of `fan_out` (SHARED isolation).
- **Stateless Hermes invoke:** `parallel_critique.py:_run_check:47` — already `run_oneshot` in spirit.
- **Single-check prompt/template (agent-agnostic):** `prompts/critique.py:266,343`.
- **Write isolation:** `bakeoff/worktree.py` — `create_worktree:155`, `capture_base_sha:148`,
  `carry_dirty_state_atomic:341`, `remove_worktree:165`, `mark_crashed:179`.
- **Subprocess scatter+gather:** `bakeoff/orchestrator.py` — `asyncio.create_subprocess_exec` +
  `asyncio.gather:122`, `_wait_profile:267`.
- **Reduce strategies already in tree:**
  - flag set-union — `flags._merge_unique` / `update_flags_after_critique:161`
  - git-apply branch merge (conflict hard-gate) — `bakeoff/merge.py:32,105`; doc-copy — `:70`
  - judge rank-and-pick — `bakeoff/judge.py:69`, `comparison.py:39`
  - field-merge (last-write-wins by id) — `execute/merge.py:_merge_validated_entries:244`

---

## 4. What's net-new

1. **`run_oneshot` per backend** (the keystone):
   - **Hermes** — wrap existing `_run_check` logic behind the contract. ~free.
   - **Codex** — sessionless mode: don't touch `state["sessions"]`, accept caller output path
     (already uses unique tempfile `:1888`, ephemeral `:1985`). Small.
   - **Shannon/Claude** — a **headless one-shot door** that bypasses tmux entirely (effectively
     `claude -p <prompt> --output-format json`), no readiness handshake (`:964`), no shared prompt
     /output files. **This is the hard part and the unlock for all CLI parallelism.**
2. **Generalized `fan_out`** lifting `_run_parallel_stage` to also support WORKTREE isolation
   (folding in bakeoff's worktree create/gather/cleanup) and a pluggable `reduce`.
3. **Reduce registry** — register the five existing strategies behind one interface.
4. **Migration of the read family** onto `fan_out(isolate=SHARED, …)`; delete the ~320 duplicated lines.
5. **Bakeoff re-expressed** as `fan_out(isolate=WORKTREE, reduce=judge-pick+git-apply)` — making
   write-merge a first-class, reusable capability rather than bakeoff-private.

---

## 5. Phasing & sizing

This is **epic-sized** (~3 sprint-sized plans; weeks, per `megaplan-decision`). Suggested order:

- **Phase 0 — contract + cheap backends.** Define `run_oneshot`; implement Hermes (wrap) + Codex
  (small). Prove on one non-Shannon read site. *De-risks the contract before the hard backend.*
- **Phase 1 — Shannon headless door (keystone).** Spike this *first within the phase*; everything
  CLI-parallel depends on it. Highest unknown.
- **Phase 2 — unify the read family.** Migrate critique, review, panel, mixture-of-agents onto
  `fan_out(SHARED)`. Kill the critique/review duplication. Add an explicit **synthesis reduce** to
  recover cross-check awareness lost when checks are isolated (the one real quality risk of
  splitting a single fat prompt into N).
- **Phase 3 — write/worktree generalization.** Extend `fan_out` to WORKTREE isolation; refactor
  bakeoff to ride it. *Do last — bakeoff is load-bearing and high-regression.*
- **Phase 4 (payoff, optional).** New flows fall out as one-liners: best-of-N execute (write N
  implementations, judge, merge winner), juries, multi-sample critique.

---

## 6. Risks & open questions

- **Shannon headless door is the single keystone unknown.** If `claude -p --output-format json`
  can't cleanly produce the critique payload without the tmux session apparatus, Phase 1 balloons.
  Spike it before committing the epic.
- **No rate-limit pool for Claude/Codex.** `key_pool.py` covers only zhipu/minimax/openrouter/
  google/deepseek/fireworks — Claude/Codex have no `acquire_key`/`report_429`. N concurrent CLI
  calls hammer one key with no backpressure. Either add them to the pool or cap concurrency for
  CLI backends. **Open: build the pool, or cap+serialize CLI fan-out?**
- **Quality regression from isolation.** Splitting one fat critique prompt into N independent checks
  loses cross-referencing; the mechanical set-union reduce won't reconcile contradictions. Mitigated
  by the Phase-2 synthesis reduce — but confirm it actually recovers the signal.
- **Bakeoff regression surface.** Re-expressing the only production write-merger on top of a new
  primitive is the riskiest change; gate it behind the proven read-side primitive and keep the
  conflict hard-gate semantics (`merge.py:55`).
- **Open: is the cost/latency win even there for CLI critique?** Shannon's per-call handshake can
  make 4 concurrent fresh sessions *slower* than one bundled call. The unification is justified by
  *de-duplication + capability* (one primitive, write-merge reuse), **not** by CLI critique latency.
  Don't sell it on speed.
