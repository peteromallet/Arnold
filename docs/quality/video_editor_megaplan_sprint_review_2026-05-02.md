# Video Editor Megaplan Sprint Review

Date: 2026-05-02

Scope:
- Sprint 1 plan: `video-editor-developer-20260502-1729`
- Sprint 2 plan: `video-editor-developer-20260502-1920`
- Cloud chain: `.megaplan/video-editor-dx-chain.yaml`

This is a shared review document for issues to investigate or fix before treating the cloud Megaplan output as merge-ready. It separates application code quality from Megaplan/cloud workflow quality.

## Current State

Sprint 1 completed through review and was marked `approved`.

Sprint 2 initially returned `needs_rework`, then re-entered execute and appears to have repaired the blocking findings. The later raw review output says the mounted public facade now reuses the shared core, broad verification is green, and all must criteria pass. However, Megaplan failed to parse that final review output as JSON five times and stalled at `state: executed`, so the chain did not mark Sprint 2 done or advance to Sprint 3.

## Must Fix Before Merge

### 1. Sprint 2 has two command implementations

Severity: high, likely repaired in the later Sprint 2 execute attempt but needs confirmation from a parseable review artifact

Files:
- `src/tools/video-editor/commands/core.ts`
- `src/tools/video-editor/commands/index.ts`
- `src/tools/video-editor/hooks/useTimelineState.ts`
- `supabase/functions/ai-timeline-agent/tools/timeline.ts`

Problem:
Sprint 2 was supposed to create one shared pure command core with thin frontend/backend adapters. The backend wrappers use `commands/core.ts`, but the mounted frontend facade imports `createTimelineCommandFacade` from `commands/index.ts`, which reimplements the same command bodies instead of wrapping the core.

Latest evidence:
The first Sprint 2 `review.json` flagged this as a must-fix failure. A later raw review output, stored in `review_v3_raw.txt`, says this was fixed and that `commands/index.ts` is now a mounted adapter over `./core`. Megaplan did not accept that review because the output file was not valid JSON.

Why this matters:
This leaves two mutation engines for the same public operations. The review already found real drift: `core.ts` initializes `nextState.registry.assets ??= {}` in `registerAsset()`, while `index.ts` writes to `nextState.registry.assets[input.assetId]` without guaranteeing `assets` exists.

Fix direction:
Make `commands/index.ts` a mounted adapter over `commands/core.ts`. It should handle editor-specific concerns only: getting current state, applying the returned state through `commitData`, selection side effects, semantic labels, and conversion to mounted return types. The edit semantics should live only in `core.ts`.

### 2. Sprint 2 broad verification is still red

Severity: high, likely repaired or reclassified in the later Sprint 2 execute attempt but needs confirmation from a parseable review artifact

Files/tests reported by Megaplan review:
- `supabase/functions/ai-generate-effect/index.test.ts`
- `supabase/functions/ai-voice-prompt/index.test.ts`
- `supabase/functions/ai-timeline-agent/loop.test.ts`
- `src/shared/components/ui/overlay/dropdown-menu.test.tsx`
- later full frontend run also timed out in `src/shared/components/SettingsModal/sections/GenerationSection/components/GenerationHelpPopover.test.tsx`

Problem:
Targeted video-editor and backend suites passed, but broad test commands did not complete green. Some failures may be unrelated or flaky, but Sprint 2's success criteria required broad verification to pass.

Latest evidence:
The first Sprint 2 `review.json` flagged broad verification as red. A later raw review output says the disputed edge/frontend failures were rerun green, including `npm run test:edge` and full `npm test`. Because the final review was not parseable JSON, this needs a clean review rerun or manual verification before accepting.

Why this matters:
The Sprint 2 diff touches runtime boundaries, shared contexts, edge functions, and test files outside the video editor. Until the broad failures are explained or fixed, it is not clear whether the refactor caused collateral damage.

Fix direction:
Classify each failing broad test as one of:
- caused by the Megaplan changes and fixed in this branch;
- pre-existing and documented with evidence from main;
- flaky and rerun green with a note.

