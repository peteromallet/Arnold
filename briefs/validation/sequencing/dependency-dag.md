# Arnold — Build Sequence under the PURE DEPENDENCY-DAG lens

**Lens:** topologically-correct order. I ignore risk appetite, politics, and "how hot is the file."
I sequence strictly by *what must technically exist before what*. I build the hard prerequisite graph
among the 7 reshapers and 11 organs, find the longest chain (the critical path), and surface everything
that parallelizes off a common prerequisite. This is the skeleton; the risk-lens and the strangler-lens
bend it but cannot reorder a hard edge without breaking the build.

This is ONE of three independent orderings to be reconciled. I am decisive, not hedged.

---

## 0. Method — how I derived the hard edges

A dependency edge X → Y exists iff Y *cannot be correctly built/enforced* without X already in place —
i.e. building Y first would either (a) require re-touching X's substrate (a retrofit, not an addition),
or (b) silently produce a wrong result that no test of Y alone can catch. Soft edges ("nicer if X first")
are excluded. The reshapers (R1–R7) and organs are the *nodes*; the m1–m7 briefs are the *vehicles* that
carry them, re-aimed here onto the organ graph rather than the pre-architecture milestone framing.

The single most important structural fact, stated by the committed-UU synthesis and unarguable: **R1
(state = deterministic fold over an append-only, effect-typed, taint-carrying event log) is the universal
root.** Eleven organs all *record into* or *are folded from* the log. If R1 is built late, every organ
built before it is a retrofit against a substrate whose authority arrow points the wrong way. So R1 is
not "milestone 1 of N peers" — it is the floor the entire DAG stands on, and the longest chain necessarily
begins at it.

---

## 1. The node inventory (7 reshapers, 11 organs) and what each hard-requires

### Reshapers
- **R1 — Event-log foundation** (WAL authoritative; state.json a cache; effect-typed; taint-carrying).
  Hard-requires: nothing. *Universal root.*
- **R2 — Activation is the scheduler primitive** (pluggable readiness rule + lifecycle). Hard-requires:
  R1 (an Activation's lifecycle transitions ARE log events; its identity is a hash over node+input-ports+
  profile, which presumes the hashing/log substrate).
- **R3 — Port runtime-enforced, taint-lattice-in-the-hash, typed declassification edge.** Hard-requires:
  R1 (taint must live *inside* the content-hash that keys the log/cache; retrofitting taint after values
  share a store is the unrecoverable cache-collision-launders-taint failure — SYNTHESIS UU#4).
- **R4 — Tree-scoped Governor + linearizable Capacity-Lease** under the scheduler / over the key pool.
  Hard-requires: R2 (you cannot scope a budget to a *tree of activations* until activations are
  first-class, supervised, and parent/child-linked) AND R1 (lease state + spend accrual are folded from
  the log; fencing tokens fail the NEXT WRITE, which presumes the log is the write).
- **R5 — One Ledger, recorded-into never recomputed-from.** Hard-requires: R1 (the Ledger IS the single
  append-only log discipline; "two journals = no spine"). R5 is less a separate build than the *enforced
  discipline* on R1 extended to every world-fact — but it has its own edge: it cannot be enforced until
  the Conveyance/Envelope (organ) exists to *carry* lineage/provenance so the runtime EMITS lineage as
  Ports cross, rather than reconstructing it with a phase-name if-ladder.
- **R6 — Manifest is the object the content-hash points at** (behavioral closure). Hard-requires: R3
  (the closure includes the Port set + ABI), R2 (topology of activations + readiness), and the Effect/
  Contract organs (the closure includes routing-taken + dep-closure). It is the *latest-binding* reshaper:
  it can only fingerprint a closure once all the things in the closure are first-class.
- **R7 — Model-identity is a hash-pinned provenance fact.** Hard-requires: R1 (it is a recorded fact in
  the log/Ledger) and R3 (it rides the Conveyance/Port provenance field). Cheap to *seed* early (a typed
  field), but only *load-bearing* once the Calibration Ledger queries it.

### Organs
- **Port (data model: kind×content-type×schema, open registry, by-ref blobs)** — the spatial socket.
  Hard-requires: R1 (artifact kind = by content-hash reference into the log/blob store; value kind lives
  inline in the log). Port is R3's vehicle. **Keystone organ #1.**
- **Conveyance / Work-Envelope** — the temporal half: conserved run-context (taint-lattice + cost +
  lineage + deadline + cancel + error-class + retry-budget) on every edge. Hard-requires: R1 (it is what
  StepContext/StepResult carry *instead of* leaking through state.json) and Port (taint/provenance are the
  same lattice the Port carries spatially; they are "two faces of one law"). **Keystone organ #2 — the
  most-converged-upon missing noun.**
- **Activation (the scheduler organ)** — R2's vehicle. Hard-requires: R1, Port (readiness rules consume
  input Ports), Conveyance (a firing carries an envelope).
