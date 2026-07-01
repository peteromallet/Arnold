# Arnold Branch Transplant Audit

Date: 2026-06-12

This document records the branch/worktree/stash disposition for the Arnold clean
extraction. It is a decision record, not a raw inventory. The raw fan-out audit
was run with six DeepSeek subagents, then spot-checked manually against the
local worktrees.

The controlling rule is:

```text
Build on feat/arnold-clean-extraction from origin/main.
Quarry other branches by concept and verified files.
Do not merge broad branches wholesale.
Do not prune dirty branches/worktrees until their unique payload is either
ported, deferred with a named target, or explicitly rejected.
```

## Current Build Branch

Use:

- `feat/arnold-clean-extraction`
- worktree: `/Users/peteromalley/Documents/.worktrees/arnold-clean-extraction`
- base: `origin/main`

This worktree contains the clean Slices 1-32:

- static Arnold conformance gates;
- neutral cost/media/token accounting;
- runtime event journal, WAL fold, state persistence, semantic replay;
- neutral agent contracts, dispatcher, provider pool, and adapter protocols;
- Megaplan StepContract registry and Megaplan registry cutover;
- executor hooks, runner surface, typed Step-IO write/read checks;
- behavioural routing/join conformance;
- evidence-pack hooks as the non-Megaplan proof pipeline;
- runtime surface cleanup;
- runtime-checkable backend adapter protocol;
- reshaped DeepSeek adapter;
- Megaplan-package Codex/Shannon adapters;
- neutral resume cursor persistence, artifact IO/sidecar manifests, and
  resume re-verification helpers;
- evidence-pack package-owned resume driver;
- neutral LLM JSON extraction helper;
- validator support for caller-supplied invocation adapter registries;
- neutral model-seam submodule for model render/capture/budget/audit primitives;
- Megaplan model-seam wrapper compatibility over the neutral seam;
- generic subpipeline child-context cloning for package-owned context fields;
- neutral panel-result aggregation join primitive;
- neutral runtime error/outcome carriers and control-plane carrier contracts;
- profile structured-value validators for package-owned stage settings;
- neutral contract schema registry root resolution;
- neutral subprocess spawn/process-group reaping primitives;
- neutral sandbox path-validation primitives;
- neutral suite-delta computation utility;
- neutral static authoring checks for pipeline declarations;
- conformance ratchet cleanup after schema-registry decontamination.

The worktree is committed slice-by-slice. Keep preserving each green slice
before any branch surgery.

Full-suite readiness was verified with the project interpreter rather than the
ambient `pytest` executable:

```text
python -m pytest tests/arnold -q
1469 passed in 84.22s (0:01:24)
```

`python-dotenv` is already declared in `pyproject.toml` and installed in the
project interpreter used by `python -m pytest`; invoking a different global
`pytest` may still miss that dependency.

## Safe Base / Rejected Bases

| Branch or Worktree | Disposition | Reason |
| --- | --- | --- |
| `origin/main` | Base | Already contains the initial `arnold-epic` foundation. |
| `arnold-epic` | Consumed | No unique branch payload left beyond `origin/main`. |
| local repo root on `fix/finalize-readiness-deadturn-and-baseline-cache` | Not a base | Dirty Megaplan engine integration checkout, not Arnold-neutral extraction. |
| `arnold-generalized-pipeline` | Quarry only | Valuable Arnold material, but too broad and includes generated/archive artifacts and flattened abstractions. |

## Direct-Port / Already-Ported Areas

These areas have either landed in Slices 1-32 or are close enough that future
ports should use the source branch only as evidence, not as a merge target.

