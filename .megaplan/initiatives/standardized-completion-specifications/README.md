# Standardized Completion Specifications — Retired Launch Target

This prepared five-milestone initiative is retired as an independent epic. It
must not be launched, initialized, resumed, or deployed.

The useful material remains normative design and traceability input:

- `decisions/standardized-completion-spec-proposal.md` is the preserved design
  snapshot;
- `briefs/m1.md` through `briefs/m5.md` are preserved historical requirement
  sources; and
- `SUPERSESSION_CROSSWALK.yaml` exhaustively assigns every former requirement
  to its accepted owner and proof destination.

`chain.yaml` and `cloud.yaml` are archival source indexes. They are valid YAML
but intentionally invalid active Megaplan chain/cloud specifications. The
`.retired` marker is an additional operator-visible guard.

## Accepted critical path

```text
accepted/consolidated Custody M11 plus bounded-projection handoff
→ Native S1
→ amended Native S2F
→ inserted Native C1
→ inserted Native C2 (shadow/non-authoritative)
→ Native S2R GO-0, the sole authoritative kernel enablement
→ Native S3A…S7
→ Platform S1 → S2A → S2B → S3 → S4 → S5 → S6
```

The active chain owner is
`../megaplan-native-parity-corrective/chain.yaml`. The downstream extraction
and public-certification owner is
`../native-workflow-platformization/chain.yaml`.

Custody owns the incremental/bounded incident projection implementation,
full-rebuild parity, invalidation behavior, and 57k-scale benchmark receipt.
Native consumes that exact handoff and does not recreate it.

Internal persisted-wire compatibility begins when Native S2R accepts GO-0.
Stable public API publication remains Platform S6-only after the independently
originated unrelated-consumer proof.

Historical evidence and any artifact consumed by an existing manifest or gate
must remain content-addressably reachable. Supersession never means deletion
of proof.
