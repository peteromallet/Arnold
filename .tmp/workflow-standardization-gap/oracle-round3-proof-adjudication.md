# Oracle round 3: proof-system and feasibility adjudication

Status: advisory amendment memo; no authoritative plan files edited  
Scope: Oracle Q2 false-green implementations plus the Q3 claims about S1
checker dependencies and assumed M11 capabilities

## Executive verdict

All three Q2 attacks expose real proof-scope gaps, but two of the Oracle's
proposed remedies need narrowing:

1. **Arbitration closure is genuinely unproved.** The plan proves the named
   cancel/publish/deliver/terminal family, but does not mechanically prove that
   every arbitration site emitted by the Native lowerer is declared and tested.
   Add a lowered-IR arbitration inventory and per-cutover coverage receipt. Do
   not wait until GO-3 to discover an unindexed site that was already made live.
2. **Native durable-state restore coverage is genuinely unproved.** The M11
   receipt covers accepted M11 stores, not arbitrary Native side tables. The
   right rule is not “give every Native authority side table its own recovery
   scheme.” Native-local stores must never own grant/decision consumption,
   custody, WBC/effect truth, or other action authority. Inventory every durable
   Native record, map it to the accepted M11 transactional/restore boundary or
   classify it as immutable/rebuildable/non-authoritative, and restore-drill
   every route-relevant class. A Native decision-consumption index outside M11
   is a blocking architecture violation, not an acceptable alternative store.
3. **The trace normalizer can currently launder multiplicity.** Exact
   multiplicity is normative, but the plan does not bind raw journal identity
   through normalization or establish operational independence of the
   verifier. Require one-to-one raw-event provenance and an independently
   implemented raw-level verifier. Two fully disjoint normalization stacks are
   unnecessary; shared parsers/canonical serialization are acceptable, but the
   producer and verifier must not share event filtering, folding, or
   cardinality logic.

The Q3 S1 circularity claim is **mostly false**. S1 can and should execute the
oracle against synthetic mutation fixtures and the known-red current
implementation; target runtime integration correctly waits for S2/GO-0. This
boundary should be stated explicitly, but the S1 normalizer should not be
demoted to prose.

The M11 feature concern is **valid as an admission-capability concern**, but the
packet cannot establish which features are absent because it does not contain
the accepted M11 manifest/API bundle. S1 needs executable capability probes,
not assumptions inferred from a completion label. Missing capabilities bounce
back to an M11 point release; Native Parity must not emulate them locally.

No eighth sprint is justified by these findings. They are proof obligations
that must attach to S1, S2/GO-0, the owning cutover, and final GO-4 consumption.

## Baseline already present

The plan is not starting from zero:

- S1 already owns an executable ordered/partial-order and multiset schema,
  normalizer, same-run predicates, mutation interface, and all six scenario
  skeletons (`megaplan-native-parity-corrective-plan.md`, S1; lines 383-424).
- The golden contract requires exact occurrence/child multiplicity and one-run
  ordered/partial-order proof, and S1 must check in an executable oracle
  (`GOLDEN_TRACE_CONTRACT.md`, §§4-5 and §8).
- S1 already defines the per-cutover union-of-writers receipt; every old and
  candidate action/effect path must cross one M11 validator, with one admitted
  decision consumer/history writer (`plan`, lines 713-718; S1 brief, lines
  115-121).
- M11 admission already demands restore-resistant RA fences/Custody epochs and
  canonical repair revalidation (`plan`, lines 44-67), while Native explicitly
  forbids parallel grant/lease/attempt stores and recovery machinery (`plan`,
  lines 315-332).
- S6 and NP-GT-006A/B/C prove one closed product terminal arbitration family;
  blocking regression 18 currently names only that family.

Those controls stop several simpler false greens. They do not establish that
the proof scopes are complete.

## Q2-A: arbitration correct only for the tested triple

### Adjudication: genuine gap

The representation report says every family of competing transitions must have
a versioned policy index, but the Native plan's executable proof is centered on
NP-GT-006A/B/C. Nothing currently establishes equality among:

```text
arbitration sites emitted by lowering
= sites in the normative arbitration index
= sites with executable forced-race fixtures
= sites observed at runtime
```

Consequently a runtime can correctly implement the named terminal triple and
fall back to mutex arrival order for budget/publish, reconfigure/cancel,
migration/deadline, or another emitted site.

### Smallest blocking amendment

Define a machine-readable `arbitration_site` record in S1:

```text
site semantic identity
policy id/version
closed participant transition vocabulary
precondition/CAS key
winner, loser, late-arrival dispositions
required retained facts
owning cutover/gate
forced-race fixture IDs
```

