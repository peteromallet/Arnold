# VJ24 superfixer review → post-relaunch epic crosswalk

Date: 2026-08-05  
Incident: `critique-ledger-accountability-v3-r5-20260803` / `VJ24`  
Inputs: the evidence pack, Sol stage 2 adjudication, and the Luna reports under
`evidence/critique-v3-r5-vj24-20260805/`.

## Conclusion

The replacement `superfixer-debug` process does not replace the
`critique-ledger-post-relaunch-completion` epic. It is the incident-response
and decision protocol that must be used before repairing a blocked occurrence.
The follow-up epic is the implementation/completion vehicle for most of the
durable controls that this review identified.

There is substantial overlap, but it is intentional:

| New review finding | Existing follow-up coverage | Disposition |
| --- | --- | --- |
| Selector/task-output contract must be explicit and content-addressed | F2 admission/model/effect closure; ordinary execution acceptance | Add the concrete `selector_task_output_contract.v1` acceptance artifact to the relevant F2 brief; do not change the canary boundary. |
| One occurrence-bound causal history across run, runtime, evidence, repair and effects | F1 owner/storage/recovery; P2 control-plane mapping; incident-specific amendment | Covered in principle; require the identity tuple and migration receipt from the new Sol stage-2 contract as acceptance evidence. |
| Run Authority owns decisions/fences; Custody owns occurrence/lease/epoch; WBC owns attempt/effect evidence | NORTHSTAR and F1/F2 mapping | Covered; this is a clarification of ownership, not a new authority. |
| Credential bootstrap and role-scoped provider resolution | F2 provider resolver and incident-specific amendment | Covered; add the shared bootstrap/capability-attestation test to F2. |
| Pinned runtime/import/source/test identity | F1 repair receipts, F2 installed parity, incident-specific amendment | Covered; require the r5 migration receipt and reject marker-only liveness. |
| Snapshot-first observation and notification intent/effect dedupe | F1 notification custody and F2 status/incident dedupe | Covered; add stale-snapshot/duplicate-projection reconciliation as an explicit negative test. |
| Same-occurrence retry is unsafe after crossed bindings; use accepted migrated child revision | Stable canary boundary and T6.2 handoff rules | Immediate recovery rule, not a follow-up milestone: quarantine r5 and require the supported migration operation before any new run. |
| Legacy sessions and stale projections must not be revived implicitly | Incident-specific amendment; F2 entry-point inventory | Covered; add the exact r5 duplicate-session classification to the evidence set. |
| Generic fixer must be evidence-driven, bounded and notification-deduplicated | Follow-up epic's F1/F2 implementation obligations | The new skill is the operating procedure; the epic implements the substrate it relies on. |

## What is not covered by the replacement skill

The skill does not complete F1/F2 or the later F3–F8 milestones. It does not
claim product completion, release/deployment, ordinary CL2/CL3/CL5 work,
incident closeout, or 24-hour/72-hour/7-day durability. Those remain in
`.megaplan/initiatives/critique-ledger-post-relaunch-completion/` and must still
be gated by the accepted T6.2 safe-v3 handoff.

Conversely, the follow-up epic does not by itself replace the skill's
evidence-first Sol → Luna → Sol adjudication loop. That loop is now the
required way to investigate future blocked occurrences and to decide whether a
repair is an ordinary epic item, an occurrence migration, or an
`INDETERMINATE` quarantine.

## Ordering rule

1. Keep the current r5 occurrence quarantined; do not resume it in place.
2. Obtain an authoritative snapshot and the complete identity tuple.
3. If the tuple is consistent, use the supported operator-authorized migration
   to create a new fenced occurrence/revision; otherwise classify as
   `INDETERMINATE` and stop.
4. Run the bounded, fail-closed v3 canary and obtain the committed T6.2
   acceptance manifest.
5. Only then launch the post-relaunch epic. Its F1/F2 briefs should include the
   concrete acceptance artifacts called out above, while F3–F8 remain the
   product/release/durability tail.

This keeps the immediate recovery and the long-term hardening connected without
turning the follow-up epic into an unsafe relaunch shortcut.
