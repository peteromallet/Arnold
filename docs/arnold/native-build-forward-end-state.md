# Native Build Forward — End State

## The system

Megaplan is a source-authoritative native workflow, not a handler graph presented through Python syntax.

- Every durable root and child workflow has one canonical `.pype` file. Static imports compose workflows without executing source. Reusable steps, effects, schemas, policies, and pure helpers remain ordinary `.py`; `.py @workflow` is preview-only.
- Product topology is visible in restricted Python control flow: branches, bounded loops, typed named exits, runtime-list fanout, deterministic reducers, retries, fallback, child calls, human suspension/reentry, effect boundaries, review/rework, override, recovery, and terminal outcomes.
- `.pype` source owns product semantics. Deterministic lowering produces a content-addressed `WorkflowManifest` that owns admitted runtime and replay coordinates, never editable route truth.
- Admission pins source, manifest, decoder/lowerer, package lock, policy, Run Authority decision, Custody lease/epoch, WBC contract, and installed executable closure. Stale or incompatible identities fail closed.
- Checkpoints record semantic reentry coordinates and durable local state. Resume re-enters the same admitted program under revalidated authority; status, liveness, watchdogs, auditors, and projections cannot select a route or authorize work.
- External actions use one live writer and durable intent/outcome/ambiguity/reconciliation history. Authority cuts are single typed transitions with pre-readiness, independent post-verification, old-writer fencing, and pointer-only rollback.
- Traces are append-only, source-mapped, and causal across workflow, child, loop, item, retry, suspension, checkpoint, decision, authority, custody, WBC, effect, and terminal identities.

Platformization then turns only proven mechanics into a reusable workflow platform.

- Product-neutral runtime, admission, completion, authoring, package, identity, tooling, and component contracts are extracted without a second kernel, owner store, or authoring grammar.
- Qualified components have descriptors for ports, closed outcomes, state, policy, effects, capabilities, suspension, lifecycle, dependencies, evidence, and compatibility.
- A deterministic component/dependency lock selects exact implementations and transitive artifacts. Composition preserves namespaces, identity, state, effects, cancellation, replay, and concurrent-instance isolation.
- The composition algebra is demonstrated by extraction back into Megaplan and by an unrelated consumer with materially different types, outcomes, policies, effects, storage, nesting, human gates, and concurrency.
- Stable publication is limited to components and capability profiles that pass the two-consumer conformance and evolution contract. Other candidates remain internal or experimental.

## What the operator gets

- Author and review Megaplan workflows as readable `.pype` programs instead of reconstructing control flow from handlers, route tables, mutable status, and runtime dispatch.
- Static grammar, import, port, outcome, effect, policy, identity, package, and executable-closure validation before a run exists.
- Source-mapped format, lint, topology, preview, test, editor/navigation, package-refactor, completion-inspection, and deterministic local-harness tooling using the same parser and admission rules as production.
- Deterministic execution and resume across checkout, wheel, cloud, process death, host change, dynamic fanout, nested children, human waits, review/rework, and ambiguous effects.
- Exact explanations from source span to admitted manifest coordinate, runtime decision, authority/custody/WBC evidence, checkpoint, effect, and terminal result.
- Qualified component reuse with deterministic resolution, clean-wheel installation, supported-shape recomposition, new-instance substitution, and separately stated resume compatibility.
- Versioned compatibility ranges, explicit migrations, mixed-version rejection, pointer rollback, and quarantine when no accepted decoder or conservation mapping exists.

## Deliberately not in the end state

- Arbitrary Python as durable workflow source. The admitted language remains a restricted, statically validated subset; ordinary `.py` workflows remain non-durable preview.
- New live `.pypeline` authoring. Exact pinned readers may remain only for the accepted suspended-run retention horizon; Native S2F owns that decision and migration evidence.
- Open-stream primitives. Native S2R leaves them unsupported unless separately chartered.
- Maintenance Runtime Consolidation schedules, role/model tables, repair policy, receipts, capabilities, or canary results as Megaplan product semantics or M11 authority. Custody and Run Authority retain those boundaries.
- Product routes, grants, leases, WBC history, effects, or terminal acceptance inferred from manifests, component metadata, status, liveness, projections, or file existence.
- Certification of every extracted candidate. Platform S5 failures remain internal/experimental; Platform S6 publishes no compatibility claim for them.
- Compatibility outside declared package/component ranges, decoder promises, state migrations, and certified composition shapes.
- Rewriting historical completion manifests or false-pass evidence. They remain immutable substrate/history, not current conformance.

## The proof

Completion is demonstrated by generated, content-addressed evidence rather than narrative or green status.

- P0 proves the MRC→M11→Native crosswalk and that MRC evidence cannot satisfy Custody admission.
- P1/P2 bind all six admission gates: canonical Run Authority disposition; approved zero-blocker ownership; accepted Custody completion manifest/proof map; bounded-projection handoff; installed/runtime/production-vector and canary acceptance; and the milestone-gate bootstrap manifest with its three readiness artifacts.
- Native S7 closes Stage 1 with every one of the 31 alignment requirements, H0–H9, and D1–D15 independently dispositioned and validator-green; zero live `.pypeline`; zero handler/runtime/CLI route authority; closed allowances; complete restore coverage; and matching checkout/wheel/cloud behavior.
- Every authority, effect, or publication cut binds immutable inputs, source and package identities, focused tests, expected-red mutations, raw traces, readiness/transition/post-transition receipts, selected-state canary census, rollback, allowance lineage, independent review, and stable validator issue codes.
- The Native completion manifest and proof map content-address the Platformization handoff. Platform S1 must consume that exact handoff.
- Platform S4 proves source reuse, clean-wheel reuse, deterministic resolution, and supported-shape recomposition independently.
- Platform S5 adds independent-consumer evidence and reports new-instance substitutability separately from resume compatibility.
- Platform S6 closes only after validator self-mutations, both-consumer certification, compatibility/evolution/migration/rollback proof, a final proof map and completion manifest, and an independently verified publication transition.

The architectural basis is `docs/arnold/megaplan-native-representation-report.md` §1 and §5. Execution order and evidence authority come from the reconciliation, active chain, North Star, milestone briefs, validators, transition handlers, proof maps, and accepted receipts.