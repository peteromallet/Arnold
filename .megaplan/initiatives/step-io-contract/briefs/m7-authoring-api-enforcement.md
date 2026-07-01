# M7: Authoring-API Enforcement

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

## Outcome

Close seam #4 — Author ⇄ Runtime — by making the authoring API's contract declarations ENFORCED. Seams 1–3 make pipelines correct; seam 4 makes them cheap to author. "50 pipelines overnight" is a statement about THIS seam: an author should only ever declare contracts and never hand-roll a crossing.

The public authoring API (`p.flow/agent/panel/decision`, `HALT`, `reads`/`writes`, `arnold pipeline check`) is planned contract-SHAPED but not enforced. This milestone makes `reads`/`writes` enforced. The authoring SHAPE generalizes (B1) from `{input contract, instruction, output contract}` to `{input contracts, invocation spec (kind + adapter_config), output contract}` — "instruction" is DEMOTED to a field of the MODEL adapter's `adapter_config`, not the central authoring field, so a model step and a (future) non-model step are both expressible via the one invocation-spec shape. The runtime handles every crossing — serialize-in, validate-out, structural audit, suspension — using the machinery from m0a–m6. Enforcement is added ADDITIVELY under the planned authoring API so a running chain is not disturbed.

## Scope

IN:

- Make the authoring API's `reads`/`writes` declarations ENFORCED: a stage's declared input/output contract is bound to the typed ports (m2) and validated through the chokepoint (m1) + structural audit (m0b) at runtime.
- The author declares `{input contracts, invocation spec (kind + adapter_config), output contract}`; "instruction" is a field of the MODEL adapter's `adapter_config`, not the central field, so the same shape expresses a model step and a (future) non-model step. The runtime handles the crossing (serialize-in via the model adapter `render_step_message`, validate-out via `capture_step_output`, structural audit, suspension propagation) so no author hand-rolls assembly or parsing.
- Capability declarations: a step may declare capabilities it requires (e.g. "requires vision model", "requires image decoder"). `arnold pipeline check` VERIFIES these for compatibility, not just producer/consumer schema alignment — a capability mismatch is caught before a run.
- Wire `arnold pipeline check` (the static authoring check) to verify declared contracts are well-formed, producer/consumer contracts line up, AND declared capabilities are satisfiable before a run.
- Add enforcement ADDITIVELY under the existing/planned authoring API; do not disturb a running chain or require a flag-day change to existing pipelines (gradual typing still applies — enforce only when both sides typed).
- Tests: a pipeline authored purely via declared `reads`/`writes` runs with the runtime handling every crossing; a declaration mismatch (producer output contract ≠ consumer input contract) is caught by `arnold pipeline check`; an existing un-migrated pipeline still runs (gradual typing).

OUT:

- Defining new authoring verbs/surface beyond enforcing the existing `reads`/`writes`.
- Migrating remaining IO sites (done in m5/m6).
- Model-seam machinery (m3) and suspension composition (m4) — consumed, not built.
- The acceptance gate / 2nd-toy-pipeline proof (m8) — though m7's "author declares only contracts" is what m8's toy pipeline exercises.
- Any new validator/registry/chokepoint.

## Locked Decisions

- m7 stays in THIS epic (jury-confirmed) — it is the seam-4 / scale unlock, not a deferrable follow-on.
- Make the planned authoring API's `reads`/`writes` ENFORCED. The authoring SHAPE generalizes (B1) to `{input contracts, invocation spec (kind + adapter_config), output contract}`; "instruction" is DEMOTED to a field of the model adapter's `adapter_config`, not the central field — a model step and a future non-model step are both expressible via the one invocation-spec shape. Runtime handles the crossing.
- Capability declarations (e.g. "requires vision model", "requires image decoder") are part of the authored step and are verified by `arnold pipeline check` for compatibility — not only producer/consumer schema alignment.
- Enforcement is ADDITIVE under the authoring API and does not disturb a running chain.
- Gradual typing still governs: enforce only when both producer and consumer are typed; existing plans don't brick.

