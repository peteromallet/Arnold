# Custody control plane overlap with Native Megaplan parity

**Audit date:** 2026-07-21  
**Remote session:** `custody-control-plane-20260714`  
**Remote workspace:** `/workspace/custody-control-plane-20260714/Arnold`  
**Mode:** read-only remote inspection; no remote files, processes, plans, refs, or sessions were modified

## Verdict

The custody epic is **architecturally complementary, not a replacement for the Native Parity corrective epic**. It has built substantial reusable substrate for exact run identity, authority fencing, custody leasing, and durable boundary evidence. But its own ownership matrix says Native Parity remains the topology owner: `.pypeline` and named subworkflows must remain the semantic topology, while component/handler route tables must become non-authoritative or be deleted.

The amended Native Parity plan should therefore:

1. consume the Run Authority, Custody, and WBC contracts at canonical authored/lowered boundaries;
2. stop creating any parallel receipt, checkpoint, lease, or execution-history scheme;
3. migrate WBC producers away from the current component/handler/auto carriers as those carriers lose authority;
4. make the final proof a set-equality and captured-runtime proof from authored source through lowering, execution, WBC history, Run Authority decisions, Custody epochs, and projections;
5. admit the **completed M11 custody end state** as a pinned prerequisite, through its generated completion/conformance evidence, rather than duplicating its lease, query, projection, recovery, or generic conformance scope inside Native Parity.

This sharpens the earlier philosophical diagnosis. The principal defect is still **semantic erasure disguised as compression**, but there is now a second constraint: the restored semantics need **one exact causal and authority identity**. A beautifully explicit native graph is still unsafe if dispatch, resume, retry, effect, or completion can occur without the current grant/fence, lease/epoch, and required WBC evidence. Conversely, perfect custody evidence around handler-owned routes would merely make the wrong semantic authority better audited.

## Remote epic status (operational context, not a Native Parity design gap)

At the observation captured by `megaplan cloud status --all --compact`:

- session `custody-control-plane-20260714` was `running`, `operator=running_repairing`, `should_run=yes`;
- the active plan was `m9-rebuildable-projections-20260721-0504`, in execute attempt 3;
- chain state `chain-1e998199f544.json` had `current_milestone_index=7`, `last_state=blocked`;
- M5, M5A, M6, M6A, M7, M8, and M8A were appended to the chain's completed list;
- M9 was not complete; M10 and M11 had not begun.

Publication and proof status are weaker than the word `completed` suggests:

| Milestone | Chain record | Publication evidence | Audit interpretation |
| --- | --- | --- | --- |
| M5 | done | PR #250 merged | Landed reconciliation/retirement work |
| M5A | done | PR #281 merged | Landed atomic completion-transition work |
| M6 | done | PR #275 merged | Landed contract/inventory freeze |
| M6A | done | PR #288 merged; merge `4e480fec1` | Transactional WBC store/API exists on the consolidation line |
| M7 | done | PR #289 merged; merge `9c99688b6` | Custody contracts/store/validator exist on the consolidation line, initially shadow-only |
| M8 | done | PR #290 still open; auto-publish `751a2b833` | Substantial producer adoption exists, but is not landed canonical history |
| M8A | done | no PR in chain state; auto-publish `658f075a1` | Candidate branch work only |
| M9 | active | dirty working tree, no completion | Query/projection cutover in progress |
| M10/M11 | pending | none | Recovery/effects and final conformance remain unproved |

The remote checkout is also provenance-divergent: HEAD `658f075a1` contains M8/M8A work but does not have the published M6A merge `4e480fec1` or M7 merge `9c99688b6` as ancestors; the M8 auto-publish commit carries a very large reconstructed tree. The current M9 tree has many modified/untracked query/projection files. This is **not** a gap to add to Native Parity: under the stated sequencing assumption, Custody completes M9-M11 and publishes one clean, verified end-state revision before Native Parity starts. It is recorded only to distinguish today's machine state from that future prerequisite.

