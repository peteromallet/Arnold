# Unknown-Unknowns from the ADOPTION vantage: node/piece composition ecosystems

Vantage: ComfyUI custom nodes, n8n / Node-RED, Max/MSP & Pure Data, Unreal Blueprints,
Houdini, modular synths. The question is not "is our SDK elegant?" — it's "what do the
node/piece ecosystems that real people actually adopt have that an in-process Python SDK
of composable pieces structurally lacks?"

The frame we are attacking from the outside: Arnold is a **Python, in-process, single-repo
SDK** of composable pieces; **developers** compose **pipelines (DAGs/loops)**; success =
an external builder ships a new module cheaply; the value is **composability**.

Every prior pass took "developers compose pipelines in code" as the unit of adoption. The
ecosystems below say that is almost never where adoption actually comes from.

---

## Grounding (what real adopted ecosystems actually do)

**ComfyUI** — de-facto standard for serious Stable Diffusion. Adoption is NOT driven by
"composability of nodes in code." It is driven by three things that have nothing to do with
the SDK surface:
1. **A visual canvas** that looks like Blender/Nuke/Fusion, so artists who already think in
   node editors feel instantly at home. (datastudios, visionstack reviews)
2. **ComfyUI-Manager**: one-click install of 2,000-3,000+ community nodes. The package
   manager is a *community-built extension*, not core — and it is arguably the single
   biggest adoption driver. Without it, custom nodes are a git-clone-and-pray nightmare.
3. **Workflow-in-a-PNG**: the entire node graph is embedded in the output image's metadata.
   Drag the image back in → the whole graph reappears. Civitai calls it "how did I ever
   live without this." This made workflows *virally shareable as artifacts* — the share
   unit is the OUTPUT, not the code. (civitai, comfyui-wiki)

**n8n** — stickiness is **6,000+ templates** ("90% of a job already done") + **visual
execution history** (click any past run, see exact JSON payload at every node). Multiple
*third-party* template marketplaces emerged (9,869 / 5,000 / 2,348 workflows). "Smart
engineers start with a working template and customize it rather than building from scratch."
The unit of adoption is the **remixable template**, not the node API.

**Node-RED** — 4,000+ nodes, dominant in IoT/shop-floor. Weakness explicitly called out:
"little centralized monitoring or version control out of the box" → enterprise governance
gap. The node ecosystem thrived; the *operability* layer is what limited its ceiling.

**Max/MSP & Pure Data** — powerful, decades old, but **niche**. Stayed niche precisely
because they were *patcher-first with no remix/share/discovery layer and no package manager
that normal people use*. Power users hand-build patches; there is no viral artifact and no
"90% done" template economy. This is the cautionary twin of ComfyUI: same node paradigm,
fraction of the adoption — the difference is the social/sharing/manager layer, not the
expressiveness of the pieces.

**Visual programming critique** — devRant/HN/Dan MacKinlay: node graphs become "literal
spaghetti," reference graphs of non-trivial programs are non-planar and don't lay out on a
plane, patchers force "a million clicks to do every simple thing." The winning pattern is
**high-level nodes you can peek inside and drop to text** — node-at-the-top, code-underneath.
Pure visual-at-the-bottom loses to keyboard/text for real logic.

**Failure mode that dominates ComfyUI support** — **dependency hell**: a custom node pins
`torch==2.4.1`, another wants `>=2.4.2`, a node changes NumPy/OpenCV and silently breaks
every previously-working workflow. "Hidden killer." Frontend updates break nodes; abandoned
authors break workflows. The #1 lived pain in the most-adopted node ecosystem is **NOT
authoring difficulty — it is the combinatorial fragility of someone else's installed pieces
in a shared process.**

---

## The reframe

We are scoping a **code SDK for developers to author pieces**. Every adopted node ecosystem
shows that authoring the pieces is the **1% activity** — the adoption flywheel is the
**consume / remix / share loop around runnable artifacts**, served by a **package/registry
manager** and a **visual or declarative inspection surface**, with **operability and
dependency isolation** as the thing that decides the ceiling. An in-process single-repo
Python SDK is the Max/MSP path (elegant, expressive, niche), not the ComfyUI path
(manager + shareable artifact + canvas + template economy = mass).

The unit of value is not the pipeline-as-DAG. It is the **pipeline-as-shareable-artifact
that produces a visible, replayable run** — and the registry + inspector + isolation that
make a stranger's artifact actually run on your box.

---

## Unknown-unknowns

