# Oracle review packet inventory

Date: 2026-07-21

Purpose: define a self-contained, reviewable ZIP for the three final Oracle
questions: specification determinacy, false-green proof resistance, and
implementation/sequencing feasibility.

All 68 repository-source paths below were checked with `test -f` from
`/Users/peteromalley/Documents/Arnold` and exist. The packet builder should add
four packet-only orientation files, for 72 ZIP entries in total. The builder
must copy the files into the relative layout below rather than preserving
leading `.tmp` or `.megaplan` path segments that obscure their role.

## Proposed ZIP root

```text
arnold-native-workflow-oracle-review-2026-07-21/
├── 00_START_HERE/
│   ├── README.md
│   ├── QUESTIONS.md
│   ├── KNOWN_UNKNOWNS.md
│   └── FILE_INDEX.md
├── 01_END_STATE/
├── 02_NATIVE_PARITY_EPIC/
│   └── briefs/
├── 03_CONTRACTS/
│   ├── authoring-manifest-runtime/
│   └── authority-boundaries-state/
├── 04_CURRENT_SUBSTRATE/
│   ├── arnold/
│   └── megaplan/
├── 05_AUDITS/
└── 06_LOCAL_CUSTODY_CONTEXT_NOT_M11/
```

`FILE_INDEX.md` should map every ZIP path to its repository source path and
record a SHA-256 digest after the representation report has received its final
edit. This makes the packet snapshot self-identifying.

## Exact existing-file inventory

### 01_END_STATE — 2 files

1. `01_END_STATE/megaplan-native-representation-report.md`
   - Source: `docs/arnold/megaplan-native-representation-report.md`
   - Role: holistic current/Stage-1/Stage-2 representation and audit guide.
2. `01_END_STATE/workflow-platformization-ticket.md`
   - Source: `.megaplan/tickets/01KY2DWSJG0B9YKAJRYA0107XE-build-a-reusable-native-workflow-pattern-platform-after-megaplan-parity.md`
   - Role: dependent Stage-2 platformization specification.

### 02_NATIVE_PARITY_EPIC — 12 files

3. `02_NATIVE_PARITY_EPIC/canonical-plan.md`
   - Source: `docs/arnold/megaplan-native-parity-corrective-plan.md`
4. `02_NATIVE_PARITY_EPIC/NORTHSTAR.md`
   - Source: `.megaplan/initiatives/megaplan-native-parity-corrective/NORTHSTAR.md`
5. `02_NATIVE_PARITY_EPIC/README.md`
   - Source: `.megaplan/initiatives/megaplan-native-parity-corrective/README.md`
6. `02_NATIVE_PARITY_EPIC/chain.yaml`
   - Source: `.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml`
7. `02_NATIVE_PARITY_EPIC/GOLDEN_TRACE_CONTRACT.md`
   - Source: `.megaplan/initiatives/megaplan-native-parity-corrective/GOLDEN_TRACE_CONTRACT.md`
8. `02_NATIVE_PARITY_EPIC/briefs/s1-checker-outcomes-builder-slice.md`
   - Source: `.megaplan/initiatives/megaplan-native-parity-corrective/briefs/s1-checker-outcomes-builder-slice.md`
9. `02_NATIVE_PARITY_EPIC/briefs/s2-front-half-native-loop.md`
   - Source: `.megaplan/initiatives/megaplan-native-parity-corrective/briefs/s2-front-half-native-loop.md`
10. `02_NATIVE_PARITY_EPIC/briefs/s3-tiebreaker-replan-native.md`
    - Source: `.megaplan/initiatives/megaplan-native-parity-corrective/briefs/s3-tiebreaker-replan-native.md`
11. `02_NATIVE_PARITY_EPIC/briefs/s4-execute-dag-approval-resume.md`
    - Source: `.megaplan/initiatives/megaplan-native-parity-corrective/briefs/s4-execute-dag-approval-resume.md`
12. `02_NATIVE_PARITY_EPIC/briefs/s5-review-rework-finalize.md`
    - Source: `.megaplan/initiatives/megaplan-native-parity-corrective/briefs/s5-review-rework-finalize.md`
13. `02_NATIVE_PARITY_EPIC/briefs/s6-override-auto-compat-collapse.md`
    - Source: `.megaplan/initiatives/megaplan-native-parity-corrective/briefs/s6-override-auto-compat-collapse.md`
14. `02_NATIVE_PARITY_EPIC/briefs/s7-final-conformance-rollout.md`
    - Source: `.megaplan/initiatives/megaplan-native-parity-corrective/briefs/s7-final-conformance-rollout.md`

