# Unknown-unknowns from the NEGATIVE SPACE vantage: the builder's full lifecycle

**Vantage:** Stand where the builder stands *after* `pipelines new` succeeds and `arnold run` returns —
i.e. everything the SDK frame never modeled: TEST, DEBUG-a-live-composition, VERSION, PUBLISH/DISTRIBUTE,
DEPEND-on-another-module, SECRETS, UPGRADE-when-the-SDK-moves, SUPPORT. The epic models exactly three
builder verbs — `new` (scaffold), `check` (static contract), `doctor` (discovery health) — plus a
generated `docs/arnold/` and an `arnold_api_version` field that discovery can *refuse*. Everything past
that is unmodeled. This brief attacks the frame from outside it; it does NOT re-audit Ports, the realized
graph, the policy spine, or the trust boundary (inside-the-frame, already hardened).

## What the codebase confirms about the frame's edge

- **Distribution is filesystem-path-only.** `registry.py:10-31` discovers modules by scanning three
  *paths*: `megaplan/pipelines/<name>.py` (in-tree sibling), the package form, and
  `~/.megaplan/pipelines/<name>.py` (user-installed = "drop a `.py` into a magic dir"). There is no
  PyPI/entry-point/plugin-metadata path. A module is "shipped" by *copying a file*.
- **`arnold_api_version` is a gate, not a migration.** `builder-docs.md:103` — "discovery refuses an
  incompatible" version. Refusal is the entire upgrade story: when the SDK bumps, the builder's module
  stops being discovered. There is no codemod, no `arnold upgrade`, no deprecation shim, no N-1 support
  window in the epic.
- **Replay exists, but only as an internal CI oracle.** `EPIC.md:181` — "replay oracle (recorded real-run
  traces vs each PR)". This is the SDK's *own* regression guard. It is never exposed as a builder
  debugging tool. The builder cannot replay *their* run.
- **No inter-module dependency vocabulary.** Grep of `builder-docs.md` + `EPIC.md` for
  requires/depends_on/needs returns nothing. The manifest declares `name/driver/entrypoint/capabilities/
  SKILL.md/arnold_api_version/trust tier` — but never "this module consumes the output of *that* module"
  or "this module needs node-library ≥ X." Ports are typed *within* a pipeline; there is no typed seam
  *between* modules.
