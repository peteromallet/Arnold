# Megaplan Native Semantic Parity Corrective Master Plan

Generated: 2026-07-09

This is a corrective execution plan, not an implementation report. It treats
`docs/arnold/megaplan-native-representation-conformance-report.md` as a
historical false pass and makes closure depend on source-derived semantic
evidence, not path existence, topology hashes, compatibility projections, or
manual tables.

Outcome target: the product of this plan should make
`arnold_pipelines/megaplan/workflows/workflow.pypeline` and its imported named
native subworkflows match the semantic shape described by
`docs/arnold/megaplan-native-representation-report.md`, but with one important
qualification: the representation report is target history, not proof. The final
source should expose the same report-owned branches, loops, fanouts, joins,
caps, route labels, policies, and phase boundaries from source, while final
status is proven by strict checker evidence, carrier-scan reconciliation,
split-outcome baselines, and mutation gates.

Execution posture: use the hybrid lean plan. The goal is not to build a
self-defending governance system around the migration; the goal is to make false
semantic closure impossible while keeping the implementation focused on the
North Star. Controls that directly block the historical false-pass pattern stay
programmatic. Controls that mostly replace human attention become sprint review
questions, adversarial audit prompts, or halt-and-ask triggers.

Core controls that remain programmatic:

- The row registry must be complete. A structural carrier scan is authoritative
  for discovering route-authoritative hidden semantic carriers, and every such
  carrier maps to a row ID, is removed, or is explicitly fenced as inert
  compatibility. S7 fails on unmapped route-authoritative carriers.
- Golden split-outcome baselines are captured before extraction while the old
  path is still authoritative. Later parity and mutation gates compare against
  those frozen baselines.
- Rejection rules are structural for prohibited route authority, not token/name
  blacklists. They must catch the real forbidden classes: `handler_ref`,
  `route_bindings`, component route authority, manifest/backend route
  translation, auto next-step derivation, CLI dispatch, and compatibility
  projection evidence.
- Feature flags are temporary rollout scaffolding only. No sprint closes with
  dual route authority alive; rollback is by reverting the sprint.
- A current-shape negative fixture is permanent CI and pinned to diagnostic
  codes. Renamed/re-encoded adversarial fixtures are kept as a focused suite, not
  expanded into a fixture treadmill for every new spelling of a carrier.
- Baselines must be produced by a deterministic replay harness with hash-pinned
  canned worker payloads. Live model output is not admissible as a golden oracle.
- Baseline rewrites and route-authoritative exemptions are halt-and-ask events:
  they require a short reviewed record, but not a broad governance subsystem.
- Row-registry exemptions are bounded for route-authoritative carriers. S7 fails
  if any scheduled route-authoritative exemption remains open.
- The manifest backend remains an execution substrate for lowered source, but is
  quarantined as semantic evidence. "Quarantine" means it cannot prove source
  authority, not that the existing DSL/manifest runtime must be deleted in this
  epic.
- Dynamic `parallel_map` is not assumed to work merely because the compiler
  preserves `FanoutPolicy(mode="dynamic")`. S1b-1 must prove runtime support for
  dynamic `items_ref` fanout, suspension/reentry, and loop exit semantics before
  extraction sprints rely on those constructs.
- Golden baselines default to route/state/next-command/suspension assertions.
  Canonicalized artifact hashes are added only when artifact content is used as
  parity proof; raw hashes with timestamps, UUIDs, absolute paths, invocation ids,
  or worker session ids are never admissible.
- Headless split-outcome gates require an explicit control-injection API. A
  scenario that can only be driven through an interactive CLI is not CI evidence,
  but the API should cover only required split outcomes such as approval,
  resume-clarify, and tiebreaker decisions.
- Topology-changing sprints require a serialized-plan decision. If live suspended
  plans must survive, add migration fixtures; otherwise document and enforce a
  drain/quarantine window before rollout.
- Carrier scan reconciliation is tiered. Route-authoritative carriers block
  closeout unless mapped or removed; descriptive metadata must be classified and
  reviewable so exemption volume cannot hide live route authority. The tier
  boundary is a falsifiable claim: S1 and S7 must randomly sample seeded
  descriptive classifications, corrupt them, and prove the split-outcome
  scenario suite is unchanged. One sampled "descriptive" carrier that changes
  behavior invalidates the classification run.
- Installed-package mode must load `.pypeline` source through package resources
  from the installed artifact, not through checkout-relative paths. Run this as
  an S1 smoke and an S7 final gate, plus any sprint that changes packaging.
- North Star sense checks are independent audits, not executor self-reports. For
  explanation-style questions, a clean-context reviewer from a different
  principal/model family predicts behavior from source without reading the
  executor narrative, then verifies against run/generated evidence. Blocking
  severity is schema-assigned for route authority, baselines, exemptions, target
  narrowing, generated conformance authority, and live-plan topology/resume risk.
- The epic must run on a pinned Megaplan runner version. From S2 onward, this epic
  modifies the workflow code that executes it, so the chain driver is pinned at
  start and repinned only at explicit checkpoints after S1b-2 and S5. Each repin
  requires the auto-drive characterization corpus plus strict checker and
  North-Star-action smoke gates to pass.

Controls downgraded from mandatory infrastructure:

- Full worker/model I/O replay is not part of the base plan. Route/state replay
  with canned payloads is sufficient for this end-state unless a later sprint
  chooses artifact-level parity proof that needs deeper interception.
- Mutation evidence is plain behavior tests and dead-delete tests, not a separate
  mutation-artifact framework.
- Full package-wide carrier scans run in S1 and S7. Per-sprint scans are targeted
  to changed files plus a North Star review question about newly introduced route
  authority.
- Baseline amendment and exemption ledgers are simple reviewed records, not
  autonomous governance machinery.

Escalate back to the full apparatus if any sprint passes while a
route-authoritative carrier remains unmapped, a checker bypass is used for
closeout, a renamed/re-encoded carrier evades the focused structural suite,
deterministic scenarios flake or require baseline regeneration, old carriers
still affect behavior after dead-delete tests, installed-package behavior diverges
at S7, or live suspended plans must survive topology-changing rollout.

Expected size after the 48-report existing-work swarm and a three-Codex sprint
sizing review: keep the default at roughly 15 aggressive two-week sprints. The
swarm found substantial reusable scaffolding, especially in
native runtime support, execute scheduling, override/control, boundary evidence,
native goldens, installed-wheel smoke tests, and the old evidence generator. It
also confirmed that S0, the strict semantic checker hard bar, carrier
reconciliation, deterministic baseline freeze, strict installed-package checker,
and generated final conformance tooling are not already built. The swarm bought
reuse and confidence, not a collapse to a few sprints.

Research delta: see
`docs/arnold/megaplan-native-parity-existing-work-swarm-synthesis.md`. Treat it
as the current reuse map. It supersedes any assumption in this plan that S7 is
only final assembly or that execute/override are greenfield implementation
domains.

Sprint sizing delta: see
`docs/arnold/megaplan-native-semantic-parity-sprint-sizing-review.md`. The
current default is to keep the 15-sprint spine. Optional compression is limited
to S1c+S1d and S4a+S4b only when their prerequisite midpoint proofs are already
green; otherwise keep the proof boundaries separate. Split S0, S2b, S4b, S6b,
or S7 rather than forcing closure if their documented split triggers appear.

Plan adjustments from that swarm:

- Keep S0 to one aggressive sprint, but recognize it is greenfield runner and
  gate/revise plumbing built on existing gate-carry/revise feedback paths.
- Pull S7 tooling forward. S1a/S1b must create or generalize the scanner, row
  registry, strict checker, baseline freeze, scenario validation, and generated
  evidence scripts. S7 reruns and aggregates them; it must not invent them at the
  end.
- Treat native runtime dynamic fanout and suspension as mostly implemented at the
  generic native runtime layer. S1b-1/S1c must prove the Megaplan path and replace
  manifest/backend dispatch authority, not rebuild the whole native runtime.
- Reclassify execute DAG/scheduling as verify/harden/extract rather than
  greenfield build. The pure scheduling and execute policy functions are reusable,
  but legacy handler/auto route authority still needs dead-delete proof.
- Reclassify override/control as collapse/extract of an existing split-brain
  surface rather than greenfield build. `override_matrix.py`,
  `AuthorityRecord`, and `ControlTransition` are extraction inputs, not final
  source-authority proof.
- Split overloaded extraction domains into aggressive two-week sprints:
  prep/plan/critique; gate/revise; execute scheduling; execute approval/resume;
  review/rework; finalize/terminal projection; override/control; auto/manifest/
  compatibility.

## 1. Ground-Truth Status

The required DeepSeek gate passed. I launched one smoke test with:

```bash
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/launch_hermes_agent.py --toolsets="file,web,terminal" --query-file=.tmp/native-semantic-parity-master-plan/deepseek-smoke-brief.md --project-dir="$PWD" > .tmp/native-semantic-parity-master-plan/deepseek-smoke.out 2> .tmp/native-semantic-parity-master-plan/deepseek-smoke.err
```

The result cited `.megaplan/initiatives/megaplan-native-parity-corrective/NORTHSTAR.md:3`, and stderr showed the file read tool ran. Then I ran 5 DeepSeek audits through `fan.py`; `.tmp/native-semantic-parity-master-plan/results/_report.json` records `succeeded_count: 5`, `failed_count: 0`.

Current checker reality:

```bash
PYENV_VERSION=3.11.11 python - <<'PY'
from pathlib import Path
from collections import Counter
from arnold.workflow.source_compiler import check_workflow_file, check_workflow_source
p=Path('arnold_pipelines/megaplan/workflows/workflow.pypeline')
for name, result in [('file_default', check_workflow_file(p)), ('file_strict_empty', check_workflow_file(p, evidence=())), ('source_default', check_workflow_source(p.read_text(), source_path=p))]:
    print(name, result.ok, len(result.diagnostics), dict(Counter(d.code.value for d in result.diagnostics)))
PY
```

Output:

| Path | Result |
| --- | --- |
| `check_workflow_file(p)` | `ok=True`, `diagnostic_count=0` |
| `check_workflow_file(p, evidence=())` | `ok=False`, 9x `AWF245_ROW_EVIDENCE_INSUFFICIENCY` |
| `check_workflow_source(...)` | `ok=False`, 9x `AWF245_ROW_EVIDENCE_INSUFFICIENCY` |

The strict row IDs are:

| Row | Span | Carrier |
| --- | --- | --- |
| `s2.prep.1` | `workflow.pypeline:390` | `AUTHORING_PREP` |
| `s2.plan.1` | `workflow.pypeline:391` | `AUTHORING_PLAN` |
| `s2.critique.1` | `workflow.pypeline:395-401` | `AUTHORING_CRITIQUE` |
| `s2.gate.1` | `workflow.pypeline:402` | `AUTHORING_GATE` |
| `s2.revise.1` | `workflow.pypeline:442` | `AUTHORING_REVISE` |
| `s3.tiebreaker_researcher.1` | `workflow.pypeline:472-475` | `TIEBREAKER_RESEARCHER` |
| `s3.tiebreaker_challenger.1` | `workflow.pypeline:476-479` | `TIEBREAKER_CHALLENGER` |
| `s3.tiebreaker_synthesis.1` | `workflow.pypeline:480-484` | `TIEBREAKER_SYNTHESIS` |
| `s3.tiebreaker_decision.1` | `workflow.pypeline:485-488` | `TIEBREAKER_DECISION` |

`PYENV_VERSION=3.11.11 pytest tests/arnold/workflow/test_row_evidence_checker.py -q` passed: `25 passed in 0.05s`.

Discrepancies vs prior reports:

- The false conformance report lists all 31 rows as implemented (`docs/arnold/megaplan-native-representation-conformance-report.md:26-56`), but strict source checking fails current canonical source with 9 `AWF245` diagnostics.
- The repository has a closure bypass: `check_workflow_file` defaults `evidence=None` (`arnold/workflow/source_compiler.py:623-638`), while `check_workflow_source` defaults strict `evidence=()` (`arnold/workflow/source_compiler.py:642-649`). `check_workflow_source` only calls `_row_evidence_diagnostics` when `evidence is not None` (`arnold/workflow/source_compiler.py:687-690`).
- Current CLI source commands route through `check_workflow_file(source_path)` without evidence in `arnold/cli/workflow.py:207-208`, `:433-438`, `:513-515`, and `:676-677`, so they do not enforce AWF245.
- The mission referred to `workflows/_compatibility.py`; the repo path is `arnold_pipelines/megaplan/_compatibility.py`.

Remaining semantic carriers verified in current source:

- `workflow.pypeline` imports `AUTHORING_*` and child workflow constants from `components.py` (`workflow.pypeline:14-34`), declares `handler_ref` and `route_bindings` in canonical source (`workflow.pypeline:81-280`), and declares route-heavy topology contracts (`workflow.pypeline:281-383`).
- `planning.py` still merges lowered source with component metadata and route bindings: `_route_id_for_lowered_route` consults declared/component `route_bindings` (`planning.py:247-268`), `_metadata_for_step` preserves `handler_ref`, `policy_refs`, and `override_actions` (`planning.py:583-598`), and `build_pipeline()` still builds canonical DSL steps/routes from component-backed structures (`planning.py:695-716`).
- `components.py` contains policy surfaces that are route tables in disguise: gate route groups and reprompt policy (`components.py:1154-1237`), revise termination/reentry policy (`components.py:1239-1336`), tiebreaker decision routes (`components.py:1392-1399`, `:2546-2550`), execute fanout/retry/route surfaces (`components.py:1694-1781`), review reducer routes (`components.py:2664-2669`), and override dispatch surfaces (`components.py:399-433`, `:1603-1621`).
- `_compatibility.py` projects DSL routes into a `NativeProgram` (`arnold_pipelines/megaplan/_compatibility.py:101-115`, `:173-207`) and can run phases through CLI `COMMAND_HANDLERS` (`_compatibility.py:235-267`).
- The manifest backend remains a route brain: it maps handler response fields to branch edge ids (`runtime/manifest_backend.py:227-322`) and imports component route bindings for `route_signal` resolution (`runtime/manifest_backend.py:173-189`).
- `route_dispatch.py` falls back to component route bindings outside front-half lowered routes (`arnold_pipelines/megaplan/route_dispatch.py:26-43`).
- Handler/execute state mutation still exists in `handlers/execute.py`, `handlers/finalize.py`, `handlers/gate.py`, `handlers/override.py`, `handlers/plan.py`, `handlers/review.py`, `execute/batch.py`, and `execute/step_edit.py` by AST scan for `current_state`, `next_step`, and `resume_cursor`.
- The historical handler purity inventory still classifies 9 of 11 Megaplan handlers as report-semantic owners and 2 as pure phase bodies (`docs/arnold/megaplan-composition-conformance-report.md:74-88`).

Runtime narrowing: this plan delivers source-authoritative `.pypeline` lowered into the existing DSL/manifest runtime. It does not deliver the full ordinary-async-Python resumable runtime described in `.megaplan/initiatives/legacy-loose-briefs/research/native-python-runtime-full-spec-codex.md:5-16` or the final ordinary-Python example in `.megaplan/initiatives/native-python-pipelines/research/native-python-pipelines-end-goal-megaplan-example.md:3-10`. Any closeout artifact that claims full ordinary async Python runtime parity fails S1/S7.

## 2. Verified Subagent Synthesis

Five DeepSeek audits completed successfully. I spot-checked their claims against source and used only claims with file:line support.

- SA1 found the closure bypass: `check_workflow_file` can skip row evidence, and the CLI uses it. Verified at `source_compiler.py:623-690` and `arnold/cli/workflow.py:207-208`, `:433-438`, `:513-515`, `:676-677`.
- SA1 also found that S5 review/finalize rows are not in `_row_evidence_diagnostics`; `_row_evidence_diagnostics` calls `_implemented_front_half_rows` (`source_compiler.py:722-726`), while S5 rows live in `_implemented_s5_boundary_rows` (`source_compiler.py:1783-1868`). S5 currently passes on policy-surface existence checks such as `Mapping` values on `REVIEW_POLICY`/`FINALIZE_POLICY` (`source_compiler.py:1189-1220`, `:1812-1868`).
- SA2 found front-half semantics concentrated in `handlers/gate.py` and `components.py`. Verified examples: debt recording in `handlers/gate.py:77-133`, no-progress tracking and termination in `handlers/gate.py:414-677`, reprompt/downgrade in `handlers/gate.py:993-1097`, gate route groups in `components.py:1154-1158`, and revise reentries in `components.py:1276-1279`.
- SA3 found tiebreaker source is still a mix of child workflow metadata and state reset. Verified tiebreaker topology/decision routes in `workflow.pypeline:281-300` and `components.py:2546-2550`; replan state clearing in `arnold_pipelines/megaplan/replan_state.py:1-38`.
- SA3 found execute route semantics still owned by execute handlers/policy: approval gate in `handlers/execute.py:322-345`, approval policy in `execute/policy.py:311-357`, fresh-session force in `handlers/execute.py:423-445`, execute route surfaces in `components.py:1740-1781`, and batch loop semantics in `execute/batch.py`.
- SA4 found review/override/auto remain route brains: review cap behavior in `handlers/review.py`, no-review terminal in `execute/policy.py:360-408` and `handlers/execute.py:562-572`, override matrix rows in `workflows/override_matrix.py:40-149`, auto phase command translation in `auto.py:1198-1245`, and auto escalation/force-proceed paths in `auto.py`.
- SA5 found evidence infrastructure exists but is not sufficient: generated evidence bundle builder (`scripts/generate_native_representation_evidence.py:1607-1712`), scenario hash builder (`:1397-1604`), installed-package fingerprints (`:916-946`), handler-purity scans (`:1018-1104`), compatibility quarantine (`:1156-1191`), and dead-delete checks (`:1194-1225`). Missing pieces are current-shape negative fixture, policy-as-route-table rejection, strict checker closure authority, per-sprint mutation gates, and row-to-scenario coverage cross-check.

Ten question-specific DeepSeek audits were then run with one subagent per
question under `.tmp/native-semantic-parity-question-audit/`. Nine returned
usable reports in the fan-out; Q1 was rerun separately because its first output
was incomplete. The disagreements with the plan are:

- Q1: `parallel_map` lowers to `Step(kind="parallel_map")` plus
  `FanoutPolicy(mode="dynamic")`, but the neutral router only fans out from
  static `width`; `items_ref` is not resolved at runtime. S1b-1 therefore needs a
  compiler/runtime substrate gate before S2-S5 depend on dynamic fanout.
- Q2: worker/model invocation paths are heterogeneous; the current auto-drive
  corpus replays route/state traces, not model I/O. Baselines should start as
  deterministic route/state assertions unless a separate invocation interceptor
  lands.
- Q3: checker rejection is currently token/name-oriented and the row registry
  lives in code, which confirms the need for the S1a data registry and structural
  rejection work already listed here.
- Q4: `handler_ref` is not required by the neutral Step/runtime protocol, but
  Megaplan's manifest backend still dispatches through hard-coded node ids.
  S1b-1 must prove substrate dispatch and S1b-2 must prove one builder edge
  without semantic dependence on
  `handler_ref`.
- Q5: replay cursors include manifest hashes; topology changes can quarantine
  suspended plans without a migration or drain policy. Each topology-changing
  sprint needs a pre-sprint serialized fixture resumed on post-sprint code, or a
  deliberate drain/quarantine rollout decision.
- Q6: no external pipeline import of Megaplan `components.py` was found, but
  `arnold/workflow/source_compiler.py` contains string couplings to component
  export names. S1a/S2-S6 need a cross-package coupling ledger so checker
  strings move in lockstep with deleted component exports.
- Q7: resume-clarify has a programmatic control path, but destructive approval
  denial/approval and tiebreaker decisions do not. S1a needs headless
  control-injection actions before those scenarios can be CI gates.