Only the seven `s1`–`s7` briefs referenced by `chain.yaml` are active. The ten
older `m1`–`m10` briefs in the same source directory are superseded planning
history and should not enter the packet.

### 03_CONTRACTS/authoring-manifest-runtime — 7 files

15. `03_CONTRACTS/authoring-manifest-runtime/python-shaped-authoring-contract.md`
    - Source: `docs/arnold/python-shaped-authoring-contract.md`
16. `03_CONTRACTS/authoring-manifest-runtime/workflow-manifest-contract.md`
    - Source: `docs/arnold/workflow-manifest.md`
17. `03_CONTRACTS/authoring-manifest-runtime/workflow-manifest-amendments.md`
    - Source: `docs/arnold/workflow-manifest-amendments.md`
18. `03_CONTRACTS/authoring-manifest-runtime/native-composition-contract.md`
    - Source: `docs/arnold/native-composition-contract.md`
19. `03_CONTRACTS/authoring-manifest-runtime/native-platform-posture.md`
    - Source: `docs/arnold/native-platform.md`
20. `03_CONTRACTS/authoring-manifest-runtime/runtime-contract.md`
    - Source: `arnold/runtime/CONTRACT.md`
21. `03_CONTRACTS/authoring-manifest-runtime/state-authority-migration.md`
    - Source: `docs/arnold/state-authority-migration.md`

### 03_CONTRACTS/authority-boundaries-state — 4 files

22. `03_CONTRACTS/authority-boundaries-state/runauthority-architecture-decision.md`
    - Source: `docs/arnold/runauthority-architecture-decision.md`
23. `03_CONTRACTS/authority-boundaries-state/runauthority-main-plan.md`
    - Source: `docs/arnold/runauthority-main-plan.md`
24. `03_CONTRACTS/authority-boundaries-state/workflow-boundary-contracts-NORTHSTAR.md`
    - Source: `.megaplan/initiatives/workflow-boundary-contracts/NORTHSTAR.md`
25. `03_CONTRACTS/authority-boundaries-state/workflow-boundary-contracts-README.md`
    - Source: `.megaplan/initiatives/workflow-boundary-contracts/README.md`

These are the closest local canonical sources for Run Authority, WBC,
state/authority migration, and evidence-versus-projection ownership. They do
not stand in for the missing completed-M11 Custody contract.

### 04_CURRENT_SUBSTRATE/context — 2 files

26. `04_CURRENT_SUBSTRATE/current-codebase-map.md`
    - Source: `docs/arnold/megaplan-native-current-codebase-map.md`
27. `04_CURRENT_SUBSTRATE/oracle-synthesis.md`
    - Source: `docs/arnold/megaplan-native-oracle-synthesis.md`

### 04_CURRENT_SUBSTRATE/arnold — 15 files

28. `04_CURRENT_SUBSTRATE/arnold/workflow/authoring.py`
    - Source: `arnold/workflow/authoring.py`
29. `04_CURRENT_SUBSTRATE/arnold/workflow/source_compiler.py`
    - Source: `arnold/workflow/source_compiler.py`
30. `04_CURRENT_SUBSTRATE/arnold/workflow/diagnostics.py`
    - Source: `arnold/workflow/diagnostics.py`
31. `04_CURRENT_SUBSTRATE/arnold/workflow/validation.py`
    - Source: `arnold/workflow/validation.py`
32. `04_CURRENT_SUBSTRATE/arnold/workflow/manifests.py`
    - Source: `arnold/workflow/manifests.py`
33. `04_CURRENT_SUBSTRATE/arnold/workflow/boundary_evidence.py`
    - Source: `arnold/workflow/boundary_evidence.py`
34. `04_CURRENT_SUBSTRATE/arnold/execution/runner.py`
    - Source: `arnold/execution/runner.py`
35. `04_CURRENT_SUBSTRATE/arnold/execution/registries.py`
    - Source: `arnold/execution/registries.py`
36. `04_CURRENT_SUBSTRATE/arnold/execution/resume.py`
    - Source: `arnold/execution/resume.py`
37. `04_CURRENT_SUBSTRATE/arnold/runtime/envelope.py`
    - Source: `arnold/runtime/envelope.py`
38. `04_CURRENT_SUBSTRATE/arnold/runtime/event_journal.py`
    - Source: `arnold/runtime/event_journal.py`
39. `04_CURRENT_SUBSTRATE/arnold/runtime/effect.py`
    - Source: `arnold/runtime/effect.py`
40. `04_CURRENT_SUBSTRATE/arnold/runtime/resume.py`
    - Source: `arnold/runtime/resume.py`
