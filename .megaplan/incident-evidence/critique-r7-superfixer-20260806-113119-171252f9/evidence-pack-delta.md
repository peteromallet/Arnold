# Evidence Pack Delta — R7 Superfixer retry occurrence (v3)

occurrence_id: occ_critique_r7_superfixer_retry_20260806_v3_86e40e1e0058ad7934f251c0
occurrence_key: sha256:86e40e1e0058ad7934f251c001a766e432730da1ca7b4cd57477982206b10899
managed_run_id: subagent-20260806-113119-171252f9 (model hermes:deepseek:deepseek-v4-flash via resident managed subagent, worker_pid 1029129)
schedule: sched_critique_r7_superfixer_retry_20260806_v3 (revision 1, generation 1)
observed_at (UTC): 2026-08-06T11:31:00Z .. 11:45:00Z

Prior occurrences (same target, same protocol lineage, DO NOT duplicate):
- v1 09:31: /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-093148-0d3c3bc5/ (evidence-pack.md, sol-stage1.md, swarm/ fq-01..fq-10, swarm-index.json, repair-producer-attempt.json)
- v1 10:40: /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-104038-ca591908/ (evidence-pack-delta.md, sol-stage2.md, recovery-handoff.json handoff_id sha256:96fdcee6e5b9e88df587c43283afcebcf9f9afa346c9c86ce52d73ed80070dd4, blocked-receipt.json, immediate-fix-and-category-hardening.md)

## 1. What changed since the prior blocked receipt (10:40Z)

