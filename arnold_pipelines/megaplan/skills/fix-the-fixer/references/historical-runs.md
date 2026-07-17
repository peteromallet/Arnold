# Historical fixer-repair runs

Use these as prompt and proof precedent, not as current runtime truth. Raw
managed artifacts remain authoritative. The quoted prompt bodies below omit the
automatically appended resident delivery, context-directory, git-custody, and
Discord provenance contracts; their prompt hashes cover the complete files.

The canonical search that led here covered initiative, ticket, and document
names/content for `superfixer`, `fixer`, `L3`, `progress auditor`, `meta repair`,
`repair the repairer`, and `custody`. The closest synthesis was
`.megaplan/initiatives/megaplan-maintenance/research/l3-repair-the-repairer-prompt-recommendations-20260716.md`,
indexed by that initiative's `README.md`. The only matching ticket,
`.megaplan/tickets/execute-authority-rerun-loop-post-rebase-evidence-storm.md`,
concerned a different execute/rebase loop. Supporting operational documents
included `docs/hetzner-watchdog-meta-loop.md`, `docs/ops/recovery-runbooks.md`,
and `docs/ops/tiered-repair-and-audit-loop.md`. These paths are search evidence,
not proof that their current contents ship with this skill.

## Evidence index

| Run | Complete prompt SHA-256 | Raw artifacts | Observed outcome |
| --- | --- | --- | --- |
| `subagent-20260716-170615-ea341358` | `8e63294b7d18bad0b5d43b67c6ead0821d9c45ec56b4c96e3036e994fdb3966b` | `.megaplan/plans/resident-subagents/subagent-20260716-170615-ea341358/{manifest.json,prompt.md,run.log,result.md,git-custody-evidence.json}`; result SHA `9cd54bf41fcef4dfd67054a607da790db4e7bb28dded93d22f0d9b039fd18ccf` | Repaired stale failure custody, retriggered ordinary L2→L1, cleared the false block, and advanced the original plan from iteration 3 to 4. Focused independent verification passed 58/58. No push or remote merge. |
| `subagent-20260716-201212-a5bcc8ed` | `682d5363d36a682b86eea338c42e1a1617e4736236fc95a82a6cbcb025e949a6` | `.megaplan/plans/resident-subagents/subagent-20260716-201212-a5bcc8ed/{manifest.json,prompt.md,run.log,result.md,git-custody-evidence.json,superfixer-incident-evidence.json}`; result SHA `753c0431d5ac4ebc4220ee40a356e41962aeea16486a64f382729c4d08aac2bc` | Fixed self-coalesced repair custody and its L3 projection, claimed the exact request, cleared the original identity blocker, and advanced through iteration 9. A distinct later schema blocker remained. No push or remote merge. |
| `subagent-20260716-211612-5f63a2e2` | `004437fa2b0630ab8cc8043b1f5a4878ece314429a9c82ba59ff050738d3d398` | `.megaplan/plans/resident-subagents/subagent-20260716-211612-5f63a2e2/{manifest.json,prompt.md,run.log,result.md,git-custody-evidence.json,recovery-evidence.json}`; result SHA `24800b0ca7e76346d6dece9cc026c2ac4e03497f0cb573ca1dfb74a896d1b8f0` | Ordinary repair cleared the original blocker and moved `blocked → gated`; a distinct runtime-binding authority gate then stopped further effects. Six commits and the occurrence/backstop regressions were locally integrated. No rebind, push, restart, or remote merge. |

The first run's local repair commit `fd085c4ad8638e4bd19aeef37e6a17c17a297341`
was integrated into its then-pinned target but is not an ancestor of the later
resident target `817e46b2ebdba6e8761daee274456d6418734ccc`. The later representative commits
`ef27888be6f4a0579e490c981d9d01ca2fa1e361`,
`e5b7a2b29b074b407818c07bad795459f57ca321`, and
`236a746b36b811aa0ba32701d897f6174a8100fc` are ancestors of that target. This
is why historical success demonstrates the method, not current deployment.

## Recovered prompt 1: full custody repair

Source: `subagent-20260716-170615-ea341358/prompt.md` before the canonical
resident addenda.

> You are the sole synthesis/delivery owner for an authorized execution task.
> Use the `superfixer-debug` skill fully. Fix the automated Superfixer custody
> chain, retrigger it against the original stuck session, observe whether the
> automated fixer genuinely repairs the real problem, and iteratively refine
> the Superfixer until the original session recovers or a real approval/authority
> gate is reached.
>
> Establish visibility and inspect all six custody sources; walk watchdog → L1
> repair → L2 meta-repair → L3 auditor using TRACKED/FIXED/INTENT/CONTEXT;
> isolate git changes from the pinned resident target; implement the narrow root
> fix and the missed L2/L3 backstop; run focused tests and wrapper checks; use
> only reconciled, supported runtime operations; retrigger ordinary repair; and
> perform the retroactive L3 test.
>
> Completion is strict: installed/reconciled fixed layer, ordinary repair
> retriggered, authoritative proof the original session recovered and advanced,
> and L3 regression coverage. A launch, PID, exit code, agent prose, or artifact
> path is not success.