- Q8: artifact/state outputs contain timestamps, UUIDs, absolute paths,
  invocation ids, snapshot ids, and worker session ids. Baseline hash gates need
  a canonicalizer and a pinned canonicalizer version.
- Q9: package-wide carrier heuristics find hundreds of route-shaped candidates,
  not about 30. S1a must tier carriers into route-authoritative vs descriptive
  metadata before row reconciliation is realistic.
- Q10: package data config appears to include `.pypeline` files, but no strict
  installed-package checker path currently exists. S1a must implement it with
  `importlib.resources` and a smoke test against an installed artifact.

## 3. Milestone Plan

Execution should use this aggressive two-week sprint spine. The detailed
milestone sections below provide scope and gates; where a section is broader than
one sprint, split it according to this spine rather than running it as one large
milestone:

1. S0 - Runner Pinning and North Star Action Plumbing.
2. S1a - Checker Authority, Row Registry, Carrier Scan, Current-Shape Rejection.
3. S1b - Deterministic Evidence Substrate and Baseline Freeze.
4. S1c - Runtime Substrate and Manifest Source Dispatch Proof.
5. S1d - Typed Outcomes and First Builder Edge.
6. S2a - Prep, Plan, Critique Native Authority.
7. S2b - Gate and Revise Native Loop.
8. S3 - Tiebreaker and Replan Native Flow.
9. S4a - Execute DAG and Scheduling Hardening.
10. S4b - Execute Approval, Blocked Retry, Fresh Session, Partial Resume.
11. S5a - Review Fanout, Rework, Caps.
12. S5b - Finalize Fallback and Terminal Projection.
13. S6a - Override and Human Control Surface Collapse.
14. S6b - Auto, Manifest Backend, Compatibility Quarantine.
15. S7 - Final Generated Conformance and Rollout.

Ownership correction: S1a owns checker authority, row registry, carrier scan,
classification, reconciliation, and structural rejection. S1b owns replay,
headless control injection, scenarios, and baseline freeze. The detailed sprint
briefs must preserve that separation; S1a is not a credible two-week sprint if
replay/baseline implementation remains inside it.

Every sprint brief and sprint closeout must include a `Sprint Review / North Star
Sense Check` section immediately before `Do Not Close If`. These answers are not
substitutes for the core programmatic gates above; they replace the broad
governance apparatus that would otherwise try to automate every exception.
Review answers must name file paths and rows. Any `no`, `unclear`, or
`not applicable` answer creates an explicit action item before closeout, or a
human-reviewed halt-and-ask decision. For question 1 and any other
source-explanation test, the answer must be produced by a clean-context reviewer
agent that has not read the executor's closeout narrative. It predicts behavior
from source alone, then verifies against run/generated evidence and records any
divergence.

Required sprint review questions:

1. For every row this sprint claims, can a reviewer understand the
   branch/loop/fanout/join/suspension/retry/route from `workflow.pypeline`, a
   named native subworkflow, an attached declared policy, or a typed pure phase
   body without reading `components.py`, handler-local state transitions,
   manifest maps, auto-drive, CLI handlers, or compatibility projections?
2. Which old carriers did this sprint replace, and are they deleted, fenced as
   inert compatibility, or proven unable to route behavior by a dead-delete test?
3. Are all behavior claims covered by split-outcome scenarios, including
   failure/alternate branches, not just happy path?
4. Did the sprint introduce any new route-authoritative carrier outside
   canonical source or named native subworkflows?
5. Does `build_pipeline()` and runtime behavior consume lowered source for the
   changed slice, or reconstruct semantics from component metadata?
6. Are any feature flags, fallback dispatches, policy route tables, string label
   maps, or control handlers now a second route brain?
7. If a target was narrowed, is there both a checker rule blocking the old
   false-pass pattern and a behavior scenario proving the narrowed path cannot
   smuggle routing?
8. Does the sprint preserve public state names, route labels, artifact names,
   resume semantics, and installed-package behavior, or explicitly document a
   rollout/drain decision?

Default action mapping:

- Missing source authority: add or amend source constructs, then rerun strict row
  evidence.
- Old carrier still route-capable: add a dead-delete behavior test or delete/fence
  the carrier before closeout.
- Scenario gap: add a split-outcome scenario before claiming parity for that row.
- New route-authoritative carrier: move authority into source or add it to row
  registry reconciliation as a blocking carrier.
- Dual route brain: remove the fallback/feature flag before closeout, or halt for
  an explicit rollout decision.
- Packaging or live-plan uncertainty: defer to S7 installed-package proof unless
  packaging changed, and choose either migration fixture or drain/quarantine for
  live suspended plans.

Megaplan revise-stage implementation note:

- North Star sense checks should enter revise as structured
  `north_star_actions` carried by `gate.json`/`gate_carry.json`, not as prose in
  critique text. In the current Megaplan implementation, revise is handled by
  `arnold_pipelines/megaplan/orchestration/critique_runtime.py` and prompted via
  `arnold_pipelines/megaplan/prompts/critique.py`; it consumes gate summary and
  unresolved flags, while finalize can synthesize an iterate gate and carry
  feedback back to revise.
- Minimal action schema:

```json
{
  "id": "NS-ACT-001",
  "source": {"phase": "critique|gate|finalize|review", "artifact": "gate.json", "ref": "flag-or-check-id"},
  "north_star_ref": "NORTHSTAR.md:31-34",
  "finding": "Plan allows handler refs to remain semantic authority.",
  "severity": "blocking|advisory",
  "severity_source": "schema|reviewer",
  "action_type": "add_plan_item|add_exit_gate|add_scenario_test|add_checker_row|add_dead_delete_test|add_human_halt|escalate_robustness|reject_closeout",
  "target": "phase/step/milestone or null",
  "required_change": "Concrete change revise must make or halt on.",
  "acceptance_evidence": ["test/check/artifact expected"],
  "halt_if_unmappable": true
}
```

- Revise applies actions by rewriting the plan, not by recording a narrative
  answer. `add_plan_item` adds a numbered step with files and evidence;
  `add_exit_gate` adds a must-pass gate with concrete `requires`;
  `add_scenario_test` widens test blast radius; `add_checker_row` adds checker
  implementation and diagnostic/command criteria; `add_dead_delete_test` adds
  deletion/fencing plus behavior proof; `reject_closeout` becomes a must-pass
  closeout gate enforced later by review/finalize.
- Revise must refuse to silently rewrite `add_human_halt`, unmappable blocking
  actions, route-authoritative exemptions, baseline rewrites, target narrowing,
  and live-plan topology decisions. Those become blocked/halt outcomes or gate
  escalation, not vague plan text.
- Blocking North Star actions count like blocking correctness/security flags for
  loop caps and no-progress termination. They cannot be force-proceeded through
  the cosmetic/low-risk branch.
- Severity is schema-assigned for dangerous categories. Findings touching route
  authority, baselines, row/carrier exemptions, target narrowing, generated
  conformance authority, or live-plan topology/resume risk are always
  `blocking` with `severity_source: "schema"`; the answering agent cannot
  downgrade them to advisory.
- Smallest useful Make-A-Plan slice: add `north_star_actions` to gate/carry
  schema; render them in the revise prompt; add `north_star_actions_addressed`
  to `revise.json`; add a pre-worker guard for human-halt/unmappable blocking
  actions; test schema validation, prompt rendering, halt behavior, plan metadata
  output, and gate cap handling for unresolved blocking actions.

### S0 - Runner Pinning and North Star Action Plumbing

Scope:

- Land the `north_star_actions` plumbing in the pinned runner before S1a starts:
  gate/carry schema, revise prompt rendering, `north_star_actions_addressed` in
  `revise.json`, pre-worker halt guard for human-halt/unmappable blocking
  actions, and review blocking for unresolved closeout-critical actions.
- Define `north_star_critical` as an explicit chain/milestone schema field.
  Reject `north_star_critical: true` with `bare` or `light` robustness rather
  than silently upgrading robustness.
- Teach revise to explicitly load `north_star_actions` from `gate_carry.json`
  first and `gate.json` as fallback; the carry artifact is not currently a
  guaranteed revise input.
- Add post-worker revise validation: `north_star_actions_addressed` claims must
  point to concrete plan refs and action-specific structural markers. Prose-only
  "handled" claims fail.
- Add finalize/review enforcement: finalize lowers North Star obligations into
  executable tasks/user actions/checks without overloading task `sense_checks`;
  review and transition policy block unresolved `reject_closeout` or
  closeout-critical actions.
- Enforce independent clean-context answerers for explanation-style North Star
  questions. The auditor predicts behavior from source alone, then verifies
  against generated/run evidence. The executor's closeout narrative is not
  admissible as the answer.
- Make severity schema-assigned for dangerous categories: route authority,
  baseline rewrites, row/carrier exemptions, target narrowing, generated
  conformance authority, and live-plan topology/resume risk are always blocking.
- Pin the Megaplan runner used to drive the epic. Record commit SHA/package
  fingerprint, profile, robustness, and auto-drive corpus version.

Exit gates:

- `PYENV_VERSION=3.11.11 pytest tests/arnold_pipelines/megaplan/test_north_star_actions_gate_revise.py tests/arnold_pipelines/megaplan/test_north_star_actions_review_blocking.py -q`
- `PYENV_VERSION=3.11.11 pytest tests/arnold_pipelines/megaplan/test_north_star_clean_context_auditor.py tests/arnold_pipelines/megaplan/test_north_star_severity_schema.py -q`
- `PYENV_VERSION=3.11.11 pytest tests/arnold_pipelines/megaplan/test_north_star_critical_robustness.py tests/arnold_pipelines/megaplan/test_north_star_revise_post_validation.py -q`
- `PYENV_VERSION=3.11.11 python scripts/pin_megaplan_runner.py --out artifacts/native-semantic-parity/runner-pin-s0.json`
- `PYENV_VERSION=3.11.11 python scripts/check_megaplan_runner_pin.py --pin artifacts/native-semantic-parity/runner-pin-s0.json --auto-drive-corpus tests/characterization/auto_drive_corpus`
- Two cheap canary audits must run against seeded North Star defects. If the
  clean-context auditor passes a canary, S0 fails and the methodology halts.