- **No secrets vocabulary in the builder surface.** The package contract has no `secrets`/`credentials`
  field; secrets are assumed to be ambient env in the runtime (megaplan's today), invisible to `check`.

---

## UU-1 — There is no DEBUG/INSPECT loop for a live composition, and that — not authoring friction — is what gets modules abandoned

**Insight.** The epic optimizes the *first ten minutes* (scaffold green by construction, `check` exits 0,
`doctor` shows ✓) and the *last mile* (CI replay oracle, substrate-swap oracles). It models nothing about
the **middle**: the builder's module ran, the artifact is wrong, and they need to answer "which node
produced the bad Port value, and why?" Today that answer lives in megaplan's `.megaplan/` state dir +
event trace — an *internal* forensic surface (megaplan-observe/diagnose are SDK-author tools). A builder
has no `arnold run --step`, no Port-value inspector, no "replay this failed run with one node swapped,"
no breakpoint. The realized-graph and typed Ports the epic built are *exactly* the substrate a great
debugger would stand on — and the epic ships them as internal invariants, not as a builder-facing inspect
surface. The asymmetry is stark: replay was built (for CI) and then *withheld* from the person who needs
it most.

**Why our process was blind to it.** Every prior pass framed the builder as "author + check + run," and
debugging looks like a *runtime* concern, not a *composition* concern — so it fell between the SDK
(which owns runtime) and the docs (which own authoring). And because the SDK author *is* megaplan's
author, the team already has megaplan-observe/diagnose muscle memory; they cannot feel the absence of a
debugger they personally never lack. The frame's success metric ("an external builder ships a new module
cheaply") measures shipping, not the 5th iteration of a module that misbehaves only on real inputs.

**If true.** Composability without observability is a write-only SDK. The first time a builder's
non-trivial composition misbehaves on real data and they're reduced to `print`-debugging through an opaque
DAG, they conclude "this is a framework I can't see into" and abandon it. This would **reshape** M5d/M7:
a builder-facing inspect/replay surface (`arnold run --trace`, Port-value dump, single-step, replay-with-
override) becomes a *first-class deliverable*, promoted out of CI-oracle-only status — arguably the
highest-leverage thing the typed graph enables and the cheapest to expose since the substrate exists.

**Severity: would-reshape.**

---

## UU-2 — "Distribution = copy a .py into a magic dir" silently makes every module a private fork; there is no way for module B to depend on module A

**Insight.** The value proposition is composability — yet two builders cannot compose *across module
boundaries*. Discovery is path-scan (`registry.py:10-31`); the manifest has no dependency edges. So if
Alice builds a `web-research` module and Bob wants his `report` module to consume its output, Bob's only
moves are: vendor a copy of Alice's file, or hand-wire ambient assumptions about a `~/.megaplan/pipelines/`
neighbor that may or may not be present at the pinned version. There is no `requires: web-research@^1`, no
version solving, no "missing dependency" diagnostic in `check`/`doctor`. This is the difference between an
SDK (an ecosystem of interoperating units) and a *snippet library* (you copy a starting point and own the
fork forever). The epic's own keystone example — "planning reads as `clarify → produce → critique_loop →
execute → verify → review`" — is composition *of nodes within one module*; it is silent on composition
*of modules*, which is the thing that would make a marketplace.

**Why our process was blind to it.** The frame says modules are composed by "other people" (plural) but
implicitly imagines each person building a *self-contained* module — the unit is "a pipeline," never "a
pipeline that imports another team's pipeline." Because the whole repo is single-repo today, intra-repo
Python import *feels* like the dependency story, so the cross-org, cross-version case never surfaced. The
hardening effort on the *internal* Port (typed data seams between nodes) created a false sense that the
data-seam problem was solved — when the *missing* seam is between independently-versioned, independently-
distributed modules.

**If true.** The composability claim is structurally unfalsifiable in the current frame: you can't observe
network effects when there's no network. Modules are built once, for one repo, by one author, and never
recombined — which is *exactly* the "built once and abandoned" failure mode in the prompt. This would
**redirect** the epic's notion of "module": the manifest needs a typed *inter-module* dependency +
capability-requirement vocabulary and discovery needs a resolution step, OR the team must consciously
descope to "internal building blocks for one org" and stop calling it an external builder SDK. That is a
strategy fork, not a feature.

**Severity: would-redirect.**

---

## UU-3 — There is no upgrade lifecycle: "refuse on version mismatch" pushes the entire cost of SDK evolution onto a builder who has no codemod, no shim, no support channel

**Insight.** `arnold_api_version` makes the SDK's evolution the *builder's* emergency. When Arnold bumps
its API, the builder's module silently stops being discovered (refusal at `builder-docs.md:103`;
discovery already "swallows import errors," `registry.py:337-339` — so it doesn't even fail *loudly*).
The epic provides no `arnold upgrade` codemod, no compatibility window, no changelog-to-migration map, no
deprecation period, no support surface (issue tracker? versioned docs? the generated `docs/arnold/` is
*HEAD-only* — a builder pinned to api_version 2 has no docs for their version). For a *single-repo SDK
the team controls*, evolution = "we refactor and re-run the in-tree packs." For an *external builder*,
every SDK release is a potential silent break with no remediation and no one to ask. The epic's most
aggressive milestone (M5c, "evict STATE_*, the hardest") is precisely the kind of breaking change that,
post-launch, would orphan every external module — and there's no mechanism to carry them across.

**Why our process was blind to it.** Versioning got modeled as a *static type check* (does this manifest's
api_version match?) rather than a *temporal process* (how does a module survive across versions of the
SDK over months?). The team experiences upgrades as "edit the callers in the same PR" — a luxury that
vanishes the moment callers live in repos you don't control. The "no SDK author in the loop" acceptance
criterion (M7) tests *initial* authoring in isolation but never tests *surviving an SDK bump* in
isolation, so the upgrade gap is invisible to the very test designed to prove builder-autonomy.

**If true.** Modules built against v1 rot the moment v2 ships; the builder learns that authoring is cheap
but *maintenance is unbounded and unsupported*, which is a stronger abandonment signal than authoring
friction. This would **reshape** the release process and M7: versioned docs, an `arnold upgrade`/codemod
posture, a loud-not-silent compat failure, and an N-1 support window become launch prerequisites — and it
constrains how violently M5c/M6 can break the surface once anything external is pinned to it.

**Severity: would-reshape.**

---

## UU-4 (worth-knowing) — `check`/`doctor` validate *structure*, never *behavior*; the builder has no `arnold test` and no fixture/golden vocabulary, so they cannot pin "my module still does the right thing"

**Insight.** The builder's only correctness tools are a static contract check and a discovery-health check.
There is no `arnold test`, no fixture format, no golden-output/snapshot vocabulary, no way to assert
"given input X this module produces artifact Y." The SDK protects *itself* with replay + substrate-swap
oracles (`EPIC.md:181-182`) but hands the builder zero analogous machinery. A builder who wants a
regression test must hand-roll one against an unstable internal state-dir layout — so they don't, and their
module silently drifts as the SDK and the underlying LLMs change beneath it.

**Why blind.** "Testing a module" was conflated with "the SDK's own characterization tests." Behavioral
testing of LLM-driven pipelines is genuinely hard (nondeterminism), so the frame quietly routed around it.

**If true.** Modules are unverifiable by their authors and therefore untrustworthy to *recombine* (compounds
UU-2). A builder-facing `arnold test` with a record-once/replay fixture format (reusing the very replay
substrate from UU-1) would close this. **Worth-knowing**, escalating toward would-reshape if the team wants
a module *marketplace* (you won't install a stranger's module you can't test).

---

## The single biggest REFRAME

**We scoped a BUILD tool; the thing that determines adoption is an OPERATE-AND-EVOLVE platform.**

The frame's center of gravity is the *moment of authoring*: scaffold, check, run, generated reference docs,
"ship a new module cheaply." But for every comparable system that achieved composability network effects
(npm, Terraform providers, dbt packages, Airflow/Dagster, LangChain's component ecosystem, Home Assistant
integrations), adoption was never gated on *authoring* cheapness — it was gated on the **post-author
lifecycle**: can I debug it when it breaks, version it, depend on someone else's, test that it still works,
and upgrade across releases without an SDK author holding my hand? The epic built the perfect *substrate*
for that lifecycle (typed Ports, a realized graph, a replay oracle, a versioned manifest) and then exposed
**only the authoring slice** of it, keeping the inspect/replay/upgrade/dependency machinery internal.

The reframe: **the builder lifecycle is `author → test → debug → version → depend → distribute → upgrade →
support`, and the epic models only `author` plus a static checkpoint.** The single missing capability whose
absence most directly causes "built once and abandoned" is the **debug/inspect-a-live-composition loop**
(UU-1) — because it's the first wall a builder hits on iteration 2, it's the cheapest to ship (the typed
graph + replay substrate already exist), and its absence converts "composable SDK" into "write-only snippet
library." The dependency/distribution gap (UU-2) is the bigger *strategic* fork, but debugging is the
nearer cliff. Both share one substrate decision: **promote the internal replay/trace/inspect machinery from
CI-oracle to builder-facing surface.** That single move pays down UU-1, UU-3, and UU-4 at once and is the
highest-leverage thing this vantage reveals.
