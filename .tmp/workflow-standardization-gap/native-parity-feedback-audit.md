# Native Parity feedback audit

Status: read-only audit of the authoritative Native Parity corrective epic  
Date: 2026-07-21  
Scope: Stage 1 only; reusable component-platform standardization remains the dependent Platformization follow-on

## Verdict

The corrective epic already covers most of the feedback's architectural concerns strongly. In particular, it does **not** equate “native” with merely “written in Python”: it makes Python topology the sole route authority, scans transitive phase bodies, deletes or fences handler/component/runtime/CLI/auto route carriers, proves old-carrier mutations inert, and requires future extensions to fail when attempted through hidden metadata or handlers.

The plan is also already strong on human suspension, closed outcomes, declared effects and exactly-once reconciliation, four-domain identity, deterministic child coordinates, in-flight digest drift, and staged no-dual-write migration.

There are six real Stage 1 gaps and two partial gaps worth tightening. They can all be incorporated into the existing S1, S2, S4/S5, and S7 gates. **No new sprint is needed.** They should not be used to pull the Stage 2 component ABI, registry, arbitrary recomposition, or cross-product substitutability work into Native Parity.

## Coverage assessment

| Concern | Current coverage | Assessment |
| --- | --- | --- |
| Python is sole control-flow authority | North Star, canonical machinery boundary, transitive purity scan, S3/S6 carrier deletion, S7 hidden-authority and extension mutations | **Strongly covered** |
| Closed typed outcomes and declared effects | Small primitive set, exhaustive vocabulary, typed decisions, explicit effects, exact RA decision consumption, WBC intent/outcome | **Strongly covered** |
| Effect idempotency/reconciliation | M11 reuse, NP-GT-004, GO-2, crash-position mutations, no dual-write cutover | **Strongly covered** |
| Human suspension/reentry | Named human gates, exact reentry coordinates, NP-GT-003 cross-host resume, stale-input/fence/epoch/digest rejection | **Strongly covered** |
| Identity and dynamic-child stability | Four identity domains; occurrence coordinates; task/batch/item keys; retry/reentry generations | **Strong for Megaplan**, but explicit state/artifact namespace collision proof is missing |
| In-flight code evolution | Program, policy, WBC, and installed-artifact digests; pinned-version or typed migration/new-attempt/quarantine | **Semantically strong**, but executable retention/resolution is not yet operationally proven |
| Deterministic/fenced Python subset | Deterministic identities/calculations and literal/local policy appear, but no comprehensive allowed/forbidden semantics or ambient nondeterminism gate | **Real gap** |
| Compiler diagnostics/debuggability | Source spans appear in final row evidence, but no author-facing diagnostic or source-map contract | **Real gap** |
| Lightweight local testing | Neutral pipeline and many conformance tests exist, but no product-team test harness contract | **Real gap** |
| LLM replay identity and budgets | Call-site model policy and policy digest exist; model config reentry exists | **Materially partial**: prompt/tool identity, durable budget accounting, memoization, and nondeterministic output replay are underspecified |
| Checkpoint payload discipline | M11 payload/version policy is reused; checkpoint coordinates/digests are strong | **Materially partial**: no Native boundary rule for inline payload versus artifact reference or size/retention validation |
| Contract stack/action envelope | RA/Custody/WBC/projection ownership and conjunctive action rule are clear | **Strong runtime rule**, but Plan Contract and generated manifest/component lock need explicit non-authority placement |
| Migration/cutover | GO-0–GO-4, inert dual-read, no dual-write, single authority cut, old-carrier fencing/deletion | **Strongly covered** |

## Exact amendments

### A1 — Define and enforce the deterministic Python authoring subset

**Why this is a real Stage 1 gap:** resumability is not safe merely because child names and ready batches are deterministic. The current plan does not explicitly reject ambient time, random sources, unordered iteration, environment/process reads, network/filesystem I/O, mutable globals, or unmanaged concurrency in topology/control code. That omission invites either replay divergence or a retreat into opaque handlers.

**Smallest amendment:**