41. `04_CURRENT_SUBSTRATE/arnold/pipeline/native/runtime.py`
    - Source: `arnold/pipeline/native/runtime.py`
42. `04_CURRENT_SUBSTRATE/arnold/pipeline/native/checkpoint.py`
    - Source: `arnold/pipeline/native/checkpoint.py`

This is a bounded substrate sample, not a claim that these files form one
already-converged runtime. It intentionally exposes the overlapping
`arnold.execution`, `arnold.runtime`, and legacy native-pipeline planes that the
Oracle must assess.

### 04_CURRENT_SUBSTRATE/megaplan — 10 files

43. `04_CURRENT_SUBSTRATE/megaplan/workflows/planning.py`
    - Source: `arnold_pipelines/megaplan/workflows/planning.py`
44. `04_CURRENT_SUBSTRATE/megaplan/workflows/components.py`
    - Source: `arnold_pipelines/megaplan/workflows/components.py`
45. `04_CURRENT_SUBSTRATE/megaplan/core/workflow_data.py`
    - Source: `arnold_pipelines/megaplan/_core/workflow_data.py`
46. `04_CURRENT_SUBSTRATE/megaplan/orchestration/plan_contracts.py`
    - Source: `arnold_pipelines/megaplan/orchestration/plan_contracts.py`
47. `04_CURRENT_SUBSTRATE/megaplan/workflows/boundary_contracts.py`
    - Source: `arnold_pipelines/megaplan/workflows/boundary_contracts.py`
48. `04_CURRENT_SUBSTRATE/megaplan/runtime/manifest_backend.py`
    - Source: `arnold_pipelines/megaplan/runtime/manifest_backend.py`
49. `04_CURRENT_SUBSTRATE/megaplan/runtime/resume_migration.py`
    - Source: `arnold_pipelines/megaplan/runtime/resume_migration.py`
50. `04_CURRENT_SUBSTRATE/megaplan/observability/events_projection.py`
    - Source: `arnold_pipelines/megaplan/observability/events_projection.py`
51. `04_CURRENT_SUBSTRATE/megaplan/cli/projection.py`
    - Source: `arnold_pipelines/megaplan/cli/projection.py`
52. `04_CURRENT_SUBSTRATE/megaplan/auto.py`
    - Source: `arnold_pipelines/megaplan/auto.py`

These files show the exact carriers most relevant to route-authority relapse,
Plan Contract behavior, WBC evidence, resume, manifest translation,
projection-only state, and the scheduling-versus-routing boundary.

### 05_AUDITS — 10 files

53. `05_AUDITS/standardization-gap-final-report.md`
    - Source: `.tmp/workflow-standardization-gap/final-report.md`
54. `05_AUDITS/holistic-context-audit.md`
    - Source: `.tmp/workflow-standardization-gap/holistic-context-audit.md`
55. `05_AUDITS/oracle-stage1-delta.md`
    - Source: `.tmp/workflow-standardization-gap/oracle-stage1-delta.md`
56. `05_AUDITS/oracle-stage2-delta.md`
    - Source: `.tmp/workflow-standardization-gap/oracle-stage2-delta.md`
57. `05_AUDITS/oracle-control-plane-delta.md`
    - Source: `.tmp/workflow-standardization-gap/oracle-control-plane-delta.md`
58. `05_AUDITS/oracle-final-integration-review.md`
    - Source: `.tmp/workflow-standardization-gap/oracle-final-integration-review.md`
59. `05_AUDITS/oracle-answers-summary.md`
    - Source: `.tmp/workflow-standardization-gap/oracle-answers-summary.md`
60. `05_AUDITS/native-parity-feedback-audit.md`
    - Source: `.tmp/workflow-standardization-gap/native-parity-feedback-audit.md`
61. `05_AUDITS/platform-ticket-feedback-audit.md`
    - Source: `.tmp/workflow-standardization-gap/platform-ticket-feedback-audit.md`
62. `05_AUDITS/custody-overlap-audit.md`
    - Source: `.tmp/native-parity-sensecheck/custody-overlap-audit.md`

### 06_LOCAL_CUSTODY_CONTEXT_NOT_M11 — 6 files

63. `06_LOCAL_CUSTODY_CONTEXT_NOT_M11/NORTHSTAR.md`
    - Source: `.megaplan/initiatives/custody-control-plane/NORTHSTAR.md`
64. `06_LOCAL_CUSTODY_CONTEXT_NOT_M11/chain.yaml`
    - Source: `.megaplan/initiatives/custody-control-plane/chain.yaml`
65. `06_LOCAL_CUSTODY_CONTEXT_NOT_M11/briefs/m1.md`
    - Source: `.megaplan/initiatives/custody-control-plane/briefs/m1.md`
