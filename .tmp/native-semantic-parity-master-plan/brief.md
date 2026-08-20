# MISSION: Megaplan Native Semantic Parity — Corrective Master Plan

You are a GPT-5.5 Codex planning-lead subagent running in `/Users/peteromalley/Documents/Arnold`.

Your job in this session is NOT to implement anything. Your job is to produce a master plan that,
if executed milestone by milestone, gets this repo to 100% semantic parity with the
native end-state — and that CANNOT be falsely closed the way the previous epic was.

Write the final deliverable to:

`docs/arnold/megaplan-native-semantic-parity-master-plan.md`

Also include a concise command log appendix in that report. You may create temporary scratch files under `.tmp/native-semantic-parity-master-plan/`, but do not modify source, tests, docs other than the final report, or initiative files. Do not implement. Do not "fix one small thing while you're in there."

Use extra-high reasoning. Keep status claims anchored in commands and file:line evidence.

## Non-negotiable launcher gate

Before producing the master plan, prove that DeepSeek subagents can run through the local
subagent launcher from this worktree.

1. Read `arnold_pipelines/megaplan/skills/subagent-launcher/SKILL.md`.
2. Create a tiny smoke-test brief under `.tmp/native-semantic-parity-master-plan/` asking DeepSeek to read one known file and report one cited line.
3. Launch exactly one DeepSeek subagent via the Hermes launcher with file access, using the local skill's recommended command shape.
4. If the launcher fails because of stale import paths or environment discovery, fix that FIRST by creating a patched temporary copy of the launcher or fan script under `.tmp/native-semantic-parity-master-plan/`. Do not patch repo source for this planning task.
5. Re-run the smoke test through the patched temporary launcher.
6. Only after one DeepSeek smoke test round-trips successfully may you run the 5 scoped DeepSeek audits and write the master plan.

If you cannot get a DeepSeek subagent to round-trip after the temporary launcher repair attempt, STOP. Do not write a master plan. Instead write:

`docs/arnold/megaplan-native-semantic-parity-master-plan-BLOCKED.md`

That blocked report must include the exact launcher command(s), failure output paths, the import/environment diagnosis, and the next concrete fix. It must explicitly state that the master plan was not produced because the required DeepSeek audit gate failed.

## Context you must internalize first

Read, in this order:
1. `.megaplan/initiatives/megaplan-native-parity-corrective/NORTHSTAR.md`
2. `docs/arnold/megaplan-native-parity-corrective-plan.md`
3. `docs/arnold/megaplan-native-representation-report.md`
4. The sprint briefs under `.megaplan/initiatives/megaplan-native-parity-corrective/briefs/` (s1–s7)
5. `docs/arnold/megaplan-native-representation-conformance-report.md` — treat this as
   a HISTORICAL FALSE PASS, not as status. It claims 31/31 rows implemented; that
   claim is superseded and known-wrong.
6. `docs/arnold/gpt55-native-parity-endstate-gap-report.md` — this is the latest gap report and should be treated as the starting hypothesis, not as ground truth.
7. `.megaplan/initiatives/legacy-loose-briefs/research/native-python-runtime-full-spec-codex.md`
8. `.megaplan/initiatives/native-python-pipelines/research/native-python-pipelines-end-goal-megaplan-example.md`

The definition of done is SEMANTIC parity, not representational parity:
- Final semantic authority is `workflow.pypeline` + imported named native subworkflows
  + declared policies attached to named source constructs + pure retained phase bodies.
- Final topology must be understandable by a reviewer from source alone, WITHOUT
  `components.py` tables, `handler_ref`, `route_bindings`, manifest backend translation,
  `_compatibility.py` projections, auto-drive next-step derivation, or CLI handlers.
- Handlers become phase bodies. They do not own routing, loop termination, cap policy,
  severity branching, suspension, or state mutation (`current_state` / `next_step`).

## Phase 0 — Verify ground truth yourself BEFORE planning

Do not trust any prior report's status claims, including the corrective plan's own
framing. Establish current reality empirically and record file:line evidence:

1. Run the strict checker against the canonical source with row evidence ENFORCED
   (`check_workflow_source(...)` strict path, not `check_workflow_file(..., evidence=None)`).
   Record exact diagnostic counts and row IDs. Expected as of last audit:
   9× AWF245_ROW_EVIDENCE_INSUFFICIENCY on S2/S3 rows — confirm or correct this.
2. Run `pytest tests/arnold/workflow/test_row_evidence_checker.py -q` and record results.
3. Inventory every remaining semantic carrier. At minimum, grep/AST-scan for:
   - `AUTHORING_*` and `*_WORKFLOW` imports in `workflow.pypeline`
   - `DECLARED_STEP_INTERFACES` / `handler_ref` / `route_bindings` embedded in the
     canonical source itself
   - `DECLARED_WORKFLOW_TOPOLOGY_CONTRACTS` route signals / target refs / reducer routes
   - `planning.py` canonicalization via component metadata and route bindings
   - `components.py` policy surfaces that are route tables in disguise: route groups,
     fanout contracts, reducer routes, override dispatch, target refs
   - `_compatibility.py` NativeProgram projection and CLI-handler phase fallback
   - Handler-local `current_state` / `next_step` mutation across
     `arnold_pipelines/megaplan/handlers/` and `execute/`
4. Confirm which handlers are still "report-semantic owners" vs pure phase bodies
   (last audit: 9 of 11 still own semantics per
   `docs/arnold/megaplan-composition-conformance-report.md:74-88`).

If anything you find contradicts the reports above, the repo wins. Note the
discrepancy explicitly in your plan.

## Phase 1 — Deploy DeepSeek subagents for parallel deep audit

Launch 5 DeepSeek subagents via the Hermes launcher. IMPORTANT: the unmodified
launcher/fan script may fail against this worktree if it expects the older
`arnold.pipelines.megaplan` import path. If needed, create a patched temporary copy of the
launcher that imports from `arnold.agent` and `arnold_pipelines.megaplan.runtime`
instead. Verify one subagent round-trips successfully before fanning out all five.

Prefer the local skill launcher instructions at:
`arnold_pipelines/megaplan/skills/subagent-launcher/SKILL.md`

Subagent scopes. Each must return file:line-cited findings, not summaries:

- **SA1 — Checker & closure authority:** Map every validation entry point in
  `arnold/workflow/source_compiler.py`. Which paths enforce row evidence and which
  don't (`check_workflow_file` default `evidence=None` vs `check_workflow_source`
  strict)? Which S5 rows currently pass on policy-surface existence alone? Where could a closure command route around the strict path?
- **SA2 — Front-half carriers (prep/plan/critique/gate/revise):** Every place gate
  reprompt/downgrade, critique evaluator retry, loop caps, no-progress termination,
  severity branching, and debt recording still live in handlers or component
  metadata rather than source. Coupling constraints between gate and revise.
- **SA3 — Tiebreaker + execute:** Researcher/challenger/decide carriers; replan
  rejoin semantics; execute DAG batching in `execute/batch.py`; approval gates,
  blocked-retry, fresh-session forcing, resume cursors.
- **SA4 — Review/finalize/override/auto/compat:** Review outcome state machine,
  rework caps, parallel review, finalize baseline fallback, `_OVERRIDE_ACTIONS`
  dispatch, `auto.py` next-step derivation, everything `_compatibility.py` still
  load-bears at runtime.
- **SA5 — Evidence & gating infrastructure:** What exists today for generated
  ledgers, scenario hashes, installed-package fingerprints, handler-purity scans,
  dead-delete mutation checks, negative fixtures. What is missing to make each of
  the eight corrections below mechanically enforceable.

Spot-check every subagent claim against source before using it. Discard anything
you cannot verify with file:line evidence.

## Phase 2 — Produce the master plan

Structure the plan around the existing S1–S7 milestones, amended as follows. These
eight corrections are MANDATORY plan elements; your plan must include a traceability
table mapping each correction to the specific milestone, gate, and artifact that
enforces it:

1. **S1 hard bar:** S1 cannot close unless strict checker execution is wired into
   the actual closeout path, current source fails it in BOTH checkout and
   installed-package mode before correction, and final rows require fresh checker
   output with row IDs, spans, content hashes, and carrier classification. If S1 is
   too large, split it — but the checker-authority slice must land first and every
   other slice must depend on it.