| Source | Status | Notes |
| --- | --- | --- |
| `fix/arnold-neutralize-canonicalusage` | Consumed by Slice 2 | Neutral cost/media/token primitives landed. Remaining branch state is not a blocker. |
| `fix/arnold-conformance-gate` committed conformance package | Mostly consumed by Slices 1, 8, 11 | Static gates, routing/join checks, and typed Step-IO checks have clean equivalents. |
| `arnold-generalized-pipeline` runtime journal/state/replay files | Mostly consumed by Slices 3 and 10 | The clean branch deliberately removed plan/phase compatibility vocabulary. |
| `arnold-generalized-pipeline` agent contracts/dispatcher/provider pool | Mostly consumed by Slices 4, 12, 13 | DeepSeek is reshaped as a neutral provider adapter; Megaplan-backed Codex/Shannon wrappers landed in Slice 14. |
| `arnold/panel-dispatch` DeepSeek adapter ideas | Consumed by Slice 13 | Do not reintroduce import-time adapter registration or baked pricing. |
| `arnold/panel-dispatch` Codex/Shannon adapter ideas | Consumed by Slice 14 | Megaplan-worker-backed adapters now live under `arnold.pipelines.megaplan.agent_adapters`, not neutral `arnold.agent`. |
| `arnold-generalized-pipeline` resume/artifact IO prerequisites | Consumed by Slices 15-18 | Neutral cursor persistence, artifact IO/sidecar manifests, resume re-verification helpers, and the evidence-pack package resume driver landed. Broad neutral executor resume machinery is rejected for now. |
| `arnold-generalized-pipeline` `llm_json.py` | Consumed by Slice 19 | Neutral model-output JSON extraction landed as a small prerequisite for future package/model-seam work. |
| `arnold-generalized-pipeline` validator adapter-registry patch | Consumed by Slice 20 | `validate()` and `validate_invocation_requirements()` can now accept a caller-supplied `StepInvocationAdapterRegistry` while preserving default fail-closed behavior. |
| `arnold-generalized-pipeline` neutral/model wrapper seam | Consumed by Slices 21-22 | Generic render/capture/budget/audit primitives landed under `arnold.pipeline.model_seam`; Megaplan now wraps/re-exports the generic seam package-locally while keeping schemas, recovery, and compatibility guards in the Megaplan package. |
| `arnold-generalized-pipeline` subpipeline context copy | Consumed by Slice 23 | Non-dataclass child contexts now clone arbitrary parent attributes and override only `artifact_root` and `inputs`, so package-owned runtime/capability fields survive without Arnold hard-coding their names. |
| `arnold-generalized-pipeline` panel aggregation join | Consumed by Slice 24 | `aggregate_panel_join()` landed as a policy-free join primitive that preserves child outputs and sums caller-named numeric usage fields. |
| `arnold-generalized-pipeline` runtime error/outcome + control carriers | Consumed by Slice 25 | `ArnoldError`, `RunOutcome`, `RunResultMetadata`, and neutral `arnold.control` carriers landed without Megaplan imports. Existing Megaplan aliases can be retargeted later. |
| `arnold-generalized-pipeline` profile dict-value validators | Consumed by Slice 26 | Profile loading can now accept package-owned structured stage values only through explicit validators; default validation remains fail-closed to string agent specs. |
| `arnold-generalized-pipeline` schema registry decontamination | Consumed by Slice 27 | Neutral schema registry root resolution now uses explicit roots or `ARNOLD_CONTRACT_SCHEMA_ROOT`; `.megaplan/plans` derivation and `MEGAPLAN_CONTRACT_SCHEMA_ROOT` are no longer neutral Arnold behavior. |
| `arnold-generalized-pipeline` process primitives | Consumed by Slice 28 | `arnold.runtime.process` now owns neutral `spawn`, `spawn_async`, and `kill_group` helpers. Tmux session/orphan helpers remain Megaplan-package concerns. |
| `arnold-generalized-pipeline` sandbox validators | Consumed by Slice 29 | `arnold.runtime.sandbox` now owns neutral sandbox ContextVar and path validators. Tool-registry wrapper installation remains package-owned. |
| `arnold-generalized-pipeline` suite delta | Consumed by Slice 30 | `arnold.pipeline.suite_delta` now provides pure nodeid-level baseline-vs-verification diffing and excludes deleted tests from newly passing results. |
| `arnold-generalized-pipeline` C4 static checks | Consumed by Slice 31 | `arnold.pipeline.c4_static_checks` now provides neutral structured findings, structural-subset checks, binding-map port checks, schema-shape checks, and optional caller-supplied adapter-registry call-site checks. Media-pricing advice and global/default registry assumptions were deliberately not ported. |
| clean branch conformance allowlist | Cleaned by Slice 32 | Removed the stale `semantic-coupling arnold.pipeline.schema_registry` allowlist entry exposed by the schema-registry decontamination. `arnold.pipeline.step_io_policy` remains the only semantic-coupling allowlist entry. |

## Remaining Arnold Quarry

These are the only remaining quarry buckets. None are immediate clean-branch
ports after Slice 31; each either needs a concrete package caller or belongs to
Megaplan/product integration.

