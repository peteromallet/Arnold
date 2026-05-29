# Human blockers — edges (design/build-time) + runtime gates — pre-made to ZERO

**Status:** validation artifact, 2026-05-29. Goal: drive human blockers to zero. Every decision below is
converted to one of: **(a) pre-made DEFAULT**, **(b) MACHINE-ENFORCED GATE** (auto-proceed green / auto-halt
or auto-escalate red, never waits), or **(c) AUTO-ESCALATION policy** (retry → stronger model → skip+flag).
`must_ask_peter=false` everywhere unless a genuinely irreversible strategy/taste call (justified inline).

Sources: `briefs/validation/edges/{builder-docs,cli-migration,edges-map}.md`,
`megaplan/handlers/{execute,gate,override,verifiability,plan}.py`, `megaplan/cli/resolutions.py`,
`megaplan/auto.py`, `megaplan/chain/__init__.py`, `briefs/epic-pipeline-unification/m6-megaplan-as-module.md`.

---

## A. DESIGN / BUILD-TIME blockers (an agent executing the milestone would stall here)

### A1. cli-migration "FUZZY" decisions — already resolved in writing
`briefs/validation/edges/cli-migration.md` enumerates 3 FUZZY edges. They are **pre-decided** in that doc;
the only residual blocker is "did anyone notice they're decided." Pre-made defaults:
- **auto split** (umbrella loop + planning-default): DEFAULT = ship `arnold auto [<module>]`, `<module>=planning`
  during deferred-rename. Decided (cli-migration §1).
- **override split** (umbrella control vs planning transitions): DEFAULT = `abort/add-note/set-robustness/
  set-profile/set-model` umbrella; `force-proceed/replan/recover-blocked` planning. Decided (§2).
- **resume home**: DEFAULT = stays planning MODULE (`arnold planning resume`). Decided (§3).
- Mechanism to keep it from re-stalling: **machine-gate** = the `chain.yaml↔EPIC↔briefs` lint + parser-snapshot
  test (`c493f629`) already in the anti-drift family; add the cli-migration table as a fixture the snapshot
  diffs against so a drift auto-fails CI rather than re-opening the question.

### A2. Milestone-ownership / dependency-order TBDs (which milestone owns each command move)
cli-migration "Dependency order" + edges-map verdicts leave several "needs M5c / M4 / its own milestone"
open. **DEFAULT:** adopt the critical-path block in cli-migration §"Dependency order" verbatim as binding
(M1→M3→M4→M5c→M5d→M6). No agent decides ordering; it reads the block.

### A3. Builder-docs "needs its own milestone — propose M7"
`builder-docs.md:198` proposes M7. **DEFAULT = accept M7, gated on M6** (the doc's own reasoning: reference is
generated from a surface still moving through M2–M5c/M6). Machine-gate: the **M7 acceptance test is executable**
(`builder-docs.md:214-236`) — external builder ships select-tournament toy, `arnold pipelines check` exits 0,
grep asserts zero planning vocabulary. Auto-proceed on green, auto-fail on red.

### A4. Generated-vs-authored doc classification (per doc in the SET)
Seven docs each tagged generated/authored (`builder-docs.md` table :180-189). **DEFAULT = the table is the
decision.** Machine-gate: generated docs gain `--check` CI mode (re-emit + diff vs committed), joining the
anti-drift gates — drift auto-fails, never asks a human "is this stale?".

### A5. Edge contracts that are "FUZZY, named but not given a fail-loud check" (edges-map 1–9e)
Each edge in edges-map already has **owner + milestone + "Plan must"** spelled out. The blocker is only that
"FUZZY" reads as undecided. **DEFAULT = the "Plan must" line IS the decision for each edge.** Convert each to a
**machine-gate** so no human adjudicates "is this edge crisp now":
- Edge 3/9a (STATE_* leak): **CI grep gate** = ZERO `GateRecommendation`/`STATE_*` as mechanism in SDK modules
  (`EPIC.md:140`). Auto-fail on any leak.
- Edge 4 (Port): **`arnold pipelines check`** static linter fails `build()` on missing/typo'd/mistyped dep;
  delete the `v1.md` silent fallback (`step_helpers.py:104`) — turns a silent default into a loud machine-halt.