S2 makes the product-neutral lowerer emit that record and adds a checker for
exact set equality between lowered sites and declared policies/fixtures. The
neutral pipeline proves at least one non-terminal arbitration family, including
both release orders at the pre-CAS barrier.

Every product cutover then consumes the subset it makes live:

- **S3 internal stop/go and GO-1:** all arbitration sites in the migrated
  prep/plan/front-half slice;
- **GO-2:** effect ambiguity/cancel/retry sites reachable from live effect
  authority;
- **S6/GO-3:** the complete remaining product control/race matrix, including
  NP-GT-006A/B/C;
- **S7/GO-4:** exact equality across lowered inventory, policy index, fixture
  receipts, and runtime-observed sites.

For each participant pair, force both release orders from a barrier immediately
before the authoritative CAS. The accepted result and retained loser facts must
be policy-identical. Pairwise coverage is enough; exhaustive permutation of
every multi-party race is not generally required unless the policy declares a
non-associative multi-party rule.

### What not to do

- Do not scope this to every theoretical Stage-2 `JoinPolicy`; Native Parity
  must close only sites emitted or reachable by its admitted program and generic
  primitives.
- Do not put the first executable completeness check only at GO-3. That would
  allow an unindexed front-half or effect race to become live at GO-1/GO-2.
- Do not derive participants only by scanning CAS calls in Python source. The
  normative inventory must come from lowered semantic transition metadata and
  be joined to runtime CAS observations; helper-level source scanning is an
  additional negative check, not the authority.

## Q2-B: Native decision-consumption state outside the M11 restore boundary

### Adjudication: genuine gap, but the proposed fallback is too permissive

The accepted M11 prerequisite proves M11 store recovery. It does not
automatically cover a Native comparison registry, proof registry, loop ledger,
checkpoint index, decision-consumption index, or resume-selector table. The
current plan derives durable namespaces and says checkpoints use M11
facilities, but does not produce an exhaustive inventory showing the recovery
class and authority effect of every newly durable Native record.

The Oracle's example of an accepted RA decision stored in M11 but a Native
consumption bit stored elsewhere is a real wrong-action path after rollback.
However, permitting such a table merely because it passes a Native-specific
restore drill would violate the one exact authority-decision history and the
no-parallel-store boundary.

### Smallest blocking amendment

S1 extends its no-duplication dependency map to a **durable-state ownership and
restore matrix**. Every durable record is assigned exactly one class:

1. **M11 canonical/transactional:** accepted authority decisions and
   consumption CAS, WBC attempts/effects, Custody leases/epochs, authoritative
   checkpoints/reentry admission, and other facts whose rollback could permit
   an action. These must use an exact accepted M11 API/store/transaction or a
   versioned M11 extension explicitly covered by the completion proof.
2. **Native route-relevant semantic state:** loop ledgers, generation counters,
   reducer consumption, resume selectors, and typed configuration generations.
   Each must be transactionally joined to M11 decision/checkpoint acceptance or
   bind an M11 restore/incarnation token that makes a restored stale record fail
   closed before a new decision/action. S1 admission must prove the accepted
   M11 surface supports this; Native may not invent a local restore authority.
3. **Immutable content-addressed artifacts:** source, wheels, locks, prompts,
   schemas, and payload artifacts. Restore proof is digest/retrievability and
   pin retention, not monotonic CAS.
4. **Rebuildable/non-authoritative data:** projections, explanations, comparison
   artifacts, and proof views. Rollback/deletion may lose observations but can
   never permit dispatch, resume, route, terminal, or effect. Rebuild and forged
   data remain inert.
5. **Forbidden:** any Native-local table that independently owns grant,
   decision consumption, lease/epoch, WBC/effect truth, or executable action
   admission.

S2/GO-0 runs rollback-then-replay drills for each generic route-relevant class
used by the neutral pipeline. The owning product sprint adds its concrete state
classes. GO-4 consumes the complete inventory and restore receipts and fails on
any unclassified durable writer/store.

The core mutation is:

```text
accept decision / consume transition / advance semantic ledger
snapshot an older Native store image
restore that image while the accepted M11 history remains current
restart/replay on another host
=> no prior decision is consumable again; no earlier generation can route;
   reconciliation or quarantine is explicit
```

If route-relevant Native state cannot be made safe using the accepted M11
restore/incarnation/transaction surface, that is a missing M11 capability and
blocks launch or requires an M11 point release. It is not a license for a
Megaplan-local epoch.

### Gate ownership

- **S1 launch/admission:** inventory, classification, exact M11 API binding, and
  capability proof.
- **S2/GO-0:** generic restore/replay drills before product migration.
- **S3-S6 owning cutovers:** concrete record types must be added before their
  writers become authoritative.
