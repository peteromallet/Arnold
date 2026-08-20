# `.pype` Authoring Format — Decision Brief for Oracle Review

## Status

This document is the retained design/oracle decision record, not the normative
compiler contract. The hardened Alternative A recommendation has been adopted.
The normative target is `docs/arnold/pype-authoring-contract.md`; where this
brief's exploratory alternatives or questions differ, that contract wins.

The earlier multi-export `.pype` module model is retained below only as a
rejected alternative. Native Parity and Platformization must not treat it as a
simultaneous supported contract.

The decision matters because Arnold is intended to become a platform on which
developers build durable workflows. The format must make sophisticated systems
possible without making ordinary systems ceremonious. Its structure should be
rigorous enough for deterministic compilation, replay, source mapping,
packaging, and safe effects while remaining obvious, attractive, and easy to
extend.

## The crux

Arnold needs three clearly separated authoring layers:

1. **Workflow topology** — what happens, in what structure, and under which
   typed control policy.
2. **Durable steps and effects** — the typed units that perform work and cross
   retry, custody, replay, or external-effect boundaries.
3. **Supporting Python** — types, schemas, policies, pure helpers, prompt
   builders, and implementation details that do not own hidden workflow
   topology.

The central format question is where named workflows may be authored:

- only in one-workflow-per-file `.pype` sources;
- as multiple exports from a `.pype` module;
- or also as specially marked, nested-only definitions inside ordinary `.py`
  modules.

The current lean is deliberately simple:

> Every durable authored workflow, whether used as a root or as a child, lives
> in exactly one `.pype` file. Every `.pype` file contains exactly one
> top-level workflow. Ordinary `.py` supplies typed leaf implementations and
> supporting code, never an alternative workflow topology.

The oracle should test whether that simplicity is worth the additional files,
and whether a more permissive model can preserve equally clear discovery,
identity, enforcement, and developer understanding.

## Product priorities

The winning design should optimize for these priorities together rather than
maximizing any one of them.

### 1. Legibility

A developer should be able to find the workflow files, open the application
entry workflow, follow imports, and understand the product flow without
searching handlers, route tables, registries, generated manifests, or runtime
adapters.

Named loops, branches, fanout/fanin, retries, suspension, reentry, child
workflows, policy, and terminal outcomes must remain visible at their semantic
ownership point.

### 2. Clean abstraction boundaries

The platform should make the correct dependency direction natural:

```text
workflow -> workflow
workflow -> step
step     -> ordinary helper / declared effect adapter
```

It should make these directions invalid:

```text
step -> workflow
helper -> hidden workflow route
runtime/handler/manifest -> new product topology
```

A workflow should coordinate. A step should perform one typed unit of work. A
helper should calculate. An effect adapter should interact externally under a
declared durable boundary.

### 3. Developer ease and edit locality

Small workflows should remain small. Authors should not need manifests,
registries, identity tables, generated IDs, or control-plane knowledge to add a
normal step or child workflow.

The common edit should be local:

- add or modify one step;
- add one branch or retry policy at its call site;
- extract one named child workflow;
- run it in a fast local harness;
- receive a source-located diagnostic when its durability claim is invalid.

### 4. Rigorous durable semantics

Admitted execution must be statically knowable and reproducible. Arnold must
be able to bind:

- the selected root;
- every imported workflow and step;
- source and call sites;
- policy and schema versions;
- behavior-relevant helper dependencies;
- the complete executable/component lock; and
- the generated runtime representation.

The compiler must discover topology without executing author source or relying
on import-time side effects.

### 5. Accommodating rather than overbearing enforcement

Restrictions should attach to the claim being made.

- A non-durable authoring preview may warn and run unsupported code with fresh
  ephemeral identity and fake or sandbox-only effects.
- Durable sandbox, admitted production, replay/resume, and certification must
  reject hidden topology, direct effects, or ambiguous executable identity
  before authority or effect intent.
- Diagnostics should name the source span, violated responsibility, and a
  supported rewrite such as “extract this into a step” or “move this workflow
  into its own `.pype`.”
- Readability guidance should normally be advisory. Semantic ambiguity,
  identity drift, hidden effects, and route ownership are hard failures.

### 6. Aesthetic organization without arbitrary ceremony

