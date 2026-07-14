---
name: megaplan-epic
description: Run an epic — a chain of sprint-sized megaplans driven sequentially via `megaplan chain`. Use when the work is bigger than ~2 weeks and needs to be decomposed into multiple plans with state, ordering, and failure semantics handled by the harness.
---

# Megaplan Epic

An **epic** is work too big for a single megaplan, decomposed into an ordered chain of sprint-sized megaplans driven sequentially by `megaplan chain`. Each milestone in the chain is a full megaplan run (its own brief, plan, critique, execute, review); the chain handles ordering, state persistence, branch/PR lifecycle, and failure semantics.

If your work fits in one megaplan, you don't need this skill — read **megaplan-prep** and run a single sprint. Reach for the epic flow when the answer to "size each megaplan to ~2 weeks of work" is "this doesn't fit."

## When to reach for an epic

- **Scope is genuinely >2 weeks** and the deliverable is a single coherent thing (a feature, a migration, a cross-cutting refactor) — not separate unrelated efforts that should each be their own sprint.
- **Sequential dependencies between sprints** — milestone B needs the schema / interface / artifact that milestone A produces. Each handoff is a written artifact the next milestone can cite. For high-confidence handoffs, make the upstream chain produce a `completion-manifest.json` and make the downstream chain require it with `require_manifest: true`.
- **Multiple major architectural decisions** that each deserve their own brief + critique pass — pretending it's one sprint flattens decisions that need separate deliberation.
- **You want the chain to keep running unattended** — chains persist state and resume; one milestone failing doesn't lose the work the prior milestones produced.

## When NOT to use an epic

- **Single sprint fits the work.** If you can hold the whole scope in a 2-week brief, a chain just adds ceremony.
- **Exploration / discovery work** where you don't yet know the milestone breakdown. Run a single megaplan first to scope; then write the chain spec.
- **Truly independent sprints.** If sprints don't depend on each other, just run them sequentially as plain `megaplan init` calls — a chain spec is overhead with no benefit.
- **Anything where the milestone breakdown isn't pre-decided.** Chains run unattended through the declared spec; if you'd want to look at milestone 1's output and decide what milestone 2 should be, just run them as separate megaplans.

## Terminology — epic vs chain vs `megaplan epic`

Three names, three meanings:

- **Epic** (this skill) — the *concept*: multi-sprint work decomposed into a chain of megaplans.
- **`megaplan chain`** — the *imperative verb* that drives the flow. This is what you actually run.
- **`megaplan epic`** — a *data-admin verb* for snapshot / migrate / export of the editorial epic record. Not the orchestration entry point. Don't confuse the two.

## The spec — `chain.yaml`

A chain spec is a YAML file declaring the base branch, an optional seed plan, and an ordered list of milestones. Each milestone has its own rubric knobs (profile, robustness, depth, vendor, prep/feedback flags).

Store durable epic artifacts under `.megaplan/initiatives/<epic-slug>/`: put the executable `chain.yaml` at the initiative root and keep milestone brief files under `briefs/`. Single-plan idea briefs live at `.megaplan/initiatives/<slug>/briefs/<slug>.md`. `.megaplan/plans/` remains generated runtime state; `.megaplan/initiatives/` is the committed source material that creates runs.

```yaml
base_branch: main

# Required by default for epics. `brief epic` scaffolds this file.
anchors:
  north_star: NORTHSTAR.md

# Optional: a pre-existing plan whose output seeds the first milestone's repo state.
seed:
  plan: scoping-from-docs-20260415-0217

milestones:
  - label: m1-schema
    idea: .megaplan/initiatives/artifact-store/briefs/m1-schema.md
    branch: epic/m1-schema           # optional, informational for now
    profile: apex                    # tier 5 — schema everyone downstream builds on
    robustness: thorough
    depth: high

  - label: m2-storage
    idea: .megaplan/initiatives/artifact-store/briefs/m2-storage.md
    profile: premium                 # tier 4 — production migration logic
    robustness: thorough
    depth: high

  - label: m3-api
    idea: .megaplan/initiatives/artifact-store/briefs/m3-api.md
    profile: partnered               # tier 3 — once schema+storage are locked, the API is mechanical
    depth: medium
    anchors:
      north_star: m3-api-northstar.md # optional milestone extension; does not override the epic anchor

  - label: m4-docs
    idea: .megaplan/initiatives/artifact-store/briefs/m4-docs.md
    profile: directed                # tier 2 — docs benefit from a smart plan, cheap to execute

on_failure:
  abort: stop_chain                  # stop_chain | skip_milestone | retry_milestone
on_escalate:
  abort: stop_chain
merge_policy: auto                   # default: auto. Use for unattended/cloud epics so clean milestone PRs merge and the chain advances; use review/manual only when the user explicitly wants a human PR gate after every milestone.

driver:
  robustness: standard               # default if a milestone doesn't override
  auto_approve: true
  max_iterations: 60
  poll_sleep: 8.0
```

