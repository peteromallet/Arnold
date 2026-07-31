# S3B - Gate, Revise, and Complete Front-Half Cutover

## Objective

Move gate and the bounded critique/gate/revise planning cycle into canonical
source, remove the S3A seam and remaining front-half carriers, and close GO-1
with `NP-GT-001` and `NP-GT-002` from one raw composed history.

## Mandatory GO-1B stop/go

GO-1A must be green and every old-prefix fence/adoption action must consume the
exact accepted post-merge GO-1A receipt. Reconsume the exact C1/C2 manifests,
S2R kernel-enablement receipt, and current divergence-ledger hash with no stale
blocking entry. Land gate/revise and its typed outgoing tiebreaker/finalize
seam, then prove checkout and clean installed behavior, relocated WBC/action
producers, all-plane shared validation, one admitted writer and old-carrier
inertness before fencing the remaining legacy front half.

Failure blocks S4 and leaves only gate/revise old-authoritative,
validator-registered and not yet hard-fenced; it does not roll back the
accepted S3A prefix cut.

Gate/revise candidate code and the outgoing seam remain non-authoritative
through merge. Until the exact accepted post-merge GO-1B receipt is consumed,
the incoming S3A seam and legacy gate/revise producers remain usable and
authoritative. One atomic receipt-consuming switch relocates producer
authority, removes/fences the incoming seam and remaining carriers, and
activates the outgoing seam; no earlier source deletion or registry update may
make the legacy path unavailable.
The switch runs only as the chain's declared S3B transition. Its output receipt
and resulting producer/seam/fence state are consumed by a separate
post-transition GO-1B verifier before the milestone may complete.

## Product scope

- gate signal construction, worker/model call and normalization;
- flag validation, one reprompt and downgrade;
- preflight, high-complexity, cap/no-progress and severity backstops;
- debt effect and closed typed gate decision;
- revise and one bounded critique/gate/revise `planning_cycle`;
- declared planning-cycle outcomes and parent handling.

The gate's annotation, return type, lowerer and every parent share exactly this
closed vocabulary: `proceed`, `iterate`, `tiebreaker`, `escalate`, `abort`,
`blocked`, `blocked_preflight`, `force_proceed`. There is no default or
payload-carried route.

## Required work

- Add `workflows/plan_quality/gate.pype` and
  `workflows/plan_quality/cycle.pype`, each with exactly one canonical
  workflow. `cycle.pype` visibly owns the bounded critique/gate/revise topology;
  gate/revise reusable leaves remain in `steps.py` and supporting `.py` files.
  A temporary `front_half.pype` may exist only as a migration scaffold with an
  explicit identity record and must be deleted/tombstoned after GO-1B; it is
  never a durable public grouping module.
- Make canonical source own all scoped routes and call-site policies; retain
  only pure signal/model/serialization bodies.
- Freeze post-normalization/one-reprompt precedence as: agent-availability
  preflight; cap/no-progress exhaustion; severity/high-complexity backstop;
  declared model recommendation. Exhausted correctness/security blockers yield
  `blocked`; exhausted cosmetic-only debt yields `force_proceed`; before
  exhaustion high-complexity unverifiable checks may yield `iterate`.
  No-progress is no strict decrease in the canonical set of unresolved
  blocking flag identities between admitted generations; wording, order or
  aggregate count cannot reset progress. A schema migration must provide a
  total old→new flag-identity and streak mapping. Without one, emit the typed
  `progress_incomparable` fact, do not count the generation as progress or
  silently reset/carry the ordinary streak, increment a separate bounded
  incomparable counter, and take the declared human/escalate/abort cap
  disposition when that counter is exhausted.
- Establish the named ancestor `planning_cycle` with declared outcomes so
  S5B's
  delivery `review_blocked -> replan` exit has a real target.
- Prepare relocation of all remaining front-half WBC/action producers to
  lowered nodes and the deletion/hard-fence of component routes, handler
  strings, manifest defaults, `_core` transitions, CLI translation and auto
  derivation. Apply them only inside the receipt-consuming GO-1B switch.
- Remove/fence the S3A native-to-legacy-gate seam only inside that same switch;
  it remains usable until then.
- Generate the outgoing tiebreaker/finalize seam from a closed typed boundary.
  The accepted upstream decision names the downstream entry; the seam only
  serializes the payload/envelope, is registered when durable, fails route
  mutation tests and expires in S4.
- Make `NP-GT-001` and `NP-GT-002` green with raw event multiplicity,
  per-occurrence order, sibling partial order, exact decision consumption,
  four-domain joins and one aggregate child terminal.
- Mechanically derive every scoped CAS/arbitration site and participant family
  from lowered IR. Require equality with the arbitration-policy index and
  forced pre-CAS race fixtures for both release orders.
- Join each derived site to S2R's certified linearizable canonical
  store/service operation and record production adapter/store/schema
  provenance. Run the cutover receipt through two independent adapter clients;
  serialized read/check/write or an in-process mutex is a failing mutation.
- Test that the volatile-field allowlist cannot elide typed gate outcomes,
  arbitration participants, semantic keys, accepted/loser identity, CAS
  sequence, or precedence facts. Forged, missing, or reclassified fields fail.
- Put any front-half durable ledger/registry introduced by the cut in an
  admitted restore boundary or pass restore-then-replay before GO-1B.
- Bind the exact old/candidate writer cohort to the shared validator with one
  admitted decision consumer/history writer.
- Emit GO-1B and mark composite GO-1 complete only when GO-1A and GO-1B are
  both accepted. The remaining front-half authority switch and every
  fence/delete operation must consume the exact post-merge GO-1B receipt.
- Run partial-switch, wrong-tree, pre-merge, stale, red, cross-incarnation and
  replayed-receipt mutations. Each must leave the pre-switch legacy path usable
  and authoritative rather than deleting the only valid route.
- Bind every gate/revise/planning-loop durable subject to the enabled kernel,
  use S2R's concrete branch/loop/retry aggregation instances, and append every
  comparison difference to the one stable-occurrence divergence ledger. GO-1B
  binds its exact current hash and rejects a legacy completion writer.

## Semantic gate

- A reviewer can follow prep through revise without handlers, route maps,
  `_core`, CLI or auto-drive.
- Gate reprompt/downgrade, critical cap block, cosmetic force-proceed, debt,
  retry/fallback and loop generations execute from lowered source.
- Every one of the eight gate values is exhaustively compiled/handled, and
  precedence/no-progress mutations change or reject the trace as declared.
- Source mutations change raw/runtime traces; remaining old-carrier and seam
  mutations cannot change behavior.
- Lowered arbitration sites equal declared policies and forced-race coverage.

## Custody-adoption gate

- Every gate/revise action and effect uses current RA fence, exact Custody
  target/epoch, exact-version WBC and admitted executable bindings.
- Comparison history and unregistered old/candidate paths fail before action.
- GO-1B passes in checkout and clean installed execution with exactly one
  admitted writer before the remaining old front-half carriers are fenced.
- Whole-payload and open-string route discriminants reject. Every compiled
  route uses a source-mapped finite route key or statically named finite
  predicate set that is distinct from its data payload.

## Do not close if

- GO-1A is missing or the prefix is silently rolled back.
- Gate policy remains in a handler, metadata table, status or bridge.
- The outgoing seam can choose a target or has no S4 expiry.
- Raw duplicate/missing events are hidden by normalization.
- Any lowered arbitration site lacks an indexed policy and forced-race proof.
- CAS proof is not production-store linearizable, a volatile classification
  hides arbitration truth, or restore proof is deferred past GO-1B.
