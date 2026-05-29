# Unknown-Unknowns from the Ecosystem-Dynamics vantage

Vantage: I am not auditing Arnold's internals. I am standing in the graveyard and the
winners' circle of plugin/extension ecosystems (VSCode, npm, Home Assistant/HACS,
Obsidian, Figma, Kubernetes operators, WordPress, Raycast, MCP, the agent-framework
graveyard) asking one question: **does "other people build modules" ever actually
happen, and what determines it?** Our plan ships a contract-checker + SKILL.md and
calls that the ecosystem story. It is not. The contract-checker is the *quality gate*;
it answers "is this module correct?" Ecosystems live or die on a different axis
entirely: distribution, discovery, trust, the 10-minute first build, and — most
dangerously for us — *whether the unit of value is even a "module" at all.*

---

## What actually made ecosystems live or die (grounded)

**VSCode beat Atom** not on language but on a marketplace with search, ratings, reviews,
download counts, and a performance model (Extension Host) that meant a bad third-party
extension couldn't tank the host. Atom's marketplace had poor search and no review
system; finding a working extension was a slog. Discovery + quality signals + host
isolation, not raw extensibility.
(dev.to VSCode-vs-Atom; crazyegg; shiftmag)

**HACS (Home Assistant)** won because it was a *one-click install/update layer over
GitHub repos* — the author submits a repo, the user searches and installs in a few
clicks, updates push automatically. Critically: many HACS integrations exist precisely
because the authors *couldn't or wouldn't meet core's requirements* (web scraping,
no time to satisfy the contract). The ecosystem thrived on the stuff core's gate would
have *rejected*. (home-assistant.io HACS 2.0; xda; cloudapp.dev)

**Obsidian beat Roam** on openness + no lock-in (plain markdown files, unified plugin
API, open-source plugins) vs Roam's closed, paywalled, no-API stance. Roam Depot grew
slowly; Obsidian has thousands of plugins and ~5M visits/mo vs Roam declining to ~1M.
BUT the same sources note: *most Obsidian plugins don't extend the editor — they just
add a command or an isolated panel.* The deep composability almost nobody uses.
(productivitystack; aloa.co; deepwiki obsidian)

**npm / open source reality:** ~two-thirds of popular GitHub projects have 1-2
maintainers; <3% have >50 contributors; 16M npm releases have a single maintainer;
60% of maintainers are unpaid, 60% have considered quitting. The "community builds it"
story is largely a myth — a few dedicated people write ~90% of the code. And the
registry's success made it the #1 supply-chain attack surface (left-pad, Shai-Hulud
worm, 500+ compromised packages). Distribution at scale *creates* a trust/security
liability that didn't exist when it was just "your code." (increment.com; socket.dev;
CISA; chainguard)

**Kubernetes operators:** unbounded proliferation — hundreds of controllers, each its
own framework/conventions, "the most intractable problem in Helm's history." More
extensibility produced *more operator sprawl and more ops burden*, not more value.
Composability without a composition standard (KOI/KUDO is the attempted fix) = chaos.
(thenewstack; devops.com)

**The agent-framework graveyard (most relevant):** LangChain/LlamaIndex were built for
weak-model 2023. Backlash by late 2023; by 2025-2026 the dominant question is *"do I
even need a framework?"* Better models with native tool-calling made the abstraction
"unnecessary or actively harmful to debuggability." Winners (OpenAI Agents SDK) are
deliberately *thin* — they wrap native capability, they don't abstract it.
(mindstudio; shashankguda; akka.io)

**MCP** went from launch to *de facto standard* in ~18 months: 97M monthly SDK
downloads, every major vendor, donated to a Linux Foundation fund, 500+ public servers.
It won the "how do agents get capability" layer by being a *protocol*, not an SDK —
N×M integration collapse, "47 adapters → 6 servers," "3 days → 11 minutes."
(sitepoint MCP; tedt.org; wikipedia)

---

## The unknown-unknowns (full form)

### 1. The unit of distribution is the *runnable agent-tool*, not the "module." Builders compose to ship a THING to end-users; we have no demand side.
Every ecosystem that lived has a *consumption* surface where the built thing meets a
non-builder: VSCode users install extensions, HA users install integrations, Figma's
designers run plugins, WordPress site-owners install themes. The "build" side is
worthless until the "use" side exists — and it's a two-sided cold-start. Our frame
stops at "an external builder ships a new module cheaply" and *implicitly assumes the
builder is also the only consumer.* But every megaplan-style tool a builder makes is
itself something *someone non-technical wants to run.* We have a developer-supply story
and **zero demand-side / end-user-distribution story.** No "install and run this
agent-tool," no host that surfaces community tools to people who'd never write one.
If the only consumer of a module is the developer who wrote it, there is no ecosystem —
there's just a library with extra ceremony.

*Why blind:* the frame defined success as "builder ships a module," collapsing the
two-sided market into one side. We never asked "who *runs* the module, and how do they
find it?"