- **S7/GO-4:** complete inventory equality, restore receipt consumption, and an
  unregistered-side-table negative.

## Q2-C: shared normalizer collapses duplicates

### Adjudication: genuine gap

The golden contract forbids loss of multiplicity, but the proof begins after a
fixture adapter has normalized storage events. A buggy or complicit adapter can
collapse duplicate raw events before the multiplicity predicate sees them. The
report says a producer cannot be its sole verifier, but does not operationally
bar shared filtering/folding code between producer and verifier.

### Smallest blocking amendment

S1 freezes a **raw-to-normalized conservation contract**:

- Each admitted raw event has immutable source-store identity, store cursor,
  schema version, and raw payload digest.
- Every normalized event carries one source-event reference. For the Native
  lifecycle vocabulary, event folding, deduplication, and one-to-many synthesis
  are forbidden. If a storage schema genuinely needs composition, the mapping
  is an explicit versioned exception with all source IDs retained and a
  conservation equation; it cannot be called volatile-field normalization.
- Volatile normalization may remove or canonicalize only fields named by the
  versioned golden contract. Unknown fields are rejected/classified, not
  silently dropped.
- Before semantic comparison, a raw-preservation verifier checks source cursor
  continuity and exact multiset equality between in-scope raw event IDs and
  normalized source references.
- Mutations are injected into the raw export/store boundary, before the primary
  adapter: duplicate, drop, reorder, schema substitution, and forged source ID.

Add an independent audit implementation that reads the raw export directly and
recomputes the conservation/multiplicity/causality predicates. Its executable
and source digest are separately bound in the proof map. It must not import or
call the production fixture adapter's event-selection, fold/dedup, or
normalization functions.

Requiring two entirely disjoint stacks is unnecessary and may be impractical.
They may share the normative raw schema, JSON/parser libraries, cryptographic
hash implementation, and canonical serialization. Independence applies to the
claim-producing logic: event inclusion, source-reference mapping, cardinality,
ordering/causality, and verdict derivation. A lock assertion should prove that
the independent verifier does not depend on the production normalizer package
or module; code review/static import checks plus deliberate asymmetric mutation
tests provide stronger evidence than package naming alone.

### Gate ownership

- **S1:** executable primary normalizer on synthetic/red fixtures, raw
  conservation schema, independent-verifier contract and initial
  implementation, raw-level mutation API.
- **S2/GO-0:** both implementations consume one neutral pipeline raw history;
  asymmetric mutations prove either side detects the other's laundering.
- **Each product scenario receipt:** bind the raw export digest, both executable
  digests, raw-preservation result, and normalized result.
- **S7/GO-4:** checkout/wheel/cloud proof consumes raw-level mutations and both
  verdicts. Cross-environment normalized traces need not share physical event
  IDs; preservation is checked within each run, then semantic traces are
  compared across runs.

## Q3: S1 checker/normalizer forward dependency

### Adjudication: mostly unnecessary relocation

S1 explicitly expects the current implementation to remain red. It can execute:

- schema and comparator self-tests;
- synthetic ordered/partial-order/multiplicity fixtures;
- raw duplicate/drop/fold mutations;
- the current 85-to-14 false-pass fixture in checkout and installed form; and
- target scenario skeletons with red placeholders.

None requires S2's dynamic fanout, typed reconfiguration, or agentic runtime to
be implemented. Therefore the Oracle's suggestion to specify the normalizer in
S1 but validate the executable only in GO-0 would weaken S1 and contradict the
existing requirement that the oracle itself be executable.

There is nevertheless a useful two-level closure rule:

1. **S1 oracle validity:** executable against synthetic mutation corpora and the
   known-red current implementation; proves it cannot pass set-only,
   stitched-run, or normalization-laundered evidence.
2. **S2/GO-0 runtime integration:** production lowerer/runtime emit the target
   vocabulary for a neutral composed pipeline; raw adapters, M11 joins, and both
   normalizers produce a green composed receipt.

The source/lowering checker follows the same pattern: in S1 it must correctly
fail the current collapsed lowering and pass controlled minimal fixtures; in
S2 it must pass the completed generic constructs. This is staged validation,
not a circular dependency.

No sprint move is needed. Add explicit S1 and GO-0 acceptance wording so S1
cannot close with prose-only checkers and GO-0 cannot rely solely on synthetic
fixtures.

## Q3: assumed M11 capabilities

### Adjudication: valid capability-audit gap; absence is unproven

The supplied packet explicitly lacks the accepted M11 manifest, API inventory,
and schema bundle. The local `.megaplan/initiatives/custody-control-plane/` is
the older four-milestone initiative and cannot answer whether the future M11
surface provides the needed capabilities. The Oracle is correct that a
manifest hash and broad feature names are insufficient; it is not entitled to
conclude those features are absent.

