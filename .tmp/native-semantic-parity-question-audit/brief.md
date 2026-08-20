# DeepSeek Audit: Native Semantic Parity Plan Assumption Questions

Working directory: `/Users/peteromalley/Documents/Arnold`

You are an independent DeepSeek codebase auditor. Do not modify files.

Goal: sense-check the 10 questions below against the current repository and the current plan:

`docs/arnold/megaplan-native-semantic-parity-master-plan.md`

For each question:

1. Inspect source and run small read-only commands where useful.
2. Answer the question with file:line and/or command-output evidence.
3. State whether your answer agrees with, weakens, or contradicts the plan assumption.
4. If it weakens/contradicts the plan, propose the smallest concrete plan amendment.

Be strict. Prefer “unknown from repo” over narrative confidence. Do not rely on previous reports unless you verify them.

Output format:

```markdown
# Native Semantic Parity Question Audit

## Executive Verdict
- Overall: ...
- Highest-risk disagreements: ...

## Q1 ...
- Answer:
- Evidence:
- Plan assumption status: agrees | weakens | contradicts
- Amendment if needed:

...

## Required Plan Patches
1. ...

## Commands Run
...
```

Questions:

1. What does `parallel_map` in `workflow.pypeline` lower to today — a real fanout IR, or metadata passthrough that the manifest backend ignores? More broadly: does the source compiler support suspension points, dynamic fanout over runtime lists, and loop policies with typed exits — the constructs S2–S5 require? The original representation report listed dynamic parallel map and loop expressiveness as missing substrate.
   - Plan assumption tested: extraction sprints are extraction, not compiler development.
   - Bad answer implication: S2–S5 need compiler-feature predecessor tasks; estimates roughly double and S1b scope changes.

2. Is there a single seam for worker/model invocations that record/replay can intercept? Or do handlers reach models through heterogeneous paths — direct API, CLI subprocess, “fresh sessions” forced by execute handler? Check what the auto-drive characterization corpus actually replays today.
   - Plan assumption tested: replay harness amendment is S1a-sized.
   - Bad answer implication: if invocation paths are heterogeneous, harness is an epic of its own; consider narrowing baselines to state-transition/route-label assertions rather than full artifact hashes.

3. Is the existing strict checker structural or token-based? Feed or reason about a synthetic file with correct constructs under different names: would it pass? Are row IDs hardcoded in `_implemented_front_half_rows`, meaning the row registry lives in checker code, so adding ~22 rows means editing the compiler, which conflicts with gate-layer immutability?
   - Plan assumption tested: structural rejection extends existing checker rather than replacing it; registry can be data (`megaplan_semantic_rows.yaml`) not code.
   - Bad answer implication: S1a must refactor rows out of `source_compiler.py` into data first.

4. Can the DSL/manifest runtime execute a step with no `handler_ref` at all? Is component consultation in `build_pipeline()` an accident, or is `handler_ref` structurally required by the `Step`/runtime contract?
   - Plan assumption tested: “handlers become phase bodies” is achievable in existing runtime.
   - Bad answer implication: native-phase dispatch mechanism is hidden predecessor to S1b.

5. What happens to in-flight serialized plans across a topology change? Do suspended plans (`awaiting_human_verify`, blocked states) serialize route/step IDs that must survive sprint boundaries? Is there any state-migration machinery?
   - Plan assumption tested: rollout safety; parity checks assume label compatibility suffices.
   - Bad answer implication: add per-sprint gate to resume pre-sprint serialized fixture on post-sprint code; if no migration story, epic needs drain-or-migrate policy.

6. Where do `COMMAND_HANDLERS` live, and is `arnold/cli` a semantic surface? Also do any other pipelines or shared runtime modules import Megaplan `components.py`? Run a reverse-dependency check before deletion sprints.
   - Plan assumption tested: scan-root completeness; deleting route bindings breaks nothing outside Megaplan.
   - Bad answer implication: add roots/exemptions; if other packages import Megaplan components, S2–S6 deletion lists need cross-package impact entries.

7. Can every split-outcome scenario be driven headlessly today? Destructive-approval denial, resume-clarify injection, tiebreaker decisions — do these have a programmatic control-plane API, or do they assume interactive CLI?
   - Plan assumption tested: baseline capture and scenario gates can run in CI.
   - Bad answer implication: harness needs control-injection API first; scope it into S1a explicitly.

8. Do artifacts embed nondeterminism — timestamps, UUIDs, absolute paths, model/session IDs — that would break hash-pinned baselines? Is there existing canonicalization?
   - Plan assumption tested: hash-pinned baseline comparison is meaningful.
   - Bad answer implication: baselines need canonicalization layer to strip/normalize volatile fields.

9. Run proposed carrier-scan heuristics manually once, package-wide. Is the true carrier count ~30 matching row registry scale, or ~300?
   - Plan assumption tested: registry reconciliation is tractable without exemption inflation.
   - Bad answer implication: route-shaped mapping heuristic needs tiering, route-authoritative vs descriptive metadata, before reconciliation gate is realistic.

10. Does `.pypeline` source actually ship in the built package? Check package data/manifest config.
    - Plan assumption tested: checker `--mode installed-package` can inspect source.
    - Bad answer implication: fix packaging in S1a, or installed-package mode silently checks nothing.

Important:
- Cite exact source lines. Use `nl -ba`, `rg`, `sed`, `python - <<'PY'` read-only snippets as needed.
- Keep the final answer under ~3500 words.
- Do not edit files.
