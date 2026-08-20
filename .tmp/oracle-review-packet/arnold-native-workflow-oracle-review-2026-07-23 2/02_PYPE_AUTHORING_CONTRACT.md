# Arnold `.pype` Authoring Contract

## Status and authority

- **Status:** adopted target contract for Native Parity and Native Workflow
  Platformization.
- **Decision record:** `docs/arnold/pype-authoring-format-oracle-brief.md`.
- **Current implemented baseline:** `docs/arnold/python-shaped-authoring-contract.md`.
- **Implementation owner:** Native Parity S1 freezes the grammar/schema and S2
  implements it before any Megaplan product cutover.
- **Experimental public-tooling owner:** Native Workflow Platformization S2B.
- **Stable publication owner:** Native Workflow Platformization S6, formerly
  S5 before insertion of S2B.

This file is the one normative authoring-format authority shared by the two
epics. North Stars, milestone briefs, package descriptors, compilers, CLIs,
generated manifests, locks, source maps, diagnostics, examples, and
conformance fixtures may elaborate it but may not redefine it.

The contract is deliberately rigorous at durable boundaries and deliberately
small for authors. It does not prescribe arbitrary directory names, line
counts, or extraction frequency.

## 1. Three authoring layers

### 1.1 Workflow topology

Workflow topology lives in `.pype`. It owns visible product composition:
branches, bounded loops, fanout/fanin, child workflow calls, call-site policy,
suspension/reentry, typed outcomes, and terminal proposals.

### 1.2 Durable steps and effects

A step is a typed leaf unit. It owns declared retry, timeout, custody,
idempotency, durable observation, and effect boundaries. Shared steps and
effect adapters live in ordinary `.py`; private file-local steps may live in
the `.pype` that owns them.

### 1.3 Supporting Python

Ordinary `.py` owns types, schemas, policies, prompts, model/tool bindings,
effect adapters, and deterministic pure helpers. It may compute data. It may
not author admitted workflow topology.

The allowed dependency direction is:

```text
workflow -> workflow
workflow -> step
step     -> pure helper / declared effect adapter
```

These directions are invalid in every mode because they have no coherent
durable meaning:

```text
step   -> workflow
step   -> decorated step
helper -> workflow / decorated step / effect adapter
```

Shared implementation used by multiple steps is an undecorated pure helper,
not one step calling another step directly.

## 2. One file, one workflow

### PYPE-FILE-01 — Sole canonical workflow

Every `.pype` contains exactly one top-level `@workflow` definition. That
definition is the file's canonical workflow. A second workflow or no workflow
is a compile error for every durable claim.

No `main` name, `__all__`, export statement, declaration-order rule, or
file-local root selector identifies the canonical workflow. The exactly-one
rule does.

### PYPE-FILE-02 — Allowed top-level source

A `.pype` top level may contain only:

- static imports;
- literal, statically understood metadata;
- exactly one `@workflow`;
- zero or more private file-local `@step` definitions; and
- zero or more deterministic, statically sliceable, digest-bound helpers.

It may not contain arbitrary top-level execution, direct external I/O,
conditional/dynamic/star imports, runtime registration, reflection, `eval`,
mutable global control state, or a hand-authored manifest/route table.

### PYPE-FILE-03 — Private local steps and helpers

A step or helper defined in `.pype` is private to that file:

- it cannot be imported, re-exported, or invoked by another source file;
- it has no independently published or pinnable identity;
- its behavior-relevant transitive digest folds into the containing workflow's
  contract digest; and
- promoting it to a shared `.py` step is explicit executable identity drift
  recorded by the migration mechanism.

Private steps exist to keep small workflows pleasant. A step that needs reuse,
independent provenance, independent durable testing, or a separately versioned
contract belongs in `.py`.

### PYPE-FILE-04 — Naming and organization are guidance

The filename should match the workflow's logical name and projects should group
workflow files by product domain. Mismatch, file size, directory naming, and
extraction heuristics are advisory unless they cause a separate semantic
violation.