S1 admission should run version-bound executable probes for:

1. **Controlled-writer integration.** The accepted inventory/validator can
   identify and fail closed writers from all three execution planes, preserve
   one decision consumer/admitted writer, and register concrete legacy and
   candidate writer identities.
2. **Executable-envelope extensibility.** The shared validator can bind and
   validate program/topology, policy, WBC contract, installed artifact,
   dependency lock, prompt/tool, and normalized product-contract semantics,
   whether as named fields or a canonical versioned extension map/transitive
   digest with mutation proof.
3. **Semantic state/checkpoint integration.** Native loop/reducer/reentry state
   can be joined to accepted decision/checkpoint transactions or a fail-closed
   restore generation; a Native-local decision-consumption authority is not
   required.
4. **Exact Custody target representation and capacity.** Target identity can
   represent the run + semantic occurrence + action/effect target without
   collapsing items. A production-scale lease/validator benchmark is frozen at
   S1 and exercised by S2/GO-0 at reference scale and GO-2 at delivery scale.
5. **Comparison isolation disposition.** Either M11 supports an admitted
   `authority_class` excluded by construction, or comparison executes without
   M11 authority/history and writes only a separate inert comparison artifact.
   The literal `authority_class=comparison` field is not itself a mandatory M11
   feature; behavioral exclusion/non-promotion is.
6. **Restore and repair scope.** Exact M11 stores covered by rollback-resistant
   fence/epoch, decision consumption, WBC/checkpoint, and repair-revalidation
   receipts are enumerated, including extension/transaction guarantees used by
   Native.

If any required probe fails, S1 records `blocked_on_m11_capability` with the
missing versioned API/schema/proof and the chain does not start. The fix belongs
in an M11 point release and completion manifest refresh. Native Parity neither
adds a local facade nor silently narrows the proof.

### Plane-writer adapter ownership

The Oracle's proposal to put concrete registration of all three Megaplan planes
in S2 conflicts with S2's product-neutral boundary. Use this split instead:

- **S1:** enumerate every concrete old/candidate writer and prove the M11 API can
  represent/fence each class.
- **S2/GO-0:** implement and prove the generic controlled-writer/action-validator
  binding with neutral writer identities.
- **S3 internal stop/go and GO-1:** register the actual `arnold.execution`,
  native-runtime, and legacy-envelope paths for the migrated slice and prove an
  unregistered concrete path fails before body/effect intent.
- **Later cutovers:** refresh exact union-of-writers equality for their scope.

This is earlier and more precise than the current broad GO-1 wording without
making generic S2 import Megaplan legacy planes.

## Minimal amendment ledger

| Amendment | Earliest owner | First blocking proof | Final consumption |
|---|---|---|---|
| Lowered-IR arbitration-site schema and policy/fixture equality | S1 schema; S2 emitter/checker | GO-0 generic, then each owning cutover | GO-4 |
| Forced pre-CAS pairwise race matrix | S2 neutral primitive; product owner thereafter | GO-1/GO-2/GO-3 by live scope | GO-4 |
| Durable-state ownership/restore matrix | S1 admission | GO-0 generic restore drill | GO-4 |
| Ban Native-local decision/authority consumption stores | S1 architecture/admission | GO-0 negative; each writer cutover | GO-4 |
| Raw-to-normalized event conservation and raw mutations | S1 executable oracle | S1 synthetic/red; GO-0 runtime | Every scenario and GO-4 |
| Independent raw-level verifier with separate claim logic | S1 | GO-0 neutral composed history | GO-4 checkout/wheel/cloud |
| Explicit S1 self-test vs. GO-0 integration split | S1/S2 wording | S1 and GO-0 | Proof map |
| Executable M11 capability checklist and blocked-upstream disposition | S1 launch | S1 admission | Every cutover binds exact receipt |
| Generic writer adapter vs. concrete three-plane registration split | S2 vs. S3 | GO-0 then S3 stop/go/GO-1 | Per-cutover/GO-4 |

## Final recommendation

Absorb these changes into existing sprints and gates. They are not a new body
of product work; they make existing claims closed and independently testable.
The strongest changes are:

```text
lowered arbitration inventory = declared policies = forced-race receipts
durable store inventory = one declared restore/authority class per record
raw journal multiplicity = normalized source-reference multiplicity
M11 completion = executable capability probes, not label/hash acceptance
```

Do not accept three tempting shortcuts: a GO-3-only race test, a separately
restored Native authority side table, or “independent” verification that shares
the production normalizer's filtering/folding code.