Do not merge with only "targeted tests pass" as the evidence.

### 3. Sprint 2 patch is too broad for confident review

Severity: high

Evidence:
Sprint 2 review flagged roughly 8,414 changed lines across 87 files. Current cloud `git diff --stat` later showed 76 files changed with 1,650 insertions and 1,681 deletions, but the worktree had already been modified by repair attempts.

Problem:
The diff spans ports/adapters, command facade, UI components, shared `AgentChatContext`, edge functions, tests, and generated Megaplan/schema files.

Why this matters:
This makes review hard and increases regression risk. It also means the cloud worktree is no longer a clean per-sprint review surface.

Fix direction:
Split into reviewable patches:
1. Runtime/host port definitions and Reigh adapters.
2. Shared command core and frontend mounted adapter.
3. Backend wrapper migration to shared command core.
4. Tests and docs.

Generated Megaplan/schema/chain files should not be part of the app patch.

## Sprint 1 Issues To Investigate

### 4. Sprint 1 validation names overstate semantic guarantees

Severity: medium

Files:
- `src/tools/video-editor/domain/timeline/config.ts`
- `src/tools/video-editor/domain/timeline/document.ts`
- `src/tools/video-editor/lib/serialize.ts`

Problem:
Sprint 1 added structured domain issues and helpers such as `validateTimelineConfig()` and `assertValidTimelineConfig()`. The implementation mostly checks unexpected keys. Semantic issues produced during normalization, such as invalid trim ranges, are returned as issue objects but are not consistently used as blocking validation in serialize/save paths.

Why this matters:
A developer reading the API may assume `validateTimelineConfig()` fully validates the timeline domain. It does not. That creates a misleading developer experience and can let semantically invalid timelines pass unless callers manually inspect normalization issues.

Fix direction:
Either:
- make document/save paths fail on `hasTimelineDomainErrors(normalized.issues)`, or
- rename/split the APIs so structural key validation and semantic normalization issues are obviously separate.

Recommended public shape:
- `validateTimelineShape(config)`
- `normalizeTimelineConfig(config): { config, issues }`
- `assertNoTimelineDomainErrors(issues)`
- `normalizeTimelineDocument(..., { throwOnError?: true })`

### 5. Sprint 1 canonical domain still carries legacy migration behavior

Severity: medium

Files:
- `src/tools/video-editor/domain/timeline/shared.ts`
- `src/tools/video-editor/domain/timeline/config.ts`

Problem:
The new canonical domain boundary includes legacy track mapping and legacy effect migration behavior. That may be necessary for compatibility, but it makes the domain layer less clean than the name suggests.

Why this matters:
Future developers may treat the domain module as a small canonical model when it also performs historical migrations and product-specific repairs. That is workable, but it needs to be explicit.

Fix direction:
Move legacy migration policy into clearly named helpers inside the domain package, for example:
- `legacy.ts`
- `normalizeLegacyTimelineShape()`
- `repairPinnedShotGroups()`

Then make `normalizeTimelineConfig()` read as orchestration over named phases.

### 6. Sprint 1 had no automated editor smoke proof

Severity: medium

Files/artifacts:
- `.megaplan/plans/video-editor-developer-20260502-1729/review.json`

Problem:
Sprint 1 review approved the code but waived manual editor smoke coverage. The code touches render duration, preview, provider/load-save, poll sync, backend placement, and pinned shot groups.

Why this matters:
The change may be correct at the data layer but still regress mounted editor behavior. Automated unit tests do not prove basic editor interactions still work.

Fix direction:
Add a small smoke checklist or Playwright flow before merge:
- load an existing timeline;
- add a clip;
- trim/move it;
- verify preview duration remains sensible;
- save/reload;
- verify no poll-sync conflict loop;
- verify pinned shot group contiguity does not corrupt the timeline.

### 7. Sprint 1 artifacts overclaimed one documentation change

Severity: low

File:
- `docs/video_editor_canonical_timeline_sprint1.md`

