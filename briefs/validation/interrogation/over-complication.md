# Interrogation — Over-complication lens

**Stance:** Full ambition is assumed (planning becomes a discovered module, the SDK is real, a fourth
non-planning tool ships). I am NOT arguing to do less. I am hunting places where the plan introduces MORE
machinery than composability needs — where the abstraction count itself becomes the load-bearing risk.
Every finding below is a "fix the abstraction / re-sequence / collapse a concept," not "cut scope."

---

## BITE 1 (critical) — The "4 drivers" taxonomy is 1 real runtime + 1 real isolation boundary wearing 4 names; `oneshot` is a phantom

**Where:** EPIC:36 (`drivers = graph / loop / process / oneshot`), m3-drivers-state.md:38 ("peer to
`graph`/`oneshot`"), and the code: `_pipeline/executor.py:212 run_pipeline` is the ONLY runtime that exists
today — there is no `Driver` type, no driver taxonomy (`grep -rin driver megaplan/_pipeline/*.py` returns
nothing). `oneshot` is named exactly twice in the entire brief set (EPIC:36 and an m3 aside) — it has no
milestone, no acceptance test, no user, no spec.

**Why it bites:** The plan reifies four *first-class* drivers, but under the lens they are not four peers:

- `graph` = today's `run_pipeline` graph walk. Real.
- `oneshot` = a graph with one node and no edges. It is `graph` with a trivial topology. It earns a name
  only as documentation; as a *runtime* it is `graph`. Keeping it as a first-class driver means a fourth
  discovery surface, manifest value, and contract test for something that is `len(stages)==1`.
- `loop` = m3 itself concedes (m3:44-46) that "graph-sugar `iterate_until` stays for the in-graph self-edge
  case; the loop *driver* is the data-predicate path." So `loop` is **graph-with-a-self-edge plus a data
  predicate that owns the iteration count.** The honest decomposition is: a `graph` runtime + a *loop-control
  node* (the data predicate + max-iters + teardown) that the graph already routes through. The predicate and
  teardown are the real new capability (correct, keep them); making the *runtime* a separate peer driver is
  the over-build. m3:104-111 even argues loop and graph "share one interpreter" — i.e. they are the SAME
  runtime substrate.
- `process` = genuinely different: it is the only one that owns an OS-process / kill-group / OOM boundary
  (m3:104-111, `runtime/process.py:73,110`; `auto.py` watcher). This is a real second runtime.

So the honest count is **two runtime substrates** (in-interpreter walk; subprocess-isolated walk) plus
**control behaviors that compose onto a walk** (loop predicate, oneshot triviality). The plan instead sells
four co-equal "drivers a package plugs into," which forces: a 4-way manifest enum, a 4-way discovery/registry
surface (M6:47-52 "discovery for all drivers"), and the M6 open question "does planning declare ONE driver or
compose process+graph?" (M6:73-75) — a question that only exists *because* the taxonomy split a substrate
choice (isolation: yes/no) from a topology choice (linear/looping/branching) into one flat list of four.

**What it forces (additions, not cuts):**
1. Make the axes explicit and orthogonal in the contract, instead of a flat enum of 4:
   **(a) execution substrate** = `{in_process | subprocess_isolated}` (this is the real graph-vs-process
   distinction and the only one with a crash/OOM semantics difference m3:104 calls "the central tension");
   **(b) topology/control** = the graph plus optional loop-control nodes. A package declares a substrate +
   a graph; "loop" and "oneshot" become topologies expressible on either substrate, not separate runtimes.
2. Either give `oneshot` a real distinct contract + acceptance user, or delete the name from EPIC:36 and the
   m3 aside. A phantom first-class driver with no spec is pure abstraction-count tax that every "discover all
   drivers" surface (M6) must now enumerate.
3. Keep the loop *predicate + teardown + max-iters cap* exactly as M2/M3 spec them — that is the real missing
   capability. Just bind it as control on the walk, not as a fourth runtime peer.

---

## BITE 2 (high) — "State-evolution axis (forward | reversible | event-sourced) behind ONE Store" is three interfaces in a trenchcoat; only two get real backends and the third is honest-by-omission

**Where:** EPIC:36/74 and m3:30-32,61-67. The plan declares a three-value axis behind one `Store`, but
m3:67 and m3:166-167 (anti-scope) admit: "Event-sourced is *declared* on the axis and scaffolded behind the
interface but a thin backend (acceptance only); full event-sourcing is not owed here." And m3:60-67 maps the
axis onto the *existing* `write_plan_state` surface (`_core/state.py:214 PlanStateWriteMode`), which today is
8 forward-only modes (`replace`, `patch-key`, `merge-meta-list`, …).

**Why it bites:** The three values are not three implementations of one honest interface — they are three
*different contracts*:
- forward-only: `write(mode, state)` — last-writer-wins blob surgery, the current `state.json`.
- reversible: forward + `snapshot()->version_id` + `restore(version_id)`. This is a strict *superset* of
  forward-only's surface — two new methods.
- event-sourced: state is a *fold over an append-only log*; `write` is no longer blob surgery, it's
  `append(event)` and reads are projections. That is a fundamentally different mutation contract — M4:39
  itself says planning's last-writer-wins `state.json` and a revisioned/event Store are "**irreconcilable as
  one mutating contract.**" The EPIC's own M4 brief contradicts the EPIC table's "behind one Store."

So "one Store interface" is honest for **forward-only ⊆ reversible** (one is the other plus snapshot/restore),
but event-sourced cannot share the `write_plan_state(mode, state)` shape without the interface degenerating to
the union of incompatible verbs. Declaring a 3-value axis where the 3rd value is scaffold-only (no backend, no
user) means the *interface* must reserve room for a contract the milestone explicitly won't build — the worst
kind of abstraction-count tax: a public seam shaped by a hypothetical.

**What it forces (additions / re-shape, not cuts):**
1. Ship the axis as **two values now** (forward-only; reversible = forward + snapshot/restore) — that IS one
   honest interface, because reversible is a superset. The stress test's actual demands (snapshot/restore for
   solver/bisect, m3:68) need exactly this and nothing more.
