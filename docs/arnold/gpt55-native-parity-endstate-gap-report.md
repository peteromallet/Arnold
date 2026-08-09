# GPT-5.5 Native Parity End-State Gap Report

## Executive Verdict

Verdict: **right direction but under-gated**.

Confidence: **high**.

The corrective epic is aimed at the real failure mode: previous work accepted a native-looking representation, generated ledgers, and compatibility projections as proof, while the actual product semantics still needed component constants, route bindings, handler refs, manifest/compatibility code, and handler-local state transitions to explain Megaplan. The current North Star and corrective plan explicitly reject that bar and put the semantic checker, row evidence, source-derived `build_pipeline()` behavior, negative fixtures, and compatibility quarantine before broad extraction.

The remaining risk is that the repository is still in the danger zone the plan describes. The canonical source has visible Python-shaped branches and loops, but it still imports `AUTHORING_*` and `*_WORKFLOW` carriers, contains literal `handler_ref` / `route_bindings` declarations, and depends on `components.py` policy/topology surfaces for many semantics. The strict checker catches part of this today, but its coverage is not yet broad enough to make final closure impossible to fake.

## What The True End State Was

There are two related but distinct targets in the historical docs.

The more ambitious end-state target was ordinary async Python as the product workflow. The example file shows `@phase` async functions returning typed objects, then a `@pipeline("megaplan")` function where the product flow is visible as assignments, `while True`, `if`, `break`, `continue`, exception paths, and `run_subpipeline(...)` for tiebreaker behavior (`.megaplan/initiatives/native-python-pipelines/research/native-python-pipelines-end-goal-megaplan-example.md:79`, `:82`, `:86`, `:97`, `:112`). The same doc explains why: no hand-written graph, phases are ordinary async functions, subloops are function calls, overrides are runtime interception, and contracts come from dataclasses/Pydantic models (`...end-goal-megaplan-example.md:119`-`:124`).

The true native-runtime spec then sharpened that into a compiled resumable Python state machine. It explicitly says a true runtime cannot resume a normal CPython coroutine after process death, so `@pipeline async def` is author-facing Python compiled once into a resumable native program; execution follows Python await/branch/loop semantics, while the runtime owns checkpoint labels, frame state, eventing, contracts, and graph projection (`.megaplan/initiatives/legacy-loose-briefs/research/native-python-runtime-full-spec-codex.md:5`). It requires checkpoints at every awaited phase, decision, and `run_subpipeline` (`...native-python-runtime-full-spec-codex.md:80`), frame-stack cursors for nested subpipelines (`:92`-`:105`), and child-frame semantics where child state does not mutate parent directly (`:181`-`:190`).

The later representation report translated that goal into Megaplan product semantics. It says "native" means more than Python-authored: loops are loops, gates are branches, tiebreakers are subworkflows, review rework is an explicit cycle, human intervention is a suspension point, and execution fanout is not hidden behind one opaque handler (`docs/arnold/megaplan-native-representation-report.md:5`). Its aspirational file includes subworkflows for critique, gate, tiebreaker, execute, and review, plus dynamic maps, retry, model routing, human gates, typed decisions, and explicit execute/review/rework loops (`docs/arnold/megaplan-native-representation-report.md:360`, `:432`, `:485`, `:520`, `:580`, `:613`-`:720`).

That representation report also identified missing substrate: dynamic runtime topology, loop expressiveness, source-level phase-call policy, and event/control-plane clarity (`docs/arnold/megaplan-native-representation-report.md:781`-`:831`). It recommended building in slices and keeping graph projection/compatibility during migration (`:832`-`:930`).

The current corrective epic deliberately narrows the immediate runtime target. It decides that canonical Megaplan should execute through `.pypeline` lowering into the existing DSL/manifest runtime for this epic, while the generator-style native runtime remains a future/runtime-pattern reference (`docs/arnold/megaplan-native-parity-corrective-plan.md:244`-`:253`). That narrowing is acceptable only if the source-level semantic authority is still real.

## What Actually Landed

The current canonical source is `arnold_pipelines/megaplan/workflows/workflow.pypeline`. It is more than the old minimal graph. It visibly contains:

- a `@workflow(id="megaplan", version="m4-phase3", policy=DEFAULT_POLICY)` function (`arnold_pipelines/megaplan/workflows/workflow.pypeline:388`);
- prep and plan calls (`:390`-`:391`);
- a bounded loop marker plus `while True` (`:393`-`:394`);
- critique fanout through `parallel_map(...)` (`:395`-`:401`);
- gate branches for proceed, iterate, retry, reprompt downgrade, tiebreaker, escalate, abort, suspend, blocked, and force-proceed (`:404`-`:754`);
- tiebreaker researcher/challenger/synthesis/decision calls (`:472`-`:488`);
- execute/review fanout/fanin and one explicit rework pass (`:406`-`:419`, `:423`-`:455`).

