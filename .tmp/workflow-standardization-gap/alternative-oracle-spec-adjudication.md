# Alternative Oracle — Answer 1 adjudication

Scope: `04_ORACLE_ANSWERS.md` A1–A19 against the current representation
report, eight-milestone Native Parity assets, and Platformization ticket.

## Bottom line

This Oracle is a valuable **spec-consistency critic**, not the better overall
architectural Oracle. It found three live contradictions in the report's
illustrative Python and four worthwhile semantic/race clarifications. It also
repeated several issues already fixed after the earlier Oracle, and it
systematically overreaches when it treats declared, digest-bound consumer
policy as something that must be globally identical across products.

The best incremental updates from Answer 1 are:

1. repair the illustrative Python's gate vocabulary, review retry, and
   review-blocked replan path;
2. freeze the real gate precedence and canonical no-progress predicate in the
   S3B semantic contract;
3. explicitly classify product loop-cap outcomes versus platform resource
   exhaustion;
4. define answer-vs-answer and accepted-input-vs-accepted-cancel arbitration;
5. clarify that an agentic phase may influence outer topology only through a
   declared closed result consumed by authored topology;
6. define the cancellation-required child disposition set precisely.

These fit the current report/briefs/golden contract and Stage-2 S1 contract
freeze. They do **not** justify another sprint.

## Finding-by-finding classification

Legend:

- **Covered** — current authoritative assets already close the issue.
- **Novel gap** — worth a narrow update.
- **Illustrative drift** — current plans are sound, but the report's example is
  inconsistent or misleading and should be repaired.
- **Over-prescriptive** — the observation may be useful, but the proposed
  universal rule is not.