1. Pinned runtime identity VERIFIED RESTORED (the prior receipt's missing gate "verified active editable-runtime identity (recorded bind-time .pth missing)" is now satisfied):
   - `runtime_provenance(expected_root=/workspace/runtime-candidates/arnold-r7-fresh-child-20260805, expected_revision=d5848010695e28ddb9d9cbee8675d7ebe725caae)` => ok:true, errors:[], import_root/editable_root match, source_revision d5848010..., runtime_identity content_sha256 e8b12504130bd283333891ffd5e14f126bb5cd6558892153b4b533a2417fe5e6 (exact expected), editable .pth present (sha256 a2e6bee4907592da90ed9ed56d2e1bfa8dfabf6b9c5cd8b9b5f30d1194eae9ff).
   - `run_mp chain status` => execution_binding.status=match, runtime_binding.status=match (expected == active, all six revision checks match).
2. Operator constraint (this occurrence's prompt, mandatory): "do not switch the chain to runtime B" — the A->B rebind route from the prior Horizon A is explicitly excluded. Bound runtime remains A (arnold-r7-fresh-child-20260805 @ d5848010, content e8b12504). Runtime B candidate (arnold-r7-fresh-child-20260805-77b76e3a4 @ 77b76e3a487809a2d1c89ea6785aac473c8931c8) remains UNAUTHORIZED and must NOT be adopted by this occurrence.
3. Follow-up ticket 01KZBC4GX4C8SN38Z53RSWZJEG materialized (open, source human, created 2026-08-06T11:08:03Z, .megaplan/tickets/01KZBC4GX4C8SN38Z53RSWZJEG-r7-cl2-finalize-recovery-authorize-runtime-rebindmigrated-child-durable-finalize.md).
4. Authoritative fingerprint (same method as prior occurrences, fingerprint.py): combined_sha256 sha256:a8c4416eb4e87db1d2bf52c2ee18c4f39c050206803f73bcac27867729c0e68b. Prior (10:40) was sha256:f606c1a81311e3d4109e3343dcb43d230d9a0fe411560e08605fd1c83a3e25e9. Per-section diff: ONLY checkout.status_porcelain changed (new untracked .megaplan/tickets/01KZBC4GX4C8SN38Z53RSWZJEG-*.md added). chain_state, plan, leases, repair_queue sections are byte-identical.

## 2. Canonical state re-verified (all unchanged from prior pack, re-read fresh)

- chain state (.megaplan/plans/.chains/chain-880bd6e04632.json): last_state=blocked, current_milestone_index=0, current_plan_name=cl2-wbc-backed-ledger-20260805-2140, completed=[], target_base_ref d5848010, runtime_binding content e8b12504 (bound A), rebind_events=[].
- plan state.json: current_state=blocked, iteration=5, history 21 entries, last entry gate success PROCEED at 2026-08-06T00:53:17Z (artifact sha256 9df9582599f9fe096df87ab1ff23665a9e116ea959deae3e3102feab9dbead3b). No finalize history entry.
- events.ndjson: 3099 records, last seq 3098 phase_start(finalize) 2026-08-06T00:53:46.130Z + state_written current_state=blocked; finalize phase_start/phase_end cycled 3x (00:53:27-00:53:46) with NO llm_call_start/llm_call_error; state transitioned critiqued->gated (00:53:27Z) then blocked (00:53:46Z).
- Liveness lease: status=stopped, expires_at 2026-08-06T00:53:46.682173Z, publisher_pid 629623 (DEAD, confirmed via ps), runner_fence=1, sequence=2315.
- introspect: plan_state=blocked, active_phase liveness=stalled ("last event 38474s ago (>300s) and no in-flight LLM"), in_flight_llm=None, block_details.is_blocked=true, cost total $14.61.
- No live runner, no recovery owner, no finalize repair request/claim/WBC attempt. repair-queue contains only the pre-blocker revise request 74403266... (lifecycle_failure, predates 00:53:17, self-recovered).
- No notification intent/effect for this blocker.

## 3. Deterministic root cause — RE-REPRODUCED this occurrence (read-only, /tmp copy of plan dir, pinned runtime A)

- `write_critique_clearance` (finalize preflight, orchestration/critique_custody.py) raises CritiqueCustodyError:
  code=critique_finding_unresolved, issues=["finding CF-0B506E1EDCD92E90C192 / flag CF-0B506E1EDCD92E90C192 remains 'accepted_tradeoff'; it needs a traceable plan mutation plus verification, or an evidence-backed invalidation"].
- Mechanism: faults.json has 95 flags (58 verified, 25 open, 12 accepted_tradeoff). 10 of the 12 accepted_tradeoff flags carry gate_resolution.action=accept_tradeoff + rationale (resolved as minor_tradeoff). TWO flags lack gate_resolution entirely: CF-0B506E1EDCD92E90C192 and CF-B67C1E37D72114DDCF70 (both severity significant, resolution.kind=fixed, addressed_in=plan_v2.md, status accepted_tradeoff, gate_resolution=null). `_resolution_for_finding` in runtime A has no branch admitting `accepted_tradeoff && gate_expected && fixed_claim` (runtime B adds exactly that branch; A does not).
- First failure raised on CF-0B506E1EDCD92E90C192; CF-B67C1E37D72114DDCF70 would fail identically.
- v5 gate PROCEED carried neither flag in accepted_tradeoffs nor gate_carry.json.

## 4. Facts vs inference

FACTS: chain/plan blocked; runner dead; lease stopped; binding matches A; provenance ok; root cause reproduced exactly; no recovery in flight; prior handoff externally gated; operator excluded B; fingerprint a8c4416e (only ticket file changed vs prior).
INFERENCE (for Sol): the only in-scope repair families are (a) canonical control-plane repair of the two registry records through a supported seam (none identified yet), (b) source-level fix in runtime A deployed via the supported content-addressed cloud path (would make A accept the state — equivalent to B's one-commit fix, but as a NEW authorized runtime lineage/deployment, not "switching the chain to B"), (c) authority-approved migrated child, (d) external approval gate remains.
UNKNOWN: whether a supported seam exists to re-admit the gate's accepted-tradeoff resolutions into faults.json (candidate: re-running the gate producer); whether editing the pinned runtime A source is permitted by the launch boundary; whether the interrupted third finalize attempt left any external effect (INDETERMINATE since prior FQ-05).

## 5. Constraints for Sol stage 2

- Do NOT propose switching the chain to runtime B (77b76e3a4). Do NOT rebind the session marker casually.
- The occurrence is preserved: same logical target occurrence digest sha256:f3b952beb7881acc80f5efc98b1f21b64a911cc6d17dd87b220e1d336b4e55c5 (fresh-child admission), plan/chain state immutable.
- Horizon A must be the shortest safe route that genuinely advances the accepted work, with one canonical request -> Run Authority decision -> Custody claim/epoch -> WBC attempt/effect -> ordinary fixer -> verification, OR a precise external gate with named approver, receipt, and machine-checkable return condition. A quarantine paragraph alone is incomplete.
- Emit the machine-readable arnold.superfixer.recovery_handoff.v1 envelope (JSON) as a fenced block; the executor will validate handoff_id = sha256 of exact envelope bytes.
