# M2: Data Seam — Wire the Typed Ports

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

## Outcome

Take the step⇄step seam live. The typed `Port`/`PortRef` vocabulary already exists at `arnold/pipeline/types.py:234` but is dormant — flag-gated behind `typed_ports_on()`, with no step declaring `produces`/`consumes`, the executor enforcing nothing, and `StepResult.outputs` still a free-form `Mapping[str, Any]`. This milestone WIRES it: the vocabulary is a head-start, but the wiring is real work.

Declare `produces`/`consumes` ports on the 9 pipeline stages, have the executor enforce the contract when both sides are typed (via the m1 chokepoint mechanism), and make `StepResult` carry a typed payload rather than a free-form mapping. Roll out shadow-first per seam so no live step→step handoff breaks on the way to enforcement.

## Scope

IN:

- Declare typed `produces`/`consumes` ports on the 9 pipeline stages, using the existing `Port`/`PortRef` vocabulary at `arnold/pipeline/types.py:234`.
- Typed ports carry richer metadata than a bare JSON-schema match (B2): `content_type`; `cardinality` `{singleton | collection | stream}` — RESERVE the `stream` value but do NOT implement streaming now; and `logical_type` + an `accepted_version_range` (not exact-hash-only). The port contract is this metadata tuple, not just "object matching schema."
- DEFINE the `StepInvocation` seam here as a FOUNDATION primitive (B1, the big one): an invocation TYPE + an adapter INTERFACE + an adapter REGISTRY. This is where the model/tool/human/state adapter seam lives. Build NO adapters in m2 (the MODEL adapter is built in m3); register no fake tool/human/state adapters. Unknown adapter kinds FAIL CLOSED. Only the model adapter SLOT is wired (its implementation lands in m3).
- Make the executor enforce the step→step contract when BOTH the producing and consuming stage are typed, routing through m1's enforce-when-both-typed + per-seam shadow/warn/enforce machinery.
- Carry a typed payload on `StepResult` instead of the free-form `Mapping[str, Any]` (`StepContext.inputs` / `StepResult.outputs` / `state_patch` today), so the step→step handoff is a `ContractResult` payload, not loose dict data.
- Roll out per seam shadow-first: each newly-typed step→step seam enters in shadow, is observed via m1 telemetry, then is promoted toward enforce.
- Tests: a typed→typed seam enforces (and rejects a wrong-shaped handoff in enforce mode); a typed→untyped or untyped→typed seam passes through unchanged (gradual typing); a typed seam in shadow mode logs without blocking.

OUT:

- Model-seam serialize-in/validate-out and degraded mode (m3) — m2 DEFINES the `StepInvocation` seam (type + adapter interface + registry) and wires the model adapter SLOT, but the model ADAPTER implementation is m3.
- Any tool/human/state adapter implementation — these stay UNKNOWN kinds that fail closed; only their extension point (the registry) exists.
- Migration/deletion of the load-bearing-5 or long-tail IO sites (m5/m6) — those are prompt-assembly/output-parse sites, distinct from the step→step data ports.
- Suspension-aware composition (m4); `StepResult` carries the m0a `status`, but propagation across subloop/fan-out is m4.
- Any new validator, registry, or chokepoint (consumed from m0b/m1).
- The authoring-API enforcement of `reads`/`writes` (m7); m2 wires ports at the stage-definition level, m7 makes the public authoring declaration enforced.

## Locked Decisions

- ACTIVATE + complete the dormant typed Ports rather than invent a new carrier; the step→step seam is half-built and the foundation finishes it.
- Vocabulary is a head-start; WIRING is the work — types exist at `arnold/pipeline/types.py:234`, but no step declares produces/consumes and the executor enforces nothing today.
- Enforce only when BOTH producer and consumer are typed (gradual typing, via m1); otherwise loose pass-through so the 33 sites and existing plans don't brick.
- Roll out shadow-first per seam; promotion to enforce is telemetry-driven through m1's machinery.
- `StepResult` carries a typed `ContractResult` payload, not a free-form `Mapping`.
- Typed ports carry `{content_type, cardinality (singleton|collection|stream — `stream` RESERVED, not implemented), logical_type + accepted_version_range}` (B2) — the port contract is this metadata, not just a JSON-schema match.
- The `StepInvocation` seam is a FOUNDATION primitive defined HERE (B1): invocation type + adapter interface + adapter registry, where the model/tool/human/state adapter seam lives. Build no adapters in m2 (model adapter is m3); unknown adapter kinds FAIL CLOSED; only the model adapter slot is wired.
- 2nd-PIPELINE CO-DESIGN CONSTRAINT (pre-mortem risk 1, the biggest — N=1 overfit): the ports + the `StepInvocation` seam are designed against a structurally-different 2nd pipeline — the deterministic Arnold-native `evidence-pack` verifier (model-LESS tool steps, data by-reference, fan-out-reduce, typed verdict, NO planning shape) — as a CO-DESIGN constraint FROM THE START, not just an m8 acceptance test (m8 VALIDATES it, it does not meet it first). The port metadata (`content_type` / `cardinality` / `logical_type` + `accepted_version_range`) and the `StepInvocation` adapter seam must demonstrably express the evidence-pack pipeline's model-LESS tool steps, by-ref multi-content-type data, and fan-out-reduce shape as cleanly as megaplan's model-driven stages — so the seam is a platform shape, not a megaplan-anatomy fit.

