You are an expert editor. Revise the following writing to make it clearer, more concise, and more compelling.
You do NOT have to follow every critique blindly; use your judgment and preserve the author's intent.

--- ORIGINAL ---

---
name: new arnold pipeline
description: Scaffold and wire a new Megaplan-style Arnold pipeline from scratch.
---

# Creating a new Arnold pipeline (Megaplan-style)

Use this skill when the user wants a new pipeline in the Arnold harness that follows the same planning topology as Megaplan:

```
prep → plan → critique → gate → revise → finalize → execute → review
                              ↑___________|
```

## 1. Scaffold the module

From the repo root:

```bash
python -m arnold pipelines new my-planning-pipeline --driver graph
```

This creates:

```
arnold/pipelines/megaplan/pipelines/
├── my_planning_pipeline.py                 # the Python module
└── my-planning-pipeline/
    └── SKILL.md                            # agent-facing docs
```

The CLI-visible name is the hyphenated form: `my-planning-pipeline`.

## 2. Replace the skeleton `build_pipeline()`

Open `arnold/pipelines/megaplan/pipelines/my_planning_pipeline.py` and paste the following complete module.

```python
"""Python composition of the my-planning-pipeline pipeline."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path

from arnold.pipelines.megaplan._pipeline.patterns import (
    critique_revise_gate_loop,
    phase_zero_gate,
)
from arnold.pipelines.megaplan._pipeline.types import (
    Edge,
    Pipeline,
    PipelineVerdict,
    Stage,
    StepContext,
    StepResult,
)


# ── Module-level contract fields (required + recommended) ────────────────

name: str = "my-planning-pipeline"
description: str = "A minimal planning pipeline with prep, plan, critique, gate, revise, finalize, execute, review."
default_profile: str | None = None          # required by the static manifest reader
supported_modes: tuple[str, ...] = ("code",)  # required by the static manifest reader
driver: tuple[str, str] = ("graph", "dispatch+emit")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("planning",)


# Directory where prompts and other resources live.
_PIPELINE_DIR: Path = Path(__file__).parent / "my-planning-pipeline"


# ── Step implementations ─────────────────────────────────────────────────
# Each step must expose `name`, `kind`, and a `run(ctx: StepContext) -> StepResult`
# method.  In a real pipeline these runs call models, read/write artifacts,
# and inspect ctx.inputs / ctx.state.


@dataclass
class PrepStep:
    name: str = "prep"
    kind: str = "produce"

    def run(self, ctx: StepContext) -> StepResult:
        # Real work: inspect repo, gather context, write a prep artifact.
        return StepResult(next="plan", state_patch={"prepped": True})


@dataclass
class PlanStep:
    name: str = "plan"
    kind: str = "produce"

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(next="critique", state_patch={"planned": True})


@dataclass
class CritiqueStep:
    name: str = "critique"
    kind: str = "judge"

    def run(self, ctx: StepContext) -> StepResult:
        iteration = int(ctx.state.get("iteration", 0))
        recommendation = "iterate" if iteration < 1 else "proceed"
        return StepResult(
            next="gate",
            state_patch={
                "iteration": iteration + 1,
                "gate_rec": recommendation,
            },
        )


@dataclass
class GateStep:
    name: str = "gate"
    kind: str = "decide"

    def run(self, ctx: StepContext) -> StepResult:
        rec = ctx.state.get("gate_rec", "proceed")
        return StepResult(
            next="gate",
            verdict=PipelineVerdict(score=0.5, recommendation=rec),
        )


@dataclass
class ReviseStep:
    name: str = "revise"
    kind: str = "produce"

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(next="critique")


@dataclass
class FinalizeStep:
    name: str = "finalize"
    kind: str = "produce"

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(next="execute")


@dataclass
class ExecuteStep:
    name: str = "execute"
    kind: str = "produce"

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(next="review")


@dataclass
class ReviewStep:
    name: str = "review"
    kind: str = "judge"

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(next="halt")


# ── Pipeline assembly ────────────────────────────────────────────────────

def build_pipeline() -> Pipeline:
    """Return the canonical my-planning-pipeline graph."""

    prep_stage = phase_zero_gate(
        PrepStep(), name="prep", on_pass="plan", on_fail="halt"
    )

    plan_stage = Stage(
        name="plan",
        step=PlanStep(),
        edges=(Edge(label="critique", target="critique"),),
    )

    cycle = critique_revise_gate_loop(
        CritiqueStep(),
        GateStep(),
        ReviseStep(),
        on_proceed="finalize",
        on_iterate="revise",
        on_tiebreaker="halt",
        on_escalate="halt",
        revise_target="critique",
    )
    # Guard the critique→gate→revise cycle so validation does not complain
    # about an unguarded loop.  The lambda receives the executor's loop state.
    cycle["gate"] = dataclasses.replace(
        cycle["gate"],
        loop_condition=lambda loop_state: int(
            getattr(loop_state, "iteration", 0) or 0
        )
        >= 3,
    )

    finalize_stage = Stage(
        name="finalize",
        step=FinalizeStep(),
        edges=(Edge(label="execute", target="execute"),),
    )
    execute_stage = Stage(
        name="execute",
        step=ExecuteStep(),
        edges=(Edge(label="review", target="review"),),
    )
    review_stage = Stage(
        name="review",
        step=ReviewStep(),
        edges=(Edge(label="halt", target="halt"),),
    )

    return Pipeline(
        stages={
            "prep": prep_stage,
            "plan": plan_stage,
            "critique": cycle["critique"],
            "gate": cycle["gate"],
            "revise": cycle["revise"],
            "finalize": finalize_stage,
            "execute": execute_stage,
            "review": review_stage,
        },
        entry="prep",
    )


__all__ = [
    "build_pipeline",
    "name",
    "description",
    "default_profile",
    "supported_modes",
    "driver",
    "entrypoint",
    "arnold_api_version",
    "capabilities",
]
```

### What the pieces mean

| Field | Required? | Notes |
|---|---|---|
| `name` | **yes** | CLI-visible name. Must match the hyphenated form derived from the file name. |
| `description` | **yes** | One-liner shown in `arnold pipelines list`. |
| `arnold_api_version` | **yes** | Keep `"1.0"` unless targeting a newer SDK. |
| `capabilities` | **yes** | Non-empty tuple of labels. |
| `driver` | **yes** | Use `("graph", "dispatch+emit")` for graph-driven pipelines; `"in_process"` for simple in-process graphs. |
| `entrypoint` | **yes** | Bare name `"build_pipeline"` or fully-qualified `"module:name"`. |
| `build_pipeline` | **yes** | Nullary callable returning a `Pipeline`. |
| `default_profile` | recommended | Declare even as `None`; the static manifest reader requires it. |
| `supported_modes` | recommended | Declare even as `()`; the static manifest reader requires it. |

## 3. Add prompts (optional)