2. Treat event-sourced not as a third *value of the same Store interface* but as a **separate Store backend
   with its own contract**, the same way M4 treats dispatch's subprocess-vs-async as two backends that
   deliberately do NOT collapse (M4:37). Name it as a backend the SDK *offers*, behind a `Store` Protocol that
   is honest about it (reads = projection, writes = append) — don't pretend it shares `write_plan_state(mode,)`.
3. Resolve the EPIC-table-vs-M4 contradiction in writing: EPIC:36 says "behind one Store"; M4:39 says the two
   are "irreconcilable as one mutating contract." Pick the M4 framing (interfaces-with-backends) and amend
   EPIC:36, or the M6 reader cannot tell whether `Store` is one contract or a family.

---

## BITE 3 (high) — Gate-consequence parameterization is being built as a 4-case driver-level construct when it is a per-edge lookup the executor already does

**Where:** m3:55-60 + EPIC:73. The plan adds a `{verdict: consequence}` map with four consequences
(`advance | revise_in_place(target) | restore_and_diverge(version) | escalate`) resolved by "the executor's
edge-dispatch (`executor.py:267-305`)." I read `executor.py:267-305`: it ALREADY resolves
`verdict.recommendation` to an outgoing `kind="gate"` edge by recommendation string, and `escalate` is
already a real path (`run_pipeline_with_policy`, executor.py:388). `advance` and `revise_in_place(target)` and
`escalate` are **already expressible as graph edges today** (a gate edge whose target is the next stage =
advance; whose target is the revise stage = revise_in_place; the escalate policy path = escalate).

**Why it bites:** Of the four "consequences," three are already edges on the graph. Only `restore_and_diverge`
is genuinely new — and it is new *only because* it needs the reversible Store from Bite 2. So
"gate-consequence parameterization" as a named, first-class construct is mostly **renaming existing edge
targets into a consequence enum**, adding a parallel routing concept (consequence map) alongside the routing
concept that already exists (edges). Two routing vocabularies for one routing decision is the over-complication:
a builder now has to know both "what edge does the gate emit" and "what consequence does the binding map the
verdict to," and the executor must reconcile them (m3:55 routes "through a builder-supplied map rather than the
hard-wired gate-edge lookup" — i.e. it *replaces* one mechanism's clarity with a second indirection).

**What it forces (additions, not cuts):**
1. Add exactly ONE new consequence — `restore_and_diverge(version)` — as a new *edge kind* (e.g.
   `kind="restore"` peer to the existing `kind="gate"`/`kind="override"` dispatch already in
   executor.py:277-294), routed by the SAME edge mechanism. Then "parameterizing gate consequence" is "the
   builder supplies the edge set," which is already how `critique_revise_gate_loop` works
   (`pattern_topology.py:78-83` emits the 4 recommendation edges). No second routing vocabulary.
2. Keep the verdict-label/consequence decoupling (the real M2 win — verdict strings are app content) but
   express the *binding* as "which edge target does recommendation X point at," not as a separate consequence
   map the executor must consult in addition to edges. The decoupling is honest; the *parallel construct* is
   the over-build.

---

## Cross-cutting note: framework-vs-library

The EPIC's own acceptance #2 (EPIC:84) states the goal in library terms: a package says *"I'm a `graph`
driver, I need `dispatch`+`emit`"* — declarative, the package *asks for* pieces. But the driver/discovery
machinery (M6:47-52 "one discovery surface enumerates all packages AND drivers," `SKILL.md` required-or-fail,
manifest + driver enum) pulls toward a **framework that owns control flow and dictates the package contract**.
The node library (`patterns.py`, `critique_revise_gate_loop`, fan_out, panel) is the genuinely library-shaped
part — callable pieces that compose freely. The risk is that the *driver+discovery+manifest+required-SKILL.md*
envelope grows heavier than the callable pieces it wraps, so a builder pays the framework tax (declare a
manifest, satisfy discovery, name a driver, write a SKILL.md) before they can call a single node. The fix is
to keep the callable node library usable *standalone* (import `select`, `fan_out`, `loop`-control and run them
in your own `main()` with zero manifest/discovery) and treat the package contract as the OPTIONAL
discovery/orchestration layer on top — not the entry fee. That keeps Bite-1's substrates and the node library
as a library, and confines the framework weight to the (real, wanted) discovery tier.
