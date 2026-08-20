# Workflow standardization gap review

## Verdict

Assuming Custody Control Plane M11, the Native Parity epic, and the Workflow
Platformization ticket are all completed exactly as written, Arnold will have a
strong native execution substrate and several genuinely shared pattern
implementations. It will **not yet have a complete component standard** under
which arbitrary workflows, subworkflows, and steps can be decomposed,
recomposed in different shapes, upgraded, and substituted without semantic
drift.

The current work proves three important but narrower things:

1. Megaplan's authored topology is the sole owner of Megaplan semantics.
2. Generic native primitives preserve authority, custody, evidence, identity,
   retry, suspension, effect, and terminal facts through execution.
3. A second workflow can reuse the same extracted implementations from clean
   wheels without importing Megaplan.

Those are necessary. They do not, by themselves, define the execution ABI and
composition algebra of a reusable workflow component. The decisive gap is not
another missing pattern. It is the absence of one normative contract that says
what a `step`, `subworkflow`, and `workflow` are at their boundaries, how their
lifecycles nest, how control and failure propagate, what compatibility means,
and how substitutability is certified.

The existing second-consumer proof is therefore strong evidence against
Megaplan coupling and source copying, but weak evidence of behavioral
substitutability. Two consumers can successfully call the same implementation
while depending on undocumented lifecycle, ambient state, adapter, outcome,
or version-resolution behavior.

## Coverage classification

### A. Fully covered by Native Parity

Native Parity is unusually strong on the semantics of one product and on the
generic mechanisms needed beneath reusable components:

- source-authoritative Python topology, with legacy route carriers made inert;
- product-neutral decisions, bounded loops, dynamic map/reducer, deterministic
  child identity, per-item retry/fallback, human suspension/reentry,
  checkpoints, effects, and terminal arbitration;
- typed decisions/outcomes and call-site policy visibility;
- explicit semantic, Run Authority, WBC, and Custody identity domains;
- exact accepted-decision/consumed-transition equality;
- current grant/fence plus lease/epoch validation and exact-version WBC
  evidence at authoritative boundaries;
- checkpoint and action binding to program, policy, WBC-contract, and installed
  artifact digests, including stale-worker rejection and explicit drift paths;
- durable effect intent/outcome, ambiguity, reconciliation, and no-dual-write
  migration;
- ordered/partial-order, multiplicity-preserving, same-run golden traces;
- checkout/wheel/cloud parity, static negative mutations, and a fail-closed
  proof map;
- readable topology, local policy, closed vocabularies, generated mechanical
  bindings, and bounded edit locality;
- causal observation/explanation that cannot become authority.

This is enough to standardize the *core runtime facts*. It also covers concrete
Megaplan instances of nesting, fanout, retry, human gates, effects, rework, and
terminal races. It does not claim to standardize every reusable component
boundary, and its non-goals correctly avoid doing so.

### B. Explicitly covered by the Workflow Platformization ticket

The follow-on ticket explicitly adds:

- a reusable step/subworkflow manifest covering typed ports/outcomes,
  capabilities, effects/compensations, suspension/reentry, identity, policy,
  boundary version, and extension points;
- dependency-direction classification and reverse-import checks;
- a shared reusable-pattern package with stable exports/discovery;
- policy, effect, capability, and native `.pypeline` composition surfaces;
- generated RA/Custody/WBC bindings instead of handwritten platform IDs;
- clean-wheel execution;
- extraction of proven evaluator, refinement, human-gate, and effect-safe
  patterns;
- unchanged normalized Megaplan traces after extraction;
- a non-Megaplan consumer with different types, outcomes, artifacts, policies,
  effects, and storage;
- zero Megaplan imports and no copied pattern implementation;
- public exports, documentation, examples, compatibility, versioning,
  deprecation, readability/edit-locality rules, and a pattern registry.

This directly addresses source-level reuse and clean-wheel reuse. It also
correctly leaves product planning, critique, finalization, task semantics, and
consumer outcome vocabularies in product packages unless a second consumer
proves a shared abstraction.

### C. Still missing or underspecified

#### C1. A normative component execution lifecycle — blocking