For model-backed stages, place prompt files next to `SKILL.md`:

```
arnold/pipelines/megaplan/pipelines/my-planning-pipeline/
├── SKILL.md
└── prompts/
    ├── plan.md
    ├── critique.md
    └── execute.md
```

Prompt paths are resolved relative to `_PIPELINE_DIR`.  A stage can read a prompt directly:

```python
prompt_text = (_PIPELINE_DIR / "prompts" / "plan.md").read_text()
```

Or use the built-in `AgentStep` / `PipelineBuilder.agent(..., prompt="prompts/plan.md")` machinery.  See `arnold/pipelines/megaplan/_pipeline/steps/agent.py` and the `creative` pipeline for real examples.

## 4. Add a profile (optional)

If you want `--profile my-planning-pipeline:default` to work, create:

```
arnold/pipelines/megaplan/pipelines/my-planning-pipeline/profiles/default.toml
```

```toml
[profiles.default]
prep     = "hermes:deepseek:deepseek-v4-pro"
plan     = "claude"
critique = "hermes:deepseek:deepseek-v4-pro"
execute  = "hermes:deepseek:deepseek-v4-pro"
review   = "claude"
```

The keys are your stage names.  Values are agent specs understood by the Megaplan key pool (`claude`, `codex`, `hermes:deepseek:deepseek-v4-pro`, etc.).

## 5. Validate and run

```bash
# Must pass with zero defects.
python -m arnold pipelines check my-planning-pipeline

# List it.
python -m arnold pipelines list

# Run it.
python -m arnold run my-planning-pipeline "Implement a dark mode toggle"
```

`arnold run` maps the positional argument to `ctx.inputs["draft"]`.

## 6. Common gotchas

- **No leading underscore.** Files or directories starting with `_` or `.` are silently skipped by the discovery scanner. The `_template` package is named that way on purpose.
- **`build_pipeline()` must be callable with no arguments.** The registry calls it as `builder()` during discovery and validation.
- **Declare `default_profile` and `supported_modes` even if empty.** The runtime validator only warns about them (`info:`), but the static manifest reader rejects packages that omit them.
- **Guard every cycle.** If your graph has a back-edge, attach a `loop_condition` to a stage in the cycle, otherwise `arnold pipelines check` fails with `unguarded_cycle_detected`.
- **Decision routing uses `PipelineVerdict.recommendation`.** Gate stages need `kind="decide"` steps that return `StepResult(verdict=PipelineVerdict(recommendation="..."))`. The executor matches that against `kind="decision"` edges.
- **Keep module-level metadata as simple literals.** The static manifest reader parses the file with AST literal eval; it cannot follow function calls, aliases, or dynamic values.
- **SKILL.md location matters.** For a sibling-file module like `my_planning_pipeline.py`, the registry looks for `my-planning-pipeline/SKILL.md` next to the file. The scaffold already creates it.

## 7. Where to look for reference implementations

- `arnold/pipelines/megaplan/pipeline.py` — the canonical Megaplan planning graph.
- `arnold/pipelines/megaplan/pipelines/creative/__init__.py` — a model-backed multi-stage pipeline.
- `arnold/pipelines/megaplan/pipelines/writing_panel_strict.py` — a sibling-file pipeline with panels.
- `arnold/pipelines/evidence_pack/` — a package-style pipeline under `arnold/pipelines/` with typed ports, hooks, and continuation.
- `docs/arnold/authoring-guide.md` and `docs/arnold/package-authoring-contract.md` — full contract details.


--- CRITIQUES ---


[word choice and vocabulary]
# Word Choice & Vocabulary Critique

This is strong technical writing with a confident voice, but a handful of vocabulary choices undercut its precision and clarity.

---

## 1. Jargon Creep Without Definition

**"topology"** — *"follows the same planning topology as Megaplan"*

Topology is a mathematical term (study of spatial properties under deformation). Using it to describe a pipeline's stage ordering is metaphorical overreach. The rest of the doc calls it a "graph" — stick with that. Suggestion: *"planning structure"* or *"pipeline shape."*

**"unguarded cycle"** — used twice without definition until the gotchas section. If a reader hits `unguarded_cycle_detected` in step 5 and hasn't read step 6 yet, they're lost. Define it the first time it appears or avoid the term until you can explain it. The gotcha bullet *does* explain it ("If your graph has a back-edge"), so either move that explanation up or swap the error message quote for plainer language earlier.

---

## 2. Metaphors That Confuse More Than They Illuminate

**"phase zero gate"** — `phase_zero_gate(PrepStep(), name="prep", on_pass="plan", on_fail="halt")`

This is the first code the user encounters inside `build_pipeline()`, and it's introduced with no explanation. "Phase zero" implies there are numbered phases, but the rest of the pipeline uses named stages. The metaphor is imported from Megaplan's internal pattern library, but for a skill doc teaching someone to scaffold a new pipeline, throwing an opaque factory function at them without a sentence of orientation is a vocabulary failure. Either add a one-liner ("Phase zero gates validate prerequisites before the main pipeline runs") or rename the section header to something descriptive like "Pre-flight gate."

**"dispatch+emit"** — in the driver tuple. These are event-system verbs used as a compound noun. If this is a required literal, fine — but the doc never defines what it means, and the term appears nowhere else in the body text. A parenthetical like *(publishes events to the message bus)* would cost five words and anchor the metaphor.

---

## 3. Vague Substantives

**"machinery"** — *"Or use the built-in AgentStep / PipelineBuilder.agent(..., prompt="prompts/plan.md") machinery."*

"Machinery" is a hand-wave. It tells the reader "there's a subsystem here" without naming what kind. Replace with *"helper"*, *"interface"*, or better, a concrete noun: *"the AgentStep class and PipelineBuilder.agent() convenience method."*

**"pieces"** — *"What the pieces mean"* (table header)

This section explains 10 required and recommended module-level fields. Calling them "pieces" is folksy in a way that clashes with the surrounding register ("contract fields," "static manifest reader," "AST literal eval"). Use *"fields"* or *"contract fields"* for consistency.

**"stuff"** (implied) — The doc doesn't use it, but *"prompts and other resources"* in the `_PIPELINE_DIR` comment is adjacent fluff. Be specific: *"prompt templates, profiles, and SKILL.md."*

---

## 4. Redundant Pairs

**"Scaffold and wire"** in the description — then step 1 is titled "Scaffold the module." The "wire" part doesn't happen until step 2. The description promises two actions but the doc only treats scaffolding as a named step. Either drop "and wire" from the description or rename step 2 to "Wire the pipeline."

**"canonical"** — *"Return the canonical my-planning-pipeline graph."*

This is a template file that the user is supposed to paste and modify. Calling it "canonical" suggests it's the authoritative reference implementation, which conflicts with step 7 pointing users to *actual* reference implementations. Use *"default"* or *"skeleton."*

---

