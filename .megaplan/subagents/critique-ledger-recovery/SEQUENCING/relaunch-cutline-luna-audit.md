# Recovery checklist relaunch cut-line audit — Luna

Verdict: preserve all 55 tasks, but replace T6.1's vague “all preceding tasks” with an explicit safe-v3-canary cut. No checklist mutation is performed here.

Classes: `BLOCKS_SAFE_V3_CANARY` (must precede T6.1/T6.2), `BLOCKS_PRODUCT_DEPLOYMENT` (may follow bounded T6.2 but precedes T7.3/production acceptance), `POST_LAUNCH_CLOSURE` (durability/incident closeout after bounded launch).

## Recommended cut

The safe canary cut is: accepted control-plane generation and release receipt; v2 effects denied/tombstoned/deselected; fresh target-bound CL1/v3 specs and identities; attested preflight; one-transition grant/stop envelope. Then run T6.1 and independently prove T6.2 before any authority expansion. T6.3+ is not part of launch admission.

Current durable facts support this strict cut: T0.2/T0.4 are accepted; RA-CONTAIN `48e13e1...` has a local PASS only; T1 portfolio is not accepted; T2/T3/T4 preparations explicitly make no authority claim; T5.1 hard-fails with owner decisions pending. Therefore launch remains NO-GO today regardless of reordered housekeeping.

## All-task classification