One-workflow-per-file does not mean one-file-per-operation. Inline structured
blocks remain in the parent. Extract a named child workflow when it owns at
least one of:

- closed outcomes that the parent routes on;
- its own suspension/checkpoint/retry lifecycle;
- reuse;
- independent durable test/provenance requirements; or
- a semantic child identity that must survive parent refactoring.

## 3. Workflow composition

### PYPE-IMPORT-01 — Canonical-only workflow imports

A `.pype` may statically import:

- the one canonical workflow from another `.pype`; and
- typed steps, effect contracts, policies, schemas, types, prompts, and pure
  helpers from `.py`.

Only the canonical workflow crosses a `.pype` file boundary. Internal steps and
helpers are unreachable from other files.

Python-shaped import syntax is accepted only when it resolves unambiguously
through the static Arnold package graph. A `.py` and `.pype` source may not
claim the same logical module. Aliases preserve original provenance.

### PYPE-IMPORT-02 — No source execution or laundering

Discovery and linking parse syntax and descriptors; they never execute author
source. Dynamic imports, conditional imports, star imports, import-time
registration, wrapper/callback discovery, and re-export laundering fail before
durable lowering or authority.

Cross-package workflow imports must be permitted by the producer's canonical
Arnold package descriptor. Package convenience APIs cannot create a second
workflow body or independently advertised canonical identity.

### PYPE-IMPORT-03 — Cycles and bounded loops

Import cycles, recursive workflow calls, and mutually recursive workflow calls
always fail. A supported bounded loop is an explicit finite workflow construct,
not source or call-graph recursion.

### PYPE-HOST-01 — Workflow and subworkflow

`workflow` is the authored component kind. “Subworkflow” describes a workflow
invoked by a parent at one call site; it is not a separate decorator, source
kind, or file format.

A workflow is root-hostable by default. `root_hostable=False` explicitly
narrows it to child hosting. Root admission additionally requires a total typed
root-result adapter for all declared business and lifecycle/control outcomes.
Hostability never grants execution authority.

Legacy/generated `subflow` and `SubpipelineRef` forms may remain internal
decoding/lowering artifacts. They cannot author new topology.

## 4. Steps, effects, and helpers

### PYPE-STEP-01 — Responsibility test

Work must be a step when any of these apply:

- it performs filesystem, network, subprocess, model, tool, or other external
  I/O;
- it needs retry, timeout, custody, idempotency, reconciliation, or independent
  cancellation semantics;
- it produces a durably observable result;
- it needs independent execution provenance; or
- it can fail with a typed outcome the workflow handles.

### PYPE-STEP-02 — Leaf law

A step may call deterministic helpers and declared effect adapters. It may not
invoke a workflow or another decorated step, create durable children, suspend
workflow state, or own product topology.

### PYPE-EFFECT-01 — Declared external interaction

An effect adapter lives in `.py`, declares its external interaction and replay/
idempotency/reconciliation contract, and is invoked only by a step. Workflows
and helpers cannot call effect adapters directly.

### PYPE-HELPER-01 — Data up, control down

A helper may return deterministic data that a workflow visibly branches on. It
may not return a workflow, step, callable target, route table, policy owner, or
effect handle that is then invoked dynamically.

Reachable helper dependencies are scanned transitively, source-mapped, and
digest-bound. Wrapping or aliasing cannot hide I/O, nondeterminism, mutation, or
dynamic topology.

## 5. Ordinary `.py` workflows

### PYPE-PY-01 — Preview-only bridge

An `@workflow` body in ordinary `.py` is unsupported durable source. It may run
only in explicit `authoring_preview` with:

- fresh ephemeral identity;
- fake or sandbox-only effects;
- no durable checkpoint, replay, resume, comparison, admission, publication,
  or certification claim; and
- provenance marking the result as non-durable preview output.

