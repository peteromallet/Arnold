You are an expert editor. Revise the following writing to make it clearer, more concise, and more compelling.
You do NOT have to follow every critique blindly; use your judgment and preserve the author's intent.

--- ORIGINAL ---

---
name: new arnold pipeline
description: Create a new Arnold pipeline module from scratch.
---

# Creating a new Arnold pipeline

Use this skill when the user wants to add a new, named, runnable pipeline to the Arnold harness.

Arnold discovers pipeline modules under `arnold/pipelines/`. There are two common shapes:

1. **Graph-driven sibling-file module** — created with `arnold pipelines new`. Best for stage graphs, loops, and quick CLI workflows. These live under `arnold/pipelines/megaplan/pipelines/` and are executed by the Megaplan graph executor.
2. **Typed package module** — created by copying `arnold/pipelines/_template`. Best for typed ports, hooks, resume/continuation, and model-less adapters. These live as packages directly under `arnold/pipelines/`.

Both shapes expose the same module-level contract fields and both must pass `arnold pipelines check`.

## 1. Quick start: graph-driven sibling-file module

From the repo root:

```bash
python -m arnold pipelines new my-pipeline --driver graph
```

This creates:

```
arnold/pipelines/megaplan/pipelines/
├── my_pipeline.py          # the Python module
└── my-pipeline/
    └── SKILL.md            # agent-facing docs
```

The CLI-visible name is the hyphenated form: `my-pipeline`.

### Minimal module

Replace the scaffolded `arnold/pipelines/megaplan/pipelines/my_pipeline.py` with:

```python
"""Minimal graph-driven Arnold pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from arnold.pipelines.megaplan._pipeline.types import (
    Edge,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
)

# ── Module-level contract fields ─────────────────────────────────────────

name: str = "my-pipeline"
description: str = "A minimal graph-driven pipeline."
default_profile: str | None = None
supported_modes: tuple[str, ...] = ()
driver: tuple[str, str] = ("graph", "dispatch+emit")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("example",)

_PIPELINE_DIR: Path = Path(__file__).parent / "my-pipeline"


# ── Steps ────────────────────────────────────────────────────────────────

@dataclass
class IngestStep:
    name: str = "ingest"
    kind: str = "produce"

    def run(self, ctx: StepContext) -> StepResult:
        draft_path = ctx.inputs.get("draft")
        if not draft_path:
            raise ValueError("Pass a file path: arnold run my-pipeline <file>")
        text = Path(str(draft_path)).expanduser().resolve().read_text(encoding="utf-8")
        return StepResult(next="process", state_patch={"text": text})


@dataclass
class ProcessStep:
    name: str = "process"
    kind: str = "produce"

    def run(self, ctx: StepContext) -> StepResult:
        text = ctx.state["text"]
        out_path = ctx.plan_dir / "result.md"
        out_path.write_text(text.upper(), encoding="utf-8")
        return StepResult(next="halt", outputs={"result": str(out_path)})


# ── Pipeline assembly ────────────────────────────────────────────────────

def build_pipeline() -> Pipeline:
    return Pipeline(
        stages={
            "ingest": Stage(
                name="ingest",
                step=IngestStep(),
                edges=(Edge(label="process", target="process"),),
            ),
            "process": Stage(
                name="process",
                step=ProcessStep(),
                edges=(Edge(label="halt", target="halt"),),
            ),
        },
        entry="ingest",
    )
```

Notes:

- `ctx.inputs` receives the positional CLI argument as `"draft"` and `--inputs key=value` as string values.
- `ctx.state` is the graph executor's mutable run state; use `state_patch` to write values for downstream steps.
- `ctx.plan_dir` is the run's artifact directory.

## 2. Typed package module

For typed ports, hooks, resume, or non-model adapters, copy the template package:

```bash
cp -r arnold/pipelines/_template arnold/pipelines/my_pipeline
```

Then edit `arnold/pipelines/my_pipeline/__init__.py`:

```python
from arnold.pipelines._authoring import build_skeleton_pipeline
from arnold.pipeline.types import Pipeline

name = "my-pipeline"
description = "A minimal typed Arnold pipeline."
driver = "in_process"
entrypoint = "arnold.pipelines.my_pipeline:build_pipeline"
arnold_api_version = "1.0"
capabilities = ("example",)
default_profile = None
supported_modes = ()


def build_pipeline() -> Pipeline:
    return build_skeleton_pipeline(name, description)
```

Replace the skeleton with real stages in `arnold/pipelines/my_pipeline/pipelines.py` using `arnold.pipeline.builder.PipelineBuilder`. See `arnold/pipelines/evidence_pack/` for a complete example with ports, hooks, and resume.

## 3. Module contract (both shapes)

| Field | Required? | Notes |
|---|---|---|
| `name` | **yes** | CLI-visible pipeline name. Keep it stable. |
| `description` | **yes** | One-liner shown in `arnold pipelines list`. |
| `arnold_api_version` | **yes** | Keep `"1.0"` unless targeting a newer SDK. |
| `capabilities` | **yes** | Non-empty tuple of labels. |
| `driver` | **yes** | String or tuple. `"in_process"` or `("graph", "dispatch+emit")` are common. |
| `entrypoint` | **yes** | Bare name `"build_pipeline"` or `"module:name"`. |
| `build_pipeline` | **yes** | Nullary callable returning a `Pipeline`. |
| `default_profile` | recommended | Declare as `None`; the static manifest reader requires it. |
| `supported_modes` | recommended | Declare as `()`; the static manifest reader requires it. |

Keep module-level metadata as simple literals. The static manifest reader parses them with AST literal eval; it cannot follow function calls, aliases, or computed values.

## 4. Add resources (optional)

Place prompts, profiles, and extra files next to `SKILL.md` (sibling-file) or inside the package directory (package module):

```
my-pipeline/
├── SKILL.md
├── prompts/
│   └── process.md
└── profiles/
    └── default.toml
```

Resolve paths from `_PIPELINE_DIR` in sibling-file modules, or from the package directory in package modules.

## 5. Validate and run