Evidence spec:

- Runner pin record with commit/package fingerprint and auto-drive corpus hash.
- North Star action schema tests and canary audit results.
- Example `gate.json`/`gate_carry.json` carrying a blocking North Star action
  into revise, plus `revise.json` proving the action was addressed or halted.

Deletion/quarantine:

- Prose-only North Star answers cannot satisfy a blocking sense check.
- Executor-authored closeout narrative cannot be the sole answer for
  source-explanation questions.

Rollback:

- S0 rolls back as a runner/tooling change before any semantic extraction starts.

Parity checks:

- Existing gate/revise/review behavior remains unchanged when no explicit North
  Star questions are present.

### S1a - Checker Authority Hard Bar

Scope:

- Make strict semantic checking the sole closeout route before any extraction closes.
- Produce a canonical semantic row registry reconciled against a structural AST
  carrier scan for route-authoritative carriers. The S1/S7 scan must default to
  package-wide coverage of
  `arnold_pipelines/megaplan` plus relevant `arnold/workflow`, `arnold/runtime`,
  and `arnold/conformance` surfaces, with explicit exclusions rather than narrow
  inclusions. Every exclusion requires the same dated-exemption treatment as an
  unmapped route-authoritative carrier. Every route-authoritative carrier,
  including `handler_ref`, route
  bindings, state mutation sites, policy route surfaces, dispatch tables, reducer
  routes, fanout contracts, and route-like mapping literals, must map to either a
  row ID, deletion/fencing proof, or an explicit dated exemption with owner,
  category, date, and reason.
  The scan must also classify each candidate as route-authoritative,
  evidence-authoritative, compatibility metadata, or descriptive metadata before
  row reconciliation can pass.
- Required current-shape negative fixture must mirror `workflow.pypeline:14-34`, `:81-280`, `:281-383`, `:390-540`; `planning.py:247-268`, `:583-716`; `components.py:1154-1781`, `:2664-2669`; `_compatibility.py:101-115`, `:173-207`.
- Add checker rules that reject `AUTHORING_*` imports as row authority, canonical-source `handler_ref`, canonical-source `route_bindings`, compatibility `NativeProgram` projections, and policy-as-route-table constructs.
- Add structural rejection rules for renamed or re-encoded carriers: route-table
  shaped dict/list literals, mapping values that resolve to known state/step/route
  identifiers, imported component callables used as route authority, reducer/fanout
  topology encoded under innocuous names, and policy objects whose values can
  determine branch targets. This is a focused adversarial suite for the known
  carrier classes, not an unbounded fixture treadmill.
- Build the deterministic replay harness used for all split-outcome and
  dead-delete gates. The first admissible baseline layer is deterministic state transition,
  route label, next-command, suspension/terminal status, and canonical artifact
  comparison. Do not build full worker/model I/O replay unless a later sprint
  explicitly chooses it as an escalation.
- Build the baseline canonicalizer only before artifact hashes are accepted as
  parity proof. If used, it must
  normalize timestamps, UUIDs, absolute paths, invocation ids, snapshot ids,
  model/session ids, and generated-at/provenance fields, and publish a
  canonicalizer version in every baseline record.
- Add headless control-injection actions for destructive approval denial,
  destructive approval approval, tiebreaker proceed/iterate/escalate, and any
  other split outcome that currently requires interactive CLI steering.
- Implement strict installed-package mode by loading `workflow.pypeline` and
  named subworkflows through `importlib.resources.files(...)` from the installed
  `arnold_pipelines` package, then feeding the loaded source through the same
  strict checker path used in checkout mode. S1a requires a smoke proof that the
  path exists; S7 is the full installed-package semantic gate.
- Create a cross-package coupling ledger for source compiler references to
  Megaplan component export names. Component deletion sprints must update or
  retire those checker couplings in the same change.
- Author `docs/arnold/megaplan-native-representation-scenarios.yaml` with the
  full split-outcome inventory and a completeness check against the required
  scenario list.
- Capture staged pre-extraction golden baselines while legacy carriers still own
  behavior. S1a does not need to capture every later sprint's full workflow
  baseline before it closes, but sprint N extraction may not begin until sprint
  N's baselines were frozen while legacy routing remained authoritative for those
  flows.

Exit gates:

- `PYENV_VERSION=3.11.11 python scripts/check_megaplan_native_semantic_parity.py --source arnold_pipelines/megaplan/workflows/workflow.pypeline --strict --require-row-evidence --mode checkout --out .tmp/native-semantic-parity-master-plan/s1-current-checkout.json` must fail current source before correction, with row IDs, spans, hashes, and carrier classification.
- Same command with `--mode installed-package --smoke` must prove the checker
  loads source from the installed artifact rather than checkout paths. Full
  installed-package semantic failure/pass is required at S7 and any sprint that
  changes packaging.
- `PYENV_VERSION=3.11.11 python scripts/scan_megaplan_semantic_carriers.py --roots arnold_pipelines/megaplan arnold/workflow arnold/runtime arnold/conformance --exclude-from artifacts/native-semantic-parity/carrier-scan-exclusions.yaml --out artifacts/native-semantic-parity/carrier-scan.json`
- `PYENV_VERSION=3.11.11 python scripts/classify_megaplan_semantic_carriers.py --carrier-scan artifacts/native-semantic-parity/carrier-scan.json --out artifacts/native-semantic-parity/carrier-tier-classification.json` must identify route-authoritative carriers separately from descriptive metadata.
- `PYENV_VERSION=3.11.11 python scripts/validate_megaplan_carrier_tier_boundary.py --carrier-tier artifacts/native-semantic-parity/carrier-tier-classification.json --sample-seed artifacts/native-semantic-parity/carrier-tier-sample-seed.txt --sample-size 20 --scenarios docs/arnold/megaplan-native-representation-scenarios.yaml --out artifacts/native-semantic-parity/carrier-tier-boundary-validation.json` corrupts a seeded sample of descriptive carriers and fails the whole classification run if any sampled carrier changes behavior.
- `PYENV_VERSION=3.11.11 python scripts/reconcile_megaplan_semantic_rows.py --carrier-scan artifacts/native-semantic-parity/carrier-scan.json --row-registry arnold/workflow/megaplan_semantic_rows.yaml --out artifacts/native-semantic-parity/row-registry-reconciliation.json` must fail if any carrier is unmapped and unexempted.
- `PYENV_VERSION=3.11.11 pytest tests/arnold/workflow/test_megaplan_row_registry_completeness.py tests/arnold/workflow/test_megaplan_checker_structural_rejection.py -q`
- `PYENV_VERSION=3.11.11 pytest tests/arnold/workflow/test_row_evidence_checker.py tests/arnold/workflow/test_megaplan_native_semantic_checker_authority.py -q` must pass.
- `PYENV_VERSION=3.11.11 python scripts/validate_megaplan_split_outcome_scenarios.py --scenarios docs/arnold/megaplan-native-representation-scenarios.yaml --required docs/arnold/megaplan-native-required-split-outcomes.yaml`
- `PYENV_VERSION=3.11.11 python scripts/validate_megaplan_replay_harness.py --fixtures tests/fixtures/megaplan/replay --out artifacts/native-semantic-parity/replay-harness.json`
- `PYENV_VERSION=3.11.11 python scripts/validate_megaplan_baseline_canonicalizer.py --fixtures tests/fixtures/megaplan/replay --out artifacts/native-semantic-parity/baseline-canonicalizer.json` is required only if baseline artifacts include content hashes beyond route/state/next-command/suspension assertions.
- `PYENV_VERSION=3.11.11 pytest tests/arnold_pipelines/megaplan/test_control_injection_headless.py tests/arnold_pipelines/megaplan/test_installed_package_strict_source_loading.py -q`
- `PYENV_VERSION=3.11.11 python scripts/capture_megaplan_split_outcome_baselines.py --scenarios docs/arnold/megaplan-native-representation-scenarios.yaml --scope s1b,s2 --harness tests/fixtures/megaplan/replay --out artifacts/native-semantic-parity/baselines/pre-extraction --freeze` captures the first frozen legacy behavior corpus before extraction.
- `PYENV_VERSION=3.11.11 python scripts/check_megaplan_baseline_freeze.py --baselines artifacts/native-semantic-parity/baselines/pre-extraction --amendments artifacts/native-semantic-parity/baseline-amendments.yaml --mode verify`
- `PYENV_VERSION=3.11.11 python scripts/check_megaplan_native_semantic_parity.py --fixture tests/fixtures/workflow_authoring/megaplan/current_false_pass_shape.py --strict --expect-diagnostic AWF245_ROW_EVIDENCE_INSUFFICIENCY --expect-diagnostic AWF253_PROHIBITED_SEMANTIC_CARRIER` must fail forever with the specified diagnostic codes. S1a must allocate `AWF253_PROHIBITED_SEMANTIC_CARRIER` in `arnold/workflow/diagnostics.py` and its diagnostic spec before pinned fixture tests are written.
- A focused renamed/re-encoded adversarial fixture suite under
  `tests/fixtures/workflow_authoring/megaplan/renamed_carrier_evasion/` must fail
  with structural carrier diagnostics, not merely `ok=False`.
- `PYENV_VERSION=3.11.11 python scripts/validate_megaplan_runtime_narrowing.py --docs docs/arnold/megaplan-native-runtime-narrowing-contract.md docs/arnold/megaplan-native-semantic-parity-master-plan.md --forbid-full-runtime-overclaim`
- All final/initiative closeout commands must call this strict command, not `check_workflow_file(..., evidence=None)`.

Evidence spec:

- Generated JSON only from the strict checker: each row has `row_id`, `construct_type`, `source_span`, `source_sha256`, `carrier_classification`, `negative_fixture_ids`, `installed_package_fingerprint`, and `checker_version`.
- `row-registry-reconciliation.json` records every route-authoritative carrier,
  row mapping/deletion/fencing proof or exemption, carrier kind, source span,
  source hash, exemption owner, exemption category, date, and reason. The
  route-authoritative registry cannot shrink without a reconciliation diff.
  Exemption categories are `compat-metadata-inert`,
  `scheduled-for-sprint-N`, and `out-of-scope-with-justification`.