### North Star requirement

Epics require a top-level North Star by default. Put `NORTHSTAR.md` beside `chain.yaml` and declare it with `anchors.north_star: NORTHSTAR.md`. The North Star is the durable destination for the whole chain; milestone briefs narrow local scope, and milestone anchors may extend the destination for a slice, but they do not replace the top-level epic anchor.

If an epic truly has no durable end-state beyond its milestone briefs, opt out explicitly:

```bash
megaplan chain start --spec .megaplan/initiatives/my-epic/chain.yaml \
  --no-require-anchor \
  --missing-anchor-ack "Mechanical cleanup chain; no cross-milestone destination."
```

For non-interactive runs, encode the same decision in the spec:

```yaml
driver:
  require_anchor: false
  missing_anchor_ack: "Mechanical cleanup chain; no cross-milestone destination."
```

Do not rely on a colocated `NORTHSTAR.md` file without declaring it. Anchors are explicit and are snapshotted into each milestone plan at initialization.

### Milestone fields

| Field | Required | Meaning |
|---|---|---|
| `label` | yes | Short identifier (e.g. `m1`, `m2-storage`). Used in branch names and state files. |
| `idea` | yes | Path to the brief markdown file. Same as `megaplan init <idea>`. |
| `profile` | no | `solo` / `directed` / `partnered` / `premium` / `apex`. See megaplan-prep. |
| `robustness` | no | `bare` / `light` / `full` / `thorough` / `extreme`. Falls back to `driver.robustness`. |
| `depth` | no | `low` / `medium` / `high` / `xhigh` / `max`. |
| `vendor` | no | `claude` / `codex`. |
| `with_prep`, `with_feedback` | no | Booleans. |
| `phase_model` | no | List of `phase=spec` strings — the surgical escape hatch. |
| `deepseek_provider` | no | `direct` / `fireworks`. |
| `anchors` | no | Currently supports `north_star: <path>`. Milestone anchors extend the top-level epic North Star for that milestone. |
| `bakeoff` | no | Bake-off spec; rarely needed inside a chain. |
| `notes` | no | Free text retained in state for the audit trail. |

### Failure semantics

Two knobs control what the chain does when a milestone fails (`on_failure`) or hits an escalation (`on_escalate`):

- **`stop_chain`** — halt. The chain state is preserved; you re-run after fixing whatever broke.
- **`skip_milestone`** — record the milestone as skipped, continue to the next.
- **`retry_milestone`** — re-attempt the same milestone from scratch.

Default is `stop_chain` for both — failures should halt unless you've deliberately said otherwise.

### Launch preconditions and completion manifests

Use `launch_preconditions` when a chain must not start until a prerequisite file, source path, or chain completion proof exists. For ordinary dependent chains, `kind: chain_completed` verifies the prerequisite chain state, current `chain.yaml` hash, completed milestone labels, plan names, and merged PR evidence for review-merge chains.

For review-gated launch evidence, use an artifact check with `kind: review_log_clean` instead of only checking that a review log contains a marker string. It fails launch if the log contains an explicit `BLOCK` verdict or a `PASS WITH EDIT` section without an applied-edits note:

```yaml
launch_preconditions:
  - name: review log has no unaddressed blockers
    path: docs/arnold/my-review-log.md
    check:
      kind: review_log_clean
```

For high-confidence handoffs, add `require_manifest: true` to the `chain_completed` precondition:

```yaml
launch_preconditions:
  - name: platform substrate completed
    kind: chain_completed
    chain: .megaplan/initiatives/platform-substrate/chain.yaml
    require_manifest: true
```

The prerequisite chain must then write a content-addressed manifest beside its
`chain.yaml`:

```bash
megaplan chain manifest \
  --spec .megaplan/initiatives/platform-substrate/chain.yaml \
  --proof-map .megaplan/initiatives/platform-substrate/proof-map.json
```

The proof map is deliberate evidence, not a file-system scan. It maps each milestone label to the proof artifact paths that should be hashed into `completion-manifest.json`:

```json
{
  "m1-schema": ["docs/schema.md", "tests/test_schema.py"],
  "m2-storage": ["docs/storage-contract.md", "tests/test_storage.py"]
}
```

`require_manifest: true` is optional harness functionality, but use it when a downstream chain could waste work or drift if a prerequisite was only nominally complete. It blocks launch when the prerequisite manifest is missing, stale, has no proof artifacts, or no longer matches the current chain spec, North Star, milestone briefs, state records, PR metadata when applicable, or proof file hashes.

## Per-milestone rubric — same dials as megaplan-prep

Each milestone is a full megaplan. The three dials (`profile` / `robustness` / `depth`) apply per-milestone — see **megaplan-prep** for how to pick them. **Milestones in the same chain can be different tiers.** A typical epic has one or two high-stakes milestones at `premium` or `apex` and several mechanical milestones at `partnered` or `directed`.

The shorthand from megaplan-prep works for chain-spec notes: a milestone block annotated `# partnered//high +prep` in your chain.yaml comments tells the reader the intent at a glance.

## Running the chain

```bash
# Drive the full chain until completion (or failure). This requires top-level anchors.north_star by default.
megaplan chain start --spec /path/to/chain.yaml

# Explicitly opt out only when the chain has no durable epic destination.
megaplan chain start --spec /path/to/chain.yaml \
  --no-require-anchor \
  --missing-anchor-ack "Reason this epic does not need a North Star."

# Drive at most one pending milestone, persist progress, stop cleanly.
megaplan chain start --spec /path/to/chain.yaml --one

# Read-only: show current chain progress without driving anything.
megaplan chain status --spec /path/to/chain.yaml
```

### Flags worth knowing

- **`--one`** — single-step the chain. Useful when you want to inspect each milestone's output before letting the next one kick off, or when running under an external supervisor that wants tick-by-tick control.
- **`--no-git-refresh`** — skip the automatic base-branch checkout + pull that runs before each milestone. Use this on dev checkouts where chain shouldn't stomp the currently checked-out branch.
- **`--no-push`** — disable branch creation, PR creation, commits, and pushes. For local / no-network runs.

### State and resuming

Progress is persisted under `.megaplan/plans/.chains/<spec-stem>-<digest>.json`. The digest is computed from the resolved spec path, so the same spec resumes deterministically. To resume after an interruption, just re-run `megaplan chain start --spec <same path>` — the driver reads the state file, skips completed milestones, and picks up at the current one.

State persistence means:

- A crash, restart, or SIGINT mid-milestone doesn't lose prior milestones' work.
- Failed milestones can be re-attempted by deleting the milestone's plan directory and re-running — the chain will redrive that milestone.
- Editing the spec after milestones have completed only affects un-started milestones; completed entries in state stay as-is.

## Cloud chain mode

For chains that need to outlive your terminal session, run them inside `megaplan cloud` with `mode: chain` in `cloud.yaml`. The container drives the chain unattended; you observe via `megaplan cloud status` / `cloud logs` / `cloud attach`. See `docs/cloud.md` for the cloud reference.

Cloud epics should normally keep `merge_policy: auto` and `driver.auto_approve: true`. `merge_policy: review`/`manual` intentionally parks the chain at `awaiting_pr_merge` after every milestone PR; do not use it for unattended runs unless the user asked for human PR review gates.

When supervising a long cloud chain, follow the cadence in the main megaplan skill: check after launch, again after 10-15 min, then hourly.

## End-to-end example

Scope: build a new artifact store that downstream sprints will consume. ~5 weeks of work, four sequential milestones.

**1. Decompose into milestones.** Create an initiative directory under `.megaplan/initiatives/` and write one idea file per milestone under its `briefs/` directory, each sized to ~1 week:

```
.megaplan/initiatives/artifact-store/briefs/m1-schema.md  # schema + invariants
.megaplan/initiatives/artifact-store/briefs/m2-storage.md # storage layer against the schema
.megaplan/initiatives/artifact-store/briefs/m3-api.md     # public API over storage
.megaplan/initiatives/artifact-store/briefs/m4-docs.md    # docs + migration guide
.megaplan/initiatives/artifact-store/NORTHSTAR.md         # durable end-state intent
.megaplan/initiatives/artifact-store/chain.yaml           # chain spec
```

