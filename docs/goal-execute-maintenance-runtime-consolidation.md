# GOAL: Execute the maintenance runtime consolidation

Execute the complete plan in
`docs/arnold/maintenance-runtime-consolidation-execution-plan-2026-08-20.md`
from G0 through G7. Work one bounded card at a time, use the required external
subagents for implementation and review, integrate only reviewed commits, and
finish with verified editable candidates plus a disposable canary and rollback
proof. Do not create another Megaplan plan or epic for this work.

## Outcome

Produce one coherent successor to `fce48030a82d4d35d9b4a5184e4c789792b9c172`
that selectively incorporates every useful behavior from the completed
`megaplan-maintenance` milestones without importing generated evidence,
failed-publication state, superseded identity code, or over-broad automation.

The successor must:

- retain the newer `fce` runtime identity, manifest, marker, parser, custody,
  editable-install, and promotion contracts;
- make observation broad and deterministic but action authority narrow,
  typed, evidence-bound, fenced, and idempotent;
- keep M5 efficiency work report-only;
- implement real elapsed test deadlines with explicit legacy compatibility;
- install both editable candidates from the same verified successor SHA while
  keeping their project-state roots separate;
- leave the active Astrid and maintenance epic state unchanged; and
- stop before live promotion. Promotion is a separate operator decision.

## Authoritative inputs

- Remote integration target: `origin/fixer/runtime-convergence-r`. Create a fresh local branch/worktree from that ref and always push explicitly as `git push origin HEAD:fixer/runtime-convergence-r`; never infer the push target from a local branch name.
- Execution plan:
  `docs/arnold/maintenance-runtime-consolidation-execution-plan-2026-08-20.md`.
- Integration base before the main merge:
  `fce48030a82d4d35d9b4a5184e4c789792b9c172`.
- The branch has already been merged with `origin/main`; do not recreate or
  discard that merge.
- Cloud project: `/workspace/megaplan-maintenance/Arnold` on
  `root@159.69.51.216`, container `megaplan-cloud-agent-resident-only`.
- Editable candidates:
  `/workspace/runtime-candidates/astrid-first` and
  `/workspace/runtime-candidates/arnold-4a830c6ac9a0`.
- Milestone tips to preserve at G0:
  - M1 `67e7b94a4da248b5e92ad56eb4bfa5ba261d9145`
  - M2 `15b881cb47274447b3795c9438fd2de1d9f9d33d`
  - M3 `58d4a935539597c2aa3f323e1515054ec1f95fe7`
  - M3b `7272cdc7f4303219fb399aefd2966f410d79d208`
  - M4 `759e3186f773ae40e58dc9de1e716dfd2ebb8438`
  - M5 `800fa27648245115d5c1412d16ec583d91bdea02`

The execution plan is the source of truth for task order, prerequisites,
acceptance criteria, test shards, and review gates. If this goal and that plan
appear to disagree, preserve the plan's safety constraint and the model-routing
rule below, record the conflict, and resolve it before mutation.

## Mandatory model routing through `/subagent-launcher`

The orchestrating agent only advances the deterministic task state machine,
launches the routed subagents, watches their receipts, and relays reviewed
results. **All substantive work must be done in subagents.** The orchestrator
must not personally research source history, inspect implementation details,
write briefs, edit code/docs/tests, run tests, classify findings, implement
revisions, review diffs, integrate commits, push branches, update candidates,
run canaries, validate evidence, or make architectural/policy/merge judgments.

Use Luna subagents for brief preparation, workspace preparation, ordinary
implementation, ordinary review, mechanical integration/push, test execution,
evidence collection, and report assembly. Use Grok 4.6 subagents for every
material judgment, `[XHARD]` implementation, `[XHARD-REVIEW]`, and
`[XHARD-REVISION]`. The orchestrator may reject an invalid/missing receipt
mechanically; it may not replace a subagent judgment with its own.

## Judgment-call routing — always Grok 4.6

Any decision that could materially change the result must be dispatched to a
fresh Grok 4.6 judgment subagent through the receipt-producing wrapper with
role `judgment` and label `[XHARD-REVIEW]`. This includes:

- keep/adapt/drop or supersession decisions;
- scope changes, task splitting that changes semantics, or difficulty
  classification when it is not mechanically obvious;
- architecture, authority, custody, identity, migration, concurrency, replay,
  compatibility, public-schema, or live-runtime choices;