| Finding | Classification | Adjudication against current assets |
| --- | --- | --- |
| **A1 gate vocabulary** | **Illustrative drift; valid catch, faulty count** | The current example is inconsistent: `GateDecision` omits `blocked`; the decorator omits `blocked_preflight` and `force_proceed`; the parent handles all three (`report:533-541`, `:662-670`, `:868-911`). The Oracle says the pipeline handles seven values, but it actually handles **eight**: `proceed`, `force_proceed`, `iterate`, `tiebreaker`, `escalate`, `blocked_preflight`, `blocked`, `abort`. S1/S3B already require closed/exhaustive vocabularies, so this is a report-example repair, not new plan scope. |
| **A2 gate precedence/no progress** | **Novel gap; proposed ordering questionable** | S3B names preflight, high-complexity, cap/no-progress and severity behavior but does not freeze their total order or the canonical progress measure (`s3b...md:20-26`, `:53-61`). The semantic matrix is future work. This should be explicit. However, the Oracle's proposed `preflight -> exhaustion -> severity` can force-proceed at the cap before honoring high-complexity unverifiability; the safer product rule must be derived from current Megaplan behavior and make correctness/security/high-severity blockers dominate cosmetic force-proceed. “Strict decrease in unresolved blocking-flag IDs” is a good candidate but needs product validation. |
| **A3 review-blocked replan** | **Covered + illustrative drift** | Current S5 and NP-GT-005 already require a typed exit to the named `planning_cycle`, close intervening scopes, and create a fresh planning-cycle instance (`s5...md:68-74`; `GOLDEN_TRACE_CONTRACT.md:454-461`). The report example still revises/finalizes locally and skips critique/gate (`report:951-959`), so update the example only. |
| **A4 root status** | **Covered** | Current report explicitly says only a root-host adapter may propose root truth and outermost/nested hosting never invokes it implicitly; maps are statically total (`report:1437-1452`, `:1558-1584`). The ticket says the same (`ticket:163-172`). This finding is stale relative to current assets or overlooked their strongest rule. |
| **A5 `retry_review`** | **Covered normatively + illustrative drift** | Current Stage-1 rules distinguish immutable retryable attempt terminals, accepted retry generations, and the aggregate child terminal; unexpected infrastructure failure uses the fixed infrastructure channel (`report:1028-1064`, `:1265-1269`; `GOLDEN...:240-243`). S5 calls review failure an infrastructure retry (`s5...md:38-40`, `:96-101`). The illustrative `ReviewDecision` and pipeline still route `retry_review` as a product decision while also using call-site retry (`report:543-549`, `:802-841`, `:943-944`). Remove it from the illustrative product vocabulary and express exhausted infrastructure policy as its declared lifecycle result. |
| **A6 loop-cap classification** | **Novel clarity gap** | The current product plan clearly expects blocking/advisory review-cap outcomes (`s5...md:38-40`, `:96-101`), while Stage 2 separates business and lifecycle terminals (`ticket:151-162`). But no single normative sentence says product semantic caps are business outcomes while platform deadline/token/cost exhaustion uses lifecycle terminals. Add that assignment rule to the report/ticket; no sprint change. |
| **A7 outcome conditions** | **Covered completely** | Current report fixes evaluation at the emitting component's local terminal-acceptance boundary, records it atomically, reuses it on replay, emits `contract_violation` on deterministic false, and quarantines indeterminate evidence (`report:1424-1435`). Ticket S1 mirrors it (`ticket:173-186`). |
| **A8 scoped rework generation** | **Covered** | The parent-loop/new-generation semantics are explicit (`report:1051-1064`). NP-GT-005 uses `delivery-cycle/0` then `/1`, preserves T1 without repeating its effect, and requires a fresh planning instance on replan (`GOLDEN...:433-471`). S5 derives namespaces from delivery generation and logical action occurrence. |
| **A9 release vs park on suspension** | **Over-prescriptive** | The report deliberately says release or park **according to the admitted policy** (`report:1622-1634`), and conformance explicitly separates fixed protocol invariants from consumer-owned policy values (`report:2296-2301`; `ticket:273-274`). Different declared policies are different admitted programs, not two implementations of the same program. A useful clarification would require the policy's release/park semantics and resulting transfer/reclaim epoch to be digest-bound and conformance-tested. A universal “always release” rule is not justified. |
| **A10 two valid human answers** | **Partly covered; narrow novel race** | Current report says one distinct submission wins CAS and later distinct answers are `rejected_late` (`report:1082-1097`); Golden invariant 32 says the same (`GOLDEN...:251-258`). Stage 2 explicitly tests “answer races” (`ticket:423-425`). Still worth making the race family unambiguous: answer-vs-answer, not just answer-vs-timeout, must be in the total arbitration policy and forced-race corpus. First accepted CAS is a sensible default, but globally forbidding a declared responder-priority policy is unnecessary if policy identity and tie-break are admitted. |
| **A11 route hint boundary** | **Novel wording gap** | The current phrase “cannot emit a hint that chooses the next outer product route” is too broad (`report:1271-1275`) because normal closed outputs and the critique selection payload legitimately influence authored fanout (`report:586-621`). Clarify: undeclared side channels, mutable state, metadata, exceptions, or opaque helper routing are forbidden; a schema-qualified closed result consumed by an explicit authored decision/fanout is the only legal influence. This sharpens report/NORTHSTAR/S2 language, not scope. |
| **A12 inner tool custody** | **Mostly covered; useful explicit hardening** | Generic invariants already require every authority-increasing child action to validate its own grant and every action/effect/repair target to have exact Custody (`report:1036-1042`); inner effectful tools must use effect intent/outcome (`report:1199-1205`), and Golden events bind effect target/attempt lineage. Make explicit that each effectful inner tool call is a distinct effect occurrence with exact target/current epoch, while pure/model calls remain ordered attempts in the outer agentic WBC ledger. The Oracle's “every inner call gets its own lease” is too broad for pure calls. |
| **A13 global arbitration order** | **Over-prescriptive; protocol already covered** | Current Stage 2 requires a total `JoinPolicy`, typed participants, tie precedence, exact success/impossibility results, one declared CAS/arbitration order, and no defaults (`report:1708-1730`; `ticket:214-222`). Native Parity now derives arbitration sites/participants from lowered IR and requires forced races. A policy is consumer-owned and digest-bound; two different policies may legitimately give different outcomes. The platform must standardize the arbitration protocol and demand a total policy, not impose one global cancel/deadline/success precedence on every product. |
| **A14 “required child” on cancel** | **Novel precision gap; proposed fix over-tight** | Current text still says “each required child” without defining the set (`ticket:223-231`), although `JoinPolicy`, exact Custody dispositions, and `unresolved_child` substantially constrain it. Define it as a closed per-admitted-child **disposition obligation** computed by the join/cancellation policy: terminal consumed, epoch-checked release/transfer, or declared expiry with `unresolved_child` and reconciliation. Requiring every loser to emit a normal child aggregate terminal, or mandatory immediate reclaim, is too strict and conflicts with the already-designed unresolved-child path. |
| **A15 accepted input vs cancel** | **Genuine novel race; proposed precedence too absolute** | Current assets cover answer-vs-timeout and cancel/publish/deliver, but do not explicitly state how an accepted-yet-unconsumed human/repair input competes with an accepted cancellation. Add this participant pair to the lowered arbitration-site index and golden race corpus. The rule should say **accepted cancellation authority**, not mere cancel intent/request, competes through the declared CAS and action validator; the losing accepted input remains non-authoritative evidence. A universal retroactive “cancel always fences any earlier accepted input” is a product-policy choice, not automatically a protocol invariant. |
| **A16 budget/cache economics** | **Covered better; Oracle over-prescribes** | Current resource model is stronger and appropriately resource-specific: durable reservation, charge, unresolved liability, settlement, release/refund; no release at cancel dispatch or Custody expiry; invariant checked at every observable event (`report:1732-1753`; `ticket:194-204`, `:346-355`). “Cache hits always cost zero” and “charge only at outcome recording” are not universal truths. Provider/cache infrastructure may have declared cost; protocol invariants should constrain accounting, not set product economics. |
| **A17 normalizer** | **Covered; proposed shared normalizer is risky** | Current report has a versioned content-addressed field table, unknown-field failure, raw identity/multiplicity before normalization, and conservation rules (`report:1835-1862`). Native Parity requires an independently implemented audit normalizer/verifier and lowered-site race completeness. The right invariant is one shared **trace contract/schema**, not one shared code implementation; shared code would recreate the common-mode proof seam the earlier Oracle exposed. |
| **A18 pinned artifact/migrations** | **Covered** | Golden invariant 15 requires every pinned executable/lock/prompt/tool/schema for a nonterminal run to remain resolvable until terminal or admitted migration/quarantine (`GOLDEN...:201-204`). The report requires per-run accepted migration decisions (`report:1124-1143`), and Platformization S4 exercises the full ordinary evolution matrix plus retained locked artifacts (`ticket:469-484`). |
| **A19 repair acceptance** | **Covered better; Oracle over-prescribes** | Current Native assets intentionally distinguish actor-local stale worker/lease/epoch failure—which may redispatch the same still-valid unconsumed immutable M11 decision—from semantic/precondition/executable invalidation, which voids it and requires a new decision (`GOLDEN...:491-496`; `NORTHSTAR.md:167-171`). The Oracle's blanket “any epoch change expires it” would discard valid authority and conflate placement failure with semantic invalidity. Rejections remain typed facts; acceptance may not silently normalize the requested action. |