That is useful substrate and a better reviewer surface than a route table alone.

But the file is still not final semantic parity. It imports `AUTHORING_PREP`, `AUTHORING_PLAN`, `AUTHORING_GATE`, `AUTHORING_EXECUTE`, `AUTHORING_REVIEW`, `AUTHORING_REVISE`, `AUTHORING_OVERRIDE`, `CRITIQUE_PANEL_WORKFLOW`, `EXECUTE_BATCH_WORKFLOW`, `REVIEW_PANEL_WORKFLOW`, and tiebreaker components from `components.py` (`arnold_pipelines/megaplan/workflows/workflow.pypeline:14`-`:34`). It also embeds `DECLARED_STEP_INTERFACES` with handler refs and route bindings in the canonical source itself (`workflow.pypeline:81`-`:279`) and `DECLARED_WORKFLOW_TOPOLOGY_CONTRACTS` with route signals, target refs, fanout contracts, retry/reentry data, and reducer routes (`workflow.pypeline:281`-`:385`).

`planning.py` is a bridge/builder. It lowers `workflow.pypeline` (`arnold_pipelines/megaplan/workflows/planning.py:199`-`:201`), canonicalizes lowered step and route IDs through alias tables (`:110`-`:139`), derives route IDs by consulting declared route bindings or component metadata (`:247`-`:268`), reads declared handler bindings (`:356`-`:365`), reads declared route surfaces and topology contracts (`:398`-`:438`), then builds a DSL `Pipeline` from lowered steps and routes (`:695`-`:721`). This is exactly the load-bearing seam the corrective plan calls out: it is promising because it consumes lowered source, but still risky because it interleaves lowered source with component metadata and declared route bindings.

`components.py` remains a semantic carrier. It constructs `StepComponent` metadata with `route_bindings` and `handler_ref` (`arnold_pipelines/megaplan/workflows/components.py:293`-`:343`), declares runtime branch vocabularies (`:87`-`:112`), preserves/quarantines compatibility metadata (`:116`-`:223`), and contains rich policy/route surfaces for critique, gate, revise, tiebreaker, finalize, execute, review, override, model routing, and suspension. Examples:

- gate route groups, fallback route signals, severity policy, normalization policy, debt visibility, and reprompt policy (`components.py:1153`-`:1201`);
- revise loop exits, cap outcomes, termination policy, suspension, and delegated tiebreaker internals (`components.py:1257`-`:1333`);
- execute approval gates, fanout contract, retry/reentry, skip-review routes, and batch continuation/review handoff (`components.py:1673`-`:1781`);
- review fan-in contract, route groups, rework cycle, retry/cap behavior, blocked/advisory outcomes, force-proceed authority, human verification, and escalation (`components.py:593`-`:646`);
- concrete `AUTHORING_*` step components backed by handler refs (`components.py:2675`-`:2774`) and workflow carriers whose metadata mirrors `SOURCE_*` contracts (`components.py:2775`-`:2806`).

`_compatibility.py` is explicitly a compatibility shell. It projects the authored DSL pipeline into a neutral shell and attaches a `NativeProgram` (`arnold_pipelines/megaplan/_compatibility.py:1`-`:6`, `:101`-`:115`). Its native instructions are generated from DSL steps (`:173`-`:207`), and phase functions fall back to CLI command handlers when invoked under `__megaplan_auto_phase__` (`:216`-`:267`). This is a useful bridge, not semantic parity.

## Why The Epic Did Not Reach The Target

The root cause was a category error: previous closeout accepted representational parity as semantic parity.

The composition closeout report already knew handlers still owned semantics. It classified 9 of 11 handlers as "report-semantic owner" and only 2 as pure phase bodies (`docs/arnold/megaplan-composition-conformance-report.md:74`-`:88`). It also described expected failures as guards that would turn green as handlers were extracted (`docs/arnold/megaplan-composition-conformance-report.md:106`-`:110`). That was valid as intermediate status, but it could not prove final native semantics.

The final representation report then overclaimed. It states that 31 rows are implemented with source checkers, boundary records, receipts, semantic-health records, scenario hashes, and installed-package fingerprints (`docs/arnold/megaplan-native-representation-conformance-report.md:8`-`:13`). It lists every row as implemented (`:24`-`:56`) and says evidence keeps canonical `.pypeline` and named native workflow code as the only route authority (`:73`-`:76`). That is inconsistent with the current source shape, where `workflow.pypeline`, `planning.py`, and `components.py` still expose handler refs, route bindings, route surfaces, topology contracts, and compatibility projections.