- Edge 5 (StateDelta): **parity test** {5 robustness}×{prep,feedback}×{states}×{verdicts} as the M3 gate.
- Edge 6 (trust/import seam): see B-runtime R10 below (the operator-trust decision).
- Edge 9d (realized graph): the parity test above is the gate.
- Edge 9e (strangler): **standing behavioral-replay + substrate-swap oracles** every milestone; chain.yaml
  regenerated as one triple. Auto-fail on divergence.
All `must_ask_peter=false`: each is a verifiable invariant, not a taste call.

### A6. Version/stability tier assignment (edge 8) — "M5 'stable' contradicts EPIC 'keep reshaping'"
**DEFAULT = reserve `arnold_api_version` now + tier every `patterns.py` node `stable|provisional|internal`,
default `provisional`** (so the epic keeps reshaping freely; only nodes explicitly promoted carry a SemVer
contract). One-line rule removes the contradiction without a meeting. Machine-gate: discovery checks
`arnold_api_version` against supported range and refuses incompatible-major **without importing**.

---

## B. RUNTIME human-gates baked into the PRODUCT (the product waits on a person here)

### R1. Execute approval gate (`handlers/execute.py:108-115`)
Execute refuses without `auto_approve` or `--user-approved` → "orchestrator must confirm with the user."
**DEFAULT = `auto_approve=true` is the autonomous-platform default**; the gate is preserved only as an
**opt-in** for interactive use. Machine-gate replaces the human confirm: the **parity/contract gate
(`run_gate_checks` + hard preflight)** already decides safety; auto-proceed when the gate's
`recommendation==PROCEED && passed`. No human stands between gate-green and execute.
- `must_ask_peter=false`: spending/scope safety is enforced by the gate + budget authority, not by a person.

### R2. Gate ESCALATE → routes to `override add-note` (human) (`handlers/gate.py:563-564`, `:568`)
Gate ESCALATE/unknown-recommendation returns next_step `override add-note` — a human action. **AUTO-ESCALATION
policy** instead: `auto.drive` default `on_escalate="force-proceed"` (`auto.py:1159,1674`) already auto-proceeds;
unresolved correctness/security flags auto-route to STATE_BLOCKED (machine-halt, see R3), cosmetic flags
auto-force-proceed-with-audit-note (`gate.py:467-472`). Strengthen: on ESCALATE, **retry once with a stronger
gate model (auto-escalation tier) before force-proceed**, so quality isn't merely bulldozed.
- `must_ask_peter=false`: force-proceed-with-debt is reversible (logged to debt registry).

### R3. Gate BLOCKED on open correctness/security flag (`handlers/gate.py:458-466`)
Plan set to STATE_BLOCKED "for human review." **MACHINE-GATE, not a human:** STATE_BLOCKED is the auto-halt on
RED (unresolved correctness/security). Convert the recovery from "wait for human" to **auto-escalation**:
auto-route the blocked plan back through one **revise+stronger-model** round; if still red, auto-fail the
milestone and let chain `on_failure` policy act (R8). The block becomes a bounded retry, not a parking spot.
- `must_ask_peter=false`: a persistently-red correctness flag is a verifiable failure → chain policy decides.

### R4. Prep clarify halt → STATE_AWAITING_HUMAN (`handlers/plan.py:20-42`, `auto.py:1390-1407`)
Prep halts on blocking `open_questions` awaiting `override resume-clarify`. **DEFAULT = `prep_clarify` stays
`true` but the halt auto-resolves via the prep-fanout research dossier** (memory: research IS the plan-quality
bottleneck): on a blocking ambiguity, **auto-escalate to a research subagent** that answers the question from
the repo/web, writes the answer as a `--source driver` note, and auto-runs `resume-clarify`. Only escalate to
human if the research agent itself returns "unknowable without a product owner."
- `must_ask_peter=false` in the common case; the rare residual is a genuine product-intent gap (see C1).

### R5. verify-human gate → STATE_AWAITING_HUMAN_VERIFY (`handlers/verifiability.py:215`, `execute.py:248`)
Deferred-MUST success criteria require a human `--pass/--fail`. **DEFAULT = at finalize, classify criteria and
prefer machine-verifiable evidence (`classify_criteria`); for anything classed human-only, auto-attempt an
oracle/attestation** (`run(cmd)→{exit,stdout,stderr}`, the evidence piece) before deferring. Machine-gate:
criteria with a runnable check auto-verify; only criteria with **no possible automated oracle** defer, and those
get an **auto-escalation** to a stronger reviewer model that records a verdict + evidence. Net: AWAITING_HUMAN_VERIFY
fires only for criteria that are physically un-automatable (e.g. "looks good to a human eye").
- `must_ask_peter=false`: the default verdict-by-evidence is recorded and reversible; bare robustness already
  ships a stub verdict (`execute.py:248-263`) proving auto-resolution is the established pattern.