The available full-suite backstops are not completion proof: M8's backstop is `failed` (one failure, `tests/arnold/pipelines/deliberation/test_native_behavior.py`), and M8A's backstop is `error` after roughly 900 seconds with no collected results. M11 explicitly remains responsible for captured replay, cross-host handoff, installed-runtime, zero-bypass, and runtime-trace conformance. Native Parity's prerequisite gate should consume M11's accepted replacement evidence; it should not repair these intermediate backstops itself.

## Exact contract meanings

WBC means **Workflow Boundary Contracts**. The composed contract is explicit in the remote decision record, `.megaplan/initiatives/custody-control-plane/decisions/single-authoritative-runtime-history.md`:

| Contract | Owns | Does not mean |
| --- | --- | --- |
| Run Authority | Capability grants, subject/coordinator attempts, accepted claims and decisions, coordinator fences, CAS/idempotency, quarantine | It is not a renewable lease, WBC history, status, scheduling, or repair custody |
| Custody | Exact action-target and repair-occurrence identity, renewable exclusive lease, monotonic custody epoch, transfer/reclaim/release/expiry, recovery and reconciliation | Lease exclusivity is not permission to perform the action |
| WBC | Exact-version boundary declarations; durable transactional execution-attempt and external-effect history; provenance; payload/reference policy; receipts/findings; conformance | Evidence is not a grant, lease, transition, route, or lifecycle decision |
| Projections | Rebuildable views at declared source cursors | A view is never a bearer token for dispatch, repair, retry, completion, cancellation, publication, or delivery |

The required action rule is conjunctive:

```text
current Run Authority grant + current coordinator fence
AND current Custody lease + current custody epoch
AND required exact-version WBC evidence at declared boundaries
```

The first two terms authorize and fence the action. WBC establishes what was attempted and observed; it can make a boundary incomplete/indeterminate, but it cannot authorize it. The decision record states this at lines 17-35 and 109-125. The settled terminology is especially important (`single-authoritative-runtime-history.md:79-91`):

- a **Run Authority subject attempt** is an authorized identity making a claim under one fence;
- a **WBC execution attempt** is the durable ordered event/effect history of work actually attempted;
- a **Custody lease** is renewable exclusive ownership by an actor/host/process-birth identity over an exact target, with expiry and epoch;
- the **coordinator fence** and **custody epoch** are independent monotonic tokens and both must be current.

The remote implementations reflect this split:

- Run Authority contracts: `arnold_pipelines/run_authority/contracts.py:196-253,271-337` (`CoordinatorFence`, `CapabilityGrant`, `SubjectAttempt`, `Claim`, `Decision`).
- WBC attempt schema: `arnold/workflow/execution_attempt_ledger.py:1-45,146-220` (start, terminal, retry, suspend/resume, cancel, effect intent/outcome, persistence failure/reconciliation).
- Transactional store: `arnold/workflow/attempt_ledger_store.py:1-34,66-114` (SQLite WAL, monotonic sequence, idempotent dedup, exactly one terminal, reservations that explicitly are not authority).
- Custody identities and leases: `arnold_pipelines/megaplan/custody/contracts.py:17-32,111-174,177-295` (`CustodyTargetKey`, exact `RepairOccurrenceKey`, lease owner host/PID/boot ID, expiry, grant and WBC references, append-only event types).
- Shared conjunctive gate: `arnold_pipelines/megaplan/custody/action_validator.py` validates current grant/fence, current target-matching lease/epoch, and exact WBC attempt/version before action.

The lease/validator rollout is not yet active proof. M7 records its writers as shadow-only and defaults `ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT` off (`custody/controlled_writer_registry.py:454-461`; `custody/writer_map.py:108-114,245-267,410-427`). Native Parity must not count a shadow pass as enforcement.

## Overlap classification

### 1. Prerequisite substrate Native Parity should consume