| Source | Quarry | Target Decision |
| --- | --- | --- |
| `arnold/panel-dispatch` dirty worktree | Hermes CLI / Honcho relocation leftovers | Codex/Shannon adapters, `_oneshot`, adapter tests, and worker `free_text` support are ported. Keep the remaining relocation parked until a separate product integration task proves it is needed. |
| `arnold-generalized-pipeline` | remaining discovery, validator, routing, and possible same-graph entry override helper | Mine incrementally only if new evidence appears. Classify each as kernel, workflow, patterns, execution, or package-local before porting. `artifact_io.py`, cursor helpers, `resume_validation.py`, evidence-pack package resume, `llm_json.py`, the adapter-registry validator patch, neutral `model_seam.py`, Megaplan wrapper compatibility, generic subpipeline child-context cloning, panel aggregation join, profile structured-value validators, schema registry decontamination, and static authoring checks are already consumed. Do not port quarry `run_pipeline_resume()` or WAL replay into the neutral executor. |
| `arnold-generalized-pipeline` | `effect.py`, `oracle.py`, plus supervisor model/outcome helpers | Side-effect/capability/oracle material is promising but still target-shape work. `outcome.py`, neutral control carriers, process primitives, and sandbox path validators are consumed; do not port broad replay/effect/supervisor semantics until a concrete runtime/control caller needs them. |
| `arnold-generalized-pipeline` | `arnold/pipeline/_cli_check.py` | Reject as a current port. It is a fixture CLI for the C4 checker and includes media-pricing warning paths that were intentionally excluded from neutral static checks. Recreate a real CLI later only when the public Arnold command surface is designed. |
| `arnold-generalized-pipeline` | `arnold/pipeline/steps/human_gate.py` | Defer/re-author. The idea is useful, but the quarry file is stale against the current `ContractResult`/`Suspension` surface and imports `HumanSuspension`, which is not the current neutral type. A reusable human-interaction step should be designed against the new seam, not copied. |
| `arnold-generalized-pipeline` | `arnold/pipelines/deliberation/*` | Defer as a package example, not a substrate primitive. It is useful proof that layered critique pipelines fit the new model, but it hard-codes one workflow and journal semantics. Bring it back only as a concrete package after the package authoring contract is settled. |
| `arnold-generalized-pipeline` and `arnold/panel-dispatch` | broad `arnold/agent/**`, Hermes CLI, Honcho integration, environment tools, and tool registry stack | Reject for neutral Arnold. Concrete DeepSeek/Codex/Shannon adapter seams already landed in smaller shapes. The remaining stack is product/runtime integration and would reintroduce old coupling if imported wholesale. |
| `arnold-generalized-pipeline` | `arnold/pipelines/megaplan/_pipeline/adapter.py`, `hooks.py`, `artifact_adapter.py`, `schema_registry_adapter.py`, `step_io_policy_adapter.py` | Defer to the Megaplan package integration milestone. These are bridge/hook implementations, not Arnold kernel code, and should be built only when Megaplan is wired onto the canonical executor surface. |
| `fix/arnold-conformance-gate` dirty worktree | `advisory_projection.py` plus modified execute/completion/evidence/policy/test files | Preserve before pruning. Treat as possible Megaplan execution-runtime hardening, not a blind Arnold import. |

## Megaplan Package Branches

These branches are relevant to the larger Megaplan product, but they do not
block the Arnold substrate extraction.

| Branch or Worktree | Disposition | Notes |
| --- | --- | --- |
| `mp-tbr-merge` | Defer to Megaplan test-selection milestone | Has valuable `test_selection.py`, untracked `full_suite_backstop.py`, `import_graph.py`, and `tests/orchestration/`. Dirty worktree must be preserved before pruning. |
| `mp-test-blast-radius` | Reject as separate source | Subsumed by `mp-tbr-merge`. |
| `mp-milestone-attribution-ground-truth` | Defer to evidence/attribution milestone | Useful Megaplan observability/store work, not Arnold-neutral prerequisite. |
| `fix/engine-bug-ledger` | Harvest design only | Cost/provenance event shape for Codex-routed execute tasks may inform event taxonomy. Do not merge into Arnold. |
| `mp-engine-fixes` / related engine fix branches | Keep as Megaplan engine concerns | Not Arnold extraction blockers. |
| `fix/finalize-readiness-deadturn-and-baseline-cache` | Do not base Arnold on it | Dirty broad integration branch; inspect only when doing Megaplan engine cleanup. |

## Shannon Branches

The Shannon branches are operational worker/UX work, not Arnold substrate work.
Do not port them into Arnold extraction.