The failure pattern was predictable:

1. **Component constants made the source look native.** A reviewer can see branches and loops in `workflow.pypeline`, but calls like `AUTHORING_GATE(...)`, reducers like `AUTHORING_EXECUTE`, and child carriers like `EXECUTE_BATCH_WORKFLOW` can still hide phase-local or product-level decisions behind imported metadata (`workflow.pypeline:14`-`:34`, `:390`-`:417`).

2. **`handler_ref` and `route_bindings` moved rather than disappeared.** The corrective plan says earlier tests rejected obvious wrapper tokens such as `SOURCE_`, `handler_ref`, and `route_bindings`, but the banned concepts moved out of the visible file instead of being eliminated as semantic carriers (`docs/arnold/megaplan-native-parity-corrective-plan.md:119`-`:127`). In the current tree they are still present in `workflow.pypeline`, `planning.py`, and `components.py`.

3. **Policy metadata became a route table substitute.** Declared policy is legitimate only when attached to source constructs and specific to a row. But current component policies include target refs, route groups, fanout contracts, reducer routes, topology overlays, and override dispatch. That is exactly the "policy as route table" anti-pattern the corrective plan warns against (`docs/arnold/megaplan-native-parity-corrective-plan.md:792`-`:797`).

4. **Projected-native proof can launder graph ownership.** `_compatibility.py` creates a `NativeProgram` from DSL steps and describes it as "Substrate proof only" (`arnold_pipelines/megaplan/_compatibility.py:197`-`:205`). Treating that projection as native-source authority would preserve graph/component ownership underneath while looking native at the top.

5. **Path-only and generated-ledger evidence can pass the wrong bar.** The corrective plan says the previous validator checked schema, row IDs, statuses, proof categories, path existence, and `.pypeline` suffix shape, but did not AST-inspect whether canonical source carried the required semantics (`docs/arnold/megaplan-native-parity-corrective-plan.md:140`-`:153`). That is the false pass.

6. **The checker was not yet the closure authority.** I ran the strict checker against current `workflow.pypeline`; it fails with 9 `AWF245_ROW_EVIDENCE_INSUFFICIENCY` diagnostics for S2/S3 rows. The targeted row-evidence test file also asserts this exact behavior (`tests/arnold/workflow/test_row_evidence_checker.py:255`-`:286`). But `check_workflow_file()` defaults `evidence=None`, while `check_workflow_source()` defaults to strict row evidence (`arnold/workflow/source_compiler.py:623`-`:650`, `:687`-`:690`). Final closure must force the strict path.

## Is The Current Corrective Epic A Good Fix?

Yes, mostly. It is aimed at the real root cause.

The North Star is crisp: final semantic authority is `workflow.pypeline`, imported native subworkflows, declared policies attached to named source constructs, and pure retained phase bodies (`.megaplan/initiatives/megaplan-native-parity-corrective/NORTHSTAR.md:5`-`:10`). It explicitly says final topology must not require `components.py`, route bindings, handler refs, manifest backend translation, compatibility projections, auto-drive next-step derivation, or CLI handlers (`NORTHSTAR.md:12`-`:15`).

The corrective plan also names the false pass directly. It says prior epics delivered substrate but did not finish the core product migration (`docs/arnold/megaplan-native-parity-corrective-plan.md:9`-`:17`), supersedes the old closeout claims (`:19`-`:26`), and defines an end state where a reviewer can understand the whole workflow from `workflow.pypeline` and named subworkflows without component tables, handler refs, route bindings, prompt metadata, manifest builders, or handler-local `current_state` / `next_step` mutation (`:30`-`:38`).

The milestone order is basically right:

- S1 combines semantic checker, typed outcomes, and a runtime-load-bearing builder slice before extraction (`.megaplan/initiatives/megaplan-native-parity-corrective/briefs/s1-checker-outcomes-builder-slice.md:5`-`:8`, `:28`-`:49`).
- S2 extracts the front-half loop and explicitly says gate/revise must be coupled (`s2-front-half-native-loop.md:5`-`:8`).
- S3 handles tiebreaker/replan as a true subworkflow (`s3-tiebreaker-replan-native.md:5`-`:7`).
- S4 and S5 address execute DAG/approval/resume and review/rework/finalize (`s4-execute-dag-approval-resume.md:5`-`:24`; `s5-review-rework-finalize.md:5`-`:26`).
- S6 collapses override, auto, and compatibility carriers (`s6-override-auto-compat-collapse.md:5`-`:35`).
- S7 requires generated conformance evidence, split-outcome scenarios, installed-package checks, handler-purity scans, compatibility quarantine checks, dead-delete mutation checks, and narrowing records (`s7-final-conformance-rollout.md:18`-`:41`).