### U1 — The adoption unit is the *shareable runnable artifact*, not the composable piece. We have no share/remix/registry loop scoped.
ComfyUI's growth came from workflow-in-a-PNG + ComfyUI-Manager; n8n's from 6,000 remixable
templates; Max/MSP stayed niche for *lacking exactly this*. None of these are "the SDK is
expressive." A megaplan plan/run is already a near-perfect shareable artifact (state dir +
events + diff), but we treat it as private internal state, not as a thing you drag into
someone else's environment and re-run. **Why blind:** the frame says "builder ships a
module," so we optimized authoring economics; we never asked "how does a non-author *get*
and *re-run* someone else's pipeline+run in 5 minutes." **If true:** the epic's success
metric ("external builder ships a module cheaply") is measuring the 1% activity; the real
KPI is "time-to-first-re-run of a stranger's shared pipeline+result," and we need a
registry + an export/import artifact format + provenance embedding. **Severity:
would-reshape.**

### U2 — Dependency/version fragility of third-party pieces in one Python process is the ceiling-setting failure mode, and "in-process single-repo SDK" maximizes it.
The #1 lived pain in the most-adopted node ecosystem is not authoring — it's that
strangers' pieces pin conflicting deps and silently break a previously-working graph in a
shared interpreter. Our frame ("in-process, single-repo") is the *exact* architecture that
guarantees this the moment "other people" publish pieces with their own LLM-SDK / tool /
provider deps. **Why blind:** we hardened the *internal* plan (typed Ports, realized graph,
policy spine, trust boundary) which assumes a curated single repo; the trust boundary was
drawn around *behavior*, not around *dependency/process isolation* of foreign pieces.
**If true:** "external builder ships a module" is a dependency-conflict generator; we need
either a manifest/lockfile-per-piece + isolation (subprocess/venv/wheel boundaries) or a
deliberate "blessed registry only" posture — and that decision is architectural, made now,
not later. **Severity: would-redirect.**

### U3 — The winning paradigm is "high-level node you can peek inside and drop to text," and a Python-only SDK is the wrong layer to *start* from for adoption (but right to expose underneath).
Every node ecosystem that scaled gives non-authors a visual/declarative top layer; the ones
that stayed code/patcher-only stayed niche. Yet the *failure* of pure-visual at scale
(spaghetti, non-planar, click-a-million-times) says the answer is layered: declarative/visual
on top, **drop to code underneath**. We have only the bottom layer scoped. **Why blind:**
"builders are developers" was an axiom, so we never modeled the much larger consumer tier
(power users/teams/educators in ComfyUI terms) who never write a node and compose by
remixing a YAML/visual graph. **If true:** Arnold needs a **declarative pipeline format
(YAML/JSON) as a first-class authoring/sharing surface** — not just the Python compose API
— and the Python SDK becomes the "peek inside / escape hatch," inverting which layer is the
product. (Note: a yaml-pipelines-migration doc was just *deleted/archived* in this repo —
worth checking whether we retired the very layer adoption needs.) **Severity:
would-reshape.**

### U4 — Adoption is gated by the run-replay/inspection surface (the "visual execution history"), which our trust-boundary frame treats as introspection, not as the product.
n8n's stickiest feature is being able to click into any past execution and see the exact
payload at every node — debugging multi-branch state is *the* reason it beats Node-RED for
business. ComfyUI's canvas shows the live graph executing. For an LLM-agent harness where
runs are long, expensive, and non-deterministic, the **replayable, inspectable run is the
trust-builder that converts a curious first-timer into an adopter** — far more than piece
composability. **Why blind:** we built observability/introspection as an internal
operability concern (for *us*, debugging the engine), not as the *adopter-facing* surface
that makes a stranger trust and re-run an expensive agent pipeline. **If true:** the
events/state surface must be promoted from "internal telemetry" to "shareable, rendered run
record" — versioned, diffable, embeddable in the shared artifact (cf. U1). **Severity:
worth-knowing.**

---

## One-line takeaway for the epic
Stop optimizing the cheapness of *authoring a piece*. The adoption flywheel of every node
ecosystem that won is **registry + shareable-runnable-artifact + replayable-run-inspector +
dependency isolation**, with a **declarative/visual top layer over a code escape hatch.**
We have built the elegant bottom layer (the Max/MSP path) and scoped none of the four things
that separate ComfyUI from Pure Data.

## Sources
- https://github.com/comfy-org/ComfyUI
- https://www.datastudios.org/post/comfyui-how-the-node-based-system-works-why-creators-use-it-and-how-it-transforms-ai-image-genera
- https://civitai.com/articles/26592/the-workflow-in-a-png-trick-in-comfyui
- https://github.com/Comfy-Org/ComfyUI-Manager/issues/1659
- https://www.apatero.com/blog/custom-nodes-breaking-comfyui-updates-fix-guide-2025
- https://wonderfullauncher.com/docs/dependency-conflicts
- https://n8n.io/vs/node-red/
- https://hostadvice.com/blog/ai/automation/n8n-vs-node-red/
- https://n8n.io/workflows/
- https://devrant.com/rants/2846003/visual-programming-makes-for-literal-spaghetti-code
- https://danmackinlay.name/notebook/patchers.html
- https://www.merchtbpn.com/blog/comfyui-creator-stack-node-based-ai-tools
- https://appmus.com/vs/max-msp-vs-pure-data