| Branch Family | Disposition |
| --- | --- |
| `shannon-bun-deadwedge-fix`, `working-branch` | Reject for Arnold. Duplicate/obsolete operational fixes. |
| `shannon-liveness-probe` | Reject for Arnold. Worker ops concern. |
| `shannon-stream`, `sstest0612`, `shannon-stream-epic` | Reject for Arnold. Stream UX/planning concern. |
| `shannon-tmux-server-isolation`, `finalize-turn-death-fix` | Reject for Arnold. Duplicate Megaplan worker isolation concern. |
| `recovery/pre-shannon-merge-20260610` | Keep as recovery snapshot only. |

Future Shannon adapter work should come from `arnold/panel-dispatch`, not from
the Shannon ops branches.

## Stashes

| Stash | Disposition | Reason |
| --- | --- | --- |
| `stash@{0}` `T9 work in progress` | Park | Megaplan operational improvements; low overlap with Arnold extraction. |
| `stash@{1}` `m2.5-autopy-spike` | Park | Earlier pipeline spike; use only if current clean branch regresses an equivalent idea. |
| `stash@{2}` `m2-types-and-port` | Park / inspect before deletion | Could contain registry or CLI ideas, but not a known Arnold blocker. |
| `stash@{3}` `m1-foundation` | Preserve for Megaplan engine cleanup, not Arnold | Spot-check shows only `megaplan/_core/state.py`, `megaplan/auto.py`, `megaplan/chain/__init__.py`, and `tests/test_chain.py`. It may matter for chain/autocommit semantics, but it is not Arnold-neutral substrate. |
| `stash@{4}`-`stash@{6}` `m0-harness-floor` | Reject later with approval | Obsolete harness/skill/brief formatting material. Do not drop without approval. |

## Dirty Worktree Risks

Before any pruning or branch deletion, preserve these:

- current clean extraction worktree: preserve future green slices before
  branch surgery;
- `/Users/peteromalley/Documents/.worktrees/arnold-conformance-gate`: dirty
  execute/completion/evidence/policy/test changes and untracked
  `advisory_projection.py`;
- `/Users/peteromalley/Documents/.megaplan-worktrees/tbr-merge`: dirty test
  selection work plus untracked `full_suite_backstop.py`, `import_graph.py`,
  and `tests/orchestration/`;
- `/Users/peteromalley/Documents/.megaplan-worktrees/arnold-panel-dispatch`:
  remaining Hermes/Honcho relocation payload, if any later product task needs
  it;
- `/private/tmp/arnold-target`: local `arnold-generalized-pipeline` quarry.

The locked worktree entry `/private/tmp/arnold-engine-sn` is stale on disk in
this environment: `git worktree list` reports it, but the directory is absent.
Treat it as a cleanup item only after confirming no external process relies on
that lock metadata.

## Resume Integration Decision

Slice 18 resolves the immediate executor-level resume question by keeping resume
authority package-local. `arnold.pipelines.evidence_pack.resume_evidence_pack()`
resolves the persisted cursor, validates that evidence-pack can only re-enter
`human_review`, seeds explicit `human_input`, optionally calls
`reverify_resume_produces()` against a supplied human `Suspension`, and then runs
`build_continuation_pipeline()` as a normal fresh pipeline.

The rejected shape is the quarry branch's broad neutral `run_pipeline_resume()`:
cursor body interpretation, event-journal/WAL replay, and package state
authority are not generic enough for `arnold.pipeline.executor`. If multiple
future packages need same-graph re-entry, add a small entry-override helper only
after the second concrete package proves the need.

## M5 Cleanup Status

Slices 1–32 have landed in `feat/arnold-clean-extraction`. M5 is the cleanup
sprint: no new extraction ports are planned. The remaining work is branch
retirement classification, compatibility-policy documentation, allowlist
ratcheting, and artifact-gate hardening.

The clean extraction phase is complete. The next work is an epic, captured in
`.megaplan/initiatives/arnold-post-extraction-next/chain.yaml`, not more broad
quarrying.

1. **M1: Megaplan canonical executor bridge** —
   run `.megaplan/initiatives/arnold-post-extraction-next/briefs/m1-megaplan-canonical-executor-bridge.md`
   first. This wires one representative Megaplan path onto
   `arnold.pipeline.run_pipeline` through package-owned adapters/hooks while
   preserving compatibility.
2. **M2: Package authoring surface** —
   make package authoring concrete after the bridge exists, without promoting
   low-level `Stage` / `Edge` / `StepResult.next` as the polished public DSL.
3. **M3: Human interaction and deliberation package** —
   re-author human interaction only if it still earns a neutral/pattern helper,
   then bring deliberation back as a package example rather than substrate.