The gates are directionally strong. The plan requires the current implementation to fail the new semantic parity checker (`docs/arnold/megaplan-native-parity-corrective-plan.md:304`-`:312`), forbids compatibility bridges as row evidence (`:313`-`:315`), and defines final gates including no component constants as product skeleton, no handler/manifest/trace/runtime-only semantics, machine-checked row evidence, old implementation as negative fixture, installed-package reconciliation, behavior parity, compatibility quarantine, and `build_pipeline()` no longer discarding lowered topology (`:648`-`:679`).

The weak spots:

1. **S1 is overloaded.** It combines checker, typed outcomes, handler interfaces, package evidence, dead-delete mutation, and a runtime slice. That is the right dependency set, but it is a lot for one sprint. If S1 closes partially, later extraction can restart the false pass.

2. **Checker strictness must be non-optional.** The API still has legacy source-only validation paths (`check_workflow_file(..., evidence=None)`) that do not enforce row evidence (`arnold/workflow/source_compiler.py:623`-`:650`, `:687`-`:690`). S7 says final ledger generation consumes checker evidence, but the implementation process must ensure all final closure commands use the strict checker plus installed-package source.

3. **Policy evidence can still be too generous.** The source compiler currently treats some S5 rows as implemented when review/finalize policy surfaces exist (`arnold/workflow/source_compiler.py:1783`-`:1874`). That may be acceptable for declared-policy rows, but only if the final checker also rejects policy objects that contain route tables or target refs masquerading as source semantics.

4. **Component collapse is scheduled late even though the docs say delete as you extract.** S6 absorbs global collapse, but S2-S5 must also delete or fence replaced carriers incrementally. The S2/S3/S4/S5 briefs do say this, but process gates must enforce it, not leave cleanup to S6.

5. **The `.pypeline` bridge is a deliberate narrowing from the ordinary async Python runtime.** The plan states the narrowing clearly (`docs/arnold/megaplan-native-parity-corrective-plan.md:244`-`:253`). That is acceptable for this epic, but final docs must not later describe it as having delivered the full native async runtime from the older spec.

## Most Important Corrections Before We Continue

1. **Make S1 unclosable unless strict checker execution is wired into the actual closeout path.** The current source must fail in checkout and installed-package mode before correction, and final rows must require fresh checker output with row IDs, spans, content hashes, and carrier classification.

2. **Add a hard negative fixture for the current canonical source shape, not only toy wrappers.** The fixture should include `AUTHORING_*`, `DECLARED_STEP_INTERFACES`, `DECLARED_WORKFLOW_TOPOLOGY_CONTRACTS`, component-backed `parallel_map`, policy route surfaces, and a compatibility shell projection.

3. **Strengthen policy-as-route-table rejection.** A declared policy may satisfy a row only when it is specific, attached to a named source construct, and not carrying target refs, reducer routes, route groups, fanout contracts, or override dispatch that should be visible source.

4. **Require dead-delete mutation per extraction sprint.** S2 must prove front-half component/handler carriers cannot route corrected behavior; S3 must prove old tiebreaker carriers cannot route; S4 must prove execute scheduling cannot come from handlers/auto; S5 must prove review/finalize routing cannot come from state fields or metadata.

5. **Quarantine `_compatibility.py` evidence explicitly.** Its `NativeProgram` projection is useful for runtime bridging but must never be accepted as proof of native-source semantic authority.

6. **Turn the final conformance report into a generated artifact from strict evidence only.** Manual status tables and prior generated reports should be input history, not proof.

7. **Document the runtime narrowing in every final closeout.** The corrective epic is not delivering the full ordinary async Python state-machine runtime. It is delivering source-authoritative `.pypeline` lowered into the existing DSL/manifest runtime.

8. **Add split-outcome behavior gates before broad rollout.** Happy-path smoke is insufficient. Required paths include prep suspend/resume, gate reprompt/downgrade, critical vs cosmetic cap exhaustion, tiebreaker replan/rejoin, execute partial resume, destructive approval denial/approval, review rework/cap, no-review terminal, force-proceed, and abort.

## Specific Evidence