- `carrier-tier-classification.json` records route-authoritative,
  evidence-authoritative, compatibility-metadata, and descriptive-metadata
  classifications. Route-authoritative carriers cannot be cleared by a generic
  exemption. `carrier-tier-boundary-validation.json` records the seeded
  descriptive sample, corruption method, scenario command, and result; one
  behavior-changing sample invalidates the classification run.
- Golden baseline artifacts are immutable inputs to later parity gates and include
  command, fixture hash, serialized state hash, artifacts hash, route label,
  next-command/auto-drive observation, replay fixture hashes, and expected
  terminal/suspension outcome. Raw artifacts are hashed only if canonicalizer
  normalization is active, and the canonicalizer version is part of the frozen
  record. Baseline amendment records are short reviewed records with dated
  justification, reviewer, old/new hashes, and affected rows.
- No manually authored conformance table can set row status.

Deletion/quarantine:

- `check_workflow_file(..., evidence=None)` may remain only as legacy source-shape validation and must be named non-semantic in docs/tests.
- The four current CLI bypass call sites, `arnold/cli/workflow.py:207-208`,
  `:433-438`, `:513-515`, and `:676-677`, must be listed in the S1a
  deletion/quarantine ledger and either routed through strict closeout or renamed
  as explicitly non-semantic source-shape checks.
- `_compatibility.py` `NativeProgram` must be marked prohibited evidence by checker diagnostic.

Rollback:

- Revert S1a checker wiring as one slice. Because no extraction has occurred yet, rollback restores old validation behavior without stranding native source changes.

Parity checks:

- Current state names, artifact names, route labels, auto-drive labels, override/resume commands remain unchanged per `_core/workflow_data.py`; S1a only changes closure evidence authority.

### S1b-1 - Runtime Substrate Proof

Scope:

- Prove compiler/runtime substrate readiness for constructs later sprints rely on:
  dynamic `parallel_map` over runtime `items_ref`, suspension/reentry fixtures, and
  loop exits. If typed loop exits are required, implement and test them here
  before S2-S5 use them.
- Prove manifest backend phase dispatch can be derived from lowered source
  constructs or inert compatibility metadata, without `handler_ref` as route
  authority.
- Keep this as substrate work only. Do not extract Megaplan semantics in this
  sprint; the point is to remove hidden prerequisites before builder/extraction
  pressure starts.

Exit gates:

- `PYENV_VERSION=3.11.11 pytest tests/arnold_pipelines/megaplan/test_native_runtime_dynamic_fanout.py tests/arnold_pipelines/megaplan/test_native_runtime_suspension_reentry.py tests/arnold_pipelines/megaplan/test_manifest_backend_source_dispatch.py -q`
- `PYENV_VERSION=3.11.11 pytest tests/arnold_pipelines/megaplan/test_native_runtime_loop_exits.py tests/arnold_pipelines/megaplan/test_runtime_items_ref_resolution.py -q`
- `PYENV_VERSION=3.11.11 pytest tests/arnold/workflow/test_row_evidence_checker.py tests/arnold/workflow/test_megaplan_checker_structural_rejection.py tests/arnold/workflow/test_megaplan_row_registry_completeness.py -q`
- If S1b-1 changes topology, a pre-S1b-1 serialized replay cursor fixture must resume
  or intentionally quarantine on post-S1b-1 code according to a documented
  migration/drain policy.

Evidence spec:

- Runtime fixture evidence for dynamic fanout, suspension/reentry, loop exits,
  and source-derived dispatch. Evidence must show runtime behavior, not just
  lowered metadata.

Deletion/quarantine:

- `handler_ref` or manifest/backend node-id dispatch may remain only as inert
  compatibility during this sprint; S1b-2 proves one builder edge can route
  without it as semantic authority.

Rollback:

- Roll back substrate changes as a unit. Do not keep partial dynamic fanout
  support if reducer/reentry behavior is unproven.

Parity checks:

- Existing Megaplan state names and route labels are unchanged; substrate tests
  are additive.

### S1b-2 - Typed Outcomes, Builder Slice, Installed Package

Scope:

- Add closed typed outcomes/interfaces for one runtime-load-bearing edge.
- Prove `build_pipeline()` consumes lowered `.pypeline` topology for that edge instead of component route metadata. Current component fallback is in `planning.py:247-268`, `:557-598`, `:695-716`.
- Establish installed-package parity smoke for strict checker source and runtime behavior.
- Use the proven S1b-1 substrate; do not implement new fanout/suspension/loop
  substrate in this sprint.

Exit gates:

- `PYENV_VERSION=3.11.11 pytest tests/arnold_pipelines/megaplan/test_workflows_planning_lowered_topology.py tests/arnold_pipelines/megaplan/test_installed_package_composition_smoke.py -q`
- `PYENV_VERSION=3.11.11 pytest tests/arnold/workflow/test_row_evidence_checker.py tests/arnold/workflow/test_megaplan_checker_structural_rejection.py tests/arnold/workflow/test_megaplan_row_registry_completeness.py -q`
- Strict checker checkout and installed-package smoke both pass only for the
  S1b-2 slice and still fail all unextracted rows.
- Dead-delete behavior test for the S1b-2 edge: delete/mutate old component
  `route_bindings` for that edge and prove behavior/output unchanged.
- Dedicated parity checks diff S1b-2 behavior against frozen S1a baselines, not
  against the current build.
- Repin the Megaplan runner only after S1b-2 if the runner code changed. Repin
  requires auto-drive characterization, strict checker smoke, and North Star
  action smoke to pass.

Evidence spec:

- Strict checker slice record plus installed package fingerprint from source loaded out of the built artifact.

Deletion/quarantine:

- The replaced edge's component route binding cannot route behavior; component metadata may remain only as inert compatibility metadata.

Rollback:

- Revert typed outcome/builder edge and restore component edge for that single slice, with S1a checker still blocking broad closeout.

Parity checks:

- State names and route labels are preserved; `build_pipeline()` output route labels match `_core/workflow_data.py` and current CLI status/autodrive vocabulary.

### S2 - Front-Half Native Loop

Scope:

- Extract prep clarify/suspend/resume, plan artifact contract, critique fanout/retry/skip, gate preflight/reprompt/downgrade/debt/severity, and revise loop caps/no-progress termination.
- Current carriers: `workflow.pypeline:390-470`, `handlers/gate.py:77-133`, `:414-677`, `:993-1097`, `components.py:1154-1336`, `workflows/front_half.pypeline:31`, and `outcomes.py:43-44`.
- Gate/revise is one extraction unit because gate route groups and revise reentries are coupled (`components.py:1154-1158`, `:1276-1279`).

Exit gates:

- `PYENV_VERSION=3.11.11 pytest tests/arnold_pipelines/megaplan/test_front_half_native_loop.py tests/arnold/workflow/test_megaplan_native_semantic_checker_authority.py -q`
- `PYENV_VERSION=3.11.11 pytest tests/arnold/workflow/test_row_evidence_checker.py tests/arnold/workflow/test_megaplan_checker_structural_rejection.py tests/arnold/workflow/test_megaplan_row_registry_completeness.py -q`
- `PYENV_VERSION=3.11.11 python scripts/check_megaplan_baseline_freeze.py --baselines artifacts/native-semantic-parity/baselines/pre-extraction --scope s2 --require-pre-extraction --amendments artifacts/native-semantic-parity/baseline-amendments.yaml`
- Strict checker must produce row evidence for every S2 row with source spans in `workflow.pypeline` or named native subworkflows, not `components.py`.
- Split-outcome scenarios must cover prep suspend/resume, gate reprompt/downgrade, critical cap exhaustion, cosmetic cap exhaustion, force-proceed, and abort.
- Per-sprint dead-delete mutation: mutate/delete old front-half route groups, reprompt metadata, and handler route decisions; behavior remains unchanged under S2 scenarios compared to frozen S1a baselines.
- A pre-S2 serialized/suspended fixture must resume on post-S2 code or be covered
  by the sprint's explicit drain/quarantine rollout record.
- Any native-source feature flag used during S2 must be deleted before S2 closes. Closeout fails if both legacy and native front-half route authority remain selectable.

Evidence spec:

- Generated S2 checker evidence with positive/negative fixtures and mutation report tied to S2 carrier IDs.

Deletion/quarantine:

- Front-half `components.py` route groups, `handler_ref` route ownership, and handler-local `current_state`/`next_step` routing for corrected rows must be gone or fenced before S2 closes.

Rollback:

- A temporary native-source feature flag may exist only during S2 development and
  scenario hardening. It must be removed before closeout. Rollback after close is
  by reverting the S2 sprint commit(s), not by leaving a permanent dual-path
  toggle.

Parity checks:

- Preserve `prep`, `plan`, `critique`, `gate`, `revise`, `override add-note`, `override force-proceed`, `abort`, and resume labels. Auto-drive characterization must still select the same next command for existing state fixtures.

### S3 - Tiebreaker and Replan Native Flow

Scope:

- Replace `TIEBREAKER_WORKFLOW`/component child metadata with named native tiebreaker subworkflow phases: researcher, challenger, synthesis, decision.
- Current carriers: `workflow.pypeline:471-488`, `workflow.pypeline:281-300`, `components.py:2546-2550`, `replan_state.py:1-38`, `boundary_contracts.py:142-243`.
- Replan rejoin must be explicit source authority, not state-clear side effect.

Exit gates:

- `PYENV_VERSION=3.11.11 pytest tests/arnold_pipelines/megaplan/test_tiebreaker_native_flow.py -q`
- `PYENV_VERSION=3.11.11 pytest tests/arnold/workflow/test_row_evidence_checker.py tests/arnold/workflow/test_megaplan_checker_structural_rejection.py tests/arnold/workflow/test_megaplan_row_registry_completeness.py -q`
- `PYENV_VERSION=3.11.11 python scripts/check_megaplan_baseline_freeze.py --baselines artifacts/native-semantic-parity/baselines/pre-extraction --scope s3 --require-pre-extraction --amendments artifacts/native-semantic-parity/baseline-amendments.yaml`
- Strict checker must reject a single `TIEBREAKER_WORKFLOW(...)` wrapper and require all four named phases plus decision routes.
- Split-outcome scenarios: pick/proceed, replan/iterate rejoin, escalate/override, and parent rejoin receipt.
- Per-sprint dead-delete mutation: mutate/delete old tiebreaker component routes and handler decision dispatch; scenarios remain unchanged compared to frozen S1a baselines.
- A pre-S3 serialized/suspended fixture must resume on post-S3 code or be covered
  by the sprint's explicit drain/quarantine rollout record.
