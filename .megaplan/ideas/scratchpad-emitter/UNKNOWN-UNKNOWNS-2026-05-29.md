# Unknown-unknowns exploration (2026-05-29) — 10 "Lord" agents, orthogonal lenses

Phases B/C were adversarial ("find flaws IN the plan"). This phase was exploratory ("what is OUTSIDE the
plan's frame entirely?"). Ten agents, each a worldview the plan didn't have a slot for. Five were
code-grounded (Claude agents), five outward/web-grounded. The findings are bigger than the adversarial
rounds because they question the frame, not the details. Ranked across all ten by trajectory impact.

---

## TIER 1 — these change the architecture or the scope of the whole epic

### U-U #1 (D1+D2 converge): ComfyUI ALREADY HAS the identity standard we're reinventing — and our flat uid is born obsolete against native subgraphs.
Two independent agents (prior-art + moving-target) hit the same wall. ComfyUI's official frontend defines
THREE id types (docs.comfy.org/custom-nodes/js/subgraphs): `node.id` (unique only within its graph level),
an execution id (`"54:12"`), and a **locator id `"<graphUuid>:<localId>"`**. Native subgraphs shipped
Aug 2025 (frontend ≥1.24.3); interior node ids are **no longer globally unique** (frontend #8137, Jan 2026,
deferred to "subgraph-v2"). Our planned uid is a flat monotonic scalar → it **collides across subgraph
instances** and silently mismatches positions the moment a user wraps part of their graph in a native
subgraph (the feature ComfyUI promotes hardest). **Decision forced:** identity must be a SCOPED PATH
`(graph_uuid_path, local_id)`, subgraph-aware from day one — not a scalar. Our extrinsic uid becomes a
*stabilizer* against ComfyUI's id-reassignment, keyed path-wise. This reshapes M2's core data model.

### U-U #2 (D2): the frontend VALIDATES `properties` with a zod schema — it doesn't just preserve them.
The keystone assumption (K1: "unknown properties survive editor saves for free") is only HALF true.
litegraph round-trips arbitrary property *values*, but the Vue frontend runs zod that **rejects** bad
shapes on known keys: real users hit `Invalid format ... aux_id` (ComfyUI #13985) and `ver` semver-regex
failures (#7309, regex added in frontend PR #2751) — an un-dismissable wall that re-fires every reload
(#7776). Corpus is saturated: `ver`×1590, `cnr_id`×1526, `aux_id`×550. So a structure-side edit that writes
a malformed `ver`/`aux_id` on a synthesized/class-swapped node corrupts a schema-governed property and the
editor refuses to open — a round-trip break with nothing to do with layout. **Also:** we are emitting
`version: 0.4` (`ui_emitter.py:91`) but the spec is now **1.0**; we ship a back-version envelope on day one.
**Decisions forced:** (a) namespace ALL our keys under a single `properties["vibecomfy"]` sub-object (one
key to defend against a future `.strict()`, instead of N top-level keys that a stricter schema would drop —
this would be IDENTITY DEATH); (b) emit version matching the ingested source version; (c) preserve
`cnr_id`/`aux_id`/`ver` verbatim AND valid, or editor-open fails zod; (d) add a **conformance gate** that
validates emitted JSON against the live frontend zod schema — the independent oracle the plan still lacks.

### U-U #3 (D3): the round-trip is defined over the WRONG CONTAINER. Workflows travel as PNGs, not .json.
ComfyUI's default SaveImage writes the full UI graph into an uncompressed PNG `tEXt` "workflow" chunk
(`nodes.py:1658-1669`); the community's default share verb is **drag the image onto the canvas**, not
File>Open. Civitai/OpenArt/Reddit culture distributes via images. So the plan optimizes the artifact its
*primary user shares least*. The kicker: **PNG read/write is ~60 lines and nearly free given our model** —
the "workflow" chunk IS our self-describing artifact, just in a PNG wrapper (`PIL.Image.open(p).text["workflow"]`
in; `PngInfo().add_text(...)` out, mirroring ComfyUI's own code). Refusing PNG isn't saving complexity;
it's declining a ~2-3× reach expansion. Two more: (a) Civitai/OpenArt re-encode to WebP and frequently
**strip** the workflow chunk → our "self-describing artifact" is silently false on the social channel
(consider also emitting the A1111 `parameters` string so provenance survives); (b) drag-drop vs File>Open
are different load paths the parity gate never tests. **Decision forced:** PNG/WebP becomes a first-class
ingest+emit container, and PNG **ingest belongs near M2**, not deferred — the primary user's inbound artifact
is a PNG, so .json-only ingest starts one painful manual step downstream of where they live.

### U-U #4 (D4): adoption flows through ENGINEERS as intermediaries — the plan designs for the wrong user's trust model, and "you must touch Python" is disqualifying for the primary user.
The editor-first artist will **never** run `vibecomfy port export`. The tool's entire surface is `.py` + CLI;
the community cliché is "I'm an artist, not a programmer." So the artist only meets VibeComfy when an engineer
hands them a `.json`. Their trust question isn't "does it preserve positions?" but **"can I trust files that
passed through VibeComfy?"** — brand trust, not feature trust. Evidence: the successful ComfyUI tools
(Manager, IPAdapter, pydn ComfyUI-to-Python-Extension @1.2k★) are all **in-editor custom nodes**, not external
CLIs. **Scope expansion forced if we mean "definitive bridge":** a ComfyUI custom-node/plugin front-end so
the artist round-trips *inside the editor* and never sees Python; the Python bridge becomes infrastructure
engineers + agents use. Plus brand the output (`extra.vibecomfy` provenance: "round-tripped by vX, N/N
positions preserved") so a file is recognizable-and-accountable to the user who never ran the tool.

---

## TIER 2 — these are make-or-break for trust/correctness but fit within the architecture

### U-U #5 (D4): the trust asymmetry — 99% preservation is a FAILURE, not a success.
One scrambled layout = 100% trust destruction, permanently, with community broadcast ("it ate my workflow"
is reputation-death on Reddit/Discord/Banodoco, no recovery). The plan's "named in the change report" is
post-hoc console text; the artist reacts to what they SEE in the editor. **Forced:** a **dry-run / preview
BEFORE writing** (visual diff, positions green/red), **auto-backup** before any destructive emit, **never
overwrite the input file**, and make the Phase-C "refuse on un-round-trippable nodes" the DEFAULT (with
`--force`), not silent degradation. The widget-count crash (30% of corpus) must die in M1.5 — a crash on
first run is trust-suicide.

### U-U #6 (D6): the round-trip turns VibeComfy into an UNTRUSTED-INPUT COMPILER that exec()s adversary code.
Workflows are executable content from strangers (Civitai/Discord). The parity gate, strict-ready, and
scratchpad loading ALL `exec_module` the generated Python (`convert.py:333,466,489`, `scratchpad_loader.py:24`).
`ast.parse` only catches syntax errors, not malicious-but-valid code; the safety model is implicit trust in
`repr()` across 4,300 lines of codegen. ComfyUI users are actively targeted (LLMVISION stealer June 2024,
Upscaler_4K/Akira 2025, 1000+ exploited instances per Censys). Specific surfaces: code-injection via crafted
class_type/title/widget strings; **path-traversal via `filename_prefix`/`--out`/`prior_path`** (`../../.ssh/...`
survives the round-trip); the object_info gate creates a NEW reason to install untrusted packs ("I just need
the schema"), which runs their `__init__`. **Forced posture:** treat `exec_module` on generated code as a
security boundary — run validation in a sandboxed subprocess (no net, temp-only writes), fuzz the codegen
emit→parse→import chain, sanitize/size-limit the properties passthrough, never auto-install packs for schema.

### U-U #7 (D5): silent degradation is invisible BY DEFINITION — there is no forensics, and the one signal we compute is thrown away.
`recovery_report` already exists in `emit_ui_json` but is **never wired to the CLI, never persisted, never
printed** (`_cmd_port_export` only handles `--to json`). The emitted artifact records what it did, never what
it couldn't preserve; the breadcrumb stamps a layout_version but not the VibeComfy version, the object_info
schema hash, or per-node disposition. So when a file comes back subtly wrong, **neither user nor maintainer
can trace what happened, when, against which schema** — and the maintainer can never learn that, say, 4% of
real round-trips degrade on some pack. **Forced:** bake `extra.vibecomfy.provenance` (version + schema hash +
per-uid disposition: preserved/auto-placed/degraded/refused) into the artifact, persist a full
`out/roundtrips/<id>/report.json` (the round-trip's missing `metadata.json`), opt-in privacy-respecting
field telemetry. This one record is also the regression oracle and the trust receipt.

### U-U #8 (D9): the independent oracle is ALREADY PARTLY THEATER and has no refresh machinery.
The killer: **no CI job ever compares the object_info snapshot to a real ComfyUI.** The one that could
(`schema_freshness.yml`) is manual-dispatch, non-failing, and diffs the cache against itself.
60% of pinned classes (all of core: 838/1385) have **null provenance** — un-diffable. Custom packs are
extracted by **static AST parsing**, not a live ComfyUI, so dynamic `INPUT_TYPES` are guessed. 5 packs are
hand-fabricated `@stub.json` with zero provenance. The "RunPod gate of record" is a $2/night smoke on ~2
image families with no owner and email-to-nobody alerts. **So "independent verification" currently resolves
to VibeComfy validating against VibeComfy** — when ComfyUI core reorders one widget (weekly), the snapshot is
wrong, the emitter faithfully produces corrupt .json, parity stays green (shared stale schema), the nightly
doesn't touch that class. The gate dies not as a red build but a **permanently green one that stopped meaning
anything**. Estimated half-life: >10% of high-velocity pack classes stale within ~6-8 weeks. **Forced:** a
scheduled CI job that pulls object_info LIVE from a pinned-version ComfyUI and FAILS on a per-pack schema-hash
diff; real provenance for core; a coverage ratchet that fails when a corpus workflow uses an uncovered class;
a named owner.

---

## TIER 3 — real, lands within scope, mostly "build the machinery the single-shot plan omitted"

### U-U #9 (D7): we test N=1; users run N=50 over a year — and the convergence guarantee has NO longitudinal test.
"Preserve is exact by construction" is proven for ONE hop; there is no emit→re-emit×N drift test, the
canonicalization precision is still an unpinned open question, and the layout store has **no GC, no
versioning-on-read, no migration** — it only grows (tombstone uids forever). If canonicalization isn't
bit-stable, every re-emit reports "N positions changed" → the change-report cries wolf → users stop trusting
the report (M6's headline trust feature) and real losses hide in the noise. Plus: the 64 shipped templates
have NO positions, so the project's own corpus **can never dogfood the preserve feature**, and every M4 tweak
churns 64 golden snapshots. **Forced:** pin precision; add an emit→re-emit×N property test with an edit each
cycle; give the store a version field + GC + a `port store rebuild`/`port migrate` command; stamp
VibeComfy+schema+pack versions in the breadcrumb so a break a year out is self-diagnosing/bisectable.

### U-U #10 (D8): the ONE place the epic breaches its own execution/layout firewall is bypass — and it silently invalidates the parity gate + every snapshot.
Good news, verified: uid + furniture are **already compile-invisible** (`compile`/`_compile_node_inputs` read
only widgets/inputs, never metadata; `canonical_form` hashes only class_type+literals+topology) — so they're
safe-by-construction IF kept in a sidecar (NOT a per-node field that `dataclasses.asdict` could vacuum into
snapshots/contracts). The exception: making `compile()` honor bypass/mute **must** change the executed graph,
which shifts every snapshot with a bypassed node, the RunPod matrix, and the strict golden lane — and the
offline gate can't see it (normalizer ignores mode). Also flagged: THREE overlapping identity concepts now
live on `properties` (`ir_node_id`, `vibecomfy_id`, `vibecomfy_uid`) — unify or get position-theft.
**Forced:** write a tested compile-invariance contract ("compile/canonical/asdict are byte-identical with and
without uid/furniture"); land bypass-compile with a full snapshot re-baseline + real-ComfyUI bypass-equivalence
check in the SAME PR; unify the identity keys; furniture is a sidecar, never an asdict-reachable field.

### U-U #11 (D10): "green tests, wrong product" — we have NO definition of working for real users, and the corpus is biased.
"Faithful" is unfalsifiable with no human/visual oracle — a round-trip that shifts every node 8px passes every
gate while the artist says "that's not my graph." The 54-corpus is **video-heavy; the primary user is
image-first** → we'd report "92% pass" on the wrong population. No N-th-round-trip metric, no wild-corpus test,
no leading indicators (round-trip survival rate, coordinate-drift histogram, re-open-without-edit rate).
**Forced:** a headless-litegraph **visual-diff oracle** (render both, perceptual-diff the canvas — the only
test that measures the sacred axis); a **"wild corpus" beta** against thousands of scraped Civitai/community
workflows reporting % survival by failure class; per-persona operational success definitions that are NOT
"tests pass."

---

## Cross-cutting realization (the meta unknown-unknown)
The plan optimizes for being CORRECT but has almost no machinery for KNOWING it's correct in the world, and
it is scoped to the wrong container (.json not PNG), the wrong primary surface (CLI not in-editor), and a
flat identity model ComfyUI itself has already outgrown (native subgraphs). The adversarial rounds hardened
the engine; this round says the engine is aimed slightly wrong and has no instruments. Three convergences
recur across independent agents and are therefore high-confidence: (1) **subgraph-scoped identity** (D1+D2),
(2) **the artifact/surface is wrong — PNG + in-editor** (D3+D4), (3) **the verification + observability story
is self-referential and unmeasured** (D5+D9+D10).

## What this ADDS to the ambition (not subtracts — the maintainer said expand)
- Identity becomes subgraph-scoped + interoperates with ComfyUI's own locator-id scheme (future-proof).
- The container expands to PNG/WebP — VibeComfy joins the image-sharing economy; outputs become re-importable.
- A thin in-editor custom node makes the bridge reachable by its actual primary user.
- Provenance-stamped artifacts + a persisted report + visual-diff oracle + wild-corpus beta = a tool that is
  not just correct but *demonstrably, auditably, durably* correct — and recognizably branded as safe.
- A conformance gate (live zod) + a live-pull object_info refresh = an oracle that stays real as ComfyUI moves.
- Security-by-design (sandboxed exec, fuzzed codegen) = safe to point at the untrusted ecosystem it serves.

## Honest note on method
The 5 web agents ran twice (a DeepSeek fan died mid-run — "model not supported" — after banking D4+D6; the
rest were re-run as Claude agents). All ten findings are cited to real URLs / corpus paths / file:line. The
biggest single finding — native-subgraph identity collision — is the one I'd verify first against the live
ComfyUI frontend before committing the M2 identity data model, because it reshapes the foundation.
