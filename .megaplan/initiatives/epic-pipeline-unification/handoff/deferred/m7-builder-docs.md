# M7 — Builder documentation & onboarding (the outward surface)

**Status:** Milestone brief. Authoritative scope: `../pipeline-unification-EPIC.md` + design source
`../validation/edges/builder-docs.md`. Gated on M6 (the reference is generated from a surface still moving
through M2–M5c; `planning-as-composition` is only honest once M6 relocates planning).

## Outcome
An external developer — given only `docs/arnold/` + the scaffold, with **no access to SDK internals and no
SDK author in the loop** — can build, validate, and run a working non-planning module. This is the proof
that Arnold is a *builder SDK*, not an internal refactor: the docs describe a general surface, and a grep
proves a builder can succeed using **zero planning vocabulary**.

## Scope
- **`docs/arnold/authoring-guide.md`** (authored) — "build a module in N steps": `pipelines new` → manifest
  → pick a driver (substrate × topology) → declare Ports (`consumes`/`produces`) → compose nodes → write
  `SKILL.md` → `pipelines check` → `arnold run <module>`.
- **`docs/arnold/reference/`** (GENERATED from the typed surface; CI `--check` re-emit-and-diff joins the
  anti-drift gates): `pieces.md` (dispatch/state/emit/evidence/config + their Ports), `nodes.md` (the node
  library + macros, each with its declared Ports + stability tier), `drivers.md` (the substrate×topology
  matrix), `control-vocabulary.md` (`{succeeded,failed,escalated,blocked,awaiting_human}` + targets).
- **`docs/arnold/package-contract.md`** (generated field table + authored prose) — manifest schema:
  `name`, `driver`, `entrypoint`, declared `capabilities`, `SKILL.md` (required), `arnold_api_version`,
  trust tier.
- **`docs/arnold/examples/`** (code extracted from real in-tree packs, so it can't rot) — jokes (graph),
  the `select`-tournament (non-planning), and **planning-as-composition** (the beautiful example: planning
  reads as `clarify → produce → critique_loop → execute → verify → review` with its bindings).
- **`docs/arnold/skill-integration.md`** (authored) — per-package `SKILL.md` surfaced live via the registry
  (`read_skill_md`) vs the umbrella `~/.claude/skills/arnold*` generated skill; what's generated vs authored.
- **`docs/arnold/tooling.md`** (authored) — `pipelines new`/`check`/`doctor` as the builder's feedback loop
  (these land in M1; M7 documents them and wires the scaffold's emitted starter to be green by construction).

## Locked decisions
- **Generation rule:** if a fact is also a type/enum/manifest-field/node-signature, the doc is **generated**
  from it; prose explains *why/when*. So `reference/`, the manifest table, the checker error catalogue, and
  the umbrella skill are generated (CI-diffed); the authoring guide, examples, skill-integration, and
  contract prose are authored.
- Examples are **extracted from real packs**, never hand-maintained snippets.
- M7 is its own milestone (not folded into the already-overloaded M6); generators may be scaffolded
  incrementally beside each type addition in M2–M5c, but the committed, acceptance-tested set is M7.

## Open questions
- Does the umbrella skill (`~/.claude/skills/arnold*`) fully replace the megaplan-decision/observe/epic
  skills, or compose with them during the rename period?
- Where does per-module SKILL.md guidance end and umbrella how-to-build guidance begin (avoid duplication)?

## Constraints
- The reference generator must run against the FINAL (post-M6) typed surface; building it earlier means
  regenerating against a moving target. Keep the generator incremental but gate the acceptance on M6.

## Done criteria (testable)
- The external-builder acceptance test: `new` → wire `select`+`reduce` → author `SKILL.md` →
  `pipelines check` exits 0 → `pipelines doctor` shows `discovered ✓` → `arnold run` produces the winner
  artifact — performed against the docs only, with a grep asserting **no `GateRecommendation`/`STATE_*`/
  4-verdict** in the builder's module.
- `reference/` regenerates byte-identically in CI (drift gate green).
- Every `docs/arnold/examples/*` snippet is extracted from a real in-tree pack and runs.

## Touchpoints
`docs/arnold/` (new), `megaplan/_pipeline/registry.py` (read_skill_md / manifest), the `pipelines`
CLI group (M1), `megaplan/data/_*` + `~/.claude/skills/` (skill generation), the typed surfaces from M2–M5c.

## Anti-scope
No new SDK capability — M7 only documents + scaffolds what M1–M6 built. No change to the pieces.