- No S3 feature flag or alternate tiebreaker route authority may remain after closeout.

Evidence spec:

- S3 row evidence with child workflow spans, parent rejoin policy, and negative fixture for the old wrapper.

Deletion/quarantine:

- Old tiebreaker workflow metadata may remain only as compatibility metadata and cannot be cited as semantic authority.

Rollback:

- Roll back the tiebreaker subworkflow as a unit; do not leave researcher/challenger native while decision remains handler-owned.

Parity checks:

- Preserve tiebreaker artifacts (`research_findings.json`, `challenge_findings.json`, `tiebreaker_payload.json`, `tiebreaker_decisions.json`) and route labels `proceed`, `iterate`, `escalate`.

### S4 - Execute DAG, Approval, Resume

Scope:

- Extract execute dependency batching, destructive approval denial/approval, blocked retry, fresh-session forcing, partial resume cursor, no-review handoff, and execute model/tier route policy.
- Current carriers: `workflow.pypeline:405-418`, `:424-435`, `:491-502`, `components.py:1694-1781`, `handlers/execute.py:322-345`, `:402-445`, `:562-572`, `execute/policy.py:31-600`, `execute/batch.py:1201+`, `:2278+`.

Exit gates:

- `PYENV_VERSION=3.11.11 pytest tests/arnold_pipelines/megaplan/test_execute_native_dag_approval_resume.py -q`
- `PYENV_VERSION=3.11.11 pytest tests/arnold/workflow/test_row_evidence_checker.py tests/arnold/workflow/test_megaplan_checker_structural_rejection.py tests/arnold/workflow/test_megaplan_row_registry_completeness.py -q`
- `PYENV_VERSION=3.11.11 python scripts/check_megaplan_baseline_freeze.py --baselines artifacts/native-semantic-parity/baselines/pre-extraction --scope s4 --require-pre-extraction --amendments artifacts/native-semantic-parity/baseline-amendments.yaml`
- Strict checker must reject handler-owned execute route decisions and hidden scheduler authority.
- Split-outcome scenarios: partial resume, destructive approval denial, destructive approval approval, blocked retry, review handoff, no-review terminal.
- Per-sprint dead-delete mutation: mutate/delete old execute route surfaces and handler next-step scheduling; execute scenarios remain unchanged compared to frozen S1a baselines.
- A pre-S4 serialized/suspended fixture must resume on post-S4 code or be covered
  by the sprint's explicit drain/quarantine rollout record.
- No execute native/legacy route feature flag may remain after closeout.

Evidence spec:

- Generated execute row evidence includes DAG/batch spans, approval gate spans, resume cursor schema, and installed-package behavior proof.

Deletion/quarantine:

- `components.py` execute fanout contracts and route surfaces cannot route corrected behavior.
- Handler/auto execute state mutation may remain only as phase-body side effects after native route decision is already determined.

Rollback:

- Roll back execute native route authority as one unit; keep artifact schema and state compatibility fixtures intact.

Parity checks:

- Preserve task artifact names, `execute`, `review`, `no_review`, `deferred_human`, `blocked`, `recover-blocked`, and fresh-session CLI semantics.

### S5 - Review, Rework, Finalize

Scope:

- Extract review fanout/fanin, reducer routes, rework loop, review caps, no-review terminal, deferred-human terminal, finalize fallback/baseline routes, and final projection.
- Current carriers: `workflow.pypeline:413-463`, `:498-540`, `components.py:1509-1581`, `:2634-2669`, `source_compiler.py:1142-1233`, `:1783-1868`, `handlers/review.py`, `handlers/finalize.py`.

Exit gates:

- `PYENV_VERSION=3.11.11 pytest tests/arnold_pipelines/megaplan/test_review_finalize_native_flow.py -q`
- `PYENV_VERSION=3.11.11 pytest tests/arnold/workflow/test_row_evidence_checker.py tests/arnold/workflow/test_megaplan_checker_structural_rejection.py tests/arnold/workflow/test_megaplan_row_registry_completeness.py -q`
- `PYENV_VERSION=3.11.11 python scripts/check_megaplan_baseline_freeze.py --baselines artifacts/native-semantic-parity/baselines/pre-extraction --scope s5 --require-pre-extraction --amendments artifacts/native-semantic-parity/baseline-amendments.yaml`
- Strict checker must require S5 row evidence; S5 cannot pass on `Mapping` existence in `REVIEW_POLICY` or `FINALIZE_POLICY`.
- Split-outcome scenarios: review pass, review rework, review cap with blockers, review cap without blockers, no-review terminal, deferred-human terminal, finalize fallback revise.
- Per-sprint dead-delete mutation: mutate/delete old review/finalize route surfaces and handler state transition paths; S5 scenarios remain unchanged compared to frozen S1a baselines.
- A pre-S5 serialized/suspended fixture must resume on post-S5 code or be covered
  by the sprint's explicit drain/quarantine rollout record.
- No review/finalize native/legacy route feature flag may remain after closeout.

Evidence spec:

- Generated S5 checker evidence plus S5-specific negative fixture where policy metadata contains route tables but named source constructs are absent.

Deletion/quarantine:

- `reducer_routes`, `target_ref`, `force_proceed_authority`, `fallback_routes`, and review cap route decisions in policy metadata are not sufficient as row authority unless attached to named source constructs and free of route-table behavior.

Rollback:

- Review/finalize extraction rolls back together; do not leave review native with finalize fallback handler-owned.

Parity checks:

- Preserve `review_output.json`, review receipt fields, `pass`, `rework`, `blocked`, `force_proceeded`, `deferred_human`, and final plan artifact names.

### S6 - Override, Auto, Compatibility Collapse

Scope:

- Extract override action routing into source-visible control surface; remove auto-drive as a second route brain; quarantine compatibility projections.
- Current carriers: `workflow.pypeline:36-79`, `:250-280`, `components.py:399-433`, `:1603-1621`, `workflows/override_matrix.py:40-149`, `handlers/override.py`, `auto.py:1198-1245`, `:4496-4521`, `route_dispatch.py:26-43`, `runtime/manifest_backend.py:227-380`, `_compatibility.py:101-115`, `:173-267`.

Exit gates:

- `PYENV_VERSION=3.11.11 pytest tests/arnold_pipelines/megaplan/test_override_auto_compat_quarantine.py tests/arnold/conformance/test_megaplan_coupling_gate.py -q`
- `PYENV_VERSION=3.11.11 pytest tests/arnold/workflow/test_row_evidence_checker.py tests/arnold/workflow/test_megaplan_checker_structural_rejection.py tests/arnold/workflow/test_megaplan_row_registry_completeness.py -q`
- `PYENV_VERSION=3.11.11 python scripts/check_megaplan_baseline_freeze.py --baselines artifacts/native-semantic-parity/baselines/pre-extraction --scope s6 --require-pre-extraction --amendments artifacts/native-semantic-parity/baseline-amendments.yaml`
- Strict checker rejects `_compatibility.py` `NativeProgram`, manifest backend branch translation, route dispatch fallback, CLI handlers, and auto next-step derivation as row evidence.
- Split-outcome scenarios: force-proceed from allowed states, abort, replan, recover-blocked, resume-clarify, adopt-execution, invalid force-proceed state.
- Per-sprint dead-delete mutation: mutate/delete override matrix route targets, auto next-step derivation, route_dispatch fallback, and manifest backend translation; corrected behavior remains source-derived or fails closed against frozen S1a baselines.
- A pre-S6 serialized/suspended fixture must resume on post-S6 code or be covered
  by the sprint's explicit drain/quarantine rollout record.
- No override/auto native/legacy route feature flag may remain after closeout.

Evidence spec:

- Compatibility quarantine report has active rejection rules, not just a static scan.

Deletion/quarantine:

- `route_dispatch.py`, manifest backend branch maps, and `_compatibility.py` CLI-handler phase fallback must consume source-derived semantics or be fenced from evidence and runtime route authority.

Rollback:

- Keep compatibility shell executable for legacy runs, but rollback cannot restore compatibility projection as evidence authority.

Parity checks:

- `_core/workflow_data.py` state names and CLI control commands remain compatible until an explicit switch gate changes them.

### S7 - Final Generated Conformance and Rollout

Scope:

- Generate final report from strict generated evidence only: checker output,
  installed-package checker output, package-wide carrier scan, row-registry
  reconciliation, deterministic baseline freeze records, exemption summary, and
  scenario-row coverage.
- Run full split-outcome, installed-package, mutation, compatibility, handler-purity, and auto-drive characterization gates.
- Document runtime narrowing in every closeout artifact.

Exit gates:

- `PYENV_VERSION=3.11.11 python scripts/check_megaplan_native_semantic_parity.py --source arnold_pipelines/megaplan/workflows/workflow.pypeline --strict --require-row-evidence --mode checkout --out artifacts/native-semantic-parity/checker-checkout.json`
- Same command with `--mode installed-package`.
- `PYENV_VERSION=3.11.11 python scripts/scan_megaplan_semantic_carriers.py --roots arnold_pipelines/megaplan arnold/workflow arnold/runtime arnold/conformance --exclude-from artifacts/native-semantic-parity/carrier-scan-exclusions.yaml --out artifacts/native-semantic-parity/carrier-scan-final.json`
- `PYENV_VERSION=3.11.11 python scripts/classify_megaplan_semantic_carriers.py --carrier-scan artifacts/native-semantic-parity/carrier-scan-final.json --out artifacts/native-semantic-parity/carrier-tier-classification-final.json`
- `PYENV_VERSION=3.11.11 python scripts/validate_megaplan_carrier_tier_boundary.py --carrier-tier artifacts/native-semantic-parity/carrier-tier-classification-final.json --sample-seed artifacts/native-semantic-parity/carrier-tier-final-sample-seed.txt --sample-size 20 --scenarios docs/arnold/megaplan-native-representation-scenarios.yaml --out artifacts/native-semantic-parity/carrier-tier-boundary-validation-final.json`
- `PYENV_VERSION=3.11.11 python scripts/reconcile_megaplan_semantic_rows.py --carrier-scan artifacts/native-semantic-parity/carrier-scan-final.json --row-registry arnold/workflow/megaplan_semantic_rows.yaml --fail-unmapped --out artifacts/native-semantic-parity/row-registry-reconciliation-final.json`
- `PYENV_VERSION=3.11.11 python scripts/check_megaplan_exemption_ledger.py --reconciliation artifacts/native-semantic-parity/row-registry-reconciliation-final.json --fail-open-scheduled --out artifacts/native-semantic-parity/exemption-summary.json`
- `PYENV_VERSION=3.11.11 python scripts/check_megaplan_baseline_freeze.py --baselines artifacts/native-semantic-parity/baselines/pre-extraction --amendments artifacts/native-semantic-parity/baseline-amendments.yaml --mode final --require-reviewed-amendments`
- `PYENV_VERSION=3.11.11 python scripts/generate_megaplan_scenario_row_matrix.py --checker artifacts/native-semantic-parity/checker-checkout.json --scenarios docs/arnold/megaplan-native-representation-scenarios.yaml --baselines artifacts/native-semantic-parity/baselines/pre-extraction --harness tests/fixtures/megaplan/replay --out artifacts/native-semantic-parity/scenario-row-coverage.json`
- `PYENV_VERSION=3.11.11 python scripts/generate_megaplan_native_semantic_conformance.py --checker artifacts/native-semantic-parity/checker-checkout.json --installed-checker artifacts/native-semantic-parity/checker-installed.json --row-registry-reconciliation artifacts/native-semantic-parity/row-registry-reconciliation-final.json --scenario-row-coverage artifacts/native-semantic-parity/scenario-row-coverage.json --baseline-freeze artifacts/native-semantic-parity/baselines/pre-extraction/freeze-record.json --baseline-amendments artifacts/native-semantic-parity/baseline-amendments.yaml --exemption-summary artifacts/native-semantic-parity/exemption-summary.json --scenarios docs/arnold/megaplan-native-representation-scenarios.yaml --require-runtime-narrowing --out docs/arnold/megaplan-native-semantic-parity-conformance.generated.md`
- `PYENV_VERSION=3.11.11 python scripts/check_megaplan_serialized_plan_rollout.py --policy artifacts/native-semantic-parity/serialized-plan-rollout-policy.yaml --out artifacts/native-semantic-parity/serialized-plan-rollout-final.json` validates either migration fixtures for live suspended plans or an explicit drain/quarantine rollout decision.
- `PYENV_VERSION=3.11.11 pytest tests/arnold_pipelines/megaplan/test_final_conformance_scenarios.py tests/arnold_pipelines/megaplan/test_final_conformance_evidence.py tests/arnold_pipelines/megaplan/test_installed_package_composition_smoke.py tests/arnold/conformance/test_deleted_surfaces.py tests/arnold/conformance/test_megaplan_coupling_gate.py -q`
- `PYENV_VERSION=3.11.11 pytest tests/arnold/workflow/test_row_evidence_checker.py tests/arnold/workflow/test_megaplan_checker_structural_rejection.py tests/arnold/workflow/test_megaplan_row_registry_completeness.py -q`
- `PYENV_VERSION=3.11.11 python scripts/validate_megaplan_runtime_narrowing.py --docs docs/arnold/megaplan-native-semantic-parity-conformance.generated.md docs/arnold/megaplan-native-runtime-narrowing-contract.md --forbid-full-runtime-overclaim`

Evidence spec:

- The final conformance report is generated from checker JSON,
  row-registry reconciliation, carrier scan, and scenario-row coverage only. It
  includes command, git SHA, installed-package fingerprint, row evidence hashes,
  scenario hashes, mutation results, prohibited-proof rejection results, unmapped
  carrier count of zero, exemption counts and diffs since S1a, reviewed baseline
  amendment records, carrier tier counts, carrier-tier boundary validation,
  serialized-plan rollout decision, baseline canonicalizer version when artifact
  hashes are used, and row-to-scenario coverage.

Deletion/quarantine:

- No implemented row cites `components.py`, `handler_ref`, route bindings, manifest backend routing, auto next-step derivation, CLI handlers, or projected-native compatibility.

Rollback:

- Rollback is a release rollback: restore previous runtime package and previous generated conformance artifact, while S1a strict checker still blocks semantic parity claims.

Parity checks:

- Auto-drive characterization corpus, override/resume commands, serialized state consumers, state names, route labels, and artifact names remain compatible unless a separate gated migration changes them.

## 4. Correction Traceability

| Correction | Milestone | Machine gate | Artifact |
| --- | --- | --- | --- |
| 1. S1 hard bar | S0, S1a | S0 pins runner and lands North Star action plumbing; S1a `scripts/check_megaplan_native_semantic_parity.py --strict --mode checkout/installed-package` fails current source before extraction and becomes closeout path; package-wide carrier-scan row registry reconciliation must fail on unmapped route-authoritative carriers or unapproved exclusions | `runner-pin-s0.json`, `s1-current-checkout.json`, `s1-current-installed.json`, `row-registry-reconciliation.json`, `carrier-scan-exclusions.yaml` |
| 2. Hard negative fixture | S1a | Current-shape fixture plus one focused renamed/re-encoded adversarial suite rejected forever with pinned diagnostic codes | `tests/fixtures/workflow_authoring/megaplan/current_false_pass_shape.py`, `tests/fixtures/workflow_authoring/megaplan/renamed_carrier_evasion/` |
| 3. Policy-as-route-table rejection | S1a, S5 | Checker diagnostic structurally rejects policy `target_ref`, reducer routes, route groups, fanout contracts, override dispatch, or route-shaped mappings as row authority | checker JSON diagnostic records |
| 4. Per-sprint dead-delete mutation | S1b-2, S2, S3, S4, S5, S6 | Sprint-specific behavior tests prove old carriers cannot route corrected behavior against frozen deterministic baselines; no sprint closes with dual route feature flags alive | dead-delete pytest results, frozen baselines, baseline amendment records |
| 5. Compat quarantine | S1a, S6, S7 | Checker forbids `_compatibility.py` `NativeProgram`/CLI fallback as semantic evidence | compatibility quarantine rejection report |
| 6. Generated-only conformance | S7 | Generator accepts generated evidence only, each with provenance: strict checker JSON, installed checker JSON, row-registry reconciliation, package-wide carrier scan, carrier-tier boundary validation, generated scenario-row coverage, baseline freeze records, and exemption summary | generated final conformance report |
| 7. Runtime narrowing documented | S1a, every closeout, S7 | `validate_megaplan_runtime_narrowing.py` and final generator reject missing narrowing statement or full-runtime overclaim | `docs/arnold/megaplan-native-runtime-narrowing-contract.md`, generated conformance report |
| 8. Split-outcome gates before rollout | S1a, S2-S7 | S1a authors scenario inventory and deterministic harness; sprint N baselines freeze before sprint N extraction; generated row-to-scenario coverage proves coverage | scenario hash bundle, frozen baselines, replay fixture hashes, `scenario-row-coverage.json`, pytest results |

Additional subagent-audit amendments:

| Amendment | Milestone | Machine gate | Artifact |
| --- | --- | --- | --- |
| Dynamic fanout/runtime substrate | S1b-1 before dependent extraction | Runtime tests prove dynamic `items_ref` fanout, suspension/reentry, and required loop exit behavior before extraction relies on them | `test_native_runtime_dynamic_fanout.py`, runtime fixture JSON |
| Replay scope realism | S1a | Route/state replay gates land first; full model I/O replay is cut unless explicitly escalated | `replay-harness.json` |
| Canonicalized baselines | Trigger-based | Baseline canonicalizer is required only before artifact hashes are accepted as parity proof | optional `baseline-canonicalizer.json`, freeze record |
| Headless control injection | S1a targeted | Programmatic control actions drive only required non-interactive split outcomes in CI | `test_control_injection_headless.py` |
| Serialized-plan rollout | Trigger-based | Migration fixtures are required only if live suspended plans must survive; otherwise closeout records drain/quarantine | rollout/drain decision record or `serialized-plan-rollout-*.json` |
| Carrier tiering | S1/S7, targeted per sprint | Package-wide scan is tiered at S1/S7; seeded descriptive-carrier corruption validates the route/descriptive boundary; per-sprint changed-file scan plus North Star review catches new route authority | `carrier-tier-classification*.json`, `carrier-tier-boundary-validation*.json`, sprint review answers |
| Installed-package source loading | S1 smoke/S7 final | Strict checker source loading via package resources is smoke-tested at S1 and fully checked at S7 or packaging-changing sprints | `test_installed_package_strict_source_loading.py`, installed checker JSON |
| North Star action independence | S0, every sprint | Clean-context reviewer answers explanation tests; canaries validate the auditor; dangerous categories are schema-blocking | `north_star_actions` gate/carry fixtures, canary audit results |
| Runner pinning | S0, post-S1b-2, post-S5 | Chain runner is pinned and repinned only at explicit checkpoints with auto-drive characterization and smoke gates | `runner-pin-*.json`, auto-drive corpus results |

## 5. Prohibited Proofs

These must never satisfy a semantic row:

- `.pypeline` file existence.
- `Pipeline.native_program`.
- `arnold_pipelines/megaplan/_compatibility.py` projections.
- Generated ledgers without strict checker provenance.
- Topology hashes.
- Handler-purity inventories alone.
- Path-addressed evidence alone.
- Boundary receipts without source-visible authority.
- `components.py` policy route surfaces with `target_ref`, `target_refs`, route groups, fanout contracts, reducer routes, topology overlays, or override dispatch.
- `handler_ref`, `route_bindings`, manifest backend branch translation, route_dispatch fallback, auto next-step derivation, or CLI handlers.
- Renamed or re-encoded structural equivalents of the same carriers, including
  route-like mapping literals, step/state/route identifier maps, imported
  component callables used as route authority, and dispatch tables hidden under
  innocuous names.