Durable sandbox, admitted production, replay/resume, and certification reject a
`.py` workflow before authority or effect intent. Preview artifacts can never
be promoted or relabeled as durable history.

Pinned pre-cutover `.py` workflows are handled only through the legacy
resolution/migration contract in §8, not through new admission.

## 6. Logical identity and package authority

### PYPE-ID-01 — Logical workflow identity

The stable logical key is:

```text
(distribution_name, logical_workflow_name)
```

`logical_workflow_name` is the explicit `@workflow(id=...)` when present and
otherwise the decorated function name. It must be unique within the
distribution. A collision fails before lowering and lists both provenance
chains.

Filename, filesystem path, wheel resource path, and local import alias are
provenance, not identity. The filename/function-name match remains advisory.

### PYPE-ID-02 — Executable identity

Executable identity adds a contract digest covering at least:

- typed input/output and closed outcomes;
- hostability and root-result requirements;
- authored topology and call-site policies;
- logical child workflow references;
- shared step/effect/schema/policy references and versions;
- private step/helper code and transitive reachable helper slices; and
- behavior-relevant prompts, models, tools, and declared nondeterminism.

Formatting, comments, physical file moves, and proven non-behavioral metadata
do not change the contract digest.

### PYPE-ID-03 — Package descriptor ownership

The canonical Arnold package descriptor—not a source file—owns:

- the optional `default_pipeline`;
- the cross-package canonical-workflow allowlist (package visibility, not a
  source-file export table), defaulting to all canonical
  workflows unless deliberately narrowed;
- content-addressed source/descriptor correspondence;
- workflow/step/effect dependencies;
- executable/component locks; and
- the append-only identity migration log.

S1 must inventory and extend the existing Arnold pack/lock descriptor rather
than create a parallel `package.toml` unless that inventory proves no canonical
owner exists.

An explicit CLI/API request may select an eligible package-visible pipeline instead of
the package default before admission. Resolution then freezes one logical
pipeline key and contract digest across manifest, lock, admission, checkpoints,
replay, source maps, and proof. Any disagreement rejects before authority.

## 7. Change and migration classes

### PYPE-MIG-01 — Provenance-only changes

A physical file move, wheel resource relocation, import alias change, comments,
formatting, and proven non-behavioral metadata are provenance changes when the
logical key and contract digest remain unchanged.

### PYPE-MIG-02 — Identity drift

These require an explicit migration record, otherwise a pinned run rejects:

- logical workflow rename;
- signature, closed outcome, or hostability change;
- workflow extraction or inline;
- private-step promotion to shared identity or the reverse;
- child identity or call-site-policy change; and
- any behavior-relevant code, helper, schema, effect, prompt, model, tool, or
  dependency change not covered by a declared compatibility rule.

A migration record binds old and new logical/executable identities, state and
checkpoint transformation, outcome conservation, effect/idempotency
disposition, applicable run/occurrence scope, authority decision, provenance,
and verifier receipt. It is never a blanket alias.

## 8. Legacy retention and conversion

### PYPE-LEGACY-01 — Read-only legacy resolution

Pinned `.pypeline`, authored `subflow`, and durable `.py` workflow artifacts
remain resolvable only while a nonterminal occurrence depends on their exact
identity, or until that occurrence accepts migration, new-attempt, or
quarantine.

Legacy readers:

- cannot author, compile, admit, route, publish, or certify new work;
- resolve only exact content-addressed pinned artifacts;
- are covered by negative tests and an ownership/retention record; and
- are retired when no live pin requires them.

Historical evidence is immutable and is never rewritten to manufacture `.pype`
proof.

### PYPE-LEGACY-02 — Mechanical conversion

The supported converter:

- splits each legacy authored workflow into one `.pype`;
- classifies steps as private or shared `.py`;
- replaces authored `subflow` with ordinary workflow imports/calls;
- emits package descriptor/allowlist/default updates;
- writes identity migration records atomically; and
- refuses ambiguous control, effect, identity, or state conversions.

