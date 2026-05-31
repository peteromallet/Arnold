# Interrogation — SUCCESS CREATES PROBLEMS (second-order)

**Lens:** Assume the epic ships at full ambition and *succeeds*: third parties compose the same SDK
pieces (dispatch/state/emit/evidence/config + node library) to build a fourth, fifth, Nth thing,
discovered identically to planning/jokes/doc. What NEW problems arrive from external adoption that the
plan does not reserve room for? I am NOT arguing to reduce scope — the recommendations below are things
the plan must ADD or sequence in NOW so success is survivable.

Code verified against `main`, 2026-05-29.

---

## BITE 1 (CRITICAL) — Discovery EXECUTES untrusted package code, and a5 never looked at the discovery seam

**Where:** `megaplan/_pipeline/registry.py:336` (`spec.loader.exec_module(module)`) inside
`_load_module_from_path`, reached from `discover_python_pipelines()` (`registry.py:360`), which scans
`~/.megaplan/pipelines` (`registry.py:~385`, the second `scan_roots` entry with `package_prefix=None`).
M6 scope item 1 removes `_BUILTIN_NAMES` and makes a package a first-class discovered citizen
(`m6-megaplan-as-module.md:28,47-52`), and the EPIC explicitly states "discovery makes external packages
first-class" (`pipeline-unification-EPIC.md:37`).

**Why it bites:** The single confidence doc on trust — `a5-sandbox-trust.md` — answers a *different*
question. It asks "does making **dispatch/execution** a shared service open a trust hole?" and answers
"NO real new hole. Low risk" because trust is process-global and a resident loop dispatching variants
inherits the same ambient context (a5 §VERDICT, §3). Every word of a5 is about the *runtime/dispatch*
boundary (`install_sandbox`, ContextVar, `MEGAPLAN_TRUSTED_CONTAINER`). **It never examines that
discovery imports and executes the package's Python at registry-build time** — before any
`install_sandbox` block, before any dispatch, before any sandbox ContextVar is set. a5's own residual #1
("make `install_sandbox` mandatory on any shared *tool-bearing dispatch path*") does not cover module
import: `import`-time top-level code in a discovered package runs with zero sandbox by construction. So
the moment success means "I `pip install arnold-coolpipeline` / drop a folder in `~/.megaplan/pipelines`,"
running *any* megaplan command that triggers discovery is arbitrary-code-execution of the package author.
And discovery is eager and ambient — `read_skill_md`, `status`, `list`, profile resolution all funnel
through the registry.

The current `except Exception: ... return None` (`registry.py:337`) is "discovery is best-effort" — it
swallows *crashes*, not *side effects*. A malicious or merely buggy top-level `import` already ran.

**Severity:** critical. This is the textbook "community pipeline = untrusted code, who sandboxes it?"
problem named in the brief, and the one trust doc the epic relies on has a scope hole exactly here.