The manifest field list does not define a single lifecycle state machine for a
step, subworkflow, and workflow. It is unclear which transitions are common,
which are legal at each nesting level, and exactly when authority/custody/WBC
validation, body execution, checkpointing, retry, suspension, compensation,
cancellation, and terminal acceptance occur.

Without this, moving a callable from top-level step to nested subworkflow can
change retry scope, authority acquisition, custody target, checkpoint
granularity, effect reconciliation, or terminal behavior. That defeats
shape-independent recomposition.

Smallest amendment: in Platformization S1, define one versioned component
lifecycle protocol with required transition preconditions and observable
events. Distinguish step terminal, subworkflow typed return, and root workflow
terminal. In S2, make the runtime enforce it for every component kind.

Blocking gate: the same component run at root, nested one level, and nested
inside fanout produces the contractually equivalent local lifecycle, with only
declared parent/namespace differences.

#### C2. Composition algebra and control-propagation rules — blocking

The ticket says components compose in `.pypeline`, but does not specify the
meaning of composition. Missing rules include:

- how parent inputs bind to child ports and child outcomes bind to parent
  decisions;
- whether subworkflow outcomes return, bubble, or may terminate the root;
- how cancellation, deadline, retry exhaustion, suspension, and failure
  propagate across nesting;
- whether retrying a subworkflow repeats completed children or resumes it;
- how fanout sibling failure, cancellation, fallback, and reducer admission
  interact;
- whether a child may checkpoint independently of its parent and how both
  cursors join;
- how compensation scope nests;
- which context is inherited, overridden, or forbidden.

Without closed rules, source pieces are reusable only in the arrangement in
which they were extracted.

Smallest amendment: make S1 publish a composition semantics table and a small
formal/reference transition model; make S2 lower every composition to it.

Blocking gate: a recomposition matrix runs the same component sequentially,
as a nested subflow, under a bounded loop, in fanout/fanin, across suspension,
and under parent cancellation, with declared and invariant outcomes.

#### C3. Typed-port compatibility is named but not defined — blocking

“Typed ports/outcomes” is insufficient unless the plan fixes what counts as a
contract. Python annotations alone do not standardize runtime serialization,
validation, optional/default fields, generics, variance, outcome exhaustiveness,
schema evolution, or durable state compatibility.

This blocks independent packaging: two clean wheels may type-check locally yet
disagree over serialized state or outcome versions at resume time.

Smallest amendment: S1 defines canonical port/outcome/state schemas, qualified
type identity, serialization and validation rules, compatibility classes
(backward, forward, breaking), and closed-outcome exhaustiveness. S5 governs
their evolution.

Blocking gate: compatible producer/consumer versions compose; missing ports,
unhandled outcomes, incompatible schema changes, and unserializable durable
state fail statically or before authority acquisition.

#### C4. Durable state ownership and isolation — blocking

The ticket calls for hidden-global-state checks, but does not define component
state ownership. It needs explicit rules for state namespace, artifacts,
checkpoints, caches, idempotency keys, leases, effects, and child IDs when the
same component appears twice or is reused concurrently.

Otherwise two instances can collide, leak state, or accidentally resume each
other; that makes decomposition unsafe even when imports are clean.

Smallest amendment: S1 adds declared state/artifact/effect namespaces and a
“no ambient mutable authority” rule. S2 derives them from composition path plus
semantic instance key. S3 runs extracted patterns under duplicate and
concurrent instantiation.

Blocking gate: two differently configured instances and two concurrent copies
cannot observe, consume, resume, cancel, or reconcile one another's state or
effects unless an explicit shared resource port declares that relationship.

#### C5. Dependency injection and policy precedence — blocking

The ticket permits consumers to bind policies, capabilities, storage, and
effects, but does not define a standard binding model. It lacks required versus
optional dependencies, lexical scope, override precedence, default ownership,
capability narrowing, effect adapter identity, and how bindings enter digests.

Undocumented ambient lookup or precedence is semantic drift: the same package
can behave differently solely because it was embedded in a different parent.