- Immutable Run Authority grant/attempt/decision/fence contracts and pure reducer.
- WBC execution-attempt schema and transactional SQLite store/API, including idempotency, terminal uniqueness, outbox/reconciliation and payload/migration components (M6A merge `4e480fec1`).
- Custody target/repair-occurrence contracts, renewable lease history, monotonic epochs, process-birth identity, shared action validator, controlled-writer registry, and compatibility/projection scaffolding (M7 merge `9c99688b6`).
- At the assumed M11 end state: canonical exact-version WBC query APIs, pure rebuildable projections, safe retry/recovery/effects, cross-host handoff, installed-runtime provenance, zero-bypass inventories, and generated runtime conformance.
- M8/M8A adapters and pure domain helpers that survive M11's clean convergence, including native hooks, phase/child lifecycle, task feasibility/splitting, deterministic validation, bounded circuits, work ledger and verify-only repair adoption.

Native Parity should reuse the completed contracts, stores, queries, lease/recovery service, projections and proof framework. It may reuse an adapter only if the adapter is downstream of the canonical lowered node and does not preserve a legacy route owner. Custody remains owner of those generic facilities; Native Parity owns only the topology-specific binding and migration of producer identity.

### 2. Semantic overlap, but not reusable implementation as-is

- M8 adds WBC evidence around existing handlers, `auto.py`, execute batch code, compatibility paths and native hooks. This is valuable producer coverage, but much of it instruments the exact hidden semantic carriers Native Parity must demote.
- The M8 inventory still classifies handler functions such as execute/finalize/review as authority-bearing producers/readers. That is an accurate audit of today, not the desired Native Parity end state.
- Phase WBC, override WBC and native hook wrappers show how to produce start/terminal/effect records, but the stable producer identity must be the authored/lowered semantic node and child path, not a handler name or mutable phase label.
- M8A implements planner/executor decisions in handler-adjacent modules. The pure policies can be reused; their policy attachment and control edges still need to be visible from `.pypeline`.
- Today's M9 `wbc_queries.py` and projection rebuild work are uncommitted/in progress. Under the sequencing assumption, Native Parity ignores this intermediate form and consumes only the accepted M11 API/version.

### 3. Contract mismatches or risks

1. **Topology ownership risk.** The custody migration matrix explicitly assigns `.pypeline`/named subworkflows to Native Parity and requires component/handler routes deleted or adapter-only (`research/migration-matrix.md:60-62,126`). A Native Parity revision that merely adds WBC wrappers to the current 85-to-14 collapse would violate both epics.
2. **Identity collapse risk.** Run Authority subject attempt, WBC execution attempt, native invocation/child path, and Custody target/lease are related but distinct. Reusing one generic `attempt_id` for all four would erase their ownership distinctions.
3. **Evidence-as-authority risk.** Existing receipt/projection-heavy compatibility paths must not use a WBC success record or status view to select the next route, resume, or skip execution.
4. **Shadow-as-enforcement risk.** Current Custody guards are default-off/shadow, but M11 completion is assumed to resolve promotion. Native Parity's admission gate must verify the accepted enforcement cohort/version and then exercise it; it must not recreate promotion logic.
5. **Wrong-boundary instrumentation risk.** A WBC producer attached to `handle_review()` proves that the handler ran; it does not prove that the source-visible review fanout, reducer, decision and loop ran. Producer identity must move as topology is extracted.
6. **Checkpoint ambiguity risk.** WBC offers `CheckpointPayload`, but it does not itself define Megaplan's semantic coordinates. Native Parity must define task ID + batch identity + fanout item path; WBC records that coordinate and Custody fences the action on it.
7. **Suspension lease risk.** Human suspension cannot treat an old marker or an indefinitely held lease as resume authority. Suspend must be durable WBC history; resume must reacquire/validate a current lease/epoch and current Run Authority fence against the same semantic reentry identity.
8. **Proof provenance risk.** Native Parity must admit only the final M11 completion manifest, exact installed/runtime revision and generated proof map. Intermediate M8/M8A labels, open/no PR publication, dirty M9 work and failed/error backstops are operational history, not inherited proof and not Native Parity repair scope.

### 4. Remaining Native Parity gaps after consuming the substrate

The custody work does not resolve the central parity findings:

- 85 lowered authored nodes still collapse to a 14-step canonical component graph;
- canonical build still drops dynamic fanout policies;
- route decisions still come from components, handler strings, runtime maps, `_core` tables, CLI and auto-drive;
- human suspension/reentry, task/batch child identity, config-change reentry and bounded loops are not fully source-authoritative;
- compatibility/native-program/manifest evidence still can false-pass semantics;
- installed runtime equivalence and deletion of hidden carriers remain unproved.

Custody adds requirements around these gaps; it does not make them disappear.

## Amended seven-sprint recommendation

Each sprint has two gates: a **semantic gate** (the authored/lowered workflow determines behavior) and an **adoption gate** (the actual action uses the completed Custody M11 contracts and is exact-identity-bound and durably proved). Native Parity starts only after a clean exact M11 revision, completion manifest, contract/version inventory, installed-runtime attestation and zero-bypass baseline have been accepted. It does not reopen Custody's generic implementation scope.

### S1 — Custody admission, topology contract, and semantic-preservation gate

- Verify the completed Custody M11 prerequisite: exact commit/tree and installed runtime, completion manifest/proof map, contract/schema versions, WBC producer/query registries, enforcement cohort, projection rebuild digest and zero-bypass inventory.
- Import those versions as immutable dependency pins. Any mismatch blocks Native Parity; no fallback schema, store, lease service, query facade, recovery loop or projection is created locally.
- Extend the Native Parity normative matrix with four distinct IDs per node/action: authored semantic node/child path, Run Authority subject attempt, WBC execution attempt, and Custody target/lease.
- Generate source declaration -> lowered node -> WBC boundary/producer -> authority action -> projection consumer rows.
- Add the blocking 85-to-14 preservation test, dynamic-fanout retention test, handler-route negative test, and chain-level executable gates.
- Fail if a WBC producer is registered only against a soon-to-be-deleted handler carrier.

**Exit:** the present implementation fails closed; no row can be `implemented` from hashes, support labels, shadow guards, receipts, or projections.

### S2 — Generic authored control primitives bound to the completed custody APIs

- Implement product-neutral typed decision, bounded loop, dynamic map/reducer, human suspend/resume, checkpoint and call-site policy constructs.
- Lower each semantic invocation and fanout child to a deterministic path and WBC attempt identity.
- Bind lowering/runtime adapters to the existing WBC reservation/start/terminal/effect/checkpoint API; do not implement another ledger or outbox.
- At every authority-increasing dispatch/effect/transition, call the existing Custody action validator and lease/recovery interfaces; do not implement another grant/lease/reconciliation path.
- Express Native-specific suspension/reentry coordinates and pass them through Custody's already-settled suspend/resume and lease lifecycle.

**Exit:** crash/retry/idempotency/stale-fence/stale-epoch tests pass in enforce mode for a neutral reference pipeline.

### S3 — Front-half vertical slice and legacy-carrier deletion

- Move prep, clarification, plan, critique fanout/fallback/merge, gate normalization/reprompt/debt and revise loop into authored topology.
- Attach policies at authored call sites; retain only pure computation bodies.
- Move WBC producers from phase handlers to the canonical lowered nodes and child attempts.
- Delete or hard-quarantine the corresponding component route bindings, handler route strings, manifest defaults and auto-drive route derivation.

**Exit:** editing source changes runtime and WBC traces; editing the quarantined handler/component route surfaces cannot change behavior.

### S4 — Tiebreaker, finalize, human decisions, and durable reentry

- Author parallel researcher/challenger, synthesis and the full human decision vocabulary.
- Author finalize fallback-to-revise and scoped re-finalization.
- Give each human decision a capability, signed/accepted Run Authority decision, WBC suspend/resume lineage, exact reentry node, and current Custody acquisition/epoch.
- Prove stale approval, stale marker, stale fence and stale epoch cannot resume or advance.

**Exit:** kill/restart/resume traces return to the exact semantic point without marker-only authority or duplicate effects.

### S5 — One reusable delivery cycle: execute, review, rework