The platform should push projects toward domain-oriented packages, not giant
`components.py` catalogues or hundreds of unexplained tiny files. File and
directory boundaries should correspond to semantic ownership rather than
compiler accidents.

The framework should provide strong defaults while allowing a project to group
workflow files by feature, product region, or reusable package.

## Terminology

### Pipeline

A pipeline is the authored application or product flow selected for a run. In
the current one-file/one-workflow direction, a `.pype` file is a pipeline source
artifact.

### Workflow

A workflow is a typed executable topology with inputs, outcomes, child calls,
policies, and durable lifecycle semantics.

### Subworkflow

“Subworkflow” is a hosting role, not a separate authored component kind. The
same workflow is a root when selected for a run and a subworkflow when invoked
by a parent, subject to its declared hostability.

Arnold may retain an internal generated `SubpipelineRef` or equivalent to link
compiled artifacts. That does not require a second user-authored `subflow`
language.

### Step

A step is a typed leaf operation invoked by a workflow. Work should be a step
when it:

- performs filesystem, network, subprocess, model, tool, or other external I/O;
- needs retry, timeout, custody, idempotency, or reconciliation;
- produces a durably observable result;
- needs independent execution provenance; or
- may fail in a way the workflow handles through a declared outcome.

A step cannot invoke a workflow. If work contains child topology, it is a
workflow and belongs above the step boundary.

### Supporting Python

Ordinary `.py` modules may contain:

- typed step implementations;
- effect adapters;
- types and schemas;
- policy values and descriptors;
- prompts and model/tool bindings;
- deterministic pure helpers; and
- package-facing convenience APIs that do not author routes.

Supporting Python may compute values. It may not secretly choose product
routes, create durable children, suspend or resume workflow state, or perform
undeclared effects.

## Current working direction

### One workflow per `.pype`

Each `.pype` contains:

- imports;
- literal, statically understood metadata;
- exactly one top-level `@workflow`;
- optionally small deterministic helpers whose dependencies are digest-bound;
- possibly small file-local steps if the final contract permits them.

Each `.pype` does not contain:

- a second top-level workflow;
- separately importable internal subworkflows;
- a hand-maintained route table or generated manifest;
- arbitrary top-level execution;
- direct external I/O; or
- dynamically discovered imports or topology.

If a named internal region needs its own outcomes, retry lifecycle,
checkpointing, suspension, child identity, reuse, or independent test surface,
it becomes another `.pype`.

### Canonical workflow and entry selection

Exactly one top-level `@workflow` makes that workflow canonical for the file.
No function name such as `main` is magical, and the file needs no
`default_root` declaration to disambiguate its contents.

A package may optionally declare a default pipeline:

```text
default_pipeline = arnold_pipelines.megaplan.workflows.workflow
```

A CLI or API may explicitly select another eligible pipeline before admission.
Resolution freezes one logical pipeline identity across the generated manifest,
lock, admission record, checkpoint, replay, and source map. Filesystem and
wheel resource paths are provenance rather than portable identity.

### Composition

One `.pype` may statically import the canonical workflow from another `.pype`
and invoke it as a child:

```python
# planning.pype

from arnold.workflow import workflow
from .critique import critique
from .steps import prepare_plan


@workflow
async def planning(request: Request) -> Plan:
    plan = await prepare_plan(request)
    findings = await critique(plan)
    return plan.apply(findings)
```

`critique.pype` contains exactly one workflow. It may be nested-only through a
typed `root_hostable=False` contract, or it may be usable as either a root or a
child. Nested status does not change its authoring format.

Imports are resolved statically. Aliases retain original provenance. Import
cycles, recursive workflow calls, identity/version collisions, and dynamic or
star imports fail before durable admission. A supported bounded loop is an
explicit finite workflow construct, not recursive workflow invocation.

### Steps and local code

The intended responsibility boundary is:

```text
.pype             durable topology and call-site policy
typed .py step    durable leaf work and declared effects
ordinary .py      pure implementation, schemas, policies, types
```

Whether `.pype` should allow small local `@step` definitions remains an oracle
question. Allowing them improves one-file readability for small pipelines;
requiring reusable steps in `.py` creates a sharper topology/implementation
boundary. Either way, a step must remain a typed leaf and cannot contain or
invoke workflow topology.