## 5. Register Inconsistency

The doc alternates between imperative instruction (*"Open... and paste"*, *"Keep... unless"*) and descriptive narration (*"This creates:"*, *"The CLI-visible name is..."*). Neither is wrong, but the shift is jarring within a single section. Pick a lane. Given this is a skill doc, the imperative mode is stronger.

Example of the wobble (Section 2):

> Open `arnold/pipelines/megaplan/pipelines/my_planning_pipeline.py` and paste the following complete module. *(imperative)*
>
> **[code block]**
>
> The CLI-visible name is the hyphenated form. *(declarative aside)*

The declarative sentence interrupts the instructional flow. Fold it into the imperative: *"Note that the CLI-visible name uses the hyphenated form: `my-planning-pipeline`."*

---

## 6. Weak Verbs

**"Use this skill when..."** — The lead-in is passive-adjacent and generic. Every skill doc starts this way, but *"Invoke this skill when..."* or *"Reach for this skill when..."* gives it more punch and distinguishes it from the 30 other skills the agent might have loaded.

**"create"** — appears 7 times in various forms. It's a utility verb, not a sin, but over-repetition flattens the texture. In step 4 you have *"If you want `--profile` to work, create:"* — *"add:"* or *"drop in:"* would vary the rhythm.

---

## 7. Micro-Improvements

- **"inspect repo"** → *"inspect the repository"* (abbreviation feels sloppy in prose, fine in comments)
- **"gotchas"** → Fine heading, but then the bullets use formal language ("silently skipped by the discovery scanner"). The heading promises pitfalls; the bullets deliver specs. Either make the bullets more pitfall-flavored (*"If you prefix files with `_`, the scanner will silently skip them"*) or rename the heading to "Requirements and pitfalls."
- **"Nullary callable"** — Precise but esoteric. *"A function that takes no arguments"* says the same thing to a broader audience.

---

## Summary

The largest word-choice drag on this doc is the gap between its audience (a developer scaffolding their first Arnold pipeline) and its vocabulary (topology, nullary, unguarded cycles, AST literal eval). You don't need to dumb it down — the technical density is appropriate — but every term that gets used *before* it gets defined creates friction. Move definitions upstream, kill the hand-wavy metaphors ("machinery," "pieces"), and commit to the imperative voice. The prose is already 85% of the way there.


[ordering and flow of ideas]
## Flow Critique: "Creating a new Arnold pipeline (Megaplan-style)"

This document has strong content but weak ordering. The core problem: **it front-loads a 150-line code dump before explaining what any of it means**, then scatters optional steps between the validation workflow and gotchas. Here's what needs fixing, with specific quotes.

---

### 1. The "paste this giant block" trap (Section 2)

Section 2 opens with *"paste the following complete module"* and immediately drops ~130 lines of Python — every stub step class, every module constant, the full assembly function. Only *after* the block does the table *"What the pieces mean"* appear.

**The reader's experience:** They copy-paste code they don't understand, scroll past it, then retroactively learn what they just pasted. This is backwards.

**Suggested fix:** Break Section 2 into sub-sections that interleave explanation with short code fragments:

- **2a. Module-level metadata** — show the `name`, `description`, `capabilities` block with 2-3 lines of code and the relevant rows from your table *right there*.
- **2b. Step implementations** — explain the `StepResult` contract briefly, then show *one* concrete step (say, `PlanStep`) as an example, noting that the others follow the same pattern.
- **2c. Pipeline assembly** — walk through `build_pipeline()` in pieces, explaining `phase_zero_gate`, `critique_revise_gate_loop`, and how edges wire together. Then provide the full module as a consolidated reference block at the end.

---

### 2. The "What the pieces mean" table is misplaced and unstructured

The table mixes contract fields (`name`, `description` — simple strings) with execution concepts (`driver`, `build_pipeline` — architectural concerns) in one flat list. It also comes too late.

**Quote the problem:**

> "| Field | Required? | Notes |
> |---|---|
> | `name` | **yes** | CLI-visible name… |
> | `driver` | **yes** | Use `("graph", "dispatch+emit")`… |
> | `build_pipeline` | **yes** | Nullary callable returning a `Pipeline`."

`build_pipeline` isn't a module-level "field" in the same sense as `name` — it's a function. Grouping it with string constants muddies the mental model.

**Suggested fix:** Split into two small tables:

1. **Manifest fields** — `name`, `description`, `arnold_api_version`, `capabilities`, `default_profile`, `supported_modes` (the things the static manifest reader needs).
2. **Runtime contract** — `driver`, `entrypoint`, `build_pipeline` (the things the executor and registry call).

Place both tables *before* the code walkthrough, so expectations are set.

---

### 3. Sections 3 and 4 interrupt the "get it working" path

The natural sequence is: scaffold → build → validate → run. That's the "I have a working pipeline" milestone. But the document inserts prompts (Section 3) and profiles (Section 4) between the build step (2) and validate/run (5).

**Quote the break:**

> "## 2. Replace the skeleton `build_pipeline()` … [full implementation]  
> ## 3. Add prompts (optional)  
> ## 4. Add a profile (optional)  
> ## 5. Validate and run"

A first-time user who follows this linearly finishes Section 2, then gets sidetracked into optional prompt files and TOML config before they can even check if their pipeline compiles.

**Suggested fix:** Reorder to:

1. Scaffold
2. Build (the code)
3. Validate and run
4. Add prompts (optional enhancement)
5. Add a profile (optional enhancement)
6. Common gotchas
7. References

This creates a clean "minimum viable pipeline → enrich" gradient.

---

### 4. Forward references before context exists

Section 3 says:

> "See `arnold/pipelines/megaplan/_pipeline/steps/agent.py` and the `creative` pipeline for real examples."

But the *"Where to look for reference implementations"* section (7) hasn't been introduced yet. The reader gets a vague pointer with no frame. Meanwhile, Section 7 does list `creative/__init__.py` explicitly. These references should be consolidated, not scattered.

---

### 5. Gotchas refer to details buried pages ago

The gotcha *"Guard every cycle"* references `loop_condition` — a concept the reader encountered in a giant code block maybe 200 lines earlier with no standalone explanation. By the time they hit this gotcha, the memory trace is cold. The loop-guard mechanism deserves its own 2-3 sentence explanation when it first appears in the assembly code, not a belated warning.

---

### Summary: the ideal reorder

| Current order | Proposed order |
|---|---|
| 1. Scaffold | 1. Scaffold |
| 2. Giant code dump + table | 2. Manifest fields table → runtime contract table → step-by-step code walkthrough |
| 3. Prompts (optional) | 3. Validate and run |
| 4. Profile (optional) | 4. Prompts (optional) |
| 5. Validate and run | 5. Profile (optional) |
| 6. Gotchas | 6. Gotchas |
| 7. References | 7. References |

