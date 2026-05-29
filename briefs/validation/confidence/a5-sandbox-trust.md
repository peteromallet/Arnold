# A5 — Sandbox / Trust / Privilege model vs. shared-dispatch epic

**Question:** Does making dispatch/execution a SHARED service (callable by any tool,
incl. a resident Arnold loop) open a sandbox/trust/privilege hole?

**Verdict: NO real new hole. Low risk.** The trust model is ambient (process-env +
context-local cwd), not per-caller — but it was *always* ambient, and a shared
dispatch service inherits the *same* ambient context every caller already runs in.
There is no privilege escalation surface because there are no differentiated
privileges to escalate *between*. One real foot-gun to nail down: the sandbox cwd
must travel with the dispatch (it already does, via ContextVar), and a resident
loop must not leak a stale `SANDBOX_CWD` across heterogeneous invocations.

---

## 1. Current sandbox / trust model — who decides what an invocation can touch

There are **two independent layers**, and they are decided in two different places:

### Layer A — In-process tool sandbox (hermes/Claude-SDK path)
`megaplan/runtime/sandbox.py`. Mechanism:
- `install_sandbox(project_dir)` is a context manager that sets a **`SANDBOX_CWD`
  ContextVar** (`sandbox.py:87`, `:375-406`).
- Tool handlers for `terminal`, `write_file`, `patch` are wrapped **once, globally,
  idempotently** (`_ensure_wrappers_installed`, `:104-137`). The wrappers read
  `get_sandbox_cwd()` *at call time* (`:285`, `:321`, `:344`).
- If the ContextVar is `None`, wrappers **delegate unchanged** to the original
  handler — i.e. **no sandbox active = no path enforcement** on write/exec.
- When set, writes/exec are coerced/refused to stay inside `project_dir`. `read_file`
  and `search_files` are deliberately **not** sandboxed (`:33-35`).
- Installed by the hermes worker whenever a toolset is active
  (`megaplan/workers/hermes.py:1062-1064`), scoped to that worker invocation via an
  `ExitStack`. **Config = the `project_dir`/worktree path passed into the worker.**
  Per-run, not env, not global.

This is **thread/context safe by construction**: the ContextVar is per-execution-
context, so concurrent worker invocations with different `project_dir`s each see only
their own value (`:386-389`). This is the property that matters for a shared service.

### Layer B — Subprocess agent sandbox (Codex / Shannon path)
The Codex and Shannon workers shell out to external CLIs that carry their *own*
sandbox, and megaplan decides the flags from **process environment**, not per-call:
- `_trusted_container()` (`_impl.py:854-872`) reads **`MEGAPLAN_TRUSTED_CONTAINER`**
  (process env). When truthy, Codex is launched with
  `--dangerously-bypass-approvals-and-sandbox` (`_impl.py:1758-1759`, `:1782-1787`)
  and Shannon with `--dangerously-skip-permissions` (`shannon.py:999-1000`,
  `:1064-1065`). Claude/Shannon also gets `skipDangerousModePermissionPrompt`
  seeded (`shannon.py:571`).
- When **not** trusted, Codex runs in `workspace-write` with `writable_roots` derived
  from `work_dir` + auto-detected workspace root (`_auto_writable_roots`,
  `_impl.py:809-851`) + `state.config.extra_writable_roots`. `MEGAPLAN_NARROW_SANDBOX=1`
  disables the auto-widening (`_impl.py:828-831`).
- The trusted flag is **set once for the whole process** — in cloud, the entrypoint
  exports `MEGAPLAN_TRUSTED_CONTAINER=1` (`cloud/templates/entrypoint.sh.tmpl:19`;
  also injected on the `chain start` command line, `cloud/cli.py:550`). Locally it is
  unset, so local runs keep the bounded sandbox (`shannon.py:177-179` keeps local
  Shannon non-trusted by default).
- A `_sandbox_fingerprint` (`_impl.py:875-897`) hashes `trusted` + `work_dir` onto
  each persistent Codex session and **refuses to resume** a session whose sandbox
  inputs changed — the one existing guard against trust drift across invocations.

**Note:** `megaplan/runtime/capabilities.py` ("CONTAINER_CAPABILITIES",
"HUMAN_CAPABILITIES") is about *verification* capabilities (who can run tests vs.
needs a human to eyeball a UI), **not** privilege/sandbox. It does not gate file/
shell/network access and is not part of the trust boundary. Easy to misread.