- **Governor + Capacity-Lease** — R4's vehicle. Hard-requires: Activation (tree scope), Conveyance (the
  envelope is what carries the per-subgraph cost charge), R1 (lease/spend folded from log).
- **Effect Ledger** — typed world-acts (replay-class + idempotency-key ≠ hash + compensation).
  Hard-requires: R1 (acts are recorded as typed events), Conveyance (taint/provenance ride the same
  spine), R5-discipline. Must exist *before the first real money/merge/PR is journaled* — so before any
  dispatch organ performs a world-act under the new substrate.
- **Contract Ledger** — the type *system*: admission validator + repair-negotiation + taint-in-cache-key
  + pinned meaning. Hard-requires: Port (it is the registry of Port contracts and legal moves between
  them) and R1 (content-hashed registry). It is Port's *system-level* peer: Port = the socket, Contract
  Ledger = the registry of socket types + coercions. The binder (build-time consumes↔produces resolution)
  is the Contract Ledger's query surface.
- **Calibration Ledger** — CapabilityClaims + decay/exploration; routing = a query. Hard-requires: R7
  (claims are keyed on hash-pinned model-identity), Conveyance (taint-aware aggregation reads the taint
  lattice), the Evaluand/Ledger (a claim's "verdict" is an attributable judgment), Effect Ledger (the
  verifier is a recorded act). Routing-as-a-query presumes the dispatch organ already routes.
- **Evaluand + one Ledger** — versioned attributable judgments; "eval IS the spine." Hard-requires: R1/R5
  (recorded into the one Ledger), Port (a judge is a Port-typed, content-hashed *piece*), R6-seed
  (judge-version/rubric-version are manifest-ish identities). For the self-improving heart this is THE
  spine — it gates the Calibration Ledger (you cannot calibrate against un-versioned scores).
- **Behavioral Identity Manifest** — R6's vehicle. Hard-requires: R3/Port (Port set in the closure),
  Activation (topology), Effect+Contract+Calibration (routing-taken, dep-closure, ABI). Latest organ.
- **Replayable Capsule** — portable exchange unit (Definition + Contract + Lineage + Evidence).
  Hard-requires: Manifest (Definition = the closure), Contract Ledger (the exported recipient-verifiable
  contract), the one Ledger (Lineage + Evidence). It is *operations on* the Manifest + Ledger.
- **Warrant** — signed authority + verified-work + decision-time rationale, shape-independent.
  Hard-requires: Manifest (rationale anchored to the manifest hash), Evaluand (verified-work = an
  attributable judgment), Effect Ledger (the act it attests). Outermost atom; nothing depends on it
  except external consumers. **DAG sink.**

---

## 2. The hard prerequisite graph (edges, terse)

```
R1 ─────────────────────────────────────────────────── (universal root)
 ├─> Port ───┬─> Contract-Ledger ──┐
 │           │                     │
 │           └─> Conveyance/Envelope ──┬─> Activation (organ) ─> Governor+Capacity-Lease
 │                                     │
 ├─> Conveyance ──────────────────────┘
 │
 ├─> Effect-Ledger        (needs R1 + Conveyance)
 ├─> R7 model-identity     (needs R1 + Port-provenance)
 │
 (Port + Conveyance + Activation + Effect + Contract all feed:)
 └─> dispatch/evidence/emit services
        └─> Evaluand+Ledger ──> Calibration-Ledger
                                    │  (also needs R7, Conveyance-taint, Effect)
                                    ▼
        (Port + Activation + Effect + Contract + Calibration + routing-taken) ──> Manifest (R6)
                                    │
                                    ├─> Replayable Capsule
                                    └─> Warrant
```