Smallest amendment: S1 defines an explicit binding environment with typed
required slots and deterministic precedence; S2 makes bindings inspectable and
digest-bound; S3 removes ambient product defaults from extracted patterns.

Blocking gate: every runtime dependency is derivable from the component
descriptor plus explicit composition bindings; changing a binding changes the
declared policy/program digest or fails admission.

#### C6. Package identity, dependency resolution, and compatibility — blocking

Stable exports, discovery, versioning, and deprecation are listed, but the
ticket does not define qualified component IDs, transitive dependency
resolution, lock manifests, version-range semantics, duplicate-version policy,
artifact provenance, or compatibility with active checkpoints. Clean-wheel
proof only shows installation; it does not prove deterministic resolution.

Without a closed package identity, `review_cycle` can resolve to different code
or contracts on different workers, or an upgrade can strand a suspended run.

Smallest amendment: S2 creates qualified component identity
`(package, component, contract version, implementation digest)`, a resolved
dependency lock included in program/checkpoint digests, and fail-closed
resolution. S5 defines compatible upgrade, deprecation, and checkpoint
migration policy.

Blocking gate: checkout and clean wheels with the same lock select identical
components; conflicting or unavailable constraints fail before execution; an
active checkpoint resumes pinned code or takes an explicit migration/new-run
path.

#### C7. Static composition validation — blocking

Native Parity validates its known semantic matrix, but the follow-on ticket
does not promise a generic validator for arbitrary consumer compositions. A
platform needs compile-time checks for:

- port and outcome compatibility;
- unhandled typed exits and illegal root terminals;
- undeclared effects, capabilities, policies, and persistent state;
- illegal cycles or unbounded recursion;
- unsupported nesting of suspension, retry, fanout, compensation, and terminal
  constructs;
- non-deterministic or position-derived identity;
- namespace collisions;
- incompatible dependency/boundary versions;
- hidden imports and ambient route ownership.

Smallest amendment: S2 adds a product-neutral `validate_component` and
`validate_composition` pass whose receipt is required before lowering and
authority acquisition.

Blocking gate: a negative corpus mutating each rule fails closed without
executing a product body.

#### C8. Behavioral substitutability and conformance certification — blocking

The second consumer proves shared source and parameterizability, not that one
conforming implementation can replace another or that the same component keeps
its contract under a different composition shape. “Unchanged normalized
Megaplan traces” tests extraction fidelity only.

Smallest amendment: strengthen S4 from a usage demo to a conformance exercise.
The non-Megaplan consumer must use at least two shared patterns in shapes not
used by Megaplan. At least one pattern must have a small independent conforming
test implementation swapped in, and one compatible version upgrade. Both must
pass the same black-box contract suite. No third production consumer is
required.

Blocking gate: descriptor-compatible implementations are observationally
substitutable at declared ports, lifecycle events, decisions, effects,
checkpoints, and terminals; undeclared trace differences fail.

#### C9. A portable observability/evidence envelope — later hardening, with a
blocking minimum

Native Parity has excellent Megaplan-specific golden traces and the ticket
hands off source-to-runtime adapters. It does not state which normalized events
and causal joins are mandatory for every reusable component, or how
consumer-specific events extend them without breaking generic tooling.

Minimum needed for launch: S1 standardizes the component instance, parent,
port, lifecycle, decision, authority, custody, WBC, checkpoint, effect, and
terminal envelope. S4 proves cross-consumer querying. Rich dashboards and
domain-specific explanation remain later work.

Blocking minimum gate: generic tools can reconstruct one component's causal
history from either consumer without importing consumer code.

#### C10. Extension and compatibility governance — later hardening

S5 lists public exports, versioning, compatibility, and deprecation, but not
who classifies changes, what compatibility promises apply to manifests versus
Python APIs versus durable state, how long deprecations last, or what evidence
is required to publish a pattern version.

Smallest amendment: S5 defines change classes, required conformance evidence,
deprecation/migration windows, registry states (experimental/stable/deprecated/
withdrawn), and an exception process. Publication requires a content-addressed
conformance manifest.

#### C11. Resource, deadline, and cancellation context — blocking semantics;
variable policy values