**Summary of "who decides":** the *bound* (which dir) is per-invocation (`project_dir`
/ `work_dir`, ContextVar or CLI flag). The *trust mode* (bounded vs. full-access) is
**process-global env** (`MEGAPLAN_TRUSTED_CONTAINER`). Network is not separately
gated — it's whatever the host/container allows.

## 2. Does the sandbox context travel WITH the dispatch?

**Layer A: yes, and it's the right primitive for a shared service.** The sandbox is a
ContextVar set by a context manager around the actual agent call. Any shared dispatch
function that wraps the call in `install_sandbox(project_dir)` (as hermes already does)
gets the correct, per-call boundary regardless of who called it. A resident Arnold
loop dispatching N variants into N worktrees would call `install_sandbox` per variant;
ContextVar isolation means variant A cannot write into variant B's tree even
concurrently.

**The one foot-gun:** if a shared dispatch path runs the agent call **outside** an
`install_sandbox` block (ContextVar = None), the wrappers delegate unchanged →
**unbounded writes/exec**. Today only hermes installs it, and only when `toolsets` is
truthy. A new shared service must make `install_sandbox` non-optional (or default-deny)
on the tool-bearing path, not rely on each caller remembering.

**Layer B: the trust mode does NOT travel per-call — it's read from `os.environ` at
command-build time.** A shared dispatch service changes nothing here: every caller in
the same process already sees the same `MEGAPLAN_TRUSTED_CONTAINER`. There is no
mechanism today to dispatch one sub-call "trusted" and another "untrusted" in the same
process, and the epic does not need one. The `work_dir` bound *does* travel per-call.

## 3. Multi-tenant: could one tool's dispatch run at another's trust level?

**There is no per-caller capability/permission notion today — at all.** Trust is a
single process-wide boolean; the bound is a path argument. "Tenancy" in megaplan-cloud
(`extra_repos[]`, `chain_session`) is about *which repos/workspaces* a run touches, not
about differentiated privilege between callers. Every tool/loop in one process shares
one trust level. So:
- Could tool X's dispatch run at tool Y's trust level? They run at the **same** level
  by construction (one process env). There is nothing to cross.
- The only cross-tenant risk is the **bound**, not the trust mode: a shared service
  that forgets to scope `project_dir`/`work_dir` per dispatch could let variant A write
  into variant B's worktree. ContextVar (Layer A) and the `-C`/`writable_roots` flags
  (Layer B) already prevent this *when set correctly per call*. The risk is a coding
  bug in the shared service, not an architectural privilege hole.

## 4. Real new attack surface, or already-centralized-enough?

**Already centralized enough — the epic does not introduce a new trust boundary.**
- Trust mode is a single, environment-controlled switch flipped only by the operator/
  container, not by model-controllable input. A model cannot set
  `MEGAPLAN_TRUSTED_CONTAINER` from inside a worker call (it's read from the megaplan
  process env at subprocess-spawn time). A shared dispatch service called by a resident
  loop runs in that same process and cannot elevate itself.
- The Layer-A sandbox is exactly the kind of context-local primitive a shared service
  wants: set-per-call, isolated-by-context, fail-closed-if-you-wrap-the-call.
- The genuinely sharp edge that pre-dates the epic: **trusted mode = literally
  `--dangerously-bypass-...`** (full host access inside the container). That is fine
  under the documented "container IS the sandbox" model, but it means in trusted mode
  the per-call `project_dir` bound on Layer B is advisory (Codex is unsandboxed). A
  resident long-lived loop in a trusted container that dispatches *untrusted-origin*
  plan text is therefore writing with full container privilege — same as today's
  `megaplan auto` in cloud. The epic doesn't worsen this; it inherits it.

### Residual / what the epic must guard
1. **Make `install_sandbox` mandatory on any shared tool-bearing dispatch path**, not
   opt-in per caller. Default to deny (require an explicit project_dir) rather than
   delegate-unchanged when ContextVar is None for tool calls.
2. **Resident-loop ContextVar hygiene:** a long-lived Arnold loop must enter/exit
   `install_sandbox` per dispatch so a stale `SANDBOX_CWD` from a prior variant never
   leaks into the next. ContextVar reset via the context manager handles this *if used*;
   a loop that sets it manually once and reuses it would be a bug.
3. **Per-dispatch bound plumbing:** the shared service signature must take
   `project_dir`/`work_dir` as a required per-call argument, never read it from a
   shared/global.