## What should actually change

### Representation report

- Fix the illustrative Python at A1, A3, and A5. These are embarrassing because
  the surrounding report argues that source is the sole authority.
- Add the product-cap/lifecycle-resource classification rule (A6).
- Tighten “outer route hint” to permit only declared closed-result influence
  (A11).
- Add one paragraph for human answer-answer and accepted-input/cancel
  arbitration (A10/A15), and define cancellation disposition obligations (A14).
- Clarify inner effectful agentic calls as exact-target effect occurrences
  (A12).

### Native Parity epic

- In S3B, freeze gate precedence and canonical no-progress semantics; make a
  conflicting-signal fixture load-bearing (A2).
- In S2/S7 golden proof, include answer-answer and accepted-unconsumed-input vs
  accepted-cancel participant pairs in derived arbitration-site completeness
  (A10/A15).
- In S5, make product cap classification and required child-disposition set
  explicit (A6/A14).

No new sprint is warranted; these attach to existing semantic/proof owners.

### Platformization ticket

- Add A10/A15 to human-gate/terminal arbitration corpora and A14 to the total
  composition algebra.
- Add A6's cap classification to the business/lifecycle split.
- Do **not** adopt A9/A13/A16's universal policy values; preserve the existing
  protocol-invariant versus consumer-policy separation.

## Relative quality versus the prior Oracle

The earlier Oracle remains better overall. It exposed deeper composed-system
failure modes—M11 capability prerequisites, restore ownership, shared-normalizer
laundering, arbitration-site completeness, execution-plane convergence,
resume-selector ordering, and sprint feasibility—and its recommendations mostly
fit the authority/custody/WBC architecture. Those findings materially improved
the epic sequence and proof gates.

This alternative Oracle is better at **line-level semantic linting**. A1, A3,
A5, A11, and A15 are exactly the sort of contradictions/race windows a broad
architecture review can miss. But its quality drops when it infers that any
declared variability is non-conformance. A9, A13, A16, and A19 confuse “same
protocol under the same admitted policy must be invariant” with “every consumer
must use the same policy.” It also makes a concrete counting error in A1 and
occasionally chooses unsafe/overly absolute remedies.

Best synthesis: keep the prior Oracle as the architectural/plan authority; use
this one as a high-value adversarial spec linter, adopting the six narrow
updates above after technical adjudication rather than wholesale.
