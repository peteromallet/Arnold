# Arnold `.pype` Authoring Contract

## Status and authority

- **Status:** adopted target contract for Native Parity and Native Workflow
  Platformization.
- **Decision record:** `docs/arnold/pype-authoring-format-oracle-brief.md`.
- **Current implemented baseline:** `docs/arnold/python-shaped-authoring-contract.md`.
- **Implementation owner:** Native Parity S1 freezes the grammar/schema, S2F
  implements the frontend/identity/converter and closes GO-FORMAT, and S2R
  consumes it for durable runtime semantics before product cutover.
- **Experimental core-authoring owner:** Native Workflow Platformization S2B.
- **Experimental DX/tooling owner:** Native Workflow Platformization S3.
- **Stable publication owner:** Native Workflow Platformization S6, after the
  S2B core and S3 developer-tooling milestones.

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
effect adapters, deterministic pure helpers, and shared step implementations.
Those modules may use ordinary static Python and third-party imports. It may
compute data. It may not author admitted workflow topology or bypass declared
effect boundaries.

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
is a structural parse/link error in every execution mode. Preview flexibility
belongs to ordinary `.py`; it does not change what a `.pype` means.

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
- its full canonical transitive executable closure folds into the containing workflow's
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

`.pype` discovery and Arnold workflow/component linking parse syntax and
descriptors; they never execute author source. Dynamic imports, conditional
imports, star imports, import-time registration, wrapper/callback discovery,
and re-export laundering that participate in topology or Arnold component
resolution fail before durable lowering or authority. This rule does not ban
ordinary import mechanisms used internally by a locked third-party dependency
inside a step; its resolved code, optional features, Python/runtime environment
and plugin selection must nevertheless be pinned and cannot bypass topology or
effect declarations.

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

### PYPE-ROUTE-01 — Finite, named route discriminants

Every value that can select a workflow edge is declared separately from its
payload as a closed enum, a closed tagged union, or another statically finite
named discriminant. The compiler binds each variant to the exact source spans
and outgoing edges it can select.

An arbitrary payload, open string, mapping key, exception text, callable,
helper-returned target, or “whole payload” declaration is not a route
discriminant. Payload fields may inform a deterministic helper that returns a
declared discriminant; the workflow must then branch visibly on that
discriminant. Adding or removing a discriminant variant or its edge mapping is
executable identity drift.

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

### PYPE-STEP-03 — Ordinary Python dependency freedom

A shared step implementation in `.py` may use ordinary Python imports and
third-party packages. Arnold does not impose the `.pype` grammar on the
implementation inside a step. Every selected distribution/version, artifact
digest, declared optional feature, Python/runtime environment, plugin selection
and imported Arnold contract that can affect the durable result is recorded in
the transitive graph lock or an explicit pinned binding.

Import-time I/O, mutable registration, environment-derived behavior, runtime
plugin discovery, or dynamic dependency selection cannot alter topology,
policy, effects, identity, or a durable result outside an explicit pinned
binding or declared effect adapter. Imported code cannot invoke workflows or
decorated steps on the step's behalf. A normal library refactor under an
unchanged compatible requirement may preserve the caller component digest, but
selecting different concrete code changes the graph-lock digest.

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

### PYPE-POLICY-01 — Typed policy envelope

Policies live in ordinary `.py`, conventionally `policies.py`, as immutable
typed values, not as another authoring language. Every durable policy carries a
stable policy kind and schema version, recursively immutable canonical
serializable values, scope/attachment point, source provenance, deterministic
precedence, and a digest. Workflow and call-site application is visible;
inheritance and overrides are explicit.

A policy may parameterize retry/backoff, timeout/deadline, concurrency/fanout,
join/cancellation, resources/budgets, custody/worker requirements, effects,
human arbitration, checkpoints/retention, model/tool selection, or
reconfiguration. It may not contain a callable invocation target, open route
table, ambient environment lookup, mutable global default, or hidden product
branch. Route-affecting variants remain finite named discriminants visibly
handled by the workflow. An authored inline/call-site policy or policy-contract
requirement changes the caller component digest. An imported policy has its own
executable identity; selecting a different compatible concrete policy/value
changes that identity and the transitive graph-lock digest. Incompatible
schema/value/attachment changes require the declared migration/new-attempt/
quarantine disposition.

## 5. Ordinary `.py` workflows