## Open Questions

- The exact binding between an authored `reads`/`writes` declaration and the underlying typed `Port`/`PortRef` (declaration is the source of truth vs. derived from ports).
- What `arnold pipeline check` validates statically (contract well-formedness, producer/consumer line-up, schema-version availability) and what is only checkable at runtime.
- Ergonomics of the invocation-spec shape: how `adapter_config` (carrying the demoted `instruction`) and the `output contract` read alongside `reads`/`writes` without re-introducing hand-rolled assembly (the shape is settled per B1; the surface ergonomics are open).
- How enforcement coexists with the planned authoring API's current position in the cleanup chain (additive insertion point) without a flag day.
- The author-facing diagnostic when a declared contract is violated at runtime (vs. the operator-facing m1 telemetry).

## Constraints

- Adding enforcement must not disturb a running chain or force existing pipelines to change at once (additive + gradual typing).
- An author must not need to hand-roll serialize-in or validate-out for a declared crossing — that is the whole point of the seam.
- `arnold pipeline check` must catch declaration mismatches before a run, not at first crossing.
- Bases on m0a–m6; consumes the type, validator, chokepoint, ports, model-seam, and composition without modifying them.

## Done Criteria

1. The authoring API's `reads`/`writes` declarations are ENFORCED at runtime: the runtime serializes-in, validates-out, runs the structural audit, and propagates suspension for a declared crossing, with no author-side assembly/parsing.
2. A pipeline authored purely via the declared `{input contracts, invocation spec (kind + adapter_config), output contract}` shape runs end-to-end with the runtime handling every crossing (test); "instruction" is expressed as a field of the model adapter's `adapter_config`, not the central field.
3. A model step and a (future) non-model step are BOTH expressible via the one invocation-spec authoring shape; a test demonstrates both forms author cleanly (the non-model one need not execute — its adapter kind may be unbuilt/fail-closed — but it must be authorable).
4. `arnold pipeline check` catches a producer/consumer contract mismatch before a run (test).
5. `arnold pipeline check` catches a CAPABILITY mismatch (e.g. a step requiring a vision model or an image decoder that the resolved configuration cannot satisfy) before a run, distinct from schema alignment (test).
6. Enforcement is additive: an existing un-migrated pipeline still runs unchanged (gradual typing), and a running chain is not disturbed (test).
7. An author-facing diagnostic is produced when a declared contract is violated at runtime, distinct from operator telemetry.
8. No authoring verbs or model-seam/composition machinery are redefined; m7 only enforces the existing declarations over the built foundation.

## Touchpoints

- the public authoring API surface (`p.flow/agent/panel/decision`, `HALT`, `reads`/`writes`)
- `arnold pipeline check` (static authoring check — now also verifies declared capabilities, e.g. requires-vision-model / requires-image-decoder, not only producer/consumer schema alignment)
- the invocation-spec authoring shape `{input contracts, invocation spec (kind + adapter_config), output contract}` (instruction demoted to the model adapter's `adapter_config`) + step capability declarations
- `build_pipeline()` / pipeline assembly binding declarations to typed ports
- `arnold/pipeline/types.py` (Port binding) + m2 typed ports
- m1 chokepoint + telemetry, m0b validator, m3 model-seam, m4 suspension (consumed)
- authoring-enforcement tests (declared-pipeline runs, mismatch caught by check, un-migrated still runs, runtime violation diagnostic)

## Rubric

- Profile: `premium`
- Robustness: `thorough`
- Depth: `high`

Rationale: this is the seam-4 scale unlock — the difference between a correct platform and one where 50 pipelines can be authored overnight. Binding authored declarations to enforced runtime crossings additively, without disturbing a running chain and while preserving gradual typing, is genuinely tricky integration across every prior milestone, so it earns thorough/high.
