# Interrogation — STATE & DATA-FLOW lens

**Scope:** How does state/data actually flow between composed SDK pieces in the Arnold plan?
Read against `briefs/pipeline-unification-EPIC.md`, `briefs/epic-pipeline-unification/{m2-deplanning-types,
m3-drivers-state}.md`, `briefs/validation/decision/{interface-feasibility,abstraction-stress-test}.md`,
and the live code (`megaplan/_pipeline/{executor,subloop,types,pattern_dynamic}.py`, `megaplan/_core/state.py`,
`briefs/validation/confidence/a2-concurrency.md`). Ambition fixed at full extraction; findings are
ADD/fix/re-sequence/abstract-differently, never reduce scope.

---

## The actual data-flow model today (ground truth)

There are **two completely different state transports** in the codebase, and the plan adds a third
without unifying the transport contract:

1. **In-process dict** (`graph`/`loop`/`oneshot` drivers). `run_pipeline` (`executor.py:228-305`)
   carries `state: dict[str, Any]` in memory. A Step returns `StepResult.state_patch`
   (`types.py:161-164`); the executor does `state.update(dict(result.state_patch))`
   (`executor.py:257-259`). This is **flat-key last-writer-wins**: a patch key clobbers the prior
   value, no merge, no nesting awareness (`abstraction-stress-test.md:93` confirms there is no
   `accumulate`). Working state lives in RAM; disk is a side-effect.