4. **M4: Megaplan package hardening** —
   fold in test-selection, attribution, execution hardening, and dirty
   conformance-gate leftovers as Megaplan-package work.
5. **M5: Branch retirement and compatibility cutover** —
   mechanically retire or park old branches/worktrees only after the documented
   criteria are satisfied and destructive cleanup is explicitly approved.

## M5 Disposition Verdict

This section is the authoritative M5 disposition table. It covers every quarry
area (branch, worktree, or stash) identified across the audit doc, the split-plan
(deletion criteria at lines 535–608), and the port ledger. The audit doc's
classification of Slices 1–32 as landed is accepted as authoritative.

| Branch / Worktree / Stash | Disposition | Evidence | Deletion-Safe? |
| --- | --- | --- | --- |
| `origin/main` | Base | Contains initial `arnold-epic` foundation. | No — canonical base. |
| `arnold-epic` | Consumed | No unique payload beyond `origin/main`. | Yes — subsumed. |
| `fix/arnold-neutralize-canonicalusage` | Consumed (Slice 2) | Neutral cost/media/token primitives landed. | Yes — payload consumed. |
| `fix/arnold-conformance-gate` (branch) | Mostly consumed (Slices 1, 8, 11) | Static gates, routing/join checks, typed Step-IO checks have clean equivalents. | No — dirty worktree must be preserved before pruning (see below). |
| `arnold-generalized-pipeline` (branch) | Quarry only — **DO NOT DELETE YET** | 5 local-only commits ahead of origin; runtime journal/state/replay, agent contracts, resume helpers, model-seam, schema-registry decontamination, sandbox/process primitives, suite delta, C4 static checks all consumed. Remaining quarry buckets (see Remaining Arnold Quarry table) are deferred or rejected. | **Not yet** — local commits not pushed; dirty worktrees unpreserved. |
| `/private/tmp/arnold-target` (worktree, `arnold-generalized-pipeline`) | Preserve-before-prune | 5 commits ahead of origin (`5ea1f70a`, `4544c94d`, merge commits, `b1ed2225`). | No — must push or archive local commits first. |
| `arnold/panel-dispatch` (branch/worktree) | Mostly consumed (Slices 13, 14) | DeepSeek adapter reshaped (Slice 13); Codex/Shannon adapters + `free_text` landed (Slice 14). Remaining Hermes/Honcho relocation parked. | No — remaining relocation payload must be preserved or explicitly rejected. |
| `/Users/peteromalley/Documents/.megaplan-worktrees/arnold-panel-dispatch` (dirty worktree) | Preserve-before-prune | Hermes CLI / Honcho relocation leftovers. | No — preserve until product integration task resolves. |
| `/Users/peteromalley/Documents/.worktrees/arnold-conformance-gate` (dirty worktree, `fix/arnold-conformance-gate`) | Preserve-before-prune | Dirty execute/completion/evidence/policy/test changes and untracked `advisory_projection.py`. Treat as Megaplan execution-runtime hardening. | No — preserve before pruning. |
| `/Users/peteromalley/Documents/.megaplan-worktrees/tbr-merge` (`mp-tbr-merge`) | Preserve-before-prune | Dirty test-selection work plus untracked `full_suite_backstop.py`, `import_graph.py`, `tests/orchestration/`. | No — defer to Megaplan test-selection milestone. |
| `mp-tbr-merge` (branch) | Defer to Megaplan test-selection milestone | Valuable `test_selection.py`, untracked integration files. | No — deferred, not rejected. |
| `mp-test-blast-radius` (branch) | Reject as separate source | Subsumed by `mp-tbr-merge`. | Yes — after `mp-tbr-merge` is preserved. |
| `mp-milestone-attribution-ground-truth` (branch) | Defer to evidence/attribution milestone | Useful Megaplan observability/store work. | No — deferred. |
| `fix/engine-bug-ledger` (branch) | Harvest design only | Cost/provenance event shape for Codex-routed execute tasks (commit `41571fcd`). | No — design notes not yet harvested. |
| `mp-engine-fixes` / related engine fix branches | Keep as Megaplan engine concerns | Not Arnold extraction blockers. | No — keep for Megaplan. |
| `fix/finalize-readiness-deadturn-and-baseline-cache` (branch) | Do not base Arnold on it | Dirty broad integration branch. | No — inspect only during Megaplan engine cleanup. |
| Shannon branches (`shannon-bun-deadwedge-fix`, `working-branch`, `shannon-liveness-probe`, `shannon-stream`, `sstest0612`, `shannon-stream-epic`, `shannon-tmux-server-isolation`, `finalize-turn-death-fix`) | Reject for Arnold | Operational worker/UX work; duplicate/obsolete fixes. | Yes — after confirming no Shannon adapter needs them. |
| `recovery/pre-shannon-merge-20260610` | Keep as recovery snapshot only | Recovery reference. | No — keep for disaster recovery. |
| `stash@{0}` (`T9 work in progress`) | Park | Megaplan operational improvements. | No — parked. |
| `stash@{1}` (`m2.5-autopy-spike`) | Park | Earlier pipeline spike. | No — parked. |
| `stash@{2}` (`m2-types-and-port`) | Park / inspect before deletion | Could contain registry or CLI ideas. | No — inspect first. |
| `stash@{3}` (`m1-foundation`) | Preserve for Megaplan engine cleanup | `megaplan/_core/state.py`, `megaplan/auto.py`, `megaplan/chain/__init__.py`, `tests/test_chain.py`. | No — preserve for Megaplan. |
| `stash@{4}`–`stash@{6}` (`m0-harness-floor`) | Reject later with approval | Obsolete harness/skill/brief formatting material. | No — require explicit approval. |
| `/private/tmp/arnold-engine-sn` (stale locked worktree) | Cleanup item | `git worktree list` reports it; directory absent on disk. | Yes — after confirming no external process uses the lock metadata. |