- whether to delete a gate, add enforcement, accept a fallback, or tolerate
  unknown evidence;
- whether a reviewer finding is must/should, whether evidence is sufficient,
  or whether a residual risk is acceptable;
- any departure from the execution plan, settled decisions, test contract, or
  model-routing policy; and
- the final merge/promotion recommendation.

The judgment brief must demand one decisive recommendation, evidence paths,
rejected alternatives, affected tasks/contracts, and the exact downstream
routing. A Luna evidence subagent records the Grok judgment; the orchestrator
follows its routed outcome. If concrete
evidence later contradicts it, launch a fresh Grok re-adjudication; do not
silently overrule it.

Any Luna agent encountering a material judgment must stop without mutation and
return `JUDGMENT_REQUIRED` with the evidence and precise question for Grok.

### Grok 4.6 — every XHARD implementation, XHARD review, revision, and judgment

Use Grok 4.6 for:

- every task heading marked `[XHARD]`;
- every gate marked `[XHARD-REVIEW]`;
- every revision marked `[XHARD-REVISION]`;
- every material judgment described above;
- the pre-code contract review and post-code adversarial review around every
  `[XHARD]` card; and
- any ordinary card that discovers a new authority transition and is formally
  reclassified as `[XHARD]`.

After T0.3, dispatch only through the receipt-producing orchestration wrapper.
It internally invokes the repository's absolute
`subagent-launcher/launch_omp_agent.py --model=grok-4.6` path and records the
child process/model evidence:

```bash
python "$INTEGRATION_WORKTREE/scripts/run_maintenance_consolidation_agent.py" \
  --task-id="$TASK_ID" --role="$AGENT_ROLE" --label="$TASK_LABEL" \
  --model-route=grok-4.6 \
  --query-file="$BRIEF_PATH" \
  --project-dir="$TASK_WORKTREE" \
  --allowance-file="$ALLOWANCE_PATH" \
  --evidence-dir="$EVIDENCE_DIR" --timeout=3600
```

Use a fresh Grok process for implementation and each independent review. A
Grok instance must never review its own implementation. Review prompts are
read-only and must forbid edits, commits, pushes, runtime mutation, and live
state mutation.

### GPT-5.6 Luna — everything else

Use GPT-5.6 Luna for:

- G0 object/source inventory before Grok adjudication;
- every ordinary/unlabelled implementation card, recorded as `[HARD]`;
- every ordinary review gate, recorded as `[HARD-REVIEW]`;
- every bounded review repair recorded as `[HARD-REVISION]`;
- brief/worktree preparation and mechanical commit integration/push;
- focused test-shard execution and evidence collection;
- mechanical source mapping, call-site inventory, and contradiction searches;
  and
- final integration shards, except the `[XHARD-REVIEW]` judgment itself.

After T0.3, use the same receipt-producing wrapper. It internally invokes the
repository's absolute `subagent-launcher/launch_hermes_agent.py` path with
`--model=codex:gpt-5.6-luna`:

```bash
python "$INTEGRATION_WORKTREE/scripts/run_maintenance_consolidation_agent.py" \
  --task-id="$TASK_ID" --role="$AGENT_ROLE" --label="$TASK_LABEL" \
  --model-route=gpt-5.6-luna \
  --query-file="$BRIEF_PATH" \
  --project-dir="$TASK_WORKTREE" \
  --allowance-file="$ALLOWANCE_PATH" \
  --evidence-dir="$EVIDENCE_DIR" --timeout=3600
```

The wrapper—not the caller—generates the invocation ID and binds it to launcher
PID/process identity, resolved model, exact command, brief/result digests,
timestamps, and exit status. Direct launcher calls after T0.3 are invalid. The
sole bootstrap exception is the Luna call that implements T0.3 itself; invoke
that through the absolute `launch_hermes_agent.py` path with its native
`--metadata-file`, capture command/stdout/stderr digests, and register it as the
bootstrap receipt before enabling the wrapper.

Do not silently substitute Sol, Terra, DeepSeek, Kimi, or a locally improvised
agent pathway. If Grok or Luna is unavailable, record the exact launcher error
and retry once after checking launcher/model configuration. If it remains
unavailable, stop at that card rather than changing the model policy.

## Review-revision routing

