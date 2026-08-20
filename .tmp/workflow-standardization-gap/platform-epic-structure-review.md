# Native Workflow Platformization epic structure review

## Recommendation

Create a committed but unlaunched five-milestone epic at:

```text
.megaplan/initiatives/native-workflow-platformization/
  chain.yaml
  NORTHSTAR.md
  PLATFORM_CONTRACT.md
  README.md
  briefs/
    s1-component-standard-extraction-inventory.md
    s2-enforced-composition-resolution-package-surface.md
    s3-isolated-extraction-recomposition.md
    s4-adversarial-second-consumer-substitutability.md
    s5-certification-evolution-adoption.md
```

The existing ticket remains a provenance/issue-tracking record, but the epic
directory becomes the authoritative launch source. Update the ticket's `epics`
frontmatter to contain `native-workflow-platformization`, state that it has been
promoted into the prepared epic, and link the chain, North Star and contract.
Do not mark the ticket closed merely because the epic has been prepared; closure
should follow the epic's content-addressed completion proof under the ticket
workflow's normal resolver.

This should remain five milestones. The current ticket already has a coherent
five-stage dependency graph. Adding a sixth milestone would create a ceremonial
split rather than isolate a distinct proof boundary.

## Artifact ownership

### `NORTHSTAR.md`

Own the durable end state and non-negotiable philosophical constraints:

- Arnold is a workflow-component platform, not a Megaplan helper library.
- `.pypeline` Python is sole product control-flow authority.
- steps, subworkflows and workflows are qualified/versioned contracted
  components reusable across clean installations and composition shapes;
- authority, Custody, WBC evidence, effects and projections retain their
  distinct roles;
- durability survives suspension, crash, replay, retry, redeployment and
  substitution;
- experimentation is permissive, while production/certification claims are
  exact;
- stable publication requires the unrelated second consumer.

Keep detailed protocol decisions out of the North Star. Its job is to stop a
milestone from optimizing locally while missing the destination.

### `PLATFORM_CONTRACT.md`

Own all cross-milestone locked decisions currently embedded in the ticket,
including:

1. The five reuse claims and the platform/product layering.
2. Candidate/experimental status through S1-S4; only S5 may publish stable.
3. Component Descriptor v1 and deterministic durable-Python profile.
4. Five execution modes and six enforcement dispositions.
5. Source/generated-artifact authority and manifest/producer evolution.
6. One component lifecycle, disjoint business and control/lifecycle results,
   root-host rules, atomic outcome conditions and human timeout graphs.
7. Composition algebra, identity/isolation, parent-loop ledgers, typed named
   exits/reconfiguration, `JoinPolicy`, cancellation and resource settlement.
8. Run Authority/Custody/WBC/effect joins, certified production-store CAS and
   non-authoritative evidence.
9. Agentic and LLM boundaries, checkpoint payload discipline and effect replay.
10. Component locks, binding precedence, effective capability closure and both
    compatibility claims.
11. Raw-before-normalized partial-order trace truth and product-neutral causal
    explanation.
12. The eleven-clause standardization closure contract, all 37 acceptance-suite
    families, deliberately variable fields and non-goals.

Each brief should cite this contract and own only its stage-specific work. Do
not copy divergent abridgements of the same rule into five briefs. Where a
brief repeats a rule for emphasis, explicitly say that the contract is
normative.

### `README.md`

Provide human orientation only: status `prepared / not launched`, predecessor,
artifact map, milestone list, and the exact future launch command. It must say
that editing or reading the files does not launch a chain and that no chain
state should exist yet.

## Exact `chain.yaml`

