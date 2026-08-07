---
name: superfixer-debug
description: Evidence-first recovery protocol for a stuck Megaplan epic or any autonomous pipeline. Pipeline: bounded DeepSeek V4 Flash evidence swarm to understand all context → Codex/Sol decision-maker produces an ordered implementation plan (durable root fix + get-it-moving) → DeepSeek implementer executes it in the approved editable runtime, tests and iterates until the preserved occurrence advances → restart and drive the chain through the next milestones. Includes a durable root-cause checklist for the recurring stall classes (stale blocked dispositions, liveness-fenced chain auto-advance, chain spec drift, runtime split-brain, reader-side accounting bugs). Use when a validator, worker, watchdog, fixer, observer, or notification path is stalled, contradictory, or repeating.
---

# superfixer-debug

This skill replaces the former “stack of fixers” playbook. It is a decision and
custody protocol, not a license to hand-advance a run. Its invariant is:

> Evidence first → Sol scoping judgement → bounded DeepSeek V4 Flash evidence → Sol adjudication →
> canonical movement route → authoritative proof.

The fixer keeps custody until the accepted work is moving. A quarantine receipt is
an evidence checkpoint, never a successful terminal outcome. When the preserved
occurrence cannot safely resume, Sol must choose either an authority-approved
migrated child or a canonical control-plane repair that makes the missing identity
or authority durable, then the ordinary fixer must execute that route and prove
cursor/milestone advancement. “No safe retry” is not a durable answer when the
blocking seam is repairable. No route may fabricate history, bypass authority, or
weaken a validator; a genuinely external approval remains an explicit gate with an
active next-owner route.

## No-op and coordination guards (run these first)

Before doing anything else:
- NO-OP: enumerate blocked/failed chains. If none are blocked or failed, report
  "No blocked/failed chains found; nothing to fix" and end. Do not invent work,
  fabricate a failure, or touch healthy/running chains.
- COORDINATION: check whether another fixer/repair is already active for the
  target chain. Use the RELIABLE signals (cloud status may not be available if
  the initiative has no cloud.yaml): (a) a FRESH managed subagent dir for this
  session under .megaplan/plans/resident-subagents/subagent-* (created in the
  last hours), (b) a held repair lease via inspect_repair_lock, or (c) a running
  subagent_worker process for that session. If any signal is active, report
  "Another fixer is already active for this chain; standing down" and end —
  never launch a competing fixer.

## Epic-babysitting operational loop

This skill also covers "epic-babysitting": keeping the target chain actually
moving, not just fixing one layer. Repeat this loop until the canonical milestone
advances (index > 0):

1. OBSERVE authoritative state — `megaplan cloud status --all --compact
   --cloud-yaml <cloud.yaml>`; `<plan>/state.json` (current_state, active_step,
   latest_failure); `.megaplan/plans/.chains/chain-*.json`
   (current_milestone_index, completed[]); `<plan>/events.seq` (advancing =
   cooking; filter out llm_token_heartbeat/state_written noise);
   `execute_batches/*/tasks_*.json` (done/blocked).
2. DIAGNOSE the blocker — common gates: finalize feasibility (plan config
   missing phase_timeout_seconds), the pre-dispatch full-suite backstop running
   synchronously in shadow mode, cgroup OOM (raise memory), executor
   "No module named pytest" (PATH issue — use sys.executable -m pytest), runtime
   binding drift (CAS rebind or relax require_editable_runtime_match), and
   stale-blocked tasks whose validation passes but need re-admission.
3. FIX the fixer or infra — fix upstream engine bugs directly (shadow-mode
   defer, memory ceiling, runtime-match toggle, scheduler/watchdog); let the
   fixer fix everything else, and grant it the authority it needs (rebind) plus
   a durable-restart handoff (not just a gate name).
4. RE-DRIVE — `python3 -P -m arnold_pipelines.megaplan resume --plan <plan>
   --project-dir <p>`; or trigger the superfixer via `resident schedule add`
   (one-shot/hourly, deepseek-v4-flash, render_goal) + `resident schedule run-once`.
5. VERIFY durable movement — the canonical chain state must show the milestone
   advanced with matching identities and exactly one terminal notification. A
   PID, commit, or "successful" summary is NOT proof.
6. SUMMARIZE — after each fixer session, a DeepSeek Flash agent writes a 2-sentence
   summary to `.megaplan/fixer-sessions/summaries/` + `index.md` (git-committed);
   the last 5 are injected into every new fixer /goal as "UNTRUSTED HISTORICAL
   EVIDENCE — verify against current state", and recurring issues are shared
   with Sol subagents.
7. repeat until the milestone advances.

Recurring patterns: every runtime change needs a rebind (or relax
require_editable_runtime_match); each fix reveals the next blocker; the fixer
stops at authority gates (rebind) — grant authority or escalate; blocked tasks
are often stale — they need re-admission. The success condition is canonical
milestone advancement, not a fixer exit, a commit, or a live PID.

### Durable root-cause checklist — the recurring stall classes

Every one of these has frozen a healthy plan for hours. Before accepting a
"blocked" disposition as legitimate, verify it against CURRENT state — a stale
observation is not a gate.

