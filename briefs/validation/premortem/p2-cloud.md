# P2 Pre-mortem — Cloud blast radius of the Pipeline-Unification epic

Lens: what breaks for a **long-running, multi-tenant, container-resident** megaplan
chain when the epic (m1–m6) ships. Grounded in code at HEAD (2026-05-28).

The epic brief mentions cloud exactly once (line 56/105): "re-point the cloud-supervisor
SSH coupling onto the pinned (m1) contract." That is **one** of at least seven distinct
cloud failure surfaces. The brief treats cloud as a single SSH string; it is actually a
two-version distributed system (operator package vs container package) joined by (a)
internal-import `python3 -c` one-liners, (b) a JSON status contract, (c) on-disk
`chain_state.json`/`state.json` shared across a deploy boundary, and (d) per-phase
subprocess isolation that the heartbeat/supervisor watchdogs depend on.

---

## The structural fact the brief misses: cloud is a VERSION-SKEW system

`entrypoint.sh.tmpl` (L59-80) runs `pip install --upgrade --force-reinstall` of megaplan
**on every container boot**, pinned by `MEGAPLAN_REF`. The operator's local megaplan is a
*separate* install. Three independent megaplan versions are in play at once:

1. **Operator** — runs `megaplan cloud status/supervise`, parses remote files locally.
2. **Container runner** — runs `megaplan auto` / `megaplan chain start` in tmux.
3. **Container `python3 -c` snippets** — `megaplan.chain` symbols imported ad hoc over SSH.

A `cloud deploy` rebuilds/reboots the container and re-pulls megaplan, but a chain whose
`state.json`/`chain_state.json` was written by the *previous* version stays on the
persistent volume. **Mid-flight chains survive a deploy as on-disk state but get a
new-version reader.** The epic introduces schema, contract, signature, and import changes
that all cross this boundary. The brief never models version skew at all.

---

## Ranked cloud breakages

### 1. schema_version load-time validator hard-fails mid-flight chains across a deploy — m1 — CRITICAL
`ChainState.from_dict` (chain/__init__.py L472) and `state.json` have **no
`schema_version` today**; `from_dict` is tolerant (unknown keys ignored, missing keys
defaulted). m1 adds `schema_version` + "a load-time validator … migration shim for
absent/old versions."

Two skew directions, both fatal:
- **Container-old writes, operator-new reads:** `cloud_chain_status_payload` (cli.py
  L1209) does `ChainState.from_dict(json.loads(provider.read_remote_file(state_path)))`
  using the *operator's* new `from_dict`. Old state has no `schema_version`. If the
  validator rejects absent versions (or the shim is operator-side only and the container
  runner is what later re-reads), every `cloud status`/`supervise` tick raises and the
  supervisor's outer `try` (supervise.py L192) returns `supervisor_error` forever — the
  chain wedges with no human watching.
- **Operator-old reads container-new:** if the container is redeployed to the new version
  mid-chain, it writes `schema_version: 2` state; an operator still on the old build
  hits `from_dict` with no concept of the field — at best ignored, at worst the new
  validator logic isn't present so a *new* required field (e.g. `dispatch_path`) is
  silently dropped on the next operator-initiated `save_chain_state` (supervise.py L77
  round-trips state through the operator on every tick via `_remote_sync_refresh_command`).

The migration shim must be **bidirectional and present in BOTH the operator and the
container**, and the contract test (m1) must assert old→new AND new→old. The brief scopes
the shim as a single local concern.

**Fix:** version the JSON, make the validator *widen-tolerant* (accept absent = v1, never
reject forward versions outright — warn + best-effort), ship the shim in the import-surface
guard, and add a cross-version round-trip test (`from_dict(to_dict)` across the v1↔v2
boundary). Pin a deploy-time check: refuse `cloud supervise` if operator schema < container
schema.