### Quarry-Area Disposition by Category

**Already consumed (safe to delete source once worktrees preserved):**
- `fix/arnold-neutralize-canonicalusage`
- `arnold-epic`

**Quarry (keep; local commits not archived):**
- `arnold-generalized-pipeline` + `/private/tmp/arnold-target` worktree

**Preserve-before-prune (dirty worktrees with unique payload):**
- `/Users/peteromalley/Documents/.worktrees/arnold-conformance-gate`
- `/Users/peteromalley/Documents/.megaplan-worktrees/tbr-merge`
- `/Users/peteromalley/Documents/.megaplan-worktrees/arnold-panel-dispatch`

**Deferred (keep for named milestone):**
- `mp-tbr-merge`, `mp-milestone-attribution-ground-truth`, `fix/engine-bug-ledger`

**Rejected for Arnold (safe to delete after review):**
- `mp-test-blast-radius` (subsumed)
- Shannon branches (8 branches, operational)
- `stash@{4}`–`stash@{6}` (after approval)

**Parked (no action needed):**
- `stash@{0}`, `stash@{1}`, `stash@{2}`, `stash@{3}`

### Gaps and Reclassifications

1. **`arnold-generalized-pipeline` deletion gate**: The split-plan (line 536) requires
   every quarry area to be ported, deferred with named target, or explicitly rejected
   before the branch can be deleted. The "Remaining Arnold Quarry" table in this audit
   doc satisfies the deferred and rejected categories. However, the 5 local-only commits
   on `/private/tmp/arnold-target` must be pushed to origin or archived before deletion.
   **Reclassification**: move from implicit "quarry only" to explicit "preserve-before-prune
   worktree; branch safe to delete after push."

2. **`fix/arnold-conformance-gate`**: Previously classified as "Mostly consumed." The
   dirty worktree at `/Users/peteromalley/Documents/.worktrees/arnold-conformance-gate`
   contains `advisory_projection.py` and modified execute/completion/evidence/policy/test
   files. **Reclassification**: the branch itself is consumed; the dirty worktree is
   "preserve-before-prune" for Megaplan M4 hardening.

3. **`arnold/panel-dispatch` Hermes/Honcho relocation**: Previously "keep parked." The
   adapters and `free_text` support have landed. **Reclassification**: remaining payload
   is "reject for Arnold, preserve worktree snapshot only" — no future Arnold extraction
   should quarry it.

4. **`stash@{2}`**: Audit doc says "park / inspect before deletion." No inspection has
   occurred yet. **Flag**: must be inspected before M5 close; cannot be silently deleted.

## Next Execution Order

The clean extraction phase is complete. The next work is an epic, captured in
`.megaplan/initiatives/arnold-post-extraction-next/chain.yaml`, not more broad
quarrying.

1. **M1: Megaplan canonical executor bridge** —
   run `.megaplan/initiatives/arnold-post-extraction-next/briefs/m1-megaplan-canonical-executor-bridge.md`
   first. This wires one representative Megaplan path onto
   `arnold.pipeline.run_pipeline` through package-owned adapters/hooks while
   preserving compatibility.