Key non-obvious edges (the ones a naive ordering gets wrong):
1. **Conveyance must precede Activation-as-organ.** A firing record is empty without the envelope it
   carries; build Activation first and you immediately retrofit the envelope into it. The synthesis calls
   them peers, but the *envelope dataclass* is the simpler, lower noun and the Activation references it.
2. **Port precedes Conveyance.** Taint/provenance are ONE lattice that has a spatial face (Port) and a
   temporal face (Conveyance). The lattice type + the by-ref blob/value/stream `kind` discrimination are
   defined with the Port; the Conveyance reuses them. Building Conveyance first means inventing the taint
   lattice in the temporal layer and then re-conciling it with Port's hash — a retrofit into the cache key.
3. **Evaluand precedes Calibration.** A CapabilityClaim's outcome is "verdict by judge-version vs
   rubric-version" — i.e. an Evaluand. Calibrating against bare floats is the exact Goodhart/co-degradation
   failure (SYNTHESIS UU#2, #10). So the eval-spine is a hard prerequisite of the routing-flywheel, not a
   sibling. This is the edge most plans get backwards (they build routing first because it "feels core").
4. **Contract Ledger is Port's system-peer, gated AFTER Port but it gates the binder.** The build-time
   `consumes↔produces` resolution (kills the `step_helpers.py:104` silent `v1.md` fallback) is a *query
   against* the Contract Ledger. So: Port (the value) → Contract Ledger (the registry of types + legal
   moves) → binder (the resolution). M1's `pipelines check` graph-linter is a *degenerate* binder that
   only checks edges/reachability — a legitimate down-payment, but the *typed* resolution is gated on Port.
5. **Manifest is genuinely last among the foundational organs**, because its content is the *closure of
   everything else*: it cannot fingerprint routing-taken until routing exists (Calibration), nor the
   dep-closure until pieces are content-hashed (Port + Contract), nor the topology until Activation is
   first-class. Building it early gives you the dead `pipeline_version:int` field — identity theater.
6. **Capsule and Warrant are pure sinks** off the Manifest + Ledger; they add no new substrate, only
   project + sign. They can be the very last things built and nothing waits on them.

---

## 3. The topologically-correct build order (decisive)

Each step lists the reshaper/organ it lands, its hard prerequisites, and what runs in parallel off the
same prerequisite. I map each onto its milestone vehicle (m1–m7) where the briefs already carry it, and
flag where the briefs' ordering must be *corrected* to respect a hard edge.

### Tier 0 — the root (must be first, nothing parallel above it)
**S0. R1 — Event-log foundation + the hygiene/contract-checker down-payment.** (Vehicle: M1.)
The append-only effect-typed taint-carrying log becomes authoritative; `state.json` is re-cast as a
*derived cache* (fold). In M1's vehicle this is the seed: schema_version stamp + migrate-before-validate +
the `extra="ignore"` back-compat corpus + the degenerate `pipelines check/doctor` linter (edges/
reachability/gate-coverage only — NOT typed Port resolution, which has no Port type yet). The
*authoritative-log* property is the load-bearing part; the linter is the tool that keeps every later
edge-adding milestone from mis-wiring. **Prereq: none.** **Parallel: none above it** — this is the floor.

### Tier 1 — the spatial/temporal spine (the keystone), off R1
**S1. Port + Contract-Ledger + binder + StateDelta (CAS), with R3 taint-lattice-in-the-hash, and the
de-planning type decoupling.** (Vehicle: M2.)
Port = (kind ∈ {value,artifact,stream} × content-type[open MIME registry] × schema). artifact = by
content-hash reference into the R1 store; value = inline in the log. Taint enters the content-hash here
(R3) — *before any untrusted value shares the store*, which is the only non-retrofittable moment. The
Contract Ledger is the content-hashed registry of Port contracts + legal coercion moves; the binder
resolves `consumes↔produces` at build time (fails `build()` on missing/mistyped dep, kills the
`step_helpers.py:104` silent fallback). StateDelta (replace|accumulate|deep-merge + version, CAS not flat
LWW) replaces `executor_owned_keys`. The 4-verdict `GateRecommendation` is evicted from SDK types to the
planning app under a **CI ZERO-`GateRecommendation` grep gate** (partial conversion is worse than none —
a half-converted enum re-planning-izes every downstream driver, BITE 3). `select()`/`Reduce[T]` land as
structured data; the dropped `iterate_until` predicate is wired.
**Prereq: S0 (R1).**
**Parallel off R1:** R7 model-identity *seed* (a typed provenance field, no consumer yet) and the
Effect-Ledger *type skeleton* (replay-class enum + idempotency-key field) can be drafted in parallel — but
NOT enforced until they have a value/act to carry (taint lattice from Port, acts from dispatch). Keep them
as seeded fields landing alongside S1, not as separate critical work.

**S2. Conveyance / Work-Envelope** — the conserved run-context dataclass. (Vehicle: split across M2 tail /
M3 head — the briefs under-name this; it must be explicit.)
`StepContext`/`StepResult` carry a typed `RunEnvelope` (taint-lattice [joined at every merge, per-Step
transfer functions] + cost-ledger + lineage + deadline + cancellation-token + error-class + retry-budget)
*instead of* leaking through `state.json` and `repr(exc)`. Reuses Port's taint lattice (the temporal face
of the same law).
**Prereq: S1 (Port — for the shared lattice + the value kinds).**
**Parallel:** none load-bearing; it is on the critical path because Activation needs it.