1. **A "blocked" disposition is often STALE, not authoritative.** A task/phase
   recorded `blocked` against old state (a pre-work git HEAD, a dirty tree, a
   baseline captured before work landed) is frozen as terminal and never
   re-verified, cascading into `accepted_attempt_dependency_unresolved` /
   `blocked-by-prereq`. CHECK: is the block's own recorded head_sha / baseline
   the CURRENT head? Is the tree now clean? Is the prerequisite now satisfied?
   If so, reset the blocked task(s) to pending and re-dispatch — the objective
   is usually met. Over-strict executor checks (e.g. requiring HEAD == the
   milestone base instead of verifying ancestry) are the trigger; the stated
   task objective is the contract, not the executor's invented stricter
   condition.
2. **A DONE plan does not auto-advance its chain when the session is
   liveness-fenced.** The chain runner only drives chains it can confirm are
   live (identity-bound liveness). A `liveness_unknown` session is fenced, so a
   completed plan leaves its milestone parked. CHECK: after a plan reaches
   `done`, read `.megaplan/plans/.chains/chain-*.json` and run `megaplan chain
   status`; if the milestone is still `in_progress`/`blocked` and not
   `completed`, reconcile spec drift (below) then `megaplan chain start`. The
   durable fix is for the runner to advance a terminal plan even when liveness
   is unknown.
3. **Chain spec drift silently blocks advancement.** Modifying `chain.yaml` (or
   NORTHSTAR.md) after the chain is bound invalidates the execution binding and
   raises `chain_spec_not_at_intended_revision`. CHECK `megaplan chain status`
   for active_errors / execution-binding drift; reconcile via `megaplan chain
   rebind` to the current spec before advancing.
4. **Runtime split-brain.** The editable-install `.pth` may point at one tree
   while the container `PYTHONPATH` resolves a different tree, so the drive and
   the resident run different code. CHECK the effective import
   (`python3 -P -c "import arnold_pipelines.megaplan as m; print(m.__file__)"`)
   under the exact launcher env, and confirm the fix landed in the tree that
   actually runs.
5. **Reader-side accounting bugs recur.** Three shapes have each blocked a
   healthy plan: a stale reload discarding in-memory merged evidence before a
   count; keeping ONE artifact per batch and dropping the claim union; and
   comparing per-task evidence against a GLOBAL newest head instead of the
   task's own batch head. CHECK counts against the artifacts the workers
   actually wrote, not the reloaded projection.

## The execution charge (non-negotiable)

Sol is not being asked for a diagnosis that the fixer can hand back. Its Horizon A
charge is: **work in the approved editable runtime, make the smallest source-level
repair, run the focused regression, inspect the real result, and keep iterating until
the preserved occurrence advances.** The ordinary fixer owns this loop. It must not
return a blocked receipt merely because the first edit failed, a runtime identity
changed, or one candidate did not pass. After every failed edit/test/rebind/finalize
attempt it must append an evidence delta, give the updated evidence to Sol stage 2,
apply the next bounded correction, and continue until the canonical cursor or
milestone advances.

`agent_actionable: false` is reserved for a genuinely external gate (for example a
missing human approval that the system cannot issue, an unavailable provider, or an
unreadable canonical owner). A repair to the owned editable Arnold runtime is not an
external gate: creating a content-addressed descendant, reinstalling it editable,
running its tests, proving provenance, and rebinding through the supported seam are
part of Horizon A. Do not expose runtime-A/runtime-B candidate bookkeeping as a
reason to stop; the fixer must create and validate the correct descendant itself.

There is no hard time or attempt budget for this charge. Use bounded individual
commands and idempotent effect barriers, but continue the repair loop until success
or a real external gate is proven. A quiet wait for a real external gate is a
durable state; a terminal quarantine for an owned source repair is a fixer failure.

### Fast path and bounded escalation

Apply the smallest fix immediately when the fix is obvious: the root cause is
unambiguous from the evidence, the change is minimal and contained, you can verify
it with a focused test, and no owner/authority/credential gate blocks it. Do not
spend the session re-investigating an already-obvious fix. Apply it, run the focused
verification, and keep pushing until the verification genuinely passes and the
occurrence advances.

Escalate back to Sol stage 2 after **three distinct, verified fix attempts** that
did not make the occurrence advance — never three blind retries. Count only attempts
that materially changed something and were verified to still fail. Escalate sooner on
unchanged evidence, a permission/infrastructure/credential blocker, widening scope,
or destructive risk. Each escalation must carry an evidence delta: what was attempted,
the exact change, the verification output, and the rollback state. Cap Sol
re-adjudication cycles so the fixer cannot recurse to Sol indefinitely; once the cap
is reached, stop at a documented external gate and keep the next owner/schedule active.

An occurrence-bound run that carries the operator's explicit charge to get this
occurrence moving is already the operator's approval to repair the named editable
runtime within the named scope. Do not manufacture a second signed-approval gate
for an ordinary source/runtime correction, or turn a missing historical attempt
record into a reason to stop. Materialize the fresh prospective request, custody
claim, effect barrier, and provenance records through their canonical owners. Keep
the safety boundary in the scope, identity, CAS, and after-proof—not in refusing to
execute an otherwise owned repair. Escalate only when the required owner/provider
is genuinely unavailable or the requested effect would exceed the explicit scope.

It applies to every pipeline. Megaplan/cloud, Run Authority, Work Boundary
Control (WBC), Custody, and the incident ledger are examples of surfaces; never
create a second authority for another pipeline.

## Model routing