## Open Questions

- The exact port schemas for each of the 9 stages (what each stage declares it produces/consumes).
- Migration order of the 9 stages and which seams are safe to type first (which producer↔consumer pairs both get typed earliest).
- How `produces`/`consumes` declarations interact with the existing `typed_ports_on()` flag — retire the flag, repurpose it, or fold it into m1's per-seam mode.
- Coexistence of the typed `StepResult` payload with `state_patch` and the existing `RunEnvelope`/`RuntimeEnvelope` carriers during the transition.
- Whether a stage with a partially-typed contract (some ports typed, some not) is handled per-port or all-or-nothing per stage.

## Constraints

- No step→step handoff may break during rollout; every newly-typed seam enters shadow first.
- Un-migrated seams (one side untyped) must keep working exactly as today.
- The typed `StepResult` payload must remain serializable through the m1 chokepoint and round-trip with `schema_version`.
- Bases on m0a/m0b/m1; must not modify the type, validator, registry, or chokepoint.

## Done Criteria

1. The 9 pipeline stages declare typed `produces`/`consumes` ports using the `arnold/pipeline/types.py:234` vocabulary.
2. The executor enforces the step→step contract when both sides are typed, via m1's mechanism; a wrong-shaped handoff is rejected in enforce mode (test).
3. A seam with one untyped side passes through unchanged (gradual typing); a test proves an un-migrated handoff is unaffected.
4. `StepResult` carries a typed `ContractResult` payload instead of a free-form `Mapping`; a test proves the typed handoff round-trips through the chokepoint.
5. Each newly-typed seam can run in shadow mode (logs, does not block) and be promoted via m1 telemetry; tests cover shadow and enforce.
6. Typed ports carry the richer metadata — `content_type`, `cardinality {singleton|collection|stream}` (with `stream` RESERVED and not implemented), and `logical_type` + `accepted_version_range` — not just a JSON-schema match; a test proves a port declares and round-trips this metadata, and that declaring `cardinality=stream` is reserved/not-yet-implemented.
7. The `StepInvocation` invocation type + adapter interface + adapter registry exist; an unknown adapter kind FAILS CLOSED (test); only the model adapter slot is wired (its implementation is built in m3) and no tool/human/state adapter is registered.
8. No model-adapter implementation, migration, or composition work is performed; behavior of untyped seams is unchanged.
9. The ports + `StepInvocation` seam demonstrably express the structurally-different `evidence-pack` verifier shape (model-less tool steps, by-ref multi-content-type data, fan-out-reduce) as cleanly as megaplan's model-driven stages — co-designed against it from the start, NOT retrofitted at m8; an artifact/test shows the evidence-pack shape is expressible without contorting or extending the seam.

## Touchpoints

- `arnold/pipeline/types.py:234` (the dormant `Port`/`PortRef`/`produces`/`consumes` vocabulary being wired; extended with port metadata `content_type` / `cardinality {singleton|collection|stream}` (`stream` reserved) / `logical_type` + `accepted_version_range`)
- new `StepInvocation` seam primitive: invocation type + adapter interface + adapter registry (model adapter slot only; unknown kinds fail closed) — the foundation seat for the model/tool/human/state adapters
- the 9 pipeline stage definitions (`InProcessHandlerStep` / `megaplan/_pipeline/types.py:173-196` opinionated step)
- `StepResult` / `StepContext` (typed payload replacing free-form `Mapping`)
- the executor enforcement point (consuming m1's enforce-when-both-typed)
- `typed_ports_on()` flag gating
- step→step contract tests (typed-enforces, mixed-passes-through, shadow-logs)

## Rubric

- Profile: `premium`
- Robustness: `thorough`
- Depth: `high`

Rationale: this lights up the most-used seam in the system — step→step, present in every pipeline — and changes the core `StepResult` payload shape. Done loosely it would break live handoffs; done with gradual typing and shadow-first rollout it goes live safely. The executor enforcement wiring and the `StepResult` payload change are load-bearing across every pipeline, so it earns thorough/high.