## Megaplan-shaped organization

The current Megaplan representation report demonstrates the full flow in one
large illustrative Python source. That is useful for semantic review, but its
critique, gate, tiebreaker, execute, and review regions each own enough durable
topology to merit a named workflow boundary.

A clean target could be:

```text
arnold_pipelines/megaplan/workflows/
  workflow.pype

  plan_quality/
    cycle.pype
    critique.pype
    gate.pype
    tiebreaker.pype
    steps.py
    policies.py
    types.py

  delivery/
    cycle.pype
    execute.pype
    execute_batch.pype
    review.pype
    steps.py
    policies.py
    types.py

  control/
    steps.py
    policies.py
```

- `workflow.pype` owns the root product flow.
- `plan_quality/cycle.pype` owns the bounded critique/gate/revise cycle.
- `critique.pype` owns evaluator retry, lens fanout, and keyed merge.
- `gate.pype` owns signal construction, gate call, validation/reprompt, debt
  effect, and its closed decision.
- `tiebreaker.pype` owns researcher/challenger work and the resulting
  human/system decision.
- `delivery/cycle.pype` owns finalize, approval, execute, review, and rework,
  including a named replan exit.
- `execute.pype` owns dependency-ready batching and blocked/retry behavior.
- `execute_batch.pype` is an independently durable mapped child.
- `review.pype` owns worker/check fanout, merge, review decision, and human
  verification.
- `control/` supplies typed human gates, effects, and reconfiguration
  operations. Resulting product routes remain visible in the calling workflow.

A generic `components/` directory is possible, but domain-oriented
`plan_quality/`, `delivery/`, and `control/` boundaries are more legible and
less likely to become a miscellaneous catalogue.

Migration-only files such as `front_half.pype` should disappear after cutover
because “front half” is not a durable product abstraction.

## Credible design alternatives

### Alternative A — One workflow per `.pype`

This is the current lean.

Advantages:

- `.pype` has one crisp meaning;
- workflow discovery is equivalent to listing `.pype` files;
- one stable source identity maps to one authored topology;
- no root-export ambiguity within a file;
- source maps, locks, packaging, and change impact are straightforward;
- named child workflows receive first-class test and diagnostic surfaces; and
- large systems are encouraged toward explicit domain boundaries.

Risks:

- a poorly decomposed project can accumulate many small files;
- tightly related workflows may require more navigation;
- extraction boundaries may be chosen too early or too mechanically; and
- authors may resist creating a file for a very small child.

Mitigations:

- keep ordinary structured blocks inside their parent;
- extract only named regions with independent durable semantics or reuse;
- organize by domain directories;
- provide editor navigation and extraction tooling; and
- treat size guidance as advisory rather than enforcing arbitrary line counts.

### Alternative B — Multiple workflow exports per `.pype`

A `.pype` behaves as a restricted Python module that may export zero or many
steps and workflows. Runs use `package.module:export` or a declared default.

Advantages:

- related workflows can be colocated;
- reusable workflow libraries need fewer files;
- Python-module familiarity is stronger; and
- library-only workflow modules become possible.

Risks:

- `.pype` means “workflow-related module,” not “pipeline”;
- entry selection, export visibility, re-exports, and defaults need additional
  rules;
- declaration-order and accidental-root bugs require more negative machinery;
- one file change can affect several executable identities;
- modules can become large component catalogues; and
- the simplest user question—“what pipeline is this file?”—has no single
  answer.

### Alternative C — `.pype` roots plus nested-only workflows in `.py`

Only root/application workflows require `.pype`. Ordinary Python modules may
contain multiple marked `@workflow(root_hostable=False)` definitions.

Advantages:

- fewer files;
- natural colocation with related step implementations;
- standard Python import, IDE, and packaging behavior;
- an easy migration path from existing decorated Python; and
- flexibility for private implementation-level workflow decomposition.

Risks:

- there are two workflow discovery and authoring paths;
- `.pype` may become a thin facade over hidden topology in `components.py`;
- static compilation must analyze an otherwise executable Python import graph;
- import-time effects and dynamic re-exports become recurring hazards;
- behavior-relevant dependency slicing and digests become more complex;
- source, descriptor, wheel, and `.pype` identities can disagree;
- a nested-only workflow can be invoked directly or later made root-hostable
  outside the intended admission path;
