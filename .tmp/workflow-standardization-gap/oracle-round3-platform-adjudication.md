# Oracle Round 3 — Stage 2 Platformization adjudication

## Verdict

The Oracle found seven genuine determinacy gaps and one consequential cross-cutting
clarification. None warrants a sixth Platformization sprint. All are foundational
parts of the component lifecycle, composition algebra, resource ledger, or trace
contract already assigned to Platformization S1–S2; S3–S5 should prove, challenge,
and certify those contracts.

The current ticket is directionally aligned and in one case already stronger than
the report: Platformization S2 says missing business/control result mappings must be
rejected. The report's illustrative root-host example nevertheless omits two
declared lifecycle terminals, so it currently demonstrates a composition that the
ticket would correctly reject. The report and ticket need bounded amendments to
make the intended rules explicit and consistent.

The Oracle's budget-release remedy is the one material over-specification. A
uniform rule of "release only at child terminal or lease expiry" is safe-looking
but wrong for heterogeneous resources. Lease expiry fences Arnold ownership; it
does not prove that a cloud provider, model invocation, or external effect has
stopped accruing cost. The normative rule must be settlement-based and
resource-class-specific.

## Normative resolutions

### 1. Root-host maps are total and statically checked

**Current coverage:** Partially closed. The ticket's S2 implementation section
already requires rejection of a missing business/control mapping. The report's
`release_root_host` example maps all shown business outcomes but only three of the
five lifecycle terminals declared by the component model. Neither artifact states
the totality rule centrally.

**Normative rule:**

1. A root-host adapter has two disjoint, statically typed maps: one over every
   business outcome exported by the hosted root component, and one over every
   applicable lifecycle/control terminal in its descriptor.
2. Both maps are total. Missing entries, catch-all/default entries, and mappings
   from undeclared results are composition-time errors before authority acquisition.
3. Several local results may intentionally map to the same root product terminal,
   but the accepted root record must retain the original result identity and class.
   Mapping `deadline_exhausted` to a product `blocked` terminal must not rewrite the
   event into a business `blocked` outcome or claim that a business-outcome
   condition was satisfied.
4. Root-host mapping only proposes root truth. Terminal-arbitration CAS and current
   RA/Custody/WBC validation remain mandatory.
5. A component declared nested-only has no root-host map and fails static validation
   if placed at root. Root-hostability is an explicit conformance profile.

**Amendments required:** Report §§6.1/6.3 and the illustrative map; ticket S1 must
freeze totality while S2 continues to enforce it. This is not a new feature family.

### 2. Human timeout is a declared, total transition policy

**Current coverage:** Open in the normative contract. The report requires a
timeout/escalation policy and correctly separates internal suspension from returned
business outcomes, but it does not classify timeout expiry. The ticket mentions
human suspension and timeout behavior only indirectly.

**Normative rule:**

1. Every human-gate descriptor declares a closed timeout state machine. At each
   timeout generation the disposition is exactly one of:
   - advance to a named next escalation/suspension generation under pinned policy;
   - emit one declared business outcome whose condition/evidence contract is met;
   - emit one declared lifecycle/control terminal.
2. There is no implicit default from timeout to `deadline_exhausted`, `blocked`, or
   `needs_human`, and no handler callback may invent a disposition.
3. The timeout state machine must be total and bounded, or must carry a declared
   overall deadline that yields a named terminal. An indefinitely renewed ambient
   wait is invalid.
4. A human answer racing timeout/escalation uses a declared CAS arbitration rule.
   The winner is consumed once; non-winning answers/timeouts remain rejected-late
   facts.
5. Internal suspension remains a lifecycle transition. A product may expose an
   escalation or unanswered business outcome, but only by declaring it explicitly;
   this does not turn every suspension into a business result.

The Oracle's narrower "timeout must name exactly one result" rule would incorrectly
exclude legitimate multi-stage escalation. A total typed timeout transition graph is
the stronger and more useful contract.

**Amendments required:** Report §§5.2, 6.1, 6.4 and 14.4; ticket S1/S2/S3 gates.

### 3. Outcome conditions are evaluated atomically at local terminal acceptance

**Current coverage:** Partial. Both artifacts require outcome-condition declaration,
evaluation, evidence, and fail-closed behavior, but do not fix the evaluation site,
failure product, or replay semantics.