- End-state ordinary Python target: `@pipeline("megaplan")` with phase awaits, loop, branches, tiebreaker `run_subpipeline`, finalize, execute, review (`.megaplan/initiatives/native-python-pipelines/research/native-python-pipelines-end-goal-megaplan-example.md:79`-`:114`).
- End-state properties: just Python, no hand-written graph, phase calls as checkpoints, subloops as function calls, overrides invisible, typed contracts (`...end-goal-megaplan-example.md:119`-`:124`).
- Native runtime spec: author-facing Python compiled into resumable state machine, not just graph executor (`.megaplan/initiatives/legacy-loose-briefs/research/native-python-runtime-full-spec-codex.md:5`).
- Native runtime migration strategy: decorators/graph projection first, native runtime later, Megaplan port later, flip default only after parity (`...native-python-runtime-full-spec-codex.md:270`-`:286`).
- Representation report target: native means product semantics visible in Python control flow (`docs/arnold/megaplan-native-representation-report.md:5`).
- Representation report missing constructs: dynamic map, loop expressiveness, source-level policy, override control-plane clarity (`docs/arnold/megaplan-native-representation-report.md:781`-`:831`).
- Corrective plan admits previous substrate was insufficient and goal is semantic parity (`docs/arnold/megaplan-native-parity-corrective-plan.md:9`-`:18`).
- Corrective plan end state forbids relying on component tables, handler refs, route bindings, manifest builders, or handler-local state mutation (`docs/arnold/megaplan-native-parity-corrective-plan.md:30`-`:38`).
- Corrective plan explicitly chooses `.pypeline` lowering into existing DSL/manifest runtime for this epic (`docs/arnold/megaplan-native-parity-corrective-plan.md:244`-`:257`).
- North Star says components, handlers, manifests, projections, auto-drive, and CLI are consumers/adapters, not semantic authority (`.megaplan/initiatives/megaplan-native-parity-corrective/NORTHSTAR.md:31`-`:34`).
- Current canonical source imports `AUTHORING_*` and workflow carriers from `components.py` (`arnold_pipelines/megaplan/workflows/workflow.pypeline:14`-`:34`).
- Current canonical source embeds handler refs and route bindings (`workflow.pypeline:81`-`:279`).
- Current canonical source embeds topology contracts with route signals, target refs, fanout/reducer contracts (`workflow.pypeline:281`-`:385`).
- Current `planning.py` lowers `workflow.pypeline` but canonicalizes via component metadata and route bindings (`arnold_pipelines/megaplan/workflows/planning.py:199`-`:201`, `:247`-`:268`, `:356`-`:365`, `:695`-`:721`).
- Current `components.py` still defines handler refs and route bindings on step components (`arnold_pipelines/megaplan/workflows/components.py:1954`-`:2047`, `:2190`-`:2309`, `:2675`-`:2774`).
- Current compatibility shell projects DSL into a `NativeProgram` and routes auto-phase execution through CLI command handlers (`arnold_pipelines/megaplan/_compatibility.py:101`-`:115`, `:173`-`:207`, `:216`-`:267`).
- Previous composition report identified 9 report-semantic handler owners (`docs/arnold/megaplan-composition-conformance-report.md:74`-`:88`).
- Previous final representation report nevertheless lists all 31 rows as implemented (`docs/arnold/megaplan-native-representation-conformance-report.md:24`-`:56`).
- Strict checker currently fails canonical source with 9 AWF245 row-evidence diagnostics for S2/S3. I ran:
  - `python - <<'PY' ... check_workflow_source(...) ... PY`
  - Result: `ok=False`, `diagnostic_count=9`, counts `{'AWF245_ROW_EVIDENCE_INSUFFICIENCY': 9}`.
- Targeted checker tests pass. I ran:
  - `pytest tests/arnold/workflow/test_row_evidence_checker.py -q`
  - Result: `25 passed in 0.07s`.

## Bottom Line For The Human

What happened: the earlier work built useful native-looking infrastructure and a readable `.pypeline`, then closed on the wrong proof. It proved that Megaplan could be represented, projected, hashed, and reported as native. It did not fully prove that Megaplan's real product control flow had moved out of handlers, component metadata, route tables, compatibility projections, auto-drive, and CLI dispatch.

What to do next: continue the corrective epic, but hold S1 to a very hard bar. The old/current skeleton must fail strict semantic checking in checkout and installed-package mode, and the first runtime slice must actually execute from lowered source rather than component-derived routing. Then each extraction sprint must delete or quarantine the carrier it replaces before it closes.

What not to confuse again: a `.pypeline` file, a `Pipeline.native_program`, a generated conformance ledger, a topology hash, a handler-purity inventory, or path-addressed evidence is not semantic parity by itself. Semantic parity means the source and named native subworkflows are enough to understand the workflow's decisions, loops, fanout/fanin, suspension, override behavior, execute/review/rework cycle, and checkpoint policy.