**What it forces (add now, don't defer):**
- A **discovery/load trust boundary distinct from the dispatch trust boundary.** Manifest-first
  discovery: read a *static, non-executing* manifest (TOML/JSON: name, driver, entrypoint, declared
  capabilities, SKILL.md path) WITHOUT importing the module. Defer `exec_module` until a package is
  actually selected to run, and gate it on an explicit trust decision (in-tree / user-blessed / quarantined).
- A5 must be **re-opened with the discovery seam in its scope** before M6 (it currently green-lights the
  thing it never looked at). M6's "SKILL.md required, fail discovery loud if absent" (`m6:28,67`) is the
  natural place to also require the static manifest — make the manifest, not the import, the discovery unit.
- A `trust` field on the package contract (EPIC's "package contract = manifest + driver + bindings +
  SKILL.md") so the SDK can refuse to import / refuse to run-trusted a package the operator hasn't blessed.

---

## BITE 2 (HIGH) — The node library is declared a "public, stable, documented" surface with NO versioning, deprecation, or compat mechanism — and the whole epic's value proposition is to keep changing it

**Where:** M5 terminal step declares `patterns.py` the **"public, documented composition vocabulary"**
where "every macro is a node-library entry with a stable signature" (`m5-extract-features.md:197-199`,
done-criteria `:255`). The EPIC's reason-for-being is the abstraction-stress-test verdict: "the TYPES were
too planning-shaped — fix is decoupling" (`EPIC:60-77`), with P0/P1/P2 reshapings of `JoinFn`, `Reduce`,
`gate` consequence params, the state-evolution axis, `select`, etc.

**Why it bites:** These two facts collide on success. The instant a third party composes against
`select()`, `Reduce[T]`, the `gate` consequence enum, or a node signature, those signatures become a
**public API you can no longer freely change** — but the epic is *designed to keep refining the types*
(M2 de-planning-izes, M3 adds the state-evolution axis + gate-consequence params, future work will add
more missing primitives the next non-planning sketch surfaces). The plan has back-compat machinery for
*planning's own legacy* (`extra="ignore"`, name aliases, phase-slot preservation — EPIC §122) but
**nothing for the SDK-piece surface that external packages pin against**: no SemVer on the node library,
no `arnold_api_version` on the manifest/package contract, no deprecation window, no "supported piece
versions" check at discovery. "Stable signature" is asserted (`m5:198`) with no mechanism to make it true
or to evolve it safely once external code depends on it.

A bad-fit `JoinFn` shipped to external users is forever; today fixing `JoinFn`-returns-`GateRecommendation`
(`pattern_types.py:19`) is a free internal refactor — post-success it's a breaking change across an
unknown population of installed packages.

**Severity:** high. Not exploitable, but it silently converts the epic's central activity (decoupling /
type-reshaping) from "cheap internal refactor" into "ecosystem-breaking change" the day external users
arrive — and there's no version gate to even detect the break.

**What it forces (add now):**
- An **`arnold_api_version` / piece-protocol version on the package contract manifest**, checked at
  discovery; a package declares which SDK piece-surface version it composes against. This is the same
  manifest BITE 1 wants — fold them.
- A **stability tier per node-library entry** in the SKILL/manifest (`stable | provisional | internal`) so
  the epic can keep reshaping `provisional` types (it WILL need to — more non-planning sketches will
  surface more missing primitives) while `stable` ones carry a deprecation contract.
- A deprecation/alias policy for the node library mirroring the planning name-alias policy, but for the
  *general* surface — reserve the seam now even if the first deprecation is far off.

---

## BITE 3 (HIGH) — Shared services (key/rate broker, cost, quota budget) are designed for two TRUSTED in-house tenants; a community package becomes an unaccountable, un-isolated co-tenant of a shared resource

**Where:** M4 §1 adds a cross-process `key_broker`/`rate_broker` over an `fcntl.flock`'d on-disk ledger
"with a single global quota budget" (`m4-services.md:26`), and cost attribution carrying an opaque
`tenant_id` + `dispatch_id` (`m4:25`). The `CostTracker` cap "must see both plan and non-plan spend for
caps to hold" (m4 open-Q 3, `:47`). a2-concurrency frames the tenants as planning-runs + resident.

**Why it bites:** Every protection in M4 is *cooperative and self-reported*. `tenant_id` is opaque and
caller-supplied (`m4:25`); the global quota budget is a single shared number (`m4:26`); the broker assumes
tenants back off honestly on a shared cooldown. That is fine for two first-party tenants. On success, a
**third-party package is a co-tenant on the same physical key pool, the same global quota budget, and the
same CostTracker cap** — but it is untrusted code (BITE 1) that can (a) spoof or reuse another tenant's
`tenant_id` to charge cost elsewhere or evade its own cap, (b) ignore the cooldown and thundering-herd the
shared keys (the exact a2 failure the broker fixes for honest tenants, reintroduced by a dishonest one),
(c) exhaust the single global quota budget and degrade *every other* pipeline on the box — the "bad
community package degrading shared services" risk named in the brief. The epic centralizes these resources
(good, fixes a2 for cooperating tenants) but adds no **per-package quota isolation, no tenant-id
authenticity, and no resource accounting boundary** for an adversarial co-tenant.

**Severity:** high. The blast radius of one greedy/buggy community package is *all other tenants on the
shared ledger* — and cloud (`extra_repos[]`, `chain_session`) already runs multi-tenant.

**What it forces (add now):**
- **Per-package resource scope** on the broker: a package's `tenant_id` is *assigned by the SDK at load
  time*, not self-declared, and the global quota budget is partitioned/sub-budgeted per package (or per
  trust tier) so one package cannot starve the pool. Reserve the ledger schema for per-tenant sub-budgets
  NOW — retrofitting partitioning into a flat `time.time()` ledger later is a migration.
- **Cost accounting keyed to the SDK-assigned tenant**, so a community package's spend is attributable and
  cappable independent of what it self-reports — the CostTracker cap must be enforceable per package.
- Decide the trust tier (BITE 1) gates broker access: an unblessed package gets a *bounded* sub-budget or
  its own keys, never the operator's pooled keys at full quota.

---

## missing_abstraction
**A package-trust / capability tier on the package contract, evaluated at DISCOVERY/LOAD time (separate
from the runtime dispatch sandbox).** The EPIC's package contract is "manifest + driver + bindings +
SKILL.md" (`EPIC:37`) and a5 reasons entirely about the *runtime* trust boundary
(`MEGAPLAN_TRUSTED_CONTAINER`, `install_sandbox` ContextVar). Nothing models "how much do I trust this
package's *code* (its imports, its top-level execution, its claimed capabilities, its share of pooled
resources)?" That single missing abstraction — a declared, operator-blessed trust/capability tier carried
on the manifest and checked before `exec_module` and before broker access — is the common root of all
three bites (untrusted import, unversioned surface a package pins, unaccountable shared-resource co-tenant).
It must be a first-class field of the package contract the epic is already defining, not a bolt-on later.

## over_complication
**The cross-process key/rate broker built for "two concurrent tenants" (m4 done-criteria #4, `m4:62`)
before there is a non-first-party tenant that actually needs cross-process key sharing.** The two in-house
tenants (planning subprocess + resident async) and the M4 acceptance caller all run under one operator's
keys; the flock'd wall-clock ledger + global quota budget is real engineering (a2) but its *value* only
materializes with mutually-distrusting external co-tenants — which is precisely the case the broker does
NOT yet defend against (BITE 3). The complexity is correctly sequenced as a backend, but it is half a
solution: the hard part (per-package isolation/accounting) is what makes it worth the flock dance, and
that's unscoped. Not "do less" — "the broker's complexity is only justified once you ALSO build the
per-package partitioning; otherwise it's an elaborate honest-tenant cooldown."

## over_simplification
**`a5-sandbox-trust.md`'s "Verdict: NO real new hole. Low risk."** It is correct *for the question it
asked* (shared dispatch in one process at one trust level) and dangerously over-simplified as the epic's
sole trust analysis, because (a) it scopes out module discovery/import entirely — the actual untrusted-
code-execution seam (`registry.py:336`) — and (b) it assumes the only callers are first-party (planning +
resident), which is the exact assumption M6's "external packages first-class" demolishes. Carrying a5's
"low risk" conclusion into M6 unchanged is the single most likely way the trust problem ships unaddressed.