The exact target block named session `custody-control-plane-20260714`, plan
`m6-exact-contract-and-20260716-1303`, its worktree, prior contributor runs, and
the suspected historical-failure recount. That specificity let the agent test a
concrete hypothesis without treating it as established fact.

## Recovered prompt 2: repair-dispatch custody

Source: `subagent-20260716-201212-a5bcc8ed/prompt.md` before canonical addenda.

> Act as the single synthesis/delivery owner for an authorized execution
> incident on the Hetzner Megaplan superfixer. Target session:
> `custody-control-plane-20260714`; target plan:
> `m6-exact-contract-and-20260716-1303`; queued repair request begins `30e4d`
> and was observed with zero claims/launches/attempts after a deterministic
> finalize identity-change failure.
>
> Establish exact evidence from all six custody sources, diagnose why the
> watchdog/dispatcher did not claim the request and why L2/L3 missed the break,
> fix the first broken fixer and the backstop above it in an isolated worktree,
> then retrigger ordinary L1 repair. Continue until the original blocker clears
> and the chain advances or a real authority gate is reached. Confirm L3 would
> detect the class retroactively. Do not hand-advance the epic or paper over the
> identity invariant.

Its completion contract required claim/launch/attempt evidence plus an outcome
probe, so self-coalescing could not masquerade as a successful dispatch.

## Recovered prompt 3: bounded convergence and honest gate

Source: `subagent-20260716-211612-5f63a2e2/prompt.md` before canonical addenda.

> Act as the single synthesis/delivery owner for the
> `custody-control-plane-20260714` M6 recovery. This is authorized execution,
> not a status-only review.
>
> Use supported resident/cloud mechanisms to trigger the automated fixer and
> observe it long enough to determine from durable ground truth whether it is
> structurally moving in the right direction. If it is not, diagnose and fix
> the fixer/backstop machinery, retrigger ordinary automated repair, and repeat
> until credible evidence of correct direction or a genuine external
> approval/authority gate.
>
> Distinguish “going in the right direction” from “fully fixed.” Include trigger
> receipts, what the fixer saw and did, before/after canonical state, repetition
> counts, and full git evidence for any mutation.

The outcome stopped honestly at a new immutable runtime-binding authority gate
after proving the original blocker cleared. This is the precedent for treating
a new blocker or missing authority as a separate result rather than weakening a
guard to force closure.

## Evidence versus inference

Raw evidence across the three runs:

- All used one mutation-authorized resident-managed implementation owner with a
  durable manifest, prompt, complete log, result, and git receipt.
- Each required ordinary repair retrigger and authoritative original-session
  movement; the results record those outcomes and distinguish later blockers.
- Each repaired both the first failed fixer layer and an upper detection/custody
  gap. None accepted the meta-fixer's own commit or process as recovery proof.
- Target/source/runtime reconciliation and effect limits were explicit. Later
  runs stopped at distinct gates rather than silently expanding authority.

Inference encoded by this skill:

- A distinct meta-fixer is safer than making the failed fixer repair itself.
  The evidence shows independent custody and proof worked; it does not prove no
  same-process design could ever work.
- The goal-shaped terminal contract likely improved persistence and truthfulness,
  but model capability, extensive context, tools, and incident timing also
  contributed. Do not copy token use or open-ended breadth as causal features.

Unknowns:

- Reproducibility across smaller models and tighter budgets was not measured.
- These runs establish recovery of their original blocker, not completion of
  the full epic or authorization for current deployment.
- Historical literal host paths, branch names, wrapper commands, and service
  operations may be stale; always resolve them through current supported tools.

## Verbatim recovered task bodies

These are the exact task-authored portions of the three prompt files. The
resident launch boundary appended its standard execution/delivery, context,
git-custody, relationship, and Discord delivery contracts after each body.

### `subagent-20260716-170615-ea341358`