### PYPE-PY-01 — Preview-only bridge

An `@workflow` body in ordinary `.py` is unsupported durable source. It may run
only in explicit `authoring_preview` with:

- fresh ephemeral identity;
- fake/ephemeral-only effect adapters with no sandbox or production durable
  effect history;
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
distribution.

`distribution_name` is a governed namespace, not an arbitrary local string.
The canonical package/registry authority binds it to an owning publisher key
or organization and an append-only delegation/lineage record. A fork either
uses a new distribution name or presents an accepted delegation/lineage record
authorizing continued use. Two candidates that claim the same logical key
through incompatible namespace authority are a collision; resolution fails
before lowering and lists both authority and provenance chains.

Multiple contract digests for the same logical key are normal version
evolution when they descend from the same authorized distribution lineage.
They are not collisions merely because their digests differ. Admission still
selects one exact version/digest, and resume still requires the declared
compatibility, migration, new-run, or quarantine disposition.

Filename, filesystem path, wheel resource path, and local import alias are
provenance, not identity. The filename/function-name match remains advisory.

### PYPE-ID-02 — Executable identity

Executable identity adds a contract digest computed by one pinned,
content-addressed executable-closure algorithm. Every digest-bearing artifact
records the algorithm ID and version. The initially adopted identifiers are:

```text
closure algorithm: arnold.pype.executable_closure.v1
semantic IR:       arnold.workflow.semantic_ir.v1
digest envelope:   arnold.workflow.executable_envelope.v1
graph lock:        arnold.workflow.graph_lock.v1
serialization:     RFC 8785 JSON Canonicalization Scheme
hash:              SHA-256
```

Before S2F starts, Native Parity S1 must publish content-addressed machine
schemas for the semantic IR, digest envelope, graph lock, every tagged scalar/
reference form, and the closed inclusion/exclusion corpus under those IDs.
Values without a defined canonical JSON tagged encoding reject;
implementations cannot stringify Python objects or choose another encoding
locally.

Under `arnold.pype.executable_closure.v1`, the compiler:

1. statically resolves the canonical workflow, its private definitions, every
   reachable helper slice, every imported shared step/effect/schema/policy
   requirement and locked Python distribution requirement, every logical child
   workflow requirement, and every declared prompt/model/tool/nondeterminism
   binding without executing author source;
2. lowers the workflow's own closed executable closure plus its direct
   dependency requirements to the versioned canonical semantic IR and
   canonical descriptor envelope;
3. includes typed input/output and closed outcomes, hostability and root-result
   requirements, authored topology and call-site policies, finite route
   discriminants, direct qualified dependency identities and required
   interface/contract digests or constraints, private and
   reachable helper bodies/constants, and all declared bindings; and
4. canonical-serializes the envelope with sorted mapping keys, preserved
   sequence order where order is semantic, explicit type/schema tags, and
   normalized scalar encodings before applying the pinned hash algorithm.

The version-1 exclusion list is closed and deliberately small: lexical
whitespace/formatting; comments; parser source-location coordinates; and
physical file/resource paths or local import aliases after they resolve to the
same qualified identity and executable digest. Nothing else—including
docstrings, literals, metadata, prompts, policies, defaults, annotations, or
reachable helper code—is excluded. An unknown syntax form or metadata field is
included by the canonicalizer or rejected; it is never silently classified as
non-behavioral.

Thus the digest changes exactly when the pinned canonical executable closure
changes, not when an implementation claims to understand whether runtime
behavior changed. Changing an IR/envelope/lock schema, canonicalization, or
hash algorithm creates a new algorithm version and an explicit executable-
identity compatibility or migration event; existing checkpoints, locks, and
receipts retain their pinned algorithm.

The component executable digest and the resolved graph lock have distinct
jobs:

- a workflow/component digest covers its own canonical body, interface,
  private/helper closure, call-site policy, bindings, and direct dependency
  contract requirements;
- it does **not** recursively fold the selected concrete executable digests of
  child workflows or shared steps into every ancestor;
- the separately canonicalized transitive graph lock records each selected
  dependency's governed logical identity, exact version, executable digest,
  digest-algorithm version, compatibility disposition, and dependency edges,
  then receives its own RFC-8785/SHA-256 graph-lock digest; and