### 2. We are building a 2023-shaped framework into a 2026 world where the model is the framework and MCP is the integration standard. We may win the layer nobody will need.
The agent-framework backlash is not a style quibble — it's a *structural* shift:
capability migrated into the model (native tool-calling, long context, planning) and
into a *protocol* (MCP), and the thick orchestration SDK is the layer being
disintermediated. Arnold's node library (produce/judge/gate/revise/fan_out/...) is
exactly the LangChain-shaped abstraction the market is walking away from. Meanwhile MCP
captured the "how do I add a capability" job-to-be-done that a builder would otherwise
use our `pieces` for — and it's a vendor-neutral protocol with 97M downloads, not a
single Python SDK. The danger isn't that Arnold is badly built; it's that *the seam
where third parties want to plug in is the MCP seam, not the Arnold-node seam,* and
builders will reach for the protocol everyone already supports.

*Why blind:* the frame treats "Python in-process SDK of composable pieces" as the
given substrate and forbade re-auditing it. So no pass could ask whether the *substrate
itself* is the thing the ecosystem has already routed around.

### 3. The contract-checker is a gate that *suppresses* the ecosystem; HACS proves the live modules are the ones that fail your contract.
We equate "ecosystem enablement" with "a contract-checker that proves modules are
correct." But the ecosystems that thrived (HACS explicitly) grew on modules that
*couldn't or wouldn't satisfy core's requirements* — the scrapers, the hacks, the
"didn't have time to meet the bar." A strict in-repo contract + a single SKILL.md is a
*centralization + gatekeeping* posture. It optimizes for "modules in our repo that pass
our gate," which is the WordPress-core / k8s-core path, not the marketplace path. The
ecosystems that lost (Roam) were the closed, single-blessed-path ones. We've built the
quality gate and called it the ecosystem, when historically the gate is the thing that
*caps* ecosystem size at "what the core team will bless."

*Why blind:* "composability + a contract-checker" felt like obvious goodness, so no
pass distinguished *quality control* (gate) from *ecosystem growth* (distribution +
permissionless publish). They're often in direct tension.

### 4. Distribution + a registry are not "missing polish" — they are a different *liability surface* (trust, signing, abandonment, security) that, once you have an ecosystem, you cannot opt out of.
We treat registry/discovery/signing as a nice-to-have we'll bolt on later. But npm's
history shows the registry IS the ecosystem's center of gravity *and* its attack
surface: left-pad broke the world; the Shai-Hulud worm hit 500+ packages via one
phished maintainer. The moment third parties' code runs in *other people's* agent
pipelines — code that can call tools, spend tokens, touch repos and cloud workspaces —
you have inherited a supply-chain trust problem (signing, provenance, sandboxing,
abandonment policy) that simply does not exist while it's "your own modules." Our plan
has a contract-checker (correctness) but no *trust* model (is this author who they say,
can this module exfiltrate, what happens when it's abandoned). An agent-tool ecosystem
is a *higher*-stakes supply chain than npm because the modules have agency.

*Why blind:* the internal hardening pass owned "trust boundary" as an *in-process*
concept (typed Ports, policy spine). Nobody owned trust as a *social/distribution*
concept across strangers, because the frame had no strangers in it yet.

---

## The single biggest REFRAME

**Stop building "an SDK that other developers compose into pipelines." That is the
supply side of a two-sided market we have not staffed, built on a 2023-shaped
abstraction layer the market is actively routing around (model + MCP), gated by a
contract-checker that *limits* rather than grows the network.**

The ecosystems that won were never "a great SDK." They were a **distribution loop**:
a killer first-party thing people *run* → a low-friction way for that thing's users to
get *more* community things (HACS one-click, VSCode marketplace) → a permissionless
publish path → trust/quality signals layered on top. The SDK is the least important
part; megaplan-the-working-tool is the killer first-party app, and it should be the
*flywheel*, not "one module among many."

Concretely the reframe says: the unit is not a "pipeline a developer composes," it's a
**runnable agent-tool that a (possibly non-builder) user installs and runs, that a
builder can publish in 10 minutes to a place where users actually look, with trust and
discovery signals — and whose pluggable seam is very likely MCP/protocol, not our
node API.** If that loop doesn't exist, no amount of internal `Ports`-and-policy-spine
elegance produces an ecosystem; it produces a beautifully-engineered single-maintainer
library, which the data says is the overwhelmingly most likely outcome anyway.

---

## Sources
- VSCode vs Atom marketplace: dev.to, crazyegg.com, shiftmag.dev
- HACS: home-assistant.io/blog/2024/08/21, xda-developers, cloudapp.dev
- Obsidian vs Roam: productivitystack.io, aloa.co, deepwiki obsidian-help
- OSS maintainer reality: increment.com (rise of few-maintainer projects), socket.dev, ossinsight.io
- npm supply chain: CISA 2025/09/23 alert, chainguard.dev, medium NPM history
- k8s operators sprawl: thenewstack.io (runaway problem), devops.com
- Agent-framework backlash: mindstudio.ai, shashankguda.medium.com, akka.io
- MCP standardization: sitepoint.com, tedt.org/MCPs-2026-Roadmap, en.wikipedia.org/wiki/Model_Context_Protocol
- Two-sided cold start: andrewchen.com, forkoff.xyz, HN threads
- Framework non-composability + "plugins just add a command": timperrett.com, HN 19848857