2. **Disk state.json** (`process` driver, planning's `auto.py`). Each subprocess phase re-reads
   `state.json` fresh from disk (`auto.py:655,761,807,1031`) and writes it back under
   `plan_state_lock` (`state.py:234-245`, cross-process `fcntl.flock`). The parent's in-memory
   executor dict is **invisible** to the child; the only channel is the file.

3. **Store rows** (resident, `store/base.py`) — revisioned/leased/transactional, `expected_revision`
   on every mutator (`base.py:284,316`), `RevisionConflict` (`base.py:89`). Opposite philosophy to (1)/(2).

The seam that reconciles (1) and (2) is `executor-key-merge` (`state.py:361-372`): the executor
passes `executor_owned_keys` (a flat `set[str]`, `executor.py:233,259`) and the merge rule is
"for each owned key, my in-memory value wins; for every other on-disk key, disk wins." This is the
**single most load-bearing data-flow primitive in the whole SDK** and it is a flat-key LWW reconciler
with zero revision, zero nesting, zero typing.

---

## Top bites

### BITE 1 (CRITICAL) — Mixed-driver composition breaks at the state transport seam; `executor_owned_keys` is the silent corrupter

The EPIC's headline composition is "a forward-only producer feeding a reversible search," and M3
explicitly ships `loop`/`process`/versioned-Store as **selectable backends behind one Store**
(`m3-drivers-state.md:30-32,75-77`). But the three transports above do not share a write contract,
and the only bridge — `executor-key-merge` — cannot express a nested/partial write.

Concretely: an in-process `loop` driver mutates `state["frontier"]` in RAM and only flushes the
keys it touched (`executor_owned_keys`, `executor.py:259`). If a composed `process`-driver step (a
subprocess) ALSO writes `state.json` and touches a *sub-field of a dict the loop owns*, the merge at
`state.py:361-372` resolves at the **top-level key granularity only**: if `"frontier"` is in
`executor_owned_keys`, the subprocess's nested edit to `frontier` is silently discarded; if it is NOT
owned, the subprocess's whole-dict write clobbers the loop's in-memory frontier on the next reload.
There is no revision to detect the conflict (unlike the Store's `expected_revision`, `base.py:284`)
and no deep merge. **The two writers each believe they won.** This is exactly the lost-update class
a2 already found for `chain_state.json` (`a2-concurrency.md:§4` — "last `replace` wins, silently
dropping the other's update"), now promoted into the core driver-composition path.

**What it forces:** M3 must define a **typed, revisioned step-output contract** (a `StateDelta` with
explicit ownership/merge semantics — replace | accumulate | deep-merge — and a version stamp), and
the `executor-key-merge` reconciler must become revision-aware (CAS, not key-set LWW) BEFORE the
`process` driver and versioned Store land, not after. Re-sequence: this contract is a M2/M3 boundary
artifact, but the briefs put the typed-output work nowhere — M2 only de-verdicts `JoinFn`
(`m2-deplanning-types.md:40-51`), it does not type the *state delta* that flows between steps.

### BITE 2 (CRITICAL) — `snapshot`/`restore` (reversible) cannot compose with the `process` driver or with fan-out, because the snapshot does not capture the live frontier of those transports

M3 ships `snapshot(store)->version_id` / `restore(version_id)` as whole-`state.json`-blob copies
under the per-plan lock (`m3-drivers-state.md:64-66,90-92,98-100`). But a reversible search composed
with the other backends has state that is NOT in `state.json`:

- A `process`-driver subprocess that is mid-flight has uncommitted work in its own OS process; a
  `restore()` of the parent's state.json blob does nothing to roll back what the child already did
  on disk/filesystem (file edits, git state). The EPIC's own load-bearing acceptance toy is a
  backtracking solver / mini-bisect (`m3-drivers-state.md:68-71`) — and bisect's whole point is that
  the world it mutates (a git checkout) is OUTSIDE state.json. `restore` rolls back the *bookkeeping*
  but not the *world*. Attestation-vs-oracle (`abstraction-stress-test.md:78-82`) is deferred to M4,
  so M3's reversible toy has no way to roll back the side-effects it measures.
- Fan-out runs children on a **copy** of parent state (`subloop.py:83`, `executor.py:202`) and
  promotes only namespaced keys + artifacts. A `snapshot` taken in the parent does not see in-flight
  shard state; a `restore` cannot un-launch a shard. The briefs acknowledge the budget half of this
  (`m3-drivers-state.md:93-97`, "flag, don't solve") but the **reversibility half is unflagged**: a
  reversible search that fans out has no defined snapshot boundary.

**What it forces:** M3 must define what a snapshot's *boundary* is — explicitly "bookkeeping state
only; side-effects to the world are out of scope unless the driver is `process`+oracle with a
declared undo" — and must REQUIRE that the reversible backend declares whether it is composable with
`process`/fan-out at all, failing loud (not silently rolling back half the world). Add a
`restorable_boundary` declaration to the Store-evolution axis. Without it, the M3 acceptance toy
(backtracking solver) will pass on pure-in-memory state and the gap stays invisible until a real
builder composes restore with a subprocess — exactly the "forward-only producer feeding a reversible
search" the EPIC promises.

### BITE 3 (HIGH) — The loop predicate's input contract names a channel (`last_fanout_results`) that no piece produces; everything is an untyped dict + artifact files

M2 and M3 both specify the loop predicate as `Callable[[LoopContext], bool]` over
`{state, last_fanout_results, budget, iteration}` (`m2-deplanning-types.md:71`,
`m3-drivers-state.md:21,39`). **`last_fanout_results` does not exist anywhere in the code**
(`grep` across `megaplan/` returns only the three brief lines). Fan-out results today flow ONLY two
ways: (a) the `join` callable collapses them in-process and returns one `StepResult`
(`types.py:219`, `executor.py:209`), or (b) children write artifacts under `plan_dir` and downstream
steps **re-read them off disk** (`subloop.py:28-30` says exactly this: "Downstream handlers that need
to observe child results should read them from on-disk artifacts ... not from in-process state").

So the loop driver's predicate is being promised a typed in-memory results channel, but the actual
data-flow is "stringly-typed dict keys + go read the files." There is **no typed step I/O contract**:
`StepResult.outputs` is `Mapping[str, Path]` (existence-checked only, `executor.py:137-143`),
`state_patch` is `Mapping[str, Any]`, and the documented integration pattern is artifact round-trips.
A composed pipeline where step B consumes step A's structured output has no compile-time or runtime
contract that A produced what B expects — it discovers the mismatch as a `KeyError` mid-run or a
silently-stale artifact.

**What it forces:** M3 (or a re-sequenced M2) must (a) actually build the `last_fanout_results`
channel as a typed value the fan-out join writes and the loop driver reads (not an artifact
round-trip), and (b) introduce a **typed port contract** on Step — declared input keys/types and
output keys/types — so composition can be validated at wire time. The plan's generative-reduce →
`dynamic_fanout` spec channel (`m2-deplanning-types.md:62-65`, `pattern_dynamic.py:52,148`) is the
ONE place a typed inter-step value exists; generalize that into a first-class port contract rather
than leaving every other hand-off as untyped dict + files.

### BITE 4 (HIGH) — Budget/accumulate are declared per-run and single-process, but the loop predicate that reads them composes with fan-out, which copies state per shard — the resource is unobservable across the very topology that needs it

M3 ships `budget` (depletable, read by loop predicate + escalate) and `accumulate` as Store ops
(`m3-drivers-state.md:30-32,61-67`), explicitly **single-process / single-tenant**
(`m3-drivers-state.md:113-116`, "NOT a cross-tenant quota broker"). But the abstraction-stress-test's
own driving examples (bounty market, red/blue, genetic) need budget/accumulate to span fan-out shards
(`abstraction-stress-test.md:54-65,90-94`), and fan-out runs each shard on a `dict(ctx.state)` copy
(`executor.py:202`, `subloop.py:83`) whose mutations do NOT flow back except via namespaced keys.

A loop that fans out N shards, each consuming budget, cannot see the aggregate spend: shard mutations
to `state["budget"]` evaporate at the copy boundary. The briefs flag this for budget
(`m3-drivers-state.md:93-97`) but ship budget anyway as a loop resource the predicate reads — so the
**M3 budget predicate is correct ONLY for non-fan-out loops**, i.e. exactly the forward-only shape
the EPIC is trying to escape. `accumulate` has the same defect: a monotonic corpus grown inside
shards (`abstraction-stress-test.md:90-94`, red/blue survivors) cannot accumulate across siblings
because there is no fold channel back to the parent.

**What it forces:** the fold/accumulator channel (`abstraction-stress-test.md:182`, "a shared-
accumulator channel distinct from the per-result join") is NOT optional M-fanout work — it is a
**prerequisite for budget/accumulate to be meaningful in a loop that fans out**, which is the headline
non-planning composition. Either M3 ships a fold channel for budget/accumulate, or M3 must hard-fail
when a budget-reading predicate is composed with a fan-out body (declare the incompatibility loud,
don't silently under-count).

---

## Single biggest MISSING ABSTRACTION

**A typed, revision-bearing inter-step data contract — a `StateDelta`/port type with explicit merge
semantics (replace | accumulate | deep-merge) and a version stamp — that is the SAME across all three
transports (in-process dict, disk state.json, Store rows).** Today there is none: `state_patch` is
`Mapping[str, Any]` applied LWW (`executor.py:257`), the cross-transport bridge is a flat key-set
(`executor_owned_keys`, `state.py:361-372`), and the documented hand-off between composed pieces is
"read the artifact file" (`subloop.py:28-30`). Without this, "pipelines that MIX state-evolution
models compose" is asserted, not engineered — every mixed composition reconciles through a flat-key
LWW merge that cannot represent partial/nested/accumulating/revisioned writes. This abstraction is the
thing that makes a forward-only producer's output safely feed a reversible search; the plan needs it
and never names it.

## Biggest OVER-COMPLICATION

**Three state transports kept fully distinct while claiming "one Store interface."** The plan
correctly refuses to force planning's `state.json` into the revisioned Store
(`interface-feasibility.md:171-178`, the call is "artifact-blob altitude only") — that is right. But
then M3 asserts `snapshot/restore`, `accumulate`, `budget`, and the evolution axis all live "behind
ONE `Store` interface" (`m3-drivers-state.md:30-32,61`). You cannot simultaneously have (a) one Store
interface and (b) three irreconcilable transports where the bridge is a key-set LWW merge. The
over-complication is the *pretense of unification*: it forces the merge reconciler to grow a
write-mode for every cross-transport case (`state.py:214-223` already lists EIGHT write modes:
replace / executor-key-merge / patch-key / patch-many / active-step-heartbeat / merge-meta-list /
legacy-migration / copy-time-rewrite). Adding snapshot/restore/accumulate/budget as more write-modes
on this same blob-surgery API will push it past ten. The honest abstraction is fewer transports with
a real delta contract (the missing abstraction above), not one interface papering over three.

## Biggest OVER-SIMPLIFICATION

**"snapshot = copy the whole state.json blob" (`m3-drivers-state.md:90-92`) treats reversibility as a
bookkeeping-only concern.** The open question literally answers itself with "pick whole-blob"
(`m3-drivers-state.md:92`) — but the EPIC's own acceptance toys (backtracking solver, mini-bisect,
`m3-drivers-state.md:68-71`) are valuable PRECISELY because they mutate a world outside the blob (a
solver's tentative assignments may touch files; bisect checks out git revisions). A whole-blob
snapshot rolls back the *record of* the search but not the *search's side-effects*, and M3 defers the
oracle/`run(cmd)` machinery to M4 (`m3-drivers-state.md:160-162`) — so M3's reversible acceptance toy
can only ever exercise pure-in-memory rollback, which is the one case that would never surface the
gap. The simplification makes the acceptance test pass while leaving the actual composability claim
("reversible search over real side-effects") untested.