The goal: a reader who follows sections 1→2→3 has a working pipeline in under 10 minutes and *then* layers on richness. Right now, they drown in code before they understand the skeleton.


[sequencing and logical progression]
## Sequencing & Logical Progression Critique

### 1. The monolithic code dump precedes its own explanation

The biggest structural problem: Section 2 asks the reader to paste ~150 lines of Python, then Section 2's own subsection "What the pieces mean" explains module-level fields that appear at the *top* of that code block. The reader encounters `name: str = "my-planning-pipeline"`, `supported_modes: tuple[str, ...] = ("code",)`, etc. with no context, scrolls past them, then finally gets the table explaining what they are.

**Fix:** Move the "What the pieces mean" table *before* the code block, or break the code into annotated chunks where each group of fields/steps/assembly is explained immediately above the relevant snippet. At minimum, swap the order: table first, then "now paste this."

### 2. No conceptual mapping between the topology diagram and the implementation

The topology is declared upfront:

```
prep → plan → critique → gate → revise → finalize → execute → review
                              ↑___________|
```

But then the reader is thrown into scaffolding commands and a raw Python module with no bridge between the abstract diagram and the concrete stages. The `critique_revise_gate_loop` pattern — the most architecturally significant piece — is never introduced conceptually. It just appears mid-code with a comment about guarding the cycle.

**Fix:** Add a short paragraph after the topology diagram that names the two key patterns (`phase_zero_gate` and `critique_revise_gate_loop`) and explains which segments of the topology they implement. Something like: *"The prep stage uses a `phase_zero_gate` pattern that routes to plan or halt. The critique→gate→revise loop is implemented by `critique_revise_gate_loop`, which bakes in the routing logic for iterate/proceed/escalate."* This gives the reader a mental model before they see code.

### 3. "Common gotchas" appears too late

Section 6 lists pitfalls — unguarded cycles, leading underscores breaking discovery, static manifest parser limitations — *after* the reader has already scaffolded, pasted code, added optional prompts, and run validation. Several of these (e.g., "Declare `default_profile` and `supported_modes` even if empty") could prevent errors during the initial paste. "Guard every cycle" is explained in a code comment but the gotcha section is the first place it's stated plainly.

**Fix:** Move "Common gotchas" to between Sections 1 and 2, or split it: put structural gotchas (underscore naming, metadata requirements) before the code paste, and keep runtime gotchas (cycle guards, decision routing) after the assembly explanation. Alternatively, add brief "⚠️" callouts inline where the mistake would occur.

### 4. The step implementations are presented before the assembly logic that uses them

The reader sees eight `@dataclass` step classes (PrepStep through ReviewStep), but doesn't understand how they connect until the `build_pipeline()` function ~60 lines later. The steps are individually trivial, but their `next` fields reference stage names that haven't been introduced yet. For example, `PrepStep.run()` returns `next="plan"` — but at that point the reader doesn't know what "plan" means structurally or whether it's been defined.

**Fix:** Either reverse the order (show `build_pipeline()` first to establish the graph, then zoom into each step), or add a one-line comment above each step class indicating its position in the topology: `# Topology: prep → [this step] → plan`.

### 5. The "optional" sections break the tutorial's forward momentum

Sections 3 (prompts) and 4 (profiles) are marked optional, but Section 5 ("Validate and run") assumes a working pipeline. A reader who skips 3 and 4 proceeds naturally. But Section 3 introduces `AgentStep` and `PipelineBuilder.agent()` — forward references to machinery not explained until Section 7's reference list. A reader who *does* want prompts gets a teaser ("See `creative` pipeline for real examples") with no immediate payoff.

**Fix:** Either consolidate 3 and 4 into a single "Extending your pipeline (optional)" section that stays brief and defers deeply to Section 7, or move them *after* "Validate and run" as a "Next steps" section so the core path (1→2→5) stays uninterrupted.

### 6. Section 7 is a reference appendix masquerading as a final step

It's titled "Where to look for reference implementations" — this is reference material, not a procedural step. Placing it as Step 7 implies sequence where none exists. It also contains information (the `creative` pipeline, the authoring guide) that would have been useful during Section 2 when the reader is staring at unfamiliar patterns.

**Fix:** Rename it to something like "Reference" or "Further reading" and consider cross-referencing specific items earlier. For instance, when introducing `critique_revise_gate_loop` in Section 2, add: *(See `arnold/pipelines/megaplan/pipeline.py` for the canonical usage.)*

### 7. Missing a "what you'll build" roadmap

The intro jumps straight from "Use this skill when..." to the topology diagram to "1. Scaffold the module." The reader gets no preview of the 7 steps ahead or the estimated effort. This matters because the document mixes required steps (1, 2, 5), optional steps (3, 4), and reference material (6, 7) without labeling them as such upfront.

**Fix:** Add one sentence after the topology: *"This guide walks through scaffolding (step 1), wiring the graph (step 2), and validation (step 5). Optional sections cover prompts and profiles; gotchas and references follow."*

---

**Summary of priority fixes:** (1) Swap the "What the pieces mean" table to precede the code block. (2) Add a conceptual bridge between the topology diagram and the implementation patterns. (3) Move structural gotchas earlier. These three changes alone would substantially improve the document's logical flow without requiring a rewrite.


[succinctness and removing redundancy]
This is a thorough guide, but it carries a lot of dead weight. Here's a focused critique on what to cut, tighten, or consolidate.

---

### 1. The frontmatter and first sentence say the same thing three times

```yaml
name: new arnold pipeline
description: Scaffold and wire a new Megaplan-style Arnold pipeline from scratch.
```
Then the H1:
> Creating a new Arnold pipeline (Megaplan-style)

Then the lede:
> Use this skill when the user wants a new pipeline in the Arnold harness that follows the same planning topology as Megaplan