**Normative rule:**

1. A business-outcome proposal has a stable proposal identity and pinned canonical
   payload, condition version, evidence references, policy/component versions, and
   executable envelope.
2. Its condition is evaluated at the emitting component's local terminal-acceptance
   boundary, before the business terminal is accepted. The evaluation result and
   accepted local terminal are committed through the same idempotent/CAS protocol.
3. There is at most one accepted condition evaluation for a proposal identity;
   crash/retry consumes the recorded evaluation rather than recomputing against
   changed evidence.
4. A true condition permits acceptance of the proposed business outcome. A
   determinately false condition forbids that business outcome and accepts the
   reserved lifecycle/control terminal
   `contract_violation(reason=outcome_condition_failed, attempted_outcome=...)`.
   It may not substitute a different business outcome.
5. Missing, stale, ambiguous, or unavailable required evidence is not the same as a
   false predicate. It quarantines/reconciles the proposal until a deterministic
   evaluation can be recorded or the declared infrastructure/deadline policy yields
   a lifecycle terminal.
6. Parents and root hosts consume the accepted local terminal and its provenance;
   they do not re-evaluate product predicates. They still perform their own current
   admission and terminal-arbitration checks.

This adds one universal contract-violation lifecycle terminal/reason class to the
two-layer result algebra. It is preferable to treating a component bug as a domain
`blocked` result or leaving a terminal-less child indefinitely.

**Amendments required:** Report §§6.1, 6.4, 10, 14.3; ticket S1/S2 and acceptance
suite item 21.

### 4. `JoinPolicy` is a total classifier over the child result algebra

**Current coverage:** Partial. `JoinPolicy` already names all/any/quorum,
arbitration, loser cancellation, late results, and resource races, but
"qualifying", "success", and the unsatisfiable product are undefined.

**Normative rule:**

1. `JoinPolicy` is typed against the exact closed union of the child component's
   business outcomes and applicable lifecycle/control terminals.
2. It classifies every child result as qualifying, tolerated non-qualifying, fatal,
   or another explicitly named closed category. No result is handled by a default.
3. For `any`, `quorum`, and reducer thresholds, the qualifying predicate is a
   versioned declaration over outcome identities and, where necessary, a canonical
   payload predicate. Lifecycle/control terminals never count as success merely
   because they are accepted terminals; any exceptional qualification must be
   explicit and statically type-valid.
4. The policy declares the exact parent result when the target is satisfied and the
   exact parent result when satisfaction becomes impossible. Either may be a
   declared parent business outcome or applicable lifecycle/control terminal, but
   the result class and its conditions remain distinct.
5. The policy also exhaustively declares tolerated/fatal failure, partial-result,
   loser cancellation, late-result, and simultaneous-event arbitration behavior.
6. Omitted result classifications, omitted unsatisfiable results, or noncanonical
   payload predicates fail composition validation.

**Amendments required:** Report §6.5 join table and §14.4; ticket S1/S2 and S3/S4
proofs.

### 5. Budget/resource release is settlement-based, not dispatch- or lease-based

**Current coverage:** Partial. Both artifacts require reservations, charges,
release/refund, and reconciliation, but do not define the moment at which capacity
returns to the parent.

**Normative rule:**

1. Every resource class declares a durable ledger and settlement semantics:
   reservation, committed charge, unresolved liability, released/refunded amount,
   and the proof that no further charge can accrue.
2. At every observable event:

   ```text
   committed charges + unresolved liabilities + live worst-case reservations
   <= admitted parent budget
   ```

3. Sending cancellation is never sufficient to release a reservation. Release is
   allowed only after durable, resource-specific settlement proves that future
   charge is impossible—for example an accepted settled child terminal, a
   provider-confirmed cancellation/fence, or a reconciled final usage record.
4. Custody lease expiry alone does not settle token, money, tool, or external-effect
   liability. On expiry, unsettled exposure remains reserved or moves to an
   unresolved-liability entry until reconciliation. A concurrency/worker slot may
   use different settlement proof if its provider contract makes expiry sufficient.
5. Refunds are explicit ledger events; they cannot be inferred from cancellation or
   absence of an outcome.

