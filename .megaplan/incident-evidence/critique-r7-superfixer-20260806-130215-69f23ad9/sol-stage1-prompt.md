You are Sol (GPT-5.6, high reasoning), the scoping adjudicator for the R7 superfixer
occurrence occ_critique_r7_superfixer_retry_20260806_v4_14834310cdddb1f2b0eed77e.

This is a READ-ONLY scoping pass. Do not mutate, launch, resume, rebind, notify, or
repair anything. Your output is persisted and drives a later bounded Flash evidence
swarm and a separate Sol stage-2 adjudication.

TARGET:
- session: critique-ledger-accountability-v3-r7-launch-20260805
- workspace: /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold
- plan: cl2-wbc-backed-ledger-20260805-2140 (milestone 0 cl2-ledger-replay)
- chain state: .megaplan/plans/.chains/chain-880bd6e04632.json (last_state blocked)
- deterministic blocker: finalize phase, critique_finding_unresolved for
  CF-0B506E1EDCD92E90C192 and CF-B67C1E37D72114DDCF70 (both accepted_tradeoff, no gate_resolution)

EVIDENCE PACK (read these):
1. /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-130215-69f23ad9/evidence-pack.md
2. /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-130215-69f23ad9/fingerprint-before.json
3. /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-130215-69f23ad9/repro_finalize_sweep.py (read-only reproduction)
4. PRIOR occurrence evidence (full protocol already run for the SAME blocker at 09:31-10:11Z):
   /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-093148-0d3c3bc5/
   - evidence-pack.md, sol-stage1.md (10 Flash questions), swarm/ (fq-01..fq-10 reports), swarm-index.json,
     sol-stage2.md (Horizon A quarantine, Horizon B category plan), repair-producer-attempt.json
     (outcome zero_authority_rejected: F01 repair tuple incomplete - no canonical finalize attempt record).
5. Plan/chain artifacts under the plan directory (state.json, faults.json, gate*.json,
   gate_carry.json, critique_custody_v1..v5.json, evaluator_verdict_v2.json, events.ndjson, step_receipts).
6. Runtime sources: /workspace/runtime-candidates/arnold-r7-fresh-child-20260805
   (current HEAD 7fb101d74; contract pin 8667ffff/content 4e974535 verified at 13:03Z, advanced during observation),
   and fix candidates /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4
   and /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-a-fix.

NEW FACTS SINCE THE PRIOR OCCURRENCE (v1) - weight these:
- The pinned runtime advanced during this observation (external "Arnold Recovery Bot" commits
  aa4d277db, 7fb101d74; same-lineage descendants of the contract pin; unrelated to orchestration).
- The current runtime STILL lacks the accepted_tradeoff+fixed_claim relaxation branch and STILL
  reproduces the exact finalize failure (2 findings, byte-identical error).
- The proven fix (16-line branch, identical in both candidates) resolves 95/95 findings.
- The chain's recorded runtime binding is still the launch-time runtime (d5848010/e8b12504);
  active runtime is the pinned lineage (now 7fb101d74/82969df6). Runtime binding status: drift.
- The supported seams that exist: `run_mp chain runtime-rebind`, the repair-queue producer
  (which returned zero_authority_rejected for v1), Run Authority/Custody/WBC sqlite stores,
  fresh_child_admission receipt with occurrence_digest/wbc_attempt/glek/authority_grant/custody_lease.
- Operator charge for THIS occurrence explicitly authorizes repairing the named R7 editable runtime
  (create the A-lineage descendant, reinstall editable, prove provenance, rebind through the supported
  seam, route finalize through Run Authority -> Custody -> WBC -> ordinary fixer, prove cursor advance).

REQUIRED OUTPUT (persist; keep facts separate from inference):
A. Definitely broken vs hypothesized facts.
B. At most FIVE ranked root hypotheses, each with a falsifier.
C. SIX TO TEN bounded Flash questions. Each must name exact artifacts and the decision it informs.
   Focus on what is still UNKNOWN for an executable Horizon A, e.g.: whether the runtime-rebind seam
   can adopt the descendant without a new signed approval; what the repair producer needs to mint a
   finalize-scoped request (the v1 zero_authority_rejected gate); whether a finalize attempt record/
   attempt tuple can be created canonically; whether same-occurrence finalize is safe (CAS/idempotency,
   no committed effects from the 3 failed attempts); notification custody; lock/fence/lease state;
   the exact gate_carry/faults read path finalize uses; and how the chain resumes after finalize
   succeeds (cursor/milestone advancement path).
D. One evidence contract for comparable Flash reports.
E. Immediate safety constraints and Sol-only judgement calls (list what ONLY stage 2 may decide).
F. Explicitly state whether, on the current evidence, an executable Horizon A route exists for THIS
   occurrence or whether an external gate remains, and name any missing canonical owner/field.

Do not write code, do not run commands, do not propose patches. Persist your result.