- every admission, action/effect envelope, checkpoint, replay/resume decision,
  source map, and proof row binds both the selected root/component executable
  digest and the exact transitive graph-lock digest.

Changing a direct dependency requirement changes the caller's component
digest. Selecting a different concrete implementation under an unchanged
compatible requirement changes the graph-lock digest, not every ancestor
component digest. It is still a new admission binding; a pinned occurrence may
resume only under its original lock or an accepted compatibility/migration,
new-run, or quarantine disposition.

### PYPE-ID-03 — Package descriptor ownership

The canonical Arnold package descriptor—not a source file—owns:

- the optional `default_pipeline`;
- the governed distribution namespace owner/delegations/fork lineage;
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

`default_pipeline` selects only a workflow identity. It never selects, implies,
or synthesizes a root-result adapter. The invoking product/admission binding
owns the root-result adapter by default and must bind one total adapter
explicitly for the selected workflow and its exact result contract. A producer
may publish named root-adapter definitions and may nominate one named producer
default, but the invoking admission must still accept and pin that adapter (or
choose another eligible adapter). The selected adapter identity/version is part
of admission and executable proof.

## 7. Change and migration classes

### PYPE-MIG-01 — Provenance-only changes

A physical file move, wheel resource relocation, import alias change, comments,
formatting, and parser source-location changes are provenance changes when the
logical key and pinned-algorithm contract digest remain unchanged. No broader
“non-behavioral metadata” category exists outside the closed exclusion list in
`PYPE-ID-02`.

### PYPE-MIG-02 — Identity drift

These require an explicit migration record, otherwise a pinned run rejects:

- logical workflow rename;
- signature, closed outcome, or hostability change;
- workflow extraction or inline;
- private-step promotion to shared identity or the reverse;
- child identity or call-site-policy change; and
- any canonical executable-closure code, helper, schema, effect, prompt, model,
  tool, or dependency change not covered by a declared compatibility rule.

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

- cannot author, compile, admit, route, publish, or certify **new** work;
- resolve only exact content-addressed pinned artifacts;
- are covered by negative tests and an ownership/retention record; and
- are retired when no live pin requires them.

For an already admitted occurrence, resolution may supply the exact pinned
artifact to its frozen legacy runtime so that the occurrence can replay or
resume under its original identity and authority record. The resolver does not
select a route, reinterpret the artifact, silently compile it as `.pype`, or
admit a replacement occurrence. Migration to the new runtime remains an
explicit accepted migration.

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

## 9. Execution-mode disposition and store isolation

The single normative mode/disposition mapping is the versioned,
machine-readable registry at
`docs/arnold/workflow-execution-mode-dispositions.yaml`. Native Parity S1
freezes and content-addresses the adopted target version; Platformization S1
revalidates it as part of the experimental candidate before S2A executes it.
Every prose table, diagnostic matrix,
brief, generated document, CLI severity, and conformance profile is derived
from that registry and is informative only; no runner or consumer may carry a
second severity table. The following authoring-format view states required
coverage but does not redefine the registry:

| Violation | Authoring preview | Durable sandbox | Comparison | Admitted production | Certification |
| --- | --- | --- | --- | --- | --- |
| `@workflow` in `.py` | warn, ephemeral/faked only | reject | reject | reject | reject |
| hidden effect/nondeterminism in helper | warn, ephemeral/faked only | reject | reject | reject | reject |
| step invokes workflow/decorated step | reject | reject | reject | reject | reject |
| dynamic topology or dynamic `.pype` import | warn, non-durable only | reject | reject | reject | reject |
| recursive workflow call | reject | reject | reject | reject | reject |
| identity drift against pinned occurrence | fresh identity | fresh fork or accepted migration | fresh comparison identity | reject without accepted migration | reject without accepted migration |
| descriptor/source disagreement | warn, no durable claim | reject | reject | reject | reject |
| name/path/layout/size guidance | advisory | advisory | advisory | advisory/report | advisory/report |
| preview artifact claiming durable history | reject | reject | reject | reject | reject |

Structural impossibilities reject in every mode. Unsupported-but-functionally
executable Python may be explored only where the mode makes its lack of durable
meaning explicit.

The same registry contains the capability/store access matrix. Store classes
are logical authority classes, not hostnames or shared physical services:

| Class | Authoring preview | Durable sandbox | Comparison | Admitted production | Certification |
| --- | --- | --- | --- | --- | --- |
| ephemeral fixture/debug state | isolated fresh namespace | isolated fresh namespace | isolated fresh namespace | reject | isolated certification fixture only |
| sandbox checkpoint/WBC/effect history | reject | isolated fresh experiment/fork namespace | read copied inputs; write isolated comparison history | reject | isolated certification fixture only |
| content-addressed artifact store | read explicitly exported immutable inputs; writes only to preview namespace | explicit sandbox capability and namespace | read copied/recorded inputs; writes only to comparison namespace | admitted capability and production namespace | isolated certification namespace plus explicit read of pinned production evidence |
| evidence/proof store | no authoritative writes | no authoritative writes | no authoritative writes | admitted producers only; never grants authority | governed certification producers/verifiers only |
| production checkpoint/WBC/authority/Custody/effect/idempotency/cache stores | reject | reject | read only through a declared redacted/copy boundary; never direct mutation or key reuse | exact admitted capabilities and logical namespaces only | production reads only when the profile declares them; mutations use dedicated certified fixtures, never live product keys |

Sharing a physical backend does not merge logical classes. Every grant binds
mode, store class, capability, namespace, run/experiment lineage, read/write
verbs, retention, and effect/idempotency domain. Preview, sandbox, comparison,
and certification defaults receive no production mutation capability; a
content-addressed backend is not safe merely because content is immutable.

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
- one-command authoring preview with fake/ephemeral-only effects, plus a
  separately explicit durable-sandbox command when durable isolated testing is
  requested;
- source/descriptor/wheel correspondence verification; and
- developer benchmarks for common extension tasks and both monolith and
  file-explosion counterexamples.

Native Parity S2F must provide the compiler, diagnostics, conversion primitive,
and minimal local preview required for Megaplan cutover. Platformization S2B
must productize the S4-blocking parser/linker, package/identity/converter and
transactional-refactor core. Platformization S3 must complete the generic
CLI/editor/navigation/format/lint/topology/local-authoring experience and
benchmarks before reusable extraction or third-party stability claims.

### Ownership and handoff matrix

This table fixes delivery ownership without prescribing premature class names.
“Extend” means modify the canonical surface after inventory; it never means
create a parallel implementation.

| Surface | Canonical path family / authority | Native S2F/S2R | Platform S2A | Platform S2B | Platform S3 | Post-epic owner |
| --- | --- | --- | --- | --- | --- | --- |
| Grammar, parser, lowering | `arnold/workflow/{authoring,source_compiler,compiler}.py` | S2F implements adopted grammar and Megaplan-required lowering; S2R consumes only | Consume typed IR; own runtime/lifecycle interfaces, not parsing | Productize the same frontend/linker as public experimental SDK | Consume; no alternate parser | Arnold workflow platform |
| Validation, diagnostics, source maps | `arnold/workflow/{validation,diagnostics,inspect}.py` | S2F ships codes/spans/rewrites for GO-FORMAT; S2R preserves maps through runtime | Own runtime/admission faults and source-map preservation through execution | Complete package/link/refactor diagnostics and source-map invariants | Complete navigation, traceback presentation, lint/format and editor diagnostics from the same catalog | Arnold workflow platform |
| Descriptor, discovery, lock, source correspondence | Existing `arnold/workflow/discovery/`, `arnold/pipeline/native/pack_*`, and `arnold/manifest/` authorities selected by S1 inventory | Extend the canonical descriptor/lock; prove exact package correspondence | Enforce frozen identity/lock at admission/checkpoint | Productize package discovery/default/allowlist and all install-form verification | Expose inspect/explain UX only | Arnold workflow platform |
| Logical identity, provenance, migration log | The same canonical descriptor/lock/manifest authority; no separate registry | Implement workflow/digest keys, legacy mapping, and Megaplan migration records | Enforce pin/compatibility/migration/new-run/quarantine semantics | Productize move/rename/extract/inline/promote transactions and APIs | Present identity/lineage/migration diagnostics; never reinterpret | Arnold workflow platform |
| Converter, preview, semantic refactors | Generic `arnold/workflow/` and `arnold/cli/workflow*.py` surfaces chosen by inventory | Ship legacy converter and minimal ephemeral preview | Supply faithful runtime sandbox/fork hooks | Own converter and atomic supported refactor transactions | Own preview/test command ergonomics and unfamiliar-author workflows over those transactions | Arnold workflow platform |
| CLI and editor integration | `arnold/cli/workflow*.py`; any Megaplan editor adapter is transitional product integration | Make suffix/check/compile/inspect work for the cutover | Expose runtime inspect/test hooks | Expose minimal scriptable core commands needed by extraction | Own generic CLI/editor/navigation/format/lint/topology experience and benchmarks | Arnold workflow platform |
| Megaplan workflow sources and product bindings | `arnold_pipelines/megaplan/workflows/` | Own file split, product migration, golden parity, and outgoing handoff | Consume only as a conformance client | Consume only for core regression; do not redo migration | Consume only for generic DX regression | Megaplan product package |