### R6. user-action resolve (`cli/resolutions.py:29`) — `created_by` defaults to "operator"
Human resolves finalize prerequisite actions. **DEFAULT = each user_action carries a `fallback_mode` and the
finalize emitter MUST populate it** (the schema already supports `fallback_mode`); auto.drive auto-applies the
fallback resolution (`build_resolution_event` with `created_by` = the autonomous actor id via
`MEGAPLAN_ACTOR_ID`). Machine-gate: a user_action with **no fallback_mode fails finalize loud** (forces the
planner to pre-decide the fallback), so nothing reaches runtime without an auto-resolution.
- `must_ask_peter=false`: the fallback is decided at plan-time and logged.

### R7. quality-gate resolve (`cli/resolutions.py:177`) — quality blocker needs human resolution
Same shape as R6 for quality blockers. **AUTO-ESCALATION:** `evaluate_blocker_recovery` already distinguishes
non-terminal blockers; auto.drive auto-resolves non-terminal blockers with a recorded `fallback_mode`, and
**auto-escalates terminal ones to a stronger execute/review model** for one bounded retry before failing the
milestone (then chain policy R8). No human in the loop on green or on bounded-retry.
- `must_ask_peter=false`.

### R8. Chain `on_failure` / `on_escalate` default = `stop_chain` (`chain/__init__.py:295-296,347-348`)
Conservative defaults halt the whole chain for a human. **DEFAULT for autonomous epics = set
`on_escalate: force-proceed` (already the driver default `:308`) and `on_failure: retry_milestone` then
`skip_milestone`** rather than `stop_chain`, encoded in the autonomous-epic `chain.yaml` template. Machine-gate:
`retry_milestone` bounded (re-run with stronger profile) → `skip_milestone` + flag to debt registry → only
`stop_chain` if a hard-preflight invariant fails (project dir missing/unwritable — genuinely unrecoverable).
- `must_ask_peter=false`: choosing retry/skip over stop is reversible; the default ships in the template, the
  human override (`stop_chain`) remains available for interactive runs.

### R9. Chain `merge_policy: "auto"` default (`chain/__init__.py:297,349`) + `review_policy clean_milestone_pr: auto`
Default is already `auto` (auto-merges clean milestone PRs) — **good, keep**. The blocker is the *opt-in*
`merge_policy: review` value (a human reviews/merges). **DEFAULT for autonomous epics = never set `review`;**
rely on the **machine-gate** = the milestone's own gate + review phase + the strangler/oracle invariants as the
merge predicate. A clean-gate + green-oracle PR auto-merges; a red one auto-halts the milestone (R8), it does
not queue for human review.
- `must_ask_peter=false`: PR isolation/merge correctness is verified by gate+oracle, not eyeballs. (Memory note:
  carried-WIP breaks PR isolation — handled by running off clean main, a machine precondition, not a human gate.)

### R10. Discovery trust-tier "operator decides in_tree/blessed/quarantined" (`m6...md:46-49`, edges-map edge 6)
The one design point that reads as inherently human ("a human operator looks at a package and decides blessed").
**Converted to a MACHINE-GATE + DEFAULT, not a human:**
- **DEFAULT trust tier = `quarantined`** for any package discovered outside the repo tree (`~/.megaplan/pipelines`);
  `in_tree` only for packages physically inside the repo (a path fact, not a judgment).
- **Machine-gate (the real safety):** discovery is **manifest-first and non-executing** — read
  `name/driver/entrypoint/capabilities/SKILL/arnold_api_version` WITHOUT importing; `exec_module` deferred to
  selected-to-run and run **only** under the SDK-assigned `tenant_id` + per-package quota sub-budget +
  capability allowlist. A `quarantined` package runs **sandboxed with zero ambient capability** unless its
  manifest's declared capabilities are a subset of an allowlist — an automatic subset check, no human "bless".
- **Auto-escalation for promotion:** `quarantined→blessed` happens automatically when the package passes the
  graph-level abuse oracle (`unknown-unknowns/abuse-supply-chain.md` — the manifest-capability check is at the
  wrong layer; the *graph* must be evaluated). Promotion is a passed-test event, not a human signature.