### Tier 2 — the scheduler primitive + its safety regulator, off the spine
**S3. R2 — Activation as the scheduler primitive: drivers + realized-graph + state-evolution axis.**
(Vehicle: M3.)
The 2-axis driver model (substrate `in_process|subprocess_isolated` × topology `graph`, loop-control as a
node). The **topology-realizer** `build_topology(run_config)->Graph` — the single source both `next_step`
projection and reverse-recovery maps query — re-invocable mid-run. The Activation is the persisted,
supervised firing record with a pluggable readiness rule (today only "upstream done", but named now so
loop/standing/market/emergent are one field later). Its identity = hash over node + input-Ports + profile
(needs Port). State-evolution = forward-only | reversible(`snapshot`/`restore` with `restorable_boundary`
that fails LOUD under process/fan-out) | event-sourced-as-separate-backend. The cloud `_phase_command`
shim is born here with the process driver (the briefs assign it here; the DAG agrees — it is the substrate
seam).
**Prereq: S1 (Port), S2 (Conveyance), S0 (R1 — transitions ARE events).**
**Parallel off S1/S2:** S4 below shares the prerequisite set but has its own edge from Activation, so it
is *downstream* of S3, not parallel-with. However, the **dispatch/emit/evidence services (S5)** depend on
Conveyance + Effect-Ledger but NOT on the realized-graph — so S5's *interface* design can proceed in
parallel with S3's realizer once S2 lands. (The briefs serialize M3→M4; the DAG says M4's service
*interfaces* can start against S2, only their *governor wiring* waits on S3.)