Problem:
Sprint 1 claimed this doc was changed, but review/audit said it was already present and not in the current diff.

Why this matters:
This is not a code bug, but it reduces confidence in execution receipts.

Fix direction:
Treat Megaplan file-claim mismatches as review warnings. Require the final review summary to distinguish "content exists" from "this plan changed it."

## Megaplan / Cloud Workflow Issues

### 8. Chained sprints are sharing one dirty cloud worktree

Severity: high

Problem:
Sprint 2 started in the same cloud worktree after Sprint 1. The current diff now contains Sprint 1 and Sprint 2 changes together, plus repair attempts. That makes it hard to review, revert, or merge one sprint independently.

Additional evidence:
The cloud entrypoint preserves the persistent checkout when `/workspace/reigh-app/.git` already exists, and chain milestones run in that same checkout. Chain `branch` metadata exists but is currently informational. Megaplan bakeoff already has the healthier pattern: isolated worktrees plus explicit merge selection.

Why this matters:
For this style of chained work, each sprint needs an isolation boundary. Otherwise "Sprint 2 quality" and "Sprint 1 quality" become entangled.

Fix direction:
Make chain execution first-class around work items and attempts:
- each sprint runs in its own branch/worktree;
- successful sprint output is reviewed and merged into a known integration branch;
- the next sprint starts from that integration branch;
- generated Megaplan state stays outside the app diff or is ignored.

Implementation hint:
Reuse the bakeoff worktree/merge machinery instead of inventing a second isolation model.

### 9. Chain state/status can be misleading after retries

Severity: medium

Examples observed:
- `chain_state.json` initially retained `last_state: "stalled"` after a manual restart while the plan was actually healthy.
- Sprint 2 status showed all tasks complete while active step remained `execute`.
- `last_step` can show an earlier timeout/error while a repair execute is currently healthy.

Additional evidence:
Cloud chain uploads the spec to a stable remote path (`/workspace/reigh-app/chain.yaml`), and core chain state is stored beside it as `chain_state.json`. Re-running a different local chain in the same workspace can therefore reuse stale state unless the operator manually resets it.

Why this matters:
Humans need to know whether a plan is done, repairing, stalled, or safe to review. Current status requires interpretation across `state`, `active_step`, `last_step`, `progress`, and `chain_state`.

Fix direction:
Add explicit high-level statuses:
- `running`
- `repairing`
- `waiting_review`
- `done`
- `failed`
- `stalled`

When a repair starts, show: "repairing after review failure" or "retrying after execute timeout" instead of leaving that inference to the operator.

Also add:
- namespaced remote specs/state by chain id or run id;
- a spec hash in `chain_state.json`;
- `cloud chain --reset-state`;
- `cloud chain --resume-state`.

### 10. Execution progress is too coarse inside batches

Severity: medium

Problem:
During execution, status only updates between batches. Long batch runs show a live Codex process but not what it is doing.

Why this matters:
This makes it hard to distinguish productive work from a stuck agent until timeout.

Fix direction:
Write lightweight heartbeat/progress events from execute:
- current batch number;
- current task id;
- last command started/finished;
- current file focus if available;
- last artifact write time.

The `execution_trace.jsonl` should be surfaced by `megaplan status`.

### 11. Railway API/SSH timeouts interrupt observability

Severity: medium

Examples observed:
- Railway GraphQL request timeout during status polling.
- Railway WebSocket timeout while reading artifacts.

Additional evidence:
Provider commands in the Railway/SSH layers use subprocess calls without a consistent timeout envelope. A provider timeout is therefore easy to confuse with plan failure or a hung command.

Why this matters:
The plan can be healthy while the operator sees provider errors. That invites unnecessary restarts.

Fix direction:
Add retry/backoff to `megaplan cloud exec/status`, and prefer reading cached status artifacts from the worker when possible. Provider failures should be reported as "observer failed, plan state unknown" rather than plan failure.

