# Adoption Artifact & Virality — Unknown-Unknowns (committed vision)

Vantage: **the unit of adoption & virality**. For Arnold to LAND, what is the
shareable / remixable / replayable artifact, the registry it lives in, and the
inspector that makes it trustworthy? We are 100% building the full vision; this
brief only asks *what bites if we ship the pieces but no share/remix/inspect/
registry layer*.

## What the best systems actually did (grounded)

- **ComfyUI — workflow-in-PNG.** The killer mechanic isn't the node editor; it's
  that *the output IS the artifact*. The generated PNG carries the full workflow
  JSON in its metadata, so dragging the image back onto the canvas rehydrates the
  entire graph. Zero separate "export" step, zero registry friction, and the share
  medium (an image people already post on Civitai/Discord) is the distribution
  channel. The known failure: when a site re-encodes the image (WebP/JPG, resize),
  metadata is stripped and the artifact silently dies. The artifact's virality is
  exactly as durable as its self-containment.
  (civitai.com/articles/26592, comfyui-wiki.com/en/interface/workflow)

- **n8n — 6,000–9,800+ templates + click-into-past-runs.** Two flywheels, not one.
  (1) A template library that cuts setup 70–90%, so newcomers start from a working
  graph instead of a blank canvas. (2) An *execution inspector*: every run is
  replayable — click an execution and n8n re-loads the exact input/output of every
  node, you can copy a past run into the editor and re-run it. The artifact and its
  *evidence of having worked* are the same object. Adoption tracks "I can see it
  ran, and I can fork the proof." (docs.n8n.io/workflows/executions/debug,
  n8n.io/workflows — ~9,869 templates, 230k+ users, 5x YoY)

- **HuggingFace Hub — git+LFS+model cards.** Became the default ML registry by
  standardizing three things at once: content-addressed versioning (commit hash /
  Xet chunking), a *card* (metadata: task, eval results, limitations, training
  curves), and deep library integration (`from_pretrained` pulls by id). The
  artifact is legible, pinnable by hash, and one line of code away from running.
  (huggingface.co/docs/hub)

- **Replit / Glitch — Remix turns dead code into live code.** Fork+run in one
  place. The thesis (Packy McCormick): GitHub holds *dead* code; the remix button
  makes code *alive* — always ready to run and modify. Forking is a first-class,
  one-click social act, not a `git clone` + setup ritual.
  (notboring.co/p/replit-remix-the-internet)

- **Max/MSP — why it stayed niche.** Two artifact-level barriers. (1) You cannot
  edit/save a shared patch without owning a paid license — the artifact is inert to
  the recipient. (2) Practitioners report patches become "incomprehensible" once
  large — the artifact does not stay legible or composable at scale. No
  self-contained, license-free, legible-at-scale unit → no flywheel, despite a
  decade head start on node editors. (docs.cycling74.com, modwiggler forum)

- **Template-marketplace graveyards.** Most marketplace templates fail not on
  content but on *environment contract drift*: the template assumes APIs, env vars,
  regional controls, secrets the recipient's world doesn't have; AI-authored
  changes update code while the env contract is forgotten; the recipient discovers
  the break only at deploy time. Canva-style: ~85% of template sellers fail. A
  registry of artifacts that don't carry their full execution contract is a registry
  of latent "works on my machine" failures.
  (latenode community, arxiv 2604.01072 reproducibility gap, dev.to drift bugs)

## The pattern across winners

Every viral composable platform converged on ONE property: **the artifact is a
self-contained, rehydratable, replayable bundle of {definition + provenance +
evidence-it-ran}, and forking/running it is a single act.** The artifact is the
product, the documentation, the proof, and the distribution channel simultaneously.

Arnold already PRODUCES this object — a megaplan run is `state + events + diff`:
a content-hashed, journaled record of a plan that was executed and verified by a
routed model swarm. **This is a near-perfect ComfyUI-PNG-class artifact, and we
treat it as a private working directory.** That is the central blind spot.

## Unknown-unknowns

