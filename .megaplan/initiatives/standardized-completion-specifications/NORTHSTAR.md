# Standardized Completion Specifications — Superseded North Star

## Status

This directory is a non-launchable normative design and traceability source.
The former M1-M5 epic has been redistributed into Native Parity,
Platformization, and the bounded-projection Custody handoff. The exhaustive
mapping is `evidence/SUPERSESSION_CROSSWALK.yaml`.

## Accepted destination and sequence

Arnold has one neutral, content-addressed completion kernel:

```text
CompletionSpec -> CompletionBinding -> CompletionVerdict
                                      -> existing acceptance transaction
```

It is delivered only through this critical path:

```text
accepted/consolidated Custody M11 plus bounded-projection handoff
→ accepted milestone-gate bootstrap and downstream-spec readiness
→ Native S1
→ amended Native S2F
→ inserted Native C1
→ inserted Native C2 (shadow/non-authoritative)
→ Native S2R GO-0, the sole authoritative kernel enablement
→ Native S3A…S7
→ Platform S1 → S2A → S2B → S3 → S4 → S5 → S6
```

## Ownership invariants

- S2F owns authored workflow/component/graph identity and durable-boundary
  call-site identity templates. Admission and S2R instantiate runtime human,
  dynamic-child, and rework occurrences.
- C1 owns the experimental neutral package/import boundary, versioned schemas
  and serialization—including the internally versioned persisted binding wire
  schema from its first definition—stable obligation identity, durable/helper lint,
  candidate-outcome registry, named-exit supersession terminal, shadow
  generation, false-done/`REVIEW` fixture, and content-addressed divergence
  ledger.
- C2 owns immutable binding/evaluation schemas, exact evidence scope, proof
  modes, aggregation signatures, verifier independence, waiver taint,
  persisted compatibility, authoritative decoder behavior, shadow acceptance
  integration, restore proof, and projection deletion/forgery invariance. C2
  remains non-authoritative.
- S2R owns concrete child-set and aggregation instances for every durable
  primitive. Its accepted GO-0 receipt is the sole live kernel enablement.
- Every later Native cutover consumes the kernel receipts and exact current
  divergence-ledger hash.
- S5A/S5B own the full Megaplan execute/review/rework slice, including normal
  admission for reopen/new work, no executable `REVIEW`, and S5B's consumption
  gate for the 57k-scale bounded projection.
- Custody owns the bounded incident projection implementation and benchmark
  receipt; Native requires and consumes the exact handoff.
- Platformization consumes the exact Native implementation and owns neutral
  extraction, authoring/productization, DX, isolated recomposition, an
  independently originated unrelated consumer, and S6 certification.
- Completion candidate outcomes and Platform enforcement dispositions remain
  separate typed registries with a total generated boundary mapping. They are
  never collapsed into one enum.
- C1 assigns internal wire schema versions, C2 completes their reader/writer and
  decoder matrix, and the enforceable persisted-wire compatibility promise
  starts only at authoritative S2R GO-0. Stable public API publication remains
  Platform S6-only.

## Authority and evidence invariants

- The completion kernel extends the existing `CompletionVerdict`; it does not
  create another verdict, evidence registry, receipt store, scheduler, waiver
  system, lifecycle, or acceptance authority.
- Run Authority, Custody, WBC evidence, completion evaluation, and the existing
  acceptance transaction retain separate roles.
- Every admitted durable semantic subject has exactly one immutable binding.
  Pure helpers and disposable projections have none.
- Evidence is admissible only inside the binding's content-addressed scope.
  Absence and exact-set claims require complete capture.
- Review-created work returns through normal finalization/admission. `REVIEW`
  is never an executable task identity.
- Markdown, status, timelines, and other projections explain outcomes but never
  authorize them.
- Historical evidence and all manifest/gate-consumed artifacts remain
  preserved and content-addressably reachable.
- The accepted M11 completion manifest, its live authority/Custody/WBC evidence,
  the bounded-projection handoff, and every manifest-consumed predecessor proof
  are protected dependencies. Supersession cannot delete, replace by name, or
  orphan them; active gates consume exact content-addressed identities.

## Non-launch rule

Nothing in this directory is an executable chain or cloud session. The
historical briefs and decision snapshot remain byte-preserved sources whose
requirements are enforced by the active owners named in the crosswalk.
Any contradictory historical ownership statement is superseded by the
machine-resolvable owner and proof-rule records in that crosswalk.