- Build one authored reusable `finalize -> approval -> dependency-ready dynamic batches -> review fanout/reducer -> bounded rework` subworkflow.
- Use task ID + batch identity + item path for child checkpoints; parent and child WBC attempts have explicit causal joins.
- Acquire/validate Custody per authoritative task/effect target, not by broad session name; transfer/reclaim increments epoch.
- Bind accepted batch/review/final results through Run Authority decisions; verify-only repair adoption must match revision, task contract, tree/tests, fence and epoch.

**Exit:** partial failure, cancellation, fallback, cross-host handoff, crash around effect intent/outcome and resume rerun only incomplete children and never duplicate an accepted effect.

### S6 — Override and auto-drive adoption of Custody control/query surfaces

- Author every override/recovery/config-change route and its exact reentry edge.
- Route abort, force-proceed, replan, recover, resume, adoption, publication and delivery through Custody's existing action/recovery boundary; Native Parity supplies the authored semantic target and reentry edge, not new recovery policy.
- Reduce auto-drive to consuming the completed event/query/control APIs. It may request a topology-declared action but cannot derive product routes, retry policy, model choice, completion or resume authority.
- Adopt Custody's exact-version WBC queries and rebuildable projections as downstream views. Do not rewrite status/watchdog/auditor projection machinery in this epic.

**Exit:** forged/stale but internally consistent projections and WBC receipts cannot trigger any positive action.

### S7 — Native-topology conformance on the Custody M11 proof framework

- Extend Custody M11's generated proof model with Native-specific set equality across authored source nodes, lowered topology, registered producers, actual runtime traces and semantic reentry/checkpoint coordinates.
- Reuse M11's stale-fence/epoch, persistence, cross-host, recovery, projection rebuild and installed-runtime fixtures; add only Native topology mutations and end-to-end compositions that those generic fixtures cannot express.
- Run the Native workflow from clean wheel/sdist and the already-pinned custody-compatible cloud runtime.
- Require the existing enforcement and independent-verification gates plus zero hidden route reader/writer inventory; do not build a second cross-contract conformance harness.
- Delete component/handler route tables, compatibility authority paths and false-pass evidence generators only after the negative and rollback gates pass.

**Exit:** the smallest readable `.pypeline` fully determines behavior, while Run Authority determines permission, Custody determines exclusive current ownership, WBC proves the exact attempt/effects, and projections only explain them.

## Minimum new blocking regressions

1. `source -> lowered graph` preserves every semantic node, decision, loop and dynamic fanout policy.
2. Authored/lowered node identity and runtime WBC attempt identity have generated set equality.
3. Every Native authoritative action demonstrably passes through the admitted Custody validator; reuse M11's missing/stale grant, fence, lease and epoch matrix.
4. Native source/runtime mutations cannot turn WBC receipt/evidence/projection into dispatch, resume, retry, completion, cancellation, publication or delivery authority.
5. Every authored executable node/child maps to the admitted WBC lifecycle; reuse M11's durability, terminal uniqueness and ambiguity invariants.
6. Fanout child identity includes semantic item/task and batch/path coordinates, not list position alone.
7. Suspend/resume survives process death and requires current authority/custody at the same reentry point.
8. Native fanout/resume targets preserve identity through Custody's already-proved cross-host transfer/reclaim path.
9. Handler/component/runtime/CLI/auto route mutation cannot alter canonical behavior.
10. Projection deletion/rebuild is deterministic, and forged/stale projections cannot increase authority.
11. Installed package and cloud pinned runtime produce the same topology, WBC trace and decisions as checkout source.
12. Native completion consumes the pinned Custody M11 conformance receipt and adds source/lowering/runtime topology proof; neither side can be replaced by auto-publish, support manifest or status label.

## Bottom line

The custody epic confirms that the Native Parity plan should not aim merely for “all control flow visible in Python.” The end state is:

> **One authored semantic topology; one exact authority decision history; one current exclusive custody owner; one durable boundary/effect history; any number of disposable projections.**

The earlier seven-sprint structure remains usable, but every sprint now needs to relocate WBC producers and dual authority/custody gates onto the canonical authored/lowered action boundaries. The custody work reduces the amount of substrate Native Parity must invent, while increasing the precision of the identity, resume, effect, and proof contracts it must satisfy.