The model roles are explicit and stable across local runs, cloud runs, and the
three-hour backstop:

- **Sol / final adjudicator:** `codex:gpt-5.6-sol` with high reasoning. Sol scopes
  the investigation, adjudicates the evidence, makes the meaningful judgement
  calls, and separates the immediate recovery from the category-level fix.
- **Flash investigators:**
  `hermes:deepseek:deepseek-v4-flash`. Flash handles the bounded, parallel,
  read-only evidence questions that Sol assigns. It is not allowed to invent
  architecture or self-authorize a repair.
- **Execution:** the bounded recovery owner acts only on Sol's Horizon A
  cutline. Escalate that owner back to Sol whenever the decision is high-stakes,
  ambiguous, or crosses an authority/runtime boundary.

Do not silently substitute `gpt-5.6-luna`, a GLM/Fireworks alias, or a stale
provider route for the Flash investigator role. Record the actual provider/model
in every evidence index and Sol handoff.

## Non-negotiable posture

- Preserve the failed occurrence. Never fabricate an output, clear state, weaken a
  guard, use `--fresh`, or treat a PID, marker, heartbeat, launch acknowledgement,
  model prose, or deferred validation as recovery.
- Read canonical state before projections. Use the supported `megaplan introspect`
  and `megaplan cloud status --all --compact --cloud-yaml <cloud.yaml>` surfaces
  first. Raw process/log inspection is corroboration, not authority.
- Keep source/runtime/chain identity content-addressed. A runtime refresh or rebind
  is a new immutable lineage unless an accepted migration transaction says otherwise.
- Do not let a fixer launch itself directly from a stale projection. A deterministic
  blocker must become one occurrence-bound repair request owned by Run Authority →
  Custody → WBC; the ordinary fixer claims and attempts that request.
- Notifications are effects, not observations. A stale poll cannot mint a new
  message, and an ambiguous provider delivery is `INDETERMINATE`, not permission to
  resend.
- A "blocked" disposition is evidence, not a verdict. Verify the block's
  preconditions against CURRENT state (head_sha, tree cleanliness, baseline
  ancestry, prerequisite satisfaction) before accepting it as a gate. Stale
  observations and over-strict executor checks have repeatedly frozen healthy
  work; the stated task objective is the contract.

## Phase 0 — build the evidence pack

Create a durable, redacted evidence artifact before asking any model for a fix.
Give it a stable incident/occurrence name and capture UTC times. Include:

1. **Identity:** pipeline, session/epic, workspace, chain/spec, plan, plan revision,
   run revision, occurrence/fingerprint, phase/cursor, validation job, task/batch,
   source commit/tree, runtime content SHA, interpreter/import root, wrapper/config
   and schema hashes.
2. **Canonical state:** `megaplan introspect` output, plan `state.json` and history,
   chain state/events, authoritative Run Authority decision/fence, Custody claim/
   lease/epoch, WBC attempt/effect/result envelopes, and the exact failure payload.
3. **Process custody:** live process/lease only as corroboration; session marker,
   liveness lease/fence, runner identity, and exact chain/plan log tails. Record
   negative evidence with a bounded search (for example “no r5 repair request under
   `/workspace/.megaplan/cloud-sessions/repair-data/`”).
4. **Contract graph:** plan-declared selectors and outputs, validator inputs and
   source identity, task write sets, test budgets, result-envelope schemas,
   repository/content-hash observations, and any deferred/unknown statuses. Never
   collapse `deferred`, `missing`, or `INDETERMINATE` into pass.
5. **Recovery/observer:** repair requests, decisions, claims, attempts, dispatches,
   watchdog/auditor reports, host-side status snapshot errors, credentials boundary,
   notification intent/effect/provider receipts, and incident projections.
6. **Sibling search:** same failure text/fingerprint, same selector/contract error,
   same binding drift, same stale marker, and same notification key across sibling
   sessions. Keep raw evidence separate from inference and unknowns.

### Minimum authoritative data, optional diagnostics

Do not turn the evidence pack into a demand for every possible telemetry field.
The recovery decision has a small hard contract, and the rest is diagnostic:

- **Required for an actionable repair:** target/session/chain/plan revision and
  parent cursor; one deterministic terminal occurrence/failure digest; the
  current source/fence and bound runtime/contract; then the occurrence-bound
  request, Run Authority decision, Custody claim/epoch, WBC attempt/GLEK, and
  accepted result/cursor proof as those records are created.
- **Useful but optional:** exact writer, PID/process birth, model/provider/tool
  invocation, host/container detail, expanded logs, and observer projections.
  Record absent values as `unknown`; do not block an otherwise authority-complete
  recovery on them and never ask a model to invent them.

The checker must read required values from their canonical owners. A stopped lease,
pathname, hash, marker, heartbeat, or model narrative may corroborate a diagnosis
but cannot mint identity or authority. If the canonical owner cannot produce the
required identity, emit one schema-valid `blocked`/`quarantined` checkpoint,
preserve the occurrence, and immediately follow Sol's durable control-plane repair
or authority-approved migration route. The checkpoint must name the next canonical
owner, the source/runtime or rebind change required, the deployment/authority
proof it needs, and the exact return condition. It records the current gate; it is
not completion and not permission to retry the same phase indefinitely.