- **S1 / authoring contract:** add a versioned deterministic-authoring contract distinguishing:
  - topology/control code, which must be replay-pure and statically lowerable;
  - phase computation, whose nondeterministic or external operations must cross a declared durable call/effect boundary;
  - explicitly injected deterministic values such as logical time, seed, configuration, and ordered collections.
- Freeze an allow/deny matrix at minimum for wall clock, random/UUID, environment and process state, filesystem/network/subprocess access, mutable globals, unordered collection traversal, reflection/dynamic import/eval, unmanaged tasks/threads, and exception-driven product routing.
- Require canonicalization or explicit rejection where ordering is not stable. An escape hatch may exist only as a declared opaque **effect/phase boundary** with typed ports, closed outcomes, policy, and WBC history; it cannot own product control flow.
- **S2 / compiler and runtime:** implement compile-time linting plus runtime guards for cases static analysis cannot prove. Generated lowering must preserve the deterministic semantic path and source location.
- **S7 / gate:** add negative mutations for each forbidden nondeterminism family and a replay-twice test proving identical semantic/decision/checkpoint traces from the same recorded boundary results.

**Assets to amend:** `NORTHSTAR.md` (Done means), canonical plan (Semantic compression/readability, S1, S2, S7, blocking regressions), S1 brief, S2 brief, S7 brief, golden global assertions. No new golden product scenario is necessary; add deterministic mutations to the existing scenario families and neutral reference.

### A2 — Make compiler diagnostics and source mapping a closure condition

**Why:** source spans in conformance evidence help auditors, not authors. A restricted Python surface will be rejected by users if an illegal `break`, hidden route return, ambient I/O, or non-literal policy produces an IR stack trace or vague compilation failure.

**Smallest amendment:**

- **S1:** freeze a diagnostic contract: stable diagnostic code, precise source file/span, offending construct, violated determinism/control rule, and a concrete supported rewrite. Define lowering source maps from generated manifest/IR nodes back to authored call sites and named subworkflows.
- **S2:** ensure compile errors and runtime failures preserve authored source coordinates and semantic paths; generated/control-plane frames may be attached but cannot replace the user-code location.
- **S7:** test representative illegal constructs (including unsupported `break`/`continue`, dynamic policy, hidden handler route, ambient I/O/time/random, and unhandled closed outcome) and assert source-local diagnostics. Test that a runtime phase failure and suspended/replayed failure identify the same authored location.

This need not promise transparent use of every normal Python debugger across distributed replay. The Stage 1 promise should be precise local source diagnostics, stable semantic trace coordinates, and ordinary debugging inside pure phase bodies.

**Assets:** canonical plan S1/S2/S7 and readability contract; S1/S2/S7 briefs. No new sprint.

### A3 — Add a lightweight local authoring/test kit that uses the production lowerer

**Why:** the plan proves the platform extensively but does not state how a Megaplan developer iterates without booting the full durable deployment. This is an adoption and anti-escape-hatch requirement, not Stage 2 platformization.

**Smallest amendment:**

- **S2:** ship an in-process deterministic test harness over the **same production compiler/lowerer and runtime transition semantics**, with in-memory/test implementations of the admitted RA/Custody/WBC interfaces.
- It must support typed phase fakes, recorded LLM/tool results, injected logical time/faults, fast-forwarded human decisions, crash/retry/resume simulation, effect intent/outcome ambiguity, and inspection of normalized golden traces.
- The harness must not introduce an alternative route engine or weaker outcome/effect validation. Every fake is bound to a declared port/outcome/effect and semantic occurrence.
- **S3–S6:** use the harness for fast product-level split-outcome tests, while retaining installed/cross-host/cloud gates for authoritative durability proof.
- **S7:** prove selected local traces normalize equivalently to installed execution given the same recorded boundary results; local success alone never satisfies custody-adoption or release gates.

**Assets:** canonical plan S2 and test strategy/S7; S2 and S7 briefs. No new sprint.

### A4 — Complete the LLM call/replay identity contract

**Why:** `model` and a general call-site-policy digest are not precise enough for suspended/retried LLM work. An LLM result is nondeterministic input to the durable workflow and must be recorded, not silently recomputed during replay. Prompt or tool-schema changes may alter semantic output even when topology is unchanged.

