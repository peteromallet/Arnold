# Sprint 4b — Schema-driven node classification (`partnered/thorough/high +prep @codex`)

Shared context: read `docs/structural_audit_2026-05.md` (f3 fragile-heuristic sweep), `handoff-m1.md`, `handoff-m2b.md`, `handoff-m3.md`, and `handoff-m4a.md`. This sprint owns the classification seam and priority substring-site routing.

## Outcome
Node classification becomes schema-driven and centralized. The known misclassification-prone sites stop guessing by substring, and unknown schema behavior becomes explicit instead of locally heuristic.

## Scope (IN)
1. **Introduce `vibecomfy/node_classification.py`** with `classify_node(class_type, *, schema_provider=None) -> NodeClassification`, returning a frozen dataclass:
   - `class_type: str`
   - `media_kind: Literal["image", "video", "audio", "latent", "unknown"]`
   - `node_role: Literal["loader", "sampler", "save", "preview", "helper", "unknown"]`
   - `is_ui_only: bool`
2. **Own UI/helper classification**: move durable `UI_ONLY_CLASS_TYPES` ownership here, with module-local extensions where needed.
3. **Route the four priority fragile substring sites through `classify_node()`**:
   - `runtime/eval.py:164-188`
   - `porting/emitter.py:608-630`
   - `templates.py:58-65`
   - `analysis/graph.py:295-307`
4. **Use the sprint-2b schema-provider handoff as the source of truth**. Runtime and analysis code consume `classify_node()`, not the provider's internal structure.
5. **Review M1 deferred widget-alias gaps** from `handoff-m1.md`; resolve any now covered by the schema provider and carry unresolved cases into `handoff-m4b.md` with resolution path.
6. **Commit `classification_sites_m4.json`** covering the four priority sites plus any additional sites affecting runtime output, template conversion correctness, or public analysis results. Remaining non-critical substring checks are recorded as a count.
7. **Create `handoff-m4b.md`** recording classifier API decisions, schema-provider coverage, fallback/unknown cases, fixed classification sites, widget-alias outcomes, and any intentional snapshot deltas.

## Locked decisions
- The schema provider is the classification source of truth.
- Call sites use the classifier seam, not schema-provider internals.
- If schema is unavailable for a class type present in any ready template, `classify_node()` returns `UNKNOWN` and records the gap instead of guessing.
- Heuristic fallback is allowed only for genuinely absent schemas outside the ready-template corpus, and every fallback is centralized and listed with the failed schema query.
- Misclassification cases (`AudioPreview`→audio, `VideoSampler`→video) are explicit tests.

## Prep deliverables
- `prep-m4b.md` verifies the sprint-2b schema provider against ready-template class types and priority classification sites, including fallback-rate risk. If coverage is weak, prep must recommend escalation before implementation.

## Constraints
- Differential harness, snapshots, sprint-2a/2b gates, sprint-3 import-linter contract, and sprint-4a clone check stay green.
- No broad module decomposition; sprint 5 owns that.
- No behavior change to already-correct classifications.

## Done criteria
- The four priority classification sites route through `classify_node()` and have regression tests.
- `classify_node()` consults the schema provider for every provider-known class type.
- Unknown-schema behavior is tested: ready-template unknowns return `UNKNOWN`, and allowed fallbacks are centralized.
- `classification_sites_m4.json` and `handoff-m4b.md` record baseline/fixed counts and unresolved gaps.
- Sprint-1 through sprint-4a gates remain green.

## Touchpoints
`vibecomfy/node_classification.py`, `runtime/eval.py`, `porting/emitter.py`, `templates.py`, `analysis/graph.py`, `vibecomfy/_workflow_helpers.py`, tests, `docs/megaplan_chains/excellence_epic/`.

## Anti-scope
Do NOT change registry collision semantics. Do NOT decompose emitter/session modules. Do NOT build plugin route/verb policy.