If the canonical cloud snapshot cannot be obtained, record that as an observation
failure and stop short of claiming liveness. Provider authentication must use an
explicitly provisioned, locked-down Codex credential path (`CODEX_HOME`), with
its presence and file mode checked by the runner; never copy or log credentials
as an ad-hoc repair, and fail closed when the approved path is absent.

### No-action receipt (mandatory)

An observation that correctly decides “no action” is still an execution result and
must satisfy the managed completion contract. Write
`<occurrence-dir>/no-action-receipt.json` before exiting, not only prose such as
`observation-receipt.md`. The JSON must contain:

```json
{
  "schema": "arnold.superfixer.no_action_receipt.v1",
  "decision": "no_action",
  "target": {"session": "...", "plan": "...", "occurrence": "..."},
  "reason": "authoritative live runner or fresh accepted progress",
  "effects": {
    "launched": false,
    "resumed": false,
    "restarted": false,
    "forked": false,
    "notified": false,
    "mutated": false
  },
  "authoritative_before_fingerprint": "sha256:...",
  "authoritative_after_fingerprint": "sha256:...",
  "models": {"observer": "hermes:deepseek:deepseek-v4-flash"},
  "transport": "resident-managed"
}
```

The before/after fingerprint must cover the launch checkout, canonical chain/plan
state and events, receipts, leases, and repair queues. The receipt is valid only
when every effect is `false` and the managed runner's checkout snapshot is
byte-for-byte unchanged. A stale PID, detached fan, partial report, or Markdown
observation is never a substitute for this receipt and never suppresses recovery.

For an authority gate, the equivalent terminal receipt is
`arnold.superfixer.blocked_receipt.v1`: it names the target and occurrence, states
the missing canonical owner/field, includes before/after fingerprints, and proves
that no launch, resume, fork, mutation, or notification occurred. Repeated polls
with the same blocker return the same receipt identity and no new notification
effect.

The managed runner accepts this receipt only when it is complete. The minimum
shape is:

```json
{
  "schema": "arnold.superfixer.blocked_receipt.v1",
  "decision": "blocked",
  "disposition": "quarantine",
  "target": {
    "session": "<session>",
    "workspace": "<workspace>",
    "plan": "<plan>",
    "occurrence": "<deterministic-occurrence-id>"
  },
  "occurrence": "<same-deterministic-occurrence-id>",
  "missing_gates": ["<canonical-owner-or-field>"],
  "next_owner": "<canonical-control-plane-owner-or-external-approver>",
  "return_condition": "<machine-checkable-condition>",
  "handoff_id": "sha256:<recovery-handoff-content-hash>",
  "follow_up_ticket": "<canonical-ticket-id>",
  "effects": {
    "launched": false, "resumed": false, "restarted": false,
    "forked": false, "notified": false, "mutated": false,
    "repair_request_minted": false, "custody_claim": false,
    "wbc_attempt": false, "provider_effect": false,
    "epic_edited": false, "schedule_cancelled": false
  },
  "authoritative_before_fingerprint": "sha256:<digest>",
  "authoritative_after_fingerprint": "sha256:<same-digest>"
}
```

Never use `null` for the target, fingerprints, `next_owner`, `return_condition`,
or `handoff_id`. Write it in the managed
occurrence directory (or the occurrence-owned incident-evidence directory when
the runner exposes that projection); Markdown alone is not a completion result.
If the canonical identity or fingerprint cannot be computed, leave the receipt
unwritten and report the provider/observation gate rather than inventing values.

## Phase 1 — Sol scopes the DeepSeek Flash swarm

Send the complete evidence pack (not a short narrative) to an explicit GPT-5.6 Sol
high-reasoning read-only session. Use the local Codex transport, with stdin closed:

```bash
codex exec --sandbox read-only --ephemeral \
  -m gpt-5.6-sol -c model_reasoning_effort=high -C "$PWD" \
  -o "$EVIDENCE_DIR/sol-stage1.md" "$(<"$EVIDENCE_DIR/sol-stage1-prompt.md")" </dev/null
```

On the Hetzner resident image, first run the bounded Codex sandbox smoke. The
image deliberately has no unprivileged user namespaces, so `bwrap` may reject
the read-only mode even though the outer container is isolated. In that one
environment only, use the equivalent `--sandbox danger-full-access` invocation
with the same no-mutation Sol prompt and record pre/post target fingerprints;
any fingerprint change is a hard stop before Flash or Horizon A. Never silently
fall back to another model or treat a sandbox/provider error as a successful
Sol decision.

The fingerprint guard covers the launch checkout status/head, chain and plan
state/events, admitted receipts/artifacts, leases, and repair queues. Only the
Sol output and newly-created evidence files may differ. A missing Sol output,
provider error, or any unexpected target change is a durable safety/provider gate.

Sol stage 1 must return:

- definitely broken vs hypothesized facts;
- at most five ranked root hypotheses, each with a falsifier;
- six to ten bounded Flash questions naming artifacts/code and the decision each
  answer informs;
- one evidence contract for comparable reports;
- immediate safety constraints and Sol-only judgement calls.

Do not ask Sol to patch or relaunch at this stage. Persist its result beside the
evidence pack before dispatching explorers.

## Phase 2 — bounded DeepSeek V4 Flash exploration swarm