### UU-1 — We have the perfect viral artifact and have privatized it
The megaplan run (`state.json` + event journal + diff) is the strongest shareable
unit in the whole vision: it's content-hashed, it carries provenance and the
verify trail, and it *replays* — it is ComfyUI-PNG + n8n-execution-replay + HF-card
fused into one object that the harness already emits. But it lives in a per-user
plan dir keyed by local paths, treated as scratch. **Why invisible to us:** we
built it as an *engine substrate* (resume/recovery state), so we see it as
machinery, not as the thing humans and agents will trade. We optimized it for the
running process, not for a stranger receiving it. **What it threatens:** the entire
adoption flywheel. If the unit of adoption is never named and made first-class
(stable id, hash-pinned, importable, renderable by someone who wasn't there), we
ship the engine of a category-creating platform with no object to share — Arnold
becomes a powerful Max/MSP: brilliant, license-gated-feeling, niche.
**Severity: reshapes-architecture.**

### UU-2 — Rehydration requires carrying the world, not the graph (the contract-drift trap)
ComfyUI's PNG dies on re-encode; marketplace templates die on env drift. A shared
Arnold artifact is *far* more environment-coupled than a node graph: it references
a repo at a commit, models/versions, secrets, taint context, a Port topology, prior
journaled state. A recipient who drags it in gets a beautiful replay of *our* world
and a hard failure in *theirs* — and worse, a **convincing-but-wrong** partial run,
because the harness will gamely route around the missing pieces (the memory note on
silent OpenRouter routing and TIEBREAKER→ITERATE downgrades shows the system's
instinct is to degrade quietly). **Why invisible to us:** we always run artifacts in
the environment that produced them, so the contract gap never fires for us; we never
experience the recipient's broken rehydration. **What it threatens:** trust on first
contact — the single most fragile moment in any flywheel. A registry full of
artifacts that *look* runnable but silently produce different results poisons the
well faster than having no registry. This forces the Port spine
(type+version+provenance+taint) to extend from a *runtime invariant* into a
*portable, declared, recipient-verifiable contract* — a much larger thing than an
internal type system. **Severity: could-sink-the-build.**

### UU-3 — Forking an AI-authored run has no provenance graph, so remix can't accrete trust
HF/Replit virality compounds because derivatives *point back*: a fine-tune cites its
base model, a remix links its parent, and reputation flows up the lineage. Arnold's
artifacts will be overwhelmingly **AI-authored and AI-remixed** (models emit
pipelines). If a forked run doesn't carry an immutable lineage edge (this plan was
derived from that plan, by this model/profile, mutating these Ports), then at scale
we get a flat soup of near-duplicate machine-generated artifacts with no way to ask
"which lineage actually verifies / is cheapest / is trusted?" The content-hashed
foundation gives us *integrity* (this artifact is unchanged) but not *genealogy*
(how this artifact relates to others). **Why invisible to us:** today a human runs
one plan at a time and lineage lives in their head; the combinatorial fork-explosion
of agents remixing each other's runs hasn't happened yet, so the missing edge costs
nothing *now*. **What it threatens:** discoverability and the quality signal of the
registry under AI-scale authorship — the registry becomes un-rankable, and the
self-improving harness loses the cross-run signal it would most want to learn from.
**Severity: reshapes-architecture.**

### UU-4 — No inspector for a non-technical or asynchronous recipient = no spread beyond the author
n8n's growth lever is that a stranger can *click into a past run* and understand it
without re-running it. Arnold's run is replayable by the engine but only legible to
someone who can read `state.json` + an event stream — i.e. its own author or a
developer. The flywheel needs the artifact to be *inspectable as a story*: what was
asked, what the plan decided, where it forked, what it verified, what it cost, where
a human gated it. **Why invisible to us:** the author always has the surrounding
context in their head and the CLI to introspect (megaplan-observe/diagnose exist),
so we never feel the cold-open legibility gap a recipient feels. **What it
threatens:** the share→understand→remix loop. An artifact that only its author can
read is a diary, not a template; it can be sent but not *spread*.
**Severity: worth-designing-for.**

## The single biggest UNNAMED ABSTRACTION this vantage reveals

**The Replayable Capsule** — a first-class, content-addressed, *portable* unit of
exchange that bundles, as one citable object with a stable id:

1. **Definition** — the pipeline/plan topology (the Port graph: type+version+
   provenance+taint), the *intent* (what was asked), and the routing decisions.
2. **Contract** — the declared world it needs: repo@commit, model/tool versions,
   required secrets-by-shape (not value), Port input types. The recipient's runtime
   can *check this against their world before running* and refuse-or-adapt loudly,
   never silently. This is the Port spine promoted from internal invariant to
   exported, verifiable manifest — the answer to UU-2.
3. **Provenance / Lineage** — immutable parent edges (derived-from, authored-by-
   model/profile, mutated-these-Ports), so remix accretes a genealogy, not a soup
   (UU-3).
4. **Evidence** — the journaled events + diff + verify trail + cost: the proof it
   ran and what it produced, renderable as a *story* for a cold recipient (UU-4).

We already emit ~80% of the bytes (state + events + diff). What we have NOT named is
the *capsule as the platform's unit of identity, exchange, and trust* — the thing
that has an id, gets pushed to a registry, gets forked with a back-edge, gets a
contract-check on import, and gets rendered for a stranger. ComfyUI named it
(workflow-in-PNG); HF named it (repo+card); n8n named it (replayable execution).
Arnold has built the substance and skipped the naming. The Capsule is the spine of
adoption the way Port is the spine of safe composition — and it is the same
object Port should be exported *inside of*.

The registry and inspector then fall out as: a **Capsule registry** (push/pull/
fork-with-lineage, ranked by verified-evidence + cost + lineage-trust) and a
**Capsule inspector** (the cold-open story renderer). Without naming the Capsule
first, registry and inspector have no unit to operate on, and we ship a category-
creating engine with nothing the world can pass hand to hand.