No orchestrator edits code in response to review. Every finding that requires a
change becomes a new evidence-linked revision card and subagent invocation:

- `[HARD-REVISION]` → fresh GPT-5.6 Luna revision implementer. Use only when
  the governing contract is already frozen, the fix is confined to an exact
  existing file allowance, and it changes no authority, custody, identity,
  migration, concurrency/replay, compatibility/public schema, live-runtime
  behavior, task scope, or policy.
- `[XHARD-REVISION]` → fresh Grok 4.6 revision implementer. Mandatory whenever
  the finding touches any excluded HARD dimension, crosses task/module
  boundaries, changes acceptance semantics, or is difficult/ambiguous.

Every reviewer must emit finding IDs and a proposed revision class. Mechanical
HARD cases may route directly to Luna. Any ambiguous classification is itself a
material judgment and goes to a fresh Grok judgment subagent before revision.
When in doubt, route `[XHARD-REVISION]`; never downgrade to save time or cost.

Each revision brief contains only the finding evidence, frozen task contract,
exact allowed files, required counterexample test, and acceptance proof. After
revision, a fresh independent reviewer of the original gate's required model
must re-review the complete task diff. A revision agent cannot review its own
work, and the original implementation receipt remains linked rather than being
overwritten.

The evidence manifest records `finding_id`, `revision_class`, classification
receipt, revision invocation/commit, re-review invocation/verdict, and superseded
artifact digests. A task cannot integrate while any must finding lacks this
closed revision chain.

## Brief contract for every subagent

Every brief is drafted by a Luna brief-preparation subagent from the authoritative
task card and checked mechanically by the wrapper; the orchestrator does not
author it. It must be a small implementation specification, not the entire epic
history. Include only:

1. task/gate ID and exact goal;
2. task worktree and base SHA;
3. exact source commits/hunks from the G0 selection manifest;
4. allowed production and test files;
5. prerequisites already integrated;
6. forbidden behavior and non-goals;
7. acceptance criteria copied from the execution plan;
8. focused test commands and disposable test root;
9. whether mutation is authorized;
10. required output: commit SHA when implementing, files changed, commands,
    results, evidence paths, rejected alternatives, and residual risks.

If a subagent needs files outside its allowance or discovers a new policy or
authority transition, it must stop and return evidence. The orchestrator then
routes that evidence to Grok for any material split/reclassification judgment;
the subagent must not improvise architecture.

## Worktree and integration discipline

Every action in this section is performed by a routed subagent. Luna
workspace-preparation agents perform steps 1–4; implementation/review agents
perform steps 5–6; a fresh Luna integration agent performs steps 7–9 after it
receives the passing review receipt. The orchestrator only dispatches them.

1. Fetch `origin/main` and `origin/fixer/runtime-convergence-r`.
2. Start from a fresh clean worktree at the current remote integration branch.
   Do not stash, reset, checkout over, or commit unrelated edits in an existing
   dirty worktree.
3. Create one task branch/worktree per implementation card from the latest
   reviewed integration SHA.
4. Parallelize only cards the plan explicitly permits and only after their
   complete production-and-test file allowances are frozen and disjoint. Any
   shared export, fixture, helper, generated surface, or test file forces
   serialization. Register each allowance atomically in the T0.3 evidence
   registry; the receipt-producing launcher wrapper must reject dispatch when
   any active allowance overlaps.
5. The implementer edits and runs only focused tests in its task worktree, then
   commits one coherent task change.
6. The independent reviewer examines that exact commit and its production call
   paths. Findings become new HARD/XHARD revision cards handled by fresh routed
   revision subagents; the task does not merge while a must finding is open.
7. After review passes, a fresh Luna integration subagent integrates the task
   commit into the consolidation branch in dependency order and records the
   resulting integration SHA. It has no authority to resolve semantic conflicts;
   any such conflict returns `JUDGMENT_REQUIRED` for Grok.
8. Never use `git reset --hard`, destructive checkout, blanket stash, force
   push, or wholesale milestone merges.
9. The Luna integration subagent pushes after each passed batch with the explicit refspec
   `HEAD:fixer/runtime-convergence-r` so work is durable.

No two agents may edit the same worktree concurrently. No agent may review its
own commit. Preserve all excluded milestone history under safety refs; exclusion
from the runtime is not deletion.

## First action: baseline and close the moving-source boundary