- reviewers cannot enumerate workflow topology by finding `.pype`; and
- large Python component catalogues can recreate the split authority that
  Native Parity is intended to remove.

This alternative is not inherently impossible. The oracle should decide
whether its ergonomic gain is large enough to justify the second authoring
surface and the additional enforcement contract.

### Alternative D — Ordinary Python only

All workflows and steps live in `.py`; decorators and typed descriptors mark
which definitions are statically compilable.

Advantages:

- no custom file extension;
- best compatibility with existing Python tools;
- familiar imports and packaging; and
- minimal apparent ceremony.

Risks:

- the distinction between executable Python and statically interpreted durable
  topology becomes subtle;
- directly calling decorated functions can bypass workflow semantics;
- import execution, reflection, monkey-patching, and dynamic construction must
  be heavily constrained;
- finding the product topology requires semantic indexing rather than file
  discovery; and
- the platform loses an obvious visual and tooling boundary for durable source.

## Questions for the oracle

The oracle should not merely choose the most permissive or most restrictive
option. It should identify the smallest coherent model that remains pleasant
for both a three-step application and a Megaplan-sized system.

### Format meaning

1. Should `.pype` mean exactly one pipeline, or a restricted module containing
   workflow-related exports?
2. Is one-workflow-per-file a valuable semantic identity rule or only a style
   preference that the language should not enforce?
3. Does permitting library-only or multi-workflow `.pype` materially improve
   real authoring, or mostly create export/root machinery?
4. If the general platform permits multi-export `.pype` modules, should
   products such as Megaplan enforce a stricter one-workflow profile? Is that
   useful flexibility or harmful profile fragmentation?

### Root and child semantics

5. Is “subworkflow” correctly modeled as a hosting role of `workflow`, or is
   there a real semantic distinction that warrants a separate authored kind?
6. Should every `.pype` workflow be root-hostable by default, nested-only by
   default, or explicit about hostability?
7. Should the package, rather than the source file, own the optional default
   pipeline?
8. Is the sole top-level `@workflow` sufficient to identify the file's
   canonical workflow, or should the source contain an explicit export?
9. What should be the stable logical identity when a workflow file is moved,
   renamed, re-exported, or installed at a different resource path?

### Composition and visibility

10. Should another workflow be allowed to import only the one canonical
    workflow from a `.pype`, or also reach internal named regions?
11. When does a structured block deserve extraction into a child workflow?
    Can that rule be taught without encouraging file explosion?
12. Should workflow imports look exactly like Python imports, use an explicit
    `.pype` intrinsic, or be declared through a package descriptor?
13. How should public/private workflow visibility work without introducing an
    elaborate export system?
14. Should circular workflow calls always fail, with bounded loops represented
    only by explicit workflow constructs?

### Steps and supporting Python

15. Should small file-local `@step` definitions be allowed inside `.pype`, or
    should every step implementation live in `.py`?
16. What precise responsibility test tells an author that a function must
    become a step?
17. Which pure helpers may be called from workflow topology, and how should
    their transitive dependencies and behavior-relevant digests be bound?
18. Should a step ever be allowed to invoke another step directly, or should
    all durable composition remain visible in the workflow?
19. How should the compiler distinguish a pure route calculation from hidden
    product routing or policy?

### Ordinary `.py` workflows

20. Is there a compelling use case for admitted nested-only workflows in
    normal `.py` that cannot be served cleanly by another `.pype`?
21. If `.py` workflows are allowed, can the compiler resolve them without
    executing imports, and can tooling prove that no direct-call bypass exists?
22. Can a mixed `.pype`/`.py` topology retain simple source discovery,
    source-to-lock identity, source maps, and wheel/cloud equivalence?
23. Would limiting `.py` workflows to non-durable preview capture most of the
    ergonomic benefit without creating a second production authoring path?
24. What happens when a nested-only `.py` workflow later needs root hosting,
    independent testing, suspension, or reuse in another package?

### Developer experience and enforcement

25. Which restrictions must be hard in every mode, which should block only
    durable admission, and which should remain advisory?
26. Can every important rejection produce an actionable rewrite rather than a
    framework-specific error?