**Smallest amendment:**

- **S2 call-site policy contract:** every LLM/tool boundary declares and binds:
  - prompt/template identity and content digest, including system/developer instructions and referenced prompt assets;
  - model/provider/profile and decoding/tool-choice parameters;
  - tool name plus input/output schema/version and allowed effect classification;
  - token/cost/time/retry budgets and durable consumption counters;
  - cache/memoization policy and key schema;
  - output schema and recorded durable result identity.
- Treat a completed model/tool result as durable boundary evidence reused on replay. A logical retry is a new declared attempt with its own budget consumption and authority/WBC lineage; replay of the workflow history is not a fresh model call.
- Cache hits must be content-addressed by all behavior-relevant inputs and policy identities, schema-validated, journaled as provenance, and unable to grant a route. Cross-run caching is permitted only if explicitly declared; otherwise scope it to the run/semantic occurrence.
- Prompt/model/tool/policy drift at suspension or dispatch follows the existing pinned-original versus typed migration/new-attempt/quarantine rule. Changing any behavior-relevant prompt asset must change the applicable executable/call-policy binding.
- **S7:** add mutations for changed prompt content with unchanged filename, changed tool schema, changed model parameters, exhausted budget, forged cache entry, and crash after durable model result before checkpoint. Prove no duplicate call on replay and no budget reset after retry/resume.

**Assets:** canonical plan identity model/S2/S4/S7, S2 and S4 briefs, S7 brief, golden fixture envelope/global assertions and NP-GT-002/003/006 mutations. No new sprint.

### A5 — Specify checkpoint payload/reference discipline

**Why:** the plan correctly reuses M11 payload/version machinery but does not state which Native values may be embedded in checkpoints. Unbounded model output, plan bodies, review corpora, or artifacts can make durable state expensive and migrations brittle.

**Smallest amendment:**

- **S1 row/trace contract:** classify boundary fields as bounded inline control data versus content-addressed artifact reference.
- **S2 checkpoint contract:** inline only schema-versioned, size-bounded control values needed to decide/reenter (closed outcomes, semantic keys, counters, small typed inputs). Large/unbounded plans, prompts, LLM transcripts/results, task outputs, reviews, and binaries use immutable artifact references containing content digest, media/type/schema version, provenance, and retention/retrievability class.
- The checkpoint envelope records reference identity, never assumes mutable path contents, and validates referenced content before resume. Missing, digest-mismatched, schema-incompatible, or expired required artifacts yield typed repair/migration/quarantine—not silent recomputation.
- Reuse M11's accepted payload/version and artifact facilities; do not build another blob store.
- **S7:** enforce size limits and mutations for oversized inline payload, mutable-path replacement, digest mismatch, missing/expired artifact, and incompatible schema.

**Assets:** canonical plan S1/S2/S7 and row evidence; S1/S2/S7 briefs; golden checkpoint schema/global assertions. No new sprint.

### A6 — Make pinned-version resume operational for long human suspensions

**Why:** the semantic disposition is already correct, but “use the pinned original” is only executable if its wheel, prompt assets, schemas, lock, and compatible runtime are retained and resolvable after a routine v2 deployment.

**Smallest amendment:**

- **S1 admission/inventory:** define retention and resolvability requirements for any executable/program/policy/prompt/tool-schema artifact referenced by a nonterminal run.
- **S4 human-resume gate:** exercise 40-like mixed suspended-run conditions in miniature: create multiple v1 suspensions, deploy v2, then prove each v1 run either resolves the exact pinned v1 artifact and resumes under current RA/Custody/WBC, consumes an accepted typed migration/new-attempt decision, or quarantines with an actionable explanation. It may never silently use v2.
- Define garbage-collection eligibility: a pinned artifact/contract version cannot be removed while referenced by a resumable nonterminal run unless all such runs have an accepted migration/quarantine disposition.
- **S7:** add pin-resolution and premature-GC negative tests across checkout/install/cloud artifact stores.

