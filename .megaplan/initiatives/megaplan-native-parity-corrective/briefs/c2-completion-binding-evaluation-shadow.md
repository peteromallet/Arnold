# C2 — Completion Binding, Evaluation, and Shadow Acceptance Integration

## Objective

Complete the experimental kernel between C1 and S2R. Define immutable
occurrence binding, exact evidence evaluation, compatibility and decoder
behavior, and atomic integration with the existing M11 acceptance transaction
in shadow. C2 defines generic aggregation signatures only; S2R supplies every
concrete durable-primitive child-set and aggregation instance.

C2 remains non-authoritative. No flag, migration, decoder, shadow verdict, or
acceptance hook may enable live completion. The chain's S2R GO-0
receipt-consuming transition is the sole enablement boundary.

Normative retained design and exhaustive redistribution map:

- `../../standardized-completion-specifications/decisions/standardized-completion-spec-proposal.md`
- `../../standardized-completion-specifications/SUPERSESSION_CROSSWALK.yaml`
- `../../standardized-completion-specifications/briefs/m2.md`

## Required work

1. Freeze one immutable `CompletionBinding` at admission. Re-admission is
   idempotent only for identical content; conflicting content rejects. Resume
   consumes the pinned binding unchanged.
2. Bind exact evidence scope: semantic subject and path, occurrence, attempt,
   generation, dependencies and child set, source/tree/runtime and installed
   artifact digests, component and graph locks, prompt/tool/policy assets,
   store incarnation and restore generation, per-store cursor range/vector,
   Run Authority fence, Custody target/epoch, exact WBC version, admission
   receipt, and applicable product-contract digest.
3. Reject cross-subject, cross-attempt, cross-generation, cross-restore,
   cross-store, stale-fence, stale-epoch, changed-runtime, changed-binding, or
   cursor-out-of-scope evidence even when display IDs match.
4. Implement the initial proof modes: `presence`,
   `complete_capture_absence`, `set_equality`, and `aggregate`. Absence and
   exact-set success require named complete-capture evidence; incomplete
   capture yields `unknown`. One evidence item may support explicitly linked
   obligations but cannot prove multiplicity twice.
5. Evaluate exactly one proposed completion candidate outcome at a time.
   Require nontrivial obligations and transition semantics for every declared
   non-accepted candidate. Quarantine and suspension remain nonterminal unless
   a separately admitted terminal policy says otherwise.
6. Define generic aggregation signatures: total child-disposition mapping
   shape, admitted-child-set input, multiplicity/double-counting constraints,
   selected/unselected path proof, and transitive waiver-taint laws. Do not
   instantiate map/reducer, retry, loop, human, checkpoint, effect, or rework
   primitive instances here; S2R owns those exact instances and child-set
   freezing.
7. Enforce verifier independence through implementation/code provenance,
   producer identity, trust/authority domain, and direct primary-evidence
   access. Labels, process separation, or wrappers around one implementation
   do not prove independence.
8. Bind waiver authority, scope, reason, evidence, expiry, and immutable
   transitive taint. A waived child can never become clean root acceptance.
   Reuse the existing authority provenance; do not create a waiver subsystem.
9. Complete the versioned internal persisted-wire contract for spec, binding,
   verdict, and acceptance-reference records, including explicit old/new
   reader-writer compatibility. This compatibility promise begins only when
   S2R authoritatively enables persisted bindings; public authoring/API
   stability remains Platform S6-only.
10. Implement authoritative decoder behavior now: map legacy ambiguity to
    `legacy/unknown`; reject or quarantine unknown-future schema versions
    before body/effect intent; never reinterpret old coordinates under a new
    meaning. Resume with changed bindings requires explicit migration,
    new-attempt, or quarantine.
11. Integrate shadow verdict consumption with the existing M11 acceptance
    transaction atomically. Exercise concurrent contenders and every
    pre/post-write crash edge, while leaving the live acceptance decision
    unchanged until S2R GO-0.
12. Run an introduction-time restore/replay drill for every new durable kernel
    record. Bind receipts to canonical store/adapter provenance, store
    incarnation/restore generation, and raw-history high-water cursor.
13. Prove projection deletion/rebuild and forgery invariance: accept through
    the canonical pre-kernel path while evaluating in shadow, delete all
    completion/status/Markdown projections, restart, rebuild, and obtain the
    identical canonical decision/verdict/effect identity with no new action.
    Forged, corrupt, stale, or cursor-divergent projections remain inert.
14. Exercise duplicate, missing, reordered, wrong-target, and ambient-
    exception mutations for `superseded_by_named_exit`, retaining every
    intervening binding and exact unwind order.
15. Consume C1's exact manifest and current divergence-ledger hash. Append C2
    divergences to the same ledger and emit `completion-kernel-c2-manifest.json`
    plus the C2 proof map. Do not fork a second ledger or mark unresolved
    blocking entries complete.

## C2 gate

- exactly one immutable binding exists for each admitted shadow occurrence;
- all evidence-scope coordinates and invalidation mutations fail closed;
- proof modes have positive, negative, and incomplete-capture fixtures;
- aggregation signatures are total while concrete primitive instances remain
  absent and assigned to S2R;
- verifier-independence and waiver-taint mutations pass;
- old/new persisted-wire behavior and authoritative decoder outcomes are
  explicit and executable;
- atomic shadow integration, restore/replay, projection deletion/rebuild, and
  projection forgery invariance pass; and
- no live behavior changes and no crash between C2 and S2R can partially
  enable the kernel.

## S2R handoff

Publish the exact C1/C2 manifests, current divergence-ledger path and hash,
schema/hash/reader-writer versions, decoder matrix, adapter map,
evidence-scope/proof-mode/candidate-outcome registries, total boundary mapping
to platform enforcement dispositions, aggregation signatures, restore and
projection-invariance receipts, shadow acceptance integration receipt, and
the complete list of concrete primitive instances S2R must supply.

## Do not close if

- C2 enables admission or acceptance, creates a second acceptance
  transaction/store/decoder authority, or claims GO-0;
- a primitive's concrete child-set/aggregation instance is hidden in C2;
- evidence scope is a wall-clock interval or stitches attempts/stores;
- absence succeeds without complete capture, verifier independence is nominal,
  or waiver taint disappears at a parent;
- a legacy/unknown or unknown-future record can be treated as accepted;
- deletion or forgery of a projection changes canonical truth; or
- persisted-wire compatibility is described as stable public API.
