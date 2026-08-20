# Alternative Oracle Answer 2 — proof-system adjudication

## Verdict

Answer 2 contributes one important proof obligation that survived the prior
round of amendments:

> The plan now discovers every authoritative arbitration site and forces both
> release orders, but it does not yet say strongly enough that the winning CAS
> is a storage/service-enforced atomic conditional operation exercised through
> the admitted production adapter.

That is a genuine gap. The current plan can still be read as permitting an
application-level read/check/write protected by an in-process test lock. The
lowered-IR arbitration inventory, forced pre-CAS fixtures, raw independent
verifier, and Native-store restore matrix would all be valuable, but none alone
proves atomicity at the persistence enforcement point.

The answer's production story should not be adopted literally where it assumes
an old and a new Custody owner can both be current. M11's fencing contract is
supposed to make that impossible. The valid counterexample is simpler: two
legitimately admitted competing transition proposals (for example operator
cancel and automatic publication) reach the same terminal-arbitration key, or
two consumers contend for the same aggregate child terminal. If their CAS is
application read/check/write, both can win even though both callers are valid.

No new sprint is needed. This is a cross-cutting strengthening of S1, S2,
the owning cutover receipts, and S7, plus one Stage-2 capability-closure rule.

## Attack-by-attack disposition

| Attack | Current disposition | What remains |
| --- | --- | --- |
| **SWC: application-level CAS passes serialized race fixtures** | **Partly covered, with one material remainder.** Current report §14.4 and S3B/S6 derive arbitration sites from lowered IR, require exact policy/fixture equality, and force both release orders at a pre-CAS barrier. S1/S7 also inventory Native durable stores and forbid Native-local authority-consumption state. | Define “authoritative CAS” as a linearizable conditional write/unique constraint/transaction enforced by the canonical durable store or service, never application read/check/write. Exercise that primitive through the admitted production adapter with two independent clients contending on one key. Bind adapter/store provenance into the receipt. |
| **Comparison namespace by convention** | **Substantively covered.** S3A requires either storage-enforced `authority_class=comparison` or a separately credentialed immutable artifact namespace with no RA grant, Custody/effect client, admitted writer, resume, or promotion path. S7 proves exclusion/nonpromotion. | Optional cheap hardening: explicitly mutate forged, missing, and relabelled class tokens on both admitted-write and admitted-query paths. This does not warrant structural plan change. |
| **Volatile allowlist erases arbitration facts** | **Covered.** The report makes field classification contract-versioned, unknown fields fail, arbitration facts are load-bearing, and raw event identity/multiplicity is checked before normalization by a disjoint verifier. | Add one explicit negative mutation that reclassifies an arbitration/provenance field as volatile and must fail. Useful but not a new design requirement. |
| **Capability-profile under-declaration** | **A real Stage-2 clarification.** The ticket says a component declaring an LLM/effect boundary cannot omit its profile, but “applicable” can still be interpreted as whatever the descriptor self-declares. A bound policy/effect implementation could introduce an LLM/effect class without widening the declared profile. | Compute the effective capability-profile closure from the descriptor, lowered topology, transitive component graph, resolved policy/effect/model/tool bindings, and implementation metadata. The stable manifest's declared profiles must equal (or conservatively cover) that computed closure. Recompute at admission/rebind; under-declaration fails before authority. |
| **Proof-map store rollback hides a red receipt** | **Largely covered by the post-round-3 restore/ownership matrix.** S1 and S7 explicitly include proof registries and require the M11 rollback-resistant boundary or a restore-then-replay proof; the report already names a fail-closed control-plane incarnation. | Make the final proof-map receipt bind the proof-registry store incarnation and append-only cursor/high-water mark read at validation. This is a small explicit receipt field, not another sprint. Note that an ordinary failed run need not remain permanently fatal after a real fix; the invariant is that rollback cannot erase history or impersonate a newer incarnation. |
| **S2 harness/installed duality** | **Same material remainder as SWC.** The local harness is explicitly non-release proof, and S7 runs installed/cloud scenarios, but the plan does not require a route-relevant Native persistence protocol to identify and exercise its production store adapter. | Add an adapter-provenance field and a production-store conformance family for every route-relevant durable atomic protocol. Contract fakes remain appropriate for author UX, but cannot satisfy GO-0/cutover/GO-4 atomicity receipts. |

## Why the existing post-round-3 improvements still matter

The alternative Oracle is not invalidating the previous amendments. It is
operating one layer below them:

1. **Lowered-IR arbitration equality** prevents an unindexed runtime race site
   from escaping the proof corpus.
2. **Forced race fixtures** prevent the corpus from testing only the named
   cancel/publish/deliver trio.