One of these is enough. Drop the YAML `name` (it adds nothing the H1 doesn't), and fold the `description` into the lede. The H1 alone can carry the title.

---

### 2. The ASCII topology diagram is orphaned

The `prep → plan → critique → gate → revise → finalize → execute → review` diagram is decorative. It's never referenced, never explained, and the stage names are reinstantiated verbatim in the code block. Either tie it to concrete instruction ("each of these stages maps to a step class below") or delete it.

---

### 3. Section 2 dumps a ~130-line file; only ~20% is instruction

The guidance is: "paste the following complete module." That's one bullet. The rest is a full code listing. Consider:

- **Show only the diff from the scaffold skeleton.** The skeleton `build_pipeline()` already exists — show what changes, not the entire file.
- **Move the code to a reference appendix** and keep the section to: "Replace `build_pipeline()` with the graph wiring shown below; the step classes follow the same pattern (see Appendix A)."

The table "What the pieces mean" also overlaps heavily with comments already in the code (`# required by the static manifest reader` appears in both). Pick one location.

---

### 4. Redundancy in the metadata table vs. gotchas section

The table in section 2 says:
> Declare `default_profile` and `supported_modes` even if empty.

Section 6 repeats:
> **Declare `default_profile` and `supported_modes` even if empty.** The runtime validator only warns about them…

Cut the table entry or cut the gotcha — don't keep both. The same applies to "Guard every cycle" (the code comment already says `# Guard the critique→gate→revise cycle so validation does not complain`).

---

### 5. Section 3's file tree repeats section 1

Section 1:
```
my-planning-pipeline/
    └── SKILL.md
```

Section 3:
```
my-planning-pipeline/
├── SKILL.md
└── prompts/
```

Just show the full tree once (in section 1, with the prompts directory optionally present) and reference it later. The two prompt-loading approaches (`read_text()` vs. `AgentStep`) can also be collapsed to one recommended pattern, with a see-also for the alternative.

---

### 6. Section 4 is borderline for a "succinctness" guide

If creating a profile takes four lines of TOML and one sentence of explanation, it's fine. But the sentence "If you want `--profile my-planning-pipeline:default` to work, create:" could simply be: "Add a profile at `profiles/default.toml`:" — six words instead of seventeen.

---

### 7. Section 6: five of seven gotchas restate earlier content

- "No leading underscore" — new, keep.
- "`build_pipeline()` must be callable with no arguments" — new, keep.
- "Declare `default_profile` and `supported_modes`" — duplicate (see point 4).
- "Guard every cycle" — duplicate of the code comment and the table.
- "Decision routing uses `PipelineVerdict.recommendation`" — not stated earlier, keep.
- "Keep module-level metadata as simple literals" — new, keep.
- "SKILL.md location matters" — restates section 1 scaffolding output. Cut.

So section 6 can shrink from seven items to four.

---

### 8. Micro-level wordiness

- "Use this skill when the user wants a new pipeline in the Arnold harness that follows the same planning topology as Megaplan" → **"Scaffold a new pipeline with Megaplan's planning topology."**
- "This creates:" → the tree diagram already *shows* what it creates; the phrase is filler.
- "The CLI-visible name is the hyphenated form: `my-planning-pipeline`." → stated again in the table. Pick one.
- "Open `...` and paste the following complete module" → **"Replace the contents of `...` with:"**
- "For model-backed stages, place prompt files next to `SKILL.md`" → **"Place prompt files alongside `SKILL.md`:"**

---

### Estimated savings

Cutting the duplicate explanations, collapsing the code block to a diff or appendix, and merging the table with the gotchas would likely shrink this document by **30–40%** without losing a single actionable instruction.


[clarity of purpose and main point]
## Clarity-of-Purpose Critique

### The core problem: this document doesn't know what kind of document it is.

It's labeled a "skill" (agent-facing instructional doc), structured like a step-by-step tutorial, but written like a reference manual. The main point — "here's how to create a Megaplan-style pipeline" — gets buried under a 140-line code dump that arrives with almost no framing.

---

### 1. The topology diagram is decorative, not explanatory

> ```
> prep → plan → critique → gate → revise → finalize → execute → review
>                               ↑___________|
> ```

This is the only diagram and it's never referenced again. A reader has no idea what the loop means (is it the cycle guarded in the code? why does it loop back to critique and not gate?), why there are eight stages, or how the diagram maps to the code below. **Fix:** After the diagram, add 2–3 sentences: "The critique→gate→revise loop is the quality-control cycle. If the gate says 'iterate,' we revise and re-critique. If 'proceed,' we move to finalize." Then explicitly call out where in the code this loop gets assembled.

---

### 2. Step 2 is a wall. The heading lies.

> ## 2. Replace the skeleton `build_pipeline()`

The heading says "replace the skeleton `build_pipeline()`" (one function), but the instruction says "paste the following complete module" (the entire file — imports, eight step classes, module-level metadata, and assembly logic). That's a bait-and-switch. The reader expects to swap one function and instead gets asked to replace ~180 lines with no walkthrough.

**Fix:** Either:
- Rename the heading to "2. Replace the skeleton module" and break the code block into annotated chunks (imports → steps → assembly), or
- Keep the heading but show *only* the assembly function, with links to reference implementations for the step classes.

---

### 3. The "why" is entirely missing

The doc opens with:

> Use this skill when the user wants a new pipeline in the Arnold harness that follows the same planning topology as Megaplan

But it never explains: What is the Megaplan topology? Why would someone want to replicate it? What problem does the critique-revise loop solve? When would someone choose this pattern over a simpler `in_process` pipeline? The reader is asked to execute a recipe without understanding the dish.

**Fix:** Add a short "When to use" section before Step 1. Two sentences would suffice: "Use this pattern when you need LLM-driven planning with built-in self-critique and an automated quality gate that can loop until the plan passes. It's ideal for complex multi-step code generation where first drafts are rarely good enough."

---

### 4. The reference table is in the wrong place

The "What the pieces mean" table appears after the giant code block. By that point the reader has already pasted the code and is wondering what they just did. The table explains `name`, `description`, `arnold_api_version` — metadata that should be understood *before* the paste.

**Fix:** Move the table above the code block, or split it: put the "required fields" subset before the code as a pre-flight checklist, and leave "recommended" fields as a footnote.

---

### 5. Critical constraints are hidden in "gotchas"

> No leading underscore. Files or directories starting with `_` or `.` are silently skipped.

> `build_pipeline()` must be callable with no arguments.

> Declare `default_profile` and `supported_modes` even if empty.

These are not "gotchas" — they are hard requirements that, if missed, produce silent failures or cryptic validation errors. They belong in Step 2, not buried in section 6.

**Fix:** Pull these into the main flow where the reader will act on them. For example, after the code block: "⚠️ Before you move on: confirm your module name starts without an underscore, `build_pipeline()` takes no arguments, and both `default_profile` and `supported_modes` are declared."

---

### 6. The document has no "you're done" signal

Step 5 ends with `arnold run`, and then you get "Common gotchas" and "Reference implementations." There's no checkpoint, no summary of what the reader should now have working, and no "next steps" for customizing the skeleton.

**Fix:** Add a one-paragraph closing section: "You now have a working pipeline skeleton. To make it real: replace each step's `run()` method with actual LLM calls, add prompts in `prompts/`, and tune the gate's loop condition to match your quality bar."

---

### Summary

The document has all the right information. But it reads like notes from someone who already knows the system, written for themselves. To serve its stated purpose — scaffolding a new pipeline from scratch — it needs to **lead with the concept**, **break the code into digestible pieces**, and **surface constraints where they're actionable**, not where they're footnotes.


[tone and voice consistency]
## Tone & Voice Consistency Critique

This is strong technical documentation with a generally clear, instructional voice. But it wobbles between two registers — a crisp, confident reference tone and a chattier "friendly tutorial" tone — and the friction is noticeable in several places.

---

### 1. The header voice is crisp; the body sometimes isn't

Your section headers are admirably direct: "Scaffold the module," "Validate and run," "Common gotchas." They project confidence and economy. The body, however, occasionally drifts into hand-holding:

> "Open `arnold/pipelines/megaplan/pipelines/my_planning_pipeline.py` and paste the following complete module."

"Paste the following complete module" is oddly eager — it reads like a blog tutorial, not a reference guide written by someone who assumes competence. The reader doesn't need to be told to paste; the code block implies it. Compare with the more restrained tone of Section 5:

> "Must pass with zero defects."

That's sharp. It tells you what success looks like without cheerleading. The doc would feel more authoritative if Section 2 matched that energy. Suggested revision for the lead-in:

> "Replace the skeleton with the module below:"

---

### 2. "What the pieces mean" table has a register clash

This table is one of the most useful parts of the doc, but the "Notes" column mixes imperative commands with descriptive fragments:

- *Descriptive:* "One-liner shown in `arnold pipelines list`." (fine)
- *Imperative:* "Keep `"1.0"` unless targeting a newer SDK." (tells the reader what to do)
- *Descriptive-definition:* "Bare name `"build_pipeline"` or fully-qualified `"module:name"`." (fine)
- *Imperative:* "Declare even as `None`; the static manifest reader requires it." (tells the reader what to do)

Pick one stance. Since this is a reference table, not a step-by-step instruction, the descriptive voice fits better:

> `default_profile`: Declare as `None` if unused. Required by the static manifest reader.

---

### 3. Colloquial lapses in "Common gotchas"

This section is otherwise excellent — practical and memorably specific. But one line breaks character:

> "The `_template` package is named that way **on purpose**."

"On purpose" is spoken English. In a doc that uses language like "silently skipped by the discovery scanner" and "unguarded_cycle_detected," this lands as a tonal misfire. "Intentionally" does the same work without the register drop. Also, the aside "Files or directories starting with `_` or `.` are silently skipped" is clear; the `_template` sentence after it feels tacked on. Merge:

> "Files and directories beginning with `_` or `.` are silently skipped by the discovery scanner (the `_template` package is intentionally named this way)."

---

### 4. Section 7 header is verbose relative to its siblings

Every other numbered header is a verb phrase of 3–4 words: "Scaffold the module," "Add prompts (optional)," "Validate and run." Then Section 7 arrives as:

> "Where to look for reference implementations"

This is a sentence fragment you'd find in a FAQ, not a header in a tightly structured guide. The other headers *do* things; this one *preambles*. "Reference implementations" or "See also" would match the pattern.

---

### 5. Code-comment voice vs. prose voice

The inline comments in the Python module are notably more casual than the surrounding documentation:

> "# Real work: inspect repo, gather context, write a prep artifact."

"Real work:" is a conversational wink — it implies "the stub above is fake; here's what you'd actually do." This is fine *if* it's consistent across all step comments, but it isn't. `PlanStep` just has a bare `pass`. Either lean into the conversational placeholder tone everywhere or keep it uniformly terse.

---

### 6. One jargon spike

> "Nullary callable returning a `Pipeline`."

If your reader needs "paste the following complete module," they may not know "nullary." The word is precise but fractures the otherwise accessible register. "A callable taking no arguments" says the same thing without sending anyone to Wikipedia.

---

### Summary

The doc is at its best when it's terse, confident, and reference-like (Sections 1, 5, 6). It weakens when it slips into tutorial-handholding ("paste the following") or spoken register ("on purpose"). Pick the crisper voice and apply it uniformly — the content is good enough that it doesn't need softening.


[jargon and accessibility]
# Jargon & Accessibility Critique

This document is written for an audience that already lives inside the Arnold/Megaplan codebase. For anyone one step outside that circle, it's a wall of insider shorthand. Below are the worst offenders, with concrete fixes.

---

## 1. The opening sentence assumes too much

> "Scaffold and wire a new Megaplan-style Arnold pipeline from scratch."

"Scaffold" and "wire" are fine if your audience knows CLI generators, but "Megaplan-style Arnold pipeline" buries the reader in three layers of unexplained proper nouns. A newcomer has no idea whether Arnold is a framework, a CLI tool, or a person.

**Fix:** Add a one-sentence preamble: *"Arnold is the pipeline orchestration harness. Megaplan is its primary planning topology. This guide shows you how to create a pipeline that follows that topology."* Without it, the whole document floats on unnamed assumptions.

---

## 2. The topology diagram is cryptic

> ```
> prep → plan → critique → gate → revise → finalize → execute → review
>                               ↑___________|
> ```

The loop notation is nonstandard. A reader who hasn't seen ASCII art control-flow diagrams won't parse this. Worse, the stage names are never defined — what does `prep` produce? What does `gate` decide? Why does `revise` loop back to `critique` rather than `plan`?

**Fix:** Accompany the diagram with a single-sentence description per stage. Even a one-liner like *"prep: gather context from the repo"* would anchor the reader.

---

## 3. "Nullary callable" is needlessly pedantic

> `build_pipeline` | **yes** | Nullary callable returning a `Pipeline`.

"Nullary callable" is a term of art in PL theory that will make a working developer pause. This isn't a type-theory paper.

**Fix:** *"A function that takes no arguments and returns a Pipeline."* Same precision, zero friction.

---

## 4. "Static manifest reader" is invoked but never introduced

This phrase appears four times. It's clearly an important component of the system, but the document never says what it is or why its constraints matter. The AST parsing constraint in Section 6 is meaningful only if you know the reader exists.

**Fix:** Add one sentence in the table: *"The static manifest reader scans your file at import time (without executing it), so values must be plain literals — no function calls, variables, or computed expressions."* Now the Section 6 gotcha makes sense.

---

## 5. Unexplained dispatch modes

> `driver: tuple[str, str] = ("graph", "dispatch+emit")`

What does `"dispatch+emit"` mean? How does it differ from `"in_process"`? The parenthetical in the table — *"for graph-driven pipelines; `"in_process"` for simple in-process graphs"* — is circular. I still don't know what dispatch+emit *does*.

**Fix:** Even a terse footnote helps: *"dispatch+emit publishes stage transitions over the message bus for multi-process execution; in_process runs everything in one Python process."*

---

## 6. Decision routing is dense and under-explained

> "Gate stages need `kind="decide"` steps that return `StepResult(verdict=PipelineVerdict(recommendation="..."))`. The executor matches that against `kind="decision"` edges."

This is the only explanation of how the critique→gate→revise loop routes. It reads like a compiler error message. `PipelineVerdict`, `kind="decide"`, and `kind="decision"` edges are all introduced simultaneously with no example of *what routes where*.

**Fix:** Add a concrete mini-example: *"If the Critique step returns `recommendation="iterate"`, the executor follows the edge labeled `iterate` to Revise. If it returns `"proceed"`, it follows the edge to Finalize."*

---

## 7. The loop guard explanation buries its meaning

> ```python
> cycle["gate"] = dataclasses.replace(
>     cycle["gate"],
>     loop_condition=lambda loop_state: int(
>         getattr(loop_state, "iteration", 0) or 0
>     ) >= 3,
> )
> ```

A reader seeing this block will ask: what is a loop guard, why does the gate stage need one, and what does this lambda actually enforce? The prose following it — *"Guard the critique→gate→revise cycle so validation does not complain about an unguarded loop"* — explains the why, but not the what: this lambda forces the loop to halt after 3 iterations. The logic itself is also noisy (`getattr` with a fallback, `int()` coercion, `or 0` redundancies).

**Fix:** Name the condition: `max_iterations = 3` and add a comment: *"Halt the critique→revise loop after 3 passes."* Then the prose can be shorter.

---

## 8. "Agent specs understood by the Megaplan key pool" is insider-speak

> Values are agent specs understood by the Megaplan key pool (`claude`, `codex`, `hermes:deepseek:deepseek-v4-pro`, etc.).

No definition of an "agent spec" or a "key pool." If this is a model identifier with an optional provider prefix, say so plainly.

**Fix:** *"Each value is a model identifier: just a name (e.g., `claude`) uses the default provider; a colon-separated spec (e.g., `hermes:deepseek:deepseek-v4-pro`) specifies provider and model explicitly."*

---

## 9. "Sibling-file pipeline" and "sibling-file module" appear without explanation

> `writing_panel_strict.py` — a sibling-file pipeline with panels.

The distinction between a "package-style" pipeline (with `__init__.py`) and a "sibling-file" one (a lone `.py` with a same-named directory next to it) is structural but never explicitly contrasted. The Section 6 gotcha about `SKILL.md` location also references this concept without defining it.

**Fix:** In Section 1, after the scaffold output, add: *"This layout — a `.py` file alongside a same-named directory — is the sibling-file pattern. The alternative is the package pattern (`__init__.py` inside the directory)."*

---

## Summary: the root problem

This document is an excellent internal reference for contributors who already understand the Arnold topology, the dispatch system, the static manifest reader, and the loop-guard contract. But it's presented as a standalone guide. The fix isn't to remove jargon — domain terms like "stage," "gate," and "verdict" are the vocabulary of the system — but to *define each term the first time it appears*, and to add a one-paragraph "concepts you need to know" section at the top. Without that, the guide reads like a checklist for people who don't need it.


[transitions between sentences and paragraphs]
# Transition Critique

The piece is technically clear but reads like a checklist bolted together. The numbered sections stack without bridges, and several internal jumps feel like floor-drops. Here’s where it hurts most, with fixes.

---

## The biggest problem: section-to-section whiplash

Every section boundary lands without a transitional sentence. Examples:

**Section 1 → 2:**

> The CLI-visible name is the hyphenated form: `my-planning-pipeline`.
>
> ## 2. Replace the skeleton `build_pipeline()`

You just told me what the scaffold created — then you immediately tell me to replace it. Why? Add a sentence like: *"The scaffold generates a stub `build_pipeline()` that returns a placeholder graph. Replace it with the real topology below."*

**Section 2 → "What the pieces mean":**

A 100-line code block ends, then:

> ### What the pieces mean

No wrap-up, no handoff. The reader surfaces from code to a table with zero orientation. Insert: *"The module above declares several module-level contract fields. Here's what each one requires:"*

**Section 5 → 6:**

> python -m arnold run my-planning-pipeline "Implement a dark mode toggle"
>
> ## 6. Common gotchas

The run command just executed; now we get warnings. Bridge it: *"If any of the above steps fail, the issues below are the most likely culprits."*

**Section 7 lands as a dead stop:**

The document ends on a bullet list of file paths. No conclusion, no "next steps." Add a single closing line: *"Study these references alongside this guide, and you'll have a working pipeline in under ten minutes."*

---

## Mid-section jumps

**Topology diagram → "## 1. Scaffold the module"**

The diagram shows the conceptual flow; then we leap to shell commands. A one-line bridge: *"To turn this topology into code, start by scaffolding the module from the repo root:"* would make the diagram feel earned rather than decorative.

**Code comment → dataclass definitions (Section 2)**

The comment block:

> # ── Step implementations ─────────────────────────────────────────────────
> # Each step must expose `name`, `kind`, and a `run(ctx: StepContext) -> StepResult`
> # method.  In a real pipeline these runs call models…

Then immediately:

> @dataclass
> class PrepStep:

The comment explains what steps *must* do; the code shows a concrete one. The jump works structurally, but a tiny nudge helps: end the comment with *"Below are stub implementations for each stage in the topology."*

---

## Transitions that already work

Credit where it's due — within-section flow is solid:

- *"From the repo root:"* → command → *"This creates:"* → tree → naming note. Clean chain.
- *"For model-backed stages, place prompt files…"* → tree → *"Prompt paths are resolved…"* → code → *"Or use the built-in…"* Natural alternation of instruction and example.
- The gotchas list uses parallel imperative structure, which creates internal coherence without explicit transitions.

---

## Summary fix

Add **one transitional sentence** before every `##` heading (sections 2–7) and before the `### What the pieces mean` subheading. Five sentences total. The document's bones are good; it just needs connective tissue so the reader moves from *scaffold* to *replace* to *decorate* to *validate* without feeling each as an unannounced context switch.


[overall structure]
## Structural Critique

### 1. Missing Opening Frame

The document opens with a topology diagram and jumps straight into scaffolding. There's no paragraph that tells the reader what they're about to build or why. The ASCII art is evocative but never explained — what do the arrows mean? What is a "critique→revise→gate" loop? A two-sentence opener ("This guide walks you through creating a pipeline that follows Megaplan's prep→plan→critique→gate→revise→finalize→execute→review topology...") would orient the reader before the procedural steps begin.

### 2. Section 2 Is Dangerously Bloated

Section 2 ("Replace the skeleton `build_pipeline()`") is a single section that contains a ~120-line code block followed by a reference table. This is the document's structural collapse point. A reader who just scaffolded the module is hit with a wall of code containing eight step classes, a ~50-line `build_pipeline()` function, and a loop-guard workaround — all before any explanation of what they're looking at.

**Specific fix:** Split this into at least two sections:
- **2a. Step implementations** — show a *minimal* set of steps (maybe just `prep` and `plan`) with commentary on the `StepResult` contract.
- **2b. Pipeline assembly** — show `build_pipeline()` and explain the graph wiring. Point to the full module as a reference rather than pasting it inline. The reader can open the scaffolded file; they don't need it reproduced here.

### 3. The Field Table Is Misplaced and Mis-scoped

The "What the pieces mean" table lives inside section 2, after the monolithic code block. But it mixes two distinct categories:

- **Module-level fields** (`name`, `description`, `arnold_api_version`, `capabilities`, `driver`, `entrypoint`) — these belong to the module skeleton, which is section 1 material.
- **The `build_pipeline()` contract** — "Nullary callable returning a `Pipeline`" — this is about section 2 material.

The reader has already seen these fields in the code block; the table is an after-the-fact glossary. Move the module-field rows into section 1 (right after "This creates:") so the reader understands the skeleton *before* replacing it. Keep only the `build_pipeline` contract row in section 2.

### 4. Validate-and-Run Comes Before Gotchas (Wrong Order)

Section 5 says "run `arnold pipelines check`" and section 6 lists gotchas that *cause check failures* (unguarded cycles, missing `default_profile`, leading underscores). A reader who follows the document linearly will hit validation errors, scroll down, and discover the fixes in section 6. This is a sequencing error.

**Fix:** Rename section 6 to "Before you validate" or "Common pitfalls" and move it before section 5. The gotcha about `loop_condition` is especially critical — the code block in section 2 includes a guard, but the rationale isn't explained until section 6.

### 5. Optional Sections Break the Procedural Flow

Sections 3 (prompts) and 4 (profiles) are both marked "optional" and sit between the core wiring (section 2) and the validation step (section 5). For a reader doing the minimal path, these are speed bumps. Consider either:

- Moving them *after* "Validate and run" as "Extending your pipeline," or
- Grouping them under a single "Optional: prompts and profiles" heading with brief sub-sections, so the reader can skip past in one glance.

### 6. The Reference Section Is an Undifferentiated List

Section 7 is a flat bullet list of five file paths with one-line descriptions. It reads like a data dump. Group these by what the reader is looking for:
- **"If you want model-backed stages like mine"** → `creative/__init__.py`
- **"If you want typed ports and hooks"** → `evidence_pack/`
- **"For the full contract"** → the two docs

This turns a laundry list into a decision aid.

### Summary

The document's information is solid, but it's structured as a single downhill slope with the heaviest material at the top and troubleshooting at the bottom. Restacking it as **overview → scaffold → understand the skeleton → wire steps → pitfalls → validate → optional extensions → references** would cut the cognitive load substantially and prevent the reader from having to backtrack.


[reader engagement and momentum]
This document has solid bones, but its engagement and momentum suffer from structural choices that bury the reader's understanding and interrupt forward motion. Here's where it loses steam and how to fix it.

---

## The opening is functional but inert

> "Use this skill when the user wants a new pipeline in the Arnold harness that follows the same planning topology as Megaplan"

This assumes a reader who already knows they need this. A one-sentence hook framing *why* someone would scaffold a pipeline (what problem it solves, what outcome it enables) would give the reader a reason to keep going. The topology diagram is great—lead with it visually or verbally: "You're about to build a pipeline that mirrors Megaplan's critique-revise loop. Here's the shape."

## The 120-line code block arrives as a wall, not a destination

Section 2 tells the reader to "paste the following complete module" and then drops a massive code block with zero orientation. A reader who just breezed through the one-line scaffold command in Section 1 now faces a dense slab of dataclasses, factory functions, and loop guards. This is the document's biggest momentum killer.

**Fix:** Insert a 3–4 sentence preamble that maps the graph topology onto the code the reader is about to see. Something like: *"The module below defines eight steps wired into the prep→plan→critique→gate→revise→finalize→execute→review chain. Pay attention to three things: how StepResult chains steps together with next=, how the critique/gate/revise cycle is built by critique_revise_gate_loop(), and how build_pipeline() assembles them into a Pipeline dict. Everything else is boilerplate you'll customize later."* This primes the reader to parse the code instead of glazing over it.

## Explanations chase the code instead of preceding it

The "What the pieces mean" table appears *after* the code block. Readers encounter `default_profile: str | None = None` with a cryptic comment about "static manifest reader" and have no idea why it matters until they reach the table. Reverse the order: put the table first, or at minimum give a one-line rationale for each required field inline. The current approach forces the reader to either skip the code (losing context) or read it confused.

## Placeholder comments signal "this isn't real yet"

> "Real work: inspect repo, gather context, write a prep artifact."

This and similar stubs tell the reader "nothing interesting is happening here yet." If the purpose is a template, make that explicit: *"Each step's run() method is a stub—replace the body with your actual logic. For now, notice how they chain via next=."* Otherwise the reader reads seven near-identical dataclasses and wonders why they're spending time on them.

## The gate-cycle explanation is buried in code, not called out

The `critique_revise_gate_loop` call and the subsequent `loop_condition` lambda are the single most important structural detail in the whole module—this is what makes the critique→revise loop actually terminate. Yet the explanation is a brief inline comment:

> "Guard the critique→gate→revise cycle so validation does not complain about an unguarded loop."

**Fix:** Pull this out as a short sub-section or callout: *"The loop guard: without a loop_condition, the validator rejects cycles. The lambda below caps iterations at 3 to prevent infinite loops. You can adjust the threshold or tie it to a quality metric instead."* This rewards the reader's attention at the exact moment they'd otherwise skim past it.

## Optional steps interrupt the completion arc

Sections 3 (prompts) and 4 (profiles) are labeled optional, but they sit between the required build step and the validation step. The reader's natural momentum is: scaffold → build → validate → done. Interleaving "by the way, you could also…" before validation disperses focus. Move optional sections after "Validate and run" or group them under a single "Extending your pipeline" heading.

## Gotchas are gold—move them up

The "Common gotchas" section is the most concretely useful content for a practitioner, but it's parked at #6 after optional material and before references. At minimum, surface the top 2–3 gotchas as callouts inline (e.g., "⚠️ No leading underscore in filenames—the scanner skips them silently"). The current flat list at the end asks the reader to retain everything until they stumble into a problem.

## The reference list is a dump, not a guide

> "arnold/pipelines/megaplan/pipeline.py — the canonical Megaplan planning graph."

Seven references with one-line descriptions give the reader a map with no compass. Add a sentence of guidance: *"Start with creative/__init__.py if you're adding model-backed stages; look at writing_panel_strict.py for sibling-file patterns; use evidence_pack/ for typed ports and hooks."* This turns the list from "here are files that exist" into "here's what to read based on what you're building."

## The final command example is undersold

> `python -m arnold run my-planning-pipeline "Implement a dark mode toggle"`

This is the payoff—the moment the reader sees their pipeline work. It deserves a one-sentence flourish: *"If everything passes, this is the moment your pipeline springs to life—it'll run the full prep→review chain on your prompt."* Ending on a flat command makes the finish line feel administrative rather than satisfying.

---

**Summary of the one structural move that would most improve momentum:** reorder to scaffold → explain the graph shape briefly → present the code with a framing preamble → validate immediately → then offer prompts, profiles, gotchas, and references as deepening layers. The reader should feel completion after Section 5, not be left wading through appendices.


--- REVISED VERSION ---