Each idea file is a full brief (see the "What goes in the brief" section of megaplan-prep) — outcome, scope, locked decisions, open questions, constraints, done criteria, touchpoints, anti-scope. Briefs are locked at init; later edits are not re-read.

**2. Write `chain.yaml`** (see the spec example above). Pick a tier per milestone:

- m1 schema → `apex` (kernel invariant, every downstream sprint depends on it)
- m2 storage → `premium` (production migration logic)
- m3 api → `partnered` (cross-cutting but mechanical once schema+storage are locked)
- m4 docs → `directed` (docs benefit from a smart plan; execution is cheap)

**3. Drive it.**

```bash
megaplan chain start --spec .megaplan/initiatives/artifact-store/chain.yaml
```

For a long unattended run, do this inside `megaplan cloud` so it survives the terminal.

**4. Observe.**

```bash
megaplan chain status --spec .megaplan/initiatives/artifact-store/chain.yaml
```

Shows current milestone index, current plan name, last state, completed milestones, and PR state if applicable.

**5. If a milestone fails or escalates**, the chain halts (with default `stop_chain`). Investigate the failing plan via `megaplan status --plan <name>` and `megaplan audit --plan <name>`. Once you've fixed the brief or escalated the rubric (via `megaplan override set-profile` etc.), re-run `megaplan chain start --spec` and the chain resumes.

## Promotion from a ticket

When a filed ticket grows in scope and warrants its own epic and initiative, promote it:

```bash
megaplan ticket promote <ticket_id> \
  --initiative-slug my-feature \
  --title "My Feature Epic" \
  --goal "One-line goal statement"
```

Promotion rules:

- **Search first, create second.** The promoter looks for an existing initiative with a matching slug. If one exists (e.g., a previously scaffolded initiative folder), it is reused. Only create when no match is found.
- **Distinct identities are preserved.** The ticket ULID is NEVER reused as the epic ID. The epic ID is the initiative slug. The ticket retains its own ULID and identity history — it is linked to the epic with `kind: promoted_to_epic` and a `provenance: promotion:<ticket_id>` traceability string.
- **Roadmap entry is replaced, not duplicated.** If the ticket was in the strategy roadmap (`.megaplan/STRATEGY.md`), its `- [ticket:<ULID>]` entry is replaced by a `- [epic:<slug>]` entry in the same horizon. Non-roadmap tickets are not forced into the strategy.
- **Strategy entries are pointers.** The roadmap bullet references the epic slug; it never copies the epic body, lifecycle status, plan details, or completion evidence.
- **Projection JSON is disposable.** After promotion, the strategy projection (`.megaplan/strategy.projection.json`) may be stale. Delete it and rebuild: `rm -f .megaplan/strategy.projection.json && megaplan strategy project --write`. Never edit the projection directly.

Use `--skip-strategy` if you want to promote without touching the roadmap.

## Common pitfalls

- **Don't decompose so finely that each milestone is <2 days of work.** A chain of 10 micro-milestones is harder to follow than 4 right-sized ones, and the harness overhead dominates the actual work.
- **Don't reach for a chain when you don't know the breakdown yet.** Run a scoping megaplan first; let it produce the milestone list; then write the chain spec.
- **Don't tier-flatten** — uniformly picking `partnered` for every milestone misses the point of the per-milestone rubric. Differentiate; the high-stakes milestone deserves a higher tier and the cheap milestone doesn't.
- **Don't bake-off inside a chain unless you genuinely need it.** Bakeoffs are independent runs; nesting them inside a chain spec multiplies the cost without typically producing useful signal.
- **Don't edit the spec mid-flight expecting completed milestones to re-run.** State is sticky for completed entries by design — that's how resume works.
- **Don't leave `NORTHSTAR.md` undeclared.** A file beside `chain.yaml` is not auto-discovered. Declare `anchors.north_star: NORTHSTAR.md`, or explicitly opt out with `driver.require_anchor: false` plus `driver.missing_anchor_ack`.
- **Don't treat the strategy projection as authoritative.** `.megaplan/strategy.projection.json` is a deterministic, disposable projection generated from `.megaplan/STRATEGY.md`. Delete and rebuild it; never edit it directly.