2. **Hard negative fixture:** A fixture mirroring the CURRENT canonical source
   shape (`AUTHORING_*` imports, `DECLARED_STEP_INTERFACES`,
   `DECLARED_WORKFLOW_TOPOLOGY_CONTRACTS`, component-backed `parallel_map`, policy
   route surfaces, compatibility shell projection) that the checker must reject
   forever. Toy wrapper fixtures are insufficient.
3. **Policy-as-route-table rejection:** A declared policy satisfies a row only if
   specific, attached to a named source construct, and free of target refs,
   reducer routes, route groups, fanout contracts, or override dispatch.
4. **Per-sprint dead-delete mutation:** Each extraction sprint (S2–S5) must prove
   the carrier it replaced can no longer route corrected behavior — mutate/delete
   the old carrier and show behavior is unchanged. Cleanup deferred to S6 is a
   gate failure.
5. **Compat quarantine:** `_compatibility.py` NativeProgram projection is never
   admissible as evidence of native-source semantic authority. Encode this as a
   checker rule, not a convention.
6. **Generated-only conformance:** The final report must be generated from strict
   checker evidence only. Manual tables and prior reports are input history.
7. **Runtime narrowing documented:** Every closeout artifact must state that this
   epic delivers source-authoritative `.pypeline` lowered into the existing
   DSL/manifest runtime — NOT the full ordinary-async-Python resumable runtime
   from the older spec. Overclaiming this is a repeat of the original failure.
8. **Split-outcome behavior gates before rollout:** Required scenario coverage:
   prep suspend/resume, gate reprompt/downgrade, critical vs cosmetic cap
   exhaustion, tiebreaker pick/replan/escalate rejoin, execute partial resume,
   destructive approval denial AND approval, review rework/cap, no-review
   terminal, force-proceed, abort. Happy-path smoke does not count.

For EACH milestone, the plan must specify:
- Scope: exact carriers extracted/deleted, with current file:line locations
- Exit gates: machine-checkable, naming the exact command/test that proves each
- Evidence spec: what artifacts are generated, by what tool, from what source
- Deletion/quarantine list: what must be gone or fenced before close
- Rollback: how to revert without stranding partial extraction
- Parity checks: state names, artifact names, route labels, auto-drive
  characterization corpus, override/resume commands remain compatible per
  `_core/workflow_data.py` until an explicit, gated switch

## Plan deliverable format

1. Ground-truth status summary from Phase 0, with discrepancies vs prior reports
2. Subagent findings synthesis, spot-check verified and cited
3. Milestone plan, amended S1–S7
4. Correction traceability table: corrections 1–8 to enforcing plan elements
5. Prohibited-proof list: explicit enumeration of evidence types that must
   never satisfy a row (`.pypeline` file existence, `Pipeline.native_program`,
   generated ledgers without strict checker provenance, topology hashes,
   handler-purity inventories alone, path-addressed evidence, compat projections)
6. Red team section: "How could an executor falsely close each milestone of THIS
   plan?" — then patch the plan so each identified exploit is closed. A plan
   without this section is incomplete.
7. Open questions requiring human decision, each with a recommended default

## Hard rules

- No status claim without a command you ran or a file:line you inspected.
- The repo overrides all documents, including this prompt's stated expectations.
- Do not implement. Do not "fix one small thing while you're in there."
- If you believe a gap-report correction is wrong or infeasible, argue it
  explicitly with evidence — do not silently drop it.
- Use DeepSeek subagents as much as practical, but the final report is your responsibility; do not paste unchecked subagent output.
- At the end, print the final report path and a compact summary of whether the plan passes these five audit checks:
  1. Traceability table maps all eight corrections to specific, machine-checkable gates.
  2. S1 or its split makes strict checker the sole closure path, including installed-package mode.
  3. S2-S5 each include their own dead-delete mutation gate.
  4. Negative fixture mirrors the actual current source shape, not toy wrappers.
  5. No exit gate accepts a ledger, hash, projection, or path-existence check as semantic proof.