```yaml
base_branch: main

anchors:
  north_star: NORTHSTAR.md

launch_preconditions:
  - name: native parity corrective epic completed with content-addressed proof
    kind: chain_completed
    chain: .megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml
    require_manifest: true
  - name: native-to-platformization handoff manifest exists
    path: .megaplan/initiatives/megaplan-native-parity-corrective/platformization-handoff-manifest.json
    check:
      kind: contains_text
      text: arnold.native_to_platformization_handoff.v1
  - name: holistic native workflow representation report exists
    path: docs/arnold/megaplan-native-representation-report.md
    check:
      kind: contains_text
      text: Megaplan Native Python and Reusable Workflow Platform Representation Report
  - name: platform contract exists
    path: .megaplan/initiatives/native-workflow-platformization/PLATFORM_CONTRACT.md
    check:
      kind: contains_text
      text: Native Workflow Platformization Contract
  - name: platformization initiative source is committed and clean
    kind: git_tracked
    path: .megaplan/initiatives/native-workflow-platformization

milestones:
  - label: s1-component-standard-extraction-inventory
    idea: .megaplan/initiatives/native-workflow-platformization/briefs/s1-component-standard-extraction-inventory.md
    profile: apex
    robustness: extreme
    depth: max
    with_prep: true
    notes: >-
      Consume the Native Parity handoff; freeze the candidate descriptor,
      deterministic authoring, lifecycle, composition, execution-mode,
      identity, evolution and proof contracts plus executable negative and DX
      corpora. The standard remains experimental.

  - label: s2-enforced-composition-resolution-package-surface
    idea: .megaplan/initiatives/native-workflow-platformization/briefs/s2-enforced-composition-resolution-package-surface.md
    profile: apex
    robustness: extreme
    depth: max
    depends_on:
      - s1-component-standard-extraction-inventory
    notes: >-
      Implement product-neutral validation, lowering, lifecycle, package and
      local-test surfaces against the S1 contract; prove real-store CAS,
      deterministic locks, authority/effect joins and mode isolation before
      product work.

  - label: s3-isolated-extraction-recomposition
    idea: .megaplan/initiatives/native-workflow-platformization/briefs/s3-isolated-extraction-recomposition.md
    profile: partnered-5
    robustness: thorough
    depth: xhigh
    depends_on:
      - s2-enforced-composition-resolution-package-surface
    notes: >-
      Extract the first-wave patterns, make Megaplan consume them, and prove
      concurrent-instance isolation, shape-independent recomposition,
      suspension/cancellation/replay safety, developer iteration and unchanged
      Megaplan golden behavior.

  - label: s4-adversarial-second-consumer-substitutability
    idea: .megaplan/initiatives/native-workflow-platformization/briefs/s4-adversarial-second-consumer-substitutability.md
    profile: apex
    robustness: extreme
    depth: max
    with_prep: true
    depends_on:
      - s3-isolated-extraction-recomposition
    notes: >-
      Challenge the candidate standard with an unrelated non-Megaplan consumer,
      novel composition shapes and independent implementation; separately prove
      new-instance and resume compatibility, upgrade/migration/quarantine and
      cross-consumer observability.

  - label: s5-certification-evolution-adoption
    idea: .megaplan/initiatives/native-workflow-platformization/briefs/s5-certification-evolution-adoption.md
    profile: premium
    robustness: thorough
    depth: xhigh
    depends_on:
      - s4-adversarial-second-consumer-substitutability
    validate:
      - kind: final_conformance_gate
        validator: scripts/validate_native_workflow_platform_conformance.py
        conformance: docs/arnold/native-workflow-platform-conformance.yaml
        traceability: docs/arnold/native-workflow-platform-traceability.yaml
        proof_map: .megaplan/initiatives/native-workflow-platformization/final-proof-map.json
    notes: >-
      Incorporate the adversarial-consumer changes, freeze and certify the
      stable standard, public exports, evolution rules, DX baselines, registry
      states and content-addressed platform completion manifest. Unproven
      abstractions remain experimental.

on_failure:
  retry: retry_milestone
  escalate: bump_profile
  abort: stop_chain
on_escalate:
  abort: stop_chain

merge_policy: auto
prerequisite_policy: required
validation_policy: required

driver:
  auto_approve: true
  max_iterations: 90
  require_clean_base: true
  robustness: thorough
  poll_sleep: 8.0
```

### Why these profiles

- S1 is `apex`: it freezes contracts every later sprint implements.
- S2 is `apex`: it implements authority/effect/concurrency invariants and the
  reusable runtime hinge.
- S3 is `partnered-5`: it is broad and difficult, but predominantly extraction
  and proof against already frozen contracts.
- S4 is `apex`: it is an adversarial architecture review with permission to
  revise the candidate standard before stability.
- S5 is `premium`: it is production-critical publication/certification work,
  but the architectural decisions should already have been resolved by S4.

No `vendor` should be set on an `apex` milestone because that profile is
vendor-locked. `depends_on` does not schedule a DAG: the loader treats it as a
topological assertion and the chain always runs serially in listed order.

## Brief contracts

Every brief should contain: outcome; predecessor artifacts consumed; locked
decisions; in-scope work; executable gates; completion receipts/proof-map
entries; explicit anti-scope; files/touchpoints; and handoff to the next stage.

### S1

Carry all ticket decisions under **Component standard and extraction
inventory**, including the inherited Native Parity handoff, descriptor and
authoring profiles, modes/severities, source/manifest ownership, lifecycle,
root hosting, outcome conditions, human timeout graph, composition and resource
algebra, identity, trace contract, evolution, capability closure, DX baselines,
negative corpus and executable reference transition models. It must produce the
candidate standard and the conformance/traceability skeletons named by S5.

Its semantic exit is an executable contract with failures against current gaps,
not merely prose. Its adoption exit is deliberately only `experimental`.

### S2

Carry all **Enforced composition, resolution and package surface** decisions:
common lifecycle/lowering, validators before authority, local test kit,
preview/sandbox/comparison isolation, root-host adapter, human/outcome CAS,
durable composition primitives, source maps, namespaces, loop ledgers,
JoinPolicy/resource enforcement, RA/Custody/WBC bindings, component locks,
manifest evolution, declared effect protocol, partial-order comparator,
clean-wheel/cloud resolution and independent-client production CAS tests.