After S6, generic grammar/tooling/identity/package maintenance belongs to the
Arnold workflow platform. Megaplan owns only its workflow files, product
steps/bindings, and parity evidence. A change that would make either side copy
or fork the other side's canonical surface requires a contract amendment, not
an expedient local implementation.

## 12. Minimum blocking conformance

Native Parity S2F must create:

- conformance index `docs/arnold/pype-authoring-conformance.yaml`;
- validator `scripts/validate_pype_authoring_contract.py`; and
- content-addressed receipt
  `.megaplan/initiatives/megaplan-native-parity-corrective/go-format-receipt.json`
  with schema ID `arnold.megaplan.go_format_receipt.v1`.

The validator consumes the contract/index, exact compiler and diagnostic
versions, descriptor schema, locks, fixture outputs, commit/tree, and checkout/
editable/wheel/sdist/cloud artifacts; it independently recomputes the receipt
verdict. S2F cannot close and S2R cannot start unless the pre-merge gate and
post-merge rebind are green; S2R independently reruns the validator before
consuming compiler output.

The external
`.megaplan/initiatives/megaplan-chain-milestone-gates/chain.yaml` prerequisite
must first add the generic non-shell `conformance_gate`. Native's chain declares
that gate and cannot launch under the old final-only parser. The accepted
GO-FORMAT receipt is evidence, not runtime authority.

At minimum, executable fixtures prove:

1. zero or two workflows in one `.pype` reject;
2. a canonical workflow imports and invokes another canonical workflow;
3. private steps/helpers cannot be imported or independently addressed;
4. the versioned executable-closure canonicalizer includes every required
   closure input, excludes only the closed exclusion list in `PYPE-ID-02`, and
   digest mutations follow canonical-envelope changes rather than a claimed
   behavior classifier;
5. shared steps/effects/schemas/policies resolve from `.py` without executing
   author source; shared step modules use ordinary Python/third-party imports
   while the graph lock/bindings pin every selected implementation, environment,
   feature and plugin and reject import-time effects/mutable Arnold
   registration, ambient selection, and topology/effect bypass;
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
    registries;
18. governed distribution forks use a new name or accepted delegation,
    conflicting authority collides, and legitimate same-key version-digest
    evolution resolves by exact pin rather than collision;
19. `default_pipeline` never supplies a root adapter, while explicit invoking
    selection and accepted named producer defaults bind one total adapter;
20. finite named discriminants branch visibly, while whole-payload, open-string,
    mapping, exception-text, callable, and helper-returned-target routing
    rejects; and
21. registry-derived mode/store mutations reject duplicate severity policy and
    production logical-store/key/namespace access from preview, sandbox,
    comparison, or default certification capabilities;
22. the adopted IR/envelope/graph-lock schemas, RFC 8785 serialization and
    SHA-256 vectors reproduce exactly across implementations, while undefined
    tagged scalars/references and locally substituted algorithms reject; and
23. changing a direct dependency contract changes the caller component digest,
    while selecting a different compatible concrete dependency preserves that
    component digest but changes the graph-lock digest; admission/checkpoint/
    resume fixtures reject either digest when stale or missing;
24. immutable typed policies round-trip through canonical serialization with
    stable kind/schema/scope/provenance/precedence/digest, while ambient
    defaults, callables, open route tables, mutable values and hidden overrides
    reject.

The digest fixture family is authored from the contract's inclusion/exclusion
list, not from the implementation's classifier: it mutates every included
category, every excluded category, unknown syntax/metadata, algorithm version,
and transitive dependency edge. The validator must itself be mutation-tested
to reject omitted included inputs and newly excluded fields.