Run one independent, read-only DeepSeek V4 Flash investigator per Sol question.
Parallelize the questions; keep each report bounded and write one Markdown result
per question. Use the explicit model
`hermes:deepseek:deepseek-v4-flash`, normally
through the approved `subagent-launcher/fan.py`. Flash is a fast non-reasoning
evidence worker, so the brief must name the exact artifacts and decision it
informs; do not ask it for unconstrained architecture. Record the actual model,
provider, and transport in every report. If Flash is unavailable, stop at an
observation/provider gate and escalate to Sol; do not silently fall back to a
different model.

The fan process is occurrence-owned: run it in the foreground, await its terminal
report, and persist owner PID/PGID plus child-custody evidence. Never use
`nohup`, background `&`, detached sessions, or orphan-tolerant polling. On
interruption, terminate the owned process group and record a terminal child
receipt before a later occurrence can suppress recovery. A stale PID, detached
fan, output directory, or partial report without a live managed owner is not
“recovery in flight.”

Every Flash brief must repeat the incident identity, evidence-pack path, remote/local
boundary, and these prohibitions: no mutation, SSH write, launch, resume, rebind,
restart, notification, credential exposure, or agent delegation.

Each report must contain:

- question ID, one-sentence verdict, and `supported|refuted|undetermined`;
- vantage point, UTC observation interval, absolute artifact paths, existence/absence,
  size/mtime/SHA-256, and all available run/occurrence/task/attempt/fence identities;
- exact read-only commands, cwd, exit code, raw excerpts, normalized timeline, and
  bounded negative search scope;
- producer → consumer → persistence → policy code trace and strongest alternative;
- confidence and explicit `adherence vs missing structure` classification against a
  named contract/manifest;
- the immediate and durable decision it informs. No patch or dispatch.

At minimum, cover: selector/task-output declaration; task writes/budgets/attribution;
blocked transition and occurrence-bound repair; runtime/chain binding lineage;
host observer and credential boundary; notification dedup/effect custody; existing
Run Authority/WBC/Custody adherence; causal timeline; and legal state-machine
recovery routes.

Persist an index with each report’s SHA-256, model, prompt, start/end time, and exit
status. Reports are evidence, not authority and not a vote.

## Phase 3 — Sol adjudicates the recovery and architecture

Send Sol the original evidence, Sol stage 1, the swarm index, and every Flash report.
Ask for a second explicit GPT-5.6 Sol high-reasoning read-only pass. On the
Hetzner image, use the same cloud-compatible `--sandbox danger-full-access`
mode and the same pre/post fingerprint guard. It must return THREE separately labelled tiers. Do not let a convenient
“restart” satisfy the immediate tier, and do not let a broad architecture essay
substitute for the structural tier.

The three tiers are:

1. **Tier 1 — UNBLOCK (get it moving today):** the smallest, safe,
   occurrence-preserving action that advances THIS occurrence/milestone now and
   proves it moved. This is what the operator should execute immediately if they
   only want the chain moving. Name the exact command/operation and the proof.

2. **Tier 2 — PROPER STRUCTURAL FIX (prevent recurrence for anyone):** the
   complete, correct, cross-pipeline fix that closes the failure CATEGORY so no
   other chain hits it. Name the exact module/file, the mechanism, and the
   regression. This is the fix the platform should land, distinct from the
   one-off unblock.

3. **Tier 3 — ROOT BEHIND THE ROOT (the deeper structural cause):** the
   meta-level diagnosis. Is the failure because a REQUIRED structure is MISSING
   (no adopt-existing-tree transaction, no capability boundary, no canonical
   runtime root)? Or because an EXISTING structure is NOT BEING ADHERED TO
   (fixers writing out-of-band code, custody validator ignoring semantic facts)?
   Name the structural gap or the adherence failure at the deepest level, and the
   structural remedy that addresses the cause rather than the symptom.

Then Sol must give a **RECOMMENDATION**: should the operator do Tier 1 (unblock)
alone, Tier 2 (proper fix) alone, or BOTH (Tier 1 now + Tier 2/3 landed after)?
Default to BOTH when the unblock and the structural fix are independent, but be
explicit: if the unblock alone would immediately re-trigger the same failure,
say so and require Tier 2/3 before declaring victory.
Sol stage 2 must also emit the machine-readable recovery handoff described below,
including the exact canonical owner, the route for repairing a missing authority
seam, the route for an authority-approved migration, and the proof/return condition
the execution agent must satisfy. A prose quarantine recommendation without that
route is an incomplete Sol decision.

### Tier 1 — UNBLOCK: shortest safe path to durable movement (agent-actionable now)

This is the smallest occurrence-preserving recovery that can make the accepted work
advance and prove it genuinely advanced. It is not merely the shortest command or a
new live PID. It must state:

Sol must write Horizon A as an execution charge to the fixer: use the approved
editable runtime; implement the fix; run the focused test; inspect the actual
failure; revise the source when it fails; and repeat until the canonical cursor or
milestone advances.

EDITABLE-INSTALL (Sol must require this in Horizon A): the fix must LAND in the
executable editable install that the chain engine actually imports — resolve the
import root under the resident/supervisor runtime (`python3 -P -c "import
arnold_pipelines.megaplan as m; print(m.__file__)"`), patch+commit there (mirror
to workspace/worktree only if different), and verify by re-importing and running
the focused regression through the SAME resolved root. A fix present only in the
workspace clone or a worktree is NOT applied.