- `must_ask_peter=false`: "blessed" is redefined from a human signature to "passed the automated graph-abuse
  oracle + capability-subset check." This removes the only human in the trust path. **Justification it CAN be
  defaulted:** the danger (ACE on import) is killed by non-executing discovery + sandbox+quota, which are
  deterministic machine controls; the trust *tier* then just selects a sandbox policy, which a subset check
  computes. (See C2 for the single residual taste call.)

### R11. override `force-proceed` strict-notes human gate (`handlers/override.py:218-241`, `auto.py:1705-1725`)
strict_notes mode blocks force-proceed if unabsorbed user notes exist or gate ESCALATEd without `--user-approved`;
auto.drive then **halts for a human** ("force-proceed blocked by strict-notes — human required", `auto.py:1717`).
**DEFAULT = `strict_notes=false` for autonomous runs** (it's already off by default; on only for metaplan/doc
mode). When off, force-proceed auto-applies. For the metaplan/doc case, **auto-escalation:** auto-run `revise`
to absorb the notes (turning the human gate into a machine step) before force-proceed.
- `must_ask_peter=false`: note-absorption is a mechanical revise; only metaplan/doc opt into strictness.

### R12. `recover-blocked` requires human `--reason` + per-blocker resolution (`handlers/override.py:431-522`)
A human must supply `--reason` and resolve each blocker non-terminal. **AUTO-ESCALATION:** auto.drive feeds the
`phase_result.blocked_tasks` to `evaluate_blocker_recovery`; for **external_error** blockers it auto-routes to
`megaplan resume` (already the prescribed path, `override.py:467-488`) — pure machine retry. For **task/quality**
blockers, an **auto-recovery agent** generates the `--reason` + non-terminal classification from the blocker
details and re-runs; if it cannot, the milestone fails into chain policy (R8). No human types `--reason`.
- `must_ask_peter=false`: the recovery agent's reason is recorded and the action is reversible.

### R13. Tiebreaker pending → "run tiebreaker-run" (`auto.py:1418-1426`, gate TIEBREAKER `:565`)
Gate TIEBREAKER parks the plan for a human to launch the tiebreaker. **MACHINE-GATE / AUTO:** auto.drive should
**auto-invoke `tiebreaker-run`** on STATE_TIEBREAKER_PENDING (researcher/challenger run is itself an automated
phase), then resume. Memory note honored: the gate silently auto-downgrades TIEBREAKER→ITERATE when schema
fields are missing — fix that to a loud auto-escalation (retry gate with stronger model) rather than a silent
downgrade, so the tiebreaker either runs or escalates, never stalls.
- `must_ask_peter=false`: tiebreaker is an automated adjudication phase.

---

## C. The genuinely-irreversible residuals (aim: ZERO; here are the only candidates, all defaulted)

### C1. Product-intent ambiguity that NO research can resolve (residual of R4)
If prep's research subagent returns "this requires a product-owner decision that is unknowable from repo/web/
spec" (e.g. "should the tournament rank by speed or by quality — there is no stated preference anywhere").
**Pre-made DEFAULT to avoid the stall:** auto-pick the **most reversible / most conservative** interpretation,
record it as an assumption note + a debt-registry flag, and proceed. The human can override post-hoc; the build
never waits.
- `must_ask_peter=false` (defaulted to reversible-choice + flag). Listed only because it is the *closest* thing
  to a true taste call, and the default explicitly converts it to a logged, reversible assumption.

### C2. First-ever "bless a NEW capability class" (residual of R10)
The very first time a community package declares a capability the allowlist has never seen (a new capability
*kind*, not a new package). The subset check can't auto-approve an empty-set baseline. **Pre-made DEFAULT:**
new capability kinds default to **DENY** (package stays quarantined, runs without that capability); the platform
ships with an explicit, version-controlled capability allowlist that grows only via a normal code change (which
is itself gated by the epic's own machine gates). So even this is a code-review event on the SDK, not a runtime
human gate.
- `must_ask_peter=false`: deny-by-default is safe and reversible; expanding the allowlist is ordinary
  versioned development, not an operator decision at runtime.

**Net: zero `must_ask_peter=true`.** Every design-time TBD reads its decision from an existing brief table or a
machine gate; every runtime human-gate is converted to auto_approve-default + gate-as-predicate, an
auto-escalation ladder (retry → stronger model → skip+flag), or a non-executing/sandboxed machine control.