```text
You are the sole synthesis/delivery owner for an authorized execution task. Use the `superfixer-debug` skill fully. Fix the automated Superfixer custody chain, retrigger it against the original stuck session, observe whether the automated fixer genuinely repairs the real problem, and iteratively refine the Superfixer until the original session recovers or a real approval/authority gate is reached.

Target incident:
- Session: `custody-control-plane-20260714`
- Plan: `m6-exact-contract-and-20260716-1303`
- Current observed state: blocked after iteration 3.
- Worktree containing the original chain: `/workspace/custody-control-plane-20260714/Arnold`.
- Resident-source work must first discover the actual pinned clean attached runtime target; do not infer literal `main` or mutate the unrelated dirty project checkout.

Prior durable evidence to reconcile, not merely trust:
- Root-block contributor `subagent-20260716-165243-1491d76d` found that a historical gate-format failure was rediscovered after later successful gates and counted three times, falsely tripping the repeated-failure circuit breaker. It also found that the latest `ITERATE` verdict was legitimate because five plan-quality findings remained.
- Synthesis audit `subagent-20260716-165258-b80aad2f` found L1 stayed attached to an obsolete critique failure and never claimed the current blocker. L2 `managed-automatic-meta-repair-f99bd14efdd854d23249` focused on missing PR metadata, had no mutation authority, and failed with exit 77. The latest L3 audit predated the failure and did not catch/correct it.
- Automatic research `managed-automatic-research-subagent-2ecff6d901481d059e74` may contain a safe-mutation handoff; inspect it as evidence.

Required method and boundaries:
1. Establish visibility and inspect all six custody sources in the skill's trust order: live process, marker JSON, chain JSON, plan state, logs, and external state. Separate evidence, inference, and missing telemetry.
2. Walk watchdog -> L1 repair -> L2 meta-repair -> L3 auditor using TRACKED/FIXED/INTENT/CONTEXT. Identify the first broken layer and the layer above that failed to catch it. Hunt sibling instances of the same failure shape.
3. Inspect both the project checkout and pinned resident runtime. For git-backed changes, create an isolated worktree/feature branch from the verified target revision. Preserve concurrent dirty work.
4. Implement the narrow root fix with regression tests, including at minimum: a later same-phase success supersedes an older failure; repeated polling cannot recount one historical failure as new. Also close the L2/L3 evidence/prompt/detection gap necessary for this class to self-correct. Do not weaken guards or directly hand-advance/edit chain state.
5. Run proportional focused tests plus the skill's required wrapper checks where applicable (`bash -n`, `tests/cloud/test_watchdog_wrappers.py`). Review the diff. Commit and locally integrate only if the target branch is unambiguous and authorized by policy. Record base, target, commit SHA, clean isolated worktree, and ancestry proof. Do not push, merge a remote PR, deploy to production, or restart unrelated services without explicit authority. On-box supported Superfixer wrapper refresh/retrigger/restart actions that are inherent to proving this requested repair are authorized only after installed-runtime/target revision reconciliation and must return durable receipts; never use broad kill commands.
6. Retrigger the ordinary automated fixer on the still-stuck original custody session. Verify from ground truth that the fixed Superfixer—not a manual workaround—claims and repairs the actual blocker. Observe long enough to distinguish genuine progress from false success. If it fails, use the new evidence to refine the Superfixer and repeat within safe authority.
7. Perform the retroactive L3 test: prove the auditor would detect this failure class and carry enough root-cause context to initiate the correct repair. Fix that layer if not.

Completion is strict: do not report success merely from a launch, PID, exit code, agent prose, or artifact. Success requires the fixed layer installed/reconciled, ordinary repair retriggered, the original session demonstrably recovered/advancing from authoritative state, and L3 regression coverage. If an external push/deploy/restart or target ambiguity becomes a real approval gate, stop with exact evidence and the smallest explicit approval request.

Deliver one concise user-facing completion to the originating Discord request. Include durable run IDs/receipts, causal finding, exact changes, tests, commit/base/target/ancestry evidence, installed-runtime reconciliation, retrigger receipt, and original-session outcome. Keep working autonomously through ordinary failures; do not stop at advice or a patch description.
```

### `subagent-20260716-201212-a5bcc8ed`