LAUNCH-AND-KEEP-MOVING (Sol must require this in Horizon A): after the fix is
applied and verified, Sol must direct the fixer to launch/re-drive the actual
chain (`resume --plan` / supported auto/resume seam) and keep it moving
task-by-task until the canonical milestone index advances past idx 0 and events
are durably advancing (fresh plan state, not a stale marker). A commit, PID,
heartbeat, or single finalize/replan is NOT the stopping condition; durable
milestone movement is. Include an explicit `iteration_loop` with the editable source
root, test command, evidence delta path, Sol re-adjudication trigger, and success
proof. Do not describe this as “try once and quarantine.” Runtime rebind, provenance,
and repair-request bookkeeping are part of this route, not reasons to hand the work
back.

- the disposition: same-occurrence resume, authority-approved migrated child, or
  `repair_control_plane_then_migrate`; quarantine is only a checkpoint inside one
  of those routes, never the final movement plan. A fresh independent child is not
  a substitute for an authority-approved migration, and `INDETERMINATE` is only
  for a genuine provider/observation outage;
- authoritative preflight and all required identity/authority/runtime checks;
- the one canonical request → Run Authority decision → Custody claim/epoch → WBC
  attempt/effect → verification path the fixer may execute;
- the exact supported lifecycle operation, bounded retries, rollback/quarantine rule,
  and explicit stop gates; and
- the after-proof: real validator success, accepted task/result envelopes, matching
  fences/epochs and content-addressed runtime, cursor/milestone advancement, and
  notification-effect custody.

The implementation agent may act only on this horizon. It must not hand-edit
`state.json`/chain state, invent missing outputs, weaken a guard, or implement the
category architecture as part of the immediate recovery.

If the canonical repair producer returns `zero_authority_rejected`, an empty
attempt tuple, or another missing-owner gate, Horizon A must name the canonical
Arnold owner and the smallest source-level change that makes the occurrence
identity durable (for example an occurrence-bound attempt/CAS record or an
editable engine-runtime repair followed by an authority-approved runtime rebind).
It must include the focused regression, the content-addressed cloud deployment/
rebind proof, and the subsequent ordinary-fixer invocation that proves movement.
The agent must execute that route before it may finish. It must iterate source edit
→ focused test → provenance/rebind → one recovery effect → finalize → after-proof,
returning to Sol with a fresh evidence delta whenever a step fails. It may leave a
checkpoint only when an explicitly named external approval or provider outage is the
remaining gate, and then it must keep the schedule/next owner active. Sol must not
answer with quarantine alone or label an owned editable repair
`agent_actionable: false`.

### Tier 2 — PROPER STRUCTURAL FIX: deepest complete solution for the failure category (epic-actionable)

This is the smallest *complete* cross-pipeline solution that closes the category,
not an invitation to overbuild. It must state the first broken contract, any deeper
missing structure, adherence versus unsupported structure, canonical owner, and:

- the one machine-readable contract and content-addressed identity/history to adopt;
- required Run Authority/WBC/Custody, validator, fixer/backstop, observer, and
  notification-intent/effect changes;
- concrete modules/schemas, migrations, tests, observability, rollout/rollback,
  very-hard decisions, and work that can run in parallel;
- the crosswalk into the existing epic (or a justified new follow-up epic), with
  milestones, dependencies, and explicit unfinished work; and
- category-closure proof, including a retroactive replay that yields exactly one
  repair occurrence, one claim/attempt, and at most one notification effect.

Horizon B is planning input for the epic. It is not authorization to launch or to
mutate the current occurrence. Sol must explicitly override Flash conclusions where
needed and mark unresolved conflicts `INDETERMINATE` rather than choosing the
convenient path.

### Shared adjudication and proof

Both horizons must include the adjudicated root cause, explicit Flash overrides,
confidence, and evidence paths supporting each material decision. The final handoff
must make the boundary between “move this occurrence now” and “close this category
forever” machine-checkable; a PID, marker, heartbeat, launch acknowledgement, model
prose, or deferred result is never sufficient proof.

The detailed fields Sol must fill are:

1. **Adjudicated root cause:** first broken contract, deeper issue, adherence vs
   missing structure, canonical owner, and explicit overrides of Flash conclusions.
2. **Immediate recovery decision:** an occurrence-preserving runbook; authoritative
   preflight; required identities; classification of missing selectors/outputs;
   same-occurrence resume vs quarantine/migration; canonical request → decision →
   Custody claim/epoch → WBC attempt/effect → verification path; supported launch
   operation only after gates. No guessed literal command when syntax is unproven.
3. **Durable architecture:** one machine-readable contract and one content-addressed
   identity/history across pipelines; existing Run Authority/WBC/Custody owners;
   host-side observer; notification intent/effect custody; fail-closed validators
   and backstops. Legacy queues/markers/projections become adapters, never owners.
4. **Implementation cutline:** concrete modules/schemas/tests required before the
   relaunch, follow-up work, high-stakes/very-hard items, parallel work, and a
   retroactive test for exactly one repair and no duplicate notification.
5. **Proof gates:** authoritative before/after state, real validator success,
   accepted task envelopes, runtime lineage, repair custody, cursor advancement,
   and notification effects. A PID or deferred result is never enough.

### Sol stage-2 handoff is an execution contract, not a report