Add provider-level configurable timeouts and classify:
- timeout;
- nonzero exit;
- missing CLI;
- transient provider/API failure.

### 12. Generated Megaplan files appear in the app diff

Severity: medium

Files repeatedly seen in cloud `git status`:
- `.megaplan/debt.json`
- `.megaplan/schemas/*.json`
- `chain.yaml`
- `chain_state.json`

Why this matters:
These files pollute code review and confuse execution audits as "unclaimed files."

Fix direction:
Separate Megaplan runtime state from repo changes:
- write generated schemas/state under an ignored runtime directory;
- or add exact ignore rules;
- or commit intentional project config separately from generated run state.

### 13. Timeout/retry semantics need clearer finalization

Severity: medium

Problem:
Sprint 2 had an execute timeout, later review returned `needs_rework`, then a repair execute started. Status exposed these facts, but the lifecycle was not obvious.

Additional evidence:
Auto phase timeout is recorded as an exit code and later interpreted through stall/retry behavior. Chain-level status receives a terminal driver outcome but loses structured timeout class/detail.

Why this matters:
An operator needs to know whether the plan is still attempting repair, whether the review failed, and whether it will automatically review again after repair.

Fix direction:
After `review: needs_rework`, Megaplan should create an explicit repair attempt:
- `attempt: 2`
- `reason: review_failed`
- `blocking_findings: [...]`
- next expected phase after execute: `review`

Timeouts should be first-class outcomes with phase, command, elapsed time, retry policy, and whether the worker process was killed.

### 14. Review output can be substantively useful but operationally rejected

Severity: high

Problem:
Sprint 2's final raw review output appears to approve the repaired work, but Megaplan rejected it repeatedly because the output file was not valid JSON. The plan then stalled at `executed` after five review attempts.

Why this matters:
The agent may have done the right work and produced a useful review, but the chain cannot advance because the harness cannot recover structured data from the raw output. This leaves the operator in an awkward state: semantically "probably reviewed" but mechanically "stalled."

Fix direction:
Improve review-output recovery:
- extract the last valid JSON object from noisy output when schema mode fails;
- store both `raw_review.md` and `review.json`;
- classify this as `review_parse_error`, not generic `review error`;
- allow `megaplan review --repair-output` or `megaplan review --from-raw` to convert a raw successful review into structured state;
- cap repeated parse retries earlier and surface the raw output path in status.

### 15. Existing cloud chain sessions are ambiguous

Severity: low/medium

Problem:
When `cloud chain` finds an existing remote tmux session, it can report that the chain is already running without proving which spec, state file, or chain id the tmux session is using.

Why this matters:
This is risky after uploading a new chain spec. The operator may believe the new chain is running while the old tmux session is still executing an older spec.

Fix direction:
Persist active chain metadata in the remote workspace and show it in `cloud status --chain`:
- chain id/spec path;
- spec hash;
- started at;
- current plan;
- tmux session id.

Require an explicit `--replace` flag to kill/restart an existing chain session.

## Merge Recommendation

Do not merge the combined cloud worktree as-is.

Recommended path:
1. Let Sprint 2 finish its repair and review loop.
2. Export clean per-sprint diffs or branches.
3. Review and land Sprint 1 separately after addressing or explicitly accepting its medium-risk items.
4. For Sprint 2, require the command facade duplication to be fixed before merge.
5. Keep Megaplan runtime artifacts out of the app patch.

## Quick Triage Table

| Area | Status | Merge stance |
| --- | --- | --- |
| Sprint 1 canonical domain | Approved with caveats | Reviewable after smoke/validation cleanup decision |
| Sprint 2 runtime ports/adapters | Mostly landed | Needs final review after repair |
| Sprint 2 command facade | Initial review failed; later raw review says repaired | Confirm with parseable review/manual inspection |
| Broad tests | Initial review red; later raw review says green | Confirm with parseable review/manual inspection |
| Cloud chain mechanics | Working but noisy | Improve status/attempt/worktree model |
| Combined cloud diff | Dirty and cross-sprint | Do not merge as one patch |