```bash
python -m arnold pipelines check my-pipeline
python -m arnold pipelines list
python -m arnold run my-pipeline path/to/input.md
```

- The positional argument maps to `ctx.inputs["draft"]`.
- `--inputs key=value` maps to `ctx.inputs["key"]` as a string.

## 6. Common gotchas

- **No leading `_` or `.`** in module or directory names; discovery silently skips them.
- **`build_pipeline()` must be callable with no arguments** from the registry's perspective.
- **Declare `default_profile` and `supported_modes` even if empty.** The runtime validator only warns, but the static manifest reader rejects packages that omit them.
- **Guard every cycle.** If your graph has a back-edge, attach a `loop_condition` to a stage in the cycle, otherwise `arnold pipelines check` fails with `unguarded_cycle_detected`.
- **Decision routing uses `PipelineVerdict.recommendation`.** Gate stages need `kind="decide"` steps that return `StepResult(verdict=PipelineVerdict(recommendation="..."))`. The executor matches that against `kind="decision"` edges.
- **Use absolute paths when shelling out to subagent launchers.** Pass fully-resolved paths for `--project-dir`, `--briefs-dir`, `--output-dir`, and file arguments (`Path(...).resolve()`). Do not mix relative CLI arguments with `cwd=...`.
- **`--inputs` values are strings.** If you need a list (e.g. `perspectives=a,b,c`), parse it inside the step with `value.split(",")`.

## 7. Where to look for reference implementations

- `arnold/pipelines/_template/` — minimal package module template.
- `arnold/pipelines/evidence_pack/` — full package module with typed ports, hooks, and resume.
- `arnold/pipelines/megaplan/pipeline.py` — Megaplan's canonical planning topology (a specific sibling-file graph).
- `docs/arnold/authoring-guide.md` — hands-on authoring guidance.
- `docs/arnold/package-authoring-contract.md` — authoritative field-level contract.


--- CRITIQUES ---


[word choice and vocabulary]
## Word Choice & Vocabulary Critique

This is a technically sound document, but several word choices undercut its precision and polish. Here are the specific issues, moving from most to least consequential.

---

### 1. **"gotchas"** (heading and body)

> "Common gotchas"

This is breezy, colloquial, and slightly dated developer slang. It clashes with the document's otherwise clipped, formal register. A technical reference shouldn't sound like a blog post from 2012.

**Suggest:** *"Common pitfalls"* or simply *"Pitfalls."* If you want to preserve approachability, *"Watch out for"* is warmer without being juvenile.

---

### 2. **"nullary callable"**

> "Nullary callable returning a Pipeline."

*Nullary* is mathematically precise but practically obscure. Most working developers will pause or Google it. The same concept is already explained plainly two bullet points earlier: *"must be callable with no arguments."* Using the jargon version first and the plain version later is backwards.

**Suggest:** *"Zero-argument callable"* in the table. Reserve *nullary* for a formal spec, not a how-to guide.

---

### 3. **"shelling out"**

> "Use absolute paths when shelling out to subagent launchers."

"Shell out" is informal phrasal-verb developer slang. It means "spawn a subprocess," but the phrasing is fuzzy and register-inappropriate for reference documentation.

**Suggest:** *"when spawning subagent launchers"* or *"when invoking subagent launchers via a shell."*

---

### 4. **"shapes"** as a synonym for architecture

> "There are two common shapes:"

A pipeline has a *shape* is a metaphor—and not an especially vivid one. In a document full of precise terms like *topology*, *stages*, and *edges*, "shapes" feels vague and hand-wavy. 

**Suggest:** *"There are two common patterns:"* or *"There are two module forms:"* — the latter ties it to the "sibling-file module" / "package module" distinction you're introducing.

---

### 5. **"best for"** (used twice, back-to-back sections)

> "Best for stage graphs, loops, and quick CLI workflows."
> "Best for typed ports, hooks, resume/continuation, and model-less adapters."

"Best for" is weak for technical guidance. It sounds like opinion, not architecture. It also gets repeated verbatim.

**Suggest:** *"Suited to…"* / *"Designed for…"* or even *"Use this when you need…"* — the last one is more directive and matches the skill's purpose.

---

### 6. **"One-liner"**

> "One-liner shown in arnold pipelines list."

Informal and imprecise. A "one-liner" is a joke or a single-line shell command, not a description string.

**Suggest:** *"Single-line description displayed in..."* or just *"Description shown in..."*

---

### 7. **"Keep it stable"**

> "CLI-visible pipeline name. Keep it stable."

"Stable" here is a euphemism for "don't rename it," but it's too soft. It could mean "reliable" rather than "immutable."

**Suggest:** *"Do not change it after initial release."* Be direct.

---

### 8. **"Declare as None" / "Declare as ()"** (repeated twice)

> "Declare as None; the static manifest reader requires it."
> "Declare as (); the static manifest reader requires it."

"Declare as" is a Python-adjacent verb used loosely. You're telling them to *assign* a value to a module-level variable, not declare a type. The phrasing is slightly off.

**Suggest:** *"Set to None"* or *"Initialize as None."*

---

### 9. **Minor quibbles**

- **"maps to"** appears three times in close succession. Vary with *"is available as,"* *"populates,"* or *"binds to."*
- **"from the registry's perspective"** anthropomorphizes code unnecessarily. Drop "perspective": *"from the registry"* is sufficient.
- **"scaffolded"** is fine (established tooling jargon), but if you're already using "replace the scaffolded," be aware you're stacking jargon on jargon for newcomers.

---

### Summary

The document's vocabulary has two voices fighting each other: a precise systems author (*topology, artifact directory, AST literal eval*) and a chatty tutorial writer (*gotchas, shelling out, shapes, one-liner*). Pick one. For a skill reference that lives alongside code, lean into the first voice—it's the stronger one and fits the material better.


[ordering and flow of ideas]
# Flow & Ordering Critique

This piece has solid raw material but its current arrangement works against the reader at several key points. Here's where the flow breaks down and how to fix it.

---

## 1. The introduction doesn't guide the choice it presents