Sol stage 2 is the point where evidence becomes an owned recovery decision. Its
output must be persisted twice: as the human-readable handoff Markdown and as a
validated, content-addressed `arnold.superfixer.recovery_handoff.v1` envelope. The
envelope is what the fixer consumes; the Markdown is its inspectable rendering.
The envelope must include:

```json
{
  "schema": "arnold.superfixer.recovery_handoff.v1",
  "handoff_id": "sha256:<content-hash>",
  "target": {"session": "...", "plan": "...", "occurrence": "..."},
  "evidence": {"pack": "...", "sol_stage1": "...", "swarm_index": "...", "sol_stage2": "..."},
  "horizon_a": {
    "route": "repair_control_plane_then_migrate",
    "agent_actionable": true,
    "canonical_owner": "...",
    "preconditions": ["..."],
    "operations": ["..."],
    "focused_tests": ["..."],
    "iteration_loop": {
      "editable_runtime_root": "...",
      "edit_test_observe_until": "canonical cursor/milestone advancement",
      "on_failed_iteration": "append evidence delta and return to Sol stage 2",
      "hard_budget": null
    },
    "deployment_or_rebind_proof": ["..."],
    "external_gate": null,
    "return_condition": "authoritative cursor/milestone advancement"
  },
  "horizon_b": {
    "epic_update_required": true,
    "epic_slug": "...",
    "ticket_or_crosswalk": "...",
    "first_broken_contract": "...",
    "category_closure_proof": ["..."]
  },
  "stop_gates": ["..."],
  "notification_key": "..."
}
```

The materializer rejects a handoff that has no executable Horizon A route, no
canonical owner, no return condition, or no explicit external gate. It writes the
handoff and creates/updates the one canonical follow-up ticket before any recovery
effect. The fixer then consumes the exact `handoff_id`; it must not paraphrase
Sol's route or substitute a generic restart.

The execution loop is deliberately closed:

1. validate the envelope and authoritative preconditions;
2. execute the canonical request → Run Authority → Custody → WBC path;
3. if authority is missing, repair the canonical owner/control-plane seam named by
   Horizon A in the approved editable runtime, run its focused regression, deploy/
   rebind the content-addressed candidate, and re-run the same idempotent producer.
   If the regression or producer still fails, append an evidence delta, return to
   Sol stage 2, and keep the editable repair loop running; do not terminalize the
   occurrence;
4. if same-occurrence movement remains unsafe, perform the explicitly authorized
   migration transaction and run the ordinary fixer on the linked child;
