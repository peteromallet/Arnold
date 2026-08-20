# T0.4 implementation brief — authoritative incident inventory

Use GPT-5.6 Luna high reasoning. Build the T0.4 incident inventory from preserved,
read-only evidence. Work in the dirty repository only as a reader. You may write only:

`/Users/peteromalley/Documents/Arnold/evidence/critique-ledger-recovery/T0.4/`

and ephemeral `/private/tmp` files. Do not edit code, plans, specs, branches, markers,
worktrees, T0.2 evidence, cloud state, or external services. Do not commit/push/deploy,
stop/resume/clean/notify, or invoke retired megaplan-cloud mutation commands.

Primary evidence:

- `evidence/critique-ledger-recovery/T0.2/manifest.json`
- `evidence/critique-ledger-recovery/T0.2/objects/sha256/`
- `evidence/critique-ledger-recovery/T0.2/verification-receipt.json`
- `.megaplan/subagents/critique-ledger-recovery/` forensic reports
- `docs/arnold/critique-ledger-incident-prevention-and-durable-recovery-plan-2026-08-02.md`
- repository authority/custody/WBC/run-state schemas and readers

Target session: `critique-ledger-accountability-v2-20260728`; target plan:
`cl2-wbc-backed-ledger-20260731-1411`.

## Required result

Publish one canonical inventory that *joins without replacing* the owner records for:

- Run Authority grants/decisions/fences/revocations;
- Custody targets/leases/epochs/fence tokens/claims;
- WBC operations, GLEKs, intents, attempts, outcomes, provider receipts, ambiguity;
- incident occurrences, diagnostic attempts, repair/fixer occurrences/results;
- plan/chain/phase/task state and cursors;
- notification incidents/intents/delivery receipts/message IDs;
- selection/session/spec/workspace/plan/branch/profile/runtime tuples;
- cloud generation/image/package/commit/Python/wrapper/config/model-route facts;
- processes, PIDs, executables, imports, containers, mounts, storage health;
- Git branches, commits, dirty state, worktrees, publication/deployment intents;
- markers/projections/artifacts and every old writer/effect surface;
- every missing/unknown/indeterminate record that later reconciliation must preserve.

Each inventory row must have:

- deterministic target/record ID and category;
- exact logical identity/scope tuple;
- owner system and source owner-record path/URI;
- current state plus whether it is authoritative, projection, evidence-only, inferred,
  unavailable, or ambiguous;
- cursor/revision/epoch/fence/GLEK/occurrence/message/provider IDs where present;
- source evidence claim/object digest and a minimal safe excerpt/query basis;
- required later action (`preserve`, `fence`, `revoke`, `expire`, `reconcile`,
  `quarantine`, `CAS-away`, `read-only-freeze`, `no-redispatch`, `verify`, or `none`);
- prerequisite authority and the exact downstream checklist task(s);
- confidence and explicit gap/reason. Clearly label inference; never promote projection
  or narrative into authority.

Outputs:

1. `inventory.json` with a strict documented schema;
2. `inventory.csv` for operator scanning;
3. `README.md` summarizing counts, critical targets, contradictions, and blockers;
4. `verify_inventory.py` plus `verification-receipt.json` that validates schema,
   deterministic IDs, source claim/object existence and digest, uniqueness, legal state
   vocabulary, and that every later T4 fence/reconciliation action has exact targets;
5. `unresolved.json` containing every ambiguity/missing owner record and why it must not be
   treated as absent/safe.

Do not copy secrets or raw sensitive payloads into excerpts. Do not contact providers.
Use the T0.2 content-addressed objects; do not rewrite them. If a required authority class
has no persisted record, inventory the authoritative absence/gap with the exact successful
bounded query that proved it, and require fail-closed treatment.

Run the verifier. Return exact output paths, counts by category/state/action, receipt ID
and SHA-256, gaps/contradictions, and whether T0.4's completion criterion is satisfied.
It is complete only if every later fence/reconciliation task has an exact target or an
explicit fail-closed unresolved target—not merely a prose summary.