> "There are two common shapes: 1. Graph-driven sibling-file module … 2. Typed package module … Both shapes expose the same module-level contract fields and both must pass `arnold pipelines check`."

The reader now faces a decision with zero decision-making criteria. The intro names two paths, then immediately launches into "Quick start: graph-driven" as though that's the default. A reader who needs the typed package module feels lost from the start.

**Fix:** Add a one-sentence decision heuristic, e.g.: *"Use the graph-driven shape for stage graphs and quick CLI workflows. Use the typed package shape when you need typed ports, hooks, or resume/continuation."* Then give each shape its own headed section, and let the reader skip to the one they need.

---

## 2. Section 1 opens with a CLI command before the reader understands what they're building

> "From the repo root: `python -m arnold pipelines new my-pipeline --driver graph`"

The reader is told to run a command before they've seen what a pipeline *is*. They don't yet know what `IngestStep`, `ProcessStep`, or `Pipeline` mean. The command → file tree → full code → notes structure means the reader skims the code without context, then retroactively learns what it does from the notes.

**Fix:** Invert the ordering within Section 1. Give a one-paragraph conceptual preview of the pieces (steps, stages, pipeline assembly), *then* show the scaffold command, *then* show the code. The notes currently trailing the code block explain `ctx.inputs`, `ctx.state`, and `ctx.plan_dir` — these are fundamental concepts that should be introduced *before* the reader encounters them in code.

---

## 3. The module contract (Section 3) interrupts the creation → validation arc

Sections 1–2 say "here's how to create a pipeline." Section 5 says "here's how to validate and run it." Section 3 lands squarely between them and is pure reference material — a table of fields with required/recommended tags. It's important, but it halts momentum.

**Fix:** Move the contract table to an appendix or fold it into each shape's section as a checklist. Better yet: keep it where it is but *rename it* to signal its role: **"3. Understanding the module contract"** rather than presenting it as a procedural step. A brief forward-reference in Sections 1 and 2 ("all fields must satisfy the module contract in Section 3") would help.

---

## 4. "Add resources" (Section 4) is an orphan

It's marked optional but wedged between the contract and validation. It references `SKILL.md` and `_PIPELINE_DIR`, concepts introduced in passing within Section 1's code block. A reader hitting this section cold may not remember what `_PIPELINE_DIR` is or where `SKILL.md` lives in their project.

**Fix:** Either merge this into each shape's section (it's shape-dependent) or move it after validation as an "Extending your pipeline" section. If it stays, it needs a sentence re-establishing context: *"In the sibling-file shape (Section 1), resource files live next to `SKILL.md`; in the package shape (Section 2), they live inside the package directory."*

---

## 5. "Common gotchas" introduces novel concepts out of nowhere

> "Decision routing uses `PipelineVerdict.recommendation`. Gate stages need `kind="decide"` steps that return `StepResult(verdict=PipelineVerdict(recommendation="..."))`."

This is the first mention of `PipelineVerdict`, gate stages, `kind="decide"`, and `kind="decision"` edges. None of these appear in the minimal examples above. The gotcha reads like it was transplanted from a more advanced document.

**Fix:** Either (a) remove gotchas that aren't directly relevant to the creation flow, or (b) add a brief "Advanced patterns" section *before* gotchas that introduces these concepts. The gotcha about `--inputs` values being strings fits naturally — it's a direct consequence of Section 5. The `PipelineVerdict` gotcha does not.

---

## 6. The two shapes are asymmetrically treated

Section 1 gets a 60-line code block, contextual notes, and a file-tree diagram. Section 2 gets 15 lines of code and a pointer to `evidence_pack/`. This asymmetry makes the typed package shape feel like an afterthought, even though the intro frames both as equally valid.

**Fix:** Either give Section 2 the same depth as Section 1, or explicitly position the graph-driven shape as "the recommended starting point" and the typed package shape as "for advanced use cases — see the full example at…"

---

## Suggested reordering

1. **Intro** — with decision heuristic
2. **Graph-driven shape** — concept preview → scaffold → code → notes (merged with shape-specific resources)
3. **Typed package shape** — same depth; template → code → notes
4. **Module contract** — as a reference section, clearly marked as such
5. **Validate and run** — with the `--inputs` gotcha folded in
6. **Advanced patterns** — decision routing, cycles, `loop_condition`, `PipelineVerdict`
7. **Reference implementations** — as-is

This ordering follows the reader's natural arc: decide → build → understand the rules → verify → extend.


[sequencing and logical progression]
# Sequencing & Logical Progression Critique

This document has a solid skeleton but its flow undermines the reader at nearly every decision point. Here's where the sequence breaks down and how to fix it.

---

## 1. The intro sets up a fork, then abandons the reader there

> *"There are two common shapes: 1. Graph-driven sibling-file module … 2. Typed package module …"*

The next heading is "Quick start: graph-driven sibling-file module." The reader hasn't been told *why* they'd pick shape 1 over shape 2. They either follow blindly or skip ahead to Section 2 to comparison-shop — which means they're reading the document out of order by design.

**Fix:** Add a one-paragraph decision guide immediately after the intro. Something like:

> *"Choose the graph-driven shape when you need stage graphs, loops, or quick CLI workflows. Choose the typed-package shape when you need typed ports, hooks, or resume/continuation. Section 1 details the first; Section 2 details the second."*

---

## 2. Explanations trail the thing they explain

Under Section 1, the 40-line code block comes first, then this:

> *"Notes: `ctx.inputs` receives the positional CLI argument as `"draft"` … `ctx.state` is the graph executor's mutable run state … `ctx.plan_dir` is the run's artifact directory."*

A reader hits `ctx.inputs`, `ctx.state`, `ctx.plan_dir` inside the code and has to either guess or keep scrolling. Those three bullet points should **precede** the code block as a short "Key concepts" primer.

---

## 3. The contract table arrives too late

Sections 1 and 2 both ask the reader to write module-level fields (`name`, `description`, `driver`, `entrypoint`, etc.). But the authoritative table defining those fields — what's required, what values are valid — doesn't appear until **Section 3**. By then the reader has already written the fields twice, possibly incorrectly.