Thus the Oracle correctly found a gap but its uniform "terminal or lease expiry"
rule is over-specified and, for external costs, unsafe.

**Amendments required:** Report §6.5; ticket S1 resource algebra, S2 enforcement,
S3 fault corpus, S4 alternate consumer, and S5 certification profile.

### 6. Expiry-based parent completion retains a typed unresolved-child fact

**Current coverage:** Partial. The existing contract allows parent completion after
declared child Custody expiry and correctly says a parent may not fictionalize a
release, but does not require a durable unresolved-child disposition.

**Normative rule:**

1. If a parent policy permits acceptance without an accepted child terminal because
   exact-target Custody expired, it records exactly one typed
   `unresolved_child` disposition containing child identity, target, last epoch,
   last known attempt/effect state, expiry evidence, and reconciliation obligation.
2. Expiry is not represented as release, child success, cancellation completion, or
   effect settlement.
3. The parent terminal, WBC explanation, projections, and conformance trace retain
   the unresolved disposition. It cannot be normalized away.
4. Late child actions remain rejected by current epoch/fence validation. Later
   reconciliation appends linked facts but does not silently reopen or rewrite the
   accepted parent terminal.
5. Whether expiry may permit parent acceptance at all is a declared parent
   cancellation/join policy. Policies requiring clean child settlement continue to
   block or escalate.

**Amendments required:** Report §§5.2, 6.5 and 14.3/14.4; ticket S1/S2 and acceptance
suite item 26.

### 7. Trace field classification is versioned contract data

**Current coverage:** Partial. The artifacts forbid multiplicity/causality erasure
and mention an allowlist of volatile fields, but do not identify its owner or define
unknown-field behavior.

**Normative rule:**

1. Every portable event/trace schema version classifies each observable field as:
   exact, canonically transformed, relationally compared, or ignorable volatile.
2. This field-classification table is a versioned, content-addressed part of the
   golden/conformance trace contract and is bound into the conformance receipt.
   It is not caller- or comparator-local configuration.
3. Unknown or unclassified fields fail comparison; they are never silently dropped.
4. Relational facts such as custody-owner consistency may pseudonymize host/process
   values while preserving equality/change relations. They may not be erased merely
   because literal host IDs differ.
5. Raw event identity and multiplicity are checked before normalization.
   Normalization cannot deduplicate events, collapse retries, or launder an
   arbitration race.

**Amendments required:** Report §§6.6, 14.3 and 14.5; ticket S1/S2, S3/S4 trace gates,
and S5 conformance-manifest rules.

### 8. Consequences of the two-layer result model

**Current coverage:** The conceptual distinction is already strong, but the Oracle
exposed consequences that must become normative:

- Business outcomes are authored semantic results with payload/condition/evidence
  contracts. Lifecycle/control terminals are runtime disposition facts. They occupy
  separate tagged unions even if a root host maps both to the same product terminal.
- Outcome conditions apply only to business outcomes. Lifecycle/control terminals
  have lifecycle acceptance preconditions, not invented domain predicates.
- Parent composition must exhaustively handle or explicitly propagate both unions.
  A catch-all exception route is not exhaustive handling.
- Human suspension is neither union's terminal result. Timeout/escalation may later
  yield a declared member of either union through its typed state machine.
- A join must classify the entire child result union. "Accepted terminal" is not
  synonymous with "successful child".
- Root hosting may translate either result class into a proposed root product
  terminal, but the accepted record retains source class and provenance.
- Cancellation, deadline, budget, infrastructure, compensation, and contract
  violation cannot be smuggled into ordinary business payload flags.

These rules should be centralized in the report's Stage 2 section and the ticket's
S1 lifecycle standard. They sharpen the existing model rather than create another
workstream.

## Exact S1–S5 ownership and gates