Unsupported conversion enters explicit manual migration or quarantine; it
never guesses.

## 9. Execution-mode disposition

| Violation | Authoring preview | Durable sandbox | Admitted production | Replay/resume | Certification |
| --- | --- | --- | --- | --- | --- |
| `@workflow` in `.py` | warn, ephemeral/faked only | reject | reject | reject | reject |
| hidden effect/nondeterminism in helper | warn, ephemeral/faked only | reject | reject | reject | reject |
| step invokes workflow/decorated step | reject | reject | reject | reject | reject |
| dynamic topology/import | warn, non-durable only | reject | reject | reject | reject |
| recursive workflow call | reject | reject | reject | reject | reject |
| identity drift against pinned occurrence | fresh identity | warn and require fresh fork/migration for durability | reject without accepted migration | reject without accepted migration | reject |
| descriptor/source disagreement | warn, no durable claim | reject | reject | reject | reject |
| name/path/layout/size guidance | advisory | advisory | advisory | advisory/report | advisory/report |
| preview artifact claiming durable history | reject | reject | reject | reject | reject |

Structural impossibilities reject in every mode. Unsupported-but-functionally
executable Python may be explored only where the mode makes its lack of durable
meaning explicit.

## 10. Required diagnostics

Every rejection carries:

- a stable code;
- definition and reachable call spans;
- logical workflow/step identity when available;
- the violated responsibility or identity rule;
- the execution claim that cannot be made; and
- a supported rewrite, such as:
  - “move this workflow into its own `.pype`”;
  - “extract this operation into a typed step”;
  - “extract shared implementation into a pure helper”;
  - “return data and branch visibly in the workflow”; or
  - “record an explicit identity migration.”

Diagnostics never silently downgrade the requested execution mode.

## 11. Tooling required before stable publication

One-workflow-per-file is not stable-platform viable without:

- extract-region/child-workflow-to-`.pype`;
- inline-child-workflow;
- promote-private-step-to-shared-`.py`;
- atomic migration-log/package-descriptor updates for those refactors;
- `.pype` formatting, linting, import navigation, and identity hover;
- a static topology view generated without source execution;
- one-command authoring preview with fake/sandbox effects;
- source/descriptor/wheel correspondence verification; and
- developer benchmarks for common extension tasks and both monolith and
  file-explosion counterexamples.

Native Parity S2 must provide the compiler, diagnostics, conversion primitive,
and minimal local preview required for Megaplan cutover. Platformization S2B
must productize the refactors, authoring SDK, packaging/editor integration, and
benchmarks before reusable extraction or third-party stability claims.

### Ownership and handoff matrix

This table fixes delivery ownership without prescribing premature class names.
“Extend” means modify the canonical surface after inventory; it never means
create a parallel implementation.