The final reconcile sprint produced useful audit data but no code:
`selected_shas: []`, `task_updates: []`, and no repository mutation. It entered
repeated review attempts and is not the authority for selecting useful milestone
behavior.

Before any fetch, test, process action, or candidate write, complete T0.0 and
capture immutable content-addressed baselines for live process identity,
selectors/markers/manifests, leases/fences, Astrid and maintenance plan/chain
state, schedules, ledger, candidate provenance, and source refs.

Then capture the reconcile audit artifacts:

- capture its current `introspect`, `execution.json`, candidate artifact,
  `review.json`, `review_evidence.json`, repository SHA, and process identity;
- preserve the reconcile process and artifacts unchanged; do not stop,
  terminalize, abort, restart, or record a new plan/chain disposition from this
  consolidation goal;
- record only the observed disposition in this goal's evidence manifest; and
- do not force it green, advance either epic, or use its empty selection to
  discard milestone work.

G0 uses exact immutable source SHAs and read-only object transfer, so it can
independently establish source custody and the keep/adapt/drop manifest without
controlling the live reconcile process. If source identity changes during G0,
retain both observations, classify the later state separately, and do not
silently move the frozen input boundary.

## Required execution sequence

Follow the document exactly:

1. **G0 / Batch 0:** complete T0.0 first; preserve all six cloud tips, resolve exact patch objects,
   classify every patch-unique production commit, and bind every selected hunk
   to a task. Luna also implements T0.3's JSON evidence schema and deterministic
   validator. Luna inventories; Grok performs `[XHARD-REVIEW]`; a Luna evidence
   subagent records the Grok disposition.
2. **Batch 1 / G1:** deterministic observation, pure operational reporting,
   efficiency read model and inert proposals. Luna implements and an independent
   Luna reviews.
3. **Batch 2 / G2:** scheduler claims, typed dispatch receipts, evidence-bound
   repair classification. Luna implements/reviews with focused shards.
4. **Batch 3 / G3:** explicit queue migration, bounded unblocker, read-only
   six-hour audit. Luna implements/reviews.
5. **G3.5 `[XHARD-REVIEW]`:** Grok reads the complete diff since `fce` and
   attacks architectural duplication, premature authority, over-enforcement,
   and missing deletions. Resolve every must finding before T4.
6. **Batch 4:** Grok implements T4.1–T4.3 serially. For each card: fresh Grok
   pre-code contract review, fresh Grok implementation, focused failure
   injection, fresh Grok post-code adversarial review, and a recorded Grok
   judgment receipt when any finding/disposition remains non-mechanical.
7. **Batch 5:** Grok performs the same sequence for elapsed test deadlines and
   legacy compatibility.
8. **Batch 6:** Grok handles T6.1 and T6.2 plus their hard reviews. Luna handles
   the ordinary scheduler handoff and negative-authority suite. Grok performs
   G6.4 whole-system aggression/simplification review.
9. **Batch 7, strictly serial:** Luna runs T7.1 completeness audit and freezes
   the validated nine-shard manifest with exact pytest selectors, commands,
   command digests, order, and behavior/test coverage. Luna then runs T7.2's
   nine canonical commands once in order. Luna performs T7.3 candidate
   installation/provenance proof. A fresh Grok passes G7.4-pre before a
   different Grok implements T7.4's `[XHARD]` disposable canary/rollback; a
   third fresh Grok must pass G7.4-post. Only then does one dedicated Luna own
   T7.5's singleton broad-suite invocation and close the evidence manifest. A
   fourth fresh Grok performs G7 and produces the promotion recommendation only
   after the validator passes. A Luna report-assembly subagent formats the final
   handoff; the orchestrator only relays it and does not promote live runtimes.

## Review and testing rules

- Implementers run only the focused tests listed on their card.
- Ordinary Luna reviewers run only the batch integration shard.
- Hard Grok reviewers inspect production paths and failure boundaries, not just
  test counts.
- A dedicated Luna validator runs the final shards once each.
- T7.2 runs only commands from the validated
  `docs/arnold/maintenance-runtime-consolidation-evidence/test-shards.json`;
  semantic shard names are not executable evidence. The validator enforces
  exact shard ID, selector set, command digest, order, uniqueness, and coverage
  of every selected behavior and changed/new test file.