```text
Act as the single synthesis/delivery owner for an authorized execution incident on the Hetzner Megaplan superfixer. Target session: custody-control-plane-20260714; target plan: m6-exact-contract-and-20260716-1303; queued repair request begins 30e4d and was observed with zero claims/launches/attempts after a deterministic finalize identity-change failure.

Use the superfixer-debug and megaplan-cloud operating procedures. First establish exact evidence from all six custody sources (live process, session marker, chain JSON, plan state, log tail, and relevant external/git state), including timestamps and the exact accepted/coalesced repair-request records. Separate evidence, inference, and missing telemetry. Determine why the watchdog/dispatcher did not claim and launch this request, and why L2/L3 did not catch that custody break. Diagnose the observation path before diagnosing the system.

Then fix the first broken fixer layer and the backstop above it. For git-backed source changes, inspect both /workspace/arnold and the pinned resident/runtime checkout; discover and record the actual target branch/revision, use an isolated worktree and feature branch, preserve dirty/concurrent work, run focused tests, review the diff, commit, revalidate the target ref, and locally integrate only when the target is unambiguous. Do not infer literal main. Do not push or merge a remote PR unless existing repository policy explicitly authorizes that exact effect. If a supported installed-runtime refresh or supervisor restart is required to make the expressly requested repair trigger work, reconcile the installed revision, use only the supported scoped operation, and retain its receipt and health evidence; never use broad kill operations.

After fixing dispatch, re-trigger ordinary L1 repair for the original still-stuck M6 session. Observe whether it claims the exact request, launches, sees the real finalize/identity-change error, and makes genuine progress without weakening guards. If it fails or repairs the wrong thing, continue diagnosing and fixing the repairer/meta-repair custody path, re-triggering after each verified correction, until the original chain's blocker is genuinely cleared and the chain advances, or until a real approval gate/material ambiguity is reached. Do not hand-advance the epic or paper over the identity invariant. Confirm that L3 would detect this class retroactively; fix its detection/context if it would remain blind.

Completion requires durable evidence: root-cause layer and axis; why the upper backstop missed it; tests/checks; reviewed diff; commit SHA, base and target revisions; clean isolated worktree; ancestry proof for any local integration; installed-runtime revision and scoped restart/refresh receipt if changed; repair request claim/launch/attempt evidence; and an outcome probe showing the original M6 session recovered and advanced. A PID, command acknowledgement, agent prose, or artifact path alone is not proof. If the chain is still running productively after blocker clearance, report the exact advancing evidence rather than waiting for full epic completion. Deliver one concise evidence-backed reply to the originating Discord request.
```

### `subagent-20260716-211612-5f63a2e2`

```text
Act as the single synthesis/delivery owner for the custody-control-plane-20260714 M6 recovery. This is authorized execution, not a status-only review.

Objective: use the supported resident/cloud mechanisms to trigger the automated fixer for the original blocked session and observe it long enough to determine, from durable ground truth, whether it is structurally moving in the right direction. If it is not, diagnose and fix the fixer/backstop machinery, re-trigger ordinary automated repair, and repeat until there is credible durable evidence of correct direction or a genuine external approval/authority gate.

Target facts at launch: session custody-control-plane-20260714; plan m6-exact-contract-and-20260716-1303; canonical state is blocked at iteration 5 with critique_finding_identity_reused. Prior fixer code changes were reported integrated at e5b7a2b29b, but the authoritative verdict was recovery_not_verified. Treat that as context, not proof.

Follow the superfixer-debug discipline. First establish visibility, then inspect all custody layers in order: live process, session marker, chain JSON, plan state.json, relevant log tail/repair artifacts, and external state if applicable. Determine L1 TRACKED/FIXED/INTENT/CONTEXT and identify the first failing layer plus why L2/L3 did not catch it. Use only supported resident/cloud/status and repair trigger seams; do not use ad-hoc process killing, hand-advance the epic, weaken guards, or claim success from an acknowledgement/PID/agent narrative.

Trigger the ordinary automated fixer for this exact still-blocked session. Observe boundedly until evidence shows one of: (a) the correct blocker is being investigated and state is genuinely advancing/clearing; (b) deterministic wrong direction, false success, stale data, repeated identical failure, or no custody/claim. If (a), end and deliver a concise evidence-backed summary; full chain completion is not required if the evidence is strong enough that the fixer is structurally converging. If (b), repair the fixer systematically: find the first custody layer and the backstop above it, hunt sibling instances of the same failure class, implement regression coverage, and re-trigger the ordinary fixer. Do not merely patch the M6 artifact directly.

For any git-backed mutation, discover the pinned resident runtime target and current project state, use a clean isolated worktree/feature branch based on the verified target revision, preserve concurrent dirty work, run proportional focused tests, review the diff, commit, revalidate target lineage, and locally integrate only when target authorization is unambiguous. Do not push, merge a remote PR, deploy to production, or restart services unless an established in-repo policy explicitly grants that exact effect; otherwise stop at the precise approval gate. If an installed-runtime refresh or supported supervisor operation is already authorized by established fixer policy, record its receipt, installed revision reconciliation, health check, and outcome probe. Never use pkill/killall/tmux cleanup.

Completion evidence must include: automated repair trigger receipt/run/request ID; observations showing what data the fixer saw and what action it took; before/after canonical session and plan state; whether the original blocker cleared or materially progressed; any deterministic repetition count; if code changed, tests, reviewed diff, commit SHA, base/target revisions, clean worktree, and target ancestry; and a retroactive verdict on whether L2/L3 would catch recurrence. Clearly distinguish “going in the right direction” from “fully fixed.” Deliver one concise user-facing completion to the originating Discord request and preserve detailed evidence in the durable run result/log.
```
