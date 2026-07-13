# Managed-Agent Current-State Survey

Date: 2026-07-11  
Purpose: evidence for extending, rather than replacing, `sequential-model-fallbacks`

## Existing coherent substrate

- `arnold_pipelines/megaplan/profiles/partnered-5.toml` already defines scalar phase routes and D1–D10 `tier_models.execute` entries, including ordered arrays at D7–D8.
- `arnold_pipelines/megaplan/fallback_chains.py` already contains `FallbackSpecChain`, canonical compact JSON phase-model bridging, provider-family/retry classification, and additive fallback observability helpers.
- Profile parsing/policy, tier/prep resolution, worker fanout, state, chain/cloud, receipts, and tests already contain partial scalar-or-array support. This is the machinery the original initiative was designed to finish.
- `arnold_pipelines/megaplan/resident/subagent.py` now has a separate `route_delegated_task` D1–D10 policy (Luna/Terra/Sol), a managed resident run v1 manifest, detached worker/result paths, and a resident-owned launch seam.
- `arnold_pipelines/megaplan/resident/provenance.py` validates and propagates a v1 resident delegation provenance envelope across process boundaries.
- Resident prompt/tool code already directs agents to a supported managed launch seam rather than a generic launcher.

These are not competing product initiatives; they are incomplete dispatcher-specific slices of the same profile, fallback, and custody problem. The correct shape is to preserve them, characterize current behavior, extract shared contracts, and migrate adapters.

## Gaps the epic must close

1. Megaplan and resident currently own different difficulty-to-model policies and resolution payloads.
2. D5 is not yet a shared explicit/default semantic with a deterministic full profile/tool/budget receipt.
3. Fallback primitives exist, but scalar-selection call sites and dispatcher-specific error/mutation boundaries remain; identical classification is not yet a cross-dispatcher invariant.
4. Resident v1 manifests carry a task string and useful provenance/result paths but do not yet establish a complete content-addressed root brief propagated through arbitrary managed descendants.
5. Resident-managed roots exist, but managed descendants need a first-class nested launch contract, ancestry, structured result custody, root-only delivery, inherited ceilings, and tree-wide accounting.
6. Depth/fanout/descendant, root attempt, visited-spec, cost/time/token, and privilege ceilings need transactional enforcement rather than prompt/local-process convention.
7. V1 schema compatibility, shadow cutover, restart reconciliation, and cross-dispatcher receipts need explicit migration evidence.

## Overlap finding

The Discord corrective initiative is active and heavily concerned with immutable Discord provenance, request-idempotent launch, terminal outbox/delivery, and artifacts. Its North Star explicitly owns transport lifecycle and delivery. The clean seam is:

```text
Discord corrective: immutable request/provenance envelope
                         ↓
This initiative: root + managed child tree, generic custody/profile/fallback/results
                         ↓
Discord corrective: one root completion intent/result → durable outbox/delivery
```

This initiative must neither weaken that provenance nor duplicate its outbox. Cross-initiative work is coordination at the two arrows.

## Shaping conclusion

Reuse `sequential-model-fallbacks`; rename its epic destination while retaining the slug and historical fallback research. The initial survey separated resolution, mutation-safe fallback, custody/schema, nested launch, policy enforcement, migration/resume, and conformance into seven review units. The canonical execution shape was subsequently consolidated into two aggressive sprints: four shared-foundation tracks in Sprint 1 and three enforcement/integration/conformance tracks in Sprint 2. Each original handoff remains explicit, but only interface convergence and the Sprint 1-to-Sprint 2 boundary are serialized.