5. verify accepted outputs and cursor/milestone advancement from canonical state;
6. if the proof fails, create a new evidence delta and return to Sol stage 2 with
   the same occurrence identity (or the resolver's new recurrence identity), never
   spin on the same command or emit a new notification for an unchanged blocker.

Only a genuine external approval/provider outage may leave step 3 or 4 at a
checkpoint. In that case the receipt records the owner, approval request, and
scheduled next attempt; it is an active recovery route, not a completed run.

## Required final handoff document and epic update

The final Sol stage-2 result must produce a durable immediate-fix handoff
document before any mutation. If the requester calls this a “`.me` document”,
use the repository's canonical Markdown/Megaplan form: a committed `.md` artifact
under `.megaplan/initiatives/<epic-slug>/` (or the incident evidence directory
when the epic is not yet known), never an ad-hoc extension that the launcher
cannot discover. Name the artifact so its two horizons are obvious, for example
`immediate-fix-and-category-hardening.md`.

That handoff must contain, in one place:

- the exact incident/occurrence identity and evidence-pack/Sol/Flash report paths;
- a clearly delimited **Horizon A** block marked `agent_actionable: true` containing
  only the smallest occurrence-preserving action that gets the work moving, its
  authoritative preconditions, supported lifecycle operation, rollback/quarantine
  rule, and proof of genuine advancement;
- a clearly delimited **Horizon B** block marked `epic_update_required: true` and
  `agent_actionable: false` containing the first broken contract, missed backstop,
  canonical owner, and the complete category-level solution;
- the proposed machine-readable contract/schema, tests, migrations, observability,
  notification controls, sequencing, and closure proof for Horizon B; and
- a checklist of deferred work, dependencies, very-hard decisions, parallelizable
  work, acceptance evidence, and the exact condition under which the document may
  claim the category is closed.

Give this handoff to the relevant Megaplan epic as canonical input. If an epic
already covers the area, update that epic's existing `README.md`, `NORTHSTAR.md`,
`UNFINISHED_WORK.md`, and milestone brief(s) through a crosswalk; do not create a
duplicate authority or silently discard unfinished work. If no suitable epic
exists, create a normal `.megaplan/initiatives/<epic-slug>/` epic scaffold with a
first immediate-recovery milestone and subsequent category-hardening milestones.
The epic must be explicitly asked to revise the immediate-fix milestone into a
whole-category solution, with the durable contract and regression proof as its
definition of done—not merely to make the current occurrence advance.

Record the handoff path, SHA-256, epic slug, milestone(s) updated/created, and
whether the epic was launched or intentionally left gated. Updating the epic is
planning state; it does not authorize a cloud launch. The same evidence-first
gates, authority boundary, and no-same-occurrence-resume rule still apply.

This planning handoff is mandatory even when Horizon A is checkpointed. Use the
canonical `megaplan-tickets`/initiative crosswalk to create or update exactly one
follow-up ticket for the unresolved control-plane/category work, and record its
ID, path, and content hash in the handoff and occurrence receipt. This planning
effect is separate from recovery authority: it never mints a repair request,
changes chain state, or authorizes a launch. A blocked run without this durable
next-owner record is incomplete.

If Sol cannot distinguish competing hypotheses, the result is `INDETERMINATE` and
the run stays quarantined. Do not choose the most convenient narrative.

## Phase 4 — implement only the canonical immediate repair

Use Sol’s cutline to choose the smallest authorized change. Prefer repairing the
first broken contract and its missed backstop, not editing the epic’s artifacts.
Load and validate the content-addressed `recovery_handoff.v1` emitted by Sol stage
2. The execution owner must record the exact `handoff_id` in every repair request,
receipt, deployment, and proof; it may not reinterpret the route from a summary
paragraph or replace it with a generic restart.

The execution owner is responsible for the whole editable repair loop. A failed
candidate, failed focused test, failed provenance check, or failed finalize attempt
is a new iteration of the same occurrence, not a reason to return a report. Re-edit
the approved runtime, reinstall it editable when needed, run the test again, append
the evidence delta, and ask Sol for the next bounded correction. Continue until the
after-proof is real or a genuine external gate is established.

- Reconcile source and installed runtime before any effect; record exact revisions,
  content hashes, interpreter/import roots, and applicability.
- Create or repair the canonical occurrence-bound request through Run Authority →
  Custody → WBC. Use deterministic idempotency/CAS and preserve the failed record.
  The checker may call only the canonical idempotent request producer; it must not
  reconstruct a missing request from labels, a dead runner, or optional telemetry.
  If the producer returns a typed authority gate, execute Sol's control-plane route:
  repair the request/attempt/CAS or runtime-rebind seam at its canonical Arnold
  source owner, run the focused regression, deploy the content-addressed candidate
  through the supported cloud path, and rerun the producer once. Never weaken the
  required contract merely to make a launch possible. If the repaired seam still
  cannot produce authority, write the checkpoint naming the external approval or
  provider gate and keep the next owner/schedule active; do not silently declare
  recovery.
- If plan/runtime/validator identity crossed an unaccepted boundary, quarantine the
  old occurrence and create an authority-approved migrated child run revision. Do
  not resume in place or fabricate missing task outputs.
- Fix selector/task-output declarations at their shared machine-readable source;
  make finalizer, executor, validator, auditor, and result admission consume the
  same hash. A prospective output is not an accepted output.
- Keep earlier worker claims quarantined until independently re-admitted with
  accepted result envelopes, write-set/test-budget evidence, and tree hashes.

No direct `state.json`/chain edit, force-proceed, `--fresh`, broad kill, unrecorded
retry, or manual completion is allowed. If an effect is not authorized, stop that
effect at the exact gate with the evidence artifact retained, but continue the
durable control-plane repair or authority-approved migration route. A blocked
receipt without a named next owner and a return condition is not a completed
fixer run. A repairable source/runtime failure is not an external gate: keep
editing the approved editable checkout, testing, and re-entering Sol until the
canonical movement proof exists.

## Phase 5 — close the loop and prove movement

Only after Sol’s gates pass, use the supported cloud/chain lifecycle API for the
accepted migration/new attempt, then observe from canonical state. A valid after
proof shows the original failure occurrence immutable, a linked repair/migration
receipt, matching Run Authority fence/Custody epoch/WBC attempt, a real validator
success, accepted task result envelopes, and a CAS-protected cursor/milestone advance.

Run the retroactive backstop test: replay the same blocker through repeated polls and
concurrent repair triggers; assert one occurrence, one request, one claim, one WBC
attempt, one notification intent, and at most one provider effect. A new accepted
state version may create a new occurrence only under the resolver’s recurrence
policy. Verify stale projections cannot emit effects.

After each mutation, keep a durable receipt containing target/session/occurrence,
authority decision, claim/epoch, WBC attempt, source/runtime hashes, tests, before/
after fingerprints, and ordinary-fixer retrigger evidence. Distinguish original
blocker recovery from any later blocker.

## Completion contract

The skill is complete only when:

- the evidence pack, Sol stage-1 result, every Flash report/index, and Sol stage-2
  decision are durable and hashable;
- the first broken contract and missed backstop are identified with raw evidence;
- the canonical repair/migration path is installed and its focused regressions pass;
- the ordinary fixer, not a manual workaround, handles the preserved occurrence;
- authoritative before/after state proves genuine advancement; and
- any schema-valid blocked/quarantined receipt is paired with a durable
  control-plane repair or authority-approved migration route, names its next owner
  and return condition, and remains notification-silent while the authoritative
  blocker is unchanged. The receipt alone is not completion;
- the final handoff has produced or updated exactly one canonical follow-up ticket
  for any deferred category work, without treating that planning effect as
  recovery authority;
- the retroactive failure/notification test passes;
- the final handoff has distinct, hashable Horizon A and Horizon B blocks, marks
  only Horizon A as agent-actionable, links Horizon B to the correct Megaplan epic,
  records whether the epic is launch-ready or gated, and either the ordinary fixer
  has advanced the accepted cursor/milestone or an explicitly named external gate
  has an active next-owner route.

If the run remains quarantined because an identity, authority, provider, or external
artifact is missing, report that precise gate, keep the route active, and do not
claim the epic is moving until authoritative cursor/milestone evidence changes.