### 2. SSH `python3 -c "from megaplan.chain import …"` runs the CONTAINER's version — m3/m1 — CRITICAL
`supervise.py::_remote_sync_refresh_command` (L53-61) builds a one-liner importing
`_capture_sync_state, ChainState, save_chain_state, load_chain_state` and **executes it in
the container**. `tests/characterization/test_import_surface.py` (L300-327) asserts these
resolve — **but only in the operator's local interpreter**. It cannot see the container's
installed version. m3 says "re-point the SSH coupling onto the pinned contract, off
internal imports," but:
- The coupling is **deeper than the brief's one line**: there is a *second* internal-import
  coupling the brief never names — `cloud resume` (cli.py L225) does
  `from megaplan.auto import _phase_command`, and **m3 ports auto.py in-process**, which is
  exactly the module most likely to be refactored. `_phase_command` is a private symbol with
  no contract test. If m3 moves/renames it, `cloud resume` breaks with `ImportError` and no
  static check fires.
- `_capture_sync_state`'s **signature** is interpolated positionally + by keyword in the
  one-liner (`branch=`, `pr_number=`, `extra_repos=`). m5's signature migration ethos
  (handlers `(root,args)`→`(root,state,hctx)`) sets a precedent; any analogous change to
  `_capture_sync_state`'s kwargs becomes a remote `TypeError` invisible to the import test.

**Fix:** m1 must pin `_capture_sync_state`/`_phase_command`/the four chain symbols as a
**stable cloud RPC surface** with a signature contract test, OR (better) replace the
`python3 -c` snippets with a first-class `megaplan chain sync-refresh --json` /
`megaplan chain next-step --json` subcommand so the coupling is the (pinned) CLI contract,
not private imports. Do this in m1, not m3 — m2 already perturbs routing symbols.

### 3. Loss of per-phase subprocess isolation → OOM/crash takes down the whole runner — m3 — CRITICAL
This is the most under-specified item and the one the brief's "in a container changes
resource/kill/crash semantics" aside (the prompt) is right to flag.

Today auto.py runs **each phase as a fresh subprocess** (`_run_phase`→`_run_megaplan`→
`spawn`, auto.py L1129/238/286), `start_new_session=True`, reaped via `kill_group`
(runtime/process.py L110) using POSIX process-group SIGTERM→SIGKILL. In a container this
boundary does real work:
- A phase that OOMs is killed by the **kernel OOM-killer**; today it kills the *phase
  subprocess* (the biggest RSS), the parent `megaplan auto` survives, synthesizes a
  `PhaseResult(exit_kind=timeout/...)` (auto.py L1164) and retries/escalates.
- A phase that hangs is bounded by `phase_timeout`/`phase_idle_timeout` and `kill_group`
  reaps the **whole codex/claude grandchild tree** via the process group.
- Zombie/orphan codex processes are reaped because each phase owns its own session.