| Surface | Canonical path family / authority | Native Parity S2 | Platform S2A | Platform S2B | Post-epic owner |
| --- | --- | --- | --- | --- | --- |
| Grammar, parser, lowering | `arnold/workflow/{authoring,source_compiler,compiler}.py` | Implement adopted grammar and Megaplan-required lowering | Consume typed IR; own runtime/lifecycle interfaces, not parsing | Productize the same frontend/linker as public experimental SDK | Arnold workflow platform |
| Validation, diagnostics, source maps | `arnold/workflow/{validation,diagnostics,inspect}.py` | Ship stable codes/spans/rewrites needed by `GO-FORMAT` | Own runtime/admission faults and source-map preservation through execution | Complete cross-file/package diagnostics, navigation, traceback, lint/format | Arnold workflow platform |
| Descriptor, discovery, lock, source correspondence | Existing `arnold/workflow/discovery/`, `arnold/pipeline/native/pack_*`, and `arnold/manifest/` authorities selected by S1 inventory | Extend the canonical descriptor/lock; prove exact package correspondence | Enforce frozen identity/lock at admission/checkpoint | Productize package discovery/default/allowlist and all install-form verification | Arnold workflow platform |
| Logical identity, provenance, migration log | The same canonical descriptor/lock/manifest authority; no separate registry | Implement workflow/digest keys, legacy mapping, and Megaplan migration records | Enforce pin/compatibility/migration/new-run/quarantine semantics | Productize move/rename/extract/inline/promote transactions and APIs | Arnold workflow platform |
| Converter, preview, semantic refactors | Generic `arnold/workflow/` and `arnold/cli/workflow*.py` surfaces chosen by inventory | Ship legacy converter and minimal ephemeral preview | Supply faithful runtime sandbox/fork hooks | Own supported refactors, preview/test SDK, and transactional workspace updates | Arnold workflow platform |
| CLI and editor integration | `arnold/cli/workflow*.py`; any Megaplan editor adapter is transitional product integration | Make suffix/check/compile/inspect work for the cutover | Expose runtime inspect/test hooks | Own generic CLI/editor/navigation/format/lint experience | Arnold workflow platform |
| Megaplan workflow sources and product bindings | `arnold_pipelines/megaplan/workflows/` | Own file split, product migration, golden parity, and outgoing handoff | Consume only as a conformance client | Consume only for generic-tooling regression; do not redo migration | Megaplan product package |

After S6, generic grammar/tooling/identity/package maintenance belongs to the
Arnold workflow platform. Megaplan owns only its workflow files, product
steps/bindings, and parity evidence. A change that would make either side copy
or fork the other side's canonical surface requires a contract amendment, not
an expedient local implementation.

## 12. Minimum blocking conformance

Native Parity S2 must create:

- conformance index `docs/arnold/pype-authoring-conformance.yaml`;
- validator `scripts/validate_pype_authoring_contract.py`; and
- content-addressed receipt
  `.megaplan/initiatives/megaplan-native-parity-corrective/go-format-receipt.json`
  with schema ID `arnold.megaplan.go_format_receipt.v1`.

The validator consumes the contract/index, exact compiler and diagnostic
versions, descriptor schema, locks, fixture outputs, commit/tree, and checkout/
editable/wheel/sdist/cloud artifacts; it independently recomputes the receipt
verdict. S2 cannot close and S3A cannot start unless that invocation is green.
The chain format presently supports a special final-conformance hook only, so
S3A's brief carries this explicit machine precondition in addition to its
ordinary dependency on S2.

At minimum, executable fixtures prove:

1. zero or two workflows in one `.pype` reject;
2. a canonical workflow imports and invokes another canonical workflow;
3. private steps/helpers cannot be imported or independently addressed;
4. private code and reachable helper changes affect the containing contract
   digest exactly when behavior changes;
5. shared steps/effects/schemas/policies resolve from `.py` without executing
   author source;
6. `.py` workflows run only in explicit preview and cannot cross any durable or
   promotion boundary;
7. step-to-workflow, step-to-step, helper-to-effect, dynamic invocation,
   import cycles, and workflow recursion reject;
8. explicit bounded loops pass and are not mistaken for recursion;
9. hidden/transitive I/O, entropy, global mutation, route smuggling, and
   import-time registration reject with both definition and call spans;
10. checkout, editable install, wheel/sdist, and pinned cloud resolve the same
    logical graph and contract digests;
11. source/descriptor/lock/admission/checkpoint disagreement rejects;
12. physical file moves preserve identity/provenance as declared, while
    rename/extract/inline/hostability changes require migration;
13. pinned legacy artifacts resolve while new legacy authoring/admission fails;
14. preview output cannot resume, promote, or certify;
15. a compact root delegating hidden topology to a handler fails;
16. a multi-workflow monolith and a trivial-workflow file explosion fail their
    respective semantic/readability gates; and
17. unfamiliar developers complete the named extension tasks without manually
    editing generated catalogs, manifests, locks, route tables, or identity
    registries.