**Fix:** Move the contract table (Section 3) to immediately follow the intro/decision-guide. Both implementation sections can then reference it with a brief "Fill in the contract fields per the table above."

---

## 4. Section 5 re-explains what Section 1 already covered

> *"The positional argument maps to `ctx.inputs["draft"]`. `--inputs key=value` maps to `ctx.inputs["key"]` as a string."*

This is a near-verbatim repeat of the Notes bullets from Section 1. The duplication isn't just redundant — it fragments the reader's mental model across two locations. If the Notes in Section 1 are sufficient, Section 5 should just reference them. If Section 5 is the canonical place, move the Notes there.

---

## 5. "Common gotchas" references concepts the reader hasn't met

> *"Decision routing uses `PipelineVerdict.recommendation`. Gate stages need `kind="decide"` steps … The executor matches that against `kind="decision"` edges."*

Neither `PipelineVerdict`, gate stages, `kind="decide"`, nor `kind="decision"` edges appear anywhere in Sections 1–2. This gotcha is dangling — the reader can't act on it because the concept was never introduced.

**Fix:** Either introduce decision routing in the relevant implementation section (probably Section 1, since it's graph-specific), or bracket the gotcha with a forward-reference like *"If your pipeline uses decision routing (see the Megaplan reference in Section 7)…"*

---

## 6. Reference implementations are listed last but needed first

Section 7 is a flat list of example codebases. An experienced reader wants to scan these *before* building — to anchor the abstractions in concrete code. The file-tree diagram in Section 1 is helpful, but it's no substitute for pointing to a living example early.

**Fix:** Move the reference list into the decision-guide paragraph (alongside the shape descriptions), so the reader can open a relevant example *before* they start scaffolding.

---

## Summary of recommended reorder

| Current | Proposed |
|---|---|
| Intro (two shapes, no guidance) | Intro + decision guide + reference list |
| Section 1 (graph-driven) | Contract table (current §3) |
| Section 2 (typed package) | Section 1 (preceded by concept bullets) |
| Section 3 (contract table) | Section 2 |
| Section 4 (resources) | Section 4 (unchanged) |
| Section 5 (validate/run) | Section 5 (deduplicated) |
| Section 6 (gotchas) | Section 6 (with forward-refs for dangling concepts) |
| Section 7 (references) | (folded into intro) |

The content is all there — it's just sequenced for someone who already knows Arnold, not for someone learning it.


[succinctness and removing redundancy]
## Succinctness Critique

This is a solid reference doc, but it carries noticeable fat. Here's where to cut.

---

### 1. The Two-Shapes Description (Opening Section)

**Current:**
> "There are two common shapes: 1. Graph-driven sibling-file module — created with `arnold pipelines new`. Best for stage graphs, loops, and quick CLI workflows. These live under `arnold/pipelines/megaplan/pipelines/` and are executed by the Megaplan graph executor. 2. Typed package module — created by copying `arnold/pipelines/_template`. Best for typed ports, hooks, resume/continuation, and model-less adapters. These live as packages directly under `arnold/pipelines/`."

**Problem:** The closing sentence then repeats the same comparison: "Both shapes expose the same module-level contract fields and both must pass `arnold pipelines check`." You've told us twice that both are valid.

**Fix:** Cut the last sentence — it's already implied by presenting them as parallel options in the same doc. Also trim the shape descriptions. "Best for" is marketing, not instruction:

> "Two shapes are available: 1. **Sibling-file** (`arnold pipelines new my-pipeline --driver graph`) lives under `megaplan/pipelines/` and suits graph-driven workflows. 2. **Package module** (copy `_template`) lives directly under `arnold/pipelines/` and suits typed ports, hooks, and resume."

---

### 2. The Module-Level Contract Table Is Redundant

The contract appears *three times*: once implicitly in the code example (every field is there with a comment), once as a commentary list ("Notes:" bullets below the code), and once as the full table in Section 3.

**Fix:** Kill the "Notes:" bullets after the code block. The code is self-documenting with inline comments. Keep only the table in Section 3 (which has the Required? column — that's the unique value-add). Move the `- ctx.inputs` / `ctx.state` / `ctx.plan_dir` notes into a small "Key objects" aside — those aren't contract fields, they're runtime concepts currently stranded under the code block.

---

### 3. Repeated "Both shapes" / "Both must"

Phrases like "Both shapes expose the same module-level contract" and "Both shapes must pass `arnold pipelines check`" appear in the intro and again in Section 3's preamble.

**Fix:** Say it once. Section 3's opening can be simply: "All pipeline modules must declare these fields as module-level literals — the static manifest reader parses them with AST literal eval."

---

### 4. Section 2: The Skeleton Example Over-Explains

The paragraph after the `__init__.py` example:

> "Replace the skeleton with real stages in `arnold/pipelines/my_pipeline/pipelines.py` using `arnold.pipeline.builder.PipelineBuilder`. See `arnold/pipelines/evidence_pack/` for a complete example with ports, hooks, and resume."

**Problem:** "with ports, hooks, and resume" is the same list from the intro ("typed ports, hooks, resume/continuation"). The pointer to `evidence_pack/` is already given in Section 7.

**Fix:** Cut to: "Replace the skeleton with real stages using `PipelineBuilder`. See `evidence_pack/` for a full example."

---

### 5. Section 5: Run Command Has Redundant Commentary

> "The positional argument maps to `ctx.inputs["draft"]`."
> "`--inputs key=value` maps to `ctx.inputs["key"]` as a string."

This was already explained in the code-block notes and again in the "Common gotchas" (`--inputs` values are strings). 

**Fix:** Drop the two bullets under the bash block. They're covered.

---

### 6. Section 7: Reference List Is Verbose

Seven entries with long paths repeated. "arnold/pipelines/" appears in four of them.

**Fix:** State the base path once:

> **Reference implementations:** (all under `arnold/pipelines/`)
> - `_template` — minimal package module
> - `evidence_pack` — typed ports, hooks, resume
> - `megaplan/pipeline.py` — canonical sibling-file graph
> 
> **Docs:** `docs/arnold/authoring-guide.md` (hands-on) and `package-authoring-contract.md` (field-level contract).

---

### Summary of Cuts

| Location | Cut |
|---|---|
| Intro "Both shapes…" sentence | Already implied |
| Code-block "Notes:" bullets | Covered by Section 3 table + move runtime notes elsewhere |
| Section 2 post-example paragraph | Redundant lists; trim |
| Section 5 two bullets | Duplicate of earlier/following content |
| Section 7 entries | Condense with shared base path |

Estimated savings: **~150–200 words** without losing a single actionable instruction. The doc is reference material — every sentence should earn its keep by being the *only* place that information lives.


[clarity of purpose and main point]
## Clarity-of-Purpose Critique

### The core problem: this document is two documents fighting for dominance

You've titled this "Creating a new Arnold pipeline," which promises a **how-to guide**. But the opening section hedges by describing "two common shapes" — and from that point on, the document can't decide whether it's:

1. A **decision tree** helping users choose between graph-driven vs. typed-package modules, or
2. A **reference manual** enumerating every field, option, and gotcha.

These two purposes dilute each other. A reader who lands here wanting a quick answer ("how do I make a pipeline?") hits a wall of taxonomy before any actionable instruction.

### Specific weak spots

**The opening paragraph buries the lede:**

> "Arnold discovers pipeline modules under `arnold/pipelines/`. There are two common shapes:"

This starts with implementation trivia (discovery path) before answering the reader's actual question: *what should I do?* By the time the reader reaches the first actionable command, they've already had to absorb a classification system they may not need.

**Fix:** Open with a one-sentence frame that makes the purpose undeniable, something like:

> "You have two paths to create a pipeline, and the right one depends on what you're building. If you need stage graphs, loops, or quick CLI workflows, start with §1 (graph-driven). If you need typed ports, hooks, or resume/continuation, start with §2 (typed package)."

Then collapse the taxonomy into a choice table.

**The two "shapes" are described backwards from what the reader needs.** Section 1 is labeled "Quick start" — but it's only a quick start for one audience. The other audience gets Section 2, which assumes they already know to copy a template. Neither section tells someone who doesn't know which shape they need how to decide. The decision criteria are scattered: "Best for stage graphs, loops" sits in the intro bullet; "Best for typed ports, hooks" sits in the next bullet. These should be adjacent and prominent.

**The "Module contract" table (Section 3) breaks the flow entirely.** It's reference material dropped into a procedural document. A reader following the step-by-step instructions in §1 or §2 will reach this table and ask: "Am I supposed to do something with this now? Did I miss a step?" The table is useful but belongs at the end as a validation checklist, not as interstitial dead weight.

**"Common gotchas" (Section 6) undermines the procedural structure.** It lists warnings that should have been inline with the steps they protect against. For example:

> "Guard every cycle. If your graph has a back-edge..."

This only applies to graph-driven modules (§1) and should live alongside the `build_pipeline()` example, not in a catch-all section the reader may skip.

### What the document's "main point" appears to be

Reading charitably: the main point is **"Here is everything you need to know to create and validate a working Arnold pipeline module, regardless of which shape you need."** That's an encyclopedia entry, not a focused document.

If you want this to be a **procedural guide**, restructure it as a single-path walkthrough with a fork point:

1. Decision: graph-driven or typed? (2-sentence rule + table)
2. Scaffold (the `pipelines new` or `cp` command)
3. Fill in the module contract (the table, now positioned as a "fill this in" step)
4. Add steps/logic (inline each shape's example with shape-specific gotchas)
5. Add resources (optional)
6. Validate and run

If you want this to be a **reference page**, retitle it "Arnold pipeline module reference" and organize by concept (module contract, shapes, discovery, validation, gotchas) rather than by a faux-procedural structure.

### Bottom line

The document is thorough and accurate, but it's unclear who it's for and what they should *do* after reading it. Pick one purpose — guide or reference — and cut everything that serves the other. The material is strong; the framing is what's hurting you.


[tone and voice consistency]
This is a technical reference document for a developer tool, and it mostly holds a steady instructional voice. That said, a few specific spots pull the tone in conflicting directions — some toward an agent-facing prompt, some toward casual developer advice, some toward dry reference. Here are the concrete weak spots and what to do about them.

---

### 1. Audience whiplash in the opening

> “Use this skill when the user wants to add a new, named, runnable pipeline to the Arnold harness.”

This opening sentence speaks to an AI *agent* (it’s a skill trigger). Every paragraph that follows speaks to a human *developer* with second-person imperatives: “Replace the scaffolded…”, “Copy the template…”, “See `arnold/pipelines/evidence_pack/` for a complete example.”

That’s two different audiences on the same page, and the reader feels it immediately. Pick one. If this is agent-facing documentation, the entire doc should stay in that frame (“The agent should guide the user to…”, “When the user asks for a typed package module…”). If it’s developer-facing, cut the opening line and start with something like:

> “Add a new named runnable pipeline to the Arnold harness by following one of two module patterns below.”

---

### 2. The “common shapes” language is oddly casual

> “There are two common shapes:”

“Shapes” is vague and informal in a document that otherwise names things precisely (“graph-driven sibling-file module,” “typed package module”). The word appears nowhere else. Swap it for “patterns,” “structures,” or “module forms” — any term already in the document’s working vocabulary.

---

### 3. Sentence fragments in the pattern descriptions

> “Best for stage graphs, loops, and quick CLI workflows.”  
> “Best for typed ports, hooks, resume/continuation, and model-less adapters.”

These two fragments stand alone in the bullet descriptions. They read like clipped notes, not like the full-sentence prose used everywhere else in the document. Either attach them to the preceding sentence (“…created with `arnold pipelines new`, which works best for stage graphs…”) or make them complete:

> “This pattern works best for stage graphs, loops, and quick CLI workflows.”

---

### 4. The “Common gotchas” heading breaks register

The rest of the document uses straight technical headings: “Quick start,” “Minimal module,” “Module contract,” “Validate and run.” Then you hit:

> “Common gotchas”

“Gotchas” is blog/tutorial casual. The surrounding voice is reference-manual neutral. Replace with “Common pitfalls,” “Troubleshooting,” or “Things to watch for” — whichever matches what similar internal docs use.

---

### 5. Inconsistent imperative style inside “Common gotchas”

The first three bullets are declarative rules:

> “No leading `_` or `.` in module or directory names; discovery silently skips them.”

Then you get a sharp command:

> “**Guard every cycle.**”

Then back to descriptive:

> “Decision routing uses `PipelineVerdict.recommendation`.”

Pick a form and stick with it. Easiest fix: make every bullet a direct statement of the rule pattern:

> “- Names must not start with `_` or `.`; discovery skips them silently.  
> - `build_pipeline()` must be callable with zero arguments from the registry’s perspective.  
> - Every cycle must carry a `loop_condition` on at least one stage, or `arnold pipelines check` fails with `unguarded_cycle_detected`.  
> - Decision routing through gate stages requires `kind="decide"` steps returning a `PipelineVerdict`; the executor matches against `kind="decision"` edges.”

One voice per section.

---

### 6. A small prose-level repetition

> “Both shapes expose the same module-level contract fields and both must pass `arnold pipelines check`.”

The doubled “both” lands awkwardly. Drop the second:

> “Both shapes expose the same module-level contract fields and must pass `arnold pipelines check`.”

---

### Summary

The document’s core voice — direct, technical, instructional — is solid. The fixes come down to three decisions:

1. **Pick one audience** (agent or human) and rewrite the opening to match.
2. **Replace a handful of casual words** (“shapes,” “gotchas”) with the register the rest of the doc already uses.
3. **Make the “pitfalls” section grammatically uniform** so it doesn’t oscillate between command, rule, and explanation.

Those three changes will make the voice feel deliberate and trustworthy from the first line to the last.


[jargon and accessibility]
# Jargon & Accessibility Critique

This document is written for an insider who already lives in the Arnold codebase. For anyone else — including a new team member — it's a wall of undefined terms and assumed context. Below are the specific problems, quoted and fixed.

---

## 1. The opening sentences bury the reader in undefined proper nouns

> *"Arnold discovers pipeline modules under `arnold/pipelines/`."*

What is Arnold? What is a pipeline module? What does "discovers" mean — filesystem scanning? A registry? The reader is five words in and already lost. Open with a one-sentence plain-English definition:

**Suggested:** *"Arnold is the project's task-runner. A 'pipeline' is a named, callable workflow — like a script with defined inputs, steps, and outputs. This guide shows you how to create one."*

---

## 2. "Graph-driven sibling-file module" is a dense compound noun with no unpacking

> *"Graph-driven sibling-file module — created with `arnold pipelines new`. Best for stage graphs, loops, and quick CLI workflows."*

You're asking the reader to hold four concepts at once (graph, sibling, file, module) before explaining any of them. "Sibling-file" in particular is an internal layout term that means nothing to a newcomer. Break it apart:

**Suggested:** *"A single `.py` file that sits alongside other pipelines inside `megaplan/pipelines/`. The runner treats each file as a node graph — you connect stages with edges. Use this for simple, linear-to-branching flows."*

---

## 3. "Megaplan graph executor" is referenced but never defined

> *"...executed by the Megaplan graph executor."*

The word "Megaplan" appears six times. It's clearly a subsystem, but the reader never learns what it is or why it matters. Either define it once or replace it with a functional description.

**Suggested (add early):** *"Megaplan is Arnold's built-in graph runtime. It walks stages, passes state between them, and handles branching."*

---

## 4. "Typed ports, hooks, resume/continuation, and model-less adapters" is a features dump, not a decision aid

> *"Best for typed ports, hooks, resume/continuation, and model-less adapters."*

This tells the reader *what* features exist but not *when* to choose this shape. It reads like a bullet list from a design doc. Ground it in a scenario:

**Suggested:** *"Choose the package shape when you need: structured input/output schemas (typed ports), the ability to pause and resume mid-run, or lifecycle hooks (setup/teardown). If none of those ring a bell, start with the graph-driven shape."*

---

## 5. "Module-level contract fields" and "static manifest reader parses them with AST literal eval"

> *"Both shapes expose the same module-level contract fields..."*  
> *"The static manifest reader parses them with AST literal eval; it cannot follow function calls, aliases, or computed values."*

"Contract fields" is abstract. "AST literal eval" is a Python internals term. This is implementation leaking into user docs. Say what the reader actually needs to know:

**Suggested:** *"These variables at the top of your file tell Arnold what your pipeline is called, how to run it, and what it supports. Keep them as plain strings and tuples — don't use variables, function calls, or `+=`. Arnold reads them without executing your code."*

---

## 6. "Nullary callable" is a term virtually no one searches for

> *"Nullary callable returning a `Pipeline`."*

In 15 years of Python I've heard this word maybe twice. Say "a function that takes no arguments" or "a zero-argument function."

---

## 7. The "Common gotchas" section is full of inside-baseball

> *"Guard every cycle. If your graph has a back-edge, attach a `loop_condition` to a stage in the cycle, otherwise `arnold pipelines check` fails with `unguarded_cycle_detected`."*

What is a back-edge? A cycle in what? This assumes the reader has already drawn a graph and is debugging it. Rephrase as a preventive rule:

**Suggested:** *"If one of your stages routes back to an earlier stage (creating a loop), you must add a `loop_condition` to one stage in that loop. Otherwise the validator will reject it as an unguarded cycle."*

---

## 8. "Decision routing" paragraph is pure internals

> *"Decision routing uses `PipelineVerdict.recommendation`. Gate stages need `kind='decide'` steps that return `StepResult(verdict=PipelineVerdict(recommendation='...'))`. The executor matches that against `kind='decision'` edges."*

This is the most egregious example. Five domain-specific types in two sentences, zero explanation of *why* you'd use this. If decision routing is an advanced topic, either give it its own section with a concrete example or link to a reference. As written, it's noise to a beginner and redundant to an expert.

---

## 9. The table in Section 3 is the clearest part — but undermines itself

The table is actually good: required/optional, one-liner notes. But then the prose underneath repeats the same information in denser form. Cut the prose; let the table stand. Also, "Declare as `None`; the static manifest reader requires it" is confusing — if it's "recommended" but "required" by a specific reader, pick one story.

**Suggested note:** *"Always include these fields, even if empty. Some tooling will fail without them."*

---

## Summary

This document has strong bones — the CLI commands, the annotated code block, and the file-tree diagrams are genuinely helpful. The problem is that every piece of explanatory prose is addressed to someone who already understands the system. Fix that by:

1. Defining Arnold and "pipeline" in the first paragraph.
2. Replacing all internal subsystem names (Megaplan, manifest reader, etc.) with functional descriptions.
3. Killing "nullary" and "AST literal eval" — use plain developer English.
4. Turning the "decision routing" paragraph into a link to advanced docs or a worked example.
5. Letting the table in Section 3 do its job without redundant, jargon-laced commentary.


[transitions between sentences and paragraphs]
## Transition Critique

This document has solid technical bones but reads like a stack of index cards — each section stands alone, and the reader is left to manufacture the connective tissue. Below are specific weak spots.

---

### 1. Missing bridges between major sections

The starkest issue: every `##` heading lands without a handoff from the preceding content.

**From §1 (graph-driven) to §2 (typed package):**

The jump is:

> — `ctx.plan_dir` is the run's artifact directory.
>
> ## 2. Typed package module

No pivot sentence exists. The reader must infer "I'm done with graph-driven; now we're switching shapes." **Suggestion:** Add a single line before the heading, e.g., *"The graph-driven module above works for simple linear or DAG workflows. When you need typed ports, hooks, or resume logic, use the package-module shape instead."*

**From §5 (Validate and run) to §6 (Common gotchas):**

> `--inputs key=value` maps to `ctx.inputs["key"]` as a string.
>
> ## 6. Common gotchas

The "how to run" section ends on a detail about string inputs, then — thud — a list of pitfalls. **Suggestion:** Bridge with something like *"Before you ship, watch for these recurring pitfalls that trip up new pipeline authors."*

**From §6 (gotchas) to §7 (references):**

Gotchas feel terminal, yet another section follows. A simple *"For deeper patterns beyond these basics, study the following implementations"* would signal that §7 isn't an appendix dropped from the sky.

---

### 2. Orphaned notes block (§1)

After the large code example, the document cuts straight to:

> Notes:
> - `ctx.inputs` receives…

These three bullets explain critical context objects, but there's no framing sentence connecting them to the code the reader just saw. **Suggestion:** Lead with *"The code above uses three context objects worth understanding:"* — then deliver the bullets.

---

### 3. Ungrouped gotchas firehose (§6)

Seven bullets span unrelated domains: naming rules, function signatures, declaration quirks, cycle guards, decision routing, path hygiene, and string coercion. They appear in no discernible order, forcing the reader to context-switch seven times with zero handrails.

**Suggestion:** Cluster them into two or three thematic groups with brief lead-ins:

*"Discovery and registration pitfalls:"* (leading underscore, nullary `build_pipeline`, omitted `default_profile`/`supported_modes`)
*"Graph execution pitfalls:"* (unguarded cycles, decision routing with `PipelineVerdict`)
*"Path and input hygiene:"* (absolute paths, `--inputs` string coercion)

This turns a pile of warnings into a scannable, memorable structure.

---

### 4. Jarring shift inside §1

> The CLI-visible name is the hyphenated form: `my-pipeline`.
>
> ### Minimal module

The one-sentence note about hyphenated naming floats alone between a file-tree display and a subheading. It's a non-sequitur placed like a transition but functioning as neither. **Suggestion:** Fold it into the preceding paragraph or make it the last sentence before the subheading: *"The CLI-visible name is the hyphenated form (`my-pipeline`). Below is the minimal working module."*

---

### 5. The intro actually works

Credit where due: the opening three paragraphs move cleanly from "use this skill when" → "Arnold discovers" → "two common shapes," and the "Both shapes expose…" wrap-up sentence ties the numbered list together. This is the document's best transitional writing — the rest simply doesn't sustain that standard.

---

### Summary prescription

Add one bridging sentence before every `##` heading and before every bulleted list that lacks a lead-in. Group the gotchas into clusters. That alone would transform this from a reference dump into a guided document that carries the reader forward rather than making them orient themselves anew after every heading.


[overall structure]
This is a solid technical reference with a clear spine, but its structure creates unnecessary friction for two distinct reader journeys: the "I know what I want" reader and the "help me decide" reader. Here are the key structural issues, ordered by impact.

---

## 1. The contract table arrives too late — and it's the most important section

The intro promises that both shapes "expose the same module-level contract fields," but the actual contract table (Section 3) sits *after* both implementation walkthroughs. A reader building a pipeline via Section 1 or 2 will have already written code before they encounter the `default_profile` / `supported_modes` requirement — a gotcha the document itself later calls "rejected by the static manifest reader."

**Fix:** Move the contract table (or a condensed version) to the intro, right after the two-shapes overview. Something like:

> Here's the shared contract both shapes must satisfy. Keep this in mind as you work through either path below.

Then the detailed per-field notes in Section 3 can remain as a reference anchor. This also eliminates the awkward "Module contract (both shapes)" header — a section that is purely reference material stranded between two procedural sections.

---

## 2. No decision point between the two shapes

The intro describes the two shapes side-by-side — "Best for stage graphs, loops, quick CLI" vs. "Best for typed ports, hooks, resume" — but never says: *If you have X, choose Y.* The reader is left to pattern-match adjectives against their own mental model of the system.

**Fix:** Add a short, explicit decision section after the intro. A simple table would work:

| You want to... | Choose |
|---|---|
| Script a quick linear/looping graph | Graph-driven sibling-file (Section 1) |
| Expose typed input/output ports | Typed package (Section 2) |
| Support resume/continuation | Typed package (Section 2) |

This gives permission to skip the irrelevant half of the document.

---

## 3. Section 1 is overloaded; Section 2 is anemic

Section 1 spans ~70 lines including a massive inline code block with dense comments. Section 2 is effectively "copy the template, here's a 15-line `__init__.py`, go read `evidence_pack`." The asymmetry suggests one of two things: either the graph-driven path genuinely requires more explanation (in which case the typed path needs equal treatment), or the typed path is under-documented here and should be fleshed out with the same level of scaffold-to-working-pipeline progression.

**Fix:** Either trim Section 1's "Minimal module" to the essential structure and push the fully-annotated version to an appendix/reference, or give Section 2 a comparable walkthrough — even a single concrete stage added via `PipelineBuilder` would close the gap. The current "see `evidence_pack/`" handoff is a structure smell; the document should be self-contained enough that the reference is genuinely optional.

---

## 4. "Common gotchas" is a grab-bag at the wrong end of the document

Seven bullet points covering naming rules, callable signatures, static manifest constraints, graph cycles, decision routing, absolute paths, and type coercion. These are unrelated concerns dumped into a single flat list. Worse, several of them duplicate or should have preempted confusion from Sections 1-2:

- "Declare `default_profile` and `supported_modes` even if empty" — should be in the contract table, not buried in gotchas.
- "Guard every cycle" — belongs in Section 1's graph discussion, since that's where loops are introduced.
- "`--inputs` values are strings" — belongs in the "Minimal module" notes, where `ctx.inputs` is first discussed.

**Fix:** Distribute these into their relevant sections. What remains as a "gotchas" section should be genuinely surprising behaviors (e.g., "discovery silently skips files with leading `_`") — the kind of thing a reader wouldn't anticipate from the rest of the document.

---

## 5. Section ordering undermines the workflow

Current order: Shape 1 → Shape 2 → Contract → Resources → Validate → Gotchas → References.

A reader following either shape linearly will: build their module → *then* discover the contract → *then* learn about optional resource directories → *then* finally validate. Validation should come immediately after construction, not after resource setup. And resources (prompts, profiles) feel like a natural subsection of each shape's instructions, not a standalone section.

**Suggested reorder:**

1. Intro + decision guide
2. Contract summary (the shared rules)
3. Shape 1 (graph-driven) → validate
4. Shape 2 (typed package) → validate
5. Resources (as a short shared section)
6. Surviving gotchas (the genuinely unexpected stuff)
7. Reference implementations

---

## One smaller note

The YAML frontmatter has `name: new arnold pipeline` with spaces. If this is consumed by a template system that expects a slug, that's a bug waiting to happen. If it's purely decorative, it's fine — but worth flagging given the document's own warning about hyphenated vs. underscored naming conventions.


[reader engagement and momentum]
## Engagement & Momentum Critique

This document reads like a well-organized reference manual — which is precisely its problem. Reference manuals are for people who already know what they're doing and just need a reminder. But this is pitched as a *skill/guide* for someone creating a pipeline "from scratch." That reader needs momentum, not taxonomy.

### The opening kills forward motion

> "Arnold discovers pipeline modules under `arnold/pipelines/`. There are two common shapes:"

This is an implementation detail before the reader even knows what they're building. You're explaining *how Arnold finds things* before the reader has written a single line. Compare with: "You're about to create a runnable Arnold pipeline. By the end, you'll have a working module you can execute with `arnold run`. Here's the fastest path." Now the reader has a destination and a reason to keep going.

The two-shapes taxonomy is premature. The reader hasn't touched code yet. They're being asked to absorb an architectural distinction — graph-driven vs. typed package — with zero experiential scaffolding. Defer this or collapse it: "Pick your path: need quick CLI workflows? Start with option 1. Need typed ports or resume support? Jump to option 2."

### "Quick start" is neither quick nor a start

The label promises velocity, but the section delivers a 65-line code block immediately after the file-tree diagram. That's a wall. The reader's momentum slams into it. Break the code into annotated fragments interspersed with what each piece *does*. Or better: show the 8-line version first — the absolute minimum to get `arnold run` working — and *then* expand.

The file-tree diagram itself is good. It gives spatial orientation. More of that instinct, less of the monolithic code dump.

### The contract table is a momentum sink

Section 3 is pure reference material dropped into the middle of a procedural guide. The reader is in "doing" mode from sections 1-2, and suddenly they're parsing a 10-row table of field definitions. This should be an appendix or a sidebar, not a sequential step. At minimum, surface only the three fields the reader *must* get right to avoid failure (`name`, `entrypoint`, `build_pipeline`) and link to the full table.

### Gotchas arrive too late

> "No leading `_` or `.` in module or directory names; discovery silently skips them."

By section 6, the reader may have already named their module `_my_pipeline` and wasted time debugging. These should be inline warnings at the point of action — next to the `cp` or `mkdir` command, not six sections later. "Silently skips" is a particularly painful failure mode; front-load it.

### The ending deflates

> "Where to look for reference implementations" followed by a bullet list of file paths.

There's no closure, no "you're done — here's what you can build next." The document just... stops. A reader who's followed sections 1-5 has a working pipeline. Celebrate that. Then offer a natural next step: "Now add a decision gate" or "Try hooking in a subagent launcher." Give them somewhere to direct their momentum.

### Structural fix (without rewriting everything)

1. **Lead with the outcome, not the architecture.** One sentence: what the reader will have built.
2. **Move the two-shapes decision to a 3-line inline choice** with clear use-case signals, not abstract taxonomy.
3. **Split the "Quick start" code into 3 chunks:** create → minimal skeleton → first run. Show output from each.
4. **Inline the critical gotchas** next to the commands that trigger them.
5. **Move the contract table to an appendix** or collapse to essential fields in a callout box.
6. **End with a concrete next-step prompt**, not a file listing.

The bones of this document are solid — the information is correct, the examples are useful, the structure is logical for *reference*. But for a guide that's meant to carry someone from zero to working pipeline, it needs to think less about completeness and more about forward motion. Cut anything that doesn't pull the reader toward a running `arnold run`.


--- REVISED VERSION ---