| Task | Class | Dependency justification / sequencing note |
|---|---|---|
| T0.0 | BLOCKS_SAFE_V3_CANARY | Canonical containment decision is prerequisite to trusted fencing. |
| T0.1 | BLOCKS_SAFE_V3_CANARY | Poisoned tuple effects must be denied before successor authority. |
| T0.2 | BLOCKS_SAFE_V3_CANARY | Accepted evidence preservation prevents destructive recovery blindness; complete. |
| T0.3 | BLOCKS_SAFE_V3_CANARY | Capacity/WAL/reserve failure can lose launch authority/receipts. |
| T0.4 | BLOCKS_SAFE_V3_CANARY | Exact old target universe is needed for fences/noncollision; complete. |
| T1.1 | BLOCKS_SAFE_V3_CANARY | Raw target-bound CL2 admission is the first successor gate. |
| T1.2 | BLOCKS_SAFE_V3_CANARY | Failed critics must not become clean semantic results. |
| T1.3 | BLOCKS_SAFE_V3_CANARY | Immutable authentic bundles are needed before any model attempt. |
| T1.4 | BLOCKS_SAFE_V3_CANARY | First transition may graph-reject; bounded repair must already be safe. |
| T1.5 | BLOCKS_SAFE_V3_CANARY | Launch must not reintroduce recovery loops/duplicate fixer authority. |
| T1.6 | BLOCKS_SAFE_V3_CANARY | Every canary effect/model/notification boundary requires WBC. |
| T1.7 | BLOCKS_SAFE_V3_CANARY | Owner receipts must survive concurrency/crash/ENOSPC. |
| T1.8 | BLOCKS_SAFE_V3_CANARY | Exact installed generation and rollback are launch prerequisites. |
| T1.9 | BLOCKS_SAFE_V3_CANARY | This is the sole authorized launch/stop transaction. |
| T1.10 | BLOCKS_SAFE_V3_CANARY | Even one-transition incident UX must dedupe and preserve ambiguity. |
| T2.1 | BLOCKS_SAFE_V3_CANARY | Prevents stale M11 promotion from remaining competing authority. |
| T2.2 | BLOCKS_SAFE_V3_CANARY | Exact offline release candidate/no-debt evidence. |
| T2.3 | BLOCKS_SAFE_V3_CANARY | Isolated canary contract must precede production generation acceptance. |
| T2.4 | BLOCKS_SAFE_V3_CANARY | Installed fault/replay proof covers launch/stop/owner torn orders. |
| T2.5 | BLOCKS_SAFE_V3_CANARY | Every permitted route must fail closed before first critique. |
| T2.6 | BLOCKS_SAFE_V3_CANARY | Explicit deploy-eligibility decision scopes T3 only. |
| T3.1 | BLOCKS_SAFE_V3_CANARY | Fresh capacity/evidence/vector preflight. |
| T3.2 | BLOCKS_SAFE_V3_CANARY | Old writers must be fenced before generation promotion. |
| T3.3 | BLOCKS_SAFE_V3_CANARY | Installs the exact tested control-plane generation. |
| T3.4 | BLOCKS_SAFE_V3_CANARY | Independently proves live bytes/processes equal tested vector. |
| T3.5 | BLOCKS_SAFE_V3_CANARY | Recovery/rollback canaries prove launch platform before use. |
| T3.6 | BLOCKS_SAFE_V3_CANARY | Exact-revision release receipt is required; ticket-closing subeffect itself is overzealous for launch and could be split/deferred. |
| T4.1 | BLOCKS_SAFE_V3_CANARY | Exact v2 quarantine prevents identity collision/resumption. |
| T4.2 | BLOCKS_SAFE_V3_CANARY | Old resume/repair/execute/publish/notify grants must reject. |
| T4.3 | BLOCKS_SAFE_V3_CANARY | Advanced epoch+tombstone prevents lease/key ABA reuse. |
| T4.4 | BLOCKS_SAFE_V3_CANARY | Old ambiguous effects must be no-redispatchable before fresh effects. |
| T4.5 | BLOCKS_SAFE_V3_CANARY | Canonical selection must move away from v2 before v3 selection. |
| T4.6 | POST_LAUNCH_CLOSURE | T0.2 already preserves evidence; after T4.1–T4.5 make v2 read-only/denied, final WORM/archive freeze need not block one transition. Overzealous current prerequisite. |
| T5.1 | BLOCKS_SAFE_V3_CANARY | Raw CL1 reviewer/coherence/proof/ownership/portfolio blockers must resolve. |
| T5.2 | BLOCKS_SAFE_V3_CANARY | Fresh target-bound handoff is successor admission input. |
| T5.3 | BLOCKS_SAFE_V3_CANARY | Fresh v3 specs/preconditions define exact launch subject. |
| T5.4 | BLOCKS_SAFE_V3_CANARY | Fresh noncolliding launch/publication identity. |
| T5.5 | BLOCKS_SAFE_V3_CANARY | Attested local and read-only remote preflight. |
| T5.6 | BLOCKS_SAFE_V3_CANARY | Exact one-transition scope/TTL/stop/verifier envelope. |
| T6.1 | BLOCKS_SAFE_V3_CANARY | The bounded launch action itself; cut terminates here. |
| T6.2 | BLOCKS_SAFE_V3_CANARY | Mandatory proof before expanding authority; safe-canary outcome. |
| T6.3 | BLOCKS_PRODUCT_DEPLOYMENT | Ordinary plan/critique/gate/finalize may follow proven first transition. |
| T6.4 | BLOCKS_PRODUCT_DEPLOYMENT | Real CL2 feature work is product input, not launch prerequisite. |
| T6.5 | BLOCKS_PRODUCT_DEPLOYMENT | Publication of successor work follows implementation. |
| T6.6 | BLOCKS_PRODUCT_DEPLOYMENT | CL3–CL5 completion precedes successor acceptance/deploy, not initial canary. |
| T7.1 | BLOCKS_PRODUCT_DEPLOYMENT | Product PR acceptance/merge. |
| T7.2 | BLOCKS_PRODUCT_DEPLOYMENT | Content-addressed product generation. |
| T7.3 | BLOCKS_PRODUCT_DEPLOYMENT | Authorized product deployment and writer fence. |
| T7.4 | BLOCKS_PRODUCT_DEPLOYMENT | Production semantic/recovery/ambiguity scenarios. |
| T7.5 | BLOCKS_PRODUCT_DEPLOYMENT | Canary-window acceptance gates broad production completion. |
| T8.1 | POST_LAUNCH_CLOSURE | Final successor manifest follows verified product. |
| T8.2 | POST_LAUNCH_CLOSURE | Incident resolution explicitly follows v3/product verification. |
| T8.3 | POST_LAUNCH_CLOSURE | Permanent replay gate is institutionalization. |
| T8.4 | POST_LAUNCH_CLOSURE | Operator runbook/card publication; interim T1.10 UX still blocks launch. |
| T8.5 | POST_LAUNCH_CLOSURE | 24h/72h/7d observation necessarily post-launch/deploy. |

## Dependency corrections

1. Replace T6.1 “all preceding tasks” with explicit prerequisites T0.0–T0.4, T1.1–T1.10, T2.1–T2.6, T3.1–T3.6 release-receipt portion, T4.1–T4.5, and T5.1–T5.6.
2. Move T4.6 after T6.2 but before incident closure; T0.2 plus T4.1–T4.5 supply safe preservation/denial meanwhile.
3. Split T3.6 logically: exact release receipt blocks launch; administrative closure of the two release tickets can occur after receipt without widening T6.1 authority. Preserve both obligations.
4. T6.3–T6.6 and all T7 tasks must not block the scoped one-transition canary; they are the staged expansion/product path.
5. T8 is entirely post-launch closure. T8.4 does not waive T1.10's launch-critical quiet-notification mechanism.

No task is deleted or weakened. The reordered cut reduces circularity: it proves the launch mechanism with one transition before demanding that the launched epic finish and deploy its product.

Read-only audit only; no checklist, code, Git, cloud, owner, marker, plan or process state was mutated. SHA-256 is recorded externally.
