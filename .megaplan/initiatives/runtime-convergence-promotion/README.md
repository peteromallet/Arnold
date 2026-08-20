# Runtime Convergence Promotion

Certify the newest completed Megaplan maintenance code, publish one immutable
integration revision, and move the maintenance and Astrid epics onto separate
per-epic runtime roots with one coherent dependency identity. Preserve the
current roots and receipts as rollback evidence throughout.

The canonical starting lineage is `4ef83c15d9` → `d38c3980a6`. The bootstrap
successor `6ea4111196` restores the documented `config` CLI contract and is the
initial candidate revision; the plan may advance it only through reviewed,
tested commits on the same branch.

The attached decisions document is the governing execution plan:
`decisions/pasted-text-1.txt`.

## Current truth and index

Keep this README current as the initiative front door: state the outcome, boundaries, success criteria, lifecycle/readiness, and link the canonical documents below. Initiative creation records commitment to an outcome; it does not launch work.

- `briefs/` — curated planning inputs and milestone briefs.
- `research/` — evidence, investigations, alternatives, and syntheses.
- `decisions/` — durable decisions with rationale and consequences.
- `notes/` — working notes worth retaining but not yet promoted.
- `handoff/` — curated handoffs and canonical syntheses; cite raw agent/subagent run artifacts instead of copying raw output here.
- `assets/` — supporting non-prose files.
- `NORTHSTAR.md` — optional durable end-state anchor, added when lifecycle maturity needs it.
- `chain.yaml` — optional executable coordination, added only when execution is ready.

Promote notes/research into decisions or briefs when they become authoritative, and update this index. Search and reuse related documents, tickets, and initiatives before creating another artifact.