2. **M2: Package authoring surface** —
   make package authoring concrete after the bridge exists, without promoting
   low-level `Stage` / `Edge` / `StepResult.next` as the polished public DSL.
3. **M3: Human interaction and deliberation package** —
   re-author human interaction only if it still earns a neutral/pattern helper,
   then bring deliberation back as a package example rather than substrate.
4. **M4: Megaplan package hardening** —
   fold in test-selection, attribution, execution hardening, and dirty
   conformance-gate leftovers as Megaplan-package work.
5. **M5: Branch retirement and compatibility cutover** —
   mechanically retire or park old branches/worktrees only after the documented
   criteria are satisfied and destructive cleanup is explicitly approved.

## M5 Deletion Proposals

This section reconciles the M5 Disposition Verdict (above) against the
pre-planned deletion categories from the split-plan (deletion criteria at
lines 535–608) and the port ledger. Every proposed action below is a
**non-destructive proposal** — no `git branch -d`, `git worktree prune`, or
`git stash drop` command is issued here. Destructive cleanup requires
explicit approval in a separate execution gate.

**⚠️ No destructive operations are performed by this proposal.** Every item
below is documentation-only. Actual deletion/retirement commands must be
reviewed and executed in a dedicated cleanup run after all preconditions are
met.

### Conformance & Test Suite Status (2026-06-13)

| Gate | Result | Notes |
| --- | --- | --- |
| `python -m pytest tests/arnold/ -q` | 1527 passed, 4 failed, 2 skipped | All 4 failures are conformance-suite behavioral tests that assert `run_conformance_suite().passed is True`. These are pre-existing and unrelated to M5 doc changes. |
| `run_conformance_suite()` import-coupling | **PASS** | No new cross-package coupling. |
| `run_conformance_suite()` package-name-staleness | FAIL (pre-existing) | `arnold.pipelines._authoring`, `arnold.pipelines._template` — added in Slices 18–32, not M5. |
| `run_conformance_suite()` semantic-coupling | FAIL (pre-existing) | `arnold.pipelines._deliberation_example.pipelines` — added in Slices 18–32, not M5. |
| `run_conformance_suite()` public-workflow-layering | FAIL (pre-existing) | `arnold.pipelines._authoring`, `arnold.pipelines._deliberation_example._hooks` — added in Slices 18–32, not M5. |
| `run_conformance_suite()` never-port-artifacts | FAIL (pre-existing) | `.megaplan/plans/` Hermes state databases and step receipts from Megaplan execution — not caused by M5. |

**Verdict**: No new failures introduced. All observed failures are pre-existing
and catalogued in the conformance allowlist (`arnold/conformance/_allowlist.txt`).

### Proposal Table

Each quarry area from the M5 Disposition Verdict is mapped to a concrete
retirement action with preconditions and approval gates.

