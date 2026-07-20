Read the predecessor result. Preserve WORD_1 through WORD_3 in order, choose a different fourth random ordinary English word, and return exactly four WORD_n lines in order followed by WORDS_IN_ORDER: <word1>, <word2>, <word3>, <word4>. Do not mutate anything.

[Queued predecessor references — bounded typed refs only]
- schema: arnold-resident-subagent-reference-v1
- predecessor_run_ids: ["subagent-20260716-185232-22726cfd"]
- instruction: inspect only the artifacts needed for the authored prompt; full content is not embedded
- manifest: /workspace/arnold/.megaplan/proofs/nonmutating-chain-31d72c3a85/.megaplan/plans/resident-subagents/subagent-20260716-185232-22726cfd/manifest.json
- result: /workspace/arnold/.megaplan/proofs/nonmutating-chain-31d72c3a85/.megaplan/plans/resident-subagents/subagent-20260716-185232-22726cfd/result.md
- log: /workspace/arnold/.megaplan/proofs/nonmutating-chain-31d72c3a85/.megaplan/plans/resident-subagents/subagent-20260716-185232-22726cfd/run.log

[Resident delegation execution/delivery instruction — canonical v1]
- schema: arnold-resident-delegation-delivery-instruction-v1
- resolved work intent: execution
- resolved mutation claim: none
This is authorized non-mutating execution: produce and verify the requested durable result without changing a repository, branch, worktree, service, or external system. Git commit/diff/clean-worktree custody is not applicable to successful completion. If the task actually requires a git-backed mutation, stop and report the contract mismatch instead of mutating under this claim. This instruction is appended by the resident launch boundary and does not expand the user's authority. Preserve the inherited immutable Discord/delegation provenance; never replace, reconstruct, or reinterpret its source envelope.

[Completion delivery contract]
[User-time presentation rule]
Render absolute user-visible times in UTC with local date/time, timezone abbreviation, and numeric UTC offset. Keep stored/control-plane/evidence timestamps in UTC and keep relative durations relative.

[Delegated context directory]
The full resident/cloud/conversation state is deliberately not embedded. Use these bounded routes only when the task needs more evidence.
- project worktree: /workspace/arnold/.megaplan/proofs/nonmutating-chain-31d72c3a85
- resident runtime source: /workspace/arnold-resident-nonmutating-verification-fix-20260716
- resident runtime revision: 31d72c3a85e20c0a76a1d5d96df2d7ce84d77ecb
- project is runtime source: False
- resident conversation: rconv_85a1c2bfd5f1
- context root: python -P -m arnold_pipelines.megaplan resident context --node root --store-root "$MEGAPLAN_RESIDENT_STORE_ROOT"
- targeted node: python -P -m arnold_pipelines.megaplan resident context --node '<node_id>' --store-root "$MEGAPLAN_RESIDENT_STORE_ROOT"
- scoped search: python -P -m arnold_pipelines.megaplan resident context-search --scope '<scope>' --query '<query>' --store-root "$MEGAPLAN_RESIDENT_STORE_ROOT"
- older reply ancestry: python -P -m arnold_pipelines.megaplan resident read-reply-chain --cursor '<cursor>' --store-root "$MEGAPLAN_RESIDENT_STORE_ROOT"
The immutable Discord source envelope is inherited in the process environment. Never replace it with a recent-message guess. The project worktree may differ from the pinned resident runtime; inspect both before resident-code changes, preserve concurrent dirty work, and publish/deploy only after explicit tree/revision reconciliation.

[Query relationship and delivery ownership]
- classification: independent
- root request source/message: msg_dfab6b2b7c55 / 1527380307983204512
- root semantic description: unavailable
- earlier request source/message: n/a / n/a
- current follow-up source/message: msg_dfab6b2b7c55 / 1527380307983204512
- current semantic description: unavailable
The current/newer request is the sole delivery and aggregation target. Consolidate relevant earlier work into one reply; internal reviewers report through the synthesis owner and must not emit independent user-facing completions.

[Internal contributor evidence to synthesize]
[{"aggregation_role": "internal_contributor", "delivery_status": "suppressed", "description": "Choose fresh proof word one.", "manifest_path": "/workspace/arnold/.megaplan/proofs/nonmutating-chain-31d72c3a85/.megaplan/plans/resident-subagents/subagent-20260716-185232-0ada2fe4/manifest.json", "result_path": "/workspace/arnold/.megaplan/proofs/nonmutating-chain-31d72c3a85/.megaplan/plans/resident-subagents/subagent-20260716-185232-0ada2fe4/result.md", "run_id": "subagent-20260716-185232-0ada2fe4", "status": "running"}, {"aggregation_role": "internal_contributor", "delivery_status": "suppressed", "description": "Choose fresh proof word three.", "manifest_path": "/workspace/arnold/.megaplan/proofs/nonmutating-chain-31d72c3a85/.megaplan/plans/resident-subagents/subagent-20260716-185232-22726cfd/manifest.json", "result_path": "/workspace/arnold/.megaplan/proofs/nonmutating-chain-31d72c3a85/.megaplan/plans/resident-subagents/subagent-20260716-185232-22726cfd/result.md", "run_id": "subagent-20260716-185232-22726cfd", "status": "queued"}, {"aggregation_role": "internal_contributor", "delivery_status": "suppressed", "description": "Choose fresh proof word two.", "manifest_path": "/workspace/arnold/.megaplan/proofs/nonmutating-chain-31d72c3a85/.megaplan/plans/resident-subagents/subagent-20260716-185232-bd11d7f0/manifest.json", "result_path": "/workspace/arnold/.megaplan/proofs/nonmutating-chain-31d72c3a85/.megaplan/plans/resident-subagents/subagent-20260716-185232-bd11d7f0/result.md", "run_id": "subagent-20260716-185232-bd11d7f0", "status": "queued"}]
Wait for every listed contributor manifest to become terminal, then read and consolidate its durable result. They are evidence inputs, not independent user-facing delivery owners.

Your FINAL response will be sent directly to the user as a Discord reply. Make it a concise, user-facing summary that stands on its own. State the outcome, the important changes or findings, verification performed, and any remaining operational caveat. Do not include internal handoff notes, ask a follow-up question, or merely say that work is complete. Never expose credentials or other secrets. Preserve and follow all task-specific instructions above.