| Platformization sprint | Required ownership | Blocking evidence |
| --- | --- | --- |
| **S1 — standard freeze** | Freeze the two-layer result algebra including `contract_violation`; total root-host maps; human timeout transition schema; atomic outcome-condition acceptance model; total JoinPolicy result classifier; resource-class settlement ledger; typed `unresolved_child`; versioned trace field-classification table. Extend the reference transition models and invalid corpora. | Reference/model tests reject missing root maps, default/catch-all mappings, unbounded/implicit human timeout routes, parent-side outcome re-evaluation, false-condition business substitution, incomplete join classifiers, missing unsatisfiable results, cancel-dispatch budget release, lease-expiry cost settlement, silent expired children, unclassified trace fields, and normalizers that erase relational facts or raw multiplicity. |
| **S2 — implementation** | Enforce all S1 contracts in `validate_component`, `validate_composition`, lowering, lifecycle terminal CAS, root hosting, human-gate runtime, JoinPolicy arbitration, resource ledger, cancellation/Custody integration, and partial-order comparator. | Exhaustive terminal-map corpus; crash injection around condition-evaluation/terminal atomicity; answer/timeout and join-race matrices; invariant checks after every resource-ledger event; expiry/reassignment/stale-child cases; raw-before-normalized multiplicity checks; checkout/wheel/cloud equality. |
| **S3 — first patterns** | Exercise the contracts through evaluator panel, human gate, effect-safe action, and bounded loop. Include one pattern hosted at root in tests even if published nested-only, or use a dedicated conformance fixture. | Human answer vs each timeout/escalation generation; all/any/quorum qualifying/nonqualifying/all-impossible cases; cancellation with settled and unresolved resources; expiry-based parent acceptance retaining `unresolved_child`; local/installed trace equality under the versioned field table. |
| **S4 — adversarial consumer** | Make the non-Megaplan consumer use a different total root map, timeout disposition, qualifying predicate/unsatisfiable join result, and resource policy. Substitution must preserve these declared observable contracts. | Independent implementation and upgrade receipts show identical result class/provenance, outcome-condition acceptance, timeout/join behavior, settlement invariant, expiry facts, and normalized partial order under the same trace-field contract. Resume compatibility remains separate. |
| **S5 — certification** | Publish root-hostable/nested-only, human-gate, join, resource-accounting, Custody-cancellation, outcome-condition, and trace-normalization conformance profiles. Bind field tables and applicable profiles into the content-addressed conformance manifest. | Stable registry status is blocked if any declared capability omits its profile, any map/policy is partial, any resource ledger violates the eventwise invariant, or any normalizer uses local/unversioned exclusions. Published docs must show both business and lifecycle/control paths without conflation. |

## Required document amendments

### Representation report

1. Correct the §6.3 root-host example by mapping `budget_exhausted` and
   `compensation_failed`, and state static totality plus provenance preservation.
2. Add the human-timeout transition state machine and answer/timeout arbitration to
   §§5.2/6.1/6.4.
3. Add the atomic outcome-condition terminal-acceptance protocol and
   `contract_violation(outcome_condition_failed)` to §§6.1/6.4.
4. Expand §6.5 with the total JoinPolicy classifier, exact unsatisfiable result,
   settlement-based resource ledger, and typed expiry disposition.
5. Make the volatile-field table contract-owned, versioned, fail-unknown, and
   raw-multiplicity-preserving in §§6.6/14.3/14.5.
6. Add timeout, outcome-condition, join, expiry, and budget races to §14.4's
   arbitration index.

### Platformization ticket

1. Extend S1's lifecycle/root-host/outcome-condition/JoinPolicy/resource/trace
   bullets with the exact rules above.
2. Extend the S1 invalid corpus and S2 gate with the corresponding negative and
   fault-injection cases.
3. Make S3's human-gate, evaluator, cancellation, resource, and trace fixtures
   exercise the new rules explicitly.
4. Require S4's adversarial consumer to vary these policies and preserve them under
   substitution.
5. Bind the resulting capability profiles and trace field table into S5's stable
   conformance manifest.

## Scope decision

- **No new Platformization sprint.** The work is definition/enforcement/proof of
  lifecycle and composition contracts already assigned to S1–S2.
- **Do not leave these as notes.** Totality, terminal acceptance, join
  qualification, resource settlement, unresolved expiry, and normalization ownership
  affect whether two implementations can disagree while both claim conformance.
- **Do not push generic Stage 2 semantics back into Native Parity.** Native Parity
  must preserve its product-specific human, timeout, outcome, cancellation, budget,
  and trace behavior and hand off evidence. Generic root hosting, reusable JoinPolicy,
  component outcome-condition protocol, and cross-consumer certification remain
  Platformization scope.