66. `06_LOCAL_CUSTODY_CONTEXT_NOT_M11/briefs/m2.md`
    - Source: `.megaplan/initiatives/custody-control-plane/briefs/m2.md`
67. `06_LOCAL_CUSTODY_CONTEXT_NOT_M11/briefs/m3.md`
    - Source: `.megaplan/initiatives/custody-control-plane/briefs/m3.md`
68. `06_LOCAL_CUSTODY_CONTEXT_NOT_M11/briefs/m4.md`
    - Source: `.megaplan/initiatives/custody-control-plane/briefs/m4.md`

The packet builder must add a warning README in this folder (or repeat the
root warning verbatim):

> **Historical/local context only — not completed M11.** This checkout's
> `custody-control-plane` has four milestones and describes canonical run-state
> resolution and repair custody. Native Parity assumes a later, externally
> completed eleven-milestone Custody/Run-Authority/WBC substrate. No completion
> manifest, public API inventory, controlled-writer proof, restore-monotonicity
> proof, or accepted M11 schema bundle for that prerequisite is present here.
> Do not infer those contracts from this folder and do not score their
> implementation as complete. Mark conclusions that depend on them
> **undetermined pending completed-M11 evidence**.

The four packet-only orientation files bring the total to 72 entries. If the
warning is a separate fifth packet-only file inside folder 06, either make
`KNOWN_UNKNOWNS.md` the physical source copied into both paths and record the
duplicate, or accept a 73-entry archive. Prefer 72 entries by placing the full
warning in root `KNOWN_UNKNOWNS.md` and a one-line pointer in the folder name
and root index.

## Exact `QUESTIONS.md` draft

```markdown
# Questions for the Oracle

Answer all three questions independently. Use concrete counterexamples and
cite packet-relative file paths plus line numbers. Distinguish current local
behavior, the accepted-but-missing completed-M11 prerequisite, the Stage-1
Native Parity target, and the Stage-2 Platformization target.

## 1. Can two conforming implementations still disagree?

Treat the revised representation report, Native Parity epic, golden trace
contract, and Platformization ticket as a specification given independently to
two implementation teams. Find every place where both teams could reasonably
claim compliance while producing incompatible observable behavior. Focus on
loop exits, root hosting, business versus lifecycle terminals, outcome
conditions, retries versus new generations, human suspension, agentic phases,
race/quorum precedence, cancellation, budget accounting, Custody release,
trace normalization, migration, and repair acceptance. For each ambiguity,
provide two conflicting compliant implementations and the smallest normative
rule that eliminates one.

## 2. Can a wrong implementation still pass every planned proof?

Design the smallest "green but wrong" implementation that passes every named
static check, golden scenario, negative mutation, local/installed comparison,
migration gate, and conformance receipt while still violating the North Star
in production. You may exploit missing scenario composition, proof adapters,
normalization, comparison provenance, omitted multiplicity, untested
interleavings, capability-profile exclusions, or differences between checkout,
wheel, cloud, and restored control-plane state. Identify exactly which current
gate falsely passes and propose one additional proof that makes the
implementation fail.

## 3. Is the plan executable on the real substrate in its current sequence?

Map every required contract and gate to the concrete current Arnold code and
the assumed completed-M11 interfaces. Identify hidden prerequisites, circular
dependencies, duplicate runtime planes, temporary dual authorities,
unavailable APIs, migration ordering hazards, and sprint workloads that cannot
realistically close within their assigned milestone. Determine whether any
requirement currently assigned to Native Parity S1-S7 or Platformization S1-S5
must move earlier, split, or become a prerequisite. Do not propose a new sprint
merely for conceptual neatness; require evidence that the existing owner cannot
safely deliver it.
```

## Concise `README.md` reviewer instructions

