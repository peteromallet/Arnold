---
type: research
date: 2026-07-11
---

# Authority lineage and migration gap

## Verdict

Arnold/Megaplan has built the correct foundation, but has not completed the
migration. The incident class remained possible because several authoritative
ideas coexist with legacy writers/readers, independently refreshed snapshots,
process-based liveness, repair sidecars and delivery outboxes that are not one
causal history.

## 2026-07-13 ownership reconciliation

Run Authority's implementation is landed through three merged milestones, but
its current proof is not accepted: all three completion receipts are false and
canonical verification reports three divergences. The receipts cite stale or
missing phase evidence, landed-diff/content-address mismatches, and structural
collection/import failures. M3's reducer suite now passes 12/12, but that result
is not yet bound into its canonical phase/suite/completion evidence. M5 owns
this reconciliation and canonical retirement proof before adoption proceeds.

WBC owns the broad boundary/attempt/effect ledger and supported-runtime
conformance portions of the original migration design. A later read-only audit
on 2026-07-14 found completed candidate `cbe69337…` but no final landed revision:
its attempt ledger is explicitly schema-only and its producer inventory remains
partially declared/unknown. The current checkout still has no accepted WBC
completion manifest. M6 validates the final landed/runtime proof and generates
the boundary inventory; M6A operationalizes the WBC-owned ledger/API; M8 adopts
every producer without changing ownership. M6A-M11 remain blocked until M5/M6
handoffs plus the human approval record pass. No competing Custody ledger,
renamed WBC contract, or manually asserted support is allowed.

The residual gap is operational storage, universal integration and retirement:
transactional WBC writes/queries, controlled authoritative writers, exact-version adoption across the complete WBC set,
rebuildable projections and pure observers, effect-safe retry/recovery with
independent verification, cross-system conformance, and legacy deletion only
after parity/proof.

## Delivered substrate

- Native runtime work established compiled workflow/manifest identities,
  append-only kernel journals, content-addressed artifacts, replay/checkpoint
  contracts and completion manifests (`arnold/kernel/journal.py`,
  `arnold/execution/`, `native-python-pipelines-completion/completion-manifest.json`,
  `native-platform-followup/completion-manifest.json`).
- Native Parity names `.pypeline` plus named subworkflows as semantic topology
  authority and demotes components, handlers, manifests and graph projections
  to adapters (`megaplan-native-parity-corrective/NORTHSTAR.md`). Its chain has
  no completion manifest here, so delivered parity must not be assumed.
- Canonical Run-State implemented a pure typed resolver and ordered evidence
  model (`run_state/model.py`, `resolver.py`, `classifiers.py`) with extensive
  incident fixtures (`test_run_state_resolver.py`). It is a classifier, not a
  universal event store or writer migration.
- Run Authority delivered three milestones for grants, accepted attempts,
  decisions, quarantine and operational views; its manifest records all three
  as done. The copied dependency proof has null commit/publication fields, so
  “done” does not by itself prove landed runtime ancestry.
- Control bindings and transition APIs exist (`control_interface.py`,
  `planning/control_binding.py`), as do plan event journals, effect ledgers,
  receipts, incident events and resident managed-run manifests.
- WBC is actively defining exact boundary declarations, execution-attempt and
  effect evidence, semantic findings and broad runtime conformance. Its C1-C6
  identities and runtime must remain untouched by this plan.

## What was not migrated

Raw `state.json`/chain JSON writers and readers remain; status and liveness can
be recomputed from snapshots, markers, logs, PIDs/tmux and mtimes; watchdog,
repair, meta-repair and wrappers carry duplicate selectors; stage/handler and
compatibility projections remain callable; effects and retries span multiple
ledgers/sidecars; resident/cloud custody and completion delivery are separate;
and recovery can advance on liveness or mutation without a mandatory
post-transition authoritative reread plus independent verification.

Concrete current-code gaps include mismatched evidence vocabulary between
`cloud/current_target.py` and `run_state/evidence.py`; resolver enforcement
default-off while `cloud/status_snapshot.py` independently classifies; PID
liveness without process-birth identity; plan state written before its shadow
WAL; chain atomic rename without a writer lock/fsync; effect-journal failures
swallowed with in-process-only dedupe; writable execute auth/connection fallback
without the read-only guard; and separate ordinary reply, scheduled notification
and managed-completion delivery semantics. These are migration gaps, not missing
architectural concepts.

The resident child audit itself demonstrated this gap: a child prompt explicitly
forbade Discord delivery, yet the resident completion outbox delivered because
delivery authority lives outside the child prompt and lacks a parent aggregation
contract. The durable run manifests are listed in the final synthesis.

## Incident mechanism

Each local surface could be internally truthful while disagreeing about causal
supersession: a stale plan projection, live unrelated process, active repair,
dead worker, fresh observer-written event, delivered notification, and terminal
artifact can coexist. Without one fenced append order and exact contract
identity, readers choose different precedence rules. Repair can then duplicate,
retry after mutation, or call liveness recovery while chain/publication/delivery
remain unresolved.

## PC ambiguity

Repository evidence uses `pc` for the native program counter; portfolio language
also plausibly abbreviates Parity Corrective or control plane. No distinct
canonical “PC” initiative was found. This ambiguity is material because a
separate PC workstream could own cursor/checkpoint or parity surfaces. M6
therefore requires a human `PC_SCOPE_DECISION` before enforcement.