**Going in-process collapses all of this into one PID.** Consequences:
- OOM-killer now targets the single `megaplan auto` process (or a random child) — the
  *driver itself dies*. Recovery falls entirely to `mp-supervise` (wrappers/mp-supervise),
  which restarts `megaplan auto` **from scratch** with exponential backoff. The fine-grained
  per-phase retry/escalate/force-proceed logic (m3's own `RuntimePolicy`) is bypassed because
  the process that runs it is gone. A long chain that previously rode out a transient per-phase
  OOM now hard-restarts the whole milestone.
- In-process worker invocation (codex/claude) — if m3 runs workers via in-process calls
  rather than `spawn`, then `kill_group`'s process-group reaping no longer applies and a
  per-phase timeout can't cleanly kill a wedged codex subtree; orphans accumulate on the
  long-lived volume across milestones.
- **`mp-heartbeat` (wrappers/mp-heartbeat) breaks its kill semantics:** it `pgrep -f
  'codex exec'` and sends `SIGINT` to the codex PID to unstick a stall. That still finds
  codex, but with no subprocess phase boundary the SIGINT now interrupts a child of the
  *live driver* — the driver's in-process stall detection and the heartbeat's SIGINT race,
  and a SIGINT delivered into an in-process-managed worker may corrupt driver state rather
  than cleanly failing one phase.

**Fix:** m3 must (a) keep worker dispatch as `spawn`+`kill_group` even when the *policy
loop* goes in-process (don't conflate "in-process policy" with "in-process workers"); (b)
add a memory ceiling / `ResumeCursor` checkpoint *before* each phase so an OOM-restart by
mp-supervise resumes at the phase boundary, not the milestone start; (c) reconcile
mp-heartbeat's SIGINT-to-codex with the new in-process stall policy (one owner of "kill a
stalled worker," not two); (d) add a cloud-shaped test: kill -9 the driver mid-phase, assert
mp-supervise restart resumes at the right cursor.

### 4. Status JSON contract drift breaks the operator AND the in-container driver — m4/m5 — HIGH
The operator's `cloud resume` consumes `next_step` from remote `megaplan status` JSON
(cli.py L222-227) and the in-container `megaplan auto` driver consumes
`next_step`/`valid_next`/`current_state` from `_status()` (auto.py L466-483, L482). m1 pins
the contract — good — but **m4 collapses split-brain routing** (retires
`_label_for`/`_gate_next_step`, makes Pipeline graph edges the source of next-step truth)
and m5 changes handler signatures. Both can legitimately change the *string values* of
`next_step` (e.g. a relocated planning pack emitting pack-qualified step names) while the
*schema* stays pinned. `_phase_command` (auto.py L486) hard-codes `"execute"`, `"feedback"`
and otherwise `shlex.split(next_step)`. A renamed/qualified step → operator builds an argv
the container's argparse rejects (`invalid choice`), and the container driver's own
`_phase_command` likewise. The pinned *schema* test passes; behavior breaks.

**Fix:** the m1 contract test must pin **value enumerations** (the allowed `next_step` token
set), not just field shapes, and m4/m5 must update that enum deliberately (the brief's
cross-cutting invariant covers planning *behavior* but not the *status vocabulary* cloud
parses). Add a cloud contract test that round-trips every `next_step` value through
`_phase_command` on both sides.

### 5. Relocated planning pack may not discover inside the container image — m4 — HIGH
Pack discovery is **filesystem `iterdir()` over the installed package dir**
(`_pipeline/registry.py` L259-298, `_scan_dir_for_pipeline_modules`). m4 relocates planning
to `megaplan/pipelines/planning/` and drops it from `_BUILTIN_NAMES` (registry.py L53), so it
becomes a *discovered* pack like creative/doc. In the container, megaplan is `pip install`ed
from PyPI/git — discovery now depends on the new `megaplan/pipelines/planning/` directory
(and its YAML/data resources) being **packaged** (package-data / MANIFEST / wheel `include`).
If the build omits the data files (a classic packaging miss for non-`.py` resources — note
the hyphenated `writing-panel-strict/` resource-dir pattern already in the tree), then inside
the container **planning silently fails to discover** and `megaplan init`/`auto`/`chain`
cannot run the default pipeline. The m1 discovery-integrity guard turns "silent" into "loud,"
but in an unattended container "loud" = the runner exits non-zero → `mp-supervise` retries the
same broken install forever (it only special-cases quota/rate-limit; everything else is
generic backoff, capped at OTHER_MAX restarts then gives up).

**Fix:** m4 must add a packaging test that builds the wheel and asserts
`discover_python_pipelines()` finds `planning` from the *installed* artifact (not the source
tree); add planning's resources to package-data; and the megaplan-cloud skill/Dockerfile must
bump to a megaplan version that ships the relocated pack.

### 6. extra_repos / chain_session multi-tenancy desync on redeploy — m1 (state) / m3 — MEDIUM
`extra_repos` are cloned once at boot (entrypoint `${ENSURE_REPO_BLOCK}`) and re-ensured on
`cloud chain` (cli.py L289 `_ensure_repo_command`). `chain_session` (spec.py L111) and
`resolved_workspace`/`extra_repos` live in `ChainState` (chain/__init__.py L447-449) and are
**persisted back through the operator** via the sync-refresh one-liner (supervise.py L65-79,
`s.resolved_workspace = …; s.chain_session = …; save_chain_state(...)`). This is a
read-modify-write of container state performed by the *operator's* serializer every tick. With
schema skew (#1), the operator round-trip can **drop or rewrite** `extra_repos`/`chain_session`
if its `to_dict`/`from_dict` disagree with the container's — silently un-tenanting a
multi-repo chain (siblings vanish from state, later milestones that depend on an extra repo
block). Compounds #1: the bidirectional shim must preserve these multi-tenant fields exactly.

**Fix:** make the operator's sync-refresh round-trip **field-preserving** (read raw JSON,
mutate only the two keys, write back — don't deserialize→reserialize through a possibly-skewed
dataclass). Add a test: operator-new round-trips container-old state and `extra_repos` is
byte-stable.

### 7. mp-supervise restart loop amplifies any new fail-loud — m2/m1 — MEDIUM
m2 replaces `DEFAULT_AGENT_ROUTING[step]` with **fail-loud** slot resolution (brief m2).
But the container entrypoint (template.py L155-164, `_agent_routing_block`) sets
`megaplan config set agents.<step>` for **every key in `DEFAULT_AGENT_ROUTING`** at boot. If
m2 renames/removes routing keys or makes unknown-slot resolution raise, an existing
`cloud.yaml`'s `agents:` mapping (or the boot routing block baked into a not-yet-redeployed
container) can now hard-error where it previously silently defaulted. Combined with
mp-supervise's restart-on-nonzero, a fail-loud at phase dispatch becomes a **crash loop** that
exhausts OTHER_MAX and abandons the chain. Fail-loud is correct locally; in an unattended
container it needs a *quarantine* state, not a crash.

**Fix:** m2's fail-loud path, when it reaches the auto/chain driver, should transition the
plan to a `blocked`/`human_prerequisite` state the supervisor already understands
(supervise.py READ_ONLY_STATUSES) rather than exiting non-zero into mp-supervise's blind
restart loop. Regenerate the entrypoint routing block against the new slot contract and bump
the cloud image.

---

## The cloud surface the epic UNDER-SPECIFIED

1. **Version skew as a first-class concern.** The brief models one megaplan; cloud is three
   (operator / container runner / `python3 -c`). Every schema/contract/signature change must
   be evaluated *across a deploy boundary with persistent state*. Nothing in m1–m6 says so.
2. **The second and third internal-import couplings.** The brief names the
   `_capture_sync_state` SSH coupling; it omits `cloud resume`'s
   `from megaplan.auto import _phase_command` (directly in m3's blast zone) and the
   operator-side `chain_module.*` calls in `cloud_chain_status_payload` (six private symbols).
3. **Subprocess isolation as a container safety property, not just an "isolation/timeout
   boundary."** m3's "go in-process" is framed as a local execution-model cleanup; in a
   container it is the OOM/crash/zombie containment boundary and the contract the
   `mp-heartbeat` watchdog and `mp-supervise` restarter are built on. m3 must keep worker
   dispatch out-of-process and add OOM-resume checkpointing + reconcile the two stall-killers.
4. **Packaging of the relocated planning pack.** Filesystem discovery from an *installed*
   wheel is not the same as from the source tree; m4 needs a wheel-level discovery test and
   package-data wiring, plus a coordinated cloud-image version bump.
5. **The status `next_step` value vocabulary** (not just schema) as part of the pinned
   contract — m4/m5 can change values while the schema test stays green.
6. **Fail-loud → unattended crash-loop.** m2's correct fail-loud must land as a supervisor-
   recognized blocked state, never a non-zero exit into mp-supervise's blind restart.
7. **The operator-side serializer round-trip** in sync-refresh is a hidden state-rewrite path;
   it must be field-preserving under skew to protect multi-tenant `extra_repos`/`chain_session`.

**Cross-cutting recommendation:** add a `briefs/epic-pipeline-unification/cloud-invariants.md`
handoff that every milestone cites, and a CI lane that builds the wheel, boots a container
against a *previous-version* state fixture, and runs status/supervise/resume across the skew.