```markdown
# Arnold native-workflow Oracle review packet

Read in this order:

1. `00_START_HERE/KNOWN_UNKNOWNS.md` and `QUESTIONS.md`.
2. `01_END_STATE/megaplan-native-representation-report.md`.
3. Native Parity's North Star, canonical plan, chain, golden contract, and the
   seven active sprint briefs in `02_NATIVE_PARITY_EPIC/`.
4. The Platformization ticket in `01_END_STATE/`.
5. Contract owners in `03_CONTRACTS/`.
6. The as-built map and bounded source snapshot in `04_CURRENT_SUBSTRATE/`.
7. Prior audits in `05_AUDITS/`; use them as hypotheses, not authority.
8. Consult `06_LOCAL_CUSTODY_CONTEXT_NOT_M11/` only to understand why the real
   M11 prerequisite cannot be verified from this packet.

Rules for the review:

- Answer each question with the smallest concrete counterexample or trace, not
  a general endorsement.
- Cite packet-relative paths and line numbers for every material claim.
- Keep `current`, `completed-M11 assumption`, `Stage 1 target`, and `Stage 2
  target` distinct.
- Treat illustrative target APIs as syntax sketches unless a linked contract
  makes their behavior normative.
- Do not infer absent M11 APIs or proofs. Mark dependent findings
  `undetermined pending completed-M11 evidence`.
- For each gap, name the owning contract, earliest safe sprint, smallest
  normative amendment, and proof that would fail before the fix and pass after.
- For proposed sprint changes, explain why absorption is unsafe before adding
  or splitting a sprint.
- End with: verdict per question, blocking findings, bounded amendments,
  evidence still required, and an overall go/conditional-go/no-go judgment.
```

## Exact `KNOWN_UNKNOWNS.md` draft

```markdown
# Known unknowns and provenance limits

This packet is a 2026-07-21 repository snapshot. It intentionally separates
implemented local behavior from accepted future prerequisites and target
contracts.

1. **Completed M11 is absent.** Native Parity assumes
   `custody-control-plane-20260714` is fully complete before work begins, but
   this checkout contains only an older four-milestone
   `.megaplan/initiatives/custody-control-plane/`. The real M11 completion
   manifest, public APIs/schemas, controlled-writer inventory, shared action
   validator, WBC registries, repair revalidation contract, restore-resistant
   RA-fence/Custody-epoch proof, and migration guarantees are not available.
   Findings dependent on them are undetermined, not passes or failures.
2. **One Oracle answer was truncated.** The prior answer to the adversarial
   suspension/crash/redeployment question refers to transition items 2, 3, 5,
   and 7, but its numbered transition list was absent. The plans deliberately
   do not claim those unnamed cases are closed.
3. **DX thresholds are not all final.** Diagnostics and local/installed trace
   equivalence are blocking requirements, but final numerical compile/test and
   ten-task time-to-green budgets may still require measurement and ratification.
4. **Some arbitration is policy-declared.** Where the report delegates legal
   precedence to a closed `JoinPolicy`, terminal-arbitration policy, cancellation
   policy, or resource algebra, the Oracle should test whether the declaration
   schema is complete rather than assume a universal precedence.
5. **Open-ended event streams are deliberate future scope.** Stage 1 and Stage
   2 cover bounded loops, dynamic finite fanout, and declared durable agentic
   phases. Unbounded streaming/event-queue topology is intentionally unsupported.
6. **The source snapshot contains overlapping execution planes.** Inclusion of
   `arnold.execution`, `arnold.runtime`, and `arnold.pipeline.native` files is
   evidence of the current migration problem, not a declaration that all three
   are jointly authoritative or already converge on one validator.
7. **Target component APIs are illustrative.** Behavioral requirements in the
   report and ticket are the target; example package names, decorators, and
   method signatures do not become current public APIs merely by appearing in
   an example.
8. **Historical Custody files are not evidence of M11.** The folder
   `06_LOCAL_CUSTODY_CONTEXT_NOT_M11/` is supplied only to prevent accidental
   conflation and to show the local mismatch.
```

## Exclusions

Exclude these to keep the review determinate and the ZIP reasonably small:

- `cloud.yaml`, credentials, provider configuration, run state, logs, worktrees,
  caches, `.pyc`, `.git`, and plan execution artifacts.
- The superseded Native Parity `m1`–`m10` briefs; only active `s1`–`s7` briefs
  are included.
- Boundary-fixture corpora and the complete test tree. The golden contract and
  audit questions ask whether the planned proof is sufficient; dumping a large
  fixture corpus would obscure that review. The Oracle may name additional
  fixtures it needs.
- Raw subagent prompts/results, first-round sense-check reports, and the
  pre-mortem draft golden contract. Their durable conclusions are represented
  by the canonical golden contract and selected integrated audits.
- Older alignment/master plans, historical conformance-closeout reports, and
  other superseded plans whose claims the corrective epic explicitly replaces.
- Full Run Authority and WBC epic brief sets. The packet includes their
  canonical architecture/main contract and North Star/README; implementation
  sequencing relevant to Native Parity is already captured in the corrective
  plan and current code map.
- `manifest-identity-report.json` and generated conformance/evidence corpora,
  unless the reviewer later asks for a specific false-green artifact. They are
  outputs under challenge, not additional normative specifications.

Do not exclude the older local Custody files silently. Their explicit, warned
presence is safer than letting a reviewer infer that the chain referenced by
Native Parity is the unseen completed M11.