- The broad suite has one authoritative owner, key `broad_suite_once_v1`, atomic
  lock/receipt, and canonical command `python -m pytest -q`. It runs only at
  T7.5 after focused shards, candidate proof, and canary/rollback pass. The
  evidence validator rejects duplicate authoritative invocations.
- Every state-writing test uses an explicit disposable root and proves that root
  is not a project, candidate, or live runtime root.
- Record for every test shard: command, source SHA, interpreter, runtime/spec/venv
  digests, disposable root, result, and artifact digest.
- Tests must prove the active Astrid and maintenance chain fixtures remain
  byte-for-byte unchanged.

Reviewers must actively look for:

- hidden writes and optional unsafe fallbacks;
- two modules independently granting the same authority;
- diagnostic or liveness evidence becoming action authority;
- unknown/partial/stale evidence becoming green through composition;
- automatic ticket, repair, scheduling-policy, provider/model, rebind, delivery,
  or cutover behavior outside the settled boundary;
- crash/retry paths that duplicate or lose effects;
- older milestone identity code overwriting `fce`; and
- opportunities to delete redundant gates rather than adding enforcement.

## Progress record and compaction seam

Maintain
`docs/arnold/maintenance-runtime-consolidation-execution-log-2026-08-20.md`.
After every card and gate, append:

- task/gate ID and disposition;
- input and output SHA;
- subagent model, launcher command, unique wrapper-generated invocation ID,
  launcher PID, timestamps/exit status, brief digest, and result digest;
- commit and files changed;
- focused tests/evidence;
- reviewer findings and their disposition;
- next unblocked card.

Commit the log at each completed batch. This file is the durable handoff and
compaction seam; do not keep the whole investigation only in chat context.

The machine-readable authority for completion is
`docs/arnold/maintenance-runtime-consolidation-evidence/manifest.json`, not the
Markdown log. Validate it with:

```bash
python scripts/validate_maintenance_runtime_consolidation_evidence.py \
  docs/arnold/maintenance-runtime-consolidation-evidence/manifest.json
```

The schema/validator created by T0.3 must enforce task/gate/shard uniqueness,
task/review/revision/judgment model routing, reviewer independence, complete
finding→revision→re-review chains, Grok receipts for material judgments,
selected-behavior mapping, artifact existence/digests, candidate/canary
receipts, and the broad-suite singleton.

## Stop and escalation conditions

Stop the affected card, preserve evidence, and do not merge when:

- G0 cannot retrieve or classify a milestone production commit;
- Grok or Luna remains unavailable after one configuration check and retry;
- an `[XHARD]` pre-code contract review does not pass;
- a reviewer has an unresolved must-level finding;
- a task needs a new authority transition absent from the settled decisions;
- tests would require writing a live/project runtime root;
- source identity, manifest, marker, candidate, or venv provenance is
  contradictory; or
- live Astrid or maintenance state changes during supposedly isolated work.

Do not stop for ordinary implementation difficulty. Re-brief, split, or return
the card to the correct model. If the same must finding survives three verified
repair attempts, dispatch a fresh Grok adjudication with the full evidence
instead of forcing a pass or writing an orchestrator judgment.

## Done when

The goal is complete only when:

- G0 through G7 have explicit passing dispositions;
- every G0-selected behavior maps to integrated code and passing evidence;
- every excluded production change has a durable reason;
- every substantive work artifact has a valid routed subagent receipt; no
  implementation, review, revision, integration, test, judgment, canary, or
  report artifact is attributed to the orchestrator;
- every reviewer finding has a closed HARD/XHARD revision and independent
  re-review chain, or a Grok judgment receipt accepting the residual risk;
- all focused, batch, integration, provenance, canary, rollback, and final broad
  tests pass;
- the canonical evidence validator exits zero on the final manifest and every
  task/gate/shard record is unique and referentially complete;
- both editable candidates prove the same approved source/package/spec/manifest/
  venv identity while retaining separate project state;
- active Astrid and maintenance state remains unchanged;
- the final Grok G7 review has no unresolved must finding;
- the integration branch and execution log are pushed; and
- a Luna report-assembly subagent reports the exact successor SHA, evidence
  manifest, residual should-level risks, and Grok's separate promotion
  recommendation; the orchestrator only relays that reviewed handoff.

Do not claim completion because every agent returned, every card has a commit,
or the broad suite is green. Completion means the coherent evidence-bound
end-state in the execution plan is actually present and independently reviewed.