27. How many files and concepts must a developer touch for the ten most common
    edits?
28. Does the model remain attractive for a small application, or is it
    optimized only for Megaplan-scale durability?
29. Does the model remain navigable at Megaplan scale, or does convenience for
    small applications lead to giant component modules?
30. Which editor, formatter, static-index, import-navigation, local-run, and
    test-harness capabilities are prerequisites for the format to feel easy?

### Migration and compatibility

31. How should existing authored `subflow`, normal-Python `@workflow`, and
    generated `SubpipelineRef` representations migrate without silently
    changing pinned run identity?
32. Should legacy readers be able only to resolve pinned artifacts, while new
    authoring rejects the old form?
33. Which change classes—file move, rename, extraction, inline, step move,
    helper edit, hostability change—are executable identity drift?
34. Which parts of the format are difficult to reverse after third-party
    developers begin publishing packages?

## Adversarial cases the oracle should test

The oracle's proposal should be applied to at least these cases:

1. A three-step linear application with one external effect.
2. A small application with one reusable child workflow.
3. A package containing reusable steps and two reusable workflows.
4. Megaplan's critique/gate/revise and execute/review/rework cycles.
5. A workflow suspended across deployment while one child file is moved.
6. A child workflow reused twice in the same parent with different bindings.
7. A developer attempting to hide network I/O in a pure helper.
8. A step attempting to invoke a workflow.
9. A normal `.py` module with import-time side effects and a marked workflow.
10. A wheel whose generated descriptor disagrees with its `.pype` resources.
11. A source import cycle and a legitimate bounded workflow loop.
12. A non-durable preview of unsupported Python followed by an attempted
    production resume or certification claim.
13. A deliberately bad one-file design containing root, critique, gate,
    tiebreaker, execute, and review workflows. Compare edit locality and review
    comprehension against the domain-oriented split.
14. A deliberately bad file-explosion design that promotes every trivial leaf
    operation into its own `.pype`. Verify that the proposed rules distinguish
    a durable child workflow from an ordinary step or structured block.
15. A compact but false design that delegates an entire delivery cycle to an
    opaque handler. Reject it even though its root source looks aesthetically
    simple.
16. Four unfamiliar-developer tasks: add a critique lens, a gate outcome, a
    human suspension, and a delivery branch. Measure authoritative files
    touched, diagnostics, generated surfaces touched, and time to explain the
    resulting topology correctly.

## Requested oracle output

The oracle should return:

1. its recommended model and the strongest reason to prefer it;
2. the strongest argument against its own recommendation;
3. a minimal normative file/import/identity contract;
4. two small syntax examples and one Megaplan-sized package layout;
5. a responsibility table for workflow, step, effect adapter, and helper;
6. the required compiler, packaging, source-map, and editor behavior;
7. warning-versus-error behavior by execution mode;
8. a migration plan from current `subflow`, `.py` workflow, and `.pypeline`
   forms;
9. concrete counterexamples that its rules reject; and
10. the decisions that must be frozen before third-party package publication
    versus those that can safely remain conventions.

## Adopted recommendation

The oracle review hardened and adopted this public contract:

1. One authored workflow per `.pype`.
2. Every named durable root or child workflow lives in `.pype`.
3. “Subworkflow” is a workflow's role at a call site, not a separate authored
   type.
4. Private file-local steps and pure helpers may remain in `.pype`; they are
   unimportable, independently unaddressable, and digest-bound to its workflow.
5. Ordinary `.py` owns reusable typed leaf steps, effects, schemas, policies, and pure
   helpers, not admitted workflow topology.
6. Workflow composition is visible only in `.pype`; steps cannot invoke
   workflows.
7. The package may declare one optional default pipeline; every admitted run
   freezes one logical pipeline identity.
8. Logical identity is distribution plus logical workflow name; paths are
   provenance, while logical/behavioral drift requires explicit migration.
9. Static linking never executes author source.
10. Unsupported Python may be explored in explicit non-durable preview, but
   durable modes reject hidden topology/effects with actionable diagnostics.
11. Domain directories organize related workflow files; generic component
   catalogues and arbitrary file-count rules are discouraged.
12. Internal runtime references may remain distinct generated artifacts, but
    they cannot become a second authored workflow language.