3. **Raw independent verification** prevents normalization from laundering
   duplicate terminals or effects.
4. **The durable-store ownership/restore matrix** prevents a Native side
   decision-consumption store from silently becoming a second authority plane.
5. **Comparison isolation** prevents shadow history from entering admitted
   resume/query paths.

The missing link is enforcement provenance: once a site is discovered and a
race is generated, the receipt must prove that the contested state transition
was decided atomically by the actual durable system of record.

## Minimal normative rule

Add one rule to the representation report and reuse it from both plans:

> Every authority-increasing arbitration or single-consumption point is accepted
> by one linearizable conditional operation in its canonical durable system of
> record, or by a canonical service whose contract proves the same property.
> Application-level read/check/write is not CAS. Each competing proposal is
> durably identifiable; exactly one acceptance and every non-winning
> disposition remain reconstructible after crash and restore. A conformance
> receipt identifies the store/service implementation, adapter, schema/key,
> atomic primitive, control-plane incarnation, and raw accepted/rejected facts.

For state such as a parent loop ledger that is route-relevant but not itself a
new RA authority store, its terminal-consumption mutation must be atomic with,
or conditionally bound to, the corresponding accepted M11 decision. “Eventually
joined” is not enough.

## Minimal plan updates

### Native Parity S1

- Extend the executable M11 capability probes from “restore-durable decision-
  consumption CAS” to **store/service-enforced atomic competing-transition and
  single-consumption CAS**.
- Probe with two independent client/session identities against the exact
  admitted production adapter and store class. A controlled barrier should
  make both proposals contend on the same empty/versioned key; exactly one may
  accept.
- Record enforcement provenance: canonical owner, store/service implementation
  digest/version, adapter digest, schema and key/version, atomic primitive,
  restore incarnation, and durable winner/loser facts.
- If M11 does not expose the required primitive, emit
  `blocked_on_m11_point_release`; do not implement a Native application lock or
  side authority record.

### Native Parity S2 / GO-0

- Add a generic production-store conformance fixture for every Native route-
  relevant atomic protocol introduced at GO-0 (at minimum parent aggregate-
  terminal consumption and any generic terminal-arbitration join).
- Run two independent admitted workers/clients with no application mutex. Test
  actual contention as well as both deterministic release orders. In-memory
  adapters may test semantics but cannot satisfy this receipt.
- Crash after proposal, after CAS result, and before loser-disposition
  journaling; prove the accepted winner remains unique and every proposal has a
  durable accepted/rejected/reconciliation disposition.

### Owning cutovers (S3B and S6)

- Keep the existing lowered-IR site inventory and pairwise forced-race matrix.
- Add a receipt join from every live arbitration site to an S1/S2-certified
  atomic primitive and production adapter. New store/protocol classes require
  their own production-store contention proof before that cutover.
- Do not multiply sprint scope by stress-testing every semantic fixture against
  physical infrastructure. Prove the store primitive once per implementation/
  schema class, then prove every lowered site binds to that certified class.

### Native Parity S7 / GO-4

- Require exact equality among lowered arbitration sites, policy/forced-race
  receipts, and certified atomic-enforcement bindings.
- Repeat at least one installed/cloud contention fixture per distinct
  production store/protocol implementation, not through recorded-boundary or
  in-memory adapters.
- Bind the proof-registry control-plane incarnation and append-only cursor into
  `final-proof-map.json`.
- Add the cheap comparison-class and volatile-arbitration-field mutations.

### Platformization ticket

- In S1, freeze the atomic-enforcement and adapter-provenance contract inherited
  from Native Parity; generic component lifecycle/loop/join/root-host CAS points
  cannot weaken it.
- In S2, implement conformance adapters for the real supported durable store
  classes, separate from the in-process authoring fakes.
- In S5, derive the component's **effective capability-profile closure** from
  resolved transitive bindings and require the published conformance manifest
  to cover it exactly/conservatively. Rebinding re-runs the check.
- Add two suite items: production-store atomic contention for every supported
  CAS protocol, and profile-under-declaration mutations where a supposedly pure
  slot is rebound to an LLM/effectful implementation.

## Relative value of this Oracle answer

For proof-system hardening, this answer is stronger than the previous Oracle's
false-green analysis in one precise way: the previous analysis led us to cover
**which races exist** and **whether raw evidence preserves them**; this answer
asks **where atomicity is actually enforced** and **which adapter/store the test
really exercised**. That is a distinct and worthwhile improvement.

Its runner-ups are mixed: comparison isolation, normalizer independence, and
restore ownership are mostly confirmations of changes already made; capability-
profile closure is a small but genuine Stage-2 addition. The answer should
therefore sharpen the current assets, not cause another redesign or sprint.