Timeout/retry/cap policy exists, but reusable nesting needs standard propagation
rules for deadlines, cancellation tokens, worker budgets, and fanout limits.
The actual values should remain consumer policy. The propagation and narrowing
rules cannot.

Smallest amendment: include resource/cancellation context in C1/C2, with child
budgets no broader than the parent unless explicitly authorized. Test parent
cancel during fanout, suspension, retry backoff, and effect ambiguity.

### D. Deliberately variable rather than standardized

Standardization should preserve these extension points:

- product domain types and business meaning;
- product-specific outcome vocabularies, so long as they bind to declared
  closed ports;
- policy values such as retry counts, models, timeouts, worker caps, review
  thresholds, and escalation choices;
- effect implementations, external systems, storage layout, and artifact
  formats behind typed contracts;
- scheduler implementation, parallel sibling wall-clock interleaving, worker
  placement, and transport, provided causal and multiplicity invariants hold;
- UUID formats, physical database tables, hash algorithms, decorator spelling,
  process/container boundaries, and projection UI;
- internal compiler APIs until they become documented public composition
  surfaces;
- whether product-specific phases are exposed as reusable patterns at all;
- performance and cost characteristics unless a component explicitly publishes
  an SLO/resource contract.

The platform should standardize *where variability is declared and how it is
bound*, not collapse these choices into universal defaults.

## Source reuse, wheel reuse, and substitutability

These must be separate completion claims:

| Claim | Existing plans after completion | What it proves |
| --- | --- | --- |
| Source-level reuse | Covered | Both products call the same implementation; no copy or Megaplan import |
| Clean-wheel reuse | Covered | Independently installed packages can import and execute the shared code |
| Deterministic dependency reuse | Missing | Every host resolves the same qualified component/dependency graph |
| Shape-independent reuse | Missing | Nesting, fanout, looping, retry, and cancellation do not silently change the component contract |
| Behavioral substitutability | Missing | A compatible implementation/version can replace another under the same black-box contract |

The platform should not call itself compositionally standardized until all five
claims are separately green.

## Minimal amendments to the proposed five sprints

No extra epic is necessary. The smallest coherent revision is to sharpen the
existing five sprints:

### S1 — add the standardization closure contract

- Freeze Component Descriptor v1 and a component-kind-neutral lifecycle.
- Define composition/control propagation, typed schema compatibility, explicit
  dependency bindings, namespace/isolation, and portable evidence events.
- Classify invariants versus consumer-supplied policy.

Gate S1 on a reference model plus invalid-descriptor/composition corpus, not
only a prose manifest.

### S2 — enforce the contract in compiler/runtime/package resolution

- Add generic static validation.
- Lower every component kind through the common execution protocol.
- Generate namespace, identity, RA/Custody/WBC, and binding records.
- Resolve qualified components from a content-addressed dependency lock.
- Bind the resolved graph into program and checkpoint digests.

Gate S2 on root/nested/fanout lifecycle equivalence, negative admission tests,
and reproducible clean-wheel resolution.

### S3 — extract under isolation and recomposition proof

- Make extracted patterns free of ambient product state/defaults.
- Instantiate the same pattern twice, concurrently, with distinct bindings.
- Recompose each first-wave pattern in at least two supported shapes.
- Preserve Megaplan traces while also passing generic component conformance.

### S4 — make the second consumer adversarial

- Use at least two patterns in arrangements Megaplan does not use.
- Exercise different port schemas, outcome vocabulary, nesting, suspension,
  cancellation, retry scope, effect adapter, and storage namespace.
- Swap one conforming implementation and perform one compatible package/state
  upgrade.
- Prove generic causal explanation without consumer imports.

### S5 — certify and govern

- Publish compatibility/change classes and checkpoint migration rules.
- Establish registry states and content-addressed dependency/conformance
  manifests.
- Require the complete standardization acceptance suite for stable status.
- Keep compiler internals and unproven product abstractions explicitly
  experimental.

## Compact standardization closure contract

Platformization should be incomplete unless all of the following are true:

1. **Descriptor:** every exported step/subworkflow/workflow has a qualified,
   versioned descriptor declaring kind, typed input/output/outcome/state schemas,
   dependencies, capabilities, policies, effects/compensations, suspension,
   identity, and extension points.
2. **Lifecycle:** every component kind executes through one closed protocol;
   legal nesting, retry, suspend/resume, cancel, compensate, and terminal
   transitions are explicit and enforced.
3. **Composition:** all bindings and control propagation are explicit; port,
   outcome, scope, deadline, cancellation, and namespace rules are statically
   checkable.
4. **Isolation:** component instances own disjoint state, checkpoint, artifact,
   identity, custody, and effect namespaces unless an explicit shared port says
   otherwise; no ambient mutable route or authority exists.
5. **Authority and evidence:** every authority-increasing boundary uses the
   generated RA/Custody/WBC integration and exact executable/dependency digests;
   evidence remains non-authoritative.
6. **Resolution:** execution uses a content-addressed component/dependency lock;
   incompatible or unavailable contracts fail before product work.
7. **Evolution:** compatible versus breaking changes are defined for Python
   API, descriptor, serialized state, checkpoints, effects, and traces; active
   runs pin or explicitly migrate.
8. **Observation:** a product-neutral event envelope explains component-local
   and parent/child causality across consumers.
9. **Conformance:** every stable component passes static, lifecycle, isolation,
   recomposition, fault, clean-wheel, upgrade, and substitution tests.
10. **Variability:** domain meaning, policies, implementations, and storage are
    consumer-owned only through declared bindings; changing them cannot mutate
    shared internals or hidden global defaults.

## Acceptance suite

The final gate should consume a common, versioned suite with at least these
families:

1. **Descriptor/static:** missing port, unhandled outcome, undeclared effect,
   illegal cycle/nesting, namespace collision, incompatible contract, hidden
   product import, hidden global state, and unserializable durable state all
   fail before authority acquisition.
2. **Decompose/reinsert:** extract a nested section into a subworkflow and
   inline it again; normalized observable behavior and declared identities are
   equivalent modulo the explicit namespace boundary.
3. **Recomposition matrix:** run a component at root, nested, sequentially,
   under a bounded loop, in fanout/fanin, across human suspension, and under
   parent cancellation/retry.
4. **Isolation:** duplicate and concurrent instances with different bindings
   cannot cross-read state, checkpoints, effects, custody, or outcomes.
5. **Lifecycle faults:** crash before/after admission, body, checkpoint, effect
   intent/outcome, suspension, resume, compensation, and terminal acceptance;
   the protocol yields one allowed history.
6. **Authority/custody/WBC negatives:** stale or missing grants, fences, leases,
   epochs, boundaries, digests, or dependency locks reject before action;
   projections and receipts cannot authorize.
7. **Version resolution:** checkout, clean wheels, and cloud select the same
   locked graph; transitive conflict and mixed worker versions fail closed.
8. **Checkpoint evolution:** compatible resume, pinned-old resume, explicit
   migration, and breaking-change quarantine each follow the declared path.
9. **Substitution:** swap a conforming implementation and compatible version;
   declared ports, lifecycle, decisions, effects, checkpoints, and terminals
   remain observationally compatible.
10. **Cross-consumer evidence:** generic tooling reconstructs causal component
    history for Megaplan and the unrelated workflow without importing either.
11. **Policy variability:** different consumer policies/effects/types alter
    only declared outcomes and digests; shared code and protocol invariants stay
    unchanged.
12. **Registry/governance:** only artifacts with valid content-addressed
    conformance manifests can be marked stable; deprecated/withdrawn or
    incompatible versions produce the specified diagnostics.

## Priority

The blockers before calling the platform compositionally standardized are C1
through C8, the minimum event envelope in C9, and cancellation/deadline
propagation in C11. C10 and richer C9 capabilities can mature after initial
platform completion, provided the stable registry already records contract and
conformance versions.

The philosophical correction is small but important: do not define reuse as
“the same Python callable can be imported twice.” Define it as “a qualified,
contracted component retains its declared semantics when its parent, shape,
package boundary, host, version, policy, and implementation vary within the
explicitly supported ranges.”