This is not Stage 2 semantic-version compatibility or substitutability; it is Stage 1 operational support for exact-version resume.

**Assets:** canonical plan sequencing/version inventory, S4 and S7; S1/S4/S7 briefs; NP-GT-003. No new sprint.

### A7 — Add explicit state/artifact/cache namespace collision proof

**Why:** semantic occurrence identity is well specified, but the plan does not explicitly say that every durable state cell, checkpoint, artifact, effect idempotency key, and cache entry derives an isolated namespace from run identity plus semantic occurrence/instance coordinates. This matters when the same delivery subworkflow is entered repeatedly or equivalent children exist in parallel.

**Smallest amendment:**

- **S2:** require all durable keys to derive from declared run identity plus semantic path, invocation/loop generation, item key, retry/reentry coordinates as applicable; no Python object identity, display label, list index, or broad phase name.
- **S5:** add collision tests for two sequential delivery-cycle generations, two same-kind children in fanout, and two concurrent runs with identical product task IDs. Verify state/checkpoints/artifacts/effects/caches cannot cross-read or overwrite.
- **S7:** include namespace equality/isolation in source/lowering/runtime proof.

This is a bounded Native/runtime primitive requirement. Arbitrary component nesting and cross-product instance algebra remain Stage 2.

**Assets:** canonical plan identity model/S2/S5/S7; S2, S5, S7 briefs; golden global assertions and NP-GT-005. No new sprint.

### A8 — Clarify Plan Contract and generated runtime artifacts in the contract stack

**Why:** the runtime ownership equation is already correct, but readers can still confuse Megaplan's `provides`/`assumes` Plan Contract or a generated manifest/component lock with authority.

**Smallest amendment:**

- Add two rows to the plan/North Star contract table:
  - **Megaplan Plan Contract:** declares milestone/product input-output assumptions (`provides`, `assumes`, `pre_existing`); it neither routes nor authorizes execution.
  - **Generated manifest plus executable/component lock:** immutable lowering/install/replay coordinates derived from source; downstream of topology and required for executable admission, but never an independent product route or RA/Custody grant.
- Name the action envelope fields explicitly: semantic occurrence; accepted RA decision/grant/fence; exact Custody target/owner/epoch; WBC attempt/contract/evidence; program/topology, call-policy, installed-artifact and dependency/prompt/tool bindings as applicable.
- Add one negative S1/S7 mutation proving Plan Contract metadata or generated manifest metadata cannot introduce a route or authorize an action.

This is mostly clarity plus one anti-relapse proof, not a new subsystem.

**Assets:** `NORTHSTAR.md`, canonical plan contract ownership/four-domain sections, README, S1 and S7 briefs. No new sprint.

## What should remain Stage 2

Do **not** expand Native Parity to solve these follow-on platform concerns:

- a public, versioned component ABI shared by unrelated product workflows;
- arbitrary step/subworkflow decomposition and recomposition rules;
- generic nesting/propagation semantics across all component packages;
- registry publication, compatibility classes, and dependency-resolution governance;
- cross-implementation behavioral substitutability;
- proving the same extracted pattern in a genuinely unrelated second consumer;
- general package lifecycle and marketplace concerns.

Native Parity should leave behind the evidence needed to extract those abstractions: one correct product implementation, deterministic/runtime primitive contracts, typed boundaries, source maps, exact identities, and a candidate-pattern inventory. The dependent Platformization ticket should then generalize only what survives a second consumer.

## Suggested closure language

The amended Stage 1 end state can be stated compactly as:

> Megaplan's fenced, deterministic Python topology is the sole product control-flow authority. Every nondeterministic interaction—including human, LLM, tool, and external effects—crosses a typed, versioned, durable boundary with closed outcomes, exact identity, bounded checkpoint state, and replay-safe evidence. Authors receive source-local diagnostics and a lightweight test loop; production retains or explicitly migrates every pinned in-flight executable. Hidden handlers, ambient nondeterminism, mutable artifacts, stale versions, and namespace collisions fail closed.

These amendments sharpen the existing seven-sprint plan; they do not change its sequence or require an eighth sprint.