S2 must not publish stable patterns or invent product semantics.

### S3

Carry the four first-wave candidates and all **isolation and recomposition**
proofs from the ticket. Preserve the rule that product-specific planning,
critique, gate, finalization and task semantics stay in Megaplan unless a real
second consumer proves otherwise. The small agentic fixture is a conformance
fixture; do not generalize a nonexistent Megaplan consumer as a stable product
pattern.

### S4

Carry every **adversarial second consumer and substitutability** decision. The
second consumer must be intentionally different in domain types, outcomes,
storage/effects, root mapping, human-timeout and join/resource policies, and
composition shape. It must exercise both compatibility claims separately and
may force changes/removals in the candidate standard. Passing S4 does not itself
publish stability.

### S5

Carry all **certification, evolution and adoption** decisions and every blocking
closure clause. It owns the validator/conformance/traceability/proof-map files
declared by `chain.yaml`, stable registry transitions and the completion
manifest. It may certify only profiles selected by mechanically derived
effective capability closure. Preview/comparison evidence cannot be promoted by
relabeling.

## Failure and launch semantics

- `chain_completed + require_manifest: true` is the real predecessor gate. It
  verifies current prerequisite chain hash, milestone set/state, completion
  evidence and the content-addressed manifest rather than accepting a marker.
- The explicit handoff-manifest check fails clearly if the predecessor is
  nominally complete but omitted the Platformization payload. Fix S7/upstream;
  do not locally synthesize it in Platformization.
- `git_tracked` prevents launching an edited/uncommitted epic contract.
- `retry_milestone` is bounded by the chain autonomy ladder; after retry
  exhaustion, `bump_profile` is attempted and the terminal disposition is
  `stop_chain`. Prior successful milestones remain durable.
- `merge_policy: auto` allows a clean unattended/cloud chain to advance. A
  review/manual policy should be used only if the user later explicitly asks
  for a human PR gate at every milestone.
- `prerequisite_policy: required` and `validation_policy: required` make missing
  predecessor and final-proof evidence blocking.
- This chain should currently be **prepared but launch-blocked** because Native
  Parity has not produced its completion and handoff manifests. That failure is
  a feature, not a readiness defect.

## Safe final validation without launch

1. Parse through the real loader and assert the serial dependency graph, final
   validation declaration and policy values. Do not hand-wave with generic YAML
   parsing alone.
2. Check that `NORTHSTAR.md`, `PLATFORM_CONTRACT.md` and all five briefs exist,
   and that every brief cites the contract and its predecessor/handoff.
3. Assert that `load_chain_state(spec_path)` is pristine: index `-1`, no current
   plan, no completed milestones. Loading an absent state is read-only.
4. Run `megaplan chain verify --spec ...`. Before Native Parity completes, this
   must fail specifically with `launch_precondition_failed` on the predecessor
   completion/handoff evidence. Any YAML, anchor or idea-path error is a real
   defect. Do not weaken or temporarily remove launch preconditions to get a
   green command.
5. Run the focused loader/precondition tests and Markdown/whitespace checks:

   ```bash
   pytest -q tests/arnold_pipelines/megaplan/test_chain_launch_preconditions.py
   git diff --check -- \
     .megaplan/initiatives/native-workflow-platformization \
     .megaplan/tickets/01KY2DWSJG0B9YKAJRYA0107XE-build-a-reusable-native-workflow-pattern-platform-after-megaplan-parity.md
   ```

6. Confirm no new plan directory and no chain-state file for the new spec were
   created. Never run `megaplan chain start`, `megaplan init`, or `megaplan
   chain manifest` as part of preparation.

At the future launch boundary, rerun `chain verify`; it must then be fully green
after the predecessor completion manifest, handoff manifest and committed clean
initiative all exist. Only then may an operator explicitly run `chain start`.

## Loader/schema observations that should shape implementation

- The chain loader rejects unknown top-level, launch-precondition and milestone
  validation keys. Keep descriptive material in `notes` or briefs.
- The only supported `validate.kind` is `final_conformance_gate`, and it may
  appear only on the final milestone.
- `validate` paths are declared before their artifacts exist; S1/S5 must create
  them before the final milestone is evaluated. The proof map is intentionally
  absent at preparation time.
- `launch_preconditions` support only `artifact`, `git_tracked` and
  `chain_completed`; artifact checks are `exists`, `contains_text` or
  `review_log_clean`. There is no arbitrary command precondition.
- `validate_paths()` also evaluates launch preconditions. For prelaunch static
  validation, load the spec and inspect anchor/idea paths separately, then run
  the full verifier and assert the expected prerequisite failure.
- The current loader accepts the named profiles above. `apex` is vendor-locked;
  do not attach `vendor` or `critic` overrides to it.