**S4. R4 — Tree-scoped Governor + linearizable Capacity-Lease.** (Vehicle: M4, the policy-spine half.)
Sits *under* the scheduler (S3) and *over* the key pool. Tree-scoped recursion/cost/fan-out/concurrency
budget charged per-subgraph against a fixed pool (the "conserved currency / ATP" — SYNTHESIS UU#8); the
distributed face is the Capacity-Lease: one linearizable arbiter (`fcntl.flock`'d ledger) with fencing
tokens that fail the NEXT WRITE. ONE live budget authority folding across fan-out shards (natural home =
the key/rate broker — rate & spend are one shared-depletable-resource problem).
**Prereq: S3 (Activation — for tree scope), S2 (Conveyance — carries the per-subgraph charge), S0 (R1).**
**Parallel:** with S5's non-governor services (dispatch/emit/evidence) — same M4 milestone, separable PRs.

### Tier 3 — services + the ledgers that record acts and judgments
**S5. Services: dispatch (2 backends) + emit (one EventSink contract) + evidence (attestation + oracle/
`run(cmd)`) + config-precedence resolver + the RecoveryPolicy spine + composition-observability contract +
the Effect Ledger made load-bearing.** (Vehicle: M4.)
`emit` = one `EventSink.emit(kind,payload,scope)` contract resolving the two-disjoint-journals problem
(SYNTHESIS UU#14 / R5) — this is where R5 ("one Ledger, recorded-into never recomputed-from") becomes
real, because emit is the single write path. The **Effect Ledger** is enforced HERE (before the first real
money/merge/PR is journaled under the new substrate): every dispatch/world-act carries a replay-class +
external idempotency-key (≠ content-hash) + declared compensation. `RecoveryPolicy.classify(error)->
{retry_fresh|retry_transient|escalate|halt(kind)}` extracts auto.py's brain. Re-home introspect/doctor/
trace/cost onto the observability contract.
**Prereq: S2 (Conveyance — services carry the envelope), S4 (Governor — dispatch acquires under the
lease), S1 (Contract Ledger — emit/dispatch results are Port-typed), S0/R5 (one log).**
**Parallel:** S5 splits into dispatch ∥ emit ∥ evidence ∥ config ∥ recovery-policy — five PRs off the
M3/M4 base, gated together on the observability contract.

### Tier 4 — the node library + execute realm (the composition vocabulary), off services
**S6. Node library (`patterns` as composition vocabulary).** (Vehicle: M5a, F1/F3/F9.)
Formalize produce/judge/gate/revise/fan_out/escalate/clarify/verify/loop_until + select/reduce as the
vocabulary, provisional tier, checker-readable registry.
**Prereq: S1 (Port-typed I/O), S5 (emit/dispatch the patterns call).**
**Parallel:** with S7 below until F4→F5's tier-resolution edge.

**S7. Execute realm: F4 complexity-tiering → F5 task-DAG scheduler.** (Vehicle: M5b.)
F4 (tier resolution) is the *input contract* to F5 (the batch scheduler resolves per-batch tier→model via
F4's capability — BITE 1). F5's reducer returns **app-defined outcomes** (typed `Reduce[T]`, binding maps
to phase_outcome). **Hard internal edge: F4 before F5.**
**Prereq: S5 (dispatch — F5 schedules dispatches), S6 (node-lib — F5 is a composition).**
**Parallel:** S6 ∥ S7-F4 off S5; F5 waits on F4.

### Tier 5 — the eval spine, then the calibration flywheel (the order most plans invert)
**S8. Evaluand + one Ledger — versioned attributable judgments.** (Vehicle: cross-cuts M4/M5; named
explicitly here because the organ briefs under-carry it.)
The judge becomes a Port-typed, content-hashed, versioned *piece*; a score = a join over (piece-version ×
rubric-version × judge-version × input-set), never a bare float. Recorded into the one Ledger (S5/R5).
**Prereq: S1 (Port — judge is a piece), S5/R5 (the one Ledger), S6 (verify/judge nodes).**
**Parallel:** with S7 — both off S5/S6.

**S9. Calibration Ledger — CapabilityClaims + decay/exploration; routing = a query.** (Vehicle: later
M5 / cross-cut, after dispatch + eval.)
The 1–5 tier score and `tier_models` become *projections*; routing becomes a query. DECAY/CHURN +
EXPLORATION BUDGET (off-policy fraction so the loop can't ratchet) + TAINT-AWARE AGGREGATION.
**Prereq: S8 (Evaluand — a claim's verdict IS an attributable judgment; calibrating on bare floats is the
Goodhart failure), R7 (model-identity — claims key on pinned weights), S2 (Conveyance taint), S5 (dispatch
must route before routing can become a query).** **This is the most order-sensitive edge in the whole DAG.**

### Tier 6 — the control plane + supervisor (top of the runtime, off services + execute)
**S10. Control plane: run-outcome vocabulary + control interface.** (Vehicle: M5c — last/hardest of M5.)
`{succeeded, failed, escalated, blocked, awaiting_human}` + `valid_targets(state)`/`recover_targets(state)`;
the control trio `(read_valid_targets, apply_transition, synthesize_artifacts)` the binding IMPLEMENTS.
Evict planning's `STATE_*` from the control plane (the SDK-vs-app edge — the most-violated boundary).
**Prereq: S5 (RecoveryPolicy spine — control fires general control ops), S7 (execute outcomes feed the
run-outcome vocabulary), S3 (set-robustness mid-run re-realizes the topology).**

**S11. Supervisor tier (general cross-run orchestration).** (Vehicle: M5d, F8.)
Chain/epic/bakeoff become bindings invoking general control ops (not "force-proceed" by name). Acceptance
= a throwaway canary epic (the real epic's frozen old engine cannot exercise it — B2).
**Prereq: S10 (invokes general control ops), S3 (the process driver it drives — F8 sits on top of the
single-planning-run driver), and the M6 trust/relocation work for the package it supervises.**

### Tier 7 — relocation, trust boundary, identity, exchange (the strangler swap + the sinks)
**S12. Megaplan as a discovered module + `arnold` namespace + trust boundary + R7 made load-bearing.**
(Vehicle: M6.)
Relocate planning; drop `_BUILTIN_NAMES`; manifest + driver + bindings + SKILL.md; **manifest-first
non-executing discovery + trust tier + `arnold_api_version`**; collapse the next-step encodings (now safe
— S3 proved the projection faithful). Re-point the cloud `_phase_command`/`supervise.py` couplings off
auto/chain internals (BITE 2 — nobody else owns this; the DAG assigns it here). resident adopts the pieces.
**This is the deferred strangler swap — LAST among load-bearing work because the flagship/dogfood engine
must stay intact until everything underneath it is proven.**
**Prereq: S3 (process driver + faithful projection), S5 (services), S7 (execute), S10 (control plane —
planning's STATE_* binds onto it), S11 implied for supervisor relocation.**

**S13. R6 — Behavioral Identity Manifest.** (Vehicle: cross-cut, post-M6; the organ the content-hash was
built to point at.)
Hash the behavioral closure (topology + step-code hashes + prompt *bodies* + routing-taken + Port set +
ABI version + resolved dep-closure). Resume = pin/refuse/migrate-via-codemod against the live def.
**Prereq: S12 (pieces are relocated + content-hashed), S9 (routing-taken is recorded), S3 (topology), S1
(Port set + ABI).** Latest foundational organ — its content is the closure of everything above.

**S14. Replayable Capsule** (Definition+Contract+Lineage+Evidence) — projection over Manifest + Ledger.
**Prereq: S13 (Manifest = Definition), S1 (Contract Ledger = exported contract), S5/R5 (Lineage+Evidence).**

**S15. Warrant** (signed authority + verified-work + decision-time rationale, shape-independent).
**Prereq: S13 (rationale anchored to manifest hash), S8 (verified-work = attributable judgment), S5 (the
act it attests).** **DAG sink — nothing internal depends on it.**

**S16. Builder docs & onboarding.** (Vehicle: M7.) Generated-from-types reference; external-builder ships
the select-tournament from docs+scaffold alone.
**Prereq: S12 (the relocated, composition-shaped planning + the namespace it documents).** A sink alongside
S14/S15.

---

## 4. The critical path (longest chain)

```
R1 (event-log)                                                      [S0 / M1]
 → Port + Contract-Ledger + taint-in-hash (R3)                      [S1 / M2]
 → Conveyance / Work-Envelope                                       [S2 / M2-M3 seam]
 → Activation primitive + realized-graph + drivers (R2)             [S3 / M3]
 → Governor + Capacity-Lease (R4)                                   [S4 / M4]
 → dispatch/emit/evidence services + Effect-Ledger + RecoveryPolicy [S5 / M4]
 → Execute realm F4→F5                                              [S7 / M5b]
 → Evaluand + one Ledger                                            [S8]
 → Calibration Ledger (routing = a query)                           [S9]
 → Control plane (run-outcome vocab + control interface)            [S10 / M5c]
 → Megaplan-as-module + trust boundary + cloud recoupling           [S12 / M6]
 → Behavioral Identity Manifest (R6)                                [S13]
 → Warrant (signed authority + verified work)                      [S15]
```

13 hops. This is the spine the other two lenses bend around. The path is forced at every edge by a
"cannot-build-Y-without-X" relation, not a preference. Note the two edges most commonly inverted:
**Conveyance before Activation** (S2→S3) and **Evaluand before Calibration** (S8→S9).

## 5. What parallelizes (off a common prerequisite — pure fan-out)

- **Off R1 (S0):** R7 model-identity *seed*, Effect-Ledger *type skeleton*, the back-compat corpus, the
  degenerate `pipelines check/doctor` linter — all land alongside/right after S1 without waiting on each
  other.
- **Off S3+S2 (post-Activation, post-Conveyance):** the M4 service *interfaces* (dispatch/emit/evidence/
  config) can be designed in parallel with the Governor (S4); only their lease-wiring waits on S4.
- **Off S5 (services):** S6 (node-lib) ∥ S7-F4 (tiering) ∥ S8 (Evaluand) are three independent fan-out
  branches off the service layer. Within S7, F4→F5 is serial.
- **Off S12 (relocation):** S14 (Capsule), S15 (Warrant), S16 (docs) are three independent sinks — none
  depends on another; S13 (Manifest) gates S14/S15 but not S16.
- **M5d supervisor (S11)** parallelizes with **S12/M6** *only after* both S10 (control plane) and S3
  (process driver) exist — it shares M6's relocation prerequisite for the package it orchestrates.

## 6. The strangler invariant I maintain (the hard constraint, expressed in DAG terms)

**At the close of every step S_i, two things must hold simultaneously, gated automatically:**
(1) the OLD engine still boots and drives a 1-milestone throwaway plan end-to-end (the load-bearing epic
runs on the FROZEN old engine, never on the half-built new pieces); AND (2) a *planning-shaped* throwaway
plan runs on the NEW pieces built through S_i (dual-engine bring-up, not just the non-planning acceptance
toy). In DAG terms: **every node is added as `{old-path default-on, new-path default-off-behind-flag}`,
and the old path's deletion is itself a node that depends on the new path having soaked.** The single
deletion that flips the system — drop `_BUILTIN_NAMES` + relocate planning (S12/M6) — is deliberately the
LAST load-bearing node precisely because it is the only one that *removes* the old path's root. There is
no multi-week broken window because the old path is a live, gated peer of the new path at every node, and
the swap is one atomic, oracle-gated cutover at S12, not a creeping half-deletion across S1–S11.

Autonomy: one t0 human "go" (recorded in EPIC §3-21), then every S_i boundary is machine-gated
(parity + substrate-swap oracles + ZERO-`GateRecommendation`/`STATE_*` grep gates + binder asserts);
red → auto-halt+revert or the bounded escalation ladder, never a human park.

## 7. The biggest sequencing risk MY ordering carries

**The critical path is 13 forced hops with the single highest-risk, fastest-moving extraction (the
Activation/driver port at S3, carrying ~2,500 LOC of auto.py recovery/retry/escalate/resume logic) sitting
at position 4 — and a pure-DAG order gives me no license to de-risk it, only to place it correctly.**

Because I sequence strictly by hard prerequisite, S3 *cannot* move earlier (it needs Port + Conveyance)
nor later (S4–S12 all depend on it). My lens therefore concentrates the build's worst stall-risk at a
fixed, un-movable position on the longest possible chain, and offers no parallel route around it: if S3
slips, S4 through S15 — the entire back two-thirds of the DAG — are blocked, because there is no
dependency-legal way to start any of them without the Activation primitive. The DAG is correct but
*brittle*: it has one long rope and the heaviest knot is un-relocatable on it.

The reconciliation the other two lenses must supply (and which the pure-DAG lens deliberately refuses to
invent) is: **split S3 at its internal seam** — pull the auto.py *behavioral-characterization oracle*
forward as its own dependency-legal node (it depends only on S0/R1 + today's subprocess engine, so it can
land as early as S0 completes, in parallel with S1/S2), so that when S3 executes it is a port against a
green, already-merged oracle rather than a discover-and-port-at-once apex milestone. The pure-DAG lens
*permits* this split (the oracle's only prerequisite is the current engine + R1's log), and flags it as
the one place the skeleton most needs the risk-lens to add a spike node — but it does not, on dependency
grounds alone, reorder anything else.

A secondary risk: the **Evaluand→Calibration edge (S8→S9)** is real but easy for a reconciliation to
"optimize away" by building routing early because it feels core. If routing/Calibration is built before
the versioned eval-spine, the self-improvement loop Goodharts on an unversioned float and the regression
is invisible by construction (it reads BETTER as quality rots). My ordering treats S8→S9 as a hard,
non-negotiable edge; any reconciliation that softens it re-introduces the Tier-S risk the whole
architecture exists to defeat.