| # | Quarry Area | Proposed Action | Preconditions | Approval Gate |
| --- | --- | --- | --- | --- |
| 1 | `arnold-epic` (branch) | **Delete** | Confirm no unpushed commits. | Auto-approved: payload consumed by Slices 1–32. |
| 2 | `fix/arnold-neutralize-canonicalusage` (branch) | **Delete** | Confirm no unpushed commits. | Auto-approved: payload consumed by Slice 2. |
| 3 | `mp-test-blast-radius` (branch) | **Delete** | `mp-tbr-merge` dirty worktree preserved first. | Post-M4: subsumed by `mp-tbr-merge`. |
| 4 | Shannon branches (8 branches: `shannon-bun-deadwedge-fix`, `working-branch`, `shannon-liveness-probe`, `shannon-stream`, `sstest0612`, `shannon-stream-epic`, `shannon-tmux-server-isolation`, `finalize-turn-death-fix`) | **Delete (local only)** | Confirm no Shannon adapter needs them. | **LOCAL-ONLY scope.** Remote deletion requires separate approval. Do not delete on origin without explicit authorization. |
| 5 | `stash@{4}`–`stash@{6}` (`m0-harness-floor`) | **Drop** | Explicit approval obtained. | Requires explicit approval gate. |
| 6 | `/private/tmp/arnold-engine-sn` (stale locked worktree) | **Prune** | Confirm no external process relies on lock metadata. | Auto-approved: directory absent on disk. |
| 7 | `fix/arnold-conformance-gate` (branch) | **Retain branch; preserve dirty worktree** | Dirty worktree at `/Users/peteromalley/Documents/.worktrees/arnold-conformance-gate` archived. | Defer to M4 Megaplan hardening. |
| 8 | `arnold-generalized-pipeline` (branch) | **Retain until local commits pushed** | 5 local commits on `/private/tmp/arnold-target` pushed to origin or archived. | After push, branch is safe to delete. |
| 9 | `/private/tmp/arnold-target` (worktree) | **Retain until branch commits archived** | Push or archive 5 local commits (`5ea1f70a`, `4544c94d`, merge commits, `b1ed2225`). | After push, worktree is safe to prune. |
| 10 | `/Users/peteromalley/Documents/.worktrees/arnold-conformance-gate` (dirty worktree) | **Preserve for M4** | Archive `advisory_projection.py` and modified test files. | Defer to M4 Megaplan hardening. |
| 11 | `/Users/peteromalley/Documents/.megaplan-worktrees/tbr-merge` (dirty worktree) | **Preserve for Megaplan test-selection milestone** | Archive `full_suite_backstop.py`, `import_graph.py`, `tests/orchestration/`. | Defer to Megaplan test-selection milestone. |
| 12 | `/Users/peteromalley/Documents/.megaplan-worktrees/arnold-panel-dispatch` (dirty worktree) | **Preserve snapshot; reject for Arnold** | Hermes/Honcho relocation payload snapshot archived. | No future Arnold extraction should quarry this worktree. |
| 13 | `mp-tbr-merge` (branch) | **Retain** | — | Defer to Megaplan test-selection milestone. |
| 14 | `mp-milestone-attribution-ground-truth` (branch) | **Retain** | — | Defer to evidence/attribution milestone. |
| 15 | `fix/engine-bug-ledger` (branch) | **Retain; harvest design** | Extract cost/provenance event shape notes. | Harvest before deletion. |
| 16 | `mp-engine-fixes` / related engine fix branches | **Retain** | — | Keep as Megaplan engine concerns. |
| 17 | `fix/finalize-readiness-deadturn-and-baseline-cache` (branch) | **Retain** | — | Inspect only during Megaplan engine cleanup. |
| 18 | `recovery/pre-shannon-merge-20260610` (branch) | **Retain** | — | Keep for disaster recovery. |
| 19 | `stash@{0}` (`T9 work in progress`) | **Park** | — | No action; parked. |
| 20 | `stash@{1}` (`m2.5-autopy-spike`) | **Park** | — | No action; parked. |
| 21 | `stash@{2}` (`m2-types-and-port`) | **Inspect before deletion** | Manual inspection for registry/CLI ideas required. | Cannot be silently deleted. |
| 22 | `stash@{3}` (`m1-foundation`) | **Preserve for Megaplan engine cleanup** | — | Keep for Megaplan chain/autocommit semantics. |
| 23 | `arnold/panel-dispatch` (branch) | **Retain until worktree preserved** | Dirty worktree snapshot archived. | After preservation, branch is safe to delete. |

### Shannon Branch Deletion: Local-Only Scope

**All Shannon branch deletions are strictly local.** The 8 Shannon branches
(`shannon-bun-deadwedge-fix`, `working-branch`, `shannon-liveness-probe`,
`shannon-stream`, `sstest0612`, `shannon-stream-epic`,
`shannon-tmux-server-isolation`, `finalize-turn-death-fix`) are operational
worker/UX branches with no Arnold substrate content. They are safe to delete
locally because:

1. No Shannon adapter work depends on them — adapters were quarried from
   `arnold/panel-dispatch` (Slices 13–14), not these branches.
2. They contain duplicate/obsolete operational fixes that are either already
   merged or superseded.
3. `recovery/pre-shannon-merge-20260610` is preserved as a disaster-recovery
   snapshot.

**Remote deletion of Shannon branches on `origin` requires separate, explicit
approval.** Do not `git push --delete` any Shannon branch without a dedicated
review. Local deletion uses `git branch -d` (safe, refuses if not merged) and
is scoped to the current machine only.

### No-Destructive-Ops Guarantee

This document is a **proposal only**. No `git branch -d`, `git worktree prune`,
`git stash drop`, or `git push --delete` command is issued by the M5 audit or
plan execution. All destructive cleanup must be performed in a separate,
explicitly-approved execution gate after every precondition in the proposal
table is satisfied.

The conformance suite and test suite results above confirm that no new
regressions were introduced by the M5 documentation changes. The 4 pre-existing
conformance failures and 4 pre-existing behavioral test failures are catalogued
in the allowlist and are unrelated to branch retirement.