- Carrier-scan exclusions that lack a dated exemption with category, owner, and
  reason.
- Live model output as baseline proof.
- Baselines regenerated after extraction without a separate reviewed amendment
  ledger entry.
- Open `scheduled-for-sprint-N` exemptions after sprint N or at S7.
- Prior reports, including `megaplan-native-representation-conformance-report.md`.

## 6. Red Team: False Closure Routes and Patches

| False closure attempt | Patch in this plan |
| --- | --- |
| Run `arnold workflow check` and claim success because it calls `check_workflow_file(..., evidence=None)`. | S1a closeout requires strict checker command and rejects non-strict CLI output. |
| Add row evidence records manually without source spans or hashes. | S1a/S7 require checker-generated JSON with row IDs, spans, source hashes, carrier class. |
| Use S5 policy surface keys to claim review/finalize parity. | S5 requires row evidence and policy-as-route-table rejection. |
| Leave old component metadata until S6. | S2-S5 each have their own dead-delete mutation gate. |
| Cite `_compatibility.py` `NativeProgram` as native authority. | S1a/S6/S7 checker rejects compatibility projection evidence. |
| Pass with a toy negative fixture while current skeleton would pass. | S1a fixture must mirror current source shape: imports, declared interfaces, topology contracts, policy route surfaces, compatibility projection. |
| Generate a final report from a YAML ledger and hashes. | S7 generator consumes generated evidence only, each with provenance; manual ledgers cannot set status. |
| Claim full ordinary async Python runtime parity. | S1a/S7 closeout requires runtime narrowing contract and rejects overclaim. |
| Use happy-path smoke tests for behavior parity. | S2-S7 require split-outcome scenarios before rollout. |
| Mutate old carriers in a way tests never exercise. | Each mutation gate must run the relevant split-outcome scenarios with the old carrier disabled/deleted. |
| Shrink the row inventory so strict checking passes vacuously. | S1a/S7 require carrier-scan row registry reconciliation; every discovered carrier maps to a row or dated exemption, and S7 fails on unmapped carriers. |
| Narrow the carrier scan roots so hidden carriers sit outside scanned paths. | S1a/S7 scan package-wide roots with explicit exclusions; every exclusion requires dated exemption treatment and appears in the final report. |
| Rename or re-encode route carriers so token blacklist checks miss them. | S1a structural rejection and renamed-carrier fixtures detect route-shaped mappings, imported component callables, and dispatch tables regardless of name. |
| Leave a feature flag that keeps legacy and native route authorities both alive. | Each sprint close gate deletes temporary feature flags; rollback is by reverting the sprint, not by retaining dual authority. |
| Edit a negative fixture so it still fails, but for a weaker unrelated diagnostic. | Permanent CI fixtures assert exact diagnostic codes, and checker meta-tests run in every sprint exit gate. |
| Compare "unchanged" behavior against the current post-extraction build. | S1a freezes golden split-outcome baselines before extraction; later mutation/parity gates diff against those baselines. |
| Capture golden baselines from live model output, making parity unreproducible. | S1a requires a deterministic replay harness with hash-pinned canned worker payloads; later scenario and mutation gates must use that harness. |
| Regenerate baselines after extraction so parity trivially passes. | Baselines are write-once after each freeze; amendments require a separate reviewed ledger entry and S7 verifies hashes against the freeze record and ledger. |
| Exempt every inconvenient carrier from the row registry. | Exemptions have categories; scheduled exemptions must close by their sprint; S7 publishes exemption counts/diffs and fails on open scheduled exemptions. |
| Claim dynamic `parallel_map` works because `FanoutPolicy(mode="dynamic")` appears in lowered metadata. | S1b-1 requires runtime dynamic fanout tests that prove `items_ref` is consumed and children are spawned. |
| Hash raw artifacts that include timestamps, UUIDs, absolute paths, invocation ids, or session ids. | S1a baseline canonicalizer must normalize volatile fields and its version is part of the frozen record. |
| Drive split outcomes manually through interactive CLI and call them CI scenarios. | S1a requires headless control-injection actions for destructive approval and tiebreaker branches. |
| Break suspended/in-flight plans across topology changes and call label compatibility sufficient. | Every topology-changing sprint needs a pre-sprint serialized fixture resume or an explicit drain/quarantine policy. |
| Bury hundreds of route-shaped candidates under generic carrier exemptions. | S1a carrier tiering separates route-authoritative carriers from descriptive metadata, and route-authoritative carriers need row mapping or removal. |
| Run installed-package mode against checkout paths. | S1a installed-package checker must load `.pypeline` source through package resources from the installed artifact. |
| Let the executor answer its own "can this be understood from source?" question optimistically. | S0 requires clean-context reviewer agents for explanation tests; they predict from source before reading executor narrative and verify against evidence. |
| Downgrade a dangerous North Star action to advisory. | Severity is schema-assigned as blocking for route authority, baselines, exemptions, target narrowing, generated conformance authority, and live-plan topology/resume risk. |
| Misclassify live route authority as descriptive metadata. | S1/S7 seeded descriptive-carrier corruption must leave behavior unchanged; one behavior-changing sample invalidates the tier classification run. |
| The epic modifies the runner driving itself and loses the enforcement loop. | S0 pins the runner; repins happen only after S1b-2 and S5 with auto-drive characterization, strict checker, and North Star action smoke gates. |

## 7. Open Questions

1. Should `check_workflow_file` default become strict globally?
Recommended default: yes, but expose a renamed `check_workflow_file_source_shape_only` for legacy callers so non-strict validation is explicit.
Decision deadline: before S1a closeout. The S1a deletion/quarantine ledger and
CLI bypass disposition cannot close until this decision is recorded.

2. Should policy objects ever contain route targets?
Recommended default: only compatibility metadata may contain them, and the checker must mark those objects inadmissible as row authority. Declared policy evidence must attach to named source constructs and avoid route tables.

3. S1 split decision.
Resolved: S1 does not remain one sprint. The plan is split into S0 runner/North
Star action plumbing, S1a checker authority, S1b-1 runtime substrate proof, and
S1b-2 typed outcomes/builder slice. Each depends on the prior slice.

4. Should old `_compatibility.py` continue to execute legacy plans?
Recommended default: yes for runtime continuity, but quarantine it from semantic evidence and require source-derived route authority for corrected flows.

## Appendix A: Command Log

```bash
sed -n '1,220p' arnold_pipelines/megaplan/skills/subagent-launcher/SKILL.md
sed -n '1,180p' /Users/peteromalley/Documents/poms_skills/contextminning-subagentmaxxing/SKILL.md
mkdir -p .tmp/native-semantic-parity-master-plan/briefs .tmp/native-semantic-parity-master-plan/results .tmp/native-semantic-parity-master-plan/logs
wc -l .megaplan/initiatives/megaplan-native-parity-corrective/NORTHSTAR.md docs/arnold/megaplan-native-parity-corrective-plan.md docs/arnold/megaplan-native-representation-report.md docs/arnold/megaplan-native-representation-conformance-report.md docs/arnold/gpt55-native-parity-endstate-gap-report.md .megaplan/initiatives/legacy-loose-briefs/research/native-python-runtime-full-spec-codex.md .megaplan/initiatives/native-python-pipelines/research/native-python-pipelines-end-goal-megaplan-example.md
ls -1 .megaplan/initiatives/megaplan-native-parity-corrective/briefs
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/launch_hermes_agent.py --toolsets="file,web,terminal" --query-file=.tmp/native-semantic-parity-master-plan/deepseek-smoke-brief.md --project-dir="$PWD" > .tmp/native-semantic-parity-master-plan/deepseek-smoke.out 2> .tmp/native-semantic-parity-master-plan/deepseek-smoke.err
PYENV_VERSION=3.11.11 python - <<'PY'
from pathlib import Path
from collections import Counter
from arnold.workflow.source_compiler import check_workflow_source
p=Path('arnold_pipelines/megaplan/workflows/workflow.pypeline')
result=check_workflow_source(p.read_text(), source_path=str(p))
print(result.ok, len(result.diagnostics), dict(Counter(d.code.value for d in result.diagnostics)))
PY
PYENV_VERSION=3.11.11 pytest tests/arnold/workflow/test_row_evidence_checker.py -q
rg -n "AUTHORING_|[A-Z_]+_WORKFLOW|DECLARED_STEP_INTERFACES|handler_ref|route_bindings|DECLARED_WORKFLOW_TOPOLOGY_CONTRACTS|target_ref|reducer_routes|parallel_map" arnold_pipelines/megaplan/workflows/workflow.pypeline arnold_pipelines/megaplan/workflows/planning.py arnold_pipelines/megaplan/workflows/components.py
rg --files | rg '(_compatibility\.py|manifest_backend\.py|route_dispatch\.py|auto\.py|workflow_data\.py)$'
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/fan.py --briefs-dir=.tmp/native-semantic-parity-master-plan/briefs --output-dir=.tmp/native-semantic-parity-master-plan/results --max-workers=5 --model="deepseek:deepseek-v4-pro" --toolsets="file,web,terminal" --task-timeout=1800 --project-dir="$PWD"
PYENV_VERSION=3.11.11 python - <<'PY'
from pathlib import Path
from collections import Counter
from arnold.workflow.source_compiler import check_workflow_file, check_workflow_source
p=Path('arnold_pipelines/megaplan/workflows/workflow.pypeline')
for name, result in [('file_default', check_workflow_file(p)), ('file_strict_empty', check_workflow_file(p, evidence=())), ('source_default', check_workflow_source(p.read_text(), source_path=p))]:
    print(name, 'ok', result.ok, 'diagnostic_count', len(result.diagnostics), dict(Counter(d.code.value for d in result.diagnostics)))
PY
```
